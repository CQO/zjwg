# functions.py - 外部功能函数文件
# 这个文件可以放在程序同目录下，修改后无需重新打包

import os
import time
import hashlib

import subprocess
from PIL import Image

# 功能配置 - 定义每个功能的显示名称、颜色和描述
FUNCTION_CONFIGS = {
    "回关并发私信": {
        "color": "#4CAF50",
        "desc": "回关并发私信"
    },
    "回关发私信下拉": {
        "color": "#4CAF50",
        "desc": "回关发私信下拉"
    },
    "自动回复通知": {
        "color": "#4CAF50",
        "desc": "自动回复通知"
    },
    "自动回复未读": {
        "color": "#4CAF50",
        "desc": "自动回复未读"
    },
    "测试提取文字": {
        "color": "#4CAF50",
        "desc": "测试提取文字"
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
    def get_screen_texts(self, device=None):
        return self.app.get_screen_texts(device)
    
    def find_texts_first(self, keyword, exact=False, device=None):
        items = self.app.get_screen_texts(device)
        if not items:
            return None
        for row in items:
            text, cx, cy = row[0], row[1], row[2]
            if (text == keyword) if exact else (keyword in text):
                self.log_message(f"找到文字 '{text[:20]}' → 坐标 ({cx}, {cy})", "info")
                return (cx, cy)
        return None
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
 
    def sendDouyinMessage(self):
        messagevalue = self.settings_mgr.get_value("消息内容", "")
        messagevalue2 = self.settings_mgr.get_value("消息内容2", "")
        messagevalue3 = self.settings_mgr.get_value("消息内容3", "")
        if (messagevalue != ""):
            
            inputPos = self.find_texts_first("发消息或按住说话...")
            
            if (not inputPos):
                inputPos = self.find_texts_first("发送消息")
            if (not inputPos):
                inputPos = self.find_texts_first("输入你的问题..")
            if (inputPos):
                self.log_message("找到输入框", "info")
                # 是没发过消息的才发 不然不发送
                if (self.get_color(618, 1539) == "EFEFEF"):
                    self.click_point(inputPos[0], inputPos[1])
                    time.sleep(1)
                    self.input_chinese(messagevalue)
                    time.sleep(1)
                    if (not self.findImgAndClick("./抖音榜单/send2.png", 0 , 0, True)):
                        self.findImgAndClick("./抖音榜单/send1.png", 0 , 0, True)
                    if (messagevalue2):
                        self.click_point(inputPos[0], inputPos[1])
                        time.sleep(1)
                        self.input_chinese(messagevalue2)
                        time.sleep(1)
                        if (not self.findImgAndClick("./抖音榜单/send2.png", 0 , 0, True)):
                            self.findImgAndClick("./抖音榜单/send1.png", 0 , 0, True)
                    if (messagevalue3):
                        self.click_point(inputPos[0], inputPos[1])
                        time.sleep(1)
                        self.input_chinese(messagevalue3)
                        time.sleep(1)
                        if (not self.findImgAndClick("./抖音榜单/send2.png", 0 , 0, True)):
                            self.findImgAndClick("./抖音榜单/send1.png", 0 , 0, True)

                else:
                    self.log_message("已经发过了!", "info")
                    self.click_point(inputPos[0], inputPos[1])
                    time.sleep(1)
                    self.input_chinese("好的，马上联系你")
                    time.sleep(1)
                    if (not self.findImgAndClick("./抖音榜单/send2.png", 0 , 0, True)):
                        self.findImgAndClick("./抖音榜单/send1.png", 0 , 0, True)
                return True
                
            else:
                self.log_message("无法找到输入框", "error")
                return False
    def 回关发私信下拉(self):
        inputPos = self.find_texts_first("回关")
        if (inputPos):
            self.click_point(inputPos[0], inputPos[1])
            time.sleep(2)
            # 发私信
            self.click_point(inputPos[0], inputPos[1])
            time.sleep(2)
            # 获取发送内容
            if self.sendDouyinMessage():
                self.press_back()
                time.sleep(2)
            self.press_back()
            time.sleep(3)
            # 判断是否在发私信页面
            ygzPos = self.find_texts_first("获赞")
            if ygzPos:
                self.press_back()
                time.sleep(2)
        self.swipe(530, 1786, 530, 1392, 1200)

    def 自动回复通知(self):
        # 先判断有没有回复
        
        # if (self.get_color(519, 2316) == "F3F3F2"):
        #     self.log_message("回复消息", "info")
        #     time.sleep(2)
        if (self.findImgAndClick("./抖音榜单/dot.png", 100 , 0, False, 0.95)):
            time.sleep(4)
            def sendMessage():
                time.sleep(4)
                if (self.findImgAndClick("./抖音榜单/sendPannel.png", 0 , 0, False)):
                    time.sleep(3)
                    if self.sendDouyinMessage():
                        self.press_back()
                        time.sleep(2)
                    else:
                        self.log_message("没有成功发送", "error")
                    self.press_back()
                    time.sleep(2)
                    self.press_back()
                    time.sleep(2)
                    return True
                else:
                    return False
            if not sendMessage():
                if (self.get_color(904, 1001) == "FE2E57"):
                    self.log_message("组合消息", "info")
                    self.click_point(141, 1013)
                    sendMessage()
                    time.sleep(2)
                    self.press_back()
                elif (self.find_texts_first("主页访客")):
                    self.log_message("主页访客", "info")
                    self.click_point(145, 449)
                    sendMessage()
        else:
            self.swipe(530, 1451, 530, 1984, 1200)
            time.sleep(4)
        # if (self.findImgAndClick("./抖音榜单/dot.png", 0 , 0, False, 0.95)):
        #     self.log_message("有新未读消息", "info")
        #     time.sleep(4)
        #     # 先判断有没有回复
        #     hfxxPos = self.find_texts_first("回复")
        #     if (hfxxPos):
        #         self.click_point(hfxxPos[0], hfxxPos[1])
        #         time.sleep(2)
        #     else:
        #         self.click_point(541, 1001)
        #         time.sleep(2)
        #         if (self.findImgAndClick("./抖音榜单/sendPannel.png", 0 , 0, True)):
        #             time.sleep(2)
        #             messagevalue = self.settings_mgr.get_value("消息内容", "")
        #             if self.sendDouyinMessage(messagevalue):
        #                 self.press_back()
        #                 time.sleep(1)
        #             self.press_back()
        #             time.sleep(1)
        #             # 返回到关注列表
        #             self.press_back()
        #             time.sleep(2)
        #             # 返回视频
        #             self.press_back()
        #             time.sleep(2)
        #             # 返回通知列表
        #             hdxxPos = self.find_texts_first("互动消息")
        #             if (not hdxxPos):
        #                 self.press_back()
        #                 time.sleep(2)
        # self.swipe(530, 1451, 530, 1984, 1200)
        # time.sleep(2)

    def 自动回复未读(self):
        self.click_point(644, 617)
        time.sleep(2)
        if self.sendDouyinMessage():
            self.press_back()
        time.sleep(2)
        self.swipe(530, 1451, 530, 1984, 1200)

    def 回关并发私信(self):
        inputPos = self.find_texts_first("回关")
        if (inputPos):
            self.click_point(inputPos[0], inputPos[1])
            time.sleep(2)
            # 发私信
            self.click_point(inputPos[0], inputPos[1])
            time.sleep(2)
            # 获取发送内容
            if self.sendDouyinMessage():
                self.press_back()
                time.sleep(2)
            self.press_back()
            time.sleep(3)
            # 判断是否在发私信页面
            ygzPos = self.find_texts_first("获赞")
            if ygzPos:
                self.press_back()
                time.sleep(2)
        self.swipe(530, 1451, 530, 1984, 1200)

    def 测试提取文字(self):
        items = self.app.get_screen_texts()
        if not items:
            return None
        for row in items:
            text, cx, cy = row[0], row[1], row[2]
            self.log_message(f"找到文字 '{text[:20]}' → 坐标 ({cx}, {cy})", "info")
        return None