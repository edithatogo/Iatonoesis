# E02 exploratory synthetic qualifier-binding pilot

Related: [comparative benchmark protocol](../comparative-study.md), E02 and T01/#2, common runner T00.003/#1, benchmark T14/#15. This is a feasibility simulation performed separately while upstream qualification is pending, not the accepted E02 experiment.

96 generated fictional administrative policy documents, eight template IDs, 24 development, 24 calibration, 48 test. Each contains four requirement–footnote associations generated before token rendering. The comparator only receives visible text and token coordinates; four markers deliberately omitted in one test family. Family IDs are disjoint; rendering patterns recur. No authentic documents, OCR, patient data, or learned models.

Compare preceding-requirement flat-text binding against a simple deterministic geometric rule. Both use identical input tokens. Score exact tuple-set micro-F1 and exact document counts. Four missing markers yield false negatives even for the spatial method. This generator deliberately tests an ordering failure mode, not external validity or general clinical safety.

Local result: flat 116 TP, 72 FP, 76 FN, F1 0.6105, exact 24/48; spatial 188 TP, 0 FP, 4 FN, F1 0.9895, exact 44/48. No learned comparison executed. These numbers must not be cited as medical-document accuracy.

Reproduction after installing repository: `python -m iatonoesis.policy_layout_pilot --seed 17 --output policy-layout-pilot.json`. Full raw per-document predictions, intended reference tuples and counts are emitted into that file. Versioned aggregate receipt: [pilot result](../../results/exploratory/E02-layout-pilot-seed17.json). Verify the full output SHA-256 against receipt; Python version and determinism may affect cross-environment reproducibility. Local isolated tests: `PYTHONPATH=src python -m pytest -q tests/test_run_contracts.py tests/test_policy_layout_pilot.py`: 16 passed. Full hosted suite not yet observed. No canonical task state changed.

Next qualify independently rendered rights-cleared PDFs/images and separately adjudicated requirements, tables and footnotes; freeze and hash actual inputs, references, splits and candidate arms before confirmatory runs. Use OCR and conventional PDF extraction as comparators; include uncertainty, resource use and errors per document/family. Do not mistake synthetic oracle correctness for validated clinical labels.
