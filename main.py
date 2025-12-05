import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import subprocess
import threading
import configparser
from concurrent.futures import ThreadPoolExecutor

# 配置文件名
CONFIG_FILE = "config.ini"

# --- 辅助类：滚动框架 (保持不变) ---
class ScrollableFrame(ttk.Frame):
    def __init__(self, container, *args, **kwargs):
        super().__init__(container, *args, **kwargs)
        self.canvas = tk.Canvas(self, borderwidth=0, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")

# --- 核心类：Git 操作基类 (新抽象出来的父类) ---
class GitItemBase:
    def __init__(self, app, path, display_name):
        self.app = app
        self.full_path = path
        self.display_name = display_name
        self.is_update_available = False

    def run_git(self, args):
        return self.app.run_git_cmd(self.full_path, args)

    def check_status_base(self):
        if not os.path.exists(os.path.join(self.full_path, ".git")):
            return "非Git仓库", "gray", False
        
        self.run_git(["fetch"]) 
        code, out, _ = self.run_git(["status", "-uno"])
        
        if "behind" in out or "落后" in out:
            return "检测到新版本", "red", True
        elif "detached" in out:
             return "处于历史版本", "orange", False
        
        return "最新版本", "green", False

    def fetch_versions_base(self):
        versions = ["最新版本 (Latest)"]
        if not os.path.exists(os.path.join(self.full_path, ".git")):
            return []
        
        # Tags
        code, out, _ = self.run_git(["tag", "--sort=-creatordate"])
        if code == 0 and out:
            tags = out.split('\n')[:8] # 取最近8个tag
            for t in tags:
                if t.strip(): versions.append(f"Tag: {t.strip()}")

        # Commits
        code, out, _ = self.run_git(["log", "--pretty=format:%h - %s", "-n", "15"])
        if code == 0 and out:
            commits = out.split('\n')
            for c in commits:
                if c.strip(): versions.append(f"Commit: {c.strip()}")
        return versions

    def do_update_logic(self, selection, silent=False):
        # 通用的更新逻辑
        try:
            def try_force_reset(err_msg):
                keywords = ["overwritten by merge", "stash them", "local changes", "aborted"]
                if any(k in err_msg for k in keywords):
                    if messagebox.askyesno("冲突解决", 
                        f"检测到 {self.display_name} 有本地修改导致更新失败。\n\n是否【丢弃本地修改】并强制更新？"):
                        r_code, _, r_err = self.run_git(["reset", "--hard", "HEAD"])
                        return r_code == 0
                return False

            if "最新版本" in selection:
                # 获取当前分支或 HEAD 指向的分支
                code, out, _ = self.run_git(["remote", "show", "origin"])
                head_branch = "master" 
                if "HEAD branch" in out:
                    for line in out.splitlines():
                        if "HEAD branch" in line:
                            head_branch = line.split(":")[-1].strip()
                            break
                
                # 尝试 checkout 回主分支 (防止处于 detached 状态无法 pull)
                self.run_git(["checkout", head_branch])
                
                code, out, err = self.run_git(["pull"])
                if code != 0:
                    if try_force_reset(err):
                        code, out, err = self.run_git(["pull"])

                if code == 0:
                    return True, "更新成功"
                else:
                    return False, f"更新失败: {err}"

            elif "Tag:" in selection or "Commit:" in selection:
                target = selection.replace("Tag: ", "").strip() if "Tag:" in selection else selection.split(" ")[1].strip()
                code, _, err = self.run_git(["checkout", target])
                if code != 0:
                    if try_force_reset(err):
                        code, _, err = self.run_git(["checkout", target])
                
                if code == 0:
                    return True, f"已回退: {target}"
                else:
                    return False, f"切换失败: {err}"
            return False, "未选择操作"

        except Exception as e:
            return False, str(e)

# --- 插件行UI (继承自 GitItemBase) ---
class PluginRow(GitItemBase):
    def __init__(self, parent_frame, app, folder_name):
        full_path = os.path.join(app.nodes_path, folder_name)
        super().__init__(app, full_path, folder_name)
        
        self.frame = tk.Frame(parent_frame, bd=1, relief=tk.RIDGE, bg="white")
        self.frame.pack(fill="x", pady=2, padx=5)
        
        self.lbl_name = tk.Label(self.frame, text=folder_name, width=30, anchor="w", font=("Arial", 9, "bold"), bg="white")
        self.lbl_name.pack(side="left", padx=5)

        self.lbl_status = tk.Label(self.frame, text="等待检查...", width=15, fg="gray", bg="white")
        self.lbl_status.pack(side="left", padx=5)

        self.var_version = tk.StringVar()
        self.combo_versions = ttk.Combobox(self.frame, textvariable=self.var_version, width=30, state="readonly")
        self.combo_versions.set("加载中...")
        self.combo_versions.pack(side="left", padx=5)

        self.btn_action = tk.Button(self.frame, text="执行操作", command=self.on_action_click, bg="#f0f0f0", state="disabled")
        self.btn_action.pack(side="right", padx=5)

        threading.Thread(target=self.init_data, daemon=True).start()

    def init_data(self):
        text, color, is_update = self.check_status_base()
        self.is_update_available = is_update
        self.app.root.after(0, lambda: self.lbl_status.config(text=text, fg=color))

        versions = self.fetch_versions_base()
        self.app.root.after(0, lambda: self._update_combo(versions))

    def _update_combo(self, versions):
        self.combo_versions['values'] = versions
        if versions: self.combo_versions.current(0)
        else: self.combo_versions.set("无版本记录")
        self.btn_action.config(state="normal")

    def on_action_click(self):
        selection = self.var_version.get()
        if not selection: return
        if messagebox.askyesno("确认", f"对插件 {self.display_name} 执行:\n{selection}?"):
            self.btn_action.config(state="disabled", text="执行中...")
            threading.Thread(target=self.do_update, args=(selection, False), daemon=True).start()

    def do_update(self, selection, silent=False):
        success, msg = self.do_update_logic(selection, silent)
        def post_ui():
            self.btn_action.config(state="normal", text="执行操作")
            if success:
                self.lbl_status.config(text="操作成功", fg="green")
                self.is_update_available = False
                if not silent: messagebox.showinfo("成功", f"{self.display_name}: {msg}")
            else:
                self.lbl_status.config(text="操作失败", fg="red")
                if not silent: messagebox.showerror("失败", f"{self.display_name}: {msg}")
        self.app.root.after(0, post_ui)

# --- ComfyUI 本体管理 UI ---
class CoreManagerFrame(tk.Frame, GitItemBase):
    def __init__(self, parent, app):
        tk.Frame.__init__(self, parent)
        self.app = app
        # 这里路径暂时为空，等 select_directory 后设置
        GitItemBase.__init__(self, app, "", "ComfyUI 本体")
        
        self.create_widgets()
    
    def create_widgets(self):
        # 顶部提示
        tk.Label(self, text="ComfyUI 本体版本管理", font=("Arial", 14, "bold"), pady=10).pack()
        
        # 路径显示
        self.lbl_path = tk.Label(self, text="当前路径: 未设置", fg="gray")
        self.lbl_path.pack()

        # 状态显示区域
        status_frame = tk.LabelFrame(self, text="当前状态", padx=20, pady=20)
        status_frame.pack(fill="x", padx=20, pady=10)

        self.lbl_status_large = tk.Label(status_frame, text="未知", font=("Arial", 12))
        self.lbl_status_large.pack()
        
        self.lbl_commit_info = tk.Label(status_frame, text="", fg="#555")
        self.lbl_commit_info.pack(pady=5)

        # 操作区域
        action_frame = tk.LabelFrame(self, text="更新/回退操作", padx=20, pady=20)
        action_frame.pack(fill="x", padx=20, pady=10)

        tk.Label(action_frame, text="选择目标版本:").pack(anchor="w")
        self.var_version = tk.StringVar()
        self.combo_versions = ttk.Combobox(action_frame, textvariable=self.var_version, width=50, state="readonly")
        self.combo_versions.pack(fill="x", pady=5)

        btn_bar = tk.Frame(action_frame)
        btn_bar.pack(fill="x", pady=10)
        
        self.btn_check = tk.Button(btn_bar, text="检查更新", command=self.refresh_data)
        self.btn_check.pack(side="left", padx=5)

        self.btn_execute = tk.Button(btn_bar, text="开始执行", bg="#c8e6c9", command=self.on_execute)
        self.btn_execute.pack(side="right", padx=5)

    def set_path(self, path):
        self.full_path = path
        self.lbl_path.config(text=f"位置: {path}")
        self.refresh_data()

    def refresh_data(self):
        if not self.full_path or not os.path.exists(self.full_path):
            return
        
        self.btn_check.config(state="disabled")
        threading.Thread(target=self._async_check, daemon=True).start()

    def _async_check(self):
        # 1. 获取基本状态
        text, color, is_update = self.check_status_base()
        
        # 2. 获取当前 Commit 信息
        _, current_commit, _ = self.run_git(["log", "-1", "--format=%h - %s (%cd)", "--date=short"])
        
        # 3. 获取版本列表
        versions = self.fetch_versions_base()

        def update_ui():
            self.lbl_status_large.config(text=text, fg=color)
            self.lbl_commit_info.config(text=f"当前Commit: {current_commit}")
            self.combo_versions['values'] = versions
            if versions: self.combo_versions.current(0)
            self.btn_check.config(state="normal")
        
        self.app.root.after(0, update_ui)

    def on_execute(self):
        selection = self.var_version.get()
        if not selection: return

        if messagebox.askyesno("风险提示", f"即将对 ComfyUI 本体执行:\n{selection}\n\n注意：如果 ComfyUI 正在运行，请先关闭它，否则可能更新失败。确定继续吗？"):
            self.btn_execute.config(state="disabled", text="执行中...")
            threading.Thread(target=self._async_execute, args=(selection,), daemon=True).start()

    def _async_execute(self, selection):
        success, msg = self.do_update_logic(selection)
        def post():
            self.btn_execute.config(state="normal", text="开始执行")
            if success:
                messagebox.showinfo("成功", f"本体操作完成: {msg}\n请重启 ComfyUI。")
                self.refresh_data()
            else:
                messagebox.showerror("失败", msg)
        self.app.root.after(0, post)


# --- 主程序类 ---
class ComfyUpdaterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("ComfyUI 全能管理器 (插件 + 本体)")
        self.root.geometry("1100x750")

        self.config = configparser.ConfigParser()
        self.git_exe = "git"
        self.comfyui_root = "" # 变更为根目录
        self.nodes_path = ""
        self.proxy_url = "" 
        
        # UI 组件引用
        self.plugin_rows = []
        
        # 1. 顶部选择栏
        top_frame = tk.Frame(root, pady=10, bg="#f5f5f5")
        top_frame.pack(fill="x")
        
        tk.Button(top_frame, text="设置 ComfyUI 根目录", command=self.select_directory).pack(side="left", padx=10)
        self.path_label = tk.Label(top_frame, text="未选择", fg="blue", bg="#f5f5f5")
        self.path_label.pack(side="left")

        # 2. 选项卡 (Notebook)
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill="both", expand=True, padx=5, pady=5)

        # Tab 1: 插件管理
        self.tab_plugins = tk.Frame(self.notebook)
        self.notebook.add(self.tab_plugins, text=" 🧩 插件管理 (Custom Nodes) ")
        
        # Tab 1 的工具栏
        plugin_toolbar = tk.Frame(self.tab_plugins)
        plugin_toolbar.pack(fill="x", pady=5)
        tk.Button(plugin_toolbar, text="刷新列表", command=self.refresh_plugin_list).pack(side="right", padx=5)
        self.btn_update_all = tk.Button(plugin_toolbar, text="一键更新所有插件", command=self.update_all_plugins, bg="#c8e6c9")
        self.btn_update_all.pack(side="right", padx=5)

        self.list_container = ScrollableFrame(self.tab_plugins)
        self.list_container.pack(fill="both", expand=True, padx=10, pady=5)

        # Tab 2: 本体管理
        self.tab_core = tk.Frame(self.notebook)
        self.notebook.add(self.tab_core, text=" ⚙️ ComfyUI 本体管理 ")
        
        self.core_manager = CoreManagerFrame(self.tab_core, self)
        self.core_manager.pack(fill="both", expand=True)

        # 3. 底部状态栏
        self.status_bar = tk.Label(root, text="就绪", bd=1, relief=tk.SUNKEN, anchor="w")
        self.status_bar.pack(side="bottom", fill="x")

        # 加载配置
        self.load_config()

    def load_config(self):
        if not os.path.exists(CONFIG_FILE): return
        try:
            self.config.read(CONFIG_FILE, encoding='utf-8')
            if 'Settings' in self.config:
                self.git_exe = self.config['Settings'].get('git_path', 'git').strip()
                p = self.config['Settings'].get('comfyui_root_path', '').strip()
                if p:
                    self.set_root_path(p if os.path.isabs(p) else os.path.abspath(os.path.join(os.getcwd(), p)))
            
            if 'Network' in self.config:
                self.proxy_url = self.config['Network'].get('https_proxy', '').strip()
        except: pass

    def select_directory(self):
        path = filedialog.askdirectory(title="选择 ComfyUI 根目录 (包含 main.py 和 custom_nodes 的文件夹)", initialdir=self.comfyui_root)
        if path:
            self.set_root_path(path)

    def set_root_path(self, root_path):
        """ 统一设置路径并刷新两个 Tab """
        self.comfyui_root = root_path
        self.nodes_path = os.path.join(root_path, "custom_nodes")
        self.path_label.config(text=self.comfyui_root)
        
        # 刷新状态栏
        self.status_bar.config(text=f"代理: {self.proxy_url if self.proxy_url else '无'}")

        # 1. 刷新本体 Tab
        self.core_manager.set_path(self.comfyui_root)

        # 2. 刷新插件 Tab
        if os.path.exists(self.nodes_path):
            self.refresh_plugin_list()
        else:
            messagebox.showwarning("警告", f"在所选目录下没找到 'custom_nodes' 文件夹。\n请确认选择了正确的 ComfyUI 根目录。")

    def run_git_cmd(self, folder_path, args):
        try:
            cmd = [self.git_exe] + args
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            
            env = os.environ.copy()
            env["GIT_TERMINAL_PROMPT"] = "0"
            env["GCM_INTERACTIVE"] = "never"
            if self.proxy_url:
                env["http_proxy"] = self.proxy_url
                env["https_proxy"] = self.proxy_url

            result = subprocess.run(
                cmd, cwd=folder_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, encoding='utf-8', errors='ignore', 
                startupinfo=startupinfo, env=env, timeout=60
            )
            return result.returncode, result.stdout.strip(), result.stderr.strip()
        except Exception as e:
            return -1, "", str(e)

    def refresh_plugin_list(self):
        for widget in self.list_container.scrollable_frame.winfo_children():
            widget.destroy()
        self.plugin_rows.clear()

        if not os.path.exists(self.nodes_path): return

        folders = [f for f in os.listdir(self.nodes_path) if os.path.isdir(os.path.join(self.nodes_path, f))]
        
        for folder in folders:
            # 排除 __pycache__ 等非插件文件夹
            if folder.startswith("__") or folder.startswith("."): continue
            row = PluginRow(self.list_container.scrollable_frame, self, folder)
            self.plugin_rows.append(row)

    def update_all_plugins(self):
        targets = [row for row in self.plugin_rows if row.is_update_available]
        
        if not targets:
            messagebox.showinfo("提示", "当前没有检测到需要更新的插件。")
            return

        if not messagebox.askyesno("批量更新", f"检测到 {len(targets)} 个插件有新版本。\n是否开始批量更新？"):
            return

        self.btn_update_all.config(state="disabled", text="正在更新...")
        
        def run_batch():
            with ThreadPoolExecutor(max_workers=5) as executor:
                for row in targets:
                    row.btn_action.config(state="disabled", text="队列中...")
                    executor.submit(row.do_update, "最新版本 (Latest)", True)
            
            self.root.after(0, lambda: self.btn_update_all.config(state="normal", text="一键更新所有插件"))
            self.root.after(0, lambda: messagebox.showinfo("完成", "批量更新流程已结束。"))

        threading.Thread(target=run_batch, daemon=True).start()

if __name__ == "__main__":
    root = tk.Tk()
    app = ComfyUpdaterApp(root)
    root.mainloop()