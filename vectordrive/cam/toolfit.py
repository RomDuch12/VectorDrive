"""L'outil passe-t-il partout ? Pour les formes fermées qu'une opération
usine : la part de surface que l'outil n'atteint pas (ouverture de la
région par le rayon de coupe) et le plus gros diamètre qui passe partout
(à une tolérance près) — une aide au choix de l'outil, avant le calcul."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Fit:
    area: float = 0.0               # surface des formes (mm²)
    unreached: float = 0.0          # surface que l'outil n'atteint pas (mm²)
    fit_diameter: float = 0.0       # plus gros Ø qui laisse moins de `limit` de la surface
    parts: int = 0                  # formes fermées

    @property
    def fraction(self) -> float:
        return self.unreached / self.area if self.area > 0 else 0.0


def unreached(reg, radius: float) -> float:
    """Surface de `reg` que n'atteint pas un outil de rayon `radius` (ce qui
    reste hors de l'ouverture morphologique)."""
    if radius <= 0 or reg.is_empty:
        return 0.0
    opened = reg.buffer(-radius, quad_segs=8).buffer(radius, quad_segs=8)
    return max(0.0, reg.difference(opened).area)


def largest_fit(reg, d_max: float, limit: float = 0.005, steps: int = 14) -> float:
    """Plus gros diamètre (≤ `d_max`) qui laisse au plus `limit` de la surface
    hors d'atteinte (dichotomie)."""
    area = reg.area
    if area <= 0 or d_max <= 0:
        return 0.0
    if unreached(reg, d_max / 2) <= limit * area:
        return d_max
    lo, hi = 0.0, d_max / 2
    for _ in range(steps):
        mid = (lo + hi) / 2
        if unreached(reg, mid) <= limit * area:
            lo = mid
        else:
            hi = mid
    return round(2 * lo, 3)


def check(doc, op, tool, tolerance: float = 0.01, limit: float = 0.005) -> Fit:
    """L'outil `tool` sur les formes de l'opération `op` (rayon de coupe à la
    profondeur de l'opération pour un outil conique)."""
    from . import strategies as S
    geoms = [g for it in S.source_items(doc, op) if (g := S.item_geometry(it))]
    reg = S.region(geoms, tolerance)
    if reg.is_empty:
        return Fit()
    r = S.cut_radius(op, tool) if tool is not None else 0.0
    parts = len(getattr(reg, 'geoms', [reg]))
    return Fit(area=reg.area, unreached=unreached(reg, r), fit_diameter=largest_fit(reg, max(2 * r, 0.1) * 4, limit),
               parts=parts)


def advise(doc, op, candidates, prefs=None, tolerance: float = 0.01, limit: float = 0.005):
    """Outil conseillé pour l'opération : parmi `candidates` adaptés à sa
    stratégie (outils proposés par opération), le plus gros qui atteint
    tous les détails (à `limit` près de la surface). Rend (outil ou None,
    plus gros Ø qui passe)."""
    from . import strategies as S
    from . import toolprefs
    geoms = [g for it in S.source_items(doc, op) if (g := S.item_geometry(it))]
    reg = S.region(geoms, tolerance)
    tools = [t for t in candidates if toolprefs.suits(t, op.kind, prefs)] or list(candidates)
    if reg.is_empty or not tools:
        return None, 0.0
    radius = {id(t): S.cut_radius(op, t) for t in tools}
    fit_d = largest_fit(reg, 2 * max(radius.values()), limit)
    area = reg.area
    for t in sorted(tools, key=lambda t: -radius[id(t)]):
        r = radius[id(t)]
        if 2 * r <= fit_d + 1e-6 and unreached(reg, r) <= limit * area:
            return t, fit_d
    return None, fit_d
