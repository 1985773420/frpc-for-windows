import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import subprocess
import os
import sys
import winreg
from pathlib import Path
import time
import logging
import hashlib
import watchdog.observers
import watchdog.events


def get_app_path():
    """获取应用程序真实路径（兼容开发环境和打包环境）"""
    if getattr(sys, 'frozen', False):  # 打包环境
        return Path(sys.executable).parent
    else:  # 开发环境
        return Path(__file__).parent


def resource_path(relative_path):
    """获取资源的绝对路径（兼容EXE和源码环境）"""
    base_dir = get_app_path()
    return str(base_dir / relative_path)


class ConfigHandler(watchdog.events.FileSystemEventHandler):
    """配置文件变更处理器（带内容哈希校验）"""

    def __init__(self, callback):
        self.callback = callback
        self.last_hash = self.get_file_hash()

    def get_file_hash(self):
        """计算配置文件哈希值"""
        config_path = resource_path("frpc.toml")
        try:
            if os.path.exists(config_path):
                with open(config_path, "rb") as f:
                    return hashlib.md5(f.read()).hexdigest()
            return ""
        except Exception:
            return ""

    def on_modified(self, event):
        if not event.is_directory and event.src_path.endswith("frpc.toml"):
            new_hash = self.get_file_hash()
            if new_hash and new_hash != self.last_hash:  # 内容实际发生变化
                self.last_hash = new_hash
                self.callback()


class ServiceManagerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("FRPC 服务管理器")
        self.root.geometry("800x600")
        self.root.resizable(True, True)
        self.service_process = None
        self.service_thread = None
        self.service_running = False
        self.last_reload_time = 0
        self.config_observer = None
        self.app_path = get_app_path()

        # 配置日志
        self.setup_logging()

        # 应用现代化主题
        self.setup_theme()

        # 构建UI
        self.create_widgets()

        # 启动配置监控
        self.start_config_monitor()

        # 自动启动服务
        self.start_service()

    def setup_logging(self):
        """配置日志记录"""
        log_path = self.app_path / "frpc_manager.log"
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_path),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger("FRPCManager")
        self.logger.info(f"应用程序启动路径: {self.app_path}")

    def setup_theme(self):
        """配置现代化UI主题"""
        style = ttk.Style()
        style.theme_use('clam')  # 使用现代主题

        # 自定义配色方案
        style.configure('TFrame', background='#f0f5ff')
        style.configure('TLabel', background='#f0f5ff', foreground='#2c3e50', font=('Segoe UI', 10))
        style.configure('TButton', font=('Segoe UI', 10), padding=6)
        style.configure('Header.TLabel', font=('Segoe UI', 14, 'bold'))
        style.configure('Status.TLabel', font=('Segoe UI', 11, 'bold'))
        style.configure('Success.TLabel', foreground='#27ae60')
        style.configure('Error.TLabel', foreground='#e74c3c')
        style.configure('Log.TFrame', background='white')

    def create_widgets(self):
        """创建界面组件"""
        # 顶部标题
        header_frame = ttk.Frame(self.root, padding=10)
        header_frame.pack(fill=tk.X)
        ttk.Label(header_frame, text="FRPC 服务管理控制台", style='Header.TLabel').pack()

        # 服务状态面板
        status_frame = ttk.LabelFrame(self.root, text="服务状态", padding=10)
        status_frame.pack(fill=tk.X, padx=10, pady=5)

        self.status_var = tk.StringVar(value="正在启动服务...")
        self.status_label = ttk.Label(
            status_frame,
            textvariable=self.status_var,
            style='Status.TLabel'
        )
        self.status_label.pack(anchor=tk.W)

        # 控制按钮
        btn_frame = ttk.Frame(self.root, padding=10)
        btn_frame.pack(fill=tk.X)

        self.start_btn = ttk.Button(btn_frame, text="启动服务", command=self.start_service)
        self.stop_btn = ttk.Button(btn_frame, text="停止服务", command=self.stop_service, state=tk.DISABLED)
        self.restart_btn = ttk.Button(btn_frame, text="重启服务", command=self.restart_service)
        self.reload_btn = ttk.Button(btn_frame, text="重载配置", command=self.reload_config)
        self.install_btn = ttk.Button(btn_frame, text="添加开机自启", command=self.install_autostart)
        self.uninstall_btn = ttk.Button(btn_frame, text="移除开机自启", command=self.uninstall_autostart)

        self.start_btn.pack(side=tk.LEFT, padx=5)
        self.stop_btn.pack(side=tk.LEFT, padx=5)
        self.restart_btn.pack(side=tk.LEFT, padx=5)
        self.reload_btn.pack(side=tk.LEFT, padx=5)
        self.install_btn.pack(side=tk.LEFT, padx=5)
        self.uninstall_btn.pack(side=tk.LEFT, padx=5)

        # 日志显示
        log_frame = ttk.LabelFrame(self.root, text="服务日志", padding=10, style='Log.TFrame')
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        self.log_area = scrolledtext.ScrolledText(
            log_frame, wrap=tk.WORD, bg='#2d3436', fg='#dfe6e9',
            font=('Consolas', 9), padx=10, pady=10
        )
        self.log_area.pack(fill=tk.BOTH, expand=True)
        self.log_area.config(state=tk.DISABLED)

    def start_config_monitor(self):
        """启动配置文件监控"""
        try:
            # 确保安装了watchdog
            import watchdog
        except ImportError:
            self.log_message("未安装watchdog库，无法监控配置变更")
            return

        # 创建观察者
        observer = watchdog.observers.Observer()
        handler = ConfigHandler(self.on_config_changed)
        observer.schedule(handler, path=str(self.app_path), recursive=False)
        observer.start()
        self.config_observer = observer
        self.log_message("已启动配置文件监控")

    def on_config_changed(self):
        """配置文件变更回调"""
        current_time = time.time()
        # 防抖处理：3秒内只触发一次
        if current_time - self.last_reload_time > 3:
            self.last_reload_time = current_time
            self.log_message("检测到配置文件变更，正在自动重载...")
            self.reload_config()

    def reload_config(self):
        """重载FRPC配置"""
        if not self.service_running:
            self.log_message("服务未运行，无法重载配置")
            return

        try:
            # 执行重载命令
            frpc_exe = resource_path("frpc.exe")

            # 检查admin端口是否启用
            if not self.check_admin_port_enabled():
                self.log_message("未启用admin端口，无法重载配置")
                self.log_message("请在frpc.toml的[common]段添加: admin_addr = '127.0.0.1' 和 admin_port = 7400")
                return

            result = subprocess.run(
                [frpc_exe, "reload", "-c", resource_path("frpc.toml")],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW
            )

            if result.returncode == 0:
                self.log_message("配置重载成功")
                self.log_message(result.stdout)
            else:
                self.log_message(f"配置重载失败，错误码: {result.returncode}")
                self.log_message(result.stdout)

        except Exception as e:
            self.log_message(f"重载配置时出错: {str(e)}")

    def check_admin_port_enabled(self):
        """检查frpc.toml是否启用了admin端口"""
        config_path = resource_path("frpc.toml")
        try:
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    # 检查[common]段下的admin配置
                    common_section = content.split('[common]')[-1].split('\n\n')[0]
                    return "admin_addr" in common_section or "admin_port" in common_section
            return False
        except Exception as e:
            self.log_message(f"检查admin端口时出错: {str(e)}")
            return False

    def run_service(self):
        """后台线程运行服务"""
        try:
            frpc_exe = resource_path("frpc.exe")
            config_file = resource_path("frpc.toml")

            if not os.path.exists(frpc_exe) or not os.path.exists(config_file):
                self.update_status("错误: 缺少FRPC执行文件或配置文件", True)
                self.log_message(f"FRPC路径: {frpc_exe}")
                self.log_message(f"配置文件路径: {config_file}")
                return

            self.log_message(f"启动FRPC服务: {frpc_exe} -c {config_file}")

            self.service_process = subprocess.Popen(
                [frpc_exe, "-c", config_file],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                errors='replace',
                creationflags=subprocess.CREATE_NO_WINDOW  # Windows隐藏控制台窗口
            )

            self.service_running = True
            self.update_status("服务运行中", False)
            self.update_buttons(True)

            # 实时捕获并显示日志
            while self.service_running:
                line = self.service_process.stdout.readline()
                if not line and self.service_process.poll() is not None:
                    break
                if line:
                    self.log_message(line.strip())

            # 服务意外退出处理
            if self.service_running:
                self.update_status("服务意外终止", True)
                return_code = self.service_process.returncode
                self.log_message(f"服务退出，返回码: {return_code}")

        except Exception as e:
            self.update_status(f"服务启动失败: {str(e)}", True)
            self.logger.exception("服务启动失败")
        finally:
            self.service_running = False
            self.update_buttons(False)

    def start_service(self):
        """启动服务"""
        if self.service_running:
            return

        self.log_message("正在启动FRPC服务...")
        self.service_thread = threading.Thread(target=self.run_service, daemon=True)
        self.service_thread.start()

    def stop_service(self):
        """停止服务"""
        if self.service_process and self.service_running:
            self.service_running = False
            self.service_process.terminate()
            self.log_message("服务已停止")
            self.update_status("服务已停止", True)
            self.update_buttons(False)

    def restart_service(self):
        """重启服务"""
        self.log_message("正在重启服务...")
        self.stop_service()
        time.sleep(1)  # 等待进程完全退出
        self.start_service()

    def install_autostart(self):
        """添加注册表开机自启项（用户登录时启动）"""
        try:
            app_name = "FRPCManager"
            # 获取当前程序路径（兼容打包和开发环境）
            if getattr(sys, 'frozen', False):
                exe_path = sys.executable
            else:
                exe_path = f'"{sys.executable}" "{os.path.abspath(__file__)}"'

            # 打开注册表键（当前用户的Run键）
            key = winreg.HKEY_CURRENT_USER
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
            with winreg.OpenKey(key, key_path, 0, winreg.KEY_WRITE) as reg_key:
                winreg.SetValueEx(reg_key, app_name, 0, winreg.REG_SZ, exe_path)

            self.log_message("已添加到注册表开机自启（用户登录时启动）！")
        except Exception as e:
            self.log_message(f"添加开机自启失败: {str(e)}")

    def uninstall_autostart(self):
        """移除注册表开机自启项"""
        try:
            app_name = "FRPCManager"
            key = winreg.HKEY_CURRENT_USER
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
            with winreg.OpenKey(key, key_path, 0, winreg.KEY_WRITE) as reg_key:
                winreg.DeleteValue(reg_key, app_name)
            self.log_message("已从注册表开机自启中移除！")
        except Exception as e:
            self.log_message(f"移除开机自启失败: {str(e)}")

    def update_buttons(self, running):
        """更新按钮状态"""
        if running:
            self.start_btn.config(state=tk.DISABLED)
            self.stop_btn.config(state=tk.NORMAL)
            self.reload_btn.config(state=tk.NORMAL)
        else:
            self.start_btn.config(state=tk.NORMAL)
            self.stop_btn.config(state=tk.DISABLED)
            self.reload_btn.config(state=tk.DISABLED)

    def update_status(self, message, is_error=False):
        """更新状态显示"""
        self.status_var.set(message)
        if is_error:
            self.status_label.configure(style='Error.TLabel')
        else:
            self.status_label.configure(style='Success.TLabel')

    def log_message(self, message):
        """添加日志信息"""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {message}\n"

        self.log_area.config(state=tk.NORMAL)
        self.log_area.insert(tk.END, log_entry)
        self.log_area.see(tk.END)  # 自动滚动到底部
        self.log_area.config(state=tk.DISABLED)

        # 同时输出到日志记录器
        self.logger.info(message)

    def on_closing(self):
        """窗口关闭事件处理"""
        # 停止配置监控
        if self.config_observer:
            self.config_observer.stop()
            self.config_observer.join()

        # 停止服务
        if self.service_running:
            if messagebox.askyesno("确认", "服务仍在运行，确定要退出吗？"):
                self.stop_service()
                self.root.destroy()
        else:
            self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = ServiceManagerApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()