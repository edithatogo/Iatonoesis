# Common run contracts v0.1.0

Ownership: T00.002 (#1); consumers T14.001–004 (#15), T01–T08 (#2–#9).
Companion: [programme](programme.v1.json), [benchmark candidates](benchmark-candidates.v1.json), [comparative protocol](../research/comparative-study.md).

This is a minimal executable structural contract for a paired case-level comparison. The earlier [run-manifest example](run-manifest.example.json) is illustrative only, not a valid result. The Python module validates three linked JSON records; call validate_dataset, validate_experiment and validate_result in order. Test fixtures show the complete field structure.

- Dataset: ID, synthetic/public kind, source, revision, raw SHA-256, approved-rights assertion with licence/evidence locator, reference kind/revision/hash, grouping keys and row-to-partition assignments. Each declared group must be disjoint across development/calibration/test. Missing provenance or unresolved rights block use.
- Experiment: stable owning task, exact dataset and reference identity, frozen test IDs, metric/unit, seed, declared arms, common case/time budget and claim boundary. Include at least one deterministic comparator. Generalist, classical, specialist and hybrid arms are distinguished; unavailable arms remain visible.
- Result: source commit, canonical experiment hash, linked data/reference hashes, seed, environment, claim boundary, one record for every planned arm. Executed arms require predictions hash, elapsed time and consistent total/scored/abstained/errors counts. Learned arms require exact model metadata. Failed, skipped or unavailable arms require a reason and must not contain invented results.

Canonical JSON hashing is sorted-key UTF-8, compact separators and no nonfinite numbers. The validators check declared metadata and identity consistency, not actual file bytes, truthful rights evidence, label independence, installed model weights or clinical validity. Actual runner verification of files, manifests and predictions is T00.003–004; task-specific metrics, intervals and aggregation are T00.005; real model qualification is T00.006. No clinical authorisation is inferred. These are initial case-classification denominators, not yet comprehensive ranking, extraction, sequence or graph metric contracts.

Local isolated test receipt (not a repository checkout): Python 3.13.5, pytest 9.0.2, initial test collection failed with missing run_contracts module; after implementation, 12 tests passed. Command: PYTHONPATH=src python -m pytest -q tests/test_run_contracts.py. Hosted Python 3.15.2 full suite still required. Fixture hashes and approvals in unit tests are placeholders, not real datasets. No canonical task is accepted on this receipt alone.
