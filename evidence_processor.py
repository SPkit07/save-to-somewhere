import os
import sys
import json
import base64
import uuid
import datetime
from pathlib import Path
import eel
from logger import logger

def get_evidence_base_dir() -> str:
    """
    Get the directory where evidence folder should be placed.
    When compiled with PyInstaller, this is the folder where the .exe file lives.
    """
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    # Check if dist/ExcelProcessor exists (compiled output)
    dist_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dist", "ExcelProcessor")
    if os.path.isdir(dist_dir):
        return dist_dir
    return os.path.dirname(os.path.abspath(__file__))

def get_evidence_dir() -> str:
    return os.path.join(get_evidence_base_dir(), "evidence")

def get_db_file() -> str:
    return os.path.join(get_evidence_dir(), "evidence_db.json")

def init_db():
    evidence_dir = get_evidence_dir()
    db_file = get_db_file()
    if not os.path.exists(evidence_dir):
        os.makedirs(evidence_dir, exist_ok=True)
    if not os.path.exists(db_file):
        # Check if there is an existing database inside _internal/evidence to migrate
        internal_db = os.path.join(os.path.dirname(os.path.abspath(__file__)), "evidence", "evidence_db.json")
        if os.path.exists(internal_db):
            try:
                import shutil
                shutil.copy2(internal_db, db_file)
            except Exception as e:
                logger.warning(f"Could not copy existing db from _internal: {e}")
                with open(db_file, 'w', encoding='utf-8') as f:
                    json.dump({"records": []}, f)
        else:
            with open(db_file, 'w', encoding='utf-8') as f:
                json.dump({"records": []}, f)

def load_db():
    init_db()
    with open(get_db_file(), 'r', encoding='utf-8') as f:
        return json.load(f)

def save_db(data):
    init_db()
    with open(get_db_file(), 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

@eel.expose
def save_evidence(branch: str, date_str: str, product_name: str, quantity: str, barcode: str, image_base64_list: list):
    try:
        init_db()
        # Parse date to ensure format YYYY-MM-DD
        try:
            dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            dt = datetime.datetime.now()
            date_str = dt.strftime("%Y-%m-%d")
            
        month_str = dt.strftime("%Y-%m")
        
        # Create branch/month/date folder
        target_dir = os.path.join(get_evidence_dir(), branch, month_str, date_str)
        os.makedirs(target_dir, exist_ok=True)
        
        record_id = str(uuid.uuid4())
        saved_images = []
        
        for idx, img_b64 in enumerate(image_base64_list):
            if not img_b64:
                continue
                
            # Handle data URI scheme if present (e.g. data:image/jpeg;base64,...)
            if "," in img_b64:
                img_b64 = img_b64.split(",")[1]
                
            img_ext = "jpg" # Default to jpg
            img_filename = f"{record_id}_{idx}.{img_ext}"
            img_path = os.path.join(target_dir, img_filename)
            
            with open(img_path, "wb") as fh:
                fh.write(base64.b64decode(img_b64))
                
            # Store relative path for UI
            rel_path = f"evidence/{branch}/{month_str}/{date_str}/{img_filename}"
            saved_images.append(rel_path)
            
        # If no images were saved, we still create the record but with empty images
        
        new_record = {
            "id": record_id,
            "branch": branch,
            "date": date_str,
            "month": month_str,
            "product_name": product_name,
            "quantity": quantity,
            "barcode": barcode,
            "images": saved_images,
            "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        db = load_db()
        db["records"].append(new_record)
        save_db(db)
        
        return {"success": True, "message": "บันทึกหลักฐานเรียบร้อยแล้ว", "record": new_record}
        
    except Exception as e:
        logger.error(f"Error saving evidence: {e}")
        return {"success": False, "message": f"เกิดข้อผิดพลาด: {str(e)}"}

@eel.expose
def get_evidence_tree():
    try:
        db = load_db()
        records = db.get("records", [])
        
        # Structure: { branch: { month: [day1, day2, ...] } }
        tree = {}
        
        for r in records:
            branch = r.get("branch", "Unknown")
            date_str = r.get("date", "")
            if not date_str:
                continue
                
            month_str = r.get("month", date_str[:7] if len(date_str) >= 7 else "Unknown")
            
            if branch not in tree:
                tree[branch] = {}
                
            if month_str not in tree[branch]:
                tree[branch][month_str] = set()
                
            tree[branch][month_str].add(date_str)
            
        # Convert sets to sorted lists
        result_tree = {}
        for b, months in tree.items():
            result_tree[b] = {}
            for m, days in months.items():
                result_tree[b][m] = sorted(list(days), reverse=True)
                
        return {"success": True, "tree": result_tree}
        
    except Exception as e:
        logger.error(f"Error getting evidence tree: {e}")
        return {"success": False, "tree": {}}

@eel.expose
def get_evidence_by_date(branch: str, date_str: str):
    try:
        db = load_db()
        records = db.get("records", [])
        
        filtered = [
            r for r in records 
            if r.get("branch") == branch and r.get("date") == date_str
        ]
        
        # Sort by creation time desc
        filtered.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        
        return {"success": True, "records": filtered}
        
    except Exception as e:
        logger.error(f"Error getting evidence by date: {e}")
        return {"success": False, "records": []}

@eel.expose
def delete_evidence(record_id: str):
    try:
        db = load_db()
        record_to_delete = None
        for i, r in enumerate(db["records"]):
            if r.get("id") == record_id:
                record_to_delete = r
                del db["records"][i]
                break
                
        if record_to_delete:
            # Try to delete associated images
            for img_rel_path in record_to_delete.get("images", []):
                rel_clean = img_rel_path.replace("/", os.sep)
                # Primary path in app base dir
                abs_path = os.path.join(get_evidence_base_dir(), rel_clean)
                try:
                    if os.path.exists(abs_path):
                        os.remove(abs_path)
                    else:
                        # Fallback path in _internal
                        fallback_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), rel_clean)
                        if os.path.exists(fallback_path):
                            os.remove(fallback_path)
                except Exception as e:
                    logger.warning(f"Could not delete image {abs_path}: {e}")
                    
            save_db(db)
            return {"success": True, "message": "ลบข้อมูลเรียบร้อยแล้ว"}
        else:
            return {"success": False, "message": "ไม่พบข้อมูลที่ต้องการลบ"}
            
    except Exception as e:
        logger.error(f"Error deleting evidence: {e}")
        return {"success": False, "message": f"เกิดข้อผิดพลาด: {str(e)}"}

@eel.expose
def get_image_base64(rel_path: str):
    """
    Returns base64 string of the image (with data URI prefix) for the UI.
    rel_path example: evidence/K1/2026-09/2026-09-02/uuid_0.jpg
    """
    try:
        rel_clean = rel_path.replace("/", os.sep)
        # Primary path (beside .exe)
        abs_path = os.path.join(get_evidence_base_dir(), rel_clean)
        if not os.path.exists(abs_path):
            # Fallback path (inside _internal)
            fallback_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), rel_clean)
            if os.path.exists(fallback_path):
                abs_path = fallback_path

        if os.path.exists(abs_path):
            with open(abs_path, "rb") as fh:
                b64_str = base64.b64encode(fh.read()).decode('utf-8')
                
            # Determine extension
            ext = abs_path.split('.')[-1].lower()
            mime = f"image/{ext}" if ext in ["jpg", "jpeg", "png", "gif"] else "image/jpeg"
            return f"data:{mime};base64,{b64_str}"
            
    except Exception as e:
        logger.error(f"Error loading image {rel_path}: {e}")
        
    return None
