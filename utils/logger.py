import logging
import os
import atexit
import glob
import json
from datetime import datetime

LOG_DIR = "logs"
CONFIG_FILE = "data/app_config.json"

# Default settings
ENABLE_FILE_LOGGING = False  # Log to file
ENABLE_CONSOLE_LOGGING = True  # Log to console (for developers)
DEBUG_MODE = True  # Show detailed logs

def load_logging_config():
    """Load logging settings from config file"""
    global ENABLE_FILE_LOGGING, ENABLE_CONSOLE_LOGGING, DEBUG_MODE
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
                ENABLE_FILE_LOGGING = config.get("enable_file_logging", False)
                ENABLE_CONSOLE_LOGGING = config.get("enable_console_logging", True)
                DEBUG_MODE = config.get("debug_mode", True)
    except:
        pass

def save_logging_config():
    """Save logging settings to config file"""
    try:
        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
        config = {}
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
        
        config["enable_file_logging"] = ENABLE_FILE_LOGGING
        config["enable_console_logging"] = ENABLE_CONSOLE_LOGGING
        config["debug_mode"] = DEBUG_MODE
        
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2)
    except:
        pass

def set_debug_mode(enabled: bool):
    """Enable/disable debug mode (for production builds)"""
    global DEBUG_MODE, ENABLE_CONSOLE_LOGGING
    DEBUG_MODE = enabled
    ENABLE_CONSOLE_LOGGING = enabled
    save_logging_config()

def is_debug_mode() -> bool:
    """Check if debug mode is enabled"""
    return DEBUG_MODE

# Load config on module import
load_logging_config()

# Track current log file for cleanup
_current_log_file = None

def cleanup_logs():
    """Xóa tất cả log files khi app đóng"""
    global _current_log_file
    try:
        if os.path.exists(LOG_DIR):
            # Xóa tất cả .log files
            log_files = glob.glob(os.path.join(LOG_DIR, "*.log"))
            for f in log_files:
                try:
                    os.remove(f)
                except:
                    pass
            # Xóa folder nếu trống
            try:
                if os.path.exists(LOG_DIR) and not os.listdir(LOG_DIR):
                    os.rmdir(LOG_DIR)
            except:
                pass
    except:
        pass

# Đăng ký cleanup khi app thoát
atexit.register(cleanup_logs)

def setup_logger(name="AUTO_TOOL"):
    global _current_log_file
    
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    
    # Clear existing handlers
    logger.handlers.clear()

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(message)s"
    )

    # File handler - chỉ tạo nếu ENABLE_FILE_LOGGING = True
    if ENABLE_FILE_LOGGING:
        if not os.path.exists(LOG_DIR):
            os.makedirs(LOG_DIR)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = os.path.join(LOG_DIR, f"run_{timestamp}.log")
        _current_log_file = log_file
        
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(formatter)
        logger.addHandler(fh)

    # Console handler - chỉ tạo nếu ENABLE_CONSOLE_LOGGING = True
    if ENABLE_CONSOLE_LOGGING:
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        ch.setFormatter(formatter)
        logger.addHandler(ch)

    return logger

def log(message: str):
    """Convenience function for quick logging - respects DEBUG_MODE"""
    if not DEBUG_MODE:
        return  # Skip logging in production mode
    
    logger = logging.getLogger("AUTO_TOOL")
    if not logger.handlers:
        logger = setup_logger()
    logger.info(message)