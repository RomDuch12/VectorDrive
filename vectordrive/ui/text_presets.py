"""Préréglages de texte, comme TypeEdit 13 : la mise en forme complète d'un texte enregistrée sous un nom — police,
hauteur, largeur, interlettrage, interligne, alignement, espacement des lettres, inclinaison, souligné, petites
majuscules, sens de l'écriture (et ce qu'un texte enregistré avait de plus : ligne de base, longueur maximale).

Rangés dans les réglages (`texte/styles` : les « styles de texte » d'avant y sont déjà) ; le format des nouveaux textes
est gardé à part (`texte/format`) : un préréglage choisi s'applique aux textes sélectionnés et devient celui des
nouveaux textes (`texte/preset` : son nom). Le gestionnaire (`PresetsDialog`) les crée, les modifie champ par champ,
les renomme, les duplique, les supprime, les importe et les exporte (JSON)."""
from __future__ import annotations

import copy
import json
import math

from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDoubleSpinBox, QFileDialog, QFormLayout, QHBoxLayout,
                               QInputDialog, QLabel, QListWidget, QMessageBox, QPushButton, QVBoxLayout, QWidget)

from ..i18n import tr

KEY = 'texte/styles'
#: format des nouveaux textes (JSON : {'attrs': …, 'extra': …})
FORMAT_KEY = 'texte/format'
#: nom du préréglage des nouveaux textes
CURRENT = 'texte/preset'
#: alignements et espacements proposés (clé, libellé)
ALIGNS = (('left', 'Gauche'), ('center', 'Centré'), ('right', 'Droite'), ('justify', 'Justifié'))
SPACINGS = (('typo', 'Typographique'), ('prop', 'Proportionnel'), ('tight_kern', 'Serré avec crénage'),
            ('tight', 'Serré'), ('fixed', 'Chasse fixe'))


def load(settings) -> dict:
    """{nom : format} des préréglages enregistrés."""
    try:
        got = json.loads(str(settings.value(KEY, '{}') or '{}'))
    except ValueError:
        got = {}
    return {str(k): norm(v) for k, v in got.items() if valid(v)} if isinstance(got, dict) else {}


def valid(fmt) -> bool:
    return isinstance(fmt, dict) and isinstance(fmt.get('attrs'), dict)


def _num(v, default=None):
    """Nombre fini lu de `v`, sinon `default` (un booléen n'est pas un nombre)."""
    if isinstance(v, bool):
        return default
    try:
        f = float(v)
    except (TypeError, ValueError, OverflowError):      # OverflowError : entier démesuré d'un fichier importé
        return default
    return f if math.isfinite(f) else default


def norm(fmt: dict) -> dict:
    """Un format complet et sain : {'attrs': …, 'extra': …} (un fichier importé peut n'avoir que les attributs). Seuls
    les champs de mise en forme restent, et seulement avec une valeur lisible : une valeur illisible est écartée (celle
    par défaut la remplace)."""
    a_in = fmt.get('attrs') if isinstance(fmt.get('attrs'), dict) else {}
    e_in = fmt.get('extra') if isinstance(fmt.get('extra'), dict) else {}
    a = {}
    if isinstance(a_in.get('font'), str) and a_in['font'].strip():
        a['font'] = a_in['font'].strip()
    for k, positive in (('size', True), ('width_ratio', True), ('spacing', False), ('line_spacing', True)):
        v = _num(a_in.get(k))
        if v is not None and (v > 0 or not positive):
            a[k] = v
    if isinstance(a_in.get('align'), str) and a_in['align'] in dict(ALIGNS):
        a['align'] = a_in['align']
    e = {}
    v = _num(e_in.get('italic'))
    if v is not None:
        e['italic'] = max(-75.0, min(75.0, v))
    if isinstance(e_in.get('spacing_mode'), str) and e_in['spacing_mode'] in dict(SPACINGS):
        e['spacing_mode'] = e_in['spacing_mode']
    u = e_in.get('underline')
    if u is True or isinstance(u, dict):
        e['underline'] = copy.deepcopy(u)
    for k in ('small_caps', 'rtl'):
        if e_in.get(k) is True:
            e[k] = True
    b = e_in.get('baseline')
    if isinstance(b, dict) and _num(b.get('offset', 0.0) or 0.0) is not None:
        e['baseline'] = copy.deepcopy(b)
    m = e_in.get('max_length')
    if isinstance(m, dict) and (_num(m.get('length')) or 0.0) > 0:
        e['max_length'] = copy.deepcopy(m)
    lm = e_in.get('line_mode')
    if isinstance(lm, dict) and isinstance(lm.get('mode'), str) and lm['mode'] in ('fixed', 'prop', 'typo') and \
            _num(lm.get('value', 0.0) or 0.0) is not None:
        e['line_mode'] = copy.deepcopy(lm)
    return {'attrs': a, 'extra': e}


def same(a: dict, b: dict) -> bool:
    """Même mise en forme : les champs du ruban et du gestionnaire, et le reste des styles enregistrés (souligné :
    mis ou non)."""
    if values(a) != values(b):
        return False
    ea, eb = dict(a.get('extra') or {}), dict(b.get('extra') or {})
    ea.pop('underline', None)
    eb.pop('underline', None)
    return ea == eb


def save(settings, presets: dict) -> None:
    settings.setValue(KEY, json.dumps(presets, ensure_ascii=False))


def base_format(settings) -> dict:
    """Format de départ : police et hauteur par défaut (F10 › Texte), le reste tel qu'un nouveau texte."""
    try:
        size = float(settings.value('texte/hauteur', 5.0))
    except (TypeError, ValueError):
        size = 5.0
    return {'attrs': {'font': str(settings.value('texte/police', 'Arial') or 'Arial'), 'size': size,
                      'width_ratio': 1.0, 'spacing': 0.0, 'line_spacing': 1.2, 'align': 'left'}, 'extra': {}}


def new_text_format(settings) -> dict:
    """Format des nouveaux textes : celui gardé (préréglage choisi, valeurs du ruban sans texte sélectionné), sinon le
    format de départ."""
    fmt = base_format(settings)
    try:
        got = json.loads(str(settings.value(FORMAT_KEY, '') or 'null'))
    except ValueError:
        got = None
    if valid(got):
        got = norm(got)
        fmt['attrs'].update(got['attrs'])
        fmt['extra'] = got['extra']
    return fmt


def set_new_text_format(settings, fmt: dict, name: str | None = None) -> None:
    """Le format des nouveaux textes (et la police, la hauteur par défaut des fenêtres de texte) ; `name` : le
    préréglage d'où il vient ('' : aucun, None : inchangé)."""
    settings.setValue(FORMAT_KEY, json.dumps(fmt, ensure_ascii=False))
    a = fmt.get('attrs') or {}
    if a.get('font'):
        settings.setValue('texte/police', a['font'])
    if _num(a.get('size')):
        settings.setValue('texte/hauteur', _num(a['size']))
    if name is not None:
        settings.setValue(CURRENT, name)


def with_value(fmt: dict, field: str, value) -> dict:
    """Une copie du format, `field` changé (champs du ruban et du gestionnaire : font, size, width (%), spacing,
    line_spacing, align, spacing_mode, italic (°, 0 : droit), underline, small_caps, rtl)."""
    out = copy.deepcopy(fmt)
    a, e = out.setdefault('attrs', {}), out.setdefault('extra', {})
    if field in ('font', 'size', 'spacing', 'line_spacing', 'align'):
        a[field] = value
        if field == 'line_spacing':
            e.pop('line_mode', None)                     # la valeur donnée remplace le mode d'interligne
    elif field == 'width':
        a['width_ratio'] = float(value) / 100.0
    elif field == 'width_ratio':
        a['width_ratio'] = float(value)
    elif field == 'spacing_mode':
        if value and value != 'typo':
            e['spacing_mode'] = value
        else:
            e.pop('spacing_mode', None)
    elif field == 'italic':
        if abs(float(value or 0.0)) > 1e-9:
            e['italic'] = float(value)
        else:
            e.pop('italic', None)
    elif field in ('underline', 'small_caps', 'rtl'):
        if value:
            if field != 'underline' or not e.get('underline'):
                e[field] = True
        else:
            e.pop(field, None)
    return out


def values(fmt: dict) -> dict:
    """Les champs d'un format, pour le ruban et le gestionnaire."""
    a, e = fmt.get('attrs') or {}, fmt.get('extra') or {}
    return {'font': str(a.get('font') or 'Arial'), 'size': _num(a.get('size'), 5.0),
            'width': _num(a.get('width_ratio'), 1.0) * 100.0, 'spacing': _num(a.get('spacing'), 0.0),
            'line_spacing': _num(a.get('line_spacing'), 1.2), 'align': a.get('align', 'left'),
            'spacing_mode': e.get('spacing_mode', 'typo'), 'italic': _num(e.get('italic'), 0.0),
            'underline': bool(e.get('underline')), 'small_caps': bool(e.get('small_caps')), 'rtl': bool(e.get('rtl'))}


def describe(fmt: dict) -> str:
    """« Arial, 5 mm, 100 %, interlettrage 0, interligne 1,2 » et les styles."""
    v = values(fmt)
    parts = [v['font'], f"{v['size']:g} mm", f"{v['width']:g} %"]
    if v['spacing']:
        parts.append(tr('interlettrage {0:g} mm').format(v['spacing']))
    parts.append(tr('interligne {0:g}').format(v['line_spacing']))
    if v['italic']:
        parts.append(tr('inclinaison {0:g}°').format(v['italic']))
    for k, label in (('underline', tr('souligné')), ('small_caps', tr('petites majuscules')), ('rtl', tr('de droite à gauche'))):
        if v[k]:
            parts.append(label)
    return ', '.join(parts)


class PresetsDialog(QDialog):
    """Gestionnaire des préréglages de texte : la liste à gauche, tous les champs du préréglage choisi à droite (chaque
    changement est enregistré), les commandes dessous."""

    def __init__(self, win):
        super().__init__(win)
        from .dialogs import FontBox
        from .fit import no_hscroll
        no_hscroll(self)
        self.win = win
        self.settings = win.settings
        self.presets = load(self.settings)
        self._loading = False
        self.setWindowTitle(tr('Préréglages de texte'))
        self.setSizeGripEnabled(True)
        lay = QVBoxLayout(self)
        top = QHBoxLayout()
        self.list = QListWidget()
        self.list.setMinimumWidth(200)
        self.list.currentTextChanged.connect(lambda _t: self._show())
        self.list.itemDoubleClicked.connect(lambda _i: self.apply_to_selection())
        top.addWidget(self.list, 1)
        form_box = QWidget()
        form = QFormLayout(form_box)
        self.w = {}
        self.w['font'] = FontBox()
        self.w['font'].activated.connect(lambda _i: self._edit('font'))
        self.w['font'].lineEdit().editingFinished.connect(lambda: self._edit('font'))
        form.addRow(tr('Police'), self.w['font'])
        for field, label, lo, hi, dec, suffix in (('size', tr('Hauteur des capitales'), 0.05, 2000, 3, ' mm'),
                                                  ('width', tr('Largeur des lettres'), 10, 1000, 1, ' %'),
                                                  ('spacing', tr('Interlettrage'), -100, 100, 3, ' mm'),
                                                  ('line_spacing', tr('Interligne'), 0.3, 10, 2, ' ×'),
                                                  ('italic', tr('Inclinaison (0 : droit)'), -75, 75, 1, ' °')):
            sb = QDoubleSpinBox()
            sb.setRange(lo, hi)
            sb.setDecimals(dec)
            sb.setSuffix(suffix)
            sb.setKeyboardTracking(False)
            sb.valueChanged.connect(lambda _v, f=field: self._edit(f))
            self.w[field] = sb
            form.addRow(label, sb)
        for field, label, items in (('align', tr('Alignement'), ALIGNS), ('spacing_mode', tr('Espacement'), SPACINGS)):
            cb = QComboBox()
            for k, text in items:
                cb.addItem(tr(text), k)
            cb.currentIndexChanged.connect(lambda _i, f=field: self._edit(f))
            self.w[field] = cb
            form.addRow(label, cb)
        for field, label in (('underline', tr('Souligné')), ('small_caps', tr('Petites majuscules')),
                             ('rtl', tr('De droite à gauche'))):
            ch = QCheckBox(label)
            ch.toggled.connect(lambda _on, f=field: self._edit(f))
            self.w[field] = ch
            form.addRow('', ch)
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        form.addRow(self.summary)
        top.addWidget(form_box, 2)
        lay.addLayout(top, 1)
        row = QHBoxLayout()
        for label, tip, slot in ((tr('Nouveau…'), tr('Un préréglage d’après le premier texte sélectionné, sinon '
                                                     'd’après le format des nouveaux textes'), self.new_preset),
                                 (tr('Dupliquer'), tr('Une copie du préréglage choisi'), self.duplicate),
                                 (tr('Renommer…'), '', self.rename),
                                 (tr('Supprimer'), '', self.delete),
                                 (tr('Importer…'), tr('Préréglages d’un fichier JSON (ceux du même nom sont remplacés)'),
                                  self.import_file),
                                 (tr('Exporter…'), tr('Tous les préréglages dans un fichier JSON'), self.export_file)):
            b = QPushButton(label)
            if tip:
                b.setToolTip(tip)
            b.clicked.connect(lambda _=False, s=slot: s())
            row.addWidget(b)
        lay.addLayout(row)
        row = QHBoxLayout()
        b = QPushButton(tr('Appliquer à la sélection'))
        b.setToolTip(tr('Le préréglage choisi sur les textes sélectionnés (double-clic dans la liste aussi)'))
        b.clicked.connect(lambda: self.apply_to_selection())
        row.addWidget(b)
        b = QPushButton(tr('Pour les nouveaux textes'))
        b.setToolTip(tr('Les nouveaux textes prendront ce préréglage'))
        b.clicked.connect(lambda: self.use_for_new())
        row.addWidget(b)
        row.addStretch(1)
        b = QPushButton(tr('Fermer'))
        b.clicked.connect(self.accept)
        row.addWidget(b)
        lay.addLayout(row)
        self.resize(720, 460)
        self.refill(str(self.settings.value(CURRENT, '') or ''))

    # --- liste ----------------------------------------------------------------------------
    def refill(self, current: str = '') -> None:
        self.list.blockSignals(True)
        self.list.clear()
        names = sorted(self.presets, key=str.casefold)
        self.list.addItems(names)
        self.list.blockSignals(False)
        if names:
            self.list.setCurrentRow(names.index(current) if current in names else 0)
        self._show()

    def current(self) -> str:
        it = self.list.currentItem()
        return it.text() if it is not None else ''

    def _show(self) -> None:
        name = self.current()
        fmt = self.presets.get(name)
        for w in self.w.values():
            w.setEnabled(fmt is not None)
        if fmt is None:
            self.summary.setText(tr('Aucun préréglage : « Nouveau… » en crée un.'))
            return
        v = values(fmt)
        self._loading = True
        try:
            from PySide6.QtGui import QFont
            self.w['font'].setCurrentFont(QFont(v['font']))
            self.w['font'].setEditText(v['font'])
            for k in ('size', 'width', 'spacing', 'line_spacing', 'italic'):
                self.w[k].setValue(v[k])
            for k in ('align', 'spacing_mode'):
                self.w[k].setCurrentIndex(max(0, self.w[k].findData(v[k])))
            for k in ('underline', 'small_caps', 'rtl'):
                self.w[k].setChecked(v[k])
        finally:
            self._loading = False
        self.summary.setText(describe(fmt))

    def _edit(self, field: str) -> None:
        """Un champ changé : le préréglage choisi le prend, enregistré aussitôt."""
        name = self.current()
        if self._loading or name not in self.presets:
            return
        w = self.w[field]
        value = (w.currentText().strip() if field == 'font' else w.currentData() if isinstance(w, QComboBox)
                 else w.isChecked() if isinstance(w, QCheckBox) else w.value())
        if field == 'font' and not value:
            return
        self.presets[name] = with_value(self.presets[name], field, value)
        save(self.settings, self.presets)
        self.summary.setText(describe(self.presets[name]))
        if str(self.settings.value(CURRENT, '') or '') == name:        # préréglage des nouveaux textes : suivi
            set_new_text_format(self.settings, self.presets[name])
        self._sync_ribbon()

    def _sync_ribbon(self) -> None:
        """Les onglets Mise en forme (VectorDrive, TypeEdit 13) montrent les préréglages et les valeurs à jour."""
        refresh = getattr(self.win, 'refresh_text_bars', None)
        if refresh is not None:
            refresh()

    # --- commandes ------------------------------------------------------------------------
    def _unique(self, name: str) -> str:
        base, k = name.strip() or tr('Préréglage'), 2
        out = base
        while out in self.presets:
            out = f'{base} ({k})'
            k += 1
        return out

    def new_preset(self, name: str | None = None) -> str:
        """Un préréglage d'après le premier texte sélectionné (sinon le format des nouveaux textes) ; rend son nom."""
        from ..core import text as TX
        from .textbar import selected_texts
        texts = selected_texts(self.win)
        fmt = TX.text_format(texts[0]) if texts else new_text_format(self.settings)
        if name is None:
            name, ok = QInputDialog.getText(self, tr('Préréglages de texte'), tr('Nom du préréglage'),
                                            text=self._unique(values(fmt)['font']))
            if not ok or not name.strip():
                return ''
        name = self._unique(name)
        self.presets[name] = norm(fmt)
        save(self.settings, self.presets)
        self.refill(name)
        self._sync_ribbon()
        return name

    def duplicate(self) -> str:
        name = self.current()
        if name not in self.presets:
            return ''
        new = self._unique(name)
        self.presets[new] = copy.deepcopy(self.presets[name])
        save(self.settings, self.presets)
        self.refill(new)
        self._sync_ribbon()
        return new

    def rename(self, new: str | None = None) -> str:
        name = self.current()
        if name not in self.presets:
            return ''
        if new is None:
            new, ok = QInputDialog.getText(self, tr('Renommer le préréglage'), tr('Nouveau nom'), text=name)
            if not ok:
                return ''
        new = new.strip()
        if not new or new == name:
            return ''
        new = self._unique(new)
        self.presets[new] = self.presets.pop(name)
        save(self.settings, self.presets)
        if str(self.settings.value(CURRENT, '') or '') == name:
            self.settings.setValue(CURRENT, new)
        self.refill(new)
        self._sync_ribbon()
        return new

    def delete(self) -> bool:
        name = self.current()
        if self.presets.pop(name, None) is None:
            return False
        save(self.settings, self.presets)
        if str(self.settings.value(CURRENT, '') or '') == name:
            self.settings.setValue(CURRENT, '')
        self.refill()
        self._sync_ribbon()
        return True

    def export_file(self, path: str | None = None) -> int:
        if path is None:
            path, _f = QFileDialog.getSaveFileName(self, tr('Exporter les préréglages de texte'),
                                                   'prereglages_texte.json', 'JSON (*.json)')
            if not path:
                return 0
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump({'format': 'VectorDrive préréglages de texte', 'version': 1, 'prereglages': self.presets},
                          f, ensure_ascii=False, indent=1)
        except OSError as ex:
            QMessageBox.warning(self, tr('Préréglages de texte'), tr('Enregistrement impossible : {0}').format(ex))
            return 0
        return len(self.presets)

    def import_file(self, path: str | None = None) -> int:
        if path is None:
            path, _f = QFileDialog.getOpenFileName(self, tr('Importer des préréglages de texte'), '', 'JSON (*.json)')
            if not path:
                return 0
        try:
            with open(path, encoding='utf-8') as f:
                data = json.load(f)
        except (OSError, ValueError) as ex:
            QMessageBox.warning(self, tr('Préréglages de texte'), tr('Fichier illisible : {0}').format(ex))
            return 0
        got = data.get('prereglages', data) if isinstance(data, dict) else {}
        n = 0
        for name, fmt in (got.items() if isinstance(got, dict) else ()):
            if valid(fmt):
                self.presets[str(name)] = norm(fmt)
                n += 1
        if n:
            save(self.settings, self.presets)
            cur = str(self.settings.value(CURRENT, '') or '')
            if cur in self.presets:                      # préréglage des nouveaux textes remplacé : suivi
                set_new_text_format(self.settings, self.presets[cur])
            self.refill(self.current())
            self._sync_ribbon()
        return n

    def apply_to_selection(self) -> int:
        name = self.current()
        return self.win.use_text_preset(name) if name in self.presets else 0

    def use_for_new(self) -> bool:
        name = self.current()
        if name not in self.presets:
            return False
        set_new_text_format(self.settings, self.presets[name], name)
        self._sync_ribbon()
        self.win.statusBar().showMessage(tr('Nouveaux textes : préréglage « {0} »').format(name), 5000)
        return True


__all__ = ['PresetsDialog', 'load', 'save', 'valid', 'norm', 'same', 'new_text_format', 'set_new_text_format',
           'with_value', 'values', 'describe']
