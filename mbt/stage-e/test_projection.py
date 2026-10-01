#!/usr/bin/env python3
"""Check sparse address preservation and malformed state-map rejection."""
from copy import deepcopy
import unittest
from prepare import project


class ProjectionTests(unittest.TestCase):
    def fixture(self):
        return {
            "#meta": {"varTypes": {"statesAt": "(Int -> Set(Str))"}},
            "states": [{"statesAt": {"#map": [
                [{"#bigint": "4096"}, {"#set": ["entry"]}],
                [{"#bigint": "18446744073709551615"}, {"#set": []}],
            ]}}],
        }

    def test_sparse_and_empty_rows(self):
        trace = self.fixture()
        original = deepcopy(trace)
        rows = project(trace)["states"][0]["statesAt"]["#set"]
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1], {"va": {"#bigint": "18446744073709551615"}, "states": {"#set": []}})
        self.assertEqual(trace, original)

    def test_duplicate_and_noncanonical_addresses_rejected(self):
        for address in ("4096", "04096", "-1"):
            with self.subTest(address=address):
                trace = self.fixture()
                trace["states"][0]["statesAt"]["#map"][1][0]["#bigint"] = address
                with self.assertRaises(ValueError):
                    project(trace)

    def test_wrong_declared_type_and_extra_map_fields_rejected(self):
        trace = self.fixture()
        trace["#meta"]["varTypes"]["statesAt"] = "(Str -> Set(Str))"
        with self.assertRaises(ValueError):
            project(trace)
        trace = self.fixture()
        trace["states"][0]["statesAt"]["extra"] = 1
        with self.assertRaises(ValueError):
            project(trace)


if __name__ == "__main__":
    unittest.main()
