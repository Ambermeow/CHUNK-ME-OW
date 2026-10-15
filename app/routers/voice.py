"""音频库静态文件（§5）：仅读、文件名白名单，防路径穿越。"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from ..config import AUDIO_DIR
from ..deps import get_current_user
from ..models import User
from ..services.audio import valid_filename

router = APIRouter(tags=["voice"])


@router.get("/voice/{filename}")
def get_voice(filename: str, user: User = Depends(get_current_user)):
    if not valid_filename(filename):
        raise HTTPException(status_code=404)
    path = AUDIO_DIR / filename
    if not path.is_file():
        raise HTTPException(status_code=404)
    return FileResponse(path, media_type="audio/mpeg")
