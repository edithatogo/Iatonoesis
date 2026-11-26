# AGENTS.md

Read [Conductor](conductor/index.md), the track spec and plan and the canonical
[programme](contracts/programme.v1.json) before editing. One writer per owned path;
reconcile current main and open pull requests. Do not silently overwrite another lane.

- src/iatonoesis: research-only command-line and shared experiment tools.
- contracts: machine-readable tasks, application and result definitions.
- conductor: project context, stable task IDs, dependency order, evidence and issue ownership.
- tests: deterministic acceptance and negative tests.
- research: protocols, literature and scientific decisions.

Use the pinned Python starter and `python -m pytest --cov --cov-report=xml` after
installing the test extra. Use `python -m iatonoesis validate` to check the research plan,
and `python -m iatonoesis ready` for dependency-ready tasks. Never mark a task complete
without revision-bound evidence. Use test-first implementation and a focused PR.
Follow [repository-standards](
https://github.com/edithatogo/repository-standards/tree/49b532a8cb5627fe904ae6fa7032b6814fb001f3).
Solo maintainer: no required human approvals or CODEOWNERS gate; required machine checks
must pass. Scientific, clinical, legal and rights gates are independent of code review.
No patient records, clinical deployment, real clinical recommendations, credentials, or
restricted-source text in this public repository. Synthetic or rights-cleared public inputs
only; all external calls and publication opt-in. No clinical safety claims from simulations.
No model-generated data may be represented as an independent clinical gold standard.
