"""Credential-free demonstration and local sandbox runner."""

import argparse
import json
from pathlib import Path

from veriagent.agent import Agent
from veriagent.evaluation import compare
from veriagent.executor import Executor
from veriagent.models import Budget, Mode
from veriagent.planner import MockProvider
from veriagent.sandbox import Faults, Sandbox
from veriagent.trace import TraceStore
from veriagent.verification import StateVerifier


def main() -> None:
    parser = argparse.ArgumentParser(prog="veriagent")
    commands = parser.add_subparsers(dest="command", required=True)
    demo = commands.add_parser("demo", help="Compare three modes using fresh paired sandboxes")
    demo.add_argument("--output", type=Path, default=Path("artifacts"))
    demo.add_argument(
        "--scenario",
        choices=("clean", "silent_drop", "persistent_drop", "transient"),
        default="silent_drop",
    )
    run = commands.add_parser("run", help="Run a constrained natural-language objective")
    run.add_argument("objective")
    run.add_argument("--mode", choices=[m.value for m in Mode], default="recover")
    run.add_argument("--db", type=Path, default=Path("artifacts/sandbox.sqlite"))
    run.add_argument("--traces", type=Path, default=Path("artifacts/traces.sqlite"))
    run.add_argument("--silent-drops", type=int, default=0)
    run.add_argument("--max-retries", type=int, default=2)
    serve = commands.add_parser("serve", help="Serve a local sandbox on 127.0.0.1")
    serve.add_argument("--db", type=Path, default=Path("artifacts/sandbox.sqlite"))
    serve.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    if args.command == "demo":
        result = compare(args.output, args.scenario)
        print("mode       claim  audit  false-success  actions  retries")
        for row in result["runs"]:
            print(
                f"{row['mode']:10} {str(row['claimed_success']):6} "
                f"{str(row['ground_truth_success']):6} {str(row['false_success']):14} "
                f"{row['actions']:7} {row['recovery_attempts']:8}"
            )
        print(f"Evidence and traces: {result['directory']}")
        return
    if args.command == "serve":
        import uvicorn

        from veriagent.api import create_app

        sandbox = Sandbox(args.db)
        sandbox.seed()
        uvicorn.run(create_app(sandbox), host="127.0.0.1", port=args.port)
        return
    try:
        provider = MockProvider()
        task = provider.parse(args.objective)
        budget = Budget(max_retries=args.max_retries)
        faults = Faults(silent_drops=args.silent_drops)
        if args.db.resolve() == args.traces.resolve():
            raise ValueError("State and trace databases must use separate paths")
    except ValueError as exc:
        parser.error(str(exc))
    sandbox = Sandbox(args.db, faults)
    sandbox.seed()
    traces = TraceStore(args.traces)
    report = Agent(provider, Executor(sandbox), StateVerifier(sandbox.path), traces, budget).run(
        task, Mode(args.mode)
    )
    print(json.dumps(report.model_dump(mode="json"), indent=2))
    if not report.claimed_success:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
