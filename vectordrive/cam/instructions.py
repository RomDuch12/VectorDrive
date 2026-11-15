"""Instructions machine : opérations sans parcours (palpage, origine,
miroir, messages, mesure d'outil, préchauffage, table à vide…), placées
dans l'ordre des opérations. Chaque instruction : un libellé et ses
champs ; les post-processeurs qui la connaissent l'écrivent (Datron :
plugin de l'atelier), les autres l'ignorent avec un avertissement.

Champ : (nom, libellé, nature, défaut[, choix]) — nature 'float', 'int',
'bool', 'str', 'text' (plusieurs lignes) ou 'choice'. Les champs nommés
dans `advanced` sont rangés dans un groupe « Réglages avancés » replié ;
`pick` dit comment « Prendre sur la sélection » remplit la position
(voir `from_selection`).
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Instruction:
    label: str
    fields: list = field(default_factory=list)
    note: str = ''
    advanced: tuple = ()
    pick: str = ''          # '', 'center', 'corner', 'edge', 'rect', 'axis', 'u', 'two_circles'


# --- choix communs des palpages (libellés ; le post-processeur les traduit) ---------------
CORNERS = ['Avant gauche', 'Avant droit', 'Arrière gauche', 'Arrière droit']
VIEWS = ['Extérieur', 'Intérieur']
DIRECTIONS = ['X+ (arête à droite)', 'X− (arête à gauche)', 'Y+ (arête derrière)', 'Y− (arête devant)']
RESULTS = ['Repère pièce (Wcs)', 'Repère local (Lcs)', 'Aucun (valeur seule)']
RECT_ORIGINS = ['Centre'] + CORNERS
ROTATION_AXES = ['Auto (long côté)', 'Y+', 'X+']
AXES = ['X (+ Z)', 'Y (+ Z)']
WIDTH_SIDES = ['Extérieur (largeur de pièce)', 'Intérieur (largeur de poche)']
FRAMES = ['Wcs (origine pièce)', 'Lcs (origine locale)']
FEATURES = ['Perçage (mesure intérieure)', 'Bossage (mesure extérieure)']
LCS_MODES = ['Décalage incrémental', 'Décalage absolu', 'Rotation incrémentale', 'Rotation absolue',
             'Remise à zéro']

_POINT = [('x', 'X du palpage (mm)', 'float', 0.0), ('y', 'Y du palpage (mm)', 'float', 0.0)]
_SAFE_Z = ('probe_safe_z', 'Z d\'approche (mm)', 'float', 5.0)
_COMMON = [('skip_z_measure', 'Ne pas mesurer Z', 'bool', False),
           ('skip_z_result', 'Rejeter le Z mesuré', 'bool', False),
           ('force_safe_height', 'Hauteur sûre entre les points', 'bool', False),
           ('retract', 'Z après mesure (mm)', 'float', 15.0),
           ('search', 'Course de recherche (mm)', 'float', 15.0),
           ('result', 'Résultat', 'choice', RESULTS[0], RESULTS),
           ('origin_x_shift', 'Décalage origine X (mm)', 'float', 0.0),
           ('origin_y_shift', 'Décalage origine Y (mm)', 'float', 0.0),
           ('origin_z_shift', 'Décalage origine Z (mm)', 'float', 0.0)]
_STOCK_XYZ = [('stock_x', 'Surépaisseur brut X (mm)', 'float', 0.0),
              ('stock_y', 'Surépaisseur brut Y (mm)', 'float', 0.0),
              ('stock_z', 'Surépaisseur brut Z (mm)', 'float', 0.0)]


def _names(fields) -> tuple:
    return tuple(f[0] for f in fields)


INSTRUCTIONS: dict[str, Instruction] = {
    'palpage_z': Instruction('Palpage Z (surface de la pièce)', [
        ('x', 'X du palpage (mm)', 'float', 0.0), ('y', 'Y du palpage (mm)', 'float', 0.0),
        ('origin_z_shift', 'Décalage Z de l\'origine (mm)', 'float', 0.0),
        ('stock_offset', 'Surépaisseur (mm)', 'float', 0.0)],
        'mesure la surface et y met le zéro Z', pick='center'),
    'palpage_memorise': Instruction('Palpage Z mémorisé (série de pièces)', [
        ('x', 'X du palpage (mm)', 'float', 0.0), ('y', 'Y du palpage (mm)', 'float', 0.0),
        ('mode', 'Comportement', 'choice', 'Demander', ['Demander', 'Toujours reprendre', 'Toujours repalper']),
        ('message', 'Question à l\'opérateur', 'str', 'Un palpage enregistré existe. Le reprendre sans repalper ?'),
        ('forget_after', 'Oublier la mesure en fin de programme', 'bool', False),
        ('approach_z', 'Z d\'approche (mm)', 'float', 15.0),
        ('origin_z_shift', 'Décalage Z de l\'origine (mm)', 'float', 0.0),
        ('stock_offset', 'Surépaisseur (mm)', 'float', 0.0),
        ('variable', 'Variable gardée par la machine', 'str', 'dernierPalpage')],
        'la première pièce est palpée et la mesure gardée par la machine ; sur les suivantes, elle est reprise '
        'sans repalper (selon le comportement) ; « oublier » : la pièce suivante repalpe',
        advanced=('approach_z', 'origin_z_shift', 'stock_offset', 'variable'), pick='center'),
    'palpage_coin': Instruction('Palpage d\'un coin', [
        ('corner', 'Coin', 'choice', CORNERS[0], CORNERS), ('view', 'Approche', 'choice', VIEWS[0], VIEWS),
        *_POINT, ('probe_depth', 'Profondeur de palpage (mm)', 'float', 5.0),
        ('distance', 'Distance au coin (mm)', 'float', 10.0),
        ('measure_rotation', 'Mesurer l\'orientation', 'bool', False),
        ('rotation_distance', 'Écart pour l\'orientation (mm)', 'float', 40.0), _SAFE_Z,
        *_COMMON, *_STOCK_XYZ],
        'origine (et orientation) reprises sur un coin ; le palpeur part au-dessus du coin',
        advanced=_names(_COMMON + _STOCK_XYZ), pick='corner'),
    'palpage_arete': Instruction('Palpage d\'une arête', [
        ('direction', 'Arête', 'choice', DIRECTIONS[0], DIRECTIONS), *_POINT,
        ('z_edge_offset', 'Point Z : distance à l\'arête (mm)', 'float', 10.0),
        ('measure_z_offset', 'Hauteur de mesure (mm)', 'float', -0.5),
        ('rotation_offset', 'Écart pour l\'orientation (0 : sans) (mm)', 'float', 0.0),
        ('rotation_only', 'Orientation seule', 'bool', False), _SAFE_Z,
        *_COMMON, ('stock_edge', 'Surépaisseur brut à l\'arête (mm)', 'float', 0.0),
        ('stock_z', 'Surépaisseur brut Z (mm)', 'float', 0.0)],
        'origine reprise sur une arête ; le palpeur part au-dessus de la matière, près de l\'arête',
        advanced=_names(_COMMON) + ('stock_edge', 'stock_z'), pick='edge'),
    'palpage_rectangle': Instruction('Palpage d\'un rectangle (brut)', [
        *_POINT, ('width_x', 'Dimension X (mm)', 'float', 120.0), ('width_y', 'Dimension Y (mm)', 'float', 15.0),
        ('probe_side', 'Côté palpé', 'choice', VIEWS[0], VIEWS),
        ('origin', 'Origine mesurée', 'choice', RECT_ORIGINS[0], RECT_ORIGINS),
        ('probe_depth', 'Profondeur de palpage (mm)', 'float', 5.0),
        ('rotation_distance', 'Écart pour l\'orientation (0 : 80 % du long côté) (mm)', 'float', 0.0),
        ('rotation_axis', 'Sens de l\'orientation', 'choice', ROTATION_AXES[0], ROTATION_AXES), _SAFE_Z,
        ('x_measure_y_shift', 'Mesure X : décalage Y (mm)', 'float', 0.0),
        ('y_measure_x_shift', 'Mesure Y : décalage X (mm)', 'float', 0.0),
        ('z_measure_x_shift', 'Palpage Z : décalage X (mm)', 'float', 0.0),
        ('z_measure_y_shift', 'Palpage Z : décalage Y (mm)', 'float', 0.0),
        ('origin_x_shift', 'Décalage origine X (mm)', 'float', 0.0),
        ('origin_y_shift', 'Décalage origine Y (mm)', 'float', 0.0),
        ('origin_z_shift', 'Décalage origine Z (mm)', 'float', 0.0),
        ('skip_z_measure', 'Ne pas mesurer Z', 'bool', False),
        ('skip_z_result', 'Rejeter le Z mesuré', 'bool', False),
        ('force_safe_height', 'Hauteur sûre entre les points', 'bool', False),
        ('wcs', 'Écrire dans le repère pièce (Wcs)', 'bool', True)],
        'origine et orientation d\'un brut rectangulaire ; le palpeur part au-dessus de l\'origine choisie',
        advanced=('x_measure_y_shift', 'y_measure_x_shift', 'z_measure_x_shift', 'z_measure_y_shift',
                  'origin_x_shift', 'origin_y_shift', 'origin_z_shift', 'skip_z_measure', 'skip_z_result',
                  'force_safe_height', 'wcs'), pick='rect'),
    'palpage_symetrie': Instruction('Palpage d\'un axe de symétrie', [
        ('axis', 'Axe palpé', 'choice', AXES[0], AXES), ('width', 'Largeur (mm)', 'float', 20.0),
        ('side', 'Type', 'choice', WIDTH_SIDES[0], WIDTH_SIDES),
        ('frame', 'Origine', 'choice', FRAMES[0], FRAMES),
        ('position', 'Aller d\'abord au point (SafeRapid)', 'bool', True), *_POINT, _SAFE_Z,
        ('measure_z_offset', 'Hauteur de mesure (mm)', 'float', -0.5),
        ('z_measure_x_shift', 'Palpage Z : décalage X (mm)', 'float', 0.0),
        ('z_measure_y_shift', 'Palpage Z : décalage Y (mm)', 'float', 0.0),
        ('origin_x_shift', 'Décalage origine X (mm)', 'float', 0.0),
        ('origin_y_shift', 'Décalage origine Y (mm)', 'float', 0.0),
        ('origin_z_shift', 'Décalage origine Z (mm)', 'float', 0.0),
        ('search', 'Course de recherche (mm)', 'float', 15.0),
        ('retract', 'Z après mesure (mm)', 'float', 15.0),
        ('skip_z_measure', 'Ne pas mesurer Z', 'bool', False),
        ('skip_z_result', 'Rejeter le Z mesuré', 'bool', False),
        ('force_safe_height', 'Hauteur sûre entre les points', 'bool', False)],
        'milieu d\'une pièce ou d\'une poche entre deux faces', advanced=(
            'z_measure_x_shift', 'z_measure_y_shift', 'origin_x_shift', 'origin_y_shift', 'origin_z_shift',
            'search', 'retract', 'skip_z_measure', 'skip_z_result', 'force_safe_height'), pick='axis'),
    'palpage_u': Instruction('Palpage d\'une forme en U', [
        ('direction', 'Sens du U', 'choice', DIRECTIONS[0], DIRECTIONS),
        ('view', 'Approche', 'choice', VIEWS[0], VIEWS), *_POINT,
        ('width', 'Largeur du fond (mm)', 'float', 20.0),
        ('z_offset', 'Point Z : distance au fond (mm)', 'float', 10.0),
        ('z_side_offset', 'Point Z : distance au côté (mm)', 'float', 10.0),
        ('side_offset', 'Côtés : distance au fond (mm)', 'float', 10.0),
        ('side_z', 'Côtés : hauteur de mesure (mm)', 'float', -0.5),
        ('bottom_z', 'Fond : hauteur de mesure (mm)', 'float', -0.5),
        ('bottom_rotation', 'Orientation : 2e point du fond (mm)', 'float', 0.0),
        ('side_rotation', 'Orientation : 2e point du côté (mm)', 'float', 0.0), _SAFE_Z,
        *_COMMON, *_STOCK_XYZ],
        'fond et deux côtés : arête et symétrie à la fois ; le palpeur part au milieu du U',
        advanced=_names(_COMMON + _STOCK_XYZ), pick='u'),
    'mesure_orientation': Instruction('Mesure d\'orientation (deux repères ronds)', [
        ('x1', 'X repère 1 (mm)', 'float', 0.0), ('y1', 'Y repère 1 (mm)', 'float', 0.0),
        ('d1', 'Ø repère 1 (mm)', 'float', 10.0),
        ('x2', 'X repère 2 (mm)', 'float', 50.0), ('y2', 'Y repère 2 (mm)', 'float', 0.0),
        ('d2', 'Ø repère 2 (mm)', 'float', 10.0),
        ('feature', 'Type de repère', 'choice', FEATURES[0], FEATURES),
        ('axis', 'Alignement nominal', 'choice', AXES[0], AXES),
        ('approach_z', 'Z d\'approche (mm)', 'float', 15.0),
        ('set_origin', 'Origine sur le repère 1', 'bool', False),
        ('show_result', 'Afficher l\'angle', 'bool', True),
        ('max_angle', 'Angle max toléré (0 : sans contrôle) (°)', 'float', 5.0)],
        'deux palpages de cercles, puis rotation du repère local ; au-delà de l\'angle max, '
        'l\'opérateur confirme', pick='two_circles'),
    'repere_local': Instruction('Repère local', [
        ('mode', 'Commande', 'choice', LCS_MODES[0], LCS_MODES),
        ('shift_x', 'X (mm)', 'float', 0.0), ('shift_y', 'Y (mm)', 'float', 0.0), ('shift_z', 'Z (mm)', 'float', 0.0),
        ('gamma', 'Angle autour de Z (°)', 'float', 0.0)],
        'décale ou tourne le repère local par-dessus le repère pièce (qui ne bouge pas)'),
    'compteur_pieces': Instruction('Compteur de pièces', [
        ('var_name', 'Variable', 'str', 'compteur'), ('start_value', 'Valeur initiale', 'int', 1),
        ('step', 'Incrément', 'int', 1), ('show_dialog', 'Afficher la valeur', 'bool', True),
        ('prefix', 'Préfixe du numéro de série', 'str', ''),
        ('digits', 'Chiffres (0 : sans zéros devant)', 'int', 0)],
        'numéro gardé par la machine d\'un lancement à l\'autre'),
    'saisie_operateur': Instruction('Saisie de l\'opérateur (au lancement)', [
        ('caption', 'Titre de la fenêtre', 'str', 'Réglages pièce'),
        ('champs', 'Champs : une ligne « libellé ; type ; défaut ; unité ; variable »', 'text',
         'N° de commande ; Texte ; 2026-001')],
        'types : Position, Avance, Angle, Nombre, Quantité, Texte, Booléen ; chaque valeur va dans une '
        'variable (le libellé sans accents si elle n\'est pas nommée), reprise par le texte machine…'),
    'question': Instruction('Question à l\'opérateur (Oui / Non)', [
        ('message', 'Question', 'str', 'Continuer l\'usinage ?'),
        ('park', 'Aller en position de parking avant', 'bool', True)],
        'sur Non, les opérations qui suivent sont sautées, jusqu\'à la question suivante'),
    'appel_programme': Instruction('Appel d\'un programme de la machine', [
        ('name', 'Nom du programme', 'str', 'Programme'),
        ('path', 'Fichier du programme (sur le poste ou sur la machine)', 'file', '')],
        'programme existant, appelé ici tel quel (il reste maître de son contenu) ; un chemin du poste est '
        'écrit en chemin de la machine (F10 › FAO › Programmes appelés)'),
    'decalage_origine': Instruction('Décalage d\'origine', [
        ('x', 'X (mm)', 'float', 0.0), ('y', 'Y (mm)', 'float', 0.0), ('z', 'Z (mm)', 'float', 0.0)],
        'décale le repère de travail (incrémental)'),
    'rotation_repere': Instruction('Rotation du repère', [
        ('gamma', 'Angle autour de Z (°)', 'float', 0.0),
        ('absolue', 'Angle absolu (sinon ajouté)', 'bool', False)]),
    'miroir': Instruction('Miroir du repère', [
        ('mirror_x', 'Miroir en X', 'bool', True), ('mirror_y', 'Miroir en Y', 'bool', False)]),
    'retablir_miroir': Instruction('Rétablir le repère (sans miroir)', []),
    'message': Instruction('Message à l\'opérateur', [
        ('message', 'Message', 'str', '')], 'affiché dans la barre d\'état de la machine'),
    'retournement': Instruction('Retournement de la pièce', [
        ('message', 'Message', 'str', 'Retourner la pièce puis valider'),
        ('park', 'Aller en position de parking', 'bool', True)],
        'arrosage et broche coupés, attente de l\'opérateur'),
    'mesure_outil': Instruction('Mesure de la longueur d\'outil', [
        ('skip_restoring', 'Ne pas revenir', 'bool', False), ('skip_saving', 'Ne pas enregistrer', 'bool', False),
        ('skip_dialogs', 'Sans dialogue', 'bool', False)]),
    'prechauffage': Instruction('Préchauffage de la broche', [
        ('force', 'Même si la broche est chaude', 'bool', False)]),
    'table_vide': Instruction('Table à vide', [
        ('mode', 'Pompe', 'choice', 'Marche', ['Marche', 'Arrêt'])]),
    'bloc': Instruction('Bloc de programme (texte machine tel quel)', [
        ('texte', 'Lignes du programme', 'text', ''),
        ('p1', 'Paramètre {p1}', 'float', 0.0), ('p2', 'Paramètre {p2}', 'float', 0.0),
        ('p3', 'Paramètre {p3}', 'float', 0.0), ('p4', 'Paramètre {p4}', 'float', 0.0),
        ('p5', 'Paramètre {p5}', 'float', 0.0), ('p6', 'Paramètre {p6}', 'float', 0.0),
        ('noms', 'Noms des paramètres (séparés par ;)', 'str', '')],
        'copié dans le programme, {p1} … {p6} remplacés par les paramètres (fonction personnalisée)',
        advanced=('p5', 'p6', 'noms')),
}


def number(v) -> str:
    """Nombre écrit sans exposant ni zéros inutiles (5, 2.5, -0.125)."""
    s = f'{float(v):.6f}'.rstrip('0').rstrip('.')
    return '0' if s in ('', '-0') else s


def bloc_names(params: dict | None) -> list[str]:
    """Noms donnés aux paramètres {p1} … {p6} d'un bloc (vides : pas de nom)."""
    names = [n.strip() for n in str((params or {}).get('noms') or '').split(';')]
    return (names + [''] * 6)[:6]


def bloc_lines(params: dict) -> list[str]:
    """Lignes d'un bloc de programme, {p1} … {p6} remplacés par leurs
    valeurs (NeoDrive : fonction custom) ; lignes vides retirées."""
    p = params_of('bloc', params)
    text = str(p.get('texte') or '')
    for k in range(1, 7):
        text = text.replace('{p%d}' % k, number(p.get(f'p{k}', 0.0)))
    return [line.rstrip() for line in text.splitlines() if line.strip()]


#: réglages propres à une stratégie (champ `params` de l'opération), décrits comme les instructions
KIND_PARAMS: dict[str, Instruction] = {
    'texte_machine': Instruction('Texte machine', [
        ('text', 'Texte', 'str', 'Texte'),
        ('variable', 'Variable ajoutée (compteur de pièces…)', 'str', ''),
        ('date', 'Ajouter la date du jour', 'bool', False),
        ('x', 'X du centre (mm)', 'float', 0.0), ('y', 'Y du centre (mm)', 'float', 0.0),
        ('height', 'Hauteur des caractères (mm)', 'float', 2.5), ('rotation', 'Rotation (°)', 'float', 0.0),
        ('double', 'Double passe (ébauche puis finition)', 'bool', True),
        ('depth1', 'Profondeur de l\'ébauche (mm)', 'float', 0.15)],
        'police de la commande numérique, texte composé au moment de l\'usinage (n° de série, date) ; '
        'écrit par les post-processeurs qui le connaissent (Datron)', pick='center'),
}


#: types de saisie de l'opérateur
INPUT_TYPES = ('Position', 'Avance', 'Angle', 'Nombre', 'Quantité', 'Texte', 'Booléen')


def input_fields(text: str) -> tuple[list[dict], list[str]]:
    """Champs d'une saisie de l'opérateur : une ligne « libellé ; type ;
    défaut ; unité ; variable » (type Position par défaut). Rend (champs,
    problèmes) — une ligne au type inconnu est écartée."""
    fields, problems = [], []
    for n, line in enumerate((text or '').splitlines(), start=1):
        if not line.strip():
            continue
        parts = [p.strip() for p in line.split(';')] + [''] * 5
        label, kind, default, unit, var = parts[:5]
        kind = kind or 'Position'
        match = next((t for t in INPUT_TYPES if t.lower() == kind.lower()), None)
        if match is None:
            problems.append(f'ligne {n} : type « {kind} » inconnu ({", ".join(INPUT_TYPES)})')
            continue
        fields.append({'label': label or f'Valeur {n}', 'type': match, 'default': default, 'unit': unit,
                       'var': var})
    return fields, problems


def describe(key: str) -> Instruction | None:
    """Description d'une instruction, ou des réglages d'une stratégie."""
    return INSTRUCTIONS.get(key) or KIND_PARAMS.get(key)


def label(key: str) -> str:
    ins = INSTRUCTIONS.get(key)
    return ins.label if ins else key


def params_of(key: str, params: dict | None) -> dict:
    """Réglages complets d'une instruction (ou d'une stratégie à réglages) :
    ceux donnés, sinon les défauts (un choix hors liste reprend le défaut)."""
    ins = describe(key)
    out = {}
    for f in (ins.fields if ins else []):
        name, default = f[0], f[3]
        v = (params or {}).get(name, default)
        try:
            v = type(default)(v) if not isinstance(default, bool) else bool(v)
        except (TypeError, ValueError):
            v = default
        if f[2] == 'choice' and v not in f[4]:
            v = default
        out[name] = v
    return out


def _round(v: float) -> float:
    return round(float(v), 3) + 0.0


def from_selection(key: str, params: dict | None, box, circles=()) -> dict:
    """Réglages repris de la sélection : `box` = (x0, y0, x1, y1) de son
    encombrement (mm, Y vers l'arrière de la machine), `circles` = (x, y,
    rayon) des cercles choisis. Rend les réglages complets, la position (et
    les cotes qui s'en déduisent) remplacée ; inchangés sans `pick`."""
    ins = describe(key)
    p = params_of(key, params)
    if ins is None or not ins.pick:
        return p
    if ins.pick == 'two_circles':
        if len(circles) >= 2:
            (x1, y1, r1), (x2, y2, r2) = circles[0], circles[1]
            p.update(x1=_round(x1), y1=_round(y1), d1=_round(2 * r1), x2=_round(x2), y2=_round(y2),
                     d2=_round(2 * r2), axis=AXES[0] if abs(x2 - x1) >= abs(y2 - y1) else AXES[1])
        return p
    if not box:
        return p
    x0, y0, x1, y1 = box
    cx, cy, w, h = (x0 + x1) / 2, (y0 + y1) / 2, x1 - x0, y1 - y0
    corner_xy = {CORNERS[0]: (x0, y0), CORNERS[1]: (x1, y0), CORNERS[2]: (x0, y1), CORNERS[3]: (x1, y1)}
    x, y = cx, cy
    if ins.pick == 'corner':
        x, y = corner_xy.get(p['corner'], (x0, y0))
    elif ins.pick == 'edge':                       # au-dessus de la matière, près de l'arête
        dx = min(abs(p['z_edge_offset']), w / 2)
        dy = min(abs(p['z_edge_offset']), h / 2)
        x, y = {DIRECTIONS[0]: (x1 - dx, cy), DIRECTIONS[1]: (x0 + dx, cy),
                DIRECTIONS[2]: (cx, y1 - dy), DIRECTIONS[3]: (cx, y0 + dy)}[p['direction']]
    elif ins.pick == 'rect':
        x, y = corner_xy.get(p['origin'], (cx, cy))
        p.update(width_x=_round(w), width_y=_round(h))
    elif ins.pick == 'axis':
        p.update(width=_round(w if p['axis'] == AXES[0] else h))
    elif ins.pick == 'u':                          # côtés parallèles au sens du U
        p.update(width=_round(h if p['direction'] in DIRECTIONS[:2] else w))
    p.update(x=_round(x), y=_round(y))
    return p
