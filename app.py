import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import subprocess
import threading
import time
import os
import re
import json
import sys
import io
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, unquote
from PIL import Image, ImageGrab, ImageTk

# ===== 拆分出去的模块 =====
from core.settings_manager import SettingsManager
from core.adb_controller import AdbController
from task.task_manager import TaskManager
from ui.phone_control import PhoneControlWindow



# 图标修改
def resource_path(rel):
    """兼容 PyInstaller 单文件模式的资源路径"""
    base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)


class ADBGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("手机自动化控制程序")
        self.root.geometry("1150x750")
        self.root.resizable(True, True)

        # 初始化设置管理器
        self.settings_mgr = SettingsManager()

        # 初始化 ADB 路径
        self.adb_path = self.get_adb_path()
        self.log_message(f"ADB 路径: {self.adb_path}", "info")

        # 初始化 ADB 控制器
        self.adb = AdbController(
            adb_path=self.adb_path,
            logger=self.log_message,
            settings_mgr=self.settings_mgr,
        )

        # 初始化功能相关变量
        self.function_instances = None
        self.function_configs = {}

        # 加载外部功能模块
        self.load_functions_module()

        # 初始化任务管理器
        self.task_manager = TaskManager(self)

        # 变量
        self.devices = []
        self.selected_device = tk.StringVar()

        # API 服务
        self.api_server = None
        self.api_thread = None
        self.api_running = False
        self.api_port_var = tk.StringVar(value=str(self.settings_mgr.get_value("api_port", 8765)))
        self.api_enabled_var = tk.BooleanVar(value=False)

        # 创建界面
        self.create_widgets()

        # 初始刷新设备列表
        self.refresh_devices()

        # 加载设置到UI
        self.load_settings_to_ui()

        # 加载保存的任务队列
        self.load_task_queue_from_settings()

    def get_adb_path(self):
        """
        获取 ADB 可执行文件路径
        优先从当前目录的 platform-tools 文件夹查找
        如果找不到则使用系统 PATH 中的 adb
        """
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))

        platform_tools_adb = os.path.join(base_dir, 'platform-tools', 'adb')
        if sys.platform == 'win32':
            platform_tools_adb += '.exe'

        if os.path.exists(platform_tools_adb) and os.access(platform_tools_adb, os.X_OK):
            self.log_message(f"使用本地 ADB: {platform_tools_adb}", "info")
            return platform_tools_adb

        local_adb = os.path.join(base_dir, 'adb')
        if sys.platform == 'win32':
            local_adb += '.exe'
        if os.path.exists(local_adb) and os.access(local_adb, os.X_OK):
            self.log_message(f"使用本地 ADB: {local_adb}", "info")
            return local_adb

        self.log_message("使用系统 PATH 中的 ADB", "info")
        return 'adb'

    def load_functions_module(self):
        """加载外部功能模块"""
        try:
            # 打包后 = exe 所在目录；脚本运行 = main.py 所在目录
            if getattr(sys, 'frozen', False):
                base_dir = os.path.dirname(sys.executable)
            else:
                base_dir = os.path.dirname(os.path.abspath(__file__))

            functions_path = os.path.join(base_dir, "functions.py")

            if not os.path.exists(functions_path):
                self.log_message(f"未找到 {functions_path}，使用内置功能", "warning")
                self.load_builtin_functions()
                return False

            import importlib.util
            spec = importlib.util.spec_from_file_location("functions", functions_path)
            if spec is None or spec.loader is None:
                self.log_message(f"无法加载 {functions_path}", "error")
                self.load_builtin_functions()
                return False

            functions_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(functions_module)

            if hasattr(functions_module, 'FUNCTION_CONFIGS'):
                self.function_configs = functions_module.FUNCTION_CONFIGS
            else:
                self.log_message("functions.py 中没有 FUNCTION_CONFIGS", "warning")
                self.function_configs = {}

            if hasattr(functions_module, 'Functions'):
                self.function_instances = functions_module.Functions(self)

                for func_name in self.function_configs.keys():
                    if hasattr(self.function_instances, func_name):
                        setattr(self, func_name, getattr(self.function_instances, func_name))

                self.log_message(f"外部功能模块加载成功，共 {len(self.function_configs)} 个功能", "info")
                return True
            else:
                self.log_message("functions.py 中没有 Functions 类", "error")
                self.load_builtin_functions()
                return False

        except Exception as e:
            self.log_message(f"加载外部功能模块失败: {e}", "error")
            self.load_builtin_functions()
            return False

    def load_builtin_functions(self):
        """加载内置功能（作为后备）"""
        self.function_configs = {
            "测试消息": {"color": "#4CAF50", "desc": "执行城墙任务"},
        }
        self._define_builtin_functions()
        self.log_message("使用内置功能", "info")

    def _define_builtin_functions(self):
        def 测试消息():
            self.log_message("测试消息", "info")
        setattr(self, "测试消息", 测试消息)

    def reload_functions(self):
        """重新加载外部功能模块（支持热更新）"""
        try:
            for func_name in list(self.function_configs.keys()):
                if hasattr(self, func_name):
                    delattr(self, func_name)

            self.function_configs = {}
            self.function_instances = None

            if 'functions' in sys.modules:
                del sys.modules['functions']

            success = self.load_functions_module()

            if success:
                self.refresh_quick_buttons()
                self.update_task_combo()
                self.log_message("外部功能模块重新加载成功", "info")
                messagebox.showinfo("成功", f"功能模块已重新加载！共 {len(self.function_configs)} 个功能")
            else:
                messagebox.showerror("错误", "重新加载失败，请检查 functions.py 文件")

            return success
        except Exception as e:
            self.log_message(f"重新加载功能模块失败: {e}", "error")
            messagebox.showerror("错误", f"重新加载失败: {e}")
            return False

    # ==================================================================
    #  UI 构建
    # ==================================================================
    def create_widgets(self):
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        top_frame = ttk.Frame(main_frame, height=450)
        top_frame.pack(fill=tk.X, pady=(0, 5))
        top_frame.pack_propagate(False)

        left_frame = ttk.Frame(top_frame, width=200)
        left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 5))

        ttk.Label(left_frame, text="已连接的ADB设备", font=('Arial', 10, 'bold')).pack(pady=5)

        self.device_listbox = tk.Listbox(left_frame, height=8, selectmode=tk.SINGLE)
        self.device_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.device_listbox.bind('<<ListboxSelect>>', self.on_device_select)

        refresh_btn = ttk.Button(left_frame, text="刷新设备列表", command=self.refresh_devices)
        refresh_btn.pack(pady=5)

        reload_btn = ttk.Button(left_frame, text="重载功能",
                                command=self.reload_functions)
        reload_btn.pack(pady=2)

        ttk.Label(left_frame, text="当前选中设备:").pack(pady=(10, 0))
        self.selected_device_label = ttk.Label(left_frame, text="未选择", foreground="blue")
        self.selected_device_label.pack()

        right_frame = ttk.Frame(top_frame)
        right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.notebook = ttk.Notebook(right_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        self.task_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.task_tab, text="任务控制")
        self.create_task_tab()

        self.settings_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.settings_tab, text="配置信息")
        self.create_settings_tab()

        self.quick_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.quick_tab, text="快捷功能")
        self.create_quick_tab()

        self.test_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.test_tab, text="辅助功能")
        self.create_test_tab()

        log_frame = ttk.LabelFrame(main_frame, text="执行日志", padding=5)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(5, 0))

        self.log_text = scrolledtext.ScrolledText(log_frame, height=10, state=tk.NORMAL)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        self.log_text.config(state=tk.DISABLED)

    def create_task_tab(self):
        task_main_frame = ttk.Frame(self.task_tab)
        task_main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        top_half = ttk.Frame(task_main_frame)
        top_half.pack(fill=tk.BOTH, expand=True)

        list_frame = ttk.LabelFrame(top_half, text="任务队列", padding=5)
        list_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))

        columns = ("序号", "任务名称", "执行次数", "间隔(秒)")
        self.task_tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=12)

        self.task_tree.heading("序号", text="#")
        self.task_tree.heading("任务名称", text="任务名称")
        self.task_tree.heading("执行次数", text="执行次数")
        self.task_tree.heading("间隔(秒)", text="间隔(秒)")

        self.task_tree.column("序号", width=50)
        self.task_tree.column("任务名称", width=150)
        self.task_tree.column("执行次数", width=80)
        self.task_tree.column("间隔(秒)", width=80)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.task_tree.yview)
        self.task_tree.configure(yscrollcommand=scrollbar.set)

        self.task_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.task_context_menu = tk.Menu(self.task_tree, tearoff=0)
        self.task_context_menu.add_command(label="上移", command=lambda: self.move_task(-1))
        self.task_context_menu.add_command(label="下移", command=lambda: self.move_task(1))
        self.task_context_menu.add_separator()
        self.task_context_menu.add_command(label="删除", command=self.delete_task)
        self.task_context_menu.add_command(label="清空", command=self.clear_tasks)
        self.task_tree.bind("<Button-3>", self.show_task_context_menu)

        operation_frame = ttk.LabelFrame(top_half, text="任务操作", padding=10)
        operation_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 0))

        ttk.Label(operation_frame, text="添加任务到队列:", font=('Arial', 10, 'bold')).pack(pady=(0, 10))

        ttk.Label(operation_frame, text="选择任务:").pack(anchor=tk.W)
        self.task_combo = ttk.Combobox(operation_frame, width=20)
        self.task_combo.pack(fill=tk.X, pady=(0, 10))
        self.update_task_combo()

        ttk.Label(operation_frame, text="执行次数:").pack(anchor=tk.W)
        self.task_times_entry = ttk.Entry(operation_frame, width=10)
        self.task_times_entry.insert(0, "1")
        self.task_times_entry.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(operation_frame, text="执行间隔(秒):").pack(anchor=tk.W)
        self.task_interval_entry = ttk.Entry(operation_frame, width=10)
        self.task_interval_entry.insert(0, "1.0")
        self.task_interval_entry.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(operation_frame, text="添加到队列",
                   command=self.add_task_to_queue, width=18).pack(pady=5)

        bottom_half = ttk.Frame(task_main_frame)
        bottom_half.pack(fill=tk.X, pady=(10, 0))

        control_frame = ttk.LabelFrame(bottom_half, text="任务控制", padding=10)
        control_frame.pack(fill=tk.X)

        control_row1 = ttk.Frame(control_frame)
        control_row1.pack(fill=tk.X, pady=5)

        btn_frame = ttk.Frame(control_row1)
        btn_frame.pack(side=tk.LEFT, padx=(0, 20))

        self.start_btn = ttk.Button(btn_frame, text="启动任务",
                                    command=self.start_task_queue, width=20)
        self.start_btn.pack(side=tk.LEFT, padx=2)

        self.stop_btn = ttk.Button(btn_frame, text="停止任务",
                                   command=self.stop_task_queue, width=15, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=2)

        ttk.Button(btn_frame, text="清空队列",
                   command=self.clear_tasks, width=15).pack(side=tk.LEFT, padx=2)

        loop_frame = ttk.Frame(control_row1)
        loop_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)

        ttk.Label(loop_frame, text="循环次数:").pack(side=tk.LEFT, padx=5)
        self.loop_times_entry = ttk.Entry(loop_frame, width=8)
        self.loop_times_entry.insert(0, "1")
        self.loop_times_entry.pack(side=tk.LEFT, padx=2)
        ttk.Label(loop_frame, text="(-1无限)", font=('Arial', 9)).pack(side=tk.LEFT, padx=2)

        status_frame = ttk.Frame(control_frame)
        status_frame.pack(fill=tk.X, pady=5)

        self.task_status_label = ttk.Label(status_frame, text="状态: 空闲", foreground="green")
        self.task_status_label.pack(side=tk.LEFT, padx=5)

    def update_task_combo(self):
        tasks = list(self.function_configs.keys())
        custom_tasks = self.settings_mgr.get_value("custom_tasks", [])
        if isinstance(custom_tasks, list):
            tasks.extend(custom_tasks)
        self.task_combo['values'] = tasks
        if tasks:
            self.task_combo.set(tasks[0])

    def show_task_context_menu(self, event):
        item = self.task_tree.identify_row(event.y)
        if item:
            self.task_tree.selection_set(item)
            self.task_context_menu.post(event.x_root, event.y_root)

    def add_task_to_queue(self):
        task_name = self.task_combo.get()
        if not task_name:
            messagebox.showwarning("警告", "请选择任务")
            return

        try:
            times = int(self.task_times_entry.get())
            if times <= 0:
                raise ValueError("执行次数必须大于0")
        except ValueError:
            messagebox.showerror("错误", "请输入有效的执行次数")
            return

        try:
            interval = float(self.task_interval_entry.get())
            if interval < 0:
                raise ValueError("间隔不能为负数")
        except ValueError:
            messagebox.showerror("错误", "请输入有效的间隔时间")
            return

        self.task_manager.add_task(task_name, times, interval)
        self.refresh_task_list()
        self.log_message(f"已添加任务: {task_name} (执行{times}次, 间隔{interval}秒)", "info")
        self.save_task_queue_to_settings()

    def refresh_task_list(self):
        for item in self.task_tree.get_children():
            self.task_tree.delete(item)

        for idx, task in enumerate(self.task_manager.task_queue):
            task_name = task[0]
            times = task[1]
            interval = task[2] if len(task) > 2 else 1.0
            self.task_tree.insert("", tk.END, values=(idx + 1, task_name, times, interval))

    def delete_task(self):
        selected = self.task_tree.selection()
        if not selected:
            return
        item = selected[0]
        values = self.task_tree.item(item, "values")
        idx = int(values[0]) - 1
        if self.task_manager.remove_task(idx):
            self.refresh_task_list()
            self.save_task_queue_to_settings()
            self.log_message(f"已删除任务: {values[1]}", "info")

    def clear_tasks(self):
        if not self.task_manager.task_queue:
            return
        if messagebox.askyesno("确认清空", "确定要清空所有任务吗？"):
            self.task_manager.clear_tasks()
            self.refresh_task_list()
            self.save_task_queue_to_settings()
            self.log_message("已清空任务队列", "info")

    def move_task(self, direction):
        selected = self.task_tree.selection()
        if not selected:
            return
        item = selected[0]
        values = self.task_tree.item(item, "values")
        current_idx = int(values[0]) - 1
        new_idx = current_idx + direction

        if 0 <= new_idx < len(self.task_manager.task_queue):
            self.task_manager.task_queue[current_idx], self.task_manager.task_queue[new_idx] = \
                self.task_manager.task_queue[new_idx], self.task_manager.task_queue[current_idx]
            self.refresh_task_list()
            self.save_task_queue_to_settings()

            for child in self.task_tree.get_children():
                if self.task_tree.item(child, "values")[0] == str(new_idx + 1):
                    self.task_tree.selection_set(child)
                    break

    def save_task_queue_to_settings(self):
        task_list = []
        for task in self.task_manager.task_queue:
            task_list.append({
                "name": task[0],
                "times": task[1],
                "interval": task[2] if len(task) > 2 else 1.0
            })
        self.settings_mgr.set_value("task_queue", task_list)

    def load_task_queue_from_settings(self):
        task_list = self.settings_mgr.get_value("task_queue", [])
        if task_list and isinstance(task_list, list):
            self.task_manager.clear_tasks()
            for task in task_list:
                if isinstance(task, dict) and "name" in task:
                    self.task_manager.add_task(
                        task["name"],
                        task.get("times", 1),
                        task.get("interval", 1.0)
                    )
            self.refresh_task_list()
            self.log_message(f"已加载 {len(task_list)} 个任务", "info")

    def start_task_queue(self):
        if self.task_manager.is_running:
            return
        try:
            max_loops = int(self.loop_times_entry.get())
            self.task_manager.set_max_loops(max_loops)
        except ValueError:
            self.task_manager.set_max_loops(-1)

        if self.task_manager.start():
            self.start_btn.config(state=tk.DISABLED)
            self.stop_btn.config(state=tk.NORMAL)
            self.log_message(f"任务队列已启动 (循环次数: {'无限' if self.task_manager.max_loops == -1 else self.task_manager.max_loops})", "info")

    def stop_task_queue(self):
        if not self.task_manager.is_running:
            return
        self.task_manager.stop()
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)

    def update_task_status(self, status_text, color="green"):
        self.task_status_label.config(text=f"状态: {status_text}", foreground=color)

    def on_task_finished(self):
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)

    def create_quick_tab(self):
        main_frame = ttk.Frame(self.quick_tab)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        canvas = tk.Canvas(main_frame)
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.quick_buttons = {}
        self.create_function_buttons(scrollable_frame)

    def create_function_buttons(self, parent_frame):
        for widget in parent_frame.winfo_children():
            widget.destroy()

        row = 0
        col = 0
        max_cols = 5

        for name, config in self.function_configs.items():
            btn_frame = ttk.LabelFrame(parent_frame, text=name, padding=10)
            btn_frame.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")

            btn = tk.Button(
                btn_frame,
                text=f"{name}",
                font=('Arial', 12, 'bold'),
                bg=config.get("color", "#E0E0E0"),
                fg="white",
                padx=20,
                pady=15,
                command=lambda n=name: self.execute_function(n),
                cursor="hand2"
            )
            btn.pack(fill=tk.X, pady=5)

            status_label = ttk.Label(btn_frame, text="就绪", foreground="green", font=('Arial', 8))
            status_label.pack(pady=5)

            self.quick_buttons[name] = {
                "button": btn,
                "status": status_label,
                "config": config
            }

            col += 1
            if col >= max_cols:
                col = 0
                row += 1

        parent_frame.grid_columnconfigure(0, weight=1)
        parent_frame.grid_columnconfigure(1, weight=1)

    def refresh_quick_buttons(self):
        for child in self.quick_tab.winfo_children():
            child.destroy()
        self.create_quick_tab()
        self.log_message("功能按钮已刷新", "info")

    def execute_function(self, func_name):
        if func_name not in self.quick_buttons:
            return

        status_label = self.quick_buttons[func_name]["status"]
        status_label.config(text="执行中...", foreground="orange")
        self.log_message(f"开始执行: {func_name}", "info")

        def run_func():
            try:
                if not self.get_selected_device():
                    status_label.config(text="请选择设备", foreground="red")
                    self.log_message(f"执行 {func_name} 失败: 未选择设备", "error")
                    return

                if hasattr(self, func_name):
                    getattr(self, func_name)()
                elif self.function_instances and hasattr(self.function_instances, func_name):
                    getattr(self.function_instances, func_name)()
                else:
                    raise AttributeError(f"功能 '{func_name}' 不存在")

                status_label.config(text="执行完成 ✓", foreground="green")
                self.log_message(f"功能 '{func_name}' 执行完成", "info")
            except Exception as e:
                status_label.config(text="执行失败 ✗", foreground="red")
                self.log_message(f"功能 '{func_name}' 执行失败: {e}", "error")

        threading.Thread(target=run_func, daemon=True).start()

    def create_settings_tab(self):
        top_frame = ttk.Frame(self.settings_tab)
        top_frame.pack(fill=tk.X, pady=5, padx=5)

        ttk.Button(top_frame, text="添加新设置", command=self.add_setting_dialog).pack(side=tk.LEFT, padx=5)
        ttk.Button(top_frame, text="刷新列表", command=self.refresh_settings_display).pack(side=tk.LEFT, padx=5)
        ttk.Button(top_frame, text="导出设置", command=self.export_settings).pack(side=tk.LEFT, padx=5)
        ttk.Button(top_frame, text="导入设置", command=self.import_settings).pack(side=tk.LEFT, padx=5)

        list_frame = ttk.LabelFrame(self.settings_tab, text="设置列表", padding=5)
        list_frame.pack(fill=tk.X, expand=False, pady=5, padx=5)

        columns = ("键", "值", "类型")
        self.settings_tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=13)

        self.settings_tree.heading("键", text="键名")
        self.settings_tree.heading("值", text="值")
        self.settings_tree.heading("类型", text="类型")

        self.settings_tree.column("键", width=200)
        self.settings_tree.column("值", width=300)
        self.settings_tree.column("类型", width=100)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.settings_tree.yview)
        self.settings_tree.configure(yscrollcommand=scrollbar.set)

        self.settings_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.create_settings_context_menu()

        bottom_frame = ttk.Frame(self.settings_tab)
        bottom_frame.pack(fill=tk.X, pady=5, padx=5)

        ttk.Button(bottom_frame, text="修改选中", command=self.modify_setting_dialog).pack(side=tk.LEFT, padx=5)
        ttk.Button(bottom_frame, text="删除选中", command=self.delete_setting).pack(side=tk.LEFT, padx=5)

    def create_settings_context_menu(self):
        self.context_menu = tk.Menu(self.settings_tree, tearoff=0)
        self.context_menu.add_command(label="修改", command=self.modify_setting_dialog)
        self.context_menu.add_command(label="删除", command=self.delete_setting)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="复制键名", command=self.copy_key_name)
        self.context_menu.add_command(label="复制值", command=self.copy_value)
        self.settings_tree.bind("<Button-3>", self.show_settings_context_menu)

    def show_settings_context_menu(self, event):
        item = self.settings_tree.identify_row(event.y)
        if item:
            self.settings_tree.selection_set(item)
            self.context_menu.post(event.x_root, event.y_root)

    def copy_key_name(self):
        selected = self.settings_tree.selection()
        if selected:
            item = selected[0]
            key = self.settings_tree.item(item, "values")[0]
            self.root.clipboard_clear()
            self.root.clipboard_append(key)
            messagebox.showinfo("成功", f"已复制键名: {key}")

    def copy_value(self):
        selected = self.settings_tree.selection()
        if selected:
            item = selected[0]
            value = self.settings_tree.item(item, "values")[1]
            self.root.clipboard_clear()
            self.root.clipboard_append(value)
            messagebox.showinfo("成功", f"已复制值: {value}")

    def load_settings_to_ui(self):
        for item in self.settings_tree.get_children():
            self.settings_tree.delete(item)

        all_settings = self.settings_mgr.get_all()
        for key, value in all_settings.items():
            value_type = type(value).__name__
            display_value = str(value)
            if len(display_value) > 50:
                display_value = display_value[:47] + "..."
            self.settings_tree.insert("", tk.END, values=(key, display_value, value_type))

    def refresh_settings_display(self):
        self.settings_mgr.load_settings()
        self.load_settings_to_ui()
        self.log_message("设置列表已刷新", "info")

    def add_setting_dialog(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("添加新设置")
        dialog.geometry("400x250")
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(dialog, text="键名:").pack(pady=(10, 0))
        key_entry = ttk.Entry(dialog, width=40)
        key_entry.pack(pady=5)

        ttk.Label(dialog, text="值:").pack(pady=(10, 0))
        value_entry = ttk.Entry(dialog, width=40)
        value_entry.pack(pady=5)

        type_frame = ttk.Frame(dialog)
        type_frame.pack(pady=10)

        ttk.Label(type_frame, text="类型:").pack(side=tk.LEFT, padx=5)
        type_var = tk.StringVar(value="字符串")
        type_combo = ttk.Combobox(type_frame, textvariable=type_var,
                                  values=["字符串", "整数", "浮点数", "布尔值"], width=15)
        type_combo.pack(side=tk.LEFT, padx=5)

        def confirm_add():
            key = key_entry.get().strip()
            value_str = value_entry.get().strip()

            if not key:
                messagebox.showerror("错误", "请输入键名")
                return
            if not value_str:
                messagebox.showerror("错误", "请输入值")
                return

            try:
                type_choice = type_var.get()
                if type_choice == "整数":
                    value = int(value_str)
                elif type_choice == "浮点数":
                    value = float(value_str)
                elif type_choice == "布尔值":
                    value = value_str.lower() in ("true", "1", "是", "yes")
                else:
                    value = value_str
            except ValueError:
                messagebox.showerror("错误", f"值 '{value_str}' 无法转换为 {type_choice}")
                return

            self.settings_mgr.set_value(key, value)
            self.load_settings_to_ui()
            self.log_message(f"添加设置: {key} = {value}", "info")
            dialog.destroy()

        ttk.Button(dialog, text="确认添加", command=confirm_add).pack(pady=10)
        ttk.Button(dialog, text="取消", command=dialog.destroy).pack()

    def modify_setting_dialog(self):
        selected = self.settings_tree.selection()
        if not selected:
            messagebox.showwarning("警告", "请先选择一个设置项")
            return

        item = selected[0]
        values = self.settings_tree.item(item, "values")
        old_key = values[0]
        old_value = self.settings_mgr.get_value(old_key)

        dialog = tk.Toplevel(self.root)
        dialog.title(f"修改设置: {old_key}")
        dialog.geometry("400x250")
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(dialog, text="键名:").pack(pady=(10, 0))
        key_label = ttk.Label(dialog, text=old_key, foreground="blue")
        key_label.pack(pady=5)

        ttk.Label(dialog, text="新值:").pack(pady=(10, 0))
        value_entry = ttk.Entry(dialog, width=40)
        value_entry.insert(0, str(old_value))
        value_entry.pack(pady=5)

        def confirm_modify():
            new_value_str = value_entry.get().strip()
            if not new_value_str:
                messagebox.showerror("错误", "请输入值")
                return

            old_type = type(old_value)
            try:
                if old_type == int:
                    new_value = int(new_value_str)
                elif old_type == float:
                    new_value = float(new_value_str)
                elif old_type == bool:
                    new_value = new_value_str.lower() in ("true", "1", "是", "yes")
                else:
                    new_value = new_value_str
            except ValueError:
                messagebox.showerror("错误", f"值 '{new_value_str}' 无法转换为 {old_type.__name__}")
                return

            self.settings_mgr.set_value(old_key, new_value)
            self.load_settings_to_ui()
            self.log_message(f"修改设置: {old_key} = {new_value}", "info")
            dialog.destroy()

        ttk.Button(dialog, text="确认修改", command=confirm_modify).pack(pady=10)
        ttk.Button(dialog, text="取消", command=dialog.destroy).pack()

    def delete_setting(self):
        selected = self.settings_tree.selection()
        if not selected:
            messagebox.showwarning("警告", "请先选择一个设置项")
            return

        item = selected[0]
        values = self.settings_tree.item(item, "values")
        key = values[0]

        if messagebox.askyesno("确认删除", f"确定要删除设置 '{key}' 吗？"):
            if self.settings_mgr.delete_key(key):
                self.load_settings_to_ui()
                self.log_message(f"删除设置: {key}", "info")
            else:
                messagebox.showerror("错误", "删除设置失败")

    def export_settings(self):
        file_path = filedialog.asksaveasfilename(
            title="导出设置",
            defaultextension=".json",
            filetypes=[("JSON文件", "*.json"), ("所有文件", "*.*")]
        )
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(self.settings_mgr.get_all(), f, ensure_ascii=False, indent=2)
                messagebox.showinfo("成功", f"设置已导出到: {file_path}")
                self.log_message(f"设置已导出到: {file_path}", "info")
            except Exception as e:
                messagebox.showerror("错误", f"导出失败: {e}")

    def import_settings(self):
        file_path = filedialog.askopenfilename(
            title="导入设置",
            filetypes=[("JSON文件", "*.json"), ("所有文件", "*.*")]
        )
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    imported = json.load(f)

                if messagebox.askyesno("确认导入", f"将导入 {len(imported)} 个设置项，是否继续？"):
                    self.settings_mgr.update_settings(imported)
                    self.load_settings_to_ui()
                    self.log_message(f"已导入 {len(imported)} 个设置项", "info")
                    messagebox.showinfo("成功", f"成功导入 {len(imported)} 个设置项")
            except Exception as e:
                messagebox.showerror("错误", f"导入失败: {e}")


    def create_test_tab(self):
        coord_frame = ttk.LabelFrame(self.test_tab, text="控制手机", padding=10)
        coord_frame.pack(fill=tk.X, pady=5, padx=5)

        ttk.Button(coord_frame, text="📱 控制手机",
                   command=self.open_phone_control_window, width=20).pack(pady=5)
        ttk.Label(coord_frame,
                  text="打开实时画面窗口：支持开始/暂停实时获取、截图、点击计算相对与真实坐标、开关模拟真实点击",
                  foreground="gray").pack(pady=(0, 5))

        text_frame = ttk.LabelFrame(self.test_tab, text="ADBKeyboard文字输入测试", padding=10)
        text_frame.pack(fill=tk.X, pady=5, padx=5)

        status_display_frame = ttk.Frame(text_frame)
        status_display_frame.pack(fill=tk.X, pady=5)

        self.adbkeyboard_status_label = ttk.Label(status_display_frame, text="检测ADBKeyboard状态...", foreground="blue")
        self.adbkeyboard_status_label.pack(side=tk.LEFT, padx=5)

        btn_container = ttk.Frame(status_display_frame)
        btn_container.pack(side=tk.RIGHT, padx=5)

        ttk.Button(btn_container, text="安装 ADBKeyboard",
                   command=self.install_adbkeyboard, width=18).pack(side=tk.RIGHT, padx=2)

        ttk.Button(btn_container, text="检测并激活",
                   command=self.check_and_activate_adbkeyboard, width=15).pack(side=tk.RIGHT, padx=2)

        text_input_frame = ttk.Frame(text_frame)
        text_input_frame.pack(fill=tk.X, pady=5)

        ttk.Label(text_input_frame, text="输入文本:").pack(side=tk.LEFT, padx=5)
        self.test_text_entry = ttk.Entry(text_input_frame, width=50)
        self.test_text_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        self.test_text_entry.insert(0, "你好世界 Hello World! 123 😊")

        text_btn_frame = ttk.Frame(text_frame)
        text_btn_frame.pack(fill=tk.X, pady=5)

        ttk.Button(text_btn_frame, text="测试输入",
                   command=self.test_adbkeyboard_input, width=12).pack(side=tk.LEFT, padx=5)

        ttk.Button(text_btn_frame, text="使用说明",
                   command=self.show_adbkeyboard_help, width=12).pack(side=tk.LEFT, padx=5)

        api_frame = ttk.LabelFrame(self.test_tab, text="API 调用服务", padding=10)
        api_frame.pack(fill=tk.X, pady=5, padx=5)

        api_row1 = ttk.Frame(api_frame)
        api_row1.pack(fill=tk.X, pady=5)

        ttk.Label(api_row1, text="监听端口:").pack(side=tk.LEFT, padx=5)
        self.api_port_entry = ttk.Entry(api_row1, textvariable=self.api_port_var, width=8)
        self.api_port_entry.pack(side=tk.LEFT, padx=5)

        self.api_toggle_btn = ttk.Button(
            api_row1, text="启动 API 服务",
            command=self.toggle_api_server, width=18)
        self.api_toggle_btn.pack(side=tk.LEFT, padx=10)

        self.api_status_label = ttk.Label(api_row1, text="⏹ 已停止", foreground="red")
        self.api_status_label.pack(side=tk.LEFT, padx=10)

        tip = (
            "GET http://127.0.0.1:<端口>/run/<功能名>   → 执行一次该功能\n"
            "GET http://127.0.0.1:<端口>/list           → 列出所有可调用功能"
        )
        ttk.Label(api_frame, text=tip, foreground="gray", justify=tk.LEFT).pack(anchor=tk.W, pady=(0, 5))

    # ==================================================================
    #  HTTP API 服务
    # ==================================================================
    def start_api_server(self):
        if self.api_running:
            self.log_message("API 服务已在运行", "warning")
            return False

        try:
            port = int(self.api_port_var.get())
            if not (1 <= port <= 65535):
                raise ValueError
        except ValueError:
            messagebox.showerror("错误", "端口号必须是 1~65535 之间的整数")
            return False

        app_ref = self  # 闭包引用

        class ApiHandler(BaseHTTPRequestHandler):
            def log_message(self, fmt, *args):
                # 用我们自己的日志，屏蔽默认 stderr 输出
                app_ref.log_message("API: " + (fmt % args), "info")

            def _send(self, code, body):
                data = json.dumps(body, ensure_ascii=False).encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):
                parsed = urlparse(self.path)
                path = unquote(parsed.path)
                parts = [p for p in path.split("/") if p]

                # 健康检查
                if path == "/":
                    self._send(200, {"ok": True, "msg": "ADB API running"})
                    return

                # /run/<功能名>
                if len(parts) == 2 and parts[0] == "run":
                    func_name = parts[1]
                    if not hasattr(app_ref, func_name):
                        self._send(404, {
                            "ok": False,
                            "error": f"功能 '{func_name}' 不存在",
                        })
                        return
                    try:
                        device = app_ref.selected_device.get()
                        if not device:
                            self._send(400, {"ok": False, "error": "未选择设备"})
                            return

                        app_ref.log_message(f"API 调用功能: {func_name}", "info")
                        # 在线程里跑，避免阻塞
                        threading.Thread(
                            target=lambda: getattr(app_ref, func_name)(),
                            daemon=True,
                        ).start()
                        self._send(200, {"ok": True, "func": func_name})
                    except Exception as e:
                        self._send(500, {"ok": False, "error": str(e)})
                    return

                # /list 列出所有可调用功能
                if path == "/list":
                    funcs = []
                    for name in app_ref.function_configs.keys():
                        if hasattr(app_ref, name):
                            funcs.append(name)
                    self._send(200, {"ok": True, "functions": funcs})
                    return

                self._send(404, {"ok": False, "error": "未知路径"})

        try:
            self.api_server = ThreadingHTTPServer(("0.0.0.0", port), ApiHandler)
        except OSError as e:
            messagebox.showerror("错误", f"无法监听端口 {port}: {e}")
            return False

        self.api_running = True
        self.api_thread = threading.Thread(target=self.api_server.serve_forever, daemon=True)
        self.api_thread.start()

        self.settings_mgr.set_value("api_port", port)
        self.api_enabled_var.set(True)
        self.api_status_label.config(text=f"✅ 运行中 (端口 {port})", foreground="green")
        self.api_toggle_btn.config(text="关闭 API 服务")
        self.log_message(f"API 服务已启动: http://127.0.0.1:{port}/run/<功能名>", "info")
        return True

    def stop_api_server(self):
        if not self.api_running:
            return
        try:
            self.api_server.shutdown()
            self.api_server.server_close()
        except Exception as e:
            self.log_message(f"关闭 API 服务异常: {e}", "warning")
        self.api_server = None
        self.api_thread = None
        self.api_running = False
        self.api_enabled_var.set(False)
        self.api_status_label.config(text="⏹ 已停止", foreground="red")
        self.api_toggle_btn.config(text="启动 API 服务")
        self.log_message("API 服务已停止", "info")

    def toggle_api_server(self):
        if self.api_running:
            self.stop_api_server()
        else:
            self.start_api_server()

    def on_close(self):
        try:
            self.stop_api_server()
        except Exception:
            pass
        self.root.destroy()
    def open_phone_control_window(self):
        device = self.get_selected_device()
        if not device:
            return
        existing = getattr(self, '_phone_control_window', None)
        if existing is not None and existing.window.winfo_exists():
            existing.window.lift()
            return
        self._phone_control_window = PhoneControlWindow(self)

    def refresh_devices(self, retry_count=2):
        self.device_listbox.delete(0, tk.END)

        adb_path = self.adb_path
        self.log_message("ADB目录:" + adb_path, "info")

        for attempt in range(retry_count + 1):
            try:
                if attempt == 0:
                    self.log_message("正在启动 ADB 服务...", "info")
                    self.adb.start_server()
                    time.sleep(0.5)

                devices = self.adb.list_devices()

                for serial in devices:
                    self.device_listbox.insert(tk.END, serial)

                if not devices:
                    self.device_listbox.insert(tk.END, "没有已连接的设备")
                    self.selected_device.set("")
                    self.selected_device_label.config(text="未选择")
                else:
                    self.device_listbox.selection_set(0)
                    self.on_device_select(None)

                self.log_message(f"设备列表已刷新 (发现 {len(devices)} 个设备)", "info")
                return

            except Exception as e:
                if attempt < retry_count:
                    self.log_message(f"刷新设备列表失败，第 {attempt + 1} 次重试: {e}", "warning")
                    time.sleep(1)
                else:
                    self.log_message(f"刷新设备列表失败: {e}", "error")
                    messagebox.showerror("错误", f"ADB命令执行失败: {e}")

    def on_device_select(self, event):
        selection = self.device_listbox.curselection()
        if selection:
            index = selection[0]
            device = self.device_listbox.get(index)
            if device != "没有已连接的设备":
                self.selected_device.set(device)
                self.selected_device_label.config(text=device)
                self.log_message(f"选中设备: {device}", "info")
            else:
                self.selected_device.set("")
                self.selected_device_label.config(text="未选择")
        else:
            self.selected_device.set("")
            self.selected_device_label.config(text="未选择")

    def get_selected_device(self):
        device = self.selected_device.get()
        if not device:
            messagebox.showwarning("警告", "请先选择一个设备")
            return None
        return device

    # ==================================================================
    #  以下是对外兼容的包装方法 —— functions.py 里调用 self.app.xxx(...) 不用改
    # ==================================================================

    def get_color(self, x, y, device=None):
        """获取指定点颜色值"""
        if device is None:
            device = self.get_selected_device()
            if not device:
                return None
        return self.adb.get_color(device, x, y)

    def press_back(self, device=None):
        """按下返回键"""
        if device is None:
            device = self.get_selected_device()
            if not device:
                return False
        return self.adb.press_back(device)

    def click_point(self, x, y, device=None, delay=None):
        """点击指定坐标"""
        if device is None:
            device = self.get_selected_device()
            if not device:
                return False
        return self.adb.click_point(device, x, y, delay=delay)

    def long_press(self, x, y, duration=1.0, device=None, tap_offset=0.08):
        """长按"""
        if device is None:
            device = self.get_selected_device()
        if not device:
            self.log_message("长按失败：未选择设备", "error")
            return False
        return self.adb.long_press(device, x, y, duration=duration, tap_offset=tap_offset)

    def swipe(self, x1, y1, x2, y2, duration=300, device=None):
        """滑动"""
        if device is None:
            device = self.get_selected_device()
            if not device:
                return False
        return self.adb.swipe(device, x1, y1, x2, y2, duration=duration)

    def find_image(self, image_path, device=None, threshold=None, use_cache=False):
        """找图（最高分）"""
        if device is None:
            device = self.get_selected_device()
            if not device:
                return None
        return self.adb.find_image(device, image_path, threshold=threshold, use_cache=use_cache)

    def find_image_first(self, image_path, device=None, threshold=None, use_cache=False):
        """找图（最左上）"""
        if device is None:
            device = self.get_selected_device()
            if not device:
                return None
        return self.adb.find_image_first(device, image_path, threshold=threshold, use_cache=use_cache)

    def get_screen_texts(self, device=None, include_desc=True):
        """
        获取当前屏幕所有文字 + 中心坐标
        返回 list[dict]，失败返回 None
        """
        if device is None:
            device = self.get_selected_device()
            if not device:
                return None
        return self.adb.get_screen_texts(device, include_desc=include_desc)

    def input_number_with_backspace(self, target_number, delete_count=1, device=None):
        if device is None:
            device = self.get_selected_device()
            if not device:
                return False
        return self.adb.input_number_with_backspace(device, target_number, delete_count=delete_count)

    def input_chinese(self, text, device=None):
        """输入中文（对外保留这个名字）"""
        if device is None:
            device = self.get_selected_device()
            if not device:
                return False

        success, err = self.adb.input_text(device, text)
        if not success:
            messagebox.showerror("输入失败",
                f"输入失败！\n\n错误信息: {err}\n\n"
                "可能的原因：\n"
                "1. 当前输入法不是 ADBKeyboard\n"
                "2. 输入框未获得焦点（请点击输入框）\n"
                "3. ADBKeyboard未正确安装\n\n"
                "请确保：\n"
                "• 已手动切换输入法为 ADBKeyboard\n"
                "• 输入框处于激活状态（光标闪烁）")
        return success

    def install_adbkeyboard(self, device=None):
        """安装 ADBKeyboard（含 UI 状态更新）"""
        if device is None:
            device = self.get_selected_device()
            if not device:
                self.adbkeyboard_status_label.config(text="❌ 请先选择设备", foreground="red")
                return False

        self.adbkeyboard_status_label.config(text="🔄 检查APK文件...", foreground="orange")
        self.root.update()

        success, msg = self.adb.install_adbkeyboard(device)

        if success:
            self.adbkeyboard_status_label.config(text="✅ 安装成功！", foreground="green")
            messagebox.showinfo("安装成功", "ADBKeyboard 已成功安装到设备！\n\n点击「检测并激活」切换输入法。")
            # 自动尝试激活
            self.check_and_activate_adbkeyboard(device)
            return True
        else:
            if "INSTALL_FAILED_ALREADY_EXISTS" in msg:
                self.adbkeyboard_status_label.config(text="⚠️ 已安装 (可重新安装)", foreground="orange")
                messagebox.showinfo("已安装", "ADBKeyboard 已经安装在设备上。\n\n如需重新安装，请先卸载旧版本。")
            else:
                self.adbkeyboard_status_label.config(text="❌ 安装失败", foreground="red")
                messagebox.showerror("安装失败",
                    f"安装失败:\n{msg}\n\n可能的原因:\n1. 设备未连接\n2. USB调试未开启\n3. 安装权限不足")
            return False

    def check_and_activate_adbkeyboard(self, device=None):
        """检测并尝试激活 ADBKeyboard（含 UI 状态更新）"""
        if device is None:
            device = self.get_selected_device()
            if not device:
                self.adbkeyboard_status_label.config(text="❌ 未选择设备", foreground="red")
                return False

        self.adbkeyboard_status_label.config(text="🔄 正在尝试切换输入法...", foreground="orange")
        self.log_message("🔄 正在尝试切换到ADBKeyboard...", "info")

        installed, switched, err = self.adb._try_switch_adbkeyboard(device)

        if not installed:
            self.adbkeyboard_status_label.config(text="❌ ADBKeyboard未安装", foreground="red")
            self.log_message("❌ ADBKeyboard未安装，请先安装ADBKeyboard.apk", "error")
            messagebox.showerror("错误",
                "ADBKeyboard未安装！\n\n"
                "请下载 ADBKeyboard.apk 并安装：\n"
                "1. 下载 ADBKeyboard.apk\n"
                "2. 执行: adb install ADBKeyboard.apk")
            return False

        if switched:
            self.adbkeyboard_status_label.config(text="✅ ADBKeyboard已激活", foreground="green")
            self.log_message("✅ ADBKeyboard已成功切换为当前输入法", "info")
        else:
            self.adbkeyboard_status_label.config(
                text="⚠️ ADBKeyboard已安装 (请手动切换输入法)",
                foreground="orange"
            )
            self.log_message(f"⚠️ 无法自动切换输入法: {err}", "warning")
            self.log_message("💡 请手动在设备设置中切换输入法为 ADBKeyboard", "info")

            if not hasattr(self, '_manual_switch_shown'):
                self._manual_switch_shown = True
                messagebox.showinfo("手动切换提示",
                    "ADBKeyboard已安装，但无法自动切换输入法。\n\n"
                    "请按以下步骤手动切换：\n"
                    "1. 在模拟器/设备中打开任意输入框\n"
                    "2. 点击键盘切换图标\n"
                    "3. 选择 ADBKeyboard 输入法\n\n"
                    "之后就可以正常输入中文了！")

        return True

    def ensure_adbkeyboard_ready(self, device=None):
        return self.check_and_activate_adbkeyboard(device)

    def test_adbkeyboard_input(self):
        device = self.get_selected_device()
        if not device:
            return
        text = self.test_text_entry.get().strip()
        if not text:
            messagebox.showwarning("警告", "请输入要测试的文本")
            return
        self.input_chinese(text)

    def show_adbkeyboard_help(self):
        help_text = """
        📖 ADBKeyboard 使用说明

        ═══════════════════════════════════════

        📌 自动检测与激活
        • 程序会自动检测ADBKeyboard状态
        • 如果已安装但未激活，会自动激活
        • 状态显示在"检测并激活"按钮旁边

        📌 首次使用准备
        1. 下载 ADBKeyboard.apk
        2. 使用以下命令安装：
        adb install ADBKeyboard.apk

        📌 使用步骤
        1. 选择设备
        2. 点击"检测并激活"按钮
        3. 在模拟器中点击输入框（获得焦点）
        4. 输入文本并点击"输入文本"按钮

        📌 手动激活命令
        adb shell ime enable com.android.adbkeyboard/.AdbIME
        adb shell ime set com.android.adbkeyboard/.AdbIME

        📌 ADBKeyboard优势
        ✅ 支持中文和特殊字符
        ✅ 不需要系统剪贴板权限
        ✅ 输入速度快
        ✅ 支持Base64编码，兼容性好
        ✅ 自动激活，无需手动设置

        ═══════════════════════════════════════
        """
        messagebox.showinfo("ADBKeyboard使用说明", help_text)

    # ---------- 辅助函数 ----------
    def log_message(self, msg, level="info"):
        self.root.after(0, self._log_message, msg, level)

    def _log_message(self, msg, level="info"):
        timestamp = time.strftime("%H:%M:%S")
        prefix = {
            "info": "[INFO]",
            "error": "[ERROR]",
            "warning": "[WARN]"
        }.get(level, "[INFO]")

        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, f"{timestamp} {prefix} {msg}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)


if __name__ == "__main__":
    root = tk.Tk()
    try:
        root.iconbitmap(resource_path("app.ico"))
    except Exception as e:
        print("设置窗口图标失败:", e)
    app = ADBGUI(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()