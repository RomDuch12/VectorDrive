"""Le protocole MCP (Model Context Protocol), côté serveur, pour les outils de VectorDrive : JSON-RPC 2.0, écrit ici
avec la seule bibliothèque standard (aucune dépendance à embarquer) — `initialize`, `ping`, `tools/list`,
`tools/call`. Le transport (HTTP local, entrée et sortie standard) est ailleurs : ce module ne fait que répondre à des
messages.

    serveur = Server(outils, '0.913.0')
    reponse = serveur.handle({'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list'})
"""
from __future__ import annotations

import json

#: versions du protocole comprises (la plus récente d'abord) ; une autre demandée : la plus récente est proposée
PROTOCOL_VERSIONS = ('2025-06-18', '2025-03-26', '2024-11-05')
SERVER_NAME = 'vectordrive'
PARSE_ERROR, INVALID_REQUEST, METHOD_NOT_FOUND, INVALID_PARAMS, INTERNAL_ERROR = -32700, -32600, -32601, -32602, -32603

INSTRUCTIONS = ('VectorDrive: 2D drawing and CAM for engraving. Units are millimetres; X grows to the right, Y grows '
                'upwards. Tools act on the drawing open in the running application; each change is one undo step '
                'for the user. Call get_document first, then list_objects to see what is there.')


class ToolError(Exception):
    """Un outil ne peut pas faire ce qui est demandé : dit au modèle (résultat `isError`), pas une erreur du
    protocole."""


def error(msg_id, code: int, message: str) -> dict:
    return {'jsonrpc': '2.0', 'id': msg_id, 'error': {'code': code, 'message': message}}


def result(msg_id, value) -> dict:
    return {'jsonrpc': '2.0', 'id': msg_id, 'result': value}


def text_content(value) -> dict:
    """Un contenu « texte » : `value` tel quel si c'est une chaîne, sinon en JSON."""
    return {'type': 'text', 'text': value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)}


class Server:
    """Répond aux messages MCP. `tools` : un objet qui a `specs()` → la liste des outils ({name, description,
    inputSchema}) et `call(name, arguments)` → une liste de contenus (ou lève `ToolError`, `KeyError` pour un outil
    inconnu)."""

    def __init__(self, tools, version: str = '0'):
        self.tools = tools
        self.version = str(version)
        self.initialized = False

    # --- un message ---------------------------------------------------------------------------------
    def handle(self, message):
        """Un message JSON-RPC déjà lu (dictionnaire), ou un lot (liste) : sa réponse — None pour une notification,
        une liste pour un lot."""
        if isinstance(message, list):
            if not message:
                return error(None, INVALID_REQUEST, 'empty batch')
            out = [r for r in (self.handle(m) for m in message) if r is not None]
            return out or None
        if not isinstance(message, dict) or message.get('jsonrpc') != '2.0':
            return error(message.get('id') if isinstance(message, dict) else None, INVALID_REQUEST, 'not JSON-RPC 2.0')
        method, msg_id = message.get('method'), message.get('id')
        if not isinstance(method, str):                  # une réponse du client (à rien que nous ayons demandé)
            return None if 'result' in message or 'error' in message else error(msg_id, INVALID_REQUEST, 'no method')
        params = message.get('params')
        if params is None:
            params = {}
        if 'id' not in message:                          # notification : jamais de réponse
            if method == 'notifications/initialized':
                self.initialized = True
            return None
        if not isinstance(params, dict):
            return error(msg_id, INVALID_PARAMS, 'params must be an object')
        try:
            return self._request(msg_id, method, params)
        except Exception as ex:                          # noqa: BLE001 — jamais une exception vers le transport
            return error(msg_id, INTERNAL_ERROR, f'{type(ex).__name__}: {ex}')

    def _request(self, msg_id, method: str, params: dict) -> dict:
        if method == 'initialize':
            wanted = params.get('protocolVersion')
            version = wanted if wanted in PROTOCOL_VERSIONS else PROTOCOL_VERSIONS[0]
            return result(msg_id, {
                'protocolVersion': version, 'capabilities': {'tools': {'listChanged': False}},
                'serverInfo': {'name': SERVER_NAME, 'title': 'VectorDrive', 'version': self.version},
                'instructions': INSTRUCTIONS})
        if method == 'ping':
            return result(msg_id, {})
        if method == 'tools/list':
            return result(msg_id, {'tools': list(self.tools.specs())})
        if method == 'tools/call':
            name, args = params.get('name'), params.get('arguments')
            if not isinstance(name, str) or (args is not None and not isinstance(args, dict)):
                return error(msg_id, INVALID_PARAMS, 'tools/call needs a name and an arguments object')
            try:
                content = self.tools.call(name, args or {})
            except KeyError:
                return error(msg_id, INVALID_PARAMS, f'Unknown tool: {name}')
            except ToolError as ex:
                return result(msg_id, {'content': [text_content(str(ex))], 'isError': True})
            except Exception as ex:                      # noqa: BLE001 — l'outil a échoué : dit au modèle
                return result(msg_id, {'content': [text_content(f'{type(ex).__name__}: {ex}')], 'isError': True})
            return result(msg_id, {'content': list(content), 'isError': False})
        return error(msg_id, METHOD_NOT_FOUND, f'Method not found: {method}')

    # --- du texte ---------------------------------------------------------------------------------------
    def handle_text(self, text: str) -> str | None:
        """Un message en JSON (texte) : sa réponse en JSON, ou None (notification)."""
        try:
            message = json.loads(text)
        except (ValueError, RecursionError):
            return json.dumps(error(None, PARSE_ERROR, 'invalid JSON'))
        out = self.handle(message)
        return None if out is None else json.dumps(out)     # en ASCII : un caractère invalide d'un texte ne casse rien
