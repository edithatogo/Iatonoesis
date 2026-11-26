# T09 — Integrated multi-model workflows

Issue [#10](https://github.com/edithatogo/Iatonoesis/issues/10). Stable task IDs; canonical machine-readable source is contracts/programme.v1.json. `python -m iatonoesis ready` lists dependency-ready work; individual experiments are not yet implemented. Acceptance commands and result paths must be added before marking implementation complete.

- [ ] **T09.001** — Specify component interfaces and abstention propagation (#10)
  - Depends on: T00.002.
  - Accept: Versioned input/output schemas and rejected incompatible versions.
  - Evidence: pending; record exact source commit, commands, fixtures and outcomes.
- [ ] **T09.002** — Replay regional referral and transfer workflow (A) (#10)
  - Depends on: T09.001, T01.005, T02.005, T03.005, T04.005, T05.005, T06.005, T08.005.
  - Accept: Reference and corrupted upstream inputs, per-component replacements, appropriate destination, time and unresolved obligations.
  - Evidence: pending; record exact source commit, commands, fixtures and outcomes.
- [ ] **T09.003** — Replay clinical governance and learning workflow (B) (#10)
  - Depends on: T09.002, T07.005.
  - Accept: Conventional audit/process mining versus hybrid; actionable findings per reviewer hour, false alerts.
  - Evidence: pending; record exact source commit, commands, fixtures and outcomes.
- [ ] **T09.004** — Run fixed-pool and factorial ablations across both workflows (#10)
  - Depends on: T09.003.
  - Accept: Report standalone versus pipeline performance, interactions, paired uncertainty and costs.
  - Evidence: pending; record exact source commit, commands, fixtures and outcomes.
- [ ] **T09.005** — Simulate rural disruption, missing data and connectivity failure (#10)
  - Depends on: T09.004.
  - Accept: Unsafe route, false closure and recovery tests; no live action.
  - Evidence: pending; record exact source commit, commands, fixtures and outcomes.
- [ ] **T09.006** — Qualify external adapters to standards_check and CareOps (#10)
  - Depends on: T09.005.
  - Accept: Exact pinned consumer fixtures, ownership, rollback and no copied business logic.
  - Evidence: pending; record exact source commit, commands, fixtures and outcomes.
