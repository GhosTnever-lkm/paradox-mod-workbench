# Changelog

## 0.2.1 - 2026-10-08

- Clarify current scanner coverage, install requirements, and report behavior.
- Correct roadmap to list only work that has not shipped yet.

## 0.2.0 - 2026-10-08

- Read `descriptor.mod` dependency and replace-path declarations.
- Report dependencies outside the scanned set and cycles among scanned mods.
- Fix ZIP wrapper normalization for standard Clausewitz root folders.
- Parse repeated keys in Clausewitz `.yml` localization files correctly.
- Avoid including absolute local paths in JSON reports.
- Add CI coverage for Python 3.11, 3.12, and 3.13.

## 0.1.0 - unreleased

- Initial local-first scanner for folders and ZIP archives.
- Detect duplicate localization keys, script brace errors, and file overrides.
