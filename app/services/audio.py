"""发音音频库（§2.5）：edge-tts en-GB-RyanNeural, rate -10%。

- 文件名 = sha1(word.lower()).hexdigest()[:12] + ".mp3"，统一存放音频库目录。
- 导入新词时对缺失音频生成（失败重试 3 次）；每日练习不实时合成，只引用库文件。
- edge-tts 2026-10 起需端点补丁（WSS 端点改 api.msedgeservices.com +
  Ocp-Apim-Subscription-Key，对应其 GitHub PR #491）；此处 best-effort 打补丁。
"""
import asyncio
import hashlib
import re
import time

from ..config import AUDIO_DIR, VOICE_RATE, VOICE_VOICE

TRUSTED_CLIENT_TOKEN = "6A5AA1D4EAFF4E9FB37E23D68491D6F4"
_PATCHED = False


def lib_name(word: str) -> str:
    return hashlib.sha1(word.lower().encode("utf-8")).hexdigest()[:12] + ".mp3"


def _apply_endpoint_patch():
    """若 edge-tts 仍指向旧端点 speech.platform.bing.com，则替换为
    api.msedgeservices.com 并补 Ocp-Apim-Subscription-Key（PR #491 的等效补丁）。"""
    global _PATCHED
    if _PATCHED:
        return
    _PATCHED = True
    try:
        import edge_tts.communicate as _com
        for attr in ("COMMUNICATE_URL", "SPEECH_CONFIG_URL", "TRUSTED_CLIENT_TOKEN"):
            val = getattr(_com, attr, None)
            if isinstance(val, str) and "speech.platform.bing.com" in val:
                setattr(_com, attr, val.replace(
                    "speech.platform.bing.com", "api.msedgeservices.com"))
        # 头部补订阅密钥（不同版本属性名不一，逐一探测）
        for cls_name in ("Communicate", "CommunicateBase"):
            cls = getattr(_com, cls_name, None)
            if cls is None:
                continue
            req = getattr(cls, "headers", None)
            if isinstance(req, dict) and "speech.platform.bing.com" in str(req):
                req["Ocp-Apim-Subscription-Key"] = TRUSTED_CLIENT_TOKEN
    except Exception:
        pass  # 版本结构不符时保持原行为


async def _gen_one(word: str, path: str):
    import edge_tts
    _apply_endpoint_patch()
    await edge_tts.Communicate(word, voice=VOICE_VOICE, rate=VOICE_RATE).save(path)


def ensure_audio(word: str) -> bool:
    """确保音频库中存在该词 mp3；缺失则生成（重试 3 次）。"""
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    path = AUDIO_DIR / lib_name(word)
    if path.exists() and path.stat().st_size > 0:
        return True

    async def _run():
        await _gen_one(word, str(path))

    for _ in range(3):
        try:
            asyncio.run(_run())
        except Exception:
            time.sleep(2)
            continue
        if path.exists() and path.stat().st_size > 0:
            return True
    # 失败时清掉半成品
    try:
        if path.exists() and path.stat().st_size == 0:
            path.unlink()
    except OSError:
        pass
    return False


_FILENAME_RE = re.compile(r"^[0-9a-f]{12}\.mp3$")


def valid_filename(name: str) -> bool:
    return bool(_FILENAME_RE.match(name))
