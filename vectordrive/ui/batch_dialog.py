"""Traitement par lots : fichiers ou dossiers, format de sortie, dossier
de sortie ; conversion avec barre de progression et Annuler, compte rendu."""
from __future__ import annotations

import pathlib

from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
                               QHBoxLayout, QLabel, QLineEdit, QListWidget, QMessageBox, QPlainTextEdit,
                               QPushButton, QToolButton, QVBoxLayout, QWidget)

from ..i18n import tr
from ..io import batch


class BatchDialog(QDialog):
    def __init__(self, win, parent=None):
        super().__init__(parent or win)
        from .fit import no_hscroll
        no_hscroll(self)                                 # pas de défilement horizontal à l'ouverture
        self.win = win
        self.setWindowTitle(tr('Traitement par lots'))
        self.resize(760, 560)
        st = win.settings
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(tr('Dessins à convertir (fichiers, ou dossiers et leurs sous-dossiers) :')))
        self.list = QListWidget()
        lay.addWidget(self.list, 1)
        row = QHBoxLayout()
        for text, slot in ((tr('Ajouter des fichiers…'), self.add_files), (tr('Ajouter un dossier…'), self.add_folder),
                           (tr('Retirer'), self.remove), (tr('Vider'), self.list.clear)):
            b = QPushButton(text)
            b.clicked.connect(lambda _=False, s=slot: s())
            row.addWidget(b)
        row.addStretch(1)
        lay.addLayout(row)
        form = QFormLayout()
        self.fmt = QComboBox()
        for f in batch.writable_formats():
            self.fmt.addItem(f'{f.label} ({f.extensions[0]})', f.key)
        self.fmt.setCurrentIndex(max(0, self.fmt.findData(st.value('lots/format', 'dxf'))))
        form.addRow(tr('Convertir en'), self.fmt)
        out = QWidget()
        orow = QHBoxLayout(out)
        orow.setContentsMargins(0, 0, 0, 0)
        self.out = QLineEdit(str(st.value('lots/dossier', '') or ''))
        b = QToolButton()
        b.setText('…')
        b.clicked.connect(self._choose_out)
        orow.addWidget(self.out, 1)
        orow.addWidget(b)
        form.addRow(tr('Dossier de sortie'), out)
        self.tree = QCheckBox(tr('Garder l\'arborescence des dossiers'))
        self.tree.setChecked(True)
        form.addRow(self.tree)
        self.overwrite = QCheckBox(tr('Remplacer les fichiers existants'))
        form.addRow(self.overwrite)
        self.proof = QCheckBox(tr('Faire aussi le BAT PDF de chaque dessin'))
        form.addRow(self.proof)
        lay.addLayout(form)
        # programmes en série (demande du 14/11) : un modèle d'usinage appliqué à chaque dessin, son programme écrit
        prog = QFormLayout()
        title = QLabel('<b>' + tr('Programmes machine en série') + '</b>')
        title.setToolTip(tr('Chaque dessin reçoit le modèle d\'usinage, ses parcours sont calculés et son programme '
                            'est écrit dans le dossier de sortie (sans dossier : à côté du dessin). Les dessins ne '
                            'sont jamais réécrits.'))
        prog.addRow(title)
        self.template = QComboBox()
        self.template.addItem(tr('Les opérations de chaque dessin'), '')
        from ..cam import templates as TPL
        found = TPL.all_templates()
        for name in sorted(found, key=lambda n: n.lower()):
            self.template.addItem(name, name)
        self._templates = {n: t for n, (_origin, t) in found.items()}
        self.template.setCurrentIndex(max(0, self.template.findData(str(st.value('lots/modele', '') or ''))))
        prog.addRow(tr('Modèle d\'usinage'), self.template)
        self.post = QComboBox()
        self.post.addItem(tr('Celui de chaque dessin'), '')
        from ..cam import post as POST
        panel = getattr(win, 'cam_panel', None)
        self.machines_dir = panel.machines_dir() if panel is not None and hasattr(panel, 'machines_dir') else ''
        for key, label in POST.posts(self.machines_dir).items():
            self.post.addItem(str(label), key)
        self.post.setCurrentIndex(max(0, self.post.findData(str(st.value('lots/post', '') or ''))))
        prog.addRow(tr('Post-processeur'), self.post)
        self.replace = QCheckBox(tr('Le modèle remplace les opérations du dessin'))
        self.replace.setToolTip(tr('Décoché : les opérations du modèle s\'ajoutent à celles du dessin'))
        self.replace.setChecked(str(st.value('lots/remplacer', 'true')) in ('true', 'True', '1'))
        prog.addRow(self.replace)
        self.template.currentIndexChanged.connect(lambda _i: self._sync_series())
        self._sync_series()
        lay.addLayout(prog)
        self.report = QPlainTextEdit()
        self.report.setReadOnly(True)
        self.report.setMaximumHeight(140)
        lay.addWidget(self.report)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        go = bb.addButton(tr('Convertir'), QDialogButtonBox.ButtonRole.ActionRole)
        go.clicked.connect(self.run)
        chk = bb.addButton(tr('Vérifier seulement'), QDialogButtonBox.ButtonRole.ActionRole)
        chk.setToolTip(tr('Lire chaque dessin sans rien écrire : objets, contours, remarques, erreurs '
                          '(rapport CSV dans le dossier de sortie s\'il est choisi)'))
        chk.clicked.connect(self.check)
        self.go_programs = bb.addButton(tr('Écrire les programmes'), QDialogButtonBox.ButtonRole.ActionRole)
        self.go_programs.setToolTip(tr('Programmes machine en série : le modèle d\'usinage appliqué à chaque dessin'))
        self.go_programs.clicked.connect(self.programs)
        self.open_out = bb.addButton(tr('Ouvrir le dossier de sortie'), QDialogButtonBox.ButtonRole.ActionRole)
        self.open_out.setToolTip(tr('Montrer les fichiers produits dans l\'explorateur'))
        self.open_out.clicked.connect(self.reveal_out)
        self.out.textChanged.connect(self._out_changed)
        self._out_changed()
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        self._root = None

    def _sync_series(self) -> None:
        self.replace.setEnabled(bool(self.template.currentData()))

    def programs(self):
        """Programmes en série (`cam.series`) : le modèle choisi appliqué à chaque dessin, son programme écrit ;
        compte rendu dans la fenêtre. Rend le `SeriesResult` (None : rien fait)."""
        from ..cam import series
        from .progress import Cancelled, run
        sources = [self.list.item(i).text() for i in range(self.list.count())]
        files = batch.collect(sources)
        if not files:
            QMessageBox.information(self, tr('Traitement par lots'), tr('Aucun dessin lisible à convertir.'))
            return None
        name = self.template.currentData() or ''
        tpl = self._templates.get(name) if name else None
        out = self.out.text().strip()
        st = self.win.settings
        st.setValue('lots/modele', name)
        st.setValue('lots/post', self.post.currentData() or '')
        st.setValue('lots/remplacer', 'true' if self.replace.isChecked() else 'false')
        if out:
            st.setValue('lots/dossier', out)
        dirs = [pathlib.Path(p) for p in sources if pathlib.Path(p).is_dir()]
        root = dirs[0] if out and self.tree.isChecked() and len(dirs) == 1 else None
        try:
            res = run(self, tr('Programmes en série'), series.programs, files, out, tpl, self.post.currentData() or '',
                      replace=self.replace.isChecked(), overwrite=self.overwrite.isChecked(), keep_tree_from=root,
                      machines_dir=self.machines_dir, default_post=str(st.value('fao/post', '') or ''),
                      dates=st.value('fao/dates', 'true') in (True, 'true'))
        except Cancelled:
            self.report.setPlainText(tr('Traitement annulé : les programmes des dessins déjà traités sont écrits.'))
            return None
        lines = [tr('{0} programme(s) écrit(s), {1} ignoré(s), {2} erreur(s)').format(
            len(res.done), len(res.skipped), len(res.errors))]
        lines += [f'⚠ {pathlib.Path(s).name} : {m}' for s, m in res.errors]
        lines += [f'— {pathlib.Path(s).name} : {m}' for s, m in res.skipped]
        lines += [f'• {pathlib.Path(s).name} : {w}' for s, w in res.warnings[:40]]
        self.report.setPlainText('\n'.join(lines))
        self._out_changed()
        return res

    def _out_changed(self, *_a) -> None:
        d = self.out.text().strip()
        self.open_out.setEnabled(bool(d) and pathlib.Path(d).is_dir())

    def reveal_out(self) -> bool:
        from .reveal import reveal
        d = self.out.text().strip()
        return bool(d) and reveal(d)

    def add_paths(self, paths) -> None:
        have = {self.list.item(i).text() for i in range(self.list.count())}
        for p in paths:
            if str(p) not in have:
                self.list.addItem(str(p))

    def add_files(self) -> None:
        from ..io import registry
        files, _ = QFileDialog.getOpenFileNames(self, tr('Dessins à convertir'), '', registry.filter_string())
        self.add_paths(files)

    def add_folder(self) -> None:
        d = QFileDialog.getExistingDirectory(self, tr('Dossier de dessins'))
        if d:
            self.add_paths([d])

    def remove(self) -> None:
        for it in self.list.selectedItems():
            self.list.takeItem(self.list.row(it))

    def _choose_out(self) -> None:
        d = QFileDialog.getExistingDirectory(self, tr('Dossier de sortie'), self.out.text())
        if d:
            self.out.setText(d)

    def check(self) -> list | None:
        """Vérification seule ; rapport à l'écran (et CSV dans le dossier de sortie)."""
        from .progress import Cancelled, run
        files = batch.collect([self.list.item(i).text() for i in range(self.list.count())], programs=True)
        if not files:
            QMessageBox.information(self, tr('Traitement par lots'), tr('Aucun dessin lisible à convertir.'))
            return None
        try:
            rows = run(self, tr('Vérification des dessins'), batch.check, files)
        except Cancelled:
            self.report.setPlainText(tr('Traitement annulé'))
            return None
        lines = [batch.check_summary(rows)]
        for r in rows:
            name = pathlib.Path(r['fichier']).name
            if not r['lu']:
                lines.append(f'⚠ {name} : {r["erreur"]}')
            elif r['remarques']:
                lines.append(f'• {name} : {r["objets"]} objets — {r["remarque"]}')
        out = self.out.text().strip()
        if out:
            csv_path = batch.write_csv(rows, pathlib.Path(out) / 'verification.csv')
            lines.insert(1, tr('Rapport : {0}').format(csv_path))
        self.report.setPlainText('\n'.join(lines))
        return rows

    def run(self) -> batch.BatchResult | None:
        from .progress import Cancelled, run
        sources = [self.list.item(i).text() for i in range(self.list.count())]
        files = batch.collect(sources)
        if not files:
            QMessageBox.information(self, tr('Traitement par lots'), tr('Aucun dessin lisible à convertir.'))
            return None
        out = self.out.text().strip()
        if not out:
            QMessageBox.information(self, tr('Traitement par lots'), tr('Choisissez le dossier de sortie.'))
            return None
        st = self.win.settings
        st.setValue('lots/format', self.fmt.currentData())
        st.setValue('lots/dossier', out)
        dirs = [pathlib.Path(p) for p in sources if pathlib.Path(p).is_dir()]
        root = dirs[0] if self.tree.isChecked() and len(dirs) == 1 else None
        try:
            from .options import value
            res = run(self, tr('Traitement par lots'), batch.convert, files, out, self.fmt.currentData(),
                      overwrite=self.overwrite.isChecked(), proof=self.proof.isChecked(), keep_tree_from=root,
                      live_texts=value(st, 'vnd/textes_vivants'))
        except Cancelled:
            self.report.setPlainText(tr('Traitement annulé'))
            return None
        lines = [tr('{0} converti(s), {1} ignoré(s), {2} erreur(s)').format(len(res.done), len(res.skipped),
                                                                            len(res.errors))]
        lines += [f'⚠ {pathlib.Path(s).name} : {m}' for s, m in res.errors]
        lines += [f'— {pathlib.Path(s).name} : {m}' for s, m in res.skipped]
        self.report.setPlainText('\n'.join(lines))
        self._out_changed()                              # le dossier existe maintenant
        return res
