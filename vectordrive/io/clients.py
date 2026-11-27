"""Carnet de clients du BAT : un nom et un logo par client, gardés dans un dossier.

Le dossier contient `clients.json` et un sous-dossier `logos` où chaque logo est **copié** (de tout format que
VectorDrive lit : image ou dessin) — le carnet ne dépend plus de l'endroit d'où le logo venait, et un dossier
partagé sert à tous les postes. Son emplacement : la variable `VECTORDRIVE_CLIENTS`, sinon le réglage `bat/clients`
(F10 › BAT), sinon `clients` dans les données de VectorDrive. Ce sont des données du poste : jamais dans le dessin.
Une reprise d'ancienne version, une mise à jour et l'import d'une configuration le fusionnent (`merge`, demande du
27/11 : « maj garder le carnet client ») : rien d'ici n'est jamais écrasé.

    {"version": 1, "clients": [{"nom": "…", "logo": "logos/….svg"}]}
"""
from __future__ import annotations

import filecmp
import json
import os
import pathlib
import re
import shutil
from typing import NamedTuple

FILE = 'clients.json'
LOGOS = 'logos'
ENV = 'VECTORDRIVE_CLIENTS'
SETTING = 'bat/clients'
#: suffixe d'un fichier en cours de copie (`merge`) : il ne prend sa place qu'une fois complet
PART = '.vd_copie'


def folder(settings=None) -> pathlib.Path:
    """Dossier du carnet (pas créé ici)."""
    forced = os.environ.get(ENV)
    if forced:
        return pathlib.Path(forced)
    chosen = str(settings.value(SETTING, '') or '').strip().strip('"') if settings is not None else ''
    if chosen:
        return pathlib.Path(chosen)
    from ..portable import data_dir
    return data_dir() / 'clients'


def load(where) -> list[dict]:
    """Les clients du carnet, par nom ; un carnet absent ou illisible : aucun."""
    try:
        data = json.loads((pathlib.Path(where) / FILE).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return []
    items = data.get('clients') if isinstance(data, dict) else None
    out = [c for c in (items or []) if isinstance(c, dict) and str(c.get('nom') or '').strip()]
    return sorted(out, key=lambda c: str(c['nom']).lower())


def _save(where, clients: list[dict]) -> None:
    d = pathlib.Path(where)
    d.mkdir(parents=True, exist_ok=True)
    tmp = d / (FILE + '.tmp')
    tmp.write_text(json.dumps({'version': 1, 'clients': clients}, ensure_ascii=False, indent=1), encoding='utf-8')
    tmp.replace(d / FILE)


def find(where, name: str) -> dict | None:
    key = str(name or '').strip().lower()
    return next((c for c in load(where) if str(c['nom']).strip().lower() == key), None)


def logo_path(where, client: dict | None) -> str:
    """Chemin du logo du client dans le carnet ; '' s'il n'en a pas ou que le fichier manque."""
    rel = str((client or {}).get('logo') or '')
    p = pathlib.Path(where) / rel if rel else None
    return str(p) if p is not None and p.is_file() else ''


def _slug(name: str) -> str:
    s = re.sub(r'[^0-9A-Za-zÀ-ÿ]+', '_', str(name)).strip('_')
    return s[:60] or 'client'


def _same_file(a: pathlib.Path, b: pathlib.Path) -> bool:
    try:
        return a.resolve() == b.resolve()
    except OSError:
        return False


def add(where, name: str, logo: str = '', **more) -> dict:
    """Ajoute le client, ou le met à jour (même nom, sans tenir compte de la casse). `logo` : un fichier, copié dans
    le carnet sous le nom du client ; vide : le logo déjà gardé reste. `more` : autres données du client."""
    name = str(name or '').strip()
    if not name:
        raise ValueError('client sans nom')
    d = pathlib.Path(where)
    clients = load(d)
    cur = next((c for c in clients if str(c['nom']).strip().lower() == name.lower()), None)
    if cur is None:
        cur = {'nom': name}
        clients.append(cur)
    cur['nom'] = name
    cur.update({k: v for k, v in more.items() if v not in (None, '')})
    src = pathlib.Path(logo) if logo else None
    if src is not None and src.is_file():
        (d / LOGOS).mkdir(parents=True, exist_ok=True)
        dst = d / LOGOS / (_slug(name) + src.suffix.lower())
        if not _same_file(src, dst):
            shutil.copyfile(src, dst)
        old = d / str(cur.get('logo') or '') if cur.get('logo') else None
        if old is not None and old.is_file() and not _same_file(old, dst):
            old.unlink()                                 # l'ancien logo du client (autre format)
        cur['logo'] = f'{LOGOS}/{dst.name}'
    _save(d, sorted(clients, key=lambda c: str(c['nom']).lower()))
    return cur


def remove(where, name: str) -> bool:
    """Retire le client et son logo du carnet. Rend False s'il n'y était pas."""
    d = pathlib.Path(where)
    clients = load(d)
    key = str(name or '').strip().lower()
    gone = [c for c in clients if str(c['nom']).strip().lower() == key]
    if not gone:
        return False
    for c in gone:
        p = d / str(c.get('logo') or '') if c.get('logo') else None
        if p is not None and p.is_file() and _same_file(p.parent, d / LOGOS):
            p.unlink()
    _save(d, [c for c in clients if c not in gone])
    return True


# --- fusion de deux carnets (demande du 27/11 : « maj garder le carnet client ») ------------------------------------
class Merged(NamedTuple):
    """Une fusion (`merge`) : `added`, les noms des clients ajoutés ; `logos`, combien d'entre eux avec leur logo ;
    `kept`, les clients déjà là, gardés tels quels ; `replaced`, la copie de secours (« fichier → copie ») ;
    `failed`, « chemin : raison »."""
    added: list
    logos: int
    kept: int
    replaced: list
    failed: list


def _safe_rel(rel: str) -> bool:
    """Le chemin d'un logo écrit dans un carnet, lu comme texte seulement (aucun accès au disque ni au réseau) : relatif
    au carnet — ni absolu, ni lecteur, ni chemin réseau, ni « .. », ni barre inverse."""
    if not rel or '\\' in rel or ':' in rel or rel.startswith('/'):
        return False
    parts = pathlib.PurePosixPath(rel).parts
    return bool(parts) and '..' not in parts


def _inside(base: pathlib.Path, p: pathlib.Path) -> bool:
    """`p` reste dans `base`, chemins résolus (ni lien, ni jonction ne le font sortir)."""
    try:
        b = os.path.realpath(base)
        return os.path.commonpath([b, os.path.realpath(p)]) == b
    except ValueError:                                   # autre lecteur
        return False


def _raw(where) -> list | None:
    """Les clients tels qu'écrits dans `clients.json` (rien d'écarté ni de trié) : [] sans carnet ; None : illisible
    (jamais réécrit alors)."""
    f = pathlib.Path(where) / FILE
    if not f.is_file():
        return []
    try:
        data = json.loads(f.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    items = data.get('clients', []) if isinstance(data, dict) else None
    return list(items) if isinstance(items, list) else None


def _put(src: pathlib.Path, dst: pathlib.Path) -> None:
    """`src` copié en `dst` sous un nom provisoire, vérifié (taille, source inchangée pendant la copie), puis mis en
    place d'un coup."""
    from ..i18n import tr
    st = src.stat()
    part = dst.with_name(dst.name + PART)
    try:
        shutil.copy2(src, part)
        if part.stat().st_size != st.st_size:
            raise OSError(tr('copie incomplète'))
        after = src.stat()
        if (after.st_size, after.st_mtime_ns) != (st.st_size, st.st_mtime_ns):
            raise OSError(tr('modifié pendant la copie'))
        os.replace(part, dst)
    except BaseException:
        part.unlink(missing_ok=True)
        raise


def _copy_logo(src: pathlib.Path, d: pathlib.Path, used: set) -> str:
    """Le logo `src` copié dans `d/logos` sous un nom libre (le sien, sinon « nom_2 », « nom_3 »…) — jamais un fichier
    déjà là écrasé. Un fichier identique qu'aucun client n'emploie (`used` : les logos employés, en minuscules ;
    laissé par une fusion coupée) est repris tel quel : ni doublon, ni orphelin. Rend son chemin dans le carnet."""
    folder = d / LOGOS
    folder.mkdir(parents=True, exist_ok=True)
    stem, ext = src.stem, src.suffix.lower()
    dst, i = folder / (stem + ext), 1
    while True:
        rel = f'{LOGOS}/{dst.name}'
        if not dst.exists() and not dst.with_name(dst.name + PART).exists():
            break
        if rel.lower() not in used and dst.is_file() and filecmp.cmp(src, dst, shallow=False):
            return rel                                   # laissé par une fusion coupée : repris
        i += 1
        dst = folder / f'{stem}_{i}{ext}'
    _put(src, dst)
    return rel


def _copy_as_is(s: pathlib.Path, d: pathlib.Path) -> None:
    """Un carnet illisible recopié tel quel dans `d`, qui n'en a pas : ses logos absents d'ici, puis son
    `clients.json` (jamais un fichier déjà là écrasé)."""
    logos = s / LOGOS
    if logos.is_dir() and not os.path.islink(logos):
        for f in sorted(logos.iterdir()):
            dst = d / LOGOS / f.name
            if f.is_file() and not os.path.islink(f) and not f.name.lower().endswith(PART) and not dst.exists():
                dst.parent.mkdir(parents=True, exist_ok=True)
                _put(f, dst)
    d.mkdir(parents=True, exist_ok=True)
    _put(s / FILE, d / FILE)


def merge(src, dst, backup=None) -> Merged:
    """Les clients du carnet `src` ajoutés au carnet `dst` : un client déjà là (même nom, sans tenir compte de la
    casse) est gardé tel quel ; un client absent est ajouté avec toutes ses données et son logo, copié dans
    `dst/logos` sous un nom libre — aucun fichier déjà là n'est écrasé. `dst` sans carnet : celui de `src` y est
    copié. Avant de réécrire un `clients.json` déjà là, `backup(chemin)` (s'il est donné) en fait la copie de secours
    et rend le texte « fichier → copie » ; si elle échoue, rien n'est écrit. Un carnet d'ici illisible n'est jamais
    réécrit ; un carnet `src` illisible est recopié tel quel s'il n'y en a pas ici, sinon laissé — dit dans les deux
    cas, comme ses clients sans nom. Le chemin d'un logo est contrôlé comme texte avant tout accès au disque
    (`_safe_rel`). Les logos sont copiés avant le `clients.json` : une fusion coupée puis refaite reprend ceux qu'elle
    avait déjà copiés (`_copy_logo`). Rend `Merged`."""
    from ..i18n import tr
    s, d = pathlib.Path(src), pathlib.Path(dst)
    if _same_file(s, d):
        return Merged([], 0, 0, [], [])
    raw = _raw(s)
    if raw is None:
        if (d / FILE).exists():
            return Merged([], 0, 0, [], [f'{s / FILE} : ' + tr('carnet de clients illisible : non fusionné, gardé '
                                                               'dans son dossier')])
        try:
            _copy_as_is(s, d)
        except OSError as ex:
            return Merged([], 0, 0, [], [f'{s / FILE} : {ex.strerror or ex}'])
        return Merged([], 0, 0, [], [f'{s / FILE} : ' + tr('carnet de clients illisible : recopié tel quel, à '
                                                           'vérifier')])
    failed = []
    theirs = load(s)
    nameless = len(raw) - len(theirs)
    if nameless:
        failed.append(f'{s / FILE} : ' + tr('{0} client(s) sans nom laissé(s)').format(nameless))
    mine = _raw(d)
    if mine is None:
        return Merged([], 0, 0, [], failed + [f'{d / FILE} : ' + tr('carnet de clients illisible : rien n’y est '
                                                                    'ajouté')])
    have = {str(c.get('nom') or '').strip().lower() for c in mine if isinstance(c, dict)}
    new = []
    for c in theirs:
        key = str(c['nom']).strip().lower()
        if key not in have:
            have.add(key)
            new.append(c)
    kept = len(theirs) - len(new)
    if not new:
        return Merged([], 0, kept, [], failed)
    replaced = []
    if (d / FILE).is_file() and backup is not None:
        try:
            replaced.append(backup(d / FILE))
        except OSError as ex:
            return Merged([], 0, kept, [], failed + [f'{d / FILE} : {ex.strerror or ex}'])
    used = {str(c.get('logo') or '').lower() for c in mine if isinstance(c, dict) and c.get('logo')}
    added, logos = [], 0
    for c in new:
        c = dict(c)
        rel = str(c.pop('logo', '') or '')
        if rel and not _safe_rel(rel):                   # lu comme texte : jamais un accès réseau (UNC)
            failed.append(f'{c["nom"]} : ' + tr('logo refusé (chemin hors du carnet) : client repris sans lui'))
        elif rel:
            logo = s / rel
            if _inside(s, logo) and logo.is_file():
                try:
                    c['logo'] = _copy_logo(logo, d, used)
                    used.add(c['logo'].lower())
                    logos += 1
                except OSError as ex:
                    failed.append(f'{logo} : {ex.strerror or ex}')
            else:
                failed.append(f'{logo} : ' + tr('logo introuvable : client repris sans lui'))
        added.append(c)
    try:
        _save(d, mine + added)
    except OSError as ex:
        return Merged([], 0, kept, replaced, failed + [f'{d / FILE} : {ex.strerror or ex}'])
    return Merged([str(c['nom']) for c in added], logos, kept, replaced, failed)
