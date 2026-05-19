// ==================== CONFIG ====================
const DESKTOP_MODE = true;  // ใช้ Eel API แทน HTTP
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

    // File Input
    browseBtn.addEventListener('click', handleBrowseClick);
    fileInput.addEventListener('change', handleFileSelect);

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

function handleFileDrop(e) {
    e.preventDefault();
    e.stopPropagation();
    dropzone.classList.remove('dragover');

    // ใน Desktop Mode ให้เปิด File Dialog แทน (เพราะ Browser File API มี limitation)
    if (DESKTOP_MODE) {
        handleBrowseClick();
    } else {
        // Fallback: ใช้ Browser File API
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            fileInput.files = files;
            handleFileSelect();
        }
    }
}

async function handleBrowseClick() {
    const filePath = await eel.select_file_dialog()();
    if (filePath) {
        uploadFileFromPath(filePath);
    }
}

function handleFileSelect() {
    const file = fileInput.files[0];
    if (!file) return;

    // Check file type
    if (!['application/vnd.ms-excel', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'].includes(file.type)) {
        showStatus('❌ กรุณาเลือกไฟล์ Excel (.xlsx หรือ .xls)', 'error');
        return;
    }

    // Send file to backend
    uploadFile(file);
}

// ==================== UPLOAD FROM DESKTOP PATH ====================
async function uploadFileFromPath(filePath) {
    showStatus('⏳ กำลังประมวลผลไฟล์...', 'loading');

    try {
        // Get current paths configuration
        const paths = getCurrentPathsConfig();
        
        // เรียก Eel function เพื่อประมวลผลไฟล์จาก absolute path
        const result = await eel.process_file_from_desktop(filePath, paths)();
        
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
        showStatus(`❌ เกิดข้อผิดพลาด: ${error.message || 'ไม่ทราบสาเหตุ'}`, 'error');
    }
}

// ==================== FILE UPLOAD ====================
async function uploadFile(file) {
    showStatus('⏳ กำลังประมวลผลไฟล์...', 'loading');

    try {
        // Get current paths configuration
        const paths = getCurrentPathsConfig();
        
        // เรียก Eel function เพื่อประมวลผลไฟล์
        const result = await eel.process_file_from_desktop(file.name, paths)();
        
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
        showStatus(`❌ เกิดข้อผิดพลาด: ${error.message || 'ไม่ทราบสาเหตุ'}`, 'error');
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
