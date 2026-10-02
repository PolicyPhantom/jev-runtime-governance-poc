import os
from importlib.metadata import version

from typesafe_sdk import Choice, RetryPolicy, TypeSafeClient

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