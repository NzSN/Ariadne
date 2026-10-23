"""Concrete controls for the AMD-specific unadmitted 32-bit REP assessment."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import check_bap_rep_address_scope as scope

MOVSB = dict(family="movs", elementBits=8, repeatCondition="count")


class RepAddressScopeControls(unittest.TestCase):
    def test_low_zero_count_preserves_all_state_without_memory_access(self):
        state = scope.registers(1 << 32)
        state["RSI"] = scope.Value(0x123400007000, 64)
        state["RDI"] = scope.Value(0x567800008000, 64)
        result, memory = scope.expected32(MOVSB, state, {})
        self.assertEqual(result, {name: value.n for name, value in state.items()})
        self.assertEqual(memory, {})

    def test_address_truncation_uses_low_pointer_and_zero_extends_writes(self):
        state = scope.registers()
        state["RSI"] = scope.Value(0x123400007000, 64)
        state["RDI"] = scope.Value(0x567800008000, 64)
        memory = {0x7000: 0x21, 0x8000: 0x43,
                  0x123400007000: 0x65, 0x567800008000: 0x87}
        result, actual_memory = scope.expected32(MOVSB, state, memory)
        self.assertEqual((result["RCX"], result["RSI"], result["RDI"]), (0, 0x7001, 0x8001))
        self.assertEqual(actual_memory, {**memory, 0x8000: 0x21})
        for flag in scope.FLAGS:
            self.assertEqual(result[flag], state[flag].n)

    def test_pointer_updates_wrap_in_32_bits_in_both_directions(self):
        for direction, start, end in ((0, 0xffffffff, 0), (1, 0, 0xffffffff)):
            state = scope.registers(direction=direction)
            state["RSI"] = scope.Value(start, 64)
            state["RDI"] = scope.Value(start, 64)
            result, memory = scope.expected32(MOVSB, state, {start: 0x76})
            self.assertEqual((result["RSI"], result["RDI"]), (end, end))
            self.assertEqual(memory, {start: 0x76})


if __name__ == "__main__":
    unittest.main()
