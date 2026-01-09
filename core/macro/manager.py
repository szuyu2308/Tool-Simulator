# AI GOVERNANCE:
# Apply auditor-router
# This is a CODE change

"""
Macro Manager - High-level API for macro operations
Coordinates recorder, processor, player, and file operations
"""

from __future__ import annotations
from typing import Optional, List, Callable, Dict, Any
from pathlib import Path
import os
import json
import threading

from .models import (
    Macro, MacroAction, MacroSettings, MacroTarget, WindowMatch, HotkeyConfig
)
from .recorder import MacroRecorder, RecorderState, RawEvent, WindowUtils, GlobalHotkeyManager
from .processor import MacroEventProcessor, create_macro_from_events
from .player import MacroPlayer, PlaybackState

from utils.logger import log


class MacroManager:
    """
    High-level Macro Manager
    Provides unified interface for recording, playback, and file operations
    """
    
    DEFAULT_MACRO_DIR = "data/macros"
    
    def __init__(self, macro_dir: str = None):
        """
        Initialize macro manager
        
        Args:
            macro_dir: Directory for macro files (default: data/macros)
        """
        self._macro_dir = macro_dir or self.DEFAULT_MACRO_DIR
        os.makedirs(self._macro_dir, exist_ok=True)
        
        # Components
        self._recorder = MacroRecorder()
        self._player = MacroPlayer()
        self._hotkey_manager = GlobalHotkeyManager()
        
        # State
        self._current_macro: Optional[Macro] = None
        self._current_file: Optional[str] = None
        self._recent_files: List[str] = []
        self._settings = MacroSettings()
        
        # Callbacks
        self._on_recorder_state_change: Optional[Callable[[RecorderState], None]] = None
        self._on_player_state_change: Optional[Callable[[PlaybackState], None]] = None
        self._on_macro_change: Optional[Callable[[Macro], None]] = None
        
        # Setup internal callbacks
        self._recorder.set_callbacks(
            on_state_change=self._handle_recorder_state_change
        )
        self._player.set_callbacks(
            on_state_change=self._handle_player_state_change
        )
        
        # Load recent files
        self._load_recent_files()
    
    # ==================== PROPERTIES ====================
    
    @property
    def current_macro(self) -> Optional[Macro]:
        return self._current_macro
    
    @property
    def current_file(self) -> Optional[str]:
        return self._current_file
    
    @property
    def is_recording(self) -> bool:
        return self._recorder.is_recording
    
    @property
    def is_playing(self) -> bool:
        return self._player.is_playing
    
    @property
    def recorder_state(self) -> RecorderState:
        return self._recorder.state
    
    @property
    def player_state(self) -> PlaybackState:
        return self._player.state
    
    @property
    def settings(self) -> MacroSettings:
        return self._settings
    
    @property
    def recent_files(self) -> List[str]:
        return list(self._recent_files)
    
    # ==================== CALLBACKS ====================
    
    def set_callbacks(self,
                      on_recorder_state_change: Callable[[RecorderState], None] = None,
                      on_player_state_change: Callable[[PlaybackState], None] = None,
                      on_macro_change: Callable[[Macro], None] = None):
        """Set manager callbacks"""
        self._on_recorder_state_change = on_recorder_state_change
        self._on_player_state_change = on_player_state_change
        self._on_macro_change = on_macro_change
    
    def _handle_recorder_state_change(self, state: RecorderState):
        """Handle recorder state change"""
        if state == RecorderState.IDLE and self._recorder.raw_events:
            # Recording stopped - process events
            self._process_recording()
        
        if self._on_recorder_state_change:
            self._on_recorder_state_change(state)
    
    def _handle_player_state_change(self, state: PlaybackState):
        """Handle player state change"""
        if self._on_player_state_change:
            self._on_player_state_change(state)
    
    # ==================== RECORDING ====================
    
    def start_recording(self, target_hwnd: int = None, name: str = None):
        """
        Start recording a new macro
        
        Args:
            target_hwnd: Target window handle (optional)
            name: Macro name (optional)
        """
        if self.is_recording or self.is_playing:
            return
        
        # Create new macro
        self._current_macro = Macro(
            name=name or "New Recording",
            settings=self._settings
        )
        self._current_file = None
        
        # Configure recorder
        self._recorder._target_hwnd = target_hwnd
        self._recorder.set_settings(
            include_mouse_move=self._settings.include_mouse_move,
            mouse_move_min_delta=self._settings.mouse_move_min_delta_px
        )
        
        # Start recording
        self._recorder.start_recording()
        
        log(f"[MANAGER] Recording started: {self._current_macro.name}")
    
    def stop_recording(self):
        """Stop recording"""
        if not self.is_recording:
            return
        
        self._recorder.stop_recording()
        log("[MANAGER] Recording stopped")
    
    def toggle_recording(self):
        """Toggle recording on/off"""
        if self.is_recording:
            self.stop_recording()
        else:
            self.start_recording()
    
    def pause_recording(self):
        """Pause recording"""
        self._recorder.pause_recording()
    
    def resume_recording(self):
        """Resume recording"""
        self._recorder.resume_recording()
    
    def _process_recording(self):
        """Process recorded events into macro"""
        if not self._current_macro:
            return
        
        events = self._recorder.raw_events
        if not events:
            return
        
        start_time = self._recorder._start_time or events[0].timestamp
        
        # Process events
        processor = MacroEventProcessor(self._settings)
        actions = processor.process_events(events, start_time)
        
        self._current_macro.actions = actions
        
        log(f"[MANAGER] Processed {len(events)} events -> {len(actions)} actions")
        
        if self._on_macro_change:
            self._on_macro_change(self._current_macro)
    
    # ==================== PLAYBACK ====================
    
    def play(self, hwnd: int = None, speed: float = None):
        """
        Start playback of current macro
        
        Args:
            hwnd: Target window handle (optional)
            speed: Playback speed multiplier (optional)
        """
        if not self._current_macro:
            log("[MANAGER] No macro loaded")
            return
        
        if self.is_playing or self.is_recording:
            return
        
        speed = speed or self._settings.play_speed_multiplier
        self._player.play(self._current_macro, hwnd, speed)
    
    def stop_playback(self):
        """Stop playback"""
        self._player.stop()
    
    def pause_playback(self):
        """Pause playback"""
        self._player.pause()
    
    def resume_playback(self):
        """Resume playback"""
        self._player.resume()
    
    def toggle_playback(self):
        """Toggle playback on/off"""
        if self.is_playing:
            self.stop_playback()
        elif self._current_macro:
            self.play()
    
    def toggle_pause(self):
        """Toggle pause state"""
        self._player.toggle_pause()
    
    # ==================== FILE OPERATIONS ====================
    
    def new_macro(self, name: str = "New Macro"):
        """Create new empty macro"""
        self._current_macro = Macro(name=name, settings=self._settings)
        self._current_file = None
        
        if self._on_macro_change:
            self._on_macro_change(self._current_macro)
    
    def save(self, filepath: str = None) -> bool:
        """
        Save current macro to file
        
        Args:
            filepath: File path (uses current file if not specified)
        
        Returns:
            True if saved successfully
        """
        if not self._current_macro:
            return False
        
        filepath = filepath or self._current_file
        if not filepath:
            log("[MANAGER] No file path specified")
            return False
        
        # Ensure .mrf extension
        if not filepath.endswith('.mrf'):
            filepath += '.mrf'
        
        try:
            self._current_macro.save(filepath)
            self._current_file = filepath
            self._add_recent_file(filepath)
            log(f"[MANAGER] Saved: {filepath}")
            return True
        except Exception as e:
            log(f"[MANAGER] Save error: {e}")
            return False
    
    def save_as(self, filepath: str) -> bool:
        """Save current macro to new file"""
        return self.save(filepath)
    
    def load(self, filepath: str) -> bool:
        """
        Load macro from file
        
        Args:
            filepath: File path to load
        
        Returns:
            True if loaded successfully
        """
        try:
            self._current_macro = Macro.load(filepath)
            self._current_file = filepath
            self._settings = self._current_macro.settings
            self._add_recent_file(filepath)
            
            if self._on_macro_change:
                self._on_macro_change(self._current_macro)
            
            log(f"[MANAGER] Loaded: {filepath}")
            return True
        except Exception as e:
            log(f"[MANAGER] Load error: {e}")
            return False
    
    def get_macro_files(self) -> List[str]:
        """Get list of .mrf files in macro directory"""
        files = []
        for f in os.listdir(self._macro_dir):
            if f.endswith('.mrf'):
                files.append(os.path.join(self._macro_dir, f))
        return sorted(files)
    
    def _add_recent_file(self, filepath: str):
        """Add file to recent list"""
        abs_path = os.path.abspath(filepath)
        if abs_path in self._recent_files:
            self._recent_files.remove(abs_path)
        self._recent_files.insert(0, abs_path)
        self._recent_files = self._recent_files[:10]  # Keep only 10 recent
        self._save_recent_files()
    
    def _load_recent_files(self):
        """Load recent files list"""
        recent_file = os.path.join(self._macro_dir, '.recent.json')
        try:
            if os.path.exists(recent_file):
                with open(recent_file, 'r') as f:
                    self._recent_files = json.load(f)
        except:
            self._recent_files = []
    
    def _save_recent_files(self):
        """Save recent files list"""
        recent_file = os.path.join(self._macro_dir, '.recent.json')
        try:
            with open(recent_file, 'w') as f:
                json.dump(self._recent_files, f)
        except:
            pass
    
    # ==================== ACTION EDITING ====================
    
    def add_action(self, action: MacroAction):
        """Add action to current macro"""
        if self._current_macro:
            self._current_macro.add_action(action)
            if self._on_macro_change:
                self._on_macro_change(self._current_macro)
    
    def remove_action(self, action_id: str):
        """Remove action from current macro"""
        if self._current_macro:
            self._current_macro.remove_action(action_id)
            if self._on_macro_change:
                self._on_macro_change(self._current_macro)
    
    def update_action(self, action: MacroAction):
        """Update existing action"""
        if self._current_macro:
            for i, a in enumerate(self._current_macro.actions):
                if a.id == action.id:
                    self._current_macro.actions[i] = action
                    break
            if self._on_macro_change:
                self._on_macro_change(self._current_macro)
    
    def reorder_action(self, action_id: str, new_index: int):
        """Move action to new position"""
        if self._current_macro:
            self._current_macro.reorder_action(action_id, new_index)
            if self._on_macro_change:
                self._on_macro_change(self._current_macro)
    
    def set_action_enabled(self, action_id: str, enabled: bool):
        """Enable/disable action"""
        if self._current_macro:
            action = self._current_macro.get_action(action_id)
            if action:
                action.enabled = enabled
                if self._on_macro_change:
                    self._on_macro_change(self._current_macro)
    
    # ==================== SETTINGS ====================
    
    def update_settings(self, **kwargs):
        """Update macro settings"""
        for key, value in kwargs.items():
            if hasattr(self._settings, key):
                setattr(self._settings, key, value)
        
        if self._current_macro:
            self._current_macro.settings = self._settings
    
    # ==================== HOTKEYS ====================
    
    def setup_global_hotkeys(self, config: HotkeyConfig = None):
        """Setup global hotkeys for recording/playback control"""
        config = config or self._settings.hotkeys
        
        self._hotkey_manager.register(config.record_start_stop, self.toggle_recording)
        self._hotkey_manager.register(config.play_toggle, self.toggle_playback)
        self._hotkey_manager.register(config.pause_toggle, self.toggle_pause)
        self._hotkey_manager.register(config.stop_playback, self.stop_playback)
        
        self._hotkey_manager.start()
        log("[MANAGER] Global hotkeys enabled")
    
    def disable_global_hotkeys(self):
        """Disable global hotkeys"""
        self._hotkey_manager.stop()
        log("[MANAGER] Global hotkeys disabled")
    
    # ==================== UTILITY ====================
    
    def find_windows(self, title_contains: str = None,
                     class_name: str = None,
                     process_name: str = None) -> List[Dict[str, Any]]:
        """
        Find windows matching criteria
        
        Returns:
            List of window info dicts with hwnd, title, class, process
        """
        hwnds = WindowUtils.find_windows_by_match(
            title_contains=title_contains,
            class_name=class_name,
            process_name=process_name
        )
        
        results = []
        for hwnd in hwnds:
            results.append({
                'hwnd': hwnd,
                'title': WindowUtils.get_window_title(hwnd),
                'class': WindowUtils.get_window_class(hwnd),
                'process': WindowUtils.get_window_process_name(hwnd)
            })
        
        return results
    
    def shutdown(self):
        """Clean shutdown"""
        self._recorder.shutdown()
        self._player.shutdown()
        self._hotkey_manager.stop()
        log("[MANAGER] Shutdown complete")


# Singleton instance
_manager_instance: Optional[MacroManager] = None


def get_macro_manager() -> MacroManager:
    """Get singleton macro manager instance"""
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = MacroManager()
    return _manager_instance
