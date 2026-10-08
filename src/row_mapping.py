import tkinter as tk
from tkinter import ttk
from mapping_models import SheetMapping, ColumnMapping
from grid_widget import ComplianceGrid
from ui_components import ZoomManager

class RowMappingView(tk.Frame):
    """
    Ansicht zum Zuordnen von Zeilen zwischen gemappten Arbeitsblättern.
    Beinhaltet links die Modus-Auswahl (Positionell, Schlüssel, Cross-Check) per Virtual-Grid
    und rechts eine Vorschau der definierten Schlüssel.
    """
    def __init__(self, parent, data_provider=None, *args, **kwargs):
        super().__init__(parent, bg="#ffffff", *args, **kwargs)
        
        self.data_provider = data_provider
        
        self.sheet_mappings: list[SheetMapping] = []
        self.active_mapping_idx = None
        self.selected_left_indices = []
        self.selected_right_indices = []
        self.on_sheet_pair_selected = None  # Callback(sheet1_name, sheet2_name)
        self.on_key_based_toggled = None    # Callback(is_key_based)
        self.on_keys_changed = None         # Callback(side: int)
        self.manual_mappings = []
        self.on_manual_toggled = None
        
        self._setup_ui()
        self.zoom_manager_left = ZoomManager(self.left_frame, zoom_id="row_mapping_panel")
        self.zoom_manager_right = ZoomManager(self.right_frame, zoom_id="row_mapping_grid")
        
    def clear_cache(self):
        self.active_mapping_idx = None
        self._editing_state = "none"
        self._pending_left = None
        self._pending_right = None
        self.selected_left_idx = -1
        self.selected_right_idx = -1
        self._current_grid_data = []
        if hasattr(self, 'grid_keys'):
            self.grid_keys.set_data([], ["Spalte Links", "Spalte Rechts"])
            self.grid_keys.redraw()

    def _setup_ui(self):
        # Haupt-PanedWindow für Links/Rechts-Aufteilung
        self.paned = tk.PanedWindow(self, orient=tk.HORIZONTAL, sashwidth=4, bd=0, bg="#dcdcdc")
        self.paned.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # ==========================================
        # LINKER BEREICH: Konfiguration
        # ==========================================
        self.left_frame = tk.Frame(self.paned, bg="#ffffff", width=10, height=10)
        self.left_frame.pack_propagate(False)
        self.left_frame.grid_propagate(False)
        self.paned.add(self.left_frame, stretch="always", minsize=200)
        

        # Einheitlicher Header Links
        header_left = tk.Frame(self.left_frame, bg="#ffffff", pady=5)
        header_left.pack(fill=tk.X)
        tk.Label(header_left, text="Zuordnungsmodus", font=("Segoe UI", 11, "bold"), fg="#5f6368", bg="#ffffff").pack(side=tk.LEFT, padx=5)

        # Treeview für Optionen
        style = ttk.Style()
        style.configure("RowMapping.Treeview", rowheight=32, font=("Segoe UI", 11), borderwidth=0, background="#ffffff", fieldbackground="#ffffff")
        style.layout("RowMapping.Treeview", [('RowMapping.Treeview.treearea', {'sticky': 'nswe'})]) # Remove borders

        tree_container = tk.Frame(self.left_frame, bg="#ffffff")
        tree_container.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=5, pady=(5, 0))

        self.tree_options = ttk.Treeview(tree_container, columns=("radio",), show="tree", style="RowMapping.Treeview")
        
        scrollbar = ttk.Scrollbar(tree_container, orient="vertical", command=self.tree_options.yview)
        self.tree_options.configure(yscrollcommand=scrollbar.set)
        
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree_options.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.tree_options.column("#0", width=180, anchor="w", stretch=tk.NO)
        self.tree_options.column("radio", width=50, anchor="w", stretch=tk.YES)
        
        # Tags for Categories
        self.tree_options.tag_configure("category_active", font=("Segoe UI", 11, "bold"))
        self.tree_options.tag_configure("category_inactive", foreground="#888888", font=("Segoe UI", 11, "bold"))
        # Tags for Options
        self.tree_options.tag_configure("option_active_even", foreground="#0078D7", font=("Segoe UI", 11, "bold"), background="#ffffff")
        self.tree_options.tag_configure("option_active_odd", foreground="#0078D7", font=("Segoe UI", 11, "bold"), background="#f4f5f7")
        self.tree_options.tag_configure("option_inactive_even", foreground="#333333", font=("Segoe UI", 11, "bold"), background="#ffffff")
        self.tree_options.tag_configure("option_inactive_odd", foreground="#333333", font=("Segoe UI", 11, "bold"), background="#f4f5f7")
        self.tree_options.tag_configure("option_disabled_even", foreground="#888888", font=("Segoe UI", 11, "bold"), background="#ffffff")
        self.tree_options.tag_configure("option_disabled_odd", foreground="#888888", font=("Segoe UI", 11, "bold"), background="#f4f5f7")
        
        # Hover Tags
        self.tree_options.tag_configure("hover_category", foreground="#333333", font=("Segoe UI", 11, "bold"), background="#e5f3ff")
        self.tree_options.tag_configure("hover_active_even", foreground="#0078D7", font=("Segoe UI", 11, "bold"), background="#e5f3ff")
        self.tree_options.tag_configure("hover_active_odd", foreground="#0078D7", font=("Segoe UI", 11, "bold"), background="#e5f3ff")
        self.tree_options.tag_configure("hover_inactive_even", foreground="#333333", font=("Segoe UI", 11, "bold"), background="#e5f3ff")
        self.tree_options.tag_configure("hover_inactive_odd", foreground="#333333", font=("Segoe UI", 11, "bold"), background="#e5f3ff")
        self.tree_options.tag_configure("hover_disabled_even", foreground="#888888", font=("Segoe UI", 11, "bold"), background="#e5f3ff")
        self.tree_options.tag_configure("hover_disabled_odd", foreground="#888888", font=("Segoe UI", 11, "bold"), background="#e5f3ff")

        def _update_tags_fs(fs):
            for tag in ["category_active", "category_inactive", "option_active_even", "option_active_odd", 
                        "option_inactive_even", "option_inactive_odd", "option_disabled_even", "option_disabled_odd",
                        "hover_category", "hover_active_even", "hover_active_odd", "hover_inactive_even",
                        "hover_inactive_odd", "hover_disabled_even", "hover_disabled_odd"]:
                self.tree_options.tag_configure(tag, font=("Segoe UI", fs, "bold"))
            
            # Skaliere auch die Spaltenbreiten, damit der Text nicht überlappt
            ratio = fs / 11.0
            self.tree_options.column("#0", width=int(180 * ratio))
            self.tree_options.column("radio", width=int(50 * ratio))
            
        self.tree_options.update_tags_font_size = _update_tags_fs

        self.tree_options.bind("<Button-1>", self._on_tree_click)
        self.tree_options.bind("<Motion>", self._on_mouse_motion)
        self.tree_options.bind("<Leave>", self._on_mouse_leave)
        self.tree_options.bind("<Configure>", self._on_tree_resize)
        
        self._hovered_item = None
        self._max_text_width = 180
        
        # ==========================================
        # RECHTER BEREICH: Vorschau & Manuelles Zuordnen
        # ==========================================
        self.right_frame = tk.Frame(self.paned, bg="#ffffff", width=10, height=10)
        self.right_frame.pack_propagate(False)
        self.right_frame.grid_propagate(False)
        self.paned.add(self.right_frame, stretch="always", minsize=280)
        
        # Container für Preview (Zugeordnet)
        self.preview_container = tk.Frame(self.right_frame, bg="#ffffff")
        self.preview_container.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        
        header_right = tk.Frame(self.preview_container, bg="#ffffff", pady=5)
        header_right.pack(fill=tk.X)
        self.lbl_preview_title = tk.Label(header_right, text="Zugeordnet", font=("Segoe UI", 11, "bold"), fg="#5f6368", bg="#ffffff")
        self.lbl_preview_title.pack(side=tk.LEFT, padx=5)
        
        bottom_right = tk.Frame(self.preview_container, bg="#ffffff")
        bottom_right.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.separator = tk.Frame(bottom_right, height=4, bg="#dcdcdc")
        self.separator.pack(fill=tk.X, padx=0, pady=(0, 5))
        
        from ui_components import RoundedButton
        self.btn_del = RoundedButton(bottom_right, text="Auswahl Löschen", command=self._on_del_key, theme="primary", bg_light="#ffffff", bg_dark="#1e1e1e", fixed_width=130)
        self.btn_del.pack(side=tk.RIGHT, padx=5, pady=(0, 5))
        
        self.grid_keys = ComplianceGrid(self.preview_container, select_mode="row", show_index=False, show_xscroll=False, show_horizontal_lines=False, show_vertical_lines=True, stretch_columns=True, zoom_id="row_mapping_grid")
        self.grid_keys.set_theme("light")
        self.grid_keys.header_context_menu_enabled = False
        self.grid_keys.index_context_menu_enabled = False
        self.grid_keys.header_row_index = None
        self.grid_keys.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Context Menu
        self.context_menu = tk.Menu(self, tearoff=0)
        self.context_menu.add_command(label="Löschen", command=self._on_del_key)
        self.grid_keys.main_table.bind("<Button-3>", self._show_context_menu)
        self.grid_keys.index.bind("<Button-3>", self._show_context_menu)
        
        self._row_to_key_idx = {}
        self._current_grid_data = []

    def _show_context_menu(self, event):
        r, c = self.grid_keys.get_cell_from_coords(event.widget, event.x, event.y)
        if r is not None and 0 <= r < len(self._current_grid_data):
            if r not in self.grid_keys.selected_rows:
                self.grid_keys.selected_rows.clear()
                self.grid_keys.selected_rows.add(r)
                
                # Select all rows belonging to the same key group
                key_idx = self._row_to_key_idx.get(r)
                if key_idx is not None:
                    for row_idx, k_idx in self._row_to_key_idx.items():
                        if k_idx == key_idx:
                            self.grid_keys.selected_rows.add(row_idx)
                            
                self.grid_keys.redraw()
            self.context_menu.post(event.x_root, event.y_root)
        

    def get_current_key_indices(self, side: int) -> list[int]:
        """Returns all column indices currently defining the key for the given side (from saved keys + current entry)."""
        if self.active_mapping_idx is None or self.active_mapping_idx >= len(self.sheet_mappings):
            return []
            
        mapping = self.sheet_mappings[self.active_mapping_idx]
        if mapping.row_matching_mode != "key_based":
            return []
            
        indices = set()
        for key_mapping in mapping.key_mappings:
            idx_list = key_mapping.col1_indices if side == 1 else key_mapping.col2_indices
            indices.update(idx_list)
            
        selected_indices = self.selected_left_indices if side == 1 else self.selected_right_indices
        indices.update(selected_indices)
            
        return list(indices)

    def refresh_data(self, mappings: list[SheetMapping], ui_update: bool = True):
        """Lädt die aktuellen Mappings neu."""
        self.sheet_mappings = mappings
        
        # If the active mapping no longer exists, reset it
        if self.active_mapping_idx is not None and self.active_mapping_idx >= len(self.sheet_mappings):
            self.active_mapping_idx = None
            
        if self.active_mapping_idx is None and self.sheet_mappings:
            self.active_mapping_idx = 0
            if not self.sheet_mappings[0].row_matching_mode:
                self.sheet_mappings[0].row_matching_mode = "positional"
                
        def format_col(c):
            id_str, val_str = str(c[0]).strip(), str(c[1]).strip()
            if val_str and id_str != val_str.upper():
                if val_str.startswith(id_str): return val_str
                return f"{id_str}     {val_str}"
            return id_str

        # Update key names for all key mappings to reflect potential header changes
        for mapping in self.sheet_mappings:
            if mapping.row_matching_mode == "key_based" and self.data_provider:
                cols1, cols2 = self.data_provider(mapping.sheet1_name, mapping.sheet2_name)
                if hasattr(mapping, 'key_mappings'):
                    for k in mapping.key_mappings:
                        left_parts = []
                        for col_idx in k.col1_indices:
                            if cols1 and 0 <= col_idx < len(cols1):
                                left_parts.append(format_col(cols1[col_idx]))
                        
                        right_parts = []
                        for col_idx in k.col2_indices:
                            if cols2 and 0 <= col_idx < len(cols2):
                                right_parts.append(format_col(cols2[col_idx]))
                                
                        if left_parts: k.col1_names = " + ".join(left_parts)
                        if right_parts: k.col2_names = " + ".join(right_parts)
            
        if ui_update:
            self._populate_options()
            self._update_ui_state()
        
    def _get_tag_for_item(self, item_id, is_hovered):
        parts = item_id.split("_", 1)
        if len(parts) != 2:
            return ""
            
        idx = int(parts[0])
        mode = parts[1]
        
        is_active_category = (self.active_mapping_idx == idx)
        
        if mode == "category":
            if is_hovered:
                return "hover_category"
            return "category_active" if is_active_category else "category_inactive"
            
        # Es ist eine Option
        option_index = ["positional", "key_based", "cross_check"].index(mode)
        is_even = (option_index % 2 == 0)
        
        if is_active_category:
            is_active_option = (self.sheet_mappings[idx].row_matching_mode == mode)
            if is_hovered:
                return "hover_active_even" if is_active_option and is_even else ("hover_active_odd" if is_active_option else ("hover_inactive_even" if is_even else "hover_inactive_odd"))
            else:
                return "option_active_even" if is_active_option and is_even else ("option_active_odd" if is_active_option else ("option_inactive_even" if is_even else "option_inactive_odd"))
        else:
            if is_hovered:
                return "hover_disabled_even" if is_even else "hover_disabled_odd"
            else:
                return "option_disabled_even" if is_even else "option_disabled_odd"

    def _on_tree_resize(self, event=None):
        if not hasattr(self, '_max_text_width'):
            return
            
        tree_width = self.tree_options.winfo_width()
        if tree_width <= 1:
            tree_width = self.tree_options.winfo_reqwidth()
            
        # Minimum width for #0 to fit "Cross-Check" comfortably
        min_col0_width = 130 
        
        # We want #0 to be exactly _max_text_width to hug the text.
        # But if the user drags the sash making the pane too small, we must shrink #0
        # so that the radio column (width 50) is not pushed outside the visible area!
        target_width = max(min_col0_width, min(self._max_text_width, tree_width - 50))
        
        self.tree_options.column("#0", width=int(target_width))

    def _on_mouse_motion(self, event):
        item = self.tree_options.identify_row(event.y)
        if item != self._hovered_item:
            if self._hovered_item and self.tree_options.exists(self._hovered_item):
                tag = self._get_tag_for_item(self._hovered_item, is_hovered=False)
                if tag: self.tree_options.item(self._hovered_item, tags=(tag,))
                
            if item:
                tag = self._get_tag_for_item(item, is_hovered=True)
                if tag: self.tree_options.item(item, tags=(tag,))
                
            self._hovered_item = item

        # Tooltip logic for long category names
        if item:
            parts = item.split("_", 1)
            if len(parts) == 2 and parts[1] == "category":
                idx = int(parts[0])
                if idx < len(self.sheet_mappings):
                    mapping = self.sheet_mappings[idx]
                    name1 = mapping.sheet1_name or "?"
                    name2 = mapping.sheet2_name or "?"
                    full_text = f"[{name1}] \u2194 [{name2}]" if mapping.sheet1_name or mapping.sheet2_name else f"Zuweisung {idx+1}"
                    import tkinter.font as tkfont
                    font_bold = tkfont.Font(family="Segoe UI", size=11, weight="bold")
                    text_width = font_bold.measure(full_text) + 45
                    col_width = self.tree_options.column("#0", "width")
                    
                    if text_width > col_width:
                        if not hasattr(self, "_tooltip"):
                            from property_grid import GridToolTip
                            self._tooltip = GridToolTip(self.tree_options)
                        self._tooltip.show(full_text, event.x_root, event.y_root)
                    else:
                        if hasattr(self, "_tooltip"): self._tooltip.hide()
            else:
                if hasattr(self, "_tooltip"): self._tooltip.hide()
        else:
            if hasattr(self, "_tooltip"): self._tooltip.hide()

    def _on_mouse_leave(self, event):
        if self._hovered_item and self.tree_options.exists(self._hovered_item):
            tag = self._get_tag_for_item(self._hovered_item, is_hovered=False)
            if tag: self.tree_options.item(self._hovered_item, tags=(tag,))
        self._hovered_item = None
        if hasattr(self, "_tooltip"): self._tooltip.hide()

    def _on_tree_click(self, event):
        element = self.tree_options.identify_element(event.x, event.y)
        if element == "Treeitem.indicator":
            return # Let Tkinter handle expand/collapse
            
        region = self.tree_options.identify_region(event.x, event.y)
        if region in ("cell", "tree"):
            item_id = self.tree_options.identify_row(event.y)
            if not item_id: return
            
            parts = item_id.split("_", 1)
            if len(parts) != 2: return
            
            idx = int(parts[0])
            mode = parts[1]
            
            # Validierung vor dem Wechsel
            if self.active_mapping_idx is not None and self.active_mapping_idx != idx:
                mapping = self.sheet_mappings[self.active_mapping_idx]
                if mapping.row_matching_mode == "key_based":
                    if not mapping.key_mappings:
                        from tkinter import messagebox
                        messagebox.showerror("Validierungsfehler", "Bitte definieren Sie zuerst die Schlüsselspalten für die aktuelle Zuweisung oder wählen Sie einen anderen Modus.")
                        return
                    if len(mapping.key_mappings[0].col1_indices) != len(mapping.key_mappings[0].col2_indices):
                        from tkinter import messagebox
                        messagebox.showerror("Validierungsfehler", "Die Anzahl der gewählten Schlüsselspalten muss auf beiden Seiten gleich sein.")
                        return
            
            if mode == "category":
                if self.active_mapping_idx != idx:
                    self._switch_active_mapping(idx)
            else:
                if self.sheet_mappings[idx].row_matching_mode != mode:
                    self.sheet_mappings[idx].row_matching_mode = mode
                if self.active_mapping_idx != idx:
                    self._switch_active_mapping(idx)
                else:
                    self._populate_options()
                    self._update_ui_state()
                    
        return "break"

    def _switch_active_mapping(self, idx):
        self.active_mapping_idx = idx
        self._populate_options()
        self._update_ui_state()

    def _populate_options(self):
        open_states = {}
        for item in self.tree_options.get_children():
            open_states[item] = self.tree_options.item(item, "open")
            self.tree_options.delete(item)
            
        import tkinter.font as tkfont
        try:
            font_bold = tkfont.Font(family="Segoe UI", size=11, weight="bold")
            self._max_text_width = 180
            for mapping in self.sheet_mappings:
                name1 = mapping.sheet1_name or "?"
                name2 = mapping.sheet2_name or "?"
                category_text = f"[{name1}] \u2194 [{name2}]" if mapping.sheet1_name or mapping.sheet2_name else f"Zuweisung"
                w = font_bold.measure(category_text) + 45
                if w > self._max_text_width: self._max_text_width = w
            
            self._on_tree_resize()
        except Exception:
            pass
            
        for i, mapping in enumerate(self.sheet_mappings):
            name1 = mapping.sheet1_name or "?"
            name2 = mapping.sheet2_name or "?"
            category_text = f"[{name1}] \u2194 [{name2}]" if mapping.sheet1_name or mapping.sheet2_name else f"Zuweisung {i+1}"
            
            is_active_category = (self.active_mapping_idx == i)
            cat_tag = "category_active" if is_active_category else "category_inactive"
            cat_id = f"{i}_category"
            
            is_open = open_states.get(cat_id, True)
            self.tree_options.insert("", "end", iid=cat_id, text=category_text, values=("",), tags=(cat_tag,), open=is_open)
            
            options = [
                ("Positionell", "positional"),
                ("Schlüssel", "key_based"),
                ("Cross-Check", "cross_check")
            ]
            
            for opt_idx, (text, opt_mode) in enumerate(options):
                opt_id = f"{i}_{opt_mode}"
                is_active_option = (mapping.row_matching_mode == opt_mode)
                checkbox_char = "⬤" if is_active_option else "○"
                tag = self._get_tag_for_item(opt_id, is_hovered=False)
                
                self.tree_options.insert(cat_id, "end", iid=opt_id, text=f"  {text}", values=(checkbox_char,), tags=(tag,))
        
        if self.active_mapping_idx is not None:
            active_cat = f"{self.active_mapping_idx}_category"
            if self.tree_options.exists(active_cat):
                self.tree_options.selection_set(active_cat)

    def validate_current_state(self) -> bool:
        from tkinter import messagebox
        for i, mapping in enumerate(self.sheet_mappings):
            if mapping.row_matching_mode == "key_based" and not mapping.key_mappings:
                name = f"'{mapping.sheet1_name}' <-> '{mapping.sheet2_name}'" if mapping.sheet1_name else f"Zuweisung {i+1}"
                messagebox.showerror("Validierungsfehler", f"Für {name} ist 'Schlüssel' ausgewählt, aber es wurden keine Schlüsselspalten definiert. Bitte definieren Sie Schlüsselspalten oder wählen Sie einen anderen Modus.")
                return False
        return True

    def _update_ui_state(self):
        if self.active_mapping_idx is None or self.active_mapping_idx >= len(self.sheet_mappings):
            self._refresh_key_list()
            if self.on_key_based_toggled:
                self.on_key_based_toggled(False)
            if self.on_keys_changed:
                self.on_keys_changed(1)
                self.on_keys_changed(2)
            return
            
        mapping = self.sheet_mappings[self.active_mapping_idx]
        
        if mapping.row_matching_mode == "key_based":
            self._refresh_key_list()
                
            if self.on_key_based_toggled:
                self.on_key_based_toggled(True)
        else:
            self._refresh_key_list()
            
            if self.on_key_based_toggled:
                self.on_key_based_toggled(False)

        if self.on_sheet_pair_selected:
            should_expand = (mapping.row_matching_mode == "key_based")
            self.on_sheet_pair_selected(mapping.sheet1_name, mapping.sheet2_name, should_expand)

        if self.on_keys_changed:
            self.on_keys_changed(1)
            self.on_keys_changed(2)

    def _refresh_key_list(self):
        self._row_to_key_idx.clear()
        self._current_grid_data = []
        row_idx = 0
            
        if self.active_mapping_idx is not None and self.active_mapping_idx < len(self.sheet_mappings):
            mapping = self.sheet_mappings[self.active_mapping_idx]
            if mapping.row_matching_mode == "key_based":
                mappings_to_show = mapping.key_mappings if hasattr(mapping, 'key_mappings') else []
                
                cols1, cols2 = None, None
                if self.data_provider:
                    cols1, cols2 = self.data_provider(mapping.sheet1_name, mapping.sheet2_name)
                    
                def format_col(c):
                    id_str, val_str = str(c[0]).strip(), str(c[1]).strip()
                    if val_str and id_str != val_str.upper():
                        if val_str.startswith(id_str): return val_str
                        return f"{id_str}     {val_str}"
                    return id_str

                for idx, k in enumerate(mappings_to_show):
                    left_parts = []
                    for i, col_idx in enumerate(k.col1_indices):
                        if cols1 and 0 <= col_idx < len(cols1):
                            left_parts.append(format_col(cols1[col_idx]))
                        else:
                            fallback = [p.strip() for p in k.col1_names.split('+')]
                            left_parts.append(fallback[i] if i < len(fallback) else "?")
                    
                    right_parts = []
                    for i, col_idx in enumerate(k.col2_indices):
                        if cols2 and 0 <= col_idx < len(cols2):
                            right_parts.append(format_col(cols2[col_idx]))
                        else:
                            fallback = [p.strip() for p in k.col2_names.split('+')]
                            right_parts.append(fallback[i] if i < len(fallback) else "?")
                            
                    k.col1_names = "\n".join(left_parts)
                    k.col2_names = "\n".join(right_parts)

                    self._current_grid_data.append([k.col1_names, k.col2_names])
                    self._row_to_key_idx[row_idx] = idx
                    row_idx += 1
                        
        self.grid_keys.set_data(self._current_grid_data, ["Spalte Links", "Spalte Rechts"])

    def set_theme(self, theme):
        is_dark = (theme == "dark")
        bg_main = "#1e1e1e" if is_dark else "#ffffff"
        bg_alt = "#252525" if is_dark else "#f4f5f7"
        bg_hover = "#3a3a3a" if is_dark else "#e5f3ff"
        fg_active = "#ffffff" if is_dark else "#0078D7"
        fg_text = "#e0e0e0" if is_dark else "#333333"
        fg_inactive = "#a0a0a0" if is_dark else "#888888"

        self.config(bg=bg_main)

        style = ttk.Style()
        style.configure("RowMapping.Treeview", background=bg_main, fieldbackground=bg_main, foreground=fg_text)

        self.tree_options.tag_configure("category_active", foreground=fg_text, background=bg_main)
        self.tree_options.tag_configure("category_inactive", foreground=fg_inactive, background=bg_main)

        self.tree_options.tag_configure("option_active_even", foreground=fg_active, background=bg_main)
        self.tree_options.tag_configure("option_active_odd", foreground=fg_active, background=bg_alt)
        self.tree_options.tag_configure("option_inactive_even", foreground=fg_text, background=bg_main)
        self.tree_options.tag_configure("option_inactive_odd", foreground=fg_text, background=bg_alt)
        self.tree_options.tag_configure("option_disabled_even", foreground=fg_inactive, background=bg_main)
        self.tree_options.tag_configure("option_disabled_odd", foreground=fg_inactive, background=bg_alt)

        self.tree_options.tag_configure("hover_category", foreground=fg_text, background=bg_hover)
        self.tree_options.tag_configure("hover_active_even", foreground=fg_active, background=bg_hover)
        self.tree_options.tag_configure("hover_active_odd", foreground=fg_active, background=bg_hover)
        self.tree_options.tag_configure("hover_inactive_even", foreground=fg_text, background=bg_hover)
        self.tree_options.tag_configure("hover_inactive_odd", foreground=fg_text, background=bg_hover)
        self.tree_options.tag_configure("hover_disabled_even", foreground=fg_inactive, background=bg_hover)
        self.tree_options.tag_configure("hover_disabled_odd", foreground=fg_inactive, background=bg_hover)

        if hasattr(self, 'grid_keys'):
            self.grid_keys.set_theme(theme)

        main_app = self.winfo_toplevel()
        if hasattr(main_app, '_apply_colors'):
            for child in self.winfo_children():
                main_app._apply_colors(child)
                
        bg_sash = "#555555" if is_dark else "#dcdcdc"
        if hasattr(self, 'separator'):
            self.separator.config(bg=bg_sash)

    def _on_del_key(self):
        if self.active_mapping_idx is None or self.active_mapping_idx >= len(self.sheet_mappings):
            return
            
        mapping = self.sheet_mappings[self.active_mapping_idx]
        selected_rows = self.grid_keys.selected_rows
        if not selected_rows: return
        
        indices_to_delete = set()
        for row_idx in selected_rows:
            key_idx = self._row_to_key_idx.get(row_idx)
            if key_idx is not None:
                indices_to_delete.add(key_idx)
                
        for idx in sorted(list(indices_to_delete), reverse=True):
            if 0 <= idx < len(mapping.key_mappings):
                del mapping.key_mappings[idx]
                
        self._refresh_key_list()
        
        if self.on_keys_changed:
            self.on_keys_changed(1)
            self.on_keys_changed(2)

    def receive_selection(self, side: int, col_idx: int, col_name: str):
        """Called from main.py when a column is clicked in the tree or grid."""
        main_app = self.winfo_toplevel()
        if hasattr(main_app, '_current_tab_index') and main_app._current_tab_index != 4:
            return

        if self.active_mapping_idx is None or self.active_mapping_idx >= len(self.sheet_mappings):
            return
            
        mapping = self.sheet_mappings[self.active_mapping_idx]
        if mapping.row_matching_mode != "key_based":
            return
            
        if not hasattr(self, '_editing_state'):
            self._editing_state = "none"
            self._pending_left_idx = []
            self._pending_left_name = []
            self._pending_right_idx = []
            self._pending_right_name = []

        def get_str(name_list):
            return "\n".join(name_list) if isinstance(name_list, list) else str(name_list)

        if not hasattr(mapping, 'key_mappings'):
            mapping.key_mappings = []
            
        if len(mapping.key_mappings) == 0:
            from mapping_models import KeyMapping
            mapping.key_mappings.append(KeyMapping(col1_names="", col2_names="", col1_indices=[], col2_indices=[]))
            
        km = mapping.key_mappings[0]
        
        # Ensure indices are lists
        if not isinstance(km.col1_indices, list): km.col1_indices = [km.col1_indices] if km.col1_indices is not None else []
        if not isinstance(km.col2_indices, list): km.col2_indices = [km.col2_indices] if km.col2_indices is not None else []
        
        left_names = km.col1_names.split('\n') if km.col1_names else []
        right_names = km.col2_names.split('\n') if km.col2_names else []

        if side == 1:
            if col_idx not in km.col1_indices:
                km.col1_indices.append(col_idx)
                left_names.append(col_name)
                km.col1_names = get_str(left_names)
        else:
            if col_idx not in km.col2_indices:
                km.col2_indices.append(col_idx)
                right_names.append(col_name)
                km.col2_names = get_str(right_names)

        # Force ONLY ONE key mapping in the array
        if len(mapping.key_mappings) > 1:
            mapping.key_mappings = [km]
                
        self._refresh_key_list()
        if self.on_keys_changed:
            self.on_keys_changed(side)

    def validate_current_state(self) -> bool:
        for idx, mapping in enumerate(self.sheet_mappings):
            if mapping.row_matching_mode == "key_based":
                name1 = mapping.sheet1_name or f"Zuweisung {idx+1}"
                if not mapping.key_mappings:
                    from tkinter import messagebox
                    messagebox.showerror("Validierungsfehler", f"Fehler in '{name1}':\nBitte definieren Sie zuerst die Schlüsselspalten oder wählen Sie einen anderen Modus.")
                    return False
                km = mapping.key_mappings[0]
                if len(km.col1_indices) != len(km.col2_indices):
                    from tkinter import messagebox
                    messagebox.showerror("Validierungsfehler", f"Fehler in '{name1}':\nDie Anzahl der gewählten Schlüsselspalten muss auf beiden Seiten gleich sein.")
                    return False
        return True
