import json
from dataclasses import replace

import pytest
from test_browser_controls_audit import fixture_evaluation
from test_browser_controls_audit import nested_audit as nested_audit

from veriagent.browser_catalog import CONTROL_CATALOG, CONTROL_MATRICES, saved_control_matrix
from veriagent.browser_controls import matrix_contract
from veriagent.browser_controls_audit import audit_browser_controls
from veriagent.browser_review import render_control_review, summarize_control_audit


def write_json(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")


def versioned_evaluation(tmp_path):
    directory = fixture_evaluation(tmp_path / "evaluation")
    path = directory / "controls.json"
    saved = json.loads(path.read_text())
    saved.update(schema_version=2, matrix_contract=matrix_contract(saved_control_matrix(saved)))
    write_json(path, saved)
    return directory


@pytest.mark.parametrize("definition", CONTROL_CATALOG, ids=CONTROL_MATRICES)
def test_contract_identity_is_deterministic_and_excludes_display_text(definition):
    identity = matrix_contract(definition)
    assert identity == matrix_contract(definition)
    assert identity == matrix_contract(replace(definition, description="Display-only change"))
    assert identity["version"] == 1 and identity["matrix"] == definition.name
    assert len(identity["sha256"]) == 64


@pytest.mark.parametrize("change", ["budget", "expectations", "corpus"])
def test_contract_changes_when_declarations_or_expectations_change(change, monkeypatch):
    definition = CONTROL_CATALOG[3]
    original = matrix_contract(definition)
    if change == "budget":
        batch = replace(definition.batches[0], max_actions=3)
        definition = replace(definition, batches=(batch,) + definition.batches[1:])
    elif change == "expectations":
        from veriagent import browser_controls

        expected = browser_controls.expected_control
        monkeypatch.setattr(
            browser_controls,
            "expected_control",
            lambda *args: {**expected(*args), "new_expectation": True},
        )
    else:
        monkeypatch.setattr("veriagent.browser_controls.load_corpus", lambda: (None, "0" * 64))
    assert matrix_contract(definition)["sha256"] != original["sha256"]


def test_new_contract_is_validated_without_rewriting_evidence(tmp_path, nested_audit):
    directory = versioned_evaluation(tmp_path)
    before = {p.relative_to(directory): p.read_bytes() for p in directory.rglob("*") if p.is_file()}
    result = audit_browser_controls(directory)
    assert result["evidence_passed"] and result["matrix_contract"]["status"] == "matched"
    assert before == {
        p.relative_to(directory): p.read_bytes() for p in directory.rglob("*") if p.is_file()
    }


def test_legacy_evaluation_remains_supported_and_labeled(tmp_path, nested_audit):
    directory = fixture_evaluation(tmp_path / "legacy")
    result = audit_browser_controls(directory)
    assert result["evidence_passed"] and result["matrix_contract"]["status"] == "legacy_missing"
    assert "Matrix contract: legacy_missing" in render_control_review(
        summarize_control_audit(result)
    )


@pytest.mark.parametrize(
    "mutation,status",
    [
        ("hash", "mismatch"),
        ("matrix", "mismatch"),
        ("version", "unsupported_version"),
        ("boolean_version", "invalid"),
        ("null", "invalid"),
        ("missing_hash", "invalid"),
    ],
)
def test_invalid_or_mismatched_contract_stops_before_nested_evidence(
    tmp_path, monkeypatch, mutation, status
):
    directory = versioned_evaluation(tmp_path)
    path = directory / "controls.json"
    saved = json.loads(path.read_text())
    if mutation == "hash":
        saved["matrix_contract"]["sha256"] = "f" * 64
    elif mutation == "matrix":
        saved["matrix_contract"]["matrix"] = "default"
    elif mutation == "version":
        saved["matrix_contract"]["version"] = 2
    elif mutation == "boolean_version":
        saved["matrix_contract"]["version"] = True
    elif mutation == "null":
        saved["matrix_contract"] = None
    else:
        del saved["matrix_contract"]["sha256"]
    write_json(path, saved)
    monkeypatch.setattr(
        "veriagent.browser_controls_audit.audit_browser_batch",
        lambda path: pytest.fail("No nested interpretation"),
    )
    audit = audit_browser_controls(directory)
    assert not audit["evidence_passed"] and audit["matrix_contract"]["status"] == status
    assert summarize_control_audit(audit)["counts"] is None


def test_version_two_requires_identity_even_if_nested_artifacts_exist(tmp_path, monkeypatch):
    directory = versioned_evaluation(tmp_path)
    path = directory / "controls.json"
    saved = json.loads(path.read_text())
    del saved["matrix_contract"]
    write_json(path, saved)
    monkeypatch.setattr(
        "veriagent.browser_controls_audit.audit_browser_batch",
        lambda path: pytest.fail("No nested interpretation"),
    )
    result = audit_browser_controls(directory)
    assert not result["evidence_passed"] and result["matrix_contract"]["status"] == "missing"


def test_changed_current_contract_is_explicit_in_review(tmp_path, monkeypatch):
    directory = versioned_evaluation(tmp_path)
    from veriagent import browser_controls

    expected = browser_controls.expected_control
    monkeypatch.setattr(
        browser_controls,
        "expected_control",
        lambda *args: {**expected(*args), "new_expectation": True},
    )
    monkeypatch.setattr(
        "veriagent.browser_controls_audit.audit_browser_batch",
        lambda path: pytest.fail("No nested interpretation"),
    )
    report = summarize_control_audit(audit_browser_controls(directory))
    assert report["matrix_contract"]["status"] == "mismatch" and report["counts"] is None
    assert "Matrix contract: mismatch" in render_control_review(report)
