"""One deterministic decision, at most one provider attempt, one audit record."""

from copy import deepcopy
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from .audit import AuditWriter
from .contracts import NOT_VALIDATED, validate
from .fixtures import content_hash
from .gate import decide
from .models import JsonObject, MOCK_MODEL
from .precheck import check
from .providers import Provider, ProviderRequest, ProviderResponse


@dataclass(frozen=True)
class CompletedDecision:
    record: JsonObject
    evidence_path: Path


def run(fixture: JsonObject, provider: Provider | None, *,
        writer: AuditWriter | None = None,
        requested_model: str = MOCK_MODEL) -> CompletedDecision:
    fixture = deepcopy(fixture)
    precheck = check(fixture)
    state = {key: fixture.get(key) for key in (
        "suspension_cause", "required_evidence", "submitted_evidence", "deterministic_flags")}
    question = fixture.get("semantic_question")
    record: JsonObject = {
        "logical_decision_id": str(uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "fixture": {
            "fixture_id": fixture.get("fixture_id"),
            "fixture_version": fixture.get("version"),
            "fixture_hash": content_hash(fixture),
        },
        "input": {
            "state_hash": content_hash(state), "question_hash": content_hash(question),
            "policy_profile_id": "Jev_PoC_J0-J2_Integrated_Baseline_v0.1_20260926",
        },
        "precheck": asdict(precheck),
        "request": {
            "primitive": "choice", "requested_model": requested_model,
            "sdk_name": None, "sdk_version": None,
            "retry_policy": {"enabled": False, "max_attempts": 1},
            "timeout": None,
        },
        "provider": {
            "transport_status": "NOT_CALLED", "resolved_model": None,
            "attempt_count": 0, "latency_ms": None,
        },
        "answer": {"selected_label": None, "probabilities": None, "confidence_nullable": None},
        "validation": asdict(NOT_VALIDATED),
        "evidence": {"raw_response_hash": None, "error_class": None, "error_detail": None},
    }
    validation = NOT_VALIDATED
    provider_valid = False
    contract_encoding_failed = False
    if precheck.result == "PASS":
        if provider is None:
            record["provider"]["transport_status"] = "UNAVAILABLE"
            record["evidence"].update(error_class="ProviderUnavailable", error_detail="No provider supplied")
        else:
            start = perf_counter()
            try:
                record["request"].update(sdk_name=provider.sdk_name, sdk_version=provider.sdk_version)
                # Expectations, notes, bands, flags, and repeat groups are not semantic input.
                semantic_state = {key: deepcopy(state[key]) for key in (
                    "suspension_cause", "required_evidence", "submitted_evidence")}
                request = ProviderRequest(semantic_state, question, requested_model)
                record["provider"]["attempt_count"] = 1
                response = provider.evaluate(request)
                if not isinstance(response, ProviderResponse):
                    raise TypeError("Provider must return ProviderResponse")
                record["provider"].update(
                    transport_status=response.transport_status,
                    resolved_model=response.resolved_model,
                )
                validation, answer = validate(response.raw_response, requested_model, response.resolved_model)
                record["validation"] = asdict(validation)
                record["answer"] = answer
                try:
                    record["evidence"]["raw_response_hash"] = content_hash(response.raw_response)
                except (ValueError, TypeError) as error:
                    # Preserve J3/J4's encoding-rejection classification without
                    # treating a response that failed processing as successful.
                    contract_encoding_failed = response.transport_status == "OK"
                    validation = replace(validation, schema_status="INVALID")
                    record["validation"] = asdict(validation)
                    record["evidence"].update(error_class=type(error).__name__, error_detail=str(error))
                if (response.transport_status != "OK" or not validation.valid) and record["evidence"]["error_class"] is None:
                    record["evidence"].update(
                        error_class="ContractInvalid" if response.transport_status == "OK" else "ProviderResultInvalid",
                        error_detail="Provider result did not satisfy the controlled choice contract",
                    )
                # Success becomes authoritative only after required processing.
                provider_valid = (response.transport_status == "OK"
                                  and record["evidence"]["raw_response_hash"] is not None)
            except Exception as error:
                provider_valid = False
                contract_encoding_failed = False
                if validation != NOT_VALIDATED:
                    validation = replace(validation, schema_status="INVALID")
                record["validation"] = asdict(validation)
                record["provider"]["transport_status"] = "ERROR"
                record["evidence"].update(error_class=type(error).__name__, error_detail=str(error))
            finally:
                record["provider"]["latency_ms"] = (perf_counter() - start) * 1000
    gate = decide(precheck, validation, record["answer"]["selected_label"], provider_valid,
                  contract_encoding_failed=contract_encoding_failed)
    record["component_gate"] = asdict(gate)
    # There is no completed-result return path until persistence succeeds.
    evidence_path = (writer if writer is not None else AuditWriter()).write(record)
    return CompletedDecision(record, evidence_path)
