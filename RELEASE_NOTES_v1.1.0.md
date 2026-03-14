# v1.1.0 Release Notes

## Yeni
- Hazır profil sistemi eklendi:
  - `Clean (Temiz)`
  - `Crunch (Ritmik)`
  - `Lead (Solo)`
- `Hızlı Kayıt (Test + Kayıt)` eklendi.
- `Dosya Adını Otomatik Oluştur` eklendi.
- `Yardım (Hızlı Kullanım)` penceresi eklendi.

## İyileştirmeler
- Arayüz kaydırma desteği eklendi; alt butonlar her pencerede erişilebilir.
- Buton görünürlüğü düzeltildi.
- Preset değerleri daha dengeli ve profesyonel tona göre optimize edildi.
- MP3 üretimi güçlendirildi:
  - `ffmpeg` birden fazla standart yoldan aranır.
  - MP3 üretilemese bile `mix.wav` ve `vocal.wav` garanti kaydedilir.

## Kurulum ve Paketleme
- macOS build/kurulum akışı güncellendi:
  - `build_macos_app.sh`
  - `install_macos_professional.sh`
  - `package_macos_release.sh`
- Masaüstü başlatıcı akışı iyileştirildi.
- Release workflow güncellendi (`release-macos.yml`).

## Kullanım (Hızlı)
1. `Müzik Dosyası Seç`
2. `Hazır Profil` seç + `Profili Uygula`
3. `Dosya Adını Otomatik Oluştur`
4. `Hızlı Kayıt (Test + Kayıt)`
5. Masaüstü çıktıları:
   - `guitar_mix_... .mp3`
   - `guitar_mix_..._mix.wav`
   - `guitar_mix_..._vocal.wav`
   - `guitar_mix_..._device_test.wav`

## Not
- Bu sürüm özellikle kullanım akışını sadeleştirme ve kayıt güvenilirliğini artırma odaklıdır.
