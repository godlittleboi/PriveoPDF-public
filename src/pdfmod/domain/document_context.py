from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

DocumentSourceKind = Literal["launcher", "workspace", "generated", "drop", "manual"]
ToolLaunchSource = Literal["document_workspace", "workspace_sidebar", "dashboard", "manual"]


@dataclass(frozen=True)
class DocumentContext:
    source_path: Path
    display_name: str
    source_kind: DocumentSourceKind
    last_output_path: Path | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.source_path, Path):
            raise TypeError("source_path must be a Path")
        if not isinstance(self.display_name, str) or not self.display_name.strip():
            raise ValueError("display_name must be a non-empty string")
        if self.last_output_path is not None and not isinstance(self.last_output_path, Path):
            raise TypeError("last_output_path must be a Path or None")


@dataclass(frozen=True)
class ToolLaunchContext:
    input_files: tuple[Path, ...]
    active_document: DocumentContext | None
    source: ToolLaunchSource
    return_to_document: bool
    suggested_output_dir: Path | None = None
    suggested_output_basename: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.input_files, tuple):
            raise TypeError("input_files must be a tuple of Path")
        if not all(isinstance(path, Path) for path in self.input_files):
            raise TypeError("input_files must contain only Path values")
        if self.suggested_output_dir is not None and not isinstance(
            self.suggested_output_dir, Path
        ):
            raise TypeError("suggested_output_dir must be a Path or None")
        if self.suggested_output_basename is not None and (
            not isinstance(self.suggested_output_basename, str)
            or not self.suggested_output_basename.strip()
        ):
            raise ValueError("suggested_output_basename must be a non-empty string or None")
