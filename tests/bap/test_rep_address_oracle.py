"""Independent AMD address-size equations and typed-BIL mutation controls."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import check_bap_rep_address_oracle as oracle


def variable(name, width=64, memory=False):
    return dict(name=name, index=0, virtual=False, width=0 if memory else width,
                type="mem" if memory else "imm")


def ref(name, width=64, memory=False):
    return dict(kind="var", var=variable(name, width, memory))


def integer(value, width):
    return dict(kind="int", value=f"0x{value:x}:{width}")


def cast(op, width, arg):
    return dict(kind="cast", op=op, width=width, arg=arg)


def binary(op, lhs, rhs):
    return dict(kind="binop", op=op, lhs=lhs, rhs=rhs)


def move(name, value):
    return dict(kind="move", var=variable(name), value=value)


def lodsb32_bil():
    """Small independent typed test input; never used as production semantics."""
    low = lambda name: cast(0, 32, ref(name))
    widen = lambda value: cast(3, 64, value)
    address = widen(low("RSI"))
    load = dict(kind="load", mem=ref("mem", memory=True), addr=address, width=8)
    stride = dict(kind="ite", condition=ref("DF", 1),
                  yes=integer(0xFFFFFFFF, 32), no=integer(1, 32))
    return [dict(kind="while", condition=binary(4, low("RCX"), integer(0, 32)), body=[
        move("RAX", dict(kind="concat", lhs=dict(kind="extract", hi=63, lo=8, arg=ref("RAX")), rhs=load)),
        move("RSI", widen(binary(18, low("RSI"), stride))),
        move("RCX", widen(binary(17, low("RCX"), integer(1, 32)))),
    ])]


class AddressOracleControls(unittest.TestCase):
    def test_exact_scope_and_canonical_prefix_order(self):
        self.assertEqual(len(oracle.CASES), 32)
        self.assertEqual(sum(case["addressBits"] == 32 for case in oracle.CASES.values()), 28)
        self.assertEqual({code for code in oracle.CASES if not code.startswith("67")},
                         {"f3ac", "66f3ad", "f3ad", "f348ad"})
        self.assertIn("6766f2a7", oracle.CASES)
        self.assertNotIn("66f267a7", oracle.CASES)

    def test_amd_zero_low_count_preserves_all_high_lanes_and_memory(self):
        for code, case in oracle.CASES.items():
            count = oracle.HIGH_COUNT if case["addressBits"] == 32 else 0
            state, memory = oracle.scenario(case, count, 1, 1, "source-wrap", "first-diff", oracle.ACCUMULATORS[0])
            actual, actual_memory = oracle.expected(case, state, memory)
            with self.subTest(code=code):
                self.assertEqual(actual, {name: value.n for name, value in state.items()})
                self.assertEqual(actual_memory, memory)

    def test_nonzero_low_count_ignores_high_bits_and_zero_extends_only_written_indices(self):
        for code, case in oracle.CASES.items():
            if case["addressBits"] != 32:
                continue
            state, memory = oracle.scenario(case, oracle.HIGH_COUNT | 1, 0, 0,
                                            "disjoint", "equal", oracle.ACCUMULATORS[0])
            actual, _ = oracle.expected(case, state, memory)
            family, size = case["family"], case["elementBits"] // 8
            with self.subTest(code=code):
                self.assertEqual(actual["RCX"], 0)
                self.assertEqual(actual["RSI"], 0x7000 + size if family in {"movs", "lods", "cmps"} else state["RSI"].n)
                self.assertEqual(actual["RDI"], 0x8000 + size if family in {"movs", "stos", "cmps", "scas"} else state["RDI"].n)

    def test_whole_element_crosses_four_gib_before_index_wrap(self):
        case = oracle.CASES["67f348ad"]
        state, _ = oracle.scenario(case, 1, 0, 1, "disjoint", "equal", 0)
        state["RSI"] = oracle.Value(0x12345678FFFFFFFC, 64)
        memory = {0xFFFFFFFC + i: i + 1 for i in range(8)}
        memory.update({i: 0xEE for i in range(4)})
        result, actual_memory = oracle.expected(case, state, memory)
        self.assertEqual(result["RAX"], 0x0807060504030201)
        self.assertEqual(result["RSI"], 4)
        self.assertEqual(actual_memory, memory)

    def test_index_wrap_is_reapplied_between_iterations_in_both_directions(self):
        case = oracle.CASES["67f3ac"]
        for direction, start, memory, accumulator, final in (
                (0, oracle.MASK32, {oracle.MASK32: 0x11, 0: 0x22}, 0x22, 1),
                (1, 0, {0: 0x11, oracle.MASK32: 0x22}, 0x22, oracle.MASK32 - 1)):
            state, _ = oracle.scenario(case, 2, direction, 1, "disjoint", "equal", 0)
            state["RSI"] = oracle.Value(start, 64)
            actual, _ = oracle.expected(case, state, memory)
            self.assertEqual(actual["RSI"], final)
            self.assertEqual(actual["RAX"], accumulator)

    def test_initial_zf_does_not_skip_first_compare(self):
        for code in ("67f3a6", "67f2a6", "67f3ae", "67f2ae"):
            case = oracle.CASES[code]
            pattern = "first-diff" if case["repeatCondition"] == "equal" else "first-equal"
            for zf in (0, 1):
                state, memory = oracle.scenario(case, oracle.HIGH_COUNT | 3, 0, zf,
                                                "disjoint", pattern, oracle.ACCUMULATORS[0])
                result, _ = oracle.expected(case, state, memory)
                self.assertEqual(result["RCX"], 2)
                self.assertEqual(result["ZF"], int(case["repeatCondition"] == "not-equal"))

    def test_lods_accumulator_partial_zero_and_full_writes(self):
        for code in ("67f3ac", "6766f3ad", "67f3ad", "67f348ad"):
            case = oracle.CASES[code]
            state, memory = oracle.scenario(case, 1, 0, 1, "disjoint", "equal", oracle.ACCUMULATORS[0])
            result, _ = oracle.expected(case, state, memory)
            bits = case["elementBits"]
            wanted = 1 << (bits - 1)
            if bits < 32:
                wanted |= state["RAX"].n & (oracle.MASK64 ^ ((1 << bits) - 1))
            self.assertEqual(result["RAX"], wanted)

    def test_subtraction_flags_use_full_element_signed_ranges(self):
        for bits in (8, 16, 32, 64):
            sign, mask = 1 << (bits - 1), (1 << bits) - 1
            flags = oracle.difference_flags(sign, 1, bits)
            self.assertEqual(flags, dict(CF=0, PF=int(bits != 8), AF=1, ZF=0, SF=0, OF=1))
            flags = oracle.difference_flags(sign - 1, mask, bits)
            self.assertEqual(flags, dict(CF=1, PF=int(bits != 8), AF=0, ZF=0, SF=1, OF=1))

    def test_overlap_reads_entire_source_element_before_writing_destination(self):
        case = oracle.CASES["6766f3a5"]
        state, _ = oracle.scenario(case, 2, 0, 0, "overlap-forward", "equal", 0)
        result, memory = oracle.expected(case, state, {0x7000 + i: i + 1 for i in range(5)})
        self.assertEqual(memory, {0x7000: 1, 0x7001: 1, 0x7002: 2, 0x7003: 2, 0x7004: 4})
        self.assertEqual(result["RSI"], 0x7004)

    def test_synthetic_typed_bil_matches_finite_independent_lodsb_equations(self):
        bil = lodsb32_bil()
        oracle.verify_capi_types(bil)
        for values in oracle.parameters(oracle.CASES["67f3ac"]):
            oracle.check_bil("67f3ac", bil, values)

    def test_wrong_64_bit_counter_is_rejected_without_huge_count_execution(self):
        bil = lodsb32_bil()
        bil[0]["condition"] = binary(4, ref("RCX"), integer(0, 64))
        with self.assertRaises(ValueError):
            oracle.check_bil("67f3ac", bil, (oracle.HIGH_COUNT, 0, 0, "disjoint", "equal", 0))

    def test_wrong_64_bit_pointer_is_rejected(self):
        bil = lodsb32_bil()
        bil[0]["body"][0]["value"]["rhs"]["addr"] = ref("RSI")
        with self.assertRaises(ValueError):
            oracle.check_bil("67f3ac", bil, (1, 0, 0, "disjoint", "equal", 0))

    def test_wrong_cast_enum_is_rejected_even_when_numerically_equal(self):
        bil = lodsb32_bil()
        bil[0]["body"][1]["value"]["op"] = 0
        with self.assertRaisesRegex(ValueError, "cast direction"):
            oracle.verify_capi_types(bil)
        bil = lodsb32_bil()
        bil[0]["condition"]["lhs"]["op"] = 3
        with self.assertRaisesRegex(ValueError, "cast direction"):
            oracle.verify_capi_types(bil)

    def test_unrelated_register_and_memory_mutations_are_rejected(self):
        values = (0, 0, 0, "disjoint", "equal", 0)
        for statement in (move("RBX", integer(0, 64)),
                          dict(kind="move", var=variable("mem", memory=True),
                               value=dict(kind="store", mem=ref("mem", memory=True),
                                          addr=integer(0x123456, 64), value=integer(0, 8)))):
            bil = lodsb32_bil() + [statement]
            with self.assertRaises(ValueError):
                oracle.check_bil("67f3ac", bil, values)

    def test_missing_memory_is_not_silently_filled_and_large_counts_are_bounded(self):
        case = oracle.CASES["67f3ac"]
        state, _ = oracle.scenario(case, 1, 0, 0, "disjoint", "equal", 0)
        with self.assertRaises(KeyError):
            oracle.expected(case, state, {})
        state["RCX"] = oracle.Value(9, 64)
        with self.assertRaisesRegex(ValueError, "finite-count bound"):
            oracle.expected(case, state, {})


if __name__ == "__main__":
    unittest.main()
