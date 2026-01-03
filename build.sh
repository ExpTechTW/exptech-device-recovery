#!/bin/bash

# ExpTech Device Recovery - Cross-platform Build Script
# Usage: ./build.sh

set -e

echo "=========================================="
echo "  ExpTech Device Recovery Build Script"
echo "=========================================="

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "Error: python3 not found"
    exit 1
fi

# Install dependencies
echo ""
echo "[1/3] Installing dependencies..."
pip3 install -r requirements.txt
pip3 install pyinstaller

# Build
echo ""
echo "[2/3] Building executable..."
pyinstaller build.spec --clean --noconfirm

# Result
echo ""
echo "[3/3] Build complete!"
echo ""
echo "Output location: dist/exptech-device-recovery"

# Platform-specific info
case "$(uname -s)" in
    Darwin*)
        echo "Platform: macOS"
        echo "Run: ./dist/exptech-device-recovery"
        ;;
    Linux*)
        echo "Platform: Linux"
        echo "Run: ./dist/exptech-device-recovery"
        ;;
    MINGW*|MSYS*|CYGWIN*)
        echo "Platform: Windows"
        echo "Run: dist\\exptech-device-recovery.exe"
        ;;
esac

echo ""
echo "Done!"
