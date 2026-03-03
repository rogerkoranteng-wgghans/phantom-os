# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for PhantomBackend.exe
Build from repo root:  pyinstaller build/specs/backend.spec
"""
import os

block_cipher = None

# Include the built dashboard static files
dashboard_src = os.path.join("..", "..", "backend", "static", "dashboard")
datas = []
if os.path.isdir(dashboard_src):
    datas.append((dashboard_src, "static/dashboard"))

# Include agent/api/models/services directories as packages
datas += [
    ("../../backend/agents",   "agents"),
    ("../../backend/api",      "api"),
    ("../../backend/models",   "models"),
    ("../../backend/services", "services"),
]

a = Analysis(
    ["../../backend/main.py"],
    pathex=["../../backend"],
    binaries=[],
    datas=datas,
    hiddenimports=[
        "uvicorn.logging",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.websockets",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan",
        "uvicorn.lifespan.on",
        "fastapi",
        "starlette",
        "starlette.staticfiles",
        "google.genai",
        "google.cloud.firestore",
        "redis.asyncio",
        "fakeredis",
        "fakeredis.aioredis",
        "agents.orchestrator",
        "agents.safety",
        "agents.memory",
        "agents.research",
        "agents.workflow",
        "agents.prediction",
        "agents.communication",
        "agents.phantom_core",
        "services.gemini_live",
        "services.redis_bus",
        "services.session",
        "services.action_schema",
        "api.sessions",
        "api.memory",
        "api.workflows",
        "models.schemas",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "cv2"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="PhantomBackend",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    icon="../../installer/phantom_icon.ico",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="PhantomBackend",
)
