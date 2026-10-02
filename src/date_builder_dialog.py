import tkinter as tk
from tkinter import ttk, messagebox
from ui_components import ZoomManager
import re

def guess_date_format(sample_string: str):
    """
    Returns (machine_fmt, display_fmt) based on simple heuristics.
    """
    if not sample_string:
        return "", ""
        
    tokens = re.split(r'(\D+)', sample_string.strip())
    tokens = [t for t in tokens if t]
    
    options = {
        "Tag": "%d", "Mon": "%m", "Jahr": "%Y",
        "Std": "%H", "Min": "%M", "Sek": "%S", "ms": "%f"
    }
    display_map = {
        "%d": "TT", "%m": "MM", "%Y": "YYYY", "%y": "YY",
        "%H": "hh", "%M": "mm", "%S": "ss", "%f": "ms", "%p": "AM/PM", "%I": "hh(12)"
    }
    
    machine_fmt = ""
    display_fmt = ""
    
    used_choices = set()
    col = 0
    for t in tokens:
        if t.isdigit():
            choice = ""
            if len(t) == 4: choice = "Jahr"
            elif len(t) == 3:
                if col >= 6: choice = "ms"
            elif len(t) <= 2:
                if ":" in sample_string and not any(s in sample_string for s in ['-', '.', '/']):
                    if col == 0: choice = "Std"
                    elif col == 2: choice = "Min"
                    elif col == 4: choice = "Sek"
                else:
                    if col == 0: choice = "Tag"
                    elif col == 2: choice = "Mon"
                    elif col == 4: 
                        choice = "Tag" if "Jahr" in used_choices else "Jahr"
                    elif col == 6: choice = "Std"
                    elif col == 8: choice = "Min"
                    elif col == 10: choice = "Sek"
                    
                    # Heuristic to fix US date format vs EU format
                    if choice in ("Tag", "Mon"):
                        digit_tokens = [tok for tok in tokens if tok.isdigit() and len(tok) <= 2]
                        if len(digit_tokens) >= 2:
                            first_val = int(digit_tokens[0])
                            second_val = int(digit_tokens[1])
                            if first_val <= 12 and second_val > 12:
                                # First is Month, Second is Day (e.g. 01/15/2025)
                                if t == digit_tokens[0]: choice = "Mon"
                                elif t == digit_tokens[1]: choice = "Tag"
                
            if choice == "Jahr":
                code = "%Y" if len(t) == 4 else "%y"
                machine_fmt += code
                display_fmt += display_map[code]
                used_choices.add("Jahr")
            else:
                code = options.get(choice, "")
                if code:
                    machine_fmt += code
                    display_fmt += display_map.get(code, code)
                    used_choices.add(choice)
                else:
                    machine_fmt += t
                    display_fmt += t
            col += 1
        else:
            if t.strip().lower() in ['am', 'pm']:
                machine_fmt += t.replace(t.strip(), "%p")
                display_fmt += t.replace(t.strip(), "AM/PM")
            else:
                machine_fmt += t
                display_fmt += t
            col += 1
            
    if "%p" in machine_fmt and "%H" in machine_fmt:
        machine_fmt = machine_fmt.replace("%H", "%I")
        display_fmt = display_fmt.replace("hh", "hh(12)")

    return machine_fmt, display_fmt

class DateBuilderDialog(tk.Toplevel):
    def __init__(self, parent, sample_string: str):
        super().__init__(parent)
        self.title("Datumsformat definieren")
        self.minsize(900, 350)
        self.transient(parent)
        self.grab_set()
        
        self.result_format = None
        
        self._center_window(parent)
        self._build_ui(sample_string)
        
        self.zoom_manager = ZoomManager(self, zoom_id="dialog_date_builder")
        
    def _center_window(self, parent):
        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")
        
    def _build_ui(self, sample_string: str):
        app = self.master
        while app and not hasattr(app, "current_theme"):
            app = app.master
            
        is_dark = getattr(app, "current_theme", "light") == "dark"
        
        try:
            import ctypes
            self.update_idletasks()
            hwnd = ctypes.windll.user32.GetParent(self.winfo_id())
            rendering_policy = ctypes.c_int(1 if is_dark else 0)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(rendering_policy), ctypes.sizeof(rendering_policy))
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 19, ctypes.byref(rendering_policy), ctypes.sizeof(rendering_policy))
        except Exception:
            pass
            
        main_frame = tk.Frame(self, padx=20, pady=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        lbl_info = tk.Label(main_frame, text="Die App benötigt Hilfe beim Erkennen des Datumsformats.", font=("Segoe UI", 11, "bold"))
        lbl_info.pack(anchor="w", pady=(0, 5))
        
        lbl_desc = tk.Label(main_frame, text="Beispiel-Wert aus der ausgewählten Spalte:", font=("Segoe UI", 10))
        lbl_desc.pack(anchor="w")
        
        lbl_sample = tk.Label(main_frame, text=sample_string if sample_string else "<Leer>", font=("Consolas", 12, "bold"), foreground="#0b57d0")
        lbl_sample.pack(anchor="w", pady=(5, 20))
        
        tokens = re.split(r'(\D+)', sample_string.strip())
        tokens = [t for t in tokens if t]
        
        builder_frame = tk.Frame(main_frame)
        builder_frame.pack(fill=tk.X, expand=False, pady=10)
        
        self.options = ["", "Tag", "Mon", "Jahr", "Std", "Min", "Sek", "ms"]
        
        self.cb_vars = [tk.StringVar() for _ in range(7)]
        self.cb_vals = ["" for _ in range(7)]  
        self.sep_vars = [tk.StringVar() for _ in range(6)] # Only 6 separators between the 7 comboboxes
        
        used_choices = set()
        cb_idx = 0
        for t in tokens:
            if t.isdigit():
                if cb_idx < 7:
                    self.cb_vals[cb_idx] = t
                    choice = ""
                    if len(t) == 4: choice = "Jahr"
                    elif len(t) == 3:
                        if cb_idx >= 5: choice = "ms"
                    elif len(t) <= 2:
                        if ":" in sample_string and not any(s in sample_string for s in ['-', '.', '/']):
                            if cb_idx == 0: choice = "Std"
                            elif cb_idx == 1: choice = "Min"
                            elif cb_idx == 2: choice = "Sek"
                            elif cb_idx == 3: choice = "ms"
                        else:
                            if cb_idx == 0: choice = "Tag"
                            elif cb_idx == 1: choice = "Mon"
                            elif cb_idx == 2: 
                                choice = "Tag" if "Jahr" in used_choices else "Jahr"
                            elif cb_idx == 3: choice = "Std"
                            elif cb_idx == 4: choice = "Min"
                            elif cb_idx == 5: choice = "Sek"
                            elif cb_idx == 6: choice = "ms"
                        
                    self.cb_vars[cb_idx].set(choice)
                    if choice: used_choices.add(choice)
                    cb_idx += 1
            else:
                if 0 < cb_idx <= 6:
                    self.sep_vars[cb_idx - 1].set(self.sep_vars[cb_idx - 1].get() + t)
                    
        for var in self.cb_vars + self.sep_vars:
            var.trace_add('write', self._update_preview)
            
        col = 1
        for i in range(7):
            cb = ttk.Combobox(builder_frame, textvariable=self.cb_vars[i], values=self.options, state="readonly", width=7)
            cb.grid(row=0, column=col, padx=1, pady=5)
            if self.cb_vals[i]:
                lbl = tk.Label(builder_frame, text=self.cb_vals[i], font=("Consolas", 9, "bold"), foreground="#777")
                lbl.grid(row=1, column=col)
            col += 1
            
            if i < 6:
                tk.Entry(builder_frame, textvariable=self.sep_vars[i], width=5).grid(row=0, column=col, padx=1)
                col += 1
                
        preview_frame = tk.Frame(main_frame)
        preview_frame.pack(fill=tk.X, pady=20)
        
        tk.Label(preview_frame, text="Generiertes Format:", font=("Segoe UI", 10, "bold")).pack(side=tk.LEFT)
        self.lbl_preview = tk.Label(preview_frame, text="", font=("Consolas", 11), foreground="#0f9d58")
        self.lbl_preview.pack(side=tk.LEFT, padx=10)
        
        self._update_preview()
        
        btn_frame = tk.Frame(self, padx=20, pady=15)
        btn_frame.pack(fill=tk.X, side=tk.BOTTOM)
        
        btn_ok = tk.Button(btn_frame, text="OK", command=self._on_ok, width=12)
        btn_ok.pack(side=tk.RIGHT, padx=(10, 0))
        btn_cancel = tk.Button(btn_frame, text="Abbrechen", command=self.destroy, width=12)
        btn_cancel.pack(side=tk.RIGHT)
        
        if app and hasattr(app, "_apply_colors"):
            app._apply_colors(self)
            
        if is_dark:
            btn_ok.config(bg="#0b57d0", fg="#ffffff", activebackground="#005c94", relief="flat")
            btn_cancel.config(bg="#3c4043", fg="#ffffff", activebackground="#5f6368", relief="flat")

    def _build_format_strings(self):
        machine_fmt = ""
        display_fmt = ""
        
        display_map = {
            "%d": "TT", "%m": "MM", "%Y": "YYYY", "%y": "YY",
            "%H": "hh", "%M": "mm", "%S": "ss", "%f": "ms", "%p": "AM/PM", "%I": "hh(12)"
        }
        
        options_map = {
            "Tag": "%d", "Mon": "%m", "Std": "%H",
            "Min": "%M", "Sek": "%S", "ms": "%f"
        }
        
        for i in range(7):
            choice = self.cb_vars[i].get()
            val = self.cb_vals[i]
            
            if choice == "Jahr":
                code = "%Y" if len(val) == 4 else "%y"
                machine_fmt += code
                display_fmt += display_map[code]
            elif choice in options_map:
                code = options_map[choice]
                machine_fmt += code
                display_fmt += display_map[code]
                
            if i < 6:
                sep = self.sep_vars[i].get()
                sep_mach = re.sub(r'(?i)\b(am|pm)\b', '%p', sep)
                sep_disp = re.sub(r'(?i)\b(am|pm)\b', 'AM/PM', sep)
                machine_fmt += sep_mach
                display_fmt += sep_disp
                
        if "%p" in machine_fmt and "%H" in machine_fmt:
            machine_fmt = machine_fmt.replace("%H", "%I")
            display_fmt = display_fmt.replace("hh", "hh(12)")
                
        return machine_fmt, display_fmt

    def _update_preview(self, *args):
        machine_fmt, display_fmt = self._build_format_strings()
        self.lbl_preview.config(text=f"{display_fmt}  ({machine_fmt})")

    def _on_ok(self):
        machine_fmt, display_fmt = self._build_format_strings()
        if not machine_fmt:
            from tkinter import messagebox
            messagebox.showerror("Fehler", "Bitte definieren Sie ein gültiges Datumsformat.", parent=self)
            return
        self.result_format = (machine_fmt, display_fmt)
        self.destroy()
