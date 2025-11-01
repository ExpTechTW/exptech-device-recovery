import sys
import glob
import json
import os
import urllib.request
import serial.tools.list_ports
from esptool import main as esptool_main

CHIP_TYPE = 'esp32'
BAUD_RATE = 460800
APP_ADDRESS = '0x10000'
FIRMWARE_JSON_PATH = 'firmware.json'
FIRMWARE_CACHE_DIR = 'firmware_cache'


def list_serial_ports():
    """列出所有可用的序列埠"""
    ports = serial.tools.list_ports.comports()
    if not ports:
        print("❌ 未偵測到任何序列埠裝置。請檢查 USB 連接與驅動程式。")
        sys.exit(1)

    port_list = []
    print("\n✅ 可用序列埠：")
    for i, port in enumerate(ports):
        desc = port.description if 'USB' in port.description or 'tty' in port.name else port.device
        print(f"   [{i + 1}] {port.device} ({desc})")
        port_list.append(port.device)

    return port_list


def load_firmware_json():
    """讀取 firmware.json"""
    try:
        with open(FIRMWARE_JSON_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"❌ 找不到 {FIRMWARE_JSON_PATH} 檔案。")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"❌ 無法解析 {FIRMWARE_JSON_PATH}：{e}")
        sys.exit(1)


def select_model(firmware_data):
    """選擇型號（model）"""
    products = firmware_data.get('product', [])

    available_products = [p for p in products if p.get(
        'versions') and len(p['versions']) > 0]

    if not available_products:
        print("❌ 未找到任何有可用版本的產品。")
        sys.exit(1)

    print("\n✅ 可用型號：")
    for i, product in enumerate(available_products):
        model = product.get('model', '')
        name = product.get('name', model)
        versions_count = len(product.get('versions', []))
        print(f"   [{i + 1}] {name} ({model}) - {versions_count} 個版本")

    while True:
        choice = input(f"   請選擇型號序號（1-{len(available_products)}）：").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(available_products):
            return available_products[int(choice) - 1]
        print("   輸入無效，請重新輸入。")


def select_version(product):
    """選擇版本並返回 URL（默認選擇最新版本）"""
    versions = product.get('versions', [])

    if not versions:
        print("❌ 此型號沒有可用版本。")
        sys.exit(1)

    print(f"\n✅ 可用版本（{product.get('name', product.get('model', ''))}）：")
    for i, version in enumerate(versions):
        ver = version.get('version', '未知')
        default_mark = " (最新，默認)" if i == 0 else ""
        print(f"   [{i + 1}] {ver}{default_mark}")

    while True:
        choice = input(
            f"   請選擇版本序號（1-{len(versions)}，按 Enter 使用默認最新版本）：").strip()

        if not choice:
            choice = '1'

        if choice.isdigit() and 1 <= int(choice) <= len(versions):
            selected_version = versions[int(choice) - 1]
            url = selected_version.get('url', '')
            if not url:
                print("❌ 此版本沒有有效的 URL。")
                sys.exit(1)
            return url, selected_version.get('version', 'unknown')
        print("   輸入無效，請重新輸入。")


def download_firmware(url, version, model):
    """下載固件檔案"""
    if not os.path.exists(FIRMWARE_CACHE_DIR):
        os.makedirs(FIRMWARE_CACHE_DIR)

    filename = f"{model}_{version}.bin"
    filepath = os.path.join(FIRMWARE_CACHE_DIR, filename)

    if os.path.exists(filepath):
        print(f"\n📁 發現已下載的檔案：{filepath}")
        overwrite = input("   是否重新下載？（y/N）：").strip().lower()
        if overwrite != 'y':
            print(f"   使用現有檔案：{filepath}")
            return filepath

    print(f"\n⬇️  正在下載固件...")
    print(f"   URL: {url}")
    print(f"   儲存位置: {filepath}")

    try:
        urllib.request.urlretrieve(url, filepath)
        print(f"✅ 下載完成：{filepath}")
        return filepath
    except Exception as e:
        print(f"❌ 下載失敗：{e}")
        sys.exit(1)


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


def run_flash_tool():
    """主程式：執行燒錄作業"""

    print("=" * 40)
    print(f"🚀 ESP32 應用程式固件燒錄工具 ({CHIP_TYPE})")
    print(f"📍 應用程式起始位址: {APP_ADDRESS}")
    print("=" * 40)
    print()

    print("✅ 請選擇燒錄來源：")
    print("   [1] 使用 firmware.json 中的固件（默認）")
    print("   [2] 使用 test.bin")

    source_choice = input("   請選擇（1-2，按 Enter 使用默認）：").strip()
    if not source_choice:
        source_choice = '1'

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
    else:
        firmware_data = load_firmware_json()

        selected_product = select_model(firmware_data)

        url, version = select_version(selected_product)

        bin_path = download_firmware(
            url, version, selected_product.get('model', 'unknown'))

    port_list = list_serial_ports()
    while True:
        port_choice = input(
            f"   請選擇序列埠序號（1-{len(port_list)}），或輸入完整名稱：").strip()
        if port_choice.isdigit() and 1 <= int(port_choice) <= len(port_list):
            port = port_list[int(port_choice) - 1]
            break
        elif port_choice:
            port = port_choice
            break
        print("   輸入無效，請重新輸入。")

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
        'write_flash',
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


if __name__ == '__main__':
    try:
        run_flash_tool()
    except KeyboardInterrupt:
        print("\n操作已中斷。程式結束。")
        sys.exit(0)
