"""Machines de la FAO : chaque fraiseuse, chaque laser, avec le post-processeur qui lui convient le mieux.

Le cœur n'en connaît aucune : les plugins les déclarent (`Api.add_machine`). Une machine nomme :

* `posts` — les clés de post-processeur qui la pilotent, de la meilleure à la moins bonne. Ce sont des motifs à la
  `fnmatch`, comparés sans tenir compte de la casse ni du sens des barres : « gcode », ou « mah:*/Haas/* » pour la
  fiche machine d'un dossier ;
* `doubles` — les clés qui font double emploi avec elle (anciennes fiches, autres post-processeurs de la même
  machine) : elles ne sont plus proposées.

La liste des post-processeurs (`choices`) montre alors chaque machine une fois, sous son nom, puis les
post-processeurs qui ne sont à aucune machine. Une machine dont aucun post-processeur n'est disponible reste dans
le ruban, « à configurer ». Sans machine déclarée, rien ne change : la liste est celle des post-processeurs.
"""
from __future__ import annotations

import fnmatch

KINDS = ('fraiseuse', 'laser')


def all_machines(kind: str | None = None) -> list:
    """Les machines déclarées, dans l'ordre où elles l'ont été ; `kind` : 'fraiseuse' ou 'laser' seulement."""
    from ..plugins import REGISTRY
    return [m for m in getattr(REGISTRY, 'machines', []) if kind is None or m.kind == kind]


def by_key(key: str):
    return next((m for m in all_machines() if m.key == key), None)


def _norm(s) -> str:
    return str(s or '').replace('\\', '/').lower()


def _direct(key: str, pattern: str) -> bool:
    return bool(key) and bool(pattern) and fnmatch.fnmatchcase(_norm(key), _norm(pattern))


def _family(key: str) -> str:
    from . import post
    try:
        fam = post.family(key)
    except Exception:                                    # clé d'un plugin absent
        return ''
    return fam if fam and fam != key else ''


def resolve(spec, available) -> str:
    """La clé du post-processeur à employer pour la machine, parmi les clés `available` : la première que trouve un
    motif de `posts`, pris dans l'ordre. '' : aucune (machine à configurer)."""
    keys = list(available)
    for pattern in getattr(spec, 'posts', ()) or ():
        for k in keys:
            if _direct(k, pattern):
                return k
    return ''


def of_post(key: str):
    """La machine d'une clé de post-processeur : celle dont `posts` ou `doubles` la reconnaît — par la clé d'abord,
    sinon par sa famille (une fiche « mah:…Datron.MAH » est de la famille « datron »). None : aucune."""
    if not key:
        return None
    for probe in (key, _family(key)):
        if not probe:
            continue
        for m in all_machines():
            if any(_direct(probe, p) for p in tuple(m.posts) + tuple(m.doubles)):
                return m
    return None


def kind_of(key: str) -> str:
    """'fraiseuse' ou 'laser' : le genre de la machine d'une clé de post-processeur ; '' si aucune ne la reconnaît."""
    m = of_post(key)
    return m.kind if m is not None else ''


def choices(available: dict) -> list:
    """Ce qu'on propose pour les post-processeurs `available` ({clé: libellé}) : [(clé, libellé, machine ou None)].
    Chaque machine qui a un post-processeur, une fois, sous son nom ; puis les post-processeurs d'aucune machine.
    Sans machine déclarée : la liste telle quelle."""
    ms = all_machines()
    if not ms:
        return [(k, label, None) for k, label in available.items()]
    out = []
    for m in ms:
        k = resolve(m, available)
        if k:
            out.append((k, m.label, m))
    out += [(k, label, None) for k, label in available.items() if of_post(k) is None]
    return out


def label_of(key: str, available: dict | None = None) -> str:
    """Nom à montrer pour une clé de post-processeur : celui de sa machine, sinon son libellé, sinon ''."""
    m = of_post(key)
    if m is not None:
        return m.label
    return str((available or {}).get(key, ''))
