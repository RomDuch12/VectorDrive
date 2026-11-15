"""Montrer un fichier produit (programme machine, parcours…) dans
l'explorateur du système : dossier ouvert, fichier sélectionné quand le
système le permet."""
from __future__ import annotations

import pathlib
import subprocess
import sys

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QMessageBox, QWidget

from ..i18n import tr


def reveal(path) -> bool:
    """Ouvre le dossier de `path` (un fichier ou un dossier) ; sous Windows
    et macOS le fichier y est sélectionné. Rend False si rien n'existe."""
    p = pathlib.Path(path)
    if not p.exists():
        p = p.parent
        if not p.exists():
            return False
    if p.is_file() and sys.platform == 'win32':
        subprocess.Popen(f'explorer /select,"{p}"')
        return True
    if p.is_file() and sys.platform == 'darwin':
        subprocess.Popen(['open', '-R', str(p)])
        return True
    folder = p if p.is_dir() else p.parent
    return QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))


def done_message(parent: QWidget | None, title: str, text: str, path) -> QMessageBox:
    """Message de fin (non bloquant) avec un bouton « Ouvrir le dossier »
    qui montre `path`. Rend la boîte (déjà affichée)."""
    box = QMessageBox(QMessageBox.Icon.Information, title, text, QMessageBox.StandardButton.Ok, parent)
    b = box.addButton(tr('Ouvrir le dossier'), QMessageBox.ButtonRole.ActionRole)
    b.setToolTip(str(path))
    b.clicked.connect(lambda: reveal(path))          # puis la boîte se ferme, comme pour tout bouton
    box.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
    box.setObjectName('done_message')
    box.open()
    return box
