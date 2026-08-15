@echo off
cd /d "%~dp0"

set PYTHON=C:\Users\prade\AppData\Roaming\Python\Python310\Scripts
set PY=C:\Users\prade\AppData\Local\Programs\Python\Python310\python.exe

:: Fall back to py launcher if explicit path missing
if not exist "%PY%" set PY=py -3.10

echo ============================================
echo  Quantix — Starting up
echo ============================================

:: Install / update dependencies silently
echo Checking dependencies...
"%PY%" -m pip install -r requirements.txt --quiet --disable-pip-version-check
if errorlevel 1 (
    echo WARNING: Some packages may not have installed correctly.
    pause
)

echo Dependencies OK. Starting Streamlit...

:: Launch Streamlit
start "Quantix" cmd /k "%PYTHON%\streamlit.exe run app.py --server.port 8502 --server.address localhost"

:: Wait until server responds
echo Waiting for server...
:wait_loop
timeout /t 2 /nobreak >nul
curl -s http://localhost:8502 >nul 2>&1
if errorlevel 1 goto wait_loop

echo Server ready. Opening browser...

:: Open Chrome (try PATH, then common locations, then default browser)
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

start "" "http://localhost:8502"

:done
