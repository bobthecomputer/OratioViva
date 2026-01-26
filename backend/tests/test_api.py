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
async def test_health(app):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "voices" in data


@pytest.mark.asyncio
async def test_voices_and_synthesize(app):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
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


@pytest.mark.asyncio
async def test_presets(app):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/presets")
        assert resp.status_code == 200
        data = resp.json()
        assert "tones" in data
        assert "prompts" in data
        assert "defaults" in data
        assert len(data["tones"]) > 0, "Expected at least one tone preset"
        assert len(data["prompts"]) > 0, "Expected at least one prompt preset"


@pytest.mark.asyncio
async def test_presets_tone_crud(app):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        test_preset = {
            "id": "test_tone",
            "name": "Test Tone",
            "description": "A test tone preset",
            "style": "Test style description",
            "voice_prompt": "Test voice prompt",
        }
        save_resp = await client.post("/presets/tones", json=test_preset)
        assert save_resp.status_code == 200

        list_resp = await client.get("/presets")
        assert list_resp.status_code == 200
        tones = list_resp.json()["tones"]
        test_tone = next((t for t in tones if t["id"] == "test_tone"), None)
        assert test_tone is not None, "Test tone should be in list"
        assert test_tone["is_custom"] == True

        delete_resp = await client.delete("/presets/tones/test_tone")
        assert delete_resp.status_code == 200


@pytest.mark.asyncio
async def test_presets_prompt_crud(app):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        test_preset = {
            "id": "test_prompt",
            "name": "Test Prompt",
            "description": "A test voice direction preset",
            "voice_prompt": "Warm and confident delivery",
        }
        save_resp = await client.post("/presets/prompts", json=test_preset)
        assert save_resp.status_code == 200

        delete_resp = await client.delete("/presets/prompts/test_prompt")
        assert delete_resp.status_code == 200


@pytest.mark.asyncio
async def test_diagnostics(app):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/diagnostics")
        assert resp.status_code == 200
        data = resp.json()
        assert "backend" in data
        assert "storage" in data
        assert "settings" in data
        assert "models" in data
        assert "platform" in data["backend"]
        assert "python" in data["backend"]


@pytest.mark.asyncio
async def test_telemetry_settings(app):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        get_resp = await client.get("/settings/telemetry")
        assert get_resp.status_code == 200
        data = get_resp.json()
        assert "crash_reports" in data

        set_resp = await client.post(
            "/settings/telemetry", json={"crash_reports": True}
        )
        assert set_resp.status_code == 200
        assert set_resp.json()["crash_reports"] == True

        set_resp2 = await client.post(
            "/settings/telemetry", json={"crash_reports": False}
        )
        assert set_resp2.status_code == 200
        assert set_resp2.json()["crash_reports"] == False


@pytest.mark.asyncio
async def test_model_capabilities(app):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/presets/model-capabilities?model_name=parler-tts")
        assert resp.status_code == 200
        data = resp.json()
        assert "capabilities" in data
        caps = data["capabilities"]
        assert "style" in caps
        assert "voice_prompt" in caps
        assert "voice_ref" in caps


@pytest.mark.asyncio
async def test_cleanup_endpoint(app):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post("/maintenance/cleanup", json={"delete_audio": True})
        assert resp.status_code == 200
        data = resp.json()
        assert "deleted" in data
        assert "audio_files" in data["deleted"]


@pytest.mark.asyncio
async def test_synthesize_with_presets(app):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        voices_resp = await client.get("/voices")
        voice_id = voices_resp.json()["voices"][0]["id"]

        synth_resp = await client.post(
            "/synthesize?async_mode=false",
            json={
                "text": "Test with tone preset",
                "voice_id": voice_id,
                "speed": 1.0,
                "tone_id": "neutral",
                "prompt_id": "default",
            },
        )
        assert synth_resp.status_code == 200
        job = synth_resp.json()
        assert job["status"] == "succeeded"
