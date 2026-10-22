from __future__ import annotations

import json
import tempfile
import unittest
import warnings
import zipfile
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from paradox_mod_workbench import __version__
from paradox_mod_workbench.cli import main
from paradox_mod_workbench.diagnostics import compare_mods, dependency_findings, inspect_mod
from paradox_mod_workbench.ingest import load_mod
from paradox_mod_workbench.model import Finding, ModInput
from paradox_mod_workbench.report import to_json, to_sarif, to_text


class IngestTests(unittest.TestCase):
    def test_folder_symlinks_are_skipped_without_reading_outside_files(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as external:
            root = Path(directory) / "mod"
            root.mkdir()
            (root / "common").mkdir()
            (root / "common" / "inside.txt").write_text("inside", encoding="utf-8")
            outside_file = Path(external) / "outside.txt"
            outside_file.write_text("outside-secret-fixture", encoding="utf-8")
            outside_dir = Path(external) / "linked-dir"
            outside_dir.mkdir()
            (outside_dir / "outside.txt").write_text("outside-directory-fixture", encoding="utf-8")
            try:
                (root / "linked-file.txt").symlink_to(outside_file)
                (root / "linked-dir").symlink_to(outside_dir, target_is_directory=True)
            except OSError as error:
                self.skipTest(f"symlinks are unavailable on this runner: {error}")

            mod = load_mod(root)

        self.assertEqual([item.path for item in mod.files], ["common/inside.txt"])
        self.assertEqual(
            {(item.code, item.path) for item in mod.findings if item.code == "LINK_SKIPPED"},
            {("LINK_SKIPPED", "linked-file.txt"), ("LINK_SKIPPED", "linked-dir")},
        )
        self.assertNotIn("outside-secret-fixture", repr(mod.files))
        self.assertNotIn("outside-directory-fixture", repr(mod.files))

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

    def test_duplicate_zip_path_is_reported_and_first_entry_is_kept(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "duplicate.zip"
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                with zipfile.ZipFile(archive, "w") as zipped:
                    zipped.writestr("common/ideas/x.txt", "first")
                    zipped.writestr("common/ideas/x.txt", "second")
            mod = load_mod(archive)
            self.assertEqual(len(mod.files), 1)
            self.assertEqual(mod.files[0].data, b"first")
            duplicate = next(item for item in mod.findings if item.code == "DUPLICATE_ARCHIVE_PATH")
            self.assertEqual(duplicate.severity, "warning")
            self.assertEqual(duplicate.path, "common/ideas/x.txt")

    def test_case_only_zip_paths_are_reported_as_a_collision(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "case-collision.zip"
            with zipfile.ZipFile(archive, "w") as zipped:
                zipped.writestr("events/Foo.txt", "first")
                zipped.writestr("events/foo.txt", "second")
            mod = load_mod(archive)
            self.assertEqual([item.path for item in mod.files], ["events/Foo.txt"])
            duplicate = next(item for item in mod.findings if item.code == "DUPLICATE_ARCHIVE_PATH")
            self.assertEqual(duplicate.path, "events/foo.txt")

    def test_repository_and_workshop_noise_is_ignored_for_folders_and_zips(self):
        service_paths = (
            ".gitignore", ".gitattributes", ".github/workflows/ci.yml",
            "preview.png", "desktop.ini",
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            folder = root / "mod-folder"
            for relative in service_paths:
                file_path = folder / relative
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_text("service noise", encoding="utf-8")
            keep = folder / "common" / "ideas" / "keep.txt"
            keep.parent.mkdir(parents=True)
            keep.write_text("idea = { }", encoding="utf-8")

            archive = root / "mod.zip"
            with zipfile.ZipFile(archive, "w") as zipped:
                for relative in service_paths:
                    zipped.writestr(relative, "service noise")
                zipped.writestr("common/ideas/keep.txt", "idea = { }")

            expected = ["common/ideas/keep.txt"]
            self.assertEqual([item.path for item in load_mod(folder).files], expected)
            self.assertEqual([item.path for item in load_mod(archive).files], expected)

    def test_service_files_do_not_create_false_overrides(self):
        with tempfile.TemporaryDirectory() as directory:
            mods = []
            for name in ("a", "b"):
                path = Path(directory) / name
                path.mkdir()
                (path / "thumbnail.png").write_bytes(b"image")
                mods.append(load_mod(path))
            self.assertEqual(compare_mods(mods), [])

    def test_distinct_sources_with_same_name_still_report_overrides(self):
        with tempfile.TemporaryDirectory() as directory:
            mods = []
            for folder in ("left", "right"):
                path = Path(directory) / folder / "SameMod"
                target = path / "common" / "ideas" / "shared.txt"
                target.parent.mkdir(parents=True)
                target.write_text("idea = { }", encoding="utf-8")
                mods.append(load_mod(path))

            findings = compare_mods(mods)
            self.assertEqual(len(findings), 1)
            self.assertEqual(findings[0].code, "FILE_OVERRIDE")
            self.assertEqual(findings[0].path, "common/ideas/shared.txt")
            self.assertIn("SameMod [SameMod #1]", findings[0].message)
            self.assertIn("SameMod [SameMod #2]", findings[0].message)


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

    def test_script_errors_are_checked_in_all_scripted_roots(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "mod"
            roots = ("scripted_effects", "scripted_guis", "scripted_triggers")
            for root in roots:
                target = path / root / "broken.txt"
                target.parent.mkdir(parents=True)
                target.write_text("effect = {\n", encoding="utf-8")

            findings = inspect_mod(load_mod(path))
            broken_paths = {
                item.path for item in findings if item.code == "SCRIPT_UNCLOSED_BRACE"
            }
            self.assertEqual(
                broken_paths,
                {f"{root}/broken.txt" for root in roots},
            )

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

    def test_self_dependency_is_reported_as_a_cycle(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "SelfMod"
            path.mkdir()
            (path / "descriptor.mod").write_text(
                'name = "SelfMod"\ndependencies = { "SelfMod" }\n',
                encoding="utf-8",
            )

            findings = dependency_findings([load_mod(path)])

            self.assertEqual([finding.code for finding in findings], ["DEPENDENCY_CYCLE"])
            self.assertIn("SelfMod -> SelfMod", findings[0].message)

    def test_duplicate_declared_names_do_not_create_a_false_cycle(self):
        with tempfile.TemporaryDirectory() as directory:
            mods = []
            for folder, dependencies in (
                ("first-copy", ""),
                ("second-copy", 'dependencies = { "Shared Name" }\n'),
            ):
                path = Path(directory) / folder
                path.mkdir()
                (path / "descriptor.mod").write_text(
                    f'name = "Shared Name"\n{dependencies}', encoding="utf-8"
                )
                mods.append(load_mod(path))

            findings = dependency_findings(mods)

            self.assertEqual(
                [finding.code for finding in findings],
                ["DEPENDENCY_NAME_AMBIGUOUS"],
            )
            self.assertNotIn("DEPENDENCY_CYCLE", [finding.code for finding in findings])

    def test_long_dependency_cycle_does_not_exceed_python_recursion_limit(self):
        count = 1200
        mods = [
            ModInput(
                name=f"Mod {index}",
                source=f"mod-{index}",
                files=[],
                findings=[],
                declared_name=f"mod-{index}",
                dependencies=[f"mod-{index + 1}"] if index + 1 < count else ["mod-0"],
            )
            for index in range(count)
        ]

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

    def test_dependencies_match_declared_descriptor_names(self):
        with tempfile.TemporaryDirectory() as directory:
            mods = []
            for folder, declared, dependency in (("folder-a", "Alpha Mod", "Beta Mod"), ("folder-b", "Beta Mod", None)):
                path = Path(directory) / folder
                path.mkdir()
                metadata = f'name = "{declared}"\n'
                if dependency:
                    metadata += f'dependencies = {{ "{dependency}" }}\n'
                (path / "descriptor.mod").write_text(metadata, encoding="utf-8")
                mods.append(load_mod(path))
            self.assertEqual([mod.declared_name for mod in mods], ["Alpha Mod", "Beta Mod"])
            self.assertEqual(dependency_findings(mods), [])
            payload = json.loads(to_json(mods, []))
            self.assertEqual([item["declared_name"] for item in payload["mods"]], ["Alpha Mod", "Beta Mod"])

    def test_legacy_sidecar_descriptor_contributes_dependencies(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            legacy = root / "legacy"
            content = legacy / "Old Mod"
            (content / "common").mkdir(parents=True)
            (content / "common" / "ideas.txt").write_text("idea = { }", encoding="utf-8")
            (legacy / "Old Mod.mod").write_text(
                'name = "Legacy Alpha"\ndependencies = { "Legacy Beta" }\nreplace_path = "common/ideas"\n',
                encoding="utf-8",
            )
            beta = root / "beta"
            beta.mkdir()
            (beta / "descriptor.mod").write_text('name = "Legacy Beta"\n', encoding="utf-8")

            alpha_mod = load_mod(legacy)
            beta_mod = load_mod(beta)
            self.assertEqual(alpha_mod.name, "Old Mod")
            self.assertEqual(alpha_mod.declared_name, "Legacy Alpha")
            self.assertEqual(alpha_mod.dependencies, ["Legacy Beta"])
            self.assertEqual(alpha_mod.replace_paths, ["common/ideas"])
            self.assertEqual(dependency_findings([alpha_mod, beta_mod]), [])


class CliTests(unittest.TestCase):
    def test_json_report_retains_repeated_replace_paths_for_folder_zip_and_legacy_mods(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            descriptor = (
                'name = "Fixture"\n'
                'replace_path = "common/ideas"\n'
                'replace_path = "history/countries" # another replaced directory\n'
            )
            folder = root / "mod"
            folder.mkdir()
            (folder / "descriptor.mod").write_text(descriptor, encoding="utf-8")
            (folder / "events").mkdir()
            (folder / "events" / "fixture.txt").write_text("event = { }", encoding="utf-8")
            archive = root / "mod.zip"
            with zipfile.ZipFile(archive, "w") as zipped:
                zipped.writestr("Wrapped/descriptor.mod", descriptor)
                zipped.writestr("Wrapped/events/fixture.txt", "event = { }")
            legacy = root / "legacy"
            (legacy / "Fixture" / "events").mkdir(parents=True)
            (legacy / "Fixture.mod").write_text(descriptor, encoding="utf-8")
            (legacy / "Fixture" / "events" / "fixture.txt").write_text("event = { }", encoding="utf-8")

            for source in (folder, archive, legacy):
                with self.subTest(source=source.name):
                    output = root / "report.json"
                    result = main(["scan", str(source), "--format", "json", "--output", str(output)])
                    payload = json.loads(output.read_text(encoding="utf-8"))
                    self.assertEqual(result, 0)
                    self.assertEqual(
                        payload["mods"][0]["replace_paths"],
                        ["common/ideas", "history/countries"],
                    )

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
            self.assertEqual(payload["version"], __version__)
            self.assertNotIn(str(Path(directory).resolve()), rendered)

    def test_sarif_driver_reports_current_package_version(self):
        payload = json.loads(to_sarif([], []))
        self.assertEqual(payload["runs"][0]["tool"]["driver"]["version"], __version__)

    def test_reports_visibly_escape_untrusted_controls_and_bidi_paths(self):
        path = "common/ideas/alert\u202Egpj.txt"
        finding = Finding("HOSTILE_PATH", "warning", "bad\u202Evalue\nforged row", "mod\u202Ename", path)

        json_text = to_json([], [finding])
        json_finding = json.loads(json_text)["findings"][0]
        self.assertEqual(json_finding["path"], r"common/ideas/alert\u{202E}gpj.txt")
        self.assertIn(r"bad\u{202E}value\u{A}forged row", json_finding["message"])

        sarif_text = to_sarif([], [finding])
        sarif = json.loads(sarif_text)
        result = sarif["runs"][0]["results"][0]
        self.assertEqual(result["locations"][0]["physicalLocation"]["artifactLocation"]["uri"],
                         "common/ideas/alert%E2%80%AEgpj.txt")
        self.assertIn(r"\u{202E}", result["message"]["text"])

        text = to_text([], [finding])
        self.assertIn(r"alert\u{202E}gpj.txt", text)
        self.assertNotIn("\u202e", json_text + sarif_text + text)
        self.assertNotIn("\nforged row", json_text + sarif_text + text)


if __name__ == "__main__":
    unittest.main()
