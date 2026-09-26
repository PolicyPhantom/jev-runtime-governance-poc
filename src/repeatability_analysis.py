"""Descriptive offline analysis, with no dependency on the component gate."""

from collections.abc import Sequence
from copy import deepcopy
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import math
from statistics import fmean

from .contracts import Validation
from .fixtures import content_hash
from .models import JsonObject, LABELS
from .providers import ProviderRequest


@dataclass(frozen=True)
class AnalysisOnlyProfile:
    """Observation cutoffs only: not governance, permission, or calibration."""

    profile_id: str = "analysis-demo-v0.1"
    selected_label_probability_threshold: float = 0.70
    confidence_threshold: float = 0.70

    def __post_init__(self) -> None:
        if not isinstance(self.profile_id, str) or not self.profile_id.strip():
            raise ValueError("An analysis-only profile ID is required")
        for value in (self.selected_label_probability_threshold, self.confidence_threshold):
            if type(value) not in (int, float) or not 0 <= value <= 1 or not math.isfinite(value):
                raise ValueError("Analysis-only thresholds must be finite numbers in [0, 1]")


def provider_visible_content(request: ProviderRequest) -> JsonObject:
    """Exactly the five fields exposed to the provider, without audit metadata."""
    return deepcopy({
        "state": request.state,
        "semantic_question": request.semantic_question,
        "requested_model": request.requested_model,
        "primitive": request.primitive,
        "allowed_labels": list(request.allowed_labels),
    })


def request_identity_hash(request: ProviderRequest) -> str:
    return content_hash(provider_visible_content(request))


def _sequence_summary(values: list) -> JsonObject:
    unique = []
    for value in values:
        if value not in unique:
            unique.append(value)
    return {
        "sequence": values,
        "unique": unique,
        "switches": sum(left != right for left, right in zip(values, values[1:])),
    }


def _numeric_summary(values: list[float]) -> JsonObject | None:
    if not values:
        return None
    return {"count": len(values), "min": min(values), "max": max(values),
            "range": max(values) - min(values), "mean": fmean(values)}


def analysis_only_crossings(field: str, values: Sequence[float | None], threshold: float) -> list[JsonObject]:
    """Compare adjacent numeric runs; equality belongs to the upper side.

    Missing/null observations break adjacency; they are not zero or interpolated.
    Run indices are one-based. These observations never feed the gate.
    """
    crossings = []
    for index, (left, right) in enumerate(zip(values, values[1:]), start=1):
        if left is None or right is None or (left >= threshold) == (right >= threshold):
            continue
        crossings.append({
            "field": field, "run_indices": [index, index + 1],
            "values": [left, right], "direction": "UP" if right > left else "DOWN",
        })
    return crossings


def summarize_repeat_group(records: Sequence[JsonObject],
                           analysis_profile: AnalysisOnlyProfile = AnalysisOnlyProfile()) -> JsonObject:
    """Retain raw observations; suppress derived statistics for invalid groups.

    Only already-persisted decision records should be supplied by the runner.
    This function neither writes evidence nor modifies any decision outcome.
    """
    if not records:
        raise ValueError("A repeat group must contain at least one decision")
    records = deepcopy(list(records))
    tags = [record["evidence"]["repeatability"] for record in records]
    group_id = tags[0]["repeat_group_id"]
    hashes = [tag["request_identity_hash"] for tag in tags]
    attempts = [record["provider"]["attempt_count"] for record in records]
    reasons: list[str] = []

    def invalidate(reason: str) -> None:
        if reason not in reasons:
            reasons.append(reason)

    decision_ids = [record["logical_decision_id"] for record in records]
    if len(set(decision_ids)) != len(records):
        invalidate("DUPLICATE_DECISION_ID")
    for index, (record, tag) in enumerate(zip(records, tags), start=1):
        if (tag["repeat_group_id"] != group_id or tag["repeat_group"] != tags[0]["repeat_group"]
                or tag["run_index"] != index):
            invalidate("GROUP_MEMBERSHIP_MISMATCH")
        if not record["precheck"]["schema_valid"] or not record["precheck"]["fixture_identity_valid"]:
            invalidate("FIXTURE_NOT_VERIFIED")
        if record["request"]["retry_policy"] != {"enabled": False, "max_attempts": 1} or attempts[index - 1] > 1:
            invalidate("RETRY_INVARIANT_VIOLATION")
        request = tag["provider_visible_request"]
        if attempts[index - 1] == 1:
            if request is None or tag["request_identity_hash"] != content_hash(request):
                invalidate("REQUEST_IDENTITY_NOT_VERIFIED")
        elif request is not None or tag["request_identity_hash"] is not None:
            invalidate("UNEXPECTED_PROVIDER_REQUEST")

    # Excludes decision IDs, clocks, latency, and evidence paths.
    input_signatures = [content_hash({
        "fixture": record["fixture"], "input": record["input"], "request": record["request"],
    }) for record in records]
    if len(set(input_signatures)) != 1:
        invalidate("INPUT_OR_POLICY_DRIFT")
    if len(set(hashes)) != 1:
        invalidate("REQUEST_IDENTITY_DRIFT")
    bypass = all(record["precheck"]["result"] != "PASS" for record in records)
    if bypass:
        if any(attempts):
            invalidate("BYPASS_PROVIDER_CALL")
    else:
        if any(record["precheck"]["result"] != "PASS" for record in records):
            invalidate("PRECHECK_PATH_DRIFT")
        if any(count != 1 for count in attempts):
            invalidate("MISSING_PROVIDER_ATTEMPT")
        if any(not Validation(**record["validation"]).valid for record in records):
            invalidate("INVALID_CONTRACT_RESULT")
        if any(record["provider"]["transport_status"] != "OK" for record in records):
            invalidate("INVALID_PROVIDER_RESULT")
        if any(record["validation"]["model_identity_status"] != "MATCH" for record in records):
            invalidate("MODEL_IDENTITY_INCOMPATIBILITY")
        if any(record["component_gate"]["component_outcome"] not in {
            "SEMANTIC_CHECK_PASS", "SEMANTIC_CHECK_HOLD",
        } for record in records):
            invalidate("NON_SEMANTIC_DECISION")

    validity = "INVALID" if reasons else "EXCLUDED_DETERMINISTIC_BYPASS" if bypass else "VALID"
    labels = [record["answer"]["selected_label"] for record in records]
    vectors = [record["answer"]["probabilities"] for record in records]
    confidence = [record["answer"]["confidence_nullable"] for record in records]
    confidence_statuses = [record["validation"]["confidence_status"] for record in records]
    models = [record["provider"]["resolved_model"] for record in records]
    outcomes = [record["component_gate"]["component_outcome"] for record in records]
    summary: JsonObject = {
        "record_type": "repeatability_group",
        "logical_decision_id": group_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "analysis_scope": "offline repeatability observation machinery",
        "claim_boundary": "offline scripted sequence only",
        "repeat_group_id": group_id,
        "repeat_group": tags[0]["repeat_group"],
        **records[0]["fixture"],
        "request_identity_hash": hashes[0] if len(set(hashes)) == 1 else None,
        "request_identity_hashes": hashes,
        "repeat_group_validity": validity,
        "invalidation_reasons": reasons,
        "run_count": len(records),
        "decision_ids": decision_ids,
        "selected_labels": labels,
        "probability_vectors": vectors,
        "confidence_values": confidence,
        "confidence_statuses": confidence_statuses,
        "resolved_models": models,
        "component_outcome_sequence": outcomes,
        "contract_statuses": [record["validation"] for record in records],
        "attempt_counts": attempts,
        "latencies_ms": [record["provider"]["latency_ms"] for record in records],
        "analysis_profile": asdict(analysis_profile),
        "labels": None,
        "probabilities": None,
        "confidence": {"presence_status": confidence_statuses, "values": confidence, "statistics": None},
        "models": None,
        "component_outcomes": None,
        "attempts": {"per_run": attempts, "max": max(attempts)},
        "threshold_observations": [],
        "threshold_crossings": [],
    }
    # With stable inputs, expose output incompatibility diagnostics. These are
    # observations of invalid decisions, not a valid model-repeatability series.
    output_reasons = {"INVALID_CONTRACT_RESULT", "INVALID_PROVIDER_RESULT",
                      "MODEL_IDENTITY_INCOMPATIBILITY", "NON_SEMANTIC_DECISION"}
    if not bypass and set(reasons).issubset(output_reasons):
        summary["models"] = {"requested": records[0]["request"]["requested_model"],
                             **_sequence_summary(models)}
        summary["component_outcomes"] = _sequence_summary(outcomes)
    if validity == "VALID":
        summary["labels"] = _sequence_summary(labels)
        summary["probabilities"] = {label: _numeric_summary([vector[label] for vector in vectors])
                                    for label in LABELS}
        summary["confidence"]["statistics"] = _numeric_summary([
            value for value, status in zip(confidence, confidence_statuses) if status == "VALID"
        ])
        crossings = analysis_only_crossings(
            "selected_label_probability", [vector[label] for vector, label in zip(vectors, labels)],
            analysis_profile.selected_label_probability_threshold,
        ) + analysis_only_crossings("confidence", confidence, analysis_profile.confidence_threshold)
        summary["threshold_observations"] = crossings
        summary["threshold_crossings"] = deepcopy(crossings)
    return summary
