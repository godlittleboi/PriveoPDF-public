from __future__ import annotations

from pathlib import Path

from pdfmod.ui.page_contracts import BusyDocumentProvider


class BusyDocumentRegistry:
    """Public read model for documents currently used by a running page job."""

    def __init__(self) -> None:
        self._providers: list[BusyDocumentProvider] = []

    def register(self, provider: BusyDocumentProvider) -> None:
        if any(candidate is provider for candidate in self._providers):
            return
        self._providers.append(provider)

    def unregister(self, provider: BusyDocumentProvider) -> None:
        self._providers = [candidate for candidate in self._providers if candidate is not provider]

    def busy_paths(self) -> tuple[Path, ...]:
        paths: list[Path] = []
        seen: set[Path] = set()
        for provider in self._providers:
            for path in provider.busy_document_paths():
                resolved = Path(path).resolve(strict=False)
                if resolved in seen:
                    continue
                seen.add(resolved)
                paths.append(Path(path))
        return tuple(paths)

    def is_busy(self, path: Path) -> bool:
        resolved = Path(path).resolve(strict=False)
        return any(candidate.resolve(strict=False) == resolved for candidate in self.busy_paths())


__all__ = ["BusyDocumentRegistry"]
