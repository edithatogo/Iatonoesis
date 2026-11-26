# External CQL scalar replay — exploratory

T08/#9, T18/#19 and T14/#15; dependent on frozen upstream fixture PR #33. This is an independently sourced published fixture check, not independent clinical adjudication. No cases used in model training, but the fixture contents and labels were visible when defining the supported grammar. This is **exploratory**, not a blinded confirmatory experiment; preserve that exposure when designing later held-out studies.

Bounded deterministic evaluator for Boolean/null operations, scalar integer arithmetic/comparison, simple if/else and case expressions. No eval, arbitrary code execution or real clinical guidance. Unsupported expressions return unavailable. Type-aware comparison distinguishes null, Boolean and integer values. Verify the pinned upstream revision, licence assertion, derived dataset SHA-256 and case IDs before replay. No fabricated development/calibration splits. Actual upstream CQL engine and independently frozen learned challenger remain separate gates.

Results: 39/39 logical, 9/9 conditional, no unavailable cases. RED: module absent; GREEN: five local tests pass, including exact published-fixture replay. Reconstructed the retrieved derived JSON bytes and matched both frozen SHA-256 digests. Source and test Git blob identities recorded in receipt. No full local checkout or Python 3.15.2 hosted result yet. Result is not a certification of CQL, full language coverage or clinical effectiveness.

Reproduce from the repository checkout:

```sh
python -m iatonoesis.cql_external_replay --fixtures datasets/fixtures/cql-external-holdout-v0.1.0 --output /tmp/cql-replay.json
python -m pytest -q tests/test_cql_external_replay.py
```

Versioned [receipt](../../results/exploratory/cql-external-scalar-replay-v0.1.0.json). The full case-level JSON is deterministically reproduced by the CLI and its byte digest is asserted by a regression test. Keep the earlier #33 acquisition and frozen source provenance intact. No canonical scientific task accepted.
