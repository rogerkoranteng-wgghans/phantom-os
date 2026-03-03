@echo off
setlocal enabledelayedexpansion

echo =============================================
echo   Phantom OS — Windows Build Script
echo =============================================
echo.

:: Check prerequisites
where python >nul 2>&1 || (echo ERROR: Python not found. Install Python 3.11+ && exit /b 1)
where node   >nul 2>&1 || (echo ERROR: Node.js not found. Install Node 18+      && exit /b 1)
where npm    >nul 2>&1 || (echo ERROR: npm not found.                            && exit /b 1)

set ROOT=%~dp0..
cd /d %ROOT%

:: ── Step 1: Build React dashboard ────────────────────────────────────────────
echo [1/5] Building React dashboard...
cd dashboard
call npm install --silent
call npm run build
if errorlevel 1 (echo ERROR: Dashboard build failed && exit /b 1)
cd ..

:: Copy built dashboard into backend static dir
if not exist backend\static\dashboard mkdir backend\static\dashboard
xcopy /E /Y /Q dashboard\dist\* backend\static\dashboard\
echo      Dashboard copied to backend/static/dashboard

:: ── Step 2: Install Python dependencies ──────────────────────────────────────
echo [2/5] Installing Python dependencies...

python -m pip install --upgrade pip pyinstaller --quiet

:: Backend venv
cd backend
python -m venv venv_build
call venv_build\Scripts\activate.bat
pip install -r requirements.txt --quiet
pip install pyinstaller --quiet
call venv_build\Scripts\deactivate.bat
cd ..

:: Agent venv
cd agent
python -m venv venv_build
call venv_build\Scripts\activate.bat
pip install -r requirements.txt --quiet
pip install pyinstaller pystray pillow --quiet
call venv_build\Scripts\deactivate.bat
cd ..

:: Launcher deps
cd launcher
python -m venv venv_build
call venv_build\Scripts\activate.bat
pip install -r requirements.txt pyinstaller --quiet
call venv_build\Scripts\deactivate.bat
cd ..

:: ── Step 3: PyInstaller — backend ────────────────────────────────────────────
echo [3/5] Packaging backend (PhantomBackend.exe)...
cd backend
call venv_build\Scripts\activate.bat
pyinstaller --distpath ..\dist --workpath ..\build_tmp\backend --noconfirm ..\build\specs\backend.spec
if errorlevel 1 (echo ERROR: Backend packaging failed && exit /b 1)
call venv_build\Scripts\deactivate.bat
cd ..

:: ── Step 4: PyInstaller — agent ──────────────────────────────────────────────
echo [4/5] Packaging agent (PhantomAgent.exe)...
cd agent
call venv_build\Scripts\activate.bat
pyinstaller --distpath ..\dist --workpath ..\build_tmp\agent --noconfirm ..\build\specs\agent.spec
if errorlevel 1 (echo ERROR: Agent packaging failed && exit /b 1)
call venv_build\Scripts\deactivate.bat
cd ..

:: ── Step 4b: PyInstaller — launcher ──────────────────────────────────────────
echo [4b/5] Packaging launcher (PhantomOS.exe)...
cd launcher
call venv_build\Scripts\activate.bat
pyinstaller --distpath ..\dist --workpath ..\build_tmp\launcher --noconfirm ..\build\specs\launcher.spec
if errorlevel 1 (echo ERROR: Launcher packaging failed && exit /b 1)
call venv_build\Scripts\deactivate.bat
cd ..

:: Move launcher exe into dist root
move /Y dist\PhantomOS.exe dist\PhantomOS.exe >nul 2>&1

:: ── Step 5: Inno Setup ───────────────────────────────────────────────────────
echo [5/5] Creating installer with Inno Setup...
where iscc >nul 2>&1
if errorlevel 1 (
    echo WARNING: Inno Setup ^(iscc^) not found. Skipping installer creation.
    echo          Install Inno Setup from https://jrsoftware.org/isinfo.php
    echo          Then run: iscc installer\setup.iss
) else (
    iscc installer\setup.iss
    if errorlevel 1 (echo ERROR: Inno Setup failed && exit /b 1)
    echo.
    echo Installer created: installer\Output\PhantomOS-Setup.exe
)

echo.
echo =============================================
echo   Build complete!
echo   Standalone files:  dist\
echo   Installer (if built): installer\Output\PhantomOS-Setup.exe
echo =============================================
