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
import numpy as np

# Fix Unicode encoding สำหรับ Thai characters บน Windows
if sys.platform == 'win32':
    import io
    if sys.stdout is not None:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    if sys.stderr is not None:
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
        
        # 1. Clean Data like Save.ipynb
        if "RECEIVE_PIECE" in df.columns:
            df.loc[df["RECEIVE_PIECE"] == 0, "ReBplus"] = np.nan
            
        # 2. Validation for 1=SP,2=WH mismatch (Column J vs K)
        jk_mismatch_details = []
        jk_has_zero = False
        
        # คอลัมน์ J = index 9, คอลัมน์ K = index 10
        if len(df.columns) > 10:
            col_j = df.columns[9]
            col_k = df.columns[10]
            
            # เช็คว่ามีค่า 0 ในคอลัมน์ J หรือ K หรือไม่
            if (df[col_j] == 0).any() or (df[col_k] == 0).any():
                jk_has_zero = True
                
            val_j = df[col_j].fillna("").astype(str).str.strip().str.replace(r'\.0$', '', regex=True)
            val_k = df[col_k].fillna("").astype(str).str.strip().str.replace(r'\.0$', '', regex=True)
            
            mismatch_mask = val_j != val_k
            
            if mismatch_mask.any():
                mismatched_df = df[mismatch_mask]
                
                # GOODS_CODE column
                goods_code_col = "GOODS_CODE" if "GOODS_CODE" in df.columns else None
                
                # SKU_NAME: ใช้คอลัมน์ SKU_NAME หรือ Column F (index 5) เป็น fallback
                prod_name_col = None
                if "SKU_NAME" in df.columns:
                    prod_name_col = "SKU_NAME"
                elif len(df.columns) > 5:
                    prod_name_col = df.columns[5]  # Column F
                        
                for idx, (row_idx, row) in enumerate(mismatched_df.iterrows(), 1):
                    code = row[goods_code_col] if goods_code_col and pd.notna(row[goods_code_col]) else "ไม่ระบุรหัส"
                    name = row[prod_name_col] if prod_name_col and pd.notna(row[prod_name_col]) else "ไม่ระบุชื่อ"
                    col_j_val = row[col_j] if pd.notna(row[col_j]) else "-"
                    col_k_val = row[col_k] if pd.notna(row[col_k]) else "-"
                    
                    jk_mismatch_details.append({
                        "index": idx,
                        "row_num": int(row_idx) + 2,
                        "code": str(code).strip(),
                        "name": str(name).strip(),
                        "col_j": str(col_j_val).replace(".0", "").strip(),
                        "col_k": str(col_k_val).replace(".0", "").strip()
                    })
            
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
        sku_str = df["ReBplus"].astype(str).str.strip()
        extracted_code = sku_str.str.split(",").str.get(2).str.strip()
        
        branch_codes = extracted_code.unique()
        detected_branch = None
        for code in ["11", "21", "31", "41", "51"]:
            if code in branch_codes:
                detected_branch = code
                break
        if not detected_branch and "00" in branch_codes:
            detected_branch = "SP"
        
        branch_name = BRANCH_NAMES.get(detected_branch, "Unknown") if detected_branch else "ไม่พบ"
        
        # Count types (SP vs WH) using EXACT Save.ipynb logic
        sp_count = 0
        wh_count = 0
        
        if detected_branch:
            type_col_name = "1=SP,2=WH"
            if type_col_name in df.columns:
                col_type = df[type_col_name]
            else:
                alt_name = [c for c in df.columns if "1=" in str(c) or "WH" in str(c)]
                col_type = df[alt_name[0]] if alt_name else df.iloc[:, 1]
                
            # SP Count
            if detected_branch == "SP":
                cond_main = (extracted_code == "00")
            else:
                cond_main = col_type.isin([1, 1.0, "1", "1.0"]) & (extracted_code == detected_branch)
            sp_count = len(df.loc[cond_main, "ReBplus"])
            
            # WH Count
            if detected_branch == "SP":
                wh_count = 0
            else:
                cond_00 = (col_type.isin([2, 2.0, "2", "2.0"]) | col_type.isna() | (col_type.astype(str).str.strip() == "nan")) & (extracted_code == "00")
                wh_count = len(df.loc[cond_00, "ReBplus"])
        
        return {
            "success": True,
            "file_path": file_path,
            "file_name": os.path.basename(file_path),
            "total_rows": total_rows,
            "detected_branch": detected_branch,
            "branch_name": branch_name,
            "sp_count": int(sp_count),
            "wh_count": int(wh_count),
            "columns": columns[:5],
            "jk_mismatch": jk_mismatch_details,
            "jk_has_zero": jk_has_zero
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
                "message": "ไฟล์ไม่พบ",
                "errors": ["[ERROR]", f"ไฟล์ไม่พบ: {file_path}"],
                "error_details": "File not found"
            }
        
        # Check file extension
        if not file_path.lower().endswith(('.xlsx', '.xls')):
            return {
                "success": False,
                "message": "ไฟล์ไม่ถูกต้อง",
                "errors": ["[ERROR]", "ไฟล์ต้องเป็น Excel (.xlsx หรือ .xls)"],
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
            "message": f"เกิดข้อผิดพลาด: {str(e)}",
            "errors": ["[ERROR]", str(e)],
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


@eel.expose
def save_temp_file(filename: str, base64_data: str) -> str:
    """
    บันทึกไฟล์ชั่วคราวจากการลากวาง (Drag & Drop)
    """
    try:
        import base64
        import os
        from pathlib import Path
        
        temp_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "temp_uploads")
        Path(temp_dir).mkdir(exist_ok=True)
        
        temp_path = os.path.join(temp_dir, filename)
        
        # decode base64 string
        with open(temp_path, "wb") as fh:
            fh.write(base64.b64decode(base64_data))
            
        logger.info(f"Saved dropped file to {temp_path}")
        return temp_path
        
    except Exception as e:
        logger.error(f"Error saving temp file: {e}")
        return ""

# ==================== CONFIG MANAGEMENT ====================
def get_config_path() -> str:
    """Get the path to the configuration file"""
    if getattr(sys, 'frozen', False):
        base_path = os.path.dirname(sys.executable)
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, "paths_config.json")

@eel.expose
def load_paths_config() -> Dict:
    """Load paths config from file"""
    config_path = get_config_path()
    try:
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Error loading config from {config_path}: {e}")
    return {}

@eel.expose
def save_paths_config(paths: Dict) -> bool:
    """Save paths config to file"""
    config_path = get_config_path()
    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(paths, f, ensure_ascii=False, indent=4)
        return True
    except Exception as e:
        logger.error(f"Error saving config to {config_path}: {e}")
        return False


@eel.expose
def check_directory_exists(directory_path: str) -> bool:
    """ตรวจสอบว่า directory มีอยู่และสามารถเข้าถึงได้"""
    try:
        return os.path.isdir(directory_path) and os.access(directory_path, os.R_OK)
    except Exception as e:
        logger.warning(f"Error checking directory {directory_path}: {e}")
        return False


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

