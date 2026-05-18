"""
Test Script - ตรวจสอบการตั้งค่า
รัน script นี้เพื่อตรวจสอบว่าทุกอย่างถูกตั้งค่าถูกต้องหรือไม่
"""

import os
import sys
import json
import subprocess
from pathlib import Path

def print_header(text):
    print("\n" + "="*60)
    print(f"  {text}")
    print("="*60 + "\n")

def check_file(path, name):
    """ตรวจสอบว่าไฟล์มีอยู่หรือไม่"""
    if os.path.exists(path):
        print(f"  ✅ {name}: มี")
        return True
    else:
        print(f"  ❌ {name}: ไม่มี")
        return False

def check_python_module(module_name):
    """ตรวจสอบว่า Python package มีอยู่หรือไม่"""
    try:
        __import__(module_name)
        print(f"  ✅ {module_name}: ติดตั้งแล้ว")
        return True
    except ImportError:
        print(f"  ❌ {module_name}: ยังไม่ติดตั้ง")
        return False

def main():
    base_path = os.path.dirname(os.path.abspath(__file__))
    
    print_header("🔍 SYSTEM CHECK - ตรวจสอบการตั้งค่า")
    
    # ======================================
    # 1. ตรวจสอบไฟล์ที่จำเป็น
    # ======================================
    print_header("1️⃣ ตรวจสอบไฟล์")
    
    files_to_check = {
        "index.html": "หน้าเว็บ",
        "script.js": "Frontend JavaScript",
        "app.py": "Backend FastAPI",
        "requirements.txt": "Python Dependencies",
        "config.json": "Configuration"
    }
    
    files_ok = True
    for filename, description in files_to_check.items():
        filepath = os.path.join(base_path, filename)
        if not check_file(filepath, description):
            files_ok = False
    
    # ======================================
    # 2. ตรวจสอบ Python Version
    # ======================================
    print_header("2️⃣ ตรวจสอบ Python")
    
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    print(f"  Python Version: {python_version}")
    
    if sys.version_info.major >= 3 and sys.version_info.minor >= 8:
        print(f"  ✅ Python ถูกต้อง (ต้องเป็น 3.8 ขึ้นไป)")
    else:
        print(f"  ❌ Python เวอร์ชันเก่าเกินไป (ต้อง 3.8 ขึ้นไป)")
    
    # ======================================
    # 3. ตรวจสอบ Virtual Environment
    # ======================================
    print_header("3️⃣ ตรวจสอบ Virtual Environment")
    
    venv_path = os.path.join(base_path, "venv")
    if os.path.exists(venv_path):
        print(f"  ✅ Virtual Environment: มี")
    else:
        print(f"  ❌ Virtual Environment: ไม่มี")
        print(f"     วิธีสร้าง: python -m venv venv")
    
    # ======================================
    # 4. ตรวจสอบ Python Packages
    # ======================================
    print_header("4️⃣ ตรวจสอบ Python Packages")
    
    packages_to_check = {
        "fastapi": "FastAPI",
        "uvicorn": "Uvicorn",
        "pandas": "Pandas",
        "numpy": "NumPy",
        "openpyxl": "OpenPyXL"
    }
    
    packages_ok = True
    for package, name in packages_to_check.items():
        if not check_python_module(package):
            packages_ok = False
    
    if not packages_ok:
        print("\n  ⚠️  บางสิ่งยังไม่ติดตั้ง")
        print("  วิธีติดตั้ง: pip install -r requirements.txt")
    
    # ======================================
    # 5. ตรวจสอบ config.json
    # ======================================
    print_header("5️⃣ ตรวจสอบ Configuration")
    
    config_path = os.path.join(base_path, "config.json")
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        print(f"  ✅ config.json: ถูกต้อง")
        print(f"     - Branches: {len(config['branches'])} สาขา")
        print(f"     - Default Paths: {len(config['default_paths'])} เส้นทาง")
    except Exception as e:
        print(f"  ❌ config.json: ผิดพลาด ({e})")
    
    # ======================================
    # 6. ตรวจสอบ DEFAULT_PATHS ที่สามารถเข้าถึงได้
    # ======================================
    print_header("6️⃣ ตรวจสอบ Directories")
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        default_paths = config['default_paths']
        accessible = 0
        not_accessible = 0
        
        for key, path in default_paths.items():
            # ตรวจสอบเฉพาะสาขาหลัก
            if "_00" not in key:
                if os.path.exists(path):
                    print(f"  ✅ {key}: {path}")
                    accessible += 1
                else:
                    print(f"  ⚠️  {key}: {path} (ไม่มี - แต่ระบบจะสร้าง)")
                    not_accessible += 1
        
        print(f"\n  สรุป: {accessible} accessible")
    except Exception as e:
        print(f"  ⚠️  ไม่สามารถตรวจสอบ Directories ({e})")
    
    # ======================================
    # 7. สรุป
    # ======================================
    print_header("📋 สรุปผลการตรวจสอบ")
    
    if files_ok and packages_ok:
        print("  ✅ ทุกอย่างพร้อม!")
        print("\n  วิธีเริ่มต้น:")
        print("  1. รัน Backend: python app.py")
        print("  2. เปิด index.html ในเบราว์เซอร์")
        print("  3. ลากไฟล์ Excel ลงในกล่อง Dropzone")
        return 0
    else:
        print("  ⚠️  มีบางอย่างที่ต้องแก้ไข")
        if not files_ok:
            print("  - ตรวจสอบไฟล์ที่ขาดหายไป")
        if not packages_ok:
            print("  - รัน: pip install -r requirements.txt")
        return 1

if __name__ == "__main__":
    try:
        exit_code = main()
        print("\n" + "="*60)
        input("กด Enter เพื่อปิด...")
        sys.exit(exit_code)
    except Exception as e:
        print(f"\n❌ เกิดข้อผิดพลาด: {e}")
        input("กด Enter เพื่อปิด...")
        sys.exit(1)
