"""Offline reconciliation of fixed browser control evaluations and nested evidence."""

import hashlib
import json
import re
from pathlib import Path

from veriagent.browser_batch_audit import audit_browser_batch
from veriagent.browser_controls import compare_control, control_batch_specs
from veriagent.browser_evidence import _read
from veriagent.models import Budget


def audit_browser_controls(directory: Path) -> dict:
    result = {
        "schema_version": 1,
        "evidence_passed": False,
        "controls_passed": None,
        "checks": [],
        "batches": [],
        "limitations": "Unsigned evidence reconciliation against current control definitions.",
    }

    def check(name, passed):
        result["checks"].append({"check": name, "passed": bool(passed)})

    try:
        saved = json.loads(_read(directory, "controls.json"))
        if any(
            type(saved[k]) is not bool
            for k in ("indexed", "multi_event", "passed", "coverage_complete")
        ):
            raise ValueError("Invalid matrix flags")
        specs = control_batch_specs(indexed=saved["indexed"], multi_event=saved["multi_event"])
        bindings = saved["batch_bindings"]
        if not isinstance(bindings, list) or len(bindings) != len(specs):
            raise ValueError("Incomplete batch bindings")
        check(
            "completed_evaluation", saved["schema_version"] == 1 and saved["status"] == "complete"
        )
        check("offline_engine", saved["provider"] == "mock" and saved["engine"] == "dynamic")
        controls = []
        run_ids = set()
        seen = set()
        for ordinal, (binding, spec) in enumerate(zip(bindings, specs, strict=True), 1):
            relative = binding["directory"]
            if (
                not isinstance(relative, str)
                or not re.fullmatch(r"[0-9a-f]{32}", relative)
                or relative in seen
            ):
                raise ValueError("Invalid batch directory")
            seen.add(relative)
            path = directory / relative
            if not path.resolve().is_relative_to(directory.resolve()):
                raise ValueError("Batch escapes evaluation")
            raw = _read(path, "manifest.json")
            check(
                f"manifest_binding:{ordinal}",
                hashlib.sha256(raw).hexdigest() == binding["manifest_sha256"],
            )
            manifest = json.loads(raw)
            check(
                f"batch_configuration:{ordinal}",
                manifest["configuration"]
                == {
                    "tasks": list(spec["tasks"]),
                    "scenarios": list(spec["scenarios"]),
                    "modes": list(spec["modes"]),
                    "repeats": 1,
                }
                and manifest["budget"]
                == Budget(
                    max_actions=8,
                    max_decisions=8,
                    timeout_seconds=30,
                    action_timeout_seconds=1,
                    max_retries=spec["max_retries"],
                ).model_dump(mode="json")
                and manifest["engine"] == "dynamic",
            )
            # Reject wrong selection before reading an unexpected nested matrix.
            if not result["checks"][-1]["passed"]:
                raise ValueError("Wrong nested matrix")
            batch_audit = audit_browser_batch(path)
            result["batches"].append({"directory": relative, **batch_audit})
            check(f"batch_evidence:{ordinal}", batch_audit["evidence_passed"])
            if not batch_audit["evidence_passed"]:
                raise ValueError("Invalid nested evidence")
            for row in manifest["trials"]:
                # The nested auditor already validated this relative bundle path.
                bundle = json.loads(_read(path / row["bundle_directory"], "result.json"))
                run_id = bundle["result"]["run_id"]
                check(f"unique_control_run:{len(controls) + 1}", run_id not in run_ids)
                run_ids.add(run_id)
                controls.append({**compare_control(row), "batch_directory": relative})
        required = {
            (task, scenario, mode, spec["max_retries"])
            for spec in specs
            for task in spec["tasks"]
            for scenario in spec["scenarios"]
            for mode in spec["modes"]
        }
        observed = {(r["task_id"], r["scenario"], r["mode"], r["max_retries"]) for r in controls}
        coverage = required == observed and len(controls) == len(required)
        check("control_coverage", coverage and saved["coverage_complete"] == coverage)
        check("control_results", saved["controls"] == controls)
        passed = coverage and all(row["passed"] for row in controls)
        result["controls_passed"] = passed
        check("reported_outcome", saved["passed"] == passed)
        result["controls"] = controls
        result["evidence_passed"] = all(c["passed"] for c in result["checks"])
    except (OSError, ValueError, KeyError, TypeError, AttributeError, RecursionError):
        check("readable_complete_evaluation", False)
    return result
