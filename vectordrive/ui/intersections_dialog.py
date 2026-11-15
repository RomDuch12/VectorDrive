"""Fenêtre des points d'intersection (TypeEdit : I) : combien, de quelle
nature, où (un clic sur une ligne y amène la vue), et la méthode pour les
supprimer — appliquée aux objets concernés, annulable."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QButtonGroup, QDialog, QDialogButtonBox, QDoubleSpinBox, QHBoxLayout, QLabel,
                               QListWidget, QListWidgetItem, QRadioButton, QVBoxLayout)

from ..core import intersect as I
from ..i18n import tr

TIPS = {
    'loops': 'Le contour garde sa forme ; seules les boucles plus courtes que la limite disparaissent '
             '(reprise de tracé, décalage retourné, gravure doublée).',
    'normalize': 'Chaque objet devient une surface sans croisement, à la règle pair-impair : ce qui se '
                 'recouvre devient un trou, comme le montre le remplissage.',
    'nonzero': 'Chaque objet devient la surface qu\'il remplit : les recouvrements restent pleins.',
    'union': 'Les objets qui se croisent ou se chevauchent sont réunis en un seul contour.',
    'outer': 'Réunion, puis le seul contour extérieur : les trous et les détails intérieurs disparaissent.',
    'split': 'Chaque contour est coupé à ses intersections en traits ouverts : on peut ensuite supprimer '
             'les morceaux en trop, ou graver chacun une fois.',
    'dedupe': 'Un contour dessiné deux fois (ou presque, à 0,05 mm) est gravé deux fois : on n\'en garde qu\'un.',
}


class IntersectionsDialog(QDialog):
    def __init__(self, parent, report: I.Report, canvas=None, settings=None):
        super().__init__(parent)
        self.setWindowTitle(tr('Points d\'intersection'))
        self.report = report
        self.canvas = canvas
        self.settings = settings
        lay = QVBoxLayout(self)
        r = report
        head = QLabel(tr('{0} point(s) d\'intersection : {1} boucle(s) ({2} petite(s)), {3} entre contours '
                         'd\'un objet, {4} entre objets ; {5} contour(s) en double.').format(
            r.count(), r.count('self'), r.small_loops(), r.count('contours'), r.count('objets'),
            r.count('doublon')))
        head.setWordWrap(True)
        lay.addWidget(head)
        self.list = QListWidget()
        self.list.setMaximumHeight(160)
        for c in r.crossings[:2000]:
            text = tr(I.KINDS[c.kind])
            if c.kind == 'self':
                text += tr(' — boucle de {0:.2f} mm').format(c.loop)
            it = QListWidgetItem(f'{text}   ({c.x:.3f} ; {c.y:.3f})')
            it.setData(Qt.ItemDataRole.UserRole, (c.x, c.y))
            self.list.addItem(it)
        self.list.itemClicked.connect(self._goto)
        lay.addWidget(self.list)
        lay.addWidget(QLabel(tr('Supprimer les intersections :')))
        self.group = QButtonGroup(self)
        self.radios = {}
        last = str(settings.value('intersections/methode', '') or '') if settings is not None else ''
        default = last if last in I.METHODS else ('dedupe' if r.count('doublon') else 'loops' if r.small_loops()
                                                  else 'union' if r.count('objets') else 'normalize')
        for key, label in I.METHODS.items():
            b = QRadioButton(tr(label))
            b.setToolTip(tr(TIPS[key]))
            self.group.addButton(b)
            self.radios[key] = b
            if key == 'loops':
                row = QHBoxLayout()
                row.addWidget(b)
                self.limit = QDoubleSpinBox()
                self.limit.setRange(0.01, 1000)
                self.limit.setDecimals(2)
                self.limit.setSuffix(' mm')
                self.limit.setValue(float(settings.value('intersections/boucle', I.LOOP)) if settings is not None
                                    else I.LOOP)
                self.limit.setToolTip(tr('Longueur au-dessous de laquelle une boucle est un défaut'))
                row.addWidget(QLabel(tr('plus courtes que')))
                row.addWidget(self.limit)
                row.addStretch(1)
                lay.addLayout(row)
            else:
                lay.addWidget(b)
        self.radios[default].setChecked(True)
        self.help = QLabel()
        self.help.setWordWrap(True)
        self.help.setStyleSheet('color: #868e96;')
        lay.addWidget(self.help)
        self.group.buttonToggled.connect(lambda *_a: self._help())
        self._help()
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        self.ok = bb.addButton(tr('Appliquer'), QDialogButtonBox.ButtonRole.AcceptRole)
        self.ok.setEnabled(bool(r.count()))
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def method(self) -> str:
        return next(k for k, b in self.radios.items() if b.isChecked())

    def set_method(self, key: str) -> None:
        self.radios[key].setChecked(True)

    def _help(self) -> None:
        self.help.setText(tr(TIPS[self.method()]))

    def _goto(self, it) -> None:
        if self.canvas is None:
            return
        x, y = it.data(Qt.ItemDataRole.UserRole)
        span = 5.0
        self.canvas.fit((x - span, y - span, x + span, y + span))

    def accept(self) -> None:
        if self.settings is not None:
            self.settings.setValue('intersections/methode', self.method())
            self.settings.setValue('intersections/boucle', self.limit.value())
        super().accept()
