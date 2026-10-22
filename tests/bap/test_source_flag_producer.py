"""Independent negative controls for the source-built BAP flag producer pilot."""
import copy
import importlib.util
from pathlib import Path
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "source_flag_build", ROOT / "native/bap/source-coverage/build.py")
pilot = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pilot)


def variable(name):
    return dict(name=name, width=1, virtual=False)


def constant(value):
    return dict(kind="int", width=1, value=f"0x{value}:1")


def lift(destination, expression):
    return dict(status="lifted", wellTyped=True, length=1,
                bil=[dict(kind="move", var=variable(destination), value=expression)])


class FlagProducerControls(unittest.TestCase):
    def test_independently_written_five_flag_equations(self):
        rows = {"f8": lift("CF", constant(0)), "f9": lift("CF", constant(1)),
                "f5": lift("CF", dict(kind="not", arg=dict(kind="var", var=variable("CF")))),
                "fd": lift("DF", constant(1)), "fc": lift("DF", constant(0))}
        for code, row in rows.items():
            result = pilot.verify_flag(code, row)
            self.assertTrue(result["independentEquationsMatch"])
            self.assertEqual(result["inputCombinations"], 4)
        self.assertEqual(pilot.verify_flag("f5", rows["f5"])["uses"], ["flag:cf"])
        self.assertEqual(pilot.verify_flag("fd", rows["fd"])["uses"], [])

    def test_constant_cannot_replace_complement_even_when_one_input_matches(self):
        for value in (0, 1):
            with self.assertRaises(ValueError):
                pilot.verify_flag("f5", lift("CF", constant(value)))

    def test_wrong_flag_hidden_write_and_unknown_expression_are_rejected(self):
        candidates = [lift("DF", constant(0)),
                      lift("CF", dict(kind="outside-flag-subset", text="unknown"))]
        extra = lift("CF", constant(0))
        extra["bil"].append(dict(kind="move", var=variable("DF"), value=constant(1)))
        candidates.append(extra)
        for row in candidates:
            with self.assertRaises(ValueError):
                pilot.verify_flag("f8", row)

    def test_namespace_width_and_virtual_flag_aliases_cannot_gain_acceptance(self):
        for key, value in (("name", "RAX"), ("width", 64), ("virtual", True)):
            row = lift("CF", constant(0))
            row["bil"][0]["var"][key] = value
            with self.assertRaises(ValueError):
                pilot.verify_flag("f8", row)
        row = lift("CF", constant(2))
        with self.assertRaises(ValueError):
            pilot.verify_flag("f8", row)

    def test_missing_lift_and_trailing_instruction_are_not_success(self):
        for status in ("missing-semantics", "empty-bil", "trailing-bytes", "error"):
            row = lift("CF", constant(0))
            row["status"] = status
            with self.assertRaises(ValueError):
                pilot.verify_flag("f8", row)

    def test_archive_extraction_rejects_symlink_module(self):
        with tempfile.TemporaryDirectory(prefix="ariadne-source-flag-test-") as temp:
            root = Path(temp)
            archive_path = root / "source.tar"
            with tarfile.open(archive_path, "w") as archive:
                entry = tarfile.TarInfo("bap-revision/" + pilot.MODULES[0])
                entry.type = tarfile.SYMTYPE
                entry.linkname = "/etc/passwd"
                archive.addfile(entry)
            with self.assertRaises(ValueError):
                pilot.extract_sources(archive_path, "revision", root / "output")

    def test_observation_identity_and_exact_sequence_are_required(self):
        import json
        rows = [dict(schema="ariadne.bap-source-flag-observation/v1", bytes=code,
                     production=False, entry="X86_lifter.disasm_instr", bilEncoding="flag-bil-subset/v1")
                for code in pilot.CASES]
        encoded = lambda items: "\n".join(json.dumps(row) for row in items)
        self.assertEqual(set(pilot.bind_observations(encoded(rows))), set(pilot.CASES))
        for damaged in (rows[:-1], rows[::-1], rows + rows[:1]):
            with self.assertRaises(ValueError):
                pilot.bind_observations(encoded(damaged))
        forged = copy.deepcopy(rows)
        forged[0]["production"] = True
        with self.assertRaises(ValueError):
            pilot.bind_observations(encoded(forged))


if __name__ == "__main__":
    unittest.main()
