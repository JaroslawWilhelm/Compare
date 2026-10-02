import tkinter as tk
import math
from tkinter import ttk
import tkinter.font as tkfont

class RoundedButton(tk.Canvas):
    def __init__(self, parent, text, command=None, theme="blue", bg_light="#e1e4e8", bg_dark="#202124", fixed_width=None, **kwargs):
        self.bg_light = bg_light
        self.bg_dark = bg_dark
        self.btn_width = fixed_width if fixed_width else max(90, len(text) * 9 + 20)
        self.btn_height = 30
        
        if 'bg_color' in kwargs:
            bg = kwargs.pop('bg_color')
        else:
            bg = bg_light
            
        super().__init__(parent, bg=bg, highlightthickness=0, width=self.btn_width, height=self.btn_height, **kwargs)
        self.command = command
        self._theme_type = theme
        
        if theme == "blue":
            self.btn_bg = "#d3e3fd"
            self.btn_hover_bg = "#c2d8fb"
            self.btn_active_bg = "#abc9f8"
            self.btn_fg = "#0b57d0"
        elif theme == "primary":
            self.btn_bg = "#0b57d0"
            self.btn_hover_bg = "#094aae"
            self.btn_active_bg = "#073886"
            self.btn_fg = "#ffffff"
        else:
            self.btn_bg = "#3c4043"
            self.btn_hover_bg = "#5f6368"
            self.btn_active_bg = "#80868b"
            self.btn_fg = "#ffffff"
        
        self.font_size = 10
        self._btn_text = text
        self.create_rounded_rect(2, 2, self.btn_width-2, self.btn_height-2, r=6, fill=self.btn_bg, tags=("bg_shape",))
        self.text_item = self.create_text(self.btn_width//2, self.btn_height//2, text=text, font=("Arial", self.font_size, "bold"), fill=self.btn_fg)
        
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Enter>", self._on_enter)
        
        self._pressed = False
        
    def on_external_zoom(self, delta):
        # We assume the font_size is stored, or default to 10
        current_font_size = getattr(self, "font_size", 10)
        new_size = current_font_size + delta
        if 6 <= new_size <= 30:
            self.font_size = new_size
            scale = 1.1 if delta > 0 else (1 / 1.1)
            self.btn_width = max(30, int(round(self.btn_width * scale)))
            self.btn_height = max(15, int(round(self.btn_height * scale)))
            
            self.config(width=self.btn_width, height=self.btn_height)
            self.delete("all")
            
            fill_color = self.btn_active_bg if self._pressed else self.btn_bg
            self.create_rounded_rect(2, 2, self.btn_width-2, self.btn_height-2, r=6, fill=fill_color, tags=("bg_shape",))
            
            # Since RoundedButton didn't save text previously, grab it from text_item if needed,
            # or just use self._btn_text if we save it.
            text = getattr(self, "_btn_text", "Button")
            self.text_item = self.create_text(self.btn_width//2, self.btn_height//2, text=text, font=("Arial", self.font_size, "bold"), fill=self.btn_fg)
        
    def create_rounded_rect(self, x1, y1, x2, y2, r, fill, tags):
        points = []
        resolution = 10
        # Top-Left (180 to 90 degrees)
        for i in range(resolution + 1):
            angle = math.radians(180 - (90 * i / resolution))
            points.extend([x1 + r + r * math.cos(angle), y1 + r - r * math.sin(angle)])
        # Top-Right (90 to 0 degrees)
        for i in range(resolution + 1):
            angle = math.radians(90 - (90 * i / resolution))
            points.extend([x2 - r + r * math.cos(angle), y1 + r - r * math.sin(angle)])
        # Bottom-Right (0 to -90 degrees)
        for i in range(resolution + 1):
            angle = math.radians(- (90 * i / resolution))
            points.extend([x2 - r + r * math.cos(angle), y2 - r - r * math.sin(angle)])
        # Bottom-Left (270 to 180 degrees)
        for i in range(resolution + 1):
            angle = math.radians(270 - (90 * i / resolution))
            points.extend([x1 + r + r * math.cos(angle), y2 - r - r * math.sin(angle)])
            
        self.create_polygon(points, outline="", fill=fill, tags=tags, smooth=False)
        
    def _on_enter(self, event):
        self.config(cursor="hand2")
        if not self._pressed:
            self.itemconfig("bg_shape", fill=self.btn_hover_bg)
        
    def _on_press(self, event):
        self._pressed = True
        self.itemconfig("bg_shape", fill=self.btn_active_bg)
        
    def _on_leave(self, event):
        self._pressed = False
        self.itemconfig("bg_shape", fill=self.btn_bg)
        
    def _on_release(self, event):
        if self._pressed:
            def execute():
                if self.winfo_exists():
                    self.itemconfig("bg_shape", fill=self.btn_bg)
                if self.command:
                    self.command()
            self.after(150, execute)
            self._pressed = False

    def set_theme(self, theme_name):
        is_dark = (theme_name == "dark")
        self.config(bg=self.bg_dark if is_dark else self.bg_light)
        if self._theme_type == "blue":
            self.btn_bg = "#004a77" if is_dark else "#d3e3fd"
            self.btn_hover_bg = "#0062a3" if is_dark else "#c2d8fb"
            self.btn_active_bg = "#0078c8" if is_dark else "#abc9f8"
            self.btn_fg = "#4daafc" if is_dark else "#0b57d0"
        elif self._theme_type == "primary":
            self.btn_bg = "#66b2ff" if is_dark else "#0b57d0"
            self.btn_hover_bg = "#3399ff" if is_dark else "#094aae"
            self.btn_active_bg = "#0080ff" if is_dark else "#073886"
            self.btn_fg = "#000000" if is_dark else "#ffffff"
        else:
            self.btn_bg = "#3c4043" if is_dark else "#ffffff"
            self.btn_hover_bg = "#5f6368" if is_dark else "#e8eaed"
            self.btn_active_bg = "#80868b" if is_dark else "#dadce0"
            self.btn_fg = "#ffffff" if is_dark else "#3c4043"
            
        if not self._pressed:
            self.itemconfig("bg_shape", fill=self.btn_bg)
        self.itemconfig(self.text_item, fill=self.btn_fg)

import tkinter.font as tkfont

class ScalingCheckbox(tk.Canvas):
    def __init__(self, parent, text, variable, bg="#ffffff", fg="#333333", **kwargs):
        super().__init__(parent, bg=bg, highlightthickness=0, height=30, **kwargs)
        self.variable = variable
        self.text = text
        self.fg = fg
        self.bg_color = bg
        self.font_size = 11
        
        self.bind("<Button-1>", self.toggle)
        self.bind("<Enter>", lambda e: self.config(cursor="hand2"))
        
        self.variable.trace_add("write", self._on_var_changed)
        self._on_var_changed()
        
    def _on_var_changed(self, *args):
        self.delete("all")
        try:
            checked = self.variable.get()
        except:
            checked = False
            
        box_size = max(10, int(round(16 * (self.font_size / 11))))
        cy = max(10, int(round(15 * (self.font_size/11))))
        
        self.create_rectangle(2, cy - box_size//2, 2 + box_size, cy + box_size//2, outline="#a0a0a0", fill="#0b57d0" if checked else self.bg_color, width=2)
        if checked:
            check_font_size = max(8, int(round(12 * (self.font_size / 11))))
            self.create_text(2 + box_size//2, cy, text="✓", fill="#ffffff", font=("Segoe UI", check_font_size, "bold"))
            
        self.create_text(10 + box_size, cy, text=self.text, fill=self.fg, font=("Segoe UI", self.font_size), anchor="w")
        width = int(10 + box_size + len(self.text) * self.font_size * 0.75)
        self.config(width=width)
        
    def toggle(self, event):
        try:
            self.variable.set(not self.variable.get())
        except:
            pass
        
    def on_external_zoom(self, delta):
        new_size = self.font_size + delta
        if 6 <= new_size <= 30:
            self.font_size = new_size
            self.config(height=max(20, int(round(30 * (self.font_size/11)))))
            self._on_var_changed()
            
    def set_theme(self, theme):
        is_dark = (theme == "dark")
        self.bg_color = "#1e1e1e" if is_dark else "#f0f0f0"
        self.fg = "#ffffff" if is_dark else "#000000"
        self.config(bg=self.bg_color)
        self._on_var_changed()
            
class ScalingRadiobutton(ScalingCheckbox):
    def __init__(self, parent, text, variable, value, bg="#ffffff", fg="#333333", **kwargs):
        self.value = value
        super().__init__(parent, text, variable, bg, fg, **kwargs)
        
    def _on_var_changed(self, *args):
        self.delete("all")
        try:
            checked = (str(self.variable.get()) == str(self.value))
        except:
            checked = False
            
        box_size = max(10, int(round(16 * (self.font_size / 11))))
        cy = max(10, int(round(15 * (self.font_size/11))))
        
        self.create_oval(2, cy - box_size//2, 2 + box_size, cy + box_size//2, outline="#a0a0a0", fill=self.bg_color, width=2)
        if checked:
            inner_size = box_size // 2
            self.create_oval(2 + box_size//2 - inner_size//2, cy - inner_size//2, 2 + box_size//2 + inner_size//2, cy + inner_size//2, fill="#0b57d0", outline="")
            
        self.create_text(10 + box_size, cy, text=self.text, fill=self.fg, font=("Segoe UI", self.font_size), anchor="w")
        width = int(10 + box_size + len(self.text) * self.font_size * 0.75)
        self.config(width=width)
        
    def toggle(self, event):
        try:
            self.variable.set(self.value)
        except:
            pass

class ZoomManager:
    """
    Verwaltet das rekursive Zoomen (Strg+Mausrad) von Standard-Tkinter-Widgets
    wie Labels, Buttons, Entries in Containern oder Dialogen.
    """
    GLOBAL_STATES = {}

    def __init__(self, root_widget, zoom_id=None):
        self.root = root_widget
        self.zoom_id = zoom_id
        self.total_zoom_delta = 0
        self._bind_tree(self.root)
        
        # Initialen Zoom anwenden, falls vorhanden
        if self.zoom_id and self.zoom_id in self.GLOBAL_STATES:
            saved_delta = self.GLOBAL_STATES[self.zoom_id]
            self.apply_absolute_zoom(saved_delta)

    def _bind_tree(self, widget):
        # Eigene Canvas-Widgets, die Zoom selbst verwalten, überspringen (außer root)
        if hasattr(widget, "_on_zoom") and widget != self.root:
            return
            
        widget.bind("<Control-MouseWheel>", self._on_zoom)
        widget.bind("<Control-Button-4>", self._on_zoom)
        widget.bind("<Control-Button-5>", self._on_zoom)
        
        for child in widget.winfo_children():
            self._bind_tree(child)

    def _on_zoom(self, event):
        delta = 1 if (event.delta > 0 or getattr(event, 'num', 0) == 4) else -1
        self._apply_zoom(self.root, delta)
        self.total_zoom_delta += delta
        if self.zoom_id:
            self.GLOBAL_STATES[self.zoom_id] = self.total_zoom_delta

    def apply_absolute_zoom(self, total_delta):
        """Wendet einen absoluten Zoom-Wert an (z.B. +3), indem delta-Schritte simuliert werden."""
        if total_delta > 0:
            for _ in range(total_delta):
                self._apply_zoom(self.root, 1)
                self.total_zoom_delta += 1
        elif total_delta < 0:
            for _ in range(abs(total_delta)):
                self._apply_zoom(self.root, -1)
                self.total_zoom_delta -= 1
        
        if self.zoom_id:
            self.GLOBAL_STATES[self.zoom_id] = self.total_zoom_delta

    def _apply_zoom(self, widget, delta):
        if hasattr(widget, "on_external_zoom"):
            widget.on_external_zoom(delta)
            return

        # Eigene Canvas-Widgets, die Zoom selbst verwalten, überspringen
        if hasattr(widget, "_on_zoom") and widget != self.root:
            return
            
        try:
            is_treeview = isinstance(widget, ttk.Treeview)
            current_font = None
            style_name = None
            
            if is_treeview:
                style_name = widget.cget("style") or "Treeview"
                current_font = ttk.Style().lookup(style_name, "font")
                if not current_font:
                    current_font = ("Segoe UI", 11)
            elif "font" in widget.keys():
                current_font = widget.cget("font")

            if current_font:
                try:
                    actual_font = tkfont.nametofont(current_font)
                except tk.TclError:
                    actual_font = tkfont.Font(font=current_font)
                    
                size = actual_font.cget("size")
                # Tkinter fonts können negativ (Pixel) oder positiv (Punkte) sein.
                is_negative = (size < 0)
                abs_size = abs(size)
                
                new_size = abs_size + delta
                if 6 <= new_size <= 30:
                    final_size = -new_size if is_negative else new_size
                    
                    font_family = actual_font.cget("family")
                    font_weight = actual_font.cget("weight")
                    font_slant = actual_font.cget("slant")
                    
                    modifiers = []
                    if font_weight == "bold": modifiers.append("bold")
                    if font_slant == "italic": modifiers.append("italic")
                    
                    if modifiers:
                        new_font = (font_family, final_size, " ".join(modifiers))
                    else:
                        new_font = (font_family, final_size)
                        
                    if is_treeview:
                        # Rowheight leicht skalieren für bessere Lesbarkeit
                        new_rowheight = max(20, int(abs(final_size) * 2.5))
                        ttk.Style().configure(style_name, font=new_font, rowheight=new_rowheight)
                        if hasattr(widget, "update_tags_font_size"):
                            widget.update_tags_font_size(final_size)
                    else:
                        widget.config(font=new_font)
        except Exception:
            pass
            
        for child in widget.winfo_children():
            self._apply_zoom(child, delta)

