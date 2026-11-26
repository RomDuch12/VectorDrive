"""Dossiers de travail (demande du 25/11 : « Parametres : … ajouter section dossiers de travail (tous les dossiers par
défaut des imports exports sauve fichier sauve programme avec un champ par défaut ou le dernier usé) »).

Pour chaque usage des fenêtres de fichiers (Ouvrir, Enregistrer, Importer, Exporter, programmes…), F10 › Dossiers de
travail propose « Le dernier utilisé » (d'office : le comportement d'avant) ou « Toujours ce dossier ». Toutes les
fenêtres prennent leur dossier de départ par `start_folder` : le dossier fixé s'il est là, sinon le dernier utilisé,
sinon ce que la fenêtre proposait avant. Le dernier utilisé reste retenu même quand un dossier est fixé (ses clés
« dossier/… » ne changent pas). Un dossier fixé hors d'atteinte (lecteur réseau débranché, clé USB retirée) ne bloque
rien : un partage réseau est regardé dans un fil à part, `REMOTE_WAIT` secondes au plus la première fois ; sans
réponse, ce partage est laissé de côté `DOWN_FOR` secondes (ou jusqu'à ce que le fil, même tardif, réponde).

    from .workdirs import start_folder
    start = start_folder(self.settings, 'exporter', str(pathlib.Path.home()))

Chaque départ rendu est noté (`issue`) : `pathmemory` reconnaît ainsi une fenêtre qui a sa ligne et garde le chemin
rendu (dossier fixé ou dernier utilisé) ; « Autres fenêtres de fichiers » ne vaut que pour les fenêtres sans ligne.

Un plugin ajoute sa ligne (ses dossiers clients…) : `api.add_work_folder('clients', 'Dossiers clients')`, ou
`workdirs.register(...)` ; il lit ensuite son dossier de départ par `start_folder(settings, 'clients', …)`, ou le
dossier fixé seul par `fixed_folder(settings, 'clients')` ('' : aucun, ou hors d'atteinte).
"""
from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass

#: réglages : « dossiers_travail/<usage> » (LAST ou FIXED) et « dossiers_travail/<usage>_chemin » (le dossier fixé)
PREFIX = 'dossiers_travail/'
LAST = 'dernier'
FIXED = 'fixe'
#: attente au plus (s) pour savoir si un dossier fixé sur un partage réseau répond, dans le fil de l'interface
REMOTE_WAIT = 0.8
#: un partage qui n'a pas répondu à temps n'est plus regardé pendant ce temps (s), pour aucun de ses dossiers : pas
#: une attente à chaque fenêtre
DOWN_FOR = 30.0


@dataclass(frozen=True)
class Usage:
    key: str                                             # « ouvrir », « exporter »… (celui de `_last_dir`)
    label: str                                           # libellé de la ligne (français, passé à tr())
    last_key: str = ''                                   # réglage du dernier dossier utilisé ; vide : dossier/<key>
    tip: str = ''                                        # bulle de la ligne (français, passé à tr())

    @property
    def last(self) -> str:
        return self.last_key or f'dossier/{self.key}'


#: les lignes de la section, dans l'ordre (les plugins en ajoutent par `register`)
USAGES: dict[str, Usage] = {}


def _add(key: str, label: str, tip: str = '', last_key: str = '') -> None:
    USAGES[key] = Usage(key, label, last_key, tip)


_add('ouvrir', 'Ouvrir un dessin', 'Ouvrir (Ctrl+O) : le navigateur de VectorDrive ou la boîte du système ; aussi '
     '« Comparer à »')
_add('enregistrer', 'Enregistrer un dessin', 'Enregistrer sous, et le premier enregistrement d’un dessin neuf')
_add('importer', 'Importer', 'Importer un fichier dans le dessin ouvert')
_add('exporter', 'Exporter', 'Exporter dans tous les formats (image comprise)')
_add('programmes', 'Enregistrer un programme', 'Post-traiter : programmes machine, programmes des panneaux, parcours '
     'TypeEdit. D’office (« Le dernier utilisé ») : le dossier du dessin d’abord, sinon le dernier dossier d’un '
     'programme ; « Toujours ce dossier » passe devant le dossier du dessin',
     'dossier/programmes')
_add('bat', 'BAT (PDF)', 'Enregistrer le BAT en PDF')
_add('image', 'Images lues', 'Vectoriser une image, image ajoutée au rapport d’imbrication')
_add('modele3d', 'Modèles 3D lus', 'Importer un volume, projection locale, relief d’un modèle 3D')
_add('stl', 'Export STL', 'Exporter en STL')
_add('police', 'Polices SVG', 'Lire une police SVG (éditeur de polices)')
_add('iso', 'Programmes ISO lus', 'Lire un programme ISO')
_add('parametres', 'Paramètres exportés et importés', 'Exporter et importer les paramètres (.vdparam)')
_add('import_outils', 'Outils importés dans Mes outils', 'Bibliothèque d’outils : importer des outils, un dossier '
     'd’outils', 'dossier/import_outils')
_add('autres', 'Autres fenêtres de fichiers', 'Toutes les autres (thèmes, raccourcis, ruban, STEP…) quand elles ne '
     'proposent rien de précis : le dernier dossier choisi dans chacune, ou toujours ce dossier',
     'chemins_retenus/dernier')                          # pathmemory.LAST


def register(key: str, label: str, *, last_key: str = '', tip: str = '') -> Usage:
    """Une ligne de plus dans F10 › Dossiers de travail (plugins : `api.add_work_folder`) ; `last_key` : le réglage
    où l'appelant retient son dernier dossier (vide : « dossier/<key> », celui de `MainWindow._remember_dir`).
    Une clé déjà connue est remplacée. Rend l'usage."""
    u = Usage(str(key), str(label), str(last_key or ''), str(tip or ''))
    USAGES[u.key] = u
    from . import options
    options.add_workdir(u)
    return u


def mode_key(usage: str) -> str:
    return PREFIX + usage


def path_key(usage: str) -> str:
    return PREFIX + usage + '_chemin'


def last_key(usage: str) -> str:
    u = USAGES.get(usage)
    return u.last if u is not None else f'dossier/{usage}'


def clean_path(text) -> tuple[str, bool]:
    """(chemin, valable) d'un dossier écrit : espaces et guillemets (copier le chemin de l'Explorateur) retirés,
    « ~ » et « %VARIABLE% » développés (une variable inconnue reste telle quelle : un « % » du nom d'un dossier) ;
    valable : vide, ou chemin complet (D:\\…, \\\\serveur\\…). Sans disque."""
    p = str(text or '').strip().strip('"').strip("'").strip()
    if not p:
        return '', True
    p = os.path.expanduser(os.path.expandvars(p))
    if p.startswith('~') or not os.path.isabs(p):
        return p, False
    return os.path.normpath(p), True


def fixed_setting(settings, usage: str) -> str:
    """Le dossier fixé pour cet usage (sans regarder le disque) ; '' : le dernier utilisé (ou un chemin écrit qui
    n'est pas un dossier complet)."""
    if str(settings.value(mode_key(usage), LAST) or LAST) != FIXED:
        return ''
    p, ok = clean_path(settings.value(path_key(usage), '') or '')
    return p if ok else ''


def last_used(settings, usage: str) -> str:
    """Le dernier dossier utilisé pour cet usage ('' : aucun encore)."""
    return str(settings.value(last_key(usage), '') or '')


def _remote(path) -> bool:
    from .pathmemory import _remote as remote
    return remote(path)


_isdir = os.path.isdir
#: partages qui n'ont pas répondu à temps : racine du partage (`share_root`) → instant ; lu et écrit sous `_LOCK` (le
#: fil la retire s'il finit par trouver le dossier)
_DOWN: dict = {}
_LOCK = threading.Lock()


def share_root(path) -> str:
    """La racine d'un chemin réseau, en minuscules : « \\\\serveur\\partage » ou la lettre du lecteur (« t: »)."""
    drive = os.path.splitdrive(str(path))[0]
    return os.path.normcase(drive or str(path)).rstrip('\\/')


def _is_down(k: str) -> bool:
    with _LOCK:
        since = _DOWN.get(k)
        return since is not None and time.monotonic() - since < DOWN_FOR


def reachable(path, wait: float | None = None) -> bool:
    """Le dossier est-il là ? Un dossier local : regardé tout de suite. Un partage réseau : dans un fil à part,
    `wait` (sinon `REMOTE_WAIT`) secondes au plus — un serveur hors d'atteinte ne gèle pas l'interface ; sans
    réponse à temps, tout ce partage est tenu pour absent `DOWN_FOR` secondes, sauf si le fil finit par répondre."""
    p = str(path or '')
    if not p:
        return False
    if not _remote(p):
        try:
            return bool(_isdir(p))
        except (OSError, ValueError):
            return False
    k = share_root(p)
    if _is_down(k):
        return False
    box: list = []

    def look():
        try:
            ok = bool(_isdir(p))
        except Exception:                                # noqa: BLE001 — partage illisible : absent
            ok = False
        with _LOCK:
            box.append(ok)
            if ok:
                _DOWN.pop(k, None)                       # réponse, même tardive : le partage de nouveau regardé
    t = threading.Thread(target=look, name='dossier-de-travail', daemon=True)
    t.start()
    t.join(REMOTE_WAIT if wait is None else wait)
    with _LOCK:
        if box:
            return box[0]
        _DOWN[k] = time.monotonic()                      # pas de réponse à temps : le partage absent pour l'instant
    return False                                         # (un dossier qui manque sur un partage qui répond : non)


def fixed_folder(settings, usage: str) -> str:
    """Le dossier fixé pour cet usage s'il est là ; '' : pas de dossier fixé, ou hors d'atteinte."""
    p = fixed_setting(settings, usage)
    return p if p and reachable(p) else ''


#: départs rendus aux fenêtres qui ont leur ligne : chemin (normcase) → (usage, comment, instant) ; `pathmemory` les
#: reconnaît (puis les oublie) ; ceux qu'aucune boîte n'a pris s'effacent après `ISSUED_FOR` secondes
_ISSUED: dict = {}
ISSUED_FOR = 60.0
ISSUED_HOW = (FIXED, LAST, 'repli')


def issue(usage: str, path, how: str) -> None:
    """Note le départ `path` rendu pour l'usage : `how` FIXED (le dossier fixé), LAST (le dernier utilisé, ou un
    dossier choisi par la fenêtre elle-même : celui du dessin) ou 'repli' (l'ancien défaut). Un usage sans ligne
    (fiche, rapport, symbole…) n'est pas noté : « Autres fenêtres de fichiers » s'y applique."""
    k = _norm(path) if path else ''
    if not k or usage not in USAGES:
        return
    now = time.monotonic()
    with _LOCK:
        for old in [x for x, v in _ISSUED.items() if now - v[2] > ISSUED_FOR]:
            del _ISSUED[old]
        _ISSUED[k] = (usage, how, now, str(path))


def issued(path) -> tuple:
    """(usage, comment, dossier noté) du départ noté pour ce chemin (ou le dossier de ce fichier), oublié aussitôt ;
    (None, '', '') : une fenêtre sans ligne."""
    if not path:
        return None, '', ''
    keys = (_norm(path), _norm(os.path.dirname(str(path).rstrip('\\/'))))
    now = time.monotonic()
    with _LOCK:
        for k in keys:
            v = _ISSUED.pop(k, None)
            if v is not None and now - v[2] <= ISSUED_FOR:
                return v[0], v[1], v[3]
    return None, '', ''


def start_folder(settings, usage: str, fallback: str = '') -> str:
    """Le dossier de départ d'une fenêtre de fichiers : le dossier fixé s'il est là, sinon le dernier utilisé, sinon
    `fallback` (ce que la fenêtre proposait avant). Noté (`issue`) pour `pathmemory`."""
    for path, how in ((fixed_folder(settings, usage), FIXED), (last_used(settings, usage), LAST),
                      (str(fallback or ''), 'repli')):
        if path:
            issue(usage, path, how)
            return path
    return ''


def _norm(path) -> str:
    try:
        return os.path.normcase(os.path.normpath(str(path))).rstrip('\\/')
    except (TypeError, ValueError):
        return ''


def is_fixed_path(settings, path, usage: str) -> bool:
    """Le chemin proposé est-il le dossier fixé de cette ligne (ou un fichier dedans) ? Sans disque."""
    f = fixed_setting(settings, usage)
    if not (f and path):
        return False
    return _norm(f) in (_norm(path), _norm(os.path.dirname(str(path).rstrip('\\/'))))
