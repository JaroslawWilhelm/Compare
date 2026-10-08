import sqlite3
import unicodedata
import typing
import warnings
import locale
import decimal
from datetime import datetime, timezone
try:
    import zoneinfo
except ImportError:
    pass

class DataPreparator:
    """
    Bereitet Rohdaten für den hochperformanten Vergleich vor.
    Implementiert das 'Shadow Table'-Muster (Schatten-Tabellen) zur Wahrung 
    der GxP-Konformität (Originaldaten bleiben unangetastet).
    """

    UMLAUT_MAPPING = {
        ord('Ä'): 'Ae', ord('ä'): 'ae',
        ord('Ö'): 'Oe', ord('ö'): 'oe',
        ord('Ü'): 'Ue', ord('ü'): 'ue',
        ord('ß'): 'ss'
    }

    DATE_FORMAT_MAP = {
        "ISO 8601 Standard": "%Y-%m-%d %H:%M:%S",
        "Europäisch (DD.MM.YYYY HH:MM:SS)": "%d.%m.%Y %H:%M:%S",
        "Amerikanisch (MM/DD/YYYY HH:MM:SS AM/PM)": "%m/%d/%Y %I:%M:%S %p",
        "ISO 8601": "%Y-%m-%d %H:%M:%S"
    }

    DATE_FALLBACKS = [
        "%Y-%m-%d %H:%M:%S", "%Y-%m-%d", 
        "%d.%m.%Y %H:%M:%S", "%d.%m.%Y",
        "%m/%d/%Y %H:%M:%S", "%m/%d/%Y",
        "%d.%m.%y %H:%M", "%d.%m.%y"
    ]

    def __init__(self, db_connection: sqlite3.Connection):
        self.con = db_connection

    @staticmethod
    def normalize_text(
        value: typing.Any, 
        ignore_case: bool = True, 
        trim_spaces: bool = True, 
        normalize_umlauts: bool = True
    ) -> str:
        """
        Normalisiert einen Textwert für den perfekten Vergleich.
        """
        if value is None:
            return ""
            
        text = str(value)
        
        if trim_spaces:
            text = text.strip()
            
        if normalize_umlauts:
            # 1. Deutsche Umlaute spezifisch übersetzen (Ä -> AE), 
            # da Standard-Unicode-Normalisierung oft Ä -> A macht.
            text = text.translate(DataPreparator.UMLAUT_MAPPING)
            
            # 2. Allgemeine Unicode-Normalisierung für alle anderen 
            # Akzente und Sonderzeichen (z.B. é -> e, ñ -> n)
            text = unicodedata.normalize('NFKD', text).encode('ASCII', 'ignore').decode('utf-8')
            
        if ignore_case:
            # casefold() ist aggressiver und korrekter als lower() 
            # für das caseless matching im Unicode-Standard.
            text = text.casefold()
            
        return text

    @staticmethod
    def normalize_custom_values(
        value: typing.Any, 
        true_values: typing.Set[str], 
        false_values: typing.Set[str], 
        none_values: typing.Set[str]
    ) -> str:
        """
        Übersetzt benutzerdefinierte Werte für True/False/None 
        in die literalen Strings "True", "False" und "" (Leerstelle), 
        damit der Nutzer diese in den Test-Tabellen sauber kontrollieren kann.
        """
        if value is None:
            val_str = ""
        else:
            val_str = str(value)
            
        # Wir nutzen intern casefold zum Vergleichen, um Schreibfehler abzufangen
        val_cf = val_str.casefold().strip()
        
        # 1. None-Prüfung -> Leerstelle / Leerstring
        if val_cf in none_values or val_str == "":
            return ""
            
        # 2. True-Prüfung -> "True"
        if val_cf in true_values:
            return "True"
            
        # 3. False-Prüfung -> "False"
        if val_cf in false_values:
            return "False"
            
        # Wenn kein Match gefunden wurde, geben wir den (als String konvertierten) Originalwert zurück
        return val_str

    @staticmethod
    def _parse_ignored_rows(s):
        indices = set()
        if not s: return indices
        for part in s.split(","):
            part = part.strip()
            if not part: continue
            if "-" in part:
                parts = part.split("-")
                if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                    indices.update(range(int(parts[0]) - 1, int(parts[1])))
            elif part.isdigit():
                indices.add(int(part) - 1)
        return indices

    @staticmethod
    def _parse_ignored_cols(s, headers):
        indices = set()
        if not s: return indices
        for part in s.split(","):
            part = part.strip()
            if not part: continue
            if headers and part in headers:
                indices.add(headers.index(part))
            elif part.isdigit():
                indices.add(int(part) - 1)
            else:
                part = part.upper()
                res = 0
                valid = True
                for char in part:
                    if 'A' <= char <= 'Z':
                        res = res * 26 + (ord(char) - ord('A') + 1)
                    else:
                        valid = False
                        break
                if valid and res > 0:
                    indices.add(res - 1)
        return indices

    @staticmethod
    def normalize_number(
        val_str: str, 
        decimal_sep: str, 
        thousands_sep: str, 
        rounding_places: int | None,
        rounding_method: str
    ) -> str:
        if not val_str:
            return ""
            
        clean_val = str(val_str)
        if thousands_sep:
            clean_val = clean_val.replace(thousands_sep, "")
        if decimal_sep and decimal_sep != ".":
            clean_val = clean_val.replace(decimal_sep, ".")
            
        try:
            d = decimal.Decimal(clean_val)
            
            if rounding_places is not None:
                if rounding_places == 0:
                    q = decimal.Decimal("1")
                else:
                    q = decimal.Decimal("1." + "0" * rounding_places)
                    
                if rounding_method == "CEIL":
                    rnd = decimal.ROUND_CEILING
                elif rounding_method == "FLOOR":
                    rnd = decimal.ROUND_FLOOR
                else:
                    rnd = decimal.ROUND_HALF_EVEN
                    
                d = d.quantize(q, rounding=rnd)
                
            return str(d)
        except Exception:
            return val_str

    @staticmethod
    def normalize_datetime(val_str: str, date_format: str, source_timezone: str) -> str:
        """
        Wandelt ein Datum basierend auf der Quell-Zeitzone sicher in UTC um 
        und gibt es als sortierbaren ISO 8601 String (YYYY-MM-DD HH:MM:SS) zurück.
        Dadurch können Zeiten konsistent und performant verglichen werden.
        """
        if not val_str:
            return ""
            
        fmt = DataPreparator.DATE_FORMAT_MAP.get(date_format, date_format)
        dt_naive = None
        
        def try_parse(f):
            nonlocal dt_naive
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", category=DeprecationWarning)
                    dt_naive = datetime.strptime(val_str.strip(), f)
                return True
            except ValueError:
                if "%p" in f or "%I" in f:
                    try:
                        old_loc = locale.setlocale(locale.LC_TIME)
                        try:
                            locale.setlocale(locale.LC_TIME, 'C')
                            with warnings.catch_warnings():
                                warnings.simplefilter("ignore", category=DeprecationWarning)
                                dt_naive = datetime.strptime(val_str.strip(), f)
                            return True
                        except ValueError:
                            pass
                        finally:
                            locale.setlocale(locale.LC_TIME, old_loc)
                    except Exception:
                        pass
            return False

        if fmt:
            try_parse(fmt)
            
        if dt_naive is None:
            try:
                dt_naive = datetime.fromisoformat(val_str.strip())
            except ValueError:
                for fb in DataPreparator.DATE_FALLBACKS:
                    if try_parse(fb):
                        break
                        
        if dt_naive is None:
            return val_str
            
        if dt_naive.tzinfo is not None:
            dt_aware = dt_naive
        else:
            try:
                src_tz = zoneinfo.ZoneInfo(source_timezone)
            except Exception:
                src_tz = timezone.utc
            dt_aware = dt_naive.replace(tzinfo=src_tz)
            
        try:
            dt_utc = dt_aware.astimezone(timezone.utc)
        except Exception:
            dt_utc = dt_aware
            
        return dt_utc.strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def prepare_sheet_for_test(v_list, sheet_idx: int, config, col_types: dict = None, allowed_cols: set = None, allowed_rows: set = None) -> dict:
        """
        Liest ein existierendes Sheet aus der MemoryVirtualList,
        wendet die Text- und Werte-Normalisierung an,
        und speichert das Ergebnis als neue 'prepared' Tabelle im SQLite.
        Gibt ein Dictionary zurück, das als neue SheetInfo an v_list.sheets_info angehängt werden kann.
        """
        if sheet_idx < 0 or sheet_idx >= len(v_list.sheets_info):
            return None
            
        source_sheet = v_list.sheets_info[sheet_idx]
        source_table = source_sheet["table"]
        sheet_name = source_sheet["name"]
        num_cols = source_sheet["num_cols"]
        
        # Nur echte Daten-Spalten abfragen (keine internen 'id' Schlüssel)
        cols_to_select = ", ".join([f'"Col_{i}"' for i in range(num_cols)])
        v_list.cursor.execute(f"SELECT {cols_to_select} FROM {source_table}")
        all_rows = v_list.cursor.fetchall()
        
        if not all_rows:
            return None
            
        # --- Struktur filtern (Zeilen & Spalten) ---
        has_header = config.get_has_header(sheet_name)
        header_row_idx = config.get_header_row(sheet_name) - 1
        data_start_idx = config.get_data_start_row(sheet_name) - 1
        data_end_idx = config.get_data_end_row(sheet_name) - 1
        if data_end_idx < 0:
            data_end_idx = len(all_rows) - 1
            
        ignore_rows_str = config.get_ignore_rows(sheet_name)
        ignore_cols_str = config.get_ignore_columns(sheet_name)
        
        ignored_rows = DataPreparator._parse_ignored_rows(ignore_rows_str)
        
        headers = []
        if has_header and 0 <= header_row_idx < len(all_rows):
            headers = [str(x) for x in all_rows[header_row_idx]]
            
        ignored_cols = DataPreparator._parse_ignored_cols(ignore_cols_str, headers)
        
        orig_col_map = []
        for c in range(len(all_rows[0] if all_rows else [])):
            if c in ignored_cols:
                continue
            if allowed_cols is not None and c not in allowed_cols:
                ignored_cols.add(c)
                continue
            orig_col_map.append(c)
        
        actual_num_cols = len(orig_col_map)
        
        if actual_num_cols == 0:
            return None
            
        # Neue Tabelle anlegen
        new_table = f"prepared_{source_table}"
        v_list.cursor.execute(f"DROP TABLE IF EXISTS {new_table}")
        
        col_defs_list = []
        for i in range(actual_num_cols):
            orig_c = orig_col_map[i]
            ctype = col_types.get(orig_c, "") if col_types else ""
            if ctype == "Zahl":
                col_defs_list.append(f'"Col_{i}" NUMERIC')
            elif ctype == "Boolean":
                col_defs_list.append(f'"Col_{i}" BOOLEAN')
            elif ctype and ctype.startswith("Datum/Zeit"):
                col_defs_list.append(f'"Col_{i}" DATETIME')
            else:
                col_defs_list.append(f'"Col_{i}" TEXT')
                
        col_defs = ", ".join(col_defs_list)
        if not col_defs:
            col_defs = '"Col_0" TEXT'
            
        v_list.cursor.execute(f"CREATE TABLE {new_table} ({col_defs})")
        
        # Einstellungen lesen & pre-calculating sets for speed
        ignore_case = config.case_insensitive
        normalize_umlauts = config.normalize_umlauts
        trim_spaces = config.trim_whitespace
        
        true_vals = {x.strip().casefold() for x in config.true_values.split(',')}
        false_vals = {x.strip().casefold() for x in config.false_values.split(',')}
        none_vals = {x.strip().casefold() for x in config.na_values.split(',')}
        
        dec_sep = config.decimal_separator
        th_sep = config.thousands_separator
        rnd_places = config.rounding_decimal_places
        rnd_method = config.rounding_method
        
        # Vorab die Spalten-Typen extrahieren und extrem schnelle Cache-Prozessoren bauen
        def make_processor(ctype, date_fmt):
            cache = {}
            is_numeric = (ctype == "Zahl")
            is_boolean = (ctype == "Boolean")
            is_date = (ctype and ctype.startswith("Datum/Zeit"))
            
            def norm_text(v_str):
                text = v_str
                if trim_spaces: text = text.strip()
                if normalize_umlauts:
                    text = text.translate(DataPreparator.UMLAUT_MAPPING)
                    text = unicodedata.normalize('NFKD', text).encode('ASCII', 'ignore').decode('utf-8')
                if ignore_case:
                    text = text.casefold()
                return text

            if is_boolean:
                def proc(val):
                    if val in cache: return cache[val]
                    if val is None: return ""
                    v_str = str(val)
                    v_cf = v_str.casefold().strip()
                    if v_cf in none_vals or v_str == "": res = ""
                    elif v_cf in true_vals: res = "True"
                    elif v_cf in false_vals: res = "False"
                    else: res = ""
                    cache[val] = res
                    return res
                return proc
            elif is_numeric:
                def proc(val):
                    if val in cache: return cache[val]
                    if val is None: return ""
                    v_str = str(val)
                    v_cf = v_str.casefold().strip()
                    if v_cf in none_vals or v_str == "": res = ""
                    elif v_cf in true_vals: res = "True"
                    elif v_cf in false_vals: res = "False"
                    else: 
                        res = DataPreparator.normalize_number(v_str, dec_sep, th_sep, rnd_places, rnd_method)
                        if res == v_str: res = norm_text(v_str)
                    cache[val] = res
                    return res
                return proc
            elif is_date:
                def proc(val):
                    if val in cache: return cache[val]
                    if val is None: return ""
                    v_str = str(val)
                    v_cf = v_str.casefold().strip()
                    if v_cf in none_vals or v_str == "": res = ""
                    elif v_cf in true_vals: res = "True"
                    elif v_cf in false_vals: res = "False"
                    else: 
                        res = DataPreparator.normalize_datetime(v_str, date_fmt, config.timezone)
                        if res == v_str: res = norm_text(v_str)
                    cache[val] = res
                    return res
                return proc
            else:
                def proc(val):
                    if val in cache: return cache[val]
                    if val is None: return ""
                    v_str = str(val)
                    v_cf = v_str.casefold().strip()
                    if v_cf in none_vals or v_str == "": res = ""
                    elif v_cf in true_vals: res = "True"
                    elif v_cf in false_vals: res = "False"
                    else: res = norm_text(v_str)
                    cache[val] = res
                    return res
                return proc

        col_processors = []
        date_formats = config.get_column_date_formats(sheet_name)
        for orig_c in orig_col_map:
            ctype = col_types.get(orig_c, "") if col_types else ""
            date_fmt = date_formats.get(orig_c, "") if ctype and ctype.startswith("Datum/Zeit") else ""
            col_processors.append((orig_c, make_processor(ctype, date_fmt)))
            
        batch = []
        insert_sql = f"INSERT INTO {new_table} VALUES ({', '.join(['?'] * actual_num_cols)})"
        
        orig_row_map = []
        rows_processed = 0
        
        for i, row in enumerate(all_rows):
            if i in ignored_rows:
                continue
                
            is_data = (data_start_idx <= i <= data_end_idx)
            if not is_data:
                continue
                
            if allowed_rows is not None and i not in allowed_rows:
                continue
                
            orig_row_map.append(i)
            rows_processed += 1
            new_row = []
            
            for orig_c, proc in col_processors:
                new_row.append(proc(row[orig_c]))
                
            batch.append(new_row)
            
            if len(batch) >= 1000:
                v_list.cursor.executemany(insert_sql, batch)
                batch.clear()
                
        if batch:
            v_list.cursor.executemany(insert_sql, batch)
            
        v_list.conn.commit()
        
        if rows_processed == 0:
            return None
            
        # Set default values for the prepared sheet explicitly so UI highlights correctly
        prepared_name = f"[PREPARED] {sheet_name}"
        config.set_has_header(prepared_name, False)
        config.set_header_row(prepared_name, None)
        config.set_data_start_row(prepared_name, 1)
            
        # Metadaten für das neue Sheet zurückgeben
        return {
            "name": prepared_name,
            "table": new_table,
            "num_cols": actual_num_cols,
            "num_rows": rows_processed,
            "header_row_idx": 1 if has_header else 0,
            "orig_row_map": orig_row_map,
            "orig_col_map": orig_col_map
        }

