# functions.py - 外部功能函数文件
# 这个文件可以放在程序同目录下，修改后无需重新打包

import os
import time
import hashlib

import subprocess
from PIL import Image

# 功能配置 - 定义每个功能的显示名称、颜色和描述
FUNCTION_CONFIGS = {
    "新增拜访": {
        "color": "#4CAF50"
    }
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
            self.log_message("找到图片:" + imgPath, "info")
            self.click_point(pos[0] + xOffset, pos[1] + yOffset)
            return True
        self.log_message("无法找到:" + imgPath, "info")
        return False

    # ========== 以下是具体的功能函数 ==========

            
    def capture_and_upload(self, device=None):
        """
        截取设备屏幕并上传到服务器
        
        :param device: 设备序列号，None则使用当前选中的设备
        :param server_url: 服务器上传地址
        :return: (success, response_text) 或 (False, error_message)
        """
        
        
        if device is None:
            device = self.get_selected_device()
            if not device:
                return False, "未选择设备"
            else:
                self.log_message(f"选择设备: {device}", "info")
        
        try:
            import requests
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


    def 新增拜访(self):
        khxmList = self.settings_mgr.get_value("客户姓名", "")
        if (khxmList != ""):
            khxmList = khxmList.split('@')
            print(khxmList)
            index = 0
            for khxm in khxmList:
                print(index)
                print(khxm)
                fwlx = self.settings_mgr.get_value("访问类型", "1")

                bfdz = self.settings_mgr.get_value("拜访地址", "1")

                bfzj = self.settings_mgr.get_value("拜访总结", "1")

                qdlb = self.settings_mgr.get_value("签到列表", "1")

                self.click_point(1120, 186)
                time.sleep(2)
                # 点临时拜访
                self.click_point(578, 622)
                time.sleep(4)
                # 拜访类型 
                self.click_point(445, 934)
                time.sleep(2)
                
                fwlx = int(fwlx)
                if (fwlx == 1):
                    self.click_point(578, 1822)
                if (fwlx == 2):
                    self.click_point(333, 1947)
                if (fwlx == 3):
                    self.click_point(578, 2329)
                time.sleep(2)
                # 客户姓名
                self.click_point(570, 1204)
                time.sleep(2)
                
                
                self.click_point(424, 1141)
                time.sleep(2)
                self.input_chinese(khxm)
                time.sleep(1)
                # 搜索
                self.click_point(1074, 1146)
                time.sleep(1)
                # 选择
                self.click_point(645, 1370)
                time.sleep(2)
                self.swipe(608, 2200, 570, 1500)
                time.sleep(2)
                # 拜访目的
                self.click_point(466, 1644)
                time.sleep(2)
                # 固定值 学术信息传递
                self.click_point(437, 2013)
                time.sleep(2)
                self.swipe(608, 2200, 570, 1500)

                time.sleep(2)
                # 拜访地址
                self.click_point(466, 1615)
                time.sleep(2)
                # 固定选第一个
                if (bfdz == "1"):
                    self.click_point(558, 1291)
                if (bfdz == "2"):
                    self.click_point(558, 1391)
                time.sleep(2)

                # 品牌提示
                self.click_point(528, 2063)
                time.sleep(2)
                # 固定选第一个
                self.click_point(341, 1822)
                time.sleep(2)

                self.swipe(608, 2200, 570, 1200)
                time.sleep(2)

                # 拜访效果
                self.click_point(703, 1287)
                time.sleep(2)
                # 固定选第一个
                self.click_point(574, 1818)
                time.sleep(1)

                self.swipe(608, 2200, 570, 1200)
                time.sleep(2)

                # 拜访总结
                
                self.click_point(524, 469)
                time.sleep(2)
                self.input_chinese(bfzj)
                time.sleep(2)

                # 拜访积分
                bfjf = self.settings_mgr.get_value("拜访积分", "")
                self.click_point(399, 1590)
                time.sleep(1)
                self.input_chinese(str(bfjf))
                time.sleep(2)


                # 签到地址
                self.click_point(995, 2350)
                time.sleep(2)
                # 先暂时第一个
                if (qdlb == "1"):
                    self.click_point(608, 1104)
                if (qdlb == "2"):
                    self.click_point(608, 1391)
                time.sleep(1)

                # self.swipe(608, 2200, 570, 1200)
                # time.sleep(2)
                
                # 确定
                self.click_point(920, 2499)
                time.sleep(2)
                self.click_point(787, 1515)
                time.sleep(2)
                self.click_point(1099, 170)
                time.sleep(2)
                index = index + 1

        else:
            self.log_message("客户姓名为空!", "error")