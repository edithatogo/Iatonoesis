# Model-informed deterministic rule refinement — exploratory executed receipt

[Protocol](../protocols/T18-model-informed-rule-refinement-v0.1.0.md), T18/#19, T17/#18, T08/#9, T09/#10, T11/#12, T14/#15. Discovery: actual #44 E22 six neural/rule disagreements at verified freeze and result digests. All six neural outputs completed, but three references were late. The observed narrative form is an analyst-generated rule candidate; no claim of automatic rule discovery or superiority over an expert finding the same gap.

The 19 synthetic stress cases were frozen in commit 444cfc79088357c72466886b5f22d0cd7431cf5b prior to candidate execution. All arms see the same inputs, including newly supplied synthetic provenance, exception and observation horizon fields. Compare unchanged legacy verify_steps, exact phrase alias only and guarded rules. The guarded version is explicit, inspectable, reason-coded and requires no AI model or model runtime.

| Arm | Exact | False timely | Missed required review | Unnecessary review | Total reviews |
|---|---:|---:|---:|---:|---:|
| Legacy | 10/19 | 3 | 7/11 | 2/8 | 6 |
| Alias only | 11/19 | 4 | 8/11 | 0/8 | 3 |
| Refined | 19/19 | 0 | 0/11 | 0/8 | 11 |

Alias recognition recovered the two previously unresolved attested examples, but added an unverified completion. The refined rule rejects untrusted evidence, malformed/future timestamps, conflicting dates and unverified/contradictory exceptions, and only classifies a missing step after the deadline with a complete log. Eleven cases genuinely need review by the synthetic specification: do not count review as completed care. Review burden increases appropriately; do not conclude cost savings.

Test-first local RED missing module, then 4 tests passed on Python 3.13.5, 75/76 source statements covered, 99% rounded. Exact legacy, common metric, source, test and fixture Git blobs recorded and checked. Two executions identical byte-for-byte. Reproduce:
```sh
PYTHONPATH=src python -m iatonoesis.rule_feedback --fixtures datasets/fixtures/rule-feedback-v0.1.0.json --output /tmp/rule-feedback.json
PYTHONPATH=src python -m pytest -q tests/test_rule_feedback.py
```
[Aggregate receipt](../../results/exploratory/rule-feedback-v0.1.0.json). Hosted checks pending. Purposefully designed cases, expected outputs authored before implementation but not blinded or independently adjudicated; no clinical validity or promotion to production. Next, compare analyst-only, deterministic counterexample, random review and model-assisted candidate discovery at matched budgets on genuinely new independent sources; count accepted rules, failures prevented, complexity, safe review burden, runtime and changes required in source systems. Preserve candidate rejection and rollback.
