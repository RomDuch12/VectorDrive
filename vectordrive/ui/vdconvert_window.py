"""La fenêtre de VD-convert (voir `vectordrive.vdconvert`) : l'état du menu de l'explorateur et les autres versions
trouvées, Installer (ou Remplacer et installer) / Désinstaller, une conversion à la main (fichiers choisis ou
déposés) et le mode d'emploi."""
from __future__ import annotations

import pathlib

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QComboBox, QGroupBox, QHBoxLayout, QLabel, QListWidget, QMessageBox,
                               QPlainTextEdit, QPushButton, QVBoxLayout, QWidget)

from .. import shellmenu as SM
from .. import vdconvert as VC
from ..i18n import tr


def _label(text: str) -> QLabel:
    lab = QLabel(text)
    lab.setWordWrap(True)
    lab.setTextFormat(Qt.TextFormat.PlainText)
    return lab


class ConvertWindow(QWidget):
    """`reg` : le registre (WinReg sous Windows ; MemoryReg ailleurs et dans les essais)."""

    def __init__(self, reg=None, parent=None):
        super().__init__(parent)
        if reg is None:
            reg = VC.WinReg() if SM.available() else VC.MemoryReg()
        self.reg = reg
        self.setWindowTitle(f'{VC.NAME} {VC.version()}')
        self.setMinimumWidth(600)
        self.setAcceptDrops(True)
        lay = QVBoxLayout(self)
        lay.addWidget(_label(tr('Convertit les dessins (VND, VDZ, DXF, SVG, PDF, AI, EPS…) en DXF, SVG, PDF ou EPS, '
                                'au clic droit de l’explorateur ou ici, sans ouvrir VectorDrive. Le fichier converti '
                                'est écrit à côté de l’original, jamais par-dessus un fichier existant.')))

        box = QGroupBox(tr('Menu de l’explorateur'))
        bl = QVBoxLayout(box)
        self.state = _label('')
        bl.addWidget(self.state)
        self.others_title = _label(tr('Autres versions trouvées (retirées à l’installation) :'))
        bl.addWidget(self.others_title)
        self.others = QListWidget()
        self.others.setMaximumHeight(90)
        bl.addWidget(self.others)
        row = QHBoxLayout()
        self.install_btn = QPushButton(tr('Installer'))
        self.install_btn.clicked.connect(lambda _=False: self.do_install())
        self.uninstall_btn = QPushButton(tr('Désinstaller'))
        self.uninstall_btn.clicked.connect(lambda _=False: self.do_uninstall())
        row.addWidget(self.install_btn)
        row.addWidget(self.uninstall_btn)
        row.addStretch(1)
        bl.addLayout(row)
        lay.addWidget(box)

        box = QGroupBox(tr('Convertir'))
        cl = QVBoxLayout(box)
        row = QHBoxLayout()
        row.addWidget(QLabel(tr('Vers')))
        self.fmt = QComboBox()
        for k, lab in SM.TARGETS:
            self.fmt.addItem(lab, k)
        row.addWidget(self.fmt)
        self.pick_btn = QPushButton(tr('Choisir des fichiers…'))
        self.pick_btn.clicked.connect(lambda _=False: self.pick())
        row.addWidget(self.pick_btn)
        row.addWidget(QLabel(tr('ou déposez-les sur cette fenêtre')))
        row.addStretch(1)
        cl.addLayout(row)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(120)
        cl.addWidget(self.log)
        lay.addWidget(box)

        lay.addWidget(_label(self.guide_text()))
        row = QHBoxLayout()
        row.addStretch(1)
        close = QPushButton(tr('Fermer'))
        close.clicked.connect(lambda _=False: self.close())
        row.addWidget(close)
        lay.addLayout(row)
        self.refresh()

    @staticmethod
    def guide_text() -> str:
        return tr('Mode d’emploi : « Installer » copie VD-convert dans votre dossier de programmes '
                  '(%LOCALAPPDATA%\\Programs\\VD-convert) et pose « Convertir avec VectorDrive » au clic droit des '
                  'dessins ; les autres versions trouvées (un autre VD-convert, le menu de VectorDrive ou d’une copie '
                  'déplacée) sont retirées et remplacées ; VectorDrive lui-même reste installé. Sous Windows 11, le '
                  'menu est sous « Afficher plus d’options » (Maj+F10). Tout est écrit sous votre compte seulement, '
                  'sans droit d’administrateur ; « Désinstaller » (ici ou dans les Applications de Windows) retire '
                  'tout.')

    # --- état ---------------------------------------------------------------------------------------------------
    def installed_dir(self):
        """Le dossier de l'installation inscrite, s'il y en a une."""
        loc = self.reg.read(VC.UNINSTALL_KEY, 'InstallLocation')
        return pathlib.Path(loc) if loc else None

    def me(self) -> tuple:
        """Le programme que le menu doit appeler (exe, [script]) : la copie installée, ou ce script en
        développement."""
        if VC.running_dir() is None:
            return VC.dev_program()
        return str((self.installed_dir() or VC.install_dir()) / VC.EXE), []

    def refresh(self) -> None:
        ok, why, others = VC.status(self.reg, self.me())
        inst = self.installed_dir()
        v = self.reg.read(VC.UNINSTALL_KEY, 'DisplayVersion') or ''
        lines = []
        if inst is not None:
            lines.append(tr('Installé : version {0} dans {1}').format(v or '?', inst))
        lines.append(why if why and why != 'Non installé.' else tr('Menu de l’explorateur : non posé.'))
        self.state.setText('\n'.join(lines))
        self.others.clear()
        for o in others:
            self.others.addItem(o.text())
        self.others.setVisible(bool(others))
        self.others_title.setVisible(bool(others))
        self.install_btn.setText(tr('Remplacer et installer') if others else
                                 tr('Réinstaller') if ok else tr('Installer'))
        self.install_btn.setEnabled(SM.available() or isinstance(self.reg, VC.MemoryReg))
        self.uninstall_btn.setEnabled(inst is not None or ok)
        self._others = others

    # --- actions -------------------------------------------------------------------------------------------------
    def do_install(self, confirm: bool = True) -> dict | None:
        others = list(getattr(self, '_others', []))
        if confirm and others:
            q = tr('Ces autres versions seront retirées et remplacées par VD-convert {0} :\n\n{1}\n\nContinuer ?').format(
                VC.version(), '\n'.join('• ' + o.text() for o in others))
            if QMessageBox.question(self, VC.NAME, q) != QMessageBox.StandardButton.Yes:
                return None
        try:
            src = VC.running_dir()
            got = VC.install(self.reg, src, VC.install_dir() if src is not None else None)
        except OSError as ex:
            QMessageBox.warning(self, VC.NAME, str(ex))
            return None
        self.refresh()
        if confirm:
            msg = tr('Installé : {0}').format(got['exe'])
            if got['removed']:
                msg += '\n\n' + tr('Retiré :') + '\n' + '\n'.join('• ' + r for r in got['removed'])
            msg += '\n\n' + tr('Sous Windows 11 : clic droit sur un dessin, puis « Afficher plus d’options ».')
            QMessageBox.information(self, VC.NAME, msg)
        return got

    def do_uninstall(self, confirm: bool = True) -> list | None:
        if confirm and QMessageBox.question(
                self, VC.NAME, tr('Désinstaller VD-convert (menu de l’explorateur, entrée des Applications, '
                                  'dossier installé) ?')) != QMessageBox.StandardButton.Yes:
            return None
        me = self.me()
        try:
            done = VC.uninstall(self.reg, self.installed_dir() or VC.install_dir(),
                                program=me[1][0] if me[1] else None)
        except OSError as ex:
            QMessageBox.warning(self, VC.NAME, str(ex))
            return None
        self.refresh()
        leaving = any('à la fermeture' in d for d in done)
        if leaving:                                      # le dossier part à la fermeture : rien à réinstaller d'ici
            self.install_btn.setEnabled(False)
            self.uninstall_btn.setEnabled(False)
        if confirm:
            QMessageBox.information(self, VC.NAME, '\n'.join(done) or tr('Rien à retirer.'))
            if leaving:
                from PySide6.QtWidgets import QApplication
                QApplication.instance().quit()
        return done

    def convert_files(self, paths) -> list:
        """Convertit les fichiers vers le format choisi ; rend les chemins écrits (erreurs dans le journal)."""
        fmt = self.fmt.currentData()
        out = []
        for p in paths:
            try:
                dest, notes = VC.convert(p, fmt)
            except Exception as ex:                      # noqa: BLE001 — un fichier illisible n'arrête pas les autres
                self.log.appendPlainText(f'✗ {pathlib.Path(p).name} : {ex}')
                continue
            out.append(dest)
            self.log.appendPlainText(f'✓ {pathlib.Path(p).name} → {dest.name}' +
                                     ''.join(f'\n    {n}' for n in notes))
        return out

    def pick(self) -> list:
        from PySide6.QtWidgets import QFileDialog
        pat = ' '.join('*' + e for e in SM.SOURCES)
        files, _f = QFileDialog.getOpenFileNames(self, tr('Dessins à convertir'), '',
                                                 tr('Dessins ({0})').format(pat))
        return self.convert_files(files) if files else []

    def dragEnterEvent(self, ev):
        if ev.mimeData().hasUrls():
            ev.acceptProposedAction()

    def dropEvent(self, ev):
        paths = [u.toLocalFile() for u in ev.mimeData().urls() if u.isLocalFile()]
        paths = [p for p in paths if pathlib.Path(p).suffix.lower() in SM.SOURCES]
        if paths:
            ev.acceptProposedAction()
            self.convert_files(paths)
