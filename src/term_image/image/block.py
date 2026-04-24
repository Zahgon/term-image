from __future__ import annotations

__all__ = ("BlockImage",)

import io
import os
from math import ceil
from operator import mul
from typing import Optional, Tuple, Union

import PIL

from .._ctlseqs import SGR_BG_DIRECT, SGR_DEFAULT, SGR_FG_DIRECT
from ..utils import get_fg_bg_colors
from .common import TextImage

LOWER_PIXEL = "\u2584"  # lower-half block element
UPPER_PIXEL = "\u2580"  # upper-half block element


class BlockImage(TextImage):
    """A render style using unicode half blocks and direct-color colour escape
    sequences.

    See :py:class:`TextImage` for the description of the constructor.
    """

    @classmethod
    def is_supported(cls):
        if cls._supported is None:
            COLORTERM = os.environ.get("COLORTERM") or ""
            TERM = os.environ.get("TERM") or ""
            cls._supported = (
                "truecolor" in COLORTERM or "24bit" in COLORTERM or "256color" in TERM
            )

        return cls._supported

    def _get_render_size(self) -> Tuple[int, int]:
        pass

    @staticmethod
    def _pixels_cols(
        *, pixels: Optional[int] = None, cols: Optional[int] = None
    ) -> int:
        return pixels if pixels is not None else cols

    @staticmethod
    def _pixels_lines(
        *, pixels: Optional[int] = None, lines: Optional[int] = None
    ) -> int:
        return ceil(pixels / 2) if pixels is not None else lines * 2

    def _render_image(
        self,
        img: PIL.Image.Image,
        alpha: Union[None, float, str],
        *,
        frame: bool = False,
        split_cells: bool = False,
    ) -> str:
        # NOTE:
        # It's more efficient to write separate strings to the buffer separately
        # than concatenate and write together.

        pass
