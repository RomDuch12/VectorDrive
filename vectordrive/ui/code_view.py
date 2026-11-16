"""Vue d'un programme machine (demande du 15/11, 20 h 55 : « numérotation lignes, repliage blocs et sequences, et
surlignage (plutot discret) de la partie concernée par ce que fait user dans les autres colonnes ») :

- les numéros de ligne dans une marge, à gauche ;
- des blocs repliables : un clic sur ▾ dans la marge replie le bloc sous sa première ligne, ▸ le déplie ; les blocs
  viennent des mots du langage (`fold_regions` : module … endmodule, program … endprogram, if … endif…) et des
  plages que l'appelant donne (les parcours d'un programme) ;
- une ou plusieurs plages de lignes surlignées discrètement (`set_bands`), avec un trait dans la marge.

`CodeView` reste un `QPlainTextEdit` : texte, coloration, sélection et copie comme avant."""
from __future__ import annotations

import re

from PySide6.QtCore import QRect, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QPlainTextEdit, QWidget

#: mots qui ouvrent un bloc, et celui qui le ferme (en début de ligne)
BLOCKS = {'module': 'endmodule', 'program': 'endprogram', 'if': 'endif', 'for': 'endfor', 'while': 'endwhile',
          'sub': 'endsub', 'function': 'endfunction'}
_FIRST_WORD = re.compile(r'^\s*([A-Za-z_]+)\b')
#: largeur de la colonne des marques de repli, dans la marge (px)
FOLD_W = 14
#: fond d'une plage surlignée (discret : on lit le programme au travers) et son trait dans la marge
BAND = QColor(255, 212, 59, 40)
BAND_EDGE = QColor(245, 159, 0, 200)


def fold_regions(text: str, sections=()) -> list:
    """Les blocs repliables de `text` : [(première ligne, dernière ligne)], numérotées de 0 — la première reste
    montrée, les suivantes jusqu'à la dernière se replient. Les blocs du langage (un mot de `BLOCKS` en début de
    ligne, jusqu'à la ligne d'avant son mot de fin), puis les plages `sections` de l'appelant (les parcours) ; un bloc
    d'une seule ligne n'en est pas un."""
    stack, out = [], []
    for n, line in enumerate(str(text or '').split('\n')):
        m = _FIRST_WORD.match(line)
        word = m.group(1) if m else ''
        if word in BLOCKS:
            stack.append((BLOCKS[word], n))
        elif word in BLOCKS.values() and any(close == word for close, _n in stack):
            while stack[-1][0] != word:                  # un bloc jamais fermé : laissé de côté (un mot de fin sans
                stack.pop()                              # bloc ouvert, lui, ne ferme rien)
            _close, first = stack.pop()
            if n - 1 > first:
                out.append((first, n - 1))
    for first, last in sections or ():
        if last > first and (first, last) not in out:
            out.append((int(first), int(last)))
    return sorted(set(out))


class _Gutter(QWidget):
    """La marge : numéros de ligne, marques de repli, trait des plages surlignées."""

    def __init__(self, view):
        super().__init__(view)
        self.view = view

    def sizeHint(self) -> QSize:                                          # noqa: N802
        return QSize(self.view.gutter_width(), 0)

    def paintEvent(self, ev) -> None:                                     # noqa: N802
        self.view.paint_gutter(ev)

    def mousePressEvent(self, ev) -> None:                                # noqa: N802
        self.view.gutter_clicked(ev.position().toPoint().y())


class CodeView(QPlainTextEdit):
    """Texte d'un programme : numéros de ligne, blocs repliables, plages surlignées."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.regions: list = []                          # [(première, dernière)] : les blocs repliables
        self.folded: set = set()                         # premières lignes des blocs repliés
        self.bands: list = []                            # [(première, dernière)] : plages surlignées
        self._hidden: set = set()                        # les lignes cachées en ce moment (`_apply_folds`)
        self._ends: dict = {}                            # première ligne → dernière ligne de son bloc (`end_of`)
        self._ends_of = None                             # … calculé pour cette liste `regions`
        self.gutter = _Gutter(self)
        self.blockCountChanged.connect(lambda _n: self._margins())
        self.updateRequest.connect(self._scrolled)
        self._margins()

    # --- la marge --------------------------------------------------------------------------------
    def gutter_width(self) -> int:
        digits = max(3, len(str(max(1, self.blockCount()))))
        return 8 + self.fontMetrics().horizontalAdvance('9') * digits + FOLD_W

    def _margins(self) -> None:
        self.setViewportMargins(self.gutter_width(), 0, 0, 0)

    def _scrolled(self, rect, dy: int) -> None:
        if dy:
            self.gutter.scroll(0, dy)
        else:
            self.gutter.update(0, rect.y(), self.gutter.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self._margins()

    def resizeEvent(self, ev) -> None:                                    # noqa: N802
        super().resizeEvent(ev)
        cr = self.contentsRect()
        self.gutter.setGeometry(QRect(cr.left(), cr.top(), self.gutter_width(), cr.height()))

    def _shown_blocks(self):
        """(bloc, haut, hauteur) des lignes montrées à l'écran, de haut en bas."""
        block = self.firstVisibleBlock()
        top = self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        limit = self.viewport().height()
        doc = self.document()
        while block.isValid() and top <= limit:
            if block.isVisible():
                h = self.blockBoundingRect(block).height()
                yield block, top, h
                top += h
                block = block.next()
            else:                                        # un bloc replié : sauté d'un coup, pas ligne à ligne
                n = block.blockNumber()
                end = max((self.end_of(a) for a in self.folded if a < n <= self.end_of(a)), default=n)
                block = doc.findBlockByNumber(end + 1)

    def paint_gutter(self, ev) -> None:
        p = QPainter(self.gutter)
        pal = self.palette()
        p.fillRect(ev.rect(), pal.alternateBase().color())
        ink = pal.placeholderText().color() if hasattr(pal, 'placeholderText') else pal.mid().color()
        heads = {a for a, _b in self.regions}
        w = self.gutter.width()
        fh = self.fontMetrics().height()
        p.setFont(self.font())
        for block, top, h in self._shown_blocks():
            if top + h < ev.rect().top() or top > ev.rect().bottom():
                continue
            n = block.blockNumber()
            if any(a <= n <= b for a, b in self.bands):
                p.fillRect(QRectF(0, top, 3, h), BAND_EDGE)
            p.setPen(ink)
            p.drawText(QRectF(0, top, w - FOLD_W - 4, fh), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                       str(n + 1))
            if n in heads:
                p.setPen(pal.text().color())
                p.drawText(QRectF(w - FOLD_W, top, FOLD_W, fh), Qt.AlignmentFlag.AlignCenter,
                           '▸' if n in self.folded else '▾')
        p.end()

    def line_at(self, y: int) -> int:
        """La ligne (numérotée de 0) montrée à la hauteur `y` de la vue ; -1 : aucune."""
        for block, top, h in self._shown_blocks():
            if top <= y < top + h:
                return block.blockNumber()
        return -1

    def gutter_clicked(self, y: int) -> None:
        n = self.line_at(y)
        if n >= 0 and any(a == n for a, _b in self.regions):
            self.toggle_fold(n)

    # --- les blocs repliables ------------------------------------------------------------------
    def set_regions(self, regions, keep: bool = True) -> None:
        """Les blocs repliables ; `keep` : ceux qui étaient repliés et existent encore le restent."""
        self.regions = sorted({(int(a), int(b)) for a, b in regions or () if b > a})
        heads = {a for a, _b in self.regions}
        self.folded = {a for a in self.folded if a in heads} if keep else set()
        self._apply_folds()

    def end_of(self, first: int) -> int:
        """La dernière ligne du bloc qui commence à `first` (le plus long, s'il y en a deux) ; -1 : pas un bloc."""
        if self._ends_of is not self.regions:            # (une table, refaite quand la liste des blocs change)
            ends: dict = {}
            for a, b in self.regions:
                if b > ends.get(a, -1):
                    ends[a] = b
            self._ends, self._ends_of = ends, self.regions
        return self._ends.get(first, -1)

    def is_folded(self, first: int) -> bool:
        return first in self.folded

    def toggle_fold(self, first: int) -> bool:
        """Replie ou déplie le bloc qui commence à la ligne `first` ; rend vrai s'il est replié."""
        if self.end_of(first) < 0:
            return False
        if first in self.folded:
            self.folded.discard(first)
        else:
            self.folded.add(first)
        self._apply_folds()
        return first in self.folded

    def fold_all(self, on: bool = True, depth: int | None = None) -> None:
        """Tous les blocs repliés (`on`) ou dépliés ; `depth` : seulement ceux de ce niveau d'imbrication (0 : les
        plus larges)."""
        if not on:
            self.folded = set()
        else:
            heads = {a for a, _b in self.regions}
            if depth is not None:
                heads = {a for a in heads if self.depth_of(a) == depth}
            self.folded = heads
        self._apply_folds()

    def depth_of(self, first: int) -> int:
        """Le niveau d'imbrication du bloc qui commence à `first` : le nombre de blocs qui le contiennent."""
        last = self.end_of(first)
        return sum(1 for a, b in self.regions if a < first and b >= last)

    def hidden_lines(self) -> set:
        """Les lignes cachées par les blocs repliés."""
        out = set()
        for a in self.folded:
            out.update(range(a + 1, self.end_of(a) + 1))
        return out

    def reveal(self, line: int) -> None:
        """Déplie les blocs qui cachent la ligne `line`."""
        hiding = {a for a in self.folded if a < line <= self.end_of(a)}
        if hiding:
            self.folded -= hiding
            self._apply_folds()

    def _apply_folds(self) -> None:
        """Les lignes des blocs repliés cachées, les autres montrées : seules celles dont l'état change sont
        touchées (un clic dans la marge d'un long programme ne le parcourt pas en entier)."""
        hidden = self.hidden_lines()
        doc = self.document()
        changed = False
        for n in sorted(hidden ^ self._hidden):
            block = doc.findBlockByNumber(n)
            if not block.isValid():
                continue
            show = n not in hidden
            if block.isVisible() != show:
                block.setVisible(show)
                block.setLineCount(max(1, block.layout().lineCount()) if show else 0)
                changed = True
        self._hidden = hidden
        if changed:
            layout = doc.documentLayout()
            layout.requestUpdate()
            layout.documentSizeChanged.emit(layout.documentSize())
            self.viewport().update()
        self.gutter.update()

    # --- le texte ----------------------------------------------------------------------------------
    def setPlainText(self, text: str) -> None:                            # noqa: N802
        """Un texte neuf : toutes ses lignes sont montrées (plus rien de replié)."""
        self._hidden = set()
        self.folded = set()
        super().setPlainText(text)

    def set_program(self, text: str, sections=()) -> None:
        """Pose le texte et ses blocs repliables (`fold_regions`, avec les plages `sections`) ; un bloc replié le
        reste si sa première ligne est toujours la même (même texte, même rang parmi ses pareilles)."""
        was = self._fold_keys()
        self.folded = set()
        self.bands = []
        self.setPlainText(text)
        self.regions = fold_regions(text, sections)
        if was:
            lines = text.split('\n')
            seen: dict = {}
            for a, _b in self.regions:
                key = (lines[a], seen.get(lines[a], 0))
                seen[lines[a]] = key[1] + 1
                if key in was:
                    self.folded.add(a)
        self._apply_folds()

    def _fold_keys(self) -> set:
        """{(texte de la première ligne, rang parmi les premières lignes de même texte)} des blocs repliés."""
        if not self.folded:
            return set()
        doc = self.document()
        out, seen = set(), {}
        for a, _b in self.regions:
            t = doc.findBlockByNumber(a).text()
            k = seen.get(t, 0)
            seen[t] = k + 1
            if a in self.folded:
                out.add((t, k))
        return out

    # --- les plages surlignées -------------------------------------------------------------------
    def set_bands(self, bands) -> None:
        """Les plages de lignes surlignées discrètement : [(première, dernière)] (vide : aucune)."""
        self.bands = sorted({(int(a), int(b)) for a, b in bands or () if b >= a})
        self.viewport().update()
        self.gutter.update()

    def paintEvent(self, ev) -> None:                                     # noqa: N802
        if self.bands:
            p = QPainter(self.viewport())
            w = self.viewport().width()
            for block, top, h in self._shown_blocks():
                n = block.blockNumber()
                if any(a <= n <= b for a, b in self.bands):
                    p.fillRect(QRectF(0, top, w, h), BAND)
            p.end()
        super().paintEvent(ev)
