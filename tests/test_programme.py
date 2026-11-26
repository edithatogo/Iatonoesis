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
    assert [a["id"] for a in data["applications"]] == [f"E{i:02}" for i in range(1, 39)]
    assert len(data["tracks"]) == 20
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


def test_taxonomy_and_issue_registry_cover_programme():
    data = programme()
    registry = json.loads((ROOT / "contracts/project/conductor-issues.v1.json").read_text())
    taxonomy = json.loads((ROOT / "taxonomy/roles.v0.1.0.json").read_text())
    assert len(taxonomy["roles"]) == 22
    assert {app for role in taxonomy["roles"] for app in role["applications"]} == {a["id"] for a in data["applications"]}
    assert registry["issues"] == [{"issue": t["issue"], "track": t["slug"], "task_ids": [x["id"] for x in t["tasks"]]} for t in data["tracks"]]
    for t in data["tracks"]:
        folder = ROOT / "conductor" / "tracks" / t["slug"]
        meta = json.loads((folder / "metadata.json").read_text())
        assert meta["issue"] == t["issue"]
        assert all(task["id"] in (folder / "plan.md").read_text() for task in t["tasks"])
        assert (folder / "spec.md").is_file()


def test_cross_track_task_ownership_rejected():
    data = programme()
    data["tracks"][0]["tasks"][0]["issue"] = 999
    with pytest.raises(ValueError, match="ownership"):
        validate(data)


def test_duplicate_application_rejected():
    data = programme()
    data["applications"].append(copy.deepcopy(data["applications"][0]))
    with pytest.raises(ValueError, match="duplicate"):
        validate(data)


def test_unknown_application_rejected():
    data = programme()
    data["tracks"][0]["tasks"][0]["application"] = "E99"
    with pytest.raises(ValueError, match="application"):
        validate(data)


def test_failed_run_not_acceptance():
    data = programme()
    task = data["tracks"][0]["tasks"][0]
    task["status"] = "accepted"
    task["evidence"] = [{"commit": "a" * 40, "command": "fixture", "outcome": "fail"}]
    with pytest.raises(ValueError, match="evidence"):
        validate(data)


def test_accepted_task_requires_accepted_dependency():
    data = programme()
    task = data["tracks"][0]["tasks"][1]
    task["status"] = "accepted"
    task["evidence"] = [{"commit": "a" * 40, "command": "fixture", "outcome": "pass"}]
    with pytest.raises(ValueError, match="prerequisite"):
        validate(data)
