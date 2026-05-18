"""
models.py - Pydantic Models for Request/Response
"""
from pydantic import BaseModel
from typing import Dict, List, Optional

# ==================== REQUEST MODELS ====================
class ProcessFileRequest(BaseModel):
    """Request body for file processing"""
    paths_config: Dict[str, str] = {}

# ==================== RESPONSE MODELS ====================
class ProcessFileResponse(BaseModel):
    """Response from file processing"""
    success: bool
    message: str
    detected_branch: Optional[str] = None
    branch_name: Optional[str] = None
    files_saved: List[str] = []
    error_details: Optional[str] = None

class HealthCheckResponse(BaseModel):
    """Health check response"""
    status: str
    message: str
    version: str = "1.0.0"

class ConfigResponse(BaseModel):
    """Configuration response"""
    paths: Dict[str, str]
    branches: Dict[str, str]
