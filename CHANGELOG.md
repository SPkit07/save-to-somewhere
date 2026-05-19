# 🔧 ข้อมูลการแก้ไข Excel Processor

## แก้ไขลักษณะการทำงาน

### ปัญหาเดิม:
- ใส่ไฟล์ Excel ไม่ได้
- ไม่มีการ Preview ก่อน Process

### แก้ไขใหม่:
1. ✅ **Preview Modal** - แสดงสรุปข้อมูลไฟล์ก่อนประมวลผล:
   - ชื่อไฟล์
   - จำนวนแถวทั้งหมด
   - สาขาที่ตรวจพบ
   - จำนวน SP (หน้าร้าน) vs WH (โกดัง)

2. ✅ **File Dialog** - เปิด Windows File Dialog ให้เลือก Excel
   - แก้ tkinter attributes('-topmost') เพื่อให้ dialog อยู่บน

3. ✅ **Confirm Button** - ผู้ใช้ต้อง click "ยืนยันและประมวลผล" ก่อนจึงจะประมวลผลจริง ๆ

---

## ไฟล์ที่แก้ไข:

| ไฟล์ | การแก้ไข |
|-----|--------|
| `main.py` | + `preview_excel_file()` function, แก้ `select_file_dialog()` |
| `script.js` | + `previewFile()`, `showPreviewModal()`, `confirmProcess()` |
| `index.html` | + Preview Modal HTML & CSS |
| `requirements.txt` | + eel library |

---

## วิธีใช้งานใหม่:

1. Double-click `ExcelProcessor.exe`
2. ฝั่งขวา → กรอก Path เพื่อตั้งค่า
3. Click "เลือกไฟล์" → File Dialog เปิด
4. เลือกไฟล์ Excel → Modal แสดงสรุป (จำนวนแถว, สาขา, SP/WH)
5. Click "✅ ยืนยันและประมวลผล" → ประมวลผลจริง ๆ
6. แสดงผลลัพธ์ ✅

---

## ทดสอบ:

ต้องรัน:
```powershell
cd "c:\Users\USER\Desktop\Save to somewhere"
venv\Scripts\activate
python main.py
```

หรือ build .exe ใหม่:
```powershell
.\build.bat
```

---

## บันทึก:
- File Dialog ใช้ tkinter (included ใน Python)
- Preview อ่าน Excel อย่างรวดเร็ว (ไม่ upload)
- ทั้งหมด offline ทำงาน โดยไม่ต้อง internet
