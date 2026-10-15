"""测试环境：临时 SQLite + 临时音频目录 + 假 TTS 生成器（不联网）。"""
import base64
import os
import secrets
import tempfile

_TMP = tempfile.mkdtemp(prefix="spelltest_")
os.environ["DATA_DIR"] = os.path.join(_TMP, "data")
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP}/test.db"
os.environ["AUDIO_DIR"] = os.path.join(_TMP, "voice")
os.environ["JWT_SECRET"] = "test-jwt-secret-0123456789-0123456789-abcdef"
os.environ["FERNET_KEY"] = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import app.services.audio as audio_mod  # noqa: E402


async def _fake_gen(word: str, path: str):
    with open(path, "wb") as f:
        f.write(b"FAKE_MP3_" + word.encode())


audio_mod._gen_one = _fake_gen

from app.main import app  # noqa: E402

TEST_DB = f"{_TMP}/test.db"
_ip = [0]


def next_ip() -> str:
    _ip[0] += 1
    return f"10.77.{(_ip[0] // 254) % 254}.{_ip[0] % 254}"


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


def register(client, email: str, password: str = "password123"):
    r = client.post("/api/auth/register",
                    json={"email": email, "password": password},
                    headers={"X-Forwarded-For": next_ip()})
    assert r.status_code == 200, r.text
    return r.json(), {"Authorization": "Bearer " + r.json()["access_token"]}


@pytest.fixture(scope="session")
def user_a(client):
    return register(client, "a@test.local")
