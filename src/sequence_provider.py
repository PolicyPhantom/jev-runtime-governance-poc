"""Offline J5 test instrument; a script is not a model simulation."""

from collections.abc import Sequence
from copy import deepcopy

from .providers import ProviderRequest, ProviderResponse


class SequenceExhaustedError(RuntimeError):
    """There is no next scripted response; no looping or fallback is permitted."""


class ScriptedSequenceProvider:
    sdk_name = "standard-library-offline-scripted-sequence"
    sdk_version = "j5-v0.1"

    def __init__(self, responses: Sequence[ProviderResponse]):
        self._responses = tuple(deepcopy(responses))
        self.evaluate_calls = 0
        self.consumed_count = 0

    def evaluate(self, request: ProviderRequest) -> ProviderResponse:
        # The request is intentionally never inspected.
        self.evaluate_calls += 1
        if self.consumed_count >= len(self._responses):
            raise SequenceExhaustedError("Offline scripted response sequence exhausted")
        response = self._responses[self.consumed_count]
        self.consumed_count += 1
        return deepcopy(response)
