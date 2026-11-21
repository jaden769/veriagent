import json
import sys

import pytest
from test_browser_suite import evaluation, mock_evaluations

from veriagent.browser_suite import review_browser_suite
from veriagent.browser_suite_validation import MAX_REPORT_BYTES, validate_suite_review_file
from veriagent.cli import main


@pytest.fixture
def exported(tmp_path, monkeypatch):
    paths = mock_evaluations(monkeypatch, tmp_path, [evaluation("default", "one")])
    report = review_browser_suite(paths)
    path = tmp_path / "report.json"
    path.write_text(json.dumps(report), encoding="utf-8")
    return path, report


def test_validator_reads_only_export_and_preserves_bytes(exported, monkeypatch):
    path, _ = exported
    before = path.read_bytes()

    def forbidden(*args, **kwargs):
        pytest.fail("Validation must not reopen evaluations or construct providers")

    monkeypatch.setattr("veriagent.browser_suite.audit_browser_controls", forbidden)
    monkeypatch.setattr("veriagent.cli.configured_provider", forbidden)
    assert validate_suite_review_file(path)["validation_passed"]
    assert path.read_bytes() == before
    assert sorted(p.name for p in path.parent.iterdir()) == ["report.json"]


def test_valid_rejected_selection_is_a_consistent_report(tmp_path, monkeypatch):
    paths = mock_evaluations(monkeypatch, tmp_path, [evaluation("default", "one")])
    report = review_browser_suite(paths, require_all=True)
    assert not report["selection_passed"] and report["counts"] is None
    path = tmp_path / "rejected.json"
    path.write_text(json.dumps(report), encoding="utf-8-sig")
    assert validate_suite_review_file(path)["validation_passed"]


@pytest.mark.parametrize(
    "payload",
    [b"{", b"[]", b"null", b"\xff", b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":Infinity}'],
)
def test_bad_json_and_non_report_values_fail(tmp_path, payload):
    path = tmp_path / "bad.json"
    path.write_bytes(payload)
    result = validate_suite_review_file(path)
    assert not result["validation_passed"] and result["errors"]
    assert result["report_schema_version"] is None


def test_size_limit_and_missing_input(tmp_path):
    path = tmp_path / "large.json"
    path.write_bytes(b" " * (MAX_REPORT_BYTES + 1))
    assert not validate_suite_review_file(path)["validation_passed"]
    assert not validate_suite_review_file(tmp_path / "missing.json")["validation_passed"]
    assert not validate_suite_review_file(tmp_path)["validation_passed"]


def test_counter_drift_fails_without_echoing_input(exported):
    path, report = exported
    report["counts"]["controls"] = "private-input-marker"
    path.write_text(json.dumps(report), encoding="utf-8")
    result = validate_suite_review_file(path)
    assert not result["validation_passed"]
    assert "private-input-marker" not in json.dumps(result)
    assert result["errors"][0]["location"] == ["counts", "controls"]


@pytest.mark.parametrize("output_format", ["text", "json"])
@pytest.mark.parametrize("valid", [True, False])
def test_cli_status_and_scope(exported, monkeypatch, capsys, output_format, valid):
    path, report = exported
    if not valid:
        report["schema_version"] = 1
        path.write_text(json.dumps(report), encoding="utf-8")
    monkeypatch.setattr(
        sys, "argv", ["veriagent", "validate-browser-suite", str(path), "--format", output_format]
    )
    if valid:
        main()
    else:
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 1
    output = capsys.readouterr().out
    assert "not independently verified" in output
    if output_format == "json":
        assert json.loads(output)["validation_passed"] is valid
    else:
        assert ("consistency: passed" if valid else "consistency: failed") in output
