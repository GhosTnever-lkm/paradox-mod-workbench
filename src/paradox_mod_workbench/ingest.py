from __future__ import annotations

import os
import re
import zipfile
from pathlib import Path, PurePosixPath

from .model import Finding, ModFile, ModInput

DEFAULT_MAX_UNPACKED = 500 * 1024 * 1024
IGNORED_PARTS = {".git", ".hg", ".svn", "__macosx", "node_modules"}
IGNORED_NAMES = {".ds_store", "thumbs.db", "thumbnail.png", "readme.md", "readme.txt"}
CLAUSEWITZ_ROOTS = {
    "common", "events", "decisions", "history", "interface", "localisation",
    "localization", "gfx", "sound", "music", "map", "portraits", "musicplayer",
    "fonts", "dlc", "scripted_effects", "scripted_guis", "scripted_triggers",
}


def _descriptor_values(raw: dict[str, bytes]) -> tuple[list[str], list[str]]:
    """Read dependency and replace_path declarations from descriptor.mod, when present."""
    data = raw.get("descriptor.mod")
    if data is None:
        return [], []
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return [], []

    def values(key: str) -> list[str]:
        match = re.search(rf"(?ms)^\s*{re.escape(key)}\s*=\s*(\{{.*?\}}|[^\r\n#]+)", text)
        if not match:
            return []
        body = re.sub(r"(?m)#.*$", "", match.group(1))
        found: list[str] = []
        for quoted, single_quoted, bare in re.findall(r'"([^"]+)"|\'([^\']+)\'|([^\s{}]+)', body):
            value = quoted or single_quoted or bare
            if value:
                found.append(value)
        return found

    return values("dependencies"), values("replace_path")


def _safe_archive_path(name: str) -> str | None:
    normalized = name.replace("\\", "/")
    if normalized.startswith("/") or re.match(r"^[a-zA-Z]:", normalized):
        return None
    path = PurePosixPath(normalized)
    if any(part in {"..", ""} for part in path.parts) or path.is_absolute():
        return None
    return path.as_posix()


def _service_file(path: str) -> bool:
    parts = path.casefold().split("/")
    return any(part in IGNORED_PARTS for part in parts) or parts[-1] in IGNORED_NAMES or parts[-1].endswith((".bak", ".tmp", ".swp"))


def _strip_wrapper(paths: dict[str, bytes]) -> dict[str, bytes]:
    """Strip one enclosing folder only when it is unambiguously a wrapper."""
    if "descriptor.mod" in paths or not paths:
        return paths
    first_parts = {path.split("/", 1)[0] for path in paths}
    if len(first_parts) != 1:
        return paths
    root = next(iter(first_parts))
    # A mod may consist solely of a standard game folder, e.g. common/.
    if root.casefold() in CLAUSEWITZ_ROOTS:
        return paths
    stripped = {path[len(root) + 1:]: data for path, data in paths.items() if path.startswith(root + "/")}
    return stripped or paths


def load_mod(source: str | os.PathLike[str], max_unpacked: int = DEFAULT_MAX_UNPACKED) -> ModInput:
    location = Path(source)
    name = location.stem if location.is_file() else location.name
    findings: list[Finding] = []
    raw: dict[str, bytes] = {}
    if location.is_dir():
        for path in location.rglob("*"):
            if not path.is_file():
                continue
            relative = path.relative_to(location).as_posix()
            if _service_file(relative):
                continue
            try:
                raw[relative] = path.read_bytes()
            except OSError as exc:
                findings.append(Finding("FILE_READ_ERROR", "warning", f"Could not read file ({exc.__class__.__name__}).", name, relative))
    elif location.is_file() and location.suffix.casefold() == ".zip":
        try:
            with zipfile.ZipFile(location) as archive:
                total = 0
                safe_entries: list[tuple[zipfile.ZipInfo, str]] = []
                for info in archive.infolist():
                    if info.is_dir():
                        continue
                    safe_path = _safe_archive_path(info.filename)
                    if safe_path is None:
                        findings.append(Finding("UNSAFE_ARCHIVE_PATH", "error", "Archive entry has an absolute or parent-traversal path and was skipped.", name))
                        continue
                    if _service_file(safe_path):
                        continue
                    total += info.file_size
                    if total > max_unpacked:
                        findings.append(Finding("ARCHIVE_SIZE_LIMIT", "error", f"Archive exceeds the {max_unpacked} byte uncompressed limit.", name))
                        break
                    safe_entries.append((info, safe_path))
                if total <= max_unpacked:
                    for info, safe_path in safe_entries:
                        try:
                            raw[safe_path] = archive.read(info)
                        except (OSError, zipfile.BadZipFile, RuntimeError):
                            findings.append(Finding("ARCHIVE_ENTRY_READ_ERROR", "error", "Could not read an archive entry.", name, safe_path))
        except (OSError, zipfile.BadZipFile):
            findings.append(Finding("INVALID_ZIP", "error", "The selected file is not a readable ZIP archive.", name))
    else:
        findings.append(Finding("UNSUPPORTED_SOURCE", "error", "Choose a mod folder or a ZIP archive.", name))

    raw = _strip_wrapper(raw) if location.is_file() else raw
    if location.is_dir() and "descriptor.mod" not in raw:
        # Normalize the common legacy layout: mod/<name>.mod + mod/<name>/...
        descriptors = list(location.glob("*.mod"))
        children = [child for child in location.iterdir() if child.is_dir() and child.name.casefold() not in IGNORED_PARTS]
        if len(descriptors) == 1 and len(children) == 1:
            child_prefix = children[0].name + "/"
            if any(path.startswith(child_prefix) for path in raw):
                raw = {path[len(child_prefix):]: data for path, data in raw.items() if path.startswith(child_prefix)}
                name = descriptors[0].stem
    if not raw and not any(f.code in {"INVALID_ZIP", "UNSUPPORTED_SOURCE", "ARCHIVE_SIZE_LIMIT"} for f in findings):
        findings.append(Finding("EMPTY_MOD", "warning", "No readable mod files were found.", name))
    dependencies, replace_paths = _descriptor_values(raw)
    files = [ModFile(name, path, data) for path, data in sorted(raw.items(), key=lambda item: item[0].casefold())]
    return ModInput(name=name, source=str(location), files=files, findings=findings,
                    dependencies=dependencies, replace_paths=replace_paths)
