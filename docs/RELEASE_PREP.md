# Release Prep

Bu not, Git tarafini temiz tutup yeni surumu yayinlamadan once hangi adimlarin tamamlanacagini netlestirir.

## Hedef Surum

- `VERSION`: `1.1.2`
- Changelog: `CHANGELOG.md`
- Release body: `docs/RELEASE_BODY.md`

## Git Temizlik Kurallari

Takip edilmemesi gereken yerel dosyalar:

- `.gui_saved_preset.json`
- `.last_preset.json`
- `.last_session.json`
- `.pyinstaller-cache/`
- `cleanup_*/`

Not:

- `.venv/` su anda repoda tarihsel olarak izlenmis gorunuyor. Bu surumde geriye donuk repo cerrahisi yapilmadi.
- Release commit'inde ortam/artifact kaynakli `.venv` degisiklikleri dahil edilmemeli.

## Release Commit Icin Dahil Edilecek Ana Dosyalar

- `app.py`
- `README.md`
- `VERSION`
- `CHANGELOG.md`
- `docs/RELEASE_BODY.md`
- `docs/MACOS_RELEASE_CHECKLIST.md`
- `docs/PRODUCT_ROADMAP.md`
- `.github/workflows/release-macos.yml`
- `release_macos_desktop.sh`
- `notarize_macos_app.sh`
- `scripts/generate_release_notes.py`
- `scripts/tag_release.py`

## Onerilen Akis

1. Uygulama testlerini tamamla.
2. `python scripts/generate_release_notes.py` ile `docs/RELEASE_BODY.md` dosyasini guncelle.
3. Release hazirlik PR'ini `main` branch'ine merge et.
4. Temiz bir `main` checkout'u al ve `git pull --ff-only origin main` calistir.
5. `python3 scripts/tag_release.py` ile `VERSION` tabanli tag'i mevcut `main` commit'i uzerinde olustur.
6. `git push origin v1.1.2`

## Tek Akis Kurali

- Release tag'i her zaman merge edilmis `main` commit'i uzerinde olusmali.
- Tag, release hazirlik branch'inde degil, `main` uzerinde acilmalidir.
- `VERSION`, `CHANGELOG.md` ve `docs/RELEASE_BODY.md` ayni surumu gostermelidir.
- GitHub Release body workflow tarafinda `docs/RELEASE_BODY.md` uzerinden otomatik yayinlanir.

## Notarized macOS Release

Gercek notarized yayin icin ayrica:

- Apple `Developer ID Application` sertifikasi
- notarytool credentials
- GitHub secrets

gereklidir.
