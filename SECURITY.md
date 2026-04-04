# Security Policy

## Supported Versions

Su an aktif olarak desteklenen genel surum hatti:

| Version | Supported |
| ------- | --------- |
| 1.1.x   | yes       |
| < 1.1   | no        |

## Reporting a Vulnerability

Guvenlik acigi oldugunu dusunuyorsaniz, lutfen bunu public issue olarak paylasmayin.

Bunun yerine:

1. Sorunu kisa ve net sekilde yazin.
2. Etkilenen surumu belirtin.
3. Mumkunse tekrar uretim adimlarini ekleyin.
4. Etkisini aciklayin:
   - veri kaybi
   - yetkisiz erisim
   - dosya sistemi erisimi
   - komut calistirma
   - paket / release butunlugu

Guvenlik raporlarinda ozellikle su alanlar onemlidir:

- paketlenmis uygulama izinleri
- release dosyalari ve checksum butunlugu
- gizli anahtarlar / tokenlar
- dosya sistemi erisim izinleri

Rapor incelendikten sonra:

- sorun dogrulanirsa duzeltme planlanir
- etkilenen surum hatti belirlenir
- gerekirse yeni release cikarilir

Not:

- GitHub token, parola veya gizli bilgi iceren ekran goruntulerini public issue icine eklemeyin.
