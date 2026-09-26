# Jev PoC J5 Repeatability & Independent Review Specification v0.1

**Date:** 2026-09-26  
**Status:** PRE-IMPLEMENTATION FREEZE  
**Branch:** `j5-repeatability-review`  
**Prerequisite:** J4 CLOSED / 68 tests PASS  
**Live Jev:** NOT AUTHORIZED  
**J5 Objective:** Build and verify the repeatability-analysis layer and complete an independent review of the bounded offline harness before any live Jev evaluation.

---

## 1. Scope

J5 evaluates the **observation machinery**, not Jev itself.

The phase has two parts:

1. **Repeatability layer**
   - exact-input reuse
   - repeated provider-evaluation orchestration
   - label/probability/confidence variance recording
   - threshold-crossing observation
   - resolved-model consistency observation
   - reconstructable run-group evidence

2. **Independent review**
   - review J3/J4/J5 implementation against the frozen specifications
   - identify fail-open paths, hidden authority, silent retry, or evidence gaps
   - report findings without modifying frozen semantics unless human review authorizes a correction

J5 remains fully offline.

It does **not**:

- call the live Jev API
- measure live Jev repeatability
- claim model calibration
- claim semantic accuracy
- define a production threshold
- approve Jev adoption
- approve SimBench integration
- define a general mixed-failure precedence policy
- enable retry
- modify the canonical SimBench repository

---

## 2. Frozen prerequisites

J5 must preserve all accepted J3/J4 invariants.

### Provider-eligible fixtures

```text
F-01
F-02
F-03
F-04
F-07
```

### Deterministic-bypass fixtures

```text
F-05 -> DETERMINISTIC_DENY
F-06 -> NOT_EVALUATED
F-08 -> SEMANTIC_CHECK_HOLD
```

### Repeat groups from J2

```text
R1 = F-01 clear positive anchor
R2 = F-03 ambiguous boundary case
R3 = F-04 conflicting case
R4 = F-07 distracting-input case
```

### Core boundaries

```text
SEMANTIC_CHECK_PASS != ALLOW
RETRY = OFF
1 logical decision <= 1 provider attempt
precheck owns deterministic bypass
gate owns provider-result mapping after PASS
evidence persistence is required before CompletedDecision
```

---

## 3. Exact-input repeatability rule

Within one repeat group:

```text
fixture bytes / canonical fixture content
semantic question
provider request state
requested model
policy profile
retry policy
```

must remain unchanged unless the specific test is explicitly about one of those variables.

The repeatability runner must not introduce incidental input drift through:

```text
timestamps
UUIDs
randomized field ordering
mutable fixture reuse
whitespace changes
implicit environment metadata
```

Runtime-generated fields such as decision IDs, timestamps, and latency are outputs, not semantic inputs.

---

## 4. Repeatability provider abstraction

J5 may add a local **ScriptedSequenceProvider** (or equivalent).

Purpose:

- return a predetermined sequence of valid or invalid provider responses
- allow controlled variance testing
- remain fully offline
- never inspect fixture contents
- never select an answer based on expected handling bands
- never decide permission
- never retry internally

Example sequence:

```text
Run 1 -> SUFFICIENT, probabilities A, confidence A
Run 2 -> SUFFICIENT, probabilities B, confidence B
Run 3 -> UNCERTAIN, probabilities C, confidence C
```

This is a **test instrument**, not a probabilistic-model simulator.

The sequence provider must:

```text
consume at most one scripted response per evaluate() call
record call count
fail explicitly if the scripted sequence is exhausted
not loop or retry
```

---

## 5. Repeatability runner

Add a bounded runner that can execute one frozen fixture repeatedly.

Minimum inputs:

```text
fixture_id
repeat_count
provider
requested_model
analysis_profile
writer / evidence directory
```

Minimum outputs:

```text
repeat_group_id
fixture_id
fixture_version
fixture_hash
request_identity_hash
run_count
decision_ids
selected_labels
probability_vectors
confidence_values
resolved_models
component_outcomes
contract_statuses
attempt_counts
latencies_ms
threshold_observations
```

The runner must preserve each ordinary decision's audit record.

It may create a separate group summary, but the group summary must not replace per-decision evidence.

---

## 6. Request identity

J5 must derive a stable identity for the semantic provider request.

The identity must be based on the provider-visible request only:

```text
state
semantic_question
requested_model
primitive
allowed_labels
```

It must not include:

```text
decision UUID
timestamp
latency
expected handling band
fixture notes
repeat group label
audit path
```

All runs in a valid same-input repeat group must have the same request identity hash.

If request identity changes unexpectedly:

```text
REPEAT_GROUP_VALIDITY = INVALID
```

and no stability interpretation may be produced.

---

## 7. Variance observations

J5 observes, but does not normatively judge, the following.

### 7.1 Label stability

Record:

```text
label_sequence
unique_labels
label_switch_count
```

### 7.2 Probability variance

For each allowed label, record at minimum:

```text
min
max
range
mean
```

Standard deviation may be included using the Python standard library if useful.

Do not infer calibration from these statistics.

### 7.3 Confidence variance

If confidence is present:

```text
min
max
range
mean
```

If confidence is absent/null:

```text
preserve absence/null status explicitly
```

Do not convert missing confidence into a numeric zero.

### 7.4 Resolved model consistency

Record:

```text
requested_model
unique_resolved_models
model_switch_count
```

In the controlled offline baseline, an unexpected resolved-model change is an observable incompatibility.

### 7.5 Outcome stability

Record:

```text
component_outcome_sequence
unique_component_outcomes
outcome_switch_count
```

---

## 8. Threshold-observation profile

J5 may introduce **analysis-only thresholds** for observing boundary crossings.

These are **not policy thresholds** and must never affect gate outcomes.

Example analysis profile:

```text
profile_id = "analysis-demo-v0.1"

selected_label_probability_threshold = 0.70
confidence_threshold = 0.70
```

The exact numeric defaults may be chosen for testability, but documentation must state:

```text
ANALYSIS THRESHOLD != GOVERNANCE THRESHOLD
ANALYSIS THRESHOLD != PERMISSION
ANALYSIS THRESHOLD != CALIBRATION CLAIM
```

A threshold crossing means only:

> A recorded numeric field moved from one side of the analysis-only threshold to the other across repeated observations.

The runner must record:

```text
crossing field
run indices
values
direction
```

The crossing must not modify the recorded component outcome.

---

## 9. Required J5 controlled scenarios

### JR-01 — Stable positive sequence

Fixture:

```text
F-01 / R1
```

Script:

```text
SUFFICIENT on all runs
small probability variation
no threshold crossing
same resolved model
```

Expected:

```text
label_switch_count = 0
outcome_switch_count = 0
request identity stable
```

### JR-02 — Ambiguous same-label numeric variance

Fixture:

```text
F-03 / R2
```

Script:

```text
UNCERTAIN on all runs
probability/confidence values vary
no label switch
```

Expected:

```text
numeric variance observed
semantic outcome remains HOLD
```

### JR-03 — Label switching within HOLD zone

Fixture:

```text
F-03 / R2
```

Script:

```text
INSUFFICIENT
UNCERTAIN
INSUFFICIENT
UNCERTAIN
```

Expected:

```text
label switches observed
component outcome remains SEMANTIC_CHECK_HOLD throughout
```

This demonstrates:

```text
semantic-label variance
!=
runtime authority variance
```

### JR-04 — Conflicting fixture

Fixture:

```text
F-04 / R3
```

Script includes repeated `CONFLICTING` results with numeric variation.

Expected:

```text
HOLD throughout
request identity stable
```

### JR-05 — Distracting-input fixture

Fixture:

```text
F-07 / R4
```

Script remains non-sufficient.

Expected:

```text
embedded instructions do not alter provider script or gate logic
```

### JR-06 — Analysis-only threshold crossing

Use a provider-eligible fixture and scripted valid outputs whose selected-label probability crosses the analysis-only threshold while the semantic label remains unchanged.

Expected:

```text
crossing recorded
gate outcome unchanged
```

### JR-07 — Confidence threshold crossing

Where confidence is present, cross the analysis-only confidence threshold without changing authorization semantics.

Expected:

```text
crossing recorded
gate outcome unchanged
```

### JR-08 — Resolved model switch observation

Provide valid responses under two different resolved-model identifiers across runs.

Because the current controlled contract requires requested/resolved model match, the mismatched run(s) should become invalid decisions rather than silently forming one stable series.

Expected:

```text
model inconsistency observed
no fail-open
```

The runner must not reinterpret this as model quality evidence.

### JR-09 — Request identity drift detection

Intentionally alter one provider-visible request input between runs in a dedicated test.

Expected:

```text
REPEAT_GROUP_VALIDITY = INVALID
```

No repeatability interpretation should be emitted for the invalid group.

### JR-10 — Deterministic bypass excluded from provider repeatability

Attempt repeat-run orchestration for:

```text
F-05
F-06
F-08
```

Expected:

```text
provider attempts = 0
deterministic outcomes preserved
not treated as model repeatability observations
```

---

## 10. Aggregate repeatability summary

The group summary should contain at minimum:

```text
analysis_scope
fixture_id
repeat_group
fixture_hash
request_identity_hash
repeat_group_validity
run_count

labels:
  sequence
  unique
  switches

component_outcomes:
  sequence
  unique
  switches

probabilities:
  per_label statistics

confidence:
  presence status
  statistics when numeric

models:
  requested
  resolved sequence
  unique
  switches

attempts:
  per-run
  max

threshold_crossings:
  list

claim_boundary:
  "offline scripted sequence only"
```

---

## 11. J5 acceptance criteria

J5 repeatability layer is acceptable only if:

```text
FULL_TEST_SUITE = PASS
J3_REGRESSION = 0
J4_REGRESSION = 0
FAIL_OPEN = 0
SILENT_RETRY = 0
REQUEST_IDENTITY_DRIFT_UNDETECTED = 0
THRESHOLD_TO_GATE_COUPLING = 0
DETERMINISTIC_BYPASS_PROVIDER_CALLS = 0
PARTIAL_EVIDENCE_COMMIT = 0
NETWORK_CALLS = 0
LIVE_JEV_CALLS = 0
SECRET_ACCESS = 0
BASELINE_MODIFICATION = 0
J4_SPEC_MODIFICATION = 0
```

---

## 12. Independent review

After implementation and full tests pass, perform an **independent read-only review**.

Use a fresh review context/session.

The reviewer must not modify files during the first review pass.

Review focus:

```text
1. hidden authority leakage
2. fail-open paths
3. retry leakage
4. request identity correctness
5. threshold-to-gate coupling
6. repeat-group contamination
7. evidence reconstruction gaps
8. model-identity handling
9. deterministic bypass contamination
10. claim-boundary overreach
```

The review must classify findings as:

```text
BLOCKER
MAJOR
MINOR
NOTE
```

No numeric score is required.

The reviewer must report:

```text
finding_id
severity
file/location
finding
why it matters
recommended correction
```

If any `BLOCKER` or `MAJOR` is found:

```text
J5_CLOSURE = HOLD
```

Human review decides whether corrections are authorized.

If only `MINOR` / `NOTE` findings remain, human review decides whether J5 may close or whether cleanup is warranted.

---

## 13. Independent review boundaries

The reviewer must not:

- redesign the PoC
- propose live Jev use as a fix
- require SimBench integration
- introduce a production threshold
- infer real-world reliability
- treat scripted repeatability as model repeatability
- treat low variance as correctness
- treat high confidence as authority
- convert J5 into a benchmark

---

## 14. Documentation

Add a concise J5 implementation note containing:

```text
repeatability architecture
request identity definition
analysis-only threshold policy
JR-01..JR-10 traceability
aggregate summary semantics
claim boundaries
independent review result
```

Do not create per-run Notion records.

Raw run evidence remains in ignored `evidence/`.

---

## 15. J5 closure report

At completion report:

```text
J5_IMPLEMENTATION = COMPLETE / BLOCKED
FULL_TEST_COUNT
NEW_J5_TEST_COUNT
JR-01..JR-10 COVERAGE
FAIL_OPEN_COUNT
RETRY_COUNT_BEYOND_FIRST
REQUEST_IDENTITY_DRIFT_UNDETECTED
THRESHOLD_TO_GATE_COUPLING_FINDINGS
DETERMINISTIC_BYPASS_PROVIDER_CALLS
EVIDENCE_PARTIAL_COMMIT_FINDINGS
J3_REGRESSION_COUNT
J4_REGRESSION_COUNT
BASELINE_SHA256
J4_SPEC_SHA256
J5_SPEC_SHA256
NETWORK_CALLS
LIVE_JEV_CALLS
SECRETS_INSPECTED
INDEPENDENT_REVIEW_FINDINGS
FILES_CREATED
FILES_MODIFIED
DEVIATIONS
BLOCKERS
GIT_STATUS
```

Do not commit until human review accepts J5.

Do not proceed to J6 automatically.

---

## 16. Minimal Notion checkpoint

After J5 closes, create **one** integrated J3–J5 checkpoint.

It should contain only:

```text
J3 harness closure
J4 failure-injection closure
J5 repeatability/review closure
test totals
key findings
known boundaries
canonical commits
next authorized phase
```

Do not import raw tests, raw evidence, or per-run logs into Notion.

---

## 17. Current authorization

```text
J3 = CLOSED
J4 = CLOSED
J5_REPEATABILITY_AND_REVIEW = AUTHORIZED AFTER THIS SPEC IS COMMITTED
J6_LIVE_JEV_EVALUATION = NOT AUTHORIZED
SIMBENCH_INTEGRATION = NOT APPROVED
JEV_ADOPTION_DECISION = NOT MADE
```
