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
    ตรวจสอบว่า user ระบุ paths ทั้งหมดเอง
    ไม่มีค่าเริ่มต้น - ผู้ใช้จำเป็นต้องระบุเอง
    
    Args:
        user_paths: User-provided paths
    
    Returns:
        User paths (no defaults merged)
    """
    if not user_paths:
        logger.warning("No paths provided by user. All paths must be specified explicitly.")
        return {}
    
    logger.info(f"Using {len(user_paths)} user-provided paths")
    return user_paths

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
    thai_year = now.year + 543 - 2500
    return f"{now.day}-{now.month}-{thai_year} รับ"

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

# ==================== COLUMN J & K VALIDATION ====================
def check_columns_j_k_match(df: pd.DataFrame) -> Tuple[bool, list]:
    """
    ตรวจสอบว่าคอลัมน์ J และ K (ทั้งคู่มีชื่อ '1=SP,2=WH') ตรงกันหรือไม่
    
    Args:
        df: DataFrame
    
    Returns:
        Tuple of (all_match, error_details_list)
        - all_match: True ถ้าทั้งหมดตรงกัน, False ถ้ามีที่ไม่ตรง
        - error_details_list: List of dicts with mismatch information
    """
    try:
        # ค้นหาคอลัมน์ที่มีชื่อ "1=SP,2=WH"
        type_cols = [c for c in df.columns if "1=SP,2=WH" in str(c)]
        
        # ถ้าไม่มีหรือมีแค่อันเดียว ถือว่าไม่มีข้อมูลให้ตรวจสอบ
        if len(type_cols) < 2:
            logger.info("Found less than 2 columns with '1=SP,2=WH' - skipping J/K check")
            return True, []
        
        col_j, col_k = type_cols[0], type_cols[1]
        logger.info(f"Checking J & K match: {col_j} vs {col_k}")
        
        # แปลงค่าให้เป็นสตริง และลบช่องว่าง และลบ .0 (จากการแปลง float)
        val_j = df[col_j].fillna("").astype(str).str.strip().str.replace(r'\.0$', '', regex=True)
        val_k = df[col_k].fillna("").astype(str).str.strip().str.replace(r'\.0$', '', regex=True)
        
        # เปรียบเทียบ
        mismatch_mask = val_j != val_k
        
        if not mismatch_mask.any():
            logger.info("✅ All rows in columns J and K match perfectly")
            return True, []
        
        # มีการไม่ตรงกัน - สร้างรายการ error details
        mismatched_df = df[mismatch_mask].reset_index(drop=True)
        logger.warning(f"⚠️ Found {len(mismatched_df)} mismatched rows")
        
        # ค้นหาคอลัมน์ GOODS_CODE
        goods_code_col = "GOODS_CODE" if "GOODS_CODE" in df.columns else None
        
        # ค้นหาคอลัมน์ชื่อสินค้า (SKU_NAME หรือคอลัมน์ F)
        prod_name_col = None
        for candidate in ["SKU_NAME", "GOODS_NAME", "PRODUCT_NAME", "ITEM_NAME", "ชื่อสินค้า", "GOODS_DESC"]:
            if candidate in df.columns:
                prod_name_col = candidate
                logger.info(f"Found product name column: {candidate}")
                break
        
        # Fallback ไปที่คอลัมน์ F (index 5)
        if not prod_name_col and len(df.columns) > 5:
            prod_name_col = df.columns[5]
            logger.info(f"Using column F as product name: {prod_name_col}")
        
        error_details = []
        for idx, row in mismatched_df.iterrows():
            # ดึงข้อมูล GOODS_CODE
            code = ""
            if goods_code_col and goods_code_col in row.index:
                code = row[goods_code_col] if pd.notna(row[goods_code_col]) else ""
            code = str(code).strip() if code else "-"
            
            # ดึงข้อมูล SKU_NAME หรือชื่อสินค้า
            name = ""
            if prod_name_col and prod_name_col in row.index:
                name = row[prod_name_col] if pd.notna(row[prod_name_col]) else ""
            name = str(name).strip() if name else "-"
            
            # ดึงค่าจากคอลัมน์ J และ K
            col_j_val = str(row[col_j]).replace(".0", "").strip() if pd.notna(row[col_j]) else "-"
            col_k_val = str(row[col_k]).replace(".0", "").strip() if pd.notna(row[col_k]) else "-"
            
            error_details.append({
                "row": idx + 1,  # บันทึกแถวจริง (ไม่นับจาก 0)
                "goods_code": code,
                "sku_name": name,
                "col_j": col_j_val,
                "col_k": col_k_val
            })
        
        logger.info(f"Generated {len(error_details)} error detail entries")
        return False, error_details
        
    except Exception as e:
        logger.error(f"Error checking J & K columns: {e}", exc_info=True)
        # ถ้าเกิดข้อผิดพลาด ให้ถือว่าไม่มีการไม่ตรงกัน (ไม่ยุติการประมวลผล)
        return True, []

# ==================== MAIN PROCESSING FUNCTION ====================
def process_excel_file(
    file_path: str,
    paths_config: Dict[str, str]
) -> Dict:
    """
    ประมวลผลไฟล์ Excel หลัก (ทำตาม Save.ipynb แบบเป๊ะๆ)
    """
    logger.info(f"Starting file processing: {file_path}")
    
    try:
        # ===== 1. Read Excel File =====
        df = pd.read_excel(file_path)
        logger.info(f"Excel loaded: {df.shape[0]} rows, {df.shape[1]} columns")
        
        # ===== 2. Validation like Save.ipynb =====
        if "1=SP,2=WH" in df.columns:
            if (df["1=SP,2=WH"] == 0).any():
                error_msg = "ตรวจพบค่า '0' ในคอลัมน์ 1=SP,2=WH ซึ่งไม่ถูกต้อง!"
                logger.error(error_msg)
                return {
                    "success": False,
                    "errors": ["[ERROR]", error_msg],
                    "detected_branch": None,
                    "message": error_msg
                }

        # ===== 2b. Check Column J & K Match (ตรวจสอบว่า J และ K ตรงกันหรือไม่) =====
        j_k_match, j_k_mismatches = check_columns_j_k_match(df)
        warnings = []
        
        if not j_k_match and j_k_mismatches:
            warning_msg = f"⚠️ [WARNING]: ตรวจพบความไม่ตรงกันในคอลัมน์ J และ K ({len(j_k_mismatches)} รายการ)"
            warnings.append({
                "type": "j_k_mismatch",
                "message": warning_msg,
                "details": j_k_mismatches,
                "count": len(j_k_mismatches)
            })
            logger.warning(warning_msg)
                
        # ===== 3. Clean Data like Save.ipynb =====
        if "RECEIVE_PIECE" in df.columns:
            df.loc[df["RECEIVE_PIECE"] == 0, "ReBplus"] = np.nan
            logger.info("🧹 เคลียร์ค่าว่างสำหรับแถวที่ RECEIVE_PIECE == 0 เรียบร้อยแล้ว")
            
        # Date Suffix
        now = datetime.now()
        thai_year = now.year + 543 - 2500
        DATE_SUFFIX = f"{now.day}-{now.month}-{thai_year} รับ"
        
        # ===== 4. Detect Branch like Save.ipynb =====
        if "ReBplus" not in df.columns:
            error_msg = "ไม่พบ Column 'ReBplus'"
            return {
                "success": False,
                "errors": ["[ERROR]", error_msg],
                "detected_branch": None,
                "message": error_msg
            }
            
        all_codes = df["ReBplus"].astype(str).str.split(",").str.get(2).str.strip().unique()
        current_branch = None
        for branch_code in ["11", "21", "31", "41", "51"]:
            if branch_code in all_codes:
                current_branch = branch_code
                break
        if not current_branch and "00" in all_codes:
            current_branch = "SP"
            
        if current_branch is None:
            error_msg = "ไม่พบโครงสร้างรหัสสาขาที่ถูกต้องในไฟล์นี้  ไม่สามารถประมวลผลได้"
            logger.error(error_msg)
            return {
                "success": False,
                "errors": ["[ERROR]", error_msg],
                "detected_branch": None,
                "message": error_msg
            }
            
        # ===== 5. Processing like Save.ipynb =====
        sku_str = df["ReBplus"].astype(str).str.strip()
        extracted_code = sku_str.str.split(",").str.get(2).str.strip()
        
        type_col_name = "1=SP,2=WH"
        if type_col_name in df.columns:
            col_type = df[type_col_name]
        else:
            alt_name = [c for c in df.columns if "1=" in str(c) or "WH" in str(c)]
            col_type = df[alt_name[0]] if alt_name else df.iloc[:, 1]
            
        b_name = BRANCH_NAMES.get(current_branch, current_branch)
        results = []
        
        merged_paths = paths_config if paths_config else {}
        
        # 🏪 [ส่วนที่ 1] กรองผ่านคอลัมน์ประเภท == 1 (หน้าร้าน)
        if current_branch == "SP":
            cond_main = (extracted_code == "00")
        else:
            cond_main = col_type.isin([1, 1.0, "1", "1.0"]) & (extracted_code == current_branch)
            
        main_data = df.loc[cond_main, "ReBplus"]
        
        if not main_data.empty:
            main_file_name = f"{b_name}-SP-{DATE_SUFFIX}.txt"
            main_path = merged_paths.get(current_branch)
            if main_path and ensure_directory_exists(main_path):
                main_full_path = os.path.join(main_path, main_file_name)
                with open(main_full_path, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(main_data.astype(str).tolist()))
                results.append(f"🏪 เซฟหน้าร้านสำเร็จ: {main_full_path} (รวม {len(main_data)} แถว)")
                
        # 🏢 [ส่วนที่ 2] กรองผ่านคอลัมน์ประเภท == 2 (โกดัง)
        if current_branch == "SP":
            data_00 = []
        else:
            cond_00 = (col_type.isin([2, 2.0, "2", "2.0"]) | col_type.isna() | (col_type.astype(str).str.strip() == "nan")) & (extracted_code == "00")
            data_00 = df.loc[cond_00, "ReBplus"]
            
        if not (isinstance(data_00, list) or data_00.empty):
            file_name_00 = f"{b_name}-WH-{DATE_SUFFIX}.txt"
            key_00 = f"{current_branch}_00"
            path_00 = merged_paths.get(key_00)
            if path_00 and ensure_directory_exists(path_00):
                full_path_00 = os.path.join(path_00, file_name_00)
                with open(full_path_00, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(data_00.astype(str).tolist()))
                results.append(f"🏢 เซฟโกดังสำเร็จ  : {full_path_00} (รวม {len(data_00)} แถว)")
        
        if not results:
            results.append("⚠️ ประมวลผลสำเร็จ แต่ไม่ได้เซฟไฟล์ใดๆ (กรุณาตั้งค่า Path ให้ครบถ้วน)")
            
        summary_msg = f"ประมวลผลสำเร็จ!"
        
        # สร้าง response
        response = {
            "success": True,
            "message": summary_msg,
            "summary": "\n".join(results),
            "detected_branch": current_branch,
            "branch_name": b_name,
            "files_saved": results
        }
        
        # เพิ่ม warnings ถ้ามี
        if warnings:
            response["warnings"] = warnings
            response["has_warnings"] = True
        else:
            response["has_warnings"] = False
        
        return response
        
    except Exception as e:
        logger.error(f"Processing failed: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"เกิดข้อผิดพลาด: {str(e)}",
            "errors": ["[ERROR]", str(e)],
            "detected_branch": None,
            "error_details": str(e)
        }
