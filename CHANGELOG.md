# Changelog

Bu dosya surum bazli degisiklikleri tutar.

## [1.1.6] - 2026-03-25

### Degisti

- macOS build paketi sonrasinda `.app` bundle `Info.plist` icine surum alanlari dogrudan yazilir hale getirildi
- bundle metadata akisi PyInstaller varsayilanlarina bagli kalmayacak sekilde build script icinde netlestirildi

### Guvenlik ve Kararlilik

- `CFBundleShortVersionString` ve `CFBundleVersion` alanlari `VERSION` dosyasi ile birebir esitlenir hale getirildi
- mikrofon izin aciklamasi her build'de bundle icine garanti sekilde yazilir hale getirildi

## [1.1.5] - 2026-03-25

### Degisti

- GUI preset kaydetme akisi, bos adla kaydetme denemesinde mevcut kullanici preset'ini guncelleyecek sekilde netlestirildi
- yerlesik preset adlari ile cakisan kullanici verileri filtrelenerek hazir presetlerin bozulmasi engellendi
- eski tekli GUI preset dosyalari coklu preset deposuna daha guvenli bicimde tasinacak sekilde ele alindi

### Guvenlik ve Kararlilik

- yerlesik GUI presetler uzerine kaydetme ve silme islemleri acik hata mesajlariyla bloklandi
- preset silme sonrasi secili preset baglami korunarak beklenmedik hedef degisimi riski azaltildi
- GUI preset store davranislari yeni unittest kapsami ile dogrulandi

## [1.1.3] - 2026-03-21

### Eklendi

- `CHANGELOG.md` kaynagindan otomatik GitHub Release notes uretimi
- temel import, CLI ve release notes dogrulamasi icin hafif smoke testleri
- birlesik masaustu release workflow'u ile macOS ve Windows release otomasyonu

### Degisti

- release sureci tek matrix workflow altinda sadeleştirildi
- CI akisina `py_compile`, smoke test ve shell script dogrulama adimlari eklendi
- CLI'ya etkileşimsiz `--help` ve `--version` bayraklari eklendi

### Guvenlik ve Kararlilik

- release body ile etiketlenen surum arasinda tek kaynakli metadata akisi netlestirildi
- manuel release adimlari azaltildi ve artefact isimleri standartlastirildi

## [1.1.2] - 2026-03-19

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
