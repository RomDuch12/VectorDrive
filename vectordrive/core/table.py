"""Tableau (comme TABLE des logiciels de DAO) : grille de cellules et
leurs textes, pour les plaques signalétiques (caractéristiques d'une
machine, repères, nomenclatures).

Les contenus s'écrivent une ligne par rangée, les cellules séparées par
« ; » (ou une tabulation) ; une cellule vide reste vide. Largeurs de
colonnes égales ou données (« 30 50 20 »), hauteur de rangée, cadre
extérieur, traits intérieurs, alignement des textes, marge dans la
cellule. Le texte d'une cellule trop longue se resserre (longueur maximale).
"""
from __future__ import annotations

from dataclasses import dataclass

from .geom import Affine, Path, polyline, rect

ALIGNS = (('left', 'À gauche'), ('center', 'Centré'), ('right', 'À droite'))


@dataclass
class TableSpec:
    content: str = 'Désignation;Valeur\nTension;230 V\nPuissance;1,5 kW'
    widths: str = ''                # largeurs des colonnes (mm), vide : égales
    width: float = 80.0             # largeur totale si les colonnes sont égales
    row_height: float = 8.0
    text_height: float = 3.5
    padding: float = 1.5            # marge dans la cellule (mm)
    align: str = 'left'
    frame: bool = True
    inner: bool = True
    font: str = 'Arial'


def rows_of(content: str) -> list[list[str]]:
    lines = content.replace('\\n', '\n').split('\n')
    return [[c.strip() for c in (ln.split('\t') if '\t' in ln else ln.split(';'))] for ln in lines if ln.strip()]


def column_widths(spec: TableSpec, ncols: int) -> list[float]:
    try:
        ws = [float(v) for v in spec.widths.replace(',', '.').split()]
    except ValueError:
        ws = []
    ws = [w for w in ws if w > 0]
    if len(ws) >= ncols:
        return ws[:ncols]
    rest = max(0.0, spec.width - sum(ws)) / max(1, ncols - len(ws)) if ws else spec.width / max(1, ncols)
    return ws + [rest] * (ncols - len(ws))


def build(spec: TableSpec, origin=(0.0, 0.0)):
    """(Path des traits, [(texte, x, y de la ligne de base, alignement,
    longueur maximale)]) ; `origin` : coin haut-gauche du tableau."""
    rows = rows_of(spec.content)
    if not rows:
        return Path(), []
    ncols = max(len(r) for r in rows)
    ws = column_widths(spec, ncols)
    W, H = sum(ws), spec.row_height * len(rows)
    x0, ytop = origin
    lines = []
    if spec.frame:
        lines.append(rect(x0, ytop - H, W, H))
    if spec.inner:
        for k in range(1, len(rows)):
            y = ytop - k * spec.row_height
            lines.append(polyline([(x0, y), (x0 + W, y)]))
        x = x0
        for w in ws[:-1]:
            x += w
            lines.append(polyline([(x, ytop), (x, ytop - H)]))
    texts = []
    for i, r in enumerate(rows):
        yb = ytop - (i + 0.5) * spec.row_height - spec.text_height / 2
        x = x0
        for j in range(ncols):
            t = r[j] if j < len(r) else ''
            w = ws[j]
            if t:
                xa = {'left': x + spec.padding, 'right': x + w - spec.padding}.get(spec.align, x + w / 2)
                texts.append((t, xa, yb, spec.align, max(0.5, w - 2 * spec.padding)))
            x += w
    return Path(lines), texts
