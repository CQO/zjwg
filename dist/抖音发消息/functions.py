# functions.py - 外部功能函数文件
# 这个文件可以放在程序同目录下，修改后无需重新打包

import os
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
    "发送关注私信": {
        "color": "#4CAF50",
        "desc": "执行发送关注私信任务"
    },
    "切换商圈": {
        "color": "#4CAF50",
        "desc": "测试切换商圈按钮"
    },
    "刷视频关注店铺": {
        "color": "#4CAF50",
        "desc": "刷视频关注店铺"
    },
    "回复未读消息": {
        "color": "#4CAF50",
        "desc": "刷视频关注店铺"
    },
    "测试获取文字": {
        "color": "#4CAF50",
        "desc": "测试获取文字"
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
        

    def 切换商圈(self):
        qyxz = self.settings_mgr.get_value("区域选择", "")
        qyxz2 = self.settings_mgr.get_value("区域选择2", "")
        qyxzButton = self.settings_mgr.get_value("区域切换按钮", "")
        qyxzList = qyxz.split('#')
        qyxzButtonList = qyxzButton.split('@')
        self.click_point(int(qyxzButtonList[0]), int(qyxzButtonList[1]))
        time.sleep(2)
        canClick = False
        for temp in qyxzList:
            print(temp)
            pointList = temp.split('@')
            qyxz2List = qyxz2.split('@')
            if self.get_color(int(pointList[0]), int(pointList[1])) != 'FFFFFF':
                if (canClick):
                    self.click_point(int(pointList[0]), int(pointList[1]))
                    time.sleep(1)
                    self.click_point(int(qyxz2List[0]), int(qyxz2List[1]))
                    break
            else:
                canClick = True

    def sendDouyinMessage(self, messagevalue):
        if (messagevalue != ""):
            self.log_message("尝试发送消息内容:" + messagevalue, "info")
            inputPos = self.find_texts_first("发送消息")
            if (not inputPos):
                inputPos = self.find_texts_first("发消息或按住说话...")
            if (not inputPos):
                inputPos = self.find_texts_first("输入你的问题..")
            if (inputPos):
                self.click_point(inputPos[0], inputPos[1])
                time.sleep(2)
                self.input_chinese(messagevalue)
                time.sleep(2)
                if (not self.findImgAndClick("./抖音榜单/send2.png", 0 , 0, True)):
                    self.findImgAndClick("./抖音榜单/send1.png", 0 , 0, True)
            else:
                self.log_message("无法找到输入框", "error")

    # def 发送关注私信(self):
    #     if self.findImgAndClick("./抖音榜单/ygzlb.png", -460 , 0, False):
    #         time.sleep(2)
    #         ygzPos = self.find_texts_first("已关注")
    #         if (self.findImgAndClick("./抖音榜单/ygz.png", 500 , 0, False)):
    #             time.sleep(2)
    #             # 获取发送内容
    #             messagevalue = self.settings_mgr.get_value("消息内容", "")
    #             self.sendDouyinMessage(messagevalue)
    #             self.press_back()
    #             time.sleep(2)
    #             self.press_back()
    #             time.sleep(3)
    #             # 判断是否在发私信页面
    #             ygzPos = self.find_image_first("./抖音榜单/ygz.png", threshold=0.9, use_cache=False)
    #             if ygzPos:
    #                 self.press_back()
    #                 time.sleep(2)
    #             else:
    #                 self.log_message("找不到发私信按钮!", "error")
                
    #             self.swipe(530, 1000, 530, 900, 800)
    #         else:
    #             self.press_back()
    #             self.log_message("无法找到发消息按钮", "error")
    #             time.sleep(2)
    #             self.swipe(530, 1000, 530, 900, 800)
    #     else:
    #         self.log_message("无法找到好友列表", "error")

    def 发送关注私信(self):
        morePos = self.find_texts_first("已关注")
        if morePos:
            self.click_point(morePos[0] - 460, morePos[1])
            time.sleep(2)
            ygzPos = self.find_texts_first("已关注")
            if (ygzPos):
                # 先看看是谁
                items = self.app.get_screen_texts()
                lastItem = ""
                for row in items:
                    text, cx, cy = row[0], row[1], row[2]
                    if '抖音号' in text:
                        self.log_message("发私信给:" + lastItem, "info")
                    lastItem = text
                self.click_point(ygzPos[0] + 500, ygzPos[1])
                time.sleep(2)
                # 获取发送内容
                messagevalue = self.settings_mgr.get_value("消息内容", "")
                self.sendDouyinMessage(messagevalue)
                self.press_back()
                time.sleep(2)
                self.press_back()
                time.sleep(3)
                # 判断是否在发私信页面
                ygzPos = self.find_texts_first("获赞")
                if ygzPos:
                    self.press_back()
                    time.sleep(2)
                
                self.swipe(530, 1000, 530, 900, 800)
            else:
                self.press_back()
                self.log_message("无法找到发消息按钮", "error")
                time.sleep(2)
                self.swipe(530, 1000, 530, 900, 800)
        else:
            self.log_message("无法找到好友列表", "error")

    def 寻找可关注(self):
        threshold = self.settings_mgr.get_value("image_threshold", 0.9)
        # 判断是否到底了
        nomore = self.find_image_first("./抖音榜单/zanwu.png", threshold=threshold, use_cache=False)
        if nomore:
            print(nomore)
            if (nomore[1]  <= int(self.settings_mgr.get_value("到底位置", 2000))):
                self.log_message("已经到底了", "info")
                return
        morePos = self.find_image_first("./抖音榜单/distance.png", threshold=0.90, use_cache=False)
        if morePos:
            self.click_point(morePos[0], morePos[1])
            time.sleep(2)
            findButton = self.findImgAndClick("./抖音榜单/focus.png", 0 , 0)
            if (not findButton):
                findButton = self.findImgAndClick("./抖音榜单/add.png", 0 , 0)
            if (findButton):
                time.sleep(3)
                # 关闭广告
                self.findImgAndClick("./抖音榜单/closebutton.png", 0 , 0)
            time.sleep(3)
            self.press_back()
            time.sleep(2)
            hdfd = self.settings_mgr.get_value("关注滑动幅度", 100)
            self.swipe(530, 800 + hdfd, 530, 800 - hdfd, 1200)
        else:
            
            self.log_message("找不到产品", "error")
            xpjPos = self.find_image("./抖音榜单/daohang.png", threshold=0.9, use_cache=False)
            # if (xpjPos):
            #     self.log_message("还在详情页面，返回上一页", "error")
            self.press_back()
            time.sleep(4)
    

    def 刷视频关注店铺(self):
        tuangouButonFind = self.findImgAndClick("./抖音榜单/tuangou.png", 100 , 20, False)
        if (tuangouButonFind):
            time.sleep(4)
            self.swipe(530, 1800, 530, 1400, 800)
            time.sleep(2)
            # 关闭广告
            self.findImgAndClick("./抖音榜单/closebutton.png", 0 , 0)
            time.sleep(2)
            # 找到关注按钮
            findButton = self.findImgAndClick("./抖音榜单/add.png", 0 , 0)
            if (findButton):
                time.sleep(3)
                # 关闭广告
                self.findImgAndClick("./抖音榜单/closebutton.png", 0 , 0)
                time.sleep(3)
            self.press_back()
            time.sleep(2)
            # 判断是否需要再次返回
            if (self.findImgAndClick("./抖音榜单/close2.png", 0 , 0)):
                time.sleep(2)
            self.swipe(530, 1800, 530, 1400, 1200)
            time.sleep(2)
    def 回复未读消息(self):
        threshold = self.settings_mgr.get_value("image_threshold", 0.95)
        pos = self.find_image_first("./抖音榜单/weidu.png", threshold=threshold, use_cache=False)
        if pos:
            print(pos)
            self.click_point(pos[0], pos[1])
            time.sleep(2)
            self.click_point(200, 735)
            messagevalue = self.settings_mgr.get_value("发送消息内容", "")
            self.sendDouyinMessage(messagevalue)
            time.sleep(2)
            self.press_back()
        else:
            self.log_message("没有未读消息", "info")

    def 测试获取文字(self):
        """
        查找包含 keyword 的文字，返回中心坐标 (cx, cy) 或 None
        二维数组结构：[text, cx, cy, left, top, width, height]
        """
        items = self.get_screen_texts()
        if not items:
            return None

        for row in items:
            text, cx, cy = row[0], row[1], row[2]
            self.log_message(f"找到文字 '{text[:20]}' → 坐标 ({cx}, {cy})", "info")
        return None
