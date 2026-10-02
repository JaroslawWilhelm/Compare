import csv
from collections import Counter

class CSVAnalyzer:
    """
    Robust pure-Python CSV analysis tool designed for strict GxP and industrial data.
    Automatically detects encoding, dialect (delimiter, quotechar), and structural
    metadata (header row, preamble/comments) without external libraries (like pandas).
    """

    @staticmethod
    def detect_encoding(filepath: str, sample_size: int = 100000) -> dict:
        """
        Attempts to read the file chunk using safe encodings.
        Returns a dict: {'encoding': str, 'fallback_used': bool}
        """
        try:
            with open(filepath, 'rb') as f:
                raw_bytes = f.read(sample_size)

            if raw_bytes.startswith(b'\xef\xbb\xbf'):
                return {'encoding': 'utf-8-sig', 'fallback_used': False}

            raw_bytes.decode('utf-8')
            return {'encoding': 'utf-8', 'fallback_used': False}

        except UnicodeDecodeError:
            # windows-1252 handles all 256 byte values gracefully.
            return {'encoding': 'windows-1252', 'fallback_used': True}
        except Exception:
            return {'encoding': 'utf-8', 'fallback_used': True}

    @staticmethod
    def analyze_structure(filepath: str, encoding: str, sample_lines: int = 1000):
        """
        Simulates "Pattern Scoring" to guess the true dialect and skip preamble.
        Returns:
            dict with:
                - delimiter: str
                - quotechar: str
                - num_cols: int
                - header_row_idx: int (0-based)
        """
        delimiters = [';', ',', '\t', '|']
        quotechars = ['"', "'"]
        
        best_score = -1
        best_dialect = {'delimiter': ';', 'quotechar': '"'}
        best_lengths_map = []
        best_mode_cols = 1
        best_max_cols = 1
        
        for delim in delimiters:
            for qc in quotechars:
                lengths = []
                # Performance optimized C-based read limit
                try:
                    with open(filepath, 'r', encoding=encoding, errors='replace') as f:
                        reader = csv.reader(f, delimiter=delim, quotechar=qc)
                        for i, row in enumerate(reader):
                            if i >= sample_lines:
                                break
                            lengths.append((i, len(row)))
                except Exception:
                    continue
                
                if not lengths:
                    continue
                
                # Analyze lengths across this sample
                # Discard empty rows or single-column rows (often comments) from being the main layout
                valid_lengths = [l for idx, l in lengths if l > 1]
                
                if not valid_lengths:
                    # Fallback if the ENTIRE file is literally 1 column
                    valid_lengths = [l for idx, l in lengths]
                    if not valid_lengths:
                        continue

                # Mathematical Mode calculation using Counter
                c_counts = Counter(valid_lengths)
                most_common_len, freq = c_counts.most_common(1)[0]
                
                # Score heuristic: Frequent column counts * length weight
                # Highlights dialects that successfully split lines into numerous chunks over 
                # a high number of rows.
                score = freq * (most_common_len ** 1.5)
                
                if score > best_score:
                    best_score = score
                    best_dialect['delimiter'] = delim
                    best_dialect['quotechar'] = qc
                    best_lengths_map = lengths
                    best_mode_cols = most_common_len
                    best_max_cols = max([l for _, l in lengths]) if lengths else 1
                    
        # Find the structural start (Header row)
        header_row_idx = 0
        if best_lengths_map:
            # The FIRST row that matches the recognized table width is considered the header.
            for idx, length in best_lengths_map:
                if length == best_mode_cols:
                    header_row_idx = idx
                    break
        
        return {
            'delimiter': best_dialect['delimiter'],
            'quotechar': best_dialect['quotechar'],
            'mode_cols': best_mode_cols,
            'max_cols': best_max_cols,
            'header_row_idx': header_row_idx,
        }
