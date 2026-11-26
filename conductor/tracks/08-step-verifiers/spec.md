# T08 — Step verifiers

Owner: [#9](https://github.com/edithatogo/Iatonoesis/issues/9). Research-only. Canonical tasks: [programme](../../../contracts/programme.v1.json).

## E22: Stroke pathway conformance

Classification: adaptation from documented process mining; setting: patient safety.

Workflow: Auditor checks delayed or unverified steps.

Input: synthetic events, orders and notes. Output: completed/late/missing/inapplicable/unverifiable.

Comparator: event-log rules. Failure and reviewer: order mistaken for completion; auditor verifies.

Feasibility cohort: 150 simulated episodes. Model metric: false completion and missed-step recall. Workflow outcome: audit time and verified timely care.

## E23: Analytical workflow verification

Classification: adaptation; setting: research.

Workflow: Analyst resolves discrepancies before release.

Input: synthetic protocol, code, logs and outputs. Output: step-level failures with evidence.

Comparator: executable checks and code review. Failure and reviewer: successful run mistaken for sound design; statistician reviews.

Feasibility cohort: 100 injected defects. Model metric: defect recall and false pass. Workflow outcome: review effort and errors prevented.

## E24: Transfer handover verification

Classification: hypothesis; setting: rural patient care.

Workflow: Coordinator checks explicit acceptance, never delays urgent transfer.

Input: synthetic transfer and acknowledgment logs. Output: obligation verification and provenance.

Comparator: checklist and deterministic event matching. Failure and reviewer: delivered mistaken for accepted; coordinator checks.

Feasibility cohort: 100 transfers. Model metric: false closure and incomplete handover recall. Workflow outcome: unresolved obligations and workload.

All claims and research progress remain unverified until the corresponding evidence is captured.
