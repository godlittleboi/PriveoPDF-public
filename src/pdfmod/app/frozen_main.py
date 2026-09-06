"""Entry point for the installed executable and its isolated subprocesses."""

from __future__ import annotations

import sys
from collections.abc import Sequence
from functools import partial


def main(arguments: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if arguments is None else arguments)
    if args and args[0] == "--network-broker":
        from pdfmod.app import network_broker
        from pdfmod.app.update_checker import GitHubRepository, check_for_updates

        network_broker.check_for_updates = partial(
            check_for_updates,
            repository=GitHubRepository("godlittleboi", "PriveoPDF-public"),
            source="github_releases",
        )
        return network_broker.main(args[1:])
    if args == ["--version"]:
        from pdfmod.app.app_info import get_app_version

        print(get_app_version())
        return 0

    from pdfmod.workers.network_isolation import document_namespace_verified

    if not document_namespace_verified():
        print("network_isolation_unavailable", file=sys.stderr)
        return 78
    if args and args[0] == "--pdf-worker":
        from pdfmod.workers.pdf_worker import main as worker_main

        return worker_main(args[1:])

    from pdfmod.app.bootstrap import run_app

    return run_app([sys.argv[0], *args])


if __name__ == "__main__":
    raise SystemExit(main())
