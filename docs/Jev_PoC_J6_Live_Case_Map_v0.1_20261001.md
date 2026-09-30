# Jev PoC J6 Live Case Map v0.1

**Status:** PRE-LIVE CASE BINDING
**Date:** 2026-10-01 JST
**J6 Specification Baseline:** v0.3 FROZEN
**Implementation Baseline:** commit `2c344ef`

---

## 1. Purpose

This document binds each approved J6 live scenario to one existing frozen semantic source fixture.

It does not modify the frozen J6 permission fixtures.

It does not modify the frozen J0-J2 semantic fixtures.

It does not define expected live provider outputs.

---

## 2. Case Binding

```text
J6-PERM-R1
→ provider semantic source fixture: F-01

J6-PERM-X1
→ provider semantic source fixture: F-02

3. Binding Rationale
J6-PERM-R1 → F-01
F-01 provides a clean synthetic remediation-evidence case whose frozen semantic expectation is substantively sufficient.
This pairing is useful for observing whether a live component result can remain distinct from permission restoration.
The intended governance distinction is:
technical remediation support
!= permission restoration

No live outcome is guaranteed.
J6-PERM-X1 → F-02
F-02 provides a clean synthetic remediation-evidence case whose frozen semantic expectation is non-sufficient.
This pairing is useful for observing that component outcome and permission applicability remain separate dimensions.
The intended governance distinction is:
semantic component result
!= permission applicability

No live outcome is guaranteed.
4. Identity Separation
The runtime evidence must preserve both identities separately.
Example:
j6_scenario_id
provider_source_fixture_id

For R1:
j6_scenario_id = J6-PERM-R1
provider_source_fixture_id = F-01

For X1:
j6_scenario_id = J6-PERM-X1
provider_source_fixture_id = F-02

The source fixture identity must not replace the J6 scenario identity.
The J6 scenario identity must not replace the provider source fixture identity.
5. Frozen Expectation vs Live Observation
The following must remain distinct:
frozen semantic expectation
!= live observed provider result
!= permission applicability result

A live result that differs from the frozen semantic expectation is retained as an observation.
It does not authorize modification of:
- J6 Specification v0.3
- J6-PERM-R1
- J6-PERM-X1
- F-01
- F-02
6. Live Result Handling
Examples:
F-01 live result = SEMANTIC_CHECK_PASS
J6-PERM-R1 permission = NOT_SUPPORTED

is a valid cross-layer combination.
Likewise:
F-02 live result = SEMANTIC_CHECK_HOLD
J6-PERM-X1 permission = NOT_SUPPORTED

is also a valid cross-layer combination.
Unexpected combinations are preserved as evidence rather than patched away.
7. Scope Boundary
This case map does not authorize:
- additional semantic source fixtures
- repeatability runs
- adversarial source substitution
- exploratory provider calls
- extra J6 scenarios
Any change to the case binding requires Human Review.
8. Approved Live Call Mapping
Call 1
J6-PERM-R1
→ F-01

Call 2
J6-PERM-X1
→ F-02

Execution remains subject to the separate J6 Live Execution Plan v0.1 and final live Human Gate.
END OF J6 LIVE CASE MAP v0.1
