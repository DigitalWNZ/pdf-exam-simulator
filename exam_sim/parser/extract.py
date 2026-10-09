"""PDF → ordered stream of text lines and images (PyMuPDF), with generic noise filters."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import Union

import pymupdf

QUESTION_HEADER = re.compile(r"^Question #(\d+)$")
FOOTER_PATTERNS = (re.compile(r"^\[\d{6}\]$"), re.compile(r"^https?://\S+$"))
MIN_IMAGE_SIDE = 20
WATERMARK_PAGE_FRACTION = 0.5
WATERMARK_MIN_PAGES = 3


@dataclass
class Line:
    text: str
    page: int


@dataclass(eq=False)
class Image:
    data: bytes
    ext: str
    width: int
    height: int
    page: int

    @cached_property
    def digest(self) -> str:
        return hashlib.sha1(self.data).hexdigest()


Item = Union[Line, Image]


def read_items(pdf_path: Path) -> tuple[list[Item], int]:
    """Return (items in reading order across all pages, page_count). No filtering."""
    items: list[Item] = []
    with pymupdf.open(pdf_path) as doc:
        for page in doc:
            pno = page.number + 1
            for block in page.get_text("dict", sort=True)["blocks"]:
                if block["type"] == 1:
                    items.append(Image(data=block["image"], ext=block["ext"],
                                       width=int(block["width"]), height=int(block["height"]), page=pno))
                    continue
                for line in block["lines"]:
                    text = " ".join("".join(span["text"] for span in line["spans"]).split())
                    if text:
                        items.append(Line(text=text, page=pno))
        return items, doc.page_count


def filter_items(items: list[Item], page_count: int) -> list[Item]:
    """Drop watermark images, tiny images, footer lines and everything before the first question."""
    pages_by_digest: dict[str, set[int]] = {}
    for it in items:
        if isinstance(it, Image):
            pages_by_digest.setdefault(it.digest, set()).add(it.page)
    threshold = max(1, page_count) * WATERMARK_PAGE_FRACTION
    watermarks = {d for d, pages in pages_by_digest.items()
                  if len(pages) >= WATERMARK_MIN_PAGES and len(pages) > threshold}

    out: list[Item] = []
    seen_question = False
    for it in items:
        if isinstance(it, Image):
            if it.digest in watermarks or it.width < MIN_IMAGE_SIDE or it.height < MIN_IMAGE_SIDE:
                continue
        else:
            if any(p.match(it.text) for p in FOOTER_PATTERNS):
                continue
            if QUESTION_HEADER.match(it.text):
                seen_question = True
        if seen_question:
            out.append(it)
    return out


def to_png(data: bytes, ext: str) -> bytes:
    if ext.lower() == "png":
        return data
    return pymupdf.Pixmap(data).tobytes("png")


def extract_items(pdf_path: Path) -> list[Item]:
    items, page_count = read_items(pdf_path)
    return filter_items(items, page_count)
