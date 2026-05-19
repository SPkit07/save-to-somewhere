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
        
        // แสดง Preview Modal
        showPreviewModal(preview);
        
    } catch (error) {
        console.error('Preview error:', error);
        showStatus(`❌ Error: ${error.message}`, 'error');
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

// ==================== CONFIRM PROCESS ====================
async function confirmProcess() {
    if (!currentPreviewData) {
        showStatus('❌ ไม่มีข้อมูลไฟล์', 'error');
        return;
    }
    
    // เก็บข้อมูลไว้ก่อน เพราะ closePreviewModal จะ clear currentPreviewData
    const previewData = { ...currentPreviewData };
    
    closePreviewModal();
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

// ==================== LOCALSTORAGE MANAGEMENT ====================
function savePathsToLocalStorage() {
    const paths = getCurrentPathsConfig();
    localStorage.setItem('pathsConfig', JSON.stringify(paths));
    showStatus('✅ บันทึกการตั้งค่า Path สำเร็จแล้ว!', 'success');
}

function loadPathsFromLocalStorage() {
    const saved = localStorage.getItem('pathsConfig');
    if (!saved) return;

    try {
        const paths = JSON.parse(saved);
        Object.keys(paths).forEach(key => {
            const input = document.querySelector(`input[data-key="${key}"]`);
            if (input) {
                input.value = paths[key];
            }
        });
    } catch (error) {
        console.error('Error loading paths from localStorage:', error);
    }
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
    const branchName = BRANCH_NAMES[branchCode] || 'ไม่ทราบ';
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
