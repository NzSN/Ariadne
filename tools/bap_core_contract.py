"""A0 envelope/attribution admission only; no solver or state observer."""
import json
import math
import re

SCHEMA = "ariadne.bap-core/v1"
MAX_FRAME_BYTES = 8 * 1024 * 1024
ACTIONS = {
    "recovery": {"Visit": True, "FinishRecovery": False, "Propagate": True,
                 "FinishDataflow": False, "ExpandSlice": False, "FinishSlice": False},
    "stateflow": {"Propagate": True, "FinishStateflow": False},
}


class ContractError(ValueError):
    pass


def require(condition, reason):
    if not condition:
        raise ContractError(reason)


def address(value):
    require(isinstance(value, str) and re.fullmatch(r"0x[0-9a-f]{16}", value),
            "address must be canonical unsigned 64-bit hex")
    return int(value, 16)


def exact(value, keys):
    require(isinstance(value, dict) and set(value) == set(keys), "unexpected or missing fields")


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate JSON key")
        result[key] = value
    return result


def forbidden_number(value):
    raise ContractError("nonfinite JSON number: " + value)


def finite_float(value):
    result = float(value)
    require(math.isfinite(result), "nonfinite JSON number")
    return result


def decode_request(raw, identity, next_sequence, initialized):
    """Validate one request; callers retain all state and sequence ownership.

    Initialization payload semantics and enabled-action guards belong to the
    future native pass. Success here MUST NOT publish an admitted analysis.
    """
    require(type(raw) is bytes and 0 < len(raw) <= MAX_FRAME_BYTES, "frame size/type")
    require(raw.endswith(b"\n") and b"\n" not in raw[:-1], "exactly one JSON line required")
    require(type(next_sequence) is int and 0 <= next_sequence < 2**64, "invalid expected sequence")
    require(type(initialized) is bool, "invalid initialization state")
    try:
        request = json.loads(raw.decode("utf-8"), object_pairs_hook=unique_object,
                             parse_constant=forbidden_number, parse_float=finite_float)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as error:
        raise ContractError("malformed JSON frame") from error
    exact(request, ["schema", "session", "snapshot", "query", "family", "sequence", "operation", "payload"])
    require(request["schema"] == SCHEMA, "unsupported schema")
    for key in ("session", "snapshot", "query", "family"):
        require(isinstance(request[key], str) and bool(request[key]), "empty identity")
        require(request[key] == identity.get(key), "identity mismatch")
    require(re.fullmatch(r"[0-9a-f]{64}", request["query"]), "noncanonical query digest")
    require(request["family"] in ACTIONS, "unsupported analysis family")
    require(type(request["sequence"]) is int and request["sequence"] == next_sequence,
            "sequence mismatch")
    operation, payload = request["operation"], request["payload"]
    require(isinstance(operation, str) and isinstance(payload, dict), "operation/payload shape")
    if not initialized:
        require(next_sequence == 0 and operation == "initialize", "initialize must be first")
    else:
        require(operation != "initialize", "fresh process required for reinitialization")
    if operation == "initialize":
        exact(payload, ["profile", "input"])
        require(payload["profile"] == "normalized-fixed-input/v1", "unsupported input profile")
        require(isinstance(payload["input"], dict), "input must be an object")
    elif operation == "advance":
        action = payload.get("action")
        require(isinstance(action, str) and action in ACTIONS[request["family"]], "unsupported action")
        addressed = ACTIONS[request["family"]][action]
        exact(payload, ["action", "address"] if addressed else ["action"])
        if addressed:
            address(payload["address"])
    elif operation in ("observe", "finish", "reset"):
        exact(payload, [])
    else:
        raise ContractError("unsupported operation")
    return request


def validate_attribution(rows, snapshot, captured_sites):
    """Check namespace/attribution shape, not whether a BIR term really exists."""
    require(isinstance(snapshot, str) and snapshot, "snapshot required")
    require(isinstance(captured_sites, set), "captured site set required")
    for site in captured_sites:
        address(site)
    require(isinstance(rows, list) and len(rows) <= 65536, "attribution budget/type")
    seen = set()
    for row in rows:
        exact(row, ["term", "class", "origin", "snapshot", "va", "parents"])
        term = row["term"]
        require(isinstance(term, str) and term and term not in seen, "duplicate/empty term")
        seen.add(term)
        require(row["class"] in ("program", "sub", "blk", "def", "phi", "jmp", "arg"), "term class")
        require(row["snapshot"] == snapshot, "cross-snapshot attribution")
        parents = row["parents"]
        require(isinstance(parents, list) and all(isinstance(p, str) and p for p in parents), "parent type")
        require(len(parents) == len(set(parents)) and term not in parents, "duplicate/self parent")
        if row["origin"] == "machine":
            address(row["va"])
            require(row["va"] in captured_sites, "machine term lacks captured instruction")
        elif row["origin"] == "synthetic":
            require(row["va"] is None and bool(parents), "synthetic term needs parents and no invented VA")
        else:
            raise ContractError("origin kind")
    for row in rows:
        require(set(row["parents"]) <= seen, "unknown parent")
    # Reject cycles without recursion; shared ancestry and same-VA terms remain valid.
    resolved = set()
    while len(resolved) < len(rows):
        ready = {row["term"] for row in rows if set(row["parents"]) <= resolved} - resolved
        require(bool(ready), "cyclic attribution")
        resolved.update(ready)
