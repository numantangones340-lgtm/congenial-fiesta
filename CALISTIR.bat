@echo off
setlocal enableextensions enabledelayedexpansion

cd /d "%~dp0"
echo Guitar Amp Recorder baslatiliyor...

set "PYTHON_BIN="
if exist ".venv\Scripts\python.exe" set "PYTHON_BIN=.venv\Scripts\python.exe"

if not defined PYTHON_BIN (
  where py >nul 2>nul
  if %ERRORLEVEL%==0 (
    set "PYTHON_BIN=py -3"
  ) else (
    where python >nul 2>nul
    if %ERRORLEVEL%==0 (
      set "PYTHON_BIN=python"
    )
  )
)

if not defined PYTHON_BIN (
  echo HATA: Python bulunamadi. Lutfen Python 3.9+ kurun.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo Sanal ortam olusturuluyor...
  %PYTHON_BIN% -m venv .venv
  if errorlevel 1 (
    echo HATA: Sanal ortam olusturulamadi.
    pause
    exit /b 1
  )
  set "PYTHON_BIN=.venv\Scripts\python.exe"
) else (
  set "PYTHON_BIN=.venv\Scripts\python.exe"
)

%PYTHON_BIN% -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)"
if errorlevel 1 (
  echo HATA: Python 3.9+ gerekir.
  pause
  exit /b 1
)

set "PIP_NO_CACHE_DIR=1"
set "PIP_DISABLE_PIP_VERSION_CHECK=1"
echo Gerekli kutuphaneler yukleniyor...
%PYTHON_BIN% -m pip install -r requirements.txt
if errorlevel 1 (
  echo HATA: Kutuphane kurulumu basarisiz.
  pause
  exit /b 1
)

where ffmpeg >nul 2>nul
if errorlevel 1 (
  echo UYARI: ffmpeg bulunamadi. MP3 olusturma atlanir, WAV dosyalari yine kaydedilir.
)

set "MODE=%~1"
if /I "%MODE%"=="cli" goto run_cli
if /I "%MODE%"=="gui" goto run_gui

:run_auto
echo Pencere surumu aciliyor...
%PYTHON_BIN% app.py
if errorlevel 1 (
  echo GUI acilamadi. CLI surumune geciliyor...
  %PYTHON_BIN% cli_app.py
)
goto done

:run_gui
echo Pencere surumu aciliyor...
%PYTHON_BIN% app.py
goto done

:run_cli
echo Terminal surumu aciliyor...
%PYTHON_BIN% cli_app.py

:done
exit /b 0
