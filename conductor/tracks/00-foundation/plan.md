# T00 — Research infrastructure

Issue [#1](https://github.com/edithatogo/Iatonoesis/issues/1). Stable task IDs; canonical [programme](../../../contracts/programme.v1.json). Cross-track prerequisites: none. Downstream consumers: T01 (#2), T02 (#3), T03 (#4), T04 (#5), T05 (#6), T06 (#7), T07 (#8), T08 (#9), T09 (#10), T10 (#11), T11 (#12), T12 (#13), T13 (#14), T14 (#15), T15 (#16), T16 (#17), T17 (#18), T18 (#19), T19 (#20). [Roadmap](../../roadmap.md).

- [ ] **T00.001** — Reconcile starter, gitlink, community policy and solo-maintainer settings (#1)
  - Depends on: none.
  - Accept: Verify exact gitlink, provider status, actual protected checks, audit receipt; record unobserved settings.
  - Evidence: pending; record exact revision, commands, fixtures and outcomes.
- [ ] **T00.002** — Define experiment/data/result contracts and validation (#1)
  - Depends on: T00.001.
  - Accept: Schema rejects missing provenance, unknown state, inconsistent metric denominator and leakage.
  - Evidence: pending; record exact revision, commands, fixtures and outcomes.
- [ ] **T00.003** — Build deterministic run harness and synthetic dataset manifest (#1)
  - Depends on: T00.002.
  - Accept: Two same-seed runs produce identical canonical outputs; record hash, runtime, failures.
  - Evidence: pending; record exact revision, commands, fixtures and outcomes.
- [ ] **T00.004** — Freeze calibration/development/test partitions and rights ledger (#1)
  - Depends on: T00.003.
  - Accept: Independent holdouts, site/temporal split where appropriate; no protected data in Git.
  - Evidence: pending; record exact revision, commands, fixtures and outcomes.
- [ ] **T00.005** — Implement common metrics and confidence intervals (#1)
  - Depends on: T00.004.
  - Accept: Known analytic fixtures, denominator/abstention tests and seeded bootstrap; differential reference.
  - Evidence: pending; record exact revision, commands, fixtures and outcomes.
- [ ] **T00.006** — Qualify CPU-first model adapter and optional HF runtime (#1)
  - Depends on: T00.005.
  - Accept: Exact model revision, licence, memory/latency budget, offline fail-closed; no default network.
  - Evidence: pending; record exact revision, commands, fixtures and outcomes.
- [ ] **T00.007** — Enable CI, one-command assurance, results storage and issue reconciliation (#1)
  - Depends on: T00.006.
  - Accept: Required hosted checks, exact-head receipt and bidirectional plan/issue check; no false success on skip.
  - Evidence: pending; record exact revision, commands, fixtures and outcomes.

## 26 November measured-value and integration addendum (not accepted)

[Evidence ledger and next gates](../../research-evidence-20261126-measured.md). T00.001/.002/.005/.006/.007: central registration, coverage remediation, typed envelope #47, exact-head and protection gates. Canonical task acceptance unchanged.

## External validation and replication addendum (not accepted)

[Evidence ledger](../../research-evidence-20261126-external.md). T00.001/.007: #40/#52 qualified and merged, #54/#56/#57 actual hosted gates passed; main protection still administratively blocked. Canonical states unchanged.
