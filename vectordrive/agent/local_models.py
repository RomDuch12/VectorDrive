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

Ministral 3 demande Ollama 0.13.1 ou plus récent. Rien ici ne télécharge ni n'installe de lui-même : l'interface le
demande, après accord de l'utilisateur pour l'installation (l'installateur officiel, signé par Ollama Inc.). Le
modèle se télécharge par l'API d'Ollama (`pull_stream`, avec l'avancement) ; `pull` (une console) reste pour qui la
préfère.
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


# --- installer Ollama, télécharger un modèle, le démarrer au besoin (demande du 22/11 après-midi : « vd desktop doit
# pouvoir gérer entièrement l'install de ollama, de son modèle et son utilisation ») ---------------------------------
#: l'installateur officiel d'Ollama pour Windows (Inno Setup ; pour le compte de l'utilisateur, sans droit
#: d'administrateur) ; ollama.com renvoie vers les versions publiées sur GitHub
INSTALLER_URL = 'https://ollama.com/download/OllamaSetup.exe'
#: les seuls serveurs d'où l'installateur peut venir (https, redirections comprises)
INSTALLER_HOSTS = ('ollama.com', 'github.com', 'githubusercontent.com')
#: l'éditeur exigé dans la signature Authenticode de l'installateur, avant de le lancer
SIGNER = 'O=Ollama Inc.'
#: la taille de l'installateur (Go, relevée le 22/11/2026), dite avant de le télécharger
INSTALLER_GB = 1.9
WINGET_ID = 'Ollama.Ollama'
#: le port d'Ollama sur ce poste (celui que son application ouvre)
DEFAULT_PORT = 11434
#: le démarrage automatique attend Ollama au plus tant de secondes
START_WAIT_S = 45
#: le téléchargement d'un modèle attend une nouvelle d'Ollama au plus tant de secondes (la vérification des parties
#: d'un gros modèle se tait plusieurs minutes)
PULL_TIMEOUT_S = 1800


class Cancelled(Exception):
    """L'utilisateur a annulé (téléchargement de l'installateur ou du modèle)."""


class SetupError(Exception):
    """L'installation, le démarrage ou le téléchargement n'a pas abouti. `reason` : download (téléchargement),
    source (serveur refusé), file (pas un programme), signature, installer (code de sortie), missing (introuvable
    après l'installation), address, model, pull (refus d'Ollama), down (Ollama ne répond pas), start (ne démarre
    pas), notinstalled, old (version trop ancienne) ; `detail` : ce qu'on en sait."""

    def __init__(self, reason: str, detail: str = ''):
        super().__init__(f'{reason}: {detail}' if detail else reason)
        self.reason, self.detail = reason, detail


def _system_exe(name: str) -> str:
    """Un programme de Windows par son chemin complet (jamais un homonyme du dossier courant ou de l'application)."""
    root = pathlib.Path(os.environ.get('SystemRoot') or r'C:\Windows') / 'System32'
    if name == 'powershell':
        return str(root / 'WindowsPowerShell' / 'v1.0' / 'powershell.exe')
    return str(root / f'{name}.exe')


def _int(v) -> int:
    try:
        return max(0, int(v))
    except (TypeError, ValueError):
        return 0


def _unlink(p) -> None:
    try:
        pathlib.Path(p).unlink()
    except OSError:
        pass


def on_this_machine(url: str = '') -> bool:
    """L'adresse est-elle celle d'Ollama sur ce poste (le seul que VectorDrive peut démarrer ou installer) ?"""
    try:
        u = urlsplit(base_url(url))
        host, port = (u.hostname or '').lower(), u.port
    except ValueError:
        return False
    ip = _ip(host)
    local = host in LOCAL_HOSTS or (ip is not None and ip.is_loopback)
    return local and port == DEFAULT_PORT                # http://localhost sans port : le port 80, pas Ollama


def _host_ok(url: str) -> bool:
    try:
        u = urlsplit(url)
        host = (u.hostname or '').lower()
    except ValueError:
        return False
    return u.scheme == 'https' and any(host == h or host.endswith('.' + h) for h in INSTALLER_HOSTS)


class _SafeRedirect(urllib.request.HTTPRedirectHandler):
    """Les redirections de l'installateur : en https, vers ollama.com ou GitHub seulement."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not _host_ok(newurl):
            raise SetupError('source', urlsplit(newurl).hostname or newurl[:80])
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def download_installer(folder, on_progress=None, cancel=None, opener=None) -> pathlib.Path:
    """Télécharge l'installateur officiel dans `folder` ; `on_progress(fait, total)` en octets ; `cancel` (Event)
    l'arrête (`Cancelled`, le fichier partiel retiré). Rend le chemin de OllamaSetup.exe."""
    folder = pathlib.Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    part = folder / 'OllamaSetup.exe.part'
    out = folder / 'OllamaSetup.exe'
    opener = opener or urllib.request.build_opener(_SafeRedirect())
    req = urllib.request.Request(INSTALLER_URL, headers={'User-Agent': 'VectorDrive'})
    try:
        with opener.open(req, timeout=60) as r:                    # noqa: S310 — adresse fixe, en https
            final = r.geturl() if hasattr(r, 'geturl') else INSTALLER_URL
            if not _host_ok(final):
                raise SetupError('source', urlsplit(final).hostname or '')
            total = _int(r.headers.get('Content-Length'))
            done = 0
            with open(part, 'wb') as f:
                while True:
                    if cancel is not None and cancel.is_set():
                        raise Cancelled()
                    chunk = r.read(1 << 20)
                    if not chunk:
                        break
                    f.write(chunk)
                    done += len(chunk)
                    if on_progress is not None:
                        on_progress(done, total)
        if cancel is not None and cancel.is_set():
            raise Cancelled()
        if total and done != total:
            raise SetupError('download', f'{done}/{total}')
        with open(part, 'rb') as f:
            if f.read(2) != b'MZ':
                raise SetupError('file')
        _unlink(out)
        part.replace(out)
        return out
    except (Cancelled, SetupError):
        _unlink(part)
        raise
    except (OSError, ValueError, http.client.HTTPException) as ex:
        _unlink(part)
        raise SetupError('download', str(getattr(ex, 'reason', ex))[:200]) from None


def signature(path, run=None) -> tuple:
    """(état, sujet) de la signature Authenticode de `path` (PowerShell `Get-AuthenticodeSignature`, le chemin passé
    par l'environnement, jamais dans la commande) ; ('', '') si illisible ou hors Windows. `run(path)` : essais."""
    if run is not None:
        out = run(path)
    elif sys.platform != 'win32':
        return '', ''
    else:
        script = ("[Console]::OutputEncoding = [Text.Encoding]::UTF8; "
                  "$s = Get-AuthenticodeSignature -LiteralPath $env:VECTORDRIVE_SIGNED_FILE; "
                  "'' + $s.Status + '|' + $s.SignerCertificate.Subject")
        try:
            out = subprocess.run([_system_exe('powershell'), '-NoProfile', '-NonInteractive', '-Command', script],
                                 capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=120,
                                 creationflags=0x08000000, env=dict(os.environ, VECTORDRIVE_SIGNED_FILE=str(path)),
                                 check=False).stdout
        except (OSError, subprocess.SubprocessError):
            return '', ''
    status_, _sep, subject = str(out or '').strip().partition('|')
    return status_.strip(), subject.strip()


def _fields(subject: str, key: str) -> list:
    """Les valeurs du champ `key` (O, CN…) d'un sujet de certificat, guillemets compris (« O="A, B" »)."""
    found = re.findall(r'(?:^|,)\s*([A-Za-z0-9.]+)=("(?:[^"]|"")*"|[^,]*)', subject or '')
    out = []
    for k, v in found:
        if k.upper() == key.upper():
            v = v.strip()
            if len(v) >= 2 and v[0] == v[-1] == '"':
                v = v[1:-1].replace('""', '"')
            out.append(v)
    return out


def trusted(path, run=None) -> bool:
    """La signature est-elle valide, et celle d'Ollama Inc. (un seul champ O=, exactement « Ollama Inc. ») ?"""
    status_, subject = signature(path, run)
    return status_ == 'Valid' and _fields(subject, 'O') == [SIGNER.split('=', 1)[1]]


def run_installer(path, popen=None):
    """Lance l'installateur, sans question (`/SILENT` : sa fenêtre montre l'avancement ; `/CLOSEAPPLICATIONS` :
    un Ollama en marche est fermé pour la mise à jour) ; rend le processus."""
    popen = popen or subprocess.Popen
    return popen([str(path), '/SILENT', '/NORESTART', '/SUPPRESSMSGBOXES', '/CLOSEAPPLICATIONS'], close_fds=True)


def install(folder, on_step=None, on_progress=None, cancel=None, opener=None, run=None, popen=None) -> str:
    """Installe Ollama : télécharge l'installateur officiel, vérifie sa signature (rien n'est lancé sinon), l'exécute
    et attend sa fin ; l'installateur est retiré ensuite. `on_step(clé)` : download, verify, install. Rend le chemin
    de ollama.exe ; `SetupError` ou `Cancelled` sinon."""
    step = on_step or (lambda _k: None)
    setup = pathlib.Path(folder) / 'OllamaSetup.exe'
    try:
        step('download')
        setup = download_installer(folder, on_progress, cancel, opener)
        step('verify')
        if not trusted(setup, run):
            raise SetupError('signature')
        step('install')                                  # dit d'abord : l'interface n'annonce plus « Annulé »
        if cancel is not None and cancel.is_set():
            raise Cancelled()
        try:
            code = run_installer(setup, popen).wait()
        except OSError as ex:
            raise SetupError('installer', str(ex)[:200]) from None
        if code:
            raise SetupError('installer', str(code))
    finally:
        _unlink(setup)
        try:
            pathlib.Path(folder).rmdir()                 # le dossier de ce travail, vide
        except OSError:
            pass
    path = exe()
    if not path:
        raise SetupError('missing')
    return path


def winget() -> str | None:
    """winget (le gestionnaire de paquets de Windows), s'il est là."""
    return shutil.which('winget') if sys.platform == 'win32' else None


def install_winget(popen=None) -> bool:
    """Installe Ollama par winget, dans une console que l'utilisateur voit (il y suit l'avancement et y accepte les
    conditions de la source) ; rend False sans winget."""
    path = winget()
    if not path:
        return False
    popen = popen or subprocess.Popen
    popen([_system_exe('cmd'), '/k', path, 'install', '--id', WINGET_ID, '-e', '--source', 'winget'],
          creationflags=0x00000010, close_fds=True)                  # CREATE_NEW_CONSOLE
    return True


def _error_of(raw: bytes) -> str:
    text = raw.decode('utf-8', 'replace').strip()
    try:
        got = json.loads(text)
    except ValueError:
        return text[:300]
    return str(got.get('error') or text)[:300] if isinstance(got, dict) else text[:300]


def pull_stream(model: str, url: str = '', on_progress=None, cancel=None, connect=None) -> None:
    """Télécharge `model` par l'API d'Ollama (`/api/pull`, en flux), sans console : `on_progress(étape, fait,
    total)` (octets, toutes les parties du modèle réunies) ; `cancel` (Event) l'arrête à la nouvelle suivante
    (`Cancelled` ; la connexion fermée, Ollama s'arrête et garde ce qui est déjà là pour reprendre). Sans proxy du
    système, comme la discussion. `SetupError` si Ollama refuse ou ne répond pas."""
    m = (model or '').strip()
    if not m:
        raise SetupError('model')
    base = base_url(url)
    if not address_ok(base):
        raise SetupError('address')
    if connect is None:
        u = urlsplit(base)
        cls = http.client.HTTPSConnection if u.scheme == 'https' else http.client.HTTPConnection
        conn = cls(u.hostname, u.port, timeout=PULL_TIMEOUT_S)
    else:
        conn = connect()
    path = (urlsplit(base).path or '').rstrip('/') + '/api/pull'
    stopped = lambda: cancel is not None and cancel.is_set()     # noqa: E731
    parts = {}
    try:
        conn.request('POST', path, body=json.dumps({'model': m, 'stream': True}).encode('utf-8'),
                     headers={'Content-Type': 'application/json', 'Accept': 'application/x-ndjson'})
        r = conn.getresponse()
        if r.status >= 400:
            raise SetupError('pull', _error_of(r.read(500)))
        while True:
            if stopped():
                raise Cancelled()
            line = r.readline()
            if not line:
                break
            try:
                d = json.loads(line)
            except ValueError:
                continue
            if not isinstance(d, dict):
                continue
            if d.get('error'):
                raise SetupError('pull', str(d['error'])[:300])
            step = str(d.get('status') or '')
            if d.get('digest') and _int(d.get('total')):
                parts[str(d['digest'])] = (min(_int(d.get('completed')), _int(d['total'])), _int(d['total']))
            if on_progress is not None:
                on_progress(step, sum(c for c, _t in parts.values()), sum(t for _c, t in parts.values()))
            if step == 'success':
                return
        if stopped():
            raise Cancelled()
        raise SetupError('pull', 'interrompu')
    except (Cancelled, SetupError):
        raise
    except (OSError, ValueError, http.client.HTTPException) as ex:
        if stopped():
            raise Cancelled() from None
        raise SetupError('down', str(ex)[:200]) from None
    finally:
        try:
            conn.close()
        except OSError:
            pass


def ensure_running(url: str = '', wait_s: float = START_WAIT_S, stopping=None, status_fn=None, start_fn=None,
                   sleep=None) -> bool:
    """Ollama en marche : déjà là, ou (sur ce poste, s'il est installé) démarré puis attendu, au plus `wait_s` s ;
    `stopping()` : l'utilisateur a arrêté. Rend False sans rien lancer pour un autre poste ou sans Ollama."""
    import time
    base = base_url(url)
    status_fn = status_fn or (lambda: status(base, timeout=1.5))
    sleep = sleep or time.sleep
    if status_fn()['running']:
        return True
    if not on_this_machine(base) or not exe():
        return False
    try:
        if not (start_fn or start)():
            return False
    except OSError:
        return False
    deadline = time.monotonic() + wait_s
    while time.monotonic() < deadline:
        if stopping is not None and stopping():
            return False
        sleep(0.5)
        if status_fn()['running']:
            return True
    return False


def down_reason(url: str = '') -> str:
    """Pourquoi Ollama ne répond pas : 'notinstalled' (sur ce poste, pas installé), 'start' (installé, ne démarre
    pas), 'down' (un autre poste)."""
    if not on_this_machine(url):
        return 'down'
    return 'start' if exe() else 'notinstalled'
