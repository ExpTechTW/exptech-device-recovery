@echo off
REM ExpTech Device Recovery - Windows Build Script
REM Usage: build.bat

echo ==========================================
echo   ExpTech Device Recovery Build Script
echo ==========================================

REM Check Python
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo Error: python not found
    exit /b 1
)

echo.
echo [1/3] Installing dependencies...
pip install -r requirements.txt
pip install pyinstaller

echo.
echo [2/3] Building executable...
pyinstaller build.spec --clean --noconfirm

echo.
echo [3/3] Build complete!
echo.
echo Output location: dist\exptech-device-recovery.exe
echo Run: dist\exptech-device-recovery.exe
echo.
echo Done!
pause
