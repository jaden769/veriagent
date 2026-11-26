"""Post-execution local audit and descriptive contrasts for action-cap evidence.

Kept outside the frozen research execution inventory; never runs a policy or provider.
"""

import json
import re
from pathlib import Path

from analysis.run_action_budget import (
    LOCK,
    PLAN,
    bindings,
    budget_for,
    reconcile_condition,
    validate_plan,
)
from research.reflection_evidence import require, same
from research.run_bounded_oracle import digest


def read(path):
    require(path.stat().st_size <= 8 * 1024 * 1024, "Oversized local evidence")
    return json.loads(path.read_text(encoding="utf-8"))


def audit_trial(directory, row, case, plan):
    cap = row["condition"]["max_actions"]
    result = reconcile_condition(directory, row, case, plan, budget_for(plan, cap))
    result["stopping_diagnostics"] = row["stopping_diagnostics"]
    result["budget"] = row["budget"]
    result["faults_configured"] = row["faults_configured"]
    result["additional_resources"] = row["additional_resources"]
    return result


def contrasts(rows):
    by_key = {
        (
            r["condition"]["arm"],
            r["condition"]["task_id"],
            r["condition"]["scenario"],
            r["condition"]["max_actions"],
        ): r
        for r in rows
    }
    output = []
    for key in sorted({k[:3] for k in by_key}):
        for high, low in [(12, 10), (10, 8), (12, 8)]:
            a, b = by_key[*key, high], by_key[*key, low]
            output.append(
                dict(
                    arm=key[0],
                    task_id=key[1],
                    scenario=key[2],
                    contrast=f"{high}_minus_{low}",
                    goal_delta=int(a["ground_truth_success"]) - int(b["ground_truth_success"]),
                    achieved_goal_budget_delta=int(
                        a["stopping_diagnostics"]["achieved_goal_with_budget_failure"]
                    )
                    - int(b["stopping_diagnostics"]["achieved_goal_with_budget_failure"]),
                    claim_delta=int(a["claimed_success"]) - int(b["claimed_success"]),
                )
            )
    return output


def summarize(rows):
    groups = []
    for arm, cap in sorted({(r["condition"]["arm"], r["condition"]["max_actions"]) for r in rows}):
        selected = [
            r for r in rows if r["condition"]["arm"] == arm and r["condition"]["max_actions"] == cap
        ]
        groups.append(
            dict(
                arm=arm,
                max_actions=cap,
                assigned_runs=24,
                completed_runs=len(selected),
                goals_met=sum(r["ground_truth_success"] for r in selected),
                claimed_success=sum(r["claimed_success"] for r in selected),
                false_success=sum(r["false_success"] for r in selected),
                achieved_goal_budget_failures=sum(
                    r["stopping_diagnostics"]["achieved_goal_with_budget_failure"] for r in selected
                ),
                joint_action_decision_caps=sum(
                    r["stopping_diagnostics"]["action_cap_reached"]
                    and r["stopping_diagnostics"]["decision_cap_reached"]
                    for r in selected
                ),
                resources={
                    k: sum(r["resources"][k] for r in selected) for k in selected[0]["resources"]
                },
            )
        )
    return groups


def audit(directory, expected_manifest_sha256):
    directory = Path(directory).resolve()
    require(
        isinstance(expected_manifest_sha256, str)
        and re.fullmatch(r"[0-9a-f]{64}", expected_manifest_sha256),
        "Require external manifest SHA-256",
    )
    require(
        digest(directory / "manifest.json") == expected_manifest_sha256, "Manifest binding mismatch"
    )
    plan = read(directory / "plan.json")
    cases = validate_plan(plan)
    manifest = read(directory / "manifest.json")
    require(
        same(read(directory / "execution-lock.json"), read(LOCK))
        and same(manifest["bindings"], bindings(PLAN))
        and same(read(LOCK), bindings(PLAN)),
        "Execution binding mismatch",
    )
    require(
        manifest["complete"] is True
        and same([manifest["completed_runs"], manifest["planned_runs"]], [288, 288])
        and manifest["active_condition"] is None,
        "Incomplete study",
    )
    runs = manifest["runs"]
    require(
        len(runs) == 288 and same([r["condition"] for r in runs], plan["conditions"]),
        "Assigned coverage mismatch",
    )
    require(len({r["run_id"] for r in runs}) == 288, "Duplicate run identity")
    audited = []
    for index, row in enumerate(runs, 1):
        require(
            row["directory"] == f"trial-{index:03d}"
            and re.fullmatch(r"[0-9a-f]{32}", row["run_id"]),
            "Unsafe trial identity",
        )
        audited.append(
            audit_trial(directory / row["directory"], row, cases[row["condition"]["task_id"]], plan)
        )
    require(manifest["evidence_passed"] is True, "Evidence flag disagreement")
    prior = read(PLAN.parent / "decision-budget-results.json")["conditions"]
    old = {
        (r["condition"]["arm"], r["condition"]["task_id"], r["condition"]["scenario"]): r
        for r in prior
        if r["condition"]["max_decisions"] == 12
    }
    differences = []
    for r in audited:
        c = r["condition"]
        if c["max_actions"] != 8:
            continue
        previous = old[c["arm"], c["task_id"], c["scenario"]]
        keys = ["ground_truth_success", "claimed_success", "false_success", "failure", "resources"]
        changed = [k for k in keys if not same(r[k], previous[k])]
        if changed:
            differences.append(dict(condition=c, changed_fields=changed))
    return dict(
        schema_version=1,
        recorded_on="2026-11-26",
        scope="fixed_mock_action_budget_sensitivity_results",
        consistency_passed=True,
        completed_runs=288,
        execution_bindings=manifest["bindings"],
        manifest_sha256=expected_manifest_sha256,
        raw_directory=str(directory),
        conditions=audited,
        summary=summarize(audited),
        contrasts=contrasts(audited),
        prior_action_eight_differences=differences,
        limitations=(
            "Unsigned local consistency. Fixed mock action-cap sensitivity, not stochastic, "
            "causal, equal-cost or LLM-quality evidence. Prior cells are not pooled; "
            "fault delivery not reenacted."
        ),
    )
