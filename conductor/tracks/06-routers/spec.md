# T06 — Routers

Owner: [#7](https://github.com/edithatogo/Iatonoesis/issues/7). Research-only. Canonical tasks: [programme](../../../contracts/programme.v1.json).

## E16: Specialist referral routing

Classification: documented underlying capability; setting: patient access.

Workflow: Referral officer approves feasible service.

Input: synthetic referral, capabilities and roster. Output: candidate destination, confidence and reasons.

Comparator: fixed specialty map. Failure and reviewer: service lacks capability; capability rule and clinician override.

Feasibility cohort: 300 scenarios. Model metric: destination accuracy and unsafe routing. Workflow outcome: redirects and time to acceptance.

## E17: Governance request routing

Classification: adaptation; setting: administration.

Workflow: Owner confirms responsibility and consultation.

Input: synthetic requests and delegations. Output: owner, consultation and approval route.

Comparator: decision tree. Failure and reviewer: wrong delegation; governance officer checks register.

Feasibility cohort: 200 requests. Model metric: owner accuracy and missed consultation. Workflow outcome: touches and turnaround.

## E18: Adaptive human/rule/model routing

Classification: hypothesis; setting: rural operations.

Workflow: Constrained router suggests safe processing pathway.

Input: simulated workload, connectivity, uncertainty and risk. Output: eligible destination or human escalation.

Comparator: static router and largest-model policy. Failure and reviewer: unsafe cheap route; hard constraint and human escalation.

Feasibility cohort: 500 simulated tasks. Model metric: unsafe routing and risk–coverage. Workflow outcome: latency, workload and compute cost.

All claims and research progress remain unverified until the corresponding evidence is captured.
