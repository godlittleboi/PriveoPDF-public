from __future__ import annotations

import uuid
from pathlib import Path

from PySide6.QtCore import QMimeData, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QBrush, QColor, QKeyEvent, QMouseEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from priveopdf.app.settings import AppSettings
from priveopdf.domain.document_context import ToolLaunchContext
from priveopdf.domain.jobs import JobRequest, JobResult, OperationType
from priveopdf.ui.components import (
    ElidedLabel,
    GhostButton,
    OutputTargetField,
    PdfInputPanel,
    SecondaryButton,
    SourceCheck,
    SurfacePanel,
    ToolActionBar,
    job_result_message,
    open_output_folder_if_requested,
    output_suffix,
    page_count_text,
    proposed_output_directory,
    set_button_role,
)
from priveopdf.ui.i18n import Locale, tr
from priveopdf.ui.theme.tokens import SPACING
from priveopdf.ui.tool_specs import TOOL_SPECS_BY_KEY
from priveopdf.ui.workspace_state import WorkspaceDocument, preloads_open_documents
from priveopdf.workers.job_runner import PageCountResult, QtJobRunner


class _MergeRow(QWidget):
    """One listed PDF: name, page count, `X` to remove it from the merge (rule 2).

    Clicks outside the button go to the list, so selection and drag-and-drop
    reordering keep working on the whole row."""

    remove_requested = Signal(str)

    def __init__(self, key: str, name: str, pages: str, remove_text: str) -> None:
        super().__init__()
        self._key = key
        self._name = ElidedLabel(name)
        self._name.setObjectName("MergeRowName")
        self._pages = QLabel(pages)
        self._pages.setObjectName("HelpText")
        for label in (self._name, self._pages):
            label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._remove = QPushButton("X")
        self._remove.setObjectName("MergeRowRemove")
        set_button_role(self._remove, "workspaceRemove")
        self._remove.setToolTip(remove_text)
        self._remove.setAccessibleName(remove_text)
        self._remove.clicked.connect(lambda: self.remove_requested.emit(self._key))
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACING["sm"])
        layout.addWidget(self._name, 1)
        layout.addWidget(self._pages)
        layout.addWidget(self._remove)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt override
        event.ignore()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt override
        event.ignore()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt override
        event.ignore()


class PdfDropList(QListWidget):
    files_dropped = Signal(list)

    def __init__(self) -> None:
        super().__init__()
        self.setAcceptDrops(True)
        self.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.setAlternatingRowColors(True)
        self.setMinimumHeight(260)
        self.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)

    remove_current_requested = Signal()

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802 - Qt override
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace) and self.currentItem():
            self.remove_current_requested.emit()
            return
        super().keyPressEvent(event)

    def dragEnterEvent(self, event) -> None:  # noqa: ANN001
        if event.source() is self:
            super().dragEnterEvent(event)
            return
        if self._has_pdf_urls(event.mimeData()):
            event.acceptProposedAction()
            return
        event.ignore()

    def dragMoveEvent(self, event) -> None:  # noqa: ANN001
        if event.source() is self:
            super().dragMoveEvent(event)
            return
        if self._has_pdf_urls(event.mimeData()):
            event.acceptProposedAction()
            return
        event.ignore()

    def dropEvent(self, event) -> None:  # noqa: ANN001
        if not event.mimeData().hasUrls():
            super().dropEvent(event)
            return
        paths = [Path(url.toLocalFile()) for url in event.mimeData().urls() if url.isLocalFile()]
        pdfs = [path for path in paths if path.suffix.lower() == ".pdf"]
        if pdfs:
            self.files_dropped.emit(pdfs)
            event.acceptProposedAction()
            return
        event.ignore()

    def _has_pdf_urls(self, mime_data: QMimeData) -> bool:
        return any(
            url.isLocalFile() and Path(url.toLocalFile()).suffix.lower() == ".pdf"
            for url in mime_data.urls()
        )


class MergePdfPage(QWidget):
    back_requested = Signal()
    workspace_files_added = Signal(list)
    output_pdf_requested = Signal(object)
    job_completed = Signal(object)

    def __init__(self, locale: Locale = "en", settings: AppSettings | None = None) -> None:
        super().__init__()
        self._spec = TOOL_SPECS_BY_KEY["merge"]
        self._locale = locale
        self._settings = settings or AppSettings()
        self._output_source: Path | None = None
        self._launch_context: ToolLaunchContext | None = None
        self._workspace_documents: tuple[WorkspaceDocument, ...] = ()
        self._removed_paths: set[str] = set()
        self._job_runner = QtJobRunner(self)
        self._job_runner.finished.connect(self._merge_finished)
        self._job_runner.progress.connect(self._merge_progress)

        self._file_list = PdfDropList()
        self._file_list.files_dropped.connect(self._handle_files)
        self._file_list.remove_current_requested.connect(self._remove_selected)
        # Rule 2: each listed PDF shows its page count, known from the L4 check.
        self._page_counts: dict[str, int] = {}
        self._file_list.model().rowsMoved.connect(self._list_reordered)
        self._input_panel = PdfInputPanel(multiple=True, locale=locale)
        self._input_panel.paths_selected.connect(self._handle_files)

        self._back_button = GhostButton()
        self._back_button.clicked.connect(self.back_requested.emit)
        self._up_button = SecondaryButton()
        self._up_button.clicked.connect(self._move_selected_up)
        self._down_button = SecondaryButton()
        self._down_button.clicked.connect(self._move_selected_down)

        # L4: each PDF of the list is checked on load; the message names the file.
        self._source_check = SourceCheck(locale, name_files=True)
        self._source_check.changed.connect(self._update_action_state)
        # L5: open documents taken on arrival, dropped if one proves unusable.
        self._preloaded: set[str] = set()
        self._selected_key = ""
        self._source_check.checked.connect(self._preload_checked)
        self._source_check.checked.connect(self._record_page_count)
        self._output = OutputTargetField("file", locale)
        self._output.changed.connect(self._output_changed)
        self._action_bar = ToolActionBar(locale)
        self._action_bar.set_action_text_key(self._spec.action_button_key)
        self._action_bar.action_requested.connect(self._start_merge)
        self._action_bar.cancel_requested.connect(self._job_runner.cancel)
        self._action_bar.open_pdf_requested.connect(self.output_pdf_requested.emit)

        self._description_label = QLabel()
        self._description_label.setObjectName("HelpText")
        self._description_label.setWordWrap(True)

        page_toolbar = QHBoxLayout()
        page_toolbar.addWidget(self._back_button)
        page_toolbar.addStretch(1)

        file_toolbar = QHBoxLayout()
        file_toolbar.addStretch(1)
        file_toolbar.addWidget(self._up_button)
        file_toolbar.addWidget(self._down_button)

        file_panel = SurfacePanel(role="primary")
        file_panel_layout = QVBoxLayout(file_panel)
        file_panel_layout.setContentsMargins(16, 16, 16, 16)
        file_panel_layout.setSpacing(10)
        file_panel_layout.addLayout(file_toolbar)
        file_panel_layout.addWidget(self._file_list)
        file_panel_layout.addWidget(self._source_check)
        file_panel_layout.addWidget(self._output)
        file_panel_layout.addWidget(self._action_bar)
        self._file_panel = file_panel

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)
        layout.addLayout(page_toolbar)
        layout.addWidget(self._description_label)
        layout.addWidget(self._input_panel)
        layout.addWidget(file_panel)
        layout.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(content)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(scroll)
        self.set_locale(locale)
        self._update_action_state()

    def _handle_files(self, paths: list[Path]) -> None:
        if self._job_runner.is_running():
            return
        self._removed_paths.difference_update(_path_key(path) for path in paths)
        self._add_files(paths)
        self.workspace_files_added.emit(paths)

    def _add_files(self, paths: list[Path]) -> None:
        existing = {self._file_list.item(i).data(0x0100) for i in range(self._file_list.count())}
        added = False
        for path in paths:
            normalized = _path_key(path)
            if normalized in existing:
                continue
            item = QListWidgetItem(path.name)
            item.setData(0x0100, normalized)
            # The row widget draws the name; the item keeps it for accessibility.
            item.setForeground(QBrush(QColor(0, 0, 0, 0)))
            self._file_list.addItem(item)
            existing.add(normalized)
            added = True
        if added:
            self._list_changed()
        self._update_action_state()

    def _remove_selected(self) -> None:
        row = self._file_list.currentRow()
        if row >= 0:
            self._remove_key(self._file_list.item(row).data(0x0100))

    def _remove_key(self, key: str) -> None:
        """Remove one PDF from the merge; the file on disk is never touched."""

        if self._job_runner.is_running():
            return
        for row in range(self._file_list.count()):
            if self._file_list.item(row).data(0x0100) == key:
                self._file_list.takeItem(row)
                self._removed_paths.add(key)
                self._list_changed()
                break
        self._update_action_state()

    def _record_page_count(self, result: object) -> None:
        if not isinstance(result, PageCountResult):
            return
        key = _path_key(result.pdf_path)
        if result.success and result.page_count:
            self._page_counts[key] = result.page_count
        else:
            self._page_counts.pop(key, None)
        self._rebuild_rows()

    def _rebuild_rows(self) -> None:
        running = self._job_runner.is_running()
        for row in range(self._file_list.count()):
            item = self._file_list.item(row)
            key = item.data(0x0100)
            count = self._page_counts.get(key)
            pages = (
                page_count_text(count, self._locale)
                if count
                else tr("merge.row.pages_unknown", self._locale)
            )
            widget = _MergeRow(
                key, item.text(), pages, tr("merge.row.remove", self._locale, name=item.text())
            )
            widget.remove_requested.connect(self._remove_key)
            widget.setEnabled(not running)
            # The row is as tall as its styled widget: the `X` is never clipped.
            self._file_list.setItemWidget(item, widget)
            widget._remove.ensurePolished()
            hint = widget.sizeHint()
            # QListWidget::item pads and borders the row (styles.py): add both.
            item.setSizeHint(QSize(hint.width(), hint.height() + 2 * (SPACING["sm"] + 1)))

    def _move_selected_up(self) -> None:
        self._move_selected(-1)

    def _move_selected_down(self) -> None:
        self._move_selected(1)

    def _move_selected(self, offset: int) -> None:
        row = self._file_list.currentRow()
        target = row + offset
        if row < 0 or target < 0 or target >= self._file_list.count():
            return
        item = self._file_list.takeItem(row)
        self._file_list.insertItem(target, item)
        self._file_list.setCurrentRow(target)
        self._list_changed()
        # The messages and `Unlock PDF` follow the new order.
        self._update_action_state()

    def _list_reordered(self, *_args: object) -> None:
        self._list_changed()
        self._update_action_state()

    def _list_changed(self) -> None:
        self._action_bar.clear_result()
        self._propose_output()
        # Item widgets do not follow a moved row: draw every row again.
        self._rebuild_rows()

    def _input_files(self) -> list[Path]:
        return [Path(self._file_list.item(i).data(0x0100)) for i in range(self._file_list.count())]

    def _propose_output(self) -> None:
        files = self._input_files()
        first = files[0] if files else None
        if first == self._output_source:
            return
        self._output_source = first
        if first is None:
            self._output.clear()
            return
        directory = proposed_output_directory(first, self._settings)
        self._output.propose(directory, first.stem, output_suffix("merge", self._locale))

    def _output_changed(self) -> None:
        self._action_bar.clear_result()
        self._update_action_state()

    def _start_merge(self) -> None:
        if self._job_runner.is_running():
            return
        input_files = self._input_files()
        output_path = self._output.path()
        if len(input_files) < 2 or output_path is None:
            self._update_action_state()
            return
        job = JobRequest(
            operation=OperationType.MERGE_PDFS,
            input_files=tuple(input_files),
            output_dir=output_path.parent,
            options={"output_path": output_path},
            naming_strategy="explicit",
            job_id=str(uuid.uuid4()),
        )
        self._action_bar.set_running(tr("merge.status.running", self._locale))
        self._job_runner.start(job)
        self._update_action_state()

    def _merge_progress(self, done: int, total: int) -> None:
        self._action_bar.set_progress(done, total, tr("merge.status.running", self._locale))

    def _merge_finished(self, result: JobResult) -> None:
        if result.success:
            # Next free name first: a destination change clears the displayed result.
            self._output.refresh()
        self._action_bar.finish(result, job_result_message(result, self._locale, "merge"))
        if result.success:
            open_output_folder_if_requested(self._settings, result)
        self._update_action_state()
        self.job_completed.emit(result)

    def _update_action_state(self) -> None:
        count = self._file_list.count()
        has_files = count > 0
        is_running = self._job_runner.is_running()
        self._input_panel.set_loaded(has_files)
        self._input_panel.setEnabled(not is_running)
        self._file_panel.setVisible(has_files)
        for widget in (self._file_list, self._up_button, self._down_button):
            widget.setEnabled(not is_running)
        self._output.setEnabled(not is_running)
        files = tuple(self._input_files())
        if files != self._source_check.sources():
            self._source_check.check(files)
        blocker = self._source_check.blocker_text()
        if not blocker and count < 2:
            blocker = tr("merge.required.files", self._locale)
        elif not blocker and self._output.path() is None:
            blocker = tr("merge.required.output", self._locale)
        self._action_bar.set_blocker(blocker)

    def set_workspace_documents(self, documents: tuple[WorkspaceDocument, ...]) -> None:
        # Refreshes keep the user's order and removals; arriving on the page resets the list.
        self._workspace_documents = documents
        if self._job_runner.is_running():
            return
        open_paths = {_path_key(document.path) for document in documents}
        removed = False
        for row in reversed(range(self._file_list.count())):
            if self._file_list.item(row).data(0x0100) not in open_paths:
                self._file_list.takeItem(row)
                removed = True
        if removed:
            self._list_changed()
        self._add_files(
            [
                document.path
                for document in documents
                if _path_key(document.path) not in self._removed_paths
            ]
        )

    def set_tool_launch_context(self, context: ToolLaunchContext | None) -> None:
        self._launch_context = context
        if self._job_runner.is_running():
            return
        self._removed_paths.clear()
        self._file_list.clear()
        self._output_source = None
        self._output.clear()
        self._action_bar.clear_result()
        if context is None:
            # L5 applies from Home too: 2 to 4 readable open documents (or the
            # only one) start the list; more than 4 do not.
            documents = self._workspace_documents
            if len(documents) == 1 or preloads_open_documents(documents):
                self._add_files([document.path for document in documents])
        else:
            self._add_files(list(context.input_files))
            # L5: open documents left out on arrival stay out on later refreshes;
            # documents opened afterwards still join the list.
            included = {_path_key(path) for path in context.input_files}
            self._preloaded = included if len(included) > 1 else set()
            selected = (
                context.active_document.source_path
                if context.active_document is not None
                else context.input_files[0]
            )
            self._selected_key = _path_key(selected)
            self._removed_paths.update(
                key
                for key in (_path_key(document.path) for document in self._workspace_documents)
                if key not in included
            )
        self._update_action_state()

    def _preload_checked(self, _result: object) -> None:
        # Deferred: the list must not change while the check delivers its result.
        QTimer.singleShot(0, self._apply_preload_rule)

    def _apply_preload_rule(self) -> None:
        """L5: if an open document taken on arrival is protected or unreadable,
        the merge starts again with the selected document alone."""

        if not self._preloaded or self._job_runner.is_running():
            return
        unusable = any(self._source_check.problem_of(Path(key)) for key in self._preloaded)
        if not unusable:
            return
        for row in reversed(range(self._file_list.count())):
            key = self._file_list.item(row).data(0x0100)
            if key in self._preloaded and key != self._selected_key:
                self._file_list.takeItem(row)
                self._removed_paths.add(key)
        self._preloaded = set()
        self._list_changed()
        self._update_action_state()

    def set_locale(self, locale: Locale) -> None:
        self._locale = locale
        self._description_label.setText(tr(self._spec.description_key, locale))
        self._back_button.setText(tr("button.back", locale))
        self._back_button.setToolTip(tr("button.back", locale))
        self._up_button.setText(tr("button.up", locale))
        self._up_button.setToolTip(tr("button.up", locale))
        self._down_button.setText(tr("button.down", locale))
        self._down_button.setToolTip(tr("button.down", locale))
        self._input_panel.set_locale(locale)
        self._source_check.set_locale(locale)
        self._output.set_locale(locale)
        self._action_bar.set_locale(locale)
        self._output_source = None
        self._propose_output()
        self._rebuild_rows()
        self._update_action_state()

    def busy_document_paths(self) -> tuple[Path, ...]:
        if not self._job_runner.is_running():
            return ()
        return tuple(self._input_files())


def _path_key(path: Path) -> str:
    return str(path.resolve(strict=False))
