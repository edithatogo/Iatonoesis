# T12 — Health economics and implementation science

Issue [#13](https://github.com/edithatogo/Iatonoesis/issues/13). Stable task IDs; canonical machine-readable source is contracts/programme.v1.json. `python -m iatonoesis ready` lists dependency-ready work; individual experiments are not yet implemented. Acceptance commands and result paths must be added before marking implementation complete.

- [ ] **T12.001** — Create resource-use instrument (#13)
  - Depends on: T00.002.
  - Accept: Measure clinician/administrator time, cost, compute, verification burden and transport separately.
  - Evidence: pending; record exact source commit, commands, fixtures and outcomes.
- [ ] **T12.002** — Specify cost-consequence and workload scenarios (#13)
  - Depends on: T12.001.
  - Accept: Conventional vs assisted workflow, uncertainty and sensitivity; simulated effects labelled.
  - Evidence: pending; record exact source commit, commands, fixtures and outcomes.
- [ ] **T12.003** — Model rural workload, connectivity and capability constraints (#13)
  - Depends on: T12.002.
  - Accept: Scenario sensitivity, patient travel and staffing dependencies; no real service claims.
  - Evidence: pending; record exact source commit, commands, fixtures and outcomes.
- [ ] **T12.004** — Develop prospective implementation and health-economic protocol (#13)
  - Depends on: T12.003.
  - Accept: Define perspective, horizon, equity, workflow acceptance and external governance gates.
  - Evidence: pending; record exact source commit, commands, fixtures and outcomes.
