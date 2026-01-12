from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Launch the OratioViva FastAPI server.")
    parser.add_argument("--host", default=os.getenv("ORATIO_HOST", "127.0.0.1"), help="Bind host")
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


def main() -> None:
    set_workdir()
    args = parse_args()

    os.environ.setdefault("ORATIO_HOST", args.host)
    os.environ.setdefault("ORATIO_PORT", str(args.port))

    import uvicorn

    uvicorn.run("backend.main:app", host=args.host, port=args.port, reload=False)


if __name__ == "__main__":
    main()
