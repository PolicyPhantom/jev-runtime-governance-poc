"""Offline tests for the bounded J6 live-case runner."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

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

class CaptureFailingRawResponse:
    def __deepcopy__(self, memo):
        raise RecursionError("synthetic raw-response snapshot failure")

    def __repr__(self):
        return "<CaptureFailingRawResponse>"


class InvalidReturnProvider:
    sdk_name = "offline-invalid-return-provider"
    sdk_version = "test-v0.1"

    def __init__(self):
        self.calls = 0

    def evaluate(self, request):
        self.calls += 1
        return {
            "unexpected": "provider return object",
        }

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

    def test_local_validation_failure_preserves_provider_return_and_raw_response(self):
        raw_response = mock_choice("SUFFICIENT")

        provider = CountingProvider(
            raw_response,
            resolved_model="jev-1.13.0",
            transport_status="OK",
        )

        temporary_directory, writer = self._writer()

        try:
            with patch(
                "src.j6_live_runner.validate_j6_live_response",
                side_effect=ValueError(
                    "synthetic local validation failure"
                ),
            ):
                completed = run_j6_live_case(
                    "J6-PERM-R1",
                    provider,
                    writer=writer,
                    requested_model="jev-latest",
                )

            record = completed.record

            self.assertEqual(provider.calls, 1)
            self.assertEqual(
                record["provider"]["attempt_count"],
                1,
            )

            # The provider returned successfully. Local processing failure
            # must not rewrite that observation as a provider transport error.
            self.assertEqual(
                record["provider"]["transport_status"],
                "OK",
            )
            self.assertEqual(
                record["provider"]["resolved_model"],
                "jev-1.13.0",
            )

            # The received response must already have been retained before
            # local validation was attempted.
            self.assertIsNotNone(
                record["evidence"]["raw_response_hash"]
            )
            self.assertEqual(
                record["evidence"]["raw_response"],
                raw_response,
            )
            self.assertIsNone(
                record["evidence"]["raw_response_repr"]
            )

            self.assertEqual(
                record["live_component"]["component_outcome"],
                Outcome.INVALID_RESULT.value,
            )
            self.assertEqual(
                record["live_component"]["rationale_code"],
                "J6_LOCAL_RESPONSE_PROCESSING_ERROR",
            )

            self.assertTrue(
                record["stop"]["triggered"]
            )
            self.assertEqual(
                record["stop"]["reason"],
                "LOCAL_RESPONSE_PROCESSING_ERROR",
            )

            self.assertEqual(
                record["evidence"]["error_class"],
                "ValueError",
            )
            self.assertIn(
                "synthetic local validation failure",
                record["evidence"]["error_detail"],
            )

            self.assertTrue(
                completed.evidence_path.exists()
            )

        finally:
            temporary_directory.cleanup()

    def test_raw_response_capture_failure_preserves_fallback_and_stops(self):
        provider = CountingProvider(
            CaptureFailingRawResponse(),
            resolved_model="jev-1.13.0",
            transport_status="OK",
        )

        temporary_directory, writer = self._writer()

        try:
            completed = run_j6_live_case(
                "J6-PERM-R1",
                provider,
                writer=writer,
                requested_model="jev-latest",
            )

            record = completed.record

            self.assertEqual(provider.calls, 1)
            self.assertEqual(
                record["provider"]["attempt_count"],
                1,
            )

            # The provider returned successfully; capture failure is local.
            self.assertEqual(
                record["provider"]["transport_status"],
                "OK",
            )
            self.assertEqual(
                record["provider"]["resolved_model"],
                "jev-1.13.0",
            )

            # Trusted raw evidence must remain empty because snapshot failed.
            self.assertIsNone(
                record["evidence"]["raw_response_hash"]
            )
            self.assertIsNone(
                record["evidence"]["raw_response"]
            )

            # Best-effort attributable representation is still retained.
            self.assertEqual(
                record["evidence"]["raw_response_repr"],
                "<CaptureFailingRawResponse>",
            )

            self.assertEqual(
                record["live_component"]["component_outcome"],
                Outcome.INVALID_RESULT.value,
            )
            self.assertEqual(
                record["live_component"]["rationale_code"],
                "J6_LOCAL_RESPONSE_PROCESSING_ERROR",
            )

            self.assertTrue(
                record["stop"]["triggered"]
            )
            self.assertEqual(
                record["stop"]["reason"],
                "LOCAL_RESPONSE_PROCESSING_ERROR",
            )

            self.assertEqual(
                record["evidence"]["error_class"],
                "RecursionError",
            )
            self.assertIn(
                "synthetic raw-response snapshot failure",
                record["evidence"]["error_detail"],
            )

            self.assertTrue(
                completed.evidence_path.exists()
            )

        finally:
            temporary_directory.cleanup()

    def test_invalid_provider_return_type_preserves_returned_object_repr(self):
        provider = InvalidReturnProvider()

        temporary_directory, writer = self._writer()

        try:
            completed = run_j6_live_case(
                "J6-PERM-R1",
                provider,
                writer=writer,
                requested_model="jev-latest",
            )

            record = completed.record

            self.assertEqual(provider.calls, 1)
            self.assertEqual(
                record["provider"]["attempt_count"],
                1,
            )

            self.assertEqual(
                record["provider"]["transport_status"],
                "RETURNED_INVALID_TYPE",
            )

            self.assertIsNone(
                record["evidence"]["raw_response_hash"]
            )
            self.assertIsNone(
                record["evidence"]["raw_response"]
            )
            self.assertIn(
                "provider return object",
                record["evidence"]["raw_response_repr"],
            )

            self.assertEqual(
                record["live_component"]["component_outcome"],
                Outcome.INVALID_RESULT.value,
            )
            self.assertEqual(
                record["live_component"]["rationale_code"],
                "J6_LOCAL_RESPONSE_PROCESSING_ERROR",
            )

            self.assertTrue(
                record["stop"]["triggered"]
            )
            self.assertEqual(
                record["stop"]["reason"],
                "LOCAL_RESPONSE_PROCESSING_ERROR",
            )

            self.assertEqual(
                record["evidence"]["error_class"],
                "TypeError",
            )

            self.assertTrue(
                completed.evidence_path.exists()
            )

        finally:
            temporary_directory.cleanup()

if __name__ == "__main__":
    unittest.main()