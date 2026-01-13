"""
Compat wrapper so you can run downloads from backend/:

    python download_models.py --dest ../models

It forwards args to scripts/download_models.py at repo root.
"""
from __future__ import annotations

import runpy
import sys
from pathlib import Path


def main() -> None:
    script = Path(__file__).resolve().parent.parent / "scripts" / "download_models.py"
    if not script.exists():
        raise SystemExit(f"Could not find download script at {script}")
    sys.argv = [str(script)] + sys.argv[1:]
    runpy.run_path(str(script), run_name="__main__")


if __name__ == "__main__":
    main()
