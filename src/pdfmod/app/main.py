from __future__ import annotations

import sys

from pdfmod.app.bootstrap import run_app


def main() -> int:
    return run_app(sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())
