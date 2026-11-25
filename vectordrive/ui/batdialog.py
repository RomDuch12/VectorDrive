"""BAT : cartouche et mise en page réglables, avec aperçu de la page."""
from __future__ import annotations

import dataclasses

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPixmap, QTransform
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFileDialog, QFormLayout,
                               QGroupBox, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QPlainTextEdit, QPushButton,
                               QSpinBox, QVBoxLayout, QWidget)

from ..i18n import tr
from ..io import proof

PREVIEW_W, PREVIEW_H = 520, 400


def render_page(doc, info: proof.ProofInfo, w: int = PREVIEW_W, h: int = PREVIEW_H, items=None) -> QPixmap:
    """Aperçu de la page BAT (mêmes primitives que le PDF et l'impression)."""
    prims, PW, PH = proof.build(doc, info, items)
    return paint_page(prims, PW, PH, w, h)


#: au-delà de ce nombre d'objets, la page de l'aperçu est calculée dans un fil (fenêtre sans gel)
ASYNC_ITEMS = 2000


def page_job(doc, info, items):
    """(primitives, largeur, hauteur, libellé d'échelle) de la page — dans le fil de l'aperçu."""
    prims, PW, PH = proof.build(doc, info, items)
    g = proof._geometry(doc, info, items)
    return prims, PW, PH, ' + '.join(proof.scale_label(v['k']) for v in g['views'])


def paint_page(prims, PW: float, PH: float, w: int = PREVIEW_W, h: int = PREVIEW_H) -> QPixmap:
    """La page peinte (fil de l'interface : QPixmap)."""
    from .printing import paint_prims
    pm = QPixmap(w, h)
    pm.fill(QColor('#8a919c'))
    k = min((w - 16) / PW, (h - 16) / PH)
    ox, oy = (w - PW * k) / 2, (h - PH * k) / 2
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    p.fillRect(int(ox) + 3, int(oy) + 3, int(PW * k), int(PH * k), QColor(0, 0, 0, 70))
    p.fillRect(int(ox), int(oy), int(PW * k), int(PH * k), QColor('white'))
    paint_prims(p, prims, QTransform(k, 0, 0, -k, ox, oy + PH * k), min_pen=0.6 / k)       # mm, y vers le haut
    p.end()
    return pm


class BatDialog(QDialog):
    """Cartouche (client, référence…) et mise en page (format, orientation,
    échelle, marge, éléments affichés) ; aperçu mis à jour en direct."""

    TEXT = (('client', 'Client'), ('reference', 'Référence'), ('designation', 'Désignation'),
            ('material', 'Matière'), ('bat_number', 'BAT n°'), ('author', 'Établi par'), ('date', 'Date'),
            ('company', 'Entreprise (en-tête)'))
    LOGOS_KEY = 'bat/logos'                              # les logos déjà employés
    COPIES_KEY = 'bat/logos_copies'                      # {logo d'origine : nom de sa copie de « Logos BAT »}, en JSON
    LOGOS_MAX = 12
    PRESETS_KEY = 'bat/presets'                          # préréglages de l'utilisateur : {nom: réglages}, en JSON

    def __init__(self, parent, doc, info: proof.ProofInfo, items=None):
        super().__init__(parent)
        from .fit import no_hscroll
        no_hscroll(self)                                 # pas de défilement horizontal à l'ouverture
        self.setWindowTitle(tr('BAT (bon à tirer)'))
        self.doc = doc
        self.items = list(items or [])
        self.info = dataclasses.replace(info)
        lay = QHBoxLayout(self)
        left = QVBoxLayout()
        lay.addLayout(left)
        # cartouche et mise en page : dans un volet qui défile quand l'écran est plus petit qu'eux ; les boutons, eux,
        # restent sous le volet, toujours visibles
        col = QWidget()
        options = QVBoxLayout(col)
        options.setContentsMargins(0, 0, 0, 0)
        g1 = QGroupBox(tr('Cartouche'))
        f1 = QFormLayout(g1)
        self.edits = {}
        for key, label in self.TEXT:
            e = QLineEdit(str(getattr(info, key)))
            e.textChanged.connect(self._later)
            f1.addRow(tr(label), e)
            self.edits[key] = e
        self.notes = QPlainTextEdit(info.notes)
        self.notes.setFixedHeight(64)
        self.notes.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.notes.setToolTip(tr('Le texte passe à la ligne tout seul, ici comme sur le BAT ; Entrée commence une '
                                 'nouvelle ligne'))
        self.notes.textChanged.connect(self._later)
        f1.addRow(tr('Remarques'), self.notes)
        options.addWidget(g1)
        g2 = QGroupBox(tr('Mise en page'))
        f2 = QFormLayout(g2)
        n = len(self.items)
        self.content = self._combo([('auto', tr('La sélection ({0} objet(s))').format(n) if n
                                     else tr('Tout le dessin (rien n\'est sélectionné)')),
                                    ('tout', tr('Tout le dessin, sur sa plaque'))],
                                   'tout' if info.content == 'tout' else 'auto')
        self.content.setEnabled(bool(n))
        f2.addRow(tr('Contenu'), self.content)
        self.fit = QCheckBox(tr('Sélection ajustée à la page'))
        self.fit.setChecked(bool(info.fit_selection))
        self.fit.setToolTip(tr('La sélection remplit la feuille (l\'échelle est écrite sur le BAT)'))
        self.fit.toggled.connect(self._later)
        f2.addRow(self.fit)
        self.page = self._combo([(k, k) for k in proof.PAGES], info.page)
        f2.addRow(tr('Format'), self.page)
        self.orient = self._combo([('auto', tr('Selon le dessin')), ('portrait', tr('Portrait')),
                                   ('paysage', tr('Paysage'))], info.orientation)
        f2.addRow(tr('Orientation'), self.orient)
        self.mode = self._combo([('vues', tr('1:1 cotée + agrandissement ou réduction')),
                                 ('reelle', tr('Taille réelle (réduite si besoin)')),
                                 ('normalisee', tr('Échelle normalisée (agrandit les petits dessins)')),
                                 ('ajuster', tr('Ajustée à la page')),
                                 ('imposee', tr('Imposée'))], info.scale_mode)
        f2.addRow(tr('Échelle'), self.mode)
        self.scale = QDoubleSpinBox()
        self.scale.setRange(0.001, 1000)
        self.scale.setDecimals(3)
        self.scale.setValue(float(info.scale))
        self.scale.setToolTip(tr('Facteur page / réel : 2 = 2:1, 1 = 1:1, 0,5 = 1:2'))
        self.scale.valueChanged.connect(self._later)
        f2.addRow(tr('Échelle imposée'), self.scale)
        self.enlarge_below = QDoubleSpinBox()
        self.enlarge_below.setRange(0, 1000)
        self.enlarge_below.setDecimals(1)
        self.enlarge_below.setSuffix(' mm')
        self.enlarge_below.setValue(float(info.enlarge_below))
        self.enlarge_below.setToolTip(tr('Une pièce plus petite reçoit aussi une vue agrandie'))
        self.enlarge_below.valueChanged.connect(self._later)
        f2.addRow(tr('Agrandissement sous'), self.enlarge_below)
        self.enlarge = QCheckBox(tr('Toujours ajouter une vue agrandie'))
        self.enlarge.setChecked(bool(info.enlarge))
        self.enlarge.toggled.connect(self._later)
        f2.addRow(self.enlarge)
        self.margin = QDoubleSpinBox()
        self.margin.setRange(0, 60)
        self.margin.setSuffix(' mm')
        self.margin.setValue(float(info.margin))
        self.margin.valueChanged.connect(self._later)
        f2.addRow(tr('Marge'), self.margin)
        self.checks = {}
        for key, label in (('title_block', 'Cartouche'), ('dims', 'Cotes d\'encombrement'),
                           ('legend', 'Légende des outils'), ('mono', 'Noir et blanc'),
                           ('fill', 'Coloriage (contours fermés remplis)'),
                           ('dims_each', 'Une cote par gravure'), ('show_bruts', 'Bruts des ensembles, cotés à part'),
                           ('prices', 'Prix du devis par gravure'), ('price_page', 'Prix sur une page à part')):
            c = QCheckBox(tr(label))
            c.setChecked(bool(getattr(info, key)))
            c.toggled.connect(self._later)
            f2.addRow(c)
            self.checks[key] = c
        self.checks['dims'].setToolTip(tr('Plusieurs gravures cotées une à une (« Une cote par gravure ») : '
                                          'pas de cote de l\'ensemble'))
        self.checks['dims_each'].setToolTip(tr('Chaque gravure cotée à côté d\'elle, jusqu\'à {0} gravures ; au-delà, le '
                                               'dessin est coté comme un tout').format(proof.MAX_ENGRAVINGS))
        self.checks['price_page'].setToolTip(tr('Quand un plugin de devis en donne une : la page technique sans '
                                                'les prix, puis une page des prix'))
        from ..plugins import REGISTRY                   # sans plugin qui donne une page des prix : sans effet, grisé
        self.checks['price_page'].setEnabled(bool(REGISTRY.bat_pages) and self.checks['prices'].isChecked())
        self.checks['prices'].toggled.connect(
            lambda on: self.checks['price_page'].setEnabled(bool(REGISTRY.bat_pages) and on))
        self.fill_mode = self._combo([('contour', tr('Couleur des contours (pleins et vides alternés)')),
                                      ('noir', tr('Logo en noir (contours fermés : pleins et vides alternés)')),
                                      ('teinte', tr('Teinte claire de la couleur de l\'outil'))],
                                     getattr(info, 'fill_mode', 'contour'))
        self.fill_mode.setToolTip(tr('Un contour fermé dans un autre est vide, le suivant plein… Les traits ouverts '
                                     'ne sont pas remplis'))
        f2.addRow(tr('Coloriage'), self.fill_mode)
        self.decimals = QSpinBox()
        self.decimals.setRange(0, 4)
        try:
            self.decimals.setValue(int(info.decimals))
        except (TypeError, ValueError):
            self.decimals.setValue(2)
        self.decimals.setSuffix(tr(' décimale(s)'))
        self.decimals.valueChanged.connect(self._later)
        f2.addRow(tr('Précision des cotes'), self.decimals)
        self.keep_zeros = QCheckBox(tr('Garder les zéros de la fin (12,50)'))
        self.keep_zeros.setChecked(bool(info.keep_zeros))
        self.keep_zeros.toggled.connect(self._later)
        f2.addRow(self.keep_zeros)
        cur = getattr(info, 'title_color', '') or ''
        choices = [('', tr('Noir')), ('logo', tr('Prise sur le logo')), ('#1f4e9c', tr('Bleu')), ('#b22222', tr('Rouge')),
                   ('#2e7d32', tr('Vert')), ('#d46a00', tr('Orange')), ('#6b6b6b', tr('Gris'))]
        if cur and cur not in [v for v, _t in choices]:
            choices.append((cur, cur))
        self.title_color = self._combo(choices + [('?', tr('Autre couleur…'))], cur)
        self.title_color.activated.connect(self._pick_title_color)
        f2.addRow(tr('Couleur du cartouche'), self.title_color)
        self.theme_all = QCheckBox(tr('Thème : cette couleur aussi pour le cadre, l\'en-tête et les cotes'))
        self.theme_all.setChecked(bool(info.theme_all))
        self.theme_all.toggled.connect(self._later)
        f2.addRow(self.theme_all)
        self.logo = self._logo_combo(info.logo)
        f2.addRow(tr('Logo (à gauche)'), self.logo)
        self.logo2 = self._logo_combo(info.logo2)
        f2.addRow(tr('Second logo (à droite)'), self.logo2)
        options.addWidget(g2)
        from .fit import VScroll
        self.options_scroll = VScroll(col)
        left.addWidget(self.options_scroll, 1)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        #: « Imprimer… » : ce BAT envoyé à l'imprimante (aperçu d'abord) au lieu du PDF
        self.print_requested = False
        self.print_btn = bb.addButton(tr('Imprimer…'), QDialogButtonBox.ButtonRole.ActionRole)
        self.print_btn.setToolTip(tr('Imprimer ce BAT (F10 › Impression : aperçu, imprimante retenue)'))
        self.print_btn.clicked.connect(self.request_print)
        left.addWidget(bb)
        right = QVBoxLayout()
        lay.addLayout(right)
        g0 = QGroupBox(tr('Préréglages et clients'))
        f0 = QFormLayout(g0)
        row = QHBoxLayout()
        self.preset = QComboBox()
        self.preset.setToolTip(tr('Mise en page, couleurs, entreprise et logo, filigrane… gardés sous un nom et repris '
                                  'd\'un clic'))
        self.preset.activated.connect(self._preset_chosen)
        self.preset_save = QPushButton(tr('Enregistrer…'))
        self.preset_save.clicked.connect(lambda: self.save_preset())
        self.preset_del = QPushButton(tr('Supprimer'))
        self.preset_del.clicked.connect(self.remove_preset)
        row.addWidget(self.preset, 1)
        row.addWidget(self.preset_save)
        row.addWidget(self.preset_del)
        f0.addRow(tr('Préréglage'), row)
        row = QHBoxLayout()
        self.client_book = QComboBox()
        self.client_book.setToolTip(tr('Choisir un client écrit son nom dans le cartouche et pose son logo à droite de '
                                       'l\'en-tête'))
        self.client_book.activated.connect(self._client_chosen)
        self.client_save = QPushButton(tr('Garder ce client'))
        self.client_save.setToolTip(tr('Le client du cartouche et le second logo sont gardés dans le carnet ; le logo '
                                       'y est copié, quel que soit son format'))
        self.client_save.clicked.connect(self.save_client)
        self.client_del = QPushButton(tr('Retirer'))
        self.client_del.clicked.connect(self.remove_client)
        row.addWidget(self.client_book, 1)
        row.addWidget(self.client_save)
        row.addWidget(self.client_del)
        f0.addRow(tr('Carnet de clients'), row)
        right.addWidget(g0)
        self._mem_presets: dict = {}
        self._fill_presets()
        self._fill_clients()
        self.preview = QLabel()
        self.preview.setFixedSize(PREVIEW_W, PREVIEW_H)
        right.addWidget(self.preview)
        self.scale_info = QLabel()
        right.addWidget(self.scale_info)
        g3 = QGroupBox(tr('Filigrane et PDF'))
        f3 = QFormLayout(g3)
        self.watermark = QCheckBox(tr('Filigrane en fond du dessin'))
        self.watermark.setChecked(bool(getattr(info, 'watermark', False)))
        self.watermark.setToolTip(tr('Un texte ou un logo, clair, sous le dessin — répété en biais ou un seul au '
                                     'milieu : à l’aperçu, à l’impression et dans le PDF'))
        self.watermark.toggled.connect(self._later)
        f3.addRow(self.watermark)
        self.watermark_text = QLineEdit(str(getattr(info, 'watermark_text', '') or ''))
        self.watermark_text.setPlaceholderText(tr('Le nom de l\'entreprise'))
        self.watermark_text.textChanged.connect(self._later)
        f3.addRow(tr('Texte du filigrane'), self.watermark_text)
        wcur = str(getattr(info, 'watermark_color', '') or '')
        wchoices = [('', tr('Celle du cartouche')), ('#1f4e9c', tr('Bleu')), ('#b22222', tr('Rouge')),
                    ('#2e7d32', tr('Vert')), ('#d46a00', tr('Orange')), ('#6b6b6b', tr('Gris'))]
        if wcur and wcur not in [v for v, _t in wchoices]:
            wchoices.append((wcur, wcur))
        self.watermark_color = self._combo(wchoices + [('?', tr('Autre couleur…'))], wcur)
        self.watermark_color.activated.connect(self._pick_watermark_color)
        f3.addRow(tr('Couleur du filigrane'), self.watermark_color)
        self.watermark_kind = self._combo([('texte', tr('Le texte')), ('logo', tr('Un logo'))],
                                          getattr(info, 'watermark_kind', 'texte') or 'texte')
        f3.addRow(tr('Motif du filigrane'), self.watermark_kind)
        self.watermark_logo = self._logo_combo(str(getattr(info, 'watermark_logo', '') or ''))
        self.watermark_logo.setItemText(0, tr('Celui de l’en-tête'))
        self.watermark_logo.setToolTip(tr('Image ou dessin, tout entier dans la couleur du filigrane (le blanc d’une '
                                          'image disparaît)'))
        f3.addRow(tr('Logo du filigrane'), self.watermark_logo)

        def spin(value, lo, hi, suffix, dec, tip):
            s = QDoubleSpinBox()
            s.setRange(lo, hi)
            s.setDecimals(dec)
            s.setSuffix(suffix)
            s.setToolTip(tip)
            try:
                s.setValue(float(value))
            except (TypeError, ValueError):
                pass
            s.valueChanged.connect(self._later)
            return s
        self.watermark_size = spin(getattr(info, 'watermark_size', 9.0), *proof.WATERMARK_SIZE, ' mm', 1,
                                   tr('Hauteur du texte ; un logo : le double'))
        f3.addRow(tr('Taille du filigrane'), self.watermark_size)
        self.watermark_angle = spin(getattr(info, 'watermark_angle', 30.0), *proof.WATERMARK_ANGLE, ' °', 1,
                                    tr('0 : à l’horizontale ; négatif : penché vers le bas'))
        f3.addRow(tr('Angle du filigrane'), self.watermark_angle)
        self.watermark_gap = spin(getattr(info, 'watermark_gap', 10.0), *proof.WATERMARK_GAP, ' mm', 1,
                                  tr('Entre deux motifs d’une rangée ; entre deux rangées : 0,4 fois autant'))
        f3.addRow(tr('Écart du filigrane'), self.watermark_gap)
        self.watermark_strength = QSpinBox()
        self.watermark_strength.setRange(*proof.WATERMARK_STRENGTH)
        self.watermark_strength.setSuffix(' %')
        self.watermark_strength.setToolTip(tr('100 % : la couleur même ; peu : très clair'))
        try:
            self.watermark_strength.setValue(int(getattr(info, 'watermark_strength', 20)))
        except (TypeError, ValueError):
            self.watermark_strength.setValue(20)
        self.watermark_strength.valueChanged.connect(self._later)
        f3.addRow(tr('Intensité du filigrane'), self.watermark_strength)
        self.watermark_layout = self._combo([('trame', tr('Répété en quinconce')), ('centre', tr('Un seul, au milieu'))],
                                            getattr(info, 'watermark_layout', 'trame') or 'trame')
        f3.addRow(tr('Disposition du filigrane'), self.watermark_layout)
        self.as_image = QCheckBox(tr('PDF : dessin en image (tracé non récupérable)'))
        self.as_image.setChecked(bool(getattr(info, 'as_image', False)))
        self.as_image.setToolTip(tr('Les vues, les cotes et le filigrane sont écrits en image : le client voit le '
                                    'dessin mais ne peut pas en récupérer le tracé. Le cartouche reste net.'))
        self.as_image.toggled.connect(self._later)
        # cocher le filigrane coche l'image : c'est elle qui retire le tracé du PDF (on peut la décocher ensuite)
        self.watermark.toggled.connect(lambda on: self.as_image.setChecked(True) if on else None)
        f3.addRow(self.as_image)
        self.image_dpi = QSpinBox()
        self.image_dpi.setRange(*proof.IMAGE_DPI)
        self.image_dpi.setSingleStep(50)
        self.image_dpi.setSuffix(' dpi')
        try:
            self.image_dpi.setValue(int(getattr(info, 'image_dpi', 300)))
        except (TypeError, ValueError):
            self.image_dpi.setValue(300)
        f3.addRow(tr('Résolution de l\'image'), self.image_dpi)
        self.open_folder = QCheckBox(tr('Ouvrir le dossier du PDF une fois écrit'))
        self.open_folder.setChecked(bool(getattr(info, 'open_folder', False)))
        f3.addRow(self.open_folder)
        right.addWidget(g3)
        right.addStretch(1)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.refresh)
        self.refresh()
        self.fit_to_screen()

    def fit_to_screen(self) -> tuple:
        """Taille de la fenêtre à l'ouverture : celle de tous ses réglages quand l'écran les contient ; sinon la
        hauteur de sa zone de travail — les réglages défilent alors, les boutons restent visibles. Rend (l, h)."""
        from PySide6.QtWidgets import QApplication
        parent = self.parentWidget()
        screen = (parent.screen() if parent is not None else None) or QApplication.primaryScreen()
        hint = self.sizeHint()
        room = screen.availableGeometry().height() - 48 if screen is not None else hint.height()   # titre et cadre
        size = (hint.width(), max(240, min(hint.height(), room)))
        self.resize(*size)
        return size

    def _pick_title_color(self, index: int) -> None:
        """« Autre couleur… » : couleur choisie, ajoutée à la liste."""
        if self.title_color.itemData(index) != '?':
            return
        from PySide6.QtWidgets import QColorDialog
        prev = self.info.title_color or '#1f4e9c'
        c = QColorDialog.getColor(QColor(prev), self, tr('Couleur du cartouche'))
        value = c.name() if c.isValid() else (self.info.title_color or '')
        k = self.title_color.findData(value)
        if k < 0:
            k = self.title_color.count() - 1
            self.title_color.insertItem(k, value, value)
        self.title_color.setCurrentIndex(k)

    def _pick_watermark_color(self, index: int) -> None:
        """« Autre couleur… » du filigrane : couleur choisie, ajoutée à la liste."""
        if self.watermark_color.itemData(index) != '?':
            return
        from PySide6.QtWidgets import QColorDialog
        prev = getattr(self.info, 'watermark_color', '') or '#1f4e9c'
        c = QColorDialog.getColor(QColor(prev), self, tr('Couleur du filigrane'))
        value = c.name() if c.isValid() else (getattr(self.info, 'watermark_color', '') or '')
        k = self.watermark_color.findData(value)
        if k < 0:
            k = self.watermark_color.count() - 1
            self.watermark_color.insertItem(k, value, value)
        self.watermark_color.setCurrentIndex(k)

    # --- préréglages de l'utilisateur -------------------------------------------------------------------
    def _presets(self) -> dict:
        import json
        s = getattr(self.parent(), 'settings', None)
        if s is None:
            return dict(self._mem_presets)
        try:
            d = json.loads(str(s.value(self.PRESETS_KEY, '') or '{}'))
            return d if isinstance(d, dict) else {}
        except (ValueError, TypeError):
            return {}

    def _store_presets(self, presets: dict) -> None:
        import json
        s = getattr(self.parent(), 'settings', None)
        if s is None:
            self._mem_presets = dict(presets)
        else:
            s.setValue(self.PRESETS_KEY, json.dumps(presets, ensure_ascii=False))

    def _fill_presets(self, select: str = '') -> None:
        self.preset.blockSignals(True)
        self.preset.clear()
        self.preset.addItem(tr('— choisir —'), '')
        for name in sorted(self._presets(), key=str.lower):
            self.preset.addItem(name, name)
        self.preset.setCurrentIndex(max(0, self.preset.findData(select)) if select else 0)
        self.preset.blockSignals(False)
        self.preset_del.setEnabled(bool(self.preset.currentData()))

    def _preset_chosen(self, index: int) -> None:
        name = self.preset.itemData(index)
        self.preset_del.setEnabled(bool(name))
        if name:
            self.load_layout(self._presets().get(name) or {})

    def save_preset(self, name: str | None = None) -> str:
        """Les réglages du moment gardés sous `name` (demandé s'il n'est pas donné). Rend le nom, '' si abandonné."""
        if name is None:
            name, ok = QInputDialog.getText(self, tr('Préréglage du BAT'), tr('Nom du préréglage :'),
                                            text=str(self.preset.currentData() or ''))
            if not ok:
                return ''
        name = str(name).strip()
        if not name:
            return ''
        presets = self._presets()
        presets[name] = proof.preset_of(self.result_info())
        self._store_presets(presets)
        self._fill_presets(name)
        return name

    def remove_preset(self) -> None:
        name = self.preset.currentData()
        if not name:
            return
        presets = self._presets()
        presets.pop(name, None)
        self._store_presets(presets)
        self._fill_presets()

    def load_layout(self, values: dict) -> None:
        """Les réglages `values` (ceux d'un préréglage) posés dans la fenêtre ; ce qu'ils ne nomment pas reste."""
        import pathlib

        def pick(box, v, label=None):
            k = box.findData(v)
            if k < 0 and v not in (None, ''):            # couleur ou logo hors de la liste : ajouté avant « Autre… »
                k = max(0, box.count() - 1)
                box.insertItem(k, label or str(v), v)
            box.setCurrentIndex(max(0, k))
        for key, box in (('page', self.page), ('orientation', self.orient), ('scale_mode', self.mode),
                         ('fill_mode', self.fill_mode), ('title_color', self.title_color),
                         ('watermark_color', self.watermark_color), ('watermark_kind', self.watermark_kind),
                         ('watermark_layout', self.watermark_layout)):
            if key in values:
                pick(box, values[key] or '')
        for key, box in (('logo', self.logo), ('watermark_logo', self.watermark_logo)):
            if key in values:
                v = self.stored_logo(str(values[key] or ''))             # (l'original disparu : sa copie gardée)
                pick(box, v, pathlib.Path(v).name)
        for key, spin in (('scale', self.scale), ('enlarge_below', self.enlarge_below), ('margin', self.margin),
                          ('decimals', self.decimals), ('image_dpi', self.image_dpi),
                          ('watermark_size', self.watermark_size), ('watermark_angle', self.watermark_angle),
                          ('watermark_gap', self.watermark_gap), ('watermark_strength', self.watermark_strength)):
            if key in values:
                try:
                    spin.setValue(type(spin.value())(values[key]))
                except (TypeError, ValueError):
                    pass
        boxes = dict(self.checks, enlarge=self.enlarge, keep_zeros=self.keep_zeros, theme_all=self.theme_all,
                     watermark=self.watermark, as_image=self.as_image, open_folder=self.open_folder)
        for key, c in boxes.items():
            if key in values:
                c.setChecked(values[key] in (True, 'true', 1))
        if 'company' in values:
            self.edits['company'].setText(str(values['company'] or ''))
        if 'watermark_text' in values:
            self.watermark_text.setText(str(values['watermark_text'] or ''))
        self._later()

    # --- carnet de clients --------------------------------------------------------------------------------
    def _clients_dir(self):
        from ..io import clients as CL
        return CL.folder(getattr(self.parent(), 'settings', None))

    def _fill_clients(self, select: str = '') -> None:
        from ..io import clients as CL
        self.client_book.blockSignals(True)
        self.client_book.clear()
        self.client_book.addItem(tr('— choisir un client —'), '')
        for c in CL.load(self._clients_dir()):
            self.client_book.addItem(str(c['nom']), str(c['nom']))
        self.client_book.setCurrentIndex(max(0, self.client_book.findData(select)) if select else 0)
        self.client_book.blockSignals(False)
        self.client_del.setEnabled(bool(self.client_book.currentData()))

    def _client_chosen(self, index: int) -> None:
        """Le client choisi : son nom dans le cartouche, son logo à droite de l'en-tête."""
        from ..io import clients as CL
        name = self.client_book.itemData(index)
        self.client_del.setEnabled(bool(name))
        c = CL.find(self._clients_dir(), name) if name else None
        if c is None:
            return
        self.edits['client'].setText(str(c['nom']))
        self.set_logo(self.logo2, CL.logo_path(self._clients_dir(), c))
        self._later()

    def save_client(self) -> str:
        """Le client du cartouche et le second logo gardés dans le carnet (le logo y est copié). Rend son nom."""
        from ..io import clients as CL
        name = self.edits['client'].text().strip()
        if not name:
            self.scale_info.setText(tr('Carnet de clients : écrire d\'abord le nom du client dans le cartouche'))
            return ''
        logo = self.logo2.currentData()
        try:
            c = CL.add(self._clients_dir(), name, '' if logo in (None, '?') else str(logo))
        except (OSError, ValueError) as ex:
            self.scale_info.setText(tr('Carnet de clients : {0}').format(ex))
            return ''
        self._fill_clients(str(c['nom']))
        kept = CL.logo_path(self._clients_dir(), c)
        if kept:
            self.set_logo(self.logo2, kept)              # le BAT emploie désormais la copie du carnet
        return str(c['nom'])

    def remove_client(self) -> None:
        from ..io import clients as CL
        name = self.client_book.currentData()
        if name:
            CL.remove(self._clients_dir(), name)
            self._fill_clients()

    def _recent_logos(self) -> list:
        s = getattr(self.parent(), 'settings', None)
        v = s.value(self.LOGOS_KEY, []) if s is not None else []
        if isinstance(v, str):
            v = [v] if v else []
        return [str(x) for x in (v or [])]

    def _logo_copies(self) -> dict:
        """{logo d'origine (chemin normalisé) : nom de sa copie dans « Logos BAT »}, pour les derniers employés."""
        import json
        s = getattr(self.parent(), 'settings', None)
        try:
            d = json.loads(str(s.value(self.COPIES_KEY, '') or '{}')) if s is not None else {}
        except ValueError:
            d = {}
        return {str(k): str(v) for k, v in d.items()} if isinstance(d, dict) else {}

    def stored_logo(self, path: str) -> str:
        """Le fichier à employer pour le logo `path` : lui-même tant qu'il est là, sur un disque du poste ; disparu
        (déplacé, renommé), ou sur un partage (pas lu : hors d'atteinte, il figerait la fenêtre) : sa copie de
        « Logos BAT », si elle existe."""
        import os
        from .symbols import is_remote, logo_library
        if not path or path == '?' or (not is_remote(path) and os.path.isfile(path)):
            return path
        name = self._logo_copies().get(os.path.normcase(path))
        kept = logo_library() / name if name else None
        return str(kept) if kept is not None and kept.is_file() else path

    def logo_choices(self, current: str = '') -> list:
        """Les logos proposés : celui en cours, les derniers employés (un original disparu remplacé par sa copie),
        puis les autres logos gardés dans « Logos BAT » — jamais l'original et sa copie à la fois."""
        import os
        from .symbols import logo_exts, logo_library
        paths = self._recent_logos()
        if current and current not in paths:
            paths.insert(0, current)
        copies = self._logo_copies()
        out, seen, same = [], set(), set()
        for p in paths:
            same.add(str(copies.get(os.path.normcase(p), '')).lower())      # sa copie : pas proposée en plus
            p = self.stored_logo(p)
            if os.path.normcase(p) not in seen:
                seen.add(os.path.normcase(p))
                out.append(p)
        exts = logo_exts()
        try:
            kept = sorted((f for f in logo_library().iterdir() if f.suffix.lower() in exts and f.is_file()),
                          key=lambda f: f.name.lower())
        except OSError:                                  # pas encore de logo gardé
            kept = []
        return out + [str(f) for f in kept if os.path.normcase(str(f)) not in seen and f.name.lower() not in same]

    def _logo_combo(self, current: str) -> QComboBox:
        import pathlib
        current = self.stored_logo(current)
        c = self._combo([('', tr('Aucun'))] + [(p, pathlib.Path(p).name) for p in self.logo_choices(current)]
                        + [('?', tr('Choisir un fichier…'))], current or '')
        for k in range(1, c.count() - 1):                # (deux logos de même nom : la bulle dit lequel)
            c.setItemData(k, c.itemData(k), Qt.ItemDataRole.ToolTipRole)
        c.activated.connect(lambda index, box=c: self._pick_logo(box, index))
        return c

    def _pick_logo(self, box: QComboBox, index: int) -> None:
        """« Choisir un fichier… » : image ou dessin, ajouté à la liste."""
        if box.itemData(index) != '?':
            return
        path, _ = QFileDialog.getOpenFileName(self, tr('Logo'), '',
                                              tr('Images et dessins') + f' ({proof.logo_filter()})')
        self.set_logo(box, path)

    def set_logo(self, box: QComboBox, path: str) -> None:
        import pathlib
        k = box.findData(path) if path else 0
        if k < 0:
            k = box.count() - 1
            box.insertItem(k, pathlib.Path(path).name, path)
        box.setCurrentIndex(max(0, k))

    def remember_logos(self) -> list:
        """Les logos employés reviennent dans les listes des prochains BAT, et chacun est copié une fois dans
        « Logos BAT » de la bibliothèque interne : il reste disponible même si l'original bouge. Rend les erreurs de
        copie (jamais levées : le BAT se fait) ; `logos_copied` : le nombre de copies faites cette fois."""
        import json
        import os
        import pathlib
        from .symbols import keep_copy, logo_library
        self.logos_copied = 0
        s = getattr(self.parent(), 'settings', None)
        if s is None:
            return []
        used = [v for v in (self.info.logo, self.info.logo2, getattr(self.info, 'watermark_logo', '')) if v]
        used = list(dict.fromkeys(used))                 # (le même logo en en-tête et en filigrane : une fois)
        recent = (used + [p for p in self._recent_logos() if p not in used])[:self.LOGOS_MAX]
        s.setValue(self.LOGOS_KEY, recent)
        copies, errors, made = self._logo_copies(), [], []
        folder = logo_library()
        for p in used:
            try:
                kept = keep_copy(p, folder, made)
            except OSError as ex:
                errors.append(f'{pathlib.Path(p).name} ({ex})')
                continue
            if kept is not None and os.path.normcase(str(kept)) != os.path.normcase(p):
                copies[os.path.normcase(p)] = kept.name
        keys = {os.path.normcase(p) for p in recent}     # (seuls les derniers employés ont besoin de leur copie)
        s.setValue(self.COPIES_KEY, json.dumps({k: v for k, v in copies.items() if k in keys}, ensure_ascii=False))
        self.logos_copied = len(made)
        return errors

    def request_print(self) -> None:
        self.print_requested = True
        self.accept()

    def _combo(self, items, current) -> QComboBox:
        c = QComboBox()
        for value, text in items:
            c.addItem(text, value)
        c.setCurrentIndex(max(0, c.findData(current)))
        c.currentIndexChanged.connect(self._later)
        return c

    def _later(self, *_a) -> None:
        self._timer.start(120)

    def result_info(self) -> proof.ProofInfo:
        i = self.info
        for key, e in self.edits.items():
            setattr(i, key, e.text())
        i.notes = self.notes.toPlainText()
        i.page, i.orientation, i.scale_mode = self.page.currentData(), self.orient.currentData(), self.mode.currentData()
        i.content, i.fit_selection = self.content.currentData(), self.fit.isChecked()
        i.enlarge_below, i.enlarge = self.enlarge_below.value(), self.enlarge.isChecked()
        i.scale, i.margin = self.scale.value(), self.margin.value()
        for key, c in self.checks.items():
            setattr(i, key, c.isChecked())
        i.fill_mode = self.fill_mode.currentData() or 'contour'
        i.decimals, i.keep_zeros, i.theme_all = self.decimals.value(), self.keep_zeros.isChecked(), self.theme_all.isChecked()
        for box, key in ((self.logo, 'logo'), (self.logo2, 'logo2'), (self.watermark_logo, 'watermark_logo')):
            v = box.currentData()
            if v != '?':
                setattr(i, key, v or '')
        col = self.title_color.currentData()
        i.title_color = col if col != '?' else (i.title_color or '')
        i.watermark, i.watermark_text = self.watermark.isChecked(), self.watermark_text.text().strip()
        wcol = self.watermark_color.currentData()
        i.watermark_color = wcol if wcol != '?' else (getattr(i, 'watermark_color', '') or '')
        i.watermark_kind = self.watermark_kind.currentData() or 'texte'
        i.watermark_layout = self.watermark_layout.currentData() or 'trame'
        i.watermark_size, i.watermark_angle = self.watermark_size.value(), self.watermark_angle.value()
        i.watermark_gap, i.watermark_strength = self.watermark_gap.value(), int(self.watermark_strength.value())
        i.as_image, i.image_dpi = self.as_image.isChecked(), int(self.image_dpi.value())
        i.open_folder = self.open_folder.isChecked()
        return i

    def refresh(self) -> None:
        info = self.result_info()
        sel = proof.uses_selection(info, self.items)
        self.fit.setEnabled(sel)
        self.fill_mode.setEnabled(info.fill)
        self.title_color.setEnabled((info.title_block or info.theme_all) and not info.mono)
        self.theme_all.setEnabled(not info.mono)
        self.keep_zeros.setEnabled(info.decimals > 0)
        self.watermark_text.setEnabled(info.watermark)  # avec un logo : le motif si le logo manque
        self.watermark_color.setEnabled(info.watermark and not info.mono)
        self.watermark_logo.setEnabled(info.watermark and info.watermark_kind == 'logo')
        for w in (self.watermark_kind, self.watermark_size, self.watermark_angle, self.watermark_strength,
                  self.watermark_layout):
            w.setEnabled(info.watermark)
        self.watermark_gap.setEnabled(info.watermark and info.watermark_layout == 'trame')
        self.image_dpi.setEnabled(info.as_image)
        self.mode.setEnabled(not (sel and info.fit_selection))
        self.scale.setEnabled(info.scale_mode == 'imposee' and self.mode.isEnabled())
        vues = info.scale_mode == 'vues' and self.mode.isEnabled()
        self.enlarge_below.setEnabled(vues)
        self.enlarge.setEnabled(vues)
        if sum(1 for _ in self.doc.iter_leaves()) > ASYNC_ITEMS:
            self._refresh_later(info)                 # gros dessin : page calculée dans un fil
            return
        try:
            self.preview.setPixmap(render_page(self.doc, info, items=self.items))
            self.scale_info.setText(tr('Échelle du dessin sur la page : {0}').format(self.current_scale(info)))
        except Exception as ex:                       # aperçu seulement : jamais bloquant
            self.scale_info.setText(str(ex))

    def _refresh_later(self, info) -> None:
        import copy
        from concurrent.futures import ThreadPoolExecutor
        from PySide6.QtCore import QTimer
        if getattr(self, '_ppool', None) is None:
            self._ppool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='apercu_bat')
            self._ptimer = QTimer(self)
            self._ptimer.setInterval(50)
            self._ptimer.timeout.connect(self._page_ready)
        self._pgen = getattr(self, '_pgen', 0) + 1
        self.scale_info.setText(tr('Aperçu en cours…'))
        self._pjob = (self._pgen, self._ppool.submit(page_job, self.doc, copy.copy(info), self.items))
        self._ptimer.start()

    def _page_ready(self) -> None:
        job = getattr(self, '_pjob', None)
        if job is None or not job[1].done():
            return
        self._ptimer.stop()
        self._pjob = None
        gen, fut = job
        if gen != self._pgen:
            return
        try:
            prims, PW, PH, scale = fut.result()
            self.preview.setPixmap(paint_page(prims, PW, PH))
            self.scale_info.setText(tr('Échelle du dessin sur la page : {0}').format(scale))
        except Exception as ex:                       # aperçu seulement : jamais bloquant
            self.scale_info.setText(str(ex))

    def current_scale(self, info) -> str:
        g = proof._geometry(self.doc, info, self.items)
        return ' + '.join(proof.scale_label(v['k']) for v in g['views'])
