@echo off
REM ============================================================
REM ajr-compare.bat - Wrapper do comparador AJR (Windows)
REM ============================================================
REM Equivalente ao alias "ajr-compare" do Mac.
REM
REM Uso:
REM   ajr-compare.bat --all
REM   ajr-compare.bat voo_20260527_142555 voo_20260527_142428
REM   ajr-compare.bat --all --output "%USERPROFILE%\Downloads\comparacao.md"
REM ============================================================

set ROOT_DIR=%~dp0
set SCRIPTS_DIR=%ROOT_DIR%scripts
set OUTPUT_DIR=%ROOT_DIR%sessoes

python "%SCRIPTS_DIR%\pipeline\ajr_compare.py" --sessoes "%OUTPUT_DIR%" %*
