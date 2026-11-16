"""Un texte de plusieurs lignes qui se replie en une seule (demande du 15/11, 22 h 30 : « fao parcours : colonne est
polluée par commentaires avec panneaux attention, possibilité de les replier »). Replié, il montre un résumé d'une
ligne, coupé à la largeur de la colonne : le nombre d'avertissements (⚠), puis la ligne donnée par l'appelant (ou la
première) ; le texte entier reste en bulle, et `text()` le rend toujours."""
from __future__ import annotations

import textwrap

from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtWidgets import QFrame, QLabel, QScrollArea, QSizePolicy

WARN = '⚠'


def warnings_in(text: str) -> int:
    """Le nombre de lignes d'avertissement (⚠) de `text`."""
    return sum(1 for line in str(text or '').split('\n') if line.lstrip().startswith(WARN))


def summary_of(text: str, head: str | None = None) -> str:
    """Le résumé d'une ligne de `text` : « ⚠ 2 · ligne » (`head` : la ligne à montrer ; sinon la première qui n'est
    pas un avertissement, sinon la première)."""
    lines = [line.strip() for line in str(text or '').split('\n') if line.strip()]
    if not lines:
        return ''
    n = warnings_in(text)
    plain = [line for line in lines if not line.startswith(WARN)]
    line = (head or '').strip() or (plain[0] if plain else lines[0].lstrip(WARN + ' '))
    return f'{WARN} {n} · {line}' if n else line


def tip_of(text: str, width: int = 90) -> str:
    """`text` en bulle : ses longues lignes coupées (une bulle en texte brut ne revient pas à la ligne d'elle-même :
    une phrase de 250 caractères ferait une bulle plus large que l'écran)."""
    lines = str(text or '').split('\n')
    return '\n'.join(line if len(line) <= width else textwrap.fill(line, width) for line in lines)


class FoldLabel(QLabel):
    """QLabel à retour à la ligne, repliable : `set_folded`, `folded`, `foldable` ; `changed` à chaque texte posé et
    à chaque repli (le bouton de repli se montre ou se cache, la zone reprend sa hauteur)."""

    changed = Signal()

    def __init__(self, text: str = '', parent=None):
        super().__init__(parent)
        self._full = ''
        self._head = None
        self._folded = False
        self._always = False
        self.setWordWrap(True)
        self.setText(text)

    def set_always(self, on: bool) -> None:
        """Repliable même s'il n'a qu'une ligne (une longue phrase d'aide, sur plusieurs lignes à l'écran)."""
        self._always = bool(on)
        self._show()
        self.changed.emit()

    # --- texte ---------------------------------------------------------------------------------
    def setText(self, text: str, summary: str | None = None) -> None:     # noqa: N802
        """Pose le texte entier ; `summary` : la ligne à montrer une fois replié."""
        self._full = str(text or '')
        self._head = summary
        self._show()
        self.changed.emit()

    def text(self) -> str:
        """Le texte entier, replié ou non."""
        return self._full

    def clear(self) -> None:
        self.setText('')

    def shown_text(self) -> str:
        """Ce qui est montré : le texte entier, ou son résumé d'une ligne (peut-être coupé)."""
        return QLabel.text(self)

    # --- repli ---------------------------------------------------------------------------------
    def foldable(self) -> bool:
        """Plusieurs lignes (ou `set_always`) : il y a de quoi replier."""
        n = len([line for line in self._full.split('\n') if line.strip()])
        return n > 1 or (self._always and n == 1)

    def folded(self) -> bool:
        return self._folded

    def set_folded(self, on: bool) -> None:
        if bool(on) != self._folded:
            self._folded = bool(on)
            self._show()
            self.changed.emit()

    def _show(self) -> None:
        fold = self._folded and self.foldable()
        self.setWordWrap(not fold)
        # replié : une ligne coupée à la largeur donnée, sans jamais élargir la colonne
        policy = QSizePolicy(QSizePolicy.Policy.Ignored if fold else QSizePolicy.Policy.Preferred,
                             QSizePolicy.Policy.Preferred)
        policy.setHeightForWidth(not fold)               # déplié : sa hauteur suit sa largeur (retour à la ligne)
        self.setSizePolicy(policy)
        self.setToolTip(tip_of(self._full) if fold else '')
        if fold:
            self._elide()
        else:
            QLabel.setText(self, self._full)
        self.updateGeometry()

    def summary(self) -> str:
        """Le résumé d'une ligne (entier : montré coupé à la largeur)."""
        return summary_of(self._full, self._head)

    def _elide(self) -> None:
        line = self.summary()
        width = max(40, self.contentsRect().width())
        QLabel.setText(self, self.fontMetrics().elidedText(line, Qt.TextElideMode.ElideRight, width))

    def resizeEvent(self, ev) -> None:                                    # noqa: N802
        super().resizeEvent(ev)
        if self._folded and self.foldable():
            self._elide()

    def minimumSizeHint(self) -> QSize:                                   # noqa: N802
        hint = super().minimumSizeHint()
        if self._folded and self.foldable():
            return QSize(40, self.fontMetrics().height() + 2)
        return hint

    def sizeHint(self) -> QSize:                                          # noqa: N802
        if self._folded and self.foldable():
            return QSize(40, self.fontMetrics().height() + 2)
        return super().sizeHint()


class FoldArea(QScrollArea):
    """Un `FoldLabel` dans une zone d'au plus `lines` lignes de haut (demande du 16/11 : « Liste opé calculée doit
    prendre plus de hauteur dans sa colonne ») : la zone prend la hauteur du texte, jusqu'à cette limite ; au-delà elle
    défile, et la liste au-dessus garde la hauteur de la colonne."""

    def __init__(self, label: FoldLabel, lines: int = 6, parent=None):
        super().__init__(parent)
        self.label = label
        self.lines = lines
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)      # pas un arrêt de tabulation de plus dans le panneau
        self.viewport().setAutoFillBackground(False)     # le fond du panneau, pas celui d'une liste
        self.setWidget(label)
        label.setAutoFillBackground(False)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        label.changed.connect(self.updateGeometry)

    def max_height(self) -> int:
        return self.lines * self.label.fontMetrics().lineSpacing() + 4

    def _too_wide(self) -> bool:
        """Un mot plus large que la zone (un chemin de fichier) : elle défile en largeur, plutôt que de le couper ou
        d'élargir la colonne."""
        lab = self.label
        return not (lab.folded() and lab.foldable()) and lab.minimumSizeHint().width() > self.viewport().width() > 0

    def wanted_height(self) -> int:
        """La hauteur du texte montré à la largeur de la zone, bornée à `lines` lignes."""
        lab = self.label
        one = lab.fontMetrics().height() + 2
        if lab.folded() and lab.foldable():
            return one
        wide = self._too_wide()
        h = lab.heightForWidth(max(40, lab.minimumSizeHint().width() if wide else self.viewport().width()))
        bar = self.horizontalScrollBar().sizeHint().height() if wide else 0
        return min(max(h if h > 0 else lab.sizeHint().height(), one), self.max_height()) + bar

    def show_end(self) -> None:
        """La fin du texte en vue (le temps estimé d'un compte rendu, écrit en dernier), une fois la zone à sa
        taille."""
        bar = self.verticalScrollBar()
        QTimer.singleShot(0, self, lambda: bar.setValue(bar.maximum()))

    def sizeHint(self) -> QSize:                                          # noqa: N802
        return QSize(40, self.wanted_height())

    def minimumSizeHint(self) -> QSize:                                   # noqa: N802
        return QSize(40, self.wanted_height())

    def resizeEvent(self, ev) -> None:                                    # noqa: N802
        super().resizeEvent(ev)
        if ev.size().width() != ev.oldSize().width():    # autre largeur : autre hauteur de texte
            self.updateGeometry()
