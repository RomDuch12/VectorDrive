"""L'éditeur de polices : on dessine le caractère dans le dessin, la fenêtre reste ouverte à côté.
La sélection devient le caractère ; un caractère s'insère dans le dessin pour être repris."""
from __future__ import annotations

import pathlib
import xml.etree.ElementTree as ET

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap, QTransform
from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout,
                               QLabel, QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QPushButton, QVBoxLayout,
                               QWidget)

from ..core import fontedit as FE
from ..core import fonts
from ..core.combine import combine
from ..core.document import Shape
from ..core.geom import Path
from ..i18n import tr
from .canvas import to_qpath
from .dialogs import FontBox, _spin

SAMPLE = 'Hamburgefonstiv 123'


def _draw(painter: QPainter, path: Path, rect, margin: float, color) -> None:
    """Le tracé dans ce cadre, y vers le haut, à la plus grande échelle qui y tient. Sans remplissage :
    le o fermé d'une police monotrait reste un trait."""
    box = path.bbox()
    if box is None:
        return
    w, h = max(box[2] - box[0], 1e-6), max(box[3] - box[1], 1e-6)
    k = min((rect.width() - 2 * margin) / w, (rect.height() - 2 * margin) / h)
    if k <= 0:
        return
    ox = rect.x() + (rect.width() - w * k) / 2 - box[0] * k
    oy = rect.y() + (rect.height() + h * k) / 2 + box[1] * k
    q = to_qpath(path)
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setTransform(QTransform(k, 0, 0, -k, ox, oy), True)
    pen = QPen(color)
    pen.setCosmetic(True)
    painter.setPen(pen)
    painter.drawPath(q)
    painter.restore()


def glyph_icon(path: Path, size: int = 44) -> QIcon:
    pm = QPixmap(size, size)
    pm.fill(QColor('white'))
    p = QPainter(pm)
    _draw(p, path, pm.rect(), 4.0, QColor('black'))
    p.end()
    return QIcon(pm)


class Preview(QWidget):
    """Le texte d'essai dans le brouillon, avec ses chasses et son crénage."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.path = Path()
        self.setMinimumHeight(80)

    def show_path(self, path: Path) -> None:
        self.path = path
        self.update()

    def paintEvent(self, _ev) -> None:
        p = QPainter(self)
        p.fillRect(self.rect(), QColor('white'))
        _draw(p, self.path, self.rect(), 8.0, QColor('black'))
        p.end()


class CloneBox(QDialog):
    """Le choix de la police dont on repart."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle(tr('Reprendre une police'))
        form = QFormLayout(self)
        self.font_box = FontBox()
        form.addRow(tr('Police'), self.font_box)
        note = QLabel(tr('La copie reste soumise à la licence de la police d’origine. Son crénage n’est pas repris.'))
        note.setWordWrap(True)
        form.addRow(note)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        form.addRow(bb)


class FontEditor(QDialog):
    def __init__(self, win):
        super().__init__(win)
        self.win = win
        self.draft = FE.Draft()
        self.path: pathlib.Path | None = None
        self.dirty = False
        self._loading = False
        self.setWindowTitle(tr('Éditeur de polices'))
        self.setModal(False)
        self.resize(860, 640)
        lay = QVBoxLayout(self)

        top = QHBoxLayout()
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText(tr('Nom de la police'))
        self.name_edit.textEdited.connect(self._touch)
        top.addWidget(QLabel(tr('Nom')))
        top.addWidget(self.name_edit, 1)
        top.addWidget(self._button(tr('Nouvelle'), lambda: self.new_font()))
        top.addWidget(self._button(tr('Ouvrir…'), lambda: self.open_font()))
        top.addWidget(self._button(tr('Reprendre une police…'), lambda: self.clone_font()))
        top.addWidget(self._button(tr('Enregistrer'), lambda: self.save_font()))
        lay.addLayout(top)

        mid = QHBoxLayout()
        self.list = QListWidget()
        self.list.setViewMode(QListWidget.ViewMode.IconMode)
        self.list.setIconSize(QSize(44, 44))
        self.list.setGridSize(QSize(62, 70))
        self.list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.list.setMovement(QListWidget.Movement.Static)
        self.list.setMinimumWidth(320)
        self.list.currentItemChanged.connect(self._picked)
        mid.addWidget(self.list, 1)

        holder = QWidget()
        holder.setMaximumWidth(430)
        side = QVBoxLayout(holder)
        side.setContentsMargins(0, 0, 0, 0)
        add = QGroupBox(tr('Ajouter un caractère'))
        form = QFormLayout(add)
        self.char_edit = QLineEdit()
        self.char_edit.setMaxLength(2)                   # un caractère hors du plan de base compte pour deux en Qt
        self.char_edit.setToolTip(tr('Le caractère à ajouter, tel qu’on le tapera : attention aux majuscules et minuscules'))
        self.char_edit.textChanged.connect(self._char_changed)
        self.code_label = QLabel()
        row = QHBoxLayout()
        row.addWidget(self.char_edit)
        row.addWidget(self.code_label)
        form.addRow(tr('Caractère'), row)
        self.place = QComboBox()
        self.place.addItem(tr('Sur la ligne de base'))
        self.place.addItem(tr('À sa place depuis l’origine du dessin'))
        self.place.setToolTip(tr('Sur la ligne de base : le coin bas gauche de la sélection se pose à zéro. '
                                 'Depuis l’origine : pour un g ou une virgule, qui descendent ; dessinez-le alors à sa place.'))
        form.addRow(tr('Position'), self.place)
        self.before = _spin(0.0, -1000.0, 1000.0)
        self.before.setToolTip(tr('L’espace qui précède le caractère, sur la ligne de base'))
        form.addRow(tr('Espace avant'), self.before)
        self.after = _spin(10.0, -1000.0, 1000.0)
        self.after.setToolTip(tr('L’espace qui suit le caractère'))
        form.addRow(tr('Espace après'), self.after)
        self.cap_mm = _spin(100.0, 1.0, 10000.0)
        self.cap_mm.setToolTip(tr('La hauteur de capitale dans le dessin : 100 mm conseillés. Elle donne l’échelle de tout le reste'))
        self.cap_mm.valueChanged.connect(lambda _=0.0: self._refresh_values())
        form.addRow(tr('Hauteur de capitale'), self.cap_mm)
        form.addRow(self._button(tr('Ajouter la sélection'), lambda: self.add_selection()))
        side.addWidget(add)

        cur = QGroupBox(tr('Caractère choisi'))
        form = QFormLayout(cur)
        self.adv_box = _spin(0.0, -10000.0, 10000.0)
        self.adv_box.setToolTip(tr('La place que prend le caractère dans le texte : de son origine au caractère suivant'))
        self.adv_box.editingFinished.connect(self.set_adv)
        form.addRow(tr('Chasse'), self.adv_box)
        row = QHBoxLayout()
        self.insert_button = self._button(tr('Insérer dans le dessin'), lambda: self.insert_glyph())
        self.delete_button = self._button(tr('Supprimer'), lambda: self.delete_glyph())
        row.addWidget(self.insert_button)
        row.addWidget(self.delete_button)
        form.addRow(row)
        side.addWidget(cur)

        kern = QGroupBox(tr('Crénage'))
        form = QFormLayout(kern)
        self.pair_edit = QLineEdit()
        self.pair_edit.setMaxLength(4)
        self.pair_edit.setToolTip(tr('Les deux caractères de la paire, par exemple AV'))
        form.addRow(tr('Paire'), self.pair_edit)
        self.kern_box = _spin(0.0, -10000.0, 10000.0)
        self.kern_box.setToolTip(tr('Négatif : rapproche les deux caractères. Zéro retire la paire'))
        form.addRow(tr('Décalage'), self.kern_box)
        form.addRow(self._button(tr('Appliquer à la paire'), lambda: self.apply_kern()))
        self.kern_list = QListWidget()
        self.kern_list.setMaximumHeight(90)
        self.kern_list.currentItemChanged.connect(self._kern_picked)
        form.addRow(self.kern_list)
        side.addWidget(kern)
        side.addStretch(1)
        mid.addWidget(holder)
        lay.addLayout(mid, 1)

        self.sample = QLineEdit(SAMPLE)
        self.sample.setToolTip(tr('Un texte d’essai, posé avec les chasses et le crénage de la police'))
        self.sample.textChanged.connect(lambda _='': self._refresh_preview())
        lay.addWidget(self.sample)
        self.preview = Preview()
        lay.addWidget(self.preview)
        bottom = QHBoxLayout()
        self.info = QLabel()
        bottom.addWidget(self.info, 1)
        bottom.addWidget(self._button(tr('Fermer'), self.close))
        lay.addLayout(bottom)
        self._refresh_all()

    @staticmethod
    def _button(text: str, slot) -> QPushButton:
        b = QPushButton(text)
        b.setAutoDefault(False)                          # Entrée dans un champ ne doit rien déclencher
        b.clicked.connect(lambda _=False: slot())
        return b

    # --- état ---------------------------------------------------------------------------------

    def _touch(self, *_a) -> None:
        self.dirty = True

    def _take(self, draft: FE.Draft, path, dirty: bool) -> None:
        self.draft, self.path, self.dirty = draft, pathlib.Path(path) if path else None, dirty
        self._loading = True
        self.name_edit.setText(draft.name)
        self._loading = False
        self._refresh_all()

    def char(self) -> str | None:
        ch = self.char_edit.text()
        return ch if FE.valid_char(ch) else None

    def current_code(self) -> int | None:
        it = self.list.currentItem()
        return it.data(Qt.ItemDataRole.UserRole) if it is not None else None

    def _select(self, code: int | None) -> None:
        for i in range(self.list.count()):
            if self.list.item(i).data(Qt.ItemDataRole.UserRole) == code:
                self.list.setCurrentRow(i)
                return

    # --- affichage ----------------------------------------------------------------------------

    def _refresh_all(self, keep: int | None = None) -> None:
        self.list.blockSignals(True)
        self.list.clear()
        for code in sorted(self.draft.glyphs):
            it = QListWidgetItem(glyph_icon(self.draft.glyph_units(code)), chr(code) if chr(code) != ' ' else tr('espace'))
            it.setData(Qt.ItemDataRole.UserRole, code)
            it.setToolTip(f'U+{code:04X}')
            self.list.addItem(it)
        self.list.blockSignals(False)
        self._select(keep)
        self._refresh_kern()
        self._refresh_values()
        self._refresh_preview()
        self.info.setText(tr('{0} caractères').format(len(self.draft.glyphs)))

    def _refresh_kern(self) -> None:
        self.kern_list.blockSignals(True)
        self.kern_list.clear()
        cap = self.cap_mm.value()
        for (a, b) in sorted(self.draft.kern):
            it = QListWidgetItem(f'{chr(a)}{chr(b)}   {self.draft.kern_mm(a, b, cap):.3f}')
            it.setData(Qt.ItemDataRole.UserRole, (a, b))
            self.kern_list.addItem(it)
        self.kern_list.blockSignals(False)

    def _refresh_values(self) -> None:
        code = self.current_code()
        self._loading = True
        on = code is not None and code in self.draft.glyphs
        self.adv_box.setEnabled(on)
        self.insert_button.setEnabled(on)
        self.delete_button.setEnabled(on)
        self.adv_box.setValue(self.draft.adv_mm(code, self.cap_mm.value()) if on else 0.0)
        self._loading = False

    def _refresh_preview(self) -> None:
        self.preview.show_path(self.draft.text_units(self.sample.text()))

    def _picked(self, *_a) -> None:
        code = self.current_code()
        if code is not None:
            self.char_edit.setText(chr(code))
        self._refresh_values()

    def _kern_picked(self, *_a) -> None:
        it = self.kern_list.currentItem()
        if it is None:
            return
        a, b = it.data(Qt.ItemDataRole.UserRole)
        self.pair_edit.setText(chr(a) + chr(b))
        self.kern_box.setValue(self.draft.kern_mm(a, b, self.cap_mm.value()))

    def _char_changed(self, text: str) -> None:
        self.code_label.setText(f'U+{ord(text):04X}' if FE.valid_char(text) else '')

    # --- police -------------------------------------------------------------------------------

    def ask_discard(self) -> bool:
        """Vrai si l'on peut quitter la police en cours ; on propose de l'enregistrer si elle a changé."""
        if not self.dirty:
            return True
        name = self.name_edit.text().strip() or tr('sans nom')
        got = QMessageBox.question(self, self.windowTitle(), tr('Enregistrer la police « {0} » ?').format(name),
                                   QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard
                                   | QMessageBox.StandardButton.Cancel)
        if got == QMessageBox.StandardButton.Save:
            return self.save_font()
        return got == QMessageBox.StandardButton.Discard

    def new_font(self) -> None:
        if self.ask_discard():
            self._take(FE.Draft(), None, False)

    def open_font(self, path: str | None = None) -> bool:
        if not self.ask_discard():
            return False
        title = tr('Ouvrir une police')
        if path is None:
            folder = fonts.user_font_dir()
            start = str(folder) if folder.is_dir() else self.win._last_dir('police')
            path, _ = QFileDialog.getOpenFileName(self, title, start, tr('Polices SVG (*.svg)'))
            if not path:
                return False
        try:
            draft = FE.load(path)
        except (OSError, ValueError, ET.ParseError):
            QMessageBox.information(self, title, tr('Ce fichier SVG ne contient pas de police.'))
            return False
        self.win._remember_dir('police', path)
        self._take(draft, path, False)
        return True

    def clone_font(self, name: str | None = None) -> bool:
        if not self.ask_discard():
            return False
        title = tr('Reprendre une police')
        if name is None:
            box = CloneBox(self)
            if box.exec() != QDialog.DialogCode.Accepted:
                return False
            name = box.font_box.currentText().strip()
        if not FE.can_clone(name):
            QMessageBox.information(self, title, tr('Seule une police TrueType, OpenType ou SVG de cette machine peut être reprise.'))
            return False
        draft = FE.clone(name, tr('{0} copie').format(name))
        if not draft.glyphs:
            QMessageBox.information(self, title, tr('Cette police ne donne aucun caractère.'))
            return False
        self._take(draft, None, True)
        return True

    def save_font(self) -> bool:
        title = tr('Enregistrer')
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.information(self, title, tr('Donnez un nom à la police.'))
            self.name_edit.setFocus()
            return False
        if not self.draft.glyphs:
            QMessageBox.information(self, title, tr('La police n’a encore aucun caractère.'))
            return False
        folder = fonts.user_font_dir()
        mine = self.path if self.path is not None and FE.inside(self.path, folder) else None
        if FE.name_taken(name, mine):
            QMessageBox.information(self, title, tr('Une autre police porte déjà le nom « {0} » : chaque nom doit être unique.').format(name))
            self.name_edit.setFocus()
            return False
        target = mine or FE.file_for(name, folder)
        self.draft.name = name
        try:
            self.draft.save(target)
        except OSError as ex:
            QMessageBox.critical(self, title, str(ex))
            return False
        self.path, self.dirty = target, False
        fonts.font_changed()
        self.win.font_redrawn(name)
        self.info.setText(tr('Police « {0} » enregistrée : {1} caractères.').format(name, len(self.draft.glyphs)))
        return True

    # --- caractères ---------------------------------------------------------------------------

    def add_selection(self) -> bool:
        title = tr('Ajouter la sélection')
        ch = self.char()
        if ch is None:
            QMessageBox.information(self, title, tr('Tapez le caractère à ajouter : un seul.'))
            self.char_edit.setFocus()
            return False
        whole = combine(list(self.win.canvas.selection))
        path = whole.path if whole is not None else Path()
        if not path.contours and not ch.isspace():
            QMessageBox.information(self, title, tr('Sélectionnez le dessin du caractère.'))
            return False
        code = ord(ch)
        if code in self.draft.glyphs:
            got = QMessageBox.question(self, title, tr('Le caractère « {0} » existe déjà. Le remplacer ?').format(ch))
            if got != QMessageBox.StandardButton.Yes:
                return False
        cap = self.cap_mm.value()
        shape = FE.placed(path, self.place.currentIndex() == 0, self.before.value())
        box = shape.bbox()
        adv = max(box[2] + self.after.value(), 0.0) if box else cap * FE.SPACE_SHARE
        self.draft.put(code, shape, adv, cap)
        self.dirty = True
        self._refresh_all(keep=code)
        return True

    def insert_glyph(self) -> Shape | None:
        """Dans le dessin, à sa place depuis l'origine ; l'ajouter de nouveau le remplacera sans le déplacer."""
        code = self.current_code()
        if code is None:
            return None
        cap = self.cap_mm.value()
        path = self.draft.glyph_mm(code, cap)
        box = path.bbox()
        if box is None:
            QMessageBox.information(self, tr('Insérer dans le dessin'), tr('Ce caractère n’a pas de tracé.'))
            return None
        shape = Shape(path=path, name=chr(code), tool=self.win.canvas.current_tool_index)
        self.win._add_items([shape])
        self.place.setCurrentIndex(1)
        self.after.setValue(self.draft.adv_mm(code, cap) - box[2])
        return shape

    def delete_glyph(self) -> None:
        code = self.current_code()
        if code is None:
            return
        row = self.list.currentRow()
        self.draft.remove(code)
        self.dirty = True
        self._refresh_all()
        if self.list.count():
            self.list.setCurrentRow(min(row, self.list.count() - 1))

    def set_adv(self) -> None:
        code = self.current_code()
        if self._loading or code is None or code not in self.draft.glyphs:
            return
        cap = self.cap_mm.value()
        value = self.adv_box.value()
        if abs(value - self.draft.adv_mm(code, cap)) < 5e-4:
            return
        self.draft.set_adv(code, value, cap)
        self.dirty = True
        self._refresh_preview()

    def apply_kern(self) -> bool:
        pair = self.pair_edit.text()
        if len(pair) != 2 or not all(FE.valid_char(c) for c in pair):
            QMessageBox.information(self, tr('Crénage'), tr('Tapez les deux caractères de la paire.'))
            self.pair_edit.setFocus()
            return False
        self.draft.set_kern(ord(pair[0]), ord(pair[1]), self.kern_box.value(), self.cap_mm.value())
        self.dirty = True
        self._refresh_kern()
        self._refresh_preview()
        return True

    # --- fermeture ----------------------------------------------------------------------------

    def closeEvent(self, ev) -> None:
        if self.ask_discard():
            ev.accept()
        else:
            ev.ignore()

    def reject(self) -> None:
        if self.ask_discard():
            super().reject()
