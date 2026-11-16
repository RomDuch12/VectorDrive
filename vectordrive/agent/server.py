"""Le serveur MCP local de VectorDrive : un assistant (Claude Code, Claude Desktop par le pont `--mcp`…) s'y branche
pour lire et modifier le dessin ouvert, avec les outils de `agent.tools`.

- HTTP sur 127.0.0.1 seulement (jamais sur le réseau), transport « Streamable HTTP » de MCP : un POST de JSON-RPC sur
  `/mcp`, une réponse en JSON ; pas de flux (GET : 405).
- Trois gardes : l'en-tête `Host` doit être cette machine (pas de nom détourné vers 127.0.0.1), l'en-tête `Origin`
  d'une page web est refusé, et chaque demande porte le jeton de la fenêtre (`Authorization: Bearer …`).
- Les outils s'exécutent dans le fil de l'interface, un à la fois ; une fenêtre modale ouverte les fait refuser.
- Bibliothèque standard seulement (`http.server`), rien à embarquer.

    serveur = LocalServer(fenetre)
    port = serveur.start(8765, jeton)
    serveur.stop()
"""
from __future__ import annotations

import json
import secrets
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from PySide6.QtCore import QObject, Qt, Signal

from .protocol import INVALID_REQUEST, PROTOCOL_VERSIONS, Server, ToolError, error
from .tools import ToolSet

HOST = '127.0.0.1'
PATH = '/mcp'
DEFAULT_PORT = 8765
#: réglages : le serveur est lancé avec la fenêtre ; son port ; son jeton (fait une fois, gardé)
KEY_ON, KEY_PORT, KEY_TOKEN = 'agent/serveur', 'agent/port', 'agent/jeton'
#: une demande plus grosse est refusée ; un outil attend l'interface tant de secondes avant de renoncer
MAX_BODY = 8 << 20
WAIT_S = 60.0


def token_of(settings) -> str:
    """Le jeton du serveur local dans ces réglages ; fait (au hasard) et retenu la première fois."""
    tok = str(settings.value(KEY_TOKEN, '') or '').strip()
    if len(tok) < 16:
        tok = secrets.token_urlsafe(24)
        settings.setValue(KEY_TOKEN, tok)
    return tok


def port_of(settings) -> int:
    try:
        port = int(settings.value(KEY_PORT, DEFAULT_PORT) or DEFAULT_PORT)
    except (TypeError, ValueError):
        port = DEFAULT_PORT
    return port if 1024 <= port <= 65535 else DEFAULT_PORT


class UiBridge(QObject):
    """Exécute une fonction dans le fil de l'interface (celui où le pont est créé) pour un autre fil, qui attend son
    résultat."""
    asked = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._home = threading.current_thread()
        self.closed = False
        self.asked.connect(self._do, Qt.ConnectionType.QueuedConnection)

    def _do(self, job) -> None:
        job()

    @staticmethod
    def busy() -> str:
        """'' si un outil peut toucher au dessin maintenant ; sinon pourquoi pas. Une fenêtre modale, une commande
        en cours (barre de progression, menu ouvert : une boucle d'événements dans la boucle) ou un bouton de souris
        enfoncé (glisser en cours) : l'outil s'exécuterait AU MILIEU de la commande de l'utilisateur."""
        from PySide6.QtCore import QThread
        from PySide6.QtGui import QGuiApplication
        from PySide6.QtWidgets import QApplication
        if QApplication.activeModalWidget() is not None:
            return 'a dialog is open in VectorDrive: the user must close it first'
        if QThread.currentThread().loopLevel() > 1:
            return 'VectorDrive is in the middle of a command: try again in a moment'
        if QGuiApplication.mouseButtons() != Qt.MouseButton.NoButton:
            return 'the user is dragging something in VectorDrive: try again in a moment'
        return ''

    def run(self, fn):
        if threading.current_thread() is self._home:
            return fn()
        if self.closed:
            raise ToolError('VectorDrive is closing')
        done, lock, box = threading.Event(), threading.Lock(), {'state': 'waiting'}

        def job():
            with lock:
                if box['state'] != 'waiting':            # l'appelant a renoncé : ne rien changer après coup
                    return
                box['state'] = 'running'
            try:
                if self.closed:
                    raise ToolError('VectorDrive is closing')
                why = self.busy()
                if why:
                    raise ToolError(why)
                box['value'] = fn()
            except BaseException as ex:                  # noqa: BLE001 — rendue à l'appelant, dans son fil
                box['error'] = ex
            finally:
                done.set()
        self.asked.emit(job)
        if not done.wait(WAIT_S):
            with lock:
                if box['state'] == 'waiting':
                    box['state'] = 'given up'
                    raise ToolError('VectorDrive is busy and did not answer in time; nothing was changed')
            done.wait()                                  # commencé : attendre sa fin
        if 'error' in box:
            raise box['error']
        return box['value']


class _Http(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False      # Windows : sinon deux fenêtres prendraient le même port sans le savoir

    def server_bind(self):
        exclusive = getattr(socket, 'SO_EXCLUSIVEADDRUSE', None)
        if exclusive is not None:
            self.socket.setsockopt(socket.SOL_SOCKET, exclusive, 1)
        super().server_bind()


class _Handler(BaseHTTPRequestHandler):
    server_version = 'VectorDrive-MCP'
    sys_version = ''
    protocol_version = 'HTTP/1.1'
    timeout = 120                    # un client muet ne garde pas un fil pour toujours

    def log_message(self, *_args) -> None:               # rien sur la sortie d'erreur
        pass

    def _send(self, code: int, body: str | None = None, headers: tuple = ()) -> None:
        data = body.encode('utf-8') if body else b''
        if code >= 400:
            self.close_connection = True                 # le corps de la demande n'est peut-être pas lu
        self.send_response(code)
        for k, v in headers:
            self.send_header(k, v)
        if data:
            self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        if data and self.command != 'HEAD':
            self.wfile.write(data)

    def _refuse(self, code: int, message: str, headers: tuple = ()) -> None:
        self._send(code, json.dumps(error(None, INVALID_REQUEST, message)), headers)

    def _body(self) -> bytes | None:
        """Le corps de la demande, lu avant toute réponse (un refus envoyé sur un corps non lu coupe la connexion
        avant que le client ait lu le refus) ; None : longueur absente ou trop grande, refus déjà envoyé."""
        raw = self.headers.get('Content-Length')
        if raw is None and self.command != 'POST':
            return b''
        try:
            size = int(raw or '')
        except ValueError:
            self._refuse(411, 'Content-Length is required')
            return None
        if not 0 <= size <= MAX_BODY:
            self._refuse(413, 'request too large')
            return None
        return self.rfile.read(size) if size else b''

    def _guard(self) -> bool:
        owner = self.server.owner
        if owner._http is not self.server:               # serveur arrêté : une connexion gardée ouverte ne sert plus
            self._refuse(503, 'this server is stopped')
            return False
        if (self.headers.get('Host') or '').strip().lower() not in owner.hosts():
            self._refuse(403, 'this server only answers on this machine (Host)')
            return False
        origin = self.headers.get('Origin')
        if origin is not None and origin.strip().lower() not in ['http://' + h for h in owner.hosts()]:
            self._refuse(403, 'requests from a web page are refused (Origin)')   # une page web : jamais
            return False
        if self.path.split('?', 1)[0].rstrip('/') != PATH:
            self._refuse(404, 'the MCP endpoint is ' + PATH)
            return False
        given = (self.headers.get('Authorization') or '').strip().encode('utf-8', 'replace')
        if not secrets.compare_digest(given, ('Bearer ' + owner.token).encode('utf-8')) or not owner.token:
            self._refuse(401, 'missing or wrong token (Authorization: Bearer ...)', (('WWW-Authenticate', 'Bearer'),))
            return False
        return True

    def do_POST(self) -> None:                           # noqa: N802 — nom imposé par http.server
        body = self._body()
        if body is None or not self._guard():
            return
        version = self.headers.get('MCP-Protocol-Version')
        if version is not None and version.strip() not in PROTOCOL_VERSIONS:
            self._refuse(400, 'unsupported MCP-Protocol-Version; supported: ' + ', '.join(PROTOCOL_VERSIONS))
            return
        if not body:
            self._refuse(400, 'empty request')
            return
        text = body.decode('utf-8', 'replace')
        out = self.server.owner.mcp.handle_text(text)    # les outils passent un à un par le fil de l'interface
        if out is None:
            self._send(202)                              # notification : reçue, rien à répondre
        else:
            self._send(200, out)

    def _no_stream(self) -> None:
        if self._body() is not None and self._guard():
            self._send(405, None, (('Allow', 'POST'),))

    do_GET = do_DELETE = do_PUT = do_OPTIONS = do_HEAD = _no_stream   # noqa: N815


class LocalServer:
    """Le serveur MCP local d'une fenêtre : `start(port, jeton)` → le port servi (OSError : port pris), `stop()`."""

    def __init__(self, win, version: str | None = None):
        if version is None:
            from .. import __version__ as version
        self.win = win
        self.bridge = UiBridge(win)
        self.tools = ToolSet(win, run=self.bridge.run)
        self.mcp = Server(self.tools, version)
        self.token = ''
        self._http = None
        self._thread = None

    @property
    def running(self) -> bool:
        return self._http is not None

    @property
    def port(self) -> int:
        return self._http.server_address[1] if self._http is not None else 0

    @property
    def url(self) -> str:
        return f'http://{HOST}:{self.port}{PATH}' if self.running else ''

    def hosts(self) -> tuple:
        return (f'{HOST}:{self.port}', f'localhost:{self.port}')

    def start(self, port: int = DEFAULT_PORT, token: str | None = None) -> int:
        """Sert sur 127.0.0.1:`port` (0 : un port libre) avec ce jeton (sans : un neuf). Rend le port."""
        self.stop()
        http = _Http((HOST, int(port)), _Handler)        # OSError : port déjà pris
        http.owner = self
        self.token = token or secrets.token_urlsafe(24)
        self.bridge.closed = False
        self._http = http
        self._thread = threading.Thread(target=http.serve_forever, kwargs={'poll_interval': 0.2},
                                        name='vectordrive-mcp', daemon=True)
        self._thread.start()
        return self.port

    def stop(self) -> None:
        http, thread = self._http, self._thread
        self._http = self._thread = None
        if http is None:
            return
        self.bridge.closed = True                        # un outil en attente renonce au lieu de toucher au dessin
        http.shutdown()
        http.server_close()
        if thread is not None:
            thread.join(2.0)
