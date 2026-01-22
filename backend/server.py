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


def configure_certificates() -> None:
    import certifi
    from pathlib import Path

    cert_path = certifi.where()
    bundled_cert_path = Path(__file__).parent / "certs" / "cacert.pem"

    if cert_path and os.path.isfile(cert_path):
        os.environ.setdefault("SSL_CERT_FILE", cert_path)
        os.environ.setdefault("REQUESTS_CA_BUNDLE", cert_path)
        os.environ.setdefault("CURL_CA_BUNDLE", cert_path)
        print(f"Using certifi certificates: {cert_path}")
    elif bundled_cert_path.is_file():
        os.environ.setdefault("SSL_CERT_FILE", str(bundled_cert_path))
        os.environ.setdefault("REQUESTS_CA_BUNDLE", str(bundled_cert_path))
        os.environ.setdefault("CURL_CA_BUNDLE", str(bundled_cert_path))
        print(f"Using bundled certificates: {bundled_cert_path}")
    else:
        for var in ["SSL_CERT_FILE", "REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE"]:
            os.environ.pop(var, None)
        print("WARNING: No CA certificates available. Downloads may fail.")


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
