# function_manager.py - 功能模块管理器
import os
import sys
import importlib
import inspect
from typing import Dict, Any

class FunctionManager:
    """功能模块管理器 - 支持动态加载和管理外部功能"""
    
    def __init__(self, app):
        self.app = app
        self.modules = {}
        self.functions = {}
        self.configs = {}
        self.watcher = None
    
    def load_module(self, module_name: str) -> bool:
        """加载指定模块"""
        try:
            if module_name in sys.modules:
                del sys.modules[module_name]
            
            module = importlib.import_module(module_name)
            self.modules[module_name] = module
            
            # 加载配置
            if hasattr(module, 'FUNCTION_CONFIGS'):
                self.configs.update(module.FUNCTION_CONFIGS)
            
            # 加载功能类
            if hasattr(module, 'Functions'):
                func_class = getattr(module, 'Functions')
                instance = func_class(self.app)
                self.functions[module_name] = instance
                
                # 注册方法
                for func_name in dir(instance):
                    if not func_name.startswith('_') and callable(getattr(instance, func_name)):
                        if func_name in self.configs:
                            setattr(self.app, func_name, getattr(instance, func_name))
            
            return True
        except Exception as e:
            print(f"加载模块 {module_name} 失败: {e}")
            return False
    
    def reload_module(self, module_name: str) -> bool:
        """重新加载模块（热更新）"""
        try:
            if module_name in sys.modules:
                del sys.modules[module_name]
            return self.load_module(module_name)
        except Exception as e:
            print(f"重新加载模块 {module_name} 失败: {e}")
            return False
    
    def load_all_modules(self, module_dir: str = ".") -> int:
        """加载目录下所有功能模块"""
        count = 0
        for file in os.listdir(module_dir):
            if file.startswith('func_') and file.endswith('.py'):
                module_name = file[:-3]
                if self.load_module(module_name):
                    count += 1
        return count
    
    def get_all_functions(self) -> Dict[str, Any]:
        """获取所有已加载的功能"""
        return self.functions
    
    def get_function_configs(self) -> Dict[str, Dict]:
        """获取所有功能配置"""
        return self.configs