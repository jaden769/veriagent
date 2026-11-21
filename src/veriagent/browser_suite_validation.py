"""Read-only validation of exported reports, without auditing referenced artifacts."""

import json
from pathlib import Path

from pydantic import ValidationError

from veriagent.browser_suite_schema import validate_suite_review

MAX_REPORT_BYTES = 4 * 1024 * 1024
LIMITATIONS = (
    "Checks report structure and internal consistency only. Referenced evaluations are not "
    "opened; evidence, contract identities and task outcomes are not independently verified."
)


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON object key")
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError("Non-finite JSON number")


def validate_suite_review_file(path: Path) -> dict:
    result = {
        "schema_version": 1,
        "validation_passed": False,
        "scope": "exported_report_consistency",
        "report_schema_version": None,
        "errors": [],
        "limitations": LIMITATIONS,
    }
    try:
        with Path(path).open("rb") as source:
            payload = source.read(MAX_REPORT_BYTES + 1)
        if len(payload) > MAX_REPORT_BYTES:
            raise ValueError("Report exceeds 4 MiB limit")
        report = json.loads(
            payload.decode("utf-8-sig"),
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
        validate_suite_review(report)
    except ValidationError as exc:
        result["errors"] = [
            {"location": list(error["loc"]), "type": error["type"]}
            for error in exc.errors(include_input=False, include_context=False)[:20]
        ]
    except (OSError, UnicodeError, ValueError, RecursionError) as exc:
        result["errors"] = [{"location": [], "type": type(exc).__name__}]
    else:
        result["validation_passed"] = True
        result["report_schema_version"] = report["schema_version"]
    return result


def render_suite_validation(result: dict) -> str:
    state = "passed" if result["validation_passed"] else "failed"
    lines = [f"Exported suite report consistency: {state}"]
    for error in result["errors"]:
        location = ".".join(map(str, error["location"])) or "report"
        lines.append(f"- {location}: {error['type']}")
    return "\n".join([*lines, "", result["limitations"], ""])
