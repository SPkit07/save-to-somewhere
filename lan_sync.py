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


def get_device_owner_name() -> str:
    """ดึงชื่อเจ้าของเครื่อง / ชื่อประจำเครื่อง"""
    try:
        from main import load_paths_config
        config = load_paths_config()
        owner = config.get("device_owner_name")
        if owner and owner.strip():
            return owner.strip()
    except Exception as e:
        logger.warning(f"Could not load device owner name from config: {e}")

    # Fallback to dist config if available
    try:
        dist_cfg = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dist", "ExcelProcessor", "paths_config.json")
        if os.path.exists(dist_cfg):
            with open(dist_cfg, "r", encoding="utf-8") as f:
                d = json.load(f)
                if d.get("device_owner_name") and d.get("device_owner_name").strip():
                    return d.get("device_owner_name").strip()
    except Exception:
        pass

    # Default to Windows username or hostname
    username = os.environ.get("USERNAME") or os.environ.get("USER") or ""
    hostname = socket.gethostname()
    if username:
        return f"{username} ({hostname})"
    return hostname


def save_device_owner_name(name: str) -> bool:
    """บันทึกชื่อเจ้าของเครื่อง (ทั้งใน root และ dist config)"""
    clean_name = str(name).strip()
    if not clean_name:
        return False

    saved_any = False

    # 1. Update via main.save_paths_config
    try:
        from main import load_paths_config, save_paths_config
        config = load_paths_config()
        config["device_owner_name"] = clean_name
        if save_paths_config(config):
            saved_any = True
    except Exception as e:
        logger.warning(f"save_paths_config failed: {e}")

    # 2. Save directly to dist/ExcelProcessor/paths_config.json
    dist_cfg = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dist", "ExcelProcessor", "paths_config.json")
    if os.path.exists(os.path.dirname(dist_cfg)):
        try:
            dist_data = {}
            if os.path.exists(dist_cfg):
                with open(dist_cfg, "r", encoding="utf-8") as f:
                    dist_data = json.load(f)
            dist_data["device_owner_name"] = clean_name
            with open(dist_cfg, "w", encoding="utf-8") as f:
                json.dump(dist_data, f, ensure_ascii=False, indent=4)
            saved_any = True
        except Exception as e:
            logger.warning(f"Writing dist paths_config.json failed: {e}")

    # 3. Save directly to root paths_config.json
    root_cfg = os.path.join(os.path.dirname(os.path.abspath(__file__)), "paths_config.json")
    try:
        root_data = {}
        if os.path.exists(root_cfg):
            with open(root_cfg, "r", encoding="utf-8") as f:
                root_data = json.load(f)
        root_data["device_owner_name"] = clean_name
        with open(root_cfg, "w", encoding="utf-8") as f:
            json.dump(root_data, f, ensure_ascii=False, indent=4)
        saved_any = True
    except Exception as e:
        logger.warning(f"Writing root paths_config.json failed: {e}")

    logger.info(f"✅ Device owner name saved: {clean_name}")
    return saved_any


# ==================== DATA MERGE LOGIC ====================

def merge_problematic_barcodes(incoming_barcodes: list) -> dict:
    """
    ผสานรายการบาร์โค้ดที่มีปัญหา:
    - ถ้าบาร์โค้ดซ้ำ ให้รวมข้อมูลและอัปเดตข้อมูลล่าสุด
    - ถ้าเป็นบาร์โค้ดใหม่ ให้นำไปต่อท้าย
    """
    from main import load_problematic_barcodes, save_problematic_barcodes
    
    existing = load_problematic_barcodes()
    existing_map = {}
    
    # Map by barcode
    for idx, item in enumerate(existing):
        b = str(item.get("barcode", "")).strip()
        if b:
            existing_map[b] = idx
            
    added_count = 0
    updated_count = 0
    
    for inc in incoming_barcodes:
        b = str(inc.get("barcode", "")).strip()
        if not b:
            continue
            
        if b in existing_map:
            # ซ้ำ -> อัปเดตข้อมูล / รวมข้อความ
            idx = existing_map[b]
            cur = existing[idx]
            # รวม error message ถ้าไม่เหมือนกัน
            old_err = cur.get("error", "").strip()
            new_err = inc.get("error", "").strip()
            if new_err and new_err != old_err and new_err not in old_err:
                cur["error"] = f"{old_err} | {new_err}" if old_err else new_err
                
            # อัปเดตชื่อหรือคำแนะนำถ้ามี
            if inc.get("recommended") and not cur.get("recommended"):
                cur["recommended"] = inc.get("recommended")
            if inc.get("name") and not cur.get("name"):
                cur["name"] = inc.get("name")
                
            existing[idx] = cur
            updated_count += 1
        else:
            # ไม่ซ้ำ -> นำไปต่อท้าย
            existing.append({
                "name": inc.get("name", ""),
                "barcode": b,
                "error": inc.get("error", ""),
                "recommended": inc.get("recommended", "")
            })
            existing_map[b] = len(existing) - 1
            added_count += 1
            
    save_problematic_barcodes(existing)
    logger.info(f"✅ Merged problematic barcodes: {added_count} added, {updated_count} updated")
    return {"added": added_count, "updated": updated_count, "total": len(existing)}


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
                
                total_images = sum(len(r.get("images_data", [])) for r in evidence_list)
                
                summary = {
                    "transfer_id": transfer_id,
                    "sender_owner": sender_owner,
                    "sender_device": sender_device,
                    "sender_ip": sender_ip,
                    "barcodes_count": len(barcodes_list),
                    "evidence_count": len(evidence_list),
                    "images_count": total_images,
                    "barcodes_preview": barcodes_list[:5],
                    "evidence_preview": [{
                        "product_name": r.get("product_name"),
                        "branch": r.get("branch"),
                        "date": r.get("date"),
                        "images_count": len(r.get("images_data", []))
                    } for r in evidence_list[:5]]
                }
                
                # Create synchronization event
                transfer_event = threading.Event()
                with _pending_lock:
                    _pending_transfers[transfer_id] = {
                        "event": transfer_event,
                        "accepted": False,
                        "payload": payload,
                        "timestamp": time.time()
                    }
                    
                # Call Eel to notify frontend and show modal popup
                logger.info(f"📥 Received sync request from {sender_owner} ({sender_ip}) - ID: {transfer_id}")
                try:
                    if 'eel' in globals() and hasattr(eel, 'show_incoming_sync_modal'):
                        eel.show_incoming_sync_modal(summary)
                except Exception as err:
                    logger.error(f"Error notifying frontend of incoming sync: {err}")
                    
                # Wait for user action on the receiver modal (up to 90 seconds timeout)
                responded = transfer_event.wait(timeout=90.0)
                
                with _pending_lock:
                    transfer_info = _pending_transfers.pop(transfer_id, None)
                    
                if not responded:
                    logger.warning(f"⌛ Transfer request {transfer_id} timed out without user response")
                    self._send_json(408, {"status": "timeout", "message": "หมดเวลารอการตอบรับจากเครื่องปลายทาง (90s)"})
                    return
                    
                if transfer_info and transfer_info.get("accepted"):
                    # Process Merge
                    barcode_res = merge_problematic_barcodes(barcodes_list)
                    evidence_res = merge_evidence(evidence_list)
                    
                    # Refresh frontend views
                    try:
                        if hasattr(eel, 'on_lan_sync_completed'):
                            eel.on_lan_sync_completed({
                                "barcodes": barcode_res,
                                "evidence": evidence_res
                            })
                    except Exception as err:
                        logger.debug(f"Could not trigger frontend refresh callback: {err}")
                        
                    self._send_json(200, {
                        "status": "accepted",
                        "message": "รวมข้อมูลเรียบร้อยแล้ว",
                        "barcodes_result": barcode_res,
                        "evidence_result": evidence_res
                    })
                else:
                    self._send_json(200, {
                        "status": "rejected",
                        "message": "เครื่องปลายทางปฏิเสธการรับข้อมูล"
                    })
                    
            except Exception as e:
                logger.error(f"Error handling sync request: {e}", exc_info=True)
                self._send_json(500, {"status": "error", "message": str(e)})
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
        scan_range = [i for i in range(max(1, curr_num - 20), min(255, curr_num + 21)) if i != curr_num]
        for num in scan_range:
            t = threading.Thread(target=_check_ip, args=(num,))
            threads.append(t)
            t.start()
            
        for t in threads:
            t.join(timeout=1.0)
            
    return list(discovered.values())


@eel.expose
def respond_incoming_sync(transfer_id: str, accept: bool) -> bool:
    """ผู้รับกดปุ่ม 'ยอมรับ' หรือ 'ปฏิเสธ' บน Modal"""
    with _pending_lock:
        if transfer_id in _pending_transfers:
            _pending_transfers[transfer_id]["accepted"] = bool(accept)
            _pending_transfers[transfer_id]["event"].set()
            return True
    return False


@eel.expose
def send_lan_sync(target_ip: str, selected_barcodes: list, selected_evidence_ids: list) -> dict:
    """
    ผู้ส่งส่งข้อมูลไปยังเครื่องเป้าหมาย:
    - ดึงข้อมูล barcodes ที่ถูกเลือก
    - ดึงข้อมูล evidence พร้อมแปลงรูปเป็น Base64
    - ส่ง HTTP POST /api/sync/request
    - รอการตอบรับ
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

        # 1. รวบรวมข้อมูลบาร์โค้ด
        from main import load_problematic_barcodes
        all_barcodes = load_problematic_barcodes() or []
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
            with urlopen(req, timeout=95.0) as resp:
                res_data = json.loads(resp.read().decode('utf-8'))

                if res_data.get("status") == "accepted":
                    return {
                        "success": True,
                        "message": "เครื่องปลายทางยอมรับข้อมูลและรวมเรียบร้อยแล้ว",
                        "details": res_data
                    }
                elif res_data.get("status") == "rejected":
                    return {
                        "success": False,
                        "message": "เครื่องปลายทางปฏิเสธการรับข้อมูล"
                    }
                elif res_data.get("status") == "timeout":
                    return {
                        "success": False,
                        "message": "หมดเวลารอการตอบรับจากเครื่องปลายทาง (90s)"
                    }
                else:
                    return {
                        "success": False,
                        "message": res_data.get("message", "เกิดข้อผิดพลาดในการส่ง")
                    }
        except HTTPError as e:
            if e.code == 408:
                return {"success": False, "message": "หมดเวลารอการกดยอมรับจากเครื่องปลายทาง (Timeout 90s)"}
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
