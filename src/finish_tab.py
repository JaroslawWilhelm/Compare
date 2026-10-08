import tkinter as tk
from tkinter import ttk

class FinishTab(tk.Frame):
    def __init__(self, parent, on_start_comparison_callback=None, on_save_settings_callback=None):
        super().__init__(parent, bg="#f8f9fa")
        
        self.on_start_comparison_callback = on_start_comparison_callback
        self.on_save_settings_callback = on_save_settings_callback
        
        self.on_sheet_pair_selected = None
        self.on_cols_changed = None
        self._item_to_sheets = {}
        self._item_to_cols = {}
        
        self._tooltip_window = None
        
        # 1. Pack bottom frame FIRST so it always stays visible
        self.finish_btn_frame = tk.Frame(self, bg="#ffffff")
        self.finish_btn_frame.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.separator = tk.Frame(self.finish_btn_frame, height=4, bg="#dcdcdc")
        self.separator.pack(side=tk.TOP, fill=tk.X)
        
        content_frame = tk.Frame(self.finish_btn_frame, bg="#ffffff")
        content_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=15)
        
        self.text_frame = tk.Frame(content_frame, bg="#ffffff")
        self.text_frame.pack(side=tk.LEFT, fill=tk.Y)
        
        #self.lbl_abschluss_title = tk.Label(self.text_frame, text="Abschluss", font=("Segoe UI", 12, "bold"), fg="#5f6368", bg="#ffffff", anchor="w")
        #self.lbl_abschluss_title.pack(side=tk.TOP, fill=tk.X)
        
        #self.lbl_abschluss_desc = tk.Label(self.text_frame, text="", font=("Segoe UI", 10), fg="#444444", bg="#ffffff", anchor="w")
        #self.lbl_abschluss_desc.pack(side=tk.TOP, fill=tk.X, pady=(2,0))
        
        from ui_components import RoundedButton
        self.btn_save_settings = RoundedButton(content_frame, text="Einstellungen speichern", command=self.on_save_settings_callback, theme="primary", bg_light="#ffffff", bg_dark="#2d2d2d", fixed_width=200)
        self.btn_save_settings.pack(side=tk.RIGHT)
        
        self.btn_start_comparison = RoundedButton(content_frame, text="Vergleich starten", command=self.on_start_comparison_callback, theme="primary", bg_light="#ffffff", bg_dark="#2d2d2d", fixed_width=160)
        self.btn_start_comparison.pack(side=tk.RIGHT, padx=(0, 10))
        
        # 2. Pack summary frame SECOND so it takes the remaining space
        summary_frame = tk.Frame(self, bg="#f8f9fa")
        summary_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        self.tree = ttk.Treeview(summary_frame, columns=("value_col",), show="tree headings", selectmode="browse", style="Finish.Treeview")
        self.tree.heading("#0", text="Eigenschaft / Kategorie", anchor="w")
        self.tree.heading("value_col", text="Wert", anchor="w")
        self.tree.column("#0", width=350, stretch=True)
        self.tree.column("value_col", width=350, stretch=True)
        
        tree_scroll = ttk.Scrollbar(summary_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_scroll.set)
        
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.tree.bind("<Motion>", self._on_tree_motion)
        self.tree.bind("<Leave>", self._on_leave)
        
        self.tree.bind("<Control-MouseWheel>", self._on_zoom)
        self.tree.bind("<Control-Button-4>", self._on_zoom)
        self.tree.bind("<Control-Button-5>", self._on_zoom)
        
        self._tooltip_dict = {}
        self._hovered_item = None
        self._last_motion_time = 0
        self._zebra_cache = {}
        
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self.tree.bind("<ButtonRelease-1>", self._on_tree_click)
        
    def _on_tree_select(self, event):
        selected = self.tree.selection()
        if not selected: return
        item_id = selected[0]
        
        if getattr(self, '_item_to_sheets', None) and item_id in self._item_to_sheets:
            s1, s2 = self._item_to_sheets[item_id]
            if self.on_sheet_pair_selected:
                self.on_sheet_pair_selected(s1, s2, True)
                
        if self.on_cols_changed:
            self.after(50, lambda: self.on_cols_changed(0))

    def _on_tree_click(self, event):
        item_id = self.tree.identify_row(event.y)
        if not item_id: return
        
        if self.tree.selection() == (item_id,):
            if getattr(self, '_item_to_sheets', None) and item_id in self._item_to_sheets:
                s1, s2 = self._item_to_sheets[item_id]
                if self.on_sheet_pair_selected:
                    self.on_sheet_pair_selected(s1, s2, True)
                    
            if self.on_cols_changed:
                self.after(50, lambda: self.on_cols_changed(0))

    def get_current_selected_columns(self, side: int) -> list:
        selected = self.tree.selection()
        if not selected: return []
        item_id = selected[0]
        
        if getattr(self, '_item_to_cols', None) and item_id in self._item_to_cols:
            c1, c2 = self._item_to_cols[item_id]
            if side == 1 and c1 is not None and c1 >= 0: return [c1]
            if side == 2 and c2 is not None and c2 >= 0: return [c2]
        return []

    def _on_zoom(self, event):
        from ui_components import ZoomManager
        delta = 1 if (event.delta > 0 or getattr(event, 'num', 0) == 4) else -1
        current_zoom = ZoomManager.GLOBAL_STATES.get("finish_tree", 0)
        new_fs = 11 + current_zoom + delta
        if new_fs <= 6 and delta < 0: return
        if new_fs >= 30 and delta > 0: return
        
        ZoomManager.GLOBAL_STATES["finish_tree"] = current_zoom + delta
        
        if hasattr(self, 'current_theme'):
            self.set_theme(self.current_theme)

    def _on_tree_motion(self, event):
        import time
        now = time.time()
        if now - getattr(self, '_last_motion_time', 0) > 0.02:
            self._last_motion_time = now
            self._process_hover(event)

    def _process_hover(self, event):
        item_id = self.tree.identify_row(event.y)
        col = self.tree.identify_column(event.x)
        
        show_tooltip = False
        tooltip_text = ""
        
        if item_id and col:
            text = ""
            if col == '#0':
                text = self.tree.item(item_id, "text")
            else:
                try:
                    col_idx = int(col.replace('#', '')) - 1
                    values = self.tree.item(item_id, "values")
                    if 0 <= col_idx < len(values):
                        text = values[col_idx]
                except Exception:
                    pass
                    
            if text:
                import tkinter.font as tkfont
                bbox = self.tree.bbox(item_id, col)
                if bbox:
                    _, _, w, _ = bbox
                    
                    fs = 11
                    try:
                        from ui_components import ZoomManager
                        if "finish_tree" in ZoomManager.GLOBAL_STATES:
                            fs = 11 + ZoomManager.GLOBAL_STATES["finish_tree"]
                    except Exception:
                        pass
                        
                    tags = self.tree.item(item_id, "tags")
                    weight = "bold" if ("header" in tags or "sub" in tags) else "normal"
                    if "header" in tags:
                        fs += 1
                        
                    f = tkfont.Font(family="Segoe UI", size=fs, weight=weight)
                    
                    available_w = w
                    if col == '#0':
                        depth = 0
                        p = self.tree.parent(item_id)
                        while p:
                            depth += 1
                            p = self.tree.parent(p)
                        available_w = w - (depth * 20 + 25)
                        
                    if f.measure(str(text)) >= available_w:
                        show_tooltip = True
                        tooltip_text = text
                        
        if show_tooltip:
            if not getattr(self, '_tooltip_window', None):
                self._tooltip_current_text = tooltip_text
                self._show_tooltip(event, tooltip_text)
            else:
                if getattr(self, '_tooltip_current_text', None) != tooltip_text:
                    self._hide_tooltip()
                    self._tooltip_current_text = tooltip_text
                    self._show_tooltip(event, tooltip_text)
                else:
                    self._move_tooltip(event)
        else:
            self._hide_tooltip()
            
        if item_id != getattr(self, '_hovered_item', None):
            old_item = getattr(self, '_hovered_item', None)
            if old_item and self.tree.exists(old_item):
                tags = list(self.tree.item(old_item, "tags"))
                if "hover" in tags:
                    tags.remove("hover")
                    cached_zebra = self._zebra_cache.get(old_item)
                    if cached_zebra and cached_zebra not in tags:
                        tags.append(cached_zebra)
                    self.tree.item(old_item, tags=tags)
            
            if item_id:
                tags = list(self.tree.item(item_id, "tags"))
                if "hover" not in tags:
                    if "even_row" in tags:
                        self._zebra_cache[item_id] = "even_row"
                        tags.remove("even_row")
                    elif "odd_row" in tags:
                        self._zebra_cache[item_id] = "odd_row"
                        tags.remove("odd_row")
                        
                    tags.append("hover")
                    self.tree.item(item_id, tags=tags)
            self._hovered_item = item_id

    def _on_leave(self, event):
        self._hide_tooltip()
        old_item = getattr(self, '_hovered_item', None)
        if old_item and self.tree.exists(old_item):
            tags = list(self.tree.item(old_item, "tags"))
            if "hover" in tags:
                tags.remove("hover")
                cached_zebra = self._zebra_cache.get(old_item)
                if cached_zebra and cached_zebra not in tags:
                    tags.append(cached_zebra)
                self.tree.item(old_item, tags=tags)
        self._hovered_item = None

    def _show_tooltip(self, event, text):
        if getattr(self, '_tooltip_window', None):
            self._hide_tooltip()
            
        self._tooltip_window = tk.Toplevel(self)
        self._tooltip_window.wm_overrideredirect(True)
        
        lbl = tk.Label(self._tooltip_window, text=str(text), justify='left',
                      background="#ffffe0", fg="#000000", relief='solid', borderwidth=1,
                      font=("Segoe UI", 9))
        lbl.pack()
        
        x = event.x_root + 15
        y = event.y_root + 15
        self._tooltip_window.wm_geometry(f"+{x}+{y}")
        
    def _move_tooltip(self, event):
        if getattr(self, '_tooltip_window', None):
            x = event.x_root + 15
            y = event.y_root + 15
            self._tooltip_window.wm_geometry(f"+{x}+{y}")

    def _hide_tooltip(self, event=None):
        if getattr(self, '_tooltip_window', None):
            self._tooltip_window.destroy()
            self._tooltip_window = None

    def set_theme(self, current_theme):
        self.current_theme = current_theme
        style = ttk.Style()
        
        from ui_components import ZoomManager
        fs = 11 + ZoomManager.GLOBAL_STATES.get("finish_tree", 0)
        
        if current_theme == "dark":
            style.configure("Finish.Treeview", background="#1e1e1e", foreground="#cccccc", fieldbackground="#1e1e1e", font=("Segoe UI", fs), rowheight=int(fs * 2.2))
            style.configure("Finish.Treeview.Heading", background="#2d2d2d", foreground="#ffffff", font=("Segoe UI", fs, "bold"))
            style.map("Finish.Treeview", background=[('selected', '#3d3d3d')], foreground=[('selected', '#ffffff')])
            self.finish_btn_frame.config(bg="#2d2d2d")
            if hasattr(self, 'separator'):
                self.separator.config(bg="#444444")
            if hasattr(self, 'text_frame'):
                self.text_frame.config(bg="#2d2d2d")
                self.text_frame.master.config(bg="#2d2d2d")
            if hasattr(self, 'btn_start_comparison'):
                self.btn_start_comparison.set_theme("dark")
            if hasattr(self, 'btn_save_settings'):
                self.btn_save_settings.set_theme("dark")
            self.config(bg="#1e1e1e")
            self.tree.tag_configure("even_row", background="#1e1e1e")
            self.tree.tag_configure("odd_row", background="#252525")
            self.tree.tag_configure("header", foreground="#66b2ff", font=("Segoe UI", fs + 1, "bold"))
            self.tree.tag_configure("sub", foreground="#dddddd", font=("Segoe UI", fs, "bold"))
            self.tree.tag_configure("normal", foreground="#cccccc", font=("Segoe UI", fs))
            self.tree.tag_configure("hover", background="#004a77")
        else:
            style.configure("Finish.Treeview", background="#ffffff", foreground="#444444", fieldbackground="#ffffff", font=("Segoe UI", fs), rowheight=int(fs * 2.2))
            style.configure("Finish.Treeview.Heading", background="#e0e0e0", foreground="#333333", font=("Segoe UI", fs, "bold"))
            style.map("Finish.Treeview", background=[('selected', '#e6e6e6')], foreground=[('selected', '#000000')])
            self.finish_btn_frame.config(bg="#ffffff")
            if hasattr(self, 'separator'):
                self.separator.config(bg="#dcdcdc")
            if hasattr(self, 'text_frame'):
                self.text_frame.config(bg="#ffffff")
                self.text_frame.master.config(bg="#ffffff")
            if hasattr(self, 'btn_start_comparison'):
                self.btn_start_comparison.set_theme("light")
            if hasattr(self, 'btn_save_settings'):
                self.btn_save_settings.set_theme("light")
            self.config(bg="#f8f9fa")
            self.tree.tag_configure("even_row", background="#ffffff")
            self.tree.tag_configure("odd_row", background="#f4f5f7")
            self.tree.tag_configure("header", foreground="#0b57d0", font=("Segoe UI", fs + 1, "bold"))
            self.tree.tag_configure("sub", foreground="#333333", font=("Segoe UI", fs, "bold"))
            self.tree.tag_configure("normal", foreground="#444444", font=("Segoe UI", fs))
            self.tree.tag_configure("hover", background="#E5F3FF")

    def update_summary(self, app):
        """
        app is the main Application instance. We extract the needed data from it.
        """
        self.tree.delete(*self.tree.get_children())
        self._tooltip_dict.clear()
        
        self.current_header_id = None
        self.current_sub_id = None
        self._row_counter = 0
        
        self._item_to_sheets = {}
        self._item_to_cols = {}
        
        def strip_prefix(name):
            import re
            if isinstance(name, str):
                return re.sub(r'^[A-Z]+(?:[:]\s*|\s{2,})', '', name)
            if isinstance(name, list):
                return [strip_prefix(n) for n in name]
            if isinstance(name, tuple):
                return tuple(strip_prefix(n) for n in name)
            return name
        
        def add_header(text):
            self._row_counter += 1
            z_tag = "even_row" if self._row_counter % 2 == 0 else "odd_row"
            self.current_header_id = self.tree.insert("", tk.END, text=text, tags=("header", z_tag), open=True)
            self.current_sub_id = None
            return self.current_header_id
            
        def add_sub(text):
            self._row_counter += 1
            z_tag = "even_row" if self._row_counter % 2 == 0 else "odd_row"
            parent = self.current_header_id if self.current_header_id else ""
            self.current_sub_id = self.tree.insert(parent, tk.END, text=text, tags=("sub", z_tag), open=True)
            return self.current_sub_id
            
        def add_norm(text):
            self._row_counter += 1
            z_tag = "even_row" if self._row_counter % 2 == 0 else "odd_row"
            parent = self.current_sub_id if self.current_sub_id else (self.current_header_id if self.current_header_id else "")
            return self.tree.insert(parent, tk.END, text=text, tags=("normal", z_tag))
            
        def add_spacer():
            pass # In the treeview we do not necessarily need empty lines
            
        self.set_theme(app.current_theme)
        
        # GLOBALE PROJEKTINFORMATIONEN
        def val_or_dash(val):
            return str(val) if val and str(val).strip() else "-"
            
        def add_table_row(key, value, extra_tags=None):
            parent = self.current_sub_id if self.current_sub_id else (self.current_header_id if self.current_header_id else "")
            
            self._row_counter += 1
            z_tag = "even_row" if self._row_counter % 2 == 0 else "odd_row"
            
            if extra_tags:
                tags = [z_tag]
                tags.extend(extra_tags)
            else:
                tags = ["normal", z_tag]
                
            if not key and value:
                # E.g. for column assignments where key is empty
                item_id = self.tree.insert(parent, tk.END, text="", values=(str(value),), tags=tuple(tags))
            else:
                item_id = self.tree.insert(parent, tk.END, text=str(key), values=(str(value),), tags=tuple(tags))
            return item_id
            
        def add_color_row(key, hex_color):
            if isinstance(hex_color, (tuple, list)) and len(hex_color) >= 3:
                hex_color = f"#{int(hex_color[0]):02x}{int(hex_color[1]):02x}{int(hex_color[2]):02x}"
                
            if not hex_color or not str(hex_color).startswith('#'):
                add_table_row(key, val_or_dash(hex_color))
                return
            
            color_tag = f"color_{hex_color.replace('#', '')}"
            self.tree.tag_configure(color_tag, foreground=hex_color)
            add_table_row(key, f"⬤ {hex_color}", extra_tags=[color_tag])
            
        add_header("Allgemeine Projektinformationen")
        # Da diese in der Regel für beide Dateien synchronisiert werden, reicht der Wert von config1
        add_table_row("Benutzer / Prüfer", val_or_dash(app.config1.user_name))
        add_table_row("Projekt / Kontext", val_or_dash(app.config1.project_id))
        add_spacer()
        
        # TAB 1: DATEI-IMPORT
        add_header("1. Datei-Import")
        
        f1_path = val_or_dash(app.v_list1.file_path if getattr(app, 'v_list1', None) else None)
        add_sub("Ziel-Datei (Target / Left)")
        add_table_row("Dateipfad", f1_path)
        add_table_row("Hash (SHA-256)", val_or_dash(app.config1.file_hash))
        add_table_row("Encoding", val_or_dash(app.config1.encoding))
        if app.config1.file_type != "Excel":
            add_table_row("Trennzeichen", val_or_dash(app.config1.delimiter))
            add_table_row("Text-Quote", val_or_dash(app.config1.quote_char))
        add_spacer()
        
        f2_path = val_or_dash(app.v_list2.file_path if getattr(app, 'v_list2', None) else None)
        add_sub("Ist-Datei (Actual / Right)")
        add_table_row("Dateipfad", f2_path)
        add_table_row("Hash (SHA-256)", val_or_dash(app.config2.file_hash))
        add_table_row("Encoding", val_or_dash(app.config2.encoding))
        if app.config2.file_type != "Excel":
            add_table_row("Trennzeichen", val_or_dash(app.config2.delimiter))
            add_table_row("Text-Quote", val_or_dash(app.config2.quote_char))
        add_spacer()

        # TAB 2: DATEN-STRUKTUR
        add_header("2. Datenstruktur")
        for i, (v_list, config) in enumerate([(getattr(app, 'v_list1', None), app.config1), (getattr(app, 'v_list2', None), app.config2)]):
            file_lbl = "Ziel-Datei (Target / Left)" if i == 0 else "Ist-Datei (Actual / Right)"
            add_sub(file_lbl)
            if not v_list:
                add_norm("Keine Daten geladen.")
                add_spacer()
                continue
                
            # Formate (Global für die Datei)
            add_table_row("Dezimaltrennzeichen", val_or_dash(config.decimal_separator))
            add_table_row("Tausendertrennzeichen", val_or_dash(config.thousands_separator))
            
            # Runden Logic
            if config.rounding_decimal_places is None:
                rounding = "Aus"
            else:
                method = "Aufrunden"
                if getattr(config, 'rounding_method', 'HALF_EVEN') == "FLOOR": method = "Abrunden"
                elif getattr(config, 'rounding_method', 'HALF_EVEN') == "HALF_EVEN": method = "Gerade Zahl bleibt"
                rounding = f"{config.rounding_decimal_places} Stellen ({method})"
            add_table_row("Runden auf Stellen", rounding)
            
            add_table_row("Zeitzone (IANA)", val_or_dash(config.timezone))
            add_table_row("Leerzeichen trimmen", "Ja" if config.trim_whitespace else "Nein")
            add_table_row("Groß-/Kleinschreibung ign.", "Ja" if config.case_insensitive else "Nein")
            add_table_row("Umlaute normalisieren", "Ja" if config.normalize_umlauts else "Nein")
            
            add_table_row("Als 'Leer' (NULL) behandeln", val_or_dash(config.na_values))
            add_table_row("Als 'Wahr' behandeln", val_or_dash(config.true_values))
            add_table_row("Als 'Falsch' behandeln", val_or_dash(config.false_values))
            
            add_color_row("Farbe: True", config.color_true)
            add_color_row("Farbe: False", config.color_false)
            add_color_row("Farbe: Nicht vergleichbar", config.color_not_comp)
            add_color_row("Farbe: Anzahl unterschiedl.", config.color_count_diff)
            
            add_spacer()
            
            sheets = [s["name"] for s in getattr(v_list, 'sheets_info', [])]
            for s in sheets:
                if len(sheets) > 1 or s != "default":
                    add_sub(f"Arbeitsblatt '{s}'")
                
                has_hdr = config.get_has_header(s)
                header_val = str(config.get_header_row(s)) if has_hdr else "-"
                end_row = config.get_data_end_row(s)
                end_str = str(end_row) if end_row > 0 else "-"
                
                add_table_row("Nummer Kopfzeile", header_val)
                add_table_row("Start Datenzeile", str(config.get_data_start_row(s)))
                add_table_row("Ende Datenzeile", end_str)
                add_table_row("Spalten ignorieren", val_or_dash(config.get_ignore_columns(s)))
                add_table_row("Zeilen ignorieren", val_or_dash(config.get_ignore_rows(s)))
                add_spacer()

        # TAB 3: SPALTENTYPEN
        from type_detector import ColumnTypeDetector
        add_header("3. Spaltentypen")
        for i, (v_list, config, grid) in enumerate([(getattr(app, 'v_list1', None), app.config1, getattr(app, 'grid_left', None)), (getattr(app, 'v_list2', None), app.config2, getattr(app, 'grid_right', None))]):
            file_lbl = "Ziel-Datei (Target / Left)" if i == 0 else "Ist-Datei (Actual / Right)"
            add_sub(file_lbl)
            if not v_list:
                add_norm("Keine Daten geladen.")
                add_spacer()
                continue
                
            sheets = [s["name"] for s in getattr(v_list, 'sheets_info', [])]
            detector = ColumnTypeDetector(config)
            side = i + 1
            
            for s in sheets:
                col_types = None
                col_conf = {}
                col_is_auto = {}
                bounds = app.get_valid_data_bounds(side, s) if hasattr(app, 'get_valid_data_bounds') else None
                
                # Wenn aktives Sheet und Typen bereits ermittelt (inkl. manueller Änderungen durch den User)
                if hasattr(v_list, 'active_sheet_name') and v_list.active_sheet_name == s and getattr(grid, '_types_detected', False) and hasattr(grid, 'column_types'):
                    col_types = grid.column_types
                    col_conf = getattr(grid, 'column_confidences', {})
                    col_is_auto = getattr(grid, 'column_is_auto', {})
                else:
                    # Im Hintergrund erkennen
                    prev_active = getattr(v_list, 'active_sheet_name', None)
                    if hasattr(v_list, 'set_active_sheet'):
                        v_list.set_active_sheet(s)
                    try:
                        col_types, _, col_conf, _ = detector.detect_column_types(v_list, s, bounds=bounds)
                        col_is_auto = {c: True for c in col_types} if col_types else {}
                    except Exception:
                        pass
                    if hasattr(v_list, 'set_active_sheet') and prev_active:
                        v_list.set_active_sheet(prev_active)
                        
                if len(sheets) > 1 or s != "default":
                    add_sub(f"Arbeitsblatt '{s}'")
                        
                if col_types and bounds:
                    for col_idx, col_info in enumerate(bounds.get("columns", [])):
                        ident, val, has_hdr, is_ign = col_info
                        col_name = strip_prefix(val if val else ident)
                        
                        t = col_types.get(col_idx, "Text")
                        is_auto = col_is_auto.get(col_idx, True)
                        conf = col_conf.get(col_idx, "100%")
                        
                        if is_auto:
                            t = f"Auto: {t}"
                            
                        if isinstance(conf, str):
                            if conf != "100%":
                                t = f"⚠️ {t} ({conf})"
                            else:
                                t = f"✓ {t} (100%)"
                        else:
                            if conf < 100.0:
                                t = f"⚠️ {t} ({conf:g}%)"
                            else:
                                t = f"✓ {t} (100%)"
                        
                        if is_ign:
                            t = f"{t} (Ignoriert)"
                            
                        item_id = add_table_row(col_name, t)
                        if side == 1:
                            self._item_to_cols[item_id] = (col_idx, None)
                            self._item_to_sheets[item_id] = (s, None)
                        else:
                            self._item_to_cols[item_id] = (None, col_idx)
                            self._item_to_sheets[item_id] = (None, s)
                elif col_types:
                    for col_idx, t in col_types.items():
                        item_id = add_table_row(f"Spalte {col_idx+1}", t)
                        if side == 1:
                            self._item_to_cols[item_id] = (col_idx, None)
                            self._item_to_sheets[item_id] = (s, None)
                        else:
                            self._item_to_cols[item_id] = (None, col_idx)
                            self._item_to_sheets[item_id] = (None, s)
                else:
                    add_table_row("Status", "Konnte nicht ermittelt werden")
            add_spacer()

        # TAB 4: MAPPINGS
        add_header("4. Arbeitsblätter zuordnen")
        if hasattr(app, 'tab_mapping'):
            mappings = getattr(app.tab_mapping, '_cached_mappings', [])
            if not mappings and hasattr(app.tab_mapping, 'get_sheet_mappings'):
                mappings = app.tab_mapping.get_sheet_mappings()
            
            if not mappings:
                add_table_row("Status", "Keine Zuordnungen definiert.")
            else:
                for idx, m in enumerate(mappings):
                    s_t = getattr(m, 'sheet1_name', '(Nicht zugeordnet)')
                    s_a = getattr(m, 'sheet2_name', '(Nicht zugeordnet)')
                    
                    import os
                    file1 = os.path.basename(app.v_list1.file_path) if getattr(app, 'v_list1', None) and app.v_list1.file_path else "Target-Datei"
                    file2 = os.path.basename(app.v_list2.file_path) if getattr(app, 'v_list2', None) and app.v_list2.file_path else "Actual-Datei"
                    
                    sub_id = add_sub(f"Zuordnung {idx+1}")
                    self._item_to_sheets[sub_id] = (s_t, s_a)
                    item1 = add_table_row(file1, s_t)
                    self._item_to_sheets[item1] = (s_t, s_a)
                    item2 = add_table_row(file2, s_a)
                    self._item_to_sheets[item2] = (s_t, s_a)
        add_spacer()
                    
        # TAB 5: ZEILEN ZUORDNEN (KEYS)
        add_header("5. Zugeordnete Zeilen")
        if hasattr(app, 'tab_row_mapping'):
            mappings = getattr(app.tab_row_mapping, 'sheet_mappings', [])
            if not mappings:
                add_norm("Keine Zeilenzuordnungen definiert.")
            for idx, m in enumerate(mappings):
                s1 = getattr(m, 'sheet1_name', 'Unbekannt')
                s2 = getattr(m, 'sheet2_name', 'Unbekannt')
                
                row_mode = getattr(m, 'row_matching_mode', 'positional')
                mode_str = "Schlüssel" if row_mode == "key_based" else "Positionell"
                
                sub_id = add_sub(f"{s1} <-> {s2}")
                self._item_to_sheets[sub_id] = (s1, s2)
                item1 = add_table_row("  Modus", mode_str)
                self._item_to_sheets[item1] = (s1, s2)
                
                if row_mode == 'key_based':
                    keys_t = [k.col1_names for k in getattr(m, 'key_mappings', [])]
                    keys_a = [k.col2_names for k in getattr(m, 'key_mappings', [])]
                    
                    t_str = ", ".join(str(strip_prefix(k)) for k in keys_t if k)
                    a_str = ", ".join(str(strip_prefix(k)) for k in keys_a if k)
                    
                    item_tk = add_table_row("  • Target Keys", t_str if t_str else "Keine")
                    self._item_to_sheets[item_tk] = (s1, s2)
                    item_ak = add_table_row("  • Actual Keys", a_str if a_str else "Keine")
                    self._item_to_sheets[item_ak] = (s1, s2)
        add_spacer()

        # TAB 6: SPALTENZUORDNUNG
        add_header("6. Spaltenzuordnung")
        if hasattr(app, 'tab_column_mapping'):
            mappings = getattr(app.tab_column_mapping, 'sheet_mappings', [])
            if not mappings:
                add_table_row("Status", "Keine Spaltenzuordnungen definiert.")
            for idx, m in enumerate(mappings):
                s1 = getattr(m, 'sheet1_name', 'Unbekannt')
                s2 = getattr(m, 'sheet2_name', 'Unbekannt')
                col_mode = getattr(m, 'column_matching_mode', 'positional')
                mode_str = {'positional': 'Positionell', 'by_name': 'Nach Namen', 'cross_check': 'Cross-Check', 'manual': 'Manuell'}.get(col_mode, col_mode)
                
                cols = getattr(m, 'column_mappings', [])
                
                sub_id = add_sub(f"{s1} <-> {s2}")
                self._item_to_sheets[sub_id] = (s1, s2)
                
                if len(cols) == 0:
                    add_table_row(f"  Modus: {mode_str}", "Keine Spalten zugeordnet")
                else:
                    for col_map in cols:
                        item_id = add_table_row(f"  {strip_prefix(col_map.col1_name)} <-> {strip_prefix(col_map.col2_name)}", mode_str)
                        self._item_to_cols[item_id] = (col_map.col1_idx, col_map.col2_idx)
                        self._item_to_sheets[item_id] = (s1, s2)
                
                add_spacer()
                
        # TAB 7: VERGLEICHSLOGIK
        add_header("7. Vergleichslogik")
        if hasattr(app, 'tab_comparison'):
            mappings = getattr(app.tab_column_mapping, 'sheet_mappings', []) if hasattr(app, 'tab_column_mapping') else []
            if not mappings:
                add_table_row("Status", "Keine Vergleichslogik definiert.")
            for idx, m in enumerate(mappings):
                s1 = getattr(m, 'sheet1_name', 'Unbekannt')
                s2 = getattr(m, 'sheet2_name', 'Unbekannt')
                cols = getattr(m, 'column_mappings', [])
                
                if not cols:
                    continue
                    
                sub_id = add_sub(f"{s1} <-> {s2}")
                self._item_to_sheets[sub_id] = (s1, s2)
                
                for col_map in cols:
                    rule = getattr(col_map, 'rule', None)
                    method = "Äquivalent"
                    if rule:
                        is_equiv = getattr(rule, 'check_equivalent', False)
                        is_greater = getattr(rule, 'check_greater', False)
                        is_less = getattr(rule, 'check_less', False)
                        is_tol = getattr(rule, 'check_tolerance', False)
                        is_greater_eq = getattr(rule, 'check_greater_eq', False)
                        is_less_eq = getattr(rule, 'check_less_eq', False)
                        
                        if is_tol:
                            method = f"Toleranz (±{getattr(rule, 'tolerance_value', 0)})"
                        elif is_greater_eq:
                            method = "Größergleich"
                        elif is_less_eq:
                            method = "Kleinergleich"
                        elif is_greater:
                            method = "Größer"
                        elif is_less:
                            method = "Kleiner"
                        elif is_equiv:
                            method = "Äquivalent"
                        else:
                            method = "Keine Zuordnung"
                            
                    # Using two spaces for indentation
                    item_id = add_table_row(f"  {strip_prefix(col_map.col1_name)} <-> {strip_prefix(col_map.col2_name)}", method)
                    self._item_to_cols[item_id] = (col_map.col1_idx, col_map.col2_idx)
                    self._item_to_sheets[item_id] = (s1, s2)
                    
                add_spacer()
        # Treeview is read-only by default, nothing to disable
