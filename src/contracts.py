"""Local choice adapter contract, not a claim about a live SDK wire format."""

import math
from dataclasses import dataclass
from typing import Any

from .models import JsonObject, LABELS


@dataclass(frozen=True)
class Validation:
    schema_status: str
    allowed_label_status: str
    probability_status: str
    confidence_status: str
    model_identity_status: str

    @property
    def valid(self) -> bool:
        return (
            self.schema_status == "VALID"
            and self.allowed_label_status == "VALID"
            and self.probability_status == "VALID"
            and self.confidence_status in {"VALID", "NULL", "ABSENT"}
            and self.model_identity_status == "MATCH"
        )


NOT_VALIDATED = Validation(*(["NOT_EVALUATED"] * 5))


def _unit_number(value: Any) -> bool:
    # Exclude bool, NaN, infinity, and oversized integers before float arithmetic.
    return (type(value) in (int, float) and 0 <= value <= 1
            and math.isfinite(value))


def validate(raw: object, requested_model: str, resolved_model: object) -> tuple[Validation, JsonObject]:
    data = raw if isinstance(raw, dict) else {}
    label = data.get("selected_label")
    label_valid = isinstance(label, str) and label in LABELS
    probabilities = data.get("probabilities")
    probability_valid = (
        isinstance(probabilities, dict)
        and set(probabilities) == set(LABELS)
        and all(_unit_number(value) for value in probabilities.values())
        and math.isclose(sum(probabilities.values()), 1.0, rel_tol=0, abs_tol=1e-9)
    )
    confidence = data.get("confidence")
    if "confidence" not in data:
        confidence_status = "ABSENT"
    elif confidence is None:
        confidence_status = "NULL"
    else:
        confidence_status = "VALID" if _unit_number(confidence) else "INVALID"
    model_status = (
        "MISSING" if not isinstance(resolved_model, str) or not resolved_model.strip()
        else "MATCH" if resolved_model == requested_model else "MISMATCH"
    )
    schema_valid = (
        isinstance(raw, dict) and data.get("primitive") == "choice"
        and isinstance(label, str) and "probabilities" in data
    )
    validation = Validation(
        "VALID" if schema_valid else "INVALID",
        "VALID" if label_valid else "INVALID",
        "VALID" if probability_valid else "INVALID",
        confidence_status, model_status,
    )
    # Invalid structures stay in the response hash, never in normalized fields.
    answer = {
        "selected_label": label if isinstance(label, str) else None,
        "probabilities": dict(probabilities) if probability_valid else None,
        "confidence_nullable": confidence if confidence_status == "VALID" else None,
    }
    return validation, answer
