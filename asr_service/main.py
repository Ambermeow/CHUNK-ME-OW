"""ASR 独立服务入口：/v1/asr/transcribe，App Key 门禁，无状态、零业务耦合。

启动:  uvicorn asr_service.main:app --port 8001
门禁:  请求头 X-App-Key。密钥表来自环境变量
       ASR_APP_KEYS="keyA:应用名A,keyB:应用名B"
       本地缺省时自动读取/生成 data/.asr_app_key（与主服务共享，0600）。
       显式设 ASR_OPEN_MODE=1 可完全免鉴权（仅限本机调试）。
"""
import os
import secrets
from pathlib import Path

from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from . import engine

MAX_UPLOAD_BYTES = int(os.getenv("ASR_MAX_UPLOAD_BYTES", str(10 * 1024 * 1024)))

app = FastAPI(title="ASR 语音识别服务", docs_url="/docs")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in os.getenv("ASR_CORS_ORIGINS", "*").split(",")],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _load_app_keys() -> dict[str, str]:
    """key -> 应用名。环境变量优先；否则回退共享密钥文件。"""
    raw = os.getenv("ASR_APP_KEYS", "").strip()
    keys: dict[str, str] = {}
    if raw:
        for part in raw.split(","):
            if ":" in part:
                k, name = part.split(":", 1)
                if k.strip():
                    keys[k.strip()] = name.strip() or "unknown"
        return keys
    data_dir = Path(os.getenv("DATA_DIR", str(Path(__file__).resolve().parent.parent / "data")))
    secret_file = data_dir / ".asr_app_key"
    if secret_file.exists():
        val = secret_file.read_text().strip()
        if val:
            keys[val] = "spelling-app"
            return keys
    if os.getenv("ASR_OPEN_MODE") == "1":
        return keys  # 空表 + 开放模式 → 免鉴权
    # 首次本地启动：生成共享密钥（主服务 config 也会读/写同一文件）
    data_dir.mkdir(parents=True, exist_ok=True)
    val = secrets.token_urlsafe(24)
    secret_file.write_text(val)
    os.chmod(secret_file, 0o600)
    keys[val] = "spelling-app"
    return keys


APP_KEYS = _load_app_keys()
OPEN_MODE = os.getenv("ASR_OPEN_MODE") == "1" and not APP_KEYS


def _check_key(x_app_key: str | None) -> None:
    if OPEN_MODE:
        return
    if not x_app_key or x_app_key not in APP_KEYS:
        raise HTTPException(status_code=401, detail="invalid_app_key")


@app.get("/v1/health")
def health():
    return {"ok": True, "model": engine.MODEL_NAME, "ready": engine.model_ready()}


@app.post("/v1/asr/transcribe")
async def transcribe(audio: UploadFile = File(...),
                     language: str = Form("en"),
                     x_app_key: str | None = Header(default=None, alias="X-App-Key")):
    _check_key(x_app_key)
    data = await audio.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="file_too_large")
    if not data:
        raise HTTPException(status_code=422, detail="empty_upload")
    try:
        result = engine.transcribe_bytes(data, language=language)
    except engine.AudioError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))
    return {"ok": True, **result}
