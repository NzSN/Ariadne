#!/usr/bin/env python3
"""Finite v2 legal-domain/binding pilot, kept separate from candidate accounting.

The reviewed REP derivation is a trust premise, not a whole-manual legality
model. Every byte/environment point in this deliberately small canonical-prefix
scope is enumerated. Unsupported grammar, stale inputs and work exhaustion never
close either the domain or implementation gate. Expanded observations/reports
belong under target/ or temporary work, never in maintained fixture directories.
"""
import argparse
from collections import Counter
import hashlib
import itertools
import json
from pathlib import Path
import re
import subprocess
import sys

from run_output import run_output

ROOT = Path(__file__).resolve().parents[1]
LEGAL = "ariadne.amd64-legal-forms/v2"
BINDINGS = "ariadne.amd64-profile-bindings/v2"
ASSESSMENT = "ariadne.amd64-coverage-assessment/v2"
OBSERVATIONS = "ariadne.amd64-binding-observations/v2"
RUST_TEST = "bap::projection::repeated_string_tests::fresh_producer_loops_project_under_only_the_repeated_string_profile"
MAX_INPUT_BYTES = 16 * 1024 * 1024
DEFAULT_BUDGET = 100000
PROFILE = "bap-bit-provenance-v12"
PDF_SHA = "e18bd39ad0ca19d2eb9b9ea25c2635144c5ab368e5d6fbdc7a08345515ea1aee"
REP_OPERATIONS = {"movs": (0xa4, 0xa5), "stos": (0xaa, 0xab), "cmps": (0xa6, 0xa7)}
EXACT_IMPLEMENTED = {"f3a4": "movs", "f3aa": "stos", "f3a6": "cmps"}
IMPLEMENTATION_SOURCES = ("src/bap/repeated_strings.rs", "src/bap/projection.rs",
                          "src/bap/session.rs", "src/bap/ast.rs",
                          "tests/bap/repeated_string_projection.rs",
                          "native/bap/lift.cpp", "native/bap/build.sh",
                          "tools/amd64_legal_forms.py", "tools/amd64_manual_geometry.py",
                          "tools/check_bap_repeated_string_oracle.py",
                          "tools/check_bap_admission_oracle.py",
                          "tools/check_bap_bit_count_oracle.py")


class BudgetExceeded(ValueError):
    """No classification/completeness conclusion is permitted."""


class Budget:
    def __init__(self, limit):
        require(type(limit) is int and 0 < limit <= 10000000, "invalid enumeration budget")
        self.remaining = limit

    def consume(self, amount=1):
        self.remaining -= amount
        if self.remaining < 0:
            raise BudgetExceeded("finite enumeration budget exhausted")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def fields(value, expected, label):
    require(isinstance(value, dict) and set(value) == set(expected), label + " fields")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def strict_json(data):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "duplicate JSON key: " + key)
            result[key] = value
        return result
    return json.loads(data, object_pairs_hook=unique,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError("nonfinite JSON: " + value)))


def read(path):
    raw = Path(path).read_bytes()
    require(len(raw) <= MAX_INPUT_BYTES, "input byte budget")
    return strict_json(raw)


def rows(values, label):
    require(isinstance(values, list), label + " must be a list")
    result = {}
    for row in values:
        require(isinstance(row, dict) and isinstance(row.get("id"), str) and row["id"]
                and row["id"] not in result, "invalid/duplicate " + label)
        result[row["id"]] = row
    return result


def hex_bytes(value, label, allow_empty=False):
    require(isinstance(value, str) and (bool(value) or allow_empty)
            and len(value) % 2 == 0 and re.fullmatch("[0-9a-f]*", value), label + " hex bytes")
    data = bytes.fromhex(value)
    require(len(data) <= 15, label + " exceeds 15 consumed bytes")
    return data


def environment_key(environment):
    return tuple(sorted(environment.items()))


def point_key(byte_string, environment):
    return byte_string, environment_key(environment)


def current_sources(root=ROOT):
    from amd64_manual_geometry import extractor_sources

    root = Path(root)
    names = set(IMPLEMENTATION_SOURCES)
    names.update(extractor_sources(root))
    names.update(str(path.relative_to(root)) for path in (root / "src/bap").glob("*.rs"))
    return {name: sha(root / name) for name in sorted(names)}


def validate_axes(axes):
    require(isinstance(axes, dict) and bool(axes), "missing environment axes")
    for axis, values in axes.items():
        require(isinstance(axis, str) and axis and isinstance(values, list) and values
                and all(type(value) in (str, int, bool) for value in values)
                and len({(type(v).__name__, v) for v in values}) == len(values), "environment axis")
    require(axes.get("mode") == [64]
            and set(axes.get("addressBits", [])) <= {32, 64}
            and set(axes.get("operandBits", [])) <= {8, 16, 32, 64}, "pilot decode axes")


def environments(predicate, axes, budget):
    require(isinstance(predicate, dict) and set(predicate) <= set(axes), "unknown environment predicate")
    domains = []
    for axis in sorted(axes):
        values = predicate.get(axis, axes[axis])
        require(isinstance(values, list) and values
                and len({(type(v).__name__, v) for v in values}) == len(values)
                and all(any(type(v) is type(w) and v == w for w in axes[axis]) for v in values),
                "environment predicate outside frozen scope")
        domains.append(values)
    product = 1
    for values in domains:
        product *= len(values)
    require(product > 0, "empty environment domain")
    if product > budget.remaining:
        raise BudgetExceeded("environment product exceeds enumeration budget")
    for values in itertools.product(*domains):
        budget.consume()
        yield dict(zip(sorted(axes), values))


def enumerate_grammar(grammar, axes, budget):
    fields(grammar, {"alternatives"}, "grammar")
    require(isinstance(grammar["alternatives"], list) and grammar["alternatives"], "empty grammar")
    result = set()
    for alternative in grammar["alternatives"]:
        fields(alternative, {"prefixes", "opcode", "fields", "environment"}, "grammar alternative")
        require(isinstance(alternative["prefixes"], list), "prefixes must be ordered exact bytes")
        prefixes = [hex_bytes(prefix, "prefix") for prefix in alternative["prefixes"]]
        require(all(len(value) == 1 for value in prefixes), "prefix must have one byte")
        opcode = hex_bytes(alternative["opcode"], "opcode")
        require(isinstance(alternative["fields"], list), "finite fields")
        names, domains = set(), []
        fixed_length = sum(map(len, prefixes)) + len(opcode)
        product = 1
        for field in alternative["fields"]:
            fields(field, {"name", "width", "values"}, "finite field")
            require(isinstance(field["name"], str) and field["name"] and field["name"] not in names,
                    "duplicate finite field name")
            names.add(field["name"])
            width, values = field["width"], field["values"]
            require(type(width) is int and 1 <= width <= 8
                    and isinstance(values, list) and values
                    and all(type(v) is int and 0 <= v < 1 << (width * 8) for v in values)
                    and len(set(values)) == len(values), "invalid finite field values")
            fixed_length += width
            domains.append([value.to_bytes(width, "little") for value in values])
            product *= len(values)
        require(fixed_length <= 15, "grammar exceeds 15 consumed bytes")
        if product > budget.remaining:
            raise BudgetExceeded("byte-field product exceeds enumeration budget")
        envs = list(environments(alternative["environment"], axes, budget))
        if product * len(envs) > budget.remaining:
            raise BudgetExceeded("byte/environment product exceeds enumeration budget")
        for values in itertools.product(*domains):
            encoded = (b"".join(prefixes) + opcode + b"".join(values)).hex()
            for env in envs:
                budget.consume()
                point = point_key(encoded, env)
                require(point not in result, "duplicate/overlapping alternatives in one grammar")
                result.add(point)
    return result


def expected_rep_domain(rule, axes, budget):
    """Independent finite derivation, not enumeration of the supplied grammar.

    Canonical pilot prefix order is repeat, address-size, operand-size/REX.W.
    Other orders, redundant/ignored prefixes and other families are outside this
    frozen pilot BEFORE domain construction, and remain vendor obligations.
    """
    expected = set()
    opcode8, opcode_wide = REP_OPERATIONS[rule["operation"]]
    for width, address in itertools.product(rule["elementBits"], rule["addressBits"]):
        prefix = "f3" + ("67" if address == 32 else "")
        prefix += {8: "", 16: "66", 32: "", 64: "48"}[width]
        encoded = prefix + f"{opcode8 if width == 8 else opcode_wide:02x}"
        predicate = {"operandBits": [width], "addressBits": [address]}
        for environment in environments(predicate, axes, budget):
            expected.add(point_key(encoded, environment))
    return expected


def validate_legal(legal, root=ROOT, budget=None):
    budget = budget or Budget(DEFAULT_BUDGET)
    fields(legal, {"schema", "scope", "sourcePins", "sourceCells", "reviewedRules", "forms", "overlapRules"}, "legal forms")
    require(legal["schema"] == LEGAL, "new v2 legal-form schema required; v1 candidates cannot be promoted")
    scope = legal["scope"]
    fields(scope, {"id", "vendor", "environmentAxes", "prefixPolicy", "sourceComplete",
                   "vendorFullDenominator", "exclusions"}, "scope")
    require(scope["id"] == "amd-long64-canonical-rep-pilot/v2" and scope["vendor"] == "AMD"
            and scope["prefixPolicy"] == "repeat-address-operand-canonical-only"
            and scope["sourceComplete"] is False and scope["vendorFullDenominator"] is False,
            "pilot cannot claim source or vendor denominator completeness")
    validate_axes(scope["environmentAxes"])
    exclusions = rows(scope["exclusions"], "scope exclusion")
    for exclusion in exclusions.values():
        fields(exclusion, {"id", "kind", "reason", "beforeDomainConstruction"}, "scope exclusion")
        require(exclusion["kind"] in {"other-families", "other-prefix-order", "redundant-prefixes", "other-vendors"}
                and exclusion["beforeDomainConstruction"] is True
                and isinstance(exclusion["reason"], str) and exclusion["reason"],
                "scope exclusion must be frozen before D; point exclusions inside D are forbidden")
    require({row["kind"] for row in exclusions.values()} ==
            {"other-families", "other-prefix-order", "redundant-prefixes", "other-vendors"},
            "incomplete pilot scope exclusions")
    pins = rows(legal["sourcePins"], "source pin")
    require(len(pins) == 1, "pilot requires exact official Vol3 source pin")
    for pin in pins.values():
        fields(pin, {"id", "lockPath", "lockSha256", "publication", "revision", "pdfSha256"}, "source pin")
        require(pin["lockPath"] == "tests/bap/fixtures/amd64-semantics/manual-inventory.lock.json"
                and pin["lockSha256"] == sha(Path(root) / pin["lockPath"]), "stale source pin")
        lock = read(Path(root) / pin["lockPath"])
        matches = [row for row in lock["documents"] if row["publication"] == pin["publication"]]
        require(len(matches) == 1 and pin["publication"] == "24594" and pin["revision"] == "3.38"
                and pin["pdfSha256"] == PDF_SHA
                and all(matches[0][key] == pin[key] for key in ("revision", "pdfSha256"))
                and matches[0]["sourceProvenance"]["officialByteIdentity"] == "matches-repository-official-source-pin",
                "unreviewed source publication or PDF identity")
    cells = rows(legal["sourceCells"], "reviewed source cell")
    for cell in cells.values():
        fields(cell, {"id", "pdfSha256", "pdfPage", "rect", "wordSpan", "unicodeSha256", "wordBoxesSha256"}, "source cell reference")
        require(cell["pdfSha256"] == PDF_SHA and cell["pdfPage"] in {50, 51, 52, 54, 55, 56}
                and cell["id"].startswith(f'pdf:{cell["pdfPage"]}:cell:')
                and isinstance(cell["rect"], list) and len(cell["rect"]) == 4
                and isinstance(cell["wordSpan"], list) and len(cell["wordSpan"]) == 2
                and all(re.fullmatch("[0-9a-f]{64}", cell[key] or "") for key in ("unicodeSha256", "wordBoxesSha256")),
                "invalid source cell address")
    rules = rows(legal["reviewedRules"], "reviewed rule")
    for rule in rules.values():
        fields(rule, {"id", "sourcePin", "pdfPages", "kind", "operation", "elementBits", "addressBits",
                      "review", "sourceCells"}, "reviewed rule")
        require(rule["sourcePin"] in pins and rule["kind"] == "rep-memory-string/v1"
                and rule["operation"] in REP_OPERATIONS
                and rule["pdfPages"] == [50, 51, 52, 54, 55, 56]
                and rule["elementBits"] == [8, 16, 32, 64] and rule["addressBits"] == [32, 64],
                "unsupported/unreviewed derivation rule")
        require(isinstance(rule["sourceCells"], list) and len(set(rule["sourceCells"])) == len(rule["sourceCells"])
                and set(rule["sourceCells"]) <= set(cells)
                and {cells[name]["pdfPage"] for name in rule["sourceCells"]} >= {50, 51, 52},
                "reviewed rule lacks exact prefix/size source cells")
        fields(rule["review"], {"sourceAddress", "premises", "limits"}, "review metadata")
        require(rule["review"]["sourceAddress"] == "AMD 24594 r3.38 PDF pages 50-52,54-56; prefix, size, implicit-register and repeat tables"
                and isinstance(rule["review"]["premises"], list) and len(rule["review"]["premises"]) >= 2
                and isinstance(rule["review"]["limits"], str) and rule["review"]["limits"], "source-addressed review missing")
    forms = rows(legal["forms"], "legal form")
    require(bool(forms), "empty legal denominator")
    domains = {}
    for form in forms.values():
        fields(form, {"id", "meaning", "reviewedRule", "grammar"}, "legal form")
        require(form["reviewedRule"] in rules, "orphan reviewed rule")
        rule = rules[form["reviewedRule"]]
        require(form["meaning"] == "rep-" + rule["operation"], "form meaning differs from source derivation")
        domain = enumerate_grammar(form["grammar"], scope["environmentAxes"], budget)
        expected = expected_rep_domain(rule, scope["environmentAxes"], budget)
        require(domain == expected, "grammar differs from independent reviewed derivation; omitted or illegal byte/environment points")
        domains[form["id"]] = domain
    validate_overlaps(forms, domains, legal["overlapRules"], scope["environmentAxes"])
    return forms, domains


def validate_source_evidence(legal, evidence):
    """Replay source addresses against word boxes; derivation remains reviewed.

    The source-corpus tool separately pins/reproduces the extractor. This check
    verifies the actual PDF identity and every retained rule address, rather
    than accepting a self-hash of a legality claim as source authority.
    """
    fields(evidence, {"pdfPath", "bboxPath", "bboxSha256"}, "source evidence")
    require(sha(evidence["pdfPath"]) == PDF_SHA and sha(evidence["bboxPath"]) == evidence["bboxSha256"],
            "stale PDF/word-box evidence")
    from amd64_manual_geometry import read_geometry
    cells = {cell["id"]: dict(cell, pdfSha256=PDF_SHA)
             for page in read_geometry(evidence["bboxPath"]) for cell in page["cells"]}
    for reference in legal["sourceCells"]:
        require(reference["id"] in cells and all(cells[reference["id"]][key] == value for key, value in reference.items()),
                "source cell bytes/geometry differ from reviewed reference")
    return len(legal["sourceCells"])


def validate_overlaps(forms, domains, rules, axes):
    """Check complete intersections, with explicit identical or guarded dispatch."""
    pairs = {}
    for rule in rules:
        require(isinstance(rule, dict) and set(rule) in
                ({"left", "right", "kind", "rationale"}, {"left", "right", "kind", "rationale", "axis", "dispatch"}),
                "overlap rule fields")
        pair = tuple(sorted((rule["left"], rule["right"])))
        require(rule["left"] != rule["right"] and all(x in forms for x in pair) and pair not in pairs,
                "duplicate/orphan overlap rule")
        require(isinstance(rule["rationale"], str) and rule["rationale"], "reviewed overlap rationale missing")
        pairs[pair] = rule
    for left, right in itertools.combinations(sorted(forms), 2):
        overlap = domains[left] & domains[right]
        rule = pairs.pop((left, right), None)
        if not overlap:
            require(rule is None, "overlap rule has no domain intersection")
            continue
        require(rule is not None, "unresolved overlapping legal meanings")
        if rule["kind"] == "identical-meaning":
            require(set(rule) == {"left", "right", "kind", "rationale"}
                    and forms[left]["meaning"] == forms[right]["meaning"], "overlap meanings differ")
        elif rule["kind"] == "guarded-alias":
            axis, dispatch = rule.get("axis"), rule.get("dispatch")
            require(axis in axes and isinstance(dispatch, dict) and set(dispatch) == {left, right}, "alias dispatch axis")
            selected = []
            for name in (left, right):
                require(isinstance(dispatch[name], list) and dispatch[name], "empty alias dispatch")
                selected.extend(dispatch[name])
            require(Counter((type(v).__name__, v) for v in selected) ==
                    Counter((type(v).__name__, v) for v in axes[axis]), "alias guards do not partition the environment")
            for _, environment in overlap:
                value = dict(environment)[axis]
                require(sum(value in dispatch[name] for name in (left, right)) == 1, "ambiguous feature alias")
        else:
            raise ValueError("unknown overlap resolution")
    require(not pairs, "unconsumed overlap rule")


def validate_bindings(bindings, legal, domains, root=ROOT, budget=None):
    budget = budget or Budget(DEFAULT_BUDGET)
    fields(bindings, {"schema", "legalFormsSha256", "consumer", "implementationRule", "implementationSources", "producerPin",
                      "partitions"}, "profile bindings")
    require(bindings["schema"] == BINDINGS and bindings["legalFormsSha256"] == digest(legal), "stale legal-form binding")
    require(bindings["consumer"] == {"profile": PROFILE, "capability": "plain-dependencies"}
            and bindings["implementationRule"] == "exact-v12-byte-rep-projection/v1", "unknown consumer/implementation rule")
    require(bindings["implementationSources"] == current_sources(root), "stale implementation/consumer source digests")
    fields(bindings["producerPin"], {"helperSha256", "runtimeLockSha256"}, "producer pin")
    require(re.fullmatch("[0-9a-f]{64}", bindings["producerPin"]["helperSha256"] or "")
            and bindings["producerPin"]["runtimeLockSha256"] == sha(Path(root) / "native/bap/toolchain.lock.json"),
            "stale runtime/invalid helper pin")
    partitions = rows(bindings["partitions"], "binding partition")
    classified = {name: {} for name in domains}
    for partition in partitions.values():
        fields(partition, {"id", "form", "disposition", "grammar", "reason", "observationIds"}, "partition")
        require(partition["form"] in domains and partition["disposition"] in {"S", "U", "X"}
                and isinstance(partition["reason"], str) and partition["reason"]
                and isinstance(partition["observationIds"], list)
                and len(set(partition["observationIds"])) == len(partition["observationIds"]), "partition identity/disposition")
        points = enumerate_grammar(partition["grammar"], legal["scope"]["environmentAxes"], budget)
        require(points <= domains[partition["form"]], "binding domain outside referenced legal form D")
        if partition["disposition"] == "S":
            require(partition["observationIds"] and all(byte_string in EXACT_IMPLEMENTED and
                    dict(environment)["operandBits"] == 8 and dict(environment)["addressBits"] == 64
                    for byte_string, environment in points), "implementation rule does not admit this domain")
        else:
            require(not partition["observationIds"], "unsupported/unresolved regions cannot claim test support")
        for point in points:
            require(point not in classified[partition["form"]], "overlapping S/U/X partitions")
            classified[partition["form"]][point] = (partition["disposition"], partition["id"])
    return partitions, classified


def validate_producer(producer, bindings, root=ROOT):
    fields(producer, {"helperPath", "helperSha256", "runtimeRoot", "runtimeLockPath", "runtimeLockSha256"}, "producer")
    require(sha(producer["helperPath"]) == producer["helperSha256"] == bindings["producerPin"]["helperSha256"],
            "stale/unpinned helper identity")
    require(producer["runtimeLockPath"] == "native/bap/toolchain.lock.json"
            and sha(Path(root) / producer["runtimeLockPath"]) == producer["runtimeLockSha256"], "stale runtime lock")
    lock = read(Path(root) / producer["runtimeLockPath"])
    for relative, expected in lock["files"].items():
        require(sha(Path(producer["runtimeRoot"]) / relative) == expected, "runtime file differs from pin: " + relative)


def validate_observations(observations, legal, bindings, partitions, classified, root=ROOT):
    fields(observations, {"schema", "legalFormsSha256", "bindingsSha256", "sourceSha256", "producer", "rows", "rustAdmissionTest", "sourceEvidence"}, "observations")
    require(observations["schema"] == OBSERVATIONS and observations["legalFormsSha256"] == digest(legal)
            and observations["bindingsSha256"] == digest(bindings), "stale observation inputs")
    require(observations["sourceSha256"] == current_sources(root), "stale current test sources")
    validate_source_evidence(legal, observations["sourceEvidence"])
    validate_producer(observations["producer"], bindings, root)
    observations_by_id = rows(observations["rows"], "observation")
    used = set()
    from check_bap_repeated_string_oracle import check_case, scenario
    for partition in partitions.values():
        if partition["disposition"] != "S":
            continue
        witnessed = set()
        for observation_id in partition["observationIds"]:
            require(observation_id in observations_by_id and observation_id not in used, "missing/duplicate observation provenance")
            used.add(observation_id)
            observation = observations_by_id[observation_id]
            fields(observation, {"id", "partition", "request", "response", "astSha256", "comparisonCount"}, "observation row")
            require(observation["partition"] == partition["id"], "observation partition identity")
            request = observation["request"]
            fields(request, {"snapshot", "va", "consumedBytes", "decodeEnvironment", "target", "profile", "consumer"}, "request")
            require(request["snapshot"] == digest({"legal": digest(legal), "bindings": digest(bindings)})
                    and re.fullmatch("0x[0-9a-f]{16}", request["va"] or "")
                    and request["target"] == "windows-amd64" and request["profile"] == PROFILE
                    and request["consumer"] == "plain-dependencies", "request snapshot/VA/target/consumer identity")
            hex_bytes(request["consumedBytes"], "consumed instruction")
            point = point_key(request["consumedBytes"], request["decodeEnvironment"])
            require(classified[partition["form"]].get(point) == ("S", partition["id"]), "observation bytes/environment not admitted by binding")
            response = observation["response"]
            fields(response, {"schema", "batch", "snapshot", "va", "status", "length", "bytes", "opcode", "properties", "bil"},
                   "producer response")
            require(isinstance(response, dict) and response.get("schema") == "ariadne.bap-site/v1"
                    and response.get("snapshot") == request["snapshot"] and response.get("va") == request["va"]
                    and response.get("status") == "decoded" and type(response.get("batch")) is int and response.get("batch") == 0
                    and response.get("opcode") == {"f3a4": "MOVSB", "f3aa": "STOSB", "f3a6": "CMPSB"}[request["consumedBytes"]]
                    and response.get("bytes") == request["consumedBytes"]
                    and type(response.get("length")) is int
                    and response["length"] == len(request["consumedBytes"]) // 2
                    and isinstance(response.get("bil"), list) and response["bil"],
                    "producer response bytes/consumed extent/snapshot/VA mismatch")
            require(observation["astSha256"] == digest(response["bil"]), "typed BIL AST digest differs")
            operation = EXACT_IMPLEMENTED[request["consumedBytes"]] + "b"
            comparisons = 0
            for parameters in itertools.product((0, 1, 2, 4, 8), (0, 1), (0, 1),
                                                ("disjoint", "overlap", "source-wrap", "destination-wrap"),
                                                ("equal", "first-diff", "late-diff")):
                registers, memory = scenario(*parameters)
                check_case({"name": observation_id, "operation": operation}, response["bil"], registers, memory)
                comparisons += 1
            require(type(observation["comparisonCount"]) is int and observation["comparisonCount"] == comparisons,
                    "independent test observation count differs")
            require(point not in witnessed, "duplicate byte/environment observation")
            witnessed.add(point)
        required = {point for point, (disposition, part) in classified[partition["form"]].items()
                    if disposition == "S" and part == partition["id"]}
        require(witnessed == required, "supported finite binding lacks current byte/environment observations")
    require(used == set(observations_by_id), "orphan observation")
    if observations["rustAdmissionTest"] is not None:
        test = observations["rustAdmissionTest"]
        fields(test, {"test", "liftSetSha256", "stdout", "stderr"}, "Rust admission test")
        require(test["test"] == RUST_TEST and test["liftSetSha256"] == digest(rust_lift_set(observations))
                and isinstance(test["stdout"], str) and isinstance(test["stderr"], str)
                and f"test {RUST_TEST} ... ok" in test["stdout"]
                and "test result: ok. 1 passed; 0 failed;" in test["stdout"], "Rust admission observer missing or stale")
    return len(used)


def rust_lift_set(observations):
    by_byte = {row["response"]["bytes"]: row["response"] for row in observations["rows"]}
    require(set(by_byte) == set(EXACT_IMPLEMENTED), "Rust observer requires the exact three reviewed v12 forms")
    return [by_byte[encoded] for encoded in ("f3a4", "f3aa", "f3a6")]


def assess(legal, bindings, observations=None, root=ROOT, budget=DEFAULT_BUDGET):
    if legal.get("schema") == MEMORY_LEGAL:
        return assess_memory(legal, bindings, observations, root, budget)
    base = dict(schema=ASSESSMENT, sourceComplete=False, vendorFullDenominator=False,
                fullAmd64Coverage=False, sourceDerivationTrust="reviewed finite canonical-prefix REP rules; no full-manual proof",
                legalFormsSha256=digest(legal), bindingsSha256=digest(bindings),
                totalDisposition=False, implementationComplete=False, currentObservationsValidated=False)
    try:
        work = Budget(budget)
        _, domains = validate_legal(legal, root, work)
        partitions, classified = validate_bindings(bindings, legal, domains, root, work)
        summaries = []
        for name in sorted(domains):
            counts = Counter(disposition for disposition, _ in classified[name].values())
            holes = domains[name] - set(classified[name])
            summaries.append(dict(form=name, domain=len(domains[name]), supported=counts["S"],
                                  unsupported=counts["U"], unresolved=counts["X"], holes=len(holes),
                                  firstHole=None if not holes else dict(bytes=sorted(holes)[0][0], environment=dict(sorted(holes)[0][1]))))
        observed = validate_observations(observations, legal, bindings, partitions, classified, root) if observations is not None else 0
        accounting = all(row["holes"] == 0 for row in summaries)
        implementation = accounting and all(row["unsupported"] == row["unresolved"] == 0 for row in summaries)
        profile_validated = observations is not None and observations["rustAdmissionTest"] is not None
        return dict(base, status="checked", forms=summaries, enumeratedPoints=sum(row["domain"] for row in summaries),
                    totalDisposition=accounting, implementationComplete=implementation and profile_validated,
                    implementationDomainComplete=implementation, currentObservationsValidated=observations is not None,
                    profileBindingsValidated=profile_validated,
                    observationCount=observed, remainingEnumerationBudget=work.remaining)
    except BudgetExceeded as error:
        return dict(base, status="unknown", reason=str(error))


def query(bindings, legal, observations, byte_string, environment, root=ROOT, budget=DEFAULT_BUDGET):
    if legal.get("schema") == MEMORY_LEGAL:
        return query_memory(bindings, legal, observations, byte_string, environment, root, budget)
    result = assess(legal, bindings, observations, root, budget)
    require(result["status"] == "checked", "query domain checker returned unknown")
    hex_bytes(byte_string, "consumed instruction")
    _, domains = validate_legal(legal, root)
    _, classified = validate_bindings(bindings, legal, domains, root)
    point = point_key(byte_string, environment)
    matches = [{"form": form, "disposition": classified[form].get(point, ("hole", None))[0],
                "partition": classified[form].get(point, (None, None))[1]}
               for form in sorted(domains) if point in domains[form]]
    return dict(schema="ariadne.amd64-legal-query/v2", consumedBytes=byte_string,
                decodeEnvironment=environment, matches=matches, currentObservationsValidated=observations is not None,
                profileAdmissionValidated=result["profileBindingsValidated"] and bool(matches)
                    and all(match["disposition"] == "S" for match in matches),
                limit="Finite v12 binding; other consumer profiles are unbound by this registry.")


def build_observations(legal, bindings, helper, runtime, source_pdf, source_bbox, root=ROOT, run_rust=True, budget=DEFAULT_BUDGET):
    """Fresh protocol query; never adopt a caller-provided passed boolean."""
    work = Budget(budget)
    _, domains = validate_legal(legal, root, work)
    partitions, classified = validate_bindings(bindings, legal, domains, root, work)
    pending = []
    for form in sorted(classified):
        for point, (disposition, partition) in sorted(classified[form].items()):
            if disposition == "S":
                pending.append((point, partition))
    require(bool(pending), "no supported pilot points")
    snapshot = digest({"legal": digest(legal), "bindings": digest(bindings)})
    command = f"ARIADNE-BAP-LIFT 1 windows-amd64 {snapshot}\nbatch 0 {len(pending)}\n"
    command += "".join(f"0x{0x401000 + i * 32:016x} {point[0]}\n" for i, (point, _) in enumerate(pending))
    import os
    runtime = Path(runtime).resolve()
    producer = dict(helperPath=str(Path(helper).resolve()), helperSha256=sha(helper), runtimeRoot=str(runtime),
                    runtimeLockPath="native/bap/toolchain.lock.json",
                    runtimeLockSha256=sha(Path(root) / "native/bap/toolchain.lock.json"))
    validate_producer(producer, bindings, root)
    source_evidence = dict(pdfPath=str(Path(source_pdf).resolve()), bboxPath=str(Path(source_bbox).resolve()),
                           bboxSha256=sha(source_bbox))
    validate_source_evidence(legal, source_evidence)
    env = {**os.environ, "LD_LIBRARY_PATH": str(runtime / "usr/local/lib") + ":" + str(runtime / "usr/lib/x86_64-linux-gnu"),
           "XDG_STATE_HOME": str(runtime / "state"), "XDG_CACHE_HOME": str(runtime / "cache")}
    process = subprocess.run([str(Path(helper).resolve()), str(runtime / "usr/local/lib/bap")],
                             input=command, text=True, capture_output=True, timeout=300, env=env)
    require(process.returncode == 0, "fresh producer query failed: " + process.stderr[:2000])
    frames = [strict_json(line) for line in process.stdout.splitlines()]
    require(len(frames) == len(pending) + 2, "missing/duplicate producer frames")
    require(frames[0] == {"schema": "ariadne.bap-ready/v1", "snapshot": snapshot, "target": "windows-amd64",
                          "version": "2.5.0-alpha", "lifter": "legacy"}, "producer ready identity")
    require(frames[-1] == {"schema": "ariadne.bap-batch/v1", "batch": 0, "count": len(pending)}, "producer batch identity")
    output = dict(schema=OBSERVATIONS, legalFormsSha256=digest(legal), bindingsSha256=digest(bindings),
                  sourceSha256=dict(bindings["implementationSources"]), producer=producer, rows=[], rustAdmissionTest=None,
                  sourceEvidence=source_evidence)
    for i, ((point, partition), response) in enumerate(zip(pending, frames[1:-1])):
        require(len(partitions[partition]["observationIds"]) == 1, "pilot observation ID assignment requires single-point partitions")
        output["rows"].append(dict(id=partitions[partition]["observationIds"][0], partition=partition,
            request=dict(snapshot=snapshot, va=f"0x{0x401000 + i * 32:016x}", consumedBytes=point[0],
                         decodeEnvironment=dict(point[1]), target="windows-amd64", profile=PROFILE, consumer="plain-dependencies"),
            response=response, astSha256=digest(response.get("bil")), comparisonCount=240))
    validate_observations(output, legal, bindings, partitions, classified, root)
    if run_rust:
        import tempfile
        with tempfile.TemporaryDirectory(prefix="ariadne-legal-pilot-") as work:
            lift_path = Path(work) / "lifts.json"
            lift_set = rust_lift_set(output)
            lift_path.write_text(json.dumps(lift_set))
            test_env = {**os.environ, "ARIADNE_REP_FRESH_LIFTS": str(lift_path)}
            test = subprocess.run(["cargo", "test", "--offline", "--locked", "--lib", RUST_TEST,
                                   "--", "--ignored", "--exact"], cwd=root, env=test_env,
                                  text=True, capture_output=True, timeout=600)
            require(test.returncode == 0, "fresh Rust profile observer failed: " + test.stdout[-2000:] + test.stderr[-2000:])
            output["rustAdmissionTest"] = dict(test=RUST_TEST, liftSetSha256=digest(lift_set), stdout=test.stdout, stderr=test.stderr)
        validate_observations(output, legal, bindings, partitions, classified, root)
    require(output["sourceSha256"] == current_sources(root), "source changed during fresh observation campaign")
    return output


# The v2 pilot and its prefix order are frozen. This independently scoped v3
# registry covers only one canonical encoding per memory-string tuple, never
# the entire encoding domain of an XED symbolic template.
MEMORY_LEGAL = "ariadne.amd64-legal-forms/v3"
MEMORY_BINDINGS = "ariadne.amd64-profile-bindings/v3"
MEMORY_OBSERVATIONS = "ariadne.amd64-binding-observations/v3"
MEMORY_ASSESSMENT = "ariadne.amd64-coverage-assessment/v3"
MEMORY_RUST_TEST = "bap::projection::repeated_string_binding_observer::fresh_selected_producers_bind_all_memory_rep_profiles"
MEMORY_PROFILES = tuple(f"bap-bit-provenance-v{version}" for version in (12, 13, 14, 15))
MEMORY_AXES = dict(vendor=["AMD"], mode=[64], addressBits=[32, 64], operandBits=[8, 16, 32, 64],
                   flatDefaultSegments=[True], outcomes=["finite-normal-completion"])
MEMORY_FAMILIES = {
    "movs": (0xa4, 0xa5, (301, 302)), "stos": (0xaa, 0xab, (396, 397)),
    "lods": (0xac, 0xad, (267, 268)), "cmps": (0xa6, 0xa7, (207, 208)),
    "scas": (0xae, 0xaf, (376, 377)),
}
MEMORY_SOURCE_RANGES = {
    "sizes": {50: (9, 44), 51: (9, 72), 52: (5, 76), 57: (10, 64), 65: (13, 46)},
    "movs": {54: (29, 45), 301: (9, 44)},
    "stos": {55: (10, 18), 396: (9, 38)},
    "lods": {54: (29, 37), 267: (9, 45)},
    "cmps": {55: (18, 34), 56: (6, 14), 207: (9, 51)},
    "scas": {55: (18, 42), 56: (14, 22), 376: (9, 45)},
    "repeat": {54: (8, 19), 55: (18, 24), 56: (3, 26)},
}
SOURCE_PRODUCERS = {
    "lods": dict(stem="lods", role="lods-source", profile=MEMORY_PROFILES[2],
                 lock="native/bap/source-coverage/lods.runtime.lock.json",
                 sources=("lods_build.py", "lods_lift.ml", "lods_probe.ml", "lods.patch", "build.py")),
    "repAddress": dict(stem="rep-address", role="rep-address-source", profile=MEMORY_PROFILES[3],
                       lock="native/bap/source-coverage/rep-address.runtime.lock.json",
                       sources=("rep_address_build.py", "rep_address_lift.ml", "rep_address_probe.ml",
                                "rep_address.patch", "lods.patch", "build.py")),
}


def memory_source_ids(family):
    return sorted({f"pdf:{page}:cell:{index}" for group in ("sizes", "repeat", family)
                   for page, (start, stop) in MEMORY_SOURCE_RANGES[group].items()
                   for index in range(start, stop)})


def memory_cases():
    cases = {}
    for family, (byte, wide, pages) in MEMORY_FAMILIES.items():
        for repeat in (("f3", "f2") if family in {"cmps", "scas"} else ("f3",)):
            for width, address in itertools.product((8, 16, 32, 64), (32, 64)):
                prefix = ("67" if address == 32 else "") + ("66" if width == 16 else "") + repeat
                prefix += "48" if width == 64 else ""
                encoded = prefix + f"{byte if width == 8 else wide:02x}"
                environment = dict(vendor="AMD", mode=64, addressBits=address, operandBits=width,
                                   flatDefaultSegments=True, outcomes="finite-normal-completion")
                cases[encoded] = dict(bytes=encoded, family=family, elementBits=width, addressBits=address,
                    repeat=repeat, repeatCondition=("count" if family not in {"cmps", "scas"}
                                                   else "equal" if repeat == "f3" else "not-equal"),
                    opcode=family.upper() + {8: "B", 16: "W", 32: "L", 64: "Q"}[width],
                    form=f"amd-canonical-{repeat}-{family}", environment=environment, pdfPages=list(pages))
    return cases


def memory_admits(profile, case):
    require(profile in MEMORY_PROFILES, "unknown memory consumer profile")
    if profile == MEMORY_PROFILES[0]:
        return case["bytes"] in EXACT_IMPLEMENTED
    if profile == MEMORY_PROFILES[1]:
        return case["addressBits"] == 64 and case["family"] != "lods"
    if profile == MEMORY_PROFILES[2]:
        return case["addressBits"] == 64
    return True


def memory_producer(profile, case):
    require(memory_admits(profile, case), "unsupported memory consumer has no selected producer")
    if profile == MEMORY_PROFILES[3] and (case["addressBits"] == 32 or case["family"] == "lods"):
        return "repAddress"
    return "lods" if case["family"] == "lods" else "base"


def current_memory_sources(root=ROOT):
    root = Path(root)
    names = set(current_sources(root))
    names.update(str(path.relative_to(root)) for pattern in
                 ("native/bap/source-coverage/*", "tests/bap/repeated_string_binding_observer.rs",
                  "tools/check_bap_rep_address_oracle.py", "tools/amd64_rep_address_recipes.py",
                  "tools/check_bap_lods_oracle.py", "tools/amd64_rep_recipes.py")
                 for path in root.glob(pattern) if path.is_file())
    return {name: sha(root / name) for name in sorted(names)}


def memory_producer_pins(helper, root=ROOT):
    root = Path(root)
    pins = dict(base=dict(helperSha256=sha(helper), runtimeLockPath="native/bap/toolchain.lock.json",
                          runtimeLockSha256=sha(root / "native/bap/toolchain.lock.json")))
    for name, contract in SOURCE_PRODUCERS.items():
        path = root / contract["lock"]
        pins[name] = dict(lockPath=contract["lock"], lockSha256=sha(path) if path.is_file() else None)
    return pins


def validate_memory_legal(legal, root=ROOT, budget=None):
    budget = budget or Budget(DEFAULT_BUDGET)
    fields(legal, {"schema", "scope", "sourcePins", "sourceCells", "reviewedRules", "forms", "overlapRules"}, "memory legal forms")
    require(legal["schema"] == MEMORY_LEGAL, "memory legal schema")
    scope = legal["scope"]
    fields(scope, {"id", "vendor", "environmentAxes", "prefixPolicy", "sourceComplete", "vendorFullDenominator", "exclusions"}, "memory scope")
    require(scope["id"] == "amd-long64-canonical-memory-rep/v3" and scope["vendor"] == "AMD"
            and digest(scope["environmentAxes"]) == digest(MEMORY_AXES)
            and scope["prefixPolicy"] == "address-operand-repeat-rex-canonical-only"
            and scope["sourceComplete"] is False and scope["vendorFullDenominator"] is False,
            "memory scope cannot claim full source or encoding denominator")
    exclusions = rows(scope["exclusions"], "memory scope exclusion")
    expected_exclusions = {"other-families", "other-prefix-order", "redundant-prefixes", "other-vendors",
                           "segment-overrides", "io", "fault-and-restart"}
    require({row.get("kind") for row in exclusions.values()} == expected_exclusions, "memory scope exclusions")
    for exclusion in exclusions.values():
        fields(exclusion, {"id", "kind", "reason", "beforeDomainConstruction"}, "memory exclusion")
        require(exclusion["beforeDomainConstruction"] is True and bool(exclusion["reason"]),
                "memory exclusions must precede D construction")
    pins = rows(legal["sourcePins"], "memory source pin")
    require(len(pins) == 1, "memory rules need exact Vol3 source")
    for pin in pins.values():
        fields(pin, {"id", "lockPath", "lockSha256", "publication", "revision", "pdfSha256"}, "memory source pin")
        require(pin["lockPath"] == "tests/bap/fixtures/amd64-semantics/manual-inventory.lock.json"
                and pin["lockSha256"] == sha(Path(root) / pin["lockPath"])
                and pin["publication"] == "24594" and pin["revision"] == "3.38" and pin["pdfSha256"] == PDF_SHA,
                "memory source publication identity")
        documents = read(Path(root) / pin["lockPath"])["documents"]
        require(any(row["publication"] == "24594" and row["revision"] == "3.38" and row["pdfSha256"] == PDF_SHA
                    and row["sourceProvenance"]["officialByteIdentity"] == "matches-repository-official-source-pin"
                    for row in documents), "memory source official identity")
    cells = rows(legal["sourceCells"], "memory source cell")
    required_cells = {cell for family in MEMORY_FAMILIES for cell in memory_source_ids(family)}
    require(set(cells) == required_cells, "memory rules lack exact opcode/repeat/address-size source cells")
    for cell in cells.values():
        fields(cell, {"id", "pdfSha256", "pdfPage", "rect", "wordSpan", "unicodeSha256", "wordBoxesSha256"}, "memory source cell")
        require(cell["pdfSha256"] == PDF_SHA and cell["id"].startswith(f'pdf:{cell["pdfPage"]}:cell:')
                and isinstance(cell["rect"], list) and len(cell["rect"]) == 4
                and isinstance(cell["wordSpan"], list) and len(cell["wordSpan"]) == 2
                and all(re.fullmatch("[0-9a-f]{64}", cell[key] or "") for key in ("unicodeSha256", "wordBoxesSha256")),
                "memory source cell geometry/hash")
    rules, forms = rows(legal["reviewedRules"], "memory reviewed rule"), rows(legal["forms"], "memory legal form")
    cases = memory_cases()
    expected_forms = {case["form"] for case in cases.values()}
    require(set(forms) == expected_forms and len(rules) == len(forms), "memory canonical family denominator differs")
    domains, used_rules = {}, set()
    for name, form in forms.items():
        fields(form, {"id", "meaning", "reviewedRule", "grammar"}, "memory legal form")
        require(form["reviewedRule"] in rules and form["reviewedRule"] not in used_rules, "memory orphan/duplicate derivation")
        used_rules.add(form["reviewedRule"])
        rule = rules[form["reviewedRule"]]
        fields(rule, {"id", "sourcePin", "operation", "repeat", "elementBits", "addressBits", "sourceCells", "review"}, "memory reviewed rule")
        group = [case for case in cases.values() if case["form"] == name]
        first = group[0]
        require(rule["sourcePin"] in pins and rule["operation"] == first["family"] and rule["repeat"] == first["repeat"]
                and rule["elementBits"] == [8, 16, 32, 64] and rule["addressBits"] == [32, 64]
                and form["meaning"] == first["repeat"] + "-" + first["family"]
                and rule["sourceCells"] == memory_source_ids(first["family"]), "memory reviewed rule differs from source derivation")
        fields(rule["review"], {"premises", "limits"}, "memory review")
        require(isinstance(rule["review"]["premises"], list) and len(rule["review"]["premises"]) >= 3
                and isinstance(rule["review"]["limits"], str) and bool(rule["review"]["limits"]), "memory source derivation premises")
        domain = enumerate_grammar(form["grammar"], scope["environmentAxes"], budget)
        expected = {point_key(case["bytes"], case["environment"]) for case in group}
        require(domain == expected, "memory grammar differs from independent reviewed derivation")
        domains[name] = domain
    validate_overlaps(forms, domains, legal["overlapRules"], scope["environmentAxes"])
    return forms, domains


def validate_memory_bindings(bindings, legal, domains, root=ROOT, budget=None):
    budget = budget or Budget(DEFAULT_BUDGET)
    fields(bindings, {"schema", "legalFormsSha256", "implementationSources", "producerPins", "consumers"}, "memory bindings")
    require(bindings["schema"] == MEMORY_BINDINGS and bindings["legalFormsSha256"] == digest(legal), "stale memory legal binding")
    require(bindings["implementationSources"] == current_memory_sources(root), "stale memory implementation sources")
    pins = bindings["producerPins"]
    fields(pins, {"base", "lods", "repAddress"}, "memory producer pins")
    fields(pins["base"], {"helperSha256", "runtimeLockPath", "runtimeLockSha256"}, "memory base producer pin")
    require(re.fullmatch("[0-9a-f]{64}", pins["base"]["helperSha256"] or "")
            and pins["base"]["runtimeLockPath"] == "native/bap/toolchain.lock.json"
            and pins["base"]["runtimeLockSha256"] == sha(Path(root) / pins["base"]["runtimeLockPath"]), "memory base runtime pin")
    for name, contract in SOURCE_PRODUCERS.items():
        fields(pins[name], {"lockPath", "lockSha256"}, "memory source producer pin")
        path = Path(root) / contract["lock"]
        require(pins[name]["lockPath"] == contract["lock"]
                and pins[name]["lockSha256"] == (sha(path) if path.is_file() else None), "memory source producer lock identity")
    consumers = rows(bindings["consumers"], "memory consumer")
    require(set(consumers) == set(MEMORY_PROFILES), "memory consumers must preserve v12/v13/v14/v15")
    classified, partitions = {}, {}
    cases = memory_cases()
    for profile, consumer in consumers.items():
        fields(consumer, {"id", "capability", "implementationRule", "partitions"}, "memory consumer")
        require(consumer["capability"] == "plain-dependencies"
                and consumer["implementationRule"] == f"exact-memory-rep-{profile}/v1", "memory consumer capability/rule")
        classified[profile] = {name: {} for name in domains}
        partitions[profile] = rows(consumer["partitions"], "memory binding partition")
        for partition in partitions[profile].values():
            fields(partition, {"id", "form", "disposition", "grammar", "reason", "producer", "observationIds"}, "memory partition")
            require(partition["form"] in domains and partition["disposition"] in {"S", "U", "X"}
                    and isinstance(partition["reason"], str) and bool(partition["reason"])
                    and isinstance(partition["observationIds"], list)
                    and len(set(partition["observationIds"])) == len(partition["observationIds"]), "memory partition identity")
            points = enumerate_grammar(partition["grammar"], legal["scope"]["environmentAxes"], budget)
            require(points <= domains[partition["form"]], "memory binding outside legal domain")
            if partition["disposition"] == "S":
                require(bool(partition["observationIds"])
                        and all(memory_admits(profile, cases[code]) and memory_producer(profile, cases[code]) == partition["producer"]
                                for code, _ in points), "memory consumer/producer does not admit domain")
            else:
                require(not partition["observationIds"] and partition["producer"] is None,
                        "unsupported/unresolved memory partition cannot claim producer observations")
            for point in points:
                require(point not in classified[profile][partition["form"]], "overlapping memory S/U/X partitions")
                classified[profile][partition["form"]][point] = (partition["disposition"], partition["id"])
    return partitions, classified


def validate_memory_producers(producers, bindings, root=ROOT):
    """Verify selected artifacts and their source/build binding, not pass flags."""
    fields(producers, {"base", "lods", "repAddress"}, "selected memory producers")
    base_binding = {"producerPin": {key: bindings["producerPins"]["base"][key]
                                    for key in ("helperSha256", "runtimeLockSha256")}}
    validate_producer(producers["base"], base_binding, root)
    manifests = {}
    for name, contract in SOURCE_PRODUCERS.items():
        producer = producers[name]
        fields(producer, {"directory", "manifestSha256", "executableSha256", "lockSha256"}, "selected source producer")
        require(bindings["producerPins"][name]["lockSha256"] is not None
                and producer["lockSha256"] == bindings["producerPins"][name]["lockSha256"], "source producer is not qualified/pinned")
        lock = read(Path(root) / contract["lock"])
        fields(lock, {"schema", "manifest_sha256", "executable_sha256"}, "source runtime lock")
        require(lock["schema"] == f'ariadne.bap-source-{contract["stem"]}-lock/v1', "source runtime lock schema")
        directory = Path(producer["directory"])
        require(sha(directory / "manifest.json") == producer["manifestSha256"] == lock["manifest_sha256"]
                and sha(directory / (contract["stem"] + "-lift")) == producer["executableSha256"] == lock["executable_sha256"],
                "selected source artifact differs from reviewed pin")
        manifest = read(directory / "manifest.json")
        expected_cases = sorted(code for code, case in memory_cases().items()
                                if case["family"] == "lods" and case["addressBits"] == 64
                                or name == "repAddress" and case["addressBits"] == 32)
        require(manifest["schema"] == f'ariadne.bap-source-{contract["stem"]}-build/v1'
                and manifest["profiles"] == [contract["profile"]] and manifest["runtime_role"] == contract["role"]
                and manifest["executable"] == contract["stem"] + "-lift"
                and manifest["executable_sha256"] == producer["executableSha256"]
                and manifest["cases"] == expected_cases and manifest["max_response_bytes"] == 65536,
                "selected source manifest contract")
        if name == "repAddress":
            require(manifest.get("vendor") == "AMD" and manifest.get("semantic_premises") ==
                    ["amd-long-mode-memory-rep", "address32-zero-count-preserves-upper-lanes"],
                    "selected address producer AMD semantic premises")
        binding = manifest["binding"]
        require(binding["sources"] == {source: sha(Path(root) / "native/bap/source-coverage" / source)
                                       for source in contract["sources"]}, "selected producer source binding")
        sdk_lock = read(Path(root) / "native/bap-core/sdk.lock.json")
        require(binding["sdk_lock_sha256"] == sha(Path(root) / "native/bap-core/sdk.lock.json")
                and binding["base_revision"] == sdk_lock["bapSourceRevision"]
                and binding["source_archive_sha256"] == sdk_lock["bapSourceArchive"]["sha256"]
                and manifest["build_id"] == digest(binding), "selected producer SDK/build identity")
        manifests[name] = manifest
    return manifests


def validate_memory_response(row, profile, case, producer_name, snapshot, manifests):
    fields(row, {"id", "partition", "request", "producer", "response", "astSha256", "comparisonCount"}, "memory observation")
    request, response = row["request"], row["response"]
    fields(request, {"snapshot", "va", "consumedBytes", "decodeEnvironment", "target", "profile", "consumer"}, "memory request")
    require(request["snapshot"] == snapshot and re.fullmatch("0x[0-9a-f]{16}", request["va"] or "")
            and request["consumedBytes"] == case["bytes"]
            and digest(request["decodeEnvironment"]) == digest(case["environment"])
            and request["target"] == "windows-amd64" and request["profile"] == profile
            and request["consumer"] == "plain-dependencies" and row["producer"] == producer_name,
            "memory request bytes/environment/consumer/producer identity")
    if producer_name == "base":
        fields(response, {"schema", "batch", "snapshot", "va", "status", "length", "bytes", "opcode", "properties", "bil"}, "memory base response")
        require(response["schema"] == "ariadne.bap-site/v1" and type(response["batch"]) is int
                and response["batch"] == 0 and response["status"] == "decoded"
                and response["opcode"] == case["opcode"] and isinstance(response["properties"], dict), "memory base decode identity")
    else:
        fields(response, {"schema", "build_id", "target", "snapshot", "va", "bytes", "length", "bil"}, "memory source response")
        require(response["schema"] == f'ariadne.bap-source-{SOURCE_PRODUCERS[producer_name]["stem"]}/v1'
                and response["build_id"] == manifests[producer_name]["build_id"]
                and response["target"] == request["target"], "memory selected producer response identity")
    require(response["snapshot"] == snapshot and response["va"] == request["va"] and response["bytes"] == case["bytes"]
            and type(response["length"]) is int and response["length"] == len(case["bytes"]) // 2
            and isinstance(response["bil"], list) and bool(response["bil"]), "memory response extent/snapshot/VA/AST")
    require(row["astSha256"] == digest(response["bil"]), "memory typed BIL digest differs")


def memory_comparisons(case, bil):
    if case["addressBits"] == 32:
        from check_bap_rep_address_oracle import CASES, parameters, check_bil, verify_capi_types
        require(case["bytes"] in CASES, "address oracle lacks bound byte point")
        verify_capi_types(bil)
        count = 0
        for parameter in parameters(CASES[case["bytes"]]):
            check_bil(case["bytes"], bil, parameter)
            count += 1
        require(count > 0, "empty address oracle parameter domain")
        return count
    from check_bap_repeated_string_oracle import LoopEvaluator, expected_recipe, scenario_recipe
    from check_bap_lods_oracle import INPUTS
    count = 0
    for parameter in itertools.product(*INPUTS):
        registers, memory = scenario_recipe(case, *parameter)
        expected_registers, expected_memory = expected_recipe(case, registers, memory)
        evaluator = LoopEvaluator(registers, memory.copy())
        evaluator.statements(bil)
        require(all(evaluator.values[name].n == value for name, value in expected_registers.items())
                and evaluator.memory == expected_memory, f'memory numeric comparison differs for {case["bytes"]}: {parameter}')
        count += 1
    return count


def memory_rust_lift_set(observations):
    cases = memory_cases()
    return [dict(profile=row["request"]["profile"], producer=row["producer"],
                 opcode=cases[row["request"]["consumedBytes"]]["opcode"],
                 addressBits=cases[row["request"]["consumedBytes"]]["addressBits"],
                 response=row["response"], astSha256=row["astSha256"])
            for row in observations["rows"]]


def validate_memory_observations(observations, legal, bindings, partitions, classified, root=ROOT):
    fields(observations, {"schema", "legalFormsSha256", "bindingsSha256", "sourceSha256", "producers", "sourceEvidence", "rows", "rustAdmissionTest"}, "memory observations")
    require(observations["schema"] == MEMORY_OBSERVATIONS and observations["legalFormsSha256"] == digest(legal)
            and observations["bindingsSha256"] == digest(bindings)
            and observations["sourceSha256"] == current_memory_sources(root), "stale memory observation inputs/sources")
    validate_source_evidence(legal, observations["sourceEvidence"])
    manifests = validate_memory_producers(observations["producers"], bindings, root)
    by_id, used, numeric_cache = rows(observations["rows"], "memory observation"), set(), {}
    snapshot = digest({"legal": digest(legal), "bindings": digest(bindings)})
    cases = memory_cases()
    for profile in MEMORY_PROFILES:
        for partition in partitions[profile].values():
            if partition["disposition"] != "S":
                continue
            witnessed = set()
            for observation_id in partition["observationIds"]:
                require(observation_id in by_id and observation_id not in used, "missing/duplicate memory observation provenance")
                used.add(observation_id)
                row = by_id[observation_id]
                require(row["partition"] == partition["id"], "memory observation partition identity")
                code = row["request"]["consumedBytes"]
                require(code in cases, "memory observation byte domain")
                case = cases[code]
                point = point_key(code, row["request"]["decodeEnvironment"])
                require(classified[profile][partition["form"]].get(point) == ("S", partition["id"]), "memory observation outside bound environment")
                validate_memory_response(row, profile, case, partition["producer"], snapshot, manifests)
                numeric_key = (code, row["astSha256"])
                if numeric_key not in numeric_cache:
                    numeric_cache[numeric_key] = memory_comparisons(case, row["response"]["bil"])
                require(type(row["comparisonCount"]) is int and row["comparisonCount"] == numeric_cache[numeric_key],
                        "memory numeric comparison count differs")
                require(point not in witnessed, "duplicate memory byte/environment observation")
                witnessed.add(point)
            required = {point for point, (disposition, part) in classified[profile][partition["form"]].items()
                        if disposition == "S" and part == partition["id"]}
            require(witnessed == required, "memory supported binding lacks current observations")
    require(used == set(by_id), "orphan memory observation")
    test = observations["rustAdmissionTest"]
    if test is not None:
        fields(test, {"test", "liftSetSha256", "stdout", "stderr"}, "memory Rust admission observer")
        require(test["test"] == MEMORY_RUST_TEST and test["liftSetSha256"] == digest(memory_rust_lift_set(observations))
                and isinstance(test["stdout"], str) and isinstance(test["stderr"], str)
                and f"test {MEMORY_RUST_TEST} ... ok" in test["stdout"]
                and "test result: ok. 1 passed; 0 failed;" in test["stdout"], "memory Rust admission observer missing/stale")
    return len(used)


def assess_memory(legal, bindings, observations=None, root=ROOT, budget=DEFAULT_BUDGET):
    base = dict(schema=MEMORY_ASSESSMENT, sourceComplete=False, vendorFullDenominator=False,
                fullAmd64Coverage=False, candidateFullDomainBindings=0,
                sourceDerivationTrust="Reviewed AMD finite canonical memory-REP prefix rules; explicit flat-segment and normal-completion premises; no whole-manual proof",
                legalFormsSha256=digest(legal), bindingsSha256=digest(bindings),
                totalDisposition=False, implementationComplete=False, currentObservationsValidated=False,
                profileBindingsValidated=False)
    try:
        work = Budget(budget)
        _, domains = validate_memory_legal(legal, root, work)
        partitions, classified = validate_memory_bindings(bindings, legal, domains, root, work)
        observed = validate_memory_observations(observations, legal, bindings, partitions, classified, root) if observations is not None else 0
        validated = observations is not None and observations["rustAdmissionTest"] is not None
        consumers = []
        for profile in MEMORY_PROFILES:
            forms = []
            for name in sorted(domains):
                counts = Counter(disposition for disposition, _ in classified[profile][name].values())
                holes = domains[name] - set(classified[profile][name])
                forms.append(dict(form=name, domain=len(domains[name]), supported=counts["S"], unsupported=counts["U"],
                                  unresolved=counts["X"], holes=len(holes)))
            total = all(row["holes"] == 0 for row in forms)
            complete = total and all(row["unsupported"] == row["unresolved"] == 0 for row in forms)
            consumers.append(dict(profile=profile, forms=forms, totalDisposition=total,
                                  implementationDomainComplete=complete, profileBindingsValidated=validated,
                                  implementationComplete=complete and validated))
        return dict(base, status="checked", consumers=consumers,
                    enumeratedPoints=sum(len(domain) for domain in domains.values()),
                    totalDisposition=all(row["totalDisposition"] for row in consumers),
                    implementationComplete=consumers[-1]["implementationComplete"],
                    currentObservationsValidated=observations is not None, profileBindingsValidated=validated,
                    observationCount=observed, remainingEnumerationBudget=work.remaining)
    except BudgetExceeded as error:
        return dict(base, status="unknown", reason=str(error))


def query_memory(bindings, legal, observations, byte_string, environment, root=ROOT, budget=DEFAULT_BUDGET):
    result = assess_memory(legal, bindings, observations, root, budget)
    require(result["status"] == "checked", "memory query checker returned unknown")
    hex_bytes(byte_string, "consumed memory instruction")
    _, domains = validate_memory_legal(legal, root)
    _, classified = validate_memory_bindings(bindings, legal, domains, root)
    point = point_key(byte_string, environment)
    # Python equates True with 1 and 64 with 64.0. They are distinct protocol
    # environments and must not share an admitted byte/environment point.
    typed_environment = isinstance(environment, dict) and set(environment) == set(MEMORY_AXES) and all(
        any(type(value) is type(candidate) and value == candidate for candidate in MEMORY_AXES[axis])
        for axis, value in environment.items())
    matches = [dict(profile=profile, form=form, disposition=classified[profile][form].get(point, ("hole", None))[0],
                    partition=classified[profile][form].get(point, (None, None))[1])
               for profile in MEMORY_PROFILES for form in sorted(domains) if typed_environment and point in domains[form]]
    for match in matches:
        match["profileAdmissionValidated"] = result["profileBindingsValidated"] and match["disposition"] == "S"
    return dict(schema="ariadne.amd64-legal-query/v3", consumedBytes=byte_string, decodeEnvironment=environment,
                matches=matches, currentObservationsValidated=result["currentObservationsValidated"],
                limit="Only these exact AMD canonical memory-REP byte/environment points and plain-dependency profiles; no XED template full-domain binding.")


def build_memory_observations(legal, bindings, helper, runtime, source_pdf, source_bbox,
                              lods_runtime, rep_address_runtime, root=ROOT, run_rust=True, budget=DEFAULT_BUDGET):
    import os
    import tempfile
    work = Budget(budget)
    _, domains = validate_memory_legal(legal, root, work)
    partitions, classified = validate_memory_bindings(bindings, legal, domains, root, work)
    require(lods_runtime is not None and rep_address_runtime is not None, "fresh memory build needs both selected source runtimes")
    base = dict(helperPath=str(Path(helper).resolve()), helperSha256=sha(helper), runtimeRoot=str(Path(runtime).resolve()),
                runtimeLockPath="native/bap/toolchain.lock.json", runtimeLockSha256=sha(Path(root) / "native/bap/toolchain.lock.json"))
    producers = {"base": base}
    for name, directory in (("lods", lods_runtime), ("repAddress", rep_address_runtime)):
        directory = Path(directory).resolve()
        contract = SOURCE_PRODUCERS[name]
        producers[name] = dict(directory=str(directory), manifestSha256=sha(directory / "manifest.json"),
            executableSha256=sha(directory / (contract["stem"] + "-lift")),
            lockSha256=sha(Path(root) / contract["lock"]))
    manifests = validate_memory_producers(producers, bindings, root)
    evidence = dict(pdfPath=str(Path(source_pdf).resolve()), bboxPath=str(Path(source_bbox).resolve()), bboxSha256=sha(source_bbox))
    validate_source_evidence(legal, evidence)
    output = dict(schema=MEMORY_OBSERVATIONS, legalFormsSha256=digest(legal), bindingsSha256=digest(bindings),
                  sourceSha256=dict(bindings["implementationSources"]), producers=producers,
                  sourceEvidence=evidence, rows=[], rustAdmissionTest=None)
    snapshot = digest({"legal": digest(legal), "bindings": digest(bindings)})
    pending = []
    cases = memory_cases()
    for profile in MEMORY_PROFILES:
        for form in sorted(classified[profile]):
            for point, (disposition, partition_id) in sorted(classified[profile][form].items()):
                if disposition != "S":
                    continue
                partition = partitions[profile][partition_id]
                require(len(partition["observationIds"]) == 1, "fresh memory observer needs single-point partitions")
                pending.append((profile, cases[point[0]], partition))
    require(bool(pending), "empty supported memory domain")
    base_pending = [(index, entry) for index, entry in enumerate(pending) if entry[2]["producer"] == "base"]
    request = f"ARIADNE-BAP-LIFT 1 windows-amd64 {snapshot}\nbatch 0 {len(base_pending)}\n"
    request += "".join(f'0x{0x401000 + index * 32:016x} {entry[1]["bytes"]}\n' for index, entry in base_pending)
    runtime = Path(runtime).resolve()
    env = {**os.environ, "LD_LIBRARY_PATH": str(runtime / "usr/local/lib") + ":" + str(runtime / "usr/lib/x86_64-linux-gnu"),
           "XDG_STATE_HOME": str(runtime / "state"), "XDG_CACHE_HOME": str(runtime / "cache")}
    process = subprocess.run([str(Path(helper).resolve()), str(runtime / "usr/local/lib/bap")],
                             input=request, capture_output=True, text=True, timeout=300, env=env)
    require(process.returncode == 0, "fresh base memory producer failed: " + process.stderr[:2000])
    frames = [strict_json(line) for line in process.stdout.splitlines()]
    require(len(frames) == len(base_pending) + 2
            and frames[0] == {"schema": "ariadne.bap-ready/v1", "snapshot": snapshot, "target": "windows-amd64", "version": "2.5.0-alpha", "lifter": "legacy"}
            and frames[-1] == {"schema": "ariadne.bap-batch/v1", "batch": 0, "count": len(base_pending)}, "fresh base memory frame identities")
    base_frames = {index: frame for (index, _), frame in zip(base_pending, frames[1:-1])}
    numeric_cache = {}
    for index, (profile, case, partition) in enumerate(pending):
        producer_name = partition["producer"]
        va = f"0x{0x401000 + index * 32:016x}"
        if producer_name == "base":
            response = base_frames[index]
        else:
            executable = Path(producers[producer_name]["directory"]) / (SOURCE_PRODUCERS[producer_name]["stem"] + "-lift")
            process = subprocess.run([str(executable), "windows-amd64", snapshot, va, case["bytes"]],
                                     env={}, stdin=subprocess.DEVNULL, capture_output=True, timeout=60)
            require(process.returncode == 0 and len(process.stdout) <= 65536, "fresh selected source memory producer failed/budget")
            response = strict_json(process.stdout)
        row = dict(id=partition["observationIds"][0], partition=partition["id"], producer=producer_name,
                   request=dict(snapshot=snapshot, va=va, consumedBytes=case["bytes"], decodeEnvironment=case["environment"],
                                target="windows-amd64", profile=profile, consumer="plain-dependencies"),
                   response=response, astSha256=digest(response.get("bil")), comparisonCount=0)
        validate_memory_response(row, profile, case, producer_name, snapshot, manifests)
        numeric_key = (case["bytes"], row["astSha256"])
        if numeric_key not in numeric_cache:
            numeric_cache[numeric_key] = memory_comparisons(case, response["bil"])
        row["comparisonCount"] = numeric_cache[numeric_key]
        output["rows"].append(row)
    if run_rust:
        with tempfile.TemporaryDirectory(prefix="ariadne-memory-bindings-") as directory:
            path = Path(directory) / "lifts.json"
            lift_set = memory_rust_lift_set(output)
            path.write_text(json.dumps(lift_set))
            test = subprocess.run(["cargo", "test", "--offline", "--locked", "--lib", MEMORY_RUST_TEST, "--", "--ignored", "--exact"],
                cwd=root, env={**os.environ, "ARIADNE_REP_BINDING_LIFTS": str(path)}, text=True, capture_output=True, timeout=600)
            require(test.returncode == 0, "fresh memory Rust admission observer failed: " + test.stdout[-2000:] + test.stderr[-2000:])
            output["rustAdmissionTest"] = dict(test=MEMORY_RUST_TEST, liftSetSha256=digest(lift_set), stdout=test.stdout, stderr=test.stderr)
    validate_memory_observations(output, legal, bindings, partitions, classified, root)
    validate_memory_producers(output["producers"], bindings, root)
    require(output["sourceSha256"] == current_memory_sources(root), "source changed during memory observation campaign")
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("build", "check", "query"))
    parser.add_argument("--legal", type=Path, required=True)
    parser.add_argument("--bindings", type=Path, required=True)
    parser.add_argument("--observations", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--budget", type=int, default=DEFAULT_BUDGET)
    parser.add_argument("--helper", type=Path, default=ROOT / "target/ariadne-bap-lift")
    parser.add_argument("--runtime", type=Path, default=ROOT / "tmp/bap-setup/stable")
    parser.add_argument("--bytes")
    parser.add_argument("--environment", help="exact JSON decode environment")
    parser.add_argument("--require-implementation", action="store_true")
    parser.add_argument("--require-bindings", action="store_true", help="require current BIL and Rust profile validation")
    parser.add_argument("--skip-rust-admission", action="store_true", help="leave profile binding validation open")
    parser.add_argument("--source-pdf", type=Path)
    parser.add_argument("--source-bbox", type=Path)
    parser.add_argument("--lods-runtime", type=Path, help="v3 selected frozen v14 LODS runtime")
    parser.add_argument("--rep-address-runtime", type=Path, help="v3 selected AMD v15 address-size runtime")
    args = parser.parse_args()
    legal, bindings = read(args.legal), read(args.bindings)
    observations = read(args.observations) if args.observations else None
    if args.action == "build":
        require(args.source_pdf is not None and args.source_bbox is not None, "fresh build requires pinned source PDF and word boxes")
        if legal.get("schema") == MEMORY_LEGAL:
            result = build_memory_observations(legal, bindings, args.helper, args.runtime, args.source_pdf, args.source_bbox,
                args.lods_runtime, args.rep_address_runtime, run_rust=not args.skip_rust_admission, budget=args.budget)
        else:
            result = build_observations(legal, bindings, args.helper, args.runtime, args.source_pdf, args.source_bbox,
                                        run_rust=not args.skip_rust_admission, budget=args.budget)
    elif args.action == "query":
        require(args.bytes is not None and args.environment is not None, "query needs exact bytes/environment")
        result = query(bindings, legal, observations, args.bytes, strict_json(args.environment), budget=args.budget)
    else:
        result = assess(legal, bindings, observations, budget=args.budget)
    output = run_output(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n")
    if args.action == "check":
        print(f'Legal-domain pilot: {result["status"]}; total disposition={result["totalDisposition"]}; current bindings={result.get("profileBindingsValidated", False)}; implementation={result["implementationComplete"]}; full AMD64=false')
        return 0 if (result["status"] == "checked" and result["totalDisposition"]
                     and (not args.require_bindings or result.get("profileBindingsValidated", False))
                     and (not args.require_implementation or result["implementationComplete"])) else 3
    print(str(output))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, KeyError, OSError, subprocess.SubprocessError) as error:
        print("Legal-domain pilot rejected: " + str(error), file=sys.stderr)
        sys.exit(2)
