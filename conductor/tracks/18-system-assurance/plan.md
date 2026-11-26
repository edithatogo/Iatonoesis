# T18 — Counterexamples, failure attribution and transportability

Issue [#19](https://github.com/edithatogo/Iatonoesis/issues/19). Stable task IDs; canonical [programme](../../../contracts/programme.v1.json). Cross-track prerequisites: T00 (#1), T11 (#12), T14 (#15). Downstream consumers: T09 (#10), T11 (#12). [Roadmap](../../roadmap.md).

- [ ] **T18.001** — Finite-domain counterexample pilot (#19)
  - Depends on: T00.002, T00.003, T11.001.
  - Accept: Toy executable rules, exhaustive oracle, non-equivalent mutants, random/boundary/learned candidate selection at matched budget; exploratory not clinical evidence.
  - Evidence: pending; record exact revision, commands, fixtures and outcomes.
- [ ] **T18.002** — Clinical-rule counterexample benchmark (#19)
  - Depends on: T18.001, T14.004, T00.006.
  - Accept: Rights-qualified CQL and synthetic cases; held-out rule/mutation families; independent oracle; distinct defects per budget and invalid cases.
  - Evidence: pending; record exact revision, commands, fixtures and outcomes.
- [ ] **T18.003** — System failure attribution (#19)
  - Depends on: T14.004, T00.006, T11.001.
  - Accept: Synthetic known mechanisms then qualified public reports; compare timelines and process mining; unsupported causal attribution; no culpability inference.
  - Evidence: pending; record exact revision, commands, fixtures and outcomes.
- [ ] **T18.004** — Transportability assessor (#19)
  - Depends on: T14.004, T00.006, T11.001.
  - Accept: Hold out environments, use PhysioNet only if site metadata verified; WILDS/FluSight alternative; estimate target performance vs statistical baseline.
  - Evidence: pending; record exact revision, commands, fixtures and outcomes.

## Exploratory pilot evidence (not accepted)

- [PR #26](https://github.com/edithatogo/Iatonoesis/pull/26), [protocol](../../../research/protocols/T18.001-counterexample-pilot.v0.1.0.md), [result and reproducibility receipt](../../../research/results/T18.001-exploratory-v0.1.0.md). Source/test blob identity verified against local execution. Eight-case budget; 36 held-out instances; boundary 83.93%, learned 80.09%, random 76.14%. Negative finding retained. T18.001 remains planned pending T00.002/003, T11.001 and hosted exact-head qualification. No clinical claim.
- [PR #28](https://github.com/edithatogo/Iatonoesis/pull/28) advances CQL and other source metadata; T18.002 requires compatible translator/runtime, actual byte and reference qualification.

- Follow-up [protocol](../../../research/protocols/T18.001-counterexample-followup.v0.2.0.md), [result receipt](../../../research/results/T18.001-exploratory-v0.2.0.md) and [summary](../../../results/exploratory/T18.001-followup-summary.v0.2.0.json). Six fresh held-out rule families, nine new transformations, 54 instances. Boundary/pairwise 97.92%, learned feedback/no-feedback 92.50% at eight tests; oracle ceiling 100%. Learned advantage at one/two tests is exploratory. No acceptance; preserve original result. Next independently freeze new families and compare under low test budgets with compute/resource accounting; CQL runtime and reference qualification separate. Hosted replay artifacts pending.
