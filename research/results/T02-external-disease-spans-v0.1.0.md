# T02 — external disease span extraction: executed exploratory receipt

Refs T02/#3, T00/#1, T09/#10, T11/#12 and T14/#15. [Protocol](../protocols/external-disease-spans-v0.1.0.md), [implementation #55](https://github.com/edithatogo/Iatonoesis/pull/55), exact head 2a87ca50344b6352bab9412c1b099b70183bae3e, merge 9f25fb4c45e3ce31ea26f543a358ceb4cc98f9ad. [Hosted replay 45815081481](https://github.com/edithatogo/Iatonoesis/actions/runs/45815081481) passed; Codecov patch 91.22% (target 90%), CI/privacy/community passed. Downloaded [artifact 15115096872](https://github.com/edithatogo/Iatonoesis/actions/runs/45815081481/artifacts/15115096872); actual ZIP SHA-256 90948b3aace70c3da7b56b70d32f4c1a0c145308175da4973426631ed8845e80 matched API. Freeze JSON SHA-256 bb9f8a39a6edc2364c4eaec23122f0cc208b2ce7c3d3506ea288aa0c5a89c7a0, result JSON SHA-256 691f33c8a5b7fa91677154a6dc73e1efb62e4ad13cf7654a426e2f40ab8c2d72. No source text exported. Source/test blobs fda84fedfc7399e24872e447657b8f8d3c999dd9 and 3c0945ed2e463c5272c547584cae92008089ef70.

NCBI original independently curated disease corpus (public-domain notice verified), exact original mirror files and source hashes checked. One malformed training document quarantined and one identical duplicate removed; fixed 256 development, 100 calibration and 100 test abstracts. Test contains 960 exact gold spans; 457 surface forms absent from the development lexicon. Known public-source/pretraining exposure not ruled out; no clinical adjudication. BC5CDR optional cross-corpus input **unavailable**, source acquisition/admission returned ValueError, no external test rows, no model results. Diagnose exact failed gate before another attempt. No weakening of rights, format or integrity requirements.

Actual pretrained MACCROBAT-trained DistilBERT d4data/biomedical-ner-all revision 015a4050c9ac99722e61c547aa9b4282bcbedc7f, Apache-2.0 model card; 265,722,260-byte safetensors verified SHA-256 d744b846a71ce6ccdb49d7bfe5097eadc41e766ffd28481e1636ed796e820165. Config/tokenizer digest ed4f23d623abddd256d8ed4f513bee67ff243363c35364823a1cbf3c0af41518. Small MLP 8,323 parameters, one unrepresentable training span, weights SHA-256 25f0183bac80bef75219080c436c5e35a07bd2f3407307ece885b13dda5e0358. Exact publication/source attribution in protocol.

| Arm | TP | FP | FN | Span F1 | Exact documents | Abstentions | Novel gold recovered |
|---|---:|---:|---:|---:|---:|---:|---:|
| Dictionary |501|468|459|.51944|2/100|0|0/457|
| Small MLP |493|1986|467|.28671|0/100|0|107/457|
| Pretrained |95|492|865|.12282|0/100|2|38/457|
| Calibrated fallback |501|468|459|.51944|2/100|0|0/457|
| Agreement |0|0|960|.00000|0/100|100|0/457|

No eligible calibration proposal for dictionary-empty fallback; null threshold, zero activations. Agreement abstains everywhere; no review credited as correct. Paired document-bootstrap delta versus dictionary: small MLP -.23273 [-.27586,-.18913], pretrained -.39662 [-.45398,-.34084], descriptive 200 draws. At matched 50% and 75% document retention, no arm with feasible budget had an exact correct document; agreement budget infeasible. Full coverage infeasible for pretrained (2 long-document abstentions). This is not a matched-error policy or clinical task validation.

Observed test inference seconds dictionary .340, small MLP .645, pretrained 18.961; MLP training 3.861 s, pretrained loading 5.503 s. Same test inputs, not equal compute. Negative transfer from case-report disease-disorder mapping to abstract disease mentions may reflect label ontology, context, span boundaries and unfamiliar language, not a general failure of pretrained NER. Prioritize matched ontology (disease-only specialist with explicit training partition provenance), separately audited source-disjoint test and real span/mention calibration. Investigate error strata without tuning on these exposed cases. No claim that T02 or eight-family independent clinical admission is complete.

No clinical deployment, registry population or assertion/experiencer validation. Follow-up: qualify BC5CDR source and source-specific label mapping, independently adjudicated spans, matched workload and cost, and preserve negative findings.
