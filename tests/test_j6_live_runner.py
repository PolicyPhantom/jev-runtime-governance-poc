"""Offline tests for the bounded J6 live-case runner."""

from pathlib import Path
import tempfile
import unittest

from src.audit import AuditWriter, EVIDENCE_ROOT, EvidencePersistenceError
from src.j6_live_runner import run_j6_live_case
from src.models import Outcome
from src.providers import MockProvider, ProviderResponse, mock_choice


class CountingProvider:
    sdk_name = "offline-counting-provider"
    sdk_version = "test-v0.1"

    def __init__(
        self,
        raw_response,
        *,
        resolved_model="jev-1.13.0",
        transport_status="OK",
    ):
        self.raw_response = raw_response
        self.resolved_model = resolved_model
        self.transport_status = transport_status
        self.calls = 0

    def evaluate(self, request):
        self.calls += 1

        return ProviderResponse(
            raw_response=self.raw_response,
            resolved_model=self.resolved_model,
            transport_status=self.transport_status,
        )


class RaisingProvider:
    sdk_name = "offline-raising-provider"
    sdk_version = "test-v0.1"

    def __init__(self):
        self.calls = 0

    def evaluate(self, request):
        self.calls += 1
        raise RuntimeError("synthetic provider failure")


class FailingWriter:
    def write(self, record):
        raise EvidencePersistenceError(
            "synthetic evidence persistence failure"
        )


class J6LiveRunnerTests(unittest.TestCase):
    def _writer(self):
        temporary_directory = tempfile.TemporaryDirectory(
            dir=EVIDENCE_ROOT
        )

        writer = AuditWriter(
            Path(temporary_directory.name)
        )

        return temporary_directory, writer

    def test_r1_live_pass_remains_separate_from_frozen_permission(self):
        provider = CountingProvider(
            mock_choice("SUFFICIENT"),
            resolved_model="jev-1.13.0",
        )

        temporary_directory, writer = self._writer()

        try:
            completed = run_j6_live_case(
                "J6-PERM-R1",
                provider,
                writer=writer,
                requested_model="jev-latest",
            )
        finally:
            temporary_directory.cleanup()

        record = completed.record

        self.assertEqual(provider.calls, 1)
        self.assertEqual(
            record["provider"]["attempt_count"],
            1,
        )

        self.assertEqual(
            record["live_case"]["j6_scenario_id"],
            "J6-PERM-R1",
        )
        self.assertEqual(
            record["live_case"]["provider_source_fixture_id"],
            "F-01",
        )

        self.assertEqual(
            record["live_component"]["component_outcome"],
            Outcome.SEMANTIC_CHECK_PASS.value,
        )

        self.assertEqual(
            record["frozen_j6_assessment"][
                "decision_reconstruction_status"
            ],
            "RECONSTRUCTED",
        )
        self.assertEqual(
            record["frozen_j6_assessment"][
                "permission_applicability_status"
            ],
            "NOT_SUPPORTED",
        )

        self.assertFalse(record["stop"]["triggered"])

    def test_x1_live_hold_remains_separate_from_frozen_permission(self):
        provider = CountingProvider(
            mock_choice("INSUFFICIENT"),
            resolved_model="jev-1.13.0",
        )

        temporary_directory, writer = self._writer()

        try:
            completed = run_j6_live_case(
                "J6-PERM-X1",
                provider,
                writer=writer,
                requested_model="jev-latest",
            )
        finally:
            temporary_directory.cleanup()

        record = completed.record

        self.assertEqual(provider.calls, 1)

        self.assertEqual(
            record["live_case"]["j6_scenario_id"],
            "J6-PERM-X1",
        )
        self.assertEqual(
            record["live_case"]["provider_source_fixture_id"],
            "F-02",
        )

        self.assertEqual(
            record["live_component"]["component_outcome"],
            Outcome.SEMANTIC_CHECK_HOLD.value,
        )

        self.assertEqual(
            record["frozen_j6_assessment"][
                "permission_applicability_status"
            ],
            "NOT_SUPPORTED",
        )

        self.assertFalse(record["stop"]["triggered"])

    def test_model_identity_mismatch_is_observed_without_stop(self):
        provider = CountingProvider(
            mock_choice("SUFFICIENT"),
            resolved_model="jev-1.13.0",
        )

        temporary_directory, writer = self._writer()

        try:
            completed = run_j6_live_case(
                "J6-PERM-R1",
                provider,
                writer=writer,
                requested_model="jev-latest",
            )
        finally:
            temporary_directory.cleanup()

        record = completed.record

        self.assertEqual(
            record["validation"]["model_identity_status"],
            "MISMATCH",
        )
        self.assertTrue(
            record["validation"]["response_contract_valid"]
        )
        self.assertFalse(record["stop"]["triggered"])
        self.assertEqual(
            record["live_component"]["component_outcome"],
            Outcome.SEMANTIC_CHECK_PASS.value,
        )

    def test_malformed_response_is_invalid_and_stops(self):
        malformed = {
            "primitive": "choice",
            "selected_label": "SUFFICIENT",
            "probabilities": {
                "SUFFICIENT": 0.90,
                "INSUFFICIENT": 0.20,
                "CONFLICTING": 0.00,
                "UNCERTAIN": 0.00,
            },
            "confidence": 0.81,
        }

        provider = CountingProvider(
            malformed,
            resolved_model="jev-1.13.0",
        )

        temporary_directory, writer = self._writer()

        try:
            completed = run_j6_live_case(
                "J6-PERM-R1",
                provider,
                writer=writer,
            )
        finally:
            temporary_directory.cleanup()

        record = completed.record

        self.assertEqual(provider.calls, 1)
        self.assertEqual(
            record["live_component"]["component_outcome"],
            Outcome.INVALID_RESULT.value,
        )
        self.assertTrue(record["stop"]["triggered"])
        self.assertEqual(
            record["stop"]["reason"],
            "MALFORMED_PROVIDER_RESPONSE",
        )

    def test_provider_exception_is_invalid_and_stops_without_retry(self):
        provider = RaisingProvider()

        temporary_directory, writer = self._writer()

        try:
            completed = run_j6_live_case(
                "J6-PERM-R1",
                provider,
                writer=writer,
            )
        finally:
            temporary_directory.cleanup()

        record = completed.record

        self.assertEqual(provider.calls, 1)
        self.assertEqual(
            record["provider"]["attempt_count"],
            1,
        )
        self.assertEqual(
            record["provider"]["transport_status"],
            "ERROR",
        )
        self.assertEqual(
            record["live_component"]["component_outcome"],
            Outcome.INVALID_RESULT.value,
        )
        self.assertTrue(record["stop"]["triggered"])
        self.assertEqual(
            record["stop"]["reason"],
            "PROVIDER_EXECUTION_ERROR",
        )

    def test_unapproved_scenario_is_rejected_before_provider_call(self):
        provider = CountingProvider(
            mock_choice("SUFFICIENT"),
        )

        temporary_directory, writer = self._writer()

        try:
            with self.assertRaisesRegex(
                ValueError,
                "Unapproved J6 live scenario",
            ):
                run_j6_live_case(
                    "J6-PERM-UNAPPROVED",
                    provider,
                    writer=writer,
                )
        finally:
            temporary_directory.cleanup()

        self.assertEqual(provider.calls, 0)

    def test_persistence_failure_returns_no_completed_result(self):
        provider = CountingProvider(
            mock_choice("SUFFICIENT"),
        )

        with self.assertRaises(
            EvidencePersistenceError
        ):
            run_j6_live_case(
                "J6-PERM-R1",
                provider,
                writer=FailingWriter(),
            )

        self.assertEqual(provider.calls, 1)


if __name__ == "__main__":
    unittest.main()