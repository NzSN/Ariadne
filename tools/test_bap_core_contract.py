"""A0 protocol admission tests, not BAP analysis conformance."""
import copy
import json
import unittest
from bap_core_contract import ContractError, SCHEMA, decode_request, validate_attribution

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


if __name__ == "__main__":
    unittest.main()
