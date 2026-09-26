"""Shared component vocabulary; none of these outcomes grants permission."""

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any


class Label(StrEnum):
    SUFFICIENT = "SUFFICIENT"
    INSUFFICIENT = "INSUFFICIENT"
    CONFLICTING = "CONFLICTING"
    UNCERTAIN = "UNCERTAIN"


class Outcome(StrEnum):
    SEMANTIC_CHECK_PASS = "SEMANTIC_CHECK_PASS"
    SEMANTIC_CHECK_HOLD = "SEMANTIC_CHECK_HOLD"
    DETERMINISTIC_DENY = "DETERMINISTIC_DENY"
    NOT_EVALUATED = "NOT_EVALUATED"
    INVALID_RESULT = "INVALID_RESULT"


PROJECT_ROOT = Path(__file__).resolve().parent.parent
LABELS = tuple(label.value for label in Label)
MOCK_MODEL = "mock-choice-v0.1"
JsonObject = dict[str, Any]


@dataclass(frozen=True)
class Precheck:
    schema_valid: bool
    required_fields_present: bool
    identity_binding_valid: bool | str
    integrity_valid: bool
    prohibited: bool
    fixture_identity_valid: bool
    required_evidence_present: bool
    result: str
    rationale_code: str


@dataclass(frozen=True)
class GateResult:
    semantic_signal: str | None
    component_outcome: Outcome
    rationale_code: str
