import copy
import unittest

from projection import FIELDS, project, restore


class ProjectionTests(unittest.TestCase):
    def raw(self):
        return {
            "#meta": {"varTypes": {name: definition[1] for name, definition in FIELDS.items()}},
            "states": [{
                "phase": "recover",
                "provenance": {"#map": [[{"#bigint": "4096"}, "file"], [{"#bigint": "4100"}, "unavailable"]]},
                "reaching": {"#map": [[{"#bigint": "4096"}, {"#set": []}], [{"#bigint": "4100"}, {"#set": []}]]},
            }],
        }

    def test_sparse_addresses_round_trip_without_rebasing(self):
        raw = self.raw()
        original = copy.deepcopy(raw)
        projected = project(raw)
        self.assertEqual(raw, original)
        self.assertEqual(restore(projected, raw["#meta"]["varTypes"]), raw)
        self.assertEqual([r["va"] for r in projected["states"][0]["provenance"]["#set"]],
                         [{"#bigint": "4096"}, {"#bigint": "4100"}])

    def test_duplicate_keys_and_wrong_declarations_fail_closed(self):
        raw = self.raw()
        raw["states"][0]["provenance"]["#map"].append([{"#bigint": "4096"}, "captured"])
        with self.assertRaisesRegex(ValueError, "duplicate"):
            project(raw)
        raw = self.raw()
        raw["#meta"]["varTypes"]["provenance"] = "(Str -> Str)"
        with self.assertRaisesRegex(ValueError, "source type"):
            project(raw)

    def test_noncanonical_addresses_are_rejected(self):
        for address in ("01", "-1", "1.0", "+1", "", 1):
            raw = self.raw()
            raw["states"][0]["provenance"]["#map"][0][0]["#bigint"] = address
            with self.subTest(address=address), self.assertRaises(ValueError):
                project(raw)


if __name__ == "__main__":
    unittest.main()
