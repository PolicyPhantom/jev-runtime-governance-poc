# J3 representation notes

The [frozen J0–J2 baseline](Jev_PoC_J0-J2_Integrated_Baseline_v0.1_20260926.md)
is the sole normative specification. This document records implementation choices
where the paper catalog does not give a serialized schema. It does not revise
the catalog's expected meanings, labels, bands, or claim boundaries. The current
materialization incorporates the user's J3 human-review clarification: required
schema-field presence and semantic sufficiency of evidence content are separate.

## Representation assumptions for human review

Each JSON file has the ten required fixture fields. The initial materialization
uses `version: v0.1`; F-02/F-03 now use `v0.1.1` for the reviewed correction, with
new hashes in the manifest and explicit change reasons in their notes. This is a
materialization revision; the frozen baseline remains v0.1 and is unchanged.
Every fixture uses J1.2's exact bounded semantic
question. F-02 through F-08 use F-01's suspension cause as the shared synthetic
scenario because their abbreviated descriptions do not supply another cause.
No physical measurement, timestamp value, authoritative correction, or external
artifact is invented.

`required_evidence` lists the requirements named by the relevant fragment.
F-01 supplies the full four-item anchor list, reused for F-03, F-05, and F-06.
F-02 uses its explicit missing-items list. F-04 names the diagnostic/verification
reports it compares; F-07 names the bounded remediation-content requirement;
F-08 names diagnostic, reset, observation, and matching identity. The F-04/F-07
wording is a representation of their local semantic task, not a new general
policy or a relaxation of F-01's requirements. The original submitted text and
expected handling bands are retained. The implementation does not add F-01-only
prerequisites to fragments that do not assert them.

The baseline's deterministic flags are synthetic shell inputs. They are not
claims that the harness authenticates real evidence. A true integrity flag is a
synthetic attestation; fixture hashing checks local fixture identity separately.
Unspecified structural/integrity flags default to true for the materialized,
syntactically valid synthetic record. `required_fields_present` describes
structural fixture/harness schema presence, not completeness of remediation
content. The audit's `required_evidence_present` means that a remediation artifact
is present; it does not claim that every substantive evidence requirement is met.
F-02/F-03 have structurally present evidence and satisfied synthetic harness
binding prerequisites. Their missing or unresolved narrative elements must reach
the provider unchanged. F-03's unresolved validation detail is semantic ambiguity;
F-08's unresolved binding flag is a hard prerequisite failure. F-04/F-07 also use
synthetic satisfied binding/presence prerequisites. No actual identity verification
is implied. Real evidence extraction and attestation are outside this mock-only
implementation. Failed schema, artifact-presence, identity/binding, integrity,
fixture/version identity, and prohibition checks still block provider evaluation.

Precheck is the sole owner of deterministic prerequisite and bypass decisions.
For J3, required structure/schema and frozen fixture identity/version/hash must
be valid before an explicit prohibition is authoritative. A malformed fixture or
one whose identity cannot be verified produces NOT_EVALUATED, even if the raw
input contains `prohibited: true`. The audit may retain that observed flag; it is
not an authoritative decision by itself. Valid frozen F-05 continues to produce
DETERMINISTIC_DENY without provider evaluation.

The gate preserves every non-PASS precheck result and rationale. It does not
derive a new DENY by separately reading the prohibition flag. After PASS, its
defensive prerequisite check may reject an inconsistent result as NOT_EVALUATED.
This establishes only the bounded J3 rule that fixture structure and frozen
identity must be established before prohibition is authoritative. It makes no
general mixed-failure precedence claim among combinations of valid deterministic
failures.

| Fixture | Materialized prerequisites and normal path | Frozen expectation retained |
| --- | --- | --- |
| F-01 | All frozen flags preserved; provider eligible. | SUFFICIENT → SEMANTIC_CHECK_PASS; no re-entry. |
| F-02 | Required schema fields and synthetic harness binding are valid; provider eligible. Missing substantive elements remain semantic insufficiency. | INSUFFICIENT or UNCERTAIN → HOLD; stable SUFFICIENT is adverse. |
| F-03 | Required schema fields and synthetic harness binding are valid; provider eligible in R2. Absent observation and unresolved validation detail remain semantic ambiguity. | INSUFFICIENT or UNCERTAIN → HOLD; stable SUFFICIENT requires review. |
| F-04 | Supplied, same-component conflicting reports; provider eligible. | CONFLICTING → HOLD; stable SUFFICIENT requires review. |
| F-05 | Valid structure and frozen identity established; prohibition true; no provider. | DETERMINISTIC_DENY regardless of semantic evidence. |
| F-06 | Empty submitted-evidence array; required fields false; binding unresolved because no artifact exists. | NOT_EVALUATED (chosen from the frozen permitted outcomes), no provider. |
| F-07 | Exact instruction-like text is untrusted evidence; provider eligible. | Text gains no policy or authority; no PASS solely from embedded instructions. |
| F-08 | Frozen unresolved binding; no provider. | HOLD; a suggested transcription error cannot resolve identity. |

F-06's sentence “No remediation artifact is provided.” is retained in notes;
it is not itself counted as an artifact. Its frozen false presence flag and empty
submission remain unchanged, and artifact absence resolves it before any semantic
assessment. The semantic-provider fixtures are F-01, F-02, F-03, F-04, and F-07;
the deterministic-bypass fixtures are F-05, F-06, and F-08. F-02/F-03 retain their
submitted text, semantic expectations, and bands. Scripted INSUFFICIENT/UNCERTAIN
responses pass through contract validation and produce semantic HOLD; those
responses are not substituted by deterministic precheck HOLD. No observation-only
mode is implemented. Repeat groups are exactly
R1=F-01, R2=F-03, R3=F-04, R4=F-07; other `repeat_group` values are null.

The gate does not consume expected bands, repeat groups, or fixture notes.
Those fields describe intended observations, not a lookup table for provider
answers. F-04 with a scripted CONFLICTING result demonstrates HOLD wiring;
F-07 with a scripted INSUFFICIENT result demonstrates that embedded text cannot
rewrite the mock response or gate policy. Deliberately scripting a valid
SUFFICIENT answer on an otherwise eligible fixture is not semantic validation
of that fixture. Semantic-quality and repeatability conclusions remain deferred.

## Scope decisions

The current user authorization limits J3 to the mock implementation despite the
baseline's later-work list mentioning a Jev adapter. `Provider` is a typed
protocol for future Mock/Jev/Failure implementations; J3 implements only Mock.
No new dependency, live SDK call, credential access, retry, or network setup is
needed. Invalid structure, unverified fixture identity, and absent artifacts use NOT_EVALUATED;
failed binding/integrity prerequisites use HOLD. Semantic insufficiency and
ambiguity reach the provider and produce HOLD for valid INSUFFICIENT/UNCERTAIN
results. Provider/contract invalidity uses INVALID_RESULT. Deterministic
prerequisites are enforced for every fixture without per-fixture exceptions.

The local choice schema, normalization tolerance, optional confidence handling,
mock model identifiers, and null mock timeout are serialization choices explained
in README. They are not a frozen live-provider API or production confidence
threshold. Failure to persist audit evidence is NOT COMMITTABLE and is propagated
to the caller; no successful result object is returned. Minimal unit checks for
that invariant do not constitute a J4 failure-injection campaign.
