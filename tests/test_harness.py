"""Offline checks of the J3 boundaries and complete persisted audit path."""

from copy import deepcopy
from dataclasses import asdict, replace
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from src.audit import AuditWriter, EVIDENCE_ROOT, EvidencePersistenceError
from src.contracts import validate
from src.fixtures import canonical_json, content_hash, load_catalog, load_fixture
from src.gate import decide
from src.harness import run
from src.models import LABELS, MOCK_MODEL, Outcome, PROJECT_ROOT
from src.precheck import REQUIRED_FIELDS, check
from src.providers import MockProvider, mock_choice


class FixtureTests(unittest.TestCase):
    def test_catalog_has_exactly_eight_versioned_fixtures(self):
        catalog = load_catalog()
        self.assertEqual(set(catalog['fixtures']), {f'F-{index:02d}' for index in range(1, 9)})
        for fixture_id, entry in catalog['fixtures'].items():
            with self.subTest(fixture=fixture_id):
                fixture = load_fixture(fixture_id)
                self.assertEqual(set(fixture), set(REQUIRED_FIELDS))
                self.assertEqual(fixture['fixture_id'], fixture_id)
                self.assertEqual(fixture['version'], entry['version'])
                self.assertEqual(content_hash(fixture), entry['fixture_hash'])

    def test_baseline_bytes_match_recorded_entry_hash(self):
        catalog = load_catalog()
        self.assertEqual(hashlib.sha256((PROJECT_ROOT / catalog['baseline']).read_bytes()).hexdigest(),
                         'b19ae8f6fefe88d9e5155a16a21c8e095bbbb1949dd013a9ed052a344dbc6df9')
        self.assertEqual(catalog['baseline_sha256'],
                         'b19ae8f6fefe88d9e5155a16a21c8e095bbbb1949dd013a9ed052a344dbc6df9')

    def test_repeat_groups_and_serialized_inputs_are_preserved(self):
        expected = {'F-01': 'R1', 'F-03': 'R2', 'F-04': 'R3', 'F-07': 'R4'}
        for fixture_id in load_catalog()['fixtures']:
            fixture = load_fixture(fixture_id)
            self.assertEqual(fixture['repeat_group'], expected.get(fixture_id))
            self.assertEqual(content_hash(fixture), content_hash(load_fixture(fixture_id)))

    def test_unknown_fixture_id_is_rejected(self):
        with self.assertRaises(ValueError):
            load_fixture('../F-01')

    def test_semantic_and_deterministic_fixture_partition(self):
        results = {fixture_id: check(load_fixture(fixture_id)).result
                   for fixture_id in load_catalog()['fixtures']}
        self.assertEqual({key for key, value in results.items() if value == 'PASS'},
                         {'F-01', 'F-02', 'F-03', 'F-04', 'F-07'})
        self.assertEqual({key: value for key, value in results.items() if value != 'PASS'}, {
            'F-05': Outcome.DETERMINISTIC_DENY,
            'F-06': Outcome.NOT_EVALUATED,
            'F-08': Outcome.SEMANTIC_CHECK_HOLD,
        })


class PrecheckTests(unittest.TestCase):
    def test_fixture_version_id_and_content_changes_are_rejected(self):
        for key, value in [('version', 'v0.2'), ('fixture_id', 'F-99'),
                           ('semantic_question', 'Authorize execution now')]:
            with self.subTest(field=key):
                fixture = load_fixture('F-01')
                fixture[key] = value
                self.assertEqual(check(fixture).result, Outcome.NOT_EVALUATED)
                self.assertFalse(check(fixture).fixture_identity_valid)

    def test_structural_fields_and_prerequisites_fail_without_model(self):
        # Isolate prerequisites from the independent frozen-content check.
        cases = [('schema_valid', False), ('required_fields_present', False),
                 ('identity_binding_valid', False), ('identity_binding_valid', 'unresolved'),
                 ('integrity_valid', False), ('prohibited', 'false')]
        for key, value in cases:
            with self.subTest(flag=key, value=value):
                fixture = load_fixture('F-01')
                fixture['deterministic_flags'][key] = value
                with patch('src.precheck.fixture_identity_valid', return_value=True):
                    self.assertNotEqual(check(fixture).result, 'PASS')

    def test_missing_fields_and_empty_artifacts_are_not_delegated(self):
        fixture = load_fixture('F-01')
        del fixture['semantic_question']
        self.assertFalse(check(fixture).required_fields_present)
        self.assertEqual(check(fixture).result, Outcome.NOT_EVALUATED)
        fixture = load_fixture('F-01')
        fixture['submitted_evidence'] = []
        with patch('src.precheck.fixture_identity_valid', return_value=True):
            self.assertEqual(check(fixture).result, Outcome.NOT_EVALUATED)

    def test_malformed_fixture_cannot_authorize_prohibition(self):
        fixture = {'deterministic_flags': {'prohibited': True}}
        result = check(fixture)
        self.assertEqual(result.result, Outcome.NOT_EVALUATED)
        self.assertEqual(result.rationale_code, 'MISSING_FIXTURE_FIELDS')
        self.assertTrue(result.prohibited)
        self.assertFalse(result.schema_valid)

    def test_unavailable_catalog_cannot_authorize_prohibition_or_enable_pass(self):
        prohibited = load_fixture('F-05')
        positive = load_fixture('F-01')
        with patch('src.fixtures.load_catalog', side_effect=ValueError('invalid local catalog')):
            self.assertEqual(check(prohibited).result, Outcome.NOT_EVALUATED)
            self.assertEqual(check(positive).result, Outcome.NOT_EVALUATED)

    def test_non_object_fixture_does_not_pass_schema(self):
        self.assertEqual(check([]).result, Outcome.NOT_EVALUATED)


class ContractTests(unittest.TestCase):
    def test_all_labels_have_valid_contracts(self):
        for label in LABELS:
            self.assertTrue(validate(mock_choice(label), MOCK_MODEL, MOCK_MODEL)[0].valid)

    def test_unknown_or_missing_label_is_invalid(self):
        for value in ['ALLOW', 'sufficient', '', None, ['SUFFICIENT']]:
            raw = mock_choice('SUFFICIENT')
            raw['selected_label'] = value
            self.assertFalse(validate(raw, MOCK_MODEL, MOCK_MODEL)[0].valid)
        raw.pop('selected_label')
        self.assertFalse(validate(raw, MOCK_MODEL, MOCK_MODEL)[0].valid)

    def test_probability_structure_and_values_are_validated(self):
        base = mock_choice('SUFFICIENT')['probabilities']
        invalid = [None, [1, 0, 0, 0], {}, {'SUFFICIENT': 1.0},
                   {**base, 'ALLOW': 0}, {**base, 'SUFFICIENT': 1.1},
                   {**base, 'INSUFFICIENT': -0.1}, {**base, 'SUFFICIENT': True},
                   {**base, 'SUFFICIENT': '1'}, {**base, 'SUFFICIENT': 0.2},
                   {**base, 'SUFFICIENT': float('nan')},
                   {**base, 'SUFFICIENT': float('inf')},
                   {**base, 'SUFFICIENT': 10 ** 1000}]
        for probabilities in invalid:
            with self.subTest(probabilities=repr(probabilities)[:100]):
                raw = mock_choice('SUFFICIENT')
                raw['probabilities'] = probabilities
                validation, answer = validate(raw, MOCK_MODEL, MOCK_MODEL)
                self.assertFalse(validation.valid)
                self.assertIsNone(answer['probabilities'])

    def test_confidence_absent_null_and_numeric_are_explicit_without_cutoff(self):
        for value, status in [(None, 'NULL'), (0, 'VALID'), (0.01, 'VALID'), (1, 'VALID')]:
            raw = {**mock_choice('SUFFICIENT'), 'confidence': value}
            validation, answer = validate(raw, MOCK_MODEL, MOCK_MODEL)
            self.assertTrue(validation.valid)
            self.assertEqual(validation.confidence_status, status)
            self.assertEqual(answer['confidence_nullable'], value)
        raw.pop('confidence')
        validation, answer = validate(raw, MOCK_MODEL, MOCK_MODEL)
        self.assertTrue(validation.valid)
        self.assertEqual(validation.confidence_status, 'ABSENT')
        self.assertIsNone(answer['confidence_nullable'])

    def test_invalid_confidence_never_validates(self):
        for value in [-0.1, 1.1, True, 'high', {}, float('nan'), float('inf')]:
            validation, _ = validate({**mock_choice('SUFFICIENT'), 'confidence': value},
                                     MOCK_MODEL, MOCK_MODEL)
            self.assertFalse(validation.valid)

    def test_model_identity_is_required_and_must_match(self):
        for resolved in [None, '', 'another-model', 123]:
            self.assertFalse(validate(mock_choice('SUFFICIENT'), MOCK_MODEL, resolved)[0].valid)

    def test_wrong_primitive_and_non_object_results_are_invalid(self):
        for raw in [None, [], 'SUFFICIENT', {'primitive': 'text'},
                    {**mock_choice('SUFFICIENT'), 'primitive': 'text'}]:
            self.assertFalse(validate(raw, MOCK_MODEL, MOCK_MODEL)[0].valid)


class HarnessTests(unittest.TestCase):
    def setUp(self):
        self.assertEqual(EVIDENCE_ROOT.resolve(), EVIDENCE_ROOT)
        EVIDENCE_ROOT.mkdir(exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(prefix='j3-tests-', dir=EVIDENCE_ROOT)
        self.directory = Path(self.temporary.name).resolve()
        self.assertTrue(self.directory.is_relative_to(EVIDENCE_ROOT))
        self.addCleanup(self.temporary.cleanup)
        self.writer = AuditWriter(self.directory)

    def evaluate(self, fixture_id='F-01', label='SUFFICIENT', raw=None, **kwargs):
        provider = MockProvider(mock_choice(label) if raw is None else raw)
        return run(load_fixture(fixture_id), provider, writer=self.writer, **kwargs)

    def test_f01_sufficient_can_pass_and_evidence_is_persisted(self):
        result = self.evaluate()
        self.assertEqual(result.record['component_gate']['component_outcome'], Outcome.SEMANTIC_CHECK_PASS)
        self.assertEqual(result.record['component_gate']['semantic_signal'], 'SUFFICIENT')
        self.assertTrue(result.evidence_path.is_file())
        self.assertEqual(json.loads(result.evidence_path.read_text(encoding='utf-8')), result.record)
        self.assertEqual(list(self.directory.glob('.pending-*')), [])

    def test_semantic_pass_is_never_an_allow_outcome(self):
        record = self.evaluate().record
        self.assertNotIn('ALLOW', {item.value for item in Outcome})
        self.assertNotIn('ALLOW', json.dumps(record))

    def test_all_non_sufficient_labels_hold(self):
        for label in ['INSUFFICIENT', 'CONFLICTING', 'UNCERTAIN']:
            with self.subTest(label=label):
                gate = self.evaluate(label=label).record['component_gate']
                self.assertEqual(gate['component_outcome'], Outcome.SEMANTIC_CHECK_HOLD)
                self.assertEqual(gate['semantic_signal'], label)

    def test_f05_f06_and_f08_need_no_provider_at_all(self):
        for fixture_id, expected in [('F-05', Outcome.DETERMINISTIC_DENY),
                                     ('F-06', Outcome.NOT_EVALUATED),
                                     ('F-08', Outcome.SEMANTIC_CHECK_HOLD)]:
            result = run(load_fixture(fixture_id), None, writer=self.writer)
            self.assertEqual(result.record['component_gate']['component_outcome'], expected)
            self.assertEqual(result.record['provider']['attempt_count'], 0)

    def test_f05_f06_and_f08_never_call_provider(self):
        for fixture_id, expected in [('F-05', Outcome.DETERMINISTIC_DENY),
                                     ('F-06', Outcome.NOT_EVALUATED),
                                     ('F-08', Outcome.SEMANTIC_CHECK_HOLD)]:
            with self.subTest(fixture=fixture_id):
                provider = Mock(wraps=MockProvider(mock_choice('SUFFICIENT')))
                record = run(load_fixture(fixture_id), provider, writer=self.writer).record
                provider.evaluate.assert_not_called()
                self.assertTrue(record['precheck']['schema_valid'])
                self.assertTrue(record['precheck']['fixture_identity_valid'])
                self.assertEqual(record['precheck']['result'], expected)
                self.assertEqual(record['component_gate']['component_outcome'], expected)
                self.assertEqual(record['component_gate']['rationale_code'],
                                 record['precheck']['rationale_code'])
                self.assertIsNone(record['component_gate']['semantic_signal'])
                self.assertEqual(record['provider']['transport_status'], 'NOT_CALLED')
                self.assertEqual(record['provider']['attempt_count'], 0)
                self.assertEqual(record['validation']['schema_status'], 'NOT_EVALUATED')

    def assert_untrusted_prohibition_skips_provider(self, fixture, reason):
        provider = MockProvider(mock_choice('SUFFICIENT'))
        with patch.object(provider, 'evaluate', wraps=provider.evaluate) as evaluate:
            record = run(fixture, provider, writer=self.writer).record
        evaluate.assert_not_called()
        self.assertTrue(record['precheck']['prohibited'])
        self.assertEqual(record['precheck']['result'], Outcome.NOT_EVALUATED)
        self.assertEqual(record['precheck']['rationale_code'], reason)
        self.assertEqual(record['component_gate']['component_outcome'], Outcome.NOT_EVALUATED)
        self.assertEqual(record['component_gate']['rationale_code'], reason)
        self.assertIsNone(record['component_gate']['semantic_signal'])
        self.assertEqual(record['provider']['attempt_count'], 0)
        self.assertEqual(record['provider']['transport_status'], 'NOT_CALLED')

    def test_malformed_prohibited_fixture_is_not_evaluated_without_provider(self):
        malformed = load_fixture('F-05')
        malformed['submitted_evidence'] = 'wrong schema type'
        for fixture, reason in [
            ({'deterministic_flags': {'prohibited': True}}, 'MISSING_FIXTURE_FIELDS'),
            (malformed, 'INVALID_FIXTURE_SCHEMA'),
        ]:
            with self.subTest(reason=reason):
                self.assert_untrusted_prohibition_skips_provider(fixture, reason)

    def test_unverified_prohibited_fixture_is_not_evaluated_without_provider(self):
        for field, value in [('fixture_id', 'F-99'), ('version', 'v0.2'),
                             ('semantic_question', 'Altered frozen content')]:
            with self.subTest(field=field):
                fixture = load_fixture('F-05')
                fixture[field] = value
                self.assert_untrusted_prohibition_skips_provider(
                    fixture, 'FROZEN_FIXTURE_IDENTITY_MISMATCH')

    def test_unavailable_catalog_skips_provider_for_prohibited_fixture(self):
        fixture = load_fixture('F-05')
        for error in [OSError('local catalog unavailable'), ValueError('invalid local catalog')]:
            with self.subTest(error=type(error).__name__):
                with patch('src.fixtures.load_catalog', side_effect=error):
                    self.assert_untrusted_prohibition_skips_provider(
                        fixture, 'FROZEN_FIXTURE_IDENTITY_MISMATCH')

    def assert_semantic_hold_reaches_provider(self, fixture_id, label):
        fixture = load_fixture(fixture_id)
        provider = MockProvider(mock_choice(label))
        with patch.object(provider, 'evaluate', wraps=provider.evaluate) as evaluate:
            record = run(fixture, provider, writer=self.writer).record
        evaluate.assert_called_once()
        self.assertEqual(evaluate.call_args.args[0].state['submitted_evidence'],
                         fixture['submitted_evidence'])
        self.assertEqual(record['precheck']['result'], 'PASS')
        self.assertTrue(record['precheck']['required_fields_present'])
        self.assertIs(record['precheck']['identity_binding_valid'], True)
        self.assertEqual(record['provider']['attempt_count'], 1)
        self.assertEqual(record['provider']['transport_status'], 'OK')
        self.assertEqual(record['validation']['schema_status'], 'VALID')
        self.assertEqual(record['component_gate']['semantic_signal'], label)
        self.assertEqual(record['component_gate']['component_outcome'], Outcome.SEMANTIC_CHECK_HOLD)
        self.assertEqual(record['component_gate']['rationale_code'], 'SEMANTIC_SUPPORT_NOT_SUFFICIENT')

    def test_f02_semantic_insufficiency_reaches_provider_and_holds(self):
        for label in ['INSUFFICIENT', 'UNCERTAIN']:
            with self.subTest(label=label):
                self.assert_semantic_hold_reaches_provider('F-02', label)

    def test_f03_semantic_ambiguity_reaches_provider_and_holds(self):
        for label in ['INSUFFICIENT', 'UNCERTAIN']:
            with self.subTest(label=label):
                self.assert_semantic_hold_reaches_provider('F-03', label)

    def test_f03_r2_reuses_identical_inputs_across_independent_decisions(self):
        provider = MockProvider(mock_choice('UNCERTAIN'))
        fixture = load_fixture('F-03')
        self.assertEqual(fixture['repeat_group'], 'R2')
        with patch.object(provider, 'evaluate', wraps=provider.evaluate) as evaluate:
            first = run(fixture, provider, writer=self.writer).record
            second = run(load_fixture('F-03'), provider, writer=self.writer).record
        self.assertEqual(evaluate.call_count, 2)
        requests = [canonical_json(asdict(call.args[0])) for call in evaluate.call_args_list]
        self.assertEqual(requests[0], requests[1])
        self.assertEqual(first['fixture']['fixture_hash'], second['fixture']['fixture_hash'])
        self.assertEqual(first['input'], second['input'])
        self.assertNotEqual(first['logical_decision_id'], second['logical_decision_id'])
        for record in [first, second]:
            self.assertEqual(record['provider']['attempt_count'], 1)
            self.assertEqual(record['component_gate']['semantic_signal'], 'UNCERTAIN')
            self.assertEqual(record['component_gate']['component_outcome'], Outcome.SEMANTIC_CHECK_HOLD)

    def test_semantic_fixtures_still_enforce_structural_and_governance_prerequisites(self):
        for fixture_id in ['F-02', 'F-03']:
            for failure in ['missing_schema_field', 'absent_artifact', 'required_fields_present',
                            'identity_binding_valid', 'integrity_valid', 'prohibited']:
                with self.subTest(fixture=fixture_id, failure=failure):
                    fixture = load_fixture(fixture_id)
                    if failure == 'missing_schema_field':
                        del fixture['semantic_question']
                    elif failure == 'absent_artifact':
                        fixture['submitted_evidence'] = []
                    else:
                        fixture['deterministic_flags'][failure] = {
                            'identity_binding_valid': 'unresolved', 'prohibited': True,
                        }.get(failure, False)
                    provider = MockProvider(mock_choice('SUFFICIENT'))
                    # Isolate these prerequisites from catalog hash rejection.
                    with patch('src.precheck.fixture_identity_valid', return_value=True), \
                         patch.object(provider, 'evaluate', wraps=provider.evaluate) as evaluate:
                        record = run(fixture, provider, writer=self.writer).record
                    evaluate.assert_not_called()
                    self.assertNotEqual(record['precheck']['result'], 'PASS')
                    self.assertEqual(record['provider']['attempt_count'], 0)
                    self.assertNotEqual(record['component_gate']['component_outcome'],
                                        Outcome.SEMANTIC_CHECK_PASS)

    def test_prohibition_cannot_be_overridden_by_valid_sufficient(self):
        validation, _ = validate(mock_choice('SUFFICIENT'), MOCK_MODEL, MOCK_MODEL)
        precheck = check(load_fixture('F-05'))
        self.assertTrue(validation.valid)
        self.assertEqual(precheck.result, Outcome.DETERMINISTIC_DENY)
        gate = decide(precheck, validation, 'SUFFICIENT', True)
        self.assertEqual(gate.component_outcome, Outcome.DETERMINISTIC_DENY)
        self.assertEqual(gate.rationale_code, precheck.rationale_code)
        self.assertIsNone(gate.semantic_signal)

    def test_gate_preserves_non_pass_decision_without_reinterpreting_prohibition(self):
        validation, _ = validate(mock_choice('SUFFICIENT'), MOCK_MODEL, MOCK_MODEL)
        for outcome in [Outcome.NOT_EVALUATED, Outcome.SEMANTIC_CHECK_HOLD, Outcome.INVALID_RESULT]:
            with self.subTest(outcome=outcome):
                precheck = replace(check(load_fixture('F-05')), result=outcome,
                                   rationale_code='PRECHECK_ALREADY_DECIDED')
                self.assertTrue(precheck.prohibited)
                gate = decide(precheck, validation, 'SUFFICIENT', True)
                self.assertEqual(gate.component_outcome, outcome)
                self.assertEqual(gate.rationale_code, precheck.rationale_code)
                self.assertIsNone(gate.semantic_signal)

    def test_gate_rechecks_all_deterministic_prerequisites(self):
        validation, _ = validate(mock_choice('SUFFICIENT'), MOCK_MODEL, MOCK_MODEL)
        passed = check(load_fixture('F-01'))
        cases = [(field, False) for field in [
            'schema_valid', 'required_fields_present', 'identity_binding_valid',
            'integrity_valid', 'fixture_identity_valid', 'required_evidence_present',
        ]] + [('prohibited', True)]
        for field, value in cases:
            with self.subTest(field=field):
                gate = decide(replace(passed, **{field: value}), validation, 'SUFFICIENT', True)
                self.assertEqual(gate.component_outcome, Outcome.NOT_EVALUATED)
                self.assertEqual(gate.rationale_code, 'DETERMINISTIC_PREREQUISITE_FAILED')

    def test_f04_conflicting_mock_holds(self):
        result = self.evaluate('F-04', 'CONFLICTING')
        self.assertEqual(result.record['component_gate']['component_outcome'], Outcome.SEMANTIC_CHECK_HOLD)

    def test_f07_embedded_instructions_do_not_rewrite_mock_answer(self):
        result = self.evaluate('F-07', 'INSUFFICIENT')
        self.assertEqual(result.record['answer']['selected_label'], 'INSUFFICIENT')
        self.assertEqual(result.record['component_gate']['component_outcome'], Outcome.SEMANTIC_CHECK_HOLD)

    def test_expected_bands_and_notes_are_not_sent_as_semantic_authority(self):
        provider = MockProvider(mock_choice('SUFFICIENT'))
        with patch.object(provider, 'evaluate', wraps=provider.evaluate) as evaluate:
            self.assertEqual(run(load_fixture('F-01'), provider, writer=self.writer)
                             .record['component_gate']['component_outcome'], Outcome.SEMANTIC_CHECK_PASS)
        evaluate.assert_called_once()
        request = evaluate.call_args.args[0]
        self.assertEqual(set(request.state), {'suspension_cause', 'required_evidence', 'submitted_evidence'})
        self.assertEqual(request.allowed_labels, LABELS)

    def test_unknown_label_and_malformed_probabilities_cannot_pass(self):
        for raw in [{**mock_choice('SUFFICIENT'), 'selected_label': 'ALLOW'},
                    {**mock_choice('SUFFICIENT'), 'probabilities': [1, 0, 0, 0]}]:
            record = self.evaluate(raw=raw).record
            self.assertEqual(record['component_gate']['component_outcome'], Outcome.INVALID_RESULT)
            self.assertIsNone(record['component_gate']['semantic_signal'])
            self.assertEqual(record['evidence']['error_class'], 'ContractInvalid')

    def test_unencodable_response_is_invalid_and_auditable(self):
        raw = {**mock_choice('SUFFICIENT'), 'confidence': float('nan')}
        record = self.evaluate(raw=raw).record
        self.assertEqual(record['component_gate']['component_outcome'], Outcome.INVALID_RESULT)
        self.assertIsNone(record['evidence']['raw_response_hash'])
        self.assertEqual(record['evidence']['error_class'], 'ValueError')
        self.assertEqual(record['provider']['transport_status'], 'OK')
        self.assertEqual(record['validation']['schema_status'], 'INVALID')
        self.assertEqual(record['validation']['confidence_status'], 'INVALID')

    def test_model_mismatch_cannot_pass_and_both_identities_are_audited(self):
        provider = MockProvider(mock_choice('SUFFICIENT'), 'different-mock')
        record = run(load_fixture('F-01'), provider, writer=self.writer).record
        self.assertEqual(record['component_gate']['component_outcome'], Outcome.INVALID_RESULT)
        self.assertEqual(record['request']['requested_model'], MOCK_MODEL)
        self.assertEqual(record['provider']['resolved_model'], 'different-mock')

    def test_low_confidence_does_not_create_a_production_threshold(self):
        raw = {**mock_choice('SUFFICIENT'), 'confidence': 0.001}
        self.assertEqual(self.evaluate(raw=raw).record['component_gate']['component_outcome'],
                         Outcome.SEMANTIC_CHECK_PASS)

    def test_missing_provider_is_explicitly_invalid_without_attempt(self):
        record = run(load_fixture('F-01'), None, writer=self.writer).record
        self.assertEqual(record['component_gate']['component_outcome'], Outcome.INVALID_RESULT)
        self.assertEqual(record['provider']['attempt_count'], 0)
        self.assertEqual(record['provider']['transport_status'], 'UNAVAILABLE')

    def test_audit_contains_complete_frozen_envelope(self):
        record = self.evaluate().record
        self.assertEqual(set(record), {'logical_decision_id', 'timestamp', 'fixture', 'input',
                                      'precheck', 'request', 'provider', 'answer', 'validation',
                                      'component_gate', 'evidence'})
        expected = {
            'fixture': {'fixture_id', 'fixture_version', 'fixture_hash'},
            'input': {'state_hash', 'question_hash', 'policy_profile_id'},
            'precheck': {'schema_valid', 'required_fields_present', 'identity_binding_valid',
                         'integrity_valid', 'prohibited', 'result'},
            'request': {'primitive', 'requested_model', 'sdk_name', 'sdk_version', 'retry_policy', 'timeout'},
            'provider': {'transport_status', 'resolved_model', 'attempt_count', 'latency_ms'},
            'answer': {'selected_label', 'probabilities', 'confidence_nullable'},
            'validation': {'schema_status', 'allowed_label_status', 'probability_status',
                           'confidence_status', 'model_identity_status'},
            'component_gate': {'semantic_signal', 'component_outcome', 'rationale_code'},
            'evidence': {'raw_response_hash', 'error_class', 'error_detail'},
        }
        for key, fields in expected.items():
            self.assertTrue(fields.issubset(record[key]), key)
        self.assertEqual(record['request']['requested_model'], MOCK_MODEL)
        self.assertEqual(record['provider']['resolved_model'], MOCK_MODEL)
        self.assertEqual(record['evidence']['raw_response_hash'], content_hash(mock_choice('SUFFICIENT')))
        self.assertGreaterEqual(record['provider']['latency_ms'], 0)

    def test_retry_off_and_exactly_one_attempt(self):
        provider = MockProvider(mock_choice('SUFFICIENT'))
        with patch.object(provider, 'evaluate', wraps=provider.evaluate) as evaluate:
            record = run(load_fixture('F-01'), provider, writer=self.writer).record
        evaluate.assert_called_once()
        self.assertEqual(record['request']['retry_policy'], {'enabled': False, 'max_attempts': 1})
        self.assertEqual(record['provider']['attempt_count'], 1)

    def test_timestamp_has_explicit_timezone_offset(self):
        timestamp = self.evaluate().record['timestamp']
        self.assertTrue(timestamp.endswith('+00:00'))
        self.assertEqual(datetime.fromisoformat(timestamp).utcoffset(), timedelta(0))

    def test_fixture_input_is_not_mutated(self):
        fixture = load_fixture('F-01')
        before = deepcopy(fixture)
        run(fixture, MockProvider(mock_choice('SUFFICIENT')), writer=self.writer)
        self.assertEqual(fixture, before)

    def test_persistence_failure_does_not_return_success_or_commit_partial_json(self):
        # One unit check of J3's persistence invariant, not a failure campaign.
        with patch('src.audit.os.replace', side_effect=OSError('local test write failure')):
            with self.assertRaisesRegex(EvidencePersistenceError, 'NOT COMMITTABLE'):
                self.evaluate()
        self.assertEqual(list(self.directory.iterdir()), [])

    def test_writer_rejects_paths_outside_local_evidence_before_writing(self):
        with self.assertRaisesRegex(EvidencePersistenceError, 'local evidence/'):
            run(load_fixture('F-01'), MockProvider(mock_choice('SUFFICIENT')),
                writer=AuditWriter(PROJECT_ROOT / 'tests'))

    def test_existing_audit_record_is_not_overwritten(self):
        result = self.evaluate()
        original = result.evidence_path.read_bytes()
        with self.assertRaises(EvidencePersistenceError):
            self.writer.write(result.record)
        self.assertEqual(result.evidence_path.read_bytes(), original)


if __name__ == '__main__':
    unittest.main()
