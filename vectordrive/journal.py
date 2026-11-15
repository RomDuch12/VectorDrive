"""Journal des erreurs inattendues.

Une erreur que rien ne rattrape — dans une commande, dans un fil de calcul — n'était écrite que sur la sortie
d'erreur. Dans l'exécutable empaqueté, qui n'a pas de console, elle disparaissait : la commande semblait ne rien
faire. Elle est maintenant écrite dans `erreurs.txt` (dossier des données de VectorDrive) et dite dans la barre
d'état de la fenêtre.
"""
from __future__ import annotations

import datetime as dt
import sys
import threading
import time
import traceback
import weakref

NAME = 'erreurs.txt'
#: au-delà, le journal ne garde que sa moitié la plus récente
MAX_BYTES = 512_000
#: une même erreur, de nouveau dans ce délai (s) : pas réécrite (une erreur dans un dessin ou un geste de souris se
#: répète à chaque événement)
REPEAT_S = 5.0
_previous = None
_previous_thread = None
_window = None
_last = ['', 0.0]


def path():
    from .portable import data_dir
    return data_dir() / NAME


def record(etype, value, tb, where: str = '') -> str:
    """Écrit l'erreur dans le journal ; rend son résumé (« ValueError : … »). Ne lève jamais."""
    last = f'{getattr(etype, "__name__", etype)} : {value}'
    try:
        text = ''.join(traceback.format_exception(etype, value, tb))
        p = path()
        key, now = f'{where}|{text}', time.monotonic()
        if key == _last[0] and now - _last[1] < REPEAT_S and p.exists():
            _last[1] = now
            return last
        _last[:] = [key, now]
        p.parent.mkdir(parents=True, exist_ok=True)
        if p.exists() and p.stat().st_size > MAX_BYTES:  # la moitié la plus récente, à partir d'un début de ligne
            tail = p.read_bytes()[-MAX_BYTES // 2:]
            nl = tail.find(b'\n')
            p.write_bytes(tail[nl + 1:] if 0 <= nl < len(tail) - 1 else tail.decode('utf-8', 'ignore').encode('utf-8'))
        from . import __version__
        head = f'\n=== {dt.datetime.now().isoformat(timespec="seconds")} — VectorDrive {__version__}'
        with open(p, 'a', encoding='utf-8') as fh:
            fh.write(head + (f' — {where}' if where else '') + '\n' + text)
    except Exception:                                    # noqa: BLE001 — le journal ne doit jamais casser l'application
        pass
    return last


def _tell(last: str) -> None:
    win = _window() if _window is not None else None
    if win is None or threading.current_thread() is not threading.main_thread():
        return
    try:
        from PySide6.QtCore import QTimer
        from .i18n import tr
        text = tr('Erreur inattendue : {0} — détail dans {1}').format(last, path())
        QTimer.singleShot(0, lambda: win.statusBar().showMessage(text, 20000))
    except Exception:                                    # noqa: BLE001
        pass


def _hook(etype, value, tb) -> None:
    if etype is not None and issubclass(etype, KeyboardInterrupt):
        if _previous is not None:
            _previous(etype, value, tb)
        return
    _tell(record(etype, value, tb))
    if _previous is not None and sys.stderr is not None:
        _previous(etype, value, tb)                      # et la sortie d'erreur, quand il y en a une


def _thread_hook(args) -> None:
    name = getattr(args.thread, 'name', '') if args.thread is not None else ''
    record(args.exc_type, args.exc_value, args.exc_traceback, where=f'fil « {name} »')
    if _previous_thread is not None and sys.stderr is not None:
        try:
            _previous_thread(args)                       # et la sortie d'erreur, quand il y en a une
        except Exception:                                # noqa: BLE001
            pass


def install(window=None) -> None:
    """Pose le journal (une fois) ; `window` : la fenêtre dont la barre d'état dit l'erreur."""
    global _previous, _previous_thread, _window
    if window is not None:
        _window = weakref.ref(window)
    if sys.excepthook is not _hook:
        _previous = sys.excepthook
        sys.excepthook = _hook
    if threading.excepthook is not _thread_hook:
        _previous_thread = threading.excepthook
        threading.excepthook = _thread_hook


def uninstall() -> None:
    """Rend les crochets d'origine (essais)."""
    global _previous, _previous_thread, _window
    if sys.excepthook is _hook:
        sys.excepthook = _previous or sys.__excepthook__
    if threading.excepthook is _thread_hook:
        threading.excepthook = _previous_thread or threading.__excepthook__
    _previous = _previous_thread = _window = None
