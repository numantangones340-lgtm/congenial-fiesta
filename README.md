# Guitar Amp Recorder

Gitar/vokal girisini amfi benzeri efektlerle isleyip kaydetmek icin masaustu (Tkinter) ve terminal (CLI) uygulamasi.

## Ozellikler

- Backing track ile kayit (`playrec`) veya backing olmadan `mic-only` kayit
- Gain / Boost / Bass / Treble / Distortion ayarlari
- Backing ve vokal seviye ayri kontrolu
- Cihaz listeleme ve input/output cihaz ID secimi
- 5 saniyelik cihaz testi
- Cikti dosyalari:
  - `*_mix.wav`
  - `*_vocal.wav`
  - `*.mp3` (ffmpeg varsa)

## Gereksinimler

- Python 3.10+
- `ffmpeg` (MP3 icin, opsiyonel)

## Hizli Calistirma (macOS)

```bash
cd /Users/numantangones/Documents/congenial-fiesta
./CALISTIR.command
```

CLI surumu:

```bash
cd /Users/numantangones/Documents/congenial-fiesta
./CALISTIR.command cli
```

## Manuel Kurulum

```bash
cd /Users/numantangones/Documents/congenial-fiesta
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

## Cikti Konumu

Tum kayitlar `~/Desktop` altina yazilir.

## Sorun Giderme

- `Invalid sample rate` veya cihaz hatasi: Cihaz ID alanlarini bos birakin veya cihaz listesinden dogru ID secin.
- `ffmpeg bulunamadi`: MP3 olusmaz, WAV dosyalari normal olusur.
- Geri besleme/eko: Kulaklik kullanin.
