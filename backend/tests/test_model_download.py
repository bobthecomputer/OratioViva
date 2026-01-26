import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))


class DummyDownloadError(RuntimeError):
    pass


def test_download_reraises_original_error(monkeypatch, tmp_path):
    try:
        import huggingface_hub  # noqa: F401
    except ModuleNotFoundError:
        stub = types.ModuleType("huggingface_hub")
        stub.hf_hub_download = lambda *args, **kwargs: None
        stub.snapshot_download = lambda *args, **kwargs: None
        sys.modules["huggingface_hub"] = stub

    from backend import models

    def fake_snapshot_download(*args, **kwargs):
        raise DummyDownloadError("401 unauthorized")

    monkeypatch.setattr(models, "snapshot_download", fake_snapshot_download)

    manager = models.ModelManager(
        base_dir=tmp_path,
        models_dir=tmp_path / "models",
        token=None,
        optional_models=None,
        extra_dirs=None,
    )
    manager._download_progress = {}

    target = tmp_path / "models" / "FlashLabs_Chroma-4B"
    target.mkdir(parents=True, exist_ok=True)

    with pytest.raises(DummyDownloadError) as excinfo:
        manager._try_download_with_fallback(
            "FlashLabs/Chroma-4B", target, "chroma_4b"
        )

    assert "401 unauthorized" in str(excinfo.value)
