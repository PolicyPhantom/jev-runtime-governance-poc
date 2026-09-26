"""Provider boundary only: J3 implements no Jev or failure provider."""

from copy import deepcopy
from dataclasses import dataclass
from typing import Protocol

from .models import JsonObject, LABELS, MOCK_MODEL


@dataclass(frozen=True)
class ProviderRequest:
    state: JsonObject
    semantic_question: str
    requested_model: str
    primitive: str = "choice"
    allowed_labels: tuple[str, ...] = LABELS


@dataclass(frozen=True)
class ProviderResponse:
    raw_response: object
    resolved_model: str | None
    transport_status: str = "OK"


class Provider(Protocol):
    sdk_name: str
    sdk_version: str

    def evaluate(self, request: ProviderRequest) -> ProviderResponse: ...


class MockProvider:
    """Returns a caller-supplied response, without interpreting any evidence."""

    sdk_name = "standard-library-mock"
    sdk_version = "j3-v0.1"

    def __init__(self, raw_response: object, resolved_model: str | None = MOCK_MODEL):
        self._raw_response = deepcopy(raw_response)
        self._resolved_model = resolved_model

    def evaluate(self, request: ProviderRequest) -> ProviderResponse:
        return ProviderResponse(deepcopy(self._raw_response), self._resolved_model)


def mock_choice(label: str) -> JsonObject:
    """Create an explicitly scripted response; this does not assess a fixture."""
    if label not in LABELS:
        raise ValueError("The scripted mock label must be an allowed choice")
    return {
        "primitive": "choice",
        "selected_label": label,
        "probabilities": {item: float(item == label) for item in LABELS},
        "confidence": None,
    }
