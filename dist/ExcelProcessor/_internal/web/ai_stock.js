// ==================== PAGE 4 (AI STOCK) LOGIC ====================
let aiReceiveTempPath = null;
let aiDetectedBranch = null;

const aiReceiveDropzone = document.getElementById("aiReceiveDropzone");
const aiReceiveFileInput = document.getElementById("aiReceiveFileInput");
const aiStockFolderInput = document.getElementById("aiStockFolderInput");
const browseAiStockFolderBtn = document.getElementById("browseAiStockFolderBtn");

// Load saved folder from config file on disk
if (aiStockFolderInput) {
    // Load from backend config (persistent on disk)
    (async () => {
        try {
            if (typeof eel !== 'undefined' && eel.load_paths_config) {
                const config = await eel.load_paths_config()();
                if (config && config.aiStockFolder) {
                    aiStockFolderInput.value = config.aiStockFolder;
                }
            }
        } catch (err) {
            console.error("Error loading aiStockFolder from config:", err);
        }
    })();

    // Save to config when user types and leaves the field
    aiStockFolderInput.addEventListener('change', async (e) => {
        try {
            if (typeof eel !== 'undefined' && eel.load_paths_config && eel.save_paths_config) {
                const config = await eel.load_paths_config()() || {};
                config.aiStockFolder = e.target.value;
                await eel.save_paths_config(config)();
            }
        } catch (err) {
            console.error("Error saving aiStockFolder to config:", err);
        }
    });
}

if (browseAiStockFolderBtn) {
    browseAiStockFolderBtn.addEventListener('click', async () => {
        if (typeof eel !== 'undefined' && eel.select_folder_dialog) {
            try {
                const folderPath = await eel.select_folder_dialog()();
                if (folderPath) {
                    aiStockFolderInput.value = folderPath;
                    // Save to config file on disk
                    try {
                        const config = await eel.load_paths_config()() || {};
                        config.aiStockFolder = folderPath;
                        await eel.save_paths_config(config)();
                    } catch (saveErr) {
                        console.error("Error saving aiStockFolder to config:", saveErr);
                    }
                }
            } catch (err) {
                console.error("Error selecting folder:", err);
            }
        }
    });
}

if (aiReceiveDropzone) {
    aiReceiveDropzone.addEventListener("dragover", (e) => {
        e.preventDefault();
        aiReceiveDropzone.classList.add("dragover");
    });
    aiReceiveDropzone.addEventListener("dragleave", () => {
        aiReceiveDropzone.classList.remove("dragover");
    });
    aiReceiveDropzone.addEventListener("drop", async (e) => {
        e.preventDefault();
        aiReceiveDropzone.classList.remove("dragover");
        if (e.dataTransfer.files.length > 0) {
            await handleAiFile(e.dataTransfer.files[0], 'receive');
        }
    });
    aiReceiveFileInput.addEventListener("change", async (e) => {
        if (e.target.files.length > 0) {
            await handleAiFile(e.target.files[0], 'receive');
        }
    });
}

async function handleAiFile(file, type) {
    if (!file.name.match(/\.(xlsx|xls)$/i)) {
        alert("กรุณาเลือกไฟล์ Excel (.xlsx, .xls)");
        return;
    }

    showAiStatus('⏳ กำลังอัปโหลดไฟล์รับเข้า...', 'loading');

    const reader = new FileReader();
    reader.onload = async function (event) {
        const result = event.target.result;
        const base64Data = result.includes(',') ? result.split(',')[1] : result;

        try {
            const tempPath = await eel.save_temp_file(file.name, base64Data)();
            if (tempPath) {
                if (type === 'receive') {
                    aiReceiveTempPath = tempPath;
                    document.getElementById("aiReceiveFileName").innerText = file.name;
                    await previewAiReceive(tempPath);
                }
            } else {
                showAiStatus('❌ ไม่สามารถสร้างไฟล์ชั่วคราวได้', 'error');
            }
        } catch (err) {
            showAiStatus(`❌ Error: ${err.message}`, 'error');
        }
    };
    reader.readAsDataURL(file);
}

async function previewAiReceive(path) {
    showAiStatus('⏳ กำลังตรวจสอบไฟล์รับเข้า...', 'loading');
    try {
        const result = await eel.preview_receive_for_ai(path)();
        if (result.success) {
            aiDetectedBranch = result.detected_branch;
            document.getElementById("aiBranchName").innerText = result.branch_name;
            document.getElementById("aiBranchCode").innerText = "รหัสสาขา: " + result.detected_branch;
            showAiStatus('✅ ตรวจสอบไฟล์รับเข้าเรียบร้อย', 'success');
        } else {
            aiDetectedBranch = null;
            document.getElementById("aiBranchName").innerText = "ไม่พบสาขา";
            document.getElementById("aiBranchCode").innerText = "-";
            showAiStatus(`❌ ${result.message}`, 'error');
        }
    } catch (err) {
        showAiStatus(`❌ Error: ${err.message}`, 'error');
    }
}

function showAiStatus(text, type) {
    const statusMsg = document.getElementById('aiStatusMessage');
    const statusIcon = document.getElementById('aiStatusIcon');
    const statusText = document.getElementById('aiStatusText');

    statusMsg.className = 'status-message';
    statusMsg.classList.add(type);
    statusMsg.style.display = 'flex';
    // Support multiline (e.g. stock card path on second line)
    statusText.innerHTML = text.replace(/\n/g, '<br>');

    if (type === 'success') statusIcon.innerText = '✅';
    else if (type === 'error') statusIcon.innerText = '❌';
    else statusIcon.innerText = '⏳';
}

const processAiBtn = document.getElementById("processAiBtn");
if (processAiBtn) {
    processAiBtn.addEventListener("click", async () => {
        const stockFolder = aiStockFolderInput ? aiStockFolderInput.value.trim() : "";

        if (!aiReceiveTempPath) {
            showAiStatus('❌ กรุณาอัปโหลดไฟล์รับเข้าก่อน', 'error');
            return;
        }
        if (!stockFolder) {
            showAiStatus('❌ กรุณาระบุโฟลเดอร์เก็บไฟล์สต็อกการ์ด', 'error');
            return;
        }
        if (!aiDetectedBranch) {
            showAiStatus('❌ ไม่สามารถประมวลผลได้เนื่องจากไม่พบรหัสสาขาในไฟล์รับเข้า', 'error');
            return;
        }

        showAiStatus('⏳ กำลังค้นหาไฟล์และประมวลผล AI Stock... อาจใช้เวลาสักครู่', 'loading');
        document.getElementById("aiResultsTableContainer").style.display = "none";

        try {
            const result = await eel.process_ai_stock_from_desktop(aiReceiveTempPath, stockFolder, aiDetectedBranch)();
            if (result.success) {
                let statusMsg = `✅ ${result.message}`;
                if (result.stock_card_path) {
                    statusMsg += `\n📂 สต็อกการ์ด: ${result.stock_card_path}`;
                }
                showAiStatus(statusMsg, 'success');

                // Sort by Isolation Score descending
                const sortedData = (result.data || []).slice().sort((a, b) => {
                    return (b["ค่า Isolation Score"] || 0) - (a["ค่า Isolation Score"] || 0);
                });
                renderAiResults(sortedData);
            } else {
                showAiStatus(`❌ ${result.message}`, 'error');
            }
        } catch (err) {
            showAiStatus(`❌ Error: ${err.message}`, 'error');
        }
    });
}

function renderAiResults(data) {
    const tbody = document.getElementById("aiResultsTbody");
    tbody.innerHTML = "";

    if (!data || data.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" style="text-align:center; padding:15px; color:#6b7280;">ไม่มีรายการที่ผิดปกติ</td></tr>';
    } else {
        data.forEach(item => {
            const row = document.createElement("tr");
            row.style.borderBottom = "1px solid var(--border-light)";
            row.style.cursor = "pointer";
            row.addEventListener("mouseover", () => {
                if(!item["is_mismatch"]) row.style.backgroundColor = "var(--surface-alt)";
                else row.style.backgroundColor = "rgba(240, 23, 23, 0.4)";
            });
            row.addEventListener("mouseout", () => {
                if(!item["is_mismatch"]) row.style.backgroundColor = "transparent";
                else row.style.backgroundColor = "rgba(240, 23, 23, 0.3)";
            });

            if (item["is_mismatch"]) {
                row.style.backgroundColor = "rgba(240, 23, 23, 0.3)"; // Light red background for mismatch
                row.title = "จำนวน EXPORT_PIECE ไม่เท่ากับ RECEIVE_PIECE";
            }

            let html = `<td style="padding: 10px; color: var(--accent); font-weight: 500;">${item["ชื่อสินค้า"]}</td>`;
            html += `<td style="padding: 10px; text-align: right;">${item["จำนวนล่าสุดที่นำเข้าไป"]}</td>`;
            html += `<td style="padding: 10px; text-align: right;">${item["ค่า Robust Z-Score"]}</td>`;
            html += `<td style="padding: 10px; text-align: right; font-weight:bold; color:var(--accent);">${item["Expect Import"]}</td>`;

            row.innerHTML = html;
            
            row.addEventListener("click", () => {
                showAiChartModal(item);
            });
            
            tbody.appendChild(row);
        });
    }
    document.getElementById("aiResultsTableContainer").style.display = "block";
}

let aiChartInstance = null;

function showAiChartModal(item) {
    document.getElementById("aiChartProductName").innerText = item["ชื่อสินค้า"];
    
    // Set robust parameters
    const params = item["robust_params"] || {};
    document.getElementById("aiChartIQR").innerText = params.iqr ? params.iqr.toFixed(2) : "-";
    document.getElementById("aiChartMedian").innerText = params.median ? params.median.toFixed(2) : "-";
    document.getElementById("aiChartMAD").innerText = params.mad ? params.mad.toFixed(2) : "-";
    
    const history = item["history"] || [];
    
    const labels = history.map(h => h.date);
    const dataPoints = history.map(h => h.import);
    
    // Colors for points: red if outlier, else default blue
    const pointColors = history.map(h => h.is_outlier ? 'rgba(239, 68, 68, 1)' : 'rgba(79, 110, 247, 1)');
    const pointRadiuses = history.map(h => h.is_outlier ? 6 : 4);

    const ctx = document.getElementById("aiImportChart").getContext("2d");
    
    if (aiChartInstance) {
        aiChartInstance.destroy();
    }
    
    aiChartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'จำนวนการรับเข้า (Import)',
                data: dataPoints,
                borderColor: 'rgba(79, 110, 247, 0.5)',
                backgroundColor: 'rgba(79, 110, 247, 0.1)',
                borderWidth: 2,
                pointBackgroundColor: pointColors,
                pointBorderColor: pointColors,
                pointRadius: pointRadiuses,
                pointHoverRadius: 8,
                fill: true,
                tension: 0.1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: {
                    title: {
                        display: true,
                        text: 'วันที่ (Date)'
                    }
                },
                y: {
                    beginAtZero: true,
                    title: {
                        display: true,
                        text: 'จำนวนรับเข้า'
                    }
                }
            },
            plugins: {
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const index = context.dataIndex;
                            const h = history[index];
                            let lines = [`เลขที่บิล: ${h.bill || '-'}`, `รับเข้า: ${h.import}`];
                            if (h.is_outlier) {
                                lines[1] += ' (Outlier!)';
                            }
                            return lines;
                        }
                    }
                }
            }
        }
    });
    
    document.getElementById("aiChartModal").style.display = "flex";
}

function closeAiChartModal() {
    document.getElementById("aiChartModal").style.display = "none";
}
