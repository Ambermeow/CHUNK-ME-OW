"""主服务 /api/speech/score：代理 ASR + 本地容错比对（httpx 打桩）。"""
from conftest import register

import app.routers.speech as speech_router


class _FakeResp:
    def __init__(self, status, payload):
        self.status_code = status
        self._payload = payload

    def json(self):
        return self._payload


class _FakeClient:
    """替换 httpx.AsyncClient：记录调用并返回预设响应。"""
    resp = _FakeResp(200, {"ok": True, "text": "tough pill to swallow"})
    last = None

    def __init__(self, timeout=None):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def post(self, url, files=None, data=None, headers=None):
        _FakeClient.last = {"url": url, "files": files, "data": data,
                            "headers": headers}
        return _FakeClient.resp


def test_score_pass_and_key_forwarded(client, monkeypatch):
    _, hdr = register(client, "speak1@example.com")
    monkeypatch.setattr(speech_router.httpx, "AsyncClient", _FakeClient)
    _FakeClient.resp = _FakeResp(200, {"ok": True, "text": "tough pill to swallow"})

    r = client.post("/api/speech/score", headers=hdr,
                    files={"audio": ("rec.webm", b"FAKE_AUDIO")},
                    data={"target": "tough pill to swallow"})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["ok"] and j["pass"] and j["recognized"] == "tough pill to swallow"
    # App Key 由后端注入，绝不落前端
    assert _FakeClient.last["headers"]["X-App-Key"]
    assert "/v1/asr/transcribe" in _FakeClient.last["url"]


def test_score_fail_with_word_diff(client, monkeypatch):
    _, hdr = register(client, "speak2@example.com")
    monkeypatch.setattr(speech_router.httpx, "AsyncClient", _FakeClient)
    _FakeClient.resp = _FakeResp(200, {"ok": True, "text": "tough pill to swallow"})

    r = client.post("/api/speech/score", headers=hdr,
                    files={"audio": ("rec.webm", b"FAKE_AUDIO")},
                    data={"target": "bottle it up"})
    j = r.json()
    assert j["ok"] and j["pass"] is False and j["errors"] > 0
    assert len(j["details"]) == 3


def test_score_requires_login(client, monkeypatch):
    monkeypatch.setattr(speech_router.httpx, "AsyncClient", _FakeClient)
    r = client.post("/api/speech/score",
                    files={"audio": ("rec.webm", b"FAKE_AUDIO")},
                    data={"target": "bottle it up"})
    assert r.status_code == 401


def test_asr_error_passthrough(client, monkeypatch):
    _, hdr = register(client, "speak3@example.com")
    monkeypatch.setattr(speech_router.httpx, "AsyncClient", _FakeClient)
    _FakeClient.resp = _FakeResp(422, {"detail": "empty_or_silent_audio"})

    r = client.post("/api/speech/score", headers=hdr,
                    files={"audio": ("rec.webm", b"FAKE_AUDIO")},
                    data={"target": "bottle it up"})
    assert r.status_code == 422
    assert r.json()["error"] == "empty_or_silent_audio"
