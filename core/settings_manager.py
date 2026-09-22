import os
import json


class SettingsManager:
    """设置管理器 - 负责加载、保存和管理设置数据"""

    def __init__(self, settings_file=None):
        if settings_file is None:
            # 基于本文件所在目录的上一级（项目根）定位配置文件
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            settings_file = os.path.join(base_dir, "adb_settings.json")
        self.settings_file = settings_file
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
        return self.settings.get(key, default)

    def set_value(self, key, value):
        self.settings[key] = value
        self.save_settings()

    def delete_key(self, key):
        if key in self.settings:
            del self.settings[key]
            self.save_settings()
            return True
        return False

    def get_all(self):
        return self.settings.copy()

    def update_settings(self, new_settings):
        self.settings.update(new_settings)
        self.save_settings()