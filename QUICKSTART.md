# 🚀 เริ่มต้นอย่างรวดเร็ว (Quick Start)

## เล่มนี้ทำให้คุณเริ่มต้นใช้งานได้ใน 5 นาที ✨

---

## ขั้นตอนที่ 1: ติดตั้ง Backend (ครั้งแรกเท่านั้น)

เปิด **PowerShell** แล้วรันคำสั่ง:

```powershell
cd "c:\Users\USER\Desktop\Save to somewhere"
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

> ⚠️ **If you get "Failed to build 'pandas'" error:**
> 
> ```powershell
> pip install --only-binary :all: pandas numpy openpyxl
> pip install -r requirements.txt
> ```
> 
> Or simply: `double-click fix-pandas.bat`
> 
> For detailed solutions: See [FIX_PANDAS_ERROR.md](FIX_PANDAS_ERROR.md)

> ✅ เสร็จแล้ว! ข้ามไปขั้นตอนที่ 2

---

## ขั้นตอนที่ 2: เปิดใช้งาน Backend (ทุกครั้งที่ใช้งาน)

### วิธีที่ 1: ใช้ PowerShell
```powershell
cd "c:\Users\USER\Desktop\Save to somewhere"
venv\Scripts\activate
python app.py
```

### วิธีที่ 2: ใช้ไฟล์ Batch (สำหรับคนรักความสะดวก)

สร้างไฟล์ชื่อ `run-backend.bat` ในโฟลเดอร์เดียวกัน:

```batch
@echo off
cd /d "%~dp0"
call venv\Scripts\activate
python app.py
pause
```

จากนั้น Double-click ไฟล์นี้เพื่อเปิด Backend

---

## ขั้นตอนที่ 3: เปิดหน้าเว็บ

1. ไปที่ `c:\Users\USER\Desktop\Save to somewhere`
2. Double-click ไฟล์ `index.html`
3. หน้าเว็บจะเปิดในเบราว์เซอร์โดยอัตโนมัติ

---

## ขั้นตอนที่ 4: ใช้งาน

### ครั้งแรก:
1. **ขวา** → กรอก Path สำหรับแต่ละสาขา
2. คลิก **"💾 บันทึกการตั้งค่า"**

### ครั้งต่อไป:
1. ลาก `.xlsx` ลงในกล่อง **Dropzone**
2. รอสักครู่แล้ว ✅ เสร็จ!

---

## 🔗 URL เว็บ

- **ปกติ** (ไฟล์ local):
  ```
  file:///c:/Users/USER/Desktop/Save%20to%20somewhere/index.html
  ```

- **ถ้าอยากรัน Backend บน localhost** (ตัวเลือก):
  - ติดตั้ง [Live Server extension](https://marketplace.visualstudio.com/items?itemName=ritwickdey.LiveServer) ใน VS Code
  - Right-click `index.html` → Open with Live Server

---

## ⚠️ ตรวจสอบก่อนใช้งาน

- [ ] Backend ทำงานอยู่ (Terminal แสดง "running on http://0.0.0.0:8000")
- [ ] ไฟล์ `index.html`, `script.js`, `app.py` มีทั้งหมด
- [ ] Path ที่กรอกถูกต้องและมีสิทธิ์ในการบันทึก

---

## 📝 หมายเหตุเพิ่มเติม

| ฟีเจอร์ | รายละเอียด |
|--------|----------|
| **LocalStorage** | บันทึก Path ที่ผู้ใช้กรอก - ไม่ต้องกรอกซ้ำ |
| **Drag & Drop** | ลากไฟล์มาโดยไม่ต้องเลือกจาก Explorer |
| **Auto-detect Branch** | ตรวจพบสาขาโดยอัตโนมัติ |
| **Date Suffix** | ชื่อไฟล์ output พร้อมวันที่อัตโนมัติ |

---

## 🆘 ปัญหาทั่วไป

| ปัญหา | วิธีแก้ |
|------|--------|
| **"Cannot connect to API"** | ตรวจสอบว่า Backend ทำงานอยู่ หรือตรวจสอบ URL ใน `script.js` |
| **"ไฟล์ไม่ถูกต้อง"** | ตรวจสอบว่าไฟล์ Excel มีโครงสร้างถูกต้อง (มีคอลัมน์ "ReBplus") |
| **"LocalStorage ไม่บันทึก"** | ลองเปิด Browser DevTools (F12) → Application → LocalStorage → ตรวจสอบค่า |

---

**🎉 เอาล่ะ! คุณพร้อมแล้ว ลองใช้งานกันเลย!**
