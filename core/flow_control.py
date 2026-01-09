# AI GOVERNANCE:
# Apply auditor-router
# This is a CODE change

"""
Flow Control Module — per UPGRADE_PLAN_V2 spec B4
Implements: Label, Goto, Repeat, EmbedMacro
"""

from __future__ import annotations
import json
import os
from typing import Optional, Dict, List, Any, TYPE_CHECKING
from dataclasses import dataclass, field
from enum import Enum

from utils.logger import log

if TYPE_CHECKING:
    from core.action_engine import ActionEngine


class FlowControlType(Enum):
    """Types of flow control actions"""
    LABEL = "Label"
    GOTO = "Goto"
    REPEAT = "Repeat"
    EMBED_MACRO = "EmbedMacro"
    IF = "If"
    END_IF = "EndIf"


@dataclass
class FlowState:
    """Tracks flow control state during execution"""
    # Label name -> action index mapping
    labels: Dict[str, int] = field(default_factory=dict)
    
    # Repeat counters: loop_id -> current iteration
    repeat_counters: Dict[str, int] = field(default_factory=dict)
    
    # Repeat starts: loop_id -> start index
    repeat_starts: Dict[str, int] = field(default_factory=dict)
    
    # Call stack for embedded macros
    call_stack: List[Dict[str, Any]] = field(default_factory=list)
    
    # Current execution index
    current_index: int = 0
    
    # Next index to jump to (None = continue normally)
    jump_to: Optional[int] = None
    
    def reset(self):
        """Reset all flow state"""
        self.labels.clear()
        self.repeat_counters.clear()
        self.repeat_starts.clear()
        self.call_stack.clear()
        self.current_index = 0
        self.jump_to = None


def build_label_map(actions: List[Dict[str, Any]]) -> Dict[str, int]:
    """
    Pre-scan actions to build label -> index mapping
    
    Args:
        actions: List of action dictionaries
        
    Returns:
        Dict mapping label names to action indices
    """
    labels = {}
    
    for i, action in enumerate(actions):
        action_type = action.get("type", "")
        
        if action_type == "Label":
            label_name = action.get("params", {}).get("name", "")
            if label_name:
                labels[label_name] = i
                log(f"[FLOW] Label '{label_name}' at index {i}")
    
    return labels


class FlowController:
    """
    Handles flow control logic during macro execution
    """
    
    def __init__(self, actions: List[Dict[str, Any]], macros_dir: str = "data/macros"):
        """
        Args:
            actions: List of action dictionaries
            macros_dir: Directory containing macro files for EmbedMacro
        """
        self.actions = actions
        self.macros_dir = macros_dir
        self.state = FlowState()
        
        # Pre-build label map
        self.state.labels = build_label_map(actions)
    
    def reset(self):
        """Reset flow state for new execution"""
        self.state.reset()
        self.state.labels = build_label_map(self.actions)
    
    def get_next_index(self, current_index: int) -> int:
        """
        Get the next action index after processing flow control
        
        Args:
            current_index: Current action index
            
        Returns:
            Next action index to execute
        """
        self.state.current_index = current_index
        
        # Check for pending jump
        if self.state.jump_to is not None:
            next_idx = self.state.jump_to
            self.state.jump_to = None
            return next_idx
        
        # Normal progression
        return current_index + 1
    
    def process_flow_action(self, action: Dict[str, Any], current_index: int) -> Optional[int]:
        """
        Process a flow control action
        
        Args:
            action: The action dictionary
            current_index: Current action index
            
        Returns:
            Next index to jump to, or None to continue normally
        """
        action_type = action.get("type", "")
        params = action.get("params", {})
        
        if action_type == "Label":
            # Labels are just markers, continue normally
            return None
        
        elif action_type == "Goto":
            return self._handle_goto(params)
        
        elif action_type == "Repeat":
            return self._handle_repeat(params, current_index)
        
        elif action_type == "EmbedMacro":
            return self._handle_embed_macro(params, current_index)
        
        return None
    
    def _handle_goto(self, params: dict) -> Optional[int]:
        """Handle Goto action"""
        target_label = params.get("target", "")
        
        if not target_label:
            log("[FLOW] Goto: no target label specified")
            return None
        
        if target_label not in self.state.labels:
            log(f"[FLOW] Goto: label '{target_label}' not found")
            return None
        
        target_index = self.state.labels[target_label]
        log(f"[FLOW] Goto '{target_label}' -> index {target_index}")
        
        return target_index
    
    def _handle_repeat(self, params: dict, current_index: int) -> Optional[int]:
        """
        Handle Repeat action
        
        Per spec B4-3:
        - Repeat(count, end_label): Loop count times, then jump to end_label
        - Uses loop_id to track nested loops
        """
        count = params.get("count", 1)
        end_label = params.get("end_label", "")
        loop_id = params.get("loop_id", f"loop_{current_index}")
        
        # Initialize counter if first iteration
        if loop_id not in self.state.repeat_counters:
            self.state.repeat_counters[loop_id] = 0
            self.state.repeat_starts[loop_id] = current_index
            log(f"[FLOW] Repeat '{loop_id}': starting {count} iterations")
        
        # Increment counter
        self.state.repeat_counters[loop_id] += 1
        current_iteration = self.state.repeat_counters[loop_id]
        
        log(f"[FLOW] Repeat '{loop_id}': iteration {current_iteration}/{count}")
        
        # Check if loop is complete
        if current_iteration >= count:
            # Clean up
            del self.state.repeat_counters[loop_id]
            del self.state.repeat_starts[loop_id]
            
            # Jump to end label if specified
            if end_label and end_label in self.state.labels:
                return self.state.labels[end_label]
            
            # Otherwise continue normally
            return None
        
        # Continue to next action (loop body)
        return None
    
    def _handle_embed_macro(self, params: dict, current_index: int) -> Optional[int]:
        """
        Handle EmbedMacro action
        
        Per spec B4-4:
        - EmbedMacro(macro_name): Execute another macro inline
        - Push current state to call stack, load and execute embedded macro
        """
        macro_name = params.get("macro_name", "")
        
        if not macro_name:
            log("[FLOW] EmbedMacro: no macro name specified")
            return None
        
        # Load embedded macro
        embedded_actions = self._load_macro(macro_name)
        if not embedded_actions:
            log(f"[FLOW] EmbedMacro: failed to load '{macro_name}'")
            return None
        
        # Push current state to call stack
        self.state.call_stack.append({
            "return_index": current_index + 1,
            "parent_actions": self.actions
        })
        
        # Replace actions with embedded macro
        self.actions = embedded_actions
        self.state.labels = build_label_map(embedded_actions)
        
        log(f"[FLOW] EmbedMacro: executing '{macro_name}' ({len(embedded_actions)} actions)")
        
        # Start at beginning of embedded macro
        return 0
    
    def _load_macro(self, macro_name: str) -> Optional[List[Dict[str, Any]]]:
        """Load macro from file"""
        # Try different file paths
        possible_paths = [
            os.path.join(self.macros_dir, f"{macro_name}.json"),
            os.path.join(self.macros_dir, macro_name),
            macro_name  # Absolute path
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    # Handle different macro formats
                    if isinstance(data, list):
                        return data
                    elif isinstance(data, dict):
                        return data.get("actions", data.get("steps", []))
                    
                except Exception as e:
                    log(f"[FLOW] Error loading macro '{path}': {e}")
        
        return None
    
    def return_from_embed(self) -> Optional[int]:
        """
        Return from embedded macro execution
        
        Returns:
            Index to return to, or None if not in embedded macro
        """
        if not self.state.call_stack:
            return None
        
        # Pop from call stack
        state = self.state.call_stack.pop()
        
        # Restore parent actions
        self.actions = state["parent_actions"]
        self.state.labels = build_label_map(self.actions)
        
        return_index = state["return_index"]
        log(f"[FLOW] Return from embed -> index {return_index}")
        
        return return_index
    
    def is_in_embedded_macro(self) -> bool:
        """Check if currently executing an embedded macro"""
        return len(self.state.call_stack) > 0
    
    def get_repeat_info(self, loop_id: str) -> Optional[Dict[str, int]]:
        """
        Get information about a repeat loop
        
        Args:
            loop_id: Loop identifier
            
        Returns:
            Dict with 'current' and 'start_index', or None if not in loop
        """
        if loop_id not in self.state.repeat_counters:
            return None
        
        return {
            "current": self.state.repeat_counters[loop_id],
            "start_index": self.state.repeat_starts[loop_id]
        }


def is_flow_control_action(action_type: str) -> bool:
    """Check if action type is a flow control action"""
    flow_types = {"Label", "Goto", "Repeat", "EmbedMacro", "If", "EndIf"}
    return action_type in flow_types


def create_label_action(name: str) -> Dict[str, Any]:
    """Create a Label action"""
    return {
        "type": "Label",
        "params": {"name": name}
    }


def create_goto_action(target: str) -> Dict[str, Any]:
    """Create a Goto action"""
    return {
        "type": "Goto",
        "params": {"target": target}
    }


def create_repeat_action(count: int, end_label: str = "", loop_id: str = "") -> Dict[str, Any]:
    """Create a Repeat action"""
    params = {"count": count}
    if end_label:
        params["end_label"] = end_label
    if loop_id:
        params["loop_id"] = loop_id
    
    return {
        "type": "Repeat",
        "params": params
    }


def create_embed_macro_action(macro_name: str) -> Dict[str, Any]:
    """Create an EmbedMacro action"""
    return {
        "type": "EmbedMacro",
        "params": {"macro_name": macro_name}
    }
