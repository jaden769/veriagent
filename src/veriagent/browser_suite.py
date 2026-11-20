"""Bounded offline review of distinct saved browser control matrices."""

from pathlib import Path

from veriagent.browser_controls import CONTROL_MATRICES
from veriagent.browser_controls_audit import audit_browser_controls
from veriagent.browser_review import summarize_control_audit


def review_browser_suite(directories: list[Path], *, require_all: bool = False) -> dict:
    if not 1 <= len(directories) <= len(CONTROL_MATRICES):
        raise ValueError("Select one to six saved evaluations")
    paths = [directory.resolve() for directory in directories]
    if len(set(paths)) != len(paths):
        raise ValueError("Select distinct evaluation directories")
    result = {
        "schema_version": 1,
        "evidence_passed": True,
        "selection_passed": True,
        "controls_passed": None,
        "require_all": require_all,
        "coverage_complete": False,
        "present_matrices": [],
        "missing_matrices": [],
        "counts": None,
        "evaluations": [],
        "issues": [],
        "limitations": "Unsigned fixture totals; not independent reliability estimates.",
    }
    matrices, runs = set(), set()
    for index, directory in enumerate(paths, 1):
        audit = audit_browser_controls(directory)
        report = summarize_control_audit(audit)
        matrix = audit.get("matrix") if report["evidence_passed"] else None
        result["evaluations"].append(
            {"directory": str(directory), "matrix": matrix, "review": report}
        )
        if not report["evidence_passed"] or matrix not in CONTROL_MATRICES:
            result["evidence_passed"] = False
            result["issues"].append({"evaluation": index, "issue": "invalid_evaluation_evidence"})
            continue
        if matrix in matrices:
            result["evidence_passed"] = result["selection_passed"] = False
            result["issues"].append({"evaluation": index, "issue": "duplicate_matrix"})
        matrices.add(matrix)
        run_ids = audit.get("run_ids", [])
        valid_run_ids = isinstance(run_ids, list) and all(
            isinstance(run_id, str) for run_id in run_ids
        )
        if (
            not valid_run_ids
            or len(run_ids) != report["counts"]["controls"]
            or len(set(run_ids)) != len(run_ids)
            or runs.intersection(run_ids)
        ):
            result["evidence_passed"] = False
            result["issues"].append({"evaluation": index, "issue": "missing_or_reused_run_ids"})
        if valid_run_ids:
            runs.update(run_ids)
    result["present_matrices"] = [name for name in CONTROL_MATRICES if name in matrices]
    result["missing_matrices"] = [name for name in CONTROL_MATRICES if name not in matrices]
    result["coverage_complete"] = not result["missing_matrices"]
    if require_all and not result["coverage_complete"]:
        result["selection_passed"] = False
        result["issues"].append({"issue": "required_matrices_missing"})
    if result["evidence_passed"] and result["selection_passed"]:
        reports = [row["review"] for row in result["evaluations"]]
        keys = reports[0]["counts"]
        result["counts"] = {key: sum(report["counts"][key] for report in reports) for key in keys}
        result["controls_passed"] = all(report["controls_passed"] for report in reports)
    return result


def render_suite_review(result: dict) -> str:
    lines = [
        "Browser control suite review",
        "Evidence: " + ("valid" if result["evidence_passed"] else "invalid or inconsistent"),
        f"Matrix coverage: {len(result['present_matrices'])}/{len(CONTROL_MATRICES)}",
        "Selection: " + ("accepted" if result["selection_passed"] else "not satisfied"),
    ]
    if result["missing_matrices"]:
        lines.append("Missing matrices: " + ", ".join(result["missing_matrices"]))
    if result["counts"] is None:
        lines.append("Outcome totals withheld because evidence or selection checks failed.")
    else:
        counts = result["counts"]
        lines.extend(
            [
                f"Controls matched: {counts['matched_controls']}/{counts['controls']}",
                f"Successful tasks: {counts['successful_tasks']}",
                f"Expected task failures: {counts['expected_task_failures']}",
                f"Unexpected task failures: {counts['unexpected_task_failures']}",
                f"Expectation mismatches: {counts['expectation_mismatches']}",
            ]
        )
    lines.extend(["", "Evaluations:"])
    for index, row in enumerate(result["evaluations"], 1):
        review = row["review"]
        counts = review["counts"]
        state = (
            f"{counts['matched_controls']}/{counts['controls']} controls matched"
            if counts is not None
            else "evidence invalid; totals withheld"
        )
        lines.extend(
            [
                f"- {index}. {row['matrix'] or 'unverified matrix'}: {state}",
                f"  Evidence: {row['directory']}",
            ]
        )
        for gap in review["evidence_gaps"]:
            lines.append(f"  Gap: {gap['location']}: {gap['check']}")
        if review["gaps_truncated"]:
            lines.append("  Further gaps omitted; use audit-browser-controls for full details.")
    if result["issues"]:
        lines.extend(["", "Suite issues:"])
        for issue in result["issues"]:
            prefix = f"evaluation {issue['evaluation']}: " if "evaluation" in issue else ""
            lines.append("- " + prefix + issue["issue"])
    return "\n".join(lines + ["", result["limitations"]]) + "\n"
