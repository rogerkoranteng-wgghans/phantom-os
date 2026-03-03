# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for PhantomAgent.exe
Build from repo root:  pyinstaller build/specs/agent.spec
"""

block_cipher = None

a = Analysis(
    ["../../agent/main.py"],
    pathex=["../../agent"],
    binaries=[],
    datas=[
        ("../../agent/capture",  "capture"),
        ("../../agent/executor", "executor"),
        ("../../agent/overlay",  "overlay"),
    ],
    hiddenimports=[
        "sounddevice",
        "numpy",
        "cv2",
        "mss",
        "mss.windows",
        "pynput",
        "pynput.keyboard",
        "pynput.mouse",
        "PIL",
        "PIL.Image",
        "websockets",
        "dotenv",
        "capture.screen",
        "capture.audio",
        "capture.camera",
        "executor.mouse",
        "executor.keyboard",
        "executor.system",
        "overlay.hud",
        "client",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    name="PhantomAgent",
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
    name="PhantomAgent",
)
