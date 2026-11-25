"""Ctrl+P, Imprimer : ce qu'il faut imprimer (la sélection, la plaque et ce qu'elle contient, des calques, tout le
dessin, ou la page BAT), où (l'imprimante ou un fichier PDF), sur quelle feuille (A6 à A1, Letter ; en PDF : la taille
réelle du dessin), à quelle échelle (ajustée à la feuille à l'échelle normalisée conseillée, ajustée, 1:1, zoom au
choix), l'orientation et la marge. L'échelle obtenue est montrée avant d'imprimer."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout, QLabel,
                               QListWidget, QListWidgetItem)

from ..i18n import tr

#: formats de feuille proposés (ceux de `printing.PAGE_IDS`), puis la taille réelle (PDF)
FORMATS = ('A6', 'A5', 'A4', 'A3', 'A2', 'A1', 'Letter')
REAL = 'reelle'
#: dans l'ordre demandé (réponse du 14/11) : la sélection, la page BAT, la plaque, tout ; puis les calques au choix
WHAT = (('selection', 'La sélection'), ('bat', 'La page BAT (bon à tirer)'),
        ('plaque', 'La plaque et ce qu’elle contient'), ('tout', 'Tout le dessin'), ('calques', 'Des calques'))
SCALES = (('conseillee', 'Ajustée à la feuille, à l’échelle conseillée'), ('ajuster', 'Ajustée à la feuille'),
          ('1', '1:1 (taille réelle)'), ('zoom', 'Zoom au choix'))


def _num(v, default: float) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):                   # choix retenu abîmé : la valeur d'office
        return default


def items_for(doc, selection, v: dict):
    """Les objets à imprimer selon `v` (`PrintDialog.values`) : la sélection, ceux des calques choisis (visibles), ou
    None (la plaque, tout le dessin : le dessin visible)."""
    if v.get('quoi') == 'selection':
        return list(selection)
    if v.get('quoi') == 'calques':
        ids = set(v.get('calques') or [])
        from ..cam.fixture import is_plate_layer         # plaque de reprise posée : jamais imprimée (question 43)
        return [it for L in doc.layers if L.id in ids and not is_plate_layer(L) for it in L.items if it.visible]
    return None


def override_for(v: dict) -> dict:
    """Les réglages d'impression du dessin (`printing.print_drawing`) que la fenêtre impose pour cette fois — tous ceux
    qui comptent, pour que l'échelle montrée soit celle imprimée (ni la mosaïque ni la réduction de F10) : un zoom trop
    grand pour la feuille est réduit ; la taille réelle n'est jamais réduite."""
    q = v.get('quoi') or 'tout'
    real = v.get('format') == REAL
    scale = str(v.get('echelle') or 'conseillee')
    if real:
        scale = '1'
    elif scale == 'zoom':
        scale = repr(max(0.0001, _num(v.get('zoom'), 100.0) / 100.0))
    return {'quoi': q, 'selection': q == 'selection', 'plaque': bool(v.get('plaque', True)),
            'format': v.get('format') or 'A4', 'orientation': 'auto' if real else (v.get('orientation') or 'auto'),
            'echelle': scale, 'marge': max(0.0, _num(v.get('marge'), 10.0)), 'position': 'centre',
            'reduire': not real, 'mosaique': False, 'couleurs': bool(v.get('couleurs', False))}


class PrintDialog(QDialog):
    """La fenêtre Imprimer (Ctrl+P). `last` : les choix de la fois d'avant (`values`)."""

    def __init__(self, parent, doc, selection, last: dict | None = None):
        super().__init__(parent)
        from .fit import no_hscroll
        no_hscroll(self)
        self.doc, self.selection = doc, list(selection or [])
        last = dict(last or {})
        self.setWindowTitle(tr('Imprimer'))
        form = QFormLayout(self)
        self.what = QComboBox()
        for k, label in WHAT:
            if k != 'plaque' or doc.plate is not None:   # sans plaque : pas de « la plaque »
                self.what.addItem(tr(label), k)
        default = 'selection' if self.selection else ('plaque' if doc.plate is not None else 'tout')
        want = last.get('quoi') or default
        if (want == 'selection' and not self.selection) or self.what.findData(want) < 0:
            want = default                               # sans sélection, sans plaque, choix abîmé : d'office
        self.what.setCurrentIndex(max(0, self.what.findData(want)))
        form.addRow(tr('Imprimer'), self.what)
        self.layers = QListWidget()
        self.layers.setMaximumHeight(110)
        saved = last.get('calques')
        chosen = set(saved if isinstance(saved, list) else []) & {L.id for L in doc.layers}   # un autre dessin : ses visibles
        from ..cam.fixture import is_plate_layer
        for L in doc.layers:
            if is_plate_layer(L):                        # plaque de reprise posée : pas proposée (question 43)
                continue
            it = QListWidgetItem(L.name or L.id)
            it.setData(Qt.ItemDataRole.UserRole, L.id)
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            it.setCheckState(Qt.CheckState.Checked if (L.id in chosen if chosen else L.visible)
                             else Qt.CheckState.Unchecked)
            self.layers.addItem(it)
        form.addRow(tr('Calques'), self.layers)
        self.output = QComboBox()
        self.output.addItem(tr('L’imprimante'), 'imprimante')
        self.output.addItem(tr('Un fichier PDF'), 'pdf')
        self.output.setCurrentIndex(max(0, self.output.findData(last.get('sortie') or 'imprimante')))
        form.addRow(tr('Vers'), self.output)
        self.format = QComboBox()
        for f in FORMATS:
            self.format.addItem(f, f)
        self.format.addItem(tr('Taille réelle du dessin (PDF)'), REAL)
        self.format.setCurrentIndex(max(0, self.format.findData(last.get('format') or 'A4')))
        form.addRow(tr('Feuille'), self.format)
        self.orientation = QComboBox()
        for k, label in (('auto', tr('Selon le dessin')), ('portrait', tr('Portrait')), ('paysage', tr('Paysage'))):
            self.orientation.addItem(label, k)
        self.orientation.setCurrentIndex(max(0, self.orientation.findData(last.get('orientation') or 'auto')))
        form.addRow(tr('Orientation'), self.orientation)
        self.scale = QComboBox()
        for k, label in SCALES:
            self.scale.addItem(tr(label), k)
        self.scale.setCurrentIndex(max(0, self.scale.findData(last.get('echelle') or 'conseillee')))
        self.scale.setToolTip(tr('Échelle conseillée : la plus grande échelle normalisée (1:1, 1:2, 1:5, 2:1…) qui tient '
                                 'sur la feuille'))
        form.addRow(tr('Échelle'), self.scale)
        self.zoom = QDoubleSpinBox()
        self.zoom.setRange(1.0, 10000.0)
        self.zoom.setDecimals(1)
        self.zoom.setSuffix(' %')
        self.zoom.setValue(_num(last.get('zoom'), 100.0) or 100.0)
        form.addRow(tr('Zoom'), self.zoom)
        self.margin = QDoubleSpinBox()
        self.margin.setRange(0.0, 60.0)
        self.margin.setDecimals(1)
        self.margin.setSuffix(' mm')
        self.margin.setValue(_num(last.get('marge'), 10.0))
        form.addRow(tr('Marge'), self.margin)
        self.plate = QCheckBox(tr('La plaque en pointillés'))
        self.plate.setChecked(bool(last.get('plaque', True)))
        form.addRow(self.plate)
        self.colors = QCheckBox(tr('En couleurs (celles des outils)'))   # demande du 24/11 ; décochée : en noir
        self.colors.setToolTip(tr('Traits et aplats à la couleur de leur outil, comme « Couleurs » (Ctrl+8) à '
                                  'l’écran ; décochée : tout en noir'))
        self.colors.setChecked(bool(last.get('couleurs', False)))
        form.addRow(self.colors)
        self.info = QLabel()
        self.info.setWordWrap(True)
        form.addRow(self.info)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.button(QDialogButtonBox.StandardButton.Ok).setText(tr('Imprimer…'))
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        form.addRow(bb)
        self.output.currentIndexChanged.connect(self._output_changed)
        self.format.currentIndexChanged.connect(self._format_changed)
        for box in (self.what, self.orientation, self.scale):
            box.currentIndexChanged.connect(self.update_info)
        for spin in (self.zoom, self.margin):
            spin.valueChanged.connect(self.update_info)
        self.plate.toggled.connect(self.update_info)
        self.layers.itemChanged.connect(self.update_info)
        if self.format.currentData() == REAL and self.output.currentData() != 'pdf':
            self.format.setCurrentIndex(self.format.findData('A4'))
        self.update_info()

    def _output_changed(self, *_a) -> None:
        if self.output.currentData() != 'pdf' and self.format.currentData() == REAL:
            self.format.setCurrentIndex(self.format.findData('A4'))      # l'imprimante n'a que ses feuilles
        self.update_info()

    def _format_changed(self, *_a) -> None:
        if self.format.currentData() == REAL and self.output.currentData() != 'pdf':
            self.output.setCurrentIndex(self.output.findData('pdf'))
        self.update_info()

    def values(self) -> dict:
        return {'quoi': self.what.currentData(), 'calques': [self.layers.item(i).data(Qt.ItemDataRole.UserRole)
                                                             for i in range(self.layers.count())
                                                             if self.layers.item(i).checkState() == Qt.CheckState.Checked],
                'sortie': self.output.currentData(), 'format': self.format.currentData(),
                'orientation': self.orientation.currentData(), 'echelle': self.scale.currentData(),
                'zoom': self.zoom.value(), 'marge': self.margin.value(), 'plaque': self.plate.isChecked(),
                'couleurs': self.colors.isChecked()}

    def update_info(self, *_a) -> str:
        """L'échelle et la feuille obtenues, montrées sous les réglages ; rend le texte."""
        from ..io.proof import scale_label
        from . import printing
        v = self.values()
        q = v['quoi']
        bat = q == 'bat'
        self.layers.setEnabled(q == 'calques')
        for w in (self.format, self.orientation, self.scale, self.margin, self.output):
            w.setEnabled(not bat)
        self.zoom.setEnabled(not bat and v['echelle'] == 'zoom' and v['format'] != REAL)
        self.scale.setEnabled(not bat and v['format'] != REAL)
        self.orientation.setEnabled(not bat and v['format'] != REAL)   # la taille réelle : la feuille suit le dessin
        self.plate.setEnabled(q in ('plaque', 'tout', 'calques'))
        self.colors.setEnabled(not bat)                  # la page BAT : ses couleurs à elle
        if bat:
            text = tr('La page BAT : sa fenêtre suit (format, orientation, échelle)')
        else:
            items = items_for(self.doc, self.selection, v)
            o = override_for(v)
            bb, _plate = printing.extent(self.doc, o, items)
            if not bb or items == []:
                text = tr('Rien à imprimer')
            elif v['format'] == REAL:
                m = o['marge']
                text = tr('Échelle 1:1 — feuille de {0:.0f} × {1:.0f} mm').format(bb[2] - bb[0] + 2 * m,
                                                                                bb[3] - bb[1] + 2 * m)
            else:
                pw, ph = printing.sheet_mm(v['format'], o['orientation'], bb)
                k, _asked, tiles = printing.fit_scale(o, bb, pw, ph)
                text = tr('Échelle {0} ({1} %) — {2} {3}').format(
                    scale_label(k), f'{100 * k:.0f}', v['format'], tr('paysage') if pw > ph else tr('portrait'))
                if tiles:
                    text += ' — ' + tr('{0} feuilles (mosaïque)').format(len(tiles))
        self.info.setText(text)
        return text
