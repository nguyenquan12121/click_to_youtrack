@echo off
setlocal

set VENV=%~dp0\.venv
if not exist "%VENV%\Scripts\python.exe" (
  echo Creating virtualenv...
  python -m venv "%VENV%"
)

set PY=%VENV%\Scripts\python.exe
%PY% -m pip install --upgrade pip
if exist "%~dp0requirements.txt" (
  %PY% -m pip install -r "%~dp0requirements.txt"
)

echo Running app...
%PY% "%~dp0\src\app.py"
endlocal