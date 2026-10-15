FROM python:3.12-slim

WORKDIR /srv/app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1 \
    DATA_DIR=/srv/data \
    AUDIO_DIR=/srv/data/voice_lib

EXPOSE 8000

# 音频库与 SQLite 文件放持久卷（docker-compose 挂载 /srv/data）
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
