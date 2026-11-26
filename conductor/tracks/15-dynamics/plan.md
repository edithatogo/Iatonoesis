# T15 — State reconstruction, world models, recoverability and ascertainment

Issue [#16](https://github.com/edithatogo/Iatonoesis/issues/16). Stable task IDs; canonical [programme](../../../contracts/programme.v1.json). Cross-track prerequisites: T00 (#1), T11 (#12), T14 (#15). Downstream consumers: T09 (#10), T16 (#17). [Roadmap](../../roadmap.md).

- [ ] **T15.001** — State reconstruction (#16)
  - Depends on: T14.004, T00.006, T11.001.
  - Accept: PhysioNet masked observations vs last value, imputation and trained temporal model; held-out measurement error and calibration, not undocumented truth.
  - Evidence: pending; record exact revision, commands, fixtures and outcomes.
- [ ] **T15.002** — Operational world modelling (#16)
  - Depends on: T14.004, T00.006, T11.001.
  - Accept: NHS passive forecasting vs seasonal/DES baselines; intervention effects only in qualified simulation; trajectory error and calibration.
  - Evidence: pending; record exact revision, commands, fixtures and outcomes.
- [ ] **T15.003** — Recoverability horizon (#16)
  - Depends on: T14.004, T00.006, T11.001.
  - Accept: 4TU traces plus known synthetic intervention effects; fixed deadlines/early warning vs learned horizon; missed rescue windows and false reassurance.
  - Evidence: pending; record exact revision, commands, fixtures and outcomes.
- [ ] **T15.004** — Ascertainment and observation process (#16)
  - Depends on: T14.004, T00.006, T11.001.
  - Accept: FluSight and simulated reporting delays; compare conventional nowcast; independent anchors for incidence; estimate uncertainty.
  - Evidence: pending; record exact revision, commands, fixtures and outcomes.
