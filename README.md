# Paradox Mod Workbench

**A local-first quality and conflict workbench for Paradox mods.** Compare an entire mod pack, map descriptor dependencies, surface file overrides, inspect localization tables and Clausewitz scripts, and export machine-readable findings from one command.

## What it checks

- Compare folders and ZIP archives using normalized mod-relative paths, including archives wrapped in one enclosing directory.
- Identify meaningful file overrides while ignoring repository and Workshop noise.
- Report duplicate keys in Clausewitz `.yml` localization and unbalanced braces or quotes in `.txt` and `.gui` scripts.
- Read `descriptor.mod` dependencies and `replace_path` declarations, report dependencies outside the supplied scan as unchecked, and detect cycles among supplied mods.
- Emit text, JSON, or SARIF reports for local review and CI automation.

The scanner is read-only. It never edits a mod or uploads its contents.

## Install

Requires Python 3.11 or newer.

```console
python -m pip install git+https://github.com/GhosTnever-lkm/paradox-mod-workbench.git
```

## Quick start

```console
# Compare a mod with a compatibility patch
pmw scan "mods/Red Dawn" "mods/Red Dawn patch.zip" --format text

# Save a JSON report
pmw scan "mods/Red Dawn" "mods/compatibility patch" --format json --output report.json

# Produce SARIF for code-scanning tools
pmw scan "mods/Red Dawn" --format sarif --output results.sarif
```

Pass one or more mod directories or `.zip` archives. Diagnostics are calculated without launching the game. Dependency names are matched against the names of supplied folders or ZIP files; a dependency outside the scan is reported as **unchecked**, not declared missing from disk.

## Safety and limits

- ZIP entries with absolute paths, drive prefixes, or `..` segments are skipped with a finding.
- The default total uncompressed archive limit is 500 MiB.
- Reports contain relative paths and compact finding messages; file contents are not copied into output.
- `--format json` and `--format sarif` are suitable for automation.

## Roadmap

1. Improve load-order explanations using game-specific rules and explicit ordering metadata.
2. Add cross-file reference checks for common Clausewitz definitions.
3. Build an optional HTML report with filters and a dependency graph.
4. Add adapters for ModRelease Studio, Mod Conflict Map, and localization guard tools.

## Development

```console
python -m unittest discover -s tests -v
```

The GitHub Actions workflow runs the test suite and CLI smoke check on Python 3.11, 3.12, and 3.13.

MIT licensed. See [LICENSE](LICENSE) and [SECURITY.md](SECURITY.md).

## Support / Pro Version

The core tool is free and open source. Optional paid editions may be offered after a stable release; no paid edition is required to use this repository. You can support development through [Buy Me a Coffee](https://buymeacoffee.com/azizazimov8) or [Boosty](https://boosty.to/azizazim).
