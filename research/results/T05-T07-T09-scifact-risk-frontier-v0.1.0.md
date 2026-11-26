# SciFact retrospective joint risk–coverage and interaction audit v0.1.0

T05/T07/T09/T11/T12/T14, #6 #8 #10 #12 #13 #15. Reuse exact hosted artifact [15112698149](https://github.com/edithatogo/Iatonoesis/actions/runs/45811355777/artifacts/15112698149) from merged #50 and [#53 receipt](T05-T07-T09-scifact-external-pretrained-v0.1.0.md). ZIP, original result and canonical prediction hashes verified, no new inference, no source text. Local RED then 3 tests passed, Python 3.13.5. Exact source and test blobs verified. Results are post-hoc diagnostic on exposed test labels: do not choose a production threshold from this table.

At each observed error ceiling, retain the largest complete descending confidence prefix (no splitting tied scores), require >=30 retained and >=20 non-support examples, false support <=5% of retained non-support. Null means no feasible prefix, not zero accuracy. Of 339 pairs:

| Error ceiling | Rules | Linear | Small MLP | Pretrained NLI |
|---|---:|---:|---:|---:|
| 10% | — | — | — | — |
| 20% | — | — | 47 | — |
| 30% | 88 | 38 | 57 | — |
| 40% | 178 | 38 | 57 | 30 |
| 50% | 253 | 38 | 57 | 58 |

At 20%, MLP correct 38/47, false support 1/36, review 292/339. No model met earlier independently calibrated risk gate; never reinterpret these test-tuned diagnostic maxima as prospective qualification. Claim/document grouping, small retained denominators and multiple comparisons limit inference.

Exact replay of 8 crossed pipeline cells. Changing BM25 to pretrained reranking at fixed classifier changes correctly completed claims out of 300 by 0 (rules), -1 (linear), -2 (MLP), 0 (NLI). Interactions versus rules baseline same. Candidate recall already near ceiling; no benefit or cost-effectiveness evidence for the more expensive reranker. Measured ranking .342 vs 24.583 seconds plus neural load 2.065 s; calibration+test classifier times .026 vs 113.774 s (MLP vs NLI, excluding fit/load). These are measured costs for matched input budgets, **not** a matched-compute experiment.

Reproduce with the exact original ZIP (obtain from the Actions artifact while available):
```sh
PYTHONPATH=src python -m iatonoesis.scifact_frontier --artifact /path/to/scifact.zip --output /tmp/frontier.json
PYTHONPATH=src python -m pytest -q tests/test_scifact_frontier.py
```
Full deterministic audit JSON SHA-256 a01218ba3016f142bca419b4caac59475d82d856af4513b71d1af1f77bc0fc2b. [Aggregate receipt](../../results/exploratory/scifact-risk-frontier-v0.1.0.json). Original run and calibration remain untouched. Need separately powered, source-disjoint calibration and cost-matched inference, broader pools and uncertainty intervals. No canonical task acceptance.
