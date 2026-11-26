"""Sens des contours pour l'affichage (Ctrl+7) et l'export : contour fermé
horaire en vert, anti-horaire en bleu (foncés sur fond clair, clairs sur fond
sombre), contour ouvert en noir (blanc sur fond sombre).

Le sens se juge dans le repère du dessin, Y vers le haut comme à l'écran :
aire signée (`Contour.signed_area`) positive = anti-horaire, négative = horaire."""
from __future__ import annotations

from .geom import Path

#: couleur de chaque sens sur fond clair (thème clair, export) : vert et bleu foncés, noir
COLORS = {'cw': '#1a7f37', 'ccw': '#1a47b0', 'open': '#000000'}
#: couleur de chaque sens sur fond sombre (thème sombre) : vert et bleu clairs, blanc
COLORS_DARK = {'cw': '#7ee08f', 'ccw': '#7ab8ff', 'open': '#ffffff'}


def colors(dark: bool = False) -> dict[str, str]:
    """Couleurs des sens ('cw', 'ccw', 'open') pour un fond sombre (`dark`) ou clair."""
    return COLORS_DARK if dark else COLORS


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
