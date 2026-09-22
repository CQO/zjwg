import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import subprocess
import threading
import time
import io
from PIL import Image, ImageTk


class PhoneControlWindow:
    """控制手机弹窗 - 实时画面 / 截图 / 坐标计算 / 模拟点击"""

    def __init__(self, app):
        self.app = app
        self.device = app.selected_device.get()

        self.window = tk.Toplevel(app.root)
        self.window.title(f"控制手机 - {self.device}")
        self.window.geometry("980x720")
        self.window.minsize(700, 500)
        self.window.protocol("WM_DELETE_WINDOW", self.on_close)

        self.current_image = None
        self.last_frame = None
        self.original_size = (0, 0)
        self.display_size = (0, 0)
        self.image_position = (0, 0)

        self.live_running = False
        self.stop_event = threading.Event()
        self.live_interval = 2
        self._capture_lock = threading.Lock()

        self.click_enabled = tk.BooleanVar(value=False)

        self.build_ui()
        self.start_live()

    # ---------------- UI ----------------
    def build_ui(self):
        control_frame = ttk.Frame(self.window, padding=8)
        control_frame.pack(fill=tk.X)

        self.start_btn = ttk.Button(control_frame, text="▶ 开始实时",
                                    command=self.start_live, width=12)
        self.start_btn.pack(side=tk.LEFT, padx=3)
        self.pause_btn = ttk.Button(control_frame, text="⏸ 暂停实时",
                                    command=self.pause_live, width=12, state=tk.DISABLED)
        self.pause_btn.pack(side=tk.LEFT, padx=3)
        ttk.Button(control_frame, text="📷 截图",
                   command=self.save_screenshot, width=10).pack(side=tk.LEFT, padx=3)

        self.click_check = tk.Checkbutton(control_frame, text="⚡ 开启屏幕点击",
                                          variable=self.click_enabled,
                                          command=self.on_click_toggle,
                                          font=('Arial', 10, 'bold'))
        self.click_check.pack(side=tk.LEFT, padx=15)

        ttk.Label(control_frame, text="刷新间隔(秒):").pack(side=tk.LEFT, padx=(10, 2))
        self.interval_entry = ttk.Entry(control_frame, width=6)
        self.interval_entry.insert(0, str(self.live_interval))
        self.interval_entry.pack(side=tk.LEFT)

        self.status_label = ttk.Label(control_frame, text="就绪", foreground="green")
        self.status_label.pack(side=tk.LEFT, padx=10)

        main_frame = ttk.Frame(self.window)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        left_frame = ttk.LabelFrame(main_frame, text="手机屏幕（点击计算坐标）", padding=5)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(left_frame, bg='black', cursor='cross')
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<Button-1>", self.on_canvas_click)
        self.canvas.bind("<Configure>", lambda e: self.redraw_last_frame())

        right_frame = ttk.LabelFrame(main_frame, text="坐标信息", padding=10, width=240)
        right_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(8, 0))
        right_frame.pack_propagate(False)

        ttk.Label(right_frame, text="相对坐标(画面):").pack(anchor=tk.W)
        self.relative_label = ttk.Label(right_frame, text="X: ---, Y: ---", font=("Arial", 10))
        self.relative_label.pack(anchor=tk.W, pady=3)

        ttk.Label(right_frame, text="真实坐标(手机):").pack(anchor=tk.W, pady=(10, 0))
        self.real_label = ttk.Label(right_frame, text="X: ---, Y: ---",
                                    font=("Arial", 12, "bold"), foreground="blue")
        self.real_label.pack(anchor=tk.W, pady=3)

        self.click_state_label = ttk.Label(right_frame, text="屏幕点击: 已关闭", foreground="red")
        self.click_state_label.pack(anchor=tk.W, pady=(15, 0))

        ttk.Label(right_frame, text="提示：真实坐标已自动复制到剪贴板；开启「屏幕点击」后点击图片将模拟真实点击",
                  wraplength=210, foreground="gray").pack(anchor=tk.W, pady=15)

    # ---------------- 实时画面 ----------------
    def start_live(self):
        if self.live_running:
            return
        try:
            val = float(self.interval_entry.get())
            if val >= 0.1:
                self.live_interval = val
        except (ValueError, tk.TclError):
            pass
        self.live_running = True
        self.stop_event.clear()
        self.start_btn.config(state=tk.DISABLED)
        self.pause_btn.config(state=tk.NORMAL)
        self.status_label.config(text="实时获取中...", foreground="orange")
        threading.Thread(target=self._live_loop, daemon=True).start()

    def pause_live(self):
        self.live_running = False
        self.stop_event.set()
        try:
            self.start_btn.config(state=tk.NORMAL)
            self.pause_btn.config(state=tk.DISABLED)
            self.status_label.config(text="已暂停", foreground="blue")
        except tk.TclError:
            pass

    def _live_loop(self):
        while not self.stop_event.is_set():
            frame = self._capture_frame()
            if frame is not None:
                self.last_frame = frame
                try:
                    self.window.after(0, self._update_frame_display)
                except tk.TclError:
                    return
            self.stop_event.wait(self.live_interval)

    def _capture_frame(self):
        """抓取一帧屏幕，返回 PIL Image 或 None"""
        with self._capture_lock:
            try:
                return self.app.adb.screencap_image(self.device, timeout=5)
            except Exception as e:
                try:
                    self.window.after(0, lambda: self.app.log_message(f"实时画面获取失败: {e}", "error"))
                except tk.TclError:
                    pass
                return None

    def _update_frame_display(self):
        if self.last_frame is None:
            return
        self.original_size = self.last_frame.size
        self._show_image(self.last_frame)
        self.status_label.config(
            text=f"实时获取中 {self.original_size[0]}x{self.original_size[1]}  间隔{self.live_interval}s",
            foreground="orange")

    def redraw_last_frame(self):
        if self.last_frame is not None:
            self._show_image(self.last_frame)

    def _show_image(self, img):
        canvas_width = max(self.canvas.winfo_width(), 2)
        canvas_height = max(self.canvas.winfo_height(), 2)

        scale = min(canvas_width / img.size[0], canvas_height / img.size[1])
        new_width = max(int(img.size[0] * scale), 1)
        new_height = max(int(img.size[1] * scale), 1)
        self.display_size = (new_width, new_height)

        resized = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        self.current_image = ImageTk.PhotoImage(resized)

        self.canvas.delete("all")
        x = (canvas_width - new_width) // 2
        y = (canvas_height - new_height) // 2
        self.image_position = (x, y)
        self.canvas.create_image(x, y, anchor=tk.NW, image=self.current_image)

    # ---------------- 截图 ----------------
    def save_screenshot(self):
        def work():
            frame = self._capture_frame()
            if frame is None:
                self.window.after(0, lambda: messagebox.showerror("错误", "截图失败，请检查设备连接"))
                return
            self.last_frame = frame
            self.window.after(0, self._update_frame_display)

            file_path = filedialog.asksaveasfilename(
                parent=self.window,
                title="保存截图",
                defaultextension=".png",
                initialfile=f"screenshot_{time.strftime('%Y%m%d_%H%M%S')}.png",
                filetypes=[("PNG图片", "*.png"), ("所有文件", "*.*")])
            if file_path:
                try:
                    frame.save(file_path)
                    self.app.log_message(f"截图已保存: {file_path}", "info")
                except Exception as e:
                    self.window.after(0, lambda: messagebox.showerror("错误", f"保存失败: {e}"))
        threading.Thread(target=work, daemon=True).start()

    # ---------------- 点击 ----------------
    def on_click_toggle(self):
        if self.click_enabled.get():
            self.click_state_label.config(text="屏幕点击: 已开启 ⚡", foreground="green")
            self.canvas.config(cursor="target")
        else:
            self.click_state_label.config(text="屏幕点击: 已关闭", foreground="red")
            self.canvas.config(cursor="cross")

    def on_canvas_click(self, event):
        if self.last_frame is None:
            return
        img_x, img_y = self.image_position
        img_w, img_h = self.display_size
        click_x = event.x - img_x
        click_y = event.y - img_y
        if not (0 <= click_x <= img_w and 0 <= click_y <= img_h):
            return

        real_x = int(click_x * (self.original_size[0] / img_w))
        real_y = int(click_y * (self.original_size[1] / img_h))

        self.relative_label.config(text=f"X: {click_x}, Y: {click_y}")
        self.real_label.config(text=f"X: {real_x}, Y: {real_y}")

        self.window.clipboard_clear()
        self.window.clipboard_append(f"{real_x},{real_y}")

        self.canvas.delete("click_marker")
        r = 6
        self.canvas.create_oval(event.x - r, event.y - r, event.x + r, event.y + r,
                                outline="red", width=2, tags="click_marker")

        if self.click_enabled.get():
            self.app.click_point(real_x, real_y, self.device)
            self.status_label.config(text=f"已模拟点击: ({real_x}, {real_y})", foreground="green")

    def on_close(self):
        self.pause_live()
        try:
            self.window.destroy()
        except tk.TclError:
            pass
        self.app._phone_control_window = None