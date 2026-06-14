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
document.addEventListener('DOMContentLoaded', async () => {
    initializeBranchPaths();
    await loadPathsFromLocalStorage();
    setupEventListeners();
    setupWindowStatePersistence();
    
    // Page 2 (Bill Processor) Initializations
    await loadBillFormFromBackend();
    setupBillFormEventListeners();
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

function setupWindowStatePersistence() {
    let saveTimer = null;

    const saveCurrentWindowState = () => {
        if (!DESKTOP_MODE || typeof eel === 'undefined' || !eel.save_window_state) return;

        const state = {
            width: window.outerWidth || window.innerWidth,
            height: window.outerHeight || window.innerHeight,
            x: typeof window.screenX === 'number' ? window.screenX : 50,
            y: typeof window.screenY === 'number' ? window.screenY : 50
        };

        eel.save_window_state(state)();
    };

    const scheduleSave = () => {
        clearTimeout(saveTimer);
        saveTimer = setTimeout(saveCurrentWindowState, 250);
    };

    window.addEventListener('resize', scheduleSave);
    window.addEventListener('move', scheduleSave);
    window.addEventListener('beforeunload', saveCurrentWindowState);

    setTimeout(saveCurrentWindowState, 1000);
    setInterval(saveCurrentWindowState, 3000);
}

function setupBillFormEventListeners() {
    // Inputs changes for saving & updating autocomplete suggestions
    const kmartSelect = document.getElementById('kmartSelect');
    const partAInput = document.getElementById('partAInput');
    const partBInput = document.getElementById('partBInput');

    [kmartSelect, partAInput, partBInput].forEach(elem => {
        elem.addEventListener('change', () => {
            saveBillFormToLocalStorage();
            fetchBillSuggestions();
        });
    });

    // Bill autocomplete (Google-style)
    setupBillAutocomplete();

    // Browse Buttons for search paths
    document.getElementById('browsePartABtn').addEventListener('click', handleBrowsePartAClick);
    document.getElementById('browsePartBBtn').addEventListener('click', handleBrowsePartBClick);

    // Browse Buttons for per-branch save paths (dynamic binding via data attribute)
    document.querySelectorAll('.sp-browse-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const targetId = btn.getAttribute('data-save-target');
            if (targetId) handleBrowseSavePathClick(targetId);
        });
    });

    // Save path input change -> persist to localStorage
    SAVE_PATH_IDS.forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.addEventListener('change', saveBillFormToLocalStorage);
        }
    });

    // Save Settings Button for Page 2
    const saveBillPathsBtn = document.getElementById('saveBillPathsBtn');
    if (saveBillPathsBtn) {
        saveBillPathsBtn.addEventListener('click', saveBillPathsToBackend);
    }

    // Run Button
    document.getElementById('runBillBtn').addEventListener('click', runBillProcessor);
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
    
    // อัปเดตสรุปข้อมูลไฟล์ล่าสุดเพื่อแสดงค้างบนหน้าจอ
    const fileSummaryDisplay = document.getElementById('fileSummaryDisplay');
    if (fileSummaryDisplay) {
        document.getElementById('summaryFileName').textContent = preview.file_name;
        document.getElementById('summaryTotalRows').textContent = preview.total_rows;
        document.getElementById('summarySPCount').textContent = preview.sp_count || 0;
        document.getElementById('summaryWHCount').textContent = preview.wh_count || 0;
        fileSummaryDisplay.style.display = 'block';
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
    // Read existing backend config
    let existingPaths = {};
    if (DESKTOP_MODE) {
        try {
            existingPaths = await eel.load_paths_config()();
        } catch (error) {
            console.error('Error loading existing config:', error);
        }
    } else {
        const saved = localStorage.getItem('pathsConfig');
        if (saved) {
            try {
                existingPaths = JSON.parse(saved);
            } catch (e) {}
        }
    }

    const page1Paths = getCurrentPathsConfig();
    const mergedPaths = { ...existingPaths, ...page1Paths };

    // Validation: ตรวจสอบว่าไม่มี PATH ว่างเปล่าสำหรับ Page 1
    const emptyPaths = [];
    document.querySelectorAll('.path-input').forEach(input => {
        const key = input.getAttribute('data-key');
        if (!key) return; // Only validate Page 1 paths
        const label = input.previousElementSibling ? input.previousElementSibling.textContent : key;
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
            const success = await eel.save_paths_config(mergedPaths)();
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
        localStorage.setItem('pathsConfig', JSON.stringify(mergedPaths));
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


// ==================== PAGE 2 (BILL PROCESSOR) LOGIC ====================

// --- Autocomplete state ---
let allBillSuggestions = [];  // Full list fetched from backend
let acHighlightIndex = -1;   // Currently highlighted item in dropdown
let isFetchingSuggestions = false;  // Loading state

function switchTab(tabName) {
    // Hide all tabs
    document.querySelectorAll('.tab-content').forEach(tab => {
        tab.classList.remove('active-tab');
    });
    document.querySelectorAll('.tab-button').forEach(btn => {
        btn.classList.remove('active');
    });
    
    // Show selected tab
    const selectedTab = document.getElementById(`tab-${tabName}`);
    if (selectedTab) {
        selectedTab.classList.add('active-tab');
    }
    
    // Set active button
    let activeBtn;
    if (tabName === 'processor') {
        activeBtn = document.getElementById('tabBtnProcessor');
    } else {
        activeBtn = document.getElementById('tabBtnBillProcessor');
    }
    if (activeBtn) {
        activeBtn.classList.add('active');
    }
}

// ==================== GOOGLE-STYLE AUTOCOMPLETE ====================

async function fetchBillSuggestions() {
    const kmart = document.getElementById('kmartSelect').value;
    const partA = document.getElementById('partAInput').value.trim();
    const partB = document.getElementById('partBInput').value.trim();
    
    if (!kmart || (!partA && !partB)) {
        allBillSuggestions = [];
        return;
    }
    
    isFetchingSuggestions = true;
    
    // Render immediately to show loading spinner
    renderBillDropdown();
    
    try {
        allBillSuggestions = await eel.get_bill_suggestions(kmart, partA, partB)();
    } catch (err) {
        console.error("Error fetching bill suggestions:", err);
        allBillSuggestions = [];
    } finally {
        isFetchingSuggestions = false;
        // Render again with fetched suggestions
        renderBillDropdown();
    }
}

function renderBillDropdown() {
    const dropdown = document.getElementById('billDropdown');
    const query = document.getElementById('billInput').value.trim().toLowerCase();
    
    if (isFetchingSuggestions) {
        dropdown.innerHTML = '<div class="autocomplete-empty">⏳ กำลังโหลดรายการบิล...</div>';
        dropdown.classList.add('show');
        return;
    }
    
    if (!query) {
        // Show all suggestions when focused but empty (like Google shows popular)
        if (allBillSuggestions.length > 0) {
            let html = '';
            allBillSuggestions.forEach((sug, i) => {
                html += `<div class="autocomplete-item${i === acHighlightIndex ? ' highlighted' : ''}" data-index="${i}" data-value="${sug}">
                    <span class="ac-icon">📄</span>
                    <span class="ac-text">${sug}</span>
                </div>`;
            });
            dropdown.innerHTML = html;
            dropdown.classList.add('show');
        } else {
            dropdown.innerHTML = '<div class="autocomplete-empty">ยังไม่มีข้อมูลบิล — ตั้งค่า part_a / part_b ก่อน</div>';
            dropdown.classList.add('show');
        }
        return;
    }
    
    // Filter suggestions that contain the query
    const filtered = allBillSuggestions.filter(s => s.toLowerCase().includes(query));
    
    if (filtered.length === 0) {
        dropdown.innerHTML = `<div class="autocomplete-empty">ไม่พบ "${query}" — กด Enter เพื่อใช้ค่านี้</div>`;
        dropdown.classList.add('show');
        acHighlightIndex = -1;
        return;
    }
    
    // Clamp highlight index
    if (acHighlightIndex >= filtered.length) acHighlightIndex = filtered.length - 1;
    
    let html = '';
    filtered.forEach((sug, i) => {
        // Highlight the matching portion
        const matchStart = sug.toLowerCase().indexOf(query);
        let displayText;
        if (matchStart >= 0) {
            const before = sug.substring(0, matchStart);
            const match = sug.substring(matchStart, matchStart + query.length);
            const after = sug.substring(matchStart + query.length);
            displayText = `${before}<mark>${match}</mark>${after}`;
        } else {
            displayText = sug;
        }
        
        html += `<div class="autocomplete-item${i === acHighlightIndex ? ' highlighted' : ''}" data-index="${i}" data-value="${sug}">
            <span class="ac-icon">🔍</span>
            <span class="ac-text">${displayText}</span>
        </div>`;
    });
    
    dropdown.innerHTML = html;
    dropdown.classList.add('show');
}

function closeBillDropdown() {
    const dropdown = document.getElementById('billDropdown');
    dropdown.classList.remove('show');
    acHighlightIndex = -1;
}

function setupBillAutocomplete() {
    const input = document.getElementById('billInput');
    const dropdown = document.getElementById('billDropdown');
    
    // Debounced input handler
    let debounceTimer;
    input.addEventListener('input', () => {
        acHighlightIndex = -1;
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => {
            renderBillDropdown();
        }, 80);
    });
    
    // Show dropdown on focus and proactively fetch suggestions
    input.addEventListener('focus', async () => {
        renderBillDropdown();
        await fetchBillSuggestions();
    });
    
    // Keyboard navigation
    input.addEventListener('keydown', (e) => {
        const items = dropdown.querySelectorAll('.autocomplete-item');
        if (!dropdown.classList.contains('show') || items.length === 0) {
            if (e.key === 'Enter') {
                e.preventDefault();
                saveBillFormToLocalStorage();
            }
            return;
        }
        
        if (e.key === 'ArrowDown') {
            e.preventDefault();
            acHighlightIndex = Math.min(acHighlightIndex + 1, items.length - 1);
            renderBillDropdown();
            // Scroll into view
            const highlighted = dropdown.querySelector('.highlighted');
            if (highlighted) highlighted.scrollIntoView({ block: 'nearest' });
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            acHighlightIndex = Math.max(acHighlightIndex - 1, 0);
            renderBillDropdown();
            const highlighted = dropdown.querySelector('.highlighted');
            if (highlighted) highlighted.scrollIntoView({ block: 'nearest' });
        } else if (e.key === 'Enter') {
            e.preventDefault();
            if (acHighlightIndex >= 0 && acHighlightIndex < items.length) {
                input.value = items[acHighlightIndex].getAttribute('data-value');
            }
            closeBillDropdown();
            saveBillFormToLocalStorage();
        } else if (e.key === 'Escape') {
            closeBillDropdown();
        }
    });
    
    // Click on dropdown item
    dropdown.addEventListener('mousedown', (e) => {
        // mousedown instead of click to fire before blur
        const item = e.target.closest('.autocomplete-item');
        if (item) {
            input.value = item.getAttribute('data-value');
            closeBillDropdown();
            saveBillFormToLocalStorage();
        }
    });
    
    // Close dropdown when clicking outside
    document.addEventListener('click', (e) => {
        if (!e.target.closest('.autocomplete-wrapper')) {
            closeBillDropdown();
        }
    });
}

// ==================== SAVE/LOAD FORM ====================

const SAVE_PATH_IDS = ['savePathK1', 'savePathK2', 'savePathK3', 'savePathK4', 'savePathK5', 'savePathSP'];
const KMART_SAVE_KEY_MAP = {
    'K1': 'savePathK1',
    'K2': 'savePathK2',
    'K3': 'savePathK3',
    'K4': 'savePathK4',
    'K5': 'savePathK5',
    'SP': 'savePathSP',
};

function saveBillFormToLocalStorage() {
    const kmart = document.getElementById('kmartSelect').value;
    const bill = document.getElementById('billInput').value.trim();
    const partA = document.getElementById('partAInput').value.trim();
    const partB = document.getElementById('partBInput').value.trim();
    
    // Collect all save paths
    const savePaths = {};
    SAVE_PATH_IDS.forEach(id => {
        const el = document.getElementById(id);
        if (el) savePaths[id] = el.value.trim();
    });
    
    const config = { kmart, bill, partA, partB, savePaths };
    localStorage.setItem('billProcessorConfig', JSON.stringify(config));
}

async function saveBillPathsToBackend() {
    const partA = document.getElementById('partAInput').value.trim();
    const partB = document.getElementById('partBInput').value.trim();
    
    // Collect all save paths
    const savePaths = {};
    SAVE_PATH_IDS.forEach(id => {
        const el = document.getElementById(id);
        if (el) savePaths[id] = el.value.trim();
    });
    
    // Validate that at least one search folder is set
    if (!partA && !partB) {
        showBillStatus('❌ กรุณาระบุโฟลเดอร์ part_a หรือ part_b อย่างน้อยหนึ่งแห่ง', 'error');
        return;
    }
    
    // Save to localStorage (original behavior)
    saveBillFormToLocalStorage();
    
    // Save to Backend Config
    let existingConfig = {};
    if (DESKTOP_MODE) {
        try {
            existingConfig = await eel.load_paths_config()();
        } catch (error) {
            console.error('Error loading existing config:', error);
        }
    }
    
    // Merge Page 2 settings
    const page2Settings = {
        partA: partA,
        partB: partB,
        ...savePaths
    };
    
    const mergedConfig = { ...existingConfig, ...page2Settings };
    
    if (DESKTOP_MODE) {
        try {
            const success = await eel.save_paths_config(mergedConfig)();
            if (success) {
                showBillStatus('✅ บันทึกการตั้งค่าเส้นทางทั้งหมดสำเร็จแล้ว!', 'success');
            } else {
                showBillStatus('❌ ไม่สามารถบันทึกการตั้งค่าเส้นทางได้', 'error');
            }
        } catch (error) {
            console.error('Error saving Page 2 config to backend:', error);
            showBillStatus('❌ เกิดข้อผิดพลาดขณะเชื่อมต่อกับระบบหลัก', 'error');
        }
    } else {
        showBillStatus('✅ บันทึกการตั้งค่าเส้นทาง (Local) สำเร็จแล้ว!', 'success');
    }
}

async function loadBillFormFromBackend() {
    let paths = {};
    if (DESKTOP_MODE) {
        try {
            paths = await eel.load_paths_config()();
        } catch (error) {
            console.error('Error loading config from backend:', error);
        }
    }
    
    // Also try localStorage as fallback or merge
    let localConfig = {};
    const saved = localStorage.getItem('billProcessorConfig');
    if (saved) {
        try {
            localConfig = JSON.parse(saved);
        } catch (e) {
            console.error("Error parsing bill form config:", e);
        }
    }
    
    // Load inputs
    const kmart = localConfig.kmart || 'K1';
    const bill = localConfig.bill || '';
    const partA = paths.partA || localConfig.partA || "G:\\My Drive\\KMART(ใช้งาน)";
    const partB = paths.partB || localConfig.partB || "G:\\My Drive\\SP";
    
    document.getElementById('kmartSelect').value = kmart;
    document.getElementById('billInput').value = bill;
    document.getElementById('partAInput').value = partA;
    document.getElementById('partBInput').value = partB;
    
    // Load save paths
    SAVE_PATH_IDS.forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.value = paths[id] || (localConfig.savePaths && localConfig.savePaths[id]) || '';
        }
    });
    
    // Migration: if old config has destPath but no savePaths, migrate
    if (localConfig.destPath && (!localConfig.savePaths && !paths.savePathK1)) {
        SAVE_PATH_IDS.forEach(id => {
            const el = document.getElementById(id);
            if (el && !el.value) el.value = localConfig.destPath;
        });
    }
    
    // If SP path is empty, set default
    const spEl = document.getElementById('savePathSP');
    if (spEl && !spEl.value) {
        spEl.value = "C:\\Users\\KS\\Desktop";
    }
}

// ==================== BROWSE BUTTONS ====================

async function handleBrowsePartAClick() {
    const path = await eel.select_directory_dialog()();
    if (path) {
        document.getElementById('partAInput').value = path;
        saveBillFormToLocalStorage();
        fetchBillSuggestions();
    }
}

async function handleBrowsePartBClick() {
    const path = await eel.select_directory_dialog()();
    if (path) {
        document.getElementById('partBInput').value = path;
        saveBillFormToLocalStorage();
        fetchBillSuggestions();
    }
}

async function handleBrowseSavePathClick(targetId) {
    const path = await eel.select_directory_dialog()();
    if (path) {
        document.getElementById(targetId).value = path;
        saveBillFormToLocalStorage();
    }
}

// ==================== RUN BILL PROCESSOR ====================

async function runBillProcessor() {
    const kmart = document.getElementById('kmartSelect').value;
    const bill = document.getElementById('billInput').value.trim();
    const partA = document.getElementById('partAInput').value.trim();
    const partB = document.getElementById('partBInput').value.trim();
    
    // Get save path for the selected branch
    const savePathId = KMART_SAVE_KEY_MAP[kmart];
    const destPath = savePathId ? document.getElementById(savePathId).value.trim() : '';
    
    if (!bill) {
        showBillStatus('❌ กรุณาระบุเดือน-ท้ายบิล (เช่น 05 หรือ 05-1)', 'error');
        return;
    }
    if (!destPath) {
        showBillStatus(`❌ กรุณาระบุ PATH ปลายทางเซฟไฟล์สำหรับสาขา ${kmart}`, 'error');
        return;
    }
    if (!partA && !partB) {
        showBillStatus('❌ กรุณาระบุโฟลเดอร์ part_a หรือ part_b อย่างน้อยหนึ่งแห่ง', 'error');
        return;
    }
    
    saveBillFormToLocalStorage();
    
    showBillStatus('⏳ กำลังประมวลผลไฟล์บิลย้อนหลัง...', 'loading');
    document.getElementById('billResultCard').style.display = 'none';
    
    try {
        const result = await eel.process_pass_2_save(kmart, bill, destPath, partA, partB)();
        
        if (result.success) {
            showBillStatus(`✅ ${result.message}`, 'success');
            
            const resultCard = document.getElementById('billResultCard');
            const resultContent = document.getElementById('billResultContent');
            
            resultContent.textContent = `🎉 ประมวลผลสำเร็จ!
📄 ชื่อไฟล์สาขา: ${kmart}-${bill}
📊 จำนวนข้อมูลแถวทั้งหมด: ${result.row_count} บรรทัด
💾 เซฟตำแหน่งไฟล์: ${result.save_path}`;
            
            resultCard.style.display = 'block';
        } else {
            showBillStatus(`❌ ${result.message}`, 'error');
        }
    } catch (err) {
        console.error("Processing bill error:", err);
        showBillStatus(`❌ เกิดข้อผิดพลาด: ${err.message}`, 'error');
    }
}

function showBillStatus(message, type = 'loading') {
    const msgEl = document.getElementById('billStatusMessage');
    const textEl = document.getElementById('billStatusText');
    const iconEl = document.getElementById('billStatusIcon');
    
    msgEl.className = `status-message ${type}`;
    textEl.textContent = message;
    
    const icons = {
        'loading': '⏳',
        'success': '✅',
        'error': '❌'
    };
    iconEl.textContent = icons[type] || '⏳';
    msgEl.style.display = 'flex';
    
    if (type !== 'loading') {
        setTimeout(() => {
            msgEl.style.display = 'none';
        }, 7000);
    }
}
