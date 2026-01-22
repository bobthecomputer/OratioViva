#!/usr/bin/env python
"""Prepare bundle_resources/models with Dia2 weights chunked.

Usage:
  python scripts/prepare_bundle_resources.py --chunk-size-mb 1024
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path

BUFFER_SIZE = 4 * 1024 * 1024


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare bundle resources with chunked Dia2 weights."
    )
    parser.add_argument(
        "--chunk-size-mb",
        type=int,
        default=1024,
        help="Chunk size in MB (default: 1024).",
    )
    parser.add_argument(
        "--models-dir",
        type=Path,
        default=Path("models"),
        help="Source models directory (default: models).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("bundle_resources") / "models",
        help="Output bundle models directory.",
    )
    return parser.parse_args()


def copy_models(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    for root, dirs, files in os.walk(src):
        rel = Path(root).relative_to(src)
        if ".cache" in dirs:
            dirs.remove(".cache")
        target_dir = dst / rel
        target_dir.mkdir(parents=True, exist_ok=True)
        for name in files:
            if rel == Path("nari-labs_Dia2-2B") and name == "model.safetensors":
                continue
            shutil.copy2(Path(root) / name, target_dir / name)


def split_file(src: Path, dst_dir: Path, chunk_size: int) -> list[str]:
    dst_dir.mkdir(parents=True, exist_ok=True)
    parts = []
    part_index = 0
    bytes_written = 0
    out_path = dst_dir / f"{src.name}.part{part_index:03d}"
    out_file = open(out_path, "wb")
    try:
        with open(src, "rb") as src_file:
            while True:
                data = src_file.read(BUFFER_SIZE)
                if not data:
                    break
                offset = 0
                while offset < len(data):
                    remaining = chunk_size - bytes_written
                    slice_end = offset + remaining
                    out_file.write(data[offset:slice_end])
                    bytes_written += min(remaining, len(data) - offset)
                    offset = slice_end
                    if bytes_written >= chunk_size:
                        out_file.close()
                        parts.append(out_path.name)
                        part_index += 1
                        out_path = dst_dir / f"{src.name}.part{part_index:03d}"
                        out_file = open(out_path, "wb")
                        bytes_written = 0
        out_file.close()
        if out_path.stat().st_size > 0:
            parts.append(out_path.name)
        else:
            out_path.unlink(missing_ok=True)
    finally:
        try:
            out_file.close()
        except Exception:
            pass
    return parts


def write_manifest(target_dir: Path, filename: str, parts: list[str], chunk_size: int, total_size: int) -> None:
    manifest = {
        "filename": filename,
        "chunk_size": chunk_size,
        "total_size": total_size,
        "parts": parts,
    }
    (target_dir / f"{filename}.parts.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )


def main() -> None:
    args = parse_args()
    source_models = args.models_dir.resolve()
    output_models = args.output_dir.resolve()

    dia2_dir = source_models / "nari-labs_Dia2-2B"
    weights_path = dia2_dir / "model.safetensors"
    if not weights_path.exists():
        raise SystemExit(f"Missing Dia2 weights: {weights_path}")

    chunk_size = args.chunk_size_mb * 1024 * 1024

    print(f"Copying models from {source_models} -> {output_models}")
    copy_models(source_models, output_models)

    target_dia2_dir = output_models / "nari-labs_Dia2-2B"
    print(f"Splitting {weights_path} into {args.chunk_size_mb}MB parts")
    parts = split_file(weights_path, target_dia2_dir, chunk_size)
    write_manifest(target_dia2_dir, weights_path.name, parts, chunk_size, weights_path.stat().st_size)
    print(f"Created {len(parts)} parts in {target_dia2_dir}")


if __name__ == "__main__":
    main()
