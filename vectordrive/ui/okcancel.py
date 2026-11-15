"""OK et Annuler bien visibles (demande du 15/11) : plus grands, colorés (OK en vert, Annuler en rouge), centrés en bas
de la fenêtre. Les couleurs sont lisibles en thème clair comme en thème sombre (texte blanc sur fond franc)."""
from __future__ import annotations

from PySide6.QtWidgets import QDialogButtonBox

#: fond, fond survolé ou appuyé
GREEN = ('#2e7d32', '#1b5e20')
RED = ('#c62828', '#8e1b1b')
#: taille minimale des deux boutons, en pixels
MIN_WIDTH, MIN_HEIGHT = 150, 40
#: propriété posée sur les deux boutons (styles, essais)
PROP = 'vd_prominent'

STYLE = ('QPushButton {{ background: {0}; color: white; border: 2px solid {0}; border-radius: 6px; '
         'padding: 6px 28px; font-weight: bold; }} '
         'QPushButton:hover, QPushButton:pressed {{ background: {1}; border-color: {1}; }} '
         'QPushButton:focus {{ border-color: #ffd54f; }} '
         'QPushButton:disabled {{ background: #e0e0e0; border-color: #bdbdbd; color: #616161; }}')


def prominent(box: QDialogButtonBox) -> None:
    """Les boutons OK et Annuler de `box` grands et colorés, `box` centrée (les autres boutons, s'il y en a, restent
    comme ils sont)."""
    box.setCenterButtons(True)
    for which, colors in ((QDialogButtonBox.StandardButton.Ok, GREEN),
                          (QDialogButtonBox.StandardButton.Cancel, RED)):
        b = box.button(which)
        if b is None:
            continue
        b.setMinimumSize(MIN_WIDTH, MIN_HEIGHT)
        f = b.font()
        if f.pointSizeF() > 0:
            f.setPointSizeF(f.pointSizeF() * 1.15)
        b.setFont(f)
        b.setStyleSheet(STYLE.format(*colors))
        b.setProperty(PROP, True)
