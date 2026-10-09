"""FastAPI application: bank + progress API, bank images, static web UI."""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .storage import BankNotFound, InvalidBankId, Storage

MAX_PROGRESS_BYTES = 20 * 1024 * 1024
WEB_DIR = Path(__file__).resolve().parents[2] / "web"


def create_app(banks_dir: Path, data_dir: Path, web_dir: Path = WEB_DIR) -> FastAPI:
    storage = Storage(banks_dir, data_dir)
    app = FastAPI(title="Exam Sim", docs_url=None, redoc_url=None)
    app.state.storage = storage

    @app.exception_handler(InvalidBankId)
    async def _invalid_id(_: Request, exc: InvalidBankId):
        return JSONResponse({"detail": f"invalid bank id: {exc}"}, status_code=400)

    @app.exception_handler(BankNotFound)
    async def _not_found(_: Request, exc: BankNotFound):
        return JSONResponse({"detail": f"not found: {exc}"}, status_code=404)

    @app.get("/api/banks")
    async def list_banks():
        return storage.list_banks()

    @app.get("/api/banks/{bank_id}")
    async def get_bank(bank_id: str):
        return storage.load_bank(bank_id)

    @app.get("/api/banks/{bank_id}/progress")
    async def get_progress(bank_id: str):
        return storage.load_progress(bank_id)

    @app.put("/api/banks/{bank_id}/progress")
    async def put_progress(bank_id: str, request: Request):
        declared = request.headers.get("content-length")
        if declared and declared.isdigit() and int(declared) > MAX_PROGRESS_BYTES:
            return JSONResponse({"detail": "progress document too large"}, status_code=413)
        body = await request.body()
        if len(body) > MAX_PROGRESS_BYTES:
            return JSONResponse({"detail": "progress document too large"}, status_code=413)
        try:
            doc = json.loads(body)
            saved = storage.save_progress(bank_id, doc)
        except ValueError as exc:                     # bad JSON or failed validation
            return JSONResponse({"detail": str(exc)}, status_code=400)
        return {"ok": True, "updated_at": saved["updated_at"]}

    @app.get("/banks/{bank_id}/images/{filename}")
    async def bank_image(bank_id: str, filename: str):
        return FileResponse(storage.image_path(bank_id, filename))

    if web_dir.is_dir():
        app.mount("/", StaticFiles(directory=web_dir, html=True), name="web")
    return app
