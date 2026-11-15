"""Avancement et annulation des calculs (sans Qt).

Un calcul long appelle `step(i, n, texte)` (ou `check()`) dans ses
boucles : l'interface (`ui.progress.run`) affiche l'avancement et, si
l'utilisateur annule, le prochain `step` / `check` lève `Cancelled`. Hors
d'une tâche suivie, ces appels ne font rien (coût négligeable) : les
fonctions restent utilisables telles quelles (tests, ligne de commande).

    def calcul(objets):
        for i, o in enumerate(objets):
            progress.step(i, len(objets), 'objet {0}')
            …
"""
from __future__ import annotations

import contextvars
import threading
import time


class Cancelled(Exception):
    """Calcul annulé par l'utilisateur."""


class Task:
    """État partagé entre le calcul (fil de travail) et l'interface."""

    def __init__(self, title: str = ''):
        self.title = title
        self.fraction = 0.0                 # 0…1 ; -1 : indéterminé
        self.text = ''
        self.cancelled = threading.Event()
        self.started = time.monotonic()
        self._span = (0.0, 1.0)             # sous-tâche : part de la barre qui lui revient

    def cancel(self) -> None:
        self.cancelled.set()

    def report(self, fraction: float, text: str | None = None) -> None:
        a, b = self._span
        self.fraction = a + (b - a) * min(1.0, max(0.0, fraction))
        if text is not None:
            self.text = text


_current: contextvars.ContextVar[Task | None] = contextvars.ContextVar('vd_task', default=None)


def current() -> Task | None:
    return _current.get()


def attach(task: Task | None):
    """Rattache la tâche au contexte courant (fil de travail) ; rend le jeton."""
    return _current.set(task)


def detach(token) -> None:
    _current.reset(token)


def check() -> None:
    """Lève `Cancelled` si l'utilisateur a annulé."""
    t = _current.get()
    if t is not None and t.cancelled.is_set():
        raise Cancelled()


def step(i: float, n: float, text: str = '') -> None:
    """Avancement i / n (et vérifie l'annulation)."""
    t = _current.get()
    if t is None:
        return
    if t.cancelled.is_set():
        raise Cancelled()
    if text:
        from ..i18n import tr
        text = tr(text).format(int(i) + 1, int(n))
    t.report((i / n) if n else 0.0, text or None)


class span:
    """Sous-tâche : `with progress.span(0.2, 0.8):` — les `step` qu'elle
    contient ne remplissent que cette part de la barre."""

    def __init__(self, a: float, b: float):
        self.a, self.b = a, b
        self.prev = None

    def __enter__(self):
        t = _current.get()
        if t is not None:
            self.prev = t._span
            pa, pb = t._span
            t._span = (pa + (pb - pa) * self.a, pa + (pb - pa) * self.b)
        return self

    def __exit__(self, *exc):
        t = _current.get()
        if t is not None and self.prev is not None:
            t._span = self.prev
        return False
