import hashlib
import json
from dataclasses import FrozenInstanceError

import pytest

from veriagent.benchmark_cases import load_corpus
from veriagent.browser_catalog import (
    ALL_TASKS,
    CONTROL_CATALOG,
    CONTROL_MATRICES,
    CONTROL_MATRIX_FLAGS,
    saved_control_matrix,
    select_control_matrix,
)
from veriagent.browser_controls import CHANGED_TARGETS, control_batch_specs
from veriagent.cli import main

# Normalized ordered-batch fingerprints from the pre-refactor committed definitions.
PREVIOUS_BATCHES = {
    "default": "fed07c1ccba5ca852e18e93bb0d011539c168c90063372f82a7b88849c658e98",
    "indexed": "cc30a0836510154b9cf8712ca53da94465d233e41d1cc06ed108581f26fb94a9",
    "multi_event": "a1c45974ebbded9eea3d71263972cef9d7528cfd42070e0a8637a9219676dda4",
    "budget_boundaries": "d359c4c2b61cacb93b078e1f26ebce5b3ef8c88846b14a7dc19ca0698fe70844",
    "fault_budget_boundaries": "f4e58f7f0cc6fca1b28fa677901139f71b88542feed2b51b19f513ddbb5be421",
    "satisfied_budget_boundaries": (
        "3b9352c4c4e47a03f4fff0d22d1ef5e0abb92a52e24acf7c5e5549cdd0d1b295"
    ),
}


@pytest.mark.parametrize("definition", CONTROL_CATALOG, ids=CONTROL_MATRICES)
def test_catalog_preserves_previous_ordered_batches(definition):
    flags = {definition.flag: True} if definition.flag else {}
    specs = control_batch_specs(**flags)
    digest = hashlib.sha256(json.dumps(specs, sort_keys=True).encode()).hexdigest()
    assert digest == PREVIOUS_BATCHES[definition.name]
    assert select_control_matrix(flags) is definition
    assert definition.control_count == sum(
        len(s["tasks"]) * len(s["scenarios"]) * len(s["modes"]) for s in specs
    )


def test_registry_matches_independent_task_corpus_and_expected_counts():
    assert ALL_TASKS == tuple(c.id for c in load_corpus()[0].cases) == tuple(CHANGED_TARGETS)
    assert [m.control_count for m in CONTROL_CATALOG] == [42, 24, 12, 12, 24, 16]
    assert sum(m.control_count for m in CONTROL_CATALOG) == 130
    assert len(set(CONTROL_MATRICES)) == 6 and len(set(CONTROL_MATRIX_FLAGS)) == 5
    for matrix in CONTROL_CATALOG:
        assert matrix.requires_budget_metadata == any(
            b.max_actions != 8 or b.max_decisions != 8 for b in matrix.batches
        )


def test_catalog_and_returned_batch_specs_cannot_mutate_each_other():
    matrix = CONTROL_CATALOG[0]
    with pytest.raises(FrozenInstanceError):
        matrix.name = "changed"
    with pytest.raises(FrozenInstanceError):
        matrix.batches[0].max_actions = 999
    specs = matrix.specs()
    specs[0]["tasks"] = ("changed",)
    assert matrix.specs()[0]["tasks"] == ALL_TASKS


@pytest.mark.parametrize(
    "flags",
    [
        {"unknown": True},
        {"indexed": 1},
        {"multi_event": None},
        {"indexed": True, "multi_event": True},
    ],
)
def test_invalid_or_conflicting_flags_fail_closed(flags):
    with pytest.raises(ValueError):
        select_control_matrix(flags)


def test_legacy_required_flags_and_omitted_later_flags_remain_compatible():
    assert saved_control_matrix({"indexed": False, "multi_event": False}).name == "default"
    assert saved_control_matrix({"indexed": True, "multi_event": False}).name == "indexed"
    with pytest.raises(ValueError):
        saved_control_matrix({"indexed": False})
    with pytest.raises(ValueError):
        saved_control_matrix({"indexed": False, "multi_event": False, "budget_boundaries": "yes"})


@pytest.mark.parametrize("definition", CONTROL_CATALOG, ids=CONTROL_MATRICES)
def test_cli_dispatch_uses_catalog_flags_without_a_provider(
    definition, monkeypatch, capsys, tmp_path
):
    received = []

    def evaluate(output, **flags):
        received.append((output, flags))
        return {"passed": True}

    monkeypatch.setattr("veriagent.browser_controls.evaluate_browser_controls", evaluate)
    monkeypatch.setattr(
        "veriagent.cli.configured_provider", lambda args: pytest.fail("No provider")
    )
    arguments = ["veriagent", "evaluate-browser", "--output", str(tmp_path)]
    if definition.cli_option:
        arguments.append(definition.cli_option)
    monkeypatch.setattr("sys.argv", arguments)
    main()
    assert json.loads(capsys.readouterr().out)["passed"]
    assert received[0][0] == tmp_path
    assert set(received[0][1]) == set(CONTROL_MATRIX_FLAGS)
    assert select_control_matrix(received[0][1]) is definition


def test_cli_help_includes_each_catalog_flag_and_computed_count(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["veriagent", "evaluate-browser", "--help"])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 0
    help_text = " ".join(capsys.readouterr().out.split())
    for matrix in CONTROL_CATALOG:
        if matrix.cli_option:
            assert matrix.cli_option in help_text and matrix.cli_help in help_text
