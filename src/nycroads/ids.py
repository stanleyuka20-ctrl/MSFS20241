"""Stable identifiers.

IDs are derived deterministically from OSM identity (way id + bounding node ids),
so the same input always yields the same IDs. A persisted registry additionally
lets an ID survive upstream OSM edits that split or renumber ways: a new key
inherits the ID of a key that disappeared in this import when both span the same
node pair (same physical piece of road).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


def short_hash(text: str, n: int = 10) -> str:
    return hashlib.sha1(text.encode()).hexdigest()[:n]


class IdRegistry:
    def __init__(self, path: Path | None = None):
        self.path = path
        # key -> {"id", "match", "kind", "retired", ["superseded_by"]}
        self.entries: dict[str, dict] = {}
        if path and path.exists():
            self.entries = json.loads(path.read_text())

    def assign_batch(self, kind: str, prefix: str, items: list[tuple[str, str]]) -> dict[str, str]:
        """Assign IDs for one full import of ``kind``.

        ``items`` is a list of (key, match) pairs. Keys of this kind that are absent
        from the batch are retired; a new key whose ``match`` equals a vanished
        key's ``match`` inherits that ID.
        """
        current = {k for k, _ in items}
        vanished = {e["match"]: k for k, e in self.entries.items()
                    if e["kind"] == kind and k not in current and "superseded_by" not in e}
        used_ids = {e["id"] for k, e in self.entries.items() if k in current}
        out = {}
        for key, match in items:
            e = self.entries.get(key)
            if e is not None:
                e["retired"] = False
                out[key] = e["id"]
                continue
            old_key = vanished.pop(match, None)
            if old_key is not None and self.entries[old_key]["id"] not in used_ids:
                ident = self.entries[old_key]["id"]
                self.entries[old_key]["superseded_by"] = key
            else:
                ident = f"{prefix}-{short_hash(key)}"
            used_ids.add(ident)
            self.entries[key] = {"id": ident, "match": match, "kind": kind, "retired": False}
            out[key] = ident
        for k, e in self.entries.items():
            if e["kind"] == kind and k not in current:
                e["retired"] = True
        return out

    def save(self) -> None:
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self.entries, indent=1, sort_keys=True))
