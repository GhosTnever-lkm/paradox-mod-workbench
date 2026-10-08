from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .diagnostics import compare_mods, dependency_findings, inspect_mod
from .ingest import DEFAULT_MAX_UNPACKED, load_mod
from .report import to_json, to_sarif, to_text, write_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pmw", description="Compare and diagnose Paradox mod folders and ZIPs.")
    commands = parser.add_subparsers(dest="command", required=True)
    scan = commands.add_parser("scan", help="Inspect one or more mods and compare their overridden files.")
    scan.add_argument("sources", nargs="+", help="Mod folders or .zip archives to inspect.")
    scan.add_argument("--format", choices=("text", "json", "sarif"), default="text")
    scan.add_argument("--output", help="Write report to a file instead of stdout.")
    scan.add_argument("--max-unpacked-mb", type=int, default=500, help="Maximum total expanded size for each archive (default: 500 MiB).")
    scan.add_argument("--fail-on", choices=("error", "warning", "never"), default="error", help="Exit non-zero at or above this severity (default: error).")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    missing = [source for source in args.sources if not Path(source).exists()]
    if missing:
        for source in missing:
            print(f"pmw: source does not exist: {source}", file=sys.stderr)
        return 2
    if args.max_unpacked_mb < 1:
        print("pmw: --max-unpacked-mb must be at least 1", file=sys.stderr)
        return 2
    limit = args.max_unpacked_mb * 1024 * 1024
    mods = [load_mod(source, max_unpacked=limit) for source in args.sources]
    findings = [finding for mod in mods for finding in inspect_mod(mod)]
    findings.extend(compare_mods(mods))
    findings.extend(dependency_findings(mods))
    renderer = {"text": to_text, "json": to_json, "sarif": to_sarif}[args.format]
    write_report(renderer(mods, findings), args.output)
    if args.fail_on == "never":
        return 0
    order = {"info": 0, "warning": 1, "error": 2}
    threshold = 2 if args.fail_on == "error" else 1
    return 1 if any(order[item.severity] >= threshold for item in findings) else 0
