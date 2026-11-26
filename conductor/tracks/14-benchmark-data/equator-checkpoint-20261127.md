# EQUATOR acquisition checkpoint reconciliation — 27 November 2026 (AEST)

T14.001–004 / [#15](https://github.com/edithatogo/Iatonoesis/issues/15), T13/#14; follow-up to merged [#40](https://github.com/edithatogo/Iatonoesis/pull/40) and the [census protocol](../../../research/methods/equator-census-heterogeneity.md). Iatonoesis receiving revision `78d15200bcfa8a27f2bc6c10aed699e4844943ef`. Consumer/evidence lane only. Standards Check owns source acquisition, edition/rights assessment and family/reference lock under [#111](https://github.com/edithatogo/standards_check/issues/111), [#158](https://github.com/edithatogo/standards_check/issues/158) and [#188](https://github.com/edithatogo/standards_check/pull/188), head `a7435884e6c0c1ef3e0c26ab2c740f55bbbb669e` at inspection. Its Assurance run 45836173758 is red; no producer integration or new acquisition authorised by this note. The source owner records project-level research authorization, not blanket third-party permissions. Apps retains layout and Research Agenda retains CQL; neither is changed. #72 owns concurrent T14 plan/index edits, so link this receipt from the existing T14 spec and #40 method rather than edit those shared paths. Canonical task states remain planned.

## Exact retained receipts (read-only; no provider calls)

| Receipt | Producer/source identity | Actual verified digest |
|---|---|---|
| [First bounded checkpoint 45802629341, artifact 15107508921](https://github.com/edithatogo/standards_check/actions/runs/45802629341/artifacts/15107508921) | checkout `8cd98a51bb3ab8fb13e53046cb6684799856ec0c`; source `e34dd7d8559a5df0fe4b7185c093978e4b2d6cbe` | ZIP `be0c2221b737042d0bb4656d1f1f4145324dbaf820112b1e366ba7f402e8676a`; survey JSON `4e05045889b1f8f3a6228466e88d13b2baf866be63ea3c453e305f020fe468e3`; parent survey hash `fc859acaf9ae378b3bb1a2d74be0eeb0ff294319434d83bce6f9a4daf835fa32` (declared in checkpoint, not independently re-read here) |
| [Later directory receipt 45836174045, artifact 15125132946](https://github.com/edithatogo/standards_check/actions/runs/45836174045/artifacts/15125132946) | PR #188 head `a7435884e6c0c1ef3e0c26ab2c740f55bbbb669e`, tested merge indicated by artifact names `9d580176fac9ab385a0d23e5776f7f35d25595d9`; source `b9150c9fa177011694f94a3dcab7a95b1b1bece6` | ZIP `0ae736cbfc6b904fa1a45ddc6a40a1e1f7224c979abb42653f39a5bc69fa21ca`; survey JSON `c4bde82b734b3b5cbca91a9b6c2f96b6c05919b67072d874e4d79e611cae5529` |
| [Later structural observation 45836192308, artifact 15125352116](https://github.com/edithatogo/standards_check/actions/runs/45836192308/artifacts/15125352116) | #188, artifact name tested merge `9d580176fac9ab385a0d23e5776f7f35d25595d9` | ZIP `ebc1c2ab584bc460f5d4d8fbb6ba0daad3548de74767e2d2a64bb7f9ef54fa42`; priority-structure JSON `1e5db4b68a65d4aa7e8e99236a7ebea74f42a3ea82a1210c407de69625c4b4e7` |

Downloaded retained ZIPs using the GitHub artifact interface and independently SHA-256 checked each against API metadata. Inspected JSON in memory using local Python zipfile/json/hashlib; verified unique worklist PMCID inventory, exact DOI/PMID/directory-ID/source-blob binding for **205/205** first-checkpoint and **207/207** later bulk rows; joined **720/720** later catalogue and survey IDs and blob hashes. No raw source text or third-party documents copied. No new software, model run, provider request or source fetch.

## Separate denominators, not a corpus-performance result

| Stage | First checkpoint (source e34dd7d) | Later receipt (source b9150c9) |
|---|---:|---:|
| Directory metadata identities | 720 | 720 |
| OA XML candidates (reported, not acquired) | 209 | 210 |
| Metadata only | 379 | 379 |
| Lookup incomplete | 56 | 51 |
| Missing identifier | 76 | 74 |
| Identifier conflict / unresolved identifier | 0 / 0 | 3 / 3 |
| Bulk acquisition worklist (unique PMCID records, not documents or families) | 205 | 207 |
| Deferred / held / source inventory observed | 200 / 4 / 1 | 204 / 2 / 1 |
| Bulk source hashes observed | 1 | 1 |
| Bulk checklist item matches / retained item anchors | 0 / 0 | 0 / 0 |
| Priority manifestations held / numbered rows observed | 6 / 0 | 7 / 1 |
| Priority matched item rows / anchors | 0 / 0 | 42 / 42 (CONSORT 2025, table/item rights unassessed) |
| Newly promoted canonical packs | 0 | 0 |
| Independent EQUATOR model-evaluation cases evidenced by these receipts | 0 | 0 |

The existing #40 analysis of source revision 388e294f (720 identities, 189 OA leads, 186 bulk records) is a **third historical snapshot**, not the parent of the first bulk checkpoint. The first checkpoint's one observed bulk source is PMC10160267 (CC BY 4.0 observed at article level, exact source SHA-256 `4d60e0af1752cbe8267f69f4034e7adbc40852e9e802e079bae90750a1533e26`): one 66-body-row table inventory, **zero matched checklist items**, table/item reuse unassessed. No inference that 66 body rows are obligations. The later priority source contains 42 numbered rows/anchors at source SHA-256 `f9fbfe00268baad460722d487f2871730ec104cceccd7476a30d15fce382b56e`; these are extractable-source observations, not independent reference labels, admitted test cases or released checklist text. The later structural artifact records TRIPOD+AI and STROBE as source_observation_only, scientific qualification false, public redistribution qualification false, zero promotions; do not count it as an independent layout experiment.

The first checkpoint separately contains a PRISMA 2020 pack diagnostic (pack SHA-256 `56f79ee76d463c3878431a0342f127a1bcc89c019d636e4f28afdc0dfc462ec1`; pack-evidence-inventory JSON SHA-256 `64df8dd8ace0873746d1f6906fc2336ce47218abc935bc0ce2470cd004afe54b`): **one pack, 42 masked same-source item-identity queries, 1,764 query/candidate pairs**, advisory only. This is an actual upstream diagnostic, not independent semantic relevance, held-out families or complete corpus evaluation. Do not add it to the directory count. Iatonoesis #40's historical synthetic paired replay (40 pages/240 intended links per modality) is also not an EQUATOR case count. Other external datasets are separate.

## Two failed attempts, four untouched selections

First checkpoint: prior inventory 202 deferred, 2 held, 1 observed; selected six, attempted two; 200 deferred, 4 held, 1 observed afterwards. Four provider attempts across the two attempted articles, no verified bytes, no item rows. Both retained records have identical current source-ID/DOI/PMID/blob bindings and unchanged acquisition receipts in the later directory snapshot.

| PMCID / DOI / PMID | Retained directory binding | Reported licence | Disposition |
|---|---|---|---|
| PMC10155050 / 10.1136/bmj-2022-073538 / 37137496 | equator:tripod-srma; 71faa039c5925eae3fbd61f4ce4acb701bed0f68 | CC BY (metadata) | Europe PMC TimeoutError; PMC OAI ValueError, unavailable_or_held; no article bytes; hold |
| PMC10182844 / 10.1186/s12874-023-01888-7 / 37179308 | equator:triple-c-reporting-principles-for-case-study-evaluations-of-the-role-of-context-in-complex-interventions; 470f4dcc3c452976285a3c43ba4295fcd126f156 | CC BY (metadata) | Europe PMC TimeoutError; PMC OAI ValueError, unavailable_or_held; no article bytes; hold |
| PMC10245063 / 10.1016/j.heliyon.2023.e16780 / 37292336 | bibliometric reporting guideline proposal; c9fd4af76b2307508ca543a4d990c3dd7401903b | CC BY-NC-ND (metadata) | selected not attempted; exact permissible processing/derivative use and item scope unresolved |
| PMC10251230 / 10.2196/45662 / 37227772 | analysis-ready RWE/EHR data tutorial; 38e55c29f5400384f70d70c84dfec1a0d607276b | CC BY (metadata) | selected not attempted; permissive lead only, exact article/table/checklist source and permitted scope unresolved |
| PMC10364529 / 10.1093/bjs/znac394 / 36413510 | CONFERD-HP; 7d25114ac9b40dc94949be6262bf1ca81ec8a492 | CC BY (metadata) | selected not attempted; same unresolved source-specific rights and checklist scope |
| PMC10389401 / 10.1097/js9.0000000000000373 / 37013953 | SCARE; a19f2d6293f05d7b24498bab9d398bf41fa97eb7 | CC BY-NC-ND (metadata) | selected not attempted; exact permitted scope unresolved |

All six have reported rights state unassessed_article_and_table_reuse and no provider identity disagreements in the two receipts. Candidate status is not actual rights or benchmark eligibility. Europe PMC timeouts are transport failures. PMC OAI ValueError has no retained response bytes, specific error body or code sufficient to distinguish invalid response, identity/structure rejection, unavailable content or reuse restriction. Do not infer copyright denial, nonexistence or permission from it. Circuit breaker stopped after two consecutive holds; no repeated attempt or alternative provider introduced.

The later source revision has 720 identical directory IDs, 706 unchanged source blobs, 14 changed; unique bulk worklist added 13 and removed 11 PMCIDs. It is **not** a continuation of the first checkpoint by count. All six selected records remain identical. Crucially PMC10196944 (10.1016/j.euros.2023.04.014, CC BY-NC-ND metadata) and PMC10209789 (10.2196/46694, CC BY metadata) changed from held to deferred in the later snapshot. Their first-checkpoint receipts retain Europe PMC OSError and PMC OAI ValueError; no evidence of clearance or resolved failure. Preserve historical holds when reconciling producer receipts; do not reclassify as never attempted or retry automatically.

## Smallest next batch and stop decision

Original checkpoint's ordered next unattempted single candidate is PMC10245063, followed by PMC10251230, PMC10364529 and PMC10389401 (all four already-selected, not attempted). The producer's existing six-candidate bounded resume and failure breaker remain unchanged. Do not substitute the later snapshot's head-of-queue PMC10196944/PMC10209789 as new unattempted cases. The four original candidates remain metadata candidates only; their exact permitted processing/edition/actual checklist content is not established here. Among the previously selected unattempted candidates, PMC10251230 is the earliest with a reported permissive CC BY lead; PMC10364529 is the next. A **single** owner-approved eligible candidate would be the smallest diagnostic, only if the producer confirms a permitted exact source and scope and authorises that selection/route without skipping existing holds or altering the circuit breaker. Neither is established as eligible for a fresh acquisition in this consumer lane, nor independently reference-qualified. Do not run a new acquisition, relabel, retry or route around the producer's ownership or held constraints. **Executable next batch in Iatonoesis: zero.** The existing producer #188 retains all acquisition and rights work and its protected gates; no competing crawler, new provider, or source acquisition requested. Record these concrete blockers under #15 and preserve T14.001–004 open. No claim of entire-corpus evaluation.
