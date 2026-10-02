from src.j6_live_provider import LiveJevProvider
from src.j6_live_runner import run_j6_live_case


def main():
    provider = LiveJevProvider()

    try:
        decision = run_j6_live_case(
            "J6-PERM-X1",
            provider,
            requested_model="jev-latest",
        )

        record = decision.record

        print("J6_LIVE_X1_RESULT")
        print("EVIDENCE_PATH=" + str(decision.evidence_path))
        print(
            "SCENARIO="
            + str(record["live_case"]["j6_scenario_id"])
        )
        print(
            "SOURCE_FIXTURE="
            + str(record["live_case"]["provider_source_fixture_id"])
        )
        print(
            "TRANSPORT="
            + str(record["provider"]["transport_status"])
        )
        print(
            "ATTEMPT_COUNT="
            + str(record["provider"]["attempt_count"])
        )
        print(
            "REQUESTED_MODEL="
            + str(record["request"]["requested_model"])
        )
        print(
            "RESOLVED_MODEL="
            + str(record["provider"]["resolved_model"])
        )
        print(
            "SELECTED_LABEL="
            + str(record["answer"]["selected_label"])
        )
        print(
            "RESPONSE_CONTRACT_VALID="
            + str(record["validation"]["response_contract_valid"])
        )
        print(
            "MODEL_IDENTITY_STATUS="
            + str(record["validation"]["model_identity_status"])
        )
        print(
            "LIVE_COMPONENT_OUTCOME="
            + str(record["live_component"]["component_outcome"])
        )
        print(
            "LIVE_COMPONENT_RATIONALE="
            + str(record["live_component"]["rationale_code"])
        )
        print(
            "DECISION_RECONSTRUCTION="
            + str(
                record["frozen_j6_assessment"][
                    "decision_reconstruction_status"
                ]
            )
        )
        print(
            "PERMISSION_APPLICABILITY="
            + str(
                record["frozen_j6_assessment"][
                    "permission_applicability_status"
                ]
            )
        )
        print(
            "STOP_TRIGGERED="
            + str(record["stop"]["triggered"])
        )
        print(
            "STOP_REASON="
            + str(record["stop"]["reason"])
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


if __name__ == "__main__":
    main()