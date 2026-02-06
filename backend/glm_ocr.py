from __future__ import annotations

import json
import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

GLM_OCR_DEFAULT_MODEL = os.getenv("ORATIO_GLM_OCR_MODEL", "zai-org/GLM-OCR")
GLM_OCR_TASK_PROMPTS = {
    "text": "Text Recognition:",
    "formula": "Formula Recognition:",
    "table": "Table Recognition:",
}
GLM_OCR_INPUT_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".bmp",
    ".webp",
    ".tiff",
    ".tif",
    ".pdf",
}


@dataclass
class OCRRequest:
    image_path: Path
    task: str = "text"
    prompt: Optional[str] = None
    model_id: str = GLM_OCR_DEFAULT_MODEL
    max_new_tokens: int = 2048
    max_pages: int = int(os.getenv("ORATIO_GLM_OCR_MAX_PAGES", "12"))


@dataclass
class OCRResult:
    text: str
    model: str
    task: str
    prompt: str
    device: Optional[str]
    elapsed_seconds: float


class GLMOCRService:
    def __init__(self, backend_dir: Optional[Path] = None) -> None:
        self.backend_dir = backend_dir or Path(__file__).resolve().parent
        self.worker_script = self.backend_dir / "glm_ocr_worker.py"

    def _resolve_python(self) -> Path:
        override = os.getenv("ORATIO_DIA2_PYTHON")
        if override:
            return Path(override)
        return self.backend_dir.parent / ".venv_dia2" / "Scripts" / "python.exe"

    @staticmethod
    def _timeout_seconds() -> int:
        return max(60, int(os.getenv("ORATIO_GLM_OCR_TIMEOUT", "900")))

    @staticmethod
    def resolve_prompt(task: str, prompt: Optional[str]) -> str:
        custom = (prompt or "").strip()
        if custom:
            return custom
        return GLM_OCR_TASK_PROMPTS.get(task, GLM_OCR_TASK_PROMPTS["text"])

    @staticmethod
    def parse_worker_json(raw: str, context: str = "GLM-OCR") -> dict:
        payload = (raw or "").strip()
        if not payload:
            raise RuntimeError(f"{context} worker returned empty output.")

        try:
            return json.loads(payload)
        except json.JSONDecodeError:
            pass

        lines = [line.strip() for line in payload.splitlines() if line.strip()]
        for line in reversed(lines):
            if not (line.startswith("{") and line.endswith("}")):
                continue
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue

        start = payload.find("{")
        end = payload.rfind("}")
        if start != -1 and end != -1 and end > start:
            snippet = payload[start : end + 1]
            try:
                return json.loads(snippet)
            except json.JSONDecodeError:
                pass

        raise RuntimeError(f"Invalid JSON from {context} worker: {payload[:500]}")

    def health(self) -> dict:
        heavy_python = self._resolve_python()
        return {
            "model": GLM_OCR_DEFAULT_MODEL,
            "worker_script": str(self.worker_script),
            "worker_script_exists": self.worker_script.exists(),
            "heavy_python": str(heavy_python),
            "heavy_python_exists": heavy_python.exists(),
            "supported_tasks": sorted(GLM_OCR_TASK_PROMPTS.keys()),
            "supported_extensions": sorted(GLM_OCR_INPUT_EXTENSIONS),
        }

    def run(self, request: OCRRequest) -> OCRResult:
        heavy_python, payload, prompt = self._prepare_request(request)

        fd, payload_path = tempfile.mkstemp(prefix="glm_ocr_", suffix=".json")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle)

            result = subprocess.run(
                [
                    str(heavy_python),
                    "-u",
                    str(self.worker_script),
                    "--payload",
                    payload_path,
                ],
                capture_output=True,
                text=True,
                timeout=self._timeout_seconds(),
            )

            combined_output = result.stdout or ""
            if result.stderr:
                combined_output = f"{combined_output}\n{result.stderr}".strip()
            try:
                output = self.parse_worker_json(combined_output, "GLM-OCR")
            except RuntimeError as parse_exc:
                if result.returncode != 0:
                    details = (combined_output or str(parse_exc)).strip()
                    raise RuntimeError(details[:1200]) from parse_exc
                raise

            if result.returncode != 0:
                raise RuntimeError(output.get("error") or "GLM-OCR worker failed")
            if not output.get("success"):
                raise RuntimeError(output.get("error") or "GLM-OCR failed")

            return OCRResult(
                text=str(output.get("text") or ""),
                model=str(output.get("model") or payload["model_id"]),
                task=str(output.get("task") or request.task),
                prompt=str(output.get("prompt") or prompt),
                device=output.get("device"),
                elapsed_seconds=float(output.get("elapsed_seconds") or 0.0),
            )
        finally:
            try:
                os.unlink(payload_path)
            except OSError:
                pass

    def run_with_progress(
        self,
        request: OCRRequest,
        progress_callback: Optional[Callable[[dict], None]] = None,
    ) -> OCRResult:
        heavy_python, payload, prompt = self._prepare_request(request)

        fd, payload_path = tempfile.mkstemp(prefix="glm_ocr_", suffix=".json")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle)

            process = subprocess.Popen(
                [
                    str(heavy_python),
                    "-u",
                    str(self.worker_script),
                    "--payload",
                    payload_path,
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )

            output_lines: list[str] = []
            final_payload: Optional[dict] = None

            assert process.stdout is not None
            for raw_line in process.stdout:
                line = (raw_line or "").strip()
                if not line:
                    continue
                output_lines.append(line)
                parsed = self._try_parse_line(line)
                if not parsed:
                    continue
                if parsed.get("type") == "progress":
                    if progress_callback:
                        progress_callback(parsed)
                    continue
                if "success" in parsed:
                    final_payload = parsed

            return_code = process.wait(timeout=self._timeout_seconds())
            if final_payload is None:
                combined = "\n".join(output_lines)
                final_payload = self.parse_worker_json(combined, "GLM-OCR")

            if return_code != 0 or not final_payload.get("success"):
                detail = final_payload.get("error") or "GLM-OCR worker failed"
                raise RuntimeError(str(detail))

            return OCRResult(
                text=str(final_payload.get("text") or ""),
                model=str(final_payload.get("model") or payload["model_id"]),
                task=str(final_payload.get("task") or request.task),
                prompt=str(final_payload.get("prompt") or prompt),
                device=final_payload.get("device"),
                elapsed_seconds=float(final_payload.get("elapsed_seconds") or 0.0),
            )
        finally:
            try:
                os.unlink(payload_path)
            except OSError:
                pass

    def _prepare_request(self, request: OCRRequest) -> tuple[Path, dict, str]:
        if not request.image_path.exists():
            raise ValueError(f"Image not found: {request.image_path}")

        extension = request.image_path.suffix.lower()
        if extension not in GLM_OCR_INPUT_EXTENSIONS:
            supported = ", ".join(sorted(GLM_OCR_INPUT_EXTENSIONS))
            raise ValueError(
                f"Unsupported file format '{extension}'. Use one of: {supported}"
            )

        heavy_python = self._resolve_python()
        if not heavy_python.exists():
            raise RuntimeError(
                "GLM-OCR environment is not ready. Expected heavy Python at "
                f"{heavy_python}. Set ORATIO_DIA2_PYTHON or install .venv_dia2."
            )
        if not self.worker_script.exists():
            raise RuntimeError(f"GLM-OCR worker not found: {self.worker_script}")

        prompt = self.resolve_prompt(request.task, request.prompt)
        payload = {
            "image_path": str(request.image_path),
            "task": request.task,
            "prompt": prompt,
            "model_id": request.model_id or GLM_OCR_DEFAULT_MODEL,
            "max_new_tokens": int(request.max_new_tokens),
            "max_pages": int(request.max_pages),
        }
        return heavy_python, payload, prompt

    @staticmethod
    def _try_parse_line(line: str) -> Optional[dict]:
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            return None
