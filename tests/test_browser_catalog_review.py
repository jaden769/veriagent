import json

import pytest

from veriagent.browser_catalog import CONTROL_CATALOG, CONTROL_MATRICES
from veriagent.browser_catalog_review import inspect_browser_matrices, render_matrix_inspection
from veriagent.browser_controls import matrix_contract
from veriagent.cli import main


def test_full_inspection_matches_installed_catalog_and_contracts():
    result = inspect_browser_matrices()
    assert result["selected_matrices"] == list(CONTROL_MATRICES)
    assert result["installed_matrix_count"] == 6 and result["control_count"] == 130
    for row, definition in zip(result["matrices"], CONTROL_CATALOG, strict=True):
        assert row["matrix_contract"] == matrix_contract(definition)
        assert row["control_count"] == definition.control_count
        assert row["cli_option"] == definition.cli_option
        assert len(row["batches"]) == row["batch_count"]
    assert "Selected: 6/6 matrices; 130 controls" in render_matrix_inspection(result)


def test_selection_order_and_budgets_are_visible_without_artifact_paths():
    result = inspect_browser_matrices(("satisfied_budget_boundaries", "default"))
    assert result["selected_matrices"] == ["satisfied_budget_boundaries", "default"]
    assert result["control_count"] == 58
    assert result["matrices"][0]["batches"][0]["budget"]["max_actions"] == 1
    assert "artifacts" not in json.dumps(result)


@pytest.mark.parametrize("names", [(), ("default", "default"), ("unknown",)])
def test_invalid_selection_is_rejected_before_fingerprinting(monkeypatch, names):
    monkeypatch.setattr(
        "veriagent.browser_catalog_review.matrix_contract",
        lambda definition: pytest.fail("No identity calculation"),
    )
    with pytest.raises(ValueError):
        inspect_browser_matrices(names)


@pytest.mark.parametrize("output_format", ["text", "json"])
def test_cli_is_read_only_and_never_constructs_provider_or_evaluation(
    tmp_path, monkeypatch, capsys, output_format
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "veriagent.cli.configured_provider", lambda args: pytest.fail("No provider")
    )
    monkeypatch.setattr(
        "veriagent.browser_controls.evaluate_browser_controls",
        lambda *args, **kwargs: pytest.fail("No evaluation"),
    )
    monkeypatch.setattr(
        "sys.argv",
        ["veriagent", "inspect-browser-matrices", "--matrix", "indexed", "--format", output_format],
    )
    main()
    output = capsys.readouterr().out
    if output_format == "json":
        result = json.loads(output)
        assert result["selected_matrices"] == ["indexed"]
        assert result["matrices"][0]["matrix_contract"]["matrix"] == "indexed"
    else:
        assert "Selected: 1/6 matrices; 24 controls" in output and "Contract v1:" in output
        assert "1 batch (--indexed)" in output
    assert list(tmp_path.iterdir()) == []


def test_duplicate_cli_selection_returns_argument_error(monkeypatch, capsys):
    monkeypatch.setattr(
        "sys.argv",
        ["veriagent", "inspect-browser-matrices", "--matrix", "default", "--matrix", "default"],
    )
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2
    assert "unique installed" in capsys.readouterr().err
