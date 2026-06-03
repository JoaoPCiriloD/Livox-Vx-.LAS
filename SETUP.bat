@echo off
REM ============================================================
REM SETUP.bat - Configuracao inicial RedTech LiDAR (Windows)
REM ============================================================
REM Roda uma vez para preparar o ambiente.
REM Instala bibliotecas Python e cria estrutura de pastas.
REM ============================================================

echo ============================================================
echo   REDTECH LIDAR - SETUP WINDOWS
echo ============================================================
echo.

REM --- 1. Verificar Python ---
echo [1/4] Verificando Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo   ERRO: Python nao encontrado.
    echo.
    echo   Instale Python 3 primeiro:
    echo   1. Baixe em https://www.python.org/downloads/
    echo   2. IMPORTANTE: marque "Add Python to PATH" durante a instalacao
    echo   3. Rode este SETUP.bat de novo
    echo.
    pause
    exit /b 1
)
python --version
echo   Python OK.
echo.

REM --- 2. Instalar bibliotecas ---
echo [2/4] Instalando bibliotecas Python...
echo   (pode demorar alguns minutos na primeira vez)
python -m pip install --upgrade pip
python -m pip install laspy numpy pyubx2 pyproj
if %errorlevel% neq 0 (
    echo.
    echo   ERRO ao instalar bibliotecas.
    echo   Tente manualmente: python -m pip install laspy numpy pyubx2 pyproj
    echo.
    pause
    exit /b 1
)
echo   Bibliotecas OK.
echo.

REM --- 3. Validar imports ---
echo [3/4] Validando bibliotecas...
python -c "import laspy, numpy, pyubx2, pyproj; print('   Todas as bibliotecas importam OK')"
if %errorlevel% neq 0 (
    echo   ERRO: bibliotecas instaladas mas nao importam.
    pause
    exit /b 1
)
echo.

REM --- 4. Criar estrutura de pastas ---
echo [4/4] Criando estrutura de pastas...
set REDTECH_DIR=%USERPROFILE%\Downloads\LIDAR_tests
if not exist "%REDTECH_DIR%\sessoes" (
    mkdir "%REDTECH_DIR%\sessoes"
    echo   Criada: %REDTECH_DIR%\sessoes
) else (
    echo   Ja existe: %REDTECH_DIR%\sessoes
)
echo.

echo ============================================================
echo   SETUP COMPLETO
echo ============================================================
echo.
echo Proximos passos:
echo   1. Copie os 5 scripts .py para:
echo      %REDTECH_DIR%
echo.
echo   2. Copie os arquivos .bat (redtech.bat, redtech-compare.bat) para:
echo      %REDTECH_DIR%
echo.
echo   3. Instale o CloudCompare:
echo      https://www.danielgm.net/cc/release/
echo.
echo   4. Teste rodando:
echo      redtech.bat --help
echo.
echo Para nao precisar digitar o caminho completo, veja o
echo arquivo ADICIONAR_AO_PATH.txt
echo.
pause
