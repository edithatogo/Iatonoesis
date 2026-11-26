# T04 — Decision models

Owner: [#5](https://github.com/edithatogo/Iatonoesis/issues/5). Research-only. Canonical tasks: [programme](../../../contracts/programme.v1.json).

## E10: Referral prioritisation

Classification: documented underlying capability; setting: patient care.

Workflow: Clinician reviews urgency; no autonomous decision.

Input: synthetic referrals and prioritisation criteria. Output: urgency, supporting criteria and abstention.

Comparator: deterministic criteria and clinician comparator. Failure and reviewer: serious under-triage; clinician retains decision.

Feasibility cohort: 300 scenarios. Model metric: weighted kappa and serious under-triage. Workflow outcome: triage minutes and appropriate timing.

## E11: Credentialing evidence

Classification: adaptation; setting: governance.

Workflow: Committee reviews criterion support.

Input: synthetic portfolios and scope requirements. Output: supported/unsupported/conditional/insufficient.

Comparator: mandatory-field and explicit rules. Failure and reviewer: false competency equivalence; specialty reviewer checks.

Feasibility cohort: 80 synthetic portfolios. Model metric: false equivalence and selective accuracy. Workflow outcome: review time and rework.

## E12: Justified clinical variation

Classification: hypothesis; setting: governance.

Workflow: M&M reviewers investigate unresolved deviations.

Input: synthetic pathway cases and context. Output: appropriate variation/potential deficiency/unresolved.

Comparator: binary compliance rules. Failure and reviewer: unsupported exoneration; clinical reviewer checks contemporaneous evidence.

Feasibility cohort: 100 counterfactual pairs. Model metric: false exoneration and exception F1. Workflow outcome: review effort and actionable findings.

All claims and research progress remain unverified until the corresponding evidence is captured.
