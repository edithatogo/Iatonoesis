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

## Exploratory evidence — T15.001

[Shared T15/T16 synthetic protocol](../../../research/protocols/T15.001-T16.001-synthetic-state-information.v0.1.0.md), [result receipt](../../../research/results/T15.001-T16.001-exploratory-v0.1.0.md), [summary](../../../results/exploratory/T15.001-T16.001-summary.v0.1.0.json). Ridge MAE .74643 vs last .83842; interval coverage fell from 93.33% matched to 70% shifted. 240 synthetic test subjects; no real PhysioNet, clinical claim or acceptance. T16.001 reuses same splits. Qualify public bytes, temporal/reference integrity, calibration and runtime before confirmatory run.

## 26 November measured-value and integration addendum (not accepted)

[Evidence ledger and next gates](../../research-evidence-20261126-measured.md). T15.001: real bounded measured HR benchmark #49 executed; last observation wins; wider qualification and prespecified stratified replication pending. Canonical task acceptance unchanged.

## External validation and replication addendum (not accepted)

[Evidence ledger](../../research-evidence-20261126-external.md). T15.001 #57 512 fresh identities, 1/3/6-hour horizons; last observation best all three. Prespecified strata and paired uncertainty retained; no canonical acceptance. Canonical states unchanged.

## Frontier replication extension (not accepted)

[Role and dataset extension](../../../research/frontier-replication-extension.v0.1.0.md). T15.004: observation recording propensity baseline and later marked temporal point process; T15.001 2012 measured-target eligibility for replication; T15.002 latent operational world model candidate.
