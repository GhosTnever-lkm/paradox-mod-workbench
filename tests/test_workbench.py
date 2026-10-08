from __future__ import annotations

import json
import tempfile
import unittest
import zipfile
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from paradox_mod_workbench.cli import main
from paradox_mod_workbench.diagnostics import compare_mods, dependency_findings, inspect_mod
from paradox_mod_workbench.ingest import load_mod


class IngestTests(unittest.TestCase):
    def test_wrapper_folder_does_not_hide_overlap(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / "wrapped.zip"
            with zipfile.ZipFile(archive, "w") as zipped:
                zipped.writestr("ModA/common/ideas/x.txt", "idea = { }\n")
            folder = root / "ModB"
            (folder / "common/ideas").mkdir(parents=True)
            (folder / "common/ideas/x.txt").write_text("idea = { }\n", encoding="utf-8")
            first = load_mod(archive)
            second = load_mod(folder)
            self.assertEqual(first.files[0].path, "common/ideas/x.txt")
            overlaps = compare_mods([first, second])
            self.assertEqual(len(overlaps), 1)
            self.assertEqual(overlaps[0].code, "FILE_OVERRIDE")

    def test_standard_top_level_folder_is_not_stripped_as_wrapper(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "common-only.zip"
            with zipfile.ZipFile(archive, "w") as zipped:
                zipped.writestr("common/ideas/x.txt", "idea = { }\n")
            self.assertEqual(load_mod(archive).files[0].path, "common/ideas/x.txt")

    def test_unsafe_zip_entries_are_reported_and_skipped(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "unsafe.zip"
            with zipfile.ZipFile(archive, "w") as zipped:
                zipped.writestr("../outside.txt", "unsafe")
                zipped.writestr("common/ideas/ok.txt", "idea = { }\n")
            mod = load_mod(archive)
            self.assertIn("UNSAFE_ARCHIVE_PATH", [finding.code for finding in mod.findings])
            self.assertEqual([item.path for item in mod.files], ["common/ideas/ok.txt"])

    def test_service_files_do_not_create_false_overrides(self):
        with tempfile.TemporaryDirectory() as directory:
            mods = []
            for name in ("a", "b"):
                path = Path(directory) / name
                path.mkdir()
                (path / "thumbnail.png").write_bytes(b"image")
                mods.append(load_mod(path))
            self.assertEqual(compare_mods(mods), [])


class DiagnosticsTests(unittest.TestCase):
    def test_duplicate_localization_keys_are_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "mod"
            localization = path / "localisation"
            localization.mkdir(parents=True)
            (localization / "test_l_english.yml").write_text('l_english:\n key_one:0 "First"\n key_one:0 "Second"\n', encoding="utf-8")
            mod = load_mod(path)
            findings = inspect_mod(mod)
            self.assertIn("DUPLICATE_LOCALIZATION_KEY", [finding.code for finding in findings])

    def test_unbalanced_script_brace_reports_line(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "mod"
            common = path / "common" / "ideas"
            common.mkdir(parents=True)
            (common / "broken.txt").write_text('idea = {\n name = "x"\n', encoding="utf-8")
            findings = inspect_mod(load_mod(path))
            match = next(item for item in findings if item.code == "SCRIPT_UNCLOSED_BRACE")
            self.assertEqual(match.path, "common/ideas/broken.txt")

    def test_dependency_cycle_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            mods = []
            for name, dependency in (("A", "B"), ("B", "A")):
                path = Path(directory) / name
                path.mkdir()
                (path / "descriptor.mod").write_text(f'dependencies = {{ "{dependency}" }}\n', encoding="utf-8")
                mods.append(load_mod(path))
            findings = dependency_findings(mods)
            self.assertEqual([finding.code for finding in findings], ["DEPENDENCY_CYCLE"])

    def test_external_dependency_is_reported_as_unchecked(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "A"
            path.mkdir()
            (path / "descriptor.mod").write_text('dependencies = { "External Mod" }\n', encoding="utf-8")
            findings = dependency_findings([load_mod(path)])
            self.assertEqual(findings[0].code, "DEPENDENCY_NOT_SCANNED")

    def test_descriptor_block_and_scalar_replace_paths_are_read(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "A"
            path.mkdir()
            (path / "descriptor.mod").write_text('dependencies = { "B"\n "C" }\nreplace_path = "common/ideas"\n', encoding="utf-8")
            mod = load_mod(path)
            self.assertEqual(mod.dependencies, ["B", "C"])
            self.assertEqual(mod.replace_paths, ["common/ideas"])


class CliTests(unittest.TestCase):
    def test_json_report_has_summary_and_readable_output(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "mod"
            path.mkdir()
            report = Path(directory) / "report.json"
            result = main(["scan", str(path), "--format", "json", "--output", str(report)])
            self.assertIn(result, (0, 1))
            rendered = report.read_text(encoding="utf-8")
            payload = json.loads(rendered)
            self.assertIn("findings", payload)
            self.assertIn("summary", payload)
            self.assertNotIn(str(Path(directory).resolve()), rendered)


if __name__ == "__main__":
    unittest.main()
