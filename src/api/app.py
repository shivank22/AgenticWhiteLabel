"""HTTP API for the workflow chat UI."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src.api.chat import ChatService, TurnOutcome
from src.api.errors import ChatError, public_error
from src.api.serialize import present_thread
from src.api.sessions import NEW_THREAD_TITLE, ThreadRegistry, public_thread, title_from_message
from src.llm.factory import resolve_openai_api_key

logger = logging.getLogger(__name__)

_THREAD_ID = re.compile(r"^[0-9a-f]{32}$")
_USER_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.@-]{0,80}$")

router = APIRouter(prefix="/api")


class NoCacheStaticFiles(StaticFiles):
    """Revalidate UI files so a local refresh picks up edits."""

    async def get_response(self, path: str, scope):
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-cache"
        return response


class CreateBody(BaseModel):
    title: str | None = None


class TurnBody(BaseModel):
    content: str | None = None
    answer: Any | None = None


def find_frontend_dir() -> Path | None:
    """Locate the browser UI next to the repository that contains this file."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "frontend" / "index.html"
        if candidate.is_file():
            return candidate.parent
    return None


async def current_user(
    x_dice_user: Annotated[str | None, Header()] = None,
) -> str:
    raw = (x_dice_user or "local").strip()
    if not _USER_ID.fullmatch(raw):
        raise HTTPException(status_code=400, detail="Invalid user id.")
    return raw


async def owned_thread(
    thread_id: str,
    request: Request,
    user_id: Annotated[str, Depends(current_user)],
) -> dict[str, Any]:
    if not _THREAD_ID.fullmatch(thread_id):
        raise HTTPException(status_code=404, detail="Thread not found.")
    record = await request.app.state.registry.get(thread_id)
    if record is None or record.get("user_id") != user_id:
        raise HTTPException(status_code=404, detail="Thread not found.")
    return record


async def chat_error_handler(_request: Request, exc: ChatError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})


def _sse(event: str, data: Any) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def finalize_turn(
    registry: ThreadRegistry,
    thread_id: str,
    outcome: TurnOutcome,
) -> dict[str, Any]:
    """Persist a display reply and the sidebar phase, then return the UI view."""
    if outcome.reply and str(outcome.reply.get("content") or "").strip():
        await registry.add_reply(
            thread_id,
            index=int(outcome.reply["index"]),
            content=str(outcome.reply["content"]).strip(),
        )
    record = await registry.get(thread_id)
    title = None
    if record and not outcome.resumed and outcome.content:
        current = record.get("title") or ""
        if current in {"", NEW_THREAD_TITLE}:
            title = title_from_message(outcome.content)
    await registry.touch(
        thread_id,
        title=title,
        phase=str(outcome.view.get("phase") or "") or None,
        status=str(outcome.view.get("status") or "") or None,
        bump=True,
    )
    latest = await registry.get(thread_id)
    return present_thread(outcome.view, latest)


@router.get("/health")
async def health() -> dict[str, Any]:
    try:
        import langchain_openai  # noqa: F401

        installed = True
    except ImportError:
        installed = False
    return {
        "ok": True,
        "llm_installed": installed,
        "llm_configured": bool(installed and resolve_openai_api_key()),
    }


@router.get("/threads")
async def list_threads(
    request: Request,
    user_id: Annotated[str, Depends(current_user)],
) -> dict[str, Any]:
    records = await request.app.state.registry.list_threads(user_id)
    return {"threads": [public_thread(record) for record in records]}


@router.post("/threads", status_code=201)
async def create_thread(
    request: Request,
    user_id: Annotated[str, Depends(current_user)],
    body: CreateBody | None = None,
) -> dict[str, Any]:
    title = body.title if body is not None else None
    record = await request.app.state.registry.create(user_id, title)
    return public_thread(record)


@router.get("/threads/{thread_id}")
async def get_thread(
    request: Request,
    record: Annotated[dict[str, Any], Depends(owned_thread)],
) -> dict[str, Any]:
    chat: ChatService = request.app.state.chat
    registry: ThreadRegistry = request.app.state.registry
    view = await chat.snapshot(user_id=record["user_id"], thread_id=record["thread_id"])
    await registry.touch(
        record["thread_id"],
        phase=view["phase"],
        status=view["status"],
        bump=False,
    )
    latest = await registry.get(record["thread_id"])
    return present_thread(view, latest)


@router.delete("/threads/{thread_id}", status_code=204)
async def delete_thread(
    request: Request,
    record: Annotated[dict[str, Any], Depends(owned_thread)],
) -> Response:
    await request.app.state.registry.delete(record["thread_id"])
    return Response(status_code=204)


@router.post("/threads/{thread_id}/turns")
async def post_turn(
    request: Request,
    body: TurnBody,
    record: Annotated[dict[str, Any], Depends(owned_thread)],
) -> dict[str, Any]:
    chat: ChatService = request.app.state.chat
    outcome = await chat.run_turn(
        user_id=record["user_id"],
        thread_id=record["thread_id"],
        content=body.content,
        answer=body.answer,
    )
    return await finalize_turn(request.app.state.registry, record["thread_id"], outcome)


@router.post("/threads/{thread_id}/turns/stream")
async def stream_turn(
    request: Request,
    body: TurnBody,
    record: Annotated[dict[str, Any], Depends(owned_thread)],
) -> StreamingResponse:
    chat: ChatService = request.app.state.chat
    registry: ThreadRegistry = request.app.state.registry
    thread_id = record["thread_id"]

    async def generate() -> Any:
        try:
            async for event in chat.iter_turn_events(
                user_id=record["user_id"],
                thread_id=thread_id,
                content=body.content,
                answer=body.answer,
            ):
                if event["event"] != "snapshot":
                    yield _sse(event["event"], event["data"])
                    continue
                payload = event["data"]
                outcome = TurnOutcome(
                    view=payload["view"],
                    reply=payload.get("reply"),
                    resumed=bool(payload.get("resumed")),
                    content=payload.get("content"),
                )
                view = await finalize_turn(registry, thread_id, outcome)
                yield _sse("snapshot", view)
        except ChatError as exc:
            yield _sse("error", {"message": exc.message})
        except Exception as exc:
            logger.exception("workflow stream failed")
            yield _sse("error", {"message": public_error(exc)})

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/threads/{thread_id}/files")
async def list_files(
    request: Request,
    record: Annotated[dict[str, Any], Depends(owned_thread)],
    prefix: str = "/",
) -> dict[str, Any]:
    chat: ChatService = request.app.state.chat
    files = await chat.list_workspace(
        user_id=record["user_id"],
        thread_id=record["thread_id"],
        prefix=prefix,
    )
    return {"files": files}


@router.get("/threads/{thread_id}/files/content")
async def read_file(
    request: Request,
    record: Annotated[dict[str, Any], Depends(owned_thread)],
    path: str,
) -> dict[str, str]:
    if not path.strip():
        raise HTTPException(status_code=400, detail="A file path is required.")
    chat: ChatService = request.app.state.chat
    content = await chat.read_workspace(
        user_id=record["user_id"],
        thread_id=record["thread_id"],
        path=path,
    )
    return {"path": path, "content": content}


def create_app(
    *,
    chat: ChatService | None = None,
    registry: ThreadRegistry | None = None,
    frontend_dir: Path | None = None,
) -> FastAPI:
    """Build the API and, when the files are present, serve the chat UI."""
    app = FastAPI(
        title="DICE workflow",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        redoc_url=None,
    )
    app.state.chat = chat or ChatService()
    app.state.registry = registry or ThreadRegistry()
    app.include_router(router)
    app.add_exception_handler(ChatError, chat_error_handler)
    directory = find_frontend_dir() if frontend_dir is None else frontend_dir
    if directory is not None and (directory / "index.html").is_file():
        app.mount(
            "/",
            NoCacheStaticFiles(directory=str(directory), html=True),
            name="frontend",
        )
    else:
        logger.warning("Workflow UI files were not found; the API is still available.")
    return app
