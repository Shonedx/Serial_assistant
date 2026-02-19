import tkinter as tk
from tkinter import colorchooser, messagebox
import customtkinter as ctk
import serial
import serial.tools.list_ports
import threading
import time
import binascii  # 处理十六进制转换

# 全局样式
ctk.set_appearance_mode("Dark")

class MotorApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.version = "v1.3.1_Full_Feature"
        self.title(f"串口助手_极客翔 ({self.version})")
        self.geometry("1300x950")
        
        # 样式变量
        self.font_family = tk.StringVar(value="KaiTi")
        self.font_size = tk.IntVar(value=14)
        self.text_bg_color = tk.StringVar(value="#1e1e1e")
        self.text_fg_color = tk.StringVar(value="#00FF00")
        
        # 新增：格式/编码配置变量
        self.send_format = tk.StringVar(value="Text")  # Text/HEX
        self.recv_format = tk.StringVar(value="Text")  # Text/HEX
        self.send_encoding = tk.StringVar(value="UTF-8")  # UTF-8/GBK
        self.recv_encoding = tk.StringVar(value="UTF-8")  # UTF-8/GBK
        
        # 核心监听
        self.text_bg_color.trace_add("write", lambda *args: self.apply_global_theme())
        self.text_fg_color.trace_add("write", lambda *args: self.apply_global_theme())
        # 新增：格式切换监听（控制编码选项是否可用）
        self.send_format.trace_add("write", self.on_format_change)
        self.recv_format.trace_add("write", self.on_format_change)

        self.ser = None
        self.running = False
        self.encoding = tk.StringVar(value="UTF-8")  # 兼容原有逻辑

        # 布局
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # 侧边栏
        self.sidebar = ctk.CTkFrame(self, width=80)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.setup_sidebar()

        # 容器
        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.grid(row=0, column=1, padx=15, pady=15, sticky="nsew")
        self.container.grid_columnconfigure(0, weight=1)
        self.container.grid_rowconfigure(0, weight=1)

        self.frames = {}
        for F in (ConsolePage, ParamPage, SettingPage):
            frame = F(parent=self.container, controller=self)
            self.frames[F.__name__] = frame
            frame.grid(row=0, column=0, sticky="nsew")

        # 修复：所有页面创建完成后，再初始化格式/编码控件状态
        self.show_frame("ConsolePage")
        self.init_format_controls()  # 新增：统一初始化控件状态

    def setup_sidebar(self):
        menu = [("📝", "ConsolePage"), ("⚙️", "ParamPage"), ("🎨", "SettingPage")]
        for icon, page in menu:
            ctk.CTkButton(self.sidebar, text=icon, width=60, height=60, font=("Arial", 28),
                          fg_color="transparent", hover_color="#333333",
                          command=lambda p=page: self.show_frame(p)).pack(pady=20)

    def apply_global_theme(self):
        """递归刷新所有文本框颜色（修复：区分组件类型，适配原生tkinter属性）"""
        bg, fg = self.text_bg_color.get(), self.text_fg_color.get()
        fs, ff = self.font_size.get(), self.font_family.get()

        def update_recursive(parent):
            for child in parent.winfo_children():
                try:
                    # 1. 区分组件类型：customtkinter文本框 vs tkinter原生文本框
                    if isinstance(child, ctk.CTkTextbox):
                        # CTkTextbox：使用customtkinter属性
                        child.configure(fg_color=bg, text_color=fg, font=(ff, fs))
                    elif isinstance(child, tk.Text):
                        # tk.Text：使用原生tkinter属性
                        child.configure(bg=bg, fg=fg, font=(ff, fs))
                    
                    # 2. 处理颜色预览按钮（自定义tag）
                    if hasattr(child, "preview_tag"):
                        child.configure(fg_color=bg if child.preview_tag=="bg" else fg)
                    
                    # 3. 递归处理子组件
                    if child.winfo_children():
                        update_recursive(child)
                except Exception as e:
                    # 捕获单个组件的配置异常，不中断整体递归
                    print(f"组件样式更新警告：{child} - {e}")
                    continue
        update_recursive(self)

    def init_format_controls(self):
        """新增：统一初始化格式/编码控件状态（避免提前调用）"""
        self.on_format_change()

    def on_format_change(self, *args):
        """格式切换时控制编码选项是否可用（修复KeyError）"""
        # 修复：先判断键是否存在，避免KeyError
        if 'ConsolePage' in self.frames:
            console_frame = self.frames['ConsolePage']
            # 发送编码选项：Text模式可用，HEX模式禁用
            if hasattr(console_frame, 'send_encoding_opt'):
                console_frame.send_encoding_opt.configure(
                    state="normal" if self.send_format.get() == "Text" else "disabled"
                )
            # 接收编码选项：Text模式可用，HEX模式禁用
            if hasattr(console_frame, 'recv_encoding_opt'):
                console_frame.recv_encoding_opt.configure(
                    state="normal" if self.recv_format.get() == "Text" else "disabled"
                )

    def show_frame(self, page_name):
        self.frames[page_name].tkraise()
        self.apply_global_theme()

    def hex_to_bytes(self, hex_str):
        """十六进制字符串转字节（处理空格/大小写）"""
        try:
            # 移除所有空格，转大写
            hex_clean = hex_str.replace(" ", "").upper()
            # 校验是否为合法十六进制
            if not all(c in "0123456789ABCDEF" for c in hex_clean):
                raise ValueError("包含非十六进制字符")
            # 补全偶数长度（1个字符时补0）
            if len(hex_clean) % 2 != 0:
                hex_clean = "0" + hex_clean
            return binascii.unhexlify(hex_clean)
        except Exception as e:
            messagebox.showerror("HEX格式错误", f"十六进制转换失败：{str(e)}")
            return None

    def bytes_to_hex(self, byte_data):
        """字节转十六进制字符串（带空格分隔）"""
        return binascii.hexlify(byte_data).upper().decode("ascii").replace("", " ").strip()

    def send_raw(self, data):
        """发送原始数据（适配Text/HEX格式 + 编码切换）"""
        if not self.ser or not self.ser.is_open:
            messagebox.showwarning("提示", "请先打开串口！")
            return

        try:
            send_data = None
            # 1. 处理发送格式
            if self.send_format.get() == "Text":
                # 文本模式：按选择编码转字节
                encoding = self.send_encoding.get()
                send_data = data.encode(encoding, errors="ignore")
            else:
                # HEX模式：转十六进制字节
                send_data = self.hex_to_bytes(data)
                if send_data is None:
                    return

            # 2. 发送数据
            self.ser.write(send_data)

            # 3. 同步到反馈区（显示实际发送的内容）
            display_data = ""
            if self.send_format.get() == "Text":
                display_data = f"[发送({self.send_encoding.get()})] {data}\n"
            else:
                display_data = f"[发送(HEX)] {self.bytes_to_hex(send_data)}\n"
            
            if hasattr(self.frames['ParamPage'], 'feedback_box'):
                self.frames['ParamPage'].feedback_box.insert("end", display_data)
                self.frames['ParamPage'].feedback_box.see("end")
            if hasattr(self.frames['SettingPage'], 'feedback_box'):
                self.frames['SettingPage'].feedback_box.insert("end", display_data)
                self.frames['SettingPage'].feedback_box.see("end")

        except Exception as e:
            messagebox.showerror("发送失败", f"串口发送错误：{str(e)}")

    def clear_all_terminal_text(self):
        """全局清除所有终端文本区域"""
        try:
            if hasattr(self.frames['ConsolePage'], 'recv_box'):
                self.frames['ConsolePage'].recv_box.delete("1.0", tk.END)
            if hasattr(self.frames['ConsolePage'], 'send_box'):
                self.frames['ConsolePage'].send_box.delete("1.0", tk.END)
            if hasattr(self.frames['ParamPage'], 'feedback_box'):
                self.frames['ParamPage'].feedback_box.delete("1.0", tk.END)
            if hasattr(self.frames['SettingPage'], 'feedback_box'):
                self.frames['SettingPage'].feedback_box.delete("1.0", tk.END)
            messagebox.showinfo("成功", "所有终端文本已清空！")
        except Exception as e:
            messagebox.showerror("错误", f"清除文本失败：{str(e)}")

# --- 页面1：串口助手 (新增格式/编码设置) ---
class ConsolePage(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller
        
        # 配置区（拆分为上下两行，适配新增的格式选项）
        cfg_top = ctk.CTkFrame(self)
        cfg_top.pack(fill="x", pady=5)
        
        # 第一行：串口选择 + 打开串口 + 清除按钮
        self.port_sel = ctk.CTkOptionMenu(cfg_top, values=self.get_serial_ports(), width=100)
        self.port_sel.pack(side="left", padx=5)
        self.btn_open = ctk.CTkButton(cfg_top, text="打开串口", width=100, command=self.toggle_ser)
        self.btn_open.pack(side="left", padx=10)
        
        # 清除按钮组
        ctk.CTkButton(cfg_top, text="清除所有终端", width=100, 
                      command=self.controller.clear_all_terminal_text,
                      fg_color="#8e44ad", hover_color="#7d3c98"
                     ).pack(side="right", padx=5)
        ctk.CTkButton(cfg_top, text="清除接收", width=80, 
                      command=lambda: self.recv_box.delete("1.0", tk.END)
                     ).pack(side="right", padx=5)

        # 第二行：格式/编码设置
        cfg_bottom = ctk.CTkFrame(self)
        cfg_bottom.pack(fill="x", pady=5)
        
        # 接收格式设置
        ctk.CTkLabel(cfg_bottom, text="接收格式：", width=80).pack(side="left", padx=5)
        recv_format_opt = ctk.CTkOptionMenu(cfg_bottom, values=["Text", "HEX"], 
                                            variable=self.controller.recv_format, width=80)
        recv_format_opt.pack(side="left", padx=2)
        ctk.CTkLabel(cfg_bottom, text="编码：", width=50).pack(side="left")
        self.recv_encoding_opt = ctk.CTkOptionMenu(cfg_bottom, values=["UTF-8", "GBK"], 
                                                   variable=self.controller.recv_encoding, width=80)
        self.recv_encoding_opt.pack(side="left", padx=5)
        
        # 发送格式设置
        ctk.CTkLabel(cfg_bottom, text="发送格式：", width=80).pack(side="left", padx=20)
        send_format_opt = ctk.CTkOptionMenu(cfg_bottom, values=["Text", "HEX"], 
                                            variable=self.controller.send_format, width=80)
        send_format_opt.pack(side="left", padx=2)
        ctk.CTkLabel(cfg_bottom, text="编码：", width=50).pack(side="left")
        self.send_encoding_opt = ctk.CTkOptionMenu(cfg_bottom, values=["UTF-8", "GBK"], 
                                                   variable=self.controller.send_encoding, width=80)
        self.send_encoding_opt.pack(side="left", padx=5)

        # 接收区域
        self.recv_box = ctk.CTkTextbox(self)
        self.recv_box.pack(fill="both", expand=True, padx=5, pady=5)
        
        # 发送区域
        send_f = ctk.CTkFrame(self, height=150)
        send_f.pack(fill="x", pady=5)
        self.send_box = ctk.CTkTextbox(send_f, height=100)
        self.send_box.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        
        # 发送区域按钮容器
        btn_frame = ctk.CTkFrame(send_f, fg_color="transparent")
        btn_frame.pack(side="right", padx=5, pady=5)
        
        # 发送按钮
        ctk.CTkButton(btn_frame, text="发送", width=80, 
                      command=lambda: self.controller.send_raw(self.send_box.get("1.0", "end-1c"))
                     ).pack(side="top", pady=5)
        
        # 发送区域清除按钮
        ctk.CTkButton(btn_frame, text="清除发送", width=80, 
                      command=lambda: self.send_box.delete("1.0", tk.END),
                      fg_color="#e74c3c", hover_color="#c0392b"
                     ).pack(side="top", pady=5)

        # 移除：不再在__init__里直接调用，改为全局统一初始化
        # self.controller.on_format_change()

    def get_serial_ports(self):
        """自动获取可用串口"""
        ports = serial.tools.list_ports.comports()
        return [port.device for port in ports] if ports else ["COM1", "COM2", "COM3"]

    def toggle_ser(self):
        """完善串口开关逻辑"""
        if self.controller.ser and self.controller.ser.is_open:
            # 关闭串口
            self.controller.ser.close()
            self.btn_open.configure(text="打开串口")
            self.controller.running = False
        else:
            # 打开串口
            try:
                self.controller.ser = serial.Serial(
                    port=self.port_sel.get(),
                    baudrate=9600,
                    timeout=0.1
                )
                self.btn_open.configure(text="关闭串口")
                self.controller.running = True
                # 启动接收线程
                threading.Thread(target=self.receive_thread, daemon=True).start()
            except Exception as e:
                messagebox.showerror("失败", f"打开串口失败：{str(e)}")

    def receive_thread(self):
        """串口接收线程（适配Text/HEX格式 + 编码切换）"""
        while self.controller.running and self.controller.ser.is_open:
            try:
                if self.controller.ser.in_waiting > 0:
                    # 读取原始字节数据
                    byte_data = self.controller.ser.read(self.controller.ser.in_waiting)
                    display_data = ""
                    
                    # 处理接收格式
                    if self.controller.recv_format.get() == "Text":
                        # 文本模式：按选择编码解码
                        encoding = self.controller.recv_encoding.get()
                        display_data = byte_data.decode(encoding, errors="ignore")
                        display_prefix = f"[接收({encoding})] "
                    else:
                        # HEX模式：转十六进制字符串
                        display_data = self.controller.bytes_to_hex(byte_data)
                        display_prefix = "[接收(HEX)] "

                    # 同步到主接收框
                    self.recv_box.insert("end", display_prefix + display_data + "\n")
                    self.recv_box.see("end")
                    
                    # 同步到参数页反馈框
                    if hasattr(self.controller.frames['ParamPage'], 'feedback_box'):
                        self.controller.frames['ParamPage'].feedback_box.insert("end", display_prefix + display_data + "\n")
                        self.controller.frames['ParamPage'].feedback_box.see("end")
                    # 同步到设置页反馈框
                    if hasattr(self.controller.frames['SettingPage'], 'feedback_box'):
                        self.controller.frames['SettingPage'].feedback_box.insert("end", display_prefix + display_data + "\n")
                        self.controller.frames['SettingPage'].feedback_box.see("end")
                time.sleep(0.01)
            except Exception as e:
                # 捕获异常但不中断线程
                print(f"接收数据异常：{e}")
                pass

# --- 页面2：电机调优 (核心改造：自定义参数组件) ---
class ParamPage(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller
        
        # 左侧工具栏：添加组件
        tools = ctk.CTkFrame(self, width=180)
        tools.pack(side="left", fill="y", padx=5, pady=5)
        ctk.CTkLabel(tools, text="组件工厂", font=("KaiTi", 18)).pack(pady=10)
        
        ctk.CTkButton(tools, text="+ 自定义参数组件", command=self.add_custom_param).pack(pady=10, padx=10)
        ctk.CTkButton(tools, text="+ 纯文本指令组件", command=self.add_text_cmd).pack(pady=10, padx=10)

        # 右侧内容区：自定义参数组件容器
        self.scroll = ctk.CTkScrollableFrame(self, label_text="自定义参数控制台 (支持自动/手动发送)")
        self.scroll.pack(side="top", fill="both", expand=True, padx=5, pady=5)

        # 下位机反馈显示区（需求：查看调整）
        mon_f = ctk.CTkFrame(self, height=200)
        mon_f.pack(side="bottom", fill="x", padx=5, pady=5)
        ctk.CTkLabel(mon_f, text="📥 下位机反馈显示区:", font=("KaiTi", 14)).pack(anchor="w", padx=10)
        self.feedback_box = ctk.CTkTextbox(mon_f, height=150)
        self.feedback_box.pack(fill="both", expand=True, padx=5, pady=5)
        # 反馈区清除按钮
        ctk.CTkButton(mon_f, text="清除反馈", width=80, 
                      command=lambda: self.feedback_box.delete("1.0", tk.END),
                      fg_color="#95a5a6", hover_color="#7f8c8d"
                     ).pack(side="right", padx=5, pady=5)

    def add_custom_param(self):
        """添加自定义参数组件"""
        CustomParamComponent(self.scroll, self.controller).pack(fill="x", pady=8, padx=5)

    def add_text_cmd(self):
        """添加纯文本指令组件"""
        TextCmdComponent(self.scroll, self.controller).pack(fill="x", pady=8, padx=5)

# --- 核心改造：自定义参数组件 (需求16/17/22) ---
class CustomParamComponent(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, border_width=2, border_color="#3498DB", corner_radius=8)
        self.controller = controller
        
        # 基础变量
        self.auto_sending = False  # 自动发送状态
        self.send_count = 0        # 已发送次数
        self.max_send_times = 1    # 一次性发送次数
        self.send_interval = 100   # 发送间隔(ms)
        
        # ========== 第一行：数据名称和格式配置 ==========
        row1 = ctk.CTkFrame(self, fg_color="transparent")
        row1.pack(fill="x", padx=10, pady=8)
        
        # 数据名称
        ctk.CTkLabel(row1, text="数据名称:", width=80).pack(side="left")
        self.name_entry = ctk.CTkEntry(row1, placeholder_text="如：电机速度", width=150)
        self.name_entry.pack(side="left", padx=5)
        
        # 协议格式（特定格式文本，需求22）
        ctk.CTkLabel(row1, text="协议格式:", width=80).pack(side="left")
        self.format_entry = ctk.CTkEntry(row1, placeholder_text="如：SPEED={VAL}", width=200)
        self.format_entry.pack(side="left", padx=5)
        
        # 移除组件按钮
        ctk.CTkButton(row1, text="🗑️", width=30, fg_color="#e74c3c", hover_color="#c0392b",
                      command=self.destroy).pack(side="right", padx=5)

        # ========== 第二行：数值范围和滑块 ==========
        row2 = ctk.CTkFrame(self, fg_color="transparent")
        row2.pack(fill="x", padx=10, pady=5)
        
        # 数值范围
        ctk.CTkLabel(row2, text="数值范围:", width=80).pack(side="left")
        self.min_entry = ctk.CTkEntry(row2, placeholder_text="最小值", width=80)
        self.min_entry.insert(0, "0")
        self.min_entry.pack(side="left", padx=2)
        ctk.CTkLabel(row2, text="-").pack(side="left")
        self.max_entry = ctk.CTkEntry(row2, placeholder_text="最大值", width=80)
        self.max_entry.insert(0, "100")
        self.max_entry.pack(side="left", padx=2)
        ctk.CTkButton(row2, text="更新范围", width=80, command=self.update_range).pack(side="left", padx=5)
        
        # 滑块（核心交互）
        self.slider = ctk.CTkSlider(row2, from_=0, to=100, command=self.on_slider_change)
        self.slider.pack(side="left", fill="x", expand=True, padx=10)
        
        # 数值输入框（优化：自适应大小，超长滚动，需求16）
        self.val_entry = ctk.CTkEntry(row2, width=80)
        self.val_entry.insert(0, "0.00")
        # 输入框事件：失去焦点时恢复默认宽度，输入时允许滚动
        self.val_entry.bind("<FocusOut>", self.on_entry_focus_out)
        self.val_entry.bind("<KeyRelease>", self.on_entry_key)
        self.val_entry.pack(side="left", padx=5)

        # ========== 第三行：发送模式配置 ==========
        row3 = ctk.CTkFrame(self, fg_color="transparent")
        row3.pack(fill="x", padx=10, pady=8)
        
        # 发送模式选择：手动/自动
        self.send_mode = ctk.StringVar(value="manual")
        ctk.CTkRadioButton(row3, text="手动模式", variable=self.send_mode, value="manual",
                           command=self.on_mode_change).pack(side="left", padx=10)
        ctk.CTkRadioButton(row3, text="自动模式", variable=self.send_mode, value="auto",
                           command=self.on_mode_change).pack(side="left", padx=10)
        
        # 自动模式参数：间隔(ms)
        ctk.CTkLabel(row3, text="发送间隔(ms):", width=100).pack(side="left")
        self.interval_entry = ctk.CTkEntry(row3, width=80)
        self.interval_entry.insert(0, "100")
        self.interval_entry.pack(side="left", padx=5)
        
        # 自动模式参数：发送次数（0=无限次）
        ctk.CTkLabel(row3, text="发送次数(0=无限):", width=120).pack(side="left")
        self.times_entry = ctk.CTkEntry(row3, width=80)
        self.times_entry.insert(0, "0")
        self.times_entry.pack(side="left", padx=5)
        
        # 手动发送按钮
        self.manual_send_btn = ctk.CTkButton(row3, text="手动发送", width=100,
                                             command=self.manual_send, fg_color="#2ecc71")
        self.manual_send_btn.pack(side="right", padx=5)
        
        # 自动发送控制按钮
        self.auto_ctrl_btn = ctk.CTkButton(row3, text="启动自动发送", width=120,
                                           command=self.toggle_auto_send, fg_color="#f39c12")
        self.auto_ctrl_btn.pack(side="right", padx=5)

    def update_range(self):
        """更新滑块范围（容错处理）"""
        try:
            min_val = float(self.min_entry.get())
            max_val = float(self.max_entry.get())
            if min_val >= max_val:
                messagebox.showwarning("警告", "最小值必须小于最大值！")
                return
            self.slider.configure(from_=min_val, to=max_val)
            # 更新当前值
            current_val = self.slider.get()
            self.val_entry.delete(0, tk.END)
            self.val_entry.insert(0, f"{current_val:.2f}")
        except ValueError:
            messagebox.showerror("错误", "请输入有效的数字！")

    def on_slider_change(self, value):
        """滑块变动事件（修复bug17：手动模式下不自动发送）"""
        # 更新输入框显示
        self.val_entry.delete(0, tk.END)
        self.val_entry.insert(0, f"{value:.2f}")
        
        # 修复bug：只有自动模式下才自动发送，手动模式下仅更新值不发送
        if self.auto_sending and self.send_mode.get() == "auto":
            self.send_data()

    def on_entry_key(self, event):
        """输入框按键事件：超长文本滚动显示"""
        # 获取输入内容长度
        content = self.val_entry.get()
        if len(content) > 10:
            # 超过10个字符时，扩展输入框宽度
            self.val_entry.configure(width=150)
        else:
            self.val_entry.configure(width=80)
        
        # 按回车时同步到滑块
        if event.keysym == "Return":
            try:
                val = float(content)
                min_val = self.slider.cget("from")
                max_val = self.slider.cget("to")
                if val < min_val: val = min_val
                if val > max_val: val = max_val
                self.slider.set(val)
            except ValueError:
                messagebox.showerror("错误", "请输入有效的数字！")

    def on_entry_focus_out(self, event):
        """输入框失去焦点：恢复默认宽度"""
        self.val_entry.configure(width=80)

    def on_mode_change(self):
        """发送模式切换"""
        mode = self.send_mode.get()
        if mode == "manual":
            # 手动模式：停止自动发送，启用手动按钮，禁用自动按钮
            self.auto_sending = False
            self.manual_send_btn.configure(state="normal")
            self.auto_ctrl_btn.configure(state="disabled", text="启动自动发送")
        else:
            # 自动模式：启用自动按钮，手动按钮仍可用
            self.manual_send_btn.configure(state="normal")
            self.auto_ctrl_btn.configure(state="normal")

    def get_formatted_data(self):
        """获取格式化后的发送数据（需求22：特定格式文本）"""
        try:
            val = float(self.val_entry.get())
            format_str = self.format_entry.get() or "{VAL}"
            # 替换{VAL}为实际数值
            data = format_str.replace("{VAL}", f"{val:.2f}")
            # 添加数据名称标识
            name = self.name_entry.get() or "自定义参数"
            return f"[{name}] {data}"
        except:
            return f"[{self.name_entry.get() or '自定义参数'}] 格式错误"

    def send_data(self):
        """发送数据（核心功能）"""
        data = self.get_formatted_data()
        self.controller.send_raw(data)
        self.send_count += 1

    def manual_send(self):
        """手动发送（需求：手动模式）"""
        self.send_data()

    def toggle_auto_send(self):
        """切换自动发送状态（需求：自动模式）"""
        if not self.auto_sending:
            # 启动自动发送
            try:
                self.send_interval = int(self.interval_entry.get())
                self.max_send_times = int(self.times_entry.get())
                if self.send_interval < 10:
                    self.send_interval = 10  # 最小间隔保护
                self.send_count = 0
                self.auto_sending = True
                self.auto_ctrl_btn.configure(text="停止自动发送", fg_color="#e74c3c")
                # 启动自动发送线程
                threading.Thread(target=self.auto_send_thread, daemon=True).start()
            except ValueError:
                messagebox.showerror("错误", "请输入有效的数字参数！")
        else:
            # 停止自动发送
            self.auto_sending = False
            self.auto_ctrl_btn.configure(text="启动自动发送", fg_color="#f39c12")

    def auto_send_thread(self):
        """自动发送线程（支持间隔/次数，需求16）"""
        while self.auto_sending:
            self.send_data()
            
            # 检查发送次数（0=无限次）
            if self.max_send_times > 0 and self.send_count >= self.max_send_times:
                self.auto_sending = False
                self.auto_ctrl_btn.configure(text="启动自动发送", fg_color="#f39c12")
                break
            
            # 等待间隔时间
            time.sleep(self.send_interval / 1000)

# --- 纯文本指令组件 (需求22：特定格式文本发送) ---
class TextCmdComponent(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, border_width=2, border_color="#1F538D", corner_radius=8)
        self.controller = controller
        
        line = ctk.CTkFrame(self, fg_color="transparent")
        line.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(line, text="文本指令:", width=80).pack(side="left", padx=5)
        self.txt_entry = ctk.CTkEntry(line, placeholder_text="如：MOTOR_STOP 或 SPEED=50", width=400)
        self.txt_entry.pack(side="left", padx=10, fill="x", expand=True)
        
        # 发送按钮
        ctk.CTkButton(line, text="发送指令", width=100, fg_color="#2ecc71",
                      command=self.send_text_cmd).pack(side="right", padx=5)
        
        # 清除按钮
        ctk.CTkButton(line, text="清空", width=80, fg_color="#95a5a6",
                      command=lambda: self.txt_entry.delete(0, tk.END)).pack(side="right", padx=5)

    def send_text_cmd(self):
        """发送纯文本指令"""
        cmd = self.txt_entry.get().strip()
        if not cmd:
            messagebox.showwarning("警告", "指令不能为空！")
            return
        self.controller.send_raw(cmd)

# --- 页面3：设置 (保留原有功能 + 新增参数组件功能) ---
class SettingPage(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller
        
        # ========== 原有视觉配置区域 ==========
        ctk.CTkLabel(self, text="🎨 终端视觉中心", font=("KaiTi", 26, "bold")).pack(pady=20)

        # 颜色预览卡片
        card = ctk.CTkFrame(self)
        card.pack(pady=10, padx=40, fill="x")

        # 1. 背景颜色调整
        bg_row = ctk.CTkFrame(card, fg_color="transparent")
        bg_row.pack(fill="x", pady=15, padx=20)
        ctk.CTkLabel(bg_row, text="终端背景颜色:", font=("KaiTi", 16)).pack(side="left")
        self.bg_preview = ctk.CTkButton(bg_row, text="", width=100, command=self.set_bg)
        self.bg_preview.preview_tag = "bg"
        self.bg_preview.configure(fg_color=self.controller.text_bg_color.get())
        self.bg_preview.pack(side="right")

        # 2. 文字颜色调整
        fg_row = ctk.CTkFrame(card, fg_color="transparent")
        fg_row.pack(fill="x", pady=15, padx=20)
        ctk.CTkLabel(fg_row, text="终端文字颜色:", font=("KaiTi", 16)).pack(side="left")
        self.fg_preview = ctk.CTkButton(fg_row, text="", width=100, command=self.set_fg)
        self.fg_preview.preview_tag = "fg"
        self.fg_preview.configure(fg_color=self.controller.text_fg_color.get())
        self.fg_preview.pack(side="right")

        # 3. 字体大小
        font_row = ctk.CTkFrame(card, fg_color="transparent")
        font_row.pack(fill="x", pady=15, padx=20)
        ctk.CTkLabel(font_row, text="字体大小:").pack(side="left")
        self.font_size_label = ctk.CTkLabel(font_row, text=f"{self.controller.font_size.get()}")
        self.font_size_label.pack(side="right", padx=10)
        font_slider = ctk.CTkSlider(font_row, from_=10, to=40, variable=self.controller.font_size,
                                    command=lambda v: self.font_size_label.configure(text=f"{int(float(v))}"))
        font_slider.pack(side="right", fill="x", expand=True, padx=20)

        # 预设按钮
        presets = ctk.CTkFrame(self, fg_color="transparent")
        presets.pack(pady=20)
        ctk.CTkButton(presets, text="黑客绿", fg_color="#1e1e1e", text_color="#00FF00", 
                      command=lambda: self.apply_preset("#1e1e1e", "#00FF00")).pack(side="left", padx=10)
        ctk.CTkButton(presets, text="极客蓝", fg_color="#000000", text_color="#3498DB", 
                      command=lambda: self.apply_preset("#000000", "#3498DB")).pack(side="left", padx=10)
        
        # 分割线
        ctk.CTkLabel(self, text="———————————— 扩展功能区 ————————————", font=("KaiTi", 18)).pack(pady=20)
        
        # ========== 新增：参数组件功能区（和ParamPage一致） ==========
        # 左侧工具栏：添加组件
        tools = ctk.CTkFrame(self, width=180)
        tools.pack(side="left", fill="y", padx=5, pady=5)
        ctk.CTkLabel(tools, text="组件工厂", font=("KaiTi", 18)).pack(pady=10)
        
        ctk.CTkButton(tools, text="+ 自定义参数组件", command=self.add_custom_param).pack(pady=10, padx=10)
        ctk.CTkButton(tools, text="+ 纯文本指令组件", command=self.add_text_cmd).pack(pady=10, padx=10)

        # 右侧内容区：自定义参数组件容器
        self.scroll = ctk.CTkScrollableFrame(self, label_text="自定义参数控制台 (支持自动/手动发送)")
        self.scroll.pack(side="top", fill="both", expand=True, padx=5, pady=5)

        # 下位机反馈显示区
        mon_f = ctk.CTkFrame(self, height=200)
        mon_f.pack(side="bottom", fill="x", padx=5, pady=5)
        ctk.CTkLabel(mon_f, text="📥 下位机反馈显示区:", font=("KaiTi", 14)).pack(anchor="w", padx=10)
        self.feedback_box = ctk.CTkTextbox(mon_f, height=150)
        self.feedback_box.pack(fill="both", expand=True, padx=5, pady=5)
        # 反馈区清除按钮
        ctk.CTkButton(mon_f, text="清除反馈", width=80, 
                      command=lambda: self.feedback_box.delete("1.0", tk.END),
                      fg_color="#95a5a6", hover_color="#7f8c8d"
                     ).pack(side="right", padx=5, pady=5)

    # 原有视觉配置函数
    def set_bg(self):
        c = colorchooser.askcolor(title="选择背景颜色", initialcolor=self.controller.text_bg_color.get())[1]
        if c: 
            self.controller.text_bg_color.set(c)
            self.bg_preview.configure(fg_color=c)

    def set_fg(self):
        c = colorchooser.askcolor(title="选择文字颜色", initialcolor=self.controller.text_fg_color.get())[1]
        if c: 
            self.controller.text_fg_color.set(c)
            self.fg_preview.configure(fg_color=c)

    def apply_preset(self, b, f):
        self.controller.text_bg_color.set(b)
        self.controller.text_fg_color.set(f)
        self.bg_preview.configure(fg_color=b)
        self.fg_preview.configure(fg_color=f)
    
    # 新增：参数组件相关函数
    def add_custom_param(self):
        """添加自定义参数组件"""
        CustomParamComponent(self.scroll, self.controller).pack(fill="x", pady=8, padx=5)

    def add_text_cmd(self):
        """添加纯文本指令组件"""
        TextCmdComponent(self.scroll, self.controller).pack(fill="x", pady=8, padx=5)

if __name__ == "__main__":
    app = MotorApp()
    app.mainloop()