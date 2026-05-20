@echo off
REM ==========================================
REM Build Desktop Application with PyInstaller
REM ==========================================

setlocal enabledelayedexpansion

cd /d "%~dp0"

echo.
echo ===============================================
echo  Building Desktop Application (.exe)
echo ===============================================
echo.

REM ใช้อินเทอร์พรีตเตอร์ Python หลักในเครื่อง
echo Using global Python environment...

echo.
echo Step 1: ติดตั้ง build dependencies...
pip install eel pyinstaller tkinter --quiet

echo.
echo Step 2: สร้างโฟลเดอร์ web และ copy files...
if exist "web" rmdir /s /q web
mkdir web
copy index.html web\ >nul 2>&1
copy script.js web\ >nul 2>&1
echo ✅ UI files ready

echo.
echo Step 3: ล้างการ build เก่า...
if exist "dist" rmdir /s /q dist
if exist "build" rmdir /s /q build
if exist "ExcelProcessor.spec" del ExcelProcessor.spec

echo.
echo Step 4: สร้าง .exe ด้วย PyInstaller...
echo.

python -m PyInstaller ^
    --name "ExcelProcessor" ^
    --onefile ^
    --windowed ^
    --add-data "web;web" ^
    --add-data "config.json;." ^
    --hidden-import=pandas ^
    --hidden-import=numpy ^
    --hidden-import=openpyxl ^
    --hidden-import=eel ^
    --collect-all=eel ^
    main.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ❌ Build failed - ตรวจสอบข้อความ error ด้านบน
    pause
    exit /b 1
)

echo.
echo ===============================================
echo  ✅ Build Complete!
echo ===============================================
echo.
echo 📁 Output: dist\ExcelProcessor.exe
echo.
echo วิธีใช้:
echo   1. ไปที่โฟลเดอร์ dist\
echo   2. Double-click ExcelProcessor.exe
echo   3. เสร็จ!
echo.
pause
