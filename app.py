# from utils.logger import setup_logger
# from core.window_scanner import WindowScanner

# def main():
#     logger = setup_logger()
#     logger.info("=== AUTO TOOL STARTED ===")

#     scanner = WindowScanner(logger)
#     windows = scanner.scan()

#     logger.info("=== DISCOVERY RESULT ===")
#     for idx, w in enumerate(windows, start=1):
#         logger.info(f"{idx}. {w.title} | {w.status} | rect={w.rect}")

#     logger.info("=== AUTO TOOL FINISHED ===")

# if __name__ == "__main__":
#     main()

from ui.main_ui import MainUI

def initialize_workers_fast():
    """No auto-scan - return empty list. User must use Set Worker dialog."""
    print("[APP] Starting in standalone mode")
    print("[APP] Use 'Set Worker' button to assign LDPlayer instances")
    return []

# No auto-scan - workers start empty
workers = initialize_workers_fast()

ui = MainUI(workers)
ui.root.mainloop()
