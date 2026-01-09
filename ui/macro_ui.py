# AI GOVERNANCE:
# Apply auditor-router
# This is a CODE change

"""
Macro Recorder UI Components
Provides recording/playback controls and action editor UI
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
from typing import Optional, Callable, List

from core.macro import (
    MacroManager, get_macro_manager,
    Macro, MacroAction, MacroActionType, MacroSettings, MacroOnError,
    MouseMoveAction, MouseClickAction, MouseDragAction, MouseScrollAction,
    KeyPressAction, HotkeyAction, TextInputAction,
    WaitTimeAction, WaitPixelAction, WaitWindowAction,
    WindowFocusAction,
    RecorderState, PlaybackState,
    MouseButton, KeyPressMode, TextInputMode
)
from utils.logger import log


class MacroRecorderPanel:
    """
    Macro Recorder control panel UI component
    Provides recording/playback buttons and status display
    """
    
    def __init__(self, parent: tk.Widget, manager: MacroManager = None):
        """
        Initialize recorder panel
        
        Args:
            parent: Parent tkinter widget
            manager: MacroManager instance (uses singleton if not provided)
        """
        self._parent = parent
        self._manager = manager or get_macro_manager()
        
        # Callbacks
        self._on_macro_loaded: Optional[Callable[[Macro], None]] = None
        
        # Build UI
        self._build_ui()
        
        # Setup manager callbacks
        self._manager.set_callbacks(
            on_recorder_state_change=self._on_recorder_state_change,
            on_player_state_change=self._on_player_state_change,
            on_macro_change=self._on_macro_change
        )
    
    def _build_ui(self):
        """Build control panel UI"""
        self._frame = tk.LabelFrame(self._parent, text="🎬 Macro Recorder")
        
        # Status label
        self._status_var = tk.StringVar(value="Ready")
        status_frame = tk.Frame(self._frame)
        status_frame.pack(fill="x", padx=8, pady=4)
        
        tk.Label(status_frame, text="Status:", font=("Arial", 9, "bold")).pack(side="left")
        self._status_label = tk.Label(status_frame, textvariable=self._status_var,
                                       font=("Arial", 9), fg="gray")
        self._status_label.pack(side="left", padx=5)
        
        # Recording controls
        rec_frame = tk.Frame(self._frame)
        rec_frame.pack(fill="x", padx=8, pady=4)
        
        self._btn_record = tk.Button(rec_frame, text="⏺ Record", 
                                      command=self._toggle_recording,
                                      bg="#f44336", fg="white", width=10)
        self._btn_record.pack(side="left", padx=2)
        
        self._btn_play = tk.Button(rec_frame, text="▶ Play",
                                    command=self._toggle_playback,
                                    bg="#4CAF50", fg="white", width=10)
        self._btn_play.pack(side="left", padx=2)
        
        self._btn_pause = tk.Button(rec_frame, text="⏸ Pause",
                                     command=self._toggle_pause,
                                     bg="#FF9800", fg="white", width=10)
        self._btn_pause.pack(side="left", padx=2)
        
        self._btn_stop = tk.Button(rec_frame, text="⏹ Stop",
                                    command=self._stop_all,
                                    bg="#9E9E9E", fg="white", width=10)
        self._btn_stop.pack(side="left", padx=2)
        
        # File operations
        file_frame = tk.Frame(self._frame)
        file_frame.pack(fill="x", padx=8, pady=4)
        
        tk.Button(file_frame, text="📂 Load", command=self._load_macro,
                  width=8).pack(side="left", padx=2)
        tk.Button(file_frame, text="💾 Save", command=self._save_macro,
                  width=8).pack(side="left", padx=2)
        tk.Button(file_frame, text="📝 New", command=self._new_macro,
                  width=8).pack(side="left", padx=2)
        
        # Macro info
        info_frame = tk.Frame(self._frame)
        info_frame.pack(fill="x", padx=8, pady=4)
        
        self._macro_name_var = tk.StringVar(value="(No macro)")
        tk.Label(info_frame, text="Macro:", font=("Arial", 9)).pack(side="left")
        tk.Label(info_frame, textvariable=self._macro_name_var,
                 font=("Arial", 9, "bold")).pack(side="left", padx=5)
        
        self._action_count_var = tk.StringVar(value="0 actions")
        tk.Label(info_frame, textvariable=self._action_count_var,
                 font=("Arial", 9), fg="gray").pack(side="right")
        
        # Speed control
        speed_frame = tk.Frame(self._frame)
        speed_frame.pack(fill="x", padx=8, pady=4)
        
        tk.Label(speed_frame, text="Speed:", font=("Arial", 9)).pack(side="left")
        self._speed_var = tk.DoubleVar(value=1.0)
        speed_scale = tk.Scale(speed_frame, from_=0.1, to=5.0, resolution=0.1,
                               orient=tk.HORIZONTAL, variable=self._speed_var,
                               length=150, command=self._on_speed_change)
        speed_scale.pack(side="left", padx=5)
        
        self._speed_label = tk.Label(speed_frame, text="1.0x", font=("Arial", 9))
        self._speed_label.pack(side="left")
        
        # Hotkey info
        hotkey_frame = tk.Frame(self._frame)
        hotkey_frame.pack(fill="x", padx=8, pady=4)
        
        hotkey_text = "Hotkeys: Ctrl+Shift+R (Record) | Ctrl+Shift+P (Play)"
        tk.Label(hotkey_frame, text=hotkey_text, font=("Arial", 8), fg="gray").pack()
    
    @property
    def frame(self) -> tk.Widget:
        """Get the panel frame widget"""
        return self._frame
    
    def pack(self, **kwargs):
        """Pack the panel"""
        self._frame.pack(**kwargs)
    
    def grid(self, **kwargs):
        """Grid the panel"""
        self._frame.grid(**kwargs)
    
    def set_on_macro_loaded(self, callback: Callable[[Macro], None]):
        """Set callback for when macro is loaded"""
        self._on_macro_loaded = callback
    
    def enable_global_hotkeys(self):
        """Enable global hotkeys"""
        self._manager.setup_global_hotkeys()
    
    def disable_global_hotkeys(self):
        """Disable global hotkeys"""
        self._manager.disable_global_hotkeys()
    
    def _toggle_recording(self):
        """Toggle recording on/off"""
        self._manager.toggle_recording()
    
    def _toggle_playback(self):
        """Toggle playback on/off"""
        self._manager.toggle_playback()
    
    def _toggle_pause(self):
        """Toggle pause state"""
        self._manager.toggle_pause()
    
    def _stop_all(self):
        """Stop recording or playback"""
        if self._manager.is_recording:
            self._manager.stop_recording()
        if self._manager.is_playing:
            self._manager.stop_playback()
    
    def _load_macro(self):
        """Load macro from file"""
        filepath = filedialog.askopenfilename(
            title="Load Macro",
            filetypes=[("Macro files", "*.mrf"), ("All files", "*.*")]
        )
        if filepath:
            if self._manager.load(filepath):
                if self._on_macro_loaded:
                    self._on_macro_loaded(self._manager.current_macro)
            else:
                messagebox.showerror("Error", "Failed to load macro")
    
    def _save_macro(self):
        """Save macro to file"""
        if not self._manager.current_macro:
            messagebox.showwarning("Warning", "No macro to save")
            return
        
        if self._manager.current_file:
            self._manager.save()
            messagebox.showinfo("Saved", f"Macro saved to {self._manager.current_file}")
        else:
            filepath = filedialog.asksaveasfilename(
                title="Save Macro",
                defaultextension=".mrf",
                filetypes=[("Macro files", "*.mrf"), ("All files", "*.*")]
            )
            if filepath:
                if self._manager.save(filepath):
                    messagebox.showinfo("Saved", f"Macro saved to {filepath}")
                else:
                    messagebox.showerror("Error", "Failed to save macro")
    
    def _new_macro(self):
        """Create new macro"""
        name = tk.simpledialog.askstring("New Macro", "Enter macro name:",
                                          initialvalue="New Macro")
        if name:
            self._manager.new_macro(name)
            if self._on_macro_loaded:
                self._on_macro_loaded(self._manager.current_macro)
    
    def _on_speed_change(self, value):
        """Handle speed slider change"""
        speed = float(value)
        self._speed_label.config(text=f"{speed:.1f}x")
        self._manager.update_settings(play_speed_multiplier=speed)
    
    def _on_recorder_state_change(self, state: RecorderState):
        """Handle recorder state change"""
        if state == RecorderState.RECORDING:
            self._status_var.set("🔴 Recording...")
            self._status_label.config(fg="red")
            self._btn_record.config(text="⏹ Stop Rec", bg="#B71C1C")
            self._btn_play.config(state="disabled")
        elif state == RecorderState.PAUSED:
            self._status_var.set("⏸ Paused")
            self._status_label.config(fg="orange")
        else:  # IDLE
            self._status_var.set("Ready")
            self._status_label.config(fg="gray")
            self._btn_record.config(text="⏺ Record", bg="#f44336")
            self._btn_play.config(state="normal")
    
    def _on_player_state_change(self, state: PlaybackState):
        """Handle player state change"""
        if state == PlaybackState.PLAYING:
            self._status_var.set("▶ Playing...")
            self._status_label.config(fg="green")
            self._btn_play.config(text="⏹ Stop", bg="#1B5E20")
            self._btn_record.config(state="disabled")
        elif state == PlaybackState.PAUSED:
            self._status_var.set("⏸ Paused")
            self._status_label.config(fg="orange")
            self._btn_play.config(text="▶ Resume", bg="#4CAF50")
        elif state == PlaybackState.ERROR:
            self._status_var.set("❌ Error")
            self._status_label.config(fg="red")
            self._btn_play.config(text="▶ Play", bg="#4CAF50")
            self._btn_record.config(state="normal")
        else:  # IDLE, STOPPED
            self._status_var.set("Ready")
            self._status_label.config(fg="gray")
            self._btn_play.config(text="▶ Play", bg="#4CAF50")
            self._btn_record.config(state="normal")
    
    def _on_macro_change(self, macro: Macro):
        """Handle macro change"""
        if macro:
            self._macro_name_var.set(macro.name)
            self._action_count_var.set(f"{len(macro.actions)} actions")
        else:
            self._macro_name_var.set("(No macro)")
            self._action_count_var.set("0 actions")


class MacroActionListPanel:
    """
    Macro action list panel UI component
    Displays and allows editing of macro actions
    """
    
    def __init__(self, parent: tk.Widget, manager: MacroManager = None):
        """
        Initialize action list panel
        
        Args:
            parent: Parent tkinter widget
            manager: MacroManager instance
        """
        self._parent = parent
        self._manager = manager or get_macro_manager()
        
        # Build UI
        self._build_ui()
        
        # Setup manager callbacks
        self._manager.set_callbacks(on_macro_change=self._refresh_list)
    
    def _build_ui(self):
        """Build action list UI"""
        self._frame = tk.LabelFrame(self._parent, text="📋 Macro Actions")
        
        # Toolbar
        toolbar = tk.Frame(self._frame)
        toolbar.pack(fill="x", padx=5, pady=3)
        
        tk.Button(toolbar, text="➕ Add", command=self._add_action, width=8).pack(side="left", padx=2)
        tk.Button(toolbar, text="🗑 Delete", command=self._delete_action, width=8).pack(side="left", padx=2)
        tk.Button(toolbar, text="⬆", command=self._move_up, width=3).pack(side="left", padx=2)
        tk.Button(toolbar, text="⬇", command=self._move_down, width=3).pack(side="left", padx=2)
        
        # Treeview
        tree_frame = tk.Frame(self._frame)
        tree_frame.pack(fill="both", expand=True, padx=5, pady=3)
        
        columns = ("STT", "Type", "Summary", "Enabled")
        self._tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=12)
        
        self._tree.column("STT", width=40, anchor=tk.CENTER)
        self._tree.column("Type", width=100, anchor=tk.W)
        self._tree.column("Summary", width=200, anchor=tk.W)
        self._tree.column("Enabled", width=60, anchor=tk.CENTER)
        
        self._tree.heading("STT", text="#")
        self._tree.heading("Type", text="Type")
        self._tree.heading("Summary", text="Summary")
        self._tree.heading("Enabled", text="On")
        
        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self._tree.yview)
        self._tree.configure(yscroll=scrollbar.set)
        
        self._tree.pack(side=tk.LEFT, fill="both", expand=True)
        scrollbar.pack(side=tk.RIGHT, fill="y")
        
        # Bind double-click to edit
        self._tree.bind("<Double-1>", self._on_double_click)
    
    @property
    def frame(self) -> tk.Widget:
        return self._frame
    
    def pack(self, **kwargs):
        self._frame.pack(**kwargs)
    
    def grid(self, **kwargs):
        self._frame.grid(**kwargs)
    
    def set_macro(self, macro: Macro):
        """Set macro to display"""
        self._refresh_list(macro)
    
    def _refresh_list(self, macro: Macro = None):
        """Refresh action list display"""
        # Clear tree
        for item in self._tree.get_children():
            self._tree.delete(item)
        
        macro = macro or self._manager.current_macro
        if not macro:
            return
        
        # Populate tree
        for idx, action in enumerate(macro.actions, 1):
            type_name = action.type.value.replace("_", " ").title()
            summary = action.get_summary()
            enabled = "✓" if action.enabled else "✗"
            
            self._tree.insert("", tk.END, values=(idx, type_name, summary, enabled),
                             tags=(action.id,))
    
    def _get_selected_index(self) -> Optional[int]:
        """Get index of selected action"""
        selection = self._tree.selection()
        if not selection:
            return None
        
        values = self._tree.item(selection[0], "values")
        return int(values[0]) - 1
    
    def _get_selected_action(self) -> Optional[MacroAction]:
        """Get selected action"""
        idx = self._get_selected_index()
        if idx is None:
            return None
        
        macro = self._manager.current_macro
        if macro and 0 <= idx < len(macro.actions):
            return macro.actions[idx]
        return None
    
    def _add_action(self):
        """Open dialog to add new action"""
        MacroActionEditor(self._parent, self._manager, on_save=self._refresh_list)
    
    def _delete_action(self):
        """Delete selected action"""
        action = self._get_selected_action()
        if not action:
            return
        
        if messagebox.askyesno("Delete", f"Delete action '{action.get_summary()}'?"):
            self._manager.remove_action(action.id)
    
    def _move_up(self):
        """Move selected action up"""
        idx = self._get_selected_index()
        if idx is None or idx == 0:
            return
        
        action = self._get_selected_action()
        if action:
            self._manager.reorder_action(action.id, idx - 1)
    
    def _move_down(self):
        """Move selected action down"""
        idx = self._get_selected_index()
        macro = self._manager.current_macro
        
        if idx is None or not macro or idx >= len(macro.actions) - 1:
            return
        
        action = self._get_selected_action()
        if action:
            self._manager.reorder_action(action.id, idx + 1)
    
    def _on_double_click(self, event):
        """Handle double-click to edit action"""
        action = self._get_selected_action()
        if action:
            MacroActionEditor(self._parent, self._manager, action, on_save=self._refresh_list)


class MacroActionEditor:
    """
    Dialog for editing macro actions
    """
    
    def __init__(self, parent: tk.Widget, manager: MacroManager,
                 action: MacroAction = None, on_save: Callable = None):
        """
        Initialize action editor dialog
        
        Args:
            parent: Parent widget
            manager: MacroManager instance
            action: Action to edit (None for new action)
            on_save: Callback when action is saved
        """
        self._manager = manager
        self._action = action
        self._on_save = on_save
        self._is_edit = action is not None
        
        # Create dialog
        self._dialog = tk.Toplevel(parent)
        self._dialog.title("Edit Action" if self._is_edit else "Add Action")
        self._dialog.geometry("450x400")
        self._dialog.transient(parent)
        self._dialog.grab_set()
        
        self._widgets = {}
        self._build_ui()
    
    def _build_ui(self):
        """Build editor UI"""
        # Action type
        type_frame = tk.Frame(self._dialog)
        type_frame.pack(fill="x", padx=15, pady=10)
        
        tk.Label(type_frame, text="Type:", font=("Arial", 9, "bold")).pack(side="left")
        
        type_options = [
            "Mouse Click", "Mouse Move", "Mouse Drag", "Mouse Scroll",
            "Key Press", "Hotkey", "Text Input",
            "Wait Time", "Wait Pixel", "Wait Window",
            "Window Focus"
        ]
        
        current_type = "Mouse Click"
        if self._action:
            current_type = self._action.type.value.replace("_", " ").title()
        
        self._type_var = tk.StringVar(value=current_type)
        type_combo = ttk.Combobox(type_frame, textvariable=self._type_var,
                                  values=type_options, state="readonly", width=20)
        type_combo.pack(side="left", padx=10)
        type_combo.bind("<<ComboboxSelected>>", lambda e: self._render_config())
        
        # Config frame
        self._config_frame = tk.LabelFrame(self._dialog, text="Configuration")
        self._config_frame.pack(fill="both", expand=True, padx=15, pady=10)
        
        # Enabled checkbox
        enabled_frame = tk.Frame(self._dialog)
        enabled_frame.pack(fill="x", padx=15, pady=5)
        
        self._enabled_var = tk.BooleanVar(value=self._action.enabled if self._action else True)
        tk.Checkbutton(enabled_frame, text="Enabled", variable=self._enabled_var).pack(anchor="w")
        
        # Comment
        comment_frame = tk.Frame(self._dialog)
        comment_frame.pack(fill="x", padx=15, pady=5)
        
        tk.Label(comment_frame, text="Comment:").pack(side="left")
        self._comment_var = tk.StringVar(value=self._action.comment if self._action and self._action.comment else "")
        tk.Entry(comment_frame, textvariable=self._comment_var, width=40).pack(side="left", padx=5)
        
        # Buttons
        btn_frame = tk.Frame(self._dialog)
        btn_frame.pack(fill="x", padx=15, pady=10)
        
        tk.Button(btn_frame, text="✓ Save", command=self._save,
                  bg="#4CAF50", fg="white", width=10).pack(side="left", padx=5)
        tk.Button(btn_frame, text="✗ Cancel", command=self._dialog.destroy,
                  bg="#f44336", fg="white", width=10).pack(side="left", padx=5)
        
        # Initial render
        self._render_config()
    
    def _render_config(self):
        """Render configuration panel based on action type"""
        # Clear config frame
        for widget in self._config_frame.winfo_children():
            widget.destroy()
        self._widgets.clear()
        
        type_str = self._type_var.get().lower().replace(" ", "_")
        
        if type_str == "mouse_click":
            self._render_mouse_click_config()
        elif type_str == "mouse_move":
            self._render_mouse_move_config()
        elif type_str == "mouse_drag":
            self._render_mouse_drag_config()
        elif type_str == "mouse_scroll":
            self._render_mouse_scroll_config()
        elif type_str == "key_press":
            self._render_key_press_config()
        elif type_str == "hotkey":
            self._render_hotkey_config()
        elif type_str == "text_input":
            self._render_text_input_config()
        elif type_str == "wait_time":
            self._render_wait_time_config()
        elif type_str == "wait_pixel":
            self._render_wait_pixel_config()
        elif type_str == "wait_window":
            self._render_wait_window_config()
        elif type_str == "window_focus":
            self._render_window_focus_config()
        else:
            tk.Label(self._config_frame, text="Configuration not available").pack(pady=20)
    
    def _render_mouse_click_config(self):
        """Render mouse click configuration"""
        action = self._action if isinstance(self._action, MouseClickAction) else None
        
        # Button
        frame1 = tk.Frame(self._config_frame)
        frame1.pack(fill="x", padx=10, pady=5)
        tk.Label(frame1, text="Button:").pack(side="left")
        self._widgets["button"] = tk.StringVar(value=action.button.value if action else "left")
        ttk.Combobox(frame1, textvariable=self._widgets["button"],
                     values=["left", "right", "middle", "double"],
                     state="readonly", width=10).pack(side="left", padx=5)
        
        # Position
        frame2 = tk.Frame(self._config_frame)
        frame2.pack(fill="x", padx=10, pady=5)
        tk.Label(frame2, text="Position:").pack(side="left")
        
        self._widgets["x"] = tk.IntVar(value=action.x if action else 0)
        tk.Label(frame2, text="X:").pack(side="left", padx=(10, 2))
        tk.Entry(frame2, textvariable=self._widgets["x"], width=6).pack(side="left")
        
        self._widgets["y"] = tk.IntVar(value=action.y if action else 0)
        tk.Label(frame2, text="Y:").pack(side="left", padx=(10, 2))
        tk.Entry(frame2, textvariable=self._widgets["y"], width=6).pack(side="left")
        
        # Repeat
        frame3 = tk.Frame(self._config_frame)
        frame3.pack(fill="x", padx=10, pady=5)
        tk.Label(frame3, text="Repeat:").pack(side="left")
        self._widgets["repeat"] = tk.IntVar(value=action.repeat if action else 1)
        tk.Spinbox(frame3, from_=1, to=100, textvariable=self._widgets["repeat"], width=6).pack(side="left", padx=5)
    
    def _render_mouse_move_config(self):
        """Render mouse move configuration"""
        action = self._action if isinstance(self._action, MouseMoveAction) else None
        
        frame = tk.Frame(self._config_frame)
        frame.pack(fill="x", padx=10, pady=5)
        tk.Label(frame, text="Move to:").pack(side="left")
        
        self._widgets["x"] = tk.IntVar(value=action.x if action else 0)
        tk.Label(frame, text="X:").pack(side="left", padx=(10, 2))
        tk.Entry(frame, textvariable=self._widgets["x"], width=6).pack(side="left")
        
        self._widgets["y"] = tk.IntVar(value=action.y if action else 0)
        tk.Label(frame, text="Y:").pack(side="left", padx=(10, 2))
        tk.Entry(frame, textvariable=self._widgets["y"], width=6).pack(side="left")
    
    def _render_mouse_drag_config(self):
        """Render mouse drag configuration"""
        action = self._action if isinstance(self._action, MouseDragAction) else None
        
        # Start position
        frame1 = tk.Frame(self._config_frame)
        frame1.pack(fill="x", padx=10, pady=5)
        tk.Label(frame1, text="From:").pack(side="left")
        
        self._widgets["x1"] = tk.IntVar(value=action.x1 if action else 0)
        tk.Label(frame1, text="X:").pack(side="left", padx=(10, 2))
        tk.Entry(frame1, textvariable=self._widgets["x1"], width=6).pack(side="left")
        
        self._widgets["y1"] = tk.IntVar(value=action.y1 if action else 0)
        tk.Label(frame1, text="Y:").pack(side="left", padx=(10, 2))
        tk.Entry(frame1, textvariable=self._widgets["y1"], width=6).pack(side="left")
        
        # End position
        frame2 = tk.Frame(self._config_frame)
        frame2.pack(fill="x", padx=10, pady=5)
        tk.Label(frame2, text="To:").pack(side="left")
        
        self._widgets["x2"] = tk.IntVar(value=action.x2 if action else 100)
        tk.Label(frame2, text="X:").pack(side="left", padx=(10, 2))
        tk.Entry(frame2, textvariable=self._widgets["x2"], width=6).pack(side="left")
        
        self._widgets["y2"] = tk.IntVar(value=action.y2 if action else 100)
        tk.Label(frame2, text="Y:").pack(side="left", padx=(10, 2))
        tk.Entry(frame2, textvariable=self._widgets["y2"], width=6).pack(side="left")
        
        # Duration
        frame3 = tk.Frame(self._config_frame)
        frame3.pack(fill="x", padx=10, pady=5)
        tk.Label(frame3, text="Duration (ms):").pack(side="left")
        self._widgets["duration_ms"] = tk.IntVar(value=action.duration_ms if action else 200)
        tk.Entry(frame3, textvariable=self._widgets["duration_ms"], width=8).pack(side="left", padx=5)
    
    def _render_mouse_scroll_config(self):
        """Render mouse scroll configuration"""
        action = self._action if isinstance(self._action, MouseScrollAction) else None
        
        # Position
        frame1 = tk.Frame(self._config_frame)
        frame1.pack(fill="x", padx=10, pady=5)
        tk.Label(frame1, text="Position:").pack(side="left")
        
        self._widgets["x"] = tk.IntVar(value=action.x if action else 0)
        tk.Label(frame1, text="X:").pack(side="left", padx=(10, 2))
        tk.Entry(frame1, textvariable=self._widgets["x"], width=6).pack(side="left")
        
        self._widgets["y"] = tk.IntVar(value=action.y if action else 0)
        tk.Label(frame1, text="Y:").pack(side="left", padx=(10, 2))
        tk.Entry(frame1, textvariable=self._widgets["y"], width=6).pack(side="left")
        
        # Direction & delta
        frame2 = tk.Frame(self._config_frame)
        frame2.pack(fill="x", padx=10, pady=5)
        
        tk.Label(frame2, text="Direction:").pack(side="left")
        self._widgets["direction"] = tk.StringVar(value=action.direction if action else "down")
        ttk.Combobox(frame2, textvariable=self._widgets["direction"],
                     values=["up", "down"], state="readonly", width=8).pack(side="left", padx=5)
        
        tk.Label(frame2, text="Delta:").pack(side="left", padx=(10, 2))
        self._widgets["delta"] = tk.IntVar(value=action.delta if action else 3)
        tk.Spinbox(frame2, from_=1, to=20, textvariable=self._widgets["delta"], width=4).pack(side="left")
    
    def _render_key_press_config(self):
        """Render key press configuration"""
        action = self._action if isinstance(self._action, KeyPressAction) else None
        
        frame1 = tk.Frame(self._config_frame)
        frame1.pack(fill="x", padx=10, pady=5)
        tk.Label(frame1, text="Key:").pack(side="left")
        self._widgets["key"] = tk.StringVar(value=action.key if action else "")
        tk.Entry(frame1, textvariable=self._widgets["key"], width=20).pack(side="left", padx=5)
        
        frame2 = tk.Frame(self._config_frame)
        frame2.pack(fill="x", padx=10, pady=5)
        tk.Label(frame2, text="Repeat:").pack(side="left")
        self._widgets["repeat"] = tk.IntVar(value=action.repeat if action else 1)
        tk.Spinbox(frame2, from_=1, to=100, textvariable=self._widgets["repeat"], width=6).pack(side="left", padx=5)
    
    def _render_hotkey_config(self):
        """Render hotkey configuration"""
        action = self._action if isinstance(self._action, HotkeyAction) else None
        
        frame = tk.Frame(self._config_frame)
        frame.pack(fill="x", padx=10, pady=5)
        tk.Label(frame, text="Keys:").pack(side="left")
        
        keys_str = "+".join(action.keys) if action and action.keys else ""
        self._widgets["keys"] = tk.StringVar(value=keys_str)
        tk.Entry(frame, textvariable=self._widgets["keys"], width=30).pack(side="left", padx=5)
        tk.Label(frame, text="(e.g., Ctrl+Shift+A)", fg="gray").pack(side="left")
    
    def _render_text_input_config(self):
        """Render text input configuration"""
        action = self._action if isinstance(self._action, TextInputAction) else None
        
        frame1 = tk.Frame(self._config_frame)
        frame1.pack(fill="x", padx=10, pady=5)
        tk.Label(frame1, text="Text:").pack(anchor="w")
        
        self._widgets["text"] = tk.Text(frame1, height=3, width=40)
        self._widgets["text"].pack(fill="x", pady=2)
        if action:
            self._widgets["text"].insert("1.0", action.text)
        
        frame2 = tk.Frame(self._config_frame)
        frame2.pack(fill="x", padx=10, pady=5)
        tk.Label(frame2, text="Mode:").pack(side="left")
        self._widgets["mode"] = tk.StringVar(value=action.mode.value if action else "paste")
        ttk.Combobox(frame2, textvariable=self._widgets["mode"],
                     values=["paste", "humanize"], state="readonly", width=10).pack(side="left", padx=5)
    
    def _render_wait_time_config(self):
        """Render wait time configuration"""
        action = self._action if isinstance(self._action, WaitTimeAction) else None
        
        frame = tk.Frame(self._config_frame)
        frame.pack(fill="x", padx=10, pady=5)
        tk.Label(frame, text="Wait (ms):").pack(side="left")
        self._widgets["ms"] = tk.IntVar(value=action.ms if action else 1000)
        tk.Entry(frame, textvariable=self._widgets["ms"], width=10).pack(side="left", padx=5)
        
        frame2 = tk.Frame(self._config_frame)
        frame2.pack(fill="x", padx=10, pady=5)
        tk.Label(frame2, text="Variance (ms):").pack(side="left")
        self._widgets["variance_ms"] = tk.IntVar(value=action.variance_ms if action and action.variance_ms else 0)
        tk.Entry(frame2, textvariable=self._widgets["variance_ms"], width=10).pack(side="left", padx=5)
    
    def _render_wait_pixel_config(self):
        """Render wait pixel configuration"""
        action = self._action if isinstance(self._action, WaitPixelAction) else None
        
        # Position
        frame1 = tk.Frame(self._config_frame)
        frame1.pack(fill="x", padx=10, pady=5)
        tk.Label(frame1, text="Position:").pack(side="left")
        
        self._widgets["x"] = tk.IntVar(value=action.x if action else 0)
        tk.Label(frame1, text="X:").pack(side="left", padx=(10, 2))
        tk.Entry(frame1, textvariable=self._widgets["x"], width=6).pack(side="left")
        
        self._widgets["y"] = tk.IntVar(value=action.y if action else 0)
        tk.Label(frame1, text="Y:").pack(side="left", padx=(10, 2))
        tk.Entry(frame1, textvariable=self._widgets["y"], width=6).pack(side="left")
        
        # RGB
        frame2 = tk.Frame(self._config_frame)
        frame2.pack(fill="x", padx=10, pady=5)
        tk.Label(frame2, text="RGB:").pack(side="left")
        
        rgb = action.rgb if action else (0, 0, 0)
        self._widgets["r"] = tk.IntVar(value=rgb[0])
        self._widgets["g"] = tk.IntVar(value=rgb[1])
        self._widgets["b"] = tk.IntVar(value=rgb[2])
        
        tk.Entry(frame2, textvariable=self._widgets["r"], width=4).pack(side="left", padx=2)
        tk.Entry(frame2, textvariable=self._widgets["g"], width=4).pack(side="left", padx=2)
        tk.Entry(frame2, textvariable=self._widgets["b"], width=4).pack(side="left", padx=2)
        
        # Timeout
        frame3 = tk.Frame(self._config_frame)
        frame3.pack(fill="x", padx=10, pady=5)
        tk.Label(frame3, text="Timeout (ms):").pack(side="left")
        self._widgets["timeout_ms"] = tk.IntVar(value=action.timeout_ms if action else 30000)
        tk.Entry(frame3, textvariable=self._widgets["timeout_ms"], width=8).pack(side="left", padx=5)
    
    def _render_wait_window_config(self):
        """Render wait window configuration"""
        action = self._action if isinstance(self._action, WaitWindowAction) else None
        
        frame1 = tk.Frame(self._config_frame)
        frame1.pack(fill="x", padx=10, pady=5)
        tk.Label(frame1, text="Title contains:").pack(side="left")
        
        title = action.window_match.title_contains if action and action.window_match else ""
        self._widgets["title_contains"] = tk.StringVar(value=title or "")
        tk.Entry(frame1, textvariable=self._widgets["title_contains"], width=30).pack(side="left", padx=5)
        
        frame2 = tk.Frame(self._config_frame)
        frame2.pack(fill="x", padx=10, pady=5)
        tk.Label(frame2, text="Timeout (ms):").pack(side="left")
        self._widgets["timeout_ms"] = tk.IntVar(value=action.timeout_ms if action else 30000)
        tk.Entry(frame2, textvariable=self._widgets["timeout_ms"], width=8).pack(side="left", padx=5)
    
    def _render_window_focus_config(self):
        """Render window focus configuration"""
        action = self._action if isinstance(self._action, WindowFocusAction) else None
        
        frame1 = tk.Frame(self._config_frame)
        frame1.pack(fill="x", padx=10, pady=5)
        tk.Label(frame1, text="Title contains:").pack(side="left")
        
        title = action.window_match.title_contains if action and action.window_match else ""
        self._widgets["title_contains"] = tk.StringVar(value=title or "")
        tk.Entry(frame1, textvariable=self._widgets["title_contains"], width=30).pack(side="left", padx=5)
        
        frame2 = tk.Frame(self._config_frame)
        frame2.pack(fill="x", padx=10, pady=5)
        self._widgets["restore"] = tk.BooleanVar(value=action.restore_if_minimized if action else True)
        tk.Checkbutton(frame2, text="Restore if minimized", variable=self._widgets["restore"]).pack(anchor="w")
    
    def _save(self):
        """Save action"""
        type_str = self._type_var.get().lower().replace(" ", "_")
        
        try:
            action = self._create_action(type_str)
            if not action:
                return
            
            action.enabled = self._enabled_var.get()
            action.comment = self._comment_var.get() or None
            
            if self._is_edit:
                action.id = self._action.id
                action.t_ms = self._action.t_ms
                self._manager.update_action(action)
            else:
                action.t_ms = self._get_next_t_ms()
                self._manager.add_action(action)
            
            if self._on_save:
                self._on_save(self._manager.current_macro)
            
            self._dialog.destroy()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save action: {e}")
            log(f"[UI] Action save error: {e}")
    
    def _get_next_t_ms(self) -> int:
        """Get next timestamp for new action"""
        macro = self._manager.current_macro
        if macro and macro.actions:
            return max(a.t_ms for a in macro.actions) + 100
        return 0
    
    def _create_action(self, type_str: str) -> Optional[MacroAction]:
        """Create action from widgets"""
        try:
            if type_str == "mouse_click":
                return MouseClickAction(
                    button=MouseButton(self._widgets["button"].get()),
                    x=self._widgets["x"].get(),
                    y=self._widgets["y"].get(),
                    repeat=self._widgets["repeat"].get()
                )
            
            elif type_str == "mouse_move":
                return MouseMoveAction(
                    x=self._widgets["x"].get(),
                    y=self._widgets["y"].get()
                )
            
            elif type_str == "mouse_drag":
                return MouseDragAction(
                    x1=self._widgets["x1"].get(),
                    y1=self._widgets["y1"].get(),
                    x2=self._widgets["x2"].get(),
                    y2=self._widgets["y2"].get(),
                    duration_ms=self._widgets["duration_ms"].get()
                )
            
            elif type_str == "mouse_scroll":
                return MouseScrollAction(
                    x=self._widgets["x"].get(),
                    y=self._widgets["y"].get(),
                    direction=self._widgets["direction"].get(),
                    delta=self._widgets["delta"].get()
                )
            
            elif type_str == "key_press":
                return KeyPressAction(
                    key=self._widgets["key"].get(),
                    repeat=self._widgets["repeat"].get()
                )
            
            elif type_str == "hotkey":
                keys_str = self._widgets["keys"].get()
                keys = [k.strip() for k in keys_str.split("+") if k.strip()]
                return HotkeyAction(keys=keys)
            
            elif type_str == "text_input":
                text = self._widgets["text"].get("1.0", tk.END).strip()
                return TextInputAction(
                    text=text,
                    mode=TextInputMode(self._widgets["mode"].get())
                )
            
            elif type_str == "wait_time":
                variance = self._widgets["variance_ms"].get()
                return WaitTimeAction(
                    ms=self._widgets["ms"].get(),
                    variance_ms=variance if variance > 0 else None
                )
            
            elif type_str == "wait_pixel":
                from core.macro.models import WindowMatch
                return WaitPixelAction(
                    x=self._widgets["x"].get(),
                    y=self._widgets["y"].get(),
                    rgb=(self._widgets["r"].get(), self._widgets["g"].get(), self._widgets["b"].get()),
                    timeout_ms=self._widgets["timeout_ms"].get()
                )
            
            elif type_str == "wait_window":
                from core.macro.models import WindowMatch
                return WaitWindowAction(
                    window_match=WindowMatch(title_contains=self._widgets["title_contains"].get()),
                    timeout_ms=self._widgets["timeout_ms"].get()
                )
            
            elif type_str == "window_focus":
                from core.macro.models import WindowMatch
                return WindowFocusAction(
                    window_match=WindowMatch(title_contains=self._widgets["title_contains"].get()),
                    restore_if_minimized=self._widgets["restore"].get()
                )
            
            else:
                messagebox.showwarning("Warning", f"Unknown action type: {type_str}")
                return None
                
        except Exception as e:
            log(f"[UI] Create action error: {e}")
            raise


# Add simpledialog import
try:
    from tkinter import simpledialog
except ImportError:
    import tkinter.simpledialog as simpledialog
