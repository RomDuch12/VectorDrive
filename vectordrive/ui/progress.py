"""Barre de progression et bouton Annuler pour tout calcul.

    from .progress import run, Cancelled
    try:
        res = run(self, tr('Calcul des parcours'), strategies.compute_all, doc, setup)
    except Cancelled:
        return

Le calcul tourne dans un fil de travail (l'interface reste vivante) ; la
fenêtre de progression n'apparaît qu'au-delà de `SHOW_MS` (rien ne
clignote pour un calcul court). Annuler : le calcul s'arrête au prochain
point de contrôle (`core.progress.step` / `check`) et `run` lève
`Cancelled` aussitôt ; un calcul sans point de contrôle finit en arrière-
plan, son résultat est jeté. Le calcul ne doit pas toucher à l'interface
ni au dessin affiché : il rend un résultat, appliqué ensuite par l'appelant.
"""
from __future__ import annotations

import contextvars
import threading
import time

from PySide6.QtCore import QEvent, QEventLoop, QObject, Qt, QTimer
from PySide6.QtGui import QWindow
from PySide6.QtWidgets import QApplication, QProgressDialog

from ..core import progress as P
from ..core.progress import Cancelled  # noqa: F401  (réexporté pour les appelants)
from ..i18n import tr

SHOW_MS = 350
#: réglage F10 › Performances : pendant un calcul, le processus passe en priorité basse (Windows)
LOW_PRIORITY = False
_LOW_DEPTH = 0                  # calculs imbriqués : la priorité revient à la fin du dernier


def _set_low_priority(on: bool) -> None:
    """Priorité du processus : basse pendant les calculs longs (Windows), normale ensuite."""
    global _LOW_DEPTH
    import sys
    if sys.platform != 'win32':
        return
    _LOW_DEPTH += 1 if on else -1
    if (on and _LOW_DEPTH != 1) or (not on and _LOW_DEPTH != 0):
        return
    try:
        k = _kernel32()
        k.SetPriorityClass(k.GetCurrentProcess(), 0x4000 if on else 0x20)     # BELOW_NORMAL / NORMAL
    except (AttributeError, OSError):
        pass


def _kernel32():
    """kernel32 avec les types des fonctions de priorité (poignée 64 bits)."""
    import ctypes
    from ctypes import wintypes
    k = ctypes.WinDLL('kernel32', use_last_error=True)
    k.GetCurrentProcess.restype = wintypes.HANDLE
    k.SetPriorityClass.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    k.SetPriorityClass.restype = wintypes.BOOL
    k.GetPriorityClass.argtypes = [wintypes.HANDLE]
    k.GetPriorityClass.restype = wintypes.DWORD
    return k
#: essais : la fenêtre n'est jamais montrée, l'annulation se simule
AUTO_CANCEL_AFTER_MS: float | None = None
#: fenêtres de progression ouvertes (calculs imbriqués : chacune reste cliquable)
_DIALOGS: list = []


_INPUT = {QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonRelease, QEvent.Type.MouseButtonDblClick,
          QEvent.Type.MouseMove, QEvent.Type.KeyPress, QEvent.Type.KeyRelease, QEvent.Type.Wheel,
          QEvent.Type.ShortcutOverride, QEvent.Type.Shortcut, QEvent.Type.Drop, QEvent.Type.DragEnter}


class _InputGuard(QObject):
    """Pendant un calcul, le dessin ne doit pas changer : clics, touches et
    molette sont ignorés, sauf dans la fenêtre de progression (Annuler)."""

    def eventFilter(self, obj, ev) -> bool:
        if ev.type() not in _INPUT:
            return False
        return not self.inside(obj)

    def inside(self, obj) -> bool:
        """obj appartient à la fenêtre de progression (widget ou fenêtre
        native : les clics passent d'abord par la QWindow du dialogue)."""
        if isinstance(obj, QWindow):
            return any(obj is d.windowHandle() for d in _DIALOGS)
        w = obj
        while w is not None:
            if any(w is d for d in _DIALOGS):
                return True
            w = w.parent()
        return False


def run(parent, title: str, fn, *args, **kwargs):
    """Exécute fn(*args, **kwargs) avec avancement et Annuler ; rend son
    résultat, lève `Cancelled` si l'utilisateur annule, ou l'exception du
    calcul."""
    task = P.Task(title)
    box: dict = {}
    ctx = contextvars.copy_context()

    def work():
        token = P.attach(task)
        try:
            box['result'] = fn(*args, **kwargs)
        except BaseException as ex:                  # transmis au fil de l'interface
            box['error'] = ex
        finally:
            P.detach(token)
            box['done'] = True

    th = threading.Thread(target=lambda: ctx.run(work), name=f'vd-calcul-{title}', daemon=True)
    app = QApplication.instance()
    cursor = app is not None
    guard = _InputGuard()
    if cursor:
        QApplication.setOverrideCursor(Qt.CursorShape.BusyCursor)
        app.installEventFilter(guard)
    low = LOW_PRIORITY
    if low:
        _set_low_priority(True)
    th.start()
    dlg = None
    loop = QEventLoop()
    t0 = time.monotonic()
    timer = QTimer()
    timer.setInterval(40)

    def tick():
        nonlocal dlg
        if box.get('done') or task.cancelled.is_set():
            loop.quit()
            return
        ms = (time.monotonic() - t0) * 1000
        if AUTO_CANCEL_AFTER_MS is not None and ms >= AUTO_CANCEL_AFTER_MS:
            task.cancel()
            loop.quit()
            return
        if dlg is None and ms >= SHOW_MS and AUTO_CANCEL_AFTER_MS is None:
            dlg = QProgressDialog(title, tr('Annuler'), 0, 1000, parent)
            dlg.setWindowTitle(tr('Calcul en cours'))
            dlg.setWindowModality(Qt.WindowModality.WindowModal)
            dlg.setMinimumDuration(0)
            dlg.setAutoClose(False)
            dlg.setAutoReset(False)
            dlg.canceled.connect(task.cancel)
            _DIALOGS.append(dlg)
            dlg.show()
        if dlg is not None:
            if task.fraction < 0:
                dlg.setRange(0, 0)
            else:
                dlg.setRange(0, 1000)
                dlg.setValue(int(task.fraction * 1000))
            secs = int(ms / 1000)
            dlg.setLabelText(title + (f'\n{task.text}' if task.text else '') + (f'\n{secs} s' if secs >= 2 else ''))

    timer.timeout.connect(tick)
    timer.start()
    try:
        if not box.get('done'):
            loop.exec()
    finally:
        timer.stop()
        if dlg is not None:
            _DIALOGS.remove(dlg)
            dlg.close()
            dlg.deleteLater()
        if cursor:
            app.removeEventFilter(guard)
            QApplication.restoreOverrideCursor()
        if low:
            _set_low_priority(False)
    if task.cancelled.is_set() and not box.get('done'):
        raise Cancelled()
    if 'error' in box:
        raise box['error']
    return box.get('result')
