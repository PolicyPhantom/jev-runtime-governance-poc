# J5 repeatability layer

Scope: the offline observation machinery in the
[frozen J5 specification](Jev_PoC_J5_Repeatability_Independent_Review_Spec_v0.1_20260926.md).
J3/J4 logic, their 68 tests, all fixtures, and the three frozen specifications are
unchanged. Only the standard library is used. Independent review is deferred to a
fresh session after implementation acceptance; this note contains no review result.

## Architecture and use

`ScriptedSequenceProvider` returns supplied responses in order without inspecting
the request. Each successful call consumes exactly one response. Exhaustion raises
`SequenceExhaustedError`, increments the call count, consumes no response, and
never loops or retries. The unchanged harness records exhaustion as INVALID_RESULT.
This is a test instrument, not a model simulator.

`run_repeatability` snapshots one fixture as canonical JSON and deserializes a
fresh copy for each ordinary harness run. Repeat count is bounded to 1–1000 as a
local workload limit, not a governance threshold. Each run has its own decision
ID, timestamp, audit file, and at most one provider attempt. A new decision in the
explicit group is not a retry of an earlier decision.

For an offline example, run this Python code from the repository directory:

```python
from src.models import MOCK_MODEL
from src.providers import ProviderResponse, mock_choice
from src.repeatability import run_repeatability
from src.sequence_provider import ScriptedSequenceProvider

script = [ProviderResponse(mock_choice("UNCERTAIN"), MOCK_MODEL) for _ in range(3)]
group = run_repeatability("F-03", 3, ScriptedSequenceProvider(script))
print(group.summary_path)
```

Optional arguments are `requested_model`, `analysis_profile`, and an existing
`AuditWriter` pointing beneath local ignored `evidence/`. No network or API key is
needed. The runner never deletes per-decision records. Tests use their own temporary
directories under `evidence/` and clean those directories after verification.

## Request identity and evidence

An observing provider adapter captures the actual request immediately before
forwarding it. Request identity is SHA-256 of canonical JSON containing exactly:
`state`, `semantic_question`, `requested_model`, `primitive`, and `allowed_labels`.
Dictionary-key order is normalized; text whitespace and label order are retained.
UUIDs, timestamps, latency, bands, notes, group labels, and paths are excluded.

Each ordinary record retains its full J3 envelope. Audit-only
`evidence.repeatability` adds the group ID, frozen R-group label, one-based run
index, captured request content, and its hash. These fields are attached after
the gate has decided and before the unchanged safe writer persists the record.
No request is invented for a deterministic bypass: its content/hash are null.

The summary uses a separate UUID (`repeat_group_id`, also the summary's
`logical_decision_id`) and `record_type: repeatability_group`. It references all
decision IDs and their paths relative to `evidence/`. It is written only after
all decisions have been persisted. Any decision or summary persistence failure
propagates as EvidencePersistenceError; no CompletedRepeatGroup is returned.
Previously completed decision records remain available. A summary never replaces
per-decision evidence, and partial staged files are never committed JSON.

## Summary semantics

Every group retains fixture ID/version/hash, request hashes, run count, decision
IDs, raw labels, probability vectors, confidence values/statuses, resolved models,
component outcomes, contract statuses, attempt counts, latencies, and the analysis
profile. The frozen repeat-group label is `repeat_group`; a particular execution
has a distinct `repeat_group_id`.

- `VALID`: verified same-input series with valid provider/contract results.
  Labels, resolved models, and outcomes have sequence/unique/switch summaries.
  Each label's probabilities have count/min/max/range/mean. Numeric confidence
  has the same statistics; ABSENT and NULL remain explicit and never become zero.
- `INVALID`: request identity drift, fixture/input/policy drift, or invalid
  decisions. Raw observations and reasons remain. Input drift suppresses all
  derived stability summaries and crossings. With stable inputs but invalid
  output/model identity, model and outcome counts remain diagnostic only;
  label/probability/confidence statistics and crossings are suppressed. A model
  mismatch remains INVALID_RESULT in its original decision; the group is invalid.
- `EXCLUDED_DETERMINISTIC_BYPASS`: F-05/F-06/F-08 retain their deterministic
  outcomes with zero provider attempts and no model-repeatability statistics.

Group validity is an analysis status, never a component or authorization outcome.
Checks also compare fixture/input/request audit metadata for constant policy and
retry settings. UUIDs, clocks, and latency do not participate in those checks.
`summarize_repeat_group` can reanalyze persisted records with another profile
without changing the records or writing files.

## Analysis-only thresholds

`AnalysisOnlyProfile` defaults to ID `analysis-demo-v0.1`, selected-label
probability threshold 0.70, and confidence threshold 0.70. The profile is never
passed to the harness or gate. Analysis starts only after decision persistence.

ANALYSIS THRESHOLD != GOVERNANCE THRESHOLD.
ANALYSIS THRESHOLD != PERMISSION.
ANALYSIS THRESHOLD != CALIBRATION CLAIM.

Crossings compare adjacent numeric observations. Equality belongs to the upper
side. Missing/null observations break adjacency; no interpolation occurs. Each
crossing records only field, one-based run indices, values, and UP/DOWN direction.
Selected-label probability means the probability assigned to that run's selected
label. `threshold_observations` and `threshold_crossings` contain the same list.
Crossing a cutoff cannot change any recorded component outcome.

## JR traceability

Tests are in `tests/test_j5_repeatability.py`:

| Case | Test | Observation |
| --- | --- | --- |
| JR-01 | `test_jr_01_stable_positive_sequence` | F-01/R1, sufficient with small variance, no crossings |
| JR-02 | `test_jr_02_same_label_numeric_variance` | F-03/R2, UNCERTAIN with probability/confidence variance |
| JR-03 | `test_jr_03_label_switching_within_hold` | F-03/R2, INSUFFICIENT/UNCERTAIN switches; HOLD unchanged |
| JR-04 | `test_jr_04_repeated_conflicting` | F-04/R3, CONFLICTING with numeric variance |
| JR-05 | `test_jr_05_distracting_input_does_not_change_script` | F-07/R4, script remains non-sufficient |
| JR-06 | `test_jr_06_analysis_probability_crossing_does_not_change_gate` | Probability crosses; outcome unchanged under alternate profiles |
| JR-07 | `test_jr_07_analysis_confidence_crossing_does_not_change_gate` | Confidence crosses; outcome unchanged under alternate profiles |
| JR-08 | `test_jr_08_model_inconsistency_is_invalid_and_observed` | Resolved-model switch observed; mismatched decision invalid |
| JR-09 | `test_jr_09_request_identity_drift_invalidates_group` | Separate drift subcase for each of the five request fields |
| JR-10 | `test_jr_10_bypass_is_provider_free_and_excluded` | F-05/F-06/F-08 never consume the supplied empty script |

Twelve additional tests cover consumption/exhaustion, script isolation, identity
inclusions/exclusions, confidence missingness, crossing adjacency, parameter
bounds, failed decision/summary persistence, output metadata, and policy drift.
Run the full suite with:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v -f
```

`J5_SUMMARY` asserts full JR coverage and zero fail-open findings, retries beyond
the first attempt, undetected request drift, threshold-to-gate coupling, bypass
provider calls, and partial evidence commits. Legitimate SUFFICIENT/PASS decisions
are positive controls, not fail-open findings. J3/J4 regression tests remain intact.

These observations establish no live Jev repeatability, calibration, correctness,
reliability, or authority. Low variance is not evidence of those properties.
SEMANTIC_CHECK_PASS is not ALLOW or re-entry permission. There is no SimBench
integration, production threshold, or general mixed-failure precedence policy.
Live Jev, J6, and the independent-review step are outside this implementation pass.
