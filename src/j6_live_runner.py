"""Bounded J6 live-case runner.

This module connects one frozen J6 scenario to one frozen semantic source
fixture and at most one provider attempt.

It does not implement retries, repeatability runs, or provider-specific API
configuration. Live provider execution remains separately Human-Gated.
"""

from copy import deepcopy
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from .audit import AuditWriter, EVIDENCE_ROOT
from .fixtures import (
    content_hash,
    fixture_identity_valid,
    load_fixture,
)
from .j6_assessment import assess_j6_fixture
from .j6_fixtures import load_j6_fixture
from .j6_live_validation import validate_j6_live_response
from .models import JsonObject, Outcome
from .providers import Provider, ProviderRequest, ProviderResponse


J6_LIVE_EVIDENCE_DIR = EVIDENCE_ROOT / "j6_live"

J6_LIVE_CASE_MAP = {
    "J6-PERM-R1": "F-01",
    "J6-PERM-X1": "F-02",
}


@dataclass(frozen=True)
class J6CompletedLiveCase:
    record: JsonObject
    evidence_path: Path


def _semantic_provider_input(
    source_fixture: JsonObject,
) -> tuple[JsonObject, str]:
    """Materialize only the frozen semantic fields visible to the provider."""
    state = {
        key: deepcopy(source_fixture.get(key))
        for key in (
            "suspension_cause",
            "required_evidence",
            "submitted_evidence",
        )
    }

    question = source_fixture.get("semantic_question")

    if not isinstance(question, str) or not question.strip():
        raise ValueError("Frozen semantic source has no valid semantic question")

    return state, question


def _live_component_result(
    *,
    transport_status: str,
    response_contract_valid: bool,
    selected_label: object,
    raw_response_hash: str | None,
) -> tuple[str, str, bool, str | None]:
    """Derive the live component result without model-equality gating.

    Returns:
        component_outcome,
        rationale_code,
        stop_triggered,
        stop_reason
    """
    if transport_status != "OK":
        return (
            Outcome.INVALID_RESULT.value,
            "J6_PROVIDER_TRANSPORT_INVALID",
            True,
            "PROVIDER_TRANSPORT_FAILURE",
        )

    if raw_response_hash is None:
        return (
            Outcome.INVALID_RESULT.value,
            "J6_RESPONSE_EVIDENCE_UNENCODABLE",
            True,
            "UNENCODABLE_PROVIDER_RESPONSE",
        )

    if not response_contract_valid:
        return (
            Outcome.INVALID_RESULT.value,
            "J6_RESPONSE_CONTRACT_INVALID",
            True,
            "MALFORMED_PROVIDER_RESPONSE",
        )

    if selected_label == "SUFFICIENT":
        return (
            Outcome.SEMANTIC_CHECK_PASS.value,
            "J6_SEMANTIC_SUPPORT_SUFFICIENT",
            False,
            None,
        )

    return (
        Outcome.SEMANTIC_CHECK_HOLD.value,
        "J6_SEMANTIC_SUPPORT_NOT_SUFFICIENT",
        False,
        None,
    )


def run_j6_live_case(
    j6_scenario_id: str,
    provider: Provider,
    *,
    writer: AuditWriter | None = None,
    requested_model: str = "jev-latest",
) -> J6CompletedLiveCase:
    """Run exactly one bounded provider attempt for one approved J6 case.

    This function has no retry loop. The supplied provider must also be
    configured with retry disabled before live execution.
    """
    if j6_scenario_id not in J6_LIVE_CASE_MAP:
        raise ValueError(f"Unapproved J6 live scenario: {j6_scenario_id}")

    source_fixture_id = J6_LIVE_CASE_MAP[j6_scenario_id]

    # Both identity chains must be valid before any provider attempt.
    j6_fixture = load_j6_fixture(j6_scenario_id)
    source_fixture = load_fixture(source_fixture_id)

    if not fixture_identity_valid(source_fixture):
        raise ValueError(
            f"Frozen semantic source identity invalid: {source_fixture_id}"
        )

    frozen_assessment = assess_j6_fixture(j6_fixture)

    state, question = _semantic_provider_input(source_fixture)

    record: JsonObject = {
        "logical_decision_id": str(uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "live_case": {
            "j6_scenario_id": j6_scenario_id,
            "j6_scenario_version": j6_fixture.get("version"),
            "j6_scenario_hash": content_hash(j6_fixture),
            "fixture_decision_id": j6_fixture.get("decision_id"),
            "provider_source_fixture_id": source_fixture_id,
            "provider_source_fixture_version": source_fixture.get("version"),
            "provider_source_fixture_hash": content_hash(source_fixture),
            "source_expected_handling_band": source_fixture.get(
                "expected_handling_band"
            ),
        },
        "input": {
            "state_hash": content_hash(state),
            "question_hash": content_hash(question),
            "provider_visible_fields": [
                "suspension_cause",
                "required_evidence",
                "submitted_evidence",
                "semantic_question",
            ],
        },
        "request": {
            "primitive": "choice",
            "requested_model": requested_model,
            "sdk_name": getattr(provider, "sdk_name", None),
            "sdk_version": getattr(provider, "sdk_version", None),
            "retry_policy": {
                "enabled": False,
                "max_attempts": 1,
            },
        },
        "provider": {
            "transport_status": "NOT_CALLED",
            "resolved_model": None,
            "attempt_count": 0,
            "latency_ms": None,
        },
        "answer": {
            "selected_label": None,
            "probabilities": None,
            "confidence_nullable": None,
        },
        "validation": {
            "schema_status": "NOT_EVALUATED",
            "allowed_label_status": "NOT_EVALUATED",
            "probability_status": "NOT_EVALUATED",
            "confidence_status": "NOT_EVALUATED",
            "model_identity_status": "NOT_EVALUATED",
            "response_contract_valid": False,
        },
        "live_component": {
            "component_outcome": Outcome.INVALID_RESULT.value,
            "rationale_code": "J6_PROVIDER_NOT_EVALUATED",
        },
        "frozen_j6_assessment": {
            "decision_reconstruction_status": (
                frozen_assessment.decision_reconstruction_status.value
            ),
            "decision_reconstruction_reason_code": (
                frozen_assessment.decision_reconstruction_reason_code
            ),
            "permission_applicability_status": (
                frozen_assessment.permission_applicability_status.value
            ),
            "permission_reason_code": (
                frozen_assessment.permission_reason_code
            ),
        },
        "evidence": {
            "raw_response_hash": None,
            "raw_response": None,
            "raw_response_repr": None,
            "error_class": None,
            "error_detail": None,
        },
        "stop": {
            "triggered": False,
            "reason": None,
        },
    }

    request = ProviderRequest(
        state=deepcopy(state),
        semantic_question=question,
        requested_model=requested_model,
    )

    start = perf_counter()

    try:
        # Exactly one runner-level provider attempt.
        record["provider"]["attempt_count"] = 1

        try:
            response = provider.evaluate(request)

        except Exception as error:
            # The provider call itself failed before a usable response returned.
            record["provider"]["transport_status"] = "ERROR"

            record["live_component"] = {
                "component_outcome": Outcome.INVALID_RESULT.value,
                "rationale_code": "J6_PROVIDER_EXECUTION_ERROR",
            }

            record["stop"] = {
                "triggered": True,
                "reason": "PROVIDER_EXECUTION_ERROR",
            }

            record["evidence"]["error_class"] = type(error).__name__
            record["evidence"]["error_detail"] = str(error)

        else:
            if not isinstance(response, ProviderResponse):
                # The provider returned, but the local adapter boundary could
                # not interpret the returned object as ProviderResponse.
                record["provider"]["transport_status"] = (
                    "RETURNED_INVALID_TYPE"
                )

                record["live_component"] = {
                    "component_outcome": Outcome.INVALID_RESULT.value,
                    "rationale_code": (
                        "J6_LOCAL_RESPONSE_PROCESSING_ERROR"
                    ),
                }

                record["stop"] = {
                    "triggered": True,
                    "reason": "LOCAL_RESPONSE_PROCESSING_ERROR",
                }

                record["evidence"]["error_class"] = "TypeError"
                record["evidence"]["error_detail"] = (
                    "Provider returned a non-ProviderResponse object"
                )

            else:
                # Preserve the provider-returned transport observation before
                # any local response validation or normalization occurs.
                record["provider"]["transport_status"] = (
                    response.transport_status
                )
                record["provider"]["resolved_model"] = (
                    response.resolved_model
                )

                # Preserve the received raw response before local validation.
                # If it cannot be canonically encoded, retain only an
                # attributable fallback representation. The fallback never
                # becomes trusted normalized evidence.
                try:
                    raw_hash = content_hash(response.raw_response)

                    record["evidence"]["raw_response_hash"] = (
                        raw_hash
                    )
                    record["evidence"]["raw_response"] = deepcopy(
                        response.raw_response
                    )

                except (TypeError, ValueError) as error:
                    raw_hash = None

                    try:
                        raw_repr = repr(response.raw_response)
                    except Exception as repr_error:
                        raw_repr = (
                            "<raw response representation failed: "
                            f"{type(repr_error).__name__}: "
                            f"{repr_error}>"
                        )

                    record["evidence"]["raw_response_repr"] = (
                        raw_repr
                    )
                    record["evidence"]["error_class"] = (
                        type(error).__name__
                    )
                    record["evidence"]["error_detail"] = str(error)

                if raw_hash is None:
                    # An unencodable response is already sufficient to stop.
                    # Do not attempt to normalize it into trusted evidence.
                    (
                        component_outcome,
                        rationale_code,
                        stop_triggered,
                        stop_reason,
                    ) = _live_component_result(
                        transport_status=response.transport_status,
                        response_contract_valid=False,
                        selected_label=None,
                        raw_response_hash=None,
                    )

                    record["live_component"] = {
                        "component_outcome": component_outcome,
                        "rationale_code": rationale_code,
                    }

                    record["stop"] = {
                        "triggered": stop_triggered,
                        "reason": stop_reason,
                    }

                else:
                    try:
                        live_validation = (
                            validate_j6_live_response(
                                response.raw_response,
                                requested_model=requested_model,
                                resolved_model=response.resolved_model,
                            )
                        )

                        record["validation"].update(
                            asdict(live_validation.validation)
                        )
                        record["validation"][
                            "response_contract_valid"
                        ] = (
                            live_validation.response_contract_valid
                        )

                        record["answer"] = deepcopy(
                            live_validation.answer
                        )

                        (
                            component_outcome,
                            rationale_code,
                            stop_triggered,
                            stop_reason,
                        ) = _live_component_result(
                            transport_status=(
                                response.transport_status
                            ),
                            response_contract_valid=(
                                live_validation.response_contract_valid
                            ),
                            selected_label=(
                                record["answer"]["selected_label"]
                            ),
                            raw_response_hash=raw_hash,
                        )

                        record["live_component"] = {
                            "component_outcome": component_outcome,
                            "rationale_code": rationale_code,
                        }

                        record["stop"] = {
                            "triggered": stop_triggered,
                            "reason": stop_reason,
                        }

                        if (
                            stop_triggered
                            and record["evidence"]["error_class"]
                            is None
                        ):
                            record["evidence"]["error_class"] = (
                                "J6LiveStopCondition"
                            )
                            record["evidence"]["error_detail"] = (
                                stop_reason
                            )

                    except Exception as error:
                        # The provider returned successfully. Preserve that
                        # observation and the already captured raw response.
                        # This is a local processing failure, not a provider
                        # execution failure.
                        record["live_component"] = {
                            "component_outcome": (
                                Outcome.INVALID_RESULT.value
                            ),
                            "rationale_code": (
                                "J6_LOCAL_RESPONSE_PROCESSING_ERROR"
                            ),
                        }

                        record["stop"] = {
                            "triggered": True,
                            "reason": (
                                "LOCAL_RESPONSE_PROCESSING_ERROR"
                            ),
                        }

                        record["evidence"]["error_class"] = (
                            type(error).__name__
                        )
                        record["evidence"]["error_detail"] = (
                            "LOCAL_RESPONSE_PROCESSING_ERROR: "
                            + str(error)
                        )

    finally:
        record["provider"]["latency_ms"] = (
            perf_counter() - start
        ) * 1000

    # No completed-result return path exists until atomic persistence succeeds.
    evidence_writer = (
        writer
        if writer is not None
        else AuditWriter(J6_LIVE_EVIDENCE_DIR)
    )

    evidence_path = evidence_writer.write(record)

    return J6CompletedLiveCase(
        record=record,
        evidence_path=evidence_path,
    )
