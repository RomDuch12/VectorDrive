"""Champs de valeur de toute l'application (QDoubleSpinBox, QSpinBox et
lignes de saisie numériques) :

* un double-clic sélectionne TOUTE la valeur (Qt ne prenait que le mot sous
  le curseur : la partie entière ou les décimales) ;
* le clic qui entre dans un champ sélectionne aussi toute sa valeur, prête à
  être remplacée (sauf une partie choisie en glissant) ;
* jamais de flèches : les champs n'ont plus leurs boutons ▲▼ ;
* les touches ↑ ↓ passent au champ de valeur précédent ou suivant de la
  fenêtre, sa valeur sélectionnée : un formulaire se remplit au clavier
  (réponse du 15/11 à la question 37) ; la molette ne change plus une valeur
  (elle fait défiler le formulaire) ; Page précédente et Page suivante la
  changent toujours ;
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
from PySide6.QtWidgets import (QAbstractScrollArea, QAbstractSpinBox, QApplication, QDateTimeEdit, QDoubleSpinBox,
                               QLineEdit, QScrollArea)


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


_POLISH, _FOCUS_IN = QEvent.Type.Polish, QEvent.Type.FocusIn
_RELEASE, _DOUBLE, _KEY, _WHEEL = (QEvent.Type.MouseButtonRelease, QEvent.Type.MouseButtonDblClick,
                                   QEvent.Type.KeyPress, QEvent.Type.Wheel)
#: les seuls événements regardés (le filtre voit passer tous ceux de l'application) ; pas la sortie d'un champ, que
#: Qt envoie aussi pendant la destruction d'une fenêtre (chaque entrée réarme ou désarme le clic)
_WATCHED = frozenset((_POLISH, _FOCUS_IN, _RELEASE, _DOUBLE, _KEY, _WHEEL))
_NO_BUTTONS = QAbstractSpinBox.ButtonSymbols.NoButtons


def _select_value(le: QLineEdit) -> None:
    """Toute la valeur : celle d'un champ numérique sans son suffixe (« mm », « ° »), comme Tab ; sinon tout le texte."""
    p = le.parentWidget()
    if isinstance(p, QAbstractSpinBox):
        p.selectAll()
    else:
        le.selectAll()


def _field_of(w):
    """Le champ de valeur dont `w` est la ligne de saisie (ou `w`)."""
    p = w.parentWidget() if isinstance(w, QLineEdit) else None
    return p if isinstance(p, QAbstractSpinBox) else w


def _scroll_area_of(w):
    """La zone qui défile où se trouve `w` (None : aucune dans sa fenêtre)."""
    p = w.parentWidget()
    while p is not None:
        if isinstance(p, QAbstractScrollArea):
            return p
        if p.isWindow():
            return None
        p = p.parentWidget()
    return None


def keeps_arrows(w) -> bool:
    """Un champ où ↑ ↓ et la molette gardent leur rôle de Qt : date ou heure (ses parties), champ marqué
    `vd_fleches`."""
    f = _field_of(w)
    return isinstance(f, QDateTimeEdit) or bool(f.property('vd_fleches'))


def is_value_field(w) -> bool:
    """`w` est un champ de valeur où l'on peut saisir : un champ numérique (pas sa ligne de saisie interne), ou une
    ligne de saisie numérique."""
    if isinstance(w, QAbstractSpinBox):
        return not w.isReadOnly()
    return isinstance(w, QLineEdit) and not isinstance(w.parentWidget(), QAbstractSpinBox) \
        and numeric_editor(w) is not None and not w.isReadOnly()


def next_field(w, forward: bool = True):
    """Le champ de valeur suivant (ou précédent) de la fenêtre de `w`, dans l'ordre de Tab : montré, actif ; après
    le dernier, le premier. None : pas d'autre champ."""
    start = _field_of(w)
    win = start.window()
    cur = start
    for _ in range(200000):                              # (la chaîne de la fenêtre principale : des milliers de maillons)
        cur = cur.nextInFocusChain() if forward else cur.previousInFocusChain()
        if cur is None or cur is start:
            return None
        if cur.window() is win and cur.isEnabled() and cur.isVisibleTo(win) \
                and cur.focusPolicy() & Qt.FocusPolicy.TabFocus and is_value_field(cur):
            return cur
    return None


def move_field(w, forward: bool = True) -> bool:
    """↑ ↓ : le focus au champ de valeur précédent ou suivant, sa valeur sélectionnée (la valeur en cours de saisie
    est prise, comme avec Tab). False : pas d'autre champ."""
    nxt = next_field(w, forward)
    if nxt is None:
        return False
    nxt.setFocus(Qt.FocusReason.TabFocusReason if forward else Qt.FocusReason.BacktabFocusReason)
    nxt.selectAll()
    area = _scroll_area_of(nxt)
    if isinstance(area, QScrollArea):                    # le formulaire défile jusqu'au champ atteint (Qt ne le fait
        area.ensureWidgetVisible(nxt)                    # que pour Tab)
    return True


class NumericInputFilter(QObject):
    """Filtre d'événements de l'application (voir le module)."""

    def eventFilter(self, obj, ev) -> bool:                      # noqa: N802 (API Qt)
        t = ev.type()
        if t not in _WATCHED:
            return False
        if t == _POLISH:                                            # jamais de flèches (demande du 15/11)
            if isinstance(obj, QAbstractSpinBox) and obj.buttonSymbols() != _NO_BUTTONS:
                obj.setButtonSymbols(_NO_BUTTONS)
            if isinstance(obj, QAbstractSpinBox) and obj.focusPolicy() == Qt.FocusPolicy.WheelFocus \
                    and not keeps_arrows(obj):
                obj.setFocusPolicy(Qt.FocusPolicy.StrongFocus)      # la molette ne donne plus le focus au champ
            return False
        if t == _FOCUS_IN:
            le = numeric_editor(obj)
            if le is not None:                                      # entré au clic : toute la valeur au relâché
                le.setProperty('vd_click_select', ev.reason() == Qt.FocusReason.MouseFocusReason)
            return False
        if t == _WHEEL:                                             # la molette donne aussi le focus « souris » :
            le = numeric_editor(obj)                                # pas un clic, rien à sélectionner ensuite
            if le is not None:
                le.setProperty('vd_click_select', False)
            if isinstance(_field_of(obj), QAbstractSpinBox) and not keeps_arrows(obj):
                # la molette ne change plus une valeur : donnée à la zone qui défile (le formulaire) ; sans zone, ou
                # avec Ctrl, au parent du champ (plein écran translucide : son filtre zoome le dessin)
                field = _field_of(obj)
                area = _scroll_area_of(field)
                ctrl = bool(ev.modifiers() & Qt.KeyboardModifier.ControlModifier)
                target = area.viewport() if area is not None and not ctrl else field.parentWidget()
                if target is not None:
                    QApplication.sendEvent(target, ev)
                ev.accept()                                         # (Qt ne la propose plus aux parents)
                return True
            return False
        if t == _RELEASE:
            le = numeric_editor(obj)
            if le is not None and le.property('vd_click_select'):
                le.setProperty('vd_click_select', False)            # le clic suivant place le curseur
                if not le.hasSelectedText():                        # une partie choisie en glissant : gardée
                    _select_value(le)
            return False
        if t == _DOUBLE:
            le = numeric_editor(obj)
            if le is not None:
                QTimer.singleShot(0, le.selectAll)              # après la sélection du mot par Qt
            return False
        if t == _KEY:
            le = numeric_editor(obj)
            if le is not None:
                le.setProperty('vd_click_select', False)            # au clavier : le clic suivant place le curseur
            if le is None or le.isReadOnly():
                return False
            if ev.key() in (Qt.Key.Key_Up, Qt.Key.Key_Down) and not keeps_arrows(obj) \
                    and not ev.modifiers() & ~Qt.KeyboardModifier.KeypadModifier:
                move_field(obj, ev.key() == Qt.Key.Key_Down)        # ↑ ↓ : d'un champ à l'autre, jamais la valeur
                return True
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
