@echo off
setlocal
cd /d "%~dp0"

echo ============================================
echo  GPU Energy + Ollama monitoring - starting
echo ============================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] "python" was not found on PATH.
    echo Install Python 3, or activate the right environment, then try again.
    pause
    exit /b 1
)

echo [1/4] Starting energy_tracker.py  ^(GPU power/utilization sampling^)...
start "Energy Tracker" cmd /k python energy_tracker.py
ping -n 4 127.0.0.1 >nul

echo [2/4] Starting ollama_proxy.py    ^(token/TPS logging proxy on :11435^)...
start "Ollama Proxy" cmd /k python ollama_proxy.py
ping -n 3 127.0.0.1 >nul

echo [3/4] Starting the Streamlit dashboard...
start "Energy Dashboard" cmd /k streamlit run dashboard.py
ping -n 3 127.0.0.1 >nul

echo [4/4] Opening a ready-to-use Ollama chat window ^(via the proxy^)...
start "Ollama Chat (via proxy)" cmd /k "set OLLAMA_HOST=http://localhost:11435 & echo. & echo OLLAMA_HOST is set to the logging proxy (port 11435). & echo Example: ollama run llama3.1 & echo."

echo.
echo All 4 windows launched:
echo   - Energy Tracker    (GPU sampling)
echo   - Ollama Proxy       (token/TPS logging, port 11435)
echo   - Energy Dashboard   (Streamlit, opens in your browser)
echo   - Ollama Chat        (type your "ollama run ..." command there)
echo.
echo Close each window individually to stop it. This window can be closed now.
pause
