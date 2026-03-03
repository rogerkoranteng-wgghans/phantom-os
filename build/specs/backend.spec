# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for PhantomBackend.exe
Build from repo root:  pyinstaller build/specs/backend.spec
"""
import os

block_cipher = None

# SPECPATH is the directory containing this spec file (build/specs/)
# Go up two levels to reach the repo root
ROOT = os.path.abspath(os.path.join(SPECPATH, "..", ".."))

# Include the built dashboard static files
dashboard_src = os.path.join(ROOT, "backend", "static", "dashboard")
datas = []
if os.path.isdir(dashboard_src):
    datas.append((dashboard_src, os.path.join("static", "dashboard")))
else:
    print(f"WARNING: Dashboard not found at {dashboard_src} — skipping")

# Include backend source directories
datas += [
    (os.path.join(ROOT, "backend", "agents"),   "agents"),
    (os.path.join(ROOT, "backend", "api"),      "api"),
    (os.path.join(ROOT, "backend", "models"),   "models"),
    (os.path.join(ROOT, "backend", "services"), "services"),
]

a = Analysis(
    [os.path.join(ROOT, "backend", "main.py")],
    pathex=[os.path.join(ROOT, "backend")],
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
    icon=None,
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
