"""Credential-free demonstration and local sandbox runner."""

import argparse
import json
import os
from pathlib import Path

from veriagent.agent import Agent
from veriagent.benchmark import SCENARIOS, repeated_trials
from veriagent.benchmark_cases import load_corpus, select_cases
from veriagent.benchmark_faults import ALL_SCENARIOS
from veriagent.browser_faults import (
    ALL_BROWSER_SCENARIOS,
    BROWSER_SCENARIOS,
    validate_browser_deadline,
)
from veriagent.dynamic import DynamicAgent
from veriagent.evaluation import compare
from veriagent.interpretation import approved_task, load_proposal, proposal_digest, propose_task
from veriagent.isolated import sandbox_executor
from veriagent.models import Budget, Mode, ModelLimits, ToolExecutionConfig
from veriagent.openai_provider import OpenAIConfig, OpenAIProvider, ProviderError
from veriagent.planner import MockProvider
from veriagent.safety_evaluation import evaluate_safety, load_suite
from veriagent.sandbox import Faults, Sandbox
from veriagent.smoke import smoke_test
from veriagent.trace import TraceStore
from veriagent.verification import StateVerifier


def add_provider_options(command: argparse.ArgumentParser, *, timeout: float) -> None:
    command.add_argument("--provider", choices=("mock", "openai"), default="mock")
    command.add_argument("--model", help="OpenAI model ID; defaults to OPENAI_MODEL")
    command.add_argument(
        "--timeout", type=float, default=timeout, help="Cooperative run deadline in seconds"
    )
    command.add_argument("--model-timeout", type=float, default=15)
    command.add_argument("--max-output-tokens", type=int, default=2048)
    command.add_argument(
        "--input-price", type=float, help="Caller-supplied USD per million input tokens"
    )
    command.add_argument(
        "--output-price", type=float, help="Caller-supplied USD per million output tokens"
    )
    command.add_argument(
        "--max-model-tokens", type=int, help="Observed total-token threshold per run"
    )
    command.add_argument(
        "--max-model-output-tokens", type=int, help="Cumulative output-token allowance"
    )
    command.add_argument(
        "--max-model-cost", type=float, help="Observed USD threshold; requires prices"
    )


def configured_provider(args: argparse.Namespace) -> MockProvider | OpenAIProvider:
    if args.provider == "mock":
        if any(
            value is not None
            for value in (args.max_model_tokens, args.max_model_output_tokens, args.max_model_cost)
        ):
            raise ValueError("Model usage limits require --provider openai")
        if any(value is not None for value in (args.model, args.input_price, args.output_price)):
            raise ValueError("--model and token prices require --provider openai")
        return MockProvider()
    model = args.model or os.environ.get("OPENAI_MODEL", "").strip()
    if not model:
        raise ProviderError("Specify --model or set OPENAI_MODEL")
    config = OpenAIConfig(
        model=model,
        request_timeout_seconds=args.model_timeout,
        max_output_tokens=args.max_output_tokens,
        input_usd_per_million=args.input_price,
        output_usd_per_million=args.output_price,
        limits=ModelLimits(
            max_total_tokens=args.max_model_tokens,
            max_output_tokens=args.max_model_output_tokens,
            max_cost_usd=args.max_model_cost,
        ),
    )
    return OpenAIProvider.from_env(config)


def add_engine_options(
    command: argparse.ArgumentParser, *, action_timeout: float | None = 1
) -> None:
    command.add_argument("--engine", choices=("static", "dynamic"), default="static")
    command.add_argument("--max-actions", type=int, default=20)
    command.add_argument(
        "--action-timeout",
        type=float,
        default=action_timeout,
        help="Tool deadline including worker startup when isolated",
    )
    command.add_argument(
        "--isolate-tools", action="store_true", help="Use one worker per tool action"
    )
    command.add_argument(
        "--hang-before-commit",
        type=int,
        default=0,
        help="Inject worker hangs before this many writes (isolated tools only)",
    )
    command.add_argument(
        "--hang-after-commit",
        type=int,
        default=0,
        help="Inject worker hangs after this many writes (isolated tools only)",
    )
    command.add_argument(
        "--max-decisions",
        type=int,
        default=20,
        help="Dynamic decision limit; each OpenAI decision can be billable",
    )


def main() -> None:
    parser = argparse.ArgumentParser(prog="veriagent")
    commands = parser.add_subparsers(dest="command", required=True)
    benchmark = commands.add_parser(
        "benchmark", help="Run bounded repeated trials with independent audits"
    )
    benchmark.add_argument("--output", type=Path, default=Path("artifacts/benchmarks"))
    benchmark.add_argument("--repeats", type=int, default=3)
    benchmark.add_argument("--scenario", action="append", choices=ALL_SCENARIOS)
    tasks = benchmark.add_mutually_exclusive_group()
    tasks.add_argument("--task", action="append", help="Fixed task ID; repeat to select several")
    tasks.add_argument("--all-tasks", action="store_true", help="Select all six fixed task cases")
    benchmark.add_argument("--engine", choices=("static", "dynamic"), default="static")
    benchmark.add_argument("--max-actions", type=int, default=8)
    benchmark.add_argument("--max-decisions", type=int, default=8)
    add_provider_options(benchmark, timeout=60)
    demo = commands.add_parser("demo", help="Compare three modes using fresh paired sandboxes")
    demo.add_argument("--output", type=Path, default=Path("artifacts"))
    demo.add_argument("--engine", choices=("static", "dynamic"), default="static")
    safety = commands.add_parser(
        "evaluate-safety", help="Run scripted offline boundary cases; no LLM calls"
    )
    safety.add_argument("--output", type=Path, default=Path("artifacts/safety"))
    safety.add_argument("--suite", type=Path, help="Optional bounded JSON fixture suite")
    safety.add_argument(
        "--case", action="append", default=[], help="Select a case ID; repeat to select several"
    )
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
    add_provider_options(run, timeout=10)
    add_engine_options(run)
    propose = commands.add_parser("propose", help="Interpret an objective without executing tools")
    propose.add_argument("objective")
    propose.add_argument("--output", type=Path, default=Path("artifacts/proposals"))
    add_provider_options(propose, timeout=60)
    review = commands.add_parser("review", help="Display a proposal and its approval digest")
    review.add_argument("proposal", type=Path)
    execute = commands.add_parser("execute", help="Execute the exact proposal you reviewed")
    execute.add_argument("proposal", type=Path)
    execute.add_argument("--approve", required=True, help="Digest printed by review")
    execute.add_argument("--mode", choices=[m.value for m in Mode], default="recover")
    execute.add_argument("--db", type=Path, default=Path("artifacts/sandbox.sqlite"))
    execute.add_argument("--traces", type=Path, default=Path("artifacts/traces.sqlite"))
    execute.add_argument("--silent-drops", type=int, default=0)
    execute.add_argument("--max-retries", type=int, default=2)
    add_provider_options(execute, timeout=60)
    add_engine_options(execute, action_timeout=None)
    execute.add_argument("--tool-backend", choices=("sandbox", "browser"), default="sandbox")
    execute.add_argument("--browser-scenario", choices=BROWSER_SCENARIOS, default="clean")
    execute.add_argument(
        "--browser-artifacts", type=Path, default=Path("artifacts/browser-executions")
    )
    smoke = commands.add_parser("smoke", help="Save an isolated dropped-write recovery check")
    smoke.add_argument("--output", type=Path, default=Path("artifacts/smoke"))
    add_provider_options(smoke, timeout=60)
    add_engine_options(smoke)
    browser = commands.add_parser(
        "browser-smoke", help="Run the local headless browser recovery check"
    )
    browser.add_argument("--output", type=Path, default=Path("artifacts/browser-smoke"))
    browser.add_argument("--engine", choices=("static", "dynamic"), default="static")
    browser.add_argument("--max-actions", type=int, default=8)
    browser.add_argument("--max-decisions", type=int, default=8)
    browser.add_argument("--action-timeout", type=float, default=5)
    browser.add_argument("--browser-scenario", choices=BROWSER_SCENARIOS, default="silent_drop")
    add_provider_options(browser, timeout=60)
    check = commands.add_parser(
        "check-provider", help="Check OpenAI model metadata without generation"
    )
    check.add_argument("--model", help="OpenAI model ID; defaults to OPENAI_MODEL")
    check.add_argument("--timeout", type=float, default=15)
    serve = commands.add_parser("serve", help="Serve a local sandbox on 127.0.0.1")
    serve.add_argument("--db", type=Path, default=Path("artifacts/sandbox.sqlite"))
    serve.add_argument("--port", type=int, default=8000)
    batch = commands.add_parser("browser-batch", help="Run bounded offline browser corpus trials")
    batch.add_argument("--output", type=Path, default=Path("artifacts/browser-batches"))
    batch.add_argument("--task", action="append")
    batch.add_argument("--scenario", action="append", choices=ALL_BROWSER_SCENARIOS)
    batch.add_argument("--mode", action="append", choices=[m.value for m in Mode])
    batch.add_argument("--engine", choices=("static", "dynamic"), default="dynamic")
    batch.add_argument("--repeats", type=int, default=1)
    controls = commands.add_parser(
        "evaluate-browser", help="Check 42 fixed offline dynamic browser controls"
    )
    controls.add_argument("--output", type=Path, default=Path("artifacts/browser-controls"))
    matrix = controls.add_mutually_exclusive_group()
    matrix.add_argument("--indexed", action="store_true", help="Check 24 later-write controls")
    matrix.add_argument(
        "--multi-event", action="store_true", help="Check 12 retry-exhaustion controls"
    )
    audit_browser = commands.add_parser(
        "audit-browser", help="Re-audit a saved browser trial offline"
    )
    audit_browser.add_argument("directory", type=Path)
    audit_batch = commands.add_parser(
        "audit-browser-batch", help="Reconcile saved browser batch evidence offline"
    )
    audit_batch.add_argument("directory", type=Path)
    args = parser.parse_args()
    if args.command == "audit-browser-batch":
        from veriagent.browser_batch_audit import audit_browser_batch

        result = audit_browser_batch(args.directory)
        print(json.dumps(result, indent=2))
        if not result["evidence_passed"]:
            raise SystemExit(1)
        return
    if args.command == "audit-browser":
        from veriagent.browser_evidence import audit_browser_evidence

        result = audit_browser_evidence(args.directory)
        print(json.dumps(result, indent=2))
        if not result["evidence_passed"]:
            raise SystemExit(1)
        return
    if args.command == "evaluate-browser":
        from veriagent.browser import BrowserSetupError
        from veriagent.browser_controls import evaluate_browser_controls

        try:
            result = evaluate_browser_controls(
                args.output, indexed=args.indexed, multi_event=args.multi_event
            )
        except BrowserSetupError as exc:
            parser.error(str(exc))
        print(json.dumps(result, indent=2))
        if not result["passed"]:
            raise SystemExit(1)
        return
    if args.command == "browser-batch":
        from veriagent.browser import BrowserSetupError
        from veriagent.browser_batch import browser_batch

        try:
            result = browser_batch(
                args.output,
                task_ids=tuple(args.task or ("single_done",)),
                scenarios=tuple(args.scenario or ("clean", "silent_drop")),
                modes=tuple(args.mode or ("recover",)),
                repeats=args.repeats,
                engine=args.engine,
            )
        except (ValueError, BrowserSetupError) as exc:
            parser.error(str(exc))
        print(json.dumps(result, indent=2))
        return
    if args.command == "benchmark":
        try:
            scenarios = tuple(args.scenario) if args.scenario else SCENARIOS
            task_ids = (
                tuple(case.id for case in load_corpus()[0].cases)
                if args.all_tasks
                else tuple(args.task or ("single_done",))
            )
            cases, _ = select_cases(task_ids)
            if (
                not 1 <= args.repeats <= 20
                or args.repeats * len(scenarios) * len(cases) * len(Mode) > 120
            ):
                raise ValueError("Select 1 to 20 repeats and at most 120 total runs")
            if len(set(scenarios)) != len(scenarios):
                raise ValueError("Select unique scenarios")
            if args.provider == "openai" and args.max_model_output_tokens is None:
                raise ValueError("Live benchmarks require --max-model-output-tokens (per run)")
            budget = Budget(
                max_actions=args.max_actions,
                max_decisions=args.max_decisions,
                timeout_seconds=args.timeout,
            )
            # Validate configuration before creating artifact directories or starting trials.
            provider = configured_provider(args)
            if isinstance(provider, OpenAIProvider):
                provider.close()
            result = repeated_trials(
                args.output,
                repeats=args.repeats,
                scenarios=scenarios,
                task_ids=task_ids,
                engine=args.engine,
                budget=budget,
                provider_factory=lambda: configured_provider(args),
                provider_name=args.provider,
            )
        except (ValueError, ProviderError, OSError) as exc:
            parser.error(str(exc))
        print(
            json.dumps(
                {
                    key: result[key]
                    for key in (
                        "directory",
                        "complete",
                        "planned_runs",
                        "completed_runs",
                        "summary",
                    )
                },
                indent=2,
            )
        )
        if not result["complete"]:
            raise SystemExit(1)
        return
    if args.command == "check-provider":
        try:
            model = args.model or os.environ.get("OPENAI_MODEL", "").strip()
            if not model:
                raise ValueError("Specify --model or set OPENAI_MODEL")
            provider = OpenAIProvider.from_env(
                OpenAIConfig(model=model, request_timeout_seconds=args.timeout)
            )
        except (ValueError, ProviderError) as exc:
            parser.error(str(exc))
        try:
            result = provider.check_model()
        finally:
            provider.close()
        print(json.dumps(result, indent=2))
        if not result["ok"]:
            raise SystemExit(1)
        return
    if args.command == "evaluate-safety":
        try:
            result = evaluate_safety(args.output, load_suite(args.suite), case_ids=tuple(args.case))
        except (ValueError, OSError) as exc:
            parser.error(str(exc))
        print(
            json.dumps(
                {
                    "passed": result["passed"],
                    "directory": result["directory"],
                    "suite_sha256": result["suite_sha256"],
                    "summary": result["summary"],
                },
                indent=2,
            )
        )
        if not result["passed"]:
            raise SystemExit(1)
        return
    if args.command == "review":
        try:
            proposal = load_proposal(args.proposal)
        except (ValueError, OSError) as exc:
            parser.error(str(exc))
        print(
            json.dumps(
                {
                    **proposal.model_dump(mode="json"),
                    "approval_digest": proposal_digest(proposal)
                    if proposal.interpretation.clarification is None
                    else None,
                },
                indent=2,
            )
        )
        if proposal.interpretation.clarification is not None:
            raise SystemExit(1)
        return
    if args.command == "propose":
        try:
            if not 1 <= len(args.objective) <= 2000:
                raise ValueError("Objective must contain 1 to 2000 characters")
            budget = Budget(timeout_seconds=args.timeout)
            provider = configured_provider(args)
        except (ValueError, ProviderError) as exc:
            parser.error(str(exc))
        try:
            result = propose_task(
                args.objective, provider, args.output, timeout=budget.timeout_seconds
            )
        finally:
            if isinstance(provider, OpenAIProvider):
                provider.close()
        print(json.dumps(result, indent=2))
        if result["error"] is not None:
            raise SystemExit(1)
        return
    if args.command == "demo":
        result = compare(args.output, args.scenario, engine=args.engine)
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
    if args.command in {"smoke", "browser-smoke"}:
        from veriagent.browser import BrowserSetupError

        try:
            tool_config = (
                None
                if args.command == "browser-smoke"
                else ToolExecutionConfig(
                    mode="process" if args.isolate_tools else "in_process",
                    hangs_before_commit=args.hang_before_commit,
                    hangs_after_commit=args.hang_after_commit,
                )
            )
            budget = Budget(
                timeout_seconds=args.timeout,
                max_actions=args.max_actions,
                max_decisions=args.max_decisions,
                action_timeout_seconds=args.action_timeout,
            )
            if args.command == "browser-smoke":
                validate_browser_deadline(args.browser_scenario, budget.action_timeout_seconds)
            provider = configured_provider(args)
        except (ValueError, ProviderError) as exc:
            parser.error(str(exc))
        try:
            result = smoke_test(
                args.output,
                provider,
                budget,
                engine=args.engine,
                tool_config=tool_config,
                tool_backend="browser" if args.command == "browser-smoke" else "sandbox",
                browser_scenario=args.browser_scenario
                if args.command == "browser-smoke"
                else "silent_drop",
            )
        except BrowserSetupError as exc:
            parser.error(str(exc))
        finally:
            if isinstance(provider, OpenAIProvider):
                provider.close()
        print(json.dumps(result, indent=2))
        if not result["smoke_passed"]:
            raise SystemExit(1)
        return
    try:
        # Validate objective and local configuration before constructing any API client.
        reviewed = None
        if args.command == "execute":
            task, reviewed = approved_task(args.proposal, args.approve)
        else:
            task = MockProvider().parse(args.objective)
        browser_backend = args.command == "execute" and args.tool_backend == "browser"
        if args.command == "execute" and args.browser_scenario != "clean" and not browser_backend:
            raise ValueError("Browser scenarios require --tool-backend browser")
        if browser_backend and args.browser_scenario != "clean" and args.silent_drops:
            raise ValueError("Select a browser scenario or --silent-drops, not both")
        if browser_backend and (
            args.isolate_tools or args.hang_before_commit or args.hang_after_commit
        ):
            raise ValueError("Browser backend cannot use isolated-worker or worker-hang options")
        if browser_backend and args.browser_artifacts.resolve() in {
            args.db.resolve(),
            args.traces.resolve(),
        }:
            raise ValueError("Browser artifact directory must differ from database files")
        budget = Budget(
            max_retries=args.max_retries,
            timeout_seconds=args.timeout,
            max_actions=args.max_actions,
            max_decisions=args.max_decisions,
            action_timeout_seconds=args.action_timeout
            if args.action_timeout is not None
            else (5 if browser_backend else 1),
        )
        tool_config = ToolExecutionConfig(
            mode="process" if args.isolate_tools else "in_process",
            hangs_before_commit=args.hang_before_commit,
            hangs_after_commit=args.hang_after_commit,
        )
        if browser_backend:
            validate_browser_deadline(args.browser_scenario, budget.action_timeout_seconds)
        faults = Faults(
            silent_drops=1
            if browser_backend and args.browser_scenario == "silent_drop"
            else args.silent_drops
        )
        if args.db.resolve() == args.traces.resolve():
            raise ValueError("State and trace databases must use separate paths")
        provider = configured_provider(args)
    except (ValueError, ProviderError, OSError) as exc:
        parser.error(str(exc))
    try:
        sandbox = Sandbox(args.db, faults)
        sandbox.seed()
        traces = TraceStore(args.traces)
        if browser_backend:
            from veriagent.browser import BrowserSetupError
            from veriagent.browser_execution import execute_browser

            try:
                result = execute_browser(
                    reviewed,
                    provider,
                    sandbox,
                    traces,
                    budget,
                    output=args.browser_artifacts,
                    engine=args.engine,
                    mode=Mode(args.mode),
                    browser_scenario=args.browser_scenario,
                )
            except BrowserSetupError as exc:
                parser.error(str(exc))
        else:
            agent_class = DynamicAgent if args.engine == "dynamic" else Agent
            report = agent_class(
                provider,
                sandbox_executor(sandbox, tool_config),
                StateVerifier(sandbox.path),
                traces,
                budget,
            ).run(task, Mode(args.mode), reviewed_proposal=reviewed)
            result = report.model_dump(mode="json")
    finally:
        if isinstance(provider, OpenAIProvider):
            provider.close()
    print(json.dumps(result, indent=2))
    if not result.get("browser_execution_passed", result["claimed_success"]):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
