"""The deterministic gate owns the component outcome, never runtime authority."""

from .contracts import Validation
from .models import GateResult, LABELS, Outcome, Precheck


def decide(precheck: Precheck, validation: Validation, selected_label: str | None,
           provider_valid: bool) -> GateResult:
    # Precheck alone owns deterministic bypass outcomes and their rationale.
    if precheck.result != "PASS":
        return GateResult(None, Outcome(precheck.result), precheck.rationale_code)
    if not all((precheck.schema_valid, precheck.required_fields_present,
                precheck.identity_binding_valid is True, precheck.integrity_valid,
                precheck.fixture_identity_valid, precheck.required_evidence_present,
                not precheck.prohibited)):
        return GateResult(None, Outcome.NOT_EVALUATED, "DETERMINISTIC_PREREQUISITE_FAILED")
    if not provider_valid:
        return GateResult(None, Outcome.INVALID_RESULT, "PROVIDER_RESULT_INVALID")
    if not validation.valid or selected_label not in LABELS:
        return GateResult(None, Outcome.INVALID_RESULT, "CONTRACT_INVALID")
    if selected_label == "SUFFICIENT":
        return GateResult(selected_label, Outcome.SEMANTIC_CHECK_PASS, "SEMANTIC_SUPPORT_SUFFICIENT")
    return GateResult(selected_label, Outcome.SEMANTIC_CHECK_HOLD, "SEMANTIC_SUPPORT_NOT_SUFFICIENT")
