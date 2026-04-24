""".. Widgets for urwid"""

from __future__ import annotations

__all__ = ("UrwidImage", "UrwidImageCanvas", "UrwidImageScreen")

from typing import Optional, Tuple

import urwid

from .. import _ctlseqs as ctlseqs

# These sequences are used during performance-critical operations that occur often
from .._ctlseqs import BEGIN_SYNCED_UPDATE, END_SYNCED_UPDATE, ESC_b, SGR_DEFAULT_b
from ..exceptions import UrwidImageError
from ..image import BaseImage, ITerm2Image, KittyImage, Size, TextImage
from ..utils import arg_type_error, get_terminal_name_version, lock_tty, write_tty

# NOTE: Any new "private" attribute of any subclass of an urwid class should be
# prepended with "_ti" to prevent clashes with names used by urwid itself.


class UrwidImage(urwid.Widget):
    """Image widget (box/flow) for the urwid TUI framework.

    Args:
        image: The image to be rendered by the widget.
        format_spec: :ref:`Render format specifier <format-spec>`. Padding width and
          height are ignored.
        upscale: If ``True``, the image will be upscaled to fit maximally within the
          available size, if necessary, while still preserving the aspect ratio.
          Otherwise, the image is never upscaled.

    Raises:
        TypeError: An argument is of an inappropriate type.
        ValueError: An argument is of an appropriate type but has an
          unexpected/invalid value.
        term_image.exceptions.StyleError: Invalid style-specific format specifier.
        term_image.exceptions.UrwidImageError: Too many image widgets rendering images
          with the *kitty* render style.

    | Any ample space in the widget's render size is filled with spaces.
    | For animated images, the current frame (at render-time) is rendered.

    TIP:
        If *image* is of a :ref:`graphics-based <graphics-based>` render style and the
        widget is being used as or within a **flow** widget, with overlays or in any
        other case where the canvas will require vertical trimming, make sure to use a
        render method that splits images across lines such as the **LINES** render
        method for *kitty* and *iterm2* render styles.

    NOTE:
        * The `z-index` style-specific format spec field for
          :py:class:`~term_image.image.KittyImage` is ignored as this is used
          internally.
        * A **maximum** of ``2**32 - 2`` instances initialized with
          :py:class:`~term_image.image.KittyImage` instances may exist at the same time.

    IMPORTANT:
        This is defined if and only if the ``urwid`` package is available.
    """

    _sizing = frozenset((urwid.BOX, urwid.FLOW))
    ignore_focus = True

    _ti_error_placeholder = None

    # For kitty images
    _ti_disguise_state = 0
    _ti_free_z_indexes = set()

    # Progresses thus: 1, -1, 2, -2, 3, ..., 2**31 - 1, -(2**31 - 1)
    # This sequence results in shorter image escape sequences compared to starting
    # from -(2**31)
    _ti_next_z_index = 1

    def __init__(
        self, image: BaseImage, format_spec: str = "", *, upscale: bool = False
    ) -> None:
        if not isinstance(image, BaseImage):
            raise arg_type_error("image", image)

        if not isinstance(format_spec, str):
            raise arg_type_error("format_spec", format_spec)
        *fmt, alpha, style_args = image._check_format_spec(format_spec)

        if not isinstance(upscale, bool):
            raise arg_type_error("upscale", upscale)

        super().__init__()
        self._ti_image = image
        self._ti_h_align, _, self._ti_v_align, _ = fmt
        self._ti_alpha = alpha
        self._ti_style_args = style_args
        self._ti_sizing = Size.FIT if upscale else Size.AUTO

        if isinstance(image, TextImage):
            style_args["split_cells"] = True
        elif isinstance(image, KittyImage):
            style_args["z_index"] = self._ti_z_index = self._ti_get_z_index()

            # Since Konsole doesn't blend images placed at the same location and
            # z-index, unlike Kitty (and potentially others), `blend=True` is
            # better on Konsole as it reduces/eliminates flicker.
            if get_terminal_name_version()[0] != "konsole":
                # To clear directly overlapped images when urwid redraws a line without
                # a change in image position
                style_args["blend"] = False

    def __del__(self) -> None:
        if hasattr(self, "_ti_z_index"):
            __class__._ti_free_z_indexes.add(self._ti_z_index)

    image = property(
        lambda self: self._ti_image,
        doc="""
        The image rendered by the widget

        :type: BaseImage

        GET:
            Returns the image instance rendered by the widget.
        """,
    )

    def render(self, size: Tuple[int, int], focus: bool = False) -> urwid.Canvas:
        pass

    def rows(self, size: Tuple[int], focus: bool = False) -> int:
        pass

    @classmethod
    def set_error_placeholder(cls, widget: Optional[urwid.Widget]) -> None:
        """Sets the widget to be rendered in place of an image when rendering fails.

        Args:
            widget: The placeholder widget or ``None`` to remove the placeholder.

        Raises:
            TypeError: *widget* is not an urwid widget.

        If set, any exception raised during rendering is **suppressed** and the
        placeholder is rendered in place of the image.
        """
        pass

    @staticmethod
    def _ti_get_z_index() -> int:
        if __class__._ti_free_z_indexes:
            return __class__._ti_free_z_indexes.pop()

        z_index = __class__._ti_next_z_index
        if z_index == 2**31:
            raise UrwidImageError("Too many image widgets with the kitty render style")
        __class__._ti_next_z_index = -z_index if z_index > 0 else -z_index + 1

        return z_index

    def _ti_change_disguise(self) -> None:
        """See :py:meth`UrwidImageCanvas._ti_change_disguise`."""
        pass


class UrwidImageCanvas(urwid.Canvas):
    """Image canvas for the urwid TUI framework.

    Args:
        render: The rendered image.
        size: The canvas size. Also, the size of the rendered (and formatted) image.
        image_size: The size with which the image was rendered (excluding padding).

    NOTE:
        The canvas outputs blanks (spaces) for :ref:`graphics-based <graphics-based>`
        images when horizontal trimming is required (e.g when a widget is laid over
        an image). This is temporary as horizontal trimming will be implemented in the
        future.

        This canvas is intended to be rendered by :py:class:`UrwidImage` (or a subclass
        of it) only. Otherwise, the output isn't guaranteed to be as expected.

    WARNING:
        The constructor of this class performs NO argument validation at all for the
        sake of performance. If instantiating this class directly, make sure to pass
        appropriate arguments or create subclass, override the constructor and perform
        the validation.

    IMPORTANT:
        This is defined if and only if the ``urwid`` package is available.
    """

    _ti_disguise_state = 0

    def __init__(
        self, render: str, size: Tuple[int, int], image_size: Tuple[int, int]
    ) -> None:
        super().__init__()
        self.size = size
        self._ti_image_size = image_size

        # On the last row of the screen, urwid inserts the second to the last
        # character after writing the last (though placed before it i.e inserted),
        # thereby messing up an escape sequence occurring at the end.
        # See `urwid.raw_display.Screen._last_row()`.
        # Any line of the image could potentially be the last on the screen as a result
        # of trimming.
        self._ti_lines = [line + b"\0\0" for line in render.encode().split(b"\n")]

    def cols(self) -> int:
        pass

    def content(self, trim_left=0, trim_top=0, cols=None, rows=None, attr_map=None):
        pass

    def rows(self) -> int:
        pass

    @classmethod
    def _ti_change_disguise(cls) -> None:
        """Changes the hidden text embedded on every line, such that every line of the
        canvas is different in every state.

        The reason for this is, ``urwid`` will not redraw lines that have not changed
        since the last screen update. So this is to trick ``urwid`` into taking every
        line containing a part of an image as different in each state.

        This is used to force redraws of all images on screen, particularly when
        graphics-based images are cleared and their positions have not change so
        much.
        """
        pass

    @staticmethod
    def _ti_calc_trim(
        size: int,
        image_size: int,
        trim_side1: int,
        pad_side1: int,
        trim_side2: int,
        pad_side2: int,
    ) -> Tuple[int, int, int, int]:
        """Calculates the new padding size on both sides after trimming and size to be
        trimmed off the rendered image from both ends, all **along the same axis**.

        Args:
            size: Canvas size.
            image_size: Size with which the image was rendered (excluding padding).
            trim_side1: Size to trim off the canvas (image with padding) from one size.
            pad_side1: Padding size on one side of the image.
            trim_side2: Size to trim off the canvas (image with padding) from the
              opposite size.
            pad_side2: Padding size on the opposite side of the image.

        Returns:
            A 4-tuple containing the following dimensions, in the given order:

            - new_pad_side1: The trimmed padding size on one side.
            - trim_image_side1: The size to be trimmed off the image on one side.
            - trim_image_side2: The size to be trimmed off the image on the opposite
              side.
            - new_pad_side2: The trimmed padding size on the opposite side.

        The dimensions given as arguments must be along the **same axis** (vertical or
        horizontal).
        """
        pass


class UrwidImageScreen(urwid.raw_display.Screen):
    """A screen that supports drawing images.

    It monitors images of some :ref:`graphics-based <graphics-based>` render styles
    and clears them off the screen when necessary (e.g at startup, when scrolling,
    upon terminal resize and at exit).

    See the baseclass for further description.

    IMPORTANT:
        This is defined if and only if the ``urwid`` package is available.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._ti_screen_canv = None
        self._ti_image_cviews = frozenset()

    def clear(self):
        pass

    def clear_images(self, *widgets: UrwidImage, now: bool = False) -> None:
        """Clears on-screen images of :ref:`graphics-based <graphics-based>`
        styles **that support/require such an operation**.

        Args:
            widgets: Image widgets to clear.

              All on-screen images rendered by each of the widgets are cleared,
              provided the widget was initialized with a
              :py:class:`term_image.image.KittyImage` instance.

              If none is given, all images (of styles **that support/require such an
              operation**) on-screen are cleared.

            now: If ``True`` the images are cleared immediately.
              Otherwise, they're cleared when next the output buffer is flushed,
              such as at the next screen redraw.
        """
        pass

    # `@lock_tty` prevents queries during a synced update.
    # Otherwise, responses would be delayed until the synced update ends and that might
    # be after the query has timed out.
    @lock_tty
    def draw_screen(self, maxres, canvas):
        """See the description of the baseclass' method.

        Synchronizes output on terminal emulators that support the feature to
        reduce/eliminate image flickering and screen tearing.
        """
        pass

    @lock_tty
    def flush(self):
        """See the baseclass' method for the description."""
        pass

    @lock_tty
    def get_available_raw_input(self):
        """See the baseclass' method for the description."""
        pass

    @lock_tty
    def write(self, data):
        """See the baseclass' method for the description."""
        return super().write(data)

    def _start(self, *args, **kwargs):
        pass

    def _stop(self):
        pass

    def _ti_clear_images(self):
        pass
