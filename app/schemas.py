"""Pydantic v2 严格校验所有入参（§8）。"""
from datetime import date

from pydantic import BaseModel, ConfigDict, EmailStr, Field

MAX_IMPORT_WORDS = 500
MAX_SUBMIT_RESULTS = 200


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class RefreshIn(BaseModel):
    refresh_token: str = Field(min_length=10, max_length=4096)


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class SettingsIn(BaseModel):
    llm_model: str | None = Field(default=None, max_length=128)
    api_key: str | None = Field(default=None, min_length=8, max_length=512)


class SettingsOut(BaseModel):
    llm_model: str | None
    api_key_masked: str | None


class WordlistCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64)


class WordlistUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=64)
    new_words_per_day: int | None = Field(default=None, ge=1, le=100)


class WordlistOut(BaseModel):
    id: int
    name: str
    kind: str
    new_words_per_day: int
    total: int
    mastered: int
    unstarted: int
    created_on: date


class PresetOut(BaseModel):
    id: int
    name: str
    total: int


class TodayItem(BaseModel):
    i: int
    audio_url: str
    correct: str
    cn: str
    ex: str


class TodayOut(BaseModel):
    date: date
    items: list[TodayItem]
    has_local_draft_hint: bool
    submitted_summary: dict | None = None


class SubmitResult(BaseModel):
    word: str = Field(min_length=1, max_length=255)
    attempts: int = Field(ge=0, le=1000)
    errors: list[str] = Field(default_factory=list, max_length=30)
    one_shot: bool = False

    model_config = ConfigDict(extra="ignore")


class SubmitIn(BaseModel):
    date: date
    wordlist_id: int | None = None
    results: list[SubmitResult] = Field(min_length=1, max_length=MAX_SUBMIT_RESULTS)


class SubmitOut(BaseModel):
    date: date
    total: int
    one_shot: int
    retry: int


class DashboardOut(BaseModel):
    total: int
    started: int
    mastered: int
    cycling: int
    daily: int
    unstarted: int
    est_days: int
    new_words_per_day: int
    next_review_count: int


class WordOut(BaseModel):
    id: int
    word: str
    cn: str
    added_on: date
    status: str


class HistoryPoint(BaseModel):
    date: date
    status: str | None


class NextOut(BaseModel):
    date: date
    count: int
    items: list[dict]


class ImportWord(BaseModel):
    word: str = Field(min_length=1, max_length=255)
    cn: str = Field(default="", max_length=512)
    ex: str = Field(default="", max_length=1024)


class ImportIn(BaseModel):
    wordlist_id: int | None = None
    words: list[ImportWord] = Field(min_length=1, max_length=MAX_IMPORT_WORDS)


class ImportOut(BaseModel):
    inserted: int
    total: int
    audio_ok: bool
    audio_failed: list[str]
    skipped: list[str]
