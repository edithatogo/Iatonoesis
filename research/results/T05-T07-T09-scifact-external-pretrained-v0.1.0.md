# SciFact external pretrained comparison — executed exploratory receipt

Status: exploratory, independent author reference annotations, not blinded confirmatory or clinical evidence. Tracks T05, T07, T09, T14. Code PR #50 merged; qualified PR head `c5eec6825ea5135fad41f1e56f361788207774b2`; receiving merge `e77d7a4f56ab3ef2778feeb594c788aa270b0138`. [Hosted replay](https://github.com/edithatogo/Iatonoesis/actions/runs/45811355777), artifact 15112698149, ZIP SHA256 `b0c15678940e3c43c76922ff9fc2e172b45fb8e61cbdb64297e34bd92c8f8d61`. Downloaded and verified ZIP. Hosted execution used synthetic PR merge `d44506998e9a5b960c3327e34a863eb9d98f6bc9`. Exact-head CI, replay, privacy, community and Codecov patch 94.42% (target 90%) succeeded. Protocol: [external pipeline v0.1.0](../protocols/scifact-external-pretrained-pipeline-v0.1.0.md).

## Provenance and split

Original [SciFact](https://github.com/allenai/scifact/tree/68b98a56d93e0f9da0d2aab4e6c3294699a0f72e), DOI [10.18653/v1/2020.emnlp-main.609](https://doi.org/10.18653/v1/2020.emnlp-main.609). Author license distinguishes claims/evidence CC BY 4.0, corpus ODC-By 1.0 and code Apache-2.0. No source text reproduced. Archive SHA256 `11c621288d41ac144d29b13b0f8503b3820b7d6e8b1f6ff24dff335c196d76be`, 3,115,079 bytes. Public development annotations reserved as exploratory test, not official hidden test. Claim/document components disjoint; 278 training claims removed for overlap.

| Split | Pairs | Claims | Groups |
|---|---:|---:|---:|
| Development |448|397|238|
| Calibration |152|134|87|
| Test |339|300|247|

Freeze SHA256 `ab452560041235ca77e30925d034a28daac499c4bd0c93e38c544e6a7d9eb570`; result SHA256 `40eb749415cb065e26a4d6ea3613d8222b76a79766d469d4a71cef5a73624924`; canonical predictions SHA256 `76126dacae5ee20ac1d97346f22baa11e9d19d6986fd36ec6565461d5ba82549`. Python 3.13.5, torch 2.10.0+cpu, transformers 4.57.1, HF hub 0.36.0.

Observed model pins (Apache-2.0):
- cross-encoder/nli-distilroberta-base: revision `b14d131f9d32668a5e6a982729b57ff6ed5dfcbd`, safetensors SHA256 `9df3eb5d37118f952f4ba4fb46fde6889e3a9ccedeee0bad09b0110fc64c5c29`, 328499560 bytes.
- cross-encoder/ms-marco-MiniLM-L6-v2: revision `233902d25c440f23af6f7d6e94d2946bac0bee0a`, safetensors SHA256 `821d1aa69520101d6e0737f78a042ae25b19e5cb9160701909d10434f4aeb0ae`, 90870598 bytes.
Execution resolves and verifies an immutable model revision before inference; future exact replay must explicitly select the observed revisions rather than assume a mutable upstream HEAD is unchanged. Contamination not excluded.

## Pair decisions and review budgets

| Classifier | Correct/339 | False supports/201 | Correct/169 at 50% coverage | Correct/254 at 75% coverage |
|---|---:|---:|---:|---:|
| Rules |133|0|106|128|
| Linear |199|69|105|148|
| Small MLP |204|66|115|163|
| Pretrained NLI |147|5|82|112|

Matched 50% coverage means 170 reviews; 75% means 85. False supports at 50% were 0/133, 33/96, 21/103, 1/103 respectively. NLI support recall 13/138; contradiction recall 20/71. No classifier met calibration risk gate. 46 eligible calibration proposals; fallback gate null, zero activations. Linear selective baseline retained 221/339, 137 correct, 41 false supports, 118 reviews. Review not counted as a correct answer. No learned-fallback benefit established.

## Crossed pipeline

Both rankers retrieved evidence first for 185/188 evidence-bearing claims. MRR .9920213 and nDCG@3 .99368356. These are fixed cited pools, often singleton, not open retrieval.

| Ranker | Rules | Linear | Small MLP | Pretrained NLI |
|---|---:|---:|---:|---:|
| BM25 |115|173|178|123|
| Pretrained |115|172|176|123|

Cells are correct end-to-end decisions out of 300 claims. BM25 test 0.342 s versus pretrained 24.583 s plus load 2.065 s; NLI calibration+test 113.774 s plus load 3.924 s versus small MLP 0.026 s plus training 0.051 s. Same candidate/review budgets, not equal compute. 53/339 test pairs truncated at 512 tokens. Exploratory linguistic subgroup counts: long abstracts 72 (MLP 42, NLI 16 correct), negation 31 (18, 13), numeric 58 (32, 23). No causal subgroup conclusion.

## Implications and open gates

Small task-trained model outperformed transferred NLI on accuracy; NLI reduced false supports but missed most supports. Pretrained ranking did not improve already near-ceiling cited pools. Retain both safety and discrimination metrics; no fallback admission. Next: broader hard candidate pools, independent diverse calibration, explicit cost-matched inference, truncation controls and blinded source-family holdouts. Do not declare all eight families admitted. DocLayNet cross-source layout candidate remains unexecuted; clinical, document-qualifier and policy reference standards remain open. No production protection claim: administration endpoint forbidden and rulesets empty at observation.
