"""Compact review views derived only from re-audited browser control evidence."""

import json
from pathlib import Path

from veriagent.browser_controls_audit import audit_browser_controls


def summarize_control_audit(audit: dict) -> dict:
    report = {
        "schema_version": 1,
        "evidence_passed": audit["evidence_passed"],
        "controls_passed": None,
        "counts": None,
        "expected_task_failures": [],
        "unexpected_task_failures": [],
        "expectation_mismatches": [],
        "evidence_gaps": [],
        "gaps_truncated": False,
        "limitations": "Unsigned deterministic local evidence; not a reliability estimate.",
    }

    def gaps(node, location):
        for check in node.get("checks", []):
            if not check["passed"]:
                if len(report["evidence_gaps"]) < 100:
                    report["evidence_gaps"].append({"location": location, "check": check["check"]})
                else:
                    report["gaps_truncated"] = True
        for batch in node.get("batches", []):
            gaps(batch, batch["directory"])
        for trial in node.get("trials", []):
            gaps(trial, location + "/" + trial["bundle_directory"])

    gaps(audit, "evaluation")
    if not audit["evidence_passed"]:
        # Partial or inconsistent inputs must not produce reassuring aggregate counts.
        return report
    controls = audit["controls"]
    trials = {
        (batch["directory"], trial["bundle_directory"]): trial
        for batch in audit["batches"]
        for trial in batch["trials"]
    }
    keys = [(row["batch_directory"], row["bundle_directory"]) for row in controls]
    if (
        len(keys) != len(trials)
        or len(set(keys)) != len(keys)
        or set(keys) != trials.keys()
        or any(type(trial["task_passed"]) is not bool for trial in trials.values())
    ):
        report["evidence_passed"] = False
        report["evidence_gaps"].append({"location": "evaluation", "check": "report_trial_mapping"})
        return report
    successful = 0
    for row, key in zip(controls, keys, strict=True):
        trial = trials[key]
        detail = {
            k: row[k]
            for k in (
                "task_id",
                "scenario",
                "mode",
                "max_retries",
                "batch_directory",
                "bundle_directory",
            )
        }
        if "max_actions" in row:
            detail.update(max_actions=row["max_actions"], max_decisions=row["max_decisions"])
        if trial["task_passed"]:
            successful += 1
        else:
            category = (
                "unexpected_task_failures"
                if row["expected"]["execution_passed"]
                else "expected_task_failures"
            )
            report[category].append(detail)
        if not row["passed"]:
            report["expectation_mismatches"].append({**detail, "mismatches": row["mismatches"]})
    report["counts"] = {
        "controls": len(controls),
        "matched_controls": sum(row["passed"] for row in controls),
        "successful_tasks": successful,
        "expected_task_failures": len(report["expected_task_failures"]),
        "unexpected_task_failures": len(report["unexpected_task_failures"]),
        "expectation_mismatches": len(report["expectation_mismatches"]),
    }
    report["controls_passed"] = audit["controls_passed"]
    return report


def review_browser_controls(directory: Path) -> dict:
    return summarize_control_audit(audit_browser_controls(directory))


def render_control_review(report: dict) -> str:
    lines = [
        "Browser control evidence review",
        "Evidence: " + ("valid" if report["evidence_passed"] else "invalid or incomplete"),
    ]
    if report["counts"] is None:
        lines.append("Outcome counts withheld because evidence is incomplete or inconsistent.")
    else:
        counts = report["counts"]
        lines.extend(
            [
                f"Controls matched: {counts['matched_controls']}/{counts['controls']}",
                f"Successful tasks: {counts['successful_tasks']}",
                f"Expected task failures: {counts['expected_task_failures']}",
                f"Unexpected task failures: {counts['unexpected_task_failures']}",
                f"Expectation mismatches: {counts['expectation_mismatches']}",
            ]
        )
    for key, title in (
        ("expected_task_failures", "Expected task failures"),
        ("unexpected_task_failures", "Unexpected task failures"),
        ("expectation_mismatches", "Expectation mismatches"),
    ):
        if report[key]:
            lines.extend(["", title + ":"])
            for row in report[key]:
                lines.append(
                    f"- {row['task_id']} / {row['scenario']} / {row['mode']}"
                    f" / retries={row['max_retries']}"
                )
                if "max_actions" in row:
                    lines.append(
                        f"  Limits: actions={row['max_actions']}, decisions={row['max_decisions']}"
                    )
                lines.append(f"  Evidence: {row['batch_directory']}/{row['bundle_directory']}")
                if key == "expectation_mismatches":
                    lines.append("  Differences: " + json.dumps(row["mismatches"], sort_keys=True))
    if report["evidence_gaps"]:
        lines.extend(["", "Evidence gaps:"])
        lines.extend(f"- {gap['location']}: {gap['check']}" for gap in report["evidence_gaps"])
    if report["gaps_truncated"]:
        lines.append(
            "Additional evidence gaps omitted; use audit-browser-controls for full details."
        )
    lines.extend(["", report["limitations"]])
    return "\n".join(lines) + "\n"
