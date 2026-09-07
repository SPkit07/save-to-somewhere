"""
lan_sync.py - ระบบส่งและรับข้อมูลบาร์โค้ดและรูปภาพหลักฐานผ่านเครือข่ายวงแลน (LAN)
รองรับการค้นหาเครื่องอัตโนมัติ (UDP Broadcast), การระบุชื่อเจ้าของเครื่อง,
การส่งคำขอพร้อมป็อปอัปผู้รับ, และการผสานข้อมูล (Merge & Append)
"""

import os
import sys
import json
import base64
import socket
import threading
import time
import uuid
import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
import eel
from logger import logger

# Ports
LAN_HTTP_PORT = 18999
LAN_UDP_PORT = 18998

# Global state
_server_instance = None
_server_thread = None
_udp_thread = None
_pending_transfers = {}  # transfer_id -> {"event": threading.Event(), "response": None, "data": ...}
_pending_lock = threading.Lock()


from config import (
    get_app_config_dir,
    get_paths_config_path,
    get_problematic_barcodes_path,
    get_lan_config_path
)


def get_local_ip() -> str:
    """ดึงหมายเลข IPv4 ของเครื่องในวง LAN"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.5)
        # ไม่จำเป็นต้องเชื่อมต่อจริง เพียงให้ socket หา interface ที่ออก LAN
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return "127.0.0.1"


# ==================== BARCODE STORAGE HELPERS ====================

def read_problematic_barcodes() -> list:
    """อ่านข้อมูล problematic_barcodes.json จากตำแหน่งที่ถูกต้อง"""
    paths_to_try = [
        get_problematic_barcodes_path(),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "problematic_barcodes.json"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "dist", "ExcelProcessor", "problematic_barcodes.json"),
    ]
    for p in paths_to_try:
        if p and os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        return data
            except Exception as e:
                logger.warning(f"Error reading problematic barcodes from {p}: {e}")
    return []


def write_problematic_barcodes(barcodes: list) -> bool:
    """บันทึกข้อมูล problematic_barcodes.json ในทุกตำแหน่งที่เกี่ยวข้อง"""
    success = False
    paths_to_write = [
        get_problematic_barcodes_path(),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "problematic_barcodes.json"),
    ]
    dist_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dist", "ExcelProcessor", "problematic_barcodes.json")
    if os.path.isdir(os.path.dirname(dist_file)):
        paths_to_write.append(dist_file)

    for p in set(paths_to_write):
        try:
            os.makedirs(os.path.dirname(os.path.abspath(p)), exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                json.dump(barcodes, f, ensure_ascii=False, indent=4)
            success = True
        except Exception as e:
            logger.warning(f"Error writing problematic barcodes to {p}: {e}")
    return success


# ==================== DEVICE OWNER CONFIG ====================

def get_device_owner_name() -> str:
    """ดึงชื่อเจ้าของเครื่อง / ชื่อประจำเครื่อง"""
    # 1. ตรวจสอบ lan_config.json ก่อน (แยกเฉพาะ LAN เพื่อความปลอดภัยจากการถูก overwrite)
    lan_cfg_file = get_lan_config_path()
    try:
        if os.path.exists(lan_cfg_file):
            with open(lan_cfg_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                val = data.get("device_owner_name")
                if val and str(val).strip():
                    return str(val).strip()
    except Exception as e:
        logger.debug(f"Could not read from lan_config.json: {e}")

    # 2. ตรวจสอบ paths_config.json ใน runtime folder
    paths_cfg_file = get_paths_config_path()
    try:
        if os.path.exists(paths_cfg_file):
            with open(paths_cfg_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                val = data.get("device_owner_name")
                if val and str(val).strip():
                    return str(val).strip()
    except Exception as e:
        logger.debug(f"Could not read from paths_config.json: {e}")

    # 3. ตรวจสอบ root และ dist paths_config.json
    fallback_paths = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "paths_config.json"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "lan_config.json"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "dist", "ExcelProcessor", "paths_config.json"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "dist", "ExcelProcessor", "lan_config.json"),
    ]
    for fp in fallback_paths:
        if os.path.exists(fp):
            try:
                with open(fp, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    val = data.get("device_owner_name")
                    if val and str(val).strip():
                        return str(val).strip()
            except Exception:
                pass

    # 4. Default to Windows username or hostname
    username = os.environ.get("USERNAME") or os.environ.get("USER") or ""
    hostname = socket.gethostname()
    if username:
        return f"{username} ({hostname})"
    return hostname


def save_device_owner_name(name: str) -> bool:
    """บันทึกชื่อเจ้าของเครื่อง (ทั้งใน lan_config.json และ paths_config.json ทุกตำแหน่ง)"""
    clean_name = str(name).strip()
    if not clean_name:
        return False

    saved_any = False

    # 1. บันทึกลง lan_config.json ใน runtime directory
    try:
        lan_cfg = get_lan_config_path()
        lan_data = {}
        if os.path.exists(lan_cfg):
            try:
                with open(lan_cfg, "r", encoding="utf-8") as f:
                    lan_data = json.load(f)
            except Exception:
                lan_data = {}
        lan_data["device_owner_name"] = clean_name
        with open(lan_cfg, "w", encoding="utf-8") as f:
            json.dump(lan_data, f, ensure_ascii=False, indent=4)
        saved_any = True
    except Exception as e:
        logger.warning(f"Error saving to lan_config.json: {e}")

    # 2. บันทึกลง paths_config.json ใน runtime directory
    try:
        paths_cfg = get_paths_config_path()
        paths_data = {}
        if os.path.exists(paths_cfg):
            try:
                with open(paths_cfg, "r", encoding="utf-8") as f:
                    paths_data = json.load(f)
            except Exception:
                paths_data = {}
        paths_data["device_owner_name"] = clean_name
        with open(paths_cfg, "w", encoding="utf-8") as f:
            json.dump(paths_data, f, ensure_ascii=False, indent=4)
        saved_any = True
    except Exception as e:
        logger.warning(f"Error saving to paths_config.json: {e}")

    # 3. บันทึกซิงค์ไปยัง root directory
    root_cfg = os.path.join(os.path.dirname(os.path.abspath(__file__)), "paths_config.json")
    try:
        r_data = {}
        if os.path.exists(root_cfg):
            try:
                with open(root_cfg, "r", encoding="utf-8") as f:
                    r_data = json.load(f)
            except Exception:
                r_data = {}
        r_data["device_owner_name"] = clean_name
        with open(root_cfg, "w", encoding="utf-8") as f:
            json.dump(r_data, f, ensure_ascii=False, indent=4)
        saved_any = True
    except Exception as e:
        logger.warning(f"Error saving to root paths_config.json: {e}")

    # 4. บันทึกซิงค์ไปยัง dist directory ถ้ามี
    dist_cfg = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dist", "ExcelProcessor", "paths_config.json")
    if os.path.isdir(os.path.dirname(dist_cfg)):
        try:
            d_data = {}
            if os.path.exists(dist_cfg):
                try:
                    with open(dist_cfg, "r", encoding="utf-8") as f:
                        d_data = json.load(f)
                except Exception:
                    d_data = {}
            d_data["device_owner_name"] = clean_name
            with open(dist_cfg, "w", encoding="utf-8") as f:
                json.dump(d_data, f, ensure_ascii=False, indent=4)
            saved_any = True
        except Exception as e:
            logger.warning(f"Error saving to dist paths_config.json: {e}")

    logger.info(f"✅ Device owner name successfully saved: '{clean_name}'")
    return saved_any


# ==================== DATA MERGE LOGIC ====================

def merge_problematic_barcodes(incoming_barcodes: list) -> dict:
    """
    ผสานรายการบาร์โค้ดที่มีปัญหา:
    - ถ้าบาร์โค้ดมีอยู่แล้ว (ซ้ำ): รวมข้อมูล (Merge)
      * รวม error message: หากข้อความใหม่ต่างจากของเดิม ให้นำมารวมกันด้วย ' | ' (ไม่ซ้ำซ้อน)
      * อัปเดต/รวม recommended: หากของใหม่มีคำแนะนำ และเดิมไม่มีหรือต่างกัน
      * ปรับปรุง name: หากของใหม่มีชื่อ และเดิมไม่มี หรือชื่อเดิมสั้นกว่า
    - ถ้ายังไม่มี: นำไปต่อท้าย (Append/Add)
    - กำจัดรายการซ้ำซ้อนในไฟล์เดิม (Deduplicate)
    """
    existing = read_problematic_barcodes()
    
    # ดำเนินการสร้าง clean existing map โดยกำจัดตัวซ้ำเดิมใน existing ก่อน
    existing_map = {}  # barcode -> index ใน clean_list
    clean_existing = []

    for item in existing:
        if not isinstance(item, dict):
            continue
        b = str(item.get("barcode", "")).strip()
        if not b:
            continue
        if b in existing_map:
            # รวมตัวซ้ำที่มีอยู่เดิมเข้าด้วยกัน
            idx = existing_map[b]
            cur = clean_existing[idx]
            old_err = cur.get("error", "").strip()
            item_err = item.get("error", "").strip()
            if item_err and item_err != old_err and item_err not in old_err:
                cur["error"] = f"{old_err} | {item_err}" if old_err else item_err
            if item.get("recommended") and not cur.get("recommended"):
                cur["recommended"] = item.get("recommended")
            if item.get("name") and not cur.get("name"):
                cur["name"] = item.get("name")
            clean_existing[idx] = cur
        else:
            clean_existing.append({
                "name": str(item.get("name", "")).strip(),
                "barcode": b,
                "error": str(item.get("error", "")).strip(),
                "recommended": str(item.get("recommended", "")).strip()
            })
            existing_map[b] = len(clean_existing) - 1

    added_count = 0
    updated_count = 0

    for inc in incoming_barcodes:
        if not isinstance(inc, dict):
            continue
        b = str(inc.get("barcode", "")).strip()
        if not b:
            continue

        inc_name = str(inc.get("name", "")).strip()
        inc_error = str(inc.get("error", "")).strip()
        inc_recommended = str(inc.get("recommended", "")).strip()

        if b in existing_map:
            # มีอยู่แล้ว -> รวมข้อมูล (Merge)
            idx = existing_map[b]
            cur = clean_existing[idx]
            was_modified = False

            # รวม error message
            old_err = cur.get("error", "").strip()
            if inc_error:
                if not old_err:
                    cur["error"] = inc_error
                    was_modified = True
                elif inc_error != old_err and inc_error not in old_err:
                    # ถ้า old_err อยู่ใน inc_error ให้ใช้ inc_error ที่ละเอียดกว่า
                    if old_err in inc_error:
                        cur["error"] = inc_error
                    else:
                        cur["error"] = f"{old_err} | {inc_error}"
                    was_modified = True

            # รวม / อัปเดต recommended
            old_rec = cur.get("recommended", "").strip()
            if inc_recommended:
                if not old_rec:
                    cur["recommended"] = inc_recommended
                    was_modified = True
                elif inc_recommended != old_rec and inc_recommended not in old_rec:
                    if old_rec in inc_recommended:
                        cur["recommended"] = inc_recommended
                    else:
                        cur["recommended"] = f"{old_rec} | {inc_recommended}"
                    was_modified = True

            # ปรับปรุงชื่อสินค้า
            old_name = cur.get("name", "").strip()
            if inc_name and (not old_name or len(inc_name) > len(old_name)):
                cur["name"] = inc_name
                was_modified = True

            clean_existing[idx] = cur
            if was_modified:
                updated_count += 1
        else:
            # ยังไม่มี -> เพิ่มรายการใหม่ (Append)
            new_entry = {
                "name": inc_name,
                "barcode": b,
                "error": inc_error,
                "recommended": inc_recommended
            }
            clean_existing.append(new_entry)
            existing_map[b] = len(clean_existing) - 1
            added_count += 1

    write_problematic_barcodes(clean_existing)
    logger.info(f"✅ Merged problematic barcodes: {added_count} added, {updated_count} merged/updated, total {len(clean_existing)}")
    return {
        "added": added_count,
        "updated": updated_count,
        "total": len(clean_existing)
    }


def merge_evidence(incoming_records: list) -> dict:
    """
    ผสานรูปภาพและฐานข้อมูลหลักฐาน:
    - บันทึกไฟล์รูปภาพลงโฟลเดอร์ evidence
    - อัปเดตหรือเพิ่มลงใน evidence_db.json
    """
    from evidence_processor import get_evidence_dir, load_db, save_db
    
    base_evidence_dir = get_evidence_dir()
    db = load_db()
    existing_records = db.get("records", [])
    
    # Map existing records by id or (branch, date, product_name, barcode)
    id_map = {}
    content_map = {}
    for idx, r in enumerate(existing_records):
        rid = r.get("id")
        if rid:
            id_map[rid] = idx
        key = (r.get("branch", ""), r.get("date", ""), r.get("product_name", ""), r.get("barcode", ""))
        content_map[key] = idx
        
    saved_images_count = 0
    added_records = 0
    updated_records = 0
    
    for inc in incoming_records:
        branch = inc.get("branch", "Unknown")
        date_str = inc.get("date", datetime.datetime.now().strftime("%Y-%m-%d"))
        month_str = inc.get("month", date_str[:7] if len(date_str) >= 7 else "Unknown")
        prod_name = inc.get("product_name", "")
        barcode = inc.get("barcode", "")
        quantity = inc.get("quantity", "")
        
        target_dir = os.path.join(base_evidence_dir, branch, month_str, date_str)
        os.makedirs(target_dir, exist_ok=True)
        
        saved_img_rel_paths = []
        
        # Save image files from base64 payload
        images_payload = inc.get("images_data", [])
        for img_info in images_payload:
            img_b64 = img_info.get("base64", "")
            img_filename = img_info.get("filename", "")
            if not img_b64 or not img_filename:
                continue
                
            if "," in img_b64:
                img_b64 = img_b64.split(",")[1]
                
            dest_file = os.path.join(target_dir, img_filename)
            try:
                with open(dest_file, "wb") as fh:
                    fh.write(base64.b64decode(img_b64))
                rel_path = f"evidence/{branch}/{month_str}/{date_str}/{img_filename}"
                saved_img_rel_paths.append(rel_path)
                saved_images_count += 1
            except Exception as e:
                logger.error(f"Error writing image {dest_file}: {e}")
                
        # Check if record exists
        rec_id = inc.get("id")
        content_key = (branch, date_str, prod_name, barcode)
        
        matched_idx = None
        if rec_id and rec_id in id_map:
            matched_idx = id_map[rec_id]
        elif content_key in content_map:
            matched_idx = content_map[content_key]
            
        if matched_idx is not None:
            # Merge images into existing record
            cur = existing_records[matched_idx]
            cur_imgs = cur.get("images", [])
            for p in saved_img_rel_paths:
                if p not in cur_imgs:
                    cur_imgs.append(p)
            cur["images"] = cur_imgs
            if quantity and not cur.get("quantity"):
                cur["quantity"] = quantity
            existing_records[matched_idx] = cur
            updated_records += 1
        else:
            # Create new record
            new_id = rec_id or str(uuid.uuid4())
            new_rec = {
                "id": new_id,
                "branch": branch,
                "date": date_str,
                "month": month_str,
                "product_name": prod_name,
                "quantity": quantity,
                "barcode": barcode,
                "images": saved_img_rel_paths,
                "created_at": inc.get("created_at") or datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            existing_records.append(new_rec)
            id_map[new_id] = len(existing_records) - 1
            content_map[content_key] = len(existing_records) - 1
            added_records += 1
            
    db["records"] = existing_records
    save_db(db)
    logger.info(f"✅ Merged evidence: {added_records} records added, {updated_records} records updated, {saved_images_count} images saved")
    return {
        "records_added": added_records,
        "records_updated": updated_records,
        "images_saved": saved_images_count,
        "total_records": len(existing_records)
    }


# ==================== HTTP SERVER HANDLER ====================

class LANSyncHTTPHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Suppress standard logging to prevent console spam
        pass

    def _send_json(self, status_code: int, data: dict):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self._send_json(200, {"status": "ok"})

    def do_GET(self):
        if self.path == '/api/sync/ping':
            # Ping response for discovery
            self._send_json(200, {
                "app": "ExcelProcessor",
                "status": "ready",
                "device_name": socket.gethostname(),
                "owner_name": get_device_owner_name(),
                "ip": get_local_ip(),
                "port": LAN_HTTP_PORT
            })
        else:
            self._send_json(404, {"error": "Not found"})

    def do_POST(self):
        if self.path == '/api/sync/request':
            try:
                content_len = int(self.headers.get('Content-Length', 0))
                raw_body = self.rfile.read(content_len)
                payload = json.loads(raw_body.decode('utf-8'))
                
                transfer_id = str(uuid.uuid4())
                sender_owner = payload.get("sender_owner") or "เครื่องอื่นในวงแลน"
                sender_ip = payload.get("sender_ip") or self.client_address[0]
                sender_device = payload.get("sender_device") or sender_ip
                
                barcodes_list = payload.get("problematic_barcodes", [])
                evidence_list = payload.get("evidence_records", [])
                
                logger.info(f"📥 Received sync request from {sender_owner} ({sender_ip}) - Barcodes: {len(barcodes_list)}, Evidence: {len(evidence_list)}")
                
                # ทำการผสานข้อมูลทันที (Auto-Merge): "หากมีอยู่แล้วให้รวม ถ้าไม่มีก็เพิ่ม"
                barcode_res = merge_problematic_barcodes(barcodes_list)
                evidence_res = merge_evidence(evidence_list)
                
                # แจ้งเตือน Frontend ผ่าน Eel ให้ทราบและรีเฟรชหน้าจอ
                sync_summary = {
                    "transfer_id": transfer_id,
                    "sender_owner": sender_owner,
                    "sender_device": sender_device,
                    "sender_ip": sender_ip,
                    "barcodes": barcode_res,
                    "evidence": evidence_res
                }
                
                try:
                    if hasattr(eel, 'on_lan_sync_completed'):
                        eel.on_lan_sync_completed(sync_summary)()
                except Exception as err:
                    logger.debug(f"Frontend notification error (Eel): {err}")

                try:
                    if hasattr(eel, 'show_incoming_sync_modal'):
                        eel.show_incoming_sync_modal({
                            "transfer_id": transfer_id,
                            "sender_owner": sender_owner,
                            "sender_device": sender_device,
                            "sender_ip": sender_ip,
                            "barcodes_count": len(barcodes_list),
                            "evidence_count": len(evidence_list),
                            "images_count": sum(len(r.get("images_data", [])) for r in evidence_list),
                            "barcodes_preview": barcodes_list[:5],
                            "evidence_preview": [{
                                "product_name": r.get("product_name"),
                                "branch": r.get("branch"),
                                "date": r.get("date"),
                                "images_count": len(r.get("images_data", []))
                            } for r in evidence_list[:5]],
                            "auto_merged": True
                        })()
                except Exception as err:
                    logger.debug(f"Receiver modal error (Eel): {err}")

                # ส่งผลลัพธ์การรวมข้อมูลกลับไปให้เครื่องผู้ส่งทันที
                msg = f"รวมข้อมูลเรียบร้อยแล้ว: เพิ่มบาร์โค้ด {barcode_res.get('added', 0)} รายการ, รวมบาร์โค้ดเดิม {barcode_res.get('updated', 0)} รายการ, บันทึกรูปหลักฐาน {evidence_res.get('images_saved', 0)} รูป"
                self._send_json(200, {
                    "status": "accepted",
                    "message": msg,
                    "barcodes_result": barcode_res,
                    "evidence_result": evidence_res
                })
                logger.info(f"✅ Sync request processed successfully: {msg}")

            except Exception as e:
                logger.error(f"Error handling sync request: {e}", exc_info=True)
                self._send_json(500, {"status": "error", "message": f"ข้อผิดพลาดขณะรวมข้อมูล: {str(e)}"})
        else:
            self._send_json(404, {"error": "Not found"})


# ==================== UDP DISCOVERY BROADCAST ====================

def _udp_discovery_listener():
    """รับฟัง UDP Broadcast บนพอร์ต 18998 เพื่อตอบกลับข้อมูลเครื่อง"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(('', LAN_UDP_PORT))
        
        while True:
            try:
                data, addr = sock.recvfrom(2048)
                msg = json.loads(data.decode('utf-8'))
                if msg.get("app") == "ExcelProcessor" and msg.get("type") == "DISCOVER":
                    sender_ip = addr[0]
                    my_ip = get_local_ip()
                    
                    response = {
                        "app": "ExcelProcessor",
                        "type": "HERE_I_AM",
                        "device_name": socket.gethostname(),
                        "owner_name": get_device_owner_name(),
                        "ip": my_ip,
                        "port": LAN_HTTP_PORT
                    }
                    sock.sendto(json.dumps(response, ensure_ascii=False).encode('utf-8'), addr)
            except Exception:
                pass
    except Exception as e:
        logger.warning(f"UDP Discovery listener stopped: {e}")


def start_lan_sync_server():
    """เริ่มการทำงานของเซิร์ฟเวอร์ LAN ใน background"""
    global _server_instance, _server_thread, _udp_thread
    
    if _server_thread and _server_thread.is_alive():
        return
        
    try:
        _server_instance = HTTPServer(('0.0.0.0', LAN_HTTP_PORT), LANSyncHTTPHandler)
        _server_thread = threading.Thread(target=_server_instance.serve_forever, daemon=True)
        _server_thread.start()
        logger.info(f"🚀 LAN Sync Server running on port {LAN_HTTP_PORT}")
        
        _udp_thread = threading.Thread(target=_udp_discovery_listener, daemon=True)
        _udp_thread.start()
        logger.info(f"📡 LAN Discovery UDP Listener running on port {LAN_UDP_PORT}")
    except Exception as e:
        logger.error(f"❌ Failed to start LAN Sync Server: {e}")


# ==================== EEL EXPOSED FUNCTIONS ====================

@eel.expose
def get_my_device_info() -> dict:
    """ส่งข้อมูลเครื่องปัจจุบันให้ Frontend"""
    return {
        "ip": get_local_ip(),
        "device_name": socket.gethostname(),
        "owner_name": get_device_owner_name(),
        "port": LAN_HTTP_PORT
    }


@eel.expose
def save_my_owner_name(name: str) -> bool:
    """บันทึกชื่อเจ้าของเครื่อง"""
    return save_device_owner_name(name)


@eel.expose
def test_ping_device(target_ip: str) -> dict:
    """ทดสอบเชื่อมต่อไปยัง IP เครื่องปลายทาง"""
    clean_ip = str(target_ip).strip().replace("http://", "").replace("https://", "").strip()
    target_port = LAN_HTTP_PORT
    if ":" in clean_ip:
        parts = clean_ip.split(":")
        clean_ip = parts[0].strip()
        try:
            target_port = int(parts[1].split("/")[0].strip())
        except Exception:
            target_port = LAN_HTTP_PORT
    if "/" in clean_ip:
        clean_ip = clean_ip.split("/")[0].strip()

    if not clean_ip:
        return {"success": False, "message": "กรุณาระบุ IP ปลายทาง"}
        
    url = f"http://{clean_ip}:{target_port}/api/sync/ping"
    try:
        req = Request(url, headers={"User-Agent": "ExcelProcessor-LANSync"}, method='GET')
        with urlopen(req, timeout=3.0) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            return {
                "success": True,
                "message": "เชื่อมต่อสำเร็จ",
                "device": data
            }
    except Exception as e:
        err_msg = str(e)
        if "actively refused" in err_msg or "10061" in err_msg:
            err_msg = f"เครื่องปลายทางปฏิเสธการเชื่อมต่อ (อาจยังไม่ได้เปิดโปรแกรม หรือ Firewall บล็อกพอร์ต {target_port})"
        elif "timed out" in err_msg or "10060" in err_msg:
            err_msg = f"หมดเวลาเชื่อมต่อ (Timeout) ตรวจสอบว่าอยู่ใน WiFi/LAN เดียวกัน"
        return {"success": False, "message": f"ไม่สามารถเชื่อมต่อไปยัง {clean_ip}:{target_port}: {err_msg}"}


@eel.expose
def scan_lan_devices() -> list:
    """
    ค้นหาเครื่องที่เปิดโปรแกรมในวง LAN เดียวกัน
    1. ส่ง UDP Broadcast
    2. ทำ Fast HTTP Ping ใน Subnet เดียวกัน
    """
    discovered = {}
    my_ip = get_local_ip()
    
    # 1. UDP Broadcast Scan
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.settimeout(1.2)
        
        msg = json.dumps({"app": "ExcelProcessor", "type": "DISCOVER"}).encode('utf-8')
        sock.sendto(msg, ('<broadcast>', LAN_UDP_PORT))
        
        start_t = time.time()
        while time.time() - start_t < 1.2:
            try:
                data, addr = sock.recvfrom(2048)
                res = json.loads(data.decode('utf-8'))
                if res.get("app") == "ExcelProcessor":
                    ip = res.get("ip") or addr[0]
                    if ip != my_ip:
                        discovered[ip] = {
                            "ip": ip,
                            "device_name": res.get("device_name", ip),
                            "owner_name": res.get("owner_name") or res.get("device_name", ip),
                            "port": res.get("port", LAN_HTTP_PORT)
                        }
            except socket.timeout:
                break
            except Exception:
                pass
        sock.close()
    except Exception as e:
        logger.warning(f"UDP scan error: {e}")
        
    # 2. Subnet quick ping check around my_ip
    parts = my_ip.split(".")
    if len(parts) == 4 and parts[0] != "127":
        subnet_base = f"{parts[0]}.{parts[1]}.{parts[2]}"
        
        def _check_ip(ip_num):
            ip_str = f"{subnet_base}.{ip_num}"
            if ip_str == my_ip or ip_str in discovered:
                return
            try:
                req = Request(f"http://{ip_str}:{LAN_HTTP_PORT}/api/sync/ping", method='GET')
                with urlopen(req, timeout=0.6) as resp:
                    data = json.loads(resp.read().decode('utf-8'))
                    if data.get("app") == "ExcelProcessor":
                        discovered[ip_str] = {
                            "ip": ip_str,
                            "device_name": data.get("device_name", ip_str),
                            "owner_name": data.get("owner_name") or data.get("device_name", ip_str),
                            "port": LAN_HTTP_PORT
                        }
            except Exception:
                pass

        threads = []
        curr_num = int(parts[3])
        scan_range = [i for i in range(max(1, curr_num - 25), min(255, curr_num + 26)) if i != curr_num]
        for num in scan_range:
            t = threading.Thread(target=_check_ip, args=(num,))
            threads.append(t)
            t.start()
            
        for t in threads:
            t.join(timeout=1.0)
            
    return list(discovered.values())


@eel.expose
def respond_incoming_sync(transfer_id: str, accept: bool) -> bool:
    """ผู้รับกดปุ่มบน Modal (รองรับกรณีมีการตอบกลับ)"""
    with _pending_lock:
        if transfer_id in _pending_transfers:
            _pending_transfers[transfer_id]["accepted"] = bool(accept)
            _pending_transfers[transfer_id]["event"].set()
            return True
    return True


@eel.expose
def send_lan_sync(target_ip: str, selected_barcodes: list, selected_evidence_ids: list) -> dict:
    """
    ผู้ส่งส่งข้อมูลไปยังเครื่องเป้าหมาย:
    - ดึงข้อมูล barcodes ที่ถูกเลือก
    - ดึงข้อมูล evidence พร้อมแปลงรูปเป็น Base64
    - ส่ง HTTP POST /api/sync/request
    - ได้รับการตอบรับทันที
    """
    try:
        clean_ip = str(target_ip).strip().replace("http://", "").replace("https://", "").strip()
        target_port = LAN_HTTP_PORT
        if ":" in clean_ip:
            parts = clean_ip.split(":")
            clean_ip = parts[0].strip()
            try:
                target_port = int(parts[1].split("/")[0].strip())
            except Exception:
                target_port = LAN_HTTP_PORT
        if "/" in clean_ip:
            clean_ip = clean_ip.split("/")[0].strip()

        if not clean_ip:
            return {"success": False, "message": "กรุณาระบุ IP ปลายทาง"}

        # 1. รวบรวมข้อมูลบาร์โค้ดจากระบบจัดเก็บโดยตรง (ไม่พึ่งพา main.py)
        all_barcodes = read_problematic_barcodes()
        barcodes_to_send = []

        if selected_barcodes:
            selected_set = set(str(b).strip() for b in selected_barcodes if b)
            for item in all_barcodes:
                if isinstance(item, dict):
                    b_str = str(item.get("barcode", "")).strip()
                    if b_str and b_str in selected_set:
                        barcodes_to_send.append(item)

        # 2. รวบรวมข้อมูลหลักฐานและอ่านไฟล์รูปภาพเป็น base64
        from evidence_processor import load_db, get_evidence_base_dir
        evidence_db = load_db() or {}
        all_records = evidence_db.get("records", []) or []

        evidence_to_send = []
        base_dir = get_evidence_base_dir()

        if selected_evidence_ids:
            selected_id_set = set(str(eid).strip() for eid in selected_evidence_ids if eid)
            for rec in all_records:
                if isinstance(rec, dict) and str(rec.get("id", "")).strip() in selected_id_set:
                    rec_copy = dict(rec)
                    images_data = []
                    for rel_path in (rec.get("images", []) or []):
                        if not rel_path or not isinstance(rel_path, str):
                            continue
                        rel_clean = rel_path.replace("/", os.sep)
                        candidate_paths = [
                            os.path.join(base_dir, rel_clean),
                            os.path.join(base_dir, "_internal", rel_clean),
                            os.path.join(os.path.dirname(os.path.abspath(__file__)), rel_clean),
                            os.path.join(os.path.dirname(os.path.abspath(__file__)), "_internal", rel_clean),
                            os.path.join(os.path.dirname(os.path.abspath(__file__)), "dist", "ExcelProcessor", "_internal", rel_clean),
                            os.path.join(os.path.dirname(os.path.abspath(__file__)), "dist", "ExcelProcessor", rel_clean),
                        ]
                        abs_path = None
                        for cp in candidate_paths:
                            if os.path.exists(cp):
                                abs_path = cp
                                break

                        if abs_path and os.path.exists(abs_path):
                            try:
                                with open(abs_path, "rb") as fh:
                                    b64 = base64.b64encode(fh.read()).decode('utf-8')
                                images_data.append({
                                    "filename": os.path.basename(abs_path),
                                    "base64": b64
                                })
                            except Exception as e:
                                logger.error(f"Error encoding image {abs_path}: {e}")

                    rec_copy["images_data"] = images_data
                    evidence_to_send.append(rec_copy)

        if not barcodes_to_send and not evidence_to_send:
            return {"success": False, "message": "กรุณาเลือกข้อมูลอย่างน้อย 1 รายการเพื่อส่ง (บาร์โค้ด หรือ รูปหลักฐาน)"}

        payload = {
            "sender_owner": get_device_owner_name(),
            "sender_device": socket.gethostname(),
            "sender_ip": get_local_ip(),
            "timestamp": time.time(),
            "problematic_barcodes": barcodes_to_send,
            "evidence_records": evidence_to_send
        }

        url = f"http://{clean_ip}:{target_port}/api/sync/request"
        body = json.dumps(payload, ensure_ascii=False).encode('utf-8')

        try:
            req = Request(
                url,
                data=body,
                headers={
                    "Content-Type": "application/json; charset=utf-8",
                    "User-Agent": "ExcelProcessor-LANSync"
                },
                method='POST'
            )
            # ข้อมูลถูกผสานทันทีฝั่งปลายทาง ใช้เวลาเพียงไม่กี่วินาที
            with urlopen(req, timeout=30.0) as resp:
                res_data = json.loads(resp.read().decode('utf-8'))

                if res_data.get("status") == "accepted":
                    return {
                        "success": True,
                        "message": res_data.get("message", "รวมข้อมูลเข้าสู่เครื่องปลายทางเรียบร้อยแล้ว"),
                        "details": res_data
                    }
                elif res_data.get("status") == "rejected":
                    return {
                        "success": False,
                        "message": "เครื่องปลายทางปฏิเสธการรับข้อมูล"
                    }
                else:
                    return {
                        "success": False,
                        "message": res_data.get("message", "เกิดข้อผิดพลาดในการส่งข้อมูล")
                    }
        except HTTPError as e:
            return {"success": False, "message": f"เซิร์ฟเวอร์ปลายทางแจ้งข้อผิดพลาด: HTTP {e.code}"}
        except URLError as e:
            reason = str(e.reason)
            if "actively refused" in reason or "10061" in reason:
                return {"success": False, "message": f"ไม่สามารถเชื่อมต่อไปยัง {clean_ip}:{target_port} (เครื่องปลายทางยังไม่ได้เปิดโปรแกรม หรือถูกบล็อกโดย Windows Firewall)"}
            elif "timed out" in reason or "10060" in reason:
                return {"success": False, "message": f"การเชื่อมต่อไปยัง {clean_ip} หมดเวลา (Time out: ตรวจสอบว่าอยู่ใน WiFi/LAN เดียวกัน และเปิดสิทธิ์ Firewall)"}
            return {"success": False, "message": f"ไม่สามารถเชื่อมต่อไปยัง {clean_ip}: {reason}"}
        except Exception as e:
            return {"success": False, "message": f"เกิดข้อผิดพลาดในการส่งข้อมูล: {str(e)}"}

    except Exception as e:
        logger.error(f"Error in send_lan_sync: {e}", exc_info=True)
        return {"success": False, "message": f"ข้อผิดพลาดภายในระบบ: {str(e)}"}
