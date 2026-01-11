import importlib
import os
import sys
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))


@pytest.fixture(scope="session")
def app():
    os.environ["ORATIO_TTS_STUB"] = "1"
    # Reload to apply stub env if already imported.
    import backend.main as backend_main

    importlib.reload(backend_main)
    return backend_main.app


@pytest.mark.asyncio
async def test_health(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "voices" in data


@pytest.mark.asyncio
async def test_voices_and_synthesize(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        voices_resp = await client.get("/voices")
        assert voices_resp.status_code == 200
        voices = voices_resp.json()["voices"]
        assert voices, "Expected at least one voice preset"

        voice_id = voices[0]["id"]
        synth_resp = await client.post(
            "/synthesize?async_mode=false",
            json={"text": "Bonjour le monde", "voice_id": voice_id, "speed": 1.0},
        )
        assert synth_resp.status_code == 200
        job = synth_resp.json()
        assert job["status"] == "succeeded"
        assert job["audio_url"].startswith("/audio/")
