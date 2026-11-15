"""Fenêtre de vérification avant l'écriture du programme (cam.preflight)."""
from __future__ import annotations

from PySide6.QtWidgets import QCheckBox, QDialog, QDialogButtonBox, QLabel, QTextBrowser, QVBoxLayout

from ..cam import preflight as PF
from ..i18n import tr


class PreflightDialog(QDialog):
    """`add_stops` : fonction qui ajoute les arrêts qui manquent entre deux
    prises (bouton montré s'il en manque) ; le programme est alors à réécrire."""

    def __init__(self, parent, report: PF.Report, add_stops=None):
        super().__init__(parent)
        from .fit import no_hscroll
        no_hscroll(self)                                 # pas de défilement horizontal à l'ouverture
        self.setWindowTitle(tr('Vérification avant l\'écriture du programme'))
        self.setSizeGripEnabled(True)
        self.report = report
        lay = QVBoxLayout(self)
        n = len(report.blocking())
        head = QLabel(tr('{0} point(s) bloquant(s), en tête de la liste : à corriger avant d\'écrire — ou '
                         'écrire quand même, la décision vous revient.').format(n) if n else
                      tr('Ce que le programme contient, et ce qui mérite un regard. Rien n\'est bloqué : '
                         'la décision vous revient.'))
        head.setWordWrap(True)
        lay.addWidget(head)
        self.text = QTextBrowser()
        self.text.setHtml(PF.summary_html(report, tr))
        lay.addWidget(self.text, 1)
        self.skip = QCheckBox(tr('Ne plus vérifier avant d\'écrire (FAO ▸ Réglage pour le rétablir)'))
        lay.addWidget(self.skip)
        self.stops_added = []
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.stops_btn = None
        if add_stops is not None:
            self.stops_btn = bb.addButton(tr('Ajouter les arrêts'), QDialogButtonBox.ButtonRole.ActionRole)
            self.stops_btn.setToolTip(tr('Une instruction « Retournement de la pièce » (broche coupée, attente de '
                                         'l\'opérateur) avant chaque usinage de la pièce tournée autrement ; '
                                         'le programme n\'est pas écrit : relancer l\'écriture ensuite'))

            def fix() -> None:
                self.stops_added = add_stops() or []
                self.reject()
            self.stops_btn.clicked.connect(lambda: fix())
        bb.button(QDialogButtonBox.StandardButton.Ok).setText(tr('Écrire le programme'))
        if report.blocking():                            # Entrée : renoncer, pas écrire
            ok = bb.button(QDialogButtonBox.StandardButton.Ok)
            ok.setText(tr('Écrire quand même'))
            ok.setAutoDefault(False)
            ok.setDefault(False)
            bb.button(QDialogButtonBox.StandardButton.Cancel).setDefault(True)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        self.resize(560, 460)

    def skip_next_time(self) -> bool:
        return self.skip.isChecked()
