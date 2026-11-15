"""Logiciel externe encastré dans VectorDrive.

`ExternalApp` lance un programme, attend sa fenêtre principale et la loge
dans un onglet de l'espace de travail (`MainWindow.add_workspace`) : on
travaille dedans comme dans sa propre fenêtre, sans la mélanger à
VectorDrive (deux processus, chacun ses réglages et son thème).

Windows : la fenêtre est trouvée par son processus (ou un processus enfant,
pour les exécutables qui se relancent) et son titre, puis rattachée par
`QWindow.fromWinId`. Ailleurs, ou si on la détache, elle reste à part.
"""
from __future__ import annotations

import ntpath
import sys

from PySide6.QtCore import QProcess, Qt, QTimer, Signal
from PySide6.QtGui import QWindow
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ..i18n import tr

WAIT_MS = 30000            # délai d'apparition de la fenêtre principale
POLL_MS = 250
FRAMELESS_AFTER_MS = 10000  # sans fenêtre à barre de titre d'ici là : une fenêtre sans cadre convient
STABLE_MS = 1000           # une fenêtre n'est logée qu'après être restée ce temps (pas les fenêtres de passage)
WS_CAPTION = 0x00C00000


def _win32():
    import ctypes
    from ctypes import wintypes
    return ctypes, wintypes


def processes() -> list[tuple[int, int, str]]:
    """(pid, pid du parent, nom de l'exécutable) de tous les processus (Windows)."""
    if sys.platform != 'win32':
        return []
    ctypes, wintypes = _win32()

    class PE(ctypes.Structure):
        _fields_ = [('dwSize', wintypes.DWORD), ('cntUsage', wintypes.DWORD), ('th32ProcessID', wintypes.DWORD),
                    ('th32DefaultHeapID', ctypes.c_void_p), ('th32ModuleID', wintypes.DWORD),
                    ('cntThreads', wintypes.DWORD), ('th32ParentProcessID', wintypes.DWORD),
                    ('pcPriClassBase', ctypes.c_long), ('dwFlags', wintypes.DWORD), ('szExeFile', ctypes.c_wchar * 260)]
    k32 = ctypes.windll.kernel32
    snap = k32.CreateToolhelp32Snapshot(0x2, 0)
    out = []
    try:
        e = PE()
        e.dwSize = ctypes.sizeof(PE)
        ok = k32.Process32FirstW(snap, ctypes.byref(e))
        while ok:
            out.append((int(e.th32ProcessID), int(e.th32ParentProcessID), e.szExeFile))
            ok = k32.Process32NextW(snap, ctypes.byref(e))
    finally:
        k32.CloseHandle(snap)
    return out


def pids_named(exe: str) -> set[int]:
    """Processus dont l'exécutable porte ce nom (sans le dossier)."""
    name = ntpath.basename(exe).lower()
    return {p for p, _par, n in processes() if n.lower() == name}


def child_pids(pid: int) -> set[int]:
    """Le processus et tous ses descendants (Windows)."""
    if sys.platform != 'win32':
        return {pid}
    parents = {p: par for p, par, _n in processes()}
    out, grew = {pid}, True
    while grew:
        grew = False
        for p, par in parents.items():
            if par in out and p not in out:
                out.add(p)
                grew = True
    return out


def top_windows(pids: set[int], title_hint: str = '', *, framed_only: bool = False) -> list[tuple[int, str, int]]:
    """Fenêtres principales visibles de ces processus : (hwnd, titre, aire),
    les plus grandes d'abord ; `title_hint` : le titre doit le contenir ;
    `framed_only` : seulement celles qui ont une barre de titre (pas l'écran
    d'accueil qu'un logiciel montre pendant son chargement)."""
    if sys.platform != 'win32':
        return []
    ctypes, wintypes = _win32()
    u32 = ctypes.windll.user32
    found = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def cb(hwnd, _lp):
        pid = wintypes.DWORD()
        u32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if framed_only and (u32.GetWindowLongW(hwnd, -16) & WS_CAPTION) != WS_CAPTION:     # -16 : GWL_STYLE
            return True
        if pid.value in pids and u32.IsWindowVisible(hwnd) and not u32.GetWindow(hwnd, 4):     # 4 : GW_OWNER
            n = u32.GetWindowTextLengthW(hwnd)
            buf = ctypes.create_unicode_buffer(n + 1)
            u32.GetWindowTextW(hwnd, buf, n + 1)
            r = wintypes.RECT()
            u32.GetWindowRect(hwnd, ctypes.byref(r))
            area = max(0, r.right - r.left) * max(0, r.bottom - r.top)
            if buf.value and (not title_hint or title_hint.lower() in buf.value.lower()):
                found.append((int(hwnd), buf.value, area))
        return True
    u32.EnumWindows(cb, 0)
    return sorted(found, key=lambda f: -f[2])


def _strip_frame(hwnd: int) -> None:
    """Sans barre de titre ni bord : la fenêtre devient le contenu de l'onglet."""
    ctypes, _w = _win32()
    u32 = ctypes.windll.user32
    GWL_STYLE, WS_CAPTION, WS_THICKFRAME, WS_CHILD, WS_POPUP = -16, 0x00C00000, 0x00040000, 0x40000000, 0x80000000
    style = u32.GetWindowLongW(hwnd, GWL_STYLE) & 0xFFFFFFFF
    u32.SetWindowLongW(hwnd, GWL_STYLE, _signed((style & ~(WS_CAPTION | WS_THICKFRAME | WS_POPUP)) | WS_CHILD))


def _signed(v: int) -> int:
    """Style de fenêtre (32 bits) tel que SetWindowLongW l'attend."""
    v &= 0xFFFFFFFF
    return v - (1 << 32) if v >= 1 << 31 else v


class ExternalApp(QWidget):
    """Onglet qui héberge un logiciel externe ; `bar` reçoit les boutons
    propres à ce logiciel (envoyer le dessin…)."""

    embedded = Signal(int)
    finished = Signal(int)

    def __init__(self, program: str, args: list[str], title: str, *, title_hint: str = '', cwd: str = '',
                 parent=None):
        super().__init__(parent)
        self.program, self.args, self.title = program, list(args), title
        self.title_hint = title_hint or title
        self.cwd = cwd
        self.hwnd = 0
        self.container = None
        self.proc = QProcess(self)
        self.proc.finished.connect(self._finished)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        top = QHBoxLayout()
        top.setContentsMargins(4, 2, 4, 2)
        self.status = QLabel(tr('{0} : démarrage…').format(title))
        top.addWidget(self.status)
        top.addStretch(1)
        self.bar = top
        self.detach_btn = QPushButton(tr('Détacher'))
        self.detach_btn.setToolTip(tr('Rendre sa propre fenêtre à {0}').format(title))
        self.detach_btn.clicked.connect(self.detach)
        top.addWidget(self.detach_btn)
        lay.addLayout(top)
        self.body = QVBoxLayout()
        lay.addLayout(self.body, 1)
        self.waited = 0
        self._cand, self._cand_ms = 0, 0            # fenêtre candidate et depuis combien de temps
        self.timer = QTimer(self)
        self.timer.setInterval(POLL_MS)
        self.timer.timeout.connect(self._poll)
        self.watch = QTimer(self)
        self.watch.setInterval(1000)
        self.watch.timeout.connect(self._watch)

    def start(self) -> bool:
        if self.cwd:
            self.proc.setWorkingDirectory(self.cwd)
        self.proc.start(self.program, self.args)
        if not self.proc.waitForStarted(10000):
            self.status.setText(tr('{0} n\'a pas pu démarrer : {1}').format(self.title, self.proc.errorString()))
            return False
        self.waited = 0
        self.timer.start()
        return True

    def _poll(self) -> None:
        self.waited += POLL_MS
        pid = int(self.proc.processId() or 0)
        # d'abord une vraie fenêtre principale : l'écran d'accueil (NeoDrive)
        # porte le même titre mais n'a pas de barre de titre, et disparaît
        # NeoDrive montre aussi, une fraction de seconde, une fenêtre de passage
        # au même titre : on attend qu'une fenêtre reste STABLE_MS
        framed = self.waited < FRAMELESS_AFTER_MS
        wins = top_windows(child_pids(pid), self.title_hint, framed_only=framed) if pid else []
        if wins:
            h = wins[0][0]
            if h != self._cand:
                self._cand, self._cand_ms = h, 0
            else:
                self._cand_ms += POLL_MS
            if self._cand_ms >= STABLE_MS:
                self.timer.stop()
                self._cand, self._cand_ms = 0, 0
                self.attach(h)
            return
        self._cand, self._cand_ms = 0, 0
        if self.waited >= WAIT_MS:
            self.timer.stop()
            self.status.setText(tr('{0} tourne dans sa propre fenêtre').format(self.title))

    def attach(self, hwnd: int) -> None:
        """Loge la fenêtre native `hwnd` dans l'onglet."""
        self.hwnd = hwnd
        if sys.platform == 'win32':
            _strip_frame(hwnd)
        win = QWindow.fromWinId(hwnd)
        win.setFlags(Qt.WindowType.FramelessWindowHint)
        self.container = QWidget.createWindowContainer(win, self)
        self.container.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.body.addWidget(self.container, 1)
        self.status.setText(self.title)
        self.embedded.emit(hwnd)
        if sys.platform == 'win32':
            self.watch.start()

    def _watch(self) -> None:
        """La fenêtre logée a disparu alors que le logiciel tourne encore
        (écran d'accueil, fenêtre recréée) : on attend la suivante."""
        if not self.hwnd or self.container is None:
            self.watch.stop()
            return
        ctypes, _w = _win32()
        if ctypes.windll.user32.IsWindow(self.hwnd):
            return
        self.watch.stop()
        self.container.setParent(None)
        self.container.deleteLater()
        self.container = None
        self.hwnd = 0
        if self.proc.state() != QProcess.ProcessState.NotRunning:
            self.status.setText(tr('{0} : démarrage…').format(self.title))
            self.waited = 0
            self.timer.start()

    def detach(self) -> None:
        if not self.container:
            return
        if sys.platform == 'win32' and self.hwnd:
            ctypes, _w = _win32()
            u32 = ctypes.windll.user32
            u32.SetParent(self.hwnd, 0)
            style = u32.GetWindowLongW(self.hwnd, -16) & 0xFFFFFFFF
            u32.SetWindowLongW(self.hwnd, -16, _signed((style & ~0x40000000) | 0x00C00000 | 0x00040000))
            u32.ShowWindow(self.hwnd, 3)                   # agrandie
        self.container.setParent(None)
        self.container = None
        self.status.setText(tr('{0} tourne dans sa propre fenêtre').format(self.title))

    def stop(self, wait_ms: int = 8000) -> bool:
        """Ferme le logiciel comme si on cliquait sa croix (il peut demander
        d'enregistrer). Jamais d'arrêt forcé : s'il n'est pas fermé à temps,
        il est détaché et reste ouvert dans sa propre fenêtre. Rend True s'il
        est fermé."""
        self.timer.stop()
        self.watch.stop()
        pid = int(self.proc.processId() or 0)
        pids = child_pids(pid) if pid else set()
        if sys.platform == 'win32':
            ctypes, _w = _win32()
            for hwnd, _t, _a in ([(self.hwnd, '', 0)] if self.hwnd else top_windows(pids)):
                ctypes.windll.user32.PostMessageW(hwnd, 0x0010, 0, 0)          # WM_CLOSE
        elif self.proc.state() != QProcess.ProcessState.NotRunning:
            self.proc.terminate()
        closed = self.proc.state() == QProcess.ProcessState.NotRunning or self.proc.waitForFinished(wait_ms)
        if closed and sys.platform == 'win32':
            closed = not top_windows(pids)
        if not closed:
            self.detach()
        return closed

    def _finished(self, code, _status=None) -> None:
        self.timer.stop()
        self.watch.stop()
        self.status.setText(self.gone_message())
        self.finished.emit(int(code))

    def gone_message(self) -> str:
        """Le logiciel s'est arrêté. Parti sans jamais montrer de fenêtre, il
        a sans doute passé la main à un exemplaire déjà ouvert (instance
        unique, comme NeoDrive) : le dire, plutôt qu'un onglet vide."""
        if self.hwnd or self.container is not None or sys.platform != 'win32':
            return tr('{0} est fermé').format(self.title)
        others = pids_named(self.program)
        if not others:
            return tr("{0} s'est fermé sans ouvrir de fenêtre").format(self.title)
        if top_windows(others, self.title_hint):
            return tr('{0} était déjà ouvert dans sa propre fenêtre : il a pris le relais').format(self.title)
        return tr('{0} est déjà lancé mais sans fenêtre visible : fermez-le dans le Gestionnaire des tâches '
                  '(processus {1}), puis rouvrez cet onglet').format(self.title, ', '.join(map(str, sorted(others))))
