"""
config.py - Configuration Management
"""
import os
from pathlib import Path
from typing import Dict

# ==================== ENVIRONMENT SETTINGS ====================
DEBUG = os.getenv("DEBUG", "False").lower() == "true"
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
UPLOAD_TEMP_DIR = os.getenv("UPLOAD_TEMP_DIR", "./temp_uploads")

# ==================== SERVER SETTINGS ====================
SERVER_HOST = os.getenv("SERVER_HOST", "0.0.0.0")
SERVER_PORT = int(os.getenv("SERVER_PORT", "8000"))
RELOAD = os.getenv("RELOAD", "True").lower() == "true"

# API / Application version
API_VERSION = os.getenv("API_VERSION", "1.0.0")

# ==================== CORS SETTINGS ====================
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_METHODS = ["*"]
CORS_ALLOW_HEADERS = ["*"]

# ==================== BRANCH & PATH CONFIGURATION ====================
BRANCH_NAMES = {
    '00': 'WH',
    '11': 'K1',
    '21': 'K2',
    '31': 'K3',
    '41': 'K4',
    '51': 'K5'
}

# ไม่มีค่าเริ่มต้น - ผู้ใช้ต้องระบุ Path เอง
DEFAULT_PATHS: Dict[str, str] = {}

# ==================== EXCEL FILE SETTINGS ====================
ALLOWED_FILE_TYPES = ['.xlsx', '.xls']
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

# ==================== FILE PROCESSING ====================
OUTPUT_FILE_ENCODING = 'utf-8'
DATE_FORMAT_THAI = "%d-%m-{} รับ"  # {thai_year} will be inserted

# Ensure temp directory exists
Path(UPLOAD_TEMP_DIR).mkdir(exist_ok=True)
