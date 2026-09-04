// ==================== EVIDENCE (TAB 5) LOGIC ====================

let evImageBase64List = [];

// DOM Elements
const evImageDropzone = document.getElementById('evImageDropzone');
const evImageInput = document.getElementById('evImageInput');
const evImagePreviewContainer = document.getElementById('evImagePreviewContainer');
const evidenceUploadModal = document.getElementById('evidenceUploadModal');
const imageViewerModal = document.getElementById('imageViewerModal');
const imageViewerImg = document.getElementById('imageViewerImg');

// Modal Logic
function openManualEvidenceUpload() {
    clearEvidenceModal();
    // Pre-fill date with today
    const today = new Date().toISOString().split('T')[0];
    document.getElementById('evDate').value = today;
    document.getElementById('evBranch').value = 'K1'; // Default
    
    evidenceUploadModal.style.display = 'flex';
}

function openEvidenceUploadFromAI(productName, quantity, branch) {
    clearEvidenceModal();
    
    document.getElementById('evProductName').value = productName || '';
    document.getElementById('evQuantity').value = quantity || '';
    if (branch) {
        // Try to set branch, if invalid it might not set, so fallback is fine
        const branchSelect = document.getElementById('evBranch');
        for(let i=0; i<branchSelect.options.length; i++) {
            if(branchSelect.options[i].value === branch) {
                branchSelect.selectedIndex = i;
                break;
            }
        }
    }
    
    // Set date to today
    const today = new Date().toISOString().split('T')[0];
    document.getElementById('evDate').value = today;
    
    evidenceUploadModal.style.display = 'flex';
}

function closeEvidenceUploadModal() {
    evidenceUploadModal.style.display = 'none';
}

function clearEvidenceModal() {
    document.getElementById('evProductName').value = '';
    document.getElementById('evBranch').selectedIndex = 0;
    document.getElementById('evDate').value = '';
    document.getElementById('evQuantity').value = '';
    document.getElementById('evBarcode').value = '';
    
    evImageBase64List = [];
    evImagePreviewContainer.innerHTML = '';
}

// Image Dropzone Logic
if (evImageDropzone) {
    evImageDropzone.addEventListener('click', () => {
        evImageInput.click();
    });

    evImageDropzone.addEventListener('dragover', (e) => {
        e.preventDefault();
        evImageDropzone.classList.add('dragover');
    });

    evImageDropzone.addEventListener('dragleave', () => {
        evImageDropzone.classList.remove('dragover');
    });

    evImageDropzone.addEventListener('drop', (e) => {
        e.preventDefault();
        evImageDropzone.classList.remove('dragover');
        if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
            handleEvImages(e.dataTransfer.files);
        }
    });

    evImageInput.addEventListener('change', (e) => {
        if (e.target.files && e.target.files.length > 0) {
            handleEvImages(e.target.files);
        }
    });
}

function handleEvImages(files) {
    for (let i = 0; i < files.length; i++) {
        const file = files[i];
        if (!file.type.match('image.*')) continue;

        const reader = new FileReader();
        reader.onload = (e) => {
            const base64 = e.target.result;
            evImageBase64List.push(base64);
            
            // Render preview
            const imgContainer = document.createElement('div');
            imgContainer.style.position = 'relative';
            imgContainer.style.width = '60px';
            imgContainer.style.height = '60px';
            imgContainer.style.flexShrink = '0';
            
            const img = document.createElement('img');
            img.src = base64;
            img.style.width = '100%';
            img.style.height = '100%';
            img.style.objectFit = 'cover';
            img.style.borderRadius = '4px';
            img.style.border = '1px solid var(--border)';
            
            const removeBtn = document.createElement('div');
            removeBtn.innerHTML = '×';
            removeBtn.style.position = 'absolute';
            removeBtn.style.top = '-5px';
            removeBtn.style.right = '-5px';
            removeBtn.style.background = 'red';
            removeBtn.style.color = 'white';
            removeBtn.style.borderRadius = '50%';
            removeBtn.style.width = '16px';
            removeBtn.style.height = '16px';
            removeBtn.style.fontSize = '12px';
            removeBtn.style.display = 'flex';
            removeBtn.style.alignItems = 'center';
            removeBtn.style.justifyContent = 'center';
            removeBtn.style.cursor = 'pointer';
            
            const index = evImageBase64List.length - 1;
            removeBtn.onclick = (event) => {
                event.stopPropagation();
                evImageBase64List.splice(index, 1);
                imgContainer.remove();
                // We should ideally re-render all to keep indices correct, but for simplicity this works if we re-render
                reRenderEvPreviews();
            };
            
            imgContainer.appendChild(img);
            imgContainer.appendChild(removeBtn);
            evImagePreviewContainer.appendChild(imgContainer);
        };
        reader.readAsDataURL(file);
    }
}

function reRenderEvPreviews() {
    evImagePreviewContainer.innerHTML = '';
    const currentList = [...evImageBase64List];
    evImageBase64List = [];
    
    currentList.forEach(b64 => {
        // Just mock a file read to reuse logic
        const imgContainer = document.createElement('div');
        imgContainer.style.position = 'relative';
        imgContainer.style.width = '60px';
        imgContainer.style.height = '60px';
        imgContainer.style.flexShrink = '0';
        
        const img = document.createElement('img');
        img.src = b64;
        img.style.width = '100%';
        img.style.height = '100%';
        img.style.objectFit = 'cover';
        img.style.borderRadius = '4px';
        img.style.border = '1px solid var(--border)';
        
        const removeBtn = document.createElement('div');
        removeBtn.innerHTML = '×';
        removeBtn.style.position = 'absolute';
        removeBtn.style.top = '-5px';
        removeBtn.style.right = '-5px';
        removeBtn.style.background = 'red';
        removeBtn.style.color = 'white';
        removeBtn.style.borderRadius = '50%';
        removeBtn.style.width = '16px';
        removeBtn.style.height = '16px';
        removeBtn.style.fontSize = '12px';
        removeBtn.style.display = 'flex';
        removeBtn.style.alignItems = 'center';
        removeBtn.style.justifyContent = 'center';
        removeBtn.style.cursor = 'pointer';
        
        const index = evImageBase64List.length;
        evImageBase64List.push(b64); // Add back
        
        removeBtn.onclick = (event) => {
            event.stopPropagation();
            evImageBase64List.splice(index, 1);
            reRenderEvPreviews();
        };
        
        imgContainer.appendChild(img);
        imgContainer.appendChild(removeBtn);
        evImagePreviewContainer.appendChild(imgContainer);
    });
}

async function submitEvidence() {
    const productName = document.getElementById('evProductName').value.trim();
    const branch = document.getElementById('evBranch').value;
    const dateStr = document.getElementById('evDate').value;
    const quantity = document.getElementById('evQuantity').value;
    const barcode = document.getElementById('evBarcode').value.trim();
    const btn = document.getElementById('btnSubmitEvidence');
    
    if (!productName) {
        alert("กรุณาระบุชื่อสินค้า");
        return;
    }
    if (!dateStr) {
        alert("กรุณาระบุวันที่");
        return;
    }
    
    btn.disabled = true;
    btn.innerText = "กำลังบันทึก...";
    
    try {
        const res = await eel.save_evidence(branch, dateStr, productName, quantity, barcode, evImageBase64List)();
        if (res.success) {
            alert("บันทึกหลักฐานเรียบร้อยแล้ว");
            closeEvidenceUploadModal();
            // Refresh tree if we are on the evidence tab
            if (document.getElementById('tab-evidence').classList.contains('active-tab')) {
                loadEvidenceTree();
                // Optionally reload current day if we just added to it
                if (window.currentEvidenceBranch === branch && window.currentEvidenceDate === dateStr) {
                    loadEvidenceForDay(branch, dateStr);
                }
            }
        } else {
            alert(res.message);
        }
    } catch (e) {
        alert("Error: " + e.message);
    } finally {
        btn.disabled = false;
        btn.innerText = "💾 บันทึกหลักฐาน";
    }
}

// Tree Logic
let currentEvidenceBranch = null;
let currentEvidenceDate = null;

async function loadEvidenceTree() {
    const container = document.getElementById('evidenceTreeContainer');
    container.innerHTML = '<div style="color: var(--text-muted); text-align: center; margin-top: 20px;">กำลังโหลด...</div>';
    
    try {
        const res = await eel.get_evidence_tree()();
        if (res.success && Object.keys(res.tree).length > 0) {
            container.innerHTML = '';
            const tree = res.tree;
            
            // Render tree
            for (const branch in tree) {
                const branchDiv = document.createElement('div');
                branchDiv.style.marginBottom = '8px';
                
                const branchHeader = document.createElement('div');
                branchHeader.style.fontWeight = '700';
                branchHeader.style.padding = '6px';
                branchHeader.style.backgroundColor = 'var(--surface-alt)';
                branchHeader.style.borderRadius = '4px';
                branchHeader.style.cursor = 'pointer';
                branchHeader.innerText = `🏢 สาขา ${branch}`;
                
                const monthsContainer = document.createElement('div');
                monthsContainer.style.paddingLeft = '16px';
                monthsContainer.style.marginTop = '4px';
                
                // Toggle logic
                branchHeader.onclick = () => {
                    monthsContainer.style.display = monthsContainer.style.display === 'none' ? 'block' : 'none';
                };
                
                for (const month in tree[branch]) {
                    const monthDiv = document.createElement('div');
                    monthDiv.style.marginBottom = '4px';
                    
                    const monthHeader = document.createElement('div');
                    monthHeader.style.fontWeight = '600';
                    monthHeader.style.padding = '4px';
                    monthHeader.style.color = 'var(--accent)';
                    monthHeader.style.cursor = 'pointer';
                    // Convert 2026-09 to Year-Month text
                    monthHeader.innerText = `📅 ${month}`;
                    
                    const daysContainer = document.createElement('div');
                    daysContainer.style.paddingLeft = '16px';
                    
                    monthHeader.onclick = () => {
                        daysContainer.style.display = daysContainer.style.display === 'none' ? 'block' : 'none';
                    };
                    
                    const days = tree[branch][month];
                    days.forEach(day => {
                        const dayDiv = document.createElement('div');
                        dayDiv.style.padding = '4px 8px';
                        dayDiv.style.cursor = 'pointer';
                        dayDiv.style.borderRadius = '4px';
                        dayDiv.innerText = `📄 ${day}`;
                        
                        dayDiv.onmouseover = () => {
                            if (window.currentEvidenceBranch !== branch || window.currentEvidenceDate !== day) {
                                dayDiv.style.backgroundColor = 'var(--border-light)';
                            }
                        };
                        dayDiv.onmouseout = () => {
                            if (window.currentEvidenceBranch !== branch || window.currentEvidenceDate !== day) {
                                dayDiv.style.backgroundColor = 'transparent';
                            }
                        };
                        
                        dayDiv.onclick = () => {
                            // Reset all highlights
                            container.querySelectorAll('.day-item').forEach(el => {
                                el.style.backgroundColor = 'transparent';
                                el.style.color = 'var(--text)';
                                el.style.fontWeight = 'normal';
                            });
                            
                            dayDiv.classList.add('day-item');
                            dayDiv.style.backgroundColor = 'var(--primary)';
                            dayDiv.style.color = 'white';
                            dayDiv.style.fontWeight = 'bold';
                            
                            window.currentEvidenceBranch = branch;
                            window.currentEvidenceDate = day;
                            
                            loadEvidenceForDay(branch, day);
                        };
                        
                        dayDiv.classList.add('day-item');
                        daysContainer.appendChild(dayDiv);
                    });
                    
                    monthDiv.appendChild(monthHeader);
                    monthDiv.appendChild(daysContainer);
                    monthsContainer.appendChild(monthDiv);
                }
                
                branchDiv.appendChild(branchHeader);
                branchDiv.appendChild(monthsContainer);
                container.appendChild(branchDiv);
            }
        } else {
            container.innerHTML = '<div style="color: var(--text-muted); text-align: center; margin-top: 20px;">ยังไม่มีข้อมูลหลักฐาน</div>';
        }
    } catch (e) {
        container.innerHTML = `<div style="color: red; text-align: center; margin-top: 20px;">Error: ${e.message}</div>`;
    }
}

async function loadEvidenceForDay(branch, dateStr) {
    document.getElementById('evidenceCurrentDate').innerText = `(${branch} - ${dateStr})`;
    const container = document.getElementById('evidenceListContainer');
    container.innerHTML = '<div style="text-align: center; color: var(--text-muted); padding: 40px;">กำลังโหลดข้อมูล...</div>';
    
    try {
        const res = await eel.get_evidence_by_date(branch, dateStr)();
        if (res.success && res.records && res.records.length > 0) {
            container.innerHTML = '';
            
            res.records.forEach(record => {
                const card = document.createElement('div');
                card.style.background = 'var(--surface)';
                card.style.border = '1px solid var(--border)';
                card.style.borderRadius = 'var(--radius)';
                card.style.padding = '16px';
                card.style.display = 'flex';
                card.style.flexDirection = 'column';
                card.style.gap = '12px';
                
                let headerHtml = `
                    <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                        <div>
                            <h3 style="margin: 0 0 4px 0; font-size: 15px; color: var(--accent);">${record.product_name}</h3>
                            <div style="font-size: 12px; color: var(--text-muted);">
                                ${record.barcode ? `<span>บาร์โค้ด: ${record.barcode}</span> | ` : ''}
                                <span>จำนวน: <strong style="color: var(--text);">${record.quantity || '-'}</strong></span>
                            </div>
                        </div>
                        <button onclick="deleteEvidenceRecord('${record.id}', '${branch}', '${dateStr}')" style="background: none; border: none; color: #ef4444; cursor: pointer; font-size: 14px; padding: 4px;" title="ลบข้อมูล">🗑️</button>
                    </div>
                `;
                
                let imagesHtml = '';
                if (record.images && record.images.length > 0) {
                    imagesHtml = `<div style="display: flex; gap: 10px; flex-wrap: wrap;">`;
                    record.images.forEach(imgPath => {
                        // We use a trick: the python eel server exposes the whole directory if we use the right path.
                        // Wait, eel usually serves from 'web' folder. If evidence is outside 'web', we might need to fetch it via eel function or serve it differently.
                        // Actually, if we just use a relative path, Eel might not serve it if it's outside the web folder.
                        // For a desktop app, we can use an absolute file:// URI, but we need the absolute path.
                        // Let's create an eel function to get the absolute path or just send the file path via base64 for simplicity if needed.
                        // BUT, Eel handles static files in 'web'. So if we created 'evidence' inside 'web', it would work.
                        // Our python script created it in os.path.dirname(__file__)/evidence. We need a way to view it.
                        // Let's modify the image source to call an eel function that returns base64, or use python's exposed folder.
                        // Actually, we can just use the absolute path in modern browsers if it's local: 'file://' + absolute_path
                        // Wait, to be safe, I'll update Python later to send absolute paths or base64. Let's assume we can fetch image via eel.
                        // To keep it simple, we'll request the image content via Eel.
                        
                        // Let's create a temporary img element
                        imagesHtml += `
                            <div style="width: 80px; height: 80px; border-radius: 6px; overflow: hidden; border: 1px solid var(--border-light); cursor: pointer;" onclick="openImageViewer('${imgPath}')">
                                <img class="ev-lazy-img" data-path="${imgPath}" src="" style="width: 100%; height: 100%; object-fit: cover;" alt="Loading...">
                            </div>
                        `;
                    });
                    imagesHtml += `</div>`;
                } else {
                    imagesHtml = `<div style="font-size: 12px; color: var(--text-muted); font-style: italic;">ไม่มีรูปภาพ</div>`;
                }
                
                card.innerHTML = headerHtml + imagesHtml;
                container.appendChild(card);
            });
            
            // Load images lazily via eel
            document.querySelectorAll('.ev-lazy-img').forEach(async (img) => {
                const path = img.getAttribute('data-path');
                try {
                    const b64 = await eel.get_image_base64(path)();
                    if (b64) {
                        img.src = b64;
                    } else {
                        img.alt = 'Image not found';
                    }
                } catch (e) {
                    console.error("Error loading image", e);
                }
            });
            
        } else {
            container.innerHTML = '<div style="text-align: center; color: var(--text-muted); padding: 40px;">ไม่พบข้อมูลสำหรับวันนี้</div>';
        }
    } catch (e) {
        container.innerHTML = `<div style="color: red; text-align: center; padding: 40px;">Error: ${e.message}</div>`;
    }
}

async function deleteEvidenceRecord(recordId, branch, dateStr) {
    if (confirm('คุณต้องการลบหลักฐานรายการนี้ใช่หรือไม่?')) {
        try {
            const res = await eel.delete_evidence(recordId)();
            if (res.success) {
                // Refresh list and tree
                loadEvidenceForDay(branch, dateStr);
                loadEvidenceTree();
            } else {
                alert(res.message);
            }
        } catch (e) {
            alert('Error: ' + e.message);
        }
    }
}

async function openImageViewer(path) {
    imageViewerModal.style.display = 'flex';
    imageViewerImg.src = '';
    try {
        const b64 = await eel.get_image_base64(path)();
        if (b64) {
            imageViewerImg.src = b64;
        }
    } catch (e) {
        console.error(e);
    }
}

function closeImageViewer() {
    imageViewerModal.style.display = 'none';
    imageViewerImg.src = '';
}

// Ensure the tree loads when switching to the evidence tab
document.addEventListener('DOMContentLoaded', () => {
    // Override the global switchTab slightly to hook into it, or just listen for clicks
    const btn = document.getElementById('tabBtnEvidence');
    if (btn) {
        btn.addEventListener('click', () => {
            if (document.getElementById('evidenceTreeContainer').innerHTML.includes('กำลังโหลด...')) {
                loadEvidenceTree();
            }
        });
    }
});
