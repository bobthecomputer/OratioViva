from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List


def cleanup_outputs(
    audio_dir: Path,
    history_path: Path,
    *,
    max_age_hours: int = 48,
    max_history: int = 200,
) -> Dict[str, int]:
    """Remove old audio files and trim history."""
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=max_age_hours)

    removed_files = 0
    removed_history = 0

    if audio_dir.exists():
        for wav in audio_dir.glob("*.wav"):
            mtime = datetime.fromtimestamp(wav.stat().st_mtime, tz=timezone.utc)
            if mtime < cutoff:
                try:
                    wav.unlink()
                    removed_files += 1
                except OSError:
                    continue

    history: List[dict] = []
    if history_path.exists():
        try:
            history = json.loads(history_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            history = []

    filtered = []
    for entry in history:
        audio_path = entry.get("audio_path")
        if audio_path and not Path(audio_path).exists():
            removed_history += 1
            continue
        created_at = entry.get("created_at")
        try:
            dt = datetime.fromisoformat(created_at)
        except Exception:
            dt = now
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        if dt < cutoff:
            removed_history += 1
            continue
        filtered.append(entry)

    if len(filtered) > max_history:
        removed_history += len(filtered) - max_history
        filtered = filtered[:max_history]

    history_path.parent.mkdir(parents=True, exist_ok=True)
    history_path.write_text(json.dumps(filtered, indent=2, ensure_ascii=False), encoding="utf-8")

    return {
        "removed_files": removed_files,
        "removed_history": removed_history,
        "remaining_history": len(filtered),
    }


def run_from_env(audio_dir: Path, history_path: Path) -> Dict[str, int]:
    """Convenience runner using environment variables to override defaults."""
    max_age_hours = int(os.getenv("ORATIO_CLEAN_MAX_HOURS", "48"))
    max_history = int(os.getenv("ORATIO_CLEAN_MAX_HISTORY", "200"))
    return cleanup_outputs(
        audio_dir=audio_dir,
        history_path=history_path,
        max_age_hours=max_age_hours,
        max_history=max_history,
    )
