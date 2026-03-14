# PR: v1.1.0 - Pro Recorder UX ve Release Hazırlığı

## Özet
Bu PR, `v1.0.3` sonrası uygulamayı günlük kullanımda daha stabil ve hızlı hale getirir:
- Arayüz erişilebilirliği düzeltildi (scroll + görünür butonlar)
- Hazır ses profilleri eklendi (`Clean`, `Crunch`, `Lead`)
- Tek adım akış eklendi: `Hızlı Kayıt (Test + Kayıt)`
- Otomatik dosya adı üretimi eklendi (profil + zaman damgası)
- Yardım penceresi eklendi (`Yardım (Hızlı Kullanım)`)
- MP3 üretimi güçlendirildi (`ffmpeg` yol tespiti + WAV garanti)
- macOS kurulum/paketleme akışı sadeleştirildi

## Değişiklikler
### Uygulama (`app.py`)
- Dikey kaydırmalı arayüz eklendi; alt butonlar her ekran çözünürlüğünde erişilebilir.
- Buton görünürlüğü düzeltildi.
- Preset sistemi eklendi:
  - `Clean (Temiz)`
  - `Crunch (Ritmik)`
  - `Lead (Solo)`
- `Profili Uygula` ile tek tık slider yükleme.
- `Dosya Adını Otomatik Oluştur` ile ad şablonu:
  - `guitar_mix_YYYYMMDD_HHMMSS_profil`
- `Yardım (Hızlı Kullanım)` popup penceresi.
- `Hızlı Kayıt (Test + Kayıt)` akışı:
  1. 5 sn test
  2. Test başarılıysa otomatik ana kayıt
- `ffmpeg` tespiti güçlendirildi:
  - `PATH`, `/opt/homebrew/bin/ffmpeg`, `/usr/local/bin/ffmpeg`
- MP3 başarısız olsa bile `*_mix.wav` ve `*_vocal.wav` garanti yazılır.

### Dokümantasyon (`README.md`)
- Kullanım adımları güncellendi.
- Hızlı kullanım kartı eklendi.
- Yeni akış ve çıktı isimleri netleştirildi.

### Kurulum/Paketleme
- `build_macos_app.sh` eklendi/güncellendi.
- `install_macos_professional.sh` eklendi (build + install + cleanup + launcher).
- `package_macos_release.sh` güncellendi.
- `install_desktop_shortcut.sh` iyileştirildi.
- `release-macos.yml` akışı release için hazırlandı.
- `.gitignore` geçici/artifact dosyaları için genişletildi.

## Neden
- Kullanıcı tarafında görünmeyen test/kayıt butonları ve MP3 üretim tutarsızlıkları vardı.
- Kurulum ve günlük kayıt akışı çok adımlıydı.
- Hedef: tek ekranda, tek tıkla daha güvenilir kayıt deneyimi.

## Test Notları
- Uygulama açılışı (macOS) doğrulandı.
- Scroll ile alt buton görünürlüğü doğrulandı.
- Profil seçimi ve otomatik adlandırma doğrulandı.
- Hızlı kayıt akışı doğrulandı.
- Masaüstü çıktıları doğrulandı:
  - `*.mp3`
  - `*_mix.wav`
  - `*_vocal.wav`
  - `*_device_test.wav`

## Sürümleme
- Tag: `v1.1.0`
- Branch: `codex/release-final`
