from __future__ import annotations

import asyncio
import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from ssscreen_web.api import artifacts, datasets, events, health, me, projects, runs, tasks, uploads
from ssscreen_web.api.errors import install_error_handlers
from ssscreen_web.settings import get_settings
from ssscreen_web.workers.celery_app import (
    dispatch_pending_outbox,
    reconcile_stale_published_outbox,
)
from ssscreen_web.workers.composition_task import recover_stale_composition_tasks
from ssscreen_web.workers.condensation_task import recover_stale_condensation_tasks
from ssscreen_web.workers.example_task import recover_stale_demo_tasks
from ssscreen_web.workers.mp_dataset_task import recover_stale_mp_dataset_tasks
from ssscreen_web.workers.wbm_dataset_task import recover_stale_wbm_dataset_tasks

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    del app
    settings = get_settings()
    stopped = asyncio.Event()

    async def reconcile_outbox() -> None:
        while not stopped.is_set():
            try:
                await asyncio.to_thread(reconcile_stale_published_outbox)
                await asyncio.to_thread(dispatch_pending_outbox)
                await asyncio.to_thread(recover_stale_demo_tasks)
                await asyncio.to_thread(recover_stale_mp_dataset_tasks)
                await asyncio.to_thread(recover_stale_wbm_dataset_tasks)
                await asyncio.to_thread(recover_stale_composition_tasks)
                await asyncio.to_thread(recover_stale_condensation_tasks)
            except Exception:
                logger.exception("Control-plane reconciliation failed")
            try:
                await asyncio.wait_for(stopped.wait(), timeout=settings.outbox_reconcile_seconds)
            except TimeoutError:
                pass

    task = asyncio.create_task(reconcile_outbox())
    try:
        yield
    finally:
        stopped.set()
        await task


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="SS-Screen Web API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
        allow_headers=["Content-Type", "Last-Event-ID", "Idempotency-Key"],
    )

    @app.middleware("http")
    async def trace_request(request: Request, call_next):
        request.state.trace_id = request.headers.get("X-Trace-ID", str(uuid.uuid4()))
        response = await call_next(request)
        response.headers["X-Trace-ID"] = request.state.trace_id
        return response

    for router in (
        health.router,
        me.router,
        projects.router,
        uploads.router,
        datasets.router,
        runs.router,
        tasks.router,
        artifacts.router,
        events.router,
    ):
        app.include_router(router)
    install_error_handlers(app)
    return app


app = create_app()
