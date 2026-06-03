@echo off
REM ============================================================
REM redtech.bat - Wrapper do pipeline RedTech (Windows)
REM ============================================================
REM Equivalente ao alias "redtech" do Mac.
REM
REM Uso:
REM   redtech.bat "C:\Users\Joao\Downloads\Teste 1" --batch
REM   redtech.bat "C:\Users\Joao\Downloads\Teste 1\voo_20260527_142555"
REM   redtech.bat --help
REM ============================================================

set SCRIPTS_DIR=%USERPROFILE%\Downloads\LIDAR_tests
set OUTPUT_DIR=%USERPROFILE%\Downloads\LIDAR_tests\sessoes

python "%SCRIPTS_DIR%\redtech_pipeline.py" --scripts "%SCRIPTS_DIR%" --output "%OUTPUT_DIR%" %*
