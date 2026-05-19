"""
main.py - Eel Desktop Application
ตัวห่อหุ้ม UI Web ทำให้เป็น Desktop Program
"""
import os
import sys
import json
import traceback
from pathlib import Path
from typing import Dict

# Fix Unicode encoding สำหรับ Thai characters บน Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Import eel หลังจากที่แน่ใจว่า web directory ตั้งค่าถูก
try:
    import eel
except ImportError:
    print("Error: Eel not installed. Run: pip install eel")
    sys.exit(1)

# Import from modular components
try:
    from config import SERVER_HOST, CORS_ORIGINS, BRANCH_NAMES
    from logger import setup_logger
    from processors import process_excel_file
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure config.py, logger.py, processors.py exist in the same directory")
    sys.exit(1)

# ==================== SETUP ====================
logger = setup_logger(__name__)

# สำหรับ PyInstaller: ชี้ให้ Eel รู้ว่า web files อยู่ที่ไหน
web_dir = 'web'
if getattr(sys, 'frozen', False):
    # PyInstaller bundle
    application_path = sys._MEIPASS
    web_dir = os.path.join(application_path, 'web')
elif not os.path.exists(web_dir):
    web_dir = os.path.dirname(os.path.abspath(__file__))

logger.info(f"Web directory: {web_dir}")

# Initialize Eel
try:
    eel.init(web_dir)
    logger.info("✅ Eel initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize Eel: {e}")
    sys.exit(1)

# ==================== EEL EXPOSED FUNCTIONS ====================

@eel.expose
def preview_excel_file(file_path: str) -> Dict:
    """
    Preview ไฟล์ Excel ก่อนประมวลผล
    
    Args:
        file_path: Path to Excel file
    
    Returns:
        Preview data with row count, branch, types
    """
    try:
        import pandas as pd
        
        logger.info(f"Previewing file: {file_path}")
        
        # Validate file
        if not os.path.exists(file_path):
            return {
                "success": False,
                "message": f"ไฟล์ไม่พบ: {file_path}"
            }
        
        if not file_path.lower().endswith(('.xlsx', '.xls')):
            return {
                "success": False,
                "message": "ไฟล์ต้องเป็น Excel (.xlsx หรือ .xls)"
            }
        
        # Read Excel
        df = pd.read_excel(file_path)
        
        # Get basic info
        total_rows = len(df)
        columns = list(df.columns)
        
        # Detect branch
        if "ReBplus" not in columns:
            return {
                "success": False,
                "message": "ไฟล์ Excel ไม่มี Column 'ReBplus' - โปรดตรวจสอบโครงสร้าง"
            }
        
        # Extract branch code
        branch_codes = df["ReBplus"].astype(str).str.split(",").str.get(2).str.strip().unique()
        detected_branch = None
        for code in ["11", "21", "31", "41", "51"]:
            if code in branch_codes:
                detected_branch = code
                break
        if not detected_branch and "00" in branch_codes:
            detected_branch = "SP"
        
        branch_name = BRANCH_NAMES.get(detected_branch, "Unknown") if detected_branch else "ไม่พบ"
        
        # Count types (SP vs WH)
        type_col = "1=SP,2=WH"
        sp_count = 0
        wh_count = 0
        
        if type_col in columns:
            sp_count = len(df[df[type_col] == 1])
            wh_count = len(df[df[type_col] == 2])
        
        return {
            "success": True,
            "file_path": file_path,
            "file_name": os.path.basename(file_path),
            "total_rows": total_rows,
            "detected_branch": detected_branch,
            "branch_name": branch_name,
            "sp_count": int(sp_count),
            "wh_count": int(wh_count),
            "columns": columns[:5]
        }
    
    except Exception as e:
        logger.error(f"Error previewing file: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"Error: {str(e)}"
        }


@eel.expose
def process_file_from_desktop(file_path: str, paths_config: Dict[str, str]) -> Dict:
    """
    ประมวลผลไฟล์จาก Desktop (มี access เต็ม ๆ)
    
    Args:
        file_path: Path to Excel file (absolute path บน desktop)
        paths_config: Paths configuration from user
    
    Returns:
        Processing result
    """
    try:
        logger.info(f"Processing file from desktop: {file_path}")
        
        # Validate file exists
        if not os.path.exists(file_path):
            return {
                "success": False,
                "message": f"❌ ไฟล์ไม่พบ: {file_path}",
                "error_details": "File not found"
            }
        
        # Check file extension
        if not file_path.lower().endswith(('.xlsx', '.xls')):
            return {
                "success": False,
                "message": "❌ ไฟล์ต้องเป็น Excel (.xlsx หรือ .xls)",
                "error_details": "Invalid file type"
            }
        
        # Process file
        result = process_excel_file(file_path, paths_config)
        logger.info(f"Processing complete: {result['success']}")
        
        return result
    
    except Exception as e:
        logger.error(f"Error processing file: {str(e)}", exc_info=True)
        return {
            "success": False,
            "message": f"❌ Error: {str(e)}",
            "error_details": traceback.format_exc()
        }


@eel.expose
def get_branch_config() -> Dict:
    """ส่งข้อมูล Branch ให้ Frontend"""
    return {
        "branches": BRANCH_NAMES,
        "desktop_mode": True
    }


@eel.expose
def select_file_dialog() -> str:
    """
    เปิด File Dialog ให้ User เลือกไฟล์ Excel
    (ใช้ tkinter)
    """
    try:
        import tkinter as tk
        from tkinter import filedialog
        
        root = tk.Tk()
        root.withdraw()  # ซ่อนหน้าต่างหลัก
        root.attributes('-topmost', True)  # ให้ dialog อยู่บน
        
        file_path = filedialog.askopenfilename(
            title="เลือกไฟล์ Excel",
            filetypes=[("Excel files", "*.xlsx *.xls"), ("All files", "*.*")]
        )
        
        root.destroy()
        logger.info(f"File selected: {file_path if file_path else 'Cancelled'}")
        return file_path if file_path else ""
    
    except Exception as e:
        logger.error(f"Error in file dialog: {e}", exc_info=True)
        return ""


@eel.expose
def select_directory_dialog() -> str:
    """
    เปิด Directory Dialog ให้ User เลือกโฟลเดอร์
    """
    try:
        import tkinter as tk
        from tkinter import filedialog
        
        root = tk.Tk()
        root.withdraw()
        
        dir_path = filedialog.askdirectory(title="เลือกโฟลเดอร์บันทึก")
        
        root.destroy()
        return dir_path if dir_path else ""
    
    except Exception as e:
        logger.error(f"Error in directory dialog: {e}")
        return ""


# ==================== START DESKTOP APP ====================
def start_app():
    """เปิด Desktop Application"""
    logger.info("="*60)
    logger.info("Starting Desktop Application...")
    logger.info("="*60)
    
    try:
        # เปิด UI ที่ port ค่าเริ่มต้น (ใช้ port random เพื่อหลีกเลี่ยง conflict)
        eel.start(
            'index.html',
            size=(1400, 900),
            position=(50, 50),
            disable_cache=True,
            port=0  # ให้ OS เลือก port อัตโนมัติ
        )
    
    except Exception as e:
        logger.error(f"Error starting app: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    logger.info("Initializing Desktop Application...")
    start_app()

