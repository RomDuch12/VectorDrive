"""« Ajouter à une mémoire… » du panneau de l'assistant (demande du 20/11, 15 h 36 : « IA : fonction ajout à une
mémoire (nouvelle ou existante) les opérations effectuées sur ce fichiers, on demandera un titre et en option une
description faite par user pour structurer cette mémoire »).

`operations_text(win)` : les opérations faites sur le dessin affiché — les modifications dans l'ordre (la pile
d'annulation, sans les défaites), la machine et les opérations FAO ; `AddToMemory` : la fenêtre (mémoire nouvelle ou
existante, titre, description facultative, le texte relu et corrigé avant d'être gardé)."""
from __future__ import annotations

import pathlib

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
                               QPlainTextEdit, QPushButton, QVBoxLayout)

from ..i18n import tr

#: au plus tant de modifications reprises (les plus récentes)
MAX_STEPS = 300


def _num(v) -> str:
    from ..i18n import decimal_sep
    try:
        return f'{float(v):g}'.replace('.', decimal_sep())
    except (TypeError, ValueError):                      # une valeur d'un vieux fichier : telle quelle
        return str(v)


def source_name(win) -> str:
    path = getattr(win, 'path', None)
    return pathlib.Path(path).name if path else tr('Sans titre')


def operations_text(win) -> str:
    """Le texte des opérations faites sur le dessin affiché ('' : rien)."""
    out = []
    labels, done = win.history_timeline()
    steps = [str(x) for x in labels[:done]][-MAX_STEPS:]
    if steps:
        out.append(tr('Modifications du dessin (dans l’ordre) :'))
        run, n = None, 0
        for s in steps + [None]:                         # répétées à la suite : une ligne « ×n »
            if s == run:
                n += 1
                continue
            if run is not None:
                out.append(f'- {run}' + (f' (×{n})' if n > 1 else ''))
            run, n = s, 1
    cam = getattr(win, 'cam_panel', None)
    if cam is not None:
        s = cam.setup()
        if s.operations:
            from ..cam import model
            tools = {t.id: t for t in s.tools}
            if out:
                out.append('')
            out.append(tr('FAO — machine {0}, opérations dans l’ordre d’usinage :').format(cam.post_key() or '—'))
            for i, o in enumerate(s.operations, 1):
                t = tools.get(o.tool_id)
                kind = tr(model.op_kinds().get(o.kind, o.kind))
                parts = [tr('outil {0}').format(f'T{t.number} {t.name}'.strip() if t is not None else '—')]
                if o.kind not in ('instruction', 'texte_machine'):
                    parts.append(tr('profondeur {0} mm').format(_num(o.depth)))
                if o.step_down:
                    parts.append(tr('passes de {0} mm').format(_num(o.step_down)))
                if o.kind == 'contour':
                    from .cam_panel import SIDES
                    parts.append(tr('côté {0}').format(tr(SIDES.get(o.side, o.side)).lower()))
                if o.stock:
                    parts.append(tr('surépaisseur {0} mm').format(_num(o.stock)))
                if o.feed:
                    parts.append(tr('avance {0} mm/min').format(_num(o.feed)))
                if o.spindle:
                    parts.append(tr('broche {0} tr/min').format(_num(o.spindle)))
                if o.items:
                    parts.append(tr('{0} objet(s)').format(len(o.items)))
                elif o.sources:
                    parts.append(tr('couleurs {0}').format(', '.join(str(c + 1) for c in o.sources)))
                if not o.enabled:
                    parts.append(tr('désactivée'))
                name = f'{o.name} ({kind})' if o.name and o.name != kind else kind
                out.append(f'{i}. {name} — ' + ', '.join(parts))
    return '\n'.join(out)


class AddToMemory(QDialog):
    """La fenêtre : une mémoire nouvelle ou existante, son titre, sa description (facultative), les opérations."""

    def __init__(self, win, parent=None):
        super().__init__(parent)
        from ..agent import memories as M
        from .fit import release
        release(self)
        self.win, self.M = win, M
        self.saved, self.saved_title = None, ''
        self.setWindowTitle(tr('Ajouter à une mémoire'))
        lay = QVBoxLayout(self)
        intro = QLabel(tr('Les opérations faites sur ce dessin, gardées dans une mémoire que l’assistant lit quand '
                          'elle sert (il voit le titre et la description de chacune au début d’une discussion).'))
        intro.setWordWrap(True)
        lay.addWidget(intro)
        form = QFormLayout()
        self.which = QComboBox()
        self.which.addItem(tr('Nouvelle mémoire'), '')
        self._topics = M.topics()
        for t in self._topics:
            self.which.addItem(t['title'], t['title'])
        form.addRow(tr('Mémoire'), self.which)
        self.title = QLineEdit()
        self.title.setMaxLength(M.TITLE_MAX)
        self.title.setPlaceholderText(tr('Titre (obligatoire)'))
        form.addRow(tr('Titre'), self.title)
        self.description = QPlainTextEdit()
        self.description.setPlaceholderText(tr('Description (facultative) : à quoi sert cette mémoire, quand s’en '
                                               'servir'))
        self.description.setMaximumHeight(self.description.fontMetrics().lineSpacing() * 4 + 12)
        form.addRow(tr('Description'), self.description)
        lay.addLayout(form)
        lay.addWidget(QLabel(tr('Opérations de {0} (à relire, corriger) :').format(source_name(win))))
        try:
            text = operations_text(win)
        except Exception:                                # noqa: BLE001 — la fenêtre s'ouvre quand même, à remplir
            text = ''
        self.entry = QPlainTextEdit(text)
        lay.addWidget(self.entry, 1)
        self.error = QLabel('')
        self.error.setWordWrap(True)
        self.error.setStyleSheet('color: #c62828')
        lay.addWidget(self.error)
        row = QHBoxLayout()
        folder = QPushButton(tr('Ouvrir le dossier des mémoires'))
        folder.clicked.connect(self.open_folder)
        row.addWidget(folder)
        row.addStretch(1)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.keep)
        self.buttons.rejected.connect(self.reject)
        row.addWidget(self.buttons)
        lay.addLayout(row)
        self.which.currentIndexChanged.connect(lambda _i: self._which_changed())
        self.resize(600, 520)

    def _which_changed(self) -> None:
        title = self.which.currentData()
        t = next((x for x in self._topics if x['title'] == title), None) if title else None
        if not self.title.isReadOnly():                  # on quitte « Nouvelle mémoire » : ce qui est tapé, retenu
            self._typed = (self.title.text(), self.description.toPlainText())
        self.title.setReadOnly(t is not None)
        typed = getattr(self, '_typed', ('', ''))
        self.title.setText(t['title'] if t is not None else typed[0])
        self.description.setPlainText(t['description'] if t is not None else typed[1])
        self.error.setText('')

    def open_folder(self) -> None:
        d = self.M.folder()
        try:
            d.mkdir(parents=True, exist_ok=True)
        except OSError as ex:
            self.error.setText(str(ex))
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(d)))

    def keep(self) -> None:
        """OK : gardée, ou ce qui manque dit dans la fenêtre (elle reste ouverte)."""
        new = not self.which.currentData()
        title = self.M.clean_title(self.title.text())
        why = {'title': tr('Donnez un titre à la mémoire.'),
               'entry': tr('Rien à garder : le texte des opérations est vide.'),
               'exists': tr('Une mémoire porte déjà ce titre : choisissez-la dans la liste, ou un autre titre.'),
               'missing': tr('Cette mémoire n’existe plus.')}
        self.saved_title = title if new else self.which.currentData()
        try:
            self.saved = self.M.add(self.saved_title, self.entry.toPlainText(),
                                    description=self.description.toPlainText(), source=source_name(self.win),
                                    new=new)
        except ValueError as ex:
            self.error.setText(why.get(str(ex), str(ex)))
            return
        except OSError as ex:
            self.error.setText(str(ex))
            return
        self.accept()
