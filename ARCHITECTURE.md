# 🏗️ Architecture Guide - วิธีการทำงานของระบบ

## 📐 System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         USER'S COMPUTER                              │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │                    WEB BROWSER                                 │ │
│  │  ┌──────────────────────────────────────────────────────────┐ │ │
│  │  │  index.html (HTML/CSS)                                   │ │ │
│  │  │  ┌────────────────────────────────────────────────────┐ │ │ │
│  │  │  │ ฝั่งซ้าย (Left)        │  ฝั่งขวา (Right)        │ │ │ │
│  │  │  │ - Branch Display     │ - Path Input Fields    │ │ │ │
│  │  │  │ - Dropzone          │ - LocalStorage Save    │ │ │ │
│  │  │  │ - Status Message    │ - Config Manager      │ │ │ │
│  │  │  └────────────────────────────────────────────────────┘ │ │ │
│  │  │                                                          │ │ │
│  │  │  script.js (JavaScript)                                 │ │ │
│  │  │  ├─ Drag & Drop Handler                                │ │ │
│  │  │  ├─ LocalStorage Manager                               │ │ │
│  │  │  ├─ API Communication (Fetch)                          │ │ │
│  │  │  └─ UI State Manager                                   │ │ │
│  │  └──────────────────────────────────────────────────────────┘ │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                            ▲                                        │
│                            │                                        │
│                    HTTP Request/Response                            │
│                    (Fetch API)                                      │
│                            │                                        │
│                            ▼                                        │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │                    FastAPI SERVER                              │ │
│  │  (python app.py)                                              │ │
│  │  ┌──────────────────────────────────────────────────────────┐ │ │
│  │  │  /upload Endpoint                                       │ │ │
│  │  │  ├─ Receive: File + PathsConfig (JSON)                │ │ │
│  │  │  ├─ Process:                                          │ │ │
│  │  │  │  ├─ Read Excel File                               │ │ │
│  │  │  │  ├─ Merge Paths (user + default)                 │ │ │
│  │  │  │  ├─ Detect Branch (11/21/31/41/51/SP)           │ │ │
│  │  │  │  ├─ Filter Data (SP vs WH)                       │ │ │
│  │  │  │  └─ Save Files to User-defined Paths             │ │ │
│  │  │  └─ Response: JSON {status, message, files}          │ │ │
│  │  │                                                       │ │ │
│  │  │  /health Endpoint (ตรวจสอบสถานะ)                    │ │ │
│  │  │  /config/default-paths Endpoint                      │ │ │
│  │  └──────────────────────────────────────────────────────┘ │ │
│  │                                                            │ │
│  │  CORS Enabled ✅ (อนุญาตให้ Frontend เรียก)               │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                            ▲                                        │
│                            │                                        │
│                    File I/O Operations                              │
│                    (Read/Write .txt files)                          │
│                            │                                        │
│                            ▼                                        │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │              FILE SYSTEM (Local Disk)                          │ │
│  │  ┌──────────────────────────────────────────────────────────┐ │ │
│  │  │  C:\Users\USER\Desktop\                                │ │ │
│  │  │  ├─ K1\     (Branch 11 - SP)                           │ │ │
│  │  │  ├─ 1100\   (Branch 11 - WH)                           │ │ │
│  │  │  ├─ K2\     (Branch 21 - SP)                           │ │ │
│  │  │  ├─ 2100\   (Branch 21 - WH)                           │ │ │
│  │  │  ├─ ...                                                │ │ │
│  │  │  └─ SP00\   (Main Warehouse)                           │ │ │
│  │  │                                                        │ │ │
│  │  │  Output: K1-SP-17-5-69 รับ.txt                        │ │ │
│  │  │          K1-WH-17-5-69 รับ.txt                        │ │ │
│  │  └──────────────────────────────────────────────────────┘ │ │
│  └────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 🔄 Request/Response Flow

### Sequence Diagram

```
Browser                Frontend              Backend              FileSystem
   │                  (script.js)           (app.py)              (Disk)
   │                      │                    │                     │
   ├──Drag File ──────────┤                    │                     │
   │                      │                    │                     │
   │  ◄─Set Branch Name───│                    │                     │
   │                      │                    │                     │
   │  ◄─Get Paths from────│                    │                     │
   │    LocalStorage      │                    │                     │
   │                      │                    │                     │
   │  Upload File ────────┤──POST /upload──────┤                     │
   │  + PathsConfig       │  (FormData)        │                     │
   │                      │                    ├─Read .xlsx──────────┤
   │                      │                    │◄──File Data─────────┤
   │                      │                    │                     │
   │                      │                    ├─Process Data────────│
   │                      │                    │  - Detect Branch    │
   │                      │                    │  - Merge Paths      │
   │                      │                    │  - Filter Rows      │
   │                      │                    │                     │
   │                      │                    ├─Save .txt files────┤
   │                      │                    │  to Paths           │
   │                      │                    │  ┌─────────────────┤
   │                      │                    │  │ K1-SP.txt       │
   │                      │                    │  │ K1-WH.txt       │
   │                      │                    │  └─────────────────┤
   │                      │                    │                     │
   │  ◄──Response JSON────┤◄──200 OK──────────┤                     │
   │  {                   │  {status: success} │                     │
   │   success: true,     │                    │                     │
   │   message: "✅...",  │                    │                     │
   │   files_saved: [..]} │                    │                     │
   │                      │                    │                     │
   │ Display Success ◄────┤                    │                     │
   │ Message              │                    │                     │
   │                      │                    │                     │
```

---

## 💾 LocalStorage Management

### Save Workflow
```
User Input          JavaScript            Browser Memory
   │                    │                      │
   └─ Gathers all ─────→ getCurrentPathsConfig() → Creates JS Object
     Path values
                    ┌────────────────────────────┐
                    │ {                          │
                    │   "11": "C:\...\K1",       │
                    │   "11_00": "C:\...\1100",  │
                    │   "21": "C:\...\K2",       │
                    │   ...                      │
                    │ }                          │
                    └────────────────────────────┘
                           │
                           ├─→ JSON.stringify()
                           │
                           ├─→ localStorage.setItem('pathsConfig', JSON)
                           │
                           ▼
                    Browser Local Storage
                    (Persistent)
```

### Load Workflow
```
Browser Opens              JavaScript           UI Elements
   │                           │                     │
   └─Page Loaded ───→ loadPathsFromLocalStorage()    │
                              │                      │
                              ├─ localStorage.getItem('pathsConfig')
                              │                      │
                              ├─ JSON.parse()        │
                              │                      │
                              ├─ ForEach Path ───────┤─ Populate Input
                              │  input.value = path   │  Fields
                              │
                              └─ User sees
                                 saved values
```

---

## 🔧 Data Processing Pipeline

```
Input: Excel File (.xlsx)
         ↓
    ┌───────────────┐
    │ Read File     │ ← pandas.read_excel()
    └───────┬───────┘
            ↓
    ┌───────────────┐
    │ Validate Data │ ← Check for errors
    │ - ReBplus col │   - Check for '0' values
    │ - Type col    │   - Handle NaN
    └───────┬───────┘
            ↓
    ┌───────────────────────────┐
    │ Detect Branch             │ ← Extract 2nd code from ReBplus
    │ (11/21/31/41/51/SP)       │   Check if in branches list
    └───────┬───────────────────┘
            ↓
    ┌───────────────────────────┐
    │ Merge Paths               │ ← DEFAULT_PATHS ← User Paths
    │ - User input override     │   (User takes priority)
    │ - Default fallback        │
    └───────┬───────────────────┘
            ↓
    ┌───────────────────────────┐
    │ Filter Data - SP          │ ← Type==1 AND Branch Code matches
    │ (Front Store)             │
    └───────┬───────────────────┘
            ↓
    ┌───────────────────────────┐
    │ Filter Data - WH          │ ← Type==2 AND Code == '00'
    │ (Warehouse)               │
    └───────┬───────────────────┘
            ↓
    ┌───────────────────────────┐
    │ Generate Filename         │ ← {Branch}-{Type}-{Date}.txt
    │ with Date Suffix          │   e.g., K1-SP-17-5-69 รับ.txt
    └───────┬───────────────────┘
            ↓
    ┌───────────────────────────┐
    │ Ensure Dir Exists         │ ← Create folder if missing
    └───────┬───────────────────┘
            ↓
    ┌───────────────────────────┐
    │ Write .txt Files          │ ← One line per ReBplus value
    │ - SP File                 │
    │ - WH File (if data)       │
    └───────┬───────────────────┘
            ↓
Output: .txt Files in User Paths
```

---

## 🔐 Security & Data Flow

### 1. User Path Validation
```
User Input Path
    ↓
Validation:
├─ Path exists or can be created?
├─ Has write permission?
└─ Is it a valid Windows path?
    ↓
✅ Valid → Use it
❌ Invalid → Show error, use default
```

### 2. File Safety
```
├─ Temporary File Storage
│  ├─ Upload to /tmp/ first
│  └─ Delete after processing
│
├─ Excel File Validation
│  ├─ Check file type (.xlsx/.xls)
│  ├─ Check required columns
│  └─ Validate data integrity
│
└─ Output Files
   ├─ Written with UTF-8 encoding
   ├─ Overwrite existing if same name
   └─ Safe file operations
```

---

## 🌐 API Endpoints

### POST /upload
```
Request:
├─ Content-Type: multipart/form-data
├─ Body:
│  ├─ file: <Excel file>
│  └─ paths_config: '{"11": "C:\\...", ...}'
│
Response (Success):
├─ Status: 200
├─ Body:
│  {
│    "success": true,
│    "message": "✅ ประมวลผลสำเร็จ!",
│    "detected_branch": "11",
│    "branch_name": "K1",
│    "files_saved": [
│      "🏪 เซฟหน้าร้าน: K1-SP-17-5-69 รับ.txt (15 แถว)",
│      "🏢 เซฟโกดัง: K1-WH-17-5-69 รับ.txt (5 แถว)"
│    ]
│  }
│
Response (Error):
├─ Status: 400
├─ Body:
│  {
│    "success": false,
│    "message": "❌ ตรวจพบค่า '0' ในคอลัมน์...",
│    "detected_branch": null
│  }
```

### GET /health
```
Request: 
└─ No parameters

Response:
├─ Status: 200
└─ Body:
   {
     "status": "ok",
     "message": "Excel Processor API is running"
   }
```

---

## 📊 Configuration Priority

```
When determining which Path to use:

1. User-provided Path (from Frontend Input)
   ├─ Highest Priority
   ├─ Stored in Frontend Form
   └─ Sent with API request

2. LocalStorage Path
   ├─ Saved from previous use
   └─ Loaded on page open

3. DEFAULT_PATHS (Hardcoded)
   ├─ If neither above exist
   └─ Built into app.py

Selection Logic:
If (User Input provided) → Use it
Else if (LocalStorage exists) → Use it
Else → Use DEFAULT_PATHS
```

---

## 🎯 Component Interactions

```
┌──────────────────────┐
│   index.html         │
│   (User Interface)   │
└──────┬───────────────┘
       │
       ├─ Uses: CSS for styling
       │
       └─ Loads: script.js
            │
            ├─ Event Listeners
            │  ├─ Drop Zone
            │  ├─ File Input
            │  └─ Save Button
            │
            ├─ LocalStorage API
            │  ├─ Save paths
            │  └─ Load paths
            │
            └─ Fetch API
               ├─ POST /upload
               └─ Handles responses
                   │
                   ├─ Success → Display results
                   └─ Error → Show error message
                   
       ├─ Receives: app.py responses
       │
       └─ Updates: UI with results
```

---

## 🚀 Performance Flow

```
Timeline for Processing:
│
├─ 0ms     : User drops file
├─ 10ms    : File loaded to memory
├─ 50ms    : script.js prepares FormData
├─ 100ms   : HTTP request sent to Backend
│
├─ 150ms   : Backend receives request
├─ 200ms   : Excel file read (pandas)
├─ 250ms   : Branch detection
├─ 300ms   : Data filtering & processing
├─ 400ms   : Files written to disk
│
├─ 450ms   : Response prepared (JSON)
├─ 500ms   : Response sent to Frontend
│
├─ 550ms   : Frontend receives response
├─ 600ms   : UI updated with results
└─ 650ms   : User sees success/error ✅
    
Total: ~500ms for small files
       ~2-5s for large files
```

---

## ✅ Reliability & Error Handling

```
Error Scenarios Handled:

1. File Errors
   ├─ Wrong file type → Show error
   ├─ Corrupted file → Show error
   └─ Missing columns → Show error

2. Path Errors
   ├─ Invalid path → Show error
   ├─ No write permission → Show error
   └─ Create if not exist → Auto-create

3. Data Errors
   ├─ Missing required columns → Skip processing
   ├─ Invalid data format → Show details
   └─ No matching rows → Show warning

4. Network Errors
   ├─ Connection timeout → Show error
   ├─ Server error → Show error
   └─ Retry possible → Suggest retry

5. Browser Errors
   ├─ LocalStorage full → Clear old data
   ├─ CORS blocked → Show help
   └─ JavaScript error → Console logs
```

---

**ระบบเสร็จสิ้น! 🎉 พร้อมใช้งาน**
