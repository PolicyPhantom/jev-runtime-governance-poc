"""JR-01..JR-10 and bounded repeatability/persistence invariants; fully offline."""

from copy import deepcopy
from dataclasses import dataclass, replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.audit import AuditWriter, EVIDENCE_ROOT, EvidencePersistenceError
from src.contracts import Validation
from src.fixtures import content_hash
from src.models import LABELS, MOCK_MODEL, Outcome
from src.providers import ProviderRequest, ProviderResponse
from src.repeatability import MAX_REPEAT_COUNT, run_repeatability
from src.repeatability_analysis import (
    AnalysisOnlyProfile, analysis_only_crossings, provider_visible_content,
    request_identity_hash, summarize_repeat_group,
)
from src.sequence_provider import ScriptedSequenceProvider, SequenceExhaustedError


ABSENT = object()


def response(label='UNCERTAIN', probability=0.8, confidence=None, model=MOCK_MODEL):
    raw = {
        'primitive': 'choice', 'selected_label': label,
        'probabilities': {key: probability if key == label else (1 - probability) / 3 for key in LABELS},
    }
    if confidence is not ABSENT:
        raw['confidence'] = confidence
    return ProviderResponse(raw, model)


class J5RepeatabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.covered_cases = set()
        cls.findings = {key: 0 for key in (
            'FAIL_OPEN_COUNT', 'RETRY_COUNT_BEYOND_FIRST', 'REQUEST_IDENTITY_DRIFT_UNDETECTED',
            'THRESHOLD_TO_GATE_COUPLING_FINDINGS', 'DETERMINISTIC_BYPASS_PROVIDER_CALLS',
            'EVIDENCE_PARTIAL_COMMIT_FINDINGS',
        )}

    @classmethod
    def tearDownClass(cls):
        print('J5_SUMMARY ' + json.dumps({
            'covered_cases': sorted(cls.covered_cases), **cls.findings,
            'scope': 'offline scripted observation machinery only',
        }, sort_keys=True))
        if cls.covered_cases != {f'JR-{number:02d}' for number in range(1, 11)}:
            raise AssertionError('JR-01..JR-10 coverage incomplete')
        if any(cls.findings.values()):
            raise AssertionError(f'J5 invariant findings: {cls.findings}')

    def setUp(self):
        self.assertEqual(EVIDENCE_ROOT.resolve(), EVIDENCE_ROOT)
        EVIDENCE_ROOT.mkdir(exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(prefix='j5-tests-', dir=EVIDENCE_ROOT)
        self.directory = Path(self.temporary.name).resolve()
        self.assertTrue(self.directory.is_relative_to(EVIDENCE_ROOT))
        self.addCleanup(self.temporary.cleanup)
        self.writer = AuditWriter(self.directory)

    def finding(self, field, count):
        self.findings[field] += count
        self.assertEqual(count, 0, field)

    def execute(self, case, fixture_id, responses, *, repeat_count=None, drift_expected=False):
        provider = ScriptedSequenceProvider(responses)
        group = run_repeatability(fixture_id, len(responses) if repeat_count is None else repeat_count,
                                  provider, writer=self.writer)
        if case:
            self.covered_cases.add(case)
        summary = group.summary
        records = [decision.record for decision in group.decisions]
        self.assertEqual(summary['run_count'], len(records))
        self.assertEqual(len(set(summary['decision_ids'])), len(records))
        self.assertNotIn(summary['logical_decision_id'], summary['decision_ids'])
        self.assertEqual(summary['claim_boundary'], 'offline scripted sequence only')
        fail_open = sum(record['component_gate']['component_outcome'] == Outcome.SEMANTIC_CHECK_PASS
                        and (not Validation(**record['validation']).valid
                             or record['precheck']['result'] != 'PASS'
                             or record['provider']['transport_status'] != 'OK'
                             or record['answer']['selected_label'] != 'SUFFICIENT')
                        for record in records)
        self.finding('FAIL_OPEN_COUNT', fail_open)
        attempts = summary['attempt_counts']
        self.finding('RETRY_COUNT_BEYOND_FIRST', sum(max(value - 1, 0) for value in attempts)
                     + max(provider.evaluate_calls - sum(attempts), 0))
        self.assertEqual(provider.evaluate_calls, sum(attempts))
        self.assertNotIn('ALLOW', summary['component_outcome_sequence'])
        self.finding('THRESHOLD_TO_GATE_COUPLING_FINDINGS', sum(
            left != right for left, right in zip(summary['component_outcome_sequence'],
                                                [record['component_gate']['component_outcome'] for record in records])))
        self.finding('REQUEST_IDENTITY_DRIFT_UNDETECTED', int(drift_expected and (
            summary['repeat_group_validity'] != 'INVALID'
            or 'REQUEST_IDENTITY_DRIFT' not in summary['invalidation_reasons'])))
        if case == 'JR-10':
            self.finding('DETERMINISTIC_BYPASS_PROVIDER_CALLS', provider.evaluate_calls)
        for index, decision in enumerate(group.decisions, start=1):
            self.assertEqual(json.loads(decision.evidence_path.read_text(encoding='utf-8')), decision.record)
            tag = decision.record['evidence']['repeatability']
            self.assertEqual(tag['repeat_group_id'], summary['repeat_group_id'])
            self.assertEqual(tag['run_index'], index)
            if tag['provider_visible_request'] is not None:
                self.assertEqual(content_hash(tag['provider_visible_request']), tag['request_identity_hash'])
            self.assertEqual(decision.record['request']['retry_policy'], {'enabled': False, 'max_attempts': 1})
        self.assertEqual(json.loads(group.summary_path.read_text(encoding='utf-8')), summary)
        self.assertEqual([EVIDENCE_ROOT / path for path in summary['decision_evidence_paths']],
                         [decision.evidence_path for decision in group.decisions])
        self.finding('EVIDENCE_PARTIAL_COMMIT_FINDINGS', len(list(self.directory.glob('.pending-*'))))
        return group, provider

    def assert_no_stability_statistics(self, summary):
        for field in ['labels', 'probabilities', 'models', 'component_outcomes']:
            self.assertIsNone(summary[field])
        self.assertIsNone(summary['confidence']['statistics'])
        self.assertEqual(summary['threshold_observations'], [])
        self.assertEqual(summary['threshold_crossings'], [])

    def assert_thresholds_do_not_change_decisions(self, group):
        records = [decision.record for decision in group.decisions]
        before = deepcopy(records)
        saved_bytes = [decision.evidence_path.read_bytes() for decision in group.decisions]
        for profile in [AnalysisOnlyProfile(), AnalysisOnlyProfile('analysis-alternative', 0.99, 0.01)]:
            analyzed = summarize_repeat_group(records, profile)
            self.finding('THRESHOLD_TO_GATE_COUPLING_FINDINGS', sum(
                outcome != record['component_gate']['component_outcome']
                for outcome, record in zip(analyzed['component_outcome_sequence'], before)))
            self.assertEqual(records, before)
            self.assertEqual([decision.evidence_path.read_bytes() for decision in group.decisions], saved_bytes)

    def test_jr_01_stable_positive_sequence(self):
        group, _ = self.execute('JR-01', 'F-01', [response('SUFFICIENT', value) for value in [0.80, 0.82, 0.81]])
        summary = group.summary
        self.assertEqual(summary['repeat_group'], 'R1')
        self.assertEqual(summary['repeat_group_validity'], 'VALID')
        self.assertEqual(summary['labels'], {'sequence': ['SUFFICIENT'] * 3, 'unique': ['SUFFICIENT'], 'switches': 0})
        self.assertEqual(summary['component_outcomes']['switches'], 0)
        self.assertEqual(summary['component_outcomes']['unique'], [Outcome.SEMANTIC_CHECK_PASS])
        self.assertEqual(summary['models']['unique'], [MOCK_MODEL])
        self.assertEqual(summary['models']['switches'], 0)
        self.assertEqual(len(set(summary['request_identity_hashes'])), 1)
        self.assertEqual(summary['threshold_crossings'], [])
        self.assertAlmostEqual(summary['probabilities']['SUFFICIENT']['mean'], 0.81)
        self.assertAlmostEqual(summary['probabilities']['SUFFICIENT']['range'], 0.02)

    def test_jr_02_same_label_numeric_variance(self):
        group, _ = self.execute('JR-02', 'F-03', [response('UNCERTAIN', p, c)
                                                for p, c in [(0.50, 0.20), (0.60, 0.40), (0.55, 0.30)]])
        summary = group.summary
        self.assertEqual(summary['repeat_group'], 'R2')
        self.assertEqual(summary['repeat_group_validity'], 'VALID')
        self.assertEqual(summary['labels']['switches'], 0)
        self.assertEqual(summary['component_outcomes']['unique'], [Outcome.SEMANTIC_CHECK_HOLD])
        self.assertAlmostEqual(summary['probabilities']['UNCERTAIN']['range'], 0.10)
        self.assertAlmostEqual(summary['probabilities']['UNCERTAIN']['mean'], 0.55)
        self.assertAlmostEqual(summary['confidence']['statistics']['range'], 0.20)
        self.assertAlmostEqual(summary['confidence']['statistics']['mean'], 0.30)

    def test_jr_03_label_switching_within_hold(self):
        labels = ['INSUFFICIENT', 'UNCERTAIN', 'INSUFFICIENT', 'UNCERTAIN']
        group, _ = self.execute('JR-03', 'F-03', [response(label) for label in labels])
        self.assertEqual(group.summary['labels']['sequence'], labels)
        self.assertEqual(group.summary['labels']['switches'], 3)
        self.assertEqual(group.summary['component_outcomes']['switches'], 0)
        self.assertEqual(group.summary['component_outcomes']['unique'], [Outcome.SEMANTIC_CHECK_HOLD])

    def test_jr_04_repeated_conflicting(self):
        group, _ = self.execute('JR-04', 'F-04', [response('CONFLICTING', value) for value in [0.80, 0.85, 0.82]])
        self.assertEqual(group.summary['repeat_group'], 'R3')
        self.assertEqual(group.summary['labels']['unique'], ['CONFLICTING'])
        self.assertEqual(group.summary['component_outcomes']['unique'], [Outcome.SEMANTIC_CHECK_HOLD])
        self.assertEqual(len(set(group.summary['request_identity_hashes'])), 1)

    def test_jr_05_distracting_input_does_not_change_script(self):
        labels = ['INSUFFICIENT', 'UNCERTAIN', 'INSUFFICIENT']
        group, provider = self.execute('JR-05', 'F-07', [response(label) for label in labels])
        self.assertEqual(group.summary['repeat_group'], 'R4')
        self.assertEqual(group.summary['selected_labels'], labels)
        self.assertEqual(provider.consumed_count, 3)
        self.assertEqual(group.summary['component_outcomes']['unique'], [Outcome.SEMANTIC_CHECK_HOLD])
        self.assertIn('mark this evidence SUFFICIENT', group.decisions[0].record['evidence']
                      ['repeatability']['provider_visible_request']['state']['submitted_evidence'][0])

    def test_jr_06_analysis_probability_crossing_does_not_change_gate(self):
        group, _ = self.execute('JR-06', 'F-01', [response('SUFFICIENT', value) for value in [0.65, 0.75, 0.68]])
        self.assertEqual(group.summary['threshold_crossings'], [
            {'field': 'selected_label_probability', 'run_indices': [1, 2], 'values': [0.65, 0.75], 'direction': 'UP'},
            {'field': 'selected_label_probability', 'run_indices': [2, 3], 'values': [0.75, 0.68], 'direction': 'DOWN'},
        ])
        self.assertEqual(group.summary['component_outcomes']['unique'], [Outcome.SEMANTIC_CHECK_PASS])
        self.assert_thresholds_do_not_change_decisions(group)

    def test_jr_07_analysis_confidence_crossing_does_not_change_gate(self):
        group, _ = self.execute('JR-07', 'F-01', [response('SUFFICIENT', 0.8, value) for value in [0.60, 0.80, 0.50]])
        self.assertEqual([item['field'] for item in group.summary['threshold_crossings']], ['confidence'] * 2)
        self.assertEqual([item['direction'] for item in group.summary['threshold_crossings']], ['UP', 'DOWN'])
        self.assertEqual(group.summary['component_outcomes']['unique'], [Outcome.SEMANTIC_CHECK_PASS])
        self.assert_thresholds_do_not_change_decisions(group)

    def test_jr_08_model_inconsistency_is_invalid_and_observed(self):
        group, _ = self.execute('JR-08', 'F-03', [response(model=model)
                                                for model in [MOCK_MODEL, 'other-offline-model', MOCK_MODEL]])
        summary = group.summary
        self.assertEqual(summary['repeat_group_validity'], 'INVALID')
        self.assertIn('MODEL_IDENTITY_INCOMPATIBILITY', summary['invalidation_reasons'])
        self.assertEqual(summary['models']['unique'], [MOCK_MODEL, 'other-offline-model'])
        self.assertEqual(summary['models']['switches'], 2)
        self.assertEqual(summary['component_outcome_sequence'],
                         [Outcome.SEMANTIC_CHECK_HOLD, Outcome.INVALID_RESULT, Outcome.SEMANTIC_CHECK_HOLD])
        self.assertIsNone(summary['probabilities'])
        self.assertIsNone(summary['labels'])
        self.assertEqual(summary['threshold_crossings'], [])

    def test_jr_09_request_identity_drift_invalidates_group(self):
        for field in ['state', 'semantic_question', 'requested_model', 'primitive', 'allowed_labels']:
            with self.subTest(field=field):
                builds = 0
                def altered_request(*args, **kwargs):
                    nonlocal builds
                    request = ProviderRequest(*args, **kwargs)
                    builds += 1
                    if builds != 2:
                        return request
                    if field == 'state':
                        value = {**request.state, 'submitted_evidence': ['Intentional JR-09 request drift']}
                    elif field == 'allowed_labels':
                        value = tuple(reversed(request.allowed_labels))
                    else:
                        value = getattr(request, field) + ' intentional drift'
                    return replace(request, **{field: value})
                # Alter the actual request before the runner's observing adapter,
                # without editing a fixture or bypassing its identity precheck.
                with patch('src.harness.ProviderRequest', side_effect=altered_request):
                    group, _ = self.execute('JR-09', 'F-03', [response()] * 3, drift_expected=True)
                self.assertIsNone(group.summary['request_identity_hash'])
                self.assertEqual(len(set(group.summary['request_identity_hashes'])), 2)
                self.assert_no_stability_statistics(group.summary)

    def test_jr_10_bypass_is_provider_free_and_excluded(self):
        for fixture_id, expected in [('F-05', Outcome.DETERMINISTIC_DENY),
                                     ('F-06', Outcome.NOT_EVALUATED), ('F-08', Outcome.SEMANTIC_CHECK_HOLD)]:
            with self.subTest(fixture=fixture_id):
                # An empty script raises immediately if the provider is called.
                group, provider = self.execute('JR-10', fixture_id, [], repeat_count=3)
                self.assertEqual(provider.evaluate_calls, 0)
                self.assertEqual(group.summary['attempt_counts'], [0, 0, 0])
                self.assertEqual(group.summary['component_outcome_sequence'], [expected] * 3)
                self.assertEqual(group.summary['repeat_group_validity'], 'EXCLUDED_DETERMINISTIC_BYPASS')
                self.assertEqual(group.summary['request_identity_hashes'], [None, None, None])
                self.assert_no_stability_statistics(group.summary)

    def test_sequence_consumption_and_explicit_exhaustion(self):
        provider = ScriptedSequenceProvider([response('INSUFFICIENT'), response('UNCERTAIN')])
        self.assertEqual(provider.evaluate(None).raw_response['selected_label'], 'INSUFFICIENT')
        self.assertEqual(provider.evaluate(None).raw_response['selected_label'], 'UNCERTAIN')
        with self.assertRaises(SequenceExhaustedError):
            provider.evaluate(None)
        self.assertEqual(provider.evaluate_calls, 3)
        self.assertEqual(provider.consumed_count, 2)

    def test_sequence_ignores_request_and_copies_script(self):
        scripted = response('INSUFFICIENT')
        provider = ScriptedSequenceProvider([scripted, scripted])
        scripted.raw_response['selected_label'] = 'SUFFICIENT'
        first = provider.evaluate(object())
        first.raw_response['selected_label'] = 'CONFLICTING'
        self.assertEqual(provider.evaluate(object()).raw_response['selected_label'], 'INSUFFICIENT')
        self.assertEqual(provider.evaluate_calls, 2)

    def test_request_identity_covers_all_five_fields_and_ignores_key_order(self):
        request = ProviderRequest({'a': 1, 'b': 2}, 'question', MOCK_MODEL)
        original = request_identity_hash(request)
        self.assertEqual(set(provider_visible_content(request)),
                         {'state', 'semantic_question', 'requested_model', 'primitive', 'allowed_labels'})
        self.assertEqual(original, request_identity_hash(replace(request, state={'b': 2, 'a': 1})))
        for field, value in [('state', {'a': 2}), ('semantic_question', 'question '),
                             ('requested_model', 'other'), ('primitive', 'score'),
                             ('allowed_labels', tuple(reversed(LABELS)))]:
            with self.subTest(field=field):
                self.assertNotEqual(original, request_identity_hash(replace(request, **{field: value})))

    def test_request_identity_excludes_non_provider_metadata(self):
        @dataclass(frozen=True)
        class WithMetadata(ProviderRequest):
            logical_decision_id: str = 'one'
            timestamp: str = 'first'
            latency_ms: float = 1.0
            expected_handling_band: str = 'one'
            notes: str = 'one'
            repeat_group: str = 'one'
            audit_path: str = 'one'
        request = WithMetadata({}, 'question', MOCK_MODEL)
        changed = replace(request, logical_decision_id='two', timestamp='second', latency_ms=99,
                          expected_handling_band='two', notes='two', repeat_group='two', audit_path='two')
        self.assertEqual(request_identity_hash(request), request_identity_hash(changed))

    def test_confidence_absent_null_and_numeric_remain_distinct(self):
        group, _ = self.execute(None, 'F-03', [response(confidence=ABSENT), response(confidence=None),
                                              response(confidence=0.8)])
        self.assertEqual(group.summary['confidence_values'], [None, None, 0.8])
        self.assertEqual(group.summary['confidence_statuses'], ['ABSENT', 'NULL', 'VALID'])
        self.assertEqual(group.summary['confidence']['statistics'],
                         {'count': 1, 'min': 0.8, 'max': 0.8, 'range': 0, 'mean': 0.8})
        self.assertEqual(group.summary['threshold_crossings'], [])

    def test_analysis_crossing_equality_and_missing_adjacency(self):
        observations = analysis_only_crossings('confidence', [0.69, 0.70, 0.71, None, 0.60, 0.80, 0.70, 0.69], 0.70)
        self.assertEqual([item['run_indices'] for item in observations], [[1, 2], [5, 6], [7, 8]])
        self.assertEqual([item['direction'] for item in observations], ['UP', 'UP', 'DOWN'])

    def test_invalid_analysis_profiles_and_repeat_counts_are_rejected(self):
        provider = ScriptedSequenceProvider([response()])
        for count in [0, -1, True, 1.5, '2', MAX_REPEAT_COUNT + 1]:
            with self.subTest(count=count), self.assertRaises(ValueError):
                run_repeatability('F-01', count, provider, writer=self.writer)
        for value in [-0.1, 1.1, True, '0.7', float('nan'), float('inf')]:
            for field in ['confidence_threshold', 'selected_label_probability_threshold']:
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    AnalysisOnlyProfile(**{field: value})
        self.assertEqual(provider.evaluate_calls, 0)
        self.assertEqual(list(self.directory.iterdir()), [])

    def test_sequence_exhaustion_invalidates_group_without_retry(self):
        group, provider = self.execute(None, 'F-03', [response()], repeat_count=2)
        self.assertEqual(provider.consumed_count, 1)
        self.assertEqual(provider.evaluate_calls, 2)
        self.assertEqual(group.summary['repeat_group_validity'], 'INVALID')
        self.assertEqual(group.summary['component_outcome_sequence'],
                         [Outcome.SEMANTIC_CHECK_HOLD, Outcome.INVALID_RESULT])
        self.assertEqual(group.decisions[1].record['evidence']['error_class'], 'SequenceExhaustedError')
        self.assertEqual(group.summary['attempt_counts'], [1, 1])

    def test_decision_persistence_failure_aborts_group_and_preserves_prior_record(self):
        provider = ScriptedSequenceProvider([response('SUFFICIENT')] * 3)
        import src.audit as audit_module
        real_replace = audit_module.os.replace
        calls = 0
        def replace_file(source, destination):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError('J5 simulated second-decision persistence failure')
            return real_replace(source, destination)
        completed = None
        with patch('src.audit.os.replace', side_effect=replace_file):
            with self.assertRaises(EvidencePersistenceError):
                completed = run_repeatability('F-01', 3, provider, writer=self.writer)
        self.assertIsNone(completed)
        self.assertEqual(provider.evaluate_calls, 2)
        records = [json.loads(path.read_text(encoding='utf-8')) for path in self.directory.glob('*.json')]
        self.assertEqual(len(records), 1)
        self.assertNotIn('record_type', records[0])
        self.assertEqual(records[0]['evidence']['repeatability']['run_index'], 1)
        self.finding('EVIDENCE_PARTIAL_COMMIT_FINDINGS', len(list(self.directory.glob('.pending-*'))))

    def test_group_summary_persistence_failure_preserves_all_decisions(self):
        provider = ScriptedSequenceProvider([response()] * 2)
        import src.audit as audit_module
        real_replace = audit_module.os.replace
        def replace_file(source, destination):
            staged = json.loads(Path(source).read_text(encoding='utf-8'))
            if staged.get('record_type') == 'repeatability_group':
                raise OSError('J5 simulated group-summary persistence failure')
            return real_replace(source, destination)
        completed = None
        with patch('src.audit.os.replace', side_effect=replace_file):
            with self.assertRaises(EvidencePersistenceError):
                completed = run_repeatability('F-03', 2, provider, writer=self.writer)
        self.assertIsNone(completed)
        self.assertEqual(provider.evaluate_calls, 2)
        records = [json.loads(path.read_text(encoding='utf-8')) for path in self.directory.glob('*.json')]
        self.assertEqual(len(records), 2)
        self.assertTrue(all('record_type' not in record for record in records))
        self.assertEqual({record['evidence']['repeatability']['run_index'] for record in records}, {1, 2})
        self.finding('EVIDENCE_PARTIAL_COMMIT_FINDINGS', len(list(self.directory.glob('.pending-*'))))

    def test_output_clock_ids_latency_and_paths_do_not_invalidate_input_identity(self):
        group, _ = self.execute(None, 'F-03', [response()] * 2)
        records = deepcopy([decision.record for decision in group.decisions])
        records[1]['timestamp'] = '2099-01-01T00:00:00+00:00'
        records[1]['logical_decision_id'] = '00000000-0000-4000-8000-000000000001'
        records[1]['provider']['latency_ms'] = 999999
        records[1]['audit_path'] = 'ignored-local-path'
        summary = summarize_repeat_group(records)
        self.assertEqual(summary['repeat_group_validity'], 'VALID')
        self.assertEqual(summary['request_identity_hash'], group.summary['request_identity_hash'])
        self.assertEqual(summary['labels'], group.summary['labels'])

    def test_policy_drift_invalidates_group_without_stability_statistics(self):
        group, _ = self.execute(None, 'F-03', [response()] * 2)
        records = deepcopy([decision.record for decision in group.decisions])
        records[1]['input']['policy_profile_id'] = 'intentional-policy-drift'
        summary = summarize_repeat_group(records)
        self.assertEqual(summary['repeat_group_validity'], 'INVALID')
        self.assertIn('INPUT_OR_POLICY_DRIFT', summary['invalidation_reasons'])
        self.assert_no_stability_statistics(summary)


if __name__ == '__main__':
    unittest.main()
