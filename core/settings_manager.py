import os
import sys
import json


class SettingsManager:
    """设置管理器 - 负责加载、保存和管理设置数据"""

    def __init__(self, settings_file=None):
        if settings_file is None:
            settings_file = self._get_default_settings_path()
        self.settings_file = settings_file
        self.settings = {}
        self.load_settings()

    @staticmethod
    def _get_default_settings_path():
        """获取默认配置文件路径（exe 同级 或 项目根目录）"""
        if getattr(sys, 'frozen', False):
            # 打包后（PyInstaller）：exe 所在目录
            base_dir = os.path.dirname(sys.executable)
        else:
            # 源码运行：项目根目录（本文件上一级）
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(base_dir, "adb_settings.json")

    def load_settings(self):
        """从文件加载设置"""
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    self.settings = json.load(f)
            else:
                # 创建默认设置
                self.settings = {
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