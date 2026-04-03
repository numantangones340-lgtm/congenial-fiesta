# Ilk Acilis ve Hızlı Kullanım Kılavuzu

Bu kısa kılavuz, uygulamayı indiren bir kullanıcının en az adımla çalışır kayda geçmesi için hazırlanmıştır.

## En Kısa Yol

1. İşletim sisteminize uygun zip dosyasını indirin.
2. ZIP dosyasını açın.
3. Uygulamayı çalıştırın.
4. Gerekirse izin pencerelerinde `İzin Ver` deyin.
5. `Mikrofon/Ses Kartı Testi (5 sn)` ile kısa test yapın.
6. `Peak=0.000` değilse doğrudan kayda geçin.

## macOS

1. `GuitarAmpRecorder-macOS.zip` dosyasını indirin.
2. ZIP'i açın.
3. `GuitarAmpRecorder.app` uygulamasını çalıştırın.
4. Mikrofon izni gelirse `İzin Ver` deyin.
5. Masaüstü klasörü izni gelirse `İzin Ver` deyin.
6. `Mikrofon/Ses Kartı Testi (5 sn)` ile kısa test yapın.
7. Test sonunda `Peak=0.000` değilse:
   - `Quick Kayıt (Preset, Sorusuz)` ile hızlı kayıt alın
   - veya `Kaydı Başlat ve MP3 Çıkar` ile tam kayıt alın

## Windows

1. `GuitarAmpRecorder-Windows.zip` dosyasını indirin.
2. ZIP'i açın.
3. İçindeki uygulamayı çalıştırın.
4. Windows güvenlik uyarısı çıkarsa:
   - `Daha fazla bilgi`
   - ardından `Yine de çalıştır`
5. `Mikrofon/Ses Kartı Testi (5 sn)` ile kısa test yapın.
6. `Peak=0.000` değilse kayda geçin.

## Hangi Dosya Oluşur?

Quick kayıt:

- `quick_take_YYYYMMDD_HHMMSS.mp3`
- `quick_take_YYYYMMDD_HHMMSS_vocal.wav`

Tam kayıt:

- `guitar_mix_YYYYMMDD_HHMMSS.mp3`
- `guitar_mix_YYYYMMDD_HHMMSS_vocal.wav`

Not:

- Dosyalar çoğu zaman doğrudan Masaüstü'ne yazılır.
- Yeni klasör oluşmaması normaldir.

## Hızlı Sorun Giderme

`Peak=0.000` görünüyorsa:

- mikrofon iznini kontrol edin
- uygulamayı kapatıp yeniden açın
- tekrar `Mikrofon/Ses Kartı Testi (5 sn)` yapın

Dosya oluşuyor ama sessiz çalıyorsa:

- en yeni zaman damgalı dosyayı açın
- eski başarısız deneme dosyalarıyla karıştırmayın
- önce `..._vocal.wav` dosyasını dinleyin

Masaüstü'ne yazamıyorsa:

- uygulamanın Masaüstü klasörü iznini açın

## Resmi Linkler

- GitHub Releases:
  `https://github.com/numantangones340-lgtm/congenial-fiesta/releases/latest`
- GitHub Pages:
  `https://numantangones340-lgtm.github.io/congenial-fiesta/`
