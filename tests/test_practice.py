"""验收 2/3/4/5/6：选词规则、提交后状态、实时看板、音频、记忆曲线。"""
from datetime import date, timedelta

from conftest import register

from app.database import SessionLocal
from app.services.ebbinghaus import select_queue, word_status


def _submit(client, hdr, day, results):
    r = client.post("/api/today/submit", headers=hdr,
                    json={"date": day.isoformat(),
                          "results": [{"word": w, "attempts": a, "errors": e}
                                      for w, a, e in results]})
    assert r.status_code == 200, r.text
    return r.json()


def _import(client, hdr, words):
    r = client.post("/api/vocab/import", headers=hdr,
                    json={"words": [{"word": w, "cn": f"释义{w}", "ex": f"Ex {w}."}
                                    for w in words]})
    assert r.status_code == 200, r.text
    return r.json()


def _status_map(client, hdr):
    return {w["word"]: w["status"] for w in client.get("/api/words", headers=hdr).json()}


def test_submit_status_rules(client):
    """验收3：一遍过推进一档且 last_done=今天；有 errors 一律回 daily；
    D7 词写错次日出现在回炉队列且状态列显示 REP。"""
    _, hdr = register(client, "s3@example.com")
    today = date.today()
    _import(client, hdr, ["ticket", "bracket", "pocket"])

    # 三天前开始周期：ticket 一路一遍过到 D7（s1,s2,s4 已完成）
    d0 = today - timedelta(days=12)
    _submit(client, hdr, d0, [("ticket", 1, []), ("bracket", 1, []), ("pocket", 1, [])])
    _submit(client, hdr, d0 + timedelta(days=1), [("ticket", 1, [])])
    _submit(client, hdr, d0 + timedelta(days=2), [("ticket", 1, [])])
    _submit(client, hdr, d0 + timedelta(days=4), [("ticket", 1, [])])
    assert _status_map(client, hdr)["ticket"] == "D7"

    # D7 词今天写错 → REP，且次日在回炉队列
    _submit(client, hdr, today, [("ticket", 2, ["ticiket"])])
    assert _status_map(client, hdr)["ticket"] == "REP"
    with SessionLocal() as db:
        uid = client.get("/api/auth/me", headers=hdr).json()["id"]
        review, _new = select_queue(db, uid, today + timedelta(days=1))
        assert "ticket" in [w.word for w in review]

    # 一遍过：last_done=今天
    with SessionLocal() as db:
        from app.models import Word, WordProgress
        w = db.query(Word).filter(Word.user_id == uid, Word.word == "ticket").first()
        p = db.query(WordProgress).filter(WordProgress.word_id == w.id).first()
        assert p.last_done is None or p.last_done <= today
        # 重新一遍过 → cycle, D1, last_done=今天
        _submit(client, hdr, today, [("ticket", 1, [])])
        db.expire_all()
        p = db.query(WordProgress).filter(WordProgress.word_id == w.id).first()
        assert p.phase == "cycle" and p.last_done == today
        assert _status_map(client, hdr)["ticket"] == "D1"


def test_selection_quotas(client):
    """验收2：回炉优先全进、到期按 last_done+间隔、40/20 独立配额。"""
    _, hdr = register(client, "s2@example.com")
    uid = client.get("/api/auth/me", headers=hdr).json()["id"]
    today = date.today()

    many = [f"w{i:03d}" for i in range(50)]
    _import(client, hdr, many)
    _submit(client, hdr, today - timedelta(days=1), [(w, 1, []) for w in many])
    # 50 个周期词今天全部到期（间隔1）→ 复习上限 40
    with SessionLocal() as db:
        review, new = select_queue(db, uid, today)
        assert len(review) == 40 and len(new) == 0

    # 5 个回炉词优先全进 + 35 个周期词补足 40；新词名额独立 20
    _submit(client, hdr, today, [(w, 2, ["x" + w]) for w in many[:5]])
    fresh = [f"n{i:03d}" for i in range(25)]
    _import(client, hdr, fresh)
    with SessionLocal() as db:
        review, new = select_queue(db, uid, today + timedelta(days=1))
        daily_words = {w for w in many[:5]}
        assert daily_words.issubset({w.word for w in review})
        assert len(review) == 40
        assert len(new) == 20

    # 到期判定 = last_done + 第一个未完成阶段间隔（w010 不在回炉名单里）
    with SessionLocal() as db:
        from app.models import Word, WordProgress
        w = db.query(Word).filter(Word.user_id == uid, Word.word == "w010").first()
        p = db.query(WordProgress).filter(WordProgress.word_id == w.id).first()
        p.last_done = today                      # 今天刚练成
        p.s1 = True                              # 下一档间隔 2
        db.commit()
        with SessionLocal() as db2:
            review, _ = select_queue(db2, uid, today + timedelta(days=1))
            assert "w010" not in [x.word for x in review]
            review, _ = select_queue(db2, uid, today + timedelta(days=2))
            assert "w010" in [x.word for x in review]


def test_dashboard_realtime(client):
    """验收4：导入 3 个新词后不重启，总词数、未学数、明日预览立即更新。"""
    _, hdr = register(client, "s4@example.com")
    base = client.get("/api/dashboard", headers=hdr).json()
    r = _import(client, hdr, ["rt1", "rt2", "rt3"])
    after = client.get("/api/dashboard", headers=hdr).json()
    assert after["total"] == base["total"] + 3
    assert after["unstarted"] == base["unstarted"] + 3
    nxt = client.get("/api/next", headers=hdr).json()
    assert {"rt1", "rt2", "rt3"}.issubset({i["word"] for i in nxt["items"]})


def test_voice_served(client):
    """验收5：导入含缺失音频的词后音频可即时取到。"""
    _, hdr = register(client, "s5@example.com")
    _import(client, hdr, ["voicetest"])
    words = client.get("/api/words", headers=hdr).json()
    vid = [w for w in words if w["word"] == "voicetest"][0]["id"]
    import hashlib
    fname = hashlib.sha1(b"voicetest").hexdigest()[:12] + ".mp3"
    r = client.get(f"/api/voice/{fname}", headers=hdr)
    assert r.status_code == 200 and r.content == b"FAKE_MP3_voicetest"
    # 非法文件名拒绝（非 12 位 hex.mp3）
    assert client.get("/api/voice/bad_name.mp3", headers=hdr).status_code == 404


def test_memory_curve(client):
    """验收6：升到 D7 → 写错 → REP → D1 → … → COM，曲线呈 V 型回落再爬升。"""
    _, hdr = register(client, "s6@example.com")
    _import(client, hdr, ["curve"])
    vid = [w for w in client.get("/api/words", headers=hdr).json()
           if w["word"] == "curve"][0]["id"]
    d0 = date.today() - timedelta(days=30)
    seq = [
        (d0, 1, []), (d0 + timedelta(days=1), 1, []), (d0 + timedelta(days=2), 1, []),
        (d0 + timedelta(days=4), 1, []), (d0 + timedelta(days=7), 1, []),   # → D15
        (d0 + timedelta(days=15), 2, ["curv"]),                             # → REP
        (d0 + timedelta(days=16), 1, []),                                   # → D1
        (d0 + timedelta(days=17), 1, []), (d0 + timedelta(days=19), 1, []),
        (d0 + timedelta(days=23), 1, []), (d0 + timedelta(days=30), 1, []),
        (d0 + timedelta(days=31), 1, []),                                   # → COM
    ]
    for day, att, errs in seq:
        _submit(client, hdr, day, [("curve", att, errs)])
    hist = client.get(f"/api/words/{vid}/history", headers=hdr).json()
    levels = [h["status"] for h in hist]
    assert levels == ["D1", "D2", "D4", "D7", "D15", "REP",
                      "D1", "D2", "D4", "D7", "D15", "COM"]


def test_new_words_per_day_config(client):
    """每日新词 N：用户配置写库生效，选词/看板估算随 N 变化；非法值拒绝。"""
    _, hdr = register(client, "s7@example.com")
    _import(client, hdr, [f"nwc{i}" for i in range(10)])

    r = client.put("/api/me/settings", headers=hdr, json={"new_words_per_day": 3})
    assert r.status_code == 200 and r.json()["new_words_per_day"] == 3

    items = client.get("/api/today", headers=hdr).json()["items"]
    assert len(items) == 3  # 全是新词，无复习 → 恰好 N 个

    dash = client.get("/api/dashboard", headers=hdr).json()
    assert dash["new_words_per_day"] == 3
    assert dash["est_days"] == 4  # ceil(10 / 3)

    # 非法值
    assert client.put("/api/me/settings", headers=hdr,
                      json={"new_words_per_day": 0}).status_code == 422
    assert client.put("/api/me/settings", headers=hdr,
                      json={"new_words_per_day": 101}).status_code == 422

    # 改回 5 → 今日队列立即变 5
    client.put("/api/me/settings", headers=hdr, json={"new_words_per_day": 5})
    assert len(client.get("/api/today", headers=hdr).json()["items"]) == 5


def test_no_llm_calls():
    """验收10：全程无任何 LLM 调用（代码中不存在模型请求路径）。"""
    import pathlib
    root = pathlib.Path(__file__).resolve().parent.parent / "app"
    banned = ["openai", "anthropic", "chatgpt", "api.openai", "azure.com/openai",
              "dashscope", "deepseek"]
    for f in root.rglob("*.py"):
        text = f.read_text(encoding="utf-8").lower()
        for b in banned:
            assert b not in text, f"{f.name} 含 LLM 请求路径: {b}"
