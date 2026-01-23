from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# CRITICAL: Configure certificates BEFORE any HTTP libraries are imported
# This must happen at the very top, before any httpx, requests, or huggingface imports
_cert_configured = False


def _early_configure_certificates() -> None:
    """Configure certificates as early as possible, before any HTTP imports."""
    global _cert_configured
    if _cert_configured:
        return
    _cert_configured = True

    # Priority 0: explicit override
    override = os.getenv("ORATIO_CA_BUNDLE")
    if override:
        try:
            p = Path(override).expanduser()
            if p.is_file():
                os.environ["SSL_CERT_FILE"] = str(p)
                os.environ["REQUESTS_CA_BUNDLE"] = str(p)
                os.environ["CURL_CA_BUNDLE"] = str(p)
                return
        except Exception:
            pass

    # Priority 1: Tauri resource directory (for bundled app)
    # The backend folder IS the resource, so TAURI_RESOURCE_DIR points directly to it
    tauri_resource_dir = os.getenv("TAURI_RESOURCE_DIR")
    if tauri_resource_dir:
        bundled_cert_path = Path(tauri_resource_dir) / "certs" / "cacert.pem"
        if bundled_cert_path.is_file():
            os.environ["SSL_CERT_FILE"] = str(bundled_cert_path)
            os.environ["REQUESTS_CA_BUNDLE"] = str(bundled_cert_path)
            os.environ["CURL_CA_BUNDLE"] = str(bundled_cert_path)
            return

    # Priority 2: Same directory as server.py (for development)
    bundled_cert_path = Path(__file__).resolve().parent / "certs" / "cacert.pem"
    if bundled_cert_path.is_file():
        os.environ["SSL_CERT_FILE"] = str(bundled_cert_path)
        os.environ["REQUESTS_CA_BUNDLE"] = str(bundled_cert_path)
        os.environ["CURL_CA_BUNDLE"] = str(bundled_cert_path)
        return

    # Priority 3: Fall back to certifi default (suppress any warnings)
    try:
        import certifi

        cert_path = certifi.where()
        if Path(cert_path).is_file():
            os.environ["SSL_CERT_FILE"] = cert_path
            os.environ["REQUESTS_CA_BUNDLE"] = cert_path
            os.environ["CURL_CA_BUNDLE"] = cert_path
    except Exception:
        pass


# Configure certificates NOW, before any other imports
_early_configure_certificates()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Launch the OratioViva FastAPI server."
    )
    parser.add_argument(
        "--host", default=os.getenv("ORATIO_HOST", "127.0.0.1"), help="Bind host"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("ORATIO_PORT", "8000")),
        help="Bind port",
    )
    return parser.parse_args()


def set_workdir() -> None:
    """Ensure the project root is the working directory so imports work."""
    root = Path(__file__).resolve().parent.parent
    os.chdir(root)
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))


def _is_valid_ca_bundle(path: str | None) -> bool:
    if not path:
        return False
    try:
        return Path(path).expanduser().is_file()
    except Exception:
        return False


def _set_ca_bundle(path: str) -> None:
    os.environ["SSL_CERT_FILE"] = path
    os.environ["REQUESTS_CA_BUNDLE"] = path
    os.environ["CURL_CA_BUNDLE"] = path


def configure_certificates() -> None:
    """No-op: certificate config is done at import time."""
    return


def main() -> None:
    set_workdir()
    configure_certificates()
    args = parse_args()

    os.environ.setdefault("ORATIO_HOST", args.host)
    os.environ.setdefault("ORATIO_PORT", str(args.port))

    import uvicorn

    uvicorn.run("backend.main:app", host=args.host, port=args.port, reload=False)


if __name__ == "__main__":
    main()
