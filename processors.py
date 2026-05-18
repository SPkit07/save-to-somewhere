"""
processors.py - Business Logic for Excel Processing
"""
import pandas as pd
import numpy as np
import os
from datetime import datetime
from typing import Dict, Tuple, Optional
from logger import logger
from config import BRANCH_NAMES, DEFAULT_PATHS, DATE_FORMAT_THAI, OUTPUT_FILE_ENCODING

# ==================== BRANCH DETECTION ====================
def detect_file_branch(df: pd.DataFrame) -> Optional[str]:
    """
    ตรวจพบสาขาจากไฟล์ Excel
    
    Args:
        df: DataFrame from Excel file
    
    Returns:
        Branch code (11, 21, 31, 41, 51, SP) or None
    """
    try:
        if "ReBplus" not in df.columns:
            logger.error("Column 'ReBplus' not found in Excel file")
            return None
        
        # Extract branch codes (position 2 from ReBplus split by comma)
        all_codes = df["ReBplus"].astype(str).str.split(",").str.get(2).str.strip().unique()
        logger.debug(f"Found codes in file: {all_codes}")
        
        # Check main branch codes first
        for branch_code in ["11", "21", "31", "41", "51"]:
            if branch_code in all_codes:
                logger.info(f"Detected main branch: {branch_code}")
                return branch_code
        
        # If no main branch, check for warehouse (SP)
        if "00" in all_codes:
            logger.info("Detected warehouse (SP)")
            return "SP"
        
        logger.warning("No recognized branch code found")
        return None
        
    except Exception as e:
        logger.error(f"Error detecting branch: {e}", exc_info=True)
        return None

# ==================== DATA VALIDATION ====================
def validate_excel_structure(df: pd.DataFrame) -> Tuple[bool, str]:
    """
    ตรวจสอบโครงสร้าง Excel file
    
    Args:
        df: DataFrame to validate
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    required_columns = ["ReBplus", "1=SP,2=WH"]
    
    # Check required columns
    for col in required_columns:
        if col not in df.columns:
            msg = f"Required column missing: {col}"
            logger.error(msg)
            return False, msg
    
    # Check for invalid '0' values in type column
    if (df["1=SP,2=WH"] == 0).any():
        msg = "❌ [ERROR]: ตรวจพบค่า '0' ในคอลัมน์ 1=SP,2=WH ซึ่งไม่ถูกต้อง!"
        logger.error(msg)
        return False, msg
    
    logger.debug("Excel structure validation passed")
    return True, ""

# ==================== DATA CLEANING ====================
def clean_excel_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    ทำความสะอาดข้อมูล Excel
    
    Args:
        df: DataFrame to clean
    
    Returns:
        Cleaned DataFrame
    """
    try:
        if "RECEIVE_PIECE" in df.columns:
            # Clear ReBplus for rows where RECEIVE_PIECE == 0
            initial_count = len(df)
            df.loc[df["RECEIVE_PIECE"] == 0, "ReBplus"] = np.nan
            cleared_count = len(df[df["ReBplus"].isna()])
            logger.info(f"Cleaned {cleared_count} rows where RECEIVE_PIECE == 0")
        
        return df
    except Exception as e:
        logger.error(f"Error cleaning data: {e}", exc_info=True)
        return df

# ==================== PATH MANAGEMENT ====================
def merge_paths(user_paths: Dict[str, str]) -> Dict[str, str]:
    """
    รวม user paths กับ default paths
    User paths มีความสำคัญมากกว่า (override)
    
    Args:
        user_paths: User-provided paths
    
    Returns:
        Merged paths dictionary
    """
    merged = DEFAULT_PATHS.copy()
    if user_paths:
        merged.update(user_paths)
        logger.info(f"Merged {len(user_paths)} user paths with defaults")
    
    return merged

def ensure_directory_exists(path: str) -> bool:
    """
    สร้างโฟลเดอร์ถ้ายังไม่มี
    
    Args:
        path: Directory path
    
    Returns:
        True if directory exists or was created, False otherwise
    """
    try:
        os.makedirs(path, exist_ok=True)
        logger.debug(f"Directory ready: {path}")
        return True
    except Exception as e:
        logger.error(f"Failed to create directory {path}: {e}")
        return False

# ==================== FILE GENERATION ====================
def get_thai_date_suffix() -> str:
    """
    สร้าง date suffix ในรูปแบบไทย
    เช่น "17-5-69 รับ"
    
    Returns:
        Date suffix string
    """
    now = datetime.now()
    thai_year = (now.year + 543 - 2500)
    return DATE_FORMAT_THAI.format(thai_year).replace("%d", str(now.day)).replace("%m", str(now.month))

def save_output_file(filepath: str, data: pd.Series) -> bool:
    """
    บันทึกข้อมูลลง .txt file
    
    Args:
        filepath: Output file path
        data: Data to save
    
    Returns:
        True if successful
    """
    try:
        content = '\n'.join(data.astype(str).tolist())
        with open(filepath, 'w', encoding=OUTPUT_FILE_ENCODING) as f:
            f.write(content)
        logger.info(f"File saved: {filepath} ({len(data)} rows)")
        return True
    except Exception as e:
        logger.error(f"Failed to save file {filepath}: {e}", exc_info=True)
        return False

# ==================== FILTER & EXTRACT DATA ====================
def extract_middle_code(df: pd.DataFrame) -> pd.Series:
    """
    Extract middle code (position 2) from ReBplus
    
    Args:
        df: DataFrame
    
    Returns:
        Series of extracted codes
    """
    sku_str = df["ReBplus"].astype(str).str.strip()
    return sku_str.str.split(",").str.get(2).str.strip()

def get_type_column(df: pd.DataFrame) -> pd.Series:
    """
    Get type column (1=SP, 2=WH) with fallback logic
    
    Args:
        df: DataFrame
    
    Returns:
        Type column Series
    """
    type_col_name = "1=SP,2=WH"
    
    if type_col_name in df.columns:
        return df[type_col_name]
    
    # Fallback: try to find similar column
    alt_names = [c for c in df.columns if "1=" in str(c) or "WH" in str(c)]
    if alt_names:
        logger.warning(f"Using alternative column: {alt_names[0]}")
        return df[alt_names[0]]
    
    # Last resort: use second column
    logger.warning("Using column index 1 as fallback")
    return df.iloc[:, 1]

# ==================== MAIN PROCESSING FUNCTION ====================
def process_excel_file(
    file_path: str,
    paths_config: Dict[str, str]
) -> Dict:
    """
    ประมวลผลไฟล์ Excel หลัก
    
    Args:
        file_path: Path to Excel file
        paths_config: User-provided paths configuration
    
    Returns:
        Processing result dictionary
    """
    logger.info(f"Starting file processing: {file_path}")
    
    try:
        # ===== 1. Read Excel File =====
        df = pd.read_excel(file_path)
        logger.info(f"Excel loaded: {df.shape[0]} rows, {df.shape[1]} columns")
        
        # ===== 2. Validate Structure =====
        is_valid, error_msg = validate_excel_structure(df)
        if not is_valid:
            return {
                "success": False,
                "message": error_msg,
                "detected_branch": None
            }
        
        # ===== 3. Clean Data =====
        df = clean_excel_data(df)
        
        # ===== 4. Detect Branch =====
        detected_branch = detect_file_branch(df)
        if not detected_branch:
            msg = "❌ ไม่พบโครงสร้างรหัสสาขาที่ถูกต้องในไฟล์"
            logger.error(msg)
            return {
                "success": False,
                "message": msg,
                "detected_branch": None
            }
        
        # ===== 5. Merge Paths =====
        merged_paths = merge_paths(paths_config)
        logger.info(f"Using paths for branch {detected_branch}")
        
        # ===== 6. Extract Branch Info =====
        branch_name = BRANCH_NAMES.get(detected_branch, detected_branch)
        date_suffix = get_thai_date_suffix()
        
        # ===== 7. Extract Data & Codes =====
        extracted_code = extract_middle_code(df)
        col_type = get_type_column(df)
        
        results = []
        
        # ===== 8. Filter & Save Front Store (SP) =====
        logger.info(f"Processing {branch_name} data...")
        
        if detected_branch == "SP":
            cond_main = (extracted_code == "00")
        else:
            cond_main = col_type.isin([1, 1.0, "1", "1.0"]) & (extracted_code == detected_branch)
        
        main_data = df.loc[cond_main, "ReBplus"]
        
        if not main_data.empty:
            main_file_name = f"{branch_name}-SP-{date_suffix}.txt"
            main_path = merged_paths.get(detected_branch)
            
            if main_path and ensure_directory_exists(main_path):
                main_full_path = os.path.join(main_path, main_file_name)
                if save_output_file(main_full_path, main_data):
                    results.append(f"🏪 เซฟหน้าร้าน: {main_file_name} ({len(main_data)} แถว)")
        
        # ===== 9. Filter & Save Warehouse (WH) =====
        if detected_branch == "SP":
            data_00 = pd.Series([])
        else:
            cond_00 = (
                col_type.isin([2, 2.0, "2", "2.0"]) | 
                col_type.isna() | 
                (col_type.astype(str).str.strip() == "nan")
            ) & (extracted_code == "00")
            data_00 = df.loc[cond_00, "ReBplus"]
        
        if isinstance(data_00, pd.Series) and not data_00.empty:
            file_name_00 = f"{branch_name}-WH-{date_suffix}.txt"
            key_00 = f"{detected_branch}_00"
            path_00 = merged_paths.get(key_00)
            
            if path_00 and ensure_directory_exists(path_00):
                full_path_00 = os.path.join(path_00, file_name_00)
                if save_output_file(full_path_00, data_00):
                    results.append(f"🏢 เซฟโกดัง: {file_name_00} ({len(data_00)} แถว)")
        else:
            if detected_branch != "SP":
                logger.warning("No warehouse data found for filtering")
        
        # ===== 10. Return Results =====
        if not results:
            results.append("⚠️ ไม่มีข้อมูลที่ตรงกับเงื่อนไข")
        
        logger.info(f"Processing complete. Results: {len(results)}")
        
        return {
            "success": True,
            "message": f"✅ ประมวลผลสำเร็จ!\n" + "\n".join(results),
            "detected_branch": detected_branch,
            "branch_name": branch_name,
            "files_saved": results
        }
        
    except Exception as e:
        logger.error(f"Processing failed: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"❌ เกิดข้อผิดพลาด: {str(e)}",
            "detected_branch": None,
            "error_details": str(e)
        }
