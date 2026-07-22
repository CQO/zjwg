# functions.py - 外部功能函数文件
# 这个文件可以放在程序同目录下，修改后无需重新打包

import time
from PIL import Image

# 功能配置 - 定义每个功能的显示名称、颜色和描述
FUNCTION_CONFIGS = {
    "城墙": {
        "color": "#4CAF50",
        "desc": "执行城墙任务"
    },
    "战令活动": {
        "color": "#FF9800",
        "desc": "执行战令活动任务"
    },
    "挂机奖励": {
        "color": "#2196F3",
        "desc": "执行挂机奖励任务"
    },
    "征兵任务": {
        "color": "#4CAF50",
        "desc": "执行征兵任务"
    },
    "采集金矿": {
        "color": "#FF9800",
        "desc": "执行采集金矿任务"
    },
    "采集农田": {
        "color": "#FF9800",
        "desc": "执行采集农田任务"
    },
    "采集伐木场": {
        "color": "#FF9800",
        "desc": "执行采集伐木场任务"
    },
    "采集水晶矿": {
        "color": "#FF9800",
        "desc": "执行采集水晶矿任务"
    },
    "集结泰坦": {
        "color": "#FF9800",
        "desc": "执行集结泰坦任务"
    },
    "集结哈罗德": {
        "color": "#FF9800",
        "desc": "执行集结哈罗德任务"
    },
    "搜索任务": {
        "color": "#4CAF50",
        "desc": "执行搜索任务"
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
    
    def find_image(self, image_path, device=None, threshold=None):
        """找图 - 调用主程序的找图方法"""
        return self.app.find_image(image_path, device, threshold)
    
    def click_point(self, x, y, device=None, delay=None):
        """点击 - 调用主程序的点击方法"""
        return self.app.click_point(x, y, device, delay)
    
    def long_press(self, x, y, duration, device=None):
        """长按 - 调用主程序的长按方法"""
        return self.app.long_press(x, y, duration, device)
    
    def input_number_with_backspace(self, target_number, delete_count=1, device=None):
        """输入数字 - 调用主程序的输入方法"""
        return self.app.input_number_with_backspace(target_number, delete_count, device)
    
    def log_message(self, msg, level="info"):
        """日志 - 调用主程序的日志方法"""
        self.app.log_message(msg, level)
    
    # ========== 以下是具体的功能函数 ==========
    
    def 城墙(self):
        """城墙任务"""
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
    
    def 战令活动(self):
        """战令活动任务"""
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
    
    def 挂机奖励(self):
        """挂机奖励任务"""
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
    
    def 征兵任务(self):
        """征兵任务"""
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
    
    def 采集金矿(self):
        self.采集(150)
    
    def 采集农田(self):
        self.采集(300)
    
    def 采集伐木场(self):
        self.采集(450)
    
    def 采集水晶矿(self):
        self.采集(600)
    
    def 采集(self, xPoint):
        """通用采集函数"""
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
    
    def 集结泰坦(self):
        """集结泰坦"""
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
    
    def 集结哈罗德(self):
        """集结哈罗德"""
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
    
    def 关闭弹窗(self):
        """关闭弹窗"""
        threshold = self.settings_mgr.get_value("image_threshold", 0.8)
        pos = self.find_image("close.png", threshold=threshold)
        if pos:
            self.log_message(f"关闭弹窗: {pos}", "info")
            self.click_point(pos[0], pos[1])
    
    def 设置出兵数量(self):
        """设置出兵数量"""
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
    
    def 搜索任务(self):
        """搜索任务"""
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