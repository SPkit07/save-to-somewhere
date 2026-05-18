"""
Integration Example: ใช้ App.py กับ Jupyter Notebook เดิม

วิธีการ:
1. ย้ายฟังก์ชัน process_excel_file() จาก app.py
2. Import ใน notebook
3. ใช้ฟังก์ชันนี้แทน code เดิม
"""

# ==================== ในตัวอย่าง Python Script ====================
from app import process_excel_file
import json

# ตัวอย่าง 1: ใช้ Path เริ่มต้น
result = process_excel_file(
    file_path=r"C:\Users\USER\Desktop\K1.xlsx",
    paths_config={}  # ใช้ DEFAULT_PATHS
)
print(result)

# ตัวอย่าง 2: ใช้ Path ที่ผู้ใช้กรอก
user_paths = {
    "11": r"C:\Users\USER\Custom\K1-SP",
    "11_00": r"C:\Users\USER\Custom\K1-WH",
}
result = process_excel_file(
    file_path=r"C:\Users\USER\Desktop\K1.xlsx",
    paths_config=user_paths
)
print(result)

# ==================== ในตัวอย่าง Jupyter Notebook ====================
# ใน cell เดียวกับ import
# from app import process_excel_file

# # จากนั้นใช้แทน code เดิม:
# result = process_excel_file(
#     file_path=r"C:\Users\USER\Desktop\K1.xlsx",
#     paths_config={
#         "11": r"C:\Users\USER\Desktop\11",
#         "11_00": r"C:\Users\USER\Desktop\1100",
#     }
# )
# print(result['message'])
# if result['success']:
#     for file in result['files_saved']:
#         print(f"  {file}")
