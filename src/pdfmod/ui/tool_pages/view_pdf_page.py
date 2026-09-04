from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtPdf import QPdfDocument
from PySide6.QtPdfWidgets import QPdfView
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from pdfmod.ui.components import (
    GhostButton,
    PdfInputPanel,
    SecondaryButton,
    SurfacePanel,
)
from pdfmod.ui.i18n import Locale, tr
from pdfmod.ui.tool_specs import TOOL_SPECS_BY_KEY
from pdfmod.ui.workspace_state import WorkspaceDocument

ZOOM_PERCENT_OPTIONS = (25, 50, 75, 100, 125, 150, 200, 300, 400)


class ReaderPdfView(QPdfView):
    zoom_requested = Signal(float)
    page_step_requested = Signal(int)

    def wheelEvent(self, event) -> None:  # noqa: ANN001, N802
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            if delta:
                self.zoom_requested.emit(1.12 if delta > 0 else 0.88)
                event.accept()
                return
        super().wheelEvent(event)

    def keyPressEvent(self, event) -> None:  # noqa: ANN001, N802
        if event.key() in {Qt.Key.Key_PageDown, Qt.Key.Key_Down, Qt.Key.Key_Right}:
            self.page_step_requested.emit(1)
            event.accept()
            return
        if event.key() in {Qt.Key.Key_PageUp, Qt.Key.Key_Up, Qt.Key.Key_Left}:
            self.page_step_requested.emit(-1)
            event.accept()
            return
        super().keyPressEvent(event)


class ViewPdfPage(QWidget):
    back_requested = Signal()
    workspace_files_added = Signal(list)
    page_count_ready = Signal(object, int)

    def __init__(self, locale: Locale = "en") -> None:
        super().__init__()
        self._locale = locale
        self._current_path: Path | None = None
        self._document = QPdfDocument(self)
        self._document.pageCountChanged.connect(self._update_page_status)

        self._description_label = QLabel()
        self._description_label.setObjectName("HelpText")
        self._description_label.setWordWrap(True)

        self._back_button = GhostButton()
        self._back_button.clicked.connect(self.back_requested.emit)

        self._previous_button = SecondaryButton()
        self._previous_button.clicked.connect(lambda: self._go_to_relative_page(-1))

        self._next_button = SecondaryButton()
        self._next_button.clicked.connect(lambda: self._go_to_relative_page(1))

        self._zoom_out_button = SecondaryButton()
        self._zoom_out_button.clicked.connect(lambda: self._zoom_by(0.85))

        self._zoom_percent_combo = QComboBox()
        self._zoom_percent_combo.setObjectName("ZoomPercentCombo")
        self._zoom_percent_combo.setEditable(True)
        if self._zoom_percent_combo.lineEdit() is not None:
            self._zoom_percent_combo.lineEdit().setReadOnly(True)
            self._zoom_percent_combo.lineEdit().setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._zoom_percent_combo.setMinimumWidth(88)
        self._zoom_percent_combo.setFixedWidth(96)
        for percent in ZOOM_PERCENT_OPTIONS:
            self._zoom_percent_combo.addItem(f"{percent} %", percent)
        self._zoom_percent_combo.currentIndexChanged.connect(self._zoom_percent_index_changed)

        self._zoom_in_button = SecondaryButton()
        self._zoom_in_button.clicked.connect(lambda: self._zoom_by(1.15))

        self._fit_page_button = SecondaryButton()
        self._fit_page_button.clicked.connect(self._fit_page)

        self._fit_width_button = SecondaryButton()
        self._fit_width_button.clicked.connect(self._fit_width)

        self._page_label = QLabel()
        self._page_label.setObjectName("HelpText")

        self._input_panel = PdfInputPanel(multiple=False, locale=locale)
        self._input_panel.paths_selected.connect(self._handle_files)

        self._pdf_view = ReaderPdfView()
        self._pdf_view.setDocument(self._document)
        self._pdf_view.setPageMode(QPdfView.PageMode.MultiPage)
        self._pdf_view.setZoomMode(QPdfView.ZoomMode.FitInView)
        self._pdf_view.setMinimumHeight(360)
        self._pdf_view.pageNavigator().currentPageChanged.connect(self._update_page_status)
        self._pdf_view.zoom_requested.connect(self._zoom_by)
        self._pdf_view.page_step_requested.connect(self._go_to_relative_page)

        self._status_label = QLabel()
        self._status_label.setObjectName("StatusText")
        self._status_label.setWordWrap(True)

        toolbar = QHBoxLayout()
        toolbar.addWidget(self._back_button)
        toolbar.addStretch(1)
        toolbar.addWidget(self._previous_button)
        toolbar.addWidget(self._page_label)
        toolbar.addWidget(self._next_button)
        toolbar.addWidget(self._fit_page_button)
        toolbar.addWidget(self._fit_width_button)
        toolbar.addWidget(self._zoom_out_button)
        toolbar.addWidget(self._zoom_percent_combo)
        toolbar.addWidget(self._zoom_in_button)

        viewer_panel = SurfacePanel(role="primary")
        viewer_layout = QVBoxLayout(viewer_panel)
        viewer_layout.setContentsMargins(18, 18, 18, 18)
        viewer_layout.setSpacing(12)
        viewer_layout.addWidget(self._pdf_view, 1)
        viewer_layout.addWidget(self._status_label)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 30, 32, 30)
        layout.setSpacing(16)
        layout.addWidget(self._description_label)
        layout.addLayout(toolbar)
        layout.addWidget(self._input_panel)
        layout.addWidget(viewer_panel, 1)
        self.set_locale(locale)
        self._set_empty_state()

    def load_document(self, path: Path) -> None:
        candidate = Path(path)
        self._current_path = candidate
        self._document.close()
        error = self._document.load(str(candidate))
        if error != QPdfDocument.Error.None_:
            self._status_label.setText(tr("viewer.load_error", self._locale))
            self._page_label.setText(tr("page_count.empty", self._locale))
            self._input_panel.set_loaded(False)
            return

        self._pdf_view.setZoomMode(QPdfView.ZoomMode.FitInView)
        self._input_panel.set_loaded(True)
        self._status_label.setText(tr("viewer.loaded", self._locale, name=candidate.name))
        page_count = self._document.pageCount()
        if page_count > 0:
            self.page_count_ready.emit(candidate, page_count)
        self._update_page_status()
        self._update_zoom_percent()

    def set_workspace_document(self, document: WorkspaceDocument | None) -> None:
        if document is None:
            self._set_empty_state()
            return
        if self._current_path != document.path:
            self.load_document(document.path)

    def set_locale(self, locale: Locale) -> None:
        self._locale = locale
        spec = TOOL_SPECS_BY_KEY["view"]
        self._description_label.setText(tr(spec.description_key, locale))
        self._back_button.setText(tr("button.back", locale))
        self._previous_button.setText(tr("viewer.previous", locale))
        self._next_button.setText(tr("viewer.next", locale))
        self._zoom_out_button.setText(tr("viewer.zoom_out", locale))
        self._zoom_in_button.setText(tr("viewer.zoom_in", locale))
        self._fit_page_button.setText(tr("viewer.fit_page", locale))
        self._fit_width_button.setText(tr("viewer.fit_width", locale))
        self._input_panel.set_locale(locale)
        self._update_page_status()
        if self._current_path is None:
            self._status_label.setText(tr("viewer.no_pdf", locale))

    def _handle_files(self, paths: list[Path]) -> None:
        if not paths:
            return
        self.load_document(paths[0])
        self.workspace_files_added.emit(paths)

    def _set_empty_state(self) -> None:
        self._current_path = None
        self._document.close()
        self._input_panel.set_loaded(False)
        self._status_label.setText(tr("viewer.no_pdf", self._locale))
        self._page_label.setText(tr("page_count.empty", self._locale))
        self._set_zoom_percent_text(100)

    def _go_to_relative_page(self, offset: int) -> None:
        page_count = self._document.pageCount()
        if page_count <= 0:
            return
        navigator = self._pdf_view.pageNavigator()
        target = max(0, min(page_count - 1, navigator.currentPage() + offset))
        navigator.jump(target, QPointF(), self._pdf_view.zoomFactor())
        self._update_page_status()

    def _zoom_by(self, factor: float) -> None:
        self._pdf_view.setZoomMode(QPdfView.ZoomMode.Custom)
        zoom = max(0.25, min(4.0, self._pdf_view.zoomFactor() * factor))
        self._pdf_view.setZoomFactor(zoom)
        self._update_zoom_percent()

    def _zoom_percent_index_changed(self, index: int) -> None:
        percent = self._zoom_percent_combo.itemData(index)
        if not isinstance(percent, int):
            return
        self._pdf_view.setZoomMode(QPdfView.ZoomMode.Custom)
        self._pdf_view.setZoomFactor(percent / 100)
        self._set_zoom_percent_text(percent)

    def _fit_page(self) -> None:
        self._pdf_view.setZoomMode(QPdfView.ZoomMode.FitInView)
        self._update_zoom_percent()

    def _fit_width(self) -> None:
        self._pdf_view.setZoomMode(QPdfView.ZoomMode.FitToWidth)
        self._update_zoom_percent()

    def _update_page_status(self, *args: object) -> None:
        del args
        page_count = self._document.pageCount()
        if page_count <= 0:
            self._page_label.setText(tr("page_count.empty", self._locale))
            return
        current_page = self._pdf_view.pageNavigator().currentPage() + 1
        self._page_label.setText(
            tr("viewer.page_status", self._locale, page=current_page, total=page_count)
        )
        self._update_zoom_percent()

    def _update_zoom_percent(self) -> None:
        zoom_percent = max(1, round(self._pdf_view.zoomFactor() * 100))
        self._set_zoom_percent_text(zoom_percent)

    def _set_zoom_percent_text(self, percent: int) -> None:
        self._zoom_percent_combo.blockSignals(True)
        index = self._zoom_percent_combo.findData(percent)
        if index >= 0:
            self._zoom_percent_combo.setCurrentIndex(index)
        else:
            self._zoom_percent_combo.setCurrentIndex(-1)
            self._zoom_percent_combo.setEditText(f"{percent} %")
        self._zoom_percent_combo.blockSignals(False)
