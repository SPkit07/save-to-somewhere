"""
FastAPI Backend สำหรับ Excel File Processor (Modular Architecture)
รับไฟล์ Excel และการตั้งค่า Path จากหน้าเว็บ

โครงสร้าง:
- config.py: Configuration management
- logger.py: Logging system
- models.py: Pydantic request/response models
- processors.py: Business logic (Excel processing)
"""

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import json
import tempfile
import os
import traceback
from typing import Dict, Optional

# Import from modular components
from config import (
    SERVER_HOST, SERVER_PORT, RELOAD,
    CORS_ORIGINS, BRANCH_NAMES, DEFAULT_PATHS,
    API_VERSION
)
from logger import setup_logger
from models import ProcessFileResponse, HealthCheckResponse, ConfigResponse
from processors import process_excel_file

# ==================== LOGGER SETUP ====================
logger = setup_logger(__name__)

# ==================== INITIALIZE FASTAPI ====================
app = FastAPI(
    title="Excel Processor API",
    version=API_VERSION,
    description="Backend server for Excel file processing with branch detection"
)

# ==================== CORS CONFIGURATION ====================
app.add_middleware(
    CORSMiddleware,
    allow_origins=[CORS_ORIGINS] if isinstance(CORS_ORIGINS, str) else CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger.info(f"CORS enabled for origins: {CORS_ORIGINS}")


# ==================== GLOBAL EXCEPTION HANDLER ====================
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Handle all unhandled exceptions globally"""
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "message": f"❌ Server Error: {str(exc)}",
            "error_details": traceback.format_exc()
        }
    )


# ==================== LIFECYCLE EVENTS ====================
@app.on_event("startup")
async def startup_event():
    """Called when server starts"""
    logger.info("=" * 50)
    logger.info("Excel Processor API Starting...")
    logger.info(f"Server: {SERVER_HOST}:{SERVER_PORT}")
    logger.info(f"Reload mode: {RELOAD}")
    logger.info("=" * 50)


@app.on_event("shutdown")
async def shutdown_event():
    """Called when server stops"""
    logger.info("Excel Processor API Shutting down...")


# ==================== API ENDPOINTS ====================
@app.get("/health", response_model=HealthCheckResponse)
def health_check() -> HealthCheckResponse:
    """
    ตรวจสอบสถานะ API
    
    Returns:
        HealthCheckResponse: Status, message, and version
    """
    logger.info("Health check requested")
    return HealthCheckResponse(
        status="ok",
        message="Excel Processor API is running",
        version=API_VERSION
    )


@app.get("/config/default-paths", response_model=ConfigResponse)
def get_default_paths() -> ConfigResponse:
    """
    ดึงการตั้งค่า Paths
    
    ⚠️ ไม่มีค่า Path เริ่มต้น - ผู้ใช้ต้องระบุ Path เองทุกครั้ง
    
    Returns:
        ConfigResponse: Branches information (paths will be empty - user must provide)
    """
    logger.debug("Fetching paths configuration")
    logger.warning("No default paths configured. Users must provide paths explicitly.")
    return ConfigResponse(
        paths=DEFAULT_PATHS,  # ✓ Empty - users must specify
        branches=BRANCH_NAMES
    )


@app.get("/info")
def get_info() -> Dict:
    """
    ดึงข้อมูลระบบ
    
    Returns:
        Dict: System information
    """
    logger.debug("Fetching system information")
    return {
        "api_name": "Excel Processor API",
        "version": API_VERSION,
        "status": "running",
        "branches": BRANCH_NAMES,
        "max_file_size_mb": 50,
        "supported_formats": [".xlsx", ".xls"]
    }


@app.post("/upload", response_model=ProcessFileResponse)
async def upload_file(
    file: UploadFile = File(...),
    paths_config: str = Form(...)
) -> ProcessFileResponse:
    """
    รับไฟล์ Excel และการตั้งค่า Path แล้วประมวลผล
    
    ⚠️ paths_config เป็นพารามิเตอร์บังคับ - ไม่มีค่า Path เริ่มต้น
    
    Parameters:
        file: ไฟล์ Excel ที่อัปโหลด
        paths_config: JSON string ของ Path configuration (บังคับ - ผู้ใช้ต้องระบุเอง)
                      เช่น: {"11": "C:\\path\\to\\11", "21": "C:\\path\\to\\21"}
    
    Returns:
        ProcessFileResponse: Processing result with status and details
    """
    logger.info(f"Upload request received for file: {file.filename}")
    
    try:
        # Validate file extension
        if not file.filename.endswith(('.xlsx', '.xls')):
            logger.warning(f"Invalid file format: {file.filename}")
            raise HTTPException(status_code=400, detail="Only .xlsx and .xls files are supported")
        
        # Parse paths_config from JSON string
        try:
            paths_dict = json.loads(paths_config) if paths_config != "{}" else {}
            logger.debug(f"Paths config parsed: {list(paths_dict.keys())}")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in paths_config: {str(e)}")
            paths_dict = {}
        
        # Validate that paths are provided
        if not paths_dict:
            logger.error("No paths provided - paths_config is required and cannot be empty")
            raise HTTPException(
                status_code=400, 
                detail="❌ ERROR: paths_config is required - must provide at least one path. Example: {\"11\": \"C:\\\\path\\\\to\\\\11\"}"
            )
        
        # Save uploaded file to temporary location
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name
        
        logger.info(f"File saved to temp location: {tmp_path}")
        
        try:
            # Process the file using processors module
            logger.info("Starting file processing...")
            result = process_excel_file(tmp_path, paths_dict)
            
            if result["success"]:
                logger.info(f"File processing successful. Branch: {result.get('detected_branch')}")
            else:
                logger.warning(f"File processing failed: {result.get('message')}")
            
            return ProcessFileResponse(**result)
        
        finally:
            # Clean up temporary file
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
                logger.debug(f"Temporary file deleted: {tmp_path}")
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error during file upload: {str(e)}", exc_info=True)
        return ProcessFileResponse(
            success=False,
            message=f"❌ Server Error: {str(e)}",
            detected_branch=None,
            error_details=traceback.format_exc()
        )


# ==================== RUN SERVER ====================
if __name__ == "__main__":
    import uvicorn
    
    logger.info(f"Starting Uvicorn server...")
    uvicorn.run(
        "app:app",
        host=SERVER_HOST,
        port=SERVER_PORT,
        reload=RELOAD,
        log_level="info"
    )
