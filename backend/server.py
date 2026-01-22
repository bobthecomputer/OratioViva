from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


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
    """Make HTTPS downloads reliable.

    Strategy:
      1) Respect an explicit user override (ORATIO_CA_BUNDLE)
      2) Respect existing REQUESTS_CA_BUNDLE/SSL_CERT_FILE/CURL_CA_BUNDLE if valid
      3) Use a bundled CA bundle shipped with the app (backend/certs/cacert.pem)
      4) Use certifi.where() if present
      5) Fallback to system trust store (truststore) if installed
    """

    override = os.getenv("ORATIO_CA_BUNDLE")
    if _is_valid_ca_bundle(override):
        _set_ca_bundle(str(Path(override).expanduser()))
        print(f"Using ORATIO_CA_BUNDLE: {os.environ['SSL_CERT_FILE']}")
        return

    for var in ("REQUESTS_CA_BUNDLE", "SSL_CERT_FILE", "CURL_CA_BUNDLE"):
        existing = os.getenv(var)
        if _is_valid_ca_bundle(existing):
            _set_ca_bundle(str(Path(existing).expanduser()))
            print(f"Using existing {var}: {os.environ['SSL_CERT_FILE']}")
            return

    bundled_cert_path = Path(__file__).parent / "certs" / "cacert.pem"
    if bundled_cert_path.is_file():
        _set_ca_bundle(str(bundled_cert_path))
        print(f"Using bundled certificates: {bundled_cert_path}")
        return

    try:
        import certifi

        cert_path = certifi.where()
    except Exception:
        cert_path = None

    if _is_valid_ca_bundle(cert_path):
        _set_ca_bundle(str(Path(cert_path).expanduser()))
        print(f"Using certifi certificates: {os.environ['SSL_CERT_FILE']}")
        return

    try:
        import truststore

        truststore.inject_into_ssl()
        for var in ("SSL_CERT_FILE", "REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE"):
            os.environ.pop(var, None)
        print("Using system trust store (truststore).")
        return
    except Exception as exc:
        for var in ("SSL_CERT_FILE", "REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE"):
            os.environ.pop(var, None)
        print(
            f"WARNING: No CA certificates available ({exc}). HTTPS downloads may fail."
        )


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
