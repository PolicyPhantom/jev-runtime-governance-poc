# Jev Runtime-Governance PoC

A bounded derivative validation from the AIBL / SimBench runtime-governance research line.

This repository examines how a probabilistic semantic decision component can be integrated into a deterministic governance shell **without allowing the component itself to become permission, authority, or an autonomous runtime controller**.

The project progressed from frozen offline fixtures and failure injection through bounded live integration with Jev.

Final project status:

`J6 = COMPLETE / FROZEN`

---

## Core Finding

The central boundary examined by this PoC is:

```text
semantic judgment
!= component outcome
!= permission applicability
!= governance authority
```

Within the bounded J6 cases, Jev was usable as a probabilistic semantic decision component when surrounded by consumer-side controls for:

- request and fixture identity,
- deterministic prechecks,
- response validation,
- evidence preservation,
- failure attribution,
- permission separation,
- and Human Gate authority.

The provider output was **not** treated as permission, re-entry authorization, or an autonomous governance decision.

A concise bounded interpretation is:

> Jev is useful as a bounded probabilistic semantic decision component, not as an autonomous governance authority.

This is a PoC finding, not a general claim about Jev performance or production suitability.

---

## Relationship to SimBench

This repository is a derivative validation from the broader AIBL / SimBench runtime-governance research line.

Parent research repository:

[AIBL Physical AI Runtime-Governance SimBench](https://github.com/PolicyPhantom/aibl-physical-ai-runtime-governance-simbench)

SimBench established the research pattern of translating governance concepts into:

```text
specification
-> implementation
-> executable tests
-> failure injection
-> evidence
-> review
-> correction
-> Human Gate
-> theory feedback
```

The Jev PoC applies that pattern to a provider-managed probabilistic decision component.

It is not part of the SimBench runtime itself and does not claim SimBench production integration.

---

## Research Question

The primary J6 question was not:

> Can Jev produce the expected label?

The primary question was:

> Can a consumer reconstruct a bounded decision path from retained evidence while preventing a probabilistic semantic output from implicitly becoming permission or governance authority?

This distinction is central to the project.

---

## J0-J6 Overview

### J0-J2 — Frozen Baseline

The initial specification defined the bounded semantic task and governance constraints.

Canonical baseline:

[`docs/Jev_PoC_J0-J2_Integrated_Baseline_v0.1_20260926.md`](docs/Jev_PoC_J0-J2_Integrated_Baseline_v0.1_20260926.md)

Semantic labels:

- `SUFFICIENT`
- `INSUFFICIENT`
- `CONFLICTING`
- `UNCERTAIN`

Component outcomes include:

- `SEMANTIC_CHECK_PASS`
- `SEMANTIC_CHECK_HOLD`
- `DETERMINISTIC_DENY`
- `NOT_EVALUATED`
- `INVALID_RESULT`

A semantic PASS is never equivalent to ALLOW.

---

### J3 — Deterministic Governance Harness

J3 materialized the frozen fixtures into a local executable harness.

The harness separates:

- deterministic prerequisites,
- provider evaluation,
- contract validation,
- component outcome,
- and persisted evidence.

Provider bypass conditions remain explicit.

---

### J4 — Failure Injection

J4 introduced bounded offline failure injection across provider, contract, encoding, persistence, and deterministic bypass boundaries.

The failure set is documented in:

[`docs/J4_Implementation.md`](docs/J4_Implementation.md)

The tested J4 scope produced:

```text
FAIL_OPEN_COUNT = 0
RETRY_COUNT_BEYOND_FIRST = 0
EVIDENCE_PARTIAL_COMMIT_FINDINGS = 0
```

These counters apply only to the bounded tested cases.

---

### J5 — Repeatability Observation

J5 added scripted repeatability machinery without converting probability or confidence into governance authority.

The repeatability layer observes:

- label variance,
- probability variance,
- confidence variance,
- input identity,
- provider bypass,
- and analysis-only threshold crossings.

Analysis thresholds do not alter the deterministic component gate.

J5 documentation:

[`docs/J5_Implementation.md`](docs/J5_Implementation.md)

---

### J6 — Permission Boundary and Bounded Live Integration

J6 extended the PoC from semantic component behavior to the boundary between:

```text
semantic judgment
component outcome
decision reconstruction
permission applicability
governance authority
```

Frozen J6 specification:

[`docs/Jev_PoC_J6_Specification_v0.3_20260930.md`](docs/Jev_PoC_J6_Specification_v0.3_20260930.md)

Live execution plan:

[`docs/Jev_PoC_J6_Live_Execution_Plan_v0.1_20261001.md`](docs/Jev_PoC_J6_Live_Execution_Plan_v0.1_20261001.md)

Case map:

[`docs/Jev_PoC_J6_Live_Case_Map_v0.1_20261001.md`](docs/Jev_PoC_J6_Live_Case_Map_v0.1_20261001.md)

Final closeout note:

[`docs/Jev_PoC_J6_Closeout_v0.1_20261002.md`](docs/Jev_PoC_J6_Closeout_v0.1_20261002.md)

---

## J6 Bounded Live Observations

Exactly two Human-Gated live semantic calls were executed.

Conditions:

```text
R1 maximum calls = 1
X1 maximum calls = 1
provider retry = 0
runner retry = none
automatic rerun = prohibited
repeatability sweep = not performed
additional exploratory calls = prohibited
```

### R1 — Restoration Case

Mapping:

```text
J6-PERM-R1 -> F-01
```

Observed result:

```text
requested model        = jev-latest
resolved model         = jev-1.13.0
transport              = OK
attempt count          = 1

semantic judgment      = SUFFICIENT
component outcome      = SEMANTIC_CHECK_PASS
decision reconstruction= RECONSTRUCTED
permission             = NOT_SUPPORTED

permission reason      = PA_RESTORATION_CONDITION_UNMET
STOP                    = false
```

Observed semantic probabilities:

```text
SUFFICIENT   = 0.86
INSUFFICIENT = 0.11
UNCERTAIN    = 0.03
CONFLICTING  = 0.00
confidence   = 0.82
```

---

### X1 — Contrast Restriction Case

Mapping:

```text
J6-PERM-X1 -> F-02
```

Observed result:

```text
requested model        = jev-latest
resolved model         = jev-1.13.0
transport              = OK
attempt count          = 1

semantic judgment      = INSUFFICIENT
component outcome      = SEMANTIC_CHECK_HOLD
decision reconstruction= RECONSTRUCTED
permission             = NOT_SUPPORTED

permission reason      = PA_EXPLICIT_EXCLUSION
STOP                    = false
```

Observed semantic probabilities:

```text
INSUFFICIENT = 1.00
SUFFICIENT   = 0.00
UNCERTAIN    = 0.00
CONFLICTING  = 0.00
confidence   = 1.00
```

These are case-specific observations from single bounded calls and are not statistical performance claims.

---

## Cross-Case Interpretation

The two live cases produced different semantic outcomes:

```text
R1:
SUFFICIENT
-> SEMANTIC_CHECK_PASS
-> RECONSTRUCTED
-> NOT_SUPPORTED

X1:
INSUFFICIENT
-> SEMANTIC_CHECK_HOLD
-> RECONSTRUCTED
-> NOT_SUPPORTED
```

The semantic component changed its judgment.

The permission layer remained independently governed by different permission conditions.

This is consistent with the J6 design objective:

```text
semantic judgment
!= component outcome
!= permission applicability
!= governance authority
```

The provider output did not itself grant, restore, revoke, or authorize permission.

---

## Architecture

The overall structure is intentionally layered.

```text
Frozen Fixture / Scenario
        |
        v
Deterministic Precheck
        |
        v
Probabilistic Semantic Component
        |
        v
Consumer-Side Validation
        |
        v
Component Outcome
        |
        v
Evidence Preservation
        |
        v
Decision Reconstruction
        |
        v
Permission Assessment
        |
        v
Human / Governance Authority
```

The probabilistic component is intentionally bounded inside a deterministic governance structure.

---

## Provider and Failure Boundaries

J6 distinguishes between:

- provider execution failure,
- local response-processing failure,
- raw-response capture failure,
- response encoding failure,
- diagnostic-rendering failure,
- and evidence persistence failure.

A successful provider transport observation is not rewritten as a provider failure merely because local processing later fails.

Where trusted raw-response evidence cannot be captured or encoded, the result fails closed.

Fallback representations remain explicitly untrusted.

Diagnostic failures such as broken `__str__` or `__repr__` behavior cannot suppress STOP state or bypass intended evidence persistence.

A completed live result is not returned unless evidence persistence succeeds.

---

## Model Identity

Both bounded live calls requested:

```text
jev-latest
```

The provider reported:

```text
jev-1.13.0
```

J6 records this as:

```text
model_identity_status = MISMATCH
```

Model identity is treated as a separate observation.

A requested/resolved mismatch does not automatically invalidate an otherwise structurally valid J6 response.

The provider-reported resolved model is retained as consumer-visible evidence.

It is not treated as independent proof of provider-internal execution state.

---

## Evidence Preservation Boundary

Runtime evidence is written locally under:

```text
evidence/
```

The directory is intentionally excluded from Git through `.gitignore`.

The R1 and X1 raw runtime evidence JSON files therefore remain local evidence artifacts.

The repository preserves:

- evidence identifiers,
- local evidence paths,
- raw-response hashes,
- scenario identifiers,
- reviewed observations,
- and closeout findings,

but does not publish the raw runtime evidence JSON files themselves.

This is an intentional repository boundary and does not indicate evidence-persistence failure.

---

## Verification

Final full regression before closeout:

```text
124 / 124 PASS
```

The test suite covers the accumulated J3-J6 offline implementation, including:

- deterministic prechecks,
- semantic fixture handling,
- contract validation,
- failure injection,
- persistence failure,
- repeatability machinery,
- J6 permission boundaries,
- live-response validation,
- live-runner failure attribution,
- broken diagnostic rendering,
- raw-response capture failures,
- model identity separation,
- and provider attempt limits.

The regression suite is offline and deterministic.

---

## Local Test Execution

Python 3.11 or newer is required.

Verification was performed with Python 3.14.3.

From PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The ordinary offline regression suite does not require a Jev API key.

---

## Live Provider Code

The repository retains the bounded J6 provider adapter and R1/X1 entrypoints used during the Human-Gated study:

```text
src/j6_live_provider.py
j6_live_r1.py
j6_live_x1.py
```

They are retained for implementation provenance.

J6 is now:

```text
COMPLETE / FROZEN
```

The frozen study does not authorize additional J6 live calls, repeatability runs, or exploratory provider calls.

---

## Claim Boundaries

This repository does **not** establish:

- general Jev accuracy,
- Jev superiority over other decision models,
- statistical reliability,
- calibration quality,
- production readiness,
- production safety,
- certification suitability,
- autonomous governance capability,
- generalization across domains,
- provider-internal execution verification,
- universal permission semantics,
- or production runtime control suitability.

Only two Human-Gated J6 live semantic calls were executed.

Each live scenario was executed exactly once.

The project is a bounded integration study.

---

## Research Interpretation

The PoC suggests that the difficult part of integrating a probabilistic decision component is not merely obtaining a useful semantic judgment.

The harder integration problem is preserving the boundaries around that judgment:

```text
What was observed?
What was validated?
What evidence was retained?
Where did a failure occur?
What permission conditions apply?
Who retains authority over state transition?
```

This supports studying probabilistic decision components as bounded elements inside deterministic governance structures rather than as substitutes for governance authority.

---

## Repository Status

```text
J0-J2 baseline       FROZEN
J3                   COMPLETE
J4                   COMPLETE
J5                   COMPLETE
J6                   COMPLETE / FROZEN

Final regression     124 / 124 PASS
J6 live calls        2 total
Additional calls     0
Runtime evidence     local / Git-excluded
```

Final J6 closeout documentation:

[`docs/Jev_PoC_J6_Closeout_v0.1_20261002.md`](docs/Jev_PoC_J6_Closeout_v0.1_20261002.md)

---

## Scope

This repository is a research artifact.

It is intended to make bounded runtime-governance assumptions, failure boundaries, evidence handling, and permission separation inspectable.

It is not production control software, certification evidence, or a claim of proven AI safety.
```
