# Jev runtime-governance PoC — J3/J4/J5

This isolated PoC tests whether a typed probabilistic decision component can sit
inside a deterministic shell without becoming an authority. The sole normative
J0–J2 specification is
[the frozen baseline](docs/Jev_PoC_J0-J2_Integrated_Baseline_v0.1_20260926.md).

Current implementation: **accepted J3/J4 plus the J5 offline repeatability layer**.
The [frozen J4 specification](docs/Jev_PoC_J4_Failure_Injection_Spec_v0.1_20260926.md)
bounds failure injection; the
[frozen J5 specification](docs/Jev_PoC_J5_Repeatability_Independent_Review_Spec_v0.1_20260926.md)
bounds repeatability observation. Independent review is a separate, deferred step.
`J0_MOCK_ENTRY = PASS`;
`J0_LIVE_ENTRY = BLOCKED_API_KEY`. Live Jev evaluation remains blocked and is not
authorized. The harness neither reads credentials nor imports the installed Jev
SDK. This is not SimBench integration. No runtime permission, re-entry, execution,
or state transition is performed. **SEMANTIC_CHECK_PASS is not ALLOW.**

## Architecture

```text
Frozen Fixture → Deterministic Precheck → Provider Adapter
  → Contract Validation → Semantic Signal → Deterministic Component Gate
  → Audit Record
```

- `src/precheck.py` checks schema fields, artifact presence, binding, integrity,
  prohibition, and fixture version/hash against the catalog. Required structure
  and schema must be valid, and frozen fixture identity must be established, before
  a prohibition can produce `DETERMINISTIC_DENY`. Malformed or unverified fixtures
  produce `NOT_EVALUATED`, including when they contain `prohibited: true`. This is
  a bounded J3 ordering rule, not a general mixed-failure precedence claim.
  Failed structural or governance prerequisites skip
  the provider. Missing substantive elements within a present, structurally valid
  evidence submission remain inputs to semantic assessment.
- `src/providers.py` defines a protocol and `MockProvider`, which returns an
  explicitly scripted response without examining evidence,
  expected bands, or notes. There is no authorization logic or fallback in it.
- `src/failure_provider.py` supplies J4's local `FailureProvider`. It raises a
  configured exception or returns an injected invalid result without reading
  the request. HTTP status simulations are local exceptions, not HTTP calls.
- `src/sequence_provider.py` supplies J5's `ScriptedSequenceProvider`. It consumes
  one supplied response per call and fails explicitly on exhaustion. It never
  reads the request and is a test instrument, not a model simulator.
- `src/repeatability.py` runs one frozen fixture repeatedly through the unchanged
  harness, captures actual provider-visible requests, and persists every decision
  plus a separate group summary. `src/repeatability_analysis.py` observes variance
  and analysis-only threshold crossings after decisions are persisted. Input drift
  invalidates the group and suppresses stability statistics. Deterministic bypass
  is excluded from model repeatability interpretation.
- `src/contracts.py` validates the local `choice` contract: one allowed label,
  probabilities for all four labels, and explicit confidence/model handling.
- `src/gate.py` permits `SUFFICIENT` to become `SEMANTIC_CHECK_PASS` only after
  deterministic and contract checks pass. Other valid labels yield
  `SEMANTIC_CHECK_HOLD`; invalid provider/contract results yield `INVALID_RESULT`.
  Non-PASS precheck outcomes and rationales are preserved without reinterpreting
  prohibition. The defensive check after PASS rejects inconsistent prerequisites;
  it does not create a new deterministic DENY.
- `src/harness.py` makes at most one provider attempt per decision, records
  requested/resolved model identities, and never retries. Bypasses record zero
  attempts, a null resolved model, and `NOT_CALLED`.
- `src/audit.py` writes UTF-8 JSON under ignored local `evidence/`. It flushes and
  syncs a `.pending-*.tmp` file, closes it, then atomically renames it to `.json`.
  Only `.json` files represent persisted records. Persistence failure raises
  `EvidencePersistenceError` (`NOT COMMITTABLE`), and the runner exits unsuccessfully.

## Local setup and execution

Python 3.11 or newer is required; verification used Python 3.14.3. From the
repository directory in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m src --fixture F-01 --label SUFFICIENT
.\.venv\Scripts\python.exe -m src --fixture F-05 --label SUFFICIENT
```

Skip the first command if the virtual environment already exists. J3–J5 need only
the standard library: no package installation or network access is required.
Existing `requirements.txt` and `requirements-lock.txt` are unchanged and are not
needed to run the mock harness. No API key setup is required.

The `--label` argument is required: it is the caller's scripted mock answer, not
a model assessment. F-05 returns `DETERMINISTIC_DENY` even when that argument is
`SUFFICIENT`; F-06 returns `NOT_EVALUATED` without calling the provider. A successful
CLI run reports `EVIDENCE_PERSISTED`, the component outcome, and the local record
path. That status says nothing about runtime permission.

## Fixtures and local contract choices

All eight fixtures live in `fixtures/semantic/`. Their versions and canonical
JSON hashes are pinned in `fixtures/manifest.json`, which also records the
unchanged baseline's byte hash. Unknown IDs, changed versions, or modified fixture
content cannot reach provider evaluation. This is a local change-detection check,
not a cryptographic trust anchor; the manifest is reviewed repository content.

[J3 materialization notes](docs/J3_Materialization.md) document how abbreviated
paper fixtures become machine-readable, including which prerequisites are
synthetic and which missingness cases short-circuit. These notes do not supersede
the frozen baseline and record the human-review clarification of structural versus
semantic missingness. Provider-eligible fixtures are F-01, F-02, F-03, F-04, and
F-07. F-05 (prohibition), F-06 (absent artifact), and F-08 (unresolved binding)
bypass the provider. F-02/F-03 use corrected materialization version `v0.1.1` with
new hashes and change reasons; their submitted evidence and expected labels are
unchanged. Future fixture changes require a new version, change reason, and hash.
Repeat groups R1–R4 are retained, including provider-eligible F-03 in R2. J5
exercises them with scripted offline sequences; it does not measure Jev itself.

The local adapter contract uses a probability object with exactly `SUFFICIENT`,
`INSUFFICIENT`, `CONFLICTING`, and `UNCERTAIN` keys. Values must be finite numbers
in `[0, 1]`, excluding booleans, and sum to one within `1e-9` numerical tolerance.
This tolerance is structural, not a confidence threshold. Confidence may be
absent, null, or a finite number in `[0, 1]`; its status is recorded, and there is
no production confidence cutoff. A missing/mismatched resolved model invalidates
the controlled result. This contract does not claim to reproduce live SDK output.

Mock request metadata identifies `standard-library-mock`, version `j3-v0.1`, and
model `mock-choice-v0.1`. `retry_policy` records `enabled: false, max_attempts: 1`.
`timeout: null` means no transport timeout applies to the synchronous in-process
mock; it is not a future live-provider timeout policy. All timestamps are local
harness timestamps in ISO 8601 UTC with explicit `+00:00` offsets. Hashes use
UTF-8 canonical JSON with sorted keys and compact separators. `state_hash` covers
the suspension cause, required/submitted evidence, and deterministic flags;
`question_hash` covers the semantic question. `raw_response_hash` covers the
mock's returned JSON object, including unknown fields. Unencodable responses
produce `INVALID_RESULT` and an explicit encoding error with a null response hash.

Tests are deterministic and offline. They write temporary records only below
ignored `evidence/` and clean their own temporary directories. The full test
command includes the accepted J3/J4 suites, JR-01–JR-10, and J5 support checks,
with required variants expressed as subtests. It prints `J4_SUMMARY` and
`J5_SUMMARY` with coverage and observed invariant counters. The runner can stop
at the first failure by adding `-f`.

[J4 implementation notes](docs/J4_Implementation.md) map every JF case to its test.
`FAIL_OPEN = 0` refers only to the tested J4 failure set and successfully returned
or committed decisions. A computed candidate whose persistence fails is NOT
COMMITTABLE. Retry remains OFF. These simulations make no claim about live
provider reliability, semantic quality, or production readiness. This is not
SimBench integration. Live Jev remains unauthorized.

[J5 implementation notes](docs/J5_Implementation.md) describe the runner API,
request identity, summary fields, and JR traceability. Analysis thresholds are
observation cutoffs only: they are not governance thresholds, permission, or
calibration claims. Low variance implies neither correctness, reliability, nor
authority. Independent review must take place in a fresh session after this
implementation is accepted; it has not been performed here. J6 is not authorized.
