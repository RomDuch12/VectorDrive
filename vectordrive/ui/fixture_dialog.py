"""Fenêtre « Plaque de reprise : trous de fixation des bruts » (`cam.fixture`, demande du 14/11) : le calque de la
plaque, les bruts (formes choisies ou un calque), les trous de la plaque retenus, les vis par brut, la marge, le
filetage et sa profondeur, le brut retourné ou non pour son taraudage. Le compte des trous suit chaque réglage."""
from __future__ import annotations

from PySide6.QtCore import QLocale
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout, QLabel,
                               QSpinBox, QVBoxLayout)

from ..cam import fixture as FX
from ..i18n import tr

#: retournement du brut pour son taraudage (miroir autour de son centre)
MIRRORS = {'': 'Non, taraudé tel qu\'il est posé', 'x': 'Oui, retourné de gauche à droite',
           'y': 'Oui, retourné de haut en bas'}
#: où vont les vis quand des gravures sont découpées dans le brut (question 45 : selon le cahier des charges du client)
SCREWS = {'': 'Partout sous le brut', 'squelette': 'Dans le squelette, hors de la découpe des gravures',
          'gravures': 'Dans les gravures, taraudées au dos de chacune'}


def mm(value: float) -> str:
    """Une cote dans la langue de l'interface (3,5 en français)."""
    return QLocale().toString(float(value), 'g', 6)


class FixtureDialog(QDialog):
    """`doc` : le dessin ; `spec` : le dernier réglage (`cam.fixture.Spec`) ; `selection` : les objets choisis (les
    bruts, d'office, s'il y a parmi eux des formes fermées)."""

    def __init__(self, parent, doc, spec: FX.Spec, selection=(), placer=None, settings=None, thickness=None):
        super().__init__(parent)
        self.setWindowTitle(tr('Plaque de reprise : trous de fixation des bruts'))
        self.doc = doc
        self.placer, self.settings = placer, settings    # placer(chemin) → calque de la plaque posée, ou None
        self.selection = list(selection or [])
        lay = QVBoxLayout(self)
        intro = QLabel(tr('Les bruts posés sur le dessin de la plaque de reprise y sont vissés par-dessous : sous '
                          'chaque brut, les trous de la plaque qu\'il couvre (à la marge de son bord près) sont les '
                          'places de ses vis. Les plus écartés sont gardés, puis le brut est percé et taraudé à ces '
                          'places. Les trous ajoutés au dessin se déplacent ou s\'effacent ensuite comme les autres '
                          'objets : les opérations les suivent.'))
        intro.setWordWrap(True)
        lay.addWidget(intro)
        form = QFormLayout()
        self.plate = QComboBox()
        self.blank_src = QComboBox()
        self._cache: dict = {}
        best, best_n = None, 0
        for L in doc.layers:
            found = FX.plate_holes(L.items, spec.min_diameter, spec.max_diameter)
            self.plate.addItem(tr('{0} ({1} trous)').format(L.name, len(found)), L.id)
            self.blank_src.addItem(L.name, L.id)
            made = bool(L.extra.get(FX.MADE_KEY))       # un calque de trous de fixation déjà ajouté
            rank = (FX.is_plate_layer(L), len(found))    # une plaque posée passe avant les autres calques
            if found and not made and (best is None or rank > best_n):
                best, best_n = L.id, rank
        if best is not None:
            self.plate.setCurrentIndex(self.plate.findData(best))
        plate = self._layer(best)
        sel_blanks = FX.find_blanks(self.selection, plate.items if plate is not None else [], spec.min_diameter,
                                    spec.max_diameter) if self.selection else []
        if sel_blanks:                                   # les formes choisies d'abord
            self.blank_src.insertItem(0, tr('Les formes choisies ({0})').format(len(sel_blanks)), '')
            self.blank_src.setCurrentIndex(0)
        else:                                            # sinon le premier autre calque
            k = next((i for i in range(self.blank_src.count()) if self.blank_src.itemData(i) != best), 0)
            self.blank_src.setCurrentIndex(k)
        form.addRow(tr('Calque de la plaque'), self.plate)
        from PySide6.QtWidgets import QHBoxLayout, QPushButton, QWidget
        row = QWidget()
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 0, 0, 0)
        self.library = QComboBox()
        for name, path in FX.plate_files(FX.plate_folders(settings)):
            self.library.addItem(name, str(path))
        self.library.setToolTip(tr('Les plaques des dossiers de plaques : le dernier choisi, puis ceux des modules'))
        self.place_btn = QPushButton(tr('Poser'))
        self.place_btn.setToolTip(tr('La plaque sur un calque à elle, verrouillé, jamais usiné : un repère pour poser '
                                     'les bruts'))
        self.place_btn.clicked.connect(lambda: self.place(self.library.currentData()))
        self.other_btn = QPushButton(tr('Autre fichier…'))
        self.other_btn.clicked.connect(lambda: self.place_other())
        h.addWidget(self.library, 1)
        h.addWidget(self.place_btn)
        h.addWidget(self.other_btn)
        form.addRow(tr('Poser une plaque'), row)
        form.addRow(tr('Bruts'), self.blank_src)
        self.dmin, self.dmax = self._spin(spec.min_diameter, 0.0, 100.0), self._spin(spec.max_diameter, 0.0, 100.0)
        form.addRow(QLabel(tr('Trous de la plaque : Ø de (mm)')), self.dmin)
        form.addRow(QLabel(tr('à (mm)')), self.dmax)
        self.common = QCheckBox(tr('Seulement les trous du diamètre le plus fréquent'))
        self.common.setToolTip(tr('Les autres trous de la plaque (sa fixation sur la table, des alésages) ne sont pas des places de vis'))
        self.common.setChecked(bool(spec.common_only))
        self.common.toggled.connect(lambda _on: self.refresh())
        form.addRow(self.common)
        self.per_blank = QSpinBox()
        self.per_blank.setRange(0, 99)
        self.per_blank.setSpecialValueText(tr('tous'))
        self.per_blank.setValue(spec.per_blank)
        self.per_blank.valueChanged.connect(lambda _v: self.refresh())
        form.addRow(tr('Vis par brut'), self.per_blank)
        self.margin = self._spin(spec.margin, 0.0, 100.0)
        form.addRow(QLabel(tr('Marge au bord du brut (mm)')), self.margin)
        self.screws_in = QComboBox()                     # question 45 : la découpe des gravures ne touche pas les vis
        for k, text in SCREWS.items():
            self.screws_in.addItem(tr(text), k)
        self.screws_in.setToolTip(tr('Des gravures découpées dans le brut (la découpe suit le cadre de chacune) : '
                                     'les vis vont dans le squelette qui reste, ou au dos de chaque gravure, selon '
                                     'le cahier des charges du client'))
        self.screws_in.setCurrentIndex(max(0, self.screws_in.findData(spec.screws_in)))
        self.screws_in.currentIndexChanged.connect(lambda _i: self.refresh())
        form.addRow(tr('Les vis vont'), self.screws_in)
        self.cut_width = self._spin(spec.cut_width, 0.0, 50.0)
        self.cut_width.setToolTip(tr('Autour du cadre de chaque gravure : le Ø de l’outil de découpe'))
        form.addRow(QLabel(tr('Largeur de la découpe des gravures (mm)')), self.cut_width)
        self.thread = QComboBox()
        self.thread.addItem(tr('D\'après les trous de la plaque'), '')
        from ..cam.model import THREADS
        for name in THREADS:
            self.thread.addItem(name, name)
        self.thread.setCurrentIndex(max(0, self.thread.findData(spec.thread)))
        self.thread.currentIndexChanged.connect(lambda _i: self.refresh())
        form.addRow(tr('Filetage'), self.thread)
        if thickness is None:                            # sans réglage FAO : la plaque du dessin
            plate_doc = getattr(doc, 'plate', None)
            thickness = float(getattr(plate_doc, 'thickness', 0.0) or 0.0) if plate_doc is not None else 0.0
        #: l'épaisseur du brut ; 0 : inconnue
        self.thickness = max(0.0, float(thickness))
        self.too_thin = False
        self.auto_depth = QCheckBox(tr('Profondeur d’après l’épaisseur du brut'))
        self.auto_depth.setToolTip(tr('Ce qui reste sous l’usinage de la face, moins 0,5 mm, 6 mm au plus : 3,5 mm pour un brut de 7 mm, 6 mm pour 10 mm. Sans effet tant que l’épaisseur du brut n’est pas connue.'))
        self.auto_depth.setChecked(bool(spec.auto_depth))
        self.auto_depth.toggled.connect(lambda _on: self.refresh())
        form.addRow(self.auto_depth)
        self.machined = self._spin(spec.machined, 0.0, 100.0)
        form.addRow(QLabel(tr('Usiné en face (mm)')), self.machined)
        self._depth_set = float(spec.depth)              # la profondeur réglée à la main, gardée sous la case
        self.depth = self._spin(spec.depth, 0.1, 100.0)
        form.addRow(QLabel(tr('Profondeur taraudée (mm)')), self.depth)
        self.extra = self._spin(spec.extra_drill, 0.0, 50.0)
        form.addRow(QLabel(tr('Perçage plus profond de (mm)')), self.extra)
        self.mirror = QComboBox()
        for k, text in MIRRORS.items():
            self.mirror.addItem(tr(text), k)
        self.mirror.setCurrentIndex(max(0, self.mirror.findData(spec.mirror)))
        self.mirror.currentIndexChanged.connect(lambda _i: self.refresh())
        form.addRow(tr('Brut retourné pour son taraudage'), self.mirror)
        lay.addLayout(form)
        self.info = QLabel()
        self.info.setWordWrap(True)
        lay.addWidget(self.info)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        self.ok = bb.button(QDialogButtonBox.StandardButton.Ok)
        self.plate.currentIndexChanged.connect(lambda _i: self.refresh())
        self.blank_src.currentIndexChanged.connect(lambda _i: self.refresh())
        self.placement = None
        self._sync_place()
        self.refresh()

    def _spin(self, value: float, lo: float, hi: float) -> QDoubleSpinBox:
        sp = QDoubleSpinBox()
        sp.setRange(lo, hi)
        sp.setDecimals(2)
        sp.setValue(float(value))
        sp.valueChanged.connect(lambda _v: self.refresh())
        return sp

    def place(self, path) -> bool:
        """La plaque `path` posée (par `placer`) : son calque devient celui de la plaque ; faux si rien n'est posé."""
        if not path or self.placer is None:
            return False
        layer = self.placer(str(path))
        if layer is None:
            return False
        found = FX.plate_holes(layer.items, float(self.dmin.value()), float(self.dmax.value()))
        self.plate.addItem(tr('{0} ({1} trous)').format(layer.name, len(found)), layer.id)
        self.blank_src.addItem(layer.name, layer.id)
        self.plate.setCurrentIndex(self.plate.count() - 1)
        self._cache.clear()
        self.refresh()
        return True

    def place_other(self) -> bool:
        """« Autre fichier… » : une plaque choisie dans la fenêtre de fichiers ; son dossier est retenu."""
        from PySide6.QtWidgets import QFileDialog
        folders = FX.plate_folders(self.settings)
        path, _ = QFileDialog.getOpenFileName(self, tr('Plaque de reprise'), str(folders[0]) if folders else '',
                                              tr('Plaques ({0})').format(' '.join('*' + e for e in FX.PLATE_EXTS)))
        if not path:
            return False
        if not self.place(path):
            return False
        import pathlib
        if self.settings is not None:                    # posée : son dossier retenu, la liste relue
            self.settings.setValue(FX.FOLDER_KEY, str(pathlib.Path(path).parent))
            self.library.clear()
            for name, p in FX.plate_files(FX.plate_folders(self.settings)):
                self.library.addItem(name, str(p))
            self.library.setCurrentIndex(max(0, self.library.findData(str(pathlib.Path(path)))))
            self._sync_place()
        return True

    def _layer(self, layer_id):
        return next((L for L in self.doc.layers if L.id == layer_id), None)

    def plate_layer(self):
        return self._layer(self.plate.currentData())

    def skip(self) -> set:
        """Les cercles des bruts (dans le groupe d'un brut) : pas des trous de la plaque."""
        src = self.blank_src.currentData()
        L = self._layer(src) if src else None
        plate = self.plate_layer()
        where = list(self.selection if not src else (L.items if L is not None else []))
        where += list(plate.items) if plate is not None and plate is not L else []   # les alésages posés sur la plaque
        return FX.skip_for(where, self.blanks())

    def blanks(self) -> list:
        """Les bruts de la source choisie (gardés tant que la source, la plaque et les Ø ne changent pas)."""
        src = self.blank_src.currentData()
        plate = self.plate_layer()
        key = (src, plate.id if plate is not None else '', float(self.dmin.value()), float(self.dmax.value()))
        if key not in self._cache:
            if not src:
                items = self.selection
            else:
                L = self._layer(src)
                items = L.items if L is not None else []
            self._cache[key] = FX.find_blanks(items, plate.items if plate is not None else [], key[2], key[3])
        return self._cache[key]

    def spec(self) -> FX.Spec:
        depth = float(self.depth.value()) if self.depth.isEnabled() else self._depth_set
        return FX.Spec(min_diameter=float(self.dmin.value()), max_diameter=float(self.dmax.value()),
                       per_blank=int(self.per_blank.value()), margin=float(self.margin.value()),
                       mirror=self.mirror.currentData() or '', thread=self.thread.currentData() or '',
                       depth=depth, extra_drill=float(self.extra.value()),
                       common_only=self.common.isChecked(), auto_depth=self.auto_depth.isChecked(),
                       machined=float(self.machined.value()), screws_in=self.screws_in.currentData() or '',
                       cut_width=float(self.cut_width.value()))

    def _sync_depth(self) -> None:
        """Sous la case « d'après l'épaisseur », l'épaisseur connue : la profondeur calculée, montrée, non
        modifiable (`too_thin` : rien à tarauder) ; la profondeur réglée à la main est gardée et revient quand la
        case est décochée."""
        on = self.auto_depth.isChecked() and self.thickness > 0
        auto = FX.depth_for(self.thickness, float(self.machined.value())) if on else 0.0
        self.too_thin = on and not auto
        self.depth.blockSignals(True)
        if on:
            if self.depth.isEnabled():
                self._depth_set = float(self.depth.value())
            if auto:
                self.depth.setValue(auto)
        elif not self.depth.isEnabled():
            self.depth.setValue(self._depth_set)
        self.depth.setEnabled(not on)
        self.depth.blockSignals(False)
        self.machined.setEnabled(on)

    def refresh(self) -> None:
        self._sync_depth()
        plate = self.plate_layer()
        blanks = self.blanks()
        if plate is None or not blanks:
            self.placement = None
            self.info.setText(tr('Choisissez les bruts (formes fermées choisies sur le dessin, ou leur calque) et le '
                                 'calque de la plaque de reprise.'))
            self.ok.setEnabled(False)
            return
        spec = self.spec()
        pl = FX.layout(blanks, plate.items, spec, self.skip(), logos=FX.engraving_items(self.doc))
        self.placement = pl
        self.cut_width.setEnabled(bool(spec.screws_in))
        if pl.screws_in == 'gravures' and pl.frames:
            text = tr('{0} gravures : {1} trous de vis, filetage {2}.').format(len(pl.frames), pl.count(),
                                                                          pl.thread or tr('aucun'))
            if pl.bare():
                text += ' ' + tr('{0} gravures sans aucun trou de la plaque dessous (trop petites, ou à déplacer).').format(len(pl.bare()))
        else:
            text = tr('{0} bruts : {1} trous de vis, filetage {2}.').format(len(pl.blanks), pl.count(),
                                                                           pl.thread or tr('aucun'))
            if pl.screws_in == 'squelette' and pl.frames:
                text += ' ' + tr('{0} gravures découpées : les vis restent hors de leur découpe.').format(len(pl.frames))
        if pl.empty() and not (pl.screws_in == 'gravures' and pl.frames):
            text += ' ' + tr('{0} bruts sans aucun trou de la plaque dessous (trop petits, ou à déplacer).').format(
                len(pl.empty()))
        if not pl.count() and spec.common_only:
            text += ' ' + tr('Si les places de vis ne sont pas les trous les plus nombreux de la plaque, décochez « Seulement les trous du diamètre le plus fréquent ».')
        if pl.count() and not pl.thread:
            text += ' ' + tr('Aucun filetage ne passe dans ces trous : choisissez-le.')
        elif pl.count() and self.too_thin:
            text += ' ' + tr('Le brut ({0} mm) est trop mince pour être taraudé sous {1} mm usinés en face : décochez la profondeur d’après l’épaisseur pour la régler à la main.').format(mm(self.thickness), mm(spec.machined))
        elif pl.count() and FX.predrilled(pl.thread):
            text += ' ' + tr('{0} : perçage à la fraise à {1} mm, puis taraudage à {2} mm.').format(
                pl.thread, mm(spec.drill_on(self.thickness)), mm(spec.depth_on(self.thickness)))
        elif pl.count():
            text += ' ' + tr('{0} : une seule opération à {1} mm, la fraise à fileter perce.').format(
                pl.thread, mm(spec.depth_on(self.thickness)))
        self.extra.setEnabled(not pl.thread or FX.predrilled(pl.thread))     # pas de perçage à part sous M6
        self.info.setText(text)
        self.ok.setEnabled(bool(pl.count() and pl.thread and not self.too_thin))

    def _sync_place(self) -> None:
        self.place_btn.setEnabled(self.placer is not None and self.library.count() > 0)
        self.other_btn.setEnabled(self.placer is not None)
