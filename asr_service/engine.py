"""Whisper 识别引擎：懒加载 + 解码 + 转写。纯工具层，零业务耦合。

对外仅暴露 transcribe_bytes(data, language) -> dict（§契约：单条最优结果）。
"""
import io
import os
from pathlib import Path

from faster_whisper import WhisperModel
from faster_whisper.audio import decode_audio

_ROOT = Path(__file__).resolve().parent.parent


def _resolve_model() -> str:
    """ASR_MODEL 环境变量优先；否则若本地已预置模型目录则直接用，
    避免首次请求才去 HF 下载（网络受限环境会挂死）。"""
    name = os.getenv("ASR_MODEL")
    if name:
        return name
    local_dir = Path(os.getenv("DATA_DIR", str(_ROOT / "data"))) / "asr_models" / "faster-whisper-small.en"
    if (local_dir / "model.bin").exists():
        return str(local_dir)
    return "small.en"


MODEL_NAME = _resolve_model()
DEVICE = os.getenv("ASR_DEVICE", "auto")          # auto / cpu / cuda
COMPUTE_TYPE = os.getenv("ASR_COMPUTE", "int8")    # int8 / int8_float16 / float16
MAX_DURATION_SEC = float(os.getenv("ASR_MAX_DURATION_SEC", "30"))

_model: WhisperModel | None = None


def model_ready() -> bool:
    return _model is not None


def get_model() -> WhisperModel:
    global _model
    if _model is None:
        _model = WhisperModel(MODEL_NAME, device=DEVICE, compute_type=COMPUTE_TYPE)
    return _model


class AudioError(Exception):
    """音频不可用（格式不支持/无法解码/超长/静音），附带建议 HTTP 状态码。"""

    def __init__(self, message: str, status_code: int):
        super().__init__(message)
        self.status_code = status_code


def transcribe_bytes(data: bytes, language: str = "en") -> dict:
    """音频字节 → 单条识别结果 dict。

    返回: {text, language, language_probability, duration_sec, segments}
    """
    try:
        pcm = decode_audio(io.BytesIO(data), sampling_rate=16000)
    except Exception:
        raise AudioError("unsupported_or_undecodable_audio", 415)

    duration = len(pcm) / 16000
    if duration > MAX_DURATION_SEC:
        raise AudioError("audio_too_long", 413)
    if duration < 0.3 or float(abs(pcm).max()) < 1e-4:
        raise AudioError("empty_or_silent_audio", 422)

    model = get_model()
    segments_iter, info = model.transcribe(
        pcm,
        language=language or "en",
        beam_size=5,
        vad_filter=True,
    )
    segments = []
    texts = []
    for seg in segments_iter:
        segments.append({
            "start": round(seg.start, 2),
            "end": round(seg.end, 2),
            "text": seg.text.strip(),
        })
        texts.append(seg.text.strip())

    return {
        "text": " ".join(t for t in texts if t).strip(),
        "language": info.language,
        "language_probability": round(info.language_probability, 3),
        "duration_sec": round(duration, 2),
        "segments": segments,
    }
