@echo off
cd /d "%~dp0"

:: Start Streamlit using Python 3.10 user install
start "Quantix" cmd /k "C:\Users\prade\AppData\Roaming\Python\Python310\Scripts\streamlit.exe run app.py --server.port 8502 --server.address localhost"

:: Wait until Streamlit responds on port 8502
echo Waiting for server to start...
:wait_loop
timeout /t 2 /nobreak >nul
curl -s http://localhost:8502 >nul 2>&1
if errorlevel 1 goto wait_loop

echo Server is ready. Opening Chrome...

:: Try Chrome in PATH first, then common install locations
where chrome >nul 2>&1
if not errorlevel 1 (
    start "" chrome "http://localhost:8502"
    goto done
)
if exist "C:\Program Files\Google\Chrome\Application\chrome.exe" (
    start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" "http://localhost:8502"
    goto done
)
if exist "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe" (
    start "" "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe" "http://localhost:8502"
    goto done
)

echo Chrome not found. Opening in default browser...
start "" "http://localhost:8502"

:done
