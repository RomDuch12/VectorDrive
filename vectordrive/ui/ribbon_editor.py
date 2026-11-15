"""Personnaliser le ruban : des onglets à soi (« Mon onglet », puis autant
qu'on veut), chacun nommé et placé où l'on veut (en premier, en dernier,
après un onglet donné), composés de n'importe quelles commandes rangées en
groupes, en grands ou petits boutons, au libellé choisi ; les onglets
inutiles masqués ; le tout exporté ou importé (fichier JSON, d'un poste à
l'autre).

Réglages : « ruban/perso » (JSON, le premier onglet), « ruban/onglets »
(JSON, les suivants) et « ruban/masques » (titres des onglets masqués,
séparés par ;).

    {"titre": "Mon onglet", "position": "debut",
     "groupes": [{"titre": "Fichiers", "commandes": [{"key": "open", "big": true, "texte": "Ouvrir"}, …]}, …]}

Position : « debut », « fin », ou « apres:<titre d'un onglet> ».
"""
from __future__ import annotations

import json

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QHBoxLayout,
                               QHeaderView, QInputDialog,
                               QLabel, QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QPushButton,
                               QTreeWidget, QTreeWidgetItem, QVBoxLayout)

from ..i18n import tr

KEY = 'ruban/perso'
MORE = 'ruban/onglets'
HIDDEN = 'ruban/masques'
DEFAULT = {'titre': 'Mon onglet', 'position': 'debut', 'groupes': []}
#: préfixe d'une position « après un onglet »
AFTER = 'apres:'


def _clean(d) -> dict | None:
    """Onglet relu (réglage, fichier importé) ; None s'il est illisible."""
    if not isinstance(d, dict):
        return None
    groups = []
    for g in d.get('groupes') or []:
        if isinstance(g, dict):
            cmds = []
            for c in g.get('commandes') or []:
                if isinstance(c, dict) and c.get('key'):
                    c = dict(c)
                    if not str(c.get('texte') or '').strip():
                        c.pop('texte', None)
                    cmds.append(c)
            groups.append({'titre': str(g.get('titre') or ''), 'commandes': cmds})
    pos = str(d.get('position') or 'debut')
    if pos not in ('debut', 'fin') and not (pos.startswith(AFTER) and len(pos) > len(AFTER)):
        pos = 'debut'
    return {'titre': str(d.get('titre') or DEFAULT['titre']), 'position': pos, 'groupes': groups}


def free_title(title: str, taken) -> str:
    """`title`, ou « title (2) », « title (3) »… s'il est déjà pris."""
    out, n = title, 2
    while out in taken:
        out = f'{title} ({n})'
        n += 1
    return out


def _json(settings, key):
    try:
        return json.loads(str(settings.value(key, '') or '') or 'null')
    except ValueError:
        return None


def load(settings) -> dict:
    """Le premier onglet à soi (« Mon onglet » par défaut)."""
    return _clean(_json(settings, KEY)) or dict(DEFAULT, groupes=[])


def save(settings, conf: dict) -> None:
    """Le premier onglet à soi (les suivants ne changent pas)."""
    settings.setValue(KEY, json.dumps(conf, ensure_ascii=False))


def load_all(settings) -> list[dict]:
    """Tous les onglets à soi, dans l'ordre (le premier : `load`)."""
    more = _json(settings, MORE)
    return [load(settings)] + [t for t in (_clean(d) for d in (more if isinstance(more, list) else [])) if t]


def save_all(settings, tabs: list[dict]) -> None:
    tabs = list(tabs) or [dict(DEFAULT, groupes=[])]
    save(settings, tabs[0])
    if len(tabs) > 1:
        settings.setValue(MORE, json.dumps(tabs[1:], ensure_ascii=False))
    else:
        settings.remove(MORE)


def hidden(settings) -> list[str]:
    titles = [t for t in str(settings.value(HIDDEN, '') or '').split(';') if t]
    if tr('FAO') in titles:                              # l'onglet FAO d'avant : FAO 2D et FAO 3D
        titles += [t for t in (tr('FAO 2D'), tr('FAO 3D')) if t not in titles]
    return titles


def set_hidden(settings, titles: list[str]) -> None:
    settings.setValue(HIDDEN, ';'.join(titles))


class RelayAction(QAction):
    """Bouton d'un onglet à soi au libellé choisi : même icône, même commande,
    même état (coché, actif) que l'action d'origine."""

    def __init__(self, src: QAction, text: str, parent):
        super().__init__(src.icon(), text, parent)
        self.src = src
        self.setToolTip(src.toolTip() or src.text())
        self.setStatusTip(src.statusTip())
        self.setCheckable(src.isCheckable())
        if src.property('vd_icon'):
            self.setProperty('vd_icon', src.property('vd_icon'))   # icône refaite au changement de thème
        if src.menu() is not None:
            self.setMenu(src.menu())
        self._sync()
        src.changed.connect(self._sync)
        if src.isCheckable():
            src.toggled.connect(self._toggled)
        self.triggered.connect(self._run)

    def detach(self) -> None:
        """Plus relié à l'action d'origine (onglet refait)."""
        self.src.changed.disconnect(self._sync)
        if self.isCheckable():
            self.src.toggled.disconnect(self._toggled)

    def _sync(self) -> None:
        self.setEnabled(self.src.isEnabled())
        if self.isCheckable() and self.isChecked() != self.src.isChecked():
            self._toggled(self.src.isChecked())

    def _toggled(self, on: bool) -> None:
        self.blockSignals(True)
        self.setChecked(on)
        self.blockSignals(False)

    def _run(self, _checked=False) -> None:
        self.src.trigger()
        if self.isCheckable():
            self._toggled(self.src.isChecked())


class RibbonEditor(QDialog):
    """Onglets à soi : commandes à gauche, onglet choisi à droite."""

    def __init__(self, win, parent=None):
        super().__init__(parent or win)
        from .fit import no_hscroll
        no_hscroll(self)                                 # pas de défilement horizontal à l'ouverture
        self.win = win
        self.setWindowTitle(tr('Personnaliser le ruban'))
        avail = self.screen().availableGeometry() if self.screen() is not None else None
        self.resize(min(900, avail.width() - 40) if avail else 900, min(620, avail.height() - 60) if avail else 620)
        self.tabs = load_all(win.settings)
        self.cur = 0
        self.conf = self.tabs[0]
        r = win.ribbon
        own = set(getattr(r, 'custom_titles', None) or [])
        #: onglets de VectorDrive (ni à soi, ni contextuels) : « après… », onglets affichés
        self.builtin = []
        for i in range(r.count()):
            t = r.tabText(i)
            if t in own or t == getattr(win, 'text_tab_title', None) or t in self.builtin:
                continue
            if r.widget(i).property('te_context'):
                continue                                     # onglets contextuels de TypeEdit : ouverts par Mode
            self.builtin.append(t)
        lay = QVBoxLayout(self)
        row = QHBoxLayout()
        row.addWidget(QLabel(tr('Onglet')))
        self.tab_choice = QComboBox()
        self.tab_choice.setMinimumWidth(160)
        self.tab_choice.currentIndexChanged.connect(lambda i: self._tab_changed(i))
        row.addWidget(self.tab_choice)
        for text, slot, tip in ((tr('Nouvel onglet…'), lambda: self.new_tab(), tr('Un autre onglet à soi, à nommer')),
                                (tr('Supprimer l\'onglet'), lambda: self.remove_tab(),
                                 tr('L\'onglet choisi et ses groupes retirés du ruban'))):
            b = QPushButton(text)
            b.setToolTip(tip)
            b.clicked.connect(lambda _=False, s=slot: s())
            row.addWidget(b)
        row.addStretch(1)
        lay.addLayout(row)
        top = QHBoxLayout()
        top.addWidget(QLabel(tr('Nom de l\'onglet')))
        self.title = QLineEdit(self.conf['titre'])
        self.title.textEdited.connect(lambda t: self._renamed(t))
        top.addWidget(self.title, 1)
        top.addWidget(QLabel(tr('Place')))
        self.pos = QComboBox()
        self.pos.addItem(tr('En premier'), 'debut')
        self.pos.addItem(tr('En dernier'), 'fin')
        for t in self.builtin:
            self.pos.addItem(tr('Après « {0} »').format(t.replace('&', '')), AFTER + t)
        self.pos.currentIndexChanged.connect(lambda _i: self._pos_changed())
        top.addWidget(self.pos)
        lay.addLayout(top)
        body = QHBoxLayout()
        left = QVBoxLayout()
        self.filter = QLineEdit()
        self.filter.setPlaceholderText(tr('Filtrer les commandes…'))
        self.filter.textChanged.connect(self._fill_commands)
        left.addWidget(self.filter)
        self.commands = QListWidget()
        self.commands.itemDoubleClicked.connect(lambda *_: self.add())
        left.addWidget(self.commands, 1)
        body.addLayout(left, 1)
        mid = QVBoxLayout()
        mid.addStretch(1)
        for text, slot in ((tr('Ajouter →'), self.add), (tr('← Retirer'), self.remove),
                           (tr('Nouveau groupe…'), self.new_group), (tr('Renommer le groupe…'), self.rename_group),
                           (tr('Monter'), lambda: self.move(-1)), (tr('Descendre'), lambda: self.move(1)),
                           (tr('Grand / petit bouton'), self.toggle_big), (tr('Libellé du bouton…'), self.set_label)):
            b = QPushButton(text)
            b.clicked.connect(lambda _=False, s=slot: s())
            mid.addWidget(b)
        mid.addStretch(1)
        body.addLayout(mid)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels([tr('Mon onglet'), tr('Bouton')])
        hh = self.tree.header()
        hh.setStretchLastSection(False)
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        body.addWidget(self.tree, 1)
        lay.addLayout(body, 1)
        lay.addWidget(QLabel(tr('Onglets affichés')))
        from PySide6.QtWidgets import QGridLayout
        tabs = QGridLayout()                                 # sur plusieurs lignes : la fenêtre tient dans l'écran
        self.tab_checks: dict[str, QCheckBox] = {}
        hid = set(hidden(win.settings))
        for t in self.builtin:
            c = QCheckBox(t.replace('&', ''))
            c.setChecked(t not in hid)
            n = len(self.tab_checks)
            tabs.addWidget(c, n // 8, n % 8)
            self.tab_checks[t] = c
        tabs.setColumnStretch(8, 1)
        lay.addLayout(tabs)
        bottom = QHBoxLayout()
        for text, slot, tip in ((tr('Exporter…'), lambda: self.export_file(),
                                 tr('Les onglets à soi et les onglets masqués dans un fichier, pour un autre poste')),
                                (tr('Importer…'), lambda: self.import_file(),
                                 tr('Onglets à soi d\'un fichier exporté (remplacent ceux d\'ici)'))):
            b = QPushButton(text)
            b.setToolTip(tip)
            b.clicked.connect(lambda _=False, s=slot: s())
            bottom.addWidget(b)
        bottom.addStretch(1)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        bottom.addWidget(bb)
        lay.addLayout(bottom)
        self._fill_commands()
        self._fill_tabs(0)

    # --- onglets --------------------------------------------------------------------------------
    def _fill_tabs(self, select: int) -> None:
        self.tab_choice.blockSignals(True)
        self.tab_choice.clear()
        for t in self.tabs:
            self.tab_choice.addItem(t['titre'])
        self.tab_choice.setCurrentIndex(max(0, min(select, len(self.tabs) - 1)))
        self.tab_choice.blockSignals(False)
        self._tab_changed(self.tab_choice.currentIndex())

    def _tab_changed(self, i: int) -> None:
        if not 0 <= i < len(self.tabs):
            return
        self.cur = i
        self.conf = self.tabs[i]
        self.title.setText(self.conf['titre'])
        j = self.pos.findData(self.conf['position'])
        if j < 0 and self.conf['position'].startswith(AFTER):     # onglet absent (masqué, plugin retiré) : gardé
            self.pos.addItem(tr('Après « {0} »').format(self.conf['position'][len(AFTER):]), self.conf['position'])
            j = self.pos.count() - 1
        self.pos.blockSignals(True)
        self.pos.setCurrentIndex(max(0, j))
        self.pos.blockSignals(False)
        self.tree.headerItem().setText(0, self.conf['titre'])
        self._fill_tree()

    def _renamed(self, text: str) -> None:
        self.conf['titre'] = text.strip() or DEFAULT['titre']
        self.tab_choice.setItemText(self.cur, self.conf['titre'])
        self.tree.headerItem().setText(0, self.conf['titre'])

    def _pos_changed(self) -> None:
        self.conf['position'] = self.pos.currentData() or 'debut'

    def _free_title(self, title: str) -> str:
        """Titre d'un onglet à soi qui ne double ni un onglet de VectorDrive
        ni un autre onglet à soi."""
        return free_title(title, set(self.builtin) | {t['titre'] for k, t in enumerate(self.tabs) if k != self.cur})

    def new_tab(self, title: str | None = None) -> int:
        if title is None:
            title, ok = QInputDialog.getText(self, tr('Nouvel onglet'), tr('Nom de l\'onglet'),
                                             text=tr('Mon onglet {0}').format(len(self.tabs) + 1))
            if not ok:
                return -1
        self.cur = len(self.tabs)
        self.tabs.append({'titre': self._free_title(title.strip() or DEFAULT['titre']), 'position': 'fin',
                          'groupes': []})
        self._fill_tabs(self.cur)
        return self.cur

    def remove_tab(self) -> None:
        del self.tabs[self.cur]
        if not self.tabs:
            self.tabs.append(dict(DEFAULT, groupes=[]))
        self._fill_tabs(min(self.cur, len(self.tabs) - 1))

    # --- listes ---------------------------------------------------------------------------------
    def _fill_commands(self) -> None:
        q = self.filter.text().strip().lower()
        self.commands.clear()
        for key, act in sorted(self.win.A.items(), key=lambda kv: kv[1].text().replace('&', '').lower()):
            label = act.text().replace('&', '')
            tip = act.toolTip() or ''
            if q and q not in label.lower() and q not in tip.lower() and q not in key:
                continue
            it = QListWidgetItem(act.icon(), label)
            it.setToolTip(tip)
            it.setData(Qt.ItemDataRole.UserRole, key)
            self.commands.addItem(it)

    def _fill_tree(self, select: tuple | None = None) -> None:
        self.tree.clear()
        for gi, g in enumerate(self.conf['groupes']):
            gi_item = QTreeWidgetItem([g['titre'] or tr('(sans titre)'), ''])
            gi_item.setData(0, Qt.ItemDataRole.UserRole, (gi, -1))
            f = gi_item.font(0)
            f.setBold(True)
            gi_item.setFont(0, f)
            self.tree.addTopLevelItem(gi_item)
            for ci, c in enumerate(g['commandes']):
                act = self.win.A.get(c['key'])
                label = act.text().replace('&', '') if act else c['key']
                ch = QTreeWidgetItem([c.get('texte') or label, tr('grand') if c.get('big') else tr('petit')])
                if c.get('texte'):
                    ch.setToolTip(0, tr('Commande : {0}').format(label))
                if act:
                    ch.setIcon(0, act.icon())
                ch.setData(0, Qt.ItemDataRole.UserRole, (gi, ci))
                gi_item.addChild(ch)
                if select == (gi, ci):
                    self.tree.setCurrentItem(ch)
            gi_item.setExpanded(True)
            if select == (gi, -1):
                self.tree.setCurrentItem(gi_item)

    def _current(self) -> tuple[int, int]:
        it = self.tree.currentItem()
        if it is None:
            return (len(self.conf['groupes']) - 1, -1)
        return tuple(it.data(0, Qt.ItemDataRole.UserRole))

    # --- actions ----------------------------------------------------------------------------------
    def add(self, key: str | None = None) -> None:
        if key is None:
            it = self.commands.currentItem()
            if it is None:
                return
            key = it.data(Qt.ItemDataRole.UserRole)
        if not self.conf['groupes']:
            self.conf['groupes'].append({'titre': tr('Mes commandes'), 'commandes': []})
        gi, ci = self._current()
        gi = max(0, gi)
        cmds = self.conf['groupes'][gi]['commandes']
        pos = ci + 1 if ci >= 0 else len(cmds)
        cmds.insert(pos, {'key': key, 'big': len(cmds) < 3})
        self._fill_tree((gi, pos))

    def remove(self) -> None:
        gi, ci = self._current()
        if gi < 0:
            return
        if ci >= 0:
            del self.conf['groupes'][gi]['commandes'][ci]
            self._fill_tree((gi, min(ci, len(self.conf['groupes'][gi]['commandes']) - 1)))
        else:
            del self.conf['groupes'][gi]
            self._fill_tree()

    def new_group(self, title: str | None = None) -> None:
        if title is None:
            title, ok = QInputDialog.getText(self, tr('Nouveau groupe'), tr('Titre du groupe'))
            if not ok:
                return
        self.conf['groupes'].append({'titre': title.strip(), 'commandes': []})
        self._fill_tree((len(self.conf['groupes']) - 1, -1))

    def rename_group(self) -> None:
        gi, _ci = self._current()
        if gi < 0:
            return
        title, ok = QInputDialog.getText(self, tr('Renommer le groupe'), tr('Titre du groupe'),
                                         text=self.conf['groupes'][gi]['titre'])
        if ok:
            self.conf['groupes'][gi]['titre'] = title.strip()
            self._fill_tree((gi, -1))

    def move(self, d: int) -> None:
        gi, ci = self._current()
        if gi < 0:
            return
        if ci >= 0:
            cmds = self.conf['groupes'][gi]['commandes']
            j = ci + d
            if 0 <= j < len(cmds):
                cmds[ci], cmds[j] = cmds[j], cmds[ci]
                self._fill_tree((gi, j))
        else:
            gs = self.conf['groupes']
            j = gi + d
            if 0 <= j < len(gs):
                gs[gi], gs[j] = gs[j], gs[gi]
                self._fill_tree((j, -1))

    def toggle_big(self) -> None:
        gi, ci = self._current()
        if gi >= 0 and ci >= 0:
            c = self.conf['groupes'][gi]['commandes'][ci]
            c['big'] = not c.get('big')
            self._fill_tree((gi, ci))

    def set_label(self, text: str | None = None) -> None:
        """Libellé du bouton choisi dans l'onglet (vide : celui de la commande)."""
        gi, ci = self._current()
        if gi < 0 or ci < 0:
            return
        c = self.conf['groupes'][gi]['commandes'][ci]
        if text is None:
            act = self.win.A.get(c['key'])
            text, ok = QInputDialog.getText(self, tr('Libellé du bouton'),
                                            tr('Libellé (vide : « {0} »)').format(
                                                act.text().replace('&', '') if act else c['key']),
                                            text=c.get('texte', ''))
            if not ok:
                return
        if text.strip():
            c['texte'] = text.strip()
        else:
            c.pop('texte', None)
        self._fill_tree((gi, ci))

    # --- fichier ----------------------------------------------------------------------------------
    def export_file(self, path: str | None = None) -> str | None:
        if path is None:
            path, _f = QFileDialog.getSaveFileName(self, tr('Exporter le ruban'), 'ruban.json', tr('Ruban (*.json)'))
            if not path:
                return None
        data = {'vectordrive_ruban': 1, 'onglets': self.result_tabs(), 'masques': self.hidden_tabs()}
        import pathlib
        p = pathlib.Path(path)
        tmp = p.with_suffix(p.suffix + '.tmp')
        tmp.write_bytes(json.dumps(data, ensure_ascii=False, indent=1).encode('utf-8'))
        tmp.replace(p)
        return str(p)

    def import_file(self, path: str | None = None) -> int:
        """Onglets d'un fichier exporté à la place de ceux de la fenêtre (validé
        par OK) ; rend leur nombre (0 : fichier illisible, dit)."""
        if path is None:
            path, _f = QFileDialog.getOpenFileName(self, tr('Importer le ruban'), '', tr('Ruban (*.json)'))
            if not path:
                return 0
        import pathlib
        try:
            data = json.loads(pathlib.Path(path).read_text(encoding='utf-8'))
        except (OSError, ValueError):
            data = None
        tabs = data.get('onglets') if isinstance(data, dict) else None
        tabs = [t for t in (_clean(d) for d in (tabs if isinstance(tabs, list) else [])) if t]
        if not tabs:
            QMessageBox.warning(self, tr('Importer le ruban'), tr('Fichier sans onglet de ruban lisible'))
            return 0
        self.tabs = tabs
        if isinstance(data.get('masques'), list):
            for t, c in self.tab_checks.items():
                c.setChecked(t not in data['masques'])
        self._fill_tabs(0)
        return len(tabs)

    # --- résultat ---------------------------------------------------------------------------------
    def result_conf(self) -> dict:
        """L'onglet choisi, tel que réglé."""
        conf = dict(self.conf)
        conf['titre'] = self.title.text().strip() or DEFAULT['titre']
        conf['position'] = self.pos.currentData()
        return conf

    def result_tabs(self) -> list[dict]:
        """Tous les onglets à soi, titres rendus uniques (ni un onglet de
        VectorDrive, ni un autre onglet à soi)."""
        out = [dict(t) for t in self.tabs]
        out[self.cur] = self.result_conf()
        taken = set(self.builtin)
        for t in out:
            t['titre'] = free_title(t['titre'], taken)
            taken.add(t['titre'])
        return out

    def hidden_tabs(self) -> list[str]:
        return [t for t, c in self.tab_checks.items() if not c.isChecked()]

    def accept(self) -> None:
        save_all(self.win.settings, self.result_tabs())
        set_hidden(self.win.settings, self.hidden_tabs())
        super().accept()
