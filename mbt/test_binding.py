"""Exercise the production freshness check against an altered generated artifact."""

import shutil
import unittest

from binding import GENERATED, check_binding, generated_hashes
from tools import mirrors_tools, prepare_model, sha256, work_directory


class BindingFreshnessTests(unittest.TestCase):
    def test_modified_generated_source_is_rejected_without_repair(self):
        work = work_directory("binding-freshness")
        model = prepare_model(work)
        _, compiler, _ = mirrors_tools()
        candidate = work / "generated"
        original_hashes = generated_hashes()
        shutil.copytree(GENERATED, candidate)
        check_binding(compiler, model, work / "fresh.log", candidate)
        source = candidate / "AriadneReplayMirror.generated.rs"
        source.write_text(source.read_text() + "\n// Deliberately stale test artifact.\n")
        stale_hash = sha256(source)
        with self.assertRaisesRegex(RuntimeError, "AriadneReplayMirror.generated.rs"):
            check_binding(compiler, model, work / "stale.log", candidate)
        self.assertEqual(sha256(source), stale_hash, "a freshness check must not repair generated code")
        self.assertEqual(generated_hashes(), original_hashes)


if __name__ == "__main__":
    unittest.main()
