from __future__ import annotations

import uuid
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from priveopdf.app.settings import AppSettings
from priveopdf.domain.document_context import ToolLaunchContext
from priveopdf.domain.errors import DangerousOutputError
from priveopdf.domain.jobs import JobRequest, JobResult, OperationType
from priveopdf.domain.page_plans import (
    PageOutputGroupModel,
    PageSelectionModel,
    SplitPlanModel,
    every_n_pages_groups,
    split_group_file_names,
    split_range_file_names,
)
from priveopdf.domain.page_ranges import (
    parse_page_range_groups,
    parse_page_ranges,
    validate_page_numbers,
    validate_page_ranges,
)
from priveopdf.ui.components import (
    GhostButton,
    OutputTargetField,
    PageOutputGroupWidget,
    PdfInputPanel,
    PdfPageThumbnailGrid,
    SecondaryButton,
    SourceCheck,
    SurfacePanel,
    ToolActionBar,
    install_page_tool_layout,
    job_result_message,
    open_output_folder_if_requested,
)
from priveopdf.ui.components.page_groups import (
    PAGE_OUTPUT_LIST_COMPACT_HEIGHT,
    PAGE_OUTPUT_LIST_HEIGHT,
    PAGE_OUTPUT_LIST_LARGE_HEIGHT,
)
from priveopdf.ui.components.page_thumbnails import pages_to_range_expression
from priveopdf.ui.components.tool_flow import page_count_text
from priveopdf.ui.i18n import Locale, tr
from priveopdf.ui.theme.tokens import SPACING
from priveopdf.ui.tool_pages.page_tool_mixin import PageToolMixin
from priveopdf.ui.tool_specs import ToolSpec, tool_spec_for_operation
from priveopdf.workers.job_runner import PageCountResult, QtJobRunner, QtPageCountRunner

MAX_SPLIT_OUTPUT_GROUPS = 4
# L5: one "Split" list, the most common case first; no separate advanced mode.
SPLIT_MODES = ("every_n", "single_pages", "groups", "ranges")
# Names listed in full up to this count; beyond, the first two and the last one.
ANNOUNCED_NAMES_IN_FULL = 3


class VisualPageOperationPage(PageToolMixin, QWidget):
    back_requested = Signal()
    workspace_files_added = Signal(list)
    page_count_ready = Signal(object, int)
    page_count_failed = Signal(object, str)
    job_completed = Signal(object)
    output_pdf_requested = Signal(object)

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
        self._launch_context: ToolLaunchContext | None = None
        self._deleted_pages: set[int] = set()
        self._split_group_counter = 0
        self._split_groups: dict[str, PageOutputGroupWidget] = {}
        self._manual_dirty = False
        self._syncing_manual = False

        self._job_runner = QtJobRunner(self)
        self._page_count_runner = QtPageCountRunner(self)
        self._job_runner.finished.connect(self._operation_finished)
        self._page_count_runner.finished.connect(self._page_count_finished)

        self._description_label = QLabel()
        self._description_label.setObjectName("HelpText")
        self._description_label.setWordWrap(True)
        self._back_button = GhostButton()
        self._back_button.clicked.connect(self.back_requested.emit)

        self._input_panel = PdfInputPanel(multiple=False, locale=locale)
        self._input_panel.paths_selected.connect(self._handle_files)
        # L4: a protected or damaged source is reported under it.
        self._source_check = SourceCheck(locale)
        self._source_check.changed.connect(self._update_action_state)
        # E2: the page names the file it will act on, with its page count.
        self._input_status = QLabel()
        self._input_status.setObjectName("HelpText")
        self._input_status.setWordWrap(True)

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
        content_row.addWidget(source_panel, 3)
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
            content_row.addWidget(outputs_scroll, 2)

        # Split modes (L5): every N pages (default), one page per file, drag groups, ranges.
        self._split_mode_label = QLabel()
        self._split_mode_label.setObjectName("SectionTitle")
        self._split_mode = QComboBox()
        self._split_mode.setObjectName("SplitModeCombo")
        self._split_mode.currentIndexChanged.connect(self._split_mode_changed)
        self._split_size_label = QLabel()
        self._split_size_label.setObjectName("HelpText")
        self._split_size = QSpinBox()
        self._split_size.setObjectName("SplitSizeInput")
        # L5: N = 2 is shown from the start; the range follows the PDF once loaded.
        self._split_size.setRange(1, 2)
        self._split_size.setValue(2)
        self._split_size.valueChanged.connect(self._split_settings_changed)
        self._split_announcement = QLabel()
        self._split_announcement.setObjectName("HelpText")
        self._split_announcement.setWordWrap(True)
        is_split = self._operation is OperationType.SPLIT_BY_RANGES
        for widget in (
            self._split_mode_label,
            self._split_mode,
            self._split_announcement,
        ):
            widget.setVisible(is_split)
        self._advanced_button = SecondaryButton()
        self._advanced_button.clicked.connect(self._toggle_advanced)
        self._ranges_label = QLabel()
        self._ranges_label.setObjectName("SectionTitle")
        self._ranges_label.setVisible(False)
        self._ranges_input = QLineEdit()
        self._ranges_input.setPlaceholderText(self._spec.page_range_placeholder)
        self._ranges_input.setVisible(False)
        self._ranges_input.textEdited.connect(self._manual_text_edited)

        self._output = OutputTargetField(self._spec.output_mode, locale)
        self._output.changed.connect(self._output_changed)
        self._action_bar = ToolActionBar(locale)
        self._action_bar.set_action_text_key(self._spec.action_button_key)
        self._action_bar.action_requested.connect(self._start_operation)
        self._action_bar.cancel_requested.connect(self._job_runner.cancel)
        self._action_bar.open_pdf_requested.connect(self.output_pdf_requested.emit)
        self._action_button = self._action_bar.action_button()

        # Rule 1, page-editing adaptation: pages on the left; settings (advanced
        # ranges), output and action stacked in the right column.
        self._settings_panel = SurfacePanel(role="primary")
        settings_layout = QVBoxLayout(self._settings_panel)
        settings_layout.setContentsMargins(*(SPACING["lg"],) * 4)
        settings_layout.setSpacing(SPACING["sm"])
        settings_layout.addWidget(self._split_mode_label)
        settings_layout.addWidget(self._split_mode)
        size_row = QHBoxLayout()
        size_row.setSpacing(SPACING["sm"])
        size_row.addWidget(self._split_size_label, 1)
        size_row.addWidget(self._split_size)
        settings_layout.addLayout(size_row)
        settings_layout.addWidget(self._advanced_button)
        settings_layout.addWidget(self._ranges_label)
        settings_layout.addWidget(self._ranges_input)

        self._output_panel = SurfacePanel(role="primary")
        output_layout = QVBoxLayout(self._output_panel)
        output_layout.setContentsMargins(*(SPACING["lg"],) * 4)
        output_layout.setSpacing(SPACING["sm"])
        output_layout.addWidget(self._output)
        output_layout.addWidget(self._split_announcement)
        output_layout.addWidget(self._action_bar)

        pages = QWidget()
        pages.setLayout(content_row)
        install_page_tool_layout(
            self,
            back=self._back_button,
            header=(
                self._description_label,
                self._input_panel,
                self._input_status,
                self._source_check,
            ),
            pages=pages,
            side_panels=(self._settings_panel, self._output_panel),
        )
        self.set_locale(locale)
        self._clear_input_path()

    def set_locale(self, locale: Locale) -> None:
        self._locale = locale
        if self._input_path is not None and self._page_count is not None:
            self._input_status.setText(
                tr(
                    "blank.ready",
                    locale,
                    name=self._input_path.name,
                    pages=page_count_text(self._page_count, locale),
                )
            )
        self._description_label.setText(tr(self._spec.description_key, locale))
        self._back_button.setText(tr("button.back", locale))
        self._source_title.setText(tr("visual.source_pdf", locale))
        self._advanced_button.setText(tr("visual.advanced_mode", locale))
        self._split_mode_label.setText(tr("split.mode.label", locale))
        self._split_size_label.setText(tr("split.size.label", locale))
        current_mode = self._split_mode_key()
        self._split_mode.blockSignals(True)
        self._split_mode.clear()
        for mode in SPLIT_MODES:
            self._split_mode.addItem(tr(f"split.mode.{mode}", locale), mode)
        self._split_mode.setCurrentIndex(SPLIT_MODES.index(current_mode))
        self._split_mode.blockSignals(False)
        self._refresh_split_mode_visibility()
        self._ranges_label.setText(tr(self._spec.ranges_label_key, locale).upper())
        self._add_split_group_button.setText(tr("visual.add_output_pdf", locale).upper())
        self._sync_outputs_width()
        self._input_panel.set_locale(locale)
        self._source_check.set_locale(locale)
        self._thumbnail_grid.set_locale(locale)
        for index, group in enumerate(self._split_groups.values(), start=1):
            group.set_title(tr("visual.output_pdf_n", locale, index=index))
            group.set_remove_text(tr("visual.remove_from_output", locale))
        if self._extract_group is not None:
            self._extract_group.set_title(tr("visual.extracted_pdf", locale))
            self._extract_group.set_remove_text(tr("visual.remove_from_output", locale))
        if self._input_path is None:
            self._page_count_label.setText(tr("page_count.empty", locale))
        self._output.set_locale(locale)
        self._action_bar.set_locale(locale)
        self._propose_output()
        self._refresh_split_group_controls()
        self._update_action_state()

    def busy_document_paths(self) -> tuple[Path, ...]:
        if not self._job_runner.is_running() or self._input_path is None:
            return ()
        return (self._input_path,)

    def _sync_outputs_width(self) -> None:
        """L7 / E9: the output column never gets narrower than its content.

        Its horizontal scroll bar is off, so a narrower column clipped the drop
        hints and the add button at 1180 x 700; the source pages take the rest.
        """

        scroll, host = self._outputs_scroll, self._outputs_host
        if scroll is None or host is None:
            return
        host.adjustSize()
        bar = scroll.verticalScrollBar().sizeHint().width()
        scroll.setMinimumWidth(host.minimumSizeHint().width() + bar + 2 * scroll.frameWidth())

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
        if hasattr(self, "_action_bar"):
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
        self._input_path = path
        self._page_count = None
        self._deleted_pages.clear()
        self._manual_dirty = False
        self._thumbnail_grid.clear_document()
        self._thumbnail_grid.setVisible(False)
        self._input_panel.set_loaded(True)
        self._source_check.set_sources([path])
        self._page_count_label.setText(tr("page_count.loading", self._locale))
        self._input_status.setText(tr("blank.loading", self._locale, name=path.name))
        self._action_bar.clear_result()
        self._output.clear()
        self._propose_output()
        self._clear_visual_outputs()
        self._update_action_state()
        if self._page_count_runner.is_running():
            self._queued_page_count_path = path
            return
        self._page_count_runner.start(path)

    def _clear_input_path(self) -> None:
        self._input_path = None
        self._page_count = None
        self._queued_page_count_path = None
        self._deleted_pages.clear()
        self._manual_dirty = False
        self._input_panel.set_loaded(False)
        self._input_status.setText("")
        self._source_check.clear()
        self._thumbnail_grid.clear_document()
        self._thumbnail_grid.setVisible(False)
        self._page_count_label.setText(tr("page_count.empty", self._locale))
        self._action_bar.clear_result()
        self._output.clear()
        self._clear_visual_outputs()
        self._update_action_state()

    def _page_count_finished(self, result: PageCountResult) -> None:
        queued_path = self._queued_page_count_path
        self._queued_page_count_path = None
        if result.success:
            self.page_count_ready.emit(result.pdf_path, result.page_count)
        else:
            self.page_count_failed.emit(result.pdf_path, result.technical_detail)
        self._source_check.record(result)

        if self._input_path == result.pdf_path:
            if result.success:
                self._page_count = result.page_count
                self._page_count_label.setText(
                    tr("page_count.value", self._locale, count=result.page_count)
                )
                self._input_status.setText(
                    tr(
                        "blank.ready",
                        self._locale,
                        name=result.pdf_path.name,
                        pages=page_count_text(result.page_count, self._locale),
                    )
                )
                self._thumbnail_grid.set_document(result.pdf_path, result.page_count)
                self._thumbnail_grid.setVisible(True)
                self._input_panel.set_loaded(True)
                self._split_size.blockSignals(True)
                self._split_size.setRange(1, max(1, result.page_count))
                self._split_size.setValue(min(2, result.page_count))
                self._split_size.blockSignals(False)
            else:
                self._page_count = None
                self._page_count_label.setText(tr("page_count.empty", self._locale))
                self._thumbnail_grid.setVisible(False)
                # L4: a protected or damaged PDF is reported under the source,
                # with `Change PDF` kept; other failures stay at the action.
                reported = bool(self._source_check.problem())
                self._input_panel.set_loaded(reported)
                self._input_status.setText(result.pdf_path.name if reported else "")
                if not reported:
                    self._action_bar.show_error(_page_count_error(result, self._locale))

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
        assigned = tuple(page for group in self._split_groups.values() for page in group.pages())
        self._action_bar.clear_result()  # rule 8: the shown result no longer matches
        self._thumbnail_grid.clear_page_marks()
        self._thumbnail_grid.set_page_marks(assigned, "assigned")
        self._sync_advanced_from_visual("")
        self._update_action_state()

    def _sync_extract_state(self) -> None:
        pages = self._extract_group.pages() if self._extract_group is not None else ()
        self._action_bar.clear_result()  # rule 8
        self._thumbnail_grid.clear_page_marks()
        self._thumbnail_grid.set_page_marks(pages, "assigned")
        self._sync_advanced_from_visual(pages_to_range_expression(pages))
        self._update_action_state()

    def _sync_remove_state(self) -> None:
        pages = tuple(sorted(self._deleted_pages))
        self._action_bar.clear_result()  # rule 8
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
        self._action_bar.clear_result()
        self._update_action_state()

    def _toggle_advanced(self) -> None:
        visible = not self._ranges_input.isVisible()
        self._ranges_label.setVisible(visible)
        self._ranges_input.setVisible(visible)

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
        output = self._output.path()
        if output is None:
            raise ValueError(tr("visual.error.no_output", self._locale))
        return output if self._spec.output_mode == "directory" else output.parent

    def _job_options(self) -> dict[str, object]:
        if self._manual_range_active():
            return self._manual_job_options()
        if self._operation is OperationType.SPLIT_BY_RANGES:
            mode = self._split_mode_key()
            if mode == "ranges":
                raise ValueError(tr("split.required.ranges", self._locale))
            if mode != "groups":
                size = 1 if mode == "single_pages" else self._split_size.value()
                return {"page_groups": every_n_pages_groups(self._page_count or 0, size)}
            groups = tuple(
                PageOutputGroupModel(group_id, group.pages())
                for group_id, group in self._split_groups.items()
            )
            return SplitPlanModel(self._page_count or 0, groups).to_job_options()
        if self._operation is OperationType.EXTRACT_PAGES:
            pages = self._extract_group.pages() if self._extract_group is not None else ()
            page_numbers = _unique_pages(pages)
            validate_page_numbers(page_numbers, self._page_count or 0)
            return {"page_numbers": page_numbers, "output_path": self._output.path()}
        if self._operation is OperationType.REMOVE_PAGES:
            page_numbers = PageSelectionModel.from_pages(
                self._page_count or 0,
                tuple(self._deleted_pages),
            ).as_page_numbers(allow_all=False)
            return {"page_numbers": page_numbers, "output_path": self._output.path()}
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
        return {"page_numbers": page_numbers, "output_path": self._output.path()}

    def _manual_range_active(self) -> bool:
        if self._operation is OperationType.SPLIT_BY_RANGES:
            return self._split_mode_key() == "ranges" and bool(self._ranges_input.text().strip())
        return bool(
            self._manual_dirty
            and self._ranges_input.isVisible()
            and self._ranges_input.text().strip()
        )

    def _blocker(self) -> str:
        if self._input_path is None:
            return tr("tool.required.source", self._locale)
        problem = self._source_check.blocker_text()
        if problem:
            return problem
        if self._page_count is None or self._page_count_runner.is_running():
            return tr("page_count.loading", self._locale)
        if self._operation is OperationType.SPLIT_BY_RANGES and self._page_count < 2:
            return tr("split.required.pages", self._locale)
        if not self._has_valid_plan():
            if self._manual_range_active():
                try:
                    self._manual_job_options()
                except ValueError as error:
                    remove_all = tr("visual.error.remove_all", self._locale)
                    if str(error) == remove_all:
                        return remove_all
                return tr("visual.required.ranges", self._locale)
            if self._operation is OperationType.REMOVE_PAGES and self._deleted_pages:
                return tr("visual.error.remove_all", self._locale)
            if self._split_mode_key() == "ranges" and self._is_split():
                return tr("split.required.ranges", self._locale)
            return tr(f"visual.required.{self._spec.key}", self._locale)
        if self._split_copies_whole_document():
            return tr("split.required.parts", self._locale)
        if self._output.path() is None:
            return tr("tool.required.output", self._locale)
        existing = self._existing_split_file_name()
        if existing:
            return tr("split.required.free_names", self._locale, name=existing)
        return ""

    def _update_action_state(self) -> None:
        running = self._job_runner.is_running()
        self._output.setEnabled(not running)
        self._input_panel.setEnabled(not running)
        # Settings are frozen while the job runs: the result shown at the end
        # always matches the settings that produced it.
        self._settings_panel.setEnabled(not running)
        self._source_panel.setEnabled(not running)
        for group in self._split_groups.values():
            group.setEnabled(not running)
        if self._extract_group is not None:
            self._extract_group.setEnabled(not running)
        self._add_split_group_button.setEnabled(not running)
        self._action_bar.set_blocker(self._blocker())
        self._refresh_split_announcement()

    def _split_mode_key(self) -> str:
        mode = self._split_mode.currentData()
        return mode if mode in SPLIT_MODES else SPLIT_MODES[0]

    def _split_mode_changed(self, _index: int) -> None:
        self._refresh_split_mode_visibility()
        self._split_settings_changed()

    def _split_settings_changed(self, *_args: object) -> None:
        self._action_bar.clear_result()
        self._update_action_state()

    def _is_split(self) -> bool:
        return self._operation is OperationType.SPLIT_BY_RANGES

    def _refresh_split_mode_visibility(self) -> None:
        is_split = self._is_split()
        mode = self._split_mode_key()
        every_n = is_split and mode == "every_n"
        self._split_size_label.setVisible(every_n)
        self._split_size.setVisible(every_n)
        if not is_split:
            return
        # L5 / E6: each way of splitting is one choice of the list; drag groups
        # and typed ranges only show in their own mode.
        if self._outputs_scroll is not None:
            self._outputs_scroll.setVisible(mode == "groups")
        self._advanced_button.setVisible(False)
        self._ranges_label.setVisible(mode == "ranges")
        self._ranges_input.setVisible(mode == "ranges")

    def _split_file_names(self) -> tuple[str, ...]:
        """Names the engine will write, announced before the action (contract, rule 4)."""

        if self._operation is not OperationType.SPLIT_BY_RANGES or self._input_path is None:
            return ()
        try:
            options = self._job_options()
            ranges = options.get("ranges")
            if ranges:
                labels = tuple(page_range.label for page_range in ranges)
                return split_range_file_names(self._input_path.stem, labels)
            groups = options.get("page_groups") or ()
            return split_group_file_names(self._input_path.stem, len(groups))
        except (ValueError, DangerousOutputError):
            return ()

    def _split_copies_whole_document(self) -> bool:
        if self._operation is not OperationType.SPLIT_BY_RANGES or not self._page_count:
            return False
        try:
            options = self._job_options()
        except ValueError:
            return False
        everything = tuple(range(1, self._page_count + 1))
        ranges = options.get("ranges")
        if ranges:
            return len(ranges) == 1 and ranges[0].pages == everything
        groups = options.get("page_groups") or ()
        return len(groups) == 1 and tuple(groups[0]) == everything

    def _existing_split_file_name(self) -> str:
        directory = self._output.path()
        if self._operation is not OperationType.SPLIT_BY_RANGES or directory is None:
            return ""
        return next((name for name in self._split_file_names() if (directory / name).exists()), "")

    def _refresh_split_announcement(self) -> None:
        names = self._split_file_names()
        visible = bool(names) and not self._job_runner.is_running()
        self._split_announcement.setVisible(visible)
        if not visible:
            return
        if len(names) <= ANNOUNCED_NAMES_IN_FULL:
            listed = ", ".join(names)
        else:
            listed = f"{names[0]}, {names[1]}, …, {names[-1]}"
        key = "split.announce.one" if len(names) == 1 else "split.announce.many"
        self._split_announcement.setText(tr(key, self._locale, count=len(names), names=listed))

    def _has_valid_plan(self) -> bool:
        try:
            self._job_options()
        except ValueError:
            return False
        return True

    def _operation_finished(self, result: JobResult) -> None:
        if result.success:
            # Next free name first: a destination change clears the displayed result.
            self._output.refresh()
        self._action_bar.finish(result, job_result_message(result, self._locale, self._spec.key))
        self._update_action_state()
        if result.success:
            open_output_folder_if_requested(self._settings, result)
        self.job_completed.emit(result)


def _page_count_error(result: PageCountResult, locale: Locale) -> str:
    failure = JobResult(False, (), (), "-", result.technical_detail or "invalid_pdf")
    return job_result_message(failure, locale)


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
