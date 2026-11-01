"""ASR 独立服务：App Key 门禁、契约结构、错误码（引擎打桩，不加载模型）。"""
import os

os.environ["ASR_APP_KEYS"] = "test-key-alpha:spelling-app,test-key-beta:other-app"

from fastapi.testclient import TestClient  # noqa: E402

from asr_service import engine  # noqa: E402
from asr_service.main import app as asr_app  # noqa: E402

client = TestClient(asr_app)
HDR = {"X-App-Key": "test-key-alpha"}


def _stub(monkeypatch, text="tough pill to swallow"):
    monkeypatch.setattr(engine, "transcribe_bytes",
                        lambda data, language="en": {
                            "text": text, "language": "en",
                            "language_probability": 0.97, "duration_sec": 2.4,
                            "segments": [{"start": 0.0, "end": 2.4, "text": text}]})


def test_requires_app_key(monkeypatch):
    _stub(monkeypatch)
    r = client.post("/v1/asr/transcribe", files={"audio": ("a.webm", b"x")})
    assert r.status_code == 401
    r2 = client.post("/v1/asr/transcribe", files={"audio": ("a.webm", b"x")},
                     headers={"X-App-Key": "wrong-key"})
    assert r2.status_code == 401


def test_transcribe_contract(monkeypatch):
    _stub(monkeypatch)
    r = client.post("/v1/asr/transcribe", files={"audio": ("a.webm", b"x")},
                    headers=HDR)
    assert r.status_code == 200
    j = r.json()
    assert j["ok"] is True
    assert j["text"] == "tough pill to swallow"
    assert set(j) == {"ok", "text", "language", "language_probability",
                      "duration_sec", "segments"}
    assert j["segments"][0]["text"] == "tough pill to swallow"


def test_second_app_key_also_works(monkeypatch):
    _stub(monkeypatch)
    r = client.post("/v1/asr/transcribe", files={"audio": ("a.webm", b"x")},
                    headers={"X-App-Key": "test-key-beta"})
    assert r.status_code == 200


def test_audio_errors(monkeypatch):
    def boom(data, language="en"):
        raise engine.AudioError("audio_too_long", 413)
    monkeypatch.setattr(engine, "transcribe_bytes", boom)
    r = client.post("/v1/asr/transcribe", files={"audio": ("a.webm", b"x")},
                    headers=HDR)
    assert r.status_code == 413


def test_health():
    r = client.get("/v1/health")
    assert r.status_code == 200 and r.json()["ok"] is True
