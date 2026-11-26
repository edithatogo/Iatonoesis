# Iatonoesis

Research laboratory for specialist computational models in healthcare, medicine,
public health and learning health systems.

**Research only.** Not a clinical decision tool, medical device or deployment.
No patient data in this public repository.

The initial programme has eight model families, 24 application hypotheses or
adaptations, two integrated workflow studies and cross-cutting research tracks.
The question is when specialist learned models add measurable value over simple
rules, conventional software and professional judgment.

## Start here

- [Conductor index](conductor/index.md) and [track index](conductor/tracks.md).
- [Research programme](contracts/programme.v1.json) and [protocol](research/protocol.md).
- [Contribution and validation](CONTRIBUTING.md), [security](SECURITY.md),
  [citation](CITATION.cff), [MIT licence](LICENSE).
- [Adopted template and policy revisions](conductor/bootstrap-evidence.md).

```sh
git submodule update --init --recursive
python3.15 -m venv .venv
.venv/bin/python -m pip install -e ".[test]"
.venv/bin/python -m iatonoesis validate
.venv/bin/python -m iatonoesis ready
.venv/bin/python -m pytest --cov --cov-report=xml
```

Tasks and research outcomes remain planned until a specific result is recorded.
No claim of clinical efficacy, scientific novelty, data approval or provider
activation follows from the initial setup.
