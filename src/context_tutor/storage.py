from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


class JsonlStore:
    """Tiny append-only store. No database dependency, easy to diff in git."""

    FILES = {
        "sources": "sources.jsonl",
        "sentences": "sentences.jsonl",
        "contexts": "context_cards.jsonl",
    }

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        for filename in self.FILES.values():
            (self.root / filename).touch(exist_ok=True)

    def path(self, kind: str) -> Path:
        if kind not in self.FILES:
            raise ValueError(f"unknown record kind: {kind}")
        return self.root / self.FILES[kind]

    def read(self, kind: str) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        with self.path(kind).open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
        return records

    def append(self, kind: str, record: dict[str, Any]) -> bool:
        """Append unless a record with the same id already exists."""
        if self.exists(kind, str(record.get("id", ""))):
            return False
        with self.path(kind).open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        return True

    def exists(self, kind: str, record_id: str) -> bool:
        if not record_id:
            return False
        return any(record.get("id") == record_id for record in self.read(kind))

    def find(self, kind: str, **filters: Any) -> list[dict[str, Any]]:
        return [
            record
            for record in self.read(kind)
            if all(record.get(key) == value for key, value in filters.items())
        ]

    def update(self, kind: str, record_id: str, **changes: Any) -> bool:
        """Replace one record atomically. Append-only is kept for inserts only."""
        records = self.read(kind)
        found = False
        for record in records:
            if record.get("id") == record_id:
                record.update(changes)
                found = True
                break
        if not found:
            return False
        temp_path = self.path(kind).with_suffix(".tmp")
        with temp_path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        os.replace(temp_path, self.path(kind))
        return True

    def count(self, kind: str) -> int:
        return len(self.read(kind))
