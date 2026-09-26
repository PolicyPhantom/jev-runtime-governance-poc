"""Deterministic prerequisites are decided before any provider evaluation."""

from typing import Any

from .fixtures import fixture_identity_valid
from .models import Outcome, Precheck


REQUIRED_FIELDS = (
    "fixture_id", "version", "suspension_cause", "required_evidence",
    "submitted_evidence", "deterministic_flags", "semantic_question",
    "expected_handling_band", "repeat_group", "notes",
)
BANDS = {
    "STABLE_SUFFICIENT", "STABLE_NON_SUFFICIENT", "HOLD_ZONE",
    "DETERMINISTIC_BYPASS", "ADVERSARIAL_RESILIENCE",
}


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _text_list(value: Any) -> bool:
    return isinstance(value, list) and all(_text(item) for item in value)


def check(fixture: Any) -> Precheck:
    data = fixture if isinstance(fixture, dict) else {}
    flags = data.get("deterministic_flags")
    flags = flags if isinstance(flags, dict) else {}
    fields_present = all(field in data for field in REQUIRED_FIELDS)
    binding = flags.get("identity_binding_valid")
    binding_schema = type(binding) is bool or binding == "unresolved"
    schema = (
        fields_present
        and all(_text(data.get(key)) for key in (
            "fixture_id", "version", "suspension_cause", "semantic_question"))
        and _text_list(data.get("required_evidence"))
        and bool(data.get("required_evidence"))
        and _text_list(data.get("submitted_evidence"))
        and _text_list(data.get("notes"))
        and isinstance(data.get("expected_handling_band"), str)
        and data["expected_handling_band"] in BANDS
        and (data.get("repeat_group") is None or _text(data["repeat_group"]))
        and all(type(flags.get(key)) is bool for key in (
            "schema_valid", "required_fields_present", "integrity_valid", "prohibited"))
        and binding_schema
        and flags.get("schema_valid") is True
    )
    # This flag attests structural schema presence, not semantic completeness.
    structural_fields_present = fields_present and flags.get("required_fields_present") is True
    # The audit's required_evidence_present field means an artifact exists.
    # Do not infer sufficiency or binding validity from narrative evidence gaps.
    evidence_present = (
        _text_list(data.get("submitted_evidence"))
        and bool(data.get("submitted_evidence"))
    )
    prohibited = flags.get("prohibited") is True
    integrity = flags.get("integrity_valid") is True
    identity = bool(schema) and fixture_identity_valid(data)

    # J3 requires valid structure and frozen identity before flags are authoritative.
    # This is not a general ordering of combinations of deterministic failures.
    if not fields_present:
        result, reason = Outcome.NOT_EVALUATED, "MISSING_FIXTURE_FIELDS"
    elif not schema:
        result, reason = Outcome.NOT_EVALUATED, "INVALID_FIXTURE_SCHEMA"
    elif not identity:
        result, reason = Outcome.NOT_EVALUATED, "FROZEN_FIXTURE_IDENTITY_MISMATCH"
    elif prohibited:
        result, reason = Outcome.DETERMINISTIC_DENY, "EXPLICIT_PROHIBITION"
    elif not evidence_present:
        result, reason = Outcome.NOT_EVALUATED, "REMEDIATION_ARTIFACT_ABSENT"
    elif not structural_fields_present:
        result, reason = Outcome.NOT_EVALUATED, "REQUIRED_SCHEMA_FIELDS_MISSING"
    elif binding is not True:
        result, reason = Outcome.SEMANTIC_CHECK_HOLD, "IDENTITY_BINDING_UNRESOLVED"
    elif not integrity:
        result, reason = Outcome.SEMANTIC_CHECK_HOLD, "INTEGRITY_PREREQUISITE_FAILED"
    else:
        result, reason = "PASS", "PREREQUISITES_SATISFIED"
    return Precheck(
        bool(schema), structural_fields_present, binding if binding_schema else "unresolved",
        integrity, prohibited, identity, bool(evidence_present), str(result), reason,
    )
