# T11 — Safety, equity and model assurance

Issue [#12](https://github.com/edithatogo/Iatonoesis/issues/12). Stable task IDs; canonical machine-readable source is contracts/programme.v1.json. `python -m iatonoesis ready` lists dependency-ready work; individual experiments are not yet implemented. Acceptance commands and result paths must be added before marking implementation complete.

- [ ] **T11.001** — Create hazard register and intended-use boundaries (#12)
  - Depends on: T00.002.
  - Accept: Explicit clinical responsibility, no live decisions, unsafe completion/under-triage controls.
  - Evidence: pending; record exact source commit, commands, fixtures and outcomes.
- [ ] **T11.002** — Implement selective prediction and calibration protocol (#12)
  - Depends on: T11.001.
  - Accept: Reliability curves, risk–coverage, group/site error, confidence intervals; frozen calibration.
  - Evidence: pending; record exact source commit, commands, fixtures and outcomes.
- [ ] **T11.003** — Test counterfactuals, missingness, OOD, prompt injection and leakage (#12)
  - Depends on: T11.002.
  - Accept: Source-bound outputs, explicit abstentions; holdout invariance and adversarial fixtures.
  - Evidence: pending; record exact source commit, commands, fixtures and outcomes.
- [ ] **T11.004** — Assess rural, regional and underserved setting performance (#12)
  - Depends on: T11.003.
  - Accept: Predefined subgroup denominators and uncertainty; no invented demographic identity.
  - Evidence: pending; record exact source commit, commands, fixtures and outcomes.
- [ ] **T11.005** — Verify privacy, supply chain, licensing and model/dataset provenance (#12)
  - Depends on: T11.004.
  - Accept: Hosted scans and actual receipts, rights ledger, no secrets or real records.
  - Evidence: pending; record exact source commit, commands, fixtures and outcomes.
- [ ] **T11.006** — Define separate deployment and publication gates (#12)
  - Depends on: T11.005.
  - Accept: Scientific evidence, ethics, independent reference and institutional permissions remain unfulfilled until observed.
  - Evidence: pending; record exact source commit, commands, fixtures and outcomes.
