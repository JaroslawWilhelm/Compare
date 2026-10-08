import sqlite3
import time
import typing

class CrossCheckComparator:
    """
    Führt einen Cross-Check (Element vs Element) Abgleich zwischen zwei Tabellen 
    in SQLite durch. Zählt die Häufigkeit aller Elemente unabhängig von der Position.
    Generiert serverseitig 'diff1', 'diff2' und 'same' Ansichten als neue SQLite-Tabellen.
    """
    
    @staticmethod
    def elementwise_sheet_vs_sheet(v_list1, sheet_info1: dict, v_list2, sheet_info2: dict, mapping=None) -> dict:
        start = time.process_time()
        
        conn1 = v_list1.conn
        cursor1 = conn1.cursor()
        conn2 = v_list2.conn
        cursor2 = conn2.cursor()
        
        table1 = sheet_info1["table"]
        table2 = sheet_info2["table"]
        
        cols1 = sheet_info1["num_cols"]
        cols2 = sheet_info2["num_cols"]
        max_cols = max(cols1, cols2)
        
        from collections import Counter
        
        counter1 = Counter()
        if cols1 > 0:
            col_names1 = ",".join([f'"Col_{i}"' for i in range(cols1)])
            cursor1.execute(f"SELECT {col_names1} FROM {table1}")
            for row in cursor1:
                for val in row:
                    if val is not None and val != "":
                        counter1[str(val)] += 1
                        
        counter2 = Counter()
        if cols2 > 0:
            col_names2 = ",".join([f'"Col_{i}"' for i in range(cols2)])
            cursor2.execute(f"SELECT {col_names2} FROM {table2}")
            for row in cursor2:
                for val in row:
                    if val is not None and val != "":
                        counter2[str(val)] += 1
                        
        status_dict = {}
        all_keys = set(counter1.keys()).union(set(counter2.keys()))
        
        for k in all_keys:
            c1 = counter1.get(k, 0)
            c2 = counter2.get(k, 0)
            
            if c1 > 0 and c2 == 0:
                status_dict[k] = 'only1'
            elif c2 > 0 and c1 == 0:
                status_dict[k] = 'only2'
            elif c1 == c2:
                status_dict[k] = 'sameAmount'
            else:
                status_dict[k] = 'diffAmount'
                
        end = time.process_time()
        
        return {
            "cross_check": True,
            "status_dict": status_dict,
            "time_taken": end - start
        }

    @staticmethod
    def cleanup(v_list1, table_names: typing.List[str]):
        cursor = v_list1.conn.cursor()
        for t in table_names:
            cursor.execute(f"DROP TABLE IF EXISTS {t}")
        v_list1.conn.commit()
