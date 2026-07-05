// This file contains raw code snippets used by the Code tab (Page 3).
// It is auto-loaded by index.html and consumed by script.js as `CODE_TEXT`.
const CODE_TEXT = `//ลบแถว 0
document.querySelectorAll('tr').forEach(row => {
    // หา span ที่มีคลาส font-bold ภายในแถวนั้น
    const span = row.querySelector('span.font-bold');
    
    if (span) {
        // ดึงข้อความออกมา แล้วตัดช่องว่างออก
        const value = span.innerText.trim();
        
        // ถ้าค่าเป็น "0" ให้ซ่อนทั้งแถว
        if (value === "0") {
            row.style.display = 'none';
        } else {
            // ถ้าไม่ใช่ 0 ให้โชว์ไว้ (เผื่อกรณีรันซ้ำ)
            row.style.display = '';
        }
    }
});

// กำหนดลำดับคอลัมน์ที่ต้องการซ่อน (นับเริ่มจาก 0)
// 5=ผู้เบิก, 7=ผู้รับ, 9=Type, 10=ตำแหน่งเบิก, 11=ตำแหน่งรับ
const columnsToHide = [5, 7, 9, 10, 11];

document.querySelectorAll('tr').forEach(row => {
    const cells = row.querySelectorAll('th, td');
    columnsToHide.forEach(index => {
        if (cells[index]) {
            cells[index].style.display = 'none';
        }
    });
});

// 1. ขยายขนาดตัวอักษรในตารางทั้งหมด (ปรับเลข 20px ได้ตามต้องการ)
document.querySelectorAll('table, th, td, span').forEach(el => {
    el.style.fontSize = '20px'; 
    el.style.lineHeight = 'normal'; // ปรับระยะบรรทัดให้พอดี
});

// 2. ขยายขนาดช่อง Input (ถ้ามีตัวเลขในช่องที่อยากให้ชัดขึ้น)
document.querySelectorAll('input').forEach(input => {
    input.style.fontSize = '20px';
    input.style.width = 'auto'; // ให้ช่องขยายตามขนาดตัวเลข
});


//---------------------------------------------------------------------------------------------------------------
// ยกเลิกการซ่อน
document.querySelectorAll('table tbody tr').forEach(row => {
    row.style.display = ''; 
});
//---------------------------------------------------------------------------------------------------------------
//รายชื่อคนเบิก
(function() {
    const uniqueNames = new Set();
    
    // วิ่งไล่ดูทุกแถวใน tbody ของตาราง
    document.querySelectorAll('table tbody tr').forEach(row => {
        // มองหาตัวเลือก <select> ในแถว (เพื่อเช็กจำนวนตำแหน่ง)
        const dropdowns = row.querySelectorAll('select');
        
        // คอลัมน์ "ผู้เบิก" จะอยู่ก่อนหน้าคอลัมน์ "จำนวนรับ"
        // จากโครงสร้างเต็ม คอลัมน์ผู้เบิกคือคอลัมน์ที่ 6 (หรือนับย้อนจาก select ตัวแรก)
        const cells = row.querySelectorAll('td');
        if (cells.length >= 6) {
            // ดึงข้อความชื่อผู้เบิก (คอลัมน์ที่ 6 คืออินเด็กซ์ที่ 5)
            const name = cells[5].innerText.trim();
            if (name) {
                uniqueNames.add(name);
            }
        }
    });

    // แสดงผลลัพธ์ออกมาในคอนโซล
    console.log("=== รายชื่อผู้เบิกทั้งหมด (ไม่ซ้ำกัน) ===");
    console.log(Array.from(uniqueNames));
})();
//---------------------------------------------------------------------------------------------------------------
// แก้ไขรายชื่อและชื่อสาขาที่ต้องการ
const nameConfig = {
    // ===================================================
    // กลุ่มที่ 1: เบิก WH / รับ WH (คลังสินค้าหลัก)
    // ===================================================
    "Noh":       { source: "WH", target: "WH" },
    "Hah":       { source: "WH", target: "WH" },
    "You191":    { source: "WH", target: "WH" },
    "Hafisi191": { source: "WH", target: "WH" },
    "Moh31":     { source: "WH", target: "WH" },
    "ลาโก้":     { source: "WH", target: "WH" },
    "ดา":        { source: "WH", target: "WH" },

    // ===================================================
    // กลุ่มที่ 2: เบิก SP / รับ SP (หน้าร้าน/สาขา SP)
    // ===================================================
    "Sao":      { source: "SP", target: "SP" },
    "Blue":     { source: "SP", target: "SP" },
    "Pcnee":    { source: "SP", target: "SP" },
    "PET SHOP": { source: "SP", target: "SP" },
    "Dada":     { source: "SP", target: "SP" },
    "Sasa":     { source: "SP", target: "SP" }
};

document.querySelectorAll('table tbody tr').forEach(row => {
    // 1. วิ่งหาช่องชื่อผู้เบิกในแถว
    let foundName = null;
    row.querySelectorAll('td').forEach(td => {
        const currentText = td.innerText.trim();
        if (nameConfig[currentText]) {
            foundName = currentText;
        }
    });
    
    // 2. ถ้าเจอชื่อที่ตรงกับที่เราตั้งค่าไว้
    if (foundName) {
        const config = nameConfig[foundName];
        const dropdowns = row.querySelectorAll('select');
        
        // ตรวจสอบ Dropdown 2 ตัวสุดท้ายของแถว (ตำแหน่งเบิก และ ตำแหน่งรับ)
        if (dropdowns.length >= 2) {
            const selectSource = dropdowns[dropdowns.length - 2]; // ช่องตำแหน่งเบิก
            const selectTarget = dropdowns[dropdowns.length - 1]; // ช่องตำแหน่งรับ
            
            // ฟังก์ชันพิเศษ: วิ่งหาตัวเลือกจากตัวหนังสือที่มองเห็น (Visible Text)
            const selectByText = (selectElement, targetText) => {
                if (!selectElement) return;

                // ตรวจสอบเงื่อนไขเพิ่มเติม: ถ้าค่าที่เลือกอยู่ในปัจจุบัน (Text ของ Option ที่เลือกอยู่) 
                // ตรงกับ targetText อยู่แล้ว... ให้ข้ามไปเลย ไม่ต้องกดเลือกซ้ำ
                const currentSelectedOption = selectElement.options[selectElement.selectedIndex];
                if (currentSelectedOption && currentSelectedOption.text.trim() === targetText) {
                    // console.log(\`ข้ามการแก้ไข: ตัวเลือกเป็น "\${targetText}" อยู่แล้ว\`);
                    return; 
                }
                
                // ค้นหา option ที่มีตัวหนังสือตรงกับที่เราต้องการ
                const matchedOption = Array.from(selectElement.options).find(opt => opt.text.trim() === targetText);
                
                if (matchedOption) {
                    selectElement.value = matchedOption.value; // ดึงค่า value จริงๆ ของระบบมาใส่ให้
                    selectElement.dispatchEvent(new Event('change', { bubbles: true })); // สั่งอัปเดตหน้าเว็บ
                } else {
                    console.log(\`ไม่พบตัวเลือกที่เขียนว่า "\${targetText}" ใน Dropdown นี้\`);
                }
            };
            
            // สั่งเปลี่ยนค่าตามที่เราแมปไว้ด้านบน (ระบบจะเช็กเงื่อนไขข้างในก่อนเปลี่ยน)
            selectByText(selectSource, config.source);
            selectByText(selectTarget, config.target);
        }
    }
});
`;

// CODE_TEXT is exposed as a global variable for the page to consume
