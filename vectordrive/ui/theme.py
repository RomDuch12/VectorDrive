"""Application du thème choisi (`themes.py`) : palette des fenêtres,
police, couleurs du plan de travail et des icônes — indépendamment du
thème de Windows, sans quoi les panneaux passent en noir sous un thème
sombre et les libellés du ruban deviennent illisibles."""
from __future__ import annotations

from PySide6.QtGui import QColor, QFont, QPalette

from . import themes as T

#: réglage « vue/theme » : une clé de thème, ou « systeme » (thème clair ou
#: sombre préféré selon Windows)
MODES = ('clair', 'sombre', 'systeme')

_R = QPalette.ColorRole
ROLES = {_R.Window: 'window', _R.WindowText: 'window_text', _R.Base: 'base', _R.AlternateBase: 'alt_base',
         _R.Text: 'text', _R.Button: 'button', _R.ButtonText: 'button_text', _R.Highlight: 'highlight',
         _R.HighlightedText: 'highlighted_text', _R.ToolTipBase: 'tooltip', _R.ToolTipText: 'tooltip_text',
         _R.PlaceholderText: 'placeholder', _R.Link: 'link', _R.BrightText: 'bright_text', _R.Light: 'light',
         _R.Midlight: 'midlight', _R.Mid: 'mid', _R.Dark: 'dark', _R.Shadow: 'shadow'}

#: couleurs du plan de travail des thèmes Clair et Sombre (compatibilité)
CANVAS_LIGHT = T.BUILTIN['clair'].canvas
CANVAS_DARK = T.BUILTIN['sombre'].canvas

_current: T.Theme | None = None
_system_font: QFont | None = None


def system_is_dark() -> bool:
    """Thème sombre demandé par le système (Qt 6.5 et plus)."""
    try:
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QGuiApplication
        return QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark
    except Exception:
        return False


def is_dark(mode: str) -> bool:
    return mode == 'sombre' or (mode == 'systeme' and system_is_dark()) or \
        (mode not in MODES and T.get(mode).dark)


def palette_of(t: T.Theme) -> QPalette:
    p = QPalette()
    for role, key in ROLES.items():
        v = t.colors.get(key)
        if v:
            p.setColor(role, QColor(v.split(';')[0]))
    dis = QColor(t.colors['disabled'])
    for role in (_R.WindowText, _R.Text, _R.ButtonText):
        p.setColor(QPalette.ColorGroup.Disabled, role, dis)
    return p


def apply(app, t: T.Theme, *, font_size: int = 0) -> T.Theme:
    """Applique le thème `t` à l'application (style Fusion, palette, police)."""
    global _current, _system_font
    if app is not None:
        if _system_font is None:
            _system_font = QFont(app.font())
        app.setStyle('Fusion')
        app.setPalette(palette_of(t))
        f = QFont(_system_font)
        if t.font:
            f.setFamily(t.font)
        if font_size and font_size > 0:
            f.setPointSize(int(font_size))
        if f != app.font():
            app.setFont(f)
    _current = t
    return t


def apply_theme(app, mode: str, settings=None) -> bool:
    """Applique le thème `mode` (clé de thème, ou clair / sombre / systeme),
    avec les réglages de l'utilisateur s'ils sont donnés ; rend True s'il
    est sombre."""
    sysdark = system_is_dark()
    key = T.chosen_key(settings, sysdark) if mode == 'systeme' and settings is not None else \
        (('sombre' if sysdark else 'clair') if mode == 'systeme' else mode)
    t = T.resolve(settings, sysdark, key=key) if settings is not None else T.get(key)
    size = 0
    if settings is not None:
        try:
            size = int(float(settings.value('vue/taille_police_ui', 0) or 0))
        except (TypeError, ValueError):
            size = 0
    apply(app, t, font_size=size)
    return t.dark


def apply_light(app) -> None:
    apply(app, T.BUILTIN['clair'])


def apply_dark(app) -> None:
    apply(app, T.BUILTIN['sombre'])


def current() -> T.Theme:
    """Thème appliqué (à défaut : Clair ou Sombre selon la palette)."""
    if _current is not None:
        return _current
    from .icons import dark_theme
    return T.BUILTIN['sombre' if dark_theme() else 'clair']


def canvas_colors() -> dict:
    return current().canvas


def ink(color: str) -> str:
    """Couleur d'outil telle qu'affichée : en thème sombre, le noir passe
    en gris clair et une encre foncée (bleu pur…) est éclaircie vers le
    blanc, pour rester lisible sur le fond sombre."""
    from .icons import dark_theme
    if not dark_theme():
        return color
    c = QColor(color)
    r, g, b = c.redF(), c.greenF(), c.blueF()
    lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
    if max(r, g, b) < 0.25:
        return '#e6e6e6'
    if lum < 0.3:
        k = 0.5 * (0.3 - lum) / 0.3 + 0.25            # part de blanc mêlée
        c.setRgbF(r + (1 - r) * k, g + (1 - g) * k, b + (1 - b) * k)
        return c.name()
    return color
