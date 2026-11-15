"""Mise en page qui passe à la ligne (barres d'outils qui tiennent dans une
fenêtre étroite) et étiquette tronquée (texte long qui n'élargit pas la
fenêtre)."""
from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QLabel, QLayout, QSizePolicy, QWidgetItem


class FlowLayout(QLayout):
    """Éléments les uns après les autres, à la ligne quand la place manque."""

    def __init__(self, parent=None, spacing: int = 4):
        super().__init__(parent)
        self._items: list = []
        self.setSpacing(spacing)

    def addItem(self, item) -> None:
        self._items.append(item)

    def addWidget(self, w, stretch: int = 0) -> None:     # stretch : sans objet ici (signature des QBoxLayout)
        self.addChildWidget(w)
        self.addItem(QWidgetItem(w))

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, i: int):
        return self._items[i] if 0 <= i < len(self._items) else None

    def takeAt(self, i: int):
        return self._items.pop(i) if 0 <= i < len(self._items) else None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return self._place(QRect(0, 0, width, 0), apply=False)

    def setGeometry(self, rect) -> None:
        super().setGeometry(rect)
        self._place(rect, apply=True)

    def sizeHint(self) -> QSize:
        return self.minimumSize()

    def minimumSize(self) -> QSize:
        s = QSize()
        for it in self._items:
            if not it.isEmpty():
                s = s.expandedTo(it.minimumSize())
        m = self.contentsMargins()
        return s + QSize(m.left() + m.right(), m.top() + m.bottom())

    def _place(self, rect, apply: bool) -> int:
        m = self.contentsMargins()
        r = rect.adjusted(m.left(), m.top(), -m.right(), -m.bottom())
        x, y, line = r.x(), r.y(), 0
        sp = self.spacing()
        for it in self._items:
            if it.isEmpty():
                continue
            hint = it.sizeHint()
            if x + hint.width() > r.right() + 1 and line > 0:
                x, y, line = r.x(), y + line + sp, 0
            if apply:
                it.setGeometry(QRect(QPoint(x, y), hint))
            x += hint.width() + sp
            line = max(line, hint.height())
        return y + line - rect.y() + m.bottom()


class ElideLabel(QLabel):
    """Étiquette d'une ligne, tronquée (…) à la place disponible ; le texte
    entier en bulle d'aide."""

    def __init__(self, text: str = '', parent=None):
        super().__init__(text, parent)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)

    def setText(self, text: str) -> None:
        super().setText(text)
        self.setToolTip(text if text else '')

    def minimumSizeHint(self) -> QSize:
        return QSize(0, super().minimumSizeHint().height())

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        r = self.contentsRect()
        txt = self.fontMetrics().elidedText(self.text(), Qt.TextElideMode.ElideRight, r.width())
        p.drawText(r, int(self.alignment()) | int(Qt.AlignmentFlag.AlignVCenter), txt)
