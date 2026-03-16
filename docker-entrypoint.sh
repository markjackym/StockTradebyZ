#!/usr/bin/env bash
set -e

# 确保 state 目录存在
mkdir -p /app/data/state

case "${1:-dashboard}" in
  dashboard)
    echo "[entrypoint] 启动 Dashboard + Scheduler (supervisord) ..."
    exec supervisord -c /app/supervisord.conf
    ;;
  pipeline)
    echo "[entrypoint] 运行完整选股流程 ..."
    exec python run_all.py "${@:2}"
    ;;
  review)
    echo "[entrypoint] 仅运行 LLM 评分 ..."
    exec python agent/llm_review.py "${@:2}"
    ;;
  *)
    exec "$@"
    ;;
esac
