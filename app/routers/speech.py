"""跟读评分代理接口：前端上传录音 → 调 ASR 服务 → 本地容错比对。

ASR 服务保持纯净（音频进文本出）；比对逻辑在本服务内的
services/speech_match.py，不写库、不影响练习进度。
"""
import httpx
from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import JSONResponse

from ..config import ASR_APP_KEY, ASR_SERVICE_URL
from ..deps import get_current_user
from ..models import User
from ..services import speech_match

router = APIRouter(prefix="/speech", tags=["speech"])

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
ASR_TIMEOUT = 90.0  # 首次请求含模型懒加载，放宽超时


@router.post("/score")
async def score(audio: UploadFile = File(...),
                target: str = Form(...),
                user: User = Depends(get_current_user)):
    data = await audio.read()
    if len(data) > MAX_UPLOAD_BYTES:
        return JSONResponse(status_code=413, content={"ok": False, "error": "file_too_large"})
    if not data:
        return JSONResponse(status_code=422, content={"ok": False, "error": "empty_upload"})

    try:
        async with httpx.AsyncClient(timeout=ASR_TIMEOUT) as client:
            r = await client.post(
                f"{ASR_SERVICE_URL}/v1/asr/transcribe",
                files={"audio": (audio.filename or "rec.webm", data,
                                  audio.content_type or "application/octet-stream")},
                data={"language": "en"},
                headers={"X-App-Key": ASR_APP_KEY},
            )
    except httpx.HTTPError:
        return JSONResponse(status_code=503,
                            content={"ok": False, "error": "asr_service_unreachable"})

    if r.status_code != 200:
        detail = {}
        try:
            detail = r.json()
        except Exception:
            pass
        return JSONResponse(status_code=r.status_code,
                            content={"ok": False, "error": detail.get("detail", "asr_error")})

    recognized = r.json().get("text", "")
    result = speech_match.match(target, recognized)
    return {"ok": True, "recognized": recognized, **result}
