"""Génère l'icône « V » de VectorDrive.

Même repère 3D que l'icône « G » de TypeEdit : hexagone isométrique (la
silhouette d'un cube, sommet en haut), trait de 13/256, extrémités droites,
angles vifs. Le dessin est construit ici, il ne reprend aucun pixel de
l'icône Gravotech : seules les proportions du repère sont communes.

Le V suit les **diagonales des deux faces avant du cube** : du sommet
haut-gauche au sommet bas, puis au sommet haut-droit ; chaque branche se
prolonge sur le tiers de l'arête supérieure du cube (variante D, retenue),
le cube complet restant en filigrane.

    python outils/icone_v.py            → vectordrive/ressources/vectordrive.ico (+ PNG), variante D
    python outils/icone_v.py --variante A
    python outils/icone_v.py --variantes → planche des variantes A, B, C
"""
from __future__ import annotations

import math
import pathlib
import sys

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter, QPainterPath, QPen

RACINE = pathlib.Path(__file__).resolve().parents[1]
SORTIE = RACINE / 'vectordrive' / 'ressources'

BLEU = QColor(19, 137, 226)          # le bleu du G
TRAIT = 13 / 256                     # épaisseur relative
R = 113.7 / 256                      # rayon de l'hexagone, à l'axe du trait
C = (0.5, 0.5)


def sommet(angle_deg: float) -> tuple[float, float]:
    """Sommet de l'hexagone (pointe en haut), repère image (Y vers le bas)."""
    a = math.radians(angle_deg)
    return (C[0] + R * math.cos(a), C[1] - R * math.sin(a))


HAUT = sommet(90)
HAUT_DROIT = sommet(30)
BAS_DROIT = sommet(-30)
BAS = sommet(-90)
BAS_GAUCHE = sommet(-150)
HAUT_GAUCHE = sommet(150)
CENTRE = C


def _tiers(a, b):
    """Point situé au tiers du segment [a, b], depuis a."""
    return (a[0] + (b[0] - a[0]) / 3, a[1] + (b[1] - a[1]) / 3)

VARIANTES = {
    # A : départ comme le G (arête haut-gauche), puis le V sur les faces
    'A': [[HAUT, HAUT_GAUCHE, BAS, HAUT_DROIT]],
    # B : le cube en filigrane, le V en plein
    'B': [[HAUT_GAUCHE, BAS, HAUT_DROIT]],
    # C : face du dessus fermée + V (losange pointé vers le bas)
    'C': [[HAUT, HAUT_GAUCHE, BAS, HAUT_DROIT, HAUT]],
    # D (retenue le 16/10) : B, et chaque branche du V se prolonge sur le
    # tiers de l'arête supérieure du cube, sans rejoindre l'autre
    'D': [[_tiers(HAUT_GAUCHE, HAUT), HAUT_GAUCHE, BAS, HAUT_DROIT, _tiers(HAUT_DROIT, HAUT)]],
}


def dessine(taille: int, variante: str = 'D', couleur: QColor = BLEU,
            trait: float | None = None) -> QImage:
    """`trait` : épaisseur en pixels (par défaut 13/256 de la taille)."""
    img = QImage(taille, taille, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    s = taille
    w = trait if trait is not None else TRAIT * s
    if variante in ('B', 'D'):
        fil = QColor(couleur)
        fil.setAlpha(70)
        pen = QPen(fil, w * 0.55)
        pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
        p.setPen(pen)
        hexa = QPainterPath()
        pts = [HAUT, HAUT_DROIT, BAS_DROIT, BAS, BAS_GAUCHE, HAUT_GAUCHE]
        hexa.moveTo(pts[0][0] * s, pts[0][1] * s)
        for q in pts[1:]:
            hexa.lineTo(q[0] * s, q[1] * s)
        hexa.closeSubpath()
        p.drawPath(hexa)
    pen = QPen(couleur, max(1.0, w))
    pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
    pen.setMiterLimit(4.0)
    pen.setCapStyle(Qt.PenCapStyle.FlatCap)
    p.setPen(pen)
    for trace in VARIANTES[variante]:
        path = QPainterPath()
        path.moveTo(trace[0][0] * s, trace[0][1] * s)
        for q in trace[1:]:
            path.lineTo(q[0] * s, q[1] * s)
        if trace[0] == trace[-1]:
            path.closeSubpath()
        p.drawPath(path)
    p.end()
    return img


def ico(variante: str, chemin: pathlib.Path) -> None:
    """ICO multi-tailles (Pillow assemble les PNG)."""
    from PIL import Image
    tailles = (16, 20, 24, 32, 40, 48, 64, 256)
    images = []
    for t in tailles:
        # suréchantillonnage ×4 ; trait d'au moins 1,6 px aux petites tailles
        q = dessine(t * 4, variante, trait=max(TRAIT * t, 1.6) * 4)
        tmp = chemin.with_name(f'_tmp_{t}.png')
        q.save(str(tmp))
        images.append(Image.open(tmp).convert('RGBA').resize((t, t), Image.LANCZOS))
        tmp.unlink()
    images[-1].save(chemin, format='ICO', sizes=[(t, t) for t in tailles],
                     append_images=images[:-1])


def planche(chemin: pathlib.Path, g_png: str | None = None) -> None:
    """Planche de comparaison : le G de TypeEdit (si fourni) et les variantes."""
    cols = (['G'] if g_png else []) + ['B', 'D']
    W, H = 300 * len(cols), 340
    img = QImage(W, H, QImage.Format.Format_ARGB32)
    img.fill(QColor('#ffffff'))
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    f = p.font()
    f.setPixelSize(22)
    p.setFont(f)
    for i, v in enumerate(cols):
        x = 300 * i + 22
        if v == 'G':
            p.drawImage(QRectF(x, 20, 256, 256), QImage(g_png))
            lab = 'TypeEdit (référence)'
        else:
            p.drawImage(QRectF(x, 20, 256, 256), dessine(256, v))
            lab = f'Variante {v}'
        p.setPen(QColor('#333333'))
        p.drawText(QRectF(300 * i, 290, 300, 40), Qt.AlignmentFlag.AlignCenter, lab)
    p.end()
    img.save(str(chemin))


def main(argv) -> int:
    app = QGuiApplication.instance() or QGuiApplication(argv[:1])
    SORTIE.mkdir(parents=True, exist_ok=True)
    if '--variantes' in argv:
        g = argv[argv.index('--g') + 1] if '--g' in argv else None
        out = RACINE / 'tests' / '_sorties' / 'icone_variantes.png'
        out.parent.mkdir(parents=True, exist_ok=True)
        planche(out, g)
        print(out)
        return 0
    v = argv[argv.index('--variante') + 1] if '--variante' in argv else 'D'
    dessine(256, v).save(str(SORTIE / 'vectordrive.png'))
    ico(v, SORTIE / 'vectordrive.ico')
    print(SORTIE / 'vectordrive.ico')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
