# Guitar Amp Recorder (macOS / Windows)

Hizli indirme:

- GitHub Releases:
  https://github.com/numantangones340-lgtm/congenial-fiesta/releases/latest
- GitHub Pages:
  https://numantangones340-lgtm.github.io/congenial-fiesta/
- Ilk kullanim kilavuzu:
  `docs/FIRST_RUN_GUIDE.md`
- Destek / SSS:
  `docs/SUPPORT_FAQ.md`
- Katki rehberi:
  `CONTRIBUTING.md`
- Teslim ozeti:
  `docs/DELIVERY_SUMMARY.md`

Bu uygulama şunları yapar:
- 1. kanal: Hazır müzik (arka plan)
- 2. kanal: Mikrofon kaydı
- Mikrofon kanalına amfi benzeri efektler (kazanç, güçlendirme, bas, tiz, distorsiyon)
- Gürültü azaltma (%), hızlandırma/yavaşlatma (%), çıkış kazancı (dB)
- Mikrofon ve ses kartı aygıt kimliği seçimi (giriş/çıkış, boş bırakılabilir)
- Kayıt sınırı seçimi (1 saat / 2 saat)
- Tek tık 5 sn cihaz/kayıt testi
- Sonucu otomatik MP3 olarak Masaüstüne çıkarır

## Son Eklenen Konfor Araçları

Bakim turlarinda eklenen kucuk ama faydali kolayliklar:

- `Son Çıktılar` içinde `Çıktı Filtresi`
- `Görünen Sesi Oynat`
- `Görünen Dosyayı Göster`
- `Görünen Yolu Kopyala`
- `Listeyi Kopyala`
- `Eski Denemeleri Temizle`
- `Son Oturumu Arşivle`
- `Temiz Başlangıç`
- `Kayıt Planı` alaninda `Hazırlık Yolunu Kopyala`
- `Hazırlık durumu` rozeti ve mini bilgi satiri

## Dil Desteği

- Arayüz dili: Türkçe
- Terminal (CLI) metinleri: Türkçe
- GUI metinleri: Türkçe

## Kurulum (macOS önerilen)

1. Python 3.9+ kurulu olsun (onerilen: 3.10+).
2. `ffmpeg` kurun:
   - macOS (Homebrew):
     ```bash
     brew install ffmpeg
     ```
3. Proje klasöründe sanal ortam kurup paketleri yükleyin:
   ```bash
   cd /Users/numantangones/Documents/GuitarAmpRecorder
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

## Kurulum (Windows)

1. Python 3.9+ kurulu olsun (önerilen: 3.10+).
2. `ffmpeg` kurun ve PATH'e ekleyin (MP3 için).
3. Hazir release kullanacaksaniz GitHub Releases'ten su iki dosyayi indirin:
   - `GuitarAmpRecorder-Windows.zip`
   - `GuitarAmpRecorder-Windows.zip.sha256`
4. Proje klasöründe çalıştırın:
   ```bat
   cd C:\Users\%USERNAME%\Documents\GuitarAmpRecorder
   CALISTIR.bat
   ```

## macOS `.app` paketleme (önerilen)

`Tk/Tcl` kaynakları eksik paketlenirse uygulama açılırken `EXC_CRASH (SIGABRT)` verebilir.
Bu repo içindeki build akışı bu kaynakları `.app` içine ekler.

```bash
cd /Users/numantangones/Documents/GuitarAmpRecorder
source .venv/bin/activate
pip install pyinstaller
./build_macos_app.sh
```

Üretilen uygulama:

- `dist/GuitarAmpRecorder.app`
- `dist/GuitarAmpRecorder-macOS.zip`
- `dist/GuitarAmpRecorder-macOS.zip.sha256`

## Release Hazirligi

Repo icinde dogrudan kullanilabilen macOS release paketleme komutu:

```bash
./package_macos_release.sh
```

Bu komut mevcut `.app` paketini zip'ler; paket yoksa once `./build_macos_app.sh` calisir.
Sonuc olarak hem `dist/GuitarAmpRecorder-macOS.zip` hem de `dist/GuitarAmpRecorder-macOS.zip.sha256` hazir olur.
Windows release workflow'u da `GuitarAmpRecorder-Windows.zip` ve `GuitarAmpRecorder-Windows.zip.sha256` artefact'lerini uretir.

Detayli kontrol listesi:

- `docs/MACOS_RELEASE_CHECKLIST.md`
- `docs/WINDOWS_RELEASE_CHECKLIST.md`
- `docs/RELEASE_PREP.md`
- `docs/PRODUCT_ROADMAP.md`
- `docs/FIRST_RUN_GUIDE.md`
- `docs/SUPPORT_FAQ.md`

## Çalıştırma

```bash
cd /Users/numantangones/Documents/GuitarAmpRecorder
./CALISTIR.command
```

`CALISTIR.command` otomatik olarak GUI sürümünü açar; GUI açılamazsa CLI sürüme geçer.

Manuel mod seçimi:

```bash
./CALISTIR.command gui
./CALISTIR.command cli
./CALISTIR.command quick
```

Windows için:

```bat
cd C:\Users\%USERNAME%\Documents\GuitarAmpRecorder
CALISTIR.bat
CALISTIR.bat gui
CALISTIR.bat cli
```

## İlk Açılışta En Güvenli Sıra

1. `Mikrofonları Yeniden Tara` ile giriş ve çıkışı doğrulayın.
2. `Çıkış Klasörü` seçin.
3. MP3 istiyorsanız `ffmpeg` kurulu olduğundan emin olun.
4. Önce `5 sn test`, sonra gerçek kayda geçin.

Notlar:
- Mikrofon görünmüyorsa macOS içinde `Sistem Ayarları > Gizlilik ve Güvenlik > Mikrofon` iznini açın.
- Aygıt kimliklerini boş bırakmak en güvenli başlangıçtır; sorun olursa uygulamadaki `Önerilen Aygıtları Doldur` yolunu deneyin.
- `ffmpeg` yoksa MP3 yerine WAV ile devam edebilirsiniz.

CLI sürümünde son kullandığınız ayarlar proje klasöründeki `.last_preset.json` dosyasına kaydedilir.
Bir sonraki açılışta `Kayıtlı ayarlar yüklensin mi? [E/h]:` sorusuna `E` diyerek tek adımda devam edebilirsiniz.
`./CALISTIR.command quick` komutu ise kayıtlı ayarlar ile soru sormadan doğrudan kayıt alır.
Bu kayda mikrofon/çıkış aygıt kimlikleri de dahildir.
`CALISTIR.command`, `requirements.txt` ve Python sürümü değişmediyse `pip install` adımını otomatik atlar (daha hızlı açılış).
Quick kayıt dosya adı zaman damgalı ve nettir: `quick_take_20260403_191431`, `quick_take_20260403_191623` ...

## macOS İlk Açılış (En Kolay Yol)

İndirilen `.app` ilk kez açıldığında macOS bazı izinler isteyebilir. En kısa doğru akış:

1. Uygulamayı açın.
2. Mikrofon izni penceresi gelirse `İzin Ver` deyin.
3. Masaüstü klasörü izni istenirse yine `İzin Ver` deyin.
4. `Mikrofon/Ses Kartı Testi (5 sn)` ile kısa test yapın.
5. Test sonunda alttaki `Peak=...` değeri `0.000` değilse mikrofon doğru çalışıyor demektir.
6. Sonra `Quick Kayıt (Preset, Sorusuz)` ile 5-10 saniyelik gerçek kayıt alın.

Başarılı ilk kayıt sonrası Masaüstü'nde genelde şu dosyalar oluşur:

- `quick_take_YYYYMMDD_HHMMSS.mp3`
- `quick_take_YYYYMMDD_HHMMSS_vocal.wav`

Tam kayıt akışında ise dosya adı genelde `guitar_mix_YYYYMMDD_HHMMSS` ile başlar:

- `guitar_mix_YYYYMMDD_HHMMSS.mp3`
- `guitar_mix_YYYYMMDD_HHMMSS_vocal.wav`

Not:

- Yeni klasör oluşmayabilir; varsayılan akış çoğu zaman dosyaları doğrudan Masaüstü'ne yazar.

Eğer masaüstünde eski sessiz denemeler varsa, en yeni çalışan dosyalar genelde en son zaman damgasını taşıyanlar olacaktır.

## macOS Hızlı Sorun Giderme

- `Peak=0.000` görünüyorsa:
  - `Sistem Ayarları > Gizlilik ve Güvenlik > Mikrofon` içinde `GuitarAmpRecorder` için izin açık olmalı.
- Kayıt dosyası oluşuyor ama Finder'da sessiz çalıyorsa:
  - eski başarısız denemeleri değil, en yeni zaman damgalı `quick_take_...` veya `guitar_mix_...` dosyasını açın.
- Masaüstüne yazamıyorsa:
  - `Sistem Ayarları > Gizlilik ve Güvenlik > Dosyalar ve Klasörler` içinde `GuitarAmpRecorder > Masaüstü Klasörü` açık olmalı.

CLI için isimli preset deposu da desteklenir:

- proje klasöründeki `.cli_presets.json` içinde tutulur
- açılışta kayıtlı isimli preset seçebilirsiniz
- kayıt sonunda mevcut ayarları isimli preset olarak kaydedebilirsiniz
- komut satırıyla da yönetebilirsiniz:

```bash
python3 cli_app.py --list-presets
python3 cli_app.py --show-preset "Temiz"
python3 cli_app.py --select-preset "Temiz"
python3 cli_app.py --rename-preset "Eski" "Yeni"
python3 cli_app.py --show-settings
python3 cli_app.py --show-settings --preset "Temiz"
python3 cli_app.py --list-devices
python3 cli_app.py --test
python3 cli_app.py --test --preset "Temiz"
python3 cli_app.py --preset "Temiz"
python3 cli_app.py --quick --preset "Temiz"
python3 cli_app.py --delete-preset "Temiz"
python3 cli_app.py --save-preset "Yeni Preset"
python3 cli_app.py --help
```

## Masaustu Tek Tik Baslatici

```bash
cd /Users/numantangones/Documents/GuitarAmpRecorder
./install_desktop_shortcut.sh
```

Bu komut `~/Desktop/GuitarAmpRecorder.command` dosyasi olusturur.
Ek olarak `~/Desktop/GuitarAmpRecorder-Quick.command` dosyasini da olusturur (sorusuz quick kayit).

## Masaustune macOS Kurulum Paketi Alma

```bash
cd /Users/numantangones/Documents/GuitarAmpRecorder
./package_macos_release.sh
```

Bu komut:
- `dist/GuitarAmpRecorder-macOS.zip` olusturur
- `dist/GuitarAmpRecorder-macOS.zip.sha256` olusturur
- ayni zip dosyasini `~/Desktop/GuitarAmpRecorder-macOS.zip` olarak kopyalar
- checksum dosyasini `~/Desktop/GuitarAmpRecorder-macOS.zip.sha256` olarak kopyalar

Build + zip islemini tek komutta almak icin:

```bash
cd /Users/numantangones/Documents/GuitarAmpRecorder
./build_macos_app.sh
./package_macos_release.sh
```

## Guvenilir Indirme Sayfalari

- GitHub Releases (resmi surum dosyalari):
  - https://github.com/numantangones340-lgtm/congenial-fiesta/releases/latest
- GitHub Pages (indirme yonlendirme sayfasi):
  - https://numantangones340-lgtm.github.io/congenial-fiesta/
- Hızlı ilk açılış kılavuzu:
  - `docs/FIRST_RUN_GUIDE.md`
- Destek / SSS:
  - `docs/SUPPORT_FAQ.md`

## Yayinlama (Diger Kullanicilar Icin)

Bu repoda otomatik yayin akisi eklidir:
- `.github/workflows/release.yml`
  - `v*` etiketi push edilince tek matrix workflow ile macOS ve Windows build alir.
  - macOS kolu varsa codesign + notarization yapar, her iki platform icin zip ve Release asset uretir.
  - macOS signing/notarization icin `sign_macos_app.sh` ve `notarize_macos_app.sh` scriptlerini kullanir.
- `.github/workflows/static.yml`
  - `main` branch push edilince `docs/` klasorunu GitHub Pages'e deploy eder.

macOS workflow icin onerilen GitHub secrets:

- `APPLE_DEVELOPER_ID_APP_CERT_BASE64`
- `APPLE_DEVELOPER_ID_APP_CERT_PASSWORD`
- `APPLE_DEVELOPER_ID_APP_IDENTITY`
- `APPLE_NOTARY_APPLE_ID`
- `APPLE_NOTARY_TEAM_ID`
- `APPLE_NOTARY_APP_PASSWORD`
- `APPLE_BUILD_KEYCHAIN_PASSWORD`

Ornek release:

```bash
git tag v1.1.10
git push origin v1.1.10
```

Not:

- tag her zaman merge edilmis `main` commit'i uzerinde olusturulmali
- GitHub Release notlari `CHANGELOG.md` kaynagindan otomatik uretilir

## Kullanım

Sürüm bilgisi:

- `VERSION` dosyasından okunur
- uygulama içinde `Hakkinda` ile görüntülenir
- surum degisiklikleri `CHANGELOG.md` içinde tutulur
- GitHub Release notlari `scripts/generate_release_notes.py` ile `CHANGELOG.md` kaynagindan otomatik uretilir

1. Mikrofon/Çıkış Aygıt Kimliği kutularını boş bırakabilirsiniz (varsayılan cihaz).
2. `Mikrofon/Ses Kartı Testi (5 sn)` butonuyla önce test yapın.
3. `Müzik Dosyası Seç` ile backing track seçin (`.wav/.aiff/.flac`) veya boş bırakıp sadece mikrofon kaydı alın.
4. `Kazanç / Güçlendirme / High-Pass / Bas / Presence / Tiz / Distorsiyon` ayarlarını yapın.
5. `Arka Plan Seviye / Vokal Seviye / Gürültü Azaltma / Noise Gate Eşigi / Canli Monitor Seviye / Kompresor / Limiter / Hız / Çıkış Kazancı` ayarlarını yapın.
6. `Çıkış Klasörü` seçin. Varsayılan olarak Masaüstü kullanılır.
7. İsterseniz `Oturum Modu` ile tarihli veya isimli alt klasör kullanın.
8. `MP3 Kalitesi` ve `WAV Export` modunu seçin.
9. `Kayıt Sınırı (1 veya 2 saat)` seçin.
10. `Preset Adi` alanına isim verip farkli kurulumlar icin `Preset Kaydet / Yükle / Sil` kullanabilirsiniz.
11. `Kaydı Başlat ve MP3 Çıkar` butonuna basın.
   - Backing seçilmediyse `Sadece Mikrofon Süresi (sn)` ayarındaki süre kadar kayıt alınır.
   - Hızlı tek tuş için `Quick Kayıt (Preset, Sorusuz)` butonunu kullanabilirsiniz.
   - Gerekirse `Monitor Ac` ile canli dinleme yapabilirsiniz. Kulaklik kullanin.
   - `Guvenlik` satiri giris seviyesinin cok dusuk, uygun veya riskli oldugunu gosterir.
   - `Kayıt Durumu` panelinde geçen süre ve kalan süre canlı görünür.
   - Gerekirse `Kaydı Durdur ve Kaydet` ile o ana kadar alınan bölüm dışa aktarılır.
12. Kayıt bitince dosyalar seçtiğiniz klasöre veya seçtiğiniz oturum alt klasörüne yazılır:
   - `dosyaadi.mp3` (mix)
   - `dosyaadi_vocal.wav` (işlenmiş vokal/gitar kanalınız)
   - isteğe bağlı `dosyaadi_mix.wav` (tam mix WAV)
   - `dosyaadi_device_test.wav` (test kaydı)
   - `session_summary.json` (oturum ayarlari ve uretilen dosyalar)
13. `Son Ciktilar` panelinden son dosyayi Finder'da gosterebilir veya aktif cikis/oturum klasorunu acabilirsiniz.
14. `Son Oturumu Yükle` ile son kullanilan oturum klasoru ve preset baglamini geri cagirabilirsiniz.

## Notlar

- Kayıt sırasında kulaklık kullanmanız geri besleme (feedback) riskini azaltır.
- `ffmpeg bulunamadı` hatası alırsanız `brew install ffmpeg` komutunu tekrar çalıştırın.
- Windows'ta da çalışır; `ffmpeg` ve Python kurulumu gerekir.
- Önemli: Program soru sorarken terminale `git ...` gibi komutlar yapıştırmayın. Önce `Ctrl + C` ile programdan çıkın, sonra komutları çalıştırın.
