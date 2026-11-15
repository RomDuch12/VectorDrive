"""Sens des contours pour l'affichage (Ctrl+7) et l'export : contour fermé
anti-horaire en vert, horaire en bleu, contour ouvert en noir."""
from __future__ import annotations

from .geom import Path

#: couleur de chaque sens
COLORS = {'ccw': '#2b9348', 'cw': '#1c6dd0', 'open': '#000000'}


def orientation(contour) -> str:
    """'ccw' (anti-horaire), 'cw' (horaire) ou 'open' (contour ouvert, ou sans aire)."""
    if not contour.closed:
        return 'open'
    a = contour.signed_area()
    return 'open' if abs(a) < 1e-12 else ('ccw' if a > 0 else 'cw')


def split(path: Path) -> dict[str, Path]:
    """Contours d'un tracé rangés par sens : {'ccw' | 'cw' | 'open': Path}."""
    out: dict[str, list] = {}
    for c in path.contours:
        if c.segments:
            out.setdefault(orientation(c), []).append(c)
    return {k: Path(v) for k, v in out.items()}
