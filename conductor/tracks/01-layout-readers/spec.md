# T01 — Layout-aware document readers

Owner: [#2](https://github.com/edithatogo/Iatonoesis/issues/2). Research-only. Canonical tasks: [programme](../../../contracts/programme.v1.json).

## E01: Rural clinical referral reading

Classification: adaptation; setting: rural patient access.

Workflow: Referral staff validate fields before import.

Input: synthetic scans and reports. Output: source-linked fields, dates and missingness.

Comparator: OCR and fixed templates. Failure and reviewer: result linked to wrong date; receiving clinician reviews region.

Feasibility cohort: 150 varied referrals. Model metric: field linkage F1 and critical omission. Workflow outcome: processing time and rework.

## E02: Machine-readable clinical policies

Classification: adaptation; setting: governance.

Workflow: Policy owner approves structured requirements.

Input: rights-clear or synthetic standards pages. Output: hierarchy, rows, qualifiers and source boxes.

Comparator: text extraction and conventional table parser. Failure and reviewer: exception overgeneralised; policy owner adjudicates.

Feasibility cohort: 100 annotated pages. Model metric: qualifier-link F1. Workflow outcome: policy review hours.

## E03: Longitudinal historical records

Classification: hypothesis; setting: research and continuity.

Workflow: Abstractor checks chart and pedigree candidates.

Input: synthetic historical records. Output: time-linked observations and relationships.

Comparator: OCR plus manual abstraction. Failure and reviewer: wrong pedigree edge; genetics reviewer checks original.

Feasibility cohort: 40 synthetic records. Model metric: relationship and temporal-link accuracy. Workflow outcome: abstraction time and completeness.

All claims and research progress remain unverified until the corresponding evidence is captured.
