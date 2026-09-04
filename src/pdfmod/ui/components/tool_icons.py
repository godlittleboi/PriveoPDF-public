from __future__ import annotations

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QApplication, QWidget

from pdfmod.ui.theme.tokens import PALETTES, ThemeTokens

TOOL_ICON_BY_ID: dict[str, str] = {
    "view": "view_page",
    "merge": "merge_pages",
    "split": "split_cut",
    "remove": "remove_cross",
    "extract": "extract_out",
    "reorder": "reorder_grid",
    "insert": "insert_pages",
    "blank_page": "blank_page",
    "rotate": "rotate_arrow",
    "scan_to_pdf": "scanner",
    "compress": "compress_inward",
    "repair_pdf": "repair_tool",
    "ocr_pdf": "ocr_target",
    "jpg_to_pdf": "image_to_doc",
    "word_to_pdf": "text_doc_to_pdf",
    "powerpoint_to_pdf": "slide_to_pdf",
    "excel_to_pdf": "sheet_to_pdf",
    "html_to_pdf": "html_to_pdf",
    "pdf_to_jpg": "doc_to_image",
    "pdf_to_word": "pdf_to_text_doc",
    "pdf_to_powerpoint": "pdf_to_slide",
    "pdf_to_excel": "pdf_to_sheet",
    "pdf_to_pdfa": "archive_doc",
    "page_numbers": "page_numbers",
    "watermark": "watermark",
    "crop": "crop_marks",
    "edit_pdf": "edit_pen",
    "pdf_forms": "form_fields",
    "unlock_pdf": "unlock",
    "protect": "lock",
    "sign_pdf": "pen_signature",
    "redact_pdf": "redact_bar",
    "compare_pdf": "compare_pages",
    "summarize_pdf_ai": "ai_summary",
    "translate_pdf_ai": "translate_doc",
}

TOOL_ICON_SIGNATURES: dict[str, tuple[str, ...]] = {
    "view_page": ("page", "eye"),
    "merge_pages": ("two_pages", "join_bar"),
    "split_cut": ("page", "vertical_cut"),
    "remove_cross": ("page", "cross"),
    "extract_out": ("stack", "page_out"),
    "reorder_grid": ("three_pages", "order_arrow"),
    "insert_pages": ("two_pages", "insertion_arrow"),
    "blank_page": ("page", "plus"),
    "rotate_arrow": ("page", "circular_arrow"),
    "scanner": ("scanner", "scan_line"),
    "compress_inward": ("page", "inward_arrows"),
    "repair_tool": ("page", "wrench"),
    "ocr_target": ("page", "target"),
    "image_to_doc": ("image", "arrow", "page"),
    "text_doc_to_pdf": ("text_lines", "arrow", "page"),
    "slide_to_pdf": ("slide", "arrow", "page"),
    "sheet_to_pdf": ("grid_sheet", "arrow", "page"),
    "html_to_pdf": ("html_brackets", "arrow", "page"),
    "doc_to_image": ("page", "arrow", "image"),
    "pdf_to_text_doc": ("page", "arrow", "text_lines"),
    "pdf_to_slide": ("page", "arrow", "slide"),
    "pdf_to_sheet": ("page", "arrow", "grid_sheet"),
    "archive_doc": ("page", "archive_a"),
    "page_numbers": ("page", "numbers"),
    "watermark": ("page", "stamp"),
    "crop_marks": ("crop_corners", "page"),
    "edit_pen": ("page", "pen"),
    "form_fields": ("page", "checkboxes"),
    "unlock": ("open_lock",),
    "lock": ("closed_lock",),
    "pen_signature": ("signature_curve", "pen_tip"),
    "redact_bar": ("page", "black_bar"),
    "compare_pages": ("two_pages", "compare_gap"),
    "ai_summary": ("page", "spark_lines"),
    "translate_doc": ("page", "language_blocks"),
    "document": ("page", "text"),
    "shield": ("shield", "check"),
}


def icon_for_tool_id(tool_id: str) -> str:
    return TOOL_ICON_BY_ID.get(tool_id, "document")


def tool_icon_signature(icon_name: str) -> tuple[str, ...]:
    return TOOL_ICON_SIGNATURES.get(icon_name, TOOL_ICON_SIGNATURES["document"])


class LineIcon(QWidget):
    def __init__(
        self,
        icon_name: str = "document",
        accent_role: str = "primary",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._icon_name = icon_name
        self._accent_role = accent_role
        self.setFixedSize(40, 40)

    def set_icon(self, icon_name: str, accent_role: str | None = None) -> None:
        self._icon_name = icon_name
        if accent_role is not None:
            self._accent_role = accent_role
        self.update()

    def paintEvent(self, event) -> None:  # noqa: ANN001
        del event
        tokens = _current_tokens()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        color = _role_color(tokens, self._accent_role)
        dark = QColor(tokens.color_text_main)

        def block(
            x: int,
            y: int,
            w: int = 4,
            h: int = 4,
            fill: QColor | None = None,
        ) -> None:
            painter.fillRect(QRect(x, y, w, h), fill or color)

        def rect(x: int, y: int, w: int, h: int, fill: bool = False) -> None:
            painter.setPen(_pixel_pen(color.name(), 2))
            painter.drawRect(QRect(x, y, w, h))
            if fill:
                painter.fillRect(QRect(x + 2, y + 2, max(0, w - 3), max(0, h - 3)), color)

        def line(x1: int, y1: int, x2: int, y2: int, width: int = 3) -> None:
            painter.setPen(_pixel_pen(color.name(), width))
            painter.drawLine(x1, y1, x2, y2)

        def page(x: int = 10, y: int = 7, w: int = 20, h: int = 26) -> None:
            rect(x, y, w, h)
            block(x + w - 6, y + 2, 4, 4)

        def arrow_right(x: int = 17, y: int = 18) -> None:
            block(x, y, 10, 4)
            block(x + 8, y - 4, 4, 4)
            block(x + 8, y + 4, 4, 4)

        name = self._icon_name
        if name == "view_page":
            page(8, 8, 16, 24)
            rect(20, 14, 12, 10)
            block(24, 17, 4, 4, dark)
        elif name == "merge_pages":
            rect(7, 8, 13, 18)
            rect(20, 14, 13, 18)
            block(16, 20, 8, 4)
            block(18, 18, 4, 8)
        elif name == "split_cut":
            page(8, 7, 24, 26)
            block(18, 9, 4, 22)
            block(10, 33, 7, 4)
            block(24, 33, 8, 4)
        elif name == "remove_cross":
            page(9, 7, 20, 26)
            line(12, 12, 30, 30)
            line(30, 12, 12, 30)
        elif name == "extract_out":
            rect(7, 10, 16, 22)
            rect(12, 6, 16, 22)
            rect(23, 14, 9, 10)
            arrow_right(17, 18)
        elif name == "reorder_grid":
            rect(7, 8, 9, 9)
            rect(19, 8, 9, 9)
            rect(7, 21, 9, 9)
            block(25, 24, 8, 4)
            block(29, 20, 4, 12)
        elif name == "insert_pages":
            rect(5, 8, 12, 24)
            rect(23, 8, 12, 24)
            block(14, 18, 12, 4)
            block(18, 14, 4, 12)
        elif name == "blank_page":
            page(8, 7, 22, 26)
            block(16, 18, 10, 4)
            block(19, 15, 4, 10)
        elif name == "rotate_arrow":
            page(12, 10, 16, 20)
            block(9, 8, 16, 4)
            block(25, 8, 4, 8)
            block(21, 16, 10, 4)
            block(8, 20, 4, 9)
            block(8, 29, 20, 4)
        elif name == "scanner":
            rect(7, 18, 26, 12)
            block(10, 10, 20, 4)
            block(12, 14, 16, 3)
            block(11, 24, 18, 2)
        elif name == "compress_inward":
            page(11, 8, 18, 24)
            block(5, 14, 8, 4)
            block(27, 14, 8, 4)
            block(9, 12, 4, 8)
            block(27, 12, 4, 8)
            block(5, 24, 8, 4)
            block(27, 24, 8, 4)
        elif name == "repair_tool":
            page(8, 8, 18, 24)
            line(23, 26, 33, 16)
            block(30, 12, 5, 5)
            block(20, 27, 5, 5)
        elif name == "ocr_target":
            page(8, 8, 18, 24)
            rect(22, 12, 10, 10)
            block(25, 15, 4, 4)
            block(11, 15, 10, 3)
            block(11, 22, 8, 3)
        elif name == "image_to_doc":
            rect(6, 10, 14, 14)
            block(15, 14, 3, 3)
            block(9, 20, 8, 3)
            arrow_right(18, 19)
            page(26, 8, 9, 24)
        elif name == "text_doc_to_pdf":
            block(6, 10, 14, 3)
            block(6, 17, 12, 3)
            block(6, 24, 14, 3)
            arrow_right(18, 18)
            page(27, 8, 8, 24)
        elif name == "slide_to_pdf":
            rect(5, 10, 15, 12)
            block(8, 24, 9, 3)
            arrow_right(18, 18)
            page(27, 8, 8, 24)
        elif name == "sheet_to_pdf":
            rect(5, 9, 15, 15)
            block(10, 10, 2, 13)
            block(6, 15, 13, 2)
            arrow_right(18, 18)
            page(27, 8, 8, 24)
        elif name == "html_to_pdf":
            block(5, 13, 4, 4)
            block(9, 17, 4, 4)
            block(5, 21, 4, 4)
            block(16, 13, 4, 4)
            block(12, 17, 4, 4)
            block(16, 21, 4, 4)
            arrow_right(18, 18)
            page(27, 8, 8, 24)
        elif name == "doc_to_image":
            page(5, 8, 10, 24)
            arrow_right(14, 18)
            rect(25, 10, 12, 14)
            block(33, 14, 3, 3)
            block(27, 21, 8, 3)
        elif name == "pdf_to_text_doc":
            page(5, 8, 10, 24)
            arrow_right(14, 18)
            block(27, 11, 10, 3)
            block(27, 18, 8, 3)
            block(27, 25, 10, 3)
        elif name == "pdf_to_slide":
            page(5, 8, 10, 24)
            arrow_right(14, 18)
            rect(26, 11, 12, 10)
            block(29, 24, 7, 3)
        elif name == "pdf_to_sheet":
            page(5, 8, 10, 24)
            arrow_right(14, 18)
            rect(26, 9, 12, 15)
            block(31, 10, 2, 13)
            block(27, 15, 10, 2)
        elif name == "archive_doc":
            page(8, 7, 22, 26)
            block(13, 25, 4, 4)
            block(17, 17, 4, 12)
            block(21, 25, 4, 4)
            block(15, 15, 8, 3)
        elif name == "page_numbers":
            page(8, 7, 22, 26)
            block(13, 14, 4, 12)
            block(20, 14, 7, 3)
            block(23, 17, 4, 4)
            block(20, 24, 8, 3)
        elif name == "watermark":
            page(8, 7, 22, 26)
            rect(14, 15, 12, 10)
            block(17, 18, 6, 4)
        elif name == "crop_marks":
            block(8, 8, 4, 12)
            block(8, 8, 12, 4)
            block(28, 8, 4, 12)
            block(20, 8, 12, 4)
            block(8, 20, 4, 12)
            block(8, 28, 12, 4)
            block(28, 20, 4, 12)
            block(20, 28, 12, 4)
        elif name == "edit_pen":
            page(8, 8, 18, 24)
            line(18, 28, 32, 14)
            block(30, 12, 4, 4)
        elif name == "form_fields":
            page(8, 7, 22, 26)
            rect(12, 13, 5, 5)
            block(20, 14, 7, 3)
            rect(12, 23, 5, 5)
            block(20, 24, 7, 3)
        elif name == "unlock":
            rect(9, 17, 22, 15)
            block(13, 10, 4, 8)
            block(23, 8, 4, 4)
            block(27, 11, 4, 4)
        elif name == "lock":
            rect(9, 16, 22, 16)
            block(13, 10, 4, 8)
            block(23, 10, 4, 8)
            block(17, 8, 10, 4)
        elif name == "pen_signature":
            line(7, 25, 14, 18)
            line(14, 18, 20, 27)
            line(20, 27, 29, 16)
            block(29, 12, 5, 5)
        elif name == "redact_bar":
            page(8, 7, 22, 26)
            block(11, 17, 16, 6, dark)
            block(11, 26, 12, 4, dark)
        elif name == "compare_pages":
            rect(7, 8, 13, 24)
            rect(22, 8, 13, 24)
            block(19, 13, 3, 4)
            block(19, 23, 3, 4)
        elif name == "ai_summary":
            page(8, 8, 18, 24)
            block(29, 9, 4, 4)
            block(27, 15, 8, 3)
            block(29, 20, 4, 4)
        elif name == "translate_doc":
            page(8, 8, 18, 24)
            block(28, 11, 4, 4)
            block(24, 15, 12, 3)
            block(26, 21, 8, 4)
        elif name == "shield":
            block(18, 6, 6, 4)
            block(10, 10, 22, 4)
            block(10, 14, 4, 10)
            block(28, 14, 4, 10)
            block(14, 24, 14, 4)
            block(18, 28, 6, 4)
            block(15, 19, 4, 4, QColor(tokens.color_pixel_green))
            block(19, 23, 4, 4, QColor(tokens.color_pixel_green))
            block(23, 15, 4, 4, QColor(tokens.color_pixel_green))
        else:
            page(9, 7, 22, 26)
            block(14, 14, 12, 4)
            block(14, 21, 12, 4)
            block(14, 28, 8, 4)


def _current_tokens() -> ThemeTokens:
    app = QApplication.instance()
    preset = app.property("priveopdf_theme_preset") if app is not None else "dark_pro"
    if isinstance(preset, str):
        return PALETTES.get(preset, PALETTES["dark_pro"])
    mode = app.property("priveopdf_theme_mode") if app is not None else "dark"
    return PALETTES.get(mode, PALETTES["dark_pro"])


def _role_color(tokens: ThemeTokens, role: str) -> QColor:
    role_map = {
        "neutral": tokens.color_border_default,
        "primary": tokens.color_pixel_blue,
        "info": tokens.color_info,
        "success": tokens.color_success,
        "warning": tokens.color_warning,
        "danger": tokens.color_danger,
        "color_pixel_blue": tokens.color_pixel_blue,
        "color_pixel_yellow": tokens.color_pixel_yellow,
        "color_pixel_green": tokens.color_pixel_green,
        "color_pixel_red": tokens.color_pixel_red,
    }
    return QColor(role_map.get(role, tokens.color_pixel_blue))


def _pixel_pen(color: str, width: int) -> QPen:
    pen = QPen(QColor(color), width)
    pen.setCapStyle(Qt.PenCapStyle.SquareCap)
    pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
    return pen
