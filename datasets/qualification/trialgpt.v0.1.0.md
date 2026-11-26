# TrialGPT — preliminary source qualification (T14.001 / #15; B09/B14)

Date: 2026-11-26. Status: metadata/source review, **not qualified for ingestion or redistribution**. No source bytes, hashes or split receipts yet.

Primary study: Jin et al. (2024), Nature Communications 15:9074, DOI https://doi.org/10.1038/s41467-024-53081-z. Authors report 183 synthetic patient descriptions across SIGIR/TREC cohorts, and 1,015 sampled patient–criterion pairs manually evaluated by three annotators. Consensus eligibility via majority or discussion, evidence sentences via union. Annotators saw model predictions: possible anchoring, not blinded independent reference. This is a benchmark, not clinical truth or a clinical effectiveness study.

## B14 criterion annotations

- https://huggingface.co/datasets/ncbi/TrialGPT-Criterion-Annotations
- https://huggingface.co/datasets/ncbi/TrialGPT-Criterion-Annotations/blob/main/LICENSE explicitly states NCBI US government public-domain notice, citation requested. Hub connector returned generic licence tag "other"; licence text is more informative. Underlying clinical vignettes and third-party data rights and foreign jurisdiction still require review. No raw text committed.
- Hub structure inspection: default/train, approximately 1,015 rows, one ~176.1 KB Parquet export, 14 fields: annotation_id, patient_id, note, trial_id, trial_title, criterion_type, criterion_text, gpt4_explanation, explanation_correctness, gpt4_sentences, expert_sentences, gpt4_eligibility, expert_eligibility, training. Exact full dataset revision, original file hash, counts, duplicate and missingness checks pending. Converted parquet ref is mutable; do not treat as pin. Public viewer shows 53 patient and 103 trial identifiers, not independently counted.
- Input allowlist: note, criterion_text, criterion_type (identifiers only for grouping). Reference: expert_eligibility and expert_sentences. Block gpt4 outputs, explanation correctness and reference labels from model inputs. Retain training flag for audit; verify meaning in upstream sources. No row-random split. Connected components of patient/trial bipartite graph are preferred groups; if giant component prevents meaningful disjoint partition, use frozen patient-disjoint primary and trial-disjoint sensitivity, disclose residual overlap; no fallback row split.
- Predeclare majority/prior and explicit text/negation/unknown rules; separate multiclass eligible labels from binary decision mapping; verify exact label vocabulary before mapping. Sentence retrieval: fixed note sentence set, token overlap/BM25 baseline; score evidence set precision/recall, exact set, abstentions, cluster intervals. No use of published GPT outputs as predictions of our implementation.

## B09 ranking

Code snapshot observed: https://github.com/ncbi-nlp/TrialGPT/tree/1b3242cd50c153a9c324661d4a0bd94fc68a4226 ; LICENSE has same US government notice. Original cohorts:
- SIGIR: https://data.csiro.au/collection/csiro:17152 (portal requires JS; terms not confirmed here).
- TREC 2021: https://www.trec-cds.org/2021.html ; TREC 2022: https://www.trec-cds.org/2022.html . Synthetic topics, graded relevance judgements, shared April 27 2021 ClinicalTrials.gov snapshot; separate topic sets. Public download instructions verified, not component-specific terms. Corpus is large; first use bounded fixed pools after rights and provenance verification. Do not assume code licence grants all upstream rights.
- NCBI processed files referenced in upstream README; pin exact source and checksum on acquisition. Use original relevance judgements, explicitly distinguish unjudged from judged negative and retrieval ceiling from ranking. Record candidate pool construction and hash, query grouping, contamination limitations. B14 sampled criterion rows are not exhaustive trial-level qrels.

## Gate before execution

1. T00.002 contracts and T14.001 rights/source review complete; approve scope (research only) and institutional determination as applicable.
2. Resolve dataset revision, rights of source components, exact input hashes and schema; validate counts/unique keys/label values, missingness, duplicated notes and patient/trial overlap. Record results without publishing raw restricted data.
3. T14.002 seal group partitions and reference manifest; baseline first; source date, training exposure and model contamination caveat.
4. T14.003/004 record paired predictions, hashes, metrics, budgets, uncertainty, errors and unavailable arms. No data or results acquired by this receipt.
