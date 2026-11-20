"""Offline, bounded consistency checks for unsigned local browser evidence."""

import hashlib
import json
from pathlib import Path

from veriagent.browser_execution import audit_browser_state
from veriagent.interpretation import proposal_digest
from veriagent.models import Budget, Issue, RunReport, Task, TaskProposal

MAX_FILE_BYTES = 16 * 1024 * 1024
MAX_TOTAL_BYTES = 64 * 1024 * 1024
REQUIRED = {
    "result.json",
    "trace.json",
    "trace.txt",
    "browser-events.json",
    "application-events.json",
}


def _read(directory: Path, name: str) -> bytes:
    # Inventory names are leaf filenames, never paths or external references.
    if not name or name in {".", ".."} or "/" in name or "\\" in name or ":" in name:
        raise ValueError("Invalid evidence filename")
    path = directory / name
    if path.is_symlink() or path.resolve().parent != directory.resolve():
        raise ValueError("Evidence must stay inside its directory")
    with path.open("rb") as stream:
        data = stream.read(MAX_FILE_BYTES + 1)
    if len(data) > MAX_FILE_BYTES:
        raise ValueError("Evidence file exceeds limit")
    return data


def seal_browser_evidence(directory: Path) -> None:
    names = sorted(p.name for p in directory.iterdir() if p.is_file() and p.name != "evidence.json")
    inventory = {}
    total = 0
    for name in names:
        raw = _read(directory, name)
        total += len(raw)
        if total > MAX_TOTAL_BYTES or len(names) > 64:
            raise ValueError("Evidence bundle exceeds limit")
        inventory[name] = {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
    (directory / "evidence.json").write_text(
        json.dumps({"schema_version": 1, "files": inventory}, indent=2) + "\n", encoding="utf-8"
    )


def audit_browser_evidence(directory: Path) -> dict:
    result = {
        "schema_version": 1,
        "evidence_passed": False,
        "task_passed": None,
        "checks": [],
        "limitations": "Unsigned local consistency check; not authenticated provenance.",
    }

    def check(name, passed):
        result["checks"].append({"check": name, "passed": bool(passed)})

    try:
        inventory = json.loads(_read(directory, "evidence.json"))
        files = inventory["files"]
        if (
            inventory["schema_version"] != 1
            or not isinstance(files, dict)
            or not 1 <= len(files) <= 64
        ):
            raise ValueError("Invalid inventory")
        check("required_files", REQUIRED <= files.keys())
        data = {}
        total = 0
        for name, expected in files.items():
            raw = _read(directory, name)
            total += len(raw)
            if total > MAX_TOTAL_BYTES:
                raise ValueError("Evidence bundle exceeds limit")
            check(
                "hash:" + name,
                expected == {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()},
            )
            data[name] = raw
        bundle = json.loads(data["result.json"])
        if bundle["schema_version"] != 1:
            raise ValueError("Unknown result schema")
        task = Task.model_validate(bundle["task"])
        proposal = TaskProposal.model_validate(bundle["proposal"])
        Budget.model_validate(bundle["budget"])
        check("reviewed_task", proposal.task() == task)
        check("approval_digest", proposal_digest(proposal) == bundle["approval_digest"])
        initial, final = bundle["initial_state"], bundle["final_state"]
        for rows in (initial, final):
            if not isinstance(rows, list) or not 1 <= len(rows) <= 100:
                raise ValueError("Invalid state snapshot")
            for row in rows:
                Issue.model_validate(row)
                if type(row["version"]) is not int or row["version"] < 0:
                    raise ValueError("Invalid state version")
            if len({row["id"] for row in rows}) != len(rows):
                raise ValueError("Duplicate state row")
        saved = bundle["result"]
        if any(
            type(value) is not bool
            for value in (saved["browser"]["cleanup_completed"], saved["browser_execution_passed"])
        ):
            raise ValueError("Invalid outcome flags")
        report = RunReport.model_validate({k: saved[k] for k in RunReport.model_fields})
        audit = audit_browser_state(task, initial, final)
        check("state_audit", audit == saved["browser_audit"])
        task_passed = (
            report.claimed_success and audit["passed"] and saved["browser"]["cleanup_completed"]
        )
        result["task_passed"] = bool(task_passed)
        check("execution_outcome", task_passed == saved["browser_execution_passed"])
        events = json.loads(data["application-events.json"])
        browser_events = json.loads(data["browser-events.json"])
        if (
            not isinstance(events, list)
            or len(events) > 2048
            or not isinstance(browser_events, list)
            or len(browser_events) > 2048
        ):
            raise ValueError("Invalid event log")
        check("complete_event_logs", saved["browser"]["events_dropped"] == 0)
        states = {row["id"]: (row["status"], row["version"]) for row in initial}
        replay_ok = True
        for event in events:
            before = (event["before_status"], event["before_version"])
            after = (event["after_status"], event["after_version"])
            committed = before != after
            replay_ok &= states.get(event["issue_id"]) == before
            replay_ok &= event["committed"] == committed
            replay_ok &= not committed or (after == (event["requested_status"], before[1] + 1))
            states[event["issue_id"]] = after
        check(
            "application_event_replay",
            replay_ok and states == {row["id"]: (row["status"], row["version"]) for row in final},
        )
        trace = json.loads(data["trace.json"])
        if not isinstance(trace, list) or not 1 <= len(trace) <= 10000:
            raise ValueError("Invalid trace")
        tasks = [e["payload"] for e in trace if e["kind"] == "task"]
        reviews = [e["payload"] for e in trace if e["kind"] == "requirements_review"]
        reports = [e["payload"] for e in trace if e["kind"] == "report"]
        check("trace_task", tasks == [task.model_dump(mode="json")])
        check(
            "trace_review",
            len(reviews) == 1 and reviews[0]["proposal_digest"] == bundle["approval_digest"],
        )
        check("trace_report", reports == [report.model_dump(mode="json")])
        check("trace_order", [e["seq"] for e in trace] == sorted({e["seq"] for e in trace}))
        check(
            "trace_text",
            data["trace.txt"].decode("utf-8").replace("\r\n", "\n")
            == "\n".join(
                f"{e['seq']:04d} {e['kind']}: {json.dumps(e['payload'], sort_keys=True)}"
                for e in trace
            )
            + "\n",
        )
        audits = [e["payload"] for e in trace if e["kind"] == "browser_execution_audit"]
        check(
            "trace_audit",
            audits
            == [
                {
                    **audit,
                    "browser_execution_passed": task_passed,
                    "cleanup_completed": saved["browser"]["cleanup_completed"],
                }
            ],
        )
        for phase in ("before", "after"):
            captures = [c for c in saved["browser"]["captures"] if c["phase"] == phase]
            check(
                "captures:" + phase,
                [c["issue_id"] for c in captures] == [r.issue_id for r in task.requirements],
            )
            check("captures_complete:" + phase, all(c["captured"] is True for c in captures))
            for i, capture in enumerate(captures, 1):
                if capture["captured"]:
                    check(
                        f"capture_files:{phase}-{i:03d}",
                        {f"{phase}-{i:03d}.png", f"{phase}-{i:03d}.html"} <= files.keys(),
                    )
        result["evidence_passed"] = all(c["passed"] for c in result["checks"])
    except (OSError, ValueError, KeyError, TypeError, AttributeError, RecursionError):
        check("readable_complete_bundle", False)
    return result
