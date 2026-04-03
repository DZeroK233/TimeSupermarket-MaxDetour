import tkinter as tk
from tkinter import messagebox, filedialog
import time
import threading
import json
import random
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
        self.root.title("超市最优布局求解器 - 深度回溯 DFS (可中断版)")
        self.root.geometry("850x700")

        self.rows = 15  # 竖
        self.cols = 19  # 横
        self.cell_size = 40
        self.grid = [[CELL_GROUND for _ in range(self.cols)] for _ in range(self.rows)]

        # 默认布局设置
        self.init_default_layout()

        self.current_tool = tk.IntVar(value=CELL_HIGH)
        self.use_multi_gems = tk.BooleanVar(value=True)
        self.sim_time_var = tk.StringVar(value="60")  # 默认自定义60秒
        self.is_solving = False
        self.stop_requested = False

        self.setup_ui()
        self.draw_grid()

    def init_default_layout(self):
        """按照要求初始化默认的入口和出口位置"""
        self.grid = [[CELL_GROUND for _ in range(self.cols)] for _ in range(self.rows)]
        if 5 < self.rows and 5 < self.cols:
            self.grid[0][6] = CELL_ENTRANCE
            self.grid[5][0] = CELL_EXIT
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

        tk.Frame(control_frame, height=2, bd=1, relief=tk.SUNKEN).pack(fill=tk.X, pady=10)

        tk.Checkbutton(control_frame, text="使用多面宝石", variable=self.use_multi_gems,
                       font=("Arial", 11, "bold")).pack(anchor=tk.W)
        tk.Label(control_frame, text="规则: 8面(≥6), 4面(≥3), 2面(前后)", font=("Arial", 9), fg="gray").pack(
            anchor=tk.W)

        tk.Frame(control_frame, height=2, bd=1, relief=tk.SUNKEN).pack(fill=tk.X, pady=10)

        # 新增：自定义时间输入框
        time_frame = tk.Frame(control_frame)
        time_frame.pack(fill=tk.X, pady=5)
        tk.Label(time_frame, text="推演时间(秒):", font=("Arial", 11, "bold")).pack(side=tk.LEFT)
        tk.Entry(time_frame, textvariable=self.sim_time_var, width=6, font=("Arial", 11)).pack(side=tk.LEFT, padx=5)

        tk.Frame(control_frame, height=2, bd=1, relief=tk.SUNKEN).pack(fill=tk.X, pady=10)

        # 求解与中断按钮
        self.solve_btn = tk.Button(control_frame, text="▶ 开始求最优解", bg="#4CAF50", fg="white",
                                   font=("Arial", 12, "bold"), command=self.start_solving)
        self.solve_btn.pack(fill=tk.X, pady=5)

        self.stop_btn = tk.Button(control_frame, text="⏹ 强制结束并输出最优", bg="#f44336", fg="white",
                                  font=("Arial", 12, "bold"), command=self.force_stop, state=tk.DISABLED)
        self.stop_btn.pack(fill=tk.X, pady=5)

        self.reset_btn = tk.Button(control_frame, text="重置网格", command=self.reset_grid)
        self.reset_btn.pack(fill=tk.X, pady=15)

        self.status_var = tk.StringVar(value="就绪")
        tk.Label(control_frame, textvariable=self.status_var, fg="blue", font=("Arial", 10)).pack(pady=5)

        # 结果显示区
        tk.Label(control_frame, text="求解结果:", font=("Arial", 12, "bold")).pack(anchor=tk.W, pady=(5, 0))
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

        # 结果数据
        self.best_solution_grid = None
        self.best_gem_map = {}

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

                if text:
                    self.canvas.create_text(x1 + self.cell_size / 2, y1 + self.cell_size / 2, text=text,
                                            font=("Arial", 10, "bold"))

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
            self.best_gem_map.clear()  # 清除历史结果
            self.draw_grid()

    def on_click(self, event):
        self.paint_cell(event)

    def on_drag(self, event):
        self.paint_cell(event)

    def reset_grid(self):
        if self.is_solving: return
        self.init_default_layout()
        self.best_gem_map.clear()
        self.draw_grid()
        self.result_text.delete(1.0, tk.END)

    def clear_solution(self):
        """清除之前的求解结果（路径、货架、障碍物），只保留高台、入出口、地面"""
        self.best_gem_map.clear()
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
        self.clear_solution()  # 导出前清理计算结果
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

        # 每次求解前，自动清除旧的求解结果
        self.clear_solution()

        # 验证是否包含至少一个入口和一个出口
        entrances = [(r, c) for r in range(self.rows) for c in range(self.cols) if self.grid[r][c] == CELL_ENTRANCE]
        exits = [(r, c) for r in range(self.rows) for c in range(self.cols) if self.grid[r][c] == CELL_EXIT]

        if not entrances or not exits:
            messagebox.showwarning("提示", "请在画布上至少绘制一个入口和一个出口！")
            return

        self.is_solving = True
        self.stop_requested = False
        self.solve_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.result_text.delete(1.0, tk.END)
        self.status_var.set("正在求解中...")

        start_pos = entrances[0]
        t = threading.Thread(target=self.solve_algorithm, args=(start_pos, exits, sim_time), daemon=True)
        t.start()

    def force_stop(self):
        if self.is_solving:
            self.stop_requested = True
            self.status_var.set("正在停止，请等待当前迭代完成...")

    #  核心算法：最大化最短路径 (Maximize Shortest Path by Obstacle Placement)
    #
    #  本算法将问题转化为：在空地格子上放置障碍物（货架），使得从入口S
    #  到出口T的BFS最短路径长度尽可能大，同时保证路径始终存在。
    #
    #  策略：
    #    Phase 1 - 贪心初始化：反复求当前最短路径，然后选路径上"最关键"
    #              的节点放障碍（不能放切断连通性的节点），迫使路径绕行。
    #    Phase 2 - 模拟退火优化：在贪心解基础上，随机交换障碍/空地，
    #              用退火概率接受劣解以跳出局部最优。
    # =====================================================================

    def _bfs_shortest_path(self, start, targets, blocked):
        """
        BFS求从start到targets中任一目标的最短路径。
        blocked: set，被障碍物占据的格子。
        返回: (距离, 路径列表) 或 (None, []) 如果不可达。
        路径列表包含从start到target的所有格子坐标。
        """
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
                    # 可通行：空地且不在blocked中，或者是入口/出口
                    if (cell == CELL_GROUND and pos not in blocked) or cell == CELL_ENTRANCE or cell == CELL_EXIT:
                        visited[nr][nc] = True
                        parent[pos] = (r, c)
                        if pos in targets:
                            # 回溯路径
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
        """快速检查start能否到达targets中的任一目标"""
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
        """
        评估阻断cell后对最短路径的影响。
        返回增加的距离（越大越好）。如果阻断后不连通，返回 -1。
        """
        new_blocked = blocked | {cell}
        if not self._is_connected(start, targets, new_blocked):
            return -1  # 不能切断连通性

        new_dist, _ = self._bfs_shortest_path(start, targets, new_blocked)
        if new_dist is None:
            return -1
        return new_dist - current_dist

    def solve_algorithm(self, start_pos, exits, sim_time):
        import math

        end_time = time.time() + sim_time
        target_set = set(exits)

        # 收集所有可放置障碍的空地格子（不包括入口、出口、高台）
        ground_cells = set()
        for r in range(self.rows):
            for c in range(self.cols):
                if self.grid[r][c] == CELL_GROUND:
                    ground_cells.add((r, c))

        # 入口和出口不能被堵
        protected = {start_pos} | target_set

        # ===== Phase 1: 贪心初始化 =====
        blocked = set()  # 当前已放置障碍的格子
        phase1_iterations = 0

        dist, path = self._bfs_shortest_path(start_pos, target_set, blocked)
        if dist is None:
            # 初始就不连通
            self.root.after(0, self.finish_solving, (-1, -999999), [], {}, {}, 0, False)
            return

        best_dist = dist
        best_blocked = set(blocked)
        last_ui_update = time.time()

        # 贪心策略：每轮找到当前最短路径，选路径上使路径增长最多的节点放障碍
        while time.time() < end_time and not self.stop_requested:
            dist, path = self._bfs_shortest_path(start_pos, target_set, blocked)
            if dist is None:
                break

            if dist > best_dist:
                best_dist = dist
                best_blocked = set(blocked)

            # 评估路径上每个可阻断的节点
            candidates = []
            for cell in path:
                if cell in protected or cell not in ground_cells or cell in blocked:
                    continue
                gain = self._compute_bottleneck_score(cell, start_pos, target_set, blocked, dist)
                if gain > 0:
                    candidates.append((gain, cell))

            if not candidates:
                # 路径上没有可以有效阻断的节点了，贪心阶段结束
                break

            # 选增益最大的节点放置障碍
            candidates.sort(key=lambda x: -x[0])
            best_cell = candidates[0][1]
            blocked.add(best_cell)

            phase1_iterations += 1

            # 更新UI
            if time.time() - last_ui_update > 0.5:
                cur_dist, _ = self._bfs_shortest_path(start_pos, target_set, blocked)
                self.root.after(0, self.status_var.set,
                                f"Phase 1 贪心构造中... 已放置 {len(blocked)} 个障碍，当前最短路径: {cur_dist} 步")
                last_ui_update = time.time()

        # 贪心结束后更新最优
        final_dist, final_path = self._bfs_shortest_path(start_pos, target_set, blocked)
        if final_dist is not None and final_dist > best_dist:
            best_dist = final_dist
            best_blocked = set(blocked)

        # ===== Phase 2: 模拟退火优化 =====
        # 在贪心解基础上微调，尝试找到更优的障碍放置方案
        current_blocked = set(best_blocked)
        current_dist_val = best_dist
        sa_best_dist = best_dist
        sa_best_blocked = set(best_blocked)

        temperature = 5.0  # 初始温度
        cooling_rate = 0.9995
        sa_iterations = 0

        # 可用于交换的空地池（未被阻挡的空地）
        free_ground = ground_cells - current_blocked - protected

        while time.time() < end_time and not self.stop_requested:
            sa_iterations += 1

            # 随机选择一种邻域操作
            op = random.random()

            if op < 0.4 and current_blocked:
                # 操作1：移除一个随机障碍
                remove_cell = random.choice(list(current_blocked))
                new_blocked = current_blocked - {remove_cell}

            elif op < 0.8 and free_ground:
                # 操作2：添加一个随机障碍
                add_cell = random.choice(list(free_ground))
                new_blocked = current_blocked | {add_cell}

            elif current_blocked and free_ground:
                # 操作3：交换一个障碍和一个空地
                remove_cell = random.choice(list(current_blocked))
                add_cell = random.choice(list(free_ground))
                new_blocked = (current_blocked - {remove_cell}) | {add_cell}
            else:
                continue

            # 检查连通性和新距离
            if not self._is_connected(start_pos, target_set, new_blocked):
                continue

            new_dist, _ = self._bfs_shortest_path(start_pos, target_set, new_blocked)
            if new_dist is None:
                continue

            # 模拟退火接受准则
            delta = new_dist - current_dist_val
            if delta > 0 or (temperature > 0.01 and random.random() < math.exp(delta / temperature)):
                current_blocked = new_blocked
                current_dist_val = new_dist
                free_ground = ground_cells - current_blocked - protected

                if current_dist_val > sa_best_dist:
                    sa_best_dist = current_dist_val
                    sa_best_blocked = set(current_blocked)

            temperature *= cooling_rate

            # 更新UI
            if sa_iterations % 200 == 0 and time.time() - last_ui_update > 0.5:
                self.root.after(0, self.status_var.set,
                                f"Phase 2 模拟退火中... 迭代 {sa_iterations}，当前最短路径: {current_dist_val} 步，最优: {sa_best_dist} 步，温度: {temperature:.2f}")
                last_ui_update = time.time()

        # ===== 最终结果整理 =====
        final_blocked = sa_best_blocked
        final_dist_val, final_path = self._bfs_shortest_path(start_pos, target_set, final_blocked)
        if final_dist_val is None:
            final_dist_val = best_dist
            final_blocked = best_blocked
            _, final_path = self._bfs_shortest_path(start_pos, target_set, final_blocked)

        # 将最终路径转为 path_set，评估宝石布局
        path_set = set(final_path) if final_path else set()
        # 将blocked中的格子视为"非路径空地"，用于货架评估
        # 非blocked且非path的空地也要加入货架评估

        score_tuple, gem_stats, local_gem_map = self.evaluate_layout(path_set, final_blocked)

        is_forced_stop = self.stop_requested
        total_iterations = phase1_iterations + sa_iterations
        self.root.after(0, self.finish_solving, score_tuple, list(final_path) if final_path else [],
                        gem_stats, local_gem_map, total_iterations, is_forced_stop)

    def evaluate_layout(self, path_set, blocked_set=None):
        """
        评估当前布局的货架/宝石配置。
        path_set: 顾客行走路径上的格子。
        blocked_set: 被放置为障碍的格子（这些格子优先作为货架候选）。
        """
        if blocked_set is None:
            blocked_set = set()

        score = 0
        num_obstacles = 0
        gem_stats = {'8_face': 0, '4_face': 0, '2_face': 0, '1_face': 0}
        local_gem_map = {}
        use_multi = self.use_multi_gems.get()

        for r in range(self.rows):
            for c in range(self.cols):
                if self.grid[r][c] != CELL_GROUND:
                    continue
                if (r, c) in path_set:
                    continue
                # 这个格子是空地且不在路径上 → 放货架或障碍
                c_adj = 0
                d_adj = 0
                has_top = has_bottom = has_left = has_right = False

                # 检查四周十字 (接触面)
                for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < self.rows and 0 <= nc < self.cols:
                        if (nr, nc) in path_set or self.grid[nr][nc] in [CELL_ENTRANCE, CELL_EXIT]:
                            c_adj += 1
                            if dr == -1: has_top = True
                            if dr == 1: has_bottom = True
                            if dc == -1: has_left = True
                            if dc == 1: has_right = True

                # 检查四角对角线 (用于8面判定)
                for dr, dc in [(-1, -1), (-1, 1), (1, -1), (1, 1)]:
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < self.rows and 0 <= nc < self.cols:
                        if (nr, nc) in path_set or self.grid[nr][nc] in [CELL_ENTRANCE, CELL_EXIT]:
                            d_adj += 1

                t_adj = c_adj + d_adj
                best_f = 0
                best_g = None

                if use_multi:
                    # 8面宝石利用率 >= 75% 即 >= 6面
                    if t_adj >= 6:
                        best_f, best_g = t_adj, '8_face'
                    # 4面宝石利用率 >= 75% 即 >= 3面
                    if c_adj >= 3 and c_adj > best_f:
                        best_f, best_g = c_adj, '4_face'
                    # 2面宝石要求前后夹击，即上下都有路 或 左右都有路
                    if (has_top and has_bottom) or (has_left and has_right):
                        if 2 > best_f:
                            best_f, best_g = 2, '2_face'

                if best_f == 0 and c_adj >= 1:
                    best_f, best_g = 1, '1_face'

                if best_f > 0:
                    score += best_f
                    gem_stats[best_g] += 1
                    local_gem_map[(r, c)] = best_g
                else:
                    # 0面接触，算作纯障碍物
                    num_obstacles += 1

        # 优先比较接触面，其次比较障碍物数量(越少越好，所以取负数)
        return (score, -num_obstacles), gem_stats, local_gem_map

    def finish_solving(self, best_score_tuple, best_path, best_gem_stats, best_local_gem_map, sim_run, is_forced_stop):
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
            self.status_var.set(f"时间到！在期限内深搜了 {sim_run} 条通关路线并返回最优")

        # 打印输出结果
        res = f"★★★ 寻路规划完成 ★★★\n\n"
        if is_forced_stop:
            res += f"状态: 用户强制终止\n"
        res += f"共深搜探索了 {sim_run} 条通关路线\n\n"
        res += f"最大总接触面数 (销量): {best_score} 面\n\n"
        res += f"【货架使用统计】\n"
        if self.use_multi_gems.get():
            res += f"- 8面宝石货架: {best_gem_stats.get('8_face', 0)} 个\n"
            res += f"- 4面宝石货架: {best_gem_stats.get('4_face', 0)} 个\n"
            res += f"- 2面宝石货架: {best_gem_stats.get('2_face', 0)} 个\n"
        res += f"- 单面普通货架: {best_gem_stats.get('1_face', 0)} 个\n\n"

        total_shelves = sum(best_gem_stats.values())
        res += f"实际摆放销售货架总数: {total_shelves} 个\n"
        res += f"额外放置挡路障碍物(棕色): {num_obstacles} 个\n"

        self.result_text.delete(1.0, tk.END)
        self.result_text.insert(tk.END, res)


if __name__ == "__main__":
    root = tk.Tk()
    app = SupermarketSolverApp(root)
    root.mainloop()