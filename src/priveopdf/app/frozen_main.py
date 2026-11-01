"""Entry point for the installed executable and its isolated subprocesses."""

from __future__ import annotations

import sys
from collections.abc import Sequence
from functools import partial


def main(arguments: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if arguments is None else arguments)
    if args and args[0] == "--render-memory-broker":
        from priveopdf.workers.render_memory_broker import main as memory_broker_main

        return memory_broker_main(args[1:])
    if args and args[0] == "--release-opener":
        from priveopdf.app.release_opener import main as release_opener_main

        return release_opener_main(args[1:])
    if args and args[0] == "--network-broker":
        from priveopdf.app import network_broker
        from priveopdf.app.update_checker import GitHubRepository, check_for_updates

        network_broker.check_for_updates = partial(
            check_for_updates,
            repository=GitHubRepository("godlittleboi", "PriveoPDF-public"),
            source="github_releases",
        )
        return network_broker.main(args[1:])
    if args == ["--version"]:
        from priveopdf.app.app_info import get_app_version

        print(get_app_version())
        return 0

    from priveopdf.workers.network_isolation import document_namespace_verified

    if not document_namespace_verified():
        print("network_isolation_unavailable", file=sys.stderr)
        return 78
    if args and args[0] == "--pdf-worker":
        from priveopdf.workers.pdf_worker import main as worker_main

        return worker_main(args[1:])
    if args == ["--render-worker"]:
        from priveopdf.workers.render_worker import main as render_main

        return render_main()

    from priveopdf.app.bootstrap import run_app

    return run_app([sys.argv[0], *args])


if __name__ == "__main__":
    raise SystemExit(main())
