# Release Prep

Bu not, Git tarafini temiz tutup yeni surumu yayinlamadan once hangi adimlarin tamamlanacagini netlestirir.

## Hedef Surum

- `VERSION`: `1.1.0`
- Changelog: `CHANGELOG.md`
- Release notes: `docs/RELEASE_NOTES_1.1.0.md`

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
- `docs/RELEASE_NOTES_1.1.0.md`
- `docs/MACOS_RELEASE_CHECKLIST.md`
- `docs/PRODUCT_ROADMAP.md`
- `.github/workflows/release-macos.yml`
- `release_macos_desktop.sh`
- `notarize_macos_app.sh`

## Onerilen Akis

1. Uygulama testlerini tamamla.
2. `git diff` ile yalnizca release'e girecek dosyalari gozden gecir.
3. Release commit'ini olustur.
4. `git tag v1.1.0`
5. `git push origin <branch>`
6. `git push origin v1.1.0`

## Notarized macOS Release

Gercek notarized yayin icin ayrica:

- Apple `Developer ID Application` sertifikasi
- notarytool credentials
- GitHub secrets

gereklidir.
