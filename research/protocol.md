# Prospective protocol v0.1.0 (draft)

For each E01–E38: compare a simple conventional baseline and at least one specialist challenger on fixed, independently adjudicated evaluation cases. Human comparator and human-assisted arms follow only when approved. Use separate development/calibration/test partitions, grouped by source/site/cohort and time where possible; no threshold tuning on test. Report paired estimates, uncertainty, denominators, abstentions, critical errors, computation and staff/patient-relevant proxy outcomes. Synthetic results are simulations, not clinical effectiveness.

Record input/output schema, model architecture versus task role, exact revision, licence, training/label signal, data provenance, baseline, resource budget, error and reviewer, and result receipt. Stop or abstain on unsupported evidence. Retain failed runs. Source claims require primary citations and maturity; the initial documented-underlying labels in the programme are candidate claims to verify, not a completed literature review.

Workflow A: referral layout → tags → capability graph and fixed-pool ranking → urgency decision and constrained router → human acceptance → handover verification.
Workflow B: standards/clinical records/evidence → layout and tags → graph → step verification and analogous-case ranking → bounded decision and evidence appraisal → accountable routing → human improvement and independent outcomes.

Measure each component with reference upstream inputs, then actual upstream outputs, then a matched baseline substitution. Keep candidate sets fixed for rerankers; compare learned graph to deterministic graph; use paired confidence intervals and report interactions. No deployment, publication or patient data use authorised by this protocol.

## Extension

The [functional-specialisation supplement](functional-specialisation.v0.1.0.md) defines five comparison arms, matched budgets, literature extraction and public/synthetic dataset qualification. T14 owns shared benchmark contracts; T15–T19 own additional roles. T18.001 is exploratory toy mutation testing, not clinical CQL evidence. Human references and public release require separate authorization. Do not pool incomparable endpoints into a universal score.
