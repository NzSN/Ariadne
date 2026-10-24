#!/usr/bin/env python3
"""Strict finite byte domains with a bounded dependent address grammar.

The generic enumerator establishes only the domain written in its input. The
separate reviewed MOV8 validator prevents a narrowed grammar from becoming a
smaller self-certified architectural denominator.
"""
import argparse
import hashlib
import itertools
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "ariadne.amd64-finite-domain/v4"
MEMORY_SCHEMA = "ariadne.amd64-finite-domain/v5"
MOV8_SCOPE = "amd-long64-canonical-mov8-register/v1"
PACK_PATH = "tests/bap/fixtures/amd64-semantics/mov8-domain/source-constraints.json"
DOMAIN_PATH = "tests/bap/fixtures/amd64-semantics/mov8-domain/legal-domain.json"
MOV8_ENVIRONMENT = {"vendor": "AMD", "mode": 64, "operandBits": 8, "addressBits": 64}
MOV8_FORMS = {"mov8-register-88": "88", "mov8-register-8a": "8a"}
MOV8_EXCLUSIONS = ["memory-operands", "other-opcodes", "legacy-prefixes", "repeated-prefixes",
                   "rex-w-or-x-set", "non-amd-or-non-long64", "exceptional-or-interrupted-outcomes"]
MEMORY_SCOPE = "amd-long64-bounded-mov8-memory/v1"
ARCHITECTURE_PACK_PATH = "tests/bap/fixtures/amd64-semantics/architecture-constraints-v1.json"
MEMORY_FORMS = {"mov8-memory-store-88": "88", "mov8-memory-load-8a": "8a"}
MEMORY_RULES = {"prefix-group-order", "legacy-prefix-byte-groups", "rex-placement-count",
    "instruction-length-limit", "operand-size-override",
    "address-size-override", "address-size-truncation", "modrm-fields",
    "modrm-memory-displacements", "sib-presence", "sib-fields-scale", "sib-address-equation",
    "rex-register-extension", "rex-index-extension", "rex-base-extension", "rex-high-byte-exclusion",
    "rip-relative-selector", "rip-relative-next-ip", "sib-base5-no-base", "sib-index4-no-index",
    "signed-displacement", "flat-data-segments"}
MEMORY_EXCLUSIONS = ["register-direct-operands", "other-opcodes", "noncanonical-or-repeated-prefixes",
    "legacy-prefixes-other-than-single-address-override", "rex-w-set", "other-modrm-register-or-rm-fields",
    "other-sib-fields", "other-displacement-values", "non-amd-or-non-long64",
    "nonzero-ds-or-ss-base", "exceptional-or-interrupted-outcomes"]


class DomainUnknown(ValueError):
    """Unsupported grammar or exhausted finite work leaves the query unknown."""


def require(condition, message):
    if not condition:
        raise ValueError(message)


def fields(value, keys, label):
    require(isinstance(value, dict) and set(value) == set(keys), label + " fields")


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    raw = Path(path).read_bytes()
    require(len(raw) <= 16 * 1024 * 1024, "finite-domain input byte budget")
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "duplicate JSON key")
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=unique,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError("nonfinite JSON")))


class Budget:
    def __init__(self, limit):
        require(type(limit) is int and 0 < limit <= 10000000, "invalid finite work budget")
        self.remaining = limit

    def consume(self, count=1):
        if count > self.remaining:
            raise DomainUnknown("finite domain work budget exhausted")
        self.remaining -= count


def point_key(point):
    fields(point, {"bytes", "environment", "form"}, "domain point")
    return point["form"], point["bytes"], canonical(point["environment"])


def _bytes(value):
    require(isinstance(value, str) and bool(value) and len(value) % 2 == 0
            and re.fullmatch(r"[0-9a-f]+", value), "literal consumed bytes")
    data = bytes.fromhex(value)
    require(len(data) <= 15, "literal exceeds instruction length")
    return data


def _values(values, bits):
    require(isinstance(values, list) and values and all(type(value) is int and 0 <= value < 1 << bits for value in values)
            and len(set(values)) == len(values), "finite unsigned field values")
    return values


def _address_node(node, budget):
    """Emit complete memory addressing tails for the explicitly selected fields."""
    fields(node, {"kind", "name", "mod", "reg", "rm", "sib", "displacements"}, "dependent address")
    mods, regs, rms = _values(node["mod"], 2), _values(node["reg"], 3), _values(node["rm"], 3)
    require(set(mods) <= {0, 1, 2}, "dependent address node excludes register-direct operands")
    fields(node["sib"], {"scale", "index", "base"}, "dependent SIB")
    scales, indices, bases = (_values(node["sib"][name], bits)
                              for name, bits in (("scale", 2), ("index", 3), ("base", 3)))
    fields(node["displacements"], {"8", "32"}, "dependent displacements")
    for width in (8, 32):
        values = node["displacements"][str(width)]
        require(isinstance(values, list) and values and all(type(value) is int
                and -(1 << (width - 1)) <= value < (1 << (width - 1)) for value in values)
                and len(set(values)) == len(values), "signed displacement values")
    result = []
    for mod, reg, rm in itertools.product(mods, regs, rms):
        sibs = [None] if rm != 4 else list(itertools.product(scales, indices, bases))
        for sib in sibs:
            width = 8 if mod == 1 else 32 if mod == 2 or mod == 0 and (
                rm == 5 or sib is not None and sib[2] == 5) else 0
            displacements = node["displacements"][str(width)] if width else [0]
            for displacement in displacements:
                budget.consume()
                prefix = bytes([(mod << 6) | (reg << 3) | rm])
                if sib is not None:
                    prefix += bytes([(sib[0] << 6) | (sib[1] << 3) | sib[2]])
                result.append(prefix + (displacement.to_bytes(width // 8, "little", signed=True) if width else b""))
    return result


def _node(node, names, budget, *, dependent=False):
    require(isinstance(node, dict) and isinstance(node.get("kind"), str), "domain node")
    kind = node["kind"]
    if kind == "literal":
        fields(node, {"kind", "bytes"}, "literal")
        return [_bytes(node["bytes"])]
    if kind == "modrm-sib-displacement" and dependent:
        require(isinstance(node.get("name"), str) and node["name"] and node["name"] not in names,
                "duplicate/invalid field name")
        names.add(node["name"])
        return _address_node(node, budget)
    if kind not in {"byte-fields", "uint-le"}:
        raise DomainUnknown("unsupported finite domain node: " + kind)
    require(isinstance(node.get("name"), str) and node["name"] and node["name"] not in names, "duplicate/invalid field name")
    names.add(node["name"])
    if kind == "uint-le":
        fields(node, {"kind", "name", "width", "values"}, "little-endian field")
        require(type(node["width"]) is int and 1 <= node["width"] <= 8, "little-endian field width")
        values = _values(node["values"], node["width"] * 8)
        budget.consume(len(values))
        return [value.to_bytes(node["width"], "little") for value in values]
    fields(node, {"kind", "name", "parts"}, "byte field")
    require(isinstance(node["parts"], list) and node["parts"], "missing byte-field parts")
    mask, part_names, domains = 0, set(), []
    for part in node["parts"]:
        fields(part, {"name", "lsb", "width", "values"}, "byte-field part")
        require(isinstance(part["name"], str) and part["name"] and part["name"] not in part_names, "duplicate part name")
        part_names.add(part["name"])
        lsb, width = part["lsb"], part["width"]
        require(type(lsb) is int and type(width) is int and 0 <= lsb < 8 and 1 <= width <= 8 - lsb, "byte-field bit interval")
        selected = ((1 << width) - 1) << lsb
        require(not mask & selected, "overlapping byte-field parts")
        mask |= selected
        domains.append([value << lsb for value in _values(part["values"], width)])
    require(mask == 255, "byte-field bits omitted")
    product = 1
    for domain in domains:
        product *= len(domain)
    budget.consume(product)
    return [bytes([sum(parts)]) for parts in itertools.product(*domains)]


def _environments(axes, predicate, budget):
    require(isinstance(axes, dict) and axes and isinstance(predicate, dict) and set(predicate) <= set(axes), "environment axes/predicate")
    domains = []
    for name in sorted(axes):
        require(isinstance(name, str) and bool(name), "environment axis name")
        values = axes[name]
        require(isinstance(values, list) and values and all(type(value) in {str, int, bool} for value in values)
                and len({(type(value).__name__, value) for value in values}) == len(values), "typed environment axis")
        selected = predicate.get(name, values)
        require(isinstance(selected, list) and selected and
                len({(type(value).__name__, value) for value in selected}) == len(selected) and
                all(any(type(value) is type(expected) and value == expected for expected in values) for value in selected),
                "environment predicate outside scope")
        domains.append(selected)
    count = 1
    for domain in domains:
        count *= len(domain)
    budget.consume(count)
    return [dict(zip(sorted(axes), values)) for values in itertools.product(*domains)]


def enumerate_domain(document, *, budget=100000):
    """Return complete sorted points or raise; never return a truncated domain."""
    require(isinstance(document, dict) and document.get("schema") in {SCHEMA, MEMORY_SCHEMA}, "finite domain schema")
    dependent = document["schema"] == MEMORY_SCHEMA
    fields(document, {"schema", "scope", "sourcePacks" if dependent else "sourcePack", "forms"}, "finite domain")
    scope = document["scope"]
    fields(scope, {"id", "environmentAxes", "prefixPolicy", "outcome", "exclusions", "sourceComplete", "vendorFullDenominator"}, "scope")
    require(isinstance(scope["id"], str) and scope["id"] and scope["sourceComplete"] is False
            and scope["vendorFullDenominator"] is False, "finite domain cannot grant source/vendor completeness")
    require(isinstance(scope["prefixPolicy"], str) and scope["prefixPolicy"]
            and isinstance(scope["outcome"], str) and scope["outcome"]
            and isinstance(scope["exclusions"], list) and all(isinstance(value, str) and value for value in scope["exclusions"])
            and len(set(scope["exclusions"])) == len(scope["exclusions"]), "scope prefix/outcome/exclusion declarations")
    packs = document["sourcePacks"] if dependent else [document["sourcePack"]]
    require(isinstance(packs, list) and packs, "source-pack identities")
    for pack in packs:
        fields(pack, {"path", "sha256"}, "source-pack identity")
        require(isinstance(pack["path"], str) and bool(pack["path"])
                and isinstance(pack["sha256"], str) and re.fullmatch(r"[0-9a-f]{64}", pack["sha256"]), "source-pack digest")
    require(len({pack["path"] for pack in packs}) == len(packs), "duplicate source pack")
    require(isinstance(document["forms"], list) and document["forms"], "empty finite legal domain")
    work, identities, seen, result = Budget(budget), set(), set(), []
    for form in document["forms"]:
        fields(form, {"id", "meaning", "sourceRules", "alternatives"}, "finite form")
        require(isinstance(form["id"], str) and form["id"] and form["id"] not in identities, "duplicate/empty form")
        identities.add(form["id"])
        require(isinstance(form["meaning"], str) and form["meaning"] and isinstance(form["sourceRules"], list)
                and form["sourceRules"] and all(isinstance(rule, str) and rule for rule in form["sourceRules"])
                and len(set(form["sourceRules"])) == len(form["sourceRules"]), "source-derived form meaning/rules")
        require(isinstance(form["alternatives"], list) and form["alternatives"], "empty alternatives")
        for alternative in form["alternatives"]:
            fields(alternative, {"environment", "sequence"}, "finite alternative")
            require(isinstance(alternative["sequence"], list) and alternative["sequence"], "empty byte sequence")
            names, parts, product = set(), [], 1
            for node in alternative["sequence"]:
                values = _node(node, names, work, dependent=dependent)
                parts.append(values)
                product *= len(values)
            envs = _environments(scope["environmentAxes"], alternative["environment"], work)
            work.consume(product * len(envs))
            for values in itertools.product(*parts):
                encoded = b"".join(values)
                require(0 < len(encoded) <= 15, "consumed instruction length")
                for environment in envs:
                    # General overlap/alias rules are a later stage. Refuse an
                    # overlap rather than silently collapsing it into a set.
                    key = encoded.hex(), canonical(environment)
                    require(key not in seen, "overlapping finite alternatives/forms")
                    seen.add(key)
                    result.append(dict(bytes=encoded.hex(), environment=environment, form=form["id"]))
    return sorted(result, key=lambda point: (point["bytes"], canonical(point["environment"]), point["form"]))


def validate_mov8_domain(document, *, source_pack=None, root=ROOT, budget=100000):
    """Check this reviewed slice against its independent complete byte rule."""
    from amd64_source_constraints import validate_pack_structure
    root = Path(root)
    require(document["sourcePack"] == {"path": PACK_PATH, "sha256": sha(root / PACK_PATH)}, "stale MOV8 source-pack identity")
    source_pack = read(root / PACK_PATH) if source_pack is None else source_pack
    validate_pack_structure(source_pack, root=root)
    require(digest(source_pack) == digest(read(root / PACK_PATH)), "substituted MOV8 source pack")
    expected_scope = dict(id=MOV8_SCOPE, environmentAxes={key: [value] for key, value in MOV8_ENVIRONMENT.items()},
                          prefixPolicy="none-or-single-rex-w0-x0", outcome="normal-completion",
                          exclusions=MOV8_EXCLUSIONS, sourceComplete=False, vendorFullDenominator=False)
    require(canonical(document["scope"]) == canonical(expected_scope), "MOV8 reviewed scope differs")
    require({form["id"] for form in document["forms"]} == set(MOV8_FORMS) and len(document["forms"]) == 2, "MOV8 form omission/duplication")
    all_rules = {rule["id"] for rule in source_pack["clauses"]}
    for form in document["forms"]:
        opcode = MOV8_FORMS[form["id"]]
        expected_rules = all_rules - {"mov8-direction-" + ("8a" if opcode == "88" else "88")}
        require(form["meaning"] == "mov8-register-copy-opcode-" + opcode
                and set(form["sourceRules"]) == expected_rules, "MOV8 meaning/source derivation differs")
    points = enumerate_domain(document, budget=budget)
    expected = {(form, prefix + opcode + format(modrm, "02x"), canonical(MOV8_ENVIRONMENT))
                for form, opcode in MOV8_FORMS.items() for prefix in ("", "40", "41", "44", "45")
                for modrm in range(192, 256)}
    require({point_key(point) for point in points} == expected, "MOV8 source-derived domain has an omission or extra point")
    return points


def decode_mov8_expectation(code):
    """Finite-slice byte roles; production semantics still come from BAP."""
    raw = _bytes(code)
    require(len(raw) in {2, 3}, "MOV8 consumed length")
    rex = raw[0] if len(raw) == 3 else None
    require(rex is None or rex in {0x40, 0x41, 0x44, 0x45}, "MOV8 canonical REX")
    opcode, modrm = raw[-2:]
    require(opcode in {0x88, 0x8a} and modrm >> 6 == 3, "MOV8 register-only opcode/ModRM")
    banks = ("rax", "rcx", "rdx", "rbx", "rsp", "rbp", "rsi", "rdi") + tuple("r" + str(index) for index in range(8, 16))
    def register(index):
        if rex is None and index >= 4:
            return dict(bank=banks[index - 4], byteOffset=1, width=8)
        return dict(bank=banks[index], byteOffset=0, width=8)
    reg = ((modrm >> 3) & 7) + (8 if rex is not None and rex & 4 else 0)
    rm = (modrm & 7) + (8 if rex is not None and rex & 1 else 0)
    source, destination = (reg, rm) if opcode == 0x88 else (rm, reg)
    return dict(source=register(source), destination=register(destination), consumedLength=len(raw),
                flags="unchanged", memory="none", nonDestinationBits="preserved")


def memory_mov8_scope():
    return dict(id=MEMORY_SCOPE, environmentAxes={"vendor": ["AMD"], "mode": [64],
        "operandBits": [8], "addressBits": [32, 64], "segmentModel": ["flat-ds-ss"]},
        prefixPolicy="optional-67-then-optional-single-rex-w0", outcome="normal-completion",
        exclusions=MEMORY_EXCLUSIONS, sourceComplete=False, vendorFullDenominator=False)


def memory_mov8_points():
    """Independent complete denominator for this selected field-value slice.

    The 5,760 members do not exhaust register fields, SIB fields or displacement
    values. This direct construction does not consume the supplied grammar.
    """
    result = []
    for address_bits, rex, (form, opcode), reg, mod, rm in itertools.product(
            (32, 64), (None, *range(0x40, 0x48)), MEMORY_FORMS.items(), (0, 4), (0, 1, 2), (0, 4, 5)):
        for sib in ([None] if rm != 4 else (0x00, 0x05, 0x20, 0x25, 0xc0, 0xc5, 0xe0, 0xe5)):
            width = 1 if mod == 1 else 4 if mod == 2 or mod == 0 and (
                rm == 5 or sib is not None and sib & 7 == 5) else 0
            displacements = (-128, 0, 127) if width == 1 else (-2147483648, 0, 2147483647) if width == 4 else (0,)
            for displacement in displacements:
                code = (b"\x67" if address_bits == 32 else b"") + (bytes([rex]) if rex is not None else b"")
                code += bytes([int(opcode, 16), mod * 64 + reg * 8 + rm])
                if sib is not None:
                    code += bytes([sib])
                if width:
                    code += displacement.to_bytes(width, "little", signed=True)
                result.append(dict(form=form, bytes=code.hex(), environment=dict(vendor="AMD", mode=64,
                    operandBits=8, addressBits=address_bits, segmentModel="flat-ds-ss")))
    return sorted(result, key=lambda point: (point["bytes"], canonical(point["environment"]), point["form"]))


def validate_memory_mov8_domain(document, *, root=ROOT, budget=100000):
    from amd64_source_constraints import validate_pack_structure, validate_architecture_pack_structure
    root = Path(root)
    expected_packs = [{"path": name, "sha256": sha(root / name)}
                      for name in (PACK_PATH, ARCHITECTURE_PACK_PATH)]
    require(document.get("schema") == MEMORY_SCHEMA and document.get("sourcePacks") == expected_packs,
            "stale memory MOV8 source packs")
    instruction = read(root / PACK_PATH)
    architecture = read(root / ARCHITECTURE_PACK_PATH)
    validate_pack_structure(instruction, root=root)
    validate_architecture_pack_structure(architecture, root=root)
    require(MEMORY_RULES <= {clause["id"] for clause in architecture["clauses"]},
            "memory MOV8 architectural rule reference is unresolved")
    require(canonical(document["scope"]) == canonical(memory_mov8_scope()), "memory MOV8 reviewed scope differs")
    require(len(document["forms"]) == 2 and {form["id"] for form in document["forms"]} == set(MEMORY_FORMS),
            "memory MOV8 form omission/duplication")
    for form in document["forms"]:
        opcode = MEMORY_FORMS[form["id"]]
        rules = MEMORY_RULES | {"mov8-direction-" + opcode, "mov-copy-width", "register-code-map",
                                "byte-register-alias-preservation", "flags-unmodified"}
        require(form["meaning"] == "mov8-memory-" + ("store" if opcode == "88" else "load")
                and set(form["sourceRules"]) == rules, "memory MOV8 source derivation differs")
    points = enumerate_domain(document, budget=budget)
    require(points == memory_mov8_points(), "memory MOV8 finite selection omission/extra/overlap")
    return points


def decode_memory_mov8(code):
    """Independent membership/address decoder for the bounded memory slice.

    A rejection means outside this finite selection, not architectural invalidity.
    RIP/EIP bases are resolved from the exact instruction VA and consumed length.
    """
    raw = _bytes(code)
    cursor, address_bits = (1, 32) if raw[0] == 0x67 else (0, 64)
    require(cursor < len(raw), "truncated memory MOV8 prefix")
    rex = raw[cursor] if 0x40 <= raw[cursor] <= 0x47 else None
    cursor += rex is not None
    require(cursor + 2 <= len(raw), "truncated memory MOV8 opcode/ModRM")
    opcode, modrm = raw[cursor:cursor + 2]
    cursor += 2
    mod, reg, rm = modrm >> 6, (modrm >> 3) & 7, modrm & 7
    require(opcode in {0x88, 0x8a} and mod in {0, 1, 2} and reg in {0, 4} and rm in {0, 4, 5},
            "outside finite memory MOV8 opcode/ModRM selection")
    sib = None
    if rm == 4:
        require(cursor < len(raw), "missing dependent SIB")
        sib = raw[cursor]
        cursor += 1
        require(sib >> 6 in {0, 3} and (sib >> 3) & 7 in {0, 4} and sib & 7 in {0, 5},
                "outside finite memory MOV8 SIB selection")
    width = 1 if mod == 1 else 4 if mod == 2 or mod == 0 and (rm == 5 or sib is not None and sib & 7 == 5) else 0
    require(len(raw) == cursor + width, "memory MOV8 dependent displacement/consumed extent")
    displacement = int.from_bytes(raw[cursor:], "little", signed=True) if width else 0
    require(not width or displacement in ((-128, 0, 127) if width == 1 else (-2147483648, 0, 2147483647)),
            "outside finite memory MOV8 displacement selection")
    extension = rex or 0
    data_bank = reg + (8 if extension & 4 else 0)
    data_offset = 0
    if rex is None and reg == 4:
        data_bank, data_offset = 0, 1
    ip_relative = mod == 0 and rm == 5
    no_base = sib is not None and mod == 0 and sib & 7 == 5
    base = None if ip_relative or no_base else ((sib & 7) if sib is not None else rm) + (8 if extension & 1 else 0)
    index_field = (sib >> 3) & 7 if sib is not None else None
    index = None if index_field is None or index_field == 4 and not extension & 2 else index_field + (8 if extension & 2 else 0)
    return dict(operation="store" if opcode == 0x88 else "load", dataBank=data_bank, dataByte=data_offset,
        addressBits=address_bits, base=base, index=index, ipRelative=ip_relative, noBase=no_base,
        scale=1 << (sib >> 6) if sib is not None else 1, displacement=displacement,
        displacementBytes=width, consumedLength=len(raw), flags="unchanged", segmentModel="flat-ds-ss")


def memory_mov8_address(decoded, registers, va):
    """EA = truncate(base + index * scale + signed displacement), then zero extend."""
    require(type(va) is int and 0 <= va < 1 << 64 and len(registers) == 16
            and all(type(value) is int and 0 <= value < 1 << 64 for value in registers), "address input values")
    base = va + decoded["consumedLength"] if decoded["ipRelative"] else (
        registers[decoded["base"]] if decoded["base"] is not None else 0)
    index = registers[decoded["index"]] if decoded["index"] is not None else 0
    return (base + index * decoded["scale"] + decoded["displacement"]) & ((1 << decoded["addressBits"]) - 1)


def validate_partitions(points, partitions):
    """Check disjoint S/U/X accounting separately from implementation evidence."""
    require(isinstance(partitions, list), "partitions must be a list")
    domain = {point_key(point) for point in points}
    require(len(domain) == len(points), "duplicate domain points")
    assigned, identities = {}, set()
    for partition in partitions:
        fields(partition, {"id", "disposition", "points", "reason"}, "finite partition")
        require(isinstance(partition["id"], str) and partition["id"] and partition["id"] not in identities, "duplicate partition")
        identities.add(partition["id"])
        require(partition["disposition"] in {"S", "U", "X"} and isinstance(partition["reason"], str)
                and partition["reason"] and isinstance(partition["points"], list) and partition["points"], "partition disposition/reason/domain")
        for point in partition["points"]:
            key = point_key(point)
            require(key in domain and key not in assigned, "partition outside domain or overlap")
            assigned[key] = partition["disposition"]
    counts = {kind: sum(value == kind for value in assigned.values()) for kind in ("S", "U", "X")}
    holes = sorted(domain - set(assigned))
    return dict(totalDisposition=not holes, implementationDomainComplete=not holes and counts["U"] == counts["X"] == 0,
                supported=counts["S"], unsupported=counts["U"], unresolved=counts["X"], holes=holes,
                profileBindingsValidated=False, fullAmd64Coverage=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("domain", type=Path)
    parser.add_argument("--budget", type=int, default=100000)
    args = parser.parse_args()
    try:
        document = read(args.domain)
        validator = validate_memory_mov8_domain if document.get("schema") == MEMORY_SCHEMA else validate_mov8_domain
        points = validator(document, budget=args.budget)
    except DomainUnknown as error:
        print(canonical(dict(status="unknown", reason=str(error), fullAmd64Coverage=False)))
        return 1
    print(canonical(dict(status="checked", points=len(points), sourceEvidenceReplayed=False,
                         profileBindingsValidated=False, candidateFullDomainBindings=0, fullAmd64Coverage=False)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
