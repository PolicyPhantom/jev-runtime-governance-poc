"""J4-only offline injection; no request inspection, transport, or retry logic."""

from copy import deepcopy
import json
from typing import cast

from .providers import ProviderRequest, ProviderResponse


class SimulatedConnectionError(ConnectionError):
    """A local connection-like failure, without opening a connection."""


class SimulatedTimeoutError(TimeoutError):
    """A local timeout-like failure, without waiting for a deadline."""


class SimulatedHTTPError(RuntimeError):
    """Simulation metadata is carried in the existing audit error detail."""

    def __init__(self, status: int):
        if status not in {408, 429, 500, 503}:
            raise ValueError("HTTP simulation is limited to the frozen J4 status set")
        super().__init__(json.dumps({
            "simulated": True,
            "failure_kind": "http_status",
            "http_status": status,
            "provider_exception_class": type(self).__name__,
        }, sort_keys=True))


class FailureProvider:
    """Raise the supplied local exception or return the supplied invalid result.

    Only the injected behavior is configured. The request is never read.
    The cast deliberately allows JF-07 to violate the provider return contract;
    the existing harness, rather than this injector, detects that violation.
    """

    sdk_name = "standard-library-offline-failure-simulation"
    sdk_version = "j4-v0.1"

    def __init__(self, result: object = None, *, error: Exception | None = None):
        if result is not None and error is not None:
            raise ValueError("Choose one injected return or exception behavior")
        self._result = deepcopy(result)
        self._error = error
        self.evaluate_calls = 0

    def evaluate(self, request: ProviderRequest) -> ProviderResponse:
        self.evaluate_calls += 1
        if self._error is not None:
            raise self._error
        return cast(ProviderResponse, deepcopy(self._result))
