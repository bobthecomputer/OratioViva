#!/usr/bin/env python
"""GLM-OCR worker running in the heavy Python environment."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict

import torch
from transformers import AutoModelForImageTextToText, AutoProcessor

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

TASK_PROMPTS = {
    "text": "Text Recognition:",
    "formula": "Formula Recognition:",
    "table": "Table Recognition:",
}

_PROCESSOR: Any = None
_MODEL: Any = None
_MODEL_ID: str | None = None
_DEVICE: str = "cpu"


def _emit_progress(
    *,
    progress: float,
    message: str,
    current_page: int | None = None,
    total_pages: int | None = None,
    phase: str | None = None,
) -> None:
    payload: Dict[str, Any] = {
        "type": "progress",
        "progress": max(0.0, min(100.0, float(progress))),
        "message": message,
    }
    if current_page is not None:
        payload["current_page"] = int(current_page)
    if total_pages is not None:
        payload["total_pages"] = int(total_pages)
    if phase:
        payload["phase"] = phase
    print(json.dumps(payload, ensure_ascii=False), flush=True)


def _resolve_prompt(task: str, prompt: str | None) -> str:
    custom = (prompt or "").strip()
    if custom:
        return custom
    return TASK_PROMPTS.get(task, TASK_PROMPTS["text"])


def _load_model(model_id: str) -> tuple[Any, Any, str]:
    global _PROCESSOR, _MODEL, _MODEL_ID, _DEVICE

    if _MODEL is not None and _PROCESSOR is not None and _MODEL_ID == model_id:
        return _PROCESSOR, _MODEL, _DEVICE

    device = "cuda" if torch.cuda.is_available() else "cpu"
    dtype = torch.bfloat16 if device == "cuda" else torch.float32

    processor = AutoProcessor.from_pretrained(model_id, trust_remote_code=True)
    model = AutoModelForImageTextToText.from_pretrained(
        model_id,
        torch_dtype=dtype,
        trust_remote_code=True,
    )
    model.to(device)
    model.eval()

    _PROCESSOR = processor
    _MODEL = model
    _MODEL_ID = model_id
    _DEVICE = device
    return processor, model, device


def _render_pdf_pages(
    pdf_path: Path, temp_dir: Path, max_pages: int, dpi: int
) -> list[Path]:
    import pypdfium2

    scale = max(1.0, float(dpi) / 72.0)
    document = pypdfium2.PdfDocument(str(pdf_path))
    page_total = len(document)
    page_limit = min(page_total, max_pages)
    rendered_paths: list[Path] = []
    try:
        for index in range(page_limit):
            page = document[index]
            try:
                bitmap = page.render(scale=scale)
                image = bitmap.to_pil()
                image_path = temp_dir / f"page_{index + 1:04d}.png"
                image.save(image_path, format="PNG")
                rendered_paths.append(image_path)
            finally:
                page.close()
    finally:
        document.close()
    return rendered_paths


def _run_single_image(
    image_path: Path,
    prompt: str,
    processor: Any,
    model: Any,
    max_new_tokens: int,
) -> str:
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image", "url": str(image_path)},
                {"type": "text", "text": prompt},
            ],
        }
    ]

    inputs = processor.apply_chat_template(
        messages,
        tokenize=True,
        add_generation_prompt=True,
        return_dict=True,
        return_tensors="pt",
    )

    model_device = model.device
    tensor_inputs: Dict[str, Any] = {}
    for key, value in inputs.items():
        if hasattr(value, "to"):
            tensor_inputs[key] = value.to(model_device)
        else:
            tensor_inputs[key] = value
    tensor_inputs.pop("token_type_ids", None)

    with torch.no_grad():
        generated_ids = model.generate(**tensor_inputs, max_new_tokens=max_new_tokens)
    generated_tokens = generated_ids[0][tensor_inputs["input_ids"].shape[1] :]
    output_text = processor.decode(generated_tokens, skip_special_tokens=True)
    return output_text.strip()


def _run(payload: Dict[str, Any]) -> Dict[str, Any]:
    input_path = Path(str(payload.get("image_path") or "")).expanduser().resolve()
    if not input_path.exists():
        raise ValueError(f"Input file not found: {input_path}")

    task = str(payload.get("task") or "text").strip().lower()
    prompt = _resolve_prompt(task, payload.get("prompt"))
    model_id = str(payload.get("model_id") or "zai-org/GLM-OCR").strip()
    max_new_tokens = int(payload.get("max_new_tokens") or 2048)
    max_new_tokens = max(64, min(max_new_tokens, 8192))
    max_pages = int(
        payload.get("max_pages") or os.getenv("ORATIO_GLM_OCR_MAX_PAGES", "12")
    )
    max_pages = max(1, min(max_pages, 200))
    pdf_dpi = int(os.getenv("ORATIO_GLM_OCR_PDF_DPI", "160"))
    pdf_dpi = max(72, min(pdf_dpi, 300))

    processor, model, device = _load_model(model_id)
    _emit_progress(progress=5, message="Model ready", phase="prepare")

    started = time.perf_counter()
    suffix = input_path.suffix.lower()

    if suffix == ".pdf":
        _emit_progress(progress=8, message="Rendering PDF pages", phase="render")
        with tempfile.TemporaryDirectory(prefix="glm_ocr_pdf_") as temp_dir_raw:
            temp_dir = Path(temp_dir_raw)
            page_paths = _render_pdf_pages(
                input_path, temp_dir, max_pages=max_pages, dpi=pdf_dpi
            )
            if not page_paths:
                raise RuntimeError("No pages rendered from PDF")

            total_pages = len(page_paths)
            for index in range(total_pages):
                progress = 8 + ((index + 1) / total_pages) * 22
                _emit_progress(
                    progress=progress,
                    message=f"Rendered page {index + 1}/{total_pages}",
                    current_page=index + 1,
                    total_pages=total_pages,
                    phase="render",
                )

            outputs: list[str] = []
            for index, page_path in enumerate(page_paths, start=1):
                _emit_progress(
                    progress=30 + ((index - 1) / total_pages) * 60,
                    message=f"Running OCR page {index}/{total_pages}",
                    current_page=index,
                    total_pages=total_pages,
                    phase="ocr",
                )
                page_text = _run_single_image(
                    page_path,
                    prompt,
                    processor,
                    model,
                    max_new_tokens,
                )
                if page_text:
                    outputs.append(f"[Page {index}]\n{page_text}")

                _emit_progress(
                    progress=30 + (index / total_pages) * 60,
                    message=f"Completed page {index}/{total_pages}",
                    current_page=index,
                    total_pages=total_pages,
                    phase="ocr",
                )

            output_text = "\n\n".join(outputs).strip()
            page_count = len(page_paths)
    else:
        _emit_progress(
            progress=25,
            message="Running OCR",
            current_page=1,
            total_pages=1,
            phase="ocr",
        )
        output_text = _run_single_image(
            input_path,
            prompt,
            processor,
            model,
            max_new_tokens,
        )
        page_count = 1
        _emit_progress(
            progress=92,
            message="OCR completed",
            current_page=1,
            total_pages=1,
            phase="ocr",
        )

    elapsed = time.perf_counter() - started
    _emit_progress(
        progress=100,
        message="Done",
        current_page=page_count,
        total_pages=page_count,
        phase="done",
    )

    return {
        "success": True,
        "text": output_text.strip(),
        "model": model_id,
        "task": task,
        "prompt": prompt,
        "device": device,
        "elapsed_seconds": elapsed,
        "pages": page_count,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run GLM-OCR inference")
    parser.add_argument("--payload", required=True, help="Path to JSON payload")
    args = parser.parse_args()

    try:
        with open(args.payload, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        result = _run(payload)
        print(json.dumps(result, ensure_ascii=False))
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"success": False, "error": str(exc)}, ensure_ascii=False))
        sys.exit(1)


if __name__ == "__main__":
    main()
