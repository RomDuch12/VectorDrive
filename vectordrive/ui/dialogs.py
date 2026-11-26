"""Boîtes de dialogue : texte, décalage, congés et chanfreins."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox,
                               QDoubleSpinBox, QFormLayout, QPlainTextEdit)
from ..i18n import tr


def _spin(value: float, lo: float, hi: float, suffix=' mm', decimals=3) -> QDoubleSpinBox:
    s = QDoubleSpinBox()
    s.setDecimals(decimals)
    s.setRange(lo, hi)
    s.setValue(value)
    s.setSuffix(suffix)
    s.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
    return s


def _buttons(dlg: QDialog, form: QFormLayout) -> None:
    bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
    bb.accepted.connect(dlg.accept)
    bb.rejected.connect(dlg.reject)
    form.addRow(bb)


def render_text_preview(text: str, font: str, align: str = 'left', spacing_ratio: float = 0.0,
                        line_spacing: float = 1.2, width: int = 420, height: int = 90, dark: bool = False):
    """Aperçu du texte dessiné par le moteur de VectorDrive (vraie police,
    celles des plugins comprises, crénage) : QPixmap."""
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap, QTransform
    from ..core import text as TX
    pm = QPixmap(width, height)
    pm.fill(QColor('#2b2b2b' if dark else 'white'))
    sample = '\n'.join(text.split('\n')[:3])[:120] or 'AaBbCc 0123'
    try:
        path = TX.layout(sample, font, 10.0, align=align, spacing=spacing_ratio * 10.0,
                         line_spacing=line_spacing)
    except Exception:
        path = None
    bb = path.bbox() if path else None
    if not bb:
        return pm
    w, h = max(bb[2] - bb[0], 1e-6), max(bb[3] - bb[1], 1e-6)
    k = min((width - 16) / w, (height - 16) / h)
    tf = QTransform(k, 0, 0, -k, (width - w * k) / 2 - bb[0] * k, (height + h * k) / 2 + bb[1] * k)
    q = QPainterPath()                    # contours fermés : remplis
    q.setFillRule(Qt.FillRule.OddEvenFill)
    o = QPainterPath()                    # traits ouverts (polices monotrait) : jamais remplis
    for c in path.contours:
        pts = c.flatten(0.5 / k)
        if not pts:
            continue
        tgt = q if c.closed else o
        tgt.moveTo(*pts[0])
        for pt in pts[1:]:
            tgt.lineTo(*pt)
        if c.closed:
            tgt.closeSubpath()
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setTransform(tf)
    pen = QPen(QColor('#e8e8e8' if dark else '#202020'), 0)
    pen.setCosmetic(True)
    p.setPen(pen)
    fill = QColor('#e8e8e8' if dark else '#202020')
    fill.setAlpha(60)
    p.setBrush(fill)
    p.drawPath(q)
    pen.setWidthF(1.6)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawPath(o)
    p.end()
    return pm


class TextDialog(QDialog):
    """Texte : contenu, police, hauteur des capitales, alignement ; aperçu
    dessiné avec la vraie police."""

    def __init__(self, parent=None, *, text='', font='Arial', height=5.0, align='left',
                 spacing=0.0, line_spacing=1.2, fit_width=0.0, fit_mode='spacing'):
        super().__init__(parent)
        from .fit import no_hscroll
        no_hscroll(self)                                 # pas de défilement horizontal à l'ouverture
        self.setWindowTitle(tr('Texte'))
        form = QFormLayout(self)
        self.text = QPlainTextEdit(text)
        self.text.setMinimumHeight(90)
        self.font = FontBox()
        self.font.setCurrentFont(QFont(font))
        self.height = _spin(height, 0.05, 2000)
        self.align = QComboBox()
        for k, label in (('left', tr('Gauche')), ('center', tr('Centré')), ('right', tr('Droite')),
                         ('justify', tr('Justifié'))):
            self.align.addItem(label, k)
        self.align.setCurrentIndex(max(0, self.align.findData(align)))
        self.spacing = _spin(spacing, -100, 100)
        self.line = _spin(line_spacing, 0.5, 5, suffix=tr(' × corps'), decimals=2)
        form.addRow(tr('Texte'), self.text)
        from PySide6.QtWidgets import QPushButton, QSizePolicy
        from ..core.text import SPRING
        spring = QPushButton(tr('Ressort {0}').format(SPRING))
        spring.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)   # à sa taille, pas toute la ligne
        spring.setToolTip(tr('Ressort : l\'espace libre de la ligne (jusqu\'à la largeur imposée, sinon la plus '
                             'longue ligne) est partagé entre les ressorts — pour aligner, centrer, répartir'))
        spring.clicked.connect(lambda: (self.text.insertPlainText(SPRING), self.text.setFocus()))
        form.addRow('', spring)
        form.addRow(tr('Police'), self.font)
        form.addRow(tr('Hauteur des capitales'), self.height)
        form.addRow(tr('Alignement'), self.align)
        form.addRow(tr('Interlettrage'), self.spacing)
        form.addRow(tr('Interligne'), self.line)
        self.fit_w = _spin(fit_width, 0, 100000)
        self.fit_w.setSpecialValueText(tr('libre'))
        self.fit_mode = QComboBox()
        self.fit_mode.addItem(tr('par l\'interlettrage'), 'spacing')
        self.fit_mode.addItem(tr('par étirement des lettres'), 'ratio')
        self.fit_mode.setCurrentIndex(max(0, self.fit_mode.findData(fit_mode)))
        form.addRow(tr('Largeur imposée'), self.fit_w)
        form.addRow(tr('Ajustement'), self.fit_mode)
        self.fit_w.valueChanged.connect(lambda v: self.spacing.setEnabled(v <= 0))
        self.spacing.setEnabled(fit_width <= 0)
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QLabel
        self.preview = QLabel()
        self.preview.setMinimumSize(420, 90)
        self.preview.setToolTip(tr('Aperçu avec la police choisie'))
        form.addRow(tr('Aperçu'), self.preview)
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.timeout.connect(self.update_preview)
        for sig in (self.text.textChanged, self.font.currentTextChanged, self.align.currentIndexChanged,
                    self.spacing.valueChanged, self.line.valueChanged):
            sig.connect(lambda *_a: self._preview_timer.start(150))
        _buttons(self, form)
        self.update_preview()
        self.text.setFocus()

    def update_preview(self) -> None:
        h = max(self.height.value(), 0.05)
        dark = self.palette().window().color().lightness() < 128
        self.preview.setPixmap(render_text_preview(
            self.text.toPlainText(), self.font.currentText(), self.align.currentData() or 'left',
            self.spacing.value() / h, self.line.value(), dark=dark))

    def values(self) -> dict:
        return {'text': self.text.toPlainText(), 'font': self.font.currentFont().family(),
                'height': self.height.value(), 'align': self.align.currentData(),
                'spacing': self.spacing.value(), 'line_spacing': self.line.value(),
                'fit': {'width': self.fit_w.value(), 'mode': self.fit_mode.currentData()}}


class TextsDialog(QDialog):
    """Plusieurs textes sélectionnés : un formulaire commun. `rows` : les valeurs de chaque texte
    (`text_presets.values`, plus `fit_width` et `fit_mode`). Chaque champ montre la valeur commune, ou celle du premier
    texte en gris quand elles diffèrent ; seuls les champs modifiés (`changes`) s'appliquent, à tous."""

    FIELDS = ('font', 'size', 'width', 'italic', 'spacing', 'line_spacing', 'spacing_mode', 'align', 'fit_width',
              'fit_mode')
    #: champs en gris : les valeurs diffèrent d'un texte à l'autre
    MIXED_STYLE = 'color: gray'

    def __init__(self, parent=None, rows: list | None = None):
        super().__init__(parent)
        from PySide6.QtWidgets import QLabel
        from ..core import text as TX
        from .fit import no_hscroll
        from .text_presets import SPACINGS
        no_hscroll(self)
        rows = rows or [{}]
        first = rows[0]
        self.setWindowTitle(tr('Textes'))
        form = QFormLayout(self)
        note = QLabel(tr('{0} textes : les champs modifiés s’appliquent à tous. En gris, les valeurs diffèrent d’un texte '
                         'à l’autre (celle du premier est montrée) : laissées telles quelles si vous n’y touchez pas')
                      .format(len(rows)))
        note.setWordWrap(True)
        form.addRow(note)
        # noms en _box : `font`, `size`, `width` sont des méthodes de QWidget (la mise à la taille de l'écran s'en sert)
        self.font_box = FontBox()
        self.font_box.setCurrentFont(QFont(str(first.get('font') or 'Arial')))
        self.font_box.setEditText(str(first.get('font') or 'Arial'))
        self.size_box = _spin(float(first.get('size', 5.0)), 0.05, 2000)
        self.width_box = _spin(float(first.get('width', 100.0)), 10, 1000, suffix=' %', decimals=1)
        self.italic = _spin(float(first.get('italic', 0.0)), -TX.ITALIC_MAX, TX.ITALIC_MAX, suffix=' °', decimals=1)
        self.spacing = _spin(float(first.get('spacing', 0.0)), -100, 100)
        self.line = _spin(float(first.get('line_spacing', 1.2)), 0.3, 10, suffix=tr(' × corps'), decimals=2)
        self.spacing_mode = QComboBox()
        for k, label in SPACINGS:
            self.spacing_mode.addItem(tr(label), k)
        self.spacing_mode.setCurrentIndex(max(0, self.spacing_mode.findData(first.get('spacing_mode', 'typo'))))
        self.align = QComboBox()
        for k, label in (('left', tr('Gauche')), ('center', tr('Centré')), ('right', tr('Droite')),
                         ('justify', tr('Justifié'))):
            self.align.addItem(label, k)
        self.align.setCurrentIndex(max(0, self.align.findData(first.get('align', 'left'))))
        self.fit_w = _spin(float(first.get('fit_width', 0.0)), 0, 100000)
        self.fit_w.setSpecialValueText(tr('libre'))
        self.fit_mode = QComboBox()
        self.fit_mode.addItem(tr('par l\'interlettrage'), 'spacing')
        self.fit_mode.addItem(tr('par étirement des lettres'), 'ratio')
        self.fit_mode.setCurrentIndex(max(0, self.fit_mode.findData(first.get('fit_mode', 'spacing'))))
        self.widgets = {'font': self.font_box, 'size': self.size_box, 'width': self.width_box, 'italic': self.italic,
                        'spacing': self.spacing, 'line_spacing': self.line, 'spacing_mode': self.spacing_mode,
                        'align': self.align, 'fit_width': self.fit_w, 'fit_mode': self.fit_mode}
        for label, f in ((tr('Police'), 'font'), (tr('Hauteur des capitales'), 'size'), (tr('Largeur des lettres'), 'width'),
                         (tr('Inclinaison'), 'italic'), (tr('Interlettrage'), 'spacing'), (tr('Interligne'), 'line_spacing'),
                         (tr('Espacement des lettres'), 'spacing_mode'), (tr('Alignement'), 'align'),
                         (tr('Largeur imposée'), 'fit_width'), (tr('Ajustement'), 'fit_mode')):
            form.addRow(label, self.widgets[f])
        self.mixed = {f for f in self.FIELDS if len({repr(r.get(f)) for r in rows}) > 1}
        for f in self.mixed:
            self.widgets[f].setStyleSheet(self.MIXED_STYLE)
            self.widgets[f].setToolTip(tr('Valeurs différentes d’un texte à l’autre : laissées telles quelles si vous '
                                          'n’y touchez pas'))
        self.touched: set = set()
        self.font_box.currentTextChanged.connect(lambda *_a: self._touch('font'))
        for f in ('size', 'width', 'italic', 'spacing', 'line_spacing', 'fit_width'):
            self.widgets[f].valueChanged.connect(lambda *_a, f=f: self._touch(f))
        for f in ('spacing_mode', 'align', 'fit_mode'):
            self.widgets[f].currentIndexChanged.connect(lambda *_a, f=f: self._touch(f))
        _buttons(self, form)

    def _touch(self, field: str) -> None:
        self.touched.add(field)
        if field in self.mixed:
            self.widgets[field].setStyleSheet('')
            self.widgets[field].setToolTip('')

    def changes(self) -> dict:
        """Les champs modifiés et leur valeur (`width` en rapport : 1 pour 100 %)."""
        get = {'font': lambda: self.font_box.currentText().strip(), 'size': self.size_box.value,
               'width': lambda: self.width_box.value() / 100.0, 'italic': self.italic.value, 'spacing': self.spacing.value,
               'line_spacing': self.line.value, 'spacing_mode': lambda: self.spacing_mode.currentData() or 'typo',
               'align': lambda: self.align.currentData() or 'left', 'fit_width': self.fit_w.value,
               'fit_mode': lambda: self.fit_mode.currentData() or 'spacing'}
        return {f: get[f]() for f in self.FIELDS if f in self.touched}


class OffsetDialog(QDialog):
    """Décaler : la distance arrive sélectionnée (« A 5 Entrée » décale de
    5) ; jonction et « conserver l'original » repris de la fois d'avant ; les
    décalages qui se croisent réunis (d'office)."""
    def __init__(self, parent=None, distance=1.0, join='round', keep=True, last_only=False, union=True):
        super().__init__(parent)
        from .fit import no_hscroll
        no_hscroll(self)                                 # pas de défilement horizontal à l'ouverture
        self.setWindowTitle(tr('Décaler'))
        form = QFormLayout(self)
        self.dist = _spin(distance, -1000, 1000)
        self.dist.setToolTip(tr('Contour ouvert : un seul contour ouvert parallèle, à la même distance partout, sans '
                                'bouchon aux bouts ; + à droite du sens de tracé, − à gauche (« Sens », Ctrl+7, le '
                                'montre)'))
        self.join = QComboBox()
        for k, label in (('round', tr('Arrondie')), ('miter', tr('Angle vif')), ('bevel', tr('Chanfreinée'))):
            self.join.addItem(label, k)
        self.join.setCurrentIndex(max(0, self.join.findData(join)))
        self.count = QDoubleSpinBox()
        self.count.setDecimals(0)
        self.count.setRange(1, 200)
        self.count.setValue(1)
        self.keep = QCheckBox(tr('Conserver l\'original'))
        self.keep.setChecked(bool(keep))
        self.last_only = QCheckBox(tr('Seulement le plus éloigné'))
        self.last_only.setChecked(bool(last_only))
        self.last_only.setToolTip(tr('Avec plusieurs décalages : garder seulement le dernier, à la distance multipliée par '
                                     'leur nombre'))
        self.union = QCheckBox(tr('Réunir les décalages qui se croisent'))
        self.union.setChecked(bool(union))
        self.union.setToolTip(tr('Les contours décalés qui se chevauchent (lettres voisines, formes proches) ne font plus '
                                 'qu’un, à chaque distance et pour un même outil : pas de matière enlevée deux fois. '
                                 'L’un dans l’autre (une lettre dans son cadre), ils restent séparés'))
        form.addRow(tr('Distance (+ extérieur, − intérieur)'), self.dist)
        form.addRow(tr('Jonctions'), self.join)
        form.addRow(tr('Nombre de décalages'), self.count)
        form.addRow(self.last_only)
        form.addRow(self.union)
        form.addRow(self.keep)
        _buttons(self, form)
        self.dist.setFocus()

    def showEvent(self, ev) -> None:
        super().showEvent(ev)
        self.dist.setFocus()
        self.dist.selectAll()                            # la frappe remplace la valeur

    def values(self) -> dict:
        return {'distance': self.dist.value(), 'join': self.join.currentData(),
                'count': int(self.count.value()), 'keep': self.keep.isChecked(), 'last_only': self.last_only.isChecked(),
                'union': self.union.isChecked()}


class CornerDialog(QDialog):
    def __init__(self, parent=None, kind='fillet', size=2.0):
        super().__init__(parent)
        from .fit import no_hscroll
        no_hscroll(self)                                 # pas de défilement horizontal à l'ouverture
        self.setWindowTitle(tr('Congés') if kind == 'fillet' else tr('Chanfreins'))
        form = QFormLayout(self)
        self.size = _spin(size, -10000 if kind == 'fillet' else 0.001, 10000)
        if kind == 'fillet':
            self.size.setToolTip(tr('Rayon négatif : arrondi creusé vers l\'intérieur, centré sur le coin'))
        form.addRow(tr('Rayon (négatif : creusé)') if kind == 'fillet' else tr('Recul'), self.size)
        _buttons(self, form)

    def value(self) -> float:
        return self.size.value()


class TextArcsDialog(QDialog):
    """Textes sur arcs multiples (TypeEdit) : centre des arcs, rotation, et pour chaque texte : rayon, angle de départ
    (milieu du texte), sens horaire, déformation. Quatre cases imposent aux lignes suivantes la valeur de la première.
    Un texte déjà posé sur un arc revient avec ses réglages. `preview(centre, lignes)` : ce que fait le bouton Aperçu."""

    def __init__(self, parent, texts: list, center, preview=None):
        super().__init__(parent)
        from .fit import no_hscroll
        no_hscroll(self)                                 # pas de défilement horizontal à l'ouverture
        import math

        from PySide6.QtWidgets import QCheckBox, QComboBox, QHBoxLayout, QTableWidget, QTableWidgetItem, QVBoxLayout
        from ..core.text import ARC_MODES
        self._preview = preview
        self.setWindowTitle(tr('Textes sur arcs multiples'))
        self.setSizeGripEnabled(True)
        lay = QVBoxLayout(self)
        form = QFormLayout()
        self.cx, self.cy = _spin(center[0], -1e6, 1e6, decimals=3), _spin(center[1], -1e6, 1e6, decimals=3)
        self.rotation = _spin(0.0, -360.0, 360.0, suffix=' °', decimals=2)
        form.addRow(tr('Centre des arcs X (mm)'), self.cx)
        form.addRow(tr('Centre des arcs Y (mm)'), self.cy)
        form.addRow(tr('Rotation (°)'), self.rotation)
        self.same_radius = QCheckBox(tr('Même rayon'))
        self.same_angle = QCheckBox(tr('Angle de départ identique'))
        self.same_direction = QCheckBox(tr('Même direction'))
        self.same_type = QCheckBox(tr('Même type'))
        self._same = (self.same_radius, self.same_angle, self.same_direction, self.same_type)
        boxes = QHBoxLayout()
        for box in self._same:
            box.toggled.connect(lambda _=False: self._sync())
            boxes.addWidget(box)
        boxes.addStretch(1)
        lay.addLayout(form)
        lay.addLayout(boxes)
        self.table = QTableWidget(len(texts), 5)
        self.table.setHorizontalHeaderLabels([tr('Texte'), tr('Rayon (mm)'), tr('Angle (°)'), tr('Sens horaire'),
                                              tr('Déformation')])
        h = max(t.size for t in texts)
        self.widgets = []
        for i, t in enumerate(texts):
            item = QTableWidgetItem(t.text.split('\n')[0])
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(i, 0, item)
            saved = t.extra.get('arc_warp') or {}
            r = _spin(float(saved.get('radius', 20.0 + (len(texts) - 1 - i) * 1.6 * h)), 0.01, 1e6, decimals=3)
            a = _spin(math.fmod(float(saved.get('angle', 90.0)), 360.0), -360.0, 360.0, suffix=' °', decimals=2)
            cw = QCheckBox()
            cw.setChecked(bool(saved.get('clockwise', True)))
            mode = QComboBox()
            for k, lab in ARC_MODES.items():
                mode.addItem(tr(lab), k)
            at = mode.findData(saved.get('mode', 'simple'))
            if at >= 0:
                mode.setCurrentIndex(at)
            if i == 0:                                   # les lignes suivantes peuvent la suivre
                r.valueChanged.connect(lambda _=0.0: self._sync())
                a.valueChanged.connect(lambda _=0.0: self._sync())
                cw.toggled.connect(lambda _=False: self._sync())
                mode.currentIndexChanged.connect(lambda _=0: self._sync())
            for col, w in ((1, r), (2, a), (3, cw), (4, mode)):
                self.table.setCellWidget(i, col, w)
            self.widgets.append((r, a, cw, mode))
        self.table.resizeColumnsToContents()
        lay.addWidget(self.table, 1)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        self.b_preview = bb.addButton(tr('Aperçu'), QDialogButtonBox.ButtonRole.ActionRole)
        self.b_preview.setAutoDefault(False)
        self.b_preview.setEnabled(preview is not None)
        self.b_preview.clicked.connect(lambda _=False: self.preview_now())
        lay.addWidget(bb)
        self.resize(720, 290 + 30 * len(texts))

    def _sync(self) -> None:
        """Une case cochée : les lignes suivantes prennent la valeur de la première et ne se règlent plus."""
        if not self.widgets:
            return
        first = self.widgets[0]
        for col, box in enumerate(self._same):
            on = box.isChecked()
            for row in self.widgets[1:]:
                row[col].setEnabled(not on)
                if on:
                    if col < 2:
                        row[col].setValue(first[col].value())
                    elif col == 2:
                        row[col].setChecked(first[col].isChecked())
                    else:
                        row[col].setCurrentIndex(first[col].currentIndex())

    def preview_now(self) -> None:
        if self._preview is not None:
            self._preview(self.center(), self.rows())

    def center(self) -> tuple:
        return (self.cx.value(), self.cy.value())

    def rows(self) -> list:
        return [(r.value(), a.value() + self.rotation.value(), cw.isChecked(), mode.currentData())
                for r, a, cw, mode in self.widgets]


class ParamsDialog(QDialog):
    """Formulaire construit à partir d'une dataclass de paramètres
    (export SimPl, CLJOB…). `labels` : champ → libellé ; les champs absents
    de `labels` ne sont pas montrés."""

    def __init__(self, parent, title: str, params, labels: dict, warning: str = '', choices: dict | None = None):
        super().__init__(parent)
        from .fit import no_hscroll
        no_hscroll(self)                                 # pas de défilement horizontal à l'ouverture
        from PySide6.QtWidgets import QComboBox, QLabel, QLineEdit, QSpinBox
        self.setWindowTitle(title)
        self.params = params
        form = QFormLayout(self)
        if warning:
            w = QLabel(warning)
            w.setWordWrap(True)
            w.setStyleSheet('color: #a33; font-weight: bold;')
            form.addRow(w)
        self.fields = {}
        for name, label in labels.items():
            v = getattr(params, name)
            if choices and name in choices:
                ed = QComboBox()
                for value, text in choices[name]:
                    ed.addItem(text, value)
                ed.setCurrentIndex(max(0, ed.findData(v)))
            elif isinstance(v, bool):
                ed = QCheckBox()
                ed.setChecked(v)
            elif isinstance(v, int):
                ed = QSpinBox()
                ed.setRange(-10_000_000, 10_000_000)
                ed.setValue(v)
            elif isinstance(v, float):
                ed = _spin(v, -1e7, 1e7, suffix='', decimals=4)
            else:
                ed = QLineEdit(str(v))
            form.addRow(label, ed)
            self.fields[name] = ed
        _buttons(self, form)

    def showEvent(self, ev) -> None:                     # noqa: N802 (API Qt)
        super().showEvent(ev)
        if not ev.spontaneous():                         # à l'ouverture (pas au retour d'une fenêtre réduite)
            from .fields import focus_first
            focus_first(self.fields.values())            # le premier champ, sélectionné : la frappe le remplace

    def result_params(self):
        from PySide6.QtWidgets import QComboBox, QLineEdit, QSpinBox
        for name, ed in self.fields.items():
            if isinstance(ed, QComboBox):
                setattr(self.params, name, ed.currentData())
            elif isinstance(ed, QCheckBox):
                setattr(self.params, name, ed.isChecked())
            elif isinstance(ed, QSpinBox):
                setattr(self.params, name, ed.value())
            elif isinstance(ed, QDoubleSpinBox):
                setattr(self.params, name, ed.value())
            elif isinstance(ed, QLineEdit):
                setattr(self.params, name, ed.text())
        return self.params


class DuplicateDialog(QDialog):
    """Duplication linéaire, en grille ou circulaire de la sélection."""

    def __init__(self, parent=None, *, center=(0.0, 0.0), plate_center=None, settings=None):
        super().__init__(parent)
        from .fit import no_hscroll
        no_hscroll(self)                                 # pas de défilement horizontal à l'ouverture
        from PySide6.QtWidgets import QSpinBox, QTabWidget, QVBoxLayout, QWidget
        self.setWindowTitle(tr('Dupliquer'))
        self.settings = settings
        g = (lambda k, d: float(settings.value(f'dupliquer/{k}', d))) if settings else (lambda k, d: d)
        lay = QVBoxLayout(self)
        self.tabs = QTabWidget()
        lay.addWidget(self.tabs)

        def count(v):
            s = QSpinBox()
            s.setRange(1, 10000)
            s.setValue(int(v))
            return s
        # linéaire
        w = QWidget()
        f = QFormLayout(w)
        self.lin_n = count(g('lin_n', 1))
        self.lin_dx = _spin(g('lin_dx', 10.0), -1e6, 1e6)
        self.lin_dy = _spin(g('lin_dy', 0.0), -1e6, 1e6)
        f.addRow(tr('Nombre de copies'), self.lin_n)
        f.addRow(tr('Pas X'), self.lin_dx)
        f.addRow(tr('Pas Y'), self.lin_dy)
        self.tabs.addTab(w, tr('Linéaire'))
        # grille
        w = QWidget()
        f = QFormLayout(w)
        self.gr_cols = count(g('gr_cols', 3))
        self.gr_rows = count(g('gr_rows', 2))
        self.gr_dx = _spin(g('gr_dx', 20.0), -1e6, 1e6)
        self.gr_dy = _spin(g('gr_dy', 20.0), -1e6, 1e6)
        f.addRow(tr('Colonnes'), self.gr_cols)
        f.addRow(tr('Lignes'), self.gr_rows)
        f.addRow(tr('Pas X'), self.gr_dx)
        f.addRow(tr('Pas Y'), self.gr_dy)
        self.tabs.addTab(w, tr('Grille'))
        # circulaire
        w = QWidget()
        f = QFormLayout(w)
        self.ci_n = count(g('ci_n', 6))
        self.ci_n.setMinimum(2)
        self.ci_angle = _spin(g('ci_angle', 360.0), -360, 360, suffix=' °')
        self.ci_ref = QComboBox()
        self.ci_ref.addItem(tr('Centre de la sélection'), 'sel')
        if plate_center is not None:
            self.ci_ref.addItem(tr('Centre de la plaque'), 'plate')
        self.ci_ref.addItem(tr('Point X / Y'), 'xy')
        self._centers = {'sel': center, 'plate': plate_center}
        self.ci_x = _spin(center[0], -1e6, 1e6)
        self.ci_y = _spin(center[1], -1e6, 1e6)
        self.ci_ref.currentIndexChanged.connect(self._ref_changed)
        self.ci_rot = QCheckBox(tr('Faire tourner les copies'))
        self.al_rot = QCheckBox(tr('Orienter selon la courbe'))
        self.ci_rot.setChecked(True)
        f.addRow(tr('Exemplaires (original compris)'), self.ci_n)
        f.addRow(tr('Angle total'), self.ci_angle)
        f.addRow(tr('Centre'), self.ci_ref)
        f.addRow('X', self.ci_x)
        f.addRow('Y', self.ci_y)
        f.addRow(self.ci_rot)
        self.tabs.addTab(w, tr('Circulaire'))
        # sur courbe : la courbe est le dernier objet sélectionné
        w = QWidget()
        f = QFormLayout(w)
        self.al_n = count(g('al_n', 8))
        self.al_sp = _spin(float(g('al_sp', 0.0)), 0, 1e6)
        self.al_sp.setToolTip(tr('Un exemplaire tous les tant de mm depuis le départ de la courbe, autant qu\'elle '
                                 'en porte ; 0 : le nombre d\'exemplaires'))
        self.al_sp.valueChanged.connect(lambda v: self.al_n.setEnabled(v <= 0))
        self.al_n.setEnabled(self.al_sp.value() <= 0)
        self.al_rot.setChecked(True)
        self.al_kind = QComboBox()
        self.al_kind.addItem(tr('Posés sur la courbe'), 'along')
        self.al_kind.addItem(tr('En gardant leur écart à la courbe'), 'follow')
        self.al_kind.addItem(tr('Par déformation du premier objet au second'), 'morph')
        kept = self.al_kind.findData(settings.value('dupliquer/al_kind', 'along') if settings else 'along')
        self.al_kind.setCurrentIndex(max(kept, 0))
        from PySide6.QtWidgets import QLabel
        note = QLabel(tr('La courbe est le dernier objet sélectionné, ou plusieurs courbes combinées ; les autres sont '
                         'dupliqués à intervalles réguliers le long de chacune. Pour garder l\'écart, un marqueur parmi '
                         'les objets donne le point qui suit la courbe, sinon son départ.'))
        note.setWordWrap(True)
        f.addRow(note)
        f.addRow(tr('Type'), self.al_kind)
        f.addRow(tr('Exemplaires'), self.al_n)
        f.addRow(tr('Écart (0 : selon le nombre)'), self.al_sp)
        f.addRow(self.al_rot)
        self.tabs.addTab(w, tr('Sur courbe'))
        self.tabs.setCurrentIndex(int(g('onglet', 0)))
        form = QFormLayout()
        lay.addLayout(form)
        _buttons(self, form)

    def _ref_changed(self) -> None:
        k = self.ci_ref.currentData()
        c = self._centers.get(k)
        if c is not None:
            self.ci_x.setValue(c[0])
            self.ci_y.setValue(c[1])

    def values(self) -> dict:
        v = {'mode': ('linear', 'grid', 'circular', 'along')[self.tabs.currentIndex()],
             'al_n': self.al_n.value(), 'al_sp': self.al_sp.value(), 'al_rot': self.al_rot.isChecked(),
             'al_kind': self.al_kind.currentData(),
             'lin_n': self.lin_n.value(), 'lin_dx': self.lin_dx.value(), 'lin_dy': self.lin_dy.value(),
             'gr_cols': self.gr_cols.value(), 'gr_rows': self.gr_rows.value(),
             'gr_dx': self.gr_dx.value(), 'gr_dy': self.gr_dy.value(),
             'ci_n': self.ci_n.value(), 'ci_angle': self.ci_angle.value(),
             'center': (self.ci_x.value(), self.ci_y.value()), 'rotate': self.ci_rot.isChecked()}
        if self.settings is not None:
            for k in ('lin_n', 'lin_dx', 'lin_dy', 'gr_cols', 'gr_rows', 'gr_dx', 'gr_dy', 'ci_n', 'ci_angle',
                      'al_n', 'al_sp'):
                self.settings.setValue(f'dupliquer/{k}', v[k])
            self.settings.setValue('dupliquer/onglet', self.tabs.currentIndex())
            self.settings.setValue('dupliquer/al_kind', v['al_kind'])
        return v


#: Options F10 : clé QSettings → (libellé, défaut, mini, maxi, suffixe, décimales)
class BarcodeDialog(QDialog):
    """Code-barres : symbologie, contenu, module, style ; aperçu de la taille."""

    def __init__(self, parent=None, spec=None):
        super().__init__(parent)
        from .fit import no_hscroll
        no_hscroll(self)                                 # pas de défilement horizontal à l'ouverture
        from PySide6.QtWidgets import QLabel, QLineEdit
        from ..core import barcode as B
        from ..core import codes
        self.setWindowTitle(tr('Code-barres'))
        self.spec = spec or codes.BarcodeSpec()
        form = QFormLayout(self)
        self.kind = QComboBox()
        for k, lab in B.KINDS:
            self.kind.addItem(lab, k)
        self.kind.setCurrentIndex(max(0, self.kind.findData(self.spec.kind)))
        self.text = QLineEdit(self.spec.text)
        self.module = _spin(self.spec.module, 0.05, 50)
        self.height = _spin(self.spec.height, 0.5, 500)
        self.style = QComboBox()
        for k, lab in codes.STYLES:
            self.style.addItem(tr(lab), k)
        self.style.setCurrentIndex(max(0, self.style.findData(self.spec.style)))
        self.dot = _spin(self.spec.dot_ratio, 0.1, 1.0, suffix=' × module', decimals=2)
        self.level = QComboBox()
        for k, lab in B.QR_LEVELS:
            self.level.addItem(lab, k)
        self.level.setCurrentIndex(max(0, self.level.findData(self.spec.level)))
        self.shape = QComboBox()
        for k, lab in B.DM_SHAPES:
            self.shape.addItem(tr(lab), k)
        self.shape.setCurrentIndex(max(0, self.shape.findData(self.spec.shape)))
        self.checksum = QCheckBox(tr('Caractère de contrôle (Code 39)'))
        self.checksum.setChecked(self.spec.checksum)
        self.human = QCheckBox(tr('Texte lisible sous le code'))
        self.human.setChecked(self.spec.human)
        self.text_h = _spin(self.spec.text_height, 0.3, 100)
        self.invert = QCheckBox(tr('Inverser couleur (graver le fond autour du code)'))
        self.invert.setChecked(self.spec.invert)
        self.quiet = _spin(self.spec.quiet, 0.0, 20, suffix=tr(' module(s)'), decimals=1)
        self.info = QLabel('')
        self.info.setWordWrap(True)
        form.addRow(tr('Symbologie'), self.kind)
        form.addRow(tr('Contenu'), self.text)
        form.addRow(tr('Module (largeur de barre fine)'), self.module)
        form.addRow(tr('Hauteur des barres'), self.height)
        form.addRow(tr('Style (codes 2D)'), self.style)
        form.addRow(tr('Diamètre des points'), self.dot)
        form.addRow(tr('Correction QR'), self.level)
        form.addRow(tr('Forme DataMatrix'), self.shape)
        form.addRow(self.checksum)
        form.addRow(self.human)
        form.addRow(tr('Hauteur du texte'), self.text_h)
        form.addRow(self.invert)
        form.addRow(tr('Marge du négatif'), self.quiet)
        form.addRow(self.info)
        for w in (self.kind, self.style, self.level, self.shape):
            w.currentIndexChanged.connect(self._update)
        self.text.textChanged.connect(self._update)
        self.module.valueChanged.connect(self._update)
        self.checksum.toggled.connect(self._update)
        _buttons(self, form)
        self._ok = self.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Ok)
        self._update()
        self.text.setFocus()

    def result_spec(self):
        from ..core import codes
        return codes.BarcodeSpec(
            kind=self.kind.currentData(), text=self.text.text(), module=self.module.value(),
            height=self.height.value(), style=self.style.currentData(), dot_ratio=self.dot.value(),
            level=self.level.currentData(), shape=self.shape.currentData(),
            checksum=self.checksum.isChecked(), human=self.human.isChecked(),
            font=self.spec.font, text_height=self.text_h.value(), invert=self.invert.isChecked(),
            quiet=self.quiet.value())

    def _update(self) -> None:
        from ..core import barcode as B
        from ..core import codes
        kind = self.kind.currentData()
        linear = B.is_linear(kind)
        for w in (self.height, self.human, self.text_h):
            w.setEnabled(linear)
        for w in (self.style, self.dot):
            w.setEnabled(not linear)
        self.level.setEnabled(kind == 'qr')
        self.shape.setEnabled(kind == 'datamatrix')
        self.checksum.setEnabled(kind == 'code39')
        spec = self.result_spec()
        try:
            m = codes.matrix(spec)
        except B.CodeError as ex:
            self.info.setText(str(ex))
            self.info.setStyleSheet('color: #a33;')
            self._ok.setEnabled(False)
            return
        except Exception as ex:                     # donnée vide ou hors capacité
            self.info.setText(str(ex) or tr('Contenu à saisir'))
            self.info.setStyleSheet('color: #a33;')
            self._ok.setEnabled(False)
            return
        w = len(m[0]) * spec.module
        h = spec.height if linear else len(m) * spec.module
        self.info.setStyleSheet('color: #1f3d73;')
        self.info.setText(tr('{0} × {1} modules — {2:.2f} × {3:.2f} mm').format(len(m[0]), len(m), w, h))
        self._ok.setEnabled(bool(spec.text))


class ArcTextDialog(QDialog):
    """Texte en arc, par la distance cordale, par le centre et le rayon ou par
    deux angles, sur la ligne de base ou dessous, dans quatre directions."""

    def __init__(self, parent=None, *, font='Arial', height=5.0, radius=30.0, text='', center=(0.0, 0.0), spacing=0.0,
                 method='circle', position='top', side='outside', chord=1.0, start=135.0, end=45.0):
        super().__init__(parent)
        from .fit import no_hscroll
        no_hscroll(self)                                 # pas de défilement horizontal à l'ouverture
        self.setWindowTitle(tr('Texte en arc'))
        form = QFormLayout(self)
        from PySide6.QtWidgets import QLineEdit
        self.text = QLineEdit(text)
        self.font = FontBox()
        self.font.setCurrentFont(QFont(font))
        self.height = _spin(height, 0.05, 2000)
        self.radius = _spin(radius, 0.1, 100000)
        self.position = QComboBox()
        self.position.addItem(tr('En haut du cercle'), 'top')
        self.position.addItem(tr('En bas du cercle'), 'bottom')
        self.position.addItem(tr('À droite, de haut en bas'), 'right')
        self.position.addItem(tr('À gauche, de bas en haut'), 'left')
        self.position.addItem(tr('En bas, renversé'), 'under')
        self.position.setCurrentIndex(max(0, self.position.findData(position)))
        self.side = QComboBox()
        self.side.addItem(tr('Sur la ligne de base'), 'outside')
        self.side.addItem(tr('Sous la ligne de base'), 'inside')
        self.side.setCurrentIndex(max(0, self.side.findData(side)))
        self.spacing = _spin(spacing, -100, 100)
        self.method = QComboBox()
        self.method.addItem(tr('Distance cordale'), 'chord')
        self.method.addItem(tr('Centre et rayon'), 'circle')
        self.method.addItem(tr('Angles de départ et d\'arrivée'), 'angles')
        self.method.setCurrentIndex(max(0, self.method.findData(method)))
        self.chord = _spin(chord, 0.001, 100000)
        self.chord.setToolTip(tr('Distance entre le sommet de l\'arc et la ligne de base, sur toute la longueur du texte'))
        self.cx = _spin(center[0], -1000000, 1000000)
        self.cy = _spin(center[1], -1000000, 1000000)
        self.start = _spin(start, -3600, 3600, decimals=2)
        self.end = _spin(end, -3600, 3600, decimals=2)
        self.start.setToolTip(tr('Le texte va en sens horaire de l\'angle de départ à l\'angle d\'arrivée, et les remplit'))
        self.end.setToolTip(self.start.toolTip())
        form.addRow(tr('Texte'), self.text)
        form.addRow(tr('Police'), self.font)
        form.addRow(tr('Hauteur des capitales'), self.height)
        form.addRow(tr('Interlettrage'), self.spacing)
        form.addRow(tr('Méthode'), self.method)
        form.addRow(tr('Position'), self.position)
        form.addRow(tr('Côté'), self.side)
        form.addRow(tr('Distance cordale'), self.chord)
        form.addRow(tr('Centre X'), self.cx)
        form.addRow(tr('Centre Y'), self.cy)
        form.addRow(tr('Rayon du cercle'), self.radius)
        form.addRow(tr('Angle de départ (°)'), self.start)
        form.addRow(tr('Angle d\'arrivée (°)'), self.end)
        _buttons(self, form)
        self.method.currentIndexChanged.connect(lambda _i: self._refresh())
        self._refresh()
        self.text.setFocus()

    def _refresh(self) -> None:
        m = self.method.currentData()
        self.chord.setEnabled(m == 'chord')
        self.position.setEnabled(m != 'angles')
        self.spacing.setEnabled(m != 'angles')           # l'interlettrage remplit l'arc
        for w in (self.cx, self.cy, self.radius):
            w.setEnabled(m != 'chord')
        for w in (self.start, self.end):
            w.setEnabled(m == 'angles')

    def values(self) -> dict:
        return {'text': self.text.text(), 'font': self.font.currentFont().family(),
                'height': self.height.value(), 'radius': self.radius.value(),
                'position': self.position.currentData(), 'side': self.side.currentData(),
                'spacing': self.spacing.value(), 'method': self.method.currentData(), 'chord': self.chord.value(),
                'center': (self.cx.value(), self.cy.value()), 'start': self.start.value(), 'end': self.end.value()}


class BoxTextDialog(QDialog):
    """Texte dans un rectangle : la hauteur est calculée pour que tout le
    texte tienne dans le cadre (étirement facultatif pour remplir la largeur)."""

    def __init__(self, parent=None, *, text='', font='Arial', align='center', line_spacing=1.2,
                 stretch=False, width=None, height=None, compress=True):
        super().__init__(parent)
        from .fit import no_hscroll
        no_hscroll(self)                                 # pas de défilement horizontal à l'ouverture
        self.setWindowTitle(tr('Texte dans un rectangle'))
        form = QFormLayout(self)
        self.text = QPlainTextEdit(text)
        self.text.setMinimumHeight(80)
        self.font = FontBox()
        self.font.setCurrentFont(QFont(font))
        self.align = QComboBox()
        for k, label in (('left', tr('Gauche')), ('center', tr('Centré')), ('right', tr('Droite')),
                         ('justify', tr('Justifié'))):
            self.align.addItem(label, k)
        self.align.setCurrentIndex(max(0, self.align.findData(align)))
        self.line = _spin(line_spacing, 0.5, 5, suffix=tr(' × corps'), decimals=2)
        self.fit = QComboBox()
        self.fit.addItem(tr('Comprimer les lettres pour garder la hauteur du cadre'), 'compress')
        self.fit.addItem(tr('Réduire le texte pour qu\'il tienne'), 'reduce')
        self.fit.addItem(tr('Étirer les lettres pour remplir la largeur'), 'stretch')
        self.fit.setCurrentIndex(self.fit.findData('stretch' if stretch else 'compress' if compress else 'reduce'))
        from ..core.text import SPRING
        self.spring_text = SPRING
        self.text.setTabChangesFocus(False)
        self.text.installEventFilter(self)
        self.text.setToolTip(tr('Tab : un ressort {0}, qui partage l\'espace libre de la ligne').format(SPRING))
        form.addRow(tr('Texte'), self.text)
        form.addRow(tr('Police'), self.font)
        form.addRow(tr('Alignement'), self.align)
        form.addRow(tr('Interligne'), self.line)
        form.addRow(tr('Ajustement'), self.fit)
        self.w = self.h = None
        if width is not None:
            self.w = _spin(width, 0.1, 100000)
            self.h = _spin(height, 0.1, 100000)
            form.addRow(tr('Largeur du cadre'), self.w)
            form.addRow(tr('Hauteur du cadre'), self.h)
        _buttons(self, form)
        self.text.setFocus()

    def eventFilter(self, obj, ev) -> bool:
        from PySide6.QtCore import QEvent
        if obj is self.text and ev.type() == QEvent.Type.KeyPress and ev.key() == Qt.Key.Key_Tab:
            self.text.insertPlainText(self.spring_text)
            return True
        return super().eventFilter(obj, ev)

    def values(self) -> dict:
        v = {'text': self.text.toPlainText(), 'font': self.font.currentFont().family(),
             'align': self.align.currentData(), 'line_spacing': self.line.value(),
             'stretch': self.fit.currentData() == 'stretch', 'compress': self.fit.currentData() == 'compress'}
        if self.w is not None:
            v['width'], v['height'] = self.w.value(), self.h.value()
        return v


class BrailleDialog(QDialog):
    """Braille : texte, cotes des points ; transcription affichée pour relecture."""

    def __init__(self, parent=None, spec=None):
        super().__init__(parent)
        from .fit import no_hscroll
        no_hscroll(self)                                 # pas de défilement horizontal à l'ouverture
        from PySide6.QtWidgets import QLabel
        from ..core import braille as BR
        self.setWindowTitle(tr('Braille'))
        self.spec = spec or BR.BrailleSpec()
        form = QFormLayout(self)
        self.text = QPlainTextEdit(self.spec.text)
        self.text.setMinimumHeight(70)
        self.dot = _spin(self.spec.dot, 0.2, 10)
        self.dot_pitch = _spin(self.spec.dot_pitch, 0.5, 20)
        self.cell_pitch = _spin(self.spec.cell_pitch, 1, 50)
        self.line_pitch = _spin(self.spec.line_pitch, 1, 100)
        self.capitals = QCheckBox(tr('Signaler les majuscules'))
        self.capitals.setChecked(self.spec.capitals)
        self.preview = QLabel('')
        self.preview.setWordWrap(True)
        f = self.preview.font()
        f.setPointSize(16)
        self.preview.setFont(f)
        self.info = QLabel(tr('Faire relire la transcription par un lecteur braille avant fabrication.'))
        self.info.setWordWrap(True)
        self.info.setStyleSheet('color: #a33;')
        form.addRow(tr('Texte'), self.text)
        form.addRow(tr('Diamètre des points'), self.dot)
        form.addRow(tr('Écart entre points'), self.dot_pitch)
        form.addRow(tr('Écart entre cellules'), self.cell_pitch)
        form.addRow(tr('Écart entre lignes'), self.line_pitch)
        form.addRow(self.capitals)
        form.addRow(tr('Transcription'), self.preview)
        form.addRow(self.info)
        _buttons(self, form)
        self._ok = self.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Ok)
        self.text.textChanged.connect(self._update)
        self.capitals.toggled.connect(self._update)
        self._update()
        self.text.setFocus()

    def result_spec(self):
        from ..core import braille as BR
        return BR.BrailleSpec(text=self.text.toPlainText(), dot=self.dot.value(),
                              dot_pitch=self.dot_pitch.value(), cell_pitch=self.cell_pitch.value(),
                              line_pitch=self.line_pitch.value(), capitals=self.capitals.isChecked())

    def _update(self) -> None:
        from ..core import braille as BR
        try:
            self.preview.setText(BR.unicode_braille(self.text.toPlainText(), capitals=self.capitals.isChecked()))
            self.preview.setStyleSheet('')
            self._ok.setEnabled(bool(self.text.toPlainText().strip()))
        except BR.BrailleError as ex:
            self.preview.setText(str(ex))
            self.preview.setStyleSheet('color: #a33; font-size: 10pt;')
            self._ok.setEnabled(False)


class HalftoneDialog(QDialog):
    """Photo : image, largeur, pas et style de trame."""

    def __init__(self, parent=None, spec=None):
        super().__init__(parent)
        from .fit import no_hscroll
        no_hscroll(self)                                 # pas de défilement horizontal à l'ouverture
        from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QToolButton
        from ..core import halftone as HT
        self.setWindowTitle(tr('Photo (trame)'))
        self.spec = spec or HT.HalftoneSpec()
        form = QFormLayout(self)
        row = QHBoxLayout()
        self.source = QLineEdit(self.spec.source)
        b = QToolButton()
        b.setText('…')
        b.clicked.connect(self._browse)
        row.addWidget(self.source, 1)
        row.addWidget(b)
        self.width = _spin(self.spec.width, 1, 5000)
        self.pitch = _spin(self.spec.pitch, 0.05, 20)
        self.style = QComboBox()
        self.style.addItem(tr('Points (aire selon la densité)'), 'dots')
        self.style.addItem(tr('Lignes (épaisseur selon la densité)'), 'lines')
        self.style.setCurrentIndex(max(0, self.style.findData(self.spec.style)))
        self.gamma = _spin(self.spec.gamma, 0.2, 5, suffix='', decimals=2)
        self.invert = QCheckBox(tr('Inverser (la gravure éclaircit)'))
        self.invert.setChecked(self.spec.invert)
        self.min_size = _spin(self.spec.min_size, 0, 5)
        self.info = QLabel('')
        form.addRow(tr('Image'), row)
        form.addRow(tr('Largeur'), self.width)
        form.addRow(tr('Pas de la trame'), self.pitch)
        form.addRow(tr('Style'), self.style)
        form.addRow(tr('Gamma'), self.gamma)
        form.addRow(self.invert)
        form.addRow(tr('Taille minimale gravée'), self.min_size)
        form.addRow(self.info)
        _buttons(self, form)
        for w in (self.width, self.pitch):
            w.valueChanged.connect(self._update)
        self.source.textChanged.connect(self._update)
        self._update()

    def _browse(self) -> None:
        from PySide6.QtWidgets import QFileDialog
        f, _ = QFileDialog.getOpenFileName(self, tr('Image'), self.source.text(),
                                           tr('Images (*.png *.jpg *.jpeg *.bmp *.tif *.tiff *.gif)'))
        if f:
            self.source.setText(f)

    def _update(self) -> None:
        from PySide6.QtGui import QImageReader
        size = QImageReader(self.source.text()).size()
        if size.width() <= 0:
            self.info.setText(tr('Choisir une image.'))
            return
        cols = round(self.width.value() / self.pitch.value())
        rows = round(cols * size.height() / size.width())
        self.info.setText(tr('{0} × {1} px → {2} × {3} cellules, {4:.1f} × {5:.1f} mm').format(
            size.width(), size.height(), cols, rows, cols * self.pitch.value(), rows * self.pitch.value()))

    def result_spec(self):
        from ..core import halftone as HT
        return HT.HalftoneSpec(width=self.width.value(), pitch=self.pitch.value(),
                               style=self.style.currentData(), gamma=self.gamma.value(),
                               invert=self.invert.isChecked(), min_size=self.min_size.value(),
                               source=self.source.text())


class FontBox(QComboBox):
    """Choix de police : les polices monotrait intégrées (VD Trait, VD Géo), celles
    que lisent les plugins, les polices SVG, puis celles du système. Même
    interface que QFontComboBox. La liste dépliée (`fontlist.FontPopup`) : haute
    comme la fenêtre, avec une recherche, des filtres et les favorites."""

    #: au plus une recherche de polices nouvelles par intervalle (s), à l'ouverture de la liste
    CHECK_S = 2.0

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self._checked = -1e9
        self._popup = None
        self._fill()

    def _add(self, name: str, kind: str, tip: str | None = None, group: str = '') -> None:
        from .fontlist import GROUP_ROLE, KIND_ROLE
        self.addItem(name)
        i = self.count() - 1
        self.setItemData(i, kind, KIND_ROLE)
        if tip:
            self.setItemData(i, tip, Qt.ItemDataRole.ToolTipRole)
        if group:                                          # filtre de son format (« TypeEdit ») dans la liste
            self.setItemData(i, group, GROUP_ROLE)

    def _fill(self) -> None:
        from PySide6.QtGui import QFontDatabase
        from ..core import fonts, strokegeo
        self._gen = fonts.generation()
        for m in fonts.BUILTIN:
            self._add(m.NAME, 'integree',
                      tr('Police monotrait intégrée, linéale géométrique : traits ouverts, gravés en un passage')
                      if m is strokegeo else tr('Police monotrait intégrée : traits ouverts, gravés en un passage'))
        self.insertSeparator(self.count())
        from ..core import fontformats
        gv = fonts.plugin_families()
        qt = list(QFontDatabase.families())                 # celles du système que Qt connaît depuis son lancement,
        others = sorted(qt + fonts.unlisted_families(qt), key=str.lower)     # et les TrueType arrivées depuis
        plugin = set(gv)
        # TrueType rangées avec les polices d'un format qui a son filtre (livrées avec TypeEdit) : sous ce filtre
        tt = {n: g for n in others if n not in plugin and (g := fonts.group_of(n))}
        for n in sorted([*gv, *tt], key=str.lower):
            if n in tt:
                self._add(n, 'plugin', tr('Police TrueType livrée avec les polices {0}').format(tr(tt[n])), tt[n])
                continue
            fmt = fontformats.of(fonts.PLUGIN_FONTS.get(n, ''))
            self._add(n, 'plugin', tr(fmt.label) if fmt is not None else tr('Police lue par un plugin'),
                      fmt.filter_label if fmt is not None else '')
        if gv or tt:
            self.insertSeparator(self.count())
        svg = fonts.svg_families()
        for n in svg:
            self._add(n, 'svg', tr('Police SVG'))
        if svg:
            self.insertSeparator(self.count())
        for n in others:
            if n not in tt:
                self._add(n, 'systeme')

    def reload(self) -> None:
        """La liste refaite (polices installées depuis), le choix et le texte tapé gardés, sans signal."""
        text = self.currentText()
        was = self.blockSignals(True)
        try:
            self.clear()
            self._fill()
            self.setCurrentFont(text)
        finally:
            self.blockSignals(was)

    def showPopup(self) -> None:                           # noqa: N802 (API Qt)
        """Une police installée depuis le remplissage de la liste y est. La liste : `fontlist.FontPopup` (haute comme
        la fenêtre, recherche, filtres, favorites)."""
        import time
        from ..core import fonts
        now = time.monotonic()
        if now - self._checked >= self.CHECK_S:
            self._checked = now
            try:
                fonts.rescan()
            except OSError:                                # dossier de polices illisible : la liste telle quelle
                pass
        if fonts.generation() != self._gen:
            self.reload()
        if self._popup is None:
            from .fontlist import FontPopup
            self._popup = FontPopup(self)                  # rattachée à la fenêtre : partie avec elle, ou avec nous
            self._popup.picked.connect(self._picked)
            self._popup.destroyed.connect(self._popup_gone)
            self.destroyed.connect(self._popup.deleteLater)
        self._popup.open_for()

    def _popup_gone(self, *_a) -> None:
        self._popup = None

    def hidePopup(self) -> None:                           # noqa: N802 (API Qt)
        if self._popup is not None and self._popup.isVisible():
            self._popup.hide()
        super().hidePopup()

    def _picked(self, name: str) -> None:
        """Une police choisie dans la liste : comme un choix dans la liste de Qt (`activated`, `textActivated`, et
        `currentTextChanged` si elle change). Le focus n'est pas repris : la barre de texte le rend au dessin pendant
        une saisie."""
        i = self.findText(name, Qt.MatchFlag.MatchExactly | Qt.MatchFlag.MatchCaseSensitive)
        if i < 0:
            i = self.findText(name, Qt.MatchFlag.MatchFixedString)
        if i < 0:
            return
        self.setCurrentIndex(i)
        self.setEditText(self.itemText(i))
        self.activated.emit(i)
        self.textActivated.emit(self.itemText(i))

    def setCurrentFont(self, f) -> None:
        name = f.family() if hasattr(f, 'family') else str(f)
        i = self.findText(name, Qt.MatchFlag.MatchFixedString)
        if i >= 0:
            self.setCurrentIndex(i)
        else:
            self.setEditText(name)

    def currentFont(self):
        return QFont(self.currentText())


def load_gray(path: str):
    """Image → niveaux de gris numpy (0 noir … 1 blanc), ligne 0 en haut ;
    la transparence compte comme du blanc."""
    from ..io import raster
    img, _orig, _note = raster.load_image(path)          # grandes images comprises (limite de Qt levée)
    return qimage_gray(img)


def qimage_gray(img, max_side: int = 0):
    """QImage → niveaux de gris numpy (0 noir … 1 blanc) ; réduite si son
    plus grand côté dépasse `max_side` (0 : jamais)."""
    import numpy as np
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QColor, QImage, QPainter
    if max_side and max(img.width(), img.height()) > max_side:
        img = img.scaled(max_side, max_side, Qt.AspectRatioMode.KeepAspectRatio,
                         Qt.TransformationMode.SmoothTransformation)
    light = light_on_transparent(img)                # dessin clair sans fond : posé sur du noir, puis inversé
    flat = QImage(img.size(), QImage.Format.Format_RGB32)
    flat.fill(QColor('black' if light else 'white'))
    p = QPainter(flat)
    p.drawImage(0, 0, img)
    p.end()
    g = flat.convertToFormat(QImage.Format.Format_Grayscale8)
    arr = np.frombuffer(g.constBits(), np.uint8, g.sizeInBytes()).reshape(g.height(), g.bytesPerLine())
    out = arr[:, :g.width()].astype(float) / 255.0
    return 1.0 - out if light else out


def qimage_rgb(img, max_side: int = 0):
    """QImage → (couleurs numpy 0…1, pixels réels : faux où l'image est transparente) ; réduite si son plus grand côté
    dépasse `max_side` (0 : jamais)."""
    import numpy as np
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QImage
    if max_side and max(img.width(), img.height()) > max_side:
        img = img.scaled(max_side, max_side, Qt.AspectRatioMode.KeepAspectRatio,
                         Qt.TransformationMode.SmoothTransformation)
    a = img.convertToFormat(QImage.Format.Format_RGBA8888)
    arr = np.frombuffer(a.constBits(), np.uint8, a.sizeInBytes()).reshape(a.height(), a.bytesPerLine())
    px = arr[:, :a.width() * 4].reshape(a.height(), a.width(), 4)
    return px[..., :3].astype(float) / 255.0, px[..., 3] >= 128


def light_on_transparent(img) -> bool:
    """Image à fond transparent dont le dessin est clair (blanc sur rien) :
    invisible sur fond blanc, à vectoriser d'après sa forme."""
    import numpy as np
    from PySide6.QtGui import QImage
    if img is None or img.isNull() or not img.hasAlphaChannel():
        return False
    a = img
    if max(a.width(), a.height()) > 400:
        from PySide6.QtCore import Qt
        a = a.scaled(400, 400, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.FastTransformation)
    a = a.convertToFormat(QImage.Format.Format_ARGB32)
    arr = np.frombuffer(a.constBits(), np.uint8, a.sizeInBytes()).reshape(a.height(), a.bytesPerLine() // 4, 4)
    arr = arr[:, :a.width()].astype(float)
    alpha = arr[..., 3] / 255.0
    if alpha.size == 0 or (alpha < 0.5).mean() < 0.05 or alpha.sum() < 1:
        return False                                 # presque pas de transparence
    lum = (0.299 * arr[..., 2] + 0.587 * arr[..., 1] + 0.114 * arr[..., 0]) / 255.0   # octets B, V, R, A
    return float((lum * alpha).sum() / alpha.sum()) > 0.75

