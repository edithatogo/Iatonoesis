# MONDO temporal assertion ranking — executed results v0.1.0

[Protocol](../protocols/mondo-temporal-graph-ranking-v0.1.0.md); T03/#4, T05/#6, T09/#10, T11/#12, T14/#15. Source: Mondo Disease Ontology / Monarch Initiative, CC BY 4.0, Vasilevsky et al., [Genetics 2026](https://doi.org/10.1093/genetics/iyaf215). No source content or altered ontology published. Exact source commit 7cfb052a402fde688190d6304abf923fd9a39ee6; [hosted run 45831877769](https://github.com/edithatogo/Iatonoesis/actions/runs/45831877769), artifact 15122179337. All four pinned release byte counts and SHA-256 values verified. Artifact ZIP retained byte-identically as [aggregate archive](../../results/benchmarks/mondo-temporal-v0.1.0-aggregate.zip), SHA-256 b938ed5935a53cfe6532c43b6a8980a03f0a8247017dd445d920e8c6981e4f13, internal JSON SHA-256 0151a91a5f276c5b74c86a6b8f131c01f19fba003a936ae4e56e75307bc04a3b; [derived summary](../../results/benchmarks/mondo-temporal-v0.1.0-summary.json). Initial exact-head CI, community, privacy, task replay and Codecov patch 98.39% passed. Local RED missing module then seven synthetic tests passed, 98% module line coverage; hosted execution is distinct.

| Window | Changed existing children | Eligible new assertions | Excluded new-endpoint assertions |
|---|---:|---:|---:|
| Feb→May development | 69 | 78 | 2,614 |
| May→Aug calibration | 67 | 70 | 4,751 |
| Aug→Nov test | 383 | 475 | 194 |

One test child occurred in development and one in calibration (overlap between those counts unknown). All 383 test children retained; 32 historical candidates per query, 12,256 candidates total. Fixed-pool recall 162/475 = 34.11%; all 313 missed gold assertions count against end-to-end recall. Candidate-generation elapsed 17.067 s; no measured human workflow or clinical effect.

| Arm | MRR | Recall@1 | Recall@5 | Recall@10 | Confirmed top-1/383 |
|---|---:|---:|---:|---:|---:|
| lexical | 0.1190 | 0.0653 | 0.1200 | 0.1579 | 31 |
| topology | 0.0894 | 0.0189 | 0.1263 | 0.2316 | 9 |
| hybrid_rule | 0.1197 | 0.0547 | 0.1453 | 0.2042 | 26 |
| linear | 0.1734 | 0.0947 | 0.2021 | 0.2505 | 45 |
| neural | 0.1804 | 0.0989 | 0.2126 | 0.2716 | 47 |
| no_graph | 0.1247 | 0.0695 | 0.1179 | 0.1705 | 33 |

The graph-feature MLP improved MRR by .06069 over equal-weight hybrid rules (paired descriptive interval [.03956,.08410]) and .05569 over its lexical-only feature ablation ([.03378,.08252]). Linear scorer improved MRR by .05366 over the hybrid [.03510,.07641]. Linear and neural differ by only .00703 descriptively; no predeclared paired inference between them. At 383 top-one reviews, neural confirmed 47 later assertions and 336 remained unconfirmed. At 95 reviews the neural confirmed 12, versus lexical 13 and ablated 15; no model dominates every budget. All six fail the prespecified calibration criterion (≥20 selected, Wilson upper unconfirmed fraction ≤.20); none activated selective suggestions. Abstention not success. A missing later ontology edge is not proven false; this is a curation reference, not a clinical classifier. Aggregate results use shared graph dependencies; intervals are descriptive, not proof of superiority. Candidate cap and review budgets matched, compute not matched; timing observed separately.

**Next frozen study:** candidate retrieval factorial before ranking, broader historical and cross-ontology source families, candidate-recall ceiling vs reranking, exact model and source rights plus contamination audit, true GNN and pretrained semantic embedding challenger with documented historical cutoff, source-group stratification, repeated calibration windows and explicit no-change query population. Do not tune the current test set or claim clinical qualification. Preserve exact hierarchy traversal for computable questions. No canonical task accepted.
