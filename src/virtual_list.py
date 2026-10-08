import sqlite3
import csv
import os

from csv_analyzer import CSVAnalyzer
from spreadsheet_parser import SpreadsheetAnalyzer

# ==========================================
# SQLITE IN-MEMORY VIRTUAL DATA LAYER
# ==========================================
class SqliteVirtualRow:
    """
    Represents a single row of data fetched from the SQLite database.
    """
    def __init__(self, parent_list, row_data):
        self.parent = parent_list
        self.data = row_data 

    def __getitem__(self, col_index):
        if 0 <= col_index < len(self.data):
            return self.data[col_index]
        return ""

    def __len__(self):
        return len(self.data)


class MemoryVirtualList:
    """
    In-Memory SQLite implementation. 
    Combines RAM speed with SQLite query power and C-level memory efficiency.
    No GC overhead for millions of strings.
    """
    def __init__(self, file_path, db_path="", config=None):
        self.file_path = file_path
        self.config = config
        
        # KEY CHANGE: purely in memory!
        self.conn = sqlite3.connect(":memory:", check_same_thread=False)
        self.cursor = self.conn.cursor()
        
        self.num_rows = 0
        self.num_cols = 0
        self.header_row_idx = 1
        self.table_name = ""
        self.sheets_info = []
        self.active_sheet_name = "default"
        self.has_uncalculated_formulas = False
        
        self._cache = {} 
        self.block_size = 200
        
        self._notes = {}

        self._import_file()

    def _import_file(self):
        ext = os.path.splitext(self.file_path)[1].lower()
        if ext == '.csv':
            self._import_csv()
        elif ext in ['.xlsx', '.ods']:
            self._import_spreadsheet()
        else:
            raise ValueError(f"Nicht unterstütztes Format: {ext}")

    def _import_csv(self):
        self.table_name = "sheet_0"
        self.cursor.execute(f"DROP TABLE IF EXISTS {self.table_name}")
        
        if self.config and self.config.encoding != "Auto":
            self.encoding = self.config.encoding
            self.encoding_fallback_used = False
        else:
            enc_info = CSVAnalyzer.detect_encoding(self.file_path)
            self.encoding = enc_info['encoding']
            self.encoding_fallback_used = enc_info['fallback_used']
            if self.config:
                self.config.encoding = self.encoding
        
        struct = CSVAnalyzer.analyze_structure(self.file_path, self.encoding)
        
        if self.config and self.config.delimiter != "Auto":
            delim_map = {"Semikolon (;)": ";", "Komma (,)": ",", "Tabulator (\\t)": "\t", "Pipe (|)": "|"}
            delim = delim_map.get(self.config.delimiter, self.config.delimiter)
        else:
            delim = struct['delimiter']
            if self.config:
                inv_delim_map = {";": "Semikolon (;)", ",": "Komma (,)", "\t": "Tabulator (\\t)", "|": "Pipe (|)"}
                self.config.delimiter = inv_delim_map.get(delim, "Semikolon (;)")

        if self.config and self.config.quote_char is not None and len(self.config.quote_char) > 0:
            qc = self.config.quote_char
            quoting = csv.QUOTE_MINIMAL
        elif self.config and self.config.quote_char == "":
            qc = '"' # dummy
            quoting = csv.QUOTE_NONE
        else:
            qc = struct['quotechar']
            quoting = csv.QUOTE_MINIMAL
            if self.config:
                self.config.quote_char = qc

        self.num_cols = struct['max_cols']
        self.header_row_idx = struct['header_row_idx']
        
        import hashlib
        sha256 = hashlib.sha256()
        
        with open(self.file_path, 'r', encoding=self.encoding, errors='replace') as f:
            reader = csv.reader(f, delimiter=delim, quotechar=qc, quoting=quoting)
            
            col_defs = ", ".join([f'"Col_{i}" TEXT' for i in range(self.num_cols)])
            self.cursor.execute(f"CREATE TABLE {self.table_name} ({col_defs})")
            
            placeholders = ", ".join(["?" for _ in range(self.num_cols)])
            sql = f"INSERT INTO {self.table_name} VALUES ({placeholders})"
            
            batch = []
            hash_batch = []
            count = 0
            
            for row in reader:
                actual_len = len(row)
                if actual_len < self.num_cols:
                    row_data = row + [""] * (self.num_cols - actual_len)
                else:
                    row_data = row[:self.num_cols]
                    
                batch.append(row_data)
                count += 1
                
                hash_batch.append("\x1F".join(row_data) + "\x1E")
                
                if len(batch) >= 5000:
                    self.cursor.executemany(sql, batch)
                    batch = []
                    sha256.update("".join(hash_batch).encode('utf-8'))
                    hash_batch.clear()
                    
            if batch:
                self.cursor.executemany(sql, batch)
                sha256.update("".join(hash_batch).encode('utf-8'))
            
            self.num_rows = count
        self.conn.commit()
        
        self.sheets_info = [{
            "name": os.path.basename(self.file_path),
            "table": "sheet_0",
            "num_cols": self.num_cols,
            "num_rows": self.num_rows,
            "hash": sha256.hexdigest()
        }]
        self.set_active_sheet(0)

    def _import_spreadsheet(self):
        parser = SpreadsheetAnalyzer.get_parser(self.file_path)
        
        # Extrahieren der Excel Metadaten und Aktualisierung der Config, damit nicht "Auto" angezeigt wird.
        if self.config:
            if self.config.encoding == "Auto":
                self.config.encoding = parser.get_encoding()
            if self.config.delimiter == "Auto":
                self.config.delimiter = "-"
            if getattr(self.config, 'quote_char', None) == "Auto" or getattr(self.config, 'quote_char', None) == "":
                self.config.quote_char = "-"
                
        sheet_names = parser.get_sheet_names()
        
        for idx, sheet_name in enumerate(sheet_names):
            table_name = f"sheet_{idx}"
            self.cursor.execute(f"DROP TABLE IF EXISTS {table_name}")
            
            current_max_cols = 0
            self.cursor.execute(f"CREATE TABLE {table_name} (id INTEGER PRIMARY KEY)")
            
            iterator = parser.iter_sheet_data(sheet_name)
            batch = []
            count = 0
            
            for row in iterator:
                if len(row) > current_max_cols:
                    for i in range(current_max_cols, len(row)):
                        self.cursor.execute(f'ALTER TABLE {table_name} ADD COLUMN "Col_{i}" TEXT')
                    current_max_cols = len(row)
                    
                batch.append(row)
                count += 1
                
                if len(batch) >= 5000:
                    self._insert_batch(table_name, batch, current_max_cols)
                    batch = []
                    
            if batch:
                self._insert_batch(table_name, batch, current_max_cols)
                
            self.sheets_info.append({
                "name": sheet_name,
                "table": table_name,
                "num_cols": current_max_cols,
                "num_rows": count
            })
            
        self.conn.commit()
        
        self.has_uncalculated_formulas = getattr(parser, 'has_uncalculated_formulas', False)
        
        if self.sheets_info:
            self.set_active_sheet(0)

    def _insert_batch(self, table_name, batch, max_cols):
        if not batch or max_cols == 0:
            return
        
        padded_batch = [r + [""] * (max_cols - len(r)) for r in batch]
        cols_names = ", ".join([f'"Col_{i}"' for i in range(max_cols)])
        placeholders = ", ".join(["?" for _ in range(max_cols)])
        
        sql = f"INSERT INTO {table_name} ({cols_names}) VALUES ({placeholders})"
        self.cursor.executemany(sql, padded_batch)

    def set_active_sheet(self, sheet_idx_or_name):
        info = None
        if isinstance(sheet_idx_or_name, int):
            if 0 <= sheet_idx_or_name < len(self.sheets_info):
                info = self.sheets_info[sheet_idx_or_name]
        else:
            for s in self.sheets_info:
                if s["name"] == sheet_idx_or_name:
                    info = s
                    break
                    
        if info:
            self.active_sheet_name = info["name"]
            self.table_name = info["table"]
            self.num_rows = info["num_rows"]
            self.num_cols = info["num_cols"]
            self._cache.clear()

    def get_sheet_row(self, sheet_name, row_idx):
        info = next((s for s in self.sheets_info if s["name"] == sheet_name), None)
        if not info:
            return None
        
        table = info["table"]
        db_rowid = row_idx + 1
        self.cursor.execute(f"SELECT * FROM {table} WHERE ROWID = ?", (db_rowid,))
        r = self.cursor.fetchone()
        if r:
            row_data = r[-info["num_cols"]:] if info["num_cols"] > 0 else []
            return ["" if x is None else x for x in row_data]
        return None

    def get_sheet_hash(self, sheet_name):
        info = next((s for s in self.sheets_info if s["name"] == sheet_name), None)
        if not info:
            return "N/A"
            
        if "hash" in info:
            return info["hash"]
        
        table = info["table"]
        num_cols = info["num_cols"]
        
        import hashlib
        sha256 = hashlib.sha256()
        
        self.cursor.execute(f"SELECT ROWID, * FROM {table} ORDER BY ROWID")
        while True:
            rows = self.cursor.fetchmany(1000)
            if not rows:
                break
            for r in rows:
                data_cols = r[-num_cols:] if num_cols > 0 else []
                row_str = "\x1F".join(str(val) if val is not None else "" for val in data_cols)
                sha256.update((row_str + "\x1E").encode('utf-8'))
        
        info["hash"] = sha256.hexdigest()
        return info["hash"]

    def __len__(self):
        return self.num_rows

    def __getitem__(self, index):
        if index < 0 or index >= self.num_rows:
            raise IndexError("Audit Data Index out of range")
        
        db_rowid = index + 1
        
        if db_rowid not in self._cache:
            self._fill_cache(db_rowid)
            
        return SqliteVirtualRow(self, self._cache.get(db_rowid, [""] * self.num_cols))

    def _fill_cache(self, target_rowid):
        start = max(1, target_rowid - (self.block_size // 2))
        end = start + self.block_size
        
        self.cursor.execute(f"SELECT ROWID, * FROM {self.table_name} WHERE ROWID BETWEEN ? AND ?", (start, end))
        rows = self.cursor.fetchall()
        
        self._cache.clear()
        for r in rows:
            rowid = r[0]
            data_cols = r[-self.num_cols:] if self.num_cols > 0 else []
            self._cache[rowid] = data_cols

    def close(self):
        self.conn.close()
        self._notes = {}

    def add_audit_note(self, row_idx, col_idx, note_text, media_files=None, author="System"):
        key = (row_idx, col_idx)
        if key not in self._notes:
            self._notes[key] = []
        
        from datetime import datetime
        self._notes[key].append({
            "author": author,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "text": note_text,
            "media_files": media_files if media_files else []
        })
        
    def get_audit_notes(self):
        result = []
        for (r, c), notes in self._notes.items():
            for n in notes:
                n_copy = n.copy()
                n_copy['row_idx'] = r
                n_copy['col_idx'] = c
                result.append(n_copy)
        return result
        
    def has_notes(self):
        return len(self._notes) > 0
        
    def __iter__(self):
        for i in range(self.num_rows):
            yield self[i]
