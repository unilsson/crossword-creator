"""Webbserver: JSON-API och statiska filer för gränssnittet.

Miljövariabler:
    WORDLIST_PATH      ordlista att läsa in (standard /data/words.tsv)
    AUTO_FETCH_SALDO   "1" = hämta och bygg SALDO i bakgrunden om ordlistan saknas
    AI_PROVIDER m.fl.  se crossword/ai.py
"""

from __future__ import annotations

import logging
import os
import threading
from pathlib import Path

from starlette.applications import Starlette
from starlette.concurrency import run_in_threadpool
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from . import __version__, ai, saldo
from .fill import fill_grid
from .grid import clean_grid, find_slots, slot_answer, slot_pattern
from .wordlist import WordIndex, load_index

log = logging.getLogger("crossword")
STATIC_DIR = Path(__file__).parent / "static"


class State:
    def __init__(self, wordlist_path: Path, auto_fetch: bool) -> None:
        self.wordlist_path = wordlist_path
        self.index: WordIndex = load_index(wordlist_path)
        self.fetch_status = "ej startad"
        self.fetch_error = ""
        self._lock = threading.Lock()
        if auto_fetch and not wordlist_path.exists():
            self.start_fetch()

    def start_fetch(self) -> bool:
        with self._lock:
            if self.fetch_status == "pågår":
                return False
            self.fetch_status = "pågår"
            self.fetch_error = ""
        threading.Thread(target=self._fetch, daemon=True).start()
        return True

    def _fetch(self) -> None:
        try:
            saldo.fetch_and_build(self.wordlist_path)
            self.index = load_index(self.wordlist_path)
            self.fetch_status = "klar"
            log.info("SALDO inläst: %d ord", len(self.index))
        except Exception as exc:  # noqa: BLE001 – visas för användaren
            self.fetch_status = "misslyckades"
            self.fetch_error = str(exc)
            log.exception("Kunde inte hämta SALDO")


def _error(msg: str, status: int = 400) -> JSONResponse:
    return JSONResponse({"error": msg}, status_code=status)


def create_app(
    wordlist_path: Path | None = None, auto_fetch: bool | None = None, env: dict[str, str] | None = None
) -> Starlette:
    env = dict(os.environ) if env is None else env
    if wordlist_path is None:
        wordlist_path = Path(env.get("WORDLIST_PATH", "/data/words.tsv"))
    if auto_fetch is None:
        auto_fetch = env.get("AUTO_FETCH_SALDO", "0") == "1"
    state = State(wordlist_path, auto_fetch)

    try:
        provider = ai.get_provider(env)
        provider_error = ""
    except ai.AIError as exc:
        provider, provider_error = None, str(exc)

    async def status(request: Request) -> JSONResponse:
        return JSONResponse(
            {
                "version": __version__,
                "wordlist": {
                    "source": state.index.source,
                    "count": len(state.index),
                    "by_length": state.index.length_counts(),
                    "fetch_status": state.fetch_status,
                    "fetch_error": state.fetch_error,
                },
                "ai": {
                    "enabled": provider is not None,
                    "provider": provider.name if provider else None,
                    "model": provider.model if provider else None,
                    "error": provider_error,
                },
            }
        )

    async def words(request: Request) -> JSONResponse:
        pattern = request.query_params.get("pattern", "")
        if not pattern:
            return _error("Ange ett mönster, t.ex. K?T?")
        try:
            limit = max(1, min(500, int(request.query_params.get("limit", "100"))))
        except ValueError:
            limit = 100
        total, hits = state.index.search(pattern, limit)
        return JSONResponse({"pattern": pattern, "total": total, "words": [{"word": w, "score": s} for w, s in hits]})

    async def fill(request: Request) -> JSONResponse:
        body = await request.json()
        grid = body.get("grid")
        if not isinstance(grid, list) or not grid:
            return _error("grid saknas")
        if len(grid) > 25 or any(len(r) > 25 for r in grid):
            return _error("Rutnätet får vara högst 25×25")
        timeout = max(1.0, min(60.0, float(body.get("timeout", 10))))
        seed = body.get("seed")
        try:
            result = await run_in_threadpool(fill_grid, grid, state.index, timeout, seed)
        except ValueError as exc:
            return _error(str(exc))
        return JSONResponse(
            {
                "ok": result.ok,
                "grid": result.grid,
                "message": result.message,
                "elapsed_ms": result.elapsed_ms,
                "steps": result.steps,
            }
        )

    async def check(request: Request) -> JSONResponse:
        """Lista luckorna och markera ifyllda ord som saknas i ordlistan."""
        body = await request.json()
        try:
            grid = clean_grid(body.get("grid") or [])
        except ValueError as exc:
            return _error(str(exc))
        out = []
        for slot in find_slots(grid):
            answer = slot_answer(grid, slot)
            pattern = slot_pattern(grid, slot)
            out.append(
                {
                    "key": slot.key,
                    "num": slot.num,
                    "direction": slot.direction,
                    "row": slot.row,
                    "col": slot.col,
                    "length": slot.length,
                    "pattern": pattern,
                    "answer": answer,
                    "known": (answer in state.index) if answer else None,
                    "candidates": None if answer else state.index.match_bits(pattern).bit_count(),
                }
            )
        return JSONResponse({"slots": out})

    async def clues(request: Request) -> JSONResponse:
        if provider is None:
            return _error(provider_error or "Ingen AI-tjänst är konfigurerad (sätt AI_PROVIDER, se README)", 503)
        body = await request.json()
        answer = str(body.get("answer", "")).strip().upper()
        if not answer or "?" in answer:
            return _error("Ordet måste vara helt ifyllt")
        difficulty = str(body.get("difficulty", "medel"))
        count = max(1, min(8, int(body.get("count", 4))))
        context = str(body.get("context", ""))[:300]
        try:
            suggestions = await run_in_threadpool(ai.suggest_clues, provider, answer, difficulty, count, context)
        except ai.AIError as exc:
            return _error(str(exc), 502)
        return JSONResponse({"answer": answer, "clues": suggestions})

    async def wordlist_fetch(request: Request) -> JSONResponse:
        started = state.start_fetch()
        return JSONResponse({"started": started, "fetch_status": state.fetch_status})

    routes = [
        Route("/api/status", status),
        Route("/api/words", words),
        Route("/api/fill", fill, methods=["POST"]),
        Route("/api/check", check, methods=["POST"]),
        Route("/api/clues", clues, methods=["POST"]),
        Route("/api/wordlist/fetch", wordlist_fetch, methods=["POST"]),
        Mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static"),
    ]
    return Starlette(routes=routes)


def main() -> None:
    import uvicorn

    logging.basicConfig(level=logging.INFO)
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(create_app(), host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
