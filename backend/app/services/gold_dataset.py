"""Чтение и редактирование gold dataset (per-stage эталоны)."""
from __future__ import annotations

import asyncio
import json
import uuid
from pathlib import Path
from typing import Iterable

VALID_STAGES = ("cold", "warm", "hot", "after_sale")

_lock = asyncio.Lock()


def _atomic_write(path: Path, data: list[dict]) -> None:
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    tmp.replace(path)


def load(path: str | Path) -> list[dict]:
    p = Path(path)
    if not p.exists():
        return []
    raw = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        return []
    return [
        e for e in raw
        if isinstance(e, dict) and e.get("stage") in VALID_STAGES and e.get("reference")
    ]


async def list_entries(path: str | Path) -> list[dict]:
    async with _lock:
        return load(path)


async def add_entry(path: str | Path, stage: str, reference: str) -> dict:
    if stage not in VALID_STAGES:
        raise ValueError(f"invalid stage: {stage}")
    if not reference.strip():
        raise ValueError("reference must not be empty")
    async with _lock:
        entries = load(path)
        new_entry = {
            "id": f"{stage}-{uuid.uuid4().hex[:8]}",
            "stage": stage,
            "reference": reference.strip(),
        }
        entries.append(new_entry)
        _atomic_write(Path(path), entries)
        return new_entry


async def update_entry(
    path: str | Path,
    entry_id: str,
    *,
    stage: str | None = None,
    reference: str | None = None,
) -> dict:
    async with _lock:
        entries = load(path)
        for e in entries:
            if e["id"] == entry_id:
                if stage is not None:
                    if stage not in VALID_STAGES:
                        raise ValueError(f"invalid stage: {stage}")
                    e["stage"] = stage
                if reference is not None:
                    if not reference.strip():
                        raise ValueError("reference must not be empty")
                    e["reference"] = reference.strip()
                _atomic_write(Path(path), entries)
                return e
        raise KeyError(entry_id)


async def delete_entry(path: str | Path, entry_id: str) -> None:
    async with _lock:
        entries = load(path)
        new_entries = [e for e in entries if e["id"] != entry_id]
        if len(new_entries) == len(entries):
            raise KeyError(entry_id)
        _atomic_write(Path(path), new_entries)


def filter_by_stages(entries: Iterable[dict], stages: Iterable[str] | None) -> list[dict]:
    if not stages:
        return list(entries)
    s = set(stages)
    return [e for e in entries if e["stage"] in s]
