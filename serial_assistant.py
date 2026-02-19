import tkinter as tk
from tkinter import colorchooser, messagebox
import customtkinter as ctk
import serial
import serial.tools.list_ports
import threading
import time
import binascii

ctk.set_appearance_mode("Dark")

# 简化UI线程安全装饰器
def ui_thread_safe(func):
    def wrapper(*args, **kwargs):
        self = args[0]
        ctrl = self.controller if hasattr(self, 'controller') else self
        ctrl.after(0, lambda: func(*args, **kwargs))
    return wrapper

class MotorApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.version = "v1.4.1_Final"
        self.title(f"串口助手_极客翔 ({self.version})")
        
        self.minsize(1000, 700)
        self.geometry("1300x950")
        
        # 基础配置
        self.font_family = tk.StringVar(value="KaiTi")
        self.font_size = tk.IntVar(value=18)
        self.text_bg_color = tk.StringVar(value="#1e1e1e")
        self.text_fg_color = tk.StringVar(value="#00FF00")
        
        self.send_format = tk.StringVar(value="Text")
        self.recv_format = tk.StringVar(value="Text")
        self.send_encoding = tk.StringVar(value="UTF-8")
        self.recv_encoding = tk.StringVar(value="UTF-8")

        self.baudrate = tk.StringVar(value="9600")
        self.databits = tk.StringVar(value="8")
        self.stopbits = tk.StringVar(value="1")
        self.parity = tk.StringVar(value="N-无校验")
        
        # 绑定主题更新
        self.font_size.trace_add("write", lambda *args: self.apply_global_theme())
        self.font_family.trace_add("write", lambda *args: self.apply_global_theme())
        self.text_bg_color.trace_add("write", lambda *args: self.apply_global_theme())
        self.text_fg_color.trace_add("write", lambda *args: self.apply_global_theme())
        self.send_format.trace_add("write", self.on_format_change)
        self.recv_format.trace_add("write", self.on_format_change)

        # 串口相关
        self.ser = None
        self.running = False
        self.receive_thread = None

        # 布局配置
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # 侧边栏
        self.sidebar = ctk.CTkFrame(self, width=80)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.setup_sidebar()

        # 主容器
        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.grid(row=0, column=1, padx=15, pady=15, sticky="nsew")
        self.container.grid_columnconfigure(0, weight=1)
        self.container.grid_rowconfigure(0, weight=1)

        # 页面切换
        self.frames = {}
        for F in (ConsolePage, ParamPage, SettingPage):
            frame = F(parent=self.container, controller=self)
            self.frames[F.__name__] = frame
            frame.grid(row=0, column=0, sticky="nsew")

        self.show_frame("ConsolePage")
        self.on_format_change()
        self.apply_global_theme()

    def setup_sidebar(self):
        """侧边栏按钮"""
        menu = [("📝", "ConsolePage"), ("⚙️", "ParamPage"), ("🎨", "SettingPage")]
        for icon, page in menu:
            ctk.CTkButton(self.sidebar, text=icon, width=60, height=60, font=("Arial", 28),
                          fg_color="transparent", hover_color="#333333",
                          command=lambda p=page: self.show_frame(p)).pack(pady=20)

    def apply_global_theme(self):
        """应用全局主题"""
        bg, fg = self.text_bg_color.get(), self.text_fg_color.get()
        fs, ff = self.font_size.get(), self.font_family.get()
        
        def update_recursive(parent):
            for child in parent.winfo_children():
                if isinstance(child, ctk.CTkTextbox):
                    child.configure(fg_color=bg, text_color=fg, font=(ff, fs))
                elif isinstance(child, tk.Text):
                    child.configure(bg=bg, fg=fg, font=(ff, fs))
                elif isinstance(child, ctk.CTkLabel):
                    child.configure(text_color=fg, font=(ff, fs))
                elif isinstance(child, ctk.CTkButton):
                    child.configure(font=(ff, fs))
                elif isinstance(child, ctk.CTkEntry):
                    child.configure(fg_color=bg, text_color=fg, font=(ff, fs))
                elif isinstance(child, ctk.CTkOptionMenu):
                    child.configure(font=(ff, fs))
                elif isinstance(child, ctk.CTkRadioButton):
                    child.configure(font=(ff, fs))
                if hasattr(child, "preview_tag"):
                    child.configure(fg_color=bg if child.preview_tag=="bg" else fg)
                if child.winfo_children():
                    update_recursive(child)
        update_recursive(self)

    def on_format_change(self, *args):
        """格式变更处理"""
        cf = self.frames['ConsolePage']
        cf.send_encoding_opt.configure(state="normal" if self.send_format.get() == "Text" else "disabled")
        cf.recv_encoding_opt.configure(state="normal" if self.recv_format.get() == "Text" else "disabled")

    def show_frame(self, page_name):
        """切换页面"""
        self.frames[page_name].tkraise()
        self.apply_global_theme()

    def hex_to_bytes(self, hex_str):
        """HEX转字节"""
        h = hex_str.replace(" ", "").upper()
        if len(h) % 2 != 0:
            h = "0" + h
        return binascii.unhexlify(h)

    def bytes_to_hex(self, b):
        """字节转HEX"""
        return binascii.hexlify(b).upper().decode().replace("", " ").strip()

    def send_raw(self, data):
        """发送原始数据"""
        if not self.ser or not self.ser.is_open:
            messagebox.showwarning("提示", "请先打开串口")
            return
        
        if self.send_format.get() == "Text":
            b = data.encode(self.send_encoding.get(), errors="ignore")
        else:
            b = self.hex_to_bytes(data)
        
        self.ser.write(b)
        txt = f"[发送({self.send_encoding.get()})] {data}\n" if self.send_format.get() == "Text" else \
              f"[发送(HEX)] {self.bytes_to_hex(b)}\n"
        self._update_textbox(self.frames['ParamPage'].feedback_box, txt)

    @ui_thread_safe
    def _update_textbox(self, tb, s):
        """更新文本框"""
        tb.insert("end", s)
        tb.see("end")

    def clear_all_terminal_text(self):
        """清空所有终端"""
        self.frames['ConsolePage'].recv_box.delete("1.0", "end")
        self.frames['ConsolePage'].send_box.delete("1.0", "end")
        self.frames['ParamPage'].feedback_box.delete("1.0", "end")
        messagebox.showinfo("成功", "已清空所有终端")

# ====================== 串口页面（核心修复：移除weight参数） ======================
class ConsolePage(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller

        # 串口配置栏
        cfg_top = ctk.CTkFrame(self)
        cfg_top.pack(fill="x", pady=5)

        ctk.CTkLabel(cfg_top, text="串口号：", width=60).pack(side="left", padx=2)
        self.port_sel = ctk.CTkOptionMenu(cfg_top, values=self.get_serial_ports(), width=100)
        self.port_sel.pack(side="left", padx=5)
        ctk.CTkButton(cfg_top, text="刷新", width=60, command=self.refresh_serial_ports).pack(side="left", padx=5)

        # 串口参数
        ctk.CTkLabel(cfg_top, text="波特率：", width=60).pack(side="left", padx=2)
        ctk.CTkOptionMenu(cfg_top, values=["9600","19200","38400","57600","115200","230400"],
                          variable=controller.baudrate, width=100).pack(side="left", padx=5)

        ctk.CTkLabel(cfg_top, text="数据位：", width=60).pack(side="left", padx=2)
        ctk.CTkOptionMenu(cfg_top, values=["5","6","7","8"],
                          variable=controller.databits, width=80).pack(side="left", padx=5)

        ctk.CTkLabel(cfg_top, text="停止位：", width=60).pack(side="left", padx=2)
        ctk.CTkOptionMenu(cfg_top, values=["1","1.5","2"],
                          variable=controller.stopbits, width=80).pack(side="left", padx=5)

        ctk.CTkLabel(cfg_top, text="校验位：", width=60).pack(side="left", padx=2)
        ctk.CTkOptionMenu(cfg_top, values=["N-无校验", "E-偶校验", "O-奇校验"],
                          variable=controller.parity, width=100).pack(side="left", padx=5)

        self.btn_open = ctk.CTkButton(cfg_top, text="打开串口", width=100, command=self.toggle_ser)
        self.btn_open.pack(side="left", padx=10)

        # 清除按钮
        ctk.CTkButton(cfg_top, text="清除所有终端", width=100, command=controller.clear_all_terminal_text,
                      fg_color="#8e44ad").pack(side="right", padx=5)
        ctk.CTkButton(cfg_top, text="清除接收", width=80,
                      command=lambda: self.recv_box.delete("1.0", "end")).pack(side="right", padx=5)

        # 格式编码配置
        cfg_bottom = ctk.CTkFrame(self)
        cfg_bottom.pack(fill="x", pady=5)
        ctk.CTkLabel(cfg_bottom, text="接收格式：", width=80).pack(side="left", padx=5)
        ctk.CTkOptionMenu(cfg_bottom, values=["Text","HEX"], variable=controller.recv_format, width=80).pack(side="left", padx=2)
        ctk.CTkLabel(cfg_bottom, text="编码：", width=50).pack(side="left")
        self.recv_encoding_opt = ctk.CTkOptionMenu(cfg_bottom, values=["UTF-8","GBK"], variable=controller.recv_encoding, width=80)
        self.recv_encoding_opt.pack(side="left", padx=5)

        ctk.CTkLabel(cfg_bottom, text="发送格式：", width=80).pack(side="left", padx=20)
        ctk.CTkOptionMenu(cfg_bottom, values=["Text","HEX"], variable=controller.send_format, width=80).pack(side="left", padx=2)
        ctk.CTkLabel(cfg_bottom, text="编码：", width=50).pack(side="left")
        self.send_encoding_opt = ctk.CTkOptionMenu(cfg_bottom, values=["UTF-8","GBK"], variable=controller.send_encoding, width=80)
        self.send_encoding_opt.pack(side="left", padx=5)

        # ====================== 核心修复：移除weight参数 ======================
        # 原生tkinter.PanedWindow仅保留基础属性，去掉所有无效参数
        self.paned = tk.PanedWindow(self, orient="vertical", sashwidth=10, bg="#333333", bd=0)
        self.paned.pack(fill="both", expand=True, padx=5, pady=5)

        # 接收区（仅add，无weight）
        self.recv_box = ctk.CTkTextbox(self.paned)
        self.paned.add(self.recv_box)

        # 发送区（仅add，无weight）
        send_frame = ctk.CTkFrame(self.paned)
        self.paned.add(send_frame)

        self.send_box = ctk.CTkTextbox(send_frame)
        self.send_box.pack(side="left", fill="both", expand=True, padx=5, pady=5)

        btn_frame = ctk.CTkFrame(send_frame, fg_color="transparent", width=100)
        btn_frame.pack(side="right", fill="y", padx=5, pady=5)

        ctk.CTkButton(btn_frame, text="发送", width=80,
                      command=lambda: controller.send_raw(self.send_box.get("1.0", "end-1c"))
                     ).pack(side="top", pady=5)
        ctk.CTkButton(btn_frame, text="清除发送", width=80, fg_color="#e74c3c",
                      command=lambda: self.send_box.delete("1.0", "end")
                     ).pack(side="top", pady=5)

    def refresh_serial_ports(self):
        """刷新串口列表"""
        ports = self.get_serial_ports()
        self.port_sel.configure(values=ports)
        if ports:
            self.port_sel.set(ports[0])

    def get_serial_ports(self):
        """获取串口列表"""
        return [p.device for p in serial.tools.list_ports.comports()] or ["COM1","COM2","COM3"]

    def toggle_ser(self):
        """打开/关闭串口"""
        if self.controller.ser and self.controller.ser.is_open:
            # 关闭串口
            self.controller.running = False
            self.controller.ser.close()
            self.btn_open.configure(text="打开串口")
            messagebox.showinfo("成功", "串口已关闭")
        else:
            # 打开串口
            s = self.controller
            b = int(s.baudrate.get())
            d = int(s.databits.get())
            st = {"1":serial.STOPBITS_ONE, "1.5":serial.STOPBITS_ONE_POINT_FIVE, "2":serial.STOPBITS_TWO}[s.stopbits.get()]
            parity_str = s.parity.get()[0]
            p = {"N":serial.PARITY_NONE,"E":serial.PARITY_EVEN,"O":serial.PARITY_ODD}[parity_str]

            self.controller.ser = serial.Serial(
                port=self.port_sel.get(), 
                baudrate=b, 
                bytesize=d, 
                stopbits=st, 
                parity=p, 
                timeout=0.1
            )
            self.btn_open.configure(text="关闭串口")
            self.controller.running = True
            self.controller.receive_thread = threading.Thread(target=self.recv_thread, daemon=True)
            self.controller.receive_thread.start()
            messagebox.showinfo("成功", f"串口已打开\n{b} 波特 | {d}数据位 | {s.stopbits.get()}停止位 | {s.parity.get()}")

    def recv_thread(self):
        """接收线程"""
        while self.controller.running and self.controller.ser and self.controller.ser.is_open:
            if self.controller.ser.in_waiting > 0:
                b = self.controller.ser.read(self.controller.ser.in_waiting)
                if self.controller.recv_format.get() == "Text":
                    e = self.controller.recv_encoding.get()
                    t = b.decode(e, errors="ignore")
                    head = f"[接收({e})] "
                else:
                    t = self.controller.bytes_to_hex(b)
                    head = "[接收(HEX)] "
                self._update(head + t + "\n")
            time.sleep(0.01)

    @ui_thread_safe
    def _update(self, s):
        """更新接收显示"""
        self.recv_box.insert("end", s)
        self.recv_box.see("end")
        self.controller.frames['ParamPage'].feedback_box.insert("end", s)
        self.controller.frames['ParamPage'].feedback_box.see("end")

# ====================== 参数页面 ======================
class ParamPage(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller
        
        # 工具区
        tools = ctk.CTkFrame(self, width=180)
        tools.pack(side="left", fill="y", padx=5, pady=5)
        ctk.CTkLabel(tools, text="组件工厂", font=("KaiTi", 18)).pack(pady=10)
        ctk.CTkButton(tools, text="+ 自定义参数组件", command=self.add_p).pack(pady=10, padx=10)
        ctk.CTkButton(tools, text="+ 纯文本指令组件", command=self.add_t).pack(pady=10, padx=10)

        # 滚动面板
        self.scroll = ctk.CTkScrollableFrame(self, label_text="自定义参数控制台")
        self.scroll.pack(side="top", fill="both", expand=True, padx=5, pady=5)

        # 反馈区
        mon = ctk.CTkFrame(self)
        mon.pack(side="bottom", fill="x", padx=5, pady=5)
        ctk.CTkLabel(mon, text="📥 下位机反馈显示区:", font=("KaiTi",14)).pack(anchor="w", padx=10)
        self.feedback_box = ctk.CTkTextbox(mon, height=150)
        self.feedback_box.pack(fill="both", expand=True, padx=5, pady=5)
        ctk.CTkButton(mon, text="清除反馈", width=80, command=lambda: self.feedback_box.delete("1.0","end")).pack(side="right", padx=5)

    def add_p(self):
        """添加参数组件"""
        CustomParamComponent(self.scroll, self.controller).pack(fill="x", pady=8, padx=5)
        
    def add_t(self):
        """添加文本指令组件"""
        TextCmdComponent(self.scroll, self.controller).pack(fill="x", pady=8, padx=5)

class CustomParamComponent(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, border_width=2, border_color="#3498DB", corner_radius=8)
        self.controller = controller
        self.auto_sending = False

        # 第一行：名称和格式
        row1 = ctk.CTkFrame(self, fg_color="transparent")
        row1.pack(fill="x", padx=10, pady=8)
        ctk.CTkLabel(row1, text="数据名称:", width=80).pack(side="left")
        self.name_entry = ctk.CTkEntry(row1, placeholder_text="如：电机速度", width=150)
        self.name_entry.pack(side="left", padx=5)
        
        ctk.CTkLabel(row1, text="协议格式:", width=80).pack(side="left")
        self.format_entry = ctk.CTkEntry(row1, placeholder_text="如：SPEED={VAL}", width=200)
        self.format_entry.pack(side="left", padx=5)
        
        ctk.CTkButton(row1, text="🗑️", width=30, fg_color="#e74c3c", command=self.destroy).pack(side="right", padx=5)

        # 第二行：数值范围和滑块
        row2 = ctk.CTkFrame(self, fg_color="transparent")
        row2.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(row2, text="数值范围:", width=80).pack(side="left")
        self.min_entry = ctk.CTkEntry(row2, width=80); self.min_entry.insert(0,"0"); self.min_entry.pack(side="left", padx=2)
        ctk.CTkLabel(row2, text="-").pack(side="left")
        self.max_entry = ctk.CTkEntry(row2, width=80); self.max_entry.insert(0,"100"); self.max_entry.pack(side="left", padx=2)
        ctk.CTkButton(row2, text="更新范围", width=80, command=self.update_range).pack(side="left", padx=5)
        self.slider = ctk.CTkSlider(row2, from_=0, to=100, command=self.on_slide)
        self.slider.pack(side="left", fill="x", expand=True, padx=10)
        self.val_entry = ctk.CTkEntry(row2, width=80); self.val_entry.insert(0,"0.00"); self.val_entry.pack(side="left", padx=5)

        # 第三行：发送模式
        row3 = ctk.CTkFrame(self, fg_color="transparent")
        row3.pack(fill="x", padx=10, pady=8)
        self.mode = ctk.StringVar(value="manual")
        ctk.CTkRadioButton(row3, text="手动", variable=self.mode, value="manual", command=self.switch_mode).pack(side="left", padx=10)
        ctk.CTkRadioButton(row3, text="自动", variable=self.mode, value="auto", command=self.switch_mode).pack(side="left", padx=10)
        ctk.CTkLabel(row3, text="间隔(ms):", width=100).pack(side="left")
        self.interval = ctk.CTkEntry(row3, width=80); self.interval.insert(0,"100"); self.interval.pack(side="left", padx=5)
        ctk.CTkLabel(row3, text="次数(0=无限):", width=120).pack(side="left")
        self.times = ctk.CTkEntry(row3, width=80); self.times.insert(0,"0"); self.times.pack(side="left", padx=5)
        self.btn_manual = ctk.CTkButton(row3, text="手动发送", width=100, fg_color="#2ecc71", command=self.manual_send)
        self.btn_manual.pack(side="right", padx=5)
        self.btn_auto = ctk.CTkButton(row3, text="启动自动", width=120, fg_color="#f39c12", command=self.toggle_auto)
        self.btn_auto.pack(side="right", padx=5)
        self.btn_auto.configure(state="disabled")

    def update_range(self):
        """更新滑块范围"""
        mi, ma = float(self.min_entry.get()), float(self.max_entry.get())
        if mi >= ma: 
            messagebox.showwarning("警告","最小值<最大值")
            return
        self.slider.configure(from_=mi, to=ma)
        self.val_entry.delete(0, "end")
        self.val_entry.insert(0, f"{self.slider.get():.2f}")

    def on_slide(self, v):
        """滑块值变更"""
        self.val_entry.delete(0,"end")
        self.val_entry.insert(0,f"{v:.2f}")
        if self.auto_sending: 
            self.send()

    def switch_mode(self):
        """切换发送模式"""
        if self.mode.get() == "manual":
            self.auto_sending = False
            self.btn_auto.configure(state="disabled", text="启动自动")
        else:
            self.btn_auto.configure(state="normal")

    def send(self):
        """发送参数"""
        fmt = self.format_entry.get() or "{VAL}"
        val = float(self.val_entry.get())
        s = fmt.replace("{VAL}", f"{val:.2f}")
        self.controller.send_raw(f"[{self.name_entry.get() or '参数'}] {s}")

    def manual_send(self):
        """手动发送"""
        self.send()

    def toggle_auto(self):
        """启动/停止自动发送"""
        if not self.auto_sending:
            itv = int(self.interval.get())
            tms = int(self.times.get())
            if itv <10: itv=10
            self.auto_sending = True
            self.btn_auto.configure(text="停止自动", fg_color="#e74c3c")
            threading.Thread(target=self.auto_task, args=(itv, tms), daemon=True).start()
        else:
            self.auto_sending = False
            self.btn_auto.configure(text="启动自动", fg_color="#f39c12")

    def auto_task(self, itv, tms):
        """自动发送任务"""
        cnt=0
        while self.auto_sending:
            self.send()
            cnt +=1
            if tms>0 and cnt>=tms:
                self.auto_sending=False
                self.controller.after(0, lambda: self.btn_auto.configure(text="启动自动", fg_color="#f39c12"))
                break
            time.sleep(itv/1000)

class TextCmdComponent(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, border_width=2, border_color="#1F538D", corner_radius=8)
        self.controller = controller
        
        line = ctk.CTkFrame(self, fg_color="transparent")
        line.pack(fill="x", padx=10, pady=10)
        ctk.CTkLabel(line, text="文本指令:", width=80).pack(side="left", padx=5)
        self.e = ctk.CTkEntry(line, placeholder_text="如：MOTOR_STOP", width=400)
        self.e.pack(side="left", padx=10, fill="x", expand=True)
        ctk.CTkButton(line, text="发送", width=100, fg_color="#2ecc71", command=self.send).pack(side="right", padx=5)
        ctk.CTkButton(line, text="清空", width=80, command=lambda: self.e.delete(0,"end")).pack(side="right", padx=5)

    def send(self):
        """发送文本指令"""
        t = self.e.get().strip()
        if not t: 
            messagebox.showwarning("警告","不能为空")
            return
        self.controller.send_raw(t)

# ====================== 设置页面 ======================
class SettingPage(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller
        
        ctk.CTkLabel(self, text="🎨 视觉设置", font=("KaiTi",26,"bold")).pack(pady=20)
        card = ctk.CTkFrame(self)
        card.pack(pady=10, padx=40, fill="x")

        # 背景色设置
        bg_row = ctk.CTkFrame(card, fg_color="transparent")
        bg_row.pack(fill="x", pady=15, padx=20)
        ctk.CTkLabel(bg_row, text="背景色:", font=("KaiTi",16)).pack(side="left")
        self.bg_btn = ctk.CTkButton(bg_row, text="", width=100, command=self.set_bg)
        self.bg_btn.preview_tag="bg"
        self.bg_btn.configure(fg_color=controller.text_bg_color.get())
        self.bg_btn.pack(side="right")

        # 文字色设置
        fg_row = ctk.CTkFrame(card, fg_color="transparent")
        fg_row.pack(fill="x", pady=15, padx=20)
        ctk.CTkLabel(fg_row, text="文字色:", font=("KaiTi",16)).pack(side="left")
        self.fg_btn = ctk.CTkButton(fg_row, text="", width=100, command=self.set_fg)
        self.fg_btn.preview_tag="fg"
        self.fg_btn.configure(fg_color=controller.text_fg_color.get())
        self.fg_btn.pack(side="right")

        # 字体设置
        font_row = ctk.CTkFrame(card, fg_color="transparent")
        font_row.pack(fill="x", pady=15, padx=20)
        ctk.CTkLabel(font_row, text="字体:", font=("KaiTi",16)).pack(side="left", padx=5)
        ctk.CTkOptionMenu(font_row, values=["KaiTi","Arial","SimHei","Microsoft YaHei"],
                          variable=controller.font_family, width=120).pack(side="left", padx=5)
        ctk.CTkLabel(font_row, text="大小:", font=("KaiTi",16)).pack(side="left", padx=10)
        self.fs_lbl = ctk.CTkLabel(font_row, text=str(controller.font_size.get()), font=("KaiTi",16))
        self.fs_lbl.pack(side="right", padx=10)
        self.slider = ctk.CTkSlider(font_row, from_=10, to=40, variable=controller.font_size, command=self.on_font_change)
        self.slider.pack(side="right", fill="x", expand=True, padx=20)
        self.slider.set(controller.font_size.get())

        # 预设样式
        pre = ctk.CTkFrame(self, fg_color="transparent")
        pre.pack(pady=20)
        ctk.CTkButton(pre, text="黑客绿", fg_color="#1e1e1e", text_color="#0f0",
                      command=lambda: self.preset("#1e1e1e","#00ff00")).pack(side="left", padx=10)
        ctk.CTkButton(pre, text="极客蓝", fg_color="#000", text_color="#3498db",
                      command=lambda: self.preset("#000","#3498db")).pack(side="left", padx=10)

    def on_font_change(self, v):
        """字体大小变更"""
        self.fs_lbl.configure(text=str(int(v)))
        self.controller.apply_global_theme()

    def set_bg(self):
        """设置背景色"""
        c = colorchooser.askcolor(initialcolor=self.controller.text_bg_color.get())[1]
        if c: 
            self.controller.text_bg_color.set(c)
            self.bg_btn.configure(fg_color=c)
            
    def set_fg(self):
        """设置文字色"""
        c = colorchooser.askcolor(initialcolor=self.controller.text_fg_color.get())[1]
        if c: 
            self.controller.text_fg_color.set(c)
            self.fg_btn.configure(fg_color=c)
            
    def preset(self,b,f):
        """应用预设样式"""
        self.controller.text_bg_color.set(b)
        self.controller.text_fg_color.set(f)

if __name__ == "__main__":
    app = MotorApp()
    
    def on_close():
        """关闭程序"""
        if app.ser and app.ser.is_open:
            app.running=False
            app.ser.close()
        app.destroy()
        
    app.protocol("WM_DELETE_WINDOW", on_close)
    app.mainloop()