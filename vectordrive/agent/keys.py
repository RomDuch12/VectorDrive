"""Les clés d'API de l'assistant IA (`agent.chat`) : gardées dans le gestionnaire d'identifiants de Windows (chiffrées
pour la session de l'utilisateur, jamais dans les réglages ni dans un fichier de VectorDrive), une par fournisseur.

- Ailleurs que sous Windows, ou si le gestionnaire refuse : retenues le temps de la session seulement.
- Sans clé retenue : celle de la variable d'environnement du fournisseur (ANTHROPIC_API_KEY…), si elle existe.
- Les essais (`VECTORDRIVE_KEYS_MEMORY=1`, posée par `tests`) ne touchent jamais le gestionnaire du poste.

    keys.save('anthropic', cle)
    keys.load('anthropic')      # '' si aucune
    keys.forget('anthropic')
"""
from __future__ import annotations

import os
import sys

TARGET = 'VectorDrive/assistant/{0}'
_memory: dict = {}


def _windows() -> bool:
    return sys.platform == 'win32' and os.environ.get('VECTORDRIVE_KEYS_MEMORY', '') not in ('1', 'true')


def _cred():
    """Les fonctions du gestionnaire d'identifiants (advapi32), par ctypes."""
    import ctypes
    from ctypes import wintypes

    class FILETIME(ctypes.Structure):
        _fields_ = [('dwLowDateTime', wintypes.DWORD), ('dwHighDateTime', wintypes.DWORD)]

    class CREDENTIAL(ctypes.Structure):
        _fields_ = [('Flags', wintypes.DWORD), ('Type', wintypes.DWORD), ('TargetName', wintypes.LPWSTR),
                    ('Comment', wintypes.LPWSTR), ('LastWritten', FILETIME),
                    ('CredentialBlobSize', wintypes.DWORD), ('CredentialBlob', ctypes.POINTER(ctypes.c_ubyte)),
                    ('Persist', wintypes.DWORD), ('AttributeCount', wintypes.DWORD),
                    ('Attributes', ctypes.c_void_p), ('TargetAlias', wintypes.LPWSTR),
                    ('UserName', wintypes.LPWSTR)]

    adv = ctypes.WinDLL('advapi32', use_last_error=True)
    adv.CredReadW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                              ctypes.POINTER(ctypes.POINTER(CREDENTIAL))]
    adv.CredReadW.restype = wintypes.BOOL
    adv.CredWriteW.argtypes = [ctypes.POINTER(CREDENTIAL), wintypes.DWORD]
    adv.CredWriteW.restype = wintypes.BOOL
    adv.CredDeleteW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
    adv.CredDeleteW.restype = wintypes.BOOL
    adv.CredFree.argtypes = [ctypes.c_void_p]
    adv.CredFree.restype = None
    return ctypes, CREDENTIAL, adv


CRED_TYPE_GENERIC = 1
CRED_PERSIST_LOCAL_MACHINE = 2


def save(provider: str, key: str) -> bool:
    """Retient la clé ; rend True si elle est gardée dans le gestionnaire de Windows (False : pour la session)."""
    key = (key or '').strip()
    _memory[provider] = key
    if not key or not _windows():
        return False
    try:
        ctypes, CREDENTIAL, adv = _cred()
        blob = key.encode('utf-16-le')
        buf = (ctypes.c_ubyte * len(blob)).from_buffer_copy(blob)
        c = CREDENTIAL()
        c.Type = CRED_TYPE_GENERIC
        c.TargetName = TARGET.format(provider)
        c.Comment = 'VectorDrive'
        c.CredentialBlobSize = len(blob)
        c.CredentialBlob = ctypes.cast(buf, ctypes.POINTER(ctypes.c_ubyte))
        c.Persist = CRED_PERSIST_LOCAL_MACHINE
        c.UserName = provider
        return bool(adv.CredWriteW(ctypes.byref(c), 0))
    except (OSError, AttributeError, ValueError):
        return False


def _read(provider: str) -> str:
    try:
        ctypes, CREDENTIAL, adv = _cred()
        p = ctypes.POINTER(CREDENTIAL)()
        if not adv.CredReadW(TARGET.format(provider), CRED_TYPE_GENERIC, 0, ctypes.byref(p)):
            return ''
        try:
            n = p.contents.CredentialBlobSize
            raw = ctypes.string_at(p.contents.CredentialBlob, n) if n else b''
        finally:
            adv.CredFree(p)
        return raw.decode('utf-16-le', 'replace').strip()
    except (OSError, AttributeError, ValueError):
        return ''


def stored(provider: str) -> bool:
    """Une clé retenue par VectorDrive (pas seulement celle d'une variable d'environnement)."""
    if _memory.get(provider):
        return True
    return bool(_windows() and _read(provider))


def load(provider: str) -> str:
    """La clé du fournisseur : retenue, sinon celle de sa variable d'environnement ; '' si aucune."""
    if _memory.get(provider):
        return _memory[provider]
    key = _read(provider) if _windows() else ''
    if key:
        _memory[provider] = key
        return key
    from .chat import PROVIDERS
    return os.environ.get(PROVIDERS[provider][3], '').strip() if provider in PROVIDERS else ''


def forget(provider: str) -> None:
    """Oublie la clé retenue (celle d'une variable d'environnement reste)."""
    _memory.pop(provider, None)
    if _windows():
        try:
            _ctypes, _c, adv = _cred()
            adv.CredDeleteW(TARGET.format(provider), CRED_TYPE_GENERIC, 0)
        except (OSError, AttributeError):
            pass
