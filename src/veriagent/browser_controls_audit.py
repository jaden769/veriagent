"""Offline reconciliation of fixed browser control evaluations and nested evidence."""

import hashlib
import json
import re
from pathlib import Path

from veriagent.browser_batch_audit import audit_browser_batch
from veriagent.browser_catalog import saved_control_matrix
from veriagent.browser_controls import (
    compare_control,
    control_budget,
    control_key,
    matrix_contract,
)
from veriagent.browser_evidence import _read


def audit_browser_controls(directory: Path) -> dict:
    result = {
        "schema_version": 1,
        "evidence_passed": False,
        "controls_passed": None,
        "matrix": None,
        "matrix_contract": {"status": "not_checked", "saved": None, "current": None},
        "checks": [],
        "batches": [],
        "limitations": "Unsigned evidence reconciliation against current control definitions.",
    }

    def check(name, passed):
        result["checks"].append({"check": name, "passed": bool(passed)})

    try:
        saved = json.loads(_read(directory, "controls.json"))
        if type(saved["schema_version"]) is not int or saved["schema_version"] not in {1, 2}:
            raise ValueError("Unsupported evaluation schema")
        if any(type(saved[key]) is not bool for key in ("passed", "coverage_complete")):
            raise ValueError("Invalid matrix flags")
        definition = saved_control_matrix(saved)
        specs = definition.specs()
        result["matrix"] = definition.name
        current = matrix_contract(definition)
        identity = saved.get("matrix_contract")
        contract = result["matrix_contract"]
        contract["current"] = current
        if "matrix_contract" not in saved:
            contract["status"] = "legacy_missing" if saved["schema_version"] == 1 else "missing"
        elif (
            not isinstance(identity, dict)
            or set(identity) != {"version", "matrix", "sha256"}
            or type(identity["version"]) is not int
            or not 1 <= identity["version"] <= 99
            or not isinstance(identity["matrix"], str)
            or len(identity["matrix"]) > 80
            or not isinstance(identity["sha256"], str)
            or not re.fullmatch(r"[0-9a-f]{64}", identity["sha256"])
        ):
            contract["status"] = "invalid"
        else:
            contract["saved"] = identity
            contract["status"] = (
                "unsupported_version"
                if identity["version"] != 1
                else "matched"
                if identity == current
                else "mismatch"
            )
        if contract["status"] not in {"matched", "legacy_missing"}:
            check("matrix_contract", False)
            return result  # Do not interpret nested evidence under a different contract.
        check("matrix_contract", True)
        bindings = saved["batch_bindings"]
        if not isinstance(bindings, list) or len(bindings) != len(specs):
            raise ValueError("Incomplete batch bindings")
        check("completed_evaluation", saved["status"] == "complete")
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
                and manifest["budget"] == control_budget(spec).model_dump(mode="json")
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
            if definition.requires_budget_metadata:
                valid_metadata = all(
                    row.get("max_actions") == spec["max_actions"]
                    and row.get("max_decisions") == spec["max_decisions"]
                    and "decisions" in row
                    and "failure" in row
                    for row in manifest["trials"]
                )
                check(f"budget_control_metadata:{ordinal}", valid_metadata)
                if not valid_metadata:
                    raise ValueError("Missing budget-control metadata")
            for row in manifest["trials"]:
                # The nested auditor already validated this relative bundle path.
                bundle = json.loads(_read(path / row["bundle_directory"], "result.json"))
                run_id = bundle["result"]["run_id"]
                check(f"unique_control_run:{len(controls) + 1}", run_id not in run_ids)
                run_ids.add(run_id)
                controls.append({**compare_control(row), "batch_directory": relative})
        required = {
            (
                task,
                scenario,
                mode,
                spec["max_retries"],
                spec.get("max_actions", 8),
                spec.get("max_decisions", 8),
            )
            for spec in specs
            for task in spec["tasks"]
            for scenario in spec["scenarios"]
            for mode in spec["modes"]
        }
        observed = {control_key(row) for row in controls}
        coverage = required == observed and len(controls) == len(required)
        check("control_coverage", coverage and saved["coverage_complete"] == coverage)
        check("control_results", saved["controls"] == controls)
        passed = coverage and all(row["passed"] for row in controls)
        result["controls_passed"] = passed
        check("reported_outcome", saved["passed"] == passed)
        result["controls"] = controls
        result["run_ids"] = sorted(run_ids)
        result["evidence_passed"] = all(c["passed"] for c in result["checks"])
    except (OSError, ValueError, KeyError, TypeError, AttributeError, RecursionError):
        check("readable_complete_evaluation", False)
    return result
