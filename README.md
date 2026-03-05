# Guitar Amp Recorder

Gitar/vokal girisini amfi benzeri efektlerle isleyip kaydetmek icin masaustu (Tkinter) ve terminal (CLI) uygulamasi.

## Indirme

- Download sayfasi (GitHub Pages):
  - https://numantangones340-lgtm.github.io/congenial-fiesta/
- En guncel paketler (GitHub Releases):
  - https://github.com/numantangones340-lgtm/congenial-fiesta/releases/latest

MacOS kullanicilari release icinden `GuitarAmpRecorder-macOS.zip` dosyasini indirebilir.

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

- Python 3.9+ (onerilen 3.10+)
- `ffmpeg` (MP3 icin, opsiyonel)

## Hizli Calistirma (macOS)

```bash
cd /Users/numantangones/Documents/congenial-fiesta
./CALISTIR.command
```

`CALISTIR.command` otomatik modda calisir:

- GUI uygunsa `app.py` acilir
- GUI uyumsuzsa otomatik `cli_app.py` acilir

Manuel mod secimi:

```bash
cd /Users/numantangones/Documents/congenial-fiesta
./CALISTIR.command gui
./CALISTIR.command cli
```

Masaustune tek tik kisayol kurmak icin:

```bash
cd /Users/numantangones/Documents/congenial-fiesta
./install_desktop_shortcut.sh
```

Bu adim `~/Desktop/GuitarAmpRecorder.command` dosyasini olusturur.

## Build ve Release

Lokal macOS paketleme:

```bash
./build.sh
```

Bu komut `dist/GuitarAmpRecorder-macOS.zip` olusturur.

Otomatik release (tag ile):

```bash
git tag v1.0.0
git push origin v1.0.0
```

`.github/workflows/release-macos.yml` tag gelince zip paketi release asset olarak yukler.

Download sayfasi yayinlama:

- `push` oldugunda `.github/workflows/static.yml` otomatik olarak `docs/` klasorunu GitHub Pages'e deploy eder.
- Gerekirse Actions ekranindan `Deploy Download Page` workflow'unu manuel tetikleyebilirsiniz.

## Cikti Konumu

Tum kayitlar `~/Desktop` altina yazilir.

## Sorun Giderme

- `Invalid sample rate` veya cihaz hatasi: Cihaz ID alanlarini bos birakin veya cihaz listesinden dogru ID secin.
- `ffmpeg bulunamadi`: MP3 olusmaz, WAV dosyalari normal olusur.
- Geri besleme/eko: Kulaklik kullanin.
