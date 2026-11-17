# Local validation

Executed on 2026-11-17, Windows, Python 3.12.16. The repository initially contained only
`.git`; no project files or existing instructions were present. The system `python`
alias could not launch and `py -0p` found no Python installation. Setup downloaded uv
to `.tools/uv.exe`, then installed Python and resolved dependencies into `.venv`.
The committed `uv.lock` records the resolved package versions and hashes.

Commands below ran from the repository root in PowerShell. `uv` was invoked using its
workspace-local executable; it was not added to the user's PATH.

| Command | Observed result |
|---|---|
| `$env:UV_PYTHON_INSTALL_DIR = Join-Path $PWD '.tools\python'; .\.tools\uv.exe python install 3.12` | Installed CPython 3.12.16; transient Windows rename warnings resolved |
| `.\.tools\uv.exe sync --extra dev` | Built editable VeriAgent and installed 25 packages |
| `.\.venv\Scripts\python.exe -m pytest -q -o faulthandler_timeout=20` | **29 passed**, 1 dependency deprecation warning, 5.49 seconds |
| `.\.venv\Scripts\ruff.exe check .` | All checks passed after style fixes |
| `.\.venv\Scripts\ruff.exe format --check .` | 18 files already formatted |
| `.\.venv\Scripts\veriagent.exe demo` | Baseline false success; verification detects mismatch; recovery succeeds with 2 actions / 1 retry |
| `.\.venv\Scripts\veriagent.exe demo --scenario persistent_drop` | Recovery stops with honest failure after 3 actions / 2 retries |
| `.\.venv\Scripts\veriagent.exe demo --scenario transient` | Recovery succeeds with 2 actions / 1 retry; baseline and verification-only fail |
| `.\.venv\Scripts\veriagent.exe run 'Set ISSUE-1, ISSUE-2 to done' --silent-drops 1` | Verified success, 3 actions, 1 retry; both final statuses done with version 1 |
| `.\.tools\uv.exe sync --extra dev --locked --offline` | Resolved and checked 25 packages successfully |
| `.\.tools\uv.exe build --offline` | Built source distribution and platform-independent wheel in `dist/` |

Actual default demo output:

```text
mode       claim  audit  false-success  actions  retries
baseline   True   False  True                 1        0
verify     False  False  False                1        0
recover    True   True   False                2        1
```

Generated raw evidence (ignored by Git) is under:

- `artifacts/40955b25310649429a589ca66af2629b/` — silent drop, three modes.
- `artifacts/ca7fc33c519b452c83bedd19a2b82f2a/` — persistent dropped writes.
- `artifacts/75716ad03f004be085dde02ce38fc11b/` — transient transport failure.

Each contains `comparison.json`, per-mode JSON/text traces, three state databases,
and the SQLite trace store. Tests independently exercise all four scenarios, including
clean execution, and the installed CLI in temporary directories.

## Environment-specific issues

The first sandboxed pytest run stopped progressing in the FastAPI test. A focused run
with `faulthandler_timeout=15` showed Windows asyncio blocked in the loopback socket
pair used to create its event loop. Both blocked runs were interrupted. The complete
suite then passed outside the execution sandbox; no test was skipped or weakened.

The initial sandboxed locked sync/build also failed to persist uv's interpreter cache
with Windows error 5. Repeating those exact offline commands outside the execution
sandbox succeeded. Initial downloading required network access; after installation,
the demo, tests, locked sync and build required no paid service or API credential.

The resolved Starlette version warns that its httpx TestClient support is deprecated
in favor of httpx2. The existing httpx path remains functional and all API assertions
passed. The warning is recorded, not suppressed. No live HTTP listener, real-model
provider, browser automation, statistical benchmark or external side effect was tested.
