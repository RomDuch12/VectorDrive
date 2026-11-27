"""Une seule fenêtre de VectorDrive par session Windows : un nouveau
lancement (double-clic sur un dessin, raccourci…) passe son fichier à la
fenêtre déjà ouverte, qui l'ouvre dans un onglet et passe devant ; le
nouveau processus s'arrête aussitôt. `--nouvelle-fenetre` : une fenêtre à
part. `VECTORDRIVE_INSTANCE` : autre nom de canal (essais)."""
from __future__ import annotations

import getpass
import os
import re

from PySide6.QtNetwork import QLocalServer, QLocalSocket


def channel() -> str:
    if os.environ.get('VECTORDRIVE_INSTANCE'):
        return os.environ['VECTORDRIVE_INSTANCE']
    try:
        user = getpass.getuser()
    except Exception:                                    # pragma: no cover - compte sans nom
        user = 'utilisateur'
    return 'VectorDrive-' + re.sub(r'[^A-Za-z0-9_.-]', '_', user)


#: préfixe d'un fichier pour le traitement par lots (au lieu de l'ouvrir)
LOTS = 'lots\t'


def forward(path: str, timeout_ms: int = 400, kind: str = '') -> bool:
    """Passe `path` (vide : seulement montrer la fenêtre) à la fenêtre déjà
    ouverte ; False s'il n'y en a pas. `kind='lots'` : au traitement par lots."""
    s = QLocalSocket()
    s.connectToServer(channel())
    if not s.waitForConnected(timeout_ms):
        return False
    line = (os.path.abspath(path) if path else '')
    if kind == 'lots':
        line = LOTS + line
    s.write(line.encode('utf-8') + b'\n')
    s.flush()
    s.waitForBytesWritten(2000)
    s.waitForReadyRead(5000)                             # accusé de la fenêtre (le fichier est pris)
    s.disconnectFromServer()
    return True


def forward_lots(paths, wait_s: float = 0.0) -> bool:
    """Passe les fichiers au traitement par lots de la fenêtre ouverte ; en
    attend une `wait_s` secondes (une autre fenêtre est en train de démarrer :
    l'explorateur lance une commande par fichier sélectionné)."""
    import time
    end = time.monotonic() + wait_s
    while True:
        if forward(paths[0], kind='lots'):
            for p in paths[1:]:
                forward(p, kind='lots')
            return True
        if time.monotonic() >= end:
            return False
        time.sleep(0.2)


def starting_lock():
    """Verrou « une fenêtre démarre » (QLockFile pris), ou None s'il est déjà
    pris par un autre lancement."""
    import tempfile
    from PySide6.QtCore import QLockFile
    lock = QLockFile(os.path.join(tempfile.gettempdir(), channel() + '.demarrage.lock'))
    lock.setStaleLockTime(60_000)
    return lock if lock.tryLock(0) else None


def taken() -> bool:
    """Une fenêtre de VectorDrive (n'importe quelle version) tient le canal — cherché sans rien lui envoyer
    (`app_update.answers`)."""
    from ..app_update import answers
    return answers(channel())


def forward_allowed(new_window: bool, lots, adopting: bool) -> bool:
    """Ce lancement passe son fichier à la fenêtre déjà ouverte (`forward`) : ni fenêtre à part, ni traitement par
    lots (il a son propre chemin), ni reprise d'une ancienne version en attente (`portable.launch_adopting` : la
    fenêtre ouverte est peut-être l'ancienne, et rien ne serait proposé)."""
    return not new_window and not lots and not adopting


def forward_waiting(path: str, wait_s: float = 30.0, step_s: float = 0.25) -> bool:
    """`forward`, en attendant jusqu'à `wait_s` secondes que la fenêtre d'un autre lancement écoute (elle démarre
    après la question de la reprise, `portable.WAITED`)."""
    import time
    end = time.monotonic() + wait_s
    while True:
        if forward(path):
            return True
        if time.monotonic() >= end:
            return False
        time.sleep(step_s)


#: canal libéré mais pas pris (`serve` rend None) : autant de nouvelles tentatives, une par intervalle
SERVE_TRIES = 20


def serve_when_free(win, probe=None, every_ms: int = 3000):
    """Le canal est tenu par une autre fenêtre (l'ancienne version, encore ouverte pendant la reprise, demande du
    27/11) : jamais deux fenêtres dessus — il est pris par `win` dès qu'il est libre (`probe`, d'office `taken`,
    toutes les `every_ms` ms) ; libre mais pas pris (`serve` rend None) : retenté, `SERVE_TRIES` fois au plus. Rend
    la minuterie."""
    from PySide6.QtCore import QTimer
    timer = QTimer(win)
    timer.setInterval(every_ms)
    failed = [0]

    def tick():
        if getattr(win, '_closing', False) or getattr(win, '_instance_server', None) is not None:
            timer.stop()
            return
        try:
            busy = bool((probe or taken)())
        except Exception:                                # noqa: BLE001 — pas de réponse sûre : on attend
            return
        if busy:
            return
        win._instance_server = serve(win)
        if win._instance_server is not None:
            timer.stop()
            return
        failed[0] += 1
        if failed[0] >= SERVE_TRIES:                     # rien de plus à espérer : cette fenêtre reste seule
            timer.stop()
    timer.timeout.connect(tick)
    timer.start()
    win._instance_timer = timer
    return timer


def serve(win) -> QLocalServer | None:
    """Écoute les lancements suivants : chaque fichier reçu s'ouvre dans un
    onglet de `win`, qui passe au premier plan."""
    server = QLocalServer(win)
    if not server.listen(channel()):
        QLocalServer.removeServer(channel())             # canal laissé par une fenêtre arrêtée brutalement
        if not server.listen(channel()):
            return None

    def accept():
        while server.hasPendingConnections():
            sock = server.nextPendingConnection()
            sock.setProperty('vd_buffer', b'')
            sock.readyRead.connect(lambda s=sock: _read(win, s))
            sock.disconnected.connect(lambda s=sock: (_read(win, s), s.deleteLater()))
            _read(win, sock)                             # message déjà arrivé (lancement rapide)
    server.newConnection.connect(accept)
    return server


def _read(win, sock) -> None:
    try:
        data = bytes(sock.readAll())
    except RuntimeError:                                 # prise déjà détruite
        return
    if not data:
        return
    buf = bytes(sock.property('vd_buffer') or b'') + data
    *lines, rest = buf.split(b'\n')
    sock.setProperty('vd_buffer', rest)
    for line in lines:
        try:
            sock.write(b'ok\n')                          # accusé : le lanceur peut s'arrêter
            sock.flush()
        except RuntimeError:
            pass
        raw = line.decode('utf-8', 'replace')
        path = raw.strip()
        if raw.startswith(LOTS):                         # clic droit « Traitement par lots… »
            if raw[len(LOTS):].strip():
                win.batch_add([raw[len(LOTS):].strip()])
        elif path:
            win.open_path(path)
        if win.isMinimized():
            win.showNormal()
        win.raise_()
        win.activateWindow()
