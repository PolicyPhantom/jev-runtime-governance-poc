"""JF-01..JF-20: bounded offline failures through the accepted J3 harness."""

from datetime import datetime
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from uuid import UUID, uuid4

from src.audit import AuditWriter, EVIDENCE_ROOT, EvidencePersistenceError
from src.failure_provider import (
    FailureProvider, SimulatedConnectionError, SimulatedHTTPError, SimulatedTimeoutError,
)
from src.fixtures import content_hash, load_fixture
from src.harness import CompletedDecision, run
from src.models import MOCK_MODEL, Outcome, PROJECT_ROOT
from src.providers import MockProvider, ProviderResponse, mock_choice


class J4AuditWriter(AuditWriter):
    """Test-only provenance, added after the gate without changing its decision."""

    def __init__(self, directory: Path, case: str, variant: str):
        super().__init__(directory)
        self.injection = {'simulated': True, 'case_id': case, 'variant': variant}

    def write(self, record: dict) -> Path:
        record['evidence']['j4_injection'] = dict(self.injection)
        return super().write(record)


class J4FailureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.observations: list[dict] = []

    @classmethod
    def tearDownClass(cls):
        observations = cls.observations
        summary = {
            'scope': 'offline frozen JF-01..JF-20 only',
            'covered_cases': sorted({row['case'] for row in observations}),
            'injected_runs': len(observations),
            'FAIL_OPEN_COUNT': sum(row['completed_pass'] for row in observations),
            'ALLOW_RECORD_COUNT': sum(row['allow_record'] for row in observations),
            'RETRY_COUNT_BEYOND_FIRST': sum(row['retries'] for row in observations),
            'DETERMINISTIC_BYPASS_PROVIDER_CALLS': sum(row['bypass_calls'] for row in observations),
            'EVIDENCE_PARTIAL_COMMIT_FINDINGS': sum(row['partial_commits'] for row in observations),
            'PERSISTENCE_FAILURE_COMPLETED_DECISIONS': sum(row['persistence_completed'] for row in observations),
        }
        print('J4_SUMMARY ' + json.dumps(summary, sort_keys=True))
        if summary['covered_cases'] != [f'JF-{number:02d}' for number in range(1, 21)]:
            raise AssertionError('The frozen twenty-case J4 set was not fully exercised')
        for field, value in summary.items():
            if field.isupper() and value != 0:
                raise AssertionError(f'{field} = {value}; stop for human review')

    def setUp(self):
        self.assertEqual(EVIDENCE_ROOT.resolve(), EVIDENCE_ROOT)
        EVIDENCE_ROOT.mkdir(exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(prefix='j4-tests-', dir=EVIDENCE_ROOT)
        self.directory = Path(self.temporary.name).resolve()
        self.assertTrue(self.directory.is_relative_to(EVIDENCE_ROOT))
        self.addCleanup(self.temporary.cleanup)
        self.writer = AuditWriter(self.directory)

    def observe(self, case, variant, record, *, completed=None, calls=0,
                bypass=False, partial_commits=0, persistence_failure=False):
        outcome = record['component_gate']['component_outcome']
        observation = {
            'case': case, 'variant': variant,
            # A computed candidate is not completed until required persistence succeeds.
            'completed_pass': int(isinstance(completed, CompletedDecision)
                                  and outcome == Outcome.SEMANTIC_CHECK_PASS),
            'allow_record': int('ALLOW' in json.dumps(record)),
            'retries': max(calls - 1, 0) + max(record['provider']['attempt_count'] - 1, 0),
            'bypass_calls': calls if bypass else 0,
            'partial_commits': partial_commits,
            'persistence_completed': int(persistence_failure and isinstance(completed, CompletedDecision)),
        }
        self.observations.append(observation)
        for field in ['completed_pass', 'allow_record', 'retries', 'bypass_calls',
                      'partial_commits', 'persistence_completed']:
            self.assertEqual(observation[field], 0, f'{case}/{variant}: {field}')
        self.assertEqual(record['request']['retry_policy'], {'enabled': False, 'max_attempts': 1})
        self.assertLessEqual(record['provider']['attempt_count'], 1)
        self.assertEqual(record['evidence']['j4_injection'], {
            'simulated': True, 'case_id': case, 'variant': variant,
        })

    def exercise(self, case, variant, provider, *, fixture_id='F-01',
                 outcome=Outcome.INVALID_RESULT, transport='OK'):
        completed = run(load_fixture(fixture_id), provider,
                        writer=J4AuditWriter(self.directory, case, variant))
        record = completed.record
        bypass = case == 'JF-20'
        self.observe(case, variant, record, completed=completed,
                     calls=provider.evaluate_calls, bypass=bypass)
        self.assertEqual(provider.evaluate_calls, 0 if bypass else 1)
        self.assertEqual(record['provider']['attempt_count'], provider.evaluate_calls)
        self.assertEqual(record['provider']['transport_status'], transport)
        self.assertEqual(record['component_gate']['component_outcome'], outcome)
        self.assertIsNone(record['component_gate']['semantic_signal'])
        self.assertEqual(record['request']['requested_model'], MOCK_MODEL)
        self.assertEqual(str(UUID(record['logical_decision_id'])), record['logical_decision_id'])
        self.assertIsNotNone(datetime.fromisoformat(record['timestamp']).utcoffset())
        self.assertEqual(record['fixture']['fixture_hash'], content_hash(load_fixture(fixture_id)))
        for field in ['state_hash', 'question_hash']:
            self.assertEqual(len(record['input'][field]), 64)
        self.assertEqual(json.loads(completed.evidence_path.read_text(encoding='utf-8')), record)
        self.assertEqual(list(self.directory.glob('.pending-*')), [])
        if not bypass:
            self.assertGreaterEqual(record['provider']['latency_ms'], 0)
            self.assertIsNotNone(record['evidence']['error_class'])
            self.assertIsNotNone(record['evidence']['error_detail'])
        return record

    def contract_failure(self, case, variant, raw, *, resolved_model=MOCK_MODEL):
        provider = FailureProvider(ProviderResponse(raw, resolved_model))
        record = self.exercise(case, variant, provider)
        self.assertEqual(record['provider']['resolved_model'], resolved_model)
        self.assertEqual(record['component_gate']['rationale_code'], 'CONTRACT_INVALID')
        try:
            expected_hash = content_hash(raw)
        except (TypeError, ValueError):
            expected_hash = None
        self.assertEqual(record['evidence']['raw_response_hash'], expected_hash)
        return record

    def http_failure(self, case, status):
        record = self.exercise(case, str(status), FailureProvider(error=SimulatedHTTPError(status)),
                               transport='ERROR')
        self.assertEqual(record['evidence']['error_class'], 'SimulatedHTTPError')
        metadata = json.loads(record['evidence']['error_detail'])
        self.assertEqual(metadata, {
            'simulated': True, 'failure_kind': 'http_status', 'http_status': status,
            'provider_exception_class': 'SimulatedHTTPError',
        })

    def test_jf_01_provider_exception(self):
        record = self.exercise('JF-01', 'generic',
                               FailureProvider(error=RuntimeError('JF-01 simulated provider exception')),
                               transport='ERROR')
        self.assertEqual(record['evidence']['error_class'], 'RuntimeError')

    def test_jf_02_connection_like_failure(self):
        record = self.exercise('JF-02', 'connection',
                               FailureProvider(error=SimulatedConnectionError('JF-02 offline connection simulation')),
                               transport='ERROR')
        self.assertEqual(record['evidence']['error_class'], 'SimulatedConnectionError')

    def test_jf_03_timeout_like_failure(self):
        record = self.exercise('JF-03', 'timeout',
                               FailureProvider(error=SimulatedTimeoutError('JF-03 offline timeout simulation')),
                               transport='ERROR')
        self.assertEqual(record['evidence']['error_class'], 'SimulatedTimeoutError')

    def test_jf_04_http_408(self):
        self.http_failure('JF-04', 408)

    def test_jf_05_http_429(self):
        self.http_failure('JF-05', 429)

    def test_jf_06_http_500_and_503(self):
        for status in [500, 503]:
            with self.subTest(status=status):
                self.http_failure('JF-06', status)

    def test_jf_07_non_provider_response(self):
        for variant, value in [('none', None), ('dict', {}), ('string', 'invalid response')]:
            with self.subTest(variant=variant):
                record = self.exercise('JF-07', variant, FailureProvider(value), transport='ERROR')
                self.assertEqual(record['evidence']['error_class'], 'TypeError')

    def test_jf_08_missing_selected_label(self):
        raw = mock_choice('SUFFICIENT')
        del raw['selected_label']
        record = self.contract_failure('JF-08', 'absent', raw)
        self.assertEqual(record['validation']['allowed_label_status'], 'INVALID')

    def test_jf_09_unknown_selected_label(self):
        # The spec lists examples; these exercise unknown and incorrectly cased labels.
        # J3 separately retains its existing test of the literal permission label.
        for label in ['APPROVE', 'sufficient']:
            with self.subTest(label=label):
                record = self.contract_failure('JF-09', label,
                                               {**mock_choice('SUFFICIENT'), 'selected_label': label})
                self.assertEqual(record['validation']['allowed_label_status'], 'INVALID')

    def test_jf_10_wrong_primitive(self):
        for primitive in ['text', 'score']:
            with self.subTest(primitive=primitive):
                record = self.contract_failure('JF-10', primitive,
                                               {**mock_choice('SUFFICIENT'), 'primitive': primitive})
                self.assertEqual(record['validation']['schema_status'], 'INVALID')

    def test_jf_11_missing_probabilities(self):
        raw = mock_choice('SUFFICIENT')
        del raw['probabilities']
        record = self.contract_failure('JF-11', 'absent', raw)
        self.assertEqual(record['validation']['probability_status'], 'INVALID')

    def test_jf_12_malformed_probabilities(self):
        probabilities = mock_choice('SUFFICIENT')['probabilities']
        variants = {
            'wrong_container': [1, 0, 0, 0],
            'missing_labels': {'SUFFICIENT': 1},
            'extra_labels': {**probabilities, 'EXTRA': 0},
            'negative': {**probabilities, 'INSUFFICIENT': -0.1},
            'greater_than_one': {**probabilities, 'SUFFICIENT': 1.1},
            'bool': {**probabilities, 'SUFFICIENT': True},
            'string': {**probabilities, 'SUFFICIENT': '1'},
            'nan': {**probabilities, 'SUFFICIENT': float('nan')},
            'infinity': {**probabilities, 'SUFFICIENT': float('inf')},
            'sum_not_one': {**probabilities, 'SUFFICIENT': 0.5},
        }
        for variant, values in variants.items():
            with self.subTest(variant=variant):
                record = self.contract_failure('JF-12', variant,
                                               {**mock_choice('SUFFICIENT'), 'probabilities': values})
                self.assertEqual(record['validation']['probability_status'], 'INVALID')

    def test_jf_13_invalid_confidence(self):
        variants = {'negative': -0.1, 'greater_than_one': 1.1, 'bool': True,
                    'string': 'high', 'nan': float('nan'), 'infinity': float('inf')}
        for variant, confidence in variants.items():
            with self.subTest(variant=variant):
                record = self.contract_failure('JF-13', variant,
                                               {**mock_choice('SUFFICIENT'), 'confidence': confidence})
                self.assertEqual(record['validation']['confidence_status'], 'INVALID')

    def test_jf_14_missing_resolved_model(self):
        for variant, model in [('none', None), ('empty', '')]:
            with self.subTest(variant=variant):
                record = self.contract_failure('JF-14', variant, mock_choice('SUFFICIENT'),
                                               resolved_model=model)
                self.assertEqual(record['validation']['model_identity_status'], 'MISSING')

    def test_jf_15_resolved_model_mismatch(self):
        record = self.contract_failure('JF-15', 'mismatch', mock_choice('SUFFICIENT'),
                                       resolved_model='simulated-other-model')
        self.assertEqual(record['validation']['model_identity_status'], 'MISMATCH')
        self.assertNotEqual(record['request']['requested_model'], record['provider']['resolved_model'])

    def test_jf_16_non_canonicalizable_raw_response(self):
        raw = {**mock_choice('SUFFICIENT'), 'opaque_simulated_field': {1, 2}}
        record = self.contract_failure('JF-16', 'set', raw)
        self.assertIsNone(record['evidence']['raw_response_hash'])
        self.assertEqual(record['validation']['schema_status'], 'INVALID')
        self.assertEqual(record['evidence']['error_class'], 'TypeError')

    def persistence_failure(self, case, variant, writer, decision_id, *, existing=None):
        writer = J4AuditWriter(writer.directory, case, variant)
        provider = MockProvider(mock_choice('SUFFICIENT'))
        completed = None
        error = None
        record = None
        with patch('src.harness.uuid4', return_value=decision_id), \
             patch.object(provider, 'evaluate', wraps=provider.evaluate) as evaluate, \
             patch.object(writer, 'write', wraps=writer.write) as write:
            try:
                completed = run(load_fixture('F-01'), provider, writer=writer)
            except EvidencePersistenceError as caught:
                error = caught
            if write.called:
                record = write.call_args.args[0]
        self.assertIsNotNone(record, 'The persistence boundary must actually be reached')
        # A sufficient candidate exercises the dangerous path; no completed result
        # or newly committed record may escape when the write fails.
        self.assertEqual(record['component_gate']['component_outcome'], Outcome.SEMANTIC_CHECK_PASS)
        existing = existing or {}
        current = {path.name: path.read_bytes() for path in self.directory.glob('*.json')}
        findings = sum(current.get(name) != data for name, data in existing.items())
        findings += len(set(current) - set(existing))
        self.observe(case, variant, record, completed=completed, calls=evaluate.call_count,
                     partial_commits=findings, persistence_failure=True)
        self.assertIsNone(completed)
        self.assertIsInstance(error, EvidencePersistenceError)
        self.assertIn('NOT COMMITTABLE', str(error))
        self.assertEqual(current, existing)
        self.assertEqual(list(self.directory.glob('.pending-*')), [])
        self.assertEqual(evaluate.call_count, 1)
        self.assertEqual(record['provider']['attempt_count'], 1)
        return error

    def test_jf_17_evidence_replace_failure(self):
        decision_id = uuid4()
        def fail_replace(source, destination):
            pending = Path(source)
            self.assertEqual(pending.suffix, '.tmp')
            self.assertFalse(Path(destination).exists())
            self.assertEqual(json.loads(pending.read_text(encoding='utf-8'))['logical_decision_id'],
                             str(decision_id))
            raise OSError('JF-17 simulated atomic replace failure')
        with patch('src.audit.os.replace', side_effect=fail_replace) as replace_file:
            error = self.persistence_failure('JF-17', 'replace', self.writer, decision_id)
        replace_file.assert_called_once()
        self.assertIsInstance(error.__cause__, OSError)
        self.assertEqual(str(error.__cause__), 'JF-17 simulated atomic replace failure')

    def test_jf_18_evidence_target_outside_root(self):
        # Use a known, existing repository directory; the writer must reject it
        # before opening a temporary file or attempting any committed write.
        target = PROJECT_ROOT / 'tests'
        before = set(target.iterdir())
        with patch('src.audit.tempfile.NamedTemporaryFile',
                   side_effect=AssertionError('must not open outside evidence')) as open_temp, \
             patch('src.audit.os.replace',
                   side_effect=AssertionError('must not commit outside evidence')) as replace_file:
            self.persistence_failure('JF-18', 'outside_root', AuditWriter(target), uuid4())
        open_temp.assert_not_called()
        replace_file.assert_not_called()
        self.assertEqual(set(target.iterdir()), before)

    def test_jf_19_existing_audit_record_collision(self):
        original = run(load_fixture('F-01'), MockProvider(mock_choice('INSUFFICIENT')), writer=self.writer)
        original_bytes = original.evidence_path.read_bytes()
        existing = {original.evidence_path.name: original_bytes}
        with patch('src.audit.tempfile.NamedTemporaryFile',
                   side_effect=AssertionError('collision must be rejected before staging')) as open_temp:
            self.persistence_failure('JF-19', 'collision', self.writer,
                                     UUID(original.record['logical_decision_id']), existing=existing)
        open_temp.assert_not_called()
        self.assertEqual(original.evidence_path.read_bytes(), original_bytes)

    def test_jf_20_deterministic_bypass_with_failing_provider(self):
        expected = {'F-05': Outcome.DETERMINISTIC_DENY, 'F-06': Outcome.NOT_EVALUATED,
                    'F-08': Outcome.SEMANTIC_CHECK_HOLD}
        for fixture_id, outcome in expected.items():
            with self.subTest(fixture=fixture_id):
                provider = FailureProvider(error=RuntimeError('JF-20 provider must never be called'))
                record = self.exercise('JF-20', fixture_id, provider, fixture_id=fixture_id,
                                       outcome=outcome, transport='NOT_CALLED')
                self.assertEqual(record['precheck']['result'], outcome)
                self.assertEqual(record['component_gate']['rationale_code'], record['precheck']['rationale_code'])
                self.assertIsNone(record['evidence']['error_class'])
                self.assertEqual(set(record['validation'].values()), {'NOT_EVALUATED'})


if __name__ == '__main__':
    unittest.main()
