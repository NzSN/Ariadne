"""Native protocol and qualification admission tests, not analysis conformance."""
import base64
import copy
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock
from bap_core_contract import ContractError, SCHEMA, decode_request, validate_attribution
import with_mirrorrust_snapshot as snapshot

IDENTITY = dict(session="session-a", snapshot="snapshot-a", query="a" * 64, family="recovery")


def request(operation="observe", payload=None, sequence=1, family="recovery"):
    return dict(schema=SCHEMA, **{**IDENTITY, "family": family}, sequence=sequence,
                operation=operation, payload={} if payload is None else payload)


def decode(value, sequence=1, initialized=True, identity=IDENTITY):
    return decode_request((json.dumps(value) + "\n").encode(), identity, sequence, initialized)


class EnvelopeTests(unittest.TestCase):
    def test_lifecycle_and_both_action_families(self):
        decode(request("initialize", {"profile": "normalized-fixed-input/v1", "input": {}}, 0), 0, False)
        for operation in ("observe", "finish", "reset"):
            decode(request(operation))
        for action in ("Visit", "Propagate"):
            decode(request("advance", {"action": action, "address": "0xffffffffffffffff"}))
        for action in ("FinishRecovery", "FinishDataflow", "ExpandSlice", "FinishSlice"):
            decode(request("advance", {"action": action}))
        identity = {**IDENTITY, "family": "stateflow"}
        decode(request("advance", {"action": "FinishStateflow"}, family="stateflow"), identity=identity)

    def test_identity_sequence_and_unknown_fields(self):
        for key, value in (("schema", "v0"), ("snapshot", "other"), ("session", "old"),
                           ("query", "A" * 64), ("family", "ir"), ("sequence", True),
                           ("sequence", 0), ("sequence", 2), ("surprise", 1)):
            with self.subTest(key=key, value=value), self.assertRaises(ContractError):
                decode({**request(), key: value})

    def test_lifecycle_and_action_mismatches(self):
        cases = [request("initialize", {"profile": "normalized-fixed-input/v1", "input": {}}),
                 request("advance", {"action": "Visit"}),
                 request("advance", {"action": "FinishSlice", "address": "0x0000000000000001"}),
                 request("advance", {"action": "FinishStateflow"}),
                 request("run_to_completion"), request("observe", {"expected": {}})]
        for case in cases:
            with self.subTest(case=case), self.assertRaises(ContractError):
                decode(case)
        with self.assertRaises(ContractError):
            decode(request(sequence=0), 0, False)

    def test_addresses_are_full_unsigned_hex(self):
        for value in (1, True, "0x1", "0xFFFFFFFFFFFFFFFF", "0x10000000000000000", "-1"):
            with self.subTest(value=value), self.assertRaises(ContractError):
                decode(request("advance", {"action": "Visit", "address": value}))

    def test_json_framing_duplicate_keys_and_nonfinite(self):
        for raw in (b'{}', b'{}\n{}\n', b'{"a":1,"a":2}\n', b'{"a":NaN}\n',
                    b'{"a":Infinity}\n', b'{"a":1e9999}\n', b'\xff\n', b'[' * 2000 + b'\n',
                    b' ' * (8 * 1024 * 1024) + b'\n'):
            with self.subTest(size=len(raw)), self.assertRaises(ContractError):
                decode_request(raw, IDENTITY, 1, True)


class AttributionTests(unittest.TestCase):
    def setUp(self):
        self.site = "0xfffffffffffffff0"
        self.rows = [dict(term="b1", **{"class": "blk"}, origin="machine", snapshot="s", va=self.site, parents=[]),
                     dict(term="d1", **{"class": "def"}, origin="machine", snapshot="s", va=self.site, parents=["b1"]),
                     dict(term="phi1", **{"class": "phi"}, origin="synthetic", snapshot="s", va=None, parents=["d1"])]

    def test_same_va_multiple_terms_and_synthetic_attribution(self):
        validate_attribution(self.rows, "s", {self.site})

    def test_no_invented_va_snapshot_or_term(self):
        for index, key, value in ((2, "va", self.site), (0, "va", "0x0000000000000001"),
                                  (1, "snapshot", "other"), (1, "term", "b1"),
                                  (2, "parents", []), (2, "parents", ["missing"]),
                                  (1, "parents", ["d1"]), (2, "parents", ["d1", "d1"]),
                                  (0, "parents", ["phi1"])):
            rows = copy.deepcopy(self.rows)
            rows[index][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ContractError):
                validate_attribution(rows, "s", {self.site})


class DependencySnapshotTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.directory = self.root / "pin"
        self.client = self.directory / "MirrorRust"
        (self.client / "src").mkdir(parents=True)
        (self.client / "Cargo.toml").write_text('[package]\nname = "mirrorrust"\n')
        (self.client / "src/lib.rs").write_text("pub fn example() {}\n")
        (self.client / "capabilities.json").write_text('{"version": 1}\n')
        files = snapshot.inventory(self.client)
        contents = {name: base64.b64encode((self.client / name).read_bytes()).decode()
                    for name in files}
        self.record = {"schema": snapshot.SCHEMA, "originRevision": "a" * 40,
                       "files": files, "contentsBase64": contents,
                       "inputFiles": files, "inputContentsBase64": contents}
        self.manifest = self.directory / "manifest.json"
        self.manifest.write_text(json.dumps(self.record))
        self.digest = snapshot.sha(self.manifest)
        patch = mock.patch.object(snapshot, "revision", return_value="a" * 40)
        patch.start()
        self.addCleanup(patch.stop)

    def test_snapshot_remains_valid_after_original_source_changes(self):
        original = self.root / "live"
        shutil.copytree(self.client, original)
        (original / "src/lib.rs").write_text("pub fn changed() {}\n")
        self.assertEqual(snapshot.validate_snapshot(self.directory, self.digest), self.record)

    def test_modified_added_and_removed_snapshot_files_rejected(self):
        source = self.client / "src/lib.rs"
        source.write_text("pub fn changed() {}\n")
        with self.assertRaises(ValueError):
            snapshot.validate_snapshot(self.directory, self.digest)
        source.write_text("pub fn example() {}\n")
        added = self.client / "src/extra.rs"
        added.write_text("// extra\n")
        with self.assertRaises(ValueError):
            snapshot.validate_snapshot(self.directory, self.digest)
        added.unlink()
        source.unlink()
        with self.assertRaises(ValueError):
            snapshot.validate_snapshot(self.directory, self.digest)

    def test_manifest_selection_and_retained_bytes_are_bound(self):
        with self.assertRaises(ValueError):
            snapshot.validate_snapshot(self.directory, "0" * 64)
        self.record["contentsBase64"]["src/lib.rs"] = base64.b64encode(b"changed").decode()
        self.manifest.write_text(json.dumps(self.record))
        with self.assertRaises(ValueError):
            snapshot.validate_snapshot(self.directory, snapshot.sha(self.manifest))

    def test_root_level_compile_input_is_bound(self):
        self.assertIn("capabilities.json", self.record["files"])
        (self.client / "capabilities.json").write_text('{"version": 2}\n')
        with self.assertRaises(ValueError):
            snapshot.validate_snapshot(self.directory, self.digest)

    def test_symlink_cannot_reintroduce_a_live_dependency(self):
        source = self.client / "src/lib.rs"
        source.unlink()
        source.symlink_to(self.root / "live.rs")
        with self.assertRaises(ValueError):
            snapshot.validate_snapshot(self.directory, self.digest)

    def test_environment_without_read_only_mount_is_rejected(self):
        env = {"ARIADNE_MIRRORRUST_SNAPSHOT": str(self.directory),
               "ARIADNE_MIRRORRUST_SNAPSHOT_SHA256": self.digest}
        with mock.patch.dict(os.environ, env), mock.patch.object(os, "statvfs") as stat:
            stat.return_value.f_flag = 0
            with self.assertRaisesRegex(ValueError, "active read-only view"):
                snapshot.active_identity()
            stat.return_value.f_flag = os.ST_RDONLY
            with mock.patch.object(os.path, "samefile", return_value=False):
                with self.assertRaisesRegex(ValueError, "active read-only view"):
                    snapshot.active_identity()


if __name__ == "__main__":
    unittest.main()
