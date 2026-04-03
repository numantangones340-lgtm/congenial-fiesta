# Destek ve Sik Sorulan Sorular

Bu sayfa, uygulamayi ilk kez kullananlarin en sik yasadigi sorunlari hizli cozmeleri icin hazirlanmistir.

## 1. Test yaptim ama `Peak=0.000` gorunuyor

Kontrol edin:

- mikrofon izni verildi mi
- dogru mikrofon secili mi
- uygulama yeniden acildi mi

En hizli cozum:

1. Uygulamayi kapatin.
2. Mikrofon iznini kontrol edin.
3. Uygulamayi yeniden acin.
4. `Mikrofon/Ses Karti Testi (5 sn)` yapin.

## 2. Dosya olustu ama ses yok

Bu durumda genelde su olur:

- eski sessiz deneme dosyasi acilmistir
- en yeni zaman damgali dosya yerine eski bir dosya dinlenmistir

Dogru kontrol:

1. En yeni zaman damgali dosyayi acin.
2. Once `..._vocal.wav` dosyasini dinleyin.
3. Ses varsa sonra `mp3` dosyasini kontrol edin.

## 3. Masaustunde yeni klasor olusmadi

Bu normaldir.

- uygulama cogu zaman dosyalari dogrudan Masaustu'ne yazar
- yeni klasor olusmasi zorunlu degildir

## 4. Quick Kayit ile Tam Kayit farkli dosya adlari uretiyor

Bu beklenen davranistir:

- Quick Kayit:
  - `quick_take_YYYYMMDD_HHMMSS.mp3`
  - `quick_take_YYYYMMDD_HHMMSS_vocal.wav`
- Tam Kayit:
  - `guitar_mix_YYYYMMDD_HHMMSS.mp3`
  - `guitar_mix_YYYYMMDD_HHMMSS_vocal.wav`

## 5. Windows acilisinda guvenlik uyarisi cikiyor

Bu ilk acilista gorulebilir.

Izlenecek yol:

1. `Daha fazla bilgi`
2. `Yine de calistir`

## 6. macOS uygulamasi Masaustu'ne yazamiyor

Kontrol edin:

- `GuitarAmpRecorder > Masaustu Klasoru` izni acik mi

Gerekirse:

1. `Sistem Ayarlari > Gizlilik ve Guvenlik > Dosyalar ve Klasorler`
2. `GuitarAmpRecorder`
3. `Masaustu Klasoru` iznini acin

## 7. Hangi dosyayi dinlemeliyim?

Ilk dogrulama icin en iyi dosya:

- `..._vocal.wav`

Bu dosyada ses varsa kayit tarafi duzgun calisiyor demektir.

## Resmi Sayfalar

- GitHub Releases:
  `https://github.com/numantangones340-lgtm/congenial-fiesta/releases/latest`
- GitHub Pages:
  `https://numantangones340-lgtm.github.io/congenial-fiesta/`
