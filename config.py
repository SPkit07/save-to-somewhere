"""
config.py - Configuration Management
"""
import os
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

