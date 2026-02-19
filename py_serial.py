import serial
import serial.tools.list_ports
import threading
from queue import Queue
import time
import struct

# -------------------- 协议配置 --------------------
HEADER = bytes([0x44, 0x58])  # 协议头 "DX"
FOOTER = bytes([0x58, 0x44])  # 协议尾 "XD"
DEFAULT_CMD = 0x01            # 默认命令字节
BAUDRATE = 115200             # 默认波特率
MAX_X = 1000.0                # X坐标最大值(mm)
MAX_Z = 500.0                 # Z坐标最大值(mm)

# -------------------- 功能函数 --------------------
def float_to_bytes(f):
    """将浮点数转换为4字节bytes"""
    return struct.pack('f', f)

def validate_input(x, z, grip):
    """验证输入范围"""
    errors = []
    if not (0 <= x <= MAX_X):
        errors.append(f"X坐标必须为0-{MAX_X}的浮点数")
    if not (0 <= z <= MAX_Z):
        errors.append(f"Z坐标必须为0-{MAX_Z}的浮点数")
    if grip not in (0, 1):
        errors.append("抓取标志必须为0或1")
    return errors

def calculate_checksum(cmd, *data_bytes):
    """计算校验和（所有字段相加取低8位）"""
    checksum = cmd
    for b in data_bytes:
        checksum += b
    return checksum & 0xFF

def list_available_ports():
    """列出所有可用串口"""
    return [port.device for port in serial.tools.list_ports.comports()]

def connect_serial(port, baudrate, receive_queue):
    """连接串口并启动接收线程"""
    try:
        ser = serial.Serial(port, baudrate, timeout=0.1)
        print(f"\n[成功] 已连接 {port}")
        
        threading.Thread(
            target=serial_receiver,
            args=(ser, receive_queue),
            daemon=True
        ).start()
        
        return ser
    except Exception as e:
        print(f"\n[错误] 连接失败: {e}")
        return None

def serial_receiver(ser, queue):
    """增强型接收线程（支持协议解析）"""
    buffer = bytearray()
    while ser and ser.is_open:
        try:
            data = ser.read(ser.in_waiting or 1)
            if data:
                buffer.extend(data)
                
                # 协议解析状态机
                while len(buffer) >= 2:
                    # 查找协议头
                    header_pos = buffer.find(HEADER)
                    if header_pos == -1:
                        if len(buffer) > 100:
                            print(f"[警告] 丢弃无效数据: {bytes(buffer[:100]).hex(' ')}...")
                            buffer.clear()
                        break
                    
                    # 移除头之前的无效数据
                    if header_pos > 0:
                        print(f"[丢弃] 无效数据: {bytes(buffer[:header_pos]).hex(' ')}")
                        buffer = buffer[header_pos:]
                    
                    # 检查最小帧长度
                    if len(buffer) < 7:  # 头2 + CMD1 + LEN1 + 校验和1 + 尾2
                        break
                    
                    # 解析数据长度
                    data_len = buffer[3]
                    total_len = 7 + data_len  # 完整帧长度
                    
                    if len(buffer) < total_len:
                        break
                    
                    # 提取完整帧并校验
                    frame = bytes(buffer[:total_len])
                    buffer = buffer[total_len:]
                    
                    if frame[-2:] != FOOTER:
                        print(f"[错误] 帧尾不匹配: {frame.hex(' ')}")
                        continue
                    
                    # 校验和验证
                    calc_checksum = sum(frame[2:-3]) & 0xFF
                    if calc_checksum != frame[-3]:
                        print(f"[错误] 校验和失败 (接收:{frame[-3]:02X} 计算:{calc_checksum:02X})")
                        continue
                    
                    queue.put(frame)
                    
        except Exception as e:
            print(f"[接收错误] {e}")
            time.sleep(0.01)

# -------------------- 数据打包函数 --------------------
def build_packet(cmd, x, z, grip):
    """构建协议数据包"""
    # 将浮点数转换为字节
    x_bytes = float_to_bytes(x)
    z_bytes = float_to_bytes(z)
    
    # 构造数据域
    data = bytes([cmd]) + x_bytes + z_bytes + bytes([grip])
    data_len = len(data) - 1  # 不包含cmd的长度
    
    # 计算校验和
    checksum = calculate_checksum(cmd, *data[1:])
    
    # 完整协议帧
    return HEADER + data + bytes([checksum]) + FOOTER

# -------------------- 主程序 --------------------
def main():
    current_ser = None
    current_cmd = DEFAULT_CMD
    receive_queue = Queue()

    print("=== 机械臂控制协议调试工具 ===")
    print("命令:")
    print("  list    - 列出串口")
    print("  connect - 连接串口")
    print("  close   - 断开连接")
    print("  cmd     - 修改命令字节（当前: 0x{:02X}）".format(current_cmd))
    print("  exit    - 退出程序")
    print("数据格式: X坐标(0-{}) Z坐标(0-{}) 抓取标志(0/1)".format(MAX_X, MAX_Z))

    try:
        while True:
            # 实时处理接收数据
            while not receive_queue.empty():
                frame = receive_queue.get()
                print(f"\n[RX] {frame.hex(' ').upper()}")
                
                # 解析数据包
                try:
                    cmd = frame[2]
                    x = struct.unpack('f', frame[4:8])[0]
                    z = struct.unpack('f', frame[8:12])[0]
                    grip = frame[12]
                    print(f"解析结果: X={x:.2f}mm Z={z:.2f}mm 抓取={'是' if grip else '否'}")
                except Exception as e:
                    print(f"[解析错误] {e}")

            # 用户输入处理
            status = []
            if current_ser and current_ser.is_open:
                status.append(f"端口:{current_ser.port}")
            else:
                status.append("[未连接]")
            status.append(f"CMD:0x{current_cmd:02X}")
            
            try:
                user_input = input(f"\n[{'|'.join(status)}] 输入: ").strip()
            except:
                continue

            # 命令处理
            if user_input.lower() == 'exit':
                if current_ser:
                    current_ser.close()
                print("程序已退出")
                break

            elif user_input.lower() == 'list':
                ports = list_available_ports()
                print("\n可用串口:" + ("\n".join(ports) if ports else " 无"))

            elif user_input.lower() == 'connect':
                ports = list_available_ports()
                if not ports:
                    print("无可用串口")
                    continue
                
                print("\n选择串口:")
                for i, port in enumerate(ports):
                    print(f"{i+1}. {port}")
                
                try:
                    choice = int(input("序号: ")) - 1
                    if current_ser:
                        current_ser.close()
                    current_ser = connect_serial(ports[choice], BAUDRATE, receive_queue)
                except (ValueError, IndexError):
                    print("输入无效")

            elif user_input.lower() == 'close':
                if current_ser:
                    current_ser.close()
                    print("已断开连接")
                else:
                    print("当前未连接")

            elif user_input.lower().startswith('cmd '):
                try:
                    new_cmd = int(user_input[4:], 16)
                    if 0 <= new_cmd <= 255:
                        current_cmd = new_cmd
                        print(f"命令字节已设为 0x{current_cmd:02X}")
                    else:
                        print("CMD需在0x00-0xFF之间")
                except ValueError:
                    print("格式错误 (示例: cmd 0x05)")

            # 数据发送
            elif current_ser and current_ser.is_open:
                try:
                    # 解析输入 (示例: "100.5 200.3 1")
                    x, z, grip = map(float, user_input.split())
                    grip = int(grip)
                    
                    if errors := validate_input(x, z, grip):
                        print("\n".join(f"[错误] {err}" for err in errors))
                        continue

                    # 构建并发送数据包
                    packet = build_packet(current_cmd, x, z, grip)
                    current_ser.write(packet)
                    
                    print(f"\n[TX] {packet.hex(' ').upper()}")
                    print(f"发送数据: X={x:.2f}mm Z={z:.2f}mm 抓取={'是' if grip else '否'}")

                except ValueError:
                    print("[错误] 输入格式: X坐标 Z坐标 抓取标志 (如: 150.5 300.0 1)")
                except Exception as e:
                    print(f"[发送错误] {e}")
                    if current_ser:
                        current_ser.close()

            else:
                print("[错误] 请先连接串口")

    except KeyboardInterrupt:
        print("\n程序被中断")
    finally:
        if current_ser:
            current_ser.close()

if __name__ == "__main__":
    main()