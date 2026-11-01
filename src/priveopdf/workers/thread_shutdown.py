"""Stop a runner's QThread before Qt can destroy it while it still runs."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QThread

# Upper bound per runner when the window closes; a cancelled worker stops far sooner.
SHUTDOWN_WAIT_MS = 5000


def shutdown_runner_thread(
    thread: QThread | None,
    cancel: Callable[[], object] | None = None,
    timeout_ms: int = SHUTDOWN_WAIT_MS,
) -> bool:
    """Cancel, quit and wait (B22: closing during a job aborted Python).

    `quit()` is called directly: the worker's queued `finished -> quit` cannot be
    delivered while the GUI thread is blocked in `wait()`. Returns False if the
    thread is still running after `timeout_ms`.
    """

    if thread is None:
        return True
    if cancel is not None:
        cancel()
    thread.quit()
    return thread.wait(timeout_ms)
