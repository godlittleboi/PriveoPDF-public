"""One bounded PDF rendering request. Never imported by the GUI process."""

from __future__ import annotations

import json
import math
import os
import sys
from argparse import Namespace

MAX_PIXELS = 4_000_000
# Private writable memory (heap, image buffers, decoded streams) one rendering
# may own, enforced by the kernel (RLIMIT_DATA): a hostile stream is stopped
# here even if it grows faster than the client's 768 MiB resident watcher polls
# (F01, CA3). Measured on the versioned corpus: 61 MiB at most for a 4 Mpx
# page. Two renderings run at once, so the reader's budget is twice this.
RENDER_DATA_BYTES = 1024 * 1024**2
MAX_PAGES = 10_000
MAX_HEADER = 2_000_000
MAX_TEXT_RECTS = 5_000
MAX_SEARCH_MATCHES = 1_000
MAX_QUERY = 256


def main() -> int:
    from priveopdf.workers.local_confinement import apply_worker_profile
    from priveopdf.workers.pdf_worker import _apply_resource_limits, _set_limit

    try:
        apply_worker_profile()
    except (OSError, ValueError):
        return 78

    # PDFium reserves a large virtual address cage; this is NOT a resident-memory cap.
    _apply_resource_limits(
        Namespace(
            render_memory=False,
            memory_bytes=64 * 1024**3,
            cpu_seconds=30,
            file_size_bytes=16 * 1024**2,
            open_files=64,
            # RLIMIT_NPROC is per real UID, including existing desktop threads.
            # The renderer needs Qt threads; this is not a per-worker process quota.
            processes=1024,
        )
    )
    if sys.platform.startswith("linux"):
        import resource

        _set_limit(resource.RLIMIT_DATA, RENDER_DATA_BYTES)
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    try:
        frame = sys.stdin.buffer.read(16_385)
        if len(frame) > 16_384:
            raise ValueError("request too large")
        request = json.loads(frame)
        from PySide6.QtCore import QPointF, QSize
        from PySide6.QtGui import QGuiApplication, QImage
        from PySide6.QtPdf import QPdfDocument, QPdfDocumentRenderOptions

        _app = QGuiApplication([])
        from priveopdf.utils import keep_c_numeric_locale

        keep_c_numeric_locale()
        doc = QPdfDocument()
        error = doc.load(request["path"])
        if error != QPdfDocument.Error.None_:
            result = {
                "error": "password" if error == QPdfDocument.Error.IncorrectPassword else "load"
            }
            pixels = b""
        else:
            count = doc.pageCount()
            if not 0 < count <= MAX_PAGES:
                raise ValueError("page limit")
            action = request["action"]
            pixels = b""
            if action == "search":
                query = request["query"]
                if (
                    not isinstance(query, str)
                    or not 0 < len(query) <= MAX_QUERY
                    or not query.isprintable()
                ):
                    raise ValueError("query")
                from PySide6.QtPdf import QPdfSearchModel

                # QtPdf searches without case; each page is searched on demand.
                model = QPdfSearchModel()
                model.setDocument(doc)
                model.setSearchString(query)
                matches = []
                for number in range(count):
                    for link in model.resultsOnPage(number):
                        # Stop at the cap, even inside a page full of matches.
                        if len(matches) >= MAX_SEARCH_MATCHES:
                            break
                        rects = [r.normalized() for r in link.rectangles()[:16]]
                        boxes = [
                            [round(v, 2) for v in (r.x(), r.y(), r.width(), r.height())]
                            for r in rects
                            if r.width() > 0 and r.height() > 0
                        ]
                        if boxes:
                            matches.append([number, boxes])
                    if len(matches) >= MAX_SEARCH_MATCHES:
                        break
                result = {"matches": matches}
            elif action == "metadata":
                result = {
                    "pages": [
                        [doc.pagePointSize(p).width(), doc.pagePointSize(p).height()]
                        for p in range(count)
                    ]
                }
            else:
                page = request["page"]
                if type(page) is not int or not 0 <= page < count:
                    raise ValueError("page")
                if action == "render":
                    width, height = request["size"]
                    if (
                        type(width) is not int
                        or type(height) is not int
                        or min(width, height) < 1
                        or max(width, height) > 8192
                        or width * height > MAX_PIXELS
                    ):
                        raise ValueError("size")
                    angle = request.get("rotation", 0)
                    if angle not in (0, 90, 180, 270):
                        raise ValueError("rotation")
                    annotations = request.get("annotations", False)
                    if annotations is not True and annotations is not False:
                        raise ValueError("annotations")
                    options = QPdfDocumentRenderOptions()
                    options.setRotation(QPdfDocumentRenderOptions.Rotation(angle // 90))
                    if annotations:
                        # What the photocopy prints (stamps, filled fields): a
                        # tool that blacks out the printed page shows it too.
                        options.setRenderFlags(QPdfDocumentRenderOptions.RenderFlag.Annotations)
                    image = doc.render(page, QSize(width, height), options)
                    image = image.convertToFormat(QImage.Format.Format_RGBA8888)
                    if image.isNull() or image.width() != width or image.height() != height:
                        raise ValueError("render")
                    pixels = bytes(image.constBits())
                    result = {"size": [width, height]}
                elif action == "selection":
                    coords = request["points"]
                    if len(coords) != 4 or any(
                        not isinstance(v, (int, float)) or not math.isfinite(v) or abs(v) > 100_000
                        for v in coords
                    ):
                        raise ValueError("selection")
                    start, end = QPointF(*coords[:2]), QPointF(*coords[2:])
                    # QtPdf includes the last character only in reading order, which
                    # runs backwards on a turned page: keep the fuller of both orders.
                    selection = max(
                        (doc.getSelection(page, start, end), doc.getSelection(page, end, start)),
                        key=lambda candidate: len(candidate.text()),
                    )
                    following = doc.getSelectionAtIndex(page, selection.endIndex(), 1)
                    box = following.boundingRectangle().normalized()
                    if selection.text() and (box.contains(start) or box.contains(end)):
                        # On a page turned a quarter, QtPdf leaves out the pointed character.
                        first = selection.startIndex()
                        selection = doc.getSelectionAtIndex(
                            page, first, selection.endIndex() + 1 - first
                        )
                    bounds = [polygon.boundingRect() for polygon in selection.bounds()[:4096]]
                    result = {
                        "text": selection.text()[:100_000],
                        "bounds": [
                            [rect.x(), rect.y(), rect.width(), rect.height()] for rect in bounds
                        ],
                    }
                elif action == "text_lines":
                    # Text boxes in reading order, for the viewer's selection geometry.
                    rects = [
                        polygon.boundingRect()
                        for polygon in doc.getAllText(page).bounds()[:MAX_TEXT_RECTS]
                    ]
                    result = {
                        "rects": [
                            [round(v, 2) for v in (r.x(), r.y(), r.width(), r.height())]
                            for r in rects
                            if r.width() > 0 and r.height() > 0
                        ]
                    }
                else:
                    raise ValueError("action")
        header = json.dumps(result, allow_nan=False, separators=(",", ":")).encode()
        if len(header) > MAX_HEADER:
            raise ValueError("header")
        sys.stdout.buffer.write(len(header).to_bytes(4, "big") + header + pixels)
        sys.stdout.buffer.flush()
        return 0
    except Exception:
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
