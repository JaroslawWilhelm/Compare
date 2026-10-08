from dataclasses import dataclass, field
import datetime
import locale

def get_default_decimal_separator() -> str:
    try:
        locale.setlocale(locale.LC_ALL, '')
        dec = locale.localeconv().get('decimal_point', '.')
        return dec if dec else '.'
    except Exception:
        return '.'

def get_default_thousands_separator() -> str:
    try:
        locale.setlocale(locale.LC_ALL, '')
        th = locale.localeconv().get('thousands_sep', '')
        return th
    except Exception:
        return ''

@dataclass
class FileParsingConfig:
    # --- 1. Identifikation & Audit ---
    file_hash: str = "Berechne..."
    sync_with_other: bool = False
    apply_to_all_sheets: bool = False

    user_name: str = ""
    project_id: str = ""
    description: str = ""
    admin_mode: bool = False
    timestamp: str = field(
        default_factory=lambda: datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )

    # --- 2. Parsing (Dateiebene) ---
    file_type: str = "CSV"
    encoding: str = "utf-8"

    # CSV Spezifisch
    delimiter: str = ";"
    quote_char: str = ""

    # Excel Spezifisch
    # (Removed treat_formulas_as_values as it's not applicable for raw data exports)

    # --- 3. Struktur & Bereich (Metadata) ---
    sheet_has_header: dict = field(default_factory=dict)
    sheet_header_rows: dict = field(default_factory=dict)
    sheet_data_start_rows: dict = field(default_factory=dict)
    sheet_data_end_rows: dict = field(default_factory=dict)
    
    sheet_ignore_columns: dict = field(default_factory=dict)
    sheet_ignore_rows: dict = field(default_factory=dict)
    
    # --- 3.5. Gespeicherte Datentypen (User Overrides) ---
    sheet_column_types: dict = field(default_factory=dict)
    sheet_column_is_auto: dict = field(default_factory=dict)
    sheet_column_confidences: dict = field(default_factory=dict)
    sheet_column_date_formats: dict = field(default_factory=dict)

    # --- 4. Zahlen & Formate (Kritisch) ---
    decimal_separator: str = field(default_factory=get_default_decimal_separator)
    thousands_separator: str = field(default_factory=get_default_thousands_separator)
    date_format: str = "ISO 8601 Standard"
    custom_date_format: str = ""
    timezone: str = "UTC"

    # Rundung / Präzision
    rounding_decimal_places: int | None = None  # None = Aus, 0 = 0 Stellen, etc.
    rounding_method: str = "HALF_EVEN"  # "CEIL", "FLOOR", "HALF_EVEN"
    use_tolerance: bool = False  # Exakt vs Toleranz (für später)

    # --- 5. Normalisierung & Strings ---
    trim_whitespace: bool = False  # " A " -> "A"
    normalize_umlauts: bool = False  # "Müller" == "Mueller"
    case_insensitive: bool = False  # "Text" == "TEXT"

    # Äquivalenzen & NULL
    na_values: str = "NULL, n/a, N/A, -, ?, #N/A, NaN"  # Was ist "leer"?
    true_values: str = "True, true, TRUE"  # Was ist "Wahr"?
    false_values: str = "False, false, FALSE"  # Was ist "Falsch"?

    # --- 6. UI & Darstellung (Highlighting) ---
    # Wir speichern Farben als Hex-String oder Tupel. wx.Colour ist nicht direkt picklable,
    # daher nutzen wir hier Strings oder PropertyGrid kompatible Werte.
    color_true: tuple = (144, 238, 144)  # Grün (RGB)
    color_false: tuple = (255, 128, 128)  # Rot
    color_not_comp: tuple = (238, 130, 238)  # Violet
    color_count_diff: tuple = (255, 128, 0)  # Hellbraun/Orange

    # --- Konstanten ---
    ENCODINGS = ["utf-8", "cp1252", "latin-1", "ascii", "utf-16"]
    DELIMITERS = [";", ",", "\t", "|", "CUSTOM"]
    DELIMITER_LABELS = [
        "Semikolon (;)",
        "Komma (,)",
        "Tabulator (\\t)",
        "Pipe (|)",
        "Benutzerdefiniert",
    ]

    DECIMALS = [".", ","]
    DECIMAL_LABELS = ["Punkt (.)", "Komma (,)"]
    THOUSANDS = ["", ".", ",", " "]
    THOUSAND_LABELS = ["Kein Separator", "Punkt (.)", "Komma (,)", "Leerzeichen ( )"]
    DATE_FORMATS = [
        "ISO 8601 Standard",
        "Europäisch (DD.MM.YYYY HH:MM:SS)",
        "Amerikanisch (MM/DD/YYYY HH:MM:SS AM/PM)",
        "Benutzerdefiniert (Erweitert)..."
    ]

    def get_has_header(self, sheet_name: str) -> bool:
        return self.sheet_has_header.get(sheet_name, False)
        
    def set_has_header(self, sheet_name: str, value: bool):
        self.sheet_has_header[sheet_name] = value

    def get_header_row(self, sheet_name: str) -> int:
        return self.sheet_header_rows.get(sheet_name, 1)
        
    def set_header_row(self, sheet_name: str, value: int):
        self.sheet_header_rows[sheet_name] = value
        
    def get_data_start_row(self, sheet_name: str) -> int:
        default_start = self.get_header_row(sheet_name) + 1 if self.get_has_header(sheet_name) else 1
        return self.sheet_data_start_rows.get(sheet_name, default_start)
        
    def set_data_start_row(self, sheet_name: str, value: int):
        self.sheet_data_start_rows[sheet_name] = value

    def get_data_end_row(self, sheet_name: str) -> int:
        return self.sheet_data_end_rows.get(sheet_name, 0)
        
    def set_data_end_row(self, sheet_name: str, value: int):
        self.sheet_data_end_rows[sheet_name] = value

    def get_ignore_columns(self, sheet_name: str) -> str:
        return self.sheet_ignore_columns.get(sheet_name, "")
        
    def set_ignore_columns(self, sheet_name: str, value: str):
        self.sheet_ignore_columns[sheet_name] = value

    def get_ignore_rows(self, sheet_name: str) -> str:
        return self.sheet_ignore_rows.get(sheet_name, "")
        
    def set_ignore_rows(self, sheet_name: str, value: str):
        self.sheet_ignore_rows[sheet_name] = value

    def get_column_types(self, sheet_name: str) -> dict:
        return self.sheet_column_types.get(sheet_name, {})
        
    def set_column_types(self, sheet_name: str, value: dict):
        self.sheet_column_types[sheet_name] = value

    def get_column_is_auto(self, sheet_name: str) -> dict:
        return self.sheet_column_is_auto.get(sheet_name, {})
        
    def set_column_is_auto(self, sheet_name: str, value: dict):
        self.sheet_column_is_auto[sheet_name] = value

    def get_column_confidences(self, sheet_name: str) -> dict:
        return self.sheet_column_confidences.get(sheet_name, {})
        
    def set_column_confidences(self, sheet_name: str, value: dict):
        self.sheet_column_confidences[sheet_name] = value

    def get_column_date_formats(self, sheet_name: str) -> dict:
        return self.sheet_column_date_formats.get(sheet_name, {})
        
    def set_column_date_formats(self, sheet_name: str, value: dict):
        self.sheet_column_date_formats[sheet_name] = value
