# ExpTech Device Recovery

ESP32 韌體燒錄工具

## 下載

從 [Releases](https://github.com/ExpTechTW/exptech-device-recovery/releases) 頁面下載對應平台的可執行檔：

| 平台 | 檔案 |
|------|------|
| Windows | `exptech-device-recovery-windows.exe` |
| macOS | `exptech-device-recovery-macos` |
| Linux | `exptech-device-recovery-linux` |

## 使用方式

### Windows

直接雙擊執行 `exptech-device-recovery-windows.exe`

### macOS

首次執行需要移除安全隔離屬性：

```bash
xattr -d com.apple.quarantine ./exptech-device-recovery-macos
chmod +x ./exptech-device-recovery-macos
./exptech-device-recovery-macos
```

### Linux

```bash
chmod +x ./exptech-device-recovery-linux
./exptech-device-recovery-linux
```

## 功能

- 從遠端下載並燒錄韌體
- 燒錄本地 `.bin` 檔案
- 完全清除 ESP32 flash 記憶體

## 從原始碼執行

```bash
# 安裝依賴
pip install -r requirements.txt

# 執行
python main.py
```

## 從原始碼打包

```bash
# macOS / Linux
./build.sh

# Windows
build.bat
```

輸出位置：`dist/exptech-device-recovery`
