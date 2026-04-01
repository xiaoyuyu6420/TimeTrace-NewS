#!/bin/bash
echo "========================================"
echo "  TimeTrace - Starting all services"
echo "========================================"

# Start backend
echo "[1/2] Starting backend (port 8000)..."
cd "$(dirname "$0")/backend"
python run.py &
BACKEND_PID=$!
sleep 3

# Start frontend
echo "[2/2] Starting frontend (port 5173)..."
cd "$(dirname "$0")/web"
npm run dev &
FRONTEND_PID=$!

echo ""
echo "========================================"
echo "  Services running!"
echo "  Frontend: http://localhost:5173"
echo "  Backend:  http://localhost:8000"
echo "  API Docs: http://localhost:8000/docs"
echo "========================================"
echo "  Default admin: admin / admin123"
echo ""

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM
wait
