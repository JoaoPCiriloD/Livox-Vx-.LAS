@echo off
REM ============================================================
REM redtech-compare.bat - Wrapper do comparador RedTech (Windows)
REM ============================================================
REM Equivalente ao alias "redtech-compare" do Mac.
REM
REM Uso:
REM   redtech-compare.bat --all
REM   redtech-compare.bat voo_20260527_142555 voo_20260527_142428
REM   redtech-compare.bat --all --output "%USERPROFILE%\Downloads\comparacao.md"
REM ============================================================

set SCRIPTS_DIR=%USERPROFILE%\Downloads\LIDAR_tests
set OUTPUT_DIR=%USERPROFILE%\Downloads\LIDAR_tests\sessoes

python "%SCRIPTS_DIR%\redtech_compare.py" --sessoes "%OUTPUT_DIR%" %*
