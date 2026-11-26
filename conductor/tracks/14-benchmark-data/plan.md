# T14 — Public data, reference standards and comparative benchmark

Issue [#15](https://github.com/edithatogo/Iatonoesis/issues/15). Stable task IDs; canonical [programme](../../../contracts/programme.v1.json). Cross-track prerequisites: T00 (#1), T10 (#11), T12 (#13). Downstream consumers: T01 (#2), T02 (#3), T03 (#4), T04 (#5), T05 (#6), T06 (#7), T07 (#8), T08 (#9), T13 (#14), T15 (#16), T16 (#17), T17 (#18), T18 (#19), T19 (#20). [Roadmap](../../roadmap.md).

- [ ] **T14.001** — Dataset inventory and acquisition qualification (#15)
  - Depends on: T00.002, T10.001.
  - Accept: Source version, rights, access, schema, grain, missingness, provenance and SHA-256; no restricted redistribution.
  - Evidence: pending; record exact revision, commands, fixtures and outcomes.
- [ ] **T14.002** — Task, reference and grouped split contracts (#15)
  - Depends on: T14.001, T00.004.
  - Accept: Freeze independent reference and grouped holdouts; audit patient, site, time, document and rule-family leakage.
  - Evidence: pending; record exact revision, commands, fixtures and outcomes.
- [ ] **T14.003** — Matched-resource comparison (#15)
  - Depends on: T14.002, T00.005, T12.001.
  - Accept: Human reference only if approved, deterministic/statistical, prompted generalist, dedicated learned, hybrid; matched inputs, budgets, paired effects.
  - Evidence: pending; record exact revision, commands, fixtures and outcomes.
- [ ] **T14.004** — Run and release contracts (#15)
  - Depends on: T14.003, T00.003.
  - Accept: Record exact revision, dataset/model hashes, configuration, seeds, costs, raw outputs, failed/unavailable arms and claim boundary.
  - Evidence: pending; record exact revision, commands, fixtures and outcomes.

## Comparative benchmark crosswalk

- T14.001: [B01–B16 register](../../../contracts/benchmark-candidates.v1.json) and [TrialGPT qualification](../../../datasets/qualification/trialgpt.v0.1.0.md); preserve separate R-role candidates in [dataset register](../../../datasets/registry.md).
- T14.002: group and freeze case/trial splits before testing; verify references and contamination.
- T14.003: paired conventional and learned comparisons across two placements per core family; baseline first, no presumption that learned improves performance.
- T14.004: retain exact run receipts, failed arms and release gates. [Design](../../../research/comparative-study.md); publication T13.003/T13.007 (#14). No acceptance yet.

## 26 November measured-value and integration addendum (not accepted)

[Evidence ledger and next gates](../../research-evidence-20261126-measured.md). T14.001–.004: #45 candidate freeze, #49 measured-value source/reference/metric receipts, PubTables image/word and independent admission still open. Canonical task acceptance unchanged.

## External validation and replication addendum (not accepted)

[Evidence ledger](../../research-evidence-20261126-external.md). #56 actual PubTables pairing acquired and replayed; #45 TrialGPT author model-assisted references and training flag still block independent admission; #54/#57 aggregate external/replication receipts; #61 explicit unsupported states. Canonical states unchanged.
