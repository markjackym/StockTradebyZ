#!/usr/bin/env bash
set -e

case "${1:-dashboard}" in
  dashboard)
    echo "[entrypoint] 启动 Streamlit Dashboard ..."
    exec streamlit run dashboard/app.py \
      --server.port=8501 \
      --server.address=0.0.0.0 \
      --server.headless=true
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
