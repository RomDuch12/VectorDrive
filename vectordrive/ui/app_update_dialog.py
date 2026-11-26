"""Confirmation de la mise à jour de l'application par dossier (demande du 24/11, `MainWindow.app_update`).

Une seule fenêtre, qui dit exactement ce qui va être fait : la version trouvée et d'où elle vient, où elle est
installée, si les réglages, les données et la bibliothèque sont repris, que tous les onglets ouverts suivent, si les
raccourcis sont mis à jour, que les anciennes versions restent toutes (demande du 26/11 : aucune n'est supprimée), et
que l'application se ferme pour laisser la nouvelle se lancer.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCheckBox, QDialog, QDialogButtonBox, QLabel, QVBoxLayout

from .. import __version__
from ..i18n import tr


class AppUpdateDialog(QDialog):
    """`found` : l'archive (`app_update.Found`) ; `dest` : le dossier de la nouvelle version ; `zips` : celui où
    l'archive est copiée ; `portable` : l'application en cours est portable (ses réglages se copient) ; `shortcuts` :
    la case des raccourcis ; `there` : (la version est déjà dans le dossier VD, avec des réglages à elle) — la reprise
    est alors décochée d'office, rien n'y est remplacé sans copie de secours."""

    def __init__(self, parent, found, dest, *, zips=None, portable: bool = True, shortcuts: bool = True,
                 there=(False, False)):
        super().__init__(parent)
        self.setWindowTitle(tr('Mise à jour de l’application'))
        lay = QVBoxLayout(self)

        def line(text: str) -> QLabel:
            lab = QLabel(text)
            lab.setWordWrap(True)
            lab.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            lay.addWidget(lab)
            return lab

        self.headline = line(tr('La version {0} est disponible (en cours : {1}).').format(found.version, __version__))
        self.origin = line(tr('Archive : {0}').format(found.path))
        self.target = line(tr('Elle est copiée dans {0}, puis décompressée dans {1}.').format(
            zips if zips is not None else dest.parent, dest))
        self.carry = QCheckBox(tr('Reprendre mes réglages, mes données et ma bibliothèque'))
        here, settled = bool(there[0]), bool(there[0] and there[1])
        self.carry.setChecked(bool(portable) and not settled)
        self.carry.setEnabled(bool(portable))
        self.carry.setToolTip(tr('VectorDrive.ini et le dossier « donnees » de cette version sont copiés dans la '
                                 'nouvelle, ainsi que les fichiers de sa bibliothèque (« bibliotheque » : symboles '
                                 'ajoutés, logos des BAT, favoris) que la nouvelle n’a pas — aucun des siens n’est '
                                 'remplacé ; décochée : la nouvelle version part de ses propres réglages (les onglets '
                                 'ouverts la suivent quand même)'))
        lay.addWidget(self.carry)
        self.carry_note = self.there_note = None
        if not portable:                                 # réglages dans le registre : rien à copier, dit ici
            self.carry_note = line(tr('Cette application n’est pas portable : ses réglages sont dans le registre du '
                                      'poste et ne se copient pas. La nouvelle version, portable, part de ses '
                                      'propres réglages ; les onglets ouverts la suivent.'))
        if settled:                                      # déjà installée et déjà utilisée : ses réglages à elle
            self.there_note = line(tr('Cette version est déjà dans le dossier VD, avec ses propres réglages : ils '
                                      'sont gardés. Cocher la reprise les remplace par ceux de cette application '
                                      '(une copie de secours « VectorDrive.ini.avant_reprise » est faite).'))
        elif here:
            self.there_note = line(tr('Cette version est déjà dans le dossier VD : elle est reprise telle quelle.'))
        # demande du 26/11 (« attention à récupérer tous les onglets ») : enregistrés ou non, épinglés, renommés
        self.tabs = line(tr('Tous les onglets ouverts — enregistrés, modifiés, jamais enregistrés, épinglés, '
                            'renommés — se rouvrent dans la nouvelle version, dans le même ordre, avec l’onglet '
                            'actif ; aucun dessin n’est enregistré à votre place.'))
        self.shortcuts = QCheckBox(tr('Mettre à jour les raccourcis (menu Démarrer, barre des tâches, bureau)'))
        self.shortcuts.setChecked(bool(shortcuts))
        self.shortcuts.setToolTip(tr('Les raccourcis qui lancent l’ancienne version lancent la nouvelle ; aucun dans '
                                     'le menu Démarrer : « VectorDrive » y est créé'))
        lay.addWidget(self.shortcuts)
        # demande du 26/11 : « Ne pas supprimer de versions antérieures automatiquement »
        self.previous = line(tr('Aucune ancienne version n’est supprimée : celle-ci et les précédentes restent, '
                                'chacune dans son dossier.'))
        self.closing = line(tr('La nouvelle version se lance ; dès que sa fenêtre est prête, VectorDrive se ferme.'))
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.button(QDialogButtonBox.StandardButton.Ok).setText(tr('Mettre à jour'))
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        self.setMinimumWidth(560)

    def values(self) -> dict:
        """Les réponses : {'reprendre': …, 'raccourcis': …}."""
        return {'reprendre': self.carry.isEnabled() and self.carry.isChecked(),
                'raccourcis': self.shortcuts.isChecked()}
