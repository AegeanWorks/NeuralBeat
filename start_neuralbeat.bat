@echo off
rem One-click NeuralBeat launcher (Windows): double-click this file.
rem First run creates an isolated .venv, installs the dependencies and
rem starts the app with the console-free pythonw interpreter.
setlocal
set "HERE=%~dp0"
cd /d "%HERE%"
set "VENV_PY=%HERE%.venv\Scripts\python.exe"
set "VENV_PYW=%HERE%.venv\Scripts\pythonw.exe"

goto :bootstrap

:notfound
echo.
echo Why: no Python 3.10+ was found to create the environment for NeuralBeat.
echo Fix: install Python 3.10 or newer from https://www.python.org/downloads/
echo      (tick "Add python.exe to PATH" during setup), then double-click
echo      this file again. On Debian/Ubuntu also run:
echo      sudo apt install python3-venv
pause
exit /b 1

:bootstrap
if exist "%VENV_PY%" goto :deps

echo [NeuralBeat] First run: creating an isolated environment (.venv)...
py -3 -m venv ".venv" 2>nul
if exist "%VENV_PY%" goto :deps
python -m venv ".venv" 2>nul
if exist "%VENV_PY%" goto :deps
goto :notfound

:deps
"%VENV_PY%" -c "import numpy, scipy, sounddevice, ttkbootstrap, matplotlib" 1>nul 2>&1
if not errorlevel 1 goto :run

echo [NeuralBeat] Installing dependencies (first run only, needs internet)...
"%VENV_PY%" -m pip install --quiet --disable-pip-version-check -r requirements.txt
if errorlevel 1 (
  echo.
  echo Why: installing the dependencies failed - offline or a build error.
  echo Fix: check your connection and the messages above, then double-click
  echo      this file again. Persistent failures:
  echo      https://github.com/AegeanWorks/NeuralBeat/issues
  pause
  exit /b 1
)

:run
start "NeuralBeat" /d "%HERE%" "%VENV_PYW%" SourceCode.py
if errorlevel 1 (
  echo.
  echo Why: NeuralBeat did not start from the launcher.
  echo Fix: run this in a terminal to see the underlying error:
  echo      "%VENV_PY%" SourceCode.py
  pause
  exit /b 1
)
exit /b 0
