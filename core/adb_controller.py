import os
import io
import time
import base64
import hashlib
import subprocess
import threading
import urllib.request

from PIL import Image


class AdbController:
    """
    ADB 控制器 - 封装所有与设备交互的底层操作
    不依赖 Tkinter，不依赖 GUI，可单独测试
    """

    # ADBKeyboard 相关
    ADBKEYBOARD_PACKAGE = "com.android.adbkeyboard"
    ADBKEYBOARD_IME = "com.android.adbkeyboard/.AdbIME"
    ADBKEYBOARD_APK = "ADBKeyboard.apk"
    ADBKEYBOARD_URL = "https://cunchu.site/app/ADBKeyboard.apk"

    KEYCODE_BACK = "4"
    KEYCODE_DEL = "67"  # 退格

    def __init__(self, adb_path, logger=None, settings_mgr=None):
        """
        Args:
            adb_path: adb 可执行文件路径
            logger: 日志回调，签名 func(msg, level="info")
            settings_mgr: 可选，用于读取 image_threshold / click_delay 等
        """
        self.adb_path = adb_path
        self.logger = logger or (lambda msg, level="info": None)
        self.settings_mgr = settings_mgr
        self.image_cache = {}  # {(image_path, device, threshold): (x, y)}

    # ---------------- 内部工具 ----------------
    def _log(self, msg, level="info"):
        try:
            self.logger(msg, level)
        except Exception:
            pass

    def _get_threshold(self, threshold):
        if threshold is not None:
            return threshold
        if self.settings_mgr:
            return self.settings_mgr.get_value("image_threshold", 0.8)
        return 0.8

    def _get_click_delay(self, delay):
        if delay is not None:
            return delay
        if self.settings_mgr:
            return self.settings_mgr.get_value("click_delay", 0.5)
        return 0.5

    # ---------------- 基础命令 ----------------
    def list_devices(self, timeout=10):
        """返回已连接设备的序列号列表"""
        try:
            result = subprocess.run(
                [self.adb_path, 'devices'],
                capture_output=True, text=True, timeout=timeout, creationflags=subprocess.CREATE_NO_WINDOW
            )
            devices = []
            for line in result.stdout.strip().split('\n')[1:]:
                line = line.strip()
                if not line:
                    continue
                parts = line.split()
                if len(parts) >= 2 and parts[1] == 'device':
                    devices.append(parts[0])
            return devices
        except Exception as e:
            self._log(f"获取设备列表失败: {e}", "error")
            return []

    def start_server(self, timeout=10):
        """启动 adb 服务"""
        try:
            subprocess.run([self.adb_path, 'start-server'],
                           capture_output=True, timeout=timeout, creationflags=subprocess.CREATE_NO_WINDOW)
            return True
        except Exception as e:
            self._log(f"启动 ADB 服务失败: {e}", "error")
            return False

    def screencap_bytes(self, device, timeout=5):
        """获取屏幕原始 PNG 字节流，失败返回 None"""
        try:
            cmd = [self.adb_path, '-s', device, 'exec-out', 'screencap', '-p']
            result = subprocess.run(cmd, capture_output=True, timeout=timeout, creationflags=subprocess.CREATE_NO_WINDOW)
            if result.returncode != 0 or not result.stdout:
                return None
            return result.stdout
        except Exception as e:
            self._log(f"截图失败: {e}", "error")
            return None

    def screencap_image(self, device, timeout=5):
        """返回 PIL Image（RGB），失败返回 None"""
        data = self.screencap_bytes(device, timeout=timeout)
        if not data:
            return None
        try:
            return Image.open(io.BytesIO(data)).convert("RGB")
        except Exception as e:
            self._log(f"解析截图失败: {e}", "error")
            return None

    # ---------------- 常用操作 ----------------
    def press_back(self, device, delay=0.5):
        """按下返回键"""
        try:
            cmd = [self.adb_path, '-s', device, 'shell', 'input', 'keyevent', self.KEYCODE_BACK]
            subprocess.run(cmd, capture_output=True, check=True, timeout=5, creationflags=subprocess.CREATE_NO_WINDOW)
            self._log("按下返回按钮", "info")
            time.sleep(delay)
            return True
        except Exception as e:
            self._log(f"返回操作失败: {e}", "error")
            return False

    def click_point(self, device, x, y, delay=None):
        """点击指定坐标"""
        delay = self._get_click_delay(delay)
        try:
            cmd = [self.adb_path, '-s', device, 'shell', 'input', 'tap', str(x), str(y)]
            subprocess.run(cmd, capture_output=True, check=True, timeout=5, creationflags=subprocess.CREATE_NO_WINDOW)
            self._log(f"点击坐标 ({x}, {y})", "info")
            time.sleep(delay)
            return True
        except Exception as e:
            self._log(f"点击失败 ({x},{y}): {e}", "error")
            return False

    def long_press(self, device, x, y, duration=1.0, tap_offset=0.08):
        """
        长按并在结束前触发点击（解决 Unity 等引擎长按后菜单不弹出）
        """
        try:
            x, y = int(x), int(y)
            duration = float(duration)
            tap_offset = float(tap_offset)
            if duration < 0.15:
                duration = 0.15
        except (ValueError, TypeError):
            self._log("长按参数错误", "error")
            return False

        def swipe_thread():
            cmd = [self.adb_path, '-s', device, 'shell', 'input', 'swipe',
                   str(x), str(y), str(x + 1), str(y + 1), str(int(duration * 1000))]
            subprocess.run(cmd, capture_output=True, timeout=duration + 5, creationflags=subprocess.CREATE_NO_WINDOW)

        def tap_thread():
            sleep_time = max(duration - tap_offset, 0.03)
            time.sleep(sleep_time)
            cmd = [self.adb_path, '-s', device, 'shell', 'input', 'tap', str(x), str(y)]
            subprocess.run(cmd, capture_output=True, timeout=5, creationflags=subprocess.CREATE_NO_WINDOW)

        t1 = threading.Thread(target=swipe_thread)
        t2 = threading.Thread(target=tap_thread)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        self._log(f"✅ 长按完成 ({x},{y}) {duration}s (提前{tap_offset}s点击)", "info")
        return True

    def swipe(self, device, x1, y1, x2, y2, duration=300):
        """滑动"""
        try:
            cmd = [self.adb_path, '-s', device, 'shell', 'input', 'swipe',
                   str(x1), str(y1), str(x2), str(y2), str(duration)]
            subprocess.run(cmd, capture_output=True, check=True, timeout=5, creationflags=subprocess.CREATE_NO_WINDOW)
            self._log(f"✅ 滑动: ({x1},{y1}) -> ({x2},{y2}) 持续 {duration}ms", "info")
            return True
        except Exception as e:
            self._log(f"滑动失败: {e}", "error")
            return False

    def input_text_ascii(self, device, text, char_delay=0.05):
        """逐字符输入（仅 ASCII，用于数字/英文）"""
        try:
            for ch in str(text):
                cmd = [self.adb_path, '-s', device, 'shell', 'input', 'text', ch]
                subprocess.run(cmd, capture_output=True, check=True, timeout=2, creationflags=subprocess.CREATE_NO_WINDOW)
                time.sleep(char_delay)
            return True
        except Exception as e:
            self._log(f"输入失败: {e}", "error")
            return False

    def input_number_with_backspace(self, device, target_number, delete_count=1):
        """先退格 delete_count 次，再输入数字"""
        try:
            for _ in range(delete_count):
                cmd = [self.adb_path, '-s', device, 'shell', 'input', 'keyevent', self.KEYCODE_DEL]
                subprocess.run(cmd, capture_output=True, check=True, timeout=2, creationflags=subprocess.CREATE_NO_WINDOW)
                time.sleep(0.15)

            time.sleep(0.3)

            number_str = str(target_number)
            for ch in number_str:
                cmd = [self.adb_path, '-s', device, 'shell', 'input', 'text', ch]
                subprocess.run(cmd, capture_output=True, check=True, timeout=2, creationflags=subprocess.CREATE_NO_WINDOW)
                time.sleep(0.05)

            self._log(f"重新输入: {number_str} (已删除{delete_count}个字符)", "info")
            return True
        except Exception as e:
            self._log(f"输入数字失败: {e}", "error")
            return False

    # ---------------- 找图 ----------------
    def find_image(self, device, image_path, threshold=None, use_cache=False):
        """找图，返回置信度最高的 (x, y)，未找到返回 None"""
        threshold = self._get_threshold(threshold)
        cache_key = (image_path, device, threshold)
        if use_cache and cache_key in self.image_cache:
            return self.image_cache[cache_key]

        screen_img = self.screencap_image(device)
        if screen_img is None:
            return None

        try:
            template_img = Image.open(image_path)
        except Exception as e:
            self._log(f"打开模板图片失败: {e}", "error")
            return None

        try:
            import cv2
            import numpy as np
        except ImportError:
            self._log("未安装 opencv-python，无法使用找图功能", "error")
            return None

        try:
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
                self._log(f"找到图片坐标 X:{x} Y:{y}", "info")
                return (x, y)
            return None
        except Exception as e:
            self._log(f"找图失败: {e}", "error")
            return None

    def find_image_first(self, device, image_path, threshold=None, use_cache=False):
        """找图，返回从上到下、从左到右第一个匹配点 (x, y)，未找到返回 None"""
        threshold = self._get_threshold(threshold)
        cache_key = (image_path, device, threshold, "first")
        if use_cache and cache_key in self.image_cache:
            return self.image_cache[cache_key]

        screen_img = self.screencap_image(device)
        if screen_img is None:
            return None

        try:
            template_img = Image.open(image_path)
        except Exception as e:
            self._log(f"打开模板图片失败: {e}", "error")
            return None

        try:
            import cv2
            import numpy as np
        except ImportError:
            self._log("未安装 opencv-python，无法使用找图功能", "error")
            return None

        try:
            screen_np = np.array(screen_img)
            template_np = np.array(template_img)

            screen_gray = cv2.cvtColor(screen_np, cv2.COLOR_RGB2GRAY)
            template_gray = cv2.cvtColor(template_np, cv2.COLOR_RGB2GRAY)

            result = cv2.matchTemplate(screen_gray, template_gray, cv2.TM_CCOEFF_NORMED)
            h, w = template_gray.shape

            locations = np.where(result >= threshold)
            if len(locations[0]) == 0:
                return None

            matches = []
            for pt in zip(*locations[::-1]):  # np.where 返回 (y, x)
                x = pt[0] + w // 2
                y = pt[1] + h // 2
                matches.append((x, y))

            # 按 y 再按 x 排序 → 最左上
            matches.sort(key=lambda m: (m[1], m[0]))
            x, y = matches[0]

            if use_cache:
                self.image_cache[cache_key] = (x, y)

            self._log(f"找到第一个图片坐标 X:{x} Y:{y} (共{len(matches)}个匹配)", "info")
            return (x, y)
        except Exception as e:
            self._log(f"找图失败: {e}", "error")
            return None

    # ---------------- 取色 ----------------
    def get_color(self, device, x, y):
        """获取指定点颜色，返回 'RRGGBB' 或 None"""
        try:
            temp_file = "/sdcard/temp_screencap.png"
            cmd = [self.adb_path, '-s', device, 'shell', 'screencap', temp_file]
            subprocess.run(cmd, capture_output=True, check=True, timeout=5, creationflags=subprocess.CREATE_NO_WINDOW)

            local_temp = "temp_screencap.png"
            pull_cmd = [self.adb_path, '-s', device, 'pull', temp_file, local_temp]
            subprocess.run(pull_cmd, capture_output=True, check=True, timeout=5, creationflags=subprocess.CREATE_NO_WINDOW)

            img = Image.open(local_temp)
            pixel = img.getpixel((x, y))
            color_hex = f"{pixel[0]:02X}{pixel[1]:02X}{pixel[2]:02X}"

            try:
                os.remove(local_temp)
            except OSError:
                pass
            subprocess.run([self.adb_path, '-s', device, 'shell', 'rm', temp_file],
                           capture_output=True, timeout=3, creationflags=subprocess.CREATE_NO_WINDOW)
            return color_hex
        except Exception as e:
            self._log(f"取色失败 ({x},{y}): {e}", "error")
            return None

    # ---------------- ADBKeyboard ----------------
    def is_adbkeyboard_installed(self, device):
        try:
            cmd = [self.adb_path, '-s', device, 'shell', 'pm', 'list', 'packages',
                   self.ADBKEYBOARD_PACKAGE]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=3, creationflags=subprocess.CREATE_NO_WINDOW)
            return self.ADBKEYBOARD_PACKAGE in result.stdout
        except Exception as e:
            self._log(f"检查ADBKeyboard失败: {e}", "error")
            return False

    def _try_switch_adbkeyboard(self, device):
        """
        尝试切换输入法
        返回 (是否安装, 是否切换成功, 错误信息)
        """
        if not self.is_adbkeyboard_installed(device):
            return False, False, "ADBKeyboard 未安装"

        switch_success = False
        error_msg = ""

        # 方法1: ime set
        try:
            cmd = [self.adb_path, '-s', device, 'shell', 'ime', 'set', self.ADBKEYBOARD_IME]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5, creationflags=subprocess.CREATE_NO_WINDOW)
            if result.returncode == 0:
                switch_success = True
            else:
                error_msg = (result.stderr or "").strip()
        except Exception as e:
            error_msg = str(e)

        # 方法2: enable + settings put
        if not switch_success:
            try:
                subprocess.run(
                    [self.adb_path, '-s', device, 'shell', 'ime', 'enable', self.ADBKEYBOARD_IME],
                    capture_output=True, timeout=3, creationflags=subprocess.CREATE_NO_WINDOW
                )
                time.sleep(0.2)
                result = subprocess.run(
                    [self.adb_path, '-s', device, 'shell', 'settings', 'put', 'secure',
                     'default_input_method', self.ADBKEYBOARD_IME],
                    capture_output=True, text=True, timeout=3, creationflags=subprocess.CREATE_NO_WINDOW
                )
                if result.returncode == 0:
                    switch_success = True
            except Exception:
                pass

        return True, switch_success, error_msg

    def input_text(self, device, text):
        """
        输入文本（支持中文）—— 使用 ADBKeyboard + Base64
        返回 (success: bool, error_msg: str)
        """
        if not self.is_adbkeyboard_installed(device):
            self._log("❌ ADBKeyboard未安装，无法输入", "error")
            return False, "ADBKeyboard 未安装"

        # 尝试切换（失败也继续尝试输入）
        self._log("🔄 尝试确保 ADBKeyboard 为当前输入法...", "info")
        self._try_switch_adbkeyboard(device)

        try:
            b64_text = base64.b64encode(text.encode('utf-8')).decode('utf-8')
            cmd = [self.adb_path, '-s', device, 'shell', 'am', 'broadcast',
                   '-a', 'ADB_INPUT_B64', '--es', 'msg', b64_text]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5, creationflags=subprocess.CREATE_NO_WINDOW)

            if result.returncode == 0:
                preview = text[:30] + ("..." if len(text) > 30 else "")
                self._log(f"✅ 输入成功: {preview}", "info")
                return True, ""
            else:
                err = (result.stderr or "未知错误").strip()
                self._log(f"❌ 输入失败: {err}", "error")
                return False, err
        except Exception as e:
            self._log(f"❌ 输入失败: {e}", "error")
            return False, str(e)

    def install_adbkeyboard(self, device, apk_path=None, download_url=None, timeout=30):
        """
        安装 ADBKeyboard
        返回 (success: bool, message: str)
        """
        apk_filename = apk_path or self.ADBKEYBOARD_APK
        download_url = download_url or self.ADBKEYBOARD_URL

        # 1. 本地是否存在
        if not os.path.exists(apk_filename):
            self._log(f"📥 开始下载 {apk_filename} 从 {download_url}", "info")
            try:
                urllib.request.urlretrieve(download_url, apk_filename)
                self._log(f"✅ 下载完成: {apk_filename}", "info")
            except Exception as e:
                self._log(f"❌ 下载失败: {e}", "error")
                return False, f"下载失败: {e}"
        else:
            self._log(f"✅ 找到本地APK: {apk_filename}", "info")

        # 2. 文件大小检查
        try:
            file_size = os.path.getsize(apk_filename)
        except OSError as e:
            return False, f"无法读取APK: {e}"

        if file_size < 1000:
            self._log(f"⚠️ APK文件大小异常 ({file_size} bytes)，删除并重新下载", "warning")
            try:
                os.remove(apk_filename)
                urllib.request.urlretrieve(download_url, apk_filename)
                self._log("✅ 重新下载完成", "info")
            except Exception as e:
                return False, f"重新下载失败: {e}"

        # 3. 安装
        self._log(f"📲 正在安装 ADBKeyboard 到设备 {device}...", "info")
        try:
            cmd = [self.adb_path, '-s', device, 'install', '-r', apk_filename]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, creationflags=subprocess.CREATE_NO_WINDOW)

            if result.returncode == 0:
                self._log("✅ ADBKeyboard 安装成功！", "info")
                return True, "安装成功"

            error_msg = (result.stderr or result.stdout or "未知错误").strip()
            self._log(f"❌ 安装失败: {error_msg}", "error")
            return False, error_msg
        except Exception as e:
            self._log(f"❌ 安装过程出错: {e}", "error")
            return False, str(e)

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
                subprocess.run(cmd, stdout=f, check=True, timeout=15, creationflags=subprocess.CREATE_NO_WINDOW)
            
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
            
    # ---------------- UI 层文字提取 ----------------
    def dump_ui_xml(self, device, timeout=10, remote_path="/sdcard/window_dump.xml"):
        """
        执行 uiautomator dump 并返回 XML 字符串
        失败返回 None
        """
        try:
            # dump 到设备
            cmd = [self.adb_path, '-s', device, 'shell', 'uiautomator', 'dump', remote_path]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, creationflags=subprocess.CREATE_NO_WINDOW)
            if result.returncode != 0:
                self._log(f"uiautomator dump 失败: {result.stderr.strip()}", "error")
                return None

            # 直接 exec-out cat 回来（避免 pull 落盘）
            cmd = [self.adb_path, '-s', device, 'exec-out', 'cat', remote_path]
            result = subprocess.run(cmd, capture_output=True, timeout=timeout, creationflags=subprocess.CREATE_NO_WINDOW)
            if result.returncode != 0 or not result.stdout:
                self._log("读取 XML 失败", "error")
                return None

            # 清理设备端临时文件（失败无所谓）
            try:
                subprocess.run(
                    [self.adb_path, '-s', device, 'shell', 'rm', '-f', remote_path],
                    capture_output=True, timeout=3, creationflags=subprocess.CREATE_NO_WINDOW
                )
            except Exception:
                pass

            return result.stdout.decode('utf-8', errors='replace')

        except subprocess.TimeoutExpired:
            self._log("uiautomator dump 超时（界面可能在动）", "error")
            return None
        except Exception as e:
            self._log(f"uiautomator dump 异常: {e}", "error")
            return None

    def get_screen_texts(self, device, include_desc=True):
        """
        获取当前屏幕上的所有文字及其几何信息

        Args:
            device: 设备序列号
            include_desc: 是否把 content-desc 也当作文字一起收集（抖音/快手必须开）

        Returns:
            list[list] 二维数组，每项：
            [
                文字内容,   # str
                中心x,      # int
                中心y,      # int
                left,       # int  x1
                top,        # int  y1
                width,      # int  x2 - x1
                height,     # int  y2 - y1
            ]
            dump 失败返回 None
        """
        xml_str = self.dump_ui_xml(device)
        if not xml_str:
            return None

        try:
            import xml.etree.ElementTree as ET
            root = ET.fromstring(xml_str)
        except Exception as e:
            self._log(f"解析 XML 失败: {e}", "error")
            return None

        import re
        bounds_re = re.compile(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]')

        results = []
        for node in root.iter('node'):
            text = (node.get('text') or '').strip()
            desc = (node.get('content-desc') or '').strip()

            if text:
                display_text = text
            elif include_desc and desc:
                display_text = desc
            else:
                continue

            bounds_str = node.get('bounds') or ''
            m = bounds_re.match(bounds_str)
            if not m:
                continue

            x1, y1, x2, y2 = map(int, m.groups())
            width = x2 - x1
            height = y2 - y1
            cx = (x1 + x2) // 2
            cy = (y1 + y2) // 2

            results.append([display_text, cx, cy, x1, y1, width, height])

        self._log(f"屏幕文字提取完成，共 {len(results)} 条", "info")
        return results