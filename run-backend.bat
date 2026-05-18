@echo off
REM เปิด Backend อัตโนมัติ
echo.
echo ===============================================
echo   Excel Processor - Backend Launcher
echo ===============================================
echo.

cd /d "%~dp0"

REM ตรวจสอบว่า venv มีอยู่หรือไม่
if not exist "venv\Scripts\activate.bat" (
    echo ⚠️  Virtual Environment ยังไม่ได้สร้าง
    echo กำลังสร้าง venv และติดตั้ง dependencies...
    echo.
    python -m venv venv
    call venv\Scripts\activate.bat
    pip install -r requirements.txt
    echo.
)

echo ✅ เปิดใช้งาน Virtual Environment...
call venv\Scripts\activate.bat

echo.
echo ⏳ เปิด Backend...
echo.
python app.py

pause
