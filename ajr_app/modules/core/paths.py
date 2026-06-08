from ajr_desktop.settings import (
    SCRIPTS_DIR,
    SESSIONS_DIR,
    FASTLIO_OUTPUT_DIR,
)

def ensure_directories():
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    FASTLIO_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    