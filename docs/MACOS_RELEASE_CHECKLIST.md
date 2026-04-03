# macOS Release Checklist

Bu kontrol listesi, uygulamayi baska kullanicilara dagitmadan once macOS yayin akisinin eksiksiz oldugunu dogrulamak icin kullanilir.

## Yerel Hazirlik

1. `VERSION` ve `CHANGELOG.md` ayni surumu gostermeli.
2. Testler temiz gecmeli:
   `python -m unittest discover -s tests -p "test_*.py"`
3. Build script'leri syntax olarak dogrulanmali:
   - `bash -n build_macos_app.sh`
   - `bash -n sign_macos_app.sh`
   - `bash -n notarize_macos_app.sh`
   - `bash -n package_macos_release.sh`
   - `bash -n release_macos_desktop.sh`

## Build ve Paketleme

1. Uygulamayi paketle:
   `./build_macos_app.sh`
2. Gerekirse yerel ad-hoc imza uygula:
   `./sign_macos_app.sh`
3. Dagitim zip'ini uret:
   `./package_macos_release.sh`
4. Tek komutta tum akis:
   `./release_macos_desktop.sh`

## Gercek Dagitim

1. Apple Developer ID sertifikasi hazir olmali.
2. `notarytool` credentials saklanmis olmali.
3. Imzali ve notarized build icin:
   `./release_macos_desktop.sh "Developer ID Application: YOUR NAME (TEAMID)" AC_PROFILE TEAMID`
4. Son zip dosyasi:
   - `dist/GuitarAmpRecorder-macOS.zip`
   - `~/Desktop/GuitarAmpRecorder-macOS.zip`

## Yayin Sonrasi Kontrol

1. GitHub Release asset yuklendi mi?
2. GitHub Pages indirme sayfasi dogru linke yonleniyor mu?
3. Temiz bir macOS kullanici hesabinda zip acilip `.app` sorunsuz aciliyor mu?
4. Ilk acilista mikrofon izni, cikis secimi ve masaustu export akisi dogru mu?
5. `Mikrofon/Ses Karti Testi (5 sn)` sonrasi `Peak=0.000` degil mi?
6. `Quick Kayit (Preset, Sorusuz)` sonrasi masaustunde zaman damgali yeni dosyalar olusuyor mu?
7. Quick kayitta su iki dosya birlikte uretiliyor mu?
   - `quick_take_YYYYMMDD_HHMMSS.mp3`
   - `quick_take_YYYYMMDD_HHMMSS_vocal.wav`
8. Tam kayitta su iki dosya birlikte uretiliyor mu?
   - `guitar_mix_YYYYMMDD_HHMMSS.mp3`
   - `guitar_mix_YYYYMMDD_HHMMSS_vocal.wav`
9. Dosyalarin dogrudan Masaustu'ne yazilmasi ve yeni klasor olusmamasi kullanici icin beklenen davranis mi?
