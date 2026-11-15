"""Windows : un liseré d'un pixel autour d'une fenêtre sans cadre qui couvre tout l'écran.

Pourquoi : une fenêtre dont la surface fait exactement l'écran, avec une vue OpenGL dedans (la 3D), passe en plein
écran exclusif — l'image clignote, les menus et les bulles paraissent mal. Qt l'évite pour son propre plein écran par
un liseré d'un pixel (`HasBorderInFullScreen`) : la fenêtre couvre l'écran, sa surface un pixel de moins de chaque
côté. Notre plein écran est une fenêtre sans cadre (voir `MainWindow._enter_full_screen`), et Qt retire toute bordure
d'une fenêtre sans cadre : il répond lui-même au calcul de la zone cliente. On pose donc le style `WS_BORDER` et on
répond à ce calcul avant lui, par un filtre d'événements natifs installé le temps du plein écran seulement.

Ailleurs que sous Windows (et hors écran) : rien à faire, `set_border` rend faux.
"""
from __future__ import annotations

import sys

from PySide6.QtCore import QAbstractNativeEventFilter
from PySide6.QtWidgets import QApplication

WM_NCCALCSIZE = 0x0083
GWL_STYLE, WS_BORDER = -16, 0x00800000
# SWP_NOSIZE | SWP_NOMOVE | SWP_NOZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED
FRAME_CHANGED = 0x0001 | 0x0002 | 0x0004 | 0x0010 | 0x0020


def supported() -> bool:
    app = QApplication.instance()
    return sys.platform == 'win32' and app is not None and QApplication.platformName() == 'windows'


class BorderFilter(QAbstractNativeEventFilter):
    """Répond au calcul de la zone cliente de la fenêtre `hwnd` : un pixel de moins de chaque côté."""

    def __init__(self, hwnd: int):
        super().__init__()
        self.hwnd = int(hwnd)

    def nativeEventFilter(self, event_type, message):            # noqa: N802 (API Qt)
        from ctypes import wintypes
        msg = wintypes.MSG.from_address(int(message))
        if msg.message != WM_NCCALCSIZE or not msg.wParam or int(msg.hWnd or 0) != self.hwnd:
            return False, 0
        rect = wintypes.RECT.from_address(msg.lParam)            # rgrc[0] : la fenêtre proposée → la zone cliente
        if rect.right - rect.left > 2 and rect.bottom - rect.top > 2:
            rect.left += 1
            rect.top += 1
            rect.right -= 1
            rect.bottom -= 1
        return True, 0


def set_border(widget, on: bool) -> bool:
    """Pose (ou retire) le liseré d'un pixel de la fenêtre `widget` ; rend vrai si son état natif a été touché."""
    old = getattr(widget, '_border_filter', None)
    if not supported():
        return False
    import ctypes
    app = QApplication.instance()
    if old is not None:
        app.removeNativeEventFilter(old)
        widget._border_filter = None
    if not on and old is None:
        return False
    user32 = ctypes.windll.user32
    get, put = user32.GetWindowLongPtrW, user32.SetWindowLongPtrW
    get.restype, get.argtypes = ctypes.c_ssize_t, [ctypes.c_void_p, ctypes.c_int]
    put.restype, put.argtypes = ctypes.c_ssize_t, [ctypes.c_void_p, ctypes.c_int, ctypes.c_ssize_t]
    hwnd = int(widget.winId())
    style = get(ctypes.c_void_p(hwnd), GWL_STYLE)
    if on:
        widget._border_filter = BorderFilter(hwnd)
        app.installNativeEventFilter(widget._border_filter)
        put(ctypes.c_void_p(hwnd), GWL_STYLE, style | WS_BORDER)
    else:
        put(ctypes.c_void_p(hwnd), GWL_STYLE, style & ~WS_BORDER)
    user32.SetWindowPos(ctypes.c_void_p(hwnd), None, 0, 0, 0, 0, FRAME_CHANGED)   # la zone cliente est recalculée
    return True
