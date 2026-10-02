import re
from file_parsing_config_t import FileParsingConfig

class ColumnTypeDetector:
    def __init__(self, config: FileParsingConfig):
        self.config = config
        
    def detect_column_types(self, virtual_list, sheet_name: str, max_rows: int = 500, bounds: dict = None):
        if not virtual_list or virtual_list.num_cols == 0:
            return {}, {}, {}, {}
            
        if bounds:
            start_row = bounds.get("data_start_row", 0)
            end_row = bounds.get("data_end_row", virtual_list.num_rows)
            ignored_rows = bounds.get("ignored_rows", set())
        else:
            start_row = self.config.get_data_start_row(sheet_name) - 1
            if start_row < 0:
                start_row = 0
                
            end_row = self.config.get_data_end_row(sheet_name)
            if end_row <= 0 or end_row > virtual_list.num_rows:
                end_row = virtual_list.num_rows
            ignored_rows = set()
            
        scan_end = min(start_row + max_rows, end_row)
        
        num_cols = virtual_list.num_cols
        
        # Track counts for each column
        # counts[col_idx] = {"total": 0, "empty": 0, "integer": 0, "decimal": 0, "boolean": 0, "date": 0}
        counts = {i: {"total": 0, "empty": 0, "integer": 0, "decimal": 0, "boolean": 0, "date": 0} for i in range(num_cols)}
        
        na_values = [v.strip().lower() for v in self.config.na_values.split(',')]
        true_values = [v.strip().lower() for v in self.config.true_values.split(',')]
        false_values = [v.strip().lower() for v in self.config.false_values.split(',')]
        
        # Numeric regex (lenient, matches any valid number string)
        num_pattern = re.compile(r'^-?(?:\d{1,3}(?:[.,\s]\d{3})*|\d+)(?:[.,]\d+)?$')
            
        # Matches typical patterns like 2026-05-25, 25.05.2026, 05/25/2026, 2026-05-25T14:30:00
        # Also matches pure time patterns like 14:30, 14:30:00, 14:30:00.000, 02:30 AM
        date_pattern = re.compile(r'^(?:\d{2,4}[-./]\d{1,2}[-./]\d{1,4}(?:[T\s]\d{1,2}:\d{2}(?::\d{2})?(?:\.\d+)?[Z\+\-\d:]*(?:\s*[aApP][mM])?)?|\d{1,2}:\d{2}(?::\d{2})?(?:\.\d+)?(?:[Z\+\-\d:]*)?(?:\s*[aApP][mM])?)$')
        
        for row_idx in range(start_row, scan_end):
            if row_idx in ignored_rows:
                continue
                
            try:
                row_data = virtual_list[row_idx]
            except IndexError:
                break
                
            for col_idx in range(num_cols):
                val = str(row_data[col_idx]).strip() if col_idx < len(row_data) else ""
                val_lower = val.lower()
                
                counts[col_idx]["total"] += 1
                
                if not val or val_lower in na_values:
                    counts[col_idx]["empty"] += 1
                    continue
                    
                # Check Boolean
                if val_lower in true_values or val_lower in false_values:
                    counts[col_idx]["boolean"] += 1
                    continue
                    
                # Check Date
                if date_pattern.match(val):
                    counts[col_idx]["date"] += 1
                    continue
                    
                # Check Numeric
                if num_pattern.match(val):
                    counts[col_idx]["decimal"] += 1
                    continue
                    
        types = {}
        ambiguous = {}
        confidences = {}
        date_formats = {}
        
        for col_idx, col_counts in counts.items():
            total_non_empty = col_counts["total"] - col_counts["empty"]
            
            if total_non_empty == 0:
                types[col_idx] = "Mix"
                ambiguous[col_idx] = True
                confidences[col_idx] = "0% (Leer)"
                continue
                
            p_numeric = ((col_counts["integer"] + col_counts["decimal"]) / total_non_empty) * 100
            p_date = (col_counts["date"] / total_non_empty) * 100
            p_bool = (col_counts["boolean"] / total_non_empty) * 100
            
            p_text = 100.0 - (p_numeric + p_date + p_bool)
            if p_text < 0: p_text = 0.0
            
            threshold = 95.0
            
            if p_numeric >= threshold:
                types[col_idx] = "Zahl"
                ambiguous[col_idx] = p_numeric < 100.0
                if ambiguous[col_idx]:
                    confidences[col_idx] = f"{round(p_numeric, 1)}% Zahl, {round(p_text, 1)}% Text"
                else:
                    confidences[col_idx] = "100%"
            elif p_date >= threshold:
                from date_builder_dialog import guess_date_format
                
                # Fetch a sample to guess the format
                sample_val = ""
                for r in range(start_row, min(start_row + 500, virtual_list.num_rows)):
                    try:
                        row_data = virtual_list[r]
                        if col_idx < len(row_data):
                            v_str = str(row_data[col_idx]).strip()
                            if v_str and v_str.lower() not in ('none', 'null', ''):
                                sample_val = v_str
                                break
                    except IndexError:
                        break
                        
                machine_fmt, display_fmt = guess_date_format(sample_val)
                
                if display_fmt:
                    types[col_idx] = f"Datum/Zeit [{display_fmt}]"
                    date_formats[col_idx] = machine_fmt
                else:
                    types[col_idx] = "Datum/Zeit"
                    
                ambiguous[col_idx] = p_date < 100.0
                if ambiguous[col_idx]:
                    confidences[col_idx] = f"{round(p_date, 1)}% Datum/Zeit, {round(p_text, 1)}% Text"
                else:
                    confidences[col_idx] = "100%"
            elif p_bool >= threshold:
                types[col_idx] = "Boolean"
                ambiguous[col_idx] = p_bool < 100.0
                if ambiguous[col_idx]:
                    confidences[col_idx] = f"{round(p_bool, 1)}% Bool, {round(p_text, 1)}% Text"
                else:
                    confidences[col_idx] = "100%"
            else:
                if p_numeric > 0 or p_date > 0 or p_bool > 0:
                    types[col_idx] = "Mix"
                    ambiguous[col_idx] = True
                    parts = []
                    if p_date > 0: parts.append(f"{round(p_date, 1)}% Datum/Zeit")
                    if p_numeric > 0: parts.append(f"{round(p_numeric, 1)}% Zahl")
                    if p_bool > 0: parts.append(f"{round(p_bool, 1)}% Bool")
                    if p_text > 0: parts.append(f"{round(p_text, 1)}% Text")
                    confidences[col_idx] = ", ".join(parts)
                else:
                    types[col_idx] = "Text"
                    ambiguous[col_idx] = False
                    confidences[col_idx] = "100%"
                    
        return types, ambiguous, confidences, date_formats
