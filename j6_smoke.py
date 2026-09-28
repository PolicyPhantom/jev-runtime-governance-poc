import os
from importlib.metadata import version

from typesafe_sdk import Choice, RetryPolicy, TypeSafeClient

from src.contracts import Validation
from src.fixtures import load_fixture
from src.harness import run
from src.providers import ProviderResponse


class LiveJevProvider:
    sdk_name = "typesafe-sdk"
    sdk_version = version("typesafe-sdk")

    def __init__(self):
        retry = RetryPolicy(max_retries=0)
        self.client = TypeSafeClient(
            api_key=os.environ["TYPESAFE_API_KEY"],
            model="jev-latest",
            retry=retry,
        )

    def evaluate(self, request):
        response = self.client.system_one(
            state=request.state,
            questions={
                "assessment": Choice(
                    instructions=request.semantic_question,
                    criteria={
                        label: None
                        for label in request.allowed_labels
                    },
                )
            },
            model=request.requested_model,
            retry=RetryPolicy(max_retries=0),
        )

        answer = response.answers["assessment"]

        raw = {
            "primitive": "choice",
            "selected_label": answer.choice,
            "probabilities": dict(answer.probabilities),
            "confidence": answer.confidence,
        }

        return ProviderResponse(
            raw_response=raw,
            resolved_model=response.model,
        )

    def close(self):
        self.client.close()


provider = LiveJevProvider()

try:
    decision = run(
        load_fixture("F-01"),
        provider,
        requested_model="jev-latest",
    )

    record = decision.record

    print("J6_SMOKE_RESULT")
    print("EVIDENCE_PATH=" + str(decision.evidence_path))
    print("TRANSPORT=" + str(record["provider"]["transport_status"]))
    print("ATTEMPT_COUNT=" + str(record["provider"]["attempt_count"]))
    print("REQUESTED_MODEL=" + str(record["request"]["requested_model"]))
    print("RESOLVED_MODEL=" + str(record["provider"]["resolved_model"]))
    print("SELECTED_LABEL=" + str(record["answer"]["selected_label"]))
    print("CONFIDENCE=" + str(record["answer"]["confidence_nullable"]))
    print(
        "VALIDATION_VALID="
        + str(Validation(**record["validation"]).valid)
    )
    print(
        "COMPONENT_OUTCOME="
        + str(record["component_gate"]["component_outcome"])
    )
    print(
        "RATIONALE="
        + str(record["component_gate"]["rationale_code"])
    )
    print(
        "RAW_RESPONSE_HASH="
        + str(record["evidence"]["raw_response_hash"])
    )
    print(
        "ERROR_CLASS="
        + str(record["evidence"]["error_class"])
    )
    print(
        "ERROR_DETAIL="
        + str(record["evidence"]["error_detail"])
    )

finally:
    provider.close()