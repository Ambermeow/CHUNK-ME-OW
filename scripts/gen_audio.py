"""音频库重建（幂等）：扫描数据库中所有词，为缺失的音频调用 edge-tts 生成。

音频不进 git（data/ 整体被 ignore），但可以由词文本 100% 重新生成：
文件名 = sha1(word.lower())[:12] + ".mp3"，内容只取决于词本身。

适用场景：
- 克隆了代码、拿到了 app.db，但没有 data/voice_lib/ → 跑一次全量重建
- 导入预制词库后没有发音（预制导入只复制词条，不生成音频）→ 跑一次补齐
- 之前网络原因生成失败 → 重跑本脚本自动补缺

日常新增词不需要跑：CSV 导入 / 手动加词时会自动生成。
需要联网（Microsoft TTS 端点）。

用法：
  PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/gen_audio.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.database import SessionLocal  # noqa: E402
from app.models import Word  # noqa: E402
from app.services.audio import ensure_audio, lib_name  # noqa: E402
from app.config import AUDIO_DIR  # noqa: E402


def main():
    with SessionLocal() as db:
        words = [w for (w,) in db.query(Word.word).distinct().order_by(Word.word).all()]
    missing = [w for w in words if not (AUDIO_DIR / lib_name(w)).exists()]
    print(f"数据库去重词数: {len(words)}，缺音频: {len(missing)}")
    if not missing:
        print("音频库完整，无需生成。")
        return

    ok = fail = 0
    failed_words = []
    for i, w in enumerate(missing, 1):
        if ensure_audio(w):
            ok += 1
        else:
            fail += 1
            failed_words.append(w)
        if i % 50 == 0 or i == len(missing):
            print(f"进度 {i}/{len(missing)}  成功={ok} 失败={fail}")

    if failed_words:
        print("以下词生成失败（多为网络问题，可重跑本脚本补缺）：")
        for w in failed_words[:50]:
            print("  ", w)
        if len(failed_words) > 50:
            print(f"   ...共 {len(failed_words)} 个")
        sys.exit(1)
    print("全部缺失音频已重建完成。")


if __name__ == "__main__":
    main()
