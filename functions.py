# functions.py - 外部功能函数文件
# 这个文件可以放在程序同目录下，修改后无需重新打包

import time
import hashlib
import subprocess
from PIL import Image

# 功能配置 - 定义每个功能的显示名称、颜色和描述
FUNCTION_CONFIGS = {
    "寻找可关注": {
        "color": "#4CAF50",
        "desc": "执行寻找可关注任务"
    },
    "寻找可收藏": {
        "color": "#4CAF50",
        "desc": "执行寻找可收藏任务"
    },
    "关注列表私信": {
        "color": "#4CAF50",
        "desc": "执行关注列表私信任务"
    },
    "滑动到关注第一个": {
        "color": "#4CAF50",
        "desc": "执行滑动到关注第一个任务"
    },
}


class Functions:
    """外部功能函数类 - 所有功能都定义在这里"""
    
    def __init__(self, app):
        self.app = app
        self.settings_mgr = app.settings_mgr
    
    def get_color(self, x, y, device=None):
        """获取颜色 - 调用主程序的取色方法"""
        return self.app.get_color(x, y, device)
    
    def find_image(self, image_path, device=None, threshold=None, use_cache=False):
        """找图 - 调用主程序的找图方法"""
        return self.app.find_image(image_path, device, threshold, use_cache)

    def find_image_first(self, image_path, device=None, threshold=None, use_cache=False):
        """找图 - 调用主程序的找图方法返回匹配的第一个"""
        return self.app.find_image_first(image_path, device, threshold, use_cache)
    
    def press_back(self,device=None):
            """点击 - 调用主程序的返回方法"""
            return self.app.press_back(device)
    
    def click_point(self, x, y, device=None, delay=None):
        """点击 - 调用主程序的点击方法"""
        return self.app.click_point(x, y, device, delay)
    
    def long_press(self, x, y, duration, device=None):
        """长按 - 调用主程序的长按方法"""
        return self.app.long_press(x, y, duration, device)
    def swipe(self, x1, y1, x2, y2, duration=300, device=None):
        """滑动 - 调用主程序的滑动方法"""
        return self.app.swipe(x1, y1, x2, y2, duration, device)
    
    def input_number_with_backspace(self, target_number, delete_count=1, device=None):
        """输入数字 - 调用主程序的输入方法"""
        return self.app.input_number_with_backspace(target_number, delete_count, device)
    def input_chinese(self, text, device=None):
        return self.app.input_chinese(text, device)
    
    def log_message(self, msg, level="info"):
        """日志 - 调用主程序的日志方法"""
        self.app.log_message(msg, level)
    def get_selected_device(self):
        return self.app.get_selected_device()
    def get_screen_size(self, device=None):
        """获取颜色 - 调用主程序的取色方法"""
        return self.app.get_screen_size(device)
    def findImgAndClick(self, imgPath, xOffset = 0, yOffset = 0, use_cache=False, thresholdValue=0.8):
        threshold = self.settings_mgr.get_value("image_threshold", 0.8)
        pos = self.find_image(imgPath, threshold=threshold, use_cache=use_cache)
        if pos:
            self.log_message("找到星星按钮", "info")
            self.click_point(pos[0] + xOffset, pos[1] + yOffset)
            return True
        return False

    # ========== 以下是具体的功能函数 ==========
    
            
    def capture_and_upload(self, device=None):
        """
        截取设备屏幕并上传到服务器
        
        :param device: 设备序列号，None则使用当前选中的设备
        :param server_url: 服务器上传地址
        :return: (success, response_text) 或 (False, error_message)
        """
        import requests
        import os
        
        if device is None:
            device = self.get_selected_device()
            if not device:
                return False, "未选择设备"
            else:
                self.log_message(f"选择设备: {device}", "info")
        
        try:
            # 1. 截图保存到本地临时文件
            local_screen = "temp_upload_screen.png"
            server_url="http://localhost:5000/upload/" + hashlib.md5(device.encode('utf-8')).hexdigest()
            # 使用 exec-out 方式截图（更快）
            with open(local_screen, 'wb') as f:
                cmd = ['adb', '-s', device, 'exec-out', 'screencap', '-p']
                subprocess.run(cmd, stdout=f, check=True, timeout=15)
            
            self.log_message(f"截图已保存到: {local_screen}", "info")
            
            # 2. 检查文件是否存在
            if not os.path.exists(local_screen):
                return False, "截图文件创建失败"
            
            # 3. 上传到服务器
            try:
                with open(local_screen, 'rb') as f:
                    files = {'image': (local_screen, f, 'image/png')}
                    response = requests.post(server_url, files=files, timeout=30)
                    
                # 删除临时文件
                try:
                    os.remove(local_screen)
                except:
                    pass
                
                if response.status_code == 200:
                    self.log_message(f"图片上传成功: {server_url}", "info")
                    return True, response.text
                else:
                    error_msg = f"上传失败，状态码: {response.status_code}, 响应: {response.text}"
                    self.log_message(error_msg, "error")
                    return False, error_msg
                    
            except requests.exceptions.ConnectionError:
                self.log_message(f"无法连接到服务器: {server_url}", "error")
                return False, "服务器连接失败"
            except requests.exceptions.Timeout:
                self.log_message("上传超时", "error")
                return False, "上传超时"
            except Exception as e:
                error_msg = f"上传异常: {e}"
                self.log_message(error_msg, "error")
                return False, error_msg
                
        except subprocess.TimeoutExpired:
            self.log_message("截图超时", "error")
            return False, "截图超时"
        except Exception as e:
            error_msg = f"截图失败: {e}"
            self.log_message(error_msg, "error")
            return False, error_msg
        



    def 关注列表私信(self):
        self.click_point(491, 552)
        time.sleep(2)
        self.findImgAndClick("./抖音榜单/sendMessage.png", 0 , 0, True)
        time.sleep(2)
        self.findImgAndClick("./抖音榜单/more.png", 180 , 0, True)
        time.sleep(2)
        self.input_chinese("sdsd")
        time.sleep(2)
        self.press_back()
        time.sleep(2)
        self.press_back()
        time.sleep(3)
        # 判断是否在发私信页面
        threshold = self.settings_mgr.get_value("image_threshold", 0.8)
        pos = self.find_image("./抖音榜单/sendMessage.png", threshold=threshold, use_cache=False)
        if pos:
            self.press_back()
            time.sleep(2)
        
        self.swipe(530, 1300, 530, 1200)

    def 滑动到关注第一个(self):
        threshold = self.settings_mgr.get_value("image_threshold", 0.8)
        pos = self.find_image("./抖音榜单/wdgz.png", threshold=threshold, use_cache=False)
        if pos:
            self.log_message("找到好友按钮", "info")
            # time.sleep(2)
            self.swipe(530, 1461, 530, 1200)
        else:
            self.log_message("没有找到好友", "info")
            

        
    def 寻找可收藏(self):
        self.findImgAndClick("./抖音榜单/collect.png", 0 , 0)
        time.sleep(1)

        self.swipe(530, 1396, 530, 1183)

    def 寻找可关注(self):
        self.findImgAndClick("./抖音榜单/collect.png", -100 , 0)
        time.sleep(2)
        self.findImgAndClick("./抖音榜单/focus.png", 0 , 0)
        time.sleep(6)
        self.press_back()
        time.sleep(2)
        self.swipe(530, 1596, 530, 1183)

