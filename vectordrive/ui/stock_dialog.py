"""Fenêtre « Brut de la pièce 3D » : bloc, barre ronde, plaque du dessin ou
boîte de la pièce agrandie de marges (`core.stock3d`) — l'ébauche 3D part
du haut du brut et vide tout le brut autour de la pièce."""
from __future__ import annotations

import math

from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout, QLabel,
                               QLineEdit, QPushButton, QVBoxLayout)

from ..core import stock3d
from ..i18n import tr

#: champs numériques : (clé, libellé, natures où ils servent)
FIELDS = (('sx', 'Longueur X (mm)', ('bloc',)),
          ('sy', 'Largeur Y (mm)', ('bloc',)),
          ('diameter', 'Diamètre (mm)', ('rond',)),
          ('sz', 'Hauteur (mm, 0 = la pièce et le dessus)', ('bloc', 'rond', 'plaque')),
          ('top', 'Au-dessus de la pièce (mm)', ('bloc', 'rond', 'plaque', 'marges')),
          ('side', 'Marge de chaque côté (mm)', ('marges',)),
          ('bottom', 'Marge dessous (mm)', ('marges',)),
          ('dx', 'Décalage X (mm)', ('bloc', 'rond')),
          ('dy', 'Décalage Y (mm)', ('bloc', 'rond')))


class StockDialog(QDialog):
    """`stock` : le brut actuel ; `model` : la pièce posée (contrôles,
    « Ajuster à la pièce ») ; `plate` : la plaque du dessin."""

    def __init__(self, parent, stock: stock3d.Stock3D, model=None, plate=None):
        super().__init__(parent)
        from .fit import release
        release(self)                                    # fermée : détruite, pas gardée par son parent
        self.setWindowTitle(tr('Brut de la pièce 3D'))
        self.model, self.plate = model, plate
        self.bounds = tuple(model.bounds()) if model is not None and len(getattr(model, 'triangles', ())) else None
        lay = QVBoxLayout(self)
        intro = QLabel(tr('Le bloc (ou la barre, la plaque) d\'où la pièce est usinée : l\'ébauche 3D part de son '
                          'haut et vide tout le brut autour de la pièce ; rien n\'est usiné hors de lui.'))
        intro.setWordWrap(True)
        lay.addWidget(intro)
        form = QFormLayout()
        self.kind = QComboBox()
        for k, text in stock3d.KINDS.items():
            self.kind.addItem(tr(text), k)
        self.kind.setCurrentIndex(max(0, self.kind.findData(stock.kind)))
        form.addRow(tr('Brut'), self.kind)
        self.spins: dict = {}
        self.rows: dict = {}
        for key, label, _kinds in FIELDS:
            sp = QDoubleSpinBox()
            sp.setRange(-10000.0 if key in ('dx', 'dy') else 0.0, 10000.0)
            sp.setDecimals(2)
            sp.setValue(float(getattr(stock, key)))
            sp.valueChanged.connect(lambda _v: self.refresh())
            self.spins[key] = sp
            lab = QLabel(tr(label))
            form.addRow(lab, sp)
            self.rows[key] = lab
        self.material = QLineEdit(stock.material)
        form.addRow(tr('Matière'), self.material)
        lay.addLayout(form)
        self.fit_btn = QPushButton(tr('Ajuster à la pièce'))
        self.fit_btn.setToolTip(tr('Bloc ou barre au plus juste autour de la pièce, arrondi au millimètre, avec la '
                                   'surépaisseur du dessus'))
        self.fit_btn.clicked.connect(lambda: self.fit_to_part())
        self.fit_btn.setEnabled(self.bounds is not None)
        lay.addWidget(self.fit_btn)
        self.info = QLabel()
        self.info.setWordWrap(True)
        lay.addWidget(self.info)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        self.kind.currentIndexChanged.connect(lambda _i: self.refresh())
        self.refresh()

    def value(self) -> stock3d.Stock3D:
        s = stock3d.Stock3D(kind=self.kind.currentData() or '', material=self.material.text().strip())
        for key, sp in self.spins.items():
            setattr(s, key, float(sp.value()))
        return s

    def fit_to_part(self) -> None:
        """Bloc (ou barre ronde) au plus juste autour de la pièce."""
        if self.bounds is None:
            return
        x0, y0, z0, x1, y1, z1 = self.bounds
        k = self.kind.currentData()
        if k not in ('bloc', 'rond'):
            self.kind.setCurrentIndex(self.kind.findData('bloc'))
            k = 'bloc'
        top = self.spins['top'].value()
        self.spins['sx'].setValue(math.ceil(x1 - x0 - 1e-6))
        self.spins['sy'].setValue(math.ceil(y1 - y0 - 1e-6))
        self.spins['diameter'].setValue(math.ceil(math.hypot(x1 - x0, y1 - y0) - 1e-6))
        self.spins['sz'].setValue(math.ceil(z1 - z0 + top - 1e-6))
        self.spins['dx'].setValue(0.0)
        self.spins['dy'].setValue(0.0)
        self.refresh()

    def refresh(self) -> None:
        k = self.kind.currentData() or ''
        for key, _label, kinds in FIELDS:
            on = k in kinds
            self.spins[key].setVisible(on)
            self.rows[key].setVisible(on)
        self.material.setEnabled(bool(k))
        self.fit_btn.setVisible(k in ('bloc', 'rond', ''))
        s = self.value()
        if not s.active():
            self.info.setText(tr('Sans brut : la matière est supposée au niveau du haut de la pièce, autour d\'elle '
                                 '(sur une largeur d\'outil).'))
            return
        if self.bounds is None:
            self.info.setText(tr('Pièce 3D inconnue : le brut sera placé autour d\'elle au calcul.'))
            return
        box = stock3d.resolve(s, self.bounds, self.plate)
        if box is None:
            self.info.setText(tr('Brut incomplet : donner ses dimensions (ou une plaque au dessin).'))
            return
        lines = [tr('Brut : ') + stock3d.describe(s, box)]
        lines += stock3d.check(box, self.bounds)
        self.info.setText('\n'.join(lines))
