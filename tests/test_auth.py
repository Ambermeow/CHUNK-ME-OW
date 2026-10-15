"""§8 账号与安全 + 验收 7/8：注册登录、隔离、限速、密钥掩码。"""
from conftest import TEST_DB, next_ip, register


def test_register_login_refresh(client):
    tok, hdr = register(client, "flow@example.com")
    r = client.get("/api/auth/me", headers=hdr)
    assert r.status_code == 200 and r.json()["email"] == "flow@example.com"

    r = client.post("/api/auth/login", json={"email": "flow@example.com",
                                             "password": "password123"},
                    headers={"X-Forwarded-For": next_ip()})
    assert r.status_code == 200
    r = client.post("/api/auth/refresh", json={"refresh_token": r.json()["refresh_token"]})
    assert r.status_code == 200

    # 错误密码
    r = client.post("/api/auth/login", json={"email": "flow@example.com",
                                             "password": "wrong-password"},
                    headers={"X-Forwarded-For": next_ip()})
    assert r.status_code == 401
    # 重复注册
    r = client.post("/api/auth/register", json={"email": "flow@example.com",
                                                "password": "password123"},
                    headers={"X-Forwarded-For": next_ip()})
    assert r.status_code == 409


def test_unauthorized(client):
    assert client.get("/api/today").status_code == 401
    assert client.get("/api/dashboard").status_code == 401
    assert client.get("/api/words").status_code == 401
    bad = {"Authorization": "Bearer not-a-token"}
    assert client.get("/api/dashboard", headers=bad).status_code == 401


def test_login_rate_limit(client):
    register(client, "rl@example.com")
    ip = "9.9.9.9"
    codes = []
    for _ in range(7):
        r = client.post("/api/auth/login",
                        json={"email": "rl@example.com", "password": "password123"},
                        headers={"X-Forwarded-For": ip})
        codes.append(r.status_code)
    assert 429 in codes, codes


def test_user_isolation(client):
    _, hdr_a = register(client, "iso-a@example.com")
    _, hdr_b = register(client, "iso-b@example.com")
    r = client.post("/api/vocab/import", headers=hdr_a,
                    json={"words": [{"word": "alpha", "cn": "甲", "ex": "A."}]})
    assert r.status_code == 200
    a_id = client.get("/api/words", headers=hdr_a).json()[0]["id"]

    # B 看不到 A 的词
    assert client.get("/api/words", headers=hdr_b).json() == []
    # 越权访问返回 404
    assert client.get(f"/api/words/{a_id}/history", headers=hdr_b).status_code == 404
    # B 导入同名词 → 自己独立一条
    r = client.post("/api/vocab/import", headers=hdr_b,
                    json={"words": [{"word": "alpha", "cn": "乙", "ex": "B."}]})
    assert r.json()["inserted"] == 1


def test_secrets_not_plaintext(client):
    tok, hdr = register(client, "sec@example.com")
    api_key = "sk-secret-12345678abcd"
    r = client.put("/api/me/settings", headers=hdr,
                   json={"llm_model": "gpt-test", "api_key": api_key})
    assert r.status_code == 200
    assert r.json()["api_key_masked"] == "sk-****abcd"
    r = client.get("/api/me/settings", headers=hdr)
    assert r.json()["api_key_masked"] == "sk-****abcd"
    assert api_key not in r.text

    raw = open(TEST_DB, "rb").read()
    assert b"password123" not in raw          # 密码不落明文
    assert api_key.encode() not in raw        # API key 加密存储
