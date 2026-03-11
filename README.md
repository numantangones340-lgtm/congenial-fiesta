# Guitar Amp Recorder (macOS / Windows)

Bu uygulama şunları yapar:
- 1. kanal: Hazır müzik (backing track)
- 2. kanal: Mikrofon kaydı
- Mikrofon kanalına amfi benzeri efektler (gain, boost, bass, treble, distortion)
- Mikrofon ve ses kartı cihaz ID seçimi (input/output, bos birakilabilir)
- Tek tık 5 sn cihaz/kayıt testi
- Sonucu otomatik MP3 olarak Masaüstüne çıkarır

## Kurulum (macOS önerilen)

1. Python 3.9+ kurulu olsun (onerilen: 3.10+).
2. `ffmpeg` kurun:
   - macOS (Homebrew):
     ```bash
     brew install ffmpeg
     ```
3. Proje klasöründe sanal ortam kurup paketleri yükleyin:
   ```bash
   cd /Users/numantangones/Documents/GuitarAmpRecorder
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

## macOS `.app` paketleme (önerilen)

`Tk/Tcl` kaynakları eksik paketlenirse uygulama açılırken `EXC_CRASH (SIGABRT)` verebilir.
Bu repo içindeki build akışı bu kaynakları `.app` içine ekler.

```bash
cd /Users/numantangones/Documents/GuitarAmpRecorder
source .venv/bin/activate
pip install pyinstaller
./build_macos_app.sh
```

Üretilen uygulama:

- `dist/GuitarAmpRecorder.app`

## Codesign + Notarization

Yerel test için ad-hoc imza:

```bash
./sign_macos_app.sh
```

Developer ID ile imzalama:

```bash
./sign_macos_app.sh ./dist/GuitarAmpRecorder.app "Developer ID Application: YOUR NAME (TEAMID)"
```

Notarization (Xcode notarytool ile):

1. Bir kez keychain profile oluşturun:
   ```bash
   xcrun notarytool store-credentials "AC_PROFILE" \
     --apple-id "you@example.com" \
     --team-id "TEAMID1234" \
     --password "app-specific-password"
   ```
2. Sonra notarize edin:
   ```bash
   ./notarize_macos_app.sh ./dist/GuitarAmpRecorder.app AC_PROFILE TEAMID1234
   ```

## Çalıştırma

```bash
cd /Users/numantangones/Documents/GuitarAmpRecorder
./CALISTIR.command
```

`CALISTIR.command` otomatik olarak GUI sürümünü açar; GUI açılamazsa CLI sürüme geçer.

Manuel mod seçimi:

```bash
./CALISTIR.command gui
./CALISTIR.command cli
```

## Masaustu Tek Tik Baslatici

```bash
cd /Users/numantangones/Documents/GuitarAmpRecorder
./install_desktop_shortcut.sh
```

Bu komut `~/Desktop/GuitarAmpRecorder.command` dosyasi olusturur.

## Masaustune macOS Kurulum Paketi Alma

```bash
cd /Users/numantangones/Documents/GuitarAmpRecorder
./package_macos_release.sh
```

Bu komut:
- `dist/GuitarAmpRecorder-macOS.zip` olusturur
- ayni zip dosyasini `~/Desktop/GuitarAmpRecorder-macOS.zip` olarak kopyalar

## Guvenilir Indirme Sayfalari

- GitHub Releases (resmi surum dosyalari):
  - https://github.com/numantangones340-lgtm/gitar-amp-kaydedici/releases/latest
- GitHub Pages (indirme yonlendirme sayfasi):
  - https://numantangones340-lgtm.github.io/gitar-amp-kaydedici/

## Yayinlama (Diger Kullanicilar Icin)

Bu repoda otomatik yayin akisi eklidir:
- `.github/workflows/release-macos.yml`
  - `v*` etiketi push edilince macOS zip build eder ve Release'e koyar.
- `.github/workflows/static.yml`
  - `main` branch push edilince `docs/` klasorunu GitHub Pages'e deploy eder.

Ornek release:

```bash
git tag v1.0.0
git push origin v1.0.0
```

## Kullanım

1. Mikrofon/Cikis Device ID kutularini bos birakabilirsiniz (varsayilan cihaz).
2. `Mikrofon/Ses Kartı Testi (5 sn)` butonuyla önce test yapın.
3. `Müzik Dosyası Seç` ile backing track seçin (`.wav/.aiff/.flac`).
4. Gain/Boost/Bass/Treble/Distortion ayarlarını yapın.
5. `Kaydı Başlat ve MP3 Çıkar` butonuna basın.
6. Kayıt bitince dosyalar Masaüstüne yazılır:
   - `dosyaadi.mp3` (mix)
   - `dosyaadi_vocal.wav` (işlenmiş vokal/gitar kanalınız)
   - `dosyaadi_device_test.wav` (test kaydı)

## Notlar

- Kayıt sırasında kulaklık kullanmanız geri besleme (feedback) riskini azaltır.
- `ffmpeg bulunamadı` hatası alırsanız `brew install ffmpeg` komutunu tekrar çalıştırın.
- Windows'ta da çalışır; `ffmpeg` ve Python kurulumu gerekir.
