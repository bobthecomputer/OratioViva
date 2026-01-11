from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Dict, List, Optional


@dataclass
class JobStatus:
    job_id: str
    status: str
    created_at: datetime
    updated_at: datetime
    audio_url: Optional[str] = None
    duration_seconds: Optional[float] = None
    model: Optional[str] = None
    voice_id: Optional[str] = None
    source: Optional[str] = None
    error: Optional[str] = None


class JobStore:
    def __init__(self, path: Optional[Path] = None, max_items: int = 200) -> None:
        self._jobs: Dict[str, JobStatus] = {}
        self._lock = Lock()
        self.path = path
        self.max_items = max_items
        self._load()

    def create(self, job_id: str, status: str = "queued") -> JobStatus:
        now = datetime.now(timezone.utc)
        job = JobStatus(job_id=job_id, status=status, created_at=now, updated_at=now)
        with self._lock:
            self._jobs[job_id] = job
            self._save()
        return job

    def update(self, job_id: str, **fields) -> JobStatus:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise KeyError(f"Unknown job_id: {job_id}")
            data = job.__dict__.copy()
            data.update(fields)
            data["updated_at"] = datetime.now(timezone.utc)
            job = JobStatus(**data)
            self._jobs[job_id] = job
            self._save()
            return job

    def get(self, job_id: str) -> Optional[JobStatus]:
        with self._lock:
            return self._jobs.get(job_id)

    def list(self, limit: int = 50) -> List[JobStatus]:
        with self._lock:
            jobs = sorted(self._jobs.values(), key=lambda j: j.updated_at, reverse=True)
            return jobs[:limit]

    def _load(self) -> None:
        if not self.path or not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return
        for item in data:
            job = self._deserialize(item)
            if job:
                self._jobs[job.job_id] = job

    def delete(self, job_id: str) -> bool:
        with self._lock:
            if job_id not in self._jobs:
                return False
            self._jobs.pop(job_id, None)
            self._save()
            return True

    def _save(self) -> None:
        if not self.path:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        jobs = sorted(self._jobs.values(), key=lambda j: j.updated_at, reverse=True)
        jobs = jobs[: self.max_items]
        payload = [self._serialize(job) for job in jobs]
        self.path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    @staticmethod
    def _serialize(job: JobStatus) -> dict:
        data = job.__dict__.copy()
        data["created_at"] = job.created_at.isoformat()
        data["updated_at"] = job.updated_at.isoformat()
        return data

    @staticmethod
    def _deserialize(data: dict) -> Optional[JobStatus]:
        try:
            created = datetime.fromisoformat(data["created_at"])
            updated = datetime.fromisoformat(data["updated_at"])
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            if updated.tzinfo is None:
                updated = updated.replace(tzinfo=timezone.utc)
            return JobStatus(
                job_id=data["job_id"],
                status=data["status"],
                created_at=created,
                updated_at=updated,
                audio_url=data.get("audio_url"),
                duration_seconds=data.get("duration_seconds"),
                model=data.get("model"),
                voice_id=data.get("voice_id"),
                source=data.get("source"),
                error=data.get("error"),
            )
        except Exception:
            return None
