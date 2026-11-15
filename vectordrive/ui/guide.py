"""Guide des commandes, tiré du ruban réel (onglets, groupes, commandes,
raccourcis, infobulles) : toujours à jour et dans la langue de
l'interface. Affiché par Aide → Commandes ; `outils/guide.py` l'écrit
dans docs/."""
from __future__ import annotations

from PySide6.QtWidgets import QDialog, QLabel, QTextBrowser, QVBoxLayout

from .. import __version__
from ..i18n import tr
from .ribbon import RibbonGroup


def commands_markdown(win) -> str:
    out = [f'# {tr("Guide des commandes")} — VectorDrive {__version__}', '',
           tr('Généré depuis le ruban (outils/guide.py) : chaque ligne est une commande réelle.'), '']
    r = win.ribbon
    shown = set()
    for i in range(r.count()):
        out += [f'## {r.tabText(i)}', '']
        page = r.widget(i).widget()
        for g in page.findChildren(RibbonGroup):
            title = next((lab.text() for lab in g.findChildren(QLabel)
                          if lab.objectName() == 'ribbonGroupTitle'), '')
            rows = []
            for b in g.buttons():
                act = b.defaultAction()
                if act is None:
                    continue
                shown.add(id(act))
                keys = ', '.join(s.toString() for s in act.shortcuts())
                tip = act.statusTip() or ''
                if tip == act.text():
                    tip = ''
                rows.append(f'| {act.text()} | {keys} | {tip} |')
            if rows:
                out += [f'### {title}', '', f'| {tr("Commande")} | {tr("Raccourci")} | {tr("Rôle")} |',
                        '|---|---|---|'] + rows + ['']
    extra = [a for a in win.A.values() if a.shortcuts() and id(a) not in shown]
    if extra:
        out += [f'## {tr("Raccourcis sans bouton")}', '', f'| {tr("Commande")} | {tr("Raccourci")} |', '|---|---|']
        out += [f'| {a.text()} | {", ".join(s.toString() for s in a.shortcuts())} |' for a in extra]
        out.append('')
    return '\n'.join(out) + '\n'


class GuideDialog(QDialog):
    def __init__(self, win):
        super().__init__(win)
        from .fit import no_hscroll
        no_hscroll(self)                                 # pas de défilement horizontal à l'ouverture
        self.setWindowTitle(tr('Guide des commandes'))
        self.resize(820, 700)
        lay = QVBoxLayout(self)
        view = QTextBrowser()
        view.setMarkdown(commands_markdown(win))
        lay.addWidget(view)
