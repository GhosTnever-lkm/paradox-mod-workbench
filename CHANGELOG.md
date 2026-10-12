# Changelog

## 0.2.6 - 2026-10-13

- Match declared dependencies against descriptor `name` values, even when they differ from the selected folder name.
- Read dependency and `replace_path` metadata from legacy `.mod` sidecars and report the declared name in JSON.
- Add regression coverage for modern descriptors and the legacy `.mod` plus content-folder layout.

## 0.2.5 - 2026-10-12

- Detect file overrides between distinct sources even when their displayed mod names are identical; disambiguate those sources in the finding.
- Add a regression test for same-named folders.

## 0.2.4 - 2026-10-12

- Report the current package version in JSON and SARIF metadata instead of the stale 0.2.1 JSON value.
- Add regression checks for both machine-readable report versions.

## 0.2.3 - 2026-10-12

- Report duplicate ZIP paths after slash and case normalization; retain the first entry so ordering ambiguity is visible instead of silently overwriting it.
- Ignore additional repository, Workshop, and OS metadata files consistently for folder and ZIP scans.
- Synchronize the package and module version to 0.2.3.

## 0.2.2 - 2026-10-11

- CI now also runs the test suite on Windows (windows-latest), not only Ubuntu.


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
