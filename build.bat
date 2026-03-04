@echo off
setlocal enabledelayedexpansion

set APP_NAME=GuitarAmpRecorder
set ENTRY=app.py

where py >nul 2>&1
if errorlevel 1 (
  echo Python bulunamadi. Lutfen Python 3.10+ kurun.
  exit /b 1
)

if not exist .venv (
  py -3 -m venv .venv
)

call .venv\Scripts\activate.bat
if errorlevel 1 exit /b 1

python -m pip install --upgrade pip
if errorlevel 1 exit /b 1

pip install -r requirements.txt
if errorlevel 1 exit /b 1

pip install pyinstaller
if errorlevel 1 exit /b 1

if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist %APP_NAME%.spec del /f /q %APP_NAME%.spec

pyinstaller --onefile --windowed --name %APP_NAME% %ENTRY%
if errorlevel 1 exit /b 1

echo Build tamam: dist\%APP_NAME%.exe
exit /b 0
