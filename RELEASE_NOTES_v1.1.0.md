# GuitarAmpRecorder v1.1.0

## Öne Çıkanlar
- 3 hazır ton profili: `Clean (Temiz)`, `Crunch (Ritmik)`, `Lead (Solo)`.
- Tek adım akış: `Hızlı Kayıt (Test + Kayıt)`.
- `Dosya Adını Otomatik Oluştur` ile düzenli çıktı isimlendirme.
- `Yardım (Hızlı Kullanım)` ile uygulama içi kısa rehber.

## Stabilite ve Kullanılabilirlik
- Alt butonların görünmeme sorunu çözüldü (kaydırılabilir arayüz).
- Karanlık tema görünürlüğü iyileştirildi.
- Preset değerleri günlük kullanımda daha dengeli ton için düzenlendi.
- MP3 üretimi güçlendirildi:
  - `ffmpeg` birden fazla standart konumda aranır.
  - MP3 üretilemezse kayıt yine kaybolmaz; WAV çıktıları garanti edilir.

## Çıktı Garantisi
Her kayıtta en az aşağıdaki dosyalar alınır:
- `guitar_mix_..._mix.wav`
- `guitar_mix_..._vocal.wav`
- `guitar_mix_..._device_test.wav` (test adımı sonrası)
- Uygun ortamda ek olarak: `guitar_mix_....mp3`

## Hızlı Kullanım
1. `Müzik Dosyası Seç`
2. `Hazır Profil` seç + `Profili Uygula`
3. `Dosya Adını Otomatik Oluştur`
4. `Hızlı Kayıt (Test + Kayıt)` veya `Kaydı Başlat ve MP3 Çıkar`
5. Çıktıları masaüstünde kontrol et

## Altyapı / Release
- macOS build + kurulum scriptleri güncellendi:
  - `build_macos_app.sh`
  - `install_macos_professional.sh`
  - `package_macos_release.sh`
- Release workflow netleştirildi (`release-macos.yml`).

## Uyumluluk
- Platform: macOS
- Breaking change: yok
