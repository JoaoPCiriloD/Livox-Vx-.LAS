@echo off
setlocal EnableDelayedExpansion

if "%~1"=="" goto :help
if "%~1"=="-h" goto :help
if "%~1"=="--help" goto :help

where wsl >nul 2>nul
if errorlevel 1 (
  echo ERRO: WSL2 nao encontrado.
  exit /b 1
)

wsl --exec /bin/bash -lc "exit 0" >nul 2>nul
if errorlevel 1 (
  echo ERRO: a distribuicao WSL padrao nao possui /bin/bash.
  echo.
  echo Distribuicoes instaladas:
  wsl --list --verbose
  echo.
  echo Defina uma distribuicao Linux, como Ubuntu, como padrao:
  echo   wsl --set-default Ubuntu
  echo.
  echo Se o Ubuntu nao estiver instalado:
  echo   wsl --install -d Ubuntu
  exit /b 127
)

for /f "delims=" %%I in ('wsl wslpath -a "%~dp0.."') do set "REPO_WSL=%%I"
for /f "delims=" %%I in ('wsl wslpath -a "%~1"') do set "LVX_WSL=%%I"

if not defined REPO_WSL (
  echo ERRO: nao foi possivel converter o caminho do projeto para WSL.
  exit /b 1
)

if not defined LVX_WSL (
  echo ERRO: nao foi possivel converter o caminho do arquivo LVX para WSL.
  exit /b 1
)

if "%~2"=="" (
  wsl --exec /bin/bash -lc "cd '!REPO_WSL!' && /bin/bash bin/ajr-fastlio2-lvx.sh '!LVX_WSL!'"
) else (
  for /f "delims=" %%I in ('wsl wslpath -a "%~2"') do set "OUT_WSL=%%I"
  if not defined OUT_WSL (
    echo ERRO: nao foi possivel converter o caminho de saida para WSL.
    exit /b 1
  )
  wsl --exec /bin/bash -lc "cd '!REPO_WSL!' && /bin/bash bin/ajr-fastlio2-lvx.sh '!LVX_WSL!' '!OUT_WSL!'"
)

exit /b %errorlevel%

:help
echo Uso:
echo   bin\ajr-fastlio2-lvx.bat "C:\caminho\arquivo.lvx" [OUT_DIR]
exit /b 0
