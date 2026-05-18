"""
logger.py - Logging Configuration
"""
import logging
import sys
from config import LOG_LEVEL, DEBUG

# ==================== SETUP LOGGER ====================
def setup_logger(name: str) -> logging.Logger:
    """Setup logger with console output"""
    logger = logging.getLogger(name)
    logger.setLevel(LOG_LEVEL)
    
    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(LOG_LEVEL)
    
    # Formatter
    if DEBUG:
        formatter = logging.Formatter(
            '[%(asctime)s] %(levelname)-8s | %(name)s | %(funcName)s:%(lineno)d | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    else:
        formatter = logging.Formatter(
            '[%(asctime)s] %(levelname)-8s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    
    console_handler.setFormatter(formatter)
    
    # Remove duplicate handlers
    if logger.hasHandlers():
        logger.handlers.clear()
    
    logger.addHandler(console_handler)
    return logger

# Global logger
logger = setup_logger("ExcelProcessor")
