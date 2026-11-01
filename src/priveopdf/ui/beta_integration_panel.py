from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from priveopdf.app.beta_integration import (
    BetaIntegrationManifest,
    IntegrationChecklistStore,
    IntegrationPullRequest,
)
from priveopdf.ui.components import SurfacePanel
from priveopdf.ui.i18n import Locale, tr
from priveopdf.ui.theme.tokens import SPACING


class BetaIntegrationPanel(SurfacePanel):
    def __init__(
        self,
        manifest: BetaIntegrationManifest,
        locale: Locale,
        parent: QWidget | None = None,
        *,
        store: IntegrationChecklistStore | None = None,
    ) -> None:
        super().__init__(role="primary", parent=parent)
        self.setObjectName("BetaIntegrationPanel")
        self.setMinimumWidth(380)
        self.setMaximumWidth(460)
        self._manifest = manifest
        self._locale = locale
        self._store = store or IntegrationChecklistStore()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 14, 14, 14)
        outer.setSpacing(10)

        heading = QLabel(tr("beta.integration.heading", locale))
        heading.setObjectName("SectionTitle")
        outer.addWidget(heading)

        identity = QLabel(
            tr(
                "beta.individual.identity"
                if manifest.build_kind == "local-pr"
                else "beta.integration.identity",
                locale,
                count=len(manifest.pull_requests),
                sha=manifest.base_sha[:12],
            )
        )
        identity.setObjectName("HelpText")
        identity.setWordWrap(True)
        identity.setTextFormat(Qt.TextFormat.PlainText)
        outer.addWidget(identity)

        explanation = QLabel(
            tr(
                "beta.individual.help"
                if manifest.build_kind == "local-pr"
                else "beta.integration.help",
                locale,
            )
        )
        explanation.setObjectName("HelpText")
        explanation.setWordWrap(True)
        explanation.setTextFormat(Qt.TextFormat.PlainText)
        outer.addWidget(explanation)

        scroll = QScrollArea()
        scroll.setObjectName("BetaIntegrationChecklistScroll")
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(10)
        for pull_request in manifest.pull_requests:
            content_layout.addWidget(self._build_pull_request_panel(pull_request))
        content_layout.addStretch(1)
        scroll.setWidget(content)
        outer.addWidget(scroll, 1)

    def _build_pull_request_panel(self, pull_request: IntegrationPullRequest) -> SurfacePanel:
        panel = SurfacePanel(soft=True)
        panel.setObjectName("BetaIntegrationPullRequest")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(7)

        title = QLabel(f"PR #{pull_request.number} · {pull_request.title}")
        title.setObjectName("SectionTitle")
        title.setWordWrap(True)
        title.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(title)

        sha = QLabel(tr("beta.integration.sha", self._locale, sha=pull_request.head_sha[:12]))
        sha.setObjectName("HelpText")
        sha.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(sha)

        progress = QLabel()
        progress.setObjectName("HelpText")
        checkboxes: list[QCheckBox] = []
        for item in pull_request.checklist:
            row = QHBoxLayout()
            row.setSpacing(SPACING["sm"])
            checkbox = QCheckBox()
            checkbox.setObjectName("BetaIntegrationChecklistItem")
            checkbox.setAccessibleName(item.text)
            checkbox.setToolTip(item.text)
            checkbox.setChecked(self._store.checked(pull_request, item.item_id))
            checkbox.setProperty("itemId", item.item_id)
            checkbox.stateChanged.connect(
                lambda state, current=item.item_id: self._set_checked(
                    pull_request,
                    current,
                    state == Qt.CheckState.Checked.value,
                    progress,
                    checkboxes,
                )
            )
            checkboxes.append(checkbox)
            text = QLabel(item.text)
            text.setObjectName("BetaIntegrationChecklistText")
            text.setTextFormat(Qt.TextFormat.PlainText)
            text.setWordWrap(True)
            text.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Minimum)
            text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            text.setBuddy(checkbox)
            row.addWidget(checkbox, 0, Qt.AlignmentFlag.AlignTop)
            row.addWidget(text, 1)
            layout.addLayout(row)

        layout.addWidget(progress)
        self._refresh_progress(pull_request, progress, checkboxes)
        return panel

    def _set_checked(
        self,
        pull_request: IntegrationPullRequest,
        item_id: str,
        checked: bool,
        progress: QLabel,
        checkboxes: list[QCheckBox],
    ) -> None:
        self._store.set_checked(pull_request, item_id, checked)
        self._refresh_progress(pull_request, progress, checkboxes)

    def _refresh_progress(
        self,
        pull_request: IntegrationPullRequest,
        label: QLabel,
        checkboxes: list[QCheckBox],
    ) -> None:
        completed = sum(checkbox.isChecked() for checkbox in checkboxes)
        total = len(checkboxes)
        key = "beta.integration.complete" if completed == total else "beta.integration.progress"
        label.setText(tr(key, self._locale, completed=completed, total=total))
