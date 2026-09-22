#!/usr/bin/env python3
"""Generate and validate the reviewed AMD64 Volume 1 state inventory.

This is intentionally separate from the source extractor and the parent-owned
coverage ledger. A section classification is evidence about review routing; it
does not imply that every state field or instruction transition is complete.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "Specs" / "AMD64"
SOURCE = DATA / "source-sections.json"
FIELDS = DATA / "state-fields.json"
REVIEW = DATA / "volume1-review.json"


def load(path: Path):
    return json.loads(path.read_text())


def dump(path: Path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def source_sections():
    return load(SOURCE)["sections"]


def authority():
    source = next(row for row in load(DATA / "manuals.lock.json")["sources"] if row["volume"] == 1)
    return {
        "volume": 1,
        "publication": source["publication"],
        "revision": source["revision"],
        "release_date": source["release_date"],
        "sha256": source["sha256"],
    }


def build_fields(sections):
    by_id = {row["id"]: row for row in sections}

    def src(*ids):
        return [{"id": sid, "pdf_page": by_id[sid]["pdf_page"], "title": by_id[sid]["title"]}
                for sid in ids]

    tla = "Specs/AMD64ArchitecturalState.tla"
    lean = "lean/AMD64/ArchitecturalState.lean"

    def field(identifier, component, kind, width, multiplicity, canonical, sources,
              guards=(), constraints=(), tla_ops=(), lean_decls=(), theorems=(),
              representation="implemented", validity="checked", opens=()):
        row = {
            "id": identifier,
            "component": component,
            "kind": kind,
            "width_bits": width,
            "multiplicity": multiplicity,
            "canonical_storage": canonical,
            "source_sections": src(*sources),
            "profile_guards": list(guards),
            "validity_constraints": list(constraints),
            "representation_status": representation,
            "validity_status": validity,
            "tla": {"module": tla, "operators": list(tla_ops)},
            "lean": {"module": lean, "declarations": list(lean_decls),
                     "theorems": list(theorems)},
            "evidence": [
                {"kind": "lean-check", "command": "cd lean && lake env lean AMD64/ArchitecturalState.lean"},
                {"kind": "tla-check", "command": "cd Specs && tlc -deadlock -cleanup -config AMD64ArchitecturalState.cfg AMD64ArchitecturalStateChecks.tla"},
            ] if representation == "implemented" else [],
            "open_obligations": list(opens),
        }
        return row

    rows = []
    add = rows.append

    for name, guard in [
        ("long-mode", "enables compatibility and long64 modes"),
        ("x87", "enables x87 instructions and state access"),
        ("mmx", "enables MMX views and requires x87 storage"),
        ("sse", "enables XMM and MXCSR use"),
        ("avx", "enables YMM use and requires SSE"),
        ("avx512", "enables ZMM16-31, 512-bit vectors and K masks; requires AVX"),
        ("mxcsr-misaligned-mask", "controls whether MXCSR.MM is defined"),
    ]:
        fid = f"STATE.profile.capability.{name}"
        source_ids = ("V1-SECTION-0003", "V1-SECTION-0076")
        if name in {"sse", "avx", "avx512", "mxcsr-misaligned-mask"}:
            source_ids += ("V1-SECTION-0158", "V1-SECTION-0180")
        if name == "mmx": source_ids += ("V1-SECTION-0230",)
        if name == "x87": source_ids += ("V1-SECTION-0284",)
        add(field(fid, "profile", "profile-parameter", 1, 1, fid, source_ids,
                  guards=("CPU state-bank capability only; form-specific CPUID and OS enablement are composed separately",),
                  constraints=(guard,), tla_ops=("CapabilitiesWellFormed", "ProfileWellFormed"),
                  lean_decls=("AMD64.Arch.Capabilities", "AMD64.Arch.ValidProfile"),
                  theorems=("AMD64.Arch.avx512_implies_sse",) if name == "avx512" else ()))

    for name, source_id in [("physical-address-bits", "V1-SECTION-0017"),
                            ("linear-address-bits", "V1-SECTION-0021")]:
        fid = f"STATE.profile.{name}"
        add(field(fid, "profile", "profile-parameter", {"natural_range": [32, 64]}, 1, fid,
                  (source_id,), constraints=("value is between 32 and 64 inclusive",),
                  tla_ops=("ProfileWellFormed",),
                  lean_decls=("AMD64.Arch.ArchitectureProfile", "AMD64.Arch.ValidProfile")))

    add(field("STATE.context.mode", "execution-context", "context", None, 1,
              "STATE.context.mode", ("V1-SECTION-0008", "V1-SECTION-0009",
              "V1-SECTION-0010", "V1-SECTION-0011", "V1-SECTION-0012"),
              constraints=("one of real, protected, virtual8086, compatibility, long64",
                           "compatibility and long64 require profile longMode"),
              tla_ops=("Modes", "ModeSupported"),
              lean_decls=("AMD64.Arch.OperatingMode", "AMD64.Arch.ModeSupported")))
    add(field("STATE.context.cpl", "execution-context", "context", 2, 1,
              "STATE.context.cpl", ("V1-SECTION-0080",),
              constraints=("value is 0 through 3",), tla_ops=("CPUStateWellFormed",),
              lean_decls=("AMD64.Arch.ExecutionContext", "AMD64.Arch.ValidCPUState")))
    for name, capability in [("x87-enabled", "x87"), ("sse-enabled", "sse"),
                             ("avx-enabled", "avx"), ("avx512-enabled", "avx512")]:
        fid = f"STATE.context.{name}"
        enable_sources = ("V1-SECTION-0076", "V1-SECTION-0284") if capability == "x87" else (
            "V1-SECTION-0076", "V1-SECTION-0158", "V1-SECTION-0180")
        add(field(fid, "execution-context", "context", 1, 1, fid,
                  enable_sources,
                  guards=(f"requires profile capability {capability}",),
                  constraints=("current derived enablement; parent MachineState must link this value to CR0/CR4/XCR0 system configuration",),
                  tla_ops=("CPUStateWellFormed",),
                  lean_decls=("AMD64.Arch.ExecutionContext", "AMD64.Arch.ValidCPUState"),
                  validity="partial",
                  opens=("M2/parent composition must prove consistency with concrete system control state.",)))

    add(field("STATE.gpr.storage", "integer", "storage", 64, 16,
              "STATE.gpr.storage", ("V1-SECTION-0031", "V1-SECTION-0032"),
              constraints=("single canonical physical bank; availability is mode-sensitive",
                           "identity order is RAX,RCX,RDX,RBX,RSP,RBP,RSI,RDI,R8..R15 = 0..15"),
              tla_ops=("CPUStateWellFormed", "GPRRegisterAvailable", "GPRIndex", "ReadNamedGPR"),
              lean_decls=("AMD64.Arch.CPUState.gpr", "AMD64.Arch.GPRRegisterAvailable",
                          "AMD64.Arch.GPR", "AMD64.Arch.GPR.index",
                          "AMD64.Arch.CPUState.gprValue"),
              theorems=("AMD64.Arch.GPR.toFin_injective",
                        "AMD64.Arch.CPUState.rcx_is_index_one",
                        "AMD64.Arch.CPUState.rsi_is_index_six",
                        "AMD64.Arch.CPUState.rdi_is_index_seven")))
    for view, width, bits, sources in [
        ("low8", 8, "0..7", ("V1-SECTION-0031", "V1-SECTION-0032")),
        ("high8", 8, "8..15", ("V1-SECTION-0031", "V1-SECTION-0032")),
        ("low16", 16, "0..15", ("V1-SECTION-0031", "V1-SECTION-0032")),
        ("low32", 32, "0..31", ("V1-SECTION-0031", "V1-SECTION-0032", "V1-SECTION-0068")),
        ("full64", 64, "0..63", ("V1-SECTION-0032",)),
    ]:
        fid = f"STATE.gpr.view.{view}"
        add(field(fid, "integer", "derived-view", width, "mode-dependent",
                  "STATE.gpr.storage", sources,
                  guards=("64-bit view only in long64 mode" if view == "full64" else
                          "encoding selects which named byte/register view is legal",),
                  constraints=(f"view aliases canonical bits {bits}",),
                  tla_ops=("ReadView", "GPRWidthAvailable"),
                  lean_decls=("AMD64.GPRView", "AMD64.readView", "AMD64.Arch.GPRWidthAvailable"),
                  theorems=("AMD64.read_after_write", "AMD64.preserves_outside")))

    add(field("STATE.rip.storage", "instruction-pointer", "storage", 64, 1,
              "STATE.rip.storage", ("V1-SECTION-0028", "V1-SECTION-0035"),
              constraints=("effective architectural width is 16, 32, or 64 by mode",),
              tla_ops=("DefaultInstructionPointerWidth", "CPUStateWellFormed"),
              lean_decls=("AMD64.Arch.CPUState.rip", "AMD64.Arch.defaultInstructionPointerWidth")))

    rflag_specs = [
        ("cf", 0), ("fixed1", 1), ("pf", 2), ("reserved3", 3), ("af", 4),
        ("reserved5", 5), ("zf", 6), ("sf", 7), ("tf", 8),
        ("interrupt-enable", 9), ("df", 10), ("of", 11), ("iopl", "12:13"),
        ("nested-task", 14), ("reserved15", 15), ("resume", 16),
        ("virtual8086", 17), ("ac", 18), ("virtual-interrupt", 19),
        ("virtual-interrupt-pending", 20), ("id", 21), ("reserved-high", "22:63"),
    ]
    for name, bit_range in rflag_specs:
        fid = f"STATE.rflags.{name}"
        app_visible = name in {"cf", "pf", "af", "zf", "sf", "df", "of"}
        constraints = []
        if name == "fixed1": constraints.append("reads as one")
        if name.startswith("reserved"):
            constraints.append("must be zero/read-as-zero; writes do not create state")
        flag_sources = ("V1-SECTION-0034",) if app_visible else (
            "V1-SECTION-0034", "V2-SECTION-0373")
        add(field(fid, "rflags", "storage", 42 if name == "reserved-high" else
                  2 if name == "iopl" else 1, 1, fid,
                  flag_sources,
                  guards=("application-visible flag" if app_visible else
                          "system-visible field retained because application instructions can observe or preserve it",),
                  constraints=constraints, tla_ops=("RFlagsWellFormed",),
                  lean_decls=("AMD64.Arch.RFlags", "AMD64.Arch.RFlags.Valid"),
                  theorems=("AMD64.Arch.RFlags.valid_high_reserved_zero",)
                  if name == "reserved-high" else ()))
        rows[-1]["bit_range"] = bit_range

    for register in ["cs", "ss", "ds", "es", "fs", "gs"]:
        fid = f"STATE.segment.{register}"
        add(field(fid, "segments", "storage", None, 1, fid,
                  ("V1-SECTION-0016", "V1-SECTION-0046", "V2-SECTION-0398", "V2-SECTION-0399"),
                  constraints=("selector and effective hidden cache are one segment-register value",),
                  tla_ops=("SegmentRegisterWellFormed", "CPUStateWellFormed"),
                  lean_decls=("AMD64.Arch.SegmentRegister", "AMD64.Arch.SegmentContext"),
                  validity="partial",
                  opens=("Volume 2 protection/type/load rules are owned by M2; this module checks only CPU-local shape and CS mode consistency.",)))
    for name, width in [("selector", 16), ("selector-rpl", 2), ("selector-ti", 1),
                        ("selector-index", 13), ("base", 64), ("limit", 32),
                        ("present", 1), ("dpl", 2), ("readable", 1),
                        ("writable", 1), ("executable", 1), ("expand-down", 1),
                        ("conforming", 1),
                        ("default-big", 1), ("long-mode", 1), ("unusable", 1)]:
        fid = f"STATE.segment.effective.{name}"
        canonical = "STATE.segment.*"
        kind = "derived-view" if name.startswith("selector-") else "context"
        add(field(fid, "segments", kind, width, 6, canonical,
                  ("V1-SECTION-0016", "V1-SECTION-0035", "V2-SECTION-0397",
                   "V2-SECTION-0398", "V2-SECTION-0399"),
                  guards=("FS/GS bases remain effective in long64; ordinary CS/SS/DS/ES base/limit semantics are mode-sensitive",),
                  constraints=("values are cached effective descriptor context, not an independent descriptor table",),
                  tla_ops=("SegmentRegisterWellFormed", "SelectorRPL", "SelectorTI", "SelectorIndex"),
                  lean_decls=("AMD64.Arch.SegmentCache", "AMD64.Arch.SegmentSelector"),
                  validity="partial",
                  opens=("M2 supplies full Volume 2 descriptor, privilege, null/unusable, and long-mode access rules.",)))

    add(field("STATE.x87.physical", "x87", "storage", 80, 8,
              "STATE.x87.physical", ("V1-SECTION-0255",),
              guards=("x87 capability",), constraints=("physical storage owns MMX low-bit aliases",),
              tla_ops=("X87StateWellFormed",),
              lean_decls=("AMD64.Arch.X87State.physical",)))
    add(field("STATE.x87.st", "x87", "derived-view", 80, 8,
              "STATE.x87.physical", ("V1-SECTION-0255", "V1-SECTION-0256"),
              guards=("x87 capability",),
              constraints=("ST(i) aliases physical[(TOP+i) modulo 8]",),
              tla_ops=("ReadST",), lean_decls=("AMD64.Arch.X87State.st",),
              theorems=("AMD64.Arch.X87State.st_zero_is_top",)))
    add(field("STATE.mmx.view", "mmx", "derived-view", 64, 8,
              "STATE.x87.physical", ("V1-SECTION-0200", "V1-SECTION-0234"),
              guards=("MMX capability",), constraints=("MMXn is low 64 bits of physical FPRn",),
              tla_ops=("ReadMMX",),
              lean_decls=("AMD64.Arch.X87State.mmx", "AMD64.Arch.X87State.writeMMXStorageLow"),
              theorems=("AMD64.Arch.X87State.read_write_mmx_storage_low_same",
                        "AMD64.Arch.X87State.write_mmx_storage_low_preserves_high"),
              opens=("The helper updates alias storage only; real MMX instruction transitions must also apply Volume 1 section 5.12 high-bit, TOP, and tag effects.",)))
    add(field("STATE.x87.tags", "x87", "storage", 2, 8,
              "STATE.x87.tags", ("V1-SECTION-0258",), guards=("x87 capability",),
              constraints=("each physical register tag is valid, zero, special, or empty",),
              tla_ops=("X87Tags", "X87StateWellFormed"),
              lean_decls=("AMD64.Arch.X87Tag", "AMD64.Arch.X87State.tags")))

    x87_status = ["invalid", "denormal", "zero-divide", "overflow", "underflow",
                  "precision", "stack-fault", "error-summary", "c0", "c1", "c2",
                  "top", "c3", "busy"]
    for name in x87_status:
        fid = f"STATE.x87.status.{name}"
        add(field(fid, "x87-status", "storage", 3 if name == "top" else 1, 1, fid,
                  ("V1-SECTION-0256",), guards=("x87 capability",),
                  constraints=("TOP is 0 through 7" if name == "top" else
                               "named status/condition/exception bit",),
                  tla_ops=("X87StatusWellFormed",),
                  lean_decls=("AMD64.Arch.X87Status",)))

    x87_control = [("invalid-mask", 1), ("denormal-mask", 1), ("zero-divide-mask", 1),
                   ("overflow-mask", 1), ("underflow-mask", 1), ("precision-mask", 1),
                   ("reserved6", 1), ("reserved7", 1), ("precision-control", 2),
                   ("rounding-control", 2), ("infinity-control", 1),
                   ("reserved-high", 3)]
    for name, width in x87_control:
        fid = f"STATE.x87.control.{name}"
        constraints = []
        validity = "checked"
        opens = []
        if "reserved" in name:
            constraints.append("represented exactly; Volume 1 marks this reserved and does not define arbitrary-load readback")
            validity = "source-unspecified"
            opens.append("Instruction transitions must use the applicable load/write reserved-bit policy; FINIT/FNINIT reset is separately fixed to 037Fh.")
        if name == "precision-control": constraints.append("reserved encoding is invalid")
        add(field(fid, "x87-control", "storage", width, 1, fid,
                  ("V1-SECTION-0257",), guards=("x87 capability",),
                  constraints=constraints, tla_ops=("X87ControlWellFormed", "X87ControlInit"),
                  lean_decls=("AMD64.Arch.X87Control", "AMD64.Arch.X87Control.Valid",
                              "AMD64.Arch.X87Control.init"),
                  theorems=("AMD64.Arch.X87Control.init_matches_037f_fields",),
                  validity=validity, opens=opens))

    for name, width in [("last-instruction-pointer", "mode-dependent 32/48/64"),
                        ("last-data-pointer", "mode-dependent 32/48/64"),
                        ("last-opcode", 11)]:
        fid = f"STATE.x87.{name}"
        add(field(fid, "x87-environment", "storage", width, 1, fid,
                  ("V1-SECTION-0259", "V1-SECTION-0260"), guards=("x87 capability",),
                  constraints=("tag records the mode-sensitive encoding used when this last-pointer state was produced; it is not constrained by the current mode" if "pointer" in name
                               else "11-bit permutation of the last non-control x87 opcode",),
                  tla_ops=("X87PointerWellFormed", "X87StateWellFormed"),
                  lean_decls=("AMD64.Arch.X87Pointer",)))

    add(field("STATE.vector.zmm", "vector", "storage", 512, 32,
              "STATE.vector.zmm", ("V1-SECTION-0119", "V1-SECTION-0181"),
              guards=("registers 0-7 require SSE; 8-15 require long64; 16-31 require AVX512 and long64",),
              constraints=("single canonical storage owns YMM and XMM low views",),
              tla_ops=("VectorRegisterAvailable", "VectorWidthAvailable"),
              lean_decls=("AMD64.Arch.VectorBank", "AMD64.Arch.VectorRegisterAvailable")))
    for name, width, capability in [("xmm", 128, "SSE"), ("ymm", 256, "AVX")]:
        fid = f"STATE.vector.{name}"
        add(field(fid, "vector", "derived-view", width, 32,
                  "STATE.vector.zmm", ("V1-SECTION-0119",),
                  guards=(f"{capability} capability and register-number/mode availability",),
                  constraints=(f"{name.upper()} is the low {width} bits of canonical ZMM",),
                  tla_ops=(f"Read{name.upper()}", "VectorWidthAvailable"),
                  lean_decls=(f"AMD64.Arch.read{name.upper()}", "AMD64.Arch.VectorWidthAvailable"),
                  theorems=(f"AMD64.Arch.read{name.upper()}_write{name.upper()}_same",)))
    add(field("STATE.vector.kmask", "vector-mask", "storage", 64, 8,
              "STATE.vector.kmask", ("V1-SECTION-0183", "V1-SECTION-0184"),
              guards=("AVX512 capability; k0 is storage but EVEX.aaa=000 disables writemasking",),
              tla_ops=("MaskRegisterAvailable", "CPUStateWellFormed"),
              lean_decls=("AMD64.Arch.MaskBank", "AMD64.Arch.MaskRegisterAvailable")))

    mxcsr = ["invalid", "denormal", "zero-divide", "overflow", "underflow", "precision",
             "denormals-are-zero", "invalid-mask", "denormal-mask", "zero-divide-mask",
             "overflow-mask", "underflow-mask", "precision-mask", "rounding-control",
             "flush-to-zero", "reserved16", "misaligned-mask", "reserved-high"]
    for name in mxcsr:
        width = 14 if name == "reserved-high" else 2 if name == "rounding-control" else 1
        constraints = []
        if name.startswith("reserved"): constraints.append("must be zero")
        if name == "misaligned-mask": constraints.append("must be zero when profile does not define MXCSR.MM")
        fid = f"STATE.mxcsr.{name}"
        add(field(fid, "mxcsr", "storage", width, 1, fid,
                  ("V1-SECTION-0120",), guards=("SSE capability",),
                  constraints=constraints, tla_ops=("MXCSRWellFormed",),
                  lean_decls=("AMD64.Arch.MXCSR", "AMD64.Arch.MXCSR.Valid")))

    for identifier, component, sources, obligation in [
        ("STATE.memory.bytes", "memory", ("V1-SECTION-0014", "V1-SECTION-0020"),
         "M2 owns byte storage, address translation, access events, and commit semantics."),
        ("STATE.memory.attributes", "memory", ("V1-SECTION-0015", "V1-SECTION-0017", "V1-SECTION-0018"),
         "M2 owns memory attributes, page maps, paging configuration, and access policy."),
        ("STATE.external.io", "external", ("V1-SECTION-0089", "V1-SECTION-0090", "V1-SECTION-0091", "V1-SECTION-0092"),
         "M2 owns typed I/O events and permission context; later instruction bindings own port effects."),
    ]:
        add(field(identifier, component, "delegated-state", None, "unbounded", identifier,
                  sources, representation="delegated-open", validity="delegated-open",
                  opens=(obligation,)))

    representation_counts = {status: sum(row["representation_status"] == status for row in rows)
                             for status in sorted({row["representation_status"] for row in rows})}
    validity_counts = {status: sum(row["validity_status"] == status for row in rows)
                       for status in sorted({row["validity_status"] for row in rows})}
    return {
        "schema_version": 2,
        "authority": authority(),
        "completeness_boundary": (
            "Field rows inventory Volume 1 application-visible state and required context. "
            "Implemented means the CPU-local representation and named validity predicate exist; "
            "it does not close instruction transitions, memory/protection behavior, or full ISA coverage."
        ),
        "summary": {
            "field_rows": len(rows),
            "implemented_rows": sum(row["representation_status"] == "implemented" for row in rows),
            "delegated_open_rows": sum(row["representation_status"] == "delegated-open" for row in rows),
            "representation_status_counts": representation_counts,
            "validity_status_counts": validity_counts,
        },
        "fields": rows,
    }


INFORMATIONAL = set(range(100, 113)) | set(range(168, 180)) | set(range(241, 249)) | set(range(294, 299))
INFORMATIONAL |= {2, 116, 190, 252}

ARCHITECTURAL = set(range(1, 5)) | set(range(8, 36)) | set(range(63, 78))
ARCHITECTURAL |= set(range(113, 123)) | set(range(164, 168)) | {180, 181, 183, 184}
ARCHITECTURAL |= set(range(189, 202)) | {230, 234, 235, 236, 237, 238, 239, 240}
ARCHITECTURAL |= set(range(249, 262)) | {284, 292, 293}

SECTION_FIELDS = {
    3: ["STATE.profile.capability.long-mode"],
    4: ["STATE.gpr.storage", "STATE.rip.storage", "STATE.rflags.cf"],
    8: ["STATE.context.mode"], 9: ["STATE.context.mode"], 10: ["STATE.context.mode"],
    11: ["STATE.context.mode"], 12: ["STATE.context.mode"],
    14: ["STATE.memory.bytes"], 15: ["STATE.memory.attributes"],
    16: ["STATE.segment.cs", "STATE.segment.fs", "STATE.segment.gs"],
    17: ["STATE.profile.physical-address-bits"], 18: ["STATE.memory.attributes"],
    20: ["STATE.memory.bytes"], 21: ["STATE.profile.linear-address-bits"],
    28: ["STATE.rip.storage"], 31: ["STATE.gpr.storage"], 32: ["STATE.gpr.storage"],
    34: ["STATE.rflags.cf", "STATE.rflags.reserved-high"], 35: ["STATE.rip.storage"],
    76: ["STATE.profile.capability.long-mode"], 80: ["STATE.context.cpl"],
    89: ["STATE.external.io"], 90: ["STATE.external.io"], 91: ["STATE.external.io"],
    92: ["STATE.external.io"], 118: ["STATE.vector.zmm", "STATE.mxcsr.invalid"],
    119: ["STATE.vector.zmm", "STATE.vector.xmm", "STATE.vector.ymm"],
    120: ["STATE.mxcsr.invalid", "STATE.mxcsr.reserved-high"],
    158: ["STATE.profile.capability.sse", "STATE.profile.capability.avx"],
    164: ["STATE.vector.zmm", "STATE.mxcsr.invalid"], 165: ["STATE.vector.zmm"],
    167: ["STATE.mmx.view"], 180: ["STATE.profile.capability.avx512"],
    181: ["STATE.vector.zmm"], 183: ["STATE.vector.kmask"], 184: ["STATE.vector.kmask"],
    199: ["STATE.mmx.view"], 200: ["STATE.mmx.view"],
    230: ["STATE.profile.capability.mmx"], 234: ["STATE.mmx.view", "STATE.x87.tags"],
    235: ["STATE.mmx.view", "STATE.x87.physical"], 237: ["STATE.x87.tags"],
    238: ["STATE.x87.physical", "STATE.x87.tags"],
    249: ["STATE.x87.physical", "STATE.x87.status.top"],
    254: ["STATE.x87.physical", "STATE.x87.status.top", "STATE.x87.control.rounding-control"],
    255: ["STATE.x87.physical", "STATE.x87.st"],
    256: ["STATE.x87.status.top", "STATE.x87.status.error-summary"],
    257: ["STATE.x87.control.rounding-control", "STATE.x87.control.reserved-high"],
    258: ["STATE.x87.tags"], 259: ["STATE.x87.last-instruction-pointer", "STATE.x87.last-data-pointer", "STATE.x87.last-opcode"],
    260: ["STATE.x87.last-instruction-pointer", "STATE.x87.last-data-pointer", "STATE.x87.last-opcode"],
    284: ["STATE.profile.capability.x87"], 292: ["STATE.x87.physical", "STATE.x87.tags"],
    293: ["STATE.x87.physical", "STATE.x87.tags"],
}


def build_review(sections, fields):
    field_ids = {row["id"] for row in fields["fields"]}
    rows = []
    for ordinal, source in enumerate(sections, 1):
        if ordinal in INFORMATIONAL:
            classification = "informational"
            rationale = "Historical, editorial, or performance guidance; it does not itself define application-visible storage or a state validity invariant."
            behavior = []
        elif ordinal in ARCHITECTURAL:
            classification = "architectural-obligation"
            rationale = "Defines or constrains application-visible state, execution context, aliasing, feature availability, or a validity condition."
            behavior = []
        else:
            classification = "instruction-behavior-obligation"
            rationale = "Defines instruction families, operands, effects, exceptions, prefixes, or save/restore behavior rather than independent storage."
            behavior = ["Reconcile this section against Volume 3 forms and the owning instruction/memory workstream before claiming semantic coverage."]
        linked = SECTION_FIELDS.get(ordinal, [])
        assert set(linked) <= field_ids
        opens = []
        if classification == "instruction-behavior-obligation":
            opens = ["Instruction transition/form coverage remains open in the parent coverage ledger."]
        if any(field_id.startswith("STATE.memory") or field_id.startswith("STATE.external") for field_id in linked):
            opens.append("Representation and validity are delegated to M2.")
        if classification == "informational":
            disposition = "informational-no-semantic-closure"
        elif classification == "instruction-behavior-obligation" and ordinal >= 113:
            disposition = "outside-volume3-gp-execution-scope"
            behavior = [
                "Do not expand the instruction target to every SIMD, MMX, or x87 instruction. Retain only shared-state, save/restore, alias, exception-context, or form constraints needed by in-scope Volume 3 general-purpose entries."
            ]
        elif classification == "instruction-behavior-obligation":
            disposition = "volume3-gp-cross-check"
        elif linked:
            disposition = "state-field-routed"
        elif source["level"] < 3:
            disposition = "umbrella-routed-to-descendants"
        else:
            disposition = "open-cross-workstream-routing"
            opens.append("This architectural leaf has no direct CPU-field row; its addressing/form/environment obligation remains open in I2 or M2.")
        rows.append({
            "id": source["id"],
            "pdf_page": source["pdf_page"],
            "title": source["title"],
            "classification": classification,
            "coverage_disposition": disposition,
            "rationale": rationale,
            "state_field_ids": linked,
            "behavior_obligations": behavior,
            "dependency_section_ids": [],
            "review_status": "routing-reviewed",
            "semantic_review_status": "targeted-prose-reviewed" if linked else "bookmark-role-reviewed",
            "open_obligations": opens,
            "evidence": [{"kind": "pinned-bookmark", "source_id": source["id"],
                          "pdf_page": source["pdf_page"]}],
        })
        if ordinal == 172:
            # A performance heading does not erase the architectural memory
            # guarantees in its prose. Reviewed against pinned PDF pp269-271.
            rows[-1].update(
                classification="architectural-obligation",
                coverage_disposition="state-field-routed",
                rationale="Streaming-load guidance specifies WC ordering and coherence limits relevant to shared memory attributes and in-scope fences/locked operations.",
                state_field_ids=["STATE.memory.attributes"],
                behavior_obligations=[
                    "Preserve weakly ordered WC accesses and explicit fence/locked-operation synchronization; do not assume streaming-buffer coherence.",
                    "SIMD instruction execution remains outside the Volume 3 general-purpose target; shared memory guarantees remain in scope.",
                ],
                semantic_review_status="targeted-prose-reviewed",
                open_obligations=["Compose WC memory attributes, access events and fence/locked ordering with the memory model."],
                evidence=[{"kind": "pinned-prose", "source_id": source["id"], "pdf_pages": [269, 270, 271]}],
            )
    counts = {kind: sum(row["classification"] == kind for row in rows) for kind in
              ["architectural-obligation", "instruction-behavior-obligation", "informational"]}
    dispositions = {kind: sum(row["coverage_disposition"] == kind for row in rows)
                    for kind in sorted({row["coverage_disposition"] for row in rows})}
    return {
        "schema_version": 2,
        "authority": authority(),
        "completeness_boundary": (
            "Exactly the 298 numbered Volume 1 sections are classified. Classification routes "
            "obligations and is not implementation evidence; state-fields.json and the parent "
            "instruction coverage ledger independently record implementation and open work."
        ),
        "review_method": (
            "Every pinned bookmark title/page was classified by section role. State-bearing "
            "sections were additionally reconciled against the field inventory and targeted prose "
            "for register layouts, aliases, reserved bits, and mode/profile guards."
        ),
        "summary": {"section_rows": len(rows), **counts,
                    "coverage_disposition_counts": dispositions},
        "sections": rows,
    }


def validate(fields, review, sections, all_sections):
    expected = {row["id"]: row for row in sections}
    all_expected = {row["id"]: row for row in all_sections}
    if review["schema_version"] != 2 or fields["schema_version"] != 2:
        raise ValueError("state inventory schema must be version 2")
    rows = review["sections"]
    if len(rows) != 298 or len({row["id"] for row in rows}) != 298:
        raise ValueError("Volume 1 review must contain exactly 298 unique rows")
    if {row["id"] for row in rows} != set(expected):
        raise ValueError("Volume 1 review IDs differ from pinned source inventory")
    ids = {row["id"] for row in fields["fields"]}
    if len(ids) != len(fields["fields"]):
        raise ValueError("state field IDs must be unique")
    for row in rows:
        source = expected[row["id"]]
        if (row["title"], row["pdf_page"]) != (source["title"], source["pdf_page"]):
            raise ValueError(f"{row['id']}: title/page differs from pinned source")
        if row["classification"] not in {"architectural-obligation", "instruction-behavior-obligation", "informational"}:
            raise ValueError(f"{row['id']}: invalid classification")
        if not set(row["state_field_ids"]) <= ids:
            raise ValueError(f"{row['id']}: references unknown field")
    for row in fields["fields"]:
        for source in row["source_sections"]:
            pinned = all_expected[source["id"]]
            if source["pdf_page"] != pinned["pdf_page"] or source["title"] != pinned["title"]:
                raise ValueError(f"{row['id']}: source link differs from pinned inventory")
        if row["representation_status"] == "implemented":
            if not row["tla"]["operators"] or not row["lean"]["declarations"] or not row["evidence"]:
                raise ValueError(f"{row['id']}: implemented row lacks module/check evidence")
    print(f"AMD64 state inventory valid: {len(ids)} field rows; 298 Volume 1 classifications")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["generate", "check"])
    args = parser.parse_args()
    all_sections = source_sections()
    sections = [row for row in all_sections if row["volume"] == 1]
    if args.command == "generate":
        fields = build_fields(all_sections)
        review = build_review(sections, fields)
        dump(FIELDS, fields)
        dump(REVIEW, review)
    fields = load(FIELDS)
    review = load(REVIEW)
    expected_fields = build_fields(all_sections)
    expected_review = build_review(sections, expected_fields)
    if fields != expected_fields or review != expected_review:
        raise SystemExit("Generated state artifacts are stale; run tools/check_amd64_state.py generate")
    validate(fields, review, sections, all_sections)


if __name__ == "__main__":
    main()
