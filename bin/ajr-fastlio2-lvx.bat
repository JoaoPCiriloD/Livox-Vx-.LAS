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

  for /f "delims=" %%I in ('wsl wslpath -a "%~dp0.."') do set "REPO_WSL=%%I"
  for /f "delims=" %%I in ('wsl wslpath -a "%~1"') do set "LVX_WSL=%%I"

  if "%~2"=="" (
    wsl bash -lc "cd '!REPO_WSL!' && bash bin/ajr-fastlio2-lvx.sh '!LVX_WSL!'"
  ) else (
    for /f "delims=" %%I in ('wsl wslpath -a "%~2"') do set "OUT_WSL=%%I"
    wsl bash -lc "cd '!REPO_WSL!' && bash bin/ajr-fastlio2-lvx.sh '!LVX_WSL!' '!OUT_WSL!'"
  )

  exit /b %errorlevel%

  :help
  echo Uso:
  echo   bin\ajr-fastlio2-lvx.bat "C:\caminho\arquivo.lvx" [OUT_DIR]
  exit /b 0
