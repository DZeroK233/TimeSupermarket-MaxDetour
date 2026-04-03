import tkinter as tk
from tkinter import messagebox, filedialog
import random
import time
import threading
import json

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
        self.root.title("超市最优布局求解器")
        self.root.geometry("850x650")

        self.rows = 15  # 竖
        self.cols = 19  # 横
        self.cell_size = 40
        self.grid = [[CELL_GROUND for _ in range(self.cols)] for _ in range(self.rows)]

        # 默认布局设置
        self.init_default_layout()

        self.current_tool = tk.IntVar(value=CELL_HIGH)
        self.use_multi_gems = tk.BooleanVar(value=True)
        self.is_solving = False

        self.setup_ui()
        self.draw_grid()

    def init_default_layout(self):
        """按照要求初始化默认的入口和出口位置"""
        self.grid = [[CELL_GROUND for _ in range(self.cols)] for _ in range(self.rows)]
        if 5 < self.rows and 5 < self.cols:
            self.grid[0][6] = CELL_ENTRANCE  # 题目说 (0,5) 是入口，这里按 (row, col) 坐标系系，x=0, y=5 即 row=5, col=0
            self.grid[5][0] = CELL_EXIT  # 出口 (5,0) -> row=0, col=5
            self.grid[5][1] = CELL_EXIT  # 出口 (5,1) -> row=1, col=5

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

        self.solve_btn = tk.Button(control_frame, text="开始求最优解\n(计算约需2秒)", bg="#4CAF50", fg="white",
                                   font=("Arial", 12, "bold"), command=self.start_solving)
        self.solve_btn.pack(fill=tk.X, pady=5)

        self.reset_btn = tk.Button(control_frame, text="重置网格", command=self.reset_grid)
        self.reset_btn.pack(fill=tk.X, pady=5)

        self.status_var = tk.StringVar(value="就绪")
        tk.Label(control_frame, textvariable=self.status_var, fg="blue", font=("Arial", 10)).pack(pady=10)

        # 结果显示区
        tk.Label(control_frame, text="求解结果:", font=("Arial", 12, "bold")).pack(anchor=tk.W, pady=(10, 0))
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

        # 每次求解前，自动清除旧的求解结果
        self.clear_solution()

        # 验证是否包含至少一个入口和一个出口
        entrances = [(r, c) for r in range(self.rows) for c in range(self.cols) if self.grid[r][c] == CELL_ENTRANCE]
        exits = [(r, c) for r in range(self.rows) for c in range(self.cols) if self.grid[r][c] == CELL_EXIT]

        if not entrances or not exits:
            messagebox.showwarning("警告", "必须至少放置一个入口和一个出口！")
            return

        self.is_solving = True
        self.solve_btn.config(state=tk.DISABLED)
        self.status_var.set("计算中，正在进行深度优先确定性探索...")
        self.result_text.delete(1.0, tk.END)
        self.result_text.insert(tk.END, "努力计算中...\n")

        # 使用子线程求解，防止界面卡死
        threading.Thread(target=self.solve_algorithm, args=(entrances[0], exits), daemon=True).start()

    def solve_algorithm(self, start_pos, exits):
        best_score = (-1, -999999)  # (接触面得分, -障碍物数量)
        best_path = []
        best_gem_stats = {}
        best_local_gem_map = {}

        end_time = time.time() + 2.0  # 计算时间限制在 2 秒

        # 预存所有非地面的固定格子
        fixed_obstacles = set()
        for r in range(self.rows):
            for c in range(self.cols):
                if self.grid[r][c] == CELL_HIGH or self.grid[r][c] == CELL_ENTRANCE:
                    fixed_obstacles.add((r, c))

        # 预计算所有紧贴着出口的格子（危险区，需要尽可能避开）
        exit_adj_cells = set()
        for r in range(self.rows):
            for c in range(self.cols):
                if self.grid[r][c] == CELL_EXIT:
                    for dr, dc in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
                        nr, nc = r + dr, c + dc
                        if 0 <= nr < self.rows and 0 <= nc < self.cols:
                            exit_adj_cells.add((nr, nc))

        # 严格确定性 DFS 生成长迷宫路径 (移除了所有 random 干扰)
        while time.time() < end_time:
            # stack元素: (当前节点, 路径列表, 路径集合, 邻居迭代器)
            stack = [(start_pos, [start_pos], {start_pos}, None)]

            while stack and time.time() < end_time:
                curr, path, path_set, neighbors = stack[-1]

                if neighbors is None:
                    # 获取有效邻居
                    exit_moves = []
                    normal_moves = []

                    # 固定的探索方向顺序
                    for dr, dc in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
                        nr, nc = curr[0] + dr, curr[1] + dc
                        if 0 <= nr < self.rows and 0 <= nc < self.cols:
                            if self.grid[nr][nc] == CELL_EXIT:
                                # 检查是否会导致提前接触出口（捷径）
                                adj_path = sum(1 for ddr, ddc in [(0, 1), (1, 0), (0, -1), (-1, 0)]
                                               if 0 <= nr + ddr < self.rows and 0 <= nc + ddc < self.cols and (
                                                   nr + ddr, nc + ddc) in path_set)
                                if adj_path == 1:
                                    exit_moves.append((nr, nc))

                            elif self.grid[nr][nc] == CELL_GROUND and (nr, nc) not in path_set:
                                # 防止路径并排产生2x2或捷径，严格要求周围只有1个路径格子（即前一个格子）
                                adj_path = sum(1 for ddr, ddc in [(0, 1), (1, 0), (0, -1), (-1, 0)]
                                               if 0 <= nr + ddr < self.rows and 0 <= nc + ddc < self.cols and (
                                                   nr + ddr, nc + ddc) in path_set)
                                if adj_path == 1:
                                    normal_moves.append((nr, nc))

                    if exit_moves:
                        # 成功抵达出口！
                        final_path = path + [exit_moves[0]]
                        final_set = set(path_set)
                        final_set.add(exit_moves[0])

                        score_tuple, stats, local_map = self.evaluate_layout(final_set)
                        if score_tuple > best_score:
                            best_score = score_tuple
                            best_path = final_path
                            best_gem_stats = stats
                            best_local_gem_map = local_map

                        # 立刻回溯。因为当前格子必然是贴着出口的死胡同，不能继续往下走了。
                        stack.pop()
                        continue

                    # 将正常的下一步格子进行【严格确定性打分排序】
                    moves_with_scores = []
                    for idx, (nr, nc) in enumerate(normal_moves):
                        # 扫描它周围有多少空地（Warnsdorff启发式核心）
                        free_neighbors = 0
                        for ddr, ddc in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
                            nnr, nnc = nr + ddr, nc + ddc
                            if 0 <= nnr < self.rows and 0 <= nnc < self.cols:
                                if self.grid[nnr][nnc] == CELL_GROUND and (nnr, nnc) not in path_set:
                                    free_neighbors += 1

                        # 距离所有出口的最短曼哈顿距离
                        min_dist_to_exit = min(abs(nr - er) + abs(nc - ec) for er, ec in exits)

                        # 【确定性算分规则】：
                        # 1. 首要：剩余空地越少越优先，权重极大 (-free_neighbors)
                        # 2. 次要：距离出口越远越优先，起拖延时间的作用 (+min_dist_to_exit)
                        # 3. 三级：固定的方向索引，确保排序绝对稳定 (+idx)
                        score = (-free_neighbors * 10000) + (min_dist_to_exit * 10) - idx

                        # 核心防短路机制：如果这一步紧挨着出口，给出极其严重的扣分，逼迫它去探索远方的格子！
                        if (nr, nc) in exit_adj_cells:
                            score -= 1000000

                        moves_with_scores.append((score, (nr, nc)))

                    # 按照得分排序（得分低的放前面，得分高的放队尾，队尾会被最先 pop() 出来探索）
                    # 移除了所有 random 因素，使用 Python 稳定的 sort 保证绝对确定性
                    moves_with_scores.sort(key=lambda x: x[0])
                    neighbors = [m[1] for m in moves_with_scores]

                    stack[-1] = (curr, path, path_set, neighbors)

                if not neighbors:
                    # 死胡同，回溯
                    stack.pop()
                else:
                    nxt = neighbors.pop()
                    new_path = path + [nxt]
                    new_set = set(path_set)
                    new_set.add(nxt)
                    stack.append((nxt, new_path, new_set, None))

            # 因为是纯确定性搜索，遍历完所有能遍历的深度后，如果由于时间限制没退出，也不需要再重新进行了。
            # 直接跳出 while 循环即可。
            break

        # 回到主线程更新UI
        self.root.after(0, self.finish_solving, best_score, best_path, best_gem_stats, best_local_gem_map)

    def evaluate_layout(self, path_set):
        score = 0
        num_obstacles = 0
        gem_stats = {'8_face': 0, '4_face': 0, '2_face': 0, '1_face': 0}
        local_gem_map = {}
        use_multi = self.use_multi_gems.get()

        for r in range(self.rows):
            for c in range(self.cols):
                if self.grid[r][c] == CELL_GROUND and (r, c) not in path_set:
                    # 这是一个货架候选位置
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

    def finish_solving(self, best_score_tuple, best_path, best_gem_stats, best_local_gem_map):
        self.is_solving = False
        self.solve_btn.config(state=tk.NORMAL)

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

        self.status_var.set("求解完成！")

        # 打印输出结果
        res = f"★★★ 寻路规划完成 ★★★\n\n"
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