"""
main.py - Eel Desktop Application
ตัวห่อหุ้ม UI Web ทำให้เป็น Desktop Program
"""
import os
import sys
import json
import traceback
from datetime import datetime
from pathlib import Path
from typing import Dict

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
    from config import BRANCH_NAMES
    from logger import setup_logger
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
        import numpy as np
        from processors import validate_receive_piece
        
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
        
        # Read Excel safely using with open to prevent file locking
        with open(file_path, 'rb') as f:
            df = pd.read_excel(f)
        
        # 1. Clean Data like Save.ipynb
        if "RECEIVE_PIECE" in df.columns:
            df.loc[df["RECEIVE_PIECE"] == 0, "ReBplus"] = np.nan
            # กรองแถวที่ RECEIVE_PIECE == 0 ออก ก่อนการตรวจสอบอื่นๆ
            df = df[~df["RECEIVE_PIECE"].isin([0, "0", 0.0])]
            
        # 1b. Validate RECEIVE_PIECE and RE_SKU_CODE
        receive_valid, receive_mismatches = validate_receive_piece(df)
            
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
            "jk_has_zero": jk_has_zero,
            "receive_mismatch": receive_mismatches
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
        from processors import process_excel_file

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
def select_exe_file_dialog() -> str:
    """
    เปิด File Dialog ให้ User เลือกไฟล์ .exe
    (ใช้ tkinter)
    """
    try:
        import tkinter as tk
        from tkinter import filedialog
        
        root = tk.Tk()
        root.withdraw()  # ซ่อนหน้าต่างหลัก
        root.attributes('-topmost', True)  # ให้ dialog อยู่บน
        
        file_path = filedialog.askopenfilename(
            title="เลือกไฟล์โปรแกรม (.exe)",
            filetypes=[("Executable files", "*.exe"), ("All files", "*.*")]
        )
        
        root.destroy()
        logger.info(f"Exe file selected: {file_path if file_path else 'Cancelled'}")
        return file_path if file_path else ""
    
    except Exception as e:
        logger.error(f"Error in exe file dialog: {e}", exc_info=True)
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
        root.attributes('-topmost', True)  # ให้ dialog อยู่บน
        
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
def get_app_config_dir() -> str:
    """Get the folder where runtime configuration files are stored."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def get_config_path() -> str:
    """Get the path to the configuration file"""
    return os.path.join(get_app_config_dir(), "paths_config.json")


def get_window_state_path() -> str:
    """Get the path to the saved window state file."""
    return os.path.join(get_app_config_dir(), "window_state.json")


def load_window_state() -> Dict[str, int]:
    """Load saved window size and position for eel.start."""
    default_state = {"width": 1400, "height": 900, "x": 50, "y": 50}
    state_path = get_window_state_path()

    try:
        if os.path.exists(state_path):
            with open(state_path, 'r', encoding='utf-8') as f:
                saved_state = json.load(f)

            width = int(saved_state.get("width", default_state["width"]))
            height = int(saved_state.get("height", default_state["height"]))
            x = int(saved_state.get("x", default_state["x"]))
            y = int(saved_state.get("y", default_state["y"]))

            return {
                "width": max(800, min(width, 3840)),
                "height": max(600, min(height, 2160)),
                "x": x,
                "y": y,
            }
    except Exception as e:
        logger.warning(f"Error loading window state from {state_path}: {e}")

    return default_state


@eel.expose
def save_window_state(state: Dict) -> bool:
    """Save current browser window size and position."""
    try:
        width = int(state.get("width", 1400))
        height = int(state.get("height", 900))
        x = int(state.get("x", 50))
        y = int(state.get("y", 50))

        clean_state = {
            "width": max(800, min(width, 3840)),
            "height": max(600, min(height, 2160)),
            "x": x,
            "y": y,
        }

        with open(get_window_state_path(), 'w', encoding='utf-8') as f:
            json.dump(clean_state, f, ensure_ascii=False, indent=4)

        return True
    except Exception as e:
        logger.error(f"Error saving window state: {e}")
        return False

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
def load_custom_names_config() -> Dict:
    """Load custom names config from file"""
    config_path = os.path.join(get_app_config_dir(), "custom_names_config.json")
    try:
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Error loading custom names config from {config_path}: {e}")
    return {}


@eel.expose
def save_custom_names_config(config: Dict) -> bool:
    """Save custom names config to file"""
    config_path = os.path.join(get_app_config_dir(), "custom_names_config.json")
    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=4)
        return True
    except Exception as e:
        logger.error(f"Error saving custom names config to {config_path}: {e}")
        return False


@eel.expose
def load_custom_scripts() -> list:
    """Load custom scripts from file"""
    config_path = os.path.join(get_app_config_dir(), "custom_scripts.json")
    try:
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Error loading custom scripts from {config_path}: {e}")
    return []


@eel.expose
def save_custom_scripts(scripts: list) -> bool:
    """Save custom scripts to file"""
    config_path = os.path.join(get_app_config_dir(), "custom_scripts.json")
    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(scripts, f, ensure_ascii=False, indent=4)
        return True
    except Exception as e:
        logger.error(f"Error saving custom scripts to {config_path}: {e}")
        return False



@eel.expose
def check_directory_exists(directory_path: str) -> bool:
    """ตรวจสอบว่า directory มีอยู่และสามารถเข้าถึงได้"""
    try:
        return os.path.isdir(directory_path) and os.access(directory_path, os.R_OK)
    except Exception as e:
        logger.warning(f"Error checking directory {directory_path}: {e}")
        return False


@eel.expose
def open_folder_in_explorer(folder_path: str) -> bool:
    """เปิดโฟลเดอร์ใน Windows Explorer"""
    try:
        # Normalize path separators for Windows
        normalized_path = os.path.normpath(folder_path)
        if os.path.isdir(normalized_path):
            os.startfile(normalized_path)
            logger.info(f"📂 Opened folder in Explorer: {normalized_path}")
            return True
        else:
            logger.warning(f"Folder not found: {normalized_path}")
            return False
    except Exception as e:
        logger.error(f"Error opening folder: {e}")
        return False


def _launch_executable(exe_path: str, *args: str) -> bool:
    """Launch an executable as a detached child process to avoid duplicate windows."""
    import subprocess

    try:
        if not exe_path or not os.path.exists(exe_path):
            logger.error(f"❌ Executable not found: {exe_path}")
            return False

        command = [exe_path]
        if args:
            command.extend(args)

        creationflags = 0
        if sys.platform == 'win32':
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS

        subprocess.Popen(
            command,
            close_fds=True,
            cwd=os.path.dirname(exe_path) if os.path.dirname(exe_path) else None,
            creationflags=creationflags,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        logger.info(f"✅ Launched detached process: {exe_path}")
        return True
    except Exception as e:
        logger.error(f"❌ Error launching executable: {e}", exc_info=True)
        return False


@eel.expose
def launch_excel_processor() -> bool:
    """เปิดโปรแกรม ExcelProcessor.exe"""
    try:
        # Try dist version first, then build version
        exe_paths = [
            os.path.join(os.path.dirname(__file__), 'dist', 'ExcelProcessor', 'ExcelProcessor.exe'),
            os.path.join(os.path.dirname(__file__), 'build', 'ExcelProcessor', 'ExcelProcessor.exe'),
        ]
        
        for path in exe_paths:
            if os.path.exists(path):
                return _launch_executable(path)
        
        logger.error("❌ ExcelProcessor.exe not found in dist or build directories")
        return False
        
    except Exception as e:
        logger.error(f"❌ Error launching ExcelProcessor: {e}")
        return False


@eel.expose
def terminate_program() -> None:
    """ปิดโปรแกรมทันทีเพื่อคลายไฟล์ล็อกทั้งหมด"""
    logger.info("❌ Program termination requested by user to release file locks.")
    # หน่วงเวลานิดหน่อยเพื่อให้ frontend ปิดตัวเรียบร้อยก่อนปิด backend
    import time
    time.sleep(0.2)
    raise SystemExit(0)


@eel.expose
def restart_application() -> None:
    """
    รีสตาร์ทโปรแกรมโดยปิดหน้าต่างปัจจุบันและเปิดใหม่
    ใช้ subprocess เพื่อเปิดไฟล์ exe ใหม่
    """
    try:
        logger.info("🔄 Restarting application...")
        
        exe_path = None
        saved_exe_path = get_saved_exe_path()
        if saved_exe_path and os.path.exists(saved_exe_path):
            exe_path = saved_exe_path
            logger.info(f"🔁 Using saved exe path for restart: {exe_path}")
        elif getattr(sys, 'frozen', False):
            exe_path = sys.executable
        else:
            search_paths = [
                os.path.join(os.path.dirname(__file__), 'dist', 'ExcelProcessor', 'ExcelProcessor.exe'),
                os.path.join(os.path.dirname(__file__), 'build', 'ExcelProcessor', 'ExcelProcessor.exe'),
            ]
            for path in search_paths:
                if os.path.exists(path):
                    exe_path = path
                    break
            
            if not exe_path:
                exe_path = os.path.abspath(__file__)
                if not exe_path.lower().endswith('.exe'):
                    logger.info(f"Restarting as Python script: {exe_path}")
                    if _launch_executable(sys.executable, exe_path):
                        os._exit(0)
                    raise SystemExit(1)
        
        if exe_path and os.path.exists(exe_path):
            logger.info(f"✅ Restarting from: {exe_path}")
            # Ask frontend to close its browser window (if available) before launching replacement
            try:
                if 'eel' in globals() and hasattr(eel, '_closeWindowFromPython'):
                    try:
                        eel._closeWindowFromPython()(lambda: logger.info('Requested frontend to close'))
                    except Exception:
                        # Some eel versions map JS functions directly as attributes
                        try:
                            eel._closeWindowFromPython()
                        except Exception:
                            logger.debug('Could not call _closeWindowFromPython from Python')
            except Exception:
                logger.debug('No frontend close function available')

            if not _launch_executable(exe_path):
                logger.error("Cannot start replacement process")
                raise SystemExit(1)
        else:
            logger.error("Cannot find executable to restart")
            raise SystemExit(1)
        
        os._exit(0)
        
    except Exception as e:
        logger.error(f"❌ Error restarting application: {e}", exc_info=True)
        raise SystemExit(1)


@eel.expose
def get_recent_exe_files() -> list:
    """
    ค้นหาไฟล์ .exe ที่ใหม่ล่าสุดในโฟลเดอร์ปัจจุบัน dist และ build
    รีเทิร์นรายการ .exe พร้อมข้อมูล (path, name, modified_time)
    """
    import glob
    import os
    
    exe_list = []
    search_dirs = [
        os.path.dirname(__file__),  # Current directory
        os.path.join(os.path.dirname(__file__), 'dist'),
        os.path.join(os.path.dirname(__file__), 'build'),
        os.path.join(os.path.dirname(__file__), 'dist', 'ExcelProcessor'),
        os.path.join(os.path.dirname(__file__), 'build', 'ExcelProcessor'),
    ]
    
    try:
        found_files = {}  # dict เพื่อเก็บไฟล์ unique และเลือกเก่าสุด
        
        for search_dir in search_dirs:
            if not os.path.isdir(search_dir):
                continue
            
            # ค้นหา .exe ไฟล์ในโฟลเดอร์
            for exe_file in glob.glob(os.path.join(search_dir, '*.exe')):
                try:
                    file_name = os.path.basename(exe_file)
                    file_size = os.path.getsize(exe_file)
                    mod_time = os.path.getmtime(exe_file)
                    
                    # เก็บเฉพาะไฟล์ที่มีขนาดใหญ่ (ข้ามไฟล์ installer/uninstaller ขนาดเล็ก)
                    if file_size > 1000000:  # 1MB
                        key = file_name.lower()
                        if key not in found_files or found_files[key]['mod_time'] < mod_time:
                            found_files[key] = {
                                'path': exe_file,
                                'name': file_name,
                                'mod_time': mod_time,
                                'size': file_size
                            }
                except Exception as e:
                    logger.warning(f"Error processing exe file {exe_file}: {e}")
        
        # เรียงลำดับตามเวลาแก้ไข (ใหม่สุดก่อน)
        exe_list = sorted(found_files.values(), key=lambda x: x['mod_time'], reverse=True)
        
        # จัดรูปแบบสำหรับ frontend
        result = [{
            'path': item['path'],
            'name': item['name'],
            'modified_time': item['mod_time'],
            'size_mb': round(item['size'] / 1024 / 1024, 2)
        } for item in exe_list]
        
        logger.info(f"✅ Found {len(result)} .exe files")
        return result
        
    except Exception as e:
        logger.error(f"❌ Error scanning for .exe files: {e}")
        return []


@eel.expose
def launch_excel_processor_from_path(exe_path: str) -> bool:
    """
    เปิดโปรแกรม ExcelProcessor.exe จากเส้นทางที่กำหนด
    
    Args:
        exe_path: Path to the .exe file
    
    Returns:
        True if launched successfully, False otherwise
    """
    try:
        if not exe_path or not os.path.exists(exe_path):
            logger.error(f"❌ Executable not found: {exe_path}")
            return False
        
        if not exe_path.lower().endswith('.exe'):
            logger.error(f"❌ File is not an executable: {exe_path}")
            return False
        
        save_selected_exe_path(exe_path)
        success = _launch_executable(exe_path)
        if success:
            logger.info(f"✅ Launched executable from custom path: {exe_path}")
        return success
        
    except Exception as e:
        logger.error(f"❌ Error launching executable from {exe_path}: {e}")
        return False


@eel.expose
def get_saved_exe_path() -> str:
    """Get the last selected .exe path from config."""
    try:
        config = load_paths_config()
        saved_path = config.get("selected_exe_path") or config.get("exe_path") or ""
        if saved_path and os.path.exists(saved_path):
            return saved_path
        return ""
    except Exception as e:
        logger.warning(f"Error reading saved exe path: {e}")
        return ""


@eel.expose
def save_selected_exe_path(exe_path: str) -> bool:
    """Persist the selected .exe path so restart can reuse it."""
    try:
        if not exe_path:
            return False

        config = load_paths_config()
        config["selected_exe_path"] = exe_path
        return save_paths_config(config)
    except Exception as e:
        logger.warning(f"Error saving selected exe path: {e}")
        return False


@eel.expose
def get_bill_suggestions(kmart: str, part_a: str, part_b: str) -> list:
    """
    แสกนหาชื่อไฟล์ใน part_a และ part_b ตามรูปแบบ <kmart>-*.XLSX / <kmart>-*.xlsx (case-insensitive)
    และคืนค่ารายชื่อ * (bill) ทั้งหมดที่เป็นไปได้
    """
    import glob
    import os
    
    logger.info(f"🔍 Scanning bill suggestions for kmart={kmart}, part_a={part_a}, part_b={part_b}")
    suggestions = set()
    
    dirs_to_search = []
    if part_a and os.path.isdir(part_a):
        dirs_to_search.append(part_a)
    if part_b and os.path.isdir(part_b):
        dirs_to_search.append(part_b)
        
    for d in dirs_to_search:
        try:
            # ค้นหาแบบ recursive ครอบคลุมโฟลเดอร์ลึกทุกระดับเช่นเดียวกับตอนเซฟไฟล์
            search_patterns = [
                os.path.join(d, "**", f"{kmart}-*.XLSX"),
                os.path.join(d, "**", f"{kmart}-*.xlsx"),
            ]
            for pattern in search_patterns:
                logger.info(f"Scanning pattern: {pattern}")
                matched_files = glob.glob(pattern, recursive=True)
                logger.info(f"Found {len(matched_files)} files matching {pattern}")
                for file_path in matched_files:
                    filename = os.path.basename(file_path)
                    base, ext = os.path.splitext(filename)
                    if '-' in base:
                        parts = base.split('-', 1)
                        if len(parts) > 1:
                            suggestions.add(parts[1])
        except Exception as e:
            logger.warning(f"Error scanning directory {d} for suggestions: {e}")
            
    result = sorted(list(suggestions))
    logger.info(f"✅ Scanning complete. Found {len(result)} unique suggestions: {result}")
    return result


@eel.expose
def process_pass_2_save(kmart: str, bill: str, path_dest: str, part_a: str, part_b: str) -> dict:
    """
    ประมวลผลตามตรรกะในไฟล์ pass 2 save.ipynb
    - รับสาขา Kmart, เดือน/ท้ายบิล, ปลายทางเซฟไฟล์, และ Google Drive PATHs (part_a, part_b)
    - ค้นหาไฟล์ f"{Kmart}-{bill}.XLSX" หรือ xlsx
    - ตรวจสอบรหัสสาขาให้ถูกต้อง
    - แปลงข้อมูล ตัดช่องว่าง จัดชิดซ้าย บันทึกเป็น .txt
    """
    import os
    import glob
    import pandas as pd
    
    KMART_CODES = {
        "K1": "11",
        "K2": "21",
        "K3": "31",
        "K4": "41",
        "K5": "51",
        "SP": "00"
    }
    
    kmart = kmart.upper().strip()
    bill = bill.strip()
    
    if kmart not in KMART_CODES:
        return {
            "success": False,
            "message": f"ไม่พบข้อมูลสาขา {kmart} ในระบบ"
        }
        
    if not os.path.isdir(path_dest):
        return {
            "success": False,
            "message": f"ไม่พบโฟลเดอร์ปลายทางที่ระบุ: {path_dest}"
        }
        
    # ค้นหาไฟล์จาก part_a และ part_b
    search_a_xlsx = os.path.join(part_a, "**", f"{kmart}-{bill}.XLSX")
    search_a_lc = os.path.join(part_a, "**", f"{kmart}-{bill}.xlsx")
    search_b_xlsx = os.path.join(part_b, "**", f"{kmart}-{bill}.XLSX")
    search_b_lc = os.path.join(part_b, "**", f"{kmart}-{bill}.xlsx")
    
    file_list = []
    
    # ดำเนินการค้นหาในโฟลเดอร์ที่มีอยู่
    if os.path.isdir(part_a):
        file_list.extend(glob.glob(search_a_xlsx, recursive=True))
        file_list.extend(glob.glob(search_a_lc, recursive=True))
    if os.path.isdir(part_b):
        file_list.extend(glob.glob(search_b_xlsx, recursive=True))
        file_list.extend(glob.glob(search_b_lc, recursive=True))
        
    # เอาเฉพาะไฟล์ที่มีอยู่จริงและไม่มีโฟลเดอร์ปลอม
    file_list = [f for f in file_list if os.path.isfile(f)]
    
    if not file_list:
        return {
            "success": False,
            "message": f"❌ ไม่พบไฟล์ {kmart}-{bill}.XLSX ในโฟลเดอร์ part_a หรือ part_b (ตรวจสอบชื่อไฟล์หรือเส้นทางโฟลเดอร์)"
        }
        
    target_file = file_list[0]
    logger.info(f"Pass 2 processing using file: {target_file}")
    
    try:
        # อ่าน Excel คอลัมน์แรก ตั้งชื่อ 'forBplus' อย่างปลอดภัยเพื่อหลีกเลี่ยงการล็อกไฟล์
        with open(target_file, 'rb') as f:
            df = pd.read_excel(f, engine='openpyxl', usecols='A', names=['forBplus'])
        
        if df.empty:
            return {
                "success": False,
                "message": "ไฟล์ Excel ว่างเปล่า ไม่มีข้อมูลในคอลัมน์ A"
            }
            
        # ตรวจสอบรหัสสาขาในแถวแรก
        first_row_val = str(df['forBplus'].iloc[0])
        parts = first_row_val.split(',')
        if len(parts) < 2:
            return {
                "success": False,
                "message": f"รูปแบบข้อมูลแถวแรกไม่ถูกต้อง: {first_row_val} (ไม่มีเครื่องหมายจุลภาค)"
            }
            
        file_branch_code = parts[1].strip()
        expected_code = KMART_CODES[kmart]
        
        if file_branch_code != expected_code:
            return {
                "success": False,
                "message": f"❌ รหัสสาขาไม่ตรงกัน! รหัสสาขาในไฟล์คือ '{file_branch_code}' แต่ต้องการรหัสของ {kmart} คือ '{expected_code}'"
            }
            
        # --- สร้าง Folder ตามเดือน-ปี พ.ศ. (เหมือนหน้าแรก) ---
        now_dt = datetime.now()
        current_month = now_dt.strftime("%m")
        current_year_th = now_dt.year + 543
        month_folder_name = f"{current_month}-{current_year_th}"
        
        # สร้างโฟลเดอร์เดือน-ปี ถ้ายังไม่มี
        month_path = os.path.join(path_dest, month_folder_name)
        os.makedirs(month_path, exist_ok=True)
        logger.info(f"📁 Pass2: โฟลเดอร์เดือน-ปี: {month_path}")
        
        # เซฟไฟล์ปลายทาง (ลงในโฟลเดอร์เดือน-ปี)
        save_path = os.path.join(month_path, f"{kmart}-{bill}.txt")
        
        # ตรวจสอบไฟล์ซ้ำ ถ้ามี ให้เปลี่ยนชื่อแล้วเซฟลงโฟลเดอร์เดือน-ปีเดิม
        # (part_a / part_b ใช้แค่ค้นหาไฟล์ Excel เท่านั้น ไม่ใช้เซฟ)
        is_duplicate = False
        if os.path.exists(save_path):
            is_duplicate = True
            txt_filename = f"{kmart}-{bill}-1.txt"
            save_path = os.path.join(month_path, txt_filename)
                
        # แปลงเป็นสตริง, ลบช่องว่างหน้า-หลังแต่ละบรรทัด, และบันทึก
        raw_text = df.to_string(index=False, header=False)
        cleaned_lines = [line.strip() for line in raw_text.split('\n')]
        cleaned_text = '\n'.join(cleaned_lines)
        
        with open(save_path, 'w', encoding='utf-8') as f:
            f.write(cleaned_text)
            
        duplicate_note = " (⚠️ ตรวจพบไฟล์ซ้ำ เปลี่ยนชื่อเป็น -1)" if is_duplicate else ""
        return {
            "success": True,
            "message": f"ส่งไฟล์ {kmart} สำเร็จ! ตำแหน่งไฟล์: {save_path}{duplicate_note}",
            "row_count": len(df),
            "save_path": save_path
        }
        
    except Exception as e:
        logger.error(f"Error in process_pass_2_save: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"เกิดข้อผิดพลาดขณะประมวลผลไฟล์: {str(e)}"
        }


# ==================== START DESKTOP APP ====================
def start_app():
    """เปิด Desktop Application"""
    logger.info("="*60)
    logger.info("Starting Desktop Application...")
    logger.info("="*60)
    
    try:
        # เปิด UI ที่ port ค่าเริ่มต้น (ใช้ port random เพื่อหลีกเลี่ยง conflict)
        window_state = load_window_state()

        eel.start(
            'index.html',
            size=(window_state["width"], window_state["height"]),
            position=(window_state["x"], window_state["y"]),
            disable_cache=False,
            port=0  # ให้ OS เลือก port อัตโนมัติ
        )
    
    except Exception as e:
        logger.error(f"Error starting app: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    logger.info("Initializing Desktop Application...")
    start_app()

