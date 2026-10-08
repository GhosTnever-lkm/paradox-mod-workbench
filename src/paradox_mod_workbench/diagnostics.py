from __future__ import annotations

import csv
import re
from collections import defaultdict

from .model import Finding, ModInput

SCRIPT_SUFFIXES = {"txt", "gui"}


def _localization_findings(mod: ModInput, path: str, data: bytes) -> list[Finding]:
    findings: list[Finding] = []
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return [Finding("LOCALIZATION_ENCODING", "warning", "Localization file is not valid UTF-8; key checks were skipped.", mod.name, path)]
    keys: dict[str, int] = {}
    clausewitz_yml = path.casefold().endswith((".yml", ".yaml"))
    for line_no, line in enumerate(text.splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if clausewitz_yml:
            match = re.match(r"^\s*([A-Za-z0-9_.-]+)\s*:\s*\d+\s*\"", line)
            if not match:
                continue
            key = match.group(1)
        else:
            try:
                row = next(csv.reader([line], delimiter=";", quotechar='"', skipinitialspace=True))
            except (csv.Error, StopIteration):
                findings.append(Finding("LOCALIZATION_ROW_INVALID", "warning", "Could not parse this localization row.", mod.name, path, line_no))
                continue
            if not row or not row[0].strip():
                continue
            key = row[0].strip()
        if not key:
            findings.append(Finding("LOCALIZATION_ROW_INVALID", "warning", "Could not parse this localization row.", mod.name, path, line_no))
            continue
        if key in keys:
            findings.append(Finding("DUPLICATE_LOCALIZATION_KEY", "warning", f"Localization key {key!r} is repeated (first defined on line {keys[key]}).", mod.name, path, line_no))
        else:
            keys[key] = line_no
    return findings


def _script_findings(mod: ModInput, path: str, data: bytes) -> list[Finding]:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return []
    depth = 0
    in_quote = False
    escaped = False
    findings: list[Finding] = []
    for line_no, line in enumerate(text.splitlines(), 1):
        in_comment = False
        for char in line:
            if in_comment:
                break
            if in_quote:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_quote = False
            elif char == '"':
                in_quote = True
            elif char == "#":
                in_comment = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth < 0:
                    findings.append(Finding("SCRIPT_EXTRA_CLOSING_BRACE", "error", "Closing brace has no matching opening brace.", mod.name, path, line_no))
                    depth = 0
    if in_quote:
        findings.append(Finding("SCRIPT_UNCLOSED_QUOTE", "error", "A quoted string is not closed before end of file.", mod.name, path))
    if depth:
        findings.append(Finding("SCRIPT_UNCLOSED_BRACE", "error", f"{depth} opening brace(s) are not closed.", mod.name, path))
    return findings


def inspect_mod(mod: ModInput) -> list[Finding]:
    findings = list(mod.findings)
    for item in mod.files:
        folded = item.path.casefold()
        if folded.startswith("localisation/") or folded.startswith("localization/"):
            if folded.endswith(".yml") or folded.endswith(".yaml") or folded.endswith(".csv"):
                findings.extend(_localization_findings(mod, item.path, item.data))
        elif folded.startswith(("common/", "events/", "decisions/", "history/", "interface/")):
            if "." in item.path and item.path.rsplit(".", 1)[-1].casefold() in SCRIPT_SUFFIXES:
                findings.extend(_script_findings(mod, item.path, item.data))
    return findings


def compare_mods(mods: list[ModInput]) -> list[Finding]:
    by_path: dict[str, list[tuple[str, str]]] = defaultdict(list)
    findings: list[Finding] = []
    for mod in mods:
        for item in mod.files:
            if item.path.casefold() == "descriptor.mod":
                continue
            by_path[item.path.casefold()].append((mod.name, item.path))
    for entries in by_path.values():
        if len({(name, path.casefold()) for name, path in entries}) < 2:
            continue
        display_paths = sorted({path for _, path in entries}, key=str.casefold)
        findings.append(Finding("FILE_OVERRIDE", "info", f"This path exists in multiple mods: {', '.join(name for name, _ in entries)}.", "mod pack", display_paths[0]))
    return findings


def dependency_findings(mods: list[ModInput]) -> list[Finding]:
    """Check declared dependencies and cycles among the supplied mod descriptors."""
    findings: list[Finding] = []
    by_name: dict[str, ModInput] = {}
    for mod in mods:
        by_name.setdefault(mod.name.casefold(), mod)

    graph: dict[str, list[str]] = {name: [] for name in by_name}
    for mod in mods:
        for dependency in mod.dependencies or []:
            key = dependency.casefold()
            if key not in by_name:
                findings.append(Finding(
                    "DEPENDENCY_NOT_SCANNED", "warning",
                    f"Declared dependency {dependency!r} is not among the supplied mods; availability was not checked.",
                    mod.name, "descriptor.mod",
                ))
            elif key != mod.name.casefold():
                graph[mod.name.casefold()].append(key)

    visited: set[str] = set()
    active: set[str] = set()
    cycles: set[tuple[str, ...]] = set()

    def visit(node: str, trail: list[str]) -> None:
        if node in active:
            cycle = trail[trail.index(node):] + [node]
            canonical = tuple(sorted(set(cycle)))
            if canonical not in cycles:
                cycles.add(canonical)
                labels = [by_name[item].name for item in cycle]
                findings.append(Finding("DEPENDENCY_CYCLE", "error", "Dependency cycle: " + " -> ".join(labels) + ".", "mod pack"))
            return
        if node in visited:
            return
        active.add(node)
        for child in graph.get(node, []):
            visit(child, trail + [node])
        active.remove(node)
        visited.add(node)

    for node in graph:
        visit(node, [])
    return findings
