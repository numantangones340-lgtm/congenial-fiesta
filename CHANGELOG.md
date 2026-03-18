# Changelog

Bu dosya surum bazli degisiklikleri tutar.

## [1.1.0] - 2026-03-19

### Eklendi

- Canli giris metre sistemi, peak-hold ve clipping uyarisi
- Canli monitor ac/kapat ve monitor seviye kontrolu
- Noise gate esigi ayari
- Kompresor ve limiter zinciri
- High-pass ve presence ton kontrolleri
- MP3 kalite secenekleri
- WAV export modlari
- Kayit durumu paneli, gecen/kalan sure gosterimi
- Kaydi durdurup o ana kadar alinan bolumu kaydetme
- Son ciktilar paneli ve Finder entegrasyonu
- Isimli coklu preset yonetimi
- Tarihli veya isimli oturum klasoru modu
- `session_summary.json` ile oturum ozeti
- Son oturumu yeniden yukleme akisi
- Uygulama ici `Hakkinda` ve `VERSION` tabanli surum gostergesi

### Degisti

- Cihaz test dosyalari secilen cikis klasorune yazilir hale geldi
- Quick kayit dosya adlari aktif cikis/oturum klasorune gore uretilir hale geldi
- Export akisi MP3, mix WAV ve vocal WAV seceneklerini destekler hale geldi
- Release scripti ve macOS dagitim akisi notarization'a hazir hale getirildi

### Guvenlik ve Kararlilik

- Giris seviyesi cok dusuk/cok yuksek durumlari icin guvenlik uyarilari eklendi
- Asiri clipping durumunda kayit baslatma blokajı eklendi
- Son oturum bilgisi ve session summary ile daha izlenebilir bir is akisina gecildi
