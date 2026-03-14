# PR: v1.1.0 - Pro Recorder UX, Stabilite ve Release Paketleme

## Kapsam Özeti
Bu PR, `v1.0.3` sonrası kullanım akışını sadeleştirir ve kayıt güvenilirliğini artırır.

- Alt kontrollerin görünür olmama sorunu çözüldü (kaydırılabilir arayüz).
- 3 hazır profil eklendi: `Clean (Temiz)`, `Crunch (Ritmik)`, `Lead (Solo)`.
- Tek adım çalışma akışı eklendi: `Hızlı Kayıt (Test + Kayıt)`.
- Otomatik dosya adı üretimi eklendi (profil + zaman damgası).
- MP3 üretimi güçlendirildi; başarısız durumda WAV çıktıları garanti edildi.
- macOS build/kurulum/paketleme akışı release için netleştirildi.

## Teknik Değişiklikler
### Uygulama katmanı (`app.py`)
- Dikey scroll container eklendi; alt butonlar her çözünürlükte erişilebilir.
- Karanlık tema görünürlük düzeltmeleri yapıldı (buton ve alt durum metni).
- Preset seçimi + `Profili Uygula` ile tek tık parametre yükleme akışı eklendi.
- `Dosya Adını Otomatik Oluştur` eklendi.
  - Şablon: `guitar_mix_YYYYMMDD_HHMMSS_profil`
- `Yardım (Hızlı Kullanım)` penceresi eklendi.
- `Hızlı Kayıt (Test + Kayıt)` eklendi:
  1. 5 sn cihaz testi
  2. Başarılıysa ana kayıt akışı
- `ffmpeg` bulunabilirliği güçlendirildi:
  - `PATH`
  - `/opt/homebrew/bin/ffmpeg`
  - `/usr/local/bin/ffmpeg`
- MP3 oluşturma başarısız olsa bile `*_mix.wav` + `*_vocal.wav` çıktıları korunur.

### Dokümantasyon
- README kullanım adımları güncellendi.
- Hızlı kullanım akışı ve çıktı adlandırması netleştirildi.

### Build / Packaging
- `build_macos_app.sh` güncellendi.
- `install_macos_professional.sh` eklendi/güncellendi.
- `package_macos_release.sh` güncellendi.
- `install_desktop_shortcut.sh` iyileştirildi.
- `release-macos.yml` release akışına göre netleştirildi.
- `.gitignore` geçici build/artifact dosyalarını kapsayacak şekilde genişletildi.

## Kullanıcı Etkisi
- Uygulama ilk açılıştan kayda kadar daha az adımda kullanılabilir.
- Alt butonların görünmemesi kaynaklı tıkanma giderildi.
- MP3 üretiminde sorun yaşansa dahi kayıt çıktısı kaybolmaz.
- Profil tabanlı kullanım ile hızlı ton geçişi mümkün.

## Test / Doğrulama
- macOS üzerinde uygulama açılışı doğrulandı.
- Scroll ile alt kontrollerin erişimi doğrulandı.
- Profil uygulama ve otomatik adlandırma doğrulandı.
- Hızlı kayıt akışı doğrulandı.
- Masaüstü çıktıları doğrulandı:
  - `*.mp3`
  - `*_mix.wav`
  - `*_vocal.wav`
  - `*_device_test.wav`

## Risk ve Geri Dönüş
- Kırıcı değişiklik yok.
- Rollback: `v1.0.3` tag’ine dönüş + yeni build artifact’larının temizlenmesi.

## Sürümleme
- Branch: `codex/release-final`
- Tag: `v1.1.0`
