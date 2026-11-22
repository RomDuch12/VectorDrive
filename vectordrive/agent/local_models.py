"""Les modèles Mistral en local, par Ollama (demande du 22/11 : « les meilleurs moteurs Mistral locaux pour GPU 4 Go,
8 Go, 12 Go, 16 Go dans les possibilités de l'assistant »).

Le modèle tourne sur ce poste (ou un poste du réseau de l'atelier) : sans clé, sans abonnement, sans crédit, et le
dessin ne sort pas de l'atelier. Ollama (https://ollama.com, licence MIT) sert le modèle ; VectorDrive lui parle par
son API (`/api/chat`, avec la taille du contexte : les outils de l'assistant en prennent ~7 000 jetons, plus que
les 4 096 d'office d'Ollama).

Un palier par mémoire de carte graphique (modèles quantifiés en 4 bits, tailles d'Ollama relevées le 22/11/2026) :

* 4 Go  : Ministral 3 3B (`ministral-3:3b`, 3,0 Go) — outils et images ;
* 8 Go  : Ministral 3 8B (`ministral-3:8b`, 6,0 Go) ;
* 12 Go : Ministral 3 14B (`ministral-3:14b`, 9,1 Go) ;
* 16 Go : Mistral Small 3.2 24B (`mistral-small3.2:24b`, 15 Go) — le plus capable ; juste sur 16 Go (une partie
  du contexte passe par la mémoire du poste).

Ministral 3 demande Ollama 0.13.1 ou plus récent. Rien ici ne télécharge ni n'installe de lui-même : « Télécharger
le modèle » ouvre une console `ollama pull` que l'utilisateur voit et peut fermer.
"""
from __future__ import annotations

import http.client
import ipaddress
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from urllib.parse import urlsplit

#: l'adresse d'Ollama sur ce poste
DEFAULT_URL = 'http://localhost:11434'
#: le contexte d'office (jetons) : consignes, outils (~7 000) et une discussion de quelques tours
DEFAULT_CONTEXT = 16384
KEY_URL = 'assistant/adresse_local'
KEY_CONTEXT = 'assistant/contexte_local'
#: les modèles vus chez Ollama à la dernière vérification (proposés dans le panneau)
KEY_SEEN = 'assistant/modeles_local'
DOWNLOAD_PAGE = 'https://ollama.com/download'
LOCAL_HOSTS = ('localhost', '127.0.0.1', '::1')


@dataclass(frozen=True)
class Tier:
    gpu_gb: int          # mémoire de la carte graphique visée
    model: str           # nom chez Ollama
    size_gb: float       # taille du modèle téléchargé (4 bits)
    label: str           # nom lisible
    note: str            # ce qu'il faut savoir


TIERS = (
    Tier(4, 'ministral-3:3b', 3.0, 'Ministral 3 3B', 'rapide ; outils et images ; demandes simples'),
    Tier(8, 'ministral-3:8b', 6.0, 'Ministral 3 8B', 'bon équilibre ; outils et images'),
    Tier(12, 'ministral-3:14b', 9.1, 'Ministral 3 14B', 'plus sûr sur les demandes en plusieurs étapes'),
    Tier(16, 'mistral-small3.2:24b', 15.0, 'Mistral Small 3.2 24B',
         'le plus capable ; juste sur 16 Go (une partie passe par la mémoire du poste, plus lent)'),
)
MODELS = tuple(t.model for t in TIERS)


def tier_of(model: str) -> Tier | None:
    m = (model or '').strip().lower()
    return next((t for t in TIERS if t.model == m), None)


def recommend(gpu_gb: float | None) -> Tier:
    """Le palier le plus capable qui tient dans `gpu_gb` (une carte de « 8 Go » en annonce un peu moins) ; sans
    carte connue ou sous 4 Go : le plus petit (il tourne alors sur le processeur, lentement)."""
    if not gpu_gb:
        return TIERS[0]
    fit = [t for t in TIERS if t.gpu_gb <= gpu_gb + 0.6]
    return fit[-1] if fit else TIERS[0]


# --- la carte graphique ------------------------------------------------------------------------------------------
_GPU_CLASS = r'SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}'


def _nvidia(run) -> list:
    try:
        out = run(['nvidia-smi', '--query-gpu=memory.total', '--format=csv,noheader,nounits'])
    except (OSError, subprocess.SubprocessError, ValueError):
        return []
    vals = []
    for line in (out or '').splitlines():
        try:
            vals.append(float(line.strip()) / 1024)
        except ValueError:
            pass
    return vals


def _registry(read) -> list:
    """La mémoire annoncée par les pilotes d'affichage (lecture seule du registre)."""
    vals = []
    for i in range(10):
        key = rf'{_GPU_CLASS}\{i:04d}'
        for name in ('HardwareInformation.qwMemorySize', 'HardwareInformation.MemorySize'):
            v = read(key, name)
            if isinstance(v, (bytes, bytearray)):
                v = int.from_bytes(bytes(v)[:8], 'little') if v else None
            if isinstance(v, int) and v > 0:
                vals.append(v / 1024 ** 3)
                break
    return vals


def _run(args) -> str:
    flags = 0x08000000 if sys.platform == 'win32' else 0          # CREATE_NO_WINDOW
    return subprocess.run(args, capture_output=True, text=True, timeout=5, creationflags=flags,
                          check=True).stdout


def _read_hklm(key: str, name: str):
    if sys.platform != 'win32':
        return None
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key) as k:
            return winreg.QueryValueEx(k, name)[0]
    except OSError:
        return None


def gpu_memory_gb(run=None, read=None) -> float | None:
    """La mémoire de la plus grande carte graphique, en Go (nvidia-smi, sinon le registre) ; None si inconnue."""
    vals = _nvidia(run or _run) or _registry(read or _read_hklm)
    return round(max(vals), 1) if vals else None


# --- Ollama --------------------------------------------------------------------------------------------------------
def base_url(url: str = '') -> str:
    """L'adresse du serveur, sans le chemin d'une API (on accepte celle qu'on colle : …/api/chat, …/v1/…)."""
    u = (url or '').strip().rstrip('/') or DEFAULT_URL
    for tail in ('/api/chat', '/v1/chat/completions', '/v1', '/api'):
        if u.lower().endswith(tail):
            u = u[: -len(tail)]
            break
    return u.rstrip('/')


def _ip(host: str):
    """L'adresse IP écrite dans `host` (IPv4, IPv6, IPv4 dans une IPv6), sinon None."""
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return None
    mapped = getattr(ip, 'ipv4_mapped', None)
    return mapped or ip


def address_ok(url: str) -> bool:
    """https vers n'importe quel serveur ; http vers ce poste ou le réseau de l'atelier seulement (adresse IP privée
    ou de bouclage, nom sans point ou en .local) — pas de clé à protéger, mais le dessin ne part pas en clair sur
    Internet. Une adresse écrite en nombre (« 134744072 », « 0x8080808 », que Windows résout) est refusée."""
    try:
        u = urlsplit(url)
        host = u.hostname
        u.port                                           # un port illisible : ValueError
    except ValueError:
        return False
    if not host or u.username or u.password or u.scheme not in ('http', 'https'):
        return False
    if u.scheme == 'https':
        return True
    ip = _ip(host)
    if ip is not None:
        return (ip.is_private or ip.is_loopback) and not ip.is_unspecified
    if re.fullmatch(r'0x[0-9a-f]+|[0-9][0-9a-fx.]*', host, re.I):
        return False                                     # une adresse IP écrite autrement
    return host in LOCAL_HOSTS or '.' not in host or host.endswith('.local')


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_a, **_k):
        return None


def _get(url: str, timeout: float) -> dict:
    """Sans le proxy du système (le serveur de l'atelier ne passe pas par un proxy d'entreprise), sans redirection."""
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
    with opener.open(url, timeout=timeout) as r:                   # noqa: S310 — adresse vérifiée
        got = json.loads(r.read().decode('utf-8'))
    if not isinstance(got, dict):
        raise ValueError('not an Ollama answer')
    return got


def status(url: str = '', timeout: float = 3.0, get=None) -> dict:
    """{'running', 'version', 'models' (noms), 'error'} : Ollama répond-il, et quels modèles a-t-il ?"""
    base = base_url(url)
    get = get or _get
    if not address_ok(base):
        return {'running': False, 'version': '', 'models': [], 'error': 'adresse refusée'}
    try:
        ver = str((get(base + '/api/version', timeout) or {}).get('version') or '')
        tags = get(base + '/api/tags', timeout) or {}
    except (OSError, ValueError, AttributeError, TypeError, http.client.HTTPException) as ex:
        return {'running': False, 'version': '', 'models': [], 'error': str(getattr(ex, 'reason', ex))}
    found = tags.get('models') if isinstance(tags, dict) else None
    models = sorted(str(m.get('name') or m.get('model') or '') for m in found or [] if isinstance(m, dict))
    return {'running': True, 'version': ver, 'models': [m for m in models if m], 'error': ''}


def has_model(models, model: str) -> bool:
    """`model` est-il parmi `models` (« mistral-small » vaut « mistral-small:latest ») ?"""
    want = (model or '').strip().lower()
    names = {m.lower() for m in models}
    return want in names or (':' not in want and f'{want}:latest' in names)


def version_ok(version: str, need=(0, 13, 1)) -> bool:
    """Ministral 3 demande Ollama 0.13.1 au moins."""
    try:
        got = tuple(int(x) for x in version.split('-')[0].split('.')[:3])
    except ValueError:
        return True                                      # une version de développement : on ne bloque pas
    return got >= need


def exe() -> str | None:
    """ollama.exe : dans le PATH, sinon là où son installateur le met."""
    found = shutil.which('ollama')
    if found:
        return found
    p = pathlib.Path(os.environ.get('LOCALAPPDATA') or pathlib.Path.home()) / 'Programs' / 'Ollama' / 'ollama.exe'
    return str(p) if p.is_file() else None


def start(popen=None) -> bool:
    """Démarre Ollama (son application, dans la zone de notification ; sinon `ollama serve` caché). Rend False si
    Ollama n'est pas installé ou ne se lance pas."""
    path = exe()
    if not path:
        return False
    popen = popen or subprocess.Popen
    app = pathlib.Path(path).with_name('ollama app.exe')
    flags = (0x08000000 | 0x00000200 | 0x01000000) if sys.platform == 'win32' else 0
    try:
        if app.is_file():
            popen([str(app)], creationflags=flags, close_fds=True)
        else:
            popen([path, 'serve'], creationflags=flags, close_fds=True)
    except OSError:
        if not flags:
            return False
        flags &= ~0x01000000                             # sortie du « job » refusée : lancé quand même
        try:
            popen([str(app)] if app.is_file() else [path, 'serve'], creationflags=flags, close_fds=True)
        except OSError:
            return False
    return True


def pull(model: str, popen=None) -> bool:
    """Ouvre une console qui télécharge `model` (`ollama pull`) : l'utilisateur voit l'avancement et peut la fermer.
    Rend False si Ollama n'est pas installé."""
    path = exe()
    if not path or not model.strip():
        return False
    popen = popen or subprocess.Popen
    if sys.platform == 'win32':
        popen(['cmd', '/k', path, 'pull', model.strip()], creationflags=0x00000010, close_fds=True)  # NEW_CONSOLE
    else:
        popen([path, 'pull', model.strip()], close_fds=True)
    return True


def table_text(gpu_gb: float | None = None) -> str:
    """Les paliers, lisibles (le recommandé marqué)."""
    best = recommend(gpu_gb) if gpu_gb else None
    lines = []
    for t in TIERS:
        mark = ' ◀' if best is not None and t == best else ''
        lines.append(f'{t.gpu_gb} Go : {t.label} ({t.model}, {t.size_gb:g} Go) — {t.note}{mark}')
    return '\n'.join(lines)
