from __future__ import annotations

from dataclasses import dataclass, field

CATEGORIES = (
    "comments",
    "links",
    "widgets",
    "attachments",
    "forms",
    "internal_navigation",
    "external_references",
    "active_actions",
    "unknown_actions",
    "signatures",
    "empty_signatures",
)
COMMON_INFO = (
    "Title",
    "Author",
    "Subject",
    "Keywords",
    "Creator",
    "Producer",
    "CreationDate",
    "ModDate",
)
STATES = {"absent", "present", "unreadable", "limited", "not_analyzed"}


@dataclass(frozen=True, repr=False)
class MetadataProperty:
    origin: str
    name: str
    value: str
    truncated: bool = False


@dataclass(frozen=True, repr=False)
class ShareInspection:
    page_count: int | None = None
    size_bytes: int = 0
    encrypted: bool = False
    info_state: str = "not_analyzed"
    xmp_state: str = "not_analyzed"
    properties: tuple[MetadataProperty, ...] = field(default=(), repr=False)
    counts: tuple[int, ...] = (0,) * len(CATEGORIES)
    complete: bool = False
    warnings: tuple[str, ...] = ()

    def count(self, category: str) -> int:
        return self.counts[CATEGORIES.index(category)]
