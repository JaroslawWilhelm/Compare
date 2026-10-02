import tkinter as tk
from tkinter import ttk
import tkinter.font as tkfont
import bisect

class GridToolTip:
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

class TkPropertyGrid(tk.Frame):
    """
    A high-performance, GxP-compliant PropertyGrid implementation in pure Tkinter.
    
    ARCHITEKTUR-UPDATE (Custom-Canvas Edition):
    Verwendet "Virtual Rendering", "Object Pooling" und direkte Canvas-Befehle 
    für kompromisslose Skalierungs-Performance, genau wie das ComplianceGrid.
    Inklusive Hovering, Zebra-Muster und On-Demand Scroll-Editoren.
    """
    def __init__(self, parent, value_changed_callback=None, zoom_id=None):
        super().__init__(parent)
        self.value_changed_callback = value_changed_callback
        
        # Design & Layout Constants
        self.row_height = 32
        self.col0_width = 250
        
        self.colors = {
            "bg_even": "#ffffff",
            "bg_odd": "#f8f9fa",
            "bg_hover": "#e6f2ff",
            "cat_bg": "#eef2f5",
            "cat_bg_inactive": "#f8f9fa",
            "cat_fg": "#202124",
            "cat_fg_inactive": "#9e9e9e",
            "text_fg": "#333333",
            "text_fg_inactive": "#a0a0a0",
            "grid_line": "#e0e0e0",
            "select_outline": "#0b57d0",
            "input_bg": "#ffffff",
            "input_border": "#cccccc",
            "arrow_fg": "#666666",
            "btn_bg": "#f8f9fa",
            "btn_bg_hover": "#d3e3fd",
            "btn_bg_pressed": "#a8c7fa",
            "btn_fg": "#0b57d0",
            "btn_fg_pressed": "#062e6f",
            "btn_border": "#cccccc"
        }
        
        self.zoom_id = zoom_id
        self.font_size = 11
        
        from ui_components import ZoomManager
        if self.zoom_id and self.zoom_id in ZoomManager.GLOBAL_STATES:
            delta = ZoomManager.GLOBAL_STATES[self.zoom_id]
            self.font_size = 11 + delta
            scale = 1.1 ** delta
            self.row_height = max(16, int(round(self.row_height * scale)))
            self.col0_width = max(50, int(round(self.col0_width * scale)))
            
        self.font = ("Segoe UI", self.font_size)
        self.font_bold = ("Segoe UI", self.font_size, "bold")
        self._tk_font = tkfont.Font(font=self.font)
        
        # State
        self._data = []
        self._hover_row = None
        self._pressed_row = None
        self._selected_id = None
        self._pressed_x = None
        self._pressed_y = None
        self._edit_widget = None
        self._edit_window_id = None
        self._editing_row = None
        self._last_width = 0
        self._last_height = 0
        self._locked = False          # Pilot Mode: blocks all interaction when True
        self._lock_overlay_id = None  # Canvas rectangle for visual "locked" feedback
        
        # Object Pools
        self._pool_rects = []
        self._pool_texts = []
        self._pool_polys = []
        
        self._redraw_pending = False
        self._tooltip = GridToolTip(self)
        
        self._setup_ui()
        
    def _setup_ui(self):
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        
        self.canvas = tk.Canvas(self, highlightthickness=0, bg=self.colors["bg_even"])
        self.canvas.grid(row=0, column=0, sticky="nsew")
        
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.scrollbar.grid(row=0, column=1, sticky="ns")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        # Events
        self.canvas.bind("<Configure>", self._on_resize)
        
        # Interaction
        self.canvas.bind("<Motion>", self._on_hover)
        self.canvas.bind("<Leave>", self._on_leave)
        self.canvas.bind("<ButtonPress-1>", self._on_mouse_down)
        self.canvas.bind("<ButtonRelease-1>", self._on_mouse_up)
        
        # Safe Mousewheel Binding (Only when hovering the specific grid)
        self.canvas.bind("<Enter>", self._bind_mousewheel)
        self.canvas.bind("<Leave>", self._unbind_mousewheel)

    def _bind_mousewheel(self, event):
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind_all("<Control-MouseWheel>", self._on_zoom)
        
    def _unbind_mousewheel(self, event):
        self.canvas.unbind_all("<MouseWheel>")
        self.canvas.unbind_all("<Control-MouseWheel>")
        self._on_leave(event) # Clear hover

    # ==========================================
    # API & DATA MODEL
    # ==========================================
    def set_theme(self, theme):
        is_dark = (theme == "dark")
        if is_dark:
            self.colors = {
                "bg_even": "#1e1e1e",
                "bg_odd": "#252525",
                "bg_hover": "#004a77",
                "bg_selected": "#1a4a82",
                "cat_bg": "#2d2d2d",
                "cat_bg_inactive": "#252525",
                "cat_fg": "#ffffff",
                "cat_fg_inactive": "#666666",
                "text_fg": "#e0e0e0",
                "text_fg_inactive": "#666666",
                "grid_line": "#333333",
                "select_outline": "#4daafc",
                "input_bg": "#2d2d2d",
                "input_border": "#555555",
                "arrow_fg": "#a0a0a0",
                "btn_bg": "#333333",
                "btn_bg_hover": "#4d4d4d",
                "btn_bg_pressed": "#1e1e1e",
                "btn_fg": "#66b2ff",
                "btn_fg_pressed": "#3399ff",
                "btn_border": "#555555"
            }
        else:
            self.colors = {
                "bg_even": "#ffffff",
                "bg_odd": "#f8f9fa",
                "bg_hover": "#e6f2ff",
                "bg_selected": "#cce0ff",
                "cat_bg": "#eef2f5",
                "cat_bg_inactive": "#f8f9fa",
                "cat_fg": "#202124",
                "cat_fg_inactive": "#9e9e9e",
                "text_fg": "#333333",
                "text_fg_inactive": "#a0a0a0",
                "grid_line": "#e0e0e0",
                "select_outline": "#0b57d0",
                "input_bg": "#ffffff",
                "input_border": "#cccccc",
                "arrow_fg": "#666666",
                "btn_bg": "#f8f9fa",
                "btn_bg_hover": "#d3e3fd",
                "btn_bg_pressed": "#a8c7fa",
                "btn_fg": "#0b57d0",
                "btn_fg_pressed": "#062e6f",
                "btn_border": "#cccccc"
            }
        self.canvas.config(bg=self.colors["bg_even"])
        self._request_redraw()

    def set_locked(self, locked: bool):
        """
        Locks or unlocks the entire PropertyGrid (Pilot Mode).
        
        When locked:
        - All mouse interaction (hover, click, edit) is blocked
        - A semi-transparent overlay is drawn over the canvas
        - The cursor changes to the default arrow (no hand cursor)
        
        Args:
            locked: True to lock the grid, False to unlock.
        """
        self._locked = locked
        self._cancel_edit()
        self._hover_row = None
        self._pressed_row = None
        
        if locked:
            # Draw a stippled overlay rectangle that visually dims the grid.
            # The stipple pattern creates a semi-transparent grey effect in Tkinter.
            self._draw_lock_overlay()
        else:
            # Remove the overlay
            if self._lock_overlay_id is not None:
                self.canvas.delete(self._lock_overlay_id)
                self._lock_overlay_id = None
        
        self.redraw()
    
    def _draw_lock_overlay(self):
        """Draws a stippled overlay rectangle to indicate the grid is locked."""
        if self._lock_overlay_id is not None:
            self.canvas.delete(self._lock_overlay_id)
        
        w = max(self.canvas.winfo_width(), 1)
        h = max(len(self._data) * self.row_height, self.canvas.winfo_height())
        
        self._lock_overlay_id = self.canvas.create_rectangle(
            0, 0, w, h,
            fill="#e0e0e0", stipple="gray50", outline=""
        )
        # Ensure overlay is always on top
        self.canvas.tag_raise(self._lock_overlay_id)
    
    def clear(self):
        self._cancel_edit()
        self._data.clear()
        self._hover_row = None
        self._pressed_row = None
        self._request_redraw()

    def _request_redraw(self):
        """Batches redraw operations to avoid stuttering and prevent blank grids."""
        if not getattr(self, '_redraw_pending', False):
            self._redraw_pending = True
            self.after_idle(self._do_redraw)

    def _do_redraw(self):
        self._redraw_pending = False
        if self.winfo_exists():
            self._update_scrollregion()
            self.redraw()

    def scroll_to_top(self):
        """Scrolls the canvas view to the very top (y=0)."""
        self.canvas.yview_moveto(0.0)

    def add_category(self, label_text, prop_id=None, inactive=False):
        if prop_id is None: prop_id = label_text
        self._data.append({"type": "category", "label": label_text, "id": prop_id, "inactive": inactive})
        self._request_redraw()

    def add_radio(self, label, prop_id=None, current_val=False, *args, **kwargs):
        if prop_id is None: prop_id = label
        val_bool = str(current_val).lower() in ("true", "1", "yes")
        self._data.append({
            "type": "radio",
            "label": label,
            "value": val_bool,
            "id": prop_id,
            "readonly": False,
            "choices": None
        })
        self._request_redraw()

    def add_property(self, prop_name, prop_value, prop_id=None, read_only=False):
        if prop_id is None: prop_id = prop_name
        self._data.append({
            "type": "property",
            "label": prop_name,
            "value": str(prop_value),
            "id": prop_id,
            "readonly": read_only,
            "choices": None
        })
        self._request_redraw()

    def update_property(self, prop_id, new_value):
        for item in self._data:
            if item.get("id") == prop_id:
                if item.get("type") == "boolean":
                    item["value"] = str(new_value).lower() in ("true", "1", "yes")
                else:
                    item["value"] = str(new_value)
                self.redraw()
                return True
        return False

    def add_enum(self, label, prop_id, choices=None, *args, **kwargs):
        value = kwargs.get("current_val", args[0] if args else (choices[0] if isinstance(choices, list) and choices else ""))
        if prop_id is None: prop_id = label
        self._data.append({
            "type": "property",
            "label": label,
            "value": str(value),
            "id": prop_id,
            "readonly": False,
            "choices": [str(c) for c in choices] if choices else []
        })
        self._request_redraw()

    def add_typeahead(self, label, prop_id, choices=None, current_val="", *args, **kwargs):
        if prop_id is None: prop_id = label
        self._data.append({
            "type": "typeahead",
            "label": label,
            "value": str(current_val),
            "id": prop_id,
            "readonly": False,
            "choices": [str(c) for c in choices] if choices else []
        })
        self._request_redraw()

    def add_boolean(self, label, prop_id, default_val=False, current_val=False, *args, **kwargs):
        if prop_id is None: prop_id = label
        val_bool = str(current_val).lower() in ("true", "1", "yes")
        inactive = kwargs.get("inactive", False)
        self._data.append({
            "type": "boolean",
            "label": label,
            "value": val_bool,
            "id": prop_id,
            "readonly": False,
            "choices": None,
            "inactive": inactive
        })
        self._request_redraw()

    def add_color(self, label, prop_id=None, current_val="#ffffff", *args, **kwargs):
        if prop_id is None: prop_id = label
        
        # Format normalization
        if isinstance(current_val, (tuple, list)) and len(current_val) >= 3:
            current_val = f"#{int(current_val[0]):02x}{int(current_val[1]):02x}{int(current_val[2]):02x}"
        elif hasattr(current_val, "GetAsString"): 
            current_val = current_val.GetAsString(6) # wx.C2S_HTML_SYNTAX
            
        if not str(current_val).startswith('#'):
             current_val = "#ffffff"
             
        self._data.append({
            "type": "color",
            "label": label,
            "value": str(current_val).lower(),
            "id": prop_id,
            "readonly": False,
            "choices": None
        })
        self._request_redraw()

    def add_button(self, label, prop_id=None, current_val="Button", callback=None, *args, **kwargs):
        if prop_id is None: prop_id = label
        self._data.append({
            "type": "button",
            "label": label,
            "value": str(current_val),
            "id": prop_id,
            "readonly": False,
            "choices": None,
            "callback": callback
        })
        self._request_redraw()

    def add_dialog(self, label, value_display, prop_id=None, callback=None, *args, **kwargs):
        if prop_id is None: prop_id = label
        self._data.append({
            "type": "dialog",
            "label": label,
            "value": str(value_display),
            "id": prop_id,
            "readonly": False, # Treated as custom interactable
            "choices": None,
            "callback": callback
        })
        self._request_redraw()

    def __getattr__(self, name):
        """DAS UNIVERSAL-SICHERHEITSNETZ für alte wxPython Calls (add_int, add_color etc.)"""
        if name.startswith("add_"):
            def legacy_fallback(label, prop_id=None, value="", *args, **kwargs):
                self.add_property(prop_name=label, prop_value=value, prop_id=prop_id or label)
            return legacy_fallback
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")

    # ==========================================
    # VIRTUAL RENDERING ENGINE
    # ==========================================
    def _update_scrollregion(self, width=None):
        if width is None: width = self.winfo_width()
        total_height = len(self._data) * self.row_height
        canvas_height = self.canvas.winfo_height()
        # Ensure scrollregion is at least canvas_height to prevent out-of-bounds scrolling
        self.canvas.configure(scrollregion=(0, 0, width, max(total_height, canvas_height)))

    def _on_resize(self, event):
        if event.widget != self.canvas: return
        if event.width == self._last_width and event.height == self._last_height: return
        
        width_changed = (event.width != self._last_width)
        self._last_width = event.width
        self._last_height = event.height
        
        self._update_scrollregion(event.width)
        
        if width_changed or not self._pool_rects:
            self.redraw(event.width)

    def _on_mousewheel(self, event):
        # Stabilere Prüfung: Wenn der Scrollbalken 0.0 bis 1.0 anzeigt, ist der Inhalt vollständig sichtbar
        scroll_state = self.scrollbar.get()
        if scroll_state and scroll_state[0] <= 0.0 and scroll_state[1] >= 1.0:
            self.canvas.yview_moveto(0)
            return
        self.canvas.yview_scroll(int(-event.delta / 120), "units")

    def _on_zoom(self, event):
        if not self._data: return
        delta = 1 if event.delta > 0 else -1
        new_size = self.font_size + delta
        if not (6 <= new_size <= 30):
            return
            
        self.font_size = new_size
        self.font = ("Segoe UI", self.font_size)
        self.font_bold = ("Segoe UI", self.font_size, "bold")
        self._tk_font.configure(size=self.font_size)
        
        if self.zoom_id:
            from ui_components import ZoomManager
            ZoomManager.GLOBAL_STATES[self.zoom_id] = self.font_size - 11
            
        scale = 1.1 if delta > 0 else (1 / 1.1)
        self.row_height = max(16, int(round(self.row_height * scale)))
        self.col0_width = max(50, int(round(self.col0_width * scale)))
        
        self._update_scrollregion(self._last_width)
        self.redraw(self._last_width)

    def get_visible_area(self):
        if not self._data: return 0, 0
        return 0, len(self._data)

    def _round_rect_coords(self, x1, y1, x2, y2, r=4):
        return [
            x1+r, y1,  x1+r, y1,  x2-r, y1,  x2-r, y1,
            x2, y1,    x2, y1+r,  x2, y1+r,  x2, y2-r,  x2, y2-r,
            x2, y2,    x2-r, y2,  x2-r, y2,  x1+r, y2,  x1+r, y2,
            x1, y2,    x1, y2-r,  x1, y2-r,  x1, y1+r,  x1, y1+r,
            x1, y1
        ]

    def _truncate_text(self, text, max_width):
        if not text: return ""
        if self._tk_font.measure(text) <= max_width:
            return text
        ellipsis = "..."
        e_width = self._tk_font.measure(ellipsis)
        if max_width <= e_width:
            return ""
        
        # Binäre Suche für maximale Performance beim Abschneiden
        low, high = 0, len(text)
        best = 0
        while low <= high:
            mid = (low + high) // 2
            if self._tk_font.measure(text[:mid]) + e_width <= max_width:
                best = mid
                low = mid + 1
            else:
                high = mid - 1
        return text[:best] + ellipsis

    def redraw(self, override_width=None):
        if not self._data:
            for r in self._pool_rects: self.canvas.itemconfig(r, state="hidden")
            for t in self._pool_texts: self.canvas.itemconfig(t, state="hidden")
            for p in self._pool_polys: self.canvas.itemconfig(p, state="hidden")
            return
            
        from_row, upto_row = self.get_visible_area()
        width = override_width if override_width is not None else self.canvas.winfo_width()
        
        rect_idx = 0
        text_idx = 0
        
        for r in range(from_row, upto_row):
            item = self._data[r]
            y1 = r * self.row_height
            y2 = y1 + self.row_height
            text_y = y1 + (self.row_height // 2)
            
            # Ensure pool capacity (2 rects, 3 texts per row)
            while len(self._pool_rects) <= rect_idx + 1:
                self._pool_rects.append(self.canvas.create_rectangle(0,0,0,0, outline=""))
            while len(self._pool_polys) <= r:
                self._pool_polys.append(self.canvas.create_polygon(0,0,0,0, outline="", smooth=True))
            while len(self._pool_texts) <= text_idx + 2:
                self._pool_texts.append(self.canvas.create_text(0,0, text="", anchor="w"))
                
            r_bg = self._pool_rects[rect_idx]
            r_line = self._pool_rects[rect_idx + 1]
            p_extra = self._pool_polys[r]
            
            t_left = self._pool_texts[text_idx]
            t_right = self._pool_texts[text_idx + 1]
            t_extra = self._pool_texts[text_idx + 2]
            
            if item["type"] == "category":
                self.canvas.coords(r_bg, 0, y1, width, y2)
                
                is_inactive = item.get("inactive", False)
                cat_bg = self.colors["cat_bg"] if not is_inactive else self.colors.get("cat_bg_inactive", "#f8f9fa")
                cat_fg = self.colors["cat_fg"] if not is_inactive else self.colors.get("cat_fg_inactive", "#9e9e9e")
                
                self.canvas.itemconfig(r_bg, fill=cat_bg, outline="", state="normal")
                
                self.canvas.coords(t_left, 10, text_y)
                self.canvas.itemconfig(t_left, text=item["label"], font=self.font_bold, fill=cat_fg, state="normal")
                
                self.canvas.itemconfig(r_line, state="hidden")
                self.canvas.itemconfig(t_right, state="hidden")
                self.canvas.itemconfig(p_extra, state="hidden")
                self.canvas.itemconfig(t_extra, state="hidden")
            else:
                if item.get("id") == self._selected_id and self._selected_id is not None:
                    bg_color = self.colors["bg_selected"]
                else:
                    bg_color = self.colors["bg_hover"] if r == self._hover_row else (
                               self.colors["bg_even"] if r % 2 == 0 else self.colors["bg_odd"])
                           
                self.canvas.coords(r_bg, 0, y1, width, y2)
                self.canvas.itemconfig(r_bg, fill=bg_color, outline="", state="normal")
                
                self.canvas.coords(r_line, self.col0_width, y1, self.col0_width+1, y2)
                self.canvas.itemconfig(r_line, fill=self.colors["grid_line"], outline="", state="normal")
                
                is_inactive = item.get("inactive", False)
                text_fg = self.colors["text_fg"] if not is_inactive else self.colors.get("text_fg_inactive", "#a0a0a0")
                
                self.canvas.coords(t_left, 25, text_y)
                self.canvas.itemconfig(t_left, text=item["label"], font=self.font, fill=text_fg, state="normal")
                
                if item.get("type") == "boolean":
                    box_size = 18
                    box_x1 = self.col0_width + 10
                    box_y1 = text_y - box_size // 2
                    box_x2 = box_x1 + box_size
                    box_y2 = text_y + box_size // 2
                    
                    self.canvas.coords(p_extra, *self._round_rect_coords(box_x1, box_y1, box_x2, box_y2, 4))
                    
                    if item["value"]:
                        self.canvas.itemconfig(p_extra, fill="#0b57d0", outline="#0b57d0", state="normal")
                        self.canvas.coords(t_right, box_x1 + box_size//2, text_y)
                        self.canvas.itemconfig(t_right, text="✓", font=("Segoe UI", 12, "bold"), fill="#ffffff", state="normal", anchor="center")
                    else:
                        border_color = self.colors["select_outline"] if r == self._hover_row else self.colors["input_border"]
                        self.canvas.itemconfig(p_extra, fill=self.colors["input_bg"], outline=border_color, state="normal")
                        self.canvas.itemconfig(t_right, state="hidden")
                        
                    self.canvas.itemconfig(t_extra, state="hidden")
                elif item.get("type") == "color":
                    if r == self._editing_row:
                        self.canvas.itemconfig(t_right, state="hidden")
                        self.canvas.itemconfig(p_extra, state="hidden")
                        self.canvas.itemconfig(t_extra, state="hidden")
                    else:
                        color_val = item["value"]
                        # Color box
                        box_size = 18
                        box_x1 = self.col0_width + 10
                        box_y1 = text_y - box_size // 2
                        box_x2 = box_x1 + box_size
                        box_y2 = text_y + box_size // 2
                        
                        self.canvas.coords(p_extra, *self._round_rect_coords(box_x1, box_y1, box_x2, box_y2, 4))
                        try:
                            self.canvas.itemconfig(p_extra, fill=color_val, outline="#a0a0a0", state="normal")
                        except tk.TclError:
                            self.canvas.itemconfig(p_extra, fill="#ffffff", outline="#a0a0a0", state="normal")
                            
                        # RGB text
                        try:
                            c = color_val.lstrip('#')
                            if len(c) == 6:
                                r_c, g_c, b_c = tuple(int(c[i:i+2], 16) for i in (0, 2, 4))
                                rgb_text = f"({r_c},{g_c},{b_c})"
                            else:
                                rgb_text = color_val
                        except:
                            rgb_text = color_val

                        self.canvas.coords(t_right, box_x2 + 10, text_y)
                        self.canvas.itemconfig(t_right, text=rgb_text, font=self.font, fill=self.colors["text_fg"], state="normal", anchor="w")
                        
                        # "..." button (fest an linker Seite gebunden, damit es beim Verkleinern verschwindet)
                        self.canvas.coords(t_extra, box_x2 + 120, text_y)
                        self.canvas.itemconfig(t_extra, text="...", font=self.font_bold, fill=self.colors["text_fg"], anchor="w", state="normal")
                elif item.get("type") == "dialog":
                    # Custom dialog property: Show value text, then a [...] button
                    display_val = item["value"]
                    
                    available_width = width - self.col0_width - 50 # Make room for [...]
                    if available_width > 0:
                        display_val = self._truncate_text(str(display_val), available_width)
                    else:
                        display_val = ""
                        
                    self.canvas.coords(t_right, self.col0_width + 10, text_y)
                    self.canvas.itemconfig(t_right, text=display_val, font=self.font, fill=self.colors["text_fg"], state="normal", anchor="w")
                    
                    # Draw [...] button visually as text or a small rect
                    btn_w = 30
                    btn_x1 = width - btn_w - 5
                    btn_x2 = width - 5
                    if btn_x1 > self.col0_width + 10:
                        self.canvas.coords(p_extra, *self._round_rect_coords(btn_x1, y1 + 6, btn_x2, y2 - 6, 3))
                        bg_col = self.colors["btn_bg_hover"] if r == self._hover_row else self.colors["input_bg"]
                        self.canvas.itemconfig(p_extra, fill=bg_col, outline=self.colors["input_border"], state="normal")
                        
                        self.canvas.coords(t_extra, (btn_x1 + btn_x2)//2, text_y)
                        self.canvas.itemconfig(t_extra, text="...", font=self.font_bold, fill=self.colors["text_fg"], state="normal", anchor="center")
                    else:
                        self.canvas.itemconfig(p_extra, state="hidden")
                        self.canvas.itemconfig(t_extra, state="hidden")
                        
                elif item.get("type") == "button":
                    if r == self._pressed_row and r == self._hover_row:
                        bg_col = self.colors["btn_bg_pressed"]
                        fg_col = self.colors["btn_fg_pressed"]
                    else:
                        bg_col = self.colors["btn_bg_hover"] if r == self._hover_row else self.colors["btn_bg"]
                        fg_col = self.colors["btn_fg"] if r == self._hover_row else self.colors["text_fg"]
                    
                    btn_text = item["value"]
                    btn_width = max(100, len(btn_text) * 8 + 20)
                    
                    # Fest an der linken Seite ausrichten (Performance bei Größenänderung)
                    btn_x1 = self.col0_width + 10
                    btn_x2 = btn_x1 + btn_width
                    
                    self.canvas.coords(p_extra, *self._round_rect_coords(btn_x1, y1 + 4, btn_x2, y2 - 4, 6))
                    self.canvas.itemconfig(p_extra, fill=bg_col, outline=fg_col, state="normal")
                    
                    self.canvas.coords(t_right, (btn_x1 + btn_x2) // 2, text_y)
                    self.canvas.itemconfig(t_right, text=btn_text, font=self.font_bold, fill=fg_col, state="normal", anchor="center")
                    
                    self.canvas.itemconfig(r_line, state="hidden")
                    self.canvas.itemconfig(t_extra, state="hidden")
                else:
                    if r == self._editing_row:
                        self.canvas.itemconfig(t_right, state="hidden")
                    else:
                        display_val = item["value"]
                        
                        has_dropdown = item.get("choices") is not None and not item.get("readonly", False)
                        available_width = width - self.col0_width - (35 if has_dropdown else 15)
                        
                        if available_width > 0:
                            display_val = self._truncate_text(str(display_val), available_width)
                        else:
                            display_val = ""
                            
                        self.canvas.coords(t_right, self.col0_width + 10, text_y)
                        self.canvas.itemconfig(t_right, text=display_val, font=self.font, fill=self.colors["text_fg"], state="normal", anchor="w")
                    
                    if item.get("choices") is not None and not item.get("readonly", False):
                        # Background rectangle for the dropdown
                        drop_x1 = self.col0_width + 4
                        drop_y1 = y1 + 4
                        drop_x2 = width - 4
                        drop_y2 = y2 - 4
                        
                        self.canvas.coords(p_extra, *self._round_rect_coords(drop_x1, drop_y1, drop_x2, drop_y2, 4))
                        border_color = self.colors["select_outline"] if r == self._hover_row else self.colors["input_border"]
                        
                        self.canvas.itemconfig(p_extra, fill=self.colors["input_bg"], outline=border_color, state="normal")
                        
                        # Arrow
                        arrow_x = drop_x2 - 10
                        self.canvas.coords(t_extra, arrow_x, text_y)
                        self.canvas.itemconfig(t_extra, text="▼", font=("Segoe UI", 9), fill=self.colors["arrow_fg"], state="normal", anchor="e")
                        
                        # Raise text items above the polygon
                        self.canvas.tag_raise(t_right)
                        self.canvas.tag_raise(t_extra)
                    else:
                        self.canvas.itemconfig(p_extra, state="hidden")
                        self.canvas.itemconfig(t_extra, state="hidden")
            
            rect_idx += 2
            text_idx += 3
            
        # Hide unused pool items
        for i in range(rect_idx, len(self._pool_rects)): self.canvas.itemconfig(self._pool_rects[i], state="hidden")
        for i in range(text_idx, len(self._pool_texts)): self.canvas.itemconfig(self._pool_texts[i], state="hidden")
        for i in range(upto_row, len(self._pool_polys)): self.canvas.itemconfig(self._pool_polys[i], state="hidden")
        
        # Update edit widget width if resizing during edit
        if self._editing_row is not None and self._edit_window_id:
            self.canvas.itemconfig(self._edit_window_id, width=width - self.col0_width - 1)
        
        # Pilot Mode: Re-draw the lock overlay on top of all content.
        # Must be done AFTER all pool items are rendered, otherwise the overlay
        # gets buried underneath the grid rows.
        if self._locked:
            self._draw_lock_overlay()

    # ==========================================
    # INTERACTION & ERGONOMICS
    # ==========================================
    def _on_hover(self, event):
        if self._locked:
            return  # Pilot Mode: no hover feedback when locked
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        r = int(y // self.row_height)
        
        if 0 <= r < len(self._data):
            item = self._data[r]
            if x > self.col0_width and item["type"] in ("property", "enum", "dialog"):
                display_val = str(item.get("value", ""))
                
                if item["type"] == "dialog":
                    available_width = self.canvas.winfo_width() - self.col0_width - 50
                else:
                    has_dropdown = item.get("choices") is not None and not item.get("readonly", False)
                    available_width = self.canvas.winfo_width() - self.col0_width - (35 if has_dropdown else 15)
                
                if self._tk_font.measure(display_val) > available_width:
                    self._tooltip.show(display_val, event.x_root, event.y_root)
                else:
                    self._tooltip.hide()
            else:
                self._tooltip.hide()
        else:
            self._tooltip.hide()
            
        if 0 <= r < len(self._data) and self._data[r]["type"] in ("property", "boolean", "color", "button", "dialog"):
            if self._hover_row != r:
                self._hover_row = r
                self.redraw()
        else:
            if self._hover_row is not None:
                self._hover_row = None
                self.redraw()
                
    def _on_leave(self, event):
        if self._tooltip: self._tooltip.hide()
        if self._locked:
            return
        if self._hover_row is not None:
            self._hover_row = None
            self.redraw()

    # ==========================================
    # ON-DEMAND EDITING
    # ==========================================
    def _on_mouse_down(self, event):
        if self._locked:
            return  # Pilot Mode: no interaction when locked
            
        if self._edit_widget:
            self._commit_edit()
            self._cancel_edit()
            
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        r = int(y // self.row_height)
        
        self._pressed_x = event.x
        self._pressed_y = event.y
        
        if 0 <= r < len(self._data):
            item = self._data[r]
            if x > self.col0_width:
                # Allow pressing readonly properties so they can be copied
                if not item.get("readonly", False) or item["type"] == "property":
                    self._pressed_row = r
                if item["type"] == "button" and not item.get("readonly", False):
                    self.redraw()

    def _set_choice_value(self, item, new_val):
        force_trigger = str(new_val).startswith("Benutzerdefiniert")
        if str(new_val) != str(item["value"]) or force_trigger:
            item["value"] = str(new_val)
            if self.value_changed_callback:
                self.value_changed_callback(item["id"], new_val)
            self.redraw()

    def _on_mouse_up(self, event):
        if self._locked:
            return  # Pilot Mode: no interaction when locked
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        r = int(y // self.row_height)
        
        pressed = self._pressed_row
        if self._pressed_row is not None:
            self._pressed_row = None
            self.redraw()
            
        # Toleranzprüfung: Klick zulassen, wenn die Mausbewegung < 5 Pixel war (Standard-Best-Practice)
        is_valid_click = False
        if getattr(self, '_pressed_x', None) is not None and getattr(self, '_pressed_y', None) is not None:
            dist_sq = (event.x - self._pressed_x)**2 + (event.y - self._pressed_y)**2
            if dist_sq <= 25:
                is_valid_click = True
            
        if 0 <= r < len(self._data) and (r == pressed or is_valid_click):
            item = self._data[r]
            
            # Select row (except categories)
            if item.get("type") != "category":
                self._selected_id = item.get("id")
                self.redraw()
                
            if x > self.col0_width:
                if item["type"] == "property":
                    if item.get("choices") is not None:
                        # Natives Menü für Dropdowns (verhindert Fokus-Bugs)
                        if not item.get("readonly", False):
                            menu = tk.Menu(
                                self, 
                                tearoff=0, 
                                font=self.font,
                                bg=self.colors["bg_even"],
                                fg=self.colors["text_fg"],
                                activebackground="#0b57d0",
                                activeforeground="#ffffff",
                                relief="solid",
                                bd=1
                            )
                            for choice in item["choices"]:
                                menu.add_command(label=choice, command=lambda c=choice: self._set_choice_value(item, c))
                            
                            menu_x = self.canvas.winfo_rootx() + self.col0_width + 4
                            menu_y = self.canvas.winfo_rooty() + (r + 1) * self.row_height - int(self.canvas.canvasy(0)) - 4
                            menu.post(menu_x, menu_y)
                    else:
                        # We allow readonly properties to open an edit widget in readonly state for copying
                        self._start_edit(r, item)
                elif item["type"] == "boolean" and not item.get("readonly", False):
                    item["value"] = not item["value"]
                    if self.value_changed_callback:
                        self.value_changed_callback(item["id"], "True" if item["value"] else "False")
                    self.redraw()
                elif item["type"] == "button" and not item.get("readonly", False):
                    if item.get("callback"):
                        item["callback"]()
                    elif self.value_changed_callback:
                        self.value_changed_callback(item["id"], "clicked")
                elif item["type"] == "dialog" and not item.get("readonly", False):
                    if item.get("callback"):
                        item["callback"]()
                elif item["type"] == "color" and not item.get("readonly", False):
                    from tkinter import colorchooser
                    color_code = colorchooser.askcolor(title="Farbe wählen", initialcolor=item["value"], parent=self)
                    if color_code[1] is not None:
                        new_val = str(color_code[1]).lower()
                        if new_val != item["value"]:
                            item["value"] = new_val
                            if self.value_changed_callback:
                                self.value_changed_callback(item["id"], new_val)
                            self.redraw()
                elif item["type"] == "typeahead" and not item.get("readonly", False):
                    self._open_typeahead_popup(r, item)
            else:
                # If they click the label of a boolean, toggle it anyway
                if item["type"] == "boolean" and not item.get("readonly", False):
                    item["value"] = not item["value"]
                    if self.value_changed_callback:
                        self.value_changed_callback(item["id"], "True" if item["value"] else "False")
                    self.redraw()

    def _open_typeahead_popup(self, row, item):
        popup = tk.Toplevel(self)
        popup.wm_overrideredirect(True)
        # Position it exactly over the cell
        menu_x = self.canvas.winfo_rootx() + self.col0_width + 4
        menu_y = self.canvas.winfo_rooty() + row * self.row_height - int(self.canvas.canvasy(0))
        w = self.canvas.winfo_width() - self.col0_width - 1
        popup.wm_geometry(f"{w}x250+{menu_x}+{menu_y}")
        popup.configure(bg=self.colors["bg_even"], highlightbackground="#0b57d0", highlightthickness=1)
        
        entry = tk.Entry(popup, font=self.font, bg=self.colors["bg_even"], fg=self.colors["text_fg"], 
                         insertbackground=self.colors["text_fg"], relief="flat")
        entry.pack(fill=tk.X, padx=2, pady=2)
        
        list_frame = tk.Frame(popup, bg=self.colors["bg_even"])
        list_frame.pack(fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        listbox = tk.Listbox(list_frame, font=self.font, bg=self.colors["bg_even"], fg=self.colors["text_fg"], 
                             selectbackground="#0b57d0", selectforeground="#ffffff", relief="flat", highlightthickness=0,
                             yscrollcommand=scrollbar.set)
        listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=listbox.yview)
        
        all_choices = item.get("choices", [])
        current_val = item["value"]
        
        def update_list(*args):
            search = entry.get().lower()
            listbox.delete(0, tk.END)
            for c in all_choices:
                if search in c.lower():
                    listbox.insert(tk.END, c)
            
            if not search and current_val in all_choices:
                try:
                    idx = listbox.get(0, tk.END).index(current_val)
                    listbox.selection_set(idx)
                    listbox.see(idx)
                except ValueError:
                    pass
        
        update_list()
        
        def on_select(event):
            selection = listbox.curselection()
            if selection:
                val = listbox.get(selection[0])
                self._set_choice_value(item, val)
                popup.destroy()
                
        def on_enter(event):
            selection = listbox.curselection()
            if selection:
                val = listbox.get(selection[0])
                self._set_choice_value(item, val)
                popup.destroy()
            elif listbox.size() > 0:
                val = listbox.get(0)
                self._set_choice_value(item, val)
                popup.destroy()
                
        def on_focus_out(event):
            def check():
                try:
                    focus_widget = popup.focus_get()
                    if not focus_widget or str(focus_widget.winfo_toplevel()) != str(popup):
                        popup.destroy()
                except tk.TclError:
                    pass
            popup.after(100, check)

        listbox.bind("<<ListboxSelect>>", on_select)
        entry.bind("<KeyRelease>", update_list)
        entry.bind("<Return>", on_enter)
        entry.bind("<Escape>", lambda e: popup.destroy())
        entry.bind("<Down>", lambda e: listbox.focus_set() or listbox.selection_set(0))
        entry.bind("<FocusOut>", on_focus_out)
        listbox.bind("<FocusOut>", on_focus_out)
        entry.focus_set()

    def _start_edit(self, row, item):
        if self._edit_widget:
            self._commit_edit()
        self._cancel_edit()
        
        y1 = row * self.row_height
        w = self.canvas.winfo_width() - self.col0_width - 1
        h = self.row_height
        
        self._editing_row = row
        
        self._edit_widget = tk.Entry(self.canvas, font=self.font, bg=self.colors["input_bg"], fg=self.colors["text_fg"], relief="flat", insertbackground=self.colors["text_fg"])
        self._edit_widget.insert(0, item["value"])
        if item.get("readonly", False):
            self._edit_widget.config(state="readonly", readonlybackground=self.colors["input_bg"])
            
            menu_bg = "#2d2d2d" if self.colors["bg_even"] == "#1e1e1e" else "#ffffff"
            menu_fg = "#ffffff" if self.colors["bg_even"] == "#1e1e1e" else "#000000"
            menu = tk.Menu(self._edit_widget, tearoff=0, bg=menu_bg, fg=menu_fg, activebackground=self.colors["select_outline"], activeforeground="#ffffff")
            menu.add_command(label="Kopieren", command=lambda: self._copy_to_clipboard(item["value"]))
            self._edit_widget.bind("<Button-3>", lambda e: menu.post(e.x_root, e.y_root))
        else:
            self._edit_widget.bind("<Return>", self._commit_edit)
            
        self._edit_widget.bind("<FocusOut>", self._commit_edit)
        self._edit_widget.bind("<Escape>", lambda e: self._cancel_edit())
        
        self.canvas.update_idletasks()
        self._edit_window_id = self.canvas.create_window(
            self.col0_width + 1, y1, 
            window=self._edit_widget, 
            anchor="nw", 
            width=w, height=h
        )
        
        self._edit_widget.focus_set()
        if not item.get("readonly", False) and item["choices"] is None:
            self._edit_widget.selection_range(0, tk.END)

    def _copy_to_clipboard(self, text):
        self.clipboard_clear()
        self.clipboard_append(text)
        self.update()

    def _commit_edit(self, event=None):
        if self._edit_widget and self._editing_row is not None:
            new_val = self._edit_widget.get()
            item = self._data[self._editing_row]
            
            if new_val != item["value"]:
                item["value"] = new_val
                if self.value_changed_callback:
                    self.value_changed_callback(item["id"], new_val)
                    
            if event is not None:
                self.after(10, self._cancel_edit)

    def _cancel_edit(self):
        if self._edit_window_id:
            self.canvas.delete(self._edit_window_id)
            self._edit_window_id = None
        if self._edit_widget:
            self._edit_widget.destroy()
            self._edit_widget = None
        self._editing_row = None
        self.canvas.focus_set()
        self.redraw()