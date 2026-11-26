# Iatonoesis comparative specialist-model study — protocol supplement v0.1.0 (draft)

**Question:** When do dedicated learned models add value over conventional methods and general foundation models on bounded healthcare tasks? This is an empirical computational methods study, not a clinical effectiveness trial.

## Ownership and integration

Use the existing [programme](../contracts/programme.v1.json), [track index](../conductor/tracks.md) and [research protocol](protocol.md). Do not replace E01–E24, the separate emerging-role taxonomy or existing priority pilots E02/E04/E22. B01–B16 are methodological benchmarks, not a second set of application IDs. Some benchmark tasks are analogues rather than exact instantiations of an E application. T14 (#15) coordinates public data, split/reference qualification and comparative results; T01–T08 (#2–#9) own component implementations; T00 (#1) owns shared contracts, runner and evidence. T10 (#11) owns verified literature and taxonomy. T11 (#12) safety, uncertainty and equity; T12 (#13) economic/resource evaluation; T13 (#14) claim-bound dissemination. T15–T19 (#16–#20) are distinct emerging roles: dynamics, information acquisition, feasibility, assurance and commitment stewardship. Their canonical plans must be reconciled by the bootstrap lane before the supplement enters main.

- Candidate register: [B01–B16](../contracts/benchmark-candidates.v1.json). Extends rather than replaces [dataset register](../datasets/registry.md).
- First shared public-data candidate: TrialGPT (B09/B14), subject to rights and label qualification; can support extracted eligibility, retrieval, reranking and evidence checks on the same cases.
- Keep first pilot CPU-first and independently reproducible; do not introduce extensive GPU requirements or external model calls before baseline receipts.
- Cross-reference issue dependencies rather than close umbrella issues for partial progress.

## Comparative design

Compare five eligible arms: deterministic/conventional, classical learned, task-specialised learned, general-purpose foundation model, modular/hybrid. Record when an arm is inapplicable or unavailable. Preserve model objective, task role vs architecture, exact model revision, training evidence, parameter count, precision, compute and knowledge access. Prompted roles are not automatically dedicated learned models. Compare matched inputs and resource budgets; separately report unconstrained results where justified. Predeclare primary endpoint, practical margin, unit of analysis and pairing, and freeze splits before test execution. Use paired cluster/case bootstrap or other justified paired inference with confidence intervals; prespecify multiplicity families; report raw denominators, abstentions, critical failures, subgroup counts, latency, memory, cost and negative results. Do not combine arbitrary task scores into an unsupported global ranking.

Candidate data status is not evidence of qualification. Before download or processing verify primary locator, exact version, access and terms including redistribution, provenance, grain, schema, label mechanism, independent reference, training contamination, near-duplicates, split design, coverage, compute feasibility and SHA-256. Controlled-access/full MIMIC is excluded from public CI. Demo datasets require their own assessment. No private records, real health service data or autonomous actions.

## Synthetic and rural benchmark

Use Synthea plus independent scenario specifications, controlled defects and deterministic reference oracles. Freeze generator families/templates and hold out sites or templates; independently verify labels; distinguish model-generated challenge data from independently adjudicated gold. Test clean cases, true omissions and justified exceptions. Fictional regional sites may use AIHW and ABS public aggregates to calibrate plausible context only; no individual-level clinical labels or operational inference from aggregate statistics. Keep clinical urgency, permissions and hard capability constraints deterministic. No patient benefit or causal claim from a simulation.

## Crosswalk of 24 earlier discussion hypotheses

Discussion IDs below are not canonical experiment IDs. Preserve all existing tasks, labels and acceptance gates; variants are proposed, not executed. Owner references use the existing GitHub issues.

| Discussion ID | Programme/issue | Scope |
|---|---|---|
| L1 | E03 (#2) | historical laboratory result tuples; extension |
| L2 | E01/E24 (#2/#9) | transfer-package integrity |
| L3 | E02 (#2) | policy hierarchy and qualifier links |
| T1 | E04/T19 (#3/#20) | clinical commitments |
| T2 | E06/E21 (#3/#8) | system conditions and attribution |
| T3 | E05/E03 (#3/#2) | phenotype provenance extension |
| G1 | E07 (#4) | service fragility |
| G2 | T19/E24 (#20/#9) | accountability graph |
| G3 | E09/T16 (#4/#17) | mechanistic cohort construction |
| D1 | T16 (#17) | investigation value of information |
| D2 | T17/E07 (#18/#4) | disruption scheduling |
| D3 | T17/T12/T15 (#18/#13/#16) | mobile preventive allocation |
| R1 | E13/E03 (#6/#2) | chart provenance ranking variant |
| R2 | E13 (#6) | applicable policy ranking |
| R3 | E09/T16 (#4/#17) | knowledge-triggered patient-level reanalysis extension |
| RT1 | E16 (#7) | capability-aware referral routing |
| RT2 | E18 (#7) | privacy and compute adaptive routing |
| RT3 | E17/E15 (#7/#6) | multi-owner safety signals |
| E1 | E20 (#8) | local applicability |
| E2 | E21 (#8) | incident causal claims |
| E3 | E09/E19/T16 (#4/#8/#17) | gene–disease evidence independence |
| V1 | E24/E01 (#9/#2) | transfer readiness |
| V2 | E23/T18 (#9/#19) | calculation verification variant; synthetic only |
| V3 | E23 (#9) | research workflow conformance |

## Experimental sequencing

1. T00 and T14: minimal run and data contracts, rights, independent references; T10 source verification; T11 hazard analysis. Qualify TrialGPT and a synthetic pilot just in time.
2. Preserve E02/E04/E22 as the priority application pilots. Use conventional baseline and frozen reference before specialist challenger. Historical laboratory extraction (L1) and research conformance (V3) are later bounded variants E03/E23; do not displace existing tasks.
3. B01–B16: two distinct benchmark tasks per core family, with fixed candidate pools for reranking; graph traversal before GNNs; calibration separate from test; model vs deterministic vs general arms as applicable.
4. T18 synthetic executable-rule mutation experiments and subsequent error attribution; T15–T19 studies only after appropriate prerequisites and data qualification.
5. T09: existing referral/transfer and governance workflow; measure individual component performance using oracle inputs, then actual upstream outputs, then one-at-a-time baseline substitutions and selected interactions. Genomic reanalysis is a candidate later extension (E03/E05/E09/T16), requiring separate reference and temporal holdout.
6. T12 and T13: resource/equity analysis, versioned results and claim-to-run registry; publication and release permission separate. OSF, HF and Zenodo are proposed destinations, not provisioned.

## Required receipts

Every run must identify source commit, experiment/track, exact dataset and model revisions/hashes, environment, command, seed, split manifest, comparator and budget, predictions, errors, timing, denominators, metrics/uncertainty, and pass/fail/skip/unavailable status. Keep negative scientific findings distinct from software failures. Capture failed attempts, not just successful reruns. Register protocol prospectively before confirmatory runs; note exploratory analyses. No clinical deployment or institutional determination established.

## Integration acceptance

- Bootstrap writer reconciles canonical T14–T19 plans, metadata and issue registry; validates acyclic dependencies and consistent task ownership.
- Verify B IDs are unique; precisely two per core family; references to valid E IDs; all entries unqualified until documented rights/version review.
- Link supplement and candidate register from Conductor index, T14 plan, original family plans and T13, without duplicating task ownership.
- Required checks on exact PR head; receiving-main verification after integration. Do not claim experiment completion without executed receipts.
