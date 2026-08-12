// This file contains raw code snippets used by the Code tab (Page 3).
// It is auto-loaded by index.html and consumed by script.js as `CODE_TEXT`.
const CODE_TEXT = `//กรอง 0 
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

//---------------------------------------------------------------------------------------------------------------
//ลบคอลัมป์
// กำหนดลำดับคอลัมน์ที่ต้องการซ่อน (นับเริ่มจาก 0)
// 5=ผู้เบิก, 7=ผู้รับ, 9=Type, 10=ตำแหน่งเบิก, 11=ตำแหน่งรับ
const columnsToHide = [5, 7, 9, 10, 11,12,13,14];

document.querySelectorAll('tr').forEach(row => {
    const cells = row.querySelectorAll('th, td');
    columnsToHide.forEach(index => {
        if (cells[index]) {
            cells[index].style.display = 'none';
        }
    });
});

//---------------------------------------------------------------------------------------------------------------
//ปรับขนาดอักษร

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
// สั่งให้ทุกแถวกลับมาแสดงผลตามปกติ (ยกเลิกการซ่อน)
document.querySelectorAll('table tbody tr').forEach(row => {
    row.style.display = ''; 
});
//---------------------------------------------------------------------------------------------------------------
รายชื่อคนเบิก
(() => {
    const uniqueNames = new Set();
    
    // วิ่งไล่ดูทุกแถวใน tbody ของตาราง
    document.querySelectorAll('table tbody tr').forEach(row => {
        // มองหาตัวเลือก <select> ในแถว (เพื่อเช็กจำนวนตำแหน่ง)
        const dropdowns = row.querySelectorAll('select');
        
        // คอลัมน์ "ผู้เบิก" จะอยู่ก่อนหน้าคอลัมน์ "จำนวนรับ"
        // จากโครงสร้างเต็ม คอลัมน์ผู้เบิกคือคอลัมน์ที่ 6 (หรือนับย้อนจาก select ตัวแรก)
        const cells = row.querySelectorAll('td');
        if (cells.length >= 10) {
            // ดึงข้อความชื่อผู้เบิก (คอลัมน์ที่ 6 คืออินเด็กซ์ที่ 5)
            const name = cells[9].innerText.trim();
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
// แก้ไขรายชื่อและชื่อสาขาที่ต้องการตรงนี้ได้เลยครับ
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
    "ไก่แจ้":        { source: "WH", target: "WH" },

    // ===================================================
    // กลุ่มที่ 2: เบิก SP / รับ SP (หน้าร้าน/สาขา SP)
    // ===================================================
    "Sao":      { source: "SP", target: "SP" },
    "Blue":     { source: "SP", target: "SP" },
    "Pcnee":    { source: "SP", target: "SP" },
    "PET SHOP": { source: "SP", target: "SP" },
    "Dada":     { source: "SP", target: "SP" },
    "Sasa":     { source: "SP", target: "SP" },
    "ดาดา":     { source: "SP", target: "SP" }
};

// ฟังก์ชันเลือก Option โดยดูจาก Text ที่เห็นบนหน้าจอ
const selectByText = (selectElement, targetText) => {
    if (!selectElement || !targetText) return;

    // ตรวจสอบว่าเลือกตรงอยู่แล้วหรือยัง ถ้าใช่ให้ข้าม
    const currentSelectedOption = selectElement.options[selectElement.selectedIndex];
    if (currentSelectedOption && currentSelectedOption.text.trim() === targetText) {
        return;
    }
    
    // ค้นหา option ที่ตรงกัน
    const matchedOption = Array.from(selectElement.options).find(opt => opt.text.trim() === targetText);
    
    if (matchedOption) {
        selectElement.value = matchedOption.value;
        selectElement.dispatchEvent(new Event('change', { bubbles: true }));
    }
};

// วนลูปตรวจในแต่ละแถวของตาราง
document.querySelectorAll('table tbody tr').forEach(row => {
    // 1. ดึงชื่อผู้เบิกจาก Class col-ex col-emp
    const senderCell = row.querySelector('td.col-ex.col-emp');
    if (!senderCell) return;

    const senderName = senderCell.innerText.trim();

    // 2. ถ้าเจอชื่อตรงกับใน nameConfig
    if (nameConfig[senderName]) {
        const config = nameConfig[senderName];

        // 3. ดึง Dropdown โดยใช้ Class ex-stamp (เบิก) และ re-stamp (รับ) โดยตรง
        const selectSource = row.querySelector('select.ex-stamp');
        const selectTarget = row.querySelector('select.re-stamp');

        // 4. สั่งเปลี่ยนค่าตาม Config
        selectByText(selectSource, config.source);
        selectByText(selectTarget, config.target);
    }
});

//---------------------------------------------------------------------------------------------------------------
//มีรับไม่มีเบิก
document.querySelectorAll('tr[class*="drow"]').forEach(tr => {
    // ดึง dropdown สองตัวในแถว (ตัวแรก = บาร์โค้ดเบิก, ตัวที่สอง = บาร์โค้ดรับ)
    const selects = tr.querySelectorAll('select');
    
    if (selects.length >= 2) {
        const valEx = selects[0].value; // บาร์โค้ดเบิก
        const valRe = selects[1].value; // บาร์โค้ดรับ

        // เงื่อนไข: บาร์โค้ดเบิก == - เลือก - AND บาร์โค้ดรับ != - เลือก -
        const isExSelectedDefault = valEx === '- เลือก -' || valEx === '';
        const isReHasValue = valRe !== '- เลือก -' && valRe !== '';

        if (isExSelectedDefault && isReHasValue) {
            tr.style.display = ''; // แสดงแถวที่ตรงเงื่อนไข (แถวที่ 2)
        } else {
            tr.style.display = 'none'; // ซ่อนแถวที่ไม่ตรง
        }
    }
});
`;

// CODE_TEXT is exposed as a global variable for the page to consume
