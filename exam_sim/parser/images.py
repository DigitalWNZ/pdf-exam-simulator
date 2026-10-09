"""Writes question images to <bank_dir>/images as numbered PNGs and returns content blocks."""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Callable

from .extract import Image, to_png
from .model import Block, ImageBlock, TextBlock

MISSING_IMAGE_TEXT = "[image missing]"


class ImageWriter:
    def __init__(self, bank_dir: Path):
        self.images_dir = bank_dir / "images"
        self.counts: dict[int, int] = {}
        self.written = 0
        self.warnings: list[str] = []

    def reset_dir(self) -> None:
        shutil.rmtree(self.images_dir, ignore_errors=True)
        self.images_dir.mkdir(parents=True, exist_ok=True)

    def writer_for(self, number: int) -> Callable[[Image], Block]:
        def write(img: Image) -> Block:
            k = self.counts.get(number, 0) + 1
            self.counts[number] = k
            name = f"q{number:03d}_{k}.png"
            try:
                data = to_png(img.data, img.ext)
            except Exception as exc:  # any decoder failure → placeholder, never abort the parse
                self.warnings.append(f"Q{number}: image {k} on page {img.page} could not be converted ({exc})")
                return TextBlock(text=MISSING_IMAGE_TEXT)
            self.images_dir.mkdir(parents=True, exist_ok=True)
            (self.images_dir / name).write_bytes(data)
            self.written += 1
            return ImageBlock(src=f"images/{name}", w=img.width, h=img.height)

        return write
