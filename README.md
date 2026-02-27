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
