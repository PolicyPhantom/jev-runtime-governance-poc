"""Bounded orchestration around the unchanged J3 harness, without retry."""

from copy import deepcopy
from dataclasses import dataclass
import json
from pathlib import Path
from uuid import uuid4

from .audit import AuditWriter, EVIDENCE_ROOT
from .fixtures import canonical_json, content_hash, load_fixture
from .harness import CompletedDecision, run
from .models import JsonObject, MOCK_MODEL
from .providers import Provider, ProviderRequest, ProviderResponse
from .repeatability_analysis import AnalysisOnlyProfile, provider_visible_content, summarize_repeat_group


MAX_REPEAT_COUNT = 1000  # Local workload bound, not a governance or model threshold.


class _ObservedProvider:
    def __init__(self, provider: Provider):
        self.provider = provider
        self.sdk_name = provider.sdk_name
        self.sdk_version = provider.sdk_version
        self.requests: list[JsonObject] = []

    def evaluate(self, request: ProviderRequest) -> ProviderResponse:
        content = provider_visible_content(request)
        identity = content_hash(content)
        self.requests.append({"provider_visible_request": content, "request_identity_hash": identity})
        return self.provider.evaluate(request)


class _DecisionWriter(AuditWriter):
    def __init__(self, writer: AuditWriter, observed: _ObservedProvider,
                 group_id: str, repeat_group: str | None, run_index: int, request_offset: int):
        super().__init__(writer.directory)
        self.writer = writer
        self.observed = observed
        self.tag = {"repeat_group_id": group_id, "repeat_group": repeat_group, "run_index": run_index}
        self.request_offset = request_offset

    def write(self, record: JsonObject) -> Path:
        requests = self.observed.requests[self.request_offset:]
        if len(requests) > 1:
            raise RuntimeError("Unexpected multiple provider requests in one logical decision")
        record["evidence"]["repeatability"] = {
            **self.tag,
            **deepcopy(requests[0] if requests else {
                "provider_visible_request": None, "request_identity_hash": None,
            }),
        }
        return self.writer.write(record)


@dataclass(frozen=True)
class CompletedRepeatGroup:
    summary: JsonObject
    decisions: tuple[CompletedDecision, ...]
    summary_path: Path


def run_repeatability(fixture_id: str, repeat_count: int, provider: Provider, *,
                      requested_model: str = MOCK_MODEL,
                      analysis_profile: AnalysisOnlyProfile = AnalysisOnlyProfile(),
                      writer: AuditWriter | None = None) -> CompletedRepeatGroup:
    if type(repeat_count) is not int or not 1 <= repeat_count <= MAX_REPEAT_COUNT:
        raise ValueError(f"repeat_count must be an integer in [1, {MAX_REPEAT_COUNT}]")
    if not isinstance(analysis_profile, AnalysisOnlyProfile):
        raise TypeError("An AnalysisOnlyProfile is required")
    fixture = load_fixture(fixture_id)
    serialized_fixture = canonical_json(fixture)
    group_id = str(uuid4())
    writer = writer if writer is not None else AuditWriter()
    observed = _ObservedProvider(provider)
    decisions = []
    for index in range(1, repeat_count + 1):
        decision_writer = _DecisionWriter(writer, observed, group_id, fixture["repeat_group"],
                                          index, len(observed.requests))
        # A new logical decision is not a retry; identical serialized input is reused.
        decision = run(json.loads(serialized_fixture), observed, writer=decision_writer,
                       requested_model=requested_model)
        decisions.append(decision)
    # Analysis sees completed records only; the profile never reaches run() or gate.
    summary = summarize_repeat_group([decision.record for decision in decisions], analysis_profile)
    summary["decision_evidence_paths"] = [
        decision.evidence_path.relative_to(EVIDENCE_ROOT).as_posix() for decision in decisions
    ]
    summary_path = writer.write(summary)
    return CompletedRepeatGroup(summary, tuple(decisions), summary_path)
