import tkinter as tk
from tkinter import ttk
import tkinter.messagebox as messagebox
from property_grid import TkPropertyGrid
from grid_widget import ComplianceGrid
from mapping_models import SheetMapping, ColumnMapping
from ui_components import ZoomManager

class ColumnMappingView(tk.Frame):
    def __init__(self, parent, data_provider=None, *args, **kwargs):
        super().__init__(parent, bg="#ffffff", *args, **kwargs)
        
        self.sheet_mappings: list[SheetMapping] = []
        self.active_mapping_idx = None
        self.selected_left_idx = -1
        self.selected_right_idx = -1
        self.data_provider = data_provider  # Callback: func(sheet1_name, sheet2_name) -> (cols1, cols2)
        self.on_sheet_pair_selected = None  # Callback(sheet1_name, sheet2_name)
        self.on_manual_mode_toggled = None  # Callback(is_manual)
        self.on_cols_changed = None # Callback(side)
        
        # We track whether we have populated the mappings at least once
        # to avoid wiping out user data simply by switching back and forth.
        self._cached_mappings = set() 
        
        self._setup_ui()
        self.zoom_manager_left = ZoomManager(self.frame_left, zoom_id="column_mapping_panel")
        self.zoom_manager_right = ZoomManager(self.frame_right, zoom_id="column_mapping_grid")
        
    def _setup_ui(self):
        # Top label removed upon user request to unify headers
        
        # Split layout
        self.paned = tk.PanedWindow(self, orient=tk.HORIZONTAL, sashwidth=4, bd=0, bg="#dcdcdc")
        self.paned.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Left side: Mode selection (PropertyGrid style)
        self.frame_left = tk.Frame(self.paned, bg="#ffffff", width=10, height=10)
        self.frame_left.pack_propagate(False)
        self.frame_left.grid_propagate(False)
        self.paned.add(self.frame_left, stretch="always", minsize=200)
        
        # Einheitlicher Header Links
        header_left = tk.Frame(self.frame_left, bg="#ffffff", pady=5)
        header_left.pack(fill=tk.X)
        tk.Label(header_left, text="Zuordnungsmodus", font=("Segoe UI", 11, "bold"), fg="#5f6368", bg="#ffffff").pack(side=tk.LEFT, padx=5)

        # Container für Schlüssel-Definition am unteren Rand reservieren
        self.pnl_keys_container = tk.Frame(self.frame_left)
        self.pnl_keys_container.pack(side=tk.BOTTOM, fill=tk.X)

        # Right side: Keys definition & Grid
        self.frame_right = tk.Frame(self.paned, bg="#ffffff", width=10, height=10)
        self.frame_right.pack_propagate(False)
        self.frame_right.grid_propagate(False)
        self.paned.add(self.frame_right, stretch="always", minsize=280)

        # Treeview für Optionen
        style = ttk.Style()
        style.configure("ColumnMapping.Treeview", rowheight=32, font=("Segoe UI", 11), borderwidth=0, background="#ffffff", fieldbackground="#ffffff")
        style.layout("ColumnMapping.Treeview", [('ColumnMapping.Treeview.treearea', {'sticky': 'nswe'})]) # Remove borders

        tree_container = tk.Frame(self.frame_left, bg="#ffffff")
        tree_container.pack(side=tk.TOP, fill=tk.BOTH, expand=True, pady=(5, 0))

        self.tree_options = ttk.Treeview(tree_container, columns=("radio",), show="tree", style="ColumnMapping.Treeview")
        
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
            
            ratio = fs / 11.0
            self.tree_options.column("#0", width=int(180 * ratio))
            self.tree_options.column("radio", width=int(50 * ratio))
            
        self.tree_options.update_tags_font_size = _update_tags_fs

        self.tree_options.bind("<Button-1>", self._on_tree_click)
        self.tree_options.bind("<Motion>", self._on_mouse_motion)
        self.tree_options.bind("<Leave>", self._on_mouse_leave)
        self.tree_options.bind("<Configure>", self._on_tree_resize)
        
        self._hovered_item = None
        
        # ==========================================
        # RECHTER BEREICH: Vorschau & Manuelles Zuordnen
        # ==========================================
        # Container für Preview (Zugeordnet)
        self.preview_container = tk.Frame(self.frame_right, bg="#ffffff")
        self.preview_container.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        
        header_right = tk.Frame(self.preview_container, bg="#ffffff", pady=5)
        header_right.pack(fill=tk.X)
        self.lbl_preview_title = tk.Label(header_right, text="Zugeordnet", font=("Segoe UI", 11, "bold"), fg="#5f6368", bg="#ffffff")
        self.lbl_preview_title.pack(side=tk.LEFT, padx=5)
        
        bottom_right = tk.Frame(self.preview_container, bg="#ffffff")
        bottom_right.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.separator = tk.Frame(bottom_right, height=4, bg="#dcdcdc")
        self.separator.pack(fill=tk.X, padx=0, pady=(0, 5))
        
        btn_frame_bottom = tk.Frame(bottom_right, bg="#ffffff")
        btn_frame_bottom.pack(side=tk.RIGHT, padx=5, pady=(0, 5))
        
        from ui_components import RoundedButton
        self.btn_reset_auto = RoundedButton(btn_frame_bottom, text="Standard", command=self._reset_auto_mapping, theme="primary", bg_light="#ffffff", bg_dark="#1e1e1e", fixed_width=110)
        self.btn_reset_auto.pack(side=tk.RIGHT, padx=(5, 0))

        self.btn_del = RoundedButton(btn_frame_bottom, text="Auswahl Löschen", command=self._del_key, theme="primary", bg_light="#ffffff", bg_dark="#1e1e1e", fixed_width=130)
        self.btn_del.pack(side=tk.RIGHT)
        
        self.grid_cols = ComplianceGrid(self.preview_container, select_mode="row", show_index=False, show_xscroll=False, show_horizontal_lines=False, show_vertical_lines=True, stretch_columns=True, zoom_id="column_mapping_grid")
        self.grid_cols.set_theme("light")
        self.grid_cols.header_context_menu_enabled = False
        self.grid_cols.index_context_menu_enabled = False
        self.grid_cols.header_row_index = None
        
        self.grid_cols.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=5)

        
        # Context Menu
        self.context_menu = tk.Menu(self, tearoff=0)
        self.context_menu.add_command(label="Löschen", command=self._del_key)
        self.grid_cols.main_table.bind("<Button-3>", self._show_context_menu)
        self.grid_cols.index.bind("<Button-3>", self._show_context_menu)
        self.grid_cols.on_row_selected = self._on_grid_cols_select

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
        style.configure("ColumnMapping.Treeview", background=bg_main, fieldbackground=bg_main, foreground=fg_text)

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

        if hasattr(self, 'grid_cols'):
            self.grid_cols.set_theme(theme)

        main_app = self.winfo_toplevel()
        if hasattr(main_app, '_apply_colors'):
            for child in self.winfo_children():
                main_app._apply_colors(child)

        # Bewahre die Trennlinien-Farbe
        sep_color = "#333333" if is_dark else "#dcdcdc"
        if hasattr(self, 'separator'):
            self.separator.configure(bg=sep_color)

    def _on_grid_cols_select(self, row_idx):
        if self.active_mapping_idx is None or self.active_mapping_idx >= len(self.sheet_mappings):
            return
            
        mapping = self.sheet_mappings[self.active_mapping_idx]
        
        try:
            if row_idx < 0 or row_idx >= len(mapping.column_mappings):
                return

            col_mapping = mapping.column_mappings[row_idx]
            self.selected_left_idx = col_mapping.col1_idx
            self.selected_right_idx = col_mapping.col2_idx
            
            self._editing_state = "none"
            self._pending_left = None
            self._pending_right = None
            
            if self.on_cols_changed:
                self.on_cols_changed(0)
        except Exception as e:
            print(f"Error selecting mapped columns: {e}")

    def _show_context_menu(self, event):
        r, c = self.grid_cols.get_cell_from_coords(event.widget, event.x, event.y)
        if r is not None and 0 <= r < len(self._current_grid_data):
            if r not in self.grid_cols.selected_rows:
                self.grid_cols.selected_rows.clear()
                self.grid_cols.selected_rows.add(r)
                self.grid_cols.redraw()
            self.context_menu.post(event.x_root, event.y_root)
    def load_mappings(self, mappings: list[SheetMapping], ui_update: bool = True):
        """Called by main.py when transitioning to this tab."""
        self.sheet_mappings = mappings
        
        if self.active_mapping_idx is not None and self.active_mapping_idx >= len(self.sheet_mappings):
            self.active_mapping_idx = None
            
        if self.active_mapping_idx is None and self.sheet_mappings:
            self.active_mapping_idx = 0
        
        for i, mapping in enumerate(self.sheet_mappings):
            if i not in self._cached_mappings:
                if not mapping.column_matching_mode:
                    mapping.column_matching_mode = "positional"
                
                if mapping.column_matching_mode == "positional" and not mapping.column_mappings:
                    self._generate_positional_mappings(mapping)
                    
                self._cached_mappings.add(i)
                
            # --- Update column names for all mappings so they are fresh for Tab 7 ---
            if self.data_provider:
                cols1, cols2 = self.data_provider(mapping.sheet1_name, mapping.sheet2_name)
                
                def format_col(c):
                    id_str, val_str = str(c[0]).strip(), str(c[1]).strip()
                    has_header = c[2] if len(c) > 2 else False
                    if has_header:
                        return f"{id_str}     {val_str}"
                    return id_str
                    
                for m in mapping.column_mappings:
                    if m.col1_idx >= 0 and cols1 and m.col1_idx < len(cols1):
                        m.col1_name = format_col(cols1[m.col1_idx])
                    if m.col2_idx >= 0 and cols2 and m.col2_idx < len(cols2):
                        m.col2_name = format_col(cols2[m.col2_idx])
        

        if ui_update:
            if self.on_manual_mode_toggled:
                self.on_manual_mode_toggled(False)
            
            self._current_grid_data = []
            self.grid_cols.set_data(self._current_grid_data, ["Spalte Links", "Spalte Rechts"])
                
            self._populate_options()
            self._update_ui_state()

    def _populate_options(self):
        # We need to preserve open/close states
        open_states = {}
        if hasattr(self, 'tree_options'):
            for item in self.tree_options.get_children(""):
                if item.endswith("_category"):
                    open_states[item] = self.tree_options.item(item, "open")
        
        self.tree_options.delete(*self.tree_options.get_children())
        
        try:
            import tkinter.font as tkfont
            font_bold = tkfont.Font(family="Segoe UI", size=11, weight="bold")
            max_w = 130
            for i, mapping in enumerate(self.sheet_mappings):
                name1 = mapping.sheet1_name or "?"
                name2 = mapping.sheet2_name or "?"
                category_text = f"[{name1}] \u2194 [{name2}]" if mapping.sheet1_name or mapping.sheet2_name else f"Zuweisung {i+1}"
                w = font_bold.measure(category_text) + 45
                if w > max_w: max_w = w
            self._max_text_width = max_w
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
            
            # If not cached, auto-initialize to positional
            if i not in self._cached_mappings:
                if not mapping.column_matching_mode:
                    mapping.column_matching_mode = "positional"
                self._cached_mappings.add(i)
                
            options = [
                ("Positionell", "positional"),
                ("Manuell", "manual"),
                ("Nach Namen", "by_name"),
                ("Cross-Check", "cross_check")
            ]
            
            for opt_idx, (text, opt_mode) in enumerate(options):
                opt_id = f"{i}_{opt_mode}"
                
                is_selected = (mapping.column_matching_mode == opt_mode)
                
                radio_char = "⬤" if is_selected else "○"
                
                item_tag = self._get_tag_for_item(opt_id, is_hovered=False)
                
                self.tree_options.insert(cat_id, "end", iid=opt_id, text=f"  {text}", values=(radio_char,), tags=(item_tag,))
        
        if self.active_mapping_idx is not None:
            active_cat = f"{self.active_mapping_idx}_category"
            if self.tree_options.exists(active_cat):
                self.tree_options.selection_set(active_cat)

    def _get_tag_for_item(self, item_id, is_hovered=False):
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
        option_index = ["positional", "manual", "by_name", "cross_check"].index(mode)
        is_even = (option_index % 2 == 0)
        
        if is_active_category:
            is_active_option = (self.sheet_mappings[idx].column_matching_mode == mode)
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
            
        min_col0_width = 130 
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

        # Tooltip logic
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

    def _can_leave_active_mapping(self) -> bool:
        if self.active_mapping_idx is None:
            return True
        old_mapping = self.sheet_mappings[self.active_mapping_idx]
        if old_mapping.column_matching_mode == "manual":
            p_left = getattr(self, '_pending_left', None)
            p_right = getattr(self, '_pending_right', None)
            if (p_left or p_right) and not (p_left and p_right):
                from tkinter import messagebox
                messagebox.showerror("Unvollständige Zuweisung", "Es gibt eine unvollständige Spaltenzuweisung. Bitte vervollständigen Sie das Paar oder löschen Sie die Auswahl, bevor Sie fortfahren.")
                return False
            if not old_mapping.column_mappings:
                from tkinter import messagebox
                name = f"'{old_mapping.sheet1_name}' <-> '{old_mapping.sheet2_name}'" if old_mapping.sheet1_name else f"Zuweisung {self.active_mapping_idx+1}"
                messagebox.showerror("Validierungsfehler", f"Für {name} ist 'Manuell' ausgewählt, aber es wurden keine Spalten zugeordnet. Bitte ordnen Sie Spalten zu oder wählen Sie einen anderen Modus.")
                return False
        return True

    def _switch_active_mapping(self, new_idx):
        if self.active_mapping_idx == new_idx:
            return
            
        # Validation for manual mode leaving
        if not self._can_leave_active_mapping():
            self._populate_options()
            return
                
        self.active_mapping_idx = new_idx
        
        self._editing_state = "none"
        self._pending_left = None
        self._pending_right = None
        
        self._populate_options()
        self._update_ui_state()

    def _on_tree_click(self, event):
        element = self.tree_options.identify_element(event.x, event.y)
        if element == "Treeitem.indicator":
            return
            
        region = self.tree_options.identify_region(event.x, event.y)
        if region in ("cell", "tree"):
            item_id = self.tree_options.identify_row(event.y)
            if not item_id:
                return
                
            parts = item_id.split("_", 1)
            if len(parts) != 2:
                return
                
            idx = int(parts[0])
            mode = parts[1]
            
            if mode == "category":
                if self.active_mapping_idx != idx:
                    self._switch_active_mapping(idx)
            else:
                mapping = self.sheet_mappings[idx]
                old_mode = mapping.column_matching_mode
                
                # PRE-VALIDATION before any state modification
                if self.active_mapping_idx != idx:
                    if not self._can_leave_active_mapping():
                        self._populate_options()
                        return "break"
                else:
                    if old_mode == "manual" and old_mode != mode:
                        p_left = getattr(self, '_pending_left', None)
                        p_right = getattr(self, '_pending_right', None)
                        if (p_left or p_right) and not (p_left and p_right):
                            from tkinter import messagebox
                            messagebox.showerror("Unvollständige Zuweisung", "Es gibt eine unvollständige Spaltenzuweisung. Bitte vervollständigen Sie das Paar oder löschen Sie die Auswahl, bevor Sie den Modus wechseln.")
                            self._populate_options()
                            return "break"
                
                if old_mode != mode or mode in ("positional", "by_name"):
                    # Cache mappings for the old mode
                    if not hasattr(mapping, 'cached_mode_mappings'):
                        mapping.cached_mode_mappings = {}
                    
                    if old_mode and old_mode != mode:
                        mapping.cached_mode_mappings[old_mode] = mapping.column_mappings.copy()

                    mapping.column_matching_mode = mode
                    
                    if old_mode != mode:
                        mapping.column_mappings.clear()
                        self._editing_state = "none"
                        self._pending_left = None
                        self._pending_right = None
                        self.selected_left_idx = -1
                        self.selected_right_idx = -1
                    
                    # Restore from cache if available, else generate
                    if mode in mapping.cached_mode_mappings and old_mode != mode:
                        mapping.column_mappings.extend(mapping.cached_mode_mappings[mode])
                    else:
                        if mode == "positional":
                            self._generate_positional_mappings(mapping)
                        elif mode == "by_name":
                            self._generate_name_based_column_mappings(mapping)
                
                if self.active_mapping_idx != idx:
                    self._switch_active_mapping(idx)
                else:
                    self._populate_options()
                    self._update_ui_state()
                    if self.on_cols_changed:
                        self.on_cols_changed(0)
                    
        return "break"
            
    def validate_current_state(self) -> bool:
        from tkinter import messagebox
        
        p_left = getattr(self, '_pending_left', None)
        p_right = getattr(self, '_pending_right', None)
        if (p_left or p_right) and not (p_left and p_right):
            messagebox.showerror("Unvollständige Zuweisung", "Es gibt eine unvollständige Spaltenzuweisung im aktuellen Arbeitsblatt. Bitte vervollständigen Sie das Paar oder löschen Sie die Auswahl, bevor Sie fortfahren.")
            return False
            
        for i, mapping in enumerate(self.sheet_mappings):
            if mapping.column_matching_mode == "manual" and not mapping.column_mappings:
                name = f"'{mapping.sheet1_name}' <-> '{mapping.sheet2_name}'" if mapping.sheet1_name else f"Zuweisung {i+1}"
                messagebox.showerror("Validierungsfehler", f"Für {name} ist 'Manuell' ausgewählt, aber es wurden keine Spalten zugeordnet. Bitte ordnen Sie Spalten zu oder wählen Sie einen anderen Modus.")
                return False
        return True

    def _update_ui_state(self):
        if self.active_mapping_idx is None or self.active_mapping_idx >= len(self.sheet_mappings):
            if self.on_manual_mode_toggled:
                self.on_manual_mode_toggled(False)
            self._refresh_col_list()
            return
            
        mapping = self.sheet_mappings[self.active_mapping_idx]
        
        if mapping.column_matching_mode == "manual":
            if self.on_manual_mode_toggled:
                self.on_manual_mode_toggled(True)
        else:
            if self.on_manual_mode_toggled:
                self.on_manual_mode_toggled(False)
                
        if self.on_sheet_pair_selected:
            should_expand = (mapping.column_matching_mode == "manual")
            self.on_sheet_pair_selected(mapping.sheet1_name, mapping.sheet2_name, should_expand)
            
        self._refresh_col_list()

    def _generate_positional_mappings(self, mapping):
        if not self.data_provider: return
        
        cols1, cols2 = self.data_provider(mapping.sheet1_name, mapping.sheet2_name)
        if not cols1 or not cols2: return
        
        mapping.column_mappings.clear()
        
        count = min(len(cols1), len(cols2))
        for i in range(count):
            is_ignored1 = len(cols1[i]) > 3 and cols1[i][3]
            is_ignored2 = len(cols2[i]) > 3 and cols2[i][3]
            
            if is_ignored1 or is_ignored2:
                continue
                
            id1 = cols1[i][0]
            id2 = cols2[i][0]
            mapping.column_mappings.append(ColumnMapping(id1, id2, i, i))

    def _generate_name_based_column_mappings(self, mapping):
        if not self.data_provider: return
        
        cols1, cols2 = self.data_provider(mapping.sheet1_name, mapping.sheet2_name)
        if not cols1 or not cols2: 
            messagebox.showerror("Fehler", "Spaltennamen konnten nicht geladen werden.\nBitte stellen Sie sicher, dass die Parsing-Einstellungen korrekt sind.")
            return
            
        mapping.column_mappings.clear()
        
        matched_count = 0
        total_cols1 = len(cols1)
        matched_col1_ids = set()
        
        c2_vals_stripped = [str(c[1]).strip() for c in cols2]
        
        # Ignorierte Spalten in cols2 aus der Suche entfernen
        for i, c in enumerate(cols2):
            if len(c) > 3 and c[3]:
                c2_vals_stripped[i] = None
        
        for i, c1 in enumerate(cols1):
            if len(c1) > 3 and c1[3]:
                total_cols1 -= 1
                continue
                
            id1, val1 = c1[0], c1[1]
            val1_str = str(val1).strip()
            if val1_str in c2_vals_stripped:
                idx = c2_vals_stripped.index(val1_str)
                id2 = cols2[idx][0]
                mapping.column_mappings.append(ColumnMapping(id1, id2, i, idx))
                matched_count += 1
                matched_col1_ids.add(id1)
                c2_vals_stripped[idx] = None 
                
        unmatched = total_cols1 - matched_count
        msg = f"Namensbasierte Spalten-Zuordnung für:\n'{mapping.sheet1_name}' \u2194 '{mapping.sheet2_name}'\n\n"
        msg += f"• Zugeordnet: {matched_count} von {total_cols1} Spalten\n"
        
        if unmatched > 0:
            msg += f"• ACHTUNG: {unmatched} Spalten konnten nicht zugeordnet werden!\n\n"
            msg += "Nicht zugeordnete Spalten (Links):\n"
            for c1 in cols1:
                id1, val1 = c1[0], c1[1]
                if id1 not in matched_col1_ids:
                    msg += f"  - {id1} (Header: {val1})\n"
            messagebox.showwarning("Namensbasierte Zuordnung", msg)
        else:
            msg += "\nAlle Spalten wurden erfolgreich zugeordnet."
            messagebox.showinfo("Namensbasierte Zuordnung", msg)

    def _update_reset_button(self):
        if not hasattr(self, 'pnl_reset'): return
        
        if self._can_reset_current_mapping():
            if str(self.pnl_reset) not in self.right_paned.panes():
                self.right_paned.add(self.pnl_reset, stretch="never", minsize=60)
        else:
            if str(self.pnl_reset) in self.right_paned.panes():
                self.right_paned.forget(self.pnl_reset)

    def _can_reset_current_mapping(self):
        if self.active_mapping_idx is None or self.active_mapping_idx >= len(self.sheet_mappings):
            return False
            
        mapping = self.sheet_mappings[self.active_mapping_idx]
        mode = mapping.column_matching_mode
        if mode not in ("positional", "by_name"):
            return False
            
        if not self.data_provider:
            return False
            
        cols1, cols2 = self.data_provider(mapping.sheet1_name, mapping.sheet2_name)
        if not cols1 or not cols2:
            return False
            
        expected_count = 0
        if mode == "positional":
            count = min(len(cols1), len(cols2))
            for i in range(count):
                is_ignored1 = len(cols1[i]) > 3 and cols1[i][3]
                is_ignored2 = len(cols2[i]) > 3 and cols2[i][3]
                if not is_ignored1 and not is_ignored2:
                    expected_count += 1
        elif mode == "by_name":
            c2_vals_stripped = [str(c[1]).strip() if not (len(c) > 3 and c[3]) else None for c in cols2]
            for i, c1 in enumerate(cols1):
                if len(c1) > 3 and c1[3]: continue
                val1_str = str(c1[1]).strip()
                if val1_str in c2_vals_stripped:
                    idx = c2_vals_stripped.index(val1_str)
                    expected_count += 1
                    c2_vals_stripped[idx] = None
                    
        return len(mapping.column_mappings) < expected_count

    def _reset_auto_mapping(self):
        if self.active_mapping_idx is None or self.active_mapping_idx >= len(self.sheet_mappings):
            return
            
        mapping = self.sheet_mappings[self.active_mapping_idx]
        mode = mapping.column_matching_mode
        if mode == "positional":
            self._generate_positional_mappings(mapping)
        elif mode == "by_name":
            self._generate_name_based_column_mappings(mapping)
            
        if hasattr(mapping, 'cached_mode_mappings') and mode in mapping.cached_mode_mappings:
            mapping.cached_mode_mappings[mode] = mapping.column_mappings.copy()
            
        self._refresh_col_list()
        if self.on_cols_changed:
            self.on_cols_changed(0)

    def _refresh_col_list(self):
        self._update_reset_button()
        self._current_grid_data = []
        
        if self.active_mapping_idx is None or self.active_mapping_idx >= len(self.sheet_mappings):
            self.grid_cols.set_data(self._current_grid_data, ["Spalte Links", "Spalte Rechts"])
            return
            
        mapping = self.sheet_mappings[self.active_mapping_idx]
            
        if mapping.column_matching_mode == "cross_check":
            self.grid_cols.set_data(self._current_grid_data, ["Spalte Links", "Spalte Rechts"])
            return

        # Holen der aktuellen Spaltennamen, um sie mit den gespeicherten Indizes abzugleichen
        cols1, cols2 = None, None
        if self.data_provider:
            cols1, cols2 = self.data_provider(mapping.sheet1_name, mapping.sheet2_name)
            
        def format_col(c):
            id_str, val_str = str(c[0]).strip(), str(c[1]).strip()
            has_header = c[2] if len(c) > 2 else False
            if has_header:
                return f"{id_str}     {val_str}"
            return id_str
            
        self.grid_cols.ignored_rows.clear()
        ignored_cells = []
        
        for r_idx, m in enumerate(mapping.column_mappings):
            if m.col1_idx >= 0 and cols1 and m.col1_idx < len(cols1):
                m.col1_name = format_col(cols1[m.col1_idx])
            if m.col2_idx >= 0 and cols2 and m.col2_idx < len(cols2):
                m.col2_name = format_col(cols2[m.col2_idx])
                
            is_key1 = False
            is_key2 = False
            if mapping.row_matching_mode == "key_based":
                for k in mapping.key_mappings:
                    if m.col1_idx in k.col1_indices:
                        is_key1 = True
                    if m.col2_idx in k.col2_indices:
                        is_key2 = True
            
            marker1 = "🔑 " if is_key1 else ""
            marker2 = "🔑 " if is_key2 else ""
            self._current_grid_data.append([marker1 + m.col1_name, marker2 + m.col2_name])
            if is_key1:
                ignored_cells.append((r_idx, 0))
            if is_key2:
                ignored_cells.append((r_idx, 1))

        if mapping.column_matching_mode == "manual":
            p_left = getattr(self, '_pending_left', None)
            p_right = getattr(self, '_pending_right', None)
            if (p_left or p_right) and not (p_left and p_right):
                l_val = ""
                r_val = ""
                if p_left:
                    if p_left[0] >= 0 and cols1 and p_left[0] < len(cols1):
                        l_val = format_col(cols1[p_left[0]])
                    else:
                        l_val = p_left[1]
                if p_right:
                    if p_right[0] >= 0 and cols2 and p_right[0] < len(cols2):
                        r_val = format_col(cols2[p_right[0]])
                    else:
                        r_val = p_right[1]
                        
                self._current_grid_data.append([l_val, r_val])
            
        self.grid_cols.set_data(self._current_grid_data, ["Spalte Links", "Spalte Rechts"])
        for r, c in ignored_cells:
            self.grid_cols.cell_formats[(r, c)] = "ignored"
        if ignored_cells:
            self.grid_cols.redraw()

    def receive_selection(self, side: int, col_idx: int, col_name: str):
        """Called from main.py when a column is clicked in the tree or grid."""
        if self.active_mapping_idx is None or self.active_mapping_idx >= len(self.sheet_mappings):
            return
            
        mapping = self.sheet_mappings[self.active_mapping_idx]
            
        if mapping.column_matching_mode != "manual":
            if side == 1:
                self.selected_left_idx = col_idx
            else:
                self.selected_right_idx = col_idx
                
            if self.on_cols_changed:
                self.on_cols_changed(side)
            return

        if not hasattr(self, '_editing_state'):
            self._editing_state = "none"
            self._pending_left = None
            self._pending_right = None

        if side == 1:
            left_val = (col_idx, col_name)
            if self._editing_state == "right" and self._pending_left and self._pending_right:
                self._pending_left = left_val
                self._pending_right = None
                self._editing_state = "left"
            else:
                if self._pending_left and self._pending_right:
                    self._remove_pending_from_mapping(mapping)
                
                self._pending_left = left_val
                self._editing_state = "left"
        else: # side == 2
            right_val = (col_idx, col_name)
            if self._editing_state == "left" and self._pending_left and self._pending_right:
                self._pending_left = None
                self._pending_right = right_val
                self._editing_state = "right"
            else:
                if self._pending_left and self._pending_right:
                    self._remove_pending_from_mapping(mapping)
                
                self._pending_right = right_val
                self._editing_state = "right"

        if self._pending_left and self._pending_right:
            self._add_to_mapping(mapping, self._pending_left, self._pending_right)
            
        self._refresh_col_list()
        if self.on_cols_changed:
            self.on_cols_changed(side)

    def _remove_pending_from_mapping(self, mapping):
        if not self._pending_left or not self._pending_right:
            return
        l_idx = self._pending_left[0]
        r_idx = self._pending_right[0]
        
        for m in mapping.column_mappings:
            if m.col1_idx == l_idx and m.col2_idx == r_idx:
                mapping.column_mappings.remove(m)
                break

    def _add_to_mapping(self, mapping, p_left, p_right):
        l_idx, l_name = p_left
        r_idx, r_name = p_right
        
        for m in mapping.column_mappings:
            if m.col1_idx == l_idx and m.col2_idx == r_idx:
                return
                
        mapping.column_mappings.append(ColumnMapping(l_name, r_name, l_idx, r_idx))

    def _del_key(self):
        if self.active_mapping_idx is None: return
        mapping = self.sheet_mappings[self.active_mapping_idx]
        
        selected_data = self.grid_cols.get_selected_rows_data()
        if not selected_data: return
        
        # Determine items to delete based on current grid values
        items_to_delete = []
        for row in selected_data:
            c1 = str(row[0]).replace("🔑 ", "")
            c2 = str(row[1]).replace("🔑 ", "")
            items_to_delete.append((c1, c2))
            
        # Handle case where user deletes an incomplete pending
        p_left = getattr(self, '_pending_left', None)
        p_right = getattr(self, '_pending_right', None)
        if (p_left or p_right) and not (p_left and p_right):
            # Check if selected row is the last one (the pending one)
            selected_rows = list(self.grid_cols.selected_rows)
            if selected_rows and selected_rows[0] >= len(mapping.column_mappings):
                self._pending_left = None
                self._pending_right = None
                self._editing_state = "none"
            
        # Filter out deleted items
        new_mappings = []
        for m in mapping.column_mappings:
            if (str(m.col1_name), str(m.col2_name)) not in items_to_delete:
                new_mappings.append(m)
            else:
                if p_left and p_right:
                    if p_left[0] == m.col1_idx and p_right[0] == m.col2_idx:
                        self._pending_left = None
                        self._pending_right = None
                        self._editing_state = "none"
                        
        mapping.column_mappings = new_mappings
        self._refresh_col_list()
        if self.on_cols_changed:
            self.on_cols_changed(0)

    def get_current_manual_indices(self, side: int) -> list[int]:
        if self.active_mapping_idx is None or self.active_mapping_idx >= len(self.sheet_mappings):
            return []
            
        mapping = self.sheet_mappings[self.active_mapping_idx]
            
        indices = []
        
        # 1. Add all multi-selected mapped rows from grid_cols
        if hasattr(self, 'grid_cols') and self.grid_cols.selected_rows:
            for r in self.grid_cols.selected_rows:
                if 0 <= r < len(mapping.column_mappings):
                    col_mapping = mapping.column_mappings[r]
                    idx = col_mapping.col1_idx if side == 1 else col_mapping.col2_idx
                    if idx >= 0 and idx not in indices:
                        indices.append(idx)
                        
        # 2. Identify the most recently selected index
        last_idx = -1
        if mapping.column_matching_mode == "manual":
            if hasattr(self, '_pending_left') and side == 1 and self._pending_left:
                last_idx = self._pending_left[0]
            elif side == 1 and self.selected_left_idx >= 0:
                last_idx = self.selected_left_idx
                
            if hasattr(self, '_pending_right') and side == 2 and self._pending_right:
                last_idx = self._pending_right[0]
            elif side == 2 and self.selected_right_idx >= 0:
                last_idx = self.selected_right_idx
        else:
            last_idx = self.selected_left_idx if side == 1 else self.selected_right_idx
            
        # Ensure the last_idx is at the very end of the list so main.py scrolls to it
        if last_idx >= 0:
            if last_idx in indices:
                indices.remove(last_idx)
            indices.append(last_idx)
            
        return indices
