#!/usr/bin/env python3
"""Build and audit the reviewed boundary for AMD64 instruction forms.

This tool deliberately does not infer architectural legality from a mnemonic
table.  It reconciles the table cells that are recoverable from the pinned
Volume 3 PDF, normalizes operand spellings, and emits explicit obligations for
all prose-derived facts.  Only a later semantic review may replace those
obligations with constraints.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "Specs" / "AMD64"
SOURCE = DATA / "instruction-source.json"
LOCK = DATA / "manuals.lock.json"
FORMS = DATA / "forms.json"
REVIEW = DATA / "instruction-review.json"

OPEN_FORM_OBLIGATIONS = [
    "review-operands-and-implicit-resources",
    "review-mode-and-size-rules",
    "review-feature-requirements",
    "review-prefix-legality",
    "review-effects-preserved-and-undefined-outputs",
    "review-exceptions-and-ordering",
    "record-volume1-state-dependencies",
    "record-volume2-behavior-dependencies",
]

CORE_INTEGER_ENTRIES = {
    "V3-GP-005": "add-with-carry",
    "V3-GP-007": "add",
    "V3-GP-009": "logical-and",
    "V3-GP-044": "compare",
    "V3-GP-098": "logical-or",
    "V3-GP-129": "subtract-with-borrow",
    "V3-GP-143": "subtract",
    "V3-GP-145": "test",
    "V3-GP-154": "logical-xor",
}

EXTENDED_INTEGER_ENTRIES = {
    "V3-GP-006": {"operation": "adcx", "feature": "CPUID.00000007H:EBX.ADX", "flag": "CF"},
    "V3-GP-008": {"operation": "adox", "feature": "CPUID.00000007H:EBX.ADX", "flag": "OF"},
    "V3-GP-010": {"operation": "andn", "feature": "CPUID.00000007H:EBX.BMI1", "flag": None},
}

CLOSED_CORE_FORMS = {
    **{f"V3-ROW-{row:04}": "add" for row in range(26, 30)},
    **{f"V3-ROW-{row:04}": "logical-and" for row in range(47, 51)},
    **{f"V3-ROW-{row:04}": "compare" for row in range(240, 244)},
    **{f"V3-ROW-{row:04}": "move" for row in range(496, 500)},
    **{f"V3-ROW-{row:04}": "logical-or" for row in range(561, 565)},
    **{f"V3-ROW-{row:04}": "subtract" for row in range(848, 852)},
    **{f"V3-ROW-{row:04}": "test" for row in range(869, 873)},
    **{f"V3-ROW-{row:04}": "logical-xor" for row in range(913, 917)},
}


def read_json(path: Path):
    return json.loads(path.read_text())


def write_json(path: Path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def normalized_space(text: str) -> str:
    return " ".join(text.replace("\u2013", "-").split())


def mnemonic_and_operands(text: str) -> tuple[str, list[str]]:
    head, *tail = normalized_space(text).split(" ", 1)
    if not tail:
        return head, []
    return head, [part.strip() for part in tail[0].split(",") if part.strip()]


def width_of(token: str):
    widths = [int(value) for value in re.findall(r"(?:reg|mem|imm|moffset|rel)(8|16|32|64|128|512)", token)]
    if len(set(widths)) == 1:
        return widths[0]
    fixed = {"AL": 8, "AH": 8, "AX": 16, "EAX": 32, "RAX": 64, "CL": 8, "DX": 16}
    return fixed.get(token)


def operand_kind(token: str) -> str:
    if re.fullmatch(r"reg/mem\d+", token):
        return "gpr-or-memory"
    if re.fullmatch(r"reg\d+(?:\.vvvv)?", token):
        return "gpr"
    if re.fullmatch(r"imm\d+", token):
        return "immediate"
    if re.fullmatch(r"rel\d+off", token):
        return "relative-offset"
    if re.fullmatch(r"moffset\d+", token):
        return "absolute-memory-offset"
    if re.fullmatch(r"mem\d+", token) or token == "mem":
        return "memory"
    if token.startswith("mem16:") or token.startswith("mem16&mem"):
        return "memory-composite"
    if token.startswith("FAR pntr"):
        return "far-pointer-immediate"
    if token.startswith("FAR mem"):
        return "far-pointer-memory"
    if token in {"AL", "AH", "AX", "EAX", "RAX", "CL", "DX", "CS", "DS", "ES", "SS", "FS", "GS"}:
        return "fixed-register"
    if token in {"segReg"}:
        return "segment-register"
    if token in {"xmm", "mmx"}:
        return token
    if token in {"0", "1"}:
        return "constant"
    if token == "rAX":
        return "address-sized-accumulator"
    if token == "reg16/32/64/mem16":
        return "gpr-or-memory-width-dependent"
    return "unclassified"


def operand_record(index: int, token: str) -> dict:
    kind = operand_kind(token)
    allowed_kinds = {
        "gpr-or-memory": ["gpr", "memory"],
        "gpr-or-memory-width-dependent": ["gpr", "memory"],
        "fixed-register": ["gpr" if token not in {"CS", "SS", "DS", "ES", "FS", "GS"}
                           else "segment-register"],
    }.get(kind, [kind])
    fixed_identities = {
        "AL": "gpr:0:low8", "AH": "gpr:0:high8", "AX": "gpr:0:low16",
        "EAX": "gpr:0:low32", "RAX": "gpr:0:full64", "rAX": "gpr:0:address-sized",
        "CL": "gpr:1:low8", "DX": "gpr:2:low16",
        "CS": "segment:cs", "SS": "segment:ss", "DS": "segment:ds",
        "ES": "segment:es", "FS": "segment:fs", "GS": "segment:gs",
    }
    return {
        "index": index,
        "source_text": token,
        "kind": kind,
        "allowed_concrete_kinds": allowed_kinds,
        "allowed_identities": [fixed_identities.get(token, "*")],
        "width_bits": width_of(token),
        "encoded_width_bits": width_of(token),
        "semantic_width_bits": width_of(token),
        "extension": "none",
        "width_rule": "literal-source-width" if width_of(token) is not None else "pending-prose-review",
        "explicit": True,
        "access": "unknown",
        "evaluation_order": index,
        "encoding": "pending-prose-review",
    }


def form_operand_width(form: dict) -> int | None:
    widths = [operand["width_bits"] for operand in form["operands"]
              if operand["kind"] not in {"immediate", "constant", "relative-offset"}
              and operand["width_bits"] is not None]
    return widths[0] if widths else None


def apply_core_integer_review(form: dict):
    entry = next((entry for entry in form["entry_ids"] if entry in CORE_INTEGER_ENTRIES), None)
    if entry is None:
        return
    operation = CORE_INTEGER_ENTRIES[entry]
    compare_only = operation in {"compare", "test"}
    logical = operation in {"logical-and", "logical-or", "logical-xor", "test"}
    width = form_operand_width(form)
    modes = ["real", "virtual8086", "protected", "compatibility", "long64"]
    if width == 64:
        modes = ["long64"]
    for index, operand in enumerate(form["operands"]):
        operand["access"] = "read" if index > 0 or compare_only else "read-write"
        operand["encoding"] = "reviewed-table-and-prose"
    implicit = []
    if operation in {"add-with-carry", "subtract-with-borrow"}:
        implicit.append({"name": "CF", "access": "read", "source": "instruction prose"})
    form["implicit_operands"] = {"knowledge": "reviewed", "items": implicit}
    form["constraints"]["modes"] = {"knowledge": "reviewed", "allowed": modes}
    form["constraints"]["features"] = {"knowledge": "reviewed", "required": []}
    form["constraints"]["cpl"] = {"knowledge": "reviewed", "allowed": [0, 1, 2, 3]}
    form["constraints"]["operand_sizes"] = {
        "knowledge": "reviewed" if width is not None else "unknown",
        "allowed": [width] if width is not None else [],
    }
    form["constraints"]["address_sizes"] = {
        "knowledge": "partial",
        "allowed": [16, 32, 64],
        "condition": "only meaningful when a concrete operand resolves to memory; mode cross-product pending",
    }
    memory_dest = bool(form["operands"] and
                       "memory" in form["operands"][0]["allowed_concrete_kinds"] and
                       not compare_only)
    form["constraints"]["prefixes"] = {
        "knowledge": "partial",
        "allowed": [],
        "required": [],
        "lock": "memory-destination-only" if memory_dest else "forbidden",
        "operand_size": "selects reviewed effective operand width",
        "address_size": "affects concrete memory operands only",
        "segment_override": "non-stack-memory-only; 64-bit CS/DS/ES/SS null-prefix rules apply",
        "rex": "64-bit or extended-register selection; high-byte registers unavailable with REX",
        "repeat": "pending-null-or-reserved-prefix-review",
        "sources": ["Volume 3 PDF pages 48-57", f"Volume 3 PDF page {form['source']['pdf_pages'][0]}"],
    }
    read_items = [f"operand:{index + 1}" for index in range(len(form["operands"]))]
    if implicit:
        read_items.append("rFLAGS.CF")
    write_items = [] if compare_only else ["operand:1"]
    if logical:
        flags = ["rFLAGS.SF", "rFLAGS.ZF", "rFLAGS.PF"]
        cleared = ["rFLAGS.OF", "rFLAGS.CF"]
        undefined = ["rFLAGS.AF"]
    else:
        flags = ["rFLAGS.OF", "rFLAGS.SF", "rFLAGS.ZF", "rFLAGS.AF", "rFLAGS.PF", "rFLAGS.CF"]
        cleared = []
        undefined = []
    form["semantics"]["reads"] = {"knowledge": "reviewed", "items": read_items}
    form["semantics"]["writes"] = {"knowledge": "reviewed", "items": write_items + flags + cleared,
                                      "cleared": cleared}
    form["semantics"]["preserved"] = {
        "knowledge": "reviewed",
        "items": ["rFLAGS.ID", "rFLAGS.VIP", "rFLAGS.VIF", "rFLAGS.AC", "rFLAGS.VM",
                  "rFLAGS.RF", "rFLAGS.NT", "rFLAGS.IOPL", "rFLAGS.DF", "rFLAGS.IF", "rFLAGS.TF"],
    }
    form["semantics"]["undefined"] = {"knowledge": "reviewed", "items": undefined}
    form["semantics"]["exceptions"] = {
        "knowledge": "reviewed-set-order-pending",
        "items": [
            {"vector": "#SS", "when": "resolved memory address exceeds stack limit or is non-canonical"},
            {"vector": "#GP", "when": "resolved memory violates data-segment/null/write rules"},
            {"vector": "#PF", "when": "resolved memory access causes a page fault"},
            {"vector": "#AC", "when": "unaligned memory access with alignment checking enabled"},
            {"vector": "#UD", "when": "LOCK violates the reviewed memory-destination rule"},
        ],
        "condition": "memory exceptions apply only when a union operand resolves to memory",
    }
    form["semantics"]["dependencies"] = {
        "knowledge": "partial",
        "items": [
            "Volume 1 GPR views and rFLAGS state",
            "Volume 2 segmentation and canonical-address checks",
            "Volume 2 paging and alignment checking",
            "Volume 3 sections 1.2.2-1.2.7 instruction prefixes",
        ],
    }
    form["review"]["reviewed_fields"] = [
        "explicit-operand-access", "implicit-CF-read", "mode", "feature", "cpl",
        "operand-size", "lock-condition", "flag-effects", "exception-set",
    ]
    obligations = [
        "review-null-or-reserved-repeat-prefix-behavior",
        "review-mode-address-size-cross-product-and-code-segment-defaults",
        "review-memory-exception-priority-and-commit-order",
        "bind-volume1-state-field-identifiers",
        "bind-volume2-dependency-section-identifiers",
    ]
    if width == 8 and any("gpr" in op["allowed_concrete_kinds"] for op in form["operands"]):
        obligations.append("review-byte-register-selection-with-and-without-rex")
    form["review"]["open_obligations"] = obligations


def apply_extended_integer_review(form: dict):
    entry = next((entry for entry in form["entry_ids"] if entry in EXTENDED_INTEGER_ENTRIES), None)
    if entry is None:
        return
    metadata = EXTENDED_INTEGER_ENTRIES[entry]
    width = form_operand_width(form)
    is_andn = metadata["operation"] == "andn"
    modes = ["protected", "compatibility", "long64"] if is_andn else [
        "real", "virtual8086", "protected", "compatibility", "long64"
    ]
    if width == 64:
        modes = ["long64"]
    for index, operand in enumerate(form["operands"]):
        if is_andn:
            operand["access"] = "write" if index == 0 else "read"
        else:
            operand["access"] = "read-write" if index == 0 else "read"
        operand["encoding"] = "reviewed-table-and-prose"
    implicit = []
    if metadata["flag"]:
        implicit = [{"name": metadata["flag"], "access": "read-write", "source": "instruction prose"}]
    form["implicit_operands"] = {"knowledge": "reviewed", "items": implicit}
    form["constraints"]["modes"] = {"knowledge": "reviewed", "allowed": modes}
    form["constraints"]["features"] = {"knowledge": "reviewed", "required": [metadata["feature"]]}
    form["constraints"]["cpl"] = {"knowledge": "reviewed", "allowed": [0, 1, 2, 3]}
    form["constraints"]["operand_sizes"] = {"knowledge": "reviewed", "allowed": [width]}
    form["constraints"]["address_sizes"] = {
        "knowledge": "partial", "allowed": [16, 32, 64],
        "condition": "only meaningful if final source operand resolves to memory; mode cross-product pending",
    }
    mandatory = "66" if metadata["operation"] == "adcx" else "F3" if metadata["operation"] == "adox" else "VEX"
    form["encoding"]["mandatory_prefix"] = {"knowledge": "reviewed", "value": mandatory}
    form["constraints"]["prefixes"] = {
        "knowledge": "partial", "allowed": [], "required": [mandatory],
        "lock": "forbidden",
        "address_size": "affects concrete memory source only",
        "segment_override": "affects concrete non-stack memory source only",
        "rex_or_w": "64-bit width selected by REX.W" if not is_andn else "64-bit width selected by VEX.W; VEX.L must be zero",
        "sources": ["Volume 3 PDF pages 47-58"] + [f"Volume 3 PDF page {page}" for page in form["source"]["pdf_pages"]],
    }
    reads = [f"operand:{index + 1}" for index in range(1 if is_andn else 0, len(form["operands"]))]
    if metadata["flag"]:
        reads.append(f"rFLAGS.{metadata['flag']}")
    form["semantics"]["reads"] = {"knowledge": "reviewed", "items": reads}
    writes = ["operand:1"]
    if metadata["flag"]:
        writes.append(f"rFLAGS.{metadata['flag']}")
    else:
        writes += ["rFLAGS.SF", "rFLAGS.ZF", "rFLAGS.OF=0", "rFLAGS.CF=0"]
    form["semantics"]["writes"] = {"knowledge": "reviewed", "items": writes}
    form["semantics"]["undefined"] = {
        "knowledge": "reviewed", "items": ["rFLAGS.AF", "rFLAGS.PF"] if is_andn else []
    }
    form["semantics"]["preserved"] = {
        "knowledge": "reviewed",
        "items": ["all rFLAGS except " + (metadata["flag"] or "SF,ZF,AF,PF,OF,CF")],
    }
    feature_cause = f"{metadata['feature']} absent"
    ud_causes = [feature_cause, "LOCK prefix present"]
    if is_andn:
        ud_causes += ["not in protected/long mode", "VEX.L = 1"]
    form["semantics"]["exceptions"] = {
        "knowledge": "reviewed-set-order-pending",
        "items": [
            {"vector": "#UD", "when": cause} for cause in ud_causes
        ] + [
            {"vector": "#SS", "when": "resolved memory source exceeds stack limit or is non-canonical"},
            {"vector": "#GP", "when": "resolved memory source violates data-segment or null-segment rules"},
            {"vector": "#PF", "when": "resolved memory source causes a page fault"},
            {"vector": "#AC", "when": "unaligned memory source with alignment checking enabled"},
        ],
    }
    form["semantics"]["dependencies"] = {
        "knowledge": "partial",
        "items": ["Volume 1 GPR views and rFLAGS state", "Volume 2 memory access and exception delivery",
                  "Volume 3 extended-encoding and prefix rules"],
    }
    form["review"]["reviewed_fields"] = [
        "explicit-operand-access", "implicit-flag-access", "mode", "feature", "cpl",
        "operand-size", "mandatory-prefix", "lock-forbidden", "flag-effects", "exception-set",
    ]
    form["review"]["open_obligations"] = [
        "review-mode-address-size-cross-product-and-code-segment-defaults",
        "review-memory-exception-priority-and-commit-order",
        "bind-volume1-state-field-identifiers",
        "bind-volume2-dependency-section-identifiers",
        "review-remaining-null-prefix-and-extended-prefix-reserved-fields",
    ]


def apply_nop_review(form: dict):
    """Review the body without assuming a byte decoder or prefix aliases."""
    if "V3-GP-096" not in form["entry_ids"]:
        return
    for operand in form["operands"]:
        operand["access"] = "none"
        operand["encoding"] = "reviewed-table-and-prose"
    form["implicit_operands"] = {"knowledge": "reviewed", "items": []}
    form["constraints"]["cpl"] = {"knowledge": "reviewed", "allowed": [0, 1, 2, 3]}
    form["semantics"] = {
        "reads": {"knowledge": "reviewed", "items": ["rIP", "decoded-length"]},
        "writes": {"knowledge": "reviewed", "items": ["rIP"]},
        "preserved": {"knowledge": "reviewed", "items": ["all-other-machine-state"]},
        "undefined": {"knowledge": "reviewed", "items": []},
        "exceptions": {"knowledge": "partial", "items": [
            {"vector": "#UD", "when": "LOCK prefix present (Volume 3 section 1.2.5)"}]},
        "dependencies": {"knowledge": "partial", "items": [
            "instruction fetch and length", "NOP/PAUSE/XCHG decode identity",
            "Volume 3 sections 1.2.1-1.2.7"]},
    }
    form["review"]["reviewed_fields"] = [
        "no-data-operand-access", "all-non-IP-state-preserved", "cpl", "lock-forbidden"]
    form["review"]["evidence"].append("Volume 3 PDF pages 314 and 53-57")
    form["review"]["open_obligations"] = [
        "review-prefix-aliases-including-F3-90-PAUSE-and-REX-B-XCHG",
        "bind-normalized-width-mode-and-prefix-combinations",
        "bind-instruction-fetch-length-and-next-IP",
        "bind-no-memory-access-despite-memory-shaped-operand",
    ]


def apply_unary_supplement(form: dict, rows: dict, supplement: dict):
    row = rows.get(form["form_id"])
    if row is None:
        return
    if (form["source"]["row_ids"] != [row["row_id"]] or
            row["entry_id"] not in form["entry_ids"] or
            form["source_spelling"] != row["source_spelling"] or
            form["encoding"]["source_text"] != row["encoding"]):
        raise ValueError(f"Unary supplement differs from pinned row: {form['form_id']}")
    width = row["width_bits"]
    operand = form["operands"][0]
    if operand["allowed_concrete_kinds"] != row["concrete_kinds"] or operand["width_bits"] != width:
        raise ValueError(f"Unary supplement narrows operand alternatives: {form['form_id']}")
    operand["access"] = "read-write"
    operand["encoding"] = "reviewed-table-and-prose"
    rules = supplement["shared_rules"]
    modes = rules["width64_modes"] if width == 64 else (
        rules["reg_mem_modes"] if row["long64"] else rules["embedded_register_modes"])
    form["constraints"]["modes"] = {"knowledge": "reviewed", "allowed": modes}
    form["constraints"]["features"] = {"knowledge": "reviewed", "required": []}
    form["constraints"]["cpl"] = {"knowledge": "reviewed", "allowed": [0, 1, 2, 3]}
    form["constraints"]["operand_sizes"] = {"knowledge": "reviewed", "allowed": [width]}
    form["implicit_operands"] = {"knowledge": "reviewed", "items": []}
    effects = supplement["effects"][form["mnemonic"]]
    form["semantics"]["reads"] = {"knowledge": "reviewed", "items": ["operand:1"]}
    form["semantics"]["writes"] = {"knowledge": "reviewed", "items":
        ["operand:1"] + effects.get("flags_written", [])}
    preserved = effects.get("flags_preserved", [])
    form["semantics"]["preserved"] = {"knowledge": "partial", "items":
        preserved if isinstance(preserved, list) else [preserved]}
    form["semantics"]["undefined"] = {"knowledge": "partial", "items":
        ["upper GPR bits after legacy-mode low32 write"] if width == 32 else []}
    form["review"]["reviewed_fields"] = [
        "explicit-operand-access", "mode", "feature", "cpl", "operand-size", "flag-effects"]
    form["review"]["evidence"].append("Specs/AMD64/integer-form-supplement.json")
    form["review"]["open_obligations"] = list(supplement["open_obligations"]) + [
        "complete shared prefix, exception and state-dependency review"]
    form["implementation"] = {
        "status": "partial", "modules": ["Specs/AMD64IntegerExecution.tla", "lean/AMD64/IntegerExecution.lean"],
        "evidence": ["register-body binding; memory instance remains modeling-unavailable"],
    }


def close_core_register_immediate_form(form: dict, operation_override: str | None = None):
    operation = operation_override or CLOSED_CORE_FORMS.get(form["source"]["row_ids"][0])
    if operation is None:
        return
    width = form_operand_width(form)
    encoded_width = form["operands"][1]["width_bits"]
    extension = "sign" if encoded_width < width else "none"
    form["operands"][0].update(encoded_width_bits=width, semantic_width_bits=width, extension="none")
    form["operands"][1].update(semantic_width_bits=width, extension=extension)
    prefixes = ["rep", "repne", "operand-size", "address-size",
                "cs", "ss", "ds", "es", "fs", "gs", "rex"]
    if width in {8, 64}:
        prefixes.append("rex-w")
    form["constraints"] = {
        "complete": True,
        "modes": {"knowledge": "reviewed", "allowed":
                  (["long64"] if width == 64 else
                   ["real", "virtual8086", "protected", "compatibility", "long64"])},
        "features": {"knowledge": "reviewed", "required": []},
        "cpl": {"knowledge": "reviewed", "allowed": [0, 1, 2, 3]},
        "operand_sizes": {"knowledge": "reviewed", "allowed": [width]},
        "address_sizes": {"knowledge": "reviewed", "allowed": [16, 32, 64],
                          "condition": "mode/address pair checked by validator"},
        "prefixes": {"knowledge": "reviewed", "allowed": prefixes,
                     "required": (["rex-w"] if width == 64 else []),
                     "lock": "forbidden-#UD", "repeat": "no repeat effect",
                     "operand_size": "selects the normalized effective width",
                     "address_size": "no operand effect; effective context pair remains valid",
                     "segment_override": "no effect without memory operand",
                     "rex": "register selection; REX.W selects 64-bit width where required",
                     "sources": ["Volume 3 PDF pages 48-57"]},
    }
    form["encoding"]["mandatory_prefix"] = {"knowledge": "reviewed", "value": None}
    if operation == "move":
        form["operands"][0]["access"] = "write"
        form["operands"][1]["access"] = "read"
        form["implicit_operands"] = {"knowledge": "reviewed", "items": []}
        form["semantics"] = {
            "reads": {"knowledge": "reviewed", "items": ["operand:2"]},
            "writes": {"knowledge": "reviewed", "items": ["operand:1"]},
            "preserved": {"knowledge": "reviewed", "items": ["rFLAGS"]},
            "undefined": {"knowledge": "reviewed", "items": []},
            "exceptions": {"knowledge": "reviewed", "items":
                           [{"vector": "#UD", "when": "LOCK prefix present"}]},
            "dependencies": {"knowledge": "reviewed", "items":
                             ["Volume 1 GPR views", "Volume 3 sections 1.2.1-1.2.7"]},
        }
    else:
        form["semantics"]["exceptions"] = {
            "knowledge": "reviewed",
            "items": [{"vector": "#UD", "when": "LOCK prefix present"}],
        }
        form["semantics"]["dependencies"] = {
            "knowledge": "reviewed",
            "items": ["Volume 1 GPR views and rFLAGS", "Volume 3 sections 1.2.1-1.2.7"],
        }
    for operand in form["operands"]:
        operand["encoding"] = "reviewed-table-and-prose"
    form["review"].update({
        "level": "semantic-reviewed", "status": "reviewed", "open_obligations": [],
        "reviewed_fields": ["complete-register-immediate-form"],
        "evidence": form["review"]["evidence"] + ["Volume 3 PDF pages 48-57"],
    })


def repair_mnemonic(row_id: str, text: str) -> tuple[str, str | None]:
    repairs = {
        "V3-ROW-0309": "IMUL reg16, reg/mem16, imm16",
        "V3-ROW-0310": "IMUL reg32, reg/mem32, imm32",
        "V3-ROW-0311": "IMUL reg64, reg/mem64, imm32",
        "V3-ROW-0486": "MOV reg16/32/64/mem16, segReg",
    }
    if row_id in repairs:
        return repairs[row_id], "wrapped-mnemonic-cell"
    return normalized_space(text), None


def repair_opcode(rows: list[dict], index: int) -> tuple[str, str]:
    row = rows[index]
    row_id = row["id"]
    original = normalized_space(row["opcode_candidate"])
    if row_id == "V3-ROW-0477":
        return "0F 01 FA", "description-column-contamination"
    if row_id == "V3-ROW-0548":
        return "0F 01 FB", "description-column-contamination"
    if row_id == "V3-ROW-0453":
        return "8F RXB.09 0.1111.0.00 12 /0", "split-xop-columns"
    if row_id == "V3-ROW-0454":
        return "8F RXB.09 1.1111.0.00 12 /0", "split-xop-columns"
    if original.startswith("RXB.02"):
        return "C4 " + original, "split-vex-columns"
    if original.startswith("RXB.09") or original.startswith("RXB.0A"):
        return "8F " + original, "split-xop-columns"
    if original:
        return original, "same-line-cell"

    mnemonic, _ = mnemonic_and_operands(row["mnemonic_candidate"])
    # CMOV tables merge each opcode vertically across its 16/32/64 rows.
    if mnemonic.startswith("CMOV"):
        for neighbour in rows[max(0, index - 1): index + 2]:
            other, _ = mnemonic_and_operands(neighbour["mnemonic_candidate"])
            candidate = normalized_space(neighbour["opcode_candidate"])
            if other == mnemonic and candidate:
                return candidate, "vertically-merged-cmov-cell"
    # SETcc synonym groups share one vertically merged opcode cell.
    set_groups = {
        "SETB": "0F 92 /0", "SETC": "0F 92 /0", "SETNAE": "0F 92 /0",
        "SETNB": "0F 93 /0", "SETNC": "0F 93 /0", "SETAE": "0F 93 /0",
    }
    if mnemonic in set_groups:
        return set_groups[mnemonic], "vertically-merged-setcc-cell"
    raise ValueError(f"unresolved opcode cell: {row_id} {row['mnemonic_candidate']!r}")


def encoding_record(opcode: str, method: str) -> dict:
    if opcode.startswith("8F RXB."):
        family = "xop"
    elif opcode.startswith(("C4 RXB.", "C5 ")):
        family = "vex-or-legacy-ambiguous" if opcode.startswith("C5 /r") else "vex"
    else:
        family = "legacy"
    modrm = None
    match = re.search(r"/(r|[0-7])(?:\s|$)", opcode)
    if match:
        modrm = {"present": True, "reg_field": "operand" if match.group(1) == "r" else int(match.group(1))}
    immediate_tokens = re.findall(r"(?<![A-Za-z])(ib|iw|id|iq|cb|cw|cd|cp)(?![A-Za-z])|/imm(8|16|32|64)", opcode)
    widths = {"ib": 8, "iw": 16, "id": 32, "iq": 64, "cb": 8, "cw": 16, "cd": 32, "cp": "far-pointer"}
    immediates = [widths[a] if a else int(b) for a, b in immediate_tokens]
    return {
        "source_text": opcode,
        "family": family,
        "reconciliation": method,
        "modrm": modrm,
        "immediate_widths": immediates,
        "mandatory_prefix": {"knowledge": "unknown", "value": None},
        "rex": {"knowledge": "table-evidence", "w_required": "REX.W" in opcode},
    }


def alias_key(form: dict):
    mnemonic = form["mnemonic"]
    families = ("CMOV", "SET", "J", "SAL", "SHL", "XLAT")
    if not mnemonic.startswith(families):
        return None
    return (form["encoding"]["source_text"], tuple((op["kind"], op["width_bits"]) for op in form["operands"]))


def validate_decoded(form: dict, decoded: dict, profile: dict) -> dict:
    """Executable mirror of the tri-state boundary for artifact-level tests.

    This is intentionally conservative: only a closed semantic review can
    reach validated/architectural-invalid. Partial catalogue knowledge remains
    undetermined even when the supplied decode happens to match known fields.
    """
    review = form["review"]
    if review["level"] != "semantic-reviewed" or review["status"] != "reviewed" or review["open_obligations"]:
        return {"kind": "undetermined", "obligations": review["open_obligations"] + ["semantic-form-review-incomplete"]}
    required_constraints = ("modes", "features", "cpl", "operand_sizes", "address_sizes", "prefixes")
    if any(form["constraints"][name]["knowledge"] != "reviewed" for name in required_constraints):
        return {"kind": "undetermined", "obligations": ["semantic-form-constraint-data-incomplete"]}
    # The shared TLA+/Lean shape API does not yet retain CPU privilege.
    # A catalogue-only privilege allowlist cannot close that missing binding.
    if set(form["constraints"]["cpl"]["allowed"]) != {0, 1, 2, 3}:
        return {"kind": "undetermined", "obligations": ["cpu-privilege-binding-required"]}
    if not all(key in profile for key in ("modes", "features", "operand_sizes", "address_sizes")):
        return {"kind": "undetermined", "obligations": ["architecture-profile-incomplete"]}
    if "prefix_conflict" not in decoded:
        return {"kind": "undetermined", "obligations": ["decoder-prefix-conflict-evidence-missing"]}
    normalization = []
    profile_errors = []
    architectural = []
    if decoded["form_id"] != form["form_id"]:
        normalization.append("form-id-mismatch")
    prefixes = set(decoded["prefixes"])
    rex_prefix = bool({"rex", "rex-w"} & prefixes)
    family = decoded["encoding_family"]
    coherent = (decoded["rex_present"] == rex_prefix) if family == "legacy" else (
        not decoded["rex_present"] and not rex_prefix)
    coherent = coherent and (not decoded["high_byte_register"] or
                             (family == "legacy" and not decoded["rex_present"]))
    coherent = coherent and (not rex_prefix or decoded["mode"] == "long64")
    if not coherent:
        normalization.append("incoherent-decoder-evidence")
    if ((decoded["mode"] == "long64" and decoded["address_size"] == 16) or
            (decoded["mode"] != "long64" and decoded["address_size"] == 64)):
        normalization.append("mode-address-size-incompatible")
    if decoded["encoding_family"] != form["encoding"]["family"]:
        normalization.append("encoding-family-mismatch")
    if decoded["mode"] not in profile["modes"]:
        profile_errors.append("mode-not-implemented-by-profile")
    if decoded["operand_size"] not in profile["operand_sizes"]:
        profile_errors.append("operand-size-not-implemented-by-profile")
    if decoded["address_size"] not in profile["address_sizes"]:
        profile_errors.append("address-size-not-implemented-by-profile")
    if decoded["mode"] not in form["constraints"]["modes"]["allowed"]:
        architectural.append("mode-illegal-for-form")
    if decoded["operand_size"] not in form["constraints"]["operand_sizes"]["allowed"]:
        architectural.append("operand-size-illegal-for-form")
    if decoded["address_size"] not in form["constraints"]["address_sizes"]["allowed"]:
        architectural.append("address-size-illegal-for-form")
    missing_features = set(form["constraints"]["features"]["required"]) - set(profile.get("features", []))
    if missing_features:
        architectural.append("missing-required-feature")
    expected = form["operands"]
    actual = decoded["operands"]
    if len(expected) != len(actual) or any(
        got["kind"] not in want["allowed_concrete_kinds"] or
        (want["width_bits"] is not None and got["width_bits"] != want["width_bits"]) or
        (want["encoded_width_bits"] is not None and
         got.get("encoded_width_bits") != want["encoded_width_bits"]) or
        (want["semantic_width_bits"] is not None and
         got.get("semantic_width_bits") != want["semantic_width_bits"]) or
        got.get("extension") != want["extension"] or
        ("*" not in want["allowed_identities"] and got.get("identity", "") not in want["allowed_identities"]) or
        (want["access"] != "unknown" and got.get("access") != want["access"]) or
        got.get("evaluation_order") != want["evaluation_order"]
        for want, got in zip(expected, actual)
    ):
        normalization.append("operand-shape-mismatch")
    policy = form["constraints"]["prefixes"]
    allowed_prefixes = set(policy["allowed"])
    required_prefixes = set(policy["required"])
    if not prefixes <= allowed_prefixes:
        architectural.append("prefix-illegal-for-form")
    if not required_prefixes <= prefixes:
        normalization.append("required-prefix-missing")
    if "lock" in prefixes:
        lock_ok = policy.get("lock") == "memory-destination-only" and actual and actual[0]["kind"] == "memory"
        if not lock_ok:
            architectural.append("lock-requires-memory-destination")
    if normalization:
        return {"kind": "normalization-error", "reasons": normalization}
    if profile_errors:
        return {"kind": "profile-error", "reasons": profile_errors}
    if decoded["prefix_conflict"]:
        return {"kind": "undefined-encoding", "reasons": ["conflicting-prefixes"]}
    if architectural:
        return {"kind": "architectural-invalid", "reasons": architectural}
    return {"kind": "validated", "reasons": []}


def generate() -> tuple[dict, dict]:
    source = read_json(SOURCE)
    lock = read_json(LOCK)
    volume3 = next(item for item in lock["sources"] if item["volume"] == 3)
    entries = {entry["id"]: entry for entry in source["entries"]}
    unary_supplement = read_json(DATA / "integer-form-supplement.json")
    unary_rows = {row["form_id"]: row for row in unary_supplement["forms"]}
    if len(unary_rows) != len(unary_supplement["forms"]):
        raise ValueError("Duplicate unary supplement form IDs")
    forms = []
    for index, row in enumerate(source["table_row_candidates"]):
        spelling, mnemonic_repair = repair_mnemonic(row["id"], row["mnemonic_candidate"])
        mnemonic, operands = mnemonic_and_operands(spelling)
        opcode, opcode_method = repair_opcode(source["table_row_candidates"], index)
        entry_ids = list(row["entry_ids"])
        if mnemonic == "SHL" and "V3-GP-133" not in entry_ids:
            entry_ids.append("V3-GP-133")
        form = {
            "form_id": f"AMD64-F-{index + 1:04}",
            "entry_ids": entry_ids,
            "mnemonic": mnemonic,
            "source_spelling": spelling,
            "aliases": [],
            "source": {
                "volume": 3,
                "publication": volume3["publication"],
                "revision": volume3["revision"],
                "pdf_pages": [row["pdf_page"]],
                "entry_titles": [entries[entry_id]["title"] for entry_id in entry_ids],
                "row_ids": [row["id"]],
            },
            "encoding": encoding_record(opcode, opcode_method),
            "operands": [operand_record(position, operand) for position, operand in enumerate(operands, 1)],
            "implicit_operands": {"knowledge": "unknown", "items": []},
            "constraints": {
                "modes": {"knowledge": "unknown", "allowed": []},
                "features": {"knowledge": "unknown", "required": []},
                "cpl": {"knowledge": "unknown", "allowed": []},
                "operand_sizes": {"knowledge": "unknown", "allowed": []},
                "address_sizes": {"knowledge": "unknown", "allowed": []},
                "prefixes": {"knowledge": "unknown", "allowed": [], "required": []},
            },
            "semantics": {
                "reads": {"knowledge": "unknown", "items": []},
                "writes": {"knowledge": "unknown", "items": []},
                "preserved": {"knowledge": "unknown", "items": []},
                "undefined": {"knowledge": "unknown", "items": []},
                "exceptions": {"knowledge": "unknown", "items": []},
                "dependencies": {"knowledge": "unknown", "items": []},
            },
            "review": {
                "level": "table-reconciled",
                "status": "pending-semantic-review",
                "evidence": [f"Volume 3 PDF page {row['pdf_page']}", row["id"]],
                "repairs": [item for item in [mnemonic_repair, opcode_method if opcode_method != "same-line-cell" else None] if item],
                "open_obligations": list(OPEN_FORM_OBLIGATIONS),
            },
            "implementation": {"status": "missing", "modules": [], "evidence": []},
        }
        apply_core_integer_review(form)
        apply_extended_integer_review(form)
        apply_nop_review(form)
        apply_unary_supplement(form, unary_rows, unary_supplement)
        close_core_register_immediate_form(form)
        if any(entry_id in {"V3-GP-076", "V3-GP-146"} for entry_id in form["entry_ids"]):
            form["review"]["open_obligations"].append(
                "review-profile-dependent-lzcnt-tzcnt-fallback-to-bsr-bsf")
        forms.append(form)

    # C7 /0 id is one table row with a reg/mem64 destination. Preserve that
    # pending table form and add a distinct reviewed register-only variant.
    base = next(form for form in forms if form["source"]["row_ids"] == ["V3-ROW-0503"])
    variant = copy.deepcopy(base)
    variant["form_id"] = "AMD64-F-0503-R"
    variant["variant_of"] = base["form_id"]
    variant["source_spelling"] = "MOV reg64, imm32"
    variant["operands"][0].update(source_text="reg64", kind="gpr",
                                  allowed_concrete_kinds=["gpr"], width_bits=64,
                                  encoded_width_bits=64, semantic_width_bits=64,
                                  extension="none", access="write")
    variant["operands"][1].update(semantic_width_bits=64, extension="sign", access="read")
    close_core_register_immediate_form(variant, "move")
    variant["review"]["evidence"].append("register-only variant; memory table form remains pending")
    forms.append(variant)

    groups: dict[tuple, list[dict]] = {}
    for form in forms:
        key = alias_key(form)
        if key is not None:
            groups.setdefault(key, []).append(form)
    for group in groups.values():
        names = sorted({form["mnemonic"] for form in group})
        if len(names) > 1:
            for form in group:
                form["aliases"] = [name for name in names if name != form["mnemonic"]]

    by_entry = {entry_id: [] for entry_id in entries}
    for form in forms:
        for entry_id in form["entry_ids"]:
            by_entry[entry_id].append(form["form_id"])
    reviews = []
    for entry_id, entry in entries.items():
        redirects = []
        if entry_id == "V3-GP-133":
            redirects = [{"entry_id": "V3-GP-126", "reason": "SHL page directs to SAL SHL"}]
        owned_forms = [form for form in forms if entry_id in form["entry_ids"]]
        reviewed_fields = sorted({field for form in owned_forms for field in form["review"].get("reviewed_fields", [])})
        open_obligations = sorted({obligation for form in owned_forms for obligation in form["review"]["open_obligations"]})
        reviews.append({
            "entry_id": entry_id,
            "title": entry["title"],
            "source_pages": list(range(entry["pdf_page"], entry["pdf_end_page"] + 1)),
            "candidate_row_ids": entry["candidate_ids"],
            "form_ids": by_entry[entry_id],
            "redirects": redirects,
            "review_level": "table-reconciled",
            "status": "pending-semantic-review",
            "reviewed_fields": reviewed_fields,
            "open_obligations": open_obligations,
            "module_links": ["Specs/AMD64InstructionForms.tla", "lean/AMD64/InstructionForms.lean"],
            "evidence_links": ["Specs/AMD64/forms.json", "docs/amd64-instruction-forms.md"],
        })
    authority = {
        "publication": volume3["publication"],
        "revision": volume3["revision"],
        "sha256": volume3["sha256"],
        "source_inventory_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
    }
    forms_doc = {
        "schema_version": 1,
        "generated_by": "tools/amd64_forms.py",
        "authority": authority,
        "review_levels": ["table-extracted", "table-reconciled", "semantic-reviewed"],
        "legality_contract": "Only semantic-reviewed forms with no open architectural obligations may validate.",
        "summary": {
            "table_reconciled": len(source["table_row_candidates"]),
            "derived_architectural_variants": len(forms) - len(source["table_row_candidates"]),
            "partially_semantic_reviewed": sum(
                bool(form["review"].get("reviewed_fields")) and
                form["review"]["level"] != "semantic-reviewed" for form in forms),
            "semantic_reviewed": sum(form["review"]["level"] == "semantic-reviewed" for form in forms),
        },
        "forms": forms,
    }
    review_doc = {
        "schema_version": 1,
        "generated_by": "tools/amd64_forms.py",
        "authority": authority,
        "entries": reviews,
    }
    return forms_doc, review_doc


def check(forms_doc: dict, review_doc: dict):
    source = read_json(SOURCE)
    forms = forms_doc["forms"]
    reviews = review_doc["entries"]
    assert len(source["table_row_candidates"]) == 931
    assert len(forms) == 932
    assert len(reviews) == len(source["entries"]) == 154
    assert len({form["form_id"] for form in forms}) == len(forms)
    assert len({entry["entry_id"] for entry in reviews}) == len(reviews)
    assert all(form["encoding"]["source_text"] for form in forms)
    assert all(form["review"]["status"] in {"pending-semantic-review", "reviewed"} for form in forms)
    assert all(form["review"]["open_obligations"] or
               form["review"]["level"] == "semantic-reviewed" for form in forms)
    assert all(entry["form_ids"] for entry in reviews)
    assert all(entry["open_obligations"] for entry in reviews)
    assert next(entry for entry in reviews if entry["entry_id"] == "V3-GP-133")["redirects"]
    assert forms[149]["encoding"]["source_text"] == "0F 40 /r"
    assert forms[452]["encoding"]["source_text"].startswith("8F RXB.09")
    assert forms[476]["encoding"]["source_text"] == "0F 01 FA"
    assert forms[547]["encoding"]["source_text"] == "0F 01 FB"
    assert forms_doc["summary"]["partially_semantic_reviewed"] == sum(
        bool(form["review"].get("reviewed_fields")) and
        form["review"]["level"] != "semantic-reviewed" for form in forms)
    assert forms_doc["summary"]["semantic_reviewed"] == sum(
        form["review"]["level"] == "semantic-reviewed" for form in forms)
    print(f"AMD64 forms OK: {len(source['table_row_candidates'])} source table forms, "
          f"{len(forms) - len(source['table_row_candidates'])} derived variants, {len(reviews)} entries; "
          f"partial semantic fields: {forms_doc['summary']['partially_semantic_reviewed']}; "
          f"semantic-reviewed: {forms_doc['summary']['semantic_reviewed']}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["generate", "check"])
    args = parser.parse_args()
    generated_forms, generated_review = generate()
    if args.command == "generate":
        write_json(FORMS, generated_forms)
        write_json(REVIEW, generated_review)
    else:
        if read_json(FORMS) != generated_forms or read_json(REVIEW) != generated_review:
            raise SystemExit("generated form artifacts are stale; run tools/amd64_forms.py generate")
    check(generated_forms, generated_review)


if __name__ == "__main__":
    main()
