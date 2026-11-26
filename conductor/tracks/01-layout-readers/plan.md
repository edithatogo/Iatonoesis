# T01 — Layout-aware document readers

Issue [#2](https://github.com/edithatogo/Iatonoesis/issues/2). Stable task IDs; canonical [programme](../../../contracts/programme.v1.json). Cross-track prerequisites: T00 (#1), T11 (#12), T14 (#15). Downstream consumers: T09 (#10). [Roadmap](../../roadmap.md).

- [ ] **T01.001** — Verify primary-source claims, rights and model candidates (#2)
  - Depends on: T00.002.
  - Accept: Record source links, capability/setting distinction, licence, exact revisions, no novelty claim.
  - Evidence: pending; record exact revision, commands, fixtures and outcomes.
- [ ] **T01.002** — E01: freeze protocol, dataset and reference (#2)
  - Depends on: T01.001, T00.004, T14.002.
  - Accept: 150 varied referrals; label source-linked fields, dates and missingness; provenance, independent reference, frozen split and error taxonomy.
  - Evidence: pending; record exact revision, commands, fixtures and outcomes.
- [ ] **T01.003** — E01: implement and run conventional baseline (#2)
  - Depends on: T01.002, T00.003, T00.005, T14.004.
  - Accept: OCR and fixed templates; field linkage F1 and critical omission; retain predictions, denominators, runtime and negative fixtures.
  - Evidence: pending; record exact revision, commands, fixtures and outcomes.
- [ ] **T01.004** — E01: qualify and run learned challenger (#2)
  - Depends on: T01.003, T00.006.
  - Accept: Exact-pinned task-specific model; same fixed test cases; report actual error or unavailable runtime; no prompted role mislabelled as trained model.
  - Evidence: pending; record exact revision, commands, fixtures and outcomes.
- [ ] **T01.005** — E01: evaluate incremental value and failure modes (#2)
  - Depends on: T01.004, T11.001.
  - Accept: result linked to wrong date; receiving clinician reviews region; paired uncertainty, calibration/abstentions, processing time and rework; retain negative findings.
  - Evidence: pending; record exact revision, commands, fixtures and outcomes.
- [ ] **T01.006** — E02: freeze protocol, dataset and reference (#2)
  - Depends on: T01.001, T00.004, T14.002.
  - Accept: 100 annotated pages; label hierarchy, rows, qualifiers and source boxes; provenance, independent reference, frozen split and error taxonomy.
  - Evidence: pending; record exact revision, commands, fixtures and outcomes.
- [ ] **T01.007** — E02: implement and run conventional baseline (#2)
  - Depends on: T01.006, T00.003, T00.005, T14.004.
  - Accept: text extraction and conventional table parser; qualifier-link F1; retain predictions, denominators, runtime and negative fixtures.
  - Evidence: pending; record exact revision, commands, fixtures and outcomes.
- [ ] **T01.008** — E02: qualify and run learned challenger (#2)
  - Depends on: T01.007, T00.006.
  - Accept: Exact-pinned task-specific model; same fixed test cases; report actual error or unavailable runtime; no prompted role mislabelled as trained model.
  - Evidence: pending; record exact revision, commands, fixtures and outcomes.
- [ ] **T01.009** — E02: evaluate incremental value and failure modes (#2)
  - Depends on: T01.008, T11.001.
  - Accept: exception overgeneralised; policy owner adjudicates; paired uncertainty, calibration/abstentions, policy review hours; retain negative findings.
  - Evidence: pending; record exact revision, commands, fixtures and outcomes.
- [ ] **T01.010** — E03: freeze protocol, dataset and reference (#2)
  - Depends on: T01.001, T00.004, T14.002.
  - Accept: 40 synthetic records; label time-linked observations and relationships; provenance, independent reference, frozen split and error taxonomy.
  - Evidence: pending; record exact revision, commands, fixtures and outcomes.
- [ ] **T01.011** — E03: implement and run conventional baseline (#2)
  - Depends on: T01.010, T00.003, T00.005, T14.004.
  - Accept: OCR plus manual abstraction; relationship and temporal-link accuracy; retain predictions, denominators, runtime and negative fixtures.
  - Evidence: pending; record exact revision, commands, fixtures and outcomes.
- [ ] **T01.012** — E03: qualify and run learned challenger (#2)
  - Depends on: T01.011, T00.006.
  - Accept: Exact-pinned task-specific model; same fixed test cases; report actual error or unavailable runtime; no prompted role mislabelled as trained model.
  - Evidence: pending; record exact revision, commands, fixtures and outcomes.
- [ ] **T01.013** — E03: evaluate incremental value and failure modes (#2)
  - Depends on: T01.012, T11.001.
  - Accept: wrong pedigree edge; genetics reviewer checks original; paired uncertainty, calibration/abstentions, abstraction time and completeness; retain negative findings.
  - Evidence: pending; record exact revision, commands, fixtures and outcomes.

## Exploratory receipts (not task acceptance)

- [Token-only baseline](../../../research/experiments/E02-layout-pilot.md) (#24, merged).
- [Rendered PDF feasibility pilot](../../../research/experiments/E02-pdf-pilot.md) (T01.006/007): Poppler reading-order reconstruction explains much of the initial effect; spatial rules reduce false binding but do not improve recall. Independent annotations, qualified source inputs, OCR, common runner/metrics and model comparison remain outstanding. All canonical task states unchanged.
