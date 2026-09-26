"""Offline regressions for the authorized J5-IR-01/02 corrections."""

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.audit import AuditWriter, EVIDENCE_ROOT, EvidencePersistenceError
from src.contracts import Validation, validate
from src.fixtures import content_hash, load_fixture
from src.gate import decide
from src.harness import run
from src.models import LABELS, MOCK_MODEL, Outcome
from src.providers import ProviderResponse, mock_choice
from src.repeatability import run_repeatability
from src.repeatability_analysis import AnalysisOnlyProfile, summarize_repeat_group


class UnsafeProvider:
    """Return the supplied object directly, with no protective provider copy."""

    sdk_name = 'offline-unsafe-test-provider'
    sdk_version = 'j5-corrections-v0.1'

    def __init__(self, raw):
        self.raw = raw
        self.evaluate_calls = 0

    def evaluate(self, request):
        self.evaluate_calls += 1
        return ProviderResponse(self.raw, MOCK_MODEL)


class ReusingProbabilityProvider(UnsafeProvider):
    """Deliberately mutate the same probability dictionary across calls."""

    def __init__(self):
        super().__init__(mock_choice('SUFFICIENT'))

    def evaluate(self, request):
        probability = (0.60, 0.80)[self.evaluate_calls]
        self.raw['probabilities'].update({
            label: probability if label == 'SUFFICIENT' else (1 - probability) / 3
            for label in LABELS
        })
        return super().evaluate(request)


class ExplodingMetadata(dict):
    def items(self):
        raise RuntimeError('J5-IR-01 metadata canonicalization failed')


class J5CorrectionTests(unittest.TestCase):
    def setUp(self):
        self.assertEqual(EVIDENCE_ROOT.resolve(), EVIDENCE_ROOT)
        EVIDENCE_ROOT.mkdir(exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(prefix='j5-corrections-', dir=EVIDENCE_ROOT)
        self.directory = Path(self.temporary.name).resolve()
        self.assertTrue(self.directory.is_relative_to(EVIDENCE_ROOT))
        self.addCleanup(self.temporary.cleanup)
        self.writer = AuditWriter(self.directory)

    def persisted(self, decision):
        return json.loads(decision.evidence_path.read_text(encoding='utf-8'))

    def test_runtime_error_after_valid_contract_fails_closed_and_is_auditable(self):
        raw = {**mock_choice('SUFFICIENT'), 'metadata': ExplodingMetadata(note='offline')}
        self.assertTrue(validate(raw, MOCK_MODEL, MOCK_MODEL)[0].valid)
        with self.assertRaisesRegex(RuntimeError, 'metadata canonicalization failed'):
            content_hash(raw)
        provider = UnsafeProvider(raw)
        # Spy on the real gate; validation, hashing, gating, and persistence all run.
        with patch('src.harness.decide', wraps=decide) as gate:
            decision = run(load_fixture('F-01'), provider, writer=self.writer)
        record = decision.record
        self.assertEqual(record['provider']['transport_status'], 'ERROR')
        self.assertEqual(record['component_gate']['component_outcome'], Outcome.INVALID_RESULT)
        self.assertIsNone(record['component_gate']['semantic_signal'])
        self.assertFalse(gate.call_args.args[3], 'provider_valid must remain false')
        self.assertFalse(Validation(**record['validation']).valid)
        self.assertEqual(record['validation']['schema_status'], 'INVALID')
        self.assertEqual(record['evidence']['error_class'], 'RuntimeError')
        self.assertEqual(record['evidence']['error_detail'], 'J5-IR-01 metadata canonicalization failed')
        self.assertIsNone(record['evidence']['raw_response_hash'])
        self.assertEqual(provider.evaluate_calls, 1)
        self.assertEqual(record['provider']['attempt_count'], 1)
        self.assertEqual(record['request']['retry_policy'], {'enabled': False, 'max_attempts': 1})
        self.assertEqual(self.persisted(decision), record)
        self.assertEqual(list(self.directory.glob('.pending-*')), [])

    def test_known_encoding_rejections_keep_j4_classification_without_provider_success(self):
        for metadata, error_class in [({1, 2}, 'TypeError'), (float('nan'), 'ValueError')]:
            with self.subTest(error_class=error_class):
                raw = {**mock_choice('SUFFICIENT'), 'metadata': metadata}
                self.assertTrue(validate(raw, MOCK_MODEL, MOCK_MODEL)[0].valid)
                with patch('src.harness.decide', wraps=decide) as gate:
                    decision = run(load_fixture('F-01'), UnsafeProvider(raw), writer=self.writer)
                record = decision.record
                self.assertFalse(gate.call_args.args[3])
                self.assertEqual(record['provider']['transport_status'], 'OK')
                self.assertFalse(Validation(**record['validation']).valid)
                self.assertEqual(record['component_gate']['component_outcome'], Outcome.INVALID_RESULT)
                self.assertEqual(record['component_gate']['rationale_code'], 'CONTRACT_INVALID')
                self.assertIsNone(record['component_gate']['semantic_signal'])
                self.assertEqual(record['evidence']['error_class'], error_class)
                self.assertIsNone(record['evidence']['raw_response_hash'])
                self.assertEqual(self.persisted(decision), record)

    def test_normalized_probabilities_are_plain_detached_and_preserve_numeric_types(self):
        class ProviderDictionary(dict):
            pass

        for dictionary_type in (dict, ProviderDictionary):
            with self.subTest(dictionary_type=dictionary_type):
                raw = mock_choice('SUFFICIENT')
                raw['probabilities'] = dictionary_type(
                    SUFFICIENT=0.60, INSUFFICIENT=0.40, CONFLICTING=0, UNCERTAIN=0,
                )
                original = dict(raw['probabilities'])
                validation, answer = validate(raw, MOCK_MODEL, MOCK_MODEL)
                self.assertTrue(validation.valid)
                self.assertIs(type(answer['probabilities']), dict)
                self.assertIsNot(answer['probabilities'], raw['probabilities'])
                self.assertEqual(answer['probabilities'], original)
                for label, value in original.items():
                    self.assertIs(type(answer['probabilities'][label]), type(value))
                raw['probabilities']['SUFFICIENT'] = 0.80
                self.assertEqual(answer['probabilities'], original)

    def test_completed_harness_records_survive_provider_dictionary_reuse(self):
        provider = ReusingProbabilityProvider()
        first = run(load_fixture('F-01'), provider, writer=self.writer)
        original_record = deepcopy(first.record)
        original_bytes = first.evidence_path.read_bytes()
        second = run(load_fixture('F-01'), provider, writer=self.writer)
        self.assertEqual(first.record, original_record)
        self.assertEqual(first.evidence_path.read_bytes(), original_bytes)
        self.assertEqual([item.record['answer']['probabilities']['SUFFICIENT']
                          for item in (first, second)], [0.60, 0.80])
        for item in (first, second):
            self.assertIsNot(item.record['answer']['probabilities'], provider.raw['probabilities'])
            self.assertEqual(self.persisted(item), item.record)
            self.assertEqual(item.record['component_gate']['component_outcome'], Outcome.SEMANTIC_CHECK_PASS)
        self.assertEqual(provider.evaluate_calls, 2)

    def test_reused_probabilities_match_persisted_summary_and_only_analysis_crosses(self):
        for threshold in (0.70, 0.90):
            with self.subTest(threshold=threshold):
                provider = ReusingProbabilityProvider()
                profile = AnalysisOnlyProfile('reuse-observation', threshold, 0.70)
                with patch('src.repeatability.summarize_repeat_group', wraps=summarize_repeat_group) as analyze:
                    group = run_repeatability('F-01', 2, provider, writer=self.writer, analysis_profile=profile)
                persisted = [self.persisted(decision) for decision in group.decisions]
                source_records = analyze.call_args.args[0]
                self.assertEqual(source_records, persisted)
                self.assertEqual([record['answer']['probabilities']['SUFFICIENT'] for record in persisted],
                                 [0.60, 0.80])
                self.assertEqual([decision.record for decision in group.decisions], persisted)
                for source, decision in zip(source_records, group.decisions):
                    self.assertIsNot(source, decision.record)
                    self.assertIsNot(source['answer']['probabilities'], provider.raw['probabilities'])
                summary = group.summary
                self.assertEqual(summary['repeat_group_validity'], 'VALID')
                self.assertEqual(summary['probability_vectors'],
                                 [record['answer']['probabilities'] for record in persisted])
                self.assertEqual([vector['SUFFICIENT'] for vector in summary['probability_vectors']], [0.60, 0.80])
                self.assertEqual(summary['component_outcome_sequence'], [Outcome.SEMANTIC_CHECK_PASS] * 2)
                self.assertNotIn('ALLOW', summary['component_outcome_sequence'])
                self.assertEqual(summary['attempt_counts'], [1, 1])
                self.assertEqual(provider.evaluate_calls, 2)
                expected = ([{'field': 'selected_label_probability', 'run_indices': [1, 2],
                              'values': [0.60, 0.80], 'direction': 'UP'}] if threshold == 0.70 else [])
                self.assertEqual(summary['threshold_crossings'], expected)
                self.assertEqual(json.loads(group.summary_path.read_text(encoding='utf-8')), summary)

    def test_summary_source_uses_persisted_content_even_when_writer_enriches_copy(self):
        class EnrichingWriter(AuditWriter):
            def write(self, record):
                stored = deepcopy(record)
                if 'record_type' not in stored:
                    stored['evidence']['persisted_annotation'] = 'local test writer'
                return super().write(stored)

        with patch('src.repeatability.summarize_repeat_group', wraps=summarize_repeat_group) as analyze:
            group = run_repeatability('F-01', 2, ReusingProbabilityProvider(),
                                      writer=EnrichingWriter(self.directory))
        persisted = [self.persisted(decision) for decision in group.decisions]
        self.assertEqual(analyze.call_args.args[0], persisted)
        for source in analyze.call_args.args[0]:
            self.assertEqual(source['evidence']['persisted_annotation'], 'local test writer')

    def test_failed_evidence_readback_aborts_group_without_retry_or_summary(self):
        original_read = Path.read_text
        for error in (OSError('offline readback failure'), json.JSONDecodeError('invalid evidence', '', 0)):
            with self.subTest(error=type(error).__name__):
                provider = ReusingProbabilityProvider()
                before = set(self.directory.glob('*.json'))

                def fail_evidence_read(path, *args, **kwargs):
                    if path.parent == self.directory and path.suffix == '.json':
                        raise error
                    return original_read(path, *args, **kwargs)

                completed = None
                with patch.object(Path, 'read_text', new=fail_evidence_read), \
                     patch('src.repeatability.summarize_repeat_group', wraps=summarize_repeat_group) as analyze:
                    with self.assertRaisesRegex(EvidencePersistenceError, 'NOT COMMITTABLE') as caught:
                        completed = run_repeatability('F-01', 2, provider, writer=self.writer)
                self.assertIsNone(completed)
                self.assertIs(caught.exception.__cause__, error)
                analyze.assert_not_called()
                self.assertEqual(provider.evaluate_calls, 1)
                committed = set(self.directory.glob('*.json')) - before
                self.assertEqual(len(committed), 1)
                record = json.loads(committed.pop().read_text(encoding='utf-8'))
                self.assertNotIn('record_type', record)
                self.assertEqual(record['evidence']['repeatability']['run_index'], 1)
                self.assertEqual(list(self.directory.glob('.pending-*')), [])


if __name__ == '__main__':
    unittest.main()
