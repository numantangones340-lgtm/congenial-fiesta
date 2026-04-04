# Contributing

Bu repoya katki vermek isteyenler icin en kisa akisi burada topladik.

## En Kisa Katki Akisi

1. Once mevcut belgeleri okuyun:
   - `README.md`
   - `docs/FIRST_RUN_GUIDE.md`
   - `docs/SUPPORT_FAQ.md`
2. Gerekirse issue acin:
   - hata icin `bug report`
   - iyilestirme icin `feature request`
3. Yeni bir branch acin.
4. Degisikligi yapin.
5. Ilgili testleri calistirin.
6. Kisa ve net bir PR acin.

## Issue Acmadan Once

Asagidaki dosyalara bakmak cogu zaman soruyu hizla cevaplar:

- `docs/FIRST_RUN_GUIDE.md`
- `docs/SUPPORT_FAQ.md`
- `docs/MACOS_RELEASE_CHECKLIST.md`
- `docs/WINDOWS_RELEASE_CHECKLIST.md`

## Branch ve Commit

Onerilen branch mantigi:

- `fix/...`
- `feat/...`
- `docs/...`

Commit mesaji kisa ve acik olmali:

- `Fix packaged macOS microphone capture`
- `Add support FAQ page`
- `Clarify quick recording output names`

## Test ve Dogrulama

Degisiklige gore uygun olanlari calistirin:

```bash
python3 tests/smoke_test.py
.venv/bin/python -m unittest tests/test_release_pipeline_assets.py
```

Buyuk degisikliklerde:

```bash
python -m unittest discover -s tests -p "test_*.py"
```

## PR Hazirlarken

PR icinde su sorular net olmali:

- ne degisti
- neden degisti
- kullaniciya etkisi ne
- nasil test edildi

Repo icinde hazir PR sablonu vardir:

- `.github/pull_request_template.md`

## Release ile Ilgili Degisiklikler

Release veya indirme akisina dokunuyorsaniz su dosyalari birlikte gozden gecirin:

- `VERSION`
- `CHANGELOG.md`
- `docs/index.html`
- `docs/RELEASE_PREP.md`
- `docs/MACOS_RELEASE_CHECKLIST.md`
- `docs/WINDOWS_RELEASE_CHECKLIST.md`

## Guvenlik

Guvenlik acigi oldugunu dusunuyorsaniz public issue acmayin.

Once:

- `SECURITY.md`

dosyasini okuyun.
