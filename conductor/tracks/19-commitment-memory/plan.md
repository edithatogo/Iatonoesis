# T19 — Clinical commitment stewardship

Issue [#20](https://github.com/edithatogo/Iatonoesis/issues/20). Stable task IDs; canonical [programme](../../../contracts/programme.v1.json). Cross-track prerequisites: T00 (#1), T11 (#12), T14 (#15). Downstream consumers: T09 (#10), T11 (#12). [Roadmap](../../roadmap.md).

- [ ] **T19.001** — Commitment event contract (#20)
  - Depends on: T14.002, T11.001.
  - Accept: Synthetic FHIR Task history with provenance, ownership, supersession, cancellation and completion; independently verified lifecycle oracle.
  - Evidence: pending; record exact revision, commands, fixtures and outcomes.
- [ ] **T19.002** — Compare commitment stewardship (#20)
  - Depends on: T19.001, T14.004, T00.006.
  - Accept: State machine vs prompted and learned proposals on held-out event templates; false closure, missed and duplicate obligations; human-authorised closure.
  - Evidence: pending; record exact revision, commands, fixtures and outcomes.
