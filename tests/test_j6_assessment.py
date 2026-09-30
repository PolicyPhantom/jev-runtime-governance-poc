"""Offline regression tests for the frozen J6 v0.3 assessment semantics."""

from copy import deepcopy
import unittest
from unittest.mock import patch

from src.j6_assessment import (
    DecisionReconstructionStatus,
    PermissionApplicabilityStatus,
    assess_decision_reconstruction,
    assess_j6_fixture,
    assess_permission_applicability,
)
from src.j6_fixtures import load_j6_fixture


class J6CanonicalScenarioTests(unittest.TestCase):
    def test_r1_restoration_case_matches_frozen_expectation(self):
        fixture = load_j6_fixture("J6-PERM-R1")

        result = assess_j6_fixture(fixture)

        self.assertEqual(
            result.decision_reconstruction_status,
            DecisionReconstructionStatus.RECONSTRUCTED,
        )
        self.assertEqual(
            result.decision_reconstruction_reason_code,
            "DR_EVIDENCE_COMPLETE",
        )
        self.assertEqual(
            result.permission_applicability_status,
            PermissionApplicabilityStatus.NOT_SUPPORTED,
        )
        self.assertEqual(
            result.permission_reason_code,
            "PA_RESTORATION_CONDITION_UNMET",
        )

    def test_x1_restriction_case_matches_frozen_expectation(self):
        fixture = load_j6_fixture("J6-PERM-X1")

        result = assess_j6_fixture(fixture)

        self.assertEqual(
            result.decision_reconstruction_status,
            DecisionReconstructionStatus.RECONSTRUCTED,
        )
        self.assertEqual(
            result.decision_reconstruction_reason_code,
            "DR_EVIDENCE_COMPLETE",
        )
        self.assertEqual(
            result.permission_applicability_status,
            PermissionApplicabilityStatus.NOT_SUPPORTED,
        )
        self.assertEqual(
            result.permission_reason_code,
            "PA_EXPLICIT_EXCLUSION",
        )

    def test_x1_applied_rule_and_authority_remain_distinct(self):
        fixture = load_j6_fixture("J6-PERM-X1")

        self.assertNotEqual(
            fixture["applied_rule_reference"],
            fixture["authority_reference"],
        )

        status, reason = assess_decision_reconstruction(fixture)

        self.assertEqual(
            status,
            DecisionReconstructionStatus.RECONSTRUCTED,
        )
        self.assertEqual(reason, "DR_EVIDENCE_COMPLETE")


class J6PermissionBoundaryTests(unittest.TestCase):
    def test_missing_condition_evidence_is_indeterminate_not_denial(self):
        fixture = deepcopy(load_j6_fixture("J6-PERM-R1"))
        fixture["condition_evidence_references"] = []

        status, reason = assess_permission_applicability(fixture)

        self.assertEqual(
            status,
            PermissionApplicabilityStatus.INDETERMINATE,
        )
        self.assertEqual(
            reason,
            "PA_REQUIRED_CONDITION_EVIDENCE_MISSING",
        )

    def test_unresolved_exception_outranks_explicit_exclusion(self):
        fixture = deepcopy(load_j6_fixture("J6-PERM-X1"))
        fixture["permission_facts"]["exception_resolved"] = False

        status, reason = assess_permission_applicability(fixture)

        self.assertEqual(
            status,
            PermissionApplicabilityStatus.INDETERMINATE,
        )
        self.assertEqual(
            reason,
            "PA_EXCEPTION_UNRESOLVED",
        )

    def test_absence_of_affirmative_negative_evidence_is_indeterminate(self):
        fixture = deepcopy(load_j6_fixture("J6-PERM-R1"))

        fixture["permission_facts"]["unmet_necessary_conditions"] = []
        fixture["permission_facts"]["operative_restrictions"] = []
        fixture["permission_facts"]["explicit_exclusions"] = []
        fixture["permission_facts"][
            "all_necessary_permission_conditions_satisfied"
        ] = False

        status, reason = assess_permission_applicability(fixture)

        self.assertEqual(
            status,
            PermissionApplicabilityStatus.INDETERMINATE,
        )
        self.assertEqual(
            reason,
            "PA_REQUIRED_CONDITION_EVIDENCE_MISSING",
        )


class J6IdentityAndIndependenceTests(unittest.TestCase):
    def test_broken_fixture_identity_fails_closed(self):
        fixture = deepcopy(load_j6_fixture("J6-PERM-R1"))
        fixture["decision_result"] = "MUTATED_AFTER_FREEZE"

        result = assess_j6_fixture(fixture)

        self.assertEqual(
            result.decision_reconstruction_status,
            DecisionReconstructionStatus.INSUFFICIENT_EVIDENCE,
        )
        self.assertEqual(
            result.decision_reconstruction_reason_code,
            "DR_INTEGRITY_UNRESOLVED",
        )
        self.assertEqual(
            result.permission_applicability_status,
            PermissionApplicabilityStatus.INDETERMINATE,
        )
        self.assertEqual(
            result.permission_reason_code,
            "PA_REQUIRED_CONDITION_EVIDENCE_MISSING",
        )

    def test_expected_assessment_is_not_used_as_decision_input(self):
        fixture = deepcopy(load_j6_fixture("J6-PERM-R1"))

        fixture["expected_assessment"] = {
            "component_outcome": "INVALID_RESULT",
            "decision_reconstruction_status": "NOT_ASSESSED",
            "decision_reconstruction_reason_code": "DR_NOT_RUN",
            "permission_applicability_status": "SUPPORTED",
            "permission_reason_code": "PA_TERMS_SATISFIED",
        }

        with patch(
            "src.j6_assessment.j6_fixture_identity_valid",
            return_value=True,
        ):
            result = assess_j6_fixture(fixture)

        self.assertEqual(
            result.decision_reconstruction_status,
            DecisionReconstructionStatus.RECONSTRUCTED,
        )
        self.assertEqual(
            result.decision_reconstruction_reason_code,
            "DR_EVIDENCE_COMPLETE",
        )
        self.assertEqual(
            result.permission_applicability_status,
            PermissionApplicabilityStatus.NOT_SUPPORTED,
        )
        self.assertEqual(
            result.permission_reason_code,
            "PA_RESTORATION_CONDITION_UNMET",
        )


if __name__ == "__main__":
    unittest.main()