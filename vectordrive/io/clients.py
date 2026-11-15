"""Carnet de clients du BAT : un nom et un logo par client, gardés dans un dossier.

Le dossier contient `clients.json` et un sous-dossier `logos` où chaque logo est **copié** (de tout format que
VectorDrive lit : image ou dessin) — le carnet ne dépend plus de l'endroit d'où le logo venait, et un dossier
partagé sert à tous les postes. Son emplacement : la variable `VECTORDRIVE_CLIENTS`, sinon le réglage `bat/clients`
(F10 › BAT), sinon `clients` dans les données de VectorDrive. Ce sont des données du poste : jamais dans le dessin.

    {"version": 1, "clients": [{"nom": "…", "logo": "logos/….svg"}]}
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import shutil

FILE = 'clients.json'
LOGOS = 'logos'
ENV = 'VECTORDRIVE_CLIENTS'
SETTING = 'bat/clients'


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
