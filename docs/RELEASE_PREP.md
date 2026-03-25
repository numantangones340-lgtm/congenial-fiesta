# Release Prep

Bu not, Git tarafini temiz tutup yeni surumu yayinlamadan once hangi adimlarin tamamlanacagini netlestirir.

## Hedef Surum

- `VERSION`: `1.1.7`
- Changelog: `CHANGELOG.md`
- Release notes kaynagi: `CHANGELOG.md`
- Release notes uretimi: `python scripts/generate_release_notes.py --output dist/release-notes.md`

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
- `scripts/generate_release_notes.py`
- `docs/RELEASE_PREP.md`
- `docs/ROADMAP_1.1.3.md`
- `.github/workflows/release.yml`
- `build_macos_app.sh`
- `sign_macos_app.sh`
- `notarize_macos_app.sh`
- `package_macos_release.sh`
- `scripts/generate_release_notes.py`
- `scripts/tag_release.py`

## Onerilen Akis

1. Uygulama testlerini tamamla.
2. `git diff` ile yalnizca release'e girecek dosyalari gozden gecir.
3. Sadece hedef dosyalari `git add` ile secerek stage et:
   `git add VERSION CHANGELOG.md README.md app.py cli_app.py sign_macos_app.sh notarize_macos_app.sh scripts/ tests/ .github/workflows/release.yml .github/workflows/static.yml docs/RELEASE_PREP.md`
4. `git status --short` ile `.venv/` degisikliklerinin stage disinda kaldigini dogrula.
5. Release commit'ini olustur.
6. `git tag v1.1.7`
7. `git push origin <branch>`
8. `git push origin v1.1.7`

## Tek Akis Kurali

- Release tag'i her zaman merge edilmis `main` commit'i uzerinde olusmali.
- Tag, release hazirlik branch'inde degil, `main` uzerinde acilmalidir.
- `VERSION` ve `CHANGELOG.md` ayni surumu gostermelidir.
- Daha once olusturulmus `v1.1.4` etiketi baska bir commit'e baktigi icin bugunku `main` icin yeniden kullanilmamalidir.
- GitHub Release body workflow tarafinda `CHANGELOG.md` kaynagindan otomatik uretilir.

## Notarized macOS Release

Gercek notarized yayin icin ayrica:

- Apple `Developer ID Application` sertifikasi
- notarytool credentials
- GitHub secrets
- repo icindeki `sign_macos_app.sh` ve `notarize_macos_app.sh` scriptleri

gereklidir.
