import tkinter as tk
from ui_components import ZoomManager

class ColumnCastingView(tk.Frame):
    def __init__(self, parent, data_provider=None):
        super().__init__(parent, bg="#ffffff")
        self.data_provider = data_provider
        
        self.on_type_changed = None # Callback(side, col_idx, new_type)
        self.on_column_selected = None # Callback(side, col_idx)
        
        self._setup_ui()
        self.zoom_manager = ZoomManager(self)
        
    def _setup_ui(self):
        lbl = tk.Label(
            self, 
            text="Bitte definieren Sie die Spaltentypen in den seitlichen Listen\n(Rechtsklick auf eine Spalte) oder direkt in der Tabelle unten.\nKlicken Sie danach auf 'Weiter'.",
            font=("Arial", 12), bg="#ffffff", fg="#555555", justify="center"
        )
        lbl.pack(expand=True)
        
    def load_columns(self, side, columns, column_types=None):
        pass
        
    def update_type(self, side, col_idx, new_type):
        pass
