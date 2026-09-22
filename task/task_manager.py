import threading
import time


class TaskManager:
    """任务管理器 - 管理任务队列和执行"""

    def __init__(self, app):
        self.app = app
        self.task_queue = []
        self.is_running = False
        self.stop_event = threading.Event()
        self.thread = None
        self.current_task_index = -1
        self.current_task_remaining = 0
        self.loop_count = 0
        self.max_loops = -1

    def set_max_loops(self, max_loops):
        self.max_loops = max_loops

    def add_task(self, task_name, times=1, interval=1.0):
        self.task_queue.append([task_name, times, interval])

    def remove_task(self, index):
        if 0 <= index < len(self.task_queue):
            del self.task_queue[index]
            return True
        return False

    def clear_tasks(self):
        self.task_queue.clear()

    def set_task_queue(self, task_queue):
        self.task_queue = task_queue.copy()

    def insert_task(self, index, task_name, times=1, interval=1.0):
        self.task_queue.insert(index, [task_name, times, interval])

    def get_task_count(self):
        return len(self.task_queue)

    def start(self):
        if self.is_running:
            return False

        if not self.task_queue:
            self.app.log_message("任务队列为空，无法启动", "warning")
            return False

        if not self.app.get_selected_device():
            self.app.log_message("请先选择设备", "warning")
            return False

        self.is_running = True
        self.stop_event.clear()
        self.current_task_index = -1
        self.current_task_remaining = 0

        self.thread = threading.Thread(target=self._task_loop, daemon=True)
        self.thread.start()
        return True

    def stop(self):
        if not self.is_running:
            return
        self.is_running = False
        self.app.log_message("正在停止任务...", "info")
        self.stop_event.set()

    def _task_loop(self):
        total_tasks = len(self.task_queue)
        if total_tasks == 0:
            self.app.root.after(0, self._on_finished)
            return

        self.loop_count = 0

        while not self.stop_event.is_set():
            if self.max_loops != -1 and self.loop_count >= self.max_loops:
                self.app.log_message(f"✅ 已达到最大循环次数 ({self.max_loops})，停止执行", "info")
                break

            self.loop_count += 1
            if self.max_loops != -1:
                self.app.log_message(f"🔄 开始第 {self.loop_count}/{self.max_loops} 轮执行", "info")
            else:
                self.app.log_message(f"🔄 开始第 {self.loop_count} 轮执行 (无限循环)", "info")

            for task_index in range(total_tasks):
                if self.stop_event.is_set():
                    break

                task_info = self.task_queue[task_index]
                task_name = task_info[0]
                times = task_info[1]
                interval = task_info[2] if len(task_info) > 2 else 1.0

                self.current_task_index = task_index
                self.current_task_remaining = times

                loop_info = f" (第{self.loop_count}轮)" if self.max_loops != -1 else " (循环)"
                self.app.root.after(0, lambda: self.app.update_task_status(
                    f"执行中: {task_name}{loop_info} [{task_index+1}/{total_tasks}]",
                    "orange"
                ))
                self.app.log_message(f"执行任务 [{task_index+1}/{total_tasks}]: {task_name} (共{times}次)", "info")

                for i in range(times):
                    if self.stop_event.is_set():
                        break

                    self.current_task_remaining = times - i - 1
                    self.app.root.after(0, lambda n=task_name, c=i+1, t=times, loop=self.loop_count:
                        self.app.update_task_status(
                            f"循环第{loop}轮: {n} [{c}/{t}]",
                            "orange"
                        ))

                    try:
                        if hasattr(self.app, task_name):
                            func = getattr(self.app, task_name)
                            func()
                            self.app.log_message(f"✓ {task_name} 第 {i+1}/{times} 次执行完成", "info")
                        else:
                            self.app.log_message(f"❌ 任务函数 {task_name} 不存在", "error")
                            break
                    except Exception as e:
                        self.app.log_message(f"❌ 任务 {task_name} 执行失败: {e}", "error")

                    if i < times - 1 and not self.stop_event.is_set():
                        time.sleep(interval)

                if not self.stop_event.is_set():
                    time.sleep(0.5)

            if not self.stop_event.is_set():
                if self.max_loops == -1 or self.loop_count < self.max_loops:
                    self.app.log_message("🔄 本轮任务完成，继续下一轮...", "info")
                    time.sleep(1)

        self.app.root.after(0, self._on_finished)

    def _on_finished(self):
        self.is_running = False
        if self.stop_event.is_set():
            self.app.update_task_status("已停止", "blue")
            self.app.log_message("任务已停止", "info")
        else:
            self.app.update_task_status("已完成", "green")
            self.app.log_message("所有任务执行完成", "info")
        self.app.on_task_finished()

    def get_current_status(self):
        if not self.is_running:
            return "空闲", 0, 0
        return "运行中", self.current_task_index, self.current_task_remaining