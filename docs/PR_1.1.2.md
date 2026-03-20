# PR 1.1.2

## Title

Prepare 1.1.2 release

## Summary

- bump version metadata to `1.1.2`
- add `1.1.2` release notes and update release prep docs
- improve launch flow with venv compatibility recovery and dependency stamp caching
- add quick launch / quick record shortcut flow
- add built-in presets and saved CLI settings flow
- include app version metadata in macOS bundle packaging

## Validation

- `PYTHONPYCACHEPREFIX=/tmp/pycache python3 -m py_compile app.py cli_app.py`
- verified release branch push: `codex/release-prep-1-1-0`
- verified tag push: `v1.1.2`

## Notes

- local `.venv` changes were intentionally excluded from the release commit
