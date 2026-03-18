# macOS Release Checklist

Bu proje icin profesyonel macOS dagitim hattinin minimum gereksinimleri:

## 1. Apple Developer Hazirlik

- Apple Developer hesabiniz aktif olmali.
- `Developer ID Application` sertifikasi olusturulmus olmali.
- Sertifika `.p12` olarak disari alinmali.
- Apple hesabinda `app-specific password` olusturulmali.
- Team ID not edilmeli.

## 2. Yerel Makinede Ilk Kurulum

Sertifika dogrulama:

```bash
security find-identity -v -p codesigning
```

Notary profile kaydetme:

```bash
xcrun notarytool store-credentials "AC_PROFILE" \
  --apple-id "you@example.com" \
  --team-id "TEAMID1234" \
  --password "app-specific-password"
```

Tam release komutu:

```bash
./release_macos_desktop.sh \
  "Developer ID Application: AD SOYAD (TEAMID1234)" \
  AC_PROFILE \
  TEAMID1234
```

Beklenen sonuc:

- `codesign --verify` basarili
- `notarytool submit --wait` basarili
- `stapler staple` basarili
- final zip hazir

## 3. GitHub Secrets

Asagidaki repository secrets eklenmeli:

- `APPLE_DEVELOPER_ID_APP_CERT_BASE64`
- `APPLE_DEVELOPER_ID_APP_CERT_PASSWORD`
- `APPLE_DEVELOPER_ID_APP_IDENTITY`
- `APPLE_NOTARY_APPLE_ID`
- `APPLE_NOTARY_TEAM_ID`
- `APPLE_NOTARY_APP_PASSWORD`
- `APPLE_BUILD_KEYCHAIN_PASSWORD`

`.p12` dosyasini base64'e cevirmek icin:

```bash
base64 -i developer-id-app.p12 | pbcopy
```

## 4. Release Oncesi Kontrol

- Uygulama GUI aciliyor mu
- Mikrofon test akisi geciyor mu
- MP3 export calisiyor mu
- `dist/GuitarAmpRecorder.app` aciliyor mu
- imzali build icin `spctl --assess --type execute` beklenen sonucu veriyor mu

## 5. Release Sonrasi Kontrol

- GitHub artifact yuklendi mi
- GitHub Release asset eklendi mi
- temiz bir macOS makinede indirip acilis testi yapildi mi
- Gatekeeper uyari davranisi dogrulandi mi
