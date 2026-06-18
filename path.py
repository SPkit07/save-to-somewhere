from datetime import datetime
import os

# 1. กำหนด Path ปลายทาง (ใส่ r ข้างหน้าเพื่อป้องกันปัญหา Backslash)
PATHS = {
    "11": r"C:\Users\USER\Desktop\11",
    "11_00": r"C:\Users\USER\Desktop\1100",
    "21": r"C:\Users\USER\Desktop\21",
    "21_00": r"C:\Users\USER\Desktop\2100",
    "31": r"C:\Users\USER\Desktop\31",
    "31_00": r"C:\Users\USER\Desktop\3100",
    "41": r"C:\Users\USER\Desktop\41",
    "41_00": r"C:\Users\USER\Desktop\4100",
    "51": r"C:\Users\USER\Desktop\51",
    "51_00": r"C:\Users\USER\Desktop\5100",
    "SP": r"C:\Users\USER\Desktop\SP00"
}

# 2. ดึงเดือน และ ปีปัจจุบัน (ค.ศ.) แล้วแปลงเป็น พ.ศ.
now = datetime.now()
current_month = now.strftime("%m")  # ได้เป็น "01", "02", ...
current_year_th = (
    now.year + 543
)  # แปลง ค.ศ. เป็น พ.ศ. (เช่น 2026 + 543 = 2569)

# 3. ตั้งชื่อ Folder ตามรูปแบบ "MM-YYYY" (เช่น 06-2569)
folder_name = f"{current_month}-{current_year_th}"

# 4. รวม Path ปลายทางกับชื่อ Folder ใหม่
target_path = os.path.join(base_path, folder_name)

# 5. สั่งสร้าง Folder (ใช้ exist_ok=True เพื่อไม่ให้ฟ้อง Error ถ้ามี Folder นั้นอยู่แล้ว)
os.makedirs(target_path, exist_ok=True)

print(f"Folder ถูกสร้างหรือพร้อมใช้งานที่: {target_path}")