# T05 — Rerankers

Owner: [#6](https://github.com/edithatogo/Iatonoesis/issues/6). Research-only. Canonical tasks: [programme](../../../contracts/programme.v1.json).

## E13: Context-sensitive policy ranking

Classification: adaptation; setting: patient care and governance.

Workflow: Clinician reviews approved source passage.

Input: questions, metadata and fixed candidate sets. Output: reordered applicable passages.

Comparator: lexical/dense initial ranking. Failure and reviewer: inapplicable high-ranked passage; clinician checks metadata.

Feasibility cohort: 150 questions. Model metric: nDCG@5 and applicable recall. Workflow outcome: time to correct source.

## E14: Trial matching

Classification: documented underlying capability; setting: research access.

Workflow: Coordinator reviews uncertain candidates.

Input: synthetic profiles and public eligible trials. Output: ranked trials and unresolved criteria.

Comparator: lexical/dense ranking. Failure and reviewer: missing value suppresses eligible trial; coordinator checks.

Feasibility cohort: 100 profiles. Model metric: eligible recall@10 and nDCG. Workflow outcome: screening time and opportunity.

## E15: Analogous incident mechanisms

Classification: hypothesis; setting: governance.

Workflow: Reviewers investigate previous controls.

Input: synthetic incidents and fixed historical shortlist. Output: ranked mechanism analogues.

Comparator: category and embedding ranking. Failure and reviewer: surface similarity mistaken for mechanism; investigator checks.

Feasibility cohort: 100 queries. Model metric: precision@5 and nDCG. Workflow outcome: controls rediscovered and investigation time.

All claims and research progress remain unverified until the corresponding evidence is captured.
