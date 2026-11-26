# Workflow

1. Read index, active plan, current main and open PRs. Use one writer per path.
2. Choose a dependency-ready stable task; link its issue. Freeze hypothesis, comparator, inputs, metrics and failure criteria.
3. Add failing acceptance tests before behaviour; run smallest vertical slice and full validation.
4. Capture exact commit, command, versions, dataset hashes, seed, predictions, timing and pass/fail/skip/unavailable; distinguish simulation from clinical evidence.
5. Update canonical programme, plan view, evidence and issue registry together. No unchecked completion or fabricated review. No second maintainer required; required automated checks pass before merge.
6. Recheck receiving main and retain receipts. Negative research outcomes are results, not test failures to hide.

`python -m iatonoesis validate`, `python -m iatonoesis ready`, and `python -m pytest --cov --cov-report=xml` are the initial local commands. More experiment commands are introduced as tasks are implemented. Human scientific review and governance approvals remain independently required when applicable.
