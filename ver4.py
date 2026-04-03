import tkinter as tk
from tkinter import messagebox, filedialog
import time
import threading
import json
import random
import math
from collections import deque

# --- 常量定义 ---
CELL_GROUND = 0
CELL_HIGH = 1
CELL_ENTRANCE = 2
CELL_EXIT = 3
CELL_PATH = 4
CELL_SHELF = 5
CELL_OBSTACLE = 6

COLORS = {
    CELL_GROUND: "#FFFFFF",  # 地面 (白色)
    CELL_HIGH: "#808080",  # 高台 (灰色)
    CELL_ENTRANCE: "#32CD32",  # 入口 (绿色)
    CELL_EXIT: "#FF4500",  # 出口 (橙红)
    CELL_PATH: "#FFD700",  # 顾客路径 (金色)
    CELL_SHELF: "#1E90FF",  # 普通货架 (蓝色)
    CELL_OBSTACLE: "#8B4513"  # 装饰物/障碍物 (棕色)
}

# 宝石颜色标识 (绘制在货架上)
GEM_COLORS = {
    '8_face': '#8A2BE2',  # 紫色
    '4_face': '#FF1493',  # 粉色
    '2_face': '#00FA9A',  # 春绿
    '1_face': '#1E90FF'  # 默认蓝
}


class SupermarketSolverApp:
    def __init__(self, root):
        self.root = root
        self.root.title("超市最优布局求解器 - b站零号稳态二极管")
        self.root.geometry("850x750")

        self.rows = 15  # 竖
        self.cols = 19  # 横
        self.cell_size = 40
        self.grid = [[CELL_GROUND for _ in range(self.cols)] for _ in range(self.rows)]

        # 默认布局设置
        self.init_default_layout()

        self.current_tool = tk.IntVar(value=CELL_HIGH)
        self.use_multi_gems = tk.BooleanVar(value=True)
        
        # 货架尺寸开关
        self.allow_1x1 = tk.BooleanVar(value=True)
        self.allow_1x2 = tk.BooleanVar(value=True)
        self.allow_2x2 = tk.BooleanVar(value=True)
        
        self.sim_time_var = tk.StringVar(value="60")  # 默认自定义60秒
        self.is_solving = False
        self.stop_requested = False
        
        # 补回遗漏的变量初始化
        self.best_solution_grid = None
        self.best_gem_map = {}
        self.best_placed_shapes = []
        self.best_path_sales = {} # 记录每个路径格子贡献了多少面销量

        self.setup_ui()
        self.draw_grid()

    def init_default_layout(self):
        """按照要求初始化默认的入口和出口位置"""
        self.grid = [[CELL_GROUND for _ in range(self.cols)] for _ in range(self.rows)]
        if 5 < self.rows and 5 < self.cols:
            self.grid[0][6] = CELL_ENTRANCE
            self.grid[5][0] = CELL_HIGH
            self.grid[5][1] = CELL_EXIT

    def setup_ui(self):
        # 左侧控制面板
        control_frame = tk.Frame(self.root, width=250, padx=10, pady=10)
        control_frame.pack(side=tk.LEFT, fill=tk.Y)

        tk.Label(control_frame, text="工具选择:", font=("Arial", 12, "bold")).pack(anchor=tk.W, pady=(0, 5))
        tools = [
            ("入口 (起点)", CELL_ENTRANCE),
            ("出口 (终点)", CELL_EXIT),
            ("高台 (阻挡)", CELL_HIGH),
            ("地面 (橡皮擦)", CELL_GROUND)
        ]
        for text, val in tools:
            tk.Radiobutton(control_frame, text=text, variable=self.current_tool, value=val, font=("Arial", 11)).pack(
                anchor=tk.W)

        tk.Frame(control_frame, height=2, bd=1, relief=tk.SUNKEN).pack(fill=tk.X, pady=10)

        # 布局大小调整
        size_frame = tk.Frame(control_frame)
        size_frame.pack(fill=tk.X, pady=5)
        tk.Label(size_frame, text="行:").pack(side=tk.LEFT)
        self.row_var = tk.StringVar(value=str(self.rows))
        tk.Entry(size_frame, textvariable=self.row_var, width=3).pack(side=tk.LEFT, padx=2)
        tk.Label(size_frame, text="列:").pack(side=tk.LEFT)
        self.col_var = tk.StringVar(value=str(self.cols))
        tk.Entry(size_frame, textvariable=self.col_var, width=3).pack(side=tk.LEFT, padx=2)
        tk.Button(size_frame, text="修改大小", command=self.resize_grid).pack(side=tk.RIGHT)

        # 导入导出
        io_frame = tk.Frame(control_frame)
        io_frame.pack(fill=tk.X, pady=5)
        tk.Button(io_frame, text="导出布局", command=self.export_layout).pack(side=tk.LEFT, expand=True, fill=tk.X,
                                                                              padx=(0, 2))
        tk.Button(io_frame, text="导入布局", command=self.import_layout).pack(side=tk.RIGHT, expand=True, fill=tk.X,
                                                                              padx=(2, 0))

        tk.Frame(control_frame, height=2, bd=1, relief=tk.SUNKEN).pack(fill=tk.X, pady=5)

        tk.Label(control_frame, text="允许采购的货架尺寸:", font=("Arial", 11, "bold")).pack(anchor=tk.W)
        tk.Checkbutton(control_frame, text="允许 1x1 货架", variable=self.allow_1x1).pack(anchor=tk.W)
        tk.Checkbutton(control_frame, text="允许 1x2 货架", variable=self.allow_1x2).pack(anchor=tk.W)
        tk.Checkbutton(control_frame, text="允许 2x2 货架", variable=self.allow_2x2).pack(anchor=tk.W)
        tk.Label(control_frame, text="(多面宝石暂时只支持1x1的，后续再优化大货架)", font=("Arial", 9), fg="gray").pack(anchor=tk.W)

        tk.Frame(control_frame, height=2, bd=1, relief=tk.SUNKEN).pack(fill=tk.X, pady=5)

        tk.Checkbutton(control_frame, text="使用多面宝石", variable=self.use_multi_gems,
                       font=("Arial", 11, "bold")).pack(anchor=tk.W)

        tk.Frame(control_frame, height=2, bd=1, relief=tk.SUNKEN).pack(fill=tk.X, pady=5)

        # 自定义时间输入框
        time_frame = tk.Frame(control_frame)
        time_frame.pack(fill=tk.X, pady=5)
        tk.Label(time_frame, text="推演时间(秒):", font=("Arial", 11, "bold")).pack(side=tk.LEFT)
        tk.Entry(time_frame, textvariable=self.sim_time_var, width=6, font=("Arial", 11)).pack(side=tk.LEFT, padx=5)

        tk.Frame(control_frame, height=2, bd=1, relief=tk.SUNKEN).pack(fill=tk.X, pady=5)

        # 求解与中断按钮
        self.solve_btn = tk.Button(control_frame, text="▶ 开始求最优解\n(贪心阻断+模拟退火)", bg="#4CAF50", fg="white",
                                   font=("Arial", 11, "bold"), command=self.start_solving)
        self.solve_btn.pack(fill=tk.X, pady=5)

        self.stop_btn = tk.Button(control_frame, text="⏹ 强制结束并输出最优", bg="#f44336", fg="white",
                                  font=("Arial", 11, "bold"), command=self.force_stop, state=tk.DISABLED)
        self.stop_btn.pack(fill=tk.X, pady=5)

        self.reset_btn = tk.Button(control_frame, text="重置网格", command=self.reset_grid)
        self.reset_btn.pack(fill=tk.X, pady=5)

        self.status_var = tk.StringVar(value="就绪")
        tk.Label(control_frame, textvariable=self.status_var, fg="blue", font=("Arial", 10)).pack(pady=2)

        # 结果显示区
        tk.Label(control_frame, text="求解结果:", font=("Arial", 12, "bold")).pack(anchor=tk.W, pady=(2, 0))
        self.result_text = tk.Text(control_frame, height=12, width=30, font=("Arial", 10))
        self.result_text.pack(fill=tk.BOTH, expand=True)

        # 右侧画布
        self.canvas_frame = tk.Frame(self.root)
        self.canvas_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.canvas = tk.Canvas(self.canvas_frame, bg="white")
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # 绑定鼠标事件进行绘制
        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<B1-Motion>", self.on_drag)

    def draw_grid(self):
        self.canvas.delete("all")
        width = self.cols * self.cell_size
        height = self.rows * self.cell_size

        for r in range(self.rows):
            for c in range(self.cols):
                x1 = c * self.cell_size
                y1 = r * self.cell_size
                x2 = x1 + self.cell_size
                y2 = y1 + self.cell_size

                cell_val = self.grid[r][c]
                color = COLORS.get(cell_val, "#FFFFFF")

                # 如果是货架且有宝石数据，使用宝石颜色
                if cell_val == CELL_SHELF and (r, c) in self.best_gem_map:
                    color = GEM_COLORS.get(self.best_gem_map[(r, c)], color)

                self.canvas.create_rectangle(x1, y1, x2, y2, fill=color, outline="#CCCCCC")

                # 绘制文字标识
                text = ""
                if cell_val == CELL_ENTRANCE:
                    text = "入"
                elif cell_val == CELL_EXIT:
                    text = "出"
                elif cell_val == CELL_HIGH:
                    text = "高"
                elif cell_val == CELL_OBSTACLE:
                    text = "障"
                elif cell_val == CELL_SHELF and (r, c) in self.best_gem_map:
                    gem = self.best_gem_map[(r, c)]
                    if gem == '8_face':
                        text = "8面"
                    elif gem == '4_face':
                        text = "4面"
                    elif gem == '2_face':
                        text = "2面"
                
                # 如果是路径，并且贡献了销售面，在黄色框上打印数字
                if cell_val == CELL_PATH:
                    sales = self.best_path_sales.get((r, c), 0)
                    if sales > 0:
                        text = str(sales)

                if text:
                    self.canvas.create_text(x1 + self.cell_size / 2, y1 + self.cell_size / 2, text=text,
                                            font=("Arial", 12, "bold"))
                                            
        # 绘制连体货架的加粗黑框，明确显示 1x2 和 2x2 的组合边界
        if self.best_placed_shapes:
            for pts, stype in self.best_placed_shapes:
                if stype in ['1x2', '2x2']:
                    min_r = min(p[0] for p in pts)
                    max_r = max(p[0] for p in pts)
                    min_c = min(p[1] for p in pts)
                    max_c = max(p[1] for p in pts)
                    
                    x1 = min_c * self.cell_size
                    y1 = min_r * self.cell_size
                    x2 = (max_c + 1) * self.cell_size
                    y2 = (max_r + 1) * self.cell_size
                    
                    self.canvas.create_rectangle(x1+2, y1+2, x2-2, y2-2, outline="#000000", width=3)

    def paint_cell(self, event):
        if self.is_solving: return
        c = event.x // self.cell_size
        r = event.y // self.cell_size
        if 0 <= r < self.rows and 0 <= c < self.cols:
            val = self.current_tool.get()
            # 简单校验：不能覆盖已有的出入口，除非使用的是橡皮擦
            if self.grid[r][c] in [CELL_ENTRANCE, CELL_EXIT] and val not in [CELL_GROUND, CELL_ENTRANCE, CELL_EXIT]:
                return
            self.grid[r][c] = val
            self.best_gem_map.clear()
            self.best_placed_shapes = []
            self.best_path_sales = {}
            self.draw_grid()

    def on_click(self, event):
        self.paint_cell(event)

    def on_drag(self, event):
        self.paint_cell(event)

    def reset_grid(self):
        if self.is_solving: return
        self.init_default_layout()
        self.best_gem_map.clear()
        self.best_placed_shapes = []
        self.best_path_sales = {}
        self.draw_grid()
        self.result_text.delete(1.0, tk.END)

    def clear_solution(self):
        """清除之前的求解结果（路径、货架、障碍物），只保留高台、入出口、地面"""
        self.best_gem_map.clear()
        self.best_placed_shapes = []
        self.best_path_sales = {}
        for r in range(self.rows):
            for c in range(self.cols):
                if self.grid[r][c] in [CELL_PATH, CELL_SHELF, CELL_OBSTACLE]:
                    self.grid[r][c] = CELL_GROUND
        self.draw_grid()

    def resize_grid(self):
        if self.is_solving: return
        try:
            new_r = int(self.row_var.get())
            new_c = int(self.col_var.get())
            if new_r < 5 or new_c < 5 or new_r > 50 or new_c > 50:
                messagebox.showwarning("提示", "行列数建议在 5 到 50 之间")
                return
            # 创建新网格并复制旧数据
            new_grid = [[CELL_GROUND for _ in range(new_c)] for _ in range(new_r)]
            for r in range(min(self.rows, new_r)):
                for c in range(min(self.cols, new_c)):
                    new_grid[r][c] = self.grid[r][c]
            self.rows = new_r
            self.cols = new_c
            self.grid = new_grid
            self.clear_solution()
        except ValueError:
            messagebox.showerror("错误", "请输入有效的数字")

    def export_layout(self):
        if self.is_solving: return
        self.clear_solution()  
        filepath = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON files", "*.json")],
                                                initialfile="supermarket_layout.json")
        if filepath:
            data = {
                "rows": self.rows,
                "cols": self.cols,
                "grid": self.grid
            }
            try:
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(data, f)
                messagebox.showinfo("成功", "布局已导出！")
            except Exception as e:
                messagebox.showerror("错误", f"导出失败: {e}")

    def import_layout(self):
        if self.is_solving: return
        filepath = filedialog.askopenfilename(filetypes=[("JSON files", "*.json")])
        if filepath:
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.rows = data.get("rows", 15)
                self.cols = data.get("cols", 19)
                self.grid = data.get("grid", [])
                self.row_var.set(str(self.rows))
                self.col_var.set(str(self.cols))
                self.clear_solution()
            except Exception as e:
                messagebox.showerror("错误", f"导入失败: {e}")

    def start_solving(self):
        if self.is_solving: return

        try:
            sim_time = float(self.sim_time_var.get())
            if sim_time <= 0: raise ValueError
        except ValueError:
            messagebox.showwarning("错误", "请输入大于0的有效数字作为推演时间！")
            return
            
        if not self.allow_1x1.get() and not self.allow_1x2.get() and not self.allow_2x2.get():
            messagebox.showwarning("警告", "您必须在左侧勾选至少允许一种货架尺寸！")
            return

        self.clear_solution()

        entrances = [(r, c) for r in range(self.rows) for c in range(self.cols) if self.grid[r][c] == CELL_ENTRANCE]
        exits = [(r, c) for r in range(self.rows) for c in range(self.cols) if self.grid[r][c] == CELL_EXIT]

        if not entrances or not exits:
            messagebox.showwarning("提示", "请在画布上至少绘制一个入口和一个出口！")
            return

        # 固化配置字典，避免后台线程频繁读取Tkinter引发卡顿
        config = {
            'allow_1x1': self.allow_1x1.get(),
            'allow_1x2': self.allow_1x2.get(),
            'allow_2x2': self.allow_2x2.get(),
            'use_multi_gems': self.use_multi_gems.get()
        }

        self.is_solving = True
        self.stop_requested = False
        self.solve_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.result_text.delete(1.0, tk.END)
        self.status_var.set("正在通过阻断推演与模拟退火求解中...")

        start_pos = entrances[0]
        t = threading.Thread(target=self.solve_algorithm, args=(start_pos, exits, sim_time, config), daemon=True)
        t.start()

    def force_stop(self):
        if self.is_solving:
            self.stop_requested = True
            self.status_var.set("正在停止，请等待当前迭代完成...")

    def _bfs_shortest_path(self, start, targets, blocked):
        if start in targets:
            return (0, [start])

        visited = [[False] * self.cols for _ in range(self.rows)]
        parent = {}
        visited[start[0]][start[1]] = True
        q = deque([start])

        while q:
            r, c = q.popleft()
            for dr, dc in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
                nr, nc = r + dr, c + dc
                if 0 <= nr < self.rows and 0 <= nc < self.cols and not visited[nr][nc]:
                    cell = self.grid[nr][nc]
                    pos = (nr, nc)
                    if (cell == CELL_GROUND and pos not in blocked) or cell == CELL_ENTRANCE or cell == CELL_EXIT:
                        visited[nr][nc] = True
                        parent[pos] = (r, c)
                        if pos in targets:
                            path = []
                            cur = pos
                            while cur is not None:
                                path.append(cur)
                                cur = parent.get(cur)
                            path.reverse()
                            return (len(path) - 1, path)
                        q.append(pos)

        return (None, [])

    def _is_connected(self, start, targets, blocked):
        visited = [[False] * self.cols for _ in range(self.rows)]
        visited[start[0]][start[1]] = True
        q = deque([start])

        while q:
            r, c = q.popleft()
            for dr, dc in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
                nr, nc = r + dr, c + dc
                if 0 <= nr < self.rows and 0 <= nc < self.cols and not visited[nr][nc]:
                    cell = self.grid[nr][nc]
                    pos = (nr, nc)
                    if (cell == CELL_GROUND and pos not in blocked) or cell == CELL_ENTRANCE or cell == CELL_EXIT:
                        if pos in targets:
                            return True
                        visited[nr][nc] = True
                        q.append(pos)
        return False

    def _compute_bottleneck_score(self, cell, start, targets, blocked, current_dist):
        new_blocked = blocked | {cell}
        if not self._is_connected(start, targets, new_blocked):
            return -1  
        new_dist, _ = self._bfs_shortest_path(start, targets, new_blocked)
        if new_dist is None:
            return -1
        return new_dist - current_dist

    def solve_algorithm(self, start_pos, exits, sim_time, config):
        end_time = time.time() + sim_time
        target_set = set(exits)

        ground_cells = set()
        for r in range(self.rows):
            for c in range(self.cols):
                if self.grid[r][c] == CELL_GROUND:
                    ground_cells.add((r, c))

        protected = {start_pos} | target_set

        # ===== Phase 1: 贪心初始化 =====
        blocked = set()  
        phase1_iterations = 0

        dist, path = self._bfs_shortest_path(start_pos, target_set, blocked)
        if dist is None:
            self.root.after(0, self.finish_solving, (-1, -999999), [], {}, {}, [], {}, {}, 0, False)
            return

        best_dist = dist
        best_blocked = set(blocked)
        last_ui_update = time.time()

        while time.time() < end_time and not self.stop_requested:
            dist, path = self._bfs_shortest_path(start_pos, target_set, blocked)
            if dist is None:
                break

            if dist > best_dist:
                best_dist = dist
                best_blocked = set(blocked)

            candidates = []
            for cell in path:
                if cell in protected or cell not in ground_cells or cell in blocked:
                    continue
                gain = self._compute_bottleneck_score(cell, start_pos, target_set, blocked, dist)
                if gain > 0:
                    candidates.append((gain, cell))

            if not candidates:
                break

            candidates.sort(key=lambda x: -x[0])
            best_cell = candidates[0][1]
            blocked.add(best_cell)
            phase1_iterations += 1

            if time.time() - last_ui_update > 0.5:
                cur_dist, _ = self._bfs_shortest_path(start_pos, target_set, blocked)
                self.root.after(0, self.status_var.set,
                                f"Phase 1 贪心构造中... 已放置 {len(blocked)} 个阻断障碍，当前路径长度: {cur_dist} 步")
                last_ui_update = time.time()

        # 整理 Phase 1 的结果
        final_dist, final_path = self._bfs_shortest_path(start_pos, target_set, best_blocked)
        if final_dist is None:
            final_dist = best_dist
            _, final_path = self._bfs_shortest_path(start_pos, target_set, best_blocked)

        path_set = set(final_path) if final_path else set()
        
        # evaluation拆包加入了 path_sales_counts 以实现格子销量显示
        base_eval = self.evaluate_layout(path_set, best_blocked, config)
        base_score_tuple, base_gem_stats, base_local_gem_map, base_placed_shapes, base_shape_counts, base_path_sales = base_eval

        current_blocked = set(best_blocked)
        current_dist_val = final_dist
        current_score_val = base_score_tuple[0]
        
        # 【目标函数逆转】：让 AI 把“总销量(score)”作为绝对核心目标，而将路径长度降级为辅助打分。
        # AI 会为了塞下更多的连体货架，主动把路修得横平竖直。
        current_obj_val = current_score_val * 1000 + current_dist_val
        
        sa_best_obj = current_obj_val
        sa_best_eval = (base_score_tuple, base_gem_stats, base_local_gem_map, base_placed_shapes, base_shape_counts, base_path_sales, final_path)

        temperature = 1000.0  # 放大适应度后，提高初始温度
        cooling_rate = 0.9995
        sa_iterations = 0

        free_ground = ground_cells - current_blocked - protected

        # ===== Phase 2: 模拟退火优化 =====
        while time.time() < end_time and not self.stop_requested:
            sa_iterations += 1
            op = random.random()

            if op < 0.4 and current_blocked:
                remove_cell = random.choice(list(current_blocked))
                new_blocked = current_blocked - {remove_cell}
            elif op < 0.8 and free_ground:
                add_cell = random.choice(list(free_ground))
                new_blocked = current_blocked | {add_cell}
            elif current_blocked and free_ground:
                remove_cell = random.choice(list(current_blocked))
                add_cell = random.choice(list(free_ground))
                new_blocked = (current_blocked - {remove_cell}) | {add_cell}
            else:
                continue

            if not self._is_connected(start_pos, target_set, new_blocked):
                continue

            new_dist, p_path = self._bfs_shortest_path(start_pos, target_set, new_blocked)
            if new_dist is None:
                continue

            # 每一步都在内部高速进行 2D Pack，实时算出新布局能放多少大货架
            p_path_set = set(p_path)
            new_eval = self.evaluate_layout(p_path_set, new_blocked, config)
            score_tuple, gem_stats, local_gem_map, placed_shapes, shape_counts, path_sales = new_eval
            new_score = score_tuple[0]
            new_obj_val = new_score * 1000 + new_dist

            delta = new_obj_val - current_obj_val
            if delta > 0 or (temperature > 0.01 and random.random() < math.exp(delta / temperature)):
                current_blocked = new_blocked
                current_dist_val = new_dist
                current_score_val = new_score
                current_obj_val = new_obj_val
                free_ground = ground_cells - current_blocked - protected

                if current_obj_val > sa_best_obj:
                    sa_best_obj = current_obj_val
                    sa_best_eval = (score_tuple, gem_stats, local_gem_map, placed_shapes, shape_counts, path_sales, p_path)

            temperature *= cooling_rate

            if sa_iterations % 200 == 0 and time.time() - last_ui_update > 0.5:
                self.root.after(0, self.status_var.set,
                                f"Phase 2 模拟退火中... 迭代 {sa_iterations}，当前最高销量: {sa_best_eval[0][0]}面 (步数:{len(sa_best_eval[6])})")
                last_ui_update = time.time()

        # ===== 最终结果提取 =====
        best_score_tuple, best_gem_stats, best_local_gem_map, best_placed_shapes, best_shape_counts, best_path_sales, final_path = sa_best_eval
        is_forced_stop = self.stop_requested
        total_iterations = phase1_iterations + sa_iterations
        
        self.root.after(0, self.finish_solving, best_score_tuple, list(final_path) if final_path else [],
                        best_gem_stats, best_local_gem_map, best_placed_shapes, best_shape_counts, best_path_sales, total_iterations, is_forced_stop)

    def evaluate_layout(self, path_set, blocked_set, config):
        ground_set = set()
        for r in range(self.rows):
            for c in range(self.cols):
                if self.grid[r][c] == CELL_GROUND and (r, c) not in path_set:
                    ground_set.add((r, c))

        shapes = []

        def get_adj_stats(pts, stype):
            top_paths = []
            bottom_paths = []
            left_paths = []
            right_paths = []
            corner_paths = []

            min_r = min(p[0] for p in pts)
            max_r = max(p[0] for p in pts)
            min_c = min(p[1] for p in pts)
            max_c = max(p[1] for p in pts)

            for r, c in pts:
                for dr, dc, side in [(-1, 0, 'top'), (1, 0, 'bottom'), (0, -1, 'left'), (0, 1, 'right')]:
                    nr, nc = r + dr, c + dc
                    # 必须是货架整体外部的格子才算数
                    if (nr, nc) not in pts and 0 <= nr < self.rows and 0 <= nc < self.cols:
                        if (nr, nc) in path_set or self.grid[nr][nc] in [CELL_ENTRANCE, CELL_EXIT]:
                            if side == 'top': top_paths.append((nr, nc))
                            elif side == 'bottom': bottom_paths.append((nr, nc))
                            elif side == 'left': left_paths.append((nr, nc))
                            elif side == 'right': right_paths.append((nr, nc))

            corners = [(min_r - 1, min_c - 1), (min_r - 1, max_c + 1), (max_r + 1, min_c - 1), (max_r + 1, max_c + 1)]
            for nr, nc in corners:
                if 0 <= nr < self.rows and 0 <= nc < self.cols:
                    if (nr, nc) in path_set or self.grid[nr][nc] in [CELL_ENTRANCE, CELL_EXIT]:
                        corner_paths.append((nr, nc))

            c_adj_top = len(top_paths)
            c_adj_bottom = len(bottom_paths)
            c_adj_left = len(left_paths)
            c_adj_right = len(right_paths)

            c_adj = c_adj_top + c_adj_bottom + c_adj_left + c_adj_right
            t_adj = c_adj + len(corner_paths)

            max_t = {'1x1': 8, '1x2': 10, '2x2': 12}[stype]
            max_c = {'1x1': 4, '1x2': 6, '2x2': 8}[stype]

            # ---------------------------------------------------------
            # 核心修正：在不使用宝石时，1x2货架只有长边可作为单一销售正面！
            # ---------------------------------------------------------
            if stype == '1x1' or stype == '2x2':
                candidates = [
                    (c_adj_top, top_paths),
                    (c_adj_bottom, bottom_paths),
                    (c_adj_left, left_paths),
                    (c_adj_right, right_paths)
                ]
            elif stype == '1x2':
                if min_r == max_r:  # 横向 1x2，长边是上下，物理屏蔽左右短边
                    candidates = [
                        (c_adj_top, top_paths),
                        (c_adj_bottom, bottom_paths)
                    ]
                else:               # 竖向 1x2，长边是左右，物理屏蔽上下短边
                    candidates = [
                        (c_adj_left, left_paths),
                        (c_adj_right, right_paths)
                    ]

            candidates.sort(key=lambda x: x[0], reverse=True)
            best_f = candidates[0][0]
            active_paths = candidates[0][1]
            best_g = '1_face' if best_f > 0 else None

            if config['use_multi_gems']:
                if t_adj >= max_t * 0.75 and t_adj > best_f:
                    best_f = t_adj
                    best_g = '8_face'
                    active_paths = top_paths + bottom_paths + left_paths + right_paths + corner_paths
                elif c_adj >= max_c * 0.75 and c_adj > best_f:
                    best_f = c_adj
                    best_g = '4_face'
                    active_paths = top_paths + bottom_paths + left_paths + right_paths
                else:
                    gem_2_v = c_adj_top + c_adj_bottom
                    gem_2_h = c_adj_left + c_adj_right
                    if gem_2_v >= gem_2_h and gem_2_v > best_f and c_adj_top > 0 and c_adj_bottom > 0:
                        best_f = gem_2_v
                        best_g = '2_face'
                        active_paths = top_paths + bottom_paths
                    elif gem_2_h > best_f and c_adj_left > 0 and c_adj_right > 0:
                        best_f = gem_2_h
                        best_g = '2_face'
                        active_paths = left_paths + right_paths

            return best_f, best_g, active_paths

        # 扫描允许放入的 2x2 货架
        if config['allow_2x2']:
            for r in range(self.rows - 1):
                for c in range(self.cols - 1):
                    pts = [(r, c), (r+1, c), (r, c+1), (r+1, c+1)]
                    if all(p in ground_set for p in pts):
                        score, gem, paths = get_adj_stats(pts, '2x2')
                        shapes.append((score, pts, '2x2', gem, paths))
        
        # 扫描允许放入的 1x2 货架（横向和竖向）
        if config['allow_1x2']:
            for r in range(self.rows):
                for c in range(self.cols - 1):
                    pts = [(r, c), (r, c+1)]
                    if all(p in ground_set for p in pts):
                        score, gem, paths = get_adj_stats(pts, '1x2')
                        shapes.append((score, pts, '1x2', gem, paths))
            for r in range(self.rows - 1):
                for c in range(self.cols):
                    pts = [(r, c), (r+1, c)]
                    if all(p in ground_set for p in pts):
                        score, gem, paths = get_adj_stats(pts, '1x2')
                        shapes.append((score, pts, '1x2', gem, paths))

        # 扫描 1x1 货架
        if config['allow_1x1']:
            for p in ground_set:
                score, gem, paths = get_adj_stats([p], '1x1')
                shapes.append((score, [p], '1x1', gem, paths))

        # 贪心打包策略：
        # 优先填入“单位占地效率最高”的货架；如果效率相同(比如 1x1赚1面，1x2赚2面)，则优先使用体积更大的货架节省格子数。
        shapes.sort(key=lambda x: (x[0]/len(x[1]) if len(x[1])>0 else 0, len(x[1])), reverse=True)

        used = set()
        placed_shapes = []
        total_score = 0
        gem_stats = {'8_face': 0, '4_face': 0, '2_face': 0, '1_face': 0}
        local_gem_map = {}
        shape_counts = {'1x1': 0, '1x2': 0, '2x2': 0}
        path_sales_counts = {}  # 记录这套包裹方案下，每个路径格子提供了多少次售卖触碰

        for score, pts, stype, gem, active_paths in shapes:
            if not any(p in used for p in pts):
                if score > 0:  # 只摆放能赚到销量的货架
                    placed_shapes.append((pts, stype))
                    shape_counts[stype] += 1
                    total_score += score
                    if gem:
                        gem_stats[gem] += 1
                        for p in pts:
                            local_gem_map[p] = gem
                    for p in pts:
                        used.add(p)
                    # 计入热力图
                    for path_cell in active_paths:
                        path_sales_counts[path_cell] = path_sales_counts.get(path_cell, 0) + 1

        num_obstacles = len(ground_set) - len(used)

        return (total_score, -num_obstacles), gem_stats, local_gem_map, placed_shapes, shape_counts, path_sales_counts

    def finish_solving(self, best_score_tuple, best_path, best_gem_stats, best_local_gem_map, best_placed_shapes, best_shape_counts, best_path_sales, sim_run, is_forced_stop):
        self.is_solving = False
        self.solve_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)

        if best_score_tuple[0] == -1:
            self.status_var.set("求解失败: 无法找到连通出入口的路径")
            messagebox.showwarning("提示", "当前高台或布局完全封堵了道路，顾客无法走到出口。")
            self.result_text.delete(1.0, tk.END)
            return

        best_score = best_score_tuple[0]
        num_obstacles = -best_score_tuple[1]

        # 更新网格为最优解状态
        self.best_gem_map = best_local_gem_map
        self.best_placed_shapes = best_placed_shapes
        self.best_path_sales = best_path_sales
        
        for r in range(self.rows):
            for c in range(self.cols):
                if self.grid[r][c] == CELL_GROUND:
                    if (r, c) in best_path:
                        self.grid[r][c] = CELL_PATH
                    elif (r, c) in best_local_gem_map:
                        self.grid[r][c] = CELL_SHELF
                    else:
                        self.grid[r][c] = CELL_OBSTACLE

        self.draw_grid()

        if is_forced_stop:
            self.status_var.set(f"已强制结束！提取了搜索到的 {sim_run} 条路线中的最强解")
        else:
            self.status_var.set(f"计算完成！在期限内成功进行了 {sim_run} 次结构退火演化")

        # 打印输出结果
        res = f"★★★ 寻路规划完成 ★★★\n\n"
        if is_forced_stop:
            res += f"状态: 用户强制终止\n"
        res += f"AI共执行了 {sim_run} 次贪心阻断与模拟退火\n\n"
        res += f"最大总接触面数 (销量): {best_score} 面\n\n"
        
        res += f"【连体货架采购统计】\n"
        if self.allow_2x2.get():
            res += f"- 2x2 连体货架: {best_shape_counts.get('2x2', 0)} 个\n"
        if self.allow_1x2.get():
            res += f"- 1x2 连体货架: {best_shape_counts.get('1x2', 0)} 个\n"
        if self.allow_1x1.get():
            res += f"- 1x1 普通货架: {best_shape_counts.get('1x1', 0)} 个\n"
        res += "\n"
        
        res += f"【占用格子与宝石统计】\n"
        if self.use_multi_gems.get():
            res += f"- (8面规则)占地: {best_gem_stats.get('8_face', 0)} 格\n"
            res += f"- (4面规则)占地: {best_gem_stats.get('4_face', 0)} 格\n"
            res += f"- (2面规则)占地: {best_gem_stats.get('2_face', 0)} 格\n"
        res += f"- (单面售卖)占地: {best_gem_stats.get('1_face', 0)} 格\n\n"

        res += f"额外放置挡路障碍物(棕色): {num_obstacles} 个\n"

        self.result_text.delete(1.0, tk.END)
        self.result_text.insert(tk.END, res)


if __name__ == "__main__":
    root = tk.Tk()
    app = SupermarketSolverApp(root)
    root.mainloop()