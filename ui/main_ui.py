import tkinter as tk
from tkinter import filedialog, messagebox, ttk, simpledialog
import json
import os
import uuid
import threading
import time
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
        return {
            "id": self.id,
            "enabled": self.enabled,
            "action": self.action,
            "value": self.value,
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
            if btn in ("hold_left", "hold_right"):
                return f"{btn} {hold_ms}ms ({x}, {y})"
            return f"{btn} ({x}, {y})"
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
        self._recorder: Optional['MacroRecorder'] = None
        self._player_thread: Optional[threading.Thread] = None
        self._playback_stop_event = threading.Event()
        self._playback_pause_event = threading.Event()
        self._current_action_index = 0
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
        
        # Worker-specific actions storage
        self._worker_actions: Dict[int, List[Action]] = {}  # worker_id -> custom actions
        self._worker_playback_threads: Dict[int, threading.Thread] = {}  # worker_id -> thread
        self._worker_stop_events: Dict[int, threading.Event] = {}  # worker_id -> stop event
        
        # Global hotkey manager
        self._hotkey_manager: Optional['GlobalHotkeyManager'] = None
        
        # Initialize Macro Manager if available (for recorder hooks)
        self._macro_manager = None
        if MACRO_RECORDER_AVAILABLE:
            self._macro_manager = get_macro_manager()

        self.root = tk.Tk()
        self.root.title("Tools LDPlayer - Action Recorder")
        self.root.geometry("950x580")  # Adjusted size

        self._build_ui()
        self._load_macros()
        self._auto_refresh_status()
        
        # Register global hotkeys on startup
        self._register_global_hotkeys()

    # ================= UI =================

    def _build_ui(self):
        root = self.root

        # ===== TOP TOOLBAR: Record/Play/Pause/Stop (per spec 1.1) =====
        top_btn_frame = tk.Frame(root)
        top_btn_frame.pack(fill="x", padx=10, pady=8)

        # Record button (toggle)
        self.btn_record = tk.Button(
            top_btn_frame, text="⏺ Record", command=self._toggle_record,
            bg="#f44336", fg="white", font=("Arial", 9, "bold"), width=10
        )
        self.btn_record.pack(side="left", padx=4)

        # Play button
        self.btn_play = tk.Button(
            top_btn_frame, text="▶ Play", command=self._toggle_play,
            bg="#4CAF50", fg="white", font=("Arial", 9, "bold"), width=10
        )
        self.btn_play.pack(side="left", padx=4)

        # Pause/Resume button (toggle)
        self.btn_pause = tk.Button(
            top_btn_frame, text="⏸ Pause", command=self._toggle_pause,
            bg="#FF9800", fg="white", font=("Arial", 9, "bold"), width=10
        )
        self.btn_pause.pack(side="left", padx=4)

        # Stop button (Esc to stop recording)
        self.btn_stop = tk.Button(
            top_btn_frame, text="⏹ Stop (Esc)", command=self._stop_all,
            bg="#9E9E9E", fg="white", font=("Arial", 9, "bold"), width=12
        )
        self.btn_stop.pack(side="left", padx=4)
        
        # Separator
        ttk.Separator(top_btn_frame, orient="vertical").pack(side="left", fill="y", padx=8)
        
        # Target Window button (for capture)
        self._target_btn_text = tk.StringVar(value="🎯 Screen")
        self.btn_target = tk.Button(
            top_btn_frame, textvariable=self._target_btn_text, command=self._select_capture_target,
            bg="#673AB7", fg="white", font=("Arial", 9, "bold"), width=14
        )
        self.btn_target.pack(side="left", padx=4)
        
        # Separator
        ttk.Separator(top_btn_frame, orient="vertical").pack(side="left", fill="y", padx=8)
        
        # Settings button
        self.btn_settings = tk.Button(
            top_btn_frame, text="⚙ Settings", command=self._open_settings_dialog,
            bg="#607D8B", fg="white", font=("Arial", 9), width=10
        )
        self.btn_settings.pack(side="left", padx=4)
        
        # Status label
        self._status_var = tk.StringVar(value="Ready")
        self._status_label = tk.Label(
            top_btn_frame, textvariable=self._status_var,
            font=("Arial", 9), fg="gray"
        )
        self._status_label.pack(side="left", padx=10)
        
        # Update button text with hotkeys
        self._update_button_hotkey_text()

        # Container frame for vertical layout
        container = tk.Frame(root)
        container.pack(fill="both", expand=True, padx=10, pady=8)

        # Worker status frame (left side)
        worker_frame = tk.LabelFrame(container, text="Trạng thái LDPlayer (Worker)")
        worker_frame.pack(side="left", fill="both", expand=True, padx=(0, 4), pady=0)

        # Worker buttons
        worker_btn_frame = tk.Frame(worker_frame)
        worker_btn_frame.pack(fill="x", padx=8, pady=6)

        tk.Button(worker_btn_frame, text="🔄 Refresh", command=self.refresh_workers).pack(side="left", padx=2)
        tk.Button(worker_btn_frame, text="⚙ Set Worker", command=self.set_worker_dialog).pack(side="left", padx=2)
        tk.Button(worker_btn_frame, text="🔍 Check", command=self.check_status).pack(side="left", padx=2)
        tk.Button(worker_btn_frame, text=" Xóa", command=self.remove_macro).pack(side="left", padx=2)

        # Worker Treeview with columns
        tree_frame = tk.Frame(worker_frame)
        tree_frame.pack(fill="both", expand=True, padx=8, pady=(0, 6))

        # Create Treeview - Added Actions column for per-worker controls
        columns = ("ID", "Name", "Worker", "Status", "Actions")
        self.worker_tree = ttk.Treeview(tree_frame, columns=columns, height=10, show="headings")

        # Define column headings and widths
        self.worker_tree.column("#0", width=0, stretch=tk.NO)
        self.worker_tree.column("ID", anchor=tk.CENTER, width=35)
        self.worker_tree.column("Name", anchor=tk.W, width=90)
        self.worker_tree.column("Worker", anchor=tk.CENTER, width=60)
        self.worker_tree.column("Status", anchor=tk.CENTER, width=70)
        self.worker_tree.column("Actions", anchor=tk.CENTER, width=90)

        self.worker_tree.heading("#0", text="", anchor=tk.W)
        self.worker_tree.heading("ID", text="ID", anchor=tk.CENTER)
        self.worker_tree.heading("Name", text="Name", anchor=tk.W)
        self.worker_tree.heading("Worker", text="Worker", anchor=tk.CENTER)
        self.worker_tree.heading("Status", text="Status", anchor=tk.CENTER)
        self.worker_tree.heading("Actions", text="Actions", anchor=tk.CENTER)

        # Add scrollbar
        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.worker_tree.yview)
        self.worker_tree.configure(yscroll=scrollbar.set)

        self.worker_tree.pack(side=tk.LEFT, fill="both", expand=True)
        scrollbar.pack(side=tk.RIGHT, fill="y")

        # Enable click events for worker row actions
        self.worker_tree.bind("<Button-1>", self._on_worker_tree_click)
        self.worker_tree.bind("<Double-1>", lambda e: "break")  # Block double-click selection

        # Store worker IDs for reference
        self.worker_tree_items = {}

        # Action list frame (right side) - per spec 1.3
        action_frame = tk.LabelFrame(container, text="Action List")
        action_frame.pack(side="left", fill="both", expand=True, padx=(4, 0), pady=0)

        # Action buttons - per spec 1.4
        action_btn_frame = tk.Frame(action_frame)
        action_btn_frame.pack(fill="x", padx=8, pady=6)

        tk.Button(action_btn_frame, text="➕ Thêm", command=self._open_add_action_dialog).pack(side="left", padx=2)
        tk.Button(action_btn_frame, text="🗑 Xóa", command=self._remove_action).pack(side="left", padx=2)
        tk.Button(action_btn_frame, text="⬆", command=self._move_action_up, width=2).pack(side="left", padx=2)
        tk.Button(action_btn_frame, text="⬇", command=self._move_action_down, width=2).pack(side="left", padx=2)
        tk.Button(action_btn_frame, text="💾 Save", command=self._save_actions).pack(side="left", padx=2)
        tk.Button(action_btn_frame, text="📂 Load", command=self._load_actions).pack(side="left", padx=2)

        # Action Treeview - NEW COLUMNS per spec: #, Action, Value, Label, Comment
        action_tree_frame = tk.Frame(action_frame)
        action_tree_frame.pack(fill="both", expand=True, padx=8, pady=(0, 6))

        # Create Treeview for actions with NEW columns
        # selectmode="extended" allows Ctrl+A, Shift+Click, Ctrl+Click multi-select
        action_columns = ("#", "Action", "Value", "Label", "Comment")
        self.action_tree = ttk.Treeview(action_tree_frame, columns=action_columns, height=10, show="headings", selectmode="extended")

        # Define column headings and widths
        self.action_tree.column("#0", width=0, stretch=tk.NO)
        self.action_tree.column("#", anchor=tk.CENTER, width=35)
        self.action_tree.column("Action", anchor=tk.W, width=100)
        self.action_tree.column("Value", anchor=tk.W, width=150)
        self.action_tree.column("Label", anchor=tk.W, width=80)
        self.action_tree.column("Comment", anchor=tk.W, width=120)

        self.action_tree.heading("#0", text="", anchor=tk.W)
        self.action_tree.heading("#", text="#", anchor=tk.CENTER)
        self.action_tree.heading("Action", text="Action", anchor=tk.W)
        self.action_tree.heading("Value", text="Value", anchor=tk.W)
        self.action_tree.heading("Label", text="Label", anchor=tk.W)
        self.action_tree.heading("Comment", text="Comment", anchor=tk.W)

        # Add scrollbar
        action_scrollbar = ttk.Scrollbar(action_tree_frame, orient=tk.VERTICAL, command=self.action_tree.yview)
        self.action_tree.configure(yscroll=action_scrollbar.set)

        self.action_tree.pack(side=tk.LEFT, fill="both", expand=True)
        action_scrollbar.pack(side=tk.RIGHT, fill="y")
        
        # Bind double-click to edit
        self.action_tree.bind("<Double-1>", self._on_action_double_click)
        # Bind click for context menu
        self.action_tree.bind("<Button-3>", self._on_action_right_click)
        # Bind Ctrl+A to select all
        self.action_tree.bind("<Control-a>", self._select_all_actions)
        # Bind Delete key to delete selected
        self.action_tree.bind("<Delete>", self._delete_selected_actions)
        # Bind Backspace as alternative delete
        self.action_tree.bind("<BackSpace>", self._delete_selected_actions)
        
        # Drag and Drop support
        self._drag_data = {"items": [], "start_y": 0}
        self.action_tree.bind("<ButtonPress-1>", self._on_drag_start)
        self.action_tree.bind("<B1-Motion>", self._on_drag_motion)
        self.action_tree.bind("<ButtonRelease-1>", self._on_drag_end)

        # Store action IDs for reference
        self.action_tree_items = {}
        
        # Setup global hotkeys (if available)
        self._setup_global_hotkeys()

    # ================= WORKER ACTIONS =================
    
    def _on_worker_tree_click(self, event):
        """Handle click on worker tree for per-row actions"""
        region = self.worker_tree.identify("region", event.x, event.y)
        column = self.worker_tree.identify_column(event.x)
        item = self.worker_tree.identify_row(event.y)
        
        if not item:
            return
        
        # Only respond to clicks on Actions column (#5)
        if column == "#5" and region == "cell":
            # Get worker ID from the row
            values = self.worker_tree.item(item, "values")
            worker_id = int(values[0])
            
            # Show action popup menu
            self._show_worker_action_menu(event, worker_id)
    
    def _show_worker_action_menu(self, event, worker_id: int):
        """Show popup menu with Play/Pause/Stop actions for worker"""
        menu = tk.Menu(self.root, tearoff=0)
        
        # Find worker
        worker = None
        for w in self.workers:
            if w.id == worker_id:
                worker = w
                break
        
        if not worker:
            return
        
        menu.add_command(label="▶ Play", command=lambda: self._play_worker(worker_id))
        menu.add_command(label="⏸ Pause", command=lambda: self._pause_worker(worker_id))
        menu.add_command(label="⏹ Stop", command=lambda: self._stop_worker(worker_id))
        menu.add_separator()
        menu.add_command(label="🔄 Restart", command=lambda: self._restart_worker(worker_id))
        menu.add_separator()
        
        # Edit custom actions
        has_custom = worker_id in self._worker_actions and len(self._worker_actions[worker_id]) > 0
        edit_label = f"✏️ Edit Actions ({len(self._worker_actions.get(worker_id, []))} custom)" if has_custom else "✏️ Edit Actions"
        menu.add_command(label=edit_label, command=lambda: self._edit_worker_actions(worker_id))
        
        if has_custom:
            menu.add_command(label="🗑️ Clear Custom Actions", command=lambda: self._clear_worker_actions(worker_id))
        
        # Display menu at cursor position
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()
    
    def _play_worker(self, worker_id: int):
        """Start or resume script execution for a worker"""
        worker = self._find_worker(worker_id)
        if not worker:
            return
        
        # Resume if paused
        if hasattr(worker, 'paused') and worker.paused:
            worker.resume()
            log(f"[UI] Worker {worker_id}: Resumed")
            return
        
        # Start new execution with current script
        if self.current_script:
            worker.start(self.current_script)
            log(f"[UI] Worker {worker_id}: Started script '{self.current_script.name}'")
        else:
            messagebox.showwarning("No Script", "Chưa có script được load. Vui lòng load script trước.")
    
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
        worker = self._find_worker(worker_id)
        if not worker:
            return
        
        if hasattr(worker, 'stop'):
            worker.stop()
            log(f"[UI] Worker {worker_id}: Stopped")
    
    def _restart_worker(self, worker_id: int):
        """Restart script execution for a worker"""
        worker = self._find_worker(worker_id)
        if not worker:
            return
        
        # Stop first
        if hasattr(worker, 'stop'):
            worker.stop()
        
        # Then start
        if self.current_script:
            worker.start(self.current_script)
            log(f"[UI] Worker {worker_id}: Restarted")
    
    def _find_worker(self, worker_id: int):
        """Find worker by ID"""
        for w in self.workers:
            if w.id == worker_id:
                return w
        return None

    def _edit_worker_actions(self, worker_id: int):
        """Open dialog to edit custom actions for a specific worker"""
        dialog = tk.Toplevel(self.root)
        dialog.title(f"Edit Actions - Worker {worker_id}")
        dialog.geometry("600x500")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Frame for action list
        list_frame = ttk.LabelFrame(dialog, text=f"Custom Actions for Worker {worker_id}")
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Treeview for actions
        columns = ("index", "type", "target", "value")
        tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=15)
        tree.heading("index", text="#")
        tree.heading("type", text="Type")
        tree.heading("target", text="Target")
        tree.heading("value", text="Value")
        tree.column("index", width=40)
        tree.column("type", width=100)
        tree.column("target", width=200)
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
                target = getattr(action, 'target', getattr(action, 'image', ''))
                value = getattr(action, 'value', getattr(action, 'timeout', ''))
                tree.insert("", tk.END, values=(i+1, action.type, target, value))
        
        refresh_tree()
        
        # Buttons frame
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(fill=tk.X, padx=10, pady=5)
        
        def copy_from_global():
            """Copy global action list to this worker"""
            if messagebox.askyesno("Confirm", "Sao chép danh sách actions chung sang Worker này?"):
                self._worker_actions[worker_id] = list(self.actions)  # Copy list
                refresh_tree()
                messagebox.showinfo("Done", f"Đã sao chép {len(self.actions)} actions")
        
        def add_from_file():
            """Load actions from a JSON file"""
            file_path = filedialog.askopenfilename(
                title="Select Macro File",
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
            )
            if file_path:
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    # Parse actions from file
                    loaded_actions = []
                    action_data = data.get('actions', data) if isinstance(data, dict) else data
                    if isinstance(action_data, list):
                        for item in action_data:
                            if isinstance(item, dict):
                                action = Action.from_dict(item)
                                loaded_actions.append(action)
                    
                    if loaded_actions:
                        if worker_id not in self._worker_actions:
                            self._worker_actions[worker_id] = []
                        self._worker_actions[worker_id].extend(loaded_actions)
                        refresh_tree()
                        messagebox.showinfo("Done", f"Đã thêm {len(loaded_actions)} actions từ file")
                except Exception as e:
                    messagebox.showerror("Error", f"Lỗi đọc file: {e}")
        
        def clear_actions():
            """Clear all custom actions for this worker"""
            if messagebox.askyesno("Confirm", "Xóa tất cả custom actions của Worker này?"):
                self._worker_actions[worker_id] = []
                refresh_tree()
        
        def remove_selected():
            """Remove selected action"""
            selection = tree.selection()
            if selection:
                indices = [int(tree.item(item)["values"][0]) - 1 for item in selection]
                indices.sort(reverse=True)  # Remove from end first
                actions = self._worker_actions.get(worker_id, [])
                for idx in indices:
                    if 0 <= idx < len(actions):
                        del actions[idx]
                refresh_tree()
        
        ttk.Button(btn_frame, text="📋 Copy từ Global", command=copy_from_global).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="📁 Load từ File", command=add_from_file).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="🗑️ Xóa Selected", command=remove_selected).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="❌ Clear All", command=clear_actions).pack(side=tk.LEFT, padx=2)
        
        # Info label
        info_label = ttk.Label(dialog, text="Worker có custom actions sẽ chạy actions riêng thay vì global list", 
                               foreground="gray")
        info_label.pack(pady=5)
        
        # Close button
        ttk.Button(dialog, text="Close", command=dialog.destroy).pack(pady=10)
    
    def _clear_worker_actions(self, worker_id: int):
        """Clear custom actions for a specific worker"""
        if messagebox.askyesno("Confirm", f"Xóa custom actions của Worker {worker_id}?"):
            if worker_id in self._worker_actions:
                del self._worker_actions[worker_id]
            log(f"[UI] Cleared custom actions for Worker {worker_id}")

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
            log(f"[UI] Failed to setup global hotkeys: {e}")
    
    def _toggle_record(self):
        """Toggle recording on/off (per spec 2)"""
        if self._is_recording:
            self._stop_recording()
        else:
            self._start_recording()
    
    def _start_recording(self):
        """Start recording user actions - V2 using new recorder adapter"""
        if self._is_playing:
            messagebox.showwarning("Warning", "Cannot record while playing")
            return
        
        # Check for recorder availability (prefer new adapter)
        if not RECORDER_ADAPTER_AVAILABLE and not MACRO_RECORDER_AVAILABLE:
            messagebox.showerror("Error", "Macro Recorder not available.\n\nPlease install pynput:\n  pip install pynput")
            return
        
        # Get target window (first worker or let user select)
        target_hwnd = self._get_target_window()
        if target_hwnd == -1:  # Cancelled
            return
        # target_hwnd = None means Full Screen mode
        
        self._target_hwnd = target_hwnd
        
        # Use new recorder adapter if available (fixes spec A1-A4 bugs)
        if RECORDER_ADAPTER_AVAILABLE:
            try:
                self._recorder = get_recorder()
                ui_hwnd = self.root.winfo_id()
                self._recorder.configure(target_hwnd=target_hwnd, ignore_ui_hwnd=ui_hwnd)
                self._recorder.start()
                self._is_recording = True
                mode_str = "Full Screen" if target_hwnd is None else f"target hwnd: {target_hwnd}"
                log(f"[UI] Recording started (V2 adapter), {mode_str}")
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
        
        # Update UI
        self._update_ui_state()
        self._status_var.set("🔴 Recording...")
        self.btn_record.config(text="⏺ Stop Rec", bg="#B71C1C")
        
        # Show floating recording toolbar
        self._show_recording_toolbar()
    
    def _show_recording_toolbar(self):
        """Show floating toolbar with Pause/Stop buttons during recording"""
        if self._recording_toolbar is not None:
            return
        
        toolbar = tk.Toplevel(self.root)
        toolbar.title("🔴 Recording")
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
            btn_frame, text="⏸ Pause",
            bg="#FF9800", fg="white", font=("Arial", 10, "bold"), width=8
        )
        self._toolbar_pause_btn.pack(side="left", padx=5, pady=5)
        # Bind ButtonPress to pause BEFORE the click is recorded
        self._toolbar_pause_btn.bind("<ButtonPress-1>", self._on_pause_button_press)
        
        # Stop button - use bind to stop BEFORE pynput gets the click
        stop_btn = tk.Button(
            btn_frame, text="⏹ Stop",
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
            self._toolbar_pause_btn.config(text="▶ Resume", bg="#4CAF50")
            self._status_var.set("⏸ Recording Paused")
            log("[UI] Recording paused")
        else:
            # Resume recording
            if hasattr(self._recorder, 'resume'):
                self._recorder.resume()
            self._toolbar_pause_btn.config(text="⏸ Pause", bg="#FF9800")
            self._status_var.set("🔴 Recording...")
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
            self._status_var.set("🔴 Recording...")
            log("[UI] Recording resumed")
        else:
            # Was recording, now paused (already paused in button press handler)
            self._recording_paused = True
            self._toolbar_pause_btn.config(text="▶ Resume", bg="#4CAF50")
            self._status_var.set("⏸ Recording Paused")
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
        self._status_var.set("Ready")
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
                        actions.append(Action(
                            action="DRAG",
                            value={
                                "button": pending_mouse_down["event"].button or "left",
                                "x1": start_x,
                                "y1": start_y,
                                "x2": end_x,
                                "y2": end_y,
                                "duration_ms": max(100, duration_ms),
                                "screen_coords": pending_mouse_down["use_screen"]
                            }
                        ))
                    else:
                        # This is a regular CLICK (or hold if duration is long)
                        btn = pending_mouse_down["event"].button or "left"
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
                                    "screen_coords": pending_mouse_down["use_screen"]
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
                                    "screen_coords": pending_mouse_down["use_screen"]
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
                    action="WHEEL",
                    value={
                        "delta": event.wheel_delta or 0,
                        "x": x,
                        "y": y,
                        "screen_coords": use_screen
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
                actions.append(Action(
                    action="CLICK",
                    value={
                        "button": event.button or "left",
                        "x": event.x or 0,
                        "y": event.y or 0
                    }
                ))
            elif event.event_type == RawEventType.MOUSE_SCROLL:
                actions.append(Action(
                    action="WHEEL",
                    value={
                        "delta": event.scroll_delta or 0,
                        "x": event.x or 0,
                        "y": event.y or 0
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
            messagebox.showwarning("Warning", "Cannot play while recording")
            return
        
        if not self.actions and not self._worker_actions:
            messagebox.showwarning("Warning", "No actions to play")
            return
        
        self._is_playing = True
        self._is_paused = False
        self._playback_stop_event.clear()
        self._playback_pause_event.clear()
        self._current_action_index = 0
        
        # Clear previous worker threads
        self._worker_playback_threads.clear()
        self._worker_stop_events.clear()
        
        # Get ready workers with valid hwnd
        ready_workers = [w for w in self.workers if w.hwnd and hasattr(w, 'status') and w.status == 'Ready']
        
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
        self._status_var.set(f"▶ Playing on {len(ready_workers)} workers..." if ready_workers else "▶ Playing...")
    
    def _worker_playback_loop(self, worker, actions: List[Action], stop_event: threading.Event):
        """Playback loop for a specific worker - runs in its own thread"""
        import ctypes
        from ctypes import wintypes
        
        target_hwnd = worker.hwnd
        worker_id = worker.id
        action_index = 0
        
        log(f"[Worker {worker_id}] Starting playback: {len(actions)} actions, hwnd={target_hwnd}")
        
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
                self._execute_action(action, target_hwnd)
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
    
    def _playback_loop(self):
        """Main playback loop running in thread"""
        import ctypes
        from ctypes import wintypes
        
        # Get target worker
        target_worker = self.workers[0] if self.workers else None
        target_hwnd = target_worker.hwnd if target_worker else None
        
        log(f"[UI] Playback loop: {len(self.actions)} actions, target_hwnd={target_hwnd}")
        
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
            
            # Skip disabled actions
            if not action.enabled:
                self._current_action_index += 1
                continue
            
            # Execute action
            try:
                self._execute_action(action, target_hwnd)
            except Exception as e:
                log(f"[UI] Action error: {e}")
                import traceback
                log(f"[UI] Traceback: {traceback.format_exc()}")
                # Per spec 3.4 - skip on error
            
            self._current_action_index += 1
        
        # Done - release any held modifiers
        self._release_all_modifiers()
        self._is_playing = False
        log("[UI] Playback complete")
        self.root.after(0, self._on_playback_complete)
    
    def _send_key(self, key: str, repeat: int = 1):
        """Send keyboard key using Win32 API - handles modifiers properly"""
        import ctypes
        
        # Virtual key codes
        VK_MAP = {
            # Modifiers
            'alt': 0x12, 'alt_l': 0x12, 'alt_r': 0x12,
            'ctrl': 0x11, 'ctrl_l': 0x11, 'ctrl_r': 0x11,
            'shift': 0x10, 'shift_l': 0x10, 'shift_r': 0x10,
            'win': 0x5B,
            # Navigation
            'tab': 0x09, 'enter': 0x0D, 'space': 0x20,
            'backspace': 0x08, 'delete': 0x2E, 'escape': 0x1B,
            'home': 0x24, 'end': 0x23,
            'page_up': 0x21, 'page_down': 0x22,
            'up': 0x26, 'down': 0x28, 'left': 0x25, 'right': 0x27,
            'insert': 0x2D,
            # Function keys
            'f1': 0x70, 'f2': 0x71, 'f3': 0x72, 'f4': 0x73,
            'f5': 0x74, 'f6': 0x75, 'f7': 0x76, 'f8': 0x77,
            'f9': 0x78, 'f10': 0x79, 'f11': 0x7A, 'f12': 0x7B,
            # Lock keys
            'caps_lock': 0x14, 'num_lock': 0x90, 'scroll_lock': 0x91,
        }
        
        MODIFIER_KEYS = {'alt', 'alt_l', 'alt_r', 'ctrl', 'ctrl_l', 'ctrl_r', 'shift', 'shift_l', 'shift_r', 'win'}
        
        # Clean up key name
        key_clean = key.lower().replace('key.', '').strip()
        
        # Get VK code
        if key_clean in VK_MAP:
            vk = VK_MAP[key_clean]
        elif len(key_clean) == 1:
            # Single character - get VK from ord
            vk = ctypes.windll.user32.VkKeyScanW(ord(key_clean)) & 0xFF
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
    
    def _execute_action(self, action: Action, target_hwnd: Optional[int]):
        """Execute a single action using SendInput (per spec 6.2)"""
        import ctypes
        from ctypes import wintypes
        
        v = action.value
        
        if action.action == "WAIT":
            time.sleep(v.get("ms", 0) / 1000.0)
        
        elif action.action == "CLICK":
            x, y = v.get("x", 0), v.get("y", 0)
            btn = v.get("button", "left")
            hold_ms = v.get("hold_ms", 0)
            screen_coords = v.get("screen_coords", False)
            
            # Convert client coords to screen if we have target window AND not already screen coords
            if target_hwnd and not screen_coords:
                pt = wintypes.POINT(x, y)
                ctypes.windll.user32.ClientToScreen(target_hwnd, ctypes.byref(pt))
                x, y = pt.x, pt.y
            # Nếu screen_coords=True thì x,y đã là screen coords, dùng trực tiếp
            
            # Move cursor
            ctypes.windll.user32.SetCursorPos(x, y)
            time.sleep(0.02)
            
            # Click based on button type
            if btn == "left":
                ctypes.windll.user32.mouse_event(0x0002, 0, 0, 0, 0)  # LEFTDOWN
                time.sleep(0.02)
                ctypes.windll.user32.mouse_event(0x0004, 0, 0, 0, 0)  # LEFTUP
            elif btn == "right":
                ctypes.windll.user32.mouse_event(0x0008, 0, 0, 0, 0)  # RIGHTDOWN
                time.sleep(0.02)
                ctypes.windll.user32.mouse_event(0x0010, 0, 0, 0, 0)  # RIGHTUP
            elif btn == "middle":
                ctypes.windll.user32.mouse_event(0x0020, 0, 0, 0, 0)  # MIDDLEDOWN
                time.sleep(0.02)
                ctypes.windll.user32.mouse_event(0x0040, 0, 0, 0, 0)  # MIDDLEUP
            elif btn == "double":
                # Double click left
                ctypes.windll.user32.mouse_event(0x0002, 0, 0, 0, 0)  # LEFTDOWN
                time.sleep(0.02)
                ctypes.windll.user32.mouse_event(0x0004, 0, 0, 0, 0)  # LEFTUP
                time.sleep(0.05)
                ctypes.windll.user32.mouse_event(0x0002, 0, 0, 0, 0)  # LEFTDOWN
                time.sleep(0.02)
                ctypes.windll.user32.mouse_event(0x0004, 0, 0, 0, 0)  # LEFTUP
            elif btn == "hold_left":
                # Hold left button for specified duration
                ctypes.windll.user32.mouse_event(0x0002, 0, 0, 0, 0)  # LEFTDOWN
                time.sleep(hold_ms / 1000.0 if hold_ms > 0 else 0.5)
                ctypes.windll.user32.mouse_event(0x0004, 0, 0, 0, 0)  # LEFTUP
            elif btn == "hold_right":
                # Hold right button for specified duration
                ctypes.windll.user32.mouse_event(0x0008, 0, 0, 0, 0)  # RIGHTDOWN
                time.sleep(hold_ms / 1000.0 if hold_ms > 0 else 0.5)
                ctypes.windll.user32.mouse_event(0x0010, 0, 0, 0, 0)  # RIGHTUP
        
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
            screen_coords = v.get("screen_coords", False)
            
            # Backward compat: nếu có delta cũ thì dùng delta
            if "delta" in v:
                delta = v.get("delta", 120)
            else:
                delta = 120 if direction == "up" else -120
            
            # Move cursor to position
            if target_hwnd and not screen_coords:
                pt = wintypes.POINT(x, y)
                ctypes.windll.user32.ClientToScreen(target_hwnd, ctypes.byref(pt))
                ctypes.windll.user32.SetCursorPos(pt.x, pt.y)
            else:
                # Screen coords - dùng trực tiếp
                ctypes.windll.user32.SetCursorPos(x, y)
            
            # Scroll nhiều lần với delay
            for _ in range(amount):
                if self._playback_stop_event.is_set():
                    break
                ctypes.windll.user32.mouse_event(0x0800, 0, 0, delta, 0)  # WHEEL
                if speed > 0:
                    time.sleep(speed / 1000.0)
        
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
                self._execute_action(nested, target_hwnd)
        
        elif action.action == "GROUP":
            # Execute grouped actions
            nested_actions = [Action.from_dict(a) for a in v.get("actions", [])]
            log(f"[Playback] Executing GROUP '{v.get('name', '')}' with {len(nested_actions)} actions")
            for nested in nested_actions:
                if self._playback_stop_event.is_set():
                    break
                self._execute_action(nested, target_hwnd)
        
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
            region = v.get("region", (0, 0, 100, 100))
            wait = WaitScreenChange(
                region=tuple(region) if isinstance(region, list) else region,
                threshold=v.get("threshold", 0.05),
                timeout_ms=v.get("timeout_ms", 30000),
                target_hwnd=target_hwnd or 0
            )
            wait.wait(self._playback_stop_event)
        
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
                finder = FindImage(
                    template_path=v.get("template_path", ""),
                    threshold=v.get("threshold", 0.8),
                    timeout_ms=v.get("timeout_ms", 5000),
                    target_hwnd=target_hwnd or 0
                )
                match = finder.find(self._playback_stop_event)
                # Store result for subsequent actions
                if hasattr(self, '_action_vars'):
                    self._action_vars["last_image_x"] = match.center_x if match.found else 0
                    self._action_vars["last_image_y"] = match.center_y if match.found else 0
                    self._action_vars["last_image_found"] = match.found
        
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
            
            # Convert to screen coords
            if target_hwnd:
                pt1 = wintypes.POINT(x1, y1)
                pt2 = wintypes.POINT(x2, y2)
                ctypes.windll.user32.ClientToScreen(target_hwnd, ctypes.byref(pt1))
                ctypes.windll.user32.ClientToScreen(target_hwnd, ctypes.byref(pt2))
                x1, y1 = pt1.x, pt1.y
                x2, y2 = pt2.x, pt2.y
            
            # Mouse button flags
            if button == "right":
                down_flag, up_flag = 0x0008, 0x0010  # RIGHTDOWN, RIGHTUP
            else:
                down_flag, up_flag = 0x0002, 0x0004  # LEFTDOWN, LEFTUP
            
            # Move to start position
            ctypes.windll.user32.SetCursorPos(x1, y1)
            time.sleep(0.02)
            
            # Press mouse button
            ctypes.windll.user32.mouse_event(down_flag, 0, 0, 0, 0)
            time.sleep(0.02)
            
            # Smooth interpolation from start to end
            steps = max(10, duration_ms // 20)  # At least 10 steps
            step_delay = duration_ms / steps / 1000.0
            
            for i in range(1, steps + 1):
                t = i / steps
                curr_x = int(x1 + t * (x2 - x1))
                curr_y = int(y1 + t * (y2 - y1))
                ctypes.windll.user32.SetCursorPos(curr_x, curr_y)
                time.sleep(step_delay)
            
            # Ensure final position
            ctypes.windll.user32.SetCursorPos(x2, y2)
            time.sleep(0.02)
            
            # Release mouse button
            ctypes.windll.user32.mouse_event(up_flag, 0, 0, 0, 0)
    
    def _on_playback_complete(self):
        """Called when playback completes"""
        self._is_playing = False
        self._current_action_index = 0
        
        # Hide playback toolbar
        self._hide_playback_toolbar()
        
        self._update_ui_state()
        self._status_var.set("Ready")
        log("[UI] Playback complete")
    
    def _toggle_pause(self):
        """Toggle pause/resume (per spec 3.2)"""
        if not self._is_playing:
            return
        
        if self._is_paused:
            self._playback_pause_event.clear()
            self._is_paused = False
            self._status_var.set("▶ Playing...")
            self.btn_pause.config(text="⏸ Pause")
            self._update_playback_toolbar_pause_button()
            log("[UI] Playback resumed")
        else:
            self._playback_pause_event.set()
            self._is_paused = True
            self._status_var.set("⏸ Paused")
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
        self._status_var.set("Ready")
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
        """Refresh action tree display"""
        for item in self.action_tree.get_children():
            self.action_tree.delete(item)
        
        for idx, action in enumerate(self.actions, 1):
            # Action column shows type with enabled state
            action_text = f"{'✓' if action.enabled else '✗'} {action.action}"
            value_text = action.get_value_summary()
            
            self.action_tree.insert("", tk.END, values=(
                idx, action_text, value_text, action.label, action.comment
            ))
    
    def _on_action_double_click(self, event):
        """Handle double-click on action row to edit"""
        item = self.action_tree.identify_row(event.y)
        if item:
            values = self.action_tree.item(item, "values")
            idx = int(values[0]) - 1
            self._open_add_action_dialog(edit_index=idx)
    
    def _on_action_right_click(self, event):
        """Handle right-click on action row - supports multi-select"""
        item = self.action_tree.identify_row(event.y)
        if item:
            # If clicked item not in selection, set it as only selection
            # Otherwise keep multi-selection
            if item not in self.action_tree.selection():
                self.action_tree.selection_set(item)
            
            selection = self.action_tree.selection()
            count = len(selection)
            
            menu = tk.Menu(self.root, tearoff=0)
            
            if count == 1:
                # Single item - show full menu
                values = self.action_tree.item(item, "values")
                idx = int(values[0]) - 1
                menu.add_command(label="✏ Edit", command=lambda: self._open_add_action_dialog(edit_index=idx))
                menu.add_command(label="✓/✗ Toggle Enable", command=lambda: self._toggle_action_enabled(idx))
                menu.add_separator()
                menu.add_command(label="🗑 Delete", command=lambda: self._delete_action_at(idx))
                menu.add_separator()
                menu.add_command(label="⬆ Move Up", command=lambda: self._move_action(idx, -1))
                menu.add_command(label="⬇ Move Down", command=lambda: self._move_action(idx, 1))
            else:
                # Multiple items - show bulk actions
                menu.add_command(label=f"🗑 Delete {count} selected", command=self._delete_selected_actions)
                menu.add_separator()
                menu.add_command(label="📦 Group Selected", command=self._group_selected_actions)
                menu.add_separator()
                menu.add_command(label="✓ Enable All Selected", command=self._enable_selected_actions)
                menu.add_command(label="✗ Disable All Selected", command=self._disable_selected_actions)
            
            # Check if selection is a GROUP to show Ungroup option
            if count == 1:
                values = self.action_tree.item(item, "values")
                idx = int(values[0]) - 1
                if 0 <= idx < len(self.actions) and self.actions[idx].action == "GROUP":
                    menu.add_separator()
                    menu.add_command(label="📤 Ungroup", command=lambda: self._ungroup_action(idx))
            
            menu.add_separator()
            menu.add_command(label="✓ Select All (Ctrl+A)", command=self._select_all_actions)
            
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
            messagebox.showwarning("Group", "Please select at least 2 actions to group")
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
        """Save actions to JSON file (per spec 4.2)"""
        if not self.actions:
            messagebox.showwarning("Warning", "No actions to save")
            return
        
        filepath = filedialog.asksaveasfilename(
            title="Save Actions",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if not filepath:
            return
        
        try:
            data = {
                "version": "1.0",
                "target_window_match": None,
                "actions": [a.to_dict() for a in self.actions]
            }
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            messagebox.showinfo("Success", f"Saved {len(self.actions)} actions")
            log(f"[UI] Saved actions to: {filepath}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save: {e}")
    
    def _load_actions(self):
        """Load actions from JSON file (per spec 4.2)"""
        filepath = filedialog.askopenfilename(
            title="Load Actions",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if not filepath:
            return
        
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            self.actions = [Action.from_dict(a) for a in data.get("actions", [])]
            self._refresh_action_list()
            messagebox.showinfo("Success", f"Loaded {len(self.actions)} actions")
            log(f"[UI] Loaded actions from: {filepath}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load: {e}")

    # ================= ADD ACTION DIALOG (per spec 5 - V2 expanded) =================
    
    def _open_add_action_dialog(self, edit_index: int = None):
        """Open Add Action dialog (per spec 5.1 - V2 expanded)"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Add Action" if edit_index is None else "Edit Action")
        dialog.geometry("500x600")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Load existing action if editing
        edit_action = None
        if edit_index is not None and 0 <= edit_index < len(self.actions):
            edit_action = self.actions[edit_index]
        
        # ===== TYPE DROPDOWN with categories =====
        type_frame = tk.Frame(dialog)
        type_frame.pack(fill="x", padx=15, pady=10)
        
        tk.Label(type_frame, text="Type:", font=("Arial", 9, "bold")).pack(side="left", padx=(0, 5))
        type_var = tk.StringVar(value=edit_action.action if edit_action else "CLICK")
        
        # V2 expanded type options with categories
        type_options = [
            # Basic
            "CLICK", "WAIT", "KEY_PRESS", "COMBOKEY", "WHEEL", "DRAG", "TEXT",
            # Wait Actions (V2)
            "---Wait Actions---",
            "WAIT_TIME", "WAIT_PIXEL_COLOR", "WAIT_SCREEN_CHANGE", "WAIT_COMBOKEY", "WAIT_FILE",
            # Image Actions (V2)
            "---Image Actions---",
            "FIND_IMAGE", "CAPTURE_IMAGE",
            # Flow Control (V2)
            "---Flow Control---",
            "LABEL", "GOTO", "REPEAT", "EMBED_MACRO", "GROUP",
            # Misc
            "---Misc---",
            "COMMENT", "SET_VARIABLE"
        ]
        
        type_dropdown = ttk.Combobox(type_frame, textvariable=type_var, values=type_options, 
                                     state="readonly", font=("Arial", 9), width=20)
        type_dropdown.pack(side="left")
        
        # ===== CONFIGURATION PANEL =====
        config_frame = tk.LabelFrame(dialog, text="Configuration", font=("Arial", 10, "bold"))
        config_frame.pack(fill="both", expand=True, padx=15, pady=10)
        
        config_widgets = {}
        
        def render_config_panel():
            """Clear and render config based on type"""
            for w in config_frame.winfo_children():
                w.destroy()
            config_widgets.clear()
            
            action_type = type_var.get()
            
            # Skip separator items
            if action_type.startswith("---"):
                tk.Label(config_frame, text="Please select an action type", 
                        fg="gray").pack(pady=20)
                return
            
            value = edit_action.value if edit_action else {}
            
            # Basic actions
            if action_type == "CLICK":
                self._render_click_action_config(config_frame, config_widgets, value, dialog)
            elif action_type == "WAIT":
                self._render_wait_action_config(config_frame, config_widgets, value)
            elif action_type == "KEY_PRESS":
                self._render_keypress_action_config(config_frame, config_widgets, value)
            elif action_type == "COMBOKEY":
                self._render_combokey_action_config(config_frame, config_widgets, value)
            elif action_type == "WHEEL":
                self._render_wheel_action_config(config_frame, config_widgets, value)
            elif action_type == "DRAG":
                self._render_drag_action_config(config_frame, config_widgets, value, dialog)
            elif action_type == "TEXT":
                self._render_text_action_config(config_frame, config_widgets, value)
            # V2 Wait Actions
            elif action_type == "WAIT_TIME":
                self._render_wait_time_config(config_frame, config_widgets, value)
            elif action_type == "WAIT_PIXEL_COLOR":
                self._render_wait_pixel_color_config(config_frame, config_widgets, value, dialog)
            elif action_type == "WAIT_SCREEN_CHANGE":
                self._render_wait_screen_change_config(config_frame, config_widgets, value, dialog)
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
        
        type_dropdown.bind("<<ComboboxSelected>>", lambda e: render_config_panel())
        render_config_panel()
        
        # ===== ENABLED CHECKBOX =====
        enabled_frame = tk.Frame(dialog)
        enabled_frame.pack(fill="x", padx=15, pady=5)
        
        enabled_var = tk.BooleanVar(value=edit_action.enabled if edit_action else True)
        tk.Checkbutton(enabled_frame, text="Enabled", variable=enabled_var, 
                      font=("Arial", 9, "bold")).pack(anchor="w")
        
        # ===== LABEL =====
        label_frame = tk.Frame(dialog)
        label_frame.pack(fill="x", padx=15, pady=5)
        
        tk.Label(label_frame, text="Label:", font=("Arial", 9)).pack(side="left", padx=(0, 5))
        label_var = tk.StringVar(value=edit_action.label if edit_action else "")
        tk.Entry(label_frame, textvariable=label_var, width=25).pack(side="left")
        
        # ===== COMMENT =====
        comment_frame = tk.Frame(dialog)
        comment_frame.pack(fill="x", padx=15, pady=5)
        
        tk.Label(comment_frame, text="Comment:", font=("Arial", 9)).pack(side="left", padx=(0, 5))
        comment_var = tk.StringVar(value=edit_action.comment if edit_action else "")
        tk.Entry(comment_frame, textvariable=comment_var, width=35).pack(side="left")
        
        # ===== BUTTONS =====
        btn_frame = tk.Frame(dialog)
        btn_frame.pack(fill="x", padx=15, pady=10)
        
        def save_action():
            action_type = type_var.get()
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
                self.actions[edit_index] = new_action
            else:
                self.actions.append(new_action)
            
            self._refresh_action_list()
            dialog.destroy()
            log(f"[UI] {'Updated' if edit_index is not None else 'Added'} action: {action_type}")
        
        tk.Button(btn_frame, text="✓ Save", command=save_action, bg="#4CAF50", fg="white", 
                 font=("Arial", 9, "bold"), width=12).pack(side="left", padx=5)
        tk.Button(btn_frame, text="✗ Cancel", command=dialog.destroy, bg="#f44336", fg="white", 
                 font=("Arial", 9, "bold"), width=12).pack(side="left", padx=5)
    
    def _render_click_action_config(self, parent, widgets, value, dialog=None):
        """Render Click action config (per spec 5.2) - V2 with improved capture"""
        # Button type
        btn_frame = tk.Frame(parent)
        btn_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(btn_frame, text="Button:", font=("Arial", 9)).pack(side="left", padx=(0, 5))
        btn_var = tk.StringVar(value=value.get("button", "left"))
        btn_combo = ttk.Combobox(btn_frame, textvariable=btn_var, 
                    values=["left", "right", "middle", "double", "hold_left", "hold_right"], 
                    state="readonly", width=12)
        btn_combo.pack(side="left")
        widgets["button"] = btn_var
        
        # Hold duration frame (only shown for hold_left/hold_right)
        hold_frame = tk.Frame(parent)
        hold_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(hold_frame, text="Hold (ms):", font=("Arial", 9)).pack(side="left", padx=(0, 5))
        hold_var = tk.IntVar(value=value.get("hold_ms", 500))
        hold_entry = tk.Entry(hold_frame, textvariable=hold_var, width=8)
        hold_entry.pack(side="left", padx=2)
        widgets["hold_ms"] = hold_var
        
        # Position
        pos_frame = tk.Frame(parent)
        pos_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(pos_frame, text="Position:", font=("Arial", 9)).pack(side="left", padx=(0, 5))
        
        x_var = tk.IntVar(value=value.get("x", 0))
        tk.Label(pos_frame, text="X:").pack(side="left", padx=(10, 2))
        tk.Entry(pos_frame, textvariable=x_var, width=8).pack(side="left", padx=2)
        widgets["x"] = x_var
        
        y_var = tk.IntVar(value=value.get("y", 0))
        tk.Label(pos_frame, text="Y:").pack(side="left", padx=(10, 2))
        tk.Entry(pos_frame, textvariable=y_var, width=8).pack(side="left", padx=2)
        widgets["y"] = y_var
        
        # Capture button - captures position, and for hold types also measures hold duration
        capture_btn = tk.Button(pos_frame, text="📍 Capture", 
                               command=lambda: self._capture_click_with_hold(x_var, y_var, hold_var, btn_var),
                               bg="#2196F3", fg="white", font=("Arial", 8))
        capture_btn.pack(side="left", padx=10)
        
        # Status label for capture feedback
        status_label = tk.Label(parent, text="", fg="blue", font=("Arial", 8))
        status_label.pack(anchor="w", padx=10)
        widgets["_status_label"] = status_label
        
        # Hint text
        def update_hint(*args):
            btn = btn_var.get()
            if btn in ("hold_left", "hold_right"):
                status_label.config(text="💡 Capture: Click vị trí rồi GIỮ chuột - thời gian giữ sẽ được đo", fg="blue")
            else:
                status_label.config(text="💡 Capture: Click vị trí cần thao tác", fg="gray")
        
        btn_var.trace_add("write", update_hint)
        update_hint()  # Initial update
    
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
        
        tk.Label(parent, text="Click 'Capture' then press any key", fg="gray", font=("Arial", 8)).pack(anchor="w", padx=10)
    
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
        
        tk.Label(parent, text="Click 'Capture' then press key combo (Alt+Tab supported!)", fg="gray", font=("Arial", 8)).pack(anchor="w", padx=10)
    
    def _render_wheel_action_config(self, parent, widgets, value):
        """Render Wheel action config (per spec B3 - V2 improved)"""
        # Direction
        dir_frame = tk.Frame(parent)
        dir_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(dir_frame, text="Direction:", font=("Arial", 9)).pack(side="left", padx=(0, 5))
        dir_var = tk.StringVar(value=value.get("direction", "up"))
        ttk.Combobox(dir_frame, textvariable=dir_var, values=["up", "down"], 
                    state="readonly", width=8).pack(side="left")
        widgets["direction"] = dir_var
        
        # Amount (số lần scroll)
        amount_frame = tk.Frame(parent)
        amount_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(amount_frame, text="Amount:", font=("Arial", 9)).pack(side="left", padx=(0, 5))
        amount_var = tk.IntVar(value=value.get("amount", 3))
        tk.Entry(amount_frame, textvariable=amount_var, width=6).pack(side="left")
        tk.Label(amount_frame, text="(số lần scroll)", fg="gray", font=("Arial", 8)).pack(side="left", padx=5)
        widgets["amount"] = amount_var
        
        # Speed (delay giữa các tick)
        speed_frame = tk.Frame(parent)
        speed_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(speed_frame, text="Speed (ms):", font=("Arial", 9)).pack(side="left", padx=(0, 5))
        speed_var = tk.IntVar(value=value.get("speed", 50))
        tk.Entry(speed_frame, textvariable=speed_var, width=6).pack(side="left")
        tk.Label(speed_frame, text="(delay giữa mỗi tick)", fg="gray", font=("Arial", 8)).pack(side="left", padx=5)
        widgets["speed"] = speed_var
        
        # Position
        pos_frame = tk.Frame(parent)
        pos_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(pos_frame, text="Position:", font=("Arial", 9)).pack(side="left", padx=(0, 5))
        x_var = tk.IntVar(value=value.get("x", 0))
        y_var = tk.IntVar(value=value.get("y", 0))
        tk.Label(pos_frame, text="X:").pack(side="left")
        tk.Entry(pos_frame, textvariable=x_var, width=8).pack(side="left", padx=2)
        tk.Label(pos_frame, text="Y:").pack(side="left", padx=(10, 0))
        tk.Entry(pos_frame, textvariable=y_var, width=8).pack(side="left", padx=2)
        widgets["x"] = x_var
        widgets["y"] = y_var
        
        # Capture button
        tk.Button(pos_frame, text="📍", command=lambda: self._capture_position(x_var, y_var),
                 bg="#2196F3", fg="white", font=("Arial", 8)).pack(side="left", padx=5)
    
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
        ttk.Combobox(mode_frame, textvariable=mode_var, values=["paste", "humanize"], 
                    state="readonly", width=10).pack(side="left")
        widgets["mode"] = mode_var
    
    def _get_action_value_from_widgets(self, action_type: str, widgets: dict) -> dict:
        """Extract action value from config widgets"""
        if action_type == "CLICK":
            return {
                "button": widgets["button"].get(),
                "x": widgets["x"].get(),
                "y": widgets["y"].get(),
                "hold_ms": widgets["hold_ms"].get()
            }
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
            return {
                "direction": widgets["direction"].get(),
                "amount": widgets["amount"].get(),
                "speed": widgets["speed"].get(),
                "x": widgets["x"].get(),
                "y": widgets["y"].get()
            }
        elif action_type == "DRAG":
            return {
                "button": widgets["button"].get(),
                "duration_ms": widgets["duration_ms"].get(),
                "x1": widgets["x1"].get(),
                "y1": widgets["y1"].get(),
                "x2": widgets["x2"].get(),
                "y2": widgets["y2"].get()
            }
        elif action_type == "TEXT":
            return {
                "text": widgets["text"].get("1.0", tk.END).strip(),
                "mode": widgets["mode"].get()
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
                "timeout_ms": widgets["timeout_ms"].get()
            }
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
            return {
                "template_path": widgets["template_path"].get(),
                "threshold": widgets["threshold"].get(),
                "timeout_ms": widgets["timeout_ms"].get()
            }
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
            return {"target": widgets["target"].get()}
        elif action_type == "REPEAT":
            return {
                "count": widgets["count"].get(),
                "end_label": widgets.get("end_label", tk.StringVar(value="")).get()
            }
        elif action_type == "EMBED_MACRO":
            return {"macro_name": widgets["macro_name"].get()}
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
        """Render WAIT_SCREEN_CHANGE config (spec B1-3)"""
        region = value.get("region", (0, 0, 100, 100))
        
        region_frame = tk.LabelFrame(parent, text="Monitor Region")
        region_frame.pack(fill="x", padx=10, pady=5)
        
        x1_var = tk.IntVar(value=region[0] if len(region) > 0 else 0)
        y1_var = tk.IntVar(value=region[1] if len(region) > 1 else 0)
        x2_var = tk.IntVar(value=region[2] if len(region) > 2 else 100)
        y2_var = tk.IntVar(value=region[3] if len(region) > 3 else 100)
        
        row1 = tk.Frame(region_frame)
        row1.pack(fill="x", padx=5, pady=2)
        tk.Label(row1, text="X1:").pack(side="left")
        tk.Entry(row1, textvariable=x1_var, width=6).pack(side="left", padx=2)
        tk.Label(row1, text="Y1:").pack(side="left")
        tk.Entry(row1, textvariable=y1_var, width=6).pack(side="left", padx=2)
        
        row2 = tk.Frame(region_frame)
        row2.pack(fill="x", padx=5, pady=2)
        tk.Label(row2, text="X2:").pack(side="left")
        tk.Entry(row2, textvariable=x2_var, width=6).pack(side="left", padx=2)
        tk.Label(row2, text="Y2:").pack(side="left")
        tk.Entry(row2, textvariable=y2_var, width=6).pack(side="left", padx=2)
        
        widgets["x1"] = x1_var
        widgets["y1"] = y1_var
        widgets["x2"] = x2_var
        widgets["y2"] = y2_var
        
        thresh_frame = tk.Frame(parent)
        thresh_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(thresh_frame, text="Change threshold:", font=("Arial", 9)).pack(side="left", padx=(0, 5))
        thresh_var = tk.DoubleVar(value=value.get("threshold", 0.05))
        tk.Entry(thresh_frame, textvariable=thresh_var, width=8).pack(side="left")
        tk.Label(thresh_frame, text="(0.0-1.0)", fg="gray").pack(side="left", padx=5)
        widgets["threshold"] = thresh_var
        
        timeout_frame = tk.Frame(parent)
        timeout_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(timeout_frame, text="Timeout (ms):", font=("Arial", 9)).pack(side="left", padx=(0, 5))
        timeout_var = tk.IntVar(value=value.get("timeout_ms", 30000))
        tk.Entry(timeout_frame, textvariable=timeout_var, width=10).pack(side="left")
        widgets["timeout_ms"] = timeout_var
    
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
        """Render FIND_IMAGE config (spec B2-1)"""
        if not IMAGE_ACTIONS_AVAILABLE:
            tk.Label(parent, text="⚠ OpenCV not installed. Install with: pip install opencv-python",
                    fg="red", font=("Arial", 9)).pack(padx=10, pady=10)
        
        path_frame = tk.Frame(parent)
        path_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(path_frame, text="Template:", font=("Arial", 9)).pack(side="left", padx=(0, 5))
        path_var = tk.StringVar(value=value.get("template_path", ""))
        tk.Entry(path_frame, textvariable=path_var, width=25).pack(side="left")
        widgets["template_path"] = path_var
        
        def browse_template():
            from tkinter import filedialog
            fp = filedialog.askopenfilename(filetypes=[("Images", "*.png *.jpg *.bmp")])
            if fp:
                path_var.set(fp)
        tk.Button(path_frame, text="...", command=browse_template).pack(side="left", padx=5)
        
        thresh_frame = tk.Frame(parent)
        thresh_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(thresh_frame, text="Threshold:", font=("Arial", 9)).pack(side="left", padx=(0, 5))
        thresh_var = tk.DoubleVar(value=value.get("threshold", 0.8))
        tk.Entry(thresh_frame, textvariable=thresh_var, width=8).pack(side="left")
        tk.Label(thresh_frame, text="(0.0-1.0)", fg="gray").pack(side="left", padx=5)
        widgets["threshold"] = thresh_var
        
        timeout_frame = tk.Frame(parent)
        timeout_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(timeout_frame, text="Timeout (ms):", font=("Arial", 9)).pack(side="left", padx=(0, 5))
        timeout_var = tk.IntVar(value=value.get("timeout_ms", 5000))
        tk.Entry(timeout_frame, textvariable=timeout_var, width=10).pack(side="left")
        widgets["timeout_ms"] = timeout_var
    
    def _render_capture_image_config(self, parent, widgets, value, dialog=None):
        """Render CAPTURE_IMAGE config (spec B2-2)"""
        if not IMAGE_ACTIONS_AVAILABLE:
            tk.Label(parent, text="⚠ OpenCV not installed. Install with: pip install opencv-python",
                    fg="red", font=("Arial", 9)).pack(padx=10, pady=10)
        
        path_frame = tk.Frame(parent)
        path_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(path_frame, text="Save path:", font=("Arial", 9)).pack(side="left", padx=(0, 5))
        path_var = tk.StringVar(value=value.get("save_path", ""))
        tk.Entry(path_frame, textvariable=path_var, width=25).pack(side="left")
        widgets["save_path"] = path_var
        
        def browse_save():
            from tkinter import filedialog
            fp = filedialog.asksaveasfilename(
                defaultextension=".png",
                filetypes=[("PNG", "*.png"), ("JPEG", "*.jpg"), ("BMP", "*.bmp")]
            )
            if fp:
                path_var.set(fp)
        tk.Button(path_frame, text="...", command=browse_save).pack(side="left", padx=5)
        
        tk.Label(parent, text="(Leave empty for auto-generated filename)", fg="gray", font=("Arial", 8)).pack(anchor="w", padx=10)
        
        format_frame = tk.Frame(parent)
        format_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(format_frame, text="Format:", font=("Arial", 9)).pack(side="left", padx=(0, 5))
        format_var = tk.StringVar(value=value.get("format", "png"))
        ttk.Combobox(format_frame, textvariable=format_var, 
                    values=["png", "jpg", "bmp"],
                    state="readonly", width=8).pack(side="left")
        widgets["format"] = format_var
        
        # Optional region
        region_frame = tk.LabelFrame(parent, text="Region (optional)")
        region_frame.pack(fill="x", padx=10, pady=5)
        
        region = value.get("region", (0, 0, 0, 0)) or (0, 0, 0, 0)
        x1_var = tk.IntVar(value=region[0])
        y1_var = tk.IntVar(value=region[1])
        x2_var = tk.IntVar(value=region[2])
        y2_var = tk.IntVar(value=region[3])
        
        row = tk.Frame(region_frame)
        row.pack(fill="x", padx=5, pady=2)
        tk.Label(row, text="X1:").pack(side="left")
        tk.Entry(row, textvariable=x1_var, width=5).pack(side="left", padx=2)
        tk.Label(row, text="Y1:").pack(side="left")
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
        """Render LABEL config (spec B4-1)"""
        name_frame = tk.Frame(parent)
        name_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(name_frame, text="Label name:", font=("Arial", 9)).pack(side="left", padx=(0, 5))
        name_var = tk.StringVar(value=value.get("name", ""))
        tk.Entry(name_frame, textvariable=name_var, width=25).pack(side="left")
        widgets["name"] = name_var
        
        tk.Label(parent, text="Labels are markers for Goto and Repeat actions", 
                fg="gray", font=("Arial", 8)).pack(anchor="w", padx=10)
    
    def _render_goto_config(self, parent, widgets, value):
        """Render GOTO config (spec B4-2)"""
        target_frame = tk.Frame(parent)
        target_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(target_frame, text="Target label:", font=("Arial", 9)).pack(side="left", padx=(0, 5))
        target_var = tk.StringVar(value=value.get("target", ""))
        tk.Entry(target_frame, textvariable=target_var, width=25).pack(side="left")
        widgets["target"] = target_var
        
        tk.Label(parent, text="Jump to the action with this label name", 
                fg="gray", font=("Arial", 8)).pack(anchor="w", padx=10)
    
    def _render_repeat_config(self, parent, widgets, value):
        """Render REPEAT config (spec B4-3)"""
        count_frame = tk.Frame(parent)
        count_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(count_frame, text="Repeat count:", font=("Arial", 9)).pack(side="left", padx=(0, 5))
        count_var = tk.IntVar(value=value.get("count", 1))
        tk.Spinbox(count_frame, from_=1, to=9999, textvariable=count_var, width=8).pack(side="left")
        widgets["count"] = count_var
        
        end_frame = tk.Frame(parent)
        end_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(end_frame, text="End label:", font=("Arial", 9)).pack(side="left", padx=(0, 5))
        end_var = tk.StringVar(value=value.get("end_label", ""))
        tk.Entry(end_frame, textvariable=end_var, width=20).pack(side="left")
        widgets["end_label"] = end_var
        
        tk.Label(parent, text="Actions between Repeat and end_label will loop", 
                fg="gray", font=("Arial", 8)).pack(anchor="w", padx=10)
    
    def _render_embed_macro_config(self, parent, widgets, value):
        """Render EMBED_MACRO config (spec B4-4)"""
        name_frame = tk.Frame(parent)
        name_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(name_frame, text="Macro name:", font=("Arial", 9)).pack(side="left", padx=(0, 5))
        name_var = tk.StringVar(value=value.get("macro_name", ""))
        tk.Entry(name_frame, textvariable=name_var, width=25).pack(side="left")
        widgets["macro_name"] = name_var
        
        def browse_macro():
            from tkinter import filedialog
            fp = filedialog.askopenfilename(
                initialdir="data/macros",
                filetypes=[("JSON", "*.json")]
            )
            if fp:
                name_var.set(fp)
        tk.Button(name_frame, text="...", command=browse_macro).pack(side="left", padx=5)
        
        tk.Label(parent, text="Execute another macro file inline", 
                fg="gray", font=("Arial", 8)).pack(anchor="w", padx=10)
    
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
    
    def _render_drag_action_config(self, parent, widgets, value, dialog=None):
        """Render Drag action config - V2 with capture support"""
        # Button type (left/right)
        btn_frame = tk.Frame(parent)
        btn_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(btn_frame, text="Button:", font=("Arial", 9)).pack(side="left", padx=(0, 5))
        btn_var = tk.StringVar(value=value.get("button", "left"))
        btn_dropdown = ttk.Combobox(btn_frame, textvariable=btn_var, 
                                    values=["left", "right"], state="readonly", width=8)
        btn_dropdown.pack(side="left", padx=2)
        widgets["button"] = btn_var
        
        # Duration
        tk.Label(btn_frame, text="Duration (ms):").pack(side="left", padx=(10, 2))
        duration_var = tk.IntVar(value=value.get("duration_ms", 500))
        tk.Entry(btn_frame, textvariable=duration_var, width=6).pack(side="left", padx=2)
        widgets["duration_ms"] = duration_var
        
        # Start position
        start_frame = tk.Frame(parent)
        start_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(start_frame, text="Start:", font=("Arial", 9)).pack(side="left", padx=(0, 5))
        x1_var = tk.IntVar(value=value.get("x1", 0))
        y1_var = tk.IntVar(value=value.get("y1", 0))
        tk.Label(start_frame, text="X1:").pack(side="left")
        tk.Entry(start_frame, textvariable=x1_var, width=6).pack(side="left", padx=2)
        tk.Label(start_frame, text="Y1:").pack(side="left")
        tk.Entry(start_frame, textvariable=y1_var, width=6).pack(side="left", padx=2)
        widgets["x1"] = x1_var
        widgets["y1"] = y1_var
        
        # End position
        end_frame = tk.Frame(parent)
        end_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(end_frame, text="End:", font=("Arial", 9)).pack(side="left", padx=(0, 5))
        x2_var = tk.IntVar(value=value.get("x2", 0))
        y2_var = tk.IntVar(value=value.get("y2", 0))
        tk.Label(end_frame, text="X2:").pack(side="left")
        tk.Entry(end_frame, textvariable=x2_var, width=6).pack(side="left", padx=2)
        tk.Label(end_frame, text="Y2:").pack(side="left")
        tk.Entry(end_frame, textvariable=y2_var, width=6).pack(side="left", padx=2)
        widgets["x2"] = x2_var
        widgets["y2"] = y2_var
        
        # Capture button
        capture_frame = tk.Frame(parent)
        capture_frame.pack(fill="x", padx=10, pady=5)
        capture_btn = tk.Button(capture_frame, text="📍 Capture Drag", 
                               command=lambda: self._capture_drag_path(x1_var, y1_var, x2_var, y2_var, duration_var),
                               bg="#2196F3", fg="white", font=("Arial", 9))
        capture_btn.pack(side="left")
        tk.Label(capture_frame, text="(Giữ chuột và kéo để capture hành trình)", 
                fg="#666666", font=("Arial", 8)).pack(side="left", padx=10)

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
            title="Save Script",
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
            title="Load Script",
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
        tk.Button(btn_frame, text="✗ Cancel", command=dialog.destroy, bg="#f44336", fg="white", 
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
        """Render Repeat configuration"""
        count_val = 1
        until_val = ""
        
        if edit_cmd and isinstance(edit_cmd, RepeatCommand):
            count_val = edit_cmd.count
            until_val = edit_cmd.until_condition_expr or ""
        
        # Count
        count_frame = tk.Frame(parent)
        count_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(count_frame, text="Count:", font=("Arial", 9)).pack(side="left", padx=(0, 5))
        count_var = tk.IntVar(value=count_val)
        tk.Spinbox(count_frame, from_=0, to=9999, textvariable=count_var, width=8).pack(side="left")
        widgets["count"] = count_var
        tk.Label(count_frame, text="(0 = infinite)", fg="gray", font=("Arial", 8)).pack(side="left", padx=5)
        
        # Until condition
        until_frame = tk.Frame(parent)
        until_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(until_frame, text="Until Condition:", font=("Arial", 9)).pack(side="left", padx=(0, 5))
        until_var = tk.StringVar(value=until_val)
        tk.Entry(until_frame, textvariable=until_var, width=35).pack(side="left")
        widgets["until_condition"] = until_var
        
        tk.Label(parent, text="(Inner commands: Use nested editor - coming soon)", 
                fg="gray", font=("Arial", 8)).pack(pady=10)
    
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
                    self._target_btn_text.set("🎯 Screen")
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
        detail_window.geometry("500x400")
        
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

    def refresh_workers(self):
        """Refresh workers by re-detecting LDPlayer windows"""
        from initialize_workers import initialize_workers_from_ldplayer
        
        log("[UI] Refreshing workers...")
        
        # Re-initialize workers
        new_workers = initialize_workers_from_ldplayer()
        
        if new_workers:
            self.workers = new_workers
            log(f"[UI] Refreshed: {len(new_workers)} worker(s) detected")
            messagebox.showinfo("Refresh Workers", f"✓ Phát hiện {len(new_workers)} LDPlayer instance(s)")
        else:
            log("[UI] Refresh: No workers detected")
            messagebox.showwarning("Refresh Workers", "❌ Không tìm thấy LDPlayer nào.\n\nHãy chắc LDPlayer đang chạy.")
        
        # Update worker list display
        self._auto_refresh_status()
    def set_worker_dialog(self):
        """
        Phân chia LDPlayer → Worker ID
        
        Tính năng:
        1. Hiển thị danh sách LDPlayer hiện có (detect từ window)
        2. Select/Unselect từng cái hoặc All
        3. Auto-assign Worker dựa vào thứ tự (fill gaps)
        4. Xóa Worker random (giữ nguyên gaps)
        """
        from initialize_workers import detect_ldplayer_windows
        
        if not self.workers:
            messagebox.showwarning("Thông báo", "Không có worker nào")
            return
        
        # Detect LDPlayer windows (không bắt buộc phải có)
        ldplayer_windows = detect_ldplayer_windows()
        log(f"[UI] Set Worker dialog: detected {len(ldplayer_windows)} LDPlayer windows")
        
        # Create dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("Set Worker - Gán LDPlayer → Worker ID")
        dialog.geometry("500x400")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # ===== TITLE =====
        tk.Label(dialog, text="Gán LDPlayer Instance → Worker ID", 
                 font=("Arial", 11, "bold")).pack(pady=10)
        
        ldplayer_vars = {}  # {hwnd → BooleanVar}
        ldplayer_list = []  # Will be populated by refresh
        
        # Function to refresh checkbox labels with current assignments
        def refresh_dialog():
            """Refresh checkbox labels to show current Worker assignments"""
            nonlocal ldplayer_list
            
            # Re-detect LDPlayer windows
            fresh_windows = detect_ldplayer_windows()
            ldplayer_list.clear()
            ldplayer_list.extend([(w['hwnd'], w['title']) for w in fresh_windows])
            log(f"[UI] Refresh: detected {len(ldplayer_list)} LDPlayer windows")
            
            for widget in scrollable_frame.winfo_children():
                widget.destroy()
            
            ldplayer_vars.clear()
            
            if not ldplayer_list:
                # Show message when no LDPlayer found
                tk.Label(scrollable_frame, text="❌ Không tìm thấy LDPlayer nào\n\nHãy chắc LDPlayer đang chạy và nhấn Refresh",
                        bg="white", fg="red", font=("Arial", 10), justify="center").pack(pady=20)
                return
            
            for hwnd, title in ldplayer_list:
                var = tk.BooleanVar()
                ldplayer_vars[hwnd] = var
                
                # Get current assignment
                worker_id = self.worker_mgr.get_worker_id(str(hwnd))
                assigned_text = f" → Worker {worker_id}" if worker_id else " → (Not assigned)"
                
                frame = tk.Frame(scrollable_frame, bg="white")
                frame.pack(fill="x", padx=5, pady=4, anchor="w")
                
                tk.Checkbutton(frame, text=f"{title}{assigned_text}", variable=var,
                              bg="white", font=("Arial", 9)).pack(anchor="w", fill="x")
        
        # ===== ACTION BUTTONS (ĐƯA LÊN ĐẦU) =====
        action_frame = tk.Frame(dialog)
        action_frame.pack(fill="x", padx=15, pady=(5, 10))
        
        def assign_workers():
            """Auto-assign Worker ID tới selected LDPlayers"""
            selected = [hwnd for hwnd, var in ldplayer_vars.items() if var.get()]
            
            if not selected:
                messagebox.showwarning("Thông báo", "Chưa select LDPlayer nào")
                return
            
            # Auto-assign
            result = self.worker_mgr.auto_assign_selected([str(hwnd) for hwnd in selected])
            
            if result:
                msg = "✓ Đã gán:\n\n"
                for ldplayer_id, worker_id in result.items():
                    msg += f"  {ldplayer_id} → Worker {worker_id}\n"
                messagebox.showinfo("Thành công", msg)
                log(f"[UI] Assigned {len(result)} LDPlayer(s) to Worker IDs")
            else:
                messagebox.showinfo("Thông báo", "✓ Tất cả đã được gán trước đó")
            
            # Refresh dialog
            refresh_dialog()
        
        def delete_worker():
            """Xóa Worker của LDPlayer được select"""
            selected = [hwnd for hwnd, var in ldplayer_vars.items() if var.get()]
            
            if not selected:
                messagebox.showwarning("Thông báo", "Vui lòng Select LDPlayer muốn xóa Worker")
                return
            
            # Delete Worker của tất cả selected LDPlayers
            deleted_count = 0
            for hwnd in selected:
                if self.worker_mgr.remove_worker(str(hwnd)):
                    deleted_count += 1
            
            if deleted_count > 0:
                messagebox.showinfo("Thành công", f"✓ Đã xóa Worker của {deleted_count} LDPlayer")
                log(f"[UI] Deleted Worker for {deleted_count} LDPlayer(s)")
            else:
                messagebox.showwarning("Thông báo", "Không có LDPlayer nào được gán Worker")
            
            # Refresh dialog
            refresh_dialog()
        
        tk.Button(action_frame, text="🔗 Set Worker", command=assign_workers,
                  bg="#4CAF50", fg="white", font=("Arial", 9, "bold"), width=14).pack(side="left", padx=3)
        tk.Button(action_frame, text="🗑️ Delete", command=delete_worker,
                  bg="#f44336", fg="white", font=("Arial", 9, "bold"), width=10).pack(side="left", padx=3)
        tk.Button(action_frame, text="🔄 Refresh", command=refresh_dialog,
                  bg="#FF9800", fg="white", font=("Arial", 9, "bold"), width=10).pack(side="left", padx=3)
        tk.Button(action_frame, text="✓ Close", command=dialog.destroy,
                  bg="#2196F3", fg="white", font=("Arial", 9, "bold"), width=8).pack(side="left", padx=3)
        
        # ===== LDPLAYER LIST FRAME =====
        list_frame = tk.LabelFrame(dialog, text="📱 LDPlayer Instances", 
                                   font=("Arial", 10, "bold"))
        list_frame.pack(fill="both", expand=True, padx=15, pady=(0, 10))
        
        # ===== SELECT ALL CHECKBOX (INSIDE LIST FRAME) =====
        select_all_var = tk.BooleanVar()
        
        def toggle_select_all():
            """Toggle all checkboxes based on Select All state"""
            is_selected = select_all_var.get()
            for var in ldplayer_vars.values():
                var.set(is_selected)
        
        select_all_frame = tk.Frame(list_frame, bg="white")
        select_all_frame.pack(fill="x", padx=8, pady=5)
        tk.Checkbutton(select_all_frame, text="Select All", variable=select_all_var,
                      command=toggle_select_all, font=("Arial", 9, "bold"), 
                      bg="white").pack(anchor="w")
        
        # Canvas + Scrollbar
        canvas = tk.Canvas(list_frame, bg="white", highlightthickness=0)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg="white")
        
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
        # Clear existing items
        for item in self.worker_tree.get_children():
            self.worker_tree.delete(item)

        running = self.launcher.get_running_workers()

        for w in self.workers:
            # Determine status from worker state
            if hasattr(w, 'paused') and w.paused:
                status = "PAUSED"
            elif hasattr(w, 'stopped') and not w.stopped and hasattr(w, '_execution_thread') and w._execution_thread and w._execution_thread.is_alive():
                status = "RUNNING"
            elif not w.is_ready():
                status = "NOT READY"
            elif w.id in running:
                status = "RUNNING"
            else:
                status = "READY"

            # Extract name from hwnd or use default
            name = f"LDPlayer-{w.id}"
            
            # Worker ID = worker's index (w.id), vì workers được tạo tuần tự
            # từ initialize_workers_from_ldplayer
            worker_id_text = f"Worker {w.id}"
            
            # Check if worker has custom actions
            has_custom = w.id in self._worker_actions and len(self._worker_actions[w.id]) > 0
            custom_count = len(self._worker_actions.get(w.id, []))

            # Actions column shows clickable text + custom indicator
            if has_custom:
                actions_text = f"[▶ ⏸ ⏹] ✏️{custom_count}"
            else:
                actions_text = "[▶ ⏸ ⏹]"

            # Insert row with new column order: ID, Name, Worker, Status, Actions
            item_id = self.worker_tree.insert("", tk.END, values=(w.id, name, worker_id_text, status, actions_text))
            self.worker_tree_items[w.id] = item_id

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
        """Open settings dialog for hotkey binding"""
        dialog = tk.Toplevel(self.root)
        dialog.title("⚙ Settings - Hotkey Binding")
        dialog.geometry("450x500")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.resizable(False, False)
        
        # Title
        tk.Label(dialog, text="Hotkey Settings", font=("Arial", 12, "bold")).pack(pady=10)
        tk.Label(dialog, text="Click button then press key to bind", 
                font=("Arial", 9), fg="gray").pack()
        
        # Hotkey entries frame
        hotkey_frame = tk.LabelFrame(dialog, text="Hotkeys", font=("Arial", 10))
        hotkey_frame.pack(fill="x", padx=20, pady=15)
        
        hotkey_vars = {}
        hotkey_buttons = {}
        
        hotkeys = [
            ("record", "⏺ Record:", self._hotkey_settings.get("record", "")),
            ("play", "▶ Play:", self._hotkey_settings.get("play", "")),
            ("pause", "⏸ Pause:", self._hotkey_settings.get("pause", "")),
            ("stop", "⏹ Stop:", self._hotkey_settings.get("stop", ""))
        ]
        
        for key, label, current_value in hotkeys:
            row = tk.Frame(hotkey_frame)
            row.pack(fill="x", padx=10, pady=8)
            
            tk.Label(row, text=label, font=("Arial", 10), width=12, anchor="w").pack(side="left")
            
            var = tk.StringVar(value=current_value)
            hotkey_vars[key] = var
            
            # Entry to show current hotkey
            entry = tk.Entry(row, textvariable=var, width=15, font=("Arial", 10), 
                           state="readonly", justify="center")
            entry.pack(side="left", padx=5)
            
            # Bind button
            def create_bind_callback(k, v, e):
                def bind_hotkey():
                    self._capture_hotkey(k, v, e, dialog, hotkey_vars)
                return bind_hotkey
            
            btn = tk.Button(row, text="🎯 Bind", command=create_bind_callback(key, var, entry),
                          bg="#2196F3", fg="white", font=("Arial", 8))
            btn.pack(side="left", padx=5)
            hotkey_buttons[key] = btn
            
            # Unbind button
            def create_unbind_callback(v):
                def unbind_hotkey():
                    v.set("")
                return unbind_hotkey
            
            tk.Button(row, text="🚫 Unbind", command=create_unbind_callback(var),
                     bg="#FF5722", fg="white", font=("Arial", 8)).pack(side="left", padx=2)
        
        # Info
        info_frame = tk.Frame(dialog)
        info_frame.pack(fill="x", padx=20, pady=10)
        tk.Label(info_frame, text="💡 Tip: Use F1-F12, or combinations like Ctrl+Shift+R",
                font=("Arial", 8), fg="#666").pack()
        
        # Buttons
        btn_frame = tk.Frame(dialog)
        btn_frame.pack(fill="x", padx=20, pady=20)
        
        def save_and_close():
            # Update settings
            for key, var in hotkey_vars.items():
                self._hotkey_settings[key] = var.get()
            self._save_hotkey_settings()
            self._update_button_hotkey_text()
            self._register_global_hotkeys()
            dialog.destroy()
        
        def reset_defaults():
            hotkey_vars["record"].set("F9")
            hotkey_vars["play"].set("F10")
            hotkey_vars["pause"].set("F11")
            hotkey_vars["stop"].set("F12")
        
        tk.Button(btn_frame, text="✓ Save", command=save_and_close,
                 bg="#4CAF50", fg="white", font=("Arial", 10, "bold"), width=10).pack(side="left", padx=5)
        tk.Button(btn_frame, text="Reset Defaults", command=reset_defaults,
                 bg="#FF9800", fg="white", font=("Arial", 9), width=12).pack(side="left", padx=5)
        tk.Button(btn_frame, text="Cancel", command=dialog.destroy,
                 bg="#9E9E9E", fg="white", font=("Arial", 9), width=10).pack(side="left", padx=5)
    
    def _capture_hotkey(self, key_name, var, entry, parent_dialog, all_hotkey_vars=None):
        """Capture a hotkey press"""
        # IMPORTANT: Temporarily unregister global hotkeys to prevent them from triggering
        self._unregister_global_hotkeys()
        
        capture_dialog = tk.Toplevel(parent_dialog)
        capture_dialog.title(f"Bind Hotkey for {key_name.title()}")
        capture_dialog.geometry("300x150")
        capture_dialog.transient(parent_dialog)
        capture_dialog.grab_set()
        capture_dialog.resizable(False, False)
        
        # Center on parent
        capture_dialog.geometry(f"+{parent_dialog.winfo_x() + 50}+{parent_dialog.winfo_y() + 100}")
        
        tk.Label(capture_dialog, text="Press any key or combination...", 
                font=("Arial", 11)).pack(pady=15)
        
        status_label = tk.Label(capture_dialog, text="Waiting...", font=("Arial", 10), fg="blue")
        status_label.pack()
        
        conflict_label = tk.Label(capture_dialog, text="", font=("Arial", 9), fg="orange")
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
            status_label.config(text=f"Captured: {captured_key[0]}", fg="green")
            
            # Check for conflicts with other hotkeys
            conflict_action = None
            if all_hotkey_vars:
                for action, hk_var in all_hotkey_vars.items():
                    if action != key_name and hk_var.get().lower() == captured_key[0].lower():
                        conflict_action = action
                        break
            
            if conflict_action:
                conflict_label.config(text=f"⚠️ Already bound to '{conflict_action.title()}'", fg="orange")
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
            x = (screen_w - 200) // 2
            y = (screen_h - 80) // 2
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
        
        # Bind Esc to stop
        toolbar.bind("<Escape>", lambda e: self._stop_playback())
        
        self._playback_toolbar = toolbar
        
        # Hide main window
        self.root.withdraw()
    
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
