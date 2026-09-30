"""J6 live-response validation with model identity kept as observation.

J3-J5 intentionally require requested/resolved model identity equality as part
of their frozen component contract. J6 does not modify that contract.

Instead, J6 reuses the existing field-level validation while evaluating
response-contract validity independently from model-identity equality.
"""

from dataclasses import dataclass

from .contracts import Validation, validate
from .models import JsonObject


@dataclass(frozen=True)
class J6LiveValidation:
    validation: Validation
    answer: JsonObject
    response_contract_valid: bool

    @property
    def model_identity_status(self) -> str:
        return self.validation.model_identity_status


def j6_response_contract_valid(validation: Validation) -> bool:
    """Return J6 response validity without using model equality as a gate.

    J6 requires the choice response structure, allowed label, probability
    vector, and confidence representation to satisfy the existing local
    contract.

    requested_model/resolved_model identity remains separately retained as
    provider-attributed observation and does not by itself invalidate the
    response.
    """
    return (
        validation.schema_status == "VALID"
        and validation.allowed_label_status == "VALID"
        and validation.probability_status == "VALID"
        and validation.confidence_status in {"VALID", "NULL", "ABSENT"}
    )


def validate_j6_live_response(
    raw: object,
    requested_model: str,
    resolved_model: object,
) -> J6LiveValidation:
    """Validate a live J6 response while preserving identity observation."""
    validation, answer = validate(
        raw,
        requested_model,
        resolved_model,
    )

    return J6LiveValidation(
        validation=validation,
        answer=answer,
        response_contract_valid=j6_response_contract_valid(validation),
    )