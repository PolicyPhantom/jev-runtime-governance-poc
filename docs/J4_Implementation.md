# J4 offline failure injection

Scope: the twenty cases in the
[frozen J4 specification](Jev_PoC_J4_Failure_Injection_Spec_v0.1_20260926.md).
The accepted J3 harness, contract validator, gate, fixtures, and its 48 tests are
unchanged. The new provider uses only the standard library. It never reads the
request, fixture identity, expected bands, or evidence content. Its only inputs
are the configured exception or invalid return value. No retry or fallback exists.

Run from the repository directory:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v -f
```

There is one separately named J4 test for each JF case. Variants within a case
use explicit subtests. Aggregate assertions in the J4 class teardown require all
twenty IDs and zero fail-open, retry, bypass-call, or partial-commit findings.
`J4_SUMMARY` reports the observations. Tests use the existing harness and audit
writer, rather than substituting another outcome mapper.

| Case | Test in `tests/test_j4_failures.py` | Injection |
| --- | --- | --- |
| JF-01 | `test_jf_01_provider_exception` | Generic local exception |
| JF-02 | `test_jf_02_connection_like_failure` | Dedicated simulated connection exception |
| JF-03 | `test_jf_03_timeout_like_failure` | Dedicated simulated timeout; no sleep |
| JF-04 | `test_jf_04_http_408` | Simulated HTTP 408 |
| JF-05 | `test_jf_05_http_429` | Simulated HTTP 429 |
| JF-06 | `test_jf_06_http_500_and_503` | Both 500 and 503 |
| JF-07 | `test_jf_07_non_provider_response` | None, dictionary, string |
| JF-08 | `test_jf_08_missing_selected_label` | Absent selected label |
| JF-09 | `test_jf_09_unknown_selected_label` | APPROVE and lowercase sufficient |
| JF-10 | `test_jf_10_wrong_primitive` | text and score |
| JF-11 | `test_jf_11_missing_probabilities` | Absent probabilities |
| JF-12 | `test_jf_12_malformed_probabilities` | Container, missing/extra labels, negative, >1, bool, string, NaN, infinity, non-unit sum |
| JF-13 | `test_jf_13_invalid_confidence` | Negative, >1, bool, string, NaN, infinity |
| JF-14 | `test_jf_14_missing_resolved_model` | None and empty string |
| JF-15 | `test_jf_15_resolved_model_mismatch` | Different resolved model; no alias policy |
| JF-16 | `test_jf_16_non_canonicalizable_raw_response` | Otherwise sufficient response with an unencodable set |
| JF-17 | `test_jf_17_evidence_replace_failure` | Replace fails after complete staging; no committed JSON |
| JF-18 | `test_jf_18_evidence_target_outside_root` | Outside target rejected before staging or commit |
| JF-19 | `test_jf_19_existing_audit_record_collision` | Reused decision ID; existing bytes unchanged |
| JF-20 | `test_jf_20_deterministic_bypass_with_failing_provider` | F-05, F-06, F-08; exception provider supplied but never called |

The test-only `J4AuditWriter` annotates `evidence.j4_injection` with `simulated`,
`case_id`, and `variant` after the gate has decided. It delegates persistence to
the unchanged J3 writer. This provenance cannot become authorization input.
Simulated HTTP exceptions also retain status and exception class in the existing
audit `error_detail`, explicitly marked simulated. No live SDK behavior is implied.

Provider/contract cases require INVALID_RESULT. The three bypass cases retain
their frozen outcomes and zero attempts. Every injected run checks retry disabled,
maximum attempts one, and the actual provider call count independently of audit
metadata. J4 audit records are checked for absence of the literal ALLOW token;
JF-09 uses the specification's APPROVE/lowercase examples. The unchanged J3 suite
also checks rejection of the literal ALLOW label. Rejected labels never become
semantic signals or authorization outcomes.

For persistence failures, a valid SUFFICIENT mock answer deliberately produces a
candidate PASS before the writer is called. J3 permits this candidate calculation;
it becomes a completed result only after evidence persistence succeeds. JF-17–19
require EvidencePersistenceError / NOT COMMITTABLE, no CompletedDecision, no new
committed JSON, and no pending file left behind. The existing record in JF-19 is
compared byte for byte. The aggregate fail-open counter counts completed results;
committed-file checks separately ensure no failed persistence publishes one.

All test evidence stays beneath ignored local `evidence/`, in unique temporary
directories cleaned by the tests. The suite does not read credentials or import
the live SDK. FAIL_OPEN refers only to this bounded failure set. It establishes
neither live provider reliability nor production readiness. There is no SimBench
integration, confidence threshold, or general mixed-failure precedence policy.
Live Jev and J5 remain unauthorized. Human review is required for J4 acceptance.
