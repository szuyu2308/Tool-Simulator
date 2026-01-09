# ======================================================
# core/tech.py
# FILE TRUNG TÂM QUẢN LÝ TOÀN BỘ CÔNG NGHỆ / LIB
# ======================================================

# ===== SYSTEM / CORE =====
import time
import threading
import queue
import logging

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

# ===== WINDOWS API (LDPLAYER / WINDOW HANDLE) =====
import win32gui
import win32ui
import win32con
import win32api

# ===== LOW LEVEL INPUT (SENDINPUT) =====
from ctypes import windll, Structure, c_ulong, c_long

# ===== SCREEN CAPTURE =====
import mss
import mss.tools

# ===== IMAGE / MOTION PROCESS =====
import cv2
import numpy as np

# ===== CONFIG =====
import json
import yaml


# ======================================================
# EXPORT – CHỈ NHỮNG THỨ ĐƯỢC PHÉP DÙNG
# ======================================================
__all__ = [
    # system
    "time",
    "threading",
    "queue",
    "logging",

    # typing / structure
    "dataclass",
    "Any",
    "Dict",
    "List",
    "Optional",
    "Tuple",

    # windows api
    "win32gui",
    "win32ui",
    "win32con",
    "win32api",

    # low level input
    "windll",
    "Structure",
    "c_ulong",
    "c_long",

    # capture
    "mss",

    # image / motion
    "cv2",
    "np",

    # config
    "json",
    "yaml",
]
