"""Diagnostic rendering regressions for J6 live runner."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.audit import AuditWriter, EVIDENCE_ROOT
from src.j6_live_runner import run_j6_live_case
from src.models import Outcome
from src.providers import ProviderResponse, mock_choice


class BadTextError(Exception):
    def __str__(self):
        raise RuntimeError("broken __str__")


class SnapshotFail:
    def __deepcopy__(self, memo):
        raise BadTextError()

    def __repr__(self):
        return "<SnapshotFail>"


class BadRepr:
    def __repr__(self):
        raise BadTextError()


class Provider:
    sdk_name = "offline-diagnostic-provider"
    sdk_version = "test-v0.1"

    def __init__(self, value, raw=True):
        self.value = value
        self.raw = raw
        self.calls = 0

    def evaluate(self, request):
        self.calls += 1
        if self.raw:
            return ProviderResponse(self.value, "jev-1.13.0", "OK")
        return self.value


class DiagnosticFailureTests(unittest.TestCase):
    def run_case(self, provider, patch_validation=False):
        temp = tempfile.TemporaryDirectory(dir=EVIDENCE_ROOT)
        writer = AuditWriter(Path(temp.name))
        try:
            if patch_validation:
                with patch(
                    "src.j6_live_runner.validate_j6_live_response",
                    side_effect=BadTextError(),
                ):
                    completed = run_j6_live_case(
                        "J6-PERM-R1", provider, writer=writer
                    )
            else:
                completed = run_j6_live_case(
                    "J6-PERM-R1", provider, writer=writer
                )
            self.assertTrue(completed.evidence_path.exists())
            return completed.record
        finally:
            temp.cleanup()

    def test_snapshot_failure_with_broken_exception_text_persists(self):
        provider = Provider(SnapshotFail())
        record = self.run_case(provider)
        self.assertEqual(provider.calls, 1)
        self.assertEqual(record["provider"]["transport_status"], "OK")
        self.assertIsNone(record["evidence"]["raw_response_hash"])
        self.assertIsNone(record["evidence"]["raw_response"])
        self.assertEqual(
            record["evidence"]["raw_response_repr"], "<SnapshotFail>"
        )
        self.assertEqual(
            record["evidence"]["error_detail"],
            "RAW_RESPONSE_CAPTURE_ERROR: <exception message unavailable>",
        )
        self.assertEqual(
            record["live_component"]["component_outcome"],
            Outcome.INVALID_RESULT.value,
        )
        self.assertEqual(
            record["stop"]["reason"], "LOCAL_RESPONSE_PROCESSING_ERROR"
        )

    def test_validation_failure_with_broken_exception_text_persists(self):
        raw = mock_choice("SUFFICIENT")
        provider = Provider(raw)
        record = self.run_case(provider, patch_validation=True)
        self.assertEqual(provider.calls, 1)
        self.assertEqual(record["provider"]["transport_status"], "OK")
        self.assertIsNotNone(record["evidence"]["raw_response_hash"])
        self.assertEqual(record["evidence"]["raw_response"], raw)
        self.assertEqual(
            record["evidence"]["error_detail"],
            "LOCAL_RESPONSE_PROCESSING_ERROR: <exception message unavailable>",
        )
        self.assertEqual(
            record["live_component"]["component_outcome"],
            Outcome.INVALID_RESULT.value,
        )
        self.assertEqual(
            record["stop"]["reason"], "LOCAL_RESPONSE_PROCESSING_ERROR"
        )

    def test_invalid_return_with_broken_repr_uses_literal_fallback(self):
        provider = Provider(BadRepr(), raw=False)
        record = self.run_case(provider)
        self.assertEqual(provider.calls, 1)
        self.assertEqual(
            record["provider"]["transport_status"], "RETURNED_INVALID_TYPE"
        )
        self.assertIsNone(record["evidence"]["raw_response_hash"])
        self.assertIsNone(record["evidence"]["raw_response"])
        self.assertEqual(
            record["evidence"]["raw_response_repr"],
            "<raw response representation unavailable>",
        )
        self.assertEqual(
            record["live_component"]["component_outcome"],
            Outcome.INVALID_RESULT.value,
        )
        self.assertEqual(
            record["stop"]["reason"], "LOCAL_RESPONSE_PROCESSING_ERROR"
        )


if __name__ == "__main__":
    unittest.main()
