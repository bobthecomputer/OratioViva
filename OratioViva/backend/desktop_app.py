"""
Desktop launcher for OratioViva.

Starts the FastAPI app locally, opens the bundled frontend in a native window
(pywebview), and keeps the process alive until the window/console is closed.
Intended for the packaged executable so double-clicking behaves like a desktop app.
"""

from __future__ import annotations

import os
import socket
import threading
import time
from pathlib import Path
from typing import Tuple

import httpx
import uvicorn

try:
    import webview
except Exception:  # noqa: BLE001
    webview = None  # type: ignore[assignment]


def ensure_data_dir() -> Path:
    """
    Guarantee that ORATIO_DATA_DIR exists before importing the API module so the
    backend uses the right location for outputs when bundled.
    """
    existing = os.getenv("ORATIO_DATA_DIR")
    if existing:
        path = Path(existing).expanduser().resolve()
        path.mkdir(parents=True, exist_ok=True)
        return path

    default = Path.cwd() / "data"
    default.mkdir(parents=True, exist_ok=True)
    os.environ["ORATIO_DATA_DIR"] = str(default)
    return default


DATA_DIR = ensure_data_dir()
os.environ.setdefault("ORATIO_TTS_PROVIDER", "local")

# Import the FastAPI app only after ORATIO_DATA_DIR is set.
from backend.main import app  # noqa: E402

DEFAULT_HOST = os.getenv("ORATIO_HOST", "127.0.0.1")
DEFAULT_PORT = int(os.getenv("ORATIO_PORT", "8000"))
POLL_TIMEOUT = float(os.getenv("ORATIO_APP_WAIT", "12"))


def find_available_port(host: str, preferred: int) -> int:
    """Try the preferred port first, then fall back to any free port."""
    candidates = [preferred, 0]
    for candidate in candidates:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind((host, candidate))
                return sock.getsockname()[1]
            except OSError:
                continue
    return preferred


def start_server(host: str, port: int) -> Tuple[uvicorn.Server, threading.Thread]:
    """Launch uvicorn in a background thread and return the server + thread."""
    config = uvicorn.Config(app, host=host, port=port, log_level="info")
    server = uvicorn.Server(config=config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    return server, thread


def wait_for_ready(host: str, port: int, timeout: float = POLL_TIMEOUT) -> bool:
    """Poll /health until the API answers or timeout expires."""
    url = f"http://{host}:{port}/health"
    deadline = time.time() + timeout
    with httpx.Client(timeout=3) as client:
        while time.time() < deadline:
            try:
                resp = client.get(url)
                if resp.status_code == 200:
                    return True
            except httpx.HTTPError:
                pass
            time.sleep(0.4)
    return False


def open_ui(host: str, port: int) -> None:
    """Fallback: open the studio UI in the default browser."""
    import webbrowser

    url = f"http://{host}:{port}/app/"
    webbrowser.open(url)
    print(f"[oratioviva] Interface (navigateur): {url}")


def open_desktop_window(host: str, port: int, server: uvicorn.Server) -> bool:
    """
    Open a native desktop window using pywebview.

    Returns True if the webview was started, False if pywebview is unavailable.
    """
    if webview is None:
        print("[oratioviva] pywebview non disponible, ouverture dans le navigateur...")
        return False

    url = f"http://{host}:{port}/app/"
    window = webview.create_window(
        "OratioViva",
        url=url,
        width=1200,
        height=800,
        resizable=True,
        confirm_close=True,
    )

    def _on_closed() -> None:
        print("[oratioviva] Fenetre fermee, arret du serveur...")
        server.should_exit = True

    window.events.closed += _on_closed
    print(f"[oratioviva] Interface (fenetre desktop): {url}")
    webview.start()
    return True


def main() -> None:
    host = DEFAULT_HOST
    port = find_available_port(host, DEFAULT_PORT)
    print(f"[oratioviva] Demarrage du serveur local sur {host}:{port}")
    print(f"[oratioviva] Donnees et sorties: {DATA_DIR}")

    server, thread = start_server(host, port)
    ready = wait_for_ready(host, port)
    if not ready:
        print("[oratioviva] Le serveur ne repond pas (timeout).")
        print("[oratioviva] Verifiez les logs ci-dessus ou changez ORATIO_PORT.")
        server.should_exit = True
        thread.join(timeout=2)
        return

    started_webview = open_desktop_window(host, port, server)
    if not started_webview:
        open_ui(host, port)
        print("[oratioviva] Fermez cette fenetre pour arreter l'application.")

    try:
        while thread.is_alive():
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n[oratioviva] Arret demande, fermeture...")
        server.should_exit = True
    server.should_exit = True
    thread.join(timeout=2)
    print("[oratioviva] Serveur arrete.")


if __name__ == "__main__":
    main()
