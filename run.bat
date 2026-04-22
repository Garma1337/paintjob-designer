@echo off
setlocal
cd /d "%~dp0"

set "VENV_PY=.venv\Scripts\python.exe"

if not exist "%VENV_PY%" (
    echo Creating virtual environment in .venv ...
    python -m venv .venv || goto :error
    "%VENV_PY%" -m pip install --upgrade pip || goto :error
    "%VENV_PY%" -m pip install -r requirements.txt || goto :error
)

"%VENV_PY%" main.py %*
exit /b %ERRORLEVEL%

:error
echo Setup failed.
exit /b 1
