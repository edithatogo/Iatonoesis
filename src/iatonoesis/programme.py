"""Validate the programme and list dependency-ready tasks; no external calls."""

import re


TASK_STATES = {"planned", "in_progress", "blocked", "accepted", "deferred"}


def _unique(items, key, kind):
    result = {}
    for item in items:
        value = item[key]
        if value in result:
            raise ValueError(f"duplicate {kind}: {value}")
        result[value] = item
    return result


def _acyclic(items, kind):
    active, visited = set(), set()

    def visit(key):
        if key in active:
            raise ValueError(f"{kind} dependency cycle at {key}")
        if key in visited:
            return
        if key not in items:
            raise ValueError(f"unknown dependency: {key}")
        active.add(key)
        for dependency in items[key]["depends_on"]:
            visit(dependency)
        active.remove(key)
        visited.add(key)

    for key in items:
        visit(key)


def _has_pass(evidence):
    return any(
        isinstance(entry, dict)
        and entry.get("outcome") == "pass"
        and isinstance(entry.get("commit"), str)
        and re.fullmatch(r"[0-9a-f]{40}", entry["commit"])
        and isinstance(entry.get("command"), str)
        and bool(entry["command"].strip())
        for entry in evidence
    )


def validate(data):
    """Reject invalid identity, ownership, dependencies and acceptance receipts."""
    if data.get("schema_version") != 1:
        raise ValueError("unsupported programme schema version")
    tracks = _unique(data["tracks"], "id", "track")
    _unique(data["tracks"], "issue", "track issue")
    _unique(data["tracks"], "slug", "track slug")
    apps = _unique(data["applications"], "id", "application")
    tasks = _unique([task for track in tracks.values() for task in track["tasks"]], "id", "task")
    _acyclic(tracks, "track")
    _acyclic(tasks, "task")
    for track_id, track in tracks.items():
        if not re.fullmatch(r"[0-9]{2}", track_id):
            raise ValueError(f"invalid track ID: {track_id}")
        for task in track["tasks"]:
            key = task["id"]
            if not re.fullmatch(rf"T{track_id}\.[0-9]{{3}}", key) or task["issue"] != track["issue"]:
                raise ValueError(f"task ownership mismatch: {key}")
            app = task.get("application")
            if app is not None and (app not in apps or apps[app]["track"] != track_id):
                raise ValueError(f"unknown or mismatched application: {app}")
            if task["status"] not in TASK_STATES:
                raise ValueError(f"unknown task status: {key}")
            if task["status"] == "accepted":
                if not _has_pass(task["evidence"]):
                    raise ValueError(f"accepted task lacks passing revision-bound evidence: {key}")
                if any(tasks[dep]["status"] != "accepted" for dep in task["depends_on"]):
                    raise ValueError(f"accepted task has unaccepted prerequisite: {key}")
    assigned = {task["application"] for task in tasks.values() if task.get("application") is not None}
    for app_id, app in apps.items():
        if app["track"] not in tracks or app_id not in assigned:
            raise ValueError(f"unowned application: {app_id}")
    if any(priority not in apps for priority in data["priorities"]):
        raise ValueError("unknown priority application")


def ready(data):
    """Return planned tasks whose exact task dependencies are accepted."""
    validate(data)
    tasks = [task for track in data["tracks"] for task in track["tasks"]]
    accepted = {task["id"] for task in tasks if task["status"] == "accepted"}
    return [task for task in tasks if task["status"] == "planned" and set(task["depends_on"]) <= accepted]
