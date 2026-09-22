#!/usr/bin/env python3
"""Audit explicitly scoped AMD64 milestones without weakening full-manual closure.

This is a support/acceptance registry, not an instruction evaluator or a decoder.
A paired body is progress; only evidence-backed, profile-bound cases can be
advertised as verified steps. Outside-scope and unfinished cases stay unsupported.
"""
import argparse
import hashlib
import json
from pathlib import Path

from amd64_acceptance import check_evidence, checked_path, index_rows

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'Specs' / 'AMD64'
REQUIREMENTS = {
    'decoded-form-legality', 'operand-payload-binding', 'state-validity',
    'effects-flags-and-frames', 'fault-and-commit-behavior', 'instruction-boundary',
    'tla-lean-correspondence', 'conservative-analysis-projection',
}
STAGES = {'planned', 'partial', 'paired-body'}
PROFILE_SCHEMA_VERSION = 2


def read(path):
    return json.loads(path.read_text())


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def targets(profile, forms):
    by_id = {row['form_id']: row for row in forms['forms']}
    result = {}
    for milestone in profile['milestones']:
        for form_id in milestone['form_ids']:
            if form_id not in by_id:
                raise ValueError(f'Unknown source form: {form_id}')
            form = by_id[form_id]
            kinds = [list(op['allowed_concrete_kinds']) for op in form['operands']]
            if milestone['operand_projection'] == 'no-explicit-memory':
                kinds = [[kind for kind in allowed if kind != 'memory'] for allowed in kinds]
            elif milestone['operand_projection'] != 'source-operands':
                raise ValueError('Unknown operand projection')
            if any(not allowed for allowed in kinds):
                raise ValueError(f'Empty operand projection: {form_id}')
            case_id = milestone['id'] + ':' + form_id
            if case_id in result:
                raise ValueError('Duplicate target case')
            result[case_id] = dict(id=case_id, milestone_id=milestone['id'],
                                  form_id=form_id, operand_kinds=kinds,
                                  source_form_sha256=digest(form))
    return result


def case_digest(target, progress_row):
    """Bind formal evidence to the exact reviewed, implemented case claim."""
    claim = dict(target=target,
                 implementation_stage=progress_row['implementation_stage'],
                 review=progress_row['review'],
                 open_obligations=progress_row['open_obligations'])
    return digest(claim)


def check_scoped_evidence(coverage, root, semantic_case_ids, fallback_id):
    """Validate only evidence reachable from this profile's acceptance roots.

    The full-manual ledger gate deliberately validates every accepted roadmap
    record. A profile milestone instead closes over its cited semantic cases and
    unsupported fallback, including their recursive foundations/dependencies.
    """
    records = index_rows(coverage['validation_records'], 'validation')
    cases = index_rows(coverage['semantic_cases'], 'semantic case')
    foundations = index_rows(coverage.get('foundation_components', []), 'foundation component')
    dependencies = index_rows(coverage['system_dependencies'], 'system dependency')
    evidence_paths = {}
    validated = set()
    visiting = set()

    def paths_for(check):
        if check not in records:
            raise ValueError(f'Missing validation evidence: {check}')
        if check not in evidence_paths:
            evidence_paths[check] = check_evidence(records[check], root)
        return evidence_paths[check]

    def accepted_leaf(kind, item):
        key = (kind, item['id'])
        if key in validated or key in visiting:
            return
        if item['status'] != 'accepted':
            raise ValueError(f'Profile cites unaccepted {kind}: {item["id"]}')
        if not item.get('description') or item.get('open_obligations') != []:
            raise ValueError(f'Accepted item still has unclosed scope: {item["id"]}')
        if not item.get('checks') or not item.get('rules'):
            raise ValueError(f'Accepted item lacks rules/checks: {item["id"]}')
        visiting.add(key)
        for foundation_id in item.get('foundations', []):
            if foundation_id not in foundations:
                raise ValueError(f'Unknown foundation component: {foundation_id}')
            accepted_leaf('foundation component', foundations[foundation_id])
        for dependency_id in item.get('dependencies', []):
            if dependency_id not in dependencies:
                raise ValueError(f'Unknown system dependency: {dependency_id}')
            accepted_leaf('system dependency', dependencies[dependency_id])
        kinds = set()
        covered_paths = set()
        paths_by_kind = {}
        for check in item['checks']:
            paths = paths_for(check)
            evidence_kind = records[check]['kind']
            kinds.add(evidence_kind)
            covered_paths.update(paths)
            paths_by_kind.setdefault(evidence_kind, set()).update(paths)
        if not {'tla-typecheck', 'lean-build', 'lean-axiom-audit'} <= kinds:
            raise ValueError(f'Missing TLA+/Lean evidence: {item["id"]}')
        if not kinds & {'tlc', 'apalache'}:
            raise ValueError(f'Missing executable TLA+ evidence: {item["id"]}')
        languages = set()
        for rule in item['rules']:
            path = checked_path(root, rule['path'])
            if rule['path'] not in covered_paths or not rule.get('symbol'):
                raise ValueError(f'Rule not bound to checked sources: {item["id"]}')
            if path.suffix not in {'.tla', '.lean'}:
                raise ValueError('A semantic rule must refer to TLA+ or Lean source')
            if path.suffix == '.lean' and not all(
                    rule['path'] in paths_by_kind[evidence_kind]
                    for evidence_kind in ['lean-build', 'lean-axiom-audit']):
                raise ValueError('Lean rule is not bound to both build and axiom-audit evidence')
            if path.suffix == '.tla' and (
                    rule['path'] not in paths_by_kind['tla-typecheck'] or
                    rule['path'] not in paths_by_kind.get('tlc', set()) |
                        paths_by_kind.get('apalache', set())):
                raise ValueError('TLA+ rule is not bound to typechecking and executable evidence')
            languages.add(path.suffix)
        if languages != {'.tla', '.lean'}:
            raise ValueError(f'Accepted item needs both formalizations: {item["id"]}')
        visiting.remove(key)
        validated.add(key)

    for case_id in semantic_case_ids:
        if case_id not in cases:
            raise ValueError(f'Profile cites unknown semantic evidence: {case_id}')
        accepted_leaf('semantic case', cases[case_id])
    fallback = foundations.get(fallback_id)
    fallback_ready = bool(fallback and fallback['status'] == 'accepted')
    if fallback_ready:
        accepted_leaf('foundation component', fallback)
    return cases, foundations, fallback_ready


def inspect(profile, progress, coverage, forms, fields, root):
    if (profile['schema_version'] != PROFILE_SCHEMA_VERSION or
            progress['schema_version'] != PROFILE_SCHEMA_VERSION):
        raise ValueError('Unknown profile/progress schema version')
    if coverage['schema_version'] != 2:
        raise ValueError('Unknown acceptance ledger schema version')
    milestone_ids = [item['id'] for item in profile['milestones']]
    if len(set(milestone_ids)) != len(milestone_ids):
        raise ValueError('Duplicate milestone IDs')
    if profile['id'] != progress['profile_id'] or progress['profile_sha256'] != digest(profile):
        raise ValueError('Profile changed without a reviewed progress migration')
    if profile['authority'] != forms['authority']:
        raise ValueError('Profile source authority differs from the form catalogue')
    if set(profile['required_case_obligations']) != REQUIREMENTS:
        raise ValueError('Profile obligations were removed or changed')
    expected = targets(profile, forms)
    source_forms = {row['form_id']: row for row in forms['forms']}
    if len(source_forms) != len(forms['forms']):
        raise ValueError('Duplicate form IDs in source inventory')
    if profile['active_milestone'] not in {item['id'] for item in profile['milestones']}:
        raise ValueError('Active milestone is absent')
    rows = {row['id']: row for row in progress['cases']}
    if len(rows) != len(progress['cases']) or set(rows) != set(expected) or not rows:
        raise ValueError('Progress must retain every targeted case exactly once')
    fallback_id = profile['unsupported_policy']['foundation_id']
    references = {reference for row in rows.values() for reference in row['semantic_cases']}
    cases, foundations, fallback_accepted = check_scoped_evidence(
        coverage, root, references, fallback_id)
    fallback = foundations.get(fallback_id)
    fallback_ready = bool(fallback_accepted and
                          fallback.get('profile_sha256') == digest(profile))
    verified = []
    for case_id, row in rows.items():
        for key, value in expected[case_id].items():
            if row.get(key) != value:
                raise ValueError(f'Target identity/projection changed: {case_id}')
        if row['implementation_stage'] not in STAGES:
            raise ValueError('Unknown implementation stage')
        if row['review']['status'] not in {'pending', 'reviewed'}:
            raise ValueError('Unknown source review status')
        source_evidence = row['review'].get('source_evidence')
        if (not isinstance(source_evidence, list) or
                any(not isinstance(item, str) or not item.strip() for item in source_evidence)):
            raise ValueError(f'Invalid profile-case source evidence: {case_id}')
        case_hash = case_digest(expected[case_id], row)
        references = row['semantic_cases']
        evidence_ready = bool(references)
        covered_requirements = set()
        for reference in references:
            item = cases[reference]
            scope = item.get('profile_scope', {})
            if (scope.get('profile_id') != profile['id'] or
                    scope.get('profile_sha256') != digest(profile) or
                    scope.get('case_sha256', {}).get(case_id) != case_hash or
                    row['form_id'] not in item.get('form_ids', []) or
                    not set(source_forms[row['form_id']]['entry_ids']) <=
                        set(item.get('source_entry_ids', []))):
                raise ValueError(f'Semantic evidence belongs to another profile/case: {reference}')
            closed = set(scope.get('closed_obligations', []))
            if not closed <= REQUIREMENTS:
                raise ValueError(f'Unknown closed profile obligation: {reference}')
            covered_requirements.update(closed)
        if (evidence_ready and REQUIREMENTS <= covered_requirements and
                row['review']['status'] == 'reviewed' and source_evidence and
                not row['open_obligations'] and
                row['implementation_stage'] == 'paired-body' and fallback_ready):
            verified.append(case_id)
    milestones = []
    for milestone in profile['milestones']:
        selected = [row for row in rows.values() if row['milestone_id'] == milestone['id']]
        checked = sum(row['id'] in verified for row in selected)
        milestones.append(dict(id=milestone['id'], targeted=len(selected), verified=checked,
                               paired_bodies=sum(row['implementation_stage'] == 'paired-body' for row in selected),
                               complete=bool(selected) and checked == len(selected)))
    return dict(profile_id=profile['id'], profile_sha256=digest(profile),
                active_milestone=profile['active_milestone'], delivery=profile['delivery'], targeted_cases=len(rows),
                paired_body_cases=sum(row['implementation_stage'] == 'paired-body' for row in rows.values()),
                verified_cases=len(verified), verified_case_ids=sorted(verified),
                unsupported_cases=len(rows)-len(verified), fallback_accepted=fallback_ready,
                milestones=milestones, complete=all(row['complete'] for row in milestones))


def route(profile, report, case_id, mode, cpl):
    """Return an inventory candidate, never a runtime certification or handler."""
    if mode != profile['execution']['mode'] or cpl != profile['execution']['cpl']:
        return {'kind': 'unsupported', 'reason': 'outside-declared-profile'}
    if (report['profile_id'] != profile['id'] or report['profile_sha256'] != digest(profile)
            or case_id not in report['verified_case_ids']):
        return {'kind': 'unsupported', 'reason': 'semantics-not-accepted'}
    return {'kind': 'profile-case-candidate', 'certified': False,
            'requires': 're-run acceptance and validate concrete payload/state/profile preconditions'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['check', 'report'])
    parser.add_argument('--require-milestone')
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()
    try:
        profile = read(DATA/'user64-profile.json')
        result = inspect(profile, read(DATA/'user64-coverage.json'), read(DATA/'coverage.json'),
                         read(DATA/'forms.json'), read(DATA/'state-fields.json'), ROOT)
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(f"{result['profile_id']}: active milestone {result['active_milestone']}")
            for row in result['milestones']:
                print(f"  {row['id']}: {row['paired_bodies']} paired bodies; "
                      f"{row['verified']}/{row['targeted']} verified; "
                      f"{'complete' if row['complete'] else 'pending'}")
            print('Paired bodies are not advertised instruction-step support. Full-manual coverage is a separate roadmap gate.')
        if args.require_milestone:
            row = next((row for row in result['milestones'] if row['id'] == args.require_milestone), None)
            if row is None:
                raise ValueError('Unknown milestone')
            if not row['complete']:
                raise ValueError(f"Milestone {row['id']} is pending; unsupported fallback or semantic obligations remain")
    except (ValueError, KeyError) as error:
        parser.exit(1, f'profile error: {error}\n')


if __name__ == '__main__':
    main()
