import copy
import json
from pathlib import Path

import pytest

from iatonoesis.programme import validate, ready

ROOT = Path(__file__).resolve().parents[1]


def programme():
    return json.loads((ROOT / "contracts/programme.v1.json").read_text())


def test_initial_programme():
    data = programme()
    validate(data)
    assert len(data["applications"]) == 24
    assert [x["id"] for x in ready(data)] == ["T00.001"]


def test_duplicate_task_rejected():
    data = programme()
    data["tracks"][0]["tasks"].append(copy.deepcopy(data["tracks"][0]["tasks"][0]))
    with pytest.raises(ValueError, match="duplicate"):
        validate(data)


def test_unknown_dependency_rejected():
    data = programme()
    data["tracks"][0]["tasks"][0]["depends_on"] = ["T99.999"]
    with pytest.raises(ValueError, match="unknown dependency"):
        validate(data)


def test_cycle_rejected():
    data = programme()
    data["tracks"][0]["tasks"][0]["depends_on"] = ["T00.002"]
    with pytest.raises(ValueError, match="cycle"):
        validate(data)


def test_completion_requires_evidence():
    data = programme()
    data["tracks"][0]["tasks"][0]["status"] = "accepted"
    with pytest.raises(ValueError, match="evidence"):
        validate(data)


def test_next_task_requires_accepted_prerequisite():
    data = programme()
    first = data["tracks"][0]["tasks"][0]
    first["status"] = "accepted"
    first["evidence"] = [{"commit": "a" * 40, "command": "fixture", "outcome": "pass"}]
    assert [x["id"] for x in ready(data)] == ["T00.002"]
