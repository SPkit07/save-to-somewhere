// ==================== LAN SYNC JAVASCRIPT LOGIC ====================
// จัดการการส่ง-รับข้อมูลรูปภาพและบาร์โค้ดที่มีปัญหาผ่าน LAN

let lanDiscoveredDevices = [];
let lanSelectedTargetIp = '';
let lanAllBarcodes = [];
let lanAllEvidenceRecords = [];
let currentIncomingTransferId = null;

// Initialize on page load
document.addEventListener('DOMContentLoaded', async () => {
    try {
        await initLanSyncTab();
    } catch (e) {
        console.warn('LAN sync init failed', e);
    }
});

async function initLanSyncTab() {
    await loadMyDeviceInfo();
    await loadLanBarcodesList();
    await loadLanEvidenceList();
    
    // Auto scan devices on first open
    scanLanDevices();
}

// ==================== MY DEVICE INFO ====================
async function loadMyDeviceInfo() {
    if (typeof eel === 'undefined' || !eel.get_my_device_info) return;
    
    try {
        const info = await eel.get_my_device_info()();
        if (info) {
            const ipEl = document.getElementById('myDeviceIp');
            if (ipEl) ipEl.textContent = info.ip || '-';
            
            const hostEl = document.getElementById('myDeviceHost');
            if (hostEl) hostEl.textContent = info.device_name || '-';
            
            const displayNameEl = document.getElementById('myDeviceDisplayName');
            if (displayNameEl) {
                displayNameEl.textContent = info.owner_name || info.device_name || '-';
            }
            
            const ownerInput = document.getElementById('myOwnerNameInput');
            if (ownerInput) {
                ownerInput.value = info.owner_name || '';
            }
        }
    } catch (e) {
        console.error('Error loading device info:', e);
    }
}

async function saveMyOwnerName() {
    const input = document.getElementById('myOwnerNameInput');
    if (!input) return;
    const name = input.value.trim();
    if (!name) {
        alert('กรุณากรอกชื่อเครื่อง / ชื่อเจ้าของเครื่อง');
        return;
    }
    
    const saveBtn = document.getElementById('btnSaveOwnerName');
    if (saveBtn) {
        saveBtn.disabled = true;
        saveBtn.textContent = '⏳ บันทึก...';
    }
    
    try {
        if (typeof eel !== 'undefined' && eel.save_my_owner_name) {
            const ok = await eel.save_my_owner_name(name)();
            if (ok) {
                const displayNameEl = document.getElementById('myDeviceDisplayName');
                if (displayNameEl) displayNameEl.textContent = name;
                
                const statusText = document.getElementById('saveOwnerStatusText');
                if (statusText) {
                    statusText.textContent = `✅ บันทึกชื่อเครื่อง "${name}" เรียบร้อยแล้ว`;
                    statusText.style.display = 'block';
                    setTimeout(() => { if (statusText) statusText.style.display = 'none'; }, 4000);
                }
                alert(`✅ บันทึกชื่อเครื่อง "${name}" เรียบร้อยแล้ว`);
            } else {
                alert('❌ ไม่สามารถบันทึกชื่อเครื่องได้ (กรุณาลองใหม่อีกครั้ง)');
            }
        } else {
            alert('❌ ไม่พบฟังก์ชันบันทึกชื่อ (โปรดรีสตาร์ตโปรแกรม)');
        }
    } catch (e) {
        const msg = (e && (e.errorText || e.message || (typeof e === 'string' ? e : JSON.stringify(e)))) || 'เกิดข้อผิดพลาด';
        alert('❌ Error: ' + msg);
    } finally {
        if (saveBtn) {
            saveBtn.disabled = false;
            saveBtn.textContent = 'บันทึก';
        }
    }
}

// ==================== DEVICE DISCOVERY ====================
async function scanLanDevices() {
    const statusText = document.getElementById('lanScanStatus');
    const container = document.getElementById('lanDeviceList');
    const scanBtn = document.getElementById('btnScanLan');
    
    if (scanBtn) {
        scanBtn.disabled = true;
        scanBtn.innerHTML = '⏳ กำลังค้นหาเครื่อง...';
    }
    if (statusText) statusText.style.display = 'inline-block';
    
    try {
        if (typeof eel !== 'undefined' && eel.scan_lan_devices) {
            lanDiscoveredDevices = await eel.scan_lan_devices()();
            renderDeviceList(lanDiscoveredDevices);
        }
    } catch (e) {
        console.error('Error scanning LAN devices:', e);
    } finally {
        if (scanBtn) {
            scanBtn.disabled = false;
            scanBtn.innerHTML = '🔄 ค้นหาเครื่องในวงแลน';
        }
        if (statusText) statusText.style.display = 'none';
    }
}

function renderDeviceList(devices) {
    const container = document.getElementById('lanDeviceList');
    if (!container) return;
    
    if (!devices || devices.length === 0) {
        container.innerHTML = `
            <div style="text-align: center; color: var(--text-muted); padding: 24px; font-size: 13px; border: 1px dashed var(--border-color); border-radius: 8px;">
                📡 ยังไม่พบเครื่องอื่นที่เปิดโปรแกรมในวง LAN เดียวกัน<br>
                <span style="font-size: 11px; opacity: 0.8;">(คุณสามารถป้อน IP เครื่องปลายทางโดยตรงได้ที่ช่องด้านล่าง)</span>
            </div>
        `;
        return;
    }
    
    let html = '';
    devices.forEach(dev => {
        const isSelected = lanSelectedTargetIp === dev.ip;
        html += `
            <div class="lan-device-card ${isSelected ? 'selected' : ''}" onclick="selectTargetDevice('${dev.ip}')" style="cursor: pointer; display: flex; align-items: center; justify-content: space-between; padding: 12px 16px; border: 1px solid ${isSelected ? 'var(--primary)' : 'var(--border-color)'}; background: ${isSelected ? 'rgba(79, 70, 229, 0.08)' : 'var(--surface)'}; border-radius: 8px; margin-bottom: 8px; transition: all 0.2s;">
                <div style="display: flex; align-items: center; gap: 12px;">
                    <input type="radio" name="targetDeviceRadio" value="${dev.ip}" ${isSelected ? 'checked' : ''} style="cursor: pointer;">
                    <div>
                        <div style="font-weight: 700; font-size: 14px; color: var(--text);">
                            👤 ${dev.owner_name}
                        </div>
                        <div style="font-size: 12px; color: var(--text-muted);">
                            💻 ${dev.device_name} &bull; 🌐 <code>${dev.ip}</code>
                        </div>
                    </div>
                </div>
                <div style="font-size: 12px; font-weight: 600; color: #10b981; display: flex; align-items: center; gap: 6px;">
                    <span style="width: 8px; height: 8px; border-radius: 50%; background: #10b981; display: inline-block;"></span>
                    พร้อมรับข้อมูล
                </div>
            </div>
        `;
    });
    
    container.innerHTML = html;
}

function selectTargetDevice(ip) {
    lanSelectedTargetIp = ip;
    const manualInput = document.getElementById('manualTargetIpInput');
    if (manualInput) manualInput.value = ip;
    renderDeviceList(lanDiscoveredDevices);
    updateSendSummary();
}

async function testManualTargetIp() {
    const input = document.getElementById('manualTargetIpInput');
    if (!input) return;
    const ip = input.value.trim();
    if (!ip) {
        alert('กรุณากรอก IP ปลายทาง');
        return;
    }
    
    const testBtn = document.getElementById('btnTestTargetIp');
    if (testBtn) {
        testBtn.disabled = true;
        testBtn.innerHTML = '⏳ ตรวจสอบ...';
    }
    
    try {
        if (typeof eel !== 'undefined' && eel.test_ping_device) {
            const res = await eel.test_ping_device(ip)();
            if (res && res.success) {
                lanSelectedTargetIp = ip;
                // Add or update in discovered list
                const existingIdx = lanDiscoveredDevices.findIndex(d => d.ip === ip);
                const devData = {
                    ip: ip,
                    device_name: (res.device && res.device.device_name) || ip,
                    owner_name: (res.device && res.device.owner_name) || (res.device && res.device.device_name) || ip
                };
                if (existingIdx >= 0) {
                    lanDiscoveredDevices[existingIdx] = devData;
                } else {
                    lanDiscoveredDevices.push(devData);
                }
                renderDeviceList(lanDiscoveredDevices);
                updateSendSummary();
                alert(`✅ เชื่อมต่อสำเร็จ!\nเครื่อง: ${devData.owner_name} (${devData.device_name})`);
            } else {
                alert(`❌ ${(res && res.message) || 'ไม่สามารถเชื่อมต่อได้'}`);
            }
        } else {
            alert('❌ ไม่พบฟังก์ชันทดสอบการเชื่อมต่อ (โปรดรีสตาร์ตโปรแกรม)');
        }
    } catch (e) {
        const msg = (e && (e.errorText || e.message || (typeof e === 'string' ? e : JSON.stringify(e)))) || 'เกิดข้อผิดพลาดในการตรวจสอบ';
        alert('❌ Error: ' + msg);
    } finally {
        if (testBtn) {
            testBtn.disabled = false;
            testBtn.innerHTML = '🔍 ตรวจสอบ';
        }
    }
}

// ==================== LOAD & SELECT DATA ====================

async function loadLanBarcodesList() {
    const container = document.getElementById('lanBarcodesTableBody');
    if (!container) return;
    
    if (typeof eel !== 'undefined' && eel.load_problematic_barcodes) {
        try {
            lanAllBarcodes = await eel.load_problematic_barcodes()();
        } catch (e) {
            lanAllBarcodes = [];
        }
    }
    
    renderLanBarcodes(lanAllBarcodes);
}

function renderLanBarcodes(barcodes) {
    const container = document.getElementById('lanBarcodesTableBody');
    const badge = document.getElementById('lanBarcodeTotalBadge');
    if (badge) badge.textContent = `${barcodes.length} รายการ`;
    if (!container) return;
    
    if (!barcodes || barcodes.length === 0) {
        container.innerHTML = `<tr><td colspan="4" style="text-align: center; color: var(--text-muted); padding: 20px;">ไม่มีข้อมูลบาร์โค้ดที่มีปัญหา</td></tr>`;
        return;
    }
    
    let html = '';
    barcodes.forEach((b, idx) => {
        html += `
            <tr style="cursor: pointer;" onclick="toggleBarcodeRow(${idx})">
                <td style="text-align: center; width: 40px;" onclick="event.stopPropagation()">
                    <input type="checkbox" class="lan-barcode-check" data-barcode="${b.barcode}" onchange="updateSendSummary()">
                </td>
                <td style="font-weight: 500;">${b.name || '-'}</td>
                <td><code style="background: var(--surface-alt); padding: 2px 6px; border-radius: 4px; font-weight: bold;">${b.barcode}</code></td>
                <td style="color: var(--danger, #ef4444); font-size: 12px;">${b.error || '-'}</td>
            </tr>
        `;
    });
    
    container.innerHTML = html;
    updateSendSummary();
}

function toggleBarcodeRow(index) {
    const checks = document.querySelectorAll('.lan-barcode-check');
    if (checks[index]) {
        checks[index].checked = !checks[index].checked;
        updateSendSummary();
    }
}

function selectAllBarcodes(checked) {
    document.querySelectorAll('.lan-barcode-check').forEach(cb => {
        cb.checked = checked;
    });
    updateSendSummary();
}

// --- Evidence List ---
async function loadLanEvidenceList() {
    const container = document.getElementById('lanEvidenceListContainer');
    if (!container) return;
    
    if (typeof eel !== 'undefined' && eel.get_all_evidence_records) {
        try {
            const res = await eel.get_all_evidence_records()();
            if (res && res.success) {
                lanAllEvidenceRecords = res.records || [];
                renderLanEvidence(lanAllEvidenceRecords);
                return;
            }
        } catch (e) {
            console.warn('Could not load all evidence records directly, trying tree fallback:', e);
        }
    }
    
    if (typeof eel !== 'undefined' && eel.get_evidence_tree) {
        try {
            const res = await eel.get_evidence_tree()();
            // Flatten records or load by date
            if (res && res.tree) {
                lanAllEvidenceRecords = [];
                // Load for all days in tree
                for (const branch of Object.keys(res.tree)) {
                    for (const month of Object.keys(res.tree[branch])) {
                        for (const day of res.tree[branch][month]) {
                            const dayRes = await eel.get_evidence_by_date(branch, day)();
                            if (dayRes && dayRes.records) {
                                lanAllEvidenceRecords.push(...dayRes.records);
                            }
                        }
                    }
                }
            }
        } catch (e) {
            lanAllEvidenceRecords = [];
        }
    }
    
    renderLanEvidence(lanAllEvidenceRecords);
}

function renderLanEvidence(records) {
    const container = document.getElementById('lanEvidenceListContainer');
    const badge = document.getElementById('lanEvidenceTotalBadge');
    if (badge) badge.textContent = `${records.length} รายการ`;
    if (!container) return;
    
    if (!records || records.length === 0) {
        container.innerHTML = `<div style="text-align: center; color: var(--text-muted); padding: 30px; grid-column: 1/-1;">ไม่มีรูปภาพหลักฐานสินค้า</div>`;
        return;
    }
    
    let html = '';
    records.forEach(r => {
        const imgCount = (r.images && r.images.length) || 0;
        const firstImgPath = imgCount > 0 ? r.images[0] : '';
        
        html += `
            <div class="lan-evidence-card" style="border: 1px solid var(--border-color); border-radius: 8px; padding: 10px; background: var(--surface); display: flex; gap: 12px; align-items: center; position: relative;">
                <input type="checkbox" class="lan-evidence-check" data-id="${r.id}" onchange="updateSendSummary()" style="width: 18px; height: 18px; cursor: pointer;">
                <div style="width: 54px; height: 54px; border-radius: 6px; overflow: hidden; background: var(--surface-alt); border: 1px solid var(--border-light); display: flex; align-items: center; justify-content: center; flex-shrink: 0;">
                    ${firstImgPath ? `<img class="lan-lazy-thumb" data-path="${firstImgPath}" src="" style="width: 100%; height: 100%; object-fit: cover;" alt="img">` : '<span style="font-size: 20px;">📦</span>'}
                </div>
                <div style="flex: 1; min-width: 0;">
                    <div style="font-weight: 700; font-size: 13px; color: var(--text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" title="${r.product_name || ''}">
                        ${r.product_name || 'ไม่ระบุชื่อสินค้า'}
                    </div>
                    <div style="font-size: 11px; color: var(--text-muted); margin-top: 2px;">
                        🏢 สาขา: <strong>${r.branch}</strong> &bull; 📅 ${r.date}
                    </div>
                    <div style="font-size: 11px; color: var(--primary); font-weight: 600; margin-top: 2px;">
                        📸 ${imgCount} รูปภาพ ${r.barcode ? `&bull; 🔖 ${r.barcode}` : ''}
                    </div>
                </div>
            </div>
        `;
    });
    
    container.innerHTML = html;
    
    // Load lazy thumbnails
    document.querySelectorAll('.lan-lazy-thumb').forEach(async (img) => {
        const p = img.getAttribute('data-path');
        if (p && typeof eel !== 'undefined' && eel.get_image_base64) {
            try {
                const b64 = await eel.get_image_base64(p)();
                if (b64) img.src = b64;
            } catch (e) {}
        }
    });
    
    updateSendSummary();
}

function selectAllEvidence(checked) {
    document.querySelectorAll('.lan-evidence-check').forEach(cb => {
        cb.checked = checked;
    });
    updateSendSummary();
}

// ==================== SUMMARY & SEND ====================

function updateSendSummary() {
    const selectedBarcodes = Array.from(document.querySelectorAll('.lan-barcode-check:checked')).map(cb => cb.getAttribute('data-barcode'));
    const selectedEvidenceIds = Array.from(document.querySelectorAll('.lan-evidence-check:checked')).map(cb => cb.getAttribute('data-id'));
    
    let targetIp = lanSelectedTargetIp;
    const manualInput = document.getElementById('manualTargetIpInput');
    if (!targetIp && manualInput && manualInput.value.trim()) {
        targetIp = manualInput.value.trim();
    }
    
    const summaryText = document.getElementById('lanSendSummaryText');
    const sendBtn = document.getElementById('btnSubmitLanSend');
    
    if (summaryText) {
        summaryText.innerHTML = `
            เลือกบาร์โค้ด: <strong>${selectedBarcodes.length}</strong> รายการ | 
            รูปหลักฐาน: <strong>${selectedEvidenceIds.length}</strong> รายการ | 
            เป้าหมาย: <strong style="color: var(--primary);">${targetIp || '(ยังไม่เลือกเครื่อง)'}</strong>
        `;
    }
    
    if (sendBtn) {
        const hasData = selectedBarcodes.length > 0 || selectedEvidenceIds.length > 0;
        const hasTarget = Boolean(targetIp);
        sendBtn.disabled = !(hasData && hasTarget);
    }
}

async function submitLanSync() {
    let targetIp = lanSelectedTargetIp;
    const manualInput = document.getElementById('manualTargetIpInput');
    if (!targetIp && manualInput && manualInput.value.trim()) {
        targetIp = manualInput.value.trim();
    }
    
    if (!targetIp) {
        alert('กรุณาเลือกเครื่องปลายทาง หรือระบุ IP ปลายทางก่อนส่งข้อมูล');
        return;
    }
    
    const selectedBarcodes = Array.from(document.querySelectorAll('.lan-barcode-check:checked')).map(cb => cb.getAttribute('data-barcode'));
    const selectedEvidenceIds = Array.from(document.querySelectorAll('.lan-evidence-check:checked')).map(cb => cb.getAttribute('data-id'));
    
    if (selectedBarcodes.length === 0 && selectedEvidenceIds.length === 0) {
        alert('กรุณาเลือกข้อมูลอย่างน้อย 1 รายการเพื่อส่ง (บาร์โค้ดที่มีปัญหา หรือ รูปภาพหลักฐาน)');
        return;
    }
    
    // Show sending progress modal
    showSendProgressModal(targetIp, selectedBarcodes.length, selectedEvidenceIds.length);
    
    try {
        if (typeof eel === 'undefined' || !eel.send_lan_sync) {
            throw new Error('ไม่พบฟังก์ชันส่งข้อมูล Eel (โปรดรีสตาร์ตโปรแกรม)');
        }
        
        const res = await eel.send_lan_sync(targetIp, selectedBarcodes, selectedEvidenceIds)();
        hideSendProgressModal();
        
        if (res && res.success) {
            alert(`🎉 ส่งข้อมูลสำเร็จ!\n${res.message}`);
        } else {
            const failMsg = (res && res.message) ? res.message : 'เครื่องปลายทางปฏิเสธหรือไม่ตอบรับ';
            alert(`❌ ส่งข้อมูลไม่สำเร็จ:\n${failMsg}`);
        }
    } catch (e) {
        hideSendProgressModal();
        console.error('Error in submitLanSync:', e);
        let errorMsg = 'ไม่สามารถติดต่อเครื่องปลายทางได้';
        if (typeof e === 'string') {
            errorMsg = e;
        } else if (e && e.errorText) {
            errorMsg = e.errorText;
        } else if (e && e.message) {
            errorMsg = e.message;
        } else if (e && e.error) {
            errorMsg = typeof e.error === 'string' ? e.error : JSON.stringify(e.error);
        } else if (e) {
            errorMsg = JSON.stringify(e);
        }
        alert('❌ เกิดข้อผิดพลาดในการเชื่อมต่อ:\n' + errorMsg);
    }
}

// Sending progress modal
function showSendProgressModal(targetIp, barcodeCount, evidenceCount) {
    let modal = document.getElementById('lanSendProgressModal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'lanSendProgressModal';
        modal.className = 'modal';
        modal.style.display = 'flex';
        modal.style.zIndex = '9999';
        modal.innerHTML = `
            <div class="modal-content" style="max-width: 440px; text-align: center; padding: 28px;">
                <div style="font-size: 40px; margin-bottom: 12px; animation: pulse 1.5s infinite;">📡</div>
                <h3 style="font-size: 16px; font-weight: 700; margin-bottom: 8px;">กำลังส่งข้อมูลผ่าน LAN...</h3>
                <p style="font-size: 13px; color: var(--text-muted); margin-bottom: 16px;" id="lanSendProgressDetails"></p>
                <div style="background: var(--surface-alt); padding: 12px; border-radius: 8px; font-size: 12px; color: var(--text); margin-bottom: 16px;">
                    ⏳ กำลังรอเครื่องปลายทางกดยอมรับบนหน้าจอ...<br>
                    <span style="color: var(--text-muted); font-size: 11px;">(มีเวลารอสูงสุด 90 วินาที)</span>
                </div>
            </div>
        `;
        document.body.appendChild(modal);
    }
    
    const details = document.getElementById('lanSendProgressDetails');
    if (details) {
        details.textContent = `ส่งไปยัง: ${targetIp} (บาร์โค้ด ${barcodeCount} รายการ, หลักฐาน ${evidenceCount} รายการ)`;
    }
    modal.style.display = 'flex';
}

function hideSendProgressModal() {
    const modal = document.getElementById('lanSendProgressModal');
    if (modal) modal.style.display = 'none';
}

// ==================== RECEIVER POPUP MODAL ====================
// Function exposed to Python via Eel

eel.expose(show_incoming_sync_modal);
function show_incoming_sync_modal(summary) {
    currentIncomingTransferId = summary.transfer_id;
    
    let modal = document.getElementById('incomingSyncModal');
    if (!modal) {
        console.error('incomingSyncModal not found in DOM');
        return;
    }
    
    // Fill modal contents
    document.getElementById('incomingSenderOwner').textContent = summary.sender_owner || 'ไม่ระบุชื่อ';
    document.getElementById('incomingSenderDevice').textContent = `${summary.sender_device} (${summary.sender_ip})`;
    document.getElementById('incomingBarcodeCount').textContent = `${summary.barcodes_count} รายการ`;
    document.getElementById('incomingEvidenceCount').textContent = `${summary.evidence_count} รายการ (${summary.images_count} รูปภาพ)`;
    
    // Preview list
    const previewContainer = document.getElementById('incomingPreviewList');
    if (previewContainer) {
        let previewHtml = '';
        if (summary.barcodes_preview && summary.barcodes_preview.length > 0) {
            previewHtml += '<div style="font-weight: 700; font-size: 12px; margin-bottom: 4px; color: var(--text);">🚨 บาร์โค้ดตัวอย่าง:</div><ul style="margin: 0 0 10px 16px; padding: 0; font-size: 12px;">';
            summary.barcodes_preview.forEach(b => {
                previewHtml += `<li><strong>${b.name || '-'}</strong> (<code>${b.barcode}</code>): ${b.error || '-'}</li>`;
            });
            if (summary.barcodes_count > 5) previewHtml += `<li>...และอีก ${summary.barcodes_count - 5} รายการ</li>`;
            previewHtml += '</ul>';
        }
        
        if (summary.evidence_preview && summary.evidence_preview.length > 0) {
            previewHtml += '<div style="font-weight: 700; font-size: 12px; margin-bottom: 4px; color: var(--text);">📸 รายการหลักฐานตัวอย่าง:</div><ul style="margin: 0 0 0 16px; padding: 0; font-size: 12px;">';
            summary.evidence_preview.forEach(e => {
                previewHtml += `<li><strong>${e.product_name}</strong> (${e.branch} - ${e.date}): ${e.images_count} รูปภาพ</li>`;
            });
            if (summary.evidence_count > 5) previewHtml += `<li>...และอีก ${summary.evidence_count - 5} รายการ</li>`;
            previewHtml += '</ul>';
        }
        
        previewContainer.innerHTML = previewHtml;
    }
    
    modal.style.display = 'flex';
}

async function respondIncomingSync(accept) {
    if (!currentIncomingTransferId) return;
    
    const modal = document.getElementById('incomingSyncModal');
    if (modal) modal.style.display = 'none';
    
    if (typeof eel !== 'undefined' && eel.respond_incoming_sync) {
        try {
            await eel.respond_incoming_sync(currentIncomingTransferId, accept)();
            if (accept) {
                showStatus('✅ รวมข้อมูลเข้าสู่เครื่องเรียบร้อยแล้ว', 'success');
            }
        } catch (e) {
            console.error('Error responding to incoming sync:', e);
        }
    }
    currentIncomingTransferId = null;
}

// Callback when data was merged in background
eel.expose(on_lan_sync_completed);
function on_lan_sync_completed(results) {
    console.log('✅ LAN sync completed and merged:', results);
    // Reload Problematic barcodes if on Tab 3
    if (typeof loadProblematicBarcodesFromBackend === 'function') {
        loadProblematicBarcodesFromBackend();
    }
    // Reload Evidence tree if on Tab 5
    if (typeof loadEvidenceTree === 'function') {
        loadEvidenceTree();
    }
    // Reload LAN sync lists
    loadLanBarcodesList();
    loadLanEvidenceList();
}

// Shortcut triggers
function openLanSyncForBarcodes() {
    switchTab('lan-sync');
    switchLanSubTab('barcodes');
    selectAllBarcodes(true);
}

function openLanSyncForEvidence() {
    switchTab('lan-sync');
    switchLanSubTab('evidence');
    selectAllEvidence(true);
}

function switchLanSubTab(tabName) {
    document.querySelectorAll('.lan-sub-tab-btn').forEach(btn => btn.classList.remove('active'));
    document.querySelectorAll('.lan-sub-tab-content').forEach(c => c.style.display = 'none');
    
    const targetBtn = document.getElementById(`lanSubTabBtn_${tabName}`);
    if (targetBtn) targetBtn.classList.add('active');
    
    const targetContent = document.getElementById(`lanSubTabContent_${tabName}`);
    if (targetContent) targetContent.style.display = 'block';
}
