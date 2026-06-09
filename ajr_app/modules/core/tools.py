import sys

from ajr_desktop.settings import FASTLIO_OUTPUT_DIR, PROJECT_ROOT, SCRIPTS_DIR, SESSIONS_DIR

def pipeline_command(folder, batch=False, skip_cloudcompare=True):
    command = [
        sys.executable,
        str(SCRIPTS_DIR / "pipeline" / "ajr_pipeline.py"),
        "--scripts",
        str(SCRIPTS_DIR),
        "--output",
        str(SESSIONS_DIR),
    ]

    if batch:
        command.append("--batch")

    if skip_cloudcompare:
        command.append("--skip-cloudcompare")

    command.append(folder)
    return command


def fastlio2_command(lvx_file, output_dir):
    if sys.platform == "win32":
        return [
            "cmd.exe",
            "/d",
            "/c",
            str(PROJECT_ROOT / "bin" / "ajr-fastlio2-lvx.bat"),
            str(lvx_file),
            str(output_dir),
        ]

    return [
        "bash",
        str(PROJECT_ROOT / "bin" / "ajr-fastlio2-lvx.sh"),
        str(lvx_file),
        str(output_dir),
    ]


def fastlio2_output_dir(session_name):
    return FASTLIO_OUTPUT_DIR / session_name
