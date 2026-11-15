"""Mise en forme des textes (la barre « Rapido » de TypeEdit) : onglet du
ruban qui paraît quand des textes sont sélectionnés, et avec l'outil Texte
(le formulaire du texte qui s'écrit, en deux rangées comme le Rapido) —
police, hauteur, largeur, inclinaison, interlettrage, interligne,
espacement des lettres, alignement, ressort, casse, ligne de base,
longueur, largeur imposée, préréglages. Une valeur changée s'applique à
tous les textes sélectionnés (un pas d'annulation), remis en page à la
même place ; sans texte sélectionné, elle va aux nouveaux textes."""
from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QDoubleSpinBox

from ..core.document import Text
from ..i18n import tr


def selected_texts(win) -> list:
    out = []

    def walk(items):
        for it in items:
            if isinstance(it, Text):
                out.append(it)
            elif hasattr(it, 'children'):
                walk(it.children)
    walk(win.canvas.selection)
    return out


class TextFormat:
    """Contrôles de l'onglet Mise en forme (dans la page de ruban `page`). `compact` : les champs et les préréglages
    seulement (onglet Mise en forme de la disposition TypeEdit 13, dont les boutons viennent de TypeEdit)."""

    FIELDS = ('font', 'size', 'width', 'italic', 'spacing', 'line_spacing', 'spacing_mode')

    def __init__(self, win, page, compact: bool = False):
        from ..core import text as TX
        from . import text_presets as TP
        from .dialogs import FontBox
        self.win = win
        self.compact = compact
        self._loading = False
        self.max_length = None
        A = win.A
        self.font = FontBox()
        self.font.setMinimumWidth(180)
        self.font.setToolTip(tr('Police des textes sélectionnés'))
        self.font.activated.connect(lambda _i: self._changed('font', self.font))
        self.font.lineEdit().editingFinished.connect(lambda: self._changed('font', self.font))
        self.size = self._spin(tr('Hauteur '), ' mm', 0.05, 2000, 3, tr('Hauteur des capitales'), 'size')
        self.width = self._spin(tr('Largeur '), ' %', 10, 1000, 1, tr('Largeur des lettres (100 % : la police telle quelle)'),
                                'width')
        self.italic = self._spin(tr('Inclinaison '), ' °', -TX.ITALIC_MAX, TX.ITALIC_MAX, 1,
                                 tr('Inclinaison des lettres (0 : droites ; négative : penchées à gauche)'), 'italic')
        self.spacing = self._spin(tr('Lettres '), ' mm', -100, 100, 3, tr('Interlettrage ajouté entre les lettres'),
                                  'spacing')
        self.line_spacing = self._spin(tr('Lignes '), ' ×', 0.3, 10, 2, tr('Interligne (en hauteurs de capitale)'),
                                       'line_spacing')
        self.spacing_mode = QComboBox()
        for k, label in TP.SPACINGS:
            self.spacing_mode.addItem(tr(label), k)
        self.spacing_mode.setToolTip(tr('Espacement des lettres : typographique (crénage), proportionnel, serré, '
                                        'chasse fixe'))
        self.spacing_mode.activated.connect(lambda _i: self._changed('spacing_mode', self.spacing_mode))
        # largeur imposée (de la fenêtre Texte d'avant) : les lignes du texte tiennent dans cette largeur
        self.fit_width = self._spin(tr('Largeur imposée ') if compact else '', ' mm', 0, 100000, 2,
                                    tr('Largeur imposée des textes sélectionnés : leurs lignes y tiennent (0 : libre ; '
                                       'sans sélection : le prochain texte écrit)'), 'fit_width')
        self.fit_width.setSpecialValueText(tr('Largeur imposée : libre') if compact else tr('libre'))
        self.fit_mode = QComboBox()
        self.fit_mode.addItem(tr('par l\'interlettrage'), 'spacing')
        self.fit_mode.addItem(tr('par étirement des lettres'), 'ratio')
        self.fit_mode.setToolTip(tr('Ajustement à la largeur imposée'))
        self.fit_mode.activated.connect(lambda _i: self._changed('fit_mode', self.fit_mode))
        if compact:                                      # disposition TypeEdit 13 : ses boutons viennent de TypeEdit
            g = page.group(tr('Police'))
            for w in (self.font, self.size, self.width, self.italic):
                g.add_widget(w)
            g = page.group(tr('Espacement'))
            for w in (self.spacing, self.line_spacing, self.spacing_mode, self.fit_width, self.fit_mode):
                g.add_widget(w)
            g.add(A['text_spring'], big=False)
            self._presets_group(page)
            return
        # le formulaire du texte, deux rangées par groupe comme l'onglet Rapido de TypeEdit 13
        g = page.group(tr('Texte'))
        g.add(A['text_back'])
        g.add(A['tool_text'])
        g = self._form_group(page, tr('Général'))
        self._row(g, self.font, A['char_map'], A['font_recognize'], self.spacing, self.line_spacing)
        self._row(g, self.size, self.width, self.italic, self.spacing_mode)
        g = self._form_group(page, tr('Position du texte'))
        self._row(g, *(A[k] for k in ('text_align_left', 'text_align_center', 'text_align_right', 'text_align_justify',
                                      'text_spring', 'text_vertical', 'text_rtl')))
        self._row(g, *(A[k] for k in ('case_upper', 'case_lower', 'case_words', 'case_small', 'case_initial')))
        g = self._form_group(page, tr('Ligne de base'))
        self._row(g, *(A[k] for k in ('text_on_baseline', 'text_under_baseline', 'line_fixed', 'line_prop',
                                      'line_typo')))
        self.max_length = self._spin(tr('Longueur max. '), ' mm', 0, 10000, 2,
                                     tr('Longueur maximale des lignes : un texte plus long est resserré (0 : sans '
                                        'limite)'), 'max_length')
        self._row(g, self.max_length, *(A[k] for k in ('text_compress_line', 'text_compress_para',
                                                       'text_compress_global')))
        g = self._form_group(page, tr('Largeur imposée'))
        self._row(g, self.fit_width)
        self._row(g, self.fit_mode)
        g = self._form_group(page, tr('Outils'))
        self._row(g, A['find_replace'], A['replace_font'])
        self._row(g, A['text_copy_format'])
        self._presets_group(page)

    @staticmethod
    def _form_group(page, title: str):
        g = page.group(title)
        g.rows = 2                                       # deux rangées, comme le Rapido de TypeEdit
        return g

    @staticmethod
    def _row(g, *items) -> None:
        """Une rangée du formulaire : champs et petits boutons côte à côte ; les boutons suivent le groupe (libellés,
        ou icônes seules quand la place manque : le libellé en infobulle)."""
        from PySide6.QtGui import QAction
        from PySide6.QtWidgets import QHBoxLayout, QToolButton, QWidget
        from .ribbon import style_button
        row = QWidget(g.body)
        lay = QHBoxLayout(row)
        lay.setContentsMargins(0, 1, 0, 1)
        lay.setSpacing(2)
        for it in items:
            if isinstance(it, QAction):
                b = QToolButton(row)
                b.setDefaultAction(it)
                b.setAutoRaise(True)
                b.setProperty('ribbon_big', False)
                style_button(b, False, g._small_labels())
                g.row_buttons.append(b)
                it = b
            lay.addWidget(it)
        g.add_widget(row)

    def _presets_group(self, page) -> None:
        """Groupe Préréglages : la liste (choisir : appliqué aux textes sélectionnés, et aux nouveaux textes),
        Enregistrer…, le gestionnaire."""
        g = page.group(tr('Préréglages'))
        self.presets = QComboBox()
        self.presets.setMinimumWidth(150)
        self.presets.setToolTip(tr('Préréglage choisi : appliqué aux textes sélectionnés et pris pour les nouveaux '
                                   'textes'))
        self.presets.activated.connect(lambda i: (self._preset_chosen(i), self.win.typing_focus(self.presets)))
        if self.compact:
            g.add_widget(self.presets)
            g.add(self.win.A['text_preset_save'], big=False)
            g.add(self.win.A['text_styles'], big=False)
        else:
            g.rows = 2
            self._row(g, self.presets)
            self._row(g, self.win.A['text_preset_save'], self.win.A['text_styles'])
        self.fill_presets()

    def _changed(self, field: str, src=None) -> int:
        """Un champ changé à la main : appliqué, puis la frappe revient au texte qui s'écrit (pas quand on vient de
        cliquer dans un autre champ : `src`, le champ changé)."""
        n = self.apply(field)
        self.win.typing_focus(src)
        return n

    def _preset_chosen(self, i: int) -> int:
        name = self.presets.itemData(i)
        return self.win.use_text_preset(name) if name else 0

    def current_format(self) -> dict:
        """La mise en forme montrée : celle du premier texte sélectionné, sinon celle des nouveaux textes."""
        from ..core import text as TX
        from . import text_presets as TP
        texts = selected_texts(self.win)
        return TX.text_format(texts[0]) if texts else TP.new_text_format(self.win.settings)

    def fill_presets(self, fmt: dict | None = None) -> None:
        """La liste des préréglages ; celui qui correspond à la mise en forme montrée est choisi."""
        from . import text_presets as TP
        presets = TP.load(self.win.settings)
        fmt = self.current_format() if fmt is None else fmt
        names = sorted(presets, key=str.casefold)
        cur = str(self.win.settings.value(TP.CURRENT, '') or '')
        match = cur if cur in presets and TP.same(presets[cur], fmt) else \
            next((n for n in names if TP.same(presets[n], fmt)), '')
        self.presets.blockSignals(True)
        try:
            self.presets.clear()
            self.presets.addItem(tr('(aucun)'), '')
            for n in names:
                self.presets.addItem(n, n)
            self.presets.setCurrentIndex(max(0, self.presets.findData(match)))
        finally:
            self.presets.blockSignals(False)

    def _spin(self, prefix, suffix, lo, hi, dec, tip, field):
        sb = QDoubleSpinBox()
        sb.setRange(lo, hi)
        sb.setDecimals(dec)
        sb.setPrefix(prefix)
        sb.setSuffix(suffix)
        sb.setToolTip(tip)
        sb.setKeyboardTracking(False)
        sb.valueChanged.connect(lambda _v, f=field, w=sb: self._changed(f, w))
        return sb

    def refresh(self) -> None:
        """Valeurs du premier texte sélectionné ; sans texte sélectionné, celles des nouveaux textes."""
        from PySide6.QtGui import QFont
        from . import text_presets as TP
        fmt = self.current_format()
        v = TP.values(fmt)
        texts = selected_texts(self.win)
        fit = (texts[0].extra.get('fit') or {}) if texts else (getattr(self.win, 'next_text_fit', None) or {})
        self._loading = True
        try:
            self.fit_width.setValue(float(fit.get('width', 0.0) or 0.0))
            self.fit_mode.setCurrentIndex(max(0, self.fit_mode.findData(fit.get('mode') or 'spacing')))
            self.font.setCurrentFont(QFont(v['font']))
            self.font.setEditText(v['font'])
            self.size.setValue(v['size'])
            self.width.setValue(v['width'])
            self.italic.setValue(v['italic'])
            self.spacing.setValue(v['spacing'])
            self.line_spacing.setValue(v['line_spacing'])
            self.spacing_mode.setCurrentIndex(max(0, self.spacing_mode.findData(v['spacing_mode'])))
            ml = fmt['extra'].get('max_length') or {}
            if self.max_length is not None:
                self.max_length.setValue(float(ml.get('length', 0.0) or 0.0))
                for k, a in (('line', 'text_compress_line'), ('paragraph', 'text_compress_para')):
                    act = self.win.A[a]
                    act.blockSignals(True)
                    act.setChecked((ml.get('by') or 'line') == k)
                    act.blockSignals(False)
            for k, a in (('left', 'text_align_left'), ('center', 'text_align_center'), ('right', 'text_align_right'),
                         ('justify', 'text_align_justify')):
                act = self.win.A[a]
                act.blockSignals(True)
                act.setChecked(v['align'] == k)
                act.blockSignals(False)
        finally:
            self._loading = False
        self.fill_presets(fmt)

    def apply(self, field: str, value=None) -> int:
        """La valeur du contrôle `field` (ou `value`) mise à tous les textes
        sélectionnés ; rend le nombre de textes changés."""
        if self._loading:
            return 0
        if field == 'max_length':
            return self.set_max_length(self.max_length.value() if value is None else value)
        if field == 'fit_width':
            return self.set_fit(self.fit_width.value() if value is None else value,
                                self.fit_mode.currentData() or 'spacing')
        if field == 'fit_mode':
            return self.set_fit(None, (self.fit_mode.currentData() or 'spacing') if value is None else value)
        from ..core import text as TX
        from ..core.document import drop_source_object
        texts = selected_texts(self.win)
        if value is None:
            value = {'font': lambda: self.font.currentText().strip(), 'size': self.size.value,
                     'width': lambda: self.width.value() / 100.0, 'spacing': self.spacing.value,
                     'line_spacing': self.line_spacing.value, 'italic': self.italic.value,
                     'spacing_mode': lambda: self.spacing_mode.currentData() or 'typo'}[field]()
        if not texts:
            return self._set_default(field, value)
        if field in ('italic', 'spacing_mode'):
            return self._apply_extra(texts, field, value)
        attr = {'width': 'width_ratio'}.get(field, field)        # 'align' : valeur donnée
        todo = [t for t in texts if getattr(t, attr) != value and not (field in ('size', 'width') and 'box' in t.extra)]
        if not todo or (field == 'font' and not value):
            return 0
        self.win.push_undo(tr('Mise en forme du texte'))
        for t in todo:
            setattr(t, attr, value)
            if field in ('spacing', 'width'):
                t.extra.pop('fit', None)             # une largeur imposée reprendrait la main
            if field == 'line_spacing':
                t.extra.pop('line_mode', None)       # la valeur donnée remplace le mode d'interligne
            t.outline = TX.outline_for(t)
            drop_source_object(t)
        self.win.canvas.invalidate()
        self.win._on_selection()
        self.win._on_doc_changed()
        return len(todo)

    def _set_default(self, field: str, value) -> int:
        """Sans texte sélectionné, la valeur va aux nouveaux textes (comme les champs Rapido de TypeEdit, réglés
        avant de cliquer) ; rend 0 (aucun texte changé)."""
        from . import text_presets as TP
        if field == 'font' and not value:
            return 0
        settings = self.win.settings
        fmt = TP.new_text_format(settings)
        new = TP.with_value(fmt, {'width': 'width_ratio'}.get(field, field), value)
        if TP.same(new, fmt):
            return 0
        TP.set_new_text_format(settings, new, '')
        self.win.refresh_text_bars()
        return 0

    def _apply_extra(self, texts: list, field: str, value) -> int:
        """Inclinaison (°, 0 : droit) ou espacement des lettres des textes sélectionnés ; rend leur nombre."""
        from ..core import text as TX
        from ..core.document import drop_source_object

        def now(t):
            return float(t.extra.get('italic') or 0.0) if field == 'italic' else t.extra.get('spacing_mode', 'typo')
        if field == 'italic':
            value = max(-TX.ITALIC_MAX, min(TX.ITALIC_MAX, float(value)))
        todo = [t for t in texts if now(t) != value]
        if not todo:
            return 0
        self.win.push_undo(tr('Mise en forme du texte'))
        for t in todo:
            if (abs(value) > 1e-9) if field == 'italic' else value != 'typo':
                t.extra[field] = value
            else:
                t.extra.pop(field, None)
            t.outline = TX.outline_for(t)
            drop_source_object(t)
        self.win.canvas.invalidate()
        self.win._on_selection()
        self.win._on_doc_changed()
        return len(todo)

    def set_fit(self, width=None, mode: str | None = None) -> int:
        """Largeur imposée (mm, 0 : libre ; None : celle de chaque texte) et ajustement ('spacing' : par
        l'interlettrage, 'ratio' : par étirement des lettres ; None : celui de chaque texte) des textes sélectionnés
        posés en ligne droite, hors cadre ; rend leur nombre. Sans texte sélectionné : pour le prochain texte écrit."""
        from ..core import text as TX
        from ..core.document import drop_source_object
        texts = selected_texts(self.win)
        if not texts:
            nxt = getattr(self.win, 'next_text_fit', None) or {}
            w = float(nxt.get('width', 0.0) if width is None else width)
            self.win.next_text_fit = {'width': w, 'mode': mode or nxt.get('mode') or 'spacing'} if w > 0 else None
            return 0
        todo = []
        for t in texts:
            if t.extra.get('box') or t.extra.get('on_path') is not None or t.extra.get('arc') or t.extra.get('arc_warp'):
                continue
            cur = t.extra.get('fit') or {}
            w0, m0 = float(cur.get('width', 0.0) or 0.0), cur.get('mode') or 'spacing'
            w = w0 if width is None else max(0.0, float(width))
            m = m0 if mode is None else mode
            if (w, m if w > 0 else '') != (w0, m0 if w0 > 0 else ''):
                todo.append((t, w, m, m0))
        if not todo:
            return 0
        self.win.push_undo(tr('Largeur imposée'))
        for t, w, m, m0 in todo:
            if w > 0:
                t.extra['fit'] = {'width': w, 'mode': m}
            else:                                        # libre : la police telle quelle
                t.extra.pop('fit', None)
                if TX.SPRING not in t.text:              # la largeur imposée réglait interlettrage et étirement
                    t.spacing, t.width_ratio = 0.0, 1.0  # (une lettre seule s'étire même par l'interlettrage)
            t.outline = TX.outline_for(t)
            drop_source_object(t)
        self.win.canvas.invalidate()
        self.win._on_selection()
        self.win._on_doc_changed()
        return len(todo)

    def set_max_length(self, length=None, by: str | None = None) -> int:
        """Longueur maximale (mm, 0 : sans limite ; None : celle de chaque
        texte) et compression ('line' ou 'paragraph' ; None : celle de chaque
        texte) des textes sélectionnés, comme TypeEdit ; la compression
        appliquée s'affiche. Rend le nombre de textes changés."""
        from ..core import text as TX
        from ..core.document import drop_source_object
        todo = []
        for t in selected_texts(self.win):
            cur = dict(t.extra.get('max_length') or {})
            new = {'length': float(cur.get('length', 0.0) if length is None else length),
                   'by': by or cur.get('by') or 'line'}
            if new != {'length': float(cur.get('length', 0.0) or 0.0), 'by': cur.get('by') or 'line'}:
                todo.append((t, new))
        return self._set_lengths(todo)

    def set_global_compression(self, percent: float) -> int:
        """Chaque texte sélectionné tient dans ce pourcentage de sa plus longue ligne, toutes ses lignes du même facteur."""
        from ..core import text as TX
        todo = []
        for t in selected_texts(self.win):
            width = TX.natural_width(t)
            if width > 0:
                todo.append((t, {'length': width * float(percent) / 100.0, 'by': 'paragraph'}))
        return self._set_lengths(todo)

    def _set_lengths(self, todo: list) -> int:
        from ..core import text as TX
        from ..core.document import drop_source_object
        if not todo:
            return 0
        self.win.push_undo(tr('Longueur maximale du texte'))
        for t, new in todo:
            if new['length'] <= 0 and new['by'] == 'line':
                t.extra.pop('max_length', None)
            else:
                t.extra['max_length'] = new
            t.outline = TX.outline_for(t)
            drop_source_object(t)
        self.win.canvas.invalidate()
        self.win._on_selection()
        self.win._on_doc_changed()
        ratios = TX.compression(todo[0][0])
        if ratios:
            self.win.statusBar().showMessage(tr('Compression appliquée : {0} %').format(round(min(ratios) * 100)), 5000)
        return len(todo)
