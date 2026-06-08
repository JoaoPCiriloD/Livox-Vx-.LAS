@echo off
REM ============================================================
REM ajr.bat - Wrapper do pipeline AJR (Windows)
REM ============================================================
REM Equivalente ao alias "ajr" do Mac.
REM
REM Uso:
REM   ajr.bat "C:\Users\Joao\Downloads\Teste 1" --batch
REM   ajr.bat "C:\Users\Joao\Downloads\Teste 1\voo_20260527_142555"
REM   ajr.bat --help
REM ============================================================

set ROOT_DIR=%~dp0
set SCRIPTS_DIR=%ROOT_DIR%scripts
set OUTPUT_DIR=%ROOT_DIR%sessoes

python "%SCRIPTS_DIR%\pipeline\ajr_pipeline.py" --scripts "%SCRIPTS_DIR%" --output "%OUTPUT_DIR%" %*
