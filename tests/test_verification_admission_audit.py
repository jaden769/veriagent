import copy

import pytest
from test_agent_verification_budget import setup_run

from veriagent.models import Mode
from veriagent.verification_admission_audit import reconcile_verification_admission
from veriagent.verification_budget import VerificationLimits


def check(events, run_id):
    return reconcile_verification_admission(events, expected_run_id=run_id)


@pytest.mark.parametrize("engine", ["static", "dynamic"])
@pytest.mark.parametrize("mode", list(Mode))
@pytest.mark.parametrize(
    "limits",
    [VerificationLimits(), VerificationLimits(max_calls=0), VerificationLimits(max_target_rows=1)],
)
def test_actual_agent_traces_replay_to_live_ledger(tmp_path, engine, mode, limits):
    agent, task, _, traces = setup_run(tmp_path, engine, limits=limits, drops=1)
    report = agent.run(task, mode)
    events = traces.events(report.run_id)
    before = copy.deepcopy(events)
    result = check(events, report.run_id)
    assert result["admission_passed"]
    assert result["final_state"] == agent.verifier.ledger.state
    assert events == before


@pytest.mark.parametrize("engine", ["static", "dynamic"])
def test_admitted_error_replay_preserves_unknown_work(tmp_path, monkeypatch, engine):
    agent, task, _, traces = setup_run(tmp_path, engine, limits=VerificationLimits(max_calls=1))

    def fail(task):
        raise RuntimeError("injected")

    monkeypatch.setattr(agent.verifier._verifier, "verify", fail)
    report = agent.run(task)
    result = check(traces.events(report.run_id), report.run_id)
    assert result["final_state"]["verified_target_rows"] is None
    assert result["final_state"]["verification_errors"] == 1


@pytest.mark.parametrize(
    "mutation",
    [
        "counter",
        "bool_counter",
        "float_counter",
        "missing_admit",
        "missing_verification",
        "wrong_rows",
        "new_limit",
        "unknown_phase",
        "extra_field",
        "wrong_report",
        "missing_configuration",
    ],
)
def test_forged_completed_admission_is_rejected(tmp_path, mutation):
    agent, task, _, traces = setup_run(tmp_path, "dynamic", limits=VerificationLimits())
    report = agent.run(task)
    events = traces.events(report.run_id)
    budget = next(e["payload"] for e in events if e["kind"] == "verification_budget")
    if mutation == "counter":
        budget["state"]["reserved_calls"] += 1
    elif mutation == "bool_counter":
        budget["state"]["reserved_calls"] = True
    elif mutation == "float_counter":
        budget["state"]["reserved_calls"] = 1.0
    elif mutation == "missing_admit":
        events.remove(next(e for e in events if e["kind"] == "verification_budget"))
    elif mutation == "missing_verification":
        events.remove(next(e for e in events if e["kind"] == "verification"))
    elif mutation == "wrong_rows":
        budget["requested_target_rows"] = 2
    elif mutation == "new_limit":
        budget["state"]["limits"]["max_calls"] = 9
    elif mutation == "unknown_phase":
        budget["phase"] = "refunded"
    elif mutation == "extra_field":
        budget["refunded"] = True
    elif mutation == "wrong_report":
        events[-1]["payload"]["verified_success"] = False
    else:
        events.remove(next(e for e in events if e["kind"] == "configuration"))
    for seq, event in enumerate(events, 1):
        event["seq"] = seq
    with pytest.raises(ValueError):
        check(events, report.run_id)


@pytest.mark.parametrize(
    "mutation",
    ["admissible_denial", "reason", "missing_outcome", "success_claim", "execution_after_denial"],
)
def test_denial_requires_matching_limits_and_honest_terminal_outcome(tmp_path, mutation):
    agent, task, _, traces = setup_run(tmp_path, "dynamic", limits=VerificationLimits(max_calls=0))
    report = agent.run(task)
    events = traces.events(report.run_id)
    budget = next(e["payload"] for e in events if e["kind"] == "verification_budget")
    if mutation == "admissible_denial":
        next(e for e in events if e["kind"] == "configuration")["payload"]["verification_limits"][
            "max_calls"
        ] = 1
    elif mutation == "reason":
        budget["reason"] = "verification_target_rows_exhausted"
    elif mutation == "missing_outcome":
        events.remove(next(e for e in events if e["kind"] == "verification_denied"))
    elif mutation == "success_claim":
        events[-1]["payload"]["claimed_success"] = True
    else:
        events.insert(-1, {"kind": "model_usage", "payload": {}})
    for seq, event in enumerate(events, 1):
        event["seq"] = seq
    with pytest.raises(ValueError):
        check(events, report.run_id)
