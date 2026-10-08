import sqlite3
import time
import typing

class PositionalComparator:
    """
    Führt einen positionellen (koordinatenweisen) Abgleich zwischen zwei Tabellen 
    in SQLite durch. Basiert auf der FULL OUTER JOIN Architektur für maximale 
    Performance und minimalen Speicherverbrauch.
    Generiert serverseitig 'diff1', 'diff2' und 'same' Ansichten als neue SQLite-Tabellen.
    """
    
    @staticmethod
    def coordinatewise_sheet_vs_sheet(v_list1, sheet_info1: dict, v_list2, sheet_info2: dict, mapping=None) -> dict:
        """
        Führt den positionellen Abgleich für zwei definierte prepared-Sheets durch.
        
        Args:
            v_list1: VirtualList Instanz der Datei 1 (enthält die sqlite3 Connection)
            sheet_info1: Metadaten (dict) zur prepared Tabelle aus Datei 1
            v_list2: VirtualList Instanz der Datei 2 
            sheet_info2: Metadaten (dict) zur prepared Tabelle aus Datei 2
            mapping: Das SheetMapping Objekt mit den Regeln pro Spalte (optional)
            
        Returns:
            Ein Dictionary mit den Namen der erstellten Ergebnis-Tabellen.
        """
        start = time.process_time()
        
        # 1. Temporärer Transfer der Datei2-Daten in die DB von Datei1
        conn1 = v_list1.conn
        cursor1 = conn1.cursor()
        
        table1 = sheet_info1["table"]
        table2_orig = sheet_info2["table"]
        
        cols1 = sheet_info1["num_cols"]
        cols2 = sheet_info2["num_cols"]
        max_cols = max(cols1, cols2)
        
        cursor1.execute(f"PRAGMA table_info({table1})")
        type_map1 = {row[1]: row[2] for row in cursor1.fetchall()}
        
        cursor2 = v_list2.conn.cursor()
        cursor2.execute(f"PRAGMA table_info({table2_orig})")
        type_map2 = {row[1]: row[2] for row in cursor2.fetchall()}
        
        merged_type_map = {}
        for i in range(max_cols):
            col_name = f'Col_{i}'
            t1 = type_map1.get(col_name, "TEXT")
            t2 = type_map2.get(col_name, "TEXT")
            
            if t1 == t2:
                merged_type_map[col_name] = t1
            elif "NUMERIC" in (t1, t2):
                merged_type_map[col_name] = "NUMERIC"
            elif "DATETIME" in (t1, t2):
                merged_type_map[col_name] = "DATETIME"
            elif "BOOLEAN" in (t1, t2):
                merged_type_map[col_name] = "BOOLEAN"
            else:
                merged_type_map[col_name] = "TEXT"

        # Erstelle eine temporäre Tabelle in DB1 für die Daten aus DB2
        temp_table2 = "temp_compare_" + table2_orig
        cursor1.execute(f"DROP TABLE IF EXISTS {temp_table2}")
        
        col_defs2_list = []
        for i in range(cols2):
            col_name = f'Col_{i}'
            c_type = merged_type_map.get(col_name, "TEXT")
            col_defs2_list.append(f'"{col_name}" {c_type}')
            
        col_defs2 = ", ".join(col_defs2_list)
        if not col_defs2:
            col_defs2 = '"Col_0" TEXT'
            
        cursor1.execute(f"CREATE TABLE {temp_table2} (row_index INTEGER PRIMARY KEY, {col_defs2})")
        
        cursor2 = v_list2.conn.cursor()
        cursor2.execute(f"SELECT rowid, * FROM {table2_orig}")
        
        insert_sql = f"INSERT INTO {temp_table2} VALUES (?, {', '.join(['?'] * cols2)})"
        while True:
            chunk = cursor2.fetchmany(10000)
            if not chunk:
                break
            cursor1.executemany(insert_sql, chunk)
        conn1.commit()
        
        # 2. Anpassung der Spalten (Schema-Alignment)
        for i in range(cols1, max_cols):
            col_name = f'Col_{i}'
            c_type = merged_type_map.get(col_name, "TEXT")
            cursor1.execute(f'ALTER TABLE {table1} ADD COLUMN "{col_name}" {c_type}')
        for i in range(cols2, max_cols):
            col_name = f'Col_{i}'
            c_type = merged_type_map.get(col_name, "TEXT")
            cursor1.execute(f'ALTER TABLE {temp_table2} ADD COLUMN "{col_name}" {c_type}')
            
        # 3. Generierung der SQL-Statements für diff1, diff2, same1, same2
        table_diff1 = f"diff1_{table1}_{table2_orig}"
        table_diff2 = f"diff2_{table1}_{table2_orig}"
        table_same1 = f"same1_{table1}_{table2_orig}"
        table_same2 = f"same2_{table1}_{table2_orig}"
        
        cursor1.execute(f"DROP TABLE IF EXISTS {table_diff1}")
        cursor1.execute(f"DROP TABLE IF EXISTS {table_diff2}")
        cursor1.execute(f"DROP TABLE IF EXISTS {table_same1}")
        cursor1.execute(f"DROP TABLE IF EXISTS {table_same2}")
        
        select_diff1 = ["D1.rowid AS row_index"]
        select_diff2 = ["D2.row_index AS row_index"]
        select_same1 = ["D1.rowid AS row_index"]
        select_same2 = ["D2.row_index AS row_index"]
        
        orig_col_map1 = sheet_info1.get("orig_col_map", [])
        orig_col_map2 = sheet_info2.get("orig_col_map", [])

        for i in range(max_cols):
            c = f'"Col_{i}"'
            orig_c1 = orig_col_map1[i] if i < len(orig_col_map1) else -1
            orig_c2 = orig_col_map2[i] if i < len(orig_col_map2) else -1
            
            rule = None
            if mapping and mapping.column_mappings:
                for cm in mapping.column_mappings:
                    if (cm.col1_idx != -1 and cm.col1_idx == orig_c1) or (cm.col2_idx != -1 and cm.col2_idx == orig_c2):
                        rule = cm.rule
                        break
                
            if not rule:
                # Unmapped columns should be ignored (not generate diffs)
                cond_same = "1=1"
            else:
                if getattr(rule, 'check_greater_eq', False):
                    # D1 >= D2 is compliant
                    cond_same = f"(D1.{c} IS NOT NULL AND D2.{c} IS NOT NULL AND CAST(REPLACE(D1.{c}, ',', '.') AS NUMERIC) >= CAST(REPLACE(D2.{c}, ',', '.') AS NUMERIC))"
                elif getattr(rule, 'check_less_eq', False):
                    # D1 <= D2 is compliant
                    cond_same = f"(D1.{c} IS NOT NULL AND D2.{c} IS NOT NULL AND CAST(REPLACE(D1.{c}, ',', '.') AS NUMERIC) <= CAST(REPLACE(D2.{c}, ',', '.') AS NUMERIC))"
                elif rule.check_equivalent:
                    cond_same = f"D1.{c} IS NOT DISTINCT FROM D2.{c}"
                elif rule.check_greater:
                    # D1 > D2 is compliant
                    cond_same = f"(D1.{c} IS NOT NULL AND D2.{c} IS NOT NULL AND CAST(REPLACE(D1.{c}, ',', '.') AS NUMERIC) > CAST(REPLACE(D2.{c}, ',', '.') AS NUMERIC))"
                elif rule.check_less:
                    # D1 < D2 is compliant
                    cond_same = f"(D1.{c} IS NOT NULL AND D2.{c} IS NOT NULL AND CAST(REPLACE(D1.{c}, ',', '.') AS NUMERIC) < CAST(REPLACE(D2.{c}, ',', '.') AS NUMERIC))"
                else:
                    cond_same = f"D1.{c} IS NOT DISTINCT FROM D2.{c}"
            
            select_diff1.append(f'CASE WHEN NOT ({cond_same}) OR ({cond_same}) IS NULL THEN D1.{c} ELSE NULL END AS {c}')
            select_diff2.append(f'CASE WHEN NOT ({cond_same}) OR ({cond_same}) IS NULL THEN D2.{c} ELSE NULL END AS {c}')
            select_same1.append(f'CASE WHEN {cond_same} THEN D1.{c} ELSE NULL END AS {c}')
            select_same2.append(f'CASE WHEN {cond_same} THEN D2.{c} ELSE NULL END AS {c}')
            
        join_clause = "D1.rowid = D2.row_index"
        if mapping and mapping.row_matching_mode == "key_based" and mapping.key_mappings:
            join_conds = []
            km = mapping.key_mappings[0]
            for orig_idx1, orig_idx2 in zip(km.col1_indices, km.col2_indices):
                try:
                    prep_c1 = sheet_info1["orig_col_map"].index(orig_idx1)
                    prep_c2 = sheet_info2["orig_col_map"].index(orig_idx2)
                    join_conds.append(f"D1.\"Col_{prep_c1}\" = D2.\"Col_{prep_c2}\"")
                except ValueError:
                    pass
            if join_conds:
                join_clause = " AND ".join(join_conds)

        sql_diff1 = f"""
            CREATE TABLE {table_diff1} AS 
            SELECT {', '.join(select_diff1)}
            FROM {table1} D1
            FULL OUTER JOIN {temp_table2} D2 ON {join_clause}
        """
        
        sql_diff2 = f"""
            CREATE TABLE {table_diff2} AS 
            SELECT {', '.join(select_diff2)}
            FROM {table1} D1
            FULL OUTER JOIN {temp_table2} D2 ON {join_clause}
        """
        
        sql_same1 = f"""
            CREATE TABLE {table_same1} AS 
            SELECT {', '.join(select_same1)}
            FROM {table1} D1
            FULL OUTER JOIN {temp_table2} D2 ON {join_clause}
        """
        
        sql_same2 = f"""
            CREATE TABLE {table_same2} AS 
            SELECT {', '.join(select_same2)}
            FROM {table1} D1
            FULL OUTER JOIN {temp_table2} D2 ON {join_clause}
        """
        
        # 4. Ausführung in SQLite
        cursor1.execute(sql_diff1)
        cursor1.execute(sql_diff2)
        cursor1.execute(sql_same1)
        cursor1.execute(sql_same2)
        
        cursor1.execute(f"DROP TABLE {temp_table2}")
        conn1.commit()
        
        # 5. Transfer diff2 and same2 to v_list2's database
        cursor2 = v_list2.conn.cursor()
        
        col_defs_list = []
        for i in range(max_cols):
            col_name = f'Col_{i}'
            c_type = merged_type_map.get(col_name, "TEXT")
            col_defs_list.append(f'"{col_name}" {c_type}')
            
        col_defs = ", ".join(col_defs_list)
        if not col_defs:
            col_defs = '"Col_0" TEXT'
            
        # Transfer diff2
        cursor2.execute(f"DROP TABLE IF EXISTS {table_diff2}")
        cursor2.execute(f"CREATE TABLE {table_diff2} (row_index INTEGER PRIMARY KEY, {col_defs})")
        
        cursor1.execute(f"SELECT * FROM {table_diff2}")
        insert_sql2 = f"INSERT INTO {table_diff2} VALUES (?, {', '.join(['?'] * max_cols)})"
        while True:
            chunk = cursor1.fetchmany(10000)
            if not chunk:
                break
            cursor2.executemany(insert_sql2, chunk)
        v_list2.conn.commit()
        cursor1.execute(f"DROP TABLE {table_diff2}")
        
        # Transfer same2
        cursor2.execute(f"DROP TABLE IF EXISTS {table_same2}")
        cursor2.execute(f"CREATE TABLE {table_same2} (row_index INTEGER PRIMARY KEY, {col_defs})")
        
        cursor1.execute(f"SELECT * FROM {table_same2}")
        insert_sql3 = f"INSERT INTO {table_same2} VALUES (?, {', '.join(['?'] * max_cols)})"
        while True:
            chunk = cursor1.fetchmany(10000)
            if not chunk:
                break
            cursor2.executemany(insert_sql3, chunk)
        v_list2.conn.commit()
        cursor1.execute(f"DROP TABLE {table_same2}")
        
        cursor1.execute(f"SELECT COUNT(*) FROM {table_diff1}")
        diff1_rows = cursor1.fetchone()[0]
        
        cursor2.execute(f"SELECT COUNT(*) FROM {table_diff2}")
        diff2_rows = cursor2.fetchone()[0]
        
        cursor1.execute(f"SELECT COUNT(*) FROM {table_same1}")
        same1_rows = cursor1.fetchone()[0]
        
        cursor2.execute(f"SELECT COUNT(*) FROM {table_same2}")
        same2_rows = cursor2.fetchone()[0]

        end = time.process_time()
        
        return {
            "diff1": {"table": table_diff1, "db": v_list1, "num_cols": max_cols, "num_rows": diff1_rows},
            "diff2": {"table": table_diff2, "db": v_list2, "num_cols": max_cols, "num_rows": diff2_rows},
            "same1": {"table": table_same1, "db": v_list1, "num_cols": max_cols, "num_rows": same1_rows},
            "same2": {"table": table_same2, "db": v_list2, "num_cols": max_cols, "num_rows": same2_rows},
            "time_taken": end - start
        }

    @staticmethod
    def cleanup(v_list1, table_names: typing.List[str]):
        """Hilfsmethode, um nicht mehr benötigte Ergebnis-Tabellen zu löschen"""
        cursor = v_list1.conn.cursor()
        for t in table_names:
            cursor.execute(f"DROP TABLE IF EXISTS {t}")
        v_list1.conn.commit()
