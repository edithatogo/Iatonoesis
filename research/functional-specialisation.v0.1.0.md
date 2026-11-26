# Beyond Prediction: functional specialisation in healthcare AI

Version 0.1.0 — draft exploratory protocol, 26 November 2026. Canonical programme: Iatonoesis. No registration, ethics determination or empirical qualification claimed.

## Questions
1. Which distinct roles are explicitly proposed in cross-disciplinary literature and what is actually learned versus prompted, deterministic or orchestrated?
2. Under equivalent information and resource constraints, when does dedicated training or architecture improve a distinct functional task compared with simpler approaches?
3. Does compositional specialisation improve simulated end-to-end workflows and under which failure conditions?

## Study design
Stage A scoping review (T10/#11, T13/#14); distinguish author proposal, learned prototype, non-specialist implementation and original hypothesis. Anchor primary sources: [LeCun 2022](https://openreview.net/pdf?id=BZ5a1r-kVsf), [Li 2025 COLING](https://aclanthology.org/2025.coling-main.652/). Search MEDLINE, Embase, Scopus, Web of Science, IEEE Xplore, ACM, ACL, preprints and backward/forward citations subject to access. Log database, exact queries/date, coverage, exclusions, primary source, inputs/outputs, training signal, comparators, maturity and failures. Current taxonomy is exploratory, not exhaustive or novelty-certified.

Stage B task benchmarks (T01–T08 and T15–T19); T14 owns shared data/evaluation contracts. Cross model family × task framing × training specialisation where feasible. Arms: existing human reference where genuinely available, deterministic/statistical baseline, prompted generalist, dedicated learned component, hybrid. Record missing arms as missing (not zero). Match input visibility, candidate pool, budget, tune allowance and evaluation split; report training cost separately from inference. CPU-first. No proprietary API required for initial smoke.

Stage C composition (T09/#10); regional retrieval and learning-health-service simulations with component removal and replacement. No patient deployment. Use counterfactual effects only in known simulation or separately justified identifiable causal design.

## Endpoints and analysis
Task-specific primary endpoint and direction defined per registered experiment; secondary calibration, selective risk, robustness, latency/cost, subgroup/setting shifts and decision utility. Group splits by patient, time, institution, document or rule family. Report paired effect estimates and cluster-aware intervals, not pseudo-replicated observation counts. For multiple endpoints distinguish confirmatory from exploratory and prespecify adjustment family. Set sample size from precision or power justification before confirmatory evaluation. No pooling of incomparable endpoints into a universal score. Report missingness, model pretraining contamination, negative/failed runs and selection decisions. If test labels are accessed before freeze, label exploratory and obtain new held-out set.

## Boundaries
Candidate sources are unqualified; license, access and ethics assessment required. Synthetic or public retrospective experiments do not establish patient benefit, real-time feasibility or causal effects. No identifiable/restricted data or hospital integration. Never override hard safety/credential constraints or autonomously close clinical tasks. Clinical outcomes are future validation targets, not observed outcomes of simulation. Record AI assistance and independent adjudication limits. Human reference workflow only if available and authorized.

## Outputs
Versioned taxonomy, datasets/manifests, frozen task contracts, code, immutable raw results, failures, statistical analysis, PRISMA-ScR review and comparative/compositional manuscripts. See [roadmap](../conductor/roadmap.md), [track map](../conductor/tracks.md), [taxonomy](../taxonomy/roles.v0.1.0.json).
