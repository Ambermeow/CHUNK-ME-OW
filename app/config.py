"""配置：全部来自环境变量；本地开发缺省时自动生成并持久化密钥（不进 git）。

- DATABASE_URL  sqlite:///...（默认）→ postgresql+psycopg://... 一键切换
- JWT_SECRET / FERNET_KEY  生产用 env 注入；本地缺省时生成并存入 data/ 下（0600）
- AUDIO_DIR  音频库目录（持久卷）
- CORS_ORIGINS  逗号分隔白名单
"""
import base64
import os
import secrets
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("DATA_DIR", str(BASE_DIR / "data")))


def _persist_secret(filename: str, generator) -> str:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = DATA_DIR / filename
    if path.exists():
        val = path.read_text().strip()
        if val:
            return val
    val = generator()
    path.write_text(val)
    os.chmod(path, 0o600)
    return val


def _gen_jwt_secret() -> str:
    return secrets.token_urlsafe(48)


def _gen_fernet_key() -> str:
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()


DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DATA_DIR / 'app.db'}")
JWT_SECRET = os.getenv("JWT_SECRET") or _persist_secret(".jwt_secret", _gen_jwt_secret)
FERNET_KEY = os.getenv("FERNET_KEY") or _persist_secret(".fernet_key", _gen_fernet_key)

ACCESS_TOKEN_TTL_MIN = int(os.getenv("ACCESS_TOKEN_TTL_MIN", "30"))
REFRESH_TOKEN_TTL_DAYS = int(os.getenv("REFRESH_TOKEN_TTL_DAYS", "7"))

# 登录/注册限速（次/分钟/IP）
AUTH_RATE_LIMIT = int(os.getenv("AUTH_RATE_LIMIT", "5"))
AUTH_RATE_WINDOW_SEC = int(os.getenv("AUTH_RATE_WINDOW_SEC", "60"))

AUDIO_DIR = Path(os.getenv("AUDIO_DIR", str(DATA_DIR / "voice_lib")))
VOICE_VOICE = os.getenv("VOICE_VOICE", "en-GB-RyanNeural")
VOICE_RATE = os.getenv("VOICE_RATE", "-10%")

CORS_ORIGINS = [o.strip() for o in os.getenv(
    "CORS_ORIGINS",
    "http://localhost:8000,http://127.0.0.1:8000").split(",") if o.strip()]

# 业务常量（§2.3）
INTERVALS = ["1", "2", "4", "7", "15"]
MAX_REVIEW_PER_DAY = 40
MAX_NEW_PER_DAY = 20
DAILY_QUEUE_CAP = 60
EST_DAYS_DIVISOR = 60
