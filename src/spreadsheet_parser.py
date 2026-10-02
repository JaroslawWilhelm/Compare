import zipfile
import xml.etree.ElementTree as ET
import hashlib
import sqlite3
import re
import os
import datetime
from typing import Iterator, List, Dict

# ============================================================================
# ARCHITEKTUR & COMPLIANCE KONSTANTEN
# ============================================================================
MAX_XML_FILE_SIZE = 2 * 1024 * 1024 * 1024  # 2 GB hartes Limit gegen Zip-Bombs


class SecurityException(Exception):
    """Spezifische Exception für GxP-Sicherheitsverstöße beim Parsen."""
    pass


class ParserBase:
    """Basisklasse mit integrierten Compliance- und Security-Routinen."""
    
    def __init__(self, filepath: str):
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Datei nicht gefunden: {filepath}")
            
        self.filepath = filepath
        self.file_hash = self._calculate_sha256()
        self._check_zip_security()

    def _calculate_sha256(self) -> str:
        """Berechnet den SHA-256 Hash der Originaldatei (ALCOA+ Original)."""
        sha256 = hashlib.sha256()
        # rb = read binary (Read-Only)
        with open(self.filepath, 'rb') as f:
            file_data = f.read()
            sha256.update(file_data)
        return sha256.hexdigest()

    def _check_zip_security(self):
        """Prüft Header auf Zip-Bomben, ohne die Datei zu entpacken."""
        try:
            with zipfile.ZipFile(self.filepath, 'r') as zf:
                for zinfo in zf.infolist():
                    if zinfo.file_size > MAX_XML_FILE_SIZE:
                        raise SecurityException(
                            f"Sicherheitsrisiko: Datei {zinfo.filename} im Archiv "
                            f"übersteigt das Limit von {MAX_XML_FILE_SIZE} Bytes."
                        )
        except zipfile.BadZipFile:
            raise SecurityException("Die Datei ist kein gültiges oder beschädigtes ZIP/Office-Archiv.")
            
    def get_sheet_names(self) -> List[str]:
        raise NotImplementedError
        
    def iter_sheet_data(self, sheet_name: str) -> Iterator[List[str]]:
        raise NotImplementedError

    def get_encoding(self) -> str:
        """Liest das Encoding aus der ersten XML-Datei des Archivs aus."""
        try:
            with zipfile.ZipFile(self.filepath, 'r') as zf:
                # Suche nach einer bekannten XML-Datei (Excel oder ODS)
                target = None
                for candidate in ['[Content_Types].xml', 'content.xml', 'meta.xml', 'xl/workbook.xml']:
                    if candidate in zf.namelist():
                        target = candidate
                        break
                
                # Fallback auf irgendeine XML-Datei
                if not target:
                    for name in zf.namelist():
                        if name.lower().endswith('.xml'):
                            target = name
                            break
                            
                if target:
                    with zf.open(target) as f:
                        # Lese erste 100 Bytes
                        header = f.read(100).decode('ascii', errors='ignore')
                        # Suche nach encoding="xyz"
                        import re
                        match = re.search(r'encoding=[\'"]([^\'"]+)[\'"]', header, re.IGNORECASE)
                        if match:
                            return match.group(1).upper()
        except Exception:
            pass
        return "Not found" # Standard-Encoding für OpenXML

# ============================================================================
# XLSX PARSER (Excel / Office Open XML)
# ============================================================================
class SecureXlsxParser(ParserBase):
    
    def __init__(self, filepath: str):
        super().__init__(filepath)
        self.namespaces = {'ns': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
        self.has_uncalculated_formulas = False
        
        # Schnelle Python-Liste für Shared Strings (Zugriffszeit O(1) statt langsames SQL SELECT)
        self.shared_strings = []
        
        self.sheet_map = {}
        self._load_styles()
        self._load_shared_strings()

    def _load_styles(self):
        """Parst xl/styles.xml um Datumsformate zu erkennen."""
        self.style_is_date = {} 
        self.style_format = {} 
        
        target_path = None
        with zipfile.ZipFile(self.filepath, 'r') as zf:
            for name in zf.namelist():
                if name.lower() == 'xl/styles.xml':
                    target_path = name
                    break
            
            if not target_path: return
            
            with zf.open(target_path) as f:
                tree = ET.parse(f)
                root = tree.getroot()
                
                custom_num_fmts = {}
                num_fmts_node = root.find('ns:numFmts', self.namespaces)
                if num_fmts_node is not None:
                    for num_fmt in num_fmts_node.findall('ns:numFmt', self.namespaces):
                        fmt_id = int(num_fmt.attrib.get('numFmtId', 0))
                        fmt_code = num_fmt.attrib.get('formatCode', '').lower()
                        custom_num_fmts[fmt_id] = fmt_code
                        
                cell_xfs_node = root.find('ns:cellXfs', self.namespaces)
                if cell_xfs_node is not None:
                    for idx, xf in enumerate(cell_xfs_node.findall('ns:xf', self.namespaces)):
                        fmt_id = int(xf.attrib.get('numFmtId', 0))
                        
                        is_date = False
                        fmt_code = ""
                        
                        if 14 <= fmt_id <= 22 or 45 <= fmt_id <= 47:
                            is_date = True
                            # Format 14 and 22 are special in Excel: they are tied to the OS Locale.
                            built_ins = {
                                14: "locale_date", 15: "d-mmm-yy", 16: "d-mmm", 17: "mmm-yy",
                                18: "locale_time", 19: "locale_time", 20: "hh:mm", 21: "hh:mm:ss",
                                22: "locale_datetime", 45: "mm:ss", 46: "[h]:mm:ss", 47: "mm:ss.0"
                            }
                            fmt_code = built_ins.get(fmt_id, "yyyy-mm-dd hh:mm:ss")
                        elif fmt_id in custom_num_fmts:
                            code = custom_num_fmts[fmt_id]
                            if re.search(r'[dmyhs]', code) and not re.search(r'general', code):
                                is_date = True
                                fmt_code = code
                                
                        self.style_is_date[idx] = is_date
                        self.style_format[idx] = fmt_code

    def _translate_format(self, fmt_code: str) -> str:
        if not fmt_code:
            return ""
            
        if fmt_code == "locale_date": return "%x"
        if fmt_code == "locale_time": return "%X"
        if fmt_code == "locale_datetime": return "%x %H:%M:%S"
            
        fmt = fmt_code.lower()
        fmt = re.sub(r'\[.*?\]', '', fmt) # remove colors and locale
        fmt = fmt.replace('\\', '').replace('"', '')
        
        # Determine OS date separator to mimic Excel's locale behavior internationally
        try:
            import locale
            locale.setlocale(locale.LC_ALL, '')
            sys_date = datetime.datetime(2000, 12, 31).strftime('%x')
            if '.' in sys_date: sys_sep = '.'
            elif '-' in sys_date: sys_sep = '-'
            else: sys_sep = '/'
        except:
            sys_sep = '/'
            
        fmt = fmt.replace('/', sys_sep)
        
        # Support German localized Excel format tokens
        fmt = fmt.replace('jjjj', 'yyyy').replace('jj', 'yy')
        fmt = fmt.replace('ttttt', 'dddd').replace('tttt', 'dddd').replace('ttt', 'ddd').replace('tt', 'dd').replace('t', 'd')
        
        # Temporary tokens to prevent overlapping replacements (like 'd' -> '%d' -> '%%d')
        fmt = fmt.replace('yyyy', '{Y4}').replace('yy', '{Y2}')
        fmt = fmt.replace('dddd', '{D4}').replace('ddd', '{D3}')
        fmt = fmt.replace('dd', '{D2}').replace('d', '{D1}')
        fmt = fmt.replace('hh', '{H2}').replace('h', '{H1}')
        fmt = fmt.replace('ss', '{S2}').replace('s', '{S1}')
        
        # Minutes (m/mm) vs Months (m/mm/mmm/mmmm)
        # If 'm' follows an hour token or precedes a second token, it's a minute
        fmt = re.sub(r'(\{H[12]\}[^a-zA-Z0-9]*)mm', r'\g<1>{MIN2}', fmt)
        fmt = re.sub(r'(\{H[12]\}[^a-zA-Z0-9]*)m', r'\g<1>{MIN1}', fmt)
        fmt = re.sub(r'mm([^a-zA-Z0-9]*\{S[12]\})', r'{MIN2}\g<1>', fmt)
        fmt = re.sub(r'm([^a-zA-Z0-9]*\{S[12]\})', r'{MIN1}\g<1>', fmt)
        
        # Remaining m are months
        fmt = fmt.replace('mmmm', '{M4}').replace('mmm', '{M3}')
        fmt = fmt.replace('mm', '{M2}').replace('m', '{M1}')
        
        fmt = fmt.replace('am/pm', '{AMPM}')
        fmt = re.sub(r'\.0+', '.%f', fmt)
        fmt = re.sub(r'[_*].', '', fmt)
        
        mapping = {
            '{Y4}': '%Y', '{Y2}': '%y',
            '{D4}': '%A', '{D3}': '%a', '{D2}': '%d', '{D1}': '%d',
            '{H2}': '%H', '{H1}': '%H',
            '{MIN2}': '%M', '{MIN1}': '%M',
            '{S2}': '%S', '{S1}': '%S',
            '{M4}': '%B', '{M3}': '%b', '{M2}': '%m', '{M1}': '%m',
            '{AMPM}': '%p'
        }
        
        for k, v in mapping.items():
            fmt = fmt.replace(k, v)
            
        return fmt.strip()

    def _format_date(self, excel_float: float, fmt_code: str) -> str:
        try:
            base_date = datetime.datetime(1899, 12, 30)
            # Floating point rounding to nearest millisecond prevents the .999999 truncation error
            total_seconds = round(excel_float * 86400.0, 3)
            delta = datetime.timedelta(seconds=total_seconds)
            dt = base_date + delta
            
            py_fmt = self._translate_format(fmt_code)
            if py_fmt:
                res = dt.strftime(py_fmt)
                if '.%f' in py_fmt:
                    res = res[:-3] 
                return res
            
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except:
            return str(excel_float)

    def _load_shared_strings(self):
        """Parst sharedStrings.xml extrem performant als In-Memory Python-Liste."""
        target_path = None
        with zipfile.ZipFile(self.filepath, 'r') as zf:
            for name in zf.namelist():
                if name.lower() == 'xl/sharedstrings.xml':
                    target_path = name
                    break
                    
            if not target_path:
                return
                
            with zf.open(target_path) as f:
                context = ET.iterparse(f, events=('end',))
                
                for event, elem in context:
                    if elem.tag.endswith('}si'):
                        text_parts = []
                        for t in elem.iter():
                            if t.tag.endswith('}t') and t.text:
                                text_parts.append(t.text)
                        
                        self.shared_strings.append("".join(text_parts))
                        elem.clear()

    def _get_string(self, str_id: int) -> str:
        try:
            return self.shared_strings[str_id]
        except IndexError:
            return ""

    def _col_name_to_index(self, col_name: str) -> int:
        index = 0
        for char in col_name:
            index = index * 26 + (ord(char) - ord('A') + 1)
        return index - 1

    def get_sheet_names(self) -> List[str]:
        names = []
        with zipfile.ZipFile(self.filepath, 'r') as zf:
            with zf.open('xl/workbook.xml') as f:
                tree = ET.parse(f)
                root = tree.getroot()
                for sheet in root.findall('.//ns:sheet', self.namespaces):
                    name = sheet.attrib.get('name')
                    # Es gibt verschiedene Möglichkeiten wie Excel die sheetId speichert. Meist über r:id und rels,
                    # aber für Einfachheit nehmen wir den Namen aus den xml-Pfaden oder sheetId
                    sheet_id = sheet.attrib.get('sheetId')
                    
                    # WICHTIG: Die direkte Verknüpfung über sheetId ist fehleranfällig, wenn Blätter gelöscht wurden.
                    # Richtig wäre über _rels, aber der Einfachheit halber versuchen wir beides.
                    # Wir scannen einfach die Namelist
                    path = f"xl/worksheets/sheet{sheet_id}.xml"
                    self.sheet_map[name] = path
                    names.append(name)
                    
        # WICHTIG: Wenn der Pfad xl/worksheets/sheet{sheet_id}.xml nicht existiert,
        # fallback auf die alphabetische Sortierung der worksheets (robuster).
        try:
            with zipfile.ZipFile(self.filepath, 'r') as zf:
                for name, path in self.sheet_map.items():
                    if path not in zf.namelist():
                        # Fallback
                        break
                else:
                    return names
                    
                # Fallback: Extrahiere rels
                with zf.open('xl/_rels/workbook.xml.rels') as f:
                    rel_tree = ET.parse(f)
                    rel_root = rel_tree.getroot()
                    rels = {}
                    for rel in rel_root:
                        rels[rel.attrib.get('Id')] = rel.attrib.get('Target')
                
                with zf.open('xl/workbook.xml') as f:
                    tree = ET.parse(f)
                    root = tree.getroot()
                    for sheet in root.findall('.//ns:sheet', self.namespaces):
                        name = sheet.attrib.get('name')
                        r_id = sheet.attrib.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')
                        target = rels.get(r_id, "")
                        if target.startswith("worksheets/"):
                            self.sheet_map[name] = f"xl/{target}"
                        else:
                            self.sheet_map[name] = target
        except Exception:
            pass # Ignoriere, iter_sheet_data wird KeyError werfen wenn nicht gefunden

        return names

    def iter_sheet_data(self, sheet_name: str) -> Iterator[List[str]]:
        if not self.sheet_map:
            self.get_sheet_names()
            
        sheet_xml_path = self.sheet_map.get(sheet_name)
        if not sheet_xml_path:
            raise FileNotFoundError(f"Tabelle '{sheet_name}' intern nicht gefunden.")
            
        """Streamt Daten. Füllt fehlende leere Zeilen explizit auf."""
        with zipfile.ZipFile(self.filepath, 'r') as zf:
            if sheet_xml_path not in zf.namelist():
                raise FileNotFoundError(f"Tabelle {sheet_xml_path} nicht im Archiv.")
                
            with zf.open(sheet_xml_path) as f:
                context = ET.iterparse(f, events=('start', 'end'))
                _, root = next(context)
                
                last_row_idx = 0  # 1-basiert laut Excel, wir speichern als 0-basiert referenz
                
                for event, elem in context:
                    if event == 'end' and elem.tag.endswith('}row'):
                        row_data = []
                        
                        # Finde die echte Zeilennummer in Excel
                        r_attr = elem.attrib.get('r')
                        if r_attr:
                            current_row_idx = int(r_attr)
                        else:
                            current_row_idx = last_row_idx + 1
                            
                        # WICHTIG: Wenn Excel komplett leere Zeilen übersprungen hat, 
                        # füllen wir diese hier wieder auf, um Positionierung (GxP) zu wahren!
                        while last_row_idx < current_row_idx - 1:
                            yield []  # Leere Zeile auswerfen
                            last_row_idx += 1
                        
                        last_col_idx = -1
                        
                        for cell in elem:
                            if not cell.tag.endswith('}c'):
                                continue
                                
                            r_attr_cell = cell.attrib.get('r', '')
                            if r_attr_cell:
                                # Extrem schnelles Extrahieren der Spaltenbuchstaben ohne Regex
                                col_str = r_attr_cell.rstrip('0123456789')
                                current_col_idx = self._col_name_to_index(col_str)
                                
                                while last_col_idx < current_col_idx - 1:
                                    row_data.append("")
                                    last_col_idx += 1
                                last_col_idx = current_col_idx

                            val_node = cell.find('ns:v', self.namespaces)
                            val = val_node.text if val_node is not None else ""
                            
                            t_attr = cell.attrib.get('t', '')
                            s_attr = cell.attrib.get('s', '')
                            
                            if not val:
                                f_node = cell.find('ns:f', self.namespaces)
                                if f_node is not None and f_node.text:
                                    val = "=" + f_node.text
                                    self.has_uncalculated_formulas = True
                                elif t_attr == 'inlineStr':
                                    is_node = cell.find('ns:is', self.namespaces)
                                    if is_node is not None:
                                        text_parts = []
                                        for t in is_node.iter():
                                            if t.tag.endswith('}t') and t.text:
                                                text_parts.append(t.text)
                                        val = "".join(text_parts)
                            elif t_attr == 's' and val.isdigit():
                                val = self._get_string(int(val))
                            elif t_attr == 'b' and val in ('0', '1'):
                                val = "TRUE" if val == '1' else "FALSE"
                            elif t_attr == 'str':
                                pass
                            else:
                                if val and s_attr.isdigit():
                                    style_idx = int(s_attr)
                                    if getattr(self, 'style_is_date', {}).get(style_idx, False):
                                        try:
                                            f_val = float(val)
                                            fmt_code = getattr(self, 'style_format', {}).get(style_idx, "")
                                            val = self._format_date(f_val, fmt_code)
                                        except ValueError:
                                            pass
                                            
                            row_data.append(val)
                            
                        yield row_data
                        last_row_idx = current_row_idx
                        
                        elem.clear()
                        root.clear()

    def __del__(self):
        pass


# ============================================================================
# ODS PARSER (LibreOffice / OpenDocument)
# ============================================================================
class SecureOdsParser(ParserBase):
    
    def __init__(self, filepath: str):
        super().__init__(filepath)
        self.namespaces = {
            'table': 'urn:oasis:names:tc:opendocument:xmlns:table:1.0',
            'text': 'urn:oasis:names:tc:opendocument:xmlns:text:1.0',
            'office': 'urn:oasis:names:tc:opendocument:xmlns:office:1.0'
        }
        self.has_uncalculated_formulas = False

    def get_sheet_names(self) -> List[str]:
        names = []
        with zipfile.ZipFile(self.filepath, 'r') as zf:
            with zf.open('content.xml') as f:
                context = ET.iterparse(f, events=('start',))
                for event, elem in context:
                    if elem.tag.endswith('}table'):
                        name = elem.attrib.get(f"{{{self.namespaces['table']}}}name")
                        if name:
                            names.append(name)
                    elem.clear()
        return names

    def iter_sheet_data(self, target_sheet_name: str) -> Iterator[List[str]]:
        """Streamt ODS Daten und beachtet wiederholte leere Zeilen."""
        with zipfile.ZipFile(self.filepath, 'r') as zf:
            with zf.open('content.xml') as f:
                context = ET.iterparse(f, events=('start', 'end'))
                in_target_sheet = False
                
                for event, elem in context:
                    if elem.tag.endswith('}table'):
                        if event == 'start':
                            name = elem.attrib.get(f"{{{self.namespaces['table']}}}name")
                            if name == target_sheet_name:
                                in_target_sheet = True
                        elif event == 'end':
                            if in_target_sheet:
                                return
                            
                    if in_target_sheet and event == 'end' and elem.tag.endswith('}table-row'):
                        row_data = []
                        
                        for cell in elem.findall('.//table:table-cell', self.namespaces):
                            text_node = cell.find('.//text:p', self.namespaces)
                            val = text_node.text if text_node is not None and text_node.text is not None else ""
                            
                            if not val:
                                formula = cell.attrib.get(f"{{{self.namespaces['table']}}}formula")
                                if formula:
                                    self.has_uncalculated_formulas = True
                                    if formula.startswith('of:='):
                                        val = '=' + formula[4:]
                                    elif formula.startswith('of:'):
                                        val = '=' + formula[3:]
                                    else:
                                        val = '=' + formula
                            
                            repeat_attr = cell.attrib.get(f"{{{self.namespaces['table']}}}number-columns-repeated", "1")
                            repeat_count = int(repeat_attr)
                            
                            if not val and repeat_count > 100:
                                repeat_count = 1
                                
                            row_data.extend([val] * repeat_count)
                            
                        while row_data and row_data[-1] == "":
                            row_data.pop()
                            
                        # WICHTIG: ODS fasst auch LEERE ZEILEN zusammen.
                        repeat_rows_attr = elem.attrib.get(f"{{{self.namespaces['table']}}}number-rows-repeated", "1")
                        repeat_rows = int(repeat_rows_attr)
                        
                        # Sicherheits-Cutoff: LibreOffice hängt an das Ende der Datei oft 1 Million Leerzeilen an.
                        # Diese wollen wir nicht in die Datenbank speichern. Leere Zwischenzeilen hingegen schon.
                        if not any(row_data) and repeat_rows > 1000:
                            break # Dateiende-Padding erreicht, abbrechen
                            
                        # Gib die Zeile (auch wenn sie komplett leer ist) so oft aus wie definiert
                        for _ in range(repeat_rows):
                            yield list(row_data)
                            
                        elem.clear()


class SpreadsheetAnalyzer:
    @staticmethod
    def get_parser(filepath: str) -> ParserBase:
        ext = os.path.splitext(filepath)[1].lower()
        if ext == '.xlsx':
            return SecureXlsxParser(filepath)
        elif ext == '.ods':
            return SecureOdsParser(filepath)
        raise ValueError(f"Nicht unterstütztes Format: {ext}")
