import tkinter as tk 
from tkinter import messagebox 
import random 
import heapq 
import time 
from typing import Tuple, List, Optional 
SIZE = 4 
GOAL = tuple(range(1, 16)) + (0,) 
# Difficulty levels (number of random moves from goal state) 
DIFFICULTY_LEVELS = { 
    "Easy": 20, 
    "Medium": 50, 
    "Hard": 100 
} 
# ------------------------------- 
# Utility Functions 
# ------------------------------- 
def count_inversions(state: Tuple[int, ...]) -> int: 
    """Count the number of inversions in the puzzle state.""" 
    arr = [x for x in state if x != 0] 
    inv = 0 
    for i in range(len(arr)): 
        for j in range(i + 1, len(arr)): 
            if arr[i] > arr[j]: 
                inv += 1 
    return inv 
def find_blank_row_from_bottom(state: Tuple[int, ...]) -> int: 
    """Find the row of the blank tile counting from the bottom.""" 
    index = state.index(0) 
    row = index // SIZE 
    return SIZE - row 
def is_solvable(state: Tuple[int, ...]) -> bool: 
    inv = count_inversions(state) 
    blank_row = find_blank_row_from_bottom(state) 
    # For 4x4 puzzle: solvable when (inversions + blank_row) is ODD 
    return (inv + blank_row) % 2 == 1 
def get_neighbors(state: Tuple[int, ...]) -> List[Tuple[int, ...]]: 
    """Get all possible neighbor states."""  
    neighbors = [] 
    i = state.index(0) 
    r, c = divmod(i, SIZE) 
    moves = [(-1, 0), (1, 0), (0, -1), (0, 1)] 
    for dr, dc in moves: 
        nr, nc = r + dr, c + dc 
        if 0 <= nr < SIZE and 0 <= nc < SIZE: 
            ni = nr * SIZE + nc 
            new = list(state) 
            new[i], new[ni] = new[ni], new[i] 
            neighbors.append(tuple(new)) 
    return neighbors 
def generate_puzzle(solvable: bool = True, difficulty: str = "Medium") -> Tuple[int, ...]: 
    if solvable: 
        # Generate solvable puzzle by making random valid moves from goal state 
        num_moves = DIFFICULTY_LEVELS.get(difficulty, 50) 
        state = GOAL 
        for _ in range(num_moves): 
            neighbors = get_neighbors(state) 
            state = random.choice(neighbors) 
        return state 
    else: 
        # Generate unsolvable puzzle by random shuffle 
        while True: 
            arr = list(range(16)) 
            random.shuffle(arr) 
            state = tuple(arr) 
            if not is_solvable(state): 
                return state 
# ------------------------------- 
# A* Solver 
# ------------------------------- 
def manhattan(state: Tuple[int, ...]) -> int: 
    dist = 0 
    for i, val in enumerate(state): 
        if val == 0: 
            continue 
        goal_row = (val - 1) // SIZE 
        goal_col = (val - 1) % SIZE 
        cur_row = i // SIZE 
        cur_col = i % SIZE 
        dist += abs(goal_row - cur_row) + abs(goal_col - cur_col) 
    return dist 
  
 
  
 
def solve_astar(start: Tuple[int, ...]) -> Optional[List[Tuple[int, ...]]]: 
    if start == GOAL: 
        return [start] 
     
    # Priority queue: (priority, state, path) 
    queue = [(manhattan(start), start, [start])] 
    visited = {start} 
     
    while queue: 
        _, state, path = heapq.heappop(queue) 
         
        # Try all possible moves 
        for next_state in get_neighbors(state): 
            if next_state in visited: 
                continue 
             
            if next_state == GOAL: 
                return path + [next_state] 
             
            visited.add(next_state) 
            priority = len(path) + manhattan(next_state) 
            heapq.heappush(queue, (priority, next_state, path + [next_state])) 
     
    return None 
 
# ------------------------------- 
# GUI 
# ------------------------------- 
class PuzzleGUI: 
    def __init__(self, root): 
        self.root = root 
        self.root.title("15 Puzzle Solver") 
        self.root.resizable(False, False) 
         
        # Pastel color palettes for tiles 
        self.color_palettes = [ 
            {"tile": "#FFB3BA", "blank": "#FFF5F5", "name": "Pastel Pink"},      # Soft pink 
            {"tile": "#BAE1FF", "blank": "#F0F8FF", "name": "Pastel Blue"},      # Soft blue 
            {"tile": "#BAFFC9", "blank": "#F0FFF4", "name": "Pastel Green"},     # Soft green 
            {"tile": "#FFFFBA", "blank": "#FFFEF0", "name": "Pastel Yellow"},    # Soft yellow 
            {"tile": "#FFD9BA", "blank": "#FFF8F0", "name": "Pastel Orange"},    # Soft orange 
            {"tile": "#E0BBE4", "blank": "#F8F4F9", "name": "Pastel Purple"},    # Soft purple 
            {"tile": "#FFDFD3", "blank": "#FFF9F7", "name": "Pastel Peach"},     # Soft peach 
            {"tile": "#C7CEEA", "blank": "#F5F6FA", "name": "Pastel Lavender"},  # Soft lavender 
            {"tile": "#B5EAD7", "blank": "#F0FAF7", "name": "Pastel Mint"},      # Soft mint 
 
  
            {"tile": "#FFE5E5", "blank": "#FFFAFA", "name": "Pastel Rose"},      # Soft rose 
        ] 
         
        self.current_palette = random.choice(self.color_palettes) 
        self.current_difficulty = "Medium" 
         
        # Base colors 
        self.bg_color = "#2C3E50" 
        self.text_color = "#2C3E50"  # Dark text for pastel backgrounds 
        self.button_bg = "#27AE60" 
        self.button_fg = "#FFFFFF" 
         
        self.root.configure(bg=self.bg_color) 
         
        self.state = generate_puzzle(solvable=True, difficulty=self.current_difficulty) 
        self.solving = False 
         
        # Create main frame 
        main_frame = tk.Frame(root, bg=self.bg_color, padx=20, pady=20) 
        main_frame.pack() 
         
        # Title 
        title = tk.Label(main_frame, text="15 PUZZLE SOLVER",  
                        font=("Arial", 24, "bold"), 
                        bg=self.bg_color, fg="#ECF0F1") 
        title.grid(row=0, column=0, columnspan=4, pady=(0, 10)) 
         
        # Status label 
        self.status_label = tk.Label(main_frame, text="",  
                                     font=("Arial", 12), 
                                     bg=self.bg_color, fg="#ECF0F1") 
        self.status_label.grid(row=1, column=0, columnspan=4, pady=(0, 10)) 
         
        # Puzzle grid frame 
        grid_frame = tk.Frame(main_frame, bg=self.bg_color) 
        grid_frame.grid(row=2, column=0, columnspan=4, pady=(0, 20)) 
         
        # Create puzzle buttons 
        self.buttons = [] 
        for i in range(16): 
            btn = tk.Button(grid_frame, text="", width=5, height=2, 
                          font=("Arial", 20, "bold"), 
                          relief=tk.RAISED, 
                          bd=3, 
                          command=lambda i=i: self.move_tile(i)) 
            btn.grid(row=i//4, column=i%4, padx=2, pady=2) 
 
  
            self.buttons.append(btn) 
         
        # Control buttons frame 
        control_frame = tk.Frame(main_frame, bg=self.bg_color) 
        control_frame.grid(row=3, column=0, columnspan=4) 
         
        # Buttons 
        btn_base = { 
            "font": ("Arial", 12, "bold"), 
            "fg": self.button_fg, 
            "relief": tk.RAISED, 
            "bd": 2, 
            "padx": 15, 
            "pady": 8, 
            "cursor": "hand2" 
        } 
         
        tk.Button(control_frame, text="🎲 Generate Puzzle",  
                 command=self.show_generate_menu, bg="#3498DB", **btn_base).grid(row=0, column=0, padx=5, pady=5) 
         
        tk.Button(control_frame, text="🔍 Check Solvability",  
                 command=self.check_solvability, bg="#F39C12", **btn_base).grid(row=0, column=1, padx=5, pady=5) 
         
        tk.Button(control_frame, text="🤖 Solve",  
                 command=self.solve, bg="#9B59B6", **btn_base).grid(row=0, column=2, padx=5, pady=5) 
         
        # Info frame for move counter and difficulty 
        info_frame = tk.Frame(main_frame, bg=self.bg_color) 
        info_frame.grid(row=4, column=0, columnspan=4, pady=(10, 0)) 
         
        # Move counter 
        self.move_count = 0 
        self.move_label = tk.Label(info_frame, text="Moves: 0",  
                                   font=("Arial", 12), 
                                   bg=self.bg_color, fg="#ECF0F1") 
        self.move_label.pack(side=tk.LEFT, padx=10) 
         
        # Difficulty display 
        self.difficulty_label = tk.Label(info_frame, text=f"Difficulty: {self.current_difficulty}",  
                                        font=("Arial", 12), 
                                        bg=self.bg_color, fg="#ECF0F1") 
        self.difficulty_label.pack(side=tk.LEFT, padx=10) 
         
  
 
  
        self.update_grid() 
        self.update_status() 
 
    def update_grid(self): 
        """Update the visual representation of the puzzle.""" 
        for i in range(16): 
            val = self.state[i] 
            btn = self.buttons[i] 
             
            if val == 0: 
                btn["text"] = "" 
                btn["bg"] = self.current_palette["blank"] 
                btn["fg"] = self.current_palette["blank"] 
                btn["state"] = tk.DISABLED 
            else: 
                btn["text"] = str(val) 
                btn["bg"] = self.current_palette["tile"] 
                btn["fg"] = self.text_color 
                btn["state"] = tk.NORMAL if not self.solving else tk.DISABLED 
         
        # Check if solved 
        if self.state == GOAL: 
            self.status_label["text"] = "🎉 SOLVED! Congratulations!" 
            self.status_label["fg"] = "#2ECC71" 
 
    def update_status(self): 
        """Update the status message.""" 
        if self.state == GOAL: 
            self.status_label["text"] = "🎉 SOLVED! Congratulations!" 
            self.status_label["fg"] = "#2ECC71" 
        else: 
            solvable = is_solvable(self.state) 
            if solvable: 
                self.status_label["text"] = "✓ Puzzle is solvable" 
                self.status_label["fg"] = "#2ECC71" 
            else: 
                self.status_label["text"] = "✗ Puzzle is NOT solvable" 
                self.status_label["fg"] = "#E74C3C" 
 
    def move_tile(self, index): 
        """Move a tile if adjacent to blank.""" 
        if self.solving: 
            return 
             
        blank = self.state.index(0) 
        r1, c1 = divmod(index, 4) 
  
 
  
        r2, c2 = divmod(blank, 4) 
 
        if abs(r1 - r2) + abs(c1 - c2) == 1: 
            new = list(self.state) 
            new[blank], new[index] = new[index], new[blank] 
            self.state = tuple(new) 
            self.move_count += 1 
            self.move_label["text"] = f"Moves: {self.move_count}" 
            self.update_grid() 
            self.update_status() 
 
    def show_generate_menu(self): 
        """Show menu to choose between solvable and unsolvable puzzle, plus difficulty.""" 
        menu_window = tk.Toplevel(self.root) 
        menu_window.title("Generate Puzzle") 
        menu_window.configure(bg=self.bg_color) 
        menu_window.geometry("400x450") 
        menu_window.resizable(False, False) 
         
        # Center the window 
        menu_window.transient(self.root) 
        menu_window.grab_set() 
         
        main = tk.Frame(menu_window, bg=self.bg_color, padx=30, pady=30) 
        main.pack(fill=tk.BOTH, expand=True) 
         
        tk.Label(main, text="Choose Puzzle Type",  
                font=("Arial", 16, "bold"), 
                bg=self.bg_color, fg="#ECF0F1").pack(pady=(0, 20)) 
         
        # Difficulty selection frame 
        difficulty_frame = tk.Frame(main, bg=self.bg_color) 
        difficulty_frame.pack(pady=(0, 20)) 
         
        tk.Label(difficulty_frame, text="Difficulty Level:",  
                font=("Arial", 12, "bold"), 
                bg=self.bg_color, fg="#ECF0F1").pack() 
         
        # Variable to store selected difficulty 
        difficulty_var = tk.StringVar(value=self.current_difficulty) 
         
        # Difficulty radio buttons 
        for level in ["Easy", "Medium", "Hard"]: 
            moves = DIFFICULTY_LEVELS[level] 
            rb = tk.Radiobutton( 
                difficulty_frame,  
  
                text=f"{level} ({moves} moves)", 
                variable=difficulty_var, 
                value=level, 
                font=("Arial", 11), 
                bg=self.bg_color, 
                fg="#ECF0F1", 
                selectcolor=self.bg_color, 
                activebackground=self.bg_color, 
                activeforeground="#ECF0F1", 
                cursor="hand2" 
            ) 
            rb.pack(anchor=tk.W, pady=2) 
         
        tk.Label(main, text="Solvability:",  
                font=("Arial", 12, "bold"), 
                bg=self.bg_color, fg="#ECF0F1").pack(pady=(10, 10)) 
         
        btn_style = { 
            "font": ("Arial", 12, "bold"), 
            "fg": "#FFFFFF", 
            "width": 20, 
            "pady": 10, 
            "cursor": "hand2" 
        } 
         
        def generate_and_close(solvable): 
            selected_difficulty = difficulty_var.get() 
            self.generate_new_puzzle(solvable, selected_difficulty) 
            menu_window.destroy() 
         
        tk.Button(main, text="✓ Solvable Puzzle",  
                 bg="#27AE60",  
                 command=lambda: generate_and_close(True), 
                 **btn_style).pack(pady=5) 
         
        tk.Button(main, text="✗ Unsolvable Puzzle",  
                 bg="#E74C3C", 
                 command=lambda: generate_and_close(False), 
                 **btn_style).pack(pady=5) 
     
    def generate_new_puzzle(self, solvable: bool, difficulty: str = None): 
        """Generate a new puzzle (solvable or unsolvable) with specified difficulty.""" 
        if difficulty: 
            self.current_difficulty = difficulty 
         
        self.state = generate_puzzle(solvable, self.current_difficulty) 
        self.current_palette = random.choice(self.color_palettes) 
        self.move_count = 0 
        self.move_label["text"] = "Moves: 0" 
        self.difficulty_label["text"] = f"Difficulty: {self.current_difficulty}" 
        self.update_grid() 
        self.update_status() 
        if not solvable: 
            messagebox.showinfo( 
                "Unsolvable Puzzle Generated", 
                "This puzzle is mathematically UNSOLVABLE!\n\n" 
                "The parity makes it impossible to solve.\n" 
                "Click 'Check Solvability' to see the proof." 
            ) 
    def check_solvability(self): 
        """Check and display solvability with simple proof.""" 
        solvable = is_solvable(self.state) 
        inversions = count_inversions(self.state) 
        blank_row = find_blank_row_from_bottom(self.state) 
        parity_sum = inversions + blank_row 
        if solvable: 
            message = f"""✓ SOLVABLE 
Inversions: {inversions} 
Blank row: {blank_row} 
Sum: {inversions} + {blank_row} = {parity_sum} (ODD) 
For a 15-puzzle to be solvable, this sum must be ODD. 
✓ This puzzle CAN be solved!""" 
        else: 
            message = f"""✗ UNSOLVABLE 
Inversions: {inversions} 
Blank row: {blank_row} 
Sum: {inversions} + {blank_row} = {parity_sum} (EVEN) 
For a 15-puzzle to be solvable, this sum must be ODD. 
✗ This puzzle CANNOT be solved!""" 
        if solvable: 
            messagebox.showinfo("Solvability Check", message) 
        else: 
            messagebox.showwarning("Solvability Check", message) 
  
  
    def solve(self): 
        """Solve the puzzle using A* algorithm.""" 
        if self.solving: 
            return 
         
        if self.state == GOAL: 
            messagebox.showinfo("Already Solved", "Puzzle is already solved!") 
            return 
         
        if not is_solvable(self.state): 
            messagebox.showerror( 
                "Cannot Solve", 
                "This puzzle is UNSOLVABLE!\n\n" 
                "Generate a solvable puzzle to continue." 
            ) 
            return 
         
        self.solving = True 
        self.status_label["text"] = "🤖 Solving..." 
        self.status_label["fg"] = "#F39C12" 
        self.root.update() 
         
        path = solve_astar(self.state) 
         
        if path: 
            self.animate(path) 
        else: 
            messagebox.showerror("Error", "Could not find solution!") 
            self.solving = False 
            self.update_status() 
 
    def animate(self, path): 
        """Animate the solution.""" 
        for i, state in enumerate(path): 
            self.state = state 
            self.update_grid() 
            self.status_label["text"] = f"Step {i+1}/{len(path)}" 
            self.root.update() 
            time.sleep(0.1)  # Faster animation 
         
        self.solving = False 
        self.move_count = len(path) - 1 
        self.move_label["text"] = f"Moves: {self.move_count}" 
        self.update_status() 
 
if __name__ == "__main__": 
  
 
  
    root = tk.Tk() 
    app = PuzzleGUI(root) 
    root.mainloop()