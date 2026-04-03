# Windows Release Checklist

Bu kontrol listesi, uygulamayi Windows kullanicilarina dagitmadan once indirme, ilk acilis ve kayit akisinin eksiksiz oldugunu dogrulamak icin kullanilir.

## Yerel Hazirlik

1. `VERSION` ve `CHANGELOG.md` ayni surumu gostermeli.
2. Release sayfasinda `GuitarAmpRecorder-Windows.zip` ve `GuitarAmpRecorder-Windows.zip.sha256` dosyalari gorunmeli.
3. Indirme sayfasi Windows zip dosyasina dogru link vermeli.

## Ilk Acilis

1. `GuitarAmpRecorder-Windows.zip` dosyasini indirin.
2. ZIP dosyasini acin.
3. Uygulamayi calistirin.
4. Windows guvenlik uyarisi cikarsa:
   - `Daha fazla bilgi`
   - `Yine de calistir`
5. `Mikrofon/Ses Karti Testi (5 sn)` ile kisa test yapin.

## Kayit Kontrolu

1. Test sonunda `Peak=0.000` gorunmemeli.
2. `Quick Kayit (Preset, Sorusuz)` sonrasi su iki dosya birlikte uretilmeli:
   - `quick_take_YYYYMMDD_HHMMSS.mp3`
   - `quick_take_YYYYMMDD_HHMMSS_vocal.wav`
3. `Kaydi Baslat ve MP3 Cikar` sonrasi su iki dosya birlikte uretilmeli:
   - `guitar_mix_YYYYMMDD_HHMMSS.mp3`
   - `guitar_mix_YYYYMMDD_HHMMSS_vocal.wav`

## Son Kullanici Beklentisi

1. Dosyalar dogrudan Masaustu'ne yazilabilir; yeni klasor olusmamasi normaldir.
2. Eski sessiz denemeler yerine en yeni zaman damgali dosya acilmalidir.
3. Ilk dogrulama icin once `..._vocal.wav` dinlenmelidir.

## Yayin Sonrasi Kontrol

1. GitHub Release sayfasi aciliyor mu?
2. GitHub Pages indirme sayfasi Windows zip ve SHA256 linklerini gosteriyor mu?
3. Temiz bir Windows kullanici hesabinda uygulama aciliyor mu?
4. Mikrofon testi ve hizli kayit gercekten sesli sonuc veriyor mu?
