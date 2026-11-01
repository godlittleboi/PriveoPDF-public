from __future__ import annotations

import uuid
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from priveopdf.app.settings import AppSettings
from priveopdf.domain.document_context import ToolLaunchContext
from priveopdf.domain.jobs import JobRequest, JobResult, OperationType
from priveopdf.domain.page_ranges import (
    parse_page_order,
    parse_page_range_groups,
    parse_page_ranges,
    validate_page_assembly,
    validate_page_numbers,
    validate_page_ranges,
)
from priveopdf.ui.components import (
    ElidedLabel,
    GhostButton,
    OutputTargetField,
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
from priveopdf.ui.i18n import Locale, tr
from priveopdf.ui.theme.tokens import SPACING
from priveopdf.ui.tool_pages.page_tool_mixin import PageToolMixin
from priveopdf.ui.tool_specs import ToolSpec, tool_spec_for_operation
from priveopdf.workers.job_runner import PageCountResult, QtJobRunner, QtPageCountRunner


class PageOperationPage(PageToolMixin, QWidget):
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
        self._job_runner = QtJobRunner(self)
        self._page_count_runner = QtPageCountRunner(self)
        self._job_runner.finished.connect(self._operation_finished)
        self._page_count_runner.finished.connect(self._page_count_finished)
        self._syncing_visual_selection = False

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

        self._thumbnail_grid = PdfPageThumbnailGrid(
            mode=self._thumbnail_mode(),
            layout_mode=self._thumbnail_layout_mode(),
            locale=locale,
        )
        self._thumbnail_grid.selection_changed.connect(self._thumbnail_selection_changed)
        self._thumbnail_grid.order_changed.connect(self._thumbnail_order_changed)
        self._thumbnail_grid.split_ranges_changed.connect(self._thumbnail_split_ranges_changed)
        self._thumbnail_grid.setVisible(False)

        self._input_label = ElidedLabel(tr("input.none_pdf", locale))
        self._input_label.setObjectName("HelpText")
        self._page_count_label = QLabel(tr("page_count.empty", locale))
        self._page_count_label.setObjectName("HelpText")

        self._ranges_label = QLabel()
        self._ranges_label.setObjectName("SectionTitle")
        self._ranges_input = QLineEdit()
        self._ranges_input.setPlaceholderText(self._ranges_placeholder())
        self._ranges_input.textChanged.connect(self._plan_changed)
        self._advanced_button = SecondaryButton()
        self._advanced_button.clicked.connect(self._toggle_advanced)
        self._advanced_button.setVisible(self._spec.input_mode == "complete_order")
        if self._spec.input_mode == "complete_order":
            self._ranges_label.setVisible(False)
            self._ranges_input.setVisible(False)

        self._help_label = QLabel()
        self._help_label.setObjectName("HelpText")
        self._help_label.setWordWrap(True)
        self._help_label.setVisible(bool(self._help_text()))
        if self._spec.input_mode == "complete_order":
            self._help_label.setVisible(False)

        self._angle_input = QComboBox()
        self._angle_input.addItem("90", 90)
        self._angle_input.addItem("180", 180)
        self._angle_input.addItem("270", 270)
        self._angle_input.currentIndexChanged.connect(self._update_action_state)
        self._angle_input.setVisible(self._spec.requires_rotation_angle)
        self._angle_label = QLabel()
        self._angle_label.setObjectName("SectionTitle")
        self._angle_label.setVisible(self._spec.requires_rotation_angle)

        self._move_page_up_button = SecondaryButton()
        self._move_page_up_button.clicked.connect(lambda: self._move_selected_thumbnail(-1))
        self._move_page_down_button = SecondaryButton()
        self._move_page_down_button.clicked.connect(lambda: self._move_selected_thumbnail(1))
        self._duplicate_page_button = SecondaryButton()
        self._duplicate_page_button.clicked.connect(self._duplicate_selected_thumbnail)
        self._move_page_up_button.setVisible(self._spec.input_mode == "complete_order")
        self._move_page_down_button.setVisible(self._spec.input_mode == "complete_order")
        self._duplicate_page_button.setVisible(self._spec.input_mode == "complete_order")

        self._output = OutputTargetField(self._spec.output_mode, locale)
        self._output.changed.connect(self._output_changed)
        self._action_bar = ToolActionBar(locale)
        self._action_bar.set_action_text_key(self._spec.action_button_key)
        self._action_bar.action_requested.connect(self._start_operation)
        self._action_bar.cancel_requested.connect(self._job_runner.cancel)
        self._action_bar.open_pdf_requested.connect(self.output_pdf_requested.emit)
        self._action_button = self._action_bar.action_button()

        angle_row = QHBoxLayout()
        angle_row.addWidget(self._angle_label)
        angle_row.addWidget(self._angle_input)
        angle_row.addStretch(1)

        reorder_buttons = QGridLayout()
        reorder_buttons.setSpacing(SPACING["sm"])
        reorder_buttons.addWidget(self._move_page_up_button, 0, 0)
        reorder_buttons.addWidget(self._move_page_down_button, 0, 1)
        reorder_buttons.addWidget(self._duplicate_page_button, 1, 0, 1, 2)

        # Rule 1, page-editing adaptation: pages on the left; settings, output and
        # action stacked in the right column.
        self._settings_panel = SurfacePanel(role="primary")
        settings_layout = QVBoxLayout(self._settings_panel)
        settings_layout.setContentsMargins(*(SPACING["lg"],) * 4)
        settings_layout.setSpacing(SPACING["sm"])
        settings_layout.addWidget(self._input_label)
        settings_layout.addWidget(self._page_count_label)
        settings_layout.addLayout(reorder_buttons)
        settings_layout.addWidget(self._advanced_button)
        settings_layout.addWidget(self._ranges_label)
        settings_layout.addWidget(self._ranges_input)
        settings_layout.addWidget(self._help_label)
        settings_layout.addLayout(angle_row)

        self._output_panel = SurfacePanel(role="primary")
        output_layout = QVBoxLayout(self._output_panel)
        output_layout.setContentsMargins(*(SPACING["lg"],) * 4)
        output_layout.setSpacing(SPACING["sm"])
        output_layout.addWidget(self._output)
        output_layout.addWidget(self._action_bar)

        install_page_tool_layout(
            self,
            back=self._back_button,
            header=(self._description_label, self._input_panel, self._source_check),
            pages=self._thumbnail_grid,
            side_panels=(self._settings_panel, self._output_panel),
        )
        self.set_locale(locale)

    def _handle_files(self, paths: list[Path]) -> None:
        if not paths:
            return
        self._set_input_path(paths[0])
        self.workspace_files_added.emit(paths)

    def _set_input_path(self, path: Path) -> None:
        self._input_path = path
        self._page_count = None
        self._thumbnail_grid.clear_document()
        self._thumbnail_grid.setVisible(False)
        self._ranges_input.clear()
        # L7 / E8: the file name, never its full path (only the destination shows a path).
        self._input_label.setText(path.name)
        self._input_label.setToolTip(path.name)
        self._page_count_label.setText(tr("page_count.loading", self._locale))
        self._action_bar.clear_result()
        self._output.clear()
        self._propose_output()
        self._input_panel.set_loaded(True)
        self._source_check.set_sources([path])
        self._update_action_state()
        if self._page_count_runner.is_running():
            self._queued_page_count_path = path
            return
        self._page_count_runner.start(path)

    def _clear_input_path(self) -> None:
        self._input_path = None
        self._page_count = None
        self._queued_page_count_path = None
        self._input_label.setText(tr("input.none_pdf", self._locale))
        self._input_label.setToolTip("")
        self._page_count_label.setText(tr("page_count.empty", self._locale))
        self._action_bar.clear_result()
        self._output.clear()
        self._input_panel.set_loaded(False)
        self._source_check.clear()
        self._thumbnail_grid.clear_document()
        self._thumbnail_grid.setVisible(False)
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
                self._thumbnail_grid.set_document(result.pdf_path, result.page_count)
                self._thumbnail_grid.setVisible(True)
                self._input_panel.set_loaded(True)
            else:
                self._page_count = None
                self._page_count_label.setText(tr("page_count.empty", self._locale))
                self._thumbnail_grid.setVisible(False)
                # L4: a protected or damaged PDF is reported under the source,
                # with `Change PDF` kept; other failures stay at the action.
                reported = bool(self._source_check.problem())
                self._input_panel.set_loaded(reported)
                if not reported:
                    code = result.technical_detail or "invalid_pdf"
                    failure = JobResult(False, (), (), "-", code)
                    self._action_bar.show_error(job_result_message(failure, self._locale))

        if queued_path is not None and queued_path != result.pdf_path:
            self._page_count_runner.start(queued_path)
            self._update_action_state()
            return
        if self._input_path != result.pdf_path:
            self._page_count = None
        self._update_action_state()

    def _operation_finished(self, result: JobResult) -> None:
        if result.success:
            # Next free name first: a destination change clears the displayed result.
            self._output.refresh()
        self._action_bar.finish(result, job_result_message(result, self._locale, self._spec.key))
        self._update_action_state()
        if result.success:
            open_output_folder_if_requested(self._settings, result)
        self.job_completed.emit(result)

    def _build_job(self) -> JobRequest:
        if self._input_path is None or self._page_count is None:
            raise ValueError(tr("visual.error.no_pdf", self._locale))

        options: dict[str, object]
        output = self._output.path()
        if output is None:
            raise ValueError(tr("visual.error.no_output", self._locale))
        output_dir = output if self._spec.output_mode == "directory" else output.parent

        if self._spec.input_mode == "range_groups":
            page_ranges = parse_page_range_groups(self._ranges_input.text())
            validate_page_ranges(page_ranges, self._page_count)
            options = {"ranges": page_ranges}
        elif self._spec.input_mode == "complete_order":
            page_order = tuple(parse_page_order(self._ranges_input.text()))
            validate_page_assembly(page_order, self._page_count)
            options = {"page_order": page_order, "output_path": output}
        else:
            page_numbers = tuple(parse_page_ranges(self._ranges_input.text()))
            validate_page_numbers(page_numbers, self._page_count)
            options = {"page_numbers": page_numbers, "output_path": output}
            if self._spec.requires_rotation_angle:
                options["angle"] = int(self._angle_input.currentData())

        return JobRequest(
            operation=self._operation,
            input_files=(self._input_path,),
            output_dir=output_dir,
            options=options,
            naming_strategy="explicit",
            job_id=str(uuid.uuid4()),
        )

    def _blocker(self) -> str:
        if self._input_path is None:
            return tr("tool.required.source", self._locale)
        problem = self._source_check.blocker_text()
        if problem:
            return problem
        if self._page_count is None or self._page_count_runner.is_running():
            return tr("page_count.loading", self._locale)
        if self._spec.input_mode == "complete_order" and self._page_count < 2:
            return tr("reorder.required.pages", self._locale)
        if not self._has_valid_ranges():
            return tr("visual.required.ranges", self._locale)
        if self._spec.input_mode == "complete_order" and tuple(
            parse_page_order(self._ranges_input.text())
        ) == tuple(range(1, self._page_count + 1)):
            return tr("reorder.required.change", self._locale)
        if self._output.path() is None:
            return tr("tool.required.output", self._locale)
        return ""

    def _update_action_state(self) -> None:
        running = self._job_runner.is_running()
        self._output.setEnabled(not running)
        self._input_panel.setEnabled(not running)
        # Settings are frozen while the job runs: the result shown at the end
        # always matches the settings that produced it.
        self._settings_panel.setEnabled(not running)
        self._thumbnail_grid.setEnabled(not running)
        blocker = self._blocker()
        self._action_bar.set_blocker(blocker)
        self._duplicate_page_button.setEnabled(
            self._spec.input_mode == "complete_order"
            and self._page_count is not None
            and not running
            and not self._page_count_runner.is_running()
        )

    def _plan_changed(self, _text: str) -> None:
        self._action_bar.clear_result()  # rule 8
        self._update_action_state()

    def _has_valid_ranges(self) -> bool:
        if self._page_count is None:
            return False
        try:
            if self._spec.input_mode == "range_groups":
                validate_page_ranges(
                    parse_page_range_groups(self._ranges_input.text()), self._page_count
                )
            elif self._spec.input_mode == "complete_order":
                validate_page_assembly(
                    parse_page_order(self._ranges_input.text()), self._page_count
                )
            else:
                validate_page_numbers(
                    parse_page_ranges(self._ranges_input.text()), self._page_count
                )
        except ValueError:
            return False
        return True

    def _ranges_placeholder(self) -> str:
        return self._spec.page_range_placeholder

    def _help_text(self) -> str:
        if not self._spec.help_key:
            return ""
        return tr(self._spec.help_key, self._locale)

    def set_locale(self, locale: Locale) -> None:
        self._locale = locale
        self._description_label.setText(tr(self._spec.description_key, locale))
        self._back_button.setText(tr("button.back", locale))
        self._advanced_button.setText(tr("visual.advanced_mode", locale))
        self._ranges_label.setText(self._ranges_label_key_text().upper())
        self._help_label.setText(self._help_key_text())
        self._help_label.setVisible(self._ranges_input.isVisible() and bool(self._help_key_text()))
        self._angle_label.setText(tr("label.rotation_angle", locale))
        self._move_page_up_button.setText(tr("button.up", locale))
        self._move_page_down_button.setText(tr("button.down", locale))
        self._duplicate_page_button.setText(tr("button.duplicate_pages", locale))
        self._input_panel.set_locale(locale)
        self._source_check.set_locale(locale)
        self._output.set_locale(locale)
        self._action_bar.set_locale(locale)
        self._propose_output()
        self._thumbnail_grid.set_locale(locale)
        if self._input_path is None:
            self._input_label.setText(tr("input.none_pdf", locale))
        if self._page_count is None:
            self._page_count_label.setText(tr("page_count.empty", locale))
        self._update_action_state()

    def busy_document_paths(self) -> tuple[Path, ...]:
        if not self._job_runner.is_running() or self._input_path is None:
            return ()
        return (self._input_path,)

    def _ranges_label_key_text(self) -> str:
        return tr(self._spec.ranges_label_key, self._locale)

    def _help_key_text(self) -> str:
        if not self._spec.help_key:
            return ""
        return tr(self._spec.help_key, self._locale)

    def _thumbnail_mode(self) -> str:
        if self._spec.input_mode == "range_groups":
            return "split"
        if self._spec.input_mode == "complete_order":
            return "ordered"
        return "selection"

    def _thumbnail_layout_mode(self) -> str:
        if self._spec.input_mode == "complete_order":
            return "grid_reorder"
        return "horizontal_strip"

    def _thumbnail_selection_changed(self, pages: tuple[int, ...]) -> None:
        if self._syncing_visual_selection or not pages:
            return
        if self._spec.input_mode not in {"ranges"}:
            return
        self._syncing_visual_selection = True
        self._ranges_input.setText(self._thumbnail_grid.range_expression())
        self._syncing_visual_selection = False

    def _thumbnail_order_changed(self, page_order: tuple[int, ...]) -> None:
        if self._syncing_visual_selection or self._spec.input_mode != "complete_order":
            return
        self._syncing_visual_selection = True
        self._ranges_input.setText(",".join(str(page) for page in page_order))
        self._syncing_visual_selection = False

    def _thumbnail_split_ranges_changed(self, page_ranges: tuple) -> None:
        if self._syncing_visual_selection or self._spec.input_mode != "range_groups":
            return
        if not page_ranges:
            return
        self._syncing_visual_selection = True
        self._ranges_input.setText(",".join(page_range.label for page_range in page_ranges))
        self._syncing_visual_selection = False

    def _duplicate_selected_thumbnail(self) -> None:
        if self._spec.input_mode != "complete_order":
            return
        self._thumbnail_grid.duplicate_selected()
        self._update_action_state()

    def _move_selected_thumbnail(self, offset: int) -> None:
        if self._spec.input_mode != "complete_order":
            return
        self._thumbnail_grid.move_selected(offset)

    def _toggle_advanced(self) -> None:
        visible = not self._ranges_input.isVisible()
        self._ranges_label.setVisible(visible)
        self._ranges_input.setVisible(visible)
        self._help_label.setVisible(visible and bool(self._help_key_text()))
