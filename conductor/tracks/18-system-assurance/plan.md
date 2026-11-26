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
