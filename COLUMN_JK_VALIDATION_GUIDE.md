# Column J & K Validation Feature - Implementation Guide

## Summary of Changes

เพิ่มฟังก์ชันการตรวจสอบคอลัมน์ J และ K (ทั้งสองคอลัมน์มีชื่อ "1=SP,2=WH") ว่าค่าตรงกันหรือไม่

### Features Added

✅ **Automatic Column J & K Validation**
- ตรวจสอบอัตโนมัติว่าคอลัมน์ J (SP) และคอลัมน์ K (WH) ตรงกันหรือไม่
- แสดงรายการสินค้าที่ไม่ตรงกันในรูปแบบตาราง
- ระบุรหัสสินค้า (GOODS_CODE) และชื่อสินค้า (SKU_NAME) ที่มีปัญหา

✅ **Enhanced Error Reporting**
- แสดงคำเตือนในรูปแบบตาราง (Table) ที่เรียบร้อย
- แสดงทั้ง คอลัมน์ J และ K ที่มีค่าไม่ตรงกัน
- สนับสนุนการตรวจสอบหลายรายการ (multiple errors)

✅ **User-Friendly Display**
- แสดงคำเตือนในหน้าต่าง Modal ก่อนผลสรุป
- ใช้สีเหลือง (Warning) สำหรับการแจ้งเตือน
- เน้นแถวที่มีปัญหาด้วยพื้นหลังสีแดงอ่อน

---

## Files Modified

### 1. **processors.py**
เพิ่มฟังก์ชันใหม่ `check_columns_j_k_match()`:

```python
def check_columns_j_k_match(df: pd.DataFrame) -> Tuple[bool, list]:
    """
    ตรวจสอบว่าคอลัมน์ J และ K (ทั้งคู่มีชื่อ '1=SP,2=WH') ตรงกันหรือไม่
    
    Returns:
        - bool: True ถ้าทั้งหมดตรงกัน, False ถ้ามีที่ไม่ตรง
        - list: รายละเอียด error details
    """
```

**ฟีเจอร์:**
- หาคอลัมน์ J และ K โดยค้นหาชื่อ "1=SP,2=WH"
- แปลงค่าให้เป็นสตริง และลบ .0 (จากการแปลง float)
- ตัดช่องว่างและเปรียบเทียบ
- ดึง GOODS_CODE และ SKU_NAME (หรือ Column F)
- สร้างรายละเอียด error สำหรับแต่ละแถวที่ไม่ตรง

### 2. **main.py** (Desktop Application)
ไม่มีการแก้ไขสำคัญ แต่ response ตอนนี้จะรวม warnings

### 3. **web/index.html**
เพิ่ม:
- CSS styling สำหรับ warning table และ warning modal
- Modal element `warningModal` สำหรับแสดงตาราง warning

### 4. **web/script.js**
เพิ่มฟังก์ชันใหม่:
- `closeWarningModal()` - ปิด warning modal
- `displayWarningsModal(warnings)` - แสดงตาราง warnings
- `displayErrorDetailsModal(title, errorDetails)` - แสดงรายละเอียด error

อัปเดตฟังก์ชัน:
- `confirmProcess()` - เพิ่มการแสดง warnings เมื่อมี

---

## How It Works

### Backend Flow (processors.py)

1. **Read Excel File**
   ```
   df = pd.read_excel(file_path)
   ```

2. **Check Column J & K Match**
   ```
   j_k_match, j_k_mismatches = check_columns_j_k_match(df)
   warnings = []
   ```

3. **If Mismatches Found**
   - สร้าง warning object
   - เพิ่มลงใน warnings list
   - ไม่หยุดการประมวลผล (continue processing)

4. **Return Response**
   ```json
   {
       "success": true,
       "message": "ประมวลผลสำเร็จ!",
       "warnings": [
           {
               "type": "j_k_mismatch",
               "message": "⚠️ [WARNING]: ตรวจพบความไม่ตรงกันในคอลัมน์ J และ K (5 รายการ)",
               "details": [
                   {
                       "row": 2,
                       "goods_code": "SKU001",
                       "sku_name": "สินค้า A",
                       "col_j": "1",
                       "col_k": "2"
                   },
                   ...
               ]
           }
       ],
       "has_warnings": true,
       ...
   }
   ```

### Frontend Flow (script.js)

1. **Show Preview Modal**
   - แสดงข้อมูลพื้นฐาน

2. **User Confirms Processing**
   - `confirmProcess()` ถูกเรียก

3. **Process File**
   - รอ response จาก backend

4. **If Warnings Exist**
   - เรียก `displayWarningsModal(warnings)`
   - แสดง modal ด้วยตาราง

5. **Display Table**
   - ตารางแสดง: รหัสสินค้า, ชื่อสินค้า, J, K
   - แถวที่ไม่ตรงจะมีพื้นหลังสีแดงอ่อน

---

## Table Format

```
+---+------------------+-------------+--------+--------+
| # | รหัสสินค้า       | ชื่อสินค้า  | Col J  | Col K  |
+---+------------------+-------------+--------+--------+
| 1 | SKU001           | สินค้า A    | 1(🔴)  | 2(🔴)  |
| 2 | SKU002           | สินค้า B    | 1(🔴)  | 2(🔴)  |
+---+------------------+-------------+--------+--------+
```

---

## Column Detection Logic

### ค้นหา GOODS_CODE:
- ใช้คอลัมน์ที่ชื่อ `"GOODS_CODE"`

### ค้นหา SKU_NAME / Product Name:
1. SKU_NAME
2. GOODS_NAME
3. PRODUCT_NAME
4. ITEM_NAME
5. ชื่อสินค้า
6. GOODS_DESC
7. Fallback: Column F (index 5)

### ค้นหา Column J & K:
- ค้นหาคอลัมน์ที่มีชื่อ `"1=SP,2=WH"`
- Pandas จะตั้งชื่อเป็น `"1=SP,2=WH"` และ `"1=SP,2=WH.1"` (ถ้าซ้ำกัน)

---

## Data Cleaning & Comparison

```python
# ลบช่องว่าง และ .0 (จากการแปลง float)
val_j = df[col_j].fillna("").astype(str).str.strip().str.replace(r'\.0$', '', regex=True)
val_k = df[col_k].fillna("").astype(str).str.strip().str.replace(r'\.0$', '', regex=True)

# เปรียบเทียบ
mismatch_mask = val_j != val_k
```

---

## Example Usage

### Input Excel File:
```
| GOODS_CODE | SKU_NAME   | ... | 1=SP,2=WH | 1=SP,2=WH.1 |
|------------|-----------|-----|-----------|------------|
| SKU001     | Product A | ... | 1         | 2          | ❌ Mismatch
| SKU002     | Product B | ... | 2         | 2          | ✅ Match
| SKU003     | Product C | ... | 1         | 1          | ✅ Match
```

### Output (Warnings):
```
⚠️ ตรวจพบความไม่ตรงกันในคอลัมน์ J และ K (1 รายการ)

| # | รหัสสินค้า | ชื่อสินค้า | J | K |
|---|----------|----------|---|---|
| 1 | SKU001   | Product A| 1 | 2 |
```

---

## Configuration Notes

✅ **No Additional Configuration Needed**
- ฟังก์ชันทำงานอัตโนมัติ
- ไม่ต้องตั้งค่าเพิ่มเติม

✅ **Processing Continues**
- แม้มี warnings ก็ยังประมวลผลต่อ
- ไม่ถูกหยุดการบันทึกไฟล์

✅ **Multiple Errors Supported**
- สนับสนุนการแสดง error หลายตัว
- แสดงในรูปแบบตาราง

---

## Testing Checklist

- [ ] ตรวจสอบไฟล์ที่มี Column J & K ตรงกันทั้งหมด → ไม่ต้องแสดง warning
- [ ] ตรวจสอบไฟล์ที่มี Column J & K ไม่ตรงกัน → แสดง warning table
- [ ] ตรวจสอบจำนวน warning ถูกต้อง
- [ ] ตรวจสอบ GOODS_CODE และ SKU_NAME ถูกต้อง
- [ ] ตรวจสอบค่า Column J & K แสดงถูกต้อง
- [ ] ตรวจสอบไฟล์ยังคงบันทึกได้แม้มี warning

---

## Support for Thai Characters

✅ ทั้งหมดใช้ UTF-8 encoding
✅ รองรับ Thai text ทั้งหมด
✅ ตัวเลขและตัวอักษร display ถูกต้อง

---

## Notes

- ฟังก์ชัน `check_columns_j_k_match()` จะ return `(True, [])` ถ้าหา column ได้แต่ไม่มี mismatches
- ถ้าเกิดข้อผิดพลาด จะ log ข้อมูล และ return `(True, [])` เพื่อไม่ให้หยุดการประมวลผล
- ค่า 0 ในคอลัมน์ "1=SP,2=WH" จะถูก reject ก่อนการตรวจสอบ J & K
