"""Thèmes de l'interface : 30 thèmes intégrés (5 clairs, 25 sombres), dont
celui de TypeEdit, plus ceux des plugins et ceux de l'utilisateur (fichiers
JSON du dossier `themes` des données).

Un thème donne la palette des fenêtres, le style du ruban (onglets,
légendes des groupes, boutons cochés), l'encre des icônes et les couleurs
du plan de travail (fond, page, plaque, grille, sélection, aperçu…).
`resolve(settings)` y ajoute les réglages de l'utilisateur (F10 >
Apparence : couleur d'accent, couleurs du plan de travail, police) ;
`ui.theme.apply_theme` l'applique à l'application.

Le thème « TypeEdit » prend les couleurs du ruban dans l'installation de
TypeEdit du poste (script de personnalisation du ruban, lu seulement),
sinon les valeurs de la V15 : VectorDrive suit les couleurs de l'atelier.
Ce module n'importe pas Qt (essais, ligne de commande).
"""
from __future__ import annotations

import glob
import json
import os
import pathlib
import re
from dataclasses import dataclass, field

W, K = '#ffffff', '#000000'


# --- couleurs ------------------------------------------------------------------
def rgb(c) -> tuple[int, int, int]:
    """'#rrggbb', '#rgb' ou (r, g, b[, a]) → (r, g, b)."""
    if isinstance(c, (tuple, list)):
        return int(c[0]), int(c[1]), int(c[2])
    s = str(c).strip().lstrip('#')
    if len(s) == 3:
        s = ''.join(ch * 2 for ch in s)
    if not re.fullmatch(r'[0-9a-fA-F]{6}', s):
        raise ValueError(f'couleur illisible : {c!r}')
    return int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)


def hexa(r, g, b) -> str:
    return '#%02x%02x%02x' % tuple(max(0, min(255, int(round(v)))) for v in (r, g, b))


def is_color(c) -> bool:
    try:
        rgb(c)
        return True
    except (ValueError, TypeError, IndexError):
        return False


def is_fill(v) -> bool:
    """Couleur, ou dégradé vertical 'haut;bas'."""
    return isinstance(v, str) and all(is_color(x) for x in v.split(';')) and v.count(';') <= 1


def mix(a, b, t: float) -> str:
    """Mélange de a vers b (t : part de b)."""
    (r1, g1, b1), (r2, g2, b2) = rgb(a), rgb(b)
    return hexa(r1 + (r2 - r1) * t, g1 + (g2 - g1) * t, b1 + (b2 - b1) * t)


def luminance(c) -> float:
    """Luminance relative (WCAG 2)."""
    def lin(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = rgb(c)
    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)


def contrast(a, b) -> float:
    """Rapport de contraste WCAG (1 à 21)."""
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def readable(on, light=W, dark=K) -> str:
    """Texte le plus lisible sur le fond `on`."""
    return light if contrast(on, light) >= contrast(on, dark) else dark


def colorref(v: int) -> str:
    """COLORREF Windows (0x00BBGGRR) → '#rrggbb'."""
    v = int(v)
    return hexa(v & 0xff, (v >> 8) & 0xff, (v >> 16) & 0xff)


# --- rôles -----------------------------------------------------------------------
#: couleurs de l'interface : clé → libellé (éditeur de thèmes)
COLOR_ROLES = {
    'window': 'Fenêtres', 'window_text': 'Texte des fenêtres', 'base': 'Champs de saisie',
    'alt_base': 'Lignes alternées', 'text': 'Texte des champs', 'button': 'Boutons',
    'button_text': 'Texte des boutons', 'highlight': 'Sélection (listes, texte)',
    'highlighted_text': 'Texte sélectionné', 'accent': 'Accent (boutons cochés, onglet actif)',
    'tooltip': 'Bulles d\'aide', 'tooltip_text': 'Texte des bulles', 'placeholder': 'Texte indicatif',
    'link': 'Liens', 'disabled': 'Texte désactivé', 'main': 'Fond de la fenêtre principale',
    'ribbon': 'Fond du ruban', 'tab': 'Onglets du ruban', 'tab_text': 'Texte des onglets',
    'tab_selected': 'Onglet actif', 'tab_selected_text': 'Texte de l\'onglet actif',
    'caption': 'Bandeau des groupes', 'caption_text': 'Légende des groupes', 'hover': 'Survol des boutons',
    'checked': 'Bouton coché', 'checked_border': 'Bord du bouton coché', 'info': 'Informations du ruban',
    'status': 'Barre d\'état', 'border': 'Bordures', 'icon': 'Encre des icônes',
    'icon_accent': 'Accent des icônes', 'panel_title': 'Titre des panneaux',
    'panel_title_text': 'Texte des titres de panneaux', 'underline': 'Soulignement de l\'onglet actif',
}
#: couleurs du plan de travail
CANVAS_ROLES = {
    'bg': 'Fond', 'bg2': 'Fond (bas, dégradé)', 'page': 'Page', 'blank': 'Hors page', 'plate': 'Plaque',
    'plate_edge': 'Bord de la plaque', 'grid': 'Grille', 'direction': 'Sens de parcours',
    'frame': 'Cadre de sélection', 'handle': 'Poignées', 'selection': 'Objets sélectionnés',
    'preview': 'Aperçu du tracé', 'snap': 'Accrochage', 'guide': 'Guides', 'symmetry': 'Axe de symétrie',
    'node': 'Points des contours', 'node_line': 'Tangentes', 'node_fill': 'Intérieur des points', 'measure': 'Mesure',
    'ruler': 'Règles', 'ruler_text': 'Graduations',
}
#: rôles facultatifs : vides = calculés (règles d'après la palette, fond uni…)
OPTIONAL = {'tab', 'tab_text', 'caption', 'panel_title', 'panel_title_text', 'underline', 'bg2', 'ruler',
            'ruler_text'}
CAPTIONS = ('texte', 'bandeau')


@dataclass
class Theme:
    key: str
    name: str
    dark: bool
    colors: dict
    canvas: dict
    font: str = ''                   # police de l'interface ('' : celle du système)
    captions: str = 'texte'          # légendes des groupes du ruban : texte ou bandeau
    source: str = 'intégré'          # intégré, TypeEdit, plugin, utilisateur
    path: str = ''                   # fichier d'un thème de l'utilisateur
    seed: dict = field(default_factory=dict)

    def to_json(self) -> dict:
        return {'format': 'vectordrive-theme', 'version': 1, 'key': self.key, 'name': self.name,
                'dark': self.dark, 'font': self.font, 'captions': self.captions,
                'colors': dict(self.colors),
                'canvas': {k: list(v) if isinstance(v, tuple) else v for k, v in self.canvas.items()}}

    def copy(self, **kw) -> 'Theme':
        d = dict(key=self.key, name=self.name, dark=self.dark, colors=dict(self.colors),
                 canvas=dict(self.canvas), font=self.font, captions=self.captions, source=self.source,
                 path=self.path, seed=dict(self.seed))
        d.update(kw)
        return Theme(**d)


def _rgba(v, default):
    """Grille : (r, g, b, a) ; accepte '#rrggbb' (alpha de `default`)."""
    if isinstance(v, (tuple, list)) and len(v) >= 3:
        a = int(v[3]) if len(v) > 3 else default[3]
        return (int(v[0]), int(v[1]), int(v[2]), a)
    if is_color(v):
        return rgb(v) + (default[3],)
    return tuple(default)


def make(key: str, name: str, dark: bool, bg: str, text: str, accent: str, *, surface: str | None = None,
         base: str | None = None, canvas_bg: str | None = None, colors: dict | None = None,
         canvas: dict | None = None, font: str = '', captions: str = 'texte', source: str = 'intégré') -> Theme:
    """Thème complet à partir de quatre couleurs (fond, texte, accent, et
    au besoin surface des boutons) ; `colors` / `canvas` imposent des
    rôles."""
    if dark:
        surface = surface or mix(bg, W, 0.05)
        base = base or mix(bg, K, 0.25)
        c = dict(main=mix(bg, K, 0.18), ribbon=bg, window=bg, window_text=text, base=base,
                 alt_base=mix(base, bg, 0.5), text=text, button=surface, button_text=text, bright_text=W,
                 light=mix(surface, W, 0.08), midlight=mix(surface, W, 0.04), mid=mix(bg, K, 0.1),
                 dark=mix(bg, K, 0.45), shadow=mix(bg, K, 0.7), tooltip=surface, tooltip_text=text,
                 placeholder=mix(text, base, 0.45), link=mix(accent, W, 0.3), disabled=mix(text, bg, 0.55),
                 tab='', tab_text='', tab_selected=bg, tab_selected_text=mix(accent, W, 0.45),
                 caption=mix(surface, accent, 0.3), caption_text=mix(text, bg, 0.3),
                 hover=mix(surface, accent, 0.2), checked=mix(surface, accent, 0.38),
                 border=mix(bg, W, 0.12), status=mix(text, bg, 0.1), icon=mix(text, accent, 0.2),
                 icon_accent='#f06a3c', panel_title='', panel_title_text='')
        cv = dict(bg=canvas_bg or mix(bg, K, 0.45), bg2='', page=mix(bg, W, 0.05), grid=(255, 255, 255, 28),
                  plate_edge='#c9b47a', direction=mix(accent, W, 0.3), frame=mix(text, bg, 0.1),
                  selection='#ec4ba6', preview='#5fa8ff', snap='#ff8a3d', guide='#22c3e6', symmetry='#e055b5',
                  node=mix(text, accent, 0.15), node_line='#8792a3', measure='#ff7043', ruler='', ruler_text='')
        cv['blank'] = mix(cv['page'], K, 0.12)
        cv['plate'] = mix(cv['page'], '#c9b47a', 0.15)
        cv['handle'] = cv['node_fill'] = cv['page']
    else:
        surface = surface or mix(bg, W, 0.5)
        base = base or W
        c = dict(main=bg, ribbon=surface, window=bg, window_text=text, base=base,
                 alt_base=mix(base, bg, 0.6), text=text, button=surface, button_text=text, bright_text=W,
                 light=W, midlight=mix(surface, W, 0.5), mid=mix(surface, K, 0.2), dark=mix(surface, K, 0.35),
                 shadow=mix(surface, K, 0.6), tooltip='#ffffe1', tooltip_text=text,
                 placeholder=mix(text, base, 0.5), link=mix(accent, K, 0.15), disabled=mix(text, bg, 0.55),
                 tab='', tab_text='', tab_selected=surface, tab_selected_text=mix(accent, K, 0.4),
                 caption=mix(bg, accent, 0.18), caption_text=mix(text, bg, 0.45),
                 hover=mix(surface, accent, 0.12), checked=mix(surface, accent, 0.22),
                 border=mix(bg, text, 0.18), status=text, icon=mix(text, accent, 0.25),
                 icon_accent='#d0451b', panel_title='', panel_title_text='')
        cv = dict(bg=canvas_bg or mix(bg, '#3a4250', 0.75), bg2='', page=W, blank='#f4f4f4', plate='#e8e2d0',
                  plate_edge='#8a7a50', grid=(0, 0, 0, 30), direction=mix(accent, K, 0.2), frame='#202020',
                  handle=W, selection='#d01c8b', preview='#1060d0', snap='#e06000', guide='#00a6c8',
                  symmetry='#c02090', node='#203040', node_line='#7a8899', node_fill=W, measure='#d0451b',
                  ruler='', ruler_text='')
    c.update(accent=accent, highlight=accent, highlighted_text=readable(accent), checked_border=accent,
             info=c['tab_selected_text'], progress=accent)
    c.update(colors or {})
    cv.update(canvas or {})
    cv['grid'] = _rgba(cv['grid'], (0, 0, 0, 30))
    return Theme(key, name, dark, c, cv, font, captions, source,
                 seed=dict(bg=bg, text=text, accent=accent, surface=surface, base=base, canvas_bg=canvas_bg))


def with_accent(t: Theme, accent: str) -> Theme:
    """Le thème avec une autre couleur d'accent (réglage de l'utilisateur)."""
    c = dict(t.colors)
    s = c.get('button', c['window'])
    tone = W if t.dark else K
    c.update(accent=accent, highlight=accent, highlighted_text=readable(accent), checked_border=accent,
             progress=accent, checked=mix(s, accent, 0.38 if t.dark else 0.22),
             hover=mix(s, accent, 0.2 if t.dark else 0.12),
             tab_selected_text=mix(accent, tone, 0.45 if t.dark else 0.4),
             link=mix(accent, tone, 0.3 if t.dark else 0.15))
    c['info'] = c['tab_selected_text']
    cv = dict(t.canvas)
    cv['direction'] = mix(accent, tone, 0.3 if t.dark else 0.2)
    return t.copy(colors=c, canvas=cv)


def complete(t: Theme) -> Theme:
    """Rôles manquants (thème d'un fichier, d'un plugin) calculés comme
    pour un thème intégré, à partir de ses couleurs principales."""
    c, cv = t.colors, t.canvas
    try:
        bg = c.get('window') or ('#26292d' if t.dark else '#eef1f5')
        text = c.get('window_text') or c.get('text') or ('#e1e5ec' if t.dark else '#1d2433')
        accent = c.get('accent') or c.get('highlight') or '#3d6fc4'
        base = make(t.key, t.name, t.dark, bg, text, accent, surface=c.get('button'), base=c.get('base'),
                    canvas_bg=cv.get('bg'))
    except ValueError:
        base = BUILTIN['sombre' if t.dark else 'clair']
    colors = {k: v for k, v in c.items() if (k in OPTIONAL and v == '') or is_fill(v)}
    canvas = {k: v for k, v in cv.items() if (k in OPTIONAL and v == '') or is_color(v) or k == 'grid'}
    out = base.copy(key=t.key, name=t.name, font=t.font, source=t.source, path=t.path,
                    captions=t.captions if t.captions in CAPTIONS else 'texte')
    out.colors.update(colors)
    out.canvas.update(canvas)
    out.canvas['grid'] = _rgba(out.canvas.get('grid'), base.canvas['grid'])
    return out


def from_json(d: dict, *, source: str = 'utilisateur', path: str = '') -> Theme:
    if not isinstance(d, dict):
        raise ValueError('thème illisible')
    key = re.sub(r'[^0-9A-Za-z_.-]+', '_', str(d.get('key') or d.get('name') or 'theme')).strip('_') or 'theme'
    t = Theme(key, str(d.get('name') or key), bool(d.get('dark')), dict(d.get('colors') or {}),
              dict(d.get('canvas') or {}), str(d.get('font') or ''), str(d.get('captions') or 'texte'),
              source, path)
    return complete(t)


# --- thèmes intégrés ------------------------------------------------------------------
def _builtin() -> list[Theme]:
    L = []
    # clairs
    L.append(make('clair', 'Clair', False, '#eef1f5', '#1d2433', '#3d6fc4', surface='#f7f8fa', canvas_bg='#5a6270',
                  colors=dict(alt_base='#f3f5f8', placeholder='#8a93a3', link='#1f5fbf', disabled='#9aa3b2',
                              tab_selected='#f7f8fa', tab_selected_text='#1f3d73', caption_text='#6a7385',
                              info='#1f3d73', checked='#cfe0fb', checked_border='#6c95d8', border='#c4cad4',
                              main='#eef1f5', ribbon='#f7f8fa', icon='#2b3a55'),
                  canvas=dict(direction='#0060c0')))
    L.append(typeedit_theme())
    L.append(typeedit13_theme())
    L.append(make('sable', 'Sable', False, '#f1ece2', '#2b2620', '#a85a17', surface='#f8f5ee', canvas_bg='#6b6458',
                  canvas=dict(plate='#eadfc8')))
    L.append(make('contraste_clair', 'Contraste élevé clair', False, W, K, '#0000c8', surface=W, canvas_bg='#3c3c3c',
                  colors=dict(border=K, caption_text=K, disabled='#595959', placeholder='#4d4d4d', icon=K,
                              tab_selected_text='#000080', info='#000080'),
                  canvas=dict(selection='#c80000', grid=(0, 0, 0, 60), frame=K)))
    # sombres
    L.append(make('sombre', 'Sombre', True, '#26292d', '#e1e5ec', '#3d6fc4', surface='#2f3338', base='#1d1f22',
                  canvas_bg='#141619',
                  colors=dict(main='#1f2124', ribbon='#26292d', alt_base='#24272b', tooltip='#2f3338',
                              placeholder='#7d8696', link='#8cb4ff', light='#3a3f46', midlight='#33373d',
                              mid='#2a2d32', dark='#17191b', shadow='#0c0d0e', disabled='#6b7380',
                              tab_selected='#26292d', tab_selected_text='#9cc0ff', caption_text='#9aa3b5',
                              info='#9cc0ff', checked='#2f4a72', checked_border='#6c95d8', border='#3a3f47',
                              status='#d6dbe4', icon='#c8d3ea'),
                  canvas=dict(page='#2a2d33', blank='#24272c', plate='#3d392e', plate_edge='#c9b47a',
                              direction='#5fa8ff', frame='#d8dde6', handle='#2a2d33', node_fill='#2a2d33')))
    dark = [
        ('graphite', 'Graphite', '#2b2b2b', '#e6e6e6', '#4a90d9', '#333333', '#1a1a1a', {}),
        ('charbon', 'Charbon', '#1c1c1c', '#e8e8e8', '#e07b39', '#242424', '#0f0f0f', {}),
        ('ardoise', 'Ardoise', '#2a3139', '#e3e8ef', '#5b9bd5', '#323a44', '#1b2026', {}),
        ('minuit', 'Minuit', '#141b2d', '#dfe6f5', '#4fc3f7', '#1c2540', '#0b1020', {}),
        ('ocean', 'Océan', '#0f2a33', '#d9eef2', '#26c6da', '#163640', '#081b21', {}),
        ('foret', 'Forêt', '#1d2b22', '#dcebdf', '#5cb85c', '#24362b', '#111a14', {}),
        ('mousse', 'Mousse', '#2a2d22', '#e5e8d8', '#a3b84a', '#33372a', '#191b14', {}),
        ('prune', 'Prune', '#2a1f2d', '#eee2f0', '#c678dd', '#342738', '#1a131c', {'selection': '#ffd166'}),
        ('amethyste', 'Améthyste', '#231d33', '#e8e2f5', '#9d7cf5', '#2c2540', '#15111f', {}),
        ('bordeaux', 'Bordeaux', '#2d1b1f', '#f2e1e4', '#e05a6d', '#382228', '#1c1013', {'selection': '#ffd166'}),
        ('braise', 'Braise', '#231a17', '#f0e2dc', '#ff6b35', '#2d211d', '#150f0d', {}),
        ('ambre', 'Ambre', '#24201a', '#f1e8d6', '#f0a500', '#2e2920', '#16130f', {}),
        ('cafe', 'Café', '#2b231e', '#efe4da', '#c8956c', '#352b25', '#1a1512', {}),
        ('cuivre', 'Cuivre', '#262321', '#ece5df', '#d4874e', '#302c29', '#171513', {}),
        ('acier', 'Acier', '#2c3136', '#e4e9ee', '#8fb3d9', '#363c42', '#1c2024', {}),
        ('polaire', 'Nuit polaire', '#2e3440', '#eceff4', '#88c0d0', '#3b4252', '#242933', {}),
        ('crepuscule', 'Crépuscule', '#262335', '#ece6f7', '#ff7edb', '#2f2b42', '#191726', {'selection': '#ffd166'}),
        ('lagon', 'Lagon', '#132a2a', '#daf0ee', '#2ec4b6', '#1a3535', '#0b1c1c', {}),
        ('neon', 'Néon', '#0d0f12', '#e0ffe8', '#39ff14', '#15181d', '#050607', {}),
        ('terminal', 'Terminal ambre', '#120f08', '#ffcc66', '#ffb000', '#1a160c', '#0a0804',
         {'selection': '#ff5f87', 'preview': '#ffe08a'}),
        ('encre', 'Encre', '#161a22', '#d8dee9', '#6c8cff', '#1d222c', '#0d1016', {}),
    ]
    for key, name, bg, text, accent, surface, cbg, cv in dark:
        L.append(make(key, name, True, bg, text, accent, surface=surface, canvas_bg=cbg, canvas=cv))
    L.append(typeedit_dark())
    L.append(make('contraste_sombre', 'Contraste élevé sombre', True, K, W, '#ffff00', surface=K, base=K,
                  canvas_bg=K, colors=dict(border=W, caption_text=W, disabled='#a6a6a6', placeholder='#bfbfbf',
                                           icon=W, tab_selected_text='#ffff00', info='#ffff00', main=K),
                  canvas=dict(page='#0a0a0a', blank='#000000', selection='#00ffff', grid=(255, 255, 255, 70),
                              frame=W)))
    L.append(make('oled', 'Noir OLED', True, K, '#e6e6e6', '#3d8bfd', surface='#0a0a0a', base=K, canvas_bg=K,
                  colors=dict(main=K), canvas=dict(page='#0d0d0d', blank='#050505')))
    return L


# --- TypeEdit ------------------------------------------------------------------------
#: couleurs du ruban de TypeEdit V15 (valeurs d'origine de son script de ruban)
TE_V15 = {
    'RibbonPanelCaptionTopHighlight': '#335672', 'RibbonPanelCaptionTopNoHighlight': '#7e8891',
    'RibbonPanelCaptionText': '#ffffff', 'RibbonBarText': '#ffffff', 'RibbonButtonText': '#4d4d4d',
    'RibbonButtonTextGrayed': '#adadad', 'RibbonStatusText': '#9ba5a7', 'RibbonBarBackground': '#9ca4a7',
    'RibbonCategoryTab': '#d2d2d2', 'RibbonCategoryTabTopHighlight': '#335672',
    'RibbonBarTextActive': '#ffffff', 'RibbonCategoryUnderliningBar': '#1389e2', 'LayerTabTop': '#335672',
    'LayerTabText': '#ffffff', 'RulerTop': '#7e8891', 'RulerText': '#ffffff', 'TipsTop': '#9ca4a7',
    'ButtonHighlightTop': '#7e8891', 'COLOR_BACKGROUNDDIALOG_DAO': '#9ca4a7',
    'COLOR_GRADIENT_TOP_DAO': '#9ca4a7', 'COLOR_GRADIENT_BOTTOM_DAO': '#9ca4a7',
    'COLOR_BUTTON_DOWN_TART': '#3c5f8e', 'COLOR_GRID_SELECTION_BG': '#669731',
    'COLOR_GRID_SELECTION_TEXT': '#ffffff', 'COLOR_PROGRESSBAR_1': '#5a83b7', 'font': 'Segoe UI',
}
#: couleurs du ruban de TypeEdit V13 (valeurs d'origine de son script de ruban,
#: identiques sur le poste et dans l'installation de l'atelier)
TE_V13 = {
    'RibbonPanelCaptionTopHighlight': '#5a83b7', 'RibbonPanelCaptionBottomHighlight': '#5a83b7',
    'RibbonPanelCaptionTopNoHighlight': '#f1b62a', 'RibbonPanelCaptionBottomNoHighlight': '#f6e5bd',
    'RibbonPanelCaptionText': '#ffffff', 'RibbonBarText': '#000000', 'RibbonBarTextActive': '#ffffff',
    'RibbonButtonText': '#4d4d4d', 'RibbonButtonTextGrayed': '#adadad', 'RibbonStatusText': '#17246b',
    'RibbonBarBackground': '#bcc7d8', 'RibbonCategoryTab': '#d2d2d2', 'RibbonCategoryTabTopHighlight': '#5a83b7',
    'RibbonCategoryTabViewTopHighlight': '#e2e8f0', 'LayerTabTop': '#5a83b7', 'LayerTabText': '#ffffff',
    'RulerTop': '#e2e8f0', 'RulerText': '#000000', 'TipsTop': '#bcc7d8', 'ButtonHighlightTop': '#ffffff',
    'ButtonHighlightBottom': '#5a83b7', 'COLOR_BACKGROUNDDIALOG_DAO': '#bcc7d8',
    'COLOR_GRADIENT_TOP_DAO': '#bcc7d8', 'COLOR_GRADIENT_BOTTOM_DAO': '#bcc7d8',
    'COLOR_BUTTON_DOWN_TART': '#3c5f8e', 'COLOR_GRID_SELECTION_BG': '#669731',
    'COLOR_GRID_SELECTION_TEXT': '#ffffff', 'COLOR_PROGRESSBAR_1': '#5a83b7',
    'COLOR_TABSTOP_SELECTION_DAO': '#d5dbe7', 'font': 'Segoe UI',
}

_SET = re.compile(r'visualManager\.SetColor(\w+?)(FromRGB)?\s*[ (]\s*(\d+)\s*(?:,\s*(\d+)\s*,\s*(\d+))?')
_BRUSH = re.compile(r'visualManager\.ModifyType3BrushFromRGB\s+"(\w+)"\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)')
_FONT = re.compile(r'visualManager\.SetFontName\s+"([^"]+)"')


def parse_ribbon_script(text: str) -> dict:
    """Couleurs du script de ruban de TypeEdit : nom → '#rrggbb' (et
    'font'). Les lignes en commentaire (') sont ignorées."""
    out = {}
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("'"):
            continue
        m = _SET.match(s)
        if m:
            name, from_rgb, a, g, b = m.groups()
            if from_rgb and g is not None:
                out[name] = hexa(int(a), int(g), int(b))
            elif not from_rgb:
                out[name] = colorref(int(a))
            continue
        m = _BRUSH.match(s)
        if m:
            out[m.group(1)] = hexa(*(int(x) for x in m.groups()[1:]))
            continue
        m = _FONT.match(s)
        if m:
            out['font'] = m.group(1)
    return out


def typeedit_version(path: str) -> int:
    """Version de TypeEdit d'après le dossier d'installation
    (« TypeEdit_V13-LaserType_V13 » → 13) ; 0 si inconnue."""
    m = re.search(r'TypeEdit_V(\d+)', str(path), re.I)
    return int(m.group(1)) if m else 0


def ribbon_script_files(version: int | None = None) -> list[str]:
    """Scripts de ruban des TypeEdit installés (d'une version donnée, ou
    toutes), la version la plus haute puis le plus récent d'abord."""
    pats = [os.path.join(os.environ.get('PROGRAMDATA', 'C:/ProgramData'), 'Gravotech', 'TypeEdit_*', 'res',
                         'RIBBON', 'ScriptRibbonUI_TE.txt'),
            'C:/TypeEdit_*/res/RIBBON/ScriptRibbonUI_TE.txt']
    found = {os.path.normcase(os.path.abspath(f)): f for p in pats for f in glob.glob(p)}
    files = [f for f in found.values() if version is None or typeedit_version(f) == version]
    return sorted(files, key=lambda f: (-typeedit_version(f), -os.path.getmtime(f)))


def read_ribbon_script(path) -> dict:
    b = pathlib.Path(path).read_bytes()
    enc = 'utf-16' if b[:2] in (b'\xff\xfe', b'\xfe\xff') else 'latin-1'
    return parse_ribbon_script(b.decode(enc, errors='replace'))


_installed: dict = {}


def installed_typeedit(version: int | None = None) -> dict:
    """Couleurs du TypeEdit installé (lues une fois) : le plus récent, ou
    celui de la version demandée ; {} s'il n'y en a pas."""
    if version not in _installed:
        _installed[version] = {}
        if os.environ.get('VECTORDRIVE_NO_TYPEEDIT') != '1':
            for f in ribbon_script_files(version):
                try:
                    vals = read_ribbon_script(f)
                except OSError:
                    continue
                if vals:
                    _installed[version] = vals
                    break
    return _installed[version]


def typeedit_theme(vals: dict | None = None, *, key: str = 'typeedit', name: str = 'TypeEdit') -> Theme:
    """Thème « comme TypeEdit » : gris-bleu, bandeaux des groupes, plan de
    travail blanc. `vals` : couleurs du script de ruban (TE_V15 par défaut)."""
    v = dict(TE_V15)
    v.update(vals or {})
    bar = v['RibbonBarBackground']
    dlg = v.get('COLOR_BACKGROUNDDIALOG_DAO', bar)
    cap = v['RibbonPanelCaptionTopNoHighlight']
    cap2 = v.get('RibbonPanelCaptionBottomNoHighlight', cap)
    hi = v['RibbonPanelCaptionTopHighlight']
    tab_sel = v['RibbonCategoryTabTopHighlight']
    sel_bg = v.get('COLOR_GRID_SELECTION_BG', '#669731')
    cap_text = v.get('RibbonPanelCaptionText', W)
    if contrast(cap, cap_text) < 2.5:                    # bandeau clair (versions anciennes) : texte foncé
        cap_text = '#1a1a1a'
    tab_text = v.get('RibbonBarText', K)
    if contrast(bar, tab_text) < 3:                      # libellés des onglets lisibles sur le ruban
        tab_text = '#1a1a1a'
    t = make(key, name, False, dlg, K, tab_sel, surface=mix(dlg, W, 0.55), base=W, canvas_bg=W,
             font=v.get('font', ''), captions='bandeau', source='TypeEdit',
             colors=dict(main=bar, ribbon=bar, button_text=K, tab='', tab_text=tab_text,
                         tab_selected=tab_sel, tab_selected_text=v.get('RibbonBarTextActive', W),
                         caption=cap if cap2 == cap else f'{cap};{cap2}', caption_text=cap_text,
                         hover=v.get('ButtonHighlightTop', hi), checked=mix(bar, hi, 0.45), checked_border=hi,
                         info=K, status=K, highlight=sel_bg,
                         highlighted_text=v.get('COLOR_GRID_SELECTION_TEXT', readable(sel_bg)),
                         progress=v.get('COLOR_PROGRESSBAR_1', hi), border=mix(bar, K, 0.25),
                         tooltip=v.get('TipsTop', bar), tooltip_text=K, icon='#2b3a55',
                         panel_title=v.get('LayerTabTop', hi), panel_title_text=v.get('LayerTabText', W),
                         disabled=v.get('RibbonButtonTextGrayed', '#adadad'), underline=v.get(
                             'RibbonCategoryUnderliningBar', tab_sel)),
             canvas=dict(page=W, blank=W, plate='#f2f2f2', plate_edge='#d00000', grid=(0, 0, 0, 36),
                         ruler=v.get('RulerTop', cap), ruler_text=v.get('RulerText', W)))
    t.seed['typeedit'] = True
    return t


def typeedit13_theme(vals: dict | None = None) -> Theme:
    """Thème « TypeEdit 13 » : ruban bleu-gris, bandeaux des groupes, onglet
    courant et onglets de calques bleus à texte blanc, règles claires à
    graduations noires, plan de travail blanc. Couleurs du script de ruban
    de la V13 (`vals`, TE_V13 par défaut) ; à l'écran, TypeEdit 13 peint les
    bandeaux des groupes de la couleur « Highlight » (bleu), pas de
    l'orangé « NoHighlight » du script (relevé sur une capture de la V13)."""
    v = dict(TE_V13)
    v.update(vals or {})
    v['RibbonPanelCaptionTopNoHighlight'] = v['RibbonPanelCaptionTopHighlight']
    v['RibbonPanelCaptionBottomNoHighlight'] = v.get('RibbonPanelCaptionBottomHighlight',
                                                     v['RibbonPanelCaptionTopHighlight'])
    v.setdefault('RibbonCategoryUnderliningBar', v['RibbonCategoryTabTopHighlight'])
    t = typeedit_theme(v, key='typeedit13', name='TypeEdit 13')
    hi = v['RibbonPanelCaptionTopHighlight']
    c = dict(t.colors)
    # survol : dégradé blanc → bleu du script, rendu par sa teinte claire
    c['hover'] = mix(v.get('ButtonHighlightTop', W), v.get('ButtonHighlightBottom', hi), 0.25)
    c['status'] = v.get('RibbonStatusText', K)
    c['alt_base'] = v.get('COLOR_TABSTOP_SELECTION_DAO', c.get('alt_base', ''))
    # plaque comme à l'écran de la V13 : blanche, bordée d'un trait noir
    t = t.copy(colors=c, canvas=dict(t.canvas, plate=W, plate_edge=K))
    t.seed['typeedit'] = True
    t.seed['typeedit13'] = True
    return t


def typeedit_dark() -> Theme:
    """Les teintes de TypeEdit en sombre (bandeaux bleu foncé, accent bleu vif)."""
    t = make('typeedit_sombre', 'TypeEdit sombre', True, '#2b3238', '#e3e8ec', '#1389e2', surface='#353d44',
             canvas_bg='#1f252a', captions='bandeau',
             colors=dict(caption='#335672', caption_text=W, panel_title='#335672', panel_title_text=W,
                         tab_selected='#335672', tab_selected_text=W),
             canvas=dict(ruler='#3f4950', ruler_text='#e3e8ec'))
    return t


BUILTIN: dict[str, Theme] = {}
for _t in _builtin():
    BUILTIN[_t.key] = _t
LIGHT_KEYS = [k for k, t in BUILTIN.items() if not t.dark]
DARK_KEYS = [k for k, t in BUILTIN.items() if t.dark]


# --- thèmes des plugins et de l'utilisateur -------------------------------------------
def user_dir() -> pathlib.Path:
    env = os.environ.get('VECTORDRIVE_THEMES')
    if env:
        return pathlib.Path(env)
    from ..portable import data_dir
    return data_dir() / 'themes'


def user_themes() -> list[Theme]:
    out = []
    d = user_dir()
    if not d.is_dir():
        return out
    for f in sorted(d.glob('*.json')):
        try:
            out.append(from_json(json.loads(f.read_text(encoding='utf-8')), path=str(f)))
        except (OSError, ValueError, TypeError, AttributeError):
            continue
    return out


def plugin_themes() -> list[Theme]:
    from ..plugins import REGISTRY
    out = []
    for d in getattr(REGISTRY, 'themes', []):
        try:
            out.append(d if isinstance(d, Theme) else from_json(d, source='plugin'))
        except (ValueError, TypeError, AttributeError):
            continue
    return out


def all_themes() -> dict[str, Theme]:
    """Tous les thèmes : intégrés (TypeEdit lu dans l'installation), plugins,
    utilisateur (un thème de l'utilisateur remplace un homonyme)."""
    out = dict(BUILTIN)
    inst = installed_typeedit()
    if inst:
        out['typeedit'] = typeedit_theme(inst).copy(name='TypeEdit (couleurs du poste)')
    inst13 = installed_typeedit(13)
    if inst13:
        out['typeedit13'] = typeedit13_theme(inst13).copy(name='TypeEdit 13 (couleurs du poste)')
    for t in plugin_themes() + user_themes():
        out[t.key] = t
    return out


def get(key: str) -> Theme:
    themes = all_themes()
    return themes.get(key) or themes.get(LEGACY.get(key, ''), BUILTIN['clair'])


#: anciens réglages « vue/theme »
LEGACY = {'light': 'clair', 'dark': 'sombre', 'typeedit_classique': 'typeedit13'}
#: thème d'un poste qui n'en a pas choisi (0.552.0 : Crépuscule, avant Clair)
DEFAULT_KEY = 'crepuscule'


def save_user(t: Theme) -> pathlib.Path:
    d = user_dir()
    d.mkdir(parents=True, exist_ok=True)
    f = d / f'{t.key}.json'
    f.write_text(json.dumps(t.to_json(), ensure_ascii=False, indent=1), encoding='utf-8')
    return f


def delete_user(key: str) -> bool:
    f = user_dir() / f'{key}.json'
    if f.is_file():
        f.unlink()
        return True
    return False


def new_key(name: str) -> str:
    base = re.sub(r'[^0-9a-z]+', '_', name.lower()).strip('_') or 'theme'
    taken = set(all_themes())
    k, n = f'perso_{base}', 2
    while k in taken:
        k, n = f'perso_{base}_{n}', n + 1
    return k


# --- réglages de l'utilisateur ---------------------------------------------------------
#: couleurs du plan de travail qu'on peut imposer dans F10 (clé → rôle)
CANVAS_OVERRIDES = {'vue/c_fond': 'bg', 'vue/c_page': 'page', 'vue/c_plaque': 'plate', 'vue/c_grille': 'grid',
                    'vue/c_selection': 'selection', 'vue/c_apercu': 'preview', 'vue/c_accrochage': 'snap'}


def _setting(settings, key, default=''):
    v = settings.value(key, default) if settings is not None else default
    return '' if v is None else str(v)


def chosen_key(settings, system_dark: bool = False) -> str:
    """Thème choisi : « vue/theme », ou pour « systeme » le thème clair ou
    sombre préféré selon le système."""
    k = _setting(settings, 'vue/theme', DEFAULT_KEY) or DEFAULT_KEY
    if k == 'systeme':
        return (_setting(settings, 'vue/theme_sombre', 'sombre') or 'sombre') if system_dark else \
            (_setting(settings, 'vue/theme_clair', 'clair') or 'clair')
    return LEGACY.get(k, k)


def resolve(settings, system_dark: bool = False, key: str | None = None) -> Theme:
    """Thème choisi, avec l'accent, les couleurs du plan de travail et la
    police imposés par l'utilisateur."""
    t = get(key or chosen_key(settings, system_dark))
    acc = _setting(settings, 'vue/accent')
    if is_color(acc):
        t = with_accent(t, acc)
    over = {}
    for sk, role in CANVAS_OVERRIDES.items():
        v = _setting(settings, sk)
        if is_color(v):
            over[role] = v
    if over:
        cv = dict(t.canvas)
        cv.update(over)
        if 'grid' in over:
            cv['grid'] = _rgba(over['grid'], t.canvas['grid'])
        if 'bg' in over:
            cv['bg2'] = ''
        t = t.copy(canvas=cv)
    if _setting(settings, 'vue/police_ui_perso', 'false') in ('true', '1', 'True'):
        t = t.copy(font=_setting(settings, 'vue/police_ui') or t.font)
    return t


# --- feuille de style ---------------------------------------------------------------------
DENSITY = {'compacte': (1, '3px 10px', 2), 'normale': (2, '5px 14px', 4), 'aeree': (4, '7px 18px', 6)}


def _bg(v: str) -> str:
    """Fond uni ou dégradé vertical ('haut;bas')."""
    if ';' in v:
        a, b = v.split(';', 1)
        return f'qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {a}, stop:1 {b})'
    return v


def stylesheet(t: Theme, *, density: str = 'normale', radius: int = 3, captions: str = 'theme') -> str:
    """Feuille de style de la fenêtre principale (ruban, panneaux, état)."""
    c = t.colors
    pad, tab_pad, _gap = DENSITY.get(density, DENSITY['normale'])
    cap_mode = t.captions if captions in ('theme', '') else captions
    lines = [
        f'QMainWindow {{ background: {c["main"]}; }}',
        f'QTabWidget::pane {{ border-top: 1px solid {c["border"]}; background: {c["ribbon"]}; }}',
        f'QTabBar::tab {{ padding: {tab_pad};'
        + (f' background: {c["tab"]};' if c.get('tab') else '')
        + (f' color: {c["tab_text"]};' if c.get('tab_text') else '') + ' }',
        f'QTabBar::tab:selected {{ background: {c["tab_selected"]}; font-weight: bold; '
        f'color: {c["tab_selected_text"]};'
        + (f' border-bottom: 2px solid {c["underline"]};' if c.get('underline') else '') + ' }',
        f'QLabel#ribbonInfo {{ color: {c["info"]}; padding: 4px 10px; font-family: Consolas, monospace; }}',
        f'QToolButton {{ padding: {pad}px; }}',
        f'QToolButton:hover {{ background: {c["hover"]}; border-radius: {radius}px; }}',
        f'QToolButton:checked {{ background: {c["checked"]}; border: 1px solid {c["checked_border"]}; '
        f'border-radius: {radius}px; }}',
        f'QStatusBar {{ color: {c["status"]}; }}',
    ]
    if cap_mode == 'bandeau':
        lines.append(f'QLabel#ribbonGroupTitle {{ background: {_bg(c["caption"])}; color: {c["caption_text"]}; '
                     f'font-size: 9pt; border-radius: {radius}px; padding: 0px 6px; margin-top: 1px; }}')
    else:
        lines.append(f'QLabel#ribbonGroupTitle {{ color: {c["caption_text"]}; font-size: 9pt; }}')
    if c.get('panel_title'):
        lines.append(f'QDockWidget::title {{ background: {c["panel_title"]}; color: {c.get("panel_title_text") or W}; '
                     f'padding: 3px 6px; }}')
        lines.append(f'QDockWidget {{ color: {c.get("panel_title_text") or W}; }}')
        # la barre de titre commune des panneaux (`ui.columns.DockBar`) : les mêmes couleurs
        lines.append(f'QWidget#dockBar {{ background: {c["panel_title"]}; }}')
        lines.append(f'QWidget#dockBar QLabel, QWidget#dockBar QToolButton '
                     f'{{ color: {c.get("panel_title_text") or W}; }}')
    return '\n'.join(lines) + '\n'


def swatches(t: Theme) -> list[str]:
    """Quelques couleurs représentatives (aperçu dans les listes)."""
    c, cv = t.colors, t.canvas
    return [c['window'], c['ribbon'], c['accent'], cv['bg'] if ';' not in cv['bg'] else cv['bg'].split(';')[0],
            c['window_text']]
