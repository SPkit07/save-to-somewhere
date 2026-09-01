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
    
    // Page 3 (Code snippets) Initializations
    try { await initCodeTab(); } catch (e) { console.warn('Code tab init failed', e); }

    // Page 3 (Problematic Barcodes) Initializations
    try { await initProblematicBarcodes(); } catch (e) { console.warn('Problematic barcodes init failed', e); }

    // Program ON/OFF Switch
    setupProgramStatusToggle();
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
        } else if (preview.problematic_warnings && preview.problematic_warnings.length > 0) {
            showProblematicWarningModal(preview);
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
        } else if (currentPreviewData.problematic_warnings && currentPreviewData.problematic_warnings.length > 0) {
            showProblematicWarningModal(currentPreviewData);
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
        if (currentPreviewData.problematic_warnings && currentPreviewData.problematic_warnings.length > 0) {
            showProblematicWarningModal(currentPreviewData);
        } else {
            showPreviewModal(currentPreviewData);
        }
    }
}

// ==================== SHOW PROBLEMATIC BARCODE WARNING MODAL ====================
function showProblematicWarningModal(preview) {
    const modal = document.getElementById('problematicBarcodeModal');
    if (!modal) return;
    
    const tbody = document.getElementById('problematicWarningTableBody');
    tbody.innerHTML = '';
    
    if (preview.problematic_warnings && preview.problematic_warnings.length > 0) {
        preview.problematic_warnings.forEach(item => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>${item.sku_name}</td>
                <td class="mismatch">${item.wrong_barcode}</td>
                <td style="color: var(--orange); font-weight: 600;">${item.expected_error || '-'}</td>
                <td style="color: var(--green); font-weight: 600;">${item.recommended_barcode || '-'}</td>
            `;
            tbody.appendChild(tr);
        });
    }
    
    modal.style.display = 'flex';
    statusMessage.style.display = 'none';
}

function closeProblematicWarningModal() {
    const modal = document.getElementById('problematicBarcodeModal');
    if (modal) {
        modal.style.display = 'none';
    }
    currentPreviewData = null; // ยกเลิกการทำรายการ
}

function continueFromProblematicWarningToPreview() {
    const modal = document.getElementById('problematicBarcodeModal');
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
        document.getElementById('summaryBranchName').textContent = `${document.getElementById('branchName').textContent} (${document.getElementById('branchCode').textContent.replace('รหัสสาขา: ', '')})`;
        document.getElementById('summaryFileName').innerHTML = '<span style="color: #95a5a6;">(รอประมวลผล)</span>';
        document.getElementById('summaryTotalRows').textContent = preview.total_rows;
        document.getElementById('summarySPCount').textContent = preview.sp_count || 0;
        document.getElementById('summaryWHCount').textContent = preview.wh_count || 0;
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

// ==================== SHOW ERROR MODAL ====================
function showErrorModal(message) {
    const modal = document.getElementById('errorModal');
    const msgEl = document.getElementById('errorModalMessage');
    if (modal && msgEl) {
        msgEl.textContent = message;
        modal.style.display = 'flex';
    } else {
        alert(message);
    }
}

function closeErrorModal() {
    const modal = document.getElementById('errorModal');
    if (modal) {
        modal.style.display = 'none';
    }
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
let pendingSplitData = null;

function goToAiStock() {
    if (!currentPreviewData) {
        showStatus('❌ ไม่มีข้อมูลไฟล์', 'error');
        return;
    }
    
    pendingSplitData = { ...currentPreviewData };
    closePreviewModal();
    
    // Switch to Tab 4
    switchTab('ai-stock');
    
    // Auto-fill Tab 4
    if (typeof aiReceiveTempPath !== 'undefined') {
        aiReceiveTempPath = pendingSplitData.file_path; 
        aiDetectedBranch = pendingSplitData.detected_branch;
        
        const aiReceiveFileName = document.getElementById("aiReceiveFileName");
        if (aiReceiveFileName) aiReceiveFileName.innerText = pendingSplitData.file_name || "ไฟล์จากหน้าแรก";
        
        const aiBranchName = document.getElementById("aiBranchName");
        if (aiBranchName) aiBranchName.innerText = pendingSplitData.branch_name || "Unknown";
        
        const aiBranchCode = document.getElementById("aiBranchCode");
        if (aiBranchCode) aiBranchCode.innerText = "รหัสสาขา: " + (pendingSplitData.detected_branch || "-");
        
        const finalSplitBtn = document.getElementById("finalSplitBtn");
        if (finalSplitBtn) finalSplitBtn.style.display = "block";
    }
}

async function executeFinalSplit() {
    if (!pendingSplitData) {
        showStatus('❌ ไม่มีข้อมูลไฟล์สำหรับแยก', 'error');
        return;
    }

    const previewData = { ...pendingSplitData };

    // Switch back to Tab 1 to show progress
    switchTab('processor');
    showStatus('⏳ กำลังตรวจสอบที่อยู่ปลายทาง...', 'loading');

    const validation = await validatePathsAndDirectories();
    if (!validation.valid) {
        const errorMsg = validation.errors.join('\n');
        showErrorModal(errorMsg);
        showStatus('❌ พบข้อผิดพลาดในการตั้งค่า Path', 'error');
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
            // อัปเดตชื่อไฟล์ที่เซฟใน Card 3
            if (result.saved_file_names && result.saved_file_names.length > 0) {
                let exportFilesHtml = '';
                result.saved_file_names.forEach((name, index) => {
                    const folderPath = (result.saved_file_paths && result.saved_file_paths[index]) || '';
                    if (folderPath) {
                        exportFilesHtml += `<span class="saved-file-link" data-folder-path="${folderPath.replace(/\\/g, '\\\\')}" title="คลิกเพื่อเปิดโฟลเดอร์ปลายทาง">📁 ${name}</span><br>`;
                    } else {
                        exportFilesHtml += `📁 ${name}<br>`;
                    }
                });
                document.getElementById('summaryFileName').innerHTML = exportFilesHtml;

                // Bind click events to the saved file links
                document.querySelectorAll('.saved-file-link').forEach(link => {
                    link.addEventListener('click', async function() {
                        const folderPath = this.getAttribute('data-folder-path');
                        if (folderPath && DESKTOP_MODE) {
                            this.style.opacity = '0.6';
                            try {
                                const opened = await eel.open_folder_in_explorer(folderPath)();
                                if (!opened) {
                                    showStatus('❌ ไม่สามารถเปิดโฟลเดอร์ได้ (อาจถูกลบหรือย้ายไปแล้ว)', 'error');
                                }
                            } catch (err) {
                                console.error('Error opening folder:', err);
                                showStatus('❌ เกิดข้อผิดพลาดในการเปิดโฟลเดอร์', 'error');
                            } finally {
                                this.style.opacity = '1';
                            }
                        }
                    });
                });
            }
            // กางหน้าต่างสรุปข้อมูลออกอัตโนมัติ
            const summaryDetails = document.getElementById('fileSummaryDisplay');
            if (summaryDetails) {
                summaryDetails.open = true;
            }
            // Clear pending and hide button
            pendingSplitData = null;
            const finalSplitBtn = document.getElementById("finalSplitBtn");
            if (finalSplitBtn) finalSplitBtn.style.display = "none";
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
                    <div style="display: flex; gap: 10px;">
                        <input type="text" id="path_${code}" class="path-input" data-key="${code}" placeholder="เช่น: C:\\Users\\USER\\Desktop\\${branch}">
                        <button class="browse-btn page1-browse-btn" data-target="path_${code}" style="white-space: nowrap; padding: 10px 15px;">เลือกโฟลเดอร์</button>
                    </div>
                </div>
                <div class="path-input-group">
                    <label class="path-label">📦 ${branch}-WH (รหัส 00)</label>
                    <div style="display: flex; gap: 10px;">
                        <input type="text" id="path_${code}_00" class="path-input" data-key="${code}_00" placeholder="เช่น: C:\\Users\\USER\\Desktop\\${code}00">
                        <button class="browse-btn page1-browse-btn" data-target="path_${code}_00" style="white-space: nowrap; padding: 10px 15px;">เลือกโฟลเดอร์</button>
                    </div>
                </div>
            `;
        } else {
            // หนึ่งช่อง: SP เท่านั้น
            html += `
                <div class="path-input-group">
                    <label class="path-label">📁 SP (รหัส ${code})</label>
                    <div style="display: flex; gap: 10px;">
                        <input type="text" id="path_${code}" class="path-input" data-key="SP" placeholder="เช่น: C:\\Users\\USER\\Desktop\\SP00">
                        <button class="browse-btn page1-browse-btn" data-target="path_${code}" style="white-space: nowrap; padding: 10px 15px;">เลือกโฟลเดอร์</button>
                    </div>
                </div>
            `;
        }

        html += '</div>';
    });

    branchPathsContainer.innerHTML = html;

    // Add event listeners for the new browse buttons
    document.querySelectorAll('.page1-browse-btn').forEach(btn => {
        btn.addEventListener('click', async () => {
            const targetId = btn.getAttribute('data-target');
            const path = await eel.select_directory_dialog()();
            if (path) {
                document.getElementById(targetId).value = path;
            }
        });
    });
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

    // ตรวจสอบว่า directory มีอยู่จริงหรือไม่ก่อนเซฟ (ตามที่ user ต้องการ)
    showStatus('⏳ กำลังตรวจสอบที่อยู่ปลายทาง...', 'loading');
    const validation = await validatePathsAndDirectories();
    if (!validation.valid) {
        showStatus('❌ โฟลเดอร์ปลายทางไม่มีอยู่จริง กรุณาตรวจสอบ', 'error');
        showErrorModal(validation.errors.join('\n'));
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
    const tabBtnMap = {
        'processor': 'tabBtnProcessor',
        'bill-processor': 'tabBtnBillProcessor',
        'code': 'tabBtnCode',
        'ai-stock': 'tabBtnAiStock'
    };
    const activeBtn = document.getElementById(tabBtnMap[tabName]);
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

    // ตรวจสอบว่าโฟลเดอร์มีอยู่จริงหรือไม่
    showBillStatus('⏳ กำลังตรวจสอบโฟลเดอร์...', 'loading');
    const errors = [];
    
    if (partA && !(await eel.check_directory_exists(partA)())) {
        errors.push(`❌ ไม่พบโฟลเดอร์ค้นหา: ${partA}`);
    }
    if (partB && !(await eel.check_directory_exists(partB)())) {
        errors.push(`❌ ไม่พบโฟลเดอร์ค้นหา: ${partB}`);
    }
    
    for (const id of Object.keys(savePaths)) {
        const path = savePaths[id];
        if (path && !(await eel.check_directory_exists(path)())) {
            const label = id.replace('savePath', '');
            errors.push(`❌ ไม่พบโฟลเดอร์ปลายทาง (${label}): ${path}`);
        }
    }
    
    if (errors.length > 0) {
        showBillStatus('❌ โฟลเดอร์ที่ระบุไม่มีอยู่จริง', 'error');
        showErrorModal(errors.join('\n'));
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
    
    // ตรวจสอบโฟลเดอร์ปลายทางว่ามีอยู่จริงไหม
    if (!(await eel.check_directory_exists(destPath)())) {
        showBillStatus(`❌ ไม่พบโฟลเดอร์ปลายทางที่ระบุ: ${destPath}`, 'error');
        showErrorModal(`โฟลเดอร์ปลายทางสำหรับเซฟไฟล์ ${kmart} ไม่มีอยู่จริง\nโปรดตรวจสอบหรือสร้างโฟลเดอร์: ${destPath}`);
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

// Expose a JS function to Python so Python can request the frontend to close its window
function _closeWindowFromPython() {
    try {
        window.close();
    } catch (e) {
        console.warn('Unable to close window from Python:', e);
    }
}
if (typeof eel !== 'undefined' && eel.expose) {
    try {
        eel.expose(_closeWindowFromPython);
    } catch (e) {
        console.warn('Failed to expose _closeWindowFromPython to Python:', e);
    }
}

// ==================== PROGRAM STATUS TOGGLE WITH EXE SELECTION ====================
function setupProgramStatusToggle() {
    const toggle = document.getElementById('programStatusToggle');
    const stateText = document.getElementById('statusStateText');
    const overlay = document.getElementById('shutdownOverlay');
    const recentExeSelect = document.getElementById('recentExeSelect');
    const refreshExeBtn = document.getElementById('refreshExeBtn');
    const customExePath = document.getElementById('customExePath');
    const browseExeBtn = document.getElementById('browseExeBtn');

    if (!toggle || !stateText) return;

    async function saveSelectedExePath(path) {
        if (typeof eel !== 'undefined' && eel.save_selected_exe_path) {
            try {
                await new Promise((resolve) => {
                    eel.save_selected_exe_path(path)(function(success) {
                        resolve(success);
                    });
                });
            } catch (error) {
                console.error('Error saving selected exe path:', error);
            }
        }
    }

    async function loadSavedExePath() {
        if (typeof eel === 'undefined' || !eel.get_saved_exe_path) return;

        try {
            const savedPath = await new Promise((resolve) => {
                eel.get_saved_exe_path()(function(result) {
                    resolve(result);
                });
            });

            if (savedPath && recentExeSelect) {
                const matchingOption = Array.from(recentExeSelect.options).find((option) => option.value === savedPath);
                if (matchingOption) {
                    recentExeSelect.value = savedPath;
                    if (customExePath) {
                        customExePath.value = '';
                    }
                } else if (customExePath) {
                    customExePath.value = savedPath;
                }
            }
        } catch (error) {
            console.error('Error loading saved exe path:', error);
        }
    }

    // Load recent exe files on startup
    const initializeExeSelection = async () => {
        await loadRecentExeFiles();
        await loadSavedExePath();
    };
    initializeExeSelection();

    const requestProgramRestart = () => {
        if (overlay) {
            overlay.style.display = 'flex';
        }

        // Show restart message
        const shutdownText = overlay?.querySelector('div');
        if (shutdownText) {
            shutdownText.textContent = "🔄 กำลังรีสตาร์ทโปรแกรม...";
        }

        if (typeof eel !== 'undefined' && eel.restart_application) {
            try {
                eel.restart_application()(function() {});
            } catch (error) {
                console.error('Failed to restart program:', error);
            }
        } else {
            try {
                window.close();
            } catch (error) {
                console.error('Failed to close window:', error);
            }
        }
    };

    const launchExcelProcessor = () => {
        if (typeof eel !== 'undefined' && eel.launch_excel_processor) {
            try {
                eel.launch_excel_processor()(function(success) {
                    if (success) {
                        console.log('✅ ExcelProcessor launched successfully');
                    } else {
                        console.error('❌ Failed to launch ExcelProcessor');
                        // Keep toggle ON even if launch failed
                    }
                });
            } catch (error) {
                console.error('Error calling launch_excel_processor:', error);
            }
        }
    };

    const launchExcelProcessorFromPath = (exePath) => {
        if (!exePath) {
            console.error('❌ No exe path provided');
            return;
        }

        if (typeof eel !== 'undefined' && eel.launch_excel_processor_from_path) {
            try {
                saveSelectedExePath(exePath);
                eel.launch_excel_processor_from_path(exePath)(function(success) {
                    if (success) {
                        console.log(`✅ Program launched from: ${exePath}`);
                    } else {
                        console.error(`❌ Failed to launch from: ${exePath}`);
                        alert('ไม่สามารถเปิดไฟล์ .exe ได้ โปรดตรวจสอบเส้นทาง');
                    }
                });
            } catch (error) {
                console.error('Error calling launch_excel_processor_from_path:', error);
                alert('เกิดข้อผิดพลาดในการเปิดไฟล์ .exe');
            }
        }
    };

    // Load recent exe files from backend
    async function loadRecentExeFiles() {
        if (typeof eel === 'undefined' || !eel.get_recent_exe_files) return;

        try {
            const exeList = await new Promise((resolve) => {
                eel.get_recent_exe_files()(function(result) {
                    resolve(result);
                });
            });

            // Clear existing options (except first)
            while (recentExeSelect.options.length > 1) {
                recentExeSelect.remove(1);
            }

            // Add exe files to dropdown
            if (exeList && exeList.length > 0) {
                exeList.forEach((exe, index) => {
                    const option = document.createElement('option');
                    option.value = exe.path;
                    option.textContent = `${exe.name} (${exe.size_mb}MB)`;
                    recentExeSelect.appendChild(option);
                });
                console.log(`✅ Loaded ${exeList.length} recent exe files`);
            } else {
                console.log('ℹ️ No recent exe files found');
            }
        } catch (error) {
            console.error('Error loading recent exe files:', error);
        }
    }

    // Refresh exe files
    if (refreshExeBtn) {
        refreshExeBtn.addEventListener('click', () => {
            console.log('🔄 Refreshing exe files...');
            loadRecentExeFiles();
        });
    }

    // Browse for exe file
    if (browseExeBtn) {
        browseExeBtn.addEventListener('click', () => {
            if (typeof eel !== 'undefined' && eel.select_exe_file_dialog) {
                try {
                    eel.select_exe_file_dialog()(function(filePath) {
                        if (filePath && filePath.toLowerCase().endsWith('.exe')) {
                            customExePath.value = filePath;
                            if (recentExeSelect) {
                                recentExeSelect.value = '';
                            }
                            saveSelectedExePath(filePath);
                            console.log(`✅ Selected exe: ${filePath}`);
                        } else if (filePath) {
                            alert('โปรดเลือกไฟล์ .exe เท่านั้น');
                        }
                    });
                } catch (error) {
                    console.error('Error opening exe file dialog:', error);
                }
            }
        });
    }

    toggle.addEventListener('change', function() {
        if (!this.checked) {
            // User switched OFF -> restart the application
            stateText.textContent = "ปิดทำงาน (OFF)";
            stateText.classList.add('off');

            if (overlay) {
                overlay.style.display = 'flex';
            }

            setTimeout(requestProgramRestart, 180);
        } else {
            // User switched ON -> application is restarting fresh, so just show it's running
            stateText.textContent = "เปิดทำงาน (ON)";
            stateText.classList.remove('off');

            // Hide overlay instantly
            if (overlay) {
                overlay.style.display = 'none';
            }

            console.log('✅ Application restarted and running');
        }
    });

    // Listen for exe selection change to clear custom path
    if (recentExeSelect) {
        recentExeSelect.addEventListener('change', () => {
            if (recentExeSelect.value && customExePath) {
                customExePath.value = '';
            }
            saveSelectedExePath(recentExeSelect.value || '');
        });
    }

    // Listen for custom path input to clear exe selection
    if (customExePath) {
        customExePath.addEventListener('input', () => {
            if (customExePath.value && recentExeSelect) {
                recentExeSelect.value = '';
            }
            saveSelectedExePath(customExePath.value || '');
        });
    }
}

// ==================== PAGE 3: CODE SNIPPETS TAB ====================
async function initCodeTab() {
    const codeList = document.getElementById('codeList');
    if (!codeList) return;
    if (typeof CODE_TEXT === 'undefined' || !CODE_TEXT) {
        codeList.innerHTML = '<div style="color:#e74c3c;">ไม่พบข้อมูลโค้ด (CODE_TEXT)</div>';
        return;
    }

    // Set up form listeners for adding custom scripts
    setupCustomScriptListeners();

    const blocks = CODE_TEXT.split(/\n\/\/[-]{2,}\n/);
    codeList.innerHTML = '';
    codeList.style.display = 'flex';
    codeList.style.flexDirection = 'column';
    codeList.style.gap = '16px';
    codeList.style.padding = '4px 0';
    codeList.style.width = '100%';
    codeList.style.maxWidth = '860px';
    codeList.style.margin = '0 auto';

    // 1. Render all predefined blocks from CODE_TEXT
    for (const blk of blocks) {
        const trimmed = blk.trim();
        if (!trimmed) continue;

        // Extract the first comment line as the title
        const firstLine = trimmed.split('\n')[0].trim();
        let titleText = firstLine.replace(/^\/\/\s*/, '').trim();
        if (!titleText) titleText = 'โค้ด';

        // Check if this is the interactive last block
        if (trimmed.includes('แก้ไขรายชื่อและชื่อสาขาที่ต้องการ')) {
            // Render the interactive name config card
            const card = document.createElement('div');
            card.style.background = 'linear-gradient(135deg, #ffffff 0%, #f8fbff 100%)';
            card.style.border = '1px solid #dce7ff';
            card.style.padding = '16px';
            card.style.borderRadius = '16px';
            card.style.display = 'flex';
            card.style.flexDirection = 'column';
            card.style.gap = '12px';
            card.style.boxShadow = '0 10px 24px rgba(39, 64, 96, 0.08)';
            card.style.width = '100%';

            const titleRow = document.createElement('div');
            titleRow.style.display = 'flex';
            titleRow.style.justifyContent = 'center';
            titleRow.style.alignItems = 'center';
            titleRow.style.gap = '10px';
            titleRow.style.textAlign = 'center';

            const titleBlock = document.createElement('div');
            titleBlock.style.display = 'flex';
            titleBlock.style.flexDirection = 'column';
            titleBlock.style.gap = '2px';

            const title = document.createElement('div');
            title.innerText = '⚙️ ตัวจัดการชื่อและตำแหน่ง';
            title.style.fontWeight = '800';
            title.style.color = '#274060';
            title.style.fontSize = '15px';

            const subtitle = document.createElement('div');
            subtitle.innerText = 'เพิ่ม/ลบรายชื่อตามกลุ่ม SP (หน้าร้าน) หรือ WH (โกดัง)';
            subtitle.style.fontSize = '13px';
            subtitle.style.color = '#5f738c';

            titleBlock.appendChild(title);
            titleBlock.appendChild(subtitle);
            titleRow.appendChild(titleBlock);

            card.appendChild(titleRow);

            const mappingContainer = document.createElement('div');
            await createInteractiveNameConfigUI(mappingContainer, trimmed);
            card.appendChild(mappingContainer);

            codeList.appendChild(card);
        } else {
            // Render a standard code card with title + copy button
            codeList.appendChild(createCodeCard(titleText, trimmed));
        }
    }

    // 2. Render all custom scripts from Eel backend / localStorage
    let customScripts = [];
    try {
        if (typeof eel !== 'undefined' && eel.load_custom_scripts) {
            customScripts = await eel.load_custom_scripts()();
        }
    } catch (e) {
        console.error('Failed to load custom scripts from backend:', e);
    }
    if (!customScripts || customScripts.length === 0) {
        customScripts = JSON.parse(localStorage.getItem('custom_scripts') || '[]');
    }

    customScripts.forEach((script, index) => {
        codeList.appendChild(createCustomCodeCard(script.title, script.code, index));
    });
}

function setupCustomScriptListeners() {
    if (window.customScriptListenersAttached) return;
    window.customScriptListenersAttached = true;

    const addBtn = document.getElementById('addCustomScriptBtn');
    const form = document.getElementById('customScriptForm');
    const cancelBtn = document.getElementById('cancelCustomScriptBtn');
    const saveBtn = document.getElementById('saveCustomScriptBtn');
    const titleInput = document.getElementById('customScriptTitle');
    const codeInput = document.getElementById('customScriptCode');

    if (!addBtn || !form || !cancelBtn || !saveBtn) return;

    addBtn.addEventListener('click', () => {
        form.style.display = form.style.display === 'none' ? 'flex' : 'none';
        titleInput.value = '';
        codeInput.value = '';
    });

    cancelBtn.addEventListener('click', () => {
        form.style.display = 'none';
    });

    saveBtn.addEventListener('click', async () => {
        const title = titleInput.value.trim();
        const code = codeInput.value.trim();

        if (!title || !code) {
            alert('กรุณากรอกข้อมูลให้ครบถ้วน');
            return;
        }

        let customScripts = [];
        try {
            if (typeof eel !== 'undefined' && eel.load_custom_scripts) {
                customScripts = await eel.load_custom_scripts()();
            }
        } catch (e) {
            console.error('Failed to load custom scripts:', e);
        }
        if (!customScripts || customScripts.length === 0) {
            customScripts = JSON.parse(localStorage.getItem('custom_scripts') || '[]');
        }

        customScripts.push({ title, code });

        localStorage.setItem('custom_scripts', JSON.stringify(customScripts));
        try {
            if (typeof eel !== 'undefined' && eel.save_custom_scripts) {
                await eel.save_custom_scripts(customScripts)();
            }
        } catch (e) {
            console.error('Failed to save custom scripts:', e);
        }

        form.style.display = 'none';
        await initCodeTab(); // Re-render tab
    });
}

function createCodeCard(titleText, codeText) {
    const card = document.createElement('div');
    card.style.background = 'linear-gradient(135deg, #ffffff 0%, #f8fbff 100%)';
    card.style.border = '1px solid #e2e8f0';
    card.style.padding = '12px 16px';
    card.style.borderRadius = '12px';
    card.style.display = 'flex';
    card.style.justifyContent = 'space-between';
    card.style.alignItems = 'center';
    card.style.gap = '12px';
    card.style.boxShadow = '0 4px 10px rgba(15, 23, 42, 0.03)';

    const title = document.createElement('div');
    title.innerText = titleText;
    title.style.fontWeight = '700';
    title.style.color = '#2c3e50';
    title.style.fontSize = '14px';

    const copyBtn = document.createElement('button');
    copyBtn.innerHTML = '📋 ก็อปปี้';
    copyBtn.style.padding = '7px 14px';
    copyBtn.style.border = 'none';
    copyBtn.style.background = 'linear-gradient(90deg,#3b82f6,#2563eb)';
    copyBtn.style.color = 'white';
    copyBtn.style.borderRadius = '999px';
    copyBtn.style.cursor = 'pointer';
    copyBtn.style.fontSize = '12px';
    copyBtn.style.fontWeight = '600';
    copyBtn.style.whiteSpace = 'nowrap';

    copyBtn.addEventListener('click', () => {
        copyToClipboard(codeText);
        copyBtn.innerHTML = '✓ คัดลอกแล้ว';
        setTimeout(() => copyBtn.innerHTML = '📋 ก็อปปี้', 1400);
    });

    card.appendChild(title);
    card.appendChild(copyBtn);

    return card;
}

function createCustomCodeCard(titleText, codeText, index) {
    const card = createCodeCard(titleText, codeText);
    
    // Find the copy button inside the card
    const copyBtn = card.querySelector('button');
    
    const rightContainer = document.createElement('div');
    rightContainer.style.display = 'flex';
    rightContainer.style.gap = '8px';
    rightContainer.style.alignItems = 'center';

    // Replace the single copyBtn with a container of copy and delete buttons
    card.removeChild(copyBtn);
    rightContainer.appendChild(copyBtn);

    const delBtn = document.createElement('button');
    delBtn.innerHTML = '🗑️ ลบ';
    delBtn.style.padding = '7px 14px';
    delBtn.style.border = 'none';
    delBtn.style.background = '#ef4444';
    delBtn.style.color = 'white';
    delBtn.style.borderRadius = '999px';
    delBtn.style.cursor = 'pointer';
    delBtn.style.fontSize = '12px';
    delBtn.style.fontWeight = '600';
    delBtn.style.whiteSpace = 'nowrap';
    delBtn.addEventListener('click', async () => {
        if (confirm('คุณแน่ใจว่าต้องการลบสคริปต์นี้?')) {
            let customScripts = [];
            try {
                if (typeof eel !== 'undefined' && eel.load_custom_scripts) {
                    customScripts = await eel.load_custom_scripts()();
                }
            } catch (e) {
                console.error('Failed to load custom scripts:', e);
            }
            if (!customScripts || customScripts.length === 0) {
                customScripts = JSON.parse(localStorage.getItem('custom_scripts') || '[]');
            }

            customScripts.splice(index, 1);
            
            localStorage.setItem('custom_scripts', JSON.stringify(customScripts));
            try {
                if (typeof eel !== 'undefined' && eel.save_custom_scripts) {
                    await eel.save_custom_scripts(customScripts)();
                }
            } catch (e) {
                console.error('Failed to save custom scripts:', e);
            }
            await initCodeTab();
        }
    });
    rightContainer.appendChild(delBtn);
    card.appendChild(rightContainer);

    // Give the card a slightly different look to indicate it is user-added
    card.style.border = '1px solid #10b981';
    
    return card;
}

function createColumnUI(titleText, themeColor, entriesList, isSP) {
    const col = document.createElement('div');
    col.style.background = '#ffffff';
    col.style.borderRadius = '12px';
    col.style.padding = '16px';
    col.style.border = `1px solid ${themeColor}22`;
    col.style.borderTop = `4px solid ${themeColor}`;
    col.style.boxShadow = '0 4px 10px rgba(0, 0, 0, 0.03)';
    col.style.display = 'flex';
    col.style.flexDirection = 'column';
    col.style.gap = '12px';

    const colHeader = document.createElement('h4');
    colHeader.innerText = titleText;
    colHeader.style.margin = '0';
    colHeader.style.color = '#2c3e50';
    colHeader.style.fontSize = '14px';
    colHeader.style.fontWeight = '700';
    col.appendChild(colHeader);

    const listContainer = document.createElement('div');
    listContainer.style.display = 'flex';
    listContainer.style.flexDirection = 'column';
    listContainer.style.gap = '8px';
    col.appendChild(listContainer);

    function addNameRow(val = '') {
        const row = document.createElement('div');
        row.style.display = 'flex';
        row.style.gap = '8px';
        row.style.alignItems = 'center';

        const nameInput = document.createElement('input');
        nameInput.type = 'text';
        nameInput.value = val;
        nameInput.placeholder = 'ใส่ชื่อ...';
        nameInput.style.flex = '1';
        nameInput.style.padding = '8px 12px';
        nameInput.style.border = '1px solid #cbd5e1';
        nameInput.style.borderRadius = '6px';
        nameInput.style.fontSize = '13px';
        nameInput.className = isSP ? 'sp-name-input' : 'wh-name-input';

        const delBtn = document.createElement('button');
        delBtn.innerText = '✖';
        delBtn.title = 'ลบชื่อ';
        delBtn.style.background = 'transparent';
        delBtn.style.border = 'none';
        delBtn.style.cursor = 'pointer';
        delBtn.style.color = '#ef4444';
        delBtn.style.fontSize = '14px';
        delBtn.style.padding = '4px 8px';
        delBtn.addEventListener('click', () => row.remove());

        row.appendChild(nameInput);
        row.appendChild(delBtn);
        listContainer.appendChild(row);
    }

    // populate initial list
    entriesList.forEach(name => addNameRow(name));

    const addBtn = document.createElement('button');
    addBtn.innerText = `＋ เพิ่มชื่อ ${isSP ? 'SP' : 'WH'}`;
    addBtn.style.background = 'transparent';
    addBtn.style.color = themeColor;
    addBtn.style.border = `1px dashed ${themeColor}`;
    addBtn.style.padding = '8px';
    addBtn.style.borderRadius = '6px';
    addBtn.style.cursor = 'pointer';
    addBtn.style.fontSize = '12px';
    addBtn.style.fontWeight = '600';
    addBtn.style.textAlign = 'center';
    addBtn.addEventListener('click', () => addNameRow(''));
    col.appendChild(addBtn);

    return { 
        colElement: col, 
        getNames: () => {
            const inputs = Array.from(listContainer.querySelectorAll(isSP ? '.sp-name-input' : '.wh-name-input'));
            return inputs.map(i => i.value.trim()).filter(Boolean);
        }
    };
}

async function createInteractiveNameConfigUI(container, codeBlockText) {
    container.innerHTML = '';
    
    // Check if there is saved name configuration in localStorage or Eel backend
    let spNames = [];
    let whNames = [];
    let savedConfig = null;
    
    try {
        if (typeof eel !== 'undefined' && eel.load_custom_names_config) {
            const backendConfig = await eel.load_custom_names_config()();
            if (backendConfig && (backendConfig.spNames || backendConfig.whNames)) {
                savedConfig = JSON.stringify(backendConfig);
            }
        }
    } catch (e) {
        console.error('Failed to load custom names config from backend:', e);
    }
    
    if (!savedConfig) {
        savedConfig = localStorage.getItem('custom_names_config');
    }
    
    if (savedConfig) {
        try {
            const parsed = JSON.parse(savedConfig);
            spNames = parsed.spNames || [];
            whNames = parsed.whNames || [];
        } catch (e) {
            console.error('Failed to parse saved name config:', e);
        }
    }
    
    // Fallback to parsed entries from CODE_TEXT if no saved configuration exists
    if ((!spNames || spNames.length === 0) && (!whNames || whNames.length === 0)) {
        const entries = parseNameConfigFromBlock(codeBlockText);
        spNames = entries.filter(e => e.source === 'SP').map(e => e.name);
        whNames = entries.filter(e => e.source !== 'SP').map(e => e.name);
    }

    // Side-by-side columns container using the .interactive-cols CSS class
    const colsContainer = document.createElement('div');
    colsContainer.className = 'interactive-cols';
    colsContainer.style.marginTop = '10px';
    container.appendChild(colsContainer);

    // Helper to create column
    const spColData = createColumnUI('🛍️ หน้าร้าน (SP)', '#2563eb', spNames, true);
    const whColData = createColumnUI('🏢 คลังสินค้า / โกดัง (WH)', '#0f766e', whNames, false);

    colsContainer.appendChild(spColData.colElement);
    colsContainer.appendChild(whColData.colElement);

    // Controls container
    const controls = document.createElement('div');
    controls.style.display = 'flex';
    controls.style.justifyContent = 'center';
    controls.style.gap = '10px';
    controls.style.flexWrap = 'wrap';
    controls.style.marginTop = '15px';

    const saveNamesBtn = document.createElement('button');
    saveNamesBtn.innerHTML = '💾 บันทึกรายชื่อในเครื่อง';
    saveNamesBtn.style.background = 'linear-gradient(90deg,#10b981,#059669)';
    saveNamesBtn.style.color = 'white';
    saveNamesBtn.style.border = 'none';
    saveNamesBtn.style.padding = '10px 20px';
    saveNamesBtn.style.borderRadius = '999px';
    saveNamesBtn.style.cursor = 'pointer';
    saveNamesBtn.style.fontWeight = '600';
    saveNamesBtn.style.fontSize = '14px';

    saveNamesBtn.addEventListener('click', async () => {
        const finalSpNames = spColData.getNames();
        const finalWhNames = whColData.getNames();

        const configToSave = {
            spNames: finalSpNames,
            whNames: finalWhNames
        };

        localStorage.setItem('custom_names_config', JSON.stringify(configToSave));
        try {
            if (typeof eel !== 'undefined' && eel.save_custom_names_config) {
                await eel.save_custom_names_config(configToSave)();
            }
        } catch (e) {
            console.error('Failed to save names config to backend:', e);
        }
        
        saveNamesBtn.innerHTML = '✓ บันทึกสำเร็จ!';
        setTimeout(() => saveNamesBtn.innerHTML = '💾 บันทึกรายชื่อในเครื่อง', 1400);
    });

    const genCopyBtn = document.createElement('button');
    genCopyBtn.innerHTML = '📦 คัดลอกโค้ดแก้ไขรายชื่อ';
    genCopyBtn.style.background = 'linear-gradient(90deg,#8b5cf6,#7c3aed)';
    genCopyBtn.style.color = 'white';
    genCopyBtn.style.border = 'none';
    genCopyBtn.style.padding = '10px 20px';
    genCopyBtn.style.borderRadius = '999px';
    genCopyBtn.style.cursor = 'pointer';
    genCopyBtn.style.fontWeight = '600';
    genCopyBtn.style.fontSize = '14px';

    genCopyBtn.addEventListener('click', () => {
        const finalSpNames = spColData.getNames();
        const finalWhNames = whColData.getNames();

        const spData = finalSpNames.map(name => ({ name, source: 'SP', target: 'SP' }));
        const whData = finalWhNames.map(name => ({ name, source: 'WH', target: 'WH' }));
        const combinedData = [...whData, ...spData];

        const generated = generateNameConfigCode(combinedData, codeBlockText);
        copyToClipboard(generated);
        genCopyBtn.innerHTML = '✓ คัดลอกสำเร็จแล้ว!';
        setTimeout(() => genCopyBtn.innerHTML = '📦 คัดลอกโค้ดแก้ไขรายชื่อ', 1400);
    });

    const resetNamesBtn = document.createElement('button');
    resetNamesBtn.innerHTML = '🔄 รีเซ็ตรายชื่อเริ่มต้น';
    resetNamesBtn.style.background = 'linear-gradient(90deg,#6b7280,#4b5563)';
    resetNamesBtn.style.color = 'white';
    resetNamesBtn.style.border = 'none';
    resetNamesBtn.style.padding = '10px 20px';
    resetNamesBtn.style.borderRadius = '999px';
    resetNamesBtn.style.cursor = 'pointer';
    resetNamesBtn.style.fontWeight = '600';
    resetNamesBtn.style.fontSize = '14px';

    resetNamesBtn.addEventListener('click', async () => {
        if (confirm('คุณต้องการรีเซ็ตรายชื่อทั้งหมดกลับเป็นค่าเริ่มต้นหรือไม่?')) {
            localStorage.removeItem('custom_names_config');
            try {
                if (typeof eel !== 'undefined' && eel.save_custom_names_config) {
                    await eel.save_custom_names_config({spNames: [], whNames: []})();
                }
            } catch (e) {
                console.error('Failed to reset custom names config on backend:', e);
            }
            await createInteractiveNameConfigUI(container, codeBlockText);
        }
    });

    controls.appendChild(saveNamesBtn);
    controls.appendChild(genCopyBtn);
    controls.appendChild(resetNamesBtn);
    container.appendChild(controls);
}

function parseNameConfigFromBlock(blockText) {
    const results = [];
    const re = /"([^"\\]+)"\s*:\s*\{\s*source:\s*"([^"\\]+)"\s*,\s*target:\s*"([^"\\]+)"\s*\}/g;
    let m;
    while ((m = re.exec(blockText)) !== null) {
        results.push({ name: m[1], source: m[2], target: m[3] });
    }
    return results;
}

function generateNameConfigCode(entries, originalBlockText = '') {
    const entriesBlock = entries.map(e => {
        const safeName = e.name.replace(/\\"/g, '\\"');
        return `    "${safeName}":       { source: "${e.source}", target: "${e.target}" },`;
    }).join('\n');

    const generatedObject = `const nameConfig = {\n${entriesBlock ? entriesBlock + '\n' : ''}};`;

    if (originalBlockText && originalBlockText.includes('const nameConfig = {')) {
        const pattern = /const nameConfig = \{[\s\S]*?\n\};/;
        return originalBlockText.replace(pattern, generatedObject);
    }

    let out = '// แก้ไขรายชื่อและชื่อสาขาที่ต้องการ\n' + generatedObject + '\n';
    out += '\n// นำโค้ดนี้ไปวางทับส่วนเดิม หรือใช้กับสคริปต์ของคุณ\n';
    return out;
}

function copyToClipboard(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).catch(err => console.error('Copy failed', err));
    } else {
        const ta = document.createElement('textarea');
        ta.value = text;
        document.body.appendChild(ta);
        ta.select();
        try { document.execCommand('copy'); } catch (e) { console.error(e); }
        ta.remove();
    }
}

// ==================== PROBLEMATIC BARCODES SETTINGS (TAB 3) ====================
let problematicBarcodesList = [];

async function initProblematicBarcodes() {
    // Load from backend
    if (DESKTOP_MODE && typeof eel !== 'undefined' && eel.load_problematic_barcodes) {
        try {
            problematicBarcodesList = await eel.load_problematic_barcodes()();
        } catch (e) {
            console.warn('Failed to load problematic barcodes:', e);
            problematicBarcodesList = [];
        }
    }
    renderProblematicBarcodesTable();
    setupProblematicBarcodesEvents();
}

function setupProblematicBarcodesEvents() {
    const addBtn = document.getElementById('addPbBarcodeBtn');
    if (addBtn) {
        addBtn.addEventListener('click', addProblematicBarcode);
    }
}

async function addProblematicBarcode() {
    const nameInput = document.getElementById('pbNameInput');
    const barcodeInput = document.getElementById('pbBarcodeInput');
    const errorInput = document.getElementById('pbErrorInput');
    const recommendedInput = document.getElementById('pbRecommendedInput');
    
    const barcode = barcodeInput.value.trim();
    if (!barcode) {
        alert('กรุณาใส่บาร์ที่มีปัญหา (ช่องนี้จำเป็นต้องกรอก)');
        barcodeInput.focus();
        return;
    }
    
    // Check duplicate
    if (problematicBarcodesList.some(item => item.barcode === barcode)) {
        alert(`บาร์ "${barcode}" มีอยู่แล้วในรายการ`);
        return;
    }
    
    const newItem = {
        name: nameInput.value.trim(),
        barcode: barcode,
        error: errorInput.value.trim(),
        recommended: recommendedInput.value.trim()
    };
    
    problematicBarcodesList.push(newItem);
    await saveProblematicBarcodes();
    renderProblematicBarcodesTable();
    
    // Clear inputs
    nameInput.value = '';
    barcodeInput.value = '';
    errorInput.value = '';
    recommendedInput.value = '';
    barcodeInput.focus();
}

async function removeProblematicBarcode(index) {
    if (index < 0 || index >= problematicBarcodesList.length) return;
    
    const item = problematicBarcodesList[index];
    if (!confirm(`ต้องการลบบาร์ "${item.barcode}" (${item.name || '-'}) ออกจากรายการหรือไม่?`)) {
        return;
    }
    
    problematicBarcodesList.splice(index, 1);
    await saveProblematicBarcodes();
    renderProblematicBarcodesTable();
}

async function saveProblematicBarcodes() {
    if (DESKTOP_MODE && typeof eel !== 'undefined' && eel.save_problematic_barcodes) {
        try {
            await eel.save_problematic_barcodes(problematicBarcodesList)();
        } catch (e) {
            console.error('Failed to save problematic barcodes:', e);
        }
    }
}

function renderProblematicBarcodesTable() {
    const tbody = document.getElementById('pbBarcodeTableBody');
    if (!tbody) return;
    
    tbody.innerHTML = '';
    
    if (problematicBarcodesList.length === 0) {
        tbody.innerHTML = `
            <tr id="pbEmptyRow">
                <td colspan="5" style="text-align: center; color: var(--text-muted); padding: 20px;">ยังไม่มีรายการ กรุณาเพิ่มบาร์ที่คาดว่าจะมีปัญหาด้านบน</td>
            </tr>
        `;
        return;
    }
    
    problematicBarcodesList.forEach((item, index) => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${item.name || '-'}</td>
            <td style="font-family: 'IBM Plex Mono', monospace; font-weight: 600; color: var(--red);">${item.barcode}</td>
            <td style="color: var(--orange); font-weight: 500;">${item.error || '-'}</td>
            <td style="color: var(--green); font-weight: 500;">${item.recommended || '-'}</td>
            <td style="text-align: center;">
                <button onclick="removeProblematicBarcode(${index})" 
                    style="background: none; border: 1px solid var(--red); color: var(--red); border-radius: 6px; padding: 4px 8px; cursor: pointer; font-size: 11px; font-weight: 600; transition: var(--transition);" 
                    onmouseover="this.style.background='var(--red)'; this.style.color='white';" 
                    onmouseout="this.style.background='none'; this.style.color='var(--red)';">ลบ</button>
            </td>
        `;
        tbody.appendChild(tr);
    });
}
