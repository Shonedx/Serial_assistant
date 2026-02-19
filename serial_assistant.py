import tkinter as tk
from tkinter import font, colorchooser, messagebox
import customtkinter as ctk
import serial
import serial.tools.list_ports
import threading

# 全局样式配置
ctk.set_appearance_mode("Dark")

class MotorApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.version = "v1.2.3"
        self.title(f"串口助手_极客翔 ({self.version})")
        self.geometry("1280x900")
        self.minsize(1000, 750)
        
        # --- 样式与颜色配置变量 ---
        self.font_family = tk.StringVar(value="Microsoft YaHei") 
        self.font_size = tk.IntVar(value=14)
        self.font_weight = tk.StringVar(value="normal") 
        
        # 默认配色：黑底绿字（黑客风格）
        self.text_bg_color = tk.StringVar(value="#1e1e1e")
        self.text_fg_color = tk.StringVar(value="#00FF00")
        
        # 监听变量变化，实现全域实时更新
        for var in [self.font_family, self.font_size, self.font_weight, self.text_bg_color, self.text_fg_color]:
            var.trace_add("write", lambda *args: self.update_global_style())

        self.custom_font = ctk.CTkFont(family=self.font_family.get(), size=self.font_size.get(), weight=self.font_weight.get())

        self.ser = None
        self.running = False

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # 1. 侧边栏
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
        menu_items = [("📝", "ConsolePage"), ("⚙️", "ParamPage"), ("🎨", "SettingPage")]
        for icon, page in menu_items:
            btn = ctk.CTkButton(self.sidebar, text=icon, width=60, height=60, 
                                 fg_color="transparent", hover_color="#333333",
                                 font=("Arial", 24),
                                 command=lambda p=page: self.show_frame(p))
            btn.pack(pady=20, padx=10)

    def update_global_style(self):
        """核心：更新全局样式并递归刷新所有组件"""
        try:
            self.custom_font.configure(family=self.font_family.get(), size=self.font_size.get(), weight=self.font_weight.get())
            self.refresh_ui_elements(self)
        except: pass

    def refresh_ui_elements(self, parent):
        """遍历所有组件，如果是文本框，则应用最新的配色方案"""
        for child in parent.winfo_children():
            try:
                if isinstance(child, ctk.CTkTextbox):
                    child.configure(
                        font=(self.font_family.get(), self.font_size.get(), self.font_weight.get()),
                        fg_color=self.text_bg_color.get(),
                        text_color=self.text_fg_color.get()
                    )
                elif hasattr(child, "configure") and "font" in child.keys():
                    child.configure(font=self.custom_font)
            except: pass
            self.refresh_ui_elements(child)

    def show_frame(self, page_name):
        self.frames[page_name].tkraise()

    def send_raw(self, data_str):
        if self.ser and self.ser.is_open:
            try: self.ser.write(data_str.encode('utf-8'))
            except: pass

# --- 页面1：串口助手 ---
class ConsolePage(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller

        cfg_bar = ctk.CTkFrame(self, corner_radius=10)
        cfg_bar.pack(fill="x", padx=5, pady=5)
        
        r1 = ctk.CTkFrame(cfg_bar, fg_color="transparent"); r1.pack(fill="x", pady=5, padx=10)
        ctk.CTkLabel(r1, text="端口:").pack(side="left", padx=5)
        self.port_sel = ctk.CTkOptionMenu(r1, values=self.get_ports(), width=140)
        self.port_sel.pack(side="left", padx=2)
        ctk.CTkButton(r1, text="🔄", width=40, command=self.refresh_ports).pack(side="left", padx=5)
        
        ctk.CTkLabel(r1, text="波特率:").pack(side="left", padx=10)
        self.baud_sel = ctk.CTkOptionMenu(r1, values=["9600", "115200", "921600"], width=110)
        self.baud_sel.set("115200"); self.baud_sel.pack(side="left", padx=5)
        self.btn_ser = ctk.CTkButton(r1, text="开启连接", fg_color="#27AE60", command=self.toggle_ser)
        self.btn_ser.pack(side="right", padx=10)

        # 串口详细参数
        r2 = ctk.CTkFrame(cfg_bar, fg_color="transparent"); r2.pack(fill="x", pady=(0, 10), padx=10)
        ctk.CTkLabel(r2, text="数据位:").pack(side="left", padx=5)
        self.data_sel = ctk.CTkOptionMenu(r2, values=["8", "7", "6", "5"], width=80); self.data_sel.set("8"); self.data_sel.pack(side="left")
        ctk.CTkLabel(r2, text="校验位:").pack(side="left", padx=10)
        self.parity_sel = ctk.CTkOptionMenu(r2, values=["None", "Even", "Odd"], width=90); self.parity_sel.set("None"); self.parity_sel.pack(side="left")
        ctk.CTkLabel(r2, text="停止位:").pack(side="left", padx=10)
        self.stop_sel = ctk.CTkOptionMenu(r2, values=["1", "1.5", "2"], width=80); self.stop_sel.set("1"); self.stop_sel.pack(side="left")

        # 布局
        self.paned = tk.PanedWindow(self, orient=tk.VERTICAL, bg="#2b2b2b", sashwidth=6, sashrelief=tk.RAISED)
        self.paned.pack(fill="both", expand=True, pady=10)

        self.recv_frame = ctk.CTkFrame(self.paned, fg_color="transparent")
        ctk.CTkLabel(self.recv_frame, text=" 📥 接收终端", text_color="#AAAAAA").pack(anchor="w", padx=10)
        self.recv_box = ctk.CTkTextbox(self.recv_frame)
        self.recv_box.pack(fill="both", expand=True, padx=5, pady=5)
        self.paned.add(self.recv_frame, height=500)

        self.send_frame = ctk.CTkFrame(self.paned, fg_color="transparent")
        ctk.CTkLabel(self.send_frame, text=" 📤 发送指令", text_color="#AAAAAA").pack(anchor="w", padx=10)
        send_inner = ctk.CTkFrame(self.send_frame, fg_color="transparent")
        send_inner.pack(fill="both", expand=True)
        self.send_box = ctk.CTkTextbox(send_inner)
        self.send_box.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        
        btn_grp = ctk.CTkFrame(send_inner, fg_color="transparent")
        btn_grp.pack(side="right", fill="y", padx=5)
        ctk.CTkButton(btn_grp, text="手动发送", width=100, command=self.manual_send).pack(pady=5)
        ctk.CTkButton(btn_grp, text="清除接收", width=100, fg_color="#555555", command=lambda: self.recv_box.delete("1.0", "end")).pack(pady=5)
        self.paned.add(self.send_frame, height=200)

    def get_ports(self): return [p.device for p in serial.tools.list_ports.comports()] or ["无设备"]
    def refresh_ports(self): p = self.get_ports(); self.port_sel.configure(values=p); self.port_sel.set(p[0])
    
    def toggle_ser(self):
        c = self.controller
        if not c.running:
            try:
                p_map = {'None': serial.PARITY_NONE, 'Even': serial.PARITY_EVEN, 'Odd': serial.PARITY_ODD}
                s_map = {'1': serial.STOPBITS_ONE, '1.5': serial.STOPBITS_ONE_POINT_FIVE, '2': serial.STOPBITS_TWO}
                c.ser = serial.Serial(port=self.port_sel.get(), baudrate=int(self.baud_sel.get()), 
                                      bytesize=int(self.data_sel.get()), parity=p_map[self.parity_sel.get()],
                                      stopbits=s_map[self.stop_sel.get()], timeout=0.1)
                c.running = True
                self.btn_ser.configure(text="关闭串口", fg_color="#C0392B")
                threading.Thread(target=self.listen, daemon=True).start()
            except Exception as e: messagebox.showerror("错误", f"连接失败: {e}")
        else:
            c.running = False
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

    def manual_send(self): self.controller.send_raw(self.send_box.get("1.0", "end-1c"))

# --- 页面2：参数调优 (滑块控制) ---
class ParamPage(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller
        self.paned = tk.PanedWindow(self, orient=tk.VERTICAL, bg="#2b2b2b", sashwidth=4)
        self.paned.pack(fill="both", expand=True)
        
        self.top_frame = ctk.CTkFrame(self.paned, fg_color="transparent")
        t_bar = ctk.CTkFrame(self.top_frame, corner_radius=10); t_bar.pack(fill="x", padx=5, pady=5)
        ctk.CTkLabel(t_bar, text="🚀 参数实时调控").pack(side="left", padx=15)
        ctk.CTkButton(t_bar, text="+ 滑块", fg_color="#E67E22", command=self.add_param_item).pack(side="right", padx=10)
        
        self.scroll = ctk.CTkScrollableFrame(self.top_frame, label_text="控制面板")
        self.scroll.pack(fill="both", expand=True, padx=5, pady=5)
        self.paned.add(self.top_frame, height=550)
        
        self.bottom_frame = ctk.CTkFrame(self.paned, fg_color="transparent")
        ctk.CTkLabel(self.bottom_frame, text=" 📊 监控反馈:").pack(anchor="w", padx=15, pady=5)
        self.monitor_text = ctk.CTkTextbox(self.bottom_frame)
        self.monitor_text.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.paned.add(self.bottom_frame)

    def add_param_item(self): ParamComponent(self.scroll, self.controller).pack(fill="x", pady=5, padx=5)
    def update_monitor(self, text): self.monitor_text.insert("end", text); self.monitor_text.see("end")

# --- 页面3：设置页面 (核心颜色调整功能在此) ---
class SettingPage(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller
        
        ctk.CTkLabel(self, text="🎨 界面与显示定制", font=("Microsoft YaHei", 28, "bold")).pack(pady=20)
        
        # 1. 实时预览区域
        preview_frame = ctk.CTkFrame(self, corner_radius=15)
        preview_frame.pack(pady=10, padx=40, fill="x")
        ctk.CTkLabel(preview_frame, text="实时效果预览", text_color="#AAAAAA").pack(pady=5)
        self.preview_box = ctk.CTkTextbox(preview_frame, height=100)
        self.preview_box.pack(pady=10, padx=20, fill="x")
        self.preview_box.insert("0.0", "Hello! 这是你的串口显示预览。\n1234567890 ABCabc\n极客翔定制版。")

        # 2. 颜色调节卡片
        color_card = ctk.CTkFrame(self, corner_radius=15)
        color_card.pack(pady=10, padx=40, fill="x")
        
        ctk.CTkLabel(color_card, text="文本框配色设置", font=("YaHei", 16, "bold")).pack(pady=10)
        
        btn_row = ctk.CTkFrame(color_card, fg_color="transparent")
        btn_row.pack(fill="x", padx=20, pady=10)
        
        # 背景色按钮
        self.bg_btn = ctk.CTkButton(btn_row, text="选择背景颜色", 
                                    fg_color=self.controller.text_bg_color.get(),
                                    command=self.choose_bg)
        self.bg_btn.pack(side="left", expand=True, padx=10)
        
        # 文字色按钮
        self.fg_btn = ctk.CTkButton(btn_row, text="选择文字颜色", 
                                    text_color="black",
                                    fg_color=self.controller.text_fg_color.get(),
                                    command=self.choose_fg)
        self.fg_btn.pack(side="left", expand=True, padx=10)

        # 3. 预设快速切换
        preset_row = ctk.CTkFrame(color_card, fg_color="transparent")
        preset_row.pack(fill="x", padx=20, pady=10)
        
        ctk.CTkButton(preset_row, text="黑客绿", fg_color="#1e1e1e", text_color="#00FF00", 
                      command=lambda: self.set_preset("#1e1e1e", "#00FF00")).pack(side="left", padx=5, expand=True)
        ctk.CTkButton(preset_row, text="极客蓝", fg_color="#000000", text_color="#3498DB", 
                      command=lambda: self.set_preset("#000000", "#3498DB")).pack(side="left", padx=5, expand=True)
        ctk.CTkButton(preset_row, text="简约白", fg_color="#FDF6E3", text_color="#657B83", 
                      command=lambda: self.set_preset("#FDF6E3", "#657B83")).pack(side="left", padx=5, expand=True)

        # 4. 字体大小调节
        font_card = ctk.CTkFrame(self, corner_radius=15)
        font_card.pack(pady=10, padx=40, fill="x")
        ctk.CTkLabel(font_card, text="字体大小调节").pack(side="left", padx=20, pady=10)
        self.font_slider = ctk.CTkSlider(font_card, from_=10, to=40, variable=self.controller.font_size)
        self.font_slider.pack(side="right", fill="x", expand=True, padx=20)

    def choose_bg(self):
        color = colorchooser.askcolor(title="选择背景颜色", initialcolor=self.controller.text_bg_color.get())[1]
        if color:
            self.controller.text_bg_color.set(color)
            self.bg_btn.configure(fg_color=color)

    def choose_fg(self):
        color = colorchooser.askcolor(title="选择文字颜色", initialcolor=self.controller.text_fg_color.get())[1]
        if color:
            self.controller.text_fg_color.set(color)
            self.fg_btn.configure(fg_color=color)

    def set_preset(self, bg, fg):
        self.controller.text_bg_color.set(bg)
        self.controller.text_fg_color.set(fg)
        self.bg_btn.configure(fg_color=bg)
        self.fg_btn.configure(fg_color=fg)

# --- 滑块组件 ---
class ParamComponent(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, corner_radius=10, border_width=1, border_color="#3d3d3d")
        self.controller = controller
        l1 = ctk.CTkFrame(self, fg_color="transparent"); l1.pack(fill="x", padx=10, pady=5)
        self.header_e = ctk.CTkEntry(l1, placeholder_text="指令头(如P:)", width=100); self.header_e.pack(side="left", padx=2)
        self.slider = ctk.CTkSlider(self, from_=0, to=100, command=self.on_slide); self.slider.pack(fill="x", padx=10, pady=5)
        self.val_label = ctk.CTkLabel(self, text="0.00"); self.val_label.pack()
    def on_slide(self, v): 
        self.val_label.configure(text=f"{v:.2f}")
        if self.header_e.get(): self.controller.send_raw(f"{self.header_e.get()}{v:.2f}\n")

if __name__ == "__main__":
    app = MotorApp()
    app.mainloop()