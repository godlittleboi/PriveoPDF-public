"""Utilities."""

from __future__ import annotations

import locale


def keep_c_numeric_locale() -> None:
    """Restore the C numeric locale after Qt starts.

    On Linux, Qt applies the user's locale to the whole process. With a French
    locale, qpdf then reads 31.9371 as 31 and silently rounds real numbers in
    PDFs written by the same process. Qt's documentation asks for this call
    right after creating the application object.
    """
    locale.setlocale(locale.LC_NUMERIC, "C")
