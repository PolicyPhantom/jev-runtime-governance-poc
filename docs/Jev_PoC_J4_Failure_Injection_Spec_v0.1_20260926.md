# Jev PoC J4 Failure Injection Specification v0.1

**Date:** 2026-09-26  
**Status:** PRE-IMPLEMENTATION FREEZE  
**Branch:** `j4-failure-injection`  
**Prerequisite:** J3 CLOSED / 48 tests PASS  
**Live Jev:** NOT AUTHORIZED  
**J4 Objective:** Demonstrate that injected provider/contract/persistence failures do not produce `SEMANTIC_CHECK_PASS`.

---

## 1. Scope

J4 tests bounded failure behavior around the J3 harness.

It does **not**:

- call the live Jev API
- evaluate semantic quality
- establish provider reliability
- establish production readiness
- modify SimBench
- define a general runtime-governance architecture
- define general mixed-failure precedence
- add retry behavior
- introduce a production confidence threshold

Primary success condition:

```text
FAIL_OPEN = 0
```

Meaning:

> No injected provider, contract, model-identity, or persistence failure may produce `SEMANTIC_CHECK_PASS`.

---

## 2. Frozen J3 invariants

J4 must preserve:

```text
Semantic-provider fixtures:
F-01
F-02
F-03
F-04
F-07

Deterministic-bypass fixtures:
F-05 -> DETERMINISTIC_DENY
F-06 -> NOT_EVALUATED
F-08 -> SEMANTIC_CHECK_HOLD
```

And:

```text
SEMANTIC_CHECK_PASS != ALLOW
RETRY = OFF
1 logical decision <= 1 provider attempt
precheck owns deterministic bypass
gate owns provider-result mapping after precheck PASS
```

---

## 3. Failure Provider

J4 may add a dedicated local `FailureProvider`.

Purpose:

- inject controlled provider-side failure modes
- remain fully offline
- make no network/API calls
- expose deterministic, testable failure behavior

The Failure Provider must not:

- interpret fixture semantics
- inspect expected handling bands
- inspect fixture IDs to choose authorization outcomes
- add retries
- convert failure into a valid semantic label

It may be parameterized only by the failure behavior to inject.

---

## 4. Required failure cases

### JF-01 — Provider exception

Inject a generic provider exception.

Expected:

```text
provider transport_status = ERROR
component outcome = INVALID_RESULT
SEMANTIC_CHECK_PASS = prohibited
attempt_count = 1
```

### JF-02 — Connection-like failure

Inject a dedicated local exception representing a connection failure.

Expected:

```text
ERROR
INVALID_RESULT
no retry
attempt_count = 1
```

Simulation only; not a live network test.

### JF-03 — Timeout-like failure

Inject a dedicated local timeout exception.

Expected:

```text
ERROR
INVALID_RESULT
no retry
attempt_count = 1
```

No wall-clock delay is required.

### JF-04 — HTTP 408 simulation

Inject provider response/failure metadata representing HTTP 408.

Expected:

```text
not PASS
no retry
attempt_count = 1
```

### JF-05 — HTTP 429 simulation

Inject provider response/failure metadata representing HTTP 429.

Expected:

```text
not PASS
no retry
attempt_count = 1
```

### JF-06 — HTTP 5xx simulation

At minimum test:

```text
500
503
```

Expected:

```text
not PASS
no retry
attempt_count = 1
```

No need to exhaustively test every 5xx value in J4.

### JF-07 — Non-ProviderResponse object

Inject a provider return value that violates the provider interface.

Examples:

```text
None
dict
string
```

Expected:

```text
ERROR or invalid provider result
INVALID_RESULT
not PASS
```

### JF-08 — Missing selected label

Expected:

```text
contract invalid
INVALID_RESULT
```

### JF-09 — Unknown selected label

Examples:

```text
ALLOW
APPROVE
sufficient
```

Expected:

```text
contract invalid
INVALID_RESULT
```

### JF-10 — Wrong primitive

Examples:

```text
primitive = "text"
primitive = "score"
```

Expected:

```text
contract invalid
INVALID_RESULT
```

### JF-11 — Missing probabilities

Expected:

```text
contract invalid
INVALID_RESULT
```

### JF-12 — Malformed probabilities

At minimum include:

```text
wrong container type
missing labels
extra labels
negative value
value > 1
bool value
string value
NaN
infinity
sum != 1
```

Expected:

```text
contract invalid
INVALID_RESULT
```

### JF-13 — Confidence invalidity

At minimum include:

```text
< 0
> 1
bool
string
NaN
infinity
```

Expected:

```text
contract invalid
INVALID_RESULT
```

Do not introduce a production confidence threshold.

### JF-14 — Resolved model missing

Examples:

```text
None
empty string
```

Expected:

```text
model identity invalid
INVALID_RESULT
```

### JF-15 — Resolved model mismatch

Expected:

```text
requested_model != resolved_model
-> INVALID_RESULT
```

No alias-resolution policy is introduced in J4.

### JF-16 — Raw response not canonicalizable

Inject an otherwise provider-returned structure that cannot be canonicalized by the local JSON hash function.

Expected:

```text
raw_response_hash = null
validation/result invalidated
INVALID_RESULT
not PASS
```

### JF-17 — Evidence persistence replace failure

Inject failure in the safe-write replace/commit step.

Expected:

```text
EvidencePersistenceError
NOT COMMITTABLE
no CompletedDecision returned
no partial committed JSON remains
```

### JF-18 — Evidence target outside evidence/

Attempt to persist outside the configured local evidence directory.

Expected:

```text
rejected before committed write
NOT COMMITTABLE
```

### JF-19 — Existing audit record collision

Attempt to write a second record to an existing target.

Expected:

```text
existing evidence remains unchanged
new write rejected
```

### JF-20 — Deterministic bypass with failing provider object supplied

For:

```text
F-05
F-06
F-08
```

Supply a Failure Provider that would raise if called.

Expected:

```text
provider evaluate() is never called
attempt_count = 0
frozen deterministic outcome preserved
```

This proves provider failure cannot contaminate deterministic-bypass cases.

---

## 5. Retry invariant

J4 must explicitly verify:

```text
retry_policy.enabled = false
max_attempts = 1
```

For all injected provider failures:

```text
attempt_count <= 1
```

No hidden retry implementation is permitted.

A retry-on experiment belongs to a later explicitly authorized scope.

---

## 6. Failure classification

J4 may introduce local failure metadata such as:

```text
failure_kind
http_status
provider_exception_class
```

only if useful for auditability.

Any new field must:

- remain local to J4
- not imply live provider semantics unless clearly marked simulated
- not alter frozen J3 outcomes
- not become authorization input

---

## 7. Audit expectations

Every J4 case that reaches the provider layer should preserve, where applicable:

```text
logical_decision_id
timestamp
fixture identity/hash
state/question hash
requested_model
resolved_model when available
attempt_count
transport_status
latency_ms
validation status
component outcome
error_class
error_detail
raw_response_hash when encodable
```

Failure metadata must support later reconstruction of:

```text
what was injected
what layer detected it
why PASS was impossible
```

---

## 8. J4 tests

J4 must add deterministic automated tests proving at minimum:

```text
[ ] every JF-01 through JF-20 case is exercised
[ ] no injected failure produces SEMANTIC_CHECK_PASS
[ ] no injected failure introduces ALLOW
[ ] provider attempts never exceed 1
[ ] deterministic bypass cases remain provider-free
[ ] evidence persistence failure returns no successful CompletedDecision
[ ] baseline J3 tests continue to pass
```

The exact number of new tests is not frozen.

---

## 9. J4 acceptance criteria

J4 is acceptable only if:

```text
FULL_TEST_SUITE = PASS
J3_REGRESSION = 0
FAIL_OPEN = 0
SILENT_RETRY = 0
UNAUTHORIZED_PROVIDER_CALL_ON_BYPASS = 0
PARTIAL_EVIDENCE_COMMIT = 0
LIVE_NETWORK_CALLS = 0
LIVE_JEV_CALLS = 0
SECRET_ACCESS = 0
BASELINE_MODIFICATION = 0
```

---

## 10. Stop conditions

Stop J4 and report for human review if:

- a new dependency appears necessary
- J3 frozen semantics would need modification
- a failure can produce `SEMANTIC_CHECK_PASS`
- retries appear implicitly
- provider failure changes deterministic-bypass outcomes
- evidence failure returns a successful decision object
- live API/network access appears necessary
- implementation requires a general mixed-failure precedence policy
- fixture semantics would need to change

---

## 11. J4 closure record

At completion, report:

```text
J4_IMPLEMENTATION = COMPLETE / BLOCKED
FULL_TEST_COUNT
NEW_J4_TEST_COUNT
FAIL_OPEN_COUNT
RETRY_COUNT_BEYOND_FIRST
DETERMINISTIC_BYPASS_PROVIDER_CALLS
EVIDENCE_PARTIAL_COMMIT_FINDINGS
BASELINE_SHA256
NETWORK_CALLS
LIVE_JEV_CALLS
SECRETS_INSPECTED
FILES_CHANGED
GIT_STATUS
```

Do not commit until human review accepts J4.

Do not proceed to J5 automatically.

---

## 12. Current authorization

```text
J3 = CLOSED
J4_FAILURE_INJECTION = AUTHORIZED AFTER THIS SPEC IS COMMITTED
J5 = NOT AUTHORIZED
LIVE_JEV = NOT AUTHORIZED
SIMBENCH_INTEGRATION = NOT APPROVED
```
