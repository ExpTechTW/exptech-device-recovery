#!/usr/bin/env python3
"""
Zstandard 高壓縮率壓縮工具
掃描 firmware 目錄下所有 .bin 檔案並壓縮為 .bin.zst
"""

import os
import sys
import glob

try:
    import zstandard as zstd
except ImportError:
    print("❌ 請先安裝 zstandard：pip install zstandard")
    sys.exit(1)

FIRMWARE_DIR = 'firmware'
COMPRESSION_LEVEL = 22  # 最高壓縮率 (1-22)


def compress_file(input_path, output_path, level=COMPRESSION_LEVEL):
    """壓縮單一檔案"""
    cctx = zstd.ZstdCompressor(level=level)

    with open(input_path, 'rb') as f_in:
        data = f_in.read()

    compressed = cctx.compress(data)

    with open(output_path, 'wb') as f_out:
        f_out.write(compressed)

    return len(data), len(compressed)


def main():
    print("=" * 50)
    print("🗜️  Zstandard 高壓縮率工具")
    print(f"   壓縮等級: {COMPRESSION_LEVEL} (最高)")
    print("=" * 50)

    # 掃描所有 .bin 檔案
    bin_files = glob.glob(f'{FIRMWARE_DIR}/**/*.bin', recursive=True)

    if not bin_files:
        print(f"\n⚠️  在 {FIRMWARE_DIR}/ 目錄下未找到任何 .bin 檔案")
        return

    print(f"\n📁 找到 {len(bin_files)} 個 .bin 檔案：\n")

    total_original = 0
    total_compressed = 0

    for bin_file in bin_files:
        zst_file = bin_file + '.zst'

        print(f"   壓縮中: {bin_file}")

        original_size, compressed_size = compress_file(bin_file, zst_file)
        ratio = (1 - compressed_size / original_size) * 100 if original_size > 0 else 0

        total_original += original_size
        total_compressed += compressed_size

        print(f"   ✅ {original_size:,} → {compressed_size:,} bytes ({ratio:.1f}% 減少)")
        print(f"      輸出: {zst_file}\n")

    # 總結
    print("=" * 50)
    print("📊 壓縮總結：")
    print(f"   • 原始大小: {total_original:,} bytes ({total_original / 1024 / 1024:.2f} MB)")
    print(f"   • 壓縮後:   {total_compressed:,} bytes ({total_compressed / 1024 / 1024:.2f} MB)")

    if total_original > 0:
        total_ratio = (1 - total_compressed / total_original) * 100
        print(f"   • 壓縮率:   {total_ratio:.1f}%")

    print("=" * 50)


if __name__ == '__main__':
    main()
