import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import subprocess
import threading
import time
import os
import re
import json
import sys
import urllib.request
from PIL import Image, ImageGrab

class SettingsManager:
    """设置管理器 - 负责加载、保存和管理设置数据"""
    
    def __init__(self):
        self.settings_file = "adb_settings.json"
        self.settings = {}
        
        self.load_settings()
    
    def load_settings(self):
        """从文件加载设置"""
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    self.settings = json.load(f)
            else:
                # 创建默认设置
                self.settings = {
                    "task_interval": 1.0,
                    "click_delay": 0.5,
                    "retry_times": 3,
                    "image_threshold": 0.8,
                    "default_x": 100,
                    "default_y": 100,
                    "派出兵力": "1",
                    "搜索点坐标X": "0@0",
                    "搜索点坐标Y": "0@0"
                }
                self.save_settings()
        except Exception as e:
            print(f"加载设置失败: {e}")
            self.settings = {}
    
    def save_settings(self):
        """保存设置到文件"""
        try:
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"保存设置失败: {e}")
            return False
    
    def get_value(self, key, default=None):
        """获取设置值"""
        return self.settings.get(key, default)
    
    def set_value(self, key, value):
        """设置值并立即保存"""
        self.settings[key] = value
        self.save_settings()
    
    def delete_key(self, key):
        """删除键值对"""
        if key in self.settings:
            del self.settings[key]
            self.save_settings()
            return True
        return False
    
    def get_all(self):
        """获取所有设置"""
        return self.settings.copy()
    
    def update_settings(self, new_settings):
        """批量更新设置"""
        self.settings.update(new_settings)
        self.save_settings()


class TaskManager:
    """任务管理器 - 管理任务队列和执行"""
    
    def __init__(self, app):
        self.app = app
        self.task_queue = []  # 任务队列: [(任务名称, 执行次数, 执行间隔)]
        self.is_running = False
        self.stop_event = threading.Event()
        self.thread = None
        self.current_task_index = -1
        self.current_task_remaining = 0
        self.loop_count = 0  # 当前循环次数
        self.max_loops = -1  # -1表示无限循环
    
    def set_max_loops(self, max_loops):
        """设置最大循环次数，-1表示无限循环"""
        self.max_loops = max_loops
    
    def add_task(self, task_name, times=1, interval=1.0):
        """添加任务到队列末尾"""
        self.task_queue.append([task_name, times, interval])
    
    def remove_task(self, index):
        """移除指定位置的任务"""
        if 0 <= index < len(self.task_queue):
            del self.task_queue[index]
            return True
        return False
    
    def clear_tasks(self):
        """清空任务队列"""
        self.task_queue.clear()
    
    def set_task_queue(self, task_queue):
        """设置任务队列"""
        self.task_queue = task_queue.copy()
    
    def insert_task(self, index, task_name, times=1, interval=1.0):
        """在指定位置插入任务"""
        self.task_queue.insert(index, [task_name, times, interval])
    
    def get_task_count(self):
        """获取任务数量"""
        return len(self.task_queue)
    
    def start(self):
        """启动任务执行"""
        if self.is_running:
            return False
        
        if not self.task_queue:
            self.app.log_message("任务队列为空，无法启动", "warning")
            return False
        
        if not self.app.get_selected_device():
            self.app.log_message("请先选择设备", "warning")
            return False
        
        self.is_running = True
        self.stop_event.clear()
        self.current_task_index = -1
        self.current_task_remaining = 0
        
        self.thread = threading.Thread(target=self._task_loop, daemon=True)
        self.thread.start()
        return True
    
    def stop(self):
        """停止任务执行"""
        if not self.is_running:
            return
        self.is_running = False
        self.app.log_message("正在停止任务...", "info")
        self.stop_event.set()
    
    def _task_loop(self):
        """任务执行主循环 - 循环执行直到停止或达到循环次数"""
        total_tasks = len(self.task_queue)
        
        # 检查任务队列是否为空
        if total_tasks == 0:
            self.app.root.after(0, self._on_finished)
            return
        
        self.loop_count = 0
        
        # 循环执行，直到收到停止信号或达到最大循环次数
        while not self.stop_event.is_set():
            # 检查是否达到最大循环次数（-1表示无限循环）
            if self.max_loops != -1 and self.loop_count >= self.max_loops:
                self.app.log_message(f"✅ 已达到最大循环次数 ({self.max_loops})，停止执行", "info")
                break  # 退出循环
            
            self.loop_count += 1
            if self.max_loops != -1:
                self.app.log_message(f"🔄 开始第 {self.loop_count}/{self.max_loops} 轮执行", "info")
            else:
                self.app.log_message(f"🔄 开始第 {self.loop_count} 轮执行 (无限循环)", "info")
            
            # 遍历任务队列
            for task_index in range(total_tasks):
                # 检查是否收到停止信号
                if self.stop_event.is_set():
                    break
                
                # 获取当前任务
                task_info = self.task_queue[task_index]
                task_name = task_info[0]
                times = task_info[1]
                interval = task_info[2] if len(task_info) > 2 else 1.0
                
                # 更新状态
                self.current_task_index = task_index
                self.current_task_remaining = times
                
                loop_info = f" (第{self.loop_count}轮)" if self.max_loops != -1 else " (循环)"
                self.app.root.after(0, lambda: self.app.update_task_status(
                    f"执行中: {task_name}{loop_info} [{task_index+1}/{total_tasks}]", 
                    "orange"
                ))
                self.app.log_message(f"执行任务 [{task_index+1}/{total_tasks}]: {task_name} (共{times}次)", "info")
                
                # 执行当前任务指定次数
                for i in range(times):
                    if self.stop_event.is_set():
                        break
                    
                    self.current_task_remaining = times - i - 1
                    self.app.root.after(0, lambda n=task_name, c=i+1, t=times, loop=self.loop_count: 
                        self.app.update_task_status(
                            f"循环第{loop}轮: {n} [{c}/{t}]", 
                            "orange"
                        ))
                    
                    try:
                        # 执行任务函数
                        if hasattr(self.app, task_name):
                            func = getattr(self.app, task_name)
                            func()
                            self.app.log_message(f"✓ {task_name} 第 {i+1}/{times} 次执行完成", "info")
                        else:
                            self.app.log_message(f"❌ 任务函数 {task_name} 不存在", "error")
                            break
                    except Exception as e:
                        self.app.log_message(f"❌ 任务 {task_name} 执行失败: {e}", "error")
                    
                    # 任务间间隔（除了最后一次）
                    if i < times - 1 and not self.stop_event.is_set():
                        time.sleep(interval)
                
                # 任务完成后短暂间隔
                if not self.stop_event.is_set():
                    time.sleep(0.5)
            
            # 一轮任务完成
            if not self.stop_event.is_set():
                if self.max_loops == -1 or self.loop_count < self.max_loops:
                    self.app.log_message("🔄 本轮任务完成，继续下一轮...", "info")
                    time.sleep(1)  # 轮间间隔
        
        # ===== 关键修改：退出循环后调用 _on_finished =====
        # 无论是因为达到最大循环次数还是被停止，都需要恢复按钮状态
        self.app.root.after(0, self._on_finished)
                
    def _on_finished(self):
        """任务完成回调"""
        self.is_running = False
        if self.stop_event.is_set():
            self.app.update_task_status("已停止", "blue")
            self.app.log_message("任务已停止", "info")
        else:
            self.app.update_task_status("已完成", "green")
            self.app.log_message("所有任务执行完成", "info")
        self.app.on_task_finished()

    def get_current_status(self):
        """获取当前执行状态"""
        if not self.is_running:
            return "空闲", 0, 0
        return "运行中", self.current_task_index, self.current_task_remaining


class ADBGUI:
    def __init__(self, root):
        self.root = root
        self.image_cache = {}  # 缓存字典: {image_path: (x, y)}
        self.root.title("ADB 模拟器自动化控制")
        self.root.geometry("1150x750")
        self.root.resizable(True, True)
        
        # 初始化设置管理器
        self.settings_mgr = SettingsManager()

        # 初始化 ADB 路径
        self.adb_path = self.get_adb_path()
        self.log_message(f"ADB 路径: {self.adb_path}", "info")
        
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
        # 获取当前 exe 所在目录（或脚本所在目录）
        if getattr(sys, 'frozen', False):
            # 打包成 exe 后运行
            base_dir = os.path.dirname(sys.executable)
        else:
            # 作为脚本运行
            base_dir = os.path.dirname(os.path.abspath(__file__))
        
        # 检查 platform-tools 目录下的 adb
        platform_tools_adb = os.path.join(base_dir, 'platform-tools', 'adb')
        if sys.platform == 'win32':
            platform_tools_adb += '.exe'
        
        if os.path.exists(platform_tools_adb) and os.access(platform_tools_adb, os.X_OK):
            self.log_message(f"使用本地 ADB: {platform_tools_adb}", "info")
            return platform_tools_adb
        
        # 检查当前目录下的 adb
        local_adb = os.path.join(base_dir, 'adb')
        if sys.platform == 'win32':
            local_adb += '.exe'
        if os.path.exists(local_adb) and os.access(local_adb, os.X_OK):
            self.log_message(f"使用本地 ADB: {local_adb}", "info")
            return local_adb
        
        # 如果本地没有，使用系统 PATH 中的 adb
        self.log_message("使用系统 PATH 中的 ADB", "info")
        return 'adb'
    def load_functions_module(self):
        """加载外部功能模块"""
        try:
            # 检查是否存在 functions.py 文件
            if not os.path.exists("functions.py"):
                self.log_message("未找到 functions.py，使用内置功能", "warning")
                self.load_builtin_functions()
                return False
            
            # 动态导入 functions 模块
            import importlib.util
            spec = importlib.util.spec_from_file_location("functions", "functions.py")
            if spec is None or spec.loader is None:
                self.log_message("无法加载 functions.py", "error")
                self.load_builtin_functions()
                return False
            
            functions_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(functions_module)
            
            # 获取功能配置
            if hasattr(functions_module, 'FUNCTION_CONFIGS'):
                self.function_configs = functions_module.FUNCTION_CONFIGS
            else:
                self.log_message("functions.py 中没有 FUNCTION_CONFIGS", "warning")
                self.function_configs = {}
            
            # 创建功能实例
            if hasattr(functions_module, 'Functions'):
                self.function_instances = functions_module.Functions(self)
                
                # 将功能方法绑定到自身，方便调用
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
        
        # 定义内置功能方法
        self._define_builtin_functions()
        self.log_message("使用内置功能", "info")
    
    def _define_builtin_functions(self):
        """定义内置功能方法"""
        # 测试消息
        def 测试消息():
            self.log_message("测试消息", "info")    
        setattr(self, "测试消息", 测试消息)
      


    
    def reload_functions(self):
        """重新加载外部功能模块（支持热更新）"""
        try:
            # 清除已绑定的方法
            for func_name in list(self.function_configs.keys()):
                if hasattr(self, func_name):
                    delattr(self, func_name)
            
            # 重新加载
            self.function_configs = {}
            self.function_instances = None
            
            # 强制重新加载模块
            if 'functions' in sys.modules:
                del sys.modules['functions']
            
            success = self.load_functions_module()
            
            if success:
                # 刷新界面
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
    
    def create_widgets(self):
        # 主框架
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 上半部分
        top_frame = ttk.Frame(main_frame, height=450)
        top_frame.pack(fill=tk.X, pady=(0, 5))
        top_frame.pack_propagate(False)
        
        # 左侧设备列表
        left_frame = ttk.Frame(top_frame, width=200)
        left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 5))
        
        ttk.Label(left_frame, text="已连接的ADB设备", font=('Arial', 10, 'bold')).pack(pady=5)
        
        self.device_listbox = tk.Listbox(left_frame, height=8, selectmode=tk.SINGLE)
        self.device_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.device_listbox.bind('<<ListboxSelect>>', self.on_device_select)
        
        refresh_btn = ttk.Button(left_frame, text="刷新设备列表", command=self.refresh_devices)
        refresh_btn.pack(pady=5)
        
        # 添加重新加载功能按钮
        reload_btn = ttk.Button(left_frame, text="重载功能", 
                                command=self.reload_functions)
        reload_btn.pack(pady=2)
        
        ttk.Label(left_frame, text="当前选中设备:").pack(pady=(10,0))
        self.selected_device_label = ttk.Label(left_frame, text="未选择", foreground="blue")
        self.selected_device_label.pack()
        
        # 右侧：Notebook
        right_frame = ttk.Frame(top_frame)
        right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.notebook = ttk.Notebook(right_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        # 创建标签页
        self.task_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.task_tab, text="任务控制")
        self.create_task_tab()
        
        self.settings_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.settings_tab, text="设置管理")
        self.create_settings_tab()
        
        self.test_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.test_tab, text="功能测试")
        self.create_test_tab()
        
        self.quick_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.quick_tab, text="快捷功能")
        self.create_quick_tab()
        
        # 下半部分：日志输出
        log_frame = ttk.LabelFrame(main_frame, text="执行日志", padding=5)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(5, 0))
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=10, state=tk.NORMAL)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        self.log_text.config(state=tk.DISABLED)
    
    def create_task_tab(self):
        """创建任务控制标签页"""
        # 主框架分为上下两部分
        task_main_frame = ttk.Frame(self.task_tab)
        task_main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 上半部分：任务列表和控制按钮
        top_half = ttk.Frame(task_main_frame)
        top_half.pack(fill=tk.BOTH, expand=True)
        
        # 左侧：任务列表
        list_frame = ttk.LabelFrame(top_half, text="任务队列", padding=5)
        list_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        # 创建任务列表 (Treeview)
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
        
        # 滚动条
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.task_tree.yview)
        self.task_tree.configure(yscrollcommand=scrollbar.set)
        
        self.task_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 任务列表右键菜单
        self.task_context_menu = tk.Menu(self.task_tree, tearoff=0)
        self.task_context_menu.add_command(label="上移", command=lambda: self.move_task(-1))
        self.task_context_menu.add_command(label="下移", command=lambda: self.move_task(1))
        self.task_context_menu.add_separator()
        self.task_context_menu.add_command(label="删除", command=self.delete_task)
        self.task_context_menu.add_command(label="清空", command=self.clear_tasks)
        self.task_tree.bind("<Button-3>", self.show_task_context_menu)
        
        # 右侧：任务操作面板
        operation_frame = ttk.LabelFrame(top_half, text="任务操作", padding=10)
        operation_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 0))
        
        # 添加任务到队列
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
        
        # 下半部分：任务控制
        bottom_half = ttk.Frame(task_main_frame)
        bottom_half.pack(fill=tk.X, pady=(10, 0))
        
        control_frame = ttk.LabelFrame(bottom_half, text="任务控制", padding=10)
        control_frame.pack(fill=tk.X)
        
        # 第一行：控制按钮 + 循环控制（并排）
        control_row1 = ttk.Frame(control_frame)
        control_row1.pack(fill=tk.X, pady=5)
        
        # 控制按钮组
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
        
        # 循环控制选项（与按钮并排）
        loop_frame = ttk.Frame(control_row1)
        loop_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        ttk.Label(loop_frame, text="循环次数:").pack(side=tk.LEFT, padx=5)
        self.loop_times_entry = ttk.Entry(loop_frame, width=8)
        self.loop_times_entry.insert(0, "1")  # -1表示无限循环
        self.loop_times_entry.pack(side=tk.LEFT, padx=2)
        ttk.Label(loop_frame, text="(-1无限)", font=('Arial', 9)).pack(side=tk.LEFT, padx=2)
        
        # 第二行：状态显示
        status_frame = ttk.Frame(control_frame)
        status_frame.pack(fill=tk.X, pady=5)
        
        self.task_status_label = ttk.Label(status_frame, text="状态: 空闲", foreground="green")
        self.task_status_label.pack(side=tk.LEFT, padx=5)
        
    def update_task_combo(self):
        """更新任务下拉列表"""
        tasks = list(self.function_configs.keys())
        # 添加自定义任务（从设置中读取）
        custom_tasks = self.settings_mgr.get_value("custom_tasks", [])
        if isinstance(custom_tasks, list):
            tasks.extend(custom_tasks)
        self.task_combo['values'] = tasks
        if tasks:
            self.task_combo.set(tasks[0])
    
    def show_task_context_menu(self, event):
        """显示任务列表右键菜单"""
        item = self.task_tree.identify_row(event.y)
        if item:
            self.task_tree.selection_set(item)
            self.task_context_menu.post(event.x_root, event.y_root)
    
    def add_task_to_queue(self):
        """添加任务到队列"""
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
        
        # 添加到任务管理器
        self.task_manager.add_task(task_name, times, interval)
        self.refresh_task_list()
        self.log_message(f"已添加任务: {task_name} (执行{times}次, 间隔{interval}秒)", "info")
        
        # 自动保存任务队列到设置
        self.save_task_queue_to_settings()
    
    
    def refresh_task_list(self):
        """刷新任务列表显示"""
        for item in self.task_tree.get_children():
            self.task_tree.delete(item)
        
        for idx, task in enumerate(self.task_manager.task_queue):
            task_name = task[0]
            times = task[1]
            interval = task[2] if len(task) > 2 else 1.0
            self.task_tree.insert("", tk.END, values=(idx+1, task_name, times, interval))
    
    def delete_task(self):
        """删除选中的任务"""
        selected = self.task_tree.selection()
        if not selected:
            return
        
        # 获取选中项在数据中的索引
        item = selected[0]
        values = self.task_tree.item(item, "values")
        idx = int(values[0]) - 1
        
        if self.task_manager.remove_task(idx):
            self.refresh_task_list()
            self.save_task_queue_to_settings()
            self.log_message(f"已删除任务: {values[1]}", "info")
    
    def clear_tasks(self):
        """清空任务队列"""
        if not self.task_manager.task_queue:
            return
        
        if messagebox.askyesno("确认清空", "确定要清空所有任务吗？"):
            self.task_manager.clear_tasks()
            self.refresh_task_list()
            self.save_task_queue_to_settings()
            self.log_message("已清空任务队列", "info")
    
    def move_task(self, direction):
        """移动任务位置"""
        selected = self.task_tree.selection()
        if not selected:
            return
        
        item = selected[0]
        values = self.task_tree.item(item, "values")
        current_idx = int(values[0]) - 1
        new_idx = current_idx + direction
        
        if 0 <= new_idx < len(self.task_manager.task_queue):
            # 交换位置
            self.task_manager.task_queue[current_idx], self.task_manager.task_queue[new_idx] = \
                self.task_manager.task_queue[new_idx], self.task_manager.task_queue[current_idx]
            self.refresh_task_list()
            self.save_task_queue_to_settings()
            
            # 选中移动后的项目
            for child in self.task_tree.get_children():
                if self.task_tree.item(child, "values")[0] == str(new_idx + 1):
                    self.task_tree.selection_set(child)
                    break
    
    def save_task_queue_to_settings(self):
        """保存任务队列到设置"""
        task_list = []
        for task in self.task_manager.task_queue:
            task_list.append({
                "name": task[0],
                "times": task[1],
                "interval": task[2] if len(task) > 2 else 1.0
            })
        self.settings_mgr.set_value("task_queue", task_list)
    
    def load_task_queue_from_settings(self):
        """从设置加载任务队列"""
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
        """启动任务队列"""
        if self.task_manager.is_running:
            return
        
        # 获取循环次数设置
        try:
            max_loops = int(self.loop_times_entry.get())
            self.task_manager.set_max_loops(max_loops)
        except ValueError:
            self.task_manager.set_max_loops(-1)  # 默认无限循环
        
        if self.task_manager.start():
            self.start_btn.config(state=tk.DISABLED)
            self.stop_btn.config(state=tk.NORMAL)
            self.log_message(f"任务队列已启动 (循环次数: {'无限' if self.task_manager.max_loops == -1 else self.task_manager.max_loops})", "info")
    
    def stop_task_queue(self):
        """停止任务队列"""
        if not self.task_manager.is_running:
            return
        self.task_manager.stop()
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
    
    def update_task_status(self, status_text, color="green"):
        """更新任务状态显示"""
        self.task_status_label.config(text=f"状态: {status_text}", foreground=color)
    
    def on_task_finished(self):
        """任务完成回调"""
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
    
    def create_quick_tab(self):
        """创建快捷功能标签页"""
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
        """创建功能按钮"""
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
        """刷新快捷功能按钮"""
        # 重新创建快捷功能标签页的内容
        for child in self.quick_tab.winfo_children():
            child.destroy()
        self.create_quick_tab()
        self.log_message("功能按钮已刷新", "info")
    
    def execute_function(self, func_name):
        """执行指定的功能函数"""
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
                
                # 从外部模块或内置方法调用
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
        """创建设置管理标签页"""
        # 顶部操作按钮
        top_frame = ttk.Frame(self.settings_tab)
        top_frame.pack(fill=tk.X, pady=5, padx=5)
        
        ttk.Button(top_frame, text="添加新设置", command=self.add_setting_dialog).pack(side=tk.LEFT, padx=5)
        ttk.Button(top_frame, text="刷新列表", command=self.refresh_settings_display).pack(side=tk.LEFT, padx=5)
        ttk.Button(top_frame, text="导出设置", command=self.export_settings).pack(side=tk.LEFT, padx=5)
        ttk.Button(top_frame, text="导入设置", command=self.import_settings).pack(side=tk.LEFT, padx=5)
        ttk.Button(top_frame, text="恢复默认", command=self.restore_default_settings).pack(side=tk.LEFT, padx=5)
        
        # 设置列表显示
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
        
        # 右键菜单
        self.create_settings_context_menu()
        
        # 底部操作按钮
        bottom_frame = ttk.Frame(self.settings_tab)
        bottom_frame.pack(fill=tk.X, pady=5, padx=5)
        
        ttk.Button(bottom_frame, text="修改选中", command=self.modify_setting_dialog).pack(side=tk.LEFT, padx=5)
        ttk.Button(bottom_frame, text="删除选中", command=self.delete_setting).pack(side=tk.LEFT, padx=5)
    
    def create_settings_context_menu(self):
        """为设置列表创建右键菜单"""
        self.context_menu = tk.Menu(self.settings_tree, tearoff=0)
        self.context_menu.add_command(label="修改", command=self.modify_setting_dialog)
        self.context_menu.add_command(label="删除", command=self.delete_setting)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="复制键名", command=self.copy_key_name)
        self.context_menu.add_command(label="复制值", command=self.copy_value)
        
        self.settings_tree.bind("<Button-3>", self.show_settings_context_menu)
    
    def show_settings_context_menu(self, event):
        """显示设置右键菜单"""
        item = self.settings_tree.identify_row(event.y)
        if item:
            self.settings_tree.selection_set(item)
            self.context_menu.post(event.x_root, event.y_root)
    
    def copy_key_name(self):
        """复制选中的键名"""
        selected = self.settings_tree.selection()
        if selected:
            item = selected[0]
            key = self.settings_tree.item(item, "values")[0]
            self.root.clipboard_clear()
            self.root.clipboard_append(key)
            messagebox.showinfo("成功", f"已复制键名: {key}")
    
    def copy_value(self):
        """复制选中的值"""
        selected = self.settings_tree.selection()
        if selected:
            item = selected[0]
            value = self.settings_tree.item(item, "values")[1]
            self.root.clipboard_clear()
            self.root.clipboard_append(value)
            messagebox.showinfo("成功", f"已复制值: {value}")
    
    def load_settings_to_ui(self):
        """加载设置到UI列表"""
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
        """刷新设置显示"""
        self.settings_mgr.load_settings()
        self.load_settings_to_ui()
        self.log_message("设置列表已刷新", "info")
    
    def add_setting_dialog(self):
        """添加新设置的对话框"""
        dialog = tk.Toplevel(self.root)
        dialog.title("添加新设置")
        dialog.geometry("400x250")
        dialog.transient(self.root)
        dialog.grab_set()
        
        ttk.Label(dialog, text="键名:").pack(pady=(10,0))
        key_entry = ttk.Entry(dialog, width=40)
        key_entry.pack(pady=5)
        
        ttk.Label(dialog, text="值:").pack(pady=(10,0))
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
        """修改选中设置的对话框"""
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
        
        ttk.Label(dialog, text="键名:").pack(pady=(10,0))
        key_label = ttk.Label(dialog, text=old_key, foreground="blue")
        key_label.pack(pady=5)
        
        ttk.Label(dialog, text="新值:").pack(pady=(10,0))
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
        """删除选中的设置"""
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
        """导出设置到文件"""
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
        """从文件导入设置"""
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
    
    def restore_default_settings(self):
        """恢复默认设置"""
        if messagebox.askyesno("确认恢复", "将恢复所有设置为默认值，确定吗？"):
            default_settings = {
                "task_interval": 1.0,
                "click_delay": 0.5,
                "retry_times": 3,
                "image_threshold": 0.8,
                "default_x": 100,
                "default_y": 100,
                "派出兵力": "1",
                "搜索点坐标X": "0@0",
                "搜索点坐标Y": "0@0"
            }
            self.settings_mgr.update_settings(default_settings)
            self.load_settings_to_ui()
            self.log_message("已恢复默认设置", "info")
            messagebox.showinfo("成功", "已恢复默认设置")
    
    def create_test_tab(self):
        """创建功能测试标签页"""
        # 坐标测试部分（原有）
        coord_frame = ttk.LabelFrame(self.test_tab, text="坐标测试", padding=10)
        coord_frame.pack(fill=tk.X, pady=5, padx=5)
        
        input_frame = ttk.Frame(coord_frame)
        input_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(input_frame, text="X坐标:").pack(side=tk.LEFT, padx=2)
        self.x_entry = ttk.Entry(input_frame, width=10)
        self.x_entry.pack(side=tk.LEFT, padx=2)
        self.x_entry.insert(0, str(self.settings_mgr.get_value("default_x", 100)))
        
        ttk.Label(input_frame, text="Y坐标:").pack(side=tk.LEFT, padx=2)
        self.y_entry = ttk.Entry(input_frame, width=10)
        self.y_entry.pack(side=tk.LEFT, padx=2)
        self.y_entry.insert(0, str(self.settings_mgr.get_value("default_y", 100)))
        
        btn_frame = ttk.Frame(coord_frame)
        btn_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(btn_frame, text="取色", command=self.test_get_color, width=10).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="点击", command=self.test_click, width=10).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="找图", command=self.test_find_image, width=10).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="截图", command=self.test_screenshot, width=10).pack(side=tk.LEFT, padx=2)
        
        # ====== 新增：ADBKeyboard文字输入测试部分 ======
        text_frame = ttk.LabelFrame(self.test_tab, text="ADBKeyboard文字输入测试", padding=10)
        text_frame.pack(fill=tk.X, pady=5, padx=5)
        
        # 状态显示区域
        status_display_frame = ttk.Frame(text_frame)
        status_display_frame.pack(fill=tk.X, pady=5)
        
        self.adbkeyboard_status_label = ttk.Label(status_display_frame, text="检测ADBKeyboard状态...", foreground="blue")
        self.adbkeyboard_status_label.pack(side=tk.LEFT, padx=5)
        
        # 修改这里：在"检测并激活"按钮左边添加"安装 ADBKeyboard"按钮
        btn_container = ttk.Frame(status_display_frame)
        btn_container.pack(side=tk.RIGHT, padx=5)
        
        # 新增：安装 ADBKeyboard 按钮
        ttk.Button(btn_container, text="安装 ADBKeyboard", 
                command=self.install_adbkeyboard, width=18).pack(side=tk.RIGHT, padx=2)
        
        # 原有的检测并激活按钮
        ttk.Button(btn_container, text="检测并激活", 
                command=self.check_and_activate_adbkeyboard, width=15).pack(side=tk.RIGHT, padx=2)
        
        # 输入文本区域
        text_input_frame = ttk.Frame(text_frame)
        text_input_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(text_input_frame, text="输入文本:").pack(side=tk.LEFT, padx=5)
        self.test_text_entry = ttk.Entry(text_input_frame, width=50)
        self.test_text_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        self.test_text_entry.insert(0, "你好世界 Hello World! 123 😊")
        
        # 按钮区域
        text_btn_frame = ttk.Frame(text_frame)
        text_btn_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(text_btn_frame, text="测试输入", 
                command=self.test_adbkeyboard_input, width=12).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(text_btn_frame, text="使用说明", 
                command=self.show_adbkeyboard_help, width=12).pack(side=tk.LEFT, padx=5)

    
    def refresh_devices(self, retry_count=2):
        """刷新ADB设备列表（优先使用本地 platform-tools）"""
        self.device_listbox.delete(0, tk.END)
        
        # 获取 ADB 路径
        adb_path = self.get_adb_path()
        self.log_message("ADB目录:" + adb_path, "info")
        for attempt in range(retry_count + 1):
            try:
                # 第一次尝试时先启动 ADB 服务
                if attempt == 0:
                    self.log_message("正在启动 ADB 服务...", "info")
                    subprocess.run([adb_path, 'start-server'], capture_output=True, timeout=10)
                    time.sleep(0.5)
                
                result = subprocess.run([adb_path, 'devices'], capture_output=True, text=True, timeout=10)
                
                lines = result.stdout.strip().split('\n')
                devices = []
                for line in lines[1:]:
                    if line.strip() and 'device' in line and 'offline' not in line:
                        parts = line.split()
                        if len(parts) >= 2 and parts[1] == 'device':
                            serial = parts[0]
                            devices.append(serial)
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
                
            except subprocess.TimeoutExpired:
                if attempt < retry_count:
                    self.log_message(f"刷新设备列表超时，第 {attempt + 1} 次重试...", "warning")
                    time.sleep(1)
                else:
                    self.log_message("刷新设备列表超时，请检查ADB是否正常工作", "error")
                    messagebox.showerror("错误", "ADB命令执行超时，请确保:\n1. ADB已正确安装\n2. 模拟器/设备已连接")
                    
            except Exception as e:
                if attempt < retry_count:
                    self.log_message(f"刷新设备列表失败，第 {attempt + 1} 次重试: {e}", "warning")
                    time.sleep(1)
                else:
                    self.log_message(f"刷新设备列表失败: {e}", "error")
                    messagebox.showerror("错误", f"ADB命令执行失败: {e}")
    
    def on_device_select(self, event):
        """选择设备事件"""
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
        """获取当前选中的设备序列号"""
        device = self.selected_device.get()
        if not device:
            messagebox.showwarning("警告", "请先选择一个设备")
            return None
        return device
    
    def get_test_coords(self):
        """获取测试坐标输入框的值"""
        try:
            x = int(self.x_entry.get())
            y = int(self.y_entry.get())
            return x, y
        except ValueError:
            messagebox.showerror("错误", "请输入有效的整数坐标")
            return None, None
    
    # ---------- 核心功能函数 ----------
    def get_color(self, x, y, device=None):
        """获取模拟器指定点的颜色值"""
        if device is None:
            device = self.get_selected_device()
            if not device:
                return None
        
        try:
            temp_file = "/sdcard/temp_screencap.png"
            cmd = [self.adb_path, '-s', device, 'shell', 'screencap', temp_file]
            subprocess.run(cmd, capture_output=True, check=True, timeout=5)
            
            local_temp = "temp_screencap.png"
            pull_cmd = [self.adb_path, '-s', device, 'pull', temp_file, local_temp]
            subprocess.run(pull_cmd, capture_output=True, check=True, timeout=5)
            
            img = Image.open(local_temp)
            pixel = img.getpixel((x, y))
            color_hex = f"{pixel[0]:02X}{pixel[1]:02X}{pixel[2]:02X}"
            
            os.remove(local_temp)
            subprocess.run([self.adb_path, '-s', device, 'shell', 'rm', temp_file], capture_output=True, timeout=3)
            return color_hex
        except Exception as e:
            self.log_message(f"取色失败 ({x},{y}): {e}", "error")
            return None
    def press_back(self, device=None):
        """按下手机返回按钮"""
        if device is None:
            device = self.get_selected_device()
            if not device:
                return False
        
        try:
            # KEYCODE_BACK = 4
            cmd = [self.adb_path, '-s', device, 'shell', 'input', 'keyevent', '4']
            subprocess.run(cmd, capture_output=True, check=True, timeout=5)
            self.log_message("按下返回按钮", "info")
            time.sleep(0.5)  # 添加短暂延迟
            return True
        except Exception as e:
            self.log_message(f"返回操作失败: {e}", "error")
            return False
        
    def find_image_first(self, image_path, device=None, threshold=None, use_cache=False):
        """在模拟器屏幕上查找指定图片，返回从上到下、从左到右第一个匹配的位置
        
        Args:
            image_path: 图片模板路径
            device: 设备序列号，默认使用当前选中的设备
            threshold: 匹配阈值，默认从设置中读取
            use_cache: 是否使用缓存
        
        Returns:
            (x, y): 匹配到的中心坐标，如果未找到则返回 None
        """
        if threshold is None:
            threshold = self.settings_mgr.get_value("image_threshold", 0.8)
            
        if device is None:
            device = self.get_selected_device()
            if not device:
                return None
        
        # 缓存检查
        cache_key = (image_path, device, threshold, "first")
        if use_cache and cache_key in self.image_cache:
            return self.image_cache[cache_key]
        
        try:
            local_screen = "temp_screen.png"
            with open(local_screen, 'wb') as f:
                cmd = [self.adb_path, '-s', device, 'exec-out', 'screencap', '-p']
                subprocess.run(cmd, stdout=f, check=True, timeout=5)
            
            screen_img = Image.open(local_screen)
            template_img = Image.open(image_path)
            
            try:
                import cv2
                import numpy as np
                
                screen_np = np.array(screen_img)
                template_np = np.array(template_img)
                
                screen_gray = cv2.cvtColor(screen_np, cv2.COLOR_RGB2GRAY)
                template_gray = cv2.cvtColor(template_np, cv2.COLOR_RGB2GRAY)
                
                result = cv2.matchTemplate(screen_gray, template_gray, cv2.TM_CCOEFF_NORMED)
                h, w = template_gray.shape
                
                # 找到所有超过阈值的匹配点
                locations = np.where(result >= threshold)
                
                if len(locations[0]) == 0:
                    os.remove(local_screen)
                    return None
                
                # 收集所有匹配点
                matches = []
                for pt in zip(*locations[::-1]):  # 注意：np.where返回的是(y,x)顺序
                    x = pt[0] + w // 2
                    y = pt[1] + h // 2
                    confidence = result[pt[1], pt[0]]
                    matches.append((x, y, confidence))
                
                # 按 y 坐标排序（从上到下），如果 y 相同则按 x 排序（从左到右）
                matches.sort(key=lambda m: (m[1], m[0]))
                
                # 取第一个匹配点（最左上）
                x, y, _ = matches[0]
                
                if use_cache:
                    self.image_cache[cache_key] = (x, y)
                
                os.remove(local_screen)
                self.log_message(f"找到第一个图片坐标 X:{x} Y:{y} (共{len(matches)}个匹配)", "info")
                return (x, y)
                
            except ImportError:
                self.log_message("未安装opencv-python，无法使用找图功能", "error")
                os.remove(local_screen)
                return None
                
        except Exception as e:
            self.log_message(f"找图失败: {e}", "error")
            return None
        
    def find_image(self, image_path, device=None, threshold=None, use_cache=False):
        """在模拟器屏幕上查找指定图片"""
        if threshold is None:
            threshold = self.settings_mgr.get_value("image_threshold", 0.8)
            
        if device is None:
            device = self.get_selected_device()
            if not device:
                return None
        
        # 缓存检查
        cache_key = (image_path, device, threshold)
        if use_cache and cache_key in self.image_cache:
            return self.image_cache[cache_key]
        
        try:
            local_screen = "temp_screen.png"
            with open(local_screen, 'wb') as f:
                cmd = [self.adb_path, '-s', device, 'exec-out', 'screencap', '-p']
                subprocess.run(cmd, stdout=f, check=True, timeout=5)
            
            screen_img = Image.open(local_screen)
            template_img = Image.open(image_path)
            
            try:
                import cv2
                import numpy as np
                
                screen_np = np.array(screen_img)
                template_np = np.array(template_img)
                
                screen_gray = cv2.cvtColor(screen_np, cv2.COLOR_RGB2GRAY)
                template_gray = cv2.cvtColor(template_np, cv2.COLOR_RGB2GRAY)
                
                result = cv2.matchTemplate(screen_gray, template_gray, cv2.TM_CCOEFF_NORMED)
                min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
                
                if max_val >= threshold:
                    h, w = template_gray.shape
                    x = max_loc[0] + w // 2
                    y = max_loc[1] + h // 2
                    
                    if use_cache:
                        self.image_cache[cache_key] = (x, y)
                    
                    os.remove(local_screen)
                    self.log_message(f"找到图片坐标 X:{x} Y:{y}", "info")
                    return (x, y)
                else:
                    os.remove(local_screen)
                    return None
            except ImportError:
                self.log_message("未安装opencv-python，无法使用找图功能", "error")
                os.remove(local_screen)
                return None
        except Exception as e:
            self.log_message(f"找图失败: {e}", "error")
            return None
    
    def click_point(self, x, y, device=None, delay=None):
        """点击模拟器指定坐标"""
        if delay is None:
            delay = self.settings_mgr.get_value("click_delay", 0.5)
            
        if device is None:
            device = self.get_selected_device()
            if not device:
                return False
        
        try:
            cmd = [self.adb_path, '-s', device, 'shell', 'input', 'tap', str(x), str(y)]
            subprocess.run(cmd, capture_output=True, check=True, timeout=5)
            self.log_message(f"点击坐标 ({x}, {y})", "info")
            time.sleep(delay)
            return True
        except Exception as e:
            self.log_message(f"点击失败 ({x},{y}): {e}", "error")
            return False
        
    def long_press(self, x, y, duration=1.0, device=None, tap_offset=0.08):
        """
        长按并在结束前触发点击（解决 Unity 等引擎长按后菜单不弹出）
        
        原理：input swipe 提供持续按压（加载动画），在结束前用 input tap
        注入一次合法的 DOWN+UP，游戏引擎识别为"长按确认"并弹出菜单。
        
        Args:
            x, y: 屏幕坐标
            duration: 长按时长（秒），默认 1.0
            tap_offset: 在结束前多少秒触发点击（默认 0.08 = 80ms）
                    如果菜单不弹出，尝试调大（0.15）或调小（0.05）
        """
        if device is None:
            device = self.get_selected_device()
        if not device:
            self.log_message("长按失败：未选择设备", "error")
            return False
        
        try:
            x, y = int(x), int(y)
            duration = float(duration)
            tap_offset = float(tap_offset)
            if duration < 0.15:
                duration = 0.15
        except (ValueError, TypeError):
            self.log_message("长按参数错误", "error")
            return False
        
        import threading
        
        def swipe_thread():
            """执行 swipe 长按（带 1 像素微移，确保产生 MOVE 事件）"""
            cmd = [self.adb_path, '-s', device, 'shell', 'input', 'swipe',
                str(x), str(y), str(x+1), str(y+1), str(int(duration * 1000))]
            subprocess.run(cmd, capture_output=True, timeout=duration + 5)
        
        def tap_thread():
            """在长按结束前触发点击"""
            sleep_time = max(duration - tap_offset, 0.03)
            time.sleep(sleep_time)
            cmd = [self.adb_path, '-s', device, 'shell', 'input', 'tap', str(x), str(y)]
            subprocess.run(cmd, capture_output=True, timeout=5)
        
        t1 = threading.Thread(target=swipe_thread)
        t2 = threading.Thread(target=tap_thread)
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        
        self.log_message(f"✅ 长按完成 ({x},{y}) {duration}s (提前{tap_offset}s点击)", "info")
        return True
        
    def swipe(self, x1, y1, x2, y2, duration=300, device=None):
        """
        从点1滑动到点2（按住拖拽）
        
        Args:
            x1, y1: 起始坐标
            x2, y2: 结束坐标
            duration: 滑动持续时间（毫秒），默认300ms
            device: 设备序列号，默认使用当前选中的设备
        
        Returns:
            bool: 是否成功
        """
        if device is None:
            device = self.get_selected_device()
            if not device:
                return False
        
        try:
            cmd = [self.adb_path, '-s', device, 'shell', 'input', 'swipe', 
                str(x1), str(y1), str(x2), str(y2), str(duration)]
            subprocess.run(cmd, capture_output=True, check=True, timeout=5)
            
            self.log_message(f"✅ 滑动: ({x1},{y1}) -> ({x2},{y2}) 持续 {duration}ms", "info")
            return True
        except Exception as e:
            self.log_message(f"滑动失败: {e}", "error")
            return False
    def input_number_with_backspace(self, target_number, delete_count=1, device=None):
        """在输入框中先按指定次数的退格键，然后输入新的数字"""
        if device is None:
            device = self.get_selected_device()
            if not device:
                return False
        
        try:
            for i in range(delete_count):
                cmd = [self.adb_path, '-s', device, 'shell', 'input', 'keyevent', '67']
                subprocess.run(cmd, capture_output=True, check=True, timeout=2)
                time.sleep(0.15)
            
            time.sleep(0.3)
            
            number_str = str(target_number)
            for char in number_str:
                cmd = [self.adb_path, '-s', device, 'shell', 'input', 'text', char]
                subprocess.run(cmd, capture_output=True, check=True, timeout=2)
                time.sleep(0.05)
            
            self.log_message(f"重新输入: {number_str} (已删除{delete_count}个字符)", "info")
            return True
        except Exception as e:
            self.log_message(f"输入数字失败: {e}", "error")
            return False

    def input_chinese(self, text, device=None):
        """
        输入中文 - 使用ADBKeyboard的Base64方式
        无论输入法是否切换成功，都尝试输入
        """
        if device is None:
            device = self.get_selected_device()
            if not device:
                return False
        
        # 1. 先检查ADBKeyboard是否已安装
        try:
            cmd = [self.adb_path, '-s', device, 'shell', 'pm', 'list', 'packages', 'com.android.adbkeyboard']
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
            if 'com.android.adbkeyboard' not in result.stdout:
                self.log_message("❌ ADBKeyboard未安装，无法输入", "error")
                messagebox.showerror("错误", "ADBKeyboard未安装！\n请先安装 ADBKeyboard.apk")
                return False
        except Exception as e:
            self.log_message(f"检查ADBKeyboard失败: {e}", "error")
            return False
        
        # 2. 尝试切换输入法（即使失败也继续）
        self.log_message("🔄 尝试确保ADBKeyboard为当前输入法...", "info")
        
        try:
            # 尝试切换（忽略错误）
            cmd = [self.adb_path, '-s', device, 'shell', 'ime', 'set', 'com.android.adbkeyboard/.AdbIME']
            subprocess.run(cmd, capture_output=True, timeout=3)
        except:
            pass
        
        try:
            # 备用方法：启用输入法
            cmd = [self.adb_path, '-s', device, 'shell', 'ime', 'enable', 'com.android.adbkeyboard/.AdbIME']
            subprocess.run(cmd, capture_output=True, timeout=3)
        except:
            pass
        
        # 3. 执行输入（无论切换是否成功）
        try:
            import base64
            b64_text = base64.b64encode(text.encode('utf-8')).decode('utf-8')
            
            # 发送广播输入
            cmd = [self.adb_path, '-s', device, 'shell', 'am', 'broadcast', 
                '-a', 'ADB_INPUT_B64', '--es', 'msg', b64_text]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            
            if result.returncode == 0:
                self.log_message(f'✅ 输入成功: {text[:30]}{"..." if len(text) > 30 else ""}', "info")
                return True
            else:
                error_msg = result.stderr if result.stderr else "未知错误"
                self.log_message(f"❌ 输入失败: {error_msg}", "error")
                
                # 提示用户检查输入法
                messagebox.showerror("输入失败", 
                    f"输入失败！\n\n"
                    f"错误信息: {error_msg}\n\n"
                    "可能的原因：\n"
                    "1. 当前输入法不是 ADBKeyboard\n"
                    "2. 输入框未获得焦点（请点击输入框）\n"
                    "3. ADBKeyboard未正确安装\n\n"
                    "请确保：\n"
                    "• 已手动切换输入法为 ADBKeyboard\n"
                    "• 输入框处于激活状态（光标闪烁）")
                return False
                
        except Exception as e:
            self.log_message(f"❌ 输入失败: {e}", "error")
            messagebox.showerror("错误", f"输入失败: {e}")
            return False
    
    # ---------- 测试功能 ----------
    def test_get_color(self):
        """测试取色功能"""
        device = self.get_selected_device()
        if not device:
            return
        
        x, y = self.get_test_coords()
        if x is None or y is None:
            return
        
        color = self.get_color(x, y, device)
        if color:
            self.log_message(f"取色测试: ({x},{y}) -> #{color}", "info")
            messagebox.showinfo("取色结果", f"坐标 ({x}, {y}) 的颜色值为: #{color}")
        else:
            messagebox.showerror("取色失败", "无法获取颜色值")
    
    def test_click(self):
        """测试点击功能"""
        device = self.get_selected_device()
        if not device:
            return
        
        x, y = self.get_test_coords()
        if x is None or y is None:
            return
        
        if self.click_point(x, y, device):
            self.log_message(f"点击测试: ({x},{y}) 成功", "info")
            messagebox.showinfo("点击成功", f"已点击坐标 ({x}, {y})")
        else:
            messagebox.showerror("点击失败", "点击操作失败")
    
    def test_find_image(self):
        """测试找图功能"""
        device = self.get_selected_device()
        if not device:
            return
        
        path = filedialog.askopenfilename(title="选择图片模板", filetypes=[("图片文件", "*.png *.jpg *.bmp")])
        if not path:
            return
        
        pos = self.find_image(path, device)
        if pos:
            messagebox.showinfo("找图结果", f"找到图片位置: {pos}")
            self.log_message(f"找图测试: 在 {pos} 找到图片", "info")
        else:
            messagebox.showinfo("找图结果", "未找到图片")
            self.log_message("找图测试: 未找到图片", "info")
    
    def test_screenshot(self):
        """测试截图功能"""
        device = self.get_selected_device()
        if not device:
            return
        
        file_path = filedialog.asksaveasfilename(
            title="保存截图",
            defaultextension=".png",
            filetypes=[("PNG图片", "*.png"), ("所有文件", "*.*")]
        )
        if file_path:
            try:
                with open(file_path, 'wb') as f:
                    cmd = [self.adb_path, '-s', device, 'exec-out', 'screencap', '-p']
                    subprocess.run(cmd, stdout=f, check=True, timeout=5)
                self.log_message(f"截图已保存: {file_path}", "info")
                messagebox.showinfo("成功", f"截图已保存到: {file_path}")
            except Exception as e:
                messagebox.showerror("错误", f"截图失败: {e}")

    def install_adbkeyboard(self, device=None):
        """
        安装 ADBKeyboard
        1. 检查当前目录是否有 ADBKeyboard.apk
        2. 如果没有，从网络下载
        3. 尝试安装到设备
        """
        if device is None:
            device = self.get_selected_device()
            if not device:
                self.adbkeyboard_status_label.config(text="❌ 请先选择设备", foreground="red")
                return False
        
        import urllib.request
        import os
        
        apk_filename = "ADBKeyboard.apk"
        download_url = "https://cunchu.site/app/ADBKeyboard.apk"
        
        # 更新状态
        self.adbkeyboard_status_label.config(text="🔄 检查APK文件...", foreground="orange")
        self.root.update()
        
        try:
            # 1. 检查文件是否存在
            if os.path.exists(apk_filename):
                self.log_message(f"✅ 找到本地APK: {apk_filename}", "info")
            else:
                # 2. 下载文件
                self.log_message(f"📥 开始下载 ADBKeyboard.apk 从 {download_url}", "info")
                self.adbkeyboard_status_label.config(text="📥 正在下载...", foreground="orange")
                self.root.update()
                
                try:
                    urllib.request.urlretrieve(download_url, apk_filename)
                    self.log_message(f"✅ 下载完成: {apk_filename}", "info")
                except Exception as e:
                    self.adbkeyboard_status_label.config(text="❌ 下载失败", foreground="red")
                    self.log_message(f"❌ 下载失败: {e}", "error")
                    messagebox.showerror("下载失败", f"无法下载 ADBKeyboard.apk:\n{e}\n\n请手动下载并放到程序目录下")
                    return False
            
            # 3. 检查文件大小（确保不是空文件）
            file_size = os.path.getsize(apk_filename)
            if file_size < 1000:  # 小于1KB认为是无效文件
                self.log_message(f"⚠️ APK文件大小异常 ({file_size} bytes)，删除并重新下载", "warning")
                os.remove(apk_filename)
                # 重新下载
                try:
                    urllib.request.urlretrieve(download_url, apk_filename)
                    self.log_message(f"✅ 重新下载完成", "info")
                except Exception as e:
                    self.adbkeyboard_status_label.config(text="❌ 下载失败", foreground="red")
                    messagebox.showerror("下载失败", f"重新下载失败: {e}")
                    return False
            
            # 4. 安装到设备
            self.log_message(f"📲 正在安装 ADBKeyboard 到设备 {device}...", "info")
            self.adbkeyboard_status_label.config(text="📲 正在安装...", foreground="orange")
            self.root.update()
            
            cmd = [self.adb_path, '-s', device, 'install', '-r', apk_filename]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                self.log_message("✅ ADBKeyboard 安装成功！", "info")
                self.adbkeyboard_status_label.config(text="✅ 安装成功！", foreground="green")
                messagebox.showinfo("安装成功", "ADBKeyboard 已成功安装到设备！\n\n点击「检测并激活」切换输入法。")
                
                # 自动尝试激活
                self.check_and_activate_adbkeyboard(device)
                return True
            else:
                error_msg = result.stderr if result.stderr else result.stdout
                self.log_message(f"❌ 安装失败: {error_msg}", "error")
                
                # 检查是否是 INSTALL_FAILED_ALREADY_EXISTS
                if "INSTALL_FAILED_ALREADY_EXISTS" in error_msg:
                    self.adbkeyboard_status_label.config(text="⚠️ 已安装 (可重新安装)", foreground="orange")
                    messagebox.showinfo("已安装", "ADBKeyboard 已经安装在设备上。\n\n如需重新安装，请先卸载旧版本。")
                else:
                    self.adbkeyboard_status_label.config(text="❌ 安装失败", foreground="red")
                    messagebox.showerror("安装失败", f"安装失败:\n{error_msg}\n\n可能的原因:\n1. 设备未连接\n2. USB调试未开启\n3. 安装权限不足")
                return False
                
        except Exception as e:
            self.adbkeyboard_status_label.config(text="❌ 操作失败", foreground="red")
            self.log_message(f"❌ 安装过程出错: {e}", "error")
            messagebox.showerror("错误", f"安装过程中出错:\n{e}")
            return False

    def check_and_activate_adbkeyboard(self, device=None):
        """
        检测ADBKeyboard是否已安装，尝试切换，失败则提示手动切换
        """
        if device is None:
            device = self.get_selected_device()
            if not device:
                self.adbkeyboard_status_label.config(text="❌ 未选择设备", foreground="red")
                return False
        
        try:
            # 1. 检查ADBKeyboard是否已安装
            cmd = [self.adb_path, '-s', device, 'shell', 'pm', 'list', 'packages', 'com.android.adbkeyboard']
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            
            if 'com.android.adbkeyboard' not in result.stdout:
                self.adbkeyboard_status_label.config(text="❌ ADBKeyboard未安装", foreground="red")
                self.log_message("❌ ADBKeyboard未安装，请先安装ADBKeyboard.apk", "error")
                messagebox.showerror("错误", 
                    "ADBKeyboard未安装！\n\n"
                    "请下载 ADBKeyboard.apk 并安装：\n"
                    "1. 下载 ADBKeyboard.apk\n"
                    "2. 执行: adb install ADBKeyboard.apk")
                return False
            
            # 2. 尝试切换输入法（可能因权限失败）
            self.adbkeyboard_status_label.config(text="🔄 正在尝试切换输入法...", foreground="orange")
            self.log_message("🔄 正在尝试切换到ADBKeyboard...", "info")
            
            switch_success = False
            error_msg = ""
            
            # 方法1: 使用 ime set（标准方法）
            try:
                cmd = [self.adb_path, '-s', device, 'shell', 'ime', 'set', 'com.android.adbkeyboard/.AdbIME']
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    switch_success = True
                    self.log_message("✅ 已通过 ime set 切换输入法", "info")
                else:
                    error_msg = result.stderr.strip()
            except Exception as e:
                error_msg = str(e)
            
            # 方法2: 如果方法1失败，尝试启用 + 设置
            if not switch_success:
                try:
                    # 先启用
                    cmd = [self.adb_path, '-s', device, 'shell', 'ime', 'enable', 'com.android.adbkeyboard/.AdbIME']
                    subprocess.run(cmd, capture_output=True, timeout=3)
                    time.sleep(0.2)
                    
                    # 尝试通过 settings 设置
                    cmd = [self.adb_path, '-s', device, 'shell', 'settings', 'put', 'secure', 
                        'default_input_method', 'com.android.adbkeyboard/.AdbIME']
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
                    if result.returncode == 0:
                        switch_success = True
                        self.log_message("✅ 已通过 settings 切换输入法", "info")
                except Exception as e:
                    pass
            
            # 3. 更新状态显示
            if switch_success:
                self.adbkeyboard_status_label.config(text="✅ ADBKeyboard已激活", foreground="green")
                self.log_message("✅ ADBKeyboard已成功切换为当前输入法", "info")
            else:
                self.adbkeyboard_status_label.config(
                    text="⚠️ ADBKeyboard已安装 (请手动切换输入法)", 
                    foreground="orange"
                )
                self.log_message(f"⚠️ 无法自动切换输入法: {error_msg}", "warning")
                self.log_message("💡 请手动在设备设置中切换输入法为 ADBKeyboard", "info")
                
                # 只提示一次，避免频繁弹窗
                if not hasattr(self, '_manual_switch_shown'):
                    self._manual_switch_shown = True
                    messagebox.showinfo("手动切换提示", 
                        "ADBKeyboard已安装，但无法自动切换输入法。\n\n"
                        "请按以下步骤手动切换：\n"
                        "1. 在模拟器/设备中打开任意输入框\n"
                        "2. 点击键盘切换图标\n"
                        "3. 选择 ADBKeyboard 输入法\n\n"
                        "之后就可以正常输入中文了！")
            
            return True  # 无论是否切换成功，只要安装了就返回True，允许尝试输入
                    
        except Exception as e:
            self.adbkeyboard_status_label.config(text=f"❌ 检测失败: {e}", foreground="red")
            self.log_message(f"❌ 检测ADBKeyboard失败: {e}", "error")
            return False

    def ensure_adbkeyboard_ready(self, device=None):
        """
        确保ADBKeyboard已准备就绪（尝试切换，失败也继续）
        """
        if device is None:
            device = self.get_selected_device()
            if not device:
                return False
        
        # 直接调用检测方法
        return self.check_and_activate_adbkeyboard(device)

    def test_adbkeyboard_input(self):
        """测试使用ADBKeyboard输入中文"""
        device = self.get_selected_device()
        if not device:
            return
        
        text = self.test_text_entry.get().strip()
        if not text:
            messagebox.showwarning("警告", "请输入要测试的文本")
            return
        
        # 直接尝试输入（内部会尝试切换并提示）
        self.input_chinese(text)

    def show_adbkeyboard_help(self):
        """显示ADBKeyboard使用帮助"""
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
        """在日志区域添加消息"""
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
    app = ADBGUI(root)
    root.mainloop()