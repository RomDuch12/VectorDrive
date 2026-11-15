"""Champs de valeur de toute l'application (QDoubleSpinBox, QSpinBox et
lignes de saisie numériques) :

* un double-clic sélectionne TOUTE la valeur (Qt ne prenait que le mot sous
  le curseur : la partie entière ou les décimales) ;
* la virgule, le point et le point du pavé numérique sont tous acceptés
  comme séparateur décimal, quelle que soit la langue du poste ;
* la touche = ouvre un calcul (core.calc : « 25,4*3 », « (120-10)/7 »,
  « 50*tan(30) », unités « 1in », « 3/4" », « 1'6" », « 2cm ») dont le
  résultat remplace la valeur ; les calculs précédents y sont proposés et
  « ans » vaut le dernier résultat, gardés d'une séance à l'autre.

    from .fields import install
    install(app)          # une fois, au lancement
"""
from __future__ import annotations

from PySide6.QtCore import QEvent, QLocale, QObject, Qt, QTimer
from PySide6.QtGui import QDoubleValidator, QIntValidator
from PySide6.QtWidgets import QAbstractSpinBox, QApplication, QDoubleSpinBox, QLineEdit


def numeric_editor(w) -> QLineEdit | None:
    """La ligne de saisie si `w` est (ou est dans) un champ numérique."""
    if isinstance(w, QAbstractSpinBox):
        # le champ lui-même a le focus (QInputDialog, champs F2…) : Qt lui
        # donne les touches avant sa ligne de saisie, et y perdait le point
        return w.lineEdit()
    if not isinstance(w, QLineEdit):
        return None
    p = w.parentWidget()
    if isinstance(p, QAbstractSpinBox):
        return w
    v = w.validator()
    if isinstance(v, (QDoubleValidator, QIntValidator)) or w.property('vd_numeric'):
        return w
    return None


def decimal_point(w: QLineEdit) -> str:
    """Séparateur décimal attendu par le champ (celui de sa locale)."""
    p = w.parentWidget()
    loc = p.locale() if isinstance(p, QAbstractSpinBox) else w.locale()
    return loc.decimalPoint() or QLocale().decimalPoint()


class NumericInputFilter(QObject):
    """Filtre d'événements de l'application (voir le module)."""

    def eventFilter(self, obj, ev) -> bool:                      # noqa: N802 (API Qt)
        t = ev.type()
        if t == QEvent.Type.MouseButtonDblClick:
            le = numeric_editor(obj)
            if le is not None:
                QTimer.singleShot(0, le.selectAll)              # après la sélection du mot par Qt
            return False
        if t == QEvent.Type.KeyPress:
            le = numeric_editor(obj)
            if le is None or le.isReadOnly():
                return False
            if ev.key() == Qt.Key.Key_Equal or ev.text() == '=':
                calculate(le)
                return True
            if ev.key() in (Qt.Key.Key_Comma, Qt.Key.Key_Period) or ev.text() in (',', '.'):
                p = le.parentWidget()
                if isinstance(p, QAbstractSpinBox) and not isinstance(p, QDoubleSpinBox):
                    return True                                 # entier : pas de décimales
                sep = decimal_point(le)
                if sep not in le.text() or le.hasSelectedText() and sep in le.selectedText():
                    le.insert(sep)
                return True                                     # un seul séparateur, celui du champ
        return False


#: calculs précédents gardés (calculatrice des champs)
HISTORY_MAX = 15


def history(st) -> tuple[list[str], float | None]:
    """Calculs précédents (le plus récent d'abord) et dernier résultat, lus
    dans les réglages `st`."""
    h = st.value('calcul/historique', [])
    h = [h] if isinstance(h, str) else [x for x in (h or []) if isinstance(x, str)]
    try:
        ans = float(st.value('calcul/ans'))
    except (TypeError, ValueError):
        ans = None
    return h, ans


def calculate(le: QLineEdit, expr: str | None = None) -> float | None:
    """Calcul pour le champ de `le` : l'expression (demandée si absente :
    la valeur actuelle proposée, puis les calculs précédents) ; le résultat
    devient la valeur du champ et le dernier résultat (« ans ») ; un calcul
    (pas un simple nombre) rejoint les calculs précédents."""
    from .. import portable
    from ..core.calc import evaluate
    from ..i18n import tr
    p = le.parentWidget()
    box = p if isinstance(p, QAbstractSpinBox) else None
    st = portable.settings()
    hist, ans = history(st)
    if expr is None:
        from PySide6.QtWidgets import QInputDialog
        cur = (box.text() if box is not None else le.text()).strip()
        expr, ok = QInputDialog.getItem(le.window(), tr('Calcul'),
                                        tr('Calcul (+ − * / ^, parenthèses, sqrt, sin, cos, tan en degrés, pi) ; '
                                           'unités en mm : 2cm, 1in, 3/4", 1\'6", 10pt ; angles : 30°15\', '
                                           'N45°E ; ans : dernier résultat ; la liste garde les calculs précédents'),
                                        [cur] + [h for h in hist if h != cur], 0, True)
        if not ok:
            return None
    try:
        v = evaluate(expr, ans)
    except ValueError as ex:
        from PySide6.QtWidgets import QToolTip
        QToolTip.showText(le.mapToGlobal(le.rect().bottomLeft()), str(ex), le)
        return None
    e = expr.strip()
    try:
        float(e.replace(',', '.'))
    except ValueError:                                  # un calcul, pas un simple nombre
        st.setValue('calcul/historique', ([e] + [h for h in hist if h != e])[:HISTORY_MAX])
    st.setValue('calcul/ans', v)
    if isinstance(box, QDoubleSpinBox):
        box.setValue(v)
    elif box is not None and hasattr(box, 'setValue'):
        box.setValue(int(round(v)))
    else:
        le.setText(f'{v:.6g}'.replace('.', decimal_point(le)))
    return v


_FILTER: NumericInputFilter | None = None


def install(app: QApplication | None = None) -> NumericInputFilter:
    """Pose le filtre sur l'application (une seule fois)."""
    global _FILTER
    app = app or QApplication.instance()
    if _FILTER is None:
        _FILTER = NumericInputFilter(app)
        app.installEventFilter(_FILTER)
    return _FILTER
