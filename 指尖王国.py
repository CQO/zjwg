import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import subprocess
import threading
import time
import os
import re
import json
import sys
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
        
    def set_task_queue(self, task_queue):
        """设置任务队列"""
        self.task_queue = task_queue.copy()
        
    def add_task(self, task_name, times=1, interval=1.0):
        """添加任务到队列末尾"""
        self.task_queue.append([task_name, times, interval])
        
    def insert_task(self, index, task_name, times=1, interval=1.0):
        """在指定位置插入任务"""
        self.task_queue.insert(index, [task_name, times, interval])
        
    def remove_task(self, index):
        """移除指定位置的任务"""
        if 0 <= index < len(self.task_queue):
            del self.task_queue[index]
            return True
        return False
        
    def clear_tasks(self):
        """清空任务队列"""
        self.task_queue.clear()
        
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
        self.app.log_message("正在停止任务...", "info")
        self.stop_event.set()
    
    def _task_loop(self):
        """任务执行主循环"""
        total_tasks = len(self.task_queue)
        task_index = 0
        
        while not self.stop_event.is_set() and task_index < total_tasks:
            # 获取当前任务
            task_info = self.task_queue[task_index]
            task_name = task_info[0]
            times = task_info[1]
            interval = task_info[2] if len(task_info) > 2 else 1.0
            
            # 更新状态
            self.current_task_index = task_index
            self.current_task_remaining = times
            
            self.app.root.after(0, lambda: self.app.update_task_status(
                f"执行中: {task_name} ({times}次) [{task_index+1}/{total_tasks}]", 
                "orange"
            ))
            self.app.log_message(f"开始执行任务 [{task_index+1}/{total_tasks}]: {task_name} (共{times}次)", "info")
            
            # 执行当前任务指定次数
            for i in range(times):
                if self.stop_event.is_set():
                    break
                
                self.current_task_remaining = times - i - 1
                self.app.root.after(0, lambda n=task_name, c=i+1, t=times: 
                    self.app.update_task_status(
                        f"执行中: {n} [{c}/{t}]", 
                        "orange"
                    ))
                
                try:
                    # 执行任务函数 - 从app中获取方法
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
                task_index += 1
                if task_index < total_tasks:
                    time.sleep(0.5)
        
        # 任务结束
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
        self.root.title("ADB 模拟器自动化控制")
        self.root.geometry("1200x750")
        self.root.resizable(True, True)
        
        # 初始化设置管理器
        self.settings_mgr = SettingsManager()
        
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
            "城墙": {"color": "#4CAF50", "desc": "执行城墙任务"},
            "战令活动": {"color": "#FF9800", "desc": "执行战令活动任务"},
            "挂机奖励": {"color": "#2196F3", "desc": "执行挂机奖励任务"},
            "征兵任务": {"color": "#4CAF50", "desc": "执行征兵任务"},
            "采集金矿": {"color": "#FF9800", "desc": "执行采集金矿任务"},
            "采集农田": {"color": "#FF9800", "desc": "执行采集农田任务"},
            "采集伐木场": {"color": "#FF9800", "desc": "执行采集伐木场任务"},
            "采集水晶矿": {"color": "#FF9800", "desc": "执行采集水晶矿任务"},
            "集结泰坦": {"color": "#FF9800", "desc": "执行集结泰坦任务"},
            "集结哈罗德": {"color": "#FF9800", "desc": "执行集结哈罗德任务"},
            "搜索任务": {"color": "#4CAF50", "desc": "执行搜索任务"},
        }
        
        # 定义内置功能方法
        self._define_builtin_functions()
        self.log_message("使用内置功能", "info")
    
    def _define_builtin_functions(self):
        """定义内置功能方法"""
        # 城墙
        def 城墙():
            color = self.get_color(110, 1251)
            if color and color.lower() != '42AAE7':
                self.log_message("进入城堡页面", "info")
                self.click_point(110, 1251)
                time.sleep(2)
            
            self.log_message("进入城墙界面", "info")
            self.click_point(364, 904)
            time.sleep(2)
            
            retry_times = self.settings_mgr.get_value("retry_times", 3)
            for i in range(retry_times):
                if self.get_color(300, 1180) == '4282C6':
                    break
                self.log_message(f"等待城堡页面加载... (尝试 {i+1}/{retry_times})", "info")
                time.sleep(1)
            
            self.log_message("领取收益", "info")    
            self.click_point(580, 1210)
            time.sleep(2) 
            self.click_point(357, 1153)
            time.sleep(2)
            self.log_message("一键驻防", "info")    
            self.click_point(300, 1180)
            time.sleep(2)
            self.click_point(53, 157)
        setattr(self, "城墙", 城墙)
        
        # 战令活动
        def 战令活动():
            time.sleep(2)
            self.click_point(673, 596)
            time.sleep(3)
            
            threshold = self.settings_mgr.get_value("image_threshold", 0.8)
            pos = self.find_image("1.png", threshold=threshold)
            if pos:
                self.log_message(f"找到图片位置: {pos}", "info")
                self.click_point(pos[0] - 100, pos[1])
                time.sleep(2)
                self.click_point(pos[0] - 100, pos[1])
            else:
                self.log_message("未找到图片", "info")
            time.sleep(2)
            self.click_point(45, 72)
        setattr(self, "战令活动", 战令活动)
        
        # 挂机奖励
        def 挂机奖励():
            time.sleep(2)
            self.click_point(420, 1237)
            time.sleep(4)
            self.click_point(205, 844)
            time.sleep(2)
            self.click_point(538, 866)
            time.sleep(2)
            self.click_point(368, 744)
            
            time.sleep(3)
            self.click_point(205, 844)
            time.sleep(2)
            
            max_retries = self.settings_mgr.get_value("retry_times", 3)
            retry_count = 0
            while self.get_color(382, 873).startswith('42') and retry_count < max_retries:
                self.log_message("可以进行扫荡...", "info")
                self.click_point(382, 873)
                time.sleep(4)
                retry_count += 1
            
            while self.get_color(218, 655) == '5ACF39':
                self.log_message("尝试看广告...", "info")
                self.click_point(218, 655)
                time.sleep(1)
                if self.get_color(365, 681) != 'DEEBF7':
                    self.click_point(365, 681)
                else:
                    self.log_message("看不了广告了 下一步...", "info")
                    break
            
            self.click_point(671, 293)
            time.sleep(3)
            self.log_message("看广告...", "info")
            
            while self.get_color(189, 441) == 'DEEBF7':
                self.click_point(174, 872)
                time.sleep(1)
            self.log_message("返回主页面...", "info")
            self.click_point(671, 293)
        setattr(self, "挂机奖励", 挂机奖励)
        
        # 征兵任务
        def 征兵任务():
            time.sleep(1)
            self.click_point(66, 1236)
            time.sleep(2)
            self.click_point(208, 489)
            time.sleep(1)
            self.click_point(137, 205)
            
            threshold = self.settings_mgr.get_value("image_threshold", 0.8)
            pos = self.find_image("zhengbing.png", threshold=threshold)
            if pos:
                self.log_message(f"找到征兵按钮: {pos}", "info")
                self.click_point(pos[0], pos[1])
            
            time.sleep(2)
            self.click_point(52, 109)
        setattr(self, "征兵任务", 征兵任务)
        
        # 采集函数
        def 采集金矿():
            self._采集(150)
        setattr(self, "采集金矿", 采集金矿)
        
        def 采集农田():
            self._采集(300)
        setattr(self, "采集农田", 采集农田)
        
        def 采集伐木场():
            self._采集(450)
        setattr(self, "采集伐木场", 采集伐木场)
        
        def 采集水晶矿():
            self._采集(600)
        setattr(self, "采集水晶矿", 采集水晶矿)
        
        def _采集(xPoint):
            if self.get_color(700, 1225) != 'FFCB4A':
                self.click_point(700, 1225)
                time.sleep(4)
            self.click_point(700, 1225)
            time.sleep(1)
            self.click_point(277, 381)
            time.sleep(1)
            self.click_point(xPoint, 550)
            time.sleep(1)
            self.click_point(370, 920)
            time.sleep(4)
            self.click_point(357, 615)
            time.sleep(3)
            
            threshold = self.settings_mgr.get_value("image_threshold", 0.8)
            pos = self.find_image("6.png", threshold=threshold)
            if pos:
                self.log_message(f"找到采集按钮: {pos}", "info")
                self.click_point(pos[0], pos[1])
                time.sleep(2)
                if self.设置出兵数量():
                    self.log_message(f"设置出兵量成功!", "info")
                    pos = self.find_image("2.png", threshold=threshold)
                    if pos:
                        self.log_message(f"找到出发位置: {pos}", "info")
                        self.click_point(pos[0], pos[1])
        setattr(self, "_采集", _采集)
        
        # 集结泰坦
        def 集结泰坦():
            if self.get_color(700, 1225) != 'FFCB4A':
                self.click_point(700, 1225)
                time.sleep(4)
            self.click_point(700, 1225)
            time.sleep(1)
            self.click_point(443, 383)
            time.sleep(1)
            self.click_point(435, 920)
            time.sleep(2)
            
            threshold = self.settings_mgr.get_value("image_threshold", 0.8)
            pos = self.find_image("7.png", threshold=threshold)
            if pos is None:
                pos = self.find_image("5.png", threshold=threshold)
            if pos:
                self.log_message(f"找到集结按钮: {pos}", "info")
                self.click_point(pos[0], pos[1])
                time.sleep(3)
                if self.设置出兵数量():
                    self.log_message(f"设置出兵量成功!", "info")
                    pos = self.find_image("2.png", threshold=threshold)
                    if pos:
                        self.log_message(f"找到出发位置: {pos}", "info")
                        self.click_point(pos[0], pos[1])
        setattr(self, "集结泰坦", 集结泰坦)
        
        # 集结哈罗德
        def 集结哈罗德():
            if self.get_color(700, 1225) != 'FFCB4A':
                self.click_point(700, 1225)
                time.sleep(4)
            self.click_point(700, 1225)
            time.sleep(1)
            self.click_point(604, 383)
            time.sleep(1)
            self.click_point(435, 920)
            time.sleep(2)
            
            threshold = self.settings_mgr.get_value("image_threshold", 0.8)
            pos = self.find_image("7.png", threshold=threshold)
            if pos is None:
                pos = self.find_image("5.png", threshold=threshold)
            if pos:
                self.log_message(f"找到集结按钮: {pos}", "info")
                self.click_point(pos[0], pos[1])
                time.sleep(3)
                if self.设置出兵数量():
                    self.log_message(f"设置出兵量成功!", "info")
                    pos = self.find_image("2.png", threshold=threshold)
                    if pos:
                        self.log_message(f"找到出发位置: {pos}", "info")
                        self.click_point(pos[0], pos[1])
        setattr(self, "集结哈罗德", 集结哈罗德)
        
        # 搜索任务
        def 搜索任务():
            列表搜索点坐标X = self.settings_mgr.get_value("搜索点坐标X", "").split('@')
            列表搜索点坐标Y = self.settings_mgr.get_value("搜索点坐标Y", "").split('@')
            
            for i in range(len(列表搜索点坐标X)):
                搜索点坐标X = 列表搜索点坐标X[i]
                搜索点坐标Y = 列表搜索点坐标Y[i]
                
                if self.get_color(700, 1225) != 'FFCB4A':
                    self.click_point(700, 1225)
                    time.sleep(2)
                
                self.click_point(120, 195)
                time.sleep(1)
                self.click_point(235, 584)
                time.sleep(1)
                self.input_number_with_backspace(搜索点坐标X, 4)
                time.sleep(1)
                self.click_point(635, 1218)
                time.sleep(1)
                self.click_point(518, 584)
                time.sleep(1)
                self.input_number_with_backspace(搜索点坐标Y, 4)
                time.sleep(1)
                self.click_point(366, 684)
                time.sleep(3)
                self.click_point(379, 646)
                time.sleep(1)
                
                threshold = self.settings_mgr.get_value("image_threshold", 0.8)
                pos = self.find_image("4.png", threshold=threshold)
                if pos:
                    self.log_message(f"防御位置: {pos}", "info")
                    self.click_point(pos[0], pos[1])
                if pos is None:
                    pos = self.find_image("5.png", threshold=threshold)
                    if pos:
                        self.log_message(f"发起集结: {pos}", "info")
                        self.click_point(pos[0], pos[1])
                if pos is None:
                    pos = self.find_image("6.png", threshold=threshold)
                    if pos:
                        self.log_message(f"发起采集: {pos}", "info")
                        self.click_point(pos[0], pos[1])
                
                if pos is None:
                    self.log_message(f"找不到对应的操作", "info")
                    self.关闭弹窗()
                    continue
                
                time.sleep(1)
                self.click_point(227, 486)
                time.sleep(2)
                
                pos = self.find_image("3.png", threshold=threshold)
                if pos:
                    self.log_message(f"找到设置位置: {pos}", "info")
                    self.click_point(pos[0], pos[1])
                    time.sleep(1)
                    self.click_point(610, 605)
                    time.sleep(1)
                    self.input_number_with_backspace(self.settings_mgr.get_value("派出兵力", "1"), 7)
                    time.sleep(1)
                    self.click_point(635, 1218)
                    time.sleep(1)
                    self.click_point(515, 1208)
                    time.sleep(1)
                    pos = self.find_image("2.png", threshold=threshold)
                    if pos:
                        self.log_message(f"找到出发按钮: {pos}", "info")
                        self.click_point(pos[0], pos[1])
                else:
                    self.log_message(f"没有找到设置位置!", "error")
                time.sleep(10)
        setattr(self, "搜索任务", 搜索任务)
        
        # 辅助函数
        def 关闭弹窗():
            threshold = self.settings_mgr.get_value("image_threshold", 0.8)
            pos = self.find_image("close.png", threshold=threshold)
            if pos:
                self.log_message(f"关闭弹窗: {pos}", "info")
                self.click_point(pos[0], pos[1])
        setattr(self, "关闭弹窗", 关闭弹窗)
        
        def 设置出兵数量():
            threshold = self.settings_mgr.get_value("image_threshold", 0.8)
            pos = self.find_image("3.png", threshold=threshold)
            if pos:
                self.log_message(f"找到设置位置: {pos}", "info")
                self.click_point(pos[0], pos[1])
                time.sleep(1)
                self.click_point(610, 605)
                time.sleep(1)
                self.input_number_with_backspace(self.settings_mgr.get_value("派出兵力", "1"), 7)
                time.sleep(1)
                self.click_point(635, 1218)
                time.sleep(1)
                self.click_point(515, 1208)
                time.sleep(1)
                return True
            return False
        setattr(self, "设置出兵数量", 设置出兵数量)
    
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
        reload_btn = ttk.Button(left_frame, text="🔄 重载功能", 
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
        
        ttk.Button(operation_frame, text="➕ 添加到队列", 
                   command=self.add_task_to_queue, width=18).pack(pady=5)
        ttk.Button(operation_frame, text="📋 从快捷功能导入", 
                   command=self.import_from_quick_functions, width=18).pack(pady=5)
        
        # 下半部分：任务控制
        bottom_half = ttk.Frame(task_main_frame)
        bottom_half.pack(fill=tk.X, pady=(10, 0))
        
        control_frame = ttk.LabelFrame(bottom_half, text="任务控制", padding=10)
        control_frame.pack(fill=tk.X)
        
        btn_frame = ttk.Frame(control_frame)
        btn_frame.pack(fill=tk.X, pady=5)
        
        self.start_btn = ttk.Button(btn_frame, text="▶ 启动任务队列", 
                                    command=self.start_task_queue, width=15)
        self.start_btn.pack(side=tk.LEFT, padx=5)
        
        self.stop_btn = ttk.Button(btn_frame, text="⏹ 停止任务", 
                                   command=self.stop_task_queue, width=15, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(btn_frame, text="🗑 清空队列", 
                   command=self.clear_tasks, width=15).pack(side=tk.LEFT, padx=5)
        
        # 状态显示
        self.task_status_label = ttk.Label(control_frame, text="状态: 空闲", foreground="green")
        self.task_status_label.pack(pady=5)
        
        # 进度信息
        self.task_progress_label = ttk.Label(control_frame, text="", foreground="blue")
        self.task_progress_label.pack()
    
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
    
    def import_from_quick_functions(self):
        """从快捷功能导入选中的任务"""
        # 打开一个对话框选择要导入的任务
        dialog = tk.Toplevel(self.root)
        dialog.title("导入任务")
        dialog.geometry("400x400")
        dialog.transient(self.root)
        dialog.grab_set()
        
        ttk.Label(dialog, text="选择要导入的任务:", font=('Arial', 10, 'bold')).pack(pady=10)
        
        # 创建带滚动条的任务列表
        list_frame = ttk.Frame(dialog)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # 使用Listbox支持多选
        listbox = tk.Listbox(list_frame, selectmode=tk.MULTIPLE, height=15)
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=listbox.yview)
        listbox.configure(yscrollcommand=scrollbar.set)
        
        listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 填充所有可用功能
        for name in self.function_configs.keys():
            listbox.insert(tk.END, name)
        
        # 参数输入
        param_frame = ttk.Frame(dialog)
        param_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Label(param_frame, text="执行次数:").pack(side=tk.LEFT, padx=5)
        times_entry = ttk.Entry(param_frame, width=10)
        times_entry.insert(0, "1")
        times_entry.pack(side=tk.LEFT, padx=5)
        
        ttk.Label(param_frame, text="间隔(秒):").pack(side=tk.LEFT, padx=5)
        interval_entry = ttk.Entry(param_frame, width=10)
        interval_entry.insert(0, "1.0")
        interval_entry.pack(side=tk.LEFT, padx=5)
        
        def confirm_import():
            selected = listbox.curselection()
            if not selected:
                messagebox.showwarning("警告", "请选择至少一个任务")
                return
            
            try:
                times = int(times_entry.get())
                if times <= 0:
                    raise ValueError
            except ValueError:
                messagebox.showerror("错误", "请输入有效的执行次数")
                return
            
            try:
                interval = float(interval_entry.get())
                if interval < 0:
                    raise ValueError
            except ValueError:
                messagebox.showerror("错误", "请输入有效的间隔时间")
                return
            
            # 添加选中的任务
            for idx in selected:
                task_name = listbox.get(idx)
                self.task_manager.add_task(task_name, times, interval)
            
            self.refresh_task_list()
            self.save_task_queue_to_settings()
            self.log_message(f"已导入 {len(selected)} 个任务", "info")
            dialog.destroy()
        
        ttk.Button(dialog, text="确认导入", command=confirm_import).pack(pady=10)
    
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
        
        if self.task_manager.start():
            self.start_btn.config(state=tk.DISABLED)
            self.stop_btn.config(state=tk.NORMAL)
            self.log_message("任务队列已启动", "info")
    
    def stop_task_queue(self):
        """停止任务队列"""
        if not self.task_manager.is_running:
            return
        self.task_manager.stop()
        self.start_btn.config(state=tk.DISABLED)
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
        max_cols = 4
        
        for name, config in self.function_configs.items():
            btn_frame = ttk.LabelFrame(parent_frame, text=name, padding=10)
            btn_frame.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")
            
            btn = tk.Button(
                btn_frame,
                text=f"▶ {name}",
                font=('Arial', 12, 'bold'),
                bg=config.get("color", "#E0E0E0"),
                fg="white",
                padx=20,
                pady=15,
                command=lambda n=name: self.execute_function(n),
                cursor="hand2"
            )
            btn.pack(fill=tk.X, pady=5)
            
            desc_label = ttk.Label(btn_frame, text=config.get("desc", ""), 
                                font=('Arial', 9), foreground="gray")
            desc_label.pack()
            
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
    
    def refresh_devices(self):
        """刷新ADB设备列表"""
        self.device_listbox.delete(0, tk.END)
        try:
            result = subprocess.run(['adb', 'devices'], capture_output=True, text=True, timeout=5)
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
                
            self.log_message("设备列表已刷新", "info")
        except Exception as e:
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
            cmd = ['adb', '-s', device, 'shell', 'screencap', temp_file]
            subprocess.run(cmd, capture_output=True, check=True, timeout=5)
            
            local_temp = "temp_screencap.png"
            pull_cmd = ['adb', '-s', device, 'pull', temp_file, local_temp]
            subprocess.run(pull_cmd, capture_output=True, check=True, timeout=5)
            
            img = Image.open(local_temp)
            pixel = img.getpixel((x, y))
            color_hex = f"{pixel[0]:02X}{pixel[1]:02X}{pixel[2]:02X}"
            
            os.remove(local_temp)
            subprocess.run(['adb', '-s', device, 'shell', 'rm', temp_file], capture_output=True, timeout=3)
            return color_hex
        except Exception as e:
            self.log_message(f"取色失败 ({x},{y}): {e}", "error")
            return None
    
    def find_image(self, image_path, device=None, threshold=None):
        """在模拟器屏幕上查找指定图片"""
        if threshold is None:
            threshold = self.settings_mgr.get_value("image_threshold", 0.8)
            
        if device is None:
            device = self.get_selected_device()
            if not device:
                return None
        
        try:
            local_screen = "temp_screen.png"
            with open(local_screen, 'wb') as f:
                cmd = ['adb', '-s', device, 'exec-out', 'screencap', '-p']
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
                    os.remove(local_screen)
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
            cmd = ['adb', '-s', device, 'shell', 'input', 'tap', str(x), str(y)]
            subprocess.run(cmd, capture_output=True, check=True, timeout=5)
            self.log_message(f"点击坐标 ({x}, {y})", "info")
            time.sleep(delay)
            return True
        except Exception as e:
            self.log_message(f"点击失败 ({x},{y}): {e}", "error")
            return False
        
    def long_press(self, x, y, duration, device=None):
        """长按指定坐标"""
        if device is None:
            device = self.get_selected_device()
            if not device:
                return False
        
        try:
            duration_ms = int(duration * 1000)
            cmd = ['adb', '-s', device, 'shell', 'input', 'swipe', str(x), str(y), str(x), str(y), str(duration_ms)]
            subprocess.run(cmd, capture_output=True, check=True, timeout=duration + 5)
            
            subprocess.run(['adb', '-s', device, 'shell', 'input', 'tap', str(x), str(y)], 
                        capture_output=True, check=True, timeout=2)
            
            self.log_message(f"长按坐标 ({x}, {y}) 持续 {duration} 秒", "info")
            return True
        except Exception as e:
            self.log_message(f"长按失败 ({x},{y}): {e}", "error")
            return False
    
    def input_number_with_backspace(self, target_number, delete_count=1, device=None):
        """在输入框中先按指定次数的退格键，然后输入新的数字"""
        if device is None:
            device = self.get_selected_device()
            if not device:
                return False
        
        try:
            for i in range(delete_count):
                cmd = ['adb', '-s', device, 'shell', 'input', 'keyevent', '67']
                subprocess.run(cmd, capture_output=True, check=True, timeout=2)
                time.sleep(0.15)
            
            time.sleep(0.3)
            
            number_str = str(target_number)
            for char in number_str:
                cmd = ['adb', '-s', device, 'shell', 'input', 'text', char]
                subprocess.run(cmd, capture_output=True, check=True, timeout=2)
                time.sleep(0.05)
            
            self.log_message(f"重新输入: {number_str} (已删除{delete_count}个字符)", "info")
            return True
        except Exception as e:
            self.log_message(f"输入数字失败: {e}", "error")
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
                    cmd = ['adb', '-s', device, 'exec-out', 'screencap', '-p']
                    subprocess.run(cmd, stdout=f, check=True, timeout=5)
                self.log_message(f"截图已保存: {file_path}", "info")
                messagebox.showinfo("成功", f"截图已保存到: {file_path}")
            except Exception as e:
                messagebox.showerror("错误", f"截图失败: {e}")
    
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