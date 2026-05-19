# 📦 วิธีให้เครื่องอื่นใช้งาน Excel Processor

## 🎯 สำหรับผู้ใช้ที่ 2 ขึ้นไป

### **ขั้นตอนที่ 1: เตรียมไฟล์ที่จะส่ง**

หลังจาก Build สำเร็จ (ได้ `.exe`) ให้ Copy ไฟล์เหล่านี้:

```
📁 ExcelProcessor_Package/
├── 📄 ExcelProcessor.exe          ← ไฟล์หลัก
├── 📄 config.json                 ← ไฟล์ตั้งค่า (ถ้าจำเป็น)
├── 📄 README_USAGE.md             ← คู่มือการใช้งาน
└── 📄 SETUP_PATHS.txt             ← คู่มือตั้งค่า Path
```

#### วิธี Copy ง่ายสุด:
```powershell
# บนเครื่องที่ Build เสร็จแล้ว
cd "c:\Users\USER\Desktop\Save to somewhere"

# สร้างโฟลเดอร์ package
mkdir "ExcelProcessor_Package"

# Copy ไฟล์ที่จำเป็น
copy "dist\ExcelProcessor.exe" "ExcelProcessor_Package\"
copy "config.json" "ExcelProcessor_Package\"
```

---

## 📤 **ขั้นตอนที่ 2: ส่งให้ผู้ใช้อื่น**

### ตัวเลือก A: ส่งผ่าน USB / Cloud
- Copy โฟลเดอร์ `ExcelProcessor_Package` ไปรวมกัน
- ส่ง USB / Google Drive / OneDrive เป็นต้น
- ผู้ใช้ extract และ double-click `ExcelProcessor.exe`

### ตัวเลือก B: ส่งผ่าน Network Drive
```powershell
# ผู้ใช้อื่นสามารถเข้าถึง network path
\\server\shared\ExcelProcessor_Package\ExcelProcessor.exe
```

### ตัวเลือก C: ส่งผ่าน Compressed File
```powershell
# บนเครื่องที่ Build
Compress-Archive -Path "ExcelProcessor_Package" -DestinationPath "ExcelProcessor_Package.zip"
# ส่ง ExcelProcessor_Package.zip ให้ผู้ใช้
```

---

## 🚀 **สำหรับผู้ใช้ที่จะรัน**

### **ขั้นตอนที่ 1: เตรียมไฟล์**

ได้รับไฟล์จาก:
- USB / Email / Cloud / Network Drive
- Extract (ถ้า .zip) ไปยังโฟลเดอร์ที่ต้องการ

```
📁 C:\Program Files\ExcelProcessor\
├── ExcelProcessor.exe
├── config.json
└── README_USAGE.md
```

### **ขั้นตอนที่ 2: ตั้งค่า Path (ครั้งแรกเท่านั้น)**

1. Double-click `ExcelProcessor.exe`
2. หน้าเว็บเปิดขึ้น → ขวาของหน้าจอ → กรอก Path เพื่อบันทึกไฟล์
3. คลิก "💾 บันทึกการตั้งค่า"
4. ตั้งค่านี้จะจำไว้ใน Browser LocalStorage

### **ขั้นตอนที่ 3: ใช้งาน**

1. Double-click `ExcelProcessor.exe` เพื่อเปิด
2. คลิก "เลือกไฟล์" → เลือกไฟล์ Excel
3. ระบบจะประมวลผลและบันทึกผลลัพธ์ไปยัง Path ที่ตั้งค่าไว้
4. เสร็จ!

---

## ⚙️ **สำหรับผู้จัดการ IT / Administrator**

### **ติดตั้งให้ Multiple Users**

#### วิธีที่ 1: Copy ไปยัง Shared Folder
```powershell
# บน Server
\\server\shared\Applications\ExcelProcessor\
```

ผู้ใช้ทั่วไปรัน:
```powershell
# From command line หรือ Shortcut
\\server\shared\Applications\ExcelProcessor\ExcelProcessor.exe
```

#### วิธีที่ 2: Install บน Machine ของแต่ละคน
```batch
REM สร้าง batch script ชื่อ install.bat
@echo off
if not exist "C:\Program Files\ExcelProcessor" mkdir "C:\Program Files\ExcelProcessor"
copy ExcelProcessor.exe "C:\Program Files\ExcelProcessor\"
copy config.json "C:\Program Files\ExcelProcessor\"
echo Installation complete!
pause
```

#### วิธีที่ 3: Create Shortcut ให้ User
```powershell
$WshShell = New-Object -ComObject WScript.Shell
$shortcut = $WshShell.CreateShortcut("$env:USERPROFILE\Desktop\ExcelProcessor.lnk")
$shortcut.TargetPath = "C:\Program Files\ExcelProcessor\ExcelProcessor.exe"
$shortcut.WorkingDirectory = "C:\Program Files\ExcelProcessor"
$shortcut.Save()
```

---

## 🔧 **Troubleshooting สำหรับผู้ใช้อื่น**

### ❌ "ExcelProcessor.exe ไม่เปิด"
- ตรวจสอบว่า Windows 10/11 (ต้องใช้ Windows 7 ขึ้นไป)
- ลองคลิกขวา → Properties → Unblock (บางที Windows จะ block file)

### ❌ "ไม่สามารถบันทึกไฟล์ได้"
- ตรวจสอบว่า Path ที่กรอกมีสิทธิ์ในการบันทึก
- ลองใช้ Path เช่น `C:\Users\[YourName]\Documents\ExcelData`

### ❌ "ไฟล์ Excel ไม่ถูกรู้จำ"
- ตรวจสอบไฟล์ .xlsx/.xls มีโครงสร้างถูกต้อง
- ต้องมี Column: "ReBplus" และ "1=SP,2=WH"

---

## 📋 **Checklist สำหรับผู้ส่ง**

- [ ] ได้ .exe file จากการ build
- [ ] Copy `ExcelProcessor.exe` + `config.json`
- [ ] สร้าง README สำหรับผู้ใช้
- [ ] ทดสอบรัน .exe ก่อนส่ง
- [ ] เตรียมเอกสารการตั้งค่า Path

---

## 💡 **Tips เพิ่มเติม**

### สร้าง Run Shortcut
```batch
@echo off
REM run-excel-processor.bat
start "" "C:\Program Files\ExcelProcessor\ExcelProcessor.exe"
```

### สร้าง Batch สำหรับตั้งค่า Paths
```batch
REM ให้ผู้ใช้เลือก Path ผ่าน Dialog
@echo off
echo.
echo ==== ExcelProcessor Path Configuration ====
echo.
set /p PATH_K1="Enter path for K1-SP (Branch 1): "
set /p PATH_K1_WH="Enter path for K1-WH (Warehouse): "
REM ... เก็บค่าไว้ที่ไหนสักที่
```

---

**✅ เสร็จ! ตอนนี้เครื่องอื่น ๆ สามารถใช้งาน ExcelProcessor ได้แล้ว** 🎉
