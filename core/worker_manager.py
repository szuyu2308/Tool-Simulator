"""
WorkerAssignmentManager - Quản lý gán Worker ID cho LDPlayer instances
Hỗ trợ:
- Tìm gaps trong Worker ID sequence
- Assign auto Worker ID (fill gaps)
- Remove Worker (không reset toàn bộ)
- Lưu/load assignment config
"""

import json
import os
from utils.logger import log


WORKER_CONFIG_FILE = "data/worker_assignments.json"


class WorkerAssignmentManager:
    """Quản lý mapping từ LDPlayer window → Worker ID"""
    
    def __init__(self):
        """Initialize từ saved config"""
        self.assignments = {}  # hwnd/title → worker_id
        self.reverse_map = {}  # worker_id → hwnd/title
        self.load()
    
    def load(self):
        """Load từ file config"""
        if not os.path.exists(WORKER_CONFIG_FILE):
            self.assignments = {}
            self.reverse_map = {}
            return
        
        try:
            with open(WORKER_CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.assignments = data.get("assignments", {})
                # Rebuild reverse_map
                self.reverse_map = {int(v): k for k, v in self.assignments.items()}
                log(f"[WorkerMgr] Loaded {len(self.assignments)} assignments")
        except Exception as e:
            log(f"[WorkerMgr] Load failed: {e}")
            self.assignments = {}
            self.reverse_map = {}
    
    def save(self):
        """Save to file"""
        os.makedirs(os.path.dirname(WORKER_CONFIG_FILE), exist_ok=True)
        try:
            with open(WORKER_CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "assignments": self.assignments,  # ldplayer_id → worker_id
                        "reverse": {str(k): v for k, v in self.reverse_map.items()}
                    },
                    f,
                    indent=2,
                    ensure_ascii=False
                )
            log(f"[WorkerMgr] Saved {len(self.assignments)} assignments")
        except Exception as e:
            log(f"[WorkerMgr] Save failed: {e}")
    
    def get_assigned_worker_ids(self) -> set:
        """Lấy danh sách Worker ID đã được gán"""
        return set(self.reverse_map.keys())
    
    def get_worker_id(self, ldplayer_identifier: str) -> int | None:
        """Lấy Worker ID được gán cho LDPlayer (key có thể là hwnd hoặc title)"""
        return self.assignments.get(str(ldplayer_identifier))
    
    def find_next_available_worker_id(self) -> int:
        """
        Tìm Worker ID tiếp theo có sẵn
        Logic: Nếu có Worker 1,3,5 → return 2 (fill gap)
        Nếu có Worker 1,2,3 → return 4 (next sequential)
        """
        assigned_ids = self.get_assigned_worker_ids()
        
        if not assigned_ids:
            return 1
        
        # Tìm max ID hiện tại
        max_id = max(assigned_ids)
        
        # Tìm gap từ 1 đến max_id
        for i in range(1, max_id + 1):
            if i not in assigned_ids:
                return i
        
        # Không có gap → return max_id + 1
        return max_id + 1
    
    def assign_worker(self, ldplayer_identifier: str, worker_id: int) -> bool:
        """
        Gán Worker ID cho LDPlayer
        Returns: True nếu success, False nếu worker_id đã được assign cho cái khác
        """
        str_id = str(ldplayer_identifier)
        
        # Check nếu worker_id đã được assign cho cái khác
        if worker_id in self.reverse_map:
            existing = self.reverse_map[worker_id]
            if existing != str_id:
                log(f"[WorkerMgr] Worker {worker_id} already assigned to {existing}")
                return False
        
        # Remove old assignment của ldplayer này nếu có
        old_worker = self.assignments.get(str_id)
        if old_worker is not None and old_worker in self.reverse_map:
            del self.reverse_map[old_worker]
        
        # Assign mới
        self.assignments[str_id] = worker_id
        self.reverse_map[worker_id] = str_id
        
        log(f"[WorkerMgr] Assigned {ldplayer_identifier} → Worker {worker_id}")
        self.save()
        return True
    
    def auto_assign_selected(self, ldplayer_identifiers: list[str]) -> dict:
        """
        Auto-assign Worker IDs cho danh sách LDPlayer được select
        Trả về dict {ldplayer_id → worker_id} các cái được assign mới
        
        Logic:
        - Tìm Worker ID tiếp theo available cho mỗi LDPlayer
        - Fill gaps trước
        """
        assigned_map = {}
        
        for ldplayer_id in ldplayer_identifiers:
            # Bỏ qua nếu đã được assign
            if self.get_worker_id(ldplayer_id) is not None:
                continue
            
            # Tìm next available
            next_id = self.find_next_available_worker_id()
            self.assign_worker(ldplayer_id, next_id)
            assigned_map[ldplayer_id] = next_id
        
        return assigned_map
    
    def remove_worker(self, ldplayer_identifier: str) -> bool:
        """
        Xóa assignment cho 1 LDPlayer (không reset toàn bộ)
        Returns: True nếu đã xóa, False nếu không có assignment
        """
        str_id = str(ldplayer_identifier)
        
        worker_id = self.assignments.pop(str_id, None)
        if worker_id is None:
            return False
        
        if worker_id in self.reverse_map:
            del self.reverse_map[worker_id]
        
        log(f"[WorkerMgr] Removed assignment for {ldplayer_identifier} (was Worker {worker_id})")
        self.save()
        return True
    
    def remove_worker_by_id(self, worker_id: int) -> bool:
        """Xóa assignment bằng Worker ID"""
        ldplayer_id = self.reverse_map.get(worker_id)
        if ldplayer_id is None:
            return False
        
        return self.remove_worker(ldplayer_id)
    
    def reset_all(self):
        """Xóa tất cả assignments (cẩn thận!)"""
        self.assignments = {}
        self.reverse_map = {}
        self.save()
        log(f"[WorkerMgr] Reset all assignments")
    
    def get_summary(self) -> str:
        """Lấy summary assignment hiện tại"""
        if not self.assignments:
            return "No assignments"
        
        lines = []
        for ldplayer_id in sorted(self.assignments.keys()):
            worker_id = self.assignments[ldplayer_id]
            lines.append(f"  {ldplayer_id} → Worker {worker_id}")
        
        return "\n".join(lines)
    
    def cleanup_stale_assignments(self, current_hwnds: list[str]) -> int:
        """
        Xóa assignments cho các hwnd không còn tồn tại
        Returns: số lượng assignments đã xóa
        """
        current_set = set(str(h) for h in current_hwnds)
        stale_ids = []
        
        for ldplayer_id in list(self.assignments.keys()):
            if ldplayer_id not in current_set:
                stale_ids.append(ldplayer_id)
        
        removed = 0
        for stale_id in stale_ids:
            worker_id = self.assignments.pop(stale_id, None)
            if worker_id is not None:
                self.reverse_map.pop(worker_id, None)
                removed += 1
                log(f"[WorkerMgr] Cleaned up stale assignment: {stale_id} (was Worker {worker_id})")
        
        if removed > 0:
            self.save()
            log(f"[WorkerMgr] Removed {removed} stale assignments")
        
        return removed
