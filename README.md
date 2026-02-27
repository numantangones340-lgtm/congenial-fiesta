# Guitar Amp Recorder (macOS / Windows)

Mikrofon girişine amfi benzeri efektler uygulayıp, arka plan müzikle birlikte kayıt almanızı sağlayan masaüstü uygulama.

## Özellikler

- Hazır müzik (backing track) + mikrofon kaydı
- Gain / Boost / Bass / Treble / Distortion ayarları
- Giriş/çıkış cihazı seçimi (boş bırakılabilir)
- Uzun test kaydı (ör. 5 saat)
- Çıktıları otomatik masaüstüne kaydetme

## Gereksinimler

- Python 3.10+
- `ffmpeg`

### macOS (Homebrew)

```bash
brew install ffmpeg
cd /Users/numantangones/Documents/GuitarAmpRecorder
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cd /Users/numantangones/Documents/GuitarAmpRecorder
source .venv/bin/activate
python app.py
# Guitar Amp Recorder (macOS / Windows)

Mikrofon girişine amfi benzeri efektler uygulayıp backing track ile birlikte kayıt almanızı sağlayan uygulama.

## Özellikler

- Backing track + mikrofon kaydı
- Gain / Boost / Bass / Treble / Distortion ayarları
- Giriş/çıkış cihazı seçimi
- Uzun test kaydı (ör. 5 saat)
- Çıktıları otomatik masaüstüne kaydetme

## Gereksinimler

- Python 3.10+
- ffmpeg

## Kurulum (macOS önerilen)

```bash
brew install ffmpeg
cd /Users/numantangones/Documents/GuitarAmpRecorder
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cd /Users/numantangones/Documents/GuitarAmpRecorder
source .venv/bin/activate
python app.py
## İndir

En güncel sürümü buradan indir:

- [Latest Release](https://github.com/numantangones340-lgtm/congenial-fiesta/releases/latest)

### Hızlı İndirme

- **Windows (.exe):** Releases sayfasındaki `GuitarAmpRecorder-Windows.exe`
- **macOS (.dmg / .zip):** Releases sayfasındaki `GuitarAmpRecorder-macOS.dmg` veya `.zip`

### Kurulum

1. Yukarıdaki `Latest Release` linkine gir.
2. `Assets` bölümünden işletim sistemine uygun dosyayı indir.
3. Uygulamayı aç.

> Not: İlk açılışta güvenlik uyarısı çıkarsa, işletim sistemi ayarlarından uygulamaya izin ver.
pip install pyinstaller
pyinstaller --onefile --windowed --name GuitarAmpRecorder app.py
pip install pyinstaller
pip install pyinstaller
pyinstaller --windowed --name GuitarAmpRecorder app.py
cd dist
zip -r GuitarAmpRecorder-macOS.zip GuitarAmpRecorder.app
## Guitar Amp Recorder v1.0.0

### Yenilikler
- Backing track + mikrofon kayıt desteği
- Gain / Boost / Bass / Treble / Distortion ayarları
- Cihaz giriş/çıkış seçimi
- Otomatik çıktı alma (mix + vocal + test)

### İndir
- Windows: `GuitarAmpRecorder-Windows.exe`
- macOS: `GuitarAmpRecorder-macOS.zip`

### Notlar
- İlk açılışta işletim sistemi güvenlik uyarısı gösterebilir.
- Sorun yaşarsanız Issue açabilirsiniz.
- [Latest Release](https://github.com/numantangones340-lgtm/congenial-fiesta/releases/latest)
#!/usr/bin/env bash
set -euo pipefail

APP_NAME="GuitarAmpRecorder"
ENTRY="app.py"

echo "==> Venv kontrol"
if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi
source .venv/bin/activate

echo "==> Bağımlılıklar"
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller

echo "==> Eski build temizliği"
rm -rf build dist "${APP_NAME}.spec"

echo "==> Build alınıyor"
pyinstaller --windowed --name "${APP_NAME}" "${ENTRY}"

echo "==> macOS zip hazırlanıyor"
cd dist
zip -r "${APP_NAME}-macOS.zip" "${APP_NAME}.app" >/dev/null
cd ..

echo "==> Tamam"
echo "Uygulama: dist/${APP_NAME}.app"
echo "Arsiv   : dist/${APP_NAME}-macOS.zip"
chmod +x build.sh
./build.sh
@echo off
setlocal enabledelayedexpansion

set APP_NAME=GuitarAmpRecorder
set ENTRY=app.py

echo ==> Python kontrol
where py >nul 2>&1
if errorlevel 1 (
  echo Python bulunamadi. Lutfen Python 3.10+ kurun.
  exit /b 1
)

echo ==> Venv kontrol
if not exist .venv (
  py -3 -m venv .venv
)

call .venv\Scripts\activate.bat
if errorlevel 1 (
  echo Venv aktive edilemedi.
  exit /b 1
)

echo ==> Bagimliliklar
python -m pip install --upgrade pip
if errorlevel 1 exit /b 1

pip install -r requirements.txt
if errorlevel 1 exit /b 1

pip install pyinstaller
if errorlevel 1 exit /b 1

echo ==> Eski build temizligi
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist %APP_NAME%.spec del /f /q %APP_NAME%.spec

echo ==> EXE build
pyinstaller --onefile --windowed --name %APP_NAME% %ENTRY%
if errorlevel 1 exit /b 1

echo ==> Dosya adi duzenleme
if exist dist\%APP_NAME%.exe (
  copy /y dist\%APP_NAME%.exe dist\%APP_NAME%-Windows.exe >nul
)

echo.
echo ==> Tamam
echo Cikti: dist\%APP_NAME%.exe
echo Release icin: dist\%APP_NAME%-Windows.exe
exit /b 0
## Build (macOS / Windows)

Uygulamayı tek komutla paketlemek için hazır scriptler kullanabilirsiniz.

### macOS

```bash
chmod +x build.sh
./build.sh
build.bat
