"""词条删减（临时/永久）、valid_flag 过滤与管理员后台验收。"""
from datetime import date

from conftest import first_wl, register

from app.database import SessionLocal
from app.models import SessionItem, User, Word, WordProgress


def _import(client, hdr, words, wl_id=None):
    body = {"words": [{"word": w, "cn": f"释义{w}", "ex": f"Ex {w}."} for w in words]}
    if wl_id is not None:
        body["wordlist_id"] = wl_id
    r = client.post("/api/vocab/import", headers=hdr, json=body)
    assert r.status_code == 200, r.text
    return r.json()


def _words_map(client, hdr, wl_id):
    return {w["word"]: w for w in
            client.get("/api/words", headers=hdr,
                       params={"wordlist_id": wl_id}).json()}


def _today_words(client, hdr, wl_id):
    j = client.get("/api/today", headers=hdr,
                   params={"wordlist_id": wl_id}).json()
    return [it["correct"] for it in j["items"]]


def test_me_returns_is_admin(client):
    """/auth/me 返回 is_admin，普通用户为 False。"""
    _, hdr = register(client, "adm0@example.com")
    assert client.get("/api/auth/me", headers=hdr).json()["is_admin"] is False


def test_temp_delete_and_restore(client):
    """临时删除 → 退出今日队列与统计，总览仍可见并可恢复。"""
    _, hdr = register(client, "adm1@example.com")
    wl = first_wl(client, hdr)["id"]
    _import(client, hdr, ["keep1", "drop1"], wl_id=wl)
    wid = _words_map(client, hdr, wl)["drop1"]["id"]

    r = client.patch(f"/api/words/{wid}/valid", headers=hdr, json={"valid": False})
    assert r.status_code == 200 and r.json()["valid"] is False

    today = _today_words(client, hdr, wl)
    assert "keep1" in today and "drop1" not in today

    flags = {w["word"]: w["valid"] for w in
             client.get("/api/words", headers=hdr,
                        params={"wordlist_id": wl}).json()}
    assert flags == {"keep1": True, "drop1": False}

    dash = client.get("/api/dashboard", headers=hdr,
                      params={"wordlist_id": wl}).json()
    assert dash["total"] == 1  # 只统计有效词

    r = client.patch(f"/api/words/{wid}/valid", headers=hdr, json={"valid": True})
    assert r.status_code == 200 and r.json()["valid"] is True
    assert "drop1" in _today_words(client, hdr, wl)


def test_perm_delete_cascade(client):
    """永久删除：词行、进度、会话明细一并清理。"""
    _, hdr = register(client, "adm2@example.com")
    uid = client.get("/api/auth/me", headers=hdr).json()["id"]
    wl = first_wl(client, hdr)["id"]
    _import(client, hdr, ["gone1"], wl_id=wl)
    wid = _words_map(client, hdr, wl)["gone1"]["id"]

    r = client.post("/api/today/submit", headers=hdr,
                    json={"date": date.today().isoformat(), "wordlist_id": wl,
                          "results": [{"word": "gone1", "attempts": 1, "errors": []}]})
    assert r.status_code == 200

    assert client.delete(f"/api/words/{wid}", headers=hdr).status_code == 204
    with SessionLocal() as db:
        assert db.get(Word, wid) is None
        assert db.query(WordProgress).filter(
            WordProgress.word_id == wid, WordProgress.user_id == uid).count() == 0
        assert db.query(SessionItem).filter(SessionItem.word_id == wid).count() == 0
    assert "gone1" not in _words_map(client, hdr, wl)


def test_word_delete_authz(client):
    """他人词条：停用/永久删除一律 404。"""
    _, h1 = register(client, "adm3a@example.com")
    _, h2 = register(client, "adm3b@example.com")
    wl = first_wl(client, h1)["id"]
    _import(client, h1, ["mine1"], wl_id=wl)
    wid = _words_map(client, h1, wl)["mine1"]["id"]
    assert client.patch(f"/api/words/{wid}/valid", headers=h2,
                        json={"valid": False}).status_code == 404
    assert client.delete(f"/api/words/{wid}", headers=h2).status_code == 404


def test_admin_endpoints_forbidden(client):
    """非管理员访问 /admin → 403。"""
    _, hdr = register(client, "adm4@example.com")
    assert client.get("/api/admin/wordlists", headers=hdr).status_code == 403


def _set_admin(client, email):
    _, hdr = register(client, email)
    uid = client.get("/api/auth/me", headers=hdr).json()["id"]
    with SessionLocal() as db:
        db.get(User, uid).is_admin = True
        db.commit()
    return uid, hdr


def test_admin_wordlists_all_visible(client):
    """管理员可见全部词库（自己 + 他人），带归属信息。"""
    _, h_other = register(client, "adm5o@example.com")
    first_wl(client, h_other)
    _, hdr = _set_admin(client, "adm5@example.com")

    wls = client.get("/api/admin/wordlists", headers=hdr).json()
    owners = [w["owner"] for w in wls]
    assert "adm5@example.com" in owners
    assert "adm5o@example.com" in owners
    assert all("total" in w and "kind" in w for w in wls)


def test_admin_view_edit_delete(client):
    """管理员查词、编辑（含例句）、停用/恢复、永久删除。"""
    _, hdr = _set_admin(client, "adm6@example.com")
    wl = first_wl(client, hdr)["id"]
    _import(client, hdr, ["editme"], wl_id=wl)
    wid = _words_map(client, hdr, wl)["editme"]["id"]

    rows = client.get(f"/api/admin/wordlists/{wl}/words", headers=hdr).json()
    assert [w["id"] for w in rows] == [wid]
    assert rows[0]["valid_flag"] is True and rows[0]["example_en"] == ""

    r = client.put(f"/api/admin/words/{wid}", headers=hdr, json={
        "cn": "新释义", "example_en": "Use editme here.",
        "example_cn": "在这里使用 editme。"})
    assert r.status_code == 200
    j = r.json()
    assert j["cn"] == "新释义" and j["example_en"] == "Use editme here."
    assert j["example_cn"] == "在这里使用 editme。"

    r = client.put(f"/api/admin/words/{wid}", headers=hdr,
                   json={"valid_flag": False})
    assert r.status_code == 200 and r.json()["valid_flag"] is False

    assert client.delete(f"/api/admin/words/{wid}", headers=hdr).status_code == 204
    assert client.get(f"/api/admin/wordlists/{wl}/words", headers=hdr).json() == []
    assert client.put("/api/admin/words/99999", headers=hdr,
                      json={"cn": "x"}).status_code == 404


def test_today_includes_examples(client):
    """/today 携带例句字段；无例句为空串不报错。"""
    _, hdr = register(client, "adm7@example.com")
    wl = first_wl(client, hdr)["id"]
    _import(client, hdr, ["withex", "noex"], wl_id=wl)
    wid = _words_map(client, hdr, wl)["withex"]["id"]
    with SessionLocal() as db:
        w = db.get(Word, wid)
        w.example_en = "This chunk has an example."
        w.example_cn = "这个词块有例句。"
        db.commit()

    items = {it["correct"]: it for it in
             client.get("/api/today", headers=hdr,
                        params={"wordlist_id": wl}).json()["items"]}
    assert items["withex"]["example_en"] == "This chunk has an example."
    assert items["withex"]["example_cn"] == "这个词块有例句。"
    assert items["noex"]["example_en"] == "" and items["noex"]["example_cn"] == ""
