"""Personnaliser l'interface : choisir un thème sur aperçu, en dupliquer un
pour en régler chaque couleur (interface et plan de travail), importer ou
exporter un fichier de thème (JSON)."""
from __future__ import annotations

import json

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (QCheckBox, QColorDialog, QComboBox, QDialog, QDialogButtonBox, QFileDialog,
                               QFontComboBox, QFormLayout, QHBoxLayout, QInputDialog, QLabel, QLineEdit,
                               QListWidget, QListWidgetItem, QMessageBox, QPushButton, QScrollArea, QTabWidget,
                               QToolButton, QVBoxLayout, QWidget)

from ..i18n import tr
from . import themes as T


def swatch_icon(t: T.Theme, w: int = 36, h: int = 16) -> QIcon:
    """Petite bande des couleurs du thème (listes, menus)."""
    pm = QPixmap(w, h)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    cols = T.swatches(t)
    sw = w / len(cols)
    for i, c in enumerate(cols):
        p.fillRect(QRectF(i * sw, 0, sw + 0.5, h), QColor(c))
    p.setPen(QPen(QColor('#808080'), 1))
    p.drawRect(QRectF(0.5, 0.5, w - 1, h - 1))
    p.end()
    return QIcon(pm)


class ColorButton(QWidget):
    """Couleur choisie, ou vide (« celle du thème »)."""
    changed = Signal(str)

    def __init__(self, value: str = '', *, allow_empty: bool = True, empty_text: str = '', parent=None):
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        self.button = QToolButton()
        self.button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.button.setMinimumWidth(120)
        self.button.clicked.connect(self.choose)
        row.addWidget(self.button, 1)
        self.allow_empty = allow_empty
        self.empty_text = empty_text or tr('celle du thème')
        self.reset = QToolButton()
        self.reset.setText('×')
        self.reset.setToolTip(tr('Revenir à la couleur du thème'))
        self.reset.clicked.connect(lambda: self.setValue('', emit=True))
        self.reset.setVisible(allow_empty)
        row.addWidget(self.reset)
        self._value = ''
        self.setValue(value)

    def value(self) -> str:
        return self._value

    def setValue(self, v, emit: bool = False) -> None:
        v = '' if v is None else str(v)
        if isinstance(v, str) and v and not T.is_fill(v):
            v = ''
        self._value = v
        if v:
            pm = QPixmap(28, 14)
            pm.fill(QColor(v.split(';')[0]))
            self.button.setIcon(QIcon(pm))
            self.button.setText(v)
        else:
            self.button.setIcon(QIcon())
            self.button.setText(self.empty_text)
        if emit:
            self.changed.emit(v)

    def choose(self) -> None:
        cur = QColor(self._value.split(';')[0]) if self._value else QColor('#808080')
        c = QColorDialog.getColor(cur, self, tr('Couleur'))
        if c.isValid():
            self.setValue(c.name(), emit=True)


class ThemePreview(QWidget):
    """Aperçu : ruban (onglets, légende, bouton coché), panneau, plan de
    travail (page, plaque, grille, objet sélectionné, aperçu)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.theme: T.Theme | None = None
        self.setMinimumSize(380, 230)

    def set_theme(self, t: T.Theme) -> None:
        self.theme = t
        self.update()

    def paintEvent(self, ev) -> None:
        t = self.theme
        if t is None:
            return
        c, cv = t.colors, t.canvas
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()
        p.fillRect(0, 0, W, H, QColor(c['main']))
        f = QFont(self.font())
        if t.font:
            f.setFamily(t.font)
        f.setPointSizeF(8)
        p.setFont(f)
        # onglets
        x = 6
        for i, name in enumerate((tr('Fichier'), tr('Edition'), tr('Vue'))):
            w = p.fontMetrics().horizontalAdvance(name) + 16
            r = QRectF(x, 4, w, 18)
            if i == 1:
                p.fillRect(r, QColor(c['tab_selected']))
                p.setPen(QColor(c['tab_selected_text']))
                if c.get('underline'):
                    p.fillRect(QRectF(x, 20, w, 2), QColor(c['underline']))
            else:
                if c.get('tab'):
                    p.fillRect(r, QColor(c['tab']))
                p.setPen(QColor(c.get('tab_text') or c['window_text']))
            p.drawText(r, Qt.AlignmentFlag.AlignCenter, name)
            x += w + 2
        # ruban
        rib = QRectF(0, 22, W, 58)
        p.fillRect(rib, QColor(c['ribbon']))
        p.setPen(QColor(c['border']))
        p.drawLine(rib.topLeft(), rib.topRight())
        for k, (bx, label) in enumerate(((10, 'A'), (46, 'B'), (82, 'C'))):
            br = QRectF(bx, 28, 30, 30)
            if k == 1:
                p.setBrush(QColor(c['checked']))
                p.setPen(QColor(c['checked_border']))
                p.drawRoundedRect(br, 3, 3)
            elif k == 2:
                p.setBrush(QColor(c['hover']))
                p.setPen(Qt.PenStyle.NoPen)
                p.drawRoundedRect(br, 3, 3)
            p.setPen(QPen(QColor(c['icon']), 2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(br.adjusted(8, 8, -8, -8))
        cap = QRectF(6, 62, 112, 15)
        if t.captions == 'bandeau':
            col = c['caption'].split(';')
            p.setBrush(QColor(col[0]))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(cap, 3, 3)
        p.setPen(QColor(c['caption_text']))
        p.drawText(cap, Qt.AlignmentFlag.AlignCenter, tr('Groupe'))
        p.setPen(QColor(c['info']))
        p.drawText(QRectF(W - 150, 30, 144, 16), Qt.AlignmentFlag.AlignRight, 'L 50.000  H 20.000')
        # panneau
        pan = QRectF(0, 80, 110, H - 80)
        p.fillRect(pan, QColor(c['window']))
        if c.get('panel_title'):
            p.fillRect(QRectF(0, 80, 110, 16), QColor(c['panel_title']))
            p.setPen(QColor(c.get('panel_title_text') or '#ffffff'))
        else:
            p.setPen(QColor(c['window_text']))
        p.drawText(QRectF(6, 80, 104, 16), Qt.AlignmentFlag.AlignVCenter, tr('Calques'))
        p.fillRect(QRectF(6, 100, 98, 18), QColor(c['base']))
        p.setPen(QColor(c['text']))
        p.drawText(QRectF(10, 100, 94, 18), Qt.AlignmentFlag.AlignVCenter, tr('Outil 1'))
        p.fillRect(QRectF(6, 120, 98, 18), QColor(c['highlight']))
        p.setPen(QColor(c['highlighted_text']))
        p.drawText(QRectF(10, 120, 94, 18), Qt.AlignmentFlag.AlignVCenter, tr('Outil 2'))
        p.setPen(QColor(c['disabled']))
        p.drawText(QRectF(10, 140, 94, 18), Qt.AlignmentFlag.AlignVCenter, tr('Outil 3'))
        # plan de travail
        area = QRectF(110, 80, W - 110, H - 80)
        if cv.get('ruler'):
            p.fillRect(QRectF(110, 80, W - 110, 10), QColor(cv['ruler']))
        p.fillRect(area.adjusted(0, 10 if cv.get('ruler') else 0, 0, 0), QColor(cv['bg']))
        page = QRectF(area.left() + 18, area.top() + 22, area.width() - 36, area.height() - 34)
        p.fillRect(page, QColor(cv['page']))
        g = QColor(*cv['grid'])
        p.setPen(QPen(g, 1))
        gx = page.left() + 12
        while gx < page.right():
            p.drawLine(int(gx), int(page.top()), int(gx), int(page.bottom()))
            gx += 12
        plate = page.adjusted(16, 14, -16, -14)
        p.setBrush(QColor(cv['plate']))
        p.setPen(QPen(QColor(cv['plate_edge']), 1))
        p.drawRect(plate)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(cv['selection']), 2))
        p.drawEllipse(QRectF(plate.left() + 14, plate.top() + 12, 46, 30))
        p.setPen(QPen(QColor(cv['preview']), 1))
        p.drawRect(QRectF(plate.left() + 78, plate.top() + 14, 50, 26))
        p.setPen(QPen(QColor(cv['frame']), 1, Qt.PenStyle.DashLine))
        p.drawRect(QRectF(plate.left() + 10, plate.top() + 8, 54, 38))
        p.setPen(QPen(QColor(cv['snap']), 1.6))
        p.drawEllipse(QRectF(plate.left() + 75, plate.top() + 11, 7, 7))
        p.end()


class ThemeEditor(QDialog):
    """Personnaliser l'interface."""

    def __init__(self, win, parent=None):
        super().__init__(parent or win)
        from .fit import no_hscroll
        no_hscroll(self)                                 # pas de défilement horizontal à l'ouverture
        self.win = win
        self.setWindowTitle(tr('Personnaliser l\'interface'))
        self.resize(900, 640)
        self.work: T.Theme | None = None
        self.dirty = False
        lay = QHBoxLayout(self)
        left = QVBoxLayout()
        self.list = QListWidget()
        self.list.setMinimumWidth(240)
        self.list.currentItemChanged.connect(lambda *_: self._select())
        self.list.itemDoubleClicked.connect(lambda *_: self.apply())
        left.addWidget(self.list, 1)
        row = QHBoxLayout()
        for text, slot in ((tr('Importer…'), self.import_file), (tr('Exporter…'), self.export_file)):
            b = QPushButton(text)
            b.clicked.connect(lambda _=False, s=slot: s())
            row.addWidget(b)
        left.addLayout(row)
        lay.addLayout(left)
        right = QVBoxLayout()
        self.preview = ThemePreview()
        right.addWidget(self.preview)
        self.info = QLabel('')
        self.info.setWordWrap(True)
        right.addWidget(self.info)
        row = QHBoxLayout()
        self.b_apply = QPushButton(tr('Appliquer'))
        self.b_apply.clicked.connect(self.apply)
        self.b_dup = QPushButton(tr('Dupliquer pour modifier…'))
        self.b_dup.clicked.connect(self.duplicate)
        self.b_save = QPushButton(tr('Enregistrer'))
        self.b_save.clicked.connect(self.save)
        self.b_del = QPushButton(tr('Supprimer'))
        self.b_del.clicked.connect(self.delete)
        for b in (self.b_apply, self.b_dup, self.b_save, self.b_del):
            row.addWidget(b)
        right.addLayout(row)
        self.tabs = QTabWidget()
        self.color_edits: dict[tuple[str, str], ColorButton] = {}
        self.tabs.addTab(self._general_page(), tr('Général'))
        self.tabs.addTab(self._colors_page('colors', T.COLOR_ROLES), tr('Interface'))
        self.tabs.addTab(self._colors_page('canvas', T.CANVAS_ROLES), tr('Plan de travail'))
        right.addWidget(self.tabs, 1)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        bb.rejected.connect(self.reject)
        right.addWidget(bb)
        lay.addLayout(right, 1)
        self.fill()

    # --- liste ---------------------------------------------------------------------
    def fill(self, select: str | None = None) -> None:
        cur = select or str(self.win.settings.value('vue/theme', T.DEFAULT_KEY) or T.DEFAULT_KEY)
        if cur == 'systeme':
            from .theme import current
            cur = current().key
        self.list.blockSignals(True)
        self.list.clear()
        allt = T.all_themes()
        groups = [(tr('Thèmes clairs'), [t for t in allt.values() if not t.dark and t.source in ('intégré', 'TypeEdit')]),
                  (tr('Thèmes sombres'), [t for t in allt.values() if t.dark and t.source in ('intégré', 'TypeEdit')]),
                  (tr('Thèmes des plugins'), [t for t in allt.values() if t.source == 'plugin']),
                  (tr('Mes thèmes'), [t for t in allt.values() if t.source == 'utilisateur'])]
        chosen = None
        for title, items in groups:
            if not items:
                continue
            head = QListWidgetItem(title)
            head.setFlags(Qt.ItemFlag.NoItemFlags)
            f = head.font()
            f.setBold(True)
            head.setFont(f)
            self.list.addItem(head)
            for t in items:
                it = QListWidgetItem(swatch_icon(t), tr(t.name))
                it.setData(Qt.ItemDataRole.UserRole, t.key)
                self.list.addItem(it)
                if t.key == cur:
                    chosen = it
        self.list.blockSignals(False)
        if chosen is None:
            chosen = next((self.list.item(i) for i in range(self.list.count())
                           if self.list.item(i).data(Qt.ItemDataRole.UserRole)), None)
        if chosen is not None:
            self.list.setCurrentItem(chosen)
        self._select()

    def current_key(self) -> str:
        it = self.list.currentItem()
        return (it.data(Qt.ItemDataRole.UserRole) or '') if it else ''

    def _select(self) -> None:
        key = self.current_key()
        if not key:
            return
        self.work = T.all_themes().get(key) or T.get(key)
        self.dirty = False
        self._load_fields()

    def _editable(self) -> bool:
        return self.work is not None and self.work.source == 'utilisateur'

    def _load_fields(self) -> None:
        t = self.work
        self.preview.set_theme(t)
        kind = tr('sombre') if t.dark else tr('clair')
        src = {'intégré': tr('thème intégré'), 'TypeEdit': tr('couleurs lues dans TypeEdit'),
               'plugin': tr('thème d\'un plugin'), 'utilisateur': tr('mon thème')}.get(t.source, t.source)
        note = '' if self._editable() else ' — ' + tr('dupliquez-le pour le modifier')
        self.info.setText(f'<b>{tr(t.name)}</b> ({kind}, {src}){note}')
        ed = self._editable()
        self.b_save.setEnabled(ed)
        self.b_del.setEnabled(ed)
        self.name.setText(tr(t.name))
        self.dark.setChecked(t.dark)
        self.font_on.setChecked(bool(t.font))
        self.font.setCurrentFont(QFont(t.font or self.font.font().family()))
        self.captions.setCurrentIndex(max(0, self.captions.findData(t.captions)))
        for (group, role), w in self.color_edits.items():
            src_d = t.colors if group == 'colors' else t.canvas
            v = src_d.get(role, '')
            if isinstance(v, tuple):
                v = T.hexa(*v[:3])
            w.setValue(v)
            w.setEnabled(ed)
        for w in (self.name, self.dark, self.font_on, self.font, self.captions):
            w.setEnabled(ed)

    # --- champs --------------------------------------------------------------------
    def _general_page(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        self.name = QLineEdit()
        self.name.textEdited.connect(lambda _t: self._changed())
        form.addRow(tr('Nom'), self.name)
        self.dark = QCheckBox(tr('Thème sombre (icônes, couleurs des outils éclaircies)'))
        self.dark.toggled.connect(lambda _on: self._changed())
        form.addRow(self.dark)
        self.font_on = QCheckBox(tr('Police propre au thème'))
        self.font_on.toggled.connect(lambda _on: self._changed())
        self.font = QFontComboBox()
        self.font.currentFontChanged.connect(lambda _f: self._changed())
        form.addRow(self.font_on, self.font)
        self.captions = QComboBox()
        self.captions.addItem(tr('Texte seul'), 'texte')
        self.captions.addItem(tr('Bandeau coloré (TypeEdit)'), 'bandeau')
        self.captions.currentIndexChanged.connect(lambda _i: self._changed())
        form.addRow(tr('Légendes des groupes du ruban'), self.captions)
        return page

    def _colors_page(self, group: str, roles: dict) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        for role, label in roles.items():
            w = ColorButton('', allow_empty=role in T.OPTIONAL, empty_text=tr('aucune'))
            w.changed.connect(lambda _v, g=group, r=role: self._color_changed(g, r))
            self.color_edits[(group, role)] = w
            form.addRow(tr(label), w)
        sc = QScrollArea()
        sc.setWidgetResizable(True)
        sc.setWidget(page)
        return sc

    def _color_changed(self, group: str, role: str) -> None:
        if not self._editable():
            return
        v = self.color_edits[(group, role)].value()
        t = self.work
        if group == 'colors':
            t.colors[role] = v
        else:
            t.canvas[role] = T._rgba(v, t.canvas['grid']) if role == 'grid' and v else v
        self.dirty = True
        self.preview.set_theme(t)

    def _changed(self) -> None:
        if not self._editable():
            return
        t = self.work
        t.name = self.name.text().strip() or t.name
        t.dark = self.dark.isChecked()
        t.font = self.font.currentFont().family() if self.font_on.isChecked() else ''
        t.captions = self.captions.currentData() or 'texte'
        self.dirty = True
        self.preview.set_theme(t)

    # --- actions ---------------------------------------------------------------------
    def apply(self) -> None:
        if self.dirty and self._editable():
            self.save()
        key = self.current_key()
        if key:
            self.win.set_theme(key)

    def duplicate(self) -> T.Theme | None:
        if self.work is None:
            return None
        name, ok = QInputDialog.getText(self, tr('Dupliquer le thème'), tr('Nom du nouveau thème'),
                                        text=tr('{0} (mien)').format(tr(self.work.name)))
        if not ok or not name.strip():
            return None
        return self._duplicate(name.strip())

    def _duplicate(self, name: str) -> T.Theme:
        t = self.work.copy(key=T.new_key(name), name=name, source='utilisateur')
        T.save_user(t)
        self.fill(select=t.key)
        return t

    def save(self) -> None:
        if not self._editable():
            return
        T.save_user(self.work)
        self.dirty = False
        key = self.work.key
        from .theme import current
        if current().key == key:
            self.win.set_theme(key)
        self.fill(select=key)

    def delete(self) -> None:
        if not self._editable():
            return
        key = self.work.key
        if QMessageBox.question(self, tr('Supprimer le thème'),
                                tr('Supprimer le thème « {0} » ?').format(self.work.name)) \
                != QMessageBox.StandardButton.Yes:
            return
        self._delete(key)

    def _delete(self, key: str) -> None:
        T.delete_user(key)
        if str(self.win.settings.value('vue/theme', '')) == key:
            self.win.set_theme(T.DEFAULT_KEY)
        self.fill()

    def import_file(self, path: str | None = None) -> T.Theme | None:
        if not path:
            path, _ = QFileDialog.getOpenFileName(self, tr('Importer un thème'), '', tr('Thème (*.json)'))
        if not path:
            return None
        try:
            with open(path, encoding='utf-8') as f:
                t = T.from_json(json.load(f))
        except (OSError, ValueError) as ex:
            QMessageBox.warning(self, tr('Importer un thème'), str(ex))
            return None
        if t.key in T.BUILTIN or t.key in T.all_themes():
            t = t.copy(key=T.new_key(t.name))
        T.save_user(t)
        self.fill(select=t.key)
        return t

    def export_file(self, path: str | None = None) -> str | None:
        if self.work is None:
            return None
        if not path:
            path, _ = QFileDialog.getSaveFileName(self, tr('Exporter le thème'), f'{self.work.key}.json',
                                                  tr('Thème (*.json)'))
        if not path:
            return None
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.work.to_json(), f, ensure_ascii=False, indent=1)
        return path
