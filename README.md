# 喵喵的 CHUNK 背诵 · Chunk Spelling Trainer

中英双语 README：[中文](#中文) · [English](#english)

---

<a name="中文"></a>

# 中文

## 一、这是什么项目

一个**自托管的前后端英语拼写背诵工具**：前端练习页 + FastAPI 后端 + 数据库。专为「背 CHUNK（语块/词组）」设计，而不是背孤立的单词。

### 1. 记忆法：两阶段「循环死磕」模型

系统的核心是把艾宾浩斯遗忘曲线拆成两个阶段，对背不下来的词**无限循环、直到拿下为止**：

- **第一阶段 · 当日回炉（死磕区）**：当天首轮听音拼写，**拼错的词立刻进入回炉名单**——需要再连续答对 2 次才能毕业；中途再错，需求 +2。也就是说，一个顽固错词当天会被你反复逼着重写、重拼，**直到真正会写为止，绝不带着错误离开今天**。
- **第二阶段 · 周期复习**：当日一遍过的词进入 1 / 2 / 4 / 7 / 15 天的艾宾浩斯周期，每次到期复习仍要求「一遍过」；**任何一次复习出错，立刻打回第一阶段清零重来**。
- **严格的判词规则**：规范化（忽略大小写/空格/标点）后**逐字母严格相等**——多一个字母、少一个字母、错一个字母都算错。市面 App 普遍「接近就算对」，这正是你考场写不对的根源。
- **每日配额**：复习词 ≤ 40 + 新词 ≤ 20，回炉词优先全进，防止积压爆仓也防止贪多嚼不烂。
- **状态口径**：D0（未学）→ D1/D2/D4/D7/D15（各级一遍过）→ COM（周期全部完成）；REP = 正在回炉死磕。看板与记忆曲线（ECharts）实时可视。

### 2. CHUNK 大法为什么比传统背单词好

- **背的是「能直接输出的单位」**：`refrain from`、`conduct an objective assessment of` 这种语块，阅读写作听力里是整体出现的；孤立背 `refrain` 你依然不会用。
- **拼写即输出训练**：听音 + 全句语块拼写，同时练听力、拼写、搭配，直接对接考试写作与听写场景。
- **例句绑定语境**：每个语块带英文例句与中文释义（只在核对时出现，**练习过程中零中文、零提示**，杜绝看中文猜词的伪记忆）。
- **死磕机制天然适配长语块**：语块比单词难记，恰恰需要「当天循环到会写」这种强反馈，而不是打卡式的一瞥而过。

### 3. 比市面背单词软件好用的点

| 维度 | 本工具 | 典型商业 App |
|---|---|---|
| 判词 | 逐字母严格相等 | 近似即通过、选择题蒙对即通过 |
| 错词 | 当日无限回炉 + 周期打回 | 明天再见 / 简单标记 |
| 内容 | 你自己的 CHUNK 词库，随时导入 | 固定词书，夹杂中文提示 |
| 数据 | 完全自托管 SQLite/PostgreSQL，多账号隔离 | 存云端、算法黑箱 |
| 发音 | 英音 edge-tts 预生成音频库，秒开离线可用 | 实时合成、需联网 |
| 干扰 | 练习页无任何中文、无广告、无打卡社交 | 游戏化弹窗、中文例句先行 |
| 全程 | **不调用任何 LLM**，规则透明可复现 | 黑箱推荐 |

其他工程特性：JWT + argon2 密码 + Fernet 加密 API Key、登录限速、提交幂等、断页续练（localStorage 按用户+日期隔离）、Alembic 自动迁移、存量数据一键迁移脚本、备份脚本、Docker 一键部署。

## 二、依赖 · 技术栈 · 安装

### 技术栈

- **后端**：Python 3.12 · FastAPI · SQLAlchemy 2.x · Alembic · Pydantic v2
- **数据库**：SQLite（默认，零配置）→ 设 `DATABASE_URL` 一键切 PostgreSQL
- **安全**：pyjwt（access 30min / refresh 7d）· passlib-argon2 · cryptography(Fernet)
- **发音**：edge-tts（en-GB-RyanNeural，-10% 语速），导入时生成并缓存为 `sha1[:12].mp3` 音频库
- **前端**：单文件静态页（无构建）· ECharts（本地 vendor，离线可用）
- **测试**：pytest（覆盖全部验收标准）
- **部署**：Docker / docker-compose（app + postgres:16）

### 本地安装

```bash
cd spelling-app
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

打开 http://127.0.0.1:8000/ 注册账号即开练。

### 迁移旧数据（JSON 词库 → 数据库）

```bash
.venv/bin/python scripts/migrate_from_json.py ../spelling/vocab.json ../spelling/progress.json --user 你的邮箱
```

### Docker 部署（PostgreSQL 版）

```bash
cp .env.example .env   # 按需修改密钥/数据库配置
docker compose up -d   # db 端口不对外暴露
```

### 主要环境变量

| 变量 | 说明 | 默认 |
|---|---|---|
| `DATABASE_URL` | 数据库连接串 | `sqlite:///data/app.db` |
| `JWT_SECRET` / `FERNET_KEY` | 生产建议注入；缺省自动生成并持久化（0600） | 自动生成 |
| `DATA_DIR` / `AUDIO_DIR` | 数据与音频库目录 | `./data`、`data/voice_lib` |
| `ACCESS_TOKEN_TTL_MIN` / `REFRESH_TOKEN_TTL_DAYS` | 令牌有效期 | 30 / 7 |
| `AUTH_RATE_LIMIT` | 登录限速（次/分/IP） | 5 |
| `CORS_ORIGINS` | 跨域白名单 | localhost:8000 |

## 三、未来计划

- **CHUNK 词库分类**：按主题/场景（学术写作、商务、口语…）给语块打标签，选词算法支持按分类配额混合抽取，看板按分类展示进度。
- **一键导入**：支持从 CSV / 词表文件 / 旧词书批量导入，自动去重、自动补生成发音、可选自动补全释义与例句，导入即进入记忆循环。

---

<a name="english"></a>

# English

## 1. What This Project Is

A **self-hosted front-end + back-end English spelling trainer** (static practice UI + FastAPI + database), built for memorizing **chunks** (lexical phrases), not isolated words.

### Memory Method: a Two-Phase "Grind Until You Own It" Model

- **Phase 1 · Same-day re-forge**: misspell a word today and it enters a re-forge list requiring **2 consecutive correct answers** (each new mistake adds +2). Stubborn words are looped until you can actually write them — you never leave today with an unresolved error.
- **Phase 2 · Ebbinghaus cycle**: one-shot words advance through 1/2/4/7/15-day reviews. Any failed review **drops the word back to Phase 1 and resets progress**.
- **Strict judging**: exact letter match after normalization (case/space/punctuation-insensitive) — one extra, missing, or wrong letter fails. Most apps pass you on "close enough"; that's exactly why you still misspell under exam conditions.
- **Daily quotas**: ≤ 40 reviews + ≤ 20 new words; re-forge words always go in first.
- **Status ladder**: D0 → D1/D2/D4/D7/D15 → COM (REP = currently in re-forge), visualized live on a dashboard and an ECharts memory curve.

### Why Chunks Beat Traditional Word Lists

- You memorize **units you can directly output** (`refrain from`, `conduct an objective assessment of`) — phrases appear whole in reading, listening, and writing; a bare `refrain` stays unusable.
- Listen-and-spell full chunks trains listening, spelling, and collocation at once.
- Every chunk carries an example sentence; **zero Chinese, zero hints during practice** (definitions appear only in the review feedback), killing fake recognition.
- Long chunks are hard precisely because they need strong same-day feedback loops, not drive-by glances.

### Advantages Over Commercial Vocabulary Apps

| Aspect | This tool | Typical apps |
|---|---|---|
| Judging | Exact spelling | Near-miss / multiple-choice passes |
| Mistakes | Infinite same-day re-forge + cycle demotion | "See you tomorrow" |
| Content | Your own chunk library, import anytime | Fixed textbooks, Chinese hints |
| Data | Fully self-hosted, multi-account isolation | Cloud black box |
| Audio | Pre-generated British English edge-tts library, instant & offline | Real-time TTS, online |
| Distractions | No Chinese during practice, no ads, no gamified noise | Pop-ups, streak badges |
| Transparency | **Zero LLM calls**; rules are deterministic and reproducible | Opaque recommendation |

Engineering extras: JWT + argon2 + Fernet-encrypted API keys, login rate limiting, idempotent submissions, resumable practice (localStorage namespaced per user + date), Alembic auto-migration, one-shot legacy JSON migration script, backup script, Docker deployment.

## 2. Dependencies · Stack · Installation

**Stack**: Python 3.12 · FastAPI · SQLAlchemy 2.x · Alembic · Pydantic v2 · SQLite (default) / PostgreSQL (one env var) · edge-tts (en-GB-RyanNeural) · single-file frontend with locally vendored ECharts · pytest · Docker Compose (app + postgres:16).

```bash
cd spelling-app
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000/ and register.

Migrate legacy data:

```bash
.venv/bin/python scripts/migrate_from_json.py ../spelling/vocab.json ../spelling/progress.json --user your@email.com
```

Docker (PostgreSQL): `cp .env.example .env && docker compose up -d`.

Key env vars: `DATABASE_URL`, `JWT_SECRET`, `FERNET_KEY`, `DATA_DIR`, `AUDIO_DIR`, `ACCESS_TOKEN_TTL_MIN`, `REFRESH_TOKEN_TTL_DAYS`, `AUTH_RATE_LIMIT`, `CORS_ORIGINS`.

## 3. Roadmap

- **Chunk categorization**: tag chunks by topic/register (academic, business, spoken…), mix per-category quotas in the selection algorithm, and show per-category progress on the dashboard.
- **One-click import**: bulk import from CSV / word lists / legacy books with automatic dedup, audio generation, and optional definition/example enrichment — imported chunks enter the memory cycle immediately.
