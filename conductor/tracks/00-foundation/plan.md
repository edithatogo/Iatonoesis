# T00 — Research infrastructure

Issue [#1](https://github.com/edithatogo/Iatonoesis/issues/1). Stable task IDs; canonical machine-readable source is contracts/programme.v1.json. `python -m iatonoesis ready` lists dependency-ready work; individual experiments are not yet implemented. Acceptance commands and result paths must be added before marking implementation complete.

- [ ] **T00.001** — Reconcile starter, gitlink, community policy and solo-maintainer settings (#1)
  - Depends on: none.
  - Accept: Verify exact gitlink, provider status, actual protected checks, audit receipt; record unobserved settings.
  - Evidence: pending; record exact source commit, commands, fixtures and outcomes.
- [ ] **T00.002** — Define experiment/data/result contracts and validation (#1)
  - Depends on: T00.001.
  - Accept: Schema rejects missing provenance, unknown state, inconsistent metric denominator and leakage.
  - Evidence: pending; record exact source commit, commands, fixtures and outcomes.
- [ ] **T00.003** — Build deterministic run harness and synthetic dataset manifest (#1)
  - Depends on: T00.002.
  - Accept: Two same-seed runs produce identical canonical outputs; record hash, runtime, failures.
  - Evidence: pending; record exact source commit, commands, fixtures and outcomes.
- [ ] **T00.004** — Freeze calibration/development/test partitions and rights ledger (#1)
  - Depends on: T00.003.
  - Accept: Independent holdouts, site/temporal split where appropriate; no protected data in Git.
  - Evidence: pending; record exact source commit, commands, fixtures and outcomes.
- [ ] **T00.005** — Implement common metrics and confidence intervals (#1)
  - Depends on: T00.004.
  - Accept: Known analytic fixtures, denominator/abstention tests and seeded bootstrap; differential reference.
  - Evidence: pending; record exact source commit, commands, fixtures and outcomes.
- [ ] **T00.006** — Qualify CPU-first model adapter and optional HF runtime (#1)
  - Depends on: T00.005.
  - Accept: Exact model revision, licence, memory/latency budget, offline fail-closed; no default network.
  - Evidence: pending; record exact source commit, commands, fixtures and outcomes.
- [ ] **T00.007** — Enable CI, one-command assurance, results storage and issue reconciliation (#1)
  - Depends on: T00.006.
  - Accept: Required hosted checks, exact-head receipt and bidirectional plan/issue check; no false success on skip.
  - Evidence: pending; record exact source commit, commands, fixtures and outcomes.
