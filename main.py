import sys
import glob
import json
import os
import urllib.request
import urllib.error
import serial.tools.list_ports
from esptool import main as esptool_main

CHIP_TYPE = 'esp32'
BAUD_RATE = 460800
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
    print("\n✅ 可用序列埠：")
    for i, port in enumerate(ports):
        desc = port.description if 'USB' in port.description or 'tty' in port.name else port.device
        print(f"   [{i + 1}] {port.device} ({desc})")
        port_list.append(port.device)

    return port_list


def load_firmware_json():
    """從遠端 URL 讀取 firmware.json"""
    try:
        print(f"\n⬇️  正在從遠端載入 firmware.json...")
        print(f"   URL: {FIRMWARE_JSON_URL}")
        with urllib.request.urlopen(FIRMWARE_JSON_URL) as response:
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
    """選擇版本並返回版本資訊（默認選擇最新版本）"""
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
            return selected_version
        print("   輸入無效，請重新輸入。")


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
        urllib.request.urlretrieve(url, filepath)
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
    """下載固件檔案（支援相對路徑和完整 URL）"""
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
    return download_file(url, filepath, "固件")


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

    confirm = input("\n   請輸入 'YES' 確認清除操作：").strip()
    if confirm != 'YES':
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

    print("=" * 40)
    print(f"🚀 ESP32 固件燒錄工具 ({CHIP_TYPE})")
    print(f"📍 應用程式起始位址: {APP_ADDRESS}")
    print("=" * 40)
    print()

    print("✅ 請選擇操作模式：")
    print("   [1] 使用 firmware.json 中的固件燒錄（默認）")
    print("   [2] 使用 test.bin 燒錄")
    print("   [3] 完全清除 ESP32 flash 記憶體")

    source_choice = input("   請選擇（1-3，按 Enter 使用默認）：").strip()
    if not source_choice:
        source_choice = '1'

    # 選擇序列埠（清除模式也需要選擇序列埠）
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

    # 如果選擇清除模式，執行清除並退出
    if source_choice == '3':
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
    else:
        firmware_data = load_firmware_json()

        selected_product = select_model(firmware_data)

        version_info = select_version(selected_product)

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

        # 下載應用程式固件
        bin_path = download_firmware(
            url, version, selected_product.get('model', 'unknown'))

        # 準備燒錄參數
        esptool_args = [
            '--chip', CHIP_TYPE,
            '--port', port,
            '--baud', str(BAUD_RATE),
            'write-flash',
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

    # 使用 test.bin 時只燒錄應用程式
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
