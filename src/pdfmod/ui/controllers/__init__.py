"""Application-shell coordinators used by :mod:`pdfmod.ui.main_window`."""

from pdfmod.ui.controllers.navigation_controller import NavigationController
from pdfmod.ui.controllers.startup_coordinator import StartupCoordinator
from pdfmod.ui.controllers.update_controller import UpdateController
from pdfmod.ui.controllers.workspace_controller import WorkspaceController

__all__ = [
    "NavigationController",
    "StartupCoordinator",
    "UpdateController",
    "WorkspaceController",
]
