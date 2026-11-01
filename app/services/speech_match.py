"""跟读评分的容错比对：识别文本 vs 目标词块。纯函数，零 I/O、零耦合。

容错规则（按优先级）：
1. 别名归一：口语连读变体 ↔ 标准形互认（shoulda ↔ should have 等）
2. 冠词宽容：a / an / the 的缺失、多余、互混不计错
3. 编辑距离容错：非冠词错误数 ≤ allowed_errors 仍判通过
   （≤3 词短语要求全对；4 词以上允许 1 个词错）
"""
import re
from difflib import SequenceMatcher

# —— 1. 别名/连读归一表：所有变体 → 规范形（规范形取词库中最常见的写法）——
PHRASE_MAP: dict[str, str] = {
    "should have": "shoulda", "should of": "shoulda", "should've": "shoulda",
    "would have": "woulda", "would of": "woulda", "would've": "woulda",
    "could have": "coulda", "could of": "coulda", "could've": "coulda",
    "going to": "gonna", "want to": "wanna", "got to": "gotta",
    "have to": "hafta", "ought to": "oughta", "let me": "lemme",
    "give me": "gimme", "kind of": "kinda", "sort of": "sorta",
    "out of": "outta", "lot of": "lotta", "don't know": "dunno",
    "do not know": "dunno", "come on": "c'mon",
}

ARTICLES = {"a", "an", "the"}

_WORD_RE = re.compile(r"[a-z0-9']+")


def normalize(text: str) -> str:
    """小写、弯引号转直、去标点、压缩空格。"""
    s = (text or "").lower().replace("\u2019", "'").replace("\u2018", "'")
    s = re.sub(r"[^a-z0-9'\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def canonicalize(text: str) -> str:
    """把别名/连读变体统一替换为规范形（长短语优先，避免子串误替换）。"""
    s = normalize(text)
    for variant in sorted(PHRASE_MAP, key=len, reverse=True):
        s = re.sub(rf"\b{re.escape(variant)}\b", PHRASE_MAP[variant], s)
    return s


def tokenize(text: str) -> list[str]:
    return _WORD_RE.findall(canonicalize(text))


def allowed_errors(n_target_words: int) -> int:
    """容错预算：短短语全对，长短语允许 1 个非冠词错误。"""
    return 0 if n_target_words <= 3 else 1


def match(target: str, recognized: str) -> dict:
    """比对目标词块与识别文本，返回判定与逐词明细。

    返回:
      pass        bool   是否判为"背对了"
      score       float  命中非冠词数 / 目标非冠词数（0~1）
      errors      int    非冠词错误数（缺失/替换）
      allowed     int    本句容错预算
      details     list   目标侧逐词状态: ok / ignored_article / missing / wrong
      recognized_words   识别侧分词（规范形）
    """
    t_words = tokenize(target)
    r_words = tokenize(recognized)

    matcher = SequenceMatcher(a=t_words, b=r_words, autojunk=False)
    details: list[dict] = [{"word": w, "status": "missing"} for w in t_words]

    for op, i1, i2, j1, j2 in matcher.get_opcodes():
        if op == "equal":
            for k in range(i1, i2):
                details[k]["status"] = "ok"
        elif op == "replace":
            # 逐个对齐打 wrong；长度不等的部分保持 missing
            for k in range(i1, min(i2, i1 + (j2 - j1))):
                details[k]["status"] = "wrong"

    # 冠词宽容：目标侧冠词没被说对 → 不计错
    errors = 0
    target_non_article = 0
    for d in details:
        if d["word"] in ARTICLES:
            if d["status"] != "ok":
                d["status"] = "ignored_article"
        else:
            target_non_article += 1
            if d["status"] != "ok":
                errors += 1

    matched = target_non_article - errors
    score = round(matched / target_non_article, 3) if target_non_article else 1.0
    budget = allowed_errors(len(t_words))
    return {
        "pass": errors <= budget,
        "score": score,
        "errors": errors,
        "allowed_errors": budget,
        "details": details,
        "recognized_words": r_words,
    }
