"""Content-hash deterministic cache for vision-extraction outputs.

The cache is keyed by SHA-256 of (file_content, prompt_version, schema_version,
model_name). A hit returns the cached JSON directly without an LLM call. A miss
runs the extractor (caller's responsibility) and the result is stored via put().

Cache storage: ``ehi-atlas/ehi_atlas/extract/.cache/<hash>.json``. Gitignored.

Typical caller flow::

    from ehi_atlas.extract.cache import ExtractionCache, CacheKey, hash_file

    cache = ExtractionCache()
    key = CacheKey(
        file_sha256=hash_file(pdf_path),
        prompt_version="v0.1.0",
        schema_version="extraction-result-v0.1.0",
        model_name="claude-opus-4-7",
    )

    cached = cache.get(key)
    if cached is not None:
        return ExtractionResult.model_validate(cached)

    # ... otherwise call the LLM and:
    result_dict = call_claude_vision(pdf_path, prompt)
    cache.put(key, result_dict)
    return ExtractionResult.model_validate(result_dict)

Design notes:

- **Determinism guarantee**: the cache key covers every input that can influence
  the extraction output (PDF bytes, prompt version, schema version, model name).
  Bumping any of these fields automatically invalidates old entries — old hashes
  are simply never queried.
- **Write-once semantics**: entries are never mutated; ``put()`` uses an atomic
  rename to avoid partial reads from concurrent processes.
- **No TTL / LRU in Phase 1**: cleanup is manual via ``make clean`` or
  :py:meth:`ExtractionCache.clear_all`. Add eviction in Phase 2 if cache grows
  large.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Default cache location (relative to this module — extract/.cache/)
_DEFAULT_CACHE_DIR = Path(__file__).resolve().parent / ".cache"


@dataclass(frozen=True)
class CacheKey:
    """Inputs that determine cache identity.

    All four fields contribute to the SHA-256 digest used as the cache filename.
    Changing any field yields a different key, so old entries are automatically
    bypassed without explicit invalidation.
    """

    file_sha256: str   # SHA-256 hex of the source PDF bytes
    prompt_version: str  # e.g. "v0.1.0"
    schema_version: str  # e.g. "extraction-result-v0.1.0" or Pydantic-derived
    model_name: str      # e.g. "claude-opus-4-7"

    def digest(self) -> str:
        """Return the hex digest used as the cache filename (without extension)."""
        h = hashlib.sha256()
        h.update(self.file_sha256.encode("utf-8"))
        h.update(b"\n")
        h.update(self.prompt_version.encode("utf-8"))
        h.update(b"\n")
        h.update(self.schema_version.encode("utf-8"))
        h.update(b"\n")
        h.update(self.model_name.encode("utf-8"))
        return h.hexdigest()


class ExtractionCache:
    """File-based content-hash cache for vision-extraction outputs.

    Each cache entry is a single ``.json`` file named by the SHA-256 digest of
    its :class:`CacheKey`.  The cache directory is created on first use.
    """

    def __init__(self, cache_dir: Path | None = None) -> None:
        self.cache_dir = Path(cache_dir) if cache_dir else _DEFAULT_CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _path_for(self, key: CacheKey) -> Path:
        """Return the filesystem path for the given key (may not exist)."""
        return self.cache_dir / f"{key.digest()}.json"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, key: CacheKey) -> dict[str, Any] | None:
        """Return the cached extraction dict, or ``None`` on a miss.

        A corrupt or unreadable file is treated as a miss (returns ``None``)
        so a subsequent ``put()`` can overwrite it cleanly.
        """
        p = self._path_for(key)
        if not p.exists():
            return None
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

    def put(self, key: CacheKey, value: dict[str, Any]) -> Path:
        """Store *value* under *key*.  Returns the path of the written file.

        The write is atomic (write to ``.tmp`` then rename) so concurrent
        readers never see a partial file.
        """
        p = self._path_for(key)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(value, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        tmp.replace(p)
        return p

    def has(self, key: CacheKey) -> bool:
        """Return ``True`` if an entry exists for *key*."""
        return self._path_for(key).exists()

    def invalidate(self, key: CacheKey) -> bool:
        """Remove the cache entry for *key*.

        Returns ``True`` if an entry was deleted, ``False`` if it was absent.
        """
        p = self._path_for(key)
        if p.exists():
            p.unlink()
            return True
        return False

    def clear_all(self) -> int:
        """Remove every ``.json`` entry from the cache directory.

        Returns the count of entries removed.  Used by ``make clean``.
        """
        count = 0
        for f in self.cache_dir.glob("*.json"):
            f.unlink()
            count += 1
        return count


# ---------------------------------------------------------------------------
# Convenience utilities
# ---------------------------------------------------------------------------


def hash_file(path: Path) -> str:
    """Return the SHA-256 hex digest of *path*'s contents.

    Reads in 8 KiB chunks so large PDFs don't exhaust memory.  Callers use
    this to populate :attr:`CacheKey.file_sha256`.
    """
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()
