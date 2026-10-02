import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import tkinter.font as tkfont
import os
import sys
import json
import stat
import hmac
import hashlib
from tkinter import simpledialog

try:
    import zoneinfo
    tz_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "iana_tzdata")
    
    def _get_timezones():
        timezones = set()
        if os.path.isdir(tz_path):
            zoneinfo.reset_tzpath((tz_path,))
            try:
                timezones = set(zoneinfo.available_timezones())
            except Exception:
                pass
                
        if len(timezones) < 10 and os.path.isdir(tz_path):
            for root, dirs, files in os.walk(tz_path):
                for file in files:
                    if file.endswith(".tab") or file.endswith(".zi") or file.startswith("__"):
                        continue
                    rel_path = os.path.relpath(os.path.join(root, file), tz_path)
                    tz_name = rel_path.replace(os.sep, "/")
                    if tz_name != "leapseconds":
                        timezones.add(tz_name)
                        
        if not timezones:
            return ["UTC"]
        return sorted(list(timezones))
        
    AVAILABLE_TIMEZONES = _get_timezones()
except Exception as e:
    print(f"Error loading timezones: {e}")
    AVAILABLE_TIMEZONES = ["UTC"]
from ui_components import ZoomManager, ScalingCheckbox, ScalingRadiobutton
from grid_widget import ComplianceGrid
from tree_widget import FileStructureTree
from property_grid import TkPropertyGrid
from file_structure import DataNode, SingleFileViewModel
from virtual_list import MemoryVirtualList
from file_parsing_config_t import FileParsingConfig
from sheet_mapping import SheetMappingView
from row_mapping import RowMappingView
from column_mapping import ColumnMappingView
from comparison_mapping import ComparisonLogicView
from column_casting import ColumnCastingView
from finish_tab import FinishTab

import math

class TabButton(tk.Canvas):
    _instances = []
    global_font_size = 11
    global_scale = 1.0

    def __init__(self, parent, text, index, command=None, bg_color="#f8f9fa", fixed_width=None, **kwargs):
        self._original_fixed_width = fixed_width
        self.index = index
        self._btn_text = text
        self.command = command
        
        from ui_components import ZoomManager
        if "tabs" in ZoomManager.GLOBAL_STATES and TabButton.global_font_size == 11:
            delta = ZoomManager.GLOBAL_STATES["tabs"]
            TabButton.global_font_size = 11 + delta
            TabButton.global_scale = (1.1 ** delta)
        
        self.btn_width = self._calc_width()
        self.btn_height = self._calc_height()
        
        super().__init__(parent, bg=bg_color, highlightthickness=0, width=self.btn_width, height=self.btn_height, **kwargs)
        
        TabButton._instances.append(self)
        self.bind("<Destroy>", self._on_destroy, add="+")
        
        self.color_inactive_bg = "#e0e0e0"
        self.color_inactive_fg = "#5f6368"
        self.color_active_bg = "#0b57d0"
        self.color_active_fg = "#ffffff"
        self.color_hover_bg = "#d5d5d5"
        
        self.is_active = False
        
        self.create_rounded_rect(2, 2, self.btn_width-2, self.btn_height-2, r=6, fill=self.color_inactive_bg, tags=("bg_shape",))
        self.text_item = self.create_text(self.btn_width//2, self.btn_height//2 - 1, text=self._btn_text, font=("Arial", TabButton.global_font_size), fill=self.color_inactive_fg)
        
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Control-MouseWheel>", self._on_zoom)

    def _on_destroy(self, event):
        if event.widget == self and self in TabButton._instances:
            TabButton._instances.remove(self)

    def _calc_width(self):
        scale = TabButton.global_scale
        if self._original_fixed_width:
            return max(30, int(round(self._original_fixed_width * scale)))
        else:
            base_w = max(100, len(self._btn_text) * 8 + 20)
            return max(30, int(round(base_w * scale)))

    def _calc_height(self):
        return max(15, int(round(28 * TabButton.global_scale)))

    def _on_zoom(self, event):
        delta = 1 if event.delta > 0 else -1
        if (TabButton.global_font_size <= 6 and delta < 0) or (TabButton.global_font_size >= 30 and delta > 0): return
        
        TabButton.global_font_size += delta
        TabButton.global_scale *= 1.1 if delta > 0 else (1 / 1.1)
        
        from ui_components import ZoomManager
        ZoomManager.GLOBAL_STATES["tabs"] = TabButton.global_font_size - 11
        
        for inst in TabButton._instances:
            try:
                inst.apply_zoom()
            except Exception:
                pass

    def apply_zoom(self):
        self.btn_width = self._calc_width()
        self.btn_height = self._calc_height()
        
        self.config(width=self.btn_width, height=self.btn_height)
        self.delete("all")
        
        fill_color = self.color_active_bg if self.is_active else self.color_inactive_bg
        text_color = self.color_active_fg if self.is_active else self.color_inactive_fg
        
        self.create_rounded_rect(2, 2, self.btn_width-2, self.btn_height-2, r=6, fill=fill_color, tags=("bg_shape",))
        self.text_item = self.create_text(self.btn_width//2, self.btn_height//2 - 1, text=self._btn_text, font=("Arial", TabButton.global_font_size), fill=text_color)
        
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
        
    def set_active(self, active):
        self.is_active = active
        if active:
            self.itemconfig("bg_shape", fill=self.color_active_bg)
            self.itemconfig(self.text_item, fill=self.color_active_fg)
        else:
            self.itemconfig("bg_shape", fill=self.color_inactive_bg)
            self.itemconfig(self.text_item, fill=self.color_inactive_fg)
            
    def _on_enter(self, event):
        self.config(cursor="hand2")
        if not self.is_active:
            self.itemconfig("bg_shape", fill=self.color_hover_bg)

    def _on_leave(self, event):
        if not self.is_active:
            self.itemconfig("bg_shape", fill=self.color_inactive_bg)
            
    def _on_press(self, event):
        if not self.is_active:
            self.itemconfig("bg_shape", fill=self.color_active_bg)
        
    def _on_release(self, event):
        if self.command:
            self.command(self.index)

    def set_theme(self, theme_name):
        is_dark = (theme_name == "dark")
        self.config(bg="#1e1e1e" if is_dark else "#f8f9fa")
        
        self.color_inactive_bg = "#2d2d2d" if is_dark else "#e0e0e0"
        self.color_inactive_fg = "#a0a0a0" if is_dark else "#5f6368"
        self.color_active_bg = "#004a77" if is_dark else "#0b57d0"
        self.color_active_fg = "#ffffff" if is_dark else "#ffffff"
        self.color_hover_bg = "#3a3a3a" if is_dark else "#d5d5d5"
        
        self.set_active(self.is_active)

class CustomDropdownMenu(tk.Toplevel):
    def __init__(self, parent, app, bg="#ffffff", fg="#000000", active_bg="#0b57d0", active_fg="#ffffff"):
        super().__init__(parent)
        self.app = app
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        
        self.bg = bg
        self.fg = fg
        self.active_bg = active_bg
        self.active_fg = active_fg
        
        self.border_frame = tk.Frame(self, bg="#cccccc", bd=1)
        self.border_frame.pack(fill=tk.BOTH, expand=True)
        
        self.main_frame = tk.Frame(self.border_frame, bg=self.bg)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)
        
        self.withdraw()
        self.bind("<FocusOut>", lambda e: self.hide())
        
    def add_command(self, label, command, accelerator=None):
        frame = tk.Frame(self.main_frame, bg=self.bg)
        frame.pack(fill=tk.X)
        
        lbl = tk.Label(frame, text=label, bg=self.bg, fg=self.fg, font=("Segoe UI", 10), anchor="w", padx=20, pady=5)
        lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        lbl_acc = None
        if accelerator:
            lbl_acc = tk.Label(frame, text=accelerator, bg=self.bg, fg=self.fg, font=("Segoe UI", 10), padx=10, pady=5)
            lbl_acc.pack(side=tk.RIGHT)
            
        def on_enter(e):
            frame.config(bg=self.active_bg)
            lbl.config(bg=self.active_bg, fg=self.active_fg)
            if lbl_acc: lbl_acc.config(bg=self.active_bg, fg=self.active_fg)
            
        def on_leave(e):
            frame.config(bg=self.bg)
            lbl.config(bg=self.bg, fg=self.fg)
            if lbl_acc: lbl_acc.config(bg=self.bg, fg=self.fg)
            
        def on_click(e):
            self.hide()
            self.app._close_menubar()
            command()
            
        for w in (frame, lbl, lbl_acc):
            if w:
                w.bind("<Enter>", on_enter)
                w.bind("<Leave>", on_leave)
                w.bind("<Button-1>", on_click)
                
    def add_separator(self):
        sep = tk.Frame(self.main_frame, height=1, bg="#e0e0e0")
        sep.pack(fill=tk.X, padx=5, pady=2)
        
    def config(self, bg=None, fg=None, activebackground=None, activeforeground=None, **kwargs):
        if bg: self.bg = bg
        if fg: self.fg = fg
        if activebackground: self.active_bg = activebackground
        if activeforeground: self.active_fg = activeforeground
        
        self.main_frame.config(bg=self.bg)
        self.border_frame.config(bg="#444" if self.bg == "#2d2d2d" else "#cccccc")
        for child in self.main_frame.winfo_children():
            if child.winfo_class() == 'Frame':
                if child.winfo_height() == 1:
                    child.config(bg="#444" if self.bg == "#2d2d2d" else "#e0e0e0")
                else:
                    child.config(bg=self.bg)
                    for lbl in child.winfo_children():
                        lbl.config(bg=self.bg, fg=self.fg)
                        
    def post(self, x, y):
        self.geometry(f"+{x}+{y}")
        self.deiconify()
        self.focus_set()
        
    def hide(self):
        if self.winfo_ismapped():
            self.withdraw()
            self.after(10, self._check_deactivate)
            
    def _check_deactivate(self):
        if self.app._menubar_active:
            any_mapped = any(m["menu"].winfo_ismapped() for m in self.app._menubar_buttons.values())
            if not any_mapped:
                self.app._menubar_active = False
                self.app._menubar_active_menu = None

class Application(tk.Tk):
    """
    Main Application window for the Dual-Grid Audit & Compliance Comparison tool.
    Orchestrates the Model, View, and Data layers.
    """
    
    def __init__(self):
        super().__init__()
        self.title("Dual-Grid Audit & Compliance Comparison")
        self.geometry("1200x600")
        
        # Super-Performant Global Resizer (like VS Code / Libre Office)
        self.config(bg="#ecf0f1") # Default background for the "empty" space while resizing
        self.root_frame = tk.Frame(self, bg=self["bg"])
        self.root_frame.place(x=0, y=0, width=1200, height=600)
        
        # --- Konfigurationsobjekte (100% Python Standard Lib!) ---
        self.config1 = FileParsingConfig()
        self.config2 = FileParsingConfig()

        self.v_list1 = None
        self.v_list2 = None
        self.current_theme = "light"
        
        self._debounce_timer = None
        self._target_width = 1200
        self._target_height = 600
        
        # Load zoom states before UI is initialized so widgets can use them in __init__
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "layout_config.json")
        if os.path.exists(config_path):
            try:
                import json
                with open(config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                if "zoom_states" in config:
                    from ui_components import ZoomManager
                    ZoomManager.GLOBAL_STATES.update(config["zoom_states"])
                if "colors1" in config:
                    colors1 = config["colors1"]
                    if "color_true" in colors1: self.config1.color_true = colors1["color_true"]
                    if "color_false" in colors1: self.config1.color_false = colors1["color_false"]
                    if "color_not_comp" in colors1: self.config1.color_not_comp = colors1["color_not_comp"]
                    if "color_count_diff" in colors1: self.config1.color_count_diff = colors1["color_count_diff"]
                if "colors2" in config:
                    colors2 = config["colors2"]
                    if "color_true" in colors2: self.config2.color_true = colors2["color_true"]
                    if "color_false" in colors2: self.config2.color_false = colors2["color_false"]
                    if "color_not_comp" in colors2: self.config2.color_not_comp = colors2["color_not_comp"]
                    if "color_count_diff" in colors2: self.config2.color_count_diff = colors2["color_count_diff"]
            except Exception as e:
                print(f"Error pre-loading layout configs: {e}")
        
        self._setup_ui()
        self.load_layout()
        #self._load_initial_dummy_data()
        self.bind("<Configure>", self._on_root_configure)
        self.protocol("WM_DELETE_WINDOW", self._on_closing)
        
        # Automatisch Dialoge für Datei-Load beim Start anzeigen
        self.after(200, self._prompt_initial_files)

    def _prompt_initial_files(self):
        """Fragt nacheinander die Ziel- und Ist-Datei beim Start ab, wenn noch keine geladen ist."""
        if getattr(self, 'v_list1', None) is None:
            self.cmd_load_file(1)
            # Falls Datei 1 erfolgreich geladen wurde, frage nach Datei 2
            if getattr(self, 'v_list1', None) is not None:
                self.after(100, lambda: self.cmd_load_file(2))

    def _on_root_configure(self, event):
        """Asynchronous Geometry Decoupling: Lets the OS scale smoothly and computes only once."""
        if event.widget == self:
            if event.width == self._target_width and event.height == self._target_height:
                return
            
            self._target_width = event.width
            self._target_height = event.height
            
            if self._debounce_timer:
                self.after_cancel(self._debounce_timer)
            # 80ms is usually fast enough to feel responsive, but slow enough to group rapid OS events
            self._debounce_timer = self.after(80, self._apply_resize)

    def _apply_resize(self):
        """Applies the new dimensions to the actual layout engine once the user stops dragging."""
        self.root_frame.place(width=self._target_width, height=self._target_height)
        self.update_idletasks()

    def load_layout(self):
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "layout_config.json")
        if not os.path.exists(config_path):
            return
            
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
                
            if "geometry" in config:
                self.geometry(config["geometry"])
            
            if "state" in config and config["state"] in ("zoomed", "normal"):
                self.state(config["state"])
                
            if "tab_sash_states" in config:
                self._tab_sash_states = {int(k): v for k, v in config["tab_sash_states"].items()}
                if hasattr(self, '_current_tab_index') and self._current_tab_index in self._tab_sash_states:
                    state = self._tab_sash_states[self._current_tab_index]
                    self._apply_sash_state(state, self._current_tab_index)
                    
            if "theme" in config:
                self.set_theme(config["theme"])
                
        except Exception as e:
            print(f"Error loading layout: {e}")

    def save_layout(self):
        if hasattr(self, '_current_tab_index'):
            self._save_sash_state(self._current_tab_index)
            
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "layout_config.json")
        
        from ui_components import ZoomManager
        config = {
            "geometry": self.geometry(),
            "state": self.state(),
            "tab_sash_states": getattr(self, "_tab_sash_states", {}),
            "theme": getattr(self, "current_theme", "light"),
            "zoom_states": ZoomManager.GLOBAL_STATES,
            "colors1": {
                "color_true": self.config1.color_true,
                "color_false": self.config1.color_false,
                "color_not_comp": self.config1.color_not_comp,
                "color_count_diff": self.config1.color_count_diff
            },
            "colors2": {
                "color_true": self.config2.color_true,
                "color_false": self.config2.color_false,
                "color_not_comp": self.config2.color_not_comp,
                "color_count_diff": self.config2.color_count_diff
            }
        }
        
        try:
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=4)
        except Exception as e:
            print(f"Error saving layout: {e}")
            
    def _on_menubar_click(self, menu_name):
        if self._menubar_active and self._menubar_active_menu == menu_name:
            self._close_menubar()
            return
            
        self._menubar_active = True
        self._menubar_active_menu = menu_name
        self._show_active_menu()

    def _on_menubar_enter(self, menu_name):
        if self._menubar_active and self._menubar_active_menu != menu_name:
            self._menubar_active_menu = menu_name
            self._show_active_menu()
            
    def _show_active_menu(self):
        for m_name, m_data in self._menubar_buttons.items():
            if m_name != self._menubar_active_menu:
                m_data["menu"].hide()
                
        if self._menubar_active_menu:
            btn = self._menubar_buttons[self._menubar_active_menu]["btn"]
            menu = self._menubar_buttons[self._menubar_active_menu]["menu"]
            menu.post(btn.winfo_rootx(), btn.winfo_rooty() + btn.winfo_height())
            
    def _close_menubar(self):
        self._menubar_active = False
        self._menubar_active_menu = None
        for m_data in self._menubar_buttons.values():
            m_data["menu"].hide()

    def _on_closing(self):
        self.save_layout()
        self.destroy()

    def set_theme(self, theme):
        is_dark = (theme == "dark")
        self.current_theme = theme
        
        bg_main = "#1e1e1e" if is_dark else "#ffffff"
        bg_pane = "#2d2d2d" if is_dark else "#dcdcdc"
        bg_sash = "#555555" if is_dark else "#dcdcdc"
        fg_text = "#e0e0e0" if is_dark else "#1f1f1f"
        
        self.config(bg=bg_main)
        
        # Style custom menubar and popups
        menu_bg = "#202124" if is_dark else "#f8f9fa"  # slightly darker for dark mode top bar
        menu_fg = "#ffffff" if is_dark else "#000000"
        menu_hover_bg = "#3c4043" if is_dark else "#e0e0e0"
        popup_active_bg = "#004a77" if is_dark else "#cce8ff"
        popup_active_fg = "#ffffff" if is_dark else "#000000"

        if hasattr(self, 'menubar_frame'):
            self.menubar_frame.config(bg=menu_bg)
            
        for btn_name in ['btn_file', 'btn_view', 'btn_design']:
            if hasattr(self, btn_name):
                getattr(self, btn_name).config(
                    bg=menu_bg, fg=menu_fg, 
                    activebackground=menu_hover_bg, activeforeground=menu_fg
                )
                
        if hasattr(self, 'file_menu'):
            self.file_menu.config(bg=menu_bg, fg=menu_fg, activebackground=popup_active_bg, activeforeground=popup_active_fg)
        if hasattr(self, 'view_menu'):
            self.view_menu.config(bg=menu_bg, fg=menu_fg, activebackground=popup_active_bg, activeforeground=popup_active_fg)
        if hasattr(self, 'design_menu'):
            self.design_menu.config(bg=menu_bg, fg=menu_fg, activebackground=popup_active_bg, activeforeground=popup_active_fg)
        
        # Apply Windows Dark Mode Title Bar
        try:
            import ctypes
            self.update_idletasks()
            hwnd = ctypes.windll.user32.GetParent(self.winfo_id())
            rendering_policy = ctypes.c_int(1 if is_dark else 0)
            # DWMWA_USE_IMMERSIVE_DARK_MODE is 20 in Windows 11, 19 in older Windows 10
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(rendering_policy), ctypes.sizeof(rendering_policy))
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 19, ctypes.byref(rendering_policy), ctypes.sizeof(rendering_policy))
        except Exception:
            pass
        
        style = ttk.Style()
        
        if is_dark:
            style.configure(".", font=("Segoe UI", 11), background=bg_main, foreground=fg_text)
            style.configure("Treeview", background="#252525", foreground="#e0e0e0", fieldbackground="#252525", rowheight=28)
            style.configure("Treeview.Heading", background="#2d2d2d", foreground="#ffffff")
        else:
            style.configure(".", font=("Segoe UI", 11), background=bg_main, foreground=fg_text)
            style.configure("Treeview", background="#ffffff", foreground="#000000", fieldbackground="#ffffff", rowheight=28)
            style.configure("Treeview.Heading", background="#f0f0f0", foreground="#000000")
            
        # Fix for Windows Treeview fieldbackground bug
        # The native Windows 'vista' theme hardcodes the Treeview.field element to be white, ignoring our styles.
        # Removing Treeview.field from the layout allows our custom fieldbackground to take effect.
        style.layout("Treeview", [('Treeview.treearea', {'sticky': 'nswe'})])
        style.map("Treeview",
                  background=[("selected", "#004a77" if is_dark else "#cce8ff")],
                  foreground=[("selected", "#ffffff" if is_dark else "#000000")],
                  fieldbackground=[("!disabled", "#252525" if is_dark else "#ffffff")])
                  
        # Fix for Windows native scrollbars and Treeview headings ignoring dark mode styling
        if not hasattr(self, "_native_elements_replaced"):
            try:
                # Scrollbars
                style.element_create('Custom.Vertical.Scrollbar.trough', 'from', 'clam')
                style.element_create('Custom.Vertical.Scrollbar.thumb', 'from', 'clam')
                style.element_create('Custom.Vertical.Scrollbar.uparrow', 'from', 'clam')
                style.element_create('Custom.Vertical.Scrollbar.downarrow', 'from', 'clam')
                style.layout('Vertical.TScrollbar', [
                    ('Custom.Vertical.Scrollbar.trough', {'sticky': 'ns', 'children': [
                        ('Custom.Vertical.Scrollbar.uparrow', {'side': 'top', 'sticky': ''}),
                        ('Custom.Vertical.Scrollbar.downarrow', {'side': 'bottom', 'sticky': ''}),
                        ('Custom.Vertical.Scrollbar.thumb', {'expand': '1', 'sticky': 'nswe'})
                    ]})
                ])
                style.element_create('Custom.Horizontal.Scrollbar.trough', 'from', 'clam')
                style.element_create('Custom.Horizontal.Scrollbar.thumb', 'from', 'clam')
                style.element_create('Custom.Horizontal.Scrollbar.leftarrow', 'from', 'clam')
                style.element_create('Custom.Horizontal.Scrollbar.downarrow', 'from', 'clam')
                style.layout('Horizontal.TScrollbar', [
                    ('Custom.Horizontal.Scrollbar.trough', {'sticky': 'we', 'children': [
                        ('Custom.Horizontal.Scrollbar.uparrow', {'side': 'left', 'sticky': ''}),
                        ('Custom.Horizontal.Scrollbar.downarrow', {'side': 'right', 'sticky': ''}),
                        ('Custom.Horizontal.Scrollbar.thumb', {'expand': '1', 'sticky': 'nswe'})
                    ]})
                ])
                
                # Checkbutton & Radiobutton
                style.element_create('Custom.Checkbutton.indicator', 'from', 'clam')
                style.layout('TCheckbutton', [
                    ('Checkbutton.padding', {'sticky': 'nswe', 'children': [
                        ('Custom.Checkbutton.indicator', {'side': 'left', 'sticky': ''}),
                        ('Checkbutton.focus', {'side': 'left', 'sticky': '', 'children': [
                            ('Checkbutton.label', {'sticky': 'nswe'})
                        ]})
                    ]})
                ])
                
                style.element_create('Custom.Radiobutton.indicator', 'from', 'clam')
                style.layout('TRadiobutton', [
                    ('Radiobutton.padding', {'sticky': 'nswe', 'children': [
                        ('Custom.Radiobutton.indicator', {'side': 'left', 'sticky': ''}),
                        ('Radiobutton.focus', {'side': 'left', 'sticky': '', 'children': [
                            ('Radiobutton.label', {'sticky': 'nswe'})
                        ]})
                    ]})
                ])
                
                # Combobox
                style.element_create('Custom.Combobox.downarrow', 'from', 'clam')
                style.element_create('Custom.Combobox.field', 'from', 'clam')
                style.element_create('Custom.Combobox.padding', 'from', 'clam')
                style.layout('TCombobox', [
                    ('Custom.Combobox.downarrow', {'side': 'right', 'sticky': 'ns'}),
                    ('Custom.Combobox.field', {'sticky': 'nswe', 'children': [
                        ('Custom.Combobox.padding', {'sticky': 'nswe', 'children': [
                            ('Combobox.textarea', {'sticky': 'nswe'})
                        ]})
                    ]})
                ])

                # Treeview Headings
                style.element_create('Custom.Treeheading.cell', 'from', 'clam')
                style.element_create('Custom.Treeheading.border', 'from', 'clam')
                style.element_create('Custom.Treeheading.padding', 'from', 'clam')
                style.element_create('Custom.Treeheading.image', 'from', 'clam')
                style.element_create('Custom.Treeheading.text', 'from', 'clam')
                style.layout('Treeview.Heading', [
                    ('Custom.Treeheading.cell', {'sticky': 'nswe'}),
                    ('Custom.Treeheading.border', {'sticky': 'nswe', 'children': [
                        ('Custom.Treeheading.padding', {'sticky': 'nswe', 'children': [
                            ('Custom.Treeheading.image', {'side': 'right', 'sticky': ''}),
                            ('Custom.Treeheading.text', {'sticky': 'we'})
                        ]})
                    ]})
                ])
                
                self._native_elements_replaced = True
            except tk.TclError:
                pass
                
        if is_dark:
            style.configure('TScrollbar', background='#404040', troughcolor='#1e1e1e', arrowcolor='#ffffff', bordercolor='#1e1e1e', relief='flat')
            style.map('TScrollbar', background=[('active', '#555555'), ('pressed', '#777777')])
            style.configure('TCheckbutton', background=bg_main, foreground=fg_text)
            style.map('TCheckbutton', indicatorbackground=[('selected', '#0b57d0'), ('!selected', '#2d2d2d'), ('disabled', '#252525')], indicatorcolor=[('selected', '#ffffff'), ('!selected', '#2d2d2d'), ('disabled', '#252525')], foreground=[('disabled', '#777777')])
            style.configure('TRadiobutton', background=bg_main, foreground=fg_text)
            style.map('TRadiobutton', indicatorbackground=[('selected', '#0b57d0'), ('!selected', '#2d2d2d'), ('disabled', '#252525')], indicatorcolor=[('selected', '#ffffff'), ('!selected', '#2d2d2d'), ('disabled', '#252525')], foreground=[('disabled', '#777777')])
            style.configure('TCombobox', fieldbackground=bg_main, background=bg_pane, foreground=fg_text, arrowcolor=fg_text, bordercolor=bg_main)
            style.map('TCombobox', fieldbackground=[('readonly', bg_main), ('disabled', '#252525')], foreground=[('disabled', '#777777')], background=[('active', '#404040')])
            
            # Style the internal popdown listbox of ttk.Combobox
            self.option_add('*TCombobox*Listbox.background', bg_main)
            self.option_add('*TCombobox*Listbox.foreground', fg_text)
            self.option_add('*TCombobox*Listbox.selectBackground', '#0b57d0')
            self.option_add('*TCombobox*Listbox.selectForeground', '#ffffff')
        else:
            style.configure('TScrollbar', background='#d0d0d0', troughcolor='#f8f9fa', arrowcolor='#333333', bordercolor='#f8f9fa', relief='flat')
            style.map('TScrollbar', background=[('active', '#b0b0b0'), ('pressed', '#909090')])
            style.configure('TCheckbutton', background=bg_main, foreground=fg_text)
            style.map('TCheckbutton', indicatorbackground=[('selected', '#0b57d0'), ('!selected', '#ffffff'), ('disabled', '#f0f0f0')], indicatorcolor=[('selected', '#ffffff'), ('!selected', '#ffffff'), ('disabled', '#f0f0f0')], foreground=[('disabled', '#777777')])
            style.configure('TRadiobutton', background=bg_main, foreground=fg_text)
            style.map('TRadiobutton', indicatorbackground=[('selected', '#0b57d0'), ('!selected', '#ffffff'), ('disabled', '#f0f0f0')], indicatorcolor=[('selected', '#ffffff'), ('!selected', '#ffffff'), ('disabled', '#f0f0f0')], foreground=[('disabled', '#777777')])
            style.configure('TCombobox', fieldbackground='#ffffff', background='#f0f0f0', foreground='#000000', arrowcolor='#000000', bordercolor='#cccccc')
            style.map('TCombobox', fieldbackground=[('readonly', '#ffffff'), ('disabled', '#f0f0f0')], foreground=[('disabled', '#777777')], background=[('active', '#e0e0e0')])
            
            self.option_add('*TCombobox*Listbox.background', '#ffffff')
            self.option_add('*TCombobox*Listbox.foreground', '#000000')
            self.option_add('*TCombobox*Listbox.selectBackground', '#0b57d0')
            self.option_add('*TCombobox*Listbox.selectForeground', '#ffffff')
            
        def _apply_colors(w):
            # If the widget has its own set_theme (e.g. ComplianceGrid, FileStructureTree, PropertyGrid, Toolbar Buttons)
            if hasattr(w, "set_theme") and callable(w.set_theme) and w != self:
                try:
                    w.set_theme(theme)
                except Exception as e:
                    print(f"Error applying theme to {w}: {e}")
                return 

            wtype = w.winfo_class()
            
            current_bg = bg_main
            current_fg = fg_text
            
            is_separator = False
            try:
                if wtype == "Frame" and int(w.winfo_height()) in (1, 2):
                    if w.master == getattr(self, "root_frame", None):
                        is_separator = True
            except tk.TclError:
                pass

            if wtype in ("Frame", "Label", "Canvas", "Button", "Entry", "Checkbutton", "Radiobutton", "Toplevel", "Spinbox", "Listbox", "Text"):
                if not is_separator:
                    try:
                        # Protect the menubar_frame from being overridden by the main background color
                        if w == getattr(self, "menubar_frame", None):
                            pass
                        elif wtype == "Button":
                            btn_bg = "#3c4043" if is_dark else "#e0e0e0"
                            btn_fg = "#ffffff" if is_dark else "#000000"
                            btn_active_bg = "#5f6368" if is_dark else "#d0d0d0"
                            w.config(bg=btn_bg, fg=btn_fg, activebackground=btn_active_bg, activeforeground=btn_fg, relief="flat")
                        else:
                            w.config(bg=current_bg)
                            
                        if wtype in ("Entry", "Checkbutton", "Radiobutton", "Spinbox", "Text"):
                            w.config(fg=current_fg, insertbackground=current_fg, selectbackground="#0b57d0", selectforeground="#ffffff")
                            if wtype in ("Entry", "Spinbox"):
                                if is_dark:
                                    w.config(disabledbackground="#252525", disabledforeground="#777777", readonlybackground="#252525")
                                else:
                                    w.config(disabledbackground="#f0f0f0", disabledforeground="#888888", readonlybackground="#f0f0f0")
                            if wtype == "Spinbox":
                                w.config(buttonbackground=current_bg)
                            if wtype in ("Checkbutton", "Radiobutton"):
                                w.config(selectcolor=bg_pane)
                        elif wtype == "Listbox":
                            w.config(fg=current_fg, selectbackground="#0b57d0", selectforeground="#ffffff")
                    except tk.TclError: pass
                if wtype == "Label":
                    try:
                        w.config(fg=current_fg)
                    except tk.TclError: pass
            elif wtype == "Panedwindow":
                try:
                    w.config(bg=bg_sash)
                except tk.TclError: pass

            try:
                children = w.winfo_children()
            except Exception:
                children = []
                
            for child in children:
                _apply_colors(child)
        
        self._apply_colors = _apply_colors
                
        if hasattr(self, "root_frame"):
            _apply_colors(self.root_frame)
            
        # Ensure inactive tabs are also colored correctly
        if hasattr(self, "_tabs"):
            for tab_dict in self._tabs:
                frame = tab_dict.get("frame")
                if frame and frame.winfo_parent() != self.winfo_name():
                    _apply_colors(frame)

        # Explicit fallback calls just in case
        if hasattr(self, 'grid_left'):
            try: self.grid_left.set_theme(theme)
            except Exception: pass
        if hasattr(self, 'grid_right'):
            try: self.grid_right.set_theme(theme)
            except Exception: pass

    def _setup_ui(self):
        # Setup global fonts for overall larger appearance
        default_font = tkfont.nametofont("TkDefaultFont")
        default_font.configure(size=11)
        
        text_font = tkfont.nametofont("TkTextFont")
        text_font.configure(size=11)
        
        fixed_font = tkfont.nametofont("TkFixedFont")
        fixed_font.configure(size=11)

        style = ttk.Style()
        style.configure(".", font=("Segoe UI", 11))
        style.configure("Treeview", rowheight=28, font=("Segoe UI", 11))
        style.configure("Treeview.Heading", font=("Segoe UI", 11, "bold"))
        
        # 1. Themeable Menubar (replaces native one to support Dark Mode)
        # Using a Frame with Menubuttons allows us to style the main bar itself.
        self.menubar_frame = tk.Frame(self.root_frame, height=28, bg="#f8f9fa")
        self.menubar_frame.pack(fill=tk.X, side=tk.TOP)
        
        self._menubar_active = False
        self._menubar_active_menu = None
        self._menubar_buttons = {}
        
        # File Menu
        self.btn_file = tk.Menubutton(self.menubar_frame, text="Datei", padx=10, pady=2, font=("Segoe UI", 10), cursor="hand2")
        self.file_menu = CustomDropdownMenu(self.root_frame, self)
        self.file_menu.add_command(label="Load TARGET (Zieldatei)...", command=lambda: self.cmd_load_file(1), accelerator="Ctrl+T")
        self.file_menu.add_command(label="Load ACTUAL (Ist-Datei)...", command=lambda: self.cmd_load_file(2), accelerator="Ctrl+A")
        self.file_menu.add_separator()
        self.file_menu.add_command(label="Vergleichseinstellungen laden...", command=self.cmd_load_settings)
        self.file_menu.add_command(label="Vergleichseinstellungen speichern...", command=self.cmd_save_settings)
        self.file_menu.add_separator()
        self.file_menu.add_command(label="Beenden", command=self._on_closing, accelerator="Ctrl+Q")
        self.btn_file.bind("<Button-1>", lambda e: self._on_menubar_click("file"))
        self.btn_file.bind("<Enter>", lambda e: self._on_menubar_enter("file"))
        self.btn_file.pack(side=tk.LEFT)
        self._menubar_buttons["file"] = {"btn": self.btn_file, "menu": self.file_menu}
        
        # View/Layout Menu
        self.btn_view = tk.Menubutton(self.menubar_frame, text="Ansicht", padx=10, pady=2, font=("Segoe UI", 10), cursor="hand2")
        self.view_menu = CustomDropdownMenu(self.root_frame, self)
        self.view_menu.add_command(label="Standardlayout wiederherstellen", command=self._reset_layout_to_default)
        self.view_menu.add_command(label="Text- und Zellengrößen zurücksetzen", command=self._reset_zoom_to_default)
        self.btn_view.bind("<Button-1>", lambda e: self._on_menubar_click("view"))
        self.btn_view.bind("<Enter>", lambda e: self._on_menubar_enter("view"))
        self.btn_view.pack(side=tk.LEFT)
        self._menubar_buttons["view"] = {"btn": self.btn_view, "menu": self.view_menu}
        
        # Design Menu
        self.btn_design = tk.Menubutton(self.menubar_frame, text="Design", padx=10, pady=2, font=("Segoe UI", 10), cursor="hand2")
        self.design_menu = CustomDropdownMenu(self.root_frame, self)
        self.design_menu.add_command(label="Heller Modus (Light)", command=lambda: self.set_theme("light"))
        self.design_menu.add_command(label="Dunkler Modus (Dark)", command=lambda: self.set_theme("dark"))
        self.btn_design.bind("<Button-1>", lambda e: self._on_menubar_click("design"))
        self.btn_design.bind("<Enter>", lambda e: self._on_menubar_enter("design"))
        self.btn_design.pack(side=tk.LEFT)
        self._menubar_buttons["design"] = {"btn": self.btn_design, "menu": self.design_menu}
        
        self.menu_zoom_manager = ZoomManager(self.menubar_frame, zoom_id="menubar")
        
        # Bind shortcuts
        self.bind("<Control-t>", lambda e: self.cmd_load_file(1))
        self.bind("<Control-T>", lambda e: self.cmd_load_file(1))
        self.bind("<Control-a>", lambda e: self.cmd_load_file(2))
        self.bind("<Control-A>", lambda e: self.cmd_load_file(2))
        self.bind("<Control-q>", lambda e: self._on_closing())
        self.bind("<Control-Q>", lambda e: self._on_closing())

        # Custom Tabs Panel (Full Width, Scrollable)
        self._tabs = []
        self._current_tab_index = 0
        
        self.nav_container = tk.Frame(self.root_frame, bg="#f8f9fa")
        self.nav_container.pack(fill=tk.X, side=tk.TOP, padx=5, pady=(5, 0))
        
        self.btn_scroll_left = tk.Button(self.nav_container, text=" < ", relief=tk.FLAT, bg="#f8f9fa", font=("Arial", 10, "bold"), fg="#5f6368", command=self._scroll_tabs_left)
        
        self.nav_canvas = tk.Canvas(self.nav_container, bg="#f8f9fa", height=35, highlightthickness=0)
        self.nav_canvas.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        self.btn_scroll_right = tk.Button(self.nav_container, text=" > ", relief=tk.FLAT, bg="#f8f9fa", font=("Arial", 10, "bold"), fg="#5f6368", command=self._scroll_tabs_right)
        
        self.settings_nav_frame = tk.Frame(self.nav_canvas, bg="#f8f9fa")
        self.nav_canvas_window = self.nav_canvas.create_window((0, 0), window=self.settings_nav_frame, anchor="nw")
        
        self.settings_nav_frame.bind("<Configure>", self._on_nav_frame_configure)
        self.nav_canvas.bind("<Configure>", self._on_nav_canvas_configure)
        self.nav_canvas.bind("<MouseWheel>", self._on_nav_mousewheel)
        self.settings_nav_frame.bind("<MouseWheel>", self._on_nav_mousewheel)
        
        # A separator line below tabs
        tk.Frame(self.root_frame, height=2, bg="#0b57d0").pack(fill=tk.X, side=tk.TOP, padx=5, pady=(0, 5))

        # 2. Main display area (Vertical Split for Top / Bottom)
        self.main_paned = tk.PanedWindow(self.root_frame, orient=tk.VERTICAL, opaqueresize=False, sashwidth=4, bd=0, bg="#dcdcdc")
        self.main_paned.pack(fill=tk.BOTH, expand=True)

        # ----- TOP AREA (3 Columns: Files 1, Settings, Files 2) -----
        self.top_paned = tk.PanedWindow(self.main_paned, orient=tk.HORIZONTAL, opaqueresize=False, sashwidth=4, bd=0, bg="#dcdcdc")
        self.main_paned.add(self.top_paned, stretch="always")

        # --- Files 1 (Tree 1) ---
        self.frame_tree_1 = tk.Frame(self.top_paned, bg="#f8f9fa", width=250)
        self.frame_tree_1.pack_propagate(False)
        self.top_paned.add(self.frame_tree_1, stretch="never", minsize=200)
        
        tree1_container = tk.Frame(self.frame_tree_1, bg="#f8f9fa")
        tree1_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.tree1 = FileStructureTree(tree1_container)
        scroll1 = ttk.Scrollbar(tree1_container, orient="vertical", command=self.tree1.yview)
        scroll1.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree1.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.tree1.configure(yscrollcommand=scroll1.set)

        # --- Center (Settings) ---
        self.frame_middle = tk.Frame(self.top_paned, bg="#f8f9fa")
        self.top_paned.add(self.frame_middle, stretch="always", minsize=350) # More space for settings
        
        self.settings_content_frame = tk.Frame(self.frame_middle, bg="#f8f9fa")
        self.settings_content_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=0)

        
        # Tab 1: Datei-Import
        self.tab_import = tk.Frame(self.settings_content_frame, bg="#f8f9fa")
        self._add_custom_tab(self.tab_import, "1. Datei-Import")
        
        self.import_paned = tk.PanedWindow(self.tab_import, orient=tk.HORIZONTAL, sashwidth=4, bd=0, bg="#dcdcdc")
        self.import_paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        frame_imp1 = tk.Frame(self.import_paned, bg="#f8f9fa")
        self.pg_import1 = TkPropertyGrid(frame_imp1, value_changed_callback=lambda k, v: self._on_property_changed(k, v, 1), zoom_id="pg_import1")
        self.pg_import1.pack(fill=tk.BOTH, expand=True)
        self.import_paned.add(frame_imp1, stretch="always", minsize=150)
        
        frame_imp2 = tk.Frame(self.import_paned, bg="#f8f9fa")
        self.pg_import2 = TkPropertyGrid(frame_imp2, value_changed_callback=lambda k, v: self._on_property_changed(k, v, 2), zoom_id="pg_import2")
        self.pg_import2.pack(fill=tk.BOTH, expand=True)
        self.import_paned.add(frame_imp2, stretch="always", minsize=150)

        # Tab 2: Daten-Struktur
        self.tab_structure = tk.Frame(self.settings_content_frame, bg="#f8f9fa")
        self._add_custom_tab(self.tab_structure, "2. Daten-Struktur")
        
        self.struct_paned = tk.PanedWindow(self.tab_structure, orient=tk.HORIZONTAL, sashwidth=4, bd=0, bg="#dcdcdc")
        self.struct_paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        frame_str1 = tk.Frame(self.struct_paned, bg="#f8f9fa")
        self.pg_struct1 = TkPropertyGrid(frame_str1, value_changed_callback=lambda k, v: self._on_property_changed(k, v, 1), zoom_id="pg_struct1")
        self.pg_struct1.pack(fill=tk.BOTH, expand=True)
        self.struct_paned.add(frame_str1, stretch="always", minsize=150)
        
        frame_str2 = tk.Frame(self.struct_paned, bg="#f8f9fa")
        self.pg_struct2 = TkPropertyGrid(frame_str2, value_changed_callback=lambda k, v: self._on_property_changed(k, v, 2), zoom_id="pg_struct2")
        self.pg_struct2.pack(fill=tk.BOTH, expand=True)
        self.struct_paned.add(frame_str2, stretch="always", minsize=150)
        
        # Tab 3: Spaltentypen definieren (Casting)
        self.tab_casting = tk.Frame(self.settings_content_frame, bg="#f8f9fa")
        lbl = tk.Label(self.tab_casting, text="Bitte definieren Sie die Spaltentypen.\\nSie können dies direkt über die Dateibäume links und rechts (Rechtsklick auf Spalte)\\noder in der Vorschau unten (Rechtsklick auf Spaltenkopf) tun.", bg="#f8f9fa", font=("Arial", 11), justify="left")
        lbl.pack(padx=20, pady=20, anchor="nw")
        self._add_custom_tab(self.tab_casting, "3. Spaltentypen definieren")
        
        # Tab 4: Arbeitsblätter zuordnen
        self.tab_mapping = SheetMappingView(self.settings_content_frame)
        self.tab_mapping.on_manual_toggled = self._on_manual_mode_toggled
        self._add_custom_tab(self.tab_mapping, "4. Arbeitsblätter zuordnen")
        
        # Tab 5: Zeilen zuordnen
        self.tab_row_mapping = RowMappingView(self.settings_content_frame, data_provider=self._fetch_columns_for_mapping)
        self.tab_row_mapping.on_sheet_pair_selected = self._on_row_mapping_sheet_pair_selected
        self.tab_row_mapping.on_key_based_toggled = self._on_manual_mode_toggled
        self.tab_row_mapping.on_keys_changed = self._update_key_highlights
        self._add_custom_tab(self.tab_row_mapping, "5. Zeilen zuordnen")
        
        # Tab 6: Spalten zuordnen
        self.tab_column_mapping = ColumnMappingView(self.settings_content_frame, data_provider=self._fetch_columns_for_mapping)
        self.tab_column_mapping.on_sheet_pair_selected = self._on_row_mapping_sheet_pair_selected
        self.tab_column_mapping.on_manual_mode_toggled = self._on_manual_mode_toggled
        self.tab_column_mapping.on_cols_changed = self._update_key_highlights
        self._add_custom_tab(self.tab_column_mapping, "6. Spalten zuordnen")
        
        # Tab 7: Vergleichslogik
        self.tab_comparison = ComparisonLogicView(self.settings_content_frame)
        self.tab_comparison.on_sheet_pair_selected = self._on_row_mapping_sheet_pair_selected
        self.tab_comparison.on_cols_changed = self._update_key_highlights
        self._add_custom_tab(self.tab_comparison, "7. Vergleichslogik")
        
        # Tab 8: Abschließen
        self.tab_finish = FinishTab(self.settings_content_frame, on_save_settings_callback=self.cmd_save_settings)
        self.tab_finish.on_sheet_pair_selected = self._on_row_mapping_sheet_pair_selected
        self.tab_finish.on_cols_changed = self._update_key_highlights
        self._add_custom_tab(self.tab_finish, "8. Abschließen")
        
        self._populate_settings_grids()

        # --- Files 2 (Tree 2) ---
        self.frame_tree_2 = tk.Frame(self.top_paned, bg="#f8f9fa", width=250)
        self.frame_tree_2.pack_propagate(False)
        self.top_paned.add(self.frame_tree_2, stretch="never", minsize=200)
        
        tree2_container = tk.Frame(self.frame_tree_2, bg="#f8f9fa")
        tree2_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.tree2 = FileStructureTree(tree2_container)
        scroll2 = ttk.Scrollbar(tree2_container, orient="vertical", command=self.tree2.yview)
        scroll2.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree2.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.tree2.configure(yscrollcommand=scroll2.set)
        
        # Configure tags for key columns (light green)
        self.tree1.tag_configure("key_col", background="#d4edda")
        self.tree2.tag_configure("key_col", background="#d4edda")
        
        self.tree1.bind("<<TreeviewSelect>>", lambda e: self._on_tree_select(1))
        self.tree2.bind("<<TreeviewSelect>>", lambda e: self._on_tree_select(2))
        self.tree1.bind("<ButtonRelease-1>", lambda e: self._on_tree_click_mapping(e, 1))
        self.tree2.bind("<ButtonRelease-1>", lambda e: self._on_tree_click_mapping(e, 2))
        self.tree1.bind("<Button-3>", lambda e: self._on_tree_right_click(e, 1))
        self.tree2.bind("<Button-3>", lambda e: self._on_tree_right_click(e, 2))

        # ----- BOTTOM AREA (2 Columns for the configuration grids) -----
        self.bottom_paned = tk.PanedWindow(self.main_paned, orient=tk.HORIZONTAL, opaqueresize=False, sashwidth=4, bd=0, bg="#dcdcdc")
        self.main_paned.add(self.bottom_paned, stretch="always") # Grids usually receive more space at the bottom

        # --- Preview File 1 ---
        left_side = tk.Frame(self.bottom_paned)
        self.bottom_paned.add(left_side, stretch="always", minsize=300)
        
        header_left = tk.Frame(left_side, bg="#f8f9fa", pady=2)
        header_left.pack(fill=tk.X)
        tk.Label(header_left, text=" Preview File 1", font=("Arial", 11, "bold"), fg="#5f6368", bg="#f8f9fa").pack(side=tk.LEFT, padx=5)
        
        self.grid_left = ComplianceGrid(left_side, zoom_id="compliance_grid_left")
        self.grid_left.pack(fill=tk.BOTH, expand=True)

        # --- Preview File 2 ---
        right_side = tk.Frame(self.bottom_paned)
        self.bottom_paned.add(right_side, stretch="always", minsize=300)
        
        header_right = tk.Frame(right_side, bg="#f8f9fa", pady=2)
        header_right.pack(fill=tk.X)
        tk.Label(header_right, text=" Preview File 2", font=("Arial", 11, "bold"), fg="#5f6368", bg="#f8f9fa").pack(side=tk.LEFT, padx=5)
        
        self.grid_right = ComplianceGrid(right_side, zoom_id="compliance_grid_right")
        self.grid_right.pack(fill=tk.BOTH, expand=True)
        
        # Bind column selection events
        self.grid_left.on_column_selected = lambda col_idx, col_name: self._on_grid_col_selected(1, col_idx, col_name)
        self.grid_right.on_column_selected = lambda col_idx, col_name: self._on_grid_col_selected(2, col_idx, col_name)
        
        self.grid_left.on_type_changed = lambda col_idx, t: self._on_grid_type_changed(1, col_idx, t)
        self.grid_right.on_type_changed = lambda col_idx, t: self._on_grid_type_changed(2, col_idx, t)
        
        self.grid_left.on_header_row_changed = lambda row_idx: self._on_header_row_selected_from_grid(1, row_idx)
        self.grid_right.on_header_row_changed = lambda row_idx: self._on_header_row_selected_from_grid(2, row_idx)
        
        self.grid_left.on_data_start_row_changed = lambda row_idx: self._on_property_changed("DataStartRow", str(row_idx + 1), 1)
        self.grid_right.on_data_start_row_changed = lambda row_idx: self._on_property_changed("DataStartRow", str(row_idx + 1), 2)
        
        self.grid_left.on_data_end_row_changed = lambda row_idx: self._on_property_changed("DataEndRow", str(row_idx + 1), 1)
        self.grid_right.on_data_end_row_changed = lambda row_idx: self._on_property_changed("DataEndRow", str(row_idx + 1), 2)
        
        self.grid_left.on_ignore_row_toggled = lambda row_idx: self._on_ignore_row_toggled_from_grid(1, row_idx)
        self.grid_right.on_ignore_row_toggled = lambda row_idx: self._on_ignore_row_toggled_from_grid(2, row_idx)
        
        self.grid_left.on_ignore_col_toggled = lambda col_idx: self._on_ignore_col_toggled_from_grid(1, col_idx)
        self.grid_right.on_ignore_col_toggled = lambda col_idx: self._on_ignore_col_toggled_from_grid(2, col_idx)
        
        if self._tabs:
            self._select_tab(0, force=True)

    def _add_custom_tab(self, frame, text):
        index = len(self._tabs)
        btn = TabButton(self.settings_nav_frame, text=text, index=index, command=self._select_tab, fixed_width=175)
        btn.pack(side=tk.LEFT, padx=(0, 3))
        btn.bind("<MouseWheel>", self._on_nav_mousewheel)
        self._tabs.append({"frame": frame, "button": btn})
        
    def _update_trees_for_tab(self, expand_columns, force_select_first=False):
        if not hasattr(self, 'tree1') or not hasattr(self, 'tree2'):
            return
            
        def process_tree(tree):
            root_items = tree.get_children("")
            if not root_items: return
            
            active_sheet = self._get_active_sheet_iid(tree)
            
            for file_iid in root_items:
                tree.item(file_iid, open=True)
                for sheet_iid in tree.get_children(file_iid):
                    # Only expand the currently active sheet
                    should_open = expand_columns and (sheet_iid == active_sheet)
                    tree.item(sheet_iid, open=should_open)
            
            # Select first sheet if not selected or if forced
            if force_select_first or not tree.selection():
                sheets = tree.get_children(root_items[0])
                if sheets:
                    if tree.selection() != (sheets[0],):
                        tree.selection_set(sheets[0])
                    tree.see(sheets[0])
                    if expand_columns:
                        tree.item(sheets[0], open=True)
                
        process_tree(self.tree1)
        process_tree(self.tree2)

    def _select_tab(self, index, force=False):
        if 0 <= index < len(self._tabs):
            # If same tab is selected, do nothing
            if not force and hasattr(self, '_current_tab_index') and self._current_tab_index == index:
                return
                
            # Validate before switching away from Tab 5 (index 4)
            if hasattr(self, '_current_tab_index') and self._current_tab_index == 4:
                if hasattr(self, 'tab_row_mapping') and hasattr(self.tab_row_mapping, 'validate_current_state'):
                    if not self.tab_row_mapping.validate_current_state():
                        # Reset visual state of clicked button
                        self._tabs[index]["button"].set_active(False)
                        return
                        
            # Validate before switching away from Tab 6 (index 5)
            if hasattr(self, '_current_tab_index') and self._current_tab_index == 5:
                if hasattr(self, 'tab_column_mapping') and hasattr(self.tab_column_mapping, 'validate_current_state'):
                    if not self.tab_column_mapping.validate_current_state():
                        # Reset visual state of clicked button
                        self._tabs[index]["button"].set_active(False)
                        return

            # Save state of current tab before switching
            if hasattr(self, '_current_tab_index'):
                self._save_sash_state(self._current_tab_index)

            # Hide current
            if hasattr(self, '_current_tab_index'):
                current_frame = self._tabs[self._current_tab_index]["frame"]
                current_btn = self._tabs[self._current_tab_index]["button"]
                current_frame.pack_forget()
                current_btn.set_active(False)
            
            # Show new
            self._current_tab_index = index
            
            # --- STRUCTURE FIX FOR PANED WINDOW ---
            is_casting = (index == 2)
            if is_casting:
                # Hide the middle settings frame to give treeviews full space
                if str(self.frame_middle) in [str(p) for p in self.top_paned.panes()]:
                    self.top_paned.forget(self.frame_middle)
                    
                self.top_paned.paneconfig(self.frame_tree_1, stretch="always")
                self.top_paned.paneconfig(self.frame_tree_2, stretch="always")
            else:
                # Restore the middle settings frame if it was hidden
                if str(self.frame_middle) not in [str(p) for p in self.top_paned.panes()]:
                    self.top_paned.add(self.frame_middle, before=self.frame_tree_2, stretch="always", minsize=350)
                    
                self.top_paned.paneconfig(self.frame_tree_1, stretch="never")
                self.top_paned.paneconfig(self.frame_tree_2, stretch="never")
            # ----------------------------------------
            
            # Restore state BEFORE packing and populating data to prevent double rendering
            self._restore_sash_state(index)
            
            new_frame = self._tabs[index]["frame"]
            new_btn = self._tabs[index]["button"]
            new_frame.pack(fill=tk.BOTH, expand=True)
            new_btn.set_active(True)
            
            self._on_notebook_tab_changed(None)
            
            # Configure grid context menus based on tab
            def config_grid(grid):
                if index == 0:
                    grid.header_context_menu_enabled = False
                    grid.index_context_menu_enabled = False
                elif index == 1:
                    grid.header_context_menu_enabled = True
                    grid.header_menu_show_types = False
                    grid.header_menu_show_ignore = True
                    grid.index_context_menu_enabled = True
                elif index == 2:
                    grid.header_context_menu_enabled = True
                    grid.header_menu_show_types = True
                    grid.header_menu_show_ignore = False
                    grid.index_context_menu_enabled = False
                else:
                    grid.header_context_menu_enabled = False
                    grid.index_context_menu_enabled = False
                    
            if hasattr(self, "grid_left"): config_grid(self.grid_left)
            if hasattr(self, "grid_right"): config_grid(self.grid_right)
            
            if index != 4:
                self._clear_key_highlights()
            
            if index not in (4, 5):
                if hasattr(self, 'tree1'): self.tree1.unlock_all()
                if hasattr(self, 'tree2'): self.tree2.unlock_all()

            # Configure tree columns based on tab
            if index == 0: # Tab 1
                self._update_trees_for_tab(expand_columns=False, force_select_first=True)
            elif index == 1: # Tab 2
                self._update_trees_for_tab(expand_columns=False, force_select_first=False)
            elif index == 2: # Tab 3
                self._update_trees_for_tab(expand_columns=True, force_select_first=False)
            elif index == 3: # Tab 4
                self._update_trees_for_tab(expand_columns=False, force_select_first=True)
            elif index == 4: # Tab 5
                is_key_based = False
                if hasattr(self, 'tab_row_mapping'):
                    rm = self.tab_row_mapping
                    if rm.active_mapping_idx is not None and rm.active_mapping_idx < len(rm.sheet_mappings):
                        if rm.sheet_mappings[rm.active_mapping_idx].row_matching_mode == "key_based":
                            is_key_based = True
                self._update_trees_for_tab(expand_columns=is_key_based, force_select_first=False)
            elif index == 5: # Tab 6
                self._update_trees_for_tab(expand_columns=True, force_select_first=False)
            elif index == 6: # Tab 7
                self._update_trees_for_tab(expand_columns=False, force_select_first=True)
            elif index == 7: # Tab 8
                self._update_trees_for_tab(expand_columns=False, force_select_first=True)
                self.tab_finish.update_summary(self)

    def _get_inner_paned_for_tab(self, index):
        if index == 0 and hasattr(self, 'import_paned'): return self.import_paned
        if index == 1 and hasattr(self, 'struct_paned'): return self.struct_paned
        if index == 3 and hasattr(self, 'tab_mapping') and hasattr(self.tab_mapping, 'paned'): return self.tab_mapping.paned
        if index == 4 and hasattr(self, 'tab_row_mapping') and hasattr(self.tab_row_mapping, 'paned'): return self.tab_row_mapping.paned
        if index == 5 and hasattr(self, 'tab_column_mapping') and hasattr(self.tab_column_mapping, 'paned'): return self.tab_column_mapping.paned
        return None

    def _save_sash_state(self, index):
        if not hasattr(self, '_tab_sash_states'):
            self._tab_sash_states = {}
            
        if not self.top_paned.winfo_viewable():
            return
            
        try:
            top_widths = {str(p): self.nametowidget(p).winfo_width() for p in self.top_paned.panes()}
            bottom_widths = {str(p): self.nametowidget(p).winfo_width() for p in self.bottom_paned.panes()}
            main_heights = {str(p): self.nametowidget(p).winfo_height() for p in self.main_paned.panes()}
            
            inner_widths = {}
            pw = self._get_inner_paned_for_tab(index)
            if pw and pw.winfo_viewable():
                inner_widths = {str(p): self.nametowidget(p).winfo_width() for p in pw.panes()}
                
            grid_states = {}
            if index == 3 and hasattr(self, 'tab_mapping') and hasattr(self.tab_mapping, 'grid_preview'):
                grid_states['preview'] = self.tab_mapping.grid_preview.get_state()
            elif index == 4 and hasattr(self, 'tab_row_mapping') and hasattr(self.tab_row_mapping, 'grid_keys'):
                grid_states['keys'] = self.tab_row_mapping.grid_keys.get_state()
            elif index == 5 and hasattr(self, 'tab_column_mapping') and hasattr(self.tab_column_mapping, 'grid_cols'):
                grid_states['cols'] = self.tab_column_mapping.grid_cols.get_state()
                
            self._tab_sash_states[index] = {
                'top': top_widths,
                'bottom': bottom_widths,
                'main': main_heights,
                'inner': inner_widths,
                'grids': grid_states
            }
        except tk.TclError:
            pass
            
    def _apply_sash_state(self, state, index=None):
        try:
            top_panes_str = [str(p) for p in self.top_paned.panes()]
            for p in top_panes_str:
                width = state.get('top', {}).get(p, '')
                if width: self.top_paned.paneconfigure(p, width=width)
            
            bottom_panes_str = [str(p) for p in self.bottom_paned.panes()]
            for p in bottom_panes_str:
                width = state.get('bottom', {}).get(p, '')
                if width: self.bottom_paned.paneconfigure(p, width=width)
                
            main_panes_str = [str(p) for p in self.main_paned.panes()]
            for p in main_panes_str:
                height = state.get('main', {}).get(p, '')
                if height: self.main_paned.paneconfigure(p, height=height)
                
            if index is not None:
                pw = self._get_inner_paned_for_tab(index)
                if pw:
                    inner_panes_str = [str(p) for p in pw.panes()]
                    for p in inner_panes_str:
                        width = state.get('inner', {}).get(p, '')
                        if width: pw.paneconfigure(p, width=width)
                        
                grid_states = state.get('grids', {})
                if index == 3 and hasattr(self, 'tab_mapping') and hasattr(self.tab_mapping, 'grid_preview'):
                    self.tab_mapping.grid_preview.set_state(grid_states.get('preview'))
                elif index == 4 and hasattr(self, 'tab_row_mapping') and hasattr(self.tab_row_mapping, 'grid_keys'):
                    self.tab_row_mapping.grid_keys.set_state(grid_states.get('keys'))
                elif index == 5 and hasattr(self, 'tab_column_mapping') and hasattr(self.tab_column_mapping, 'grid_cols'):
                    self.tab_column_mapping.grid_cols.set_state(grid_states.get('cols'))
        except tk.TclError:
            pass

    def _restore_sash_state(self, index):
        if not hasattr(self, '_tab_sash_states'):
            return
        state = self._tab_sash_states.get(index)
        self._apply_or_default(state, index)
        
    def _apply_or_default(self, state, index):
        if state is None:
            state = self._get_default_sash_state(index)
        self._apply_sash_state(state, index)
        
    def _get_default_sash_state(self, index=None):
        top_panes = [str(p) for p in self.top_paned.panes()]
        bottom_panes = [str(p) for p in self.bottom_paned.panes()]
        main_panes = [str(p) for p in self.main_paned.panes()]
        
        top_state = {}
        top_width = self.top_paned.winfo_width()
        
        if len(top_panes) == 3:
            top_state[top_panes[0]] = 250
            top_state[top_panes[2]] = 250
            top_state[top_panes[1]] = max(10, top_width - 500 - 8)
        elif len(top_panes) == 2:
            w = max(10, (top_width - 4) // 2)
            top_state[top_panes[0]] = w
            top_state[top_panes[1]] = w
            
        bottom_state = {}
        bottom_width = self.bottom_paned.winfo_width()
        if len(bottom_panes) == 2:
            w = max(10, (bottom_width - 4) // 2)
            bottom_state[bottom_panes[0]] = w
            bottom_state[bottom_panes[1]] = w
            
        main_state = {}
        main_height = self.main_paned.winfo_height()
        if len(main_panes) == 2:
            h = max(10, (main_height - 4) // 2)
            main_state[main_panes[0]] = h
            main_state[main_panes[1]] = h
            
        inner_state = {}
        if index is not None:
            pw = self._get_inner_paned_for_tab(index)
            if pw:
                inner_panes = [str(p) for p in pw.panes()]
                inner_width = pw.winfo_width()
                if len(inner_panes) == 2:
                    w = max(10, (inner_width - 4) // 2)
                    inner_state[inner_panes[0]] = w
                    inner_state[inner_panes[1]] = w
            
        return {'top': top_state, 'bottom': bottom_state, 'main': main_state, 'inner': inner_state}

    def _reset_layout_to_default(self):
        """Clears all saved tab states and resets the current layout to default requested sizes."""
        self._tab_sash_states = {}
        state = self._get_default_sash_state(self._current_tab_index)
        self._apply_sash_state(state, self._current_tab_index)
        
        # Reset vertical main_paned (Top/Bottom split)
        panes = [str(p) for p in self.main_paned.panes()]
        if len(panes) == 2:
            h = max(10, (self.main_paned.winfo_height() - 4) // 2)
            self.main_paned.paneconfigure(panes[0], height=h)
            self.main_paned.paneconfigure(panes[1], height=h)
            
        # Reset all internal horizontal PanedWindows 50/50
        inner_pws = []
        if hasattr(self, 'import_paned'): inner_pws.append(self.import_paned)
        if hasattr(self, 'struct_paned'): inner_pws.append(self.struct_paned)
        if hasattr(self, 'tab_mapping') and hasattr(self.tab_mapping, 'paned'): inner_pws.append(self.tab_mapping.paned)
        if hasattr(self, 'tab_row_mapping') and hasattr(self.tab_row_mapping, 'paned'): inner_pws.append(self.tab_row_mapping.paned)
        if hasattr(self, 'tab_column_mapping') and hasattr(self.tab_column_mapping, 'paned'): inner_pws.append(self.tab_column_mapping.paned)
        
        for pw in inner_pws:
            panes = [str(p) for p in pw.panes()]
            if len(panes) == 2:
                w = max(10, (pw.winfo_width() - 4) // 2)
                pw.paneconfigure(panes[0], width=w)
                pw.paneconfigure(panes[1], width=w)
                
        # Reset grid states if available
        if hasattr(self, 'tab_mapping') and hasattr(self.tab_mapping, 'grid_preview'):
            self.tab_mapping.grid_preview.set_user_resized(False)
            self.tab_mapping.grid_preview._sync_and_redraw()
        if hasattr(self, 'tab_row_mapping') and hasattr(self.tab_row_mapping, 'grid_keys'):
            self.tab_row_mapping.grid_keys.set_user_resized(False)
            self.tab_row_mapping.grid_keys._sync_and_redraw()
        if hasattr(self, 'tab_column_mapping') and hasattr(self.tab_column_mapping, 'grid_cols'):
            self.tab_column_mapping.grid_cols.set_user_resized(False)
            self.tab_column_mapping.grid_cols._sync_and_redraw()

    def _reset_zoom_to_default(self):
        """Resets all text and cell sizes (zoom states) across all areas to their defaults."""
        class DummyEvent:
            def __init__(self, delta):
                self.delta = delta
                self.num = 0

        from ui_components import ZoomManager
        
        # 1. TabButtons
        if "tabs" in ZoomManager.GLOBAL_STATES:
            delta = TabButton.global_font_size - 11
            for _ in range(abs(delta)):
                ev = DummyEvent(120 if delta < 0 else -120)
                if TabButton._instances:
                    TabButton._instances[0]._on_zoom(ev)

        # 2. FileStructureTree
        if "file_trees" in ZoomManager.GLOBAL_STATES:
            from tree_widget import FileStructureTree
            delta = FileStructureTree.global_font_size - 11
            for _ in range(abs(delta)):
                ev = DummyEvent(120 if delta < 0 else -120)
                if FileStructureTree._instances:
                    FileStructureTree._instances[0]._on_zoom(ev)

        # 3. ComplianceGrids & PropertyGrids (instance based zoom)
        grids_to_reset = []
        if hasattr(self, 'grid_left'): grids_to_reset.append((self.grid_left, 12))
        if hasattr(self, 'grid_right'): grids_to_reset.append((self.grid_right, 12))
        if hasattr(self, 'pg_import1'): grids_to_reset.append((self.pg_import1, 11))
        if hasattr(self, 'pg_import2'): grids_to_reset.append((self.pg_import2, 11))
        if hasattr(self, 'pg_struct1'): grids_to_reset.append((self.pg_struct1, 11))
        if hasattr(self, 'pg_struct2'): grids_to_reset.append((self.pg_struct2, 11))
        
        if hasattr(self, 'tab_mapping') and hasattr(self.tab_mapping, 'grid_preview'):
            grids_to_reset.append((self.tab_mapping.grid_preview, 12))
        if hasattr(self, 'tab_row_mapping') and hasattr(self.tab_row_mapping, 'grid_keys'):
            grids_to_reset.append((self.tab_row_mapping.grid_keys, 12))
        if hasattr(self, 'tab_column_mapping') and hasattr(self.tab_column_mapping, 'grid_cols'):
            grids_to_reset.append((self.tab_column_mapping.grid_cols, 12))

        for grid, default_size in grids_to_reset:
            if hasattr(grid, 'font_size') and hasattr(grid, '_on_zoom'):
                delta = grid.font_size - default_size
                for _ in range(abs(delta)):
                    ev = DummyEvent(120 if delta < 0 else -120)
                    grid._on_zoom(ev)

        # 4. ZoomManager instances (like menu bar)
        if hasattr(self, 'menu_zoom_manager'):
            self.menu_zoom_manager.apply_absolute_zoom(-self.menu_zoom_manager.total_zoom_delta)
            
        # 5. ZoomManagers inside Tabs 4, 5, 6, 7
        for view in [getattr(self, 'tab_mapping', None), 
                     getattr(self, 'tab_row_mapping', None), 
                     getattr(self, 'tab_column_mapping', None),
                     getattr(self, 'tab_comparison', None)]:
            if view:
                for attr in ['zoom_manager', 'zoom_manager_left', 'zoom_manager_right']:
                    zm = getattr(view, attr, None)
                    if zm and hasattr(zm, 'apply_absolute_zoom') and hasattr(zm, 'total_zoom_delta'):
                        if zm.total_zoom_delta != 0:
                            zm.apply_absolute_zoom(-zm.total_zoom_delta)

        # Finally clear the global states
        ZoomManager.GLOBAL_STATES.clear()
        self.save_layout()

    def _on_nav_frame_configure(self, event):
        self.nav_canvas.configure(scrollregion=self.nav_canvas.bbox("all"))
        self._check_tab_scroll()

    def _on_nav_canvas_configure(self, event):
        self._check_tab_scroll()

    def _check_tab_scroll(self):
        req_width = self.settings_nav_frame.winfo_reqwidth()
        canvas_width = self.nav_canvas.winfo_width()
        if req_width > canvas_width and canvas_width > 10:
            if not self.btn_scroll_left.winfo_ismapped():
                self.btn_scroll_left.pack(side=tk.LEFT, before=self.nav_canvas)
            if not self.btn_scroll_right.winfo_ismapped():
                self.btn_scroll_right.pack(side=tk.RIGHT, after=self.nav_canvas)
        else:
            if self.btn_scroll_left.winfo_ismapped():
                self.btn_scroll_left.pack_forget()
            if self.btn_scroll_right.winfo_ismapped():
                self.btn_scroll_right.pack_forget()
            self.nav_canvas.xview_moveto(0)

    def _get_button_positions(self):
        positions = []
        for tab in self._tabs:
            btn = tab["button"]
            positions.append((btn.winfo_x(), btn.winfo_width()))
        return positions

    def _scroll_tabs_left(self):
        canvas_width = self.nav_canvas.winfo_width()
        inner_width = self.settings_nav_frame.winfo_width()
        if inner_width <= canvas_width: return
        
        current_left_frac = self.nav_canvas.xview()[0]
        current_left_px = current_left_frac * inner_width
        
        target_x = 0
        for x, w in reversed(self._get_button_positions()):
            if x < current_left_px - 1:
                target_x = x
                break
                
        self.nav_canvas.xview_moveto(target_x / inner_width)

    def _scroll_tabs_right(self):
        canvas_width = self.nav_canvas.winfo_width()
        inner_width = self.settings_nav_frame.winfo_width()
        if inner_width <= canvas_width: return
        
        current_left_frac = self.nav_canvas.xview()[0]
        current_left_px = current_left_frac * inner_width
        current_right_px = current_left_px + canvas_width
        
        target_x = current_left_px
        for x, w in self._get_button_positions():
            if x + w > current_right_px + 1:
                target_x = (x + w) - canvas_width
                break
                
        self.nav_canvas.xview_moveto(target_x / inner_width)

    def _on_nav_mousewheel(self, event):
        req_width = self.settings_nav_frame.winfo_reqwidth()
        canvas_width = self.nav_canvas.winfo_width()
        if req_width > canvas_width:
            delta = int(-1 * (event.delta / 120))
            self.nav_canvas.xview_scroll(delta, "units")

    def _expand_first_sheet(self, tree):
        root_items = tree.get_children("")
        if root_items:
            file_iid = root_items[0]
            tree.item(file_iid, open=True)
            sheet_items = tree.get_children(file_iid)
            if sheet_items:
                sheet_iid = sheet_items[0]
                tree.item(sheet_iid, open=True)
                if not tree.selection():
                    tree.selection_set(sheet_iid)

    def _on_grid_type_changed(self, side, col_idx, new_type):
        self._tree_change_type(side, col_idx, new_type)

    def _get_active_sheet_iid(self, tree):
        selected = tree.selection()
        if not selected:
            root_items = tree.get_children("")
            if root_items:
                sheet_items = tree.get_children(root_items[0])
                if sheet_items: return sheet_items[0]
            return None
            
        iid = selected[0]
        parent = tree.parent(iid)
        
        is_sheet = False
        if parent != "" and tree.parent(parent) == "":
            is_sheet = True
        elif parent == "" and not tree.get_children(iid):
            is_sheet = True
            
        if is_sheet: return iid
        
        if parent != "":
            grandparent = tree.parent(parent)
            if grandparent != "" and tree.parent(grandparent) == "":
                return parent
                
        if parent == "":
            sheets = tree.get_children(iid)
            if sheets: return sheets[0]
            
        return None

    def _detect_types_if_needed(self, side):
        grid = self.grid_left if side == 1 else self.grid_right
        v_list = self.v_list1 if side == 1 else self.v_list2
        config = self.config1 if side == 1 else self.config2
        
        if v_list and hasattr(grid, '_headers') and not getattr(grid, '_types_detected', False):
            from type_detector import ColumnTypeDetector
            detector = ColumnTypeDetector(config)
            bounds = self.get_valid_data_bounds(side, v_list.active_sheet_name)
            col_types, col_ambig, col_conf, col_date_fmt = detector.detect_column_types(v_list, v_list.active_sheet_name, bounds=bounds)
            
            col_is_auto = {c: True for c in col_types}
            for c, t in grid.column_types.items():
                col_types[c] = t
                if hasattr(grid, 'column_is_auto') and not grid.column_is_auto.get(c, True):
                    col_is_auto[c] = False
                elif c in grid.column_types:
                    col_is_auto[c] = False
                
                if hasattr(grid, 'column_confidences') and c in grid.column_confidences:
                    col_conf[c] = grid.column_confidences[c]
                else:
                    col_conf[c] = "100%"
                col_ambig[c] = False
                
            grid.set_column_types(col_types, col_ambig, col_conf, col_date_fmt, col_is_auto)
            grid._types_detected = True

    def _refresh_tree_types(self, side):
        tree = self.tree1 if side == 1 else self.tree2
        grid = self.grid_left if side == 1 else self.grid_right
        sheet_iid = self._get_active_sheet_iid(tree)
        if sheet_iid:
            tree.update_types(sheet_iid, grid.column_types, getattr(grid, 'column_confidences', {}), getattr(grid, 'column_is_auto', {}))

    def _on_tree_right_click(self, event, side):
        if self._current_tab_index != 2:
            return
            
        tree = self.tree1 if side == 1 else self.tree2
        iid = tree.identify_row(event.y)
        if not iid: return
        
        parent = tree.parent(iid)
        if parent == "": return # root or file
        grandparent = tree.parent(parent)
        if grandparent == "" and tree.get_children(parent):
            return # sheet
            
        # It's a column
        sheet_iid = parent
        children = tree.get_children(sheet_iid)
        if iid in children:
            col_idx = children.index(iid)
            
            # Select the item
            tree.selection_set(iid)
            
            # Scroll grid
            grid = self.grid_left if side == 1 else self.grid_right
            grid._clear_selection()
            grid.selected_cols.add(col_idx)
            
            grid.scroll_to_col(col_idx)
            grid.redraw()
                    
            # Open menu
            menu = tk.Menu(self.root_frame, tearoff=0)
            types_list = ["Text", "Zahl", "Datum/Zeit", "Boolean"]
            for t in types_list:
                menu.add_command(label=t, command=lambda t_val=t, c=col_idx: self._tree_change_type(side, c, t_val))
            menu.post(event.x_root, event.y_root)

    def _tree_change_type(self, side, col_idx, new_type):
        grid = self.grid_left if side == 1 else self.grid_right
        v_list = self.v_list1 if side == 1 else self.v_list2
        config = self.config1 if side == 1 else self.config2
        
        if new_type == "Datum/Zeit":
            start_row = config.get_data_start_row(v_list.active_sheet_name)
            
            sample_val = ""
            for r in range(start_row, v_list.num_rows):
                try:
                    row_data = v_list[r]
                    if col_idx < len(row_data):
                        val = str(row_data[col_idx]).strip()
                        if val and val.lower() not in ('none', 'null', ''):
                            sample_val = val
                            break
                except IndexError:
                    break
                    
            from date_builder_dialog import DateBuilderDialog
            dlg = DateBuilderDialog(self.root_frame, sample_val)
            self.root_frame.wait_window(dlg)
            
            if dlg.result_format:
                machine_fmt, display_fmt = dlg.result_format
                new_type = f"Datum/Zeit [{display_fmt}]"
                if not hasattr(grid, 'column_date_formats'):
                    grid.column_date_formats = {}
                grid.column_date_formats[col_idx] = machine_fmt
            else:
                return # Dialog canceled
                
        grid.column_types[col_idx] = new_type
        if hasattr(grid, 'column_is_auto'):
            grid.column_is_auto[col_idx] = False
            
        valid_count = 0
        total_count = 0
        first_error_row = -1
        
        if getattr(grid, 'validation_callback', None) and v_list:
            start_row = config.get_data_start_row(v_list.active_sheet_name)
            end_row = config.get_data_end_row(v_list.active_sheet_name)
            if end_row == 0: end_row = v_list.num_rows
            
            na_values = [v.strip().lower() for v in config.na_values.split(',')]
            
            for r in range(max(0, start_row - 1), min(end_row, v_list.num_rows)):
                if hasattr(grid, 'ignored_rows') and r in grid.ignored_rows: continue
                
                try:
                    row_data = v_list[r]
                    if col_idx < len(row_data):
                        val = row_data[col_idx]
                        val_str = str(val).strip().lower()
                        
                        if not val_str or val_str in na_values:
                            continue
                            
                        is_valid = grid.validation_callback(col_idx, val)
                        total_count += 1
                        if is_valid:
                            valid_count += 1
                        elif first_error_row == -1:
                            first_error_row = r
                except IndexError:
                    break

        if not hasattr(grid, 'column_confidences'):
            grid.column_confidences = {}
            
        if total_count > 0:
            p_valid = (valid_count / total_count) * 100
            if p_valid < 100.0:
                p_invalid = 100.0 - p_valid
                display_type = new_type.split(" [")[0]
                grid.column_confidences[col_idx] = f"{round(p_valid, 1)}% {display_type}, {round(p_invalid, 1)}% Inkompatibel"
            else:
                grid.column_confidences[col_idx] = "100%"
        else:
            grid.column_confidences[col_idx] = "0% (Leer)"
            
        if first_error_row != -1:
            grid._clear_selection()
            grid.selected_cell = (first_error_row, col_idx)
            grid.scroll_to_row(first_error_row)
            
        grid.redraw()
        self._refresh_tree_types(side)
        
    def _on_header_row_selected_from_grid(self, side, row_idx):
        config = self.config1 if side == 1 else self.config2
        pg_struct = self.pg_struct1 if side == 1 else self.pg_struct2
        v_list = self.v_list1 if side == 1 else self.v_list2
        
        if v_list and (row_idx + 1) >= v_list.num_rows:
            from tkinter import messagebox
            messagebox.showwarning(
                "Ungültige Kopfzeile", 
                f"Die Zeile {row_idx + 1} ist die letzte Zeile im Dokument.\nNach der Kopfzeile müssen Daten folgen.", 
                parent=self
            )
            return
            
        sheet_name = v_list.active_sheet_name if v_list and hasattr(v_list, 'active_sheet_name') else "default"
        
        ignored_rows = self._parse_ignored_rows(config.get_ignore_rows(sheet_name))
        if row_idx in ignored_rows:
            from tkinter import messagebox
            messagebox.showwarning(
                "Ungültige Kopfzeile", 
                f"Die Zeile {row_idx + 1} wird ignoriert und kann nicht als Kopfzeile verwendet werden.", 
                parent=self
            )
            return
        
        current_start = config.get_data_start_row(sheet_name)
        config.set_has_header(sheet_name, True)
        config.set_header_row(sheet_name, row_idx + 1)
        
        if current_start <= row_idx + 1:
            config.set_data_start_row(sheet_name, row_idx + 2)
        
        pg_struct.update_property("HasHeader", "True")
        pg_struct.update_property("HeaderRow", str(config.get_header_row(sheet_name)))
        pg_struct.update_property("DataStartRow", str(config.get_data_start_row(sheet_name)))
        
        self._refresh_tree_and_grid_headers(side)

    def _on_ignore_row_toggled_from_grid(self, side, row_idx):
        config = self.config1 if side == 1 else self.config2
        v_list = self.v_list1 if side == 1 else self.v_list2
        sheet_name = v_list.active_sheet_name if v_list and hasattr(v_list, 'active_sheet_name') else "default"
        
        current_str = config.get_ignore_rows(sheet_name)
        rows_set = self._parse_ignored_rows(current_str)
        
        if row_idx in rows_set:
            rows_set.remove(row_idx)
        else:
            rows_set.add(row_idx)
            
        new_str = ", ".join(str(r + 1) for r in sorted(rows_set))
        
        pg_struct = self.pg_struct1 if side == 1 else self.pg_struct2
        pg_struct.update_property("IgnoreRows", new_str)
        
        self._on_property_changed("IgnoreRows", new_str, side)

    def _on_ignore_col_toggled_from_grid(self, side, col_idx):
        config = self.config1 if side == 1 else self.config2
        v_list = self.v_list1 if side == 1 else self.v_list2
        grid_widget = self.grid_left if side == 1 else self.grid_right
        sheet_name = v_list.active_sheet_name if v_list and hasattr(v_list, 'active_sheet_name') else "default"
        
        current_str = config.get_ignore_columns(sheet_name)
        
        if hasattr(grid_widget, '_headers'):
            cols_set = self._parse_ignored_cols(current_str, grid_widget._headers)
            if col_idx in cols_set:
                cols_set.remove(col_idx)
            else:
                cols_set.add(col_idx)
                
            new_str = ", ".join(str(c + 1) for c in sorted(cols_set))
            
            pg_struct = self.pg_struct1 if side == 1 else self.pg_struct2
            pg_struct.update_property("IgnoreCols", new_str)
            
            self._on_property_changed("IgnoreCols", new_str, side)

    def _validate_all_mappings(self):
        invalidated_any = False
        
        mappings = self.tab_mapping.get_sheet_mappings()
        if not mappings: return
        
        for m in mappings:
            bounds1 = self.get_valid_data_bounds(1, m.sheet1_name)
            bounds2 = self.get_valid_data_bounds(2, m.sheet2_name)
            if not bounds1 or not bounds2: continue
            
            ignored1 = {i for i, c in enumerate(bounds1["columns"]) if c[3]}
            ignored2 = {i for i, c in enumerate(bounds2["columns"]) if c[3]}
            
            # 1. Validate Row Mappings (Keys)
            if hasattr(m, 'key_mappings'):
                valid_keys = []
                for k in m.key_mappings:
                    if any(idx in ignored1 for idx in k.col1_indices) or any(idx in ignored2 for idx in k.col2_indices):
                        invalidated_any = True
                    else:
                        valid_keys.append(k)
                m.key_mappings = valid_keys
                
            # 2. Validate Column Mappings
            if hasattr(m, 'column_mappings'):
                valid_cols = []
                for c in m.column_mappings:
                    if c.col1_idx in ignored1 or c.col2_idx in ignored2:
                        invalidated_any = True
                    else:
                        valid_cols.append(c)
                m.column_mappings = valid_cols
                    
        if invalidated_any:
            from tkinter import messagebox
            messagebox.showwarning(
                "Zuordnungen korrigiert",
                "Achtung: Durch Änderungen an den validen Datengrenzen (z.B. ignorierte Spalten/Zeilen) wurden einige deiner Zuordnungen automatisch entfernt, da sie auf nun ignorierte Daten zeigten.\n\nBitte überprüfe die betroffenen Tabs (z.B. Tab 5 oder Tab 6).",
                parent=self
            )

    def _on_notebook_tab_changed(self, event):
        current_tab = self._current_tab_index
        # Tab 2 is the Casting tab
        is_casting = (current_tab == 2)
        self.tree1.show_type_column(is_casting)
        self.tree2.show_type_column(is_casting)
        
        if is_casting:
            self._expand_first_sheet(self.tree1)
            self._expand_first_sheet(self.tree2)
                
            self._detect_types_if_needed(1)
            self._detect_types_if_needed(2)
                
            self._refresh_tree_types(1)
            self._refresh_tree_types(2)
        else:
            self.tree1.clear_all_type_tags()
            self.tree2.clear_all_type_tags()
                
        # Waterfall check: Validate existing mappings against the single-source-of-truth bounds
        self._validate_all_mappings()
        
        # --- Update data for the selected tab ---
        # Robust Data Pipeline: Always fetch latest from Tab 4 and cascade downwards
        if current_tab >= 4: # Zeilen zuordnen
            mappings = self.tab_mapping.get_sheet_mappings()
            self.tab_row_mapping.refresh_data(mappings, ui_update=(current_tab == 4))
            
        if current_tab >= 5: # Spalten zuordnen
            self.tab_column_mapping.load_mappings(self.tab_row_mapping.sheet_mappings, ui_update=(current_tab == 5))

        if current_tab == 6: # Vergleichslogik
            self.tab_comparison.load_mappings(self.tab_column_mapping.sheet_mappings)


    def _parse_ignored_rows(self, s):
        indices = set()
        if not s: return indices
        for part in s.split(","):
            part = part.strip()
            if not part: continue
            if "-" in part:
                parts = part.split("-")
                if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                    indices.update(range(int(parts[0]) - 1, int(parts[1])))
            elif part.isdigit():
                indices.add(int(part) - 1)
        return indices

    def _parse_ignored_cols(self, s, headers):
        indices = set()
        if not s: return indices
        for part in s.split(","):
            part = part.strip()
            if not part: continue
            if part in headers:
                indices.add(headers.index(part))
            elif part.isdigit():
                indices.add(int(part) - 1)
            else:
                part = part.upper()
                res = 0
                valid = True
                for char in part:
                    if 'A' <= char <= 'Z':
                        res = res * 26 + (ord(char) - ord('A') + 1)
                    else:
                        valid = False
                        break
                if valid and res > 0:
                    indices.add(res - 1)
        return indices

    def _on_property_changed(self, key, value, panel_idx=1):
        config = self.config1 if panel_idx == 1 else self.config2
        
        need_reload = False
        
        if key in ("UserName", "ProjectID"):
            if key == "UserName":
                self.config1.user_name = value
                self.config2.user_name = value
            else:
                self.config1.project_id = value
                self.config2.project_id = value
                
            other_idx = 2 if panel_idx == 1 else 1
            other_pg = self.pg_import2 if panel_idx == 1 else self.pg_import1
            other_config = self.config2 if panel_idx == 1 else self.config1
            self._populate_import_grid(other_pg, other_config, f"Datei {other_idx}")
            
        elif key == "Encoding": 
            config.encoding = value
            need_reload = True
        elif key == "CSV.Delimiter": 
            if value == "Benutzerdefiniert":
                from tkinter import simpledialog
                custom_val = simpledialog.askstring("Trennzeichen", "Bitte eigenes Trennzeichen eingeben:", parent=self)
                pg_import = self.pg_import1 if panel_idx == 1 else self.pg_import2
                if custom_val:
                    config.delimiter = custom_val
                    need_reload = True
                
                self._populate_import_grid(pg_import, config, f"Datei {panel_idx}")
            else:
                config.delimiter = value
                need_reload = True
        elif key == "CSV.Quote":
            config.quote_char = value
            need_reload = True
        elif key == "HasHeader":
            val_bool = str(value).lower() in ("true", "1", "yes")
            
            v_list = self.v_list1 if panel_idx == 1 else self.v_list2
            sheet_name = v_list.active_sheet_name if v_list and hasattr(v_list, 'active_sheet_name') else "default"
            
            config.set_has_header(sheet_name, val_bool)
            
            grid_widget = self.grid_left if panel_idx == 1 else self.grid_right
            pg_struct = self.pg_struct1 if panel_idx == 1 else self.pg_struct2
            
            if val_bool:
                current_header = config.get_header_row(sheet_name)
                pg_struct.update_property("HeaderRow", str(current_header))
                
                current_start = config.get_data_start_row(sheet_name)
                if current_start <= current_header:
                    config.set_data_start_row(sheet_name, current_header + 1)
                    pg_struct.update_property("DataStartRow", str(current_header + 1))
            else:
                current_start = config.get_data_start_row(sheet_name)
                current_header = config.get_header_row(sheet_name)
                
                config.set_header_row(sheet_name, 1)
                pg_struct.update_property("HeaderRow", "-")
                
                if current_start == current_header + 1:
                    config.set_data_start_row(sheet_name, 1)
                    pg_struct.update_property("DataStartRow", "1")
                    
            self._refresh_tree_and_grid_headers(panel_idx)
                    
        elif key == "HeaderRow":
            # Normalise: strip whitespace, treat '-' or empty string as "no header".
            stripped = value.strip()
            
            if stripped in ("-", ""):
                # --- Nutzer möchte keine Kopfzeile ---
                # Gleiche Logik wie bei HasHeader=False.
                v_list = self.v_list1 if panel_idx == 1 else self.v_list2
                sheet_name = v_list.active_sheet_name if v_list and hasattr(v_list, 'active_sheet_name') else "default"
                pg_struct = self.pg_struct1 if panel_idx == 1 else self.pg_struct2
                
                current_start = config.get_data_start_row(sheet_name)
                current_header = config.get_header_row(sheet_name)
                
                # Kopfzeile deaktivieren
                config.set_has_header(sheet_name, False)
                config.set_header_row(sheet_name, 1)  # Intern auf 1 zurücksetzen
                pg_struct.update_property("HasHeader", "False")
                pg_struct.update_property("HeaderRow", "-")
                
                # Startzeile ggf. auf 1 zurücksetzen (war durch Kopfzeile verschoben)
                if current_start == current_header + 1:
                    config.set_data_start_row(sheet_name, 1)
                    pg_struct.update_property("DataStartRow", "1")
                
                self._refresh_tree_and_grid_headers(panel_idx)
                return
            
            try:
                val = int(stripped)
                if val >= 1:
                    v_list = self.v_list1 if panel_idx == 1 else self.v_list2
                    sheet_name = v_list.active_sheet_name if v_list and hasattr(v_list, 'active_sheet_name') else "default"
                    pg_struct = self.pg_struct1 if panel_idx == 1 else self.pg_struct2
                    
                    if v_list and val >= v_list.num_rows:
                        from tkinter import messagebox
                        messagebox.showwarning(
                            "Ungültige Kopfzeile", 
                            f"Die angegebene Zeile {val} existiert nicht oder ist die letzte Zeile im Dokument.\nNach der Kopfzeile müssen Daten folgen.", 
                            parent=self
                        )
                        old_val = config.get_header_row(sheet_name)
                        pg_struct.update_property("HeaderRow", str(old_val) if config.get_has_header(sheet_name) else "-")
                        return
                    
                    ignored_rows = self._parse_ignored_rows(config.get_ignore_rows(sheet_name))
                    if (val - 1) in ignored_rows:
                        from tkinter import messagebox
                        messagebox.showwarning(
                            "Ungültige Kopfzeile", 
                            f"Die Zeile {val} wird ignoriert und kann nicht als Kopfzeile verwendet werden.", 
                            parent=self
                        )
                        old_val = config.get_header_row(sheet_name)
                        pg_struct.update_property("HeaderRow", str(old_val) if config.get_has_header(sheet_name) else "-")
                        return
                        
                    current_end = config.get_data_end_row(sheet_name)
                    if current_end > 0 and val >= current_end:
                        from tkinter import messagebox
                        messagebox.showwarning(
                            "Ungültige Kopfzeile", 
                            f"Die Kopfzeile ({val}) darf nicht auf oder hinter der Endzeile ({current_end}) liegen.", 
                            parent=self
                        )
                        old_val = config.get_header_row(sheet_name)
                        pg_struct.update_property("HeaderRow", str(old_val) if config.get_has_header(sheet_name) else "-")
                        return
                    
                    if not config.get_has_header(sheet_name):
                        config.set_has_header(sheet_name, True)
                        pg_struct.update_property("HasHeader", "True")
                    
                    current_start = config.get_data_start_row(sheet_name)
                    config.set_header_row(sheet_name, val)
                    if current_start <= val:
                        config.set_data_start_row(sheet_name, val + 1)
                        
                    pg_struct.update_property("DataStartRow", str(config.get_data_start_row(sheet_name)))
                    
                    self._refresh_tree_and_grid_headers(panel_idx)
                else:
                    raise ValueError()
            except ValueError:
                from tkinter import messagebox
                messagebox.showerror(
                    "Ungültige Eingabe",
                    "Die Kopfzeile muss eine gültige Zahl (>= 1) sein\noder '-' für keine Kopfzeile.",
                    parent=self
                )
                v_list = self.v_list1 if panel_idx == 1 else self.v_list2
                sheet_name = v_list.active_sheet_name if v_list and hasattr(v_list, 'active_sheet_name') else "default"
                pg_struct = self.pg_struct1 if panel_idx == 1 else self.pg_struct2
                old_val = config.get_header_row(sheet_name)
                pg_struct.update_property("HeaderRow", str(old_val) if config.get_has_header(sheet_name) else "-")

        elif key == "DataStartRow":
            try:
                val = int(value)
                if val >= 1:
                    v_list = self.v_list1 if panel_idx == 1 else self.v_list2
                    sheet_name = v_list.active_sheet_name if v_list and hasattr(v_list, 'active_sheet_name') else "default"
                    pg_struct = self.pg_struct1 if panel_idx == 1 else self.pg_struct2
                    
                    if v_list and val > v_list.num_rows:
                        from tkinter import messagebox
                        messagebox.showwarning("Ungültige Startzeile", f"Die Datei hat nur {v_list.num_rows} Zeilen.", parent=self)
                        pg_struct.update_property("DataStartRow", str(config.get_data_start_row(sheet_name)))
                        return
                        
                    if config.get_has_header(sheet_name):
                        if val <= config.get_header_row(sheet_name):
                            from tkinter import messagebox
                            messagebox.showwarning("Ungültige Startzeile", "Die Start-Datenzeile darf nicht vor oder auf der Kopfzeile liegen.", parent=self)
                            pg_struct.update_property("DataStartRow", str(config.get_data_start_row(sheet_name)))
                            return
                            
                    current_end = config.get_data_end_row(sheet_name)
                    if current_end > 0 and val > current_end:
                        from tkinter import messagebox
                        messagebox.showwarning("Ungültige Startzeile", f"Die Start-Datenzeile ({val}) darf nicht hinter der Endzeile ({current_end}) liegen.", parent=self)
                        pg_struct.update_property("DataStartRow", str(config.get_data_start_row(sheet_name)))
                        return
                        
                    config.set_data_start_row(sheet_name, val)
                    self._refresh_tree_and_grid_headers(panel_idx)
                    grid_widget = self.grid_left if panel_idx == 1 else self.grid_right
                    grid_widget.reset_types_state()
                    grid_widget.scroll_to_row(val - 1)
                else:
                    raise ValueError()
            except ValueError:
                from tkinter import messagebox
                messagebox.showerror("Ungültige Eingabe", "Die Startzeile muss eine gültige Zahl (>= 1) sein.", parent=self)
                v_list = self.v_list1 if panel_idx == 1 else self.v_list2
                sheet_name = v_list.active_sheet_name if v_list and hasattr(v_list, 'active_sheet_name') else "default"
                pg_struct = self.pg_struct1 if panel_idx == 1 else self.pg_struct2
                old_val = config.get_data_start_row(sheet_name)
                pg_struct.update_property("DataStartRow", str(old_val))

        elif key == "DataEndRow":
            if str(value).strip() in ("", "-"):
                value = 0
            try:
                val = int(value)
                v_list = self.v_list1 if panel_idx == 1 else self.v_list2
                sheet_name = v_list.active_sheet_name if v_list and hasattr(v_list, 'active_sheet_name') else "default"
                pg_struct = self.pg_struct1 if panel_idx == 1 else self.pg_struct2
                
                if val < 0: val = 0
                if v_list and val > v_list.num_rows:
                    from tkinter import messagebox
                    messagebox.showwarning("Ungültige Endzeile", f"Die Datei hat nur {v_list.num_rows} Zeilen.", parent=self)
                    
                    old_val = config.get_data_end_row(sheet_name)
                    pg_struct.update_property("DataEndRow", "-" if old_val == 0 else str(old_val))
                    return
                
                if val > 0:
                    current_start = config.get_data_start_row(sheet_name)
                    if val < current_start:
                        from tkinter import messagebox
                        messagebox.showwarning("Ungültige Endzeile", f"Die Endzeile ({val}) darf nicht vor der Start-Datenzeile ({current_start}) liegen.", parent=self)
                        old_val = config.get_data_end_row(sheet_name)
                        pg_struct.update_property("DataEndRow", "-" if old_val == 0 else str(old_val))
                        return
                    
                config.set_data_end_row(sheet_name, val)
                self._refresh_tree_and_grid_headers(panel_idx)
                
                grid_widget = self.grid_left if panel_idx == 1 else self.grid_right
                grid_widget.reset_types_state()
                
                if val > 0:
                    grid_widget.scroll_to_row(val - 1)
                else:
                    pg_struct.update_property("DataEndRow", "-")
            except ValueError:
                from tkinter import messagebox
                messagebox.showerror("Ungültige Eingabe", "Die Endzeile muss eine gültige Zahl sein oder '-' für keine Begrenzung.", parent=self)
                v_list = self.v_list1 if panel_idx == 1 else self.v_list2
                sheet_name = v_list.active_sheet_name if v_list and hasattr(v_list, 'active_sheet_name') else "default"
                pg_struct = self.pg_struct1 if panel_idx == 1 else self.pg_struct2
                old_val = config.get_data_end_row(sheet_name)
                pg_struct.update_property("DataEndRow", "-" if old_val == 0 else str(old_val))

        elif key == "IgnoreCols":
            v_list = self.v_list1 if panel_idx == 1 else self.v_list2
            sheet_name = v_list.active_sheet_name if v_list and hasattr(v_list, 'active_sheet_name') else "default"
            grid_widget = self.grid_left if panel_idx == 1 else self.grid_right
            pg_struct = self.pg_struct1 if panel_idx == 1 else self.pg_struct2
            
            val_str = str(value).strip()
            if val_str:
                import re
                if not re.match(r'^[a-zA-Z0-9,\s]+$', val_str):
                    from tkinter import messagebox
                    messagebox.showerror("Ungültige Eingabe", "Ungültige Spaltenangabe. Erlaubt sind Spaltennamen (A, B) oder Zahlen (1, 2) getrennt durch Komma.", parent=self)
                    old_val = config.get_ignore_columns(sheet_name)
                    pg_struct.update_property("IgnoreCols", old_val)
                    return
                    
            config.set_ignore_columns(sheet_name, val_str)
            self._invalidate_keys_for_sheet(panel_idx, sheet_name)
            self._refresh_tree_and_grid_headers(panel_idx)
            if hasattr(grid_widget, '_headers'):
                cols = self._parse_ignored_cols(val_str, grid_widget._headers)
                grid_widget.set_ignored_cols(cols)
                grid_widget.reset_types_state()
                if cols:
                    grid_widget.scroll_to_col(min(cols))

        elif key == "IgnoreRows":
            v_list = self.v_list1 if panel_idx == 1 else self.v_list2
            sheet_name = v_list.active_sheet_name if v_list and hasattr(v_list, 'active_sheet_name') else "default"
            grid_widget = self.grid_left if panel_idx == 1 else self.grid_right
            pg_struct = self.pg_struct1 if panel_idx == 1 else self.pg_struct2
            
            val_str = str(value).strip()
            if val_str:
                import re
                if not re.match(r'^[0-9,\s\-]+$', val_str):
                    from tkinter import messagebox
                    messagebox.showerror("Ungültige Eingabe", "Ungültige Zeilenangabe. Erlaubt sind Zahlen (1, 2) oder Bereiche (1-5) getrennt durch Komma.", parent=self)
                    old_val = config.get_ignore_rows(sheet_name)
                    pg_struct.update_property("IgnoreRows", old_val)
                    return
                    
            rows = self._parse_ignored_rows(val_str)
            
            config.set_ignore_rows(sheet_name, val_str)
            self._invalidate_keys_for_sheet(panel_idx, sheet_name)
            
            header_was_deactivated = False
            if config.get_has_header(sheet_name):
                hr_idx = config.get_header_row(sheet_name) - 1
                if hr_idx in rows:
                    config.set_has_header(sheet_name, False)
                    config.set_header_row(sheet_name, 1)
                    pg_struct.update_property("HasHeader", "False")
                    pg_struct.update_property("HeaderRow", "-")
                    header_was_deactivated = True

            if header_was_deactivated:
                self._refresh_tree_and_grid_headers(panel_idx)
            else:
                grid_widget.set_ignored_rows(rows)
                grid_widget.reset_types_state()
                
            if rows:
                grid_widget.scroll_to_row(min(rows))
                
        elif key == "Fmt.Decimal":
            if "Punkt" in value: config.decimal_separator = "."
            elif "Komma" in value: config.decimal_separator = ","
            else: config.decimal_separator = value
            grid_widget = self.grid_left if panel_idx == 1 else self.grid_right
            grid_widget.reset_types_state()
            grid_widget.redraw()
            
        elif key == "Fmt.Thousand":
            if "Kein" in value: config.thousands_separator = ""
            elif "Punkt" in value: config.thousands_separator = "."
            elif "Komma" in value: config.thousands_separator = ","
            elif "Leerzeichen" in value: config.thousands_separator = " "
            else: config.thousands_separator = value
            grid_widget = self.grid_left if panel_idx == 1 else self.grid_right
            grid_widget.reset_types_state()
            grid_widget.redraw()
            
        elif key in ["TrimSpace", "IgnoreCase", "NormUmlaut"]:
            bool_val = (value == "True")
            other_config = self.config2 if panel_idx == 1 else self.config1
            other_grid = self.pg_struct2 if panel_idx == 1 else self.pg_struct1
            other_data_grid = self.grid_right if panel_idx == 1 else self.grid_left

            if key == "TrimSpace": 
                config.trim_whitespace = bool_val
                other_config.trim_whitespace = bool_val
            elif key == "IgnoreCase": 
                config.case_insensitive = bool_val
                other_config.case_insensitive = bool_val
            elif key == "NormUmlaut": 
                config.normalize_umlauts = bool_val
                other_config.normalize_umlauts = bool_val
                
            grid_widget = self.grid_left if panel_idx == 1 else self.grid_right
            grid_widget.reset_types_state()
            grid_widget.redraw()
            
            other_grid.update_property(key, value)
            other_data_grid.reset_types_state()
            other_data_grid.redraw()
            
        elif key in ["NaValues", "TrueValues", "FalseValues"]:
            other_config = self.config2 if panel_idx == 1 else self.config1
            other_grid = self.pg_struct2 if panel_idx == 1 else self.pg_struct1
            other_data_grid = self.grid_right if panel_idx == 1 else self.grid_left

            if key == "NaValues": 
                config.na_values = value
                other_config.na_values = value
            elif key == "TrueValues": 
                config.true_values = value
                other_config.true_values = value
            elif key == "FalseValues": 
                config.false_values = value
                other_config.false_values = value
                
            grid_widget = self.grid_left if panel_idx == 1 else self.grid_right
            grid_widget.reset_types_state()
            grid_widget.redraw()
            
            other_grid.update_property(key, value)
            other_data_grid.reset_types_state()
            other_data_grid.redraw()
                
        elif key == "Timezone":
            config.timezone = value
            grid_widget = self.grid_left if panel_idx == 1 else self.grid_right
            grid_widget.redraw()

        elif key in ["ColorTrue", "ColorFalse", "ColorNotComp", "ColorCountDiff"]:
            other_config = self.config2 if panel_idx == 1 else self.config1
            other_grid = self.pg_struct2 if panel_idx == 1 else self.pg_struct1
            
            if key == "ColorTrue": 
                config.color_true = value
                other_config.color_true = value
            elif key == "ColorFalse": 
                config.color_false = value
                other_config.color_false = value
            elif key == "ColorNotComp": 
                config.color_not_comp = value
                other_config.color_not_comp = value
            elif key == "ColorCountDiff": 
                config.color_count_diff = value
                other_config.color_count_diff = value
            
            other_grid.update_property(key, value)


        if need_reload:
            self.after(50, lambda: self._reload_file_with_config(panel_idx))

    def _populate_import_grid(self, grid: TkPropertyGrid, config: FileParsingConfig, title: str):
        grid.clear()
        
        # --- 1. Datei & Audit ---
        grid.add_category("Datei & Audit")
        grid.add_property("Datei Hash", getattr(config, "file_hash", "N/A"), "FileHash", read_only=True)
        grid.add_property("Benutzer / Prüfer", config.user_name, "UserName")
        grid.add_property("Projekt / Kontext", config.project_id, "ProjectID")

        # --- 2. Dateityp & Encoding ---
        grid.add_category(f"Encoding: {title}")
        grid.add_enum("Encoding", "Encoding", choices=["Auto"] + config.ENCODINGS, current_val=config.encoding)

        # --- 3. CSV Syntax / Parser Details ---
        if config.file_type != "Excel":
            grid.add_category("Syntax / Parser")
            delim_labels = ["Auto"] + config.DELIMITER_LABELS
            if config.delimiter not in delim_labels and config.delimiter != "Auto":
                delim_labels.insert(1, config.delimiter)
                
            grid.add_enum("Trennzeichen", "CSV.Delimiter", choices=delim_labels, current_val=config.delimiter)
            grid.add_property("Text-Quote", config.quote_char, "CSV.Quote")

    def _get_rounding_display(self, config):
        if config.rounding_decimal_places is None:
            return "Aus"
        method_str = "Aufrunden"
        if getattr(config, 'rounding_method', 'HALF_EVEN') == "FLOOR":
            method_str = "Abrunden"
        elif getattr(config, 'rounding_method', 'HALF_EVEN') == "HALF_EVEN":
            method_str = "Gerade Zahl bleibt"
        return f"{config.rounding_decimal_places} Stellen ({method_str})"

    def _populate_structure_grid(self, grid: TkPropertyGrid, config: FileParsingConfig, title: str, active_sheet: str = "default"):
        grid.clear()
        
        # --- 1. Struktur (Dimensionen) ---
        grid.add_category("Datenbereich & Struktur")
        has_hdr = config.get_has_header(active_sheet)
        
        header_val = str(config.get_header_row(active_sheet)) if has_hdr else "-"
        grid.add_property("Nummer Kopfzeile", header_val, "HeaderRow")
        
        grid.add_property("Start Datenzeile", str(config.get_data_start_row(active_sheet)), "DataStartRow")
        
        end_row = config.get_data_end_row(active_sheet)
        end_row_val = "-" if end_row == 0 else str(end_row)
        grid.add_property("Ende Datenzeile", end_row_val, "DataEndRow")
        
        grid.add_property("Spalten ignorieren (Namen/Index)", config.get_ignore_columns(active_sheet), "IgnoreCols")
        grid.add_property("Zeilen ignorieren (Index)", config.get_ignore_rows(active_sheet), "IgnoreRows")

        # --- 3. Formate & Normalisierung ---
        grid.add_category("Formate & Normalisierung")
        grid.add_enum("Dezimaltrennzeichen", "Fmt.Decimal", choices=config.DECIMAL_LABELS, current_val=config.decimal_separator)
        grid.add_enum("Tausendertrennzeichen", "Fmt.Thousand", choices=config.THOUSAND_LABELS, current_val=config.thousands_separator)
        panel_idx = 1 if grid == getattr(self, 'pg_struct1', None) else 2
        grid.add_dialog("Runden auf Stellen", self._get_rounding_display(config), "Rounding", callback=lambda p=panel_idx, c=config, g=grid: self._open_rounding_dialog(p, c, g))
        grid.add_dialog("Zeitzone (IANA)", config.timezone, "Timezone", callback=lambda p=panel_idx, c=config, g=grid: self._open_timezone_dialog(p, c, g))
        grid.add_boolean("Leerzeichen trimmen", "TrimSpace", current_val=config.trim_whitespace)
        grid.add_boolean("Groß-/Kleinschreibung ignorieren", "IgnoreCase", current_val=config.case_insensitive)
        grid.add_boolean("Umlaute normalisieren (ue/ss)", "NormUmlaut", current_val=config.normalize_umlauts)

        # --- 4. Werte-Definitionen ---
        grid.add_category("Werte-Definitionen")
        panel_idx = 1 if grid == getattr(self, 'pg_struct1', None) else 2
        grid.add_dialog("Als 'Leer' (NULL) behandeln", config.na_values, "NaValues", callback=lambda p=panel_idx, c=config, g=grid: self._open_values_dialog(p, c, g, "NaValues", "Werte für 'Leer'"))
        grid.add_dialog("Als 'Wahr' behandeln", config.true_values, "TrueValues", callback=lambda p=panel_idx, c=config, g=grid: self._open_values_dialog(p, c, g, "TrueValues", "Werte für 'Wahr'"))
        grid.add_dialog("Als 'Falsch' behandeln", config.false_values, "FalseValues", callback=lambda p=panel_idx, c=config, g=grid: self._open_values_dialog(p, c, g, "FalseValues", "Werte für 'Falsch'"))

        # --- 5. UI / Farben ---
        grid.add_category("Darstellung (Farben)")
        grid.add_color("Farbe: True", "ColorTrue", current_val=config.color_true)
        grid.add_color("Farbe: False", "ColorFalse", current_val=config.color_false)
        grid.add_color("Farbe: Nicht vergleichbar", "ColorNotComp", current_val=config.color_not_comp)
        grid.add_color("Farbe: Anzahl unterschiedlich", "ColorCountDiff", current_val=config.color_count_diff)

    def _open_rounding_dialog(self, panel_idx, config, grid_widget):
        top = tk.Toplevel(self)
        top.title("Rundungs-Einstellungen")
        top.minsize(380, 320)
        top.transient(self)
        top.grab_set()
        top.focus_set()

        # Center dialog
        top.update_idletasks()
        x = self.winfo_rootx() + (self.winfo_width() - top.winfo_width()) // 2
        y = self.winfo_rooty() + (self.winfo_height() - top.winfo_height()) // 2
        top.geometry(f"+{x}+{y}")

        # Apply Dark Mode Title Bar
        is_dark = (self.current_theme == "dark")
        try:
            import ctypes
            top.update_idletasks()
            hwnd = ctypes.windll.user32.GetParent(top.winfo_id())
            rendering_policy = ctypes.c_int(1 if is_dark else 0)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(rendering_policy), ctypes.sizeof(rendering_policy))
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 19, ctypes.byref(rendering_policy), ctypes.sizeof(rendering_policy))
        except Exception:
            pass

        main_frame = tk.Frame(top, padx=15, pady=15)
        main_frame.pack(fill=tk.BOTH, expand=True)

        is_active = tk.BooleanVar(value=(config.rounding_decimal_places is not None))
        dec_places = tk.IntVar(value=(config.rounding_decimal_places if config.rounding_decimal_places is not None else 0))
        method = tk.StringVar(value=getattr(config, 'rounding_method', 'HALF_EVEN'))

        chk_active = ScalingCheckbox(main_frame, text="Runden aktivieren", variable=is_active)
        chk_active.pack(anchor="w", pady=(0, 15))

        details_frame = tk.Frame(main_frame)
        details_frame.pack(fill=tk.X, expand=True)

        lbl_places = tk.Label(details_frame, text="Nachkommastellen:")
        lbl_places.grid(row=0, column=0, sticky="w", pady=2)

        spin_places = tk.Spinbox(details_frame, from_=0, to=10, textvariable=dec_places, width=5)
        spin_places.grid(row=0, column=1, sticky="w", pady=2, padx=10)

        lbl_method = tk.Label(details_frame, text="Methode:")
        lbl_method.grid(row=1, column=0, sticky="nw", pady=(15, 2))

        methods_frame = tk.Frame(details_frame)
        methods_frame.grid(row=1, column=1, sticky="w", pady=(15, 2), padx=10)

        rb1 = ScalingRadiobutton(methods_frame, text="Aufrunden", variable=method, value="CEIL")
        rb1.pack(anchor="w", pady=2)
        rb2 = ScalingRadiobutton(methods_frame, text="Abrunden", variable=method, value="FLOOR")
        rb2.pack(anchor="w", pady=2)

        banker_frame = tk.Frame(methods_frame)
        banker_frame.pack(anchor="w", fill=tk.X, pady=2)
        rb3 = ScalingRadiobutton(banker_frame, text="Gerade Zahl bleibt", variable=method, value="HALF_EVEN")
        rb3.pack(side=tk.LEFT)

        lbl_help = tk.Label(banker_frame, text="[?]", foreground="#0b57d0", cursor="hand2", font=("Segoe UI", 9, "bold"))
        lbl_help.pack(side=tk.LEFT, padx=5)

        def show_help(event):
            if hasattr(lbl_help, 'tw') and lbl_help.tw:
                return
            tw = tk.Toplevel(lbl_help)
            tw.wm_overrideredirect(True)
            tx = lbl_help.winfo_rootx() + 20
            ty = lbl_help.winfo_rooty() + 20
            tw.wm_geometry(f"+{tx}+{ty}")
            text = "Banker's Rounding:\nDie letzte Ziffer wird zur nächsten\ngeraden Zahl gerundet.\n\nBeispiel:\n2,25 -> 2,2\n2,35 -> 2,4"
            lbl = tk.Label(tw, text=text, justify='left', background="#ffffe0", relief='solid', borderwidth=1, font=("Segoe UI", 10), padx=8, pady=5)
            lbl.pack()
            lbl_help.tw = tw

            def hide_help(e):
                if hasattr(lbl_help, 'tw') and lbl_help.tw:
                    lbl_help.tw.destroy()
                    lbl_help.tw = None

            tw.bind("<Leave>", hide_help)
            lbl_help.bind("<Leave>", hide_help)
            # Auto-hide after 5s just in case
            tw.after(5000, lambda: hide_help(None))

        lbl_help.bind("<Enter>", show_help)

        def toggle_state(*args):
            state = tk.NORMAL if is_active.get() else tk.DISABLED
            spin_places.config(state=state)
            rb1.config(state=state)
            rb2.config(state=state)
            rb3.config(state=state)

        is_active.trace_add("write", toggle_state)
        toggle_state()

        btn_frame = tk.Frame(top)
        btn_frame.pack(fill=tk.X, side=tk.BOTTOM, pady=10, padx=15)

        def on_ok():
            if is_active.get():
                try:
                    config.rounding_decimal_places = int(dec_places.get())
                except ValueError:
                    config.rounding_decimal_places = 0
                config.rounding_method = method.get()
            else:
                config.rounding_decimal_places = None
            grid_widget.update_property("Rounding", self._get_rounding_display(config))
            top.destroy()
            
        def on_cancel():
            top.destroy()

        btn_cancel = tk.Button(btn_frame, text="Abbrechen", command=on_cancel, width=12)
        btn_cancel.pack(side=tk.RIGHT, padx=(5, 0))
        btn_ok = tk.Button(btn_frame, text="OK", command=on_ok, width=12)
        btn_ok.pack(side=tk.RIGHT)
        
        # Apply themes to all new tk widgets
        self._apply_colors(top)
        
        # Override specific button colors if in dark mode so they stand out
        if is_dark:
            btn_ok.config(bg="#0b57d0", fg="#ffffff", activebackground="#005c94", relief="flat")
            btn_cancel.config(bg="#3c4043", fg="#ffffff", activebackground="#5f6368", relief="flat")
            
        top.zoom_manager = ZoomManager(top, zoom_id="dialog_rounding")

    def _open_values_dialog(self, panel_idx, config, grid_widget, prop_key, title_text):
        top = tk.Toplevel(self)
        top.title(title_text)
        top.minsize(420, 160)
        top.transient(self)
        top.grab_set()
        top.focus_set()

        # Center dialog
        top.update_idletasks()
        x = self.winfo_rootx() + (self.winfo_width() - top.winfo_width()) // 2
        y = self.winfo_rooty() + (self.winfo_height() - top.winfo_height()) // 2
        top.geometry(f"+{x}+{y}")
        
        # Apply Dark Mode Title Bar
        is_dark = (self.current_theme == "dark")
        try:
            import ctypes
            top.update_idletasks()
            hwnd = ctypes.windll.user32.GetParent(top.winfo_id())
            rendering_policy = ctypes.c_int(1 if is_dark else 0)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(rendering_policy), ctypes.sizeof(rendering_policy))
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 19, ctypes.byref(rendering_policy), ctypes.sizeof(rendering_policy))
        except Exception:
            pass

        main_frame = tk.Frame(top, padx=15, pady=15)
        main_frame.pack(fill=tk.BOTH, expand=True)

        lbl = tk.Label(main_frame, text=f"{title_text} (kommagetrennt):")
        lbl.pack(anchor="w", pady=(0, 5))

        current_val = ""
        if prop_key == "NaValues": current_val = config.na_values
        elif prop_key == "TrueValues": current_val = config.true_values
        elif prop_key == "FalseValues": current_val = config.false_values

        val_var = tk.StringVar(value=current_val)
        entry = tk.Entry(main_frame, textvariable=val_var, font=("Segoe UI", 11))
        entry.pack(fill=tk.X, pady=5)
        entry.focus_set()

        btn_frame = tk.Frame(top)
        btn_frame.pack(fill=tk.X, side=tk.BOTTOM, pady=10, padx=15)

        def on_ok(*args):
            new_val = val_var.get()
            other_config = self.config2 if panel_idx == 1 else self.config1
            other_grid = self.pg_struct2 if panel_idx == 1 else self.pg_struct1
            other_data_grid = self.grid_right if panel_idx == 1 else self.grid_left

            if prop_key == "NaValues": 
                config.na_values = new_val
                other_config.na_values = new_val
            elif prop_key == "TrueValues": 
                config.true_values = new_val
                other_config.true_values = new_val
            elif prop_key == "FalseValues": 
                config.false_values = new_val
                other_config.false_values = new_val
            
            grid_widget.update_property(prop_key, new_val)
            data_grid = self.grid_left if panel_idx == 1 else self.grid_right
            data_grid.reset_types_state()
            data_grid.redraw()
            
            other_grid.update_property(prop_key, new_val)
            other_data_grid.reset_types_state()
            other_data_grid.redraw()
            
            top.destroy()

        btn_cancel = tk.Button(btn_frame, text="Abbrechen", command=top.destroy, width=12)
        btn_cancel.pack(side=tk.RIGHT, padx=(5, 0))
        btn_ok = tk.Button(btn_frame, text="OK", command=on_ok, width=12)
        btn_ok.pack(side=tk.RIGHT)
        
        # Apply themes to all new tk widgets
        self._apply_colors(top)
        
        # Override specific button colors if in dark mode so they stand out
        if is_dark:
            btn_ok.config(bg="#0b57d0", fg="#ffffff", activebackground="#005c94", relief="flat")
            btn_cancel.config(bg="#3c4043", fg="#ffffff", activebackground="#5f6368", relief="flat")
            
        top.zoom_manager = ZoomManager(top, zoom_id="dialog_values")
        
        entry.bind("<Return>", on_ok)

    def _open_timezone_dialog(self, panel_idx, config, pg_struct):
        top = tk.Toplevel(self)
        top.title("Zeitzone auswählen")
        top.minsize(450, 500)
        top.transient(self)
        top.grab_set()
        top.focus_set()

        top.update_idletasks()
        x = self.winfo_rootx() + (self.winfo_width() - top.winfo_width()) // 2
        y = self.winfo_rooty() + (self.winfo_height() - top.winfo_height()) // 2
        top.geometry(f"+{x}+{y}")
        
        # Apply Dark Mode Title Bar
        is_dark = (self.current_theme == "dark")
        try:
            import ctypes
            top.update_idletasks()
            hwnd = ctypes.windll.user32.GetParent(top.winfo_id())
            rendering_policy = ctypes.c_int(1 if is_dark else 0)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(rendering_policy), ctypes.sizeof(rendering_policy))
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 19, ctypes.byref(rendering_policy), ctypes.sizeof(rendering_policy))
        except Exception:
            pass

        main_frame = tk.Frame(top, padx=15, pady=15)
        main_frame.pack(fill=tk.BOTH, expand=True)

        lbl = tk.Label(main_frame, text="Suchen Sie nach einer Zeitzone (z.B. Berlin, UTC, America):")
        lbl.pack(anchor="w", pady=(0, 5))

        search_var = tk.StringVar()
        entry = tk.Entry(main_frame, textvariable=search_var, font=("Arial", 11))
        entry.pack(fill=tk.X, pady=5)

        list_frame = tk.Frame(main_frame, bg="#ffffff", bd=1, relief="sunken")
        list_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        listbox = tk.Listbox(list_frame, font=("Arial", 10), selectbackground="#0b57d0", selectforeground="#ffffff", highlightthickness=0, yscrollcommand=scrollbar.set)
        listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=listbox.yview)

        def update_list(*args):
            search = search_var.get().lower()
            listbox.delete(0, tk.END)
            for tz in AVAILABLE_TIMEZONES:
                if search in tz.lower():
                    listbox.insert(tk.END, tz)
            
            if not search and config.timezone in AVAILABLE_TIMEZONES:
                try:
                    idx = listbox.get(0, tk.END).index(config.timezone)
                    listbox.selection_set(idx)
                    listbox.see(idx)
                except ValueError:
                    pass

        update_list()
        search_var.trace_add("write", update_list)

        btn_frame = tk.Frame(top)
        btn_frame.pack(fill=tk.X, side=tk.BOTTOM, pady=10, padx=15)

        def on_ok(*args):
            sel = listbox.curselection()
            if sel:
                tz = listbox.get(sel[0])
                config.timezone = tz
                pg_struct.update_property("Timezone", tz)
                
                # Trigger real-time visual update
                data_grid = self.grid_left if panel_idx == 1 else self.grid_right
                data_grid.redraw()
                
                # We also need to reload data since parsing changes
                self.after(50, lambda: self._reload_file_with_config(panel_idx))
            top.destroy()

        btn_cancel = tk.Button(btn_frame, text="Abbrechen", command=top.destroy, width=12)
        btn_cancel.pack(side=tk.RIGHT, padx=(5, 0))
        btn_ok = tk.Button(btn_frame, text="OK", command=on_ok, width=12)
        btn_ok.pack(side=tk.RIGHT)
        
        # Apply themes to all new tk widgets
        self._apply_colors(top)
        
        # Override specific button colors if in dark mode so they stand out
        if is_dark:
            btn_ok.config(bg="#0b57d0", fg="#ffffff", activebackground="#005c94", relief="flat")
            btn_cancel.config(bg="#3c4043", fg="#ffffff", activebackground="#5f6368", relief="flat")
            
        top.zoom_manager = ZoomManager(top, zoom_id="dialog_timezone")

        listbox.bind("<Double-1>", lambda e: on_ok())
        entry.bind("<Return>", lambda e: on_ok() if listbox.curselection() else listbox.selection_set(0) or on_ok() if listbox.size()>0 else None)
        entry.bind("<Down>", lambda e: listbox.focus_set() or listbox.selection_set(0))
        entry.focus_set()

    def _populate_settings_grids(self):
        self._populate_import_grid(self.pg_import1, self.config1, "Datei 1")
        self._populate_import_grid(self.pg_import2, self.config2, "Datei 2")
        self._populate_structure_grid(self.pg_struct1, self.config1, "Datei 1")
        self._populate_structure_grid(self.pg_struct2, self.config2, "Datei 2")

    def _update_nav_button_text(self, grid, text):
        for item in grid._data:
            if item.get("id") == "NavButton":
                item["value"] = text
                break
        grid.redraw()

    def _on_manual_mode_toggled(self, is_manual):
        """Called when the manual mapping mode is toggled."""
        # Adjust columns for Tab 5 and 6
        if hasattr(self, '_current_tab_index'):
            if self._current_tab_index == 4:
                self._update_trees_for_tab(expand_columns=is_manual, force_select_first=False)
            elif self._current_tab_index == 5:
                self._update_trees_for_tab(expand_columns=True, force_select_first=False)

    def _save_grid_scroll(self, side, grid, sheet_name):
        if not hasattr(self, '_grid_scroll_memory'):
            self._grid_scroll_memory = {}
        try:
            x, y = grid.get_scroll_fraction()
            self._grid_scroll_memory[(side, sheet_name)] = (x, y)
        except Exception:
            pass

    def _restore_grid_scroll(self, side, grid, sheet_name):
        if not hasattr(self, '_grid_scroll_memory'):
            return
        state = self._grid_scroll_memory.get((side, sheet_name))
        if state:
            x, y = state
            self.root_frame.after(10, lambda: self._apply_grid_scroll(grid, x, y))
            
    def _apply_grid_scroll(self, grid, x, y):
        try:
            grid.set_scroll_fraction(x, y)
            grid.redraw()
        except Exception:
            pass

    def _on_tree_click_mapping(self, event, side):
        tree = self.tree1 if side == 1 else self.tree2
        iid = tree.identify_row(event.y)
        if not iid: return
        
        tags = tree.item(iid, "tags")
        if "ignored_col" in tags: return
        
        text = tree.item(iid, "text")
        parent = tree.parent(iid)
        
        is_sheet = False
        if parent != "" and tree.parent(parent) == "":
            is_sheet = True
            
        if is_sheet:
            if side == 1:
                self.tab_mapping.set_manual_selection(left_val=text)
            else:
                self.tab_mapping.set_manual_selection(right_val=text)

    def _on_tree_select(self, side):
        tree = self.tree1 if side == 1 else self.tree2
        selected = tree.selection()
        if not selected: return
            
        iid = selected[0]
        
        tags = tree.item(iid, "tags")
        if "ignored_col" in tags:
            tree.selection_remove(iid)
            return
            
        text = tree.item(iid, "text")
        parent = tree.parent(iid)
        
        is_sheet = False
        is_file_root = False
        if parent != "" and tree.parent(parent) == "":
            is_sheet = True
        elif parent == "" and not tree.get_children(iid):
            # It's root and has no children -> it's a file acting as its own sheet
            is_sheet = True
            is_file_root = True
        elif parent == "" and tree.get_children(iid):
            is_file_root = True
            
        config = self.config1 if side == 1 else self.config2
        pg_import = self.pg_import1 if side == 1 else self.pg_import2
        v_list = self.v_list1 if side == 1 else self.v_list2
        
        if self._current_tab_index == 0:
            if is_file_root:
                pg_import.update_property("FileHash", getattr(config, "file_hash", "N/A"))
            elif is_sheet and v_list:
                pg_import.update_property("FileHash", v_list.get_sheet_hash(text))
            
        if is_sheet:
            # Switch the grid view to the selected sheet
            target_grid = self.grid_left if side == 1 else self.grid_right
            
            if v_list:
                old_sheet = getattr(v_list, 'active_sheet_name', None)
                if old_sheet:
                    self._save_grid_scroll(side, target_grid, old_sheet)
                    
                v_list.set_active_sheet(text)
                
                # Update Structure grid for the specific sheet
                pg_struct = self.pg_struct1 if side == 1 else self.pg_struct2
                self._populate_structure_grid(pg_struct, config, f"Datei {side}", active_sheet=text)
                
                # Helper function for A, B, C column identifiers
                def get_col_name(n):
                    res = ""
                    while n >= 0:
                        res = chr(n % 26 + 65) + res
                        n = n // 26 - 1
                    return res
                
                standard_headers = [get_col_name(i) for i in range(v_list.num_cols)]
                target_grid._batch_updating = True
                try:
                    target_grid.set_data(v_list, standard_headers)
                    
                    # Update visual grid header row marking after data is set
                    target_grid.set_header_row(config.get_header_row(text) - 1 if config.get_has_header(text) else None)
                    target_grid.set_data_bounds(config.get_data_start_row(text) - 1, config.get_data_end_row(text))
                    target_grid.set_ignored_rows(self._parse_ignored_rows(config.get_ignore_rows(text)))
                    target_grid.set_ignored_cols(self._parse_ignored_cols(config.get_ignore_columns(text), standard_headers))
                finally:
                    target_grid._batch_updating = False
                    target_grid._sync_and_redraw()
                
                self._restore_grid_scroll(side, target_grid, text)
                
            if self._current_tab_index == 2:
                self._detect_types_if_needed(side)
                self._refresh_tree_types(side)
                
        # Handle column selection for row mapping and Tab 3
        is_column = False
        if not is_sheet and parent != "":
            grandparent = tree.parent(parent)
            if grandparent != "" and tree.parent(grandparent) == "":
                is_column = True
                
        if is_column:
            if self._current_tab_index == 2:
                # Tab 3: Left click scrolls the grid exactly like right click does
                sheet_iid = parent
                children = tree.get_children(sheet_iid)
                if iid in children:
                    col_idx = children.index(iid)
                    grid = self.grid_left if side == 1 else self.grid_right
                    grid._clear_selection()
                    grid.selected_cols.add(col_idx)
                    
                    grid.scroll_to_col(col_idx)
                    grid.redraw()
            elif self._current_tab_index in (4, 5):
                sheet_iid = parent
                children = tree.get_children(sheet_iid)
                col_idx = -1
                if iid in children:
                    col_idx = children.index(iid)

                display_text = text
                if "     " in text:
                    parts = text.split("     ", 1)
                    if parts[0].strip().isalpha():
                        display_text = parts[1].strip()
                        
                if self._current_tab_index == 4:
                    self.tab_row_mapping.receive_selection(side, col_idx, display_text)
                else:
                    self.tab_column_mapping.receive_selection(side, col_idx, display_text)

    def _on_grid_col_selected(self, side, col_idx, col_name):
        v_list = self.v_list1 if side == 1 else self.v_list2
        config = self.config1 if side == 1 else self.config2
        
        formatted_text = col_name
        if v_list:
            sheet_name = v_list.active_sheet_name
            actual_col_name = col_name
            has_header = False
            if config.get_has_header(sheet_name):
                has_header = True
                header_row_idx = config.get_header_row(sheet_name) - 1
                if 0 <= header_row_idx < v_list.num_rows:
                    row_data = v_list[header_row_idx]
                    if col_idx < len(row_data.data):
                        actual_col_name = str(row_data.data[col_idx])
            
            letter = ""
            temp_idx = col_idx
            while temp_idx >= 0:
                letter = chr(temp_idx % 26 + 65) + letter
                temp_idx = temp_idx // 26 - 1
                
            c_name = str(actual_col_name).strip()
            if not has_header:
                formatted_text = f"{letter}"
            else:
                formatted_text = f"{letter + '     '} {actual_col_name}"

        display_text = str(actual_col_name).strip() if 'actual_col_name' in locals() else str(col_name).strip()

        if self._current_tab_index == 4:
            self.tab_row_mapping.receive_selection(side, col_idx, display_text)
        elif self._current_tab_index == 5:
            self.tab_column_mapping.receive_selection(side, col_idx, display_text)

    def get_valid_data_bounds(self, side: int, sheet_name: str) -> dict:
        v_list = self.v_list1 if side == 1 else self.v_list2
        config = self.config1 if side == 1 else self.config2
        
        if not v_list: 
            return None
            
        # Find sheet info without changing active state and clearing cache
        target_info = None
        for s in v_list.sheets_info:
            if s["name"] == sheet_name:
                target_info = s
                break
                
        if not target_info:
            return None
            
        target_table = target_info["table"]
        target_num_cols = target_info["num_cols"]
        target_num_rows = target_info["num_rows"]
        
        def get_col_name(n):
            res = ""
            while n >= 0:
                res = chr(n % 26 + 65) + res
                n = n // 26 - 1
            return res
            
        identifiers = [get_col_name(i) for i in range(target_num_cols)]
        values = identifiers.copy()
        
        has_header_flag = config.get_has_header(sheet_name)
        has_headers = [has_header_flag] * len(identifiers)
        header_row_idx = None
        if has_header_flag:
            header_row_idx = max(0, config.get_header_row(sheet_name) - 1)
            if 0 <= header_row_idx < target_num_rows:
                # Fetch just the header row directly from MemoryVirtualList
                r = v_list.get_sheet_row(sheet_name, header_row_idx)
                if r:
                    data_cols = r[-target_num_cols:] if target_num_cols > 0 else []
                    for i in range(min(len(data_cols), len(values))):
                        values[i] = str(data_cols[i])
                    
        ignored_col_indices = self._parse_ignored_cols(config.get_ignore_columns(sheet_name), identifiers)
        is_ignored_flags = [(i in ignored_col_indices) for i in range(len(identifiers))]
        
        columns = list(zip(identifiers, values, has_headers, is_ignored_flags))
        
        data_start_row = max(0, config.get_data_start_row(sheet_name) - 1)
        data_end_row = config.get_data_end_row(sheet_name)
        if data_end_row is not None and data_end_row > 0:
            data_end_row = max(0, data_end_row)
        else:
            data_end_row = target_num_rows
            
        ignored_row_indices = self._parse_ignored_rows(config.get_ignore_rows(sheet_name))
        
        return {
            "columns": columns,
            "header_row": header_row_idx,
            "data_start_row": data_start_row,
            "data_end_row": data_end_row,
            "ignored_rows": ignored_row_indices,
            "total_rows": target_num_rows
        }

    def _fetch_columns_for_mapping(self, sheet1_name, sheet2_name):
        bounds1 = self.get_valid_data_bounds(1, sheet1_name)
        bounds2 = self.get_valid_data_bounds(2, sheet2_name)
        
        cols1 = bounds1["columns"] if bounds1 else []
        cols2 = bounds2["columns"] if bounds2 else []
        
        return cols1, cols2

    def _clear_key_highlights(self):
        # Clear grids
        if hasattr(self, "grid_left"):
            self.grid_left.key_cols.clear()
            self.grid_left.redraw()
        if hasattr(self, "grid_right"):
            self.grid_right.key_cols.clear()
            self.grid_right.redraw()
            
        # Clear trees
        def clear_tree_tags(tree):
            if not hasattr(tree, "get_children"): return
            roots = tree.get_children("")
            if not roots: return
            
            # Find the active (open) sheet and clear its tags, instead of all sheets
            for child in tree.get_children(roots[0]):
                if tree.item(child, "open"):
                    for col_item in tree.get_children(child):
                        tags = list(tree.item(col_item, "tags"))
                        if "key_col" in tags:
                            tags.remove("key_col")
                            tree.item(col_item, tags=tuple(tags))
                    break
        
        if hasattr(self, "tree1"): clear_tree_tags(self.tree1)
        if hasattr(self, "tree2"): clear_tree_tags(self.tree2)

    def _update_key_highlights(self, side: int):
        if side == 0:
            self._update_key_highlights(1)
            self._update_key_highlights(2)
            return
            
        if not hasattr(self, '_current_tab_index'):
            return
            
        if self._current_tab_index == 4:
            col_indices = self.tab_row_mapping.get_current_key_indices(side)
        elif self._current_tab_index == 5:
            col_indices = self.tab_column_mapping.get_current_manual_indices(side)
        elif self._current_tab_index == 6:
            col_indices = self.tab_comparison.get_current_manual_indices(side)
        elif self._current_tab_index == 7:
            col_indices = self.tab_finish.get_current_selected_columns(side)
        else:
            return
            
        grid = self.grid_left if side == 1 else self.grid_right
        tree = self.tree1 if side == 1 else self.tree2
        
        v_list = self.v_list1 if side == 1 else self.v_list2
        config = self.config1 if side == 1 else self.config2
        sheet_name = v_list.active_sheet_name if v_list else None
        
        # 1. Update Grid using key_cols
        grid.selected_cols.clear()
        grid.selected_rows.clear()
        grid.key_cols.clear()
        
        for i in col_indices:
            if 0 <= i < len(grid._headers):
                grid.key_cols.add(i)
                
        if col_indices:
            last_idx = col_indices[-1]
            if 0 <= last_idx < len(grid._headers):
                grid.scroll_to_col(last_idx)
        else:
            if not getattr(grid, '_batch_updating', False):
                grid.redraw()
            
        # 2. Update Tree using tags
        roots = tree.get_children("")
        if not roots: return
        
        active_sheet_item = None
        for child in tree.get_children(roots[0]):
            if tree.item(child, "open"):
                active_sheet_item = child
                break
                
        if active_sheet_item:
            last_item = None
            for i, col_item in enumerate(tree.get_children(active_sheet_item)):
                current_tags = list(tree.item(col_item, "tags"))
                if i in col_indices:
                    if "key_col" not in current_tags:
                        current_tags.append("key_col")
                    last_item = col_item
                else:
                    if "key_col" in current_tags:
                        current_tags.remove("key_col")
                tree.item(col_item, tags=tuple(current_tags))
                    
            if last_item:
                tree.see(last_item)



    def _on_row_mapping_sheet_pair_selected(self, s1_name, s2_name, expand=True):
        """Called when a sheet pair is selected in the Row or Column Mapping tab."""
        def select_sheet(tree, sheet_name):
            roots = tree.get_children("")
            if not roots: return
            
            target = None
            for child in tree.get_children(roots[0]):
                if tree.item(child, "text") == sheet_name:
                    target = child
                    tree.item(child, open=expand)
                else:
                    tree.item(child, open=False)
                    
            if target:
                if tree.selection() != (target,):
                    tree.selection_set(target)
                tree.see(target)
                
            if hasattr(self, '_current_tab_index') and self._current_tab_index in (4, 5):
                allowed = set(roots)
                if target:
                    allowed.add(target)
                    allowed.update(tree.get_children(target))
                tree.set_selectable_items(allowed)
            else:
                tree.unlock_all()

        select_sheet(self.tree1, s1_name)
        select_sheet(self.tree2, s2_name)

    def _update_sheet_mappings(self):
        def get_file_name(tree):
            roots = tree.get_children("")
            if roots:
                return tree.item(roots[0], "text")
            return ""

        file1 = get_file_name(self.tree1)
        file2 = get_file_name(self.tree2)
        
        def get_sheets(tree):
            sheets = []
            roots = tree.get_children("")
            if roots:
                root_id = roots[0]
                children = tree.get_children(root_id)
                if children:
                    for child in children:
                        sheets.append(tree.item(child, "text"))
                else:
                    sheets.append(tree.item(root_id, "text"))
            return sheets

        sheets1 = get_sheets(self.tree1)
        sheets2 = get_sheets(self.tree2)
        
        self.tab_mapping.set_files(file1, file2)
        self.tab_mapping.refresh_data(sheets1, sheets2)

    def _invalidate_keys_for_sheet(self, side, sheet_name):
        if not hasattr(self, 'tab_mapping'): return
        mappings = getattr(self.tab_mapping, '_cached_mappings', [])
        if not mappings: return
        
        needs_refresh = False
        removed_keys = 0
        removed_pairs = 0
        
        config = self.config1 if side == 1 else self.config2
        
        # We parse the currently ignored columns to check for intersections
        ignored_indices = self._parse_ignored_cols(config.get_ignore_columns(sheet_name), [])
        
        for m in mappings:
            target_sheet = m.sheet1_name if side == 1 else m.sheet2_name
            if target_sheet == sheet_name:
                needs_refresh = True
                
                # 1. Automatisches Bereinigen der Schlüssel (Tab 5)
                new_keys = []
                for k in getattr(m, 'key_mappings', []):
                    indices = k.col1_indices if side == 1 else k.col2_indices
                    if any(idx in ignored_indices for idx in indices):
                        removed_keys += 1
                    else:
                        new_keys.append(k)
                m.key_mappings = new_keys
                
                # 2. Automatisches Bereinigen der Spaltenpaare (Tab 6)
                for attr in ['column_mappings', 'cached_manual_mappings']:
                    lists_of_mappings = getattr(m, attr, [])
                    new_cols = []
                    for c in lists_of_mappings:
                        idx = c.col1_idx if side == 1 else c.col2_idx
                        if idx in ignored_indices:
                            removed_pairs += 1
                        else:
                            new_cols.append(c)
                    setattr(m, attr, new_cols)
                    
        if removed_keys > 0 or removed_pairs > 0:
            from tkinter import messagebox
            msg = []
            if removed_keys > 0:
                msg.append(f"{removed_keys} Schlüssel")
            if removed_pairs > 0:
                msg.append(f"{removed_pairs} Spaltenpaar(e)")
                
            messagebox.showinfo(
                "Automatische Anpassung",
                f"Da Sie Spalten ignorieren, wurden {', '.join(msg)} automatisch aus der Konfiguration (Tab 5 / Tab 6) entfernt, da diese nicht mehr gültig waren.",
                parent=self
            )
                    
        if needs_refresh:
            tab_idx = getattr(self, '_current_tab_index', -1)
            if tab_idx == 4 and hasattr(self, 'tab_row_mapping'):
                self.tab_row_mapping._refresh_key_list()
                self._update_key_highlights(1)
                self._update_key_highlights(2)
            elif tab_idx == 5 and hasattr(self, 'tab_column_mapping'):
                self.tab_column_mapping._refresh_col_list()

    def _refresh_tree_and_grid_headers(self, side):
        v_list = self.v_list1 if side == 1 else self.v_list2
        if not v_list: return
        target_grid = self.grid_left if side == 1 else self.grid_right
        target_tree = self.tree1 if side == 1 else self.tree2
        config = self.config1 if side == 1 else self.config2
        pg_struct = self.pg_struct1 if side == 1 else self.pg_struct2
        filename = os.path.basename(v_list.file_path)
        
        sheet_name = v_list.active_sheet_name if hasattr(v_list, 'active_sheet_name') else "default"
        self._invalidate_keys_for_sheet(side, sheet_name)
        
        self._sync_tree_and_grid(v_list, target_grid, target_tree, filename, pg_struct, config, preserve_sheet=True)
        if self._current_tab_index == 2:
            self._refresh_tree_types(side)

    def _sync_tree_and_grid(self, v_list, target_grid, target_tree, filename, pg_struct, config, preserve_sheet=False):
        # Helper function for A, B, C column identifiers
        def get_col_name(n):
            res = ""
            while n >= 0:
                res = chr(n % 26 + 65) + res
                n = n // 26 - 1
            return res
        
        active_sheet_idx = 0
        if preserve_sheet:
            for i, s in enumerate(v_list.sheets_info):
                if s["name"] == v_list.active_sheet_name:
                    active_sheet_idx = i
                    break
                    
        # Feed the grid with the active sheet
        side = 1 if target_grid == self.grid_left else 2
        old_sheet = getattr(v_list, 'active_sheet_name', None)
        if old_sheet:
            self._save_grid_scroll(side, target_grid, old_sheet)
            
        v_list.set_active_sheet(active_sheet_idx)
        
        num_cols = v_list.num_cols
        standard_headers = [get_col_name(i) for i in range(num_cols)]
        
        target_grid.set_data(v_list, standard_headers)
        target_grid.set_header_row(config.get_header_row(v_list.active_sheet_name) - 1 if config.get_has_header(v_list.active_sheet_name) else None)
        target_grid.set_data_bounds(config.get_data_start_row(v_list.active_sheet_name) - 1, config.get_data_end_row(v_list.active_sheet_name))
        target_grid.set_ignored_rows(self._parse_ignored_rows(config.get_ignore_rows(v_list.active_sheet_name)))
        target_grid.set_ignored_cols(self._parse_ignored_cols(config.get_ignore_columns(v_list.active_sheet_name), standard_headers))
        
        self._restore_grid_scroll(side, target_grid, getattr(v_list, 'active_sheet_name', None))
            
        def validate_cell(col_idx, val):
            if col_idx not in target_grid.column_types:
                return True
            expected_type = target_grid.column_types[col_idx]
            if expected_type == "Text":
                return True
                
            val_str = str(val).strip().lower()
            if not val_str:
                return True
            
            na_values = [v.strip().lower() for v in config.na_values.split(',')]
            if val_str in na_values:
                return True
                
            if expected_type == "Zahl":
                import re
                pat = re.compile(r'^-?(?:\d{1,3}(?:[.,\s]\d{3})*|\d+)(?:[.,]\d+)?$')
                return bool(pat.match(str(val).strip()))
            elif expected_type == "Boolean":
                true_vals = [v.strip().lower() for v in config.true_values.split(',')]
                false_vals = [v.strip().lower() for v in config.false_values.split(',')]
                return val_str in true_vals or val_str in false_vals
            elif expected_type.startswith("Datum"):
                if hasattr(target_grid, 'column_date_formats') and col_idx in target_grid.column_date_formats:
                    fmt = target_grid.column_date_formats[col_idx]
                    if fmt:
                        import warnings
                        from datetime import datetime
                        import locale
                        try:
                            with warnings.catch_warnings():
                                warnings.simplefilter("ignore", category=DeprecationWarning)
                                datetime.strptime(str(val).strip(), fmt)
                            return True
                        except ValueError:
                            # Fallback für AM/PM in deutschen Locales
                            if "%p" in fmt or "%I" in fmt:
                                try:
                                    old_loc = locale.setlocale(locale.LC_TIME)
                                    try:
                                        locale.setlocale(locale.LC_TIME, 'C')
                                        with warnings.catch_warnings():
                                            warnings.simplefilter("ignore", category=DeprecationWarning)
                                            datetime.strptime(str(val).strip(), fmt)
                                        return True
                                    finally:
                                        locale.setlocale(locale.LC_TIME, old_loc)
                                except Exception:
                                    pass
                            return False
                return False
            return True
            
        target_grid.validation_callback = validate_cell
        target_grid.redraw()
        
        # Populate tree structure
        root_node = DataNode(filename=filename)
        root_node.styled = True
        
        for sheet_info in v_list.sheets_info:
            sheet_name = sheet_info["name"]
            sheet_node = DataNode(sheetname=sheet_name, parent=root_node)
            sheet_node.styled = True
            root_node.children.append(sheet_node)
            
            # Add columns to the sheet
            sheet_num_cols = sheet_info["num_cols"]
            
            has_header_flag = False
            if config.get_has_header(sheet_name):
                has_header_flag = True
                header_row_idx = config.get_header_row(sheet_name) - 1
                v_list.set_active_sheet(sheet_name)
                if 0 <= header_row_idx < v_list.num_rows:
                    row_data = v_list[header_row_idx]
                    col_names = [str(row_data[i]) for i in range(sheet_num_cols)]
                else:
                    col_names = [get_col_name(i) for i in range(sheet_num_cols)]
            else:
                col_names = [get_col_name(i) for i in range(sheet_num_cols)]
                
            ignored_str = config.get_ignore_columns(sheet_name)
            cols_set = self._parse_ignored_cols(ignored_str, col_names)
                
            for i in range(sheet_num_cols):
                col_title = col_names[i]
                col_node = DataNode(col=col_title, parent=sheet_node, has_header=has_header_flag)
                col_node.styled = True
                if i in cols_set:
                    col_node.is_ignored = True
                sheet_node.children.append(col_node)
                
        # Restore active sheet
        v_list.set_active_sheet(active_sheet_idx)
        
        # Wire the Model to the View!
        view_model = SingleFileViewModel(root_node)
        target_tree.sync_with_model(view_model.root_node)
        
        # Select the active sheet if preserved, else root
        target_item = ""
        roots = target_tree.get_children("")
        if roots:
            target_item = roots[0]
            if preserve_sheet:
                for child in target_tree.get_children(roots[0]):
                    if target_tree.item(child, "text") == v_list.active_sheet_name:
                        target_item = child
                        break
            
            target_tree.selection_set(target_item)
            target_tree.see(target_item)
        
        if len(v_list.sheets_info) <= 1:
            self._update_nav_button_text(pg_struct, "Done")
        else:
            self._update_nav_button_text(pg_struct, "Next Sheet")
        
        # Update mappings whenever new file is loaded
        self._update_sheet_mappings()

    def _reload_file_with_config(self, side):
        v_list = self.v_list1 if side == 1 else self.v_list2
        if not v_list: return
        
        path = v_list.file_path
        if not os.path.exists(path): return
        
        target_grid = self.grid_left if side == 1 else self.grid_right
        target_tree = self.tree1 if side == 1 else self.tree2
        config = self.config1 if side == 1 else self.config2
        pg_struct = self.pg_struct1 if side == 1 else self.pg_struct2
        pg_import = self.pg_import1 if side == 1 else self.pg_import2
        filename = os.path.basename(path)
        
        try:
            self.config(cursor="watch")
            self.update_idletasks()
            
            v_list.close()
            new_v_list = MemoryVirtualList(path, db_path="", config=config)
            if side == 1:
                self.v_list1 = new_v_list
            else:
                self.v_list2 = new_v_list
                
            self._populate_import_grid(pg_import, config, f"Datei {side}")
            self._sync_tree_and_grid(new_v_list, target_grid, target_tree, filename, pg_struct, config)
            self.config(cursor="")
        except Exception as e:
            self.config(cursor="")
            import traceback
            traceback.print_exc()
            messagebox.showerror("Error", f"Error reloading file:\n{str(e)}")

    def cmd_load_file(self, side):
        """
        End-to-End wiring for CSV, XLSX and ODS files.
        """
        target_grid = self.grid_left if side == 1 else self.grid_right
        target_tree = self.tree1 if side == 1 else self.tree2
        config = self.config1 if side == 1 else self.config2
        pg_import = self.pg_import1 if side == 1 else self.pg_import2
        pg_struct = self.pg_struct1 if side == 1 else self.pg_struct2
        
        filetypes = [
            ("All Supported Files", "*.csv;*.xlsx;*.ods"),
            ("CSV Files", "*.csv"),
            ("Excel Files", "*.xlsx"),
            ("ODF Files", "*.ods"),
            ("All Files", "*.*")
        ]
        
        dlg_title = "Soll-Datei (TARGET) auswählen..." if side == 1 else "Ist-Datei (ACTUAL) auswählen..."
        path = filedialog.askopenfilename(title=dlg_title, filetypes=filetypes)
        if not path: return
        
        try:

            self.config(cursor="watch")
            self.update_idletasks()
            
            # 1. Compute Hash
            import hashlib
            with open(path, 'rb') as f:
                # hashlib.file_digest is the official C-optimized standard in Python 3.11+
                computed_hash = hashlib.file_digest(f, "sha256").hexdigest()
            
            # Reset properties to default for the new file, keeping global metadata
            from file_parsing_config_t import FileParsingConfig
            new_config = FileParsingConfig()
            new_config.user_name = config.user_name
            new_config.project_id = config.project_id
            new_config.description = getattr(config, 'description', "")
            new_config.admin_mode = getattr(config, 'admin_mode', False)
            new_config.file_hash = computed_hash
            new_config.color_true = getattr(config, 'color_true', new_config.color_true)
            new_config.color_false = getattr(config, 'color_false', new_config.color_false)
            new_config.color_not_comp = getattr(config, 'color_not_comp', new_config.color_not_comp)
            new_config.color_count_diff = getattr(config, 'color_count_diff', new_config.color_count_diff)
            
            if side == 1:
                self.config1 = new_config
                config = self.config1
            else:
                self.config2 = new_config
                config = self.config2

            # Reset specific properties to Auto to trigger auto-detection
            config.encoding = "Auto"
            config.delimiter = "Auto"
            config.file_type = "Auto"
            
            ext = os.path.splitext(path)[1].lower()
            if ext == '.csv':
                config.file_type = "CSV"
            elif ext in ['.xlsx', '.ods']:
                config.file_type = "Excel"
            
            # Create Virtual List (RAM)
            v_list = MemoryVirtualList(path, db_path="", config=config)
            if side == 1:
                self.v_list1 = v_list
            else:
                self.v_list2 = v_list
            
            # Sync Config with detected values (if any were modified by SqliteVirtualList)
            self._populate_import_grid(pg_import, config, f"Datei {side}")
            
            filename = os.path.basename(path)
            self._sync_tree_and_grid(v_list, target_grid, target_tree, filename, pg_struct, config)
            
            # Sofort die Struktur-Einstellungen im PropertyGrid aktualisieren und zu Tab 1 wechseln
            if side == 1:
                self._populate_structure_grid(pg_struct, config, "Datei 1", active_sheet=v_list.active_sheet_name)
            else:
                self._populate_structure_grid(pg_struct, config, "Datei 2", active_sheet=v_list.active_sheet_name)
            
            self._select_tab(0)
           
            self.config(cursor="")
            self.title(f"Dual-Grid Comparison - Last File: {filename}")
            
            # Show warning if formulas were found
            if getattr(v_list, 'has_uncalculated_formulas', False):
                messagebox.showwarning(
                    "Unberechnete Formeln erkannt (GxP Warnung)",
                    f"In der Datei '{filename}' wurden unberechnete Formeln erkannt.\n\n"
                    "Da diese Formeln nicht durch die Ursprungsanwendung zu festen Werten berechnet wurden, werden sie zur Wahrung der Datenintegrität 1:1 als Text (z.B. '=SUM(A1:B1)') angezeigt.\n\n"
                    "Falls Sie stattdessen die berechneten Werte auditieren möchten, öffnen Sie die Datei kurz mit Ihrer Standardanwendung (Excel/Calc) und speichern Sie diese."
                )
            
        except Exception as e:
            self.config(cursor="")
            messagebox.showerror("Error", f"Error loading file:\n{str(e)}")

    def _load_initial_dummy_data(self):
        """Populate initial UI state just like the previous main block."""
        # --- Insert dummy data into the trees ---
        root_d1 = DataNode(filename="ist_data_COMPLETE.csv")
        root_d1.styled = True
        sheet_a1 = DataNode(sheetname="Production_Data", parent=root_d1)
        sheet_a1.styled = True
        sheet_b1 = DataNode(sheetname="Quality_Metrics", parent=root_d1)
        sheet_c1 = DataNode(sheetname="Metadata_Log", parent=root_d1)
        root_d1.children = [sheet_a1, sheet_b1, sheet_c1]
        
        view_model_1 = SingleFileViewModel(root_d1)
        self.tree1.sync_with_model(view_model_1.root_node)

        root_d2 = DataNode(filename="soll_data_COMPLETE.csv")
        root_d2.styled = True
        sheet_a2 = DataNode(sheetname="Production_Data", parent=root_d2)
        sheet_a2.styled = True
        sheet_b2 = DataNode(sheetname="Quality_Metrics", parent=root_d2)
        sheet_c2 = DataNode(sheetname="Metadata_Log", parent=root_d2)
        root_d2.children = [sheet_a2, sheet_b2, sheet_c2]
        
        view_model_2 = SingleFileViewModel(root_d2)
        self.tree2.sync_with_model(view_model_2.root_node)

        # Initial Data for Grids
        dummy_cols = ["ID", "Parameter", "Soll-Wert"]
        dummy_data = [[f"P-{i:03d}", f"Test-Param {i}", f"{100+i}.0"] for i in range(100)]
        
        self.update_idletasks()
        self.grid_left.set_data(dummy_data, dummy_cols)
        self.grid_right.set_data(dummy_data, dummy_cols)
        
        self._update_sheet_mappings()

    def _ask_password_choice(self):
        dialog = tk.Toplevel(self)
        dialog.title("Passwortschutz")
        dialog.geometry("450x160")
        dialog.resizable(True, True)
        dialog.minsize(400, 150)
        dialog.transient(self)
        
        dialog.update_idletasks()
        x = self.winfo_rootx() + (self.winfo_width() // 2) - (450 // 2)
        y = self.winfo_rooty() + (self.winfo_height() // 2) - (160 // 2)
        dialog.geometry(f"+{x}+{y}")
        
        result = [None]
        def set_result(val):
            result[0] = val
            dialog.destroy()
            
        frame = ttk.Frame(dialog, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)
        
        lbl = ttk.Label(
            frame, 
            text="Möchten Sie die Datei mit einem Passwort schützen?", 
            font=("Segoe UI", 11, "bold")
        )
        lbl.pack(pady=(0, 20))
        
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X)
        
        btn_yes = ttk.Button(btn_frame, text="Mit Passwort", command=lambda: set_result(True))
        btn_yes.pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)
        
        btn_no = ttk.Button(btn_frame, text="Ohne Passwort", command=lambda: set_result(False))
        btn_no.pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)
        
        btn_cancel = ttk.Button(btn_frame, text="Abbrechen", command=lambda: set_result(None))
        btn_cancel.pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)
        
        dialog.protocol("WM_DELETE_WINDOW", lambda: set_result(None))
        dialog.grab_set()
        dialog.focus_set()
        self.wait_window(dialog)
        return result[0]

    def _ask_password_input(self, title, prompt):
        dialog = tk.Toplevel(self)
        dialog.title(title)
        dialog.geometry("400x180")
        dialog.resizable(True, True)
        dialog.minsize(350, 160)
        dialog.transient(self)
        
        dialog.update_idletasks()
        x = self.winfo_rootx() + (self.winfo_width() // 2) - (400 // 2)
        y = self.winfo_rooty() + (self.winfo_height() // 2) - (180 // 2)
        dialog.geometry(f"+{x}+{y}")
        
        result = [None]
        def on_ok(event=None):
            result[0] = entry.get()
            dialog.destroy()
            
        def on_cancel(event=None):
            dialog.destroy()
            
        frame = ttk.Frame(dialog, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)
        
        lbl = ttk.Label(frame, text=prompt, font=("Segoe UI", 10))
        lbl.pack(anchor="w", pady=(0, 10))
        
        entry = ttk.Entry(frame, show="*", font=("Segoe UI", 10))
        entry.pack(fill=tk.X, pady=(0, 15))
        entry.bind("<Return>", on_ok)
        entry.bind("<Escape>", on_cancel)
        
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X)
        
        btn_ok = ttk.Button(btn_frame, text="OK", width=10, command=on_ok)
        btn_ok.pack(side=tk.RIGHT, padx=(5, 0))
        
        btn_cancel = ttk.Button(btn_frame, text="Abbrechen", width=10, command=on_cancel)
        btn_cancel.pack(side=tk.RIGHT)
        
        dialog.protocol("WM_DELETE_WINDOW", on_cancel)
        entry.focus_set()
        dialog.grab_set()
        self.wait_window(dialog)
        return result[0]

    def _ask_empty_password_action(self):
        dialog = tk.Toplevel(self)
        dialog.title("Kein Passwort")
        dialog.geometry("450x160")
        dialog.resizable(True, True)
        dialog.minsize(400, 150)
        dialog.transient(self)
        
        dialog.update_idletasks()
        x = self.winfo_rootx() + (self.winfo_width() // 2) - (450 // 2)
        y = self.winfo_rooty() + (self.winfo_height() // 2) - (160 // 2)
        dialog.geometry(f"+{x}+{y}")
        
        result = [None]
        def set_result(val):
            result[0] = val
            dialog.destroy()
            
        frame = ttk.Frame(dialog, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)
        
        lbl = ttk.Label(frame, text="Sie haben kein Passwort eingegeben.", font=("Segoe UI", 10, "bold"))
        lbl.pack(pady=(0, 15))
        
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X)
        
        btn_without = ttk.Button(btn_frame, text="Ohne Passwort speichern", command=lambda: set_result("ohne"))
        btn_without.pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)
        
        btn_retry = ttk.Button(btn_frame, text="Passwort eingeben", command=lambda: set_result("retry"))
        btn_retry.pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)
        
        dialog.protocol("WM_DELETE_WINDOW", lambda: set_result("cancel"))
        dialog.grab_set()
        dialog.focus_set()
        self.wait_window(dialog)
        return result[0]

    def cmd_save_settings(self):
        filepath = filedialog.asksaveasfilename(
            title="Einstellungen speichern",
            defaultextension=".json",
            filetypes=[("JSON", "*.json")]
        )
        if not filepath:
            return

        pwd_choice = self._ask_password_choice()
        
        if pwd_choice is None:
            return
            
        password = None
        if pwd_choice:
            while True:
                password = self._ask_password_input("Passwort", "Bitte geben Sie ein Passwort für die Signatur ein:")
                if password is None:
                    return
                if password == "":
                    action = self._ask_empty_password_action()
                    if action == "ohne":
                        password = None
                        break
                    elif action == "retry":
                        continue
                    else:
                        return
                else:
                    break

        def extract_config(cfg):
            return {
                "decimal_separator": cfg.decimal_separator,
                "thousands_separator": cfg.thousands_separator,
                "date_format": cfg.date_format,
                "custom_date_format": cfg.custom_date_format,
                "timezone": cfg.timezone,
                "rounding_decimal_places": cfg.rounding_decimal_places,
                "rounding_method": cfg.rounding_method,
                "trim_whitespace": cfg.trim_whitespace,
                "normalize_umlauts": cfg.normalize_umlauts,
                "case_insensitive": cfg.case_insensitive,
                "na_values": cfg.na_values,
                "true_values": cfg.true_values,
                "false_values": cfg.false_values,
                "color_true": cfg.color_true,
                "color_false": cfg.color_false,
                "color_not_comp": cfg.color_not_comp,
                "color_count_diff": cfg.color_count_diff
            }

        try:
            mappings_data = []
            if hasattr(self, 'tab_column_mapping') and hasattr(self.tab_column_mapping, 'sheet_mappings'):
                for sm in self.tab_column_mapping.sheet_mappings:
                    keys = []
                    for km in sm.key_mappings:
                        keys.append({
                            "col1_indices": km.col1_indices,
                            "col2_indices": km.col2_indices
                        })
                    
                    cols = []
                    for cm in sm.column_mappings:
                        cols.append({
                            "col1_idx": cm.col1_idx,
                            "col2_idx": cm.col2_idx,
                            "rule": {
                                "check_equivalent": cm.rule.check_equivalent,
                                "check_greater": cm.rule.check_greater,
                                "check_less": cm.rule.check_less,
                                "check_tolerance": cm.rule.check_tolerance,
                                "tolerance_value": cm.rule.tolerance_value
                            }
                        })
                    
                    mappings_data.append({
                        "sheet1_name": sm.sheet1_name,
                        "sheet2_name": sm.sheet2_name,
                        "row_matching_mode": sm.row_matching_mode,
                        "column_matching_mode": sm.column_matching_mode,
                        "keys": keys,
                        "columns": cols
                    })

            save_data = {
                "general": {
                    "user_name": self.config1.user_name,
                    "project_id": self.config1.project_id
                },
                "tab4_mode": getattr(self.tab_mapping, 'current_mode', 'ModeManual') if hasattr(self, 'tab_mapping') else 'ModeManual',
                "config1": extract_config(self.config1),
                "config2": extract_config(self.config2),
                "mappings": mappings_data
            }

            final_data = save_data
            if password:
                payload_str = json.dumps(save_data, sort_keys=True)
                signature = hmac.new(password.encode('utf-8'), payload_str.encode('utf-8'), hashlib.sha256).hexdigest()
                pwd_hash = hashlib.sha256(password.encode('utf-8')).hexdigest()
                final_data = {
                    "_signature": signature,
                    "_pwd_hash": pwd_hash,
                    "payload": save_data
                }

            # Make writable if it exists and is read-only
            if os.path.exists(filepath):
                os.chmod(filepath, stat.S_IWRITE)

            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(final_data, f, indent=4)
            
            # Make read-only
            os.chmod(filepath, stat.S_IREAD)
                
            messagebox.showinfo("Erfolg", "Einstellungen wurden erfolgreich gespeichert (schreibgeschützt).")
        except Exception as e:
            messagebox.showerror("Fehler", f"Fehler beim Speichern der Einstellungen:\n{str(e)}")

    def cmd_load_settings(self):
        filepath = filedialog.askopenfilename(
            title="Einstellungen laden",
            defaultextension=".json",
            filetypes=[("JSON Einstellungen", "*.json")]
        )
        if not filepath:
            return

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                raw_data = json.load(f)

            if isinstance(raw_data, dict) and "_signature" in raw_data and "payload" in raw_data:
                while True:
                    password = self._ask_password_input("Passwort", "Diese Datei ist signiert.\nBitte Passwort eingeben:")
                    if password is None:
                        return # Abbrechen geklickt
                    if password == "":
                        messagebox.showwarning("Hinweis", "Bitte geben Sie ein Passwort ein.")
                        continue
                    
                    # 1. Signatur der Payload berechnen
                    payload_str = json.dumps(raw_data["payload"], sort_keys=True)
                    expected_sig = hmac.new(password.encode('utf-8'), payload_str.encode('utf-8'), hashlib.sha256).hexdigest()
                    sig_match = hmac.compare_digest(expected_sig, raw_data["_signature"])
                    
                    # 2. Passwort-Hash prüfen
                    hash_match = True
                    if "_pwd_hash" in raw_data:
                        pwd_hash = hashlib.sha256(password.encode('utf-8')).hexdigest()
                        hash_match = (pwd_hash == raw_data["_pwd_hash"])
                        
                    # Auswertung der Kombinationen:
                    if hash_match and sig_match:
                        break # Alles korrekt!
                        
                    if (not hash_match and sig_match) or (hash_match and not sig_match):
                        # Eine Manipulation wurde eindeutig nachgewiesen
                        messagebox.showerror(
                            "Fehler", 
                            "Die Datei wurde verändert\nund kann nicht geladen werden"
                        )
                        return
                        
                    # Weder Hash noch Signatur stimmen. Wahrscheinlich falsches Passwort.
                    messagebox.showerror("Fehler", "Falsches Passwort")
                    continue
                
                data = raw_data["payload"]
            else:
                data = raw_data

            # 1. General
            gen = data.get("general", {})
            self.config1.user_name = gen.get("user_name", self.config1.user_name)
            self.config1.project_id = gen.get("project_id", self.config1.project_id)
            
            # 2. Configs
            def apply_config(cfg, data_dict):
                if not data_dict: return
                for k, v in data_dict.items():
                    if hasattr(cfg, k):
                        setattr(cfg, k, v)
                        
            apply_config(self.config1, data.get("config1", {}))
            apply_config(self.config2, data.get("config2", {}))

            # Helper for name resolving
            def get_col_name(side, sheet_name, col_idx):
                if not hasattr(self, 'get_valid_data_bounds'): return f"Spalte {col_idx + 1}"
                bounds = self.get_valid_data_bounds(side, sheet_name)
                if bounds and "columns" in bounds:
                    cols = bounds["columns"]
                    if 0 <= col_idx < len(cols):
                        ident, val, has_hdr, is_ign = cols[col_idx]
                        return val if val else ident
                return f"Spalte {col_idx + 1}"

            # 3. Mappings
            mappings_data = data.get("mappings", [])
            from mapping_models import SheetMapping, KeyMapping, ColumnMapping, ComparisonRule
            
            new_mappings = []
            manual_pairs = []
            
            for md in mappings_data:
                sm = SheetMapping(
                    sheet1_name=md.get("sheet1_name", ""),
                    sheet2_name=md.get("sheet2_name", "")
                )
                sm.row_matching_mode = md.get("row_matching_mode", "positional")
                sm.column_matching_mode = md.get("column_matching_mode", "positional")
                
                for kd in md.get("keys", []):
                    km = KeyMapping(
                        col1_names=", ".join([get_col_name(1, sm.sheet1_name, idx) for idx in kd.get("col1_indices", [])]),
                        col2_names=", ".join([get_col_name(2, sm.sheet2_name, idx) for idx in kd.get("col2_indices", [])]),
                    )
                    km.col1_indices = kd.get("col1_indices", [])
                    km.col2_indices = kd.get("col2_indices", [])
                    sm.key_mappings.append(km)
                    
                for cd in md.get("columns", []):
                    cm = ColumnMapping(
                        col1_name=get_col_name(1, sm.sheet1_name, cd.get("col1_idx", -1)),
                        col2_name=get_col_name(2, sm.sheet2_name, cd.get("col2_idx", -1)),
                        col1_idx=cd.get("col1_idx", -1),
                        col2_idx=cd.get("col2_idx", -1)
                    )
                    rd = cd.get("rule", {})
                    cm.rule = ComparisonRule(
                        check_equivalent=rd.get("check_equivalent", True),
                        check_greater=rd.get("check_greater", False),
                        check_less=rd.get("check_less", False),
                        check_tolerance=rd.get("check_tolerance", False),
                        tolerance_value=rd.get("tolerance_value", 0.0)
                    )
                    sm.column_mappings.append(cm)
                    
                new_mappings.append(sm)
                manual_pairs.append((sm.sheet1_name, sm.sheet2_name))

            if new_mappings:
                if hasattr(self, 'tab_mapping'):
                    tab4_mode = data.get("tab4_mode", "ModeManual")
                    self.tab_mapping._cached_mappings = new_mappings
                    self.tab_mapping.current_mode = tab4_mode
                    
                    if tab4_mode == "ModeManual":
                        self.tab_mapping.manual_mappings = manual_pairs
                    else:
                        self.tab_mapping.manual_mappings = []
                        
                    if hasattr(self.tab_mapping, '_populate_options'):
                        self.tab_mapping._populate_options()
                    if hasattr(self.tab_mapping, '_generate_mappings'):
                        self.tab_mapping._generate_mappings()
                        
                    # Propagate down manually as well
                    if hasattr(self, 'tab_row_mapping') and hasattr(self.tab_row_mapping, 'refresh_data'):
                        self.tab_row_mapping.refresh_data(new_mappings, ui_update=(self._current_tab_index == 4))
                    if hasattr(self, 'tab_column_mapping') and hasattr(self.tab_column_mapping, 'load_mappings'):
                        self.tab_column_mapping.load_mappings(new_mappings, ui_update=(self._current_tab_index == 5))
                    if hasattr(self, 'tab_comparison') and hasattr(self.tab_comparison, 'load_mappings'):
                        self.tab_comparison.load_mappings(new_mappings)
                    
            # Refresh property grids (Tab 1, Tab 2)
            if hasattr(self, '_populate_settings_grids'):
                self._populate_settings_grids()
            
            messagebox.showinfo("Erfolg", "Einstellungen wurden erfolgreich geladen.")
            
        except Exception as e:
            messagebox.showerror("Fehler", f"Fehler beim Laden der Einstellungen:\n{str(e)}")

if __name__ == "__main__":
    app = Application()
    app.mainloop()
