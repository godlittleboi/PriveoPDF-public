"""Application-shell coordinators used by :mod:`priveopdf.ui.main_window`."""

from priveopdf.ui.controllers.navigation_controller import NavigationController
from priveopdf.ui.controllers.startup_coordinator import StartupCoordinator
from priveopdf.ui.controllers.update_controller import UpdateController
from priveopdf.ui.controllers.workspace_controller import WorkspaceController

__all__ = [
    "NavigationController",
    "StartupCoordinator",
    "UpdateController",
    "WorkspaceController",
]
