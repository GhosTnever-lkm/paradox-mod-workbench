# Paradox Mod Workbench

**A local-first quality and conflict workbench for Paradox mods.** Compare an
entire mod pack, map descriptor dependencies, surface file overrides, inspect
localization tables and Clausewitz scripts, and export machine-readable findings
from one command.

The first release is being built around three practical jobs:

- compare folders and ZIPs using normalized mod-relative paths, including ZIPs
  wrapped in a single enclosing folder;
- flag meaningful file overrides while ignoring repository and Workshop noise;
- report duplicate localization keys and unbalanced Clausewitz script braces;
- read `descriptor.mod` dependencies, report dependencies outside the supplied
  scan, and detect cycles among supplied mods.

The scanner is read-only. It never edits a mod or uploads its contents.

## Install

```console
python -m pip install git+https://github.com/GhosTnever-lkm/paradox-mod-workbench.git
```

## Quick start

```console
pmw scan "mods/Red Dawn" "mods/Red Dawn patch.zip" --format text
pmw scan "mods/Red Dawn" "mods/compatibility patch" --format json --output report.json
pmw scan "mods/Red Dawn" --format sarif --output results.sarif
```

Use paths to mod directories or `.zip` archives. Diagnostics are calculated
without launching the game. Dependency names are matched against the names of
the supplied folders or ZIP files; a dependency outside the scan is reported as
unchecked, not declared missing from disk.

## Safety and limits

- ZIP entries with absolute paths, drive prefixes, or `..` segments are skipped
  with a finding.
- The default total uncompressed archive limit is 500 MiB.
- Only relative paths and compact finding messages enter reports; file contents
  are not copied into the output.
- `--format json` and `--format sarif` are suitable for automation.

## Roadmap

1. Mod pack comparison, safe ZIP ingestion, localization and script diagnostics.
2. Descriptor dependency graph and load-order conflict explanations.
3. Cross-file reference checks and HTML report with filters.
4. Optional adapters for ModRelease Studio, Mod Conflict Map, and localization
   guard tools.

## Development

```console
python -m unittest discover -s tests -v
```

MIT licensed. See [LICENSE](LICENSE) and [SECURITY.md](SECURITY.md).

## Support / Pro Version

The core tool is free and open source. Optional paid editions may be offered
after a stable release; no paid edition is required to use this repository.
You can support development through [Buy Me a Coffee](https://buymeacoffee.com/azizazimov8)
or [Boosty](https://boosty.to/azizazim).
