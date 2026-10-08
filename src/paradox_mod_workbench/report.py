from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from .model import Finding, ModInput


def to_json(mods: list[ModInput], findings: list[Finding]) -> str:
    counts = Counter(item.severity for item in findings)
    payload: dict[str, Any] = {
        "tool": "Paradox Mod Workbench",
        "version": "0.2.0",
        # Do not leak local usernames or full directory layouts into reports.
        "mods": [{"name": mod.name, "source": Path(mod.source).name, "file_count": len(mod.files),
                  "dependencies": mod.dependencies or [], "replace_paths": mod.replace_paths or []} for mod in mods],
        "summary": {"errors": counts["error"], "warnings": counts["warning"], "info": counts["info"]},
        "findings": [item.to_dict() for item in findings],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def to_sarif(mods: list[ModInput], findings: list[Finding]) -> str:
    rules = {item.code: {"id": item.code, "shortDescription": {"text": item.code.replace("_", " ").title()}} for item in findings}
    results = []
    for item in findings:
        result: dict[str, Any] = {
            "ruleId": item.code,
            "level": {"error": "error", "warning": "warning", "info": "note"}[item.severity],
            "message": {"text": f"[{item.mod}] {item.message}"},
        }
        if item.path:
            region = {"startLine": item.line} if item.line else {}
            result["locations"] = [{"physicalLocation": {"artifactLocation": {"uri": item.path}, **({"region": region} if region else {})}}]
        results.append(result)
    return json.dumps({
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [{"tool": {"driver": {"name": "Paradox Mod Workbench", "rules": list(rules.values())}}, "results": results}],
    }, ensure_ascii=False, indent=2) + "\n"


def to_text(mods: list[ModInput], findings: list[Finding]) -> str:
    lines = [f"Paradox Mod Workbench — {len(mods)} mod(s), {sum(len(mod.files) for mod in mods)} file(s)"]
    if not findings:
        lines.append("No issues found.")
    for item in findings:
        location = f" ({item.path}" + (f":{item.line}" if item.line else "") + ")" if item.path else ""
        lines.append(f"{item.severity.upper():7} {item.code}: {item.mod}{location}: {item.message}")
    return "\n".join(lines) + "\n"


def write_report(content: str, output: str | None) -> None:
    if output:
        path = Path(output)
        path.write_text(content, encoding="utf-8")
    else:
        print(content, end="")
