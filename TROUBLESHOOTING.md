# 🆘 Troubleshooting Guide - แก้ปัญหา

## สารบัญ
1. [Backend Issues](#backend-issues)
2. [Frontend Issues](#frontend-issues)
3. [File Processing Issues](#file-processing-issues)
4. [LocalStorage Issues](#localstorage-issues)
5. [General Issues](#general-issues)

---

## Backend Issues

### ❌ `Failed to build 'pandas'` or `Building wheel for pandas ... error`

**สาเหตุ**: Windows ไม่มี C++ build tools หรือ pre-built wheels ไม่พร้อม

**วิธีแก้** (ทำตามลำดับ):

**ตัวเลือกที่ 1: ใช้ Pre-built Wheels (ง่ายที่สุด)**
```powershell
pip install --only-binary :all: pandas numpy openpyxl
```

**ตัวเลือกที่ 2: รัน Fix Script**
```powershell
double-click fix-pandas.bat
# หรือใน PowerShell
python fix-pandas.bat
```

**ตัวเลือกที่ 3: ติดตั้ง Visual C++ Build Tools**
- ดาวน์โหลด: https://visualstudio.microsoft.com/downloads/
- ค้นหา "Visual Studio Build Tools"
- ติดตั้งพร้อม "Desktop development with C++"
- Restart เครื่อง
- ลองใหม่: `pip install pandas`

**ตัวเลือกที่ 4: ใช้ Conda** (ถ้า installed)
```powershell
conda install pandas numpy openpyxl
```

📖 อ่านเพิ่มเติม: [FIX_PANDAS_ERROR.md](FIX_PANDAS_ERROR.md)

---

**สาเหตุ**: FastAPI ยังไม่ติดตั้ง

**วิธีแก้**:
```powershell
cd "c:\Users\USER\Desktop\Save to somewhere"
venv\Scripts\activate
pip install -r requirements.txt
```

---

### ❌ `Address already in use: ('0.0.0.0', 8000)`

**สาเหตุ**: Port 8000 ถูกใช้งานโดยโปรแกรมอื่น

**วิธีแก้**:

**ตัวเลือกที่ 1**: ปิดโปรแกรมที่ใช้ port นี้
```powershell
netstat -ano | findstr :8000
taskkill /PID <PID> /F
```

**ตัวเลือกที่ 2**: เปลี่ยน Port ใน `app.py`
```python
# บรรทัดสุดท้ายของ app.py
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9000, reload=True)  # เปลี่ยน 8000 เป็น 9000
```

แล้วอัปเดต `script.js`:
```javascript
// บรรทัด 3
const API_BASE_URL = 'http://localhost:9000';  // เปลี่ยนเป็น 9000
```

---

### ❌ Backend รัน แต่ Frontend ไม่ได้เชื่อมต่อ

**สาเหตุ**: CORS ถูก block หรือ URL ผิด

**วิธีแก้**:

1. ตรวจสอบ URL ใน Browser Console (F12):
   ```javascript
   const API_BASE_URL = 'http://localhost:8000';
   console.log("API URL:", API_BASE_URL);
   ```

2. ตรวจสอบ CORS settings ใน `app.py`:
   ```python
   app.add_middleware(
       CORSMiddleware,
       allow_origins=["*"],  # ควรอนุญาตทั้งหมด
       allow_methods=["*"],
       allow_headers=["*"],
   )
   ```

---

## Frontend Issues

### ❌ `Cannot connect to API`

**สาเหตุ**: Backend ไม่ทำงานหรือ URL ผิด

**วิธีแก้**:

1. ตรวจสอบว่า Backend ทำงานอยู่:
   - Terminal แสดง `Uvicorn running on http://0.0.0.0:8000`

2. ทดสอบ API ด้วย curl:
   ```powershell
   curl http://localhost:8000/health
   ```

3. ตรวจสอบ URL ใน `script.js` บรรทัด 3:
   ```javascript
   const API_BASE_URL = 'http://localhost:8000';
   ```

---

### ❌ Dropzone ไม่ทำงาน

**สาเหตุ**: JavaScript มีข้อผิดพลาด หรือไฟล์ `script.js` ไม่โหลด

**วิธีแก้**:

1. เปิด Browser Console (F12 → Console)
2. ตรวจสอบข้อความ error
3. ตรวจสอบว่า `script.js` มีในโฟลเดอร์เดียวกับ `index.html`

---

### ❌ Dropzone แสดง "⏳ กำลังประมวลผล..." แต่ไม่เสร็จ

**สาเหตุ**: Backend ไม่ตอบสนอง หรือ timeout

**วิธีแก้**:

1. ตรวจสอบ Backend logs (Terminal ที่รัน Backend)
2. ตรวจสอบว่าไฟล์ Excel มีขนาดใหญ่เกินไปหรือไม่
3. ลองไฟล์ขนาดเล็กก่อน

---

## File Processing Issues

### ❌ `ตรวจพบค่า '0' ในคอลัมน์ 1=SP,2=WH`

**สาเหตุ**: ไฟล์ Excel มีข้อมูลที่ไม่ถูกต้อง

**วิธีแก้**:

1. เปิดไฟล์ Excel
2. ตรวจหาคอลัมน์ "1=SP,2=WH"
3. ค้นหาค่า "0" และแก้ไข (ต้องเป็น 1 หรือ 2)

---

### ❌ `ไม่พบโครงสร้างรหัสสาขาที่ถูกต้องในไฟล์`

**สาเหตุ**: ไฟล์ Excel ไม่มีคอลัมน์ "ReBplus" หรือโครงสร้างผิด

**วิธีแก้**:

1. ตรวจสอบว่าไฟล์มีคอลัมน์ชื่อ "ReBplus" หรือไม่
2. ตรวจสอบว่า ReBplus มีรูปแบบ: `code1,code2,code3,...`
3. ตรวจสอบว่ารหัสตำแหน่งที่ 2 (หลังจากสปลิต comma) เป็น 11, 21, 31, 41, 51, หรือ 00

---

### ❌ `ไม่มีข้อมูลที่ตรงกับเงื่อนไข`

**สาเหตุ**: ไฟล์มีข้อมูล แต่ไม่ตรงกับเงื่อนไขการกรอง

**วิธีแก้**:

1. ตรวจสอบคอลัมน์ "1=SP,2=WH" มีค่า 1 หรือ 2 หรือไม่
2. ตรวจสอบ ReBplus มีรหัสสาขาที่ตรงกัน (11, 21, 31, 41, 51 หรือ 00)

---

### ❌ ไฟล์ output ไม่ถูกบันทึก

**สาเหตุ**: Path ไม่ถูกต้อง หรือไม่มีสิทธิ์

**วิธีแก้**:

1. ตรวจสอบ Path ที่กรอก:
   - ต้องเป็น path แบบเต็ม เช่น `C:\Users\USER\Desktop\K1`
   - ไม่ใช่ path ไม่สมบูรณ์ เช่น `Desktop\K1`

2. ตรวจสอบสิทธิ์การบันทึก:
   - ทดสอบการสร้างไฟล์ใน path นั้นด้วยตัวเอง

3. ตรวจสอบว่าโฟลเดอร์มีอยู่:
   - ระบบจะสร้างอัตโนมัติ ถ้ามีสิทธิ์

---

## LocalStorage Issues

### ❌ Path ไม่ถูกบันทึก

**สาเหตุ**: LocalStorage ถูก disable หรือ Private Browsing mode

**วิธีแก้**:

1. ตรวจสอบ Browser Settings:
   - Chrome: Settings → Privacy → Cookies → ตรวจสอบการตั้งค่า
   - Firefox: Preferences → Privacy → Enhanced Tracking Protection

2. ปิด Private/Incognito mode

3. ลองเบราว์เซอร์อื่น

---

### ❌ Path หายไป เมื่อเปิด Browser ใหม่

**สาเหตุ**: Browser clear cache หรือ LocalStorage ถูก delete

**วิธีแก้**:

1. ตรวจสอบว่า Browser clear cache โดยอัตโนมัติ หรือไม่
2. อย่าลบ Browser data ระหว่างการใช้งาน
3. ใช้ Browser เดียวกัน ทุกครั้ง

---

### ✅ ตรวจสอบ LocalStorage

เปิด Browser Console (F12 → Application → LocalStorage):

```javascript
// ดูค่า LocalStorage
localStorage.getItem('pathsConfig')

// บันทึก test
localStorage.setItem('test', 'value')

// ลบข้อมูล (ถ้าต้องการ reset)
localStorage.removeItem('pathsConfig')
```

---

## General Issues

### ❌ `ImportError: cannot import name 'pd'`

**วิธีแก้**:
```powershell
pip install pandas
```

---

### ❌ ไฟล์ Excel เปิด error `UnicodeDecodeError`

**สาเหตุ**: Encoding ผิด

**วิธีแก้**: ลองบันทึกไฟล์ใหม่ด้วย UTF-8 encoding

---

### ❌ Browser ไม่เปิด index.html

**วิธีแก้**:

1. คลิก Ctrl+O ใน Browser
2. เลือก `index.html` จาก `c:\Users\USER\Desktop\Save to somewhere`
3. หรือ drag index.html ไปวาง browser tab

---

## 🔧 Advanced Troubleshooting

### ตรวจสอบ Network ใน Browser

1. F12 → Network tab
2. ลากไฟล์ลงใน Dropzone
3. ดูว่า request ไป `/upload` endpoint ถูกต้องหรือไม่
4. ตรวจสอบ Response code (200 = success, 400 = error)

---

### เปิดใช้ Debug Mode

**ใน `app.py`**:
```python
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True, log_level="debug")
```

---

### ตรวจสอบ Logs

**ใน `script.js`** เพิ่ม console.log:
```javascript
async function uploadFile(file) {
    console.log("Uploading file:", file.name);
    console.log("Paths config:", getCurrentPathsConfig());
    
    // ... rest of code
}
```

---

## 📞 ต้องการความช่วยเหลือเพิ่มเติม?

1. ตรวจสอบ Browser Console (F12)
2. ตรวจสอบ Backend Terminal logs
3. ลองใหม่หลังจาก restart Backend
4. ลองใหม่หลังจาก clear Browser cache

---

**หวังว่าปัญหาของคุณจะแก้ไขได้! 🎉**
