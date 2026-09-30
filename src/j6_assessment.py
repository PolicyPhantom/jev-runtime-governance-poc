"""Deterministic J6 assessment semantics.

This module implements the frozen J6 v0.3 decision-reconstruction and
permission-applicability semantics. It does not grant runtime authority.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .j6_fixtures import j6_fixture_identity_valid
from .models import JsonObject


class DecisionReconstructionStatus(StrEnum):
    RECONSTRUCTED = "RECONSTRUCTED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    NOT_ASSESSED = "NOT_ASSESSED"


class PermissionApplicabilityStatus(StrEnum):
    SUPPORTED = "SUPPORTED"
    NOT_SUPPORTED = "NOT_SUPPORTED"
    INDETERMINATE = "INDETERMINATE"
    NOT_ASSESSED = "NOT_ASSESSED"


DR_REASON_CODES = frozenset({
    "DR_EVIDENCE_COMPLETE",
    "DR_MISSING_DECISION_INPUT",
    "DR_MISSING_APPLIED_RULE",
    "DR_MISSING_DECISION_RECORD",
    "DR_BROKEN_EVIDENCE_LINKAGE",
    "DR_SEQUENCE_UNRESOLVED",
    "DR_CONFLICTING_RECORDS",
    "DR_INTEGRITY_UNRESOLVED",
    "DR_OUT_OF_SCOPE",
    "DR_NOT_RUN",
})

PA_REASON_CODES = frozenset({
    "PA_TERMS_SATISFIED",
    "PA_VALID_EXCEPTION_APPLIES",
    "PA_RESTORATION_CONDITIONS_SATISFIED",
    "PA_ACTIVE_RESTRICTION",
    "PA_EXPLICIT_EXCLUSION",
    "PA_RESTORATION_CONDITION_UNMET",
    "PA_APPROVAL_NOT_EFFECTIVE",
    "PA_REQUIRED_EXCEPTION_ABSENT",
    "PA_AUTHORITY_UNRESOLVED",
    "PA_EFFECTIVE_TIME_UNRESOLVED",
    "PA_SCOPE_UNRESOLVED",
    "PA_DELEGATION_UNRESOLVED",
    "PA_EXCEPTION_UNRESOLVED",
    "PA_REQUIRED_CONDITION_EVIDENCE_MISSING",
    "PA_CONFLICTING_AUTHORITY_EVIDENCE",
    "PA_OUT_OF_SCOPE",
    "PA_NOT_RUN",
})


@dataclass(frozen=True)
class J6AssessmentResult:
    decision_reconstruction_status: DecisionReconstructionStatus
    decision_reconstruction_reason_code: str
    permission_applicability_status: PermissionApplicabilityStatus
    permission_reason_code: str


def _nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _nonempty_list(value: Any) -> bool:
    return isinstance(value, list) and len(value) > 0


def _assessment_scope(fixture: JsonObject, key: str) -> str:
    scope = fixture.get("assessment_scope")

    if not isinstance(scope, dict):
        return "RUN"

    value = scope.get(key, "RUN")

    if value is False or value == "NOT_RUN":
        return "NOT_RUN"

    if value == "OUT_OF_SCOPE":
        return "OUT_OF_SCOPE"

    return "RUN"


def assess_decision_reconstruction(
    fixture: JsonObject,
) -> tuple[DecisionReconstructionStatus, str]:
    """Assess reconstruction from trusted, pre-materialized J6 fixture facts.

    This helper is not a standalone integrity or raw-evidence validation
    boundary. Callers must use assess_j6_fixture() for the guarded path that
    first verifies the frozen fixture identity chain.
    """

    scope = _assessment_scope(fixture, "decision_reconstruction")

    if scope == "NOT_RUN":
        return (
            DecisionReconstructionStatus.NOT_ASSESSED,
            "DR_NOT_RUN",
        )

    if scope == "OUT_OF_SCOPE":
        return (
            DecisionReconstructionStatus.NOT_ASSESSED,
            "DR_OUT_OF_SCOPE",
        )

    required_record_fields = (
        "decision_id",
        "examined_action",
        "decision_time",
        "decision_result",
    )

    if not all(_nonempty_string(fixture.get(field))
               for field in required_record_fields):
        return (
            DecisionReconstructionStatus.INSUFFICIENT_EVIDENCE,
            "DR_MISSING_DECISION_RECORD",
        )

    decision_inputs = fixture.get("decision_input_references")
    evidence_items = fixture.get("evidence_items")

    if not _nonempty_list(decision_inputs) or not isinstance(evidence_items, dict):
        return (
            DecisionReconstructionStatus.INSUFFICIENT_EVIDENCE,
            "DR_MISSING_DECISION_INPUT",
        )

    if any(not _nonempty_string(reference) or reference not in evidence_items
           for reference in decision_inputs):
        return (
            DecisionReconstructionStatus.INSUFFICIENT_EVIDENCE,
            "DR_MISSING_DECISION_INPUT",
        )

    if not _nonempty_string(fixture.get("applied_rule_reference")):
        return (
            DecisionReconstructionStatus.INSUFFICIENT_EVIDENCE,
            "DR_MISSING_APPLIED_RULE",
        )

    linkage = fixture.get("evidence_linkage")

    if not _nonempty_list(linkage):
        return (
            DecisionReconstructionStatus.INSUFFICIENT_EVIDENCE,
            "DR_BROKEN_EVIDENCE_LINKAGE",
        )

    reconstruction_facts = fixture.get("reconstruction_facts", {})

    if isinstance(reconstruction_facts, dict):
        if reconstruction_facts.get("records_conflict") is True:
            return (
                DecisionReconstructionStatus.INSUFFICIENT_EVIDENCE,
                "DR_CONFLICTING_RECORDS",
            )

        if reconstruction_facts.get("sequence_resolved") is False:
            return (
                DecisionReconstructionStatus.INSUFFICIENT_EVIDENCE,
                "DR_SEQUENCE_UNRESOLVED",
            )

        if reconstruction_facts.get("linkage_resolved") is False:
            return (
                DecisionReconstructionStatus.INSUFFICIENT_EVIDENCE,
                "DR_BROKEN_EVIDENCE_LINKAGE",
            )

    if not _nonempty_string(fixture.get("evidence_integrity_reference")):
        return (
            DecisionReconstructionStatus.INSUFFICIENT_EVIDENCE,
            "DR_INTEGRITY_UNRESOLVED",
        )

    return (
        DecisionReconstructionStatus.RECONSTRUCTED,
        "DR_EVIDENCE_COMPLETE",
    )


def assess_permission_applicability(
    fixture: JsonObject,
) -> tuple[PermissionApplicabilityStatus, str]:
    """Assess permission from trusted, pre-resolved J6 fixture facts.

    This helper consumes reviewed authority, scope, timing, condition,
    delegation, exception, and restoration facts. It is not a standalone
    resolver of raw authority or evidence records. Callers must use
    assess_j6_fixture() for the guarded fixture-identity path.
    """

    scope = _assessment_scope(fixture, "permission_applicability")

    if scope == "NOT_RUN":
        return (
            PermissionApplicabilityStatus.NOT_ASSESSED,
            "PA_NOT_RUN",
        )

    if scope == "OUT_OF_SCOPE":
        return (
            PermissionApplicabilityStatus.NOT_ASSESSED,
            "PA_OUT_OF_SCOPE",
        )

    if not _nonempty_string(fixture.get("authority_reference")):
        return (
            PermissionApplicabilityStatus.INDETERMINATE,
            "PA_AUTHORITY_UNRESOLVED",
        )

    if not _nonempty_string(fixture.get("authority_scope")):
        return (
            PermissionApplicabilityStatus.INDETERMINATE,
            "PA_SCOPE_UNRESOLVED",
        )

    effective_time = fixture.get("authority_effective_time_or_interval")
    if not isinstance(effective_time, dict) or not effective_time:
        return (
            PermissionApplicabilityStatus.INDETERMINATE,
            "PA_EFFECTIVE_TIME_UNRESOLVED",
        )

    if not _nonempty_string(fixture.get("examined_action")):
        return (
            PermissionApplicabilityStatus.INDETERMINATE,
            "PA_SCOPE_UNRESOLVED",
        )

    if not _nonempty_string(fixture.get("decision_time")):
        return (
            PermissionApplicabilityStatus.INDETERMINATE,
            "PA_EFFECTIVE_TIME_UNRESOLVED",
        )

    terms = fixture.get("applicable_permission_or_restriction_terms")
    if not _nonempty_list(terms):
        return (
            PermissionApplicabilityStatus.INDETERMINATE,
            "PA_REQUIRED_CONDITION_EVIDENCE_MISSING",
        )

    condition_refs = fixture.get("condition_evidence_references")
    evidence_items = fixture.get("evidence_items")

    if not _nonempty_list(condition_refs) or not isinstance(evidence_items, dict):
        return (
            PermissionApplicabilityStatus.INDETERMINATE,
            "PA_REQUIRED_CONDITION_EVIDENCE_MISSING",
        )

    if any(not _nonempty_string(reference) or reference not in evidence_items
           for reference in condition_refs):
        return (
            PermissionApplicabilityStatus.INDETERMINATE,
            "PA_REQUIRED_CONDITION_EVIDENCE_MISSING",
        )

    facts = fixture.get("permission_facts")

    if not isinstance(facts, dict):
        return (
            PermissionApplicabilityStatus.INDETERMINATE,
            "PA_REQUIRED_CONDITION_EVIDENCE_MISSING",
        )

    if facts.get("conflicting_authority_evidence") is True:
        return (
            PermissionApplicabilityStatus.INDETERMINATE,
            "PA_CONFLICTING_AUTHORITY_EVIDENCE",
        )

    resolution_checks = (
        ("authority_resolved", "PA_AUTHORITY_UNRESOLVED"),
        ("scope_resolved", "PA_SCOPE_UNRESOLVED"),
        ("effective_time_resolved", "PA_EFFECTIVE_TIME_UNRESOLVED"),
        ("conditions_resolved", "PA_REQUIRED_CONDITION_EVIDENCE_MISSING"),
        ("delegation_resolved", "PA_DELEGATION_UNRESOLVED"),
        ("exception_resolved", "PA_EXCEPTION_UNRESOLVED"),
        ("restoration_terms_resolved",
         "PA_REQUIRED_CONDITION_EVIDENCE_MISSING"),
    )

    for fact_name, reason_code in resolution_checks:
        if facts.get(fact_name) is not True:
            return (
                PermissionApplicabilityStatus.INDETERMINATE,
                reason_code,
            )

    explicit_exclusions = facts.get("explicit_exclusions", [])
    if _nonempty_list(explicit_exclusions):
        return (
            PermissionApplicabilityStatus.NOT_SUPPORTED,
            "PA_EXPLICIT_EXCLUSION",
        )

    unmet_conditions = facts.get("unmet_necessary_conditions", [])
    if _nonempty_list(unmet_conditions):
        restoration = fixture.get("restoration_condition")

        if isinstance(restoration, dict):
            restoration_id = restoration.get("condition_id")
            if restoration_id in unmet_conditions:
                return (
                    PermissionApplicabilityStatus.NOT_SUPPORTED,
                    "PA_RESTORATION_CONDITION_UNMET",
                )

        return (
            PermissionApplicabilityStatus.NOT_SUPPORTED,
            "PA_ACTIVE_RESTRICTION",
        )

    operative_restrictions = facts.get("operative_restrictions", [])
    if _nonempty_list(operative_restrictions):
        return (
            PermissionApplicabilityStatus.NOT_SUPPORTED,
            "PA_ACTIVE_RESTRICTION",
        )

    if facts.get("all_necessary_permission_conditions_satisfied") is True:
        exception = fixture.get("exception")

        if isinstance(exception, dict) and exception.get("applicable") is True:
            return (
                PermissionApplicabilityStatus.SUPPORTED,
                "PA_VALID_EXCEPTION_APPLIES",
            )

        restoration = fixture.get("restoration_condition")

        if (isinstance(restoration, dict)
                and restoration.get("required") is True):
            return (
                PermissionApplicabilityStatus.SUPPORTED,
                "PA_RESTORATION_CONDITIONS_SATISFIED",
            )

        return (
            PermissionApplicabilityStatus.SUPPORTED,
            "PA_TERMS_SATISFIED",
        )

    return (
        PermissionApplicabilityStatus.INDETERMINATE,
        "PA_REQUIRED_CONDITION_EVIDENCE_MISSING",
    )


def assess_j6_fixture(fixture: JsonObject) -> J6AssessmentResult:
    # The frozen fixture identity chain is a prerequisite for trusting the
    # materialized J6 evidence. A broken identity cannot yield a positive
    # reconstruction or permission conclusion.
    if not j6_fixture_identity_valid(fixture):
        return J6AssessmentResult(
            decision_reconstruction_status=(
                DecisionReconstructionStatus.INSUFFICIENT_EVIDENCE
            ),
            decision_reconstruction_reason_code="DR_INTEGRITY_UNRESOLVED",
            permission_applicability_status=(
                PermissionApplicabilityStatus.INDETERMINATE
            ),
            permission_reason_code="PA_REQUIRED_CONDITION_EVIDENCE_MISSING",
        )

    reconstruction_status, reconstruction_reason = (
        assess_decision_reconstruction(fixture)
    )

    permission_status, permission_reason = (
        assess_permission_applicability(fixture)
    )

    return J6AssessmentResult(
        decision_reconstruction_status=reconstruction_status,
        decision_reconstruction_reason_code=reconstruction_reason,
        permission_applicability_status=permission_status,
        permission_reason_code=permission_reason,
    )