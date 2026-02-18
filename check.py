#!/usr/bin/env python3
"""
Firmware 檢查與壓縮工具
1. 檢查 firmware.bin 內容是否與資料夾型號一致
2. 壓縮 .bin 為 .bin.zst（已存在則跳過）
"""

import os
import sys
import glob
import json

try:
    import zstandard as zstd
except ImportError:
    print("Please install zstandard: pip install zstandard")
    sys.exit(1)

FIRMWARE_DIR = 'firmware'
FIRMWARE_JSON = 'firmware.json'
COMPRESSION_LEVEL = 22

# firmware.bin 檢查規則
RULES = {
    'es-pro': {
        'must_contain': [b'ES-Pro'],
        'must_not_contain': [b'ES-Net'],
    },
    'es-net': {
        'must_contain': [b'ES-Net'],
        'must_not_contain': [b'ES-Pro'],
    },
}


def check_firmware(firmware_path, model):
    """檢查 firmware.bin 內容是否符合型號規則"""
    rule = RULES.get(model)
    if rule is None:
        return True, []

    with open(firmware_path, 'rb') as f:
        data = f.read()

    errors = []
    for pattern in rule['must_contain']:
        if pattern not in data:
            errors.append(f"missing '{pattern.decode()}'")
    for pattern in rule['must_not_contain']:
        if pattern in data:
            errors.append(f"should not contain '{pattern.decode()}'")

    return len(errors) == 0, errors


def compress_file(input_path, output_path, level=COMPRESSION_LEVEL):
    """壓縮單一檔案"""
    cctx = zstd.ZstdCompressor(level=level)

    with open(input_path, 'rb') as f_in:
        data = f_in.read()

    compressed = cctx.compress(data)

    with open(output_path, 'wb') as f_out:
        f_out.write(compressed)

    return len(data), len(compressed)


def get_model_from_path(bin_path):
    """從路徑提取型號 (es-pro / es-net)"""
    parts = bin_path.replace('\\', '/').split('/')
    for model in RULES:
        if model in parts:
            return model
    return None


def check_consistency():
    """檢查 firmware.json 與實際資料夾/firmware.bin 的一致性"""
    with open(FIRMWARE_JSON, 'r', encoding='utf-8') as f:
        data = json.load(f)

    errors = []

    # 從 firmware.json 收集所有已登錄的版本路徑
    json_entries = set()
    for product in data.get('product', []):
        path = product['path']
        for ver in product.get('versions', []):
            version_path = os.path.join(path, ver['version'])
            json_entries.add(version_path)

    # 檢查 firmware.json 有記錄，但資料夾或 firmware.bin 不存在
    for entry in sorted(json_entries):
        firmware_bin = os.path.join(entry, 'firmware.bin')
        if not os.path.isdir(entry):
            errors.append(f"firmware.json 有記錄但資料夾不存在: {entry}")
        elif not os.path.isfile(firmware_bin):
            errors.append(f"firmware.json 有記錄但 firmware.bin 不存在: {firmware_bin}")

    # 掃描實際存在的資料夾 + firmware.bin，檢查是否在 firmware.json 中有記錄
    for product in data.get('product', []):
        path = product['path']
        if not os.path.isdir(path):
            continue
        for version_dir in sorted(os.listdir(path)):
            version_path = os.path.join(path, version_dir)
            if not os.path.isdir(version_path):
                continue
            firmware_bin = os.path.join(version_path, 'firmware.bin')
            if os.path.isfile(firmware_bin) and version_path not in json_entries:
                errors.append(f"資料夾存在但 firmware.json 未記錄: {version_path}")

    return errors


def main():
    # 一致性檢查
    consistency_errors = check_consistency()
    if consistency_errors:
        print("Consistency errors:")
        for e in consistency_errors:
            print(f"  ERROR  {e}")
        print()
        sys.exit(1)

    bin_files = glob.glob(f'{FIRMWARE_DIR}/**/*.bin', recursive=True)

    if not bin_files:
        print(f"No .bin files found in {FIRMWARE_DIR}/")
        return

    total_original = 0
    total_compressed = 0
    skipped = 0
    compressed_count = 0
    errors_found = False

    for bin_file in sorted(bin_files):
        zst_file = bin_file + '.zst'
        filename = os.path.basename(bin_file)
        model = get_model_from_path(bin_file)

        # 檢查 firmware.bin 內容
        if filename == 'firmware.bin' and model:
            ok, errs = check_firmware(bin_file, model)
            if not ok:
                print(f"  ERROR  {bin_file}")
                for e in errs:
                    print(f"         {e}")
                errors_found = True
                continue

        # 已壓縮則跳過
        if os.path.isfile(zst_file):
            skipped += 1
            continue

        original_size, compressed_size = compress_file(bin_file, zst_file)
        ratio = (1 - compressed_size / original_size) * 100 if original_size > 0 else 0

        total_original += original_size
        total_compressed += compressed_size
        compressed_count += 1

        print(f"  OK     {bin_file}  {original_size:,} -> {compressed_size:,} ({ratio:.1f}%)")

    # 總結
    print()
    if errors_found:
        print("Some firmware files failed validation, not compressed.")
        sys.exit(1)

    if compressed_count == 0 and skipped > 0:
        print(f"All {skipped} files already compressed, nothing to do.")
    elif compressed_count > 0:
        print(f"Compressed {compressed_count} files, skipped {skipped}.")
        if total_original > 0:
            total_ratio = (1 - total_compressed / total_original) * 100
            print(f"Total: {total_original:,} -> {total_compressed:,} bytes ({total_ratio:.1f}%)")


if __name__ == '__main__':
    main()
