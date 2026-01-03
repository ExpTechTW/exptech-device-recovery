import sys
import glob
import json
import os
import ssl
import urllib.request
import urllib.error
import certifi
import serial.tools.list_ports
from esptool import main as esptool_main
import readchar

# Setup SSL context with certifi certificates
ssl_context = ssl.create_default_context(cafile=certifi.where())

VERSION = '1.0.0'
CHIP_TYPE = 'esp32'
BAUD_RATE = 921600
FLASH_FREQ = '80m'
APP_ADDRESS = '0x0'
FIRMWARE_JSON_URL = 'https://raw.githubusercontent.com/ExpTechTW/exptech-device-recovery/refs/heads/main/firmware.json'
BASE_URL = 'https://raw.githubusercontent.com/ExpTechTW/exptech-device-recovery/refs/heads/main'
FIRMWARE_CACHE_DIR = 'firmware_cache'


def list_serial_ports():
    """列出所有可用的序列埠"""
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


def load_firmware_json():
    """從遠端 URL 讀取 firmware.json"""
    try:
        print(f"\n⬇️  正在從遠端載入 firmware.json...")
        print(f"   URL: {FIRMWARE_JSON_URL}")
        with urllib.request.urlopen(FIRMWARE_JSON_URL, context=ssl_context) as response:
            content = response.read().decode('utf-8')
            firmware_data = json.loads(content)
            print(f"✅ 成功載入 firmware.json")
            return firmware_data
    except urllib.error.URLError as e:
        print(f"❌ 無法連線到遠端伺服器：{e}")
        print(f"   請檢查網路連接或 URL：{FIRMWARE_JSON_URL}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"❌ 無法解析 firmware.json：{e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 載入 firmware.json 時發生錯誤：{e}")
        sys.exit(1)


def interactive_select(items, title, default_index=None, get_label=None):
    """互動式選擇（支持上下鍵）"""
    if not items:
        return None
    
    if default_index is None:
        default_index = len(items) - 1  # 預設選擇最後一個
    
    current_index = default_index
    
    def display():
        print("=" * 40)
        print(f"🚀 ESP32 韌體燒錄工具 v{VERSION}")
        print("=" * 40)
        print(f"\n{title}")
        print("   使用 ↑↓ 鍵選擇，Enter 確認，q 退出")
        for i, item in enumerate(items):
            label = get_label(item, i) if get_label else str(item)
            if i == current_index:
                marker = "→ "
                # 使用反白顯示當前選項
                print(f"{marker}\033[7m[{i + 1}] {label}\033[0m")
            else:
                marker = "  "
                print(f"{marker}[{i + 1}] {label}")
    
    while True:
        # 清除並重新顯示
        sys.stdout.write('\033[2J\033[H')  # 清屏並移動到頂部
        display()
        
        key = readchar.readkey()
        
        # readchar 會自動處理箭頭鍵
        if key == readchar.key.UP:  # 上箭頭
            current_index = max(0, current_index - 1)
        elif key == readchar.key.DOWN:  # 下箭頭
            current_index = min(len(items) - 1, current_index + 1)
        elif key == readchar.key.ENTER or key == '\r' or key == '\n':  # Enter
            sys.stdout.write('\033[2J\033[H')  # 清屏
            return items[current_index]
        elif key == 'q' or key == 'Q':
            sys.exit(0)


def select_model(firmware_data):
    """選擇型號（model）"""
    products = firmware_data.get('product', [])

    available_products = [p for p in products if p.get(
        'versions') and len(p['versions']) > 0]

    if not available_products:
        print("❌ 未找到任何有可用版本的產品。")
        sys.exit(1)

    def get_product_label(product, index):
        model = product.get('model', '')
        name = product.get('name', model)
        versions_count = len(product.get('versions', []))
        return f"{name} ({model}) - {versions_count} 個版本"
    
    return interactive_select(
        available_products,
        "✅ 可用型號：",
        default_index=0,
        get_label=get_product_label
    )


def select_channel():
    """選擇更新通道"""
    channels = [
        {'name': 'Release', 'desc': '僅顯示正式版本'},
        {'name': 'All', 'desc': 'Pre-Release + Release（顯示所有版本）'}
    ]
    
    def get_channel_label(channel, index):
        default_mark = " (預設)" if index == 0 else ""
        return f"{channel['name']} - {channel['desc']}{default_mark}"
    
    selected = interactive_select(
        channels,
        "✅ 請選擇更新通道：",
        default_index=0,
        get_label=get_channel_label
    )
    
    return selected['name']


def parse_version(version_str):
    """解析版本號，返回 (年份, 週數, 字母) 用於排序"""
    # 格式：25w47a -> (25, 47, 'a')
    try:
        if 'w' in version_str.lower():
            parts = version_str.lower().split('w')
            year = int(parts[0])
            week_part = parts[1]
            # 提取週數和字母
            week = int(''.join(filter(str.isdigit, week_part)))
            letter = ''.join(filter(str.isalpha, week_part))
            if not letter:
                letter = 'a'  # 預設字母為 'a'
            return (year, week, letter)
        return (0, 0, 'a')
    except:
        return (0, 0, 'a')


def select_version(product, channel='All'):
    """選擇版本並返回版本資訊（預設選擇最新版本）"""
    all_versions = product.get('versions', [])

    if not all_versions:
        print("❌ 此型號沒有可用版本。")
        sys.exit(1)

    # 根據通道過濾版本
    if channel == 'Release':
        versions = [v for v in all_versions if v.get('type', '') == 'Release']
        if not versions:
            print("❌ 此通道沒有可用版本。")
            sys.exit(1)
    else:
        versions = all_versions

    # 按照版本號排序：年份 -> 週數 -> 字母
    # 例如：25w47a < 25w48a < 25w48b < 25w50a
    versions = sorted(versions, key=lambda v: parse_version(v.get('version', '')))

    def get_version_label(version, index):
        ver = version.get('version', '未知')
        ver_type = version.get('type', '')
        type_mark = f" [{ver_type}]" if ver_type else ""
        # 最後一個（最新的）標記為預設
        default_mark = " (最新，預設)" if index == len(versions) - 1 else ""
        return f"{ver}{type_mark}{default_mark}"
    
    title = f"✅ 可用版本（{product.get('name', product.get('model', ''))}，通道：{channel if channel == 'Release' else 'All'}）："
    
    return interactive_select(
        versions,
        title,
        default_index=len(versions) - 1,  # 預設選擇最後一個（最新的）
        get_label=get_version_label
    )


def download_file(url, filepath, description="檔案", min_size=0):
    """下載檔案並驗證檔案大小"""
    if os.path.exists(filepath):
        file_size = os.path.getsize(filepath)
        if file_size > min_size:
            print(f"\n📁 發現已下載的 {description}：{filepath} ({file_size} bytes)")
            overwrite = input("   是否重新下載？（y/N）：").strip().lower()
            if overwrite != 'y':
                print(f"   使用現有檔案：{filepath}")
                return filepath
        else:
            print(f"\n⚠️  已存在的 {description} 檔案過小或為空，將重新下載")
            os.remove(filepath)

    print(f"\n⬇️  正在下載 {description}...")
    print(f"   URL: {url}")
    print(f"   儲存位置: {filepath}")

    try:
        with urllib.request.urlopen(url, context=ssl_context) as response:
            with open(filepath, 'wb') as f:
                f.write(response.read())
        file_size = os.path.getsize(filepath)

        if file_size <= min_size:
            print(f"⚠️  警告：下載的 {description} 檔案過小或為空（{file_size} bytes）")
            confirm = input(f"   是否仍要使用此檔案？（y/N）：").strip().lower()
            if confirm != 'y':
                os.remove(filepath)
                return None

        print(f"✅ 下載完成：{filepath} ({file_size} bytes)")
        return filepath
    except Exception as e:
        print(f"❌ 下載失敗：{e}")
        sys.exit(1)


def download_firmware(url, version, model):
    """下載韌體檔案（支援相對路徑和完整 URL）"""
    if not os.path.exists(FIRMWARE_CACHE_DIR):
        os.makedirs(FIRMWARE_CACHE_DIR)

    # 如果是相對路徑，轉換為完整 URL
    if not url.startswith(('http://', 'https://')):
        if not url.startswith('/'):
            url = f"{BASE_URL}/{url}"
        else:
            url = f"{BASE_URL}{url}"

    filename = f"{model}_{version}.bin"
    filepath = os.path.join(FIRMWARE_CACHE_DIR, filename)
    return download_file(url, filepath, "韌體")


def get_bin_file_path():
    """取得 .bin 檔案路徑"""
    print("\n🔍 正在搜尋目前目錄下的 .bin 檔案...")
    bin_files = glob.glob('**/*.bin', recursive=True)

    if not bin_files:
        print("⚠️  未找到 .bin 檔案。")
        while True:
            file_path = input("   請輸入 .bin 檔案的完整路徑：").strip()
            if file_path.lower() == 'exit':
                sys.exit(0)
            if file_path:
                return file_path
            print("   路徑不能為空。")

    print("✅ 找到以下 .bin 檔案：")
    for i, file in enumerate(bin_files):
        print(f"   [{i + 1}] {file}")

    while True:
        choice = input(f"   請選擇檔案序號（1-{len(bin_files)}），或輸入完整路徑：").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(bin_files):
            return bin_files[int(choice) - 1]
        elif choice:
            return choice
        print("   輸入無效，請重新輸入。")


def erase_esp32(port):
    """完全清除 ESP32 flash 記憶體"""
    print("\n" + "=" * 40)
    print("⚠️  警告：即將完全清除 ESP32 的 flash 記憶體")
    print("⚠️  此操作不可逆轉，所有資料將被刪除")
    print("=" * 40)

    # 確認清除操作
    confirm_options = [
        {'value': True, 'name': '是，確認清除', 'desc': '將完全清除 ESP32 flash 記憶體'},
        {'value': False, 'name': '否，取消操作', 'desc': '返回主選單'}
    ]
    
    def get_confirm_label(option, index):
        return f"{option['name']} - {option['desc']}"
    
    selected_confirm = interactive_select(
        confirm_options,
        "⚠️  警告：即將完全清除 ESP32 的 flash 記憶體\n⚠️  此操作不可逆轉，所有資料將被刪除\n\n   請確認：",
        default_index=1,  # 預設選擇取消
        get_label=get_confirm_label
    )
    
    if not selected_confirm['value']:
        print("   操作已取消。")
        return False

    print(f"\n⚙️  清除設定資訊：")
    print(f"   • 晶片類型: {CHIP_TYPE}")
    print(f"   • 序列埠: {port}")
    print(f"   • 鮑率: {BAUD_RATE}")

    esptool_args = [
        '--chip', CHIP_TYPE,
        '--port', port,
        '--baud', str(BAUD_RATE),
        'erase_flash'
    ]

    print("\n" + "=" * 40)
    print("⏳ 正在啟動清除操作...")
    print("   （請依提示操作，例如按住 BOOT 鍵）")
    print("=" * 40)

    try:
        esptool_main(esptool_args)
        print("\n✅ 清除完成！ESP32 的 flash 記憶體已被完全清除。")
        return True
    except Exception as e:
        print(f"\n❌ 清除失敗。錯誤訊息：{e}")
        print("   請檢查：序列埠設定、ESP32 燒錄模式（BOOT 鍵）。")
        return False


def run_flash_tool():
    """主程式：執行燒錄作業"""

    # 選擇操作模式
    modes = [
        {'id': '1', 'name': '使用 firmware.json 中的韌體燒錄', 'desc': '從遠端下載並燒錄韌體'},
        {'id': '2', 'name': '使用 test.bin 燒錄', 'desc': '燒錄本地的 test.bin 檔案'},
        {'id': '3', 'name': '指定本地 bin 檔案', 'desc': '選擇任意本地 bin 檔案進行燒錄'},
        {'id': '4', 'name': '完全清除 ESP32 flash 記憶體', 'desc': '清除所有 flash 資料'}
    ]
    
    def get_mode_label(mode, index):
        default_mark = " (預設)" if index == 0 else ""
        return f"{mode['name']} - {mode['desc']}{default_mark}"
    
    selected_mode = interactive_select(
        modes,
        "✅ 請選擇操作模式：",
        default_index=0,
        get_label=get_mode_label
    )
    source_choice = selected_mode['id']

    # 選擇序列埠
    port_list = list_serial_ports()
    
    def get_port_label(port_info, index):
        return port_info['full_info']
    
    selected_port_info = interactive_select(
        port_list,
        "✅ 請選擇序列埠：",
        default_index=0,
        get_label=get_port_label
    )
    port = selected_port_info['device']

    # 如果選擇清除模式，執行清除並退出
    if source_choice == '4':
        erase_esp32(port)
        return

    bin_path = None

    if source_choice == '2':
        test_bin_path = 'test.bin'
        if os.path.exists(test_bin_path):
            print(f"\n✅ 找到 test.bin：{test_bin_path}")
            bin_path = test_bin_path
        else:
            print(f"\n⚠️  未找到 test.bin，請輸入完整路徑。")
            while True:
                file_path = input("   請輸入 test.bin 的完整路徑：").strip()
                if file_path.lower() == 'exit':
                    sys.exit(0)
                if file_path and os.path.exists(file_path):
                    bin_path = file_path
                    break
                print("   檔案不存在，請重新輸入。")
    elif source_choice == '3':
        # 指定本地 bin 檔案
        print("\n📁 請指定本地 bin 檔案：")
        while True:
            file_path = input("   請輸入 bin 檔案的完整路徑（或相對路徑）：").strip()
            if file_path.lower() == 'exit':
                sys.exit(0)
            if not file_path:
                print("   路徑不能為空。")
                continue

            # 處理相對路徑
            if not os.path.isabs(file_path):
                file_path = os.path.abspath(file_path)

            if os.path.exists(file_path):
                if file_path.lower().endswith('.bin'):
                    bin_path = file_path
                    print(f"\n✅ 找到檔案：{bin_path}")
                    break
                else:
                    print("   檔案必須是 .bin 格式。")
            else:
                print("   檔案不存在，請重新輸入。")

    # 如果選擇了選項 2 或 3，直接燒錄本地檔案
    if source_choice == '2' or source_choice == '3':
        print(f"\n⚙️  設定資訊：")
        print(f"   • 晶片類型: {CHIP_TYPE}")
        print(f"   • 序列埠: {port}")
        print(f"   • 檔案路徑: {bin_path}")
        print(f"   • 燒錄位址: {APP_ADDRESS}")
        print(f"   • 鮑率: {BAUD_RATE}")

        esptool_args = [
            '--chip', CHIP_TYPE,
            '--port', port,
            '--baud', str(BAUD_RATE),
            'write-flash',
            '--flash_freq', FLASH_FREQ,
            APP_ADDRESS,
            bin_path
        ]

        print("\n" + "=" * 40)
        print("⏳ 正在啟動燒錄...")
        print("   （請依提示操作，例如按住 BOOT 鍵）")
        print("=" * 40)

        try:
            esptool_main(esptool_args)
            print("\n🎉 燒錄完成！請重新啟動您的 ESP32 裝置。")
        except Exception as e:
            print(f"\n❌ 燒錄失敗。錯誤訊息：{e}")
            print("   請檢查：序列埠設定、ESP32 燒錄模式（BOOT 鍵）、檔案路徑。")
        return

    # 選項 1：使用 firmware.json 中的韌體燒錄
    if source_choice == '1':
        firmware_data = load_firmware_json()

        selected_product = select_model(firmware_data)
        
        # 選擇更新通道
        channel = select_channel()

        version_info = select_version(selected_product, channel)

        # 從 product 取得 path，從 version 取得 version 號
        product_path = selected_product.get('path', '')
        version = version_info.get('version', 'unknown')

        # 組合 URL：path/version.bin
        if product_path:
            url = f"{product_path}/{version}.bin"
        else:
            print("❌ 錯誤：產品未指定 path")
            sys.exit(1)

        # 顯示版本資訊
        print(f"\n🔍 版本資訊：")
        print(f"   • 版本號: {version}")
        print(f"   • 類型: {version_info.get('type', 'N/A')}")
        print(f"   • 路徑: {url}")

        # 下載應用程式韌體
        bin_path = download_firmware(
            url, version, selected_product.get('model', 'unknown'))

        # 準備燒錄參數
        esptool_args = [
            '--chip', CHIP_TYPE,
            '--port', port,
            '--baud', str(BAUD_RATE),
            'write-flash',
            '--flash_freq', FLASH_FREQ,
            APP_ADDRESS,
            bin_path
        ]

        print(f"\n⚙️  設定資訊：")
        print(f"   • 晶片類型: {CHIP_TYPE}")
        print(f"   • 序列埠: {port}")
        print(f"   • 鮑率: {BAUD_RATE}")
        print(f"   • 應用程式: {bin_path} @ {APP_ADDRESS}")

        print("\n" + "=" * 40)
        print("⏳ 正在啟動燒錄...")
        print("   （請依提示操作，例如按住 BOOT 鍵）")
        print("=" * 40)

        try:
            esptool_main(esptool_args)
            print("\n🎉 燒錄完成！請重新啟動您的 ESP32 裝置。")
        except Exception as e:
            print(f"\n❌ 燒錄失敗。錯誤訊息：{e}")
            print("   請檢查：序列埠設定、ESP32 燒錄模式（BOOT 鍵）、檔案路徑。")
        return


if __name__ == '__main__':
    try:
        run_flash_tool()
    except KeyboardInterrupt:
        print("\n操作已中斷。程式結束。")
        sys.exit(0)

