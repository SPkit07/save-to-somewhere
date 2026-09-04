import os
import json
import base64
import uuid
import datetime
from pathlib import Path
import eel
from logger import logger

EVIDENCE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "evidence")
DB_FILE = os.path.join(EVIDENCE_DIR, "evidence_db.json")

def init_db():
    if not os.path.exists(EVIDENCE_DIR):
        os.makedirs(EVIDENCE_DIR)
    if not os.path.exists(DB_FILE):
        with open(DB_FILE, 'w', encoding='utf-8') as f:
            json.dump({"records": []}, f)

def load_db():
    init_db()
    with open(DB_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_db(data):
    with open(DB_FILE, 'w', encoding='utf-8') as f:
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
        target_dir = os.path.join(EVIDENCE_DIR, branch, month_str, date_str)
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
            "product_name": product_name.strip() if product_name else "Unknown",
            "quantity": str(quantity),
            "barcode": str(barcode).strip() if barcode else "",
            "images": saved_images,
            "created_at": datetime.datetime.now().isoformat()
        }
        
        db = load_db()
        db["records"].append(new_record)
        save_db(db)
        
        logger.info(f"Saved evidence for {product_name} in {branch} on {date_str} with {len(saved_images)} images")
        return {"success": True, "message": "บันทึกหลักฐานเรียบร้อยแล้ว"}
        
    except Exception as e:
        logger.error(f"Error saving evidence: {e}", exc_info=True)
        return {"success": False, "message": f"เกิดข้อผิดพลาด: {str(e)}"}

@eel.expose
def get_evidence_tree():
    try:
        db = load_db()
        tree = {}
        for r in db["records"]:
            b = r.get("branch", "Unknown")
            m = r.get("month", "Unknown")
            d = r.get("date", "Unknown")
            
            if b not in tree:
                tree[b] = {}
            if m not in tree[b]:
                tree[b][m] = set()
            
            tree[b][m].add(d)
            
        # Convert sets to sorted lists
        for b in tree:
            for m in tree[b]:
                tree[b][m] = sorted(list(tree[b][m]), reverse=True)
                
        return {"success": True, "tree": tree}
    except Exception as e:
        logger.error(f"Error getting evidence tree: {e}")
        return {"success": False, "tree": {}}

@eel.expose
def get_evidence_by_date(branch: str, date_str: str):
    try:
        db = load_db()
        records = [r for r in db["records"] if r.get("branch") == branch and r.get("date") == date_str]
        
        # Sort by creation time, newest first
        records.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return {"success": True, "records": records}
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
                # Convert relative path to absolute
                abs_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), img_rel_path.replace("/", os.sep))
                try:
                    if os.path.exists(abs_path):
                        os.remove(abs_path)
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
        abs_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), rel_path.replace("/", os.sep))
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
