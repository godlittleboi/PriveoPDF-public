from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import platform
import random
import re
import shlex
import shutil
import signal
import subprocess
import time
import traceback
import uuid
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass, is_dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from types import FrameType
from typing import Any

import pikepdf

try:
    import resource
except ImportError:  # pragma: no cover - resource is POSIX-only.
    resource = None

from pdfmod.domain.jobs import JobRequest, JobResult, OperationType
from pdfmod.engine.pdf_structural import run_structural_job
from pdfmod.quality.pdf_oracles import OracleStatus, validate_structural_outputs
from pdfmod.ui.tool_specs import TOOL_SPECS, ToolSpec

DEFAULT_SEED = 42
DEFAULT_MAX_FILE_SIZE_MB = 50
VIEWER_SMOKE_LIMIT = 20
HASH_CHUNK_SIZE = 1024 * 1024
SHORT_HASH_LENGTH = 12
EXPECTED_TECHNICAL_DETAILS = {
    "encrypted_pdf",
    "invalid_pdf",
    "unsupported_pdf_feature",
    "wrong_password",
}
STRUCTURAL_TOOL_ORDER = (
    "merge",
    "split",
    "remove",
    "extract",
    "reorder",
    "insert",
    "blank_page",
    "rotate",
)
SOURCE_BUCKETS = (
    "manual_safe",
    "pdf.js",
    "qpdf",
    "veraPDF-corpus",
    "techniques-for-accessible-pdf",
)
BUG_STATUSES = {"BUG", "BUG_CRITICAL"}
TRIAGE_STATUSES = {"NEEDS_TRIAGE", "BUG", "BUG_CRITICAL"}


class PdfClassificationStatus(StrEnum):
    VALID = "VALID"
    VALID_LARGE = "VALID_LARGE"
    ENCRYPTED = "ENCRYPTED"
    INVALID = "INVALID"
    UNSUPPORTED = "UNSUPPORTED"
    EMPTY = "EMPTY"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"


class CorpusTestStatus(StrEnum):
    OK = "OK"
    SKIPPED = "SKIPPED"
    INVALID_INPUT = "INVALID_INPUT"
    UNSUPPORTED_INPUT = "UNSUPPORTED_INPUT"
    EXPECTED_FAILURE = "EXPECTED_FAILURE"
    NEEDS_TRIAGE = "NEEDS_TRIAGE"
    BUG = "BUG"
    BUG_CRITICAL = "BUG_CRITICAL"


class CorpusTimeoutError(TimeoutError):
    """Raised by the best-effort POSIX timeout guard."""


@dataclass(frozen=True)
class CorpusRunOptions:
    corpus: Path
    max_files: int | None = None
    sample: int | None = None
    seed: int = DEFAULT_SEED
    full: bool = False
    exclude: tuple[str, ...] = ()
    tools: tuple[str, ...] = ()
    only_file: str | None = None
    include_viewer_smoke: bool = False
    transform_visual_oracle: bool = True
    fail_on_bug: bool = False
    fail_on_critical: bool = False
    fail_on_any_failure: bool = False
    timeout_sec: int | None = None
    max_file_size_mb: int = DEFAULT_MAX_FILE_SIZE_MB
    include_large: bool = False
    reports_root: Path = Path("reports/corpus")
    keep_outputs: bool = False
    quiet: bool = False
    command: tuple[str, ...] = ()


@dataclass(frozen=True)
class FileFingerprint:
    exists: bool
    size_bytes: int
    sha256: str
    short_hash: str


@dataclass(frozen=True)
class PdfCandidate:
    path: Path
    rel_path: str
    size_bytes: int
    sha256: str
    short_hash: str
    source_bucket: str


@dataclass(frozen=True)
class PdfClassification:
    status: PdfClassificationStatus
    page_count: int | None = None
    technical_detail: str = ""
    exception_type: str = ""
    note: str = ""


@dataclass(frozen=True)
class ToolSelection:
    tested_operation_specs: tuple[ToolSpec, ...]
    viewer_spec: ToolSpec | None
    available_not_testable: tuple[str, ...]
    pending_not_tested: tuple[str, ...]
    requested_unknown: tuple[str, ...]


@dataclass
class CorpusToolResult:
    tool_id: str
    operation_type: str
    input_files: tuple[str, ...]
    source_classification: str
    status: CorpusTestStatus
    triage: str
    duration_ms: int
    output_paths: tuple[str, ...] = ()
    output_exists: bool = False
    output_size_bytes: tuple[int, ...] = ()
    output_openable: bool | None = None
    source_hash_before: str = ""
    source_hash_after: str = ""
    source_unchanged: bool = True
    exception_type: str = ""
    exception_message_short: str = ""
    technical_detail: str = ""
    trace_short: str = ""
    notes: str = ""
    scenario_id: str = ""
    reproduction_command: str = ""
    source_rel_path: str = ""
    source_short_hash: str = ""
    source_bucket: str = "unknown"
    page_count: int | None = None
    source_size_bytes: int = 0
    semantic_oracle_status: str = OracleStatus.NOT_APPLICABLE.value
    visual_oracle_status: str = OracleStatus.NOT_APPLICABLE.value
    oracle_pages_checked: int = 0
    visual_pages_checked: int = 0
    text_pages_checked: int = 0
    visual_pages_skipped: int = 0
    visual_max_normalized_mae: float = 0.0
    visual_max_changed_fraction: float = 0.0
    oracle_failure_code: str = ""
    oracle_failure_detail: str = ""


@dataclass(frozen=True)
class CorpusRecommendation:
    priority: str
    tool_id: str
    symptom: str
    affected_files: int
    dominant_source: str
    dominant_exception: str
    probable_code_area: str
    reproduction_command: str


@dataclass
class CorpusRunReport:
    timestamp: str
    command: str
    options: dict[str, Any]
    python_version: str
    platform: str
    pikepdf_version: str
    pyside6_version: str | None
    git_commit: str | None
    git_branch: str | None
    repo_dirty: bool | None
    corpus_path: str
    corpus_root_name: str
    pdf_detected_count: int
    pdf_selected_count: int
    pdf_tested_count: int
    classifications: dict[str, int]
    tool_stats: dict[str, dict[str, int]]
    source_stats: dict[str, dict[str, int]]
    duration_total_ms: int
    duration_by_tool_ms: dict[str, int]
    files_per_second: float
    memory_metrics_available: bool
    max_rss_kb: int | None
    timeout_available: bool
    timeout_sec: int | None
    top_slowest_files: list[dict[str, Any]]
    top_error_signatures: list[dict[str, Any]]
    results: list[CorpusToolResult]
    bugs_probable: list[CorpusToolResult]
    bugs_critical: list[CorpusToolResult]
    problem_files: list[dict[str, Any]]
    tested_tools: list[str]
    scenario_ids_by_tool: dict[str, list[str]]
    available_not_testable: list[str]
    pending_not_tested: list[str]
    viewer_smoke_not_available: str
    recommendations: list[CorpusRecommendation]
    run_dir: str


@dataclass(frozen=True)
class ToolCase:
    tool_id: str
    operation: OperationType
    input_files: tuple[Path, ...]
    output_dir: Path
    options: dict[str, Any]
    output_paths_expected: tuple[Path, ...]
    output_name_suffix: str
    note: str = ""
    scenario_id: str = ""


def available_operation_tool_ids() -> frozenset[str]:
    return frozenset(
        spec.key
        for spec in TOOL_SPECS
        if spec.status == "available"
        and spec.view_kind == "operation"
        and spec.operation is not None
    )


def missing_corpus_scenario_tool_ids() -> frozenset[str]:
    return available_operation_tool_ids() - frozenset(STRUCTURAL_TOOL_ORDER)


def discover_pdfs(options: CorpusRunOptions) -> list[PdfCandidate]:
    corpus_root = options.corpus.resolve(strict=True)
    if not corpus_root.is_dir():
        raise ValueError("--corpus must point to a directory")

    candidates: list[PdfCandidate] = []
    for path in corpus_root.rglob("*"):
        if not path.is_file() or path.suffix.lower() != ".pdf":
            continue
        absolute_path = path.resolve(strict=True)
        rel_path = absolute_path.relative_to(corpus_root).as_posix()
        fingerprint = fingerprint_file(absolute_path)
        candidates.append(
            PdfCandidate(
                path=absolute_path,
                rel_path=rel_path,
                size_bytes=fingerprint.size_bytes,
                sha256=fingerprint.sha256,
                short_hash=fingerprint.short_hash,
                source_bucket=detect_source_bucket(absolute_path),
            )
        )
    candidates.sort(key=lambda candidate: candidate.rel_path.casefold())
    return candidates


def select_candidates(
    candidates: list[PdfCandidate],
    options: CorpusRunOptions,
) -> list[PdfCandidate]:
    selected = [
        candidate
        for candidate in candidates
        if not _matches_any_exclude(candidate.rel_path, options.exclude)
    ]

    if options.only_file:
        selected = [
            candidate
            for candidate in selected
            if options.only_file in {candidate.rel_path, candidate.short_hash, candidate.sha256}
        ]
        if not selected:
            raise ValueError(f"--only-file did not match any selected PDF: {options.only_file}")

    if options.sample is not None:
        if options.sample < 0:
            raise ValueError("--sample must be greater than or equal to zero")
        sample_size = min(options.sample, len(selected))
        # This PRNG only makes corpus sampling reproducible; it protects no secret.
        selected = random.Random(options.seed).sample(selected, sample_size)  # noqa: S311
        selected.sort(key=lambda candidate: candidate.rel_path.casefold())

    if options.max_files is not None:
        if options.max_files < 0:
            raise ValueError("--max-files must be greater than or equal to zero")
        selected = selected[: options.max_files]

    return selected


def classify_pdf(candidate: PdfCandidate, options: CorpusRunOptions) -> PdfClassification:
    if candidate.size_bytes == 0:
        return PdfClassification(PdfClassificationStatus.EMPTY, note="empty file")

    try:
        with best_effort_timeout(options.timeout_sec), pikepdf.open(candidate.path) as pdf:
            if pdf.is_encrypted:
                return PdfClassification(PdfClassificationStatus.ENCRYPTED)
            page_count = len(pdf.pages)
    except pikepdf.PasswordError:
        return PdfClassification(PdfClassificationStatus.ENCRYPTED)
    except pikepdf.PdfError as exc:
        return PdfClassification(
            PdfClassificationStatus.INVALID,
            technical_detail="invalid_pdf",
            exception_type=type(exc).__name__,
        )
    except CorpusTimeoutError as exc:
        return PdfClassification(
            PdfClassificationStatus.UNKNOWN_ERROR,
            technical_detail="timeout",
            exception_type=type(exc).__name__,
            note="classification timed out",
        )
    except OSError as exc:
        return PdfClassification(
            PdfClassificationStatus.UNKNOWN_ERROR,
            technical_detail="input_path_error",
            exception_type=type(exc).__name__,
        )
    except Exception as exc:
        return PdfClassification(
            PdfClassificationStatus.UNKNOWN_ERROR,
            technical_detail="classification_error",
            exception_type=type(exc).__name__,
        )

    if candidate.size_bytes > options.max_file_size_mb * 1024 * 1024:
        return PdfClassification(PdfClassificationStatus.VALID_LARGE, page_count=page_count)
    return PdfClassification(PdfClassificationStatus.VALID, page_count=page_count)


def run_corpus_smoke(options: CorpusRunOptions) -> CorpusRunReport:
    started = time.monotonic()
    corpus_root = options.corpus.resolve(strict=True)
    run_dir = _create_run_dir(options.reports_root)
    _ensure_run_dir_outside_corpus(run_dir, corpus_root)
    fixtures_dir = run_dir / "fixtures"
    outputs_dir = run_dir / "outputs"
    fixtures_dir.mkdir(parents=True, exist_ok=True)
    outputs_dir.mkdir(parents=True, exist_ok=True)
    anchor_pdf = fixtures_dir / "anchor.pdf"
    _write_anchor_pdf(anchor_pdf)

    discovered = discover_pdfs(options)
    selected = select_candidates(discovered, options)
    tool_selection = discover_testable_tools(options)
    results: list[CorpusToolResult] = []
    classifications: dict[str, PdfClassification] = {}
    viewer_smoke_not_available = ""

    for index, candidate in enumerate(selected, start=1):
        classification = classify_pdf(candidate, options)
        classifications[candidate.rel_path] = classification
        if _skip_large_candidate(classification, options):
            results.extend(
                _skipped_results_for_candidate(
                    candidate,
                    classification,
                    tool_selection.tested_operation_specs,
                    "large file skipped; pass --include-large or --full to test it",
                    options,
                )
            )
            continue
        if classification.status is not PdfClassificationStatus.VALID:
            results.extend(
                _preclassified_results_for_candidate(
                    candidate,
                    classification,
                    tool_selection.tested_operation_specs,
                    options,
                )
            )
            continue

        for spec in tool_selection.tested_operation_specs:
            cases = _build_cases_for_tool(
                spec,
                candidate,
                classification,
                index,
                anchor_pdf,
                outputs_dir,
                options,
            )
            if not cases:
                results.append(
                    _skipped_result(
                        candidate,
                        classification,
                        spec,
                        "input shape is not suitable for this tool",
                        options,
                    )
                )
                continue
            results.extend(
                _run_tool_case(case, candidate, classification, corpus_root, options)
                for case in cases
            )

    if options.include_viewer_smoke and tool_selection.viewer_spec is not None:
        viewer_results, viewer_smoke_not_available = _run_viewer_smoke(
            selected,
            classifications,
            corpus_root,
            options,
        )
        results.extend(viewer_results)
    elif tool_selection.viewer_spec is not None:
        viewer_smoke_not_available = "viewer smoke disabled; pass --include-viewer-smoke"

    duration_total_ms = int((time.monotonic() - started) * 1000)
    report = _build_report(
        options,
        run_dir,
        corpus_root,
        discovered,
        selected,
        classifications,
        results,
        tool_selection,
        duration_total_ms,
        viewer_smoke_not_available,
    )
    write_reports(report, run_dir)
    cleanup_run_outputs(run_dir, keep_outputs=options.keep_outputs)
    return report


def write_reports(report: CorpusRunReport, run_dir: Path) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "report.json").write_text(
        json.dumps(_jsonable(report), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (run_dir / "report.jsonl").write_text(render_jsonl_report(report), encoding="utf-8")
    (run_dir / "report.md").write_text(render_markdown_report(report), encoding="utf-8")
    (run_dir / "bugs.md").write_text(render_bugs_report(report), encoding="utf-8")
    (run_dir / "problem_files.txt").write_text(render_problem_files(report), encoding="utf-8")
    (run_dir / "run.log").write_text(render_run_log(report), encoding="utf-8")


def cleanup_run_outputs(run_dir: Path, *, keep_outputs: bool) -> None:
    if keep_outputs:
        return
    for directory_name in ("outputs", "fixtures"):
        path = run_dir / directory_name
        if path.exists():
            shutil.rmtree(path)


def discover_testable_tools(options: CorpusRunOptions) -> ToolSelection:
    missing_scenarios = missing_corpus_scenario_tool_ids()
    if missing_scenarios:
        raise ValueError(
            "Available operation(s) lack corpus scenarios: " + ", ".join(sorted(missing_scenarios))
        )
    requested = set(options.tools)
    known_keys = {spec.key for spec in TOOL_SPECS}
    requested_unknown = tuple(sorted(requested - known_keys))
    if requested_unknown:
        raise ValueError(f"Unknown tool(s): {', '.join(requested_unknown)}")

    available_operation_specs = [
        spec
        for spec in TOOL_SPECS
        if spec.status == "available"
        and spec.view_kind == "operation"
        and spec.operation is not None
        and (not requested or spec.key in requested)
    ]
    available_operation_specs.sort(key=lambda spec: _tool_order_index(spec.key))

    viewer_spec = next((spec for spec in TOOL_SPECS if spec.key == "view"), None)
    if requested and "view" not in requested:
        viewer_spec = None

    available_not_testable = [
        spec.key
        for spec in TOOL_SPECS
        if spec.status == "available"
        and spec.view_kind != "operation"
        and spec.key != "view"
        and (not requested or spec.key in requested)
    ]
    if viewer_spec is not None and not options.include_viewer_smoke:
        available_not_testable.append("view")

    pending_not_tested = [
        spec.key
        for spec in TOOL_SPECS
        if spec.status == "pending" and (not requested or spec.key in requested)
    ]
    return ToolSelection(
        tested_operation_specs=tuple(available_operation_specs),
        viewer_spec=viewer_spec,
        available_not_testable=tuple(sorted(set(available_not_testable))),
        pending_not_tested=tuple(sorted(pending_not_tested)),
        requested_unknown=requested_unknown,
    )


def fingerprint_file(path: Path) -> FileFingerprint:
    if not path.exists():
        return FileFingerprint(False, 0, "", "")
    size_bytes = path.stat().st_size
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(HASH_CHUNK_SIZE), b""):
            digest.update(chunk)
    sha256 = digest.hexdigest()
    return FileFingerprint(True, size_bytes, sha256, sha256[:SHORT_HASH_LENGTH])


def detect_source_bucket(path: Path) -> str:
    parts = set(path.parts)
    for bucket in SOURCE_BUCKETS:
        if bucket in parts:
            return bucket
    return "unknown"


@contextmanager
def best_effort_timeout(seconds: int | None) -> Iterator[None]:
    if not seconds or seconds <= 0 or not timeout_is_available():
        yield
        return

    previous_handler = signal.getsignal(signal.SIGALRM)
    previous_timer = signal.setitimer(signal.ITIMER_REAL, 0)

    def _raise_timeout(_signum: int, _frame: FrameType | None) -> None:
        raise CorpusTimeoutError(f"operation timed out after {seconds} second(s)")

    signal.signal(signal.SIGALRM, _raise_timeout)
    signal.setitimer(signal.ITIMER_REAL, float(seconds))
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)
        if previous_timer[0] > 0:
            signal.setitimer(signal.ITIMER_REAL, previous_timer[0], previous_timer[1])


def timeout_is_available() -> bool:
    return hasattr(signal, "SIGALRM") and hasattr(signal, "setitimer")


def render_markdown_report(report: CorpusRunReport) -> str:
    lines = [
        "# Corpus smoke test — PriveoPDF",
        "",
        "## Résumé global",
        f"- PDF détectés : {report.pdf_detected_count}",
        f"- PDF sélectionnés : {report.pdf_selected_count}",
        f"- PDF testés : {report.pdf_tested_count}",
        f"- Durée totale : {report.duration_total_ms} ms",
        f"- Fichiers/seconde : {report.files_per_second:.2f}",
        f"- Bugs critiques : {len(report.bugs_critical)}",
        f"- Bugs probables : {len(report.bugs_probable)}",
        "",
        "## Options du run",
    ]
    for key, value in report.options.items():
        lines.append(f"- `{key}` : `{value}`")

    lines.extend(
        [
            "",
            "## Couverture des outils",
            f"- Outils testés : {', '.join(report.tested_tools) or 'aucun'}",
            f"- Disponibles non testés : {', '.join(report.available_not_testable) or 'aucun'}",
            f"- Pending non testés : {', '.join(report.pending_not_tested) or 'aucun'}",
            "",
            "## Scénarios réellement exécutés",
        ]
    )
    if report.scenario_ids_by_tool:
        for tool_id, scenario_ids in sorted(report.scenario_ids_by_tool.items()):
            lines.append(f"- `{tool_id}` : {', '.join(scenario_ids)}")
    else:
        lines.append("- Aucun")
    lines.extend(
        [
            "",
            "## Statuts PDF",
        ]
    )
    lines.extend(_counter_lines(report.classifications))
    lines.extend(["", "## Résultats par outil"])
    for tool_id, stats in sorted(report.tool_stats.items()):
        lines.append(f"### {tool_id}")
        lines.extend(_counter_lines(stats))

    lines.extend(["", "## Résultats par source de corpus"])
    for source, stats in sorted(report.source_stats.items()):
        lines.append(f"### {source}")
        lines.extend(_counter_lines(stats))

    lines.extend(["", "## Bugs critiques"])
    lines.extend(_result_summary_lines(report.bugs_critical))
    lines.extend(["", "## Bugs probables"])
    lines.extend(_result_summary_lines(report.bugs_probable))

    triage = [result for result in report.results if result.status is CorpusTestStatus.NEEDS_TRIAGE]
    lines.extend(["", "## Cas à trier"])
    lines.extend(_result_summary_lines(triage))

    lines.extend(["", "## Top 20 erreurs"])
    lines.extend(_dict_list_lines(report.top_error_signatures, ("signature", "count")))
    lines.extend(["", "## Top 20 fichiers problématiques"])
    lines.extend(_dict_list_lines(report.problem_files[:20], ("file", "status", "tool")))
    lines.extend(["", "## Top 20 fichiers les plus lents"])
    lines.extend(_dict_list_lines(report.top_slowest_files, ("file", "duration_ms", "tool")))
    lines.extend(["", "## Outils non testés"])
    if not report.available_not_testable and not report.pending_not_tested:
        lines.append("- Aucun")
    else:
        lines.extend(
            f"- `{tool}` : disponible mais non testé dans ce run"
            for tool in report.available_not_testable
        )
        lines.extend(f"- `{tool}` : non disponible" for tool in report.pending_not_tested)
    if report.viewer_smoke_not_available and "view" not in report.available_not_testable:
        lines.append(f"- `view` : {report.viewer_smoke_not_available}")

    lines.extend(["", "## Recommandations correctives"])
    if not report.recommendations:
        lines.append("- Aucune recommandation corrective automatique.")
    lines.extend(
        (
            "- "
            f"{recommendation.priority} — {recommendation.tool_id} : "
            f"{recommendation.symptom} "
            f"({recommendation.affected_files} fichier(s), source dominante "
            f"{recommendation.dominant_source}, exception dominante "
            f"{recommendation.dominant_exception}). "
            f"Zone probable : {recommendation.probable_code_area}. "
            f"Reproduction : `{recommendation.reproduction_command}`"
        )
        for recommendation in report.recommendations
    )

    lines.extend(["", "## Commandes de reproduction"])
    commands = sorted(
        {
            result.reproduction_command
            for result in report.results
            if result.reproduction_command and result.status.value in TRIAGE_STATUSES
        }
    )
    if not commands:
        lines.append("- Aucune commande de reproduction pour bug probable.")
    else:
        lines.extend(f"- `{command}`" for command in commands[:50])
    return "\n".join(lines) + "\n"


def render_bugs_report(report: CorpusRunReport) -> str:
    lines = ["# Bugs et cas à trier — Corpus PriveoPDF", ""]
    bug_results = [result for result in report.results if result.status.value in TRIAGE_STATUSES]
    if not bug_results:
        lines.append("Aucun bug ou cas à trier détecté.")
        return "\n".join(lines) + "\n"

    for index, result in enumerate(bug_results, start=1):
        bug_id = f"CORPUS-{index:04d}-{result.source_short_hash}-{result.tool_id}"
        lines.extend(
            [
                f"## {bug_id}",
                f"- Outil : `{result.tool_id}`",
                f"- Fichier : `{result.source_rel_path}`",
                f"- Hash court : `{result.source_short_hash}`",
                f"- Classification PDF : `{result.source_classification}`",
                f"- Page count : `{result.page_count}`",
                f"- Statut : `{result.status.value}`",
                f"- Exception : `{result.exception_type or 'n/a'}`",
                f"- Détail technique : `{result.technical_detail or 'n/a'}`",
                f"- Reproduction : `{result.reproduction_command}`",
                "- Sortie attendue : sortie créée, non vide, ouvrable, source inchangée.",
                f"- Sortie observée : {result.notes or result.triage}",
                f"- Suggestion : {_suggestion_for_result(result)}",
                f"- Priorité : {_priority_for_result(result)}",
                "",
            ]
        )
    return "\n".join(lines)


def render_problem_files(report: CorpusRunReport) -> str:
    lines = [
        (
            f"{item.get('file', '')}\t{item.get('short_hash', '')}\t"
            f"{item.get('status', '')}\t{item.get('tool', '')}"
        )
        for item in report.problem_files
    ]
    return "\n".join(lines) + ("\n" if lines else "")


def render_run_log(report: CorpusRunReport) -> str:
    return "\n".join(
        [
            f"timestamp={report.timestamp}",
            f"command={report.command}",
            f"corpus={report.corpus_path}",
            f"run_dir={report.run_dir}",
            f"pdf_detected={report.pdf_detected_count}",
            f"pdf_selected={report.pdf_selected_count}",
            f"result_count={len(report.results)}",
            f"bug_count={len(report.bugs_probable)}",
            f"critical_count={len(report.bugs_critical)}",
            "",
        ]
    )


def render_jsonl_report(report: CorpusRunReport) -> str:
    keep_outputs = bool(report.options.get("keep_outputs"))
    records = [
        {
            "file": result.source_rel_path,
            "short_hash": result.source_short_hash,
            "size_bytes": result.source_size_bytes,
            "page_count": result.page_count,
            "tool": result.tool_id,
            "scenario_id": result.scenario_id,
            "operation": result.operation_type,
            "status": public_status_for_result(result),
            "internal_status": result.status.value,
            "severity": severity_for_result(result),
            "duration_ms": result.duration_ms,
            "exception_type": result.exception_type,
            "error_message": _short_error_message(result),
            "semantic_oracle_status": result.semantic_oracle_status,
            "visual_oracle_status": result.visual_oracle_status,
            "oracle_pages_checked": result.oracle_pages_checked,
            "visual_pages_checked": result.visual_pages_checked,
            "output_paths": list(result.output_paths) if keep_outputs else [],
            "note": result.notes,
        }
        for result in report.results
    ]
    return "\n".join(json.dumps(record, ensure_ascii=False) for record in records) + (
        "\n" if records else ""
    )


def public_status_for_result(result: CorpusToolResult) -> str:
    if result.status is CorpusTestStatus.BUG_CRITICAL:
        return "critical"
    if result.status in {CorpusTestStatus.BUG, CorpusTestStatus.NEEDS_TRIAGE}:
        return "fail"
    if result.status in {
        CorpusTestStatus.SKIPPED,
        CorpusTestStatus.INVALID_INPUT,
        CorpusTestStatus.UNSUPPORTED_INPUT,
        CorpusTestStatus.EXPECTED_FAILURE,
    }:
        return "skip"
    return "pass"


def severity_for_result(result: CorpusToolResult) -> str:
    if result.status is CorpusTestStatus.BUG_CRITICAL:
        return "critical"
    if result.status in {CorpusTestStatus.BUG, CorpusTestStatus.NEEDS_TRIAGE}:
        return "high"
    if result.status in {
        CorpusTestStatus.INVALID_INPUT,
        CorpusTestStatus.UNSUPPORTED_INPUT,
        CorpusTestStatus.EXPECTED_FAILURE,
    }:
        return "medium"
    return "low"


def exit_code_for_report(
    report: CorpusRunReport,
    *,
    fail_on_bug: bool = False,
    fail_on_critical: bool = False,
    fail_on_any_failure: bool = False,
) -> int:
    if fail_on_any_failure:
        return 1 if _has_public_failure(report) else 0
    if fail_on_critical:
        return 1 if report.bugs_critical else 0
    if not fail_on_bug:
        return 0
    return 1 if report.bugs_probable or report.bugs_critical else 0


def _has_public_failure(report: CorpusRunReport) -> bool:
    return any(
        public_status_for_result(result) in {"fail", "critical"} for result in report.results
    )


def _short_error_message(result: CorpusToolResult) -> str:
    if result.exception_message_short:
        return result.exception_message_short
    if result.technical_detail:
        return result.technical_detail
    if result.status in {CorpusTestStatus.OK, CorpusTestStatus.SKIPPED}:
        return ""
    return result.triage


def command_to_string(command: tuple[str, ...]) -> str:
    return " ".join(shlex.quote(part) for part in command)


def _run_tool_case(
    case: ToolCase,
    candidate: PdfCandidate,
    classification: PdfClassification,
    corpus_root: Path,
    options: CorpusRunOptions,
) -> CorpusToolResult:
    before = fingerprint_file(candidate.path)
    started = time.monotonic()
    job_result: JobResult | None = None
    exception_type = ""
    exception_message = ""
    trace_short = ""
    try:
        with best_effort_timeout(options.timeout_sec):
            job = JobRequest(
                operation=case.operation,
                input_files=case.input_files,
                output_dir=case.output_dir,
                options=case.options,
                naming_strategy="explicit",
                job_id=str(uuid.uuid4()),
            )
            job_result = run_structural_job(job)
    except Exception as exc:
        exception_type = type(exc).__name__
        exception_message = _sanitize_message(str(exc), candidate, None)
        trace_short = _sanitize_trace(traceback.format_exc(), candidate)
    after = fingerprint_file(candidate.path)

    run_root = _run_root_for_case(case)
    output_paths = tuple(_relpath_if_possible(path, run_root) for path in _observed_outputs(case))
    expected_outputs = case.output_paths_expected or tuple(_observed_outputs(case))
    output_exists = bool(expected_outputs) and all(path.exists() for path in expected_outputs)
    output_sizes = tuple(path.stat().st_size if path.exists() else 0 for path in expected_outputs)
    output_openable = _outputs_openable(expected_outputs) if output_exists else False
    source_unchanged = before.exists and after.exists and before.sha256 == after.sha256
    output_inside_corpus = any(_is_relative_to(path, corpus_root) for path in expected_outputs)
    source_overwritten = any(
        path.resolve(strict=False) == candidate.path for path in expected_outputs
    )
    oracle = None
    if (
        job_result is not None
        and job_result.success
        and output_exists
        and all(size > 0 for size in output_sizes)
        and output_openable
        and source_unchanged
        and not output_inside_corpus
        and not source_overwritten
    ):
        with best_effort_timeout(options.timeout_sec):
            oracle = validate_structural_outputs(
                tool_id=case.tool_id,
                input_files=case.input_files,
                output_paths=expected_outputs,
                options=case.options,
                render_visual=options.transform_visual_oracle,
            )
    after = fingerprint_file(candidate.path)
    source_unchanged = before.exists and after.exists and before.sha256 == after.sha256
    duration_ms = int((time.monotonic() - started) * 1000)

    if not after.exists or not source_unchanged or output_inside_corpus or source_overwritten:
        status = CorpusTestStatus.BUG_CRITICAL
        triage = "source integrity or output isolation guard failed"
    elif exception_type == CorpusTimeoutError.__name__:
        status = CorpusTestStatus.BUG_CRITICAL
        triage = "operation timed out"
    elif exception_type:
        status = CorpusTestStatus.BUG
        triage = "unhandled exception escaped the corpus runner"
    elif job_result is None:
        status = CorpusTestStatus.BUG
        triage = "no job result was produced"
    elif not job_result.success:
        technical_detail = job_result.technical_detail or ""
        if _technical_detail_is_expected(technical_detail) and not _classification_is_valid(
            classification
        ):
            status = CorpusTestStatus.EXPECTED_FAILURE
            triage = "domain rejected problematic input"
        else:
            status = CorpusTestStatus.NEEDS_TRIAGE
            triage = "valid input failed in the PDF engine"
    elif not output_exists:
        status = CorpusTestStatus.BUG_CRITICAL
        triage = "job reported success but expected output is missing"
    elif any(size <= 0 for size in output_sizes):
        status = CorpusTestStatus.BUG_CRITICAL
        triage = "job reported success but output is empty"
    elif output_openable is False:
        status = CorpusTestStatus.BUG_CRITICAL
        triage = "job reported success but output is not openable"
    elif oracle is None:
        status = CorpusTestStatus.BUG_CRITICAL
        triage = "output oracle did not run"
    elif oracle.semantic_status is not OracleStatus.OK:
        status = CorpusTestStatus.BUG_CRITICAL
        triage = "output differs semantically from the requested operation"
    elif oracle.visual_status is OracleStatus.MISMATCH:
        status = CorpusTestStatus.BUG_CRITICAL
        triage = "rendered output differs from the mapped source pages"
    else:
        status = CorpusTestStatus.OK
        triage = "ok"

    technical_detail = job_result.technical_detail if job_result is not None else ""
    if technical_detail and ":" in technical_detail and not exception_type:
        exception_type = technical_detail.split(":", maxsplit=1)[1]
    notes = case.note
    if job_result is not None and job_result.user_message and status is not CorpusTestStatus.OK:
        notes = f"{notes}; {job_result.user_message}".strip("; ")

    return CorpusToolResult(
        tool_id=case.tool_id,
        operation_type=case.operation.value,
        input_files=tuple(_input_relpath(path, candidate) for path in case.input_files),
        source_classification=classification.status.value,
        status=status,
        triage=triage,
        duration_ms=duration_ms or (job_result.duration_ms if job_result else 0),
        output_paths=output_paths,
        output_exists=output_exists,
        output_size_bytes=output_sizes,
        output_openable=output_openable,
        source_hash_before=before.sha256,
        source_hash_after=after.sha256,
        source_unchanged=source_unchanged,
        exception_type=exception_type,
        exception_message_short=exception_message,
        technical_detail=technical_detail,
        trace_short=trace_short,
        notes=notes,
        scenario_id=case.scenario_id,
        reproduction_command=_reproduction_command(options, candidate, case.tool_id),
        source_rel_path=candidate.rel_path,
        source_short_hash=candidate.short_hash,
        source_bucket=candidate.source_bucket,
        page_count=classification.page_count,
        source_size_bytes=candidate.size_bytes,
        semantic_oracle_status=(
            oracle.semantic_status.value
            if oracle is not None
            else OracleStatus.NOT_APPLICABLE.value
        ),
        visual_oracle_status=(
            oracle.visual_status.value if oracle is not None else OracleStatus.NOT_APPLICABLE.value
        ),
        oracle_pages_checked=oracle.semantic_pages_checked if oracle is not None else 0,
        visual_pages_checked=oracle.visual_pages_checked if oracle is not None else 0,
        text_pages_checked=oracle.text_pages_checked if oracle is not None else 0,
        visual_pages_skipped=oracle.visual_pages_skipped if oracle is not None else 0,
        visual_max_normalized_mae=(oracle.visual_max_normalized_mae if oracle is not None else 0.0),
        visual_max_changed_fraction=(
            oracle.visual_max_changed_fraction if oracle is not None else 0.0
        ),
        oracle_failure_code=oracle.failure_code if oracle is not None else "",
        oracle_failure_detail=oracle.detail if oracle is not None else "",
    )


def _observed_outputs(case: ToolCase) -> tuple[Path, ...]:
    if case.output_paths_expected:
        return case.output_paths_expected
    if case.output_dir.exists():
        return tuple(sorted(case.output_dir.glob("*.pdf")))
    return ()


def _run_root_for_case(case: ToolCase) -> Path:
    if case.output_dir.name == "outputs":
        return case.output_dir.parent
    if case.output_dir.parent.name == "outputs":
        return case.output_dir.parent.parent
    return case.output_dir.parent


def _build_cases_for_tool(
    spec: ToolSpec,
    candidate: PdfCandidate,
    classification: PdfClassification,
    index: int,
    anchor_pdf: Path,
    outputs_dir: Path,
    options: CorpusRunOptions,
) -> tuple[ToolCase, ...]:
    if spec.operation is None:
        return ()
    page_count = classification.page_count or 0
    output_base = f"{index:05d}_{candidate.short_hash}_{spec.key}"

    if spec.key == "merge":
        output_path = outputs_dir / f"{output_base}.pdf"
        return (
            ToolCase(
                spec.key,
                spec.operation,
                (anchor_pdf, candidate.path),
                outputs_dir,
                {"output_path": output_path},
                (output_path,),
                spec.key,
                "anchor + source",
                "merge-anchor-source",
            ),
        )

    if spec.key == "extract":
        cases = [
            _single_output_case(
                spec,
                candidate,
                outputs_dir,
                f"{output_base}.pdf",
                {"page_numbers": (1,)},
                "page 1",
                "extract-page-1",
            )
        ]
        if options.full and page_count >= 3:
            cases.append(
                _single_output_case(
                    spec,
                    candidate,
                    outputs_dir,
                    f"{output_base}_pages-1-3.pdf",
                    {"page_numbers": (1, 2, 3)},
                    "pages 1-3",
                    "extract-pages-1-3",
                )
            )
        return tuple(cases)

    if spec.key == "remove":
        if page_count < 2:
            return ()
        return (
            _single_output_case(
                spec,
                candidate,
                outputs_dir,
                f"{output_base}.pdf",
                {"page_numbers": (1,)},
                "remove page 1",
                "remove-page-1",
            ),
        )

    if spec.key == "split":
        output_dir = outputs_dir / output_base
        output_dir.mkdir(parents=True, exist_ok=True)
        groups = ((1,),) if page_count == 1 else ((1,), tuple(range(2, page_count + 1)))
        expected = tuple(
            output_dir / f"{candidate.short_hash}_split_part-{part}.pdf"
            for part in range(1, len(groups) + 1)
        )
        return (
            ToolCase(
                spec.key,
                spec.operation,
                (candidate.path,),
                output_dir,
                {"page_groups": groups, "base_name": f"{candidate.short_hash}_split"},
                expected,
                spec.key,
                "page_groups visual path",
                "split-page-1-and-remainder",
            ),
        )

    if spec.key == "rotate":
        angles = (90, 180, 270) if options.full else (90,)
        return tuple(
            _single_output_case(
                spec,
                candidate,
                outputs_dir,
                f"{output_base}_{angle}.pdf",
                {"page_numbers": (1,), "angle": angle},
                f"rotate page 1 by {angle}",
                f"rotate-page-1-{angle}",
            )
            for angle in angles
        )

    if spec.key == "reorder":
        if page_count < 2:
            return ()
        order = (2, 1, *range(3, page_count + 1))
        return (
            _single_output_case(
                spec,
                candidate,
                outputs_dir,
                f"{output_base}.pdf",
                {"page_order": order},
                "complete permutation 2,1,3..N",
                "reorder-swap-first-two",
            ),
        )
    if spec.key == "insert":
        if page_count < 1:
            return ()
        output_path = outputs_dir / f"{output_base}.pdf"
        return (
            ToolCase(
                spec.key,
                spec.operation,
                (candidate.path, anchor_pdf),
                outputs_dir,
                {
                    "page_numbers": (1,),
                    "insert_after_page": min(1, page_count),
                    "output_path": output_path,
                },
                (output_path,),
                spec.key,
                "anchor page 1 inserted after primary page 1",
                "insert-anchor-page-1-after-page-1",
            ),
        )
    if spec.key == "blank_page":
        if page_count < 1:
            return ()
        return (
            _single_output_case(
                spec,
                candidate,
                outputs_dir,
                f"{output_base}.pdf",
                {"width_mm": 210.0, "height_mm": 297.0, "insert_after_page": page_count},
                "A4 portrait blank page appended",
                "blank-page-a4-portrait-at-end",
            ),
        )
    return ()


def _single_output_case(
    spec: ToolSpec,
    candidate: PdfCandidate,
    outputs_dir: Path,
    file_name: str,
    options: dict[str, Any],
    note: str,
    scenario_id: str,
) -> ToolCase:
    if spec.operation is None:
        raise ValueError("spec must define an operation")
    output_path = outputs_dir / file_name
    job_options = dict(options)
    job_options["output_path"] = output_path
    return ToolCase(
        spec.key,
        spec.operation,
        (candidate.path,),
        outputs_dir,
        job_options,
        (output_path,),
        spec.key,
        note,
        scenario_id,
    )


def _run_viewer_smoke(
    selected: list[PdfCandidate],
    classifications: dict[str, PdfClassification],
    corpus_root: Path,
    options: CorpusRunOptions,
) -> tuple[list[CorpusToolResult], str]:
    del corpus_root
    try:
        if platform.system() == "Linux":
            os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtCore import QSize
        from PySide6.QtPdf import QPdfDocument, QPdfDocumentRenderOptions
        from PySide6.QtWidgets import QApplication
    except Exception as exc:
        return [], f"viewer smoke unavailable: {type(exc).__name__}"

    app = QApplication.instance() or QApplication([])
    results: list[CorpusToolResult] = []
    valid_candidates = [
        candidate
        for candidate in selected
        if classifications.get(candidate.rel_path)
        and classifications[candidate.rel_path].status is PdfClassificationStatus.VALID
    ][:VIEWER_SMOKE_LIMIT]

    for candidate in valid_candidates:
        classification = classifications[candidate.rel_path]
        before = fingerprint_file(candidate.path)
        started = time.monotonic()
        status = CorpusTestStatus.OK
        triage = "viewer loaded first document page metadata"
        technical_detail = ""
        exception_type = ""
        visual_oracle_status = OracleStatus.NOT_APPLICABLE
        visual_pages_checked = 0
        try:
            with best_effort_timeout(options.timeout_sec):
                document = QPdfDocument()
                error = document.load(str(candidate.path))
                app.processEvents()
                if error != QPdfDocument.Error.None_ or document.pageCount() <= 0:
                    status = CorpusTestStatus.NEEDS_TRIAGE
                    triage = "valid PDF did not load in QtPdf viewer smoke"
                    technical_detail = f"qpdfdocument_error:{error}"
                    visual_oracle_status = OracleStatus.SOURCE_UNAVAILABLE
                else:
                    render_options = QPdfDocumentRenderOptions()
                    render_options.setRenderFlags(QPdfDocumentRenderOptions.RenderFlag.Annotations)
                    image = document.render(0, QSize(256, 256), render_options)
                    if image.isNull():
                        status = CorpusTestStatus.NEEDS_TRIAGE
                        triage = "QtPdf returned a null first-page rendering"
                        technical_detail = "qpdfdocument_error:null_render"
                        visual_oracle_status = OracleStatus.SOURCE_UNAVAILABLE
                    else:
                        visual_oracle_status = OracleStatus.OK
                        visual_pages_checked = 1
                document.close()
        except Exception as exc:
            status = CorpusTestStatus.BUG
            triage = "viewer smoke raised an exception"
            exception_type = type(exc).__name__
            technical_detail = exception_type
            visual_oracle_status = OracleStatus.MISMATCH
        after = fingerprint_file(candidate.path)
        if before.sha256 != after.sha256:
            status = CorpusTestStatus.BUG_CRITICAL
            triage = "viewer smoke modified source file"
        results.append(
            CorpusToolResult(
                tool_id="view",
                operation_type="viewer",
                input_files=(candidate.rel_path,),
                source_classification=classification.status.value,
                status=status,
                triage=triage,
                duration_ms=int((time.monotonic() - started) * 1000),
                source_hash_before=before.sha256,
                source_hash_after=after.sha256,
                source_unchanged=before.sha256 == after.sha256,
                exception_type=exception_type,
                technical_detail=technical_detail,
                notes="viewer smoke is capped and stores no page images",
                scenario_id="view-first-page",
                reproduction_command=_reproduction_command(options, candidate, "view"),
                source_rel_path=candidate.rel_path,
                source_short_hash=candidate.short_hash,
                source_bucket=candidate.source_bucket,
                page_count=classification.page_count,
                source_size_bytes=candidate.size_bytes,
                visual_oracle_status=visual_oracle_status.value,
                visual_pages_checked=visual_pages_checked,
            )
        )
    return results, ""


def _preclassified_results_for_candidate(
    candidate: PdfCandidate,
    classification: PdfClassification,
    specs: tuple[ToolSpec, ...],
    options: CorpusRunOptions,
) -> list[CorpusToolResult]:
    status = (
        CorpusTestStatus.UNSUPPORTED_INPUT
        if classification.status
        in {PdfClassificationStatus.ENCRYPTED, PdfClassificationStatus.UNSUPPORTED}
        else CorpusTestStatus.INVALID_INPUT
    )
    note = f"preclassified as {classification.status.value}; tool not executed"
    return [
        _synthetic_result(
            candidate,
            classification,
            spec,
            status,
            note,
            classification.note,
            options,
        )
        for spec in specs
    ]


def _skipped_results_for_candidate(
    candidate: PdfCandidate,
    classification: PdfClassification,
    specs: tuple[ToolSpec, ...],
    note: str,
    options: CorpusRunOptions,
) -> list[CorpusToolResult]:
    return [
        _synthetic_result(
            candidate,
            classification,
            spec,
            CorpusTestStatus.SKIPPED,
            note,
            note,
            options,
        )
        for spec in specs
    ]


def _skipped_result(
    candidate: PdfCandidate,
    classification: PdfClassification,
    spec: ToolSpec,
    note: str,
    options: CorpusRunOptions,
) -> CorpusToolResult:
    return _synthetic_result(
        candidate,
        classification,
        spec,
        CorpusTestStatus.SKIPPED,
        note,
        note,
        options,
    )


def _synthetic_result(
    candidate: PdfCandidate,
    classification: PdfClassification,
    spec: ToolSpec,
    status: CorpusTestStatus,
    triage: str,
    notes: str,
    options: CorpusRunOptions,
) -> CorpusToolResult:
    fingerprint = fingerprint_file(candidate.path)
    return CorpusToolResult(
        tool_id=spec.key,
        operation_type=spec.operation.value if spec.operation is not None else spec.view_kind,
        input_files=(candidate.rel_path,),
        source_classification=classification.status.value,
        status=status,
        triage=triage,
        duration_ms=0,
        source_hash_before=fingerprint.sha256,
        source_hash_after=fingerprint.sha256,
        source_unchanged=True,
        exception_type=classification.exception_type,
        technical_detail=classification.technical_detail,
        notes=notes,
        reproduction_command=_reproduction_command(options, candidate, spec.key),
        source_rel_path=candidate.rel_path,
        source_short_hash=candidate.short_hash,
        source_bucket=candidate.source_bucket,
        page_count=classification.page_count,
        source_size_bytes=candidate.size_bytes,
    )


def _build_report(
    options: CorpusRunOptions,
    run_dir: Path,
    corpus_root: Path,
    discovered: list[PdfCandidate],
    selected: list[PdfCandidate],
    classifications_by_file: dict[str, PdfClassification],
    results: list[CorpusToolResult],
    tool_selection: ToolSelection,
    duration_total_ms: int,
    viewer_smoke_not_available: str,
) -> CorpusRunReport:
    classification_counts = Counter(
        classification.status.value for classification in classifications_by_file.values()
    )
    for status in PdfClassificationStatus:
        classification_counts.setdefault(status.value, 0)

    tool_stats: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    source_stats: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    duration_by_tool: dict[str, int] = defaultdict(int)
    scenario_ids_by_tool: dict[str, set[str]] = defaultdict(set)
    for result in results:
        tool_stats[result.tool_id][result.status.value] += 1
        source_stats[result.source_bucket][result.status.value] += 1
        duration_by_tool[result.tool_id] += result.duration_ms
        if result.scenario_id:
            scenario_ids_by_tool[result.tool_id].add(result.scenario_id)

    bugs_probable = [
        result
        for result in results
        if result.status in {CorpusTestStatus.BUG, CorpusTestStatus.NEEDS_TRIAGE}
    ]
    bugs_critical = [result for result in results if result.status is CorpusTestStatus.BUG_CRITICAL]
    problem_files = _problem_files(results)
    pyside6_version = _package_version("PySide6")
    memory_available, max_rss_kb = _memory_metrics()
    pdf_tested_count = len(
        {
            result.source_rel_path
            for result in results
            if result.status
            not in {
                CorpusTestStatus.INVALID_INPUT,
                CorpusTestStatus.UNSUPPORTED_INPUT,
                CorpusTestStatus.SKIPPED,
            }
        }
    )
    report = CorpusRunReport(
        timestamp=datetime.now(UTC).isoformat(),
        command=command_to_string(options.command),
        options=_options_for_report(options),
        python_version=platform.python_version(),
        platform=platform.platform(),
        pikepdf_version=getattr(pikepdf, "__version__", "unknown"),
        pyside6_version=pyside6_version,
        git_commit=_git_output(("rev-parse", "HEAD")),
        git_branch=_git_output(("branch", "--show-current")),
        repo_dirty=_repo_dirty(),
        corpus_path=_display_path(corpus_root),
        corpus_root_name=corpus_root.name,
        pdf_detected_count=len(discovered),
        pdf_selected_count=len(selected),
        pdf_tested_count=pdf_tested_count,
        classifications=dict(sorted(classification_counts.items())),
        tool_stats={key: dict(value) for key, value in sorted(tool_stats.items())},
        source_stats={key: dict(value) for key, value in sorted(source_stats.items())},
        duration_total_ms=duration_total_ms,
        duration_by_tool_ms=dict(sorted(duration_by_tool.items())),
        files_per_second=(len(selected) / (duration_total_ms / 1000))
        if duration_total_ms > 0
        else 0.0,
        memory_metrics_available=memory_available,
        max_rss_kb=max_rss_kb,
        timeout_available=timeout_is_available(),
        timeout_sec=options.timeout_sec,
        top_slowest_files=_top_slowest(results),
        top_error_signatures=_top_error_signatures(results),
        results=results,
        bugs_probable=bugs_probable,
        bugs_critical=bugs_critical,
        problem_files=problem_files,
        tested_tools=[spec.key for spec in tool_selection.tested_operation_specs]
        + (["view"] if options.include_viewer_smoke and tool_selection.viewer_spec else []),
        scenario_ids_by_tool={
            tool_id: sorted(scenario_ids)
            for tool_id, scenario_ids in sorted(scenario_ids_by_tool.items())
        },
        available_not_testable=list(tool_selection.available_not_testable),
        pending_not_tested=list(tool_selection.pending_not_tested),
        viewer_smoke_not_available=viewer_smoke_not_available,
        recommendations=_recommendations(results),
        run_dir=_display_path(run_dir),
    )
    return report


def _options_for_report(options: CorpusRunOptions) -> dict[str, Any]:
    data = asdict(options)
    data["corpus"] = _display_path(options.corpus)
    data["reports_root"] = _display_path(options.reports_root)
    data["command"] = list(options.command)
    data["exclude"] = list(options.exclude)
    data["tools"] = list(options.tools)
    return data


def _problem_files(results: list[CorpusToolResult]) -> list[dict[str, Any]]:
    worst_by_file: dict[str, CorpusToolResult] = {}
    severity = {
        CorpusTestStatus.BUG_CRITICAL: 5,
        CorpusTestStatus.BUG: 4,
        CorpusTestStatus.NEEDS_TRIAGE: 3,
        CorpusTestStatus.INVALID_INPUT: 2,
        CorpusTestStatus.UNSUPPORTED_INPUT: 2,
        CorpusTestStatus.EXPECTED_FAILURE: 1,
        CorpusTestStatus.SKIPPED: 0,
        CorpusTestStatus.OK: 0,
    }
    for result in results:
        if severity[result.status] <= 0:
            continue
        current = worst_by_file.get(result.source_rel_path)
        if current is None or severity[result.status] > severity[current.status]:
            worst_by_file[result.source_rel_path] = result
    return [
        {
            "file": result.source_rel_path,
            "short_hash": result.source_short_hash,
            "status": result.status.value,
            "tool": result.tool_id,
            "classification": result.source_classification,
        }
        for result in sorted(worst_by_file.values(), key=lambda item: item.source_rel_path)
    ]


def _recommendations(results: list[CorpusToolResult]) -> list[CorpusRecommendation]:
    grouped: dict[tuple[str, str, str], list[CorpusToolResult]] = defaultdict(list)
    for result in results:
        if result.status.value not in TRIAGE_STATUSES:
            continue
        signature = result.technical_detail or result.exception_type or result.triage
        grouped[(result.status.value, result.tool_id, signature)].append(result)

    recommendations: list[CorpusRecommendation] = []
    for (status, tool_id, signature), group in sorted(
        grouped.items(), key=lambda item: (-len(item[1]), item[0])
    )[:20]:
        source = Counter(result.source_bucket for result in group).most_common(1)[0][0]
        priority = "P0" if status == "BUG_CRITICAL" else ("P1" if status == "BUG" else "P2")
        first = group[0]
        recommendations.append(
            CorpusRecommendation(
                priority=priority,
                tool_id=tool_id,
                symptom=f"{status} avec {signature}",
                affected_files=len(group),
                dominant_source=source,
                dominant_exception=signature,
                probable_code_area=_probable_code_area(tool_id),
                reproduction_command=first.reproduction_command,
            )
        )
    return recommendations


def _top_slowest(results: list[CorpusToolResult]) -> list[dict[str, Any]]:
    return [
        {
            "file": result.source_rel_path,
            "short_hash": result.source_short_hash,
            "tool": result.tool_id,
            "duration_ms": result.duration_ms,
            "size_bytes": result.source_size_bytes,
        }
        for result in sorted(results, key=lambda item: item.duration_ms, reverse=True)[:20]
    ]


def _top_error_signatures(results: list[CorpusToolResult]) -> list[dict[str, Any]]:
    counter = Counter(
        result.technical_detail or result.exception_type or result.triage
        for result in results
        if result.status not in {CorpusTestStatus.OK, CorpusTestStatus.SKIPPED}
    )
    return [
        {"signature": signature, "count": count} for signature, count in counter.most_common(20)
    ]


def _memory_metrics() -> tuple[bool, int | None]:
    if resource is None:
        return False, None
    try:
        usage = resource.getrusage(resource.RUSAGE_SELF)
    except Exception:
        return False, None
    return True, int(usage.ru_maxrss)


def _package_version(package_name: str) -> str | None:
    try:
        from importlib.metadata import version

        return version(package_name)
    except Exception:
        return None


def _git_output(args: tuple[str, ...]) -> str | None:
    git_executable = shutil.which("git")
    if git_executable is None:
        return None
    try:
        # The executable is resolved to an absolute path and callers pass only
        # fixed, internal read-only Git arguments.
        result = subprocess.run(  # noqa: S603
            (git_executable, *args),
            cwd=Path(__file__).resolve().parents[3],
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except Exception:
        return None
    value = result.stdout.strip()
    return value or None


def _repo_dirty() -> bool | None:
    git_executable = shutil.which("git")
    if git_executable is None:
        return None
    try:
        # The executable is resolved to an absolute path and the command is a
        # fixed, read-only repository status query.
        result = subprocess.run(  # noqa: S603
            (git_executable, "status", "--short"),
            cwd=Path(__file__).resolve().parents[3],
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except Exception:
        return None
    return bool(result.stdout.strip())


def _write_anchor_pdf(path: Path) -> None:
    pdf = pikepdf.Pdf.new()
    try:
        pdf.add_blank_page(page_size=(200, 200))
        pdf.save(path)
    finally:
        pdf.close()


def _create_run_dir(reports_root: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%dT%H%M%S%f")
    run_dir = reports_root / timestamp
    run_dir.mkdir(parents=True, exist_ok=False)
    return run_dir.resolve(strict=True)


def _ensure_run_dir_outside_corpus(run_dir: Path, corpus_root: Path) -> None:
    if _is_relative_to(run_dir, corpus_root):
        raise ValueError("reports_root must not be inside the corpus directory")


def _matches_any_exclude(rel_path: str, patterns: tuple[str, ...]) -> bool:
    return any(
        fnmatch.fnmatch(rel_path, pattern)
        or any(fnmatch.fnmatch(part, pattern) for part in rel_path.split("/"))
        for pattern in patterns
    )


def _skip_large_candidate(
    classification: PdfClassification,
    options: CorpusRunOptions,
) -> bool:
    return (
        classification.status is PdfClassificationStatus.VALID_LARGE
        and not options.include_large
        and not options.full
    )


def _classification_is_valid(classification: PdfClassification) -> bool:
    return classification.status in {
        PdfClassificationStatus.VALID,
        PdfClassificationStatus.VALID_LARGE,
    }


def _technical_detail_is_expected(technical_detail: str) -> bool:
    detail = technical_detail.split(":", maxsplit=1)[0]
    return detail in EXPECTED_TECHNICAL_DETAILS


def _outputs_openable(paths: tuple[Path, ...]) -> bool:
    try:
        for path in paths:
            with pikepdf.open(path) as pdf:
                len(pdf.pages)
    except Exception:
        return False
    return True


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(parent.resolve(strict=False))
    except ValueError:
        return False
    return True


def _input_relpath(path: Path, candidate: PdfCandidate) -> str:
    if path == candidate.path:
        return candidate.rel_path
    return _display_path(path)


def _relpath_if_possible(path: Path, root: Path) -> str:
    try:
        return path.resolve(strict=False).relative_to(root.resolve(strict=False)).as_posix()
    except ValueError:
        return _display_path(path)


def _display_path(path: Path) -> str:
    try:
        return path.resolve(strict=False).relative_to(Path.cwd()).as_posix()
    except ValueError:
        return str(path)


def _sanitize_message(
    message: str,
    candidate: PdfCandidate,
    run_dir: Path | None,
) -> str:
    sanitized = message.replace(str(candidate.path), candidate.rel_path)
    if run_dir is not None:
        sanitized = sanitized.replace(str(run_dir), "<run_dir>")
    sanitized = sanitized.replace(str(Path.cwd()), ".")
    sanitized = re.sub(r"/[^\s:]+", "<path>", sanitized)
    return sanitized[:240]


def _sanitize_trace(trace: str, candidate: PdfCandidate) -> str:
    trace_lines = trace.strip().splitlines()[-6:]
    return _sanitize_message("\n".join(trace_lines), candidate, None)


def _reproduction_command(
    options: CorpusRunOptions,
    candidate: PdfCandidate,
    tool_id: str,
) -> str:
    command = [
        "python",
        "scripts/corpus_smoke_test.py",
        "--corpus",
        _display_path(options.corpus),
        "--only-file",
        candidate.rel_path,
        "--tools",
        tool_id,
        "--fail-on-any-failure",
    ]
    if options.full:
        command.append("--full")
    if options.include_large:
        command.append("--include-large")
    if not options.transform_visual_oracle:
        command.append("--skip-transform-visual-oracle")
    return command_to_string(tuple(command))


def _tool_order_index(tool_id: str) -> int:
    try:
        return STRUCTURAL_TOOL_ORDER.index(tool_id)
    except ValueError:
        return len(STRUCTURAL_TOOL_ORDER)


def _counter_lines(counter: dict[str, int]) -> list[str]:
    if not counter:
        return ["- Aucun"]
    return [f"- `{key}` : {value}" for key, value in sorted(counter.items())]


def _result_summary_lines(results: Iterable[CorpusToolResult]) -> list[str]:
    items = list(results)
    if not items:
        return ["- Aucun"]
    return [
        "- "
        f"`{result.status.value}` `{result.tool_id}` `{result.source_rel_path}` "
        f"({result.technical_detail or result.exception_type or result.triage})"
        for result in items[:50]
    ]


def _dict_list_lines(items: list[dict[str, Any]], keys: tuple[str, ...]) -> list[str]:
    if not items:
        return ["- Aucun"]
    lines = []
    for item in items[:20]:
        parts = [f"{key}={item.get(key, '')}" for key in keys]
        lines.append(f"- {'; '.join(parts)}")
    return lines


def _probable_code_area(tool_id: str) -> str:
    mapping = {
        "merge": "src/pdfmod/engine/pdf_structural.py, merge_pdfs/save",
        "extract": "src/pdfmod/engine/pdf_structural.py, extract_pages/save",
        "remove": "src/pdfmod/engine/pdf_structural.py, remove_pages/save",
        "split": "src/pdfmod/engine/pdf_structural.py, split_pdf_by_page_groups/save",
        "rotate": "src/pdfmod/engine/pdf_structural.py, rotate_pages/save",
        "reorder": "src/pdfmod/engine/pdf_structural.py, reorder_pages/save",
        "insert": "src/pdfmod/engine/pdf_structural.py, insert_pdf_pages/save",
        "blank_page": "src/pdfmod/engine/pdf_structural.py, insert_blank_page/save",
        "view": "src/pdfmod/ui/tool_pages/view_pdf_page.py, QtPdf load",
    }
    return mapping.get(tool_id, "src/pdfmod/engine/pdf_structural.py")


def _priority_for_result(result: CorpusToolResult) -> str:
    if result.status is CorpusTestStatus.BUG_CRITICAL:
        return "P0"
    if result.status is CorpusTestStatus.BUG:
        return "P1"
    if result.status is CorpusTestStatus.NEEDS_TRIAGE:
        return "P2"
    return "P3"


def _suggestion_for_result(result: CorpusToolResult) -> str:
    if result.status is CorpusTestStatus.BUG_CRITICAL:
        return "Verifier immediatement les garde-fous de sortie et de non-modification source."
    if result.status is CorpusTestStatus.BUG:
        return f"Verifier le chemin moteur {result.tool_id} et la validation de sortie."
    return f"Qualifier le PDF et typer l'erreur attendue pour {result.tool_id} si necessaire."


def _jsonable(value: Any) -> Any:
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, Path):
        return _display_path(value)
    if is_dataclass(value) and not isinstance(value, type):
        return {key: _jsonable(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def parse_tools(value: str | None) -> tuple[str, ...]:
    if not value:
        return ()
    parts = tuple(part.strip() for part in value.split(",") if part.strip())
    if len(parts) == 1 and parts[0].casefold() == "all":
        return ()
    return parts


def run_from_argv(
    argv: tuple[str, ...],
    parser_factory: Callable[[tuple[str, ...]], CorpusRunOptions],
) -> int:
    options = parser_factory(argv)
    report = run_corpus_smoke(options)
    return exit_code_for_report(
        report,
        fail_on_bug=options.fail_on_bug,
        fail_on_critical=options.fail_on_critical,
        fail_on_any_failure=options.fail_on_any_failure,
    )
