"""
config.py - Configuration Management
"""
import os
import sys
from pathlib import Path

# ==================== ENVIRONMENT SETTINGS ====================
DEBUG = os.getenv("DEBUG", "False").lower() == "true"
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
UPLOAD_TEMP_DIR = os.getenv("UPLOAD_TEMP_DIR", "./temp_uploads")

# ==================== BRANCH CONFIGURATION ====================
BRANCH_NAMES = {
    '00': 'WH',
    '11': 'K1',
    '21': 'K2',
    '31': 'K3',
    '41': 'K4',
    '51': 'K5',
    'SP': 'Super'
}

# Ensure temp directory exists
Path(UPLOAD_TEMP_DIR).mkdir(exist_ok=True)


# ==================== RUNTIME PATH HELPERS ====================
def get_app_config_dir() -> str:
    """
    คืนค่าโฟลเดอร์สำหรับเก็บไฟล์ config ในขณะทำงาน
    รองรับทั้งขณะรัน source code และรันผ่าน PyInstaller (.exe)
    """
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    # หากรันจาก root directory
    root_dir = os.path.dirname(os.path.abspath(__file__))
    dist_dir = os.path.join(root_dir, "dist", "ExcelProcessor")
    # ถ้ามีโฟลเดอร์ dist ที่มี paths_config.json อยู่
    if os.path.isdir(dist_dir) and os.path.exists(os.path.join(dist_dir, "paths_config.json")):
        return dist_dir
    return root_dir


def get_paths_config_path() -> str:
    """คืนค่า path ของ paths_config.json"""
    return os.path.join(get_app_config_dir(), "paths_config.json")


def get_problematic_barcodes_path() -> str:
    """คืนค่า path ของ problematic_barcodes.json"""
    return os.path.join(get_app_config_dir(), "problematic_barcodes.json")


def get_lan_config_path() -> str:
    """คืนค่า path ของ lan_config.json (สำหรับเก็บข้อมูลชื่อเครื่องและการตั้งค่า LAN เฉพาะ)"""
    return os.path.join(get_app_config_dir(), "lan_config.json")

