import tkinter as tk
from tkinter import ttk

root = tk.Tk()
root.title("Ergonomisches modernes Treeview")
root.geometry("780x430")
root.configure(bg="#f4f6f8")

# --- 1. Ergonomische Farbpalette (Augenschonendes Slate-Design) ---
BG_MAIN       = "#ffffff"  # Weißer, klarer Hintergrund für Text
BG_ROOT       = "#f4f6f8"  # Sanftes Grau für den Fensterhintergrund
BG_HEADER     = "#edf2f7"  # Blendfreies, helles Schiefergrau
FG_MAIN       = "#2d3748"  # Dunkelgrau statt hartem Schwarz
BORDER_COLOR  = "#cbd5e1"  # Feine, sichtbare Trennlinien (Slate 300)
SELECT_BG     = "#3182ce"  # Angenehmes Blau
SELECT_FG     = "#ffffff"
ROW_ODD       = "#f8fafc"  # Sehr dezentes Zebra-Muster

# System-Schriftart
FONT_FAMILY = "Segoe UI" if "win" in root.tk.call("tk", "windowingsystem") else "Helvetica"
FONT_NORMAL = (FONT_FAMILY, 10)
FONT_BOLD   = (FONT_FAMILY, 10, "bold")

# --- 2. Moderne Pfeil-Icons (Transparente Bitmaps) ---
def create_arrow_icons():
    closed_img = tk.PhotoImage(width=16, height=16)
    open_img = tk.PhotoImage(width=16, height=16)
    empty_img = tk.PhotoImage(width=16, height=16)

    # Chevron rechts (›)
    chevron_right = [
        (5, 3), (6, 3), (6, 4), (7, 4), (7, 5), (8, 5),
        (8, 6), (9, 6), (8, 7), (9, 7), (7, 8), (8, 8),
        (6, 9), (7, 9), (5, 10), (6, 10)
    ]
    for x, y in chevron_right:
        closed_img.put("#64748b", (x, y))

    # Chevron unten (ˇ)
    chevron_down = [
        (3, 5), (3, 6), (4, 6), (4, 7), (5, 7), (5, 8),
        (6, 8), (6, 9), (7, 8), (7, 9), (8, 7), (8, 8),
        (9, 6), (9, 7), (10, 5), (10, 6)
    ]
    for x, y in chevron_down:
        open_img.put("#64748b", (x, y))

    return closed_img, open_img, empty_img

img_closed, img_open, img_empty = create_arrow_icons()

# --- 3. TTK-Style Konfiguration ---
style = ttk.Style()
style.theme_use("clam")

# Eigene Pfeile im Theme registrieren
style.element_create(
    "Modern.Treeitem.indicator",
    "image",
    img_closed,
    ("user1 !user2", img_open),
    ("user2", img_empty),
    sticky="w"
)

style.layout("Modern.Treeview.Item", [
    ("Treeitem.padding", {"sticky": "nswe", "children": [
        ("Modern.Treeitem.indicator", {"side": "left", "sticky": ""}),
        ("Treeitem.image", {"side": "left", "sticky": ""}),
        ("Treeitem.text", {"side": "left", "sticky": ""})
    ]})
])

# Treeview Body
style.configure("Modern.Treeview",
    background=BG_MAIN,
    foreground=FG_MAIN,
    fieldbackground=BG_MAIN,
    font=FONT_NORMAL,
    rowheight=32,          # Ergonomischer, moderner Zeilenabstand
    borderwidth=0,
    indent=16
)

style.map("Modern.Treeview",
    background=[("selected", SELECT_BG)],
    foreground=[("selected", SELECT_FG)]
)

# Treeview Headings (mit klaren vertikalen Trennern)
style.configure("Modern.Treeview.Heading",
    background=BG_HEADER,
    foreground=FG_MAIN,
    relief="solid",
    borderwidth=1,
    bordercolor=BORDER_COLOR,
    font=FONT_BOLD,
    padding=(8, 6)
)

style.map("Modern.Treeview.Heading",
    background=[("active", "#e2e8f0")]
)

# --- 4. Container & Treeview aufbauen ---
container = tk.Frame(root, bg=BORDER_COLOR, bd=1)
container.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

columns = ("owner", "status", "progress")
tree = ttk.Treeview(
    container,
    columns=columns,
    show="tree headings",
    style="Modern.Treeview",
    selectmode="browse"
)

# Spalten konfigurieren
tree.heading("#0", text="Projekt / Vorgang", anchor="w")
tree.heading("owner", text="Verantwortlich", anchor="w")
tree.heading("status", text="Status", anchor="w")
tree.heading("progress", text="Fortschritt", anchor="w")

tree.column("#0", width=250, minwidth=180)
tree.column("owner", width=160, minwidth=120)
tree.column("status", width=130, minwidth=100)
tree.column("progress", width=110, minwidth=80)

# Scrollbar
sb = ttk.Scrollbar(container, orient="vertical", command=tree.yview)
tree.configure(yscrollcommand=sb.set)

tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
sb.pack(side=tk.RIGHT, fill=tk.Y)

# Alternierende Zeilenfarben (Zebra-Muster)
tree.tag_configure("odd", background=ROW_ODD)

# --- 5. Demodaten befüllen ---
p1 = tree.insert("", tk.END, text="System-Architektur", values=("Dev-Team", "Aktiv", "80%"), open=True)
tree.insert(p1, tk.END, text="API Gateway", values=("Max M.", "Review", "100%"), tags=("odd",))
tree.insert(p1, tk.END, text="Datenbank-Cluster", values=("Sarah K.", "In Arbeit", "65%"))

p1_sub = tree.insert(p1, tk.END, text="Sicherheitsaudit", values=("SecOps", "Wartend", "20%"), tags=("odd",))
tree.insert(p1_sub, tk.END, text="Penetrationstest", values=("Extern", "Geplant", "0%"))

p2 = tree.insert("", tk.END, text="Frontend Migration", values=("UI-Team", "In Vorbereitung", "15%"))
tree.insert(p2, tk.END, text="Design System & Icons", values=("Elena B.", "In Prüfung", "40%"), tags=("odd",))

root.mainloop()
