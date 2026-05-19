# 🚀 Build Desktop Application - Quick Start

## ขั้นตอนที่ 1: ติดตั้ง Dependencies เพิ่มเติม

เปิด **PowerShell** ที่โฟลเดอร์นี้:

```powershell
cd "c:\Users\USER\Desktop\Save to somewhere"
venv\Scripts\activate

# ติดตั้ง Eel สำหรับ Desktop Application
pip install eel

# ติดตั้ง PyInstaller สำหรับ Build .exe
pip install pyinstaller

# ติดตั้ง tkinter (สำหรับ File Dialog) - มักจะมีอยู่แล้ว
python -m pip install --upgrade tkinter
```

## ขั้นตอนที่ 2: Build .exe

### วิธีที่ 1: ใช้ Batch Script (ง่ายที่สุด)

```powershell
# ยังอยู่ใน PowerShell
double-click build.bat
# หรือจากใน PowerShell
.\build.bat
```

### วิธีที่ 2: รันคำสั่ง PyInstaller โดยตรง

```powershell
# สร้างโฟลเดอร์ web
mkdir web
copy index.html web\
copy script.js web\

# Build .exe
python -m PyInstaller `
    --name "ExcelProcessor" `
    --onefile `
    --windowed `
    --add-data "web;web" `
    --add-data "config.json;." `
    --hidden-import=pandas `
    --hidden-import=numpy `
    --hidden-import=openpyxl `
    --hidden-import=eel `
    --collect-all=eel `
    main.py
```

## ขั้นตอนที่ 3: ทดสอบ .exe

ไฟล์ .exe จะอยู่ที่: `dist\ExcelProcessor.exe`

```powershell
# ทดสอบรัน
.\dist\ExcelProcessor.exe
```

## 📦 ดิสทริบิวต์ผลิตภัณฑ์ (Distribution)

### สำหรับผู้ใช้งาน:
ให้เขา copy ไฟล์เหล่านี้ไปรวมกันในโฟลเดอร์:
- `dist\ExcelProcessor.exe` (ไฟล์หลัก)
- `config.json` (ถ้าจำเป็น)

หลังจากนั้นให้เขา double-click `ExcelProcessor.exe` เพื่อรัน

### ทำให้ .exe พกพาได้ง่ายขึ้น:
```powershell
# Copy ไฟล์ที่จำเป็นไป dist\
copy config.json dist\
copy README.md dist\

# ตอนนี้ user สามารถ copy เฉพาะโฟลเดอร์ dist\ ไปได้เลย
```

## ⚠️ ปัญหาที่อาจเกิด

### ❌ "ModuleNotFoundError: No module named 'eel'"
```powershell
pip install eel
python -m PyInstaller ... --collect-all=eel main.py
```

### ❌ "No module named 'pandas'"
```powershell
# เพิ่ม --hidden-import
python -m PyInstaller ... --hidden-import=pandas --hidden-import=numpy --hidden-import=openpyxl main.py
```

### ❌ "web/index.html not found"
```powershell
# ตรวจสอบว่า web\ โฟลเดอร์มีไฟล์:
dir web\
# ต้องมี: index.html, script.js
```

## ✅ คำสั่ง Copy-Paste พร้อม

ถ้ายังไม่ติดตั้ง PyInstaller:

```powershell
cd "c:\Users\USER\Desktop\Save to somewhere"
venv\Scripts\activate
pip install eel pyinstaller
.\build.bat
```

---

**เสร็จแล้ว! ไฟล์ .exe จะอยู่ที่ `dist\ExcelProcessor.exe`** 🎉
