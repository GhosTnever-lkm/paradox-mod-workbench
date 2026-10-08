from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

Severity = Literal["error", "warning", "info"]


@dataclass(frozen=True, slots=True)
class Finding:
    code: str
    severity: Severity
    message: str
    mod: str
    path: str = ""
    line: int | None = None

    def to_dict(self) -> dict[str, str | int | None]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ModFile:
    mod: str
    path: str
    data: bytes


@dataclass(slots=True)
class ModInput:
    name: str
    source: str
    files: list[ModFile]
    findings: list[Finding]
    dependencies: list[str] | None = None
    replace_paths: list[str] | None = None
