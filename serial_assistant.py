import tkinter as tk
from tkinter import font
import customtkinter as ctk
import serial
import serial.tools.list_ports
import threading
import time

# 全局样式配置
ctk.set_appearance_mode("Dark")

class MotorApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("串口助手_极客翔 (实时预览版)")
        self.geometry("1280x900")
        self.minsize(1000, 750)
        
        # --- 字体配置变量 ---
        self.font_family = tk.StringVar(value="Microsoft YaHei") 
        self.font_size = tk.IntVar(value=14)
        self.font_weight = tk.StringVar(value="normal") 
        
        # 绑定变量追踪，实现实时更新
        self.font_family.trace_add("write", lambda *args: self.update_global_font())
        self.font_size.trace_add("write", lambda *args: self.update_global_font())
        self.font_weight.trace_add("write", lambda *args: self.update_global_font())

        self.custom_font = ctk.CTkFont(family=self.font_family.get(), size=self.font_size.get(), weight=self.font_weight.get())

        self.ser = None
        self.running = False

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # 1. 响应式侧边栏
        self.sidebar = ctk.CTkFrame(self, corner_radius=0, width=80)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.setup_sidebar()

        # 2. 页面容器
        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.grid(row=0, column=1, padx=15, pady=15, sticky="nsew")
        self.container.grid_columnconfigure(0, weight=1)
        self.container.grid_rowconfigure(0, weight=1)

        self.frames = {}
        for F in (ConsolePage, ParamPage, SettingPage):
            page_name = F.__name__
            frame = F(parent=self.container, controller=self)
            self.frames[page_name] = frame
            frame.grid(row=0, column=0, sticky="nsew")

        self.show_frame("ConsolePage")

    def setup_sidebar(self):
        self.nav_btns = []
        menu_items = [("📝", "ConsolePage"), ("⚙️", "ParamPage"), ("🎨", "SettingPage")]
        for icon, page in menu_items:
            btn = ctk.CTkButton(self.sidebar, text=icon, width=60, height=60, 
                                 fg_color="transparent", hover_color="#333333",
                                 font=("Arial", 24),
                                 command=lambda p=page: self.show_frame(p))
            btn.pack(pady=20, padx=10)
            self.nav_btns.append(btn)

    def update_global_font(self):
        """核心修复：变量一变，立即触发全窗口重绘"""
        try:
            new_weight = self.font_weight.get()
            new_family = self.font_family.get()
            new_size = self.font_size.get()
            self.custom_font.configure(family=new_family, size=new_size, weight=new_weight)
            self.refresh_ui_fonts(self)
        except:
            pass # 避免初始化时变量未就绪报错

    def refresh_ui_fonts(self, parent):
        for child in parent.winfo_children():
            try:
                # 更新 CustomTkinter 组件的字体
                if hasattr(child, "configure") and "font" in child.keys():
                    child.configure(font=self.custom_font)
                # 特殊处理：Textbox 等组件内部可能需要单独配置
                if isinstance(child, ctk.CTkTextbox):
                    child.configure(font=(self.font_family.get(), self.font_size.get()))
            except: pass
            self.refresh_ui_fonts(child)

    def show_frame(self, page_name):
        self.frames[page_name].tkraise()

    def send_raw(self, data_str):
        if self.ser and self.ser.is_open:
            try:
                self.ser.write(data_str.encode('utf-8'))
            except: pass

# --- 页面1：串口助手 ---
class ConsolePage(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller
        f_obj = self.controller.custom_font

        cfg_bar = ctk.CTkFrame(self, corner_radius=10)
        cfg_bar.pack(fill="x", padx=5, pady=5)
        
        l1 = ctk.CTkFrame(cfg_bar, fg_color="transparent"); l1.pack(fill="x", pady=5, padx=10)
        ctk.CTkLabel(l1, text="端口:").pack(side="left", padx=5)
        self.port_sel = ctk.CTkOptionMenu(l1, values=self.get_ports(), width=140)
        self.port_sel.pack(side="left", padx=2)
        ctk.CTkButton(l1, text="🔄", width=40, command=self.refresh_ports).pack(side="left", padx=5)
        
        ctk.CTkLabel(l1, text="波特率:").pack(side="left", padx=10)
        self.baud_sel = ctk.CTkOptionMenu(l1, values=["9600", "115200", "921600"], width=110)
        self.baud_sel.set("115200"); self.baud_sel.pack(side="left", padx=5)
        
        self.btn_ser = ctk.CTkButton(l1, text="开启连接", fg_color="#27AE60", command=self.toggle_ser)
        self.btn_ser.pack(side="right", padx=10)

        self.paned = tk.PanedWindow(self, orient=tk.VERTICAL, bg="#2b2b2b", sashwidth=4)
        self.paned.pack(fill="both", expand=True, pady=10)

        self.recv_frame = ctk.CTkFrame(self.paned, fg_color="#1e1e1e")
        ctk.CTkLabel(self.recv_frame, text=" 📥 接收终端", text_color="#AAAAAA").pack(anchor="w", padx=10)
        self.recv_box = ctk.CTkTextbox(self.recv_frame, font=("Consolas", 14), text_color="#00FF00")
        self.recv_box.pack(fill="both", expand=True, padx=5, pady=5); self.paned.add(self.recv_frame, height=450)

        self.send_frame = ctk.CTkFrame(self.paned, fg_color="#1e1e1e")
        ctk.CTkLabel(self.send_frame, text=" 📤 发送指令", text_color="#AAAAAA").pack(anchor="w", padx=10)
        self.send_box = ctk.CTkTextbox(self.send_frame, font=("Consolas", 14))
        self.send_box.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        ctk.CTkButton(self.send_frame, text="手动发送", width=100, command=self.manual_send).pack(side="right", fill="y", padx=5, pady=5)
        self.paned.add(self.send_frame, height=150)

    def get_ports(self):
        return [p.device for p in serial.tools.list_ports.comports()] or ["无设备"]

    def refresh_ports(self):
        p = self.get_ports(); self.port_sel.configure(values=p); self.port_sel.set(p[0])

    def toggle_ser(self):
        c = self.controller
        if not c.running:
            try:
                c.ser = serial.Serial(port=self.port_sel.get(), baudrate=int(self.baud_sel.get()), timeout=0.1)
                c.running = True
                self.btn_ser.configure(text="关闭串口", fg_color="#C0392B")
                threading.Thread(target=self.listen, daemon=True).start()
            except Exception as e: self.recv_box.insert("end", f"⚠️ 连接失败: {e}\n")
        else:
            c.running = False; 
            if c.ser: c.ser.close()
            self.btn_ser.configure(text="开启连接", fg_color="#27AE60")

    def listen(self):
        while self.controller.running:
            if self.controller.ser and self.controller.ser.in_waiting:
                try:
                    data = self.controller.ser.read(self.controller.ser.in_waiting).decode('utf-8', errors='ignore')
                    self.recv_box.insert("end", data); self.recv_box.see("end")
                    self.controller.frames["ParamPage"].update_monitor(data)
                except: break

    def manual_send(self):
        self.controller.send_raw(self.send_box.get("1.0", "end-1c"))

# --- 页面2：调优 ---
class ParamPage(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller
        
        self.paned = tk.PanedWindow(self, orient=tk.VERTICAL, bg="#2b2b2b", sashwidth=4)
        self.paned.pack(fill="both", expand=True)

        self.top_frame = ctk.CTkFrame(self.paned, fg_color="transparent")
        t_bar = ctk.CTkFrame(self.top_frame, corner_radius=10); t_bar.pack(fill="x", padx=5, pady=5)
        ctk.CTkLabel(t_bar, text="🚀 参数实时调控").pack(side="left", padx=15)
        ctk.CTkButton(t_bar, text="+ 文本组件", fg_color="#3498DB", command=self.add_text_item).pack(side="right", padx=10, pady=5)
        ctk.CTkButton(t_bar, text="+ 滑块组件", fg_color="#E67E22", command=self.add_param_item).pack(side="right", padx=5)
        
        self.scroll = ctk.CTkScrollableFrame(self.top_frame, label_text="控制面板")
        self.scroll.pack(fill="both", expand=True, padx=5, pady=5)
        self.paned.add(self.top_frame, height=550)

        self.bottom_frame = ctk.CTkFrame(self.paned, fg_color="#1a1a1a")
        ctk.CTkLabel(self.bottom_frame, text=" 📊 监控反馈:").pack(anchor="w", padx=15, pady=5)
        self.monitor_text = ctk.CTkTextbox(self.bottom_frame, font=("Consolas", 12), text_color="#3498DB")
        self.monitor_text.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.paned.add(self.bottom_frame)

    def add_param_item(self): ParamComponent(self.scroll, self.controller).pack(fill="x", pady=5, padx=5)
    def add_text_item(self): TextPacketComponent(self.scroll, self.controller).pack(fill="x", pady=5, padx=5)
    def update_monitor(self, text): self.monitor_text.insert("end", text); self.monitor_text.see("end")

# --- 页面3：实时设置页面 (核心改进) ---
class SettingPage(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller
        
        ctk.CTkLabel(self, text="🎨 界面实时调整", font=("Microsoft YaHei", 28, "bold")).pack(pady=20)
        
        # 实时预览区域
        preview_card = ctk.CTkFrame(self, fg_color="#1A1A1A", border_width=1, border_color="#333333")
        preview_card.pack(pady=10, padx=40, fill="x")
        ctk.CTkLabel(preview_card, text="实时预览文字效果: Hello World 123", text_color="#27AE60").pack(pady=20)

        card = ctk.CTkFrame(self, corner_radius=15); card.pack(pady=10, padx=40, fill="x")
        
        # 字体选择
        row1 = ctk.CTkFrame(card, fg_color="transparent"); row1.pack(fill="x", padx=20, pady=15)
        ctk.CTkLabel(row1, text="字体家族:").pack(side="left", padx=10)
        available_fonts = [f for f in ["Microsoft YaHei", "SimHei", "Arial", "Consolas", "Courier New"] if f in list(font.families())]
        ctk.CTkOptionMenu(row1, values=available_fonts, variable=self.controller.font_family).pack(side="right", padx=10)

        # 粗细选择
        row_w = ctk.CTkFrame(card, fg_color="transparent"); row_w.pack(fill="x", padx=20, pady=15)
        ctk.CTkLabel(row_w, text="字体粗细:").pack(side="left", padx=10)
        ctk.CTkOptionMenu(row_w, values=["normal", "bold"], variable=self.controller.font_weight).pack(side="right", padx=10)

        # 大小选择
        row2 = ctk.CTkFrame(card, fg_color="transparent"); row2.pack(fill="x", padx=20, pady=15)
        ctk.CTkLabel(row2, text="字体大小:").pack(side="left", padx=10)
        ctk.CTkSlider(row2, from_=10, to=24, number_of_steps=14, variable=self.controller.font_size).pack(side="right", padx=10, fill="x", expand=True)

        ctk.CTkLabel(self, text="* 操作下方控件将立即应用至全程序", text_color="#555555").pack(pady=10)

# --- 组件：滑块 (代码保持一致) ---
class ParamComponent(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, corner_radius=10, border_width=1, border_color="#3d3d3d")
        self.controller = controller; self.is_auto = False
        f_obj = self.controller.custom_font

        l1 = ctk.CTkFrame(self, fg_color="transparent"); l1.pack(fill="x", padx=10, pady=5)
        self.name_e = ctk.CTkEntry(l1, placeholder_text="参数名", width=100).pack(side="left", padx=2)
        self.header_e = ctk.CTkEntry(l1, placeholder_text="指令头", width=80); self.header_e.pack(side="left", padx=2)
        
        r_f = ctk.CTkFrame(l1, fg_color="transparent"); r_f.pack(side="left", padx=10)
        ctk.CTkLabel(r_f, text="范围:").pack(side="left")
        self.min_e = ctk.CTkEntry(r_f, width=50); self.min_e.insert(0, "0"); self.min_e.pack(side="left", padx=2)
        self.max_e = ctk.CTkEntry(r_f, width=50); self.max_e.insert(0, "100"); self.max_e.pack(side="left", padx=2)
        self.min_e.bind("<FocusOut>", self.update_range); self.max_e.bind("<FocusOut>", self.update_range)

        l2 = ctk.CTkFrame(self, fg_color="transparent"); l2.pack(fill="x", padx=10, pady=5)
        self.slider = ctk.CTkSlider(l2, from_=0, to=100, command=self.on_slide); self.slider.pack(side="left", fill="x", expand=True)
        self.val_var = tk.StringVar(value="0.00")
        ctk.CTkEntry(l2, textvariable=self.val_var, width=70).pack(side="left", padx=5)

        l3 = ctk.CTkFrame(self, fg_color="transparent"); l3.pack(fill="x", padx=10, pady=5)
        self.t_val = ctk.CTkEntry(l3, width=55); self.t_val.insert(0, "100"); self.t_val.pack(side="left")
        self.u_sel = ctk.CTkOptionMenu(l3, values=["ms", "s"], width=70); self.u_sel.set("ms"); self.u_sel.pack(side="left", padx=2)
        self.mode_sel = ctk.CTkOptionMenu(l3, values=["手动模式", "自动模式"], width=100, command=self.toggle_mode); self.mode_sel.pack(side="left", padx=10)
        ctk.CTkButton(l3, text="发送", width=80, command=self.do_send).pack(side="left")
        ctk.CTkButton(l3, text="🗑", width=40, fg_color="#C0392B", command=self.destroy).pack(side="right")

    def update_range(self, e):
        try: self.slider.configure(from_=float(self.min_e.get()), to=float(self.max_e.get()))
        except: pass
    def on_slide(self, v): self.val_var.set(f"{v:.2f}")
    def toggle_mode(self, m):
        self.is_auto = (m == "自动模式")
        if self.is_auto: threading.Thread(target=self.worker, daemon=True).start()
    def worker(self):
        while self.is_auto:
            try:
                interval = float(self.t_val.get()) / (1000 if self.u_sel.get()=="ms" else 1)
                self.do_send(); time.sleep(max(0.01, interval))
            except: time.sleep(1)
    def do_send(self):
        if self.header_e.get(): self.controller.send_raw(f"{self.header_e.get()}{self.val_var.get()}\n")

# --- 组件：文本包 ---
class TextPacketComponent(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, corner_radius=10, border_width=1, border_color="#3498DB")
        self.controller = controller; self.is_auto = False; self.is_collapsed = False
        f_obj = self.controller.custom_font

        self.header_row = ctk.CTkFrame(self, fg_color="transparent")
        self.header_row.pack(fill="x", padx=10, pady=5)
        self.fold_btn = ctk.CTkButton(self.header_row, text="🔼 收起", width=60, fg_color="#5D6D7E", command=self.toggle_fold); self.fold_btn.pack(side="left", padx=5)
        self.name_e = ctk.CTkEntry(self.header_row, placeholder_text="指令名", width=120); self.name_e.pack(side="left", padx=5)
        self.fmt_sel = ctk.CTkOptionMenu(self.header_row, values=["原始文本", "HEX发送", "加\\n"], width=100); self.fmt_sel.pack(side="left", padx=5)
        ctk.CTkButton(self.header_row, text="🗑", width=40, fg_color="#C0392B", command=self.destroy).pack(side="right")
        self.btn_send = ctk.CTkButton(self.header_row, text="立即发送", width=80, command=self.do_send); self.btn_send.pack(side="right", padx=5)

        self.content_area = ctk.CTkFrame(self, fg_color="transparent")
        self.content_area.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.txt = ctk.CTkTextbox(self.content_area, height=100, font=("Consolas", 13), border_width=1); self.txt.pack(side="left", expand=True, fill="both", padx=5)
        r_p = ctk.CTkFrame(self.content_area, fg_color="transparent"); r_p.pack(side="right", padx=5)
        self.t_val = ctk.CTkEntry(r_p, width=60); self.t_val.insert(0, "1000"); self.t_val.pack()
        self.mode_sel = ctk.CTkOptionMenu(r_p, values=["手动", "自动"], width=80, command=self.toggle_mode); self.mode_sel.pack(pady=10)

    def toggle_fold(self):
        if not self.is_collapsed:
            self.content_area.pack_forget(); self.fold_btn.configure(text="🔽 展开"); self.is_collapsed = True
        else:
            self.content_area.pack(fill="both", expand=True, padx=10, pady=(0, 10)); self.fold_btn.configure(text="🔼 收起"); self.is_collapsed = False
    def toggle_mode(self, m):
        self.is_auto = (m == "自动")
        if self.is_auto: threading.Thread(target=self.worker, daemon=True).start()
    def worker(self):
        while self.is_auto:
            try: self.do_send(); time.sleep(float(self.t_val.get())/1000)
            except: time.sleep(1)
    def do_send(self):
        content = self.txt.get("1.0", "end-1c")
        if self.fmt_sel.get() == "HEX发送":
            try: self.controller.ser.write(bytes.fromhex(content.replace(" ", "")))
            except: pass
        else:
            suffix = "\n" if self.fmt_sel.get() == "加\\n" else ""
            self.controller.send_raw(content + suffix)

if __name__ == "__main__":
    app = MotorApp(); app.mainloop()