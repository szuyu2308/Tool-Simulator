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
from initialize_workers import initialize_workers_from_ldplayer

# Auto-detect and initialize workers from LDPlayer instances
workers = initialize_workers_from_ldplayer()

ui = MainUI(workers)
ui.root.mainloop()
