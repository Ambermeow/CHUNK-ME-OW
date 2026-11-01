#!/bin/bash
# 一键后台启动/停止双服务：ASR 识别服务(8001) + 主服务(8000)
# 用法: ./scripts/run.sh {start|stop|restart|status|logs}
set -u
cd "$(dirname "$0")/.." || exit 1

UVICORN=".venv/bin/uvicorn"
LOG_DIR="data/logs"

check_env(){
  if [ ! -x "$UVICORN" ]; then
    echo "错误: 未找到 $UVICORN"
    echo "请先: python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt"
    exit 1
  fi
}

port_pids(){ lsof -tiTCP:"$1" -sTCP:LISTEN 2>/dev/null || true; }

launch(){ # $1=名称 $2=端口 $3=app模块 $4=日志文件
  local pids
  pids=$(port_pids "$2")
  if [ -n "$pids" ]; then
    echo "  $1 已在运行 (PID $pids, 端口 $2)，跳过"
    return
  fi
  mkdir -p "$LOG_DIR"
  nohup "$UVICORN" "$3" --host 127.0.0.1 --port "$2" >>"$4" 2>&1 &
  echo "  $1 已后台启动 (端口 $2)  日志: $4"
}

start(){
  check_env
  launch "ASR 识别服务" 8001 asr_service.main:app "$LOG_DIR/asr.log"
  launch "主服务"       8000 app.main:app          "$LOG_DIR/app.log"
  echo "访问: http://127.0.0.1:8000/ （ASR 模型首次使用需几秒加载）"
}

stop(){
  local found=""
  for port in 8000 8001; do
    local pids
    pids=$(port_pids "$port")
    if [ -n "$pids" ]; then
      kill $pids && echo "  已停止端口 $port 的服务 (PID $pids)"
      found=1
    else
      echo "  端口 $port 无运行中的服务"
    fi
  done
  [ -n "$found" ] && echo "SQLite 每次写操作即时落盘，无需额外刷盘。"
}

status(){
  local ok=1
  if curl -s -m 3 -o /dev/null http://127.0.0.1:8000/; then
    echo "  主服务   (8000): 运行中"
  else
    echo "  主服务   (8000): 未响应"; ok=0
  fi
  local h
  h=$(curl -s -m 5 http://127.0.0.1:8001/v1/health)
  if [ -n "$h" ]; then
    echo "  ASR 服务 (8001): 运行中 $h"
  else
    echo "  ASR 服务 (8001): 未响应"; ok=0
  fi
  [ "$ok" = 1 ] && return 0 || return 1
}

case "${1:-start}" in
  start)  start ;;
  stop)   stop ;;
  restart) stop; sleep 1; start ;;
  status) status ;;
  logs)   tail -n 60 -f "$LOG_DIR"/asr.log "$LOG_DIR"/app.log ;;
  *) echo "用法: $0 {start|stop|restart|status|logs}"; exit 1 ;;
esac
