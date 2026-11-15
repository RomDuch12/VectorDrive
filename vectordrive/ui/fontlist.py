"""La liste des polices dépliée d'une `FontBox` : haute comme la fenêtre, une recherche (plusieurs mots, sans casse ni
accents), des filtres (toutes, favorites, intégrées, lues par un plugin, SVG, système) et des favorites marquées d'une
étoile (un clic sur l'étoile ; gardées dans les réglages, en tête de la liste). Chaque police du système est montrée
dans son propre dessin. « Reconnaître la sélection » : les polices les plus proches des lettres en courbes
sélectionnées (`core.fontmatch`), parmi celles du filtre choisi, en tête de la liste."""
from __future__ import annotations

import threading
import unicodedata

from PySide6.QtCore import QEvent, QObject, QPoint, QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QGuiApplication, QPalette
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QButtonGroup, QFrame, QHBoxLayout, QLabel, QLineEdit,
                               QListWidget, QListWidgetItem, QSpinBox, QStyle, QStyledItemDelegate,
                               QStyleOptionViewItem, QToolButton, QVBoxLayout)

from ..i18n import tr

#: réglages : les favorites (liste de noms), le dernier filtre choisi
FAVORITES_KEY = 'polices/favorites'
FILTER_KEY = 'polices/filtre'
#: réglage : nombre de polices proposées par la reconnaissance
COUNT_KEY = 'polices/propositions'
#: rôles des éléments : nom de la police (None : titre de section), sa catégorie, sa proximité (reconnaissance)
NAME_ROLE = Qt.ItemDataRole.UserRole
KIND_ROLE = Qt.ItemDataRole.UserRole + 1
PROX_ROLE = Qt.ItemDataRole.UserRole + 2
#: catégories des polices, dans l'ordre de la liste (rôle KIND_ROLE des éléments de la FontBox)
KINDS = (('integree', 'Intégrées à VectorDrive'), ('plugin', 'Lues par un plugin'), ('svg', 'Polices SVG'),
         ('systeme', 'Polices du système'))
FILTERS = (('toutes', 'Toutes'), ('favorites', '★ Favorites'), ('integree', 'Intégrées'), ('plugin', 'Plugins'),
           ('svg', 'SVG'), ('systeme', 'Système'))
#: largeur de la colonne de l'étoile, largeur minimale de la liste, fenêtre trop basse pour la liste (px)
STAR_W = 24
MIN_W = 420
MIN_AREA_H = 480
#: hauteur sous la liste déroulante qui suffit à la liste ; en dessous, elle s'ouvre du côté où il y a le plus de place
#: (px) — jamais sur la liste déroulante : un second clic sur sa flèche la referme
MIN_BELOW = 360
SAMPLE = 'AaBbCc 0123'
STAR_COLOR = QColor(230, 165, 0)


def fold(s: str) -> str:
    """Pour la recherche : sans casse ni accents."""
    return ''.join(c for c in unicodedata.normalize('NFKD', s.casefold()) if not unicodedata.combining(c))


def matches(name: str, query: str) -> bool:
    """Tous les mots de la recherche sont dans le nom (sans casse ni accents)."""
    n = fold(name)
    return all(w in n for w in fold(query).split())


def _settings(settings=None):
    if settings is not None:
        return settings
    from .. import portable
    return portable.settings()


def favorites(settings=None) -> list[str]:
    """Les polices favorites, dans l'ordre où elles ont été marquées."""
    v = _settings(settings).value(FAVORITES_KEY, [])
    if isinstance(v, str):                            # une seule : relue comme un texte
        v = [v] if v else []
    return [str(x) for x in (v or []) if str(x)]


def set_favorites(names, settings=None) -> None:
    s = _settings(settings)
    s.setValue(FAVORITES_KEY, [str(n) for n in names])
    s.sync()


def screen_of(widget):
    """L'écran où est la liste déroulante (pas celui où est la plus grande part de sa fenêtre)."""
    at = QGuiApplication.screenAt(widget.mapToGlobal(widget.rect().center()))
    return at or widget.screen() or QApplication.primaryScreen()


def area_for(widget) -> QRect:
    """Où la liste peut s'étendre (coordonnées de l'écran) : la fenêtre de la liste déroulante, ou celle d'où elle a
    été ouverte si elle est trop basse (une petite fenêtre de réglages) et que la liste déroulante est devant elle,
    sinon l'écran (en plein écran : tout l'écran)."""
    scr = screen_of(widget)
    screen = scr.availableGeometry()
    at = widget.mapToGlobal(widget.rect().center())
    w = widget.window()
    seen = set()
    while w is not None and id(w) not in seen:
        seen.add(id(w))
        if w.isVisible() and w.geometry().height() >= MIN_AREA_H:
            r = w.geometry().intersected(scr.geometry() if w.isFullScreen() else screen)
            if not r.isEmpty() and r.contains(at):
                return r
            break                                         # la liste déroulante hors de cette fenêtre : l'écran
        p = w.parentWidget()
        w = p.window() if p is not None else None
    return screen


def proposal_count(settings=None) -> int:
    """Le nombre de polices proposées par la reconnaissance (réglage, 5 d'office)."""
    from ..core import fontmatch
    try:
        n = int(_settings(settings).value(COUNT_KEY, fontmatch.DEFAULT_COUNT))
    except (TypeError, ValueError):
        n = fontmatch.DEFAULT_COUNT
    return min(50, max(1, n))


class _Relay(QObject):
    """Du fil de la reconnaissance à la liste : l'avancement, le résultat (rangés selon leur jeton)."""
    progress = Signal(object, int, int)
    done = Signal(object, object)


class _Delegate(QStyledItemDelegate):
    """Une police : l'étoile (favorite ou non), son nom, puis un échantillon dans son dessin (polices du système) ou sa
    nature (les autres) ; un titre de section en gras, souligné."""

    def __init__(self, popup):
        super().__init__(popup.list)
        self.popup = popup

    def sizeHint(self, option, index):                  # noqa: N802 (API Qt)
        h = option.fontMetrics.height()
        return QSize(100, h + (8 if index.data(NAME_ROLE) is None else 12))

    def paint(self, painter, option, index):
        name = index.data(NAME_ROLE)
        r = option.rect
        pal = option.palette
        painter.save()
        try:
            if name is None:
                f = QFont(option.font)
                f.setBold(True)
                painter.setFont(f)
                painter.setPen(pal.color(QPalette.ColorRole.Text))
                painter.drawText(r.adjusted(6, 0, -6, 0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                                 str(index.data(Qt.ItemDataRole.DisplayRole) or ''))
                painter.setPen(pal.color(QPalette.ColorRole.PlaceholderText))   # lisible aussi en thème sombre
                painter.drawLine(r.left() + 4, r.bottom(), r.right() - 4, r.bottom())
                return
            opt = QStyleOptionViewItem(option)
            self.initStyleOption(opt, index)
            opt.text = ''
            style = opt.widget.style() if opt.widget is not None else QApplication.style()
            style.drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, painter, opt.widget)
            selected = bool(option.state & QStyle.StateFlag.State_Selected)
            fg = pal.color(QPalette.ColorRole.HighlightedText if selected else QPalette.ColorRole.Text)
            fav = name in self.popup.favs
            # étoile pleine : dorée, sur la ligne choisie de la couleur de son texte (surbrillance ambre des thèmes) ;
            # vide : grisée, lisible aussi en thème sombre
            painter.setPen((fg if selected else STAR_COLOR) if fav else
                           (fg if selected else pal.color(QPalette.ColorRole.PlaceholderText)))
            painter.drawText(QRect(r.left(), r.top(), STAR_W, r.height()), Qt.AlignmentFlag.AlignCenter,
                             '★' if fav else '☆')
            left = r.left() + STAR_W + 2
            room = r.right() - 6 - left
            fm = option.fontMetrics
            name_w = int(min(fm.horizontalAdvance(name) + 2, room * 0.55))
            painter.setPen(fg)
            painter.setFont(option.font)
            painter.drawText(QRect(left, r.top(), name_w, r.height()),
                             Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                             fm.elidedText(name, Qt.TextElideMode.ElideRight, name_w))
            sx = left + name_w + 14
            right = r.right() - 6
            prox = index.data(PROX_ROLE)
            if prox is not None:                          # proposée par la reconnaissance : sa proximité
                pct = tr('{0} %').format(round(float(prox) * 100))
                pw = fm.horizontalAdvance(pct) + 4
                painter.setPen(fg if selected else pal.color(QPalette.ColorRole.PlaceholderText))
                painter.drawText(QRect(right - pw, r.top(), pw, r.height()),
                                 Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, pct)
                painter.setPen(fg)
                right -= pw + 8
            sample = QRect(sx, r.top(), right - sx, r.height())
            if sample.width() < 24:
                return
            if index.data(KIND_ROLE) == 'systeme':
                f = QFont(name)
                if option.font.pointSizeF() > 0:
                    f.setPointSizeF(option.font.pointSizeF() * 1.15)
                painter.setFont(f)
                painter.drawText(sample, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                                 QFontMetrics(f).elidedText(SAMPLE, Qt.TextElideMode.ElideRight, sample.width()))
            else:
                hint = str(index.data(Qt.ItemDataRole.ToolTipRole) or '')
                f = QFont(option.font)
                if f.pointSizeF() > 0:
                    f.setPointSizeF(f.pointSizeF() * 0.9)
                painter.setFont(f)
                painter.setPen(fg if selected else pal.color(QPalette.ColorRole.PlaceholderText))
                painter.drawText(sample, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                                 QFontMetrics(f).elidedText(hint, Qt.TextElideMode.ElideRight, sample.width()))
        finally:
            painter.restore()


class FontPopup(QFrame):
    """La liste dépliée d'une FontBox (`box`) ; `picked(nom)` quand une police est choisie."""

    picked = Signal(str)

    def __init__(self, box):
        # rattachée à la fenêtre de la liste déroulante : une feuille de style posée sur celle-ci (le gris des
        # « valeurs différentes ») ne passe pas à la liste ; une liste déroulante sans fenêtre : à elle-même
        win = box.window()
        super().__init__(win if win is not box else box, Qt.WindowType.Popup)
        self.box = box
        self.favs: set = set()
        self._star_press = False
        self._list_press = False                          # un bouton enfoncé dans la liste (sinon : glissé depuis la
        #                                                   liste déroulante, relâché sur une police : choisie)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(4)
        self.search = QLineEdit(self)
        self.search.setPlaceholderText(tr('Rechercher une police (un ou plusieurs mots)'))
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(lambda _t: self.refill())
        self.search.installEventFilter(self)
        lay.addWidget(self.search)
        row = QHBoxLayout()
        row.setSpacing(2)
        self.filters = QButtonGroup(self)
        self.filters.setExclusive(True)
        self.filter_buttons = {}
        for key, label in FILTERS:
            b = QToolButton(self)
            b.setText(tr(label))
            b.setCheckable(True)
            b.setAutoRaise(True)
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            self.filters.addButton(b)
            self.filter_buttons[key] = b
            row.addWidget(b)
        row.addStretch(1)
        self.filters.buttonClicked.connect(lambda _b: self._filter_changed())
        lay.addLayout(row)
        rec = QHBoxLayout()
        rec.setSpacing(4)
        self.recognize_button = QToolButton(self)
        self.recognize_button.setText(tr('Reconnaître la sélection'))
        self.recognize_button.setToolTip(tr('Les polices les plus proches des lettres en courbes sélectionnées dans le '
                                            'dessin (une ligne de lettres, à l’horizontale), parmi celles du filtre '
                                            'choisi : en tête de la liste'))
        self.recognize_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.recognize_button.clicked.connect(self._recognize_or_stop)
        rec.addWidget(self.recognize_button)
        self.count_box = QSpinBox(self)
        self.count_box.setRange(1, 50)
        self.count_box.setSuffix(tr(' proposition(s)'))
        self.count_box.setToolTip(tr('Nombre de polices proposées par la reconnaissance'))
        self.count_box.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.count_box.setValue(proposal_count())
        self.count_box.valueChanged.connect(lambda v: _settings().setValue(COUNT_KEY, int(v)))
        rec.addWidget(self.count_box)
        self.status = QLabel(self)
        self.status.setWordWrap(True)
        rec.addWidget(self.status, 1)
        lay.addLayout(rec)
        self.proposals: list = []
        self._sig = None
        self._token = None
        self._thread = None
        self._relay = _Relay()                            # sans parent : la liste détruite pendant le calcul, le fil
        self._relay.progress.connect(self._progress)      # émet encore sans erreur (et le calcul s'arrête)
        self._relay.done.connect(self._done)
        self.destroyed.connect(lambda *_a, me=self: setattr(me, '_token', None))
        self.list = QListWidget(self)
        self.list.setUniformItemSizes(False)
        self.list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.list.setItemDelegate(_Delegate(self))
        self.list.viewport().installEventFilter(self)
        self.list.itemClicked.connect(self._clicked)
        self.list.setMouseTracking(True)                  # la ligne sous la souris : surlignée
        self.list.itemEntered.connect(self._hover)
        lay.addWidget(self.list, 1)
        self.info = QLabel(self)
        self.info.setWordWrap(True)
        lay.addWidget(self.info)

    # --- contenu ---------------------------------------------------------------------------------------------------
    def entries(self) -> list[tuple]:
        """(nom, catégorie, bulle) des polices de la FontBox, dans son ordre."""
        out = []
        b = self.box
        for i in range(b.count()):
            name = b.itemText(i)
            if not name:                                  # séparateur
                continue
            out.append((name, b.itemData(i, KIND_ROLE) or 'systeme', b.itemData(i, Qt.ItemDataRole.ToolTipRole)))
        return out

    def current_filter(self) -> str:
        return next((k for k, b in self.filter_buttons.items() if b.isChecked()), 'toutes')

    def _filter_changed(self) -> None:
        s = _settings()
        s.setValue(FILTER_KEY, self.current_filter())
        self.refill()

    def _header(self, text: str) -> None:
        it = QListWidgetItem(text)
        it.setFlags(Qt.ItemFlag.NoItemFlags)
        it.setData(NAME_ROLE, None)
        self.list.addItem(it)

    def _font(self, name: str, kind: str, tip, prox=None) -> None:
        it = QListWidgetItem(name)
        it.setData(NAME_ROLE, name)
        it.setData(KIND_ROLE, kind)
        if prox is not None:
            it.setData(PROX_ROLE, float(prox))
        it.setToolTip(str(tip or ''))
        self.list.addItem(it)

    def refill(self) -> None:
        """La liste refaite selon la recherche et le filtre ; la police de la FontBox (sinon la première trouvée)
        choisie et montrée."""
        q = self.search.text().strip()
        f = self.current_filter()
        found = [e for e in self.entries() if matches(e[0], q)]
        if f == 'favorites':
            found = [e for e in found if e[0] in self.favs]
        elif f != 'toutes':
            found = [e for e in found if e[1] == f]
        self.list.setUpdatesEnabled(False)
        try:
            self.list.clear()
            known = {e[0]: e for e in self.entries()}
            near = [(known[n], p) for n, p in self.proposals if n in known and matches(n, q)]
            if near:
                self._header(tr('Proches de la sélection'))
                for e, p in near:
                    self._font(*e, prox=p)
            if f == 'toutes':
                favs = [e for e in found if e[0] in self.favs]
                if favs:
                    self._header(tr('★ Favorites'))
                    for e in favs:
                        self._font(*e)
            for key, label in KINDS:
                group = [e for e in found if e[1] == key]
                if group:
                    self._header(tr(label))
                    for e in group:
                        self._font(*e)
        finally:
            self.list.setUpdatesEnabled(True)
        n = len({e[0] for e in found})
        if n:
            self.info.setText(tr('{0} police(s) — un clic sur l’étoile : favorite (en tête de la liste)').format(n))
        elif f == 'favorites' and not self.favs:
            self.info.setText(tr('Aucune favorite : cliquez l’étoile d’une police pour l’ajouter'))
        else:
            self.info.setText(tr('Aucune police ne correspond'))
        want = self.box.currentText() if not q and not near else None
        rows = self.font_rows()
        row = next((r for r in rows if self.list.item(r).data(NAME_ROLE) == want), rows[0] if rows else -1)
        if row >= 0:
            self.list.setCurrentRow(row)
            self.list.scrollToItem(self.list.item(row), QAbstractItemView.ScrollHint.PositionAtCenter)

    def font_rows(self) -> list[int]:
        return [r for r in range(self.list.count()) if self.list.item(r).data(NAME_ROLE)]

    def shown(self) -> list[str]:
        """Les polices montrées, dans l'ordre (une favorite deux fois : en tête et dans sa catégorie)."""
        return [self.list.item(r).data(NAME_ROLE) for r in self.font_rows()]

    # --- ouverture -------------------------------------------------------------------------------------------------
    def open_for(self) -> None:
        """Ouverte sous la FontBox, jusqu'au bas de sa fenêtre (au-dessus, jusqu'en haut de la fenêtre, si la place
        manque en dessous), la recherche vide et prête à la frappe, le dernier filtre repris — sauf s'il ne montre
        aucune police ou pas celle de la FontBox : toutes. Les filtres sans police sont grisés."""
        self.favs = set(favorites())
        if self._signature() != self._sig:               # une autre sélection : les propositions d'avant s'en vont,
            self.stop()                                  # le calcul en cours aussi
            self.proposals, self._sig = [], None
            self.status.clear()
        self.count_box.blockSignals(True)
        self.count_box.setValue(proposal_count())
        self.count_box.blockSignals(False)
        key = str(_settings().value(FILTER_KEY, 'toutes') or 'toutes')
        entries = self.entries()
        have = {k: any(e[1] == k for e in entries) for k, _l in KINDS}
        have['favorites'] = any(e[0] in self.favs for e in entries)
        have['toutes'] = True
        for k, b in self.filter_buttons.items():              # « Favorites » reste : elle dit comment en marquer
            b.setEnabled(have.get(k, True) or k == 'favorites')
        cur = self.box.currentText()
        cur_kind = next((e[1] for e in entries if e[0] == cur), None)
        if key not in self.filter_buttons or not have.get(key, False) or (
                cur_kind is not None and key != 'toutes'
                and not (cur in self.favs if key == 'favorites' else cur_kind == key)):
            key = 'toutes'
        self.filter_buttons[key].setChecked(True)
        was = self.search.blockSignals(True)
        self.search.clear()
        self.search.blockSignals(was)
        self._list_press = self._star_press = False
        self.setAttribute(Qt.WidgetAttribute.WA_NoMouseReplay, False)
        self.place()
        self.refill()
        self.show()
        self.raise_()
        self.search.setFocus()

    def place(self) -> None:
        """Sous la FontBox jusqu'au bas de la fenêtre ; si la place y manque et qu'il y en a plus au-dessus : au-dessus,
        jusqu'en haut. Jamais sur la FontBox (un second clic sur sa flèche referme la liste, comme celle de Qt)."""
        box = self.box
        area = area_for(box)
        scr = screen_of(box).availableGeometry()
        top = box.mapToGlobal(QPoint(0, 0)).y()
        corner = box.mapToGlobal(QPoint(0, box.height()))
        width = min(max(box.width(), MIN_W), scr.width())
        x = min(max(corner.x(), scr.left()), scr.right() + 1 - width)
        below = area.bottom() + 1 - corner.y()
        above = top - area.top()
        if below >= MIN_BELOW or below >= above:
            self.setGeometry(x, corner.y(), width, max(1, below))
        else:
            self.setGeometry(x, area.top(), width, above)

    def mousePressEvent(self, e) -> None:                  # noqa: N802 (API Qt)
        """Un clic hors de la liste la ferme ; sur la flèche de la FontBox (sur toute la FontBox si elle n'est pas
        éditable), il n'est pas rejoué : la liste ne se rouvre pas (comme la liste de Qt)."""
        box = self.box
        p = box.mapFromGlobal(e.globalPosition().toPoint())
        if box.rect().contains(p):
            from PySide6.QtWidgets import QStyleOptionComboBox
            opt = QStyleOptionComboBox()
            box.initStyleOption(opt)
            opt.subControls = QStyle.SubControl.SC_All
            sc = box.style().hitTestComplexControl(QStyle.ComplexControl.CC_ComboBox, opt, p, box)
            if not box.isEditable() or sc == QStyle.SubControl.SC_ComboBoxArrow:
                self.setAttribute(Qt.WidgetAttribute.WA_NoMouseReplay, True)
        super().mousePressEvent(e)

    # --- reconnaissance --------------------------------------------------------------------------------------------
    def main_window(self):
        """La fenêtre de dessin d'où la liste est ouverte (celle de la liste déroulante, ou celle d'où sa fenêtre a été
        ouverte), sinon la fenêtre de dessin visible."""
        w = self.box.window()
        seen = set()
        while w is not None and id(w) not in seen:
            seen.add(id(w))
            if hasattr(getattr(w, 'canvas', None), 'selection'):
                return w
            p = w.parentWidget()
            w = p.window() if p is not None else None
        return next((t for t in QApplication.topLevelWidgets()
                     if t.isVisible() and hasattr(getattr(t, 'canvas', None), 'selection')), None)

    def _selected(self) -> list:
        win = self.main_window()
        if win is None:
            return []
        from .canvas import _leaves
        return list(_leaves(win.canvas.selection))

    def _signature(self):
        return tuple(getattr(it, 'id', None) or id(it) for it in self._selected()) or None

    def selection_paths(self) -> list:
        """Les tracés des formes (et des textes) sélectionnés dans la fenêtre de dessin."""
        from .canvas import item_path
        return [p for p in (item_path(it) for it in self._selected()) if p]

    def recognize(self) -> None:
        """Les polices les plus proches des lettres en courbes sélectionnées, parmi celles du filtre choisi, calculées
        dans un fil (la liste reste utilisable, l'avancement est montré) ; elles viennent en tête de la liste."""
        from ..core import fontmatch
        paths = self.selection_paths()
        if not paths:
            self.status.setText(tr('Sélectionnez d’abord des lettres en courbes dans le dessin'))
            return
        f = self.current_filter()
        names = list(dict.fromkeys(e[0] for e in self.entries()
                                   if f == 'toutes' or (e[0] in self.favs if f == 'favorites' else e[1] == f)))
        if not names:
            self._drop_proposals(tr('Aucune police à comparer dans ce filtre'))
            return
        count = self.count_box.value()
        token = object()
        self._token = token
        self._sig = self._signature()
        self.recognize_button.setText(tr('Arrêter'))
        self.status.setText(tr('Reconnaissance…'))
        relay = self._relay

        def emit(sig, *args):
            try:
                sig.emit(*args)
            except RuntimeError:                       # la liste n'est plus là
                pass

        def work():
            cancel = lambda: self._token is not token  # noqa: E731
            try:
                sel = fontmatch.selection_images(paths)
                if not len(sel):
                    res = 'lettres'
                else:
                    res = fontmatch.rank(paths, names, count, progress=lambda i, n: emit(relay.progress, token, i, n),
                                         cancel=cancel, sel=sel) or 'polices'
            except Exception as e:                     # noqa: BLE001 — montré dans la liste
                res = e
            if not cancel():
                emit(relay.done, token, res)
        self._thread = threading.Thread(target=work, daemon=True, name='reconnaissance des polices')
        self._thread.start()

    def _recognize_or_stop(self) -> None:
        if self._token is not None:
            self.stop()
            self.status.setText(tr('Reconnaissance arrêtée'))
        else:
            self.recognize()

    def stop(self) -> None:
        """La reconnaissance en cours abandonnée (son résultat ne viendra pas)."""
        self._token = None
        self.recognize_button.setText(tr('Reconnaître la sélection'))

    def _drop_proposals(self, why: str) -> None:
        self.status.setText(why)
        if self.proposals:
            self.proposals = []
            self.refill()

    def _progress(self, token, done: int, total: int) -> None:
        if token is self._token and total:
            self.status.setText(tr('Polices comparées : {0} sur {1} (leurs formes sont gardées : la prochaine fois, '
                                   'c’est immédiat)').format(done, total))

    def _done(self, token, res) -> None:
        if token is not self._token:                    # abandonnée, ou une autre lancée depuis
            return
        sig = self._sig
        self.stop()
        if self._signature() != sig:                    # la sélection a changé depuis le lancement : périmé
            self._drop_proposals('')
            return
        if isinstance(res, Exception):
            self._drop_proposals(tr('Reconnaissance impossible : {0}').format(res))
            return
        if res == 'polices' or not res:
            self._drop_proposals(tr('Aucune police à comparer dans ce filtre'))
            return
        if res == 'lettres':
            self._drop_proposals(tr('Aucune lettre reconnue dans la sélection'))
            return
        self.proposals = list(res)
        self.status.setText(tr('{0} police(s) proche(s) de la sélection, en tête de la liste').format(len(res)))
        self.refill()
        self.list.scrollToTop()

    # --- choix -----------------------------------------------------------------------------------------------------
    def choose(self, name: str) -> None:
        self.hide()
        self.picked.emit(name)

    def _clicked(self, item) -> None:
        name = item.data(NAME_ROLE)
        if name:
            self.choose(name)

    def _hover(self, item) -> None:
        if item is not None and item.data(NAME_ROLE):
            self.list.setCurrentItem(item)

    def toggle_favorite(self, name: str) -> None:
        """Favorite ou plus : gardé dans les réglages tout de suite (relus d'abord : un autre VectorDrive a pu en
        marquer) ; la liste n'est pas refaite (rien ne saute sous la souris), la section des favorites suit à la
        prochaine recherche, au prochain filtre ou à la prochaine ouverture."""
        order = [n for n in favorites() if n != name]
        if name not in self.favs:
            order.append(name)
        set_favorites(order)
        self.favs = set(order)
        self.list.viewport().update()

    def _step(self, key) -> None:
        rows = self.font_rows()
        if not rows:
            return
        cur = self.list.currentRow()
        page = max(1, self.list.viewport().height() // max(1, self.list.sizeHintForRow(rows[0])) - 1)
        step = {Qt.Key.Key_Up: -1, Qt.Key.Key_Down: 1, Qt.Key.Key_PageUp: -page, Qt.Key.Key_PageDown: page}[key]
        if cur not in rows:
            target = rows[0] if step > 0 else rows[-1]
        else:
            i = rows.index(cur)
            target = rows[min(len(rows) - 1, max(0, i + step))]
        self.list.setCurrentRow(target)
        self.list.scrollToItem(self.list.item(target))

    def eventFilter(self, obj, ev) -> bool:                 # noqa: N802 (API Qt)
        t = ev.type()
        if obj is self.list.viewport():
            if t in (QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonDblClick) \
                    and ev.button() == Qt.MouseButton.LeftButton:
                self._list_press = True
                pos = ev.position().toPoint()
                it = self.list.itemAt(pos)
                if it is not None and it.data(NAME_ROLE) and pos.x() < STAR_W:
                    if t == QEvent.Type.MouseButtonPress:     # un double-clic ne la rebascule pas
                        self.toggle_favorite(it.data(NAME_ROLE))
                    self._star_press = True
                    return True
            elif t == QEvent.Type.MouseButtonRelease and self._star_press:
                self._star_press = self._list_press = False
                return True
            elif t == QEvent.Type.MouseButtonRelease and ev.button() == Qt.MouseButton.LeftButton:
                if not self._list_press:                      # glissé depuis la liste déroulante : relâché ici
                    pos = ev.position().toPoint()
                    it = self.list.itemAt(pos)
                    if it is not None and it.data(NAME_ROLE) and pos.x() >= STAR_W:
                        self.choose(it.data(NAME_ROLE))
                    return True
                self._list_press = False
        elif obj is self.search and t == QEvent.Type.KeyPress:
            k = ev.key()
            if k in (Qt.Key.Key_Up, Qt.Key.Key_Down, Qt.Key.Key_PageUp, Qt.Key.Key_PageDown):
                self._step(k)
                return True
            if k in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                it = self.list.currentItem()
                if it is not None and it.data(NAME_ROLE):
                    self.choose(it.data(NAME_ROLE))
                return True
            if k == Qt.Key.Key_Escape:
                self.hide()
                return True
        return super().eventFilter(obj, ev)
