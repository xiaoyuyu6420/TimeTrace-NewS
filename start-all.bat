@echo off
echo ========================================
echo   TimeTrace - Start All Services
echo ========================================
echo.

echo [1/2] Starting backend (port 8000)...
cd /d "%~dp0backend"
start "Backend" cmd /k "python run.py"
timeout /t 3 /nobreak >nul

echo [2/2] Starting frontend (port 5173)...
cd /d "%~dp0web"
start "Frontend" cmd /k "npm run dev"
timeout /t 3 /nobreak >nul

echo.
echo ========================================
echo   Services started!
echo   Frontend:  http://localhost:5173
echo   Backend:   http://localhost:8000
echo   API Docs:  http://localhost:8000/docs
echo   Admin:     admin / admin123
echo ========================================
echo.
pause
