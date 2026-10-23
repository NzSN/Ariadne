"""Guard the user-selected replacement of retained evidence with tests."""
import ast
import json
from pathlib import Path
import tarfile
import unittest
from run_output import run_output

ROOT = Path(__file__).resolve().parents[1]


class TestBasedValidationPolicy(unittest.TestCase):
    def test_run_outputs_cannot_recreate_collection_or_write_test_fixtures(self):
        for relative in ("evidence/new-run", "tests/fixtures/receipt.json", "docs/results"):
            with self.subTest(path=relative), self.assertRaises(ValueError):
                run_output(ROOT / relative)
        self.assertEqual(run_output(ROOT / "target/new-run"), ROOT / "target/new-run")

    def test_retained_collection_and_archive_publication_are_absent(self):
        self.assertFalse((ROOT / "evidence").exists())
        self.assertFalse((ROOT / "tools/evidence_archive.py").exists())
        self.assertFalse((ROOT / "tools/export_i5c_runtime.py").exists())
        self.assertFalse((ROOT / "mbt/results/handwritten-baseline.json").exists())
        self.assertNotIn("evidence/", (ROOT / ".gitattributes").read_text())
        for name in ("check_bap_core.py", "check_bap_ocaml.py", "check_bap_admission.py",
                     "check_i4_performance.py", "check_i5b.py", "check_i5c.py",
                     "run_generated_validation.py"):
            tree = ast.parse((ROOT / "tools" / name).read_text())
            strings = [node.value for node in ast.walk(tree)
                       if isinstance(node, ast.Constant) and isinstance(node.value, str)]
            with self.subTest(tool=name):
                self.assertFalse(any(value.startswith("evidence/") for value in strings))
                self.assertNotIn("evidence.tar.gz", strings)
                self.assertNotIn("--retain-raw", strings)
                self.assertNotIn("--receipt", strings)

    def test_controlled_bundle_contains_only_actual_test_inputs(self):
        directory = ROOT / "tests/input/fixtures/workloads"
        with tarfile.open(directory / "windows-inputs.tar.gz") as bundle:
            members = bundle.getmembers()
            self.assertEqual({m.name for m in members},
                             {"capture.dmp", "ariadne_crash_demo.exe", "witness.json"})
            self.assertTrue(all(m.isfile() for m in members))
        for name in ("bap-windows-workload-case.json", "investigation-windows-workload-case.json",
                     "real-capture-workload-case.json", "windows-oracle.json"):
            value = json.loads((directory / name).read_text())
            with self.subTest(fixture=name):
                self.assertNotIn("passed", value)
                self.assertNotIn("gates", value)
                self.assertNotIn("records", value)

    def test_active_tools_have_no_runtime_dependency_on_removed_paths(self):
        prefix = "evidence/" + "Ariadne/"
        for path in (ROOT / "tools").glob("*.py"):
            with self.subTest(tool=path.name):
                self.assertNotIn(prefix, path.read_text())
        for path in (ROOT / "tests/bap").glob("*.ml"):
            with self.subTest(native_driver=path.name):
                self.assertNotIn(prefix, path.read_text())
        for path in (ROOT / "tests").rglob("*"):
            if not path.is_file() or "__pycache__" in path.parts:
                continue
            with self.subTest(fixture=str(path.relative_to(ROOT))):
                with path.open("rb") as stream:
                    self.assertFalse(stream.read(64).startswith(b"version https://git-lfs.github.com/spec/v1\n"))


if __name__ == "__main__":
    unittest.main()
