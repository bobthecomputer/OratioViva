import importlib
import os
import sys
from pathlib import Path

import pytest

httpx = pytest.importorskip("httpx")
ASGITransport = httpx.ASGITransport
AsyncClient = httpx.AsyncClient


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))


@pytest.fixture(scope="session")
def app():
    os.environ["ORATIO_TTS_STUB"] = "1"
    import backend.main as backend_main

    importlib.reload(backend_main)
    return backend_main.app


@pytest.mark.asyncio
async def test_ocr_prompts_endpoint(app):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/ocr/prompts")
        assert resp.status_code == 200
        data = resp.json()
        assert "tasks" in data
        assert "text" in data["tasks"]


@pytest.mark.asyncio
async def test_ocr_rejects_non_image_upload(app):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/ocr/glm",
            files={"file": ("notes.txt", b"hello", "text/plain")},
            data={"task": "text"},
        )
        assert resp.status_code == 400
        assert "Unsupported file format" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_ocr_glm_success_with_mocked_service(app, monkeypatch):
    import backend.main as backend_main
    from backend.glm_ocr import OCRResult

    def fake_run(request):
        assert request.task == "text"
        return OCRResult(
            text="hello world",
            model="zai-org/GLM-OCR",
            task="text",
            prompt="Text Recognition:",
            device="cpu",
            elapsed_seconds=0.12,
        )

    monkeypatch.setattr(backend_main.ocr_service, "run", fake_run)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/ocr/glm",
            files={"file": ("sample.png", b"fake-image-bytes", "image/png")},
            data={"task": "text", "max_new_tokens": "256"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["text"] == "hello world"
        assert data["task"] == "text"
        assert data["filename"] == "sample.png"


@pytest.mark.asyncio
async def test_ocr_glm_pdf_success_with_mocked_service(app, monkeypatch):
    import backend.main as backend_main
    from backend.glm_ocr import OCRResult

    def fake_run(request):
        assert request.image_path.suffix.lower() == ".pdf"
        assert request.max_pages == 4
        return OCRResult(
            text="[Page 1]\nPDF text",
            model="zai-org/GLM-OCR",
            task="text",
            prompt="Text Recognition:",
            device="cpu",
            elapsed_seconds=0.9,
        )

    monkeypatch.setattr(backend_main.ocr_service, "run", fake_run)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/ocr/glm",
            files={"file": ("sample.pdf", b"%PDF-1.7\n", "application/pdf")},
            data={"task": "text", "max_pages": "4"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "PDF text" in data["text"]
        assert data["filename"] == "sample.pdf"


@pytest.mark.asyncio
async def test_ocr_async_job_progress_and_result(app, monkeypatch):
    import backend.main as backend_main
    from backend.glm_ocr import OCRResult

    def fake_run_with_progress(request, progress_callback=None):
        if progress_callback:
            progress_callback(
                {
                    "type": "progress",
                    "progress": 25,
                    "message": "Rendered page 1/2",
                    "current_page": 1,
                    "total_pages": 2,
                }
            )
            progress_callback(
                {
                    "type": "progress",
                    "progress": 75,
                    "message": "Completed page 2/2",
                    "current_page": 2,
                    "total_pages": 2,
                }
            )
        return OCRResult(
            text="[Page 1]\nhello\n\n[Page 2]\nworld",
            model="zai-org/GLM-OCR",
            task="text",
            prompt="Text Recognition:",
            device="cpu",
            elapsed_seconds=0.5,
        )

    monkeypatch.setattr(
        backend_main.ocr_service, "run_with_progress", fake_run_with_progress
    )

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        start_resp = await client.post(
            "/ocr/glm/start",
            files={"file": ("sample.pdf", b"%PDF-1.7\n", "application/pdf")},
            data={"task": "text", "max_pages": "2"},
        )
        assert start_resp.status_code == 200
        job_id = start_resp.json()["job_id"]

        final = None
        for _ in range(10):
            status_resp = await client.get(f"/ocr/jobs/{job_id}")
            assert status_resp.status_code == 200
            payload = status_resp.json()
            if payload["status"] in {"succeeded", "failed"}:
                final = payload
                break

        assert final is not None
        assert final["status"] == "succeeded"
        assert final["progress"] == 100.0
        assert "world" in (final.get("result_text") or "")
