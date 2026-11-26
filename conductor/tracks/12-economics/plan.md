# T12 — Health economics and implementation science

Issue [#13](https://github.com/edithatogo/Iatonoesis/issues/13). Stable task IDs; canonical [programme](../../../contracts/programme.v1.json). Cross-track prerequisites: T00 (#1), T16 (#17), T17 (#18). Downstream consumers: T13 (#14), T14 (#15). [Roadmap](../../roadmap.md).

- [ ] **T12.001** — Create resource-use instrument (#13)
  - Depends on: T00.002.
  - Accept: Measure clinician/administrator time, cost, compute, verification burden and transport separately.
  - Evidence: pending; record exact revision, commands, fixtures and outcomes.
- [ ] **T12.002** — Specify cost-consequence and workload scenarios (#13)
  - Depends on: T12.001.
  - Accept: Conventional vs assisted workflow, uncertainty and sensitivity; simulated effects labelled.
  - Evidence: pending; record exact revision, commands, fixtures and outcomes.
- [ ] **T12.003** — Model rural workload, connectivity and capability constraints (#13)
  - Depends on: T12.002.
  - Accept: Scenario sensitivity, patient travel and staffing dependencies; no real service claims.
  - Evidence: pending; record exact revision, commands, fixtures and outcomes.
- [ ] **T12.004** — Develop prospective implementation and health-economic protocol (#13)
  - Depends on: T12.003.
  - Accept: Define perspective, horizon, equity, workflow acceptance and external governance gates.
  - Evidence: pending; record exact revision, commands, fixtures and outcomes.
- [ ] **T12.005** — Cross-role resource and decision utility synthesis (#13)
  - Depends on: T12.003, T16.001, T17.001, T17.003.
  - Accept: Matched-budget acquisition, feasibility and optimisation; separate proxy outcomes from clinical outcomes.
  - Evidence: pending; record exact revision, commands, fixtures and outcomes.

## Published workflow time sensitivity (not accepted)

[T12/T16 observation bundle resource-use protocol](../../../research/protocols/T12-bundled-observation-costs-v0.1.0.md), [aggregate receipt](../../../results/benchmarks/physionet-bundle-cost-v0.1.0.json). T12.001 draft prospective resource-use instrument and T12.002 counterfactual arithmetic-mean bundle-time analysis consuming exact #57 receipt. Forced acquisition worsened descriptive MSE; stop improves only 0.05742 squared bpm over none, 132–252 of 252 cases may trigger a bundle. Whole set timing is not marginal measurement time; HR may be collected directly. T12.003/.004 local timing, travel, staffing, governance remain open; T12.005 synthesis remains held. No task acceptance.
