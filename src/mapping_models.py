from dataclasses import dataclass, field
from typing import List, Tuple

@dataclass
class ComparisonRule:
    check_equivalent: bool = True
    check_greater: bool = False
    check_less: bool = False
    check_tolerance: bool = False
    tolerance_value: float = 0.0

@dataclass
class ColumnMapping:
    col1_name: str
    col2_name: str
    col1_idx: int = -1
    col2_idx: int = -1
    rule: ComparisonRule = field(default_factory=ComparisonRule)

@dataclass
class KeyMapping:
    col1_names: str
    col2_names: str
    col1_indices: List[int] = field(default_factory=list)
    col2_indices: List[int] = field(default_factory=list)

@dataclass
class SheetMapping:
    sheet1_name: str
    sheet2_name: str
    # 'positional', 'key_based', 'cross_check'
    row_matching_mode: str = "positional"

    # 'positional', 'manual', 'by_name', 'cross_check'
    column_matching_mode: str = "positional"
    
    column_mappings: List[ColumnMapping] = field(default_factory=list)
    
    # Store composite key mappings
    key_mappings: List[KeyMapping] = field(default_factory=list)

    # Zwischenspeicher für manuelle Zuweisungen
    cached_manual_mappings: List[ColumnMapping] = field(default_factory=list)
