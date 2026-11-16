"""Le pont « entrée et sortie standard » vers le serveur MCP local : `VectorDrive.exe --mcp`.

Un client MCP qui lance lui-même ses serveurs (Claude Desktop ; Claude Code aussi le peut) lance cette commande. Elle
ne montre aucune fenêtre : chaque ligne lue sur l'entrée standard — un message JSON-RPC — est envoyée au serveur local
du VectorDrive ouvert (port et jeton lus dans les réglages, relus à chaque message), et la réponse est écrite sur la
sortie standard, une ligne par réponse, rien d'autre.

VectorDrive fermé, ou serveur arrêté : le pont répond lui-même à `initialize`, `ping` et `tools/list` — l'assistant
voit les outils — et refuse les appels d'outil en disant quoi faire.

Le jeton ne part qu'à 127.0.0.1, sans mandataire, et aucune redirection n'est suivie ; une réponse qui ne vient pas
de VectorDrive (un autre logiciel sur le port) n'est jamais recopiée : le pont répond alors comme si VectorDrive
était fermé.
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request

from .protocol import INTERNAL_ERROR, INVALID_REQUEST, Server, ToolError, error
from .tools import ToolSet

OFFLINE = ('VectorDrive is not running, or its local MCP server is off. Ask the user to start VectorDrive and to '
           'tick "Start the local MCP server with VectorDrive" in Options (F10) > General > Assistant (MCP server).')
LATE = ('VectorDrive did not answer in time. The change may or may not have been made: read the drawing '
        '(list_objects) before trying again.')
OTHER_SETTINGS = ('VectorDrive refused the token: this bridge and the running VectorDrive do not use the same '
                  'settings (two installations, or a portable copy and an installed one?). Ask the user to copy the '
                  'Claude Desktop entry again from the VectorDrive that is running.')
#: l'en-tête `Server` du serveur local (`agent.server`) : la réponse vient bien de VectorDrive
SIGNATURE = 'VectorDrive-MCP'
#: un outil peut attendre l'interface (60 s) puis calculer : le pont attend plus longtemps que lui
TIMEOUT_S = 300.0
#: après une connexion refusée, tant de secondes sans réessayer (un refus coûte une à deux secondes sous Windows)
DOWN_S = 3.0


def locate() -> tuple:
    """(adresse, jeton) du serveur local d'après les réglages ; ('', '') : pas demandé, ou jamais lancé sur ce
    poste. Les réglages sont seulement lus."""
    from .. import portable
    from . import server as AS
    st = portable.settings(migrate=False)
    token = str(st.value(AS.KEY_TOKEN, '') or '').strip()
    if not token or st.value(AS.KEY_ON, False) not in (True, 'true', 1, '1'):
        return '', ''
    return f'http://{AS.HOST}:{AS.port_of(st)}{AS.PATH}', token


def _offline(_fn):
    raise ToolError(OFFLINE)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Aucune redirection suivie : le jeton n'irait pas ailleurs qu'à l'adresse demandée."""

    def redirect_request(self, *_args, **_kwargs):
        return None


class NotOurs(Exception):
    """Ce qui répond sur le port n'est pas le serveur de VectorDrive."""


def _timed_out(ex: BaseException) -> bool:
    return isinstance(ex, TimeoutError) or isinstance(getattr(ex, 'reason', None), TimeoutError)


class Bridge:
    """Passe les messages au serveur local trouvé par `locate()` ; répond à sa place quand il n'est pas là."""

    def __init__(self, locate_fn=locate, version: str = '0', timeout: float = TIMEOUT_S):
        self.locate = locate_fn
        self.timeout = timeout
        self.offline = Server(ToolSet(None, run=_offline), version)
        # jamais par un mandataire, jamais de redirection
        self._opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
        self._down_until = 0.0

    def forward(self, text: str) -> str | None:
        """La réponse du serveur local (une ligne de JSON), None s'il n'a rien à répondre. `ConnectionError` : pas
        de serveur ; `NotOurs` : un autre logiciel répond ; `urllib.error.HTTPError` signée : VectorDrive refuse."""
        url, token = self.locate()
        if not url or time.monotonic() < self._down_until:
            raise ConnectionError('no local server')
        req = urllib.request.Request(url, data=text.encode('utf-8', 'replace'), method='POST', headers={
            'Content-Type': 'application/json', 'Accept': 'application/json', 'Authorization': 'Bearer ' + token})
        try:
            with self._opener.open(req, timeout=self.timeout) as r:
                ours = str(r.headers.get('Server') or '').startswith(SIGNATURE)
                data = r.read()
        except urllib.error.HTTPError as ex:
            if not str(ex.headers.get('Server') or '').startswith(SIGNATURE):
                raise NotOurs(f'HTTP {ex.code}') from None
            raise
        except ConnectionRefusedError:
            self._down_until = time.monotonic() + DOWN_S
            raise
        except urllib.error.URLError as ex:
            if isinstance(ex.reason, ConnectionRefusedError):
                self._down_until = time.monotonic() + DOWN_S
            raise
        if not ours:
            raise NotOurs('no signature')
        if not data:
            return None
        try:
            return json.dumps(json.loads(data.decode('utf-8')))      # une seule ligne, en ASCII, et bien du JSON
        except ValueError:
            raise NotOurs('not JSON') from None

    def handle_line(self, line: str) -> str | None:
        """Une ligne lue (un message) : la ligne à écrire, ou None. Ne lève jamais."""
        line = line.strip()
        if not line:
            return None
        try:
            return self.forward(line)
        except urllib.error.HTTPError as ex:             # VectorDrive refuse (jeton d'autres réglages…)
            return self._errors(line, INVALID_REQUEST, OTHER_SETTINGS if ex.code == 401
                                else f'VectorDrive refused the request (HTTP {ex.code})')
        except Exception as ex:                          # noqa: BLE001 — absent, arrêté, autre logiciel, coupé
            if _timed_out(ex):
                return self._errors(line, INTERNAL_ERROR, LATE)
            try:
                return self.offline.handle_text(line)
            except Exception:                            # noqa: BLE001 — le pont ne s'arrête pas pour un message
                return self._errors(line, INTERNAL_ERROR, 'the VectorDrive bridge could not answer')

    @staticmethod
    def _errors(line: str, code: int, why: str) -> str | None:
        """Une erreur pour chaque demande du message (aucune pour une notification)."""
        try:
            message = json.loads(line)
        except (ValueError, RecursionError):
            return None
        asked = [m for m in (message if isinstance(message, list) else [message])
                 if isinstance(m, dict) and 'id' in m and 'method' in m]
        out = [error(m['id'], code, why) for m in asked]
        if not out:
            return None
        return json.dumps(out if isinstance(message, list) else out[0])


def serve(stdin, stdout, bridge: Bridge) -> int:
    """Lit `stdin` (binaire) ligne par ligne jusqu'à sa fermeture ; écrit les réponses sur `stdout` (binaire)."""
    for raw in stdin:
        out = bridge.handle_line(raw.decode('utf-8', 'replace'))
        if out is not None:
            # une ligne par réponse ; json.dumps n'écrit ni saut de ligne ni caractère hors ASCII
            stdout.write(out.replace('\n', ' ').encode('utf-8', 'backslashreplace') + b'\n')
            stdout.flush()
    return 0


def _stream(obj, fd: int, mode: str):
    buf = getattr(obj, 'buffer', None)
    if buf is not None:
        return buf
    try:
        return os.fdopen(fd, mode, closefd=False)
    except OSError:
        pass
    if sys.platform == 'win32':                          # exécutable sans console : les tuyaux du client sont là
        import ctypes
        import msvcrt
        get = ctypes.windll.kernel32.GetStdHandle
        get.restype = ctypes.c_void_p
        handle = get(-10 - fd)                           # -10 : entrée, -11 : sortie
        if handle and handle != ctypes.c_void_p(-1).value:
            try:
                return os.fdopen(msvcrt.open_osfhandle(handle, os.O_RDONLY if fd == 0 else 0), mode)
            except OSError:
                pass
    return None


def std_streams() -> tuple:
    """Les flux binaires de l'entrée et de la sortie standard, aussi quand `sys.stdin` ou `sys.stdout` manquent
    (exécutable sans console lancé avec des tuyaux) ; None pour un flux qui n'existe pas."""
    return _stream(sys.stdin, 0, 'rb'), _stream(sys.stdout, 1, 'wb')


def main() -> int:
    stdin, stdout = std_streams()
    if stdin is None or stdout is None:
        return 2
    # rien d'autre que des messages sur la sortie standard : un `print` égaré va sur la sortie d'erreur
    sys.stdout = sys.stderr if sys.stderr is not None else open(os.devnull, 'w', encoding='utf-8')
    from .. import __version__
    return serve(stdin, stdout, Bridge(locate, __version__))
