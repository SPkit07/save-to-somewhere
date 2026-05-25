// ==================== CONFIG ====================
const DESKTOP_MODE = true;  // ใช้ Eel API แทน HTTP
let currentPreviewData = null;  // เก็บข้อมูล preview ชั่วคราว
const BRANCH_NAMES = {
    '00': 'WH',
    '11': 'K1',
    '21': 'K2',
    '31': 'K3',
    '41': 'K4',
    '51': 'K5'
};

const BRANCH_CONFIG = {
    'K1': { code: '11', hasTwo: true, secondary: 'WH' },
    'K2': { code: '21', hasTwo: true, secondary: 'WH' },
    'K3': { code: '31', hasTwo: true, secondary: 'WH' },
    'K4': { code: '41', hasTwo: true, secondary: 'WH' },
    'K5': { code: '51', hasTwo: true, secondary: 'WH' },
    'SP': { code: '00', hasTwo: false }
};

// ==================== DOM ELEMENTS ====================
const dropzone = document.getElementById('dropzone');
const fileInput = document.getElementById('fileInput');
const browseBtn = document.getElementById('browseBtn');
const branchNameDisplay = document.getElementById('branchName');
const branchCodeDisplay = document.getElementById('branchCode');
const branchPathsContainer = document.getElementById('branchPaths');
const saveBtn = document.getElementById('saveBtn');
const statusMessage = document.getElementById('statusMessage');
const statusIcon = document.getElementById('statusIcon');
const statusText = document.getElementById('statusText');

// ==================== INITIALIZE ====================
document.addEventListener('DOMContentLoaded', () => {
    initializeBranchPaths();
    loadPathsFromLocalStorage();
    setupEventListeners();
});

// ==================== EVENT LISTENERS ====================
function setupEventListeners() {
    // Drag & Drop
    dropzone.addEventListener('dragover', handleDragOver);
    dropzone.addEventListener('dragleave', handleDragLeave);
    dropzone.addEventListener('drop', handleFileDrop);

    // Browse Button
    browseBtn.addEventListener('click', handleBrowseClick);

    // Save Button
    saveBtn.addEventListener('click', savePathsToLocalStorage);
}

function handleDragOver(e) {
    e.preventDefault();
    e.stopPropagation();
    dropzone.classList.add('dragover');
}

function handleDragLeave(e) {
    e.preventDefault();
    e.stopPropagation();
    dropzone.classList.remove('dragover');
}

async function handleFileDrop(e) {
    e.preventDefault();
    e.stopPropagation();
    dropzone.classList.remove('dragover');

    const files = e.dataTransfer.files;
    if (files.length === 0) return;
    
    const file = files[0];
    showStatus('⏳ กำลังอัปโหลดและเตรียมไฟล์...', 'loading');
    
    // ใน Desktop Mode ให้อ่านไฟล์เป็น base64 แล้วส่งให้ Python
    if (DESKTOP_MODE) {
        const reader = new FileReader();
        reader.onload = async function(event) {
            const result = event.target.result;
            // แยกส่วนที่เป็น base64 data ออกจาก data URL prefix
            const base64Data = result.includes(',') ? result.split(',')[1] : result;
            
            try {
                // บันทึกไฟล์ลงในโฟลเดอร์ temp ฝั่ง backend
                const tempPath = await eel.save_temp_file(file.name, base64Data)();
                if (tempPath) {
                    showStatus('⏳ กำลังตรวจสอบไฟล์...', 'loading');
                    await previewFile(tempPath);
                } else {
                    showStatus('❌ ไม่สามารถสร้างไฟล์ชั่วคราวได้', 'error');
                }
            } catch (err) {
                console.error("Eel error:", err);
                showStatus(`❌ Error: ${err.message}`, 'error');
            }
        };
        reader.onerror = function() {
            showStatus('❌ เกิดข้อผิดพลาดในการอ่านไฟล์', 'error');
        };
        // อ่านเป็น Data URL (Base64)
        reader.readAsDataURL(file);
    } else {
        // Fallback สำหรับ Web Mode (ถ้ามี)
        fileInput.files = files;
        if (typeof handleFileSelect === 'function') {
            handleFileSelect();
        }
    }
}

async function handleBrowseClick() {
    const filePath = await eel.select_file_dialog()();
    if (filePath) {
        showStatus('⏳ กำลังตรวจสอบไฟล์...', 'loading');
        await previewFile(filePath);
    }
}

// ==================== PREVIEW FILE ====================
async function previewFile(filePath) {
    try {
        const preview = await eel.preview_excel_file(filePath)();
        
        if (!preview.success) {
            showStatus(`❌ ${preview.message}`, 'error');
            return;
        }
        
        // เก็บข้อมูล preview ไว้สำหรับการประมวลผลจริง ๆ
        currentPreviewData = preview;
        
        // ตรวจสอบ Warning: ข้อมูลไม่ตรงกัน หรือมีค่าเป็น 0
        if (preview.jk_has_zero || (preview.jk_mismatch && preview.jk_mismatch.length > 0)) {
            showWarningModal(preview);
        } else if (preview.receive_mismatch && preview.receive_mismatch.length > 0) {
            showReceiveWarningModal(preview);
        } else {
            // แสดง Preview Modal ทันที
            showPreviewModal(preview);
        }
        
    } catch (error) {
        console.error('Preview error:', error);
        showStatus(`❌ Error: ${error.message}`, 'error');
    }
}

// ==================== SHOW WARNING MODAL ====================
function showWarningModal(preview) {
    const modal = document.getElementById('warningModal');
    if (!modal) return;
    
    const tbody = document.getElementById('warningTableBody');
    const msg = document.getElementById('warningModalMessage');
    
    tbody.innerHTML = '';
    
    if (preview.jk_has_zero) {
        msg.textContent = "ตรวจพบค่า '0' ในคอลัมน์ 1=SP,2=WH หรือข้อมูล J และ K ไม่ตรงกัน กรุณาตรวจสอบ:";
    } else {
        msg.textContent = "พบข้อมูลในคอลัมน์ เบิก และ รับ (1=SP,2=WH) ไม่ตรงกัน กรุณาตรวจสอบ:";
    }
    
    if (preview.jk_mismatch && preview.jk_mismatch.length > 0) {
        preview.jk_mismatch.forEach(item => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>${item.code}</td>
                <td>${item.name}</td>
                <td class="mismatch">${item.col_j}</td>
                <td class="mismatch">${item.col_k}</td>
            `;
            tbody.appendChild(tr);
        });
    } else if (preview.jk_has_zero) {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td colspan="4" style="text-align: center; color: #e74c3c; font-weight: bold;">
                พบค่า '0' ในคอลัมน์ประเภทการจัดส่ง
            </td>
        `;
        tbody.appendChild(tr);
    }
    
    modal.style.display = 'flex';
    statusMessage.style.display = 'none';
}

function closeWarningModal() {
    const modal = document.getElementById('warningModal');
    if (modal) {
        modal.style.display = 'none';
    }
    currentPreviewData = null; // ยกเลิกการทำรายการ
}

function continueToPreview() {
    const modal = document.getElementById('warningModal');
    if (modal) {
        modal.style.display = 'none';
    }
    if (currentPreviewData) {
        if (currentPreviewData.receive_mismatch && currentPreviewData.receive_mismatch.length > 0) {
            showReceiveWarningModal(currentPreviewData);
        } else {
            showPreviewModal(currentPreviewData);
        }
    }
}

// ==================== SHOW RECEIVE WARNING MODAL ====================
function showReceiveWarningModal(preview) {
    const modal = document.getElementById('receiveWarningModal');
    if (!modal) return;
    
    const tbody = document.getElementById('receiveWarningTableBody');
    tbody.innerHTML = '';
    
    if (preview.receive_mismatch && preview.receive_mismatch.length > 0) {
        preview.receive_mismatch.forEach(item => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>${item.row}</td>
                <td>${item.sku_name}</td>
                <td class="mismatch">${item.receive_piece}</td>
                <td class="mismatch">${item.re_sku_code}</td>
            `;
            tbody.appendChild(tr);
        });
    }
    
    modal.style.display = 'flex';
    statusMessage.style.display = 'none';
}

function closeReceiveWarningModal() {
    const modal = document.getElementById('receiveWarningModal');
    if (modal) {
        modal.style.display = 'none';
    }
    currentPreviewData = null; // ยกเลิกการทำรายการ
}

function continueFromReceiveToPreview() {
    const modal = document.getElementById('receiveWarningModal');
    if (modal) {
        modal.style.display = 'none';
    }
    if (currentPreviewData) {
        showPreviewModal(currentPreviewData);
    }
}

// ==================== SHOW PREVIEW MODAL ====================
function showPreviewModal(preview) {
    const modal = document.getElementById('previewModal');
    if (!modal) {
        console.error('Preview modal not found');
        return;
    }
    
    // อัปเดตข้อมูลใน modal
    document.getElementById('previewFileName').textContent = preview.file_name;
    document.getElementById('previewTotalRows').textContent = preview.total_rows;
    document.getElementById('previewBranch').textContent = preview.branch_name || 'ไม่พบ';
    document.getElementById('previewBranchCode').textContent = preview.detected_branch || '-';
    document.getElementById('previewSPCount').textContent = preview.sp_count || 0;
    document.getElementById('previewWHCount').textContent = preview.wh_count || 0;
    
    // อัปเดต branch display ด้วย
    if (preview.detected_branch) {
        updateBranchDisplay(preview.detected_branch);
    }
    
    // แสดง modal
    modal.style.display = 'flex';
    statusMessage.style.display = 'none';  // ซ่อน status message
}

function closePreviewModal() {
    const modal = document.getElementById('previewModal');
    if (modal) {
        modal.style.display = 'none';
    }
    currentPreviewData = null;
}

// ==================== VALIDATE PATHS & DIRECTORIES ====================
async function validatePathsAndDirectories() {
    const paths = getCurrentPathsConfig();
    const errors = [];

    // ตรวจสอบว่ามี path ไหม
    if (!paths || Object.keys(paths).length === 0) {
        return {
            valid: false,
            errors: ['❌ กรุณาระบุที่อยู่ปลายทาง (Path) ก่อนประมวลผลไฟล์']
        };
    }

    // ตรวจสอบแต่ละ path ว่า directory มีอยู่ไหม
    for (const [key, path] of Object.entries(paths)) {
        try {
            const exists = await eel.check_directory_exists(path)();
            if (!exists) {
                const branchLabel = key === 'SP' ? 'SP' : `K${key[0]}-${key[1]}`;
                errors.push(`❌ ไม่พบโฟลเดอร์: ${path} (${branchLabel})`);
            }
        } catch (err) {
            console.error(`Error checking directory ${path}:`, err);
            errors.push(`❌ ไม่สามารถตรวจสอบ: ${path}`);
        }
    }

    return {
        valid: errors.length === 0,
        errors: errors
    };
}

// ==================== CONFIRM PROCESS ====================
async function confirmProcess() {
    if (!currentPreviewData) {
        showStatus('❌ ไม่มีข้อมูลไฟล์', 'error');
        return;
    }

    // เก็บข้อมูลไว้ก่อน เพราะ closePreviewModal จะ clear currentPreviewData
    const previewData = { ...currentPreviewData };

    // ตรวจสอบ paths และ directories ก่อน
    closePreviewModal();
    showStatus('⏳ กำลังตรวจสอบที่อยู่ปลายทาง...', 'loading');

    const validation = await validatePathsAndDirectories();
    if (!validation.valid) {
        const errorMsg = validation.errors.join('\n');
        showStatus(errorMsg, 'error');
        return;
    }

    showStatus('⏳ กำลังประมวลผลไฟล์...', 'loading');

    try {
        const paths = getCurrentPathsConfig();
        const result = await eel.process_file_from_desktop(previewData.file_path, paths)();

        if (result.success) {
            showStatus(`✅ ${result.message}`, 'success');
            if (result.detected_branch) {
                updateBranchDisplay(result.detected_branch);
            }
        } else {
            showStatus(`❌ ${result.message}`, 'error');
        }
    } catch (error) {
        console.error('Processing error:', error);
        showStatus(`❌ เกิดข้อผิดพลาด: ${error.message}`, 'error');
    }
}

// ==================== BRANCH PATHS INITIALIZATION ====================
function initializeBranchPaths() {
    const branchOrder = ['K1', 'K2', 'K3', 'K4', 'K5', 'SP'];
    let html = '';

    branchOrder.forEach(branch => {
        const config = BRANCH_CONFIG[branch];
        const code = config.code;

        html += `
            <div class="branch-group">
                <h3>${branch}</h3>
        `;

        if (config.hasTwo) {
            // สองช่อง: สาขาหลัก (11, 21, etc.) และ WH (00)
            html += `
                <div class="path-input-group">
                    <label class="path-label">📁 ${branch}-SP (รหัส ${code})</label>
                    <input type="text" class="path-input" data-key="${code}" placeholder="เช่น: C:\\Users\\USER\\Desktop\\${branch}">
                </div>
                <div class="path-input-group">
                    <label class="path-label">📦 ${branch}-WH (รหัส 00)</label>
                    <input type="text" class="path-input" data-key="${code}_00" placeholder="เช่น: C:\\Users\\USER\\Desktop\\${code}00">
                </div>
            `;
        } else {
            // หนึ่งช่อง: SP เท่านั้น
            html += `
                <div class="path-input-group">
                    <label class="path-label">📁 SP (รหัส ${code})</label>
                    <input type="text" class="path-input" data-key="SP" placeholder="เช่น: C:\\Users\\USER\\Desktop\\SP00">
                </div>
            `;
        }

        html += '</div>';
    });

    branchPathsContainer.innerHTML = html;
}

// ==================== LOCALSTORAGE / BACKEND MANAGEMENT ====================
async function savePathsToLocalStorage() {
    const paths = getCurrentPathsConfig();

    // Validation: ตรวจสอบว่าไม่มี PATH ว่างเปล่า
    const emptyPaths = [];
    document.querySelectorAll('.path-input').forEach(input => {
        const key = input.getAttribute('data-key');
        const label = input.previousElementSibling.textContent;
        if (!input.value.trim()) {
            emptyPaths.push(label);
        }
    });

    if (emptyPaths.length > 0) {
        showStatus(`❌ กรุณาใส่ PATH สำหรับ: ${emptyPaths.join(', ')}`, 'error');
        return;
    }

    if (DESKTOP_MODE) {
        try {
            const success = await eel.save_paths_config(paths)();
            if (success) {
                showStatus('✅ บันทึกการตั้งค่า Path สำเร็จแล้ว!', 'success');
            } else {
                showStatus('❌ ไม่สามารถบันทึกการตั้งค่า Path ได้', 'error');
            }
        } catch (error) {
            console.error('Error saving config to backend:', error);
            showStatus('❌ ไม่สามารถเชื่อมต่อกับระบบหลักได้', 'error');
        }
    } else {
        localStorage.setItem('pathsConfig', JSON.stringify(paths));
        showStatus('✅ บันทึกการตั้งค่า Path สำเร็จแล้ว!', 'success');
    }
}

async function loadPathsFromLocalStorage() {
    let paths = {};
    
    if (DESKTOP_MODE) {
        try {
            paths = await eel.load_paths_config()();
        } catch (error) {
            console.error('Error loading config from backend:', error);
        }
    } else {
        const saved = localStorage.getItem('pathsConfig');
        if (saved) {
            try {
                paths = JSON.parse(saved);
            } catch (error) {
                console.error('Error parsing localStorage:', error);
            }
        }
    }

    if (!paths || Object.keys(paths).length === 0) return;

    Object.keys(paths).forEach(key => {
        const input = document.querySelector(`input[data-key="${key}"]`);
        if (input) {
            input.value = paths[key];
        }
    });
}

function getCurrentPathsConfig() {
    const config = {};
    document.querySelectorAll('.path-input').forEach(input => {
        const key = input.getAttribute('data-key');
        const value = input.value.trim();
        if (value) {
            config[key] = value;
        }
    });
    return config;
}

// ==================== BRANCH DISPLAY ====================
function updateBranchDisplay(branchCode) {
    const branchName = BRANCH_NAMES[branchCode] || 'SUPER';
    branchNameDisplay.textContent = branchName;
    branchCodeDisplay.textContent = `รหัสสาขา: ${branchCode}`;
}

// ==================== STATUS MESSAGE ====================
function showStatus(message, type = 'loading') {
    statusMessage.className = `status-message ${type}`;
    statusText.textContent = message;

    const icons = {
        'loading': '⏳',
        'success': '✅',
        'error': '❌'
    };
    statusIcon.textContent = icons[type] || '⏳';

    statusMessage.style.display = 'flex';

    // Auto hide success/error after 5 seconds
    if (type !== 'loading') {
        setTimeout(() => {
            statusMessage.style.display = 'none';
        }, 5000);
    }
}
