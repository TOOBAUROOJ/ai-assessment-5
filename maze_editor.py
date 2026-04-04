"""
Maze Editor  –  BFS / DFS animated solver + Random Maze Generator
==================================================================
• 20×20 grid  •  click/drag walls  •  set Start & End
• Random solvable maze via recursive backtracker (DFS carver)
• Algorithm dropdown: BFS (queue) vs DFS (stack)
• Animated step-by-step: BFS=yellow/blue  DFS=purple/teal
• Live stats panel: nodes explored, path length, time taken
"""

import tkinter as tk
from tkinter import messagebox, filedialog, ttk
from collections import deque
import json, random, time

# ── Constants ──────────────────────────────────────────────────────────────────
ROWS, COLS  = 20, 20
CELL        = 30
PAD         = 20

BG          = "#0F1117"
PANEL_BG    = "#1A1D27"
ACCENT      = "#4F8EF7"
WALL_CLR    = "#2A2D3E"
WALL_FILL   = "#3A3F5C"
PATH_CLR    = "#1E2235"
START_CLR   = "#2ECC71"
END_CLR     = "#E74C3C"
GRID_CLR    = "#252840"
TEXT_CLR    = "#C8CCDC"
BTN_HOVER   = "#5A9EFF"
VISITED_CLR = "#C8A020"   # BFS visited  – yellow
DFS_VISITED = "#9B59B6"   # DFS visited  – purple
PATH_SOL    = "#3A8EF7"   # BFS path     – blue
DFS_PATH    = "#1ABC9C"   # DFS path     – teal
STATS_BG    = "#0C0F1A"
STAT_VAL    = "#E8F0FF"

CANVAS_W    = COLS * CELL + PAD * 2
CANVAS_H    = ROWS * CELL + PAD * 2


# ── Helpers ────────────────────────────────────────────────────────────────────
def cell_rect(r, c):
    x0 = PAD + c * CELL
    y0 = PAD + r * CELL
    return x0 + 1, y0 + 1, x0 + CELL - 1, y0 + CELL - 1


def pix_to_cell(x, y):
    c = (x - PAD) // CELL
    r = (y - PAD) // CELL
    if 0 <= r < ROWS and 0 <= c < COLS:
        return r, c
    return None


# ── App ────────────────────────────────────────────────────────────────────────
class MazeEditor:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("Maze Editor  ·  BFS / DFS  ·  Random Generator")
        root.configure(bg=BG)
        root.resizable(False, False)

        self.grid       = [[0] * COLS for _ in range(ROWS)]
        self.start      = (0, 0)
        self.end        = (ROWS - 1, COLS - 1)
        self.mode       = tk.StringVar(value="wall")
        self.drag_val   = None

        self.visited_set = set()
        self.path_set    = set()
        self.solving     = False
        self._anim_id    = None
        self._t_start    = 0.0

        self._build_ui()
        self._draw_all()

    # ──────────────────────────────────────────────────────────────────────────
    # UI
    # ──────────────────────────────────────────────────────────────────────────
    def _build_ui(self):
        # ── Left control panel ────────────────────────────────────────────────
        left = tk.Frame(self.root, bg=PANEL_BG, padx=14, pady=14)
        left.pack(side="left", fill="y")

        tk.Label(left, text="MAZE\nEDITOR", font=("Courier", 17, "bold"),
                 bg=PANEL_BG, fg=ACCENT, justify="center").pack(pady=(0, 16))

        # Tools
        self._section(left, "TOOL")
        self.mode_btns = {}
        for label, val in [("✦  Wall","wall"),("▶  Start","start"),("◼  End","end")]:
            col = {"wall": WALL_FILL, "start": START_CLR, "end": END_CLR}[val]
            b = tk.Button(left, text=label, font=("Courier", 10),
                          bg=PANEL_BG, fg=TEXT_CLR, activebackground=col,
                          activeforeground="#fff", relief="flat",
                          cursor="hand2", anchor="w", padx=8,
                          command=lambda v=val: self._set_mode(v))
            b.pack(fill="x", pady=2)
            self.mode_btns[val] = b

        self._divider(left)

        # Algorithm
        self._section(left, "ALGORITHM")
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Dark.TCombobox",
                        fieldbackground="#252840", background="#252840",
                        foreground=TEXT_CLR, selectbackground="#252840",
                        selectforeground=TEXT_CLR, arrowcolor=ACCENT,
                        bordercolor=GRID_CLR, lightcolor=GRID_CLR, darkcolor=GRID_CLR)
        style.map("Dark.TCombobox",
                  fieldbackground=[("readonly","#252840")],
                  selectbackground=[("readonly","#252840")])

        self.algo_var = tk.StringVar(value="BFS  –  Breadth-First Search")
        dd = ttk.Combobox(left, textvariable=self.algo_var, style="Dark.TCombobox",
                          state="readonly", font=("Courier", 10), width=22)
        dd["values"] = ["BFS  –  Breadth-First Search",
                        "DFS  –  Depth-First Search"]
        dd.pack(fill="x", pady=(2, 4))
        dd.bind("<<ComboboxSelected>>", lambda _: self._update_algo_card())

        self.algo_card = tk.Label(left, text="", font=("Courier", 8),
                                  bg="#12152A", fg=TEXT_CLR,
                                  wraplength=155, justify="left", padx=6, pady=5)
        self.algo_card.pack(fill="x", pady=(0, 4))
        self._update_algo_card()

        # Speed
        self._section(left, "SPEED")
        spd = tk.Frame(left, bg=PANEL_BG)
        spd.pack(fill="x")
        tk.Label(spd, text="Slow", font=("Courier", 8),
                 bg=PANEL_BG, fg=TEXT_CLR).pack(side="left")
        self.speed_var = tk.IntVar(value=80)
        tk.Scale(spd, from_=5, to=200, orient="horizontal",
                 variable=self.speed_var, showvalue=False,
                 bg=PANEL_BG, fg=ACCENT, troughcolor="#252840",
                 highlightthickness=0, bd=0).pack(side="left", fill="x", expand=True)
        tk.Label(spd, text="Fast", font=("Courier", 8),
                 bg=PANEL_BG, fg=TEXT_CLR).pack(side="left")

        self._divider(left)

        # Actions
        self._section(left, "ACTIONS")
        for label, cmd in [
            ("⬡  Solve",     self._start_solve),
            ("⏹  Stop",      self._stop_solve),
            ("⚄  Generate",  self._generate_maze),
            ("⊘  Clear",     self._clear_walls),
            ("↺  Reset",     self._reset),
            ("↓  Export",    self._export),
            ("↑  Import",    self._import),
        ]:
            b = tk.Button(left, text=label, font=("Courier", 10),
                          bg=PANEL_BG, fg=TEXT_CLR,
                          activebackground=ACCENT, activeforeground="#fff",
                          relief="flat", cursor="hand2", anchor="w", padx=8,
                          command=cmd)
            b.pack(fill="x", pady=2)
            self._hover(b)

        self._divider(left)

        # Legend
        self._section(left, "LEGEND")
        for color, label in [
            (START_CLR,   "Start"),
            (END_CLR,     "End"),
            (WALL_FILL,   "Wall"),
            (PATH_CLR,    "Open"),
            (VISITED_CLR, "BFS visited"),
            (DFS_VISITED, "DFS visited"),
            (PATH_SOL,    "BFS path"),
            (DFS_PATH,    "DFS path"),
        ]:
            self._legend_row(left, color, label)

        # Status
        self.status = tk.Label(left, text="Draw walls or Generate a maze.",
                               font=("Courier", 8), bg=PANEL_BG, fg=ACCENT,
                               wraplength=155, justify="left")
        self.status.pack(side="bottom", anchor="w", pady=(10, 0))

        # ── Right side: canvas + stats ─────────────────────────────────────────
        right = tk.Frame(self.root, bg=BG)
        right.pack(side="right", fill="both", expand=True)

        self.canvas = tk.Canvas(right, width=CANVAS_W, height=CANVAS_H,
                                bg=BG, highlightthickness=0, cursor="crosshair")
        self.canvas.pack(padx=PAD, pady=(PAD, 8))
        self.canvas.bind("<ButtonPress-1>",   self._on_press)
        self.canvas.bind("<B1-Motion>",       self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)

        # ── Stats panel ───────────────────────────────────────────────────────
        self._build_stats_panel(right)

        self._set_mode("wall")

    def _build_stats_panel(self, parent):
        """Horizontal stats bar below the canvas."""
        panel = tk.Frame(parent, bg=STATS_BG, padx=16, pady=10)
        panel.pack(fill="x", padx=PAD, pady=(0, PAD))

        tk.Label(panel, text="STATS", font=("Courier", 9, "bold"),
                 bg=STATS_BG, fg=ACCENT).pack(side="left", padx=(0, 20))

        self._stat_vars = {}
        stats = [
            ("nodes",  "Nodes Explored", "—"),
            ("path",   "Path Length",    "—"),
            ("time",   "Time Taken",     "—"),
            ("walls",  "Wall Density",   "—"),
        ]
        for key, label, default in stats:
            box = tk.Frame(panel, bg=STATS_BG, padx=14)
            box.pack(side="left")
            tk.Label(box, text=label, font=("Courier", 7, "bold"),
                     bg=STATS_BG, fg=TEXT_CLR).pack(anchor="w")
            var = tk.StringVar(value=default)
            self._stat_vars[key] = var
            tk.Label(box, textvariable=var, font=("Courier", 14, "bold"),
                     bg=STATS_BG, fg=STAT_VAL).pack(anchor="w")

            # divider between stats (not after last)
            if key != "walls":
                tk.Frame(panel, bg=GRID_CLR, width=1).pack(side="left", fill="y", padx=6)

    def _set_stat(self, key, val):
        self._stat_vars[key].set(str(val))

    def _reset_stats(self):
        for k in self._stat_vars:
            self._stat_vars[k].set("—")
        self._update_wall_density()

    def _update_wall_density(self):
        total = ROWS * COLS
        walls = sum(self.grid[r][c] for r in range(ROWS) for c in range(COLS))
        pct   = round(100 * walls / total)
        self._set_stat("walls", f"{pct}%")

    # ── Small UI helpers ──────────────────────────────────────────────────────
    def _section(self, p, t):
        tk.Label(p, text=t, font=("Courier", 9, "bold"),
                 bg=PANEL_BG, fg=TEXT_CLR).pack(anchor="w")

    def _divider(self, p):
        tk.Frame(p, bg=GRID_CLR, height=1).pack(fill="x", pady=10)

    def _legend_row(self, p, color, label):
        row = tk.Frame(p, bg=PANEL_BG)
        row.pack(fill="x", pady=1)
        tk.Canvas(row, width=11, height=11, bg=color,
                  highlightthickness=0).pack(side="left", padx=(0, 6))
        tk.Label(row, text=label, font=("Courier", 8),
                 bg=PANEL_BG, fg=TEXT_CLR).pack(side="left")

    def _hover(self, btn):
        btn.bind("<Enter>", lambda _: btn.config(fg=BTN_HOVER))
        btn.bind("<Leave>", lambda _: btn.config(fg=TEXT_CLR))

    def _update_algo_card(self):
        if "BFS" in self.algo_var.get():
            txt = ("QUEUE (FIFO). Level-by-level.\n"
                   "Always finds SHORTEST path.\n"
                   "Visited=yellow | Path=blue")
        else:
            txt = ("STACK (LIFO). Dives deep first.\n"
                   "Path may NOT be shortest.\n"
                   "Visited=purple | Path=teal")
        self.algo_card.config(text=txt)

    # ──────────────────────────────────────────────────────────────────────────
    # Mode
    # ──────────────────────────────────────────────────────────────────────────
    def _set_mode(self, val):
        self.mode.set(val)
        colors = {"wall": WALL_FILL, "start": START_CLR, "end": END_CLR}
        hints  = {"wall":  "Click / drag to toggle walls",
                  "start": "Click a cell to place Start",
                  "end":   "Click a cell to place End"}
        for k, b in self.mode_btns.items():
            b.config(bg=colors[k] if k == val else PANEL_BG,
                     fg="#fff"    if k == val else TEXT_CLR,
                     relief="groove" if k == val else "flat")
        self.status.config(text=hints[val])

    # ──────────────────────────────────────────────────────────────────────────
    # Mouse events
    # ──────────────────────────────────────────────────────────────────────────
    def _on_press(self, e):
        if self.solving:
            return
        self._clear_solution()
        cell = pix_to_cell(e.x, e.y)
        if cell is None:
            return
        r, c = cell
        m = self.mode.get()
        if m == "wall":
            self.drag_val      = 1 - self.grid[r][c]
            self.grid[r][c]   = self.drag_val
            self._draw_cell(r, c)
            self._update_wall_density()
        elif m == "start":
            self.start = cell; self._draw_all()
        elif m == "end":
            self.end   = cell; self._draw_all()

    def _on_drag(self, e):
        if self.solving or self.mode.get() != "wall" or self.drag_val is None:
            return
        cell = pix_to_cell(e.x, e.y)
        if cell is None:
            return
        r, c = cell
        if self.grid[r][c] != self.drag_val:
            self.grid[r][c] = self.drag_val
            self._draw_cell(r, c)

    def _on_release(self, _):
        self.drag_val = None
        self._update_wall_density()

    # ──────────────────────────────────────────────────────────────────────────
    # Drawing
    # ──────────────────────────────────────────────────────────────────────────
    def _draw_all(self):
        self.canvas.delete("all")
        for r in range(ROWS + 1):
            y = PAD + r * CELL
            self.canvas.create_line(PAD, y, PAD + COLS*CELL, y, fill=GRID_CLR)
        for c in range(COLS + 1):
            x = PAD + c * CELL
            self.canvas.create_line(x, PAD, x, PAD + ROWS*CELL, fill=GRID_CLR)
        for r in range(ROWS):
            for c in range(COLS):
                self._draw_cell(r, c)

    def _draw_cell(self, r, c):
        x0, y0, x1, y1 = cell_rect(r, c)
        tag = f"cell_{r}_{c}"
        self.canvas.delete(tag)

        is_bfs  = "BFS" in self.algo_var.get()
        v_color = VISITED_CLR if is_bfs else DFS_VISITED
        p_color = PATH_SOL    if is_bfs else DFS_PATH
        cell    = (r, c)

        if   cell == self.start:
            fill = START_CLR
        elif cell == self.end:
            fill = END_CLR
        elif cell in self.path_set and cell not in (self.start, self.end):
            fill = p_color
        elif cell in self.visited_set and cell not in (self.start, self.end):
            fill = v_color
        elif self.grid[r][c] == 1:
            fill = WALL_FILL
        else:
            fill = PATH_CLR

        outline = WALL_CLR if self.grid[r][c] == 1 else GRID_CLR
        self.canvas.create_rectangle(x0, y0, x1, y1,
                                     fill=fill, outline=outline, tags=tag)
        cx, cy = (x0+x1)//2, (y0+y1)//2
        if cell == self.start:
            self.canvas.create_text(cx, cy, text="S", fill="#fff",
                                    font=("Courier", 10, "bold"), tags=tag)
        elif cell == self.end:
            self.canvas.create_text(cx, cy, text="E", fill="#fff",
                                    font=("Courier", 10, "bold"), tags=tag)

    # ──────────────────────────────────────────────────────────────────────────
    # Random Maze Generator  (recursive-backtracker / DFS carver)
    # ──────────────────────────────────────────────────────────────────────────
    def _generate_maze(self):
        """
        Recursive backtracker on a (ROWS//2) × (COLS//2) logical grid.
        Every logical cell maps to a 2×2 block; walls between cells are
        the odd-indexed rows/columns.  Guarantees a perfect maze
        (exactly one path between any two cells → always solvable).
        """
        if self.solving:
            return
        self._clear_solution()

        # Start with all walls
        grid = [[1] * COLS for _ in range(ROWS)]

        LR = ROWS // 2   # logical rows
        LC = COLS // 2   # logical cols

        def carve(lr, lc):
            # Mark logical cell as open
            grid[lr * 2][lc * 2] = 0
            dirs = [(0, 1), (0, -1), (1, 0), (-1, 0)]
            random.shuffle(dirs)
            for dr, dc in dirs:
                nlr, nlc = lr + dr, lc + dc
                if 0 <= nlr < LR and 0 <= nlc < LC:
                    wr, wc = lr * 2 + dr, lc * 2 + dc   # wall cell
                    nr, nc = nlr * 2, nlc * 2            # neighbour cell
                    if grid[nr][nc] == 1:                # not yet visited
                        grid[wr][wc] = 0                 # knock down wall
                        carve(nlr, nlc)

        # Use iterative DFS to avoid Python recursion limit on large grids
        def carve_iterative(start_lr, start_lc):
            grid[start_lr * 2][start_lc * 2] = 0
            stack = [(start_lr, start_lc)]
            while stack:
                lr, lc = stack[-1]
                dirs = [(0,1),(0,-1),(1,0),(-1,0)]
                random.shuffle(dirs)
                moved = False
                for dr, dc in dirs:
                    nlr, nlc = lr + dr, lc + dc
                    if 0 <= nlr < LR and 0 <= nlc < LC:
                        nr, nc = nlr * 2, nlc * 2
                        if grid[nr][nc] == 1:
                            wr, wc = lr*2 + dr, lc*2 + dc
                            grid[wr][wc] = 0
                            grid[nr][nc] = 0
                            stack.append((nlr, nlc))
                            moved = True
                            break
                if not moved:
                    stack.pop()

        carve_iterative(0, 0)

        self.grid  = grid
        self.start = (0, 0)
        self.end   = (ROWS - 1 if (ROWS-1) % 2 == 0 else ROWS - 2,
                      COLS - 1 if (COLS-1) % 2 == 0 else COLS - 2)
        # Always open start and end cells
        self.grid[self.start[0]][self.start[1]] = 0
        self.grid[self.end[0]][self.end[1]]     = 0

        self._draw_all()
        self._reset_stats()
        self.status.config(text="Maze generated! Click Solve to run the algorithm.")

    # ──────────────────────────────────────────────────────────────────────────
    # Animated BFS / DFS solver
    # ──────────────────────────────────────────────────────────────────────────
    def _start_solve(self):
        if self.solving:
            return
        self._clear_solution()
        self._reset_stats()

        start, end = self.start, self.end
        if self.grid[start[0]][start[1]] == 1 or self.grid[end[0]][end[1]] == 1:
            messagebox.showwarning("Blocked", "Start or End is inside a wall.")
            return

        is_bfs = "BFS" in self.algo_var.get()
        algo   = "BFS" if is_bfs else "DFS"

        parent = {start: None}
        if is_bfs:
            frontier = deque([start])
            pop_fn   = frontier.popleft
            push_fn  = frontier.append
        else:
            frontier = [start]
            pop_fn   = frontier.pop
            push_fn  = frontier.append

        self.solving  = True
        self._t_start = time.perf_counter()
        step_count    = [0]
        found         = [False]

        def step():
            if not frontier or not self.solving:
                if not found[0]:
                    elapsed = time.perf_counter() - self._t_start
                    self.solving = False
                    self._set_stat("nodes", step_count[0])
                    self._set_stat("time",  f"{elapsed*1000:.1f}ms")
                    self.status.config(text="No path exists.")
                return

            cur = pop_fn()
            r, c = cur

            if cur == end:
                found[0]     = True
                self.solving = False
                elapsed      = time.perf_counter() - self._t_start
                self._set_stat("nodes", step_count[0])
                self._set_stat("time",  f"{elapsed*1000:.1f}ms")
                self._animate_path(parent, end, algo)
                return

            for dr, dc in ((-1,0),(1,0),(0,-1),(0,1)):
                nr, nc = r+dr, c+dc
                nb = (nr, nc)
                if (0 <= nr < ROWS and 0 <= nc < COLS
                        and nb not in parent
                        and self.grid[nr][nc] == 0):
                    parent[nb] = cur
                    push_fn(nb)

            if cur not in (self.start, self.end):
                self.visited_set.add(cur)
                self._draw_cell(r, c)

            step_count[0] += 1
            self._set_stat("nodes", step_count[0])
            self.status.config(text=f"{algo}: {step_count[0]} cells visited…")

            delay = max(1, 210 - self.speed_var.get())
            self._anim_id = self.root.after(delay, step)

        step()

    def _animate_path(self, parent, end, algo):
        node    = end
        ordered = []
        while node is not None:
            ordered.append(node)
            node = parent[node]
        ordered.reverse()

        self.path_set = set(ordered)
        path_len      = len(ordered) - 1
        self._set_stat("path", path_len)

        def flash(i=0):
            if i < len(ordered):
                self._draw_cell(*ordered[i])
                self.root.after(22, lambda: flash(i + 1))
            else:
                self.status.config(
                    text=(f"{algo} done!  "
                          f"Visited {len(self.visited_set)} nodes  |  "
                          f"Path: {path_len} steps"))

        flash()

    def _stop_solve(self):
        if self._anim_id:
            self.root.after_cancel(self._anim_id)
            self._anim_id = None
        self.solving = False
        self.status.config(text="Stopped.")

    def _clear_solution(self):
        self._stop_solve()
        self.visited_set.clear()
        self.path_set.clear()

    # ──────────────────────────────────────────────────────────────────────────
    # Utilities
    # ──────────────────────────────────────────────────────────────────────────
    def _clear_walls(self):
        self._clear_solution()
        self.grid = [[0]*COLS for _ in range(ROWS)]
        self._draw_all()
        self._reset_stats()
        self.status.config(text="Walls cleared.")

    def _reset(self):
        self._clear_solution()
        self.grid  = [[0]*COLS for _ in range(ROWS)]
        self.start = (0, 0)
        self.end   = (ROWS-1, COLS-1)
        self._draw_all()
        self._reset_stats()
        self.status.config(text="Maze reset.")

    def _export(self):
        p = filedialog.asksaveasfilename(defaultextension=".json",
                                          filetypes=[("JSON","*.json")])
        if not p:
            return
        with open(p, "w") as f:
            json.dump({"grid": self.grid, "start": list(self.start),
                       "end": list(self.end)}, f)
        self.status.config(text="Exported.")

    def _import(self):
        p = filedialog.askopenfilename(filetypes=[("JSON","*.json")])
        if not p:
            return
        try:
            with open(p) as f:
                data = json.load(f)
            self.grid  = data["grid"]
            self.start = tuple(data["start"])
            self.end   = tuple(data["end"])
            self._clear_solution()
            self._draw_all()
            self._reset_stats()
            self.status.config(text="Imported.")
        except Exception as ex:
            messagebox.showerror("Error", str(ex))


# ── Entry ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    root = tk.Tk()
    MazeEditor(root)
    root.mainloop()
