# Jev PoC J6 Specification v0.3

**Status:** FROZEN
**Freeze Date:** 2026-09-30 JST
**Human Gate:** APPROVED
**Specification Version:** v0.3

---

## 1. Purpose

J6 evaluates two bounded consumer-side governance claims for a hosted AI component.

### Primary Claim

Can the consumer reconstruct the bounded decision path from retained evidence?

### Secondary Claim

For the examined consumer action and decision time, does the available evidence support permission under the identified local authority terms and stated assumptions?

The following distinctions are mandatory:

```text
decision reconstructability
!= decision correctness
!= permission validity
!= provider execution truth
!= general compliance

J6 does not independently verify the provider's hidden execution implementation.
2. Approval Object
The J6 approval object is:
Provider-managed Jev service under bounded conditions.

Bounded Conditions
Intended use
= bounded semantic assessment of remediation evidence

Input scope
= synthetic, versioned research inputs only

Data scope
= no production data
  no customer data
  no sensitive data
  no operational data

Decision role
= provider output is evidence/input to a consumer-side determination
  and is not itself authority, permission, or final approval

Existing J2 fixtures remain frozen and unchanged.
J6 research inputs use a separate namespace and are versioned independently.
3. Explicitly Not Assumed
J6 does not assume the following as general requirements:
exact model version approval
exact implementation approval
requested_model == resolved_model
every version change = material change
every transition = fresh approval
provider-reported identity = independently verified execution

A difference such as:
requested_model = jev-latest
resolved_model  = jev-1.13.0

does not, by itself, constitute J6 failure.
Requested/resolved identity inequality is not evidence of implementation drift.
4. Three-Layer Semantic Model
J6 maintains three distinct semantic layers.
Layer 1 — Existing Component Outcome
SEMANTIC_CHECK_PASS
SEMANTIC_CHECK_HOLD
DETERMINISTIC_DENY
NOT_EVALUATED
INVALID_RESULT

Layer 2 — Decision Reconstruction
RECONSTRUCTED
INSUFFICIENT_EVIDENCE
NOT_ASSESSED

Layer 3 — Permission Applicability
SUPPORTED
NOT_SUPPORTED
INDETERMINATE
NOT_ASSESSED

These layers do not automatically determine one another.
5. Decision Reconstruction Semantics
RECONSTRUCTED
Claim-critical retained evidence is sufficient to reconstruct:
- what information the consumer used,
- which rule was applied,
- what decision resulted,
- and how the evidence supports the recorded decision path.
RECONSTRUCTED
!= correct
!= authorised
!= independently verified provider execution

INSUFFICIENT_EVIDENCE
The bounded decision path cannot be reconstructed because claim-critical evidence is one or more of:
missing
conflicting
unlinked
sequence-unresolved
integrity-unresolved

INSUFFICIENT_EVIDENCE
!= wrong
!= unsafe
!= unauthorised

NOT_ASSESSED
Decision reconstruction assessment was not performed.
PARTIALLY_RECONSTRUCTED is not a formal J6 status.
Incomplete details are recorded separately rather than represented by a partial status.
6. Decision Reconstruction Reason Codes
DR_EVIDENCE_COMPLETE

DR_MISSING_DECISION_INPUT
DR_MISSING_APPLIED_RULE
DR_MISSING_DECISION_RECORD
DR_BROKEN_EVIDENCE_LINKAGE
DR_SEQUENCE_UNRESOLVED
DR_CONFLICTING_RECORDS
DR_INTEGRITY_UNRESOLVED

DR_OUT_OF_SCOPE
DR_NOT_RUN

Additional detail may be retained in:
missing_evidence
reconstruction_limit

7. Decision Reconstruction Required Evidence
The minimum claim-critical evidence set is:
decision_id
examined_action
decision_time

decision_input_references
applied_rule_reference
decision_result

evidence_linkage
evidence_integrity_reference

A provider response is not universally required.
For example, a deterministic precheck may produce a reconstructable consumer decision path without a provider call.
The governing principle is:
Evidence is required when it is claim-critical to the examined decision path.

8. Permission Applicability Semantics
SUPPORTED
Available evidence establishes that the necessary permission conditions are satisfied under the identified applicable authority path for the examined action at the examined decision time.
SUPPORTED
!= general legal compliance
!= continuous authorisation
!= provider-side authorisation

NOT_SUPPORTED
Available evidence affirmatively establishes that a necessary permission condition is not satisfied.
Examples include:
operative restriction
explicit exclusion
unmet restoration condition
approval not effective
required exception confirmed absent

NOT_SUPPORTED requires affirmative negative evidence.
INDETERMINATE
Claim-critical permission facts are:
missing
conflicting
unresolved

Important rule:
Missing evidence
→ INDETERMINATE

Missing evidence
!= NOT_SUPPORTED

NOT_ASSESSED
Permission applicability assessment was not performed.
9. Permission Reason Codes
PA_TERMS_SATISFIED
PA_VALID_EXCEPTION_APPLIES
PA_RESTORATION_CONDITIONS_SATISFIED

PA_ACTIVE_RESTRICTION
PA_EXPLICIT_EXCLUSION
PA_RESTORATION_CONDITION_UNMET
PA_APPROVAL_NOT_EFFECTIVE
PA_REQUIRED_EXCEPTION_ABSENT

PA_AUTHORITY_UNRESOLVED
PA_EFFECTIVE_TIME_UNRESOLVED
PA_SCOPE_UNRESOLVED
PA_DELEGATION_UNRESOLVED
PA_EXCEPTION_UNRESOLVED
PA_REQUIRED_CONDITION_EVIDENCE_MISSING
PA_CONFLICTING_AUTHORITY_EVIDENCE

PA_OUT_OF_SCOPE
PA_NOT_RUN

PA_REQUIRED_EXCEPTION_ABSENT means that the required exception has been sufficiently established as absent.
Failure to locate evidence of an exception is not sufficient by itself.
10. Permission Required Evidence
The minimum permission-assessment evidence set is:
authority_reference
authority_scope
authority_effective_time_or_interval

examined_action
decision_time

applicable_permission_or_restriction_terms
condition_evidence_references

The following become mandatory when claim-critical to the applicable authority path:
restoration_condition
delegation
exception

The governing principle is:
Evidence is required only when it is claim-critical for the examined decision and applicable authority path.

11. Applied Rule and Applicable Authority
The following fields are intentionally distinct.
applied_rule_reference
The rule actually used by the consumer decision path.
authority_reference
The authority applicable to the permission assessment for the examined action and decision time.
Therefore the following is a valid and meaningful state:
applied_rule_reference = Rule/Policy v1
authority_reference    = Rule/Policy v2

A difference between these references is not automatically an evidence conflict.
One records actual consumer behaviour.
The other identifies the authority governing permission applicability.
12. Decision Reconstruction Precedence
Decision reconstruction is classified in the following order:
1. Assessment not performed
   → NOT_ASSESSED

2. Claim-critical evidence is
   missing / conflicting / unlinked /
   sequence-unresolved / integrity-unresolved
   → INSUFFICIENT_EVIDENCE

3. Required evidence is complete
   and the bounded decision path is reconstructable
   → RECONSTRUCTED

J6 does not use percentage completeness.
If a claim-critical item is unresolved, the result is not RECONSTRUCTED.
13. Permission Applicability Precedence
Permission applicability is classified in the following order:
1. Assessment not performed
   → NOT_ASSESSED

2. Claim-critical facts concerning the applicable authority,
   scope, effective time, conditions, delegation, exception,
   or restoration terms are missing, conflicting, or unresolved
   → INDETERMINATE

3. After resolving the applicable authority path,
   including all claim-critical exception and restoration terms,
   an operative restriction, exclusion, or unmet necessary
   condition remains applicable to the examined action
   at the decision time
   → NOT_SUPPORTED

4. After resolving the applicable authority path,
   all necessary permission conditions applicable to
   the examined action at the decision time are satisfied
   → SUPPORTED

5. Otherwise
   → INDETERMINATE

Normative clarification:
A restriction, exclusion, or unmet necessary condition triggers NOT_SUPPORTED only if it remains operative for the examined action at the decision time after applying the resolved applicable authority path, including its claim-critical exception and restoration terms.

A valid exception does not, by itself, establish that every other necessary permission condition is satisfied.
14. Conflict Precedence
Relevant unresolved conflict outranks a positive or negative permission conclusion.
For example:
supporting evidence
+
claim-critical conflicting evidence
→ INDETERMINATE

Likewise:
restriction evidence
+
potentially overriding exception unresolved
→ INDETERMINATE

J6 does not select only the evidence favourable to a desired conclusion.
15. Cross-Layer Non-Precedence Rules
The following automatic conversions are prohibited:
SEMANTIC_CHECK_PASS
→ SUPPORTED

RECONSTRUCTED
→ SUPPORTED

SUPPORTED
→ provider result accepted

missing evidence
→ NOT_SUPPORTED

requested/resolved identity mismatch
→ automatic permission failure

Component outcome validity, decision reconstructability, and permission applicability remain distinct.
16. Scenario Namespace
J6 uses a namespace separate from the frozen J2 fixtures.
J6-PERM-R1 — Restoration Case
Direction:
restricted
→ technical remediation
→ permission restoration assessment

Purpose:
Separate technical recovery from permission restoration.

A valid J6 outcome may be:
component_outcome
= SEMANTIC_CHECK_PASS

decision_reconstruction_status
= RECONSTRUCTED

permission_applicability_status
= NOT_SUPPORTED

This means:
- the remediation evidence produced an acceptable semantic component result,
- the consumer decision path is reconstructable,
- but the applicable restoration permission conditions are affirmatively not satisfied.
If the restoration-condition evidence is instead unresolved:
permission_applicability_status
= INDETERMINATE

If the applicable restoration conditions are resolved and satisfied:
permission_applicability_status
= SUPPORTED

J6-PERM-X1 — Restriction / Exclusion Contrast Case
Direction:
previously permitted
→ newer applicable authority restricts the action
→ older consumer rule remains in use
→ post-response permission applicability assessment

Purpose:
Separate the rule actually used by the consumer from the authority applicable to permission at the examined decision time.

A valid state may be:
applied_rule_reference
= old rule

authority_reference
= newer effective authority

decision_reconstruction_status
= RECONSTRUCTED

permission_applicability_status
= NOT_SUPPORTED

This means:
- the consumer decision path can be fully reconstructed,
- the old rule explains why the consumer action occurred,
- but the newer applicable authority does not support permission for that action.
If an applicable exception remains unresolved:
permission_applicability_status
= INDETERMINATE

If a valid applicable exception is resolved and all other necessary permission conditions are satisfied:
permission_applicability_status
= SUPPORTED

17. Governance Boundary Scenarios
The following are boundaries, not default direct J6 fixtures.
E-03 + C-02 — Assurance Applicability Boundary
Historical evidence may remain historically true while being insufficient to support a later or current applicability claim.
Historical truth does not automatically establish continuing applicability.
B-02 — Provider-Dependent Timing Limit
Post-response evidence cannot retroactively prevent provider-side processing that has already occurred.
J6 does not independently establish:
provider fallback history
provider routing history
provider processing region
exact hidden provider execution path

18. Timing Semantics
The current J6 mechanism is:
post-response admissibility determination

J6 may assess, after response receipt:
- response validity,
- retained evidence,
- decision reconstruction,
- permission applicability,
- prospective downstream consumer handling.
J6 does not claim to have demonstrated:
provider inference prevented
data transmission prevented
provider routing prevented
provider fallback prevented
remote execution cancelled
pre-execution enforcement established

Post-response rejection cannot undo already completed provider-side processing.
19. Transition Authority
For the current bounded J6 PoC:
Relevant transition → Human Gate

This is a current PoC operating rule, not a universal claim that every transition in every system requires fresh human approval.
A future pre-approved change envelope may permit automated continuation or restoration under bounded conditions.
Such an envelope is not part of the current J6 operational default.
20. Visibility Semantics
J6 distinguishes:
CONSUMER_OBSERVED
PROVIDER_REPORTED
INDEPENDENTLY_VERIFIED

Example:
requested_model = jev-latest
→ consumer-observed / consumer-controlled

resolved_model = jev-1.13.0
→ provider-reported

exact artifact and serving stack that actually executed
→ not independently verified by current J6

Provider-reported metadata may be retained as attributed evidence.
It must not be represented as independently verified execution proof.
21. Surviving Design Invariants
I-1 — Claim-Scoped Evidence
Evidence supports only claims within its substantive and temporal scope.
Historical evidence can remain historically valid while no longer being sufficient for a current or continuous applicability claim.
I-2 — Change Is Not Materiality
Identity movement, version movement, recovery, or change does not by itself determine materiality or an authorisation trigger.
I-3 — Permission Follows Applicable Authority
Permission depends on the applicable authority terms, conditions, delegation, and exceptions.
Technical success or historical approval alone does not establish current permission.
I-4 — Prevention Has a Temporal Boundary
Information or intervention obtained after an action cannot retroactively prevent an action that has already completed.
I-5 — Visibility Limits the Claim
Where an approval-relevant execution property is not sufficiently observable, the consumer cannot claim direct verification beyond the available evidence.
Missing evidence proves neither fault nor compliance.
22. Explicit Non-Claims
J6 does not establish that:
- Jev experienced longitudinal implementation drift.
- The provider performed a hidden update.
- A concrete model identifier fully identifies the implementation.
- Provider-reported metadata proves the actual executing artifact.
- The exact serving stack was independently verified.
- Provider routing history was independently verified.
- Provider fallback history was independently verified.
- Provider processing region was independently verified.
- Every version change is material.
- Every transition universally requires fresh human approval.
- Missing provenance implies unsafe operation.
- Technical recovery implies permission restoration.
- Historical approval implies present permission.
- Post-response rejection prevented prior provider processing.
- J6 establishes production readiness.
- J6 establishes general legal or regulatory compliance.
23. Specification STOP Conditions
Specification interpretation, fixture design, implementation, or later evaluation must STOP for Human Review if any of the following occurs:
provider-hidden execution is asserted as independently verified

exact implementation identity becomes mandatory
without explicit claim-specific justification

version movement is automatically treated as material

technical recovery is treated as permission restoration

missing evidence is treated as negative evidence

provider-reported information is represented as
independently verified execution

post-response assessment is represented as
pre-execution prevention

approved J6 scope is expanded without Human Gate

24. Freeze Basis
J6 Specification v0.3 was reviewed before freeze using an independent pre-freeze review.
The review result before correction was:
BLOCKER = 0
MAJOR   = 0
MINOR   = 1
NOTE    = 0

The single MINOR concerned permission-precedence clarity where a resolved exception may override an underlying restriction.
That MINOR was corrected in Section 13 before freeze.
At freeze:
Unresolved BLOCKER = 0
Unresolved MAJOR   = 0
Unresolved MINOR   = 0

The Human Gate approved specification freeze on 2026-09-30 JST.
25. Frozen-State Rule
This document is the frozen J6 specification baseline.
Implementation observations do not retroactively modify v0.3.
If later implementation or live evaluation reveals:
- an unexpected behaviour,
- an unmodelled edge case,
- an implementation limitation,
- or a specification defect,
the observation must be retained as evidence against this frozen baseline.
If a specification revision becomes necessary, it must be issued as a later version.
v0.3 remains preserved as the historical frozen specification.

END OF J6 SPECIFICATION v0.3
