from __future__ import annotations

import stat
import threading
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path

from pdfmod.engine.document_inspection import DocumentInspection

DEFAULT_METADATA_CACHE_ENTRIES = 128


@dataclass(frozen=True, slots=True)
class LocalFileFingerprint:
    """Ephemeral identity for one local file version; it is never persisted."""

    device: int
    inode: int
    size: int
    mtime_ns: int


@dataclass(frozen=True, slots=True)
class CachedDocumentMetadata:
    inspection: DocumentInspection | None = None
    page_count: int | None = None


def local_file_fingerprint(path: Path) -> LocalFileFingerprint | None:
    """Return a path-free fingerprint, or ``None`` when the file cannot be stated."""

    try:
        file_stat = Path(path).stat()
    except (OSError, ValueError):
        return None
    if not stat.S_ISREG(file_stat.st_mode):
        return None
    return LocalFileFingerprint(
        device=int(file_stat.st_dev),
        inode=int(file_stat.st_ino),
        size=int(file_stat.st_size),
        mtime_ns=int(file_stat.st_mtime_ns),
    )


class DocumentMetadataCache:
    """Thread-safe bounded LRU for local inspection and page-count results."""

    def __init__(self, max_entries: int = DEFAULT_METADATA_CACHE_ENTRIES) -> None:
        if not isinstance(max_entries, int) or isinstance(max_entries, bool) or max_entries < 1:
            raise ValueError("max_entries must be a positive integer")
        self._max_entries = max_entries
        self._entries: OrderedDict[LocalFileFingerprint, CachedDocumentMetadata] = OrderedDict()
        self._lock = threading.RLock()

    @property
    def max_entries(self) -> int:
        return self._max_entries

    def fingerprint(self, path: Path) -> LocalFileFingerprint | None:
        return local_file_fingerprint(path)

    def lookup(self, fingerprint: LocalFileFingerprint) -> CachedDocumentMetadata | None:
        with self._lock:
            metadata = self._entries.get(fingerprint)
            if metadata is not None:
                self._entries.move_to_end(fingerprint)
            return metadata

    def store_inspection(
        self,
        fingerprint: LocalFileFingerprint,
        inspection: DocumentInspection,
    ) -> None:
        with self._lock:
            previous = self._entries.get(fingerprint)
            page_count = inspection.page_count
            if page_count is None and previous is not None:
                page_count = previous.page_count
            self._store_locked(
                fingerprint,
                CachedDocumentMetadata(inspection=inspection, page_count=page_count),
            )

    def store_page_count(
        self,
        fingerprint: LocalFileFingerprint,
        page_count: int,
    ) -> None:
        if not isinstance(page_count, int) or isinstance(page_count, bool) or page_count < 0:
            raise ValueError("page_count must be a non-negative integer")
        with self._lock:
            previous = self._entries.get(fingerprint)
            inspection = None if previous is None else previous.inspection
            self._store_locked(
                fingerprint,
                CachedDocumentMetadata(inspection=inspection, page_count=page_count),
            )

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._entries)

    def _store_locked(
        self,
        fingerprint: LocalFileFingerprint,
        metadata: CachedDocumentMetadata,
    ) -> None:
        self._entries[fingerprint] = metadata
        self._entries.move_to_end(fingerprint)
        while len(self._entries) > self._max_entries:
            self._entries.popitem(last=False)


SHARED_DOCUMENT_METADATA_CACHE = DocumentMetadataCache()
