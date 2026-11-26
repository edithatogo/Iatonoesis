# T11 — Safety, equity and model assurance

Issue [#12](https://github.com/edithatogo/Iatonoesis/issues/12). Stable task IDs; canonical [programme](../../../contracts/programme.v1.json). Cross-track prerequisites: T00 (#1), T17 (#18), T18 (#19), T19 (#20). Downstream consumers: T01 (#2), T02 (#3), T03 (#4), T04 (#5), T05 (#6), T06 (#7), T07 (#8), T08 (#9), T13 (#14), T15 (#16), T17 (#18), T18 (#19), T19 (#20). [Roadmap](../../roadmap.md).

- [ ] **T11.001** — Create hazard register and intended-use boundaries (#12)
  - Depends on: T00.002.
  - Accept: Explicit clinical responsibility, no live decisions, unsafe completion/under-triage controls.
  - Evidence: pending; record exact revision, commands, fixtures and outcomes.
- [ ] **T11.002** — Implement selective prediction and calibration protocol (#12)
  - Depends on: T11.001.
  - Accept: Reliability curves, risk–coverage, group/site error, confidence intervals; frozen calibration.
  - Evidence: pending; record exact revision, commands, fixtures and outcomes.
- [ ] **T11.003** — Test counterfactuals, missingness, OOD, prompt injection and leakage (#12)
  - Depends on: T11.002.
  - Accept: Source-bound outputs, explicit abstentions; holdout invariance and adversarial fixtures.
  - Evidence: pending; record exact revision, commands, fixtures and outcomes.
- [ ] **T11.004** — Assess rural, regional and underserved setting performance (#12)
  - Depends on: T11.003.
  - Accept: Predefined subgroup denominators and uncertainty; no invented demographic identity.
  - Evidence: pending; record exact revision, commands, fixtures and outcomes.
- [ ] **T11.005** — Verify privacy, supply chain, licensing and model/dataset provenance (#12)
  - Depends on: T11.004.
  - Accept: Hosted scans and actual receipts, rights ledger, no secrets or real records.
  - Evidence: pending; record exact revision, commands, fixtures and outcomes.
- [ ] **T11.006** — Define separate deployment and publication gates (#12)
  - Depends on: T11.005.
  - Accept: Scientific evidence, ethics, independent reference and institutional permissions remain unfulfilled until observed.
  - Evidence: pending; record exact revision, commands, fixtures and outcomes.
- [ ] **T11.007** — Cross-role assurance and transportability (#12)
  - Depends on: T11.004, T18.004, T17.001, T19.002.
  - Accept: Compare false feasibility, false closure, uncertainty, missingness and site shift; abstention and equity.
  - Evidence: pending; record exact revision, commands, fixtures and outcomes.
