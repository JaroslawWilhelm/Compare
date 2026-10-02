import tkinter as tk
from tkinter import ttk

# =========================================================================================
# File: tree_widget.py
# -----------------------------------------------------------------------------------------
# This file is responsible for the "View" aspect of our file structure hierarchy.
# We subclass Tkinter's standard Treeview widget to build a visual folder/file tree 
# representing our DataNode structure (Model). 
# 
# Why a custom class? 
# Custom classes allow us to encapsulate all tree-related logic (like hover effects and
# data synchronization) in one place, abstracting GUI complexities away from the main loop.
# =========================================================================================

class FileStructureTree(ttk.Treeview):
    """
    Tkinter replacement for wx.dataview.DataViewCtrl.
    Visually represents the DataNode hierarchy (e.g., folders acting as files/sheets/columns).
    """
    _instances = []
    global_font_size = 11

    def __init__(self, parent, **kwargs):
        # Initialize the underlying ttk.Treeview
        # 'show="tree"' hides the standard column headers because we just want a tree list.
        # 'selectmode="browse"' restricts the user to selecting only one item at a time.
        # We start with displaycolumns empty or just "info" to hide the type column by default.
        super().__init__(parent, columns=("type", "info"), show="tree", selectmode="browse", displaycolumns=(), **kwargs)
        
        # "#0" is the default, hidden first column in Treeviews that contains the tree icons (+/-)
        # We repurpose it to show our actual data.
        self.heading("#0", text="File Structure", anchor="w")
        self.column("#0", width=250, minwidth=100, stretch=False)
        
        # Type column (hidden by default)
        self.heading("type", text="Typ", anchor="w")
        self.column("type", width=150, minwidth=60, stretch=True, anchor="w")
        
        # We create a dummy column called "info" with 0 width to store metadata if needed later
        self.column("info", width=0, stretch=False) 
        
        # We need to manually keep track of the item currently being hovered over by the mouse.
        # Tkinter's Treeview doesn't have a built-in "hover" CSS-like state for individual rows.
        self._hovered_item = None
        
        # Tooltip tracking
        self._tooltip_window = None
        self._hovered_cell = (None, None)
        
        # Setup visual styles and binding events
        self._setup_tags()
        self._setup_events()
        
        FileStructureTree._instances.append(self)
        self.bind("<Destroy>", self._on_destroy, add="+")
        
        # Apply any saved zoom
        self.apply_initial_zoom()

    def _on_destroy(self, event):
        if event.widget == self and self in FileStructureTree._instances:
            FileStructureTree._instances.remove(self)
            
    def apply_initial_zoom(self):
        from ui_components import ZoomManager
        if "file_trees" in ZoomManager.GLOBAL_STATES:
            fs = 11 + ZoomManager.GLOBAL_STATES["file_trees"]
            FileStructureTree.global_font_size = fs
            self._apply_global_font_style(fs)
            
    def _apply_global_font_style(self, fs):
        style = ttk.Style()
        style.configure("Treeview", font=("Segoe UI", fs), rowheight=int(fs * 2.2))
        style.configure("Treeview.Heading", font=("Segoe UI", fs, "bold"))
        for inst in FileStructureTree._instances:
            try:
                inst.tag_configure("active_bold", font=("Segoe UI", fs, "bold"))
                inst.tag_configure("locked", font=("Segoe UI", fs, "italic"))
                inst.tag_configure("ignored_col", font=("Segoe UI", fs, "italic"))
                inst.tag_configure("gruen_normal", font=("Segoe UI", fs, "bold"))
                inst.tag_configure("orange_normal", font=("Segoe UI", fs, "bold"))
            except Exception:
                pass

    def _setup_tags(self):
        """
        Configures the visual states (tags) a row can have. 
        
        CRITICAL CONCEPT: In Tkinter, a Treeview row can be assigned multiple tags.
        However, Tkinter applies the styles in the order the tags were DEFINED (configured here),
        NOT the order they are applied to the row! Therefore, the "hover" tag must be 
        configured last so it overrides the background color of any other active tags.
        """
        # 1. Default / Inactive state (Gray text to show standard items)
        self.tag_configure("inactive", foreground="#A0A0A0")
        
        # 2. Zebra Striping (Alternating Backgrounds)
        self.tag_configure("even_row", background="#ffffff")
        self.tag_configure("odd_row", background="#f4f5f7")
        
        fs = FileStructureTree.global_font_size
        
        # 3. Active state (Black, Bold text for highlighted items)
        self.tag_configure("active_bold", font=("Segoe UI", fs, "bold"), foreground="#000000")
        
        # 3. Locked state (Greyed-out, italic – visually distinct from inactive)
        self.tag_configure("locked", foreground="#C8C8C8", font=("Segoe UI", fs, "italic"))
        
        # Ignored column state
        self.tag_configure("ignored_col", foreground="#C8C8C8", font=("Segoe UI", fs, "italic"))
        
        # 4. Type Confidence tags (100% green, ambiguous orange)
        self.tag_configure("gruen_normal", font=("Segoe UI", fs, "bold"), foreground="green")
        self.tag_configure("orange_normal", font=("Segoe UI", fs, "bold"), foreground="orange")
        
        # 5. Hover state (Background highlight when mouse passes over)
        self.tag_configure("hover", background="#E5F3FF")

    def set_theme(self, theme):
        is_dark = (theme == "dark")
        fs = FileStructureTree.global_font_size
        
        self.tag_configure("inactive", foreground="#808080" if is_dark else "#A0A0A0")
        self.tag_configure("even_row", background="#1e1e1e" if is_dark else "#ffffff")
        self.tag_configure("odd_row", background="#252525" if is_dark else "#f4f5f7")
        self.tag_configure("active_bold", font=("Segoe UI", fs, "bold"), foreground="#ffffff" if is_dark else "#000000")
        self.tag_configure("locked", foreground="#555555" if is_dark else "#C8C8C8", background="#1e1e1e" if is_dark else "#ffffff", font=("Segoe UI", fs, "italic"))
        self.tag_configure("ignored_col", foreground="#555555" if is_dark else "#C8C8C8", font=("Segoe UI", fs, "italic"))
        self.tag_configure("gruen_normal", font=("Segoe UI", fs, "bold"), foreground="#66bb6a" if is_dark else "green")
        self.tag_configure("orange_normal", font=("Segoe UI", fs, "bold"), foreground="#ffb74d" if is_dark else "orange")
        self.tag_configure("hover", background="#004a77" if is_dark else "#E5F3FF")

    def _setup_events(self):
        """
        Binds precise mouse events to functions to create a modern, reactive hover effect.
        We use a high-performance throttle pattern to avoid CPU spikes during fast mouse movements.
        """
        import time
        self._last_motion_time = 0
        
        self.bind("<Motion>", self._throttled_motion)
        self.bind("<Leave>", self._on_mouse_leave)
        self.bind("<ButtonPress>", self._hide_tooltip, add="+")
        
        self.bind("<Control-MouseWheel>", self._on_zoom)
        self.bind("<Control-Button-4>", self._on_zoom)
        self.bind("<Control-Button-5>", self._on_zoom)

    def _on_zoom(self, event):
        delta = 1 if (event.delta > 0 or event.num == 4) else -1
        if (FileStructureTree.global_font_size <= 6 and delta < 0) or (FileStructureTree.global_font_size >= 30 and delta > 0): return
        
        FileStructureTree.global_font_size += delta
        fs = FileStructureTree.global_font_size
        
        from ui_components import ZoomManager
        ZoomManager.GLOBAL_STATES["file_trees"] = fs - 11
        
        self._apply_global_font_style(fs)

    def _throttled_motion(self, event):
        """Hardware-efficient Throttling limiter. Forces max 50 calculations per second."""
        import time
        now = time.time()
        if now - self._last_motion_time > 0.02:
            self._last_motion_time = now
            self._on_mouse_motion(event)

    def _on_mouse_motion(self, event):
        """
        Triggered when the mouse moves. We calculate exactly which row the mouse is over
        and manually inject or remove the 'hover' tag from the row's list of tags.
        """
        # event.y gives us the absolute pixel coordinate of the cursor. 
        # identify_row translates that pixel into a Tkinter Item ID (iid).
        item = self.identify_row(event.y) 
        col = self.identify_column(event.x)
        
        # Handle tooltip scheduling
        if (item, col) != self._hovered_cell:
            self._hovered_cell = (item, col)
            self._hide_tooltip()
            if item and col:
                self._show_tooltip(item, col, event.x_root, event.y_root)
        
        # To save CPU cycles, only update if the mouse actually moved to a *different* item
        if item != self._hovered_item:
            # Step 1: Remove the hover effect from the previously hovered item
            if self._hovered_item and self.exists(self._hovered_item):
                tags = list(self.item(self._hovered_item, "tags"))
                if "hover" in tags:
                    tags.remove("hover")
                    # Restore the zebra striping tag
                    idx = self.index(self._hovered_item)
                    zebra_tag = "even_row" if idx % 2 == 0 else "odd_row"
                    if zebra_tag not in tags:
                        tags.append(zebra_tag)
                    self.item(self._hovered_item, tags=tags)
            
            # Step 2: Apply the hover effect to the new item under the mouse
            if item:
                tags = list(self.item(item, "tags"))
                if "hover" not in tags:
                    # Remove zebra striping tags so hover background works reliably
                    if "even_row" in tags: tags.remove("even_row")
                    if "odd_row" in tags: tags.remove("odd_row")
                    tags.append("hover")
                    self.item(item, tags=tags)
            
            # Step 3: Update our tracker
            self._hovered_item = item

    def _on_mouse_leave(self, event):
        """Ensures the highlight vanishes cleanly if the mouse leaves the widget entirely."""
        self._hide_tooltip()
        self._hovered_cell = (None, None)
        
        if self._hovered_item and self.exists(self._hovered_item):
            tags = list(self.item(self._hovered_item, "tags"))
            if "hover" in tags:
                tags.remove("hover")
                idx = self.index(self._hovered_item)
                zebra_tag = "even_row" if idx % 2 == 0 else "odd_row"
                if zebra_tag not in tags:
                    tags.append(zebra_tag)
                self.item(self._hovered_item, tags=tags)
        self._hovered_item = None
        
    def _hide_tooltip(self, event=None):
        if self._tooltip_window:
            self._tooltip_window.destroy()
            self._tooltip_window = None
            
    def _show_tooltip(self, item, col, x, y):
        # Determine the text for the current cell
        text = ""
        if col == '#0':
            text = self.item(item, "text")
        else:
            try:
                # col is usually '#1', '#2', etc.
                col_idx = int(col.replace('#', '')) - 1
                values = self.item(item, "values")
                if 0 <= col_idx < len(values):
                    text = values[col_idx]
            except Exception:
                pass
                
        if not text:
            return
            
        import tkinter.font as tkfont
        bbox = self.bbox(item, col)
        if bbox:
            _, _, w, _ = bbox
            f = tkfont.Font(family="Segoe UI", size=11, weight="bold")
            
            available_w = w
            if col == '#0':
                depth = 0
                p = self.parent(item)
                while p:
                    depth += 1
                    p = self.parent(p)
                available_w = w - (depth * 20 + 25)
                
            # If the text width is comfortably smaller than the available width, no tooltip needed
            if f.measure(str(text)) < available_w:
                return 
                
        self._tooltip_window = tk.Toplevel(self)
        self._tooltip_window.wm_overrideredirect(True)
        # Position the tooltip slightly offset from the mouse pointer
        self._tooltip_window.wm_geometry(f"+{x+19}+{y+19}")
        
        lbl = tk.Label(self._tooltip_window, text=str(text), justify='left',
                       background="#ffffe0", relief="solid", borderwidth=1,
                       font=("Segoe UI", 11))
        lbl.pack(ipadx=1)

    def sync_with_model(self, root_node):
        """
        Rebuilds the entire visual tree based on the provided Model (DataNode).
        
        This prevents desynchronization. If the data changes, we just wipe the GUI and 
        rebuild it from scratch using the true data source.
        """
        # Save open state by text (since IIDs will change)
        def save_state(iid):
            state = {}
            if self.exists(iid):
                text = self.item(iid, "text")
                state[text] = self.item(iid, "open")
                for child in self.get_children(iid):
                    state.update(save_state(child))
            return state
            
        open_states = {}
        for root in self.get_children():
            open_states.update(save_state(root))
            
        # BEST PRACTICE: Always delete existing children before rebuilding.
        # Otherwise, every reload creates duplicates in memory until the application crashes.
        self.delete(*self.get_children()) 
        
        if root_node:
            self._insert_node("", root_node) # "" represents the invisible absolute root of the tree
            
        # Restore open state
        def restore_state(iid):
            if self.exists(iid):
                text = self.item(iid, "text")
                if text in open_states and open_states[text]:
                    self.item(iid, open=True)
                for child in self.get_children(iid):
                    restore_state(child)
                    
        for root in self.get_children():
            restore_state(root)

    def _insert_node(self, parent_iid, node, index=0):
        """
        A recursive function to insert a DataNode and all its nested children into the Treeview.
        
        Args:
            parent_iid: The Tkinter Item ID of the parent folder.
            node: The DataNode object to process.
            index: The position of this node among its siblings (used for zebra striping).
        """
        # We must link the GUI item to the python object. We use the memory address of the object as the ID.
        node_iid = str(id(node))
        
        # Determine the label to show. Note the priority logic:
        # A node usually only has ONE of these. If it's a column, show the column name. Else fallback to sheet, etc.
        if node.col is not None:
            col_idx = index
            letter = ""
            while col_idx >= 0:
                letter = chr(col_idx % 26 + 65) + letter
                col_idx = col_idx // 26 - 1
                
            col_name = str(node.col).strip()
            if not getattr(node, 'has_header', False):
                text = f"{letter}"
            else:
                text = f"{letter + '     '} {node.col}"
        elif node.sheetname is not None:
            text = str(node.sheetname)
        else:
            text = str(node.filename)

        # Determine the visual tags based on the model's boolean flags
        tags = ["active_bold"] if node.styled else ["inactive"]
        
        if getattr(node, 'is_ignored', False):
            tags = ["ignored_col"]
        
        # Apply Zebra striping based on the sibling index
        if index % 2 == 0:
            tags.append("even_row")
        else:
            tags.append("odd_row")

        # Insert the item into the Tkinter tree
        # 'end' means it gets appended at the bottom of its parent's list of children
        self.insert(parent_iid, "end", iid=node_iid, text=text, tags=tuple(tags), values=("", ""))

        # Recursion Step: Drill down and do the exact same process for every child 
        for i, child in enumerate(node.children):
            self._insert_node(node_iid, child, index=i)
            
        # Post-processing: Automatically open the root node so the user doesn't have to manually click the '+' icon
        if parent_iid == "":
            self.item(node_iid, open=True)



    def update_types(self, sheet_iid: str, type_dict: dict):
        """
        Updates the 'type' column for children of the given sheet_iid.
        type_dict maps column indices (0, 1, 2...) to string types ("Text", "Decimal", ...).
        """
        children = self.get_children(sheet_iid)
        for col_idx, child_iid in enumerate(children):
            c_type = type_dict.get(col_idx, "Auto")
            self.item(child_iid, values=(c_type, ""))

    # ==========================================
    # PILOT MODE: Selective Item Locking
    # ==========================================
    def set_selectable_items(self, allowed_iids: set[str] | None):
        """
        Restricts user selection to a specific set of tree items (Pilot Mode).
        
        All items NOT in `allowed_iids` receive the "locked" tag (greyed-out, italic)
        and cannot be selected. A <ButtonPress-1> interceptor blocks clicks on
        locked items BEFORE Tkinter processes the selection change.
        
        Args:
            allowed_iids: Set of Tkinter item IDs (iids) that remain selectable.
                          Pass None to unlock everything (equivalent to calling unlock_all).
        """
        if allowed_iids is None:
            self.unlock_all()
            return
            
        self._allowed_iids = allowed_iids
        
        # Walk the entire tree and apply/remove the "locked" tag
        self._apply_lock_tags_recursive("", allowed_iids)
        
        # Install the click interceptor (only once – check via attribute flag).
        # We use <ButtonPress-1> instead of <<TreeviewSelect>> because it fires
        # BEFORE Tkinter commits the selection, allowing us to block it entirely
        # by returning "break".
        if not getattr(self, "_guard_installed", False):
            self.bind("<ButtonPress-1>", self._on_click_guard, add=False)
            self._guard_installed = True
    
    def unlock_all(self):
        """
        Removes all locking restrictions. Every item becomes selectable again
        and the "locked" tag is stripped from all items.
        """
        self._allowed_iids = None
        self._remove_lock_tags_recursive("")
        
        # Remove the click interceptor so normal clicking is restored
        if getattr(self, "_guard_installed", False):
            self.unbind("<ButtonPress-1>")
            self._guard_installed = False
    
    def _apply_lock_tags_recursive(self, parent_iid: str, allowed: set[str]):
        """Recursively applies or removes the 'locked' tag based on the allowed set."""
        for iid in self.get_children(parent_iid):
            tags = list(self.item(iid, "tags"))
            
            if iid in allowed:
                # Remove "locked" if present, keep original styling
                if "locked" in tags:
                    tags.remove("locked")
                    if "active_bold" not in tags and "inactive" not in tags and "ignored_col" not in tags:
                        tags.append("active_bold")
                    self.item(iid, tags=tags)
            else:
                # Add "locked" tag – replaces visual styling
                # Remove conflicting visual tags first
                for old_tag in ("active_bold", "inactive"):
                    if old_tag in tags:
                        tags.remove(old_tag)
                if "locked" not in tags:
                    tags.append("locked")
                self.item(iid, tags=tags)
            
            # Recurse into children
            self._apply_lock_tags_recursive(iid, allowed)
    
    def _remove_lock_tags_recursive(self, parent_iid: str):
        """Recursively removes the 'locked' tag and restores the default 'active_bold' styling."""
        for iid in self.get_children(parent_iid):
            tags = list(self.item(iid, "tags"))
            if "locked" in tags:
                tags.remove("locked")
                # Restore to active_bold as default (since all loaded items are styled)
                if "active_bold" not in tags and "inactive" not in tags:
                    tags.append("active_bold")
                self.item(iid, tags=tags)
            self._remove_lock_tags_recursive(iid)
    
    def _on_click_guard(self, event):
        """
        Click Interceptor: Blocks clicks on locked items BEFORE selection occurs.
        
        By binding to <ButtonPress-1> and returning "break", we prevent Tkinter's
        default Treeview selection behavior from firing at all. This is far more
        robust than the <<TreeviewSelect>> approach (which fires AFTER selection)
        because the user never sees any flicker or intermediate state.
        
        For allowed items, we return None (implicit), letting Tkinter process
        the click normally.
        """
        allowed = getattr(self, "_allowed_iids", None)
        if allowed is None:
            return  # No restrictions active – let click through
            
        # Identify which tree item is under the mouse cursor
        item = self.identify_row(event.y)
        
        if item and item not in allowed:
            # Block the click entirely – "break" stops Tkinter from processing
            # the event further, so no selection change, no <<TreeviewSelect>>,
            # no visual feedback. The item stays locked.
            return "break"
        
        # Item is allowed (or click is on empty space) – let it through normally
        
    def show_type_column(self, show: bool):
        if show:
            self.configure(displaycolumns=("type",), show="tree headings")
            # Workaround for Tkinter bug: Force recalculation of stretched columns
            # when a column is added to displaycolumns dynamically.
            self.column("type", stretch=False)
            self.column("type", stretch=True)
        else:
            self.configure(displaycolumns=(), show="tree")

    def update_types(self, sheet_iid: str, types_dict: dict, confidences_dict: dict = None, is_auto_dict: dict = None):
        children = self.get_children(sheet_iid)
        for i, child_iid in enumerate(children):
            val = types_dict.get(i, "Mix") if isinstance(types_dict, dict) else (types_dict[i] if i < len(types_dict) else "Mix")
            
            is_auto = is_auto_dict.get(i, True) if is_auto_dict else True
            if is_auto:
                if val == "Mix":
                    val = "Auto: Mix"
                else:
                    val = f"Auto: {val}"
            
            if confidences_dict and i in confidences_dict:
                conf = confidences_dict[i]
                if isinstance(conf, str):
                    if conf != "100%":
                        val = f"⚠️ {val} ({conf})"
                    else:
                        val = f"✓ {val} (100%)"
                else:
                    if conf < 100.0:
                        val = f"⚠️ {val} ({conf:g}%)"
                    else:
                        val = f"✓ {val} (100%)"
                    
            self.set(child_iid, "type", val)
            
            # The user requested that the tree text remains black.
            # By not appending color tags (green/orange), the text inherits the default 'active_bold' (black).

    def clear_all_type_tags(self):
        """
        Removes the type-specific color and font tags from all items in the tree,
        restoring their default (active_bold or inactive) visual state.
        """
        for root_item in self.get_children(""):
            for sheet_item in self.get_children(root_item):
                for child_iid in self.get_children(sheet_item):
                    current_tags = list(self.item(child_iid, "tags"))
                    tags_to_remove = ["gruen_fett", "orange_fett", "gruen_normal", "orange_normal"]
                    modified = False
                    for t in tags_to_remove:
                        if t in current_tags:
                            current_tags.remove(t)
                            modified = True
                    if modified:
                        if "active_bold" not in current_tags and "inactive" not in current_tags:
                            current_tags.append("active_bold")
                        self.item(child_iid, tags=current_tags)