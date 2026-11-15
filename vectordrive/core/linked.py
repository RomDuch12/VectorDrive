"""Copies liées : modifier la forme de l'original modifie aussi ses copies.

Une copie porte `extra['link'] = {'master': id}`. Chacune garde sa place : déplacer,
tourner ou agrandir une copie reste libre, et déplacer l'original ne déplace pas ses
copies. Si la forme de l'original change (nœuds, texte, mise à l'échelle…), la copie
prend la nouvelle forme, avec sa propre transformation. Modifier les nœuds d'une copie
la détache. Une copie reste un objet ordinaire dans les fichiers.

Le `cache` (id de l'original → état connu de l'original et de ses copies) n'est pas
enregistré : il suffit à connaître la transformation de chaque copie au moment où
l'original change. L'original comme les copies peuvent être dans un groupe.
"""
from __future__ import annotations

from typing import NamedTuple

import numpy as np

from .document import Group, Item, Shape, Text
from .geom import Affine, Conic, Cubic

KEY = 'link'
#: écart admis (mm) entre une copie et l'original transformé ; au-delà, elle a été modifiée pour elle-même
FIT_TOL = 0.01
OFFSET = 5.0


def _segment_points(s) -> list:
    if isinstance(s, Cubic):
        return [s.p0, s.p1, s.p2, s.p3]
    if isinstance(s, Conic):
        return [s.p0, s.p1, s.p2]
    return [s.p0, s.p1]


def _collect(it: Item, out: list) -> None:
    if isinstance(it, Group):
        for ch in it.children:
            _collect(ch, out)
        return
    path = it.path if isinstance(it, Shape) else None
    if isinstance(it, Text):
        if it.outline is None:
            from .text import outline_for
            it.outline = outline_for(it)
        path = it.outline
    if path:
        for c in path.contours:
            for s in c.segments:
                out.extend(_segment_points(s))
    elif not isinstance(it, Text):
        box = it.bbox()                                  # une image : sa boîte
        if box:
            out.extend(((box[0], box[1]), (box[2], box[1]), (box[2], box[3]), (box[0], box[3])))


def points(it: Item) -> np.ndarray:
    """Les points qui décrivent la forme (une transformation les transforme tous, dans le même ordre)."""
    out: list = []
    _collect(it, out)
    return np.asarray(out, dtype=float).reshape(-1, 2)


def _words(it: Item) -> tuple:
    if isinstance(it, Group):
        return tuple(_words(ch) for ch in it.children)
    if isinstance(it, Text):
        return it.text, it.font
    return ()


def _affine(m: np.ndarray) -> Affine:
    return Affine(float(m[0, 0]), float(m[1, 0]), float(m[0, 1]), float(m[1, 1]), float(m[0, 2]), float(m[1, 2]))


def fit(src: np.ndarray, dst: np.ndarray) -> Affine | None:
    """La transformation qui mène `src` sur `dst` ; None si elle n'existe pas (formes différentes)."""
    if len(src) != len(dst) or len(src) == 0:
        return None
    A = np.column_stack((src, np.ones(len(src))))
    if np.linalg.matrix_rank(A - np.array([*src.mean(axis=0), 0.0]), tol=1e-9) >= 3:
        sol, *_ = np.linalg.lstsq(A, dst, rcond=None)
        m = sol.T
    else:                                                # points alignés : rotation, échelle et décalage suffisent
        a, b = src[0], src[np.argmax(np.linalg.norm(src - src[0], axis=1))]
        p, q = dst[0], dst[np.argmax(np.linalg.norm(src - src[0], axis=1))]
        u, v = complex(*(b - a)), complex(*(q - p))
        if abs(u) < 1e-12:
            k = 1 + 0j
        else:
            k = v / u
        linear = np.array([[k.real, -k.imag], [k.imag, k.real]])
        m = np.column_stack((linear, p - linear @ a))
    got = src @ m[:2, :2].T + m[:2, 2]
    if float(np.abs(got - dst).max()) > FIT_TOL:
        return None
    return _affine(m)


def _center(it: Item) -> tuple[float, float] | None:
    box = it.bbox()
    return ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2) if box else None


def make(it: Item, dx: float = OFFSET, dy: float = -OFFSET) -> Item:
    """Une copie liée à `it` (à son original si `it` est déjà une copie), décalée."""
    master = (it.extra.get(KEY) or {}).get('master') or it.id
    c = it.clone().transformed(Affine.translation(dx, dy))
    c.extra = {**c.extra, KEY: {'master': master}}
    return c


def is_copy(it: Item) -> bool:
    return bool(isinstance(it.extra.get(KEY), dict) and it.extra[KEY].get('master'))


def unlink(it: Item) -> bool:
    """La copie redevient un objet indépendant. Rend False si elle n'était pas liée."""
    if not is_copy(it):
        return False
    it.extra = {k: v for k, v in it.extra.items() if k != KEY}
    return True


class _State(NamedTuple):
    shape: np.ndarray
    words: tuple
    tool: int
    copies: dict


def _scan(doc) -> tuple[dict, dict]:
    """Les copies de chaque original, avec la liste qui les contient, et tous les objets par id."""
    linked: dict[str, list] = {}
    every: dict[str, Item] = {}

    def walk(items):
        for it in items:
            every[it.id] = it
            if is_copy(it):                              # l'intérieur d'une copie suit la copie
                linked.setdefault(it.extra[KEY]['master'], []).append((items, it))
            elif isinstance(it, Group):
                walk(it.children)

    for L in doc.layers:
        walk(L.items)
    return linked, every


def _state(m: Item, pairs: list) -> _State:
    return _State(points(m), _words(m), int(m.tool), {c.id: points(c) for _i, c in pairs})


def prime(doc, cache: dict) -> None:
    """Apprend l'état des originaux pas encore connus : à faire avant une modification."""
    linked, every = _scan(doc)
    if not linked:
        cache.clear()
        return
    for mid, pairs in linked.items():
        if mid not in cache and mid in every:
            cache[mid] = _state(every[mid], pairs)


def _same(a: np.ndarray, b: np.ndarray) -> bool:
    return len(a) == len(b) and (len(a) == 0 or float(np.abs(a - b).max()) <= 1e-9)


def _only_moved(old: _State, shape: np.ndarray, words: tuple) -> bool:
    if old.words != words or len(old.shape) != len(shape):
        return False
    if len(shape) == 0:
        return True
    return float(np.ptp(shape - old.shape, axis=0).max()) <= 1e-9


def _replace(items: list, old: Item, new: Item) -> None:
    for i, it in enumerate(items):
        if it is old:
            items[i] = new
            return


def _follow_tool(c: Item, old_tool: int, tool: int) -> None:
    if old_tool != tool and c.tool == old_tool:
        c.tool = tool


def sync(doc, cache: dict) -> list[tuple[Item, Item]]:
    """Reporte sur les copies ce qui a changé dans leur original. Rend les (ancien, nouveau) objets remplacés."""
    linked, every = _scan(doc)
    if not linked:
        cache.clear()
        return []
    changed: list[tuple[Item, Item]] = []
    for mid, pairs in linked.items():
        m = every.get(mid)
        if m is None:                                    # l'original a été supprimé : les copies sont libres
            for _i, c in pairs:
                unlink(c)
            cache.pop(mid, None)
            continue
        now = _state(m, pairs)
        old = cache.get(mid)
        if old is None:
            cache[mid] = now
            continue
        moved = _only_moved(old, now.shape, now.words)
        reshaped = not moved and fit(old.shape, now.shape) is None     # nœuds, texte : pas une transformation
        kept: dict = {}
        for items, c in pairs:
            pts = now.copies[c.id]
            was = old.copies.get(c.id)
            alike = fit(now.shape, pts) is not None if was is not None and not _same(was, pts) else None
            if alike is False:                           # la copie a changé, et plus de la même forme que l'original
                new = None if moved else _rebuilt(m, c, old, now, reshaped)
            elif moved or alike:                         # rien à reporter, ou la même opération sur les deux
                _follow_tool(c, old.tool, now.tool)
                kept[c.id] = pts
                continue
            else:
                new = _rebuilt(m, c, old, now, reshaped)
            if new is None:                              # modifiée pour elle-même : elle se détache
                unlink(c)
                continue
            _replace(items, c, new)
            changed.append((c, new))
            kept[c.id] = points(new)
        cache[mid] = now._replace(copies=kept)
    return changed


def _rebuilt(m: Item, c: Item, old: _State, now: _State, reshaped: bool) -> Item | None:
    a = fit(old.shape, points(c))
    if a is None:
        return None
    new = m.clone().transformed(a)
    if not reshaped:                                     # l'original a tourné ou changé d'échelle : autour du centre de la copie
        here, there = _center(c), _center(new)
        if here and there:
            new = new.transformed(Affine.translation(here[0] - there[0], here[1] - there[1]))
    new.id = c.id
    new.name = c.name
    new.visible, new.locked = c.visible, c.locked
    new.tool = now.tool if c.tool == old.tool else c.tool
    new.extra = {**{k: v for k, v in new.extra.items() if k != KEY}, KEY: dict(c.extra[KEY])}
    return new
