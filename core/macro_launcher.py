import subprocess
import threading
import time
import os
import signal

from core.tech import win32gui
from utils.logger import log


class MacroLauncher:
    def __init__(self, macro_exe_path: str):
        self.macro_exe_path = macro_exe_path
        self.process_map = {}   # worker_id -> Popen
        self.running = False    # LOCK START

    def _focus_window(self, hwnd):
        try:
            win32gui.ShowWindow(hwnd, 5)
            win32gui.SetForegroundWindow(hwnd)
            time.sleep(0.15)
            return True
        except Exception as e:
            log(f"[MACRO] Focus fail hwnd {hwnd}: {e}")
            return False

    def _spawn_macro(self, worker, macro_file: str):
        wid = worker.id

        if wid in self.process_map:
            log(f"[MACRO] Worker {wid} đã có macro → skip")
            return

        if not worker.is_ready():
            log(f"[MACRO] Worker {wid} NOT READY → skip")
            return

        if not self._focus_window(worker.hwnd):
            log(f"[MACRO] Worker {wid} focus fail")
            return

        try:
            proc = subprocess.Popen(
                [self.macro_exe_path, macro_file],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            self.process_map[wid] = proc
            log(f"[MACRO] Spawn macro worker {wid} | PID={proc.pid}")
        except Exception as e:
            log(f"[MACRO] Spawn fail worker {wid}: {e}")

    def run_parallel(self, workers: list, macro_file: str):
        if self.running:
            log("[MACRO] Đang chạy macro → không cho Start lại")
            return

        self.running = True
        log(f"[MACRO] START macro song song | file={macro_file}")

        for worker in workers:
            t = threading.Thread(
                target=self._spawn_macro,
                args=(worker, macro_file),
                daemon=True
            )
            t.start()
            time.sleep(0.05)

    def get_running_workers(self):
        """
        Trả về set worker_id đang chạy macro
        """
        return set(self.process_map.keys())

    # ================= STOP =================

    def stop_worker(self, worker_id: int):
        proc = self.process_map.get(worker_id)
        if not proc:
            return

        try:
            proc.terminate()
            proc.wait(timeout=2)
        except Exception:
            try:
                os.kill(proc.pid, signal.SIGKILL)
            except Exception:
                pass

        log(f"[MACRO] Stop macro worker {worker_id}")
        self.process_map.pop(worker_id, None)

    def stop_all(self):
        log("[MACRO] STOP ALL")
        for wid in list(self.process_map.keys()):
            self.stop_worker(wid)

        self.running = False
