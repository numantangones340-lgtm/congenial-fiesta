# Changelog

Bu dosya surum bazli degisiklikleri tutar.

## [1.1.10] - 2026-04-03

### Eklendi

- macOS `.app` icin ilk acilis mikrofon akisini dogrulayan release kontrolleri
- GitHub Pages indirme sayfasinda dogrudan `macOS` ve `Windows` zip baglantilari
- ilk acilis izni, `Peak` kontrolu ve quick kayit akislarini anlatan son kullanici kurulum notlari

### Degisti

- paketlenmis macOS uygulamasinda mikrofon izin bildirimi ve kayit akisi duzeltildi
- packaged app icin preset/oturum dosyalari kullanici veri klasorune daha guvenli sekilde yazilir hale getirildi
- `Quick Kayit` dosya adlari eski artan numara yerine zaman damgali ve daha anlasilir formatta uretilir hale geldi
- release ve dagitim dokumani son kullanicinin `indir, izin ver, test et, kaydet` akisina gore sadeleştirildi

### Guvenlik ve Kararlilik

- varsayilan giris seciliyken eski aygit kimliginin kayit tarafinda kullanilmasi engellendi
- giris sample rate secili mikrofonun gercek varsayilan degerine gore ayarlandi
- paketleme akisinda repo kokunde kirli spec dosyasi birakilmamasi saglandi

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
