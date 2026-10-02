import tkinter as tk
from tkinter import ttk, simpledialog
import re
from mapping_models import SheetMapping
from ui_components import ZoomManager

class ComparisonLogicView(tk.Frame):
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, bg="#ffffff", *args, **kwargs)
        
        self.sheet_mappings: list[SheetMapping] = []
        self._hovered_item = None
        self.font_size = 11
        
        self.on_cols_changed = None
        self.on_sheet_pair_selected = None
        self._selected_item = None
        
        self._setup_ui()
        self.zoom_manager = ZoomManager(self, zoom_id="comparison_logic")
        
    def _setup_ui(self):
        # Top label
        self.lbl_title = tk.Label(self, text="Vergleichslogik definieren", font=("Segoe UI", 12, "bold"), bg="#ffffff", fg="#5f6368")
        self.lbl_title.pack(anchor="w", padx=10, pady=(10, 5))
        
        # Main Container
        frame_body = tk.Frame(self, bg="#ffffff")
        frame_body.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=10, pady=(0, 5))
        
        # Style
        style = ttk.Style()
        style.configure("Comparison.Treeview", rowheight=32, font=("Segoe UI", 11), borderwidth=0, background="#ffffff", fieldbackground="#ffffff")
        style.configure("Comparison.Treeview.Heading", font=("Segoe UI", 11, "bold"), foreground="#5f6368", background="#ffffff")
        style.layout("Comparison.Treeview", [('Comparison.Treeview.treearea', {'sticky': 'nswe'})])
        
        self.tree = ttk.Treeview(frame_body, columns=("equiv", "greater", "less", "tol", "tol_val", "dummy"), show="tree headings", style="Comparison.Treeview")
        
        # Scrollbars
        self.scrollbar = ttk.Scrollbar(frame_body, orient="vertical", command=self.tree.yview)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.xscrollbar = ttk.Scrollbar(frame_body, orient="horizontal", command=self.tree.xview)
        self.xscrollbar.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.tree.configure(yscrollcommand=self.scrollbar.set, xscrollcommand=self.xscrollbar.set)
        
        # Columns config
        self.tree.heading("#0", text="Sheet-Paar", anchor="w")
        self.tree.column("#0", width=320, minwidth=100, anchor="w", stretch=tk.NO)
        
        headers = [("equiv", "Äquivalent", 110), ("greater", "Größer", 110), 
                   ("less", "Kleiner", 110), ("tol", "Toleranz", 110), ("tol_val", "Toleranzwert", 140)]
                   
        for col_id, title, w in headers:
            self.tree.heading(col_id, text=title, anchor="center")
            self.tree.column(col_id, width=w, minwidth=80, anchor="center", stretch=tk.NO)
            
        self.tree.heading("dummy", text="")
        self.tree.column("dummy", width=0, minwidth=0, stretch=tk.YES)
            
        # Tags setup
        self._setup_tags()
        
        self.tree.bind("<ButtonRelease-1>", self._on_tree_click)
        self.tree.bind("<Motion>", self._on_mouse_motion)
        self.tree.bind("<Leave>", self._on_mouse_leave)
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)

    def _setup_tags(self):
        self.tree.tag_configure("header_row", font=("Segoe UI", 11, "bold"), foreground="#333333", background="#dce3e9")
        self.tree.tag_configure("select_all", font=("Segoe UI", 11), foreground="#333333", background="#ffffff")
        self.tree.tag_configure("empty_row", background="#f4f5f7")
        
        self.tree.tag_configure("mapping_even", font=("Segoe UI", 11, "bold"), foreground="#333333", background="#ffffff")
        self.tree.tag_configure("mapping_odd", font=("Segoe UI", 11, "bold"), foreground="#333333", background="#f4f5f7")
        self.tree.tag_configure("key_even", font=("Segoe UI", 11, "bold"), foreground="#888888", background="#ffffff")
        self.tree.tag_configure("key_odd", font=("Segoe UI", 11, "bold"), foreground="#888888", background="#f4f5f7")
        
        self.tree.tag_configure("hover_mapping", font=("Segoe UI", 11, "bold"), foreground="#333333", background="#e5f3ff")
        self.tree.tag_configure("hover_key", font=("Segoe UI", 11, "bold"), foreground="#888888", background="#e5f3ff")
        self.tree.tag_configure("hover_select_all", font=("Segoe UI", 11), foreground="#333333", background="#e5f3ff")

    def _update_tags_fs(self, fs):
        for tag in ["header_row", "select_all", "mapping_even", "mapping_odd", "key_even", "key_odd", "hover_mapping", "hover_key", "hover_select_all"]:
            is_bold = tag not in ["select_all", "hover_select_all", "empty_row"]
            weight = "bold" if is_bold else "normal"
            slant = "roman"
            self.tree.tag_configure(tag, font=("Segoe UI", fs, weight, slant))
            
        ratio = fs / 11.0
        self.tree.column("#0", width=int(320 * ratio))
        self.tree.column("equiv", width=int(110 * ratio))
        self.tree.column("greater", width=int(110 * ratio))
        self.tree.column("less", width=int(110 * ratio))
        self.tree.column("tol", width=int(110 * ratio))
        self.tree.column("tol_val", width=int(140 * ratio))
        
        style = ttk.Style()
        style.configure("Comparison.Treeview", rowheight=int(32 * ratio))
        style.configure("Comparison.Treeview.Heading", font=("Segoe UI", fs, "bold"))
        self.lbl_title.config(font=("Segoe UI", int(12 * ratio), "bold"))

    def on_external_zoom(self, delta):
        if (self.font_size <= 6 and delta < 0) or (self.font_size >= 30 and delta > 0): return
        self.font_size += delta
        self._update_tags_fs(self.font_size)

    def set_theme(self, theme):
        is_dark = (theme == "dark")
        bg_main = "#1e1e1e" if is_dark else "#ffffff"
        bg_alt = "#252525" if is_dark else "#f4f5f7"
        bg_hover = "#3a3a3a" if is_dark else "#e5f3ff"
        fg_text = "#e0e0e0" if is_dark else "#333333"
        fg_inactive = "#a0a0a0" if is_dark else "#888888"
        bg_header = "#3a3a3a" if is_dark else "#dce3e9"
        fg_active = "#4daafc" if is_dark else "#0078D7"
        heading_bg = "#2d2d2d" if is_dark else "#ffffff"

        self.config(bg=bg_main)
        self.lbl_title.config(bg=bg_main, fg=fg_text)
        self.winfo_children()[1].config(bg=bg_main) # frame_body

        style = ttk.Style()
        style.configure("Comparison.Treeview", background=bg_main, fieldbackground=bg_main, foreground=fg_text)
        style.configure("Comparison.Treeview.Heading", background=heading_bg, foreground=fg_text)
        
        self.tree.tag_configure("header_row", foreground=fg_text, background=bg_header)
        self.tree.tag_configure("select_all", foreground=fg_text, background=bg_main)
        self.tree.tag_configure("empty_row", background=bg_alt)
        
        self.tree.tag_configure("mapping_even", foreground=fg_text, background=bg_main)
        self.tree.tag_configure("mapping_odd", foreground=fg_text, background=bg_alt)
        self.tree.tag_configure("key_even", foreground=fg_inactive, background=bg_main)
        self.tree.tag_configure("key_odd", foreground=fg_inactive, background=bg_alt)
        
        self.tree.tag_configure("hover_mapping", foreground=fg_text, background=bg_hover)
        self.tree.tag_configure("hover_key", foreground=fg_inactive, background=bg_hover)
        self.tree.tag_configure("hover_select_all", foreground=fg_text, background=bg_hover)

    def load_mappings(self, mappings: list[SheetMapping]):
        self.sheet_mappings = mappings
        self._populate_tree()

    def _populate_tree(self):
        # We need to preserve open/close states
        open_states = {}
        if hasattr(self, 'tree'):
            for item in self.tree.get_children(""):
                open_states[item] = self.tree.item(item, "open")
                
        self.tree.delete(*self.tree.get_children())
        
        RADIO_ON = "⬤"
        RADIO_OFF = "○"
        
        for s_idx, s_map in enumerate(self.sheet_mappings):
            if not s_map.column_mappings: continue
            
            sheet_iid = f"sheet_{s_idx}"
            sheet_name1 = s_map.sheet1_name or "?"
            sheet_name2 = s_map.sheet2_name or "?"
            
            is_open = open_states.get(sheet_iid, True)
            
            # Row 1: Sheet names
            self.tree.insert("", "end", iid=sheet_iid, text=f"[{sheet_name1}] \u2194 [{sheet_name2}]", 
                             values=("", "", "", "", ""), tags=("header_row",), open=is_open)
                             
            # Determine logic for "Select All"
            all_equiv = True
            all_greater = True
            all_less = True
            all_tol = True
            has_editable_rows = False
            
            for c_map in s_map.column_mappings:
                is_key1 = False
                is_key2 = False
                if s_map.row_matching_mode == "key_based":
                    for k in s_map.key_mappings:
                        if c_map.col1_idx in k.col1_indices: is_key1 = True
                        if c_map.col2_idx in k.col2_indices: is_key2 = True
                
                is_key = is_key1 or is_key2
                if not is_key:
                    has_editable_rows = True
                    if not c_map.rule.check_equivalent: all_equiv = False
                    if not c_map.rule.check_greater: all_greater = False
                    if not c_map.rule.check_less: all_less = False
                    if not c_map.rule.check_tolerance: all_tol = False
            
            if not has_editable_rows:
                all_equiv = all_greater = all_less = all_tol = False

            # Row 2: Select All
            sa_equiv = RADIO_ON if all_equiv and has_editable_rows else RADIO_OFF
            sa_greater = RADIO_ON if all_greater and has_editable_rows else RADIO_OFF
            sa_less = RADIO_ON if all_less and has_editable_rows else RADIO_OFF
            sa_tol = RADIO_ON if all_tol and has_editable_rows else RADIO_OFF
            
            sa_iid = f"sheet_{s_idx}_selectall"
            self.tree.insert(sheet_iid, "end", iid=sa_iid, text="", 
                             values=(sa_equiv, sa_greater, sa_less, sa_tol, ""), tags=("select_all",))
                             
            # Row 3: Empty row
            empty_iid = f"sheet_{s_idx}_empty"
            self.tree.insert(sheet_iid, "end", iid=empty_iid, text="", values=("", "", "", "", ""), tags=("empty_row",))
            
            # Rows 4+: Mapped columns
            for r_idx, c_map in enumerate(s_map.column_mappings):
                is_key1 = False
                is_key2 = False
                if s_map.row_matching_mode == "key_based":
                    for k in s_map.key_mappings:
                        if c_map.col1_idx in k.col1_indices: is_key1 = True
                        if c_map.col2_idx in k.col2_indices: is_key2 = True
                        
                is_key = is_key1 or is_key2
                if is_key:
                    c_map.rule.check_equivalent = True
                    c_map.rule.check_greater = False
                    c_map.rule.check_less = False
                    c_map.rule.check_tolerance = False
                    
                marker1 = "🔑 " if is_key1 else ""
                marker2 = "🔑 " if is_key2 else ""
                col1_clean = re.sub(r'^[A-Z]+\s+', '', c_map.col1_name)
                col2_clean = re.sub(r'^[A-Z]+\s+', '', c_map.col2_name)
                col_text = f"    {marker1}{col1_clean} \u279d {marker2}{col2_clean}"
                
                v_equiv = RADIO_ON if c_map.rule.check_equivalent else RADIO_OFF
                v_greater = RADIO_ON if c_map.rule.check_greater else RADIO_OFF
                v_less = RADIO_ON if c_map.rule.check_less else RADIO_OFF
                v_tol = RADIO_ON if c_map.rule.check_tolerance else RADIO_OFF
                v_tol_val = str(c_map.rule.tolerance_value) if c_map.rule.check_tolerance else ""
                
                if is_key:
                    v_greater = v_less = v_tol = ""
                    
                row_iid = f"col_{s_idx}_{r_idx}"
                is_even = (r_idx % 2 == 0)
                if is_key:
                    tag = "key_even" if is_even else "key_odd"
                else:
                    tag = "mapping_even" if is_even else "mapping_odd"
                    
                self.tree.insert(sheet_iid, "end", iid=row_iid, text=col_text,
                                 values=(v_equiv, v_greater, v_less, v_tol, v_tol_val), tags=(tag,))

    def _get_base_tag(self, iid):
        if iid.endswith("_selectall"):
            return "select_all"
        elif iid.endswith("_empty"):
            return "empty_row"
        elif iid.startswith("sheet_"):
            return "header_row"
        elif iid.startswith("col_"):
            parts = iid.split("_")
            s_idx = int(parts[1])
            r_idx = int(parts[2])
            s_map = self.sheet_mappings[s_idx]
            c_map = s_map.column_mappings[r_idx]
            
            is_key = False
            if s_map.row_matching_mode == "key_based":
                for k in s_map.key_mappings:
                    if c_map.col1_idx in k.col1_indices or c_map.col2_idx in k.col2_indices:
                        is_key = True
                        break
                        
            is_even = (r_idx % 2 == 0)
            if is_key:
                return "key_even" if is_even else "key_odd"
            else:
                return "mapping_even" if is_even else "mapping_odd"
        return ""

    def _on_mouse_motion(self, event):
        item = self.tree.identify_row(event.y)
        
        # Reset previous hover
        if self._hovered_item and self._hovered_item != item:
            if self.tree.exists(self._hovered_item):
                base_tag = self._get_base_tag(self._hovered_item)
                if base_tag:
                    self.tree.item(self._hovered_item, tags=(base_tag,))
                    
        # Set new hover
        if item and item != self._hovered_item:
            base_tag = self._get_base_tag(item)
            if base_tag in ["mapping_even", "mapping_odd"]:
                self.tree.item(item, tags=("hover_mapping",))
            elif base_tag in ["key_even", "key_odd"]:
                self.tree.item(item, tags=("hover_key",))
            elif base_tag == "select_all":
                self.tree.item(item, tags=("hover_select_all",))
                
        self._hovered_item = item
        
        # Tooltip logic
        col_id = self.tree.identify_column(event.x)
        if item and col_id == "#0":
            text = self.tree.item(item, "text")
            if text:
                import tkinter.font as tkfont
                current_tag = self._get_base_tag(item)
                is_bold = current_tag not in ["select_all", "hover_select_all", "empty_row"]
                weight = "bold" if is_bold else "normal"
                
                font = tkfont.Font(family="Segoe UI", size=self.font_size, weight=weight)
                text_width = font.measure(text) + 45
                col_width = self.tree.column("#0", "width")
                
                if text_width > col_width:
                    if not hasattr(self, "_tooltip"):
                        from property_grid import GridToolTip
                        self._tooltip = GridToolTip(self.tree)
                    self._tooltip.show(text, event.x_root, event.y_root)
                else:
                    if hasattr(self, "_tooltip"): self._tooltip.hide()
            else:
                if hasattr(self, "_tooltip"): self._tooltip.hide()
        else:
            if hasattr(self, "_tooltip"): self._tooltip.hide()

    def _on_mouse_leave(self, event):
        if hasattr(self, "_tooltip"): self._tooltip.hide()
        if self._hovered_item and self.tree.exists(self._hovered_item):
            base_tag = self._get_base_tag(self._hovered_item)
            if base_tag:
                self.tree.item(self._hovered_item, tags=(base_tag,))
        self._hovered_item = None

    def _on_tree_select(self, event):
        selected = self.tree.selection()
        if not selected: return
        item_id = selected[0]
        
        parts = item_id.split("_")
        if len(parts) >= 2:
            try:
                s_idx = int(parts[1])
                if s_idx < len(self.sheet_mappings):
                    s_map = self.sheet_mappings[s_idx]
                    if self.on_sheet_pair_selected:
                        self.on_sheet_pair_selected(s_map.sheet1_name, s_map.sheet2_name, True)
            except ValueError:
                pass
                
        if self.on_cols_changed:
            self.after(50, lambda: self.on_cols_changed(0))

    def _on_tree_click(self, event):
        item_id = self.tree.identify_row(event.y)
        col_id = self.tree.identify_column(event.x)
        if not item_id or not col_id: return
        
        if col_id == "#0" and item_id.startswith("col_"):
            self._selected_item = item_id
            if self.on_cols_changed:
                self.on_cols_changed(0)
            return

        region = self.tree.identify_region(event.x, event.y)
        if region != "cell": return
        
        try:
            col_idx = int(col_id.replace("#", ""))
        except ValueError:
            return
            
        # We only care about columns 1, 2, 3, 4 (checkboxes) and 5 (tolerance value)
        if col_idx < 1 or col_idx > 5: return
        
        if item_id.endswith("_selectall"):
            if col_idx > 4: return # No select all for tolerance value
            parts = item_id.split("_")
            s_idx = int(parts[1])
            s_map = self.sheet_mappings[s_idx]
            
            # Determine current state for this column to toggle it
            # We toggle to True, unless ALL are currently True, then we toggle to False
            all_true = True
            has_rows = False
            for c_map in s_map.column_mappings:
                is_key = False
                if s_map.row_matching_mode == "key_based":
                    for k in s_map.key_mappings:
                        if c_map.col1_idx in k.col1_indices or c_map.col2_idx in k.col2_indices:
                            is_key = True
                            break
                if not is_key:
                    has_rows = True
                    if col_idx == 1 and not c_map.rule.check_equivalent: all_true = False
                    if col_idx == 2 and not c_map.rule.check_greater: all_true = False
                    if col_idx == 3 and not c_map.rule.check_less: all_true = False
                    if col_idx == 4 and not c_map.rule.check_tolerance: all_true = False
                    
            if not has_rows: return
            new_state = not all_true
            
            # Apply new state
            for c_map in s_map.column_mappings:
                is_key = False
                if s_map.row_matching_mode == "key_based":
                    for k in s_map.key_mappings:
                        if c_map.col1_idx in k.col1_indices or c_map.col2_idx in k.col2_indices:
                            is_key = True
                            break
                if not is_key:
                    if col_idx == 1:
                        c_map.rule.check_equivalent = new_state
                        if new_state: c_map.rule.check_tolerance = False
                    elif col_idx == 2:
                        c_map.rule.check_greater = new_state
                        if new_state: 
                            c_map.rule.check_less = False
                            c_map.rule.check_tolerance = False
                    elif col_idx == 3:
                        c_map.rule.check_less = new_state
                        if new_state: 
                            c_map.rule.check_greater = False
                            c_map.rule.check_tolerance = False
                    elif col_idx == 4:
                        c_map.rule.check_tolerance = new_state
                        if new_state:
                            c_map.rule.check_equivalent = False
                            c_map.rule.check_greater = False
                            c_map.rule.check_less = False
                            
                    # Ensure at least one option is selected
                    if not (c_map.rule.check_equivalent or c_map.rule.check_greater or c_map.rule.check_less or c_map.rule.check_tolerance):
                        if col_idx == 1: c_map.rule.check_equivalent = True
                        elif col_idx == 2: c_map.rule.check_greater = True
                        elif col_idx == 3: c_map.rule.check_less = True
                        elif col_idx == 4: c_map.rule.check_tolerance = True
            
            self._populate_tree()
            
        elif item_id.startswith("col_"):
            parts = item_id.split("_")
            s_idx = int(parts[1])
            r_idx = int(parts[2])
            
            s_map = self.sheet_mappings[s_idx]
            c_map = s_map.column_mappings[r_idx]
            
            is_key = False
            if s_map.row_matching_mode == "key_based":
                for k in s_map.key_mappings:
                    if c_map.col1_idx in k.col1_indices or c_map.col2_idx in k.col2_indices:
                        is_key = True
                        break
            
            if is_key: return # Key columns cannot be modified
            
            rule = c_map.rule
            
            if col_idx <= 4:
                # Checkbox/Radio button hybrid logic for this row
                if col_idx == 1:
                    rule.check_equivalent = not rule.check_equivalent
                    if rule.check_equivalent: rule.check_tolerance = False
                elif col_idx == 2:
                    rule.check_greater = not rule.check_greater
                    if rule.check_greater: 
                        rule.check_less = False
                        rule.check_tolerance = False
                elif col_idx == 3:
                    rule.check_less = not rule.check_less
                    if rule.check_less: 
                        rule.check_greater = False
                        rule.check_tolerance = False
                elif col_idx == 4:
                    rule.check_tolerance = not rule.check_tolerance
                    if rule.check_tolerance:
                        rule.check_equivalent = False
                        rule.check_greater = False
                        rule.check_less = False
                        
                # Ensure at least one option is selected
                if not (rule.check_equivalent or rule.check_greater or rule.check_less or rule.check_tolerance):
                    if col_idx == 1: rule.check_equivalent = True
                    elif col_idx == 2: rule.check_greater = True
                    elif col_idx == 3: rule.check_less = True
                    elif col_idx == 4: rule.check_tolerance = True
                
                self._populate_tree()
                
            elif col_idx == 5:
                if rule.check_tolerance:
                    new_val = simpledialog.askfloat("Toleranzwert", "Bitte Toleranzwert eingeben:", 
                                                    initialvalue=rule.tolerance_value, parent=self)
                    if new_val is not None:
                        rule.tolerance_value = new_val
                        self._populate_tree()

    def get_current_manual_indices(self, side: int) -> list[int]:
        selected = self.tree.selection()
        if not selected: return []
        item_id = selected[0]
        if not item_id.startswith("col_"): return []
        
        parts = item_id.split("_")
        if len(parts) < 3: return []
        s_idx = int(parts[1])
        r_idx = int(parts[2])
        
        if s_idx < len(self.sheet_mappings):
            mapping = self.sheet_mappings[s_idx]
            if r_idx < len(mapping.column_mappings):
                c_map = mapping.column_mappings[r_idx]
                if side == 1:
                    return [c_map.col1_idx] if c_map.col1_idx >= 0 else []
                else:
                    return [c_map.col2_idx] if c_map.col2_idx >= 0 else []
        return []
