# Jev PoC J6 Live Execution Plan v0.1

**Status:** PRE-LIVE EXECUTION PLAN
**Date:** 2026-10-01 JST
**Specification Baseline:** J6 Specification v0.3 (FROZEN)
**Implementation Baseline:** commit `2c344ef`

---

## 1. Purpose

This plan defines the bounded live-execution conditions for J6.

The live phase is intended to connect the frozen J6 v0.3 governance semantics to live Jev provider responses.

It is not a repeatability study, benchmarking study, or open-ended exploratory evaluation.

---

## 2. Live Call Budget

Maximum live semantic calls:

```text
2

Allocation:
J6-PERM-R1
→ at most 1 live call

J6-PERM-X1
→ at most 1 live call

Retry policy:
retry = 0

No automatic retry is permitted.
No repeatability sweep is permitted.
No exploratory extra call is permitted.
A second call is performed only if the first approved live call completes without a STOP condition.
3. Input Scope
Only synthetic J6 research inputs are permitted.
The live phase must not use:
production data
customer data
sensitive data
operational data

The frozen J6 specification and frozen J6 fixture identities must not be modified to accommodate provider behaviour.
Unexpected provider behaviour is retained as an observation against the frozen baseline.
4. Provider and Model Reference
Provider:
Jev / TypeSafe

Requested model reference:
jev-latest

The live record must retain both:
requested_model
resolved_model

when the provider supplies a resolved model identity.
A requested/resolved identity difference:
requested_model != resolved_model

does not by itself establish:
implementation drift
material change
permission failure
provider fault

Provider-reported identity is attributed evidence and is not independently verified execution proof.
5. Evidence to Retain
For each live call, retain at least:
scenario / fixture identity
decision identifier
call sequence number
requested model
provider-reported resolved model
transport result
attempt count
selected label
probabilities when supplied
confidence when supplied
raw provider response or attributable raw-response representation
response hash where available
contract / schema validation result
component outcome
decision reconstruction result
permission applicability result
reason codes
evidence persistence result
timestamp

Provider result validity, decision reconstructability, and permission applicability must remain separate.
6. J6 Semantic Boundaries
The following conversions are prohibited:
SEMANTIC_CHECK_PASS
→ permission SUPPORTED

RECONSTRUCTED
→ permission SUPPORTED

permission SUPPORTED
→ provider result automatically accepted

The live phase does not modify the frozen J6 precedence rules.
Missing or unresolved claim-critical permission evidence must not become NOT_SUPPORTED.
7. Timing Boundary
The J6 live mechanism remains:
post-response admissibility determination

The live phase does not claim to have demonstrated:
prevention of provider inference
prevention of data transmission
prevention of provider routing or fallback
remote cancellation
pre-execution enforcement

A post-response rejection cannot retroactively prevent processing that has already occurred.
8. STOP Conditions
Execution must STOP immediately if any of the following occurs:
unexpected additional provider call
automatic retry attempt
fixture identity failure
frozen specification identity failure
evidence persistence failure
malformed provider response
unattributable provider response
unexpected scope expansion
need to modify frozen J6 v0.3
need to modify frozen J6 fixtures
need for an unapproved additional live call

After STOP:
no automatic rerun
no automatic second scenario call
return to Human Review

9. Execution Order
Default order:
1. J6-PERM-R1
2. verify evidence and STOP conditions
3. only if clean: J6-PERM-X1

If R1 produces a STOP condition, X1 is not executed.
10. Authorization Boundary
Preparation, wrapper implementation, syntax checking, and offline verification are permitted before the final live gate.
Actual provider execution remains:
NOT AUTHORIZED

until a separate Human Gate explicitly authorizes the live calls.
11. Completion Condition
The bounded live phase is complete when:
both approved calls complete without STOP

or:
a STOP condition terminates execution and the observation is preserved

No additional calls are implied by completion.
END OF J6 LIVE EXECUTION PLAN v0.1
