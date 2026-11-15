"""Table de crénage de la police intégrée « VD Géo », calculée sur son dessin.

Pour chaque paire (lettre de gauche, caractère de droite) des classes de
crénage — diagonales, potences, lettres ouvertes à gauche ; rondes,
diagonales, ponctuation et voyelles accentuées à droite — on mesure le blanc
entre le profil droit de l'une et le profil gauche de l'autre, aux hauteurs
où toutes deux ont de l'encre (blanc limité à `DEPTH` au-delà de l'écart le
plus court), et on le ramène vers `TARGET`. Le crénage reste dans
[-`CAP`, 0] (-`CAP_PUNCT` devant la ponctuation) et ne rapproche jamais deux
traits à moins de `GAPMIN` (distance euclidienne : la gravure ne doit pas
souder deux lettres). Pas de crénage après un chiffre ni après une apostrophe
(« 7.5 », « l’été » restent lisibles).

Unités : hauteur des capitales = 1. À relancer après une retouche des
glyphes, puis recopier la sortie dans `_KERN` de `vectordrive/core/strokegeo.py` :

    python outils/vdgeo_crenage.py > crenage.txt
"""
import math
import pathlib
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from vectordrive.core import strokegeo as sg  # noqa: E402

LEFT = 'AFKLPRTVWXYΓΛfkrvwxy'
RIGHT = "ACGJOQTUVWXYacdegoqsuvwxyæœ'\"’‘”“.,-" + 'àâäéèêëôöùûüçÀÂÄÇÔÖÙÛÜŒ'
TARGET, DEPTH, CAP, GAPMIN = 0.25, 0.20, 0.15, 0.15
PUNCT, CAP_PUNCT = "'\"’‘”“.,-", 0.10
COLLIDE, PLUS = 0.05, 0.06     # traits qui se touchent presque : écartés, de PLUS au plus
BANDS = np.linspace(-0.30, 1.30, 81)
_cache = {}


def points(ch):
    """Points du dessin de `ch`, tous les 8 millièmes, et son avance."""
    if ch not in _cache:
        path, adv = sg.glyph(ch)
        out = []
        for poly in path.flatten(0.002):
            for i in range(1, len(poly)):
                (x0, y0), (x1, y1) = poly[i - 1], poly[i]
                n = max(1, int(math.dist((x0, y0), (x1, y1)) / 0.008))
                out += [(x0 + (x1 - x0) * k / n, y0 + (y1 - y0) * k / n) for k in range(n + 1)]
        _cache[ch] = (np.array(out), adv)
    return _cache[ch]


def min_gap(a, b, k):
    """Distance la plus courte entre les traits de a et de b posés à l'avance de a, crénés de k."""
    pa, adv = points(a)
    pb, _ = points(b)
    q = pb + np.array([adv + k, 0.0])
    return float(np.sqrt(((pa[:, None, :] - q[None, :, :]) ** 2).sum(-1)).min())


def white(a, b):
    """Blanc moyen limité entre le profil droit de a et le profil gauche de b."""
    pa, adv = points(a)
    pb, _ = points(b)
    gaps = []
    for y in BANDS:
        ra = pa[np.abs(pa[:, 1] - y) < 0.01]
        lb = pb[np.abs(pb[:, 1] - y) < 0.01]
        if len(ra) and len(lb):
            gaps.append(lb[:, 0].min() + adv - ra[:, 0].max())
    if not gaps:
        return None
    g = np.array(gaps)
    return float(np.minimum(g, g.min() + DEPTH).mean())


def kern(a, b) -> float:
    w = white(a, b)
    cap = CAP_PUNCT if b in PUNCT else CAP
    k = 0.0 if w is None else max(-cap, min(0.0, TARGET - w))
    if min_gap(a, b, 0.0) < COLLIDE:
        lo, hi = 0.0, PLUS
        for _ in range(12):
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if min_gap(a, b, mid) < COLLIDE else (lo, mid)
        return round(hi, 2)
    if k < 0 and min_gap(a, b, k) < GAPMIN:
        lo, hi = k, 0.0
        for _ in range(12):
            mid = (lo + hi) / 2
            lo, hi = (lo, mid) if min_gap(a, b, mid) >= GAPMIN else (mid, hi)
        k = hi
    r = round(k, 2)
    if r < 0 and min_gap(a, b, r) < GAPMIN:         # l'arrondi ne rapproche pas plus que GAPMIN
        r = math.ceil(k * 100 - 1e-9) / 100
    return r


def table() -> dict:
    out = {}
    for a in LEFT:
        for b in RIGHT:
            k = kern(a, b)
            if abs(k) >= 0.03:
                out[a + b] = k
    return out


def source(t: dict) -> str:
    """Le dictionnaire `_KERN` tel qu'il s'écrit dans strokegeo.py."""
    lines, cur = [], ''
    for p, v in t.items():
        item = f'{p!r}: {v:g},'
        if cur and len(cur) + 1 + len(item) > 114:
            lines.append(cur)
            cur = item
        else:
            cur = f'{cur} {item}' if cur else item
    if cur:
        lines.append(cur)
    return '_KERN = {\n' + ''.join(f'    {line}\n' for line in lines) + '}\n'


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stdout.write(source(table()))
