#!/usr/bin/env python3
"""Bounded source/LLVM observation gate for AMD64-F-0503-R, not ISA acceptance."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from amd64_profile import case_digest, digest, targets  # noqa: E402

CASE_ID = 'register-core:AMD64-F-0503-R'
FORM_ID = 'AMD64-F-0503-R'
PROFILE_HASH = '5c07adb4b1391d5b2ec29348b208789c2469b2728afd700f27cd3a90bef078cf'
FORM_HASH = 'd45a228c0720624d73a267ced2b728de85f0058ef94601f61e459329f8fbaa29'
NATIVE_VERSION = 'ariadne-llvm-mc 20.1.2 protocol 2\n'

# Exact bytes are independent of the helper's disassembly; expected rows are
# frozen observations of LLVM 20.1.2 under both target profiles.
CASES = (
    ('rax-negative-one', '48c7c0ffffffff', 'MOV64ri32', 'r:RAX', 'i:-1', 7, True),
    ('rax-sign-bit', '48c7c000000080', 'MOV64ri32', 'r:RAX', 'i:-2147483648', 7, True),
    ('r8-sign-bit', '49c7c000000080', 'MOV64ri32', 'r:R8', 'i:-2147483648', 7, True),
    ('rex-over-66', '6648c7c0ffffffff', 'MOV64ri32', 'r:RAX', 'i:-1', 8, True),
    ('missing-rex-w', 'c7c0ffffffff', 'MOV32ri_alt', 'r:EAX', 'i:4294967295', 6, False),
    ('memory-alternative', '48c700ffffffff', 'MOV64mi32', None, None, 7, False),
    ('illegal-lock', 'f048c7c0ffffffff', 'LOCK_PREFIX', None, None, 1, False),
    ('wrong-modrm-group', '48c7c8ffffffff', '-', None, None, 0, False),
)
SOURCES = (
    'Specs/AMD64/manuals.lock.json', 'Specs/AMD64/forms.json',
    'Specs/AMD64/user64-profile.json', 'Specs/AMD64/user64-coverage.json',
    'native/llvm_mc/decode.cpp', 'tools/check_stage_d_mov_binding.py',
)


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_helper(helper, argument, input_text=''):
    result = subprocess.run([str(helper), argument], input=input_text,
                            capture_output=True, text=True, timeout=30)
    if result.returncode or result.stderr:
        raise ValueError(f'helper failed {argument}: {result.stderr or result.returncode}')
    return result.stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--helper', type=Path, default=ROOT / 'target/ariadne-llvm-mc')
    parser.add_argument('--manual-cache', type=Path, default=Path('/tmp/ariadne-amd-sources'))
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    before = {name: sha256(ROOT / name) for name in SOURCES}
    lock = json.loads((ROOT / SOURCES[0]).read_text())
    manuals = {}
    for source in lock['sources']:
        path = args.manual_cache / source['filename']
        if not path.is_file() or sha256(path) != source['sha256'] or path.stat().st_size != source['bytes']:
            raise ValueError(f'pinned AMD manual unavailable or changed: {path}')
        manuals[source['filename']] = source['sha256']

    forms = json.loads((ROOT / SOURCES[1]).read_text())
    profile = json.loads((ROOT / SOURCES[2]).read_text())
    progress = json.loads((ROOT / SOURCES[3]).read_text())
    form = next(row for row in forms['forms'] if row['form_id'] == FORM_ID)
    case = next(row for row in progress['cases'] if row['id'] == CASE_ID)
    if digest(form) != FORM_HASH or case['source_form_sha256'] != FORM_HASH:
        raise ValueError('first-case source-form hash changed')
    if digest(profile) != PROFILE_HASH or progress['profile_sha256'] != PROFILE_HASH:
        raise ValueError('first-case profile hash changed')
    if case['milestone_id'] != 'register-core' or case['semantic_cases']:
        raise ValueError('first-case status changed; review before reusing this observation')
    if case['operand_kinds'] != [['gpr'], ['immediate']]:
        raise ValueError('register-only projection changed')
    if form['encoding']['source_text'] != 'C7 /0 id' or form['encoding']['modrm']['reg_field'] != 0:
        raise ValueError('source encoding changed')
    if form['encoding']['rex'] != {'knowledge': 'table-evidence', 'w_required': False}:
        raise ValueError('literal table-evidence REX field changed; re-review needed')
    if 'rex-w' not in form['constraints']['prefixes']['required']:
        raise ValueError('derived long64 REX.W requirement changed')
    immediate = form['operands'][1]
    if (immediate['encoded_width_bits'], immediate['semantic_width_bits'], immediate['extension']) != (32, 64, 'sign'):
        raise ValueError('immediate extension metadata changed')
    if form['operands'][0]['kind'] != 'gpr' or form['operands'][0]['width_bits'] != 64:
        raise ValueError('destination is no longer an exact 64-bit GPR')
    if form['constraints']['prefixes']['lock'] != 'forbidden-#UD':
        raise ValueError('LOCK architectural outcome metadata changed')
    case_hash = case_digest(targets(profile, forms)[CASE_ID], case)

    helper = args.helper.resolve()
    if run_helper(helper, '--protocol-version') != NATIVE_VERSION:
        raise ValueError('expected pinned LLVM 20.1.2 protocol 2')
    if run_helper(helper, '--protocol-version=linux') != (
            'ariadne-llvm-mc 20.1.2 protocol 2 target x86_64-unknown-linux-gnu\n'):
        raise ValueError('expected pinned LLVM 20.1.2 Linux target')
    rows = {}
    batch = ''.join(f'{4096 + n * 16} {item[1]}\n' for n, item in enumerate(CASES))
    for target, option in [('windows-amd64', '--protocol=2'),
                           ('linux-amd64', '--protocol=2-linux')]:
        result = run_helper(helper, option, batch).splitlines()
        if len(result) != len(CASES):
            raise ValueError(f'{target}: wrong decoder row count')
        observed = []
        for n, (name, bytes_hex, opcode, register, immediate_token, length, admitted) in enumerate(CASES):
            fields = result[n].split()
            if len(fields) < 3 or fields[1] != opcode:
                raise ValueError(f'{target}/{name}: opcode changed: {result[n]}')
            address = str(4096 + n * 16)
            if admitted:
                if (fields[0:5] != ['v2', opcode, '2', register, immediate_token]
                        or fields[-5:] != [address, 'ok', str(length), 'ordinary', '-']):
                    raise ValueError(f'{target}/{name}: payload or length changed: {result[n]}')
            else:
                expected_tail = ([address, 'invalid', '0', '-', '-'] if opcode == '-'
                                 else [address, 'ok', str(length), 'ordinary', '-'])
                if fields[-5:] != expected_tail:
                    raise ValueError(f'{target}/{name}: negative control changed: {result[n]}')
            observed.append({'name': name, 'bytesHex': bytes_hex,
                             'candidate': admitted, 'decoderRecord': result[n]})
        rows[target] = observed
    stable = before == {name: sha256(ROOT / name) for name in SOURCES}
    report = {'recordedUtc': datetime.now(timezone.utc).isoformat(),
              'caseId': CASE_ID, 'caseSha256': case_hash, 'formSha256': FORM_HASH,
              'profileSha256': PROFILE_HASH, 'manualSha256': manuals,
              'decoderSha256': sha256(helper), 'sourceSha256': before,
              'sourcesStable': stable, 'targets': rows,
              'scope': 'source/decoder observation only; no instruction-step acceptance',
              'passed': stable}
    if args.report:
        args.report.write_text(json.dumps(report, indent=2) + '\n')
        print(args.report)
    else:
        print(json.dumps(report, indent=2))
    if not stable:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
