# Guitar Amp Recorder (macOS / Windows)

Bu uygulama şunları yapar:
- 1. kanal: Hazır müzik (arka plan)
- 2. kanal: Mikrofon kaydı
- Mikrofon kanalına amfi benzeri efektler (kazanç, güçlendirme, bas, tiz, distorsiyon)
- Gürültü azaltma (%), hızlandırma/yavaşlatma (%), çıkış kazancı (dB)
- Mikrofon ve ses kartı aygıt kimliği seçimi (giriş/çıkış, boş bırakılabilir)
- Kayıt sınırı seçimi (1 saat / 2 saat)
- Tek tık 5 sn cihaz/kayıt testi
- Sonucu otomatik MP3 olarak Masaüstüne çıkarır

## Hızlı Başlangıç (1 Dakika)

### Seçenek A: İndir ve Kullan (önerilen)

1. En güncel sürümü indir:
   - https://github.com/numantangones340-lgtm/congenial-fiesta/releases/latest
2. İşletim sistemine göre zip dosyasını aç:
   - macOS: `GuitarAmpRecorder-macOS.zip`
   - Windows: `GuitarAmpRecorder-Windows.zip`
3. Uygulamayı çalıştır:
   - macOS: `GuitarAmpRecorder.app`
   - Windows: `GuitarAmpRecorder.exe` (veya paket içindeki çalıştırıcı)

### Seçenek B: Kaynak Koddan Çalıştır

```bash
cd /Users/numantangones/Documents/GuitarAmpRecorder
./CALISTIR.command
```

## Dil Desteği

- Arayüz dili: Türkçe
- Terminal (CLI) metinleri: Türkçe
- GUI metinleri: Türkçe

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

## Kurulum (Windows)

1. Python 3.9+ kurulu olsun (önerilen: 3.10+).
2. `ffmpeg` kurun ve PATH'e ekleyin (MP3 için).
3. Proje klasöründe çalıştırın:
   ```bat
   cd C:\Users\%USERNAME%\Documents\GuitarAmpRecorder
   CALISTIR.bat
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

Windows için:

```bat
cd C:\Users\%USERNAME%\Documents\GuitarAmpRecorder
CALISTIR.bat
CALISTIR.bat gui
CALISTIR.bat cli
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
  - https://github.com/numantangones340-lgtm/congenial-fiesta/releases/latest
- GitHub Pages (indirme yonlendirme sayfasi):
  - https://numantangones340-lgtm.github.io/congenial-fiesta/

## Hızlı Sorun Giderme

- Uygulama açılmazsa:
  - macOS: Sistem Ayarları > Gizlilik ve Güvenlik > yine de aç.
  - Windows: SmartScreen uyarısında “More info > Run anyway”.
- MP3 oluşmuyorsa `ffmpeg` kurulu değildir; WAV dosyaları yine üretilir.
- Terminalde soru sorarken `git ...` komutlarını yapıştırmayın; önce `Ctrl + C` ile uygulamadan çıkın.

## Yayinlama (Diger Kullanicilar Icin)

Bu repoda otomatik yayin akisi eklidir:
- `.github/workflows/release-macos.yml`
  - `v*` etiketi push edilince macOS zip build eder ve Release'e koyar.
- `.github/workflows/release-windows.yml`
  - `v*` etiketi push edilince Windows zip build eder ve Release'e koyar.
- `.github/workflows/static.yml`
  - `main` branch push edilince `docs/` klasorunu GitHub Pages'e deploy eder.

Ornek release:

```bash
git tag v1.0.0
git push origin v1.0.0
```

## Kullanım

1. Mikrofon/Çıkış Aygıt Kimliği kutularını boş bırakabilirsiniz (varsayılan cihaz).
2. `Müzik Dosyası Seç` ile backing track seçin (`.wav/.aiff/.aif/.flac`).
3. İsterseniz `Çıkış Dosya Adı (MP3)` alanını düzenleyin.
4. `Kazanç / Güçlendirme / Bas / Tiz / Distorsiyon` ayarlarını yapın.
5. `Arka Plan Seviye / Vokal Seviye / Gürültü Azaltma / Hız / Çıkış Kazancı` ayarlarını yapın.
6. `Kayıt Sınırı (1 veya 2 saat)` seçin.
7. İsterseniz `Mikrofon/Ses Kartı Testi (5 sn)` ile önce test yapın.
8. İsterseniz tek adım akışı için `Hızlı Kayıt (Test + Kayıt)` butonuna basın.
9. Manuel akış için `Kaydı Başlat ve MP3 Çıkar` butonuna basın.
10. `Hazır Profil` menüsünden `Clean / Crunch / Lead` seçip `Profili Uygula` ile tek tık ayar yapabilirsiniz.
11. `Dosya Adını Otomatik Oluştur` butonu dosya adını profil + zaman damgasıyla üretir.
12. Kayıt bitince dosyalar Masaüstüne yazılır:
   - `dosyaadi.mp3` (mix, mümkünse otomatik)
   - `dosyaadi_mix.wav` (garanti mix WAV)
   - `dosyaadi_vocal.wav` (işlenmiş vokal/gitar kanalınız)
   - `dosyaadi_device_test.wav` (test kaydı)

## Hızlı Kullanım Kartı

1. `Müzik Dosyası Seç`
2. `Hazır Profil` seç (`Clean`, `Crunch`, `Lead`) + `Profili Uygula`
3. `Dosya Adını Otomatik Oluştur`
4. `Hızlı Kayıt (Test + Kayıt)`
5. Çıktıları Masaüstünde kontrol et:
   - `guitar_mix_YYYYMMDD_HHMMSS_profil.mp3`
   - `guitar_mix_YYYYMMDD_HHMMSS_profil_mix.wav`
   - `guitar_mix_YYYYMMDD_HHMMSS_profil_vocal.wav`
   - `guitar_mix_YYYYMMDD_HHMMSS_profil_device_test.wav`

## Notlar

- Kayıt sırasında kulaklık kullanmanız geri besleme (feedback) riskini azaltır.
- `ffmpeg bulunamadı` hatası alırsanız `brew install ffmpeg` komutunu tekrar çalıştırın.
- Windows'ta da çalışır; `ffmpeg` ve Python kurulumu gerekir.
- Önemli: Program soru sorarken terminale `git ...` gibi komutlar yapıştırmayın. Önce `Ctrl + C` ile programdan çıkın, sonra komutları çalıştırın.
