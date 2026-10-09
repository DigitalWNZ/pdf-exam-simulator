"""Synthetic item builders for parser tests (no PDF required)."""
import pymupdf

from exam_sim.parser.extract import Image, Line


def lines(*texts: str, page: int = 1) -> list[Line]:
    return [Line(text=t, page=page) for t in texts]


def image_bytes(w: int = 40, h: int = 30, fmt: str = "png") -> bytes:
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, w, h), False)
    pix.clear_with(128)
    return pix.tobytes(fmt)


def image(w: int = 40, h: int = 30, page: int = 1, fmt: str = "png") -> Image:
    return Image(data=image_bytes(w, h, fmt), ext=fmt, width=w, height=h, page=page)
