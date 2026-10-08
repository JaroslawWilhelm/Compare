import tkinter as tk
from tkinter import ttk
from mapping_models import SheetMapping
from ui_components import ZoomManager
from grid_widget import ComplianceGrid

class SheetMappingView(tk.Frame):
    """
    Ansicht zum Zuordnen von Arbeitsblättern zwischen zwei Dateien.
    Beinhaltet links die Modus-Auswahl (als Checkboxen im Treeview) und 
    rechts eine performante Vorschau der zugeordneten Blätter.
    """
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, bg="#ffffff", *args, **kwargs)
        
        self.file1_name = "Datei 1"
        self.file2_name = "Datei 2"
        self.current_mode = "ModePositional"
        self.sheets1 = []
        self.sheets2 = []
        self.manual_mappings = []
        
        self._setup_ui()
        self.zoom_manager_left = ZoomManager(self.left_frame, zoom_id="sheet_mapping_panel")
        self.zoom_manager_right = ZoomManager(self.right_frame, zoom_id="sheet_mapping_grid")
        
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

        # Ein vertikaler PanedWindow für Links (Modus-Wahl Oben, Manuell-Panel Unten)
        self.left_paned = tk.PanedWindow(self.left_frame, orient=tk.VERTICAL, sashwidth=4, bd=0, bg="#dcdcdc")
        self.left_paned.pack(fill=tk.BOTH, expand=True)

        self.pane_options = tk.Frame(self.left_paned, bg="#ffffff")
        self.left_paned.add(self.pane_options, stretch="always", minsize=100)

        # Einheitlicher Header Links
        header_left = tk.Frame(self.pane_options, bg="#ffffff", pady=5)
        header_left.pack(fill=tk.X)
        tk.Label(header_left, text="Zuordnungsmodus", font=("Segoe UI", 11, "bold"), fg="#5f6368", bg="#ffffff").pack(side=tk.LEFT, padx=5)

        # Treeview für Optionen
        style = ttk.Style()
        style.configure("SheetMapping.Treeview", rowheight=32, font=("Segoe UI", 11), borderwidth=0, background="#ffffff", fieldbackground="#ffffff")
        style.layout("SheetMapping.Treeview", [('SheetMapping.Treeview.treearea', {'sticky': 'nswe'})]) # Remove borders

        self.tree_options = ttk.Treeview(self.pane_options, columns=("radio",), show="tree", style="SheetMapping.Treeview", height=4)
        self.tree_options.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.tree_options.column("#0", width=180, anchor="w", stretch=tk.NO)
        self.tree_options.column("radio", width=50, anchor="w", stretch=tk.YES)
        
        self.tree_options.tag_configure("even", foreground="#333333", background="#ffffff")
        self.tree_options.tag_configure("odd", foreground="#333333", background="#f4f5f7")
        self.tree_options.tag_configure("active_even", foreground="#0078D7", font=("Segoe UI", 11, "bold"), background="#ffffff")
        self.tree_options.tag_configure("active_odd", foreground="#0078D7", font=("Segoe UI", 11, "bold"), background="#f4f5f7")
        
        # Explizite Hover-Tags (verhindert Tkinter Tag-Konflikte)
        self.tree_options.tag_configure("hover_even", foreground="#333333", background="#e5f3ff")
        self.tree_options.tag_configure("hover_odd", foreground="#333333", background="#e5f3ff")
        self.tree_options.tag_configure("hover_active_even", foreground="#0078D7", font=("Segoe UI", 11, "bold"), background="#e5f3ff")
        self.tree_options.tag_configure("hover_active_odd", foreground="#0078D7", font=("Segoe UI", 11, "bold"), background="#e5f3ff")

        def _update_tags_fs(fs):
            for tag in ["active_even", "active_odd", "hover_active_even", "hover_active_odd"]:
                self.tree_options.tag_configure(tag, font=("Segoe UI", fs, "bold"))
            
            # Skaliere auch die Spaltenbreiten, damit der Text nicht überlappt
            ratio = fs / 11.0
            self.tree_options.column("#0", width=int(180 * ratio))
            self.tree_options.column("radio", width=int(50 * ratio))
            
        self.tree_options.update_tags_font_size = _update_tags_fs

        self.tree_options.bind("<Button-1>", self._on_tree_click)
        self.tree_options.bind("<Motion>", self._on_mouse_motion)
        self.tree_options.bind("<Leave>", self._on_mouse_leave)
        
        self._hovered_item = None
        
        self._populate_options()
        
        # ==========================================
        # RECHTER BEREICH: Vorschau
        # ==========================================
        self.right_frame = tk.Frame(self.paned, bg="#ffffff", width=10, height=10)
        self.right_frame.pack_propagate(False)
        self.right_frame.grid_propagate(False)
        self.paned.add(self.right_frame, stretch="always", minsize=280)
        
        header_right = tk.Frame(self.right_frame, bg="#ffffff", pady=5)
        header_right.pack(fill=tk.X)
        self.lbl_preview_title = tk.Label(header_right, text="Zugeordnet", font=("Segoe UI", 11, "bold"), fg="#5f6368", bg="#ffffff")
        self.lbl_preview_title.pack(side=tk.LEFT, padx=5)
        
        self.grid_preview = ComplianceGrid(self.right_frame, select_mode="row", show_index=False, show_xscroll=False, stretch_columns=True, zoom_id="sheet_mapping_grid")
        self.grid_preview.set_theme("light")
        self.grid_preview.header_context_menu_enabled = False
        self.grid_preview.index_context_menu_enabled = False
        self.grid_preview.header_row_index = None
        
        bottom_right = tk.Frame(self.right_frame, bg="#ffffff")
        bottom_right.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.separator = tk.Frame(bottom_right, height=4, bg="#dcdcdc")
        self.separator.pack(fill=tk.X, padx=0, pady=(0, 5))
        
        from ui_components import RoundedButton
        self.btn_del = RoundedButton(bottom_right, text="Auswahl Löschen", command=self._on_del_clicked, theme="primary", bg_light="#ffffff", bg_dark="#1e1e1e", fixed_width=130)
        self.btn_del.pack(side=tk.RIGHT, padx=5, pady=(0, 5))
        
        self.grid_preview.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Context-Menu
        self.context_menu = tk.Menu(self, tearoff=0)
        self.context_menu.add_command(label="Löschen", command=self._on_del_clicked)
        self.grid_preview.main_table.bind("<Button-3>", self._show_context_menu)
        self.grid_preview.index.bind("<Button-3>", self._show_context_menu)
        
        # Datenspeicher für das Grid
        self._current_grid_data = []

    def _show_context_menu(self, event):
        r, c = self.grid_preview.get_cell_from_coords(event.widget, event.x, event.y)
        if r is not None and 0 <= r < len(self._current_grid_data):
            if r not in self.grid_preview.selected_rows:
                self.grid_preview.selected_rows.clear()
                self.grid_preview.selected_rows.add(r)
                self.grid_preview.redraw()
            self.context_menu.post(event.x_root, event.y_root)

    def _get_tag_for_item(self, item_id, is_hovered):
        idx = self.tree_options.index(item_id)
        is_active = (self.current_mode == item_id)
        is_even = (idx % 2 == 0)
        
        if is_hovered:
            if is_active:
                return "hover_active_even" if is_even else "hover_active_odd"
            else:
                return "hover_even" if is_even else "hover_odd"
        else:
            if is_active:
                return "active_even" if is_even else "active_odd"
            else:
                return "even" if is_even else "odd"

    def _on_mouse_motion(self, event):
        item = self.tree_options.identify_row(event.y)
        if item != self._hovered_item:
            # Altes Hover entfernen
            if self._hovered_item and self.tree_options.exists(self._hovered_item):
                tag = self._get_tag_for_item(self._hovered_item, is_hovered=False)
                self.tree_options.item(self._hovered_item, tags=(tag,))
                
            # Neues Hover anwenden
            if item:
                tag = self._get_tag_for_item(item, is_hovered=True)
                self.tree_options.item(item, tags=(tag,))
                
            self._hovered_item = item

    def _on_mouse_leave(self, event):
        if self._hovered_item and self.tree_options.exists(self._hovered_item):
            tag = self._get_tag_for_item(self._hovered_item, is_hovered=False)
            self.tree_options.item(self._hovered_item, tags=(tag,))
        self._hovered_item = None

    def _on_tree_click(self, event):
        region = self.tree_options.identify_region(event.x, event.y)
        if region in ("cell", "tree"):
            item_id = self.tree_options.identify_row(event.y)
            if item_id and self.current_mode != item_id:
                self.current_mode = item_id
                self._populate_options()
                self._update_ui_state()
                self._generate_mappings()
        return "break"

    def _populate_options(self):
        for item in self.tree_options.get_children():
            self.tree_options.delete(item)
            
        options = [
            ("Positionell (1:1)", "ModePositional"),
            ("Manuell", "ModeManual"),
            ("Jedes gegen Jedes", "ModeCross"),
            ("Nach Namen", "ModeName")
        ]
        
        for index, (text, mode_id) in enumerate(options):
            is_active = (self.current_mode == mode_id)
            checkbox_char = "⬤" if is_active else "○"
            
            if is_active:
                tags = ("active_even",) if index % 2 == 0 else ("active_odd",)
            else:
                tags = ("even",) if index % 2 == 0 else ("odd",)
                
            # Text in die 1. Spalte (#0), Radiobox in die 2. Spalte ("radio")
            self.tree_options.insert("", "end", iid=mode_id, text=f"  {text}", values=(checkbox_char,), tags=tags)

    def set_files(self, filename1, filename2):
        self.file1_name = filename1
        self.file2_name = filename2
        
    def _update_ui_state(self):
        if getattr(self, 'on_manual_toggled', None):
            self.on_manual_toggled(self.current_mode == "ModeManual")
        
    def set_manual_selection(self, left_val=None, right_val=None):
        main_app = self.winfo_toplevel()
        if hasattr(main_app, '_current_tab_index') and main_app._current_tab_index != 3:
            return

        if self.current_mode != "ModeManual":
            return

        if not hasattr(self, '_editing_state'):
            self._editing_state = "none"
            self._pending_left = ""
            self._pending_right = ""

        if left_val is not None:
            if self._editing_state == "right" and self._pending_left and self._pending_right:
                self._pending_left = left_val
                self._pending_right = ""
                self._editing_state = "left"
            else:
                if self._pending_left and self._pending_right:
                    old_mapping = (self._pending_left, self._pending_right)
                    if old_mapping in self.manual_mappings:
                        self.manual_mappings.remove(old_mapping)
                
                self._pending_left = left_val
                self._editing_state = "left"

        if right_val is not None:
            if self._editing_state == "left" and self._pending_left and self._pending_right:
                self._pending_left = ""
                self._pending_right = right_val
                self._editing_state = "right"
            else:
                if self._pending_left and self._pending_right:
                    old_mapping = (self._pending_left, self._pending_right)
                    if old_mapping in self.manual_mappings:
                        self.manual_mappings.remove(old_mapping)
                
                self._pending_right = right_val
                self._editing_state = "right"

        if self._pending_left and self._pending_right:
            mapping = (self._pending_left, self._pending_right)
            if mapping not in self.manual_mappings:
                self.manual_mappings.append(mapping)
                
        self._generate_mappings()

    def refresh_data(self, sheets1, sheets2):
        self.sheets1 = sheets1
        self.sheets2 = sheets2
        self._generate_mappings()

    def _generate_mappings(self):
        self.clear_preview()
        
        if self.current_mode == "ModeManual":
            for s1, s2 in self.manual_mappings:
                self.add_preview_item(s1, s2)
                
            p_left = getattr(self, '_pending_left', "")
            p_right = getattr(self, '_pending_right', "")
            if (p_left or p_right) and not (p_left and p_right):
                self.add_preview_item(p_left, p_right)
                
        elif self.current_mode == "ModePositional":
            for s1, s2 in zip(self.sheets1, self.sheets2):
                self.add_preview_item(s1, s2)
                
        elif self.current_mode == "ModeCross":
            for s1 in self.sheets1:
                for s2 in self.sheets2:
                    self.add_preview_item(s1, s2)
                    
        elif self.current_mode == "ModeName":
            # Lookup dict (case-insensitive key mapping to the exact original case)
            s2_stripped = {str(s).strip().lower(): str(s) for s in self.sheets2}
            for s1 in self.sheets1:
                s1_clean = str(s1).strip()
                match = s2_stripped.get(s1_clean.lower())
                if match:
                    self.add_preview_item(s1, match)
                    
        self._apply_preview_data()

    def set_theme(self, theme):
        """Wird von main.py aufgerufen. Aktualisiert die Farben der eigenen Widgets."""
        is_dark = (theme == "dark")
        bg_main = "#1e1e1e" if is_dark else "#ffffff"
        bg_alt = "#252525" if is_dark else "#f4f5f7"
        bg_hover = "#3a3a3a" if is_dark else "#e5f3ff"
        fg_active = "#ffffff" if is_dark else "#0078D7"
        fg_text = "#e0e0e0" if is_dark else "#333333"

        self.config(bg=bg_main)

        style = ttk.Style()
        style.configure("SheetMapping.Treeview", background=bg_main, fieldbackground=bg_main, foreground=fg_text)
        
        self.tree_options.tag_configure("even", foreground=fg_text, background=bg_main)
        self.tree_options.tag_configure("odd", foreground=fg_text, background=bg_alt)
        self.tree_options.tag_configure("active_even", foreground=fg_active, background=bg_main)
        self.tree_options.tag_configure("active_odd", foreground=fg_active, background=bg_alt)
        
        self.tree_options.tag_configure("hover_even", foreground=fg_text, background=bg_hover)
        self.tree_options.tag_configure("hover_odd", foreground=fg_text, background=bg_hover)
        self.tree_options.tag_configure("hover_active_even", foreground=fg_active, background=bg_hover)
        self.tree_options.tag_configure("hover_active_odd", foreground=fg_active, background=bg_hover)

        if hasattr(self, 'grid_preview'):
            self.grid_preview.set_theme(theme)

        main_app = self.winfo_toplevel()
        if hasattr(main_app, '_apply_colors'):
            for child in self.winfo_children():
                main_app._apply_colors(child)
                
        bg_sash = "#555555" if is_dark else "#dcdcdc"
        if hasattr(self, 'separator'):
            self.separator.config(bg=bg_sash)

    def _on_add_clicked(self):
        pass

    def _on_del_clicked(self):
        selected_data = self.grid_preview.get_selected_rows_data()
        if not selected_data: return
        
        for row in selected_data:
            mapping = (row[0], row[1])
            if mapping in self.manual_mappings:
                self.manual_mappings.remove(mapping)
                
            p_left = getattr(self, '_pending_left', "")
            p_right = getattr(self, '_pending_right', "")
            if row[0] == p_left and row[1] == p_right:
                self._pending_left = ""
                self._pending_right = ""
                self._editing_state = "none"
                
        self._generate_mappings()

    def add_preview_item(self, sheet1, sheet2):
        self._current_grid_data.append([sheet1, sheet2])
        
    def clear_preview(self):
        self._current_grid_data = []

    def _apply_preview_data(self):
        self.grid_preview.set_data(self._current_grid_data, ["Sheet Links", "Sheet Rechts"])

    def get_sheet_mappings(self) -> list[SheetMapping]:
        """Returns the current list of mappings as SheetMapping objects.
        Preserves previously configured state (like row keys) for existing mappings."""
        
        # Get current pairs based on mode
        pairs = []
        if self.current_mode == "ModeManual":
            pairs = list(self.manual_mappings)
        elif self.current_mode == "ModePositional":
            pairs = list(zip(self.sheets1, self.sheets2))
        elif self.current_mode == "ModeCross":
            for s1 in self.sheets1:
                for s2 in self.sheets2:
                    pairs.append((s1, s2))
        elif self.current_mode == "ModeName":
            s2_stripped = {str(s).strip().lower(): str(s) for s in self.sheets2}
            for s1 in self.sheets1:
                s1_clean = str(s1).strip()
                match = s2_stripped.get(s1_clean.lower())
                if match:
                    pairs.append((s1, match))
                    
        # Preserve existing mapping objects if they exist
        existing = {}
        if hasattr(self, '_cached_mappings'):
            existing = {(m.sheet1_name, m.sheet2_name): m for m in self._cached_mappings}
            
        new_mappings = []
        for s1, s2 in pairs:
            if (s1, s2) in existing:
                new_mappings.append(existing[(s1, s2)])
            else:
                new_mappings.append(SheetMapping(s1, s2))
                
        self._cached_mappings = new_mappings
        return new_mappings

    def clear_cache(self):
        """Clears the mapping cache and manual overrides so that new file structures do not inherit old assignments."""
        self._cached_mappings = []
        self.manual_mappings = []
        self._pending_left = ""
        self._pending_right = ""
        self._editing_state = "none"
