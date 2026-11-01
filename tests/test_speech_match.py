"""跟读评分容错比对：别名归一、冠词宽容、编辑距离预算。"""
from app.services.speech_match import canonicalize, match, tokenize


def test_exact_pass():
    r = match("tough pill to swallow", "tough pill to swallow")
    assert r["pass"] and r["score"] == 1.0 and r["errors"] == 0


def test_alias_contraction():
    # 识别侧给出标准形，目标是口语连写 → 归一后相等
    r = match("shoulda woulda coulda", "should have would have could have")
    assert r["pass"] and r["errors"] == 0
    # 反向亦然
    r2 = match("should have", "shoulda")
    assert r2["pass"]
    assert "shoulda" in canonicalize("should have")


def test_article_tolerance():
    # 多说一个冠词
    assert match("tough pill to swallow", "a tough pill to swallow")["pass"]
    # 冠词互混（the → a）
    r = match("have the guts", "have a guts")
    assert r["pass"]
    assert any(d["status"] == "ignored_article" for d in r["details"])
    # 漏说冠词
    assert match("a tough pill", "tough pill")["pass"]


def test_error_budget():
    long_phrase = "revenge is a dish best served cold"
    # 长短语允许 1 个非冠词错误
    assert match(long_phrase, "revenge is a dish best served coldy")["pass"]
    # 2 个错误 → 不通过
    assert not match(long_phrase, "revenge was a dish best served coldy")["pass"]
    # 短短语（≤3 词）必须全对
    assert not match("bottle it up", "bottle it on")["pass"]
    assert match("bottle it up", "bottle it up")["pass"]


def test_empty_or_unrelated():
    r = match("music to my ears", "")
    assert not r["pass"] and r["score"] == 0.0
    r2 = match("music to my ears", "completely different words here")
    assert not r2["pass"]


def test_punctuation_and_case():
    assert match("On the same page", "on the same page.")["pass"]
    assert tokenize("HELLO, World!") == ["hello", "world"]
    # don't know 属于别名表 → 归一为 dunno
    assert tokenize("Don't KNOW!") == ["dunno"]
