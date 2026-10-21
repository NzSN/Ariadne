#!/usr/bin/env python3
"""Draft W0 independent integer/encoding oracle; never imports Ariadne/BAP/LLVM.

--emit writes JSON expectations under tests/input/fixtures/i5c/. It creates no dump,
build or model process. --check checks the frozen JSON against this source. W0
acceptance also needs the separately run model and later SUT conformance.
"""
import argparse
import copy
import hashlib
import json
import struct
from pathlib import Path

M = 1 << 64
H = 1 << 47
SITE = 0x401000
ROOT = Path(__file__).resolve().parent / "i5c"
FORMS = [
    ("MOV32mi", "c7", 4, 1), ("MOV64mi32", "48c7", 8, 1),
    ("MOV32rm", "8b", 4, 0), ("MOV64rm", "488b", 8, 0),
    ("MOV32mr", "89", 4, 1), ("MOV64mr", "4889", 8, 1),
]
FORM_INFO = {name: (prefix, size, operation) for name, prefix, size, operation in FORMS}


def hx(value):
    return f"0x{value:016x}"


def encoding(form, displacement, *, immediate=5):
    """Hand-reviewed RAX ModRM productions; not a production decoder."""
    prefix, _size, _operation = FORM_INFO[form]
    if displacement == 0:
        modrm, suffix, bits = "00", "", 0
    elif -128 <= displacement <= 127:
        modrm, suffix, bits = "40", (displacement & 255).to_bytes(1, "little").hex(), 8
    else:
        assert -(1 << 31) <= displacement < 1 << 31
        modrm, suffix, bits = "80", (displacement & 0xFFFFFFFF).to_bytes(4, "little").hex(), 32
    tail = immediate.to_bytes(4, "little").hex() if "mi" in form else ""
    return prefix + modrm + suffix + tail, bits


GPRS = ('rax','rcx','rdx','rbx','rsp','rbp','rsi','rdi',
        'r8','r9','r10','r11','r12','r13','r14','r15')


def inspect_encoding(text):
    """Independent finite byte worksheet, with no production decoder imports.

    This covers exactly the hand-reviewed MOV and excluded MOVUPS encodings
    used by this corpus; it is not general ISA admission or semantic lifting.
    """
    data = bytes.fromhex(text)
    at, rex, prefixes = 0, 0, []
    while at < len(data):
        byte = data[at]
        if 0x40 <= byte <= 0x4f:
            rex = byte
        elif byte in (0x66,0x67,0x64,0xf0,0xf2,0xf3):
            prefixes.append(byte)
        else:
            break
        at += 1
    opcode = data[at]
    at += 1
    vector = opcode == 0x0f
    if vector:
        assert data[at] == 0x11, 'unreviewed vector encoding'
        at += 1
        size, form, operation = 16, 'MOVUPSmr', 1
    else:
        assert opcode in (0xc7,0x8b,0x89), 'unreviewed scalar opcode'
        size = 2 if 0x66 in prefixes else 8 if rex & 8 else 4
        suffix, operation = {0xc7:('mi32' if size==8 else 'mi',1),
                             0x8b:('rm',0),0x89:('mr',1)}[opcode]
        form = 'MOV' + str(size*8) + suffix
    modrm = data[at]
    at += 1
    mode, reg, rm = modrm >> 6, (modrm >> 3) & 7, modrm & 7
    assert mode != 3, 'corpus instruction must have memory operand'
    if opcode == 0xc7:
        assert reg == 0
    base, index, scale, rip = None, None, 1, False
    disp_bytes = 1 if mode == 1 else 4 if mode == 2 else 0
    if rm == 4:
        sib = data[at]
        at += 1
        scale = 1 << (sib >> 6)
        idx = (sib >> 3) & 7
        if idx != 4 or rex & 2:
            index = GPRS[idx + (8 if rex & 2 else 0)]
        low_base = sib & 7
        if mode == 0 and low_base == 5:
            disp_bytes = 4
        else:
            base = GPRS[low_base + (8 if rex & 1 else 0)]
    elif mode == 0 and rm == 5:
        disp_bytes = 4
        rip = 0x67 not in prefixes
        base = 'rip' if rip else None
    else:
        base = GPRS[rm + (8 if rex & 1 else 0)]
    displacement = int.from_bytes(data[at:at+disp_bytes], 'little', signed=True) if disp_bytes else 0
    assert len(data[at:at+disp_bytes]) == disp_bytes
    at += disp_bytes
    immediate = None
    if opcode == 0xc7:
        count = 2 if size == 2 else 4
        payload = data[at:at+count]
        assert len(payload) == count
        immediate = int.from_bytes(payload, 'little', signed=size==8) % (1 << (size*8))
        at += count
    assert at == len(data), 'trailing or missing reviewed bytes'
    payload_register = GPRS[reg + (8 if rex & 4 else 0)] if opcode == 0x89 else None
    return dict(opcode=form, length=len(data), memory_operand=1 if opcode==0x8b else 0,
                base=base,index=index,scale=scale,signed_displacement=displacement,
                displacement_width=disp_bytes*8,address_width=32 if 0x67 in prefixes else 64,
                access_width=size*8,operation=operation,rip_relative=rip,
                segment='fs' if 0x64 in prefixes else None,prefixes=[f'{x:02x}' for x in prefixes],
                immediate_payload=immediate,payload_register=payload_register)


def physical_address(receipt, registers):
    width = receipt['address_width']
    base = SITE + receipt['length'] if receipt['rip_relative'] else registers.get(receipt['base'], 0)
    index = registers.get(receipt['index'], 0) * receipt['scale'] if receipt['index'] else 0
    return (base + index + receipt['signed_displacement']) % (1 << width)


def valid_parameter_count(value):
    number=value['parameter_count']
    if type(number)is not int or not 0<=number<=15:
        raise ValueError('invalid-parameter-count: reader binding requires an integer in 0..15 before budgets')


# Pinned producer admission observations; physical arithmetic remains the independent worksheet.
PRODUCER_SELECTION_FACTS = {'operand-size': {'bytes_hex': '66c740100500', 'length': 6, 'opcode': 'MOV16mi', 'receipt_present': False, 'decoder_control': 'Ordinary', 'semantic_control': 'Ordinary', 'semantic_status': 'projected', 'memory_access_shapes': [{'role': 'Store', 'access_width': 16, 'address_width': 64}], 'provenance': 'Verified current public preparation producer03; not arithmetic or conclusion expectations'}, 'vector': {'bytes_hex': '0f1100', 'length': 3, 'opcode': 'MOVUPSmr', 'receipt_present': False, 'decoder_control': 'Ordinary', 'semantic_control': 'Ordinary', 'semantic_status': 'projected', 'memory_access_shapes': [{'role': 'Store', 'access_width': 128, 'address_width': 64}], 'provenance': 'Verified current public preparation producer03; not arithmetic or conclusion expectations'}, 'repeat': {'bytes_hex': 'f3', 'length': 1, 'opcode': 'XRELEASE_PREFIX', 'receipt_present': False, 'decoder_control': 'Ordinary', 'semantic_control': 'Stop', 'semantic_status': 'decode-disagreement', 'memory_access_shapes': [], 'provenance': 'Verified current public preparation producer03; not arithmetic or conclusion expectations'}, 'lock': {'bytes_hex': 'f0', 'length': 1, 'opcode': 'LOCK_PREFIX', 'receipt_present': False, 'decoder_control': 'Ordinary', 'semantic_control': 'Stop', 'semantic_status': 'decode-disagreement', 'memory_access_shapes': [], 'provenance': 'Verified current public preparation producer03; not arithmetic or conclusion expectations'}}


def row(name, *, form="MOV32mi", base=M-8, displacement=16, **changes):
    code, bits = encoding(form, displacement)
    _prefix, size, operation = FORM_INFO[form]
    value = dict(name=name, harness="synthetic-capture", opcode=form, code=code,
                 site=hx(SITE), base_register="rax", base_value=hx(base),
                 signed_displacement=displacement, displacement_width=bits,
                 access_size=size, operation=operation, reported=hx((base+displacement) % M),
                 context_flags=0x100003, parameter_count=2, exception_present=True,
                 context_present=True, context_supported=True, captured=True, receipt=True,
                 early_gaps=[], max_evidence=64, max_claims=64, payload=5)
    value.update(changes)
    if name in PRODUCER_SELECTION_FACTS:
        selected=copy.deepcopy(PRODUCER_SELECTION_FACTS[name])
        value['receipt']=selected['receipt_present']
        value['selected_instruction']=selected
        # Apply the already specified common admission rules to the observed
        # selected shape; never use producer evaluation as the T/q/EA oracle.
        early=set(value['early_gaps'])
        if selected['semantic_status']!='projected':
            early.add('unadmitted-instruction-semantics')
        if selected['opcode']not in FORM_INFO:
            early.add('unsupported-instruction-form')
        if len(selected['memory_access_shapes'])!=1:
            early.add('missing-or-multiple-memory-accesses')
        value['early_gaps']=sorted(early)
    valid_parameter_count(value)
    receipt = inspect_encoding(value['code'])
    # Keep nominal kernel B/D inputs explicit even for excluded shapes; physical
    # operand roles and actual instruction EA live in separate checked fields.
    if 'signed_displacement' not in changes:
        value['signed_displacement'] = receipt['signed_displacement']
    value['opcode'] = receipt['opcode']
    value['displacement_width'] = receipt['displacement_width']
    value['access_size'] = receipt['access_width'] // 8
    if 'operation' not in changes:
        value['operation'] = receipt['operation']
    registers = {name:0 for name in GPRS}
    if receipt['base'] in registers:
        registers[receipt['base']] = base
    elif receipt['index'] in registers:
        registers[receipt['index']] = base
    if receipt['index'] and 'index_value' in value:
        registers[receipt['index']] = value['index_value']
    if receipt['payload_register'] and 'payload_register' in value:
        assert value['payload_register'] == receipt['payload_register']
        registers[receipt['payload_register']] = value['payload']
    actual = physical_address(receipt, registers)
    if 'reported' not in changes:
        value['reported'] = hx(actual)
    if receipt['immediate_payload'] is not None:
        value['payload'] = receipt['immediate_payload']
    elif receipt['payload_register']:
        value['payload'] = registers[receipt['payload_register']] % (1 << receipt['access_width'])
    else:
        value['payload'] = None
    value['registers'] = {name:hx(number) for name,number in registers.items()}
    value['decoded_receipt'] = receipt
    value['actual_effective_address'] = hx(actual)
    value['encoded_base_matches_kernel'] = receipt['base'] == value['base_register']
    return value


def expected(value):
    valid_parameter_count(value)
    base, displacement = int(value["base_value"], 16), value["signed_displacement"]
    total = base + displacement
    quotient, ea = divmod(total, M)  # Independent Euclidean division, not SUT branches.
    assert quotient in (-1, 0, 1)
    flags = value["context_flags"]
    control, integer = bool(flags & 1), bool(flags & 2)
    registers = ((3 if control else 0) + (15 if integer else 0)) if value["context_supported"] else 0
    tags = ["instruction"]
    if value["exception_present"]:
        tags += ["record"]
        if value["context_present"]:
            tags += ["context"]
        tags += ["field"] * (8 + value["parameter_count"])
        if value["context_present"]:
            tags += ["field"] * (1 + registers)
    if value["receipt"]:
        tags += ["receipt"]
    retained = tags[:value["max_evidence"]]
    observed = sum(tag == "field" or (tag == "instruction" and value["captured"]) for tag in retained)
    complete = len(retained) == len(tags)
    early = set(value["early_gaps"])
    if not value["receipt"]:
        early.add("missing-decoded-address-reference")
    if not control:
        early.add("missing-or-mismatched-exception-rip")
    if not (control if value["base_register"] == "rsp" else integer):
        early.add("missing-valid-register:" + value["base_register"])
    if not value["exception_present"]:
        early.add("missing-exception-stream")
    if not value["context_supported"]:
        early.add("missing-or-unsupported-exception-context")
    if value["parameter_count"] < 2:
        early.add("missing-access-violation-parameters")
    semantic_arithmetic = not early
    needed = observed + (5 if semantic_arithmetic and complete else 0) + 1
    claims_fit = needed <= value["max_claims"]
    retained_arithmetic = semantic_arithmetic and complete and claims_fit
    gaps = set(early)
    if not complete:
        gaps.add("budget-evidence")
    if not claims_fit:
        gaps.add("budget-claims")
    end = ea + value["access_size"]
    range_ok = end < M and end <= H  # checked u64 end; H admission is independent.
    reported = int(value["reported"], 16)
    byte_ok = end < M and ea <= reported < end
    if semantic_arithmetic:
        if not range_ok:
            gaps.add("unsupported-access-range")
        if not byte_ok:
            gaps.add("reported-data-address-mismatch")
    conclusion = "unknown"
    if retained_arithmetic and range_ok and byte_ok:
        conclusion = "consistent_with_evidence" if quotient else "refuted_under_premises"
    claims_used = needed if claims_fit else min(observed, value["max_claims"]) + int(value["max_claims"] > observed)
    arithmetic = (dict(base_register=value["base_register"], base_value=hx(base),
                       signed_displacement=displacement, displacement_bits=hx(displacement % M),
                       sum_before_reduction=str(total), quotient=quotient,
                       wrap_kind={-1:"lower", 0:"none", 1:"upper"}[quotient], effective_address=hx(ea))
                  if retained_arithmetic else None)
    return dict(conclusion=conclusion, arithmetic=arithmetic, inputs_complete=complete,
                input_evidence_count=len(tags), retained_evidence_count=len(retained),
                observed_claims=observed, required_claims=needed, retained_claims=claims_used,
                truncated=not complete or not claims_fit, required_gaps=sorted(gaps),
                arithmetic_diagnostic=dict(T=str(total), q=quotient, EA=hx(ea),
                    scope="Nominal unsigned B plus signed encoded D only; excluded indexed/RIP/absolute forms do not establish this as their instruction EA."))


def decision_cases():
    result = []
    grid = [
        ("upper", M-8, 16), ("upper-boundary", M-8, 8),
        ("ordinary-positive", 8, 8), ("no-displacement", 8, 0),
        ("negative-zero", 8, -8), ("negative-nonzero", 16, -8),
        ("underflow", 0, -8), ("disp8-min", 128, -128),
        ("disp8-max", M-127, 127), ("disp32-min", 1 << 31, -(1 << 31)),
        ("disp32-max", M-1, (1 << 31)-1),
    ]
    for form, _prefix, _size, _operation in FORMS:
        result += [row(form.lower()+"-"+suffix, form=form, base=b, displacement=d)
                   for suffix, b, d in grid]
    assert len(result) == 66
    result += [
        row("lower-disp32-min", base=0, displacement=-(1 << 31)),
        row("nonwrapping-high-base", base=M-1, displacement=0),
        row("span-end-h32", base=H-4, displacement=0),
        row("span-end-h64", form="MOV64mi32", base=H-8, displacement=0),
        row("span-cross-h32", base=H-3, displacement=0),
        row("span-cross-h64", form="MOV64mi32", base=H-4, displacement=0),
        row("span-wrap32", base=M-2, displacement=0),
        row("span-wrap64", form="MOV64mi32", base=M-4, displacement=0),
        row("reported-last32", reported=hx(11)),
        row("reported-last64", form="MOV64mi32", reported=hx(15)),
        row("reported-before", reported=hx(7)),
        row("reported-after32", reported=hx(12)),
        row("reported-after64", form="MOV64mi32", reported=hx(16)),
        row("rsp-sib-upper", code="c744241005000000", base_register="rsp", context_flags=0x100001),
        row("rbp-zero-disp8", code="c7450005000000", base_register="rbp", base=8, displacement=0, displacement_width=8),
        row("r12-sib-upper", code="41c744241005000000", base_register="r12"),
        row("r13-upper", code="41c7451005000000", base_register="r13"),
        row("payload-immediate-zero", code="c7401000000000", payload=0),
        row("payload-register-zero", form="MOV32mr", code="894810", payload=0, payload_register="rcx"),
        row("payload-register-nonzero", form="MOV32mr", code="894810", payload=0x12345678, payload_register="rcx"),
    ]
    assert len(result) == 86
    negatives = [
        ("indexed-zero", "c744481005000000", "unsupported-decoded-address-profile", {}),
        ("indexed-nonzero", "c744481005000000", "unsupported-decoded-address-profile", {"index_value": 9}),
        ("index-only", "c704051000000005000000", "unsupported-encoded-base", {}),
        ("absolute", "c704251000000005000000", "unsupported-encoded-base", {}),
        ("rip-relative", "488b0510000000", "unsupported-encoded-base", {"harness":"bound-unit"}),
        ("merged-base-index", "c744001005000000", "unsupported-decoded-address-profile", {}),
        ("segment-fs", "64c7401005000000", "unsupported-instruction-prefix", {}),
        ("address-size", "67c7401005000000", "unsupported-instruction-prefix", {}),
        ("operand-size", "66c740100500", "unsupported-instruction-prefix", {}),
        ("repeat", "f3c7401005000000", "unsupported-instruction-prefix", {}),
        ("lock", "f0c7401005000000", "unsupported-instruction-prefix", {}),
        ("wrong-context-architecture", None, "missing-or-unsupported-exception-context", {"context_flags":0x200003,"context_supported":False}),
        ("vector", "0f1100", "unsupported-instruction-form", {}),
        ("multiple-access", None, "missing-or-multiple-memory-accesses", {"harness":"bound-unit"}),
        ("missing-integer", None, "missing-valid-register:rax", {"context_flags":0x100001}),
        ("missing-control", None, "missing-or-mismatched-exception-rip", {"context_flags":0x100002}),
        ("rsp-missing-control", "c744241005000000", "missing-valid-register:rsp", {"base_register":"rsp","context_flags":0x100002}),
        ("no-parameters", None, "missing-access-violation-parameters", {"parameter_count":0}),
        ("one-parameter", None, "missing-access-violation-parameters", {"parameter_count":1}),
        ("wrong-exception", None, "unsupported-exception-kind", {"exception_code":0x80000003}),
        ("execute", None, "unsupported-access-kind", {"operation":8}),
        ("chained-record", None, "chained-or-missing-exception-record", {"chain":0x1234}),
        ("unknown-flags", None, "unsupported-exception-flags", {"exception_flags":0x100}),
        ("wrong-exception-location", None, "exception-location-mismatch", {"exception_location":hx(SITE+1)}),
        ("wrong-rip", None, "missing-or-mismatched-exception-rip", {"rip":hx(SITE+1)}),
        ("wrong-operation", None, "access-kind-mismatch", {"operation":0}),
        ("linux", None, "unsupported-platform", {"platform":"linux-amd64"}),
        ("no-context", None, "missing-or-unsupported-exception-context", {"context_present":False,"context_supported":False}),
        ("no-exception", None, "missing-exception-stream", {"exception_present":False,"context_present":False,"context_supported":False}),
        ("thread-fallback", None, "missing-valid-register:rax", {"context_flags":0x100001,"thread_list_context":True}),
    ]
    for name, code, gap, changes in negatives:
        changes = dict(changes)
        if code is not None:
            changes["code"] = code
        result.append(row(name, early_gaps=[gap], **changes))
    assert len(result) == 116
    for name, gap, extra in [
        ("missing-decoded-receipt", "missing-decoded-address-reference", {"receipt":False}),
        ("decoder-bap-base-disagreement", "decoded-bil-address-disagreement", {"substitution":"BAP term bank"}),
        ("decoder-bap-constant-disagreement", "decoded-bil-address-disagreement", {"substitution":"BAP modular constant"}),
        ("decoder-bap-width-disagreement", "decoded-bil-address-disagreement", {"substitution":"BAP access width"}),
        ("missing-decoder-identity", "unsupported-decoded-address-profile", {"substitution":"decoder hash absent"}),
        ("different-decoder-target", "unsupported-decoded-address-profile", {"substitution":"legitimately supplied Linux decoder target"}),
        ("site-not-reached", "site-not-reached", {"substitution":"prepared site outside local discovery"}),
        ("unadmitted-semantics", "unadmitted-instruction-semantics", {"substitution":"opaque semantics"}),
    ]:
        result.append(row(name, harness="bound-unit", early_gaps=[gap], **extra))
    assert len(result) == 124
    budgets = [(0,64),(1,64),(31,64),(32,64),(33,64),(34,64),
               (64,0),(64,30),(64,35),(64,36),(64,37),(0,0)]
    for evidence, claims in budgets:
        result.append(row(f"budget-e{evidence}-c{claims}", harness="bound-unit",
                          max_evidence=evidence, max_claims=claims))
    for evidence, claims in [(45,64),(46,49),(64,48),(64,49)]:
        result.append(row(f"budget-max-bundle-e{evidence}-c{claims}", harness="bound-unit",
                          parameter_count=15, max_evidence=evidence, max_claims=claims))
    assert len(result) == 140 and len({item["name"] for item in result}) == 140
    return [dict(value, expected=expected(value)) for value in result]


BINDING_NEGATIVES = [
    "snapshot-id", "artifact-sha256", "query-id", "request-sha256", "semantic-profile",
    "mutable-reader-metadata", "outside-query-site", "invalid-access-index",
    "receipt-address", "receipt-bytes", "receipt-opcode", "receipt-length",
    "receipt-raw-row", "receipt-decoder-hash", "fault-field-bytes", "fault-span-hash",
    "duplicate-fault-field", "invalid-context-validity-claim", "invalid-parameter-count",
]
SERIALIZATION_NEGATIVES = [
    "duplicate-json-member", "unknown-top-level-field", "unknown-arithmetic-field",
    "sum-json-number", "sum-plus-sign", "sum-leading-zero", "sum-negative-zero",
    "sum-empty", "sum-whitespace", "sum-over-21-chars", "sum-below-domain",
    "sum-above-domain", "sum-not-B-plus-D", "wrong-wrap-kind", "wrong-effective-address",
    "wrong-signed-displacement", "arithmetic-through-early-gap", "definite-through-late-gap",
    "definite-through-budget-gap", "scope-digest", "content-digest", "dangling-evidence-ref",
    "cross-scope-claim-ref", "forged-observed-arithmetic",
]
CLI_NEGATIVES = [
    "with-zero-address", "with-zero-base-offset", "with-explanation", "with-stateflow",
    "out-of-query-site", "invalid-access-index", "site-remains-seed-not-root",
    "default-native-ownership", "explicit-rust-rollback", "transactional-render-failure",
    "transactional-native-failure", "unknown-assessment-render-order",
]
MUTATIONS = [
    ("signed-base", "mov32mi-upper", "convert B through i64 before i128"),
    ("unsigned-displacement", "mov32mi-negative-zero", "convert D through u64 before i128"),
    ("unsigned-carry", "mov32mi-negative-nonzero", "classify wrap using overflowing_add(D as u64)"),
    ("absolute-displacement", "mov32mi-negative-nonzero", "replace D with abs(D)"),
    ("strict-upper-bound", "mov32mi-upper-boundary", "use T > M instead of T >= M"),
    ("reduced-before-sum", "mov32mi-upper", "store u64-reduced sum as T"),
    ("disp8-sign", "mov32mi-disp8-min", "interpret disp8 as unsigned"),
    ("disp32-sign", "mov32mi-disp32-min", "interpret disp32 as unsigned"),
    ("bap-ea-agreement", "decoder-bap-constant-disagreement", "omit decoded/BAP constant agreement"),
    ("decoded-base-agreement", "decoder-bap-base-disagreement", "omit decoded/BAP base agreement"),
    ("zero-index-admission", "indexed-zero", "admit an encoded index when its captured value is zero"),
    ("missing-base-validity", "missing-integer", "substitute raw/default base despite invalid INTEGER"),
    ("operation-treated-late", "wrong-operation", "retain arithmetic through operation mismatch"),
    ("wrapping-access-end", "span-wrap64", "use wrapping access end instead of checked end"),
    ("omit-lower-range", "mov32mi-underflow", "remove end <= H admission"),
    ("reported-equals-ea-only", "reported-last32", "require reported byte == EA"),
    ("inclusive-reported-end", "reported-after32", "allow reported byte == exclusive end"),
    ("unknown-becomes-refuted", "missing-decoded-receipt", "refute missing encoded evidence"),
    ("evidence-budget-facts", "budget-e32-c64", "keep arithmetic after mandatory evidence omission"),
    ("claim-budget-facts", "budget-e64-c35", "keep arithmetic after atomic derived-claim omission"),
    ("zero-budget-skips-binding", "binding:receipt-bytes", "return early Unknown before binding validation"),
    ("skip-wide-recomputation", "serialization:sum-not-B-plus-D", "accept forged T in strict validator"),
    ("skip-reference-closure", "serialization:dangling-evidence-ref", "accept dangling claim reference"),
    ("question-seed-is-root", "cli:site-remains-seed-not-root", "insert assessment site into entry roots"),
]


OWNED_RECIPES = [
    dict(name='upper',code='c7411005000000',rcx=hx(M-8),rdx=hx(0),expected='consistent_with_evidence'),
    dict(name='none',code='c70105000000',rcx=hx(8),rdx=hx(0),expected='refuted_under_premises'),
    dict(name='negative',code='c741f805000000',rcx=hx(16),rdx=hx(0),expected='refuted_under_premises'),
    dict(name='indexed',code='c744111005000000',rcx=hx(M-8),rdx=hx(0),expected='unknown'),
]


def build_synthetic_capture(value):
    """Small product-independent raw minidump for synthetic-capture cases only."""
    valid_parameter_count(value)
    assert value['harness'] == 'synthetic-capture'
    data, streams = bytearray(32), []
    def append(payload):
        offset = len(data)
        data.extend(payload)
        return offset
    def stream(kind,payload):
        offset=append(payload)
        streams.append((kind,len(payload),offset))
        return offset
    system=bytearray(56)
    struct.pack_into('<H',system,0,9)
    struct.pack_into('<I',system,20,0x8201 if value.get('platform')=='linux-amd64' else 2)
    stream(7,system)
    code=bytes.fromhex(value['code'])+b'\xc3'
    code_offset=append(code)
    stream(5,struct.pack('<IQII',1,SITE,len(code),code_offset))
    context=bytearray(1232)
    struct.pack_into('<I',context,48,value['context_flags'])
    for index,name in enumerate(GPRS):
        struct.pack_into('<Q',context,120+8*index,int(value['registers'][name],16))
    struct.pack_into('<Q',context,248,int(value.get('rip',hx(SITE)),16))
    context_offset=append(context)
    if value.get('thread_list_context'):
        other=bytearray(context)
        struct.pack_into('<I',other,48,0x100003)
        other_offset=append(other)
        thread=bytearray(48)
        struct.pack_into('<I',thread,0,17)
        struct.pack_into('<II',thread,40,len(other),other_offset)
        stream(3,struct.pack('<I',1)+thread)
    if value['exception_present']:
        exception=bytearray(168)
        struct.pack_into('<I',exception,0,17)
        count=value['parameter_count']
        struct.pack_into('<IIQQI',exception,8,value.get('exception_code',0xc0000005),
            value.get('exception_flags',0),value.get('chain',0),
            int(value.get('exception_location',hx(SITE)),16),count)
        parameters=[value['operation'],int(value['reported'],16)]+[0]*13
        for index,number in enumerate(parameters[:count]):
            struct.pack_into('<Q',exception,40+8*index,number)
        struct.pack_into('<II',exception,160,len(context) if value['context_present'] else 0,context_offset)
        stream(6,exception)
    directory=len(data)
    for item in streams:
        data.extend(struct.pack('<III',*item))
    struct.pack_into('<4sIII',data,0,b'MDMP',0xa793,len(streams),directory)
    return bytes(data)


def validate_artifacts(records):
    cases=records['manifest.json']['cases']
    names={value['name'] for value in cases}
    assert len(cases)==len(names)==140
    for value in cases:
        facts=value['expected']['arithmetic']
        receipt=value['decoded_receipt']
        assert receipt==inspect_encoding(value['code'])
        assert int(value['actual_effective_address'],16)==physical_address(
            receipt,{name:int(number,16) for name,number in value['registers'].items()})
        if facts:
            assert value['encoded_base_matches_kernel']
            assert int(facts['effective_address'],16)==int(value['actual_effective_address'],16)
            assert int(facts['sum_before_reduction'])==facts['quotient']*M+int(facts['effective_address'],16)
        if value['harness']=='synthetic-capture':
            payload=build_synthetic_capture(value)
            assert payload[:4]==b'MDMP' and len(payload)<4096
    for row in MUTATIONS:
        observer=row[1]
        assert observer in names or observer.startswith(('binding:','serialization:','cli:')),observer
    assert len(BINDING_NEGATIVES)==len(set(BINDING_NEGATIVES))==19
    assert len(SERIALIZATION_NEGATIVES)==len(set(SERIALIZATION_NEGATIVES))==24
    assert len(CLI_NEGATIVES)==len(set(CLI_NEGATIVES))==12
    assert len(MUTATIONS)==len({row[0] for row in MUTATIONS})==24
    assert len(records['performance.json']['fixtureCases'])==10
    assert set(records['performance.json']['fixtureCases'])<=names
    for recipe in OWNED_RECIPES:
        receipt=inspect_encoding(recipe['code'])
        registers={'rcx':int(recipe['rcx'],16),'rdx':int(recipe['rdx'],16)}
        assert physical_address(receipt,registers)==8
        assert receipt['base']=='rcx' and receipt['signed_displacement'] in (-8,0,16)
    assert len(records['owned-captures.json']['cases'])==8


def artifacts():
    cases = decision_cases()
    records = {
        "manifest.json": {"schema":"ariadne.i5c-w0-oracle/v1", "status":"draft-unqualified",
                          "decision_case_count":140, "form_grid_count":66, "boundary_count":20,
                          "negative_capture_count":30, "adapter_case_count":8, "budget_case_count":16,
                          "cases":cases,
                          "gap_policy":"required_gaps are a minimum mandatory subset, not an exact inherited gap list",
                          "nominal_kernel_policy":"base_value/signed_displacement supply the mathematical B+D kernel; decoded_receipt/registers/actual_effective_address are the separate physical tuple for excluded forms",
                          "producer_selection_policy":"code/opcode/access_size/decoded_receipt describe the independent full captured-sequence worksheet. When selected_instruction is present, its bytes/length/opcode/access shapes describe the actually prepared selected site. Nominal B+D diagnostics never establish arithmetic of an isolated selected prefix."},
        "qualification-matrix.json": {"schema":"ariadne.i5c-w0-matrix/v1", "decision_cases":140,
            "binding_rejections":[{"name":name,"expected":"Err before budgets","budgets":[[64,64],[0,0]]} for name in BINDING_NEGATIVES],
            "serialized_rejections":[{"name":name,"expected":"Err in parse/validate/every renderer"} for name in SERIALIZATION_NEGATIVES],
            "cli_cases":CLI_NEGATIVES,"owned_controlled_cases":8,"compiled_mutants":24,
            "legacy_outputs":{"i5a":246,"i5b":342,"i5b_upstream":6,"base_and_explanation":72,"total":666,
                "base_and_explanation_cases":["linux-stage-b","windows-stage-b","bap-precision-not","pinned-real-capture"],
                "base_and_explanation_backends":["rust","default","bap"],
                "files_per_bundle":["report.txt","report.json","report.dot","explanation.txt","explanation.json","explanation.dot"]}},
        "mutations.json": {"schema":"ariadne.i5c-w0-mutations/v1","count":24,
            "records":[{"name":name,"observer_case":case,"behavioral_change":change,
                        "credit":"passing control plus compiled mutant rejected by unchanged independent observer"}
                       for name,case,change in MUTATIONS]},
        "performance.json": {"schema":"ariadne.i5c-performance-contract/v1","frozenDate":"2026-10-20",
            "maxPhaseMedianMs":10,"maxCliMedianMs":1500,"warmups":1,"measuredRepeats":5,
            "maxEvidence":64,"maxClaims":64,
            "fixtureCases":[form.lower()+"-upper" for form, *_ in FORMS]+[
                "mov32mi-negative-zero","mov32mi-underflow","indexed-zero","missing-integer"],
            "controlledCases":[f"{recipe}-{mode}" for recipe in ["upper","none","negative","indexed"] for mode in ["partial","full"]],
            "independentI4BudgetsMs":{"windows":2000,"linux":250},
            "scope":"Each named workload separately; no pooled median or inherited acceptance."},
    }
    records['owned-captures.json']={
        'schema':'ariadne.i5c-w0-owned-recipes/v1','status':'specified-not-captured',
        'cases':[dict(recipe,mode=mode,case=recipe['name']+'-'+mode,
                      decoded_receipt=inspect_encoding(recipe['code']),EA=hx(8))
                 for recipe in OWNED_RECIPES for mode in ('partial','full')],
        'scope':'Eight new native Windows owned captures are required; recipes and witness intent are not observed capture evidence.'}
    validate_artifacts(records)
    return records


def raw_corpus_manifest(cases):
    rows=[]
    for value in cases:
        if value['harness']!='synthetic-capture':
            continue
        payload=build_synthetic_capture(value)
        rows.append({'name':value['name'],'bytes':len(payload),
                     'sha256':hashlib.sha256(payload).hexdigest()})
    return {'schema':'ariadne.i5c-raw-fixture-corpus/v1','case_count':114,
            'layout':'tests/input/fixtures/i5c/dumps/<name>.dmp',
            'required_before_W1':True,'cases':rows,
            'scope':'Deterministic synthetic raw inputs; not real captures or SUT qualification.'}


def check_raw_corpus(directory, corpus):
    expected={row['name']+'.dmp' for row in corpus['cases']}|{'manifest.json'}
    assert {path.name for path in directory.iterdir()}==expected,'unexpected/missing raw fixture corpus members'
    observed=json.loads((directory/'manifest.json').read_text())
    assert observed['cases']==corpus['cases'],'raw fixture corpus manifest differs'
    for row in corpus['cases']:
        path=directory/(row['name']+'.dmp')
        assert path.is_file()and path.stat().st_size==row['bytes']
        assert hashlib.sha256(path.read_bytes()).hexdigest()==row['sha256'],row['name']


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--emit",action="store_true")
    parser.add_argument("--check",action="store_true")
    parser.add_argument('--dump-output',type=Path,help='new remote task-owned directory for product-independent synthetic dumps')
    args=parser.parse_args()
    assert args.emit != args.check, "select --emit or --check"
    records=artifacts()
    ROOT.mkdir(parents=True,exist_ok=True)
    records['raw-corpus.json']=raw_corpus_manifest(records['manifest.json']['cases'])
    for name,value in records.items():
        payload=(json.dumps(value,indent=2,sort_keys=True)+"\n").encode()
        target=ROOT/name
        if args.emit:
            target.write_bytes(payload)
        else:
            assert target.read_bytes()==payload, name
    if args.dump_output:
        output=args.dump_output.resolve()
        output.mkdir(parents=True,exist_ok=False)
        manifest=[]
        for value in records['manifest.json']['cases']:
            if value['harness']!='synthetic-capture':
                continue
            payload=build_synthetic_capture(value)
            (output/(value['name']+'.dmp')).write_bytes(payload)
            manifest.append({'name':value['name'],'bytes':len(payload),
                             'sha256':hashlib.sha256(payload).hexdigest()})
        (output/'manifest.json').write_text(json.dumps({'scope':'Synthetic captures only; bound-unit substitutions require separate controlled adapters','cases':manifest},indent=2,sort_keys=True)+'\n')
    default_raw=ROOT/'dumps'
    if default_raw.exists():
        check_raw_corpus(default_raw,records['raw-corpus.json'])
    if args.dump_output:
        check_raw_corpus(args.dump_output.resolve(),records['raw-corpus.json'])
    cases=records["manifest.json"]["cases"]
    for case in cases:
        value=case["expected"]
        if value["arithmetic"]:
            facts=value["arithmetic"]
            assert int(facts["sum_before_reduction"]) == facts["quotient"]*M+int(facts["effective_address"],16)
        if value["conclusion"]!="unknown":
            assert value["arithmetic"] is not None
            assert value["arithmetic"]["quotient"] in (0,1)
    assert len(BINDING_NEGATIVES)==19 and len(SERIALIZATION_NEGATIVES)==24 and len(CLI_NEGATIVES)==12 and len(MUTATIONS)==24
    print(json.dumps({"generated" if args.emit else "checked":True,"decision_cases":140,
                      "binding_rejections":19,"serialization_rejections":24,"cli_cases":12,
                      "mutation_count":24,"model_or_sut_exercised":False,
                      "raw_corpus_materialized":default_raw.is_dir(),
                      "raw_corpus_required_before_W1":True,
                      "files":{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in records}},indent=2))


if __name__=="__main__":
    main()
