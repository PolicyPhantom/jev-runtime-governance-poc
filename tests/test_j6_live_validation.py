"""Offline tests for J6 live-response validation semantics."""

import unittest

from src.j6_live_validation import validate_j6_live_response


def valid_choice_response():
    return {
        "primitive": "choice",
        "selected_label": "SUFFICIENT",
        "probabilities": {
            "SUFFICIENT": 0.87,
            "INSUFFICIENT": 0.10,
            "CONFLICTING": 0.00,
            "UNCERTAIN": 0.03,
        },
        "confidence": 0.81,
    }


class J6LiveValidationTests(unittest.TestCase):
    def test_matching_model_identity_is_valid_observation(self):
        result = validate_j6_live_response(
            valid_choice_response(),
            requested_model="jev-1.13.0",
            resolved_model="jev-1.13.0",
        )

        self.assertTrue(result.response_contract_valid)
        self.assertEqual(result.model_identity_status, "MATCH")
        self.assertTrue(result.validation.valid)

    def test_model_identity_mismatch_does_not_invalidate_j6_response_contract(self):
        result = validate_j6_live_response(
            valid_choice_response(),
            requested_model="jev-latest",
            resolved_model="jev-1.13.0",
        )

        self.assertTrue(result.response_contract_valid)
        self.assertEqual(result.model_identity_status, "MISMATCH")

        # Existing J3-J5 contract remains strict.
        self.assertFalse(result.validation.valid)

    def test_missing_resolved_model_remains_separate_identity_observation(self):
        result = validate_j6_live_response(
            valid_choice_response(),
            requested_model="jev-latest",
            resolved_model=None,
        )

        self.assertTrue(result.response_contract_valid)
        self.assertEqual(result.model_identity_status, "MISSING")

        # Existing frozen contract still treats missing identity as invalid.
        self.assertFalse(result.validation.valid)

    def test_invalid_probability_vector_invalidates_j6_response_contract(self):
        raw = valid_choice_response()
        raw["probabilities"] = {
            "SUFFICIENT": 0.90,
            "INSUFFICIENT": 0.20,
            "CONFLICTING": 0.00,
            "UNCERTAIN": 0.00,
        }

        result = validate_j6_live_response(
            raw,
            requested_model="jev-latest",
            resolved_model="jev-1.13.0",
        )

        self.assertFalse(result.response_contract_valid)
        self.assertEqual(
            result.validation.probability_status,
            "INVALID",
        )

    def test_unknown_label_invalidates_j6_response_contract(self):
        raw = valid_choice_response()
        raw["selected_label"] = "ALLOW"

        result = validate_j6_live_response(
            raw,
            requested_model="jev-latest",
            resolved_model="jev-1.13.0",
        )

        self.assertFalse(result.response_contract_valid)
        self.assertEqual(
            result.validation.allowed_label_status,
            "INVALID",
        )


if __name__ == "__main__":
    unittest.main()