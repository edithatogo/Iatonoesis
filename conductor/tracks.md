# Conductor tracks

All tracks contracted; no experiments run. [Programme](../contracts/programme.v1.json) and [issue registry](../contracts/project/conductor-issues.v1.json) are authoritative. Task dependencies govern execution.

| ID | Track | Track dependencies | Task-level cross-track prerequisites | Tasks | Issue | State |
|---|---|---|---|---:|---|---|
| 00 | [Research infrastructure](tracks/00-foundation/spec.md) | none | none | 7 | [#1](https://github.com/edithatogo/Iatonoesis/issues/1) | planned |
| 01 | [Layout-aware document readers](tracks/01-layout-readers/spec.md) | T00 (#1) | T00 (#1), T11 (#12), T14 (#15) | 13 | [#2](https://github.com/edithatogo/Iatonoesis/issues/2) | planned |
| 02 | [Extractive taggers](tracks/02-extractive-taggers/spec.md) | T00 (#1) | T00 (#1), T11 (#12), T14 (#15) | 13 | [#3](https://github.com/edithatogo/Iatonoesis/issues/3) | planned |
| 03 | [Graph models](tracks/03-graph-models/spec.md) | T00 (#1) | T00 (#1), T11 (#12), T14 (#15) | 13 | [#4](https://github.com/edithatogo/Iatonoesis/issues/4) | planned |
| 04 | [Decision models](tracks/04-decision-models/spec.md) | T00 (#1) | T00 (#1), T11 (#12), T14 (#15) | 13 | [#5](https://github.com/edithatogo/Iatonoesis/issues/5) | planned |
| 05 | [Rerankers](tracks/05-rerankers/spec.md) | T00 (#1) | T00 (#1), T11 (#12), T14 (#15) | 13 | [#6](https://github.com/edithatogo/Iatonoesis/issues/6) | planned |
| 06 | [Routers](tracks/06-routers/spec.md) | T00 (#1) | T00 (#1), T11 (#12), T14 (#15) | 13 | [#7](https://github.com/edithatogo/Iatonoesis/issues/7) | planned |
| 07 | [Evidence evaluators](tracks/07-evidence-evaluators/spec.md) | T00 (#1) | T00 (#1), T11 (#12), T14 (#15) | 13 | [#8](https://github.com/edithatogo/Iatonoesis/issues/8) | planned |
| 08 | [Step verifiers](tracks/08-step-verifiers/spec.md) | T00 (#1) | T00 (#1), T11 (#12), T14 (#15) | 13 | [#9](https://github.com/edithatogo/Iatonoesis/issues/9) | planned |
| 09 | [Integrated multi-model workflows](tracks/09-orchestration/spec.md) | T00 (#1) | T00 (#1), T01 (#2), T02 (#3), T03 (#4), T04 (#5), T05 (#6), T06 (#7), T07 (#8), T08 (#9), T15 (#16), T17 (#18), T18 (#19), T19 (#20) | 7 | [#10](https://github.com/edithatogo/Iatonoesis/issues/10) | planned |
| 10 | [Emerging models and literature discovery](tracks/10-emerging-models/spec.md) | T00 (#1) | T00 (#1) | 6 | [#11](https://github.com/edithatogo/Iatonoesis/issues/11) | planned |
| 11 | [Safety, equity and model assurance](tracks/11-assurance/spec.md) | T00 (#1) | T00 (#1), T17 (#18), T18 (#19), T19 (#20) | 7 | [#12](https://github.com/edithatogo/Iatonoesis/issues/12) | planned |
| 12 | [Health economics and implementation science](tracks/12-economics/spec.md) | T00 (#1) | T00 (#1), T16 (#17), T17 (#18) | 5 | [#13](https://github.com/edithatogo/Iatonoesis/issues/13) | planned |
| 13 | [Publication and dissemination](tracks/13-publication/spec.md) | T00 (#1) | T00 (#1), T09 (#10), T10 (#11), T11 (#12), T12 (#13), T14 (#15) | 7 | [#14](https://github.com/edithatogo/Iatonoesis/issues/14) | planned |
| 14 | [Public data, reference standards and comparative benchmark](tracks/14-benchmark-data/spec.md) | T00 (#1), T10 (#11), T12 (#13) | T00 (#1), T10 (#11), T12 (#13) | 4 | [#15](https://github.com/edithatogo/Iatonoesis/issues/15) | planned |
| 15 | [State reconstruction, world models, recoverability and ascertainment](tracks/15-dynamics/spec.md) | T00 (#1), T14 (#15) | T00 (#1), T11 (#12), T14 (#15) | 4 | [#16](https://github.com/edithatogo/Iatonoesis/issues/16) | planned |
| 16 | [Information acquisition, adaptive experiments and scientific data value](tracks/16-information-science/spec.md) | T00 (#1), T14 (#15) | T00 (#1), T14 (#15), T15 (#16) | 3 | [#17](https://github.com/edithatogo/Iatonoesis/issues/17) | planned |
| 17 | [Affordance, constraint acquisition and learned optimisation](tracks/17-feasibility-optimisation/spec.md) | T00 (#1), T14 (#15) | T00 (#1), T11 (#12), T14 (#15) | 3 | [#18](https://github.com/edithatogo/Iatonoesis/issues/18) | planned |
| 18 | [Counterexamples, failure attribution and transportability](tracks/18-system-assurance/spec.md) | T00 (#1), T14 (#15) | T00 (#1), T11 (#12), T14 (#15) | 4 | [#19](https://github.com/edithatogo/Iatonoesis/issues/19) | planned |
| 19 | [Clinical commitment stewardship](tracks/19-commitment-memory/spec.md) | T00 (#1), T14 (#15) | T00 (#1), T11 (#12), T14 (#15) | 2 | [#20](https://github.com/edithatogo/Iatonoesis/issues/20) | planned |

Original IDs retained. See [roadmap](roadmap.md).
