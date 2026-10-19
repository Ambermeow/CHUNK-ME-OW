"""FastAPI 入口：API（/api 前缀）+ 静态前端托管 + Alembic 自动迁移。

本地一键起步:  uvicorn app.main:app
"""
from contextlib import asynccontextmanager
from pathlib import Path

from alembic import command
from alembic.config import Config as AlembicConfig
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import AUDIO_DIR, CORS_ORIGINS, DATA_DIR
from .routers import (auth, dashboard, me, practice, vocab, voice, wordlists,
                      words)

ROOT = Path(__file__).resolve().parent.parent


def _run_migrations():
    cfg = AlembicConfig(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "alembic"))
    command.upgrade(cfg, "head")


@asynccontextmanager
async def lifespan(app: FastAPI):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    _run_migrations()
    yield


app = FastAPI(title="英语每日拼写练习系统", lifespan=lifespan, docs_url="/api/docs")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exc(request: Request, exc: Exception):
    # 错误响应不回显堆栈（§8）
    return JSONResponse(status_code=500, content={"error": "internal_error"})


for r in (auth.router, me.router, wordlists.router, practice.router,
          dashboard.router, words.router, vocab.router, voice.router):
    app.include_router(r, prefix="/api")


app.mount("/", StaticFiles(directory=str(ROOT / "app" / "static"),
                           html=True), name="static")
