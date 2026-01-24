import tkinter as tk
from tkinter import filedialog, messagebox, ttk, simpledialog
import json
import os
import sys
import uuid
import threading
import time

# Windows CREATE_NO_WINDOW flag for subprocess
if sys.platform == 'win32':
    CREATE_NO_WINDOW = 0x08000000
else:
    CREATE_NO_WINDOW = 0

# Đường dẫn tuyệt đối tới thư mục macros (tương đối với vị trí script/exe)
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MACROS_DIR = os.path.abspath(os.path.join(_SCRIPT_DIR, "..", "data", "macros"))
DATA_DIR = os.path.abspath(os.path.join(_SCRIPT_DIR, "..", "data"))
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field, asdict
from enum import Enum

from core.macro_launcher import MacroLauncher
from core.adb_manager import ADBManager
from core.worker_manager import WorkerAssignmentManager
from core.models import (
    Script, Command, CommandType,
    ClickCommand, CropImageCommand, KeyPressCommand, HotKeyCommand,
    TextCommand, WaitCommand, RepeatCommand, GotoCommand, ConditionCommand,
    ButtonType, TextMode, WaitType, OnFailAction, COMMAND_TYPE_MAP
)
from utils.logger import log

# Import Macro Recorder components for recording/playback
try:
    from core.macro import (
        MacroManager, get_macro_manager, MacroRecorder, MacroPlayer,
        RecorderState, PlaybackState, GlobalHotkeyManager, WindowUtils,
        RawEvent, RawEventType
    )
    from core.macro.processor import MacroEventProcessor
    MACRO_RECORDER_AVAILABLE = True
except ImportError as e:
    log(f"[UI] Macro Recorder not available: {e}")
    MACRO_RECORDER_AVAILABLE = False

# Import new V2 modules (recorder adapter, capture utils, action engine)
try:
    from core.recorder_adapter import (
        get_recorder, IRecorderHook, RecordedEvent, RecordedEventKind
    )
    RECORDER_ADAPTER_AVAILABLE = True
except ImportError as e:
    log(f"[UI] Recorder adapter not available: {e}")
    RECORDER_ADAPTER_AVAILABLE = False

try:
    from core.capture_utils import CaptureOverlay, QuickCapture, get_pixel_color
    CAPTURE_UTILS_AVAILABLE = True
except ImportError as e:
    log(f"[UI] Capture utils not available: {e}")
    CAPTURE_UTILS_AVAILABLE = False

try:
    from core.action_engine import ActionEngine, create_action_engine, ActionStatus
    ACTION_ENGINE_AVAILABLE = True
except ImportError as e:
    log(f"[UI] Action engine not available: {e}")
    ACTION_ENGINE_AVAILABLE = False

try:
    from core.image_actions import image_actions_available
    IMAGE_ACTIONS_AVAILABLE = image_actions_available()
except ImportError:
    IMAGE_ACTIONS_AVAILABLE = False


# ==================== MODERN UI STYLE CONFIGURATION 2026 ====================

class ModernStyle:
    """
    Modern Dark Pro UI - 2026 Design System
    Inspired by: VS Code, GitHub Dark, JetBrains New UI, shadcn/ui
    Theme: Refined dark mode with subtle depth and polish
    """
    
    # === CORE COLORS (GitHub Dark / VS Code inspired) ===
    BG_PRIMARY = "#0d1117"       # Deep background
    BG_SECONDARY = "#161b22"     # Card/panel background  
    BG_TERTIARY = "#21262d"      # Hover/elevated surfaces
    BG_ELEVATED = "#1c2128"      # Modal/dropdown bg
    BG_INPUT = "#0d1117"         # Input fields
    BG_CARD = "#161b22"          # Cards
    BG_GLASS = "#21262d"         # Glass panels
    
    # Text colors - High contrast for accessibility
    FG_PRIMARY = "#e6edf3"       # Primary text (soft white)
    FG_SECONDARY = "#8b949e"     # Secondary text
    FG_MUTED = "#484f58"         # Muted/placeholder
    FG_ACCENT = "#58a6ff"        # Accent/links
    
    # === ACCENT COLORS (Refined, not neon) ===
    ACCENT_RED = "#f85149"       # Record/Danger
    ACCENT_GREEN = "#3fb950"     # Play/Success
    ACCENT_ORANGE = "#d29922"    # Pause/Warning  
    ACCENT_PURPLE = "#a371f7"    # Screen/Special
    ACCENT_BLUE = "#58a6ff"      # Primary action
    ACCENT_CYAN = "#39c5cf"      # Info/highlight
    ACCENT_GRAY = "#6e7681"      # Stop/Neutral
    
    # Button colors with gradient support
    BTN_RECORD = "#da3633"       # Record - deep red
    BTN_RECORD_HOVER = "#f85149"
    BTN_PLAY = "#238636"         # Play - rich green
    BTN_PLAY_HOVER = "#2ea043"
    BTN_PAUSE = "#9e6a03"        # Pause - amber
    BTN_PAUSE_HOVER = "#d29922"
    BTN_STOP = "#21262d"         # Stop - subtle gray
    BTN_STOP_HOVER = "#30363d"
    BTN_SCREEN = "#8957e5"       # Screen - purple
    BTN_SCREEN_HOVER = "#a371f7"
    BTN_SETTINGS = "#6e7681"     # Settings - neutral
    BTN_PRIMARY = "#238636"      # Primary action
    BTN_PRIMARY_HOVER = "#2ea043"
    BTN_SECONDARY = "#21262d"    # Secondary
    BTN_SECONDARY_HOVER = "#30363d"
    BTN_DANGER = "#da3633"
    BTN_DANGER_HOVER = "#f85149"
    BTN_SUCCESS = "#238636"
    
    # Borders & effects
    BORDER_COLOR = "#30363d"
    BORDER_FOCUS = "#58a6ff"
    BORDER_SUBTLE = "#21262d"
    SHADOW_COLOR = "rgba(0,0,0,0.4)"
    
    # === TYPOGRAPHY (Compact for better fit) ===
    FONT_FAMILY = "Segoe UI"
    FONT_MONO = "Cascadia Code"
    FONT_SIZE_XS = 8
    FONT_SIZE_SM = 9
    FONT_SIZE_MD = 10
    FONT_SIZE_LG = 11
    FONT_SIZE_XL = 12
    FONT_SIZE_XXL = 14
    FONT_SIZE_TITLE = 11
    
    # === SPACING (Compact) ===
    PAD_XS = 2
    PAD_SM = 4
    PAD_MD = 6
    PAD_LG = 8
    PAD_XL = 12
    PAD_XXL = 16
    
    # Component sizes
    ROW_HEIGHT = 28
    BTN_HEIGHT = 26
    INPUT_HEIGHT = 28
    TOOLBAR_HEIGHT = 40
    BORDER_RADIUS = 6
    
    @classmethod
    def apply_dark_theme(cls, root):
        """Apply modern dark theme to all widgets"""
        root.configure(bg=cls.BG_PRIMARY)
        root.option_add("*Background", cls.BG_SECONDARY)
        root.option_add("*Foreground", cls.FG_PRIMARY)
        root.option_add("*Font", (cls.FONT_FAMILY, cls.FONT_SIZE_MD))
        root.option_add("*Listbox.selectBackground", cls.ACCENT_BLUE)
        root.option_add("*Listbox.selectForeground", cls.FG_PRIMARY)
        
        style = ttk.Style(root)
        style.theme_use('clam')
        
        # Global style
        style.configure(".",
                       background=cls.BG_SECONDARY,
                       foreground=cls.FG_PRIMARY,
                       fieldbackground=cls.BG_INPUT,
                       insertcolor=cls.FG_PRIMARY,
                       font=(cls.FONT_FAMILY, cls.FONT_SIZE_MD))
        
        # Frame styles
        style.configure("TFrame", background=cls.BG_SECONDARY)
        style.configure("Card.TFrame", background=cls.BG_CARD)
        style.configure("Glass.TFrame", background=cls.BG_GLASS)
        
        # Label styles
        style.configure("TLabel", 
                       background=cls.BG_SECONDARY, 
                       foreground=cls.FG_PRIMARY)
        style.configure("Title.TLabel",
                       font=(cls.FONT_FAMILY, cls.FONT_SIZE_XL, "bold"),
                       foreground=cls.FG_PRIMARY)
        style.configure("Muted.TLabel",
                       foreground=cls.FG_SECONDARY)
        
        # Button styles - Modern
        style.configure("TButton",
                       background=cls.BTN_SECONDARY,
                       foreground=cls.FG_PRIMARY,
                       padding=(cls.PAD_LG, cls.PAD_SM),
                       font=(cls.FONT_FAMILY, cls.FONT_SIZE_MD))
        style.map("TButton",
                 background=[("active", cls.BTN_SECONDARY_HOVER), ("pressed", cls.BG_PRIMARY)])
        
        # Entry & Combobox - Refined
        style.configure("TEntry",
                       fieldbackground=cls.BG_INPUT,
                       foreground=cls.FG_PRIMARY,
                       insertcolor=cls.FG_PRIMARY,
                       padding=(cls.PAD_SM, cls.PAD_XS))
        style.configure("TCombobox",
                       fieldbackground=cls.BG_INPUT,
                       foreground=cls.FG_PRIMARY,
                       arrowcolor=cls.FG_SECONDARY,
                       padding=(cls.PAD_SM, cls.PAD_XS))
        style.map("TCombobox",
                 fieldbackground=[("readonly", cls.BG_INPUT)],
                 selectbackground=[("readonly", cls.ACCENT_BLUE)])
        
        # Spinbox
        style.configure("TSpinbox",
                       fieldbackground=cls.BG_INPUT,
                       foreground=cls.FG_PRIMARY,
                       arrowcolor=cls.FG_SECONDARY)
        
        # LabelFrame - Modern card look
        style.configure("TLabelframe",
                       background=cls.BG_CARD,
                       foreground=cls.FG_PRIMARY,
                       bordercolor=cls.BORDER_COLOR)
        style.configure("TLabelframe.Label",
                       background=cls.BG_CARD,
                       foreground=cls.FG_ACCENT,
                       font=(cls.FONT_FAMILY, cls.FONT_SIZE_LG, "bold"))
        
        # Notebook (tabs)
        style.configure("TNotebook",
                       background=cls.BG_SECONDARY,
                       bordercolor=cls.BORDER_COLOR)
        style.configure("TNotebook.Tab",
                       background=cls.BG_TERTIARY,
                       foreground=cls.FG_SECONDARY,
                       padding=(cls.PAD_LG, cls.PAD_SM))
        style.map("TNotebook.Tab",
                 background=[("selected", cls.BG_CARD)],
                 foreground=[("selected", cls.FG_PRIMARY)])
        
        # Scrollbar - Minimal modern
        style.configure("TScrollbar",
                       background=cls.BG_TERTIARY,
                       troughcolor=cls.BG_PRIMARY,
                       arrowcolor=cls.FG_MUTED,
                       width=10)
        style.map("TScrollbar",
                 background=[("active", cls.FG_MUTED)])
        
        # Separator
        style.configure("TSeparator", background=cls.BORDER_COLOR)
        
        # Treeview (Tables) - Modern DataGrid with zebra
        style.configure("Treeview",
                       background=cls.BG_INPUT,
                       foreground=cls.FG_PRIMARY,
                       fieldbackground=cls.BG_INPUT,
                       rowheight=cls.ROW_HEIGHT,
                       font=(cls.FONT_FAMILY, cls.FONT_SIZE_MD))
        style.configure("Treeview.Heading",
                       background=cls.BG_TERTIARY,
                       foreground=cls.FG_SECONDARY,
                       font=(cls.FONT_FAMILY, cls.FONT_SIZE_SM, "bold"),
                       padding=(cls.PAD_MD, cls.PAD_SM))
        style.map("Treeview",
                 background=[("selected", "#1f6feb")],  # Blue selection
                 foreground=[("selected", cls.FG_PRIMARY)])
        style.map("Treeview.Heading",
                 background=[("active", cls.BG_GLASS)])
        
        # Checkbutton & Radiobutton
        style.configure("TCheckbutton",
                       background=cls.BG_SECONDARY,
                       foreground=cls.FG_PRIMARY)
        style.map("TCheckbutton",
                 background=[("active", cls.BG_TERTIARY)])
        style.configure("TRadiobutton",
                       background=cls.BG_SECONDARY,
                       foreground=cls.FG_PRIMARY)
        
        # Scale (slider)
        style.configure("TScale",
                       background=cls.BG_SECONDARY,
                       troughcolor=cls.BG_INPUT)
        style.configure("Horizontal.TScale",
                       background=cls.BG_SECONDARY)
        
        # Progressbar
        style.configure("TProgressbar",
                       background=cls.ACCENT_BLUE,
                       troughcolor=cls.BG_INPUT)
    
    @classmethod
    def create_toolbar_button(cls, parent, text, icon, command=None, color=None, width=None):
        """Create modern toolbar button with hover effects"""
        bg = color or cls.BTN_SECONDARY
        
        # Calculate hover/press colors
        def adjust_color(hex_color, factor):
            """Lighten (factor>0) or darken (factor<0) a color"""
            r = int(hex_color[1:3], 16)
            g = int(hex_color[3:5], 16)
            b = int(hex_color[5:7], 16)
            if factor > 0:
                r = min(255, int(r + (255 - r) * factor))
                g = min(255, int(g + (255 - g) * factor))
                b = min(255, int(b + (255 - b) * factor))
            else:
                r = max(0, int(r * (1 + factor)))
                g = max(0, int(g * (1 + factor)))
                b = max(0, int(b * (1 + factor)))
            return f"#{r:02x}{g:02x}{b:02x}"
        
        hover_bg = adjust_color(bg, 0.15)
        press_bg = adjust_color(bg, -0.1)
        
        # Button with icon + text
        btn = tk.Button(parent, text=f"{icon}  {text}", command=command,
                       bg=bg, fg=cls.FG_PRIMARY, 
                       activebackground=hover_bg, activeforeground=cls.FG_PRIMARY,
                       font=(cls.FONT_FAMILY, cls.FONT_SIZE_MD, "bold"),
                       relief="flat", cursor="hand2", bd=0,
                       padx=cls.PAD_LG, pady=cls.PAD_SM)
        if width:
            btn.config(width=width)
        
        # Smooth hover effects
        def on_enter(e):
            btn.config(bg=hover_bg)
        def on_leave(e):
            btn.config(bg=bg)
        def on_press(e):
            btn.config(bg=press_bg, relief="sunken")
        def on_release(e):
            btn.config(bg=hover_bg, relief="flat")
        
        btn.bind("<Enter>", on_enter)
        btn.bind("<Leave>", on_leave)
        btn.bind("<ButtonPress-1>", on_press)
        btn.bind("<ButtonRelease-1>", on_release)
        
        return btn
    
    @classmethod
    def create_action_button(cls, parent, text, command=None, style="secondary", icon=None, width=None):
        """Create action button for panels (Add, Edit, Delete, etc.)"""
        styles = {
            "primary": (cls.BTN_PRIMARY, cls.BTN_PRIMARY_HOVER, cls.FG_PRIMARY),
            "success": (cls.BTN_SUCCESS, cls.BTN_PLAY_HOVER, cls.FG_PRIMARY),
            "danger": (cls.BTN_DANGER, cls.BTN_DANGER_HOVER, cls.FG_PRIMARY),
            "warning": (cls.BTN_PAUSE, cls.BTN_PAUSE_HOVER, "#000000"),
            "secondary": (cls.BTN_SECONDARY, cls.BTN_SECONDARY_HOVER, cls.FG_PRIMARY),
        }
        bg, hover_bg, fg = styles.get(style, styles["secondary"])
        
        display_text = f"{icon} {text}" if icon else text
        
        btn = tk.Button(parent, text=display_text, command=command,
                       bg=bg, fg=fg, 
                       activebackground=hover_bg, activeforeground=fg,
                       font=(cls.FONT_FAMILY, cls.FONT_SIZE_SM, "bold"),
                       relief="flat", cursor="hand2", bd=0,
                       padx=cls.PAD_MD, pady=cls.PAD_XS)
        if width:
            btn.config(width=width)
        
        # Hover effect
        def on_enter(e):
            btn.config(bg=hover_bg)
        def on_leave(e):
            btn.config(bg=bg)
        
        btn.bind("<Enter>", on_enter)
        btn.bind("<Leave>", on_leave)
        
        return btn
    
    @classmethod
    def create_modern_button(cls, parent, text, command=None, style="primary", width=None, icon=None, **kwargs):
        """Create a Win11-style modern button with smooth hover effects"""
        # Win11-style colors with softer shades
        colors = {
            "primary": (cls.BTN_PRIMARY, "#2ea043", cls.FG_PRIMARY),
            "success": (cls.BTN_SUCCESS, "#2ea043", cls.FG_PRIMARY),
            "warning": ("#b08800", "#d4a500", "#000000"),
            "danger": (cls.BTN_DANGER, "#f85149", cls.FG_PRIMARY),
            "secondary": ("#2d333b", "#373e47", cls.FG_PRIMARY),
            "record": (cls.BTN_RECORD, "#f85149", cls.FG_PRIMARY),
            "play": (cls.BTN_PLAY, "#2ea043", cls.FG_PRIMARY),
            "stop": ("#3d444d", "#484f58", cls.FG_PRIMARY),
            "accent": (cls.ACCENT_BLUE, "#79b8ff", cls.FG_PRIMARY),
        }
        bg, hover_bg, fg = colors.get(style, colors["primary"])
        
        display_text = f"{icon} {text}" if icon else text
        
        # Create button with smooth rounded look
        btn = tk.Button(parent, text=display_text, command=command,
                       bg=bg, fg=fg, 
                       activebackground=hover_bg, activeforeground=fg,
                       font=(cls.FONT_FAMILY, cls.FONT_SIZE_SM),
                       relief="flat", cursor="hand2", bd=0,
                       padx=cls.PAD_MD, pady=cls.PAD_SM,
                       highlightthickness=0)
        if width:
            btn.config(width=width)
        
        # Smooth hover animation
        def on_enter(e):
            btn.config(bg=hover_bg)
        def on_leave(e):
            btn.config(bg=bg)
        def on_press(e):
            # Slight darken on press
            btn.config(relief="flat")
        def on_release(e):
            btn.config(relief="flat")
        
        btn.bind("<Enter>", on_enter)
        btn.bind("<Leave>", on_leave)
        btn.bind("<ButtonPress-1>", on_press)
        btn.bind("<ButtonRelease-1>", on_release)
        
        return btn
    
    @classmethod
    def create_pill_button(cls, parent, text, command=None, color=None, width=None):
        """Create a pill-shaped button (rounded edges look)"""
        bg = color or cls.ACCENT_BLUE
        
        def adjust_color(hex_color, factor):
            r = int(hex_color[1:3], 16)
            g = int(hex_color[3:5], 16)
            b = int(hex_color[5:7], 16)
            if factor > 0:
                r = min(255, int(r + (255 - r) * factor))
                g = min(255, int(g + (255 - g) * factor))
                b = min(255, int(b + (255 - b) * factor))
            else:
                r = max(0, int(r * (1 + factor)))
                g = max(0, int(g * (1 + factor)))
                b = max(0, int(b * (1 + factor)))
            return f"#{r:02x}{g:02x}{b:02x}"
        
        hover_bg = adjust_color(bg, 0.2)
        
        btn = tk.Button(parent, text=text, command=command,
                       bg=bg, fg=cls.FG_PRIMARY,
                       activebackground=hover_bg, activeforeground=cls.FG_PRIMARY,
                       font=(cls.FONT_FAMILY, cls.FONT_SIZE_SM, "bold"),
                       relief="flat", cursor="hand2", bd=0,
                       padx=cls.PAD_LG, pady=cls.PAD_SM,
                       highlightthickness=0)
        if width:
            btn.config(width=width)
        
        def on_enter(e):
            btn.config(bg=hover_bg)
        def on_leave(e):
            btn.config(bg=bg)
        
        btn.bind("<Enter>", on_enter)
        btn.bind("<Leave>", on_leave)
        
        return btn
    
    @classmethod
    def create_glass_panel(cls, parent, **kwargs):
        """Create glassmorphism styled panel"""
        frame = tk.Frame(parent, bg=cls.BG_GLASS,
                        highlightbackground=cls.BORDER_COLOR,
                        highlightthickness=1,
                        **kwargs)
        return frame
    
    @classmethod
    def create_section_frame(cls, parent, title, icon=None, **kwargs):
        """Create a simple LabelFrame section. Returns the frame directly."""
        title_text = f" {icon} {title} " if icon else f" {title} "
        frame = tk.LabelFrame(parent, text=title_text,
                             bg=cls.BG_CARD, fg=cls.FG_ACCENT,
                             font=(cls.FONT_FAMILY, cls.FONT_SIZE_TITLE, "bold"),
                             relief="flat", bd=1,
                             highlightbackground=cls.BORDER_COLOR,
                             highlightthickness=1,
                             padx=cls.PAD_SM, pady=cls.PAD_SM)
        # For backward compatibility
        frame.content = frame
        return frame
    
    @classmethod
    def create_card_frame(cls, parent, title=None, icon=None):
        """Create a modern card with optional header"""
        card = tk.Frame(parent, bg=cls.BG_CARD,
                       highlightbackground=cls.BORDER_COLOR,
                       highlightthickness=1)
        
        if title:
            # Header
            header = tk.Frame(card, bg=cls.BG_CARD)
            header.pack(fill="x", padx=cls.PAD_LG, pady=(cls.PAD_MD, 0))
            
            # Accent dot
            if icon:
                tk.Label(header, text=icon, bg=cls.BG_CARD, fg=cls.ACCENT_BLUE,
                        font=(cls.FONT_FAMILY, cls.FONT_SIZE_LG)).pack(side="left", padx=(0, cls.PAD_SM))
            
            tk.Label(header, text=title, bg=cls.BG_CARD, fg=cls.FG_PRIMARY,
                    font=(cls.FONT_FAMILY, cls.FONT_SIZE_LG, "bold")).pack(side="left")
            
            # Separator line
            sep = tk.Frame(card, bg=cls.BORDER_COLOR, height=1)
            sep.pack(fill="x", padx=cls.PAD_MD, pady=(cls.PAD_SM, 0))
        
        return card
    
    @classmethod
    def create_entry(cls, parent, textvariable=None, width=20, **kwargs):
        """Create a modern styled entry"""
        entry = tk.Entry(parent, textvariable=textvariable, width=width,
                        bg=cls.BG_INPUT, fg=cls.FG_PRIMARY,
                        insertbackground=cls.FG_PRIMARY,
                        relief="flat",
                        font=(cls.FONT_FAMILY, cls.FONT_SIZE_MD),
                        highlightthickness=1,
                        highlightbackground=cls.BORDER_COLOR,
                        highlightcolor=cls.BORDER_FOCUS,
                        selectbackground=cls.ACCENT_BLUE,
                        selectforeground=cls.FG_PRIMARY)
        return entry
    
    @classmethod
    def create_label(cls, parent, text, style="primary", size=None, bold=False, **kwargs):
        """Create a modern styled label"""
        colors = {
            "primary": cls.FG_PRIMARY,
            "secondary": cls.FG_SECONDARY,
            "muted": cls.FG_MUTED,
            "accent": cls.FG_ACCENT,
            "success": cls.ACCENT_GREEN,
            "warning": cls.ACCENT_ORANGE,
            "danger": cls.ACCENT_RED,
        }
        fg = colors.get(style, cls.FG_PRIMARY)
        font_size = size or cls.FONT_SIZE_MD
        font_weight = "bold" if bold else "normal"
        bg = kwargs.pop("bg", cls.BG_SECONDARY)
        
        label = tk.Label(parent, text=text, bg=bg, fg=fg,
                        font=(cls.FONT_FAMILY, font_size, font_weight))
        return label
    
    # === ZEBRA STRIPING COLORS ===
    ZEBRA_ODD = "#0d1117"   # Same as BG_PRIMARY
    ZEBRA_EVEN = "#161b22"  # Same as BG_SECONDARY
    
    @classmethod
    def apply_zebra_striping(cls, treeview):
        """Apply zebra striping to a Treeview by configuring tags on rows.
        Call this after inserting items and use 'oddrow' and 'evenrow' tags."""
        treeview.tag_configure('oddrow', background=cls.ZEBRA_ODD)
        treeview.tag_configure('evenrow', background=cls.ZEBRA_EVEN)
        treeview.tag_configure('selected', background=cls.ACCENT_BLUE)
        # Error and warning states
        treeview.tag_configure('error', background='#3d1c1c', foreground=cls.ACCENT_RED)
        treeview.tag_configure('warning', background='#3d2e1c', foreground=cls.ACCENT_ORANGE)
        treeview.tag_configure('success', background='#1c3d2e', foreground=cls.ACCENT_GREEN)
        treeview.tag_configure('running', background='#1c2d3d', foreground=cls.ACCENT_BLUE)
        # Muted state for disabled items
        treeview.tag_configure('muted', foreground=cls.FG_MUTED)
    
    @classmethod
    def refresh_zebra_striping(cls, treeview):
        """Refresh zebra striping after rows have been added/removed.
        Should be called after any item insertion or deletion."""
        children = treeview.get_children()
        for index, child in enumerate(children):
            tag = 'evenrow' if index % 2 == 0 else 'oddrow'
            # Get existing tags and preserve non-zebra ones
            existing = list(treeview.item(child, 'tags'))
            # Remove old zebra tags
            existing = [t for t in existing if t not in ('oddrow', 'evenrow')]
            existing.append(tag)
            treeview.item(child, tags=existing)
    
    @classmethod
    def create_status_badge(cls, parent, text, status="info"):
        """Create a colored status badge/pill"""
        colors = {
            "info": (cls.ACCENT_BLUE, cls.FG_PRIMARY),
            "success": (cls.ACCENT_GREEN, "#000000"),
            "warning": (cls.ACCENT_ORANGE, "#000000"),
            "danger": (cls.ACCENT_RED, cls.FG_PRIMARY),
            "muted": (cls.BG_TERTIARY, cls.FG_SECONDARY),
        }
        bg, fg = colors.get(status, colors["info"])
        
        badge = tk.Label(parent, text=f"  {text}  ", bg=bg, fg=fg,
                        font=(cls.FONT_FAMILY, cls.FONT_SIZE_XS, "bold"))
        return badge
    
    @classmethod
    def create_icon_button(cls, parent, icon, command=None, tooltip=None, color=None):
        """Create a small icon-only button (for toolbars, row actions)"""
        bg = color or cls.BG_TERTIARY
        
        def adjust_color(hex_color, factor):
            r = int(hex_color[1:3], 16)
            g = int(hex_color[3:5], 16)
            b = int(hex_color[5:7], 16)
            if factor > 0:
                r = min(255, int(r + (255 - r) * factor))
                g = min(255, int(g + (255 - g) * factor))
                b = min(255, int(b + (255 - b) * factor))
            else:
                r = max(0, int(r * (1 + factor)))
                g = max(0, int(g * (1 + factor)))
                b = max(0, int(b * (1 + factor)))
            return f"#{r:02x}{g:02x}{b:02x}"
        
        hover_bg = adjust_color(bg, 0.2)
        
        btn = tk.Button(parent, text=icon, command=command,
                       bg=bg, fg=cls.FG_PRIMARY,
                       activebackground=hover_bg, activeforeground=cls.FG_PRIMARY,
                       font=(cls.FONT_FAMILY, cls.FONT_SIZE_MD),
                       relief="flat", cursor="hand2", bd=0,
                       padx=cls.PAD_SM, pady=cls.PAD_XS)
        
        def on_enter(e):
            btn.config(bg=hover_bg)
        def on_leave(e):
            btn.config(bg=bg)
        
        btn.bind("<Enter>", on_enter)
        btn.bind("<Leave>", on_leave)
        
        return btn


# ==================== ACTION MODELS (Lightweight) ====================

class ActionType(Enum):
    """Supported action types per spec - V2 expanded"""
    # Basic Mouse/Keyboard
    CLICK = "CLICK"
    WAIT = "WAIT"
    KEY_PRESS = "KEY_PRESS"
    COMBOKEY = "COMBOKEY"  # Renamed from HOTKEY for clarity
    WHEEL = "WHEEL"
    DRAG = "DRAG"
    TEXT = "TEXT"
    RECORDED_BLOCK = "RECORDED_BLOCK"  # Block of recorded actions
    
    # Wait Actions (V2 - spec B1)
    WAIT_TIME = "WAIT_TIME"
    WAIT_PIXEL_COLOR = "WAIT_PIXEL_COLOR"
    WAIT_SCREEN_CHANGE = "WAIT_SCREEN_CHANGE"
    WAIT_COMBOKEY = "WAIT_COMBOKEY"  # Renamed from WAIT_HOTKEY
    WAIT_FILE = "WAIT_FILE"
    
    # Image Actions (V2 - spec B2)
    FIND_IMAGE = "FIND_IMAGE"
    CAPTURE_IMAGE = "CAPTURE_IMAGE"
    
    # Flow Control (V2 - spec B4)
    LABEL = "LABEL"
    GOTO = "GOTO"
    REPEAT = "REPEAT"
    EMBED_MACRO = "EMBED_MACRO"
    GROUP = "GROUP"  # Group multiple actions together
    
    # Misc
    COMMENT = "COMMENT"
    SET_VARIABLE = "SET_VARIABLE"


@dataclass
class Action:
    """Lightweight action object per spec section 4.1"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    enabled: bool = True
    action: str = "CLICK"  # ActionType value
    value: Dict[str, Any] = field(default_factory=dict)
    label: str = ""
    comment: str = ""
    
    def to_dict(self) -> dict:
        import copy
        return {
            "id": self.id,
            "enabled": self.enabled,
            "action": self.action,
            "value": copy.deepcopy(self.value),  # Deep copy to prevent modification
            "label": self.label,
            "comment": self.comment
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Action':
        return cls(
            id=data.get("id", str(uuid.uuid4())[:8]),
            enabled=data.get("enabled", True),
            action=data.get("action", "CLICK"),
            value=data.get("value", {}),
            label=data.get("label", ""),
            comment=data.get("comment", "")
        )
    
    def get_value_summary(self) -> str:
        """Generate short summary for Value column"""
        v = self.value
        if self.action == "CLICK":
            btn = v.get("button", "left")
            x, y = v.get("x", 0), v.get("y", 0)
            hold_ms = v.get("hold_ms", 0)
            
            # Build base text
            if btn in ("hold_left", "hold_right"):
                text = f"{btn} {hold_ms}ms ({x}, {y})"
            else:
                text = f"{btn} ({x}, {y})"
            
            # Add schedule indicator if enabled
            if v.get("schedule_enabled", False):
                schedule_time = v.get("schedule_time", "??:??:??")
                text = f"⏰{schedule_time} " + text
            
            return text
        elif self.action == "WAIT":
            ms = v.get("ms", 0)
            return f"{ms}ms"
        elif self.action == "KEY_PRESS":
            key = v.get("key", "")
            repeat = v.get("repeat", 1)
            return f"{key}" + (f" x{repeat}" if repeat > 1 else "")
        elif self.action == "COMBOKEY":
            keys = v.get("keys", [])
            return "+".join(keys)
        elif self.action == "WHEEL":
            # V2: direction + amount + speed
            direction = v.get("direction", "up")
            amount = v.get("amount", 1)
            speed = v.get("speed", 50)
            x, y = v.get("x", 0), v.get("y", 0)
            arrow = "↑" if direction == "up" else "↓"
            # Backward compat với delta cũ
            if "delta" in v and "direction" not in v:
                delta = v.get("delta", 0)
                arrow = "↑" if delta > 0 else "↓"
                return f"{arrow} ({x}, {y})"
            return f"{arrow}x{amount} @{speed}ms ({x},{y})"
        elif self.action == "DRAG":
            x1, y1 = v.get("x1", 0), v.get("y1", 0)
            x2, y2 = v.get("x2", 0), v.get("y2", 0)
            duration = v.get("duration_ms", 500)
            btn = v.get("button", "left")[0].upper()  # L or R
            return f"{btn}:({x1},{y1})→({x2},{y2}) {duration}ms"
        elif self.action == "TEXT":
            text = v.get("text", "")
            return f'"{text[:20]}...' if len(text) > 20 else f'"{text}"'
        elif self.action == "RECORDED_BLOCK":
            actions = v.get("actions", [])
            return f"[{len(actions)} actions]"
        # V2 Actions
        elif self.action == "WAIT_TIME":
            ms = v.get("delay_ms", 0)
            variance = v.get("variance_ms", 0)
            return f"{ms}ms" + (f" ±{variance}" if variance else "")
        elif self.action == "WAIT_PIXEL_COLOR":
            x, y = v.get("x", 0), v.get("y", 0)
            rgb = v.get("expected_rgb", (0, 0, 0))
            return f"({x},{y}) #{rgb[0]:02X}{rgb[1]:02X}{rgb[2]:02X}"
        elif self.action == "WAIT_SCREEN_CHANGE":
            region = v.get("region", (0, 0, 0, 0))
            return f"region {region}"
        elif self.action == "WAIT_COMBOKEY":
            combo = v.get("key_combo", "")
            return f"key: {combo}"
        elif self.action == "WAIT_FILE":
            path = v.get("path", "")
            cond = v.get("condition", "exists")
            return f"{cond}: {os.path.basename(path)[:15]}"
        elif self.action == "FIND_IMAGE":
            path = v.get("template_path", "")
            return os.path.basename(path)[:20]
        elif self.action == "CAPTURE_IMAGE":
            path = v.get("save_path", "")
            return os.path.basename(path)[:20] if path else "auto"
        elif self.action == "LABEL":
            return v.get("name", "")
        elif self.action == "GOTO":
            return f"→ {v.get('target', '')}"
        elif self.action == "REPEAT":
            count = v.get("count", 1)
            return f"{count}x"
        elif self.action == "EMBED_MACRO":
            name = v.get("macro_name", "")
            return name[:20]
        elif self.action == "GROUP":
            name = v.get("name", "Group")
            actions = v.get("actions", [])
            return f"📦 {name} [{len(actions)}]"
        elif self.action == "COMMENT":
            text = v.get("text", "")
            return text[:30]
        elif self.action == "SET_VARIABLE":
            name = v.get("name", "")
            val = v.get("value", "")
            return f"{name} = {val}"
        return str(v)[:30]


MACRO_STORE = "data/macros.json"
SCRIPT_STORE = "data/scripts.json"
ACTIONS_STORE = "data/actions.json"


class MainUI:
    REFRESH_MS = 800

    def __init__(self, workers):
        self.root = tk.Tk()
        self.root.title("Tools LDPlayer - Action Recorder")
        self.root.geometry("1100x650")  # Larger for better UI fit
        self.root.minsize(900, 550)  # Minimum size

        self.workers = workers
        self.macros = []
        self.commands = []  # Store Command objects (old architecture)
        self.actions: List[Action] = []  # NEW: Action list per spec
        self.current_script: Script = None  # Current Script object
        self.selected_workers = set()  # Track selected workers
        self.worker_mgr = WorkerAssignmentManager()  # Manager gán Worker ID

        self.launcher = MacroLauncher(
            macro_exe_path=r"C:\Program Files\MacroRecorder\MacroRecorder.exe"
        )

        # Recording/Playback state
        self._is_recording = False
        self._is_playing = False
        self._is_paused = False
        self._recording_paused = False  # Separate pause state for recording
        self._playback_running = False  # Track if any worker playback is running
        self._recorder: Optional['MacroRecorder'] = None
        self._player_thread: Optional[threading.Thread] = None
        self._playback_stop_event = threading.Event()
        self._playback_pause_event = threading.Event()
        self._current_action_index = 0
        self._repeat_counters = {}  # Track REPEAT counts: {action_index: remaining_count}
        self._target_hwnd: Optional[int] = None  # Target window for recording

        # Recording toolbar
        self._recording_toolbar: Optional[tk.Toplevel] = None

        # Playback toolbar
        self._playback_toolbar: Optional[tk.Toplevel] = None

        # Hotkey settings
        self._hotkey_settings = self._load_hotkey_settings()

        # Capture target state (for XY/Region capture)
        self._capture_target_hwnd: Optional[int] = None  # None = screen coords (default)
        self._capture_target_name: str = "Screen (Full)"
        self._capture_crop_region = (0, 0, 0, 0)  # (x1, y1, x2, y2) - vùng crop

        # Worker-specific actions storage
        self._worker_actions: Dict[int, List[Action]] = {}  # worker_id -> custom actions
        self._worker_playback_threads: Dict[int, threading.Thread] = {}  # worker_id -> thread
        self._worker_stop_events: Dict[int, threading.Event] = {}  # worker_id -> stop event

        # Input method settings (SetCursorPos, PostMessage, ADB)
        self._input_settings = self._load_input_settings()

        # Global hotkey manager
        self._hotkey_manager: Optional['GlobalHotkeyManager'] = None

        # Initialize Macro Manager if available (for recorder hooks)
        self._macro_manager = None
        if MACRO_RECORDER_AVAILABLE:
            self._macro_manager = get_macro_manager()

        self._build_ui()
        self._load_macros()
        self._load_worker_actions()  # Load saved worker actions
        self._load_session()  # Restore last session actions
        self._auto_refresh_status()

        # Register global hotkeys on startup
        self._register_global_hotkeys()
        
        # Show guide dialog on startup (if enabled)
        self._show_guide_on_startup()
        
        # Register close handler to save session on exit
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
    
    def _on_close(self):
        """Save session and close app"""
        try:
            self._save_session()
            log("[UI] Session saved on exit")
        except Exception as e:
            log(f"[UI] Failed to save session on exit: {e}")
        self.root.destroy()
    
    def _save_session(self):
        """Save current actions to session file for next startup"""
        session_file = "data/session.json"
        if not self.actions:
            # No actions to save, remove old session file
            if os.path.exists(session_file):
                os.remove(session_file)
            return
        
        import copy
        import base64
        
        try:
            os.makedirs("data", exist_ok=True)
            
            # Build session data with embedded images
            actions_data = []
            images_embedded = {}
            image_count = 0
            
            for action in self.actions:
                action_dict = action.to_dict()
                
                # Embed FIND_IMAGE templates
                if action.action == "FIND_IMAGE" and action.value.get("template_path"):
                    old_path = action.value["template_path"]
                    if not old_path.startswith("@embedded:") and os.path.exists(old_path):
                        with open(old_path, "rb") as img_file:
                            img_data = base64.b64encode(img_file.read()).decode('utf-8')
                        import re
                        filename = os.path.basename(old_path)
                        clean_filename = re.sub(r'^(img_\d{3}_)+', '', filename)
                        if not clean_filename:
                            clean_filename = f"image_{image_count:03d}.png"
                        img_key = f"session_img_{image_count:03d}_{clean_filename}"
                        images_embedded[img_key] = img_data
                        action_dict["value"]["template_path"] = f"@embedded:{img_key}"
                        image_count += 1
                
                actions_data.append(action_dict)
            
            session_data = {
                "version": "1.0",
                "actions": actions_data,
                "images": images_embedded,
                "last_save_dir": getattr(self, '_last_save_dir', ''),
                "last_load_dir": getattr(self, '_last_load_dir', '')
            }
            
            with open(session_file, "w", encoding="utf-8") as f:
                json.dump(session_data, f, indent=2, ensure_ascii=False)
            
            log(f"[UI] Session saved: {len(self.actions)} actions, {image_count} images")
        except Exception as e:
            log(f"[UI] Failed to save session: {e}")
    
    def _load_session(self):
        """Load session from last app run"""
        session_file = "data/session.json"
        if not os.path.exists(session_file):
            return
        
        try:
            with open(session_file, "r", encoding="utf-8") as f:
                session_data = json.load(f)
            
            actions_data = session_data.get("actions", [])
            images = session_data.get("images", {})
            
            if not actions_data:
                return
            
            # Restore last used directories
            self._last_save_dir = session_data.get("last_save_dir", '')
            self._last_load_dir = session_data.get("last_load_dir", '')
            
            # Extract embedded images to temp
            if images:
                import base64
                import tempfile
                temp_dir = os.path.join(tempfile.gettempdir(), "macro_images", "session")
                os.makedirs(temp_dir, exist_ok=True)
                
                for img_key, img_b64 in images.items():
                    try:
                        img_data = base64.b64decode(img_b64)
                        img_path = os.path.join(temp_dir, img_key)
                        with open(img_path, "wb") as f:
                            f.write(img_data)
                    except Exception as e:
                        log(f"[UI] Failed to extract session image {img_key}: {e}")
                
                # Update paths in actions
                for action_data in actions_data:
                    if action_data.get("action") == "FIND_IMAGE":
                        template_path = action_data.get("value", {}).get("template_path", "")
                        if template_path.startswith("@embedded:"):
                            img_key = template_path.replace("@embedded:", "")
                            action_data["value"]["template_path"] = os.path.join(temp_dir, img_key)
            
            self.actions = [Action.from_dict(a) for a in actions_data]
            self._refresh_action_list()
            
            log(f"[UI] Session restored: {len(self.actions)} actions")
        except Exception as e:
            log(f"[UI] Failed to load session: {e}")
    
    # ================= INPUT METHOD SETTINGS =================
    
    def _load_input_settings(self):
        """Load input method settings from file"""
        config_file = "data/input_settings.json"
        defaults = {
            "click_method": "SetCursorPos",
            "find_image_click_method": "SetCursorPos",
            "drag_method": "SetCursorPos",
            "show_guide_on_startup": True
        }
        
        if not os.path.exists(config_file):
            # Create default settings
            os.makedirs("data", exist_ok=True)
            with open(config_file, "w", encoding="utf-8") as f:
                json.dump(defaults, f, indent=2)
            return defaults
        
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                settings = json.load(f)
            # Merge with defaults for missing keys
            for key, val in defaults.items():
                if key not in settings:
                    settings[key] = val
            return settings
        except Exception as e:
            log(f"[UI] Failed to load input settings: {e}")
            return defaults
    
    def _save_input_settings(self):
        """Save input method settings to file"""
        config_file = "data/input_settings.json"
        try:
            os.makedirs("data", exist_ok=True)
            with open(config_file, "w", encoding="utf-8") as f:
                json.dump(self._input_settings, f, indent=2)
            log(f"[UI] Saved input settings")
        except Exception as e:
            log(f"[UI] Failed to save input settings: {e}")
    
    # ================= WORKER ACTIONS PERSISTENCE =================
    
    def _load_worker_actions(self):
        """Load saved worker actions from file"""
        config_file = "data/worker_actions.json"
        if not os.path.exists(config_file):
            return
        
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # Check for embedded images
            images = data.get("images", {})
            worker_data = data.get("workers", {})
            
            if images:
                # Extract images to temp folder
                import base64
                import tempfile
                temp_dir = os.path.join(tempfile.gettempdir(), "macro_images", "worker_actions")
                os.makedirs(temp_dir, exist_ok=True)
                
                for img_key, img_b64 in images.items():
                    try:
                        img_data = base64.b64decode(img_b64)
                        # Ensure proper extension
                        if not img_key.endswith(('.png', '.jpg', '.jpeg', '.bmp')):
                            img_key_with_ext = img_key + '.png'
                        else:
                            img_key_with_ext = img_key
                        img_path = os.path.join(temp_dir, img_key_with_ext)
                        with open(img_path, "wb") as f:
                            f.write(img_data)
                        log(f"[UI] Extracted worker action image: {img_path}")
                    except Exception as e:
                        log(f"[UI] Failed to extract worker action image {img_key}: {e}")
            
            # Load actions for each worker
            for worker_id_str, actions_data in worker_data.items():
                worker_id = int(worker_id_str)
                actions = []
                
                for action_data in actions_data:
                    # Update embedded image paths
                    if images:
                        if action_data.get("action") == "FIND_IMAGE":
                            path = action_data.get("value", {}).get("template_path", "")
                            if path.startswith("@embedded:"):
                                img_key = path.replace("@embedded:", "")
                                # Ensure extension
                                if not img_key.endswith(('.png', '.jpg', '.jpeg', '.bmp')):
                                    img_key += '.png'
                                resolved_path = os.path.join(temp_dir, img_key)
                                action_data["value"]["template_path"] = resolved_path
                                log(f"[UI] Resolved FIND_IMAGE template: {resolved_path}")
                        
                        if action_data.get("action") == "WAIT_SCREEN_CHANGE":
                            path = action_data.get("value", {}).get("reference_image", "")
                            if path.startswith("@embedded:"):
                                img_key = path.replace("@embedded:", "")
                                if not img_key.endswith(('.png', '.jpg', '.jpeg', '.bmp')):
                                    img_key += '.png'
                                resolved_path = os.path.join(temp_dir, img_key)
                                action_data["value"]["reference_image"] = resolved_path
                    
                    actions.append(Action.from_dict(action_data))
                
                if actions:
                    self._worker_actions[worker_id] = actions
            
            if self._worker_actions:
                log(f"[UI] Loaded worker actions for {len(self._worker_actions)} workers")
                
        except Exception as e:
            log(f"[UI] Failed to load worker actions: {e}")
    
    def _save_worker_actions(self):
        """Save worker actions to file with embedded images"""
        config_file = "data/worker_actions.json"
        
        if not self._worker_actions:
            # Delete file if no worker actions
            if os.path.exists(config_file):
                os.remove(config_file)
            return
        
        import base64
        
        try:
            worker_data = {}
            images_embedded = {}
            image_count = 0
            
            for worker_id, actions in self._worker_actions.items():
                actions_data = []
                
                for action in actions:
                    action_dict = action.to_dict()
                    
                    # Embed FIND_IMAGE templates
                    if action.action == "FIND_IMAGE" and action.value.get("template_path"):
                        old_path = action.value["template_path"]
                        if os.path.exists(old_path) and not old_path.startswith("@embedded:"):
                            with open(old_path, "rb") as img_file:
                                img_data = base64.b64encode(img_file.read()).decode('utf-8')
                            
                            filename = os.path.basename(old_path)
                            img_key = f"w{worker_id}_img_{image_count:03d}_{filename}"
                            images_embedded[img_key] = img_data
                            action_dict["value"]["template_path"] = f"@embedded:{img_key}"
                            image_count += 1
                    
                    # Embed WAIT_SCREEN_CHANGE reference
                    if action.action == "WAIT_SCREEN_CHANGE" and action.value.get("reference_image"):
                        old_path = action.value["reference_image"]
                        if os.path.exists(old_path) and not old_path.startswith("@embedded:"):
                            with open(old_path, "rb") as img_file:
                                img_data = base64.b64encode(img_file.read()).decode('utf-8')
                            
                            filename = os.path.basename(old_path)
                            img_key = f"w{worker_id}_img_{image_count:03d}_{filename}"
                            images_embedded[img_key] = img_data
                            action_dict["value"]["reference_image"] = f"@embedded:{img_key}"
                            image_count += 1
                    
                    actions_data.append(action_dict)
                
                worker_data[str(worker_id)] = actions_data
            
            # Save to file
            os.makedirs(os.path.dirname(config_file), exist_ok=True)
            data = {
                "version": "1.0",
                "workers": worker_data,
                "images": images_embedded
            }
            
            with open(config_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            log(f"[UI] Saved worker actions: {len(self._worker_actions)} workers, {image_count} images")
            
        except Exception as e:
            log(f"[UI] Failed to save worker actions: {e}")

    # Khi chọn vùng, lưu lại vùng crop
    def on_region_selected(self, region):
        self._capture_crop_region = region  # (x1, y1, x2, y2)
        self._capture_target_name = f"Region {region}"
        self._target_btn_text.set(f"🎯 {self._capture_target_name}")

    # ================= UI =================

    def _build_ui(self):
        root = self.root

        # ===== APPLY MODERN DARK THEME =====
        ModernStyle.apply_dark_theme(root)
        S = ModernStyle  # Shorthand
        
        # Configure root window
        root.configure(bg=S.BG_PRIMARY)
        
        # ===== TOP TOOLBAR: Modern design with icon + label =====
        toolbar_frame = tk.Frame(root, bg=S.BG_PRIMARY)
        toolbar_frame.pack(fill="x", padx=S.PAD_SM, pady=S.PAD_SM)
        
        # Left side - Main action buttons
        btn_group_left = tk.Frame(toolbar_frame, bg=S.BG_PRIMARY)
        btn_group_left.pack(side="left")

        # Record button (toggle) - Red
        self.btn_record = S.create_toolbar_button(
            btn_group_left, "Ghi", "⏺", self._toggle_record, 
            color=S.BTN_RECORD, width=9
        )
        self.btn_record.pack(side="left", padx=S.PAD_XS)

        # Play button - Green
        self.btn_play = S.create_toolbar_button(
            btn_group_left, "Phát", "▶", self._toggle_play,
            color=S.BTN_PLAY, width=8
        )
        self.btn_play.pack(side="left", padx=S.PAD_XS)

        # Pause/Resume button (toggle) - Orange
        self.btn_pause = S.create_toolbar_button(
            btn_group_left, "Tạm dừng", "⏸", self._toggle_pause,
            color=S.BTN_PAUSE, width=10
        )
        self.btn_pause.pack(side="left", padx=S.PAD_XS)

        # Stop button - Gray
        self.btn_stop = S.create_toolbar_button(
            btn_group_left, "Dừng", "⏹", self._stop_all,
            color=S.BTN_STOP, width=7
        )
        self.btn_stop.pack(side="left", padx=S.PAD_XS)
        
        # Separator
        sep1 = tk.Frame(btn_group_left, bg=S.BORDER_COLOR, width=1, height=22)
        sep1.pack(side="left", padx=S.PAD_SM, pady=2)
        
        # Target Window button (for capture) - Purple
        self._target_btn_text = tk.StringVar(value="📺 Screen")  # Default: Full screen
        self.btn_target = S.create_toolbar_button(
            btn_group_left, "Màn hình", "📷", self._select_capture_target,
            color=S.BTN_SCREEN, width=10
        )
        self.btn_target.pack(side="left", padx=S.PAD_XS)
        
        # Separator
        sep2 = tk.Frame(btn_group_left, bg=S.BORDER_COLOR, width=1, height=22)
        sep2.pack(side="left", padx=S.PAD_SM, pady=2)
        
        # Settings button
        self.btn_settings = S.create_toolbar_button(
            btn_group_left, "Cài đặt", "⚙", self._open_settings_dialog,
            color=S.BTN_SETTINGS, width=9
        )
        self.btn_settings.pack(side="left", padx=S.PAD_XS)
        
        # Guide button
        self.btn_guide = S.create_toolbar_button(
            btn_group_left, "Hướng dẫn", "📖", self._show_guide_dialog,
            color=S.ACCENT_BLUE, width=11
        )
        self.btn_guide.pack(side="left", padx=S.PAD_XS)
        
        # Right side - Status
        status_frame = tk.Frame(toolbar_frame, bg=S.BG_PRIMARY)
        status_frame.pack(side="right")
        
        self._status_var = tk.StringVar(value="● Sẵn sàng")
        self._status_label = tk.Label(
            status_frame, textvariable=self._status_var,
            font=(S.FONT_FAMILY, S.FONT_SIZE_MD, "bold"), 
            fg=S.ACCENT_GREEN, bg=S.BG_PRIMARY
        )
        self._status_label.pack(side="right", padx=S.PAD_SM)
        
        # Helper method to update status with appropriate color
        def update_status(text, status_type="ready"):
            """Update status text and color. Types: ready, recording, playing, paused, stopped, error"""
            colors = {
                "ready": S.ACCENT_GREEN,
                "recording": S.ACCENT_RED,
                "playing": S.ACCENT_GREEN,
                "paused": S.ACCENT_ORANGE,
                "stopped": S.FG_MUTED,
                "error": S.ACCENT_RED,
            }
            self._status_var.set(text)
            self._status_label.config(fg=colors.get(status_type, S.FG_PRIMARY))
        self._update_status = update_status
        
        # Update button text with hotkeys
        self._update_button_hotkey_text()

        # ===== FOOTER: Signature =====
        footer_frame = tk.Frame(root, bg=S.BG_PRIMARY)
        footer_frame.pack(side="bottom", fill="x", pady=(0, 2))
        
        tk.Label(footer_frame, text="Copyright © 2026 Szuyu. All rights reserved. Developed for internal automation. Unauthorized distribution is prohibited.", 
                 font=(S.FONT_FAMILY, S.FONT_SIZE_SM, "italic"),
                 bg=S.BG_PRIMARY, fg=S.FG_MUTED).pack(side="top", pady=2)

        # ===== MAIN CONTAINER: Two panels side by side =====
        container = tk.Frame(root, bg=S.BG_PRIMARY)
        container.pack(fill="both", expand=True, padx=S.PAD_SM, pady=(0, S.PAD_SM))

        # ===== LEFT PANEL: Worker Status =====
        worker_frame = S.create_section_frame(container, "Trạng thái Worker", icon="🎮")
        worker_frame.pack(side="left", fill="both", expand=False, padx=(0, S.PAD_XS), pady=0)
        worker_frame.configure(width=380)
        worker_frame.pack_propagate(False)

        # Worker mini buttons - 2 rows for better layout
        worker_btn_frame = tk.Frame(worker_frame, bg=S.BG_CARD)
        worker_btn_frame.pack(fill="x", padx=S.PAD_XS, pady=S.PAD_XS)

       # --- CẤU TRÚC MỚI: Chia làm 2 cột ---

        # 1. Tạo Frame chứa các nút nhỏ bên trái (Refresh, Set Worker, Play, Stop)
        left_frame = tk.Frame(worker_btn_frame, bg=S.BG_CARD)
        left_frame.pack(side="left", fill="y") # Chỉ fill chiều dọc

        # --- Row 1 (trong left_frame): Refresh & Set Worker ---
        btn_row1 = tk.Frame(left_frame, bg=S.BG_CARD)
        btn_row1.pack(fill="x", pady=(0, S.PAD_XS)) # Padding dưới để tách row 1 và 2

        for text, icon, cmd, color in [
            ("Làm mới", "🔄", self.refresh_workers, S.BTN_SECONDARY),
            ("Set Worker", "⚙", self.set_worker_dialog, S.ACCENT_BLUE),
        ]:
            btn = tk.Button(btn_row1, text=f"{icon} {text}", command=cmd,
                           bg=color, fg=S.FG_PRIMARY,
                           font=(S.FONT_FAMILY, S.FONT_SIZE_SM),
                           relief="flat", cursor="hand2", width=11)
            btn.pack(side="left", padx=S.PAD_XS)
            btn.bind("<Enter>", lambda e, b=btn: b.config(bg=S.BG_TERTIARY))
            btn.bind("<Leave>", lambda e, b=btn, c=color: b.config(bg=c))

        # --- Row 2 (trong left_frame): Play All & Stop All ---
        btn_row2 = tk.Frame(left_frame, bg=S.BG_CARD)
        btn_row2.pack(fill="x")

        for text, icon, cmd, color in [
            ("Play All", "▶", self._play_all_workers, S.ACCENT_GREEN),
            ("Stop All", "⏹", self._stop_all_workers, S.ACCENT_RED),
        ]:
            btn = tk.Button(btn_row2, text=f"{icon} {text}", command=cmd,
                           bg=color, fg=S.FG_PRIMARY,
                           font=(S.FONT_FAMILY, S.FONT_SIZE_SM),
                           relief="flat", cursor="hand2", width=11)
            btn.pack(side="left", padx=S.PAD_XS)
            btn.bind("<Enter>", lambda e, b=btn: b.config(bg=S.BG_TERTIARY))
            btn.bind("<Leave>", lambda e, b=btn, c=color: b.config(bg=c))

        # 2. Tạo nút Check to bự bên phải (nằm ngoài left_frame)
        btn_check = tk.Button(worker_btn_frame, text="🔍 Check Giả Lập", command=self.check_status,
                           bg=S.ACCENT_CYAN, fg=S.FG_PRIMARY,
                           font=(S.FONT_FAMILY, S.FONT_SIZE_SM + 1, "bold"), # Font to hơn chút cho đẹp
                           relief="flat", cursor="hand2")
        
        # side="left": Nằm tiếp theo sau left_frame
        # fill="both": Dãn ra cả chiều ngang và dọc
        # expand=True: Chiếm hết chỗ trống còn lại
        btn_check.pack(side="left", fill="both", expand=True, padx=(S.PAD_XS, 0))

        # Hiệu ứng hover cho nút Check
        btn_check.bind("<Enter>", lambda e, b=btn_check: b.config(bg=S.BG_TERTIARY))
        btn_check.bind("<Leave>", lambda e, b=btn_check, c=S.ACCENT_CYAN: b.config(bg=c))
        
        # Row 3: Bulk Action Management
        btn_row3 = tk.Frame(worker_btn_frame, bg=S.BG_CARD)
        btn_row3.pack(fill="x", pady=(S.PAD_XS, 0))
        
        for text, icon, cmd, color in [
            # ("Đồng bộ→Global", "📥", self._sync_selected_to_global, S.ACCENT_PURPLE),
            # ("Hoàn tác→Global", "🔄", self._revert_selected_to_global, S.ACCENT_ORANGE),
        ]:
            btn = tk.Button(btn_row3, text=f"{icon} {text}", command=cmd,
                           bg=color, fg=S.FG_PRIMARY,
                           font=(S.FONT_FAMILY, S.FONT_SIZE_SM),
                           relief="flat", cursor="hand2", width=16)
            btn.pack(side="left", padx=S.PAD_XS)
            btn.bind("<Enter>", lambda e, b=btn: b.config(bg=S.BG_TERTIARY))
            btn.bind("<Leave>", lambda e, b=btn, c=color: b.config(bg=c))

        # Worker Treeview
        tree_frame = tk.Frame(worker_frame, bg=S.BG_CARD)
        tree_frame.pack(fill="both", expand=True, padx=S.PAD_XS, pady=(0, S.PAD_XS))

        columns = ("ID", "Name", "Worker", "Status")
        self.worker_tree = ttk.Treeview(tree_frame, columns=columns, height=14, show="headings", selectmode="extended")

        self.worker_tree.column("#0", width=0, stretch=tk.NO)
        self.worker_tree.column("ID", anchor=tk.CENTER, width=30, minwidth=25)
        self.worker_tree.column("Name", anchor=tk.W, width=150, minwidth=100)
        self.worker_tree.column("Worker", anchor=tk.CENTER, width=70, minwidth=50)
        self.worker_tree.column("Status", anchor=tk.CENTER, width=80, minwidth=60)

        for col in columns:
            self.worker_tree.heading(col, text=col, anchor=tk.CENTER if col != "Name" else tk.W)

        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.worker_tree.yview)
        self.worker_tree.configure(yscroll=scrollbar.set)

        self.worker_tree.pack(side=tk.LEFT, fill="both", expand=True)
        scrollbar.pack(side=tk.RIGHT, fill="y")

        self.worker_tree.bind("<Button-3>", self._on_worker_tree_right_click)
        # Double-click to open worker editor removed per user request
        self.worker_tree.bind("<Control-a>", self._select_all_workers)
        self.worker_tree_items = {}
        
        # Apply zebra striping
        S.apply_zebra_striping(self.worker_tree)

        # ===== RIGHT PANEL: Action List (Primary workspace) =====
        action_frame = S.create_section_frame(container, "Danh sách Action", icon="📋")
        action_frame.pack(side="left", fill="both", expand=True, padx=(S.PAD_XS, 0), pady=0)

        # Action control buttons - 2 rows for better layout
        action_btn_frame = tk.Frame(action_frame, bg=S.BG_CARD)
        action_btn_frame.pack(fill="x", padx=S.PAD_XS, pady=S.PAD_XS)

        # Row 1: Main action buttons
        action_row1 = tk.Frame(action_btn_frame, bg=S.BG_CARD)
        action_row1.pack(fill="x", pady=(0, S.PAD_XS))

        action_buttons_row1 = [
            ("➕ Thêm", self._open_add_action_dialog, S.ACCENT_GREEN, 7),
            ("✏️ Sửa", self._edit_selected_action, S.ACCENT_BLUE, 7),
            ("🗑 Xóa", self._remove_action, S.ACCENT_RED, 6),
            ("💾 Save", self._save_actions, S.ACCENT_PURPLE, 7),
            ("📂 Load", self._load_actions, S.ACCENT_ORANGE, 7),
            # ("⬆", self._move_action_up, S.BTN_SECONDARY, 2),
            # ("⬇", self._move_action_down, S.BTN_SECONDARY, 2),
        ]
        
        for text, cmd, color, w in action_buttons_row1:
            btn = tk.Button(action_row1, text=text, command=cmd,
                           bg=color, fg=S.FG_PRIMARY,
                           font=(S.FONT_FAMILY, S.FONT_SIZE_SM),
                           relief="flat", cursor="hand2", width=w)
            btn.pack(side="left", padx=S.PAD_XS)
            btn.bind("<Enter>", lambda e, b=btn: b.config(bg=S.BG_TERTIARY))
            btn.bind("<Leave>", lambda e, b=btn, c=color: b.config(bg=c))

        # Row 2: File operations
        # action_row1 = tk.Frame(action_btn_frame, bg=S.BG_CARD)
        # action_row1.pack(fill="x")

        # action_buttons_row1 = [
        #     ("💾 Lưu", self._save_actions, S.BTN_PRIMARY, 7),
        #     ("📂 Tải", self._load_actions, S.BTN_SECONDARY, 7),
        # ]
        
        # for text, cmd, color, w in action_buttons_row1:
        #     btn = tk.Button(action_row1, text=text, command=cmd,
        #                    bg=color, fg=S.FG_PRIMARY,
        #                    font=(S.FONT_FAMILY, S.FONT_SIZE_SM),
        #                    relief="flat", cursor="hand2", width=w)
        #     btn.pack(side="left", padx=S.PAD_XS)
        #     btn.bind("<Enter>", lambda e, b=btn: b.config(bg=S.BG_TERTIARY))
        #     btn.bind("<Leave>", lambda e, b=btn, c=color: b.config(bg=c))

        # Action Treeview with proper columns
        action_tree_frame = tk.Frame(action_frame, bg=S.BG_CARD)
        action_tree_frame.pack(fill="both", expand=True, padx=S.PAD_XS, pady=(0, S.PAD_XS))

        action_columns = ("#", "Action", "Value", "Label", "Comment")
        self.action_tree = ttk.Treeview(action_tree_frame, columns=action_columns, 
                                        height=16, show="headings", selectmode="extended")

        self.action_tree.column("#0", width=0, stretch=tk.NO)
        self.action_tree.column("#", anchor=tk.CENTER, width=30, minwidth=25)
        self.action_tree.column("Action", anchor=tk.W, width=90, minwidth=70)
        self.action_tree.column("Value", anchor=tk.W, width=180, minwidth=120)
        self.action_tree.column("Label", anchor=tk.W, width=70, minwidth=50)
        self.action_tree.column("Comment", anchor=tk.W, width=120, minwidth=80)

        for col in action_columns:
            anchor = tk.CENTER if col == "#" else tk.W
            self.action_tree.heading(col, text=col, anchor=anchor)

        action_scrollbar = ttk.Scrollbar(action_tree_frame, orient=tk.VERTICAL, command=self.action_tree.yview)
        self.action_tree.configure(yscroll=action_scrollbar.set)

        self.action_tree.pack(side=tk.LEFT, fill="both", expand=True)
        action_scrollbar.pack(side=tk.RIGHT, fill="y")
        
        # Alias for backward compatibility with old code referencing command_tree
        self.command_tree = self.action_tree
        self.command_tree_items = {}
        
        # Bindings
        self.action_tree.bind("<Double-1>", self._on_action_double_click)
        self.action_tree.bind("<Button-3>", self._on_action_right_click)
        self.action_tree.bind("<Control-a>", self._select_all_actions)
        self.action_tree.bind("<Control-c>", self._copy_selected_actions_key)
        self.action_tree.bind("<Control-v>", self._paste_actions_key)
        self.action_tree.bind("<Control-x>", self._cut_selected_actions_key)
        self.action_tree.bind("<Delete>", self._delete_selected_actions)
        self.action_tree.bind("<BackSpace>", self._delete_selected_actions)
        
        # Drag and Drop
        self._drag_data = {"items": [], "start_y": 0}
        self.action_tree.bind("<ButtonPress-1>", self._on_drag_start)
        self.action_tree.bind("<B1-Motion>", self._on_drag_motion)
        self.action_tree.bind("<ButtonRelease-1>", self._on_drag_end)

        self.action_tree_items = {}
        
        # Apply zebra striping to action tree
        S.apply_zebra_striping(self.action_tree)
        
        # Setup global hotkeys
        self._setup_global_hotkeys()
    
    def _build_playback_log_panel(self, parent, S):
        """Build the playback log panel showing current action execution"""
        # Create frame at bottom of window
        log_frame = S.create_section_frame(parent, "Nhật ký Phát", icon="📊")
        log_frame.pack(side="bottom", fill="x", padx=S.PAD_XS, pady=(S.PAD_XS, 0))
        log_frame.configure(height=150)
        log_frame.pack_propagate(False)
        
        # Container for log listbox
        log_container = tk.Frame(log_frame, bg=S.BG_CARD)
        log_container.pack(fill="both", expand=True, padx=S.PAD_XS, pady=S.PAD_XS)
        
        # Header row
        header_frame = tk.Frame(log_container, bg=S.BG_TERTIARY)
        header_frame.pack(fill="x")
        
        # Column headers
        tk.Label(header_frame, text="#", width=4, anchor="center",
                bg=S.BG_TERTIARY, fg=S.FG_MUTED, font=(S.FONT_FAMILY, S.FONT_SIZE_SM, "bold")
        ).pack(side="left", padx=2)
        tk.Label(header_frame, text="Hành động", width=12, anchor="w",
                bg=S.BG_TERTIARY, fg=S.FG_MUTED, font=(S.FONT_FAMILY, S.FONT_SIZE_SM, "bold")
        ).pack(side="left", padx=2)
        tk.Label(header_frame, text="Nhãn", width=10, anchor="w",
                bg=S.BG_TERTIARY, fg=S.FG_MUTED, font=(S.FONT_FAMILY, S.FONT_SIZE_SM, "bold")
        ).pack(side="left", padx=2)
        tk.Label(header_frame, text="Trạng thái", width=12, anchor="center",
                bg=S.BG_TERTIARY, fg=S.FG_MUTED, font=(S.FONT_FAMILY, S.FONT_SIZE_SM, "bold")
        ).pack(side="left", fill="x", expand=True, padx=2)
        
        # Scrollable frame for action rows
        canvas_frame = tk.Frame(log_container, bg=S.BG_SECONDARY)
        canvas_frame.pack(fill="both", expand=True)
        
        # Canvas for scrolling
        self._playback_log_canvas = tk.Canvas(canvas_frame, bg=S.BG_SECONDARY, 
                                               highlightthickness=0, height=90)
        scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical", 
                                  command=self._playback_log_canvas.yview)
        
        self._playback_log_inner = tk.Frame(self._playback_log_canvas, bg=S.BG_SECONDARY)
        
        self._playback_log_canvas.create_window((0, 0), window=self._playback_log_inner, anchor="nw")
        self._playback_log_inner.bind("<Configure>", 
            lambda e: self._playback_log_canvas.configure(scrollregion=self._playback_log_canvas.bbox("all")))
        
        self._playback_log_canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Enable mouse wheel scrolling
        def _on_mousewheel(event):
            self._playback_log_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        self._playback_log_canvas.bind_all("<MouseWheel>", _on_mousewheel)
        
        # Store row widgets for highlighting
        self._playback_log_rows = []
        self._playback_log_style = S
        self._current_highlighted_row = -1
    
    def _populate_playback_log(self):
        """Populate playback log with current actions"""
        S = self._playback_log_style
        
        # Clear existing rows
        for widget in self._playback_log_inner.winfo_children():
            widget.destroy()
        self._playback_log_rows = []
        self._current_highlighted_row = -1
        
        # Add rows for each action
        for idx, action in enumerate(self.actions):
            row_frame = tk.Frame(self._playback_log_inner, bg=S.BG_SECONDARY)
            row_frame.pack(fill="x", pady=1)
            
            # Index
            idx_label = tk.Label(row_frame, text=str(idx), width=4, anchor="center",
                                bg=S.BG_SECONDARY, fg=S.FG_MUTED, 
                                font=(S.FONT_FAMILY, S.FONT_SIZE_SM))
            idx_label.pack(side="left", padx=2)
            
            # Action type
            action_label = tk.Label(row_frame, text=action.action, width=12, anchor="w",
                                   bg=S.BG_SECONDARY, fg=S.FG_PRIMARY,
                                   font=(S.FONT_FAMILY, S.FONT_SIZE_SM))
            action_label.pack(side="left", padx=2)
            
            # Label
            label_text = action.label if action.label else "-"
            label_lbl = tk.Label(row_frame, text=label_text, width=10, anchor="w",
                                bg=S.BG_SECONDARY, fg=S.ACCENT_BLUE,
                                font=(S.FONT_FAMILY, S.FONT_SIZE_SM))
            label_lbl.pack(side="left", padx=2)
            
            # Status
            status_label = tk.Label(row_frame, text="⏳", width=12, anchor="center",
                                   bg=S.BG_SECONDARY, fg=S.FG_MUTED,
                                   font=(S.FONT_FAMILY, S.FONT_SIZE_SM))
            status_label.pack(side="left", fill="x", expand=True, padx=2)
            
            # Store row data
            self._playback_log_rows.append({
                "frame": row_frame,
                "idx": idx_label,
                "action": action_label,
                "label": label_lbl,
                "status": status_label
            })
    
    def _highlight_playback_row(self, index: int, status: str = "running"):
        """Highlight the currently executing action row
        
        Args:
            index: Action index to highlight
            status: 'running', 'done', 'error', 'skipped'
        """
        if not hasattr(self, '_playback_log_rows') or not self._playback_log_rows:
            return
        
        S = self._playback_log_style
        
        # Define colors for different states
        colors = {
            "running": {"bg": "#1B5E20", "fg": "#FFFFFF", "status": "▶ Running", "status_fg": S.ACCENT_GREEN},
            "done": {"bg": S.BG_SECONDARY, "fg": S.FG_MUTED, "status": "✓ Done", "status_fg": S.ACCENT_GREEN},
            "error": {"bg": "#4A1010", "fg": "#FF8A80", "status": "✗ Error", "status_fg": S.ACCENT_RED},
            "skipped": {"bg": S.BG_SECONDARY, "fg": S.FG_MUTED, "status": "⊘ Skip", "status_fg": S.ACCENT_ORANGE},
            "pending": {"bg": S.BG_SECONDARY, "fg": S.FG_MUTED, "status": "⏳", "status_fg": S.FG_MUTED}
        }
        
        state = colors.get(status, colors["pending"])
        
        # Update previous highlighted row to done (if different)
        if self._current_highlighted_row >= 0 and self._current_highlighted_row != index:
            if self._current_highlighted_row < len(self._playback_log_rows):
                prev_row = self._playback_log_rows[self._current_highlighted_row]
                done = colors["done"]
                prev_row["frame"].configure(bg=done["bg"])
                for widget in ["idx", "action", "label"]:
                    prev_row[widget].configure(bg=done["bg"], fg=done["fg"])
                prev_row["status"].configure(bg=done["bg"], fg=done["status_fg"], text=done["status"])
        
        # Highlight current row
        if 0 <= index < len(self._playback_log_rows):
            row = self._playback_log_rows[index]
            row["frame"].configure(bg=state["bg"])
            for widget in ["idx", "action", "label"]:
                row[widget].configure(bg=state["bg"], fg=state["fg"])
            row["status"].configure(bg=state["bg"], fg=state["status_fg"], text=state["status"])
            
            self._current_highlighted_row = index
            
            # Auto-scroll to visible
            self._playback_log_canvas.update_idletasks()
            row_y = row["frame"].winfo_y()
            canvas_height = self._playback_log_canvas.winfo_height()
            self._playback_log_canvas.yview_moveto(max(0, (row_y - canvas_height/2) / 
                                                       max(1, self._playback_log_inner.winfo_height())))
    
    def _clear_playback_log_highlight(self):
        """Clear all highlights and reset to pending state"""
        if not hasattr(self, '_playback_log_rows'):
            return
        
        S = self._playback_log_style
        for row in self._playback_log_rows:
            row["frame"].configure(bg=S.BG_SECONDARY)
            for widget in ["idx", "action", "label"]:
                row[widget].configure(bg=S.BG_SECONDARY, fg=S.FG_MUTED)
            row["status"].configure(bg=S.BG_SECONDARY, fg=S.FG_MUTED, text="⏳")
        
        self._current_highlighted_row = -1
    
    def _on_worker_tree_click(self, event):
        """Handle click on worker tree for per-row actions"""
        # No longer needed since Actions column removed
        # Right-click menu now handles all actions
        pass
    
    def _select_all_workers(self, event=None):
        """Select all workers in worker tree (Ctrl+A)"""
        for item in self.worker_tree.get_children():
            self.worker_tree.selection_add(item)
        return "break"  # Prevent default Ctrl+A behavior
    
    def _show_worker_action_menu(self, event, worker_id: int):
        """Show popup menu with Play/Pause/Stop actions for worker (supports multi-selection)"""
        menu = tk.Menu(self.root, tearoff=0)
        
        # Get all selected workers
        selected_items = self.worker_tree.selection()
        selected_worker_ids = []
        for item in selected_items:
            values = self.worker_tree.item(item, "values")
            if values:
                selected_worker_ids.append(int(values[0]))
        
        # If nothing selected or clicked worker not in selection, use single worker
        if not selected_worker_ids or worker_id not in selected_worker_ids:
            selected_worker_ids = [worker_id]
        
        is_multi = len(selected_worker_ids) > 1
        
        # Find worker
        worker = None
        for w in self.workers:
            if w.id == worker_id:
                worker = w
                break
        
        if not worker:
            return
        
        # Single-worker actions
        if not is_multi:
            menu.add_command(label="▶ Phát", command=lambda: self._play_worker(worker_id))
            menu.add_command(label="⏸ Tạm dừng", command=lambda: self._pause_worker(worker_id))
            menu.add_command(label="⏹ Dừng", command=lambda: self._stop_worker(worker_id))
            menu.add_separator()
            menu.add_command(label="🔄 Khởi động lại", command=lambda: self._restart_worker(worker_id))
            menu.add_separator()
            
            # Edit custom actions
            has_custom = worker_id in self._worker_actions and len(self._worker_actions[worker_id]) > 0
            edit_label = f"✏️ Sửa Actions ({len(self._worker_actions.get(worker_id, []))} tùy chỉnh)" if has_custom else "✏️ Sửa Actions"
            menu.add_command(label=edit_label, command=lambda: self._edit_worker_actions(worker_id))
            
            if has_custom:
                menu.add_command(label="🗑️ Xóa Actions tùy chỉnh", command=lambda: self._clear_worker_actions(worker_id))
        else:
            # Multi-selection actions
            menu.add_command(label=f"📋 {len(selected_worker_ids)} Worker đã chọn", state="disabled")
            menu.add_separator()
            menu.add_command(label="📥 Đồng bộ đã chọn → Global", 
                           command=lambda: self._sync_workers_to_global(selected_worker_ids))
            menu.add_command(label="🔄 Hoàn tác đã chọn → Global", 
                           command=lambda: self._revert_workers_to_global(selected_worker_ids))
            # Multi-Worker Editor removed per user request
        
        # Display menu at cursor position
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()
    
    def _on_worker_tree_right_click(self, event):
        """Handle right-click on worker tree to show context menu"""
        item = self.worker_tree.identify_row(event.y)
        
        if not item:
            return
        
        # Get worker ID from the row
        values = self.worker_tree.item(item, "values")
        if not values:
            return
        
        worker_id = int(values[0])
        
        # Show action popup menu
        self._show_worker_action_menu(event, worker_id)
    
    def _play_worker(self, worker_id: int):
        """Start or resume script execution for a worker"""
        worker = self._find_worker(worker_id)
        if not worker:
            return
        
        # Get actions - priority: worker custom > loaded file > global actions
        actions = self._get_actions_for_worker(worker_id=worker_id)
        if not actions:
            messagebox.showwarning("No Script", "Chưa có actions. Vui lòng thêm actions trước.")
            return
        
        # Get target hwnd from worker
        target_hwnd = worker.emulator.hwnd if hasattr(worker, 'emulator') and hasattr(worker.emulator, 'hwnd') else None
        
        # Start playback using UI system (có mini toolbar + playlog)
        self._start_playback_for_worker(worker_id, actions, target_hwnd)
        
        # Log source
        if worker_id in self._worker_actions and self._worker_actions[worker_id]:
            log(f"[UI] Worker {worker_id}: Started with CUSTOM actions ({len(actions)} actions)")
        else:
            log(f"[UI] Worker {worker_id}: Started with GLOBAL actions ({len(actions)} actions)")
    
    def _get_actions_for_worker(self, worker_id=None):
        """Get action list for a specific worker with 3-level priority system
        
        Args:
            worker_id: If provided, check for worker-specific custom actions first
            
        Returns:
            List of actions (dict format) or None
            
        Priority System:
            1. Individual Custom Actions: Worker-specific actions from Multi-Worker Editor
            2. Multi-Worker Custom Actions: Group-assigned actions (future feature)
            3. Default Action List: Global action list or loaded script
        """
        # Priority 1: Individual Custom Actions (Worker-specific)
        if worker_id is not None:
            worker_actions = self._worker_actions.get(worker_id, [])
            if worker_actions:
                # Return worker-specific Action objects directly
                return worker_actions
        
        # Priority 2: Multi-Worker Custom Actions
        # TODO: Implement group-level custom actions in future
        # if worker_id in self._multi_worker_group_actions:
        #     return self._multi_worker_group_actions[worker_id]
        
        # Priority 3: Default Action List
        # Check loaded script first
        if self.current_script:
            # Extract actions from script.sequence
            return [cmd.params for cmd in self.current_script.sequence if hasattr(cmd, 'params')]
        
        # Fall back to global UI actions
        if self.actions:
            return self.actions
        
        return None
    
    def _start_playback_for_worker(self, worker_id: int, actions: list, target_hwnd: int = None):
        """Start playback for specific worker with mini toolbar"""
        # Stop current playback if any
        if self._playback_running:
            self._stop_playback()
            time.sleep(0.1)
        
        # Set playback state
        self._playback_running = True
        self._playback_stop_event.clear()
        self._current_action_index = 0
        self._playback_worker_id = worker_id  # Track which worker is playing
        
        # Defensive normalization: Ensure all actions are Action objects
        # (Worker actions should already be Action objects, but script.sequence may return dicts)
        if actions and isinstance(actions[0], dict):
            log(f"[UI] Converting dict actions to Action objects for worker {worker_id}")
            normalized_actions = [Action.from_dict(a) for a in actions]
        else:
            normalized_actions = actions
        
        # Set worker-specific actions and target for playback loop
        self.actions = normalized_actions  # Override global actions
        self._target_hwnd = target_hwnd  # Set target window
        
        log(f"[UI] Starting playback for worker {worker_id}: {len(normalized_actions)} actions")
        
        # Start playback thread
        def playback_thread():
            try:
                self._playback_loop()  # No args - uses self.actions and self._target_hwnd
            except Exception as e:
                log(f"[UI] Worker {worker_id} playback error: {e}")
                import traceback
                log(f"[UI] Traceback: {traceback.format_exc()}")
            finally:
                self._playback_running = False
                if hasattr(self, '_playback_worker_id'):
                    del self._playback_worker_id
        
        thread = threading.Thread(target=playback_thread, daemon=True)
        thread.start()
    
    def _pause_worker(self, worker_id: int):
        """Pause script execution for a worker"""
        worker = self._find_worker(worker_id)
        if not worker:
            return
        
        if hasattr(worker, 'pause'):
            worker.pause()
            log(f"[UI] Worker {worker_id}: Paused")
    
    def _stop_worker(self, worker_id: int):
        """Stop script execution for a worker"""
        # Stop independent playback thread if exists
        if hasattr(self, '_worker_stop_events') and worker_id in self._worker_stop_events:
            self._worker_stop_events[worker_id].set()
            log(f"[UI] Worker {worker_id}: Stopped (independent playback)")
            return
        
        # Stop UI playback if this worker is currently playing
        if hasattr(self, '_playback_worker_id') and self._playback_worker_id == worker_id:
            self._stop_playback()
            log(f"[UI] Worker {worker_id}: Stopped (UI playback)")
            return
        
        log(f"[UI] Worker {worker_id}: Not running")
    
    def _restart_worker(self, worker_id: int):
        """Restart script execution for a worker"""
        self._stop_worker(worker_id)
        time.sleep(0.2)  # Wait for stop to complete
        self._play_worker(worker_id)
    
    def _play_all_workers(self):
        """Start/Resume all workers - each runs independently with mini toolbar"""
        if not self.workers:
            messagebox.showinfo("Thông tin", "Không có worker nào")
            return
        
        log(f"[UI] Play All: Total workers in list: {len(self.workers)}")
        
        started_count = 0
        for worker in self.workers:
            log(f"[UI] Checking worker {worker.id}: hwnd={worker.hwnd}, emulator={getattr(worker, 'emulator_name', 'N/A')}")
            
            actions = self._get_actions_for_worker(worker_id=worker.id)
            if not actions:
                log(f"[UI] Worker {worker.id}: No actions available, skipping")
                continue
            
            log(f"[UI] Worker {worker.id}: Found {len(actions)} actions to execute")
            
            # Get target hwnd
            target_hwnd = worker.hwnd if hasattr(worker, 'hwnd') else None
            
            # Start independent playback thread for each worker
            self._start_independent_worker_playback(worker.id, actions, target_hwnd)
            started_count += 1
        
        # Create Play All mini toolbar
        if started_count > 0:
            self._create_play_all_mini_toolbar(started_count)
        
        log(f"[UI] Play All: Started {started_count}/{len(self.workers)} workers")

    
    def _get_worker_display_name(self, worker_id: int) -> str:
        """Get display name for worker (emulator name if available, else Worker ID)"""
        worker = self._find_worker(worker_id)
        if worker and hasattr(worker, 'emulator_name'):
            return worker.emulator_name
        return f"Worker {worker_id}"
    
    def _resolve_goto_target_for_worker(self, target: str, actions: list) -> int:
        """Resolve goto target string to action index for worker playback.
        
        Args:
            target: Goto target string ('Next', 'Start', 'End', 'Previous', or label name)
            actions: List of Action objects
            
        Returns:
            Target index (0-based). Returns -1 for 'End' to signal loop exit.
            Returns -2 for 'Exit macro' to signal stop.
        """
        if not target:
            return None  # Continue to next (default)
        
        target = target.strip()
        
        if target == "Next":
            return None  # Signal to continue to next action
        elif target == "Start":
            return 0  # Jump to first action
        elif target == "End":
            return -1  # Signal to exit loop
        elif target == "Exit macro":
            return -2  # Signal to stop playback
        elif target == "Previous":
            return -3  # Special: handled in loop (current - 1)
        else:
            # Find label by name
            label_name = target.replace("→ ", "").strip()
            
            for idx, act in enumerate(actions):
                act_label = ""
                # Check LABEL action's value.name
                if hasattr(act, 'action') and act.action == "LABEL":
                    act_label = act.value.get("name", "") if isinstance(act.value, dict) else ""
                # Also check action.label field (any action can have a label)
                if not act_label and hasattr(act, 'label') and act.label:
                    act_label = act.label
                    
                if act_label == label_name:
                    return idx  # Return 0-based index
            
            log(f"[GOTO] Warning: Label '{label_name}' not found in actions")
            return None  # Label not found, continue to next
    
    def _start_independent_worker_playback(self, worker_id: int, actions: list, target_hwnd: int = None):
        """Start independent playback thread for a worker with real-time status tracking and goto support"""
        def playback_thread():
            stop_event = threading.Event()
            # Store stop event for this worker
            if not hasattr(self, '_worker_stop_events'):
                self._worker_stop_events = {}
            self._worker_stop_events[worker_id] = stop_event
            
            # Initialize status tracking dict (shared across threads)
            if not hasattr(self, '_worker_play_status'):
                self._worker_play_status = {}
            
            # Initialize goto result storage for this worker
            if not hasattr(self, '_worker_goto_targets'):
                self._worker_goto_targets = {}
            self._worker_goto_targets[worker_id] = None
            
            self._worker_play_status[worker_id] = {
                'current_action': 'Starting...',
                'current_idx': 0,
                'total': len(actions),
                'progress': 0,
                'status': 'Running'
            }
            
            # Get worker display name and ADB serial
            worker_name = self._get_worker_display_name(worker_id)
            worker = self._find_worker(worker_id)
            adb_serial = worker.adb_device if worker and hasattr(worker, 'adb_device') else None
            
            if adb_serial:
                log(f"[{worker_name}] Using ADB device: {adb_serial}")
            
            try:
                total_actions = len(actions)
                log(f"[{worker_name}] ▶ Started: {total_actions} actions")
                
                # Use while loop instead of for to support goto
                current_idx = 0
                
                while current_idx < total_actions:
                    if stop_event.is_set():
                        self._worker_play_status[worker_id]['status'] = 'Stopped'
                        log(f"[{worker_name}] ⏹ Stopped by user at {current_idx}/{total_actions} ({current_idx/total_actions*100:.0f}%)")
                        break
                    
                    action = actions[current_idx]
                    display_idx = current_idx + 1  # 1-based for display
                    
                    # Skip disabled actions (same as _playback_loop)
                    if hasattr(action, 'enabled') and not action.enabled:
                        log(f"[{worker_name}] {display_idx}/{total_actions} - SKIPPED (disabled)")
                        current_idx += 1
                        continue
                    
                    # Check pause (if using global pause)
                    while hasattr(self, '_playback_pause_event') and self._playback_pause_event.is_set():
                        if stop_event.is_set():
                            break
                        time.sleep(0.1)
                    
                    # Calculate progress
                    progress = (display_idx / total_actions) * 100
                    
                    # Execute action using _execute_action with adb_serial
                    try:
                        # Action is Action object, not dict
                        action_type = action.action if hasattr(action, 'action') else action.get('action', 'Unknown')
                        action_label = action.label if hasattr(action, 'label') and action.label else action_type
                        
                        # Update status dict for real-time UI
                        self._worker_play_status[worker_id].update({
                            'current_action': action_label,
                            'current_idx': display_idx,
                            'progress': progress
                        })
                        
                        log(f"[{worker_name}] {display_idx}/{total_actions} ({progress:.0f}%) - {action_type}")
                        
                        # Clear any previous goto target for this worker
                        self._worker_goto_targets[worker_id] = None
                        
                        # Execute action - it may set goto target via _set_worker_goto_target
                        self._execute_action_for_worker(action, target_hwnd or 0, adb_serial=adb_serial, worker_id=worker_id)
                        
                        # Check if action set a goto target
                        goto_target_str = self._worker_goto_targets.get(worker_id)
                        if goto_target_str:
                            resolved_idx = self._resolve_goto_target_for_worker(goto_target_str, actions)
                            
                            if resolved_idx == -1:  # End
                                log(f"[{worker_name}] ⏭ GOTO End - stopping playback")
                                break
                            elif resolved_idx == -2:  # Exit macro
                                log(f"[{worker_name}] ⏹ GOTO Exit macro - stopping playback")
                                stop_event.set()
                                break
                            elif resolved_idx == -3:  # Previous
                                new_idx = max(0, current_idx - 1)
                                log(f"[{worker_name}] ↩ GOTO Previous: {current_idx+1} → {new_idx+1}")
                                current_idx = new_idx
                                continue
                            elif resolved_idx is not None:
                                # Jump to specific index
                                log(f"[{worker_name}] ↪ GOTO '{goto_target_str}': {current_idx+1} → {resolved_idx+1}")
                                current_idx = resolved_idx
                                continue
                        
                        # Normal progression to next action
                        current_idx += 1
                        
                    except Exception as e:
                        log(f"[{worker_name}] ✗ Error at {display_idx}/{total_actions}: {e}")
                        current_idx += 1  # Continue to next on error
                
                if not stop_event.is_set() and current_idx >= total_actions:
                    self._worker_play_status[worker_id]['status'] = 'Complete'
                    log(f"[{worker_name}] ✓ Complete: {total_actions}/{total_actions} (100%)")
            except Exception as e:
                self._worker_play_status[worker_id]['status'] = 'Error'
                log(f"[{worker_name}] ✗ Playback error: {e}")
            finally:
                if hasattr(self, '_worker_stop_events') and worker_id in self._worker_stop_events:
                    del self._worker_stop_events[worker_id]
                if hasattr(self, '_worker_goto_targets') and worker_id in self._worker_goto_targets:
                    del self._worker_goto_targets[worker_id]
        
        thread = threading.Thread(target=playback_thread, daemon=True, name=f"Worker-{worker_id}-Playback")
        thread.start()
    
    def _execute_action_for_worker(self, action, target_hwnd: int, adb_serial: str = None, worker_id: int = None):
        """Execute action with worker context for proper goto handling.
        
        This wrapper sets _current_worker_context before calling _execute_action,
        allowing _handle_goto to store goto targets for the worker instead of
        modifying UI-level _current_action_index.
        
        Args:
            action: Action to execute
            target_hwnd: Target window handle
            adb_serial: ADB device serial
            worker_id: Worker ID for context
        """
        # Set worker context so _handle_goto knows to store goto target
        self._current_worker_context = worker_id
        
        try:
            self._execute_action(action, target_hwnd, adb_serial=adb_serial)
        finally:
            # Clear worker context
            self._current_worker_context = None
    
    def _stop_all_workers(self):
        """Stop all workers"""
        if not self.workers:
            return
        
        # Set stop events for all workers
        if hasattr(self, '_worker_stop_events'):
            for stop_event in self._worker_stop_events.values():
                stop_event.set()
        
        log(f"[UI] Stop All: Stopping {len(self.workers)} workers")
        
        # Close Play All mini toolbar
        if hasattr(self, '_play_all_toolbar') and self._play_all_toolbar:
            try:
                self._play_all_toolbar.destroy()
                self._play_all_toolbar = None
            except:
                pass
    
    def _create_play_all_mini_toolbar(self, worker_count: int):
        """
        Create mini toolbar for Play All with 3-panel layout (2026 Clean UI)
        
        Panel 1: Worker Identity (Name/ID)
        Panel 2: Action Details (Current action label)
        Panel 3: Execution Status (Real-time progress)
        
        REMOVED: Error logs, debug buttons, filter buttons (per spec)
        FOCUS: Real-time execution tracking only
        """
        S = ModernStyle
        
        # Close existing toolbar if any
        if hasattr(self, '_play_all_toolbar') and self._play_all_toolbar:
            try:
                self._play_all_toolbar.destroy()
            except:
                pass
        
        # Create new toolbar window
        toolbar = tk.Toplevel(self.root)
        toolbar.title("▶ Phát Tất cả - Theo dõi Thực thi")
        toolbar.geometry("900x450")
        toolbar.configure(bg=S.BG_PRIMARY)
        toolbar.attributes('-topmost', True)
        
        self._play_all_toolbar = toolbar
        
        # Header with Stop button only (simplified)
        header = tk.Frame(toolbar, bg=S.BG_SECONDARY, height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        
        tk.Label(header, text=f"▶ Phát Tất cả - {worker_count} Worker(s)", 
                font=(S.FONT_FAMILY, S.FONT_SIZE_LG, "bold"),
                bg=S.BG_SECONDARY, fg=S.FG_ACCENT).pack(side="left", padx=S.PAD_MD, pady=S.PAD_SM)
        
        # Stop button (primary control)
        stop_btn = tk.Button(header, text="⏹ Dừng tất cả", command=self._stop_all_workers,
                            bg=S.ACCENT_RED, fg=S.FG_PRIMARY, font=(S.FONT_FAMILY, S.FONT_SIZE_MD, "bold"),
                            relief="flat", cursor="hand2", width=12, height=1)
        stop_btn.pack(side="right", padx=S.PAD_MD)
        
        # Main content area with 3-panel table
        content = tk.Frame(toolbar, bg=S.BG_PRIMARY)
        content.pack(fill="both", expand=True, padx=S.PAD_MD, pady=S.PAD_MD)
        
        # Title labels for 3 panels
        title_frame = tk.Frame(content, bg=S.BG_CARD, height=35)
        title_frame.pack(fill="x")
        title_frame.pack_propagate(False)
        
        tk.Label(title_frame, text="👤 Worker", 
                font=(S.FONT_FAMILY, S.FONT_SIZE_MD, "bold"),
                bg=S.BG_CARD, fg=S.ACCENT_BLUE, width=25, anchor="w").pack(side="left", padx=S.PAD_SM)
        
        tk.Label(title_frame, text="🎬 Action Hiện tại", 
                font=(S.FONT_FAMILY, S.FONT_SIZE_MD, "bold"),
                bg=S.BG_CARD, fg=S.ACCENT_PURPLE, width=30, anchor="w").pack(side="left", padx=S.PAD_SM)
        
        tk.Label(title_frame, text="📊 Trạng thái Thực thi", 
                font=(S.FONT_FAMILY, S.FONT_SIZE_MD, "bold"),
                bg=S.BG_CARD, fg=S.ACCENT_GREEN, width=25, anchor="w").pack(side="left", padx=S.PAD_SM)
        
        # Treeview for 3-panel display
        tree_frame = tk.Frame(content, bg=S.BG_CARD)
        tree_frame.pack(fill="both", expand=True)
        
        columns = ("worker", "action", "progress")
        tree = ttk.Treeview(tree_frame, columns=columns, show="headings", 
                           height=15, selectmode="browse")
        
        # Panel 1: Worker Identity (ID + Name)
        tree.column("worker", width=220, anchor=tk.W)
        tree.heading("worker", text="Worker")
        
        # Panel 2: Action Details (Current action label)
        tree.column("action", width=300, anchor=tk.W)
        tree.heading("action", text="Action")
        
        # Panel 3: Execution Status (Progress percentage + step count)
        tree.column("progress", width=220, anchor=tk.W)
        tree.heading("progress", text="Status")
        
        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        
        tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        self._play_all_status_tree = tree
        
        # Populate initial worker rows
        for w in self.workers:
            if w.id > 0:
                worker_name = self._get_worker_display_name(w.id)
                worker_display = f"[{w.id}] {worker_name}"
                tree.insert("", tk.END, iid=str(w.id),
                           values=(worker_display, "Đang khởi tạo...", "⏳ Bắt đầu..."))
        
        # Apply modern zebra striping
        S.apply_zebra_striping(tree)
        
        # Status bar (simplified - no logs)
        status_bar = tk.Frame(toolbar, bg=S.BG_SECONDARY, height=30)
        status_bar.pack(fill="x", side="bottom")
        status_bar.pack_propagate(False)
        
        self._play_all_status_label = tk.Label(status_bar, 
                                                text=f"⚡ Running {worker_count} workers in parallel", 
                                                bg=S.BG_SECONDARY, fg=S.FG_ACCENT,
                                                font=(S.FONT_FAMILY, S.FONT_SIZE_SM))
        self._play_all_status_label.pack(side="left", padx=S.PAD_MD)
        
        # Hotkey bindings (no hint label to reduce clutter)
        toolbar.bind('<F12>', lambda e: self._stop_all_workers())
        
        # Start real-time status updater
        self._start_play_all_status_updater()
    
    def _start_play_all_status_updater(self):
        """Start real-time status updater (refreshes every 500ms)"""
        if not hasattr(self, '_play_all_status_tree') or not self._play_all_status_tree:
            return
        
        try:
            # Update each worker row with current status
            if hasattr(self, '_worker_play_status'):
                for worker_id, status in self._worker_play_status.items():
                    try:
                        # Panel 1: Worker Identity (unchanged)
                        worker_display = self._play_all_status_tree.item(str(worker_id))['values'][0]
                        
                        # Panel 2: Current Action
                        action_text = status.get('current_action', 'Idle')
                        
                        # Panel 3: Execution Status
                        current_idx = status.get('current_idx', 0)
                        total = status.get('total', 0)
                        progress = status.get('progress', 0)
                        worker_status = status.get('status', 'Running')
                        
                        if worker_status == 'Complete':
                            status_text = f"✅ Hoàn thành - {total}/{total} (100%)"
                        elif worker_status == 'Stopped':
                            status_text = f"⏹ Đã dừng - {current_idx}/{total} ({progress:.0f}%)"
                        elif worker_status == 'Error':
                            status_text = f"❌ Lỗi - {current_idx}/{total} ({progress:.0f}%)"
                        else:
                            status_text = f"▶ Đang chạy - {current_idx}/{total} ({progress:.0f}%)"
                        
                        # Update tree row
                        self._play_all_status_tree.item(str(worker_id), 
                                                        values=(worker_display, action_text, status_text))
                    except tk.TclError:
                        # Tree item doesn't exist (worker removed)
                        pass
            
            # Schedule next update if toolbar still exists
            if hasattr(self, '_play_all_toolbar') and self._play_all_toolbar:
                self._play_all_toolbar.after(500, self._start_play_all_status_updater)
        except Exception as e:
            log(f"[UI] Status updater error: {e}")
    
    def _open_worker_editor(self):
        """Open Worker Actions Editor (Multi-Worker only)"""
        S = ModernStyle
        
        dialog = tk.Toplevel(self.root)
        dialog.title("🎛️ Worker Actions Editor")
        dialog.geometry("1100x700")
        dialog.configure(bg=S.BG_PRIMARY)
        dialog.transient(self.root)
        
        # Create notebook with Multi-Worker tab only
        notebook = ttk.Notebook(dialog)
        notebook.pack(fill="both", expand=True, padx=S.PAD_MD, pady=S.PAD_MD)
        
        # Tab: Multi-Worker Editor
        multi_frame = tk.Frame(notebook, bg=S.BG_CARD)
        notebook.add(multi_frame, text="📋 Sửa Multi-Worker")
        
        # ==================== MULTI-WORKER EDITOR ====================
        self._create_multi_worker_tab(multi_frame, dialog, S)
    
    def _create_multi_worker_tab(self, parent, dialog, S):
        """Create Multi-Worker Editor tab (Panel 1: Workers | Panel 2: Actions)"""
        # Horizontal split
        paned = tk.PanedWindow(parent, orient=tk.HORIZONTAL, bg=S.BG_CARD, 
                              sashwidth=4, sashrelief=tk.RAISED)
        paned.pack(fill="both", expand=True)
        
        # === PANEL 1: Worker Selection ===
        left_panel = tk.Frame(paned, bg=S.BG_CARD)
        paned.add(left_panel, width=300)
        
        tk.Label(left_panel, text="📋 Chọn Worker", 
                font=(S.FONT_FAMILY, S.FONT_SIZE_LG, "bold"),
                bg=S.BG_CARD, fg=S.FG_ACCENT).pack(pady=S.PAD_MD)
        
        # Select All checkbox
        select_all_var = tk.BooleanVar(value=False)
        
        def toggle_all():
            state = select_all_var.get()
            for var in worker_vars.values():
                var.set(state)
        
        tk.Checkbutton(left_panel, text="✓ Chọn tất cả", variable=select_all_var,
                      command=toggle_all, font=(S.FONT_FAMILY, S.FONT_SIZE_MD),
                      bg=S.BG_CARD, fg=S.FG_PRIMARY, selectcolor=S.BG_INPUT,
                      activebackground=S.BG_CARD).pack(anchor="w", padx=S.PAD_MD, pady=S.PAD_SM)
        
        # Worker list with checkboxes
        worker_list_frame = tk.Frame(left_panel, bg=S.BG_INPUT)
        worker_list_frame.pack(fill="both", expand=True, padx=S.PAD_MD, pady=S.PAD_SM)
        
        worker_canvas = tk.Canvas(worker_list_frame, bg=S.BG_INPUT, highlightthickness=0)
        worker_scrollbar = ttk.Scrollbar(worker_list_frame, orient="vertical", command=worker_canvas.yview)
        worker_scrollable = tk.Frame(worker_canvas, bg=S.BG_INPUT)
        
        worker_scrollable.bind("<Configure>", lambda e: worker_canvas.configure(scrollregion=worker_canvas.bbox("all")))
        worker_canvas.create_window((0, 0), window=worker_scrollable, anchor="nw")
        worker_canvas.configure(yscrollcommand=worker_scrollbar.set)
        
        worker_canvas.pack(side="left", fill="both", expand=True)
        worker_scrollbar.pack(side="right", fill="y")
        
        # Populate workers
        worker_vars = {}
        for w in self.workers:
            if w.id > 0:  # Only assigned workers
                var = tk.BooleanVar(value=False)
                worker_name = self._get_worker_display_name(w.id)
                cb = tk.Checkbutton(worker_scrollable, text=f"Worker {w.id}: {worker_name}",
                                  variable=var, font=(S.FONT_FAMILY, S.FONT_SIZE_MD),
                                  bg=S.BG_INPUT, fg=S.FG_PRIMARY, selectcolor=S.BG_CARD,
                                  activebackground=S.BG_INPUT)
                cb.pack(anchor="w", padx=S.PAD_SM, pady=2)
                worker_vars[w.id] = var
                
                # Auto-refresh preview when selection changes (strict isolation)
                var.trace_add("write", lambda *args: dialog.after(10, update_preview))
        
        # === PANEL 2: Actions Editor ===
        right_panel = tk.Frame(paned, bg=S.BG_CARD)
        paned.add(right_panel)
        
        tk.Label(right_panel, text="⚙️ Cấu hình Actions", 
                font=(S.FONT_FAMILY, S.FONT_SIZE_LG, "bold"),
                bg=S.BG_CARD, fg=S.FG_ACCENT).pack(pady=S.PAD_MD)
        
        # Mode state for selected workers
        mode_state = {"is_custom": False}  # False = Global, True = Custom
        
        # Row 1: Switch Toggle + Worker→Global + Mode Indicator
        action_btn_frame = tk.Frame(right_panel, bg=S.BG_CARD)
        action_btn_frame.pack(fill="x", padx=S.PAD_MD, pady=S.PAD_SM)
        
        mode_label = tk.Label(action_btn_frame, text="Chế độ: Global", 
                             bg=S.BG_CARD, fg=S.ACCENT_GREEN,
                             font=(S.FONT_FAMILY, S.FONT_SIZE_SM, "bold"))
        mode_label.pack(side="left", padx=(0, S.PAD_MD))
        
        def toggle_mode():
            """Switch Toggle: Toggle between Global/Custom for selected workers"""
            selected = [wid for wid, var in worker_vars.items() if var.get()]
            if not selected:
                messagebox.showwarning("Cảnh báo", "Vui lòng chọn ít nhất một worker")
                return
            
            # Toggle mode
            mode_state["is_custom"] = not mode_state["is_custom"]
            
            if mode_state["is_custom"]:
                # Switch to Custom
                for wid in selected:
                    if wid not in self._worker_actions:
                        self._worker_actions[wid] = [Action.from_dict(a.to_dict()) for a in self.actions]
                mode_label.config(text="Chế độ: Tùy chỉnh", fg=S.ACCENT_PURPLE)
                messagebox.showinfo("Thành công", f"✓ {len(selected)} worker(s) → Chế độ Tùy chỉnh")
                log(f"[UI] Switched {len(selected)} workers to Custom")
            else:
                # Switch to Global
                for wid in selected:
                    if wid in self._worker_actions:
                        del self._worker_actions[wid]
                mode_label.config(text="Chế độ: Global", fg=S.ACCENT_GREEN)
                messagebox.showinfo("Thành công", f"✓ {len(selected)} worker(s) → Chế độ Global")
                log(f"[UI] Switched {len(selected)} workers to Global")
            
            update_preview()
        
        def output_worker_to_global():
            """Export first selected worker's actions → Global"""
            selected = [wid for wid, var in worker_vars.items() if var.get()]
            if not selected:
                messagebox.showwarning("Cảnh báo", "Vui lòng chọn ít nhất một worker")
                return
            
            first_wid = selected[0]
            if first_wid not in self._worker_actions or not self._worker_actions[first_wid]:
                messagebox.showwarning("Cảnh báo", f"Worker {first_wid} chưa có custom actions")
                return
            
            confirm = messagebox.askyesno("Xác nhận", 
                f"Ghi đè Global actions bằng custom actions của Worker {first_wid}?")
            if not confirm:
                return
            
            # Convert to Action objects
            self.actions = self._worker_actions[first_wid]
            self._refresh_action_list()
            
            messagebox.showinfo("Thành công", f"✓ Đã xuất Worker {first_wid} → Global")
            log(f"[UI] Exported Worker {first_wid} to Global")
            update_preview()
        
        for text, cmd, color in [
            ("🔄 Đổi chế độ", toggle_mode, S.ACCENT_CYAN),
            ("📤 Worker → Global", output_worker_to_global, S.ACCENT_ORANGE),
        ]:
            btn = tk.Button(action_btn_frame, text=text, command=cmd, width=16,
                           bg=color, fg=S.FG_PRIMARY, font=(S.FONT_FAMILY, S.FONT_SIZE_SM),
                           relief="flat", cursor="hand2")
            btn.pack(side="left", padx=2)
        
        # Row 2: Action manipulation buttons (point to preview_tree)
        action_row2_frame = tk.Frame(right_panel, bg=S.BG_CARD)
        action_row2_frame.pack(fill="x", padx=S.PAD_MD, pady=(0, S.PAD_SM))
        
        # Reference to preview tree actions (will be defined after preview_tree is created)
        preview_actions = {}
        
        def add_to_preview():
            """Add action to preview tree"""
            if 'add_handler' in preview_actions:
                preview_actions['add_handler']()
        
        def edit_in_preview():
            """Edit selected action in preview tree"""
            if 'edit_handler' in preview_actions:
                preview_actions['edit_handler']()
        
        def delete_from_preview():
            """Delete selected action from preview tree"""
            if 'delete_handler' in preview_actions:
                preview_actions['delete_handler']()
        
        def save_preview():
            """Save preview actions to file"""
            if 'save_handler' in preview_actions:
                preview_actions['save_handler']()
        
        def load_to_preview():
            """Load actions from file to preview"""
            if 'load_handler' in preview_actions:
                preview_actions['load_handler']()
        
        for text, cmd, color, w in [
            ("➕ Thêm", add_to_preview, S.ACCENT_GREEN, 7),
            ("✏️ Sửa", edit_in_preview, S.ACCENT_BLUE, 7),
            ("🗑 Xóa", delete_from_preview, S.ACCENT_RED, 6),
            ("💾 Lưu", save_preview, S.BTN_PRIMARY, 7),
            ("📂 Tải", load_to_preview, S.BTN_SECONDARY, 7),
        ]:
            btn = tk.Button(action_row2_frame, text=text, command=cmd,
                           bg=color, fg=S.FG_PRIMARY,
                           font=(S.FONT_FAMILY, S.FONT_SIZE_SM),
                           relief="flat", cursor="hand2", width=w)
            btn.pack(side="left", padx=S.PAD_XS)
            btn.bind("<Enter>", lambda e, b=btn: b.config(bg=S.BG_TERTIARY))
            btn.bind("<Leave>", lambda e, b=btn, c=color: b.config(bg=c))
        
        # Action preview tree
        preview_frame = tk.LabelFrame(right_panel, text=" 📋 Xem trước Action (từ worker được chọn đầu tiên) ", 
                                     font=(S.FONT_FAMILY, S.FONT_SIZE_MD, "bold"),
                                     bg=S.BG_CARD, fg=S.FG_ACCENT)
        preview_frame.pack(fill="both", expand=True, padx=S.PAD_MD, pady=S.PAD_SM)
        
        columns = ("#", "Action", "Value", "Label")
        preview_tree = ttk.Treeview(preview_frame, columns=columns, show="headings", 
                                   height=12, selectmode="extended")
        
        preview_tree.column("#", width=40, anchor=tk.CENTER)
        preview_tree.column("Action", width=120, anchor=tk.W)
        preview_tree.column("Value", width=250, anchor=tk.W)
        preview_tree.column("Label", width=100, anchor=tk.W)
        
        for col in columns:
            preview_tree.heading(col, text=col)
        
        preview_scrollbar = ttk.Scrollbar(preview_frame, orient="vertical", command=preview_tree.yview)
        preview_tree.configure(yscrollcommand=preview_scrollbar.set)
        
        preview_tree.pack(side="left", fill="both", expand=True, padx=S.PAD_SM, pady=S.PAD_SM)
        preview_scrollbar.pack(side="right", fill="y")
        
        # Apply zebra striping
        S.apply_zebra_striping(preview_tree)
        
        # Clipboard for copy/paste
        preview_clipboard = []
        
        def update_preview():
            """Update action preview from first selected worker (strict isolation)"""
            # Clear preview
            for item in preview_tree.get_children():
                preview_tree.delete(item)
            
            # Get first selected worker
            selected = [wid for wid, var in worker_vars.items() if var.get()]
            if not selected:
                return
            
            first_wid = selected[0]
            
            # STRICT ISOLATION: Only show worker-specific custom actions
            # Do NOT fall back to global actions in Multi-Worker Editor
            worker_actions = self._worker_actions.get(first_wid, [])
            
            # Display worker's actions (may be empty)
            for idx, action in enumerate(worker_actions, 1):
                if isinstance(action, dict):
                    action_type = action.get("action", "?")
                    action_obj = Action.from_dict(action)
                    value_summary = action_obj.get_value_summary()
                    label = action.get("label", "")
                else:
                    action_type = action.action
                    value_summary = action.get_value_summary()
                    label = action.label
                
                tag = 'evenrow' if (idx-1) % 2 == 0 else 'oddrow'
                preview_tree.insert("", tk.END, values=(idx, action_type, value_summary, label), tags=(tag,))
            
            # Force UI update
            preview_tree.update_idletasks()
        
        # === Mouse & Keyboard Event Handlers ===
        
        def preview_select_all(event=None):
            """Ctrl+A: Select all items in preview"""
            for item in preview_tree.get_children():
                preview_tree.selection_add(item)
            return "break"
        
        def preview_copy(event=None):
            """Ctrl+C: Copy selected actions"""
            nonlocal preview_clipboard
            selection = preview_tree.selection()
            if not selection:
                return "break"
            
            preview_clipboard.clear()
            selected = [wid for wid, var in worker_vars.items() if var.get()]
            if not selected:
                return "break"
            
            first_wid = selected[0]
            actions = self._get_actions_for_worker(first_wid)
            
            for item in selection:
                values = preview_tree.item(item, "values")
                if values:
                    idx = int(values[0]) - 1
                    if 0 <= idx < len(actions):
                        action = actions[idx]
                        if isinstance(action, dict):
                            preview_clipboard.append(action)
                        else:
                            preview_clipboard.append(action.to_dict())
            
            log(f"[Multi-Worker Editor] Copied {len(preview_clipboard)} action(s)")
            return "break"
        
        def preview_paste(event=None):
            """Ctrl+V: Paste actions"""
            if not preview_clipboard:
                return "break"
            
            selected = [wid for wid, var in worker_vars.items() if var.get()]
            if not selected:
                messagebox.showwarning("Cảnh báo", "Vui lòng chọn ít nhất một worker")
                return "break"
            
            first_wid = selected[0]
            
            # Get or create worker actions (strict isolation - no fallback to global)
            if first_wid not in self._worker_actions:
                self._worker_actions[first_wid] = []
            
            current_actions = list(self._worker_actions[first_wid])
            
            # Append clipboard actions (convert dicts to Action objects if needed)
            for clip_action in preview_clipboard:
                if isinstance(clip_action, dict):
                    current_actions.append(Action.from_dict(clip_action))
                else:
                    current_actions.append(clip_action)
            
            self._worker_actions[first_wid] = current_actions
            
            # Force immediate UI refresh
            update_preview()
            preview_tree.update_idletasks()
            log(f"[Multi-Worker Editor] Pasted {len(preview_clipboard)} action(s)")
            return "break"
        
        def preview_right_click(event):
            """Right-click context menu"""
            # Select item under cursor
            item = preview_tree.identify_row(event.y)
            if item and item not in preview_tree.selection():
                preview_tree.selection_set(item)
            
            menu = tk.Menu(dialog, tearoff=0)
            menu.add_command(label="✏️ Sửa", command=lambda: preview_actions.get('edit_handler', lambda: None)())
            menu.add_command(label="📋 Sao chép", command=preview_copy)
            menu.add_command(label="📋 Dán", command=preview_paste)
            menu.add_command(label="🗑️ Xóa", command=lambda: preview_actions.get('delete_handler', lambda: None)())
            menu.add_separator()
            menu.add_command(label="✓ Chọn tất cả", command=preview_select_all)
            
            try:
                menu.tk_popup(event.x_root, event.y_root)
            finally:
                menu.grab_release()
        
        def preview_double_click(event):
            """Double-click to edit"""
            preview_actions.get('edit_handler', lambda: None)()
        
        # Bind mouse & keyboard events
        preview_tree.bind("<Button-3>", preview_right_click)
        preview_tree.bind("<Double-1>", preview_double_click)
        preview_tree.bind("<Control-a>", preview_select_all)
        preview_tree.bind("<Control-c>", preview_copy)
        preview_tree.bind("<Control-v>", preview_paste)
        
        # === DRAG & DROP Support ===
        
        # Row reordering
        preview_drag_data = {"items": [], "start_y": 0, "dragging": False}
        
        def preview_drag_start(event):
            """Start drag operation for reordering"""
            item = preview_tree.identify_row(event.y)
            if not item:
                preview_drag_data.update({"items": [], "start_y": 0, "dragging": False})
                return
            
            selection = preview_tree.selection()
            if item not in selection:
                preview_tree.selection_set(item)
                selection = (item,)
            
            preview_drag_data.update({
                "items": list(selection),
                "start_y": event.y,
                "dragging": False
            })
        
        def preview_drag_motion(event):
            """Handle drag motion with visual feedback"""
            if not preview_drag_data.get("items"):
                return
            
            # Start dragging after moving 5 pixels
            if not preview_drag_data.get("dragging"):
                if abs(event.y - preview_drag_data["start_y"]) > 5:
                    preview_drag_data["dragging"] = True
                    preview_tree.config(cursor="hand2")
            
            if preview_drag_data.get("dragging"):
                # Visual feedback - highlight drop target
                target_item = preview_tree.identify_row(event.y)
                if target_item and target_item not in preview_drag_data["items"]:
                    for item in preview_tree.get_children():
                        preview_tree.item(item, tags=())
                    preview_tree.item(target_item, tags=("drop_target",))
                    preview_tree.tag_configure("drop_target", background="#e3f2fd")
        
        def preview_drag_end(event):
            """End drag and reorder actions"""
            if not preview_drag_data.get("dragging") or not preview_drag_data.get("items"):
                preview_drag_data.update({"items": [], "start_y": 0, "dragging": False})
                return
            
            preview_tree.config(cursor="")
            
            # Clear drop target highlight
            for item in preview_tree.get_children():
                preview_tree.item(item, tags=())
            
            target_item = preview_tree.identify_row(event.y)
            if not target_item or target_item in preview_drag_data["items"]:
                preview_drag_data.update({"items": [], "start_y": 0, "dragging": False})
                return
            
            # Get selected worker
            selected = [wid for wid, var in worker_vars.items() if var.get()]
            if not selected:
                preview_drag_data.update({"items": [], "start_y": 0, "dragging": False})
                return
            
            first_wid = selected[0]
            
            # Get worker actions
            if first_wid not in self._worker_actions:
                self._worker_actions[first_wid] = []
            
            worker_actions = self._worker_actions[first_wid]
            
            # Get indices
            source_indices = []
            for item in preview_drag_data["items"]:
                values = preview_tree.item(item, "values")
                if values:
                    source_indices.append(int(values[0]) - 1)
            
            target_values = preview_tree.item(target_item, "values")
            target_idx = int(target_values[0]) - 1
            
            # Sort source indices
            source_indices.sort()
            
            # Extract actions to move
            actions_to_move = [worker_actions[i] for i in source_indices if 0 <= i < len(worker_actions)]
            
            # Remove from original positions (reverse order)
            for i in reversed(source_indices):
                if 0 <= i < len(worker_actions):
                    worker_actions.pop(i)
            
            # Adjust target index after removals
            removed_before_target = sum(1 for i in source_indices if i < target_idx)
            new_target_idx = target_idx - removed_before_target
            
            # Insert at new position
            for i, action in enumerate(actions_to_move):
                worker_actions.insert(new_target_idx + i + 1, action)
            
            preview_drag_data.update({"items": [], "start_y": 0, "dragging": False})
            
            # Force immediate UI refresh
            update_preview()
            preview_tree.update_idletasks()
            log(f"[Multi-Worker Editor] Moved {len(actions_to_move)} action(s) to position {new_target_idx + 2}")
        
        # File drop support
        def preview_file_drop(event):
            """Handle .macro file drop - Load into ALL selected workers"""
            import base64
            
            selected = [wid for wid, var in worker_vars.items() if var.get()]
            if not selected:
                messagebox.showwarning("Cảnh báo", "Vui lòng chọn ít nhất một worker")
                return
            
            # Get file path from event
            file_path = event.data
            if isinstance(file_path, str):
                # Remove braces if present
                file_path = file_path.strip('{}')
                
                if file_path.lower().endswith('.macro'):
                    try:
                        # Load macro file
                        with open(file_path, 'r', encoding='utf-8') as f:
                            macro_data = json.load(f)
                        
                        # Load actions (handle embedded images)
                        images_embedded = macro_data.get('images_embedded', {})
                        
                        # Apply to ALL selected workers
                        for wid in selected:
                            # Get or create worker actions
                            if wid not in self._worker_actions:
                                self._worker_actions[wid] = []
                            
                            loaded_actions = []
                            for action_dict in macro_data.get('actions', []):
                                # Handle embedded images
                                if action_dict.get('action') == 'FIND_IMAGE':
                                    template_path = action_dict.get('value', {}).get('template_path', '')
                                    if template_path.startswith('@embedded:'):
                                        img_key = template_path.replace('@embedded:', '')
                                        if img_key in images_embedded:
                                            # Decode and save to temp file
                                            img_data = base64.b64decode(images_embedded[img_key])
                                            temp_dir = os.path.join(os.getcwd(), 'data', 'cropped')
                                            os.makedirs(temp_dir, exist_ok=True)
                                            temp_path = os.path.join(temp_dir, f"preview_{wid}_{img_key}")
                                            with open(temp_path, 'wb') as img_file:
                                                img_file.write(img_data)
                                            action_dict['value']['template_path'] = temp_path
                                
                                # Convert to Action object
                                loaded_actions.append(Action.from_dict(action_dict))
                            
                            # Append to worker actions
                            self._worker_actions[wid].extend(loaded_actions)
                        
                        # Force immediate UI refresh
                        update_preview()
                        preview_tree.update_idletasks()
                        log(f"[Multi-Worker Editor] Loaded {len(loaded_actions)} actions to {len(selected)} worker(s) from {os.path.basename(file_path)}")
                        messagebox.showinfo("Thành công", f"✓ Đã tải {len(loaded_actions)} actions cho {len(selected)} worker(s)")
                        
                    except Exception as e:
                        messagebox.showerror("Lỗi", f"Không thể tải file macro: {str(e)}")
                        log(f"[Multi-Worker Editor] Error loading file: {str(e)}")
        
        # Bind drag & drop events
        preview_tree.bind("<ButtonPress-1>", preview_drag_start)
        preview_tree.bind("<B1-Motion>", preview_drag_motion)
        preview_tree.bind("<ButtonRelease-1>", preview_drag_end)
        
        # Try to enable file drop (if tkinterdnd2 available)
        try:
            from tkinterdnd2 import DND_FILES
            preview_tree.drop_target_register(DND_FILES)
            preview_tree.dnd_bind('<<Drop>>', preview_file_drop)
        except ImportError:
            pass  # tkinterdnd2 not available, skip file drop
        
        # === Action Handlers (referenced by Row 2 buttons) ===
        
        def preview_add_handler():
            """Add new action to preview"""
            selected = [wid for wid, var in worker_vars.items() if var.get()]
            if not selected:
                messagebox.showwarning("Cảnh báo", "Vui lòng chọn ít nhất một worker")
                return
            
            first_wid = selected[0]
            
            # Get or create worker actions list
            if first_wid not in self._worker_actions:
                self._worker_actions[first_wid] = []
            
            # Pass worker actions directly to dialog (no backup/restore needed)
            self._open_add_action_dialog(target_actions=self._worker_actions[first_wid])
            
            # Force immediate UI refresh
            dialog.after(10, update_preview)  # Schedule refresh after dialog closes
            log(f"[Multi-Worker Editor] Added action to Worker {first_wid}")
        
        def preview_edit_handler():
            """Edit selected action in preview"""
            selection = preview_tree.selection()
            if not selection:
                messagebox.showwarning("Cảnh báo", "Vui lòng chọn một action để sửa")
                return
            
            selected = [wid for wid, var in worker_vars.items() if var.get()]
            if not selected:
                messagebox.showwarning("Cảnh báo", "Vui lòng chọn ít nhất một worker")
                return
            
            first_wid = selected[0]
            
            # Get edit index
            values = preview_tree.item(selection[0], "values")
            if not values:
                return
            edit_idx = int(values[0]) - 1
            
            # Get or create worker actions list
            if first_wid not in self._worker_actions:
                self._worker_actions[first_wid] = []
            
            worker_actions = self._worker_actions[first_wid]
            
            # Open edit dialog with worker actions
            if 0 <= edit_idx < len(worker_actions):
                self._open_add_action_dialog(edit_index=edit_idx, target_actions=worker_actions)
                
                # Force immediate UI refresh
                dialog.after(10, update_preview)  # Schedule refresh after dialog closes
            
            log(f"[Multi-Worker Editor] Edited action {edit_idx} in Worker {first_wid}")
        
        def preview_delete_handler():
            """Delete selected actions from preview"""
            selection = preview_tree.selection()
            if not selection:
                return
            
            selected = [wid for wid, var in worker_vars.items() if var.get()]
            if not selected:
                return
            
            first_wid = selected[0]
            
            # Get indices to delete
            indices_to_delete = []
            for item in selection:
                values = preview_tree.item(item, "values")
                if values:
                    indices_to_delete.append(int(values[0]) - 1)
            
            if not indices_to_delete:
                return
            
            # Get or create worker actions
            if first_wid not in self._worker_actions:
                self._worker_actions[first_wid] = []
            
            # Work directly on worker's action list
            worker_actions = self._worker_actions[first_wid]
            
            # Delete in reverse order to maintain indices
            for idx in sorted(indices_to_delete, reverse=True):
                if 0 <= idx < len(worker_actions):
                    del worker_actions[idx]
            
            # Force immediate UI refresh
            update_preview()
            preview_tree.update_idletasks()
            log(f"[Multi-Worker Editor] Deleted {len(indices_to_delete)} action(s) from Worker {first_wid}")
        
        def preview_save_handler():
            """Save preview actions to file"""
            selected = [wid for wid, var in worker_vars.items() if var.get()]
            if not selected:
                messagebox.showwarning("Cảnh báo", "Vui lòng chọn ít nhất một worker")
                return
            
            first_wid = selected[0]
            
            # Get worker's actions
            if first_wid in self._worker_actions:
                worker_actions = self._worker_actions[first_wid]
            else:
                worker_actions = [a for a in self.actions]
            
            if not worker_actions:
                messagebox.showwarning("Cảnh báo", "Không có actions để lưu")
                return
            
            # Ask for save location
            filepath = filedialog.asksaveasfilename(
                title=f"Lưu Actions Worker {first_wid}",
                initialdir=MACROS_DIR,
                defaultextension=".macro",
                filetypes=[("Macro files", "*.macro"), ("JSON files", "*.json"), ("All files", "*.*")]
            )
            if not filepath:
                return
            
            import base64
            
            try:
                # Build actions data with embedded images
                actions_data = []
                images_embedded = {}
                image_count = 0
                
                for action in worker_actions:
                    if isinstance(action, dict):
                        action_dict = action
                        action_obj = Action.from_dict(action)
                    else:
                        action_dict = action.to_dict()
                        action_obj = action
                    
                    # Handle FIND_IMAGE - embed template as base64
                    if action_obj.action == "FIND_IMAGE" and action_obj.value.get("template_path"):
                        old_path = action_obj.value["template_path"]
                        if os.path.exists(old_path):
                            with open(old_path, "rb") as img_file:
                                img_data = base64.b64encode(img_file.read()).decode('utf-8')
                            
                            filename = os.path.basename(old_path)
                            img_key = f"img_{image_count:03d}_{filename}"
                            images_embedded[img_key] = img_data
                            action_dict["value"]["template_path"] = f"@embedded:{img_key}"
                            image_count += 1
                    
                    actions_data.append(action_dict)
                
                # Save to file
                output = {
                    "format": "embedded",
                    "version": "1.0",
                    "name": f"Worker_{first_wid}_actions",
                    "images": images_embedded,
                    "actions": actions_data
                }
                
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(output, f, indent=2, ensure_ascii=False)
                
                messagebox.showinfo("Thành công", 
                    f"✅ Đã lưu Worker {first_wid} actions\n"
                    f"📝 Actions: {len(actions_data)}\n"
                    f"🖼️ Hình ảnh: {image_count}\n"
                    f"📁 File: {os.path.basename(filepath)}")
                log(f"[Multi-Worker Editor] Saved Worker {first_wid} actions to {filepath}")
                
            except Exception as e:
                messagebox.showerror("Lỗi", f"Lưu thất bại: {e}")
                log(f"[Multi-Worker Editor] Save error: {e}")
        
        def preview_load_handler():
            """Load actions from file to ALL selected workers"""
            selected = [wid for wid, var in worker_vars.items() if var.get()]
            if not selected:
                messagebox.showwarning("Cảnh báo", "Vui lòng chọn ít nhất một worker")
                return
            
            filepath = filedialog.askopenfilename(
                title=f"Tải Actions cho {len(selected)} Worker(s)",
                initialdir=MACROS_DIR,
                filetypes=[
                    ("Macro files", "*.macro"),
                    ("JSON files", "*.json"),
                    ("All files", "*.*")
                ]
            )
            if not filepath:
                return
            
            import base64
            import tempfile
            
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                images = data.get("images", {})
                actions_data = data.get("actions", [])
                
                if data.get("format") == "embedded" and images:
                    # Extract embedded images
                    macro_name = os.path.splitext(os.path.basename(filepath))[0]
                    temp_dir = os.path.join(tempfile.gettempdir(), "macro_images", macro_name)
                    os.makedirs(temp_dir, exist_ok=True)
                    
                    for img_key, img_b64 in images.items():
                        try:
                            img_data = base64.b64decode(img_b64)
                            img_path = os.path.join(temp_dir, img_key)
                            with open(img_path, "wb") as f:
                                f.write(img_data)
                        except Exception as e:
                            log(f"[Multi-Worker Editor] Failed to extract {img_key}: {e}")
                    
                    # Update paths
                    for action_data in actions_data:
                        if action_data.get("action") == "FIND_IMAGE":
                            template_path = action_data.get("value", {}).get("template_path", "")
                            if template_path.startswith("@embedded:"):
                                img_key = template_path.replace("@embedded:", "")
                                action_data["value"]["template_path"] = os.path.join(temp_dir, img_key)
                        
                        if action_data.get("action") == "WAIT_SCREEN_CHANGE":
                            ref_path = action_data.get("value", {}).get("reference_image", "")
                            if ref_path.startswith("@embedded:"):
                                img_key = ref_path.replace("@embedded:", "")
                                action_data["value"]["reference_image"] = os.path.join(temp_dir, img_key)
                else:
                    # Legacy format - update relative paths
                    folder = os.path.dirname(filepath)
                    for action_data in actions_data:
                        if action_data.get("action") == "FIND_IMAGE":
                            template_path = action_data.get("value", {}).get("template_path", "")
                            if template_path and not os.path.isabs(template_path):
                                action_data["value"]["template_path"] = os.path.join(folder, template_path)
                
                # Convert to Action objects
                loaded_actions = [Action.from_dict(a) for a in actions_data]
                
                # Apply to ALL selected workers
                replace_mode = None  # Will be set on first worker with existing actions
                total_loaded = 0
                
                for wid in selected:
                    # Ask: Replace or Append? (only once, for first worker with existing actions)
                    if replace_mode is None and wid in self._worker_actions and self._worker_actions[wid]:
                        choice = messagebox.askyesnocancel(
                            "Load Actions",
                            f"{len(selected)} worker(s) selected. Some have existing actions.\n\n"
                            f"Yes = Replace existing actions\n"
                            f"No = Append to existing actions\n"
                            f"Cancel = Cancel load"
                        )
                        if choice is None:  # Cancel
                            return
                        replace_mode = choice
                    
                    # Apply to this worker
                    if wid not in self._worker_actions or not self._worker_actions[wid]:
                        # No existing actions - just set
                        self._worker_actions[wid] = [Action.from_dict(a.to_dict()) for a in loaded_actions]
                    elif replace_mode is True:
                        # Replace mode
                        self._worker_actions[wid] = [Action.from_dict(a.to_dict()) for a in loaded_actions]
                    elif replace_mode is False:
                        # Append mode
                        self._worker_actions[wid].extend([Action.from_dict(a.to_dict()) for a in loaded_actions])
                    else:
                        # No choice made yet (shouldn't happen but handle it)
                        self._worker_actions[wid] = [Action.from_dict(a.to_dict()) for a in loaded_actions]
                    
                    total_loaded += 1
                
                update_preview()
                
                macro_name = data.get("name", os.path.basename(filepath))
                image_count = len(images)
                messagebox.showinfo("Thành công", 
                    f"✅ Đã tải cho {total_loaded} Worker(s)\n"
                    f"📝 Actions: {len(loaded_actions)}\n"
                    f"🖼️ Hình ảnh: {image_count}")
                log(f"[Multi-Worker Editor] Loaded {len(loaded_actions)} actions to {total_loaded} worker(s)")
                
            except Exception as e:
                messagebox.showerror("Lỗi", f"Tải thất bại: {e}")
                log(f"[Multi-Worker Editor] Load error: {e}")
        
        # Register handlers
        preview_actions['add_handler'] = preview_add_handler
        preview_actions['edit_handler'] = preview_edit_handler
        preview_actions['delete_handler'] = preview_delete_handler
        preview_actions['save_handler'] = preview_save_handler
        preview_actions['load_handler'] = preview_load_handler
        
        # Bind checkbox changes to preview update
        for var in worker_vars.values():
            var.trace_add("write", lambda *args: update_preview())
        
        # Initial preview
        update_preview()
    
    def _edit_selected_action(self):
        """Edit the selected action in action list"""
        selection = self.action_tree.selection()
        if not selection:
            messagebox.showinfo("Sửa", "Vui lòng chọn một action để sửa")
            return
        # Get index from first column
        values = self.action_tree.item(selection[0], "values")
        if values:
            idx = int(values[0]) - 1  # Convert to 0-based index
            if 0 <= idx < len(self.actions):
                self._open_add_action_dialog(edit_index=idx)
    
    def _copy_selected_actions(self, event=None):
        """Copy selected actions to clipboard"""
        import json
        selection = self.action_tree.selection()
        if not selection:
            return "break"
        
        copied = []
        for item in selection:
            values = self.action_tree.item(item, "values")
            if values:
                idx = int(values[0]) - 1
                if 0 <= idx < len(self.actions):
                    copied.append(self.actions[idx].to_dict())
        
        if copied:
            self._clipboard_actions = copied
            try:
                self.root.clipboard_clear()
                self.root.clipboard_append(json.dumps(copied))
            except:
                pass
            log(f"[UI] Copied {len(copied)} action(s)")
        return "break"
    
    def _copy_selected_actions_key(self, event=None):
        """Keyboard handler for Ctrl+C"""
        return self._copy_selected_actions(event)
    
    def _cut_selected_actions(self, event=None):
        """Cut selected actions (copy then delete)"""
        self._copy_selected_actions(event)
        self._delete_selected_actions(event)
        return "break"
    
    def _cut_selected_actions_key(self, event=None):
        """Keyboard handler for Ctrl+X"""
        return self._cut_selected_actions(event)
    
    def _paste_actions(self, event=None):
        """Paste actions from clipboard"""
        import json
        
        # Get insert position (after last selected item, or at end)
        insert_idx = len(self.actions)
        selection = self.action_tree.selection()
        if selection:
            last_item = selection[-1]
            values = self.action_tree.item(last_item, "values")
            if values:
                insert_idx = int(values[0])  # Insert after selected
        
        pasted_count = 0
        
        # Try internal clipboard first
        if hasattr(self, '_clipboard_actions') and self._clipboard_actions:
            for i, action_dict in enumerate(self._clipboard_actions):
                action = Action.from_dict(action_dict)
                action.id = str(uuid.uuid4())[:8]  # New ID
                self.actions.insert(insert_idx + i, action)
                pasted_count += 1
        else:
            # Try system clipboard
            try:
                data = self.root.clipboard_get()
                actions_data = json.loads(data)
                if isinstance(actions_data, list):
                    for i, action_dict in enumerate(actions_data):
                        action = Action.from_dict(action_dict)
                        action.id = str(uuid.uuid4())[:8]
                        self.actions.insert(insert_idx + i, action)
                        pasted_count += 1
            except:
                pass
        
        if pasted_count > 0:
            self._refresh_action_list()
            log(f"[UI] Pasted {pasted_count} action(s)")
        return "break"
    
    def _paste_actions_key(self, event=None):
        """Keyboard handler for Ctrl+V"""
        return self._paste_actions(event)
    
    def _find_worker(self, worker_id: int):
        """Find worker by ID"""
        for w in self.workers:
            if w.id == worker_id:
                return w
        return None
    
    def _update_worker_resolution_from_adb(self, worker) -> bool:
        """
        Query ADB để lấy resolution thực và update Worker.
        
        Args:
            worker: Worker object cần update
            
        Returns:
            True nếu update thành công, False nếu không
        """
        if not worker.adb_device:
            return False
            
        try:
            from core.adb_manager import ADBManager
            adb = ADBManager()
            resolution = adb.query_resolution(worker.adb_device)
            
            if resolution:
                old_res = (worker.res_width, worker.res_height)
                worker.res_width, worker.res_height = resolution
                log(f"[UI] Updated Worker {worker.id} resolution from ADB: {old_res} → {resolution}")
                return True
            else:
                log(f"[UI] Could not query resolution for Worker {worker.id} via ADB")
                return False
        except Exception as e:
            log(f"[UI] Failed to update resolution from ADB: {e}")
            return False
    
    def _detect_adb_serial(self, emulator_name: str, hwnd: Optional[int] = None) -> Optional[str]:
        """
        Detect ADB serial for emulator by matching with adb devices list.
        
        Strategy (priority order):
        1. If manual mapping exists in config → use it
        2. If only 1 device → auto-select
        3. Query each device for window title match (via adb shell dumpsys)
        4. Sequential assignment for multiple devices
        
        Args:
            emulator_name: Window title (e.g., "LDPlayer-Zalo1")
            hwnd: Window handle (for future manual mapping)
        
        Returns:
            ADB serial (e.g., "emulator-5554", "127.0.0.1:5555") or None
        """
        try:
            # Get ADB device list
            import subprocess
            result = subprocess.run(
                ["adb", "devices"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=3,
                creationflags=CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )
            
            if result.returncode != 0:
                return None
            
            # Parse device list (format: "device_serial\tdevice")
            lines = result.stdout.strip().split('\n')[1:]  # Skip header "List of devices attached"
            devices = []
            for line in lines:
                parts = line.split('\t')
                if len(parts) >= 2 and parts[1].strip() == 'device':
                    devices.append(parts[0].strip())
            
            if not devices:
                log("[UI] No ADB devices found")
                return None
            
            # Strategy 1: Single device → auto-select
            if len(devices) == 1:
                log(f"[UI] Auto-selected ADB device: {devices[0]}")
                return devices[0]
            
            # Strategy 2: Multiple devices → Persistent mapping by hwnd
            # Create persistent hwnd → adb_serial mapping
            if not hasattr(self, '_hwnd_to_adb'):
                self._hwnd_to_adb = {}
            if not hasattr(self, '_adb_device_index'):
                self._adb_device_index = 0
            
            # If hwnd already mapped, use cached value
            if hwnd and hwnd in self._hwnd_to_adb:
                cached_serial = self._hwnd_to_adb[hwnd]
                # Verify cached serial still exists
                if cached_serial in devices:
                    log(f"[UI] Using cached mapping: hwnd={hwnd} → {cached_serial}")
                    return cached_serial
                else:
                    # Device disconnected, remove from cache
                    log(f"[UI] Cached device {cached_serial} disconnected, remapping...")
                    del self._hwnd_to_adb[hwnd]
            
            # New mapping: Round-robin assignment
            selected_device = devices[self._adb_device_index % len(devices)]
            self._adb_device_index += 1
            
            # Cache the mapping
            if hwnd:
                self._hwnd_to_adb[hwnd] = selected_device
                log(f"[UI] Multi-device mode: Mapped hwnd={hwnd} '{emulator_name}' → {selected_device} (round-robin)")
            else:
                log(f"[UI] Multi-device mode: Assigned '{emulator_name}' → {selected_device} (no hwnd, not cached)")
            
            return selected_device
            
        except Exception as e:
            log(f"[UI] Failed to detect ADB device: {e}")
            return None

    def _edit_worker_actions(self, worker_id: int):
        """Open dialog to edit custom actions for a specific worker - Modern UI"""
        S = ModernStyle
        
        dialog = tk.Toplevel(self.root)
        dialog.title(f"Edit Actions - Worker {worker_id}")
        dialog.geometry("700x550")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.configure(bg=S.BG_PRIMARY)
        
        # ===== HEADER =====
        header_frame = tk.Frame(dialog, bg=S.BG_SECONDARY, height=50)
        header_frame.pack(fill="x")
        header_frame.pack_propagate(False)
        
        tk.Label(header_frame, text=f"✏️ Custom Actions - Worker {worker_id}", 
                 font=(S.FONT_FAMILY, S.FONT_SIZE_LG, "bold"),
                 bg=S.BG_SECONDARY, fg=S.FG_PRIMARY).pack(pady=S.PAD_MD)
        
        # ===== ACTION BUTTONS =====
        btn_frame = tk.Frame(dialog, bg=S.BG_PRIMARY)
        btn_frame.pack(fill="x", padx=S.PAD_MD, pady=S.PAD_SM)
        
        # Treeview for actions
        list_frame = tk.LabelFrame(dialog, text=" 📋 Action List ", 
                                   font=(S.FONT_FAMILY, S.FONT_SIZE_MD, "bold"),
                                   bg=S.BG_CARD, fg=S.FG_ACCENT,
                                   padx=S.PAD_SM, pady=S.PAD_SM)
        list_frame.pack(fill="both", expand=True, padx=S.PAD_MD, pady=S.PAD_SM)
        
        columns = ("index", "type", "target", "value")
        tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=15)
        tree.heading("index", text="#")
        tree.heading("type", text="Type")
        tree.heading("target", text="Target")
        tree.heading("value", text="Value")
        tree.column("index", width=40)
        tree.column("type", width=120)
        tree.column("target", width=250)
        tree.column("value", width=200)
        
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Populate with current custom actions
        def refresh_tree():
            tree.delete(*tree.get_children())
            actions = self._worker_actions.get(worker_id, [])
            for i, action in enumerate(actions):
                action_type = action.action if hasattr(action, 'action') else getattr(action, 'type', 'Unknown')
                target = ""
                value = ""
                
                # Get target/value based on action type
                if hasattr(action, 'value') and isinstance(action.value, dict):
                    if action_type == "FIND_IMAGE":
                        target = action.value.get("template_path", "")[:40]
                        value = f"conf={action.value.get('confidence', 0.8)}"
                    elif action_type == "CLICK":
                        target = f"({action.value.get('x', 0)}, {action.value.get('y', 0)})"
                        value = action.value.get("button", "left")
                    elif action_type in ("WAIT_TIME", "DELAY"):
                        value = f"{action.value.get('delay_ms', 0)}ms"
                    elif action_type == "KEY_PRESS":
                        target = action.value.get("key", "")
                    elif action_type == "LABEL":
                        target = action.value.get("name", "")
                    elif action_type == "GOTO":
                        target = action.value.get("target", "")
                    else:
                        target = str(action.value)[:40]
                
                tree.insert("", tk.END, values=(i+1, action_type, target, value))
            
            # Update count label
            count_label.config(text=f"Total: {len(actions)} actions")
            
            # Sync toggle button state
            use_custom_mode.set(len(actions) > 0)
            update_toggle_button()
        
        def copy_from_global():
            """Copy global action list to this worker"""
            if not self.actions:
                messagebox.showwarning("Cảnh báo", "Danh sách Global actions trống")
                return
            if messagebox.askyesno("Confirm", f"Sao chép {len(self.actions)} actions từ global list?"):
                self._worker_actions[worker_id] = [Action.from_dict(a.to_dict()) for a in self.actions]
                refresh_tree()
                messagebox.showinfo("Done", f"✅ Đã sao chép {len(self.actions)} actions")
        
        def load_from_file():
            """Load actions from .macro or .json file"""
            file_path = filedialog.askopenfilename(
                title="Chọn File Macro",
                initialdir=MACROS_DIR,
                filetypes=[
                    ("Macro files", "*.macro"),
                    ("JSON files", "*.json"),
                    ("All files", "*.*")
                ]
            )
            if not file_path:
                return
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Check for embedded format
                fmt = data.get("format", "")
                images = data.get("images", {})
                actions_data = data.get('actions', data) if isinstance(data, dict) else data
                
                if fmt == "embedded" and images:
                    # Extract embedded images
                    import base64
                    import tempfile
                    
                    macro_name = os.path.splitext(os.path.basename(file_path))[0]
                    temp_dir = os.path.join(tempfile.gettempdir(), "macro_images", f"worker_{worker_id}_{macro_name}")
                    os.makedirs(temp_dir, exist_ok=True)
                    
                    for img_key, img_b64 in images.items():
                        try:
                            img_data = base64.b64decode(img_b64)
                            img_path = os.path.join(temp_dir, img_key)
                            with open(img_path, "wb") as f:
                                f.write(img_data)
                        except Exception as e:
                            log(f"[UI] Failed to extract image {img_key}: {e}")
                    
                    # Update action paths
                    for action_data in actions_data:
                        if action_data.get("action") == "FIND_IMAGE":
                            template_path = action_data.get("value", {}).get("template_path", "")
                            if template_path.startswith("@embedded:"):
                                img_key = template_path.replace("@embedded:", "")
                                action_data["value"]["template_path"] = os.path.join(temp_dir, img_key)
                        
                        if action_data.get("action") == "WAIT_SCREEN_CHANGE":
                            ref_path = action_data.get("value", {}).get("reference_image", "")
                            if ref_path.startswith("@embedded:"):
                                img_key = ref_path.replace("@embedded:", "")
                                action_data["value"]["reference_image"] = os.path.join(temp_dir, img_key)
                
                # Parse actions
                loaded_actions = []
                if isinstance(actions_data, list):
                    for item in actions_data:
                        if isinstance(item, dict):
                            action = Action.from_dict(item)
                            loaded_actions.append(action)
                
                if loaded_actions:
                    # Ask: Replace or Append?
                    existing = self._worker_actions.get(worker_id, [])
                    if existing:
                        choice = messagebox.askyesnocancel(
                            "Load Actions",
                            f"Worker {worker_id} đã có {len(existing)} actions.\n\n"
                            f"YES = Thay thế bằng {len(loaded_actions)} actions mới\n"
                            f"NO = Thêm vào cuối (append)\n"
                            f"CANCEL = Hủy"
                        )
                        if choice is None:
                            return
                        elif choice:
                            self._worker_actions[worker_id] = loaded_actions
                        else:
                            self._worker_actions[worker_id].extend(loaded_actions)
                    else:
                        self._worker_actions[worker_id] = loaded_actions
                    
                    refresh_tree()
                    messagebox.showinfo("Done", f"✅ Loaded {len(loaded_actions)} actions")
                else:
                    messagebox.showwarning("Cảnh báo", "Không tìm thấy actions trong file")
                    
            except Exception as e:
                messagebox.showerror("Error", f"Lỗi đọc file: {e}")
        
        def clear_actions():
            """Clear all custom actions for this worker"""
            if messagebox.askyesno("Confirm", f"Xóa tất cả {len(self._worker_actions.get(worker_id, []))} custom actions?"):
                self._worker_actions[worker_id] = []
                refresh_tree()
        
        def remove_selected():
            """Remove selected action"""
            selection = tree.selection()
            if not selection:
                messagebox.showwarning("Warning", "Chưa chọn action nào")
                return
            indices = [int(tree.item(item)["values"][0]) - 1 for item in selection]
            indices.sort(reverse=True)
            actions = self._worker_actions.get(worker_id, [])
            for idx in indices:
                if 0 <= idx < len(actions):
                    del actions[idx]
            refresh_tree()
        
        # Toggle button state
        use_custom_mode = tk.BooleanVar(value=worker_id in self._worker_actions and len(self._worker_actions[worker_id]) > 0)
        
        def toggle_mode():
            """Toggle between Use Global and Use Custom"""
            if use_custom_mode.get():
                # Currently using custom -> switch to global
                if messagebox.askyesno("Confirm", "Switch to Global actions?\n\nCustom actions sẽ bị xóa!"):
                    if worker_id in self._worker_actions:
                        del self._worker_actions[worker_id]
                    use_custom_mode.set(False)
                    refresh_tree()
                    update_toggle_button()
                    messagebox.showinfo("Info", "✓ Worker sẽ dùng Global Actions")
            else:
                # Currently using global -> switch to custom
                use_custom_mode.set(True)
                update_toggle_button()
                messagebox.showinfo("Info", "✓ Worker sẽ dùng Custom Actions\n\nHãy thêm actions bằng Copy/Load")
        
        def update_toggle_button():
            """Update toggle button text and color"""
            if use_custom_mode.get():
                toggle_btn.config(text="🔧 Use Custom", bg=S.ACCENT_PURPLE)
            else:
                toggle_btn.config(text="🌐 Use Global", bg=S.BTN_SECONDARY)
        
        # Buttons - Toggle ở đầu tiên
        toggle_btn = tk.Button(btn_frame, text="", command=toggle_mode,
                              fg="white", font=(S.FONT_FAMILY, S.FONT_SIZE_SM, "bold"),
                              relief="flat", cursor="hand2", width=15)
        toggle_btn.pack(side="left", padx=(0, 10))
        update_toggle_button()
        
        tk.Button(btn_frame, text="📋 Copy từ Global", command=copy_from_global,
                 bg=S.ACCENT_BLUE, fg="white", font=(S.FONT_FAMILY, S.FONT_SIZE_SM),
                 relief="flat", cursor="hand2").pack(side="left", padx=2)
        tk.Button(btn_frame, text="📁 Load File", command=load_from_file,
                 bg=S.ACCENT_GREEN, fg="white", font=(S.FONT_FAMILY, S.FONT_SIZE_SM),
                 relief="flat", cursor="hand2").pack(side="left", padx=2)
        tk.Button(btn_frame, text="🗑️ Remove", command=remove_selected,
                 bg=S.ACCENT_ORANGE, fg="white", font=(S.FONT_FAMILY, S.FONT_SIZE_SM),
                 relief="flat", cursor="hand2").pack(side="left", padx=2)
        tk.Button(btn_frame, text="❌ Clear All", command=clear_actions,
                 bg=S.ACCENT_RED, fg="white", font=(S.FONT_FAMILY, S.FONT_SIZE_SM),
                 relief="flat", cursor="hand2").pack(side="left", padx=2)
        
        # ===== INFO & COUNT =====
        info_frame = tk.Frame(dialog, bg=S.BG_PRIMARY)
        info_frame.pack(fill="x", padx=S.PAD_MD, pady=S.PAD_XS)
        
        count_label = tk.Label(info_frame, text="Total: 0 actions", 
                              bg=S.BG_PRIMARY, fg=S.FG_PRIMARY,
                              font=(S.FONT_FAMILY, S.FONT_SIZE_SM, "bold"))
        count_label.pack(side="left")
        
        tk.Label(info_frame, text="💡 Worker có custom actions sẽ chạy riêng, không dùng global list",
                bg=S.BG_PRIMARY, fg=S.FG_MUTED,
                font=(S.FONT_FAMILY, S.FONT_SIZE_SM)).pack(side="right")
        
        # ===== CLOSE BUTTON =====
        close_frame = tk.Frame(dialog, bg=S.BG_PRIMARY)
        close_frame.pack(fill="x", padx=S.PAD_MD, pady=S.PAD_SM)
        
        def close_and_save():
            self._save_worker_actions()  # Auto-save when closing
            dialog.destroy()
        
        tk.Button(close_frame, text="✓ Lưu & Đóng", command=close_and_save,
                 bg=S.BTN_PRIMARY, fg="white", font=(S.FONT_FAMILY, S.FONT_SIZE_MD),
                 relief="flat", cursor="hand2", width=15).pack()
        
        # Initial load
        refresh_tree()
    
    def _clear_worker_actions(self, worker_id: int):
        """Clear custom actions for a specific worker"""
        if messagebox.askyesno("Confirm", f"Xóa custom actions của Worker {worker_id}?"):
            if worker_id in self._worker_actions:
                del self._worker_actions[worker_id]
            self._save_worker_actions()  # Auto-save
            log(f"[UI] Cleared custom actions for Worker {worker_id}")
    
    def _sync_selected_to_global(self):
        """Sync selected workers to Global (button handler)"""
        selected_items = self.worker_tree.selection()
        if not selected_items:
            messagebox.showwarning("Warning", "Please select at least one worker")
            return
        worker_ids = [int(self.worker_tree.item(item, "values")[0]) for item in selected_items if self.worker_tree.item(item, "values") and int(self.worker_tree.item(item, "values")[0]) > 0]
        if not worker_ids or not self.actions:
            return
        if messagebox.askyesno("Confirm", f"Copy Global ({len(self.actions)} actions) to {len(worker_ids)} worker(s)?"):
            for wid in worker_ids:
                self._worker_actions[wid] = [Action.from_dict(a.to_dict() if hasattr(a, 'to_dict') else a) for a in self.actions]
            self._save_worker_actions()
            self._auto_refresh_status()
            log(f"[UI] Synced {len(worker_ids)} workers to Global")
    
    def _revert_selected_to_global(self):
        """Revert selected workers to Global (button handler)"""
        selected_items = self.worker_tree.selection()
        if not selected_items:
            messagebox.showwarning("Warning", "Please select at least one worker")
            return
        worker_ids = [int(self.worker_tree.item(item, "values")[0]) for item in selected_items if self.worker_tree.item(item, "values") and int(self.worker_tree.item(item, "values")[0]) > 0]
        has_custom = [wid for wid in worker_ids if wid in self._worker_actions]
        if not has_custom:
            messagebox.showinfo("Thông tin", "Các worker đã chọn đang dùng Global")
            return
        if messagebox.askyesno("Confirm", f"Revert {len(has_custom)} worker(s) to Global?"):
            for wid in has_custom:
                del self._worker_actions[wid]
            self._save_worker_actions()
            self._auto_refresh_status()
            log(f"[UI] Reverted {len(has_custom)} workers to Global")
    
    def _sync_workers_to_global(self, worker_ids: list):
        """Sync workers to Global (menu handler)"""
        if not worker_ids or not self.actions:
            return
        if messagebox.askyesno("Confirm", f"Copy Global to {len(worker_ids)} worker(s)?"):
            for wid in worker_ids:
                self._worker_actions[wid] = [Action.from_dict(a.to_dict() if hasattr(a, 'to_dict') else a) for a in self.actions]
            self._save_worker_actions()
            self._auto_refresh_status()
    
    def _revert_workers_to_global(self, worker_ids: list):
        """Revert workers to Global (menu handler)"""
        has_custom = [wid for wid in worker_ids if wid in self._worker_actions]
        if not has_custom:
            messagebox.showinfo("Thông tin", "Đang dùng Global rồi")
            return
        if messagebox.askyesno("Confirm", f"Revert {len(has_custom)} worker(s)?"):
            for wid in has_custom:
                del self._worker_actions[wid]
            self._save_worker_actions()
            self._auto_refresh_status()

    # ================= RECORD/PLAY/PAUSE/STOP (per spec 1.1, 2, 3) =================
    
    def _setup_global_hotkeys(self):
        """Setup global hotkeys per spec 1.1"""
        if not MACRO_RECORDER_AVAILABLE:
            return
        
        try:
            self._hotkey_manager = GlobalHotkeyManager()
            self._hotkey_manager.register("ctrl+shift+r", self._toggle_record)
            self._hotkey_manager.register("ctrl+shift+p", self._toggle_play)
            self._hotkey_manager.register("ctrl+shift+space", self._toggle_pause)
            self._hotkey_manager.register("ctrl+shift+s", self._stop_all)
            self._hotkey_manager.start()
            log("[UI] Global hotkeys registered")
        except Exception as e:
            return
            log(f"[UI] Failed to setup global hotkeys: {e}")
    
    def _toggle_record(self):
        """Toggle recording on/off (per spec 2)"""
        if self._is_recording:
            self._stop_recording()
        else:
            self._start_recording()
    
    def _start_recording(self):
        """Start recording user actions - V2 using new recorder adapter
        Uses Button "Screen" selection (_capture_target_hwnd) to determine recording mode
        """
        if self._is_playing:
            messagebox.showwarning("Cảnh báo", "Không thể ghi khi đang phát")
            return
        
        # Check for recorder availability (prefer new adapter)
        if not RECORDER_ADAPTER_AVAILABLE and not MACRO_RECORDER_AVAILABLE:
            messagebox.showerror("Error", "Macro Recorder not available.\n\nPlease install pynput:\n  pip install pynput")
            return
        
        # Use Button "Screen" selection (unified with Capture)
        target_hwnd = getattr(self, '_capture_target_hwnd', None)
        target_name = getattr(self, '_capture_target_name', 'Screen (Full)')
        
        # Store for later use in convert_events
        self._target_hwnd = target_hwnd
        
        # Use new recorder adapter if available (fixes spec A1-A4 bugs)
        if RECORDER_ADAPTER_AVAILABLE:
            try:
                self._recorder = get_recorder()
                ui_hwnd = self.root.winfo_id()
                self._recorder.configure(target_hwnd=target_hwnd, ignore_ui_hwnd=ui_hwnd)
                self._recorder.start()
                self._is_recording = True
                mode_str = f"📷 {target_name}" if target_hwnd else "Full Screen"
                log(f"[UI] Recording started (V2), Mode: {mode_str}, hwnd={target_hwnd}")
            except ImportError as e:
                log(f"[UI] pynput not installed: {e}")
                messagebox.showerror("Error", "Cannot start recording.\n\npynput library not installed.\n\nPlease run:\n  pip install pynput")
                return
            except Exception as e:
                log(f"[UI] Recording failed: {e}")
                messagebox.showerror("Error", f"Recording failed: {e}")
                return
        else:
            # Fallback to old recorder
            self._recorded_events: List[RawEvent] = []
            self._recorder = MacroRecorder()
            # Note: old recorder may not have set_target_window, handle gracefully
            try:
                if hasattr(self._recorder, 'set_target_window'):
                    self._recorder.set_target_window(target_hwnd)
                self._recorder.start(self._on_record_event)
            except Exception as e:
                log(f"[UI] Old recorder failed: {e}")
                self._is_recording = False
                messagebox.showerror("Error", f"Recording failed: {e}")
                return
            log(f"[UI] Recording started (legacy), target hwnd: {target_hwnd}")
        
        # Update UI - show current recording mode
        self._update_ui_state()
        mode_display = f"📷 {target_name}" if target_hwnd else "Full Screen"
        self._update_status(f"🔴 Đang ghi ({mode_display})", "recording")
        self.btn_record.config(text="⏺ Dừng ghi", bg="#B71C1C")
        
        # Show floating recording toolbar
        self._show_recording_toolbar()
    
    def _show_recording_toolbar(self):
        """Show floating toolbar with Pause/Stop buttons during recording"""
        if self._recording_toolbar is not None:
            return
        
        toolbar = tk.Toplevel(self.root)
        toolbar.title("🔴 Đang ghi")
        toolbar.attributes("-topmost", True)  # Always on top
        toolbar.resizable(False, False)
        toolbar.overrideredirect(True)  # No title bar - we implement custom drag
        
        # Load saved position or use default (center of screen)
        saved_pos = self._load_toolbar_position()
        if saved_pos:
            toolbar.geometry(f"200x90+{saved_pos[0]}+{saved_pos[1]}")
        else:
            # Default: center of screen
            screen_w = toolbar.winfo_screenwidth()
            screen_h = toolbar.winfo_screenheight()
            x = (screen_w - 200) // 2
            y = (screen_h - 90) // 2
            toolbar.geometry(f"200x90+{x}+{y}")
        
        # Main frame with border for visual feedback
        main_frame = tk.Frame(toolbar, bg="#222222", highlightbackground="#f44336", highlightthickness=2)
        main_frame.pack(fill="both", expand=True)
        
        # Drag handle area (top part)
        drag_frame = tk.Frame(main_frame, bg="#444444", cursor="fleur")
        drag_frame.pack(fill="x", padx=2, pady=(2, 0))
        
        drag_label = tk.Label(drag_frame, text="⠿ 🔴 Recording - Drag to move", 
                              bg="#444444", fg="white", font=("Arial", 8))
        drag_label.pack(fill="x", pady=2)
        
        # Implement drag functionality
        self._toolbar_drag_data = {"x": 0, "y": 0}
        
        def start_drag(event):
            self._toolbar_drag_data["x"] = event.x
            self._toolbar_drag_data["y"] = event.y
        
        def do_drag(event):
            x = toolbar.winfo_x() + event.x - self._toolbar_drag_data["x"]
            y = toolbar.winfo_y() + event.y - self._toolbar_drag_data["y"]
            toolbar.geometry(f"+{x}+{y}")
        
        # Bind drag to drag frame and label
        drag_frame.bind("<ButtonPress-1>", start_drag)
        drag_frame.bind("<B1-Motion>", do_drag)
        drag_label.bind("<ButtonPress-1>", start_drag)
        drag_label.bind("<B1-Motion>", do_drag)
        
        # Frame with buttons
        btn_frame = tk.Frame(main_frame, bg="#333333")
        btn_frame.pack(fill="both", expand=True, padx=2, pady=2)
        
        # Pause/Resume button - use bind to stop BEFORE pynput gets the click
        self._toolbar_pause_btn = tk.Button(
            btn_frame, text="⏸ Tạm dừng",
            bg="#FF9800", fg="white", font=("Arial", 10, "bold"), width=8
        )
        self._toolbar_pause_btn.pack(side="left", padx=5, pady=5)
        # Bind ButtonPress to pause BEFORE the click is recorded
        self._toolbar_pause_btn.bind("<ButtonPress-1>", self._on_pause_button_press)
        
        # Stop button - use bind to stop BEFORE pynput gets the click
        stop_btn = tk.Button(
            btn_frame, text="⏹ Dừng",
            bg="#f44336", fg="white", font=("Arial", 10, "bold"), width=8
        )
        stop_btn.pack(side="left", padx=5, pady=5)
        # Bind ButtonPress to stop BEFORE the click is recorded
        stop_btn.bind("<ButtonPress-1>", self._on_stop_button_press)
        
        # Bind Esc key to stop recording (on toolbar)
        toolbar.bind("<Escape>", lambda e: self._stop_recording())
        
        self._recording_toolbar = toolbar
        
        # Add toolbar hwnd to ignore list so clicks on it are not recorded
        if self._recorder and hasattr(self._recorder, 'add_ignore_hwnd'):
            toolbar.update_idletasks()  # Ensure hwnd is available
            toolbar_hwnd = toolbar.winfo_id()
            self._recorder.add_ignore_hwnd(toolbar_hwnd)
        
        # Hide main window while recording
        self.root.withdraw()
        
        # Also bind Esc to main window during recording
        self.root.bind("<Escape>", self._on_escape_key)
    
    def _load_toolbar_position(self):
        """Load saved toolbar position from config"""
        config_path = "data/toolbar_position.json"
        try:
            if os.path.exists(config_path):
                with open(config_path, "r") as f:
                    data = json.load(f)
                    return (data.get("x", None), data.get("y", None))
        except:
            pass
        return None
    
    def _save_toolbar_position(self):
        """Save toolbar position to config"""
        if self._recording_toolbar is None:
            return
        try:
            # Get current position
            geo = self._recording_toolbar.geometry()
            # Parse "180x50+X+Y" format
            parts = geo.split("+")
            if len(parts) >= 3:
                x = int(parts[1])
                y = int(parts[2])
                
                config_path = "data/toolbar_position.json"
                os.makedirs("data", exist_ok=True)
                with open(config_path, "w") as f:
                    json.dump({"x": x, "y": y}, f)
        except Exception as e:
            log(f"[UI] Failed to save toolbar position: {e}")
    
    def _hide_recording_toolbar(self):
        """Hide the recording toolbar and restore main window"""
        if self._recording_toolbar is not None:
            # Save position before destroying
            self._save_toolbar_position()
            self._recording_toolbar.destroy()
            self._recording_toolbar = None
        # Unbind Esc from main window
        self.root.unbind("<Escape>")
        # Restore main window
        self.root.deiconify()
        self.root.lift()  # Bring to front
    
    def _toggle_recording_pause(self):
        """Toggle pause state during recording"""
        if not self._is_recording:
            return
        
        self._recording_paused = not self._recording_paused
        
        if self._recording_paused:
            # Pause recording
            if hasattr(self._recorder, 'pause'):
                self._recorder.pause()
            self._toolbar_pause_btn.config(text="▶ Tiếp tục", bg="#4CAF50")
            self._status_var.set("⏸ Tạm dừng ghi")
            log("[UI] Recording paused")
        else:
            # Resume recording
            if hasattr(self._recorder, 'resume'):
                self._recorder.resume()
            self._toolbar_pause_btn.config(text="⏸ Tạm dừng", bg="#FF9800")
            self._status_var.set("🔴 Đang ghi...")
            log("[UI] Recording resumed")
    
    def _on_pause_button_press(self, event=None):
        """Handle Pause button press - IMMEDIATELY pause/stop listeners BEFORE pynput gets click"""
        if not self._is_recording:
            return
        # Stop listeners FIRST to prevent recording this click
        if self._recorder:
            if self._recording_paused:
                # Will resume - but pause first to block this click
                pass  # Already paused, resume will happen after
            else:
                # Pause immediately
                if hasattr(self._recorder, 'pause'):
                    self._recorder.pause()
        # Schedule actual toggle after event processing
        self.root.after(50, self._toggle_recording_pause_after_click)
    
    def _toggle_recording_pause_after_click(self):
        """Toggle pause after the button click event is processed"""
        if not self._is_recording:
            return
        if self._recording_paused:
            # Was paused, now resume
            if hasattr(self._recorder, 'resume'):
                self._recorder.resume()
            self._recording_paused = False
            self._toolbar_pause_btn.config(text="⏸ Pause", bg="#FF9800")
            self._update_status("🔴 Recording...", "recording")
            log("[UI] Recording resumed")
        else:
            # Was recording, now paused (already paused in button press handler)
            self._recording_paused = True
            self._toolbar_pause_btn.config(text="▶ Resume", bg="#4CAF50")
            self._update_status("⏸ Recording Paused", "paused")
            log("[UI] Recording paused")
    
    def _on_stop_button_press(self, event=None):
        """Handle Stop button press - IMMEDIATELY stop listeners BEFORE pynput gets click"""
        if not self._is_recording:
            return
        # Stop listeners FIRST to prevent recording this click
        if self._recorder:
            # Stop the listeners immediately
            if hasattr(self._recorder, '_mouse_listener') and self._recorder._mouse_listener:
                try:
                    self._recorder._mouse_listener.stop()
                except:
                    pass
            if hasattr(self._recorder, '_keyboard_listener') and self._recorder._keyboard_listener:
                try:
                    self._recorder._keyboard_listener.stop()
                except:
                    pass
        # Schedule actual stop processing after event completes
        self.root.after(10, self._stop_recording)
    
    def _on_escape_key(self, event=None):
        """Handle Esc key press - stop recording if active"""
        if self._is_recording:
            self._stop_recording()
    
    def _stop_recording(self):
        """Stop recording and convert to action block - V2 compatible"""
        if not self._is_recording:
            return
        
        recorded_actions = []
        
        # Stop recorder and get events
        if self._recorder:
            if RECORDER_ADAPTER_AVAILABLE and hasattr(self._recorder, 'stop'):
                # V2 adapter returns events from stop()
                events = self._recorder.stop()
                if events:
                    recorded_actions = self._convert_recorded_events_to_actions(events)
            else:
                # Legacy recorder
                self._recorder.stop()
                if hasattr(self, '_recorded_events') and self._recorded_events:
                    recorded_actions = self._convert_events_to_actions(self._recorded_events)
        
        self._is_recording = False
        self._recording_paused = False
        
        # Hide recording toolbar
        self._hide_recording_toolbar()
        
        # Add each action individually (NOT as block) - để dễ chỉnh sửa
        if recorded_actions:
            for action in recorded_actions:
                self.actions.append(action)
            self._refresh_action_list()
            log(f"[UI] Added {len(recorded_actions)} recorded actions")
        
        # Update UI
        self._update_ui_state()
        self._update_status("● Ready", "ready")
        self.btn_record.config(text="⏺ Record", bg="#f44336")
        log("[UI] Recording stopped")
    
    def _convert_recorded_events_to_actions(self, events: List['RecordedEvent']) -> List[Action]:
        """
        Convert V2 RecordedEvent objects to Action objects
        Detects DRAG when: MOUSE_DOWN → (MOUSE_MOVE)+ → MOUSE_UP with distance > threshold
        Detects Hold when: MOUSE_DOWN → MOUSE_UP with duration > 200ms but distance < threshold
        """
        actions = []
        last_ts = None
        
        # Drag detection state
        pending_mouse_down = None  # Store MOUSE_DOWN waiting to see if it's a drag
        drag_threshold = 30  # Min pixels moved to consider it a drag
        
        i = 0
        while i < len(events):
            event = events[i]
            
            # Determine coordinates
            def get_coords(ev):
                x = ev.x_screen or 0
                y = ev.y_screen or 0
                use_screen = True
                if ev.x_client is not None and hasattr(ev, 'hwnd') and ev.hwnd:
                    x = ev.x_client
                    y = ev.y_client or 0
                    use_screen = False
                return x, y, use_screen
            
            x, y, use_screen = get_coords(event)
            
            # Convert based on event kind
            if event.kind == RecordedEventKind.MOUSE_DOWN:
                # Insert wait delay before mouse down
                if last_ts is not None and pending_mouse_down is None:
                    delta_ms = event.ts_ms - last_ts
                    if delta_ms > 50:
                        actions.append(Action(
                            action="WAIT",
                            value={"ms": delta_ms}
                        ))
                
                # Start potential drag - store and wait for UP
                pending_mouse_down = {
                    "event": event,
                    "x": x,
                    "y": y,
                    "use_screen": use_screen,
                    "ts": event.ts_ms
                }
                last_ts = event.ts_ms
                i += 1
                continue
            
            elif event.kind == RecordedEventKind.MOUSE_UP:
                if pending_mouse_down is not None:
                    # Check if this is a drag
                    start_x = pending_mouse_down["x"]
                    start_y = pending_mouse_down["y"]
                    end_x, end_y = x, y
                    
                    distance = ((end_x - start_x)**2 + (end_y - start_y)**2) ** 0.5
                    duration_ms = event.ts_ms - pending_mouse_down["ts"]
                    
                    if distance > drag_threshold:
                        # This is a DRAG
                        # Auto-set target_mode: emulator if client coords, screen if screen coords
                        target_mode = "screen" if pending_mouse_down["use_screen"] else "emulator"
                        actions.append(Action(
                            action="DRAG",
                            value={
                                "button": pending_mouse_down["event"].button or "left",
                                "x1": start_x,
                                "y1": start_y,
                                "x2": end_x,
                                "y2": end_y,
                                "duration_ms": max(100, duration_ms),
                                "screen_coords": pending_mouse_down["use_screen"],
                                "target_mode": target_mode
                            }
                        ))
                    else:
                        # This is a regular CLICK (or hold if duration is long)
                        btn = pending_mouse_down["event"].button or "left"
                        target_mode = "screen" if pending_mouse_down["use_screen"] else "emulator"
                        if duration_ms > 200:
                            # Long press - use hold_left/hold_right
                            hold_btn = f"hold_{btn}" if btn in ("left", "right") else btn
                            actions.append(Action(
                                action="CLICK",
                                value={
                                    "button": hold_btn,
                                    "x": start_x,
                                    "y": start_y,
                                    "hold_ms": duration_ms,
                                    "screen_coords": pending_mouse_down["use_screen"],
                                    "target_mode": target_mode
                                }
                            ))
                        else:
                            # Normal click
                            actions.append(Action(
                                action="CLICK",
                                value={
                                    "button": btn,
                                    "x": start_x,
                                    "y": start_y,
                                    "screen_coords": pending_mouse_down["use_screen"],
                                    "target_mode": target_mode
                                }
                            ))
                    
                    last_ts = event.ts_ms
                    pending_mouse_down = None
                # Ignore standalone MOUSE_UP
                i += 1
                continue
            
            elif event.kind == RecordedEventKind.MOUSE_MOVE:
                # Skip mouse moves (used for drag detection but not recorded as actions)
                i += 1
                continue
            
            elif event.kind == RecordedEventKind.WHEEL:
                # If there's a pending click, finalize it first
                if pending_mouse_down is not None:
                    target_mode = "screen" if pending_mouse_down["use_screen"] else "emulator"
                    actions.append(Action(
                        action="CLICK",
                        value={
                            "button": pending_mouse_down["event"].button or "left",
                            "x": pending_mouse_down["x"],
                            "y": pending_mouse_down["y"],
                            "screen_coords": pending_mouse_down["use_screen"],
                            "target_mode": target_mode
                        }
                    ))
                    pending_mouse_down = None
                
                # Insert wait delay
                if last_ts is not None:
                    delta_ms = event.ts_ms - last_ts
                    if delta_ms > 50:
                        actions.append(Action(
                            action="WAIT",
                            value={"ms": delta_ms}
                        ))
                
                target_mode = "screen" if use_screen else "emulator"
                actions.append(Action(
                    action="WHEEL",
                    value={
                        "delta": event.wheel_delta or 0,
                        "x": x,
                        "y": y,
                        "screen_coords": use_screen,
                        "target_mode": target_mode
                    }
                ))
                last_ts = event.ts_ms
            
            elif event.kind == RecordedEventKind.KEY_DOWN:
                # If there's a pending click, finalize it first
                if pending_mouse_down is not None:
                    actions.append(Action(
                        action="CLICK",
                        value={
                            "button": pending_mouse_down["event"].button or "left",
                            "x": pending_mouse_down["x"],
                            "y": pending_mouse_down["y"],
                            "screen_coords": pending_mouse_down["use_screen"]
                        }
                    ))
                    pending_mouse_down = None
                
                # Insert wait delay
                if last_ts is not None:
                    delta_ms = event.ts_ms - last_ts
                    if delta_ms > 50:
                        actions.append(Action(
                            action="WAIT",
                            value={"ms": delta_ms}
                        ))
                
                actions.append(Action(
                    action="KEY_PRESS",
                    value={
                        "key": event.key or "",
                        "repeat": 1
                    }
                ))
                last_ts = event.ts_ms
            
            i += 1
        
        # Handle any remaining pending mouse down
        if pending_mouse_down is not None:
            actions.append(Action(
                action="CLICK",
                value={
                    "button": pending_mouse_down["event"].button or "left",
                    "x": pending_mouse_down["x"],
                    "y": pending_mouse_down["y"],
                    "screen_coords": pending_mouse_down["use_screen"]
                }
            ))
        
        return actions
    
    def _on_record_event(self, event: 'RawEvent'):
        """Callback for recorded events"""
        if hasattr(self, '_recorded_events'):
            self._recorded_events.append(event)
    
    def _convert_events_to_actions(self, events: List['RawEvent']) -> List[Action]:
        """Convert raw events to Action objects (per spec 2.1, 2.4)"""
        actions = []
        last_timestamp = None
        
        for event in events:
            # Insert wait delays (per spec 2.4)
            if last_timestamp is not None:
                delta_ms = int((event.timestamp - last_timestamp) * 1000)
                if delta_ms > 50:  # Ignore tiny delays
                    actions.append(Action(
                        action="WAIT",
                        value={"ms": delta_ms}
                    ))
            last_timestamp = event.timestamp
            
            # Convert event to action
            if event.event_type == RawEventType.MOUSE_DOWN:
                # Legacy recorder: check if we have target_hwnd from recording session
                target_mode = "screen" if getattr(self, '_target_hwnd', None) is None else "emulator"
                actions.append(Action(
                    action="CLICK",
                    value={
                        "button": event.button or "left",
                        "x": event.x or 0,
                        "y": event.y or 0,
                        "target_mode": target_mode
                    }
                ))
            elif event.event_type == RawEventType.MOUSE_SCROLL:
                target_mode = "screen" if getattr(self, '_target_hwnd', None) is None else "emulator"
                actions.append(Action(
                    action="WHEEL",
                    value={
                        "delta": event.scroll_delta or 0,
                        "x": event.x or 0,
                        "y": event.y or 0,
                        "target_mode": target_mode
                    }
                ))
            elif event.event_type == RawEventType.KEY_DOWN:
                actions.append(Action(
                    action="KEY_PRESS",
                    value={
                        "key": event.key or "",
                        "repeat": 1
                    }
                ))
        
        return actions
    
    def _get_target_window(self) -> Optional[int]:
        """Get target window hwnd for recording. Returns None for Full Screen mode."""
        # If workers available, ask user to choose
        if self.workers:
            # Build choice dialog
            choices = ["Full Screen (record all clicks)"]
            for i, w in enumerate(self.workers):
                worker_name = getattr(w, 'name', None) or f"Worker {w.id}"
                choices.append(f"{worker_name} ({w.hwnd})")
            
            # Simple dialog
            dialog = tk.Toplevel(self.root)
            dialog.title("Recording Target")
            dialog.geometry("300x200")
            dialog.transient(self.root)
            dialog.grab_set()
            
            tk.Label(dialog, text="Select recording target:").pack(pady=10)
            
            selected = tk.StringVar(value=choices[0])
            for c in choices:
                tk.Radiobutton(dialog, text=c, variable=selected, value=c).pack(anchor='w', padx=20)
            
            result = [None]  # Use list to allow modification in nested function
            
            def on_ok():
                choice = selected.get()
                if choice == choices[0]:
                    result[0] = 0  # Full Screen - special marker
                else:
                    # Extract hwnd from choice
                    for w in self.workers:
                        if str(w.hwnd) in choice:
                            result[0] = w.hwnd
                            break
                dialog.destroy()
            
            def on_cancel():
                dialog.destroy()
            
            btn_frame = tk.Frame(dialog)
            btn_frame.pack(pady=10)
            tk.Button(btn_frame, text="OK", command=on_ok, width=10).pack(side='left', padx=5)
            tk.Button(btn_frame, text="Cancel", command=on_cancel, width=10).pack(side='left', padx=5)
            
            self.root.wait_window(dialog)
            
            if result[0] == 0:
                return None  # Full Screen mode
            return result[0]
        
        # No workers - ask user to select window or Full Screen
        result = messagebox.askyesnocancel(
            "Recording Target",
            "No worker selected.\n\n"
            "Click YES for Full Screen recording (records all mouse events)\n"
            "Click NO to select a specific window (3 second delay)"
        )
        
        if result is None:  # Cancel
            return -1  # Cancel marker
        
        if result:  # Yes = Full Screen
            return None
        
        # No = Select window
        self.root.iconify()
        time.sleep(3)
        hwnd = WindowUtils.get_foreground_window()
        self.root.deiconify()
        return hwnd if hwnd else -1
    
    def _toggle_play(self):
        """Toggle playback on/off"""
        if self._is_playing:
            self._stop_playback()
        else:
            self._start_playback()
    
    def _start_playback(self):
        """Start playing actions on all ready workers (multi-worker support)"""
        if self._is_recording:
            messagebox.showwarning("Cảnh báo", "Không thể phát khi đang ghi")
            return
        
        if not self.actions and not self._worker_actions:
            messagebox.showwarning("Cảnh báo", "Không có actions để phát")
            return
        
        self._is_playing = True
        self._is_paused = False
        self._playback_stop_event.clear()
        self._playback_pause_event.clear()
        self._current_action_index = 0
        self._repeat_counters = {}  # Reset repeat counters for new playback
        
        # Clear previous worker threads
        self._worker_playback_threads.clear()
        self._worker_stop_events.clear()
        
        # Get ready workers with valid hwnd (case-insensitive status check)
        ready_workers = [w for w in self.workers if w.hwnd and hasattr(w, 'status') and w.status.upper() == 'READY']
        
        if ready_workers:
            # Multi-worker playback - each worker runs in its own thread
            for worker in ready_workers:
                stop_event = threading.Event()
                self._worker_stop_events[worker.id] = stop_event
                
                # Check if worker has custom actions
                worker_actions = self._worker_actions.get(worker.id, None)
                if worker_actions:
                    # Use worker-specific actions
                    actions_to_play = worker_actions
                    log(f"[UI] Worker {worker.id}: Using custom actions ({len(actions_to_play)} actions)")
                else:
                    # Use global action list
                    actions_to_play = self.actions
                    log(f"[UI] Worker {worker.id}: Using global actions ({len(actions_to_play)} actions)")
                
                thread = threading.Thread(
                    target=self._worker_playback_loop,
                    args=(worker, actions_to_play, stop_event),
                    daemon=True
                )
                self._worker_playback_threads[worker.id] = thread
                thread.start()
            
            log(f"[UI] Started playback on {len(ready_workers)} workers")
        else:
            # No ready workers - use single-thread playback (screen mode)
            self._player_thread = threading.Thread(target=self._playback_loop, daemon=True)
            self._player_thread.start()
            log("[UI] Playback started (Screen mode - no workers)")
        
        # Show playback toolbar
        self._show_playback_toolbar()
        
        # Update UI
        self._update_ui_state()
        status_text = f"▶ Playing on {len(ready_workers)} workers..." if ready_workers else "▶ Playing..."
        self._update_status(status_text, "playing")
    
    def _worker_playback_loop(self, worker, actions: List[Action], stop_event: threading.Event):
        """Playback loop for a specific worker - runs in its own thread"""
        import ctypes
        from ctypes import wintypes
        
        target_hwnd = worker.hwnd
        worker_id = worker.id
        action_index = 0
        
        # Get ADB serial for this worker
        adb_serial = worker.adb_device if hasattr(worker, 'adb_device') else None
        
        log(f"[Worker {worker_id}] Starting playback: {len(actions)} actions, hwnd={target_hwnd}, adb={adb_serial}")
        
        while action_index < len(actions):
            # Check stop
            if stop_event.is_set() or self._playback_stop_event.is_set():
                log(f"[Worker {worker_id}] Playback stopped")
                break
            
            # Check pause
            while self._playback_pause_event.is_set():
                if stop_event.is_set() or self._playback_stop_event.is_set():
                    break
                time.sleep(0.1)
            
            action = actions[action_index]
            
            # Skip disabled actions
            if not action.enabled:
                action_index += 1
                continue
            
            # Execute action
            try:
                self._execute_action(action, target_hwnd, adb_serial=adb_serial)
            except Exception as e:
                log(f"[Worker {worker_id}] Action error: {e}")
            
            action_index += 1
        
        # Release modifiers
        self._release_all_modifiers()
        log(f"[Worker {worker_id}] Playback complete")
        
        # Check if all workers are done
        self._check_all_workers_complete()
    
    def _check_all_workers_complete(self):
        """Check if all worker threads have completed"""
        all_done = True
        for worker_id, thread in self._worker_playback_threads.items():
            if thread.is_alive():
                all_done = False
                break
        
        if all_done and self._is_playing:
            self.root.after(0, self._on_playback_complete)
    
    def _get_worker_for_hwnd(self, hwnd):
        """Get worker object by hwnd for scale factor lookup"""
        if not hwnd:
            return None
        for w in self.workers:
            if w.hwnd == hwnd:
                return w
        return None
    
    def _playback_loop(self):
        """Main playback loop running in thread"""
        import ctypes
        from ctypes import wintypes
        
        # Get target worker - try to find any available hwnd
        target_worker = self.workers[0] if self.workers else None
        target_hwnd = target_worker.hwnd if target_worker else None
        adb_serial = None
        
        # If no hwnd from worker, try to find any LDPlayer window for emulator-mode actions
        if not target_hwnd:
            try:
                from initialize_workers import detect_ldplayer_windows
                ldplayer_wins = detect_ldplayer_windows()
                if ldplayer_wins:
                    target_hwnd = ldplayer_wins[0]['hwnd']
                    log(f"[UI] Auto-detected LDPlayer hwnd={target_hwnd} for emulator-mode actions")
            except:
                pass
        
        # Detect ADB serial from target hwnd
        if target_hwnd:
            try:
                # Get window title to detect emulator name
                title_length = ctypes.windll.user32.GetWindowTextLengthW(target_hwnd)
                if title_length > 0:
                    title_buffer = ctypes.create_unicode_buffer(title_length + 1)
                    ctypes.windll.user32.GetWindowTextW(target_hwnd, title_buffer, title_length + 1)
                    window_title = title_buffer.value
                    adb_serial = self._detect_adb_serial(window_title, hwnd=target_hwnd)
                    if adb_serial:
                        log(f"[UI] Detected ADB serial: {adb_serial} for hwnd={target_hwnd}")
            except Exception as e:
                log(f"[UI] Failed to detect ADB serial: {e}")
        
        log(f"[UI] Playback loop: {len(self.actions)} actions, target_hwnd={target_hwnd}, adb_serial={adb_serial}")
        
        while self._current_action_index < len(self.actions):
            # Check stop
            if self._playback_stop_event.is_set():
                log("[UI] Playback stopped by user")
                break
            
            # Check pause (per spec 3.2)
            while self._playback_pause_event.is_set():
                if self._playback_stop_event.is_set():
                    break
                time.sleep(0.1)
            
            action = self.actions[self._current_action_index]
            log(f"[UI] Executing action {self._current_action_index}: {action.action} = {action.value}")
            
            # Update mini playback log - highlight current row
            self.root.after(0, lambda idx=self._current_action_index: self._highlight_mini_log_row(idx, "running"))
            
            # Skip disabled actions
            if not action.enabled:
                self.root.after(0, lambda idx=self._current_action_index: self._highlight_mini_log_row(idx, "skipped"))
                self._current_action_index += 1
                continue
            
            # Execute action
            action_success = True
            try:
                self._execute_action(action, target_hwnd, adb_serial=adb_serial)
            except Exception as e:
                log(f"[UI] Action error: {e}")
                import traceback
                log(f"[UI] Traceback: {traceback.format_exc()}")
                action_success = False
                # Per spec 3.4 - skip on error
            
            # Mark action as done or error
            status = "done" if action_success else "error"
            self.root.after(0, lambda idx=self._current_action_index, s=status: self._highlight_mini_log_row(idx, s))
            
            self._current_action_index += 1
        
        # Done - release any held modifiers
        self._release_all_modifiers()
        self._is_playing = False
        log("[UI] Playback complete")
        self.root.after(0, self._on_playback_complete)
    
    def _paste_text(self, text: str):
        """Paste text using clipboard (Ctrl+V)"""
        import ctypes
        
        try:
            # Use tkinter clipboard (more reliable)
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            self.root.update()  # Required for clipboard to work
            
            # Small delay to ensure clipboard is ready
            time.sleep(0.05)
            
            # Send Ctrl+V
            VK_CTRL = 0x11
            VK_V = 0x56
            ctypes.windll.user32.keybd_event(VK_CTRL, 0, 0, 0)  # Ctrl down
            time.sleep(0.05)
            ctypes.windll.user32.keybd_event(VK_V, 0, 0, 0)  # V down
            time.sleep(0.05)
            ctypes.windll.user32.keybd_event(VK_V, 0, 2, 0)  # V up
            time.sleep(0.05)
            ctypes.windll.user32.keybd_event(VK_CTRL, 0, 2, 0)  # Ctrl up
            
            log(f"[UI] Pasted text: {text[:30]}...")
        except Exception as e:
            log(f"[UI] Paste error: {e}")
    
    def _type_text_humanize(self, text: str, speed_ms: int = 100):
        """Type text character by character with configurable delays"""
        import ctypes
        import random
        # Calculate delay range based on speed_ms
        base_delay = speed_ms / 1000.0
        min_delay = max(0.02, base_delay * 0.5)
        max_delay = base_delay * 1.5
        for char in text:
            if self._playback_stop_event.is_set():
                break
            # Nếu là xuống dòng thì Enter
            if char == '\n':
                ctypes.windll.user32.keybd_event(0x0D, 0, 0, 0)
                time.sleep(0.02)
                ctypes.windll.user32.keybd_event(0x0D, 0, 2, 0)
                time.sleep(random.uniform(min_delay, max_delay))
                continue
            # Nếu là tab thì Tab
            if char == '\t':
                ctypes.windll.user32.keybd_event(0x09, 0, 0, 0)
                time.sleep(0.02)
                ctypes.windll.user32.keybd_event(0x09, 0, 2, 0)
                time.sleep(random.uniform(min_delay, max_delay))
                continue
            # Paste từng ký tự bằng clipboard và Ctrl+V
            self.root.clipboard_clear()
            self.root.clipboard_append(char)
            self.root.update()
            time.sleep(0.03)
            VK_CTRL = 0x11
            VK_V = 0x56
            ctypes.windll.user32.keybd_event(VK_CTRL, 0, 0, 0)
            time.sleep(0.01)
            ctypes.windll.user32.keybd_event(VK_V, 0, 0, 0)
            time.sleep(0.01)
            ctypes.windll.user32.keybd_event(VK_V, 0, 2, 0)
            time.sleep(0.01)
            ctypes.windll.user32.keybd_event(VK_CTRL, 0, 2, 0)
            time.sleep(random.uniform(min_delay, max_delay))
        log(f"[UI] Typed text (humanize-paste, speed={speed_ms}ms): {text[:30]}...")
    
    def _send_unicode_char(self, char: str):
        """Send a single Unicode character using SendInput"""
        import ctypes
        from ctypes import wintypes
        
        # INPUT structure for SendInput
        class KEYBDINPUT(ctypes.Structure):
            _fields_ = [
                ("wVk", wintypes.WORD),
                ("wScan", wintypes.WORD),
                ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD),
                ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))
            ]
        
        class INPUT(ctypes.Structure):
            _fields_ = [
                ("type", wintypes.DWORD),
                ("ki", KEYBDINPUT)
            ]
        
        KEYEVENTF_UNICODE = 0x0004
        KEYEVENTF_KEYUP = 0x0002
        INPUT_KEYBOARD = 1
        
        # Key down
        inp_down = INPUT()
        inp_down.type = INPUT_KEYBOARD
        inp_down.ki.wVk = 0
        inp_down.ki.wScan = ord(char)
        inp_down.ki.dwFlags = KEYEVENTF_UNICODE
        
        # Key up
        inp_up = INPUT()
        inp_up.type = INPUT_KEYBOARD
        inp_up.ki.wVk = 0
        inp_up.ki.wScan = ord(char)
        inp_up.ki.dwFlags = KEYEVENTF_UNICODE | KEYEVENTF_KEYUP
        
        ctypes.windll.user32.SendInput(1, ctypes.byref(inp_down), ctypes.sizeof(INPUT))
        time.sleep(0.02)
        ctypes.windll.user32.SendInput(1, ctypes.byref(inp_up), ctypes.sizeof(INPUT))

    def _send_key(self, key: str, repeat: int = 1):
        """Send keyboard key using Win32 API - handles modifiers properly"""
        import ctypes
        
        # Virtual key codes - comprehensive with aliases
        VK_MAP = {
            # Modifiers and aliases
            'alt': 0x12, 'alt_l': 0x12, 'alt_r': 0x12, 'menu': 0x12,
            'ctrl': 0x11, 'ctrl_l': 0x11, 'ctrl_r': 0x11, 'control': 0x11, 'control_l': 0x11, 'control_r': 0x11,
            'shift': 0x10, 'shift_l': 0x10, 'shift_r': 0x10,
            'win': 0x5B, 'windows': 0x5B, 'super': 0x5B, 'cmd': 0x5B, 'command': 0x5B,
            
            # Navigation keys and aliases
            'tab': 0x09,
            'enter': 0x0D, 'return': 0x0D, 'ret': 0x0D,
            'space': 0x20, 'spacebar': 0x20, ' ': 0x20,
            'backspace': 0x08, 'back': 0x08, 'bs': 0x08,
            'delete': 0x2E, 'del': 0x2E,
            'escape': 0x1B, 'esc': 0x1B,
            'home': 0x24,
            'end': 0x23,
            'page_up': 0x21, 'pageup': 0x21, 'pgup': 0x21, 'prior': 0x21,
            'page_down': 0x22, 'pagedown': 0x22, 'pgdn': 0x22, 'next': 0x22,
            'up': 0x26, 'arrow_up': 0x26, 'uparrow': 0x26,
            'down': 0x28, 'arrow_down': 0x28, 'downarrow': 0x28,
            'left': 0x25, 'arrow_left': 0x25, 'leftarrow': 0x25,
            'right': 0x27, 'arrow_right': 0x27, 'rightarrow': 0x27,
            'insert': 0x2D, 'ins': 0x2D,
            
            # Function keys
            'f1': 0x70, 'f2': 0x71, 'f3': 0x72, 'f4': 0x73,
            'f5': 0x74, 'f6': 0x75, 'f7': 0x76, 'f8': 0x77,
            'f9': 0x78, 'f10': 0x79, 'f11': 0x7A, 'f12': 0x7B,
            'f13': 0x7C, 'f14': 0x7D, 'f15': 0x7E, 'f16': 0x7F,
            
            # Lock keys and aliases
            'caps_lock': 0x14, 'capslock': 0x14, 'caps': 0x14,
            'num_lock': 0x90, 'numlock': 0x90,
            'scroll_lock': 0x91, 'scrolllock': 0x91, 'scroll': 0x91,
            
            # Numpad keys
            'numpad0': 0x60, 'num0': 0x60, 'kp_0': 0x60,
            'numpad1': 0x61, 'num1': 0x61, 'kp_1': 0x61,
            'numpad2': 0x62, 'num2': 0x62, 'kp_2': 0x62,
            'numpad3': 0x63, 'num3': 0x63, 'kp_3': 0x63,
            'numpad4': 0x64, 'num4': 0x64, 'kp_4': 0x64,
            'numpad5': 0x65, 'num5': 0x65, 'kp_5': 0x65,
            'numpad6': 0x66, 'num6': 0x66, 'kp_6': 0x66,
            'numpad7': 0x67, 'num7': 0x67, 'kp_7': 0x67,
            'numpad8': 0x68, 'num8': 0x68, 'kp_8': 0x68,
            'numpad9': 0x69, 'num9': 0x69, 'kp_9': 0x69,
            'multiply': 0x6A, 'numpad*': 0x6A, 'kp_multiply': 0x6A,
            'add': 0x6B, 'numpad+': 0x6B, 'kp_add': 0x6B,
            'subtract': 0x6D, 'numpad-': 0x6D, 'kp_subtract': 0x6D,
            'decimal': 0x6E, 'numpad.': 0x6E, 'kp_decimal': 0x6E,
            'divide': 0x6F, 'numpad/': 0x6F, 'kp_divide': 0x6F,
            
            # Media keys
            'volume_mute': 0xAD, 'mute': 0xAD,
            'volume_down': 0xAE, 'volumedown': 0xAE,
            'volume_up': 0xAF, 'volumeup': 0xAF,
            'media_next': 0xB0, 'next_track': 0xB0,
            'media_prev': 0xB1, 'prev_track': 0xB1,
            'media_stop': 0xB2,
            'media_play_pause': 0xB3, 'play_pause': 0xB3,
            
            # Browser keys
            'browser_back': 0xA6, 'browser_forward': 0xA7,
            'browser_refresh': 0xA8, 'browser_stop': 0xA9,
            'browser_search': 0xAA, 'browser_favorites': 0xAB,
            'browser_home': 0xAC,
            
            # Misc keys
            'print_screen': 0x2C, 'printscreen': 0x2C, 'prtsc': 0x2C, 'snapshot': 0x2C,
            'pause': 0x13, 'break': 0x13,
            'apps': 0x5D, 'context_menu': 0x5D, 'menu_key': 0x5D,
        }
        
        MODIFIER_KEYS = {'alt', 'alt_l', 'alt_r', 'ctrl', 'ctrl_l', 'ctrl_r', 'shift', 'shift_l', 'shift_r', 'win'}
        
        # Clean up key name
        key_clean = key.lower().replace('key.', '').strip()
        
        # Get VK code
        if key_clean in VK_MAP:
            vk = VK_MAP[key_clean]
        elif len(key_clean) == 1:
            # Single character - get VK using VkKeyScanW
            # VkKeyScanW expects wchar (int), but need to handle return value properly
            from ctypes import wintypes
            ctypes.windll.user32.VkKeyScanW.argtypes = [wintypes.WCHAR]
            ctypes.windll.user32.VkKeyScanW.restype = ctypes.c_short
            result = ctypes.windll.user32.VkKeyScanW(key_clean)
            if result == -1:
                log(f"[UI] Cannot map key: {key_clean}")
                return
            vk = result & 0xFF
            shift_needed = (result >> 8) & 1
            # If shift needed, press shift
            if shift_needed:
                ctypes.windll.user32.keybd_event(0x10, 0, 0, 0)  # Shift down
                time.sleep(0.01)
        else:
            # Try alphanumeric mapping
            if key_clean.isalnum() and len(key_clean) == 1:
                vk = ord(key_clean.upper())
            else:
                log(f"[UI] Unknown key: {key}")
                return
        
        is_modifier = key_clean in MODIFIER_KEYS
        
        # Send key press
        for _ in range(repeat):
            ctypes.windll.user32.keybd_event(vk, 0, 0, 0)  # Key down
            time.sleep(0.02)
            # For modifiers, KEEP PRESSED until next action (allows combos like Alt+Tab)
            # Will be released at end of playback or when non-modifier key is pressed
            if not is_modifier:
                ctypes.windll.user32.keybd_event(vk, 0, 2, 0)  # Key up
                time.sleep(0.02)
                # Release shift if it was pressed
                if len(key_clean) == 1:
                    ctypes.windll.user32.keybd_event(0x10, 0, 2, 0)  # Shift up
                # Release any held modifiers after the key
                self._release_all_modifiers()
    
    def _release_all_modifiers(self):
        """Release all modifier keys"""
        import ctypes
        VK_ALT = 0x12
        VK_CTRL = 0x11
        VK_SHIFT = 0x10
        ctypes.windll.user32.keybd_event(VK_ALT, 0, 2, 0)
        ctypes.windll.user32.keybd_event(VK_CTRL, 0, 2, 0)
        ctypes.windll.user32.keybd_event(VK_SHIFT, 0, 2, 0)
    
    def _execute_action(self, action: Action, target_hwnd: Optional[int], adb_serial: Optional[str] = None):
        """Execute a single action using SendInput (per spec 6.2)
        
        Args:
            action: Action to execute
            target_hwnd: Target window handle
            adb_serial: ADB device serial for emulator-based actions
        """
        import ctypes
        from ctypes import wintypes
        
        v = action.value
        
        if action.action == "WAIT":
            time.sleep(v.get("ms", 0) / 1000.0)
        
        elif action.action == "CLICK":
            x, y = v.get("x", 0), v.get("y", 0)
            btn = v.get("button", "left")
            hold_ms = v.get("hold_ms", 0)
            use_current_pos = v.get("use_current_pos", False)
            
            # Check if this is a scheduled click
            if v.get("schedule_enabled", False):
                import datetime
                schedule_time_str = v.get("schedule_time", "23:59:59")
                
                try:
                    # Parse scheduled time
                    time_parts = schedule_time_str.split(":")
                    target_hour = int(time_parts[0])
                    target_minute = int(time_parts[1])
                    target_second = int(time_parts[2])
                    
                    log(f"[CLICK] Scheduled for {schedule_time_str}, waiting...")
                    
                    # Wait until scheduled time
                    while True:
                        now = datetime.datetime.now()
                        
                        # Check if stop/pause requested
                        if self._playback_stop_event.is_set():
                            log(f"[CLICK] Schedule cancelled (stop requested)")
                            return
                        
                        while self._playback_pause_event.is_set():
                            if self._playback_stop_event.is_set():
                                return
                            time.sleep(0.1)
                        
                        # Check if target time reached
                        if (now.hour == target_hour and 
                            now.minute == target_minute and 
                            now.second == target_second):
                            log(f"[CLICK] Scheduled time reached: {schedule_time_str}, executing click")
                            break
                        
                        # Check if target time has passed (schedule for tomorrow)
                        target_time = now.replace(hour=target_hour, minute=target_minute, second=target_second, microsecond=0)
                        if now > target_time:
                            log(f"[CLICK] Scheduled time {schedule_time_str} has passed today, will execute next occurrence")
                            # Wait for next occurrence (could be tomorrow)
                            # For now, wait 1 second and check again
                            time.sleep(1)
                            continue
                        
                        # Sleep for 0.5 second to avoid busy wait
                        time.sleep(0.5)
                    
                except Exception as e:
                    log(f"[CLICK] Schedule error: {e}, executing immediately")
            
            # Determine target mode for this action
            # - Respect saved target_mode from user's choice (screen vs emulator)
            # - Legacy actions without target_mode: infer from screen_coords flag
            # - Default: "screen" (full screen mode - no hwnd dependency)
            if "target_mode" in v:
                target_mode = v["target_mode"]  # Use saved mode from recording
            elif "screen_coords" in v:
                # Legacy action: infer from screen_coords flag
                target_mode = "screen" if v["screen_coords"] else "emulator"
            else:
                # No saved mode: default to screen (full screen mode)
                target_mode = "screen"
                log(f"[CLICK] No target_mode saved, defaulting to 'screen' (full screen mode)")
            
            # Set effective_hwnd ONLY if target_mode is "emulator"
            # If target_mode is "screen", ignore target_hwnd completely
            effective_hwnd = target_hwnd if target_mode == "emulator" else None
            
            # Get input method from settings
            input_method = self._input_settings.get("click_method", "SetCursorPos")
            
            # Validate input method with target mode - all ADB methods require emulator
            if input_method in ("PostMessage", "ADB Tap") and target_mode != "emulator":
                log(f"[CLICK] {input_method} requires Emulator mode, fallback to SetCursorPos")
                input_method = "SetCursorPos"
            
            # Calculate coordinates based on input method
            if use_current_pos:
                # Use current mouse position (only for SetCursorPos)
                cursor_pt = wintypes.POINT()
                ctypes.windll.user32.GetCursorPos(ctypes.byref(cursor_pt))
                screen_x, screen_y = cursor_pt.x, cursor_pt.y
                client_x, client_y = screen_x, screen_y  # Initialize for fallback cases
                log(f"[CLICK] Using current mouse position: ({screen_x},{screen_y})")
            else:
                # Initialize from action coordinates
                client_x, client_y = int(x), int(y)
                screen_x, screen_y = int(x), int(y)
                
                # Convert coordinates if needed based on input method
                if input_method == "SetCursorPos":
                    # SetCursorPos needs screen coordinates
                    if effective_hwnd:
                        # Convert client coords to screen coords
                        pt = wintypes.POINT(int(x), int(y))
                        ctypes.windll.user32.ClientToScreen(effective_hwnd, ctypes.byref(pt))
                        screen_x, screen_y = pt.x, pt.y
                        log(f"[CLICK] SetCursorPos: client({x},{y}) -> screen({screen_x},{screen_y}) [hwnd={effective_hwnd}]")
                    else:
                        # Screen mode: coords are already screen coords
                        screen_x, screen_y = int(x), int(y)
                        log(f"[CLICK] SetCursorPos: using screen coords ({screen_x},{screen_y})")
                else:
                    log(f"[CLICK] {input_method}: using client coords ({client_x},{client_y})")
            
            # Execute click based on input method
            # Check if this is an ADB-based method
            if input_method == "ADB Tap" and adb_serial and effective_hwnd:
                # METHOD 1: ADB Tap - Use uiautomator2 (same as FIND_IMAGE)
                # 1. uiautomator2 (uses accessibility framework)
                # 2. Sendevent fallback (raw hardware events)
                # 3. SetCursorPos fallback
                import subprocess
                tap_success = False
                
                # Method 1: Try uiautomator2 first (most reliable, uses accessibility)
                try:
                    import uiautomator2 as u2
                    
                    # Get window client area size
                    user32 = ctypes.windll.user32
                    rect = wintypes.RECT()
                    user32.GetClientRect(effective_hwnd, ctypes.byref(rect))
                    client_width = rect.right - rect.left
                    client_height = rect.bottom - rect.top
                    
                    # Get Android display size
                    cmd_size = f"adb -s {adb_serial} shell wm size"
                    size_result = subprocess.run(cmd_size, shell=True, capture_output=True, text=True, timeout=2,
                                                creationflags=CREATE_NO_WINDOW if sys.platform == 'win32' else 0)
                    import re
                    match = re.search(r'(\d+)x(\d+)', size_result.stdout)
                    if match:
                        android_width, android_height = int(match.group(1)), int(match.group(2))
                    else:
                        android_width, android_height = 400, 550
                    
                    log(f"[CLICK] Window client: {client_width}x{client_height}, Android: {android_width}x{android_height}")
                    
                    # Calculate offset and scale
                    offset_x = 0
                    offset_y = 0
                    scale_x = 1.0
                    scale_y = 1.0
                    
                    if client_height > android_height:
                        offset_y = client_height - android_height
                        log(f"[CLICK] Detected Y offset: {offset_y}px (toolbar)")
                    
                    if client_width != android_width or client_height != android_height:
                        scale_x = android_width / client_width
                        scale_y = android_height / (client_height - offset_y) if (client_height - offset_y) > 0 else 1.0
                    
                    # Transform coordinates
                    android_x = int((client_x - offset_x) * scale_x)
                    android_y = int((client_y - offset_y) * scale_y)
                    
                    # Clamp to valid range
                    android_x = max(0, min(android_x, android_width - 1))
                    android_y = max(0, min(android_y, android_height - 1))
                    
                    log(f"[CLICK] uiautomator2: client({client_x},{client_y}) -> android({android_x},{android_y})")
                    
                    # Connect and click with duration
                    d = u2.connect(adb_serial)
                    hold_duration = hold_ms if hold_ms > 0 else 100
                    
                    if hold_duration > 200:
                        # Long press
                        d.long_click(android_x, android_y, hold_duration / 1000.0)
                    else:
                        # Normal tap
                        d.click(android_x, android_y)
                    
                    tap_success = True
                    log(f"[CLICK] uiautomator2 tap SUCCESS at android({android_x},{android_y}) duration={hold_duration}ms")
                    
                except Exception as e:
                    log(f"[CLICK] uiautomator2 failed: {e}, trying sendevent...")
                    
                    # Method 2: Fallback to sendevent
                    try:
                        touch_device = "/dev/input/event2"
                        max_x, max_y = 549, 399
                        
                        cmd_size = f"adb -s {adb_serial} shell wm size"
                        result_size = subprocess.run(cmd_size, shell=True, capture_output=True, text=True, timeout=2,
                                                    creationflags=CREATE_NO_WINDOW if sys.platform == 'win32' else 0)
                        import re
                        match = re.search(r'(\d+)x(\d+)', result_size.stdout)
                        if match:
                            screen_width, screen_height = int(match.group(1)), int(match.group(2))
                        else:
                            screen_width, screen_height = 400, 550
                        
                        # Get window client size and calculate offset (same as uiautomator2)
                        user32 = ctypes.windll.user32
                        rect = wintypes.RECT()
                        user32.GetClientRect(effective_hwnd, ctypes.byref(rect))
                        client_width = rect.right - rect.left
                        client_height = rect.bottom - rect.top
                        
                        # Calculate Y offset (toolbar)
                        offset_y = max(0, client_height - screen_height)
                        
                        # Apply offset to coordinates BEFORE scaling
                        adjusted_x = client_x
                        adjusted_y = max(0, client_y - offset_y)
                        
                        # Now scale to touch device coordinates
                        abs_x = int((adjusted_x * max_x) / screen_width)
                        abs_y = int((adjusted_y * max_y) / screen_height)
                        abs_x = max(0, min(abs_x, max_x))
                        abs_y = max(0, min(abs_y, max_y))
                        
                        log(f"[CLICK] Sendevent: client({client_x},{client_y}) offset_y={offset_y} -> adjusted({adjusted_x},{adjusted_y}) -> touch({abs_x},{abs_y})")
                        
                        EV_ABS, EV_SYN, EV_KEY = 3, 0, 1
                        ABS_MT_SLOT, ABS_MT_TRACKING_ID = 47, 57
                        ABS_MT_POSITION_X, ABS_MT_POSITION_Y = 53, 54
                        ABS_MT_PRESSURE, BTN_TOUCH = 58, 330
                        SYN_REPORT = 0
                        
                        touch_down = [
                            f"sendevent {touch_device} {EV_ABS} {ABS_MT_SLOT} 0",
                            f"sendevent {touch_device} {EV_ABS} {ABS_MT_TRACKING_ID} 1",
                            f"sendevent {touch_device} {EV_ABS} {ABS_MT_POSITION_X} {abs_x}",
                            f"sendevent {touch_device} {EV_ABS} {ABS_MT_POSITION_Y} {abs_y}",
                            f"sendevent {touch_device} {EV_ABS} {ABS_MT_PRESSURE} 1",
                            f"sendevent {touch_device} {EV_KEY} {BTN_TOUCH} 1",
                            f"sendevent {touch_device} {EV_SYN} {SYN_REPORT} 0"
                        ]
                        
                        touch_up = [
                            f"sendevent {touch_device} {EV_ABS} {ABS_MT_TRACKING_ID} -1",
                            f"sendevent {touch_device} {EV_KEY} {BTN_TOUCH} 0",
                            f"sendevent {touch_device} {EV_SYN} {SYN_REPORT} 0"
                        ]
                        
                        cmd_down = f"adb -s {adb_serial} shell \"{' && '.join(touch_down)}\""
                        result_down = subprocess.run(cmd_down, shell=True, timeout=2, capture_output=True, text=True,
                                                    creationflags=CREATE_NO_WINDOW if sys.platform == 'win32' else 0)
                        
                        if result_down.returncode == 0:
                            hold_duration = hold_ms if hold_ms > 0 else 100
                            time.sleep(hold_duration / 1000.0)
                            
                            cmd_up = f"adb -s {adb_serial} shell \"{' && '.join(touch_up)}\""
                            result_up = subprocess.run(cmd_up, shell=True, timeout=2, capture_output=True, text=True,
                                                      creationflags=CREATE_NO_WINDOW if sys.platform == 'win32' else 0)
                            
                            if result_up.returncode == 0:
                                tap_success = True
                                log(f"[CLICK] Sendevent SUCCESS at ({client_x},{client_y})")
                                
                    except Exception as e2:
                        log(f"[CLICK] Sendevent also failed: {e2}")
                
                # Final fallback to SetCursorPos
                if not tap_success:
                    log(f"[CLICK] All ADB methods failed, fallback to SetCursorPos")
                    input_method = "SetCursorPos"
                    if effective_hwnd:
                        pt = wintypes.POINT(client_x, client_y)
                        ctypes.windll.user32.ClientToScreen(effective_hwnd, ctypes.byref(pt))
                        screen_x, screen_y = pt.x, pt.y
                    else:
                        screen_x, screen_y = client_x, client_y
                    
            if input_method == "PostMessage" and effective_hwnd:
                # METHOD 2: PostMessage - Windows message (no cursor movement, uses client coords)
                lparam = (client_y << 16) | (client_x & 0xFFFF)
                
                WM_LBUTTONDOWN = 0x0201
                WM_LBUTTONUP = 0x0202
                WM_RBUTTONDOWN = 0x0204
                WM_RBUTTONUP = 0x0205
                MK_LBUTTON = 0x0001
                MK_RBUTTON = 0x0002
                
                hold_time = hold_ms / 1000.0 if hold_ms > 0 else 0.02
                log(f"[CLICK] PostMessage to hwnd={effective_hwnd}, client({client_x},{client_y}) [Target: {target_mode}]")
                
                if btn in ("left", "hold_left"):
                    ctypes.windll.user32.PostMessageW(effective_hwnd, WM_LBUTTONDOWN, MK_LBUTTON, lparam)
                    time.sleep(hold_time)
                    ctypes.windll.user32.PostMessageW(effective_hwnd, WM_LBUTTONUP, 0, lparam)
                elif btn in ("right", "hold_right"):
                    ctypes.windll.user32.PostMessageW(effective_hwnd, WM_RBUTTONDOWN, MK_RBUTTON, lparam)
                    time.sleep(hold_time)
                    ctypes.windll.user32.PostMessageW(effective_hwnd, WM_RBUTTONUP, 0, lparam)
                elif btn == "double":
                    ctypes.windll.user32.PostMessageW(effective_hwnd, WM_LBUTTONDOWN, MK_LBUTTON, lparam)
                    time.sleep(0.02)
                    ctypes.windll.user32.PostMessageW(effective_hwnd, WM_LBUTTONUP, 0, lparam)
                    time.sleep(0.05)
                    ctypes.windll.user32.PostMessageW(effective_hwnd, WM_LBUTTONDOWN, MK_LBUTTON, lparam)
                    time.sleep(0.02)
                    ctypes.windll.user32.PostMessageW(effective_hwnd, WM_LBUTTONUP, 0, lparam)
            
            elif input_method == "SetCursorPos":
                # METHOD 3: SetCursorPos + mouse_event (default, compatible)
                # Move cursor to position (skip if using current pos)
                if not use_current_pos:
                    ctypes.windll.user32.SetCursorPos(screen_x, screen_y)
                    time.sleep(0.02)
                
                # Calculate hold time
                hold_time = hold_ms / 1000.0 if hold_ms > 0 else 0.02
                
                # Standard mouse_event
                if btn == "left":
                    ctypes.windll.user32.mouse_event(0x0002, 0, 0, 0, 0)  # LEFTDOWN
                    time.sleep(hold_time)
                    ctypes.windll.user32.mouse_event(0x0004, 0, 0, 0, 0)  # LEFTUP
                elif btn == "right":
                    ctypes.windll.user32.mouse_event(0x0008, 0, 0, 0, 0)  # RIGHTDOWN
                    time.sleep(hold_time)
                    ctypes.windll.user32.mouse_event(0x0010, 0, 0, 0, 0)  # RIGHTUP
                elif btn == "middle":
                    ctypes.windll.user32.mouse_event(0x0020, 0, 0, 0, 0)  # MIDDLEDOWN
                    time.sleep(0.02)
                    ctypes.windll.user32.mouse_event(0x0040, 0, 0, 0, 0)  # MIDDLEUP
                elif btn == "double":
                    ctypes.windll.user32.mouse_event(0x0002, 0, 0, 0, 0)
                    time.sleep(0.02)
                    ctypes.windll.user32.mouse_event(0x0004, 0, 0, 0, 0)
                    time.sleep(0.05)
                    ctypes.windll.user32.mouse_event(0x0002, 0, 0, 0, 0)
                    time.sleep(0.02)
                    ctypes.windll.user32.mouse_event(0x0004, 0, 0, 0, 0)
                elif btn == "hold_left":
                    ctypes.windll.user32.mouse_event(0x0002, 0, 0, 0, 0)
                    time.sleep(hold_time)
                    ctypes.windll.user32.mouse_event(0x0004, 0, 0, 0, 0)
                elif btn == "hold_right":
                    ctypes.windll.user32.mouse_event(0x0008, 0, 0, 0, 0)
                    time.sleep(hold_time)
                    ctypes.windll.user32.mouse_event(0x0010, 0, 0, 0, 0)
            
            # Log final result
            if input_method == "PostMessage":
                log(f"[CLICK] {btn} executed with {input_method} at client({client_x},{client_y}) [target={target_mode}]")
            elif input_method == "SetCursorPos":
                log(f"[CLICK] {btn} executed with SetCursorPos at screen({screen_x},{screen_y}) [target={target_mode}]")
        
        elif action.action == "KEY_PRESS":
            key = v.get("key", "")
            repeat = v.get("repeat", 1)
            
            # Direct keyboard simulation using ctypes
            self._send_key(key, repeat)
        
        elif action.action == "WHEEL":
            direction = v.get("direction", "up")
            amount = v.get("amount", 1)
            speed = v.get("speed", 50)  # ms delay giữa các tick
            x, y = v.get("x", 0), v.get("y", 0)
            use_current_pos = v.get("use_current_pos", False)
            
            # Respect saved target_mode or infer from legacy flags
            if "target_mode" in v:
                target_mode = v["target_mode"]
            elif "screen_coords" in v:
                target_mode = "screen" if v["screen_coords"] else "emulator"
            else:
                target_mode = "emulator"
            effective_hwnd = target_hwnd if target_mode == "emulator" else None
            
            # Get input method from settings
            input_method = self._input_settings.get("click_method", "SetCursorPos")
            
            # Validate input method with target mode
            if input_method in ("PostMessage", "ADB Tap") and target_mode != "emulator":
                log(f"[WHEEL] {input_method} requires Emulator mode, fallback to SetCursorPos")
                input_method = "SetCursorPos"
            
            # Backward compat: nếu có delta cũ thì dùng delta
            if "delta" in v:
                delta = v.get("delta", 120)
            else:
                delta = 120 if direction == "up" else -120
            
            # If use_current_pos is True, get current mouse position
            if use_current_pos:
                cursor_pt = wintypes.POINT()
                ctypes.windll.user32.GetCursorPos(ctypes.byref(cursor_pt))
                screen_x, screen_y = cursor_pt.x, cursor_pt.y
                client_x, client_y = x, y  # Will be set later if needed
                log(f"[WHEEL] Using current mouse position: ({screen_x},{screen_y})")
            # Convert client coords to screen coords if we have target window
            elif effective_hwnd:
                pt = wintypes.POINT(int(x), int(y))
                ctypes.windll.user32.ClientToScreen(effective_hwnd, ctypes.byref(pt))
                screen_x, screen_y = pt.x, pt.y
                client_x, client_y = int(x), int(y)
            else:
                screen_x, screen_y = int(x), int(y)
                client_x, client_y = int(x), int(y)
            
            # Execute scroll based on input method
            if input_method == "ADB Tap" and adb_serial and effective_hwnd:
                # METHOD 1: ADB Swipe for scrolling (no cursor movement)
                import subprocess
                
                # Calculate swipe distance (120 delta ≈ 100 pixels scroll)
                scroll_distance = 100  # pixels per scroll tick
                
                for i in range(amount):
                    if self._playback_stop_event.is_set():
                        break
                    
                    # Calculate swipe coordinates
                    if direction == "up":
                        # Swipe from bottom to top (scroll up)
                        y1 = client_y + scroll_distance // 2
                        y2 = client_y - scroll_distance // 2
                    else:  # down
                        # Swipe from top to bottom (scroll down)
                        y1 = client_y - scroll_distance // 2
                        y2 = client_y + scroll_distance // 2
                    
                    # Use swipe gesture for scroll
                    duration = max(100, speed)  # minimum 100ms for smooth scroll
                    cmd = f"adb -s {adb_serial} shell input swipe {client_x} {y1} {client_x} {y2} {duration}"
                    
                    try:
                        log(f"[WHEEL] ADB executing: {cmd}")
                        result = subprocess.run(cmd, shell=True, timeout=3, capture_output=True, text=True, creationflags=CREATE_NO_WINDOW if sys.platform == 'win32' else 0)
                        log(f"[WHEEL] ADB scroll {direction} executed at ({client_x},{client_y})")
                        if result.stderr:
                            log(f"[WHEEL] ADB stderr: {result.stderr.strip()}")
                    except Exception as e:
                        log(f"[WHEEL] ADB scroll failed: {e}, fallback to SetCursorPos")
                        input_method = "SetCursorPos"  # Fallback
                        break
                    
                    if speed > 0 and i < amount - 1:
                        time.sleep(speed / 1000.0)
                
                if input_method == "ADB Tap":  # If didn't fallback
                    log(f"[WHEEL] ADB {direction} x{amount} at client({client_x},{client_y}) [target={target_mode}]")
            
            if input_method in ("SetCursorPos", "PostMessage"):
                # METHOD 2: SetCursorPos + mouse_event (traditional)
                # Move cursor and scroll (skip move if using current pos)
                if not use_current_pos:
                    ctypes.windll.user32.SetCursorPos(screen_x, screen_y)
                
                for _ in range(amount):
                    if self._playback_stop_event.is_set():
                        break
                    ctypes.windll.user32.mouse_event(0x0800, 0, 0, delta, 0)
                    if speed > 0:
                        time.sleep(speed / 1000.0)
                
                log(f"[WHEEL] {direction} x{amount} at screen({screen_x},{screen_y})" + (f" [hwnd={effective_hwnd}]" if effective_hwnd else "") + (" [current_pos]" if use_current_pos else ""))
        
        elif action.action == "COMBOKEY":
            keys = v.get("keys", [])
            order = v.get("order", "simultaneous")
            
            # Key name mapping to VK codes
            vk_map = {
                'ctrl': 0x11, 'alt': 0x12, 'shift': 0x10, 'win': 0x5B,
                'enter': 0x0D, 'esc': 0x1B, 'tab': 0x09, 'space': 0x20,
                'backspace': 0x08, 'delete': 0x2E, 'insert': 0x2D,
                'home': 0x24, 'end': 0x23, 'pageup': 0x21, 'pagedown': 0x22,
                'left': 0x25, 'up': 0x26, 'right': 0x27, 'down': 0x28,
                'f1': 0x70, 'f2': 0x71, 'f3': 0x72, 'f4': 0x73,
                'f5': 0x74, 'f6': 0x75, 'f7': 0x76, 'f8': 0x77,
                'f9': 0x78, 'f10': 0x79, 'f11': 0x7A, 'f12': 0x7B,
                'capslock': 0x14, 'numlock': 0x90, 'scrolllock': 0x91,
            }
            
            def get_vk(key_name):
                k = key_name.lower()
                if k in vk_map:
                    return vk_map[k]
                if len(k) == 1:
                    return ord(k.upper())
                return 0
            
            vks = [get_vk(k) for k in keys if get_vk(k) != 0]
            
            if order == "simultaneous":
                # Press all keys down, then release all
                for vk in vks:
                    ctypes.windll.user32.keybd_event(vk, 0, 0, 0)  # DOWN
                    time.sleep(0.02)
                time.sleep(0.05)
                for vk in reversed(vks):
                    ctypes.windll.user32.keybd_event(vk, 0, 2, 0)  # UP
                    time.sleep(0.02)
            else:  # sequence
                for vk in vks:
                    ctypes.windll.user32.keybd_event(vk, 0, 0, 0)  # DOWN
                    time.sleep(0.02)
                    ctypes.windll.user32.keybd_event(vk, 0, 2, 0)  # UP
                    time.sleep(0.05)
        
        elif action.action == "RECORDED_BLOCK":
            # Execute nested actions
            nested_actions = [Action.from_dict(a) for a in v.get("actions", [])]
            for nested in nested_actions:
                if self._playback_stop_event.is_set():
                    break
                self._execute_action(nested, target_hwnd, adb_serial=adb_serial)
        
        elif action.action == "GROUP":
            # Execute grouped actions
            log(f"[Playback] GROUP raw value: {v}")
            actions_list = v.get("actions", [])
            log(f"[Playback] GROUP actions_list type={type(actions_list)}, len={len(actions_list) if actions_list else 0}")
            if actions_list:
                nested_actions = [Action.from_dict(a) for a in actions_list]
                log(f"[Playback] Executing GROUP '{v.get('name', '')}' with {len(nested_actions)} actions")
                for i, nested in enumerate(nested_actions):
                    if self._playback_stop_event.is_set():
                        break
                    log(f"[Playback] GROUP action {i+1}/{len(nested_actions)}: {nested.action}")
                    self._execute_action(nested, target_hwnd, adb_serial=adb_serial)
            else:
                log(f"[Playback] GROUP '{v.get('name', '')}' has NO nested actions - skipping")
        
        elif action.action == "EMBED_MACRO":
            # Load and execute macro file(s) inline
            # Support both single macro_name and multi-select macro_names list
            macro_names = v.get("macro_names", [])
            if not macro_names:
                single = v.get("macro_name", "")
                if single:
                    macro_names = [single]
            
            continue_on_error = v.get("continue_on_error", True)
            inherit_variables = v.get("inherit_variables", True)
            
            if not macro_names:
                log(f"[EMBED_MACRO] ERROR: No macro(s) specified")
                return
            
            import base64
            import tempfile
            
            log(f"[EMBED_MACRO] Will execute {len(macro_names)} macro(s) in order")
            
            for macro_idx, macro_name in enumerate(macro_names, 1):
                if self._playback_stop_event.is_set():
                    break
                
                log(f"[EMBED_MACRO] === Macro {macro_idx}/{len(macro_names)}: {macro_name} ===")
                
                # Find the macro file
                macro_path = None
                if os.path.isabs(macro_name) and os.path.exists(macro_name):
                    macro_path = macro_name
                else:
                    for ext in ['.macro', '.json', '']:
                        test_path = os.path.join(MACROS_DIR, macro_name + ext)
                        if os.path.exists(test_path):
                            macro_path = test_path
                            break
                        test_path = os.path.join(MACROS_DIR, macro_name)
                        if os.path.exists(test_path):
                            macro_path = test_path
                            break
                
                if not macro_path or not os.path.exists(macro_path):
                    log(f"[EMBED_MACRO] ERROR: Macro not found: {macro_name}")
                    if not continue_on_error:
                        raise Exception(f"Macro not found: {macro_name}")
                    continue
                
                try:
                    with open(macro_path, "r", encoding="utf-8") as f:
                        macro_data = json.load(f)
                    
                    images = macro_data.get("images", {})
                    actions_data = macro_data.get("actions", [])
                    
                    # Extract images to temp if needed
                    if images:
                        temp_dir = os.path.join(tempfile.gettempdir(), "macro_images", 
                                               os.path.splitext(os.path.basename(macro_path))[0])
                        os.makedirs(temp_dir, exist_ok=True)
                        
                        for img_key, img_b64 in images.items():
                            try:
                                img_data = base64.b64decode(img_b64)
                                img_path = os.path.join(temp_dir, img_key)
                                with open(img_path, "wb") as img_f:
                                    img_f.write(img_data)
                            except Exception as e:
                                log(f"[EMBED_MACRO] Failed to extract image {img_key}: {e}")
                        
                        for action_data in actions_data:
                            if action_data.get("action") == "FIND_IMAGE":
                                template_path = action_data.get("value", {}).get("template_path", "")
                                if template_path.startswith("@embedded:"):
                                    img_key = template_path.replace("@embedded:", "")
                                    action_data["value"]["template_path"] = os.path.join(temp_dir, img_key)
                    
                    embedded_actions = [Action.from_dict(a) for a in actions_data]
                    log(f"[EMBED_MACRO] Executing {len(embedded_actions)} actions")
                    
                    for i, embedded_action in enumerate(embedded_actions):
                        if self._playback_stop_event.is_set():
                            break
                        try:
                            self._execute_action(embedded_action, target_hwnd, adb_serial=adb_serial)
                        except Exception as e:
                            log(f"[EMBED_MACRO] Action {i+1} failed: {e}")
                            if not continue_on_error:
                                raise
                    
                    log(f"[EMBED_MACRO] Completed macro: {macro_name}")
                    
                except Exception as e:
                    log(f"[EMBED_MACRO] ERROR in macro '{macro_name}': {e}")
                    if not continue_on_error:
                        raise
        
        # V2 Wait Actions
        elif action.action == "WAIT_TIME":
            from core.wait_actions import WaitTime
            wait = WaitTime(
                delay_ms=v.get("delay_ms", 1000),
                variance_ms=v.get("variance_ms", 0)
            )
            wait.wait(self._playback_stop_event)
        
        elif action.action == "WAIT_PIXEL_COLOR":
            from core.wait_actions import WaitPixelColor
            rgb = v.get("expected_rgb", (0, 0, 0))
            wait = WaitPixelColor(
                x=v.get("x", 0),
                y=v.get("y", 0),
                expected_rgb=rgb if isinstance(rgb, tuple) else tuple(rgb),
                tolerance=v.get("tolerance", 0),
                timeout_ms=v.get("timeout_ms", 30000),
                target_hwnd=target_hwnd or 0
            )
            wait.wait(self._playback_stop_event)
        
        elif action.action == "WAIT_SCREEN_CHANGE":
            from core.wait_actions import WaitScreenChange
            import time as time_module
            
            region = v.get("region", (0, 0, 100, 100))
            timeout_seconds = v.get("timeout_seconds", v.get("timeout_ms", 30000) // 1000)
            
            # Coords from ADB capture are already Android-native, use directly
            android_region = region
            log(f"[WAIT_SCREEN_CHANGE] Using Android coords: {android_region}")
            
            log(f"[WAIT_SCREEN_CHANGE] Starting, timeout={timeout_seconds}s, region={android_region}")
            
            wait = WaitScreenChange(
                region=tuple(android_region) if isinstance(android_region, list) else android_region,
                threshold=v.get("threshold", 0.05),
                timeout_ms=timeout_seconds * 1000,
                target_hwnd=target_hwnd or 0,
                adb_serial=adb_serial
            )
            
            # Wait for screen change - returns WaitResult object
            result = wait.wait(self._playback_stop_event)
            change_found = result.success if result else False
            
            # Initialize vars storage
            if not hasattr(self, '_action_vars'):
                self._action_vars = {}
            
            if change_found:
                log(f"[WAIT_SCREEN_CHANGE] Change detected in region {region}")
                
                # Calculate center of monitored region for positioning
                x1, y1, x2, y2 = region
                center_x = (x1 + x2) // 2
                center_y = (y1 + y2) // 2
                
                # Save coordinates if enabled
                if v.get("save_xy_enabled", False):
                    x_var = v.get("save_x_var", "$changeX")
                    y_var = v.get("save_y_var", "$changeY")
                    if x_var:
                        self._action_vars[x_var.strip("$")] = center_x
                    if y_var:
                        self._action_vars[y_var.strip("$")] = center_y
                
                # Perform mouse action if enabled
                if v.get("mouse_action_enabled", False):
                    mouse_type = v.get("mouse_type", "Positioning")
                    
                    # Use screen coordinates directly
                    screen_x, screen_y = center_x, center_y
                    
                    # Move cursor
                    ctypes.windll.user32.SetCursorPos(screen_x, screen_y)
                    time_module.sleep(0.05)
                    
                    if mouse_type != "Positioning":
                        if mouse_type == "Left click":
                            ctypes.windll.user32.mouse_event(0x0002, 0, 0, 0, 0)
                            time_module.sleep(0.02)
                            ctypes.windll.user32.mouse_event(0x0004, 0, 0, 0, 0)
                        elif mouse_type == "Right click":
                            ctypes.windll.user32.mouse_event(0x0008, 0, 0, 0, 0)
                            time_module.sleep(0.02)
                            ctypes.windll.user32.mouse_event(0x0010, 0, 0, 0, 0)
                        elif mouse_type == "Double click":
                            for _ in range(2):
                                ctypes.windll.user32.mouse_event(0x0002, 0, 0, 0, 0)
                                time_module.sleep(0.02)
                                ctypes.windll.user32.mouse_event(0x0004, 0, 0, 0, 0)
                                time_module.sleep(0.05)
                        elif mouse_type == "Middle click":
                            ctypes.windll.user32.mouse_event(0x0020, 0, 0, 0, 0)
                            time_module.sleep(0.02)
                            ctypes.windll.user32.mouse_event(0x0040, 0, 0, 0, 0)
                    
                    log(f"[WAIT_SCREEN_CHANGE] {mouse_type} at ({screen_x}, {screen_y})")
                
                # Handle goto if found
                goto_target = v.get("goto_if_found", "Next")
                if goto_target and goto_target.startswith("→ "):
                    goto_target = goto_target[2:]
                self._handle_goto(goto_target)
            else:
                log(f"[WAIT_SCREEN_CHANGE] No change after {timeout_seconds}s")
                
                # Handle goto if not found
                goto_target = v.get("goto_if_not_found", "End")
                if goto_target and goto_target.startswith("→ "):
                    goto_target = goto_target[2:]
                self._handle_goto(goto_target)
        
        elif action.action == "WAIT_COLOR_DISAPPEAR":
            from core.wait_actions import WaitColorDisappear
            
            region = v.get("region", (0, 0, 100, 100))
            auto_detect = v.get("auto_detect", False)
            tolerance = v.get("tolerance", 30)
            disappear_threshold = v.get("disappear_threshold", 0.01)
            timeout_ms = v.get("timeout_ms", 30000)
            stable_count_exit = v.get("stable_count_exit", 3)
            sample_count = v.get("sample_count", 5)
            
            # Coords from ADB capture are already Android-native, use directly
            android_region = region
            log(f"[WAIT_COLOR_DISAPPEAR] Using Android coords: {android_region}")
            
            # Only use target_rgb if not auto-detect mode
            if auto_detect:
                wait = WaitColorDisappear(
                    region=tuple(android_region) if isinstance(android_region, list) else android_region,
                    tolerance=tolerance,
                    disappear_threshold=disappear_threshold,
                    timeout_ms=timeout_ms,
                    target_hwnd=target_hwnd or 0,
                    auto_detect=True,
                    auto_detect_count=v.get("auto_detect_count", 3),
                    stable_count_exit=stable_count_exit,
                    sample_count=sample_count,
                    adb_serial=adb_serial
                )
            else:
                target_rgb = v.get("target_rgb", (255, 255, 255))
                wait = WaitColorDisappear(
                    region=tuple(android_region) if isinstance(android_region, list) else android_region,
                    target_rgb=tuple(target_rgb) if isinstance(target_rgb, list) else target_rgb,
                    tolerance=tolerance,
                    disappear_threshold=disappear_threshold,
                    timeout_ms=timeout_ms,
                    target_hwnd=target_hwnd or 0,
                    auto_detect=False,
                    stable_count_exit=stable_count_exit,
                    sample_count=sample_count,
                    adb_serial=adb_serial
                )
            
            result = wait.wait(self._playback_stop_event)
            color_disappeared = result.success if result else False
            
            if color_disappeared:
                goto_target = v.get("goto_if_found", "Next")
                if goto_target and goto_target.startswith("→ "):
                    goto_target = goto_target[2:]
                self._handle_goto(goto_target)
            else:
                goto_target = v.get("goto_if_not_found", "End")
                if goto_target and goto_target.startswith("→ "):
                    goto_target = goto_target[2:]
                self._handle_goto(goto_target)
        
        elif action.action == "WAIT_COMBOKEY":
            from core.wait_actions import WaitHotkey
            wait = WaitHotkey(
                key_combo=v.get("key_combo", "F5"),
                timeout_ms=v.get("timeout_ms", 0)
            )
            wait.wait(self._playback_stop_event)
        
        elif action.action == "WAIT_FILE":
            from core.wait_actions import WaitFile
            wait = WaitFile(
                path=v.get("path", ""),
                condition=v.get("condition", "exists"),
                timeout_ms=v.get("timeout_ms", 30000)
            )
            wait.wait(self._playback_stop_event)
        
        # V2 Image Actions
        elif action.action == "FIND_IMAGE":
            if IMAGE_ACTIONS_AVAILABLE:
                from core.image_actions import FindImage
                import time as time_module
                import ctypes.wintypes
                
                template_path = v.get("template_path", "")
                threshold = v.get("threshold", 0.8)
                retry_seconds = v.get("retry_seconds", 30)
                
                # Check if template exists
                if not template_path:
                    log(f"[FIND_IMAGE] ERROR: No template path specified")
                    return
                    
                if not os.path.exists(template_path):
                    log(f"[FIND_IMAGE] ERROR: Template not found: {template_path}")
                    # Try to handle goto_if_not_found
                    goto_target = v.get("goto_if_not_found", "End")
                    if goto_target and goto_target.startswith("→ "):
                        goto_target = goto_target[2:]
                    self._handle_goto(goto_target)
                    return
                
                # crop_region is just metadata (where template was cropped from)
                # We search the FULL window/screen, not limited to crop_region
                # This is more reliable - template can appear anywhere
                search_region = None
                
                if target_hwnd:
                    log(f"[FIND_IMAGE] Searching FULL emulator window")
                else:
                    log(f"[FIND_IMAGE] Searching FULL screen")
                
                log(f"[FIND_IMAGE] Starting search, template={template_path}, retry_seconds={retry_seconds}, threshold={threshold}")
                
                # Initialize vars storage
                if not hasattr(self, '_action_vars'):
                    self._action_vars = {}
                
                # Search loop with retry
                found = False
                match = None
                start_time = time_module.time()
                attempt = 0
                
                while not found and (time_module.time() - start_time) < retry_seconds:
                    if self._playback_stop_event and self._playback_stop_event.is_set():
                        break
                    
                    attempt += 1
                    elapsed = time_module.time() - start_time
                    
                    finder = FindImage(
                        template_path=template_path,
                        region=search_region,  # Use crop_region for search area
                        threshold=threshold,
                        timeout_ms=1000,  # Single scan timeout
                        target_hwnd=target_hwnd or 0
                    )
                    match = finder.find(self._playback_stop_event)
                    found = match.found if match else False
                    
                    if not found:
                        log(f"[FIND_IMAGE] Attempt {attempt}: not found ({elapsed:.1f}s / {retry_seconds}s)")
                        time_module.sleep(0.5)  # Wait before retry
                
                # Store result
                self._action_vars["last_image_x"] = match.center_x if match and match.found else 0
                self._action_vars["last_image_y"] = match.center_y if match and match.found else 0
                self._action_vars["last_image_found"] = found
                
                # Process result
                if found and match:
                    log(f"[FIND_IMAGE] Found at ({match.center_x}, {match.center_y}) confidence={match.confidence:.2f}")
                    
                    # Motion guard: Wait for motion to stop before clicking
                    if v.get("motion_guard_enabled", False):
                        motion_region = v.get("motion_region")
                        if motion_region and len(motion_region) == 4:
                            log(f"[FIND_IMAGE] Motion guard active - checking region {motion_region}")
                            
                            from core.wait_actions import WaitColorDisappear
                            
                            motion_threshold = v.get("motion_threshold", 1.0)  # Variance %
                            stable_count = v.get("motion_stable_count", 5)
                            timeout_ms = v.get("motion_timeout_ms", 10000)  # 10s default
                            
                            # Use WaitColorDisappear with auto-detect to track animated colors
                            motion_waiter = WaitColorDisappear(
                                region=tuple(motion_region),
                                tolerance=10,
                                disappear_threshold=motion_threshold,
                                timeout_ms=timeout_ms,
                                target_hwnd=target_hwnd or 0,
                                auto_detect=True,
                                auto_detect_count=3,
                                stable_count_exit=stable_count,
                                adb_serial=adb_serial
                            )
                            
                            motion_result = motion_waiter.wait(self._playback_stop_event)
                            if motion_result:
                                log(f"[FIND_IMAGE] Motion stopped - proceeding with click")
                            else:
                                log(f"[FIND_IMAGE] Motion guard timeout - skipping click")
                                # Handle goto for motion timeout
                                goto_timeout = v.get("goto_motion_timeout", "Next")
                                if goto_timeout and goto_timeout.startswith("→ "):
                                    goto_timeout = goto_timeout[2:]
                                self._handle_goto(goto_timeout)
                                return  # Exit without clicking
                    
                    # Calculate click position based on setting
                    click_pos = v.get("click_position", "Centered")
                    click_x, click_y = match.center_x, match.center_y
                    
                    if click_pos == "Top left":
                        click_x, click_y = match.x, match.y
                    elif click_pos == "Top right":
                        click_x, click_y = match.x + match.width, match.y
                    elif click_pos == "Bottom left":
                        click_x, click_y = match.x, match.y + match.height
                    elif click_pos == "Bottom right":
                        click_x, click_y = match.x + match.width, match.y + match.height
                    elif click_pos == "Random":
                        import random
                        click_x = match.x + random.randint(0, match.width)
                        click_y = match.y + random.randint(0, match.height)
                    
                    # Save coordinates if enabled
                    if v.get("save_xy_enabled", False):
                        x_var = v.get("save_x_var", "$foundX")
                        y_var = v.get("save_y_var", "$foundY")
                        self._action_vars[x_var.strip("$")] = click_x
                        self._action_vars[y_var.strip("$")] = click_y
                    
                    # Perform mouse action if enabled
                    if v.get("mouse_action_enabled", True):
                        mouse_type = v.get("mouse_type", "Left click")
                        
                        # When target_hwnd is set, use worker InputManager to click
                        if target_hwnd:
                            # FindImage returns coordinates in CLIENT coords (screenshot pixels)
                            # These are the actual pixel positions in the window
                            # NO SCALING needed - InputManager converts client -> screen coords
                            # Emulator will handle client -> resolution conversion internally
                            client_click_x, client_click_y = click_x, click_y
                            
                            # Get worker to use InputManager
                            worker = self._get_worker_for_hwnd(target_hwnd)
                            
                            log(f"[FIND_IMAGE] Click at client coords ({client_click_x}, {client_click_y})")
                            
                            # Use worker's InputManager for reliable click (uses SendInput internally)
                            if worker and hasattr(worker, '_input_manager'):
                                from core.input import ButtonType
                                
                                # Delay before click
                                time_module.sleep(0.3)
                                
                                if mouse_type != "Positioning":
                                    button_type = ButtonType.LEFT
                                    if mouse_type == "Right click":
                                        button_type = ButtonType.RIGHT
                                    elif mouse_type == "Middle click":
                                        button_type = ButtonType.MIDDLE
                                    elif mouse_type == "Double click":
                                        button_type = ButtonType.DOUBLE
                                    
                                    # Get input method from settings
                                    input_method = self._input_settings.get("find_image_click_method", "SetCursorPos")
                                    
                                    if input_method == "ADB Tap" and adb_serial and target_hwnd:
                                        # ADB Tap: Try multiple methods to bypass anti-cheat
                                        # 1. uiautomator2 (uses accessibility framework)
                                        # 2. Sendevent (raw hardware events)
                                        # 3. SetCursorPos fallback
                                        tap_success = False
                                        import subprocess
                                        
                                        # Method 1: Try uiautomator2 first (most reliable, uses accessibility)
                                        try:
                                            import uiautomator2 as u2
                                            import ctypes
                                            from ctypes import wintypes
                                            
                                            # Get window client area size
                                            user32 = ctypes.windll.user32
                                            rect = wintypes.RECT()
                                            user32.GetClientRect(target_hwnd, ctypes.byref(rect))
                                            client_width = rect.right - rect.left
                                            client_height = rect.bottom - rect.top
                                            
                                            # Get Android display size
                                            cmd_size = f"adb -s {adb_serial} shell wm size"
                                            size_result = subprocess.run(cmd_size, shell=True, capture_output=True, text=True, timeout=2,
                                                                        creationflags=0x08000000 if sys.platform == 'win32' else 0)
                                            import re
                                            match = re.search(r'(\d+)x(\d+)', size_result.stdout)
                                            if match:
                                                android_width, android_height = int(match.group(1)), int(match.group(2))
                                            else:
                                                android_width, android_height = 400, 550
                                            
                                            log(f"[FIND_IMAGE] Window client: {client_width}x{client_height}, Android: {android_width}x{android_height}")
                                            
                                            # Calculate offset and scale
                                            # If client area is larger than Android display, there's a toolbar/border
                                            # Offset is typically at the top (Y offset)
                                            offset_x = 0
                                            offset_y = 0
                                            scale_x = 1.0
                                            scale_y = 1.0
                                            
                                            if client_height > android_height:
                                                # Toolbar at top - calculate offset
                                                offset_y = client_height - android_height
                                                log(f"[FIND_IMAGE] Detected Y offset: {offset_y}px (toolbar)")
                                            
                                            if client_width != android_width or client_height != android_height:
                                                # Need to scale coordinates
                                                scale_x = android_width / client_width
                                                scale_y = android_height / (client_height - offset_y) if (client_height - offset_y) > 0 else 1.0
                                            
                                            # Transform coordinates
                                            android_x = int((client_click_x - offset_x) * scale_x)
                                            android_y = int((client_click_y - offset_y) * scale_y)
                                            
                                            # Clamp to valid range
                                            android_x = max(0, min(android_x, android_width - 1))
                                            android_y = max(0, min(android_y, android_height - 1))
                                            
                                            log(f"[FIND_IMAGE] uiautomator2: client({client_click_x},{client_click_y}) -> android({android_x},{android_y})")
                                            
                                            # Get hold duration from action value (default 100ms)
                                            hold_duration = v.get("adb_tap_hold_ms", 100)
                                            
                                            # Connect and click with duration
                                            d = u2.connect(adb_serial)
                                            
                                            if hold_duration > 200:
                                                # Long press for >200ms
                                                log(f"[FIND_IMAGE] uiautomator2 LONG PRESS {hold_duration}ms at android({android_x},{android_y})")
                                                d.long_click(android_x, android_y, hold_duration / 1000.0)
                                            else:
                                                # Normal click
                                                log(f"[FIND_IMAGE] uiautomator2 TAP {hold_duration}ms at android({android_x},{android_y})")
                                                d.click(android_x, android_y)
                                            
                                            tap_success = True
                                            log(f"[FIND_IMAGE] uiautomator2 tap SUCCESS")
                                            
                                        except Exception as e:
                                            log(f"[FIND_IMAGE] uiautomator2 failed: {e}, trying sendevent...")
                                            
                                            # Method 2: Fallback to sendevent
                                            try:
                                                # Get screen dimensions from wm size
                                                cmd_size = f"adb -s {adb_serial} shell wm size"
                                                result_size = subprocess.run(cmd_size, shell=True, capture_output=True, text=True, timeout=2,
                                                                            creationflags=0x08000000 if sys.platform == 'win32' else 0)
                                                
                                                import re
                                                match = re.search(r'(\d+)x(\d+)', result_size.stdout)
                                                if match:
                                                    screen_width, screen_height = int(match.group(1)), int(match.group(2))
                                                else:
                                                    screen_width, screen_height = 400, 550
                                                
                                                # Use hardcoded touch device and max values for LDPlayer
                                                touch_device = "/dev/input/event2"
                                                max_x, max_y = 549, 399
                                                
                                                # Get window client size and calculate offset (same as uiautomator2)
                                                user32 = ctypes.windll.user32
                                                rect = wintypes.RECT()
                                                user32.GetClientRect(target_hwnd, ctypes.byref(rect))
                                                client_width = rect.right - rect.left
                                                client_height = rect.bottom - rect.top
                                                
                                                # Calculate Y offset (toolbar)
                                                offset_y = max(0, client_height - screen_height)
                                                
                                                # Apply offset to coordinates BEFORE scaling
                                                adjusted_x = client_click_x
                                                adjusted_y = max(0, client_click_y - offset_y)
                                                
                                                # Now scale to touch device coordinates
                                                abs_x = int((adjusted_x * max_x) / screen_width)
                                                abs_y = int((adjusted_y * max_y) / screen_height)
                                                abs_x = max(0, min(abs_x, max_x))
                                                abs_y = max(0, min(abs_y, max_y))
                                                
                                                log(f"[FIND_IMAGE] Sendevent: client({client_click_x},{client_click_y}) offset_y={offset_y} -> adjusted({adjusted_x},{adjusted_y}) -> touch({abs_x},{abs_y})")
                                                
                                                # Sendevent commands
                                                EV_ABS, EV_SYN, EV_KEY = 3, 0, 1
                                                ABS_MT_SLOT, ABS_MT_TRACKING_ID = 47, 57
                                                ABS_MT_POSITION_X, ABS_MT_POSITION_Y = 53, 54
                                                ABS_MT_PRESSURE, BTN_TOUCH = 58, 330
                                                SYN_REPORT = 0
                                                
                                                touch_down = [
                                                    f"sendevent {touch_device} {EV_ABS} {ABS_MT_SLOT} 0",
                                                    f"sendevent {touch_device} {EV_ABS} {ABS_MT_TRACKING_ID} 1",
                                                    f"sendevent {touch_device} {EV_ABS} {ABS_MT_POSITION_X} {abs_x}",
                                                    f"sendevent {touch_device} {EV_ABS} {ABS_MT_POSITION_Y} {abs_y}",
                                                    f"sendevent {touch_device} {EV_ABS} {ABS_MT_PRESSURE} 1",
                                                    f"sendevent {touch_device} {EV_KEY} {BTN_TOUCH} 1",
                                                    f"sendevent {touch_device} {EV_SYN} {SYN_REPORT} 0"
                                                ]
                                                
                                                touch_up = [
                                                    f"sendevent {touch_device} {EV_ABS} {ABS_MT_TRACKING_ID} -1",
                                                    f"sendevent {touch_device} {EV_KEY} {BTN_TOUCH} 0",
                                                    f"sendevent {touch_device} {EV_SYN} {SYN_REPORT} 0"
                                                ]
                                                
                                                cmd_down = f"adb -s {adb_serial} shell \"{' && '.join(touch_down)}\""
                                                result_down = subprocess.run(cmd_down, shell=True, timeout=2, capture_output=True, text=True,
                                                                            creationflags=0x08000000 if sys.platform == 'win32' else 0)
                                                
                                                if result_down.returncode == 0:
                                                    import time as time_module
                                                    time_module.sleep(0.1)
                                                    
                                                    cmd_up = f"adb -s {adb_serial} shell \"{' && '.join(touch_up)}\""
                                                    result_up = subprocess.run(cmd_up, shell=True, timeout=2, capture_output=True, text=True,
                                                                              creationflags=0x08000000 if sys.platform == 'win32' else 0)
                                                    
                                                    if result_up.returncode == 0:
                                                        tap_success = True
                                                        log(f"[FIND_IMAGE] Sendevent SUCCESS at ({client_click_x},{client_click_y})")
                                                        
                                            except Exception as e2:
                                                log(f"[FIND_IMAGE] Sendevent also failed: {e2}")
                                        
                                        # Final fallback to SetCursorPos
                                        if not tap_success:
                                            log(f"[FIND_IMAGE] All ADB methods failed, using SetCursorPos fallback")
                                            if worker and hasattr(worker, '_input_manager'):
                                                success = worker._input_manager.click(
                                                    client_x=client_click_x,
                                                    client_y=client_click_y,
                                                    button=button_type,
                                                    humanize_delay_min=50,
                                                    humanize_delay_max=150
                                                )
                                    
                                    elif input_method == "PostMessage" and target_hwnd:
                                        # PostMessage: No cursor movement
                                        log(f"[FIND_IMAGE] Using PostMessage at ({client_click_x}, {client_click_y})")
                                        from ctypes import windll
                                        WM_LBUTTONDOWN = 0x0201
                                        WM_LBUTTONUP = 0x0202
                                        WM_RBUTTONDOWN = 0x0204
                                        WM_RBUTTONUP = 0x0205
                                        MK_LBUTTON = 0x0001
                                        
                                        lparam = (client_click_y << 16) | (client_click_x & 0xFFFF)
                                        
                                        if mouse_type == "Right click":
                                            windll.user32.PostMessageW(target_hwnd, WM_RBUTTONDOWN, 0, lparam)
                                            time_module.sleep(0.05)
                                            windll.user32.PostMessageW(target_hwnd, WM_RBUTTONUP, 0, lparam)
                                        else:  # Left, Double, Middle (fallback to left)
                                            windll.user32.PostMessageW(target_hwnd, WM_LBUTTONDOWN, MK_LBUTTON, lparam)
                                            time_module.sleep(0.05)
                                            windll.user32.PostMessageW(target_hwnd, WM_LBUTTONUP, 0, lparam)
                                            
                                            if mouse_type == "Double click":
                                                time_module.sleep(0.05)
                                                windll.user32.PostMessageW(target_hwnd, WM_LBUTTONDOWN, MK_LBUTTON, lparam)
                                                time_module.sleep(0.05)
                                                windll.user32.PostMessageW(target_hwnd, WM_LBUTTONUP, 0, lparam)
                                    
                                    else:
                                        # SetCursorPos (default): Use InputManager
                                        # Click using InputManager with CLIENT coords
                                        # InputManager will convert to screen coords automatically
                                        success = worker._input_manager.click(
                                            client_x=client_click_x,
                                            client_y=client_click_y,
                                            button=button_type,
                                            humanize_delay_min=50,
                                            humanize_delay_max=150,
                                            wheel_delta=0
                                        )
                                        
                                        if success:
                                            log(f"[FIND_IMAGE] {mouse_type} at client ({client_click_x}, {client_click_y}) via InputManager")
                                        else:
                                            log(f"[FIND_IMAGE] Failed to click at ({client_click_x}, {client_click_y})")
                                
                                # Save last position for next actions
                                pt = ctypes.wintypes.POINT(int(client_click_x), int(client_click_y))
                                ctypes.windll.user32.ClientToScreen(target_hwnd, ctypes.byref(pt))
                                self._action_vars["last_screen_x"] = pt.x
                                self._action_vars["last_screen_y"] = pt.y
                            else:
                                log(f"[FIND_IMAGE] Worker or InputManager not available for hwnd={target_hwnd}")
                        else:
                            # Full screen mode - use SetCursorPos + mouse_event
                            screen_x, screen_y = int(click_x), int(click_y)
                            
                            # Move cursor
                            ctypes.windll.user32.SetCursorPos(screen_x, screen_y)
                            time_module.sleep(1.0)  # Tăng từ 0.05s lên 1.0s để đảm bảo cursor đã di chuyển
                            
                            # Save screen position for next action with use_current_pos
                            self._action_vars["last_screen_x"] = screen_x
                            self._action_vars["last_screen_y"] = screen_y
                            
                            if mouse_type != "Positioning":
                                if mouse_type == "Left click":
                                    ctypes.windll.user32.mouse_event(0x0002, 0, 0, 0, 0)  # LEFTDOWN
                                    time_module.sleep(0.1)  # Tăng từ 0.02s lên 0.1s
                                    ctypes.windll.user32.mouse_event(0x0004, 0, 0, 0, 0)  # LEFTUP
                                elif mouse_type == "Right click":
                                    ctypes.windll.user32.mouse_event(0x0008, 0, 0, 0, 0)  # RIGHTDOWN
                                    time_module.sleep(0.1)  # Tăng từ 0.02s lên 0.1s
                                    ctypes.windll.user32.mouse_event(0x0010, 0, 0, 0, 0)  # RIGHTUP
                                elif mouse_type == "Double click":
                                    for _ in range(2):
                                        ctypes.windll.user32.mouse_event(0x0002, 0, 0, 0, 0)
                                        time_module.sleep(0.1)  # Tăng từ 0.02s lên 0.1s
                                        ctypes.windll.user32.mouse_event(0x0004, 0, 0, 0, 0)
                                        time_module.sleep(0.1)  # Tăng từ 0.05s lên 0.1s
                                elif mouse_type == "Middle click":
                                    ctypes.windll.user32.mouse_event(0x0020, 0, 0, 0, 0)  # MIDDLEDOWN
                                    time_module.sleep(0.1)  # Tăng từ 0.02s lên 0.1s
                                    ctypes.windll.user32.mouse_event(0x0040, 0, 0, 0, 0)  # MIDDLEUP
                            
                            log(f"[FIND_IMAGE] {mouse_type} at screen ({screen_x}, {screen_y})")
                    
                    # Handle goto if found
                    goto_target = v.get("goto_found_label", "").strip()
                    if not goto_target:
                        goto_target = v.get("goto_if_found", "Next")
                    
                    if goto_target and goto_target.startswith("→ "):
                        goto_target = goto_target[2:]  # Remove prefix
                    
                    self._handle_goto(goto_target)
                    
                else:
                    log(f"[FIND_IMAGE] Not found after {retry_seconds}s")
                    
                    # Handle goto if not found
                    goto_target = v.get("goto_notfound_label", "").strip()
                    if not goto_target:
                        goto_target = v.get("goto_if_not_found", "Next")
                    
                    if goto_target and goto_target.startswith("→ "):
                        goto_target = goto_target[2:]
                    
                    self._handle_goto(goto_target)
        
        elif action.action == "CAPTURE_IMAGE":
            if IMAGE_ACTIONS_AVAILABLE:
                from core.image_actions import CaptureImage
                region = v.get("region")
                if region and isinstance(region, list):
                    region = tuple(region)
                capturer = CaptureImage(
                    region=region,
                    save_path=v.get("save_path", ""),
                    format=v.get("format", "png"),
                    target_hwnd=target_hwnd or 0
                )
                capturer.capture()
        
        # V2 Flow Control - basic handling (advanced via ActionEngine)
        elif action.action in ("LABEL", "COMMENT"):
            pass  # No-op, just markers
        
        elif action.action == "DRAG":
            x1, y1 = v.get("x1", 0), v.get("y1", 0)
            x2, y2 = v.get("x2", 0), v.get("y2", 0)
            button = v.get("button", "left")
            duration_ms = v.get("duration_ms", 500)
            use_current_start = v.get("use_current_start", False)
            
            # Respect saved target_mode or infer from legacy flags
            if "target_mode" in v:
                target_mode = v["target_mode"]
            elif "screen_coords" in v:
                target_mode = "screen" if v["screen_coords"] else "emulator"
            else:
                target_mode = "emulator"
            effective_hwnd = target_hwnd if target_mode == "emulator" else None
            
            # If use_current_start, get current mouse position as start
            if use_current_start:
                cursor_pt = wintypes.POINT()
                ctypes.windll.user32.GetCursorPos(ctypes.byref(cursor_pt))
                screen_x1, screen_y1 = cursor_pt.x, cursor_pt.y
                log(f"[DRAG] Using current mouse position as start: ({screen_x1},{screen_y1})")
                
                # End position still needs conversion if emulator mode
                if effective_hwnd:
                    pt2 = wintypes.POINT(int(x2), int(y2))
                    ctypes.windll.user32.ClientToScreen(effective_hwnd, ctypes.byref(pt2))
                    screen_x2, screen_y2 = pt2.x, pt2.y
                else:
                    screen_x2, screen_y2 = int(x2), int(y2)
            # Convert client coords to screen coords if we have target window
            elif effective_hwnd:
                pt1 = wintypes.POINT(int(x1), int(y1))
                pt2 = wintypes.POINT(int(x2), int(y2))
                ctypes.windll.user32.ClientToScreen(effective_hwnd, ctypes.byref(pt1))
                ctypes.windll.user32.ClientToScreen(effective_hwnd, ctypes.byref(pt2))
                screen_x1, screen_y1 = pt1.x, pt1.y
                screen_x2, screen_y2 = pt2.x, pt2.y
            else:
                screen_x1, screen_y1 = int(x1), int(y1)
                screen_x2, screen_y2 = int(x2), int(y2)
            
            # Mouse button flags
            if button == "right":
                down_flag, up_flag = 0x0008, 0x0010
            else:
                down_flag, up_flag = 0x0002, 0x0004
            
            # Move to start and press (skip if using current start)
            if not use_current_start:
                ctypes.windll.user32.SetCursorPos(screen_x1, screen_y1)
                time.sleep(0.02)
            ctypes.windll.user32.mouse_event(down_flag, 0, 0, 0, 0)
            time.sleep(0.02)
            
            # Smooth interpolation
            steps = max(10, duration_ms // 20)
            step_delay = duration_ms / steps / 1000.0
            
            for i in range(1, steps + 1):
                t = i / steps
                curr_x = int(screen_x1 + t * (screen_x2 - screen_x1))
                curr_y = int(screen_y1 + t * (screen_y2 - screen_y1))
                ctypes.windll.user32.SetCursorPos(curr_x, curr_y)
                time.sleep(step_delay)
            
            # Release at end
            ctypes.windll.user32.SetCursorPos(screen_x2, screen_y2)
            time.sleep(0.02)
            ctypes.windll.user32.mouse_event(up_flag, 0, 0, 0, 0)
            
            log(f"[DRAG] ({screen_x1},{screen_y1})->({screen_x2},{screen_y2}) in {duration_ms}ms" + (f" [hwnd={effective_hwnd}]" if effective_hwnd else "") + (" [current_start]" if use_current_start else ""))
        
        elif action.action == "TEXT":
            text = v.get("text", "")
            mode = v.get("mode", "paste")
            speed_ms = v.get("speed_ms", 100)
            
            if not text:
                return
            
            if mode == "paste":
                # Use clipboard to paste text
                self._paste_text(text)
            else:  # humanize
                # Type each character with configurable delays
                self._type_text_humanize(text, speed_ms)
        
        # ==================== FLOW CONTROL ACTIONS ====================
        
        elif action.action == "LABEL":
            # LABEL is just a marker - no execution needed
            label_name = v.get("name", "")
            log(f"[LABEL] Marker: '{label_name}'")
            pass
        
        elif action.action == "GOTO":
            # GOTO jumps to specified label
            target = v.get("target", "Next")
            if target and target.startswith("→ "):
                target = target[2:]
            log(f"[GOTO] Jumping to: '{target}'")
            self._handle_goto(target)
        
        elif action.action == "REPEAT":
            # REPEAT loops back to label N times, then goes to goto destination
            count = v.get("count", 1)
            label = v.get("start_label", "") or v.get("label", "")  # Support both field names
            goto_after = v.get("goto", "Next") or v.get("end_label", "Next")
            
            # Clean up label name
            if label and label.startswith("→ "):
                label = label[2:]
            if goto_after and goto_after.startswith("→ "):
                goto_after = goto_after[2:]
            
            # Get current action index for tracking
            repeat_key = self._current_action_index
            
            # Initialize counter if first time hitting this REPEAT
            if repeat_key not in self._repeat_counters:
                self._repeat_counters[repeat_key] = count
                log(f"[REPEAT] Initialized counter: {count} iterations, label='{label}', goto='{goto_after}'")
            
            remaining = self._repeat_counters[repeat_key]
            
            if remaining > 0:
                # Decrement counter and jump to label
                self._repeat_counters[repeat_key] = remaining - 1
                log(f"[REPEAT] Iteration {count - remaining + 1}/{count}, jumping to '{label}' (remaining: {remaining - 1})")
                if label:
                    self._handle_goto(label)
                else:
                    log(f"[REPEAT] Warning: No label specified, continuing to next")
            else:
                # Counter exhausted, go to destination and reset counter
                log(f"[REPEAT] Completed {count} iterations, going to '{goto_after}'")
                del self._repeat_counters[repeat_key]  # Reset for next time
                self._handle_goto(goto_after)
    
    def _handle_goto(self, target: str, worker_id: int = None):
        """Handle goto logic for flow control (FIND_IMAGE, conditions, etc.)
        
        Args:
            target: Goto target string
            worker_id: If provided, store goto target for worker instead of modifying UI state
        """
        if not target:
            return
        
        target = target.strip()
        
        # Check if in worker context mode
        effective_worker_id = worker_id
        if effective_worker_id is None and hasattr(self, '_current_worker_context'):
            effective_worker_id = self._current_worker_context
        
        # If in worker context, store goto target for worker playback loop to handle
        if effective_worker_id is not None:
            if not hasattr(self, '_worker_goto_targets'):
                self._worker_goto_targets = {}
            self._worker_goto_targets[effective_worker_id] = target
            log(f"[GOTO] Worker {effective_worker_id}: Setting goto target to '{target}'")
            return
        
        # Original UI-level goto handling (for single worker UI playback)
        if target == "Next":
            # Continue to next action (default behavior)
            pass
        elif target == "Previous":
            # Go back one action
            if self._current_action_index > 0:
                self._current_action_index -= 2  # -2 because loop will +1
        elif target == "Start":
            # Go to beginning
            self._current_action_index = -1  # Will become 0 after loop increment
        elif target == "End":
            # Go to end (skip remaining)
            self._current_action_index = len(self.actions)
        elif target == "Exit macro":
            # Stop playback
            self._stop_playback()
        else:
            # Find label by name
            label_name = target.replace("→ ", "").strip()
            log(f"[GOTO] Looking for label: '{label_name}'")
            
            # Debug: list all labels (from LABEL actions AND action.label field)
            available_labels = []
            for idx, act in enumerate(self.actions):
                act_label = ""
                # Check LABEL action's value.name
                if act.action == "LABEL":
                    act_label = act.value.get("name", "") if isinstance(act.value, dict) else ""
                # Also check action.label field (any action can have a label)
                if not act_label and act.label:
                    act_label = act.label
                    
                if act_label:
                    available_labels.append((idx, act_label))
                    if act_label == label_name:
                        self._current_action_index = idx - 1  # -1 because loop will +1
                        log(f"[GOTO] Jumping to label '{label_name}' at index {idx}")
                        return
            
            log(f"[GOTO] Warning: Label '{label_name}' not found. Available labels: {available_labels}")
    
    def _on_playback_complete(self):
        """Called when playback completes"""
        self._is_playing = False
        self._current_action_index = 0
        
        # Hide playback toolbar
        self._hide_playback_toolbar()
        
        self._update_ui_state()
        self._update_status("● Ready", "ready")
        log("[UI] Playback complete")
    
    def _toggle_pause(self):
        """Toggle pause/resume (per spec 3.2)"""
        if not self._is_playing:
            return
        
        if self._is_paused:
            self._playback_pause_event.clear()
            self._is_paused = False
            self._update_status("▶ Playing...", "playing")
            self.btn_pause.config(text="⏸ Pause")
            self._update_playback_toolbar_pause_button()
            log("[UI] Playback resumed")
        else:
            self._playback_pause_event.set()
            self._is_paused = True
            self._update_status("⏸ Paused", "paused")
            self.btn_pause.config(text="▶ Resume")
            self._update_playback_toolbar_pause_button()
            log("[UI] Playback paused")
    
    def _stop_playback(self):
        """Stop playback on all workers"""
        # Signal all threads to stop
        self._playback_stop_event.set()
        
        # Stop all worker threads
        for worker_id, stop_event in self._worker_stop_events.items():
            stop_event.set()
        
        self._is_playing = False
        self._is_paused = False
        self._current_action_index = 0
        
        # Clear worker threads
        self._worker_playback_threads.clear()
        self._worker_stop_events.clear()
        
        # Hide playback toolbar
        self._hide_playback_toolbar()
        
        self._update_ui_state()
        self._update_status("● Ready", "ready")
        self.btn_pause.config(text="⏸ Pause")
        log("[UI] Playback stopped")
    
    def _stop_all(self):
        """Stop recording or playback (per spec 3.3)"""
        if self._is_recording:
            self._stop_recording()
        if self._is_playing:
            self._stop_playback()
    
    def _update_ui_state(self):
        """Update button states based on current state"""
        if self._is_recording:
            self.btn_play.config(state="disabled")
            self.btn_pause.config(state="disabled")
        elif self._is_playing:
            self.btn_record.config(state="disabled")
            self.btn_pause.config(state="normal")
        else:
            self.btn_record.config(state="normal")
            self.btn_play.config(state="normal")
            self.btn_pause.config(state="disabled")

    # ================= ACTION LIST OPERATIONS (per spec 1.3, 1.4) =================
    
    def _refresh_action_list(self):
        """Refresh action tree display with zebra striping"""
        for item in self.action_tree.get_children():
            self.action_tree.delete(item)
        
        for idx, action in enumerate(self.actions, 1):
            # Action column shows type with enabled state
            action_text = f"{'✓' if action.enabled else '✗'} {action.action}"
            value_text = action.get_value_summary()
            
            # Zebra striping tag
            row_tag = 'evenrow' if (idx - 1) % 2 == 0 else 'oddrow'
            
            # Add warning tag for disabled actions
            tags = [row_tag]
            if not action.enabled:
                tags.append('muted')
            
            self.action_tree.insert("", tk.END, values=(
                idx, action_text, value_text, action.label, action.comment
            ), tags=tags)
    
    def _on_action_double_click(self, event):
        """Handle double-click on action row to edit"""
        item = self.action_tree.identify_row(event.y)
        if item:
            values = self.action_tree.item(item, "values")
            idx = int(values[0]) - 1
            self._open_add_action_dialog(edit_index=idx)
    
    def _on_action_right_click(self, event):
        """Handle right-click on action row - supports multi-select with Copy/Paste"""
        item = self.action_tree.identify_row(event.y)
        if item:
            # If clicked item not in selection, set it as only selection
            # Otherwise keep multi-selection
            if item not in self.action_tree.selection():
                self.action_tree.selection_set(item)
        
        selection = self.action_tree.selection()
        count = len(selection)
        
        menu = tk.Menu(self.root, tearoff=0)
        
        # Copy/Paste always available
        has_clipboard = hasattr(self, '_clipboard_actions') and self._clipboard_actions
        
        if count >= 1:
            menu.add_command(label=f"📋 Sao chép ({count})" if count > 1 else "📋 Sao chép", 
                           command=self._copy_selected_actions, accelerator="Ctrl+C")
            menu.add_command(label="✂ Cắt", command=self._cut_selected_actions, accelerator="Ctrl+X")
        
        paste_label = f"📥 Dán ({len(self._clipboard_actions)})" if has_clipboard else "📥 Dán"
        menu.add_command(label=paste_label, command=self._paste_actions, 
                        state="normal" if has_clipboard else "disabled", accelerator="Ctrl+V")
        menu.add_separator()
        
        if count == 1 and item:
            # Single item - show full menu
            values = self.action_tree.item(item, "values")
            idx = int(values[0]) - 1
            menu.add_command(label="✏ Sửa", command=lambda: self._open_add_action_dialog(edit_index=idx))
            menu.add_command(label="✓/✗ Bật/Tắt", command=lambda: self._toggle_action_enabled(idx))
            menu.add_separator()
            menu.add_command(label="🗑 Xóa", command=lambda: self._delete_action_at(idx), accelerator="Del")
            menu.add_separator()
            menu.add_command(label="⬆ Lên trên", command=lambda: self._move_action(idx, -1))
            menu.add_command(label="⬇ Xuống dưới", command=lambda: self._move_action(idx, 1))
            
            # Check if GROUP to show Ungroup option
            if 0 <= idx < len(self.actions) and self.actions[idx].action == "GROUP":
                menu.add_separator()
                menu.add_command(label="📤 Tách nhóm", command=lambda: self._ungroup_action(idx))
        elif count > 1:
            # Multiple items - show bulk actions
            menu.add_command(label=f"🗑 Xóa {count} đã chọn", command=self._delete_selected_actions, accelerator="Del")
            menu.add_separator()
            menu.add_command(label="📦 Gộp nhóm đã chọn", command=self._group_selected_actions)
            menu.add_separator()
            menu.add_command(label="✓ Bật tất cả đã chọn", command=self._enable_selected_actions)
            menu.add_command(label="✗ Tắt tất cả đã chọn", command=self._disable_selected_actions)
        
        menu.add_separator()
        menu.add_command(label="✓ Chọn tất cả", command=self._select_all_actions, accelerator="Ctrl+A")
        
        menu.tk_popup(event.x_root, event.y_root)
    
    def _toggle_action_enabled(self, idx: int):
        """Toggle enabled state of action"""
        if 0 <= idx < len(self.actions):
            self.actions[idx].enabled = not self.actions[idx].enabled
            self._refresh_action_list()
    
    def _select_all_actions(self, event=None):
        """Select all actions (Ctrl+A)"""
        for item in self.action_tree.get_children():
            self.action_tree.selection_add(item)
        return "break"  # Prevent default behavior
    
    def _delete_selected_actions(self, event=None):
        """Delete all selected actions (Delete key)"""
        selection = self.action_tree.selection()
        if not selection:
            return
        
        # Get indices of selected items (reverse order to delete from end)
        indices = []
        for item in selection:
            values = self.action_tree.item(item, "values")
            idx = int(values[0]) - 1
            indices.append(idx)
        
        # Sort in reverse to delete from end first
        indices.sort(reverse=True)
        
        count = len(indices)
        if count == 1:
            msg = f"Delete action #{indices[0] + 1}?"
        else:
            msg = f"Delete {count} selected actions?"
        
        if messagebox.askyesno("Delete", msg):
            for idx in indices:
                if 0 <= idx < len(self.actions):
                    self.actions.pop(idx)
            self._refresh_action_list()
            log(f"[UI] Deleted {count} action(s)")
        
        return "break"
    
    def _enable_selected_actions(self):
        """Enable all selected actions"""
        selection = self.action_tree.selection()
        for item in selection:
            values = self.action_tree.item(item, "values")
            idx = int(values[0]) - 1
            if 0 <= idx < len(self.actions):
                self.actions[idx].enabled = True
        self._refresh_action_list()
    
    def _disable_selected_actions(self):
        """Disable all selected actions"""
        selection = self.action_tree.selection()
        for item in selection:
            values = self.action_tree.item(item, "values")
            idx = int(values[0]) - 1
            if 0 <= idx < len(self.actions):
                self.actions[idx].enabled = False
        self._refresh_action_list()
    
    def _remove_action(self):
        """Remove selected action(s) - supports multi-select"""
        self._delete_selected_actions()
    
    def _delete_action_at(self, idx: int):
        """Delete action at specific index"""
        if 0 <= idx < len(self.actions):
            action = self.actions[idx]
            if messagebox.askyesno("Delete", f"Delete action #{idx + 1} ({action.action})?"):
                self.actions.pop(idx)
                self._refresh_action_list()
    
    def _move_action(self, idx: int, direction: int):
        """Move action up or down"""
        new_idx = idx + direction
        if 0 <= new_idx < len(self.actions):
            self.actions[idx], self.actions[new_idx] = self.actions[new_idx], self.actions[idx]
            self._refresh_action_list()
    
    def _move_action_up(self):
        """Move selected action up"""
        selection = self.action_tree.selection()
        if not selection:
            return
        values = self.action_tree.item(selection[0], "values")
        idx = int(values[0]) - 1
        self._move_action(idx, -1)
    
    def _move_action_down(self):
        """Move selected action down"""
        selection = self.action_tree.selection()
        if not selection:
            return
        values = self.action_tree.item(selection[0], "values")
        idx = int(values[0]) - 1
        self._move_action(idx, 1)
    
    # ================= DRAG AND DROP =================
    
    def _on_drag_start(self, event):
        """Start drag operation"""
        item = self.action_tree.identify_row(event.y)
        if not item:
            self._drag_data = {"items": [], "start_y": 0}
            return
        
        selection = self.action_tree.selection()
        if item not in selection:
            # Clicking on non-selected item - select only that item
            self.action_tree.selection_set(item)
            selection = (item,)
        
        # Store drag data
        self._drag_data = {
            "items": list(selection),
            "start_y": event.y,
            "dragging": False
        }
    
    def _on_drag_motion(self, event):
        """Handle drag motion"""
        if not self._drag_data.get("items"):
            return
        
        # Start dragging after moving 5 pixels
        if not self._drag_data.get("dragging"):
            if abs(event.y - self._drag_data["start_y"]) > 5:
                self._drag_data["dragging"] = True
                self.action_tree.config(cursor="hand2")
        
        if self._drag_data.get("dragging"):
            # Visual feedback - highlight drop target
            target_item = self.action_tree.identify_row(event.y)
            if target_item and target_item not in self._drag_data["items"]:
                # Clear previous selection visually and show drop indicator
                for item in self.action_tree.get_children():
                    self.action_tree.item(item, tags=())
                self.action_tree.item(target_item, tags=("drop_target",))
                self.action_tree.tag_configure("drop_target", background="#e3f2fd")
    
    def _on_drag_end(self, event):
        """End drag operation and move items"""
        if not self._drag_data.get("dragging") or not self._drag_data.get("items"):
            self._drag_data = {"items": [], "start_y": 0}
            return
        
        self.action_tree.config(cursor="")
        
        # Clear drop target highlight
        for item in self.action_tree.get_children():
            self.action_tree.item(item, tags=())
        
        target_item = self.action_tree.identify_row(event.y)
        if not target_item or target_item in self._drag_data["items"]:
            self._drag_data = {"items": [], "start_y": 0}
            return
        
        # Get indices
        source_indices = []
        for item in self._drag_data["items"]:
            values = self.action_tree.item(item, "values")
            source_indices.append(int(values[0]) - 1)
        
        target_values = self.action_tree.item(target_item, "values")
        target_idx = int(target_values[0]) - 1
        
        # Sort source indices
        source_indices.sort()
        
        # Extract actions to move
        actions_to_move = [self.actions[i] for i in source_indices]
        
        # Remove from original positions (reverse order)
        for i in reversed(source_indices):
            self.actions.pop(i)
        
        # Adjust target index after removals
        removed_before_target = sum(1 for i in source_indices if i < target_idx)
        new_target_idx = target_idx - removed_before_target
        
        # Insert at new position
        for i, action in enumerate(actions_to_move):
            self.actions.insert(new_target_idx + i + 1, action)
        
        self._drag_data = {"items": [], "start_y": 0}
        self._refresh_action_list()
        log(f"[UI] Moved {len(actions_to_move)} action(s) to position {new_target_idx + 2}")
    
    # ================= GROUP/UNGROUP =================
    
    def _group_selected_actions(self):
        """Group selected actions into a GROUP action"""
        selection = self.action_tree.selection()
        if len(selection) < 2:
            messagebox.showwarning("Nhóm", "Vui lòng chọn ít nhất 2 actions để nhóm")
            return
        
        # Get indices of selected items
        indices = []
        for item in selection:
            values = self.action_tree.item(item, "values")
            indices.append(int(values[0]) - 1)
        
        indices.sort()
        
        # Check if contiguous
        if indices != list(range(indices[0], indices[-1] + 1)):
            messagebox.showwarning("Group", "Selected actions must be contiguous (next to each other)")
            return
        
        # Prompt for group name
        group_name = simpledialog.askstring("Group Name", "Enter group name:", initialvalue="Group")
        if not group_name:
            return
        
        # Extract actions to group
        actions_to_group = [self.actions[i].to_dict() for i in indices]
        
        # Create GROUP action
        group_action = Action(
            action="GROUP",
            value={"name": group_name, "actions": actions_to_group},
            label=group_name,
            comment=f"{len(actions_to_group)} actions"
        )
        
        # Remove original actions (reverse order)
        for i in reversed(indices):
            self.actions.pop(i)
        
        # Insert group at first position
        self.actions.insert(indices[0], group_action)
        
        self._refresh_action_list()
        log(f"[UI] Grouped {len(actions_to_group)} actions into '{group_name}'")
    
    def _ungroup_action(self, idx: int):
        """Ungroup a GROUP action back to individual actions"""
        if idx < 0 or idx >= len(self.actions):
            return
        
        action = self.actions[idx]
        if action.action != "GROUP":
            return
        
        # Get grouped actions
        grouped_actions = action.value.get("actions", [])
        if not grouped_actions:
            return
        
        # Remove the GROUP action
        self.actions.pop(idx)
        
        # Insert individual actions
        for i, action_dict in enumerate(grouped_actions):
            new_action = Action.from_dict(action_dict)
            self.actions.insert(idx + i, new_action)
        
        self._refresh_action_list()
        log(f"[UI] Ungrouped {len(grouped_actions)} actions")
    
    def _save_actions(self):
        """Save actions to single .macro file (Base64 embedded images)"""
        if not self.actions:
            messagebox.showwarning("Warning", "No actions to save")
            return
        
        # Ask for save location - remember last used directory
        initial_dir = getattr(self, '_last_save_dir', MACROS_DIR)
        filepath = filedialog.asksaveasfilename(
            title="Lưu Macro",
            initialdir=initial_dir,
            defaultextension=".macro",
            filetypes=[("Macro files", "*.macro"), ("JSON files", "*.json"), ("All files", "*.*")]
        )
        if not filepath:
            return
        
        # Remember this directory for next time
        self._last_save_dir = os.path.dirname(filepath)
        
        import base64
        
        try:
            # Build actions data with embedded images
            actions_data = []
            images_embedded = {}
            image_count = 0
            
            def embed_action_images(action_dict, images_embedded, image_count):
                """Recursively embed images in action (handles nested GROUP actions)"""
                import re
                
                # Handle FIND_IMAGE
                if action_dict.get("action") == "FIND_IMAGE" and action_dict.get("value", {}).get("template_path"):
                    old_path = action_dict["value"]["template_path"]
                    log(f"[SAVE] FIND_IMAGE template_path: {old_path}")
                    if old_path.startswith("@embedded:"):
                        log(f"[SAVE] Already embedded, keeping reference")
                    elif os.path.exists(old_path):
                        with open(old_path, "rb") as img_file:
                            img_data = base64.b64encode(img_file.read()).decode('utf-8')
                        
                        filename = os.path.basename(old_path)
                        clean_filename = re.sub(r'^(img_\d{3}_)+', '', filename)
                        if not clean_filename:
                            clean_filename = f"image_{image_count:03d}.png"
                        img_key = f"img_{image_count:03d}_{clean_filename}"
                        images_embedded[img_key] = img_data
                        action_dict["value"]["template_path"] = f"@embedded:{img_key}"
                        image_count += 1
                        log(f"[SAVE] Embedded image: {filename} -> {img_key}")
                    else:
                        log(f"[SAVE] ⚠️ Image NOT FOUND: {old_path} - keeping path as-is")
                
                # Handle WAIT_SCREEN_CHANGE
                if action_dict.get("action") == "WAIT_SCREEN_CHANGE" and action_dict.get("value", {}).get("reference_image"):
                    old_path = action_dict["value"]["reference_image"]
                    if os.path.exists(old_path):
                        with open(old_path, "rb") as img_file:
                            img_data = base64.b64encode(img_file.read()).decode('utf-8')
                        
                        filename = os.path.basename(old_path)
                        clean_filename = re.sub(r'^(img_\d{3}_)+', '', filename)
                        if not clean_filename:
                            clean_filename = f"image_{image_count:03d}.png"
                        img_key = f"img_{image_count:03d}_{clean_filename}"
                        images_embedded[img_key] = img_data
                        action_dict["value"]["reference_image"] = f"@embedded:{img_key}"
                        image_count += 1
                
                # Handle GROUP - recursively process nested actions
                if action_dict.get("action") == "GROUP" and action_dict.get("value", {}).get("actions"):
                    for nested_action in action_dict["value"]["actions"]:
                        image_count = embed_action_images(nested_action, images_embedded, image_count)
                
                return image_count
            
            # Process all actions - including nested ones in GROUP
            for action in self.actions:
                action_dict = action.to_dict()
                image_count = embed_action_images(action_dict, images_embedded, image_count)
                actions_data.append(action_dict)
            
            # Save single file
            data = {
                "version": "2.1",
                "format": "embedded",
                "name": os.path.splitext(os.path.basename(filepath))[0],
                "created": __import__('datetime').datetime.now().isoformat(),
                "actions": actions_data,
                "images": images_embedded  # All images embedded here
            }
            
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            # Calculate file size
            file_size = os.path.getsize(filepath)
            size_str = f"{file_size/1024:.1f} KB" if file_size < 1024*1024 else f"{file_size/1024/1024:.1f} MB"
            
            messagebox.showinfo("Success", 
                f"✅ Đã lưu macro thành công!\n\n"
                f"📄 File: {os.path.basename(filepath)}\n"
                f"📝 Actions: {len(self.actions)}\n"
                f"🖼️ Images: {image_count} (embedded)\n"
                f"💾 Size: {size_str}\n\n"
                f"💡 Chỉ cần 1 file này để share/backup!")
            log(f"[UI] Saved macro to: {filepath}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save: {e}")
    
    def _load_actions(self):
        """Load actions from .macro file(s) - supports multiple file selection"""
        # Remember last used directory
        initial_dir = getattr(self, '_last_load_dir', MACROS_DIR)
        filepaths = filedialog.askopenfilenames(  # Changed to askopenfilenames
            title="Tải Macro (Có thể chọn nhiều files)",
            initialdir=initial_dir,
            filetypes=[
                ("Macro files", "*.macro"),
                ("JSON files", "*.json"),
                ("All files", "*.*")
            ]
        )
        if not filepaths:
            return
        
        # Remember this directory for next time
        self._last_load_dir = os.path.dirname(filepaths[0])
        
        # Load all selected files in order
        total_loaded = 0
        for filepath in filepaths:
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                # Check format version
                fmt = data.get("format", "")
                images = data.get("images", {})
                actions_data = data.get("actions", [])
                
                if fmt == "embedded" and images:
                    # New format - extract embedded images to temp
                    self._load_embedded_macro(filepath, data)
                else:
                    # Legacy format - load directly
                    self._load_legacy_macro(filepath, data)
                
                total_loaded += len(actions_data)
                log(f"[UI] Loaded {len(actions_data)} actions from {os.path.basename(filepath)}")
                    
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load {os.path.basename(filepath)}: {e}")
        
        if len(filepaths) > 1:
            messagebox.showinfo("Success", f"✅ Đã load {len(filepaths)} files với tổng {total_loaded} actions!")
    
    def _load_embedded_macro(self, filepath, data):
        """Load macro with embedded base64 images"""
        import base64
        import tempfile
        
        images = data.get("images", {})
        actions_data = data.get("actions", [])
        
        # Create temp folder for extracted images
        macro_name = os.path.splitext(os.path.basename(filepath))[0]
        temp_dir = os.path.join(tempfile.gettempdir(), "macro_images", macro_name)
        os.makedirs(temp_dir, exist_ok=True)
        
        # Extract images
        log(f"[LOAD] Extracting {len(images)} images to {temp_dir}")
        for img_key, img_b64 in images.items():
            try:
                img_data = base64.b64decode(img_b64)
                img_path = os.path.join(temp_dir, img_key)
                with open(img_path, "wb") as f:
                    f.write(img_data)
                log(f"[LOAD] Extracted: {img_key} -> {img_path}")
            except Exception as e:
                log(f"[UI] Failed to extract image {img_key}: {e}")
        
        # Update action paths to extracted images
        log(f"[LOAD] Updating {len(actions_data)} action paths...")
        
        def update_embedded_paths(action_data, temp_dir):
            """Recursively update @embedded: paths in action (handles nested GROUP actions)"""
            # Handle FIND_IMAGE
            if action_data.get("action") == "FIND_IMAGE":
                template_path = action_data.get("value", {}).get("template_path", "")
                if template_path.startswith("@embedded:"):
                    img_key = template_path.replace("@embedded:", "")
                    new_path = os.path.join(temp_dir, img_key)
                    action_data["value"]["template_path"] = new_path
                    log(f"[LOAD] Resolved FIND_IMAGE: {img_key} -> {new_path}")
            
            # Handle WAIT_SCREEN_CHANGE
            if action_data.get("action") == "WAIT_SCREEN_CHANGE":
                ref_path = action_data.get("value", {}).get("reference_image", "")
                if ref_path.startswith("@embedded:"):
                    img_key = ref_path.replace("@embedded:", "")
                    new_path = os.path.join(temp_dir, img_key)
                    action_data["value"]["reference_image"] = new_path
                    log(f"[LOAD] Resolved WAIT_SCREEN_CHANGE: {img_key} -> {new_path}")
            
            # Handle GROUP - recursively update nested actions
            if action_data.get("action") == "GROUP" and action_data.get("value", {}).get("actions"):
                log(f"[LOAD] Processing GROUP with {len(action_data['value']['actions'])} nested actions")
                for nested_action in action_data["value"]["actions"]:
                    update_embedded_paths(nested_action, temp_dir)
        
        # Process all actions - including nested ones in GROUP
        for action_data in actions_data:
            update_embedded_paths(action_data, temp_dir)
        
        # Append to existing actions instead of replacing
        new_actions = [Action.from_dict(a) for a in actions_data]
        self.actions.extend(new_actions)
        self._refresh_action_list()
        
        log(f"[UI] Loaded embedded macro: {filepath} - {len(new_actions)} actions, {len(images)} images")
    
    def _load_legacy_macro(self, filepath, data):
        """Load legacy format macro (folder-based or simple JSON)"""
        actions_data = data.get("actions", [])
        folder = os.path.dirname(filepath)
        
        # Update template paths to absolute if relative
        for action_data in actions_data:
            if action_data.get("action") == "FIND_IMAGE":
                template_path = action_data.get("value", {}).get("template_path", "")
                if template_path and not os.path.isabs(template_path):
                    abs_path = os.path.join(folder, template_path)
                    action_data["value"]["template_path"] = abs_path
        
        # Append to existing actions instead of replacing
        new_actions = [Action.from_dict(a) for a in actions_data]
        self.actions.extend(new_actions)
        self._refresh_action_list()
        
        log(f"[UI] Loaded legacy macro: {filepath} - {len(new_actions)} actions")

    # ================= ADD ACTION DIALOG (per spec 5 - V2 expanded) =================
    
    def _open_add_action_dialog(self, edit_index: int = None, target_actions: list = None):
        """Open Add Action dialog with modern JetBrains-inspired UI
        
        Args:
            edit_index: Index of action to edit (None for new action)
            target_actions: Optional list to modify instead of self.actions (for Multi-Worker Editor)
        """
        dialog = tk.Toplevel(self.root)
        dialog.title("Thêm Action" if edit_index is None else "Sửa Action")
        dialog.geometry("700x850")  # Full size to show all content
        dialog.minsize(780, 800)
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Apply dark theme colors
        S = ModernStyle
        dialog.configure(bg=S.BG_PRIMARY)
        
        # Determine which action list to use
        action_list = target_actions if target_actions is not None else self.actions
        is_worker_context = (target_actions is not None)  # True if editing worker-specific actions
        
        # Load existing action if editing
        edit_action = None
        if edit_index is not None and 0 <= edit_index < len(action_list):
            edit_action = action_list[edit_index]
        
        # ===== HEADER (compact) =====
        header_frame = tk.Frame(dialog, bg=S.BG_SECONDARY, height=40)
        header_frame.pack(fill="x", padx=0, pady=0)
        header_frame.pack_propagate(False)
        
        title_text = "✏️ Sửa Action" if edit_action else "➕ Thêm Action Mới"
        tk.Label(header_frame, text=title_text, 
                bg=S.BG_SECONDARY, fg=S.FG_PRIMARY,
                font=(S.FONT_FAMILY, S.FONT_SIZE_LG, "bold")).pack(side="left", padx=S.PAD_MD, pady=S.PAD_SM)
        
        # ===== MAIN CONTENT AREA =====
        content_frame = tk.Frame(dialog, bg=S.BG_PRIMARY)
        content_frame.pack(fill="both", expand=True, padx=S.PAD_MD, pady=S.PAD_SM)
        
        # ===== CATEGORY BUTTONS (compact) =====
        cat_frame = tk.Frame(content_frame, bg=S.BG_CARD, relief="flat")
        cat_frame.pack(fill="x", pady=(0, S.PAD_SM))
        
        cat_header = tk.Frame(cat_frame, bg=S.BG_CARD)
        cat_header.pack(fill="x", padx=S.PAD_SM, pady=S.PAD_XS)
        
        tk.Label(cat_header, text="📋 Chọn Loại Action", 
                bg=S.BG_CARD, fg=S.FG_ACCENT,
                font=(S.FONT_FAMILY, S.FONT_SIZE_MD, "bold")).pack(side="left")
        
        type_var = tk.StringVar(value=edit_action.action if edit_action else "")
        
        # Category definitions with their sub-options (uniform icon+text)
        categories = {
            "Click": ["CLICK", "DRAG", "WHEEL"],
            "Input": ["KEY_PRESS", "COMBOKEY", "TEXT"],
            "Image": ["FIND_IMAGE", "CAPTURE_IMAGE"],
            "Wait": ["WAIT", "WAIT_TIME", "WAIT_PIXEL_COLOR", "WAIT_SCREEN_CHANGE", "WAIT_COLOR_DISAPPEAR", "WAIT_COMBOKEY", "WAIT_FILE"],
            "Flow": ["REPEAT", "EMBED_MACRO", "GROUP"]
        }
        
        # Category button display (icon + short text) and colors
        cat_display = {
            "Click": ("🖱", "Click"),
            "Input": ("⌨", "Input"),
            "Image": ("🖼", "Image"),
            "Wait": ("⏳", "Wait"),
            "Flow": ("🔄", "Flow")
        }
        cat_colors = {
            "Click": S.ACCENT_GREEN,
            "Input": S.ACCENT_BLUE, 
            "Image": S.ACCENT_ORANGE,
            "Wait": S.ACCENT_PURPLE,
            "Flow": S.ACCENT_CYAN
        }
        
        selected_type_label = tk.Label(cat_frame, text="Chưa chọn action", 
                                       bg=S.BG_CARD, fg=S.FG_MUTED,
                                       font=(S.FONT_FAMILY, S.FONT_SIZE_MD))
        
        def show_category_popup(category):
            """Show popup with sub-options for category"""
            popup = tk.Toplevel(dialog)
            icon, text = cat_display[category]
            popup.title(f"Chọn {text} Action")
            popup.geometry("280x350")
            popup.transient(dialog)
            popup.grab_set()
            popup.configure(bg=S.BG_PRIMARY)
            
            # Center on dialog
            popup.geometry(f"+{dialog.winfo_x() + 250}+{dialog.winfo_y() + 100}")
            
            # Header
            header = tk.Frame(popup, bg=S.BG_SECONDARY, height=40)
            header.pack(fill="x")
            header.pack_propagate(False)
            tk.Label(header, text=f"{icon} {text} Actions", 
                    bg=S.BG_SECONDARY, fg=S.FG_PRIMARY,
                    font=(S.FONT_FAMILY, S.FONT_SIZE_MD, "bold")).pack(side="left", padx=S.PAD_MD, pady=S.PAD_SM)
            
            list_frame = tk.Frame(popup, bg=S.BG_PRIMARY)
            list_frame.pack(fill="both", expand=True, padx=S.PAD_MD, pady=S.PAD_MD)
            
            # Get the key for lookup
            cat_key = category
            for action_type in categories[cat_key]:
                def select_action(t=action_type):
                    type_var.set(t)
                    selected_type_label.config(text=f"✓ {t}", fg=S.ACCENT_GREEN)
                    popup.destroy()
                    render_config_panel()
                
                # Format display name
                display_name = action_type.replace("_", " ").title()
                btn = tk.Button(list_frame, text=f"  {display_name}", 
                               command=select_action,
                               bg=S.BG_CARD, fg=S.FG_PRIMARY,
                               activebackground=S.BG_TERTIARY, activeforeground=S.FG_PRIMARY,
                               font=(S.FONT_FAMILY, S.FONT_SIZE_SM), 
                               anchor="w", relief="flat", cursor="hand2", bd=0,
                               padx=S.PAD_MD, pady=S.PAD_XS, highlightthickness=0)
                btn.pack(fill="x", pady=1)
                
                # Hover effect
                def on_enter(e, b=btn):
                    b.config(bg=S.BG_TERTIARY)
                def on_leave(e, b=btn):
                    b.config(bg=S.BG_CARD)
                btn.bind("<Enter>", on_enter)
                btn.bind("<Leave>", on_leave)
            
            # Cancel button
            cancel_btn = S.create_modern_button(popup, "Cancel", popup.destroy, "secondary", width=12)
            cancel_btn.pack(pady=S.PAD_MD)
        
        # Create category buttons in a row - Win11 style
        btn_row = tk.Frame(cat_frame, bg=S.BG_CARD)
        btn_row.pack(fill="x", padx=S.PAD_SM, pady=(0, S.PAD_XS))
        
        def adjust_color(hex_color, factor):
            r = int(hex_color[1:3], 16)
            g = int(hex_color[3:5], 16)
            b = int(hex_color[5:7], 16)
            if factor > 0:
                r = min(255, int(r + (255 - r) * factor))
                g = min(255, int(g + (255 - g) * factor))
                b = min(255, int(b + (255 - b) * factor))
            else:
                r = max(0, int(r * (1 + factor)))
                g = max(0, int(g * (1 + factor)))
                b = max(0, int(b * (1 + factor)))
            return f"#{r:02x}{g:02x}{b:02x}"
        
        for cat_name in categories.keys():
            bg_color = cat_colors[cat_name]
            hover_color = adjust_color(bg_color, 0.2)
            icon, text = cat_display[cat_name]
            
            btn = tk.Button(btn_row, text=f"{icon}  {text}", 
                          command=lambda c=cat_name: show_category_popup(c),
                          bg=bg_color, fg=S.FG_PRIMARY,
                          activebackground=hover_color, activeforeground=S.FG_PRIMARY,
                          font=(S.FONT_FAMILY, S.FONT_SIZE_SM, "bold"), 
                          relief="flat", cursor="hand2", bd=0,
                          width=8, height=1,
                          highlightthickness=0)
            btn.pack(side="left", padx=S.PAD_XS, pady=S.PAD_SM)
            
            # Smooth hover
            def on_enter(e, b=btn, hc=hover_color):
                b.config(bg=hc)
            def on_leave(e, b=btn, bc=bg_color):
                b.config(bg=bc)
            btn.bind("<Enter>", on_enter)
            btn.bind("<Leave>", on_leave)
        
        selected_type_label.pack(side="left", padx=S.PAD_LG)
        
        # Set initial type if editing
        if edit_action:
            type_var.set(edit_action.action)
            selected_type_label.config(text=f"✓ {edit_action.action}", fg=S.ACCENT_GREEN)
        
        # ===== CONFIGURATION PANEL (compact) =====
        config_outer = tk.Frame(content_frame, bg=S.BG_CARD)
        config_outer.pack(fill="both", expand=True, pady=(0, S.PAD_SM))
        
        config_header = tk.Frame(config_outer, bg=S.BG_CARD)
        config_header.pack(fill="x", padx=S.PAD_SM, pady=S.PAD_XS)
        tk.Label(config_header, text="⚙️ Configuration", 
                bg=S.BG_CARD, fg=S.FG_ACCENT,
                font=(S.FONT_FAMILY, S.FONT_SIZE_MD, "bold")).pack(side="left")
        
        # Scrollable config frame
        config_canvas = tk.Canvas(config_outer, bg=S.BG_CARD, highlightthickness=0)
        config_scrollbar = ttk.Scrollbar(config_outer, orient="vertical", command=config_canvas.yview)
        config_frame = tk.Frame(config_canvas, bg=S.BG_CARD)
        
        config_frame.bind("<Configure>", lambda e: config_canvas.configure(scrollregion=config_canvas.bbox("all")))
        config_canvas.create_window((0, 0), window=config_frame, anchor="nw")
        config_canvas.configure(yscrollcommand=config_scrollbar.set)
        
        config_canvas.pack(side="left", fill="both", expand=True, padx=S.PAD_SM, pady=(0, S.PAD_XS))
        config_scrollbar.pack(side="right", fill="y")
        
        # Enable mousewheel scrolling (with safety check)
        def on_mousewheel(event):
            try:
                if config_canvas.winfo_exists():
                    config_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
            except:
                pass  # Canvas was destroyed
        config_canvas.bind_all("<MouseWheel>", on_mousewheel)
        
        # Unbind on dialog close (via X button)
        def on_dialog_close():
            try:
                config_canvas.unbind_all("<MouseWheel>")
            except:
                pass
            dialog.destroy()
        dialog.protocol("WM_DELETE_WINDOW", on_dialog_close)
        
        config_widgets = {}
        
        def render_config_panel():
            """Clear and render config based on type"""
            for w in config_frame.winfo_children():
                w.destroy()
            config_widgets.clear()
            
            action_type = type_var.get()
            
            if not action_type:
                placeholder = tk.Frame(config_frame, bg=S.BG_CARD, height=200)
                placeholder.pack(fill="both", expand=True, pady=S.PAD_XXL)
                tk.Label(placeholder, text="👆 Select an action type above", 
                        bg=S.BG_CARD, fg=S.FG_MUTED,
                        font=(S.FONT_FAMILY, S.FONT_SIZE_LG)).pack(expand=True)
                return
            
            value = edit_action.value if edit_action else {}
            
            # Basic actions
            if action_type == "CLICK":
                self._render_click_action_config(config_frame, config_widgets, value, dialog, is_worker_context)
            elif action_type == "WAIT":
                self._render_wait_action_config(config_frame, config_widgets, value)
            elif action_type == "KEY_PRESS":
                self._render_keypress_action_config(config_frame, config_widgets, value)
            elif action_type == "COMBOKEY":
                self._render_combokey_action_config(config_frame, config_widgets, value)
            elif action_type == "WHEEL":
                self._render_wheel_action_config(config_frame, config_widgets, value, is_worker_context, dialog)
            elif action_type == "DRAG":
                self._render_drag_action_config(config_frame, config_widgets, value, dialog, is_worker_context)
            elif action_type == "TEXT":
                self._render_text_action_config(config_frame, config_widgets, value)
            # V2 Wait Actions
            elif action_type == "WAIT_TIME":
                self._render_wait_time_config(config_frame, config_widgets, value)
            elif action_type == "WAIT_PIXEL_COLOR":
                self._render_wait_pixel_color_config(config_frame, config_widgets, value, dialog)
            elif action_type == "WAIT_SCREEN_CHANGE":
                self._render_wait_screen_change_config(config_frame, config_widgets, value, dialog)
            elif action_type == "WAIT_COLOR_DISAPPEAR":
                self._render_wait_color_disappear_config(config_frame, config_widgets, value, dialog)
            elif action_type == "WAIT_COMBOKEY":
                self._render_wait_combokey_config(config_frame, config_widgets, value)
            elif action_type == "WAIT_FILE":
                self._render_wait_file_config(config_frame, config_widgets, value)
            # V2 Image Actions
            elif action_type == "FIND_IMAGE":
                self._render_find_image_config(config_frame, config_widgets, value, dialog)
            elif action_type == "CAPTURE_IMAGE":
                self._render_capture_image_config(config_frame, config_widgets, value, dialog)
            # V2 Flow Control
            elif action_type == "LABEL":
                self._render_label_config(config_frame, config_widgets, value)
            elif action_type == "GOTO":
                self._render_goto_config(config_frame, config_widgets, value)
            elif action_type == "REPEAT":
                self._render_repeat_config(config_frame, config_widgets, value)
            elif action_type == "EMBED_MACRO":
                self._render_embed_macro_config(config_frame, config_widgets, value)
            elif action_type == "GROUP":
                self._render_group_config(config_frame, config_widgets, value)
            # Misc
            elif action_type == "COMMENT":
                self._render_comment_config(config_frame, config_widgets, value)
            elif action_type == "SET_VARIABLE":
                self._render_set_variable_config(config_frame, config_widgets, value)
        
        # Render initial config panel
        render_config_panel()
        
        # ===== BOTTOM OPTIONS (Label, Comment, Enabled) =====
        options_frame = tk.Frame(content_frame, bg=S.BG_CARD)
        options_frame.pack(fill="x", pady=(0, S.PAD_LG))
        
        options_inner = tk.Frame(options_frame, bg=S.BG_CARD)
        options_inner.pack(fill="x", padx=S.PAD_LG, pady=S.PAD_MD)
        
        # Enabled checkbox
        enabled_var = tk.BooleanVar(value=edit_action.enabled if edit_action else True)
        enabled_cb = tk.Checkbutton(options_inner, text="✓ Enabled", variable=enabled_var,
                                    bg=S.BG_CARD, fg=S.FG_PRIMARY, selectcolor=S.BG_INPUT,
                                    activebackground=S.BG_CARD, activeforeground=S.FG_PRIMARY,
                                    font=(S.FONT_FAMILY, S.FONT_SIZE_MD, "bold"))
        enabled_cb.pack(side="left", padx=(0, S.PAD_XL))
        
        # Label
        tk.Label(options_inner, text="Label:", bg=S.BG_CARD, fg=S.FG_SECONDARY,
                font=(S.FONT_FAMILY, S.FONT_SIZE_MD)).pack(side="left", padx=(0, S.PAD_SM))
        label_var = tk.StringVar(value=edit_action.label if edit_action else "")
        label_entry = S.create_entry(options_inner, textvariable=label_var, width=15)
        label_entry.pack(side="left", padx=(0, S.PAD_XL))
        
        # Comment
        tk.Label(options_inner, text="Comment:", bg=S.BG_CARD, fg=S.FG_SECONDARY,
                font=(S.FONT_FAMILY, S.FONT_SIZE_MD)).pack(side="left", padx=(0, S.PAD_SM))
        comment_var = tk.StringVar(value=edit_action.comment if edit_action else "")
        comment_entry = S.create_entry(options_inner, textvariable=comment_var, width=30)
        comment_entry.pack(side="left")
        
        # ===== FOOTER BUTTONS (compact) =====
        footer_frame = tk.Frame(dialog, bg=S.BG_SECONDARY, height=45)
        footer_frame.pack(fill="x", side="bottom")
        footer_frame.pack_propagate(False)
        
        btn_container = tk.Frame(footer_frame, bg=S.BG_SECONDARY)
        btn_container.pack(expand=True)
        
        def save_action():
            action_type = type_var.get()
            
            # Validate type selected
            if not action_type:
                messagebox.showwarning("Warning", "Vui lòng chọn loại Action trước!")
                return
            
            value = self._get_action_value_from_widgets(action_type, config_widgets)
            
            new_action = Action(
                id=edit_action.id if edit_action else str(uuid.uuid4())[:8],
                enabled=enabled_var.get(),
                action=action_type,
                value=value,
                label=label_var.get().strip(),
                comment=comment_var.get().strip()
            )
            
            if edit_index is not None:
                action_list[edit_index] = new_action
            else:
                action_list.append(new_action)
            
            # Only refresh global list if we're modifying it
            if target_actions is None:
                self._refresh_action_list()
            
            # Unbind mousewheel before closing
            config_canvas.unbind_all("<MouseWheel>")
            dialog.destroy()
            log(f"[UI] {'Updated' if edit_index is not None else 'Added'} action: {action_type}")
        
        save_btn = S.create_modern_button(btn_container, "💾 Save", save_action, "success", width=12)
        save_btn.pack(side="left", padx=S.PAD_SM, pady=S.PAD_SM)
        
        def cancel_dialog():
            config_canvas.unbind_all("<MouseWheel>")
            dialog.destroy()
        
        cancel_btn = S.create_modern_button(btn_container, "✖ Cancel", cancel_dialog, "danger", width=12)
        cancel_btn.pack(side="left", padx=S.PAD_SM, pady=S.PAD_SM)
    
    def _create_target_dropdown(self, parent, widgets, value, S, is_worker_context=False):
        """Create target dropdown (Screen/Emulator) for mouse actions
        
        Saves target_mode ("screen" or "emulator") instead of specific hwnd.
        When playback, uses worker's hwnd if target_mode == "emulator".
        This allows actions to work on any emulator, not just the one used during recording.
        
        Args:
            is_worker_context: True if editing worker-specific actions, False for Global Action List
        """
        target_frame = tk.Frame(parent, bg=S.BG_CARD)
        target_frame.pack(fill="x", padx=S.PAD_MD, pady=S.PAD_SM)
        
        tk.Label(target_frame, text="🎯 Target:", bg=S.BG_CARD, fg=S.FG_ACCENT,
                font=(S.FONT_FAMILY, S.FONT_SIZE_SM, "bold")).pack(side="left", padx=(0, S.PAD_SM))
        
        # Only 2 options: Screen or Emulator (will use current worker at runtime)
        targets = [
            ("📺 Full Screen", "screen"),
            ("🎮 Emulator (Worker)", "emulator")
        ]
        
        # Determine default target_mode based on context
        if "target_mode" in value:
            # Use saved mode from existing action
            saved_mode = value.get("target_mode")
        elif "target_hwnd" in value and value.get("target_hwnd"):
            # Backward compat: old action has target_hwnd but no target_mode
            saved_mode = "emulator"
        elif is_worker_context:
            # Worker-specific actions: default to emulator
            saved_mode = "emulator"
        else:
            # Global Action List: default to screen (user can change if needed)
            saved_mode = "screen"
        
        current_name = "📺 Full Screen"
        for name, mode in targets:
            if mode == saved_mode:
                current_name = name
                break
        
        target_var = tk.StringVar(value=current_name)
        target_mode_var = tk.StringVar(value=saved_mode)
        
        # Combobox with target names
        target_names = [t[0] for t in targets]
        target_combo = ttk.Combobox(target_frame, textvariable=target_var, 
                                    values=target_names, state="readonly", width=25)
        target_combo.pack(side="left", padx=S.PAD_XS)
        
        def on_target_change(event=None):
            selected_name = target_var.get()
            for name, mode in targets:
                if name == selected_name:
                    target_mode_var.set(mode)
                    break
        
        target_combo.bind("<<ComboboxSelected>>", on_target_change)
        
        # Store mode var for saving
        widgets["target_mode"] = target_mode_var
        widgets["_target_var"] = target_var
        
        # Info label
        info_label = tk.Label(target_frame, text="", bg=S.BG_CARD, fg=S.FG_MUTED,
                             font=(S.FONT_FAMILY, S.FONT_SIZE_XS))
        info_label.pack(side="left", padx=S.PAD_SM)
        
        def update_info(*args):
            mode = target_mode_var.get()
            if mode == "emulator":
                info_label.config(text="(Chạy trên Worker hiện tại)", fg=S.ACCENT_GREEN)
            else:
                info_label.config(text="", fg=S.FG_MUTED)
        
        target_mode_var.trace_add("write", update_info)
        update_info()
        
        return target_mode_var
    
    def _render_click_action_config(self, parent, widgets, value, dialog=None, is_worker_context=False):
        """Render Click action config (per spec 5.2) - V2 with improved capture"""
        S = ModernStyle
        
        # Target dropdown (Screen/Emulator)
        target_mode_var = self._create_target_dropdown(parent, widgets, value, S, is_worker_context)
        
        # Button type
        btn_frame = tk.Frame(parent, bg=S.BG_CARD)
        btn_frame.pack(fill="x", padx=S.PAD_MD, pady=S.PAD_SM)
        tk.Label(btn_frame, text="Button:", bg=S.BG_CARD, fg=S.FG_SECONDARY,
                font=(S.FONT_FAMILY, S.FONT_SIZE_SM)).pack(side="left", padx=(0, S.PAD_SM))
        btn_var = tk.StringVar(value=value.get("button", "left"))
        btn_combo = ttk.Combobox(btn_frame, textvariable=btn_var, 
                    values=["left", "right", "middle", "double", "hold_left", "hold_right"], 
                    state="readonly", width=12)
        btn_combo.pack(side="left")
        widgets["button"] = btn_var
        
        # Hold duration frame (only shown for hold_left/hold_right)
        hold_frame = tk.Frame(parent, bg=S.BG_CARD)
        hold_frame.pack(fill="x", padx=S.PAD_MD, pady=S.PAD_SM)
        tk.Label(hold_frame, text="Hold (ms):", bg=S.BG_CARD, fg=S.FG_SECONDARY,
                font=(S.FONT_FAMILY, S.FONT_SIZE_SM)).pack(side="left", padx=(0, S.PAD_SM))
        hold_var = tk.IntVar(value=value.get("hold_ms", 500))
        hold_entry = S.create_entry(hold_frame, textvariable=hold_var, width=8)
        hold_entry.pack(side="left", padx=S.PAD_XS)
        widgets["hold_ms"] = hold_var
        
        # Position
        pos_frame = tk.Frame(parent, bg=S.BG_CARD)
        pos_frame.pack(fill="x", padx=S.PAD_MD, pady=S.PAD_SM)
        
        # Checkbox: Use current mouse position (for use after FIND_IMAGE Positioning)
        use_current_var = tk.BooleanVar(value=value.get("use_current_pos", False))
        use_current_cb = tk.Checkbutton(pos_frame, text="🎯 Use current mouse position", 
                                        variable=use_current_var,
                                        bg=S.BG_CARD, fg=S.ACCENT_BLUE, selectcolor=S.BG_INPUT,
                                        activebackground=S.BG_CARD, activeforeground=S.ACCENT_BLUE,
                                        font=(S.FONT_FAMILY, S.FONT_SIZE_SM))
        use_current_cb.pack(side="left", padx=(0, S.PAD_MD))
        widgets["use_current_pos"] = use_current_var
        
        # Coordinates frame (disabled when use_current_pos is checked)
        coords_frame = tk.Frame(pos_frame, bg=S.BG_CARD)
        coords_frame.pack(side="left")
        
        tk.Label(coords_frame, text="X:", bg=S.BG_CARD, fg=S.FG_SECONDARY,
                font=(S.FONT_FAMILY, S.FONT_SIZE_SM)).pack(side="left", padx=(0, S.PAD_XS))
        x_var = tk.IntVar(value=value.get("x", 0))
        x_entry = S.create_entry(coords_frame, textvariable=x_var, width=6)
        x_entry.pack(side="left", padx=S.PAD_XS)
        widgets["x"] = x_var
        
        tk.Label(coords_frame, text="Y:", bg=S.BG_CARD, fg=S.FG_SECONDARY,
                font=(S.FONT_FAMILY, S.FONT_SIZE_SM)).pack(side="left", padx=(S.PAD_SM, S.PAD_XS))
        y_var = tk.IntVar(value=value.get("y", 0))
        y_entry = S.create_entry(coords_frame, textvariable=y_var, width=6)
        y_entry.pack(side="left", padx=S.PAD_XS)
        widgets["y"] = y_var
        
        # Toggle coordinate entries based on checkbox
        def toggle_coords(*args):
            state = "disabled" if use_current_var.get() else "normal"
            x_entry.config(state=state)
            y_entry.config(state=state)
        
        use_current_var.trace_add("write", toggle_coords)
        toggle_coords()  # Initial state
        
        # Input Method selector (PostMessage/ADB for parallel execution)
        method_frame = tk.Frame(parent, bg=S.BG_CARD)
        method_frame.pack(fill="x", padx=S.PAD_MD, pady=S.PAD_SM)
        
        tk.Label(method_frame, text="Input Method:", bg=S.BG_CARD, fg=S.FG_SECONDARY,
                font=(S.FONT_FAMILY, S.FONT_SIZE_SM)).pack(side="left", padx=(0, S.PAD_SM))
        
        current_method = self._input_settings.get("click_method", "SetCursorPos")
        method_var = tk.StringVar(value=current_method)
        method_combo = ttk.Combobox(method_frame, textvariable=method_var,
                                    values=["SetCursorPos", "PostMessage", "ADB Tap"],
                                    state="readonly", width=15)
        method_combo.pack(side="left", padx=S.PAD_XS)
        
        # Info label for method description
        method_info = tk.Label(method_frame, text="", bg=S.BG_CARD, fg=S.FG_MUTED,
                              font=(S.FONT_FAMILY, S.FONT_SIZE_XS))
        method_info.pack(side="left", padx=S.PAD_SM)
        
        def update_method_info(*args):
            m = method_var.get()
            target = target_mode_var.get()
            
            # Validate method with target mode - all ADB methods require emulator
            adb_methods = ("PostMessage", "ADB Tap", "ADB Sendevent A", "ADB Sendevent B", "ADB Minitouch")
            if m in adb_methods and target != "emulator":
                method_info.config(text="⚠️ Yêu cầu Target = Emulator (Worker)", fg=S.ACCENT_RED)
                return
            
            if m == "SetCursorPos":
                method_info.config(text="(Di chuyển chuột - dùng được cả Screen & Emulator)", fg=S.FG_MUTED)
            elif m == "PostMessage":
                method_info.config(text="(Không di chuyển - song song - chỉ Emulator)", fg=S.ACCENT_GREEN)
            elif m == "ADB Tap":
                method_info.config(text="(Auto - tự chọn method tốt nhất)", fg=S.ACCENT_GREEN)
        def save_method(*args):
            # Warn if workers are running
            if self._playback_running or any(self._worker_stop_events):
                from tkinter import messagebox
                result = messagebox.askyesno("⚠️ Warning", 
                    "Workers are currently running!\n\n"
                    "Changing Input Method during playback may cause:\n"
                    "• Inconsistent behavior\n"
                    "• Some workers use old method, others use new\n\n"
                    "Recommended: Stop workers first, then change.\n\n"
                    "Continue anyway?")
                if not result:
                    method_var.set(self._input_settings.get("click_method", "SetCursorPos"))
                    return
            
            self._input_settings["click_method"] = method_var.get()
            self._save_input_settings()
            update_method_info()
        
        method_var.trace_add("write", save_method)
        target_mode_var.trace_add("write", lambda *args: update_method_info())  # Update on target change
        update_method_info()  # Initial
        
        # Capture button - gets current worker hwnd for emulator mode
        def do_capture():
            hwnd = None
            if target_mode_var.get() == "emulator":
                # Only show emulator selection if workers exist
                if self.workers and any(w.hwnd for w in self.workers):
                    hwnd = self._get_emulator_hwnd_for_capture()
                else:
                    # No workers yet (Add dialog) - capture full screen
                    from tkinter import messagebox
                    messagebox.showinfo("💡 Tip", 
                        "Chưa có Worker nào chạy.\n"
                        "Capture sẽ chụp toàn màn hình.\n\n"
                        "Sau khi thêm action, nhớ Start Workers trước khi Play!")
                    hwnd = None  # Full screen capture
            self._capture_click_with_hold_target(x_var, y_var, hold_var, btn_var, hwnd, dialog)
        
        capture_btn = S.create_modern_button(pos_frame, "📍 Capture", do_capture, "accent", width=10)
        capture_btn.pack(side="left", padx=S.PAD_MD)
        
        # Status label for capture feedback
        status_label = tk.Label(parent, text="💡 Capture: Click vị trí cần thao tác", 
                               bg=S.BG_CARD, fg=S.FG_MUTED,
                               font=(S.FONT_FAMILY, S.FONT_SIZE_XS))
        status_label.pack(anchor="w", padx=S.PAD_MD)
        widgets["_status_label"] = status_label
        
        # Hint text
        def update_hint(*args):
            btn = btn_var.get()
            target = widgets.get("_target_var", tk.StringVar(value="Full Screen")).get()
            target_info = f" trong {target}" if target != "Full Screen" else ""
            if btn in ("hold_left", "hold_right"):
                status_label.config(text=f"💡 Capture: Click vị trí rồi GIỮ chuột{target_info}", fg=S.ACCENT_BLUE)
            else:
                status_label.config(text=f"💡 Capture: Click vị trí cần thao tác{target_info}", fg=S.FG_MUTED)
        
        btn_var.trace_add("write", update_hint)
        update_hint()  # Initial update
        
        # ============================================================
        # SCHEDULE CLICK SECTION (NEW FEATURE)
        # ============================================================
        # Outer container with border for visibility
        schedule_outer = tk.Frame(parent, bg=S.ACCENT_PURPLE, padx=2, pady=2)
        schedule_outer.pack(fill="x", padx=S.PAD_MD, pady=S.PAD_MD)
        
        schedule_container = tk.Frame(schedule_outer, bg=S.BG_CARD)
        schedule_container.pack(fill="x")
        
        # Title row
        schedule_title_frame = tk.Frame(schedule_container, bg=S.BG_CARD)
        schedule_title_frame.pack(fill="x", padx=S.PAD_SM, pady=(S.PAD_SM, S.PAD_XS))
        
        tk.Label(schedule_title_frame, text="⏰ SCHEDULE CLICK", 
                bg=S.BG_CARD, fg=S.ACCENT_PURPLE,
                font=(S.FONT_FAMILY, S.FONT_SIZE_SM, "bold")).pack(side="left")
        
        # Checkbox to enable schedule
        schedule_enabled_var = tk.BooleanVar(value=value.get("schedule_enabled", False))
        schedule_cb = tk.Checkbutton(schedule_title_frame, text="Enable", 
                                    variable=schedule_enabled_var,
                                    bg=S.BG_CARD, fg=S.ACCENT_GREEN, selectcolor=S.BG_INPUT,
                                    activebackground=S.BG_CARD, activeforeground=S.ACCENT_GREEN,
                                    font=(S.FONT_FAMILY, S.FONT_SIZE_SM))
        schedule_cb.pack(side="left", padx=S.PAD_MD)
        widgets["schedule_enabled"] = schedule_enabled_var
        
        # Current time display (always visible)
        current_time_label = tk.Label(schedule_title_frame, text="", bg=S.BG_CARD, fg=S.ACCENT_BLUE,
                                     font=(S.FONT_FAMILY, S.FONT_SIZE_SM, "bold"))
        current_time_label.pack(side="right", padx=S.PAD_SM)
        
        def update_current_time():
            """Update current time display"""
            import datetime
            now = datetime.datetime.now()
            current_time_label.config(text=f"🕐 NOW: {now.strftime('%H:%M:%S')}")
            # Schedule next update in 1 second
            try:
                if dialog and hasattr(dialog, 'winfo_exists') and dialog.winfo_exists():
                    dialog.after(1000, update_current_time)
            except:
                pass
        
        # Start time update loop immediately
        if dialog and hasattr(dialog, 'after'):
            update_current_time()
        
        # Time input row
        schedule_input_frame = tk.Frame(schedule_container, bg=S.BG_CARD)
        schedule_input_frame.pack(fill="x", padx=S.PAD_SM, pady=S.PAD_XS)
        
        tk.Label(schedule_input_frame, text="Set Time (24h):", bg=S.BG_CARD, fg=S.FG_SECONDARY,
                font=(S.FONT_FAMILY, S.FONT_SIZE_SM)).pack(side="left", padx=(0, S.PAD_SM))
        
        # Parse existing schedule time or default
        schedule_time_str = value.get("schedule_time", "23:59:59")
        time_parts = schedule_time_str.split(":")
        
        hour_var = tk.StringVar(value=time_parts[0] if len(time_parts) > 0 else "23")
        minute_var = tk.StringVar(value=time_parts[1] if len(time_parts) > 1 else "59")
        second_var = tk.StringVar(value=time_parts[2] if len(time_parts) > 2 else "59")
        
        # Hour input (00-23) - ALWAYS EDITABLE
        hour_entry = S.create_entry(schedule_input_frame, textvariable=hour_var, width=4)
        hour_entry.pack(side="left")
        tk.Label(schedule_input_frame, text=":", bg=S.BG_CARD, fg=S.FG_PRIMARY,
                font=(S.FONT_FAMILY, S.FONT_SIZE_MD, "bold")).pack(side="left")
        
        # Minute input (00-59) - ALWAYS EDITABLE
        minute_entry = S.create_entry(schedule_input_frame, textvariable=minute_var, width=4)
        minute_entry.pack(side="left")
        tk.Label(schedule_input_frame, text=":", bg=S.BG_CARD, fg=S.FG_PRIMARY,
                font=(S.FONT_FAMILY, S.FONT_SIZE_MD, "bold")).pack(side="left")
        
        # Second input (00-59) - ALWAYS EDITABLE
        second_entry = S.create_entry(schedule_input_frame, textvariable=second_var, width=4)
        second_entry.pack(side="left")
        
        widgets["schedule_hour"] = hour_var
        widgets["schedule_minute"] = minute_var
        widgets["schedule_second"] = second_var
        
        # Sync time button (NTP) - ALWAYS CLICKABLE
        def sync_time_online():
            """Sync time with NTP server"""
            import socket
            import struct
            import datetime
            
            try:
                # Use Google's NTP server
                ntp_server = "time.google.com"
                ntp_port = 123
                
                # NTP packet format
                client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                client.settimeout(5)
                
                # NTP request packet
                data = b'\x1b' + 47 * b'\0'
                client.sendto(data, (ntp_server, ntp_port))
                data, address = client.recvfrom(1024)
                
                # Parse NTP response
                t = struct.unpack('!12I', data)[10]
                t -= 2208988800  # Convert from NTP epoch to Unix epoch
                
                # Convert to local time
                synced_time = datetime.datetime.fromtimestamp(t)
                
                # Update time inputs
                hour_var.set(f"{synced_time.hour:02d}")
                minute_var.set(f"{synced_time.minute:02d}")
                second_var.set(f"{synced_time.second:02d}")
                
                # Show success message
                from tkinter import messagebox
                messagebox.showinfo("✅ Time Synced", 
                    f"Đã đồng bộ với {ntp_server}\n"
                    f"Giờ chuẩn: {synced_time.strftime('%H:%M:%S')}")
                
            except Exception as e:
                from tkinter import messagebox
                messagebox.showerror("❌ Sync Failed", 
                    f"Không thể đồng bộ với NTP server:\n{str(e)}\n\n"
                    f"Đang dùng giờ hệ thống.")
                
                # Fallback to system time
                now = datetime.datetime.now()
                hour_var.set(f"{now.hour:02d}")
                minute_var.set(f"{now.minute:02d}")
                second_var.set(f"{now.second:02d}")
        
        sync_btn = S.create_modern_button(schedule_input_frame, "🔄 Sync NTP", sync_time_online, "accent", width=10)
        sync_btn.pack(side="left", padx=S.PAD_MD)
        
        # Use system time button
        def use_system_time():
            import datetime
            now = datetime.datetime.now()
            hour_var.set(f"{now.hour:02d}")
            minute_var.set(f"{now.minute:02d}")
            second_var.set(f"{now.second:02d}")
        
        sys_time_btn = S.create_modern_button(schedule_input_frame, "💻 System Time", use_system_time, "secondary", width=12)
        sys_time_btn.pack(side="left", padx=S.PAD_XS)
        
        # Validation for time inputs
        def validate_time_input(var, max_val):
            """Validate hour/minute/second input"""
            def on_change(*args):
                val = var.get()
                # Remove non-digits
                val = ''.join(c for c in val if c.isdigit())
                # Limit to 2 digits
                if len(val) > 2:
                    val = val[:2]
                # Validate range
                if val and int(val) > max_val:
                    val = str(max_val)
                var.set(val)
            return on_change
        
        hour_var.trace_add("write", validate_time_input(hour_var, 23))
        minute_var.trace_add("write", validate_time_input(minute_var, 59))
        second_var.trace_add("write", validate_time_input(second_var, 59))
        
        # Info label
        schedule_info = tk.Label(schedule_container, 
                               text="💡 Tick 'Enable' để kích hoạt - Click sẽ chờ đến đúng giờ này mới thực hiện", 
                               bg=S.BG_CARD, fg=S.FG_MUTED,
                               font=(S.FONT_FAMILY, S.FONT_SIZE_XS))
        schedule_info.pack(anchor="w", padx=S.PAD_SM, pady=(0, S.PAD_SM))
    
    def _render_wait_action_config(self, parent, widgets, value):
        """Render Wait action config (per spec 5.2)"""
        ms_frame = tk.Frame(parent)
        ms_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(ms_frame, text="Milliseconds:", font=("Arial", 9)).pack(side="left", padx=(0, 5))
        ms_var = tk.IntVar(value=value.get("ms", 1000))
        tk.Entry(ms_frame, textvariable=ms_var, width=10).pack(side="left")
        widgets["ms"] = ms_var
        
        tk.Label(parent, text="(1000ms = 1 second)", fg="gray", font=("Arial", 8)).pack(anchor="w", padx=10)
    
    def _render_keypress_action_config(self, parent, widgets, value):
        """Render Key Press action config - bấm nút để capture phím"""
        key_frame = tk.Frame(parent)
        key_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(key_frame, text="Key:", font=("Arial", 9)).pack(side="left", padx=(0, 5))
        
        key_var = tk.StringVar(value=value.get("key", ""))
        key_entry = tk.Entry(key_frame, textvariable=key_var, width=15, state="readonly")
        key_entry.pack(side="left", padx=(0, 5))
        
        # Status label
        status_label = tk.Label(key_frame, text="", fg="blue", font=("Arial", 8))
        status_label.pack(side="left", padx=(5, 0))
        
        capture_active = [False]  # Use list to allow modification in nested function
        
        def start_capture():
            """Bắt đầu capture phím"""
            if capture_active[0]:
                return
            
            capture_active[0] = True
            status_label.config(text="⌨ Nhấn phím bất kỳ...", fg="red")
            capture_btn.config(text="...", state="disabled")
            
            # Bind keyboard capture
            def on_key_press(event):
                # Map keysym to key name
                keysym = event.keysym.lower()
                
                # Map special keys
                key_map = {
                    'return': 'enter',
                    'escape': 'esc',
                    'control_l': 'ctrl', 'control_r': 'ctrl',
                    'alt_l': 'alt', 'alt_r': 'alt',
                    'shift_l': 'shift', 'shift_r': 'shift',
                    'super_l': 'win', 'super_r': 'win',
                    'caps_lock': 'caps_lock',
                    'prior': 'page_up',
                    'next': 'page_down',
                    'kp_0': 'num0', 'kp_1': 'num1', 'kp_2': 'num2', 'kp_3': 'num3',
                    'kp_4': 'num4', 'kp_5': 'num5', 'kp_6': 'num6', 'kp_7': 'num7',
                    'kp_8': 'num8', 'kp_9': 'num9',
                    'kp_add': 'num_add', 'kp_subtract': 'num_subtract',
                    'kp_multiply': 'num_multiply', 'kp_divide': 'num_divide',
                    'kp_decimal': 'num_decimal', 'kp_enter': 'num_enter',
                }
                
                key_name = key_map.get(keysym, keysym)
                
                # Set value
                key_var.set(key_name)
                
                # Stop capture
                capture_active[0] = False
                status_label.config(text=f"✓ {key_name}", fg="green")
                capture_btn.config(text="🎯 Capture", state="normal")
                
                # Unbind
                parent.winfo_toplevel().unbind('<Key>')
                
                return "break"  # Prevent event propagation
            
            # Bind to dialog
            parent.winfo_toplevel().bind('<Key>', on_key_press)
        
        capture_btn = tk.Button(key_frame, text="🎯 Capture", command=start_capture,
                               bg="#2196F3", fg="white", font=("Arial", 8, "bold"))
        capture_btn.pack(side="left")
        
        widgets["key"] = key_var
        
        repeat_frame = tk.Frame(parent)
        repeat_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(repeat_frame, text="Repeat:", font=("Arial", 9)).pack(side="left", padx=(0, 5))
        repeat_var = tk.IntVar(value=value.get("repeat", 1))
        tk.Spinbox(repeat_frame, from_=1, to=100, textvariable=repeat_var, width=8).pack(side="left")
        widgets["repeat"] = repeat_var
        
        tk.Label(parent, text="Nhấn 'Capture' rồi bấm phím bất kỳ", fg="gray", font=("Arial", 8)).pack(anchor="w", padx=10)
    
    def _render_combokey_action_config(self, parent, widgets, value):
        """Render ComboKey action config - capture tổ hợp phím với pynput (chặn Alt+Tab)"""
        keys_frame = tk.Frame(parent)
        keys_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(keys_frame, text="Combo:", font=("Arial", 9)).pack(side="left", padx=(0, 5))
        
        keys = value.get("keys", [])
        keys_var = tk.StringVar(value="+".join(keys) if keys else "")
        keys_entry = tk.Entry(keys_frame, textvariable=keys_var, width=18, state="readonly")
        keys_entry.pack(side="left", padx=(0, 5))
        
        # Status label
        status_label = tk.Label(keys_frame, text="", fg="blue", font=("Arial", 8))
        status_label.pack(side="left", padx=(5, 0))
        
        capture_active = [False]
        captured_keys = [set()]  # Track currently pressed keys
        listener_ref = [None]  # Store listener reference
        stop_capture = [False]  # Flag to stop
        
        def start_capture():
            """Bắt đầu capture combo key với pynput suppress"""
            if capture_active[0]:
                return
            
            capture_active[0] = True
            stop_capture[0] = False
            captured_keys[0] = set()
            status_label.config(text="⌨ Nhấn tổ hợp phím...", fg="red")
            capture_btn.config(text="...", state="disabled")
            
            from pynput import keyboard
            
            # Map pynput keys to display names
            def get_key_name(key):
                key_map = {
                    keyboard.Key.ctrl_l: 'Ctrl', keyboard.Key.ctrl_r: 'Ctrl',
                    keyboard.Key.alt_l: 'Alt', keyboard.Key.alt_r: 'Alt',
                    keyboard.Key.alt_gr: 'Alt',
                    keyboard.Key.shift_l: 'Shift', keyboard.Key.shift_r: 'Shift',
                    keyboard.Key.cmd: 'Win', keyboard.Key.cmd_l: 'Win', keyboard.Key.cmd_r: 'Win',
                    keyboard.Key.enter: 'Enter', keyboard.Key.esc: 'Esc',
                    keyboard.Key.tab: 'Tab', keyboard.Key.space: 'Space',
                    keyboard.Key.backspace: 'Backspace', keyboard.Key.delete: 'Delete',
                    keyboard.Key.insert: 'Insert',
                    keyboard.Key.home: 'Home', keyboard.Key.end: 'End',
                    keyboard.Key.page_up: 'PageUp', keyboard.Key.page_down: 'PageDown',
                    keyboard.Key.left: 'Left', keyboard.Key.right: 'Right',
                    keyboard.Key.up: 'Up', keyboard.Key.down: 'Down',
                    keyboard.Key.caps_lock: 'CapsLock',
                    keyboard.Key.f1: 'F1', keyboard.Key.f2: 'F2', keyboard.Key.f3: 'F3',
                    keyboard.Key.f4: 'F4', keyboard.Key.f5: 'F5', keyboard.Key.f6: 'F6',
                    keyboard.Key.f7: 'F7', keyboard.Key.f8: 'F8', keyboard.Key.f9: 'F9',
                    keyboard.Key.f10: 'F10', keyboard.Key.f11: 'F11', keyboard.Key.f12: 'F12',
                }
                if key in key_map:
                    return key_map[key]
                if hasattr(key, 'char') and key.char:
                    return key.char.upper()
                if hasattr(key, 'vk'):
                    vk = key.vk
                    if 65 <= vk <= 90:  # A-Z
                        return chr(vk)
                    if 48 <= vk <= 57:  # 0-9
                        return chr(vk)
                return str(key).replace('Key.', '').capitalize()
            
            def on_press(key):
                if stop_capture[0]:
                    return False  # Stop listener
                
                key_name = get_key_name(key)
                captured_keys[0].add(key_name)
                
                # Update display in main thread
                def update_ui():
                    if not capture_active[0]:
                        return
                    current = "+".join(sorted(captured_keys[0], key=lambda x: (
                        0 if x == 'Ctrl' else
                        1 if x == 'Alt' else
                        2 if x == 'Shift' else
                        3 if x == 'Win' else 4, x
                    )))
                    status_label.config(text=f"⌨ {current}...", fg="orange")
                parent.after(0, update_ui)
                
                # Don't return False here! That stops the listener
                # suppress=True already blocks the key from system
            
            def on_release(key):
                if stop_capture[0]:
                    return False
                
                # Finish capture on any key release
                if captured_keys[0]:
                    ordered = sorted(captured_keys[0], key=lambda x: (
                        0 if x == 'Ctrl' else
                        1 if x == 'Alt' else
                        2 if x == 'Shift' else
                        3 if x == 'Win' else 4, x
                    ))
                    result = "+".join(ordered)
                    
                    def finish_capture():
                        keys_var.set(result)
                        status_label.config(text=f"✓ {result}", fg="green")
                        capture_active[0] = False
                        capture_btn.config(text="🎯 Capture", state="normal")
                    
                    parent.after(0, finish_capture)
                    stop_capture[0] = True
                    return False  # Stop listener ONLY after capture complete
            
            # Start listener with suppress=True to block Alt+Tab etc
            listener_ref[0] = keyboard.Listener(
                on_press=on_press,
                on_release=on_release,
                suppress=True  # Block keys from reaching system!
            )
            listener_ref[0].start()
        
        capture_btn = tk.Button(keys_frame, text="🎯 Capture", command=start_capture,
                               bg="#2196F3", fg="white", font=("Arial", 8, "bold"))
        capture_btn.pack(side="left")
        
        widgets["keys"] = keys_var
        
        order_frame = tk.Frame(parent)
        order_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(order_frame, text="Order:", font=("Arial", 9)).pack(side="left", padx=(0, 5))
        order_var = tk.StringVar(value=value.get("order", "simultaneous"))
        ttk.Combobox(order_frame, textvariable=order_var, values=["simultaneous", "sequence"], 
                    state="readonly", width=12).pack(side="left")
        widgets["order"] = order_var
        
        tk.Label(parent, text="Nhấn 'Capture' rồi bấm tổ hợp phím (hỗ trợ Alt+Tab!)", fg="gray", font=("Arial", 8)).pack(anchor="w", padx=10)
    
    def _render_wheel_action_config(self, parent, widgets, value, is_worker_context=False, dialog=None):
        """Render Wheel action config (per spec B3 - V2 improved)"""
        S = ModernStyle
        parent.configure(bg=S.BG_CARD)
        
        # Target dropdown (Screen/Emulator)
        target_mode_var = self._create_target_dropdown(parent, widgets, value, S, is_worker_context)
        
        # Direction
        dir_frame = tk.Frame(parent, bg=S.BG_CARD)
        dir_frame.pack(fill="x", padx=S.PAD_MD, pady=S.PAD_SM)
        tk.Label(dir_frame, text="Direction:", bg=S.BG_CARD, fg=S.FG_SECONDARY,
                font=(S.FONT_FAMILY, S.FONT_SIZE_SM)).pack(side="left", padx=(0, S.PAD_SM))
        dir_var = tk.StringVar(value=value.get("direction", "up"))
        ttk.Combobox(dir_frame, textvariable=dir_var, values=["up", "down"], 
                    state="readonly", width=8).pack(side="left")
        widgets["direction"] = dir_var
        
        # Amount (số lần scroll)
        amount_frame = tk.Frame(parent, bg=S.BG_CARD)
        amount_frame.pack(fill="x", padx=S.PAD_MD, pady=S.PAD_SM)
        tk.Label(amount_frame, text="Amount:", bg=S.BG_CARD, fg=S.FG_SECONDARY,
                font=(S.FONT_FAMILY, S.FONT_SIZE_SM)).pack(side="left", padx=(0, S.PAD_SM))
        amount_var = tk.IntVar(value=value.get("amount", 3))
        S.create_entry(amount_frame, textvariable=amount_var, width=6).pack(side="left")
        tk.Label(amount_frame, text="(số lần scroll)", bg=S.BG_CARD, fg=S.FG_MUTED,
                font=(S.FONT_FAMILY, S.FONT_SIZE_XS)).pack(side="left", padx=S.PAD_SM)
        widgets["amount"] = amount_var
        
        # Speed (delay giữa các tick)
        speed_frame = tk.Frame(parent, bg=S.BG_CARD)
        speed_frame.pack(fill="x", padx=S.PAD_MD, pady=S.PAD_SM)
        tk.Label(speed_frame, text="Speed (ms):", bg=S.BG_CARD, fg=S.FG_SECONDARY,
                font=(S.FONT_FAMILY, S.FONT_SIZE_SM)).pack(side="left", padx=(0, S.PAD_SM))
        speed_var = tk.IntVar(value=value.get("speed", 50))
        S.create_entry(speed_frame, textvariable=speed_var, width=6).pack(side="left")
        tk.Label(speed_frame, text="(delay giữa mỗi tick)", bg=S.BG_CARD, fg=S.FG_MUTED,
                font=(S.FONT_FAMILY, S.FONT_SIZE_XS)).pack(side="left", padx=S.PAD_SM)
        widgets["speed"] = speed_var
        
        # Position
        pos_frame = tk.Frame(parent, bg=S.BG_CARD)
        pos_frame.pack(fill="x", padx=S.PAD_MD, pady=S.PAD_SM)
        
        # Checkbox: Use current mouse position
        use_current_var = tk.BooleanVar(value=value.get("use_current_pos", False))
        use_current_cb = tk.Checkbutton(pos_frame, text="🎯 Use current position", 
                                        variable=use_current_var,
                                        bg=S.BG_CARD, fg=S.ACCENT_BLUE, selectcolor=S.BG_INPUT,
                                        activebackground=S.BG_CARD, activeforeground=S.ACCENT_BLUE,
                                        font=(S.FONT_FAMILY, S.FONT_SIZE_SM))
        use_current_cb.pack(side="left", padx=(0, S.PAD_SM))
        widgets["use_current_pos"] = use_current_var
        
        x_var = tk.IntVar(value=value.get("x", 0))
        y_var = tk.IntVar(value=value.get("y", 0))
        
        coords_frame = tk.Frame(pos_frame, bg=S.BG_CARD)
        coords_frame.pack(side="left")
        
        tk.Label(coords_frame, text="X:", bg=S.BG_CARD, fg=S.FG_SECONDARY,
                font=(S.FONT_FAMILY, S.FONT_SIZE_SM)).pack(side="left")
        x_entry = S.create_entry(coords_frame, textvariable=x_var, width=8)
        x_entry.pack(side="left", padx=2)
        tk.Label(coords_frame, text="Y:", bg=S.BG_CARD, fg=S.FG_SECONDARY,
                font=(S.FONT_FAMILY, S.FONT_SIZE_SM)).pack(side="left", padx=(S.PAD_MD, 0))
        y_entry = S.create_entry(coords_frame, textvariable=y_var, width=8)
        y_entry.pack(side="left", padx=2)
        widgets["x"] = x_var
        widgets["y"] = y_var
        
        # Toggle coordinate entries
        def toggle_coords(*args):
            state = "disabled" if use_current_var.get() else "normal"
            x_entry.config(state=state)
            y_entry.config(state=state)
        
        use_current_var.trace_add("write", toggle_coords)
        toggle_coords()
        
        # Capture button with target support
        def do_capture():
            hwnd = None
            if target_mode_var.get() == "emulator":
                hwnd = self._get_emulator_hwnd_for_capture()
            self._capture_position_target(x_var, y_var, hwnd, dialog)
        
        S.create_modern_button(pos_frame, "📍", do_capture, "accent", width=3).pack(side="left", padx=S.PAD_SM)
    
    def _render_text_action_config(self, parent, widgets, value):
        """Render Text action config"""
        text_frame = tk.Frame(parent)
        text_frame.pack(fill="both", expand=True, padx=10, pady=5)
        tk.Label(text_frame, text="Text:", font=("Arial", 9)).pack(anchor="w")
        text_widget = tk.Text(text_frame, height=4, font=("Arial", 9))
        text_widget.pack(fill="both", expand=True, pady=5)
        text_widget.insert("1.0", value.get("text", ""))
        widgets["text"] = text_widget
        
        mode_frame = tk.Frame(parent)
        mode_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(mode_frame, text="Mode:", font=("Arial", 9)).pack(side="left", padx=(0, 5))
        mode_var = tk.StringVar(value=value.get("mode", "paste"))
        mode_combo = ttk.Combobox(mode_frame, textvariable=mode_var, values=["paste", "humanize"], 
                    state="readonly", width=10)
        mode_combo.pack(side="left")
        widgets["mode"] = mode_var
        
        # Speed frame for humanize mode
        speed_frame = tk.Frame(parent)
        speed_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(speed_frame, text="Speed (ms/char):", font=("Arial", 9)).pack(side="left", padx=(0, 5))
        speed_var = tk.IntVar(value=value.get("speed_ms", 100))
        speed_entry = tk.Entry(speed_frame, textvariable=speed_var, width=8)
        speed_entry.pack(side="left")
        widgets["speed_ms"] = speed_var
        
        # Info labels
        info_label = tk.Label(parent, text="", font=("Arial", 8), fg="gray")
        info_label.pack(anchor="w", padx=10, pady=5)
        
        def update_info(*args):
            if mode_var.get() == "paste":
                info_label.config(text="💡 Paste: Copy to clipboard then Ctrl+V (fast)")
                speed_entry.config(state="disabled")
            else:
                info_label.config(text="💡 Humanize: Type each character with delays (natural)")
                speed_entry.config(state="normal")
        
        mode_combo.bind("<<ComboboxSelected>>", update_info)
        update_info()
    
    def _get_action_value_from_widgets(self, action_type: str, widgets: dict) -> dict:
        """Extract action value from config widgets"""
        # Helper to get target_mode if present (screen/emulator)
        def get_target_mode():
            if "target_mode" in widgets:
                return widgets["target_mode"].get()
            return "screen"  # Default
        
        if action_type == "CLICK":
            result = {
                "button": widgets["button"].get(),
                "x": widgets["x"].get(),
                "y": widgets["y"].get(),
                "hold_ms": widgets["hold_ms"].get(),
                "use_current_pos": widgets.get("use_current_pos", tk.BooleanVar(value=False)).get()
            }
            mode = get_target_mode()
            if mode == "emulator":
                result["target_mode"] = "emulator"
            
            # Add schedule data if enabled
            if "schedule_enabled" in widgets:
                schedule_enabled = widgets["schedule_enabled"].get()
                if schedule_enabled:
                    hour = widgets["schedule_hour"].get().zfill(2)
                    minute = widgets["schedule_minute"].get().zfill(2)
                    second = widgets["schedule_second"].get().zfill(2)
                    result["schedule_enabled"] = True
                    result["schedule_time"] = f"{hour}:{minute}:{second}"
                else:
                    result["schedule_enabled"] = False
            
            return result
        elif action_type == "WAIT":
            return {"ms": widgets["ms"].get()}
        elif action_type == "KEY_PRESS":
            return {
                "key": widgets["key"].get(),
                "repeat": widgets["repeat"].get()
            }
        elif action_type == "COMBOKEY":
            keys_str = widgets["keys"].get()
            return {
                "keys": [k.strip() for k in keys_str.split("+") if k.strip()],
                "order": widgets["order"].get()
            }
        elif action_type == "WHEEL":
            result = {
                "direction": widgets["direction"].get(),
                "amount": widgets["amount"].get(),
                "speed": widgets["speed"].get(),
                "x": widgets["x"].get(),
                "y": widgets["y"].get(),
                "use_current_pos": widgets.get("use_current_pos", tk.BooleanVar(value=False)).get()
            }
            mode = get_target_mode()
            if mode == "emulator":
                result["target_mode"] = "emulator"
            return result
        elif action_type == "DRAG":
            result = {
                "button": widgets["button"].get(),
                "duration_ms": widgets["duration_ms"].get(),
                "x1": widgets["x1"].get(),
                "y1": widgets["y1"].get(),
                "x2": widgets["x2"].get(),
                "y2": widgets["y2"].get(),
                "use_current_start": widgets.get("use_current_start", tk.BooleanVar(value=False)).get()
            }
            mode = get_target_mode()
            if mode == "emulator":
                result["target_mode"] = "emulator"
            return result
        elif action_type == "TEXT":
            return {
                "text": widgets["text"].get("1.0", tk.END).strip(),
                "mode": widgets["mode"].get(),
                "speed_ms": widgets.get("speed_ms", tk.IntVar(value=100)).get()
            }
        # V2 Wait Actions
        elif action_type == "WAIT_TIME":
            return {
                "delay_ms": widgets["delay_ms"].get(),
                "variance_ms": widgets.get("variance_ms", tk.IntVar(value=0)).get()
            }
        elif action_type == "WAIT_PIXEL_COLOR":
            return {
                "x": widgets["x"].get(),
                "y": widgets["y"].get(),
                "expected_rgb": (widgets["r"].get(), widgets["g"].get(), widgets["b"].get()),
                "tolerance": widgets["tolerance"].get(),
                "timeout_ms": widgets["timeout_ms"].get()
            }
        elif action_type == "WAIT_SCREEN_CHANGE":
            return {
                "region": (widgets["x1"].get(), widgets["y1"].get(), 
                          widgets["x2"].get(), widgets["y2"].get()),
                "threshold": widgets["threshold"].get(),
                "timeout_ms": widgets["timeout_ms"].get(),
                # If Change Found options
                "mouse_action_enabled": widgets.get("mouse_action_enabled", tk.BooleanVar(value=False)).get(),
                "mouse_type": widgets.get("mouse_type", tk.StringVar(value="Positioning")).get(),
                "save_xy_enabled": widgets.get("save_xy_enabled", tk.BooleanVar(value=False)).get(),
                "save_x_var": widgets.get("save_x_var", tk.StringVar()).get(),
                "save_y_var": widgets.get("save_y_var", tk.StringVar()).get(),
                "goto_if_found": widgets.get("goto_if_found", tk.StringVar(value="Next")).get(),
                # No Change Found options
                "timeout_seconds": widgets.get("timeout_seconds", tk.IntVar(value=120)).get(),
                "goto_if_not_found": widgets.get("goto_if_not_found", tk.StringVar(value="End")).get(),
            }
        elif action_type == "WAIT_COLOR_DISAPPEAR":
            result = {
                "region": (widgets["x1"].get(), widgets["y1"].get(), 
                          widgets["x2"].get(), widgets["y2"].get()),
                "tolerance": widgets["tolerance"].get(),
                "disappear_threshold": widgets["disappear_threshold"].get() / 100.0,  # Convert % to decimal
                "timeout_ms": widgets["timeout_ms"].get(),
                "stable_count_exit": widgets.get("stable_count_exit", tk.IntVar(value=3)).get(),
                "sample_count": widgets.get("sample_count", tk.IntVar(value=5)).get(),
                "goto_if_found": widgets.get("goto_if_found", tk.StringVar(value="Next")).get(),
                "goto_if_not_found": widgets.get("goto_if_not_found", tk.StringVar(value="End")).get(),
                "auto_detect": widgets.get("auto_detect", tk.BooleanVar(value=False)).get(),
            }
            
            # Only include target_rgb if not auto-detect
            if not result["auto_detect"]:
                result["target_rgb"] = (widgets["r"].get(), widgets["g"].get(), widgets["b"].get())
            else:
                result["auto_detect_count"] = widgets.get("auto_detect_count", tk.IntVar(value=3)).get()
            
            return result
        elif action_type == "WAIT_COMBOKEY":
            return {
                "key_combo": widgets["key_combo"].get(),
                "timeout_ms": widgets["timeout_ms"].get()
            }
        elif action_type == "WAIT_FILE":
            return {
                "path": widgets["path"].get(),
                "condition": widgets["condition"].get(),
                "timeout_ms": widgets["timeout_ms"].get()
            }
        # V2 Image Actions
        elif action_type == "FIND_IMAGE":
            result = {
                "template_path": widgets["template_path"].get(),
                "threshold": widgets["threshold"].get(),
                "crop_region": widgets.get("crop_region", tk.StringVar()).get(),
                # If Found options
                "mouse_action_enabled": widgets.get("mouse_action_enabled", tk.BooleanVar(value=True)).get(),
                "mouse_type": widgets.get("mouse_type", tk.StringVar(value="Left click")).get(),
                "click_position": widgets.get("click_position", tk.StringVar(value="Centered")).get(),
                "save_xy_enabled": widgets.get("save_xy_enabled", tk.BooleanVar(value=False)).get(),
                "save_x_var": widgets.get("save_x_var", tk.StringVar(value="$foundX")).get(),
                "save_y_var": widgets.get("save_y_var", tk.StringVar(value="$foundY")).get(),
                "goto_if_found": widgets.get("goto_if_found", tk.StringVar(value="Next")).get(),
                "goto_found_label": widgets.get("goto_found_label", tk.StringVar()).get(),
                # Motion Guard options
                "motion_guard_enabled": widgets.get("motion_guard_enabled", tk.BooleanVar(value=False)).get(),
                "motion_threshold": widgets.get("motion_threshold", tk.DoubleVar(value=1.0)).get(),
                "motion_stable_count": widgets.get("motion_stable_count", tk.IntVar(value=5)).get(),
                "motion_timeout_ms": widgets.get("motion_timeout_ms", tk.IntVar(value=10000)).get(),
                "goto_motion_timeout": widgets.get("goto_motion_timeout", tk.StringVar(value="Next")).get(),
                # If Not Found options
                "retry_seconds": widgets.get("retry_seconds", tk.IntVar(value=30)).get(),
                "goto_if_not_found": widgets.get("goto_if_not_found", tk.StringVar(value="Next")).get(),
                "goto_notfound_label": widgets.get("goto_notfound_label", tk.StringVar()).get(),
                # ADB Tap options
                "adb_tap_hold_ms": widgets.get("adb_tap_hold_ms", tk.IntVar(value=100)).get(),
            }
            
            # Parse motion_region from string to list
            motion_region_str = widgets.get("motion_region", tk.StringVar()).get()
            if motion_region_str and motion_region_str.strip():
                try:
                    parts = [int(p.strip()) for p in motion_region_str.split(',')]
                    if len(parts) == 4:
                        result["motion_region"] = parts
                except:
                    pass  # Invalid format, skip
            
            return result
        elif action_type == "CAPTURE_IMAGE":
            return {
                "save_path": widgets["save_path"].get(),
                "region": (widgets["x1"].get(), widgets["y1"].get(),
                          widgets["x2"].get(), widgets["y2"].get()) if "x1" in widgets else None,
                "format": widgets.get("format", tk.StringVar(value="png")).get()
            }
        # V2 Flow Control
        elif action_type == "LABEL":
            return {"name": widgets["name"].get()}
        elif action_type == "GOTO":
            target = widgets["target"].get()
            custom = widgets.get("custom_target", tk.StringVar(value="")).get()
            # If custom target is set, use it instead
            if custom and custom.strip():
                target = f"→ {custom.strip()}"
            return {"target": target}
        elif action_type == "REPEAT":
            return {
                "count": widgets["count"].get(),
                "start_label": widgets.get("start_label", tk.StringVar(value="")).get(),
                "end_label": widgets.get("end_label", tk.StringVar(value="")).get()
            }
        elif action_type == "EMBED_MACRO":
            # Support both single macro and multi-select list
            selected_macros = widgets.get("_selected_macros", [])
            single_name = widgets["macro_name"].get() if widgets.get("macro_name") else ""
            
            # Use selected list if available, otherwise fall back to single
            if selected_macros:
                macro_names = list(selected_macros)
            elif single_name:
                macro_names = [single_name]
            else:
                macro_names = []
            
            return {
                "macro_name": macro_names[0] if macro_names else "",  # Backward compat
                "macro_names": macro_names,  # New: ordered list
                "continue_on_error": widgets.get("continue_on_error", tk.BooleanVar(value=True)).get(),
                "inherit_variables": widgets.get("inherit_variables", tk.BooleanVar(value=True)).get()
            }
        elif action_type == "GROUP":
            return {
                "name": widgets["name"].get(),
                "actions": widgets.get("_actions", [])  # Preserved from original
            }
        # Misc
        elif action_type == "COMMENT":
            return {"text": widgets["text"].get("1.0", tk.END).strip()}
        elif action_type == "SET_VARIABLE":
            return {
                "name": widgets["name"].get(),
                "value": widgets["value"].get()
            }
        return {}
    
    # ================= V2 CONFIG RENDERERS =================
    
    def _render_wait_time_config(self, parent, widgets, value):
        """Render WAIT_TIME config (spec B1-1)"""
        delay_frame = tk.Frame(parent)
        delay_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(delay_frame, text="Delay (ms):", font=("Arial", 9)).pack(side="left", padx=(0, 5))
        delay_var = tk.IntVar(value=value.get("delay_ms", 1000))
        tk.Entry(delay_frame, textvariable=delay_var, width=10).pack(side="left")
        widgets["delay_ms"] = delay_var
        
        variance_frame = tk.Frame(parent)
        variance_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(variance_frame, text="Variance ±(ms):", font=("Arial", 9)).pack(side="left", padx=(0, 5))
        variance_var = tk.IntVar(value=value.get("variance_ms", 0))
        tk.Entry(variance_frame, textvariable=variance_var, width=10).pack(side="left")
        widgets["variance_ms"] = variance_var
        
        tk.Label(parent, text="Actual delay = delay ± random(variance)", fg="gray", font=("Arial", 8)).pack(anchor="w", padx=10)
    
    def _render_wait_pixel_color_config(self, parent, widgets, value, dialog=None):
        """Render WAIT_PIXEL_COLOR config (spec B1-2)"""
        pos_frame = tk.Frame(parent)
        pos_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(pos_frame, text="Position:", font=("Arial", 9)).pack(side="left", padx=(0, 5))
        
        x_var = tk.IntVar(value=value.get("x", 0))
        y_var = tk.IntVar(value=value.get("y", 0))
        tk.Label(pos_frame, text="X:").pack(side="left")
        tk.Entry(pos_frame, textvariable=x_var, width=6).pack(side="left", padx=2)
        tk.Label(pos_frame, text="Y:").pack(side="left")
        tk.Entry(pos_frame, textvariable=y_var, width=6).pack(side="left", padx=2)
        widgets["x"] = x_var
        widgets["y"] = y_var
        
        tk.Button(pos_frame, text="📍", command=lambda: self._capture_position(x_var, y_var),
                 bg="#2196F3", fg="white", font=("Arial", 8)).pack(side="left", padx=5)
        
        color_frame = tk.Frame(parent)
        color_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(color_frame, text="Expected RGB:", font=("Arial", 9)).pack(side="left", padx=(0, 5))
        
        rgb = value.get("expected_rgb", (0, 0, 0))
        r_var = tk.IntVar(value=rgb[0] if isinstance(rgb, (list, tuple)) else 0)
        g_var = tk.IntVar(value=rgb[1] if isinstance(rgb, (list, tuple)) else 0)
        b_var = tk.IntVar(value=rgb[2] if isinstance(rgb, (list, tuple)) else 0)
        
        tk.Label(color_frame, text="R:").pack(side="left")
        tk.Entry(color_frame, textvariable=r_var, width=4).pack(side="left", padx=2)
        tk.Label(color_frame, text="G:").pack(side="left")
        tk.Entry(color_frame, textvariable=g_var, width=4).pack(side="left", padx=2)
        tk.Label(color_frame, text="B:").pack(side="left")
        tk.Entry(color_frame, textvariable=b_var, width=4).pack(side="left", padx=2)
        widgets["r"] = r_var
        widgets["g"] = g_var
        widgets["b"] = b_var
        
        tol_frame = tk.Frame(parent)
        tol_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(tol_frame, text="Tolerance:", font=("Arial", 9)).pack(side="left", padx=(0, 5))
        tol_var = tk.IntVar(value=value.get("tolerance", 10))
        tk.Entry(tol_frame, textvariable=tol_var, width=6).pack(side="left")
        widgets["tolerance"] = tol_var
        
        timeout_frame = tk.Frame(parent)
        timeout_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(timeout_frame, text="Timeout (ms):", font=("Arial", 9)).pack(side="left", padx=(0, 5))
        timeout_var = tk.IntVar(value=value.get("timeout_ms", 30000))
        tk.Entry(timeout_frame, textvariable=timeout_var, width=10).pack(side="left")
        widgets["timeout_ms"] = timeout_var
    
    def _render_wait_screen_change_config(self, parent, widgets, value, dialog=None):
        """Render WAIT_SCREEN_CHANGE config - Modern UI with If Change Found / No Change Found"""
        S = ModernStyle
        parent.configure(bg=S.BG_CARD)
        
        region = value.get("region", (0, 0, 100, 100))
        
        # ==================== MONITOR REGION ====================
        region_frame = tk.LabelFrame(parent, text=" 📐 Monitor Region ", 
                                     font=(S.FONT_FAMILY, S.FONT_SIZE_MD, "bold"),
                                     bg=S.BG_CARD, fg=S.FG_ACCENT,
                                     padx=S.PAD_MD, pady=S.PAD_SM)
        region_frame.pack(fill="x", padx=S.PAD_MD, pady=S.PAD_SM)
        
        # Info about search area
        target_name = getattr(self, '_capture_target_name', 'Full Screen')
        info_label = tk.Label(region_frame, 
                             text=f"🖥️ Search area: {target_name} (from Screen setting)",
                             font=(S.FONT_FAMILY, S.FONT_SIZE_SM),
                             bg=S.BG_CARD, fg=S.ACCENT_BLUE)
        info_label.pack(anchor="w", pady=(0, S.PAD_SM))
        
        # Region coords
        coords_row = tk.Frame(region_frame, bg=S.BG_CARD)
        coords_row.pack(fill="x", pady=2)
        
        x1_var = tk.IntVar(value=region[0] if len(region) > 0 else 0)
        y1_var = tk.IntVar(value=region[1] if len(region) > 1 else 0)
        x2_var = tk.IntVar(value=region[2] if len(region) > 2 else 100)
        y2_var = tk.IntVar(value=region[3] if len(region) > 3 else 100)
        
        tk.Label(coords_row, text="X1:", bg=S.BG_CARD, fg=S.FG_PRIMARY,
                font=(S.FONT_FAMILY, S.FONT_SIZE_SM)).pack(side="left")
        tk.Entry(coords_row, textvariable=x1_var, width=6, bg=S.BG_INPUT, fg=S.FG_PRIMARY,
                insertbackground=S.FG_PRIMARY, relief="flat").pack(side="left", padx=2)
        tk.Label(coords_row, text="Y1:", bg=S.BG_CARD, fg=S.FG_PRIMARY,
                font=(S.FONT_FAMILY, S.FONT_SIZE_SM)).pack(side="left", padx=(S.PAD_SM, 0))
        tk.Entry(coords_row, textvariable=y1_var, width=6, bg=S.BG_INPUT, fg=S.FG_PRIMARY,
                insertbackground=S.FG_PRIMARY, relief="flat").pack(side="left", padx=2)
        tk.Label(coords_row, text="X2:", bg=S.BG_CARD, fg=S.FG_PRIMARY,
                font=(S.FONT_FAMILY, S.FONT_SIZE_SM)).pack(side="left", padx=(S.PAD_SM, 0))
        tk.Entry(coords_row, textvariable=x2_var, width=6, bg=S.BG_INPUT, fg=S.FG_PRIMARY,
                insertbackground=S.FG_PRIMARY, relief="flat").pack(side="left", padx=2)
        tk.Label(coords_row, text="Y2:", bg=S.BG_CARD, fg=S.FG_PRIMARY,
                font=(S.FONT_FAMILY, S.FONT_SIZE_SM)).pack(side="left", padx=(S.PAD_SM, 0))
        tk.Entry(coords_row, textvariable=y2_var, width=6, bg=S.BG_INPUT, fg=S.FG_PRIMARY,
                insertbackground=S.FG_PRIMARY, relief="flat").pack(side="left", padx=2)
        
        # Capture region button - uses ADB screenshot for Android-native coords
        def capture_from_adb():
            """Capture region directly from ADB screenshot - returns Android coords"""
            # Auto-detect ADB device
            adb_serial = None
            try:
                import subprocess
                result = subprocess.run(["adb", "devices"], capture_output=True, text=True, timeout=2,
                                       creationflags=CREATE_NO_WINDOW if sys.platform == 'win32' else 0)
                if result.returncode == 0:
                    lines = result.stdout.strip().split('\n')
                    for line in lines[1:]:
                        parts = line.strip().split('\t')
                        if len(parts) >= 2 and parts[1] == 'device':
                            adb_serial = parts[0]
                            break
            except Exception as e:
                log(f"[CAPTURE] ADB check failed: {e}")
            
            if not adb_serial:
                from tkinter import messagebox
                messagebox.showwarning("Không có ADB", "Không tìm thấy thiết bị ADB nào.\nVui lòng khởi động giả lập trước.")
                return
            
            try:
                import subprocess
                from PIL import Image, ImageTk
                import io
                
                log(f"[CAPTURE] Getting ADB screenshot from {adb_serial}...")
                from utils.subprocess_helper import run_hidden
                p = run_hidden(
                    ["adb", "-s", adb_serial, "exec-out", "screencap", "-p"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=5
                )
                if p.returncode != 0 or not p.stdout:
                    log(f"[CAPTURE] ADB screenshot failed")
                    from tkinter import messagebox
                    messagebox.showerror("Lỗi", "Không thể chụp màn hình từ giả lập")
                    return
                
                img_buffer = io.BytesIO(p.stdout)
                img = Image.open(img_buffer)
                img_width, img_height = img.size
                
                # Create popup for cropping
                crop_popup = tk.Toplevel(dialog if dialog else self.root)
                crop_popup.title(f"📐 Chọn vùng giám sát ({img_width}x{img_height})")
                crop_popup.geometry(f"{min(img_width+20, 800)}x{min(img_height+80, 700)}")
                crop_popup.transient(dialog if dialog else self.root)
                crop_popup.grab_set()
                crop_popup.configure(bg=S.BG_PRIMARY)
                
                # Scale image if too large
                scale = 1.0
                max_display = 600
                if img_width > max_display or img_height > max_display:
                    scale = min(max_display / img_width, max_display / img_height)
                    display_img = img.resize((int(img_width * scale), int(img_height * scale)), Image.LANCZOS)
                else:
                    display_img = img
                
                tk_img = ImageTk.PhotoImage(display_img)
                canvas = tk.Canvas(crop_popup, width=display_img.width, height=display_img.height, 
                                  bg=S.BG_CARD, highlightthickness=0)
                canvas.pack(padx=10, pady=10)
                canvas.create_image(0, 0, anchor="nw", image=tk_img)
                canvas._img = tk_img
                
                selection = {"start_x": 0, "start_y": 0, "rect_id": None}
                
                def on_press(e):
                    selection["start_x"], selection["start_y"] = e.x, e.y
                    if selection["rect_id"]:
                        canvas.delete(selection["rect_id"])
                    selection["rect_id"] = canvas.create_rectangle(e.x, e.y, e.x, e.y, 
                                                                   outline="#00FF00", width=2)
                
                def on_drag(e):
                    if selection["rect_id"]:
                        canvas.coords(selection["rect_id"], selection["start_x"], selection["start_y"], e.x, e.y)
                
                def on_release(e):
                    # Get display coords and convert to Android (original image) coords
                    x1_disp = min(selection["start_x"], e.x)
                    y1_disp = min(selection["start_y"], e.y)
                    x2_disp = max(selection["start_x"], e.x)
                    y2_disp = max(selection["start_y"], e.y)
                    
                    # Scale back to original Android coords
                    ax1 = max(0, min(int(x1_disp / scale), img_width))
                    ay1 = max(0, min(int(y1_disp / scale), img_height))
                    ax2 = max(0, min(int(x2_disp / scale), img_width))
                    ay2 = max(0, min(int(y2_disp / scale), img_height))
                    
                    # Set vars with Android coords
                    x1_var.set(ax1)
                    y1_var.set(ay1)
                    x2_var.set(ax2)
                    y2_var.set(ay2)
                    
                    log(f"[CAPTURE] Android coords: ({ax1},{ay1})-({ax2},{ay2})")
                    crop_popup.destroy()
                
                canvas.bind("<Button-1>", on_press)
                canvas.bind("<B1-Motion>", on_drag)
                canvas.bind("<ButtonRelease-1>", on_release)
                
                # Info label
                tk.Label(crop_popup, 
                        text="🖱️ Kéo chuột để chọn vùng • Tọa độ = Android coords (di chuyển giả lập vẫn hoạt động)",
                        font=(S.FONT_FAMILY, S.FONT_SIZE_SM),
                        bg=S.BG_PRIMARY, fg=S.ACCENT_GREEN).pack(pady=(0, 10))
                
            except Exception as e:
                log(f"[CAPTURE] ADB capture failed: {e}")
                import traceback
                log(traceback.format_exc())
                from tkinter import messagebox
                messagebox.showerror("Lỗi", f"Capture thất bại: {e}")
        
        tk.Button(coords_row, text="📍 Capture từ Emulator", command=capture_from_adb,
                 bg=S.ACCENT_BLUE, fg=S.FG_PRIMARY, relief="flat", cursor="hand2",
                 font=(S.FONT_FAMILY, S.FONT_SIZE_SM)).pack(side="left", padx=S.PAD_MD)
        
        widgets["x1"] = x1_var
        widgets["y1"] = y1_var
        widgets["x2"] = x2_var
        widgets["y2"] = y2_var
        
        # Threshold
        thresh_row = tk.Frame(region_frame, bg=S.BG_CARD)
        thresh_row.pack(fill="x", pady=S.PAD_XS)
        tk.Label(thresh_row, text="Change threshold:", bg=S.BG_CARD, fg=S.FG_PRIMARY,
                font=(S.FONT_FAMILY, S.FONT_SIZE_SM)).pack(side="left")
        thresh_var = tk.DoubleVar(value=value.get("threshold", 0.05))
        tk.Entry(thresh_row, textvariable=thresh_var, width=8, bg=S.BG_INPUT, fg=S.FG_PRIMARY,
                insertbackground=S.FG_PRIMARY, relief="flat").pack(side="left", padx=S.PAD_SM)
        tk.Label(thresh_row, text="(0.0-1.0, lower = more sensitive)", bg=S.BG_CARD, fg=S.FG_MUTED,
                font=(S.FONT_FAMILY, S.FONT_SIZE_XS)).pack(side="left")
        widgets["threshold"] = thresh_var
        
        # ==================== IF CHANGE FOUND ====================
        found_frame = tk.LabelFrame(parent, text=" ✅ Nếu Thay Đổi Được Tìm Thấy ", 
                                    font=(S.FONT_FAMILY, S.FONT_SIZE_MD, "bold"),
                                    bg=S.BG_CARD, fg=S.ACCENT_GREEN,
                                    padx=S.PAD_MD, pady=S.PAD_MD)
        found_frame.pack(fill="x", padx=S.PAD_MD, pady=S.PAD_SM)
        
        # Mouse action row
        mouse_row = tk.Frame(found_frame, bg=S.BG_CARD)
        mouse_row.pack(fill="x", pady=2)
        
        mouse_action_var = tk.BooleanVar(value=value.get("mouse_action_enabled", False))
        tk.Checkbutton(mouse_row, text="Mouse action:", variable=mouse_action_var,
                      font=(S.FONT_FAMILY, S.FONT_SIZE_MD), bg=S.BG_CARD, fg=S.FG_PRIMARY,
                      selectcolor=S.BG_INPUT, activebackground=S.BG_CARD).pack(side="left")
        widgets["mouse_action_enabled"] = mouse_action_var
        
        mouse_type_var = tk.StringVar(value=value.get("mouse_type", "Positioning"))
        mouse_type_combo = ttk.Combobox(mouse_row, textvariable=mouse_type_var, width=12,
                                        values=["Positioning", "Left click", "Right click", 
                                               "Double click", "Middle click"],
                                        state="readonly")
        mouse_type_combo.pack(side="left", padx=3)
        widgets["mouse_type"] = mouse_type_var
        
        # Save coordinates row
        save_row = tk.Frame(found_frame, bg=S.BG_CARD)
        save_row.pack(fill="x", pady=2)
        
        save_xy_var = tk.BooleanVar(value=value.get("save_xy_enabled", False))
        tk.Checkbutton(save_row, text="Save X to:", variable=save_xy_var,
                      font=(S.FONT_FAMILY, S.FONT_SIZE_MD), bg=S.BG_CARD, fg=S.FG_PRIMARY,
                      selectcolor=S.BG_INPUT, activebackground=S.BG_CARD).pack(side="left")
        widgets["save_xy_enabled"] = save_xy_var
        
        # Variable dropdowns for X and Y
        var_list = ["$changeX", "$changeY", "$foundX", "$foundY", "$customVar"]
        
        save_x_var = tk.StringVar(value=value.get("save_x_var", ""))
        save_x_combo = ttk.Combobox(save_row, textvariable=save_x_var, width=12, values=var_list)
        save_x_combo.pack(side="left", padx=3)
        widgets["save_x_var"] = save_x_var
        
        tk.Label(save_row, text="and Y to:", bg=S.BG_CARD, fg=S.FG_PRIMARY,
                font=(S.FONT_FAMILY, S.FONT_SIZE_MD)).pack(side="left", padx=(S.PAD_SM, 0))
        
        save_y_var = tk.StringVar(value=value.get("save_y_var", ""))
        save_y_combo = ttk.Combobox(save_row, textvariable=save_y_var, width=12, values=var_list)
        save_y_combo.pack(side="left", padx=3)
        widgets["save_y_var"] = save_y_var
        
        # Go to row
        goto_found_row = tk.Frame(found_frame, bg=S.BG_CARD)
        goto_found_row.pack(fill="x", pady=2)
        
        tk.Label(goto_found_row, text="Go to", bg=S.BG_CARD, fg=S.FG_PRIMARY,
                font=(S.FONT_FAMILY, S.FONT_SIZE_MD)).pack(side="left")
        
        # Function to get all labels from current actions
        def get_label_list():
            labels = ["Next", "Previous", "Start", "End", "Exit macro"]
            for action in self.actions:
                label_name = ""
                if action.action == "LABEL":
                    if isinstance(action.value, dict):
                        label_name = action.value.get("name", "")
                if not label_name and action.label:
                    label_name = action.label
                if label_name and f"→ {label_name}" not in labels:
                    labels.append(f"→ {label_name}")
            return labels
        
        goto_found_var = tk.StringVar(value=value.get("goto_if_found", "Next"))
        goto_found_combo = ttk.Combobox(goto_found_row, textvariable=goto_found_var, width=25,
                                        values=get_label_list(), state="readonly")
        goto_found_combo.pack(side="left", padx=S.PAD_SM)
        widgets["goto_if_found"] = goto_found_var
        
        # Refresh labels when dropdown opens
        goto_found_combo.bind("<Button-1>", lambda e: goto_found_combo.configure(values=get_label_list()))
        
        # ==================== NO CHANGE FOUND ====================
        notfound_frame = tk.LabelFrame(parent, text=" ❌ No Change Found ", 
                                       font=(S.FONT_FAMILY, S.FONT_SIZE_MD, "bold"),
                                       bg=S.BG_CARD, fg=S.ACCENT_RED,
                                       padx=S.PAD_MD, pady=S.PAD_MD)
        notfound_frame.pack(fill="x", padx=S.PAD_MD, pady=S.PAD_SM)
        
        # Continue waiting row
        wait_row = tk.Frame(notfound_frame, bg=S.BG_CARD)
        wait_row.pack(fill="x", pady=2)
        
        tk.Label(wait_row, text="Continue waiting", bg=S.BG_CARD, fg=S.FG_PRIMARY,
                font=(S.FONT_FAMILY, S.FONT_SIZE_MD)).pack(side="left")
        
        timeout_var = tk.IntVar(value=value.get("timeout_seconds", 120))
        timeout_entry = tk.Entry(wait_row, textvariable=timeout_var, width=6, 
                                bg=S.BG_INPUT, fg=S.FG_PRIMARY,
                                insertbackground=S.FG_PRIMARY, relief="flat")
        timeout_entry.pack(side="left", padx=S.PAD_SM)
        widgets["timeout_seconds"] = timeout_var
        
        # Also store as timeout_ms for compatibility
        timeout_ms_var = tk.IntVar(value=value.get("timeout_ms", 120000))
        widgets["timeout_ms"] = timeout_ms_var
        
        # Sync timeout_seconds to timeout_ms
        def on_timeout_change(*args):
            try:
                timeout_ms_var.set(timeout_var.get() * 1000)
            except:
                pass
        timeout_var.trace_add("write", on_timeout_change)
        
        tk.Label(wait_row, text="seconds and then", bg=S.BG_CARD, fg=S.FG_PRIMARY,
                font=(S.FONT_FAMILY, S.FONT_SIZE_MD)).pack(side="left")
        
        # Go to row
        goto_notfound_row = tk.Frame(notfound_frame, bg=S.BG_CARD)
        goto_notfound_row.pack(fill="x", pady=2)
        
        tk.Label(goto_notfound_row, text="Go to", bg=S.BG_CARD, fg=S.FG_PRIMARY,
                font=(S.FONT_FAMILY, S.FONT_SIZE_MD)).pack(side="left")
        
        goto_notfound_var = tk.StringVar(value=value.get("goto_if_not_found", "End"))
        goto_notfound_combo = ttk.Combobox(goto_notfound_row, textvariable=goto_notfound_var, width=25,
                                           values=get_label_list(), state="readonly")
        goto_notfound_combo.pack(side="left", padx=S.PAD_SM)
        widgets["goto_if_not_found"] = goto_notfound_var
        
        # Refresh labels when dropdown opens
        goto_notfound_combo.bind("<Button-1>", lambda e: goto_notfound_combo.configure(values=get_label_list()))
    
    def _render_wait_color_disappear_config(self, parent, widgets, value, dialog=None):
        """Render WAIT_COLOR_DISAPPEAR config - Wait until specific color disappears"""
        S = ModernStyle
        parent.configure(bg=S.BG_CARD)
        
        region = value.get("region", (0, 0, 100, 100))
        target_rgb = value.get("target_rgb", (255, 255, 255))
        
        # ==================== MONITOR REGION ====================
        region_frame = tk.LabelFrame(parent, text=" 📐 Monitor Region ", 
                                     font=(S.FONT_FAMILY, S.FONT_SIZE_MD, "bold"),
                                     bg=S.BG_CARD, fg=S.FG_ACCENT,
                                     padx=S.PAD_MD, pady=S.PAD_SM)
        region_frame.pack(fill="x", padx=S.PAD_MD, pady=S.PAD_SM)
        
        # Region coords
        coords_row = tk.Frame(region_frame, bg=S.BG_CARD)
        coords_row.pack(fill="x", pady=2)
        
        x1_var = tk.IntVar(value=region[0] if len(region) > 0 else 0)
        y1_var = tk.IntVar(value=region[1] if len(region) > 1 else 0)
        x2_var = tk.IntVar(value=region[2] if len(region) > 2 else 100)
        y2_var = tk.IntVar(value=region[3] if len(region) > 3 else 100)
        
        tk.Label(coords_row, text="X1:", bg=S.BG_CARD, fg=S.FG_PRIMARY,
                font=(S.FONT_FAMILY, S.FONT_SIZE_SM)).pack(side="left")
        tk.Entry(coords_row, textvariable=x1_var, width=6, bg=S.BG_INPUT, fg=S.FG_PRIMARY,
                insertbackground=S.FG_PRIMARY, relief="flat").pack(side="left", padx=2)
        tk.Label(coords_row, text="Y1:", bg=S.BG_CARD, fg=S.FG_PRIMARY,
                font=(S.FONT_FAMILY, S.FONT_SIZE_SM)).pack(side="left", padx=(S.PAD_SM, 0))
        tk.Entry(coords_row, textvariable=y1_var, width=6, bg=S.BG_INPUT, fg=S.FG_PRIMARY,
                insertbackground=S.FG_PRIMARY, relief="flat").pack(side="left", padx=2)
        tk.Label(coords_row, text="X2:", bg=S.BG_CARD, fg=S.FG_PRIMARY,
                font=(S.FONT_FAMILY, S.FONT_SIZE_SM)).pack(side="left", padx=(S.PAD_SM, 0))
        tk.Entry(coords_row, textvariable=x2_var, width=6, bg=S.BG_INPUT, fg=S.FG_PRIMARY,
                insertbackground=S.FG_PRIMARY, relief="flat").pack(side="left", padx=2)
        tk.Label(coords_row, text="Y2:", bg=S.BG_CARD, fg=S.FG_PRIMARY,
                font=(S.FONT_FAMILY, S.FONT_SIZE_SM)).pack(side="left", padx=(S.PAD_SM, 0))
        tk.Entry(coords_row, textvariable=y2_var, width=6, bg=S.BG_INPUT, fg=S.FG_PRIMARY,
                insertbackground=S.FG_PRIMARY, relief="flat").pack(side="left", padx=2)
        
        # Capture region button - uses ADB screenshot for Android-native coords
        def capture_from_adb():
            """Capture region directly from ADB screenshot - returns Android coords"""
            adb_serial = None
            try:
                import subprocess
                result = subprocess.run(["adb", "devices"], capture_output=True, text=True, timeout=2,
                                       creationflags=CREATE_NO_WINDOW if sys.platform == 'win32' else 0)
                if result.returncode == 0:
                    lines = result.stdout.strip().split('\n')
                    for line in lines[1:]:
                        parts = line.strip().split('\t')
                        if len(parts) >= 2 and parts[1] == 'device':
                            adb_serial = parts[0]
                            break
            except Exception as e:
                log(f"[CAPTURE] ADB check failed: {e}")
            
            if not adb_serial:
                from tkinter import messagebox
                messagebox.showwarning("Không có ADB", "Không tìm thấy thiết bị ADB nào.\nVui lòng khởi động giả lập trước.")
                return
            
            try:
                import subprocess
                from PIL import Image, ImageTk
                import io
                
                log(f"[CAPTURE] Getting ADB screenshot from {adb_serial}...")
                from utils.subprocess_helper import run_hidden
                p = run_hidden(
                    ["adb", "-s", adb_serial, "exec-out", "screencap", "-p"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=5
                )
                if p.returncode != 0 or not p.stdout:
                    log(f"[CAPTURE] ADB screenshot failed")
                    from tkinter import messagebox
                    messagebox.showerror("Lỗi", "Không thể chụp màn hình từ giả lập")
                    return
                
                img_buffer = io.BytesIO(p.stdout)
                img = Image.open(img_buffer)
                img_width, img_height = img.size
                
                crop_popup = tk.Toplevel(dialog if dialog else self.root)
                crop_popup.title(f"📐 Chọn vùng giám sát ({img_width}x{img_height})")
                crop_popup.geometry(f"{min(img_width+20, 800)}x{min(img_height+80, 700)}")
                crop_popup.transient(dialog if dialog else self.root)
                crop_popup.grab_set()
                crop_popup.configure(bg=S.BG_DARK)
                
                scale = 1.0
                max_display = 600
                if img_width > max_display or img_height > max_display:
                    scale = min(max_display / img_width, max_display / img_height)
                    display_img = img.resize((int(img_width * scale), int(img_height * scale)), Image.LANCZOS)
                else:
                    display_img = img
                
                tk_img = ImageTk.PhotoImage(display_img)
                canvas = tk.Canvas(crop_popup, width=display_img.width, height=display_img.height, 
                                  bg=S.BG_CARD, highlightthickness=0)
                canvas.pack(padx=10, pady=10)
                canvas.create_image(0, 0, anchor="nw", image=tk_img)
                canvas._img = tk_img
                
                selection = {"start_x": 0, "start_y": 0, "rect_id": None}
                
                def on_press(e):
                    selection["start_x"], selection["start_y"] = e.x, e.y
                    if selection["rect_id"]:
                        canvas.delete(selection["rect_id"])
                    selection["rect_id"] = canvas.create_rectangle(e.x, e.y, e.x, e.y, 
                                                                   outline="#00FF00", width=2)
                
                def on_drag(e):
                    if selection["rect_id"]:
                        canvas.coords(selection["rect_id"], selection["start_x"], selection["start_y"], e.x, e.y)
                
                def on_release(e):
                    x1_disp = min(selection["start_x"], e.x)
                    y1_disp = min(selection["start_y"], e.y)
                    x2_disp = max(selection["start_x"], e.x)
                    y2_disp = max(selection["start_y"], e.y)
                    
                    ax1 = max(0, min(int(x1_disp / scale), img_width))
                    ay1 = max(0, min(int(y1_disp / scale), img_height))
                    ax2 = max(0, min(int(x2_disp / scale), img_width))
                    ay2 = max(0, min(int(y2_disp / scale), img_height))
                    
                    x1_var.set(ax1)
                    y1_var.set(ay1)
                    x2_var.set(ax2)
                    y2_var.set(ay2)
                    
                    log(f"[CAPTURE] Android coords: ({ax1},{ay1})-({ax2},{ay2})")
                    crop_popup.destroy()
                
                canvas.bind("<Button-1>", on_press)
                canvas.bind("<B1-Motion>", on_drag)
                canvas.bind("<ButtonRelease-1>", on_release)
                
                tk.Label(crop_popup, 
                        text="🖱️ Kéo chuột để chọn vùng • Tọa độ = Android coords (di chuyển giả lập vẫn hoạt động)",
                        font=(S.FONT_FAMILY, S.FONT_SIZE_SM),
                        bg=S.BG_DARK, fg=S.ACCENT_GREEN).pack(pady=(0, 10))
                
            except Exception as e:
                log(f"[CAPTURE] ADB capture failed: {e}")
                import traceback
                log(traceback.format_exc())
                from tkinter import messagebox
                messagebox.showerror("Lỗi", f"Capture thất bại: {e}")
        
        tk.Button(coords_row, text="📍 Capture từ Emulator", command=capture_from_adb,
                 bg=S.ACCENT_BLUE, fg=S.FG_PRIMARY, relief="flat", cursor="hand2",
                 font=(S.FONT_FAMILY, S.FONT_SIZE_SM)).pack(side="left", padx=S.PAD_MD)
        
        widgets["x1"] = x1_var
        widgets["y1"] = y1_var
        widgets["x2"] = x2_var
        widgets["y2"] = y2_var
        
        # ==================== TARGET COLOR ====================
        color_frame = tk.LabelFrame(parent, text=" 🎨 Target Color (Spin Arc Color) ", 
                                    font=(S.FONT_FAMILY, S.FONT_SIZE_MD, "bold"),
                                    bg=S.BG_CARD, fg=S.FG_ACCENT,
                                    padx=S.PAD_MD, pady=S.PAD_MD)
        color_frame.pack(fill="x", padx=S.PAD_MD, pady=S.PAD_SM)
        
        # Auto-detect checkbox
        auto_detect_var = tk.BooleanVar(value=value.get("auto_detect", False))
        auto_detect_cb = tk.Checkbutton(color_frame, 
                                        text="🔍 Auto-detect colors from baseline (recommended for spin arc)",
                                        variable=auto_detect_var,
                                        font=(S.FONT_FAMILY, S.FONT_SIZE_MD, "bold"),
                                        bg=S.BG_CARD, fg=S.ACCENT_GREEN,
                                        selectcolor=S.BG_INPUT, activebackground=S.BG_CARD)
        auto_detect_cb.pack(anchor="w", pady=(0, S.PAD_SM))
        widgets["auto_detect"] = auto_detect_var
        
        # Auto-detect count
        auto_count_row = tk.Frame(color_frame, bg=S.BG_CARD)
        auto_count_row.pack(fill="x", pady=2)
        tk.Label(auto_count_row, text="  → Track top", bg=S.BG_CARD, fg=S.FG_PRIMARY,
                font=(S.FONT_FAMILY, S.FONT_SIZE_SM)).pack(side="left")
        auto_count_var = tk.IntVar(value=value.get("auto_detect_count", 3))
        tk.Spinbox(auto_count_row, from_=1, to=10, textvariable=auto_count_var, width=5,
                  bg=S.BG_INPUT, fg=S.FG_PRIMARY, relief="flat").pack(side="left", padx=S.PAD_SM)
        tk.Label(auto_count_row, text="colors", bg=S.BG_CARD, fg=S.FG_PRIMARY,
                font=(S.FONT_FAMILY, S.FONT_SIZE_SM)).pack(side="left")
        widgets["auto_detect_count"] = auto_count_var
        
        # Separator
        tk.Frame(color_frame, height=1, bg=S.FG_MUTED).pack(fill="x", pady=S.PAD_SM)
        
        # Manual mode label
        manual_label = tk.Label(color_frame, text="OR manually specify color:",
                               font=(S.FONT_FAMILY, S.FONT_SIZE_SM),
                               bg=S.BG_CARD, fg=S.FG_MUTED)
        manual_label.pack(anchor="w", pady=(S.PAD_SM, 2))
        
        # RGB inputs
        rgb_row = tk.Frame(color_frame, bg=S.BG_CARD)
        rgb_row.pack(fill="x", pady=2)
        
        r_var = tk.IntVar(value=target_rgb[0] if len(target_rgb) > 0 else 255)
        g_var = tk.IntVar(value=target_rgb[1] if len(target_rgb) > 1 else 255)
        b_var = tk.IntVar(value=target_rgb[2] if len(target_rgb) > 2 else 255)
        
        tk.Label(rgb_row, text="R:", bg=S.BG_CARD, fg="#FF5555",
                font=(S.FONT_FAMILY, S.FONT_SIZE_SM, "bold")).pack(side="left")
        r_entry = tk.Entry(rgb_row, textvariable=r_var, width=6, bg=S.BG_INPUT, fg=S.FG_PRIMARY,
                          insertbackground=S.FG_PRIMARY, relief="flat")
        r_entry.pack(side="left", padx=2)
        
        tk.Label(rgb_row, text="G:", bg=S.BG_CARD, fg="#55FF55",
                font=(S.FONT_FAMILY, S.FONT_SIZE_SM, "bold")).pack(side="left", padx=(S.PAD_SM, 0))
        g_entry = tk.Entry(rgb_row, textvariable=g_var, width=6, bg=S.BG_INPUT, fg=S.FG_PRIMARY,
                          insertbackground=S.FG_PRIMARY, relief="flat")
        g_entry.pack(side="left", padx=2)
        
        tk.Label(rgb_row, text="B:", bg=S.BG_CARD, fg="#5555FF",
                font=(S.FONT_FAMILY, S.FONT_SIZE_SM, "bold")).pack(side="left", padx=(S.PAD_SM, 0))
        b_entry = tk.Entry(rgb_row, textvariable=b_var, width=6, bg=S.BG_INPUT, fg=S.FG_PRIMARY,
                          insertbackground=S.FG_PRIMARY, relief="flat")
        b_entry.pack(side="left", padx=2)
        
        # Color preview
        color_preview = tk.Label(rgb_row, text="  ", width=4, relief="solid", bd=1)
        color_preview.pack(side="left", padx=S.PAD_SM)
        
        # Enable/disable RGB inputs based on auto_detect
        def toggle_rgb_inputs(*args):
            state = "disabled" if auto_detect_var.get() else "normal"
            r_entry.config(state=state)
            g_entry.config(state=state)
            b_entry.config(state=state)
            auto_count_row.pack(fill="x", pady=2) if auto_detect_var.get() else auto_count_row.pack_forget()
        
        auto_detect_var.trace_add("write", toggle_rgb_inputs)
        toggle_rgb_inputs()
        
        def update_preview(*args):
            try:
                r, g, b = r_var.get(), g_var.get(), b_var.get()
                color_preview.configure(bg=f"#{r:02x}{g:02x}{b:02x}")
            except:
                pass
        
        r_var.trace_add("write", update_preview)
        g_var.trace_add("write", update_preview)
        b_var.trace_add("write", update_preview)
        update_preview()
        
        widgets["r"] = r_var
        widgets["g"] = g_var
        widgets["b"] = b_var
        
        # Tolerance
        tol_row = tk.Frame(color_frame, bg=S.BG_CARD)
        tol_row.pack(fill="x", pady=S.PAD_XS)
        tk.Label(tol_row, text="Tolerance:", bg=S.BG_CARD, fg=S.FG_PRIMARY,
                font=(S.FONT_FAMILY, S.FONT_SIZE_SM)).pack(side="left")
        tol_var = tk.IntVar(value=value.get("tolerance", 30))
        tk.Entry(tol_row, textvariable=tol_var, width=6, bg=S.BG_INPUT, fg=S.FG_PRIMARY,
                insertbackground=S.FG_PRIMARY, relief="flat").pack(side="left", padx=S.PAD_SM)
        tk.Label(tol_row, text="(0-255, ±tolerance per RGB channel)", bg=S.BG_CARD, fg=S.FG_MUTED,
                font=(S.FONT_FAMILY, S.FONT_SIZE_XS)).pack(side="left")
        widgets["tolerance"] = tol_var
        
        # Disappear threshold
        thresh_row = tk.Frame(color_frame, bg=S.BG_CARD)
        thresh_row.pack(fill="x", pady=S.PAD_XS)
        tk.Label(thresh_row, text="Disappear at:", bg=S.BG_CARD, fg=S.FG_PRIMARY,
                font=(S.FONT_FAMILY, S.FONT_SIZE_SM)).pack(side="left")
        disappear_var = tk.DoubleVar(value=value.get("disappear_threshold", 0.01) * 100)  # Convert to %
        tk.Entry(thresh_row, textvariable=disappear_var, width=6, bg=S.BG_INPUT, fg=S.FG_PRIMARY,
                insertbackground=S.FG_PRIMARY, relief="flat").pack(side="left", padx=S.PAD_SM)
        tk.Label(thresh_row, text="% pixels remaining (e.g., 1.0 = <1%)", bg=S.BG_CARD, fg=S.FG_MUTED,
                font=(S.FONT_FAMILY, S.FONT_SIZE_XS)).pack(side="left")
        widgets["disappear_threshold"] = disappear_var
        
        # Stable count exit
        stable_row = tk.Frame(color_frame, bg=S.BG_CARD)
        stable_row.pack(fill="x", pady=S.PAD_XS)
        tk.Label(stable_row, text="Số lần lặp ổn định:", bg=S.BG_CARD, fg=S.FG_PRIMARY,
                font=(S.FONT_FAMILY, S.FONT_SIZE_SM)).pack(side="left")
        stable_count_var = tk.IntVar(value=value.get("stable_count_exit", 3))  # Default 3
        tk.Entry(stable_row, textvariable=stable_count_var, width=6, bg=S.BG_INPUT, fg=S.FG_PRIMARY,
                insertbackground=S.FG_PRIMARY, relief="flat").pack(side="left", padx=S.PAD_SM)
        tk.Label(stable_row, text="(3=thoát khi 3 lần check giống nhau)", bg=S.BG_CARD, fg=S.FG_MUTED,
                font=(S.FONT_FAMILY, S.FONT_SIZE_XS)).pack(side="left")
        widgets["stable_count_exit"] = stable_count_var
        
        # Sample count for auto-detect
        sample_row = tk.Frame(color_frame, bg=S.BG_CARD)
        sample_row.pack(fill="x", pady=S.PAD_XS)
        tk.Label(sample_row, text="Số mẫu phân tích:", bg=S.BG_CARD, fg=S.FG_PRIMARY,
                font=(S.FONT_FAMILY, S.FONT_SIZE_SM)).pack(side="left")
        sample_count_var = tk.IntVar(value=value.get("sample_count", 5))  # Default 5
        tk.Entry(sample_row, textvariable=sample_count_var, width=6, bg=S.BG_INPUT, fg=S.FG_PRIMARY,
                insertbackground=S.FG_PRIMARY, relief="flat").pack(side="left", padx=S.PAD_SM)
        tk.Label(sample_row, text="(5=lấy 5 mẫu để phát hiện màu động)", bg=S.BG_CARD, fg=S.FG_MUTED,
                font=(S.FONT_FAMILY, S.FONT_SIZE_XS)).pack(side="left")
        widgets["sample_count"] = sample_count_var
        
        # Info label
        info_label = tk.Label(color_frame, 
                             text="💡 Tự động: Theo dõi màu động (spin arc). Lặp ổn định: Thoát khi màn hình tĩnh.",
                             font=(S.FONT_FAMILY, S.FONT_SIZE_XS, "italic"),
                             bg=S.BG_CARD, fg=S.ACCENT_BLUE)
        info_label.pack(anchor="w", pady=(S.PAD_SM, 0))
        
        # ==================== TIMEOUT & GOTO ====================
        action_frame = tk.LabelFrame(parent, text=" ⚙️ Actions ", 
                                     font=(S.FONT_FAMILY, S.FONT_SIZE_MD, "bold"),
                                     bg=S.BG_CARD, fg=S.FG_ACCENT,
                                     padx=S.PAD_MD, pady=S.PAD_MD)
        action_frame.pack(fill="x", padx=S.PAD_MD, pady=S.PAD_SM)
        
        # Timeout
        timeout_row = tk.Frame(action_frame, bg=S.BG_CARD)
        timeout_row.pack(fill="x", pady=2)
        tk.Label(timeout_row, text="Timeout:", bg=S.BG_CARD, fg=S.FG_PRIMARY,
                font=(S.FONT_FAMILY, S.FONT_SIZE_SM)).pack(side="left")
        timeout_var = tk.IntVar(value=value.get("timeout_ms", 30000))
        tk.Entry(timeout_row, textvariable=timeout_var, width=8, bg=S.BG_INPUT, fg=S.FG_PRIMARY,
                insertbackground=S.FG_PRIMARY, relief="flat").pack(side="left", padx=S.PAD_SM)
        tk.Label(timeout_row, text="ms", bg=S.BG_CARD, fg=S.FG_MUTED,
                font=(S.FONT_FAMILY, S.FONT_SIZE_SM)).pack(side="left")
        widgets["timeout_ms"] = timeout_var
        
        # Function to get all labels
        def get_label_list():
            labels = ["Next", "Previous", "Start", "End", "Exit macro"]
            for action in self.actions:
                label_name = ""
                if action.action == "LABEL":
                    if isinstance(action.value, dict):
                        label_name = action.value.get("name", "")
                if not label_name and action.label:
                    label_name = action.label
                if label_name and f"→ {label_name}" not in labels:
                    labels.append(f"→ {label_name}")
            return labels
        
        # Go to if color disappeared
        goto_found_row = tk.Frame(action_frame, bg=S.BG_CARD)
        goto_found_row.pack(fill="x", pady=2)
        tk.Label(goto_found_row, text="✅ Nếu màu biến mất:", bg=S.BG_CARD, fg=S.ACCENT_GREEN,
                font=(S.FONT_FAMILY, S.FONT_SIZE_SM)).pack(side="left")
        goto_found_var = tk.StringVar(value=value.get("goto_if_found", "Next"))
        goto_found_combo = ttk.Combobox(goto_found_row, textvariable=goto_found_var, width=20,
                                        values=get_label_list(), state="readonly")
        goto_found_combo.pack(side="left", padx=S.PAD_SM)
        widgets["goto_if_found"] = goto_found_var
        goto_found_combo.bind("<Button-1>", lambda e: goto_found_combo.configure(values=get_label_list()))
        
        # Go to if timeout
        goto_notfound_row = tk.Frame(action_frame, bg=S.BG_CARD)
        goto_notfound_row.pack(fill="x", pady=2)
        tk.Label(goto_notfound_row, text="❌ If timeout:", bg=S.BG_CARD, fg=S.ACCENT_RED,
                font=(S.FONT_FAMILY, S.FONT_SIZE_SM)).pack(side="left")
        goto_notfound_var = tk.StringVar(value=value.get("goto_if_not_found", "End"))
        goto_notfound_combo = ttk.Combobox(goto_notfound_row, textvariable=goto_notfound_var, width=20,
                                           values=get_label_list(), state="readonly")
        goto_notfound_combo.pack(side="left", padx=S.PAD_SM)
        widgets["goto_if_not_found"] = goto_notfound_var
        goto_notfound_combo.bind("<Button-1>", lambda e: goto_notfound_combo.configure(values=get_label_list()))
    
    def _render_wait_combokey_config(self, parent, widgets, value):
        """Render WAIT_COMBOKEY config (spec B1-4)"""
        key_frame = tk.Frame(parent)
        key_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(key_frame, text="Key combo:", font=("Arial", 9)).pack(side="left", padx=(0, 5))
        key_var = tk.StringVar(value=value.get("key_combo", "F5"))
        tk.Entry(key_frame, textvariable=key_var, width=20).pack(side="left")
        widgets["key_combo"] = key_var
        
        tk.Label(parent, text="Examples: F5, ctrl+c, ctrl+shift+a", fg="gray", font=("Arial", 8)).pack(anchor="w", padx=10)
        
        timeout_frame = tk.Frame(parent)
        timeout_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(timeout_frame, text="Timeout (ms):", font=("Arial", 9)).pack(side="left", padx=(0, 5))
        timeout_var = tk.IntVar(value=value.get("timeout_ms", 0))
        tk.Entry(timeout_frame, textvariable=timeout_var, width=10).pack(side="left")
        tk.Label(timeout_frame, text="(0 = no timeout)", fg="gray").pack(side="left", padx=5)
        widgets["timeout_ms"] = timeout_var
    
    def _render_wait_file_config(self, parent, widgets, value):
        """Render WAIT_FILE config (spec B1-5)"""
        path_frame = tk.Frame(parent)
        path_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(path_frame, text="File path:", font=("Arial", 9)).pack(side="left", padx=(0, 5))
        path_var = tk.StringVar(value=value.get("path", ""))
        tk.Entry(path_frame, textvariable=path_var, width=30).pack(side="left")
        widgets["path"] = path_var
        
        def browse_file():
            from tkinter import filedialog
            fp = filedialog.askopenfilename()
            if fp:
                path_var.set(fp)
        tk.Button(path_frame, text="...", command=browse_file).pack(side="left", padx=5)
        
        cond_frame = tk.Frame(parent)
        cond_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(cond_frame, text="Condition:", font=("Arial", 9)).pack(side="left", padx=(0, 5))
        cond_var = tk.StringVar(value=value.get("condition", "exists"))
        ttk.Combobox(cond_frame, textvariable=cond_var, 
                    values=["exists", "not_exists", "modified"],
                    state="readonly", width=12).pack(side="left")
        widgets["condition"] = cond_var
        
        timeout_frame = tk.Frame(parent)
        timeout_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(timeout_frame, text="Timeout (ms):", font=("Arial", 9)).pack(side="left", padx=(0, 5))
        timeout_var = tk.IntVar(value=value.get("timeout_ms", 30000))
        tk.Entry(timeout_frame, textvariable=timeout_var, width=10).pack(side="left")
        widgets["timeout_ms"] = timeout_var
    
    def _render_find_image_config(self, parent, widgets, value, dialog=None):
        """Render FIND_IMAGE config - Modern dark UI with proper color tolerance"""
        from PIL import Image, ImageTk
        import os
        
        # Use ModernStyle
        S = ModernStyle
        parent.configure(bg=S.BG_CARD)
        
        # ==================== IMAGE SPECIFICATIONS ====================
        spec_frame = tk.LabelFrame(parent, text=" 🖼️ Image Specifications ", 
                                   font=(S.FONT_FAMILY, S.FONT_SIZE_MD, "bold"),
                                   bg=S.BG_CARD, fg=S.FG_ACCENT,
                                   padx=S.PAD_MD, pady=S.PAD_MD)
        spec_frame.pack(fill="x", padx=S.PAD_MD, pady=(S.PAD_MD, S.PAD_SM))
        
        # Top row: Preview + Controls
        top_row = tk.Frame(spec_frame, bg=S.BG_CARD)
        top_row.pack(fill="x")
        
        # Left: Preview with border - compact size
        preview_frame = tk.Frame(top_row, bg=S.BORDER_COLOR, relief="flat")
        preview_frame.pack(side="left", padx=(0, S.PAD_MD))
        
        preview_container = tk.Frame(preview_frame, width=100, height=75, bg=S.BG_INPUT)
        preview_container.pack(padx=1, pady=1)
        preview_container.pack_propagate(False)
        
        preview_label = tk.Label(preview_container, text="No Image\n📷", bg=S.BG_INPUT, 
                                fg=S.FG_MUTED, font=(S.FONT_FAMILY, S.FONT_SIZE_SM))
        preview_label.pack(expand=True)
        
        # Buttons under preview
        btn_frame = tk.Frame(top_row, bg=S.BG_CARD)
        btn_frame.pack(side="left", anchor="n")
        
        # Path variable (hidden but needed)
        path_var = tk.StringVar(value=value.get("template_path", ""))
        widgets["template_path"] = path_var
        
        # Crop region variable 
        crop_region_var = tk.StringVar(value=value.get("crop_region", ""))
        widgets["crop_region"] = crop_region_var
        
        def update_preview():
            img_path = path_var.get()
            if img_path and os.path.exists(img_path):
                try:
                    img = Image.open(img_path)
                    orig_size = f"{img.width}x{img.height}"
                    img.thumbnail((95, 70))  # Smaller thumbnail
                    img_tk = ImageTk.PhotoImage(img)
                    preview_label.config(image=img_tk, text="")
                    preview_label.image = img_tk
                    size_label.config(text=f"{orig_size}")
                except Exception as e:
                    preview_label.config(text=f"Err", image="")
            else:
                preview_label.config(text="No Image\n📷", image="")
                size_label.config(text="--")
        
        def browse_image():
            from tkinter import filedialog
            fp = filedialog.askopenfilename(
                title="Chọn ảnh mẫu",
                filetypes=[("Images", "*.png *.jpg *.jpeg *.bmp"), ("All files", "*.*")]
            )
            if fp:
                path_var.set(fp)
                update_preview()
        
        def load_from_files():
            from tkinter import filedialog
            files_dir = os.path.join(os.getcwd(), "files")
            os.makedirs(files_dir, exist_ok=True)
            fp = filedialog.askopenfilename(
                title="Tải từ thư mục Files",
                initialdir=files_dir,
                filetypes=[("Images", "*.png *.jpg *.jpeg *.bmp"), ("All files", "*.*")]
            )
            if fp:
                path_var.set(fp)
                update_preview()
        
        def crop_screen():
            """Crop from screen/emulator"""
            from core.capture_utils import CaptureOverlay
            import ctypes
            
            # Safety: Force reset if a previous capture got stuck
            if CaptureOverlay._is_active:
                log("[UI] Warning: Previous capture was stuck, forcing reset")
                CaptureOverlay.force_reset()
            
            target_hwnd = getattr(self, '_capture_target_hwnd', None)
            target_name = getattr(self, '_capture_target_name', 'Screen (Full)')
            
            # Log current target for debugging
            if target_hwnd:
                log(f"[UI] Crop with target: {target_name} (hwnd={target_hwnd})")
            else:
                log("[UI] Crop with target: Full Screen (no constraints)")
            
            emu_bounds = None
            emu_resolution = None
            
            # Get bounds directly from hwnd using Windows API
            if target_hwnd:
                try:
                    user32 = ctypes.windll.user32
                    
                    class RECT(ctypes.Structure):
                        _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                                   ("right", ctypes.c_long), ("bottom", ctypes.c_long)]
                    
                    class POINT(ctypes.Structure):
                        _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
                    
                    rect = RECT()
                    user32.GetClientRect(target_hwnd, ctypes.byref(rect))
                    
                    pt = POINT(0, 0)
                    user32.ClientToScreen(target_hwnd, ctypes.byref(pt))
                    
                    client_w = rect.right - rect.left
                    client_h = rect.bottom - rect.top
                    
                    emu_bounds = (pt.x, pt.y, pt.x + client_w, pt.y + client_h)
                    
                    # Try to get resolution from worker if available
                    for w in self.workers:
                        if w.hwnd == target_hwnd:
                            emu_resolution = (w.res_width, w.res_height)
                            break
                    
                    # Fallback to client size as resolution
                    if not emu_resolution:
                        emu_resolution = (client_w, client_h)
                    
                    log(f"[UI] Crop target bounds: {emu_bounds}, resolution: {emu_resolution}")
                except Exception as e:
                    log(f"[UI] Failed to get hwnd bounds: {e}")
            
            def on_crop(result):
                if not result.success:
                    return
                
                # Helper to check if widget still exists
                def widget_exists(w):
                    try:
                        return w.winfo_exists()
                    except:
                        return False
                
                # Check if crop region is INSIDE emulator bounds
                # If yes → convert to local coords, if no → keep screen coords
                if target_hwnd and emu_bounds and emu_resolution:
                    emu_x, emu_y, emu_x2, emu_y2 = emu_bounds
                    
                    # Check if crop is inside emulator region
                    crop_inside = (result.x >= emu_x and result.y >= emu_y and 
                                   result.x2 <= emu_x2 and result.y2 <= emu_y2)
                    
                    if crop_inside:
                        # Convert screen coords to local emulator coords
                        res_w, res_h = emu_resolution
                        client_w = emu_x2 - emu_x
                        client_h = emu_y2 - emu_y
                        
                        # Screen coords - convert to local and scale to resolution
                        local_x1 = int((result.x - emu_x) * res_w / client_w) if client_w > 0 else 0
                        local_y1 = int((result.y - emu_y) * res_h / client_h) if client_h > 0 else 0
                        local_x2 = int((result.x2 - emu_x) * res_w / client_w) if client_w > 0 else 0
                        local_y2 = int((result.y2 - emu_y) * res_h / client_h) if client_h > 0 else 0
                        
                        # Clamp to valid range
                        local_x1 = max(0, min(res_w, local_x1))
                        local_y1 = max(0, min(res_h, local_y1))
                        local_x2 = max(0, min(res_w, local_x2))
                        local_y2 = max(0, min(res_h, local_y2))
                        
                        log(f"[UI] Crop INSIDE emulator: screen({result.x},{result.y})-({result.x2},{result.y2}) → local({local_x1},{local_y1})-({local_x2},{local_y2})")
                        
                        try:
                            crop_region_var.set(f"{local_x1},{local_y1},{local_x2},{local_y2}")
                            screen_info_var.set(f"📍 Local: ({local_x1},{local_y1})-({local_x2},{local_y2}) [{res_w}x{res_h}]")
                        except:
                            pass
                    else:
                        # Crop is outside emulator - keep screen coords
                        log(f"[UI] Crop OUTSIDE emulator: screen({result.x},{result.y})-({result.x2},{result.y2})")
                        try:
                            crop_region_var.set(f"{result.x},{result.y},{result.x2},{result.y2}")
                            screen_info_var.set(f"📍 Screen: ({result.x},{result.y})-({result.x2},{result.y2}) [FULL]")
                        except:
                            pass
                else:
                    # No target - just use screen coords
                    try:
                        crop_region_var.set(f"{result.x},{result.y},{result.x2},{result.y2}")
                        screen_info_var.set(f"📍 Screen: ({result.x},{result.y})-({result.x2},{result.y2})")
                    except:
                        pass
                
                if hasattr(result, 'img_path') and result.img_path:
                    try:
                        path_var.set(result.img_path)
                    except:
                        pass
                        
                if hasattr(result, 'pil_image') and result.pil_image:
                    try:
                        if widget_exists(preview_label):
                            img = result.pil_image.copy()
                            orig_size = f"{img.width}x{img.height}"
                            img.thumbnail((130, 95))
                            img_tk = ImageTk.PhotoImage(img)
                            preview_label.config(image=img_tk, text="")
                            preview_label.image = img_tk
                        if widget_exists(size_label):
                            size_label.config(text=f"Size: {orig_size}")
                    except Exception as e:
                        log(f"[UI] Preview update skipped: {e}")
            
            # ALWAYS full screen overlay - NO constrain bounds
            # User can crop anywhere, coords will be converted if within emulator
            overlay = CaptureOverlay(self.root, target_hwnd=None)  # No target = full screen
            log(f"[UI] Crop overlay: FULL SCREEN (target for coord conversion: {target_name})")
            overlay.capture_region(on_crop)
        
        # Action buttons - compact uniform style
        def create_img_btn(parent, text, cmd, color=None):
            bg = color or S.BTN_SECONDARY
            hover = S.BG_TERTIARY if not color else adjust_btn_color(color, 0.2)
            btn = tk.Button(parent, text=text, command=cmd, width=10,
                           bg=bg, fg=S.FG_PRIMARY, activebackground=hover,
                           activeforeground=S.FG_PRIMARY, relief="flat", cursor="hand2", bd=0,
                           font=(S.FONT_FAMILY, S.FONT_SIZE_XS), highlightthickness=0)
            def on_enter(e): btn.config(bg=hover)
            def on_leave(e): btn.config(bg=bg)
            btn.bind("<Enter>", on_enter)
            btn.bind("<Leave>", on_leave)
            return btn
        
        def adjust_btn_color(hex_color, factor):
            r, g, b = int(hex_color[1:3], 16), int(hex_color[3:5], 16), int(hex_color[5:7], 16)
            r = min(255, int(r + (255 - r) * factor))
            g = min(255, int(g + (255 - g) * factor))
            b = min(255, int(b + (255 - b) * factor))
            return f"#{r:02x}{g:02x}{b:02x}"
        
        btn_browse = create_img_btn(btn_frame, "📂 Browse", browse_image)
        btn_browse.pack(anchor="w", pady=1)
        
        btn_files = create_img_btn(btn_frame, "📁 Files", load_from_files)
        btn_files.pack(anchor="w", pady=1)
        
        btn_crop = create_img_btn(btn_frame, "✂️ Crop", crop_screen, S.ACCENT_BLUE)
        btn_crop.pack(anchor="w", pady=1)
        
        # Full Screen Crop button (ignore emulator bounds)
        def crop_fullscreen():
            """Crop from full screen (ignoring any target window)"""
            from core.capture_utils import CaptureOverlay
            
            if CaptureOverlay._is_active:
                log("[UI] Warning: Previous capture was stuck, forcing reset")
                CaptureOverlay.force_reset()
            
            def on_crop_fullscreen(result):
                if not result.success:
                    return
                
                # Screen coords - no conversion needed
                local_x1, local_y1 = result.x, result.y
                local_x2, local_y2 = result.x2, result.y2
                
                try:
                    crop_region_var.set(f"{local_x1},{local_y1},{local_x2},{local_y2}")
                    screen_info_var.set(f"📍 Region: ({local_x1},{local_y1})-({local_x2},{local_y2}) [SCREEN]")
                except:
                    pass
                
                if hasattr(result, 'img_path') and result.img_path:
                    try:
                        path_var.set(result.img_path)
                    except:
                        pass
                        
                if hasattr(result, 'pil_image') and result.pil_image:
                    try:
                        img = result.pil_image.copy()
                        orig_size = f"{img.width}x{img.height}"
                        img.thumbnail((130, 95))
                        img_tk = ImageTk.PhotoImage(img)
                        preview_label.config(image=img_tk, text="")
                        preview_label.image = img_tk
                        size_label.config(text=f"Size: {orig_size}")
                    except Exception as e:
                        log(f"[UI] Preview update skipped: {e}")
            
            # Capture full screen (no target_hwnd, no constrain_bounds)
            overlay = CaptureOverlay(self.root, target_hwnd=None)
            overlay.capture_region(on_crop_fullscreen)
        
        btn_fullscreen = create_img_btn(btn_frame, "📺 Screen", crop_fullscreen, S.ACCENT_PURPLE)
        btn_fullscreen.pack(anchor="w", pady=1)
        
        # Screen info
        target_name = getattr(self, '_capture_target_name', 'Screen (Full)')
        target_hwnd = getattr(self, '_capture_target_hwnd', None)
        if target_hwnd and self.workers:
            for w in self.workers:
                if w.hwnd == target_hwnd:
                    screen_text = f"🖥️ {target_name} ({w.res_width}x{w.res_height})"
                    break
            else:
                screen_text = f"🖥️ {target_name}"
        else:
            screen_text = "🖥️ Full Screen"
        
        screen_info_var = tk.StringVar(value=screen_text)
        tk.Label(btn_frame, textvariable=screen_info_var, font=(S.FONT_FAMILY, S.FONT_SIZE_SM), 
                fg=S.ACCENT_BLUE, bg=S.BG_CARD).pack(anchor="w", pady=(5, 0))
        
        # Size info
        size_label = tk.Label(btn_frame, text="Size: --", font=(S.FONT_FAMILY, S.FONT_SIZE_SM), 
                             fg=S.FG_MUTED, bg=S.BG_CARD)
        size_label.pack(anchor="w")
        
        # Right side: Threshold/Tolerance settings
        right_frame = tk.Frame(top_row, bg=S.BG_CARD)
        right_frame.pack(side="left", fill="both", expand=True, padx=(S.PAD_MD, 0))
        
        # === MATCHING THRESHOLD (using proper OpenCV threshold 0.0-1.0) ===
        thresh_section = tk.LabelFrame(right_frame, text=" 🎯 Ngưỡng Khớp ", 
                                       font=(S.FONT_FAMILY, S.FONT_SIZE_MD, "bold"),
                                       bg=S.BG_CARD, fg=S.FG_ACCENT,
                                       padx=S.PAD_MD, pady=S.PAD_SM)
        thresh_section.pack(fill="x", pady=(0, S.PAD_SM))
        
        # Threshold value display
        thresh_val = value.get("threshold", 0.8)
        thresh_var = tk.DoubleVar(value=thresh_val)
        widgets["threshold"] = thresh_var
        
        # Slider row
        slider_row = tk.Frame(thresh_section, bg=S.BG_CARD)
        slider_row.pack(fill="x")
        
        tk.Label(slider_row, text="Strict", font=(S.FONT_FAMILY, S.FONT_SIZE_SM), 
                fg=S.FG_MUTED, bg=S.BG_CARD).pack(side="left")
        
        thresh_slider = ttk.Scale(slider_row, from_=0.5, to=1.0, orient="horizontal",
                                  variable=thresh_var, length=150)
        thresh_slider.pack(side="left", padx=5, fill="x", expand=True)
        
        tk.Label(slider_row, text="Loose", font=(S.FONT_FAMILY, S.FONT_SIZE_SM), 
                fg=S.FG_MUTED, bg=S.BG_CARD).pack(side="left")
        
        # Value display and entry
        value_row = tk.Frame(thresh_section, bg=S.BG_CARD)
        value_row.pack(fill="x", pady=(S.PAD_SM, 0))
        
        tk.Label(value_row, text="Value:", font=(S.FONT_FAMILY, S.FONT_SIZE_MD), 
                fg=S.FG_PRIMARY, bg=S.BG_CARD).pack(side="left")
        thresh_entry = tk.Entry(value_row, textvariable=thresh_var, width=6, 
                               font=(S.FONT_FAMILY, S.FONT_SIZE_MD),
                               bg=S.BG_INPUT, fg=S.FG_PRIMARY, insertbackground=S.FG_PRIMARY,
                               relief="flat", highlightthickness=1, highlightbackground=S.BORDER_COLOR)
        thresh_entry.pack(side="left", padx=5)
        
        # Preset buttons
        def set_threshold(val):
            thresh_var.set(val)
        
        preset_frame = tk.Frame(value_row, bg=S.BG_CARD)
        preset_frame.pack(side="left", padx=S.PAD_MD)
        for label, val in [("Low", 0.6), ("Med", 0.75), ("High", 0.85), ("Exact", 0.95)]:
            btn = tk.Button(preset_frame, text=label, command=lambda v=val: set_threshold(v),
                           width=4, font=(S.FONT_FAMILY, S.FONT_SIZE_SM),
                           bg=S.BTN_SECONDARY, fg=S.FG_PRIMARY, relief="flat", cursor="hand2")
            btn.pack(side="left", padx=1)
        
        # Auto Set Threshold button - finds optimal threshold
        def auto_set_threshold():
            """Auto-detect best threshold using multiple OpenCV methods"""
            template_path = path_var.get()
            if not template_path or not os.path.exists(template_path):
                messagebox.showwarning("Set Threshold", "Please load a template image first.")
                return
            
            try:
                import cv2
                import numpy as np
                from PIL import ImageGrab
                
                # Capture current screen
                screen = ImageGrab.grab()
                screen_np = np.array(screen)
                screen_bgr = cv2.cvtColor(screen_np, cv2.COLOR_RGB2BGR)
                screen_gray = cv2.cvtColor(screen_bgr, cv2.COLOR_BGR2GRAY)
                
                # Load template
                template = cv2.imread(template_path)
                if template is None:
                    messagebox.showerror("Error", "Cannot read template image")
                    return
                template_gray = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
                
                h, w = template_gray.shape
                
                # Try multiple OpenCV matching methods for best result
                methods = [
                    (cv2.TM_CCOEFF_NORMED, "CCOEFF_NORMED", True),   # Higher is better
                    (cv2.TM_CCORR_NORMED, "CCORR_NORMED", True),     # Higher is better
                    (cv2.TM_SQDIFF_NORMED, "SQDIFF_NORMED", False),  # Lower is better
                ]
                
                best_confidence = 0
                best_method_name = ""
                best_loc = (0, 0)
                
                for method, name, higher_better in methods:
                    result = cv2.matchTemplate(screen_gray, template_gray, method)
                    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
                    
                    if higher_better:
                        conf = max_val
                        loc = max_loc
                    else:
                        conf = 1.0 - min_val  # Invert for comparison
                        loc = min_loc
                    
                    if conf > best_confidence:
                        best_confidence = conf
                        best_method_name = name
                        best_loc = loc
                
                if best_confidence < 0.3:
                    messagebox.showwarning("⚠️ No Match Found", 
                        f"Template not found on current screen.\n"
                        f"Best confidence: {best_confidence:.1%}\n\n"
                        f"Tips:\n"
                        f"• Make sure the target is visible on screen\n"
                        f"• Try cropping a smaller, unique area\n"
                        f"• Avoid areas with dynamic content")
                    return
                
                # Calculate optimal threshold (slightly below found confidence for safety margin)
                # Use 95% of detected confidence as safe threshold
                optimal_threshold = round(best_confidence * 0.95, 2)
                optimal_threshold = max(0.5, min(0.98, optimal_threshold))  # Clamp to valid range
                
                cx, cy = best_loc[0] + w//2, best_loc[1] + h//2
                
                # Ask user to apply
                result = messagebox.askyesno("🎯 Optimal Threshold Found!",
                    f"Analysis Results:\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"Best Match: {best_confidence:.1%}\n"
                    f"Method: {best_method_name}\n"
                    f"Position: ({cx}, {cy})\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"Recommended Threshold: {optimal_threshold}\n"
                    f"(5% safety margin from detected)\n\n"
                    f"Apply this threshold?")
                
                if result:
                    thresh_var.set(optimal_threshold)
                    messagebox.showinfo("✅ Threshold Set", 
                        f"Threshold set to {optimal_threshold}\n\n"
                        f"This should reliably match your template.")
                        
            except ImportError:
                messagebox.showerror("Error", "OpenCV not installed.\nRun: pip install opencv-python")
            except Exception as e:
                messagebox.showerror("Error", f"Auto-detect failed: {e}")
        
        tk.Button(value_row, text="🎯 Set", command=auto_set_threshold, 
                 font=(S.FONT_FAMILY, S.FONT_SIZE_SM), bg=S.ACCENT_ORANGE, fg=S.FG_PRIMARY,
                 relief="flat", cursor="hand2", width=6).pack(side="right")
        
        # Threshold explanation
        tk.Label(thresh_section, text="💡 Nhấn 'Set' để tự động xác định ngưỡng tối ưu từ màn hình",
                font=(S.FONT_FAMILY, S.FONT_SIZE_SM), fg=S.FG_MUTED, bg=S.BG_CARD).pack(anchor="w")
        
        # Initial preview
        if path_var.get() and os.path.exists(path_var.get()):
            update_preview()
        
        # ==================== IF IMAGE IS FOUND ====================
        found_frame = tk.LabelFrame(parent, text=" ✅ Nếu TÌM THẤY Ảnh ", 
                                    font=(S.FONT_FAMILY, S.FONT_SIZE_MD, "bold"),
                                    bg=S.BG_CARD, fg=S.ACCENT_GREEN,
                                    padx=S.PAD_MD, pady=S.PAD_MD)
        found_frame.pack(fill="x", padx=S.PAD_MD, pady=S.PAD_SM)
        
        # Mouse action row
        mouse_row = tk.Frame(found_frame, bg=S.BG_CARD)
        mouse_row.pack(fill="x", pady=2)
        
        mouse_action_var = tk.BooleanVar(value=value.get("mouse_action_enabled", True))
        tk.Checkbutton(mouse_row, text="Mouse action:", variable=mouse_action_var,
                      font=(S.FONT_FAMILY, S.FONT_SIZE_MD), bg=S.BG_CARD, fg=S.FG_PRIMARY,
                      selectcolor=S.BG_INPUT, activebackground=S.BG_CARD).pack(side="left")
        widgets["mouse_action_enabled"] = mouse_action_var
        
        # Mouse type
        mouse_type_var = tk.StringVar(value=value.get("mouse_type", "Left click"))
        mouse_type_combo = ttk.Combobox(mouse_row, textvariable=mouse_type_var, width=12,
                                        values=["Positioning", "Left click", "Right click", 
                                               "Double click", "Middle click"],
                                        state="readonly")
        mouse_type_combo.pack(side="left", padx=3)
        widgets["mouse_type"] = mouse_type_var
        
        # Position
        tk.Label(mouse_row, text="at", font=(S.FONT_FAMILY, S.FONT_SIZE_MD), 
                fg=S.FG_PRIMARY, bg=S.BG_CARD).pack(side="left", padx=3)
        position_var = tk.StringVar(value=value.get("click_position", "Centered"))
        position_combo = ttk.Combobox(mouse_row, textvariable=position_var, width=10,
                                      values=["Centered", "Top left", "Top right", 
                                             "Bottom left", "Bottom right", "Random"],
                                      state="readonly")
        position_combo.pack(side="left", padx=3)
        widgets["click_position"] = position_var
        
        # Input Method row (for parallel execution)
        input_method_row = tk.Frame(found_frame, bg=S.BG_CARD)
        input_method_row.pack(fill="x", pady=2)
        
        tk.Label(input_method_row, text="Input Method:", font=(S.FONT_FAMILY, S.FONT_SIZE_MD), 
                fg=S.FG_PRIMARY, bg=S.BG_CARD).pack(side="left")
        
        current_find_method = self._input_settings.get("find_image_click_method", "SetCursorPos")
        find_method_var = tk.StringVar(value=current_find_method)
        find_method_combo = ttk.Combobox(input_method_row, textvariable=find_method_var,
                                         values=["SetCursorPos", "PostMessage", "ADB Tap", "ADB Sendevent A", "ADB Sendevent B", "ADB Minitouch"],
                                         state="readonly", width=18)
        find_method_combo.pack(side="left", padx=5)
        
        # Info label
        find_method_info = tk.Label(input_method_row, text="", bg=S.BG_CARD, fg=S.FG_MUTED,
                                    font=(S.FONT_FAMILY, S.FONT_SIZE_XS))
        find_method_info.pack(side="left", padx=S.PAD_SM)
        
        def update_find_method_info(*args):
            m = find_method_var.get()
            if m == "SetCursorPos":
                find_method_info.config(text="(Di chuyển chuột)", fg=S.FG_MUTED)
            elif m == "PostMessage":
                find_method_info.config(text="(Không di chuyển - song song)", fg=S.ACCENT_GREEN)
            elif m == "ADB Tap":
                find_method_info.config(text="(Auto - tự chọn method)", fg=S.ACCENT_GREEN)
            elif m == "ADB Sendevent A":
                find_method_info.config(text="(Protocol A - BTN_TOUCH)", fg=S.ACCENT_CYAN)
            elif m == "ADB Sendevent B":
                find_method_info.config(text="(Protocol B - Slot)", fg=S.ACCENT_CYAN)
            elif m == "ADB Minitouch":
                find_method_info.config(text="(High-performance)", fg=S.ACCENT_PURPLE)
        
        def save_find_method(*args):
            # Warn if workers are running
            if self._playback_running or any(self._worker_stop_events):
                from tkinter import messagebox
                result = messagebox.askyesno("⚠️ Warning",
                    "Workers are currently running!\n\n"
                    "Changing Input Method during playback may cause inconsistent behavior.\n\n"
                    "Recommended: Stop workers first.\n\n"
                    "Continue anyway?")
                if not result:
                    find_method_var.set(self._input_settings.get("find_image_click_method", "SetCursorPos"))
                    return
            
            self._input_settings["find_image_click_method"] = find_method_var.get()
            self._save_input_settings()
            update_find_method_info()
            update_hold_ms_visibility()
        
        find_method_var.trace_add("write", save_find_method)
        update_find_method_info()  # Initial
        
        # ADB Tap Hold Duration row (only visible when ADB Tap selected)
        adb_hold_row = tk.Frame(found_frame, bg=S.BG_CARD)
        adb_hold_row.pack(fill="x", pady=2)
        
        tk.Label(adb_hold_row, text="Hold Duration (ms):", font=(S.FONT_FAMILY, S.FONT_SIZE_MD),
                fg=S.FG_PRIMARY, bg=S.BG_CARD).pack(side="left")
        
        adb_hold_ms_var = tk.IntVar(value=value.get("adb_tap_hold_ms", 100))
        adb_hold_ms_entry = tk.Entry(adb_hold_row, textvariable=adb_hold_ms_var, width=8,
                                     font=(S.FONT_FAMILY, S.FONT_SIZE_MD),
                                     bg=S.BG_INPUT, fg=S.FG_PRIMARY, insertbackground=S.FG_PRIMARY)
        adb_hold_ms_entry.pack(side="left", padx=5)
        widgets["adb_tap_hold_ms"] = adb_hold_ms_var
        
        tk.Label(adb_hold_row, text="(100 = normal tap, >200 = long press)", 
                font=(S.FONT_FAMILY, S.FONT_SIZE_XS), fg=S.FG_MUTED, bg=S.BG_CARD).pack(side="left", padx=5)
        
        def update_hold_ms_visibility():
            m = find_method_var.get()
            if m in ("ADB Tap", "ADB Sendevent A", "ADB Sendevent B", "ADB Minitouch"):
                adb_hold_row.pack(fill="x", pady=2)
            else:
                adb_hold_row.pack_forget()
        
        update_hold_ms_visibility()  # Initial
        
        # Save coordinates row
        save_row = tk.Frame(found_frame, bg=S.BG_CARD)
        save_row.pack(fill="x", pady=2)
        
        save_xy_var = tk.BooleanVar(value=value.get("save_xy_enabled", False))
        tk.Checkbutton(save_row, text="Save coordinates:", variable=save_xy_var,
                      font=(S.FONT_FAMILY, S.FONT_SIZE_MD), bg=S.BG_CARD, fg=S.FG_PRIMARY,
                      selectcolor=S.BG_INPUT, activebackground=S.BG_CARD).pack(side="left")
        widgets["save_xy_enabled"] = save_xy_var
        
        tk.Label(save_row, text="X →", font=(S.FONT_FAMILY, S.FONT_SIZE_MD), 
                fg=S.FG_PRIMARY, bg=S.BG_CARD).pack(side="left", padx=(10, 2))
        save_x_var = tk.StringVar(value=value.get("save_x_var", "$foundX"))
        save_x_entry = tk.Entry(save_row, textvariable=save_x_var, width=10, 
                               font=(S.FONT_FAMILY, S.FONT_SIZE_MD),
                               bg=S.BG_INPUT, fg=S.FG_PRIMARY, insertbackground=S.FG_PRIMARY,
                               relief="flat", highlightthickness=1, highlightbackground=S.BORDER_COLOR)
        save_x_entry.pack(side="left")
        widgets["save_x_var"] = save_x_var
        
        tk.Label(save_row, text="Y →", font=(S.FONT_FAMILY, S.FONT_SIZE_MD), 
                fg=S.FG_PRIMARY, bg=S.BG_CARD).pack(side="left", padx=(10, 2))
        save_y_var = tk.StringVar(value=value.get("save_y_var", "$foundY"))
        save_y_entry = tk.Entry(save_row, textvariable=save_y_var, width=10, 
                               font=(S.FONT_FAMILY, S.FONT_SIZE_MD),
                               bg=S.BG_INPUT, fg=S.FG_PRIMARY, insertbackground=S.FG_PRIMARY,
                               relief="flat", highlightthickness=1, highlightbackground=S.BORDER_COLOR)
        save_y_entry.pack(side="left")
        widgets["save_y_var"] = save_y_var
        
        # Go to row (with label support)
        goto_found_row = tk.Frame(found_frame, bg=S.BG_CARD)
        goto_found_row.pack(fill="x", pady=2)
        
        tk.Label(goto_found_row, text="Then go to:", font=(S.FONT_FAMILY, S.FONT_SIZE_MD), 
                fg=S.FG_PRIMARY, bg=S.BG_CARD).pack(side="left")
        
        # Function to get all labels from current actions
        # Includes: LABEL action names + any action with a non-empty label field
        def get_label_list():
            labels = ["Next", "Previous", "Start", "End", "Exit macro"]
            for action in self.actions:
                label_name = ""
                # Check LABEL action type
                if action.action == "LABEL":
                    if isinstance(action.value, dict):
                        label_name = action.value.get("name", "")
                # Also check the label field of ANY action (comment column)
                if not label_name and action.label:
                    label_name = action.label
                # Add to list if valid
                if label_name and f"→ {label_name}" not in labels:
                    labels.append(f"→ {label_name}")
            return labels
        
        goto_found_var = tk.StringVar(value=value.get("goto_if_found", "Next"))
        goto_found_combo = ttk.Combobox(goto_found_row, textvariable=goto_found_var, width=25,
                                        values=get_label_list(), state="readonly")
        goto_found_combo.pack(side="left", padx=5)
        widgets["goto_if_found"] = goto_found_var
        
        # Refresh labels when dropdown opens
        def on_combo_click(event):
            goto_found_combo['values'] = get_label_list()
        goto_found_combo.bind("<Button-1>", on_combo_click)
        
        # Custom label entry (for labels not yet created)
        tk.Label(goto_found_row, text="or label:", font=(S.FONT_FAMILY, S.FONT_SIZE_SM), 
                fg=S.FG_MUTED, bg=S.BG_CARD).pack(side="left", padx=(10, 2))
        goto_found_label_var = tk.StringVar(value=value.get("goto_found_label", ""))
        goto_found_label_entry = tk.Entry(goto_found_row, textvariable=goto_found_label_var, width=12, 
                font=(S.FONT_FAMILY, S.FONT_SIZE_SM),
                bg=S.BG_INPUT, fg=S.FG_PRIMARY, insertbackground=S.FG_PRIMARY,
                relief="flat", highlightthickness=1, highlightbackground=S.BORDER_COLOR)
        goto_found_label_entry.pack(side="left")
        widgets["goto_found_label"] = goto_found_label_var
        
        # Hidden compatibility var
        click_type_var = tk.StringVar(value=value.get("click_type", "left"))
        widgets["click_type"] = click_type_var
        
        # ==================== MOTION GUARD (NEW) ====================
        motion_frame = tk.LabelFrame(parent, text=" 🎭 Motion Guard (Wait for Motion to Stop) ", 
                                     font=(S.FONT_FAMILY, S.FONT_SIZE_MD, "bold"),
                                     bg=S.BG_CARD, fg=S.ACCENT_CYAN,
                                     padx=S.PAD_MD, pady=S.PAD_MD)
        motion_frame.pack(fill="x", padx=S.PAD_MD, pady=S.PAD_SM)
        
        # Enable motion guard
        motion_enabled_var = tk.BooleanVar(value=value.get("motion_guard_enabled", False))
        tk.Checkbutton(motion_frame, text="✓ Check motion before clicking (e.g., wait for spin arc to stop)",
                      variable=motion_enabled_var,
                      font=(S.FONT_FAMILY, S.FONT_SIZE_MD), bg=S.BG_CARD, fg=S.FG_PRIMARY,
                      selectcolor=S.BG_INPUT, activebackground=S.BG_CARD).pack(anchor="w", pady=2)
        widgets["motion_guard_enabled"] = motion_enabled_var
        
        # Motion region row
        motion_region_row = tk.Frame(motion_frame, bg=S.BG_CARD)
        motion_region_row.pack(fill="x", pady=2)
        
        tk.Label(motion_region_row, text="Motion region (x,y,x2,y2):", 
                font=(S.FONT_FAMILY, S.FONT_SIZE_MD), 
                fg=S.FG_PRIMARY, bg=S.BG_CARD).pack(side="left")
        
        motion_region_var = tk.StringVar(value=",".join(map(str, value.get("motion_region", []))) if value.get("motion_region") else "")
        motion_region_entry = tk.Entry(motion_region_row, textvariable=motion_region_var, width=25, 
                font=(S.FONT_FAMILY, S.FONT_SIZE_MD),
                bg=S.BG_INPUT, fg=S.FG_PRIMARY, insertbackground=S.FG_PRIMARY,
                relief="flat", highlightthickness=1, highlightbackground=S.BORDER_COLOR)
        motion_region_entry.pack(side="left", padx=5)
        widgets["motion_region"] = motion_region_var
        
        def crop_motion_region():
            """Crop motion check region from screen"""
            from core.capture_utils import CaptureOverlay
            import ctypes
            
            target_hwnd = getattr(self, '_capture_target_hwnd', None)
            emu_bounds = None
            
            if target_hwnd:
                try:
                    user32 = ctypes.windll.user32
                    class RECT(ctypes.Structure):
                        _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                                   ("right", ctypes.c_long), ("bottom", ctypes.c_long)]
                    class POINT(ctypes.Structure):
                        _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
                    
                    rect = RECT()
                    user32.GetClientRect(target_hwnd, ctypes.byref(rect))
                    pt = POINT(0, 0)
                    user32.ClientToScreen(target_hwnd, ctypes.byref(pt))
                    client_w = rect.right - rect.left
                    client_h = rect.bottom - rect.top
                    emu_bounds = (pt.x, pt.y, pt.x + client_w, pt.y + client_h)
                except Exception as e:
                    log(f"[UI] Failed to get hwnd bounds: {e}")
            
            def on_crop(result):
                if result.success:
                    motion_region_var.set(f"{result.x},{result.y},{result.x2},{result.y2}")
            
            # ALWAYS full screen overlay - NO constrain bounds
            overlay = CaptureOverlay(self.root, target_hwnd=None)
            overlay.capture_region(on_crop)
        
        tk.Button(motion_region_row, text="✂️ Crop", command=crop_motion_region,
                 font=(S.FONT_FAMILY, S.FONT_SIZE_SM), bg=S.ACCENT_BLUE, fg=S.FG_PRIMARY,
                 relief="flat", cursor="hand2", width=6).pack(side="left", padx=2)
        
        # Threshold and stable count row
        motion_params_row = tk.Frame(motion_frame, bg=S.BG_CARD)
        motion_params_row.pack(fill="x", pady=2)
        
        tk.Label(motion_params_row, text="Variance threshold (%):", 
                font=(S.FONT_FAMILY, S.FONT_SIZE_MD), 
                fg=S.FG_PRIMARY, bg=S.BG_CARD).pack(side="left")
        
        motion_threshold_var = tk.DoubleVar(value=value.get("motion_threshold", 1.0))
        motion_threshold_spinbox = tk.Spinbox(motion_params_row, from_=0.1, to=10.0, increment=0.1,
                                   textvariable=motion_threshold_var,
                                   width=5, font=(S.FONT_FAMILY, S.FONT_SIZE_MD),
                                   bg=S.BG_INPUT, fg=S.FG_PRIMARY, buttonbackground=S.BTN_SECONDARY,
                                   relief="flat", highlightthickness=1, highlightbackground=S.BORDER_COLOR)
        motion_threshold_spinbox.pack(side="left", padx=5)
        widgets["motion_threshold"] = motion_threshold_var
        
        tk.Label(motion_params_row, text="Stable count:", 
                font=(S.FONT_FAMILY, S.FONT_SIZE_MD), 
                fg=S.FG_PRIMARY, bg=S.BG_CARD).pack(side="left", padx=(15, 0))
        
        motion_stable_var = tk.IntVar(value=value.get("motion_stable_count", 5))
        motion_stable_spinbox = tk.Spinbox(motion_params_row, from_=1, to=50,
                                   textvariable=motion_stable_var,
                                   width=5, font=(S.FONT_FAMILY, S.FONT_SIZE_MD),
                                   bg=S.BG_INPUT, fg=S.FG_PRIMARY, buttonbackground=S.BTN_SECONDARY,
                                   relief="flat", highlightthickness=1, highlightbackground=S.BORDER_COLOR)
        motion_stable_spinbox.pack(side="left", padx=5)
        widgets["motion_stable_count"] = motion_stable_var
        
        tk.Label(motion_params_row, text="Timeout (ms):", 
                font=(S.FONT_FAMILY, S.FONT_SIZE_MD), 
                fg=S.FG_PRIMARY, bg=S.BG_CARD).pack(side="left", padx=(15, 0))
        
        motion_timeout_var = tk.IntVar(value=value.get("motion_timeout_ms", 10000))
        motion_timeout_spinbox = tk.Spinbox(motion_params_row, from_=1000, to=60000, increment=1000,
                                   textvariable=motion_timeout_var,
                                   width=7, font=(S.FONT_FAMILY, S.FONT_SIZE_MD),
                                   bg=S.BG_INPUT, fg=S.FG_PRIMARY, buttonbackground=S.BTN_SECONDARY,
                                   relief="flat", highlightthickness=1, highlightbackground=S.BORDER_COLOR)
        motion_timeout_spinbox.pack(side="left", padx=5)
        widgets["motion_timeout_ms"] = motion_timeout_var
        
        # Goto if motion timeout
        motion_goto_row = tk.Frame(motion_frame, bg=S.BG_CARD)
        motion_goto_row.pack(fill="x", pady=2)
        
        tk.Label(motion_goto_row, text="If motion timeout:", 
                font=(S.FONT_FAMILY, S.FONT_SIZE_MD), 
                fg=S.FG_PRIMARY, bg=S.BG_CARD).pack(side="left")
        
        motion_goto_var = tk.StringVar(value=value.get("goto_motion_timeout", "Next"))
        motion_goto_combo = ttk.Combobox(motion_goto_row, textvariable=motion_goto_var, width=20,
                                        values=get_label_list(), state="readonly")
        motion_goto_combo.pack(side="left", padx=5)
        widgets["goto_motion_timeout"] = motion_goto_var
        
        # Explanation
        tk.Label(motion_frame, text="💡 Motion guard uses variance detection to wait until animated content stops (e.g., spin arc, loading animation)",
                font=(S.FONT_FAMILY, S.FONT_SIZE_SM), fg=S.FG_MUTED, bg=S.BG_CARD, wraplength=700, justify="left").pack(anchor="w", pady=(5, 0))
        
        # ==================== IF IMAGE IS NOT FOUND ====================
        notfound_frame = tk.LabelFrame(parent, text=" ❌ Nếu KHÔNG TÌM THẤY Ảnh ", 
                                       font=(S.FONT_FAMILY, S.FONT_SIZE_MD, "bold"),
                                       bg=S.BG_CARD, fg=S.ACCENT_RED,
                                       padx=S.PAD_MD, pady=S.PAD_MD)
        notfound_frame.pack(fill="x", padx=S.PAD_MD, pady=S.PAD_SM)
        
        # Retry settings row
        retry_row = tk.Frame(notfound_frame, bg=S.BG_CARD)
        retry_row.pack(fill="x", pady=2)
        
        tk.Label(retry_row, text="Keep searching for", font=(S.FONT_FAMILY, S.FONT_SIZE_MD), 
                fg=S.FG_PRIMARY, bg=S.BG_CARD).pack(side="left")
        
        retry_seconds_var = tk.IntVar(value=value.get("retry_seconds", 30))
        retry_spinbox = tk.Spinbox(retry_row, from_=1, to=999, textvariable=retry_seconds_var,
                                   width=5, font=(S.FONT_FAMILY, S.FONT_SIZE_MD),
                                   bg=S.BG_INPUT, fg=S.FG_PRIMARY, buttonbackground=S.BTN_SECONDARY,
                                   relief="flat", highlightthickness=1, highlightbackground=S.BORDER_COLOR)
        retry_spinbox.pack(side="left", padx=5)
        widgets["retry_seconds"] = retry_seconds_var
        
        tk.Label(retry_row, text="seconds, then:", font=(S.FONT_FAMILY, S.FONT_SIZE_MD), 
                fg=S.FG_PRIMARY, bg=S.BG_CARD).pack(side="left")
        
        # Hidden compatibility vars
        retry_var = tk.BooleanVar(value=True)
        widgets["retry_enabled"] = retry_var
        max_retries_var = tk.IntVar(value=value.get("max_retries", 999))
        widgets["max_retries"] = max_retries_var
        timeout_var = tk.IntVar(value=value.get("timeout_ms", 5000))
        widgets["timeout_ms"] = timeout_var
        
        # Go to row (with label support)
        goto_notfound_row = tk.Frame(notfound_frame, bg=S.BG_CARD)
        goto_notfound_row.pack(fill="x", pady=2)
        
        tk.Label(goto_notfound_row, text="Go to:", font=(S.FONT_FAMILY, S.FONT_SIZE_MD), 
                fg=S.FG_PRIMARY, bg=S.BG_CARD).pack(side="left")
        
        goto_notfound_var = tk.StringVar(value=value.get("goto_if_not_found", "Next"))
        goto_notfound_combo = ttk.Combobox(goto_notfound_row, textvariable=goto_notfound_var, width=25,
                                           values=get_label_list(), state="readonly")
        goto_notfound_combo.pack(side="left", padx=5)
        widgets["goto_if_not_found"] = goto_notfound_var
        
        # Refresh labels when dropdown opens
        def on_notfound_combo_click(event):
            goto_notfound_combo['values'] = get_label_list()
        goto_notfound_combo.bind("<Button-1>", on_notfound_combo_click)
        
        # Custom label entry (for labels not yet created)
        tk.Label(goto_notfound_row, text="or label:", font=(S.FONT_FAMILY, S.FONT_SIZE_SM), 
                fg=S.FG_MUTED, bg=S.BG_CARD).pack(side="left", padx=(10, 2))
        goto_notfound_label_var = tk.StringVar(value=value.get("goto_notfound_label", ""))
        goto_notfound_label_entry = tk.Entry(goto_notfound_row, textvariable=goto_notfound_label_var, width=12, 
                font=(S.FONT_FAMILY, S.FONT_SIZE_SM),
                bg=S.BG_INPUT, fg=S.FG_PRIMARY, insertbackground=S.FG_PRIMARY,
                relief="flat", highlightthickness=1, highlightbackground=S.BORDER_COLOR)
        goto_notfound_label_entry.pack(side="left")
        widgets["goto_notfound_label"] = goto_notfound_label_var
    
    def _render_capture_image_config(self, parent, widgets, value, dialog=None):
        """Render CAPTURE_IMAGE config (spec B2-2) - Dark theme"""
        S = ModernStyle
        parent.configure(bg=S.BG_CARD)
        
        if not IMAGE_ACTIONS_AVAILABLE:
            tk.Label(parent, text="⚠ OpenCV not installed. Install with: pip install opencv-python",
                    fg=S.ACCENT_RED, bg=S.BG_CARD, font=(S.FONT_FAMILY, S.FONT_SIZE_MD)).pack(padx=10, pady=10)
        
        path_frame = tk.Frame(parent, bg=S.BG_CARD)
        path_frame.pack(fill="x", padx=S.PAD_MD, pady=S.PAD_SM)
        tk.Label(path_frame, text="Save path:", font=(S.FONT_FAMILY, S.FONT_SIZE_MD),
                fg=S.FG_PRIMARY, bg=S.BG_CARD).pack(side="left", padx=(0, 5))
        path_var = tk.StringVar(value=value.get("save_path", ""))
        tk.Entry(path_frame, textvariable=path_var, width=25,
                font=(S.FONT_FAMILY, S.FONT_SIZE_MD), bg=S.BG_INPUT, fg=S.FG_PRIMARY,
                insertbackground=S.FG_PRIMARY, relief="flat",
                highlightthickness=1, highlightbackground=S.BORDER_COLOR).pack(side="left")
        widgets["save_path"] = path_var
        
        def browse_save():
            from tkinter import filedialog
            fp = filedialog.asksaveasfilename(
                defaultextension=".png",
                filetypes=[("PNG", "*.png"), ("JPEG", "*.jpg"), ("BMP", "*.bmp")]
            )
            if fp:
                path_var.set(fp)
        tk.Button(path_frame, text="...", command=browse_save,
                 bg=S.BTN_SECONDARY, fg=S.FG_PRIMARY, relief="flat", cursor="hand2").pack(side="left", padx=5)
        
        tk.Label(parent, text="(Leave empty for auto-generated filename)", 
                fg=S.FG_MUTED, bg=S.BG_CARD, font=(S.FONT_FAMILY, S.FONT_SIZE_SM)).pack(anchor="w", padx=S.PAD_MD)
        
        format_frame = tk.Frame(parent, bg=S.BG_CARD)
        format_frame.pack(fill="x", padx=S.PAD_MD, pady=S.PAD_SM)
        tk.Label(format_frame, text="Format:", font=(S.FONT_FAMILY, S.FONT_SIZE_MD),
                fg=S.FG_PRIMARY, bg=S.BG_CARD).pack(side="left", padx=(0, 5))
        format_var = tk.StringVar(value=value.get("format", "png"))
        ttk.Combobox(format_frame, textvariable=format_var, 
                    values=["png", "jpg", "bmp"],
                    state="readonly", width=8).pack(side="left")
        widgets["format"] = format_var
        
        # Optional region
        region_frame = tk.LabelFrame(parent, text="Region (optional)", 
                                     font=(S.FONT_FAMILY, S.FONT_SIZE_MD, "bold"),
                                     bg=S.BG_CARD, fg=S.FG_ACCENT)
        region_frame.pack(fill="x", padx=S.PAD_MD, pady=S.PAD_SM)
        
        region = value.get("region", (0, 0, 0, 0)) or (0, 0, 0, 0)
        x1_var = tk.IntVar(value=region[0])
        y1_var = tk.IntVar(value=region[1])
        x2_var = tk.IntVar(value=region[2])
        y2_var = tk.IntVar(value=region[3])
        
        row = tk.Frame(region_frame, bg=S.BG_CARD)
        row.pack(fill="x", padx=5, pady=2)
        tk.Label(row, text="X1:", fg=S.FG_PRIMARY, bg=S.BG_CARD).pack(side="left")
        tk.Entry(row, textvariable=x1_var, width=5, bg=S.BG_INPUT, fg=S.FG_PRIMARY,
                relief="flat", highlightthickness=1, highlightbackground=S.BORDER_COLOR).pack(side="left", padx=2)
        tk.Label(row, text="Y1:", fg=S.FG_PRIMARY, bg=S.BG_CARD).pack(side="left")
        tk.Entry(row, textvariable=y1_var, width=5).pack(side="left", padx=2)
        tk.Label(row, text="X2:").pack(side="left")
        tk.Entry(row, textvariable=x2_var, width=5).pack(side="left", padx=2)
        tk.Label(row, text="Y2:").pack(side="left")
        tk.Entry(row, textvariable=y2_var, width=5).pack(side="left", padx=2)
        
        widgets["x1"] = x1_var
        widgets["y1"] = y1_var
        widgets["x2"] = x2_var
        widgets["y2"] = y2_var
    
    def _render_label_config(self, parent, widgets, value):
        """Render LABEL config - Modern UI"""
        S = ModernStyle
        parent.configure(bg=S.BG_CARD)
        
        # ==================== LABEL SETTINGS ====================
        label_frame = tk.LabelFrame(parent, text=" 🏷️ Label Settings ", 
                                    font=(S.FONT_FAMILY, S.FONT_SIZE_MD, "bold"),
                                    bg=S.BG_CARD, fg=S.FG_ACCENT,
                                    padx=S.PAD_MD, pady=S.PAD_MD)
        label_frame.pack(fill="x", padx=S.PAD_MD, pady=S.PAD_SM)
        
        # Label name
        name_row = tk.Frame(label_frame, bg=S.BG_CARD)
        name_row.pack(fill="x", pady=S.PAD_XS)
        
        tk.Label(name_row, text="Label name:", bg=S.BG_CARD, fg=S.FG_PRIMARY,
                font=(S.FONT_FAMILY, S.FONT_SIZE_MD)).pack(side="left")
        
        name_var = tk.StringVar(value=value.get("name", ""))
        name_entry = tk.Entry(name_row, textvariable=name_var, width=25,
                             bg=S.BG_INPUT, fg=S.FG_PRIMARY, insertbackground=S.FG_PRIMARY,
                             font=(S.FONT_FAMILY, S.FONT_SIZE_MD), relief="flat")
        name_entry.pack(side="left", padx=S.PAD_SM)
        widgets["name"] = name_var
        
        # Show existing labels for reference
        existing_labels = []
        for action in self.actions:
            if action.action == "LABEL":
                lbl_name = ""
                if isinstance(action.value, dict):
                    lbl_name = action.value.get("name", "")
                if not lbl_name and action.label:
                    lbl_name = action.label
                if lbl_name and lbl_name not in existing_labels:
                    existing_labels.append(lbl_name)
        
        if existing_labels:
            ref_frame = tk.Frame(label_frame, bg=S.BG_CARD)
            ref_frame.pack(fill="x", pady=(S.PAD_SM, 0))
            tk.Label(ref_frame, text="📋 Existing labels:", bg=S.BG_CARD, fg=S.FG_MUTED,
                    font=(S.FONT_FAMILY, S.FONT_SIZE_SM)).pack(side="left")
            tk.Label(ref_frame, text=", ".join(existing_labels), bg=S.BG_CARD, fg=S.ACCENT_CYAN,
                    font=(S.FONT_FAMILY, S.FONT_SIZE_SM)).pack(side="left", padx=S.PAD_XS)
        
        # Info
        tk.Label(label_frame, text="💡 Labels are markers for GOTO, REPEAT, and conditional jumps",
                bg=S.BG_CARD, fg=S.FG_MUTED,
                font=(S.FONT_FAMILY, S.FONT_SIZE_SM)).pack(anchor="w", pady=(S.PAD_SM, 0))
    
    def _render_goto_config(self, parent, widgets, value):
        """Render GOTO config - Modern UI with label dropdown"""
        S = ModernStyle
        parent.configure(bg=S.BG_CARD)
        
        # ==================== GOTO SETTINGS ====================
        goto_frame = tk.LabelFrame(parent, text=" 🔀 Go To Settings ", 
                                   font=(S.FONT_FAMILY, S.FONT_SIZE_MD, "bold"),
                                   bg=S.BG_CARD, fg=S.FG_ACCENT,
                                   padx=S.PAD_MD, pady=S.PAD_MD)
        goto_frame.pack(fill="x", padx=S.PAD_MD, pady=S.PAD_SM)
        
        # Function to get all labels
        def get_label_list():
            labels = ["Next", "Previous", "Start", "End", "Exit macro"]
            for action in self.actions:
                lbl_name = ""
                if action.action == "LABEL":
                    if isinstance(action.value, dict):
                        lbl_name = action.value.get("name", "")
                if not lbl_name and action.label:
                    lbl_name = action.label
                if lbl_name and f"→ {lbl_name}" not in labels:
                    labels.append(f"→ {lbl_name}")
            return labels
        
        # Target row
        target_row = tk.Frame(goto_frame, bg=S.BG_CARD)
        target_row.pack(fill="x", pady=S.PAD_XS)
        
        tk.Label(target_row, text="Jump to:", bg=S.BG_CARD, fg=S.FG_PRIMARY,
                font=(S.FONT_FAMILY, S.FONT_SIZE_MD)).pack(side="left")
        
        target_var = tk.StringVar(value=value.get("target", "Next"))
        target_combo = ttk.Combobox(target_row, textvariable=target_var, width=25,
                                    values=get_label_list(), state="readonly")
        target_combo.pack(side="left", padx=S.PAD_SM)
        widgets["target"] = target_var
        
        # Refresh labels when dropdown opens
        target_combo.bind("<Button-1>", lambda e: target_combo.configure(values=get_label_list()))
        
        # Custom label entry
        custom_row = tk.Frame(goto_frame, bg=S.BG_CARD)
        custom_row.pack(fill="x", pady=S.PAD_XS)
        
        tk.Label(custom_row, text="Or custom label:", bg=S.BG_CARD, fg=S.FG_MUTED,
                font=(S.FONT_FAMILY, S.FONT_SIZE_SM)).pack(side="left")
        
        custom_var = tk.StringVar(value=value.get("custom_target", ""))
        custom_entry = tk.Entry(custom_row, textvariable=custom_var, width=20,
                               bg=S.BG_INPUT, fg=S.FG_PRIMARY, insertbackground=S.FG_PRIMARY,
                               font=(S.FONT_FAMILY, S.FONT_SIZE_SM), relief="flat")
        custom_entry.pack(side="left", padx=S.PAD_SM)
        widgets["custom_target"] = custom_var
        
        # Info
        tk.Label(goto_frame, text="💡 Jump to a specific label or action position",
                bg=S.BG_CARD, fg=S.FG_MUTED,
                font=(S.FONT_FAMILY, S.FONT_SIZE_SM)).pack(anchor="w", pady=(S.PAD_SM, 0))
    
    def _render_repeat_config(self, parent, widgets, value):
        """Render REPEAT config - Modern UI with label dropdown"""
        S = ModernStyle
        parent.configure(bg=S.BG_CARD)
        
        # ==================== REPEAT SETTINGS ====================
        repeat_frame = tk.LabelFrame(parent, text=" 🔁 Repeat Settings ", 
                                     font=(S.FONT_FAMILY, S.FONT_SIZE_MD, "bold"),
                                     bg=S.BG_CARD, fg=S.FG_ACCENT,
                                     padx=S.PAD_MD, pady=S.PAD_MD)
        repeat_frame.pack(fill="x", padx=S.PAD_MD, pady=S.PAD_SM)
        
        # Count row
        count_row = tk.Frame(repeat_frame, bg=S.BG_CARD)
        count_row.pack(fill="x", pady=S.PAD_XS)
        
        tk.Label(count_row, text="Repeat count:", bg=S.BG_CARD, fg=S.FG_PRIMARY,
                font=(S.FONT_FAMILY, S.FONT_SIZE_MD)).pack(side="left")
        
        count_var = tk.IntVar(value=value.get("count", 1))
        count_spin = tk.Spinbox(count_row, from_=1, to=9999, textvariable=count_var, width=8,
                               bg=S.BG_INPUT, fg=S.FG_PRIMARY, buttonbackground=S.BTN_SECONDARY,
                               font=(S.FONT_FAMILY, S.FONT_SIZE_MD), relief="flat")
        count_spin.pack(side="left", padx=S.PAD_SM)
        widgets["count"] = count_var
        
        tk.Label(count_row, text="times", bg=S.BG_CARD, fg=S.FG_MUTED,
                font=(S.FONT_FAMILY, S.FONT_SIZE_SM)).pack(side="left")
        
        # Function to get existing labels
        def get_label_list():
            labels = []
            for action in self.actions:
                lbl_name = ""
                if action.action == "LABEL":
                    if isinstance(action.value, dict):
                        lbl_name = action.value.get("name", "")
                if not lbl_name and action.label:
                    lbl_name = action.label
                if lbl_name and lbl_name not in labels:
                    labels.append(lbl_name)
            return labels
        
        # End label row
        end_row = tk.Frame(repeat_frame, bg=S.BG_CARD)
        end_row.pack(fill="x", pady=S.PAD_XS)
        
        tk.Label(end_row, text="Jump to label:", bg=S.BG_CARD, fg=S.FG_PRIMARY,
                font=(S.FONT_FAMILY, S.FONT_SIZE_MD)).pack(side="left")
        
        start_var = tk.StringVar(value=value.get("start_label", ""))
        start_combo = ttk.Combobox(end_row, textvariable=start_var, width=15,
                                   values=get_label_list())
        start_combo.pack(side="left", padx=S.PAD_SM)
        widgets["start_label"] = start_var
        
        # Refresh on click
        start_combo.bind("<Button-1>", lambda e: start_combo.configure(values=get_label_list()))
        
        tk.Label(end_row, text="After done:", bg=S.BG_CARD, fg=S.FG_PRIMARY,
                font=(S.FONT_FAMILY, S.FONT_SIZE_MD)).pack(side="left", padx=(S.PAD_SM, 0))
        
        # Goto options: Next, Start, End, Exit macro, or label names
        goto_options = ["Next", "Start", "End", "Exit macro"] + get_label_list()
        end_var = tk.StringVar(value=value.get("end_label", "Next"))
        end_combo = ttk.Combobox(end_row, textvariable=end_var, width=15,
                                 values=goto_options)
        end_combo.pack(side="left", padx=S.PAD_SM)
        widgets["end_label"] = end_var
        
        # Refresh on click
        end_combo.bind("<Button-1>", lambda e: end_combo.configure(values=["Next", "Start", "End", "Exit macro"] + get_label_list()))
        
        # Info
        tk.Label(repeat_frame, text="💡 Loop N times: Jump to label, then go to 'After done' when finished",
                bg=S.BG_CARD, fg=S.FG_MUTED,
                font=(S.FONT_FAMILY, S.FONT_SIZE_SM)).pack(anchor="w", pady=(S.PAD_SM, 0))
    
    def _render_embed_macro_config(self, parent, widgets, value):
        """Render EMBED_MACRO config - Multi-select macro list with execution order"""
        S = ModernStyle
        parent.configure(bg=S.BG_CARD)
        import os
        
        # ==================== EMBED MACRO SETTINGS ====================
        embed_frame = tk.LabelFrame(parent, text=" 📦 Embed Macro(s) ", 
                                    font=(S.FONT_FAMILY, S.FONT_SIZE_MD, "bold"),
                                    bg=S.BG_CARD, fg=S.FG_ACCENT,
                                    padx=S.PAD_MD, pady=S.PAD_MD)
        embed_frame.pack(fill="both", expand=True, padx=S.PAD_MD, pady=S.PAD_SM)
        
        # Scan available macros from MACROS_DIR
        available_macros = []
        if os.path.exists(MACROS_DIR):
            for item in sorted(os.listdir(MACROS_DIR)):
                if item.endswith(".macro") or item.endswith(".json"):
                    available_macros.append(item)
        
        # Parse existing value - can be single string or list
        existing_macros = value.get("macro_names", [])
        if not existing_macros:
            single = value.get("macro_name", "")
            if single:
                existing_macros = [single]
        
        # Two-panel layout: Available | Selected
        panels_frame = tk.Frame(embed_frame, bg=S.BG_CARD)
        panels_frame.pack(fill="both", expand=True, pady=S.PAD_XS)
        
        # Left panel - Available macros
        left_frame = tk.LabelFrame(panels_frame, text=" 📁 Available ",
                                   font=(S.FONT_FAMILY, S.FONT_SIZE_SM),
                                   bg=S.BG_CARD, fg=S.FG_MUTED)
        left_frame.pack(side="left", fill="both", expand=True, padx=(0, S.PAD_SM))
        
        available_listbox = tk.Listbox(left_frame, height=6, 
                                       bg=S.BG_INPUT, fg=S.FG_PRIMARY,
                                       selectbackground=S.ACCENT_BLUE,
                                       selectmode=tk.EXTENDED,
                                       font=(S.FONT_FAMILY, S.FONT_SIZE_SM),
                                       relief="flat", highlightthickness=0)
        available_listbox.pack(side="left", fill="both", expand=True, padx=2, pady=2)
        
        for macro in available_macros:
            available_listbox.insert(tk.END, macro)
        
        # Center buttons
        btn_frame = tk.Frame(panels_frame, bg=S.BG_CARD)
        btn_frame.pack(side="left", padx=S.PAD_XS)
        
        # Right panel - Selected macros (order matters)
        right_frame = tk.LabelFrame(panels_frame, text=" ▶ Selected ",
                                    font=(S.FONT_FAMILY, S.FONT_SIZE_SM),
                                    bg=S.BG_CARD, fg=S.ACCENT_GREEN)
        right_frame.pack(side="left", fill="both", expand=True, padx=(S.PAD_SM, 0))
        
        selected_listbox = tk.Listbox(right_frame, height=6, 
                                      bg=S.BG_INPUT, fg=S.FG_PRIMARY,
                                      selectbackground=S.ACCENT_GREEN,
                                      font=(S.FONT_FAMILY, S.FONT_SIZE_SM),
                                      relief="flat", highlightthickness=0)
        selected_listbox.pack(side="left", fill="both", expand=True, padx=2, pady=2)
        
        for i, macro in enumerate(existing_macros, 1):
            selected_listbox.insert(tk.END, f"{i}. {macro}")
        
        selected_macros = list(existing_macros)
        
        def refresh_selected():
            selected_listbox.delete(0, tk.END)
            for i, m in enumerate(selected_macros, 1):
                selected_listbox.insert(tk.END, f"{i}. {m}")
        
        def add_sel():
            for idx in available_listbox.curselection():
                m = available_listbox.get(idx)
                if m not in selected_macros:
                    selected_macros.append(m)
            refresh_selected()
        
        def remove_sel():
            sel = selected_listbox.curselection()
            for i in reversed(sel):
                if i < len(selected_macros):
                    selected_macros.pop(i)
            refresh_selected()
        
        def move_up():
            sel = selected_listbox.curselection()
            if sel and sel[0] > 0:
                i = sel[0]
                selected_macros[i], selected_macros[i-1] = selected_macros[i-1], selected_macros[i]
                refresh_selected()
                selected_listbox.selection_set(i-1)
        
        def move_down():
            sel = selected_listbox.curselection()
            if sel and sel[0] < len(selected_macros) - 1:
                i = sel[0]
                selected_macros[i], selected_macros[i+1] = selected_macros[i+1], selected_macros[i]
                refresh_selected()
                selected_listbox.selection_set(i+1)
        
        tk.Button(btn_frame, text="➡", command=add_sel, bg=S.ACCENT_BLUE, fg=S.FG_PRIMARY,
                  relief="flat", width=3, font=(S.FONT_FAMILY, S.FONT_SIZE_SM)).pack(pady=1)
        tk.Button(btn_frame, text="⬅", command=remove_sel, bg=S.ACCENT_RED, fg=S.FG_PRIMARY,
                  relief="flat", width=3, font=(S.FONT_FAMILY, S.FONT_SIZE_SM)).pack(pady=1)
        tk.Button(btn_frame, text="⬆", command=move_up, bg=S.BTN_SECONDARY, fg=S.FG_PRIMARY,
                  relief="flat", width=3, font=(S.FONT_FAMILY, S.FONT_SIZE_SM)).pack(pady=1)
        tk.Button(btn_frame, text="⬇", command=move_down, bg=S.BTN_SECONDARY, fg=S.FG_PRIMARY,
                  relief="flat", width=3, font=(S.FONT_FAMILY, S.FONT_SIZE_SM)).pack(pady=1)
        
        available_listbox.bind("<Double-Button-1>", lambda e: add_sel())
        selected_listbox.bind("<Double-Button-1>", lambda e: remove_sel())
        
        widgets["_selected_macros"] = selected_macros
        name_var = tk.StringVar()
        widgets["macro_name"] = name_var
        
        # Options
        opts = tk.Frame(embed_frame, bg=S.BG_CARD)
        opts.pack(fill="x", pady=(S.PAD_SM, 0))
        
        continue_var = tk.BooleanVar(value=value.get("continue_on_error", True))
        tk.Checkbutton(opts, text="Continue on error", variable=continue_var,
                      bg=S.BG_CARD, fg=S.FG_PRIMARY, selectcolor=S.BG_INPUT,
                      font=(S.FONT_FAMILY, S.FONT_SIZE_SM)).pack(side="left")
        widgets["continue_on_error"] = continue_var
        
        inherit_var = tk.BooleanVar(value=value.get("inherit_variables", True))
        tk.Checkbutton(opts, text="Inherit vars", variable=inherit_var,
                      bg=S.BG_CARD, fg=S.FG_PRIMARY, selectcolor=S.BG_INPUT,
                      font=(S.FONT_FAMILY, S.FONT_SIZE_SM)).pack(side="left", padx=S.PAD_MD)
        widgets["inherit_variables"] = inherit_var
        
        tk.Label(embed_frame, text="💡 Macros chạy theo thứ tự Selected",
                bg=S.BG_CARD, fg=S.FG_MUTED,
                font=(S.FONT_FAMILY, S.FONT_SIZE_SM)).pack(anchor="w")
    
    def _render_group_config(self, parent, widgets, value):
        """Render GROUP config - shows grouped actions"""
        name_frame = tk.Frame(parent)
        name_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(name_frame, text="Group name:", font=("Arial", 9)).pack(side="left", padx=(0, 5))
        name_var = tk.StringVar(value=value.get("name", "Group"))
        tk.Entry(name_frame, textvariable=name_var, width=25).pack(side="left")
        widgets["name"] = name_var
        
        # Show grouped actions (read-only list)
        actions = value.get("actions", [])
        widgets["_actions"] = actions  # Preserve for saving
        
        list_frame = tk.LabelFrame(parent, text=f"Grouped Actions ({len(actions)})")
        list_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Listbox to show actions
        listbox_frame = tk.Frame(list_frame)
        listbox_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        scrollbar = tk.Scrollbar(listbox_frame)
        scrollbar.pack(side="right", fill="y")
        
        listbox = tk.Listbox(listbox_frame, height=6, font=("Consolas", 9),
                            yscrollcommand=scrollbar.set)
        listbox.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=listbox.yview)
        
        for i, act_dict in enumerate(actions, 1):
            act_type = act_dict.get("action", "?")
            # Brief summary
            listbox.insert(tk.END, f"{i}. {act_type}")
        
        tk.Label(parent, text="To edit grouped actions, use Ungroup first", 
                fg="gray", font=("Arial", 8)).pack(anchor="w", padx=10)
    
    def _render_comment_config(self, parent, widgets, value):
        """Render COMMENT config"""
        text_frame = tk.Frame(parent)
        text_frame.pack(fill="both", expand=True, padx=10, pady=5)
        tk.Label(text_frame, text="Comment:", font=("Arial", 9)).pack(anchor="w")
        text_widget = tk.Text(text_frame, height=4, font=("Arial", 9))
        text_widget.pack(fill="both", expand=True, pady=5)
        text_widget.insert("1.0", value.get("text", ""))
        widgets["text"] = text_widget
        
        tk.Label(parent, text="Comments are not executed, just for documentation", 
                fg="gray", font=("Arial", 8)).pack(anchor="w", padx=10)
    
    def _render_set_variable_config(self, parent, widgets, value):
        """Render SET_VARIABLE config"""
        name_frame = tk.Frame(parent)
        name_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(name_frame, text="Variable name:", font=("Arial", 9)).pack(side="left", padx=(0, 5))
        name_var = tk.StringVar(value=value.get("name", ""))
        tk.Entry(name_frame, textvariable=name_var, width=20).pack(side="left")
        widgets["name"] = name_var
        
        value_frame = tk.Frame(parent)
        value_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(value_frame, text="Value:", font=("Arial", 9)).pack(side="left", padx=(0, 5))
        val_var = tk.StringVar(value=str(value.get("value", "")))
        tk.Entry(value_frame, textvariable=val_var, width=25).pack(side="left")
        widgets["value"] = val_var
        
        tk.Label(parent, text="Set a variable for use in subsequent actions", 
                fg="gray", font=("Arial", 8)).pack(anchor="w", padx=10)
    
    def _render_drag_action_config(self, parent, widgets, value, dialog=None, is_worker_context=False):
        """Render Drag action config - V2 with capture support"""
        S = ModernStyle
        parent.configure(bg=S.BG_CARD)
        
        # Target dropdown (Screen/Emulator)
        target_mode_var = self._create_target_dropdown(parent, widgets, value, S, is_worker_context)
        
        # Button type (left/right)
        btn_frame = tk.Frame(parent, bg=S.BG_CARD)
        btn_frame.pack(fill="x", padx=S.PAD_MD, pady=S.PAD_SM)
        tk.Label(btn_frame, text="Button:", bg=S.BG_CARD, fg=S.FG_SECONDARY,
                font=(S.FONT_FAMILY, S.FONT_SIZE_SM)).pack(side="left", padx=(0, S.PAD_SM))
        btn_var = tk.StringVar(value=value.get("button", "left"))
        btn_dropdown = ttk.Combobox(btn_frame, textvariable=btn_var, 
                                    values=["left", "right"], state="readonly", width=8)
        btn_dropdown.pack(side="left", padx=2)
        widgets["button"] = btn_var
        
        # Duration
        tk.Label(btn_frame, text="Duration (ms):", bg=S.BG_CARD, fg=S.FG_SECONDARY,
                font=(S.FONT_FAMILY, S.FONT_SIZE_SM)).pack(side="left", padx=(S.PAD_MD, S.PAD_XS))
        duration_var = tk.IntVar(value=value.get("duration_ms", 500))
        S.create_entry(btn_frame, textvariable=duration_var, width=6).pack(side="left", padx=2)
        widgets["duration_ms"] = duration_var
        
        # Checkbox: Use current position for START point
        start_opt_frame = tk.Frame(parent, bg=S.BG_CARD)
        start_opt_frame.pack(fill="x", padx=S.PAD_MD, pady=(S.PAD_SM, 0))
        
        use_current_start_var = tk.BooleanVar(value=value.get("use_current_start", False))
        use_current_cb = tk.Checkbutton(start_opt_frame, text="🎯 Start from current mouse position", 
                                        variable=use_current_start_var,
                                        bg=S.BG_CARD, fg=S.ACCENT_BLUE, selectcolor=S.BG_INPUT,
                                        activebackground=S.BG_CARD, activeforeground=S.ACCENT_BLUE,
                                        font=(S.FONT_FAMILY, S.FONT_SIZE_SM))
        use_current_cb.pack(side="left")
        widgets["use_current_start"] = use_current_start_var
        
        # Start position
        start_frame = tk.Frame(parent, bg=S.BG_CARD)
        start_frame.pack(fill="x", padx=S.PAD_MD, pady=S.PAD_SM)
        tk.Label(start_frame, text="Start:", bg=S.BG_CARD, fg=S.FG_SECONDARY,
                font=(S.FONT_FAMILY, S.FONT_SIZE_SM)).pack(side="left", padx=(0, S.PAD_SM))
        x1_var = tk.IntVar(value=value.get("x1", 0))
        y1_var = tk.IntVar(value=value.get("y1", 0))
        tk.Label(start_frame, text="X1:", bg=S.BG_CARD, fg=S.FG_SECONDARY,
                font=(S.FONT_FAMILY, S.FONT_SIZE_SM)).pack(side="left")
        x1_entry = S.create_entry(start_frame, textvariable=x1_var, width=6)
        x1_entry.pack(side="left", padx=2)
        tk.Label(start_frame, text="Y1:", bg=S.BG_CARD, fg=S.FG_SECONDARY,
                font=(S.FONT_FAMILY, S.FONT_SIZE_SM)).pack(side="left")
        y1_entry = S.create_entry(start_frame, textvariable=y1_var, width=6)
        y1_entry.pack(side="left", padx=2)
        widgets["x1"] = x1_var
        widgets["y1"] = y1_var
        
        # Toggle start coords
        def toggle_start_coords(*args):
            state = "disabled" if use_current_start_var.get() else "normal"
            x1_entry.config(state=state)
            y1_entry.config(state=state)
        
        use_current_start_var.trace_add("write", toggle_start_coords)
        toggle_start_coords()
        
        # End position
        end_frame = tk.Frame(parent, bg=S.BG_CARD)
        end_frame.pack(fill="x", padx=S.PAD_MD, pady=S.PAD_SM)
        tk.Label(end_frame, text="End:", bg=S.BG_CARD, fg=S.FG_SECONDARY,
                font=(S.FONT_FAMILY, S.FONT_SIZE_SM)).pack(side="left", padx=(0, S.PAD_SM))
        x2_var = tk.IntVar(value=value.get("x2", 0))
        y2_var = tk.IntVar(value=value.get("y2", 0))
        tk.Label(end_frame, text="X2:", bg=S.BG_CARD, fg=S.FG_SECONDARY,
                font=(S.FONT_FAMILY, S.FONT_SIZE_SM)).pack(side="left")
        S.create_entry(end_frame, textvariable=x2_var, width=6).pack(side="left", padx=2)
        tk.Label(end_frame, text="Y2:", bg=S.BG_CARD, fg=S.FG_SECONDARY,
                font=(S.FONT_FAMILY, S.FONT_SIZE_SM)).pack(side="left")
        S.create_entry(end_frame, textvariable=y2_var, width=6).pack(side="left", padx=2)
        widgets["x2"] = x2_var
        widgets["y2"] = y2_var
        
        # Capture button with target support
        capture_frame = tk.Frame(parent, bg=S.BG_CARD)
        capture_frame.pack(fill="x", padx=S.PAD_MD, pady=S.PAD_SM)
        
        def do_capture():
            hwnd = None
            if target_mode_var.get() == "emulator":
                hwnd = self._get_emulator_hwnd_for_capture()
            self._capture_drag_path_target(x1_var, y1_var, x2_var, y2_var, duration_var, hwnd, dialog)
        
        capture_btn = S.create_modern_button(capture_frame, "📍 Capture Drag", do_capture, "accent", width=14)
        capture_btn.pack(side="left")
        tk.Label(capture_frame, text="(Giữ chuột và kéo để capture hành trình)", 
                bg=S.BG_CARD, fg=S.FG_MUTED, font=(S.FONT_FAMILY, S.FONT_SIZE_XS)).pack(side="left", padx=S.PAD_MD)

    def _load_macros(self):
        if not os.path.exists(MACRO_STORE):
            return

        try:
            with open(MACRO_STORE, "r", encoding="utf-8") as f:
                self.macros = json.load(f)
        except Exception as e:
            log(f"[UI] Load macro fail: {e}")

    def _save_macros(self):
        os.makedirs(os.path.dirname(MACRO_STORE), exist_ok=True)
        with open(MACRO_STORE, "w", encoding="utf-8") as f:
            json.dump(self.macros, f, indent=2, ensure_ascii=False)

    # ================= COMMAND ACTIONS =================
    
    def _on_command_double_click(self, event):
        """Handle double-click on command row to edit"""
        item = self.command_tree.identify_row(event.y)
        if item:
            values = self.command_tree.item(item, "values")
            stt = int(values[0]) - 1  # STT is 1-based
            self.open_command_editor(edit_index=stt)
    
    def _on_command_click(self, event):
        """Handle single click on command row (for Actions column)"""
        region = self.command_tree.identify("region", event.x, event.y)
        column = self.command_tree.identify_column(event.x)
        item = self.command_tree.identify_row(event.y)
        
        # Actions column is #5
        if column == "#5" and region == "cell" and item:
            values = self.command_tree.item(item, "values")
            stt = int(values[0]) - 1  # STT is 1-based
            self._show_command_action_menu(event, stt)
    
    def _show_command_action_menu(self, event, index: int):
        """Show popup menu with Edit/Delete actions for command"""
        menu = tk.Menu(self.root, tearoff=0)
        
        menu.add_command(label="✏ Edit", command=lambda: self.open_command_editor(edit_index=index))
        menu.add_command(label="🗑 Delete", command=lambda: self._delete_command_at(index))
        menu.add_separator()
        menu.add_command(label="⬆ Move Up", command=lambda: self._move_command(index, -1))
        menu.add_command(label="⬇ Move Down", command=lambda: self._move_command(index, 1))
        
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()
    
    def _delete_command_at(self, index: int):
        """Delete command at specific index"""
        if 0 <= index < len(self.commands):
            cmd = self.commands[index]
            if messagebox.askyesno("Xóa", f"Xóa command '{cmd.name}'?"):
                self.commands.pop(index)
                self._refresh_command_list()
    
    def _move_command(self, index: int, direction: int):
        """Move command up or down"""
        new_index = index + direction
        if 0 <= new_index < len(self.commands):
            self.commands[index], self.commands[new_index] = self.commands[new_index], self.commands[index]
            self._refresh_command_list()
    
    def move_command_up(self):
        """Move selected command up"""
        selection = self.command_tree.selection()
        if not selection:
            return
        values = self.command_tree.item(selection[0], "values")
        index = int(values[0]) - 1
        self._move_command(index, -1)
    
    def move_command_down(self):
        """Move selected command down"""
        selection = self.command_tree.selection()
        if not selection:
            return
        values = self.command_tree.item(selection[0], "values")
        index = int(values[0]) - 1
        self._move_command(index, 1)

    # ================= ACTION =================

    def add_command(self):
        """Open Command Editor modal to add new command"""
        self.open_command_editor()
    
    def remove_command(self):
        """Remove selected command from list"""
        selection = self.command_tree.selection()
        if not selection:
            return

        item_id = selection[0]
        values = self.command_tree.item(item_id, "values")
        stt = values[0]
        name = values[1]

        if messagebox.askyesno("Xóa", f"Xóa command '{name}' khỏi danh sách?"):
            self.command_tree.delete(item_id)
            # Remove from commands list (Command objects)
            self.commands = [cmd for cmd in self.commands if cmd.name != name]
            self._refresh_command_list()
    
    def save_script(self):
        """Save current script to JSON file"""
        if not self.commands:
            messagebox.showwarning("Thông báo", "Chưa có command nào để lưu")
            return
        
        filepath = filedialog.asksaveasfilename(
            title="Lưu Script",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if not filepath:
            return
        
        try:
            # Create Script object and serialize
            script = Script(sequence=self.commands)
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(script.to_dict(), f, indent=2, ensure_ascii=False)
            messagebox.showinfo("Thành công", f"✓ Đã lưu script: {os.path.basename(filepath)}")
            log(f"[UI] Saved script: {filepath}")
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không thể lưu file: {e}")
    
    def load_script(self):
        """Load script from JSON file"""
        filepath = filedialog.askopenfilename(
            title="Tải Script",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if not filepath:
            return
        
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # Deserialize Script object
            script = Script.from_dict(data)
            self.commands = script.sequence
            self.current_script = script
            
            self._refresh_command_list()
            messagebox.showinfo("Thành công", f"✓ Đã load {len(self.commands)} command(s)")
            log(f"[UI] Loaded script: {filepath}")
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không thể load file: {e}")
    
    def _refresh_command_list(self):
        """Refresh command tree display"""
        # Clear tree
        for item in self.command_tree.get_children():
            self.command_tree.delete(item)
        
        # Reload from self.commands (Command objects)
        for idx, cmd in enumerate(self.commands, 1):
            cmd_type = cmd.type.value  # Enum value
            summary = self._get_command_summary(cmd)
            actions = "Edit | Del"
            
            self.command_tree.insert("", tk.END, values=(idx, cmd.name, cmd_type, summary, actions))
    
    def _get_command_summary(self, cmd: Command):
        """Generate summary text for command"""
        if isinstance(cmd, ClickCommand):
            return f"({cmd.x}, {cmd.y})"
        elif isinstance(cmd, KeyPressCommand):
            return f"Key: {cmd.key}"
        elif isinstance(cmd, TextCommand):
            text = cmd.content[:20]
            return f'"{text}..."' if len(cmd.content) > 20 else f'"{text}"'
        elif isinstance(cmd, WaitCommand):
            if cmd.wait_type == WaitType.TIMEOUT:
                return f"{cmd.timeout_sec}s"
            else:
                return f"Pixel/Screen check"
        elif isinstance(cmd, CropImageCommand):
            return f"Region ({cmd.x1},{cmd.y1})-({cmd.x2},{cmd.y2})"
        elif isinstance(cmd, GotoCommand):
            return f"→ {cmd.target_label}"
        elif isinstance(cmd, RepeatCommand):
            return f"{cmd.count}x" if cmd.count > 0 else "∞"
        elif isinstance(cmd, ConditionCommand):
            return f"If: {cmd.expr[:30]}"
        else:
            return ""
    
    def open_command_editor(self, edit_index=None):
        """Open Command Editor modal"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Command Editor")
        dialog.geometry("500x600")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # If editing, load existing command (Command object)
        edit_cmd = None
        if edit_index is not None and 0 <= edit_index < len(self.commands):
            edit_cmd = self.commands[edit_index]
        
        # ===== NAME =====
        name_frame = tk.Frame(dialog)
        name_frame.pack(fill="x", padx=15, pady=10)
        
        tk.Label(name_frame, text="Name:", font=("Arial", 9, "bold")).pack(side="left", padx=(0, 5))
        name_var = tk.StringVar(value=edit_cmd.name if edit_cmd else "")
        name_entry = tk.Entry(name_frame, textvariable=name_var, font=("Arial", 9))
        name_entry.pack(side="left", fill="x", expand=True)
        
        # ===== TYPE =====
        type_frame = tk.Frame(dialog)
        type_frame.pack(fill="x", padx=15, pady=5)
        
        tk.Label(type_frame, text="Type:", font=("Arial", 9, "bold")).pack(side="left", padx=(0, 5))
        type_var = tk.StringVar(value=edit_cmd.type.value if edit_cmd else "Click")
        type_options = ["Click", "KeyPress", "Text", "Wait", "CropImage", "Repeat", "Condition", "Goto", "HotKey"]
        type_dropdown = ttk.Combobox(type_frame, textvariable=type_var, values=type_options, 
                                     state="readonly", font=("Arial", 9), width=15)
        type_dropdown.pack(side="left")
        
        # ===== DYNAMIC CONFIG PANEL =====
        config_frame = tk.LabelFrame(dialog, text="Configuration", font=("Arial", 10, "bold"))
        config_frame.pack(fill="both", expand=True, padx=15, pady=10)
        
        config_widgets = {}  # Store widgets for retrieval
        
        def render_config_panel():
            """Clear and render config panel based on selected type"""
            for widget in config_frame.winfo_children():
                widget.destroy()
            config_widgets.clear()
            
            cmd_type = type_var.get()
            
            if cmd_type == "Click":
                self._render_click_config(config_frame, config_widgets, edit_cmd)
            elif cmd_type == "KeyPress":
                self._render_keypress_config(config_frame, config_widgets, edit_cmd)
            elif cmd_type == "Text":
                self._render_text_config(config_frame, config_widgets, edit_cmd)
            elif cmd_type == "Wait":
                self._render_wait_config(config_frame, config_widgets, edit_cmd)
            elif cmd_type == "CropImage":
                self._render_cropimage_config(config_frame, config_widgets, edit_cmd)
            elif cmd_type == "HotKey":
                self._render_hotkey_config(config_frame, config_widgets, edit_cmd)
            elif cmd_type == "Repeat":
                self._render_repeat_config(config_frame, config_widgets, edit_cmd)
            elif cmd_type == "Condition":
                self._render_condition_config(config_frame, config_widgets, edit_cmd)
            elif cmd_type == "Goto":
                self._render_goto_config(config_frame, config_widgets, edit_cmd)
            else:
                tk.Label(config_frame, text=f"{cmd_type} configuration coming soon...", 
                        fg="gray").pack(pady=20)
        
        type_dropdown.bind("<<ComboboxSelected>>", lambda e: render_config_panel())
        render_config_panel()  # Initial render
        
        # ===== ENABLED =====
        enabled_frame = tk.Frame(dialog)
        enabled_frame.pack(fill="x", padx=15, pady=5)
        
        enabled_var = tk.BooleanVar(value=edit_cmd.enabled if edit_cmd else True)
        tk.Checkbutton(enabled_frame, text="Enabled", variable=enabled_var, 
                      font=("Arial", 9, "bold")).pack(anchor="w")
        
        # ===== BUTTONS =====
        btn_frame = tk.Frame(dialog)
        btn_frame.pack(fill="x", padx=15, pady=10)
        
        def save_command():
            """Validate and save command"""
            name = name_var.get().strip()
            if not name:
                messagebox.showwarning("Lỗi", "Name không được để trống")
                return
            
            # Check duplicate name (except when editing same command)
            for idx, cmd in enumerate(self.commands):
                if cmd.name == name and (edit_index is None or idx != edit_index):
                    messagebox.showwarning("Lỗi", f"Name '{name}' đã tồn tại")
                    return
            
            # Build Command object based on type
            cmd_type_str = type_var.get()
            cmd_obj = self._create_command_from_widgets(
                name, cmd_type_str, enabled_var.get(), config_widgets, edit_cmd
            )
            
            if not cmd_obj:
                messagebox.showerror("Lỗi", "Không thể tạo command")
                return
            
            # Add or update
            if edit_index is not None:
                self.commands[edit_index] = cmd_obj
            else:
                self.commands.append(cmd_obj)
            
            self._refresh_command_list()
            dialog.destroy()
            log(f"[UI] {'Updated' if edit_index else 'Added'} command: {name}")
        
        tk.Button(btn_frame, text="✓ OK", command=save_command, bg="#4CAF50", fg="white", 
                 font=("Arial", 9, "bold"), width=12).pack(side="left", padx=5)
        tk.Button(btn_frame, text="✗ Hủy", command=dialog.destroy, bg="#f44336", fg="white", 
                 font=("Arial", 9, "bold"), width=12).pack(side="left", padx=5)
    
    def _render_click_config(self, parent, widgets, edit_cmd=None):
        """Render Click configuration"""
        # Extract values from Command object if editing
        button = "Left"
        x, y = 0, 0
        delay_min, delay_max = 50, 200
        
        if edit_cmd and isinstance(edit_cmd, ClickCommand):
            button = edit_cmd.button_type.value
            x, y = edit_cmd.x, edit_cmd.y
            delay_min = edit_cmd.humanize_delay_min_ms
            delay_max = edit_cmd.humanize_delay_max_ms
        
        # Button Type
        btn_frame = tk.Frame(parent)
        btn_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(btn_frame, text="Button:", font=("Arial", 9)).pack(side="left", padx=(0, 5))
        btn_var = tk.StringVar(value=button)
        ttk.Combobox(btn_frame, textvariable=btn_var, values=["Left", "Right", "Double"], 
                    state="readonly", width=10).pack(side="left")
        widgets["button"] = btn_var
        
        # Position
        pos_frame = tk.Frame(parent)
        pos_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(pos_frame, text="Position:", font=("Arial", 9)).pack(side="left", padx=(0, 5))
        
        x_var = tk.IntVar(value=x)
        tk.Label(pos_frame, text="X:").pack(side="left", padx=(10, 2))
        tk.Entry(pos_frame, textvariable=x_var, width=8).pack(side="left", padx=2)
        widgets["x"] = x_var
        
        y_var = tk.IntVar(value=y)
        tk.Label(pos_frame, text="Y:").pack(side="left", padx=(10, 2))
        tk.Entry(pos_frame, textvariable=y_var, width=8).pack(side="left", padx=2)
        widgets["y"] = y_var
        
        tk.Button(pos_frame, text="📍 Capture", command=lambda: self._capture_position(x_var, y_var), 
                 bg="#2196F3", fg="white", font=("Arial", 8)).pack(side="left", padx=10)
        
        # Humanize delay
        delay_frame = tk.Frame(parent)
        delay_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(delay_frame, text="Humanize Delay (ms):", font=("Arial", 9)).pack(side="left")
        delay_var = tk.IntVar(value=delay_max)
        tk.Scale(delay_frame, from_=0, to=500, orient=tk.HORIZONTAL, variable=delay_var, 
                length=200).pack(side="left", padx=5)
        widgets["humanize_delay"] = delay_var

    
    def _render_keypress_config(self, parent, widgets, edit_cmd=None):
        """Render KeyPress configuration"""
        key_val = ""
        repeat_val = 1
        
        if edit_cmd and isinstance(edit_cmd, KeyPressCommand):
            key_val = edit_cmd.key
            repeat_val = edit_cmd.repeat
        
        # Key
        key_frame = tk.Frame(parent)
        key_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(key_frame, text="Key:", font=("Arial", 9)).pack(side="left", padx=(0, 5))
        key_var = tk.StringVar(value=key_val)
        key_entry = tk.Entry(key_frame, textvariable=key_var, font=("Arial", 9), width=20)
        key_entry.pack(side="left")
        widgets["key"] = key_var
        
        tk.Label(key_frame, text="(e.g. A, Enter, Ctrl+C)", fg="gray", font=("Arial", 8)).pack(side="left", padx=5)
        
        # Repeat
        repeat_frame = tk.Frame(parent)
        repeat_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(repeat_frame, text="Repeat:", font=("Arial", 9)).pack(side="left", padx=(0, 5))
        repeat_var = tk.IntVar(value=repeat_val)
        tk.Spinbox(repeat_frame, from_=1, to=100, textvariable=repeat_var, width=10).pack(side="left")
        widgets["repeat"] = repeat_var
    
    def _render_text_config(self, parent, widgets, edit_cmd=None):
        """Render Text configuration"""
        content_val = ""
        mode_val = "Paste"
        speed_val = 50
        
        if edit_cmd and isinstance(edit_cmd, TextCommand):
            content_val = edit_cmd.content
            mode_val = edit_cmd.text_mode.value
            speed_val = edit_cmd.speed_max_cps
        
        # Content
        content_frame = tk.Frame(parent)
        content_frame.pack(fill="both", expand=True, padx=10, pady=5)
        tk.Label(content_frame, text="Content:", font=("Arial", 9)).pack(anchor="w")
        
        content_text = tk.Text(content_frame, height=5, font=("Arial", 9))
        content_text.pack(fill="both", expand=True, pady=5)
        content_text.insert("1.0", content_val)
        widgets["content"] = content_text
        
        # Mode
        mode_frame = tk.Frame(parent)
        mode_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(mode_frame, text="Mode:", font=("Arial", 9)).pack(side="left", padx=(0, 5))
        mode_var = tk.StringVar(value=mode_val)
        ttk.Combobox(mode_frame, textvariable=mode_var, values=["Paste", "Humanize"], 
                    state="readonly", width=10).pack(side="left")
        widgets["mode"] = mode_var
        
        # Speed (if humanize)
        speed_frame = tk.Frame(parent)
        speed_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(speed_frame, text="Speed (cps):", font=("Arial", 9)).pack(side="left")
        speed_var = tk.IntVar(value=speed_val)
        tk.Scale(speed_frame, from_=10, to=100, orient=tk.HORIZONTAL, variable=speed_var, 
                length=200).pack(side="left", padx=5)
        widgets["speed"] = speed_var
    
    def _render_wait_config(self, parent, widgets, edit_cmd=None):
        """Render Wait configuration"""
        wait_type_val = "Timeout"
        timeout_val = 30
        
        if edit_cmd and isinstance(edit_cmd, WaitCommand):
            wait_type_val = edit_cmd.wait_type.value
            timeout_val = edit_cmd.timeout_sec
        
        # Wait Type
        type_frame = tk.Frame(parent)
        type_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(type_frame, text="Wait Type:", font=("Arial", 9)).pack(side="left", padx=(0, 5))
        wait_type_var = tk.StringVar(value=wait_type_val)
        
        def update_wait_config():
            # Show/hide relevant widgets based on wait type
            if wait_type_var.get() == "Timeout":
                pixel_frame.pack_forget()
                timeout_frame.pack(fill="x", padx=10, pady=5)
            else:
                timeout_frame.pack_forget()
                pixel_frame.pack(fill="x", padx=10, pady=5)
        
        ttk.Combobox(type_frame, textvariable=wait_type_var, values=["Timeout", "PixelColor", "ScreenChange"], 
                    state="readonly", width=15, 
                    postcommand=update_wait_config).pack(side="left")
        widgets["wait_type"] = wait_type_var
        
        # Timeout config
        timeout_frame = tk.Frame(parent)
        tk.Label(timeout_frame, text="Seconds:", font=("Arial", 9)).pack(side="left", padx=(0, 5))
        timeout_var = tk.IntVar(value=timeout_val)
        tk.Spinbox(timeout_frame, from_=1, to=60, textvariable=timeout_var, width=10).pack(side="left")
        widgets["timeout_sec"] = timeout_var
        
        # Pixel config
        pixel_frame = tk.Frame(parent)
        tk.Label(pixel_frame, text="Position & Color check (coming soon)", 
                fg="gray").pack(pady=10)
        
        # Show appropriate frame
        update_wait_config()
    
    def _render_cropimage_config(self, parent, widgets, edit_cmd=None):
        """Render CropImage configuration"""
        x1, y1, x2, y2 = 0, 0, 100, 100
        target_color = (255, 0, 0)
        tolerance = 10
        output_var = "crop_result"
        scan_mode = "Exact"
        
        if edit_cmd and isinstance(edit_cmd, CropImageCommand):
            x1, y1 = edit_cmd.x1, edit_cmd.y1
            x2, y2 = edit_cmd.x2, edit_cmd.y2
            target_color = edit_cmd.target_color or (255, 0, 0)
            tolerance = edit_cmd.tolerance
            output_var = edit_cmd.output_var
            scan_mode = edit_cmd.scan_mode.value if edit_cmd.scan_mode else "Exact"
        
        # Region
        region_frame = tk.Frame(parent)
        region_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(region_frame, text="Region:", font=("Arial", 9)).pack(side="left", padx=(0, 5))
        
        x1_var = tk.IntVar(value=x1)
        tk.Label(region_frame, text="X1:").pack(side="left", padx=(5, 2))
        tk.Entry(region_frame, textvariable=x1_var, width=5).pack(side="left")
        widgets["x1"] = x1_var
        
        y1_var = tk.IntVar(value=y1)
        tk.Label(region_frame, text="Y1:").pack(side="left", padx=(5, 2))
        tk.Entry(region_frame, textvariable=y1_var, width=5).pack(side="left")
        widgets["y1"] = y1_var
        
        x2_var = tk.IntVar(value=x2)
        tk.Label(region_frame, text="X2:").pack(side="left", padx=(5, 2))
        tk.Entry(region_frame, textvariable=x2_var, width=5).pack(side="left")
        widgets["x2"] = x2_var
        
        y2_var = tk.IntVar(value=y2)
        tk.Label(region_frame, text="Y2:").pack(side="left", padx=(5, 2))
        tk.Entry(region_frame, textvariable=y2_var, width=5).pack(side="left")
        widgets["y2"] = y2_var
        
        tk.Button(region_frame, text="📐 Capture Region", 
                 command=lambda: self._capture_region(x1_var, y1_var, x2_var, y2_var),
                 bg="#2196F3", fg="white", font=("Arial", 8)).pack(side="left", padx=10)
        
        # Target Color
        color_frame = tk.Frame(parent)
        color_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(color_frame, text="Target Color (RGB):", font=("Arial", 9)).pack(side="left", padx=(0, 5))
        
        r_var = tk.IntVar(value=target_color[0])
        tk.Label(color_frame, text="R:").pack(side="left", padx=(5, 2))
        tk.Entry(color_frame, textvariable=r_var, width=4).pack(side="left")
        widgets["color_r"] = r_var
        
        g_var = tk.IntVar(value=target_color[1])
        tk.Label(color_frame, text="G:").pack(side="left", padx=(5, 2))
        tk.Entry(color_frame, textvariable=g_var, width=4).pack(side="left")
        widgets["color_g"] = g_var
        
        b_var = tk.IntVar(value=target_color[2])
        tk.Label(color_frame, text="B:").pack(side="left", padx=(5, 2))
        tk.Entry(color_frame, textvariable=b_var, width=4).pack(side="left")
        widgets["color_b"] = b_var
        
        tk.Button(color_frame, text="🎨 Pick Color", command=lambda: self._pick_color(r_var, g_var, b_var),
                 bg="#9C27B0", fg="white", font=("Arial", 8)).pack(side="left", padx=10)
        
        # Tolerance
        tol_frame = tk.Frame(parent)
        tol_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(tol_frame, text="Tolerance (0-255):", font=("Arial", 9)).pack(side="left")
        tol_var = tk.IntVar(value=tolerance)
        tk.Scale(tol_frame, from_=0, to=50, orient=tk.HORIZONTAL, variable=tol_var, 
                length=150).pack(side="left", padx=5)
        widgets["tolerance"] = tol_var
        
        # Scan Mode
        mode_frame = tk.Frame(parent)
        mode_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(mode_frame, text="Scan Mode:", font=("Arial", 9)).pack(side="left", padx=(0, 5))
        scan_var = tk.StringVar(value=scan_mode)
        ttk.Combobox(mode_frame, textvariable=scan_var, values=["Exact", "MaxMatch", "Grid"], 
                    state="readonly", width=12).pack(side="left")
        widgets["scan_mode"] = scan_var
        
        # Output Variable
        out_frame = tk.Frame(parent)
        out_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(out_frame, text="Output Variable:", font=("Arial", 9)).pack(side="left", padx=(0, 5))
        out_var = tk.StringVar(value=output_var)
        tk.Entry(out_frame, textvariable=out_var, width=20).pack(side="left")
        widgets["output_var"] = out_var
    
    def _render_hotkey_config(self, parent, widgets, edit_cmd=None):
        """Render HotKey configuration"""
        keys_val = ""
        order_val = "Simultaneous"
        
        if edit_cmd and isinstance(edit_cmd, HotKeyCommand):
            keys_val = "+".join(edit_cmd.keys) if edit_cmd.keys else ""
            order_val = edit_cmd.hotkey_order.value if edit_cmd.hotkey_order else "Simultaneous"
        
        # Keys
        keys_frame = tk.Frame(parent)
        keys_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(keys_frame, text="Keys:", font=("Arial", 9)).pack(side="left", padx=(0, 5))
        keys_var = tk.StringVar(value=keys_val)
        tk.Entry(keys_frame, textvariable=keys_var, width=30).pack(side="left")
        widgets["keys"] = keys_var
        tk.Label(keys_frame, text="(e.g. Ctrl+Shift+A)", fg="gray", font=("Arial", 8)).pack(side="left", padx=5)
        
        # Order
        order_frame = tk.Frame(parent)
        order_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(order_frame, text="Order:", font=("Arial", 9)).pack(side="left", padx=(0, 5))
        order_var = tk.StringVar(value=order_val)
        ttk.Combobox(order_frame, textvariable=order_var, values=["Simultaneous", "Sequence"], 
                    state="readonly", width=15).pack(side="left")
        widgets["hotkey_order"] = order_var
    
    def _render_repeat_config(self, parent, widgets, edit_cmd=None):
        """Render Repeat configuration - Loop back to label N times"""
        count_val = 1
        label_val = ""
        goto_val = "Next"
        
        if edit_cmd:
            if isinstance(edit_cmd, RepeatCommand):
                count_val = edit_cmd.count
                label_val = getattr(edit_cmd, 'start_label', '') or ""
                goto_val = getattr(edit_cmd, 'end_label', 'Next') or "Next"
            elif hasattr(edit_cmd, 'get'):  # Dict-like
                count_val = edit_cmd.get('count', 1)
                label_val = edit_cmd.get('start_label', '') or ""
                goto_val = edit_cmd.get('end_label', 'Next') or "Next"
        
        # Helper to get available labels
        def get_label_list():
            labels = []
            for act in self.actions:
                if act.action == "LABEL":
                    name = act.value.get("name", "") if isinstance(act.value, dict) else ""
                    if name:
                        labels.append(name)
                if act.label:
                    labels.append(act.label)
            return labels
        
        # Count
        count_frame = tk.Frame(parent)
        count_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(count_frame, text="Count:", font=("Arial", 9)).pack(side="left", padx=(0, 5))
        count_var = tk.IntVar(value=count_val)
        tk.Spinbox(count_frame, from_=1, to=9999, textvariable=count_var, width=8).pack(side="left")
        widgets["count"] = count_var
        tk.Label(count_frame, text="iterations", fg="gray", font=("Arial", 8)).pack(side="left", padx=5)
        
        # Jump to label
        label_frame = tk.Frame(parent)
        label_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(label_frame, text="Jump to label:", font=("Arial", 9)).pack(side="left", padx=(0, 5))
        label_var = tk.StringVar(value=label_val)
        label_combo = ttk.Combobox(label_frame, textvariable=label_var, width=20, values=get_label_list())
        label_combo.pack(side="left")
        widgets["start_label"] = label_var
        label_combo.bind("<Button-1>", lambda e: label_combo.configure(values=get_label_list()))
        
        # After done (goto)
        goto_frame = tk.Frame(parent)
        goto_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(goto_frame, text="After done:", font=("Arial", 9)).pack(side="left", padx=(0, 5))
        goto_options = ["Next", "Start", "End", "Exit macro"] + get_label_list()
        goto_var = tk.StringVar(value=goto_val)
        goto_combo = ttk.Combobox(goto_frame, textvariable=goto_var, width=20, values=goto_options)
        goto_combo.pack(side="left")
        widgets["end_label"] = goto_var
        goto_combo.bind("<Button-1>", lambda e: goto_combo.configure(values=["Next", "Start", "End", "Exit macro"] + get_label_list()))
        
        tk.Label(parent, text="💡 Loop: Jump to label N times, then go to 'After done'", 
                fg="gray", font=("Arial", 8)).pack(pady=5, anchor="w", padx=10)
    
    def _render_condition_config(self, parent, widgets, edit_cmd=None):
        """Render Condition configuration"""
        expr_val = ""
        then_val = ""
        else_val = ""
        
        if edit_cmd and isinstance(edit_cmd, ConditionCommand):
            expr_val = edit_cmd.expr or ""
            then_val = edit_cmd.then_label or ""
            else_val = edit_cmd.else_label or ""
        
        # Expression
        expr_frame = tk.Frame(parent)
        expr_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(expr_frame, text="Expression:", font=("Arial", 9)).pack(side="left", padx=(0, 5))
        expr_var = tk.StringVar(value=expr_val)
        tk.Entry(expr_frame, textvariable=expr_var, width=40).pack(side="left")
        widgets["expr"] = expr_var
        
        tk.Label(parent, text="Example: variables['result'] != None", 
                fg="gray", font=("Arial", 8)).pack(anchor="w", padx=15)
        
        # Then label
        then_frame = tk.Frame(parent)
        then_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(then_frame, text="Then → Label:", font=("Arial", 9)).pack(side="left", padx=(0, 5))
        then_var = tk.StringVar(value=then_val)
        tk.Entry(then_frame, textvariable=then_var, width=25).pack(side="left")
        widgets["then_label"] = then_var
        
        # Else label
        else_frame = tk.Frame(parent)
        else_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(else_frame, text="Else → Label:", font=("Arial", 9)).pack(side="left", padx=(0, 5))
        else_var = tk.StringVar(value=else_val)
        tk.Entry(else_frame, textvariable=else_var, width=25).pack(side="left")
        widgets["else_label"] = else_var
    
    def _render_goto_config(self, parent, widgets, edit_cmd=None):
        """Render Goto configuration"""
        target_val = ""
        cond_val = ""
        
        if edit_cmd and isinstance(edit_cmd, GotoCommand):
            target_val = edit_cmd.target_label or ""
            cond_val = edit_cmd.condition_expr or ""
        
        # Target label
        target_frame = tk.Frame(parent)
        target_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(target_frame, text="Target Label:", font=("Arial", 9)).pack(side="left", padx=(0, 5))
        target_var = tk.StringVar(value=target_val)
        tk.Entry(target_frame, textvariable=target_var, width=25).pack(side="left")
        widgets["target_label"] = target_var
        
        # Condition (optional)
        cond_frame = tk.Frame(parent)
        cond_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(cond_frame, text="Condition (optional):", font=("Arial", 9)).pack(side="left", padx=(0, 5))
        cond_var = tk.StringVar(value=cond_val)
        tk.Entry(cond_frame, textvariable=cond_var, width=35).pack(side="left")
        widgets["condition_expr"] = cond_var
    
    def _create_command_from_widgets(self, name, cmd_type_str, enabled, widgets, edit_cmd):
        """Create Command object from widget values"""
        try:
            if cmd_type_str == "Click":
                return ClickCommand(
                    name=name,
                    button_type=ButtonType(widgets["button"].get()),
                    x=widgets["x"].get(),
                    y=widgets["y"].get(),
                    humanize_delay_min_ms=50,
                    humanize_delay_max_ms=widgets["humanize_delay"].get(),
                    enabled=enabled
                )
            
            elif cmd_type_str == "KeyPress":
                return KeyPressCommand(
                    name=name,
                    key=widgets["key"].get(),
                    repeat=widgets["repeat"].get(),
                    enabled=enabled
                )
            
            elif cmd_type_str == "Text":
                return TextCommand(
                    name=name,
                    content=widgets["content"].get("1.0", tk.END).strip(),
                    text_mode=TextMode(widgets["mode"].get()),
                    speed_max_cps=widgets["speed"].get(),
                    enabled=enabled
                )
            
            elif cmd_type_str == "Wait":
                return WaitCommand(
                    name=name,
                    wait_type=WaitType(widgets["wait_type"].get()),
                    timeout_sec=widgets.get("timeout_sec", tk.IntVar(value=30)).get(),
                    enabled=enabled
                )
            
            elif cmd_type_str == "CropImage":
                from core.models import ScanMode
                return CropImageCommand(
                    name=name,
                    x1=widgets["x1"].get(),
                    y1=widgets["y1"].get(),
                    x2=widgets["x2"].get(),
                    y2=widgets["y2"].get(),
                    target_color=(widgets["color_r"].get(), widgets["color_g"].get(), widgets["color_b"].get()),
                    tolerance=widgets["tolerance"].get(),
                    scan_mode=ScanMode(widgets["scan_mode"].get()),
                    output_var=widgets["output_var"].get(),
                    enabled=enabled
                )
            
            elif cmd_type_str == "Goto":
                return GotoCommand(
                    name=name,
                    target_label=widgets["target_label"].get(),
                    condition_expr=widgets["condition_expr"].get() or None,
                    enabled=enabled
                )
            
            elif cmd_type_str == "Repeat":
                return RepeatCommand(
                    name=name,
                    count=widgets["count"].get(),
                    until_condition_expr=widgets["until_condition"].get() or None,
                    enabled=enabled
                )
            
            elif cmd_type_str == "Condition":
                return ConditionCommand(
                    name=name,
                    expr=widgets["expr"].get(),
                    then_label=widgets["then_label"].get() or None,
                    else_label=widgets["else_label"].get() or None,
                    enabled=enabled
                )
            
            elif cmd_type_str == "HotKey":
                from core.models import HotKeyOrder
                keys_str = widgets["keys"].get()
                keys_list = [k.strip() for k in keys_str.split("+") if k.strip()]
                return HotKeyCommand(
                    name=name,
                    keys=keys_list,
                    hotkey_order=HotKeyOrder(widgets["hotkey_order"].get()),
                    enabled=enabled
                )
            
            else:
                log(f"[UI] Unknown command type: {cmd_type_str}")
                return None
                
        except Exception as e:
            log(f"[UI] Error creating command: {e}")
            return None
    
    def _get_config_from_widgets(self, cmd_type, widgets):
        """Extract config from widgets (DEPRECATED - use _create_command_from_widgets)"""
        config = {}
        
        if cmd_type == "Click":
            config["button"] = widgets["button"].get()
            config["x"] = widgets["x"].get()
            config["y"] = widgets["y"].get()
            config["humanize_delay"] = widgets["humanize_delay"].get()
        
        elif cmd_type == "KeyPress":
            config["key"] = widgets["key"].get()
            config["repeat"] = widgets["repeat"].get()
        
        elif cmd_type == "Text":
            config["content"] = widgets["content"].get("1.0", tk.END).strip()
            config["mode"] = widgets["mode"].get()
            config["speed"] = widgets["speed"].get()
        
        elif cmd_type == "Wait":
            config["wait_type"] = widgets["wait_type"].get()
            if config["wait_type"] == "timeout":
                config["seconds"] = widgets.get("timeout_sec", tk.IntVar(value=1)).get()
        
        return config
    
    def _select_capture_target(self, callback=None):
        """
        Dialog UI để chọn Target Window cho capture
        - Screen (Full): lấy screen coords (mặc định)
        - Window Focus: chọn app bất kỳ bằng cách click vào
        - Worker/Emulator: lấy client coords trong emulator đó
        """
        dialog = tk.Toplevel(self.root)
        dialog.title("Select Target")
        dialog.geometry("400x350")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.resizable(False, False)
        
        # Center on parent
        dialog.geometry(f"+{self.root.winfo_x() + 100}+{self.root.winfo_y() + 100}")
        
        # Current selection
        current_hwnd = getattr(self, '_capture_target_hwnd', None)
        current_name = getattr(self, '_capture_target_name', 'Screen (Full)')
        
        # Title
        tk.Label(dialog, text="🎯 Select Capture Target", font=("Arial", 12, "bold")).pack(pady=10)
        
        # Current selection display
        current_frame = tk.Frame(dialog)
        current_frame.pack(fill="x", padx=15, pady=5)
        tk.Label(current_frame, text="Current:", font=("Arial", 9)).pack(side="left")
        current_label = tk.Label(current_frame, text=current_name, font=("Arial", 9, "bold"), fg="blue")
        current_label.pack(side="left", padx=5)
        
        # Listbox frame
        list_frame = ttk.LabelFrame(dialog, text="Available Targets")
        list_frame.pack(fill="both", expand=True, padx=15, pady=5)
        
        # Listbox with scrollbar
        listbox = tk.Listbox(list_frame, font=("Arial", 10), selectmode=tk.SINGLE, height=8)
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=listbox.yview)
        listbox.configure(yscrollcommand=scrollbar.set)
        listbox.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        scrollbar.pack(side="right", fill="y", pady=5)
        
        # Store target info: [(name, hwnd, display_text), ...]
        targets = []
        
        # Add Screen option
        targets.append(("Screen (Full)", None, "📺 Screen (Full)"))
        
        # Add workers
        for w in self.workers:
            if w.hwnd:
                status = "✅" if hasattr(w, 'status') and w.status == 'Ready' else "⏳"
                display = f"{status} Worker {w.id} - {w.res_width}x{w.res_height}"
                targets.append((f"Worker {w.id}", w.hwnd, display))
        
        # Add other LDPlayer windows
        try:
            from initialize_workers import detect_ldplayer_windows
            ldplayer_wins = detect_ldplayer_windows()
            existing_hwnds = {w.hwnd for w in self.workers if w.hwnd}
            
            for win in ldplayer_wins:
                if win['hwnd'] not in existing_hwnds:
                    display = f"🎮 {win['title'][:25]} ({win['width']}x{win['height']})"
                    targets.append((win['title'][:20], win['hwnd'], display))
        except:
            pass
        
        # Add picked window if not in list
        if current_hwnd is not None:
            if not any(t[1] == current_hwnd for t in targets):
                display = f"🎯 {current_name}"
                targets.append((current_name, current_hwnd, display))
        
        # Populate listbox
        selected_index = 0
        for i, (name, hwnd, display) in enumerate(targets):
            listbox.insert(tk.END, display)
            if hwnd == current_hwnd:
                selected_index = i
        
        listbox.selection_set(selected_index)
        listbox.see(selected_index)
        
        def on_select(event=None):
            selection = listbox.curselection()
            if selection:
                idx = selection[0]
                name, hwnd, display = targets[idx]
                current_label.config(text=name)
        
        listbox.bind("<<ListboxSelect>>", on_select)
        
        # Button frame
        btn_frame = tk.Frame(dialog)
        btn_frame.pack(fill="x", padx=15, pady=10)
        
        def reset_to_screen():
            """Reset capture target to full screen"""
            self._capture_target_hwnd = None
            self._capture_target_name = "Screen (Full)"
            self._target_btn_text.set("📺 Screen")
            log("[UI] Capture target reset to Screen (Full)")
            dialog.destroy()
            if callback:
                callback()
        
        def pick_window_focus():
            dialog.destroy()
            self._pick_window_by_focus(callback)
        
        def confirm_selection():
            selection = listbox.curselection()
            if selection:
                idx = selection[0]
                name, hwnd, display = targets[idx]
                self._capture_target_name = name
                self._capture_target_hwnd = hwnd
                if hwnd is None:
                    self._target_btn_text.set("📺 Screen")
                else:
                    short_name = name[:12] + "..." if len(name) > 12 else name
                    self._target_btn_text.set(f"🎯 {short_name}")
                log(f"[UI] Capture target set: {name} (hwnd={hwnd})")
            dialog.destroy()
            if callback:
                callback()
        
        # Window Focus button
        tk.Button(btn_frame, text="🎯 Window Focus", command=pick_window_focus,
                 bg="#2196F3", fg="white", font=("Arial", 10)).pack(side="left", padx=5)
        
        # Reset to Screen button
        tk.Button(btn_frame, text="📺 Reset Screen", command=reset_to_screen,
                 bg="#FF9800", fg="white", font=("Arial", 10)).pack(side="left", padx=5)
        
        # OK button
        tk.Button(btn_frame, text="✓ OK", command=confirm_selection,
                 bg="#4CAF50", fg="white", font=("Arial", 10), width=8).pack(side="right", padx=5)
        
        # Cancel button
        tk.Button(btn_frame, text="Cancel", command=dialog.destroy,
                 bg="#9E9E9E", fg="white", font=("Arial", 10), width=8).pack(side="right", padx=5)
        
        # Double-click to confirm
        def on_double_click(event):
            confirm_selection()
        listbox.bind("<Double-1>", on_double_click)
    
    def _pick_window_by_focus(self, callback=None):
        """Pick any window by clicking on it - instant detection"""
        import ctypes
        user32 = ctypes.windll.user32
        
        # Show instruction dialog
        info_dialog = tk.Toplevel(self.root)
        info_dialog.title("Window Focus Picker")
        info_dialog.geometry("350x100")
        info_dialog.transient(self.root)
        info_dialog.attributes("-topmost", True)
        
        tk.Label(info_dialog, text="🎯 Window Focus Picker", 
                font=("Arial", 11, "bold")).pack(pady=10)
        tk.Label(info_dialog, text="Click vào cửa sổ bạn muốn chọn...",
                font=("Arial", 10)).pack()
        
        status_label = tk.Label(info_dialog, text="Đang chờ...", font=("Arial", 9), fg="blue")
        status_label.pack(pady=5)
        
        cancelled = [False]
        initial_hwnd = [user32.GetForegroundWindow()]
        
        def check_focus_change():
            if cancelled[0]:
                return
            
            current_hwnd = user32.GetForegroundWindow()
            dialog_hwnd = info_dialog.winfo_id()
            root_hwnd = self.root.winfo_id()
            
            # Check if focus changed to a different window (not our dialogs)
            if current_hwnd and current_hwnd != initial_hwnd[0] and current_hwnd != dialog_hwnd and current_hwnd != root_hwnd:
                # Get window title
                length = user32.GetWindowTextLengthW(current_hwnd)
                buff = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(current_hwnd, buff, length + 1)
                title = buff.value[:25] if buff.value else "Unknown"
                
                self._capture_target_hwnd = current_hwnd
                self._capture_target_name = title
                short_name = title[:12] + "..." if len(title) > 12 else title
                self._target_btn_text.set(f"🎯 {short_name}")
                log(f"[UI] Window picked: {title} (hwnd={current_hwnd})")
                
                info_dialog.destroy()
                # Restore and bring window to front
                self.root.deiconify()
                self.root.lift()
                self.root.focus_force()
                
                # Reopen target selection dialog to show the picked window
                self.root.after(150, lambda: self._select_capture_target(callback))
                return
            
            # Continue checking every 50ms
            info_dialog.after(50, check_focus_change)
        
        def cancel():
            cancelled[0] = True
            info_dialog.destroy()
            # Restore and bring window to front
            self.root.deiconify()
            self.root.lift()
            self.root.focus_force()
            # Reopen target selection dialog
            self.root.after(150, lambda: self._select_capture_target(callback))
        
        tk.Button(info_dialog, text="Cancel", command=cancel).pack(pady=5)
        
        # Minimize main window
        self.root.iconify()
        
        # Start checking focus changes
        info_dialog.after(100, check_focus_change)
        
        # Restore main window after dialog closes
        def on_close():
            self.root.deiconify()
        info_dialog.protocol("WM_DELETE_WINDOW", lambda: [cancel(), on_close()])
        info_dialog.bind("<Destroy>", lambda e: on_close() if e.widget == info_dialog else None)
    
    def _get_emulator_hwnd_for_capture(self):
        """Get emulator hwnd for capturing - shows selection dialog if multiple available"""
        # First, try workers with hwnd
        available = []
        for w in self.workers:
            if w.hwnd:
                available.append((f"Worker {w.id} - {w.res_width}x{w.res_height}", w.hwnd))
        
        # Also detect other LDPlayer windows
        try:
            from initialize_workers import detect_ldplayer_windows
            ldplayer_wins = detect_ldplayer_windows()
            existing_hwnds = {w.hwnd for w in self.workers if w.hwnd}
            
            for win in ldplayer_wins:
                if win['hwnd'] not in existing_hwnds:
                    display = f"{win['title'][:25]} ({win['width']}x{win['height']})"
                    available.append((display, win['hwnd']))
        except Exception as e:
            log(f"[UI] Error detecting LDPlayer: {e}")
        
        if not available:
            from tkinter import messagebox
            messagebox.showwarning("Không tìm thấy", "Không có emulator/worker nào đang chạy!\nHãy Refresh Workers trước.")
            return None
        
        if len(available) == 1:
            log(f"[UI] Using single available emulator hwnd={available[0][1]}")
            return available[0][1]  # Return the only hwnd
        
        # Multiple available - show selection dialog
        S = ModernStyle
        
        dialog = tk.Toplevel(self.root)
        dialog.title("Chọn Emulator để Capture")
        dialog.geometry("320x220")
        dialog.configure(bg=S.BG_SECONDARY)
        dialog.transient(self.root)
        
        # Center dialog
        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - dialog.winfo_width()) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - dialog.winfo_height()) // 2
        dialog.geometry(f"+{x}+{y}")
        
        selected_hwnd = [None]
        
        tk.Label(dialog, text="Chọn emulator để capture:", bg=S.BG_PRIMARY, fg=S.FG_PRIMARY,
                font=(S.FONT_FAMILY, S.FONT_SIZE_SM)).pack(pady=10)
        
        listbox = tk.Listbox(dialog, height=6, bg=S.BG_CARD, fg=S.FG_PRIMARY,
                            selectbackground=S.ACCENT_BLUE, font=(S.FONT_FAMILY, S.FONT_SIZE_SM))
        listbox.pack(fill="both", expand=True, padx=10, pady=5)
        
        for name, hwnd in available:
            listbox.insert(tk.END, name)
        listbox.selection_set(0)
        
        def on_ok():
            idx = listbox.curselection()
            if idx:
                selected_hwnd[0] = available[idx[0]][1]
                log(f"[UI] Selected emulator hwnd={selected_hwnd[0]} for capture")
            dialog.destroy()
        
        def on_cancel():
            dialog.destroy()
        
        btn_frame = tk.Frame(dialog, bg=S.BG_SECONDARY)
        btn_frame.pack(pady=10)
        S.create_modern_button(btn_frame, "OK", on_ok, "accent", width=8).pack(side="left", padx=5)
        S.create_modern_button(btn_frame, "Cancel", on_cancel, "default", width=8).pack(side="left", padx=5)
        
        # Handle dialog close
        dialog.protocol("WM_DELETE_WINDOW", on_cancel)
        
        # Make dialog modal
        dialog.grab_set()
        dialog.focus_set()
        
        # Wait for dialog to close
        self.root.wait_window(dialog)
        
        return selected_hwnd[0]
    
    def _get_capture_target_rect(self):
        """
        Lấy client rect của capture target
        Returns: (x, y, w, h) hoặc None nếu là screen
        """
        import ctypes
        user32 = ctypes.windll.user32
        
        if not self._capture_target_hwnd:
            return None  # Screen mode
        
        if not user32.IsWindow(self._capture_target_hwnd):
            log(f"[UI] Target window invalid, reset to screen")
            self._capture_target_hwnd = None
            self._capture_target_name = "Screen (Full)"
            return None
        
        # Get client rect
        class RECT(ctypes.Structure):
            _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                       ("right", ctypes.c_long), ("bottom", ctypes.c_long)]
        
        class POINT(ctypes.Structure):
            _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
        
        rect = RECT()
        user32.GetClientRect(self._capture_target_hwnd, ctypes.byref(rect))
        
        # Convert client (0,0) to screen coords
        pt = POINT(0, 0)
        user32.ClientToScreen(self._capture_target_hwnd, ctypes.byref(pt))
        
        return (pt.x, pt.y, rect.right - rect.left, rect.bottom - rect.top)
    
    def _capture_click_with_hold(self, x_var, y_var, hold_var, btn_var):
        """
        Capture mouse position AND hold duration
        - Click để capture vị trí
        - Nếu là hold_left/hold_right: đo thời gian giữ chuột
        """
        import ctypes
        
        user32 = ctypes.windll.user32
        btn_type = btn_var.get()
        is_hold_mode = btn_type in ("hold_left", "hold_right")
        
        # Minimize main window
        self.root.iconify()
        self.root.update()
        
        # Wait for left mouse button release (if pressed)
        while user32.GetAsyncKeyState(0x01) & 0x8000:
            pass
        
        # Wait for click down
        while not (user32.GetAsyncKeyState(0x01) & 0x8000):
            pass
        
        # Get cursor position at click down
        class POINT(ctypes.Structure):
            _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
        
        pt = POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        screen_x, screen_y = pt.x, pt.y
        
        # Measure hold duration if in hold mode
        hold_duration_ms = 0
        if is_hold_mode:
            import time
            start_time = time.time()
            # Wait for mouse button release
            while user32.GetAsyncKeyState(0x01) & 0x8000:
                pass
            hold_duration_ms = int((time.time() - start_time) * 1000)
            hold_duration_ms = max(50, hold_duration_ms)  # Minimum 50ms
        
        # Convert based on capture target
        result_x, result_y = screen_x, screen_y
        target_rect = self._get_capture_target_rect()
        
        if target_rect:
            cx, cy, cw, ch = target_rect
            result_x = screen_x - cx
            result_y = screen_y - cy
            log(f"[UI] Captured: ({result_x},{result_y}) in {self._capture_target_name}, hold={hold_duration_ms}ms")
        else:
            log(f"[UI] Captured: screen({screen_x},{screen_y}), hold={hold_duration_ms}ms")
        
        # Restore window
        self.root.deiconify()
        self.root.update()
        
        # Update variables
        x_var.set(max(0, result_x))
        y_var.set(max(0, result_y))
        
        # Update hold duration if captured
        if is_hold_mode and hold_duration_ms > 0:
            hold_var.set(hold_duration_ms)
    
    def _capture_click_with_hold_target(self, x_var, y_var, hold_var, btn_var, target_hwnd=None, parent_dialog=None):
        """Capture click position with hold duration - supports specific target window"""
        import ctypes
        
        user32 = ctypes.windll.user32
        btn_type = btn_var.get()
        is_hold_mode = btn_type in ("hold_left", "hold_right")
        
        # Hide dialog if provided (to avoid it being captured)
        if parent_dialog:
            parent_dialog.withdraw()
            parent_dialog.update()
        
        # Minimize main window
        self.root.iconify()
        self.root.update()
        
        # Wait for left mouse button release (if pressed)
        while user32.GetAsyncKeyState(0x01) & 0x8000:
            pass
        
        # Wait for click down
        while not (user32.GetAsyncKeyState(0x01) & 0x8000):
            pass
        
        # Get cursor position at click down
        class POINT(ctypes.Structure):
            _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
        
        pt = POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        screen_x, screen_y = pt.x, pt.y
        
        # Measure hold duration if in hold mode
        hold_duration_ms = 0
        if is_hold_mode:
            import time
            start_time = time.time()
            while user32.GetAsyncKeyState(0x01) & 0x8000:
                pass
            hold_duration_ms = int((time.time() - start_time) * 1000)
            hold_duration_ms = max(50, hold_duration_ms)
        
        # Convert based on target
        result_x, result_y = screen_x, screen_y
        
        if target_hwnd:
            # Get window client rect and convert
            class RECT(ctypes.Structure):
                _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                           ("right", ctypes.c_long), ("bottom", ctypes.c_long)]
            
            rect = RECT()
            user32.GetClientRect(target_hwnd, ctypes.byref(rect))
            
            pt_origin = POINT(0, 0)
            user32.ClientToScreen(target_hwnd, ctypes.byref(pt_origin))
            
            # Convert screen coords to client coords
            result_x = screen_x - pt_origin.x
            result_y = screen_y - pt_origin.y
            
            # Clamp to window bounds
            result_x = max(0, min(result_x, rect.right - rect.left))
            result_y = max(0, min(result_y, rect.bottom - rect.top))
            
            log(f"[UI] Captured: client({result_x},{result_y}) in hwnd={target_hwnd}, hold={hold_duration_ms}ms")
        else:
            log(f"[UI] Captured: screen({screen_x},{screen_y}), hold={hold_duration_ms}ms")
        
        # Restore window
        self.root.deiconify()
        self.root.update()
        
        # Restore dialog if provided
        if parent_dialog:
            parent_dialog.deiconify()
            parent_dialog.update()
            parent_dialog.lift()
            parent_dialog.focus_force()
        
        # Update variables
        x_var.set(max(0, result_x))
        y_var.set(max(0, result_y))
        
        if is_hold_mode and hold_duration_ms > 0:
            hold_var.set(hold_duration_ms)
    
    def _capture_position_target(self, x_var, y_var, target_hwnd=None, parent_dialog=None):
        """Capture mouse position - supports specific target window"""
        import ctypes
        
        user32 = ctypes.windll.user32
        
        # Hide dialog if provided
        if parent_dialog:
            parent_dialog.withdraw()
            parent_dialog.update()
        
        # Minimize main window
        self.root.iconify()
        self.root.update()
        
        # Wait for left mouse button release (if pressed)
        while user32.GetAsyncKeyState(0x01) & 0x8000:
            pass
        
        # Wait for click
        while not (user32.GetAsyncKeyState(0x01) & 0x8000):
            pass
        
        class POINT(ctypes.Structure):
            _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
        
        pt = POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        screen_x, screen_y = pt.x, pt.y
        
        # Wait for release
        while user32.GetAsyncKeyState(0x01) & 0x8000:
            pass
        
        # Convert based on target
        result_x, result_y = screen_x, screen_y
        
        if target_hwnd:
            class RECT(ctypes.Structure):
                _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                           ("right", ctypes.c_long), ("bottom", ctypes.c_long)]
            
            rect = RECT()
            user32.GetClientRect(target_hwnd, ctypes.byref(rect))
            
            pt_origin = POINT(0, 0)
            user32.ClientToScreen(target_hwnd, ctypes.byref(pt_origin))
            
            result_x = screen_x - pt_origin.x
            result_y = screen_y - pt_origin.y
            
            result_x = max(0, min(result_x, rect.right - rect.left))
            result_y = max(0, min(result_y, rect.bottom - rect.top))
            
            log(f"[UI] Captured: client({result_x},{result_y}) in hwnd={target_hwnd}")
        else:
            log(f"[UI] Captured: screen({screen_x},{screen_y})")
        
        # Restore window
        self.root.deiconify()
        self.root.update()
        
        # Restore dialog if provided
        if parent_dialog:
            parent_dialog.deiconify()
            parent_dialog.update()
            parent_dialog.lift()
            parent_dialog.focus_force()
        
        x_var.set(max(0, result_x))
        y_var.set(max(0, result_y))
    
    def _capture_drag_path_target(self, x1_var, y1_var, x2_var, y2_var, duration_var, target_hwnd=None, parent_dialog=None):
        """Capture drag path - supports specific target window"""
        import ctypes
        import time
        
        user32 = ctypes.windll.user32
        
        # Hide dialog if provided
        if parent_dialog:
            parent_dialog.withdraw()
            parent_dialog.update()
        
        # Minimize main window
        self.root.iconify()
        self.root.update()
        
        # Wait for any button release first
        while user32.GetAsyncKeyState(0x01) & 0x8000:
            pass
        
        # Wait for mouse down (start of drag)
        while not (user32.GetAsyncKeyState(0x01) & 0x8000):
            pass
        
        class POINT(ctypes.Structure):
            _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
        
        pt = POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        start_x, start_y = pt.x, pt.y
        start_time = time.time()
        
        # Wait for mouse up (end of drag)
        while user32.GetAsyncKeyState(0x01) & 0x8000:
            pass
        
        user32.GetCursorPos(ctypes.byref(pt))
        end_x, end_y = pt.x, pt.y
        duration_ms = int((time.time() - start_time) * 1000)
        duration_ms = max(100, duration_ms)  # Minimum 100ms
        
        # Convert based on target
        if target_hwnd:
            class RECT(ctypes.Structure):
                _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                           ("right", ctypes.c_long), ("bottom", ctypes.c_long)]
            
            rect = RECT()
            user32.GetClientRect(target_hwnd, ctypes.byref(rect))
            
            pt_origin = POINT(0, 0)
            user32.ClientToScreen(target_hwnd, ctypes.byref(pt_origin))
            
            # Convert to client coords
            start_x = start_x - pt_origin.x
            start_y = start_y - pt_origin.y
            end_x = end_x - pt_origin.x
            end_y = end_y - pt_origin.y
            
            # Clamp
            max_w = rect.right - rect.left
            max_h = rect.bottom - rect.top
            start_x = max(0, min(start_x, max_w))
            start_y = max(0, min(start_y, max_h))
            end_x = max(0, min(end_x, max_w))
            end_y = max(0, min(end_y, max_h))
            
            log(f"[UI] Captured drag: ({start_x},{start_y})->({end_x},{end_y}) in {duration_ms}ms, hwnd={target_hwnd}")
        else:
            log(f"[UI] Captured drag: screen({start_x},{start_y})->({end_x},{end_y}) in {duration_ms}ms")
        
        # Restore window
        self.root.deiconify()
        self.root.update()
        
        # Restore dialog if provided
        if parent_dialog:
            parent_dialog.deiconify()
            parent_dialog.update()
            parent_dialog.lift()
            parent_dialog.focus_force()
        
        x1_var.set(max(0, start_x))
        y1_var.set(max(0, start_y))
        x2_var.set(max(0, end_x))
        y2_var.set(max(0, end_y))
        duration_var.set(duration_ms)
    
    def _capture_drag_path(self, x1_var, y1_var, x2_var, y2_var, duration_var):
        """
        Capture drag path: giữ chuột và kéo để capture hành trình
        - Start: vị trí nhấn chuột
        - End: vị trí thả chuột
        - Duration: thời gian từ lúc nhấn đến thả
        """
        import ctypes
        import time
        
        user32 = ctypes.windll.user32
        
        # Minimize main window
        self.root.iconify()
        self.root.update()
        
        # Wait for any button release first
        while user32.GetAsyncKeyState(0x01) & 0x8000:
            pass
        
        # Wait for mouse down (start of drag)
        while not (user32.GetAsyncKeyState(0x01) & 0x8000):
            pass
        
        # Get start position
        class POINT(ctypes.Structure):
            _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
        
        pt = POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        start_x, start_y = pt.x, pt.y
        start_time = time.time()
        
        # Wait for mouse up (end of drag)
        while user32.GetAsyncKeyState(0x01) & 0x8000:
            pass
        
        # Get end position
        user32.GetCursorPos(ctypes.byref(pt))
        end_x, end_y = pt.x, pt.y
        duration_ms = int((time.time() - start_time) * 1000)
        duration_ms = max(100, duration_ms)  # Minimum 100ms
        
        # Convert based on capture target
        target_rect = self._get_capture_target_rect()
        
        if target_rect:
            cx, cy, cw, ch = target_rect
            start_x = start_x - cx
            start_y = start_y - cy
            end_x = end_x - cx
            end_y = end_y - cy
            log(f"[UI] Drag captured: ({start_x},{start_y})→({end_x},{end_y}) {duration_ms}ms in {self._capture_target_name}")
        else:
            log(f"[UI] Drag captured: screen ({start_x},{start_y})→({end_x},{end_y}) {duration_ms}ms")
        
        # Restore window
        self.root.deiconify()
        self.root.update()
        
        # Update variables
        x1_var.set(max(0, start_x))
        y1_var.set(max(0, start_y))
        x2_var.set(max(0, end_x))
        y2_var.set(max(0, end_y))
        duration_var.set(duration_ms)
    
    def _capture_position(self, x_var, y_var):
        """
        Capture mouse position on click - NO messagebox, silent capture
        - Dùng _capture_target_hwnd để xác định target
        - Nếu có target → client coords
        - Nếu không → screen coords
        """
        import ctypes
        
        user32 = ctypes.windll.user32
        
        # Minimize main window immediately (no messagebox)
        self.root.iconify()
        self.root.update()
        
        # Wait for left mouse click
        while user32.GetAsyncKeyState(0x01) & 0x8000:
            pass
        while not (user32.GetAsyncKeyState(0x01) & 0x8000):
            pass
        
        # Get cursor position at click
        class POINT(ctypes.Structure):
            _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
        
        pt = POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        screen_x, screen_y = pt.x, pt.y
        
        # Convert based on capture target
        result_x, result_y = screen_x, screen_y
        target_rect = self._get_capture_target_rect()
        
        if target_rect:
            cx, cy, cw, ch = target_rect
            # Convert to client coords (relative to target window)
            result_x = screen_x - cx
            result_y = screen_y - cy
            log(f"[UI] Captured: ({result_x},{result_y}) in {self._capture_target_name}")
        else:
            log(f"[UI] Captured: screen({screen_x},{screen_y})")
        
        # Restore window
        self.root.deiconify()
        self.root.update()
        
        # Update variables
        x_var.set(max(0, result_x))
        y_var.set(max(0, result_y))
    
    def _capture_region(self, x1_var, y1_var, x2_var, y2_var):
        """
        Capture region by two clicks - NO messagebox, silent capture
        - Click 1: góc trên-trái
        - Click 2: góc dưới-phải
        """
        import ctypes
        
        user32 = ctypes.windll.user32
        
        # Minimize app immediately
        self.root.iconify()
        self.root.update()
        
        class POINT(ctypes.Structure):
            _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
        
        def wait_for_click():
            """Wait for left mouse click and return position"""
            # Wait until button released
            while user32.GetAsyncKeyState(0x01) & 0x8000:
                pass
            # Wait for click
            while not (user32.GetAsyncKeyState(0x01) & 0x8000):
                pass
            pt = POINT()
            user32.GetCursorPos(ctypes.byref(pt))
            return pt.x, pt.y
        
        # First click
        x1_screen, y1_screen = wait_for_click()
        
        # Small delay between clicks
        import time
        time.sleep(0.2)
        
        # Second click
        x2_screen, y2_screen = wait_for_click()
        
        # Convert based on capture target
        result_x1, result_y1 = x1_screen, y1_screen
        result_x2, result_y2 = x2_screen, y2_screen
        target_rect = self._get_capture_target_rect()
        
        if target_rect:
            cx, cy, cw, ch = target_rect
            # Convert to client coords
            result_x1 = x1_screen - cx
            result_y1 = y1_screen - cy
            result_x2 = x2_screen - cx
            result_y2 = y2_screen - cy
            log(f"[UI] Captured region: ({result_x1},{result_y1})-({result_x2},{result_y2}) in {self._capture_target_name}")
        else:
            log(f"[UI] Captured region: screen({result_x1},{result_y1})-({result_x2},{result_y2})")
        
        # Restore window
        self.root.deiconify()
        self.root.update()
        
        # Normalize (ensure x1 < x2, y1 < y2)
        x1_var.set(max(0, min(result_x1, result_x2)))
        y1_var.set(max(0, min(result_y1, result_y2)))
        x2_var.set(max(0, max(result_x1, result_x2)))
        y2_var.set(max(0, max(result_y1, result_y2)))
    
    def _pick_color(self, r_var, g_var, b_var):
        """Pick color from screen pixel - NO messagebox, silent capture"""
        import ctypes
        
        user32 = ctypes.windll.user32
        
        # Minimize app immediately
        self.root.iconify()
        self.root.update()
        
        # Wait for left mouse click
        while user32.GetAsyncKeyState(0x01) & 0x8000:
            pass
        while not (user32.GetAsyncKeyState(0x01) & 0x8000):
            pass
        
        class POINT(ctypes.Structure):
            _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
        
        pt = POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        
        # Get pixel color at cursor position
        hdc = user32.GetDC(0)
        pixel = ctypes.windll.gdi32.GetPixel(hdc, pt.x, pt.y)
        user32.ReleaseDC(0, hdc)
        
        # Extract RGB from pixel (COLORREF is BGR format)
        r = pixel & 0xFF
        g = (pixel >> 8) & 0xFF
        b = (pixel >> 16) & 0xFF
        
        # Restore window
        self.root.deiconify()
        self.root.update()
        
        r_var.set(r)
        g_var.set(g)
        b_var.set(b)
        
        log(f"[UI] Picked color: RGB({r}, {g}, {b}) at ({pt.x}, {pt.y})")

    def add_macro(self):
        path = filedialog.askopenfilename(
            title="Chọn file macro",
            filetypes=[("Macro File", "*.mcr *.ahk"), ("All files", "*.*")]
        )
        if not path:
            return

        name = os.path.basename(path)
        self.macros.append({"name": name, "path": path})
        item_id = self.command_tree.insert("", tk.END, values=(name, path))
        self.command_tree_items[name] = item_id
        self._save_macros()

    def start_macro(self):
        if self.launcher.running:
            return

        selection = self.command_tree.selection()
        if not selection:
            messagebox.showwarning("Chưa chọn", "Hãy chọn 1 command để chạy")
            return

        item_id = selection[0]
        values = self.command_tree.item(item_id, "values")
        name, path = values[0], values[1]

        # Validate resolution trước khi chạy
        log(f"[UI] Validating worker resolution before start...")
        validation_issues = []
        
        for w in self.workers:
            is_valid, current, expected, msg = w.validate_resolution()
            log(f"[UI] Worker {w.id}: {msg}")
            
            if not is_valid:
                validation_issues.append(f"Worker {w.id}: {msg}")
        
        # Nếu có resolution mismatch → warn user
        if validation_issues:
            warn_msg = "⚠ Resolution Mismatch:\n\n" + "\n".join(validation_issues)
            warn_msg += "\n\nTiếp tục chạy? (Tọa độ game có thể không chính xác)"
            
            if not messagebox.askyesno("Resolution Warning", warn_msg):
                log(f"[UI] Start macro cancelled by user (resolution mismatch)")
                return
        
        log(f"[UI] Start macro: {name}")
        self.launcher.run_parallel(self.workers, path)
        self.btn_start.config(state="disabled")

    def stop_macro(self):
        log("[UI] Stop all macro")
        self.launcher.stop_all()
        self.btn_start.config(state="normal")

    def check_status(self):
        """Check ADB connection and query resolution từ từng LDPlayer"""
        from core.adb_manager import ADBManager
        from initialize_workers import detect_ldplayer_windows
        
        # DEBUG: Log root window state before refresh
        log(f"[DEBUG check_status] BEFORE refresh - root geometry: {self.root.winfo_geometry()}")
        log(f"[DEBUG check_status] BEFORE refresh - root state: {self.root.state()}")
        log(f"[DEBUG check_status] BEFORE refresh - screen: {self.root.winfo_screenwidth()}x{self.root.winfo_screenheight()}")
        
        # Refresh workers first to ensure list is up-to-date
        self._refresh_workers_silent()
        
        # DEBUG: Log root window state after refresh
        log(f"[DEBUG check_status] AFTER refresh - root geometry: {self.root.winfo_geometry()}")
        log(f"[DEBUG check_status] AFTER refresh - root state: {self.root.state()}")
        log(f"[DEBUG check_status] AFTER refresh - screen: {self.root.winfo_screenwidth()}x{self.root.winfo_screenheight()}")
        
        msg = "=== LDPlayer Detection ===\n\n"
        
        # Check windows first
        try:
            windows = detect_ldplayer_windows()
            if windows:
                msg += f"✓ Tìm thấy {len(windows)} cửa sổ LDPlayer:\n"
                for i, w in enumerate(windows, 1):
                    msg += f"   {i}. {w['title']} ({w['width']}x{w['height']})\n"
                msg += "\n"
            else:
                msg += "❌ Không phát hiện cửa sổ LDPlayer nào\n"
                msg += "   (Hãy chắc LDPlayer đang chạy và cửa sổ visible)\n\n"
        except Exception as e:
            msg += f"❌ Lỗi detect LDPlayer windows: {e}\n\n"
        
        msg += "=== ADB Device Status ===\n\n"
        
        adb = ADBManager()
        devices = adb.get_devices()
        
        if not devices:
            msg += "❌ Không tìm thấy ADB device nào\n"
            msg += "   (Hãy chắc ADB đã cấu hình hoặc LDPlayer đang chạy)\n"
            if adb.adb_path:
                msg += f"   ADB path: {adb.adb_path}\n\n"
            else:
                msg += "   ⚠ ADB không tìm thấy trong PATH\n\n"
        else:
            msg += f"✓ Tìm thấy {len(devices)} device(s)\n"
        
        # Query resolution từ từng worker
        msg += "=== Resolution Detection ===\n\n"
        for i, w in enumerate(self.workers, 1):
            msg += f"Worker {w.id}:\n"
            msg += f"  Hwnd: {w.hwnd}\n"
            msg += f"  Client Area: {w.client_w}x{w.client_h}\n"
            msg += f"  Resolution: {w.res_width}x{w.res_height}\n"
            msg += f"  Status: {w.status}\n"
            
            # Try ADB query
            if w.adb_device:
                resolution = adb.query_resolution(w.adb_device)
                if resolution:
                    msg += f"  ADB Query: ✓ {resolution[0]}x{resolution[1]}\n"
                else:
                    msg += f"  ADB Query: ✗ Failed\n"
            msg += "\n"
        
        # Show in messagebox
        detail_window = tk.Toplevel(self.root)
        detail_window.title("Worker Status Check")
        detail_window.geometry("800x400")
        text_widget = tk.Text(detail_window, wrap=tk.WORD, padx=10, pady=10)
        text_widget.pack(fill="both", expand=True)
        text_widget.insert("1.0", msg)
        text_widget.config(state="disabled")
        
        # Close button
        btn_frame = tk.Frame(detail_window)
        btn_frame.pack(fill="x", padx=10, pady=10)
        tk.Button(btn_frame, text="Close", command=detail_window.destroy).pack()

    def remove_macro(self):
        selection = self.command_tree.selection()
        if not selection:
            return

        item_id = selection[0]
        values = self.command_tree.item(item_id, "values")
        name = values[0]

        if messagebox.askyesno("Xóa", f"Xóa '{name}' khỏi danh sách?"):
            self.command_tree.delete(item_id)
            self.macros = [m for m in self.macros if m["name"] != name]
            if name in self.command_tree_items:
                del self.command_tree_items[name]
            self._save_macros()

    def _refresh_workers_silent(self):
        """Refresh workers without showing messagebox (for internal use)"""
        from initialize_workers import detect_ldplayer_windows
        from core.worker import Worker
        
        log(f"[DEBUG _refresh_workers_silent] START - root geometry: {self.root.winfo_geometry()}")
        log(f"[DEBUG _refresh_workers_silent] START - screen: {self.root.winfo_screenwidth()}x{self.root.winfo_screenheight()}")
        
        # Detect LDPlayer windows
        windows = detect_ldplayer_windows()
        
        if not windows:
            log(f"[DEBUG _refresh_workers_silent] No windows found, returning False")
            return False
        
        log(f"[DEBUG _refresh_workers_silent] Found {len(windows)} windows")
        
        # Clean up stale assignments
        current_hwnds = [str(w['hwnd']) for w in windows]
        self.worker_mgr.cleanup_stale_assignments(current_hwnds)
        
        # Update workers list
        new_workers = []
        for window in windows:
            hwnd = window['hwnd']
            
            # Filter out LDMultiPlayer window
            if 'LDMultiPlayer' in window['title'] or 'MultiPlayer' in window['title']:
                continue
            
            # Check if already assigned
            worker_id = self.worker_mgr.get_worker_id(str(hwnd))
            
            if worker_id:
                existing = [w for w in self.workers if w.id == worker_id]
                if existing:
                    # Update client rect and hwnd in case window moved/resized
                    existing[0].hwnd = hwnd
                    existing[0].client_rect = (window['x'], window['y'], window['width'], window['height'])
                    existing[0].client_w = window['width']
                    existing[0].client_h = window['height']
                    # Update emulator_name from actual window title
                    existing[0].emulator_name = window['title']
                    existing[0]._window_title = window['title']
                    new_workers.append(existing[0])
                else:
                    adb_serial = self._detect_adb_serial(window['title'], hwnd=hwnd)
                    worker = Worker(
                        worker_id=worker_id,
                        hwnd=hwnd,
                        client_rect=(window['x'], window['y'], window['width'], window['height']),
                        res_width=400, res_height=550,  # Default, will be updated from ADB
                        adb_device=adb_serial
                    )
                    worker.emulator_name = window['title']
                    self._update_worker_resolution_from_adb(worker)  # Get real resolution
                    new_workers.append(worker)
            else:
                temp_id = -(hwnd % 10000)
                adb_serial = self._detect_adb_serial(window['title'], hwnd=hwnd)
                worker = Worker(
                    worker_id=temp_id,
                    hwnd=hwnd,
                    client_rect=(window['x'], window['y'], window['width'], window['height']),
                    res_width=400, res_height=550,  # Default, will be updated from ADB
                    adb_device=adb_serial
                )
                worker._window_title = window['title']
                worker.emulator_name = window['title']
                worker._is_assigned = False
                self._update_worker_resolution_from_adb(worker)  # Get real resolution
                new_workers.append(worker)
        
        self.workers = new_workers
        self._auto_refresh_status()
        
        log(f"[DEBUG _refresh_workers_silent] END - root geometry: {self.root.winfo_geometry()}")
        log(f"[DEBUG _refresh_workers_silent] END - screen: {self.root.winfo_screenwidth()}x{self.root.winfo_screenheight()}")
        return True

    def refresh_workers(self):
        """Scan LDPlayer windows và hiển thị trong danh sách Worker Status"""
        from initialize_workers import detect_ldplayer_windows
        from core.worker import Worker
        
        log("[UI] Refreshing workers...")
        log(f"[DEBUG refresh_workers] START - root geometry: {self.root.winfo_geometry()}")
        log(f"[DEBUG refresh_workers] START - screen: {self.root.winfo_screenwidth()}x{self.root.winfo_screenheight()}")
        
        # Detect LDPlayer windows
        windows = detect_ldplayer_windows()
        
        if not windows:
            messagebox.showwarning("Refresh Workers", 
                "❌ Không tìm thấy LDPlayer nào.\n\nHãy chắc LDPlayer đang chạy.")
            return
        
        # Clean up stale assignments
        current_hwnds = [str(w['hwnd']) for w in windows]
        self.worker_mgr.cleanup_stale_assignments(current_hwnds)
        
        # Update workers list - create/update worker entries for detected windows
        new_workers = []
        for window in windows:
            hwnd = window['hwnd']
            
            # Filter out LDMultiPlayer window
            if 'LDMultiPlayer' in window['title'] or 'MultiPlayer' in window['title']:
                log(f"[UI] Filtered out: {window['title']}")
                continue
            
            # Check if already assigned
            worker_id = self.worker_mgr.get_worker_id(str(hwnd))
            
            if worker_id:
                # Find existing worker or create new with assigned ID
                existing = [w for w in self.workers if w.id == worker_id]
                if existing:
                    # Update client rect and hwnd in case window moved/resized
                    existing[0].hwnd = hwnd
                    existing[0].client_rect = (window['x'], window['y'], window['width'], window['height'])
                    existing[0].client_w = window['width']
                    existing[0].client_h = window['height']
                    # Update emulator_name from actual window title
                    existing[0].emulator_name = window['title']
                    existing[0]._window_title = window['title']
                    new_workers.append(existing[0])
                else:
                    # Detect ADB serial for this emulator
                    adb_serial = self._detect_adb_serial(window['title'], hwnd=hwnd)
                    
                    # Create worker with assigned ID
                    worker = Worker(
                        worker_id=worker_id,
                        hwnd=hwnd,
                        client_rect=(window['x'], window['y'], window['width'], window['height']),
                        res_width=400, res_height=550,  # Default, will be updated from ADB
                        adb_device=adb_serial
                    )
                    # Store emulator name
                    worker.emulator_name = window['title']
                    self._update_worker_resolution_from_adb(worker)  # Get real resolution
                    new_workers.append(worker)
            else:
                # Not assigned yet - create temp worker with negative ID (placeholder)
                temp_id = -(hwnd % 10000)  # Negative ID = not assigned
                adb_serial = self._detect_adb_serial(window['title'], hwnd=hwnd)
                
                worker = Worker(
                    worker_id=temp_id,
                    hwnd=hwnd,
                    client_rect=(window['x'], window['y'], window['width'], window['height']),
                    res_width=400, res_height=550,  # Default, will be updated from ADB
                    adb_device=adb_serial
                )
                # Store window info for display
                worker._window_title = window['title']
                worker.emulator_name = window['title']
                worker._is_assigned = False
                self._update_worker_resolution_from_adb(worker)  # Get real resolution
                new_workers.append(worker)
        
        self.workers = new_workers
        log(f"[UI] Refreshed: {len(new_workers)} LDPlayer(s) detected")
        
        # Force UI update
        self._auto_refresh_status()
        
        # Show result
        assigned = sum(1 for w in self.workers if self.worker_mgr.get_worker_id(str(w.hwnd)))
        not_assigned = len(self.workers) - assigned
        
        msg = f"✅ Tìm thấy {len(self.workers)} LDPlayer\n\n"
        if assigned:
            msg += f"📗 {assigned} đã được gán Worker ID\n"
        if not_assigned:
            msg += f"📙 {not_assigned} chưa được gán (dùng Set để gán)"
        
        messagebox.showinfo("Refresh Workers", msg)
        
    def set_worker_dialog(self):
        """
        Phân chia LDPlayer → Worker ID
        Modern Dark UI với chức năng:
        1. Scan LDPlayer windows hiện có
        2. Select/Unselect từng cái hoặc All
        3. Gán Worker ID khi user click Set Worker
        4. Xóa Worker assignment
        """
        from initialize_workers import detect_ldplayer_windows
        from core.worker import Worker
        
        S = ModernStyle
        
        # Detect LDPlayer windows
        ldplayer_windows = detect_ldplayer_windows()
        log(f"[UI] Set Worker dialog: detected {len(ldplayer_windows)} LDPlayer windows")
        
        # Create dialog với Modern Dark theme
        dialog = tk.Toplevel(self.root)
        dialog.title("Set Worker - Gán LDPlayer → Worker ID")
        dialog.geometry("450x450")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.configure(bg=S.BG_PRIMARY)
        
        # ===== TITLE =====
        header_frame = tk.Frame(dialog, bg=S.BG_SECONDARY, height=50)
        header_frame.pack(fill="x")
        header_frame.pack_propagate(False)
        
        tk.Label(header_frame, text="🔗 Gán LDPlayer Instance → Worker ID", 
                 font=(S.FONT_FAMILY, S.FONT_SIZE_LG, "bold"),
                 bg=S.BG_SECONDARY, fg=S.FG_PRIMARY).pack(pady=S.PAD_MD)
        
        ldplayer_vars = {}  # {hwnd → BooleanVar}
        ldplayer_list = []  # Will be populated by refresh
        
        # Function to refresh checkbox labels with current assignments
        def refresh_dialog():
            """Refresh checkbox labels to show current Worker assignments"""
            nonlocal ldplayer_list
            
            # Re-detect LDPlayer windows
            fresh_windows = detect_ldplayer_windows()
            ldplayer_list.clear()
            for w in fresh_windows:
                # Filter out LDMultiPlayer/MultiPlayer
                if 'LDMultiPlayer' in w['title'] or 'MultiPlayer' in w['title']:
                    log(f"[UI] Set Worker: Filtered out {w['title']}")
                    continue
                ldplayer_list.append((w['hwnd'], w['title']))
            log(f"[UI] Refresh: detected {len(ldplayer_list)} LDPlayer windows")
            
            # Clean up stale assignments (hwnd không còn tồn tại)
            current_hwnds = [str(w['hwnd']) for w in fresh_windows]
            stale_count = self.worker_mgr.cleanup_stale_assignments(current_hwnds)
            if stale_count > 0:
                log(f"[UI] Cleaned up {stale_count} stale worker assignments")
            
            for widget in scrollable_frame.winfo_children():
                widget.destroy()
            
            ldplayer_vars.clear()
            
            if not ldplayer_list:
                # Show message when no LDPlayer found
                msg_frame = tk.Frame(scrollable_frame, bg=S.BG_CARD)
                msg_frame.pack(fill="x", pady=S.PAD_LG)
                tk.Label(msg_frame, text="❌ Không tìm thấy LDPlayer nào",
                        bg=S.BG_CARD, fg=S.ACCENT_RED, 
                        font=(S.FONT_FAMILY, S.FONT_SIZE_MD, "bold")).pack(pady=S.PAD_SM)
                tk.Label(msg_frame, text="Hãy mở LDPlayer và nhấn Refresh",
                        bg=S.BG_CARD, fg=S.FG_MUTED,
                        font=(S.FONT_FAMILY, S.FONT_SIZE_SM)).pack()
                return
            
            for hwnd, title in ldplayer_list:
                var = tk.BooleanVar()
                ldplayer_vars[hwnd] = var
                
                # Get current assignment
                worker_id = self.worker_mgr.get_worker_id(str(hwnd))
                
                frame = tk.Frame(scrollable_frame, bg=S.BG_CARD)
                frame.pack(fill="x", padx=S.PAD_SM, pady=3, anchor="w")
                
                # Status indicator
                if worker_id:
                    status_color = S.ACCENT_GREEN
                    status_text = f"→ Worker {worker_id}"
                else:
                    status_color = S.FG_MUTED
                    status_text = "(Not assigned)"
                
                cb = tk.Checkbutton(frame, text=f"  {title}", variable=var,
                                   bg=S.BG_CARD, fg=S.FG_PRIMARY,
                                   selectcolor=S.BG_INPUT, activebackground=S.BG_CARD,
                                   font=(S.FONT_FAMILY, S.FONT_SIZE_SM))
                cb.pack(side="left", anchor="w")
                
                tk.Label(frame, text=status_text, bg=S.BG_CARD, fg=status_color,
                        font=(S.FONT_FAMILY, S.FONT_SIZE_SM)).pack(side="right", padx=S.PAD_SM)
        
        # ===== ACTION BUTTONS =====
        action_frame = tk.Frame(dialog, bg=S.BG_PRIMARY)
        action_frame.pack(fill="x", padx=S.PAD_MD, pady=S.PAD_SM)
        
        def assign_workers():
            """Gán Worker ID tới selected LDPlayers và tạo Worker objects"""
            selected = [hwnd for hwnd, var in ldplayer_vars.items() if var.get()]
            
            if not selected:
                messagebox.showwarning("Thông báo", "Chưa select LDPlayer nào")
                return
            
            # Auto-assign Worker IDs
            result = self.worker_mgr.auto_assign_selected([str(hwnd) for hwnd in selected])
            
            if result:
                # Tạo Worker objects cho các LDPlayer mới được gán
                new_workers_created = 0
                for hwnd in selected:
                    worker_id = self.worker_mgr.get_worker_id(str(hwnd))
                    if worker_id:
                        # Check if worker already exists
                        existing = [w for w in self.workers if w.id == worker_id]
                        if not existing:
                            # Get window info
                            try:
                                import ctypes
                                from core.tech import win32gui
                                user32 = ctypes.windll.user32
                                
                                rect = win32gui.GetWindowRect(hwnd)
                                x, y, right, bottom = rect
                                width, height = right - x, bottom - y
                                
                                # Get window title (emulator name)
                                length = user32.GetWindowTextLengthW(hwnd)
                                buff = ctypes.create_unicode_buffer(length + 1)
                                user32.GetWindowTextW(hwnd, buff, length + 1)
                                emulator_name = buff.value if buff.value else f"LDPlayer-{worker_id}"
                                
                                # Detect ADB serial
                                adb_serial = self._detect_adb_serial(emulator_name, hwnd=hwnd)
                                
                                # Create new Worker
                                worker = Worker(
                                    worker_id=worker_id,
                                    hwnd=hwnd,
                                    client_rect=(x, y, width, height),
                                    res_width=400, res_height=550,  # Default, will be updated from ADB
                                    adb_device=adb_serial
                                )
                                # Add emulator name as custom attribute
                                worker.emulator_name = emulator_name
                                self._update_worker_resolution_from_adb(worker)  # Get real resolution
                                self.workers.append(worker)
                                new_workers_created += 1
                                log(f"[UI] Created Worker {worker_id} '{emulator_name}' (ADB: {adb_serial}) for hwnd={hwnd}")
                            except Exception as e:
                                log(f"[UI] Failed to create worker: {e}")
                
                msg = f"✅ Đã gán {len(result)} LDPlayer(s)\n\n"
                for ldplayer_id, worker_id in result.items():
                    msg += f"  hwnd {ldplayer_id} → Worker {worker_id}\n"
                
                if new_workers_created > 0:
                    msg += f"\n🆕 Tạo {new_workers_created} Worker mới"
                
                # NOTE: Không tự động set capture target nữa
                # User phải chủ động chọn target qua "Select Target" button
                # để tránh việc bị ràng buộc vào emulator bounds khi crop
                
                messagebox.showinfo("Thành công", msg)
                log(f"[UI] Assigned {len(result)} LDPlayer(s) to Worker IDs")
                
                # Update status display
                self._auto_refresh_status()
            else:
                messagebox.showinfo("Thông báo", "✓ Tất cả đã được gán trước đó")
            
            # Refresh dialog
            refresh_dialog()
        
        def delete_worker():
            """Xóa Worker assignment của LDPlayer được select"""
            selected = [hwnd for hwnd, var in ldplayer_vars.items() if var.get()]
            
            if not selected:
                messagebox.showwarning("Thông báo", "Vui lòng select LDPlayer muốn xóa Worker")
                return
            
            # Delete Worker của tất cả selected LDPlayers
            deleted_count = 0
            workers_to_remove = []
            
            for hwnd in selected:
                worker_id = self.worker_mgr.get_worker_id(str(hwnd))
                if worker_id:
                    # Remove from assignment manager
                    if self.worker_mgr.remove_worker(str(hwnd)):
                        deleted_count += 1
                        # Mark worker for removal from list
                        for w in self.workers:
                            if w.id == worker_id:
                                workers_to_remove.append(w)
            
            # Remove workers from list
            for w in workers_to_remove:
                self.workers.remove(w)
            
            if deleted_count > 0:
                messagebox.showinfo("Thành công", f"✅ Đã xóa {deleted_count} Worker assignment(s)")
                log(f"[UI] Deleted {deleted_count} Worker assignment(s)")
                self._auto_refresh_status()
            else:
                messagebox.showwarning("Thông báo", "Không có LDPlayer nào được gán Worker")
            
            # Refresh dialog
            refresh_dialog()
        
        # Buttons with Modern Style
        tk.Button(action_frame, text="Set Worker", command=assign_workers,
                  bg=S.ACCENT_GREEN, fg="white", font=(S.FONT_FAMILY, S.FONT_SIZE_SM, "bold"),
                  relief="flat", cursor="hand2", width=12).pack(side="left", padx=3)
        tk.Button(action_frame, text="Delete", command=delete_worker,
                  bg=S.ACCENT_RED, fg="white", font=(S.FONT_FAMILY, S.FONT_SIZE_SM, "bold"),
                  relief="flat", cursor="hand2", width=12).pack(side="left", padx=3)
        tk.Button(action_frame, text="Refresh", command=refresh_dialog,
                  bg=S.ACCENT_ORANGE, fg="white", font=(S.FONT_FAMILY, S.FONT_SIZE_SM, "bold"),
                  relief="flat", cursor="hand2", width=10).pack(side="left", padx=3)
        
        def close_and_refresh():
            self._refresh_workers_silent()
            dialog.destroy()
        
        tk.Button(action_frame, text="✓ OK", command=close_and_refresh,
                  bg=S.ACCENT_BLUE, fg="white", font=(S.FONT_FAMILY, S.FONT_SIZE_SM, "bold"),
                  relief="flat", cursor="hand2", width=8).pack(side="left", padx=3)
        
        # ===== LDPLAYER LIST FRAME =====
        list_frame = tk.LabelFrame(dialog, text=" 📱 LDPlayer Instances ", 
                                   font=(S.FONT_FAMILY, S.FONT_SIZE_MD, "bold"),
                                   bg=S.BG_CARD, fg=S.FG_ACCENT,
                                   padx=S.PAD_SM, pady=S.PAD_SM)
        list_frame.pack(fill="both", expand=True, padx=S.PAD_MD, pady=(0, S.PAD_MD))
        
        # ===== SELECT ALL CHECKBOX =====
        select_all_var = tk.BooleanVar()
        
        def toggle_select_all():
            """Toggle all checkboxes based on Select All state"""
            is_selected = select_all_var.get()
            for var in ldplayer_vars.values():
                var.set(is_selected)
        
        select_all_frame = tk.Frame(list_frame, bg=S.BG_CARD)
        select_all_frame.pack(fill="x", padx=S.PAD_SM, pady=S.PAD_XS)
        tk.Checkbutton(select_all_frame, text="Select All", variable=select_all_var,
                      command=toggle_select_all, font=(S.FONT_FAMILY, S.FONT_SIZE_SM, "bold"),
                      bg=S.BG_CARD, fg=S.FG_PRIMARY, selectcolor=S.BG_INPUT,
                      activebackground=S.BG_CARD).pack(anchor="w")
        
        # Separator
        ttk.Separator(list_frame, orient="horizontal").pack(fill="x", pady=S.PAD_XS)
        
        # Canvas + Scrollbar
        canvas = tk.Canvas(list_frame, bg=S.BG_CARD, highlightthickness=0)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg=S.BG_CARD)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Initial load
        refresh_dialog()

    # ================= STATUS =================

    def _auto_refresh_status(self):
        S = ModernStyle  # For zebra striping
        
        # Preserve current selection
        selected_ids = []
        for item in self.worker_tree.selection():
            values = self.worker_tree.item(item, "values")
            if values:
                selected_ids.append(str(values[0]))  # Store display ID as string
        
        # Clear existing items
        for item in self.worker_tree.get_children():
            self.worker_tree.delete(item)

        running = self.launcher.get_running_workers()

        for idx, w in enumerate(self.workers):
            # Check if worker is assigned
            is_assigned = self.worker_mgr.get_worker_id(str(w.hwnd)) is not None
            
            # Determine status
            if not is_assigned:
                status = "READY"  # Ready to be assigned
                worker_id_text = "Not assigned"
            elif hasattr(w, 'paused') and w.paused:
                status = "PAUSED"
                worker_id_text = f"Worker {w.id}"
            elif hasattr(w, 'stopped') and not w.stopped and hasattr(w, '_execution_thread') and w._execution_thread and w._execution_thread.is_alive():
                status = "RUNNING"
                worker_id_text = f"Worker {w.id}"
            elif not w.is_ready():
                status = "NOT READY"
                worker_id_text = f"Worker {w.id}"
            elif w.id in running:
                status = "RUNNING"
                worker_id_text = f"Worker {w.id}"
            else:
                status = "READY"
                worker_id_text = f"Worker {w.id}"

            # Extract name from emulator_name, _window_title, or fallback
            name = None
            if hasattr(w, 'emulator_name') and w.emulator_name:
                name = w.emulator_name
            elif hasattr(w, '_window_title') and w._window_title:
                name = w._window_title
            
            # Fallback if no name found
            if not name:
                name = f"LDPlayer-{w.id}" if w.id > 0 else f"LDPlayer (hwnd:{w.hwnd})"
            
            # Display ID: use actual worker_id if assigned, otherwise show index
            display_id = w.id if w.id > 0 else idx + 1
            
            # Check if worker has custom actions
            has_custom = w.id > 0 and w.id in self._worker_actions and len(self._worker_actions[w.id]) > 0
            custom_count = len(self._worker_actions.get(w.id, [])) if w.id > 0 else 0

            # Actions column shows clickable text + custom indicator
            if not is_assigned:
                actions_text = "[Set Worker]"
            elif has_custom:
                actions_text = f"[▶ ⏸ ⏹] ✏️{custom_count}"
            else:
                actions_text = "[▶ ⏸ ⏹]"

            # Determine row tag for zebra striping + status
            row_tag = 'evenrow' if idx % 2 == 0 else 'oddrow'
            status_tags = {
                "RUNNING": "running",
                "PAUSED": "warning",
                "NOT READY": "error",
            }
            tags = [row_tag]
            if status in status_tags:
                tags.append(status_tags[status])
            
            # Different tag for not assigned
            if not is_assigned:
                tags.append("warning")  # Yellow-ish for "needs action"

            # Insert row with new column order: ID, Name, Worker, Status (removed Actions)
            item_id = self.worker_tree.insert("", tk.END, values=(display_id, name, worker_id_text, status), tags=tags)
            if w.id > 0:
                self.worker_tree_items[w.id] = item_id

        # Restore selection
        if selected_ids:
            for item in self.worker_tree.get_children():
                values = self.worker_tree.item(item, "values")
                if values and str(values[0]) in selected_ids:
                    self.worker_tree.selection_add(item)

        self.root.after(self.REFRESH_MS, self._auto_refresh_status)

    # ================= HOTKEY SETTINGS =================
    
    def _load_hotkey_settings(self):
        """Load hotkey settings from config file"""
        config_path = "data/hotkey_settings.json"
        default_settings = {
            "record": "F9",
            "play": "F10",
            "pause": "F11",
            "stop": "F12"
        }
        try:
            if os.path.exists(config_path):
                with open(config_path, "r") as f:
                    settings = json.load(f)
                    # Merge with defaults
                    for key in default_settings:
                        if key not in settings:
                            settings[key] = default_settings[key]
                    return settings
        except Exception as e:
            log(f"[UI] Failed to load hotkey settings: {e}")
        return default_settings
    
    def _save_hotkey_settings(self):
        """Save hotkey settings to config file"""
        config_path = "data/hotkey_settings.json"
        try:
            os.makedirs("data", exist_ok=True)
            with open(config_path, "w") as f:
                json.dump(self._hotkey_settings, f, indent=2)
            log("[UI] Hotkey settings saved")
        except Exception as e:
            log(f"[UI] Failed to save hotkey settings: {e}")
    
    def _update_button_hotkey_text(self):
        """Update button text to show bound hotkeys"""
        record_key = self._hotkey_settings.get("record", "")
        play_key = self._hotkey_settings.get("play", "")
        pause_key = self._hotkey_settings.get("pause", "")
        stop_key = self._hotkey_settings.get("stop", "")
        
        # Update button text
        self.btn_record.config(text=f"⏺ Record ({record_key})" if record_key else "⏺ Record", width=14)
        self.btn_play.config(text=f"▶ Play ({play_key})" if play_key else "▶ Play", width=12)
        self.btn_pause.config(text=f"⏸ Pause ({pause_key})" if pause_key else "⏸ Pause", width=13)
        self.btn_stop.config(text=f"⏹ Stop ({stop_key})" if stop_key else "⏹ Stop", width=12)
    
    def _open_settings_dialog(self):
        """Open settings dialog for hotkey binding - Dark theme"""
        S = ModernStyle
        
        dialog = tk.Toplevel(self.root)
        dialog.title("⚙ Cài đặt - Phím tắt")
        dialog.geometry("450x580")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.resizable(False, False)
        dialog.configure(bg=S.BG_PRIMARY)
        
        # Header
        header = tk.Frame(dialog, bg=S.BG_SECONDARY, height=55)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="⚙ Cài đặt Phím tắt", font=(S.FONT_FAMILY, S.FONT_SIZE_XXL, "bold"),
                bg=S.BG_SECONDARY, fg=S.FG_PRIMARY).pack(side="left", padx=S.PAD_XL, pady=S.PAD_LG)
        
        tk.Label(dialog, text="Nhấn nút rồi bấm phím để gán", 
                font=(S.FONT_FAMILY, S.FONT_SIZE_SM), fg=S.FG_MUTED, bg=S.BG_PRIMARY).pack(pady=S.PAD_MD)
        
        # Hotkey entries frame
        hotkey_frame = tk.LabelFrame(dialog, text=" Phím tắt ", font=(S.FONT_FAMILY, S.FONT_SIZE_MD, "bold"),
                                     bg=S.BG_CARD, fg=S.FG_ACCENT)
        hotkey_frame.pack(fill="x", padx=S.PAD_XL, pady=S.PAD_LG)
        
        hotkey_vars = {}
        hotkey_buttons = {}
        
        hotkeys = [
            ("record", "⏺ Ghi:", self._hotkey_settings.get("record", "")),
            ("play", "▶ Phát:", self._hotkey_settings.get("play", "")),
            ("pause", "⏸ Tạm dừng:", self._hotkey_settings.get("pause", "")),
            ("stop", "⏹ Dừng:", self._hotkey_settings.get("stop", ""))
        ]
        
        for key, label, current_value in hotkeys:
            row = tk.Frame(hotkey_frame, bg=S.BG_CARD)
            row.pack(fill="x", padx=S.PAD_MD, pady=S.PAD_SM)
            
            tk.Label(row, text=label, font=(S.FONT_FAMILY, S.FONT_SIZE_MD), width=12, anchor="w",
                    bg=S.BG_CARD, fg=S.FG_PRIMARY).pack(side="left")
            
            var = tk.StringVar(value=current_value)
            hotkey_vars[key] = var
            
            # Entry to show current hotkey
            entry = tk.Entry(row, textvariable=var, width=15, font=(S.FONT_FAMILY, S.FONT_SIZE_MD), 
                           state="readonly", justify="center",
                           bg=S.BG_INPUT, fg=S.FG_PRIMARY, readonlybackground=S.BG_INPUT,
                           relief="flat", highlightthickness=1, highlightbackground=S.BORDER_COLOR)
            entry.pack(side="left", padx=5)
            
            # Bind button
            def create_bind_callback(k, v, e):
                def bind_hotkey():
                    self._capture_hotkey(k, v, e, dialog, hotkey_vars)
                return bind_hotkey
            
            btn = tk.Button(row, text="🎯 Gán", command=create_bind_callback(key, var, entry),
                          bg=S.ACCENT_BLUE, fg=S.FG_PRIMARY, font=(S.FONT_FAMILY, S.FONT_SIZE_SM),
                          relief="flat", cursor="hand2")
            btn.pack(side="left", padx=5)
            hotkey_buttons[key] = btn
            
            # Unbind button
            def create_unbind_callback(v):
                def unbind_hotkey():
                    v.set("")
                return unbind_hotkey
            
            tk.Button(row, text="🚫", command=create_unbind_callback(var),
                     bg=S.ACCENT_RED, fg=S.FG_PRIMARY, font=(S.FONT_FAMILY, S.FONT_SIZE_SM),
                     relief="flat", cursor="hand2", width=3).pack(side="left", padx=2)
        
        # Info
        info_frame = tk.Frame(dialog, bg=S.BG_PRIMARY)
        info_frame.pack(fill="x", padx=S.PAD_XL, pady=S.PAD_MD)
        tk.Label(info_frame, text="💡 Mẹo: Sử dụng F1-F12, hoặc tổ hợp như Ctrl+Shift+R",
                font=(S.FONT_FAMILY, S.FONT_SIZE_SM), fg=S.FG_MUTED, bg=S.BG_PRIMARY).pack()
        
        # Play All mini toolbar info
        toolbar_info_frame = tk.LabelFrame(dialog, text=" Mini Toolbar - Phát Tất cả (Cố định) ", 
                                          font=(S.FONT_FAMILY, S.FONT_SIZE_MD, "bold"),
                                          bg=S.BG_CARD, fg=S.ACCENT_CYAN)
        toolbar_info_frame.pack(fill="x", padx=S.PAD_XL, pady=S.PAD_MD)
        
        tk.Label(toolbar_info_frame, text="F10 = ▶ Phát tất cả", 
                font=(S.FONT_FAMILY, S.FONT_SIZE_MD), bg=S.BG_CARD, fg=S.FG_PRIMARY,
                anchor="w").pack(padx=S.PAD_MD, pady=2, fill="x")
        tk.Label(toolbar_info_frame, text="F12 = ⏹ Dừng tất cả", 
                font=(S.FONT_FAMILY, S.FONT_SIZE_MD), bg=S.BG_CARD, fg=S.FG_PRIMARY,
                anchor="w").pack(padx=S.PAD_MD, pady=2, fill="x")
        tk.Label(toolbar_info_frame, text="⚠️ Chỉ hoạt động khi mini toolbar được focus", 
                font=(S.FONT_FAMILY, S.FONT_SIZE_SM), bg=S.BG_CARD, fg=S.FG_MUTED,
                anchor="w").pack(padx=S.PAD_MD, pady=2, fill="x")
        # ==================== DEBUG MODE ====================
        debug_frame = tk.LabelFrame(dialog, text=" 🔧 Chế độ Debug (Nhà phát triển) ", 
                                   font=(S.FONT_FAMILY, S.FONT_SIZE_MD, "bold"),
                                   bg=S.BG_CARD, fg=S.ACCENT_PURPLE)
        debug_frame.pack(fill="x", padx=S.PAD_XL, pady=S.PAD_MD)
        
        from utils.logger import is_debug_mode, set_debug_mode
        
        debug_var = tk.BooleanVar(value=is_debug_mode())
        
        debug_row = tk.Frame(debug_frame, bg=S.BG_CARD)
        debug_row.pack(fill="x", padx=S.PAD_MD, pady=S.PAD_SM)
        
        tk.Checkbutton(debug_row, text="Hiển thị Log Console (dành cho dev)", variable=debug_var,
                      font=(S.FONT_FAMILY, S.FONT_SIZE_MD), bg=S.BG_CARD, fg=S.FG_PRIMARY,
                      selectcolor=S.BG_INPUT, activebackground=S.BG_CARD).pack(side="left")
        
        tk.Label(debug_frame, text="💡 Tắt khi gửi sản phẩm cho người dùng cuối",
                font=(S.FONT_FAMILY, S.FONT_SIZE_XS), bg=S.BG_CARD, fg=S.FG_MUTED).pack(padx=S.PAD_MD, pady=2)
        
        # Buttons
        btn_frame = tk.Frame(dialog, bg=S.BG_PRIMARY)
        btn_frame.pack(fill="x", padx=S.PAD_XL, pady=S.PAD_XL)
        
        def save_and_close():
            # Update settings
            for key, var in hotkey_vars.items():
                self._hotkey_settings[key] = var.get()
            self._save_hotkey_settings()
            self._update_button_hotkey_text()
            self._register_global_hotkeys()
            
            # Save debug mode
            set_debug_mode(debug_var.get())
            
            dialog.destroy()
        
        def reset_defaults():
            hotkey_vars["record"].set("F9")
            hotkey_vars["play"].set("F10")
            hotkey_vars["pause"].set("F11")
            hotkey_vars["stop"].set("F12")
        
        tk.Button(btn_frame, text="✓ Lưu", command=save_and_close,
                 bg=S.ACCENT_GREEN, fg=S.FG_PRIMARY, font=(S.FONT_FAMILY, S.FONT_SIZE_MD, "bold"), 
                 width=10, relief="flat", cursor="hand2").pack(side="left", padx=5)
        tk.Button(btn_frame, text="Mặc định", command=reset_defaults,
                 bg=S.ACCENT_ORANGE, fg=S.FG_PRIMARY, font=(S.FONT_FAMILY, S.FONT_SIZE_SM), 
                 width=12, relief="flat", cursor="hand2").pack(side="left", padx=5)
        tk.Button(btn_frame, text="Hủy", command=dialog.destroy,
                 bg=S.BTN_SECONDARY, fg=S.FG_PRIMARY, font=(S.FONT_FAMILY, S.FONT_SIZE_SM), 
                 width=10, relief="flat", cursor="hand2").pack(side="left", padx=5)
    
    def _capture_hotkey(self, key_name, var, entry, parent_dialog, all_hotkey_vars=None):
        """Capture a hotkey press"""
        # IMPORTANT: Temporarily unregister global hotkeys to prevent them from triggering
        self._unregister_global_hotkeys()
        
        S = ModernStyle
        
        capture_dialog = tk.Toplevel(parent_dialog)
        capture_dialog.title(f"Bind Hotkey for {key_name.title()}")
        capture_dialog.geometry("300x150")
        capture_dialog.transient(parent_dialog)
        capture_dialog.grab_set()
        capture_dialog.resizable(False, False)
        capture_dialog.configure(bg=S.BG_SECONDARY)
        
        # Center on parent
        capture_dialog.geometry(f"+{parent_dialog.winfo_x() + 50}+{parent_dialog.winfo_y() + 100}")
        
        tk.Label(capture_dialog, text="Press any key or combination...", 
                font=(S.FONT_FAMILY, S.FONT_SIZE_LG), bg=S.BG_SECONDARY, fg=S.FG_PRIMARY).pack(pady=15)
        
        status_label = tk.Label(capture_dialog, text="Waiting...", 
                               font=(S.FONT_FAMILY, S.FONT_SIZE_MD), fg=S.ACCENT_BLUE, bg=S.BG_SECONDARY)
        status_label.pack()
        
        conflict_label = tk.Label(capture_dialog, text="", font=(S.FONT_FAMILY, S.FONT_SIZE_SM), 
                                 fg=S.ACCENT_ORANGE, bg=S.BG_SECONDARY)
        conflict_label.pack()
        
        captured_key = [None]
        modifier_state = {"ctrl": False, "alt": False, "shift": False}
        
        def on_key_press(event):
            key = event.keysym
            
            # Track modifier keys
            if key in ('Control_L', 'Control_R'):
                modifier_state["ctrl"] = True
                status_label.config(text="Ctrl + ... (press a key)")
                return
            if key in ('Alt_L', 'Alt_R'):
                modifier_state["alt"] = True
                status_label.config(text="Alt + ... (press a key)")
                return
            if key in ('Shift_L', 'Shift_R'):
                modifier_state["shift"] = True
                status_label.config(text="Shift + ... (press a key)")
                return
            
            # Build key string from tracked modifiers
            parts = []
            if modifier_state["ctrl"]:
                parts.append("Ctrl")
            if modifier_state["alt"]:
                parts.append("Alt")
            if modifier_state["shift"]:
                parts.append("Shift")
            
            # Format key name
            if len(key) == 1:
                parts.append(key.upper())
            else:
                parts.append(key)
            
            captured_key[0] = "+".join(parts)
            status_label.config(text=f"Captured: {captured_key[0]}", fg=S.ACCENT_GREEN)
            
            # Check for conflicts with other hotkeys
            conflict_action = None
            if all_hotkey_vars:
                for action, hk_var in all_hotkey_vars.items():
                    if action != key_name and hk_var.get().lower() == captured_key[0].lower():
                        conflict_action = action
                        break
            
            if conflict_action:
                conflict_label.config(text=f"⚠️ Already bound to '{conflict_action.title()}'", fg=S.ACCENT_ORANGE)
            else:
                conflict_label.config(text="")
            
            # Auto close after short delay
            capture_dialog.after(500, lambda: finish_capture())
        
        def on_key_release(event):
            key = event.keysym
            if key in ('Control_L', 'Control_R'):
                modifier_state["ctrl"] = False
            if key in ('Alt_L', 'Alt_R'):
                modifier_state["alt"] = False
            if key in ('Shift_L', 'Shift_R'):
                modifier_state["shift"] = False
        
        def finish_capture():
            if captured_key[0]:
                var.set(captured_key[0])
            # Re-register global hotkeys when done
            self._register_global_hotkeys()
            capture_dialog.destroy()
        
        def cancel_capture():
            # Re-register global hotkeys when cancelled
            self._register_global_hotkeys()
            capture_dialog.destroy()
        
        # Handle window close button (X)
        capture_dialog.protocol("WM_DELETE_WINDOW", cancel_capture)
        
        capture_dialog.bind("<KeyPress>", on_key_press)
        capture_dialog.bind("<KeyRelease>", on_key_release)
        capture_dialog.focus_set()
        
        # Cancel button
        tk.Button(capture_dialog, text="Cancel", command=cancel_capture,
                 font=("Arial", 9)).pack(pady=10)
    
    def _show_guide_dialog(self):
        """Show guide dialog for coordinate modes"""
        S = ModernStyle
        
        dialog = tk.Toplevel(self.root)
        dialog.title("📖 Hướng Dẫn Sử Dụng")
        dialog.geometry("700x520")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.resizable(False, False)
        dialog.configure(bg=S.BG_PRIMARY)
        
        # Header
        header = tk.Frame(dialog, bg=S.BG_SECONDARY, height=100)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="📖 Hướng Dẫn Sử Dụng", 
                bg=S.BG_SECONDARY, fg=S.FG_PRIMARY).pack(expand=True)
        tk.Label(header, text="⚠️ ADB Giả Lập: Settings → Khác → Debug ADB", 
                font=(S.FONT_FAMILY, 12, "bold"),
                bg=S.BG_SECONDARY, fg=S.FG_PRIMARY).pack(expand=True)
        
        # Content frame with scrollbar
        content_frame = tk.Frame(dialog, bg=S.BG_PRIMARY)
        content_frame.pack(fill="both", expand=True, padx=S.PAD_MD, pady=S.PAD_MD)
        
        canvas = tk.Canvas(content_frame, bg=S.BG_PRIMARY, highlightthickness=0)
        scrollbar = ttk.Scrollbar(content_frame, orient="vertical", command=canvas.yview)
        scrollable = tk.Frame(canvas, bg=S.BG_PRIMARY)
        
        scrollable.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Mouse wheel scroll
        def on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", on_mousewheel)
        
        # Guide content - simplified
        guide_sections = [
            {
                "title": "SETUP NHANH",
                "color": S.ACCENT_RED,
                "content": [
                    "B1: Vào Giả Lập => Cài Đặt => Khác => Debug ADB => Kết Nối Local",
                    "B2: Hiển thị sẵn Màn hình Giả Lập - Không ẩn giả lập xuống",
                    "B3: Bấm Check Giả Lập để quét Simulator",
                    "B4: Bấm Set Worker => Select All => Set Worker => OK",
                    "B5: Bảng Danh Sách Action => Load => Input Files Macro vào",
                    "B6: Play All Để Trải Nghiệm",
                    "⚠️ Lưu Ý: Luôn để màn hình hiển thị để Worker chạy"
                ]
            },
            {
                "title": "FULL SCREEN",
                "color": S.ACCENT_BLUE,
                "content": [
                    "Mặc định khi không chọn worker",
                    "Record tọa độ màn hình (Screen Coordinates)",
                    "Phù hợp cho automation desktop apps"
                ]
            },
            {
                "title": "GIẢ LẬP ADB",
                "color": S.ACCENT_GREEN,
                "content": [
                    "⚠️ Bắt Buộc: Settings → Khác → Debug ADB",
                    "Check → Set Worker → Add",
                    "Target Mode = Emulator",
                    "Tọa độ cửa sổ (Client Coordinates)",
                    "Hỗ trợ ADB/PostMessage (không di chuyển chuột)"
                ]
            },
            {
                "title": "⚠️QUY TẮC QUAN TRỌNG",
                "color": S.ACCENT_RED,
                "content": [
                    "✅ Full Screen → Play Full Screen",
                    "✅ Emulator → Play Emulator",
                    "❌ KHÔNG trộn lẫn 2 modes!"
                ]
            },
            {
                "title": "CHỨC NĂNG CHUỘT",
                "color": S.ACCENT_PURPLE,
                "content": [
                    "SetCursorPos: Di chuyển chuột",
                    "PostMessage: Không di chuyển chuột",
                    "ADB Tap: Tốt nhất cho multi-worker"
                ]
            }
        ]
        
        for section in guide_sections:
            # Section card
            card = tk.Frame(scrollable, bg=S.BG_CARD)
            card.pack(fill="x", pady=4, padx=2)
            
            # Title - just colored text, no full-width bar
            tk.Label(card, text=section["title"], 
                    font=(S.FONT_FAMILY, 11, "bold"),
                    bg=S.BG_CARD, fg=section["color"]).pack(anchor="w", padx=10, pady=(8, 4))
            
            # Content - centered in card
            for line in section["content"]:
                if line:  # Skip empty lines
                    tk.Label(card, text=f"  • {line}", 
                            font=(S.FONT_FAMILY, 10),
                            bg=S.BG_CARD, fg=S.FG_PRIMARY, 
                            anchor="w").pack(anchor="w", padx=20, pady=1)
            
            # Bottom padding
            tk.Frame(card, bg=S.BG_CARD, height=6).pack(fill="x")
        
        # Bottom section with checkbox and button
        btn_frame = tk.Frame(dialog, bg=S.BG_PRIMARY)
        btn_frame.pack(fill="x", padx=S.PAD_MD, pady=S.PAD_SM)
        
        # Checkbox "Don't show again"
        dont_show_var = tk.BooleanVar(value=False)
        
        def on_close():
            canvas.unbind_all("<MouseWheel>")  # Unbind to prevent errors
            if dont_show_var.get():
                self._input_settings["show_guide_on_startup"] = False
                self._save_input_settings()
                log("[UI] Guide dialog disabled on startup")
            dialog.destroy()
        
        tk.Checkbutton(btn_frame, text="Không hiển thị lần sau", 
                      variable=dont_show_var,
                      font=(S.FONT_FAMILY, 9),
                      bg=S.BG_PRIMARY, fg=S.FG_MUTED, selectcolor=S.BG_INPUT,
                      activebackground=S.BG_PRIMARY).pack()
        
        tk.Button(btn_frame, text="✅ Đã Hiểu", command=on_close,
                 bg=S.ACCENT_GREEN, fg=S.FG_PRIMARY, 
                 font=(S.FONT_FAMILY, 10, "bold"), 
                 width=15, relief="flat", cursor="hand2").pack(pady=(5, 0))
        
        # Handle window close button (X)
        dialog.protocol("WM_DELETE_WINDOW", on_close)
    
    def _show_guide_on_startup(self):
        """Show guide dialog on startup if enabled"""
        if self._input_settings.get("show_guide_on_startup", True):
            # Delay a bit to let main window fully initialize
            self.root.after(500, self._show_guide_dialog)

    
    def _unregister_global_hotkeys(self):
        """Unregister all global hotkeys"""
        try:
            import keyboard
            keyboard.unhook_all_hotkeys()
            log("[UI] Global hotkeys unregistered")
        except ImportError:
            pass
        except Exception as e:
            log(f"[UI] Failed to unregister hotkeys: {e}")
    
    def _register_global_hotkeys(self):
        """Register global hotkeys based on settings"""
        # This uses keyboard library for global hotkeys
        try:
            import keyboard
            
            # Unregister all first
            try:
                keyboard.unhook_all_hotkeys()
            except:
                pass
            
            # Register new hotkeys
            if self._hotkey_settings.get("record"):
                keyboard.add_hotkey(self._hotkey_settings["record"].lower(), self._toggle_record)
            if self._hotkey_settings.get("play"):
                keyboard.add_hotkey(self._hotkey_settings["play"].lower(), self._toggle_play)
            if self._hotkey_settings.get("pause"):
                keyboard.add_hotkey(self._hotkey_settings["pause"].lower(), self._toggle_pause)
            if self._hotkey_settings.get("stop"):
                keyboard.add_hotkey(self._hotkey_settings["stop"].lower(), self._stop_all)
            
            log(f"[UI] Global hotkeys registered: {self._hotkey_settings}")
        except ImportError:
            log("[UI] keyboard library not installed, global hotkeys disabled")
        except Exception as e:
            log(f"[UI] Failed to register hotkeys: {e}")

    # ================= PLAYBACK TOOLBAR =================
    
    def _show_playback_toolbar(self):
        """Show floating toolbar during playback - similar to recording toolbar"""
        if self._playback_toolbar is not None:
            return
        
        toolbar = tk.Toplevel(self.root)
        toolbar.title("▶ Playing")
        toolbar.attributes("-topmost", True)
        toolbar.resizable(False, False)
        toolbar.overrideredirect(True)
        
        # Load saved position or use default
        saved_pos = self._load_toolbar_position()
        if saved_pos and saved_pos[0] is not None:
            toolbar.geometry(f"+{saved_pos[0]}+{saved_pos[1]}")
        else:
            screen_w = toolbar.winfo_screenwidth()
            screen_h = toolbar.winfo_screenheight()
            x = (screen_w - 280) // 2
            y = (screen_h - 200) // 2
            toolbar.geometry(f"+{x}+{y}")
        
        # Main frame with border
        main_frame = tk.Frame(toolbar, bg="#1B5E20", highlightbackground="#4CAF50", highlightthickness=2)
        main_frame.pack(fill="both", expand=True)
        
        # Drag handle
        drag_frame = tk.Frame(main_frame, bg="#2E7D32", cursor="fleur")
        drag_frame.pack(fill="x", padx=2, pady=(2, 0))
        
        drag_label = tk.Label(drag_frame, text="⠿ ▶ Playing", 
                              bg="#2E7D32", fg="white", font=("Arial", 8))
        drag_label.pack(fill="x", pady=2)
        
        # Drag functionality
        self._playback_toolbar_drag_data = {"x": 0, "y": 0}
        
        def start_drag(event):
            self._playback_toolbar_drag_data["x"] = event.x
            self._playback_toolbar_drag_data["y"] = event.y
        
        def do_drag(event):
            x = toolbar.winfo_x() + event.x - self._playback_toolbar_drag_data["x"]
            y = toolbar.winfo_y() + event.y - self._playback_toolbar_drag_data["y"]
            toolbar.geometry(f"+{x}+{y}")
        
        drag_frame.bind("<ButtonPress-1>", start_drag)
        drag_frame.bind("<B1-Motion>", do_drag)
        drag_label.bind("<ButtonPress-1>", start_drag)
        drag_label.bind("<B1-Motion>", do_drag)
        
        # Buttons frame
        btn_frame = tk.Frame(main_frame, bg="#1B5E20")
        btn_frame.pack(fill="x", padx=2, pady=2)
        
        # Pause/Resume button
        pause_key = self._hotkey_settings.get("pause", "")
        pause_text = f"⏸ ({pause_key})" if pause_key else "⏸ Pause"
        self._playback_pause_btn = tk.Button(
            btn_frame, text=pause_text,
            bg="#FF9800", fg="white", font=("Arial", 9, "bold"),
            command=self._toggle_pause
        )
        self._playback_pause_btn.pack(side="left", padx=3, pady=3)
        
        # Stop button
        stop_key = self._hotkey_settings.get("stop", "")
        stop_text = f"⏹ ({stop_key})" if stop_key else "⏹ Stop"
        stop_btn = tk.Button(
            btn_frame, text=stop_text,
            bg="#f44336", fg="white", font=("Arial", 9, "bold"),
            command=self._stop_playback
        )
        stop_btn.pack(side="left", padx=3, pady=3)
        
        # ===== PLAYBACK LOG on Mini UI =====
        log_frame = tk.Frame(main_frame, bg="#1B5E20")
        log_frame.pack(fill="both", expand=True, padx=2, pady=(0, 2))
        
        # Header
        header = tk.Frame(log_frame, bg="#2E7D32")
        header.pack(fill="x")
        tk.Label(header, text="#", width=3, bg="#2E7D32", fg="#90CAF9", 
                font=("Consolas", 8, "bold")).pack(side="left")
        tk.Label(header, text="Action", width=12, anchor="w", bg="#2E7D32", fg="#90CAF9",
                font=("Consolas", 8, "bold")).pack(side="left")
        tk.Label(header, text="Label", width=10, anchor="w", bg="#2E7D32", fg="#90CAF9",
                font=("Consolas", 8, "bold")).pack(side="left")
        tk.Label(header, text="Status", width=10, bg="#2E7D32", fg="#90CAF9",
                font=("Consolas", 8, "bold")).pack(side="left")
        
        # Log listbox with scrollbar
        list_frame = tk.Frame(log_frame, bg="#1B3320")
        list_frame.pack(fill="both", expand=True)
        
        self._mini_log_canvas = tk.Canvas(list_frame, bg="#1B3320", highlightthickness=0, 
                                          width=260, height=120)
        scrollbar = tk.Scrollbar(list_frame, orient="vertical", command=self._mini_log_canvas.yview)
        
        self._mini_log_inner = tk.Frame(self._mini_log_canvas, bg="#1B3320")
        self._mini_log_canvas.create_window((0, 0), window=self._mini_log_inner, anchor="nw")
        self._mini_log_inner.bind("<Configure>", 
            lambda e: self._mini_log_canvas.configure(scrollregion=self._mini_log_canvas.bbox("all")))
        
        self._mini_log_canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Mouse wheel scroll
        def on_mousewheel(event):
            try:
                if self._mini_log_canvas.winfo_exists():
                    self._mini_log_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
            except:
                pass
        self._mini_log_canvas.bind_all("<MouseWheel>", on_mousewheel)
        
        # Store mini log rows
        self._mini_log_rows = []
        
        # Populate with actions
        self._populate_mini_playback_log()
        
        # Bind Esc to stop
        toolbar.bind("<Escape>", lambda e: self._stop_playback())
        
        self._playback_toolbar = toolbar
        
        # Hide main window
        self.root.withdraw()
    
    def _populate_mini_playback_log(self):
        """Populate mini playback log on floating toolbar"""
        if not hasattr(self, '_mini_log_inner'):
            return
        
        # Clear existing
        for widget in self._mini_log_inner.winfo_children():
            widget.destroy()
        self._mini_log_rows = []
        
        for idx, action in enumerate(self.actions):
            row = tk.Frame(self._mini_log_inner, bg="#1B3320")
            row.pack(fill="x", pady=1)
            
            idx_lbl = tk.Label(row, text=str(idx), width=3, bg="#1B3320", fg="#888888",
                              font=("Consolas", 8))
            idx_lbl.pack(side="left")
            
            action_lbl = tk.Label(row, text=action.action[:12], width=12, anchor="w",
                                 bg="#1B3320", fg="#CCCCCC", font=("Consolas", 8))
            action_lbl.pack(side="left")
            
            label_text = (action.label[:10] if action.label else "-")
            label_lbl = tk.Label(row, text=label_text, width=10, anchor="w",
                                bg="#1B3320", fg="#64B5F6", font=("Consolas", 8))
            label_lbl.pack(side="left")
            
            status_lbl = tk.Label(row, text="⏳", width=10, bg="#1B3320", fg="#888888",
                                 font=("Consolas", 8))
            status_lbl.pack(side="left")
            
            self._mini_log_rows.append({
                "frame": row,
                "idx": idx_lbl,
                "action": action_lbl,
                "label": label_lbl,
                "status": status_lbl
            })
    
    def _highlight_mini_log_row(self, index: int, status: str = "running"):
        """Highlight row in mini playback log"""
        if not hasattr(self, '_mini_log_rows') or not self._mini_log_rows:
            return
        
        colors = {
            "running": {"bg": "#4CAF50", "fg": "#FFFFFF", "status": "▶ Run"},
            "done": {"bg": "#1B3320", "fg": "#666666", "status": "✓"},
            "error": {"bg": "#B71C1C", "fg": "#FFCDD2", "status": "✗"},
            "skipped": {"bg": "#1B3320", "fg": "#666666", "status": "⊘"},
            "pending": {"bg": "#1B3320", "fg": "#888888", "status": "⏳"}
        }
        
        state = colors.get(status, colors["pending"])
        
        # Update previous row to done
        if hasattr(self, '_mini_current_row') and self._mini_current_row >= 0:
            if self._mini_current_row != index and self._mini_current_row < len(self._mini_log_rows):
                prev = self._mini_log_rows[self._mini_current_row]
                done = colors["done"]
                try:
                    if prev["frame"].winfo_exists():
                        prev["frame"].configure(bg=done["bg"])
                        prev["idx"].configure(bg=done["bg"], fg=done["fg"])
                        prev["action"].configure(bg=done["bg"], fg=done["fg"])
                        prev["label"].configure(bg=done["bg"], fg=done["fg"])
                        prev["status"].configure(bg=done["bg"], fg=done["fg"], text=done["status"])
                except tk.TclError:
                    pass  # Widget destroyed, ignore
        
        # Highlight current
        if 0 <= index < len(self._mini_log_rows):
            row = self._mini_log_rows[index]
            try:
                if row["frame"].winfo_exists():
                    row["frame"].configure(bg=state["bg"])
                    row["idx"].configure(bg=state["bg"], fg=state["fg"])
                    row["action"].configure(bg=state["bg"], fg=state["fg"])
                    row["label"].configure(bg=state["bg"], fg=state["fg"])
                    row["status"].configure(bg=state["bg"], fg=state["fg"], text=state["status"])
            except tk.TclError:
                pass  # Widget destroyed, ignore
            
            self._mini_current_row = index
            
            # Auto scroll
            if hasattr(self, '_mini_log_canvas'):
                try:
                    self._mini_log_canvas.update_idletasks()
                    row_y = row["frame"].winfo_y()
                    canvas_h = self._mini_log_canvas.winfo_height()
                    total_h = self._mini_log_inner.winfo_height()
                    if total_h > canvas_h:
                        self._mini_log_canvas.yview_moveto(max(0, (row_y - canvas_h/2) / total_h))
                except tk.TclError:
                    pass  # Widget destroyed, ignore
    
    def _hide_playback_toolbar(self):
        """Hide playback toolbar and restore main window"""
        if self._playback_toolbar is not None:
            # Save position
            try:
                geo = self._playback_toolbar.geometry()
                parts = geo.split("+")
                if len(parts) >= 3:
                    x, y = int(parts[1]), int(parts[2])
                    config_path = "data/toolbar_position.json"
                    os.makedirs("data", exist_ok=True)
                    with open(config_path, "w") as f:
                        json.dump({"x": x, "y": y}, f)
            except:
                pass
            
            self._playback_toolbar.destroy()
            self._playback_toolbar = None
        
        self.root.deiconify()
        self.root.lift()
    
    def _update_playback_toolbar_pause_button(self):
        """Update pause button text on playback toolbar"""
        if self._playback_toolbar is None or not hasattr(self, '_playback_pause_btn'):
            return
        
        pause_key = self._hotkey_settings.get("pause", "")
        if self._is_paused:
            text = f"▶ ({pause_key})" if pause_key else "▶ Resume"
            self._playback_pause_btn.config(text=text, bg="#4CAF50")
        else:
            text = f"⏸ ({pause_key})" if pause_key else "⏸ Pause"
            self._playback_pause_btn.config(text=text, bg="#FF9800")
    # ================= LEGACY COMMAND METHODS (for backward compatibility) =================
    
    def add_command(self):
        """Legacy: redirect to Add Action dialog"""
        self._open_add_action_dialog()
    
    def remove_command(self):
        """Legacy: redirect to remove action"""
        self._remove_action()
    
    def move_command_up(self):
        """Legacy: redirect to move action up"""
        self._move_action_up()
    
    def move_command_down(self):
        """Legacy: redirect to move action down"""
        self._move_action_down()
    
    def save_script(self):
        """Legacy: redirect to save actions"""
        self._save_actions()
    
    def load_script(self):
        """Legacy: redirect to load actions"""
        self._load_actions()
    
    def start_macro(self):
        """Legacy: redirect to play"""
        self._toggle_play()
    
    def stop_macro(self):
        """Legacy: redirect to stop"""
        self._stop_all()
