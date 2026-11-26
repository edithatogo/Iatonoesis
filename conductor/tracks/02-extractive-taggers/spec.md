# T02 — Extractive taggers

Owner: [#3](https://github.com/edithatogo/Iatonoesis/issues/3). Research-only. Canonical tasks: [programme](../../../contracts/programme.v1.json).

## E04: Discharge obligations

Classification: adaptation; setting: patient care.

Workflow: Discharging clinician confirms outstanding actions.

Input: synthetic discharge notes. Output: exact action-owner-deadline-condition spans.

Comparator: keyword and negation rules. Failure and reviewer: completed action marked outstanding; discharging team reviews.

Feasibility cohort: 200 synthetic summaries. Model metric: tuple F1 and missed obligations. Workflow outcome: reconciliation minutes and overdue tasks.

## E05: Registry abstraction

Classification: documented underlying capability; setting: research.

Workflow: Registry abstractor validates tags.

Input: synthetic phenotype and intervention notes. Output: source spans, assertion, experiencer and temporality.

Comparator: terminology and negation rules. Failure and reviewer: family phenotype attributed to patient; abstractor reviews.

Feasibility cohort: 150 synthetic records. Model metric: span and assertion F1. Workflow outcome: abstraction time and completeness.

## E06: Operational constraint tagging

Classification: hypothesis; setting: governance.

Workflow: Quality team examines reported barriers, not individuals.

Input: synthetic incidents and complaints. Output: context spans and reported/verified status.

Comparator: incident categories and keyword matching. Failure and reviewer: criticism treated as fact; quality reviewer checks.

Feasibility cohort: 150 synthetic narratives. Model metric: span F1 and factor recall. Workflow outcome: actionable hazards and review time.

All claims and research progress remain unverified until the corresponding evidence is captured.
