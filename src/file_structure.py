from typing import List, Any, Optional

class DataNode:
    """
    Pure data container (Model) representing a single node in a hierarchical tree.
    
    A hierarchical tree structure looks like folders in your computer:
    - Root (e.g., The File)
      - Child (e.g., A Sheet in the CSV)
        - Grandchild (e.g., A specific Column 'A')
        
    Each 'DataNode' represents one of these points. It knows who its parent is, 
    and holds a list of its children. This makes it easy to navigate up and down the data.
    """
    def __init__(
        self,
        filename: Optional[str] = None, 
        sheetname: Optional[str] = None, 
        col: Any = None, 
        row: Optional[int] = None,
        table: Any = None, 
        info: Any = None,
        val: Any = None, 
        parent: Optional["DataNode"] = None, 
        has_header: bool = False,
    ):
        # --- Metadata & Hierarchy ---
        self.filename = filename      # For root nodes: the name of the loaded CSV file
        self.sheetname = sheetname    # For sheet-level nodes: the name of the worksheet
        self.col = col                # For column-level nodes: the column header (e.g. 'A')
        self.row = row                # Reserved for row specific data (if needed)
        
        self.table = table            # A reference to the underlying table/dataframe (optional)
        self.info = info              # Extra payload to store any additional metadata
        self.val = val                # A specific cell value (optional)
        
        # --- Tree Navigation ---
        self.parent = parent          # The node directly above this one. If None, this is the root.
        self.children: List["DataNode"] = [] # A list to store all branches nested directly under this node.
        
        # --- State Tracking ---
        # Note: Even though this is a pure data model, it needs to retain the "state" of how the user 
        # interacted with it, so the UI knows how to render it later.
        self.checked = [False] * 4    # Example usage: stores boolean states for up to 4 virtual checkboxes
        self.styled = False           # Flag to determine if this item should appear bold/highlighted in the UI
        self.has_header = has_header  # Flag to determine if the column has a header



class SingleFileViewModel:
    """
    Pure-Python Controller/ViewModel.
    
    When building a UI with Tkinter's Treeview, Tkinter only understands "Item IDs" (strings).
    Tkinter has no idea what our 'DataNode' python objects are. 
    
    The ViewModel bridges this gap. It walks through the entire tree of DataNodes, looks at 
    where each one lives in the computer's memory, and creates a dictionary linking that 
    memory address back to the actual Python object.
    
    When an item in the GUI is clicked, the GUI sends us the memory address (as a string), 
    and we can use this ViewModel to instantly return the exact original DataNode back!
    """
    def __init__(self, root_node: DataNode):
        self.root_node = root_node
        
        # This dictionary is our fast lookup table. 
        # Format: { "1402245648" : <DataNode object at that address> }
        # Looking up items in a python dict is O(1) inside - basically instantaneous.
        self.dct_id_node = {} 
        
        # As soon as the ViewModel is created, we trigger the build process.
        self._build_dict(self.root_node)

    def _build_dict(self, node: DataNode):
        """
        Recursively builds the search dictionary to easily look up nodes.
        
        'Recursion' is a programming concept where a function calls itself. 
        Here, we tell the function to process the current node, and then call itself 
        on EVERY child of this node. This allows us to map the entire tree, 
        no matter how deep the folders go, without writing complicated loops.
        """
        if node:
            # id(node) gets a unique integer representing the python object's memory address.
            # We wrap it in str() because Tkinter IDs must be strings.
            self.dct_id_node[str(id(node))] = node 
            
            # Here is the recursion step: For every child inside this node, run this same function.
            for child in node.children:
                self._build_dict(child)

    def get_node_by_iid1(self, iid: str) -> Optional[DataNode]:
        """
        Looks up and returns the real data node based on the Tkinter Item ID (iid).
        
        Using .get(iid) is a best practice compared to dct_id_node[iid]. 
        If the iid isn't found, .get() safely returns None instead of crashing
        the program with a KeyError.
        """
        return self.dct_id_node.get(iid)
