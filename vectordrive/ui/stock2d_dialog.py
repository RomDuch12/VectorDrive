"""Fenêtre « Brut du dessin 2D » (`core.stock2d`, réponse 20 du 14/11) : la plaque du dessin ou un contour dessiné,
des marges autour, une surépaisseur au-dessus de la plaque (à surfacer) et l'épaisseur — la simulation part du haut de
ce brut."""
from __future__ import annotations

from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout, QLabel, QLineEdit,
                               QPushButton, QVBoxLayout)

from ..core import stock2d
from ..i18n import tr


class Stock2DDialog(QDialog):
    """`stock` : le brut actuel ; `doc` : le dessin (plaque, contours) ; `picked` : l'objet choisi sur le dessin quand
    la fenêtre s'ouvre (« Prendre l'objet choisi »)."""

    def __init__(self, parent, stock: stock2d.Stock2D, doc, picked=None):
        super().__init__(parent)
        self.setWindowTitle(tr('Brut du dessin 2D'))
        self.doc, self.picked = doc, picked
        self.item = stock.item
        lay = QVBoxLayout(self)
        intro = QLabel(tr('La matière d\'où le dessin est usiné, quand ce n\'est pas une plaque plate à Z 0 : une '
                          'surépaisseur au-dessus de la plaque (un surfaçage la retire), des marges autour, la plaque '
                          'ou un contour dessiné. La simulation part du haut de ce brut.'))
        intro.setWordWrap(True)
        lay.addWidget(intro)
        form = QFormLayout()
        self.kind = QComboBox()
        for k, text in stock2d.KINDS.items():
            self.kind.addItem(tr(text), k)
        self.kind.setCurrentIndex(max(0, self.kind.findData(stock.kind)))
        form.addRow(tr('Brut'), self.kind)
        self.spins: dict = {}
        for key, label in (('top', 'Surépaisseur au-dessus de la plaque (mm)'), ('side', 'Marge autour (mm)'),
                           ('thickness', 'Épaisseur sous le dessus de la plaque (mm, 0 = celle de la plaque)')):
            sp = QDoubleSpinBox()
            sp.setRange(0.0, 10000.0)
            sp.setDecimals(2)
            sp.setValue(float(getattr(stock, key)))
            sp.valueChanged.connect(lambda _v: self.refresh())
            self.spins[key] = sp
            form.addRow(QLabel(tr(label)), sp)
        self.material = QLineEdit(stock.material)
        form.addRow(tr('Matière'), self.material)
        lay.addLayout(form)
        self.pick_btn = QPushButton(tr('Prendre l\'objet choisi comme contour'))
        self.pick_btn.setToolTip(tr('La forme fermée choisie sur le dessin devient le contour du brut'))
        self.pick_btn.clicked.connect(lambda: self.take_picked())
        lay.addWidget(self.pick_btn)
        self.info = QLabel()
        self.info.setWordWrap(True)
        lay.addWidget(self.info)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        self.ok = bb.button(QDialogButtonBox.StandardButton.Ok)
        self.kind.currentIndexChanged.connect(lambda _i: self.refresh())
        if self.kind.currentData() == 'contour' and not self.item and picked is not None:
            self.item = picked.id
        self.refresh()

    def take_picked(self) -> bool:
        """L'objet choisi devient le contour (nature « contour ») ; faux s'il n'a pas de contour fermé."""
        if self.picked is None or stock2d.outline(self.doc, self.picked.id) is None:
            return False
        self.item = self.picked.id
        self.kind.setCurrentIndex(self.kind.findData('contour'))
        self.refresh()
        return True

    def value(self) -> stock2d.Stock2D:
        s = stock2d.Stock2D(kind=self.kind.currentData() or '', material=self.material.text().strip())
        for key, sp in self.spins.items():
            setattr(s, key, float(sp.value()))
        if s.kind == 'contour':
            s.item = self.item or ''
        return s

    def refresh(self) -> None:
        kind = self.kind.currentData() or ''
        for sp in self.spins.values():
            sp.setEnabled(bool(kind))
        self.pick_btn.setEnabled(self.picked is not None and stock2d.outline(self.doc, self.picked.id) is not None)
        st = self.value()
        box = stock2d.resolve(st, self.doc)
        if kind == 'plaque' and box is None:
            text = tr('Le dessin n\'a pas de plaque : réglez-la (commande Plaque) ou prenez un contour dessiné.')
        elif kind == 'contour' and box is None:
            text = tr('Choisissez une forme fermée sur le dessin, puis « Prendre l\'objet choisi comme contour ».')
        else:
            text = stock2d.describe(st, box)
        self.info.setText(text)
        self.ok.setEnabled(not kind or box is not None)
