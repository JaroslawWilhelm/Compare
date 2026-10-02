import tkinter as tk
from tkinter import ttk
import tkinter.font as tkfont
import bisect

class CanvasGridToolTip:
    def __init__(self, widget):
        self.widget = widget
        self.tw = None
        self.text = ""

    def show(self, text, x, y):
        if self.tw and self.text == text: return
        self.hide()
        self.text = text
        self.tw = tk.Toplevel(self.widget)
        self.tw.wm_overrideredirect(True)
        self.tw.wm_geometry(f"+{x+19}+{y+19}")
        
        label = tk.Label(self.tw, text=self.text, justify='left',
                         background="#ffffe0", relief='solid', borderwidth=1,
                         font=("Segoe UI", 11))
        label.pack(ipadx=1)

    def hide(self):
        if self.tw:
            self.tw.destroy()
        self.tw = None
        self.text = ""

class ComplianceGrid(tk.Frame):
    """
    A high-performance, read-only data grid engineered entirely from scratch, tailored
    specifically for GxP regulated application environments where data fidelity is paramount.
    
    ================ Architecture Principles ================
    1. Immutability (ALCOA+ standard): 
       Internal data (`self._data`) cannot be overwritten through the UI. There are no 
       "double-click to edit" functions. The grid strictly visualizes the backend source of truth.
       
    2. Virtual Rendering (Object Pool Viewport):
       A standard Tkinter component creates UI elements (Labels) for every row. If you load 
       100,000 rows, Tkinter crashes. This custom grid calculates exactly WHICH rows fit into 
       the current visible screen window and utilizes a high-performance "Object Pool" 
       to instantly reposition existing Canvas items instead of ever destroying them.
       
    3. The 4-Canvas "Frozen Pane" Architecture:
       Instead of one flat screen, the UI is split cleanly into 4 independent square canvases.
    """
    def __init__(self, parent, select_mode="cell", show_index=True, show_xscroll=True, show_horizontal_lines=True, show_vertical_lines=True, stretch_columns=False, **kwargs):
        self.zoom_id = kwargs.pop("zoom_id", None)
        super().__init__(parent, **kwargs)
        
        self.select_mode = select_mode
        self.show_index = show_index
        self.show_xscroll = show_xscroll
        self.show_horizontal_lines = show_horizontal_lines
        self.show_vertical_lines = show_vertical_lines
        self.stretch_columns = stretch_columns
        
        # ==========================================
        # 1. BASE LAYOUT & THEMES
        # ==========================================
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(1, weight=1)
        
        self.themes = {
            "light": {
                "bg_even": "#ffffff",          
                "bg_odd": "#f8f9fa",           
                "grid_color": "#e0e0e0",       
                "header_bg": "#f0f0f0",        
                "index_bg": "#f0f0f0",         
                "top_left_bg": "#d9d9d9",      
                "select_bg": "#D3E3FD",        
                "select_outline": "#0b57d0",   
                "text_fg": "#1f1f1f",          
                "header_fg": "#000000",        
                "diff_bg": "#ffe6e6",          
                "note_bg": "#fff3cd",          
                "header_row_bg": "#d1ecf1",
                "ignored_bg": "#f5f5f5",
                "ignored_fg": "#a0a0a0",
                "menu_bg": "#ffffff",
                "menu_fg": "#000000",
                "hover_bg": "#e5f3ff",
                "key_bg": "#d4edda",
            },
            "dark": {
                "bg_even": "#1e1e1e",
                "bg_odd": "#252525",
                "grid_color": "#333333",
                "header_bg": "#2d2d2d",
                "index_bg": "#2d2d2d",
                "top_left_bg": "#202020",
                "select_bg": "#004a77",
                "select_outline": "#4daafc",
                "text_fg": "#e0e0e0",
                "header_fg": "#ffffff",
                "diff_bg": "#5c1e1e",          
                "note_bg": "#5c4d1e",          
                "header_row_bg": "#004d40",
                "ignored_bg": "#282828",
                "ignored_fg": "#808080",
                "menu_bg": "#2b2b2b",
                "menu_fg": "#ffffff",
                "hover_bg": "#1e3d59",
                "key_bg": "#004a77",
            }
        }
        
        self.current_theme = "light"
        self.colors = self.themes[self.current_theme]
        
        self.font_family = "Segoe UI" if "Windows" in self.winfo_server() else "Arial"
        self.font_size = 12
        
        if self.zoom_id:
            from ui_components import ZoomManager
            if self.zoom_id in ZoomManager.GLOBAL_STATES:
                self.font_size = 12 + ZoomManager.GLOBAL_STATES[self.zoom_id]
                
        self.font = (self.font_family, self.font_size)
        self.font_italic = (self.font_family, self.font_size, "italic")
        self.header_font = (self.font_family, self.font_size, "bold")
        
        # ==========================================
        # 2. THE 4 CANVASES & OBJECT POOLS
        # ==========================================
        self.top_left = tk.Canvas(self, highlightthickness=0, width=50, height=25)
        self.header = tk.Canvas(self, highlightthickness=0, height=25)
        self.header.grid(row=0, column=1, sticky="nsew")
        
        self.index = tk.Canvas(self, highlightthickness=0, width=50)
        
        if self.show_index:
            self.top_left.grid(row=0, column=0, sticky="nsew")
            self.index.grid(row=1, column=0, sticky="nsew")
        
        self.main_table = tk.Canvas(self, highlightthickness=0)
        self.main_table.grid(row=1, column=1, sticky="nsew")

        # HIGH-PERFORMANCE OBJECT POOLS (Umgeht 'Wipe-and-Overdraw' Lags)
        self._resize_timer = None
        self._pool_main_rects = []
        self._pool_main_texts = []
        self._pool_header_rects = []
        self._pool_header_texts = []
        self._pool_index_rects = []
        self._pool_index_texts = []
        self._pool_main_vlines = []

        # Dediziertes Item für den Auswahl-Rahmen, das immer ganz oben liegt (z-index)
        self._sel_border_id = self.main_table.create_rectangle(0,0,0,0, outline=self.colors["select_outline"], width=2, state="hidden")
        
        self._apply_theme_colors()

        # ==========================================
        # 3. SCROLLBARS & EVENT BINDINGS
        # ==========================================
        self.yscroll = ttk.Scrollbar(self, orient="vertical", command=self._on_yscroll)
        self.yscroll.grid(row=1, column=2, sticky="ns")
        
        self.xscroll = ttk.Scrollbar(self, orient="horizontal", command=self._on_xscroll)
        if self.show_xscroll:
            self.xscroll.grid(row=2, column=1, sticky="ew")
        
        self.main_table.configure(yscrollcommand=self.yscroll.set, xscrollcommand=self.xscroll.set)
        
        for canvas in (self.main_table, self.index, self.header):
            canvas.bind("<MouseWheel>", self._on_mousewheel)
            canvas.bind("<Button-4>", self._on_mousewheel) 
            canvas.bind("<Button-5>", self._on_mousewheel) 
            
            canvas.bind("<Control-MouseWheel>", self._on_zoom)
            canvas.bind("<Control-Button-4>", self._on_zoom)
            canvas.bind("<Control-Button-5>", self._on_zoom)

        self.main_table.bind("<Button-1>", self._on_left_click)
        self.main_table.bind("<Button-3>", self._on_right_click) 
        self.main_table.bind("<Button-2>", self._on_right_click)
        self.main_table.bind("<B1-Motion>", self._on_main_drag)
        self.main_table.bind("<Motion>", self._on_main_motion)
        self.main_table.bind("<Leave>", self._on_main_leave)

        self._tooltip = CanvasGridToolTip(self)
        self._hovered_row = None

        self.header.bind("<Button-1>", self._on_header_click)
        self.header.bind("<Double-Button-1>", self._on_header_double_click) 
        self.header.bind("<Motion>", self._on_header_motion)
        self.header.bind("<B1-Motion>", self._on_header_drag)
        self.header.bind("<ButtonRelease-1>", self._on_header_release)
        self.header.bind("<Leave>", lambda e: self._tooltip.hide())
        
        self.index.bind("<Button-1>", self._on_index_click)
        self.index.bind("<Button-3>", self._on_index_right_click)
        self.index.bind("<Motion>", self._on_index_motion)
        self.index.bind("<B1-Motion>", self._on_index_drag)
        self.index.bind("<ButtonRelease-1>", self._on_index_release)

        # CORE RENDERING TRIGGER WITH DEBOUNCING
        self._resize_timer = None
        self._last_width = 0
        self._last_height = 0
        self.bind("<Configure>", self._on_resize_debounced)

        # ==========================================
        # 4. DATA & STATE VARIABLES
        # ==========================================
        self._data = []
        self._headers = []
        
        self.row_positions = [0] 
        self.col_positions = [0] 
        
        self.cell_formats = {}
        self.selected_cell = None  
        self.selected_cols = set() 
        self.key_cols = set()
        self.selected_rows = set() 
        
        self.column_types = {} # dict mapping col_idx to type string (e.g. "Text")
        self.column_is_auto = {} # dict mapping col_idx to boolean (True if auto-detected)
        self.column_ambiguous = {} # dict mapping col_idx to boolean
        self.column_confidences = {} # dict mapping col_idx to float (e.g. 100.0)
        self.validation_callback = None # Callback(col_idx, val) -> bool
        
        self.on_column_selected = None  # Callback for column selection
        self.on_type_changed = None # Callback for column type change
        self.on_header_row_changed = None # Callback for header row selection
        self.on_data_start_row_changed = None
        self.on_data_end_row_changed = None
        self.on_ignore_row_toggled = None
        self.on_ignore_col_toggled = None
        self.on_row_selected = None  # Callback(row_idx)

        
        self.header_row_index = 0
        self.data_start_row_index = 0
        self.data_end_row_index = 0
        self.ignored_rows = set()
        self.ignored_cols = set()
        
        self._rsz_col = None
        self._rsz_row = None
        self._drag_line = None
        self._user_resized_columns = False
        self._drag_start_row = None
        self._drag_start_col = None
        self._drag_original_selection = None
        
        # Setup context menu for column headers
        self.header_menu = tk.Menu(self, tearoff=0)
        self.available_types = ["Text", "Zahl", "Datum/Zeit", "Boolean"]
        for t in self.available_types:
            self.header_menu.add_command(label=t, command=lambda type_val=t: self._on_header_menu_select(type_val))
            
        self.header_context_menu_enabled = True
        self.index_context_menu_enabled = True
        self.header_menu_show_types = True
        self.header_menu_show_ignore = True
            
        self.header.bind("<Button-3>", self._on_header_right_click)

    # ==========================================
    # RESIZE DEBOUNCER (Anti Event Storm)
    # ==========================================
    def _on_resize_debounced(self, event):
        """
        Verhindert, dass das Grid beim fließenden Skalieren des Fensters 
        hunderte Male pro Sekunde neu berechnet wird (verhindert UI-Freeze).
        """
        # WICHTIG: Tkinter reicht Configure-Events von Kindern nach oben. 
        # Wir wollen nur reagieren, wenn sich das Haupt-Grid-Frame selbst ändert.
        if event.widget != self:
            return
            
        if event.width == self._last_width and event.height == self._last_height:
            return
            
        self._last_width = event.width
        self._last_height = event.height
        
        # Alten Timer abbrechen, solange der Nutzer die Maus noch zieht
        if self._resize_timer:
            self.after_cancel(self._resize_timer)
            
        # 150ms Wartezeit laut Best Practice
        self._resize_timer = self.after(150, self._sync_and_redraw)

    def _sync_and_redraw(self):
        """
        Führt den Redraw aus und zwingt Tkinter sofort danach, alle 4 Canvases
        absolut synchron auf den Monitor zu zeichnen (verhindert asynchrone Risse).
        """
        if self.stretch_columns and self._headers:
            w = self.main_table.winfo_width()
            if w > 10:
                if getattr(self, '_user_resized_columns', False) and self.col_positions and self.col_positions[-1] > 0:
                    old_w = self.col_positions[-1]
                    ratio = w / old_w
                    for i in range(1, len(self.col_positions)):
                        self.col_positions[i] = int(self.col_positions[i] * ratio)
                else:
                    num_cols = len(self._headers)
                    col_w = w / num_cols
                    self.col_positions = [int(i * col_w) for i in range(num_cols + 1)]
                self._update_scrollregions()
                
        self.redraw()
        
    # ==========================================
    # THEMES (Dark / Light Mode)
    # ==========================================
    def set_theme(self, theme_name: str):
        if theme_name in self.themes:
            self.current_theme = theme_name
            self.colors = self.themes[theme_name]
            self._apply_theme_colors()
            self.redraw()
            
    def _apply_theme_colors(self):
        self.config(bg=self.colors["top_left_bg"])
        self.top_left.config(bg=self.colors["top_left_bg"])
        self.header.config(bg=self.colors["header_bg"])
        self.index.config(bg=self.colors["index_bg"])
        self.main_table.config(bg=self.colors["bg_even"])
        self.main_table.itemconfig(self._sel_border_id, outline=self.colors["select_outline"])
        
        if hasattr(self, "header_menu"):
            self.header_menu.config(
                bg=self.colors["menu_bg"], 
                fg=self.colors["menu_fg"], 
                activebackground=self.colors["select_outline"], 
                activeforeground="#ffffff"
            )

    # ==========================================
    # ZOOM LOGIC (BUGFIX INTEGRATED)
    # ==========================================
    def _on_zoom(self, event):
        if not self._data: return
        
        delta = 1 if (event.delta > 0 or event.num == 4) else -1
        new_size = self.font_size + delta
        if not (6 <= new_size <= 30):
            return
            
        self.font_size = new_size
        self.font = (self.font_family, self.font_size)
        self.font_italic = (self.font_family, self.font_size, "italic")
        self.header_font = (self.font_family, self.font_size, "bold")
        scale = 1.1 if delta > 0 else (1 / 1.1)
        
        if self.zoom_id:
            from ui_components import ZoomManager
            ZoomManager.GLOBAL_STATES[self.zoom_id] = self.font_size - 12
        
        new_col_positions = [0]
        for i in range(len(self.col_positions) - 1):
            w = self.col_positions[i+1] - self.col_positions[i]
            new_col_positions.append(new_col_positions[-1] + max(20, int(round(w * scale))))
        self.col_positions = new_col_positions

        new_row_positions = [0]
        for i in range(len(self.row_positions) - 1):
            h = self.row_positions[i+1] - self.row_positions[i]
            new_row_positions.append(new_row_positions[-1] + max(20, int(round(h * scale))))
        self.row_positions = new_row_positions
        
        self._update_scrollregions()
        self.redraw()

    # ==========================================
    # SCROLL SYNCHRONIZATION
    # ==========================================
    def _on_yscroll(self, *args):
        self.main_table.yview(*args)
        self.index.yview(*args)
        self.redraw()

    def _on_xscroll(self, *args):
        self.main_table.xview(*args)
        self.header.xview(*args)
        self.redraw()

    def _on_mousewheel(self, event):
        if event.num == 4 or event.delta > 0:
            scroll_amount = -1
        elif event.num == 5 or event.delta < 0:
            scroll_amount = 1
        else: return

        if event.state & 0x0001:
            x_state = self.xscroll.get()
            if x_state and x_state[0] <= 0.0 and x_state[1] >= 1.0:
                self.main_table.xview_moveto(0)
                self.header.xview_moveto(0)
                return
            self.main_table.xview_scroll(scroll_amount, "units")
            self.header.xview_scroll(scroll_amount, "units")
        else:
            y_state = self.yscroll.get()
            if y_state and y_state[0] <= 0.0 and y_state[1] >= 1.0:
                self.main_table.yview_moveto(0)
                self.index.yview_moveto(0)
                return
            self.main_table.yview_scroll(scroll_amount, "units")
            self.index.yview_scroll(scroll_amount, "units")
        self.redraw()

    # ==========================================
    # DATA MANAGEMENT & VIRTUAL RENDER ENGINE
    # ==========================================
    def _update_scrollregions(self):
        if self.row_positions and self.col_positions:
            total_w, total_h = int(self.col_positions[-1]), int(self.row_positions[-1])
            self.main_table.configure(scrollregion=(0, 0, total_w, total_h))
            self.index.configure(scrollregion=(0, 0, self.index.winfo_width(), total_h))
            self.header.configure(scrollregion=(0, 0, total_w, self.header.winfo_height()))

    def set_column_types(self, col_types: dict, col_ambiguous: dict = None, col_confidences: dict = None, col_date_formats: dict = None, col_is_auto: dict = None):
        self.column_types = col_types.copy()
        self.column_ambiguous = col_ambiguous.copy() if col_ambiguous else {}
        self.column_confidences = col_confidences.copy() if col_confidences else {}
        self.column_date_formats = col_date_formats.copy() if col_date_formats else {}
        self.column_is_auto = col_is_auto.copy() if col_is_auto else {}
        self._sync_and_redraw()

    def set_data(self, data, columns=None):
        if hasattr(data, 'values') and hasattr(data, 'columns'):
            self._data = data.values.tolist()
            self._headers = columns if columns is not None else data.columns.tolist()
        else:
            self._data = data
            self._headers = columns if columns is not None else [f"Col {i+1}" for i in range(len(data[0]) if data else 0)]

        num_rows, num_cols = len(self._data), len(self._headers)
        
        self.row_positions = [0]
        if isinstance(self._data, list) and num_rows < 5000:
            for r_idx in range(num_rows):
                max_lines = 1
                row = self._data[r_idx]
                for c_idx in range(num_cols):
                    try:
                        c_val = row[c_idx]
                    except IndexError:
                        break
                    if isinstance(c_val, str):
                        lines = c_val.count('\n') + 1
                        if lines > max_lines:
                            max_lines = lines
                self.row_positions.append(self.row_positions[-1] + (max_lines * 28))
        else:
            self.row_positions = [i * 28 for i in range(num_rows + 1)]
        
        if not getattr(self, '_user_resized_columns', False) or len(self.col_positions) != num_cols + 1:
            w = self.main_table.winfo_width()
            if self.stretch_columns and num_cols > 0 and w > 10:
                col_w = w / num_cols
                self.col_positions = [int(i * col_w) for i in range(num_cols + 1)]
            else:
                self.col_positions = [i * 120 for i in range(num_cols + 1)]
            self._user_resized_columns = False
        
        self.reset_types_state()
        self._clear_selection()
        self._update_scrollregions()
        
        # Bei neuen Daten Pools leeren und von Null beginnen, da Zellen radikal anders sein können.
        self._clear_pools()
        
        if not getattr(self, '_batch_updating', False):
            self.redraw()

    def get_state(self):
        if not self._headers: return None
        return {
            'col_positions': self.col_positions,
            'user_resized': getattr(self, '_user_resized_columns', False)
        }

    def set_state(self, state):
        if not state: return
        self.col_positions = state.get('col_positions', self.col_positions)
        self._user_resized_columns = state.get('user_resized', False)
        self._update_scrollregions()
        self.redraw()

    def set_user_resized(self, val: bool):
        self._user_resized_columns = val

    def reset_types_state(self):
        self.column_types.clear()
        self.column_is_auto.clear()
        self.column_ambiguous.clear()
        self.column_confidences.clear()
        if hasattr(self, 'column_date_formats'):
            self.column_date_formats.clear()
        self.cell_formats.clear()
        self._types_detected = False

    def _clear_pools(self):
        """Löscht ausnahmsweise alle Pools, wenn komplett neue Daten geladen werden."""
        for c in (self.main_table, self.index, self.header):
            c.delete("all")
        self._pool_main_rects.clear()
        self._pool_main_texts.clear()
        self._pool_header_rects.clear()
        self._pool_header_texts.clear()
        self._pool_index_rects.clear()
        self._pool_index_texts.clear()
        self._pool_main_vlines.clear()
        self._sel_border_id = self.main_table.create_rectangle(0,0,0,0, outline=self.colors["select_outline"], width=2, state="hidden")

    def format_cell(self, row, col, format_type="diff"):
        self.cell_formats[(row, col)] = format_type
        self.redraw()

    def _get_font_obj(self, font_tuple):
        if not hasattr(self, '_font_cache'):
            self._font_cache = {}
        if font_tuple not in self._font_cache:
            self._font_cache[font_tuple] = tkfont.Font(font=font_tuple)
        return self._font_cache[font_tuple]

    def _truncate_text(self, text, font_tuple, max_width):
        if max_width <= 0:
            return ""
            
        if "\n" in text:
            return "\n".join(self._truncate_text(line, font_tuple, max_width) for line in text.split("\n"))
            
        font_obj = self._get_font_obj(font_tuple)
        if font_obj.measure(text) <= max_width:
            return text
            
        avg_char_w = max(1, font_obj.measure("W"))
        est_chars = max(1, max_width // avg_char_w)
        
        # Start a bit larger in case of narrow characters
        candidate = text[:est_chars + 3]
        
        while len(candidate) > 0 and font_obj.measure(candidate + "...") > max_width:
            candidate = candidate[:-1]
            
        if not candidate:
            return text[:max(1, est_chars)]
            
        return candidate + "..."

    def get_visible_area(self):
        x1, y1 = self.main_table.canvasx(0), self.main_table.canvasy(0)
        x2, y2 = x1 + self.main_table.winfo_width(), y1 + self.main_table.winfo_height()

        if not self.row_positions or not self.col_positions:
            return 0, 0, 0, 0

        from_col = max(0, bisect.bisect_right(self.col_positions, x1) - 1)
        upto_col = min(len(self._headers), len(self.col_positions) - 1, bisect.bisect_left(self.col_positions, x2))
        from_row = max(0, bisect.bisect_right(self.row_positions, y1) - 1)
        upto_row = min(len(self._data), len(self.row_positions) - 1, bisect.bisect_left(self.row_positions, y2))
        
        return from_row, upto_row, from_col, upto_col

    def redraw(self):

        """
        The core engine - HIGH PERFORMANCE POOLING.
        Instead of canvas.delete("all"), this re-uses existing bounding boxes.
        No flickering, zero tearing during window resize.
        """
        from_row, upto_row, from_col, upto_col = self.get_visible_area()

        rows_to_draw = list(range(from_row, upto_row))
        frozen_row = None
        if self.header_row_index is not None and 0 <= self.header_row_index < len(self._data):
            if self.row_positions[self.header_row_index] < self.main_table.canvasy(0):
                frozen_row = self.header_row_index
                if frozen_row not in rows_to_draw:
                    rows_to_draw.append(frozen_row)
                else:
                    rows_to_draw.remove(frozen_row)
                    rows_to_draw.append(frozen_row)

        # --- 1. Main Table (Object Pool Application) ---
        rect_idx = 0
        for r in rows_to_draw:
            if r == frozen_row:
                h = self.row_positions[r+1] - self.row_positions[r]
                y1 = self.main_table.canvasy(0)
                y2 = y1 + h
            else:
                y1, y2 = self.row_positions[r], self.row_positions[r+1]
            
            row_text_fg = self.colors["text_fg"]
            if r == self.header_row_index:
                base_bg = self.colors["header_row_bg"]
            elif r < self.data_start_row_index or (self.data_end_row_index > 0 and r >= self.data_end_row_index) or r in self.ignored_rows:
                base_bg = self.colors["ignored_bg"]
                row_text_fg = self.colors["ignored_fg"]
            else:
                base_bg = self.colors["bg_even"] if r % 2 == 0 else self.colors["bg_odd"]
                
            for c in range(from_col, upto_col):
                x1, x2 = self.col_positions[c], self.col_positions[c+1]
                
                val = str(self._data[r][c])
                is_ignored_cell = (
                    r == self.header_row_index or 
                    r < self.data_start_row_index or 
                    (self.data_end_row_index > 0 and r >= self.data_end_row_index) or 
                    r in self.ignored_rows or 
                    c in self.ignored_cols
                )
                
                is_invalid = False
                if not is_ignored_cell and self.validation_callback and c in self.column_types:
                    is_invalid = not self.validation_callback(c, val)

                bg_color = base_bg
                cell_text_fg = row_text_fg
                cell_font = self.font
                
                if c in self.ignored_cols or r in self.ignored_rows:
                    bg_color = self.colors["ignored_bg"]
                    cell_text_fg = self.colors["ignored_fg"]
                    cell_font = self.font_italic
                
                if (r, c) in self.cell_formats:
                    f_type = self.cell_formats[(r, c)]
                    if f_type == "diff": bg_color = self.colors["diff_bg"]
                    elif f_type == "note": bg_color = self.colors["note_bg"]
                    elif f_type == "ignored":
                        bg_color = self.colors["ignored_bg"]
                        cell_text_fg = self.colors["ignored_fg"]
                        cell_font = self.font_italic
                elif is_invalid:
                    bg_color = "#ffcccc"
                    cell_text_fg = "#990000"
                elif c in self.key_cols:
                    bg_color = self.colors.get("key_bg", "#d4edda")
                elif self._hovered_row == r:
                    bg_color = self.colors["hover_bg"]
                
                if self.selected_cell == (r, c) or c in self.selected_cols or r in self.selected_rows:
                    bg_color = self.colors["select_bg"]
                
                text_y = y1 + ((y2 - y1) // 2)
                
                has_full_borders = self.show_horizontal_lines and self.show_vertical_lines
                
                if rect_idx < len(self._pool_main_rects):
                    # Update an existing box and text
                    r_id = self._pool_main_rects[rect_idx]
                    t_id = self._pool_main_texts[rect_idx]
                    self.main_table.coords(r_id, x1, y1, x2, y2)
                    self.main_table.itemconfig(r_id, outline=self.colors["grid_color"] if has_full_borders else "", fill=bg_color, state="normal")
                    self.main_table.coords(t_id, x1 + 5, text_y)
                    
                    display_val = self._truncate_text(val, cell_font, max(0, x2 - x1 - 10)) if c == len(self._headers) - 1 else val
                    
                    self.main_table.itemconfig(t_id, text=display_val, fill=cell_text_fg, font=cell_font, state="normal")
                else:
                    # Not enough items in pool, expand the pool
                    r_id = self.main_table.create_rectangle(x1, y1, x2, y2, outline=self.colors["grid_color"] if has_full_borders else "", fill=bg_color)
                    
                    display_val = self._truncate_text(val, cell_font, max(0, x2 - x1 - 10)) if c == len(self._headers) - 1 else val
                    
                    t_id = self.main_table.create_text(x1 + 5, text_y, text=display_val, anchor="w", font=cell_font, fill=cell_text_fg)
                    self._pool_main_rects.append(r_id)
                    self._pool_main_texts.append(t_id)
                    
                if r == frozen_row:
                    self.main_table.tag_raise(r_id)
                    self.main_table.tag_raise(t_id)
                rect_idx += 1

        # Hide any unused items left over in the pool
        for i in range(rect_idx, len(self._pool_main_rects)):
            self.main_table.itemconfig(self._pool_main_rects[i], state="hidden")
            self.main_table.itemconfig(self._pool_main_texts[i], state="hidden")
            
        # Draw custom vertical lines if horizontal lines are hidden, or if there is no data
        vline_idx = 0
        if (self.show_vertical_lines and not self.show_horizontal_lines) or (not self._data):
            vy1 = self.main_table.canvasy(0)
            vy2 = vy1 + self.main_table.winfo_height()
            
            for c in range(from_col, upto_col + 1):
                vx = self.col_positions[c]
                if vline_idx < len(self._pool_main_vlines):
                    l_id = self._pool_main_vlines[vline_idx]
                    self.main_table.coords(l_id, vx, vy1, vx, vy2)
                    self.main_table.itemconfig(l_id, state="normal", fill=self.colors["grid_color"])
                else:
                    l_id = self.main_table.create_line(vx, vy1, vx, vy2, fill=self.colors["grid_color"])
                    self._pool_main_vlines.append(l_id)
                self.main_table.tag_raise(l_id)
                vline_idx += 1
                
        for i in range(vline_idx, len(self._pool_main_vlines)):
            self.main_table.itemconfig(self._pool_main_vlines[i], state="hidden")

        # Focus Border
        if self.selected_cell and not self.selected_cols and not self.selected_rows:
            r, c = self.selected_cell
            if from_row <= r < upto_row and from_col <= c < upto_col:
                self.main_table.coords(self._sel_border_id, self.col_positions[c], self.row_positions[r], self.col_positions[c+1], self.row_positions[r+1])
                self.main_table.itemconfig(self._sel_border_id, state="normal")
                self.main_table.tag_raise(self._sel_border_id)
            else:
                self.main_table.itemconfig(self._sel_border_id, state="hidden")
        else:
            self.main_table.itemconfig(self._sel_border_id, state="hidden")

        # --- 2. Column Headers ---
        h_height = self.header.winfo_height() or 30
        h_idx = 0
        for c in range(from_col, upto_col):
            x1, x2 = self.col_positions[c], self.col_positions[c+1]
            
            header_fg = self.colors["header_fg"]
            
            if c in self.ignored_cols:
                bg_color = self.colors["ignored_bg"]
                header_fg = self.colors["ignored_fg"]
            elif c in self.key_cols:
                bg_color = self.colors.get("key_bg", "#d4edda")  # Theme-aware key columns
            else:
                bg_color = self.colors["select_bg"] if c in self.selected_cols else self.colors["header_bg"]
            
            c_type = self.column_types.get(c, "Text")
            header_text = f"{self._headers[c]}"
            truncated_header_text = self._truncate_text(header_text, self.header_font, max(0, x2 - x1 - 10))
            
            if h_idx < len(self._pool_header_rects):
                r_id = self._pool_header_rects[h_idx]
                t_id = self._pool_header_texts[h_idx]
                self.header.coords(r_id, x1, 0, x2, h_height)
                self.header.itemconfig(r_id, outline=self.colors["grid_color"], fill=bg_color, state="normal")
                self.header.coords(t_id, x1 + (x2 - x1) // 2, h_height // 2)
                self.header.itemconfig(t_id, text=truncated_header_text, font=self.header_font, fill=header_fg, state="normal", anchor="center")
            else:
                r_id = self.header.create_rectangle(x1, 0, x2, h_height, outline=self.colors["grid_color"], fill=bg_color)
                t_id = self.header.create_text(x1 + (x2 - x1) // 2, h_height // 2, text=truncated_header_text, anchor="center", font=self.header_font, fill=header_fg)
                self._pool_header_rects.append(r_id)
                self._pool_header_texts.append(t_id)
            h_idx += 1
            
        for i in range(h_idx, len(self._pool_header_rects)):
            self.header.itemconfig(self._pool_header_rects[i], state="hidden")
            self.header.itemconfig(self._pool_header_texts[i], state="hidden")

        # --- 3. Row Numbers (Index) ---
        i_width = self.index.winfo_width() or 50
        i_idx = 0
        for r in rows_to_draw:
            if r == frozen_row:
                h = self.row_positions[r+1] - self.row_positions[r]
                y1 = self.index.canvasy(0)
                y2 = y1 + h
            else:
                y1, y2 = self.row_positions[r], self.row_positions[r+1]
            
            row_idx_fg = self.colors["header_fg"]
            if r == self.header_row_index:
                bg_color = self.colors["header_row_bg"]
            elif r < self.data_start_row_index or (self.data_end_row_index > 0 and r >= self.data_end_row_index) or r in self.ignored_rows:
                bg_color = self.colors["ignored_bg"]
                row_idx_fg = self.colors["ignored_fg"]
            else:
                bg_color = self.colors["select_bg"] if r in self.selected_rows else self.colors["index_bg"]
            
            if i_idx < len(self._pool_index_rects):
                r_id = self._pool_index_rects[i_idx]
                t_id = self._pool_index_texts[i_idx]
                self.index.coords(r_id, 0, y1, i_width, y2)
                self.index.itemconfig(r_id, outline=self.colors["grid_color"], fill=bg_color, state="normal")
                self.index.coords(t_id, i_width // 2, y1 + ((y2 - y1) // 2))
                self.index.itemconfig(t_id, text=str(r+1), font=self.header_font, fill=row_idx_fg, state="normal")
            else:
                r_id = self.index.create_rectangle(0, y1, i_width, y2, outline=self.colors["grid_color"], fill=bg_color)
                t_id = self.index.create_text(i_width // 2, y1 + ((y2 - y1) // 2), text=str(r+1), anchor="center", font=self.header_font, fill=row_idx_fg)
                self._pool_index_rects.append(r_id)
                self._pool_index_texts.append(t_id)
            if r == frozen_row:
                self.index.tag_raise(r_id)
                self.index.tag_raise(t_id)
            i_idx += 1
            
        for i in range(i_idx, len(self._pool_index_rects)):
            self.index.itemconfig(self._pool_index_rects[i], state="hidden")
            self.index.itemconfig(self._pool_index_texts[i], state="hidden")
        
    # ==========================================
    # INTERACTIONS & GxP AUDIT TRAIL
    # ==========================================
    def _clear_selection(self):
        self.selected_cell = None
        self.selected_cols.clear()
        self.selected_rows.clear()

    def get_selected_rows_data(self):
        return [self._data[r] for r in self.selected_rows if 0 <= r < len(self._data)]


    def get_cell_from_coords(self, canvas, event_x, event_y):
        if not self._data: return None, None
        cx, cy = canvas.canvasx(event_x), canvas.canvasy(event_y)
        
        # Intercept frozen row clicks
        if self.header_row_index is not None and 0 <= self.header_row_index < len(self._data):
            if self.row_positions[self.header_row_index] < self.main_table.canvasy(0):
                h = self.row_positions[self.header_row_index+1] - self.row_positions[self.header_row_index]
                if cy < self.main_table.canvasy(0) + h:
                    r = self.header_row_index
                    c = bisect.bisect_right(self.col_positions, cx) - 1
                    return r, c
                    
        c = bisect.bisect_right(self.col_positions, cx) - 1
        r = bisect.bisect_right(self.row_positions, cy) - 1
        return r, c

    def _on_left_click(self, event):
        r, c = self.get_cell_from_coords(self.main_table, event.x, event.y)
        if r is None or c is None:
            return
            
        if 0 <= r < len(self._data) and 0 <= c < len(self._headers):
            # Block selection of ignored or out-of-bounds cells
            if c in self.ignored_cols or r in self.ignored_rows:
                return
            if r < self.data_start_row_index or (self.data_end_row_index > 0 and r >= self.data_end_row_index):
                return
            if r == self.header_row_index:
                return
                
            self._drag_start_row = r
            self._drag_start_col = c
            self._drag_original_selection = set(self.selected_rows) if self.select_mode == "row" else self.selected_cell
                
            if self.select_mode == "row":
                if event.state & 0x0004: # Control key
                    if r in self.selected_rows:
                        self.selected_rows.remove(r)
                    else:
                        self.selected_rows.add(r)
                else:
                    self._clear_selection()
                    self.selected_rows.add(r)
                self.redraw()
                if self.on_row_selected:
                    self.on_row_selected(r)
            else:
                self._clear_selection()
                self.selected_cell = (r, c)
                self.redraw()
                if self.on_column_selected:
                    self.on_column_selected(c, self._headers[c])

    def _on_right_click(self, event):
        r, c = self.get_cell_from_coords(self.main_table, event.x, event.y)
        if r is None or c is None:
            return
        if 0 <= r < len(self._data) and 0 <= c < len(self._headers):
            if self.select_mode == "row":
                if r not in self.selected_rows:
                    self._clear_selection()
                    self.selected_rows.add(r)
            else:
                self._clear_selection()
                self.selected_cell = (r, c)
            self.redraw()
            menu = tk.Menu(self, tearoff=0, bg=self.colors["menu_bg"], fg=self.colors["menu_fg"], 
                           activebackground=self.colors["select_outline"], activeforeground="#ffffff")
            menu.add_command(label="Attach note / evidence (Audit Trail)", command=lambda: self._trigger_audit_note(r, c))
            menu.tk_popup(event.x_root, event.y_root)

    def _trigger_audit_note(self, row, col):
        self.format_cell(row, col, "note")

    def _on_main_drag(self, event):
        self._handle_drag_selection(self.main_table, event.x, event.y, event.state)

    def _handle_drag_selection(self, widget, x, y, state):
        if not hasattr(self, '_drag_start_row') or self._drag_start_row is None:
            return
            
        r, _ = self.get_cell_from_coords(widget, x, y)
        if r is None:
            return
            
        if 0 <= r < len(self._data):
            if self.select_mode == "row":
                new_selection = set(self._drag_original_selection) if self._drag_original_selection and (state & 0x0004) else set()
                min_r, max_r = min(self._drag_start_row, r), max(self._drag_start_row, r)
                
                for row_idx in range(min_r, max_r + 1):
                    if row_idx in self.ignored_rows: continue
                    if row_idx < self.data_start_row_index or (self.data_end_row_index > 0 and row_idx >= self.data_end_row_index): continue
                    if row_idx == self.header_row_index: continue
                    if state & 0x0004 and row_idx in new_selection and row_idx != r and row_idx != self._drag_start_row:
                        pass # if it was already selected and Ctrl is pressed, do we toggle? 
                        # simpler logic for drag: just add them to selection
                    new_selection.add(row_idx)
                    
                if self.selected_rows != new_selection:
                    self.selected_rows = new_selection
                    self.redraw()
                    if hasattr(self, 'on_row_selected') and self.on_row_selected:
                        self.on_row_selected(r)

    # ==========================================
    # MANUAL RESIZING & AUTO-RESIZE
    # ==========================================
    def _get_col_edge(self, x):
        if not self.col_positions: return None
        cx = self.header.canvasx(x)
        c = bisect.bisect_right(self.col_positions, cx) - 1
        if 0 <= c < len(self._headers):
            if abs(self.col_positions[c+1] - cx) < 6: return c
            if c > 0 and abs(self.col_positions[c] - cx) < 6: return c - 1
        return None

    def _get_row_edge(self, y):
        if not self.row_positions: return None
        cy = self.index.canvasy(y)
        r = bisect.bisect_right(self.row_positions, cy) - 1
        if 0 <= r < len(self._data):
            if abs(self.row_positions[r+1] - cy) < 6: return r
            if r > 0 and abs(self.row_positions[r] - cy) < 6: return r - 1
        return None

    def _on_main_leave(self, event):
        self._tooltip.hide()
        if self._hovered_row is not None:
            self._hovered_row = None
            self.redraw()

    def _on_main_motion(self, event):
        r, c = self.get_cell_from_coords(self.main_table, event.x, event.y)
        
        if r is not None and 0 <= r < len(self._data):
            if r != self._hovered_row:
                self._hovered_row = r
                self.redraw()
        elif self._hovered_row is not None:
            self._hovered_row = None
            self.redraw()
            
        if r is not None and c is not None and 0 <= r < len(self._data) and 0 <= c < len(self._headers):
            val = str(self._data[r][c])
            col_w = self.col_positions[c+1] - self.col_positions[c]
            
            if not hasattr(self, '_cached_font'):
                self._cached_font = tkfont.Font(font=self.font)
                
            lines = val.split('\n')
            max_w = max(self._cached_font.measure(line) for line in lines) if lines else 0
            if max_w + 10 > col_w:
                self._tooltip.show(val, event.x_root, event.y_root)
            else:
                self._tooltip.hide()
        else:
            self._tooltip.hide()

    def _on_header_motion(self, event):
        edge = self._get_col_edge(event.x)
        self.header.config(cursor="sb_h_double_arrow" if edge is not None else "hand2")
        
        if edge is None:
            _, c = self.get_cell_from_coords(self.header, event.x, 0)
            if c is not None and 0 <= c < len(self._headers):
                val = str(self._headers[c])
                col_w = self.col_positions[c+1] - self.col_positions[c]
                if not hasattr(self, '_cached_font_b'):
                    self._cached_font_b = tkfont.Font(font=self.header_font)
                    
                lines = val.split('\n')
                max_w = max(self._cached_font_b.measure(line) for line in lines) if lines else 0
                if max_w + 10 > col_w:
                    self._tooltip.show(val, event.x_root, event.y_root)
                else:
                    self._tooltip.hide()
            else:
                self._tooltip.hide()
        else:
            self._tooltip.hide()

    def _on_header_click(self, event):
        edge = self._get_col_edge(event.x)
        if edge is not None:
            self._rsz_col = edge 
        else:
            _, c = self.get_cell_from_coords(self.header, event.x, 0)
            if c is None:
                return
            if 0 <= c < len(self._headers):
                if c in self.ignored_cols:
                    return
                self._clear_selection()
                self.selected_cols.add(c)
                self.redraw()
                if self.on_column_selected:
                    self.on_column_selected(c, self._headers[c])

    def _on_header_right_click(self, event):
        if not self.header_context_menu_enabled:
            return
        _, c = self.get_cell_from_coords(self.header, event.x, 0)
        if c is None:
            return
        if 0 <= c < len(self._headers):
            self._clear_selection()
            self.selected_cols.add(c)
            self.redraw()
            if self.on_column_selected:
                self.on_column_selected(c, self._headers[c])
            self._show_header_menu(event, c)
            
    def _show_header_menu(self, event, col_idx):
        self._menu_target_col = col_idx
        # update menu options dynamically
        self.header_menu.delete(0, tk.END)
        
        has_items = False
        if self.header_menu_show_types:
            for t in self.available_types:
                self.header_menu.add_command(label=t, command=lambda type_val=t: self._on_header_menu_select(type_val))
            has_items = True
            
        if self.header_menu_show_ignore:
            if has_items:
                self.header_menu.add_separator()
            if col_idx in self.ignored_cols:
                self.header_menu.add_command(label="Spalte wieder einbeziehen", command=lambda col=col_idx: self._toggle_ignore_col_from_menu(col))
            else:
                self.header_menu.add_command(label="Spalte ignorieren", command=lambda col=col_idx: self._toggle_ignore_col_from_menu(col))
            has_items = True
            
        # Post menu slightly offset right-down from the mouse click
        if has_items:
            self.header_menu.post(event.x_root + 10, event.y_root + 10)
        
    def _on_header_menu_select(self, type_val):
        if hasattr(self, '_menu_target_col') and self._menu_target_col is not None:
            c = self._menu_target_col
            if self.on_type_changed:
                self.on_type_changed(c, type_val)

    def _on_header_double_click(self, event):
        c = self._get_col_edge(event.x)
        if c is not None:
            if self.stretch_columns and c == len(self._headers) - 1:
                return
                
            temp_font = tkfont.Font(family=self.font[0], size=self.font[1], weight=self.font[2] if len(self.font)>2 else "normal")
            max_w = int(temp_font.measure(str(self._headers[c]))) + 20
            for r in range(min(1000, len(self._data))):
                w = int(temp_font.measure(str(self._data[r][c]))) + 20
                if w > max_w: max_w = w
                
            diff = max_w - (self.col_positions[c+1] - self.col_positions[c])
            if diff != 0:
                if self.stretch_columns:
                    new_pos = self.col_positions[c+1] + diff
                    if new_pos > self.col_positions[-1] - 30:
                        new_pos = self.col_positions[-1] - 30
                    self.col_positions[c+1] = int(new_pos)
                else:
                    for i in range(c + 1, len(self.col_positions)):
                        self.col_positions[i] = int(self.col_positions[i] + diff)
                        
                self._update_scrollregions()
                self._user_resized_columns = True
                self.redraw()

    def _on_header_drag(self, event):
        if self._rsz_col is not None:
            if self._drag_line: self.main_table.delete(self._drag_line)
            cx = self.main_table.canvasx(event.x)
            self._drag_line = self.main_table.create_line(
                cx, self.main_table.canvasy(0), cx, self.main_table.canvasy(self.main_table.winfo_height()), 
                fill=self.colors["select_outline"], dash=(4, 4), width=2
            )

    def _on_header_release(self, event):
        if self._rsz_col is not None:
            if self._drag_line:
                self.main_table.delete(self._drag_line)
                self._drag_line = None
                
            if self.stretch_columns and self._rsz_col == len(self._headers) - 1:
                self._rsz_col = None
                return
                
            cx = int(self.header.canvasx(event.x))
            new_width = max(20, cx - self.col_positions[self._rsz_col])
            diff = new_width - (self.col_positions[self._rsz_col+1] - self.col_positions[self._rsz_col])
            
            if diff != 0:
                if self.stretch_columns:
                    new_pos = self.col_positions[self._rsz_col+1] + diff
                    if new_pos > self.col_positions[-1] - 30:
                        new_pos = self.col_positions[-1] - 30
                    self.col_positions[self._rsz_col+1] = int(new_pos)
                else:
                    for i in range(self._rsz_col + 1, len(self.col_positions)):
                        self.col_positions[i] = int(self.col_positions[i] + diff)
                        
            self._rsz_col = None
            self._update_scrollregions()
            self._user_resized_columns = True
            self.redraw()

    def _on_index_motion(self, event):
        self.index.config(cursor="sb_v_double_arrow" if self._get_row_edge(event.y) is not None else "")

    def _on_index_click(self, event):
        edge = self._get_row_edge(event.y)
        if edge is not None:
            self._rsz_row = edge
        else:
            r, _ = self.get_cell_from_coords(self.index, 0, event.y)
            if r is None:
                return
            if 0 <= r < len(self._data):
                self._drag_start_row = r
                self._drag_start_col = 0
                self._drag_original_selection = set(self.selected_rows) if self.select_mode == "row" else self.selected_cell
                
                if event.state & 0x0004: # Control key
                    if r in self.selected_rows:
                        self.selected_rows.remove(r)
                    else:
                        self.selected_rows.add(r)
                else:
                    self._clear_selection()
                    self.selected_rows.add(r)
                self.redraw()

    def _on_index_right_click(self, event):
        if not self.index_context_menu_enabled:
            return
        r, _ = self.get_cell_from_coords(self.index, 0, event.y)
        if r is None:
            return
        if 0 <= r < len(self._data):
            if r not in self.selected_rows:
                self._clear_selection()
                self.selected_rows.add(r)
            self.redraw()
            
            menu = tk.Menu(self, tearoff=0, bg=self.colors["menu_bg"], fg=self.colors["menu_fg"], 
                           activebackground=self.colors["select_outline"], activeforeground="#ffffff")
            menu.add_command(label="Als Kopfzeile festlegen", command=lambda row=r: self._set_header_from_menu(row))
            menu.add_separator()
            menu.add_command(label="Start Datenzeile hier setzen", command=lambda row=r: self._set_data_start_from_menu(row))
            menu.add_command(label="Ende Datenzeile hier setzen", command=lambda row=r: self._set_data_end_from_menu(row))
            menu.add_separator()
            
            if r in self.ignored_rows:
                menu.add_command(label="Zeile wieder einbeziehen", command=lambda row=r: self._toggle_ignore_row_from_menu(row))
            else:
                menu.add_command(label="Zeile ignorieren", command=lambda row=r: self._toggle_ignore_row_from_menu(row))
                
            menu.post(event.x_root, event.y_root)

    def _set_header_from_menu(self, row_idx):
        self.set_header_row(row_idx)
        if self.on_header_row_changed:
            self.on_header_row_changed(row_idx)
            
    def _set_data_start_from_menu(self, row_idx):
        if self.on_data_start_row_changed:
            self.on_data_start_row_changed(row_idx)

    def _set_data_end_from_menu(self, row_idx):
        if self.on_data_end_row_changed:
            self.on_data_end_row_changed(row_idx)

    def _toggle_ignore_row_from_menu(self, row_idx):
        if self.on_ignore_row_toggled:
            self.on_ignore_row_toggled(row_idx)

    def _toggle_ignore_col_from_menu(self, col_idx):
        if self.on_ignore_col_toggled:
            self.on_ignore_col_toggled(col_idx)

    def set_header_row(self, row_idx):
        self.header_row_index = row_idx
        if not getattr(self, '_batch_updating', False):
            self.redraw()

    def set_data_bounds(self, start_row_idx, end_row_idx):
        self.data_start_row_index = start_row_idx
        self.data_end_row_index = end_row_idx
        self.redraw()

    def set_ignored_rows(self, rows_set):
        self.ignored_rows = set(rows_set)
        if not getattr(self, '_batch_updating', False):
            self.redraw()

    def set_ignored_cols(self, cols_set):
        self.ignored_cols = set(cols_set)
        if not getattr(self, '_batch_updating', False):
            self.redraw()

    def scroll_to_row(self, row_idx):
        if not self._data or not self.row_positions: return
        if row_idx < 0: row_idx = 0
        if row_idx >= len(self._data): row_idx = len(self._data) - 1
        
        total_y = self.row_positions[-1]
        if total_y > 0:
            target_y = self.row_positions[row_idx]
            # Account for view window height if possible, otherwise just set to top
            view_h = self.main_table.winfo_height()
            fraction = max(0.0, min(1.0, (target_y - view_h/2) / total_y)) if view_h else (target_y / total_y)
            self.main_table.yview_moveto(fraction)
            self.index.yview_moveto(fraction)
            self.redraw()

    def scroll_to_col(self, col_idx):
        if not self._headers or col_idx < 0 or col_idx >= len(self.col_positions) - 1:
            return
            
        target_x = self.col_positions[col_idx]
        col_right_x = self.col_positions[col_idx + 1]
        total_x = self.col_positions[-1]
        
        if total_x > 0:
            left_frac, right_frac = self.main_table.xview()
            visible_left = left_frac * total_x
            visible_right = right_frac * total_x
            viewport_width = visible_right - visible_left
            
            fraction = None
            if target_x < visible_left:
                fraction = target_x / total_x
            elif col_right_x > visible_right:
                if (col_right_x - target_x) > viewport_width:
                    scroll_x = target_x
                else:
                    scroll_x = col_right_x - viewport_width
                fraction = max(0, scroll_x) / total_x
                
            if fraction is not None:
                self.main_table.xview_moveto(fraction)
                self.header.xview_moveto(fraction)
            if not getattr(self, '_batch_updating', False):
                self.redraw()

    def get_scroll_fraction(self):
        try:
            return self.main_table.xview()[0], self.main_table.yview()[0]
        except Exception:
            return 0.0, 0.0
            
    def set_scroll_fraction(self, x_frac, y_frac):
        try:
            self.main_table.xview_moveto(x_frac)
            self.header.xview_moveto(x_frac)
            self.main_table.yview_moveto(y_frac)
            self.index.yview_moveto(y_frac)
        except Exception:
            pass

    # ==========================================
    # DRAG & DROP FÜR ZEILEN / SPALTEN RESIZING
    # ==========================================

    def _on_index_drag(self, event):
        if self._rsz_row is not None:
            if self._drag_line: self.main_table.delete(self._drag_line)
            cy = self.main_table.canvasy(event.y)
            self._drag_line = self.main_table.create_line(
                self.main_table.canvasx(0), cy, self.main_table.canvasx(self.main_table.winfo_width()), cy, 
                fill=self.colors["select_outline"], dash=(4, 4), width=2
            )
        else:
            self._handle_drag_selection(self.index, 0, event.y, event.state)

    def _on_index_release(self, event):
        if self._rsz_row is not None:
            if self._drag_line:
                self.main_table.delete(self._drag_line)
                self._drag_line = None
            cy = int(self.index.canvasy(event.y))
            new_height = max(20, cy - self.row_positions[self._rsz_row])
            diff = new_height - (self.row_positions[self._rsz_row+1] - self.row_positions[self._rsz_row])
            for i in range(self._rsz_row + 1, len(self.row_positions)):
                self.row_positions[i] = int(self.row_positions[i] + diff)
            self._rsz_row = None
            self._update_scrollregions()
            self.redraw()


