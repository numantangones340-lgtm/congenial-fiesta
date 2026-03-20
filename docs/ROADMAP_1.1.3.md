# Roadmap 1.1.3

Bu not, `1.1.3` icin onerilen bakim ve guvenilirlik islerini kisa bir backlog olarak toplar.
Asagidaki maddeler 2026-03-20 itibariyla gozden gecirilmis ve durumlari isaretlenmistir.

## Hedef

- release surecini daha az manuel hale getirmek
- GitHub Actions loglarini temizlemek
- macOS ve Windows artefact isimlerini tutarli hale getirmek
- temel CI kapsamini biraz daha guclendirmek

## Onerilen Isler

### 1. GitHub Actions warning temizligi

Durum: tamamlandi

- `actions/setup-python`
- `actions/upload-artifact`
- `softprops/action-gh-release`

Bu action surumleri Node 24 uyumlulugu acisindan gozden gecirilmeli.

### 2. Workflow sadeleştirme

Durum: tamamlandi

- artik kullanilmayan `self-hosted` varsayimlarini temizle
- release workflow'lari icin tek bir net runner stratejisi kullan
- eski veya cakisan workflow dosyalarini ayikla

### 3. Release asset isimlerini standartlastirma

Durum: tamamlandi

Tercih edilen adlar:

- `GuitarAmpRecorder-macOS.zip`
- `GuitarAmpRecorder-Windows.zip`

Eski `GuitarAmpKaydedici-*` varyantlari tek formata indirilmeli.
Mevcut aktif release akisi tercih edilen adlari kullanmaktadir.

### 4. Release notes otomasyonu

Durum: tamamlandi

- `CHANGELOG.md` ile GitHub Release body arasinda tek kaynak belirle
- release metnini dosyadan veya sablon uzerinden uret

### 5. CI kapsam genisletme

Durum: tamamlandi

Mevcut `py_compile` kontrolune ek olarak hafif smoke testler dusunulebilir:

- temel import testi
- CLI acilis testi
- build script dogrulamasi

### 6. Tag / release akisini netlestirme

Durum: tamamlandi

- merge sonrasi tag mi, tag sonrasi release mi tek akis belirle
- manuel tag duzeltme ihtiyacini azalt

### 7. macOS build guvenilirligi

Durum: tamamlandi

- `build_macos_app.sh` GitHub-hosted ortamda yeniden gozden gecirilsin
- Python ve PyInstaller surumleri daha net sabitlensin
- gerekirse cache kullanimi eklensin

## Sonuc

`1.1.3` bakim turundeki ana hedefler tamamlandi:

- Actions warning ve workflow bakimlari yapildi
- release notes akisi tek kaynaga indirildi
- hafif smoke test kapsami eklendi
- release tagging akisi daha guvenli hale getirildi
- macOS build sureci daha guvenilir hale getirildi

## Oncelik Onerisi

Ilk sirada:

- GitHub Actions warning temizligi
- workflow sadeleştirme
- release asset isim standardi

Ikinci sirada:

- release notes otomasyonu
- CI kapsam genisletme

Sonraki adim:

- yeni uygulama ozellikleri veya kullanici odakli iyilestirmeler icin ayrik bir `1.1.3` feature/backlog turu acilabilir
