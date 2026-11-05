"""Native dark window decorations without replacing desktop window controls."""
import ctypes

from PyQt6.QtCore import QEvent, QObject
from PyQt6.QtGui import QPalette
from PyQt6.QtWidgets import QWidget


def set_x11_dark_variant(window_id):
    """Request the WM's dark decoration on X11 (including XWayland)."""
    try:
        x11 = ctypes.CDLL('libX11.so.6')
    except OSError:
        return False
    x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
    x11.XOpenDisplay.restype = ctypes.c_void_p
    x11.XInternAtom.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
    x11.XInternAtom.restype = ctypes.c_ulong
    x11.XChangeProperty.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_ulong,
                                  ctypes.c_ulong, ctypes.c_int, ctypes.c_int,
                                  ctypes.c_char_p, ctypes.c_int]
    x11.XChangeProperty.restype = ctypes.c_int
    x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
    x11.XCloseDisplay.restype = ctypes.c_int
    display = x11.XOpenDisplay(None)
    if not display:
        return False
    try:
        prop = x11.XInternAtom(display, b'_GTK_THEME_VARIANT', 0)
        utf8 = x11.XInternAtom(display, b'UTF8_STRING', 0)
        x11.XChangeProperty(display, int(window_id), prop, utf8, 8, 0, b'dark', 4)
    finally:
        # Closing flushes the request before releasing this short-lived connection.
        x11.XCloseDisplay(display)
    return True


class NativeWindowTheme(QObject):
    def eventFilter(self, widget, event):
        if (event.type() == QEvent.Type.Show and isinstance(widget, QWidget)
                and widget.isWindow() and self.parent().platformName() == 'xcb'):
            set_x11_dark_variant(widget.winId())
        return False


def apply_native_palette(app, palette):
    # Qt Wayland's bradient decoration reads the application palette, not the
    # QWidget stylesheet/palette. This also covers native dialog decorations.
    app.setPalette(QPalette(palette))
    if not hasattr(app, '_opl_native_window_theme'):
        app._opl_native_window_theme = NativeWindowTheme(app)
        app.installEventFilter(app._opl_native_window_theme)
