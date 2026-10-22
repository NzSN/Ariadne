"""Identity, omission and extraction controls for the XED template denominator."""
import copy
import hashlib
import io
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import amd64_inventory as inventory
import amd64_inventory_xed as xed


def source(pattern="0xF8", operands="", mode="unspecified", easz="aszall"):
    return dict(iclass="CLC", iform="CLC", pattern=pattern, operands=operands,
                isa_set="I86", space="legacy", mode_restriction=mode, easz=easz,
                attributes="", undocumented=False)


def sample():
    rows = xed.normalize([source(), source("0xF8 REX2=1"), source(mode="not64")])
    value = dict(schema=xed.SCHEMA, records=rows, recordsSha256=xed.digest(rows),
                 counts=xed.summarize(rows), selectedInputs=[{"path": "datafiles/test", "sha256": "a" * 64}],
                 preparedInputSha256={"all-state.txt": "b" * 64},
                 operandWidths={"v": {"16": "16", "32": "32", "64": "64"}},
                 scope={"unit": "symbolic encoding template"})
    material = {key: value[key] for key in ("selectedInputs", "preparedInputSha256", "operandWidths", "scope")}
    lock = dict(normalized=dict(recordsSha256=xed.digest(rows), counts=xed.summarize(rows),
                                inputsAndScopeSha256=xed.digest(material)))
    return value, lock


class InventoryControls(unittest.TestCase):
    def test_mnemonic_and_iform_do_not_collapse_prefix_operand_or_duplicate_records(self):
        rows = xed.normalize([source(), source("0xF8 REX2=1"),
                              source(operands="REG0=XED_REG_CF:w:SUPP"), source()])
        self.assertEqual(len({row["id"] for row in rows}), 4)
        self.assertEqual(len({row["iform"] for row in rows}), 1)
        self.assertEqual(rows[0]["source"], rows[3]["source"])
        self.assertTrue(rows[3]["id"].endswith(":2"))

    def test_explicit_mode_and_address_size_constraints_are_retained(self):
        rows = xed.normalize([source(mode=2), source(mode=0), source(mode="not64"),
                              source(easz="a16"), source()])
        self.assertEqual([row["modeDomain"] for row in rows],
                         [[64], [16], [16, 32], [16, 32], [16, 32, 64]])
        with self.assertRaises(ValueError):
            xed.normalize([source(mode="unknown")])

    def test_every_upstream_field_participates_in_record_identity(self):
        first = source()
        second = dict(first, cpuid_groups=[{"records": [{"leaf": "7", "reg": "EAX", "bit": 1}]}])
        third = dict(first, new_upstream_constraint="MUST_REVIEW")
        rows = xed.normalize([first, second, third])
        self.assertEqual(len({row["id"] for row in rows}), 3)
        self.assertEqual(rows[2]["source"]["new_upstream_constraint"], "MUST_REVIEW")

    def test_omissions_duplicates_reordering_and_rehashed_changes_fail_frozen_denominator(self):
        good, lock = sample()
        inventory.validate_inventory(good, lock)
        variants = [good["records"][:-1], list(reversed(good["records"])),
                    good["records"] + good["records"][:1]]
        for rows in variants:
            changed = copy.deepcopy(good)
            changed["records"] = xed.normalize([row["source"] for row in rows])
            changed["recordsSha256"] = xed.digest(changed["records"])
            changed["counts"] = xed.summarize(changed["records"])
            with self.assertRaises(ValueError):
                inventory.validate_inventory(changed, lock)
        changed = copy.deepcopy(good)
        changed["records"][0]["modeDomain"] = [64]
        with self.assertRaises(ValueError):
            inventory.validate_inventory(changed, lock)

    def test_grammar_width_source_selection_and_scope_cannot_change(self):
        good, lock = sample()
        for key in ("operandWidths", "preparedInputSha256", "selectedInputs", "scope"):
            changed = copy.deepcopy(good)
            changed[key] = {} if key != "selectedInputs" else []
            with self.assertRaises(ValueError):
                inventory.validate_inventory(changed, lock)

    def test_extra_architecture_or_semantic_completion_claim_is_not_validated(self):
        good, lock = sample()
        for key in ("fullAmd64Support", "allEncodingsLegal", "semanticsComplete"):
            changed = dict(good, **{key: True})
            with self.assertRaises(ValueError):
                inventory.validate_inventory(changed, lock)

    def test_duplicate_json_keys_and_nonfinite_numbers_are_rejected(self):
        for text in ('{"a":1,"a":2}', '{"a":NaN}', '{"a":Infinity}'):
            with self.assertRaises(ValueError):
                inventory.strict_json(text)

    def test_archive_sha_is_checked_before_source_extraction(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "source.tar.gz"
            path.write_bytes(b"not a tar archive")
            pin = dict(name="test", bytes=path.stat().st_size, sha256="0" * 64)
            with self.assertRaisesRegex(ValueError, "differs from pin"):
                inventory.extract_archive(path, pin, Path(temporary) / "output")
            self.assertFalse((Path(temporary) / "output").exists())

    def test_pinned_extraction_rejects_traversal_and_symlink_members(self):
        for name, link in (("root/../escape", False), ("root/..\\escape", False), ("root/module", True)):
            with tempfile.TemporaryDirectory() as temporary:
                path = Path(temporary) / "source.tar.gz"
                with tarfile.open(path, "w:gz") as archive:
                    item = tarfile.TarInfo(name)
                    if link:
                        item.type = tarfile.SYMTYPE
                        item.linkname = "/etc/passwd"
                        archive.addfile(item)
                    else:
                        item.size = 1
                        archive.addfile(item, io.BytesIO(b"x"))
                pin = dict(name="test", bytes=path.stat().st_size,
                           sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                           archivePrefix="root", archiveMembers=1, expandedBytes=1 if not link else 0)
                with self.assertRaisesRegex(ValueError, "path/type"):
                    inventory.extract_archive(path, pin, Path(temporary) / "output")


if __name__ == "__main__":
    unittest.main()
