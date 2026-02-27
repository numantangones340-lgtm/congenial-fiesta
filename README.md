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
