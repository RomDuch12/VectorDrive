"""La molette ne change pas une liste déroulante au simple survol.

Faire défiler un panneau de réglages changeait au passage la valeur de la liste déroulante qui se trouvait sous le
pointeur. La molette n'agit plus sur une liste que dépliée (un clic) : la liste dépliée est une autre fenêtre, sa
molette n'est pas touchée. L'événement refusé remonte au parent : le panneau continue de défiler. Une liste ne prend
plus le clavier au passage de la molette (elle le prenait d'office : la flèche suivante l'aurait changée) : un clic
ou Tab le lui donnent.
"""
from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import QApplication, QComboBox

_NAME = 'vd_combo_wheel_guard'


class ComboWheelGuard(QObject):
    """Filtre d'application : les événements de molette adressés à une liste déroulante sont refusés."""

    WATCH = (QEvent.Type.Polish, QEvent.Type.Enter, QEvent.Type.Wheel)

    def eventFilter(self, obj, ev) -> bool:
        t = ev.type()
        if t in self.WATCH and isinstance(obj, QComboBox):
            if obj.focusPolicy() == Qt.FocusPolicy.WheelFocus:    # Qt donne le clavier avant tout filtre
                obj.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            if t == QEvent.Type.Wheel:
                ev.ignore()                              # refusé : Qt le propose au parent (le panneau qui défile)
                return True
        return False


def install(app=None) -> ComboWheelGuard | None:
    """Pose le filtre sur l'application, une seule fois ; rend le filtre."""
    app = app or QApplication.instance()
    if app is None:
        return None
    guard = app.findChild(ComboWheelGuard, _NAME)
    if guard is None:
        guard = ComboWheelGuard(app)
        guard.setObjectName(_NAME)
        app.installEventFilter(guard)
    return guard
