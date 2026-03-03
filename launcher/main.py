"""
Phantom OS — Windows Launcher

Starts the backend and agent as child processes, opens the dashboard
in the default browser, and provides a system tray icon with a Quit option.
"""
from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path


def get_install_dir() -> Path:
    """Return the directory that contains the launcher executable (or script)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).parent.parent  # repo root when running from source


def load_config(install_dir: Path) -> dict[str, str]:
    """
    Load config from  %APPDATA%\\PhantomOS\\config.env
    then fall back to  <install_dir>\\config.env
    """
    env = {}
    candidates = [
        Path(os.environ.get("APPDATA", "")) / "PhantomOS" / "config.env",
        install_dir / "config.env",
    ]
    for path in candidates:
        if path.exists():
            for line in path.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    env[k.strip()] = v.strip()
            break
    return env


def wait_for_backend(url: str = "http://localhost:8000/health", timeout: int = 30) -> bool:
    """Poll the backend health endpoint until it responds or we time out."""
    import urllib.request
    import urllib.error

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            urllib.request.urlopen(url, timeout=2)
            return True
        except Exception:
            time.sleep(0.5)
    return False


def make_tray_icon(stop_event: threading.Event, dashboard_url: str = "http://localhost:8000/dashboard"):
    """Create and run the system tray icon (blocks until quit)."""
    try:
        import pystray
        from PIL import Image, ImageDraw

        # Draw a simple purple "P" icon
        img = Image.new("RGBA", (64, 64), (18, 18, 26, 255))
        draw = ImageDraw.Draw(img)
        draw.ellipse([4, 4, 60, 60], fill=(124, 58, 237))
        draw.text((20, 16), "P", fill="white")

        def on_quit(icon, item):
            icon.stop()
            stop_event.set()

        menu = pystray.Menu(
            pystray.MenuItem("Open Dashboard", lambda: webbrowser.open(dashboard_url)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit Phantom OS", on_quit),
        )
        icon = pystray.Icon("PhantomOS", img, "Phantom OS", menu)
        icon.run()
    except ImportError:
        # pystray not available — just wait for stop event
        stop_event.wait()


def main() -> None:
    install_dir = get_install_dir()
    config = load_config(install_dir)

    env = os.environ.copy()
    env["REDIS_URL"] = "embedded"   # no external Redis needed
    env["GOOGLE_CLOUD_PROJECT"] = config.get("GOOGLE_CLOUD_PROJECT", "phantom-os")
    if "GEMINI_API_KEY" in config:
        env["GEMINI_API_KEY"] = config["GEMINI_API_KEY"]

    # Determine backend URL — cloud or local
    backend_url = config.get("BACKEND_URL", "ws://localhost:8000")
    env["BACKEND_URL"] = backend_url
    use_cloud_backend = backend_url.startswith("wss://") or (
        backend_url.startswith("ws://") and "localhost" not in backend_url
    )

    # Derive HTTP dashboard URL from the backend WebSocket URL
    if use_cloud_backend:
        dashboard_url = backend_url.replace("wss://", "https://").replace("ws://", "http://") + "/dashboard"
    else:
        dashboard_url = "http://localhost:8000/dashboard"

    # Resolve executables — support both installed (frozen) and dev layouts
    if getattr(sys, "frozen", False):
        backend_exe = str(install_dir / "PhantomBackend" / "PhantomBackend.exe")
        agent_exe   = str(install_dir / "PhantomAgent"   / "PhantomAgent.exe")
    else:
        backend_exe = str(install_dir / "backend" / "venv" / "Scripts" / "python.exe")
        agent_exe   = str(install_dir / "agent"   / "venv" / "Scripts" / "python.exe")

    # Start local backend only if not using a cloud backend
    backend_proc = None
    if use_cloud_backend:
        print(f"Using cloud backend: {backend_url}")
    else:
        if getattr(sys, "frozen", False):
            backend_cmd = [backend_exe]
        else:
            backend_cmd = [backend_exe, "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

        backend_proc = subprocess.Popen(
            backend_cmd,
            env=env,
            cwd=str(install_dir / ("." if getattr(sys, "frozen", False) else "backend")),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        print("Waiting for Phantom OS backend to start...")
        if wait_for_backend():
            print("Backend ready.")
        else:
            print("Warning: backend took too long to start.")

    # Open dashboard
    webbrowser.open(dashboard_url)

    # Start agent
    if getattr(sys, "frozen", False):
        agent_cmd = [agent_exe]
    else:
        agent_cmd = [agent_exe, str(install_dir / "agent" / "main.py"), "--no-camera"]

    agent_proc = subprocess.Popen(
        agent_cmd,
        env=env,
        cwd=str(install_dir / ("." if getattr(sys, "frozen", False) else "agent")),
    )

    stop_event = threading.Event()

    def monitor():
        """If either child dies unexpectedly, signal quit."""
        while not stop_event.is_set():
            if agent_proc.poll() is not None:
                stop_event.set()
                break
            if backend_proc is not None and backend_proc.poll() is not None:
                stop_event.set()
                break
            time.sleep(2)

    threading.Thread(target=monitor, daemon=True).start()

    try:
        make_tray_icon(stop_event, dashboard_url)
    except KeyboardInterrupt:
        pass
    finally:
        if backend_proc is not None:
            backend_proc.terminate()
        agent_proc.terminate()
        print("Phantom OS stopped.")


if __name__ == "__main__":
    main()
