from __future__ import annotations

import uuid
from pathlib import Path

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from pdfmod.app.settings import AppSettings
from pdfmod.domain.document_context import ToolLaunchContext
from pdfmod.domain.jobs import JobRequest, JobResult, OperationType
from pdfmod.domain.page_plans import PageOutputGroupModel, PageSelectionModel, SplitPlanModel
from pdfmod.domain.page_ranges import (
    parse_page_range_groups,
    parse_page_ranges,
    validate_page_numbers,
    validate_page_ranges,
)
from pdfmod.ui.components import (
    GhostButton,
    GuidedActionCue,
    PageOutputGroupWidget,
    PdfInputPanel,
    PdfPageThumbnailGrid,
    PrimaryButton,
    ProgressOverlay,
    SecondaryButton,
    SurfacePanel,
    show_error,
    show_info,
)
from pdfmod.ui.components.page_groups import (
    PAGE_OUTPUT_LIST_COMPACT_HEIGHT,
    PAGE_OUTPUT_LIST_HEIGHT,
    PAGE_OUTPUT_LIST_LARGE_HEIGHT,
)
from pdfmod.ui.components.page_thumbnails import pages_to_range_expression
from pdfmod.ui.i18n import Locale, tr
from pdfmod.ui.tool_specs import ToolSpec, tool_spec_for_operation
from pdfmod.ui.workspace_state import WorkspaceDocument
from pdfmod.workers.job_runner import PageCountResult, QtJobRunner, QtPageCountRunner

MAX_SPLIT_OUTPUT_GROUPS = 4


class VisualPageOperationPage(QWidget):
    back_requested = Signal()
    workspace_files_added = Signal(list)
    page_count_ready = Signal(object, int)
    page_count_failed = Signal(object)
    job_completed = Signal(object)

    def __init__(
        self,
        operation: OperationType,
        locale: Locale = "en",
        settings: AppSettings | None = None,
    ) -> None:
        super().__init__()
        self._operation = operation
        self._spec: ToolSpec = tool_spec_for_operation(operation)
        self._locale = locale
        self._settings = settings or AppSettings()
        self._input_path: Path | None = None
        self._page_count: int | None = None
        self._queued_page_count_path: Path | None = None
        self._output_path: Path | None = None
        self._output_dir: Path | None = None
        self._launch_context: ToolLaunchContext | None = None
        self._deleted_pages: set[int] = set()
        self._split_group_counter = 0
        self._split_groups: dict[str, PageOutputGroupWidget] = {}
        self._manual_dirty = False
        self._syncing_manual = False
        self._guidance_completed = False

        self._job_runner = QtJobRunner(self)
        self._page_count_runner = QtPageCountRunner(self)
        self._job_runner.finished.connect(self._operation_finished)
        self._page_count_runner.finished.connect(self._page_count_finished)
        self._guided_action_cue = GuidedActionCue(
            reduce_motion=self._settings.reduce_motion(),
        )

        self._description_label = QLabel()
        self._description_label.setObjectName("HelpText")
        self._description_label.setWordWrap(True)
        self._back_button = GhostButton()
        self._back_button.clicked.connect(self.back_requested.emit)

        self._input_panel = PdfInputPanel(multiple=False, locale=locale)
        self._input_panel.paths_selected.connect(self._handle_files)

        self._source_title = QLabel()
        self._source_title.setObjectName("SectionTitle")
        self._page_count_label = QLabel()
        self._page_count_label.setObjectName("HelpText")
        self._thumbnail_grid = PdfPageThumbnailGrid(
            mode="selection",
            layout_mode="selection_grid",
            locale=locale,
        )
        self._thumbnail_grid.set_external_drag_enabled(self._operation in _DRAG_OPERATIONS)
        self._thumbnail_grid.page_clicked.connect(self._source_page_clicked)
        self._thumbnail_grid.thumbnail_ready.connect(self._source_thumbnail_ready)
        self._thumbnail_grid.setVisible(False)

        source_panel = SurfacePanel(role="primary")
        source_layout = QVBoxLayout(source_panel)
        source_layout.setContentsMargins(18, 18, 18, 18)
        source_layout.setSpacing(10)
        source_layout.addWidget(self._source_title)
        source_layout.addWidget(self._page_count_label)
        source_layout.addWidget(self._thumbnail_grid, 1)
        self._source_panel = source_panel

        self._outputs_layout = QVBoxLayout()
        self._outputs_layout.setContentsMargins(0, 0, 0, 0)
        self._outputs_layout.setSpacing(12)
        self._add_split_group_button = SecondaryButton()
        self._add_split_group_button.clicked.connect(self._add_split_group)
        self._extract_group: PageOutputGroupWidget | None = None
        self._build_visual_outputs()

        content_row = QHBoxLayout()
        content_row.setContentsMargins(0, 0, 0, 0)
        content_row.setSpacing(14)
        content_row.addWidget(source_panel, 1)
        self._outputs_host: QWidget | None = None
        self._outputs_scroll: QScrollArea | None = None
        if self._operation is not OperationType.REMOVE_PAGES:
            outputs_host = QWidget()
            outputs_host.setObjectName("PageOutputsHost")
            outputs_host.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Expanding,
            )
            outputs_host.setLayout(self._outputs_layout)
            outputs_scroll = QScrollArea()
            outputs_scroll.setWidgetResizable(True)
            outputs_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
            outputs_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            outputs_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            outputs_scroll.setWidget(outputs_host)
            self._outputs_host = outputs_host
            self._outputs_scroll = outputs_scroll
            content_row.addWidget(outputs_scroll, 1)

        self._advanced_button = SecondaryButton()
        self._advanced_button.clicked.connect(self._toggle_advanced)
        self._ranges_label = QLabel()
        self._ranges_label.setObjectName("SectionTitle")
        self._ranges_label.setVisible(False)
        self._ranges_input = QLineEdit()
        self._ranges_input.setPlaceholderText(self._spec.page_range_placeholder)
        self._ranges_input.setVisible(False)
        self._ranges_input.textEdited.connect(self._manual_text_edited)

        self._output_label = QLabel(self._empty_output_text())
        self._output_label.setObjectName("HelpText")
        self._output_label.setWordWrap(True)
        self._output_button = SecondaryButton()
        self._output_button.clicked.connect(self._choose_output)
        self._action_button = PrimaryButton()
        self._action_button.clicked.connect(self._start_operation)
        self._action_button.setEnabled(False)
        self._required_step_label = QLabel()
        self._required_step_label.setObjectName("StatusText")
        self._required_step_label.setWordWrap(True)
        self._required_step_label.setVisible(False)
        self._status_label = QLabel()
        self._status_label.setObjectName("StatusText")
        self._status_label.setWordWrap(True)
        self._progress_overlay = ProgressOverlay()

        output_row = QHBoxLayout()
        output_row.addWidget(self._output_label, 1)
        output_row.addWidget(self._output_button)

        form_panel = SurfacePanel(role="primary")
        form_layout = QVBoxLayout(form_panel)
        form_layout.setContentsMargins(18, 18, 18, 18)
        form_layout.setSpacing(12)
        form_layout.addWidget(self._advanced_button)
        form_layout.addWidget(self._ranges_label)
        form_layout.addWidget(self._ranges_input)
        form_layout.addLayout(output_row)
        form_layout.addWidget(self._required_step_label)
        form_layout.addWidget(self._action_button)
        form_layout.addWidget(self._progress_overlay)
        form_layout.addWidget(self._status_label)

        toolbar = QHBoxLayout()
        toolbar.addWidget(self._back_button)
        toolbar.addStretch(1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 30, 32, 30)
        layout.setSpacing(16)
        layout.addWidget(self._description_label)
        layout.addLayout(toolbar)
        layout.addWidget(self._input_panel)
        layout.addLayout(content_row, 1)
        layout.addWidget(form_panel)
        self.set_locale(locale)
        self._clear_input_path()

    def set_workspace_document(self, document: WorkspaceDocument | None) -> None:
        if document is None:
            self._clear_input_path()
            return
        if self._input_path != document.path:
            self._set_input_path(document.path)

    def set_tool_launch_context(self, context: ToolLaunchContext | None) -> None:
        self._launch_context = context
        if context is None or not context.input_files:
            return
        if self._input_path != context.input_files[0]:
            self._set_input_path(context.input_files[0])

    def set_locale(self, locale: Locale) -> None:
        self._locale = locale
        self._description_label.setText(tr(self._spec.description_key, locale))
        self._back_button.setText(tr("button.back", locale))
        self._source_title.setText(tr("visual.source_pdf", locale))
        self._advanced_button.setText(tr("visual.advanced_mode", locale))
        self._ranges_label.setText(tr(self._spec.ranges_label_key, locale).upper())
        self._output_button.setText(tr(self._spec.output_button_key, locale).upper())
        self._action_button.setText(tr(self._spec.action_button_key, locale).upper())
        self._add_split_group_button.setText(tr("visual.add_output_pdf", locale).upper())
        self._input_panel.set_locale(locale)
        self._thumbnail_grid.set_locale(locale)
        for index, group in enumerate(self._split_groups.values(), start=1):
            group.set_title(tr("visual.output_pdf_n", locale, index=index))
            group.set_remove_text(tr("visual.remove_from_output", locale))
        if self._extract_group is not None:
            self._extract_group.set_title(tr("visual.extracted_pdf", locale))
            self._extract_group.set_remove_text(tr("visual.remove_from_output", locale))
        if self._input_path is None:
            self._page_count_label.setText(tr("page_count.empty", locale))
            self._status_label.setText(tr("viewer.no_pdf", locale))
        if self._output_path is None and self._output_dir is None:
            self._output_label.setText(self._empty_output_text())
        self._refresh_split_group_controls()
        self._update_action_state()

    def busy_document_paths(self) -> tuple[Path, ...]:
        if not self._job_runner.is_running() or self._input_path is None:
            return ()
        return (self._input_path,)

    def _build_visual_outputs(self) -> None:
        if self._operation is OperationType.SPLIT_BY_RANGES:
            self._add_split_group()
            self._add_split_group()
            self._outputs_layout.addWidget(self._add_split_group_button)
            return
        if self._operation is OperationType.EXTRACT_PAGES:
            group = PageOutputGroupWidget(
                "extract",
                tr("visual.extracted_pdf", self._locale),
                tr("visual.drop_extract", self._locale),
                remove_on_click=True,
                remove_text=tr("visual.remove_from_output", self._locale),
            )
            group.set_thumbnail_provider(self._thumbnail_icon_for_page)
            group.pages_dropped.connect(self._extract_pages_dropped)
            group.pages_changed.connect(self._extract_pages_changed)
            self._extract_group = group
            self._outputs_layout.addWidget(group)

    def _add_split_group(self) -> None:
        if len(self._split_groups) >= MAX_SPLIT_OUTPUT_GROUPS:
            self._refresh_split_group_controls()
            return
        self._split_group_counter += 1
        group_id = f"split-{self._split_group_counter}"
        group = PageOutputGroupWidget(
            group_id,
            tr("visual.output_pdf_n", self._locale, index=self._split_group_counter),
            tr("visual.drop_split", self._locale),
            remove_text=tr("visual.remove_from_output", self._locale),
        )
        group.set_thumbnail_provider(self._thumbnail_icon_for_page)
        group.pages_dropped.connect(self._split_pages_dropped)
        group.pages_changed.connect(self._split_pages_changed)
        self._split_groups[group_id] = group
        add_button_index = self._outputs_layout.indexOf(self._add_split_group_button)
        insert_at = add_button_index if add_button_index >= 0 else self._outputs_layout.count()
        self._outputs_layout.insertWidget(insert_at, group)
        self._refresh_split_group_controls()
        if hasattr(self, "_action_button"):
            self._update_action_state()

    def _refresh_split_group_controls(self) -> None:
        if self._operation is not OperationType.SPLIT_BY_RANGES:
            return
        group_count = len(self._split_groups)
        can_add = group_count < MAX_SPLIT_OUTPUT_GROUPS
        self._add_split_group_button.setEnabled(can_add)
        tooltip = (
            tr("visual.add_output_pdf", self._locale)
            if can_add
            else tr("visual.output_limit", self._locale, max_count=MAX_SPLIT_OUTPUT_GROUPS)
        )
        self._add_split_group_button.setToolTip(tooltip)
        if group_count <= 1:
            list_height = PAGE_OUTPUT_LIST_LARGE_HEIGHT
        elif group_count == 2:
            list_height = PAGE_OUTPUT_LIST_HEIGHT
        else:
            list_height = PAGE_OUTPUT_LIST_COMPACT_HEIGHT
        for group in self._split_groups.values():
            group.set_minimum_list_height(list_height)

    def _handle_files(self, paths: list[Path]) -> None:
        if not paths:
            return
        self._set_input_path(paths[0])
        self.workspace_files_added.emit(paths)

    def _set_input_path(self, path: Path) -> None:
        self._guidance_completed = False
        self._input_path = path
        self._page_count = None
        self._deleted_pages.clear()
        self._manual_dirty = False
        self._thumbnail_grid.clear_document()
        self._thumbnail_grid.setVisible(False)
        self._input_panel.set_loaded(True)
        self._page_count_label.setText(tr("page_count.loading", self._locale))
        self._status_label.setText("")
        self._clear_visual_outputs()
        self._update_action_state()
        if self._page_count_runner.is_running():
            self._queued_page_count_path = path
            return
        self._page_count_runner.start(path)

    def _clear_input_path(self) -> None:
        self._guidance_completed = False
        self._input_path = None
        self._page_count = None
        self._queued_page_count_path = None
        self._deleted_pages.clear()
        self._manual_dirty = False
        self._input_panel.set_loaded(False)
        self._thumbnail_grid.clear_document()
        self._thumbnail_grid.setVisible(False)
        self._page_count_label.setText(tr("page_count.empty", self._locale))
        self._status_label.setText(tr("viewer.no_pdf", self._locale))
        self._clear_visual_outputs()
        self._update_action_state()

    def _page_count_finished(self, result: PageCountResult) -> None:
        queued_path = self._queued_page_count_path
        self._queued_page_count_path = None
        if result.success:
            self.page_count_ready.emit(result.pdf_path, result.page_count)
        else:
            self.page_count_failed.emit(result.pdf_path)

        if self._input_path == result.pdf_path:
            if result.success:
                self._page_count = result.page_count
                self._page_count_label.setText(
                    tr("page_count.value", self._locale, count=result.page_count)
                )
                self._thumbnail_grid.set_document(result.pdf_path, result.page_count)
                self._thumbnail_grid.setVisible(True)
                self._input_panel.set_loaded(True)
                self._status_label.setText(result.user_message)
            else:
                self._page_count = None
                self._page_count_label.setText(tr("page_count.empty", self._locale))
                self._thumbnail_grid.setVisible(False)
                self._input_panel.set_loaded(False)
                self._status_label.setText(result.user_message)

        if queued_path is not None and queued_path != result.pdf_path:
            self._page_count_runner.start(queued_path)
            self._update_action_state()
            return
        self._update_action_state()

    def _source_page_clicked(self, page: int) -> None:
        if self._operation is OperationType.EXTRACT_PAGES and self._extract_group is not None:
            self._extract_group.add_pages((page,))
            return
        if self._operation is OperationType.REMOVE_PAGES:
            if page in self._deleted_pages:
                self._deleted_pages.remove(page)
            else:
                self._deleted_pages.add(page)
            self._sync_remove_state()

    def _split_pages_dropped(self, group_id: str, pages: tuple[int, ...]) -> None:
        moved_pages = set(pages)
        for other_id, group in self._split_groups.items():
            if other_id == group_id:
                continue
            group.set_pages(tuple(page for page in group.pages() if page not in moved_pages))
        target = self._split_groups[group_id]
        target.set_pages(_unique_pages(target.pages()))
        self._sync_split_state()

    def _split_pages_changed(self, _group_id: str, _pages: tuple[int, ...]) -> None:
        self._sync_split_state()

    def _extract_pages_dropped(self, group_id: str, pages: tuple[int, ...]) -> None:
        del group_id, pages
        if self._extract_group is not None:
            self._extract_group.set_pages(_unique_pages(self._extract_group.pages()))
        self._sync_extract_state()

    def _extract_pages_changed(self, _group_id: str, _pages: tuple[int, ...]) -> None:
        self._sync_extract_state()

    def _source_thumbnail_ready(self, page: int) -> None:
        for group in self._split_groups.values():
            group.refresh_page_thumbnail(page)
        if self._extract_group is not None:
            self._extract_group.refresh_page_thumbnail(page)

    def _thumbnail_icon_for_page(self, page: int):
        return self._thumbnail_grid.thumbnail_icon(page)

    def _sync_split_state(self) -> None:
        self._guidance_completed = False
        assigned = tuple(page for group in self._split_groups.values() for page in group.pages())
        self._thumbnail_grid.clear_page_marks()
        self._thumbnail_grid.set_page_marks(assigned, "assigned")
        self._sync_advanced_from_visual("")
        self._update_action_state()

    def _sync_extract_state(self) -> None:
        self._guidance_completed = False
        pages = self._extract_group.pages() if self._extract_group is not None else ()
        self._thumbnail_grid.clear_page_marks()
        self._thumbnail_grid.set_page_marks(pages, "assigned")
        self._sync_advanced_from_visual(pages_to_range_expression(pages))
        self._update_action_state()

    def _sync_remove_state(self) -> None:
        self._guidance_completed = False
        pages = tuple(sorted(self._deleted_pages))
        self._thumbnail_grid.clear_page_marks()
        self._thumbnail_grid.set_page_marks(pages, "deleted")
        self._sync_advanced_from_visual(pages_to_range_expression(pages))
        self._update_action_state()

    def _sync_advanced_from_visual(self, expression: str) -> None:
        if self._manual_dirty:
            return
        self._syncing_manual = True
        self._ranges_input.setText(expression)
        self._syncing_manual = False

    def _clear_visual_outputs(self) -> None:
        for group in self._split_groups.values():
            group.set_pages(())
        if self._extract_group is not None:
            self._extract_group.set_pages(())
        self._sync_advanced_from_visual("")

    def _manual_text_edited(self) -> None:
        if self._syncing_manual:
            return
        self._manual_dirty = True
        self._guidance_completed = False
        self._update_action_state()

    def _toggle_advanced(self) -> None:
        visible = not self._ranges_input.isVisible()
        self._ranges_label.setVisible(visible)
        self._ranges_input.setVisible(visible)

    def _choose_output(self) -> None:
        if self._spec.output_mode == "directory":
            directory = QFileDialog.getExistingDirectory(
                self,
                tr("button.choose_folder", self._locale),
                self._default_output_directory(),
            )
            if directory:
                self._guidance_completed = False
                self._output_dir = Path(directory)
                self._output_label.setText(str(self._output_dir))
                self._output_label.setToolTip(str(self._output_dir))
        else:
            file_name, _ = QFileDialog.getSaveFileName(
                self,
                tr("button.choose_output", self._locale),
                self._default_output_path_text(),
                "PDF (*.pdf)",
            )
            if file_name:
                self._guidance_completed = False
                output_path = Path(file_name)
                if output_path.suffix.lower() != ".pdf":
                    output_path = output_path.with_suffix(".pdf")
                self._output_path = output_path
                self._output_label.setText(str(output_path))
                self._output_label.setToolTip(str(output_path))
        self._update_action_state()

    def _start_operation(self) -> None:
        if self._job_runner.is_running():
            return
        try:
            job = self._build_job()
        except ValueError as exc:
            self._show_error(str(exc))
            return
        self._set_guided_step(None)
        self._action_button.setEnabled(False)
        self._status_label.setText(self._spec.progress_message)
        self._progress_overlay.show_message(self._spec.progress_message)
        self._job_runner.start(job)

    def _build_job(self) -> JobRequest:
        if self._input_path is None or self._page_count is None:
            raise ValueError(tr("visual.error.no_pdf", self._locale))
        output_dir = self._job_output_dir()
        options = self._job_options()
        return JobRequest(
            operation=self._operation,
            input_files=(self._input_path,),
            output_dir=output_dir,
            options=options,
            naming_strategy="explicit",
            job_id=str(uuid.uuid4()),
        )

    def _job_output_dir(self) -> Path:
        if self._spec.output_mode == "directory":
            if self._output_dir is None:
                raise ValueError(tr("visual.error.no_output_dir", self._locale))
            return self._output_dir
        if self._output_path is None:
            raise ValueError(tr("visual.error.no_output", self._locale))
        return self._output_path.parent

    def _job_options(self) -> dict[str, object]:
        manual_range_active = (
            self._manual_dirty
            and self._ranges_input.isVisible()
            and self._ranges_input.text().strip()
        )
        if manual_range_active:
            return self._manual_job_options()
        if self._operation is OperationType.SPLIT_BY_RANGES:
            groups = tuple(
                PageOutputGroupModel(group_id, group.pages())
                for group_id, group in self._split_groups.items()
            )
            return SplitPlanModel(self._page_count or 0, groups).to_job_options()
        if self._operation is OperationType.EXTRACT_PAGES:
            pages = self._extract_group.pages() if self._extract_group is not None else ()
            page_numbers = _unique_pages(pages)
            validate_page_numbers(page_numbers, self._page_count or 0)
            return {"page_numbers": page_numbers, "output_path": self._output_path}
        if self._operation is OperationType.REMOVE_PAGES:
            page_numbers = PageSelectionModel.from_pages(
                self._page_count or 0,
                tuple(self._deleted_pages),
            ).as_page_numbers(allow_all=False)
            return {"page_numbers": page_numbers, "output_path": self._output_path}
        raise ValueError(tr("visual.error.invalid_plan", self._locale))

    def _manual_job_options(self) -> dict[str, object]:
        if self._page_count is None:
            raise ValueError(tr("visual.error.no_pdf", self._locale))
        if self._operation is OperationType.SPLIT_BY_RANGES:
            ranges = parse_page_range_groups(self._ranges_input.text())
            validate_page_ranges(ranges, self._page_count)
            return {"ranges": ranges}
        page_numbers = tuple(parse_page_ranges(self._ranges_input.text()))
        validate_page_numbers(page_numbers, self._page_count)
        if (
            self._operation is OperationType.REMOVE_PAGES
            and len(set(page_numbers)) >= self._page_count
        ):
            raise ValueError(tr("visual.error.remove_all", self._locale))
        return {"page_numbers": page_numbers, "output_path": self._output_path}

    def _update_action_state(self) -> None:
        plan_ready = (
            self._input_path is not None
            and self._page_count is not None
            and self._has_valid_plan()
            and not self._job_runner.is_running()
            and not self._page_count_runner.is_running()
        )
        ready = plan_ready and self._has_output()
        self._action_button.setEnabled(ready)
        guided_button: QWidget | None = None
        if plan_ready and not self._guidance_completed:
            guided_button = self._action_button if self._has_output() else self._output_button
        self._set_guided_step(guided_button)

    def _set_guided_step(self, button: QWidget | None) -> None:
        self._guided_action_cue.set_reduce_motion(self._settings.reduce_motion())
        self._guided_action_cue.set_target(button)
        self._required_step_label.setVisible(button is not None)
        if button is None:
            self._required_step_label.setText("")
            return
        if button is self._output_button:
            text = tr("guidance.next.choose_output", self._locale)
        else:
            text = tr(
                "guidance.next.execute",
                self._locale,
                action=tr(self._spec.action_button_key, self._locale).lower(),
            )
        self._required_step_label.setText(text)

    def _has_valid_plan(self) -> bool:
        try:
            self._job_options()
        except ValueError:
            return False
        return True

    def _has_output(self) -> bool:
        if self._spec.output_mode == "directory":
            return self._output_dir is not None
        return self._output_path is not None

    def _operation_finished(self, result: JobResult) -> None:
        self._guidance_completed = result.success
        self._update_action_state()
        self._progress_overlay.hide_overlay()
        self._status_label.setText(self._result_message(result))
        if result.success:
            self._open_output_folder_if_requested(result)
            show_info(self, self._spec.success_title, self._result_message(result))
            self.job_completed.emit(result)
            return
        self.job_completed.emit(result)
        self._show_error(result.user_message, result.technical_detail)

    def _empty_output_text(self) -> str:
        return tr(self._spec.output_label_key, self._locale)

    def _default_output_name(self) -> str:
        if self._launch_context is not None and self._launch_context.suggested_output_basename:
            return self._launch_context.suggested_output_basename
        stem = self._input_path.stem if self._input_path is not None else "document"
        return f"{stem}{self._spec.default_output_suffix}.pdf"

    def _default_output_path_text(self) -> str:
        if (
            self._launch_context is not None
            and self._launch_context.suggested_output_dir is not None
        ):
            return str(self._launch_context.suggested_output_dir / self._default_output_name())
        output_dir = self._settings.default_output_dir()
        if output_dir is None:
            return self._default_output_name()
        return str(output_dir / self._default_output_name())

    def _default_output_directory(self) -> str:
        output_dir = self._settings.default_output_dir()
        return str(output_dir) if output_dir is not None else ""

    def _result_message(self, result: JobResult) -> str:
        if not result.output_files:
            return result.user_message
        files = "\n".join(str(path) for path in result.output_files)
        return f"{result.user_message}\n\nFichier(s) genere(s) :\n{files}"

    def _show_error(self, message: str, detail: str = "") -> None:
        self._progress_overlay.hide_overlay()
        show_error(self, "Operation impossible", message, detail)

    def _open_output_folder_if_requested(self, result: JobResult) -> None:
        if self._settings.after_job_behavior() != "open_output_folder" or not result.output_files:
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(result.output_files[0].parent)))


_DRAG_OPERATIONS = {OperationType.SPLIT_BY_RANGES, OperationType.EXTRACT_PAGES}


def _unique_pages(pages: tuple[int, ...] | list[int]) -> tuple[int, ...]:
    seen: set[int] = set()
    unique: list[int] = []
    for page in pages:
        if page in seen:
            continue
        seen.add(page)
        unique.append(page)
    return tuple(unique)
