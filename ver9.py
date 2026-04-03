import tkinter as tk
from tkinter import messagebox, filedialog
import time
import threading
import json
import random
import math
from collections import deque
import sys
import os

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
    '1_face': '#1E90FF'   # 默认蓝
}

# ===== 游戏布局导出配置 =====
# 不同尺寸货架对应的游戏内模板ID (nTemplateID)
# TODO: 请根据游戏内实际数据补完以下ID列表中值为0的条目
# 1x1 货架共5种品类:
SHELF_TEMPLATE_1x1 = [1, 2, 3, 1001, 20030]
# 1x2 货架:
SHELF_TEMPLATE_1x2 = [4, 5, 6, 7, 8]
# 2x2 货架仅1种品类:
SHELF_TEMPLATE_2x2 = [9]
# 障碍物模板ID
OBSTACLE_TEMPLATE_ID = 20030

# 求解器方向 → 游戏 eDirection 的映射
# TODO: 如游戏内方向不对，请调整此映射
DIRECTION_MAP = {
    'top': 1,
    'bottom': 2,
    'left': 3,
    'right': 0,
    None: 3  # 多面宝石默认方向
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

        # 货架比例权重 (0~5)
        self.ratio_1x1 = tk.StringVar(value="1")
        self.ratio_1x2 = tk.StringVar(value="1")
        self.ratio_2x2 = tk.StringVar(value="1")

        self.sim_time_var = tk.StringVar(value="60")  # 默认自定义60秒
        self.is_solving = False
        self.stop_requested = False

        # 补回遗漏的变量初始化
        self.best_solution_grid = None
        self.best_gem_map = {}
        self.best_placed_shapes = []
        self.best_path_sales = {} # 记录每个路径格子贡献了多少面销量
        self.best_shelf_info = {} # 记录每个货架格子的朝向/生效面数

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
        
        btn_frame = tk.Frame(io_frame)
        btn_frame.pack(fill=tk.X)
        tk.Button(btn_frame, text="导出布局", command=self.export_layout).pack(side=tk.LEFT, expand=True, fill=tk.X,
                                                                              padx=(0, 2))
        tk.Button(btn_frame, text="导入布局", command=self.import_layout).pack(side=tk.RIGHT, expand=True, fill=tk.X,
                                                                              padx=(2, 0))

        # 预设地图折叠菜单
        self.preset_menu_btn = tk.Menubutton(io_frame, text="导入不同店预设地图 (1~7)", relief=tk.RAISED)
        self.preset_menu_btn.pack(side=tk.TOP, expand=True, fill=tk.X, pady=(5, 0))
        self.preset_menu = tk.Menu(self.preset_menu_btn, tearoff=0)
        self.preset_menu_btn.config(menu=self.preset_menu)
        self.load_preset_maps()

        tk.Frame(control_frame, height=2, bd=1, relief=tk.SUNKEN).pack(fill=tk.X, pady=5)

        tk.Label(control_frame, text="允许采购的货架尺寸:", font=("Arial", 11, "bold")).pack(anchor=tk.W)

        # 1x1 行
        frame_1x1 = tk.Frame(control_frame)
        frame_1x1.pack(anchor=tk.W, fill=tk.X)
        tk.Checkbutton(frame_1x1, text="允许 1x1 货架", variable=self.allow_1x1).pack(side=tk.LEFT)
        tk.Label(frame_1x1, text="比例:").pack(side=tk.LEFT, padx=(5, 0))
        tk.Entry(frame_1x1, textvariable=self.ratio_1x1, width=3, font=("Arial", 10)).pack(side=tk.LEFT, padx=2)

        # 1x2 行
        frame_1x2 = tk.Frame(control_frame)
        frame_1x2.pack(anchor=tk.W, fill=tk.X)
        tk.Checkbutton(frame_1x2, text="允许 1x2 货架", variable=self.allow_1x2).pack(side=tk.LEFT)
        tk.Label(frame_1x2, text="比例:").pack(side=tk.LEFT, padx=(5, 0))
        tk.Entry(frame_1x2, textvariable=self.ratio_1x2, width=3, font=("Arial", 10)).pack(side=tk.LEFT, padx=2)

        # 2x2 行
        frame_2x2 = tk.Frame(control_frame)
        frame_2x2.pack(anchor=tk.W, fill=tk.X)
        tk.Checkbutton(frame_2x2, text="允许 2x2 货架", variable=self.allow_2x2).pack(side=tk.LEFT)
        tk.Label(frame_2x2, text="比例:").pack(side=tk.LEFT, padx=(5, 0))
        tk.Entry(frame_2x2, textvariable=self.ratio_2x2, width=3, font=("Arial", 10)).pack(side=tk.LEFT, padx=2)

        tk.Label(control_frame, text="比例0~5, 未勾选视为0, 默认1:1:1", font=("Arial", 9), fg="gray").pack(anchor=tk.W)
        tk.Label(control_frame, text="(八面宝石: 1x1→8格/1x2→10格/2x2→12格)", font=("Arial", 9), fg="gray").pack(anchor=tk.W)

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

        reset_export_frame = tk.Frame(control_frame)
        reset_export_frame.pack(fill=tk.X, pady=5)
        self.reset_btn = tk.Button(reset_export_frame, text="重置网格", command=self.reset_grid)
        self.reset_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 2))
        self.export_preset_btn = tk.Button(reset_export_frame, text="导出到布局预设…", command=self.export_to_game_preset)
        self.export_preset_btn.pack(side=tk.RIGHT, expand=True, fill=tk.X, padx=(2, 0))

        self.status_var = tk.StringVar(value="就绪")
        tk.Label(control_frame, textvariable=self.status_var, fg="blue", font=("Arial", 10)).pack(pady=2)

        tk.Label(control_frame, text="【交互提示】\n滚轮：上下滚动 | Ctrl+滚轮：缩放\n鼠标右键/中键：拖动地图", font=("Arial", 9), fg="gray", justify=tk.LEFT).pack(anchor=tk.W, pady=2)

        # 结果显示区
        tk.Label(control_frame, text="求解结果:", font=("Arial", 12, "bold")).pack(anchor=tk.W, pady=(2, 0))
        self.result_text = tk.Text(control_frame, height=12, width=30, font=("Arial", 10))
        self.result_text.pack(fill=tk.BOTH, expand=True)

        # 右侧画布
        self.canvas_frame = tk.Frame(self.root)
        self.canvas_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 添加滚动条
        self.v_scrollbar = tk.Scrollbar(self.canvas_frame, orient=tk.VERTICAL)
        self.h_scrollbar = tk.Scrollbar(self.canvas_frame, orient=tk.HORIZONTAL)
        self.v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)

        self.canvas = tk.Canvas(self.canvas_frame, bg="white", xscrollcommand=self.h_scrollbar.set, yscrollcommand=self.v_scrollbar.set)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.v_scrollbar.config(command=self.canvas.yview)
        self.h_scrollbar.config(command=self.canvas.xview)

        # 绑定鼠标事件进行绘制
        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<B1-Motion>", self.on_drag)

        # 绑定鼠标右键/中键滑动地图
        self.canvas.bind("<Button-3>", self.on_pan_start)
        self.canvas.bind("<B3-Motion>", self.on_pan_drag)
        self.canvas.bind("<Button-2>", self.on_pan_start)
        self.canvas.bind("<B2-Motion>", self.on_pan_drag)

        # 绑定鼠标滚轮控制上下滚动
        self.canvas.bind("<MouseWheel>", self.on_vscroll)
        self.canvas.bind("<Button-4>", self.on_vscroll)
        self.canvas.bind("<Button-5>", self.on_vscroll)

        # 绑定按住CTRL+鼠标滚轮控制缩放
        self.canvas.bind("<Control-MouseWheel>", self.on_zoom)
        self.canvas.bind("<Control-Button-4>", self.on_zoom)
        self.canvas.bind("<Control-Button-5>", self.on_zoom)

    def draw_grid(self):
        self.canvas.delete("all")
        width = self.cols * self.cell_size
        height = self.rows * self.cell_size
        self.canvas.config(scrollregion=(0, 0, width, height))

        # 收集大货架中已被处理的格子集合（用于跳过单格文字绘制）
        large_shelf_cells = set()
        if self.best_placed_shapes:
            for pts, stype in self.best_placed_shapes:
                if stype in ['1x2', '2x2']:
                    for p in pts:
                        large_shelf_cells.add(p)

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

                # 绘制文字标识 —— 大货架(1x2/2x2)的面数文字稍后居中绘制，此处跳过
                text = ""
                if cell_val == CELL_ENTRANCE:
                    text = "入"
                elif cell_val == CELL_EXIT:
                    text = "出"
                elif cell_val == CELL_HIGH:
                    text = "高"
                elif cell_val == CELL_OBSTACLE:
                    text = "障"
                elif cell_val == CELL_SHELF and (r, c) not in large_shelf_cells:
                    # 1x1 货架，直接在本格显示
                    if (r, c) in self.best_shelf_info:
                        info = self.best_shelf_info[(r, c)]
                        direction = info.get('direction')
                        active_faces = info.get('active_faces', 0)
                        if direction is not None:
                            arrow_map = {'top': '↑', 'bottom': '↓', 'left': '←', 'right': '→'}
                            text = arrow_map.get(direction, '')
                        else:
                            if active_faces > 0:
                                text = f"{active_faces}面"

                # 如果是路径，并且贡献了销售面，在黄色框上打印数字
                if cell_val == CELL_PATH:
                    sales = self.best_path_sales.get((r, c), 0)
                    if sales > 0:
                        text = str(sales)

                if text:
                    font_size = max(6, int(self.cell_size * 0.35))
                    self.canvas.create_text(x1 + self.cell_size / 2, y1 + self.cell_size / 2, text=text,
                                            font=("Arial", font_size, "bold"))

        # 绘制连体货架的加粗黑框 + 居中文字
        if self.best_placed_shapes:
            for pts, stype in self.best_placed_shapes:
                if stype in ['1x2', '2x2']:
                    min_r = min(p[0] for p in pts)
                    max_r = max(p[0] for p in pts)
                    min_c = min(p[1] for p in pts)
                    max_c = max(p[1] for p in pts)

                    bx1 = min_c * self.cell_size
                    by1 = min_r * self.cell_size
                    bx2 = (max_c + 1) * self.cell_size
                    by2 = (max_r + 1) * self.cell_size

                    self.canvas.create_rectangle(bx1+2, by1+2, bx2-2, by2-2, outline="#000000", width=max(1, int(self.cell_size * 0.05)))

                    # 在货架中心位置居中显示面数或箭头
                    center_x = (bx1 + bx2) / 2
                    center_y = (by1 + by2) / 2

                    # 取第一个格子的 shelf_info 作为整体信息
                    first_pt = pts[0]
                    if first_pt in self.best_shelf_info:
                        info = self.best_shelf_info[first_pt]
                        direction = info.get('direction')
                        active_faces = info.get('active_faces', 0)
                        shelf_text = ""
                        if direction is not None:
                            arrow_map = {'top': '↑', 'bottom': '↓', 'left': '←', 'right': '→'}
                            shelf_text = arrow_map.get(direction, '')
                        else:
                            if active_faces > 0:
                                shelf_text = f"{active_faces}面"
                        if shelf_text:
                            font_size = max(8, int(self.cell_size * 0.4))
                            self.canvas.create_text(center_x, center_y, text=shelf_text,
                                                    font=("Arial", font_size, "bold"), fill="white")

    def paint_cell(self, event):
        if self.is_solving: return
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        c = int(cx) // self.cell_size
        r = int(cy) // self.cell_size
        if 0 <= r < self.rows and 0 <= c < self.cols:
            val = self.current_tool.get()
            # 简单校验：不能覆盖已有的出入口，除非使用的是橡皮擦
            if self.grid[r][c] in [CELL_ENTRANCE, CELL_EXIT] and val not in [CELL_GROUND, CELL_ENTRANCE, CELL_EXIT]:
                return
            self.grid[r][c] = val
            self.best_gem_map.clear()
            self.best_placed_shapes = []
            self.best_path_sales = {}
            self.best_shelf_info = {}
            self.draw_grid()

    def on_click(self, event):
        self.paint_cell(event)

    def on_drag(self, event):
        self.paint_cell(event)

    def on_pan_start(self, event):
        self.canvas.scan_mark(event.x, event.y)

    def on_pan_drag(self, event):
        self.canvas.scan_dragto(event.x, event.y, gain=1)

    def on_vscroll(self, event):
        # 滚轮控制画布上下滚动
        if event.num == 5 or event.delta < 0:
            self.canvas.yview_scroll(1, "units")
        elif event.num == 4 or event.delta > 0:
            self.canvas.yview_scroll(-1, "units")

    def on_zoom(self, event):
        # 响应CTRL+滚轮事件，调整格子大小
        if event.num == 5 or event.delta < 0:  # 向下滚动，缩小
            self.cell_size = max(10, self.cell_size - 5)
        elif event.num == 4 or event.delta > 0:  # 向上滚动，放大
            self.cell_size = min(100, self.cell_size + 5)
        self.draw_grid()

    def reset_grid(self):
        if self.is_solving: return
        self.init_default_layout()
        self.best_gem_map.clear()
        self.best_placed_shapes = []
        self.best_path_sales = {}
        self.best_shelf_info = {}
        self.draw_grid()
        self.result_text.delete(1.0, tk.END)

    def clear_solution(self):
        """清除之前的求解结果（路径、货架、障碍物），只保留高台、入出口、地面"""
        self.best_gem_map.clear()
        self.best_placed_shapes = []
        self.best_path_sales = {}
        self.best_shelf_info = {}
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

    def resource_path(self, relative_path):
        """获取资源绝对路径，支持PyInstaller打包时的_MEIPASS路径"""
        try:
            base_path = sys._MEIPASS
        except Exception:
            base_path = os.path.abspath(".")
        return os.path.join(base_path, relative_path)

    def load_preset_maps(self):
        """加载同目录下的文件夹1~7的地形文件作为折叠菜单一项"""
        for i in range(1, 8):
            folder_name = str(i)
            folder_path = self.resource_path(folder_name)
            if os.path.isdir(folder_path):
                submenu = tk.Menu(self.preset_menu, tearoff=0)
                self.preset_menu.add_cascade(label=f"分店 {folder_name}", menu=submenu)
                
                try:
                    files = os.listdir(folder_path)
                    layout_files = [f for f in files if f.startswith('map_level_') and f.endswith('_layout.json')]
                    
                    def get_level(fname):
                        parts = fname.split('_')
                        if len(parts) > 2 and parts[2].isdigit():
                            return int(parts[2])
                        return 0
                    
                    layout_files.sort(key=get_level)
                    
                    for f in layout_files:
                        idx = get_level(f)
                        full_path = os.path.join(folder_path, f)
                        # 使用默认参数绑定 current path
                        submenu.add_command(label=f"Level {idx}", command=lambda p=full_path: self.load_preset_map(p))
                except Exception as e:
                    pass

    def load_preset_map(self, filepath):
        if self.is_solving: return
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
            messagebox.showerror("错误", f"预设地图导入失败: {e}")

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

        # 解析比例权重
        def parse_ratio(var, allow_var):
            if not allow_var.get():
                return 0
            try:
                v = int(var.get())
                return max(0, min(5, v))
            except (ValueError, TypeError):
                return 1

        r_1x1 = parse_ratio(self.ratio_1x1, self.allow_1x1)
        r_1x2 = parse_ratio(self.ratio_1x2, self.allow_1x2)
        r_2x2 = parse_ratio(self.ratio_2x2, self.allow_2x2)

        # 固化配置字典，避免后台线程频繁读取Tkinter引发卡顿
        config = {
            'allow_1x1': self.allow_1x1.get(),
            'allow_1x2': self.allow_1x2.get(),
            'allow_2x2': self.allow_2x2.get(),
            'use_multi_gems': self.use_multi_gems.get(),
            'ratio_1x1': r_1x1,
            'ratio_1x2': r_1x2,
            'ratio_2x2': r_2x2
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
            self.root.after(0, self.finish_solving, (-1, -999999), [], {}, {}, [], {}, {}, {}, 0, False)
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

        # ===== Phase 1.5: 清理冗余阻断点 =====
        # 逐个检查 blocked 中的格子，如果移除后路径长度不变，则释放给货架使用
        cleanup_removed = 0
        for cell in list(best_blocked):
            test_blocked = best_blocked - {cell}
            test_dist, _ = self._bfs_shortest_path(start_pos, target_set, test_blocked)
            if test_dist is not None and test_dist >= final_dist:
                best_blocked.remove(cell)
                cleanup_removed += 1
        if cleanup_removed > 0:
            # 重新计算路径
            final_dist, final_path = self._bfs_shortest_path(start_pos, target_set, best_blocked)

        path_set = set(final_path) if final_path else set()

        # evaluation拆包加入了 path_sales_counts 以实现格子销量显示
        base_eval = self.evaluate_layout(path_set, best_blocked, config)
        base_score_tuple, base_gem_stats, base_local_gem_map, base_placed_shapes, base_shape_counts, base_path_sales, base_shelf_info = base_eval

        current_blocked = set(best_blocked)
        current_dist_val = final_dist
        current_score_val = base_score_tuple[0]
        num_obstacles_val = -base_score_tuple[1]

        # 【目标函数】：销量为核心，路径长度辅助，障碍物惩罚防止空间浪费
        current_obj_val = current_score_val * 1000 + current_dist_val - num_obstacles_val * 50

        sa_best_obj = current_obj_val
        sa_best_eval = (base_score_tuple, base_gem_stats, base_local_gem_map, base_placed_shapes, base_shape_counts, base_path_sales, base_shelf_info, final_path)

        temperature = 1000.0
        cooling_rate = 0.9995
        sa_iterations = 0

        free_ground = ground_cells - current_blocked - protected

        # ===== Phase 2: 模拟退火优化 =====
        while time.time() < end_time and not self.stop_requested:
            sa_iterations += 1
            op = random.random()

            if op < 0.1 and len(current_blocked) >= 2:
                # 批量移除 2~3 个 blocked 格子，快速逃离障碍物堆积的局部最优
                n_remove = min(random.randint(2, 3), len(current_blocked))
                remove_cells = set(random.sample(list(current_blocked), n_remove))
                new_blocked = current_blocked - remove_cells
            elif op < 0.45 and current_blocked:
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
            score_tuple, gem_stats, local_gem_map, placed_shapes, shape_counts, path_sales, shelf_info = new_eval
            new_score = score_tuple[0]
            new_num_obs = -score_tuple[1]
            new_obj_val = new_score * 1000 + new_dist - new_num_obs * 50

            delta = new_obj_val - current_obj_val
            if delta > 0 or (temperature > 0.01 and random.random() < math.exp(delta / temperature)):
                current_blocked = new_blocked
                current_dist_val = new_dist
                current_score_val = new_score
                current_obj_val = new_obj_val
                free_ground = ground_cells - current_blocked - protected

                if current_obj_val > sa_best_obj:
                    sa_best_obj = current_obj_val
                    sa_best_eval = (score_tuple, gem_stats, local_gem_map, placed_shapes, shape_counts, path_sales, shelf_info, p_path)

            temperature *= cooling_rate

            if sa_iterations % 200 == 0 and time.time() - last_ui_update > 0.5:
                self.root.after(0, self.status_var.set,
                                f"Phase 2 退火中... 迭代{sa_iterations} 最优:{sa_best_eval[0][0]}面 障碍:{-sa_best_eval[0][1]}")
                last_ui_update = time.time()

        # ===== 最终结果提取 =====
        best_score_tuple, best_gem_stats, best_local_gem_map, best_placed_shapes, best_shape_counts, best_path_sales, best_shelf_info, final_path = sa_best_eval
        is_forced_stop = self.stop_requested
        total_iterations = phase1_iterations + sa_iterations

        self.root.after(0, self.finish_solving, best_score_tuple, list(final_path) if final_path else [],
                        best_gem_stats, best_local_gem_map, best_placed_shapes, best_shape_counts, best_path_sales, best_shelf_info, total_iterations, is_forced_stop)

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

            if config['use_multi_gems']:
                # 直接使用八面宝石，计算外围一圈所有路径格子
                # 1x1→8格, 1x2→10格, 2x2→12格
                all_paths = top_paths + bottom_paths + left_paths + right_paths + corner_paths
                best_f = len(all_paths)
                best_g = '8_face' if best_f > 0 else None
                active_paths = all_paths
                active_face_count = best_f
                return best_f, best_g, active_paths, None, active_face_count
            else:
                # 不使用多面宝石，选择最佳单面朝向
                if stype == '1x1' or stype == '2x2':
                    candidates = [
                        (c_adj_top, top_paths, 'top'),
                        (c_adj_bottom, bottom_paths, 'bottom'),
                        (c_adj_left, left_paths, 'left'),
                        (c_adj_right, right_paths, 'right')
                    ]
                elif stype == '1x2':
                    if min_r == max_r:  # 横向 1x2，长边是上下，物理屏蔽左右短边
                        candidates = [
                            (c_adj_top, top_paths, 'top'),
                            (c_adj_bottom, bottom_paths, 'bottom')
                        ]
                    else:               # 竖向 1x2，长边是左右，物理屏蔽上下短边
                        candidates = [
                            (c_adj_left, left_paths, 'left'),
                            (c_adj_right, right_paths, 'right')
                        ]

                candidates.sort(key=lambda x: x[0], reverse=True)
                best_f = candidates[0][0]
                active_paths = candidates[0][1]
                direction = candidates[0][2]
                best_g = '1_face' if best_f > 0 else None
                active_face_count = best_f
                return best_f, best_g, active_paths, direction, active_face_count

        # 扫描允许放入的 2x2 货架
        if config['allow_2x2']:
            for r in range(self.rows - 1):
                for c in range(self.cols - 1):
                    pts = [(r, c), (r+1, c), (r, c+1), (r+1, c+1)]
                    if all(p in ground_set for p in pts):
                        score, gem, paths, direction, af = get_adj_stats(pts, '2x2')
                        shapes.append((score, pts, '2x2', gem, paths, direction, af))

        # 扫描允许放入的 1x2 货架（横向和竖向）
        if config['allow_1x2']:
            for r in range(self.rows):
                for c in range(self.cols - 1):
                    pts = [(r, c), (r, c+1)]
                    if all(p in ground_set for p in pts):
                        score, gem, paths, direction, af = get_adj_stats(pts, '1x2')
                        shapes.append((score, pts, '1x2', gem, paths, direction, af))
            for r in range(self.rows - 1):
                for c in range(self.cols):
                    pts = [(r, c), (r+1, c)]
                    if all(p in ground_set for p in pts):
                        score, gem, paths, direction, af = get_adj_stats(pts, '1x2')
                        shapes.append((score, pts, '1x2', gem, paths, direction, af))

        # 扫描 1x1 货架
        if config['allow_1x1']:
            for p in ground_set:
                score, gem, paths, direction, af = get_adj_stats([p], '1x1')
                shapes.append((score, [p], '1x1', gem, paths, direction, af))

        # ===== 加权轮询打包策略 =====
        # 按类型分组，每组内部按得分降序
        type_shapes = {'1x1': [], '1x2': [], '2x2': []}
        for item in shapes:
            score, pts, stype, gem, active_paths, direction, af = item
            if score > 0:
                type_shapes[stype].append(item)

        for k in type_shapes:
            type_shapes[k].sort(key=lambda x: x[0], reverse=True)

        # 比例权重
        ratio_weights = {
            '1x1': config.get('ratio_1x1', 1),
            '1x2': config.get('ratio_1x2', 1),
            '2x2': config.get('ratio_2x2', 1)
        }
        total_ratio = sum(ratio_weights.values())
        if total_ratio > 0:
            target_ratios = {k: v / total_ratio for k, v in ratio_weights.items()}
        else:
            target_ratios = {'1x1': 1/3, '1x2': 1/3, '2x2': 1/3}

        used = set()
        placed_shapes = []
        total_score = 0
        gem_stats = {'8_face': 0, '1_face': 0}
        local_gem_map = {}
        shape_counts = {'1x1': 0, '1x2': 0, '2x2': 0}
        path_sales_counts = {}
        shelf_info_map = {}

        # 每种类型的遍历指针
        type_cursors = {'1x1': 0, '1x2': 0, '2x2': 0}
        # 标记哪些类型已经用尽
        exhausted = set()
        active_types = [t for t in ['2x2', '1x2', '1x1'] if target_ratios.get(t, 0) > 0]

        def _place_shape(item):
            """放置一个货架，更新所有状态"""
            nonlocal total_score
            score, pts, stype, gem, active_paths, direction, active_faces = item
            placed_shapes.append((pts, stype))
            shape_counts[stype] += 1
            total_score += score
            if gem:
                gem_stats[gem] = gem_stats.get(gem, 0) + 1
                for p in pts:
                    local_gem_map[p] = gem
            for p in pts:
                used.add(p)
                shelf_info_map[p] = {'direction': direction, 'active_faces': active_faces}
            for path_cell in active_paths:
                path_sales_counts[path_cell] = path_sales_counts.get(path_cell, 0) + 1

        def _try_place_next(stype):
            """尝试放置该类型的下一个最优候选。返回是否成功。"""
            while type_cursors[stype] < len(type_shapes[stype]):
                item = type_shapes[stype][type_cursors[stype]]
                type_cursors[stype] += 1
                pts = item[1]
                if not any(p in used for p in pts):
                    _place_shape(item)
                    return True
            exhausted.add(stype)
            return False

        # 主循环：每轮从最欠缺的类型中取下一个最优候选
        while len(exhausted) < len(active_types):
            total_placed = sum(shape_counts.values()) or 1

            # 计算每个类型的"欠缺度" = 目标比例 - 实际比例
            best_type = None
            best_deficit = -999
            for stype in active_types:
                if stype in exhausted:
                    continue
                actual_ratio = shape_counts[stype] / total_placed
                deficit = target_ratios[stype] - actual_ratio
                if deficit > best_deficit:
                    best_deficit = deficit
                    best_type = stype

            if best_type is None:
                break

            if not _try_place_next(best_type):
                # 该类型已用尽，下一轮自动跳过
                continue

        # 收尾阶段：所有有配额的类型用尽后，用剩余任意类型填满（纯贪心）
        all_remaining = []
        for stype in ['2x2', '1x2', '1x1']:
            remaining = type_shapes[stype][type_cursors[stype]:]
            all_remaining.extend(remaining)
        # 也收集比例为0但 config 允许的类型（不应该有，但防御性处理）
        all_remaining.sort(key=lambda x: x[0], reverse=True)

        for item in all_remaining:
            pts = item[1]
            stype = item[2]
            if target_ratios.get(stype, 0) == 0:
                continue  # 比例为0的类型始终不放
            if not any(p in used for p in pts):
                _place_shape(item)

        num_obstacles = len(ground_set) - len(used)

        return (total_score, -num_obstacles), gem_stats, local_gem_map, placed_shapes, shape_counts, path_sales_counts, shelf_info_map

    def finish_solving(self, best_score_tuple, best_path, best_gem_stats, best_local_gem_map, best_placed_shapes, best_shape_counts, best_path_sales, best_shelf_info, sim_run, is_forced_stop):
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
        self.best_shelf_info = best_shelf_info

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
            res += f"- 八面宝石货架: {best_gem_stats.get('8_face', 0)} 个\n"
        res += f"- 单面朝向货架: {best_gem_stats.get('1_face', 0)} 个\n\n"

        res += f"额外放置挡路障碍物(棕色): {num_obstacles} 个\n"

        self.result_text.delete(1.0, tk.END)
        self.result_text.insert(tk.END, res)

    # ===== 导出到游戏布局预设 =====

    def export_to_game_preset(self):
        """导出到游戏布局预设文件"""
        if self.is_solving:
            return
        if not self.best_placed_shapes:
            messagebox.showinfo("提示", "当前没有求解后的规划结果。\n请先运行求解器生成布局方案后再导出。")
            return
        shelf_counts = {'1x1': 0, '1x2': 0, '2x2': 0}
        for pts, stype in self.best_placed_shapes:
            shelf_counts[stype] = shelf_counts.get(stype, 0) + 1
        self._show_category_dialog(shelf_counts)

    def _show_category_dialog(self, shelf_counts):
        """显示品类数量配置对话框"""
        dialog = tk.Toplevel(self.root)
        dialog.title("导出到布局预设 - 品类配置")
        dialog.geometry("600x650")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.resizable(False, False)

        tk.Label(dialog, text="配置每种尺寸货架的品类比例", font=("Arial", 12, "bold")).pack(pady=(10, 2))
        tk.Label(dialog, text="输入框代表比例权重（数字允许很大，导出时自动按比例求出分配总数）", font=("Arial", 9), fg="gray").pack()

        sizes = ['1x1', '1x2', '2x2']
        labels_map = {
            '1x1': ['水果', '饮料', '蔬菜', '万能(1001)', '路障(20030)'],
            '1x2': ['日用', '体育', '电子', '奢侈', '服装'],
            '2x2': ['电器']
        }
        category_vars = {'1x1': [], '1x2': [], '2x2': []}

        main_frame = tk.Frame(dialog, padx=20, pady=10)
        main_frame.pack(fill=tk.X)

        for size in sizes:
            count = shelf_counts.get(size, 0)
            row_frame = tk.Frame(main_frame)
            row_frame.pack(fill=tk.X, pady=5)
            tk.Label(row_frame, text=f"{size} 货架（共 {count} 个）", font=("Arial", 11, "bold"), anchor='w').pack(side=tk.TOP, anchor='w')
            
            if count == 0:
                tk.Label(row_frame, text="暂无此尺寸货架", fg="gray").pack(side=tk.LEFT, padx=10)
                continue
                
            input_frame = tk.Frame(row_frame)
            input_frame.pack(side=tk.LEFT, fill=tk.X, pady=5)
            
            for i, label_txt in enumerate(labels_map[size]):
                col_frame = tk.Frame(input_frame)
                col_frame.pack(side=tk.LEFT, padx=5)
                tk.Label(col_frame, text=label_txt, font=("Arial", 9), justify=tk.CENTER).pack()
                # 第一个默认为总数，其余为0
                default_val = count if i == 0 else 0
                var = tk.StringVar(value=str(default_val))
                category_vars[size].append(var)
                tk.Entry(col_frame, textvariable=var, width=6, justify=tk.CENTER, font=("Arial", 10)).pack()

        # 坐标偏移
        tk.Frame(dialog, height=2, bd=1, relief=tk.SUNKEN).pack(fill=tk.X, padx=20, pady=5)
        offset_frame = tk.Frame(dialog, padx=20)
        offset_frame.pack(fill=tk.X)
        tk.Label(offset_frame, text="游戏坐标偏移:", font=("Arial", 10, "bold")).pack(side=tk.LEFT)
        tk.Label(offset_frame, text="X:").pack(side=tk.LEFT, padx=(10, 0))
        offset_x_var = tk.StringVar(value="60")
        tk.Entry(offset_frame, textvariable=offset_x_var, width=5, font=("Arial", 10)).pack(side=tk.LEFT, padx=2)
        tk.Label(offset_frame, text="Y:").pack(side=tk.LEFT, padx=(10, 0))
        offset_y_var = tk.StringVar(value="60")
        tk.Entry(offset_frame, textvariable=offset_y_var, width=5, font=("Arial", 10)).pack(side=tk.LEFT, padx=2)
        tk.Label(dialog, text="提示: 游戏原点在左上角向右下递减，计算: 游戏X=偏移X-行", font=("Arial", 8), fg="gray", padx=20).pack(anchor=tk.W)

        # 店铺和口碑配置
        tk.Frame(dialog, height=2, bd=1, relief=tk.SUNKEN).pack(fill=tk.X, padx=20, pady=5)
        scene_frame = tk.Frame(dialog, padx=20)
        scene_frame.pack(fill=tk.X)
        tk.Label(scene_frame, text="店铺与口碑:", font=("Arial", 10, "bold")).pack(side=tk.LEFT)
        tk.Label(scene_frame, text="店铺ID:").pack(side=tk.LEFT, padx=(10, 0))
        scene_id_var = tk.StringVar(value="1")
        tk.Entry(scene_frame, textvariable=scene_id_var, width=4, font=("Arial", 10)).pack(side=tk.LEFT, padx=2)
        tk.Label(scene_frame, text="口碑等级:").pack(side=tk.LEFT, padx=(10, 0))
        scene_praise_var = tk.StringVar(value="9")
        tk.Entry(scene_frame, textvariable=scene_praise_var, width=4, font=("Arial", 10)).pack(side=tk.LEFT, padx=2)

        # 预览
        tk.Frame(dialog, height=2, bd=1, relief=tk.SUNKEN).pack(fill=tk.X, padx=20, pady=5)
        tk.Label(dialog, text="分配预览:", font=("Arial", 11, "bold"), padx=20).pack(anchor=tk.W)
        preview_text = tk.Text(dialog, height=8, font=("Arial", 10), state=tk.DISABLED)
        preview_text.pack(fill=tk.BOTH, expand=True, padx=20, pady=5)

        def update_preview(*args):
            preview_text.config(state=tk.NORMAL)
            preview_text.delete(1.0, tk.END)
            for sz in sizes:
                cnt = shelf_counts.get(sz, 0)
                if cnt == 0:
                    continue
                weights = []
                for var in category_vars[sz]:
                    try:
                        val = int(var.get() or "0")
                        weights.append(max(0, val))
                    except ValueError:
                        weights.append(0)
                        
                total_w = sum(weights)
                if total_w == 0:
                    dist = [cnt] + [0]*(len(weights)-1)
                else:
                    exact_counts = [(w * cnt) / total_w for w in weights]
                    base_counts = [int(math.floor(x)) for x in exact_counts]
                    remainders = [exact_counts[j] - base_counts[j] for j in range(len(weights))]
                    assigned_cnt = sum(base_counts)
                    rem_budget = cnt - assigned_cnt
                    dist = base_counts[:]
                    if rem_budget > 0:
                        indexed_rems = list(enumerate(remainders))
                        indexed_rems.sort(key=lambda x: x[1], reverse=True)
                        for j in range(int(rem_budget)):
                            dist[indexed_rems[j][0]] += 1
                
                # 简化显示标签
                parts = []
                for j, d in enumerate(dist):
                    if labels_map[sz][j].startswith('第一') or labels_map[sz][j].startswith('第二') or labels_map[sz][j].startswith('第三') or labels_map[sz][j].startswith('第四') or labels_map[sz][j].startswith('第五'):
                        name = str(j+1)
                    elif '万能' in labels_map[sz][j]:
                        name = '万能'
                    elif '路障' in labels_map[sz][j]:
                        name = '路障'
                    else:
                        name = '唯一'
                    parts.append(f"{name}:{d}个")
                preview_text.insert(tk.END, f"{sz} → {', '.join(parts)}\n")
            preview_text.config(state=tk.DISABLED)

        # 绑定实时更新
        for sz in sizes:
            for v in category_vars.get(sz, []):
                v.trace_add("write", lambda *args: update_preview())
                
        update_preview()

        btn_row = tk.Frame(dialog)
        btn_row.pack(pady=10)

        def on_export():
            try:
                ox = int(offset_x_var.get())
                oy = int(offset_y_var.get())
                sid = int(scene_id_var.get())
                spr = int(scene_praise_var.get())
            except ValueError:
                messagebox.showerror("错误", "参数必须是整数", parent=dialog)
                return
                
            distributions = {}
            for sz in sizes:
                cnt = shelf_counts.get(sz, 0)
                if cnt == 0:
                    distributions[sz] = []
                    continue
                weights = []
                for var in category_vars[sz]:
                    try:
                        weights.append(max(0, int(var.get() or "0")))
                    except ValueError:
                        weights.append(0)
                        
                total_w = sum(weights)
                if total_w == 0:
                    dist = [cnt] + [0]*(len(weights)-1)
                else:
                    exact_counts = [(w * cnt) / total_w for w in weights]
                    base_counts = [int(math.floor(x)) for x in exact_counts]
                    remainders = [exact_counts[j] - base_counts[j] for j in range(len(weights))]
                    assigned_cnt = sum(base_counts)
                    rem_budget = cnt - assigned_cnt
                    dist = base_counts[:]
                    if rem_budget > 0:
                        indexed_rems = list(enumerate(remainders))
                        indexed_rems.sort(key=lambda x: x[1], reverse=True)
                        for j in range(int(rem_budget)):
                            dist[indexed_rems[j][0]] += 1
                distributions[sz] = dist
            dialog.destroy()
            self._do_game_export(distributions, ox, oy, sid, spr)

        tk.Button(btn_row, text="计算并导出", command=on_export, bg="#4CAF50", fg="white",
                  font=("Arial", 11, "bold"), width=12).pack(side=tk.LEFT, padx=10)
        tk.Button(btn_row, text="取消", command=dialog.destroy, font=("Arial", 11), width=8).pack(side=tk.LEFT, padx=10)

    def _filter_effective_obstacles(self):
        """过滤掉不影响最短路径的无效障碍物，只保留关键障碍"""
        entrances, exits_list, obstacle_cells = [], [], []
        for r in range(self.rows):
            for c in range(self.cols):
                if self.grid[r][c] == CELL_ENTRANCE:
                    entrances.append((r, c))
                elif self.grid[r][c] == CELL_EXIT:
                    exits_list.append((r, c))
                elif self.grid[r][c] == CELL_OBSTACLE:
                    obstacle_cells.append((r, c))
        if not entrances or not exits_list:
            return []
        start = entrances[0]
        target_set = set(exits_list)

        def bfs_len(removed=None):
            """BFS求最短路径长度，removed若不为None则该障碍视为可通行"""
            visited = [[False] * self.cols for _ in range(self.rows)]
            visited[start[0]][start[1]] = True
            q = deque([(start, 0)])
            while q:
                (r, c), d = q.popleft()
                for dr, dc in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < self.rows and 0 <= nc < self.cols and not visited[nr][nc]:
                        cell = self.grid[nr][nc]
                        pos = (nr, nc)
                        ok = cell in (CELL_PATH, CELL_ENTRANCE, CELL_EXIT, CELL_GROUND)
                        if not ok and removed is not None and pos == removed:
                            ok = True
                        if ok:
                            visited[nr][nc] = True
                            if pos in target_set:
                                return d + 1
                            q.append((pos, d + 1))
            return None

        base_len = bfs_len()
        if base_len is None:
            return []
        effective = []
        for obs in obstacle_cells:
            new_len = bfs_len(obs)
            if new_len is not None and new_len < base_len:
                effective.append(obs)
        return effective

    def _do_game_export(self, distributions, offset_x, offset_y, scene_id, scene_praise):
        """构造游戏布局JSON并保存"""
        filepath = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json")],
            initialfile="layout_preset.json"
        )
        if not filepath:
            return

        self.status_var.set("正在过滤无效障碍物…")
        self.root.update_idletasks()
        effective_obstacles = self._filter_effective_obstacles()

        # 按尺寸分组货架
        shelves_by_size = {'1x1': [], '1x2': [], '2x2': []}
        for pts, stype in self.best_placed_shapes:
            shelves_by_size[stype].append(pts)

        template_map = {'1x1': SHELF_TEMPLATE_1x1, '1x2': SHELF_TEMPLATE_1x2, '2x2': SHELF_TEMPLATE_2x2}
        doodad_list = []

        for size in ['1x1', '1x2', '2x2']:
            shelves = shelves_by_size[size]
            dist = distributions.get(size, [])
            if not shelves or not dist:
                continue
            templates = template_map[size]
            shelf_idx = 0
            for cat_idx, cat_count in enumerate(dist):
                tid = templates[cat_idx] if cat_idx < len(templates) else templates[0]
                if tid == 0:
                    tid = templates[0]
                for _ in range(cat_count):
                    if shelf_idx >= len(shelves):
                        break
                    pts = shelves[shelf_idx]
                    shelf_idx += 1
                    first_pt = pts[0]
                    info = self.best_shelf_info.get(first_pt, {})
                    direction = info.get('direction')
                    # 核心改动：必须按照游戏引擎严格的细胞数组顺序、真实方位映射和锚点规则
                    # 解析求解器的格子坐标
                    if size == '1x1':
                        r, c = pts[0]
                        cell_pos = [{"x": offset_x - r, "y": offset_y - c}]
                        # 方向映射: 'top'变为游戏朝上(1), 'left'朝左(0), 'bottom'朝下(3), 'right'朝右(2)
                        e_dir = {'top': 1, 'left': 0, 'bottom': 3, 'right': 2}.get(direction, 0)
                        
                    elif size == '1x2':
                        if pts[0][0] == pts[1][0]: 
                            # solver中同行 (水平)。按游戏要求，水平大长边占两列(Y)。
                            # JS强制要求 cellPositions 先推入 Y+1对应的地图坐标
                            r, c = pts[0]
                            cell_pos = [
                                {"x": offset_x - r, "y": offset_y - (c + 1)},
                                {"x": offset_x - r, "y": offset_y - c}
                            ]
                            # 水平的合法 eDirection 为 1,3
                            e_dir = 1 if direction == 'top' else 3
                        else:
                            # solver中同列 (垂直)
                            r, c = pts[0]
                            cell_pos = [
                                {"x": offset_x - (r + 1), "y": offset_y - c},
                                {"x": offset_x - r, "y": offset_y - c}
                            ]
                            # 垂直的合法 eDirection 为 0,2
                            e_dir = 0 if direction == 'left' else 2
                            
                    elif size == '2x2':
                        r = min(p[0] for p in pts)
                        c = min(p[1] for p in pts)
                        # JS引擎的顺时针推入顺序
                        cell_pos = [
                            {"x": offset_x - (r + 1), "y": offset_y - (c + 1)},
                            {"x": offset_x - (r + 1), "y": offset_y - c},
                            {"x": offset_x - r,       "y": offset_y - c},
                            {"x": offset_x - r,       "y": offset_y - (c + 1)}
                        ]
                        e_dir = {'top': 0, 'left': 1, 'bottom': 2, 'right': 3}.get(direction, 0)

                    # worldPos 必须由 JS推入的第一个坐标 anchor 计算得出
                    ref_x = cell_pos[0]["x"]
                    ref_y = cell_pos[0]["y"]
                    w_x = (ref_x - ref_y) * 0.5
                    w_y = (ref_x + ref_y + 1) * 0.25

                    doodad_list.append({
                        "nTemplateID": tid,
                        "nLevel": 1,
                        "eDirection": e_dir,
                        "cellPositions": cell_pos,
                        "worldPos": {"x": w_x, "y": w_y},
                        "nGemID_MultiFacet": 0,
                        "nGemID_Capacity": 0,
                        "nGemID_SellCount": 0
                    })

        # 添加有效障碍物
        for r, c in effective_obstacles:
            cx, cy = offset_x - r, offset_y - c
            doodad_list.append({
                "nTemplateID": OBSTACLE_TEMPLATE_ID,
                "nLevel": 1,
                "eDirection": 3,
                "cellPositions": [{"x": cx, "y": cy}],
                "worldPos": {"x": (cx - cy) * 0.5, "y": (cx + cy + 1) * 0.25},
                "nGemID_MultiFacet": 0,
                "nGemID_Capacity": 0,
                "nGemID_SellCount": 0
            })

        layout = {
            "nVersion": 1,
            "szModID": "",
            "nSlotIndex": 2,
            "szName": "solver_export",
            "szDesc": "由超市布局求解器自动生成",
            "szIconPath": "icon/室内装饰/20030",
            "nSceneID": scene_id,
            "nScenePraise": scene_praise,
            "nCreateTime": int(time.time()),
            "doodadLayoutDataList": doodad_list
        }

        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(layout, f, indent=4, ensure_ascii=False)
            total_s = sum(len(shelves_by_size[s]) for s in shelves_by_size)
            orig_obs = sum(1 for r in range(self.rows) for c in range(self.cols) if self.grid[r][c] == CELL_OBSTACLE)
            self.status_var.set("布局预设导出完成")
            messagebox.showinfo("导出成功",
                f"布局预设已导出！\n\n"
                f"货架总数: {total_s}\n"
                f"有效障碍物: {len(effective_obstacles)} / {orig_obs} (已剔除 {orig_obs - len(effective_obstacles)} 个无效障碍)\n\n"
                f"文件: {filepath}")
        except Exception as e:
            messagebox.showerror("错误", f"导出失败: {e}")


if __name__ == "__main__":
    root = tk.Tk()
    app = SupermarketSolverApp(root)
    root.mainloop()