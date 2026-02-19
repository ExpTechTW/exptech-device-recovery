#!/usr/bin/env python3
"""
Serial Monitor 工具
使用上下鍵選擇序列埠裝置，固定 115200 baud rate
"""

import sys
import serial
import serial.tools.list_ports
import readchar
import threading

BAUD_RATE = 115200


def list_serial_ports():
    ports = serial.tools.list_ports.comports()
    if not ports:
        print("❌ 未偵測到任何序列埠裝置。請檢查 USB 連接與驅動程式。")
        sys.exit(1)

    port_list = []
    for port in ports:
        desc = port.description if port.description else port.device
        port_list.append({
            'device': port.device,
            'description': desc,
            'full_info': f"{port.device} ({desc})"
        })

    return port_list


def interactive_select(items, title, default_index=0, get_label=None):
    if not items:
        return None

    current_index = default_index

    def display():
        print("=" * 40)
        print("📡 Serial Monitor")
        print("=" * 40)
        print(f"\n{title}")
        print("   使用 ↑↓ 鍵選擇，Enter 確認，q 退出")
        for i, item in enumerate(items):
            label = get_label(item, i) if get_label else str(item)
            if i == current_index:
                print(f"→ \033[7m[{i + 1}] {label}\033[0m")
            else:
                print(f"  [{i + 1}] {label}")

    while True:
        sys.stdout.write('\033[2J\033[H')
        display()

        key = readchar.readkey()

        if key == readchar.key.UP:
            current_index = max(0, current_index - 1)
        elif key == readchar.key.DOWN:
            current_index = min(len(items) - 1, current_index + 1)
        elif key == readchar.key.ENTER or key == '\r' or key == '\n':
            sys.stdout.write('\033[2J\033[H')
            return items[current_index]
        elif key == 'q' or key == 'Q':
            sys.exit(0)


def monitor(port):
    print(f"📡 Serial Monitor")
    print(f"   裝置: {port}")
    print(f"   鮑率: {BAUD_RATE}")
    print(f"   按 Ctrl+C 結束")
    print("=" * 40)

    try:
        ser = serial.Serial(port, BAUD_RATE, timeout=1)
    except serial.SerialException as e:
        print(f"❌ 無法開啟序列埠：{e}")
        sys.exit(1)

    stop_event = threading.Event()

    def read_serial():
        while not stop_event.is_set():
            try:
                if ser.in_waiting > 0:
                    data = ser.read(ser.in_waiting)
                    sys.stdout.write(data.decode('utf-8', errors='replace'))
                    sys.stdout.flush()
            except serial.SerialException:
                if not stop_event.is_set():
                    print("\n❌ 序列埠連線中斷")
                break

    reader = threading.Thread(target=read_serial, daemon=True)
    reader.start()

    try:
        while reader.is_alive():
            reader.join(timeout=0.1)
    except KeyboardInterrupt:
        pass
    finally:
        stop_event.set()
        ser.close()
        print("\n\n📡 Serial Monitor 已結束")


def main():
    port_list = list_serial_ports()

    selected = interactive_select(
        port_list,
        "✅ 請選擇序列埠：",
        default_index=0,
        get_label=lambda p, i: p['full_info']
    )

    monitor(selected['device'])


if __name__ == '__main__':
    main()
