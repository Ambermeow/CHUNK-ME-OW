"""词库层验收：注册送默认词库、同用户命名去重、预制复制、跨词库独立、删库级联、越权 404。"""
from datetime import date

from conftest import first_wl, register

from app.database import SessionLocal
from app.models import PracticeSession, Word, Wordlist


def _import(client, hdr, words, wl_id=None):
    body = {"words": [{"word": w, "cn": f"释义{w}", "ex": f"Ex {w}."} for w in words]}
    if wl_id is not None:
        body["wordlist_id"] = wl_id
    r = client.post("/api/vocab/import", headers=hdr, json=body)
    assert r.status_code == 200, r.text
    return r.json()


def _mk_preset(name="预制词库A", words=("alpha", "beta")):
    """直接写库构造一个系统预制词库（user_id=NULL, kind=system）。"""
    with SessionLocal() as db:
        wl = Wordlist(user_id=None, name=name, kind="system", created_on=date.today())
        db.add(wl)
        db.flush()
        for w in words:
            db.add(Word(user_id=None, wordlist_id=wl.id, word=w,
                        cn=f"释义{w}", ex="", added_on=date.today()))
        db.commit()
        return wl.id


def test_register_default_wordlist(client):
    """注册即送默认词库「自定义词库」。"""
    _, hdr = register(client, "wl0@example.com")
    wls = client.get("/api/wordlists", headers=hdr).json()
    assert len(wls) == 1
    assert wls[0]["name"] == "自定义词库"
    assert wls[0]["kind"] == "custom"
    assert wls[0]["total"] == 0


def test_create_duplicate_name_suffix(client):
    """同用户内建重名词库 → 统一加 ·{uid} 后缀。"""
    _, hdr = register(client, "wl1@example.com")
    uid = client.get("/api/auth/me", headers=hdr).json()["id"]
    r = client.post("/api/wordlists", headers=hdr, json={"name": "自定义词库"})
    assert r.status_code == 200
    assert r.json()["name"] == f"自定义词库·{uid}"


def test_rename_conflict_suffix(client):
    """改名撞上已有词库名 → 同样加 ·{uid} 后缀。"""
    _, hdr = register(client, "wl2@example.com")
    uid = client.get("/api/auth/me", headers=hdr).json()["id"]
    b = client.post("/api/wordlists", headers=hdr, json={"name": "词库B"}).json()
    r = client.put(f"/api/wordlists/{b['id']}", headers=hdr,
                   json={"name": "自定义词库"})
    assert r.status_code == 200
    assert r.json()["name"] == f"自定义词库·{uid}"


def test_add_preset_copies(client):
    """添加预制词库 = 复制母本进账户：词条数一致、可重复添加、进度从零。"""
    _, hdr = register(client, "wl3@example.com")
    pid = _mk_preset()
    r = client.post(f"/api/wordlists/{pid}/add", headers=hdr)
    assert r.status_code == 200
    wl = r.json()
    assert wl["kind"] == "custom" and wl["total"] == 2 and wl["unstarted"] == 2

    names = [w["name"] for w in client.get("/api/wordlists", headers=hdr).json()]
    assert "预制词库A" in names

    # 再添加一次 → 后缀区分，仍是独立副本
    r2 = client.post(f"/api/wordlists/{pid}/add", headers=hdr)
    assert r2.status_code == 200 and r2.json()["total"] == 2
    assert r2.json()["name"] != wl["name"]

    # 系统预制列表可见且不含用户副本
    ps = client.get("/api/wordlists/system", headers=hdr).json()
    assert any(p["id"] == pid and p["total"] == 2 for p in ps)

    # 不存在的预制 → 404
    assert client.post("/api/wordlists/99999/add", headers=hdr).status_code == 404


def test_same_word_independent_across_wordlists(client):
    """同一个词在两个词库中进度互不影响。"""
    _, hdr = register(client, "wl4@example.com")
    wl1 = first_wl(client, hdr)["id"]
    wl2 = client.post("/api/wordlists", headers=hdr, json={"name": "第二词库"}).json()["id"]
    for wl in (wl1, wl2):
        assert _import(client, hdr, ["shared"], wl_id=wl)["inserted"] == 1

    r = client.post("/api/today/submit", headers=hdr,
                    json={"date": date.today().isoformat(), "wordlist_id": wl1,
                          "results": [{"word": "shared", "attempts": 1, "errors": []}]})
    assert r.status_code == 200

    st1 = {w["word"]: w["status"] for w in
           client.get("/api/words", headers=hdr, params={"wordlist_id": wl1}).json()}
    st2 = {w["word"]: w["status"] for w in
           client.get("/api/words", headers=hdr, params={"wordlist_id": wl2}).json()}
    assert st1["shared"] == "D1"
    assert st2["shared"] == "D0"


def test_per_wordlist_new_cap(client):
    """每日新词 N 按词库独立，互不影响。"""
    _, hdr = register(client, "wl5@example.com")
    wl1 = first_wl(client, hdr)["id"]
    wl2 = client.post("/api/wordlists", headers=hdr, json={"name": "词库二"}).json()["id"]

    r = client.put(f"/api/wordlists/{wl1}", headers=hdr, json={"new_words_per_day": 7})
    assert r.status_code == 200 and r.json()["new_words_per_day"] == 7

    caps = {w["id"]: w["new_words_per_day"]
            for w in client.get("/api/wordlists", headers=hdr).json()}
    assert caps[wl1] == 7
    assert caps[wl2] == 20  # 未配置 → 环境变量默认


def test_delete_wordlist_cascade(client):
    """删库级联：词条、进度、会话与明细全部清理。"""
    _, hdr = register(client, "wl6@example.com")
    uid = client.get("/api/auth/me", headers=hdr).json()["id"]
    wl_id = first_wl(client, hdr)["id"]
    _import(client, hdr, ["del1", "del2"], wl_id=wl_id)
    r = client.post("/api/today/submit", headers=hdr,
                    json={"date": date.today().isoformat(), "wordlist_id": wl_id,
                          "results": [{"word": "del1", "attempts": 1, "errors": []}]})
    assert r.status_code == 200

    assert client.delete(f"/api/wordlists/{wl_id}", headers=hdr).status_code == 200
    assert client.get("/api/words", headers=hdr,
                      params={"wordlist_id": wl_id}).status_code == 404
    with SessionLocal() as db:
        assert db.query(Word).filter(Word.wordlist_id == wl_id).count() == 0
        assert (db.query(PracticeSession)
                .filter(PracticeSession.user_id == uid,
                        PracticeSession.wordlist_id == wl_id).count() == 0)


def test_wordlist_authz(client):
    """他人词库：改名/删除一律 404。"""
    _, h1 = register(client, "wl7a@example.com")
    _, h2 = register(client, "wl7b@example.com")
    wl1 = first_wl(client, h1)["id"]
    assert client.put(f"/api/wordlists/{wl1}", headers=h2,
                      json={"name": "哈哈"}).status_code == 404
    assert client.delete(f"/api/wordlists/{wl1}", headers=h2).status_code == 404
