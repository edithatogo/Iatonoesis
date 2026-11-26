# E02 rendered-PDF qualifier-binding feasibility pilot

Owner: T01.006–009 / #2. Related #24 token-only pilot, #29 common paired runner, T00 and T14. This is an exploratory simulation, not acceptance of a canonical task.

## Method

Generate 140 single-page text-layer PDFs from independently represented intended links (six per page) with the dependency-free synthetic renderer; no patient data, external source text, OCR or network calls. 20 development pages, 20 calibration pages and 100 test pages (five distinct template families, 20 each). The first two partitions are reserved, not used for fitting. Test families deliberately challenge content stream order, superscript markers, markers positioned to the left of a requirement, and damage or contradictory footnote labels. One seed (17). Use Poppler 25.06.0 `pdftotext -bbox -enc UTF-8` on actual generated PDF bytes. Compare a reading-order parser with the same extracted word sequence plus geometric constraints. Both share Poppler's initial extraction. Score exact requirement/qualifier pairs; retain missing intended links even where evidence has been damaged; report coverage and false binding separately.

## Results

| Arm | TP | FP | FN | Micro-F1 | Exact pages |
|---|---:|---:|---:|---:|---:|
| Reading-order baseline | 450 | 100 | 150 | 0.782609 | 60/100 |
| Spatial rule | 450 | 0 | 150 | 0.857143 | 60/100 |

Both recover 75% of the 600 intended test links. The spatial rule raises precision from 81.8% to 100% **without recovering any extra true links**. Both recover every link in detached-stream, reverse-stream and superscript families: the PDF extractor already repairs reading order. Both recover zero of 120 left-marker links; spatial avoids 100 false bindings rather than solving the task. Both leave 30 damaged links unresolved. This negative finding materially qualifies the much larger F1 gain seen in #24's token-only simulation.

## Reproduction and limits

From repository root after installing the package, with Poppler 25.06.0 installed: `python -m iatonoesis.policy_pdf_pilot --seed 17 --output run17.json`. Local isolated tests: `PYTHONPATH=src python -m pytest -q tests/test_policy_pdf_pilot.py` (six pass after initial RED). Two executions produced byte-identical raw JSON; receipt records full raw output SHA-256, PDF and extraction manifests, per-arm prediction hashes, and per-document counts. Local visual inspection of representative rendered PDF confirms the toy three-column layout. See [versioned receipt](../../results/exploratory/E02-pdf-pilot-seed17.json). The full generated output contains case-level gold and predicted tuples and source/extraction hashes; reconstruct using command. No actual OCR, image-only scans, natural policy prose, complex hierarchies or independent annotation; no human or clinical outcome. Generation and rules were authored together; family split alone does not establish independence. No learned arm or canonical acceptance. Poppler is an explicit optional runtime and is not installed by the pilot; unit tests do not assert external-tool availability. A full common-contract, time/budget and hosted end-to-end run is still needed. Freeze future bidirectional marker and OCR experiments on separate unseen templates before evaluation; do not tune the current test set and relabel it confirmatory.
