from pathlib import Path

APP_NAME = "AJR Desktop"

APP_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = APP_DIR.parent

SCRIPTS_DIR = PROJECT_ROOT / "scripts"
SESSIONS_DIR = PROJECT_ROOT / "sessoes"
FASTLIO_OUTPUT_DIR = PROJECT_ROOT / "fastlio2_output"
ASSETS_DIR = APP_DIR / "assets"
LOGO_PATH = ASSETS_DIR / "Logo_AJRD_512.png"