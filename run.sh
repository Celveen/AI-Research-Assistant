#!/usr/bin/env bash
# 一键启动后端 + 前端
set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

if [ ! -f .env ]; then
  echo "❌ 未发现 .env 文件，请先执行: cp .env.example .env 并填入 DEEPSEEK_API_KEY"
  exit 1
fi

export PYTHONPATH="$PROJECT_DIR"

# 优先使用 project2 conda 环境（如存在），否则回退到当前 PATH 中的 python
PY_BIN="/opt/anaconda3/envs/project2/bin/python"
if [ ! -x "$PY_BIN" ]; then
  PY_BIN="$(command -v python)"
  echo "⚠️  未发现 /opt/anaconda3/envs/project2，回退到: $PY_BIN"
fi

BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-8501}"

echo "🚀 启动 FastAPI 后端 (port=$BACKEND_PORT)..."
"$PY_BIN" -m uvicorn backend.main:app --host 0.0.0.0 --port "$BACKEND_PORT" --reload &
BACKEND_PID=$!

cleanup() {
  echo ""
  echo "🛑 停止服务..."
  kill $BACKEND_PID 2>/dev/null || true
  exit 0
}
trap cleanup INT TERM

sleep 3

echo "🎨 启动 Streamlit 前端 (port=$FRONTEND_PORT)..."
"$PY_BIN" -m streamlit run frontend/app.py --server.port "$FRONTEND_PORT" --server.headless true

wait $BACKEND_PID
