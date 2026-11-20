"""Optional local sandbox API. Bind to loopback; not an authenticated public service."""

from importlib.resources import files

from fastapi import FastAPI, HTTPException, Path
from fastapi.responses import HTMLResponse, Response

from veriagent.models import Issue, Schema, Status
from veriagent.sandbox import Sandbox, TransientError


class StatusUpdate(Schema):
    status: Status


def create_app(sandbox: Sandbox) -> FastAPI:
    app = FastAPI(title="VeriAgent local sandbox", version="0.1.0")

    @app.get("/ui/issues/{issue_id}", response_class=HTMLResponse)
    def issue_page(issue_id: str = Path(pattern=r"^ISSUE-\d+$")) -> HTMLResponse:
        html = files("veriagent").joinpath("web/issue.html").read_text(encoding="utf-8")
        return HTMLResponse(
            html.replace("__ISSUE_ID__", issue_id),
            headers={
                "Content-Security-Policy": (
                    "default-src 'self'; script-src 'self'; style-src 'unsafe-inline'; "
                    "connect-src 'self'; frame-src 'none'; base-uri 'none'; form-action 'self'"
                ),
                "Cache-Control": "no-store",
            },
        )

    @app.get("/ui/app.js")
    def browser_script() -> Response:
        script = files("veriagent").joinpath("web/app.js").read_text(encoding="utf-8")
        return Response(script, media_type="application/javascript")

    @app.get("/issues/{issue_id}", response_model=Issue)
    def read_issue(issue_id: str) -> Issue:
        try:
            return sandbox.read_issue(issue_id)
        except KeyError as exc:
            raise HTTPException(404, "Issue not found") from exc

    @app.patch("/issues/{issue_id}/status")
    def set_status(issue_id: str, body: StatusUpdate) -> dict:
        try:
            return sandbox.set_status(issue_id, body.status, timeout=1)
        except KeyError as exc:
            raise HTTPException(404, "Issue not found") from exc
        except TransientError as exc:
            raise HTTPException(503, "Transient sandbox failure") from exc
        except TimeoutError as exc:
            raise HTTPException(504, "Sandbox deadline exceeded") from exc

    return app
