# AI GOVERNANCE:
# Apply auditor-router
# This is a CODE change

"""
Macro Event Processor - Consolidates raw events into macro actions
Handles mouse path consolidation, text consolidation, and action creation
"""

from __future__ import annotations
from typing import List, Optional, Tuple, Dict, Any
from dataclasses import dataclass
import math
import time

from .models import (
    Macro, MacroAction, MacroActionType, MacroSettings,
    MouseMoveAction, MouseClickAction, MouseDragAction, MouseScrollAction,
    KeyPressAction, HotkeyAction, TextInputAction, WaitTimeAction,
    WindowFocusAction, WindowMatch,
    MouseButton, MouseCurve, KeyPressMode, HotkeyOrder, TextInputMode
)
from .recorder import RawEvent, RawEventType

from utils.logger import log


# ==================== PATH SIMPLIFICATION (RDP Algorithm) ====================

def rdp_simplify(points: List[Tuple[int, int, int]], epsilon: float) -> List[Tuple[int, int, int]]:
    """
    Ramer-Douglas-Peucker algorithm for polyline simplification
    
    Args:
        points: List of (x, y, dt_ms) tuples
        epsilon: Maximum distance threshold
    
    Returns:
        Simplified list of points
    """
    if len(points) < 3:
        return points
    
    # Find point with max distance from line between first and last
    first = points[0]
    last = points[-1]
    
    max_dist = 0
    max_idx = 0
    
    for i in range(1, len(points) - 1):
        dist = _perpendicular_distance(points[i], first, last)
        if dist > max_dist:
            max_dist = dist
            max_idx = i
    
    # If max distance > epsilon, split and recurse
    if max_dist > epsilon:
        left = rdp_simplify(points[:max_idx + 1], epsilon)
        right = rdp_simplify(points[max_idx:], epsilon)
        return left[:-1] + right
    else:
        return [first, last]


def _perpendicular_distance(point: Tuple[int, int, int], 
                            line_start: Tuple[int, int, int], 
                            line_end: Tuple[int, int, int]) -> float:
    """Calculate perpendicular distance from point to line"""
    x0, y0, _ = point
    x1, y1, _ = line_start
    x2, y2, _ = line_end
    
    dx = x2 - x1
    dy = y2 - y1
    
    if dx == 0 and dy == 0:
        return math.sqrt((x0 - x1) ** 2 + (y0 - y1) ** 2)
    
    t = max(0, min(1, ((x0 - x1) * dx + (y0 - y1) * dy) / (dx * dx + dy * dy)))
    
    proj_x = x1 + t * dx
    proj_y = y1 + t * dy
    
    return math.sqrt((x0 - proj_x) ** 2 + (y0 - proj_y) ** 2)


# ==================== EVENT PROCESSOR ====================

@dataclass
class PendingClick:
    """Pending click waiting for up event"""
    event: RawEvent
    t_ms: int


@dataclass
class PendingText:
    """Pending text consolidation"""
    chars: List[str]
    start_t_ms: int
    last_t_ms: int


class MacroEventProcessor:
    """
    Processes raw events into consolidated macro actions
    """
    
    # Time thresholds (ms)
    TEXT_CONSOLIDATION_THRESHOLD = 300  # Max time between chars for text consolidation
    DOUBLE_CLICK_THRESHOLD = 400  # Max time between clicks for double-click
    DRAG_THRESHOLD = 50  # Min distance for drag detection
    
    def __init__(self, settings: MacroSettings = None):
        self._settings = settings or MacroSettings()
        
        # Processing state
        self._start_time: Optional[float] = None
        self._actions: List[MacroAction] = []
        
        # Pending states
        self._pending_click: Optional[PendingClick] = None
        self._pending_text: Optional[PendingText] = None
        self._mouse_path: List[Tuple[int, int, int]] = []  # [(x, y, t_ms), ...]
        self._last_click_event: Optional[RawEvent] = None
        self._last_click_t_ms: int = 0
        
        # Modifier key tracking
        self._held_modifiers: Dict[str, int] = {}  # key -> t_ms
    
    def process_events(self, events: List[RawEvent], start_time: float) -> List[MacroAction]:
        """
        Process list of raw events into macro actions
        
        Args:
            events: List of raw events from recorder
            start_time: Recording start time (perf_counter)
        
        Returns:
            List of consolidated macro actions
        """
        self._start_time = start_time
        self._actions.clear()
        self._reset_state()
        
        for event in events:
            self._process_event(event)
        
        # Finalize pending states
        self._finalize_pending()
        
        # Post-process: consolidate mouse paths
        if self._settings.include_mouse_move:
            self._consolidate_mouse_paths()
        
        return self._actions
    
    def _reset_state(self):
        """Reset processing state"""
        self._pending_click = None
        self._pending_text = None
        self._mouse_path.clear()
        self._last_click_event = None
        self._last_click_t_ms = 0
        self._held_modifiers.clear()
    
    def _event_to_ms(self, event: RawEvent) -> int:
        """Convert event timestamp to milliseconds offset"""
        if self._start_time is None:
            return 0
        return int((event.timestamp - self._start_time) * 1000)
    
    def _process_event(self, event: RawEvent):
        """Process single event"""
        t_ms = self._event_to_ms(event)
        
        if event.event_type == RawEventType.MOUSE_MOVE:
            self._on_mouse_move(event, t_ms)
        
        elif event.event_type == RawEventType.MOUSE_DOWN:
            self._on_mouse_down(event, t_ms)
        
        elif event.event_type == RawEventType.MOUSE_UP:
            self._on_mouse_up(event, t_ms)
        
        elif event.event_type == RawEventType.MOUSE_SCROLL:
            self._on_mouse_scroll(event, t_ms)
        
        elif event.event_type == RawEventType.KEY_DOWN:
            self._on_key_down(event, t_ms)
        
        elif event.event_type == RawEventType.KEY_UP:
            self._on_key_up(event, t_ms)
        
        elif event.event_type == RawEventType.WINDOW_FOCUS:
            self._on_window_focus(event, t_ms)
    
    def _on_mouse_move(self, event: RawEvent, t_ms: int):
        """Handle mouse move event"""
        if event.x is not None and event.y is not None:
            self._mouse_path.append((event.x, event.y, t_ms))
    
    def _on_mouse_down(self, event: RawEvent, t_ms: int):
        """Handle mouse down event"""
        # Finalize any pending text
        self._finalize_text()
        
        # Flush mouse path before click
        self._flush_mouse_path(t_ms)
        
        # Store as pending click (wait for up to determine click vs drag)
        self._pending_click = PendingClick(event=event, t_ms=t_ms)
    
    def _on_mouse_up(self, event: RawEvent, t_ms: int):
        """Handle mouse up event"""
        if not self._pending_click:
            return
        
        down_event = self._pending_click.event
        down_t_ms = self._pending_click.t_ms
        
        # Calculate distance moved
        dist = 0
        if down_event.x is not None and event.x is not None:
            dist = math.sqrt((event.x - down_event.x) ** 2 + (event.y - down_event.y) ** 2)
        
        # Determine if drag or click
        if dist > self.DRAG_THRESHOLD:
            # This is a drag
            action = MouseDragAction(
                t_ms=down_t_ms,
                x1=down_event.x or 0,
                y1=down_event.y or 0,
                x2=event.x or 0,
                y2=event.y or 0,
                button=self._map_button(down_event.button),
                duration_ms=t_ms - down_t_ms
            )
            self._actions.append(action)
        else:
            # This is a click - check for double click
            button = self._map_button(down_event.button)
            
            if (self._last_click_event and 
                down_event.button == self._last_click_event.button and
                t_ms - self._last_click_t_ms < self.DOUBLE_CLICK_THRESHOLD):
                # Double click - modify last action
                if self._actions and isinstance(self._actions[-1], MouseClickAction):
                    self._actions[-1].button = MouseButton.DOUBLE
            else:
                # Single click
                action = MouseClickAction(
                    t_ms=down_t_ms,
                    button=button,
                    x=down_event.x or 0,
                    y=down_event.y or 0,
                    hold_ms=t_ms - down_t_ms if t_ms - down_t_ms > 100 else None
                )
                self._actions.append(action)
            
            self._last_click_event = down_event
            self._last_click_t_ms = t_ms
        
        self._pending_click = None
    
    def _on_mouse_scroll(self, event: RawEvent, t_ms: int):
        """Handle mouse scroll event"""
        self._finalize_text()
        
        action = MouseScrollAction(
            t_ms=t_ms,
            x=event.x or 0,
            y=event.y or 0,
            delta=abs(event.scroll_delta or 1),
            direction="up" if (event.scroll_delta or 0) > 0 else "down"
        )
        self._actions.append(action)
    
    def _on_key_down(self, event: RawEvent, t_ms: int):
        """Handle key down event"""
        key = event.key or ""
        
        # Track modifier keys
        if key.lower() in ('ctrl', 'alt', 'shift', 'cmd', 'ctrl_l', 'ctrl_r', 
                           'alt_l', 'alt_r', 'shift_l', 'shift_r'):
            normalized = key.lower().replace('_l', '').replace('_r', '')
            self._held_modifiers[normalized] = t_ms
            return
        
        # Check if this is a hotkey (modifier + key)
        if self._held_modifiers:
            self._finalize_text()
            
            keys = list(self._held_modifiers.keys()) + [key]
            action = HotkeyAction(
                t_ms=t_ms,
                keys=keys,
                order=HotkeyOrder.SIMULTANEOUS
            )
            self._actions.append(action)
            return
        
        # Check if printable character for text consolidation
        if len(key) == 1 and key.isprintable():
            if self._pending_text:
                if t_ms - self._pending_text.last_t_ms < self.TEXT_CONSOLIDATION_THRESHOLD:
                    self._pending_text.chars.append(key)
                    self._pending_text.last_t_ms = t_ms
                    return
                else:
                    self._finalize_text()
            
            self._pending_text = PendingText(
                chars=[key],
                start_t_ms=t_ms,
                last_t_ms=t_ms
            )
            return
        
        # Non-printable key - create key press action
        self._finalize_text()
        
        action = KeyPressAction(
            t_ms=t_ms,
            key=key,
            mode=KeyPressMode.PRESS
        )
        self._actions.append(action)
    
    def _on_key_up(self, event: RawEvent, t_ms: int):
        """Handle key up event"""
        key = event.key or ""
        
        # Remove from held modifiers
        if key.lower() in ('ctrl', 'alt', 'shift', 'cmd', 'ctrl_l', 'ctrl_r',
                           'alt_l', 'alt_r', 'shift_l', 'shift_r'):
            normalized = key.lower().replace('_l', '').replace('_r', '')
            self._held_modifiers.pop(normalized, None)
    
    def _on_window_focus(self, event: RawEvent, t_ms: int):
        """Handle window focus change"""
        self._finalize_text()
        
        action = WindowFocusAction(
            t_ms=t_ms,
            window_match=WindowMatch(
                title_contains=event.window_title,
                class_name=event.window_class
            )
        )
        self._actions.append(action)
    
    def _map_button(self, button: Optional[str]) -> MouseButton:
        """Map button string to MouseButton enum"""
        button_map = {
            'left': MouseButton.LEFT,
            'right': MouseButton.RIGHT,
            'middle': MouseButton.MIDDLE
        }
        return button_map.get(button or 'left', MouseButton.LEFT)
    
    def _finalize_text(self):
        """Finalize pending text into TextInputAction"""
        if not self._pending_text:
            return
        
        text = ''.join(self._pending_text.chars)
        if text:
            action = TextInputAction(
                t_ms=self._pending_text.start_t_ms,
                text=text,
                mode=TextInputMode.HUMANIZE if len(text) > 1 else TextInputMode.PASTE
            )
            self._actions.append(action)
        
        self._pending_text = None
    
    def _flush_mouse_path(self, current_t_ms: int):
        """Flush accumulated mouse path as MouseMoveAction"""
        if len(self._mouse_path) < 2:
            self._mouse_path.clear()
            return
        
        if not self._settings.include_mouse_move:
            self._mouse_path.clear()
            return
        
        # Simplify path
        epsilon = max(3, self._settings.mouse_move_min_delta_px)
        simplified = rdp_simplify(self._mouse_path, epsilon)
        
        if len(simplified) >= 2:
            start_x, start_y, start_t = simplified[0]
            end_x, end_y, _ = simplified[-1]
            
            action = MouseMoveAction(
                t_ms=start_t,
                x=end_x,
                y=end_y,
                path=simplified if len(simplified) > 2 else None,
                curve=MouseCurve.LINEAR
            )
            self._actions.append(action)
        
        self._mouse_path.clear()
    
    def _finalize_pending(self):
        """Finalize all pending states"""
        self._finalize_text()
        
        if self._pending_click:
            # Mouse button still held - create click without hold duration
            action = MouseClickAction(
                t_ms=self._pending_click.t_ms,
                button=self._map_button(self._pending_click.event.button),
                x=self._pending_click.event.x or 0,
                y=self._pending_click.event.y or 0
            )
            self._actions.append(action)
            self._pending_click = None
        
        # Flush remaining mouse path
        if self._mouse_path:
            self._flush_mouse_path(self._mouse_path[-1][2] if self._mouse_path else 0)
    
    def _consolidate_mouse_paths(self):
        """Post-process to merge adjacent mouse move actions"""
        if not self._actions:
            return
        
        consolidated = []
        pending_moves = []
        
        for action in self._actions:
            if isinstance(action, MouseMoveAction):
                pending_moves.append(action)
            else:
                # Flush pending moves
                if pending_moves:
                    merged = self._merge_mouse_moves(pending_moves)
                    consolidated.extend(merged)
                    pending_moves.clear()
                
                consolidated.append(action)
        
        # Handle remaining moves
        if pending_moves:
            merged = self._merge_mouse_moves(pending_moves)
            consolidated.extend(merged)
        
        self._actions = consolidated
    
    def _merge_mouse_moves(self, moves: List[MouseMoveAction]) -> List[MouseMoveAction]:
        """Merge multiple mouse moves into fewer actions"""
        if not moves:
            return []
        
        if len(moves) == 1:
            return moves
        
        # Combine all points
        all_points = []
        for move in moves:
            if move.path:
                all_points.extend(move.path)
            else:
                all_points.append((move.x, move.y, move.t_ms))
        
        if not all_points:
            return []
        
        # Simplify combined path
        epsilon = max(5, self._settings.mouse_move_min_delta_px)
        simplified = rdp_simplify(all_points, epsilon)
        
        if len(simplified) < 2:
            return []
        
        # Create single action with path
        start_x, start_y, start_t = simplified[0]
        end_x, end_y, _ = simplified[-1]
        
        return [MouseMoveAction(
            t_ms=start_t,
            x=end_x,
            y=end_y,
            path=simplified if len(simplified) > 2 else None,
            curve=MouseCurve.LINEAR
        )]


def create_macro_from_events(events: List[RawEvent], 
                              start_time: float,
                              name: str = "New Macro",
                              settings: MacroSettings = None) -> Macro:
    """
    Convenience function to create a Macro from raw events
    
    Args:
        events: Raw events from recorder
        start_time: Recording start time
        name: Macro name
        settings: Macro settings
    
    Returns:
        Populated Macro object
    """
    settings = settings or MacroSettings()
    processor = MacroEventProcessor(settings)
    actions = processor.process_events(events, start_time)
    
    macro = Macro(name=name, settings=settings)
    macro.actions = actions
    
    return macro
