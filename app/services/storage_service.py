from __future__ import annotations

from pathlib import Path

from app.settings import get_settings


class StorageService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.root = self.settings.local_storage_root
        self.root.mkdir(parents=True, exist_ok=True)

    def write_text(self, task_id: str, relative_path: str, content: str) -> str:
        path = self._task_path(task_id, relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return str(path)

    def write_bytes(self, task_id: str, relative_path: str, content: bytes) -> str:
        path = self._task_path(task_id, relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return str(path)

    def _task_path(self, task_id: str, relative_path: str) -> Path:
        safe_relative_path = relative_path.lstrip("/")
        return self.root / "tasks" / task_id / safe_relative_path
