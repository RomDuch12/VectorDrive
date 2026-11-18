"""Panneau FAO : outils d'usinage, opérations, calcul et affichage des
parcours, post-traitement, parcours TypeEdit."""
from __future__ import annotations

import dataclasses
import json
import math
import pathlib

from PySide6.QtCore import QLocale, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox,
                               QFileDialog, QFormLayout, QGridLayout, QGroupBox, QHBoxLayout, QHeaderView,
                               QLabel, QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QPushButton,
                               QSizePolicy, QSpinBox, QStyle, QTableWidget, QTableWidgetItem, QToolButton,
                               QVBoxLayout, QWidget)

from ..cam import model, strategies
from ..i18n import tr
import itertools as _it

_UNIQUE = _it.count()                       # empreintes illisibles : jamais deux fois la même
from .layers import swatch

#: libellés des champs (outils et opérations)
LABELS = {
    'name': 'Nom', 'kind': 'Nature', 'diameter': 'Diamètre (mm)', 'tip': 'Pointe (mm)',
    'angle': 'Angle au sommet (°)', 'flutes': 'Nombre de dents', 'cut_length': 'Longueur utile (mm)',
    'stickout': 'Dépassement hors pince (mm, 0 = non vérifié)',
    'holder_diameter': 'Ø de l\'écrou de pince / porte-outil (mm)',
    'number': 'N° dans le magasin (T)', 'ref': 'Référence', 'vendor': 'Fournisseur', 'spindle': 'Broche (tr/min)',
    'feed': 'Avance (mm/min)', 'plunge': 'Plongée (mm/min)', 'ramp_feed': 'Avance en rampe (mm/min, 0 = plongée)',
    'finish_feed': 'Avance de finition (mm/min)', 'feed_frame': 'Cadre de vitesses actif',
    'step_down': 'Passe en Z (mm)',
    'stepover': 'Recouvrement (fraction du Ø)', 'power': 'Puissance laser (%)',
    'frequency': 'Fréquence laser (kHz)', 'tool_id': 'Outil', 'sources': 'Couleurs du dessin',
    'depth': 'Profondeur (mm)', 'side': 'Côté', 'climb': 'Avalant', 'stock': 'Surépaisseur (mm)',
    'stock_z': 'Surépaisseur Z : au fond (mm)',
    'z_start': 'Z de départ : dessus de la matière (mm)',
    'tab_spacing': "Un pontet tous les (mm, 0 = d'après le nombre)",
    'tab_gap': "Distance entre ponts (mm, 0 = d'après le nombre)",
    'tab_max': 'Pontets au plus, par contour (0 : sans limite)',
    'tab_mode': 'Type de pontets',
    'sweep_by_zone': 'Par zone (sinon : avec sauts d\'îlots)',
    'finish': 'Passe de finition', 'peck': 'Débourrage (mm, 0 = non)', 'tabs': 'Pontets',
    'drill_points': 'Points percés', 'drill_mode': 'Perçage en passes',
    'drill_feed_retract': 'Remontée en vitesse de travail (sinon rapide)',
    'tab_width': 'Largeur des pontets (mm)', 'tab_height': 'Hauteur des pontets (mm)',
    'ramp': 'Entrée en rampe', 'safe_z': 'Dégagement (mm)', 'clear_z': 'Approche (mm)',
    'safe_z_faced': 'Dégagement sur une zone déjà usinée : surfaçage ou poche d’avant (mm, 0 : sans)',
    'ramp_angle': 'Angle de rampe (°, 0 = 5°)', 'ramp_max': 'Distance maxi de la rampe (mm, 0 = sans limite)',
    'pass_order': 'Passes multiples',
    'link_passes': 'Connecter les passes (rester dans la matière, descente en rampe)',
    'link_previous': 'Lier au parcours précédent : seulement la matière laissée par les opérations d\'avant (gamme)',
    'rest_previous': 'Seulement le reste : ce que les poches d\'avant n\'ont pas vidé (leur outil et leur surépaisseur XY '
                     'comptés ; rien n\'est repassé)',
    'ramp_helix': 'Poche : rampe en hélice, rayon (mm, 0 : le long du contour)',
    'thread': 'Filetage', 'thread_left': 'Filet à gauche', 'pitch': 'Pas (mm, 0 = pas ISO)',
    'thread_external': 'Filetage extérieur (vis : la fraise tourne autour)',
    'thread_start_angle': 'Angle de départ (°, depuis OX)', 'thread_lead': 'Entrée et sortie',
    'thread_lead_dist': "Distance d'entrée / sortie (mm, filetage extérieur)",
    'hole_diameter': 'Ø du trou (mm, 0 = celui du cercle)',
    'extension': 'Débordement (mm)', 'face_angle': 'Angle des passes (°)', 'face_direction': 'Sens des passes',
    'prism_hollow': 'En creux (sinon en relief)', 'prism_lateral': 'Passes latérales',
    'instruction': 'Instruction', 'params': 'Réglages de l\'instruction',
    'finish_skip_frame': 'Finition : pas de passe sur le cadre (gravure en relief)',
    'finish_shut_levels': 'Finition à toutes les cotes là où l’ébauche n’a pas ouvert la matière (zone étroite, '
                          'coin aigu)',
    'common_line': 'Découpe sur ligne commune (bord partagé de pièces voisines coupé une fois)',
    'small_first': "Petites pièces d'abord (sinon au plus proche)",
    'small_first_by': 'Petites pièces selon',
    'order_mode': 'Tri des contours',
    'holes_order': 'Contours intérieurs',
    'raster_dir': 'Sens des passes',
    'scan_mode': 'Balayage', 'raster_angle': 'Angle des passes (°)',
    'raster_turn': 'Passe croisée, tournée de (°, 0 : aucune)', 'spiral_outward': 'De l’intérieur vers l’extérieur',
    'parallel_slices': 'Tranches parallèles au profil (0 : par cotes de Z)',
    'follow_profile': 'Suivre le profil 3D (sinon l’outil remonte au-dessus de ce qui est usiné)',
    'vcarve_max_steps': 'Nombre de passes limité (depuis le bord, 0 : toutes)',
    'vcarve_step': 'Passe en Z de la gravure (mm, 0 : en une fois)',
    'vcarve_walls': 'Passes sur les flancs avant le fond (sans : comme TypeEdit)',
    'vcarve_finish': 'Passe de finition : la surépaisseur XY usinée à l’avance de finition',
    'vcarve_offset': 'Décalage XY du contour (mm, + vers l\'intérieur)',
    'contour_ref': 'Outil conique : contour respecté', 'trace_mode': 'Mode de tracé',
    'knife_mode': 'Type de découpe', 'knife_angle': 'Angle latéral minimum (°)',
    'knife_angle_max': 'Angle latéral maximum (°)', 'loop_min_side': 'Longueur min. des côtés (mm)',
    'loop_length': 'Distance entrée/sortie de boucle (mm)', 'loop_radius': 'Rayon de boucle (mm)',
    'loop_check': 'Vérifier les intersections (boucles hors matière et hors dessin)',
    'corner_loops': 'Ajouter des boucles aux angles extérieurs',
    'chain_cut': "Découpe en chaîne (d'une pièce à l'autre sans relever l'outil)",
    'fill_order': 'Ordre du remplissage', 'fill_dx': 'Zones : largeur (mm)', 'fill_dy': 'Zones : hauteur (mm)',
    'tab_shape': 'Forme des pontets',
    'hatch_auto': 'Orientation automatique (lignes dans la longueur de chaque forme)',
    'leave_uncut': 'Matière restante en fin de contour (mm, 0 : coupé en entier)',
    'trochoidal': 'Trochoïdal (avance en boucles, rainure plus large que l\'outil)',
    'troch_width': 'Trochoïdal : largeur de rainure (mm, 0 : 1,5 × Ø)',
    'troch_step': 'Trochoïdal : avance par boucle (mm, 0 : 10 % du Ø)',
    'sweep_contour_stock': "Surépaisseur du cassé d'angle (mm, -1 : celle des hachures)",
    'pocket_spiral': 'En spirale (passes concentriques sans plongée entre elles)',
    'corner_opt': "Optimisation des angles (reprendre la matière des angles aigus)",
    'corner_pull': "Tirés d'angle (l'outil conique remonte dans les angles rentrants)",
    'corner_pull_angle': 'Tirer les angles plus fermés que (°)',
    'corner_pull_z': 'Limite en Z du tiré, au-dessus de la matière (mm, 0 = à la surface)',
    'foot_pull': "Tiré d'angle au pied (angles saillants vifs en bas : poinçons)",
    'foot_pull_min': "Tiré au pied : angles d'au moins (°)", 'foot_pull_max': 'Tiré au pied : angles de moins de (°)',
    'corner_opt_angle': 'Angles plus fermés que (°)',
    'pocket_outside_in': "En partant de l'extérieur (sinon du centre vers le bord)",
    'loop_angle_min': 'Angle minimum des boucles (°)', 'loop_angle_max': 'Angle maximum des boucles (°)',
    'corner_round': 'Angles arrondis (mm, en plus de l\'outil)',
    'offset_add': 'Décalage supplémentaire (mm, négatif : vers la pièce)',
    'chamfer_width': 'Largeur du chanfrein (mm)',
    'emboss_edge': 'Largeur laissée au bord (mm)', 'emboss_width': 'Largeur maxi du profil (mm)',
    'emboss_start_angle': "Angle de départ du profil (°, depuis la verticale ; 0 : le plus raide que l'outil permet)",
    'emboss_end_angle': "Angle d'arrivée du profil (°, depuis l'horizontale)",
    'emboss_side': 'Côté du galbe', 'emboss_passes': 'Choix des passes',
    'vcarve_edges_only': "Finition : bords et tirés d'angle seulement (fond déjà vidé)",
    'finish_3d_only': "Finition 3D uniquement : les tirés d'angle et les parties étroites, sans le contour",
    'vcarve_mode': 'Gravure 2,5D',
    'pass_depths': 'Profondeurs des passes (mm, ex. « 0,6 0,5 0,4 » ; vide : passes égales)',
    'copies_x': 'Multicopie : colonnes', 'copies_y': 'Multicopie : rangées',
    'copies_dx': 'Multicopie : pas en X (mm, 0 : taille + écart)',
    'copies_dy': 'Multicopie : pas en Y (mm, 0 : taille + écart)', 'copies_gap': 'Multicopie : écart (mm)',
    'pocket_mode': 'Évidage', 'stepover_mm': 'Distance entre passes (mm)',
    'sweep_angle': 'Angle des passes (°)', 'sweep_angle_mode': 'Angle', 'sweep_direction': 'Sens des passes',
    'sweep_angle_incr': 'Rotation entre deux passes en X et Y (°)',
    'sweep_contour': 'Tour du contour (cassé d\'angle)',
    'sweep_texture': 'Texturing : fond en coups de gouge', 'tex_depth_min': 'Texturing : profondeur mini (mm)',
    'tex_depth_max': 'Texturing : profondeur maxi (mm)', 'tex_len_min': 'Texturing : longueur mini (mm)',
    'tex_len_max': 'Texturing : longueur maxi (mm)', 'tex_overlap': 'Texturing : chevauchement (%)',
    'tex_seed': 'Texturing : tirage',
    'resolution': 'Pas (relief, 2,5D, mm)', 'invert': 'Relief : blanc en creux',
    'model_path': 'Pièce 3D (STEP, STL, 3D XML ; vide : celle du dessin)', 'enabled': 'Active',
    'faces3d': 'Zone : faces choisies dans la vue 3D', 'contours3d': 'Zone : contours choisis dans la vue 3D',
    'slope_min': 'Pentes d\'au moins (°, 0 = toutes)', 'slope_max': 'Pentes d\'au plus (°, 90 = toutes)',
    'setup_face': 'Face vers l\'outil (prise)', 'body3d': 'Corps usiné (n°, −1 : toute la pièce)',
    'ref_tool_id': 'Outil passé avant (reste, gamme ; finition 2,5D : outil conique de la gravure)',
    'rough_mode': 'Ébauche (paliers en Z, surépaisseur et décalage en XY)',
    'stock_xy': 'Décalage en XY le long des flancs (ébauche, mm)', 'items': 'Objets choisis',
    'hatch_angle': 'Angle des lignes (gravure laser, °)',
    'hatch_step': 'Rotation à chaque passage (°)', 'hatch_cross': 'Lignes croisées (+90° au même passage)',
    'hatch_inset': 'Retrait du remplissage (mm)', 'laser_passes': 'Passages',
    'line_width': 'Épaisseur du trait (mm, passages parallèles)',
    'line_step': 'Écart entre ces passages (mm, 0 = 80 % du faisceau)',
    'lead_in': 'Entrée : rayon, longueur ou distance (mm, 0 = sans)', 'lead_out': 'Sortie : rayon, longueur ou distance (mm, 0 = sans)',
    'lead_mode': 'Forme de l\'entrée et de la sortie', 'lead_angle': 'Angle d\'entrée (°, linéaire)',
    'lead_out_angle': 'Angle de sortie (°, linéaire)', 'lead_pierce': 'Rayon de perçage (mm, 0 = sans contrôle)',
    'lead_transition': 'Rayon de transition de la goutte (mm, 0 = le rayon de perçage)',
    'start_policy': 'Départ des contours fermés',
    'wobble': 'Oscillation du faisceau', 'wobble_amplitude': 'Amplitude de l\'oscillation (mm)',
    'wobble_pitch': 'Pas de l\'oscillation (mm, avance par tour)',
    'wrap': 'Enroulement (pièce couchée, 3 axes)', 'wrap_radius': 'Rayon de la pièce (mm)',
    'wrap_origin': 'Génératrice du dessus, en travers de l\'axe (mm)',
    'wrap_model': 'Pièce STEP (projection parallèle)',
    'wrap_radius2': 'Cône : second rayon (mm)', 'wrap_length': 'Cône : écart entre les rayons, le long de l\'axe (mm)',
}
#: palette « Créer un parcours » (comme celle de TypeEdit) :
#: clé → (libellé, stratégie, réglages de l'opération, nature d'outil préférée)
PRESETS = {
    'trace': ('Tracé', 'gravure', {}, 'conique'),
    'percage': ('Perçage', 'percage', {'depth': 1.0}, 'foret'),
    'decoupe': ('Découpe', 'contour', {'side': 'exterieur', 'depth': 1.0}, 'fraise'),
    'gravure': ('Gravure', 'poche', {}, 'fraise'),
    'decoupe3d': ('Découpe 3D', 'decoupe3d', {'side': 'exterieur', 'depth': 0.5}, 'conique'),
    'gravure3d': ('Gravure 3D', 'vcarve', {'depth': 0.3}, 'conique'),
    'prismatique': ('Prismatique', 'prismatique', {'depth': 0.0}, 'conique'),
    'relief': ('Relief', 'relief', {'depth': 1.0}, 'boule'),
    'gamme_relief': ('Gamme relief', 'ebauche3d', {'depth': 0.0}, 'fraise'),
    'finition': ('Finition 3D', 'surface3d', {'depth': 1.0}, 'boule'),
    'finition25d': ('Finition 2,5D', 'finition25d', {'depth': 0.5, 'resolution': 0.05}, 'boule'),
    'gamme': ('Gamme', 'gamme', {'depth': 0.5}, 'conique'),
    'reste': ('Reste matière', 'reste', {'depth': 0.5}, 'fraise'),
    'laser': ('Laser', 'laser', {}, 'laser'),
    'laser_decoupe': ('Découpe laser', 'laser_decoupe', {'side': 'exterieur'}, 'laser'),
    'laser_gravure': ('Gravure laser', 'laser_gravure', {'resolution': 0.1}, 'laser'),
    'taraudage': ('Taraudage', 'taraudage', {'depth': 6.0}, 'fraise'),
    'percage_fraise': ('Perçage fraise', 'percage_fraise', {'depth': 3.0}, 'fraise'),
    'chanfrein': ('Ébavurage trous', 'chanfrein', {}, 'conique'),
    'surfacage': ('Surfaçage', 'surfacage', {'depth': 0.2}, 'fraise'),
    'instruction': ('Instruction', 'instruction', {}, 'fraise'),
    'texte_machine': ('Texte machine', 'texte_machine', {'depth': 0.25}, 'conique'),
}
#: parcours unifiés (question 27, réponse du 15/11) : 9 familles pour les 22 parcours de la palette.
#: clé → (libellé, libellé de la liste qui fait la différence, ((clé du parcours, son libellé dans la liste), …))
UNIFIED = {
    'tracer': ('Tracé', 'Procédé', (('trace', 'Usinage'), ('laser', 'Laser'))),
    'trous': ('Trous', 'Type de trou', (('percage', 'Perçage'), ('percage_fraise', 'Perçage à la fraise'),
                                         ('taraudage', 'Taraudage'), ('chanfrein', 'Ébavurage'))),
    'decouper': ('Découpe', 'Type de découpe', (('decoupe', 'Flanc droit'), ('decoupe3d', 'Flanc incliné (3D)'),
                                                ('laser_decoupe', 'Laser'))),
    'graver': ('Gravure', 'Fond', (('gravure', 'Plat'), ('gravure3d', 'En V'), ('prismatique', 'Prismatique'),
                                   ('laser_gravure', 'Laser'))),
    'reprise': ('Reprise', '', (('reste', ''),)),
    'relief3d': ('Relief 3D', 'Étape', (('relief', 'Relief'), ('gamme_relief', 'Gamme : ébauche et finition'),
                                        ('finition', 'Finition 3D'), ('finition25d', 'Finition 2,5D'))),
    'gamme_te': ('Gamme', '', (('gamme', ''),)),
    'surfacer': ('Surfaçage', '', (('surfacage', ''),)),
    'machine': ('Machine', 'Type', (('instruction', 'Instruction'), ('texte_machine', 'Texte machine'))),
}
#: réglages : la palette montre les familles (d'office) ; le dernier parcours pris dans chaque famille (JSON)
UNIFIED_KEY = 'fao/palette/unifiee'
UNIFIED_LAST = 'fao/palette/famille_dernier'


def unified(settings) -> bool:
    """La palette montre les parcours unifiés (9 familles) — d'office ; sinon les 22 parcours par dossiers."""
    return settings is None or settings.value(UNIFIED_KEY, True) not in (False, 'false', 0, '0')


def family_of(member: str) -> str:
    """La famille (clé de `UNIFIED`) du parcours `member` de la palette ; '' : aucune (parcours d'un plugin)."""
    return next((f for f, (_l, _w, members) in UNIFIED.items() if any(k == member for k, _t in members)), '')


from PySide6.QtCore import QEvent as _QEvent, QObject as _QObject  # noqa: E402 — pour `PopupOnly` seulement


class PopupOnly(_QObject):
    """Une liste qui ne change que par sa liste déroulée : fermée, ni les flèches ni les lettres ne choisissent
    (Espace, Entrée, F4 ou ↓ la déroulent). Pour la liste d'une famille, dont chaque changement ferme le
    formulaire : une touche de trop ne doit pas le faire."""

    def eventFilter(self, box, ev) -> bool:
        if ev.type() != _QEvent.Type.KeyPress or box.view().isVisible():
            return False
        if ev.key() in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab, Qt.Key.Key_Escape):
            return False
        if ev.key() in (Qt.Key.Key_Space, Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_F4, Qt.Key.Key_Down):
            box.showPopup()
        return True


#: outils créés quand la bibliothèque n'en a pas de la nature voulue
DEFAULT_TOOLS = {
    'conique': dict(name='Conique 30° pointe 0,1', kind='conique', diameter=3.175, angle=30.0, tip=0.1,
                    step_down=0.1),
    'fraise': dict(name='Fraise Ø1', kind='fraise', diameter=1.0, step_down=0.2),
    'foret': dict(name='Foret Ø1', kind='foret', diameter=1.0, step_down=0.5),
    'boule': dict(name='Fraise boule Ø1', kind='boule', diameter=1.0, step_down=0.2),
    'laser': dict(name='Laser', kind='laser', diameter=0.05, power=50.0, frequency=20.0, feed=1000.0,
                  spindle=0.0, cut_length=0.0),
}


#: natures d'opération dont le nouveau parcours propose l'outil conseillé — le plus gros qui atteint tous les
#: détails de la surface à vider : la poche. Ailleurs ce critère ne dit pas le bon outil (un perçage veut le foret
#: du trou, un détourage extérieur les creux du bord, un tracé suit le trait, un ébavurage un cône plus gros que le
#: trou) : l'outil d'office comme avant
PROPOSE_KINDS = frozenset({'poche'})


def proposes_tool(settings, preset: str) -> bool:
    """Mode expert et option « un nouveau parcours propose et vérifie l'outil conseillé » : le formulaire du parcours
    `preset` de la palette propose l'outil conseillé (demande du 14/11, 19 h 45) — pour une poche, sauf si les
    « Outils proposés par opération » en règlent un."""
    found = presets().get(preset or '')
    if found is None or found[1] not in PROPOSE_KINDS:
        return False
    from ..cam import toolprefs
    from . import modes
    from .options import value
    if settings is None:
        from .. import portable
        settings = portable.settings()
    if toolprefs.customized(found[1], toolprefs.load(settings)):
        return False
    return modes.current(settings) != 'simple' and bool(value(settings, 'fao/outil_propose'))


def presets() -> dict:
    """Boutons de la palette : ceux du cœur puis ceux des plugins."""
    from ..plugins import REGISTRY
    return {**PRESETS, **{k: v for k, v in REGISTRY.cam_presets.items() if k not in PRESETS}}


def template_note(name) -> str:
    """Le commentaire d'un modèle d'usinage (parcours préenregistré) : sa description (première ligne), sinon son nom
    sans dossier ; '' sans modèle."""
    if not name:
        return ''
    from ..cam import templates as TPL
    found = TPL.all_templates().get(name)
    tpl = found[1] if found is not None and isinstance(found[1], dict) else {}
    lines = str(tpl.get('description') or '').strip().splitlines()
    first = lines[0].strip() if lines else ''
    if first.startswith(('TypeEdit : ', 'Modèle de parcours TypeEdit')) or 'typeedit' in tpl:
        first = ''                                       # description faite à l'import TypeEdit : le nom, plutôt
    note = first or TPL.label_of(tpl) or str(name)
    return note if len(note) <= 80 else note[:79].rstrip() + '…'


def toolpath_title(kind: str, preset: str = '', note: str = '') -> str:
    """Titre du formulaire d'un parcours (demande du 16/11, 23 h 25) : « Parcours [type de parcours] » et, s'il vient
    d'un modèle, « - [commentaire du modèle] ». Le type : le bouton de la palette `preset` s'il fait cette stratégie,
    sinon le nom de la stratégie."""
    pre = presets().get(preset) if preset else None
    kind_text = tr(pre[0]) if pre is not None and pre[1] == kind else tr(model.op_kinds().get(kind, kind))
    title = tr('Parcours {0}').format(kind_text)
    return f'{title} - {note}' if note else title
SIDES = {'exterieur': 'Extérieur', 'interieur': 'Intérieur', 'sur': 'Sur le trait'}
#: champs à choix (listes)
FIELD_CHOICES = {
    'feed_frame': {'ebauche': 'Ébauche', 'finition': 'Finition'},
    'setup_face': {'': 'Comme le dessin', '+Z': 'Dessus (comme lue)', '-Z': 'Dessous (pièce retournée)',
                   '+X': 'Côté +X', '-X': 'Côté −X', '+Y': 'Côté +Y (arrière)', '-Y': 'Côté −Y (avant)'},
    'tab_shape': {'droit': 'Droits (flancs verticaux)', 'incurve': 'Incurvés (montée et descente en douceur)'},
    'start_policy': {'proche': 'Au plus près (moins de déplacements)', 'dessin': 'Point de départ du dessin'},
    'emboss_side': {'dedans': 'Dans les formes (en creux)', 'autour': 'Autour des formes (elles restent en relief)'},
    'emboss_passes': {'standard': 'Standard', 'intaille': 'Intaille', 'les_deux': 'Standard + intaille'},
    'lead_mode': {'arc': 'Circulaire', 'ligne': 'Linéaire', 'percage': 'Perçage en goutte'},
    'pass_order': {'poche': 'Poche par poche (chacune jusqu\'au fond)',
                   'global': 'Global (chaque profondeur sur toutes les poches)'},
    'fill_order': {'global': 'Global (ligne à ligne sur tout)', 'forme': 'Forme par forme',
                   'zones': 'Par zones (carreaux)'},
    'drill_points': {'cercles': 'Centres des cercles et marqueurs', 'marqueurs': 'Marqueurs seulement',
                     'depart': 'Point de départ des traits ouverts', 'arrivee': "Point d'arrivée des traits ouverts",
                     'depart_arrivee': 'Départ et arrivée (contours fermés : départ)',
                     'centres': 'Centre des contours fermés (braille)'},
    'thread_lead': {'droit': 'Tout droit (radiales)', 'arc': 'En arc de cercle (tangentes)'},
    'small_first_by': {'aire': 'Aire', 'perimetre': 'Périmètre', 'cercle': 'Cercle inscrit (pièces étroites)'},
    'order_mode': {'auto': 'Automatique (le plus court)', 'dessin': 'Manuel (ordre du dessin)'},
    'holes_order': {'element': 'Élément par élément', 'tous': 'Tous les intérieurs, puis les extérieurs'},
    'raster_dir': {'x': 'Selon X', 'y': 'Selon Y', 'xy': 'Selon X, finition croisée selon Y'},
    'scan_mode': {'passes': 'Passes selon X ou Y', 'angle': 'Suivant un angle', 'spirale': 'En spirale'},
    'drill_mode': {'debourrage': 'En passes, remontée au dégagement',
                   'brise_copeau': 'En passes, petit recul (brise-copeau)', 'simple': 'Une seule passe'},
    'knife_mode': {'trace': 'Tracé (suit le contour)', 'asservi': 'Couteau asservi (remonte aux angles)',
                   'flottant': 'Couteau flottant (pivote aux angles, déport compensé)',
                   'boucles': 'Couteau flottant à boucles (boucle hors matière aux angles)'},
    'vcarve_mode': {'passes': 'Passes décalées (fond vidé)', 'axe': 'Ligne médiane (intaille optimisée, une passe)',
                    'axe_ar': 'Ligne médiane en aller-retour (intaille standard : un flanc à l\'aller, l\'autre au retour)',
                    'contour': 'Contour 2D sans remontées d\'angle, puis vidage'},
    'trace_mode': {'simple': 'Aller simple', 'ar': 'Aller-retour', 'dernier': 'Aller-retour sur la dernière tranche',
                   'meme_sens': 'Toujours dans le même sens (traits ouverts)'},
    'contour_ref': {'surface': 'En surface (bord du dessin en haut)', 'fond': 'Au fond (pointe sur le contour)'},
    'pocket_mode': {'concentrique': 'Passes concentriques', 'balayage': 'Balayage (passes parallèles)'},
    'sweep_angle_mode': {'fixe': 'Angle de départ', 'optimise': 'Optimisé (le long de la forme)',
                         'croise': 'X et Y (passes croisées)'},
    'sweep_direction': {'aller_retour': 'Aller-retour', 'opposition': 'En opposition', 'avalant': 'En avalant'},
    'tab_mode': {'pont': 'Ponts (une hauteur reste)', 'pointille': 'Pointillés (parties non usinées, micro-attaches)',
                 'nettoyer': 'Nettoyer les ponts (seuls eux sont usinés)'},
    'sweep_contour': {'sans': 'Sans', 'avant': 'Avant le balayage', 'apres': 'Après le balayage'},
    'face_direction': {'aller_retour': 'Aller-retour', 'avalant': 'Tout en avalant', 'opposition': 'Tout en opposition'},
}
#: valeur 0 : celle de l'outil choisi — le champ la montre, avec son unité (demande du 14/11)
TOOL_DEFAULT = ('step_down', 'feed', 'plunge', 'spindle', 'finish_feed')
#: unité de la valeur de l'outil montrée dans ces champs
TOOL_UNITS = {'feed': 'mm/min', 'plunge': 'mm/min', 'spindle': 'tr/min', 'step_down': 'mm', 'finish_feed': 'mm/min'}
#: section Vitesses d'une opération : ses deux cadres (clé, titre, champs) — demande du 14/11, 19 h 45
FEED_FRAMES = (('ebauche', 'Ébauche', ('feed', 'plunge', 'spindle')), ('finition', 'Finition', ('finish_feed',)))
#: champs à 0 qui prennent une valeur tirée de l'outil (la distance entre passes : une part de son diamètre)
ZERO_IS_TOOL = TOOL_DEFAULT + ('stepover_mm',)
#: disposition des cases gardée avant que « Profondeurs » passe au-dessus d'« Entrées et liaisons » : échangées une fois
SWAPPED_KEY = 'fao/cases_operation2_profondeurs'


def _num(v: float) -> str:
    """Un nombre court (0,3 ; 420,5 ; 18000), au séparateur décimal des champs (la langue du poste, comme Qt)."""
    return f'{float(v):.3f}'.rstrip('0').rstrip('.').replace('.', QLocale().decimalPoint())


def tool_value_text(name: str, tool) -> str:
    """Ce que montre le champ `name` à 0 : la valeur prise de l'outil `tool` et son unité, rien d'autre (demande du
    15/11 : pas de « celle de l'outil » dans le champ) ; « — » si l'outil ne la donne pas (aucun outil choisi, valeur
    pas réglée dans l'outil) ; « auto » pour une distance entre passes que la stratégie calcule. L'explication :
    `tool_value_tip`, dans la bulle du champ."""
    if tool is None:
        return '—'
    if name == 'stepover_mm':
        frac = float(getattr(tool, 'stepover', 0.0) or 0.0)
        if getattr(tool, 'kind', 'fraise') != 'fraise' or frac <= 0 or not tool.diameter:
            return tr('auto')
        return '≈ {0} mm'.format(_num(frac * float(tool.diameter)))
    value = float(getattr(tool, name, 0.0) or 0.0)
    if name == 'finish_feed' and value <= 0 and float(getattr(tool, 'feed', 0.0) or 0.0) > 0:
        return '{0} mm/min'.format(_num(float(tool.feed)))       # l'outil n'a pas d'avance de finition : d'ébauche
    if value <= 0:
        return '—'
    return '{0} {1}'.format(_num(value), tr(TOOL_UNITS.get(name, '')))


def tool_value_tip(name: str, tool) -> str:
    """La bulle d'un champ à 0 : d'où vient sa valeur — celle de l'outil `tool`, avec son unité ; sans outil choisi,
    qu'il faut le choisir ; une valeur que l'outil n'a pas, qu'elle n'y est pas réglée. La distance entre passes
    n'est chiffrée que pour une fraise droite qui a la sienne : pour les autres outils, chaque stratégie la calcule
    à sa façon (largeur gravée d'un outil conique, rayon d'une boule…)."""
    if tool is None:
        return tr('d’après l’outil, à choisir')
    if name == 'stepover_mm':
        frac = float(getattr(tool, 'stepover', 0.0) or 0.0)
        if getattr(tool, 'kind', 'fraise') != 'fraise' or frac <= 0 or not tool.diameter:
            return tr('d’après l’outil et le parcours')
        return tr('≈ {0} mm ({1} % du Ø de l’outil)').format(_num(frac * float(tool.diameter)), _num(100.0 * frac))
    value = float(getattr(tool, name, 0.0) or 0.0)
    if name == 'finish_feed' and value <= 0 and float(getattr(tool, 'feed', 0.0) or 0.0) > 0:
        # l'outil n'a pas d'avance de finition : celle d'ébauche
        return tr('{0} mm/min (avance de l’outil)').format(_num(float(tool.feed)))
    if value <= 0:
        return tr('non réglée dans l’outil')
    return tr('{0} {1} (outil)').format(_num(value), tr(TOOL_UNITS.get(name, '')))


def rename_kept_cases(settings) -> bool:
    """Les sections renommées (`RENAMED_CASES`) prennent leur nouveau nom dans la disposition gardée et dans les cases
    pliées : elles gardent leur place. Rend vrai si quelque chose a changé."""
    if settings is None:
        return False
    names = dict(RENAMED_CASES)
    done = False
    for key in (CASES_KEYS[True], CASES_KEYS[True] + '_pliees'):
        raw = settings.value(key, '')
        if not isinstance(raw, str) or not any(old in raw for old in names):
            continue
        try:
            got = json.loads(raw)
        except ValueError:
            continue
        if not isinstance(got, list):
            continue
        new = [[names.get(k, k) if isinstance(k, str) else k for k in c] if isinstance(c, list) else
               names.get(c, c) if isinstance(c, str) else c for c in got]
        if new != got:
            settings.setValue(key, json.dumps(new, ensure_ascii=False))
            done = True
    return done


def swap_kept_cases(settings) -> bool:
    """Une disposition des cases gardée d'avant (demande du 14/11) : « Profondeurs » et « Entrées et liaisons » y
    échangent leur place, une fois. Rend vrai si elle a changé."""
    if settings is None or str(settings.value(SWAPPED_KEY, '')).lower() in ('1', 'true'):
        return False
    settings.setValue(SWAPPED_KEY, True)
    raw = settings.value(CASES_KEYS[True], '')
    try:
        cols = json.loads(raw) if isinstance(raw, str) and raw else None
    except ValueError:
        return False
    if not isinstance(cols, list) or not all(isinstance(c, list) for c in cols):
        return False
    at = {k: (ci, ii) for ci, c in enumerate(cols) for ii, k in enumerate(c)}
    a, b = at.get('Profondeurs'), at.get('Entrées et liaisons')
    if a is None or b is None or a < b:                  # déjà dans le bon ordre (plus haut, ou à gauche)
        return False
    cols[a[0]][a[1]], cols[b[0]][b[1]] = 'Entrées et liaisons', 'Profondeurs'
    settings.setValue(CASES_KEYS[True], json.dumps(cols, ensure_ascii=False))
    return True
#: couleurs des parcours affichés
PATH_COLORS = ['#e8590c', '#1c7ed6', '#2f9e44', '#ae3ec9', '#f08c00', '#0b7285', '#c2255c', '#5c940d']
#: couleurs des parcours pour les daltoniens (palette d'Okabe et Ito : distinctes sans le rouge / vert)
PATH_COLORS_CB = ['#e69f00', '#0072b2', '#009e73', '#cc79a7', '#56b4e9', '#d55e00', '#f0e442', '#000000']
#: réglage « couleurs pour daltoniens » (vue/daltonien), lu une fois par affichage
COLOUR_BLIND = {'on': False}


def path_colors() -> list:
    """Couleurs des parcours : la palette pour daltoniens si elle est choisie."""
    return PATH_COLORS_CB if COLOUR_BLIND['on'] else PATH_COLORS


#: formulaire d'opération : sections (dans l'ordre) et leurs champs
OP_SECTIONS = [
    ('Outil', ('tool_id', 'ref_tool_id', 'ramp')),   # ramp : bouton « Plongée angulaire » et son angle, sous l'outil
    ('Opération', ('name', 'kind', 'instruction', 'params', 'link_previous', 'rest_previous', 'enabled')),
    ('Où usiner', ('sources', 'items', 'side', 'climb')),     # sources, items : repliés en fin de formulaire
    ('Profondeurs', ('z_start', 'depth', 'step_down', 'pass_depths', 'pass_order', 'link_passes', 'stock', 'vcarve_finish', 'stock_z', 'finish',
                     'finish_skip_frame', 'finish_shut_levels',
                     'contour_ref', 'trace_mode', 'knife_mode', 'knife_angle', 'knife_angle_max',
                     'chamfer_width', 'prism_hollow', 'prism_lateral',
                     'vcarve_edges_only', 'finish_3d_only', 'vcarve_mode', 'vcarve_offset', 'vcarve_max_steps', 'vcarve_step', 'vcarve_walls', 'emboss_edge', 'emboss_width', 'emboss_start_angle',
                     'emboss_end_angle', 'emboss_side', 'emboss_passes')),
    ('Entrées et liaisons', ('ramp_max', 'ramp_helix', 'start_policy', 'lead_mode', 'lead_in', 'lead_out', 'lead_angle',
                             'lead_out_angle', 'lead_pierce', 'lead_transition', 'leave_uncut', 'safe_z',
                             'safe_z_faced', 'clear_z')),
    ('Vitesses', ('feed', 'plunge', 'spindle', 'finish_feed', 'feed_frame')),
    ('Évidage', ('pocket_mode', 'pocket_spiral', 'pocket_outside_in', 'corner_opt', 'corner_opt_angle', 'stepover_mm', 'sweep_angle', 'sweep_angle_mode', 'sweep_angle_incr', 'sweep_direction', 'sweep_by_zone',
                 'sweep_contour', 'sweep_contour_stock', 'sweep_texture', 'tex_depth_min', 'tex_depth_max', 'tex_len_min', 'tex_len_max',
                 'tex_overlap', 'tex_seed')),
    ('Avancé', ('peck', 'drill_points', 'drill_mode', 'drill_feed_retract', 'thread', 'thread_left',
                     'thread_external', 'thread_start_angle', 'thread_lead', 'thread_lead_dist', 'pitch', 'hole_diameter', 'extension', 'face_angle', 'face_direction',
                     'tabs', 'tab_spacing', 'tab_gap', 'tab_max', 'tab_mode', 'tab_width', 'tab_shape',
                     'tab_height', 'common_line', 'chain_cut', 'trochoidal', 'troch_width', 'troch_step',
                     'small_first', 'small_first_by', 'order_mode', 'holes_order',
                     'raster_dir', 'scan_mode', 'raster_angle', 'raster_turn', 'spiral_outward', 'parallel_slices',
                     'follow_profile', 'rough_mode', 'stock_xy', 'resolution', 'invert', 'model_path', 'faces3d',
                     'contours3d', 'slope_min', 'slope_max', 'setup_face', 'body3d')),
    ('Laser', ('laser_passes', 'line_width', 'line_step', 'hatch_angle', 'hatch_step', 'hatch_cross', 'hatch_inset',
               'fill_order', 'fill_dx', 'fill_dy', 'hatch_auto', 'wobble',
               'wobble_amplitude', 'wobble_pitch')),
    ('Angles', ('corner_pull', 'corner_pull_angle', 'corner_pull_z', 'foot_pull', 'foot_pull_min', 'foot_pull_max')),
    ('Boucles', ('corner_loops', 'loop_angle_min', 'loop_angle_max', 'loop_min_side', 'loop_length', 'loop_radius',
                 'loop_check', 'corner_round', 'offset_add')),
    ('Multicopie', ('copies_x', 'copies_y', 'copies_dx', 'copies_dy', 'copies_gap')),
    ('Enroulement', ('wrap', 'wrap_radius', 'wrap_origin', 'wrap_radius2', 'wrap_length', 'wrap_model')),
]
#: formulaire d'opération : la disposition d'origine des sections, en deux colonnes (demandes du 14/11) — en haut
#: l'outil et les vitesses ; à gauche dessous l'opération, les profondeurs puis « Avancé » (ex-« Particulier »), à
#: droite les entrées et liaisons ; puis le reste ; Multicopie, Enroulement et Autres tout en bas
OP_LAYOUT = [['Outil', 'Opération', 'Profondeurs', 'Avancé', 'Où usiner', 'Évidage', 'Angles', 'Multicopie', 'Autres'],
             ['Vitesses', 'Entrées et liaisons', 'Laser', 'Boucles', 'Enroulement']]
#: sections renommées : (ancien titre, nouveau) — dans les dispositions gardées aussi
RENAMED_CASES = (('Particulier', 'Avancé'),)
#: sections montrées en mode expert seulement (en mode simple : si l'opération s'en sert)
EXPERT_SECTIONS = ('Multicopie', 'Enroulement', 'Autres')
#: formulaire d'outil
TOOL_SECTIONS = [
    ('Outil', ('name', 'kind', 'number', 'ref', 'vendor', 'notes')),
    ('Géométrie', ('diameter', 'tip', 'angle', 'flutes', 'cut_length', 'stickout', 'holder_diameter')),
    ('Coupe', ('spindle', 'feed', 'finish_feed', 'plunge', 'ramp_feed', 'step_down', 'stepover')),
    ('Laser', ('power', 'frequency')),
]
#: champs propres à certaines stratégies : masqués pour les autres
KIND_FIELDS = {
    'percage': {'peck', 'drill_points', 'drill_mode', 'drill_feed_retract'},
    'gravure': {'start_policy', 'trace_mode', 'link_passes', 'tabs', 'tab_spacing', 'tab_gap', 'tab_max', 'tab_mode', 'tab_width', 'tab_shape', 'tab_height'},
    'vinyle': {'knife_mode', 'knife_angle', 'knife_angle_max', 'loop_min_side', 'loop_length',
               'loop_radius', 'loop_check'},
    'chanfrein_bord': {'side', 'climb', 'chamfer_width'},
    'fer_dorer': {'climb', 'resolution', 'emboss_edge', 'emboss_width', 'emboss_start_angle', 'emboss_end_angle',
                  'emboss_side', 'emboss_passes',
                  'contour_ref'},
    'contour': {'start_policy', 'pass_order', 'link_passes', 'link_previous',
                'side', 'climb', 'stock', 'stock_z', 'finish', 'finish_skip_frame', 'tabs', 'tab_spacing', 'tab_gap', 'tab_max', 'tab_mode', 'tab_width',
                'tab_shape',
                'tab_height', 'common_line', 'chain_cut', 'small_first', 'small_first_by', 'holes_order', 'lead_in', 'lead_out', 'lead_mode', 'lead_angle', 'lead_out_angle', 'lead_pierce', 'lead_transition',
                'contour_ref', 'trochoidal', 'troch_width', 'troch_step', 'leave_uncut',
                'corner_loops',
                'loop_angle_min', 'loop_angle_max', 'loop_min_side', 'loop_length', 'loop_radius', 'loop_check',
                'corner_round', 'offset_add'},
    'poche': {'pass_order', 'link_passes', 'link_previous', 'rest_previous',
              'climb', 'stock', 'stock_z', 'finish', 'finish_skip_frame', 'finish_shut_levels', 'contour_ref',
              'pocket_mode',
              'pocket_spiral',
              'ramp_helix',
              'pocket_outside_in', 'corner_opt', 'corner_opt_angle', 'stepover_mm', 'sweep_angle',
              'sweep_angle_mode', 'sweep_angle_incr', 'sweep_direction', 'sweep_by_zone', 'sweep_contour', 'sweep_contour_stock', 'sweep_texture',
              'tex_depth_min',
              'tex_depth_max', 'tex_len_min', 'tex_len_max', 'tex_overlap', 'tex_seed'},
    'reste': {'ref_tool_id', 'climb', 'stock', 'stock_z', 'link_previous', 'stepover_mm'},
    'gamme': {'ref_tool_id'},
    'decoupe3d': {'side', 'climb', 'stock', 'corner_pull', 'corner_pull_angle', 'corner_pull_z', 'foot_pull', 'foot_pull_min',
                  'foot_pull_max', 'link_previous'},
    'vcarve': {'stock', 'vcarve_finish', 'resolution', 'vcarve_edges_only', 'finish_3d_only', 'finish_skip_frame', 'vcarve_mode', 'vcarve_offset', 'vcarve_max_steps',
               'vcarve_step', 'vcarve_walls', 'link_previous', 'stepover_mm', 'pocket_outside_in', 'corner_pull_angle', 'ramp', 'ramp_angle'},
    'prismatique': {'climb', 'extension', 'prism_hollow', 'prism_lateral'},
    'relief': {'resolution', 'invert', 'raster_dir', 'stock', 'scan_mode', 'raster_angle', 'raster_turn',
               'spiral_outward', 'parallel_slices', 'follow_profile', 'climb'},
    'surface3d': {'model_path', 'resolution', 'raster_dir', 'stock', 'faces3d', 'contours3d', 'extension',
                  'stepover_mm', 'slope_min', 'slope_max', 'setup_face', 'body3d', 'scan_mode', 'raster_angle',
                  'raster_turn', 'spiral_outward', 'parallel_slices', 'follow_profile', 'climb'},
    'ebauche3d': {'model_path', 'resolution', 'stock', 'faces3d', 'contours3d', 'extension', 'stepover_mm',
                  'climb', 'setup_face', 'body3d'},
    'reprise3d': {'model_path', 'resolution', 'stock', 'faces3d', 'contours3d', 'extension', 'stepover_mm',
                  'raster_dir', 'ref_tool_id', 'setup_face', 'body3d'},
    'niveaux3d': {'model_path', 'resolution', 'stock', 'faces3d', 'contours3d', 'extension', 'slope_min',
                  'slope_max', 'setup_face', 'body3d'},
    'finition25d': {'ref_tool_id', 'resolution', 'raster_dir', 'rough_mode', 'stock', 'stock_xy'},
    'laser': {'start_policy', 'laser_passes', 'wobble', 'wobble_amplitude', 'wobble_pitch', 'line_width', 'line_step'},
    'laser_decoupe': {'start_policy', 'side', 'laser_passes', 'wobble', 'wobble_amplitude', 'wobble_pitch', 'holes_order', 'lead_in', 'lead_out', 'lead_mode', 'lead_angle', 'lead_out_angle', 'lead_pierce', 'lead_transition',
                      'tabs', 'tab_spacing', 'tab_gap', 'tab_max', 'tab_width',
                      'corner_loops', 'loop_angle_min', 'loop_angle_max', 'loop_min_side', 'loop_length',
                      'loop_radius', 'loop_check', 'corner_round', 'offset_add'},
    'laser_gravure': {'hatch_angle', 'resolution', 'finish', 'hatch_step', 'hatch_cross', 'hatch_inset',
                      'laser_passes', 'wobble', 'wobble_amplitude', 'wobble_pitch', 'fill_order', 'fill_dx',
                      'fill_dy', 'hatch_auto'},
    'taraudage': {'thread', 'thread_left', 'pitch', 'climb', 'thread_external', 'thread_start_angle', 'thread_lead',
                  'thread_lead_dist'},
    'percage_fraise': {'hole_diameter', 'climb'},
    'chanfrein': {'stock'},
    'surfacage': {'extension', 'face_angle', 'face_direction'},
    'instruction': {'instruction', 'params'},
    'texte_machine': {'params'},
}
OPTIONAL = set().union(*KIND_FIELDS.values())
#: la surépaisseur n'a pas le même sens selon le parcours : son libellé le dit (les autres : celui de LABELS)
STOCK_XY = 'Surépaisseur XY : le long des flancs (mm)'
STOCK_3D = 'Surépaisseur 3D : en XY et en Z (mm)'
STOCK_LABELS = {
    **{k: STOCK_XY for k in ('contour', 'poche', 'reste', 'decoupe3d', 'vcarve')},
    **{k: STOCK_3D for k in ('relief', 'surface3d', 'ebauche3d', 'reprise3d', 'niveaux3d')},
    'finition25d': 'Surépaisseur 3D de l’ébauche (mm, le décalage en XY s’y ajoute)',
    'chanfrein': 'Largeur du chanfrein (mm, 0 : 0,2 mm)',
}


def field_label(name: str, kind: str = '') -> str:
    """Libellé (en français) du champ `name` dans le formulaire d'un parcours `kind`."""
    if name == 'stock' and kind in STOCK_LABELS:
        return STOCK_LABELS[kind]
    return LABELS.get(name, name)
#: la plongée angulaire (rampe) : montrée pour les stratégies dont le parcours entre en rampe (`op.ramp` lu par
#: `_gravure`, `_edge_chamfer`, `_contour`, `_pocket`, `_rest`, `_decoupe3d`, `_vcarve`, `zlevel_rough`, la gamme),
#: et pour celles des plugins
RAMP_FIELDS = ('ramp', 'ramp_angle', 'ramp_max')
RAMP_KINDS = frozenset({'gravure', 'chanfrein_bord', 'contour', 'poche', 'reste', 'decoupe3d', 'vcarve', 'ebauche3d',
                        'gamme'})


def ramp_icon(on: bool):
    """Icône du bouton « Plongée angulaire » : la descente en biais (enfoncé) ou droite (relâché) sous la surface."""
    from PySide6.QtGui import QIcon, QPixmap
    from .icons import _inks
    ink, acc = _inks()
    pm = QPixmap(64, 64)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(ink), 4)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    p.drawLine(QPointF(4, 18), QPointF(60, 18))                       # surface de la pièce
    pen = QPen(QColor(acc) if on else QColor(ink), 6)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    if on:
        p.drawLine(QPointF(10, 18), QPointF(48, 52))                  # en biais
        tip = QPointF(48, 52)
    else:
        p.drawLine(QPointF(32, 4), QPointF(32, 54))                   # droit
        tip = QPointF(32, 54)
    p.setBrush(QColor(acc) if on else QColor(ink))
    p.drawEllipse(tip, 5, 5)
    p.end()
    return QIcon(pm)


class ToggleBox(QCheckBox):
    """Case à cocher dessinée en bouton poussoir à icône : enfoncé quand elle est cochée, un clic n'importe où la
    bascule. Reste une QCheckBox pour le formulaire (lecture, modèles, schéma)."""

    def __init__(self, text: str, icons=None, parent=None):
        super().__init__(text, parent)
        self._icons = icons
        from PySide6.QtCore import QSize
        self.setIconSize(QSize(22, 22))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggled.connect(lambda _on: self._sync())
        self._sync()

    def _sync(self) -> None:
        if self._icons is not None:
            self.setIcon(self._icons(self.isChecked()))
        self.update()

    def _option(self):
        from PySide6.QtWidgets import QStyleOptionButton
        opt = QStyleOptionButton()
        opt.initFrom(self)
        opt.text = self.text()
        opt.icon = self.icon()
        opt.iconSize = self.iconSize()
        return opt

    def sizeHint(self):                                            # noqa: N802 — API Qt
        from PySide6.QtCore import QSize
        fm = self.fontMetrics()
        inner = QSize(fm.horizontalAdvance(self.text()) + self.iconSize().width() + 8,
                      max(self.iconSize().height(), fm.height()))
        return self.style().sizeFromContents(QStyle.ContentsType.CT_PushButton, self._option(), inner, self)

    def minimumSizeHint(self):                                     # noqa: N802 — API Qt
        return self.sizeHint()

    def hitButton(self, pos) -> bool:                              # noqa: N802 — API Qt
        return self.rect().contains(pos)

    def paintEvent(self, e) -> None:                               # noqa: N802 — API Qt
        from PySide6.QtWidgets import QStylePainter
        p = QStylePainter(self)
        opt = self._option()
        if self.isChecked() or self.isDown():
            opt.state |= QStyle.StateFlag.State_On | QStyle.StateFlag.State_Sunken
        else:
            opt.state |= QStyle.StateFlag.State_Off | QStyle.StateFlag.State_Raised
        p.drawControl(QStyle.ControlElement.CE_PushButton, opt)
#: une instruction machine n'a ni outil ni parcours : ses seuls champs
INSTRUCTION_FIELDS = {'name', 'kind', 'enabled', 'instruction', 'params'}


class OpIllustration(QWidget):
    """Schéma de l'opération : vue de dessus (la forme et le parcours selon
    la stratégie et le côté) et coupe (profondeur, passes, rampe,
    finition)."""

    def __init__(self, dialog):
        super().__init__(dialog)
        self.d = dialog
        self.setMinimumSize(260, 330)

    def value(self, name, default=None):
        w = self.d.widgets.get(name)
        if w is None:
            return default
        if isinstance(w, QComboBox):
            return w.currentData()
        if isinstance(w, QCheckBox):
            return w.isChecked()
        if isinstance(w, (QSpinBox, QDoubleSpinBox)):
            return w.value()
        return default

    def ramp_angle(self) -> float:
        """Angle de rampe du formulaire (°), comme le calcul : 0 → 5°, borné à [0,5 ; 89]."""
        from ..cam.strategies import ramp_angle_of

        class _Op:
            ramp_angle = float(self.value('ramp_angle', 0.0) or 0.0)
        return ramp_angle_of(_Op)

    def ramp_segments(self, x0: float, x1: float, y0: float, scale: float, dz: float) -> list:
        """Rampe d'une passe (descente `dz` mm) à son vrai angle, même échelle
        en X et en Z (`scale` px/mm), en zigzag entre `x0` et `x1` quand elle
        est plus longue : [(xa, ya, xb, yb)] en pixels."""
        a = math.radians(self.ramp_angle())
        drop = dz * scale
        run = drop / math.tan(a)
        avail = max(10.0, x1 - x0)
        out, x, y, left, sign = [], x0, y0, run, 1.0
        while left > 1e-6 and len(out) < 60:
            seg = min(left, avail)
            xb, yb = x + sign * seg, y + drop * seg / run
            out.append((x, y, xb, yb))
            x, y, left, sign = xb, yb, left - seg, -sign
        return out

    def paintEvent(self, _ev) -> None:
        from PySide6.QtGui import QPainterPath
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()
        p.fillRect(0, 0, W, H, QColor('#f8f9fb'))
        kind = self.value('kind', 'gravure') or 'gravure'
        side = self.value('side', 'exterieur')
        ramp = bool(self.value('ramp', False))
        depth = abs(float(self.value('depth', 0.0) or 0.0))
        step = float(self.value('step_down', 0.0) or 0.0)
        finish = bool(self.value('finish', False))
        skip = bool(self.value('finish_skip_frame', False))
        title = QColor('#495057')
        p.setPen(title)
        p.drawText(QRectF(8, 4, W - 16, 18), Qt.AlignmentFlag.AlignLeft,
                   tr(model.op_kinds().get(kind, kind)))
        # --- vue de dessus : un cadre et une lettre (rectangle) ------------------------
        top = QRectF(16, 26, W - 32, H * 0.48)
        frame = top.adjusted(10, 10, -10, -10)
        letter = QRectF(frame.center().x() - frame.width() * 0.16, frame.center().y() - frame.height() * 0.22,
                        frame.width() * 0.32, frame.height() * 0.44)
        ink = QPen(QColor('#1c3d6e'), 1.6)
        p.setPen(ink)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(frame)
        p.drawRect(letter)
        tool = QPen(QColor('#e8590c'), 1.4, Qt.PenStyle.DashLine)
        p.setPen(tool)
        off = 7.0
        if kind in ('gravure', 'laser', 'vcarve', 'decoupe3d') and not (kind == 'decoupe3d' and side != 'sur'):
            p.drawRect(frame)
            p.drawRect(letter)
        elif kind in ('contour', 'decoupe3d', 'laser_decoupe'):
            if side == 'interieur':
                p.drawRect(frame.adjusted(off, off, -off, -off))
                p.drawRect(letter.adjusted(-off, -off, off, off))
            elif side == 'sur':
                p.drawRect(frame)
                p.drawRect(letter)
            else:
                p.drawRect(frame.adjusted(-off, -off, off, off))
                p.drawRect(letter.adjusted(off, off, -off, -off))
        elif kind in ('poche', 'reste', 'gamme', 'laser_gravure', 'relief', 'surface3d', 'ebauche3d', 'finition25d'):
            area = QPainterPath()
            area.addRect(frame)
            hole = QPainterPath()
            hole.addRect(letter)
            p.setBrush(QColor(232, 89, 12, 40))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawPath(area.subtracted(hole))
            p.setPen(tool)
            p.setBrush(Qt.BrushStyle.NoBrush)
            for k in range(1, 4):                       # anneaux de vidage
                p.drawRect(frame.adjusted(off * k, off * k, -off * k, -off * k))
                p.drawRect(letter.adjusted(-off * k / 2, -off * k / 2, off * k / 2, off * k / 2))
            if finish:
                fin = QPen(QColor('#2f9e44'), 1.6)
                p.setPen(fin)
                if not skip:
                    p.drawRect(frame.adjusted(3, 3, -3, -3))
                p.drawRect(letter.adjusted(-3, -3, 3, 3))
        elif kind in ('percage', 'taraudage', 'percage_fraise', 'chanfrein'):
            p.setPen(QPen(QColor('#e8590c'), 1.6))
            for c in (frame.topLeft() + QPointF(14, 14), frame.topRight() + QPointF(-14, 14),
                      frame.bottomLeft() + QPointF(14, -14), frame.bottomRight() + QPointF(-14, -14)):
                p.drawEllipse(c, 6, 6)
                p.drawLine(c + QPointF(-9, 0), c + QPointF(9, 0))
                p.drawLine(c + QPointF(0, -9), c + QPointF(0, 9))
        # --- coupe : matière, profondeur, passes, rampe ------------------------------------
        sec = QRectF(16, top.bottom() + 16, W - 32, H - top.bottom() - 30)
        surf = sec.top() + 18
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor('#e9ecef'))
        p.drawRect(QRectF(sec.left(), surf, sec.width(), sec.bottom() - surf))
        scale = (sec.bottom() - surf - 14) / max(depth, 0.001)
        bottom = surf + depth * scale
        p.setPen(QPen(QColor('#868e96'), 1))
        n = max(1, math.ceil(depth / step - 1e-9)) if step > 0 else 1
        for k in range(1, n):
            y = surf + depth * k / n * scale
            p.drawLine(QPointF(sec.left() + 30, y), QPointF(sec.right() - 10, y))
        p.setPen(QPen(QColor('#e8590c'), 2))
        x0 = sec.left() + 30
        ramp_txt = ''
        if ramp:
            for xa, ya, xb, yb in self.ramp_segments(x0, sec.right() - 10, surf, scale, depth / n):
                p.drawLine(QPointF(xa, ya), QPointF(xb, yb))
            y1 = surf + depth / n * scale
            p.drawLine(QPointF(x0, y1), QPointF(sec.right() - 10, y1))
            if n > 1:                                    # passes suivantes : même rampe, plus bas
                p.setPen(QPen(QColor('#e8590c'), 1, Qt.PenStyle.DashLine))
                p.drawLine(QPointF(x0, bottom), QPointF(sec.right() - 10, bottom))
            a = self.ramp_angle()
            p.setPen(QPen(QColor('#1c3d6e'), 1))
            r = 22.0
            p.drawArc(QRectF(x0 - r, surf - r, 2 * r, 2 * r), 0, int(-a * 16))   # l'angle, depuis l'horizontale
            p.drawText(QRectF(x0 + r + 2, surf + 1, 80, 14), Qt.AlignmentFlag.AlignLeft, f'{a:g}°')
            L = depth / n / math.tan(math.radians(a)) if a > 0 else 0.0
            ramp_txt = tr('Rampe {0}° sur {1} mm par passe').format(f'{a:g}', f'{L:.1f}'.replace('.', ','))
        else:
            p.drawLine(QPointF(x0, surf - 10), QPointF(x0, bottom))
            p.drawLine(QPointF(x0, bottom), QPointF(sec.right() - 10, bottom))
        p.setPen(title)
        p.drawText(QRectF(sec.left(), sec.top(), sec.width(), 16), Qt.AlignmentFlag.AlignLeft,
                   tr('Profondeur {0} mm — {1} passe(s)').format(f'{depth:g}', n))
        if ramp_txt:                                     # sur sa ligne, en bas de la coupe
            p.drawText(QRectF(sec.left() + 4, sec.bottom() - 34, sec.width() - 8, 16), Qt.AlignmentFlag.AlignLeft,
                       ramp_txt)
        if finish and skip:
            p.drawText(QRectF(sec.left(), sec.bottom() - 2, sec.width(), 16), Qt.AlignmentFlag.AlignLeft,
                       tr('finition sans le cadre'))
        p.end()


#: champs de l'usinage par couleur, repliés en fin de formulaire d'opération
COLOR_FIELDS = ('sources', 'items')
#: réglage : formulaire rouvert agrandi
LARGE_KEY = 'fao/formulaire_agrandi'
#: réglages : disposition des cases (sections) des formulaires d'opération et d'outil
CASES_KEYS = {True: 'fao/cases_operation2', False: 'fao/cases_outil'}   # « 2 » : la disposition d'origine a changé


class FieldsDialog(QDialog):
    """Formulaire d'un outil ou d'une opération : sections en colonnes,
    illustration (schéma de l'opération, silhouette de l'outil), champs
    propres à une stratégie masqués pour les autres ; s'ajuste à l'écran."""

    def __init__(self, parent, title: str, obj, doc=None, tools=None,
                 hidden=('id', 'geometry', 'catalog', 'drawings', 'folder', 'machines', 'surface2d', 'history',
                         'contours3d_pl', 'body3d_ref'), library=None,
                 selection=None, kind_choice: bool = False,
                 templates=None, preset: str = '', template: str | None = None, family: str = '', members=()):
        super().__init__(parent)
        #: modèles d'usinage proposés (parcours de la palette `preset`)
        self.templates = list(templates or [])
        self.preset = preset
        #: parcours unifiés : la famille du parcours et ceux qu'elle offre ici (clés) — une liste les fait choisir ;
        #: `switch_to` : le parcours choisi dans la liste (ce formulaire se ferme, celui du parcours choisi s'ouvre)
        self.family, self.members, self.switch_to = family, tuple(members), ''
        #: la stratégie est donnée par le type de parcours : pas de liste à choisir, la ligne « Type de parcours » la
        #: montre (demande du 14/11) ; seule « Nouvelle opération » la fait choisir (`kind_choice`)
        self.fixed_kind = isinstance(obj, model.Operation) and not kind_choice
        from .fit import no_hscroll
        no_hscroll(self)                                 # pas de défilement horizontal à l'ouverture
        #: objets sélectionnés sur le dessin (« Prendre sur la sélection » des instructions)
        self.selection = list(selection or [])
        self._advanced_open = False
        #: `title` None : le formulaire d'un parcours se titre lui-même, « Parcours [type] - [commentaire du modèle] »
        #: (demande du 16/11, 23 h 25), refait quand un modèle y est choisi ou enregistré
        self._auto_title = title is None and isinstance(obj, model.Operation)
        self._tpl_note = template_note(template) if self._auto_title else ''
        self.setWindowTitle(title or '')
        self.setSizeGripEnabled(True)
        self.obj = obj
        self._retitle()
        self.doc = doc
        self.widgets = {}
        self.rows = {}                                   # champ → (étiquette, champ) pour les masquer
        self.doc_tools = list(tools or [])
        #: fiches des outils du document à l'ouverture (modifiables dans « Choisir un outil ») : `changed_tools`
        self._tools_before = {t.id: t.to_dict() for t in self.doc_tools}
        #: Mes outils proposés pour l'opération ; un outil choisi là est copié dans le document
        self.library = {t.id: t for t in (library or [])}
        self.new_tools: list = []
        is_op = isinstance(obj, model.Operation)
        names = [f.name for f in dataclasses.fields(obj) if f.name not in hidden]
        for name in names:
            self.widgets[name] = self._make(name, getattr(obj, name), doc, tools)
        sections = OP_SECTIONS if is_op else TOOL_SECTIONS
        placed = {n for _t, fs in sections for n in fs} | ({'ramp_angle'} if is_op and 'ramp' in self.widgets
                                                           else set())   # l'angle va avec le bouton
        extra = [n for n in names if n not in placed]    # champs d'une version plus récente, de plugins
        color = [n for n in COLOR_FIELDS if is_op and n in self.widgets]
        groups = []
        for sec_title, fields in sections + ([('Autres', tuple(extra))] if extra else []):
            fs = [n for n in fields if n in self.widgets and n not in color]
            if not fs:
                continue
            g = QGroupBox(tr(sec_title))
            if is_op and sec_title == 'Vitesses':        # cadres Ébauche et Finition (demande du 14/11, 19 h 45)
                self._feed_frames(g, fs)
            else:
                self._section_form(g, fs, is_op)
            if is_op and sec_title in EXPERT_SECTIONS and not self._expert() and not self._section_used(fs):
                g.setProperty('vd_expert_only', True)    # mode simple : pas de multicopie, d'enroulement, d'« autres »
                g.setVisible(False)
            groups.append((sec_title, g))
        # les sections en cases, rangées à la guise de l'utilisateur (glisser le titre), disposition gardée
        from .tiles import TileBoard
        cols = QHBoxLayout()
        self.board = TileBoard(dict(groups), self._cases_settings(), CASES_KEYS[is_op], 2,
                               default=OP_LAYOUT if is_op else None)
        cols.addWidget(self.board, 1)
        # illustration
        if is_op:
            self.illustration = OpIllustration(self)
            cols.addWidget(self.illustration)
        else:
            self.illustration = QLabel()
            self.illustration.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.illustration.setMinimumWidth(180)
            cols.addWidget(self.illustration)
        outer = QVBoxLayout(self)
        self.template_box = None
        if is_op and preset:                             # modèles du parcours, comme dans TypeEdit
            row = QHBoxLayout()
            row.addWidget(QLabel(tr('Modèle')))
            from .template_picker import TemplateCombo
            self.template_box = TemplateCombo()          # déroulée : la liste à colonnes (filtre, tri, colonnes)
            self.template_box.addItem(tr('(réglages ci-dessous)'), '')
            for name in self.templates:
                self.template_box.addItem(name, name)
            self.template_box.setCurrentIndex(max(0, self.template_box.findData(template or '')))
            self.template_box.currentIndexChanged.connect(
                lambda _i: self.template_box.currentData() and self.load_template(self.template_box.currentData()))
            self.template_box.currentIndexChanged.connect(
                lambda _i: self._template_titled(self.template_box.currentData()))
            row.addWidget(self.template_box, 1)
            b = QPushButton(tr('Enregistrer comme modèle…'))
            b.setToolTip(tr('Garder ces réglages (et l\'outil) sous un nom, pour les retrouver dans la '
                            'colonne des parcours'))
            b.clicked.connect(lambda: self.save_template())
            row.addWidget(b)
            outer.addLayout(row)
        outer.addLayout(cols, 1)
        if self._auto_title:
            if self.template_box is not None:            # le modèle que la liste montre vraiment
                self._tpl_note = template_note(self.template_box.currentData())
            box = self.widgets.get('kind')
            if isinstance(box, QComboBox):               # la stratégie changée (liste, modèle) : le titre la suit
                box.currentIndexChanged.connect(lambda _i: self._retitle())
            self._retitle()
        self.color_toggle = self.color_box = None
        if color:
            self._build_color_box(outer, color)
        from PySide6.QtGui import QKeySequence, QShortcut
        from .tool_filters import toggle_full_screen
        self.setWindowFlag(Qt.WindowType.WindowMaximizeButtonHint, True)
        # OK et Annuler seuls, grands, colorés, au centre tout en bas (demande du 15/11) ; les autres boutons sur la
        # ligne du dessus (`actions_box`)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self)
        acts = self.actions_box = QDialogButtonBox()
        self.full_button = acts.addButton(tr('Plein écran'), QDialogButtonBox.ButtonRole.ResetRole)
        self.full_button.setToolTip(tr('Plein écran (F11) ; de nouveau pour revenir'))
        self.full_button.clicked.connect(lambda: toggle_full_screen(self))
        self.fit_button = None
        if is_op and doc is not None and 'tool_id' in self.widgets:
            self.fit_button = acts.addButton(tr('Vérifier l\'outil'), QDialogButtonBox.ButtonRole.ActionRole)
            self.fit_button.setToolTip(tr('L\'outil choisi atteint-il tous les détails des formes fermées à usiner ? '
                                          'Surface hors d\'atteinte et plus gros diamètre qui passe partout'))
            self.fit_button.clicked.connect(lambda: self.check_tool())
            self.advise_button = acts.addButton(tr('Outil conseillé'), QDialogButtonBox.ButtonRole.ActionRole)
            self.advise_button.setToolTip(tr('Choisir le plus gros outil adapté à la stratégie qui atteint tous les '
                                             'détails (outils du document et Mes outils de la machine)'))
            self.advise_button.clicked.connect(lambda: self.advise_tool())
            self.rest_button = acts.addButton(tr('Aperçu du reste'), QDialogButtonBox.ButtonRole.ActionRole)
            self.rest_button.setToolTip(tr('Là où l\'outil choisi ne passe pas, en rouge, sur les formes fermées à usiner'))
            self.rest_button.clicked.connect(lambda: self.rest_preview())
        QShortcut(QKeySequence('F11'), self, activated=lambda: toggle_full_screen(self))
        bb.accepted.connect(self.accept_checked)
        bb.rejected.connect(self.reject)
        self.ok_box = bb
        outer.addWidget(acts)
        from .okcancel import prominent
        prominent(bb)
        outer.addWidget(bb)
        for n, w in self.widgets.items():                # schéma à jour à chaque changement
            for sig in ('currentIndexChanged', 'valueChanged', 'toggled', 'textChanged'):
                if hasattr(w, sig):
                    getattr(w, sig).connect(lambda *_a: self._changed())
                    break
        if 'params' in self.widgets:
            self._build_params()
        self._changed()
        if self.wants_proposed_tool():                   # mode expert : l'outil conseillé, proposé et vérifié
            self.propose_tool()
        avail = self.screen().availableGeometry() if self.screen() is not None else None
        want_w = 980 if is_op else 860
        want_h = 640
        if avail is not None:
            want_w, want_h = min(want_w, avail.width() - 40), min(want_h, avail.height() - 60)
        self.resize(want_w, want_h)
        from .tool_filters import open_large
        open_large(self, self._settings(), LARGE_KEY, default=False)
        if isinstance(getattr(self, 'illustration', None), OpIllustration):   # le schéma suit le formulaire
            for wdg in self.widgets.values():
                for sig in ('valueChanged', 'toggled', 'currentIndexChanged'):
                    if hasattr(wdg, sig):
                        getattr(wdg, sig).connect(lambda *_a: self.illustration.update())
                        break

    def _ramp_row(self, form) -> None:
        """Sous l'outil : le bouton « Plongée angulaire » (enfoncé : entrée en rampe, sinon plongée droite) et l'angle
        de la rampe à côté, actif quand le bouton est enfoncé ou les passes connectées (elles descendent en rampe à cet
        angle)."""
        old = self.widgets['ramp']
        btn = ToggleBox(tr('Plongée angulaire'), ramp_icon)
        btn.setChecked(old.isChecked())
        btn.setToolTip(tr('Enfoncé : l’outil entre dans la matière en rampe, à l’angle donné à côté ; relâché : il plonge '
                          'droit'))
        old.deleteLater()
        self.widgets['ramp'] = btn
        holder = QWidget()
        row = QHBoxLayout(holder)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(btn)
        angle = self.widgets.get('ramp_angle')
        if angle is not None:
            alab = QLabel(tr('Angle (°, 0 = 5°)'))
            row.addWidget(alab)
            row.addWidget(angle, 1)
            link = self.widgets.get('link_passes')
            link = link if isinstance(link, QCheckBox) else None

            def sync(*_a):
                angle.setEnabled(btn.isChecked() or (link is not None and link.isChecked()))
            btn.toggled.connect(sync)
            if link is not None:
                link.toggled.connect(sync)
            sync()
            self.rows['ramp_angle'] = (alab, angle)
        else:
            row.addStretch(1)
        lab = QLabel(tr('Entrée'))
        form.addRow(lab, holder)
        self.rows['ramp'] = (lab, holder)

    def _settings(self):
        return getattr(self.parent(), 'settings', None) or \
            getattr(getattr(self.parent(), 'win', None), 'settings', None)

    def _expert(self) -> bool:
        """Le mode expert (toutes les sections) ; en mode simple, certaines sections ne paraissent pas."""
        from . import modes
        return modes.current(self._cases_settings()) != 'simple'

    def _section_form(self, g, fs, is_op: bool) -> None:
        form = QFormLayout(g)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)    # étroit : libellé au-dessus
        for n in fs:
            if n == 'ramp' and is_op:
                self._ramp_row(form)
                continue
            lab = QLabel(tr(LABELS.get(n, n)))
            form.addRow(lab, self.widgets[n])
            self.rows[n] = (lab, self.widgets[n])
            if n == 'tool_id' and is_op:                 # sous l'outil : l'outil proposé et sa vérification
                self.tool_note = QLabel()
                self.tool_note.setWordWrap(True)
                self.tool_note.setStyleSheet('color: palette(highlight);')
                form.addRow(self.tool_note)
                self.tool_note.hide()
            if n == 'kind' and is_op:                    # la nature : donnée par le parcours, montrée sans liste
                self.kind_label = QLabel()
                klab = QLabel(tr('Type de parcours'))
                form.addRow(klab, self.kind_label)
                self.rows['kind_label'] = (klab, self.kind_label)
                if self.family in UNIFIED and len(self.members) > 1:     # parcours unifiés : la liste de la famille
                    labels = dict(UNIFIED[self.family][2])
                    self.family_box = QComboBox()
                    for k in self.members:
                        self.family_box.addItem(tr(labels.get(k, k)), k)
                    self.family_box.setCurrentIndex(max(0, self.family_box.findData(self.preset)))
                    self.family_box.activated.connect(lambda _i: self.choose_member(self.family_box.currentData()))
                    self._family_keys = PopupOnly(self.family_box)       # fermée : aucune touche ne choisit
                    self.family_box.installEventFilter(self._family_keys)
                    flab = QLabel(tr(UNIFIED[self.family][1]))
                    form.addRow(flab, self.family_box)
                    self.rows['family'] = (flab, self.family_box)

    def _feed_frames(self, g, fs) -> None:
        """Vitesses : le cadre Ébauche (avance, plongée, broche) à côté du cadre Finition (avance de finition). Un clic
        (ou la saisie) dans un cadre l'active, en surbrillance : l'opération prend son avance. « Dans la fiche de
        l'outil » y écrit les valeurs du cadre, avec l'historique des changements."""
        from PySide6.QtWidgets import QFrame
        self.feed_box = g
        lay = QVBoxLayout(g)
        row = QHBoxLayout()
        lay.addLayout(row)
        self.feed_frames: dict = {}
        self.feed_save_buttons: dict = {}
        for key, title, names in FEED_FRAMES:
            fr = QFrame()
            fr.setObjectName('cadre_' + key)
            fr.setCursor(Qt.CursorShape.PointingHandCursor)
            fr.setToolTip(tr('Clic : l’opération prend l’avance de ce cadre'))
            v = QVBoxLayout(fr)
            v.addWidget(QLabel('<b>' + tr(title) + '</b>'))
            form = QFormLayout()
            form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
            for n in names:
                if n not in fs:
                    continue
                wn = self.widgets[n]
                lab = QLabel(tr(LABELS.get(n, n)))
                form.addRow(lab, wn)
                self.rows[n] = (lab, wn)
                wn.installEventFilter(self)              # clic, focus donné à la souris
                edit = wn.lineEdit() if hasattr(wn, 'lineEdit') else None
                if edit is not None:                     # le clic dans le texte va à son champ de saisie
                    edit.installEventFilter(self)
                if hasattr(wn, 'valueChanged'):          # la saisie dans un champ qui a déjà le focus
                    wn.valueChanged.connect(lambda _v, k=key, x=wn, e=edit: (x.hasFocus() or (
                        e is not None and e.hasFocus())) and self.set_feed_frame(k))
            v.addLayout(form)
            b = QPushButton(tr('Dans la fiche de l’outil'))
            b.setAutoDefault(False)
            b.clicked.connect(lambda _=False, k=key: self.save_feeds_to_tool(k))
            v.addWidget(b)
            fr.installEventFilter(self)
            row.addWidget(fr)
            self.feed_frames[key] = fr
            self.feed_save_buttons[key] = b
        h = QPushButton(tr('Historique des vitesses de l’outil…'))
        h.setAutoDefault(False)
        h.clicked.connect(lambda: self.feed_history())
        lay.addWidget(h)
        w = self.widgets.get('feed_frame')
        if w is not None:                                # choisi par un clic sur un cadre
            lay.addWidget(w)
            w.setVisible(False)
            w.currentIndexChanged.connect(lambda _i: self._paint_frames())
        self._paint_frames()

    def feed_frame(self) -> str:
        w = self.widgets.get('feed_frame')
        return (w.currentData() if w is not None else '') or 'ebauche'

    def set_feed_frame(self, key: str) -> None:
        """Le cadre `key` ('ebauche' ou 'finition') actif."""
        w = self.widgets.get('feed_frame')
        if w is not None and w.findData(key) >= 0 and w.currentData() != key:
            w.setCurrentIndex(w.findData(key))
        self._paint_frames()

    def _paint_frames(self) -> None:
        active = self.feed_frame()
        for key, fr in getattr(self, 'feed_frames', {}).items():
            on = key == active
            fr.setProperty('vd_active', on)
            fr.setStyleSheet(f'QFrame#cadre_{key} {{ border: 2px solid palette(highlight); border-radius: 5px; '
                             f'background: palette(alternate-base); }}' if on else
                             f'QFrame#cadre_{key} {{ border: 1px solid palette(mid); border-radius: 5px; }}')

    def eventFilter(self, obj, ev) -> bool:                     # noqa: N802 — API Qt
        from PySide6.QtCore import QEvent
        frames = getattr(self, 'feed_frames', None)
        # un clic : pas le focus donné à l'ouverture ni le passage au champ suivant par Tab
        by_user = ev.type() == QEvent.Type.MouseButtonPress or (
            ev.type() == QEvent.Type.FocusIn and ev.reason() == Qt.FocusReason.MouseFocusReason)
        if frames and by_user:
            for key, fr in frames.items():
                if obj is fr or fr.isAncestorOf(obj):
                    self.set_feed_frame(key)
                    break
        return super().eventFilter(obj, ev)

    def save_feeds_to_tool(self, key: str) -> list:
        """Les valeurs du cadre `key` dans la fiche de l'outil choisi (celles à 0 : déjà celles de l'outil) ; le
        champ de l'opération revient à 0 (elle suit l'outil) ; chaque changement entre dans l'historique de l'outil.
        Rend les champs écrits."""
        tool = self.current_tool()
        if not self._doc_tool(tool):                     # Mes outils : à modifier dans Choisir un outil
            return []
        names = dict((k, n) for k, _t, n in FEED_FRAMES)[key]
        done = []
        for n in names:
            w = self.widgets.get(n)
            if w is None:
                continue
            v = float(w.value())
            if v > 0 and abs(v - float(getattr(tool, n, 0.0) or 0.0)) > 1e-9:
                model.note_change(tool, n, getattr(tool, n, 0.0), v,
                                  getattr(self.obj, 'name', '') or tr('formulaire d’une opération'))
                setattr(tool, n, v)
                done.append(n)
            if v > 0:
                w.setValue(0.0)
        self._tool_values()
        return done

    def _doc_tool(self, tool) -> bool:
        return tool is not None and any(tool is t for t in self.doc_tools + self.new_tools)

    def _sync_feed_buttons(self, tool) -> None:
        """« Dans la fiche de l'outil » : pour un outil du document seulement."""
        own = self._doc_tool(tool)
        for b in getattr(self, 'feed_save_buttons', {}).values():
            b.setEnabled(own)
            b.setToolTip(tr('Écrire les valeurs de ce cadre dans la fiche de l’outil du document, gardée à l’OK du '
                            'formulaire (l’opération suit alors l’outil) ; le changement entre dans l’historique de '
                            'l’outil') if own else
                         tr('Outil de Mes outils : ses vitesses se changent dans Choisir un outil (sa fiche, à droite)'))

    def feed_history(self, exec_dialog: bool = True):
        """L'historique des vitesses de l'outil choisi."""
        from .tool_sheet import show_history
        return show_history(self, self.current_tool(), exec_dialog)

    def _section_used(self, fields) -> bool:
        """L'opération se sert-elle de cette section : un de ses champs n'a plus sa valeur d'origine ?"""
        try:
            fresh = type(self.obj)()
        except TypeError:
            return True
        return any(getattr(self.obj, n, None) != getattr(fresh, n, None) for n in fields)

    def _cases_settings(self):
        """Où garder la disposition des cases : les réglages de la fenêtre, sinon ceux de l'application."""
        st = self._settings()
        if st is None:
            from .. import portable
            st = portable.settings()
        if isinstance(self.obj, model.Operation):
            swap_kept_cases(st)                          # gardée d'avant : profondeurs au-dessus des entrées
            rename_kept_cases(st)                        # « Particulier » devenu « Avancé » : à sa place
        return st

    def showEvent(self, e) -> None:                              # noqa: N802 — API Qt
        st = self._settings()
        if st is not None:                               # légèrement translucide (Options, FAO)
            from .options import value
            self.setWindowOpacity(max(0.4, min(1.0, value(st, 'fao/opacite') / 100.0)))
        super().showEvent(e)

    def done(self, r) -> None:
        from .tool_filters import remember_large
        remember_large(self, self._settings(), LARGE_KEY)    # agrandi : rouvert agrandi
        super().done(r)

    def accept_checked(self) -> bool:
        """OK : une opération qui demande un outil n'est pas validée sans lui (« — Choisir un outil — ») ; la liste
        « Outil » est signalée en rouge. Rend vrai si validé."""
        w = self.widgets.get('tool_id')
        kind = self.widgets['kind'].currentData() if 'kind' in self.widgets else getattr(self.obj, 'kind', '')
        if isinstance(self.obj, model.Operation) and w is not None and not w.currentData() and \
                kind not in ('instruction',):
            w.setStyleSheet('QComboBox { border: 2px solid #c92a2a; }')
            w.setToolTip(tr('Choisir l’outil de l’opération'))
            w.setFocus()
            from PySide6.QtWidgets import QToolTip
            QToolTip.showText(w.mapToGlobal(w.rect().bottomLeft()), tr('Choisir l’outil de l’opération'), w)
            return False
        if w is not None:
            w.setStyleSheet('')
        self.accept()
        return True

    def _build_color_box(self, outer, fields) -> None:
        """Usinage par couleur (couleurs, objets choisis) : replié en fin de
        formulaire, le résumé sur le bouton."""
        t = QToolButton()
        t.setCheckable(True)
        t.setAutoRaise(True)
        t.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        t.setArrowType(Qt.ArrowType.RightArrow)
        box = QGroupBox()
        form = QFormLayout(box)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        for n in fields:
            lab = QLabel(tr(LABELS.get(n, n)))
            form.addRow(lab, self.widgets[n])
            self.rows[n] = (lab, self.widgets[n])
        box.setVisible(False)

        def _toggle(on):
            t.setArrowType(Qt.ArrowType.DownArrow if on else Qt.ArrowType.RightArrow)
            box.setVisible(bool(on))
        t.toggled.connect(_toggle)
        outer.addWidget(t)
        outer.addWidget(box)
        self.color_toggle, self.color_box = t, box
        self._color_summary()
        w = self.widgets.get('sources')
        if w is not None:
            w.itemChanged.connect(lambda _it: self._color_summary())
        if 'items' in self.widgets:
            self.widgets['items'].toggled.connect(lambda _on: self._color_summary())

    def _color_summary(self) -> None:
        """« Usinage par couleur — 2 couleur(s) » sur le bouton replié."""
        if self.color_toggle is None:
            return
        it = self.widgets.get('items')
        w = self.widgets.get('sources')
        if it is not None and it.isChecked():
            info = tr('{0} objet(s) choisi(s)').format(len(it.property('vd_items') or []))
        else:
            n = sum(1 for i in range(w.count()) if w.item(i).checkState() == Qt.CheckState.Checked) if w else 0
            info = tr('{0} couleur(s)').format(n) if n else tr('toutes les couleurs')
        self.color_toggle.setText(tr('Usinage par couleur — {0}').format(info))

    def _make(self, name, v, doc, tools):
        obj = self.obj
        if name == 'kind':
            w = QComboBox()
            choices = model.TOOL_KINDS if isinstance(obj, model.CamTool) else model.op_kinds()
            for k, lab in choices.items():
                w.addItem(tr(lab), k)
            if v and w.findData(v) < 0:                  # stratégie d'un plugin absent : gardée telle quelle
                w.addItem(str(v), v)
            w.setCurrentIndex(max(0, w.findData(v)))
        elif name == 'side' or name in FIELD_CHOICES:
            w = QComboBox()
            for k, lab in (SIDES if name == 'side' else FIELD_CHOICES[name]).items():
                w.addItem(tr(lab), k)
            w.setCurrentIndex(max(0, w.findData(v)))
        elif name == 'instruction':
            from ..cam.instructions import INSTRUCTIONS
            w = QComboBox()
            for k, ins in INSTRUCTIONS.items():
                w.addItem(tr(ins.label), k)
            w.setCurrentIndex(max(0, w.findData(v)))
            w.currentIndexChanged.connect(lambda _i: self._build_params())
        elif name == 'params':
            w = QWidget()
            QFormLayout(w).setContentsMargins(0, 0, 0, 0)
            self._params_value = dict(v or {})
            self.param_widgets = {}
        elif name == 'wobble':
            from ..cam.wobble import SHAPES as WOBBLES
            w = QComboBox()
            for k, (lab, effect) in WOBBLES.items():
                w.addItem(tr(lab), k)
                w.setItemData(w.count() - 1, tr(effect), Qt.ItemDataRole.ToolTipRole)
            w.setCurrentIndex(max(0, w.findData(v)))
        elif name == 'wrap':
            from ..cam.wrap import MODES as WRAPS
            w = QComboBox()
            for k, lab in WRAPS.items():
                w.addItem(tr(lab), k)
            w.setCurrentIndex(max(0, w.findData(v)))
        elif name == 'thread':
            w = QComboBox()
            for k, (d, p, pre) in model.THREADS.items():
                w.addItem(f'{k} — pas {p:g}, avant-trou Ø {pre:g}', k)
            w.setCurrentIndex(max(0, w.findData(v)))
        elif name in ('tool_id', 'ref_tool_id'):
            # outils du document ; Mes outils par dossiers (tool_picker) : une
            # bibliothèque de centaines d'outils ne tient pas dans une liste
            from .tool_picker import ToolCombo
            settings = getattr(self.parent(), 'settings', None) or \
                getattr(getattr(self.parent(), 'win', None), 'settings', None)
            op_kind = obj.kind if isinstance(obj, model.Operation) else ''
            w = ToolCombo(self.library, list(tools or []), settings, op_kind=op_kind, machine=self._machine())
            self._fill_tools(w, name, op_kind, v, list(tools or []))
        elif name == 'items':
            w = QCheckBox(tr('{0} objet(s) choisi(s) — décocher pour usiner par couleur').format(len(v or []))
                          if v else tr('aucun : par couleur'))
            w.setChecked(bool(v))
            w.setEnabled(bool(v))
            w.setProperty('vd_items', list(v or []))
        elif name in ('faces3d', 'contours3d'):
            n = len(v or [])
            text = (tr('{0} face(s) — décocher pour toute la pièce') if name == 'faces3d'
                    else tr('{0} contour(s) — décocher pour toute la pièce')).format(n)
            w = QCheckBox(text if n else tr('aucune : toute la pièce'))
            w.setChecked(bool(n))
            w.setEnabled(bool(n))
            w.setToolTip(tr('Vue 3D : « Clic : choisir des faces » (ou des contours), puis « Usinage 3D » '
                            '› « Remplacer la zone de… »'))
            w.setProperty('vd_items', list(v or []))
        elif name == 'sources':
            w = QListWidget()
            w.setMaximumHeight(110)
            for t in (doc.tools if doc else []):
                it = QListWidgetItem(swatch(t.color), t.name or tr('Outil {0}').format(t.index + 1))
                it.setData(Qt.ItemDataRole.UserRole, t.index)
                it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                it.setCheckState(Qt.CheckState.Checked if t.index in (v or []) else Qt.CheckState.Unchecked)
                w.addItem(it)
            w.setToolTip(tr('Aucune cochée : toutes les couleurs'))
        elif isinstance(v, bool):
            w = QCheckBox()
            w.setChecked(v)
        elif isinstance(v, int):
            w = QSpinBox()
            w.setRange(-1 if name == 'body3d' else 0, 9999)
            if name == 'body3d':                         # −1 : toute la pièce (pas le premier corps)
                w.setSpecialValueText(tr('toute la pièce'))
            w.setValue(v)
        elif isinstance(v, float):
            w = QDoubleSpinBox()
            w.setDecimals(3)
            w.setRange(-100000, 1000000)
            w.setValue(v)
            if name == 'ramp_angle' and isinstance(obj, model.Operation):   # 89° au plus (demande du 16/11)
                w.setRange(0.0, strategies.RAMP_ANGLE_MAX)
                w.setValue(min(max(v, 0.0), strategies.RAMP_ANGLE_MAX))
                w.setToolTip(tr('Angle de la descente : de 0,5 à 89° (0 = 5°)'))
            if name in ZERO_IS_TOOL and isinstance(obj, model.Operation) and v >= 0:   # négatif (gammes) : gardé
                w.setSpecialValueText(tool_value_text(name, None))     # la valeur de l'outil : `_tool_values`
                w.setToolTip(tr('À 0, le champ prend la valeur de l’outil : {0}').format(tool_value_tip(name, None)))
                w.setMinimum(0)
        else:
            w = QLineEdit(str(v))
        return w

    def _build_params(self) -> None:
        """Champs des réglages de l'instruction choisie (description de
        cam.instructions), valeurs gardées d'une instruction à l'autre."""
        box = self.widgets.get('params')
        if box is None:
            return
        self._params_value.update(self._read_params())
        form = box.layout()
        while form.rowCount():
            form.removeRow(0)
        self.param_widgets = {}
        self._params_key = self._params_source()
        ins = self._params_desc()
        advanced = None
        if ins is not None and ins.pick:
            b = QPushButton(tr('Prendre sur la sélection'))
            b.setToolTip(tr('Position (et cotes) reprises de l\'encombrement des objets sélectionnés'))
            b.setEnabled(bool(self._pick_source(ins)))
            b.clicked.connect(lambda _=False: self._pick())
            form.addRow(b)
            self.pick_button = b
        if ins is not None and ins.advanced:
            from PySide6.QtWidgets import QToolButton
            toggle = QToolButton()
            toggle.setText(tr('Réglages avancés'))
            toggle.setCheckable(True)
            toggle.setChecked(self._advanced_open)
            toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            toggle.setArrowType(Qt.ArrowType.DownArrow if self._advanced_open else Qt.ArrowType.RightArrow)
            toggle.setAutoRaise(True)
            advanced = QWidget()
            adv_form = QFormLayout(advanced)
            adv_form.setContentsMargins(12, 0, 0, 0)
            advanced.setVisible(self._advanced_open)

            def _toggle(on, t=toggle, w=advanced):
                self._advanced_open = bool(on)
                t.setArrowType(Qt.ArrowType.DownArrow if on else Qt.ArrowType.RightArrow)
                w.setVisible(bool(on))
            toggle.toggled.connect(_toggle)
            self.advanced_toggle, self.advanced_box = toggle, advanced
        names = {}
        if self._params_key == 'bloc':                  # paramètres nommés (catalogue, fonction personnalisée)
            from ..cam.instructions import bloc_names
            names = {f'p{k}': n for k, n in enumerate(bloc_names(self._params_value), start=1) if n}
        for f in (ins.fields if ins else []):
            name, lab, kind, default = f[0], f[1], f[2], f[3]
            if name in names:
                lab = f'{names[name]} {{{name}}}'
            v = self._params_value.get(name, default)
            if kind == 'bool':
                w = QCheckBox()
                w.setChecked(bool(v))
            elif kind == 'int':
                w = QSpinBox()
                w.setRange(-1000000, 1000000)
                w.setValue(int(v))
            elif kind == 'float':
                w = QDoubleSpinBox()
                w.setDecimals(3)
                w.setRange(-100000, 100000)
                w.setValue(float(v))
            elif kind == 'choice':
                w = QComboBox()
                for c in f[4]:
                    w.addItem(tr(c), c)
                w.setCurrentIndex(max(0, w.findData(v)))
            elif kind == 'text':
                from PySide6.QtWidgets import QPlainTextEdit
                w = QPlainTextEdit(str(v))
                w.setMinimumHeight(90)
            elif kind == 'file':                         # chemin, avec « … » pour le choisir sur le poste
                w = QLineEdit(str(v))
                act = w.addAction(self.style().standardIcon(QStyle.StandardPixmap.SP_DirOpenIcon),
                                  QLineEdit.ActionPosition.TrailingPosition)
                act.setToolTip(tr('Choisir le fichier sur le poste'))
                act.triggered.connect(lambda _c=False, e=w: self._browse_param_file(e))
            else:
                w = QLineEdit(str(v))
            (adv_form if advanced is not None and name in ins.advanced else form).addRow(tr(lab), w)
            self.param_widgets[name] = w
        if advanced is not None:
            form.addRow(self.advanced_toggle)
            form.addRow(advanced)
        if ins is not None and ins.note:
            note = QLabel(tr(ins.note))
            note.setWordWrap(True)
            note.setStyleSheet('color: #868e96;')
            form.addRow(note)

    def _params_source(self) -> str | None:
        """Clé des réglages affichés : l'instruction choisie, ou la stratégie
        qui a ses propres réglages (texte machine…)."""
        kind = self.widgets['kind'].currentData() if 'kind' in self.widgets else None
        if kind == 'instruction' and 'instruction' in self.widgets:
            return self.widgets['instruction'].currentData()
        return kind

    def _params_desc(self):
        from ..cam.instructions import describe
        key = self._params_source()
        return describe(key) if key else None

    def _pick_source(self, ins):
        """Encombrement des objets sélectionnés (ou leurs cercles pour une
        mesure à deux repères) ; vide s'il n'y a rien à reprendre."""
        if ins.pick == 'two_circles':
            from ..core import holes
            circles = [c for c in (holes.circle_of(it) for it in self.selection) if c]
            return circles if len(circles) >= 2 else []
        boxes = [b for b in (it.bbox() for it in self.selection) if b]
        if not boxes:
            return ()
        return (min(b[0] for b in boxes), min(b[1] for b in boxes),
                max(b[2] for b in boxes), max(b[3] for b in boxes))

    def _pick(self) -> None:
        """Position (et cotes) de l'instruction reprises de la sélection."""
        from ..cam.instructions import from_selection
        key = self._params_source()
        ins = self._params_desc()
        if ins is None or not ins.pick:
            return
        src = self._pick_source(ins)
        if not src:
            return
        if ins.pick == 'two_circles':
            p = from_selection(key, self._read_params(), None, src)
        else:
            p = from_selection(key, self._read_params(), src)
        self._params_value.update(p)
        self.param_widgets = {}                          # valeurs reprises : ne pas relire les anciens champs
        self._build_params()

    def _browse_param_file(self, edit) -> None:
        from PySide6.QtWidgets import QFileDialog
        start = edit.text().strip()
        path, _ = QFileDialog.getOpenFileName(self, tr('Programme appelé'), start,
                                              tr('Programmes (*.simpl *.nc *.h *.mpf *.iso);;Tous les fichiers (*)'))
        if path:
            edit.setText(path.replace('/', '\\'))

    def _read_params(self) -> dict:
        out = {}
        for name, w in getattr(self, 'param_widgets', {}).items():
            if isinstance(w, QCheckBox):
                out[name] = w.isChecked()
            elif isinstance(w, (QSpinBox, QDoubleSpinBox)):
                out[name] = w.value()
            elif isinstance(w, QComboBox):
                out[name] = w.currentData()
            elif hasattr(w, 'toPlainText'):
                out[name] = w.toPlainText()
            else:
                out[name] = w.text()
        return out

    def _machine(self) -> tuple:
        """(clé, libellé) de la machine du réglage FAO (post-processeur choisi)."""
        panel = self.parent()
        try:
            key = panel.setup().post
            label = panel.post.currentText() if hasattr(panel, 'post') else key
            return (key or '', label or key or '')
        except Exception:                              # formulaire hors du panneau FAO (essais, outil seul)
            return ('', '')

    def _fill_tools(self, w, name: str, op_kind: str, current, tools: list) -> None:
        """Liste « Outil » : outils du document dans l'ordre réglé pour la
        stratégie (Outils proposés par opération ; mode « seulement » : les
        autres cachés, l'outil choisi reste) ; réglage enregistré : les
        premiers outils adaptés de Mes outils ensuite."""
        from ..cam import toolprefs
        w.blockSignals(True)
        w.clear()
        w.op_kind, w.doc_tools, w.proposals = op_kind, list(tools), []
        if name == 'ref_tool_id':
            w.addItem(tr('(aucun)'), '')
        prefs = toolprefs.load(w.settings)
        shown = toolprefs.ordered(tools, op_kind, prefs) if op_kind else list(tools)
        shown += [t for t in tools if t.id == current and t not in shown]
        from ..cam import toollib
        from .tool_filters import MACHINE_ONLY, tool_icon
        for t in shown:
            w.addItem(tool_icon(t), toollib.short_label(t), t.id)
            w.setItemData(w.count() - 1, toollib.summary(t), Qt.ItemDataRole.ToolTipRole)
        mkey = w.machine[0] if (w.settings is None or w.settings.value(MACHINE_ONLY, True)
                                not in (False, 'false', '0', 0)) else ''
        if op_kind and name == 'tool_id' and toolprefs.customized(op_kind, prefs):
            lib = [t for t in toolprefs.ordered(self.library.values(), op_kind, prefs, only=True)
                   if not any(toolprefs.matches(toolprefs.tool_rule(t), d) for d in tools)
                   and toollib.for_machine(t, mkey)]
            w.proposals = [t.id for t in lib[:toolprefs.LIST_PROPOSALS]]
        w.finish()
        i = w.findData(current) if current or name != 'tool_id' else -1
        if i < 0 and name == 'tool_id':                  # pas encore d'outil : aucun mis d'office (14/11, 19 h 45)
            w.insertItem(0, tr('— Choisir un outil —'), '')
            i = 0
        w.setCurrentIndex(max(0, i))
        w._last = w.currentIndex()
        w.blockSignals(False)

    def _tool_values(self) -> None:
        """Les champs à 0 qui prennent la valeur de l'outil la montrent, celle de l'outil choisi."""
        if not isinstance(self.obj, model.Operation):
            return
        tool = self.current_tool() if 'tool_id' in self.widgets else None
        self._sync_feed_buttons(tool)
        for name in ZERO_IS_TOOL:
            w = self.widgets.get(name)
            if not isinstance(w, QDoubleSpinBox) or not w.specialValueText():
                continue
            text, tip = tool_value_text(name, tool), tool_value_tip(name, tool)
            rough = self.widgets.get('feed')
            if name == 'finish_feed' and tool is not None and float(getattr(tool, 'finish_feed', 0.0) or 0.0) <= 0 \
                    and isinstance(rough, QDoubleSpinBox) and rough.value() > 0:   # l'avance d'ébauche de l'opération
                text = '{0} mm/min'.format(_num(rough.value()))
                tip = tr('{0} mm/min (avance d’ébauche)').format(_num(rough.value()))
            w.setToolTip(tr('À 0, le champ prend la valeur de l’outil : {0}').format(tip))
            if text != w.specialValueText():             # Qt réécrit le champ : seulement si l'outil a changé,
                w.setSpecialValueText(text)              # jamais pendant la frappe

    def choose_member(self, key: str) -> None:
        """Parcours unifiés : un autre parcours de la famille choisi dans la liste — ce formulaire se ferme (rien
        n'est ajouté) et celui du parcours choisi s'ouvre, prérempli de ses propres dernières valeurs
        (`CamPanel.new_operation` lit `switch_to`)."""
        if key and str(key) != self.preset and str(key) in self.members:
            self.switch_to = str(key)
            self.reject()

    def _changed(self) -> None:
        """Champs de la stratégie choisie, schéma à jour."""
        note = getattr(self, 'tool_note', None)
        if note is not None and not getattr(self, '_proposing', False):
            note.hide()                                  # l'outil proposé et sa vérification ne valent plus
        self._tool_values()
        if isinstance(self.obj, model.Operation) and 'kind' in self.widgets:
            kind = self.widgets['kind'].currentData()
            from .tool_picker import PICK, ToolCombo
            for name in ('tool_id', 'ref_tool_id'):              # outils proposés : ceux de la stratégie choisie
                w = self.widgets.get(name)
                if isinstance(w, ToolCombo) and w.op_kind != kind:
                    cur = w.currentData()
                    if cur == PICK:
                        cur = w.itemData(w._last)
                    self._fill_tools(w, name, kind, cur, self.doc_tools + self.new_tools)
            if 'params' in self.widgets and getattr(self, '_params_key', None) != self._params_source():
                self._build_params()                         # réglages de la stratégie (ou de l'instruction) choisie
            known = kind in model.OP_KINDS                   # stratégie de plugin : tous les champs
            own = KIND_FIELDS.get(kind, set())
            for n, (lab, w) in self.rows.items():
                if kind == 'instruction':
                    show = n in INSTRUCTION_FIELDS
                elif n in RAMP_FIELDS:                       # la plongée angulaire : où le parcours la suit
                    show = (not known) or kind in RAMP_KINDS
                else:
                    show = ((not known) or n not in OPTIONAL or n in own)
                if n == 'kind' and getattr(self, 'fixed_kind', False):
                    show = False
                if n == 'family':                            # parcours unifiés : la liste de la famille, toujours
                    show = True
                if n == 'kind_label':                        # le type de parcours, sans liste (ni sous celle de la famille)
                    show = bool(getattr(self, 'fixed_kind', False)) and not hasattr(self, 'family_box')
                    ps = presets()
                    pre = ps.get(self.preset) if self.preset else None
                    w.setText(tr(pre[0]) if pre is not None and pre[1] == kind     # le parcours de la palette
                              else tr(model.op_kinds().get(kind, kind)))
                if n == 'stock':                             # XY, 3D, largeur de chanfrein : selon le parcours
                    lab.setText(tr(field_label(n, kind)))
                lab.setVisible(show)
                w.setVisible(show)
            for g in self.findChildren(QGroupBox):           # sections vides masquées
                lay = g.layout()
                if isinstance(lay, QFormLayout) and lay.rowCount():
                    rows_shown = any(lay.itemAt(r, QFormLayout.ItemRole.FieldRole) is not None and
                                     lay.itemAt(r, QFormLayout.ItemRole.FieldRole).widget() is not None and
                                     not lay.itemAt(r, QFormLayout.ItemRole.FieldRole).widget().isHidden()
                                     for r in range(lay.rowCount()))
                    if g is getattr(self, 'color_box', None):     # repliée : ouverte seulement par son bouton
                        self.color_toggle.setVisible(rows_shown)
                        g.setVisible(rows_shown and self.color_toggle.isChecked())
                    elif g.parent() is not self.widgets.get('params'):
                        g.setVisible(rows_shown and not g.property('vd_expert_only'))
            frames = getattr(self, 'feed_frames', None)
            if frames:                                   # cadres de vitesses : masqués avec leurs champs
                for key, _t, fnames in FEED_FRAMES:
                    frames[key].setVisible(any(n in self.rows and not self.rows[n][1].isHidden() for n in fnames))
                self.feed_box.setVisible(any(not f.isHidden() for f in frames.values())
                                         and not self.feed_box.property('vd_expert_only'))
            self.illustration.update()
        elif isinstance(self.obj, model.CamTool):
            try:
                from .toollib_dialog import silhouette
                probe = model.CamTool.from_dict(self.obj.to_dict())
                self._fill(probe)
                self.illustration.setPixmap(silhouette(probe, 180, 300))
            except Exception:                            # cotes en cours de saisie, incohérentes
                pass

    def _fill(self, target) -> None:
        for name, w in self.widgets.items():
            if name == 'params':
                continue
            if isinstance(w, QComboBox):
                v = w.currentData()
                if isinstance(v, str) and v.startswith('lib:'):
                    continue
            elif isinstance(w, QListWidget):
                v = [w.item(i).data(Qt.ItemDataRole.UserRole) for i in range(w.count())
                     if w.item(i).checkState() == Qt.CheckState.Checked]
            elif name in ('items', 'faces3d', 'contours3d'):
                v = list(w.property('vd_items') or []) if w.isChecked() else []
            elif isinstance(w, QCheckBox):
                v = w.isChecked()
            elif isinstance(w, (QSpinBox, QDoubleSpinBox)):
                v = w.value()
            else:
                v = w.text()
            setattr(target, name, v)

    def _from_library(self, key: str) -> str:
        """Outil de Mes outils choisi : copié dans les outils du document
        (n° de magasin libre) ; rend l'identifiant de la copie."""
        t = self.library.get(key[4:])
        if t is None:
            return ''
        same = next((c for c in self.doc_tools + self.new_tools
                     if c.name == t.name and c.kind == t.kind and c.diameter == t.diameter), None)
        if same is not None:                               # déjà dans le document : pas de doublon
            return same.id
        c = model.CamTool.from_dict(t.to_dict())
        c.id, c.folder = model.new_id(), ''
        used = {x.number for x in self.doc_tools + self.new_tools}
        if c.number in used or c.number <= 0:
            c.number = max(used | {0}) + 1
        self.new_tools.append(c)
        return c.id

    # --- modèles du parcours -----------------------------------------------------------------
    def _set_widget(self, name: str, v) -> None:
        w = self.widgets.get(name)
        if w is None:
            return
        if name == 'params':
            self._params_value = dict(v or {})
            self.param_widgets = {}
            self._build_params()
        elif isinstance(w, QComboBox):
            i = w.findData(v)
            if i >= 0:
                w.setCurrentIndex(i)
        elif isinstance(w, QCheckBox) and name != 'items':
            w.setChecked(bool(v))
        elif isinstance(w, (QSpinBox, QDoubleSpinBox)):
            try:
                w.setValue(type(w.value())(v))
            except (TypeError, ValueError):
                pass
        elif isinstance(w, QLineEdit):
            w.setText(str(v))

    def check_tool(self, show: bool = True) -> str:
        """« Vérifier l'outil » : les formes de l'opération (réglages du
        formulaire) et l'outil choisi ; rend le message."""
        from ..cam import toolfit
        o = model.Operation.from_dict(self.obj.to_dict())
        self._fill(o)
        tool = self.current_tool()
        if tool is None:
            msg = tr('Choisir d\'abord un outil.')
        else:
            try:
                f = toolfit.check(self.doc, o, tool)
            except Exception as ex:                      # géométrie impossible à évaluer : dit tel quel
                f, msg = None, tr('Vérification impossible : {0}').format(ex)
            if f is not None and f.area <= 0:
                msg = tr('Aucune forme fermée à usiner pour cette opération (couleurs ou objets choisis).')
            elif f is not None:
                fmt = lambda v: f'{v:.2f}'.rstrip('0').rstrip('.').replace('.', ',')       # noqa: E731
                name = f'T{tool.number} {tool.name} (Ø{fmt(tool.diameter)})'
                if f.fraction <= 0.005:
                    msg = tr('{0} atteint tous les détails ({1} forme(s)).').format(name, f.parts)
                else:
                    msg = tr('{0} n\'atteint pas {1} % de la surface ({2} mm²) : détails plus fins que l\'outil.'
                             ).format(name, fmt(100 * f.fraction), fmt(f.unreached))
                msg += '\n' + tr('Plus gros outil qui passe partout : Ø {0} mm environ.').format(fmt(f.fit_diameter))
        if show:
            QMessageBox.information(self, tr('Vérifier l\'outil'), msg)
        return msg

    def rest_preview(self, exec_dialog: bool = True):
        """« Aperçu du reste » : les formes de l'opération (réglages du formulaire) et l'outil choisi. Rend la fenêtre."""
        from .rest_preview_dialog import RestPreviewDialog
        o = model.Operation.from_dict(self.obj.to_dict())
        self._fill(o)
        reg = strategies.region([g for it in strategies.source_items(self.doc, o) if (g := strategies.item_geometry(it))], 0.01)
        if reg is None or reg.is_empty:
            QMessageBox.information(self, tr('Aperçu du reste'), tr('Aucune forme fermée à usiner pour cette opération (couleurs ou objets choisis).'))
            return None
        tool = self.current_tool()
        dlg = RestPreviewDialog(self, reg, list(self.doc_tools) + list(self.new_tools), tool=tool, depth=o.depth, stock=o.stock,
                                source=getattr(self.doc, 'source_path', None) or '')
        if exec_dialog:
            dlg.exec()
        return dlg

    def advise_tool(self, show: bool = True, kind: str = ''):
        """« Outil conseillé » : le plus gros outil adapté qui atteint tous les
        détails, choisi dans la liste ; rend l'outil (None : aucun)."""
        from ..cam import toollib, toolfit, toolprefs
        from .tool_filters import MACHINE_ONLY
        o = model.Operation.from_dict(self.obj.to_dict())
        self._fill(o)
        st = self._settings()
        mkey = self._machine()[0] if (st is None or st.value(MACHINE_ONLY, True) not in (False, 'false', '0', 0))             else ''
        lib = [t for t in self.library.values() if toollib.for_machine(t, mkey)]
        if kind and not lib:                             # outil proposé : tout Mes outils si aucun n'est de la machine
            lib = list(self.library.values())
        cands = list(self.doc_tools) + [t for t in lib if not any(t.id == d.id for d in self.doc_tools)]
        if kind:                                         # outil proposé : de la nature du parcours
            cands = [t for t in cands if t.kind == kind]
        try:
            t, fit_d = toolfit.advise(self.doc, o, cands, toolprefs.load(st)) if cands else (None, 0.0)
        except Exception as ex:                          # géométrie impossible à évaluer
            t, fit_d, msg = None, 0.0, tr('Conseil impossible : {0}').format(ex)
        else:
            fmt = lambda v: f'{v:.2f}'.rstrip('0').rstrip('.').replace('.', ',')       # noqa: E731
            if t is None:
                msg = tr('Aucun outil ne passe partout ; plus gros Ø qui passe : {0} mm environ.').format(fmt(fit_d))                     if fit_d > 0 else tr('Aucune forme fermée à usiner pour cette opération.')
            else:
                w = self.widgets.get('tool_id')
                key = t.id if any(t.id == d.id for d in self.doc_tools) else 'lib:' + t.id
                if w is not None:
                    i = w.findData(key)
                    if i >= 0:
                        w.setCurrentIndex(i)
                msg = tr('Outil conseillé : {0} (plus gros Ø qui passe partout : {1} mm environ).').format(
                    toollib.short_label(t), fmt(fit_d))
        if not cands:                                    # aucun outil (de la nature voulue) parmi les candidats
            msg = tr('Aucun outil adapté parmi les outils du document et Mes outils de la machine')
        self.last_advice = msg
        if show:
            QMessageBox.information(self, tr('Outil conseillé'), msg)
        return t

    def wants_proposed_tool(self) -> bool:
        """Nouveau parcours de la palette en mode expert, sans outil choisi, option cochée : l'outil conseillé est
        proposé (voir `proposes_tool`)."""
        if not isinstance(self.obj, model.Operation) or self.doc is None or self.current_tool() is not None \
                or getattr(self, 'fit_button', None) is None or getattr(self, 'tool_note', None) is None:
            return False
        return proposes_tool(self._cases_settings(), self.preset or '')

    def propose_tool(self) -> str:
        """L'outil conseillé, de la nature du parcours, choisi (s'il n'y en a toujours pas) et vérifié ; le message
        sous l'outil, caché dès qu'un champ change. Rend le message."""
        note = getattr(self, 'tool_note', None)
        if note is None or self.current_tool() is not None:
            return ''
        found = presets().get(self.preset or '')
        kind = found[3] if found else ''
        w = self.widgets.get('tool_id')
        self._proposing = True
        try:
            t = self.advise_tool(show=False, kind=kind)
            advice = getattr(self, 'last_advice', '')
            cur = self.current_tool()
            if t is not None and (cur is None or cur.id != t.id):    # pas dans la liste : comme sans conseil
                t = None
            lead = ''
            if t is None:                                # conseil sans réponse : l'outil d'office d'avant, vérifié
                lead = advice
                first = next((x for x in self.doc_tools if x.kind == kind), None) or \
                    next((x for x in self.library.values() if x.kind == kind), None)
                if first is not None and w is not None:
                    i = w.findData(first.id)
                    i = i if i >= 0 else w.findData('lib:' + first.id)
                    if i >= 0:
                        w.setCurrentIndex(i)
                t = self.current_tool()
            if t is not None:
                msg = tr('Outil proposé (mode expert) : {0}').format(self.check_tool(show=False))
                msg = f'{lead}\n{msg}' if lead else msg
            else:
                msg = advice or tr('Aucun outil proposé')
            note.setText(msg)
            note.show()
        finally:
            self._proposing = False
        return msg

    def changed_tools(self) -> set:
        """Ids des outils du document dont la fiche a changé depuis l'ouverture du formulaire."""
        return {t.id for t in self.doc_tools if t.id in self._tools_before and self._tools_before[t.id] != t.to_dict()}

    def current_tool(self):
        """Outil choisi (du document, de Mes outils ou ajouté par un modèle)."""
        w = self.widgets.get('tool_id')
        v = w.currentData() if w is not None else None
        if v == '__choisir__':
            v = w.itemData(getattr(w, '_last', 0))
        if isinstance(v, str) and v.startswith('lib:'):
            return self.library.get(v[4:])
        return next((t for t in self.doc_tools + self.new_tools if t.id == v), None)

    def _retitle(self) -> None:
        """Le titre d'un formulaire de parcours qui se titre lui-même (`toolpath_title`) : la stratégie de la liste
        si elle y est (un modèle peut la changer), sinon celle de l'opération."""
        if not getattr(self, '_auto_title', False):
            return
        box = getattr(self, 'widgets', {}).get('kind')
        kind = box.currentData() if isinstance(box, QComboBox) and box.currentData() else getattr(self.obj, 'kind', '')
        self.setWindowTitle(toolpath_title(kind, self.preset, self._tpl_note))

    def _template_titled(self, name) -> None:
        """Un modèle choisi (ou « réglages ci-dessous ») : son commentaire dans le titre."""
        self._tpl_note = template_note(name) if self._auto_title else ''
        self._retitle()

    def load_template(self, name: str) -> bool:
        """Réglages du modèle `name` dans le formulaire (et son outil)."""
        from ..cam import templates as TPL
        found = TPL.all_templates().get(name)
        if found is None or not (found[1].get('operations') or []):
            return False
        tpl = found[1]
        d = dict(tpl['operations'][0])
        for k in ('id', 'items', 'sources', 'tool_id', 'ref_tool_id', 'enabled'):
            d.pop(k, None)
        if d.get('kind') not in model.op_kinds():
            d.pop('kind', None)
        for k, v in model.Operation.from_dict(d).to_dict().items():
            if k in d:
                self._set_widget(k, v)
        tools = tpl.get('tools') or []
        w = self.widgets.get('tool_id')
        if tools and w is not None:
            want = model.CamTool.from_dict(tools[0])
            pool = model.CamSetup(tools=self.doc_tools + self.new_tools)
            got = TPL._match(pool, want)
            if got is None:
                got = model.CamTool.from_dict(want.to_dict())
                got.id, got.folder = model.new_id(), ''
                used = {x.number for x in self.doc_tools + self.new_tools}
                if got.number in used or got.number <= 0:
                    got.number = max(used | {0}) + 1
                self.new_tools.append(got)
                w.insertItem(0, f'T{got.number} {got.name}', got.id)
            w.setCurrentIndex(max(0, w.findData(got.id)))
        self._changed()
        return True

    def save_template(self, name: str | None = None) -> dict | None:
        """Ces réglages (et l'outil) en modèle d'usinage du parcours."""
        from ..cam import templates as TPL
        if name is None:
            from PySide6.QtWidgets import QInputDialog
            default = self.widgets['name'].text() if 'name' in self.widgets else ''
            name, ok = QInputDialog.getText(self, tr('Modèle d\'usinage'), tr('Nom du modèle'), text=default)
            if not ok:
                return None
        name = (name or '').strip()
        if not name:
            return None
        op = model.Operation.from_dict(self.obj.to_dict())
        self._fill(op)
        if 'params' in self.widgets:
            op.params = {**self._params_value, **self._read_params()}
        tpl = TPL.single(op, self.current_tool(), name, self.preset)
        TPL.save_user(tpl)
        if self.template_box is not None and self.template_box.findData(name) < 0:
            self.template_box.blockSignals(True)
            self.template_box.addItem(name, name)
            self.template_box.setCurrentIndex(self.template_box.count() - 1)
            self.template_box.blockSignals(False)
        if self.template_box is not None and self.template_box.currentData() == name:
            self._template_titled(name)                  # le formulaire est désormais celui d'un modèle
        pal = getattr(getattr(self.parent(), 'win', None), 'cam_palette', None)
        if pal is not None:
            pal.refresh()
        return tpl

    def apply(self) -> None:
        before = {k: float(getattr(self.obj, k, 0.0) or 0.0) for k in model.FEED_KEYS} \
            if isinstance(self.obj, model.CamTool) else None
        self._apply_fields()
        for k, old in (before or {}).items():            # formulaire d'un outil : l'historique de ses vitesses
            new = float(getattr(self.obj, k, 0.0) or 0.0)
            if abs(new - old) > 5e-4:
                model.note_change(self.obj, k, old, new, tr('formulaire de l’outil'))

    def _apply_fields(self) -> None:
        for name, w in self.widgets.items():
            if name == 'params':
                self._params_value.update(self._read_params())
                setattr(self.obj, name, dict(self._params_value))
                continue
            if isinstance(w, QComboBox):
                v = w.currentData()
                if v == '__choisir__':                         # ligne « Choisir dans Mes outils… »
                    v = w.itemData(getattr(w, '_last', 0))
                if isinstance(v, str) and v.startswith('lib:'):
                    v = self._from_library(v)
            elif isinstance(w, QListWidget):
                v = [w.item(i).data(Qt.ItemDataRole.UserRole) for i in range(w.count())
                     if w.item(i).checkState() == Qt.CheckState.Checked]
            elif name in ('items', 'faces3d', 'contours3d'):
                v = list(w.property('vd_items') or []) if w.isChecked() else []
            elif isinstance(w, QCheckBox):
                v = w.isChecked()
            elif isinstance(w, (QSpinBox, QDoubleSpinBox)):
                v = w.value()
            else:
                v = w.text()
                old = getattr(self.obj, name, None)
                if isinstance(old, (list, dict)):        # liste sans champ propre : relue, sinon gardée
                    import ast
                    try:
                        got = ast.literal_eval(v)
                    except (ValueError, SyntaxError):
                        got = None
                    v = got if isinstance(got, type(old)) else old
            setattr(self.obj, name, v)


class ToolDbDialog(QDialog):
    """Choix d'outils dans une base TypeEdit : arbre des dossiers, cases à
    cocher, filtre sur le nom ou la référence."""

    def __init__(self, parent, entries):
        from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem
        super().__init__(parent)
        from .fit import no_hscroll
        no_hscroll(self)                                 # pas de défilement horizontal à l'ouverture
        self.setWindowTitle(tr('Base d\'outils TypeEdit'))
        self.resize(560, 520)
        self.entries = entries
        lay = QVBoxLayout(self)
        self.filter = QLineEdit()
        self.filter.setPlaceholderText(tr('Filtrer (nom, référence, Ø…)'))
        self.filter.textChanged.connect(self._filter)
        lay.addWidget(self.filter)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels([tr('Outil'), tr('Nature'), 'Ø', tr('Angle'), tr('Référence')])
        self.tree.setColumnWidth(0, 260)
        folders: dict = {}
        self.items = []
        for i, e in enumerate(entries):
            parent_item = self.tree.invisibleRootItem()
            key = ()
            for name in e.path:
                key = key + (name,)
                if key not in folders:
                    it = QTreeWidgetItem([name])
                    parent_item.addChild(it)
                    folders[key] = it
                parent_item = folders[key]
            t = e.tool
            it = QTreeWidgetItem([t.name, tr(model.TOOL_KINDS.get(t.kind, t.kind)), f'{t.diameter:g}',
                                  f'{t.angle:g}°' if t.angle else '', t.ref])
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            it.setCheckState(0, Qt.CheckState.Unchecked)
            it.setData(0, Qt.ItemDataRole.UserRole, i)
            parent_item.addChild(it)
            self.items.append(it)
        lay.addWidget(self.tree, 1)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def _filter(self, text: str) -> None:
        text = text.strip().lower()
        for it in self.items:
            hit = not text or any(text in it.text(c).lower() for c in range(5))
            it.setHidden(not hit)
            p = it.parent()
            while p is not None:
                if hit:
                    p.setHidden(False)
                    p.setExpanded(bool(text))
                p = p.parent()

    def check(self, indexes) -> None:
        for it in self.items:
            if it.data(0, Qt.ItemDataRole.UserRole) in indexes:
                it.setCheckState(0, Qt.CheckState.Checked)

    def chosen(self) -> list:
        return [self.entries[it.data(0, Qt.ItemDataRole.UserRole)] for it in self.items
                if it.checkState(0) == Qt.CheckState.Checked]


#: partage du panneau FAO (outils, opérations, parcours) retenu
SPLIT_KEY = 'fao/partage_panneau2'


class CamPanel(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        self.toolpaths: list = []
        lay = QVBoxLayout(self)
        lay.setContentsMargins(2, 2, 2, 2)
        row = QHBoxLayout()
        # le post-processeur se choisit dans les Options (FAO) : ici, son nom et le chemin pour le changer
        from .flow import ElideLabel
        self.post_label = ElideLabel('')
        self.post_label.setToolTip(tr('Post-processeur (machine) du dessin : il se choisit dans les Options, '
                                      'onglet FAO'))
        row.addWidget(self.post_label, 1)
        b = QPushButton(tr('Options…'))
        b.setToolTip(tr('Choisir le post-processeur (Options, onglet FAO)'))
        b.clicked.connect(lambda: self.win.options_dialog(page='FAO'))
        row.addWidget(b)
        self.post = QComboBox()
        self.post.setVisible(False)
        self.post.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.post.setMinimumContentsLength(8)
        self.post.currentIndexChanged.connect(self._post_changed)
        row.addWidget(self.post)
        b = QPushButton('…')
        b.setMaximumWidth(34)
        b.setToolTip(tr('Dossier des fiches machine : chaque fiche devient un post-processeur (plugin)'))
        b.clicked.connect(self.choose_machines)
        row.addWidget(b)
        self.machines_btn = b
        b.setVisible(False)                              # dossier des fiches machine : dans les Options aussi
        lay.addLayout(row)
        # laser à scanner (post Cielle) : champ de marquage, gravure en morceaux
        self.laser_row = QWidget()
        lr = QHBoxLayout(self.laser_row)
        lr.setContentsMargins(0, 0, 0, 0)
        lr.addWidget(QLabel(tr('Champ')))
        self.laser_field = QDoubleSpinBox()
        self.laser_field.setRange(10.0, 2000.0)
        self.laser_field.setDecimals(1)
        self.laser_field.setSuffix(' mm')
        self.laser_field.setToolTip(tr('Côté du champ de marquage du laser (110 mm : TAU, lentille de 160 mm)'))
        lr.addWidget(self.laser_field)
        self.laser_tiles = QCheckBox(tr('En morceaux'))
        self.laser_tiles.setToolTip(tr('Dessin plus grand que le champ : un travail par morceau, et les consignes '
                                       'de déplacement de la pièce entre deux morceaux'))
        lr.addWidget(self.laser_tiles)
        self.laser_marks = QCheckBox(tr('Raccords'))
        self.laser_marks.setToolTip(tr('Traits de raccord au milieu des frontières, pour contrôler le recalage'))
        lr.addWidget(self.laser_marks)
        lr.addStretch(1)
        for w in (self.laser_tiles, self.laser_marks):
            w.toggled.connect(lambda _on: self._laser_changed())
        self.laser_field.valueChanged.connect(lambda _v: self._laser_changed())
        lay.addWidget(self.laser_row)
        self._fill_posts()
        #: parcours de la palette (colonne de gauche, cam_palette) : clé d'action → ligne ; posé par la fenêtre
        self.palette_buttons: dict = {}
        # opérations et leurs parcours (et commandes), parcours sans opération, outils (repliés) : partage réglable,
        # retenu ; les opérations d'abord
        from PySide6.QtWidgets import QSplitter
        self.split = QSplitter(Qt.Orientation.Vertical)
        self.split.setChildrenCollapsible(False)
        # outils
        g = QGroupBox(tr('Outils d\'usinage'))
        gl = QVBoxLayout(g)
        self.tools = QTableWidget(0, 5)
        self.tools.setHorizontalHeaderLabels(['T', tr('Nom'), tr('Nature'), 'Ø', tr('Avance')])
        hh = self.tools.horizontalHeader()
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for c in (0, 2, 3, 4):                           # panneau étroit : colonnes à leur contenu, pas de défilement
            hh.setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)
        self.tools.verticalHeader().hide()
        self.tools.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tools.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tools.doubleClicked.connect(lambda _i: self.edit_tool())
        # tri : clic sur un titre (croissant, décroissant, puis l'ordre du document) ; retenu
        from .tool_filters import sortable
        hh.setToolTip(tr('Clic sur un titre : trier (croissant, décroissant, puis l’ordre du document)'))
        sortable(self.tools, lambda: self.refresh(), getattr(self.win, 'settings', None), self.TOOLS_SORT_KEY)
        # filtres : recherche (nom, référence, fabricant, Ø, T, dossier) et nature
        frow = QHBoxLayout()
        self.tools_filter = QLineEdit()
        self.tools_filter.setPlaceholderText(tr('Filtrer : nom, référence, Ø, T…'))
        self.tools_filter.setClearButtonEnabled(True)
        self.tools_filter.textChanged.connect(lambda _t: self.filter_tools())
        frow.addWidget(self.tools_filter, 1)
        self.tools_kind = QComboBox()
        self.tools_kind.addItem(tr('Toutes natures'), '')
        for k, lab in model.TOOL_KINDS.items():
            self.tools_kind.addItem(tr(lab).split(' (')[0], k)
        self.tools_kind.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.tools_kind.setMinimumContentsLength(6)
        self.tools_kind.currentIndexChanged.connect(lambda _i: self.filter_tools())
        frow.addWidget(self.tools_kind)
        gl.addLayout(frow)
        self._tools_by_id: dict = {}
        gl.addWidget(self.tools)
        gl.addLayout(self._buttons((('+', tr('Nouvel outil'), self.add_tool),
                                    ('📚', tr('Ajouter un outil de Mes outils (par dossier)'), self.library_menu),
                                    ('−', tr('Supprimer l\'outil'), self.remove_tool),
                                    ('✎', tr('Modifier l\'outil'), self.edit_tool),
                                    ('⋯', tr('Bibliothèque d\'outils : importer, exporter (JSON)'),
                                     self.tools_menu))))
        g.setTitle('')                                   # son titre : le bouton qui la déplie
        self.tools_group = g
        self.tools_box = QWidget()
        tb = QVBoxLayout(self.tools_box)
        tb.setContentsMargins(0, 0, 0, 0)
        tb.setSpacing(2)
        self.tools_toggle = QToolButton()
        self.tools_toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.tools_toggle.setCheckable(True)
        self.tools_toggle.setAutoRaise(True)
        self.tools_toggle.setText(tr("Outils d'usinage"))
        self.tools_toggle.setToolTip(tr('Déplier ou replier la liste des outils d’usinage du dessin'))
        self.tools_toggle.toggled.connect(lambda on: self.set_tools_open(on))
        tb.addWidget(self.tools_toggle)
        tb.addWidget(g, 1)
        # opérations
        g = QGroupBox(tr('Opérations (dans l\'ordre d\'usinage)'))
        gl = QVBoxLayout(g)
        self.ops = QTableWidget(0, 6)
        self.ops.setHorizontalHeaderLabels([tr('Opération'), tr('Stratégie'), tr('Outil'), tr('Prof.'), '', '⟳'])
        hh = self.ops.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        for c in (1, 3):
            hh.setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)
        # l'œil du parcours de l'opération, en tête de ligne (colonne logique 4 : les autres gardent leur rang)
        from .eye import eye_icon
        head = QTableWidgetItem(eye_icon(True), '')
        head.setToolTip(tr('Parcours de l’opération : affiché ou caché d’un clic sur son œil'))
        self.ops.setHorizontalHeaderItem(self.EYE_COL, head)
        hh.setSectionResizeMode(self.EYE_COL, QHeaderView.ResizeMode.Fixed)
        self.ops.setColumnWidth(self.EYE_COL, 28)
        hh.moveSection(self.EYE_COL, 0)
        # ⟳ juste après l'œil (colonne logique 5) : l'opération prend les formes sélectionnées (demande du 15/11)
        self.ops.horizontalHeaderItem(self.REFRESH_COL).setToolTip(tr(
            '⟳ : cette opération usine les formes sélectionnées (son parcours, s’il est calculé, est refait)'))
        hh.setSectionResizeMode(self.REFRESH_COL, QHeaderView.ResizeMode.Fixed)
        self.ops.setColumnWidth(self.REFRESH_COL, 28)
        hh.moveSection(hh.visualIndex(self.REFRESH_COL), 1)
        self.ops.cellClicked.connect(self._eye_clicked)
        self.ops.verticalHeader().hide()
        self.ops.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.ops.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.ops.doubleClicked.connect(lambda i: None if i.column() in (self.EYE_COL, self.REFRESH_COL) else
                                       self.edit_op())
        self.ops.itemChanged.connect(self._op_checked)
        self.ops.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.ops.customContextMenuRequested.connect(lambda pos: self.op_menu(pos))
        from PySide6.QtGui import QKeySequence, QShortcut
        for seq, slot in (('Ctrl+M', self.edit_op), (QKeySequence.StandardKey.Delete, self.remove_op)):
            sc = QShortcut(QKeySequence(seq), self.ops)
            sc.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            sc.activated.connect(slot)
        self.ops.installEventFilter(self)                # Ctrl+I et Ctrl+T sur la liste (TE) : voir `eventFilter`
        self.ops.setMinimumHeight(self.ops.verticalHeader().defaultSectionSize() * 6 + 28)   # six lignes au moins
        gl.addWidget(self.ops)
        gl.addLayout(self._buttons((('+', tr('Nouvelle opération'), self.add_op),
                                    ('−', tr('Supprimer l\'opération'), self.remove_op),
                                    ('✎', tr('Modifier l\'opération'), self.edit_op),
                                    ('↑', tr('Monter'), lambda: self.move_op(-1)),
                                    ('↓', tr('Descendre'), lambda: self.move_op(1)),
                                    ('◧', tr('Une gravure par couleur du dessin, avec le premier outil'),
                                     self.ops_from_colors),
                                    ('📖', tr('Ajouter depuis un catalogue : commandes de la documentation de la '
                                             'machine, opérations d\'un autre logiciel, programmes, fichier '
                                             'texte (catalogues des plugins)'),
                                     lambda: self.add_from_catalog()))))
        mid = QWidget()
        ml = QVBoxLayout(mid)
        ml.setContentsMargins(0, 0, 0, 0)
        ml.addWidget(g, 1)
        # le calcul porte sur les opérations choisies dans la liste (demande du 14/11) : le mode « seulement les objets
        # sélectionnés » n'est plus au panneau — sa liste, cachée, reste pour le code qui s'en sert ; toujours
        # « toutes les opérations » au lancement
        self.calc_mode = QComboBox(self)
        self.calc_mode.hide()
        self.calc_mode.addItem(tr('toutes les opérations'), 'couleur')
        self.calc_mode.addItem(tr('seulement les objets sélectionnés'), 'selection')
        self.calc_mode.currentIndexChanged.connect(
            lambda _i: self.win.settings.setValue('fao/mode_calcul', self.calc_mode.currentData()))
        row = QHBoxLayout()
        b = self.view3d_button = QPushButton(tr('Parcours 3D'))
        b.setToolTip(tr('Calculer les parcours et montrer en 3D, dans le calque « Trajectoires », à part du dessin, '
                        'ceux des opérations choisies dans la liste (aucune choisie : toutes les opérations actives) ; '
                        'les autres sont cachés, donc hors du programme'))
        b.clicked.connect(lambda _=False: self.show_chosen_3d())
        row.addWidget(b, 1)
        from PySide6.QtCore import QSize
        from .program_window import machine_icon
        b = self.program_button = QToolButton()          # le programme machine : dans sa fenêtre (`ui.program_window`)
        b.setObjectName('programButton')
        b.setIcon(machine_icon(64))
        b.setIconSize(QSize(30, 30))
        b.setText(tr('Programme'))
        b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        b.setStyleSheet('QToolButton#programButton { font-weight: bold; padding: 2px 10px; border: 2px solid #f76707; '
                        'border-radius: 6px; } QToolButton#programButton:hover { background: rgba(247, 103, 7, 60); }')
        b.setToolTip(tr('Le programme machine dans sa fenêtre : coloré, en direct ou à la demande, à côté du dessin ou '
                        'à sa place ; « Enregistrer… » l\'écrit dans un fichier'))
        b.clicked.connect(lambda _=False: self.win.show_program())
        row.addWidget(b)
        b = self.process_button = QPushButton(tr('Ajouter aux process'))   # à côté du programme (demande du 16/11)
        process_tip = tr('Les opérations du dessin et leurs outils, enregistrées dans « Mes process » (palette FAO) : à appliquer à une autre gravure, puis ⟳ sur chaque opération pour ses formes')
        b.setToolTip(process_tip)
        b.clicked.connect(lambda _=False: self.add_to_process())
        row.addWidget(b)
        for text, tip, slot in (('📂', tr('Ouvrir le dossier du dernier programme écrit'), self.open_program_folder),):
            b = QPushButton(text)
            b.setToolTip(tip)
            if len(text) <= 2:
                b.setMaximumWidth(34)
            b.clicked.connect(lambda _=False, s=slot: s())
            row.addWidget(b)
            if text == '📂':
                self.folder_btn = b
                b.setEnabled(False)                      # rien d'écrit encore
        ml.addLayout(row)
        self.last_program: pathlib.Path | None = None
        row = QHBoxLayout()
        self.rapids = QCheckBox(tr('Rapides'))
        from .options import value as _opt
        self.rapids.setChecked(_opt(win.settings, 'fao/rapides'))
        self.rapids.toggled.connect(self._show_rapids)
        row.addWidget(self.rapids)
        b = QPushButton(tr('Réglage…'))
        b.setToolTip(tr('Importer ou exporter le réglage FAO (outils et opérations, JSON)'))
        b.clicked.connect(self.setup_menu)
        row.addWidget(b)
        self.setup_btn = b
        from . import modes
        self.apply_mode(modes.current(win.settings))
        ml.addLayout(row)
        # parcours affichés : cocher = affiché et post-traité, dans cet ordre
        g = QGroupBox(tr('Parcours'))
        self.paths_group = g
        gl = QVBoxLayout(g)
        self.paths = QListWidget()
        self.paths.itemChanged.connect(self._path_checked)
        gl.addWidget(self.paths)
        gl.addLayout(self._buttons((('↑', tr('Monter'), lambda: self.move_path(-1)),
                                    ('↓', tr('Descendre'), lambda: self.move_path(1)),
                                    ('✕', tr('Retirer le parcours'), self.remove_path),
                                    ('⇄', tr('Inverser le sens du parcours'), self.reverse_path),
                                    ('⤓', tr('Enregistrer les parcours cochés au format TypeEdit (.000, .001…)'),
                                     self.export_typeedit))))
        self.split.addWidget(mid)
        self.split.addWidget(g)
        self.split.addWidget(self.tools_box)
        for i, k in enumerate((5, 2, 2)):               # la liste des opérations prend la plus grande part
            self.split.setStretchFactor(i, k)
        g.setVisible(False)                              # montrée quand un parcours n'a pas d'opération : `display`
        lay.addWidget(self.split, 1)
        st = win.settings.value(SPLIT_KEY, None)
        if st is not None:
            try:
                self.split.restoreState(st)
            except TypeError:                            # réglage illisible : partage par défaut
                pass
        self.split.splitterMoved.connect(lambda *_a: win.settings.setValue(SPLIT_KEY, self.split.saveState()))
        self.set_tools_open(win.settings.value(self.TOOLS_OPEN_KEY, 'false') in (True, 'true'), remember=False)
        from .fold_label import FoldArea, FoldLabel
        self.info = FoldLabel('')                        # le compte rendu : repliable en une ligne (demande du 15/11)
        self.info.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        # déplié : six lignes au plus, puis il défile — la liste des opérations garde la hauteur (demande du 16/11)
        self.info_area = FoldArea(self.info, 6)
        b = self.info_fold = QToolButton()               # ▾ replier, ▸ déplier ; caché quand il n'y a qu'une ligne
        b.setAutoRaise(True)
        b.setFixedSize(18, 18)
        b.setStyleSheet('QToolButton { padding: 0px; }')  # (le signe entier, quelle que soit la densité du thème)
        b.clicked.connect(lambda _=False: self.set_info_folded(not self.info.folded()))
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(2)
        row.addWidget(b, 0, Qt.AlignmentFlag.AlignTop)
        row.addWidget(self.info_area, 1)
        lay.addLayout(row)
        self.info.changed.connect(self._sync_info_fold)
        self.set_info_folded(win.settings.value(self.INFO_FOLDED_KEY, 'false') in (True, 'true'), remember=False)
        self._loading = False

    # --- accès ----------------------------------------------------------------------
    def _buttons(self, specs) -> QHBoxLayout:
        row = QHBoxLayout()
        for text, tip, slot in specs:
            b = QPushButton(text)
            b.setToolTip(tip)
            if len(text) <= 2:
                b.setMaximumWidth(34)
            b.clicked.connect(lambda _=False, s=slot: s())
            row.addWidget(b)
        row.addStretch(1)
        return row

    @property
    def doc(self):
        return self.win.canvas.doc

    def setup(self) -> model.CamSetup:
        s = model.setup_of(self.doc)
        if 'fao' not in self.doc.extra:                  # dessin sans réglage : le post-processeur des Options
            v = str(self.win.settings.value('fao/post', '') or '')
            if v:
                s.post = v
        return s

    def set_post(self, key: str) -> bool:
        """Post-processeur du dessin (choisi dans les Options) ; rend vrai s'il a changé."""
        s = self.setup()
        if not key or key == s.post:
            return False
        if self.post.findData(key) < 0:
            self._fill_posts()
        s.post = key
        self.save(s)
        return True

    def _surfaces(self, s: model.CamSetup) -> bool:
        """Surfaces posées : contenu qui suit la pièce placée autrement,
        opérations rattachées ou défaites ; rend vrai si le réglage ou une
        surface a changé (parcours déjà calculés à refaire)."""
        from ..core import surface2d
        moved = surface2d.follow(self.doc)
        if moved:
            self.win.canvas.invalidate()
        return bool(surface2d.sync(self.doc, s)) or bool(moved)

    def current_paths(self, dates: bool = True) -> list:
        """Parcours cochés à écrire, simuler, mettre sur la fiche — calculés,
        ou recalculés si le dessin a changé depuis : surface posée qui a suivi
        la pièce placée autrement (ici ou depuis le placement, la plaque, un
        corps posé à part), rattachements, dates du jour (`dates`). Ceux des
        opérations désactivées ou supprimées depuis le calcul n'en sont plus."""
        from ..core import surface2d
        s = self.setup()
        moved = self._surfaces(s)
        if moved:
            model.store(self.doc, s)
        now = surface2d.state(self.doc)
        was = self._memo('_surface_states')                  # celles des parcours de ce document
        changed = now != was if was is not None else bool(now)
        placed = self._memo('_placement_states')             # pièce 3D placée autrement depuis le calcul
        changed = changed or (placed is not None and placed != self._placement_state())
        inputs = self._memo('_inputs_states')                # objets, outils, opérations retouchés depuis
        changed = changed or self._inputs_changed(inputs, self._inputs_state())
        if moved or changed or (dates and self.refresh_dates()):
            had = bool(self.toolpaths)
            tps = self._recompute(dates)
            if (moved or changed) and had and tps:
                self.win.statusBar().showMessage(tr('Parcours recalculés : le dessin a changé depuis leur calcul '
                                                    '(objets, outils, pièce 3D placée autrement, surface posée, '
                                                    'rattachements)'), 8000)
            return self._writable(tps)
        return self._writable(self.checked_paths() or self.compute(dates=dates))

    def outdated(self) -> bool:
        """Parcours de la liste calculés avant un changement du dessin (pièce
        3D placée autrement, surface posée, session reprise, recalcul pas
        fait) : ceux que `current_paths` referait. Sans rien recalculer ni
        toucher au dessin (vue 3D)."""
        from ..core import surface2d
        was = self._memo('_surface_states')
        now = surface2d.state(self.doc)
        if (now != was) if was is not None else bool(now):
            return True
        placed = self._memo('_placement_states')
        if placed is not None and placed != self._placement_state():
            return True
        return self._inputs_changed(self._memo('_inputs_states'), self._inputs_state(), new=False)

    def _ids(self) -> set:
        """Identifiants des objets du document, groupes compris."""
        out = set()

        def walk(items):
            for it in items:
                out.add(it.id)
                walk(getattr(it, 'children', ()))
        for L in self.doc.layers:
            walk(L.items)
        return out

    #: ce que le panneau sait des parcours d'un document (gardé avec la session)
    MEMOS = ('_only', '_computed', '_whole', '_surface_states', '_placement_states', '_inputs_states')

    def memo_of(self, doc) -> dict:
        """Ce que le panneau sait des parcours de `doc`, en JSON (session) ;
        empreinte du dessin et des outils : 'ok' (parcours à jour) ou '?'
        (le dessin relu ne donnerait pas la même)."""
        out = {}
        for name in self.MEMOS:
            e = (getattr(self, name, None) or {}).get(id(doc))
            if e is not None and e[0]() is doc:
                out[name] = sorted(e[1]) if isinstance(e[1], set) else e[1]
                if name == '_inputs_states':
                    out[name] = '?' if self._inputs_changed(e[1], self._inputs_state(doc)) else 'ok'
        return out

    def restore_memo(self, d) -> None:
        """Ce que `memo_of` a gardé, remis pour le document affiché (session
        reprise) ; rien de gardé (session d'avant) : `from_session`."""
        if not isinstance(d, dict):
            self.from_session()
            return
        for name in self.MEMOS:
            if name not in d:
                continue
            v = d[name]
            if name in ('_computed', '_whole'):
                v = set(v or ())
            elif name == '_only':
                v = tuple(v) if v else None
            elif name == '_surface_states' and v is not None:
                v = tuple(tuple(x) if isinstance(x, list) else x for x in v)
            elif name == '_inputs_states':
                v = self._inputs_state() if v == 'ok' else '?'      # à jour : l'empreinte du dessin relu
            self._remember(name, v)
        if '_inputs_states' not in d and '_computed' in d:          # session d'une version d'avant : dessin
            self._remember('_inputs_states', '?')                   # retouché depuis le calcul ? refaits

    def from_session(self) -> None:
        """Parcours repris d'une session sans ce qu'on savait de leur calcul
        (mode, objets, sens) : « Calculer » demandé avant la première
        écriture."""
        self._remember('_only', ('session', None))
        self._remember('_placement_states', '')
        self._remember('_surface_states', ('?',))
        self._remember('_inputs_states', '?')

    def _stale(self, old, msg) -> list:
        """Recalcul pas fait (annulé, objets disparus) : la liste d'avant
        remise, le recalcul retenté au prochain appel ; rien à écrire."""
        self._remember('_placement_states', '')              # empreintes qui ne correspondent à rien
        self._remember('_surface_states', ('?',))
        self._remember('_inputs_states', '?')
        self.display(old)
        self.info.setText(msg)
        self.win.statusBar().showMessage(msg, 10000)
        return []

    def _whole_again(self, tps, whole, show: bool = True):
        """`tps` avec les parcours des opérations `whole` refaits sur tous
        leurs objets, comme depuis leur formulaire ; None si annulé ; `show` :
        la liste affichée aussi."""
        from .progress import Cancelled, run
        s = self.setup()
        out = list(tps)
        for o in s.operations:
            if o.id not in whole or not o.enabled:
                continue
            try:
                tp = run(self.win, tr('Calcul du parcours'), strategies.compute, self.doc, s, o)
            except Cancelled:
                return None
            at = [i for i, t in enumerate(out) if t.op_id == o.id]
            for i in reversed(at[1:]):
                del out[i]
            if at:
                out[at[0]] = tp
            else:
                out.append(tp)
        strategies.apply_faced_all(s, out)
        self._remember('_whole', set(whole))
        if show:
            self.display(out)
        return out

    def _inputs_state(self, doc=None) -> tuple:
        """Empreinte du reste de ce que lit le calcul : (objets et calques du
        dessin, plaque, données du dessin ; réglage FAO sans opérations,
        outils ni post-processeur — qui n'écrit que le programme ;
        {opération active : ses réglages et ses outils}). Elle change quand un
        objet est déplacé, retouché, un outil ou une opération modifiés (nom
        et activation exceptés) : les parcours calculés avant sont à refaire
        (une opération seule : elle seule, mémoire des parcours). Lue sur le
        réglage écrit (identifiants tels quels) ; illisible : jamais la même."""
        doc = self.doc if doc is None else doc
        fao = doc.extra.get('fao') if isinstance(doc.extra, dict) else None
        fao = fao if isinstance(fao, dict) else {}
        tools = {str(t.get('id')): t for t in fao.get('tools') or [] if isinstance(t, dict)}
        rest = {k: v for k, v in fao.items() if k not in ('operations', 'tools', 'post', 'post_options', 'arc_fit')}
        ops, before = {}, []
        for d in fao.get('operations') or []:
            if isinstance(d, dict) and d.get('enabled', True) and d.get('instruction') != 'externe':
                mine = {k: v for k, v in d.items() if k not in ('enabled', 'name', 'restart_from', 'restart_to', 'restart_sig')}
                own = strategies._digest((mine, tools.get(str(d.get('tool_id'))), tools.get(str(d.get('ref_tool_id')))))
                # poche, seulement le reste : les opérations d'avant comptent aussi (retouchées, ou l'ordre changé)
                ops[str(d.get('id', ''))] = strategies._digest((own, before)) if d.get('rest_previous') and \
                    own is not None and None not in before else own
                before = before + [own]
        state = (strategies._doc_signature(doc), strategies._digest(rest), ops)
        if state[0] is None or state[1] is None or None in ops.values():
            return ('?', next(_UNIQUE))
        return state

    @staticmethod
    def _inputs_changed(was, now, skip='', new: bool = True) -> bool:
        """L'empreinte `now` n'est plus celle du calcul (`was`) : dessin,
        réglage, outils, ou une opération (sauf `skip` : un identifiant ou
        plusieurs) retouchés — `new` : une opération active ajoutée (ou
        réactivée) depuis compte aussi. Rien de gardé (`was` None) : non."""
        if was is None:
            return False
        if not (isinstance(was, tuple) and len(was) == 3 and len(now) == 3) or was[:2] != now[:2]:
            return True
        skips = {skip} if isinstance(skip, str) else set(skip)
        return any(k not in skips and (new or k in was[2]) and was[2].get(k) != v for k, v in now[2].items())

    def inputs_current(self) -> bool:
        """Parcours à jour du dessin, des outils, des opérations (rien de
        retouché ni d'ajouté depuis leur calcul) ?"""
        m = self._memo('_inputs_states')
        return m is not None and not self._inputs_changed(m, self._inputs_state())

    def keep_current(self) -> None:
        """Dessin changé sans effet sur les parcours (traits de « Parcours en
        dessin », pas usinés) : ceux qui étaient à jour le restent."""
        self._remember('_inputs_states', self._inputs_state())

    def _placement_state(self) -> str:
        """Empreinte du placement de la pièce 3D et des corps posés à part :
        elle change quand la pièce suit la plaque ou est replacée — les
        parcours calculés avant (opérations 3D, contours de sa vue) sont
        alors à refaire."""
        import json
        from ..core import placement3d as P3
        main, bodies = self.doc.extra.get(P3.KEY), self.doc.extra.get(P3.KEY_BODIES)
        modes = {d.get('mode') for d in [main, *(bodies or {}).values()] if isinstance(d, dict)}
        p = self.doc.plate                                   # centré ou calé dans le coin : placé au calcul
        box = (p.x, p.y, p.width, p.height) if p is not None and modes & {'centre', 'coin'} else None
        return json.dumps([main, bodies, box], sort_keys=True, default=str)

    def _memo(self, name: str):
        """Ce que le panneau garde pour le document affiché (`name`) ; None
        si c'était pour un autre (onglet, document refermé dont l'adresse
        resservirait)."""
        e = (getattr(self, name, None) or {}).get(id(self.doc))
        return e[1] if e is not None and e[0]() is self.doc else None

    def _remember(self, name: str, value) -> None:
        import weakref
        d = {k: e for k, e in (getattr(self, name, None) or {}).items() if e[0]() is not None}
        d[id(self.doc)] = (weakref.ref(self.doc), value)
        setattr(self, name, d)

    def _writable(self, tps) -> list:
        """Parcours qui vont au programme : ceux des opérations actives — une
        opération désactivée ou supprimée depuis le calcul n'y va plus — et
        ceux sans opération (parcours TypeEdit, programme relu)."""
        from ..cam import strategies as _strategies
        s = self.setup()
        ops = {o.id: o for o in s.operations}
        tps = list(tps)
        # les liaisons basses refaites pour CETTE liste, telle qu'elle est maintenant : une opération décochée,
        # retirée ou déplacée depuis le calcul n'abaisse plus rien dans ce qui est écrit
        _strategies.apply_faced_all(s, tps)
        return [tp for tp in tps if getattr(tp, 'shown', True)
                and (not tp.op_id or (tp.op_id in ops and ops[tp.op_id].enabled))]

    def _recompute(self, dates: bool = True) -> list:
        """Tout recalculé, la liste gardée comme on l'avait laissée : ordre
        changé à la main, parcours décochés ou retournés (même opération, même
        rang), parcours sans opération (TypeEdit, programme relu) ; un parcours
        retiré de la liste revient décoché (une opération ajoutée depuis le
        calcul, cochée), juste avant le suivant gardé."""
        from ..cam.edit import reversed_toolpath
        old = list(self.toolpaths)
        was_computed = self._memo('_computed')
        computed = set(was_computed or ())
        before: dict = {}
        seen: dict = {}
        for i, tp in enumerate(old):
            if tp.op_id:
                k = seen[tp.op_id] = seen.get(tp.op_id, -1) + 1
                before[(tp.op_id, k)] = (i, tp)
        last, whole = self._memo('_only'), set(self._memo('_whole') or ())
        active = {o.id for o in self.setup().operations if o.enabled}
        mine = {t.op_id for t in old if t.op_id in active}
        if last is not None and last[0] == 'session':        # session reprise sans ce qu'on savait du calcul
            if mine and not mine <= whole:
                return self._stale(old, tr('Parcours d\'une session reprise : « Calculer » pour les refaire (mode, '
                                           'objets et sens du calcul d\'alors inconnus)'))
            last = None
        if last is None and whole and mine and mine <= whole:   # rien de calculé en entier : la liste vient toute
            if dates:                                        # des formulaires, ses opérations seules refaites
                self.refresh_dates()
            tps = self._whole_again([t for t in old if t.op_id], whole, show=False)
            if tps is not None:
                from ..core import surface2d
                self._remember('_surface_states', surface2d.state(self.doc))
                self._remember('_placement_states', self._placement_state())
                self._remember('_inputs_states', self._inputs_state())
        elif last is None and mine and self.selection_mode():   # liste d'une session reprise : ses objets ?
            return self._stale(old, tr('Parcours d\'une session reprise : sélectionner les objets à usiner puis '
                                       '« Calculer »'))
        else:                                                # le dernier calcul rejoué, quel que soit le mode
            keep = list(last[1]) if last is not None and last[0] == 'selection' else None
            if keep is not None and not set(keep) <= self._ids():
                return self._stale(old, tr('Objets du dernier calcul remplacés ou supprimés (pièce replacée, '
                                           'groupe défait…) : les resélectionner puis « Calculer »'))
            tps = self.compute(dates=dates, only=keep, every=last is not None and last[0] == 'couleur')
            if not tps and getattr(self, '_cancelled', False):
                tps = None                                   # 3. annulé : rien d'écrit
            if keep is not None and whole and tps:
                tps = self._whole_again(tps, whole)
        if tps is None:                                      # annulé : ce qu'on savait de la liste remis
            self._remember('_whole', whole)
            self._remember('_computed', was_computed)
            return self._stale(old, tr('Calcul annulé'))
        if not old:
            return tps
        if not tps:                                          # rien de refait : les parcours sans opération restent
            return [t for t in old if not t.op_id]
        rank, hits = {}, []
        for tp in tps:
            k = rank[tp.op_id] = rank.get(tp.op_id, -1) + 1
            hits.append(before.get((tp.op_id, k)))
        out, nxt = [], len(old)
        for j in range(len(tps) - 1, -1, -1):            # depuis la fin : une nouvelle va avant la suivante gardée
            tp, hit = tps[j], hits[j]
            if hit is None:                              # retiré de la liste, ou opération nouvelle
                tp.shown = tp.op_id not in computed
                out.append(((nxt, -1, j), tp))
                continue
            i, was = hit
            tp.shown = getattr(was, 'shown', True)
            if getattr(was, 'reversed', False):
                tp = reversed_toolpath(tp)
                tp.reversed = True
            out.append(((i, 0, 0), tp))
            nxt = i
        out += [((i, 0, 0), tp) for i, tp in enumerate(old) if not tp.op_id]
        tps = [tp for _k, tp in sorted(out, key=lambda e: e[0])]
        self.display(tps)
        return tps

    def save(self, s: model.CamSetup) -> None:
        self._surfaces(s)                               # objets d'une surface posée : sa prise, sa cote
        from ..cam import mill3d
        mill3d.bind_volumes(self.doc, s)                # volume du dessin usiné seul : son objet gardé
        model.store(self.doc, s)
        self.win.modified = True
        self.refresh()
        self._program_changed()

    def _program_changed(self) -> None:
        """La fenêtre du programme machine prévenue : opérations, machine, parcours montrés ont changé."""
        fn = getattr(self.win, 'program_changed', None)
        if fn is not None:
            fn()

    def program_preview(self, recompute: bool = False) -> dict:
        """Le programme machine des parcours montrés, sans rien écrire ni rien demander : {'files': [(nom, texte)],
        'warnings', 'key' (post-processeur), 'extension', 'note' (ce qui manque)} — les mêmes fichiers que l'écriture
        (un programme par groupe selon le réglage, le dossier des programmes), dans l'encodage du fichier (un
        caractère qu'il n'a pas : « ? », comme à l'écriture). `recompute` : les parcours refaits d'abord si le dessin a
        changé depuis leur calcul (sans toucher aux dates du dessin) ; sinon tels qu'ils sont, et une note le dit
        s'ils sont dépassés."""
        from ..cam import post
        out = {'files': [], 'warnings': [], 'key': '', 'extension': '', 'note': '', 'sections': []}
        s = self.setup()
        available = post.posts(self.machines_dir())
        key = s.post if s.post in available or s.post.startswith('mah:') else next(iter(available), '')
        out['key'] = key
        if not key:
            out['note'] = tr('Aucun post-processeur : ils viennent des plugins de l\'atelier')
            return out
        if recompute:
            tps = self.current_paths(dates=False)
        else:
            tps = self._writable(self.checked_paths())
            if tps and self.outdated():
                out['note'] = tr('Le dessin a changé depuis le calcul : « Mettre à jour » refait les parcours')
        mine = post.doc_operations(key, self.doc)          # opérations propres à la machine (d'un plugin)
        if not tps and not mine:
            out['note'] = tr('Aucun parcours montré : « Mettre à jour » les calcule')
            return out
        if not tps:
            out['note'] = tr('Aucun parcours montré : le programme ne porte que les opérations propres à la machine')
        src = self.win.path or self.doc.source_path
        title = pathlib.Path(src).stem if src else 'VectorDrive'
        box = self._stock_box()
        origin = self.program_origin()
        how = getattr(s, 'output_orient', 'normal')
        files, warnings, ext, sections = [], [], '', []
        mine_doc = self.doc
        if mine and box is not None and how != 'normal':
            mine_doc = None                              # elles ne suivent pas l'orientation de sortie
            warnings.append(self._orient_note())
        try:
            if box is not None:
                tps, origin, box = post.oriented(tps, how, (box[0], box[1], box[3], box[4]), origin, box)
            groups = post.program_groups(tps, s.program_group, self._plan_of_path)
            for gi, (suffix, part) in enumerate(groups):
                stem = f'{title}_{suffix}' if suffix else title
                res = post.run(key, part, s, title=title, stem=stem, box_mm=box, out_dir=str(self.program_dir()),
                               origin=origin, doc=mine_doc if gi == len(groups) - 1 else None, preview=True)
                ext = ext or res.extension
                warnings += list(res.warnings)
                for sec in getattr(res, 'sections', None) or ():     # les plages données par le post : au rang de
                    try:                                             # ses fichiers parmi tous ceux du programme
                        d = {'file': len(files) + int(sec.get('file', 0) or 0), 'first': int(sec['first']),
                             'last': int(sec['last']), 'kind': str(sec.get('kind') or 'parcours'),
                             'label': str(sec.get('label') or ''), 'op_id': '', 'name': ''}
                    except (AttributeError, KeyError, TypeError, ValueError):
                        continue                                     # une plage mal formée : laissée de côté
                    k = sec.get('path')
                    if isinstance(k, int) and 0 <= k < len(part):
                        d['op_id'], d['name'] = part[k].op_id, part[k].name
                    sections.append(d)
                for name, text in (list(res.files) or ([(stem + res.extension, res.text)] if res.text else [])):
                    files.append((name, text.encode(res.encoding, 'replace').decode(res.encoding)))
        except Exception as ex:                          # noqa: BLE001 — fiche machine absente, export refusé…
            out['note'] = tr('Programme impossible : {0}').format(ex)
            return out
        out.update(files=files, warnings=warnings, extension=ext, sections=sections)
        from ..plugins import REGISTRY
        if not files:
            out['note'] = tr('Aucun programme écrit.')
        elif REGISTRY.post_exports.get(key) or REGISTRY.post_exports.get(post.family(key)):
            out['note'] = (out['note'] + ' ; ' if out['note'] else '') + tr(
                'cette machine a son propre export : « Enregistrer… » l\'ouvre')
        return out

    # --- affichage --------------------------------------------------------------------
    def refresh(self) -> None:
        self._loading = True
        s = self.setup()
        from ..cam import external
        changed, gone = external.sync(s, self.doc, s.post)   # opérations des plugins (question 48 : liste unique)
        if changed:
            model.store(self.doc, s)                     # pas « modifié » : rien que l'utilisateur ait fait
        stale = [t for t in getattr(self, 'toolpaths', []) if t.op_id in set(gone)]
        self.post.blockSignals(True)
        from ..cam import machines as MC
        known = MC.of_post(s.post)                       # la machine du post-processeur, si un plugin la déclare
        if self.post.findData(s.post) < 0 and (s.post.startswith('mah:') or known is not None):
            self.post.addItem(tr(known.label) if known is not None
                              else tr('Fiche {0}').format(pathlib.Path(s.post[4:]).name), s.post)
        self.post.setCurrentIndex(max(0, self.post.findData(s.post)))
        self.post.blockSignals(False)
        self.post_label.setText(tr('Machine : {0}').format(
            (tr(known.label) if known is not None else self.post.currentText()) or '—'))
        self.laser_row.setVisible(known.kind == 'laser' if known is not None else s.post == 'cielle')
        machine_changed = getattr(self.win, 'machine_changed', None)
        if machine_changed is not None:
            machine_changed(s.post)
        self.laser_field.setValue(s.laser_field)
        self.laser_tiles.setChecked(s.laser_tiles)
        self.laser_marks.setChecked(s.laser_marks)
        self.laser_marks.setEnabled(s.laser_tiles)
        from ..cam import toollib
        from PySide6.QtGui import QBrush, QColor
        from .tool_filters import cell as sort_cell, tool_icon
        r0 = self._row(self.tools)
        it0 = self.tools.item(r0, 0) if r0 >= 0 else None
        keep = it0.data(Qt.ItemDataRole.UserRole) if it0 is not None else None   # l'outil choisi, par son id
        self.tools.setSortingEnabled(False)              # remplie dans l'ordre du document, triée ensuite
        self.tools.setRowCount(len(s.tools))
        self.tools_toggle.setText('{0} ({1})'.format(tr("Outils d'usinage"), len(s.tools)))
        self._tools_by_id = {t.id: t for t in s.tools}
        tips = {}
        mine = self.library_tools() if s.tools else []
        for r, t in enumerate(s.tools):
            tip = toollib.summary(t)
            hit = toollib.find_match(t, mine)              # reconnu dans Mes outils ?
            tip += '\n' + (tr('Dans Mes outils : {0}').format(toollib.folder_of(hit)) if hit is not None
                           else tr('Absent de Mes outils'))
            other = not toollib.for_machine(t, s.post)       # outil réservé à d'autres machines
            if other:
                tip += '\n' + tr('⚠ Réservé à d\'autres machines que celle choisie')
            tips[t.id] = (tip, other)
            kind = tr(model.TOOL_KINDS.get(t.kind, t.kind))
            for c, (v, k) in enumerate(((str(t.number), t.number), (t.name, t.name), (kind, kind),
                                        (f'{t.diameter:g}', float(t.diameter)), (f'{t.feed:g}', float(t.feed)))):
                cell = sort_cell(v, k)
                cell.setToolTip(tip)
                if c == 0:
                    cell.setData(Qt.ItemDataRole.UserRole, t.id)      # trié ou filtré : l'outil par son id
                if c == 1:
                    cell.setIcon(tool_icon(t, 12, 22))
                if other:
                    cell.setForeground(QBrush(QColor('#d9480f')))
                self.tools.setItem(r, c, cell)
        self.tools.setSortingEnabled(True)
        self.filter_tools()
        if keep is not None:                             # trié : le même outil reste choisi, pas la même ligne
            rows = [r for r in range(self.tools.rowCount()) if self.tools.item(r, 0) is not None
                    and self.tools.item(r, 0).data(Qt.ItemDataRole.UserRole) == keep]
            if rows:
                self._select_row(self.tools, rows[0])
            else:
                self.tools.clearSelection()              # outil retiré : rien de choisi
        self.ops.setRowCount(len(s.operations))
        for r, o in enumerate(s.operations):
            t = s.tool(o.tool_id)
            it = QTableWidgetItem(('↳ ' if o.link_previous else '') + self.op_label(o)
                                  + (tr(' ({0} obj.)').format(len(o.items)) if o.items else ''))
            if o.link_previous:                          # liée : rattachée à l'opération d'avant
                head = next((p for p in reversed(s.operations[:r]) if p.enabled), None)
                it.setToolTip(tr('Liée à « {0} » : ne reprend que la matière laissée par les opérations '
                                 'd\'avant').format(self.op_label(head)) if head is not None else
                              tr('Lier au parcours précédent : aucune opération avant celle-ci'))
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            it.setCheckState(Qt.CheckState.Checked if o.enabled else Qt.CheckState.Unchecked)
            if o.sources:
                it.setIcon(swatch(self.doc.tool_color(o.sources[0])))
            self.ops.setItem(r, 0, it)
            cols = (tr(model.op_kinds().get(o.kind, o.kind)), toollib.short_label(t) if t else '—', f'{o.depth:g}')
            if external.is_external(o):                  # opération d'un plugin : ce qu'il en dit
                cols = external.columns(o)
                cols = (tr(cols[0]),) + cols[1:]
                it.setToolTip(o.params.get('tip') or tr('Opération de {0} : double clic pour la régler').format(cols[0]))
            for c, v in enumerate(cols, start=1):
                cell = QTableWidgetItem(v)
                if c == 2 and t is not None:
                    cell.setIcon(tool_icon(t, 12, 22))
                    cell.setToolTip(tips.get(t.id, ('', False))[0])
                    if tips.get(t.id, ('', False))[1]:
                        cell.setForeground(QBrush(QColor('#d9480f')))
                self.ops.setItem(r, c, cell)
        self._fill_loose_rows()
        self._sync_eyes()
        self._sync_retarget()
        self._loading = False
        self._fill_ops3d()
        paths = self._external_paths(s, stale)           # les parcours des opérations de plugin suivent la liste
        if paths is not None:
            self.display(paths)

    def _external_paths(self, s, stale) -> list | None:
        """Les parcours des opérations de plugin suivent la liste (question 48) : ceux d'une opération retirée
        (`stale`) ou défaite (Ctrl+Z) ôtés, le libellé des autres à jour ; une opération de plugin cochée, écrite par
        cette machine, qui n'a pas de parcours en reçoit un tout de suite, à sa place, dès qu'il y a des parcours —
        rien à calculer : c'est un appel que son post-processeur écrit ; sa place dans la liste vaut donc dans le
        programme sans « Calculer » (comptée calculée, comme par son formulaire). None : rien à changer."""
        from ..cam import external
        ops = {o.id: o for o in s.operations}
        tps, changed = [], bool(stale)
        for t in getattr(self, 'toolpaths', []):
            if t in stale:
                continue
            cyc = t.cycles[0] if len(getattr(t, 'cycles', None) or []) == 1 else None
            if isinstance(cyc, dict) and cyc.get('kind') == 'instruction' and cyc.get('name') == external.EXTERNAL:
                o = ops.get(t.op_id)
                if o is None or not external.is_external(o):
                    changed = True                       # son opération n'est plus là (Ctrl+Z d'un ajout)
                    continue
                if cyc.get('params') != o.params or t.name != o.name:
                    cyc['params'] = dict(o.params)       # renommée chez le plugin : le programme et la liste suivent
                    t.name = o.name
                    changed = True
            tps.append(t)
        added = set()
        if tps:
            have = {t.op_id for t in tps}
            order = {o.id: i for i, o in enumerate(s.operations)}
            for o in s.operations:
                if external.is_external(o) and o.enabled and o.id not in have and external.active(o, s.post):
                    tp = strategies.compute(self.doc, s, o)
                    me = order[o.id]                     # juste avant le parcours de l'opération suivante
                    nxt = next((i for i, t in enumerate(tps) if order.get(t.op_id, -1) > me), None)
                    tps.insert(len(tps) if nxt is None else nxt, tp)
                    added.add(o.id)
        if added:                                        # calculées, comme par leur formulaire : pas de recalcul
            done = self._memo('_computed')               # ni de « session reprise » pour elles
            if done is not None:
                self._remember('_computed', set(done) | added)
            self._remember('_whole', set(self._memo('_whole') or ()) | added)
            changed = True
        return tps if changed else None

    # --- opérations et parcours dans un seul tableau : l'œil de la ligne ----------------------
    #: colonne de l'œil dans la liste des opérations (logique : la dernière ; montrée en tête de ligne)
    EYE_COL = 4
    #: colonne ⟳ (logique : après l'œil ; montrée juste après lui) : l'opération prend les formes sélectionnées
    REFRESH_COL = 5
    #: liste des outils dépliée (retenu) ; repliée d'office : la hauteur du panneau va aux opérations
    TOOLS_OPEN_KEY = 'fao/outils_deplies'
    #: le compte rendu du bas du panneau replié en une ligne (retenu)
    INFO_FOLDED_KEY = 'fao/compte_rendu_replie'

    def set_info_folded(self, on: bool, remember: bool = True) -> None:
        """Le compte rendu du bas du panneau (une ligne par parcours, avertissements, temps estimé) replié en une
        ligne — « ⚠ n · Temps estimé… », le texte entier en bulle —, ou déplié ; retenu."""
        self.info.set_folded(on)
        if remember:
            self.win.settings.setValue(self.INFO_FOLDED_KEY, bool(on))
        self._sync_info_fold()

    def _sync_info_fold(self) -> None:
        b = self.info_fold
        folded = self.info.folded()
        b.setVisible(self.info.foldable())               # une seule ligne : rien à replier
        b.setText('▸' if folded else '▾')
        b.setToolTip(tr('Déplier ce texte') if folded else tr('Replier ce texte en une ligne'))

    def op_paths(self, r: int, ops=None) -> list:
        """Rangs, dans les parcours, de ceux de l'opération de la ligne `r` (`ops` : les opérations, déjà lues)."""
        ops = self.setup().operations if ops is None else ops
        if r >= len(ops):                                # une ligne de parcours sans opération (réponse 13 du 14/11)
            k, loose = r - len(ops), getattr(self, '_loose', [])
            return [loose[k]] if k < len(loose) and loose[k] < len(getattr(self, 'toolpaths', [])) else []
        if r < 0:
            return []
        return [i for i, tp in enumerate(self.toolpaths) if tp.op_id == ops[r].id]

    def _sync_eyes(self) -> None:
        """L'œil de chaque opération : son parcours calculé montré (œil ouvert, à la couleur du tracé), caché (œil
        barré), ou pas encore calculé (rien). La donnée de la case : True, False ou None."""
        from PySide6.QtGui import QIcon
        from .eye import eye_icon
        table = getattr(self, 'ops', None)
        if table is None:
            return
        colors = path_colors()
        role = Qt.ItemDataRole.UserRole
        ops = self.setup().operations if self.toolpaths else []   # lu une fois (et non une fois par ligne)
        by_op: dict = {}
        for i, tp in enumerate(self.toolpaths):
            by_op.setdefault(tp.op_id, []).append(i)
        for r in range(table.rowCount()):
            cell = table.item(r, self.EYE_COL)
            if cell is None:
                cell = QTableWidgetItem()
                cell.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                table.setItem(r, self.EYE_COL, cell)
            at = by_op.get(ops[r].id, []) if r < len(ops) else self.op_paths(r, ops)
            if not at:
                cell.setIcon(QIcon())
                cell.setData(role, None)
                cell.setToolTip(tr('Pas encore de parcours : « Calculer »'))
                continue
            on = any(getattr(self.toolpaths[i], 'shown', True) for i in at)
            cell.setIcon(eye_icon(on, colors[at[0] % len(colors)]))
            cell.setData(role, on)
            cell.setToolTip(tr('Parcours affiché — cliquez pour le cacher') if on else
                            tr('Parcours caché — cliquez pour l’afficher'))

    def _fill_loose_rows(self) -> None:
        """Réponse 13 du 14/11 : les parcours sans opération (programme relu, parcours TypeEdit, parcours d'une
        opération retirée) sont des lignes du tableau des opérations, après elles — en italique, sans case (rien à
        activer : leur œil les montre ou les cache, comme une opération). `_n_ops`, `_loose` : le nombre de lignes
        d'opérations et, ligne après ligne, le rang de ces parcours."""
        from PySide6.QtGui import QBrush

        from ..cam import toollib
        table = getattr(self, 'ops', None)
        if table is None:
            return
        s = self.setup()
        known = {o.id for o in s.operations}
        self._n_ops = n = len(s.operations)
        paths = getattr(self, 'toolpaths', [])
        self._loose = [i for i, tp in enumerate(paths) if not (tp.op_id and tp.op_id in known)]
        was, self._loading = getattr(self, '_loading', False), True
        table.setRowCount(n + len(self._loose))
        font = table.font()
        font.setItalic(True)
        grey = QBrush(QColor('#495057'))
        colors = path_colors()
        for k, i in enumerate(self._loose):
            tp = paths[i]
            what = (tr('Parcours TypeEdit') if tp.source == 'typeedit' else
                    tr('Programme relu') if tp.source == 'nc' else tr('Parcours sans opération'))
            tool = s.tool(tp.tool_id) if tp.tool_id else None
            zs = [m.z for m in tp.moves if m.kind != 'rapid']
            cells = ((tp.name or '—'), what, toollib.short_label(tool) if tool is not None else '—',
                     f'{-min(zs):g}' if zs and min(zs) < 0 else '—')
            for c, v in enumerate(cells):
                cell = QTableWidgetItem(v)
                cell.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                cell.setFont(font)
                cell.setForeground(grey)
                cell.setToolTip(tr('{0} : pas d’opération. Double clic : en faire une opération ; Suppr : le '
                                   'retirer').format(what))
                if c == 0:
                    cell.setIcon(swatch(colors[i % len(colors)]))
                table.setItem(n + k, c, cell)
        self._loading = was

    def _eye_clicked(self, r: int, c: int) -> None:
        if c == self.EYE_COL:
            self.toggle_op_paths(r)
        elif c == self.REFRESH_COL:
            self.retarget_op(r)

    def _sync_retarget(self) -> None:
        """La case ⟳ de chaque ligne d'opération (les parcours sans opération n'en ont pas)."""
        table = getattr(self, 'ops', None)
        if table is None:
            return
        n = getattr(self, '_n_ops', len(self.setup().operations))
        tip = tr('⟳ : cette opération usine les formes sélectionnées (son parcours, s’il est calculé, est refait)')
        for r in range(table.rowCount()):
            cell = QTableWidgetItem('⟳' if r < n else '')
            cell.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            cell.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if r < n:
                cell.setToolTip(tip)
            table.setItem(r, self.REFRESH_COL, cell)

    def retarget_op(self, r: int, items=None) -> bool:
        """⟳ (demande du 15/11, 23 h 30) : l'opération de la ligne `r` usine désormais les formes sélectionnées (`items` :
        leurs identifiants) — un process repris sur une autre gravure, adapté opération par opération. Son parcours,
        s'il était calculé, est refait. False sans sélection (dit dans la barre d'état)."""
        s = self.setup()
        if not 0 <= r < len(s.operations):
            return False
        from ..cam import external
        if external.is_external(s.operations[r]):        # opération d'un plugin : il reprend lui-même les formes
            if not external.active(s.operations[r], s.post):
                self.win.statusBar().showMessage(tr('⟳ : opération d’un plugin absent, ou d’une autre machine'), 8000)
                return False
            o = s.operations[r]
            ids = [it.id for it in self._selected()] if items is None else list(items)
            done = bool(external.call(o, 'reload', self.win, external.ref_of(o), ids, default=False))
            if done:
                self.refresh()
            else:
                self.win.statusBar().showMessage(tr('⟳ : « {0} » ne reprend pas de formes ici').format(
                    self.op_label(o)), 8000)
            return done
        if items is None:
            items = [it.id for it in self._selected()]
        if not items:
            msg = tr('⟳ : sélectionnez d’abord les formes à usiner par cette opération')
            self.info.setText(msg)
            self.win.statusBar().showMessage(msg, 8000)
            return False
        op = s.operations[r]
        self.win.push_undo(tr('Formes de l’opération'), with_cam=True)
        op.items, op.sources = list(items), []
        self.save(s)
        if any(tp.op_id == op.id for tp in self.toolpaths):
            self.compute_op(op)
        self.info.setText(tr('« {0} » : {1} forme(s) sélectionnée(s)').format(self.op_label(op), len(items)))
        return True

    def toggle_op_paths(self, r: int, on: bool | None = None):
        """L'œil de l'opération de la ligne `r` : ses parcours calculés montrés ou cachés (dessin, durée, vue 3D,
        programme écrit : comme leurs cases de la liste des parcours). Rend l'état obtenu ; None sans parcours."""
        at = self.op_paths(r)
        if not at:
            return None
        if on is None:
            on = not any(getattr(self.toolpaths[i], 'shown', True) for i in at)
        for i in at:
            self.set_path_shown(i, bool(on))
        self._sync_eyes()
        return bool(on)

    def reverse_op_path(self) -> int:
        """Les parcours de l'opération choisie, parcourus à l'envers ; rend leur nombre."""
        at = self.op_paths(self._row(self.ops))
        for i in at:
            self.paths.setCurrentRow(i)
            self.reverse_path()
        return len(at)

    def tools_open(self) -> bool:
        """La liste des outils est-elle dépliée ?"""
        return not self.tools_group.isHidden()

    def set_tools_open(self, on: bool, remember: bool = True) -> bool:
        """La liste des outils, tout en bas du panneau : dépliée ou repliée sous son bouton (retenu) ; rend l'état."""
        on = bool(on)
        was = self.tools_open()
        self.tools_group.setVisible(on)
        self.tools_toggle.blockSignals(True)
        self.tools_toggle.setChecked(on)
        self.tools_toggle.blockSignals(False)
        self.tools_toggle.setArrowType(Qt.ArrowType.DownArrow if on else Qt.ArrowType.RightArrow)
        self.tools_box.setMaximumHeight(16777215 if on else self.tools_toggle.sizeHint().height() + 4)
        if on and not was:                               # dépliée : un tiers de la hauteur, pris aux opérations
            sizes = self.split.sizes()
            k = self.split.indexOf(self.tools_box)
            total = sum(sizes)
            if total > 0 and 0 <= k < len(sizes):
                want = max(180, total // 3)
                sizes[0] = max(120, sizes[0] - (want - sizes[k]))
                sizes[k] = want
                self.split.setSizes(sizes)
        if remember:
            self.win.settings.setValue(self.TOOLS_OPEN_KEY, on)
        return on

    @staticmethod
    def op_label(o) -> str:
        label = o.name or tr(model.op_kinds().get(o.kind, o.kind))
        return tr('{0} (reprise)').format(label) if getattr(o, 'restart_sig', '') else label

    @staticmethod
    def chain_end(ops, r: int) -> int:
        """Dernière ligne du bloc de l'opération `r` : elle et les opérations liées qui la suivent."""
        e = r
        while e + 1 < len(ops) and ops[e + 1].link_previous:
            e += 1
        return e

    def _fill_ops3d(self) -> None:
        """Liste « Usinages » de la vue 3D refaite (opérations, parcours)."""
        p3 = getattr(self.win, 'panel3d', None)
        lst = getattr(p3, 'ops_list', None) if p3 is not None else None
        if lst is not None:
            lst.fill()

    def machines_dir(self) -> str:
        """Dossier des fiches machine choisi, sinon celui livré par un plugin."""
        d = str(self.win.settings.value('fao/machines', '') or '')
        if d:
            return d
        from ..cam import post
        return post.default_machines_dir()

    def _fill_posts(self) -> None:
        from ..cam import post
        self._loading = True
        cur = self.post.currentData()
        self.post.clear()
        from ..cam import machines as MC
        for k, label, m in MC.choices(post.posts(self.machines_dir())):     # chaque machine une fois, puis les autres
            if m is None and k.startswith('mah:'):
                parent = pathlib.Path(k[4:]).parent.name
                label = f'{label} — {parent}'
            self.post.addItem(tr(label), k)
        if not self.post.count():                        # cœur seul : les post-processeurs viennent des plugins
            self.post.addItem(tr('(aucun : un plugin en apporte)'), '')
        if cur is not None:
            self.post.setCurrentIndex(max(0, self.post.findData(cur)))
        self._loading = False

    def choose_machines(self) -> None:
        d = QFileDialog.getExistingDirectory(self, tr('Dossier des fiches machine (.MAH)'), self.machines_dir())
        if d:
            self.win.settings.setValue('fao/machines', d)
            self._fill_posts()
            self.refresh()

    def _post_changed(self) -> None:
        if self._loading:
            return
        s = self.setup()
        s.post = self.post.currentData()
        self.save(s)

    def _laser_changed(self) -> None:
        if getattr(self, '_loading', True):
            return
        s = self.setup()
        s.laser_field = self.laser_field.value()
        s.laser_tiles = self.laser_tiles.isChecked()
        s.laser_marks = self.laser_marks.isChecked()
        self.save(s)

    def _op_checked(self, item) -> None:
        if self._loading or item.column() != 0:
            return
        s = self.setup()
        r = item.row()
        if r < len(s.operations):
            o = s.operations[r]
            o.enabled = item.checkState() == Qt.CheckState.Checked
            from ..cam import external
            if external.is_external(o) and external.active(o, s.post):   # le plugin la (dé)coche chez lui aussi
                external.call(o, 'set_enabled', self.doc, external.ref_of(o), o.enabled)
            self.save(s)

    def _row(self, table) -> int:
        """Première ligne choisie de `table` ; -1 sans. Dans le tableau des opérations, une ligne d'opération
        seulement : celles des parcours sans opération, en dessous, n'en sont pas (`_loose_row`)."""
        rows = sorted({i.row() for i in table.selectedIndexes()})
        if table is getattr(self, 'ops', None) and getattr(self, '_n_ops', None) is not None:
            rows = [r for r in rows if r < self._n_ops]
        return rows[0] if rows else -1

    def _loose_row(self) -> int:
        """Le parcours sans opération de la ligne choisie du tableau des opérations : son rang dans les parcours ;
        -1 si aucune de ces lignes n'est choisie."""
        n = getattr(self, '_n_ops', None)
        if n is None:
            return -1
        rows = [r for r in sorted({i.row() for i in self.ops.selectedIndexes()}) if r >= n]
        at = self.op_paths(rows[0]) if rows else []
        return at[0] if at else -1

    def _select_row(self, table, r: int) -> None:
        """La ligne `r` seule choisie : selectRow l'ajouterait à la sélection
        si Ctrl ou Maj est enfoncé (et l'opération suivante partirait de la
        première ligne choisie)."""
        from PySide6.QtCore import QItemSelectionModel
        f = QItemSelectionModel.SelectionFlag
        table.selectionModel().setCurrentIndex(table.model().index(r, 0), f.ClearAndSelect | f.Rows)

    # --- outils -------------------------------------------------------------------------
    #: tri retenu de la liste des outils (« colonne,1 » : décroissant)
    TOOLS_SORT_KEY = 'fao/outils_tri'

    def tool_row_index(self) -> int:
        """Rang dans les outils du réglage de l'outil choisi dans la liste (triée ou filtrée : par son id) ; -1."""
        r = self._row(self.tools)
        it = self.tools.item(r, 0) if r >= 0 else None
        tid = it.data(Qt.ItemDataRole.UserRole) if it is not None else None
        return next((i for i, t in enumerate(self.setup().tools) if t.id == tid), -1)

    def filter_tools(self) -> int:
        """Lignes des outils qui passent les filtres (recherche, nature), les autres cachées ; rend leur nombre."""
        from ..cam import toollib
        text, kind = self.tools_filter.text(), self.tools_kind.currentData() or ''
        n = 0
        for r in range(self.tools.rowCount()):
            it = self.tools.item(r, 0)
            t = self._tools_by_id.get(it.data(Qt.ItemDataRole.UserRole)) if it is not None else None
            ok = t is None or toollib.matches(t, text, kind)
            self.tools.setRowHidden(r, not ok)
            n += ok
        return n

    def add_tool(self) -> None:
        s = self.setup()
        t = model.CamTool(number=max((x.number for x in s.tools), default=0) + 1)
        dlg = FieldsDialog(self, tr('Nouvel outil'), t)
        if dlg.exec():
            dlg.apply()
            s.tools.append(t)
            self.save(s)

    def edit_tool(self) -> None:
        s = self.setup()
        r = self.tool_row_index()
        if r < 0:
            return
        dlg = FieldsDialog(self, tr('Outil'), s.tools[r])
        if dlg.exec():
            dlg.apply()
            self.save(s)

    def remove_tool(self) -> None:
        s = self.setup()
        r = self.tool_row_index()
        if r < 0:
            return
        t = s.tools[r]
        if any(o.tool_id == t.id for o in s.operations):
            QMessageBox.warning(self, tr('FAO'), tr('Outil utilisé par une opération : changer d\'abord l\'opération'))
            return
        del s.tools[r]
        self.save(s)

    def tools_menu(self) -> None:
        from PySide6.QtWidgets import QMenu
        m = QMenu(self)
        m.addAction(tr('Bibliothèque d\'outils…'), self.tool_library)
        m.addAction(tr('Outils proposés par opération…'), self.tool_prefs)
        m.addAction(tr('Copier les outils absents dans Mes outils'), lambda: self.copy_missing_tools())
        m.addSeparator()
        m.addAction(tr('Importer d\'une base d\'outils TypeEdit (.Dbt)…'), self.import_dbt)
        m.addAction(tr('Exporter pour TypeEdit (.Dbt)…'), self.export_dbt)
        m.exec(self.cursor().pos())
        m.deleteLater()                                   # menu ponctuel : libéré (sinon un par clic)

    def copy_missing_tools(self) -> int:
        """Outils du document absents de Mes outils : copiés dans le dossier
        « Copiés des dessins » ; rend leur nombre."""
        from ..cam import toollib
        path = toollib.default_path()
        try:
            mine = toollib.load(path) if path.exists() else []
            folders = toollib.load_folders(path) if path.exists() else []
        except (OSError, ValueError) as ex:
            self.win.statusBar().showMessage(tr('Mes outils illisible : {0}').format(ex), 8000)
            return 0
        added = []
        for t in self.setup().tools:
            if toollib.find_match(t, mine + added) is None:
                c = model.CamTool.from_dict(t.to_dict())
                c.id = model.new_id()
                toollib.set_folder([c], tr('Copiés des dessins'))
                added.append(c)
        if added:
            toollib.save(mine + added, path, folders)
        self.win.statusBar().showMessage(tr('{0} outil(s) copié(s) dans Mes outils ({1})').format(len(added), path),
                                         8000)
        self.refresh()
        return len(added)

    def tool_library(self, exec_dialog: bool = True):
        """Gestionnaire d'outils : bibliothèque, catalogues, dessins, échanges."""
        from .toollib_dialog import ToolLibraryDialog
        dlg = ToolLibraryDialog(self.win, self)
        if exec_dialog:
            dlg.exec()
            self.refresh()
        return dlg

    def tool_prefs(self, exec_dialog: bool = True):
        """Quels outils proposer, et dans quel ordre, pour chaque type d'opération."""
        from ..cam import toollib
        from .toolprefs_dialog import ToolPrefsDialog
        dlg = ToolPrefsDialog(self.win, self.win.settings, toollib.library())
        if exec_dialog:
            dlg.exec()
        return dlg

    def import_tool_folder(self, path: str | None = None, replace: bool | None = None) -> int:
        """Import en lot d'un dossier d'outils dans Mes outils (bibliothèque
        ouverte sur l'import) ; rend le nombre d'outils ajoutés."""
        dlg = self.tool_library(exec_dialog=False)
        n = dlg.import_folder(path, replace=replace) if path else dlg.import_folder_dialog()
        if path is None:
            dlg.exec()
            self.refresh()
        return n

    def import_dbt(self, path: str | None = None, accept=None) -> int:
        """Outils choisis dans une base TypeEdit / LaserType ; rend leur nombre."""
        from ..cam import tooldb
        if not path:
            path, _ = QFileDialog.getOpenFileName(self, tr('Base d\'outils TypeEdit'), '',
                                                  tr('Base d\'outils (*.Dbt *.dbt *.dbtsav)'))
            if not path:
                return 0
        try:
            entries = tooldb.read(path)
        except (tooldb.DbtError, OSError) as ex:
            QMessageBox.warning(self, tr('Base d\'outils TypeEdit'), str(ex))
            return 0
        dlg = ToolDbDialog(self, entries)
        if not (accept(dlg) if accept else dlg.exec()):
            return 0
        chosen = dlg.chosen()
        s = self.setup()
        for e in chosen:
            t = model.CamTool.from_dict(e.tool.to_dict())
            t.id = model.new_id()
            s.tools.append(t)
        self.save(s)
        notes = sorted({n for e in chosen for n in e.notes})
        self.info.setText(tr('{0} outil(s) TypeEdit ajouté(s)').format(len(chosen))
                          + ('\n' + '\n'.join(notes) if notes else ''))
        return len(chosen)

    def export_dbt(self) -> None:
        from ..cam import tooldb
        s = self.setup()
        if not s.tools:
            return
        path, _ = QFileDialog.getSaveFileName(self, tr('Base d\'outils TypeEdit'), 'VectorDrive.Dbt',
                                              tr('Base d\'outils (*.Dbt)'))
        if path:
            pathlib.Path(path).write_bytes(tooldb.write_bytes(s.tools))
            self.info.setText(tr('Base d\'outils écrite (à valider dans TypeEdit) : {0}').format(path))

    def import_tools(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, tr('Bibliothèque d\'outils'), '', 'JSON (*.json)')
        if not path:
            return
        s = self.setup()
        data = json.loads(pathlib.Path(path).read_text(encoding='utf-8'))
        items = data.get('tools', data) if isinstance(data, dict) else data
        known = {t.id for t in s.tools}
        for d in items:
            t = model.CamTool.from_dict(d)
            if t.id in known:
                t.id = model.new_id()
            s.tools.append(t)
        self.save(s)

    def export_tools(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, tr('Bibliothèque d\'outils'), 'outils.json', 'JSON (*.json)')
        if path:
            s = self.setup()
            pathlib.Path(path).write_text(json.dumps({'tools': [t.to_dict() for t in s.tools]}, indent=1,
                                                     ensure_ascii=False), encoding='utf-8')

    # --- Mes outils dans le panneau ------------------------------------------------------------
    def library_tools(self) -> list:
        from ..cam import toollib
        return toollib.library()

    def pick_library(self) -> list:
        """Les outils du formulaire d'une opération (« Choisir un outil ») : Mes outils, puis les bibliothèques des
        plugins (outils DATRON de l'atelier…)."""
        from ..cam import toollib
        return toollib.with_plugins(self.library_tools())

    def add_library_tool(self, tool) -> model.CamTool:
        """Copie d'un outil de Mes outils dans les outils du document."""
        s = self.setup()
        c = model.CamTool.from_dict(tool.to_dict())
        c.id, c.folder = model.new_id(), ''
        used = {x.number for x in s.tools}
        if c.number in used or c.number <= 0:
            c.number = max(used | {0}) + 1
        s.tools.append(c)
        self.save(s)
        return c

    def library_menu(self, exec_menu: bool = True):
        """Menu Mes outils ▸ dossier ▸ outil : l'outil choisi rejoint le document."""
        from PySide6.QtGui import QCursor
        from PySide6.QtWidgets import QMenu
        from ..cam import toollib
        lib = self.library_tools()
        m = QMenu(self)
        if not lib:
            a = m.addAction(tr('Mes outils est vide (Bibliothèque d\'outils : importer)'))
            a.setEnabled(False)
        m.vd_submenus = {}                                # dossier → sous-menu (gardés vivants)

        def submenu(f: str):
            """Sous-menu du dossier (« Datron/Fraises » sous « Datron »)."""
            parts = toollib.folder_parts(f) or [f]
            parent = m
            for i, part in enumerate(parts):
                key = toollib.SEP.join(parts[:i + 1])
                if key not in m.vd_submenus:
                    m.vd_submenus[key] = parent.addMenu('📁 ' + part)
                parent = m.vd_submenus[key]
            m.vd_submenus.setdefault(f, parent)
            return parent
        for f in toollib.folders(lib):
            sub = submenu(f)
            for t in [t for t in lib if toollib.folder_of(t) == f]:
                a = sub.addAction(f'{t.name} — Ø {t.diameter:g}')
                a.triggered.connect(lambda _=False, tt=t: self.add_library_tool(tt))
        if exec_menu:
            m.exec(QCursor.pos())
            m.deleteLater()
        return m

    # --- opérations ------------------------------------------------------------------------
    def add_op(self) -> None:
        s = self.setup()
        lib = self.pick_library()
        if not s.tools and not lib:
            QMessageBox.information(self, tr('FAO'), tr('Créer d\'abord un outil d\'usinage (ou en importer '
                                                       'dans Mes outils)'))
            return
        o = model.Operation(tool_id='', sources=[self.doc.active_layer.tool],     # outil à choisir (14/11, 19 h 45)
                            **self._op_defaults(model.Operation.kind))
        from ..core import surface2d
        surface2d.adopt(self.doc, o, self.doc.active_layer)
        dlg = FieldsDialog(self, None, o, self.doc, s.tools, library=lib,
                           selection=self._selected(), kind_choice=True)   # pas de type de parcours : la liste
        if dlg.exec():
            dlg.apply()
            s.tools.extend(dlg.new_tools)
            s.operations.append(o)
            self.save(s)
            self._follow_tools(s, dlg, o)

    def _follow_tools(self, s, dlg, skip) -> int:
        """Outils du document modifiés dans la fiche de « Choisir un outil » pendant le formulaire `dlg` : les
        parcours affichés des autres opérations qui s'en servent sont recalculés. Rend leur nombre."""
        changed = dlg.changed_tools() if dlg is not None else set()
        n = 0
        for o in s.operations:
            if o is not skip and o.tool_id in changed and any(tp.op_id == o.id for tp in self.toolpaths):
                self.compute_op(o)
                n += 1
        return n

    def add_from_catalog(self, entries=None) -> list:
        """Opérations machine prises dans un catalogue (fenêtre de choix si
        `entries` n'est pas donné), posées après l'opération choisie ; rend
        les opérations ajoutées."""
        from ..cam import catalog as C
        if entries is None:
            from .instruction_catalog import CatalogDialog
            dlg = CatalogDialog(self)
            if not dlg.exec():
                return []
            entries = dlg.chosen
        ops = [C.operation_of(e) for e in entries]
        if not ops:
            return []
        s = self.setup()
        r = self._row(self.ops)
        at = r + 1 if 0 <= r < len(s.operations) else len(s.operations)
        s.operations[at:at] = ops
        self.save(s)
        self._select_row(self.ops, at + len(ops) - 1)
        self.win.statusBar().showMessage(tr('{0} opération(s) ajoutée(s) depuis le catalogue').format(len(ops)),
                                         5000)
        return ops

    def edit_op(self, exec_dialog: bool = True, take_selection: bool = True):
        """Modifier (Ctrl+M) : le formulaire de l'opération choisie ; les
        objets sélectionnés dans le dessin deviennent ce qu'elle usine (pas
        sans `take_selection` : liste des usinages de la vue 3D) ; validé,
        son parcours est recalculé s'il était affiché."""
        s = self.setup()
        r = self._row(self.ops)
        if r < 0:
            i = self._loose_row()                       # un parcours sans opération : en faire une (réponse 13)
            return self.program_form(self.toolpaths[i], exec_dialog) if i >= 0 else None
        op = s.operations[r]
        from ..cam import external
        if external.is_external(op):                    # opération d'un plugin : réglée dans son panneau
            if not external.active(op, s.post):
                self.win.statusBar().showMessage(tr('« {0} » : opération d’un plugin absent, ou d’une autre machine '
                                                    '(Suppr la retire)').format(self.op_label(op)), 8000)
            elif external.call(op, 'edit', self.win, external.ref_of(op), default=False) is False:
                self.win.statusBar().showMessage(tr('« {0} » se règle dans le panneau de son plugin').format(
                    self.op_label(op)), 8000)
            return None
        if op.body3d_ref:                               # volume du dessin gardé : son numéro d'aujourd'hui
            from ..cam import mill3d
            now = mill3d.op_body(self.doc, op)
            if now is not None and now != op.body3d:
                op.body3d, op.body3d_ref = now, dict(op.body3d_ref, n=now)
        sel = self._selected() if take_selection else []
        before = (list(op.items), list(op.sources))
        if sel:
            op.items, op.sources = [it.id for it in sel], []
        dlg = FieldsDialog(self, None, op, self.doc, s.tools, library=self.pick_library(),
                           selection=sel)

        def done(ok) -> None:
            if not ok:
                op.items, op.sources = before
                return
            dlg.apply()
            s.tools.extend(dlg.new_tools)
            self.save(s)
            if any(t.op_id == op.id for t in self.toolpaths):
                self.compute_op(op)
            self._follow_tools(s, dlg, op)
        if not exec_dialog:
            dlg.finished.connect(lambda res: done(res == QDialog.DialogCode.Accepted))
            return dlg
        done(dlg.exec())
        return dlg

    def edit_op_tool(self, exec_dialog: bool = True):
        """Le formulaire de l'outil de l'opération choisie ; validé (une
        annulation), les parcours calculés des opérations qui s'en servent
        sont recalculés. Rend le formulaire (sans l'ouvrir si `exec_dialog`
        est faux)."""
        s, _r, op = self._current_op()
        t = s.tool(op.tool_id) if op is not None else None
        if t is None:
            self.win.statusBar().showMessage(tr('Cet usinage n\'a pas d\'outil'), 5000)
            return None
        dlg = FieldsDialog(self, tr('Outil de « {0} »').format(op.name or tr(model.op_kinds().get(op.kind, op.kind))),
                           t)

        def done(ok) -> None:
            if not ok:
                return
            push = getattr(self.win, 'push_undo', None)
            if push is not None:
                push(tr('Modifier l\'outil'), with_cam=True)
            dlg.apply()
            self.save(s)
            users = [o for o in s.operations if o.tool_id == t.id]
            shown = {tp.op_id for tp in self.toolpaths if tp.op_id}
            for o in users:
                if o.id in shown:
                    self.compute_op(o)
            if len(users) > 1:
                self.win.statusBar().showMessage(
                    tr('Outil de {0} usinages : leurs parcours calculés sont refaits').format(len(users)), 6000)
        if not exec_dialog:
            dlg.finished.connect(lambda res: done(res == QDialog.DialogCode.Accepted))
            return dlg
        done(dlg.exec())
        return dlg

    def remove_op_paths(self, op) -> int:
        """Parcours calculés de `op` retirés — l'opération reste (« Recalculer ») ;
        rend leur nombre."""
        keep = [t for t in self.toolpaths if t.op_id != op.id]
        n = len(self.toolpaths) - len(keep)
        if n:
            self.display(keep)
        return n

    def op_menu(self, pos=None, exec_menu: bool = True):
        """Clic droit sur une opération : mettre à jour avec le dessin
        sélectionné, modifier, dupliquer, supprimer, simuler en 2D ou en 3D."""
        from PySide6.QtWidgets import QMenu
        if pos is not None:
            idx = self.ops.indexAt(pos)
            if idx.isValid():
                self._select_row(self.ops, idx.row())
        if self._row(self.ops) < 0:
            return self._loose_menu(pos, exec_menu)
        m = QMenu(self)
        has_sel = bool(self._selected())
        a = m.addAction(tr('Mettre à jour avec le dessin sélectionné'), self.update_op_from_selection)
        a.setEnabled(has_sel)
        a.setToolTip(tr('Mêmes réglages, sur les objets sélectionnés ; parcours recalculé'))
        m.addAction(tr('Modifier…'), self.edit_op).setShortcut('Ctrl+M')
        m.addAction(tr('Dupliquer'), self.duplicate_op)
        m.addAction(tr('Supprimer'), self.remove_op).setShortcut('Del')
        _s, r, op = self._current_op()
        if op is not None and 'link_previous' in KIND_FIELDS.get(op.kind, ()):
            a = m.addAction(tr('Lier au parcours précédent'), lambda: self.toggle_link())
            a.setCheckable(True)
            a.setChecked(bool(op.link_previous))
            a.setEnabled(r > 0 or op.link_previous)
            a.setToolTip(tr('Ne reprendre que la matière laissée par les opérations d\'avant (gamme) ; liée, '
                            'elle suit son opération dans la liste'))
        m.addSeparator()
        m.addAction(tr('Informations…'), lambda: self.path_info()).setShortcut('Ctrl+I')
        m.addAction(tr('Compte rendu parcours outil…'), lambda: self.path_report()).setShortcut('Ctrl+T')
        has_path = bool(self.op_paths(r))
        for text, slot in ((tr('Afficher ou cacher le parcours'), lambda: self.toggle_op_paths(r)),
                           (tr('Inverser le sens du parcours'), lambda: self.reverse_op_path()),
                           (tr('Retirer le parcours calculé'), lambda: self.remove_op_paths(op))):
            m.addAction(text, slot).setEnabled(has_path)
        m.addSeparator()
        m.addAction(tr('Simuler en 2D'), lambda: self.simulate_op('sim2d'))
        m.addAction(tr('Simuler en 3D'), lambda: self.simulate_op('sim3d'))
        a = m.addAction(tr('Matière restante après cette opération…'), lambda: self.simulate_after_op())
        a.setToolTip(tr('La simulation du programme arrêtée après cette opération : la matière laissée aux suivantes ; '
                        'ce que celle-ci enlève, en vert'))
        a = m.addAction(tr('Reprise d\'usinage…'), lambda: self.restart_op())
        a.setToolTip(tr('N\'usiner qu\'une partie du parcours, après une casse d\'outil par exemple : du point de reprise au dernier point choisi'))
        m.setToolTipsVisible(True)
        if exec_menu:
            m.exec(self.ops.viewport().mapToGlobal(pos) if pos is not None else self.cursor().pos())
            m.deleteLater()
        return m

    def _loose_menu(self, pos=None, exec_menu: bool = True):
        """Clic droit sur un parcours sans opération (réponse 13 du 14/11) : en faire une opération, le montrer ou le
        cacher, l'inverser, le retirer. None : aucune de ces lignes choisie."""
        from PySide6.QtWidgets import QMenu
        i = self._loose_row()
        if i < 0:
            return None
        r = self._n_ops + self._loose.index(i)
        m = QMenu(self)
        m.addAction(tr('En faire une opération…'), self.edit_op).setShortcut('Ctrl+M')
        m.addAction(tr('Afficher ou cacher le parcours'), lambda: self.toggle_op_paths(r))

        def reverse():
            self.paths.setCurrentRow(i)
            self.reverse_path()
        m.addAction(tr('Inverser le sens du parcours'), reverse)
        m.addAction(tr('Retirer le parcours'), self.remove_op).setShortcut('Del')
        if exec_menu:
            m.exec(self.ops.viewport().mapToGlobal(pos) if pos is not None else self.cursor().pos())
            m.deleteLater()
        return m

    def _current_op(self):
        s = self.setup()
        r = self._row(self.ops)
        return (s, r, s.operations[r]) if 0 <= r < len(s.operations) else (s, r, None)

    def update_op_from_selection(self):
        """L'opération choisie usine désormais les objets sélectionnés (mêmes
        réglages) ; son parcours est recalculé."""
        s, r, op = self._current_op()
        sel = self._selected()
        if op is None or not sel:
            self.win.statusBar().showMessage(tr('Sélectionnez les objets du dessin à usiner.'), 5000)
            return None
        op.items, op.sources = [it.id for it in sel], []
        self.save(s)
        self._select_row(self.ops, r)
        return self.compute_op(op)

    def duplicate_op(self):
        """Copie de l'opération choisie, juste après elle (après ses
        opérations liées : elles restent liées à elle)."""
        s, r, op = self._current_op()
        if op is None:
            return None
        from ..cam import external
        if external.is_external(op):                    # opération d'un plugin : une par ligne de son plugin
            self.win.statusBar().showMessage(tr('« {0} » : une copie se fait dans le panneau de son plugin').format(
                self.op_label(op)), 8000)
            return None
        c = model.Operation(**{k: (list(v) if isinstance(v, list) else dict(v) if isinstance(v, dict) else v)
                               for k, v in dataclasses.asdict(op).items() if k != 'id'})
        c.name = tr('{0} (copie)').format(op.name or tr(model.op_kinds().get(op.kind, op.kind)))
        at = (r if op.link_previous else self.chain_end(s.operations, r)) + 1
        s.operations.insert(at, c)
        self.save(s)
        self._select_row(self.ops, at)
        return c

    def toggle_link(self, on: bool | None = None):
        """Lier (ou délier) l'opération choisie au parcours précédent ; son
        parcours, s'il était calculé, est refait."""
        s, r, op = self._current_op()
        if op is None:
            return None
        op.link_previous = (not op.link_previous) if on is None else bool(on)
        self.save(s)
        self._select_row(self.ops, r)
        if any(t.op_id == op.id for t in self.toolpaths):
            return self.compute_op(op)
        return op

    def restart_op(self, params: dict | None = None):
        """Reprise d'usinage (TypeEdit) de l'opération choisie, calculée au besoin. Le calcul n'est pas refait : le parcours
        complet garde ses numéros de mouvement. Rend le parcours, ou None si annulé."""
        from ..cam import restart
        s, r, op = self._current_op()
        if op is None:
            return None
        if not any(t.op_id == op.id for t in self.toolpaths):
            if self.compute_op(op) is None:
                return None
            s, r, op = self._current_op()
        tp = next((t for t in self.toolpaths if t.op_id == op.id), None)
        moves = restart.full_moves(tp) if tp is not None else []
        if not restart.rows(moves):
            self.win.statusBar().showMessage(tr('Ce parcours n\'a aucun mouvement à reprendre'), 6000)
            return None
        if params is None:
            from .restart_dialog import RestartDialog
            dlg = RestartDialog(self, self.op_label(op), moves, op)
            if not dlg.exec():
                return None
            params = {'start': dlg.start, 'end': dlg.end}
        restart.choose(op, moves, params['start'], params['end'])
        self.save(s)
        self._select_row(self.ops, r)
        strategies.apply_faced_all(s, self.toolpaths)
        self.display(self.toolpaths)
        return tp

    def apply_mode(self, mode: str) -> None:
        """Le mode simple ou expert : le bouton « Réglage… » n'est montré qu'en mode expert."""
        b = getattr(self, 'setup_btn', None)
        if b is not None:
            b.setVisible(mode != 'simple')

    def eventFilter(self, obj, ev) -> bool:
        """Ctrl+I et Ctrl+T quand la liste des opérations a la main (TE) : Ctrl+I reste Importer partout ailleurs."""
        from PySide6.QtCore import QEvent
        if obj is self.ops and ev.type() in (QEvent.Type.ShortcutOverride, QEvent.Type.KeyPress) \
                and ev.modifiers() == Qt.KeyboardModifier.ControlModifier and ev.key() in (Qt.Key.Key_I, Qt.Key.Key_T):
            ev.accept()
            if ev.type() == QEvent.Type.KeyPress:
                if ev.key() == Qt.Key.Key_I:
                    self.path_info()
                else:
                    self.path_report()
            return True
        return super().eventFilter(obj, ev)

    def _op_paths(self) -> tuple:
        """L'opération choisie et ses parcours (calculés au besoin) ; (None, []) s'il n'y en a pas."""
        _s, _r, op = self._current_op()
        if op is None:
            return None, []
        if not any(t.op_id == op.id for t in self.toolpaths) and self.compute_op(op) is None:
            return None, []
        return op, [t for t in self.toolpaths if t.op_id == op.id]

    def path_info(self, exec_dialog: bool = True):
        """Informations du parcours de l'opération choisie."""
        from ..cam import timing as TM
        from . import path_report as PR
        op, tps = self._op_paths()
        if op is None:
            return None
        src = getattr(self.doc, 'source_path', None) or ''
        dlg = PR.PathInfoDialog(self, src, PR.facts(self.doc, self.setup(), op, tps, TM.spec_from_settings(self.win.settings)))
        if exec_dialog:
            dlg.exec()
        return dlg

    def path_report(self, opts=None, names=None):
        """Comptes rendus de l'opération choisie, en PDF : le choix du contenu, puis le compte rendu du parcours et le compte rendu
        final (tous les parcours à usiner). `opts`, `names` : sans fenêtre. Rend les fichiers écrits."""
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        from ..cam import timing as TM
        from . import path_report as PR
        op, tps = self._op_paths()
        if op is None:
            return []
        src = getattr(self.doc, 'source_path', None) or ''
        short = pathlib.Path(src).name if src else tr('Dessin non enregistré')
        if opts is None:
            dlg = PR.PathReportDialog(self, tr('Compte rendu du parcours : {0}').format(op.name or tr(model.OP_KINDS.get(op.kind, op.kind))))
            if dlg.exec() != QDialog.DialogCode.Accepted:
                return []
            opts = dlg.options()
        s = self.setup()
        spec = TM.spec_from_settings(self.win.settings)
        first = PR.toolpath_html(self.doc, s, op, tps, opts, spec=spec, file_name=short, image=PR.image_ok(opts.image))
        every = self.current_paths(dates=False)
        ops = [o for o in s.operations if any(t.op_id == o.id for t in every)]
        final = PR.final_html(self.doc, s, ops, every, opts, spec=spec, file_name=short)
        titled = ((tr('Compte rendu'), first, opts.image), (tr('Compte rendu final'), final, ''))
        wanted = names or PR.report_names(src, self.win._last_dir('fiche') if not src else '')
        done = []
        for (title, text, image), path in zip(titled, wanted):
            if names is None:
                path, _f = QFileDialog.getSaveFileName(self, title, path, tr('Fichier PDF (*.pdf)'))
                if not path:
                    break
            try:
                PR.write_pdf(path, text, title, image)
            except OSError as e:
                QMessageBox.warning(self, title, str(e))
                break
            done.append(path)
            if opts.show_pdf:
                QDesktopServices.openUrl(QUrl.fromLocalFile(path))
        return done

    def simulate_op(self, where: str):
        """Simulation de la seule opération choisie (calculée au besoin) :
        'sim2d' (image ombrée) ou 'sim3d' (matière enlevée en 3D)."""
        s, r, op = self._current_op()
        if op is None:
            return None
        if not any(t.op_id == op.id for t in self.toolpaths):
            if self.compute_op(op) is None:
                return None
        for tp in self.toolpaths:
            tp.shown = tp.op_id == op.id
        self.display(self.toolpaths)
        return self.win.show_toolpaths(where)

    def simulate_after_op(self, exec_dialog: bool = True):
        """La simulation du programme — les parcours qui vont au programme (cochés, des opérations actives, et ceux
        sans opération) de la même prise que l'opération choisie, plus les siens même décochés —, arrêtée après
        l'opération choisie : la matière qui reste pour les suivantes, ce qu'elle enlève en vert. Les parcours cochés
        sont recalculés si le dessin a changé depuis (recalcul annulé ou impossible, `_stale` : rien) ; celui de
        l'opération est calculé au besoin ; rien n'est recalculé s'il n'y a aucun parcours coché."""
        from ..core import workspace as WS
        _s, _r, op = self._current_op()
        if op is None:
            return None
        if not any(t.op_id == op.id and t.moves for t in self.toolpaths) and self.compute_op(op) is None:
            return None
        if self.checked_paths() and not self.current_paths(dates=False) and self.outdated():
            return None                                  # recalcul annulé ou impossible : rien de juste à simuler
        s = self.setup()
        ops = {o.id: o for o in s.operations}
        face = WS.op_setup(op, self.doc)

        def same_face(tp) -> bool:                       # une autre face, un corps seul : un autre repère
            o = ops.get(tp.op_id)
            return (WS.op_setup(o, self.doc) if o is not None else ('', -1)) == face

        program = {id(t) for t in self._writable(self.toolpaths)}
        tps = [t for t in self.toolpaths if t.moves and same_face(t) and (t.op_id == op.id or id(t) in program)]
        if not any(t.op_id == op.id for t in tps):
            self.win.statusBar().showMessage(tr('Rien à simuler : cette opération n\'a pas de parcours'), 5000)
            return None
        from ..cam import simulate as SIM
        from .sim_dialog import SimDialog
        dlg = SimDialog(self, tps, s, SIM.stock_of(self.doc, s, tps), self._theory_lines(tps),
                        on_relief=lambda img: self.win._typeart_put(img, None, tr('Relief de la simulation')), upto=op.id)
        if exec_dialog:
            dlg.exec()
            dlg.deleteLater()                            # sa matière gardée par opération : libérée
        return dlg

    def wrap_op(self, kind: str, exec_dialog: bool = True):
        """Enroulement cylindrique ou conique (TypeEdit) de l'opération
        choisie : mode réglé (axe selon Y s'il ne l'était pas), puis sa fiche
        pour le rayon et la génératrice du dessus ; rend l'opération."""
        s = self.setup()
        r = self._row(self.ops)
        if r < 0:
            self.win.statusBar().showMessage(tr('Choisir d\'abord une opération dans la liste FAO'), 5000)
            return None
        op = s.operations[r]
        if not (op.wrap or 'none').startswith(kind):
            op.wrap = kind if kind == 'surface' else f'{kind}_y'
        self.save(s)
        self._select_row(self.ops, r)
        if exec_dialog:
            self.edit_op()
        return self.setup().operations[r]

    def merge_tool_ops(self, all_tools: bool = False) -> int:
        """Fusionner les parcours (TypeEdit) : les opérations de l'outil de
        l'opération choisie viennent à sa suite — ou, `all_tools`, toutes
        regroupées par outil. Un pas d'annulation ; rend le nombre de
        changements d'outil évités."""
        s = self.setup()
        r = self._row(self.ops)
        if not all_tools and r < 0:
            self.win.statusBar().showMessage(tr('Choisir d\'abord une opération dans la liste FAO'), 5000)
            return 0
        new = model.group_by_tool(s.operations, None if all_tools else r)
        saved = model.tool_changes(s.operations) - model.tool_changes(new)
        if [o.id for o in new] == [o.id for o in s.operations]:
            self.win.statusBar().showMessage(tr('Rien à fusionner : les opérations de cet outil se suivent déjà'), 5000)
            return 0
        before = [o.id for o in s.operations]
        self.win.push_undo(tr('Fusionner les parcours'), with_cam=True)
        s.operations = new
        self.save(s)
        self.follow_order(before)
        if not all_tools:
            self._select_row(self.ops, r)                         # l'opération choisie ne bouge pas
        self.win.statusBar().showMessage(
            tr('{0} changement(s) d\'outil en moins — vérifier l\'ordre d\'usinage (ébauche avant finition…)')
            .format(saved), 8000)
        return saved

    def spindle_dialog(self, collet_length: float | None = None, nut_diameter: float | None = None) -> bool:
        """Pince et écrou de la broche (collisions du porte-outil) : longueur
        d'outil serrée et Ø de l'écrou, pour le réglage FAO du document."""
        s = self.setup()
        if collet_length is None or nut_diameter is None:
            from dataclasses import dataclass
            from .dialogs import ParamsDialog

            @dataclass
            class P:
                collet_length: float = s.collet_length
                nut_diameter: float = s.nut_diameter
            dlg = ParamsDialog(self, tr('Broche'), P(), {
                'collet_length': tr('Longueur d\'outil serrée dans la pince (mm, 0 = inconnue)'),
                'nut_diameter': tr('Ø de l\'écrou de pince (mm, 0 = inconnu)')})
            if not dlg.exec():
                return False
            p = dlg.result_params()
            collet_length, nut_diameter = p.collet_length, p.nut_diameter
        s.collet_length, s.nut_diameter = max(0.0, collet_length), max(0.0, nut_diameter)
        self.save(s)
        return True

    def arcs_dialog(self, tolerance: float | None = None) -> bool:
        """Arcs dans les programmes : tolérance de l'ajustement des segments
        en arcs G2 / G3 (mm ; 0 = segments seuls), pour le réglage FAO du
        document."""
        s = self.setup()
        if tolerance is None:
            from dataclasses import dataclass
            from .dialogs import ParamsDialog

            @dataclass
            class P:
                arc_fit: float = s.arc_fit
            dlg = ParamsDialog(self, tr('Arcs dans les programmes'), P(), {
                'arc_fit': tr('Tolérance des arcs G2 / G3 (mm, 0 = segments seuls)')},
                warning=tr('Les suites de segments qui suivent un cercle à cette tolérance près sont écrites en '
                           'arcs : programmes plus courts, mouvements plus doux. Seulement pour les '
                           'post-processeurs qui écrivent des arcs ; jamais sur une machine à axe rotatif.'))
            if not dlg.exec():
                return False
            tolerance = dlg.result_params().arc_fit
        s.arc_fit = max(0.0, min(0.1, float(tolerance)))
        self.save(s)
        return True

    #: l'orientation de sortie, dans l'ordre du manuel de TE (page 819)
    ORIENT_LABELS = {'normal': 'Position initiale', 'miroir_y': 'Miroir par rapport à l\'axe Y',
                     'miroir_x': 'Miroir par rapport à l\'axe X', 'r180': 'Rotation de 180°',
                     'miroir_r90a': 'Miroir, puis rotation de 90° en sens anti-horaire', 'r90h': 'Rotation de 90° en sens horaire',
                     'r90a': 'Rotation de 90° en sens anti-horaire', 'miroir_r90h': 'Miroir, puis rotation de 90° en sens horaire'}

    def orient_dialog(self, how: str | None = None) -> bool:
        """Orientation de sortie : la plaque, et donc les parcours, tournés ou retournés dans le programme écrit."""
        s = self.setup()
        if how is None:
            from PySide6.QtWidgets import QInputDialog
            keys = list(self.ORIENT_LABELS)
            texts = [tr(self.ORIENT_LABELS[k]) for k in keys]
            now = keys.index(s.output_orient) if s.output_orient in keys else 0
            text, ok = QInputDialog.getItem(self, tr('Orientation de sortie'), tr('Plaque dans le programme machine'), texts, now, False)
            if not ok:
                return False
            how = keys[texts.index(text)]
        if how not in self.ORIENT_LABELS:
            return False
        s.output_orient = how
        self.save(s)
        return True

    #: le zéro des programmes (TE : positionnement de la pièce, fenêtre Usinage)
    ZERO_LABELS = {'machine': 'Selon la machine', 'dessin': 'Origine du dessin',
                   'plaque_hg': 'Coin supérieur gauche de la plaque', 'plaque_centre': 'Centre de la plaque',
                   'plaque_bg': 'Coin inférieur gauche de la plaque'}

    def post_key(self, s=None) -> str:
        """Le post-processeur des programmes du dessin : le sien, sinon le premier disponible (comme le
        post-traitement)."""
        from ..cam import post
        s = self.setup() if s is None else s
        if s.post.startswith('mah:') or s.post in post.posts(''):
            return s.post
        available = post.posts(self.machines_dir())
        return s.post if s.post in available else next(iter(available), '')

    def zero_dialog(self, how: str | None = None) -> bool:
        """Zéro du programme : le point (X0 Y0) sur lequel l'opérateur règle l'origine de la machine — celui
        qu'attend la machine (réglage par défaut), l'origine du dessin, ou un coin ou le centre de la plaque, quelle
        que soit l'origine du dessin."""
        s = self.setup()
        if how is None:
            from PySide6.QtWidgets import QInputDialog
            from ..cam import post
            keys = list(self.ZERO_LABELS)
            auto = tr(self.ZERO_LABELS[post.default_zero(self.post_key(s))])
            texts = [tr('Selon la machine (ici : {0})').format(auto[:1].lower() + auto[1:]) if k == 'machine'
                     else tr(self.ZERO_LABELS[k]) for k in keys]
            now = keys.index(s.program_zero) if s.program_zero in keys else 0
            text, ok = QInputDialog.getItem(self, tr('Zéro du programme'), tr(
                'Point X0 Y0 du programme machine, sur lequel l\'origine de la machine est réglée'), texts, now, False)
            if not ok:
                return False
            how = keys[texts.index(text)]
        if how not in self.ZERO_LABELS:
            return False
        s.program_zero = how
        self.save(s)
        return True

    #: le découpage en fichiers (TE, page 816 imprimée)
    GROUP_LABELS = {'tout': 'Tout : un seul fichier', 'plan': 'Par plan : un fichier par plan', 'parcours': 'Aucun : un fichier par parcours'}

    def group_dialog(self, how: str | None = None) -> bool:
        """Grouper les programmes : tout dans un fichier, un par plan, un par parcours."""
        s = self.setup()
        if how is None:
            from PySide6.QtWidgets import QInputDialog
            keys = list(self.GROUP_LABELS)
            texts = [tr(self.GROUP_LABELS[k]) for k in keys]
            now = keys.index(s.program_group) if s.program_group in keys else 0
            text, ok = QInputDialog.getItem(self, tr('Grouper les programmes'), tr('Fichiers écrits par le post-traitement'), texts, now, False)
            if not ok:
                return False
            how = keys[texts.index(text)]
        if how not in self.GROUP_LABELS:
            return False
        s.program_group = how
        self.save(s)
        return True

    def _plan_of_path(self, tp) -> str:
        """Le plan des objets usinés par ce parcours (le premier s'il y en a plusieurs)."""
        from .path_report import plan_names
        op = next((o for o in self.setup().operations if o.id == tp.op_id), None)
        names = plan_names(self.doc, op) if op is not None else []
        return names[0] if names else ''

    def remove_op(self) -> None:
        s = self.setup()
        r = self._row(self.ops)
        if r < 0 and (i := self._loose_row()) >= 0:     # un parcours sans opération : retiré (réponse 13)
            if self._confirm_remove_loose(self.toolpaths[i]):
                del self.toolpaths[i]
                self.display(self.toolpaths)
            return
        from ..cam import external
        if r >= 0 and external.is_external(s.operations[r]) and external.active(s.operations[r], s.post):
            # opération d'un plugin : il la retire chez lui (plugin absent, autre machine : retirée comme une autre)
            o = s.operations[r]
            if external.call(o, 'remove', self.win, external.ref_of(o), default=False):
                self.refresh()                                   # sa ligne disparue : l'opération aussi
            else:
                self.win.statusBar().showMessage(tr('« {0} » se retire dans le panneau de son plugin').format(
                    self.op_label(o)), 8000)
            return
        if r >= 0:
            push = getattr(self.win, 'push_undo', None)
            if push is not None:                                 # Annuler la rend
                push(tr('Supprimer l\'opération'), with_cam=True)
                s = self.setup()
            gone = s.operations[r].id
            del s.operations[r]
            self.save(s)
            if any(t.op_id == gone for t in self.toolpaths):     # son parcours disparaît aussi
                self.display([t for t in self.toolpaths if t.op_id != gone])

    def _confirm_remove_loose(self, tp) -> bool:
        """Retirer un parcours sans opération ? Annuler ne le rend pas (un programme relu se relit) : on demande."""
        from PySide6.QtWidgets import QMessageBox
        b = QMessageBox.StandardButton
        return QMessageBox.question(
            self, tr('Retirer le parcours'),
            tr('Retirer le parcours « {0} » ? Annuler ne le rend pas : il faudra le relire.').format(tp.name or '—'),
            b.Yes | b.No, b.No) == b.Yes

    def _move_loose(self, i: int, d: int) -> None:
        """↑ / ↓ sur un parcours sans opération : il change de place dans l'ordre d'écriture (avant une opération,
        par exemple : la liste des parcours se montre alors, dans cet ordre) ; sa ligne reste choisie. Il passe d'un
        coup tous les parcours voisins d'une même opération (jamais entre deux passes d'une opération) ; un autre
        parcours sans opération, un par un."""
        t = self.toolpaths
        j = i + d
        if not 0 <= j < len(t):
            return
        known = {o.id for o in self.setup().operations}
        run = [j]
        oid = t[j].op_id
        if oid and oid in known:
            while 0 <= run[-1] + d < len(t) and t[run[-1] + d].op_id == oid:
                run.append(run[-1] + d)
        at = min(run) if d < 0 else max(run)
        t.insert(at, t.pop(i))
        self.display(t)
        if at in self._loose:
            self._select_row(self.ops, self._n_ops + self._loose.index(at))

    def move_op(self, d: int) -> None:
        """Monter (-1) ou descendre (1) l'opération choisie : avec ses
        opérations liées, d'un bloc, par-dessus le bloc voisin ; une opération
        liée change seule de place."""
        s = self.setup()
        r = self._row(self.ops)
        if r < 0 and (i := self._loose_row()) >= 0:     # un parcours sans opération (réponse 13) : sa place
            self._move_loose(i, d)
            return
        ops = s.operations
        if r < 0 or not 0 <= r + d < len(ops):
            return
        if ops[r].link_previous:
            a, b = sorted((r, r + d))
            ops[a], ops[b] = ops[b], ops[a]
            moved, at = {ops[a].id, ops[b].id}, r + d
        else:
            e = self.chain_end(ops, r)
            if d < 0:
                h = r - 1
                while h > 0 and ops[h].link_previous:        # le bloc d'avant, depuis son opération de tête
                    h -= 1
                block, other = ops[r:e + 1], ops[h:r]
                ops[h:e + 1] = block + other
                at = h
            else:
                if e + 1 >= len(ops):
                    return
                f = self.chain_end(ops, e + 1)
                block, other = ops[r:e + 1], ops[e + 1:f + 1]
                ops[r:f + 1] = other + block
                at = r + len(other)
            moved = {o.id for o in block + other}
        self.save(s)
        self._paths_follow(moved, s)
        self._select_row(self.ops, at)

    def follow_order(self, before) -> None:
        """Parcours des opérations qui ont changé de place par rapport aux
        autres depuis `before` (identifiants dans l'ordre d'avant : fusion,
        annulation) — celles hors de la suite gardée — remis juste après ceux
        des opérations qui les précèdent maintenant ; les autres restent où
        ils sont (ordre réglé à la main compris)."""
        now = [o.id for o in self.setup().operations]
        has = {t.op_id for t in self.toolpaths if t.op_id}  # sans parcours (désactivées…) : sans effet
        was, kept = set(before) & has, set(now) & has
        a, b = [i for i in now if i in was], [i for i in before if i in kept]
        same = self._lcs(a, b)
        moved = [i for i in a if i not in same]
        tps = [t for t in self.toolpaths if t.op_id not in moved]
        for oid in moved:                                    # dans l'ordre des opérations
            mine = [t for t in self.toolpaths if t.op_id == oid]
            k = now.index(oid)
            earlier, later = set(now[:k]), set(now[k + 1:])
            after = [i + 1 for i, t in enumerate(tps) if t.op_id in earlier]
            ahead = [i for i, t in enumerate(tps) if t.op_id in later]
            at = max(after) if after else min(ahead) if ahead else len(tps)
            tps[at:at] = mine
        if tps != self.toolpaths:
            self.display(tps)

    @staticmethod
    def _lcs(a, b) -> set:
        """Éléments d'une plus longue sous-suite commune à `a` et `b`."""
        n, m = len(a), len(b)
        L = [[0] * (m + 1) for _ in range(n + 1)]
        for i in range(n - 1, -1, -1):
            for j in range(m - 1, -1, -1):
                L[i][j] = L[i + 1][j + 1] + 1 if a[i] == b[j] else max(L[i + 1][j], L[i][j + 1])
        out, i, j = set(), 0, 0
        while i < n and j < m:
            if a[i] == b[j]:
                out.add(a[i])
                i, j = i + 1, j + 1
            elif L[i + 1][j] >= L[i][j + 1]:
                i += 1
            else:
                j += 1
        return out

    def _paths_follow(self, ids, s) -> None:
        """Parcours des opérations `ids` remis dans l'ordre des opérations,
        aux places qu'ils occupaient : une opération montée ou descendue
        emmène ses parcours (les autres, sans opération ou déplacés à la
        main, restent où ils sont)."""
        at = [i for i, t in enumerate(self.toolpaths) if t.op_id in ids]
        if len(at) < 2:
            return
        order = {o.id: i for i, o in enumerate(s.operations)}
        tps = list(self.toolpaths)
        for i, t in zip(at, sorted((tps[i] for i in at), key=lambda t: order.get(t.op_id, len(order)))):
            tps[i] = t
        if tps != self.toolpaths:
            self.display(tps)

    def ops_from_colors(self) -> None:
        """Une gravure par couleur (outil du dessin) utilisée."""
        s = self.setup()
        if not s.tools:
            s.tools.append(model.CamTool(name=tr('Outil de gravure'), kind='conique', diameter=3.0,
                                         tip=0.1, angle=30.0))
        from ..cam.fixture import without_plates        # plaque de reprise posée : ses couleurs n'en sont pas
        used = sorted({it.tool for it in without_plates(self.doc).iter_leaves()})
        have = {tuple(o.sources) for o in s.operations}
        for idx in used:
            if (idx,) in have:
                continue
            name = next((t.name for t in self.doc.tools if t.index == idx), '') or tr('Outil {0}').format(idx + 1)
            s.operations.append(model.Operation(name=name, kind='gravure', tool_id=s.tools[0].id, sources=[idx],
                                                **self._op_defaults('gravure')))
        self.save(s)

    # --- palette « Créer un parcours » ------------------------------------------------------
    def favorites(self) -> list[str]:
        """Commandes FAO de la palette TypeEdit_User (TypeEdit installé sur ce
        poste), sinon celles d'un plugin."""
        from ..plugins import REGISTRY
        from .shortcuts import user_palette
        got = [k for k in user_palette() if k.startswith('cam_')]
        out = []
        for k in got or REGISTRY.cam_favorites:
            if k not in out and k in self.win.A:
                out.append(k)
        return out

    #: stratégies dont les nouvelles opérations entrent en rampe si l'option le veut (F10 ; TypeEdit : plongée angulaire)
    RAMP_KINDS = ('contour', 'poche', 'gravure')
    #: réglages des nouvelles opérations venus des options (F10) depuis le round 899. Des dernières valeurs d'un parcours
    #: retenues avant, ils ne sont pas repris : c'étaient les réglages d'origine, pas un choix
    DEFAULTS_ROUND = 899
    NEW_DEFAULTS = frozenset({'start_policy', 'ramp', 'vcarve_walls'})

    def _op_defaults(self, kind: str = '') -> dict:
        """Réglages des nouvelles opérations venus des options (F10) : hauteurs de dégagement et d'approche, départ des
        contours fermés ; selon la stratégie `kind`, l'entrée en rampe et les passes sur les flancs de la Gravure 3D."""
        from .options import value
        st = self.win.settings
        start = value(st, 'fao/depart')
        d = {'safe_z': value(st, 'fao/z_degagement'),
             'safe_z_faced': value(st, 'fao/z_surface'),
             'clear_z': value(st, 'fao/z_approche'),
             'start_policy': start if start in ('proche', 'dessin') else 'proche'}
        if kind in self.RAMP_KINDS:
            d['ramp'] = value(st, 'fao/rampe')
        if kind == 'vcarve':
            d['vcarve_walls'] = value(st, 'fao/gravure3d_flancs')
        return d

    def _after_tool_chosen(self, o: model.Operation, s: model.CamSetup, key: str, old: bool) -> None:
        """Parcours ouvert sans outil, outil choisi au formulaire : le pas du fond de la gravure 3D (`old` : dernières
        valeurs d'avant les options) et l'outil de référence du reste matière, d'après lui."""
        tool = s.tool(o.tool_id)
        if tool is None:
            return
        if old:
            self._floor_default(o, tool)
        if key == 'reste' and not o.ref_tool_id:
            depth = abs(o.depth)
            bigger = [t for t in s.tools if t.kind in ('fraise', 'boule')
                      and t.radius_at(depth) > tool.radius_at(depth)]
            o.ref_tool_id = min(bigger, key=lambda t: t.diameter).id if bigger else ''

    def _floor_default(self, o: model.Operation, tool) -> None:
        """Gravure 3D : la distance entre les passes du fond, à 50 % de la pointe de l'outil comme TypeEdit, si
        l'option le veut et que l'opération n'en a pas."""
        from .options import value
        if o.kind == 'vcarve' and not o.stepover_mm and tool is not None and (getattr(tool, 'tip', 0.0) or 0.0) > 0 \
                and value(self.win.settings, 'fao/gravure3d_fond') == 'pointe':
            o.stepover_mm = round(tool.tip / 2, 3)

    #: dernières valeurs des parcours de la palette (JSON : parcours → modèle d'une opération et son outil)
    LAST_KEY = 'fao/derniers_parcours'
    #: jamais repris des dernières valeurs : le nom, la stratégie du parcours, les hauteurs de F10, ce qui tient au dessin
    LAST_SKIP = frozenset({'name', 'kind', 'stock_z', 'safe_z', 'safe_z_faced', 'clear_z', 'wrap_model', 'model_path', 'faces3d', 'contours3d',
                           'contours3d_pl', 'setup_face', 'body3d', 'body3d_ref', 'surface2d'})

    def _last_all(self) -> dict:
        import json
        try:
            d = json.loads(str(self.win.settings.value(self.LAST_KEY, '') or '') or '{}')
        except ValueError:
            return {}
        return d if isinstance(d, dict) else {}

    def last_values(self, key: str) -> dict | None:
        """Dernières valeurs du parcours `key` de la palette (modèle d'une
        opération et de son outil) ; None : pas encore employé."""
        tpl = self._last_all().get(key)
        ops = tpl.get('operations') if isinstance(tpl, dict) else None
        return tpl if isinstance(ops, list) and ops and isinstance(ops[0], dict) else None

    def remember(self, key: str, o: model.Operation, s: model.CamSetup) -> None:
        """Valeurs du formulaire validé : elles préremplissent le prochain parcours `key`."""
        import json
        from ..cam import templates as TPL
        last = self._last_all()
        last[key] = TPL.single(o, next((t for t in s.tools if t.id == o.tool_id), None), '', key)
        last[key]['defaults'] = self.DEFAULTS_ROUND
        self.win.settings.setValue(self.LAST_KEY, json.dumps(last, ensure_ascii=False))
        pal = getattr(self.win, 'cam_palette', None)
        if pal is not None:
            pal.update_tips()

    def forget_last(self, key: str) -> bool:
        """Le parcours `key` repart de ses réglages d'origine."""
        import json
        last = self._last_all()
        if last.pop(key, None) is None:
            return False
        self.win.settings.setValue(self.LAST_KEY, json.dumps(last, ensure_ascii=False))
        pal = getattr(self.win, 'cam_palette', None)
        if pal is not None:
            pal.update_tips()
        return True

    def _scope(self) -> dict | None:
        """Objets usinés par un nouveau parcours : les contours sélectionnés
        (usinage de la sélection, par défaut) ; en usinage par couleur, les
        couleurs de la sélection, sinon celle du calque actif. None : rien
        de sélectionné en usinage de la sélection."""
        sel = list(self.win.canvas.selection)
        if self.machining_mode() == 'couleur':
            from .canvas import _leaves
            cols = sorted({leaf.tool for leaf in _leaves(sel)}) if sel else []
            return {'items': [], 'sources': cols or [self.doc.active_layer.tool]}
        if not sel:
            return None
        return {'items': [it.id for it in sel], 'sources': []}

    def _tool_for(self, s: model.CamSetup, kind: str, smallest: bool = False, op_kind: str = '',
                  create: bool = True) -> model.CamTool:
        """Outil de la nature voulue (le premier, ou le plus petit) : du
        document, sinon de Mes outils (copié dans le document), sinon créé.
        Stratégie `op_kind` réglée (Outils proposés par opération) : le
        premier outil proposé, du document puis de Mes outils."""
        from ..cam import toollib, toolprefs
        from .tool_filters import MACHINE_ONLY
        prefs = toolprefs.load(self.win.settings)
        mine = self.library_tools()
        if self.win.settings.value(MACHINE_ONLY, True) not in (False, 'false', '0', 0):
            mine = [t for t in mine if toollib.for_machine(t, s.post)] or mine     # outils de la machine d'abord
        if op_kind and toolprefs.customized(op_kind, prefs):
            t = toolprefs.best(s.tools, op_kind, prefs)
            if t is not None:
                return t
            lib = toolprefs.best(mine, op_kind, prefs)
            if lib is not None:
                return self._copy_tool(s, lib)

        def pick(tools):
            same = [t for t in tools if t.kind == kind] or \
                ([t for t in tools if t.kind == 'fraise'] if kind == 'foret' else [])
            if not same:
                return None
            return min(same, key=lambda t: t.diameter) if smallest else same[0]
        t = pick(s.tools)
        if t is not None:
            return t
        lib = pick(mine)
        if lib is not None:
            return self._copy_tool(s, lib)
        if not create:                                   # formulaire ouvert : rien de créé d'office, outil à choisir
            return None
        t = model.CamTool(**DEFAULT_TOOLS.get(kind, DEFAULT_TOOLS['fraise']))
        t.name = tr(t.name)
        t.number = max([x.number for x in s.tools] + [0]) + 1
        s.tools.append(t)
        return t

    @staticmethod
    def _copy_tool(s: model.CamSetup, lib) -> model.CamTool:
        """Copie d'un outil de Mes outils dans le document (numéro libre)."""
        c = model.CamTool.from_dict(lib.to_dict())
        c.id, c.folder = model.new_id(), ''
        used = {x.number for x in s.tools}
        if c.number in used or c.number <= 0:
            c.number = max(used | {0}) + 1
        s.tools.append(c)
        return c

    def machining_mode(self) -> str:
        """Ce qu'usine un nouveau parcours : 'selection' (les contours
        sélectionnés, par défaut) ou 'couleur' (usinage par couleur)."""
        from .cam_palette import machining_mode
        return machining_mode(self.win.settings)

    def templates_for(self, key: str) -> list[str]:
        """Modèles d'usinage d'un parcours de la palette (noms)."""
        from ..cam import templates as TPL
        from .cam_palette import preset_of
        kinds = {}
        for k, (_l, kind, _kw, _tk) in presets().items():
            kinds.setdefault(kind, k)
        return sorted((n for n, (_o, t) in TPL.all_templates().items() if preset_of(t, kinds) == key),
                      key=str.lower)

    def _apply_op_template(self, o: model.Operation, s: model.CamSetup, name: str) -> bool:
        """Réglages de l'opération et outil du modèle `name` sur `o` (les
        objets à usiner restent ceux de `o`) ; l'outil du modèle est retrouvé
        dans le document, sinon ajouté."""
        from ..cam import templates as TPL
        found = TPL.all_templates().get(name)
        if found is None or not (found[1].get('operations') or []):
            return False
        return self._apply_tpl(o, s, found[1], name)

    def _apply_tpl(self, o: model.Operation, s: model.CamSetup, tpl: dict, name: str, skip=frozenset()) -> bool:
        """Réglages de l'opération et outil du modèle `tpl` sur `o` ; `skip` :
        champs gardés de `o` (dernières valeurs d'un parcours)."""
        import copy
        from ..cam import templates as TPL
        t_op = model.Operation.from_dict(tpl['operations'][0])
        keep = {'id', 'items', 'sources', 'tool_id', 'ref_tool_id', 'enabled', 'body3d_ref'} | set(skip)  # volume
        if t_op.kind not in model.op_kinds():                                         # gardé : le sien (autre
            keep.add('kind')                                                          # numéro : repris)
        for f in dataclasses.fields(model.Operation):
            if f.name not in keep:
                setattr(o, f.name, copy.deepcopy(getattr(t_op, f.name)))
        tools = tpl.get('tools') or []

        def place(d):
            want = model.CamTool.from_dict(d)
            got = TPL._match(s, want)
            if got is None:
                got = model.CamTool.from_dict(want.to_dict())
                got.id, got.folder = model.new_id(), ''
                used = {x.number for x in s.tools}
                if got.number in used or got.number <= 0:
                    got.number = max(used | {0}) + 1
                s.tools.append(got)
            return got.id
        if tools:
            o.tool_id = place(next((d for d in tools if d.get('id') == t_op.tool_id), tools[0]))
            ref = next((d for d in tools if t_op.ref_tool_id and d.get('id') == t_op.ref_tool_id), None)
            if ref is not None:                            # gamme : l'outil d'ébauche du modèle
                o.ref_tool_id = place(ref)
        if 'name' not in keep:
            o.name = t_op.name or name
        return True

    def family_members(self, family: str) -> list:
        """Parcours unifiés : les parcours (clés) que la famille `family` offre ici — ceux de la palette qui vont à
        la machine du dessin (un parcours laser pour un laser, les autres pour une fraiseuse)."""
        ps = presets()
        machine = getattr(self.win, '_machine_kind', '')

        def fits(key: str) -> bool:
            if not machine or key == 'instruction':
                return True
            return (ps[key][3] == 'laser') == (machine == 'laser')
        return [k for k, _t in UNIFIED.get(family, ('', '', ()))[2] if k in ps and fits(k)]

    def _family_last(self) -> dict:
        import json
        try:
            last = json.loads(str(self.win.settings.value(UNIFIED_LAST, '') or '{}'))
        except ValueError:
            last = {}
        return last if isinstance(last, dict) else {}

    def new_family(self, family: str, exec_dialog: bool = True, member: str = ''):
        """Nouveau parcours d'une famille (parcours unifiés, question 27) : le parcours `member`, sinon celui pris
        la dernière fois dans la famille, sinon le premier ; son formulaire porte la liste de la famille pour en
        changer. None : la famille n'offre rien ici, ou rien n'est ajouté."""
        members = self.family_members(family)
        if not members:
            return None
        if member not in members:
            member = self._family_last().get(family)
            member = member if member in members else members[0]
        return self.new_operation(member, exec_dialog=exec_dialog, family=family)

    def new_operation(self, key: str, exec_dialog: bool = True, template: str | None = None, family: str = ''):
        """Nouveau parcours de la palette : opération réglée d'avance (ou
        d'après le modèle `template`) sur les contours sélectionnés — ou les
        couleurs, en usinage par couleur —, son formulaire, puis son calcul.
        `family` : il vient d'une famille (parcours unifiés), qui retient ce choix une fois le parcours ajouté."""
        scope = self._scope()
        if scope is None:
            msg = tr('Sélectionnez d\'abord les contours à usiner (ou « Usiner : les couleurs »)')
            self.win.statusBar().showMessage(msg, 8000)
            self.info.setText(msg)
            return None
        if key == 'gamme' and not template:
            return self.new_gamme(exec_dialog=exec_dialog)
        if key == 'gamme_relief' and not template:
            return self.new_relief_gamme(exec_dialog=exec_dialog)
        if template:
            from ..cam import templates as TPL
            found = TPL.all_templates().get(template)
            if found is not None and len(found[1].get('operations') or []) > 1:
                # modèle à plusieurs opérations (gamme TypeEdit : ébauche + finition)
                self.apply_template(template, exec_dialog=False, sources=scope['sources'] or None,
                                    items=scope['items'] or None)
                return self.setup().operations[-1] if self.setup().operations else None
        label, kind, kw, tkind = presets()[key]
        s = self.setup()
        # formulaire : prérempli avec les dernières valeurs du parcours (sauf modèle choisi)
        last = self.last_values(key) if exec_dialog and not template else None
        # mode expert : le formulaire propose l'outil conseillé — aucun mis d'office (ni copié de Mes outils) avant
        propose = exec_dialog and not template and proposes_tool(self.win.settings, key)
        tool = None if (last is not None and last.get('tools')) or propose else \
            self._tool_for(s, tkind, smallest=(key == 'reste'), op_kind=kind, create=not exec_dialog)
        o = model.Operation(name=tr(label), kind=kind, tool_id=tool.id if tool is not None else '',
                            **{**self._op_defaults(kind), **kw}, **scope)
        old = True                                        # dernières valeurs retenues avant les options : pas celles-là
        if last is not None:
            old = int(last.get('defaults', 0) or 0) < self.DEFAULTS_ROUND
            self._apply_tpl(o, s, last, tr(label), skip=self.LAST_SKIP | (self.NEW_DEFAULTS if old else frozenset()))
            tool = next((t for t in s.tools if t.id == o.tool_id), tool)
        if old:
            self._floor_default(o, tool)
        if key == 'reste' and tool is not None:
            depth = abs(o.depth)
            bigger = [t for t in s.tools if t.kind in ('fraise', 'boule')
                      and t.radius_at(depth) > tool.radius_at(depth)]
            o.ref_tool_id = min(bigger, key=lambda t: t.diameter).id if bigger else ''
        if template:
            self._apply_op_template(o, s, template)
        elif kind in ('relief', 'surface3d'):             # un relief s'usine sur toute sa hauteur, pas sur la dernière valeur
            height = self._relief_height(o)
            if height > 0:
                o.depth = round(height, 3)
        from ..core import surface2d
        surface2d.adopt(self.doc, o, self.doc.active_layer)   # dessin d'une surface posée : sa prise, sa cote
        if exec_dialog:
            dlg = FieldsDialog(self, None, o, self.doc, s.tools,
                               library=self.pick_library(), selection=self._selected(),
                               templates=self.templates_for(key), preset=key, template=template,
                               family=family, members=self.family_members(family) if family else ())
            if not dlg.exec():
                if dlg.switch_to:                        # un autre parcours de la famille, choisi dans la liste
                    return self.new_family(family, exec_dialog=exec_dialog, member=dlg.switch_to)
                return None
            dlg.apply()
            s.tools.extend(dlg.new_tools)                 # outil pris dans Mes outils : copié dans le document
            if tool is None:                             # outil choisi au formulaire : ce qui se règle d'après lui
                self._after_tool_chosen(o, s, key, old)
            self.remember(key, o, s)
        if family and key in self.family_members(family):    # ajouté : la famille rouvrira ce parcours (jamais une
            import json                                      # gamme, qui a sa propre fenêtre, ni un formulaire annulé)
            last = self._family_last()
            if last.get(family) != key:
                last[family] = key
                self.win.settings.setValue(UNIFIED_LAST, json.dumps(last))
        s.operations.append(o)
        self.save(s)
        self.compute_op(o)
        if exec_dialog:
            self._follow_tools(s, dlg, o)
        return o

    #: stratégies qui usinent une pièce 3D (zone : faces ou contours choisis dans la vue 3D)
    from ..cam.mill3d import KINDS as KINDS_3D

    def add_3d_operation(self, kind: str, *, faces=(), loops=(), model_path: str = '', depth: float = 0.0,
                         name: str = '', exec_dialog: bool = True, **kw):
        """Nouvelle opération 3D sur les faces ou les contours choisis dans la
        vue 3D (outil boule de préférence), son formulaire, son calcul."""
        import os
        from ..io import model3d
        s = self.setup()
        tool = self._tool_for(s, kw.pop('tool_kind', 'boule'), op_kind=kind, create=not exec_dialog)
        src = model3d.source_of(self.doc) or ''
        same = bool(src) and os.path.normcase(os.path.abspath(src)) == os.path.normcase(os.path.abspath(model_path)) \
            if model_path else True
        o = model.Operation(name=name or tr(model.op_kinds().get(kind, kind)), kind=kind,
                            tool_id=tool.id if tool is not None else '',
                            depth=round(float(depth), 3), faces3d=sorted(int(f) for f in faces),
                            contours3d=[[[round(float(c), 4) for c in p] for p in L] for L in loops],
                            model_path='' if same else model_path, **{**self._op_defaults(kind), **kw})
        if o.contours3d:                                 # contours choisis sur la pièce posée comme maintenant
            from ..cam import mill3d
            o.contours3d_pl = mill3d.zone_frame(self.doc, mill3d.model_path(self.doc, o))
        return self._finish_new_op(s, o, exec_dialog, tr('Usinage 3D de la sélection'))

    def add_pocket(self, items, depth: float, name: str = '', exec_dialog: bool = True):
        """Poche sur les formes `items`, jusqu'à `depth` (fond plat choisi en 3D)."""
        s = self.setup()
        tool = self._tool_for(s, 'fraise', op_kind='poche', create=not exec_dialog)
        o = model.Operation(name=name or tr('Poche'), kind='poche', tool_id=tool.id if tool is not None else '',
                            depth=round(float(depth), 3),
                            items=[it.id for it in items], **self._op_defaults('poche'))
        return self._finish_new_op(s, o, exec_dialog, '')

    def add_drilling(self, items, depth: float, diameter: float, name: str = '', exec_dialog: bool = True,
                     mill: bool = False):
        """Perçage des cercles `items` (trous d'une pièce 3D) : au foret du
        bon diamètre s'il y en a un (document, puis Mes outils), sinon à la
        fraise en hélice (perçage à la fraise, diamètre du trou). `mill` :
        toujours à la fraise, même si un foret convient."""
        s = self.setup()
        foret = None if mill else next((t for t in list(s.tools) + list(self.library_tools())
                                        if t.kind == 'foret' and abs(t.diameter - diameter) < 0.011), None)
        if foret is not None:
            if all(t.id != foret.id for t in s.tools):
                foret = self._copy_tool(s, foret)
            o = model.Operation(name=name or tr('Perçage'), kind='percage', tool_id=foret.id,
                                depth=round(float(depth), 3), items=[it.id for it in items], **self._op_defaults())
        else:
            tool = self._tool_for(s, 'fraise', smallest=True, op_kind='percage_fraise', create=not exec_dialog)
            o = model.Operation(name=name or tr('Perçage à la fraise'), kind='percage_fraise',
                                tool_id=tool.id if tool is not None else '',
                                depth=round(float(depth), 3), hole_diameter=round(float(diameter), 3),
                                items=[it.id for it in items], **self._op_defaults())
        return self._finish_new_op(s, o, exec_dialog, '')

    def _finish_new_op(self, s, o, exec_dialog: bool, undo_label: str):
        """Opération `o` préparée sur le réglage `s` : son formulaire, puis
        ajoutée, enregistrée et calculée."""
        if exec_dialog:
            dlg = FieldsDialog(self, None, o, self.doc, s.tools,
                               library=self.pick_library(), selection=self._selected())
            if not dlg.exec():
                return None
            dlg.apply()
            s.tools.extend(dlg.new_tools)
        if undo_label:
            self.win.push_undo(undo_label, with_cam=True)
        s.operations.append(o)
        self.save(s)
        self.compute_op(o)
        if exec_dialog:
            self._follow_tools(s, dlg, o)
        return o

    def set_op_zone(self, op_id: str, faces=(), loops=()) -> bool:
        """Zone d'une opération 3D remplacée par les faces ou les contours
        choisis dans la vue 3D, puis parcours recalculé."""
        s = self.setup()
        o = next((x for x in s.operations if x.id == op_id), None)
        if o is None:
            return False
        self.win.push_undo(tr('Zone de l\'usinage 3D'), with_cam=True)
        o.faces3d = sorted(int(f) for f in faces)
        o.contours3d = [[[round(float(c), 4) for c in p] for p in L] for L in loops]
        from ..cam import mill3d
        o.contours3d_pl = mill3d.zone_frame(self.doc, mill3d.model_path(self.doc, o)) if o.contours3d else {}
        self.save(s)
        self.compute_op(o)
        return True

    def apply_auto3d(self, planned: list) -> list:
        """Étapes d'un automatisme 3D (`cam.auto3d.plan`) : outils pris de
        Mes outils copiés dans le document, outils nouveaux ajoutés, puis les
        opérations, dans l'ordre — une seule annulation ; parcours calculés."""
        if not planned:
            return []
        self.win.push_undo(tr('Automatisme d\'usinage 3D'), with_cam=True)
        s = self.setup()
        ops = []
        placed: dict = {}
        for p in planned:
            t = p.tool
            if t is None:                                  # instruction (retourner la pièce) : sans outil
                s.operations.append(p.op)
                ops.append(p.op)
                continue
            if t.id in placed:
                tid = placed[t.id]
            elif any(x.id == t.id for x in s.tools):
                tid = t.id
            elif p.origin == 'bibliotheque':
                tid = self._copy_tool(s, t).id
            else:
                c = model.CamTool.from_dict(t.to_dict())
                used = {x.number for x in s.tools}
                if c.number in used or c.number <= 0:
                    c.number = max(used | {0}) + 1
                s.tools.append(c)
                tid = c.id
            placed[t.id] = tid
            o = p.op
            o.tool_id = tid
            if o.ref_tool_id in placed:
                o.ref_tool_id = placed[o.ref_tool_id]
            if o.contours3d and not o.contours3d_pl:       # contours choisis sur la pièce posée comme maintenant
                from ..cam import mill3d
                o.contours3d_pl = mill3d.zone_frame(self.doc, mill3d.model_path(self.doc, o))
            s.operations.append(o)
            ops.append(o)
        self.save(s)
        for o in ops:
            if o.kind != 'instruction':
                self.compute_op(o)
        return ops

    def auto3d(self, exec_dialog: bool = True):
        """Automatisme d'usinage 3D depuis le panneau FAO : la vue 3D, puis
        sa fenêtre."""
        self.win.set_view_mode('3d')
        p = getattr(self.win, 'panel3d', None)
        if p is None:
            return None
        if p.source.currentData() not in ('auto', 'modele'):
            p.set_source('modele')
        return p.auto3d(exec_dialog=exec_dialog)

    def stock_dialog(self, exec_dialog: bool = True, model=None):
        """Brut de la pièce 3D (bloc, barre ronde, plaque, marges) : gardé
        avec le réglage FAO du dessin ; rend la fenêtre."""
        from ..core import stock3d
        from .stock_dialog import StockDialog
        if model is None:
            from ..cam import mill3d
            from ..io import model3d
            src = model3d.source_of(self.doc)
            try:
                model = mill3d.load_model(self.doc, src) if src else mill3d.volumes_model(self.doc)
            except Exception:                              # noqa: BLE001 — pièce illisible : brut sans contrôle
                model = None
        s = self.setup()
        dlg = StockDialog(self, stock3d.of_setup(s), model, getattr(self.doc, 'plate', None))
        if exec_dialog and dlg.exec():
            self.set_stock(dlg.value())
        return dlg

    def set_stock(self, stock) -> None:
        """Brut gardé avec le réglage FAO ; la vue 3D le montre."""
        from ..core import stock3d
        s = self.setup()
        s.stock3d = stock3d.to_dict(stock) if stock.active() else {}
        self.save(s)
        p = getattr(self.win, 'panel3d', None)
        if p is not None and hasattr(p, 'show_stock'):
            p.show_stock()

    def stock2d_dialog(self, exec_dialog: bool = True):
        """Brut du dessin 2D (réponse 20 du 14/11) : plaque ou contour dessiné, marges, surépaisseur au-dessus de la
        plaque ; gardé avec le réglage FAO du dessin ; rend la fenêtre."""
        from ..core import stock2d
        from .stock2d_dialog import Stock2DDialog
        sel = list(getattr(self.win.canvas, 'selection', []) or []) if getattr(self.win, 'canvas', None) else []
        dlg = Stock2DDialog(self, stock2d.of_setup(self.setup()), self.doc, sel[0] if len(sel) == 1 else None)
        if exec_dialog and dlg.exec():
            self.set_stock2d(dlg.value())
        return dlg

    def set_stock2d(self, stock) -> None:
        """Brut du dessin 2D gardé avec le réglage FAO (Annuler le rend)."""
        from ..core import stock2d
        push = getattr(self.win, 'push_undo', None)
        if push is not None:
            push(tr('Brut du dessin 2D'), with_cam=True)
        s = self.setup()
        s.stock2d = stock2d.to_dict(stock) if stock.active() else {}
        self.save(s)

    #: dernier réglage des trous de fixation des bruts (`cam.fixture.Spec`, en JSON)
    FIXTURE_KEY = 'fao/plaque_reprise'

    def blank_thickness(self) -> float:
        """L'épaisseur du brut : celle du brut 2D du réglage s'il en donne une, sinon celle de la plaque du dessin ;
        0 : inconnue."""
        from ..core import stock2d
        stock = stock2d.from_dict(self.setup().stock2d)
        if stock.active() and stock.thickness > 0:
            return float(stock.thickness)
        plate = getattr(self.doc, 'plate', None)
        return max(0.0, float(getattr(plate, 'thickness', 0.0) or 0.0)) if plate is not None else 0.0

    def _thread_mill(self, s, thread: str):
        """La fraise d'un taraudage sans avant-trou (sous M6 : elle perce elle-même) : l'outil proposé pour le
        taraudage s'il est réglé (Outils proposés par opération) ; sinon la fraise du document, puis de Mes outils,
        dont le Ø approche le plus l'avant-trou sans le dépasser — jamais moins que la moitié du filetage, qui
        laisserait un noyau au centre ; sinon une fraise créée au Ø de l'avant-trou, à vérifier."""
        from ..cam import toolprefs
        nominal, _pitch, pre = model.THREADS[thread]
        if toolprefs.customized('taraudage', toolprefs.load(self.win.settings)):
            return self._tool_for(s, 'fraise', smallest=True, op_kind='taraudage', create=True)

        def pick(tools):
            fit = [t for t in tools if t.kind == 'fraise' and nominal / 2 + 0.05 <= t.diameter <= pre + 0.05]
            return max(fit, key=lambda t: t.diameter) if fit else None
        t = pick(s.tools)
        if t is not None:
            return t
        lib = pick(self.library_tools())
        if lib is not None:
            return self._copy_tool(s, lib)
        t = model.CamTool(name=tr('Fraise à fileter {0}').format(thread), kind='fraise', diameter=pre)
        t.number = max([x.number for x in s.tools] + [0]) + 1
        s.tools.append(t)
        return t

    def fixture_holes(self, exec_dialog: bool = True, spec=None, plate_layer=None, blanks=None):
        """Plaque de reprise (demande du 14/11) : les bruts posés sur le dessin de la plaque, percés et taraudés aux
        trous de la plaque qu'ils couvrent — un calque de trous TypeEdit (avant-trou du filetage) et, sous M6, UNE
        opération « Perçage-taraudage » (la fraise à fileter perce) ; à partir de M6, un perçage à la fraise puis le
        taraudage (réponse du 16/11). Rend le placement (`cam.fixture.Placement`), None si rien n'est fait."""
        import json
        from ..cam import fixture as FX
        from ..core import holes
        from ..core.document import Layer
        st = self.win.settings
        if spec is None:
            try:
                spec = FX.Spec.from_dict(json.loads(str(st.value(self.FIXTURE_KEY, '') or '{}')))
            except (TypeError, ValueError):
                spec = FX.Spec()
        plate_items = plate_layer.items if plate_layer is not None else []
        if exec_dialog:
            from .fixture_dialog import FixtureDialog
            dlg = FixtureDialog(self, self.doc, spec, self._selected(), placer=self.place_fixture_plate,
                                settings=st, thickness=self.blank_thickness())
            if not dlg.exec():
                return None
            spec, plate_layer, blanks, skip = dlg.spec(), dlg.plate_layer(), dlg.blanks(), dlg.skip()
            plate_items = plate_layer.items if plate_layer is not None else []
        else:
            sel = self._selected()
            if blanks is None:                           # les formes choisies (ni la plaque, ni un cadre)
                blanks = FX.find_blanks(sel, plate_items, spec.min_diameter, spec.max_diameter)
            skip = FX.skip_for(list(sel) + list(plate_items), blanks)   # les cercles des bruts : pas des trous
        st.setValue(self.FIXTURE_KEY, json.dumps(spec.to_dict()))
        pl = FX.layout(blanks, plate_items, spec, skip, logos=FX.engraving_items(self.doc))   # question 45
        if not pl.count() or pl.thread not in model.THREADS:
            self.info.setText(tr('Aucun trou de la plaque sous les bruts : rien n\'est ajouté.') if not pl.count()
                              else tr('Aucun filetage ne passe dans les trous de la plaque : choisissez-le.'))
            return None
        _nominal, _pitch, drill = model.THREADS[pl.thread]
        thickness = self.blank_thickness()
        depth = spec.depth_on(thickness)
        if depth <= 0:                                   # d'après l'épaisseur : rien à tarauder
            self.info.setText(tr("Le brut est trop mince pour être taraudé sous ce qui est usiné en face : rien n’est ajouté."))
            return None
        pre = FX.predrilled(pl.thread)                   # à partir de M6 : prépercé à la fraise
        drilled = spec.drill_on(thickness) if pre else depth
        self.win.push_undo(tr('Trous de fixation des bruts'), with_cam=True)
        layer = Layer(name=tr('Fixation des bruts {0}').format(pl.thread))
        layer.extra[FX.MADE_KEY] = True                  # jamais pris pour la plaque à la fois suivante
        self.doc.layers.append(layer)
        made = [holes.make((round(h.x, 4), round(h.y, 4)), holes.HoleSpec(diameter=drill, depth=drilled),
                           tool=layer.tool) for _b, hs in pl.blanks for h in hs]
        layer.items.extend(made)
        if pre:
            self.add_drilling(made, drilled, drill, name=tr('Perçage à la fraise {0} des bruts').format(pl.thread),
                              exec_dialog=False, mill=True)
            s = self.setup()                              # relu : le perçage vient d'y être enregistré
            tool = self._tool_for(s, 'fraise', smallest=True, op_kind='taraudage', create=True)
            op_name = tr('Taraudage {0} des bruts').format(pl.thread)
        else:                                            # la fraise à fileter perce : une seule opération
            s = self.setup()
            tool = self._thread_mill(s, pl.thread)
            op_name = tr('Perçage-taraudage {0} des bruts').format(pl.thread)
        o = model.Operation(name=op_name, kind='taraudage',
                            tool_id=tool.id if tool is not None else '', depth=depth,
                            thread=pl.thread, items=[it.id for it in made], **self._op_defaults('taraudage'))
        self._finish_new_op(s, o, False, '')
        self.win.modified = True
        canvas = getattr(self.win, 'canvas', None)
        if canvas is not None:
            canvas.invalidate()
            canvas.select(made)
        self.win._on_doc_changed()
        self.refresh()
        from .fixture_dialog import mm
        if pre:
            text = tr('{0} trous de fixation ({1}) sur {2} bruts : perçage et taraudage ajoutés.').format(
                len(made), pl.thread, len(pl.blanks))
        else:
            text = tr('{0} trous de fixation ({1}) sur {2} bruts : perçage-taraudage ajouté, à {3} mm, outil « {4} » (Ø {5}) à vérifier.').format(
                len(made), pl.thread, len(pl.blanks), mm(depth), tool.name, mm(tool.diameter))
        if pl.empty():
            text += ' ' + tr('{0} bruts sans trou de la plaque dessous.').format(len(pl.empty()))
        self.info.setText(text)
        return pl

    def place_fixture_plate(self, path: str, at=None):
        """La plaque de reprise `path` (symbole, DXF…) posée sur un calque neuf, verrouillé, marqué (jamais usiné) :
        centrée sur `at`, sinon sur la plaque du dessin, sinon son coin bas-gauche à l'origine. Rend le calque (None :
        fichier illisible) ; Annuler la retire."""
        import pathlib as _pl
        from ..cam import fixture as FX
        from ..core.document import Layer
        from ..core.geom import Affine
        from .symbols import file_as_group
        try:
            g = file_as_group(path)
        except Exception as ex:                          # fichier illisible : dit, rien n'est posé
            self.info.setText(tr('Plaque illisible : {0}').format(ex))
            return None
        if g is None:
            return None
        plate = self.doc.plate
        if at is None and plate is not None:
            at = (plate.x + plate.width / 2, plate.y + plate.height / 2)
        bb = g.bbox()
        if at is not None:
            g = g.transformed(Affine.translation(float(at[0]), float(at[1])))
        elif bb:                                         # sans plaque : son coin bas-gauche à l'origine
            g = g.transformed(Affine.translation(-bb[0], -bb[1]))
        g.extra.pop('tool_colors', None)                 # un repère : ses couleurs ne changent pas celles du dessin
        self.win.push_undo(tr('Plaque de reprise'), with_cam=True)
        layer = Layer(name=tr('Plaque de reprise : {0}').format(_pl.Path(path).stem), items=[g], locked=True)
        layer.extra[FX.PLATE_LAYER] = {'fichier': str(path)}
        self.doc.active = self.doc.active_layer.id       # le calque actif reste celui du dessin (pas la plaque)
        self.doc.layers.insert(0, layer)                 # sous le dessin
        self.win.modified = True
        canvas = getattr(self.win, 'canvas', None)
        if canvas is not None:
            canvas.invalidate()
        self.win._on_doc_changed()
        self.info.setText(tr('Plaque de reprise posée : {0} (repère, jamais usinée)').format(_pl.Path(path).stem))
        return layer

    def workspace_dialog(self, exec_dialog: bool = True, model=None, setup=None):
        """Espace de travail (table, étaux, mandrins, brides…) de la prise
        `setup` (face vers l'outil, corps ; None : celle montrée dans la vue
        3D, sinon celle du dessin) : gardé avec le dessin ; rend la fenêtre."""
        from ..core import stock3d
        from ..core import workspace as WS
        from .workspace_dialog import WorkspaceDialog
        if setup is None:
            p = getattr(self.win, 'panel3d', None)
            setup = p.current_setup() if p is not None and hasattr(p, 'current_setup') else ('', -1)
        body = int(setup[1])
        face = WS.norm_face(self.doc, setup[0] or '', None, body)     # « dessus » : la prise du dessin (du corps)
        if model is None:
            from ..cam import mill3d
            from ..io import model3d
            src = model3d.source_of(self.doc)
            try:
                model = mill3d.load_model(self.doc, src, face, body) if src else None
            except Exception:                              # noqa: BLE001 — pièce illisible : sans brut placé
                model = None
        box = stock3d.box_for(self.doc, self.setup(), model) if model is not None else None
        dlg = WorkspaceDialog(self, WS.of(self.doc, face, body), box, self.toolpaths, self.setup(),
                              setup_key=(face, body), doc=self.doc)
        if exec_dialog and dlg.exec():
            self.set_workspace(dlg.value(), (face, body))
        return dlg

    def set_workspace(self, ws, setup=('', -1)) -> None:
        """Espace de travail de la prise `setup` gardé avec le dessin ; la vue 3D le montre.
        Une autre prise qui n'a pas le sien et le reçoit inchangé garde celui
        du dessin (pas de copie qui ne suivrait plus ses retouches)."""
        from ..core import workspace as WS
        body = int(setup[1])
        face = WS.norm_face(self.doc, setup[0] or '', None, body)
        if (face, body) != ('', -1) and not WS.own(self.doc, face, body) and \
                ws.to_dict() == WS.of(self.doc, face, body).to_dict():
            return
        WS.store(self.doc, ws, face, body)
        self.win.modified = True
        p = getattr(self.win, 'panel3d', None)
        if p is not None and hasattr(p, 'show_workspace'):
            p.show_workspace()

    def add_stops(self, tps=None) -> list:
        """Arrêts « Retournement de la pièce » ajoutés là où les opérations
        passent à la pièce tournée autrement sans arrêt (cam.preflight.add_stops) ;
        rend les instructions ajoutées (annulable)."""
        from ..cam import preflight as PF
        s = self.setup()
        live = list(tps if tps is not None else self.toolpaths)
        missing = any(lv == PF.BLOQUANT for lv, _t in PF.setup_changes(self.doc, s, live))
        if not missing or not PF.add_stops(self.doc, model.CamSetup.from_dict(s.to_dict()), live):
            self.info.setText(tr('Arrêts déjà là dans l\'ordre des opérations : un parcours a été déplacé à la main '
                                 '(ou vient de TypeEdit) — le remettre à sa place, ou recalculer')
                              if missing else tr('Aucun arrêt ne manque entre les prises'))
            return []
        self.win.push_undo(tr('Ajouter les arrêts entre les prises'), with_cam=True)
        added = PF.add_stops(self.doc, s, live)
        self.save(s)
        for o in added:
            self.compute_op(o)
        self.info.setText(tr('{0} arrêt(s) ajouté(s) entre les prises').format(len(added)))
        return added

    def ops_3d(self) -> list:
        """Opérations qui usinent la pièce 3D."""
        return [o for o in self.setup().operations if o.kind in self.KINDS_3D]

    def compute_op(self, op: model.Operation):
        """Parcours d'une seule opération (le formulaire validé) : calculé et
        mis à sa place dans la liste des parcours, les autres gardés."""
        if self.refresh_dates():                         # textes datés changés : les autres parcours aussi
            self._remember('_placement_states', '')      # (refaits avant l'écriture)
            self._remember('_surface_states', ('?',))
            self._remember('_inputs_states', '?')
        s = self.setup()
        if self._surfaces(s):
            model.store(self.doc, s)
        from ..core import surface2d
        if self._memo('_placement_states') not in (None, self._placement_state()):
            self._remember('_placement_states', '')      # dessin changé depuis le calcul : les autres parcours
        was = self._memo('_surface_states')              # en sont d'avant, même s'il revient comme il était
        if was is not None and was != surface2d.state(self.doc):
            self._remember('_surface_states', ('?',))
        redo = self._rest_after(s, op)                   # « seulement le reste » d'après : refaites avec elle
        if self._inputs_changed(self._memo('_inputs_states'), self._inputs_state(), skip={op.id} | redo, new=False):
            self._remember('_inputs_states', '?')        # objet, outil, autre opération retouchés : d'avant
        op = next((o for o in s.operations if o.id == op.id), op)
        from .progress import Cancelled, run
        self._computing = True
        try:
            if op.link_previous:                         # gamme : la matière laissée par les parcours d'avant
                tp = run(self.win, tr('Calcul du parcours'), self._linked, s, op)
            else:
                tp = run(self.win, tr('Calcul du parcours'), strategies.compute, self.doc, s, op)
        except Cancelled:
            self.info.setText(tr('Calcul annulé'))
            return None
        finally:
            self._computing = False
        order = {o.id: i for i, o in enumerate(s.operations)}
        at = next((i for i, t in enumerate(self.toolpaths) if t.op_id == op.id), None)
        tps = [t for t in self.toolpaths if t.op_id != op.id]
        if at is not None:                               # à la place de l'ancien : l'ordre de la liste gardé
            tps.insert(sum(1 for t in self.toolpaths[:at] if t.op_id != op.id), tp)
        else:                                            # nouveau (arrêt ajouté…) : juste avant le parcours de
            me = order.get(op.id, len(order))            # l'opération suivante (un parcours sans opération
            nxt = next((i for i, t in enumerate(tps) if order.get(t.op_id, -1) > me), None)   # reste devant)
            tps.insert(len(tps) if nxt is None else nxt, tp)
        tps = self._relink_after(s, op, tps)
        strategies.apply_faced_all(s, tps)               # liaisons basses : à jour de ce surfaçage, ou d'après lui
        done = self._memo('_computed')                   # rien de calculé avant : la liste compte
        self._remember('_computed', (done if done is not None else {t.op_id for t in tps if t.op_id}) | {op.id})
        whole = self._memo('_whole')                     # calculée sur tous ses objets, même en mode sélection
        self._remember('_whole', (whole or set()) | {op.id})
        if self._memo('_placement_states') is None:      # rien de calculé avant : la référence de placement
            self._remember('_placement_states', self._placement_state())
        if self._memo('_surface_states') is None:        # et celle des surfaces posées
            self._remember('_surface_states', surface2d.state(self.doc))
        was, now = self._memo('_inputs_states'), self._inputs_state()     # et celle du dessin, des outils,
        if was is None or (isinstance(was, tuple) and len(was) == 3 and len(now) == 3):   # des opérations :
            if len(now) == 3:                            # celle-ci à jour, les autres comme elles étaient (une
                have = {t.op_id for t in tps if t.op_id} if was is None else set(was[2])  # ajoutée sans
                ops = {k: v for k, v in now[2].items() if k in have and k != op.id}       # calcul : refaite)
                if op.id in now[2]:
                    ops[op.id] = now[2][op.id]
                for k in getattr(self, '_relink_stale', ()):     # recalcul annulé : l'ancien parcours n'est pas
                    if k in ops:                                 # à jour (refait avant l'écriture)
                        ops[k] = '?'
                now = (now[0], now[1], ops)
            self._remember('_inputs_states', now)
        self.display(tps)                                # après : la vue 3D les voit à jour
        self.announce_zones()
        return tp

    def announce_zones(self) -> list:
        """Parcours qui signalent des zones du dessin (îles gardées malgré l'arrondi des angles) : elles sont en
        surbrillance orange avec le parcours, et une fenêtre d'information le dit, une fois par calcul. Rend les
        lignes dites."""
        seen = self.__dict__.setdefault('_zones_seen', set())
        new = [tp for tp in self.toolpaths if getattr(tp, 'zones', None) and tp.uid not in seen]
        if not new:
            return []
        seen.update(tp.uid for tp in new)
        lines = [tr('{0} : {1} île(s) plus petite(s) que l\'arrondi des angles, gardée(s) telle(s) quelle(s) ; '
                    'l\'outil en fait le tour sans les arrondir').format(tp.name or '—', len(tp.zones)) for tp in new]
        box = QMessageBox(QMessageBox.Icon.Information, tr('Îles gardées'),
                          '\n'.join(lines) + '\n\n' + tr('Elles sont en surbrillance orange sur le dessin, avec le parcours.'),
                          QMessageBox.StandardButton.Ok, self.win)
        box.setModal(False)
        box.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        box.show()
        self.zones_box = box
        return lines

    def _linked(self, s: model.CamSetup, op: model.Operation, paths=None):
        """Parcours de `op` lié au parcours précédent : avec les parcours des
        opérations actives d'avant (ceux de la liste `paths`, calculés s'il en
        manque)."""
        k = next((i for i, o in enumerate(s.operations) if o.id == op.id), len(s.operations))
        before = [o for o in s.operations[:k] if o.enabled]
        have = {}
        for t in (self.toolpaths if paths is None else paths):
            if t.op_id:
                have.setdefault(t.op_id, t)
        if all(o.id in have for o in before):
            from ..cam import restart
            prev = [restart.whole(have[o.id]) for o in before]      # une reprise ne remet pas la matière enlevée
        else:
            import copy
            prefix = copy.copy(s)
            prefix.operations = list(s.operations[:k])
            prev = strategies.compute_all(self.doc, prefix)
        return strategies.compute_linked(self.doc, s, op, prev)

    def _rest_after(self, s: model.CamSetup, op: model.Operation) -> set:
        """Poches « seulement le reste » actives après `op`, déjà calculées : ce qu'elles usinent dépend de `op`."""
        ids = [o.id for o in s.operations]
        if op.id not in ids:
            return set()
        have = {t.op_id for t in self.toolpaths if t.op_id}
        return {o.id for o in s.operations[ids.index(op.id) + 1:]
                if o.enabled and o.kind == 'poche' and getattr(o, 'rest_previous', False) and o.id in have}

    def _relink_after(self, s: model.CamSetup, op: model.Operation, tps: list) -> list:
        """Opérations liées après `op` déjà calculées : refaites avec le
        nouveau parcours d'avant ; poches « seulement le reste » : d'après
        les poches d'avant."""
        from .progress import Cancelled, run
        ids = [o.id for o in s.operations]
        k = ids.index(op.id) if op.id in ids else len(ids)
        tps = list(tps)
        rest = self._rest_after(s, op)
        self._relink_stale = set()
        for j, o in enumerate(s.operations[k + 1:]):
            at = next((i for i, t in enumerate(tps) if t.op_id == o.id), None)
            if not (o.enabled and (o.link_previous or o.id in rest)) or at is None:
                continue
            try:
                if o.link_previous:
                    tps[at] = run(self.win, tr('Calcul du parcours'), self._linked, s, o, tps)
                else:
                    tps[at] = run(self.win, tr('Calcul du parcours'), strategies.compute, self.doc, s, o)
            except Cancelled:                            # celle-ci et les suivantes gardent leur ancien parcours
                have = {t.op_id for t in tps}
                self._relink_stale = {x.id for x in s.operations[k + 1 + j:]
                                      if x.enabled and (x.link_previous or x.id in rest) and x.id in have}
                break
        return tps

    def new_gamme(self, exec_dialog: bool = True, rough_id: str = '', finish_id: str = '',
                  depth: float = 0.5, mode: str = 'vcarve', *, steps=None, stock: float = 0.0, contour_ref: str = 'surface',
                  skip_frame: bool = False, z_start: float = 0.0):
        """Gamme multi-outils : autant d'outils qu'il faut (TE, pages 619 à 621), classés du plus gros au plus fin. La fenêtre part
        d'une fraise plate et d'un outil conique. Sans fenêtre : `steps` (les lignes, `cam.gamme.Step`), sinon ébauche à la
        fraise plate, puis finition à l'outil conique (gravure 3D, bords et coins) ou reprise des restes."""
        s = self.setup()
        rough = s.tool(rough_id)
        if rough is None:
            big = [t for t in s.tools if t.kind == 'fraise' and t.diameter >= 1.5]
            if big:
                rough = max(big, key=lambda t: t.diameter)
            else:
                rough = model.CamTool(name=tr('Fraise Ø2 (ébauche)'), kind='fraise', diameter=2.0, step_down=0.3,
                                      number=max([x.number for x in s.tools] + [0]) + 1)
                s.tools.append(rough)
        fin = s.tool(finish_id) or self._tool_for(s, 'conique' if mode == 'vcarve' else 'fraise', smallest=True)
        if exec_dialog:
            from ..cam import gamme
            dlg = self.gamme_dialog(s, [gamme.Step(rough.id), gamme.Step(fin.id, 'contournage')], depth)
            if not dlg.exec():
                return None
            steps, depth, stock, contour_ref, skip_frame, z_start = (dlg.steps(), dlg.depth, dlg.stock, dlg.contour_ref,
                                                                     dlg.skip_frame, dlg.z_start)
        if steps is not None:
            return self._gamme_of_steps(s, steps, depth, stock, contour_ref, skip_frame, z_start)
        if fin.diameter >= rough.diameter and mode == 'reste':
            QMessageBox.warning(self, tr('Gamme multi-outils'), tr('La finition doit être plus petite que l\'ébauche.'))
            return None
        scope = self._scope()
        if scope is None:
            self.win.statusBar().showMessage(tr("Sélectionnez d'abord les contours à usiner"), 8000)
            return None
        stock = fin.radius_at(depth) if mode == 'vcarve' else 0.0
        ops = [model.Operation(name=tr('Gamme : ébauche'), kind='poche', tool_id=rough.id, depth=depth,
                               stock=stock, **scope, **self._op_defaults()),
               model.Operation(name=tr('Gamme : finition'), kind=mode, tool_id=fin.id, ref_tool_id=rough.id,
                               depth=depth, **scope, **self._op_defaults())]
        s.operations += ops
        self.save(s)
        self.compute()
        return ops

    def gamme_dialog(self, s, steps: list, depth: float):
        """La fenêtre de la gamme (à part : les essais la remplissent sans l'ouvrir)."""
        from .gamme_dialog import GammeDialog
        return GammeDialog(self, s, steps, depth, library=self.pick_library(), settings=self.win.settings,
                           machine=self._gamme_machine(s))

    def _gamme_machine(self, s) -> tuple:
        """(clé, libellé) de la machine du réglage : « Choisir un outil… » n'y montre que ses outils."""
        key = getattr(s, 'post', '') or ''
        label = self.post.currentText() if hasattr(self, 'post') else key
        return (key, label or key)

    def _gamme_of_steps(self, s, steps: list, depth: float, stock: float, contour_ref: str, skip_frame: bool, z_start: float):
        """Les opérations d'une gamme de plusieurs outils, liées et calculées. None : rien à usiner, ou gamme impossible."""
        from ..cam import gamme
        why = gamme.problem(s, steps, depth)
        if why:
            self.win.statusBar().showMessage(tr(why), 8000)
            return None
        scope = self._scope()
        if scope is None:
            self.win.statusBar().showMessage(tr("Sélectionnez d'abord les contours à usiner"), 8000)
            return None
        ops = gamme.build(s, steps, depth, stock=stock, contour_ref=contour_ref, skip_frame=skip_frame, z_start=z_start,
                          label=tr('Gamme'), **scope, **self._op_defaults())
        s.operations += ops
        self.save(s)
        self.compute()
        return ops

    def _relief_height(self, op) -> float:
        """Hauteur totale des reliefs que `op` usine (0 : pas de relief)."""
        from ..cam import mill3d
        tops = [(float(i.extra['galbe'].get('top', 0.0)), float(i.extra['galbe'].get('base', 0.0)))
                for i in mill3d.relief_images(self.doc, op)]
        return max(t for t, _b in tops) - min(b for _t, b in tops) if tops else 0.0

    def new_relief_gamme(self, exec_dialog: bool = True, tool_ids=None, finish_id: str = '', stock: float = 0.1,
                         depth: float = 0.0):
        """Gamme d'un relief : ébauche au plus gros outil, reprises de ce qu'il a laissé au suivant, du plus
        gros au plus petit, puis finition au choix. `tool_ids` : outils du document (essais)."""
        from ..cam import mill3d
        scope = self._scope()
        if scope is None or not mill3d.relief_images(self.doc, model.Operation(kind='ebauche3d', **scope)):
            self.win.statusBar().showMessage(tr('Sélectionnez le relief à usiner.'), 8000)
            return None
        s = self.setup()
        if exec_dialog:
            answer = self._relief_gamme_dialog(s, stock, depth)
            if answer is None:
                return None
            tool_ids, finish_id, stock, depth = answer
        chosen = [t for t in (s.tool(i) for i in (tool_ids or [])) if t is not None]
        if not chosen:
            QMessageBox.information(self, tr('Gamme relief'), tr('Cochez au moins un outil d’ébauche.'))
            return None
        chosen.sort(key=lambda t: -t.diameter)
        same = [t.diameter for t in chosen]
        if len(set(same)) != len(same):
            QMessageBox.information(self, tr('Gamme relief'), tr('Chaque outil de la gamme doit avoir son diamètre.'))
            return None
        ops, before = [], None
        for t in chosen:
            ops.append(model.Operation(
                name=tr('Gamme relief : ébauche Ø{0}').format(f'{t.diameter:g}') if before is None
                else tr('Gamme relief : reprise Ø{0}').format(f'{t.diameter:g}'),
                kind='ebauche3d' if before is None else 'reprise3d', tool_id=t.id,
                ref_tool_id=before.id if before is not None else '', depth=depth, stock=stock,
                **scope, **self._op_defaults()))
            before = t
        fin = s.tool(finish_id) if finish_id else None
        if fin is not None:
            ops.append(model.Operation(name=tr('Gamme relief : finition'), kind='surface3d', tool_id=fin.id, depth=depth,
                                       **scope, **self._op_defaults()))
        s.operations += ops
        self.save(s)
        self.compute()
        return ops

    def _relief_gamme_dialog(self, s, stock: float, depth: float, run: bool = True):
        """Outils de la gamme ; rend (ébauches, finition, surépaisseur, profondeur) ou None."""
        from PySide6.QtWidgets import QListWidget, QListWidgetItem
        dlg = QDialog(self)
        dlg.setWindowTitle(tr('Gamme relief'))
        f = QFormLayout(dlg)
        from ..cam import toollib
        from .gamme_dialog import chosen_tool, tool_combo
        from .tool_filters import tool_icon
        library = {t.id: t for t in self.pick_library() if t.kind != 'laser'}
        machine = self._gamme_machine(s)
        tools = sorted((t for t in s.tools if t.kind != 'laser'), key=lambda t: -t.diameter)
        rough = QListWidget()

        def rough_row(t, checked: bool):
            it = QListWidgetItem(tool_icon(t), toollib.short_label(t))     # comme la liste des opérations
            it.setToolTip(toollib.summary(t))
            it.setData(Qt.ItemDataRole.UserRole, t.id)
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            it.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
            rough.addItem(it)
        for k, t in enumerate(tools):
            rough_row(t, k == 0 and t.kind == 'fraise')
        more = tool_combo([], library, self.win.settings, none_label=tr('Ajouter une ébauche…'), machine=machine)

        def add_rough(_i: int = 0) -> None:
            """Un outil de Mes outils ou d'une bibliothèque ajouté aux ébauches, coché (copié dans le document)."""
            tid = chosen_tool(more, s, library)
            more.blockSignals(True)
            more.setCurrentIndex(0)
            more._last = 0
            more.blockSignals(False)
            t = s.tool(tid) if tid else None
            if t is None:
                return
            for i in range(rough.count()):
                if rough.item(i).data(Qt.ItemDataRole.UserRole) == tid:
                    rough.item(i).setCheckState(Qt.CheckState.Checked)
                    return
            rough_row(t, True)
        more.currentIndexChanged.connect(add_rough)
        dlg.add_rough = more
        fin = tool_combo(tools, library, self.win.settings, none_label=tr('Aucune'), machine=machine)
        balls = [t for t in tools if t.kind == 'boule']
        if balls:
            fin.setCurrentIndex(max(0, fin.findData(balls[-1].id)))
        sp_stock, sp_depth = QDoubleSpinBox(), QDoubleSpinBox()
        for sp, v in ((sp_stock, stock), (sp_depth, depth)):
            sp.setRange(0.0, 1000.0)
            sp.setDecimals(3)
            sp.setSuffix(' mm')
            sp.setValue(v)
        f.addRow(tr('Ébauche : du plus gros au plus petit'), rough)
        if library:
            f.addRow('', more)
        f.addRow(tr('Finition'), fin)
        f.addRow(tr('Surépaisseur 3D laissée pour la finition : en XY et en Z'), sp_stock)
        f.addRow(tr('Profondeur (0 : toute la hauteur du relief)'), sp_depth)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        f.addRow(bb)
        self._gamme_dlg = dlg
        if run and not dlg.exec():
            return None
        ids = [rough.item(i).data(Qt.ItemDataRole.UserRole) for i in range(rough.count())
               if rough.item(i).checkState() == Qt.CheckState.Checked]
        return ids, chosen_tool(fin, s, library), sp_stock.value(), sp_depth.value()

    # --- réglage ----------------------------------------------------------------------------------
    def setup_menu(self) -> None:
        from PySide6.QtWidgets import QMenu
        from ..cam import templates as TPL
        m = QMenu(self)
        sub = m.addMenu(tr('Appliquer un modèle d\'usinage'))
        allt = TPL.all_templates()
        for name, (origin, tpl) in sorted(allt.items()):
            act = sub.addAction(name + ('' if origin == 'utilisateur' else f'  ({tr(origin)})'))
            act.setToolTip(tpl.get('description', ''))
            act.triggered.connect(lambda _=False, n=name: self.apply_template(n))
        sub.setEnabled(bool(allt))
        sub.setToolTipsVisible(True)
        m.addAction(tr('Enregistrer le réglage comme modèle…'), self.save_template)
        a = m.addAction(tr('Enregistrer l\'opération choisie comme modèle…'), lambda: self.save_op_template())
        a.setEnabled(self._row(self.ops) >= 0)
        m.addAction(tr('Supprimer un de mes modèles…'), self.delete_template)
        m.addSeparator()
        a = m.addAction(tr('Enregistrer les parcours cochés au format TypeEdit (.000, .001…)'),
                        lambda: self.export_typeedit())
        a.setEnabled(bool(self.toolpaths))
        m.addAction(tr('Importer un modèle de parcours TypeEdit (.ttpl)…'), lambda: self.import_ttpl())
        a = m.addAction(tr('Exporter l\'opération choisie en modèle TypeEdit (.ttpl)…'), lambda: self.export_ttpl())
        a.setEnabled(self._row(self.ops) >= 0)
        from ..cam import ttpl as TT
        a = m.addAction(tr('Reprendre les modèles TypeEdit du poste ({0})').format(len(TT.installed())),
                        lambda: self.import_installed_ttpl())
        a.setEnabled(bool(TT.installed()))
        m.addAction(tr('Broche : pince et écrou…'), lambda: self.spindle_dialog())
        m.addAction(tr('Arcs dans les programmes (G2 / G3)…'), lambda: self.arcs_dialog())
        m.addAction(tr('Orientation de sortie…'), lambda: self.orient_dialog())
        m.addAction(tr('Zéro du programme…'), lambda: self.zero_dialog())
        m.addAction(tr('Grouper les programmes…'), lambda: self.group_dialog())
        m.addSeparator()
        a = m.addAction(tr('Fusionner avec les opérations du même outil'), lambda: self.merge_tool_ops())
        a.setEnabled(self._row(self.ops) >= 0)
        m.addAction(tr('Regrouper toutes les opérations par outil'), lambda: self.merge_tool_ops(all_tools=True))
        m.addSeparator()
        from ..io import model3d
        a = m.addAction(tr('Automatisme d\'usinage 3D…'), lambda: self.auto3d())
        a.setToolTip(tr('Pièce 3D (STEP, STL, 3D XML) : ébauche, finitions… d\'un coup, sur toutes ses faces'))
        a.setEnabled(model3d.source_of(self.doc) is not None)
        a = m.addAction(tr('Brut de la pièce 3D…'), lambda: self.stock_dialog())
        a.setToolTip(tr('Bloc, barre ronde ou plaque d\'où la pièce est usinée : l\'ébauche 3D part de son haut'))
        a = m.addAction(tr('Brut du dessin 2D…'), lambda: self.stock2d_dialog())
        a.setToolTip(tr('Plaque ou contour dessiné, marges, surépaisseur au-dessus de la plaque : la simulation part '
                        'de son haut'))
        a = m.addAction(tr('Programmes en série (modèle d\'usinage)…'), lambda: self.win.batch_dialog())
        a.setToolTip(tr('Un modèle d\'usinage appliqué à chaque dessin d\'une liste, son programme écrit : Fichier › '
                        'Traitement par lots'))
        a = m.addAction(tr('Plaque de reprise : trous de fixation des bruts…'), lambda: self.fixture_holes())
        a.setToolTip(tr('Bruts posés sur le dessin d\'une plaque de reprise : percés et taraudés aux trous de la '
                        'plaque qu\'ils couvrent, pour y être vissés'))
        a = m.addAction(tr('Espace de travail (étau, mandrin, brides)…'), lambda: self.workspace_dialog())
        a.setToolTip(tr('Table de la machine et matériel de serrage autour de la pièce : vus en 3D, prise dans les '
                        'mors, collisions de l\'outil et du porte-outil vérifiées'))
        m.addSeparator()
        m.addAction(tr('Coupon d\'essai laser…'), lambda: self.laser_coupon())
        m.addSeparator()
        a = m.addAction(tr('Vérifier avant d\'écrire le programme'))
        a.setCheckable(True)
        a.setChecked(self.preflight_enabled())
        a.toggled.connect(lambda on: self.win.settings.setValue('fao/verifier', bool(on)))
        a = m.addAction(tr('Tenir un journal des exports (à côté du programme)'))
        a.setCheckable(True)
        a.setChecked(self.journal_enabled())
        a.toggled.connect(lambda on: self.win.settings.setValue('fao/journal', bool(on)))
        a = m.addAction(tr('Dates des textes mises au jour du calcul'))
        a.setCheckable(True)
        a.setChecked(self.dates_enabled())
        a.setToolTip(tr('Les textes avec |Date| ou |Heure| prennent la date du moment à chaque calcul des parcours'))
        a.toggled.connect(lambda on: self.win.settings.setValue('fao/dates', bool(on)))
        m.addSeparator()
        m.addAction(tr('Importer un réglage FAO…'), self.import_setup)
        m.addAction(tr('Exporter le réglage FAO…'), self.export_setup)
        m.exec(self.cursor().pos())
        m.deleteLater()                                   # menu ponctuel : libéré (sinon un par clic)

    # --- coupon d'essai laser -------------------------------------------------------------------------
    def _motif(self) -> list:
        """Contours du dessin sélectionné (motif des cases du coupon)."""
        from ..core.document import Group
        out = []

        def walk(it):
            if isinstance(it, Group):
                for ch in it.children:
                    walk(ch)
                return
            g = strategies.item_geometry(it)
            if g is not None:
                out.extend(c for c in g.contours if c.closed or len(c.segments))
        for it in self._selected():
            walk(it)
        return out

    def laser_coupon(self, *, exec_dialog: bool = True, spec=None, tool=None, use_motif: bool = False):
        """Coupon d'essai laser (cam.coupon) : les cases et leurs étiquettes
        ajoutées au dessin (groupées, au centre de la plaque), une opération
        par case et les copies de l'outil au réglage FAO. Rend le coupon."""
        from ..cam import coupon as CP
        s = self.setup()
        if exec_dialog:
            from .coupon_dialog import CouponDialog
            dlg = CouponDialog(self, [t for t in s.tools if t.kind == 'laser'], motif_ok=bool(self._motif()),
                               font=str(self.win.settings.value('texte/police', 'Arial')))
            if not dlg.exec():
                return None
            spec, tool, use_motif = dlg.spec(), dlg.base_tool(), dlg.use_motif()
        spec = spec or CP.Spec()
        if tool is None:
            tool = next((t for t in s.tools if t.kind == 'laser'), None) or model.CamTool(**DEFAULT_TOOLS['laser'])
        plate = self.doc.plate
        if plate is not None:
            spec.center = (plate.x + plate.width / 2, plate.y + plate.height / 2)
        c = CP.build(spec, tool, motif=self._motif() if use_motif else None)
        self.win.push_undo(tr('Coupon d\'essai laser'), with_cam=True)
        self.doc.add(c.group)
        s.tools += c.tools
        s.operations += c.operations
        model.store(self.doc, s)
        self.win.modified = True
        self.win.canvas.invalidate()
        self.win.canvas.select([c.group])
        self.win._on_doc_changed()
        self.refresh()
        self.info.setText(tr('Coupon d\'essai : {0} cases, {1} opérations ajoutées').format(
            c.cells, len(c.operations)))
        return c

    # --- modèles d'usinage ---------------------------------------------------------------------------
    def apply_template(self, name: str, *, exec_dialog: bool = True, sources=None, replace: bool = False,
                       items=None, prefer: str | None = None) -> list:
        """Applique le modèle `name` au réglage du dessin ; rend le compte rendu.
        `items` : les objets à usiner (formes choisies) au lieu des couleurs ; `prefer` : le choix « Usiner » d'office
        dans la fenêtre ('objets' : les formes sélectionnées, s'il y en a)."""
        from ..cam import templates as TPL
        found = TPL.all_templates().get(name)
        if found is None:
            return []
        tpl = found[1]
        if exec_dialog:
            dlg = QDialog(self)
            dlg.setWindowTitle(tr('Modèle d\'usinage'))
            f = QFormLayout(dlg)
            f.addRow(QLabel(f'<b>{name}</b>'))
            if tpl.get('description'):
                lab = QLabel(tpl['description'])
                lab.setWordWrap(True)
                f.addRow(lab)
            f.addRow(QLabel(tr('{0} opération(s), {1} outil(s)').format(len(tpl.get('operations') or []),
                                                                        len(tpl.get('tools') or []))))
            src = QComboBox()
            src.addItem(tr('Couleurs prévues par le modèle'), 'modele')
            if self.win.canvas.selection:
                src.addItem(tr('Objets sélectionnés seulement'), 'objets')
                src.addItem(tr('Couleurs des objets sélectionnés'), 'selection')
            src.addItem(tr('Couleur du calque actif'), 'calque')
            src.addItem(tr('Toutes les couleurs'), 'toutes')
            if prefer and src.findData(prefer) >= 0:
                src.setCurrentIndex(src.findData(prefer))
            f.addRow(tr('Usiner'), src)
            rep = QCheckBox(tr('Remplacer les opérations du dessin'))
            f.addRow(rep)
            bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
            bb.accepted.connect(dlg.accept)
            bb.rejected.connect(dlg.reject)
            f.addRow(bb)
            if not dlg.exec():
                return []
            replace = rep.isChecked()
            choice = src.currentData()
            if choice == 'objets':
                items = [it.id for it in self.win.canvas.selection]
                sources = []
            elif choice == 'selection':
                sources = sorted({it.tool for it in self.win.canvas.selection})
            elif choice == 'calque':
                sources = [self.win.canvas.current_tool_index]
            elif choice == 'toutes':
                sources = []
        elif prefer == 'objets' and items is None and sources is None and self.win.canvas.selection:
            items = [it.id for it in self.win.canvas.selection]      # sans fenêtre : les formes sélectionnées aussi
            sources = []
        self.win.push_undo(tr("Modèle d'usinage"), with_cam=True)    # (un process d'un clic : Ctrl+Z le retire)
        s, report = TPL.apply(self.setup(), tpl, sources=sources, replace=replace, items=items)
        self.save(s)
        self.info.setText(tr('Modèle « {0} » : {1}').format(name, ' ; '.join(report)))
        return report

    def save_template(self, name: str | None = None, description: str = '') -> dict | None:
        from PySide6.QtWidgets import QInputDialog
        from ..cam import templates as TPL
        s = self.setup()
        if not s.operations:
            QMessageBox.information(self, tr('Modèle d\'usinage'), tr('Aucune opération à enregistrer.'))
            return None
        if name is None:
            name, ok = QInputDialog.getText(self, tr('Modèle d\'usinage'), tr('Nom du modèle'))
            if not ok or not name.strip():
                return None
            description, _ok = QInputDialog.getText(self, tr('Modèle d\'usinage'), tr('Description (facultative)'))
        tpl = TPL.from_setup(s, name.strip(), description.strip())
        TPL.save_user(tpl)
        self.info.setText(tr('Modèle « {0} » enregistré').format(name.strip()))
        pal = getattr(self.win, 'cam_palette', None)     # plusieurs opérations : dans « Mes process », tout de suite
        if pal is not None:
            pal.refresh()
        return tpl

    def add_to_process(self, name: str | None = None) -> str | None:
        """« Ajouter aux process » (bouton à côté du programme) : les opérations du dessin en process, dans « Mes
        process » de la palette (nom demandé si `name` est None). Rend son nom (None : rien d'enregistré)."""
        pal = getattr(self.win, 'cam_palette', None)
        return pal.save_process(name) if pal is not None else None

    def save_op_template(self, name: str | None = None, description: str = '') -> dict | None:
        """Le formulaire de l'opération choisie (et son outil), enregistré pour
        servir sur d'autres formes."""
        from PySide6.QtWidgets import QInputDialog
        from ..cam import templates as TPL
        s = self.setup()
        r = self._row(self.ops)
        if r < 0:
            QMessageBox.information(self, tr('Modèle d\'usinage'), tr('Choisir d\'abord une opération.'))
            return None
        op = s.operations[r]
        if name is None:
            name, ok = QInputDialog.getText(self, tr('Modèle d\'opération'), tr('Nom du modèle'),
                                            text=op.name or tr(model.op_kinds().get(op.kind, op.kind)))
            if not ok or not name.strip():
                return None
        tpl = TPL.from_operation(s, op, name.strip(), description.strip())
        TPL.save_user(tpl)
        self.info.setText(tr('Modèle « {0} » enregistré : à appliquer sur d\'autres formes '
                             '(Réglage ▸ Appliquer un modèle)').format(name.strip()))
        return tpl

    #: dossier des modèles .ttpl repris de TypeEdit
    TTPL_FOLDER = 'TypeEdit — modèles .ttpl'

    def import_ttpl(self, path: str | None = None) -> dict | None:
        """Modèle de parcours TypeEdit (.ttpl) → modèle d'usinage."""
        from ..cam import templates as TPL, ttpl as TT
        if not path:
            start = next((str(p.parent) for p in TT.installed()), '')
            path, _ = QFileDialog.getOpenFileName(self, tr('Modèle de parcours TypeEdit'), start,
                                                  tr('Modèles de parcours TypeEdit (*.ttpl)'))
            if not path:
                return None
        try:
            tpl = TT.read(path)
        except (OSError, ValueError) as ex:
            QMessageBox.warning(self, tr('Modèle de parcours TypeEdit'), str(ex))
            return None
        tpl['dossier'] = self.TTPL_FOLDER                    # rangé à part, pas mêlé aux autres modèles
        tpl['name'] = 'TypeEdit : ' + tpl['name']
        TPL.save_user(tpl)
        self.info.setText(tr('Modèle « {0} » repris de TypeEdit').format(tpl['name']))
        return tpl

    def import_installed_ttpl(self) -> int:
        from ..cam import ttpl as TT
        n = sum(1 for p in TT.installed() if self.import_ttpl(str(p)) is not None)
        self.info.setText(tr('{0} modèle(s) de parcours TypeEdit repris').format(n))
        return n

    def export_ttpl(self, path: str | None = None) -> pathlib.Path | None:
        """L'opération choisie (et son outil) en modèle de parcours TypeEdit."""
        from ..cam import templates as TPL, ttpl as TT
        s = self.setup()
        r = self._row(self.ops)
        if r < 0:
            return None
        op = s.operations[r]
        tpl = TPL.from_operation(s, op, op.name or tr(model.op_kinds().get(op.kind, op.kind)))
        if not path:
            path, _ = QFileDialog.getSaveFileName(self, tr('Modèle de parcours TypeEdit'),
                                                  f'{tpl["name"]}.ttpl', tr('Modèles de parcours TypeEdit (*.ttpl)'))
            if not path:
                return None
        out = TT.write(tpl, path)
        self.info.setText(tr('Modèle de parcours TypeEdit écrit : {0}').format(pathlib.Path(out).name))
        return out

    def delete_template(self) -> None:
        from PySide6.QtWidgets import QInputDialog
        from ..cam import templates as TPL
        names = sorted(TPL.user_templates())
        if not names:
            QMessageBox.information(self, tr('Modèle d\'usinage'), tr('Aucun modèle enregistré.'))
            return
        name, ok = QInputDialog.getItem(self, tr('Supprimer un modèle'), tr('Modèle'), names, 0, False)
        if ok and name:
            TPL.delete_user(name)

    def import_setup(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, tr('Réglage FAO'), '', 'JSON (*.json)')
        if path:
            data = json.loads(pathlib.Path(path).read_text(encoding='utf-8'))
            s = model.CamSetup.from_dict(data)
            for o in s.operations:
                o.body3d_ref = {}                       # volumes d'un autre dessin : le numéro seul
            self.save(s)

    def export_setup(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, tr('Réglage FAO'), 'fao.json', 'JSON (*.json)')
        if path:
            pathlib.Path(path).write_text(json.dumps(self.setup().to_dict(), indent=1, ensure_ascii=False),
                                          encoding='utf-8')

    # --- parcours ------------------------------------------------------------------------------------
    def display(self, toolpaths) -> None:
        self.toolpaths = list(toolpaths)
        for tp in self.toolpaths:
            if not hasattr(tp, 'shown'):
                tp.shown = True
        self._loading = True
        self.paths.clear()
        ops = self.setup().operations if self.toolpaths else []
        linked = {o.id for o in ops if o.link_previous}
        known = {o.id for o in ops}
        for i, tp in enumerate(self.toolpaths):
            it = QListWidgetItem(swatch(path_colors()[i % len(path_colors())]),
                                 ('↳ ' if tp.op_id and tp.op_id in linked else '') +
                                 ('TE ' if tp.source == 'typeedit' else '') + (tp.name or '—'))
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            it.setCheckState(Qt.CheckState.Checked if tp.shown else Qt.CheckState.Unchecked)
            self.paths.addItem(it)
        # réponse 13 du 14/11 : un parcours sans opération (programme lu, parcours TypeEdit) est une ligne du tableau
        # des opérations, après elles ; la liste des parcours, dans leur ordre d'écriture, ne se montre que pour des
        # parcours écrits dans un autre ordre (réglé à la main, ou un parcours sans opération entre deux opérations)
        rank = {o.id: k for k, o in enumerate(ops)}
        order = [rank[tp.op_id] if tp.op_id in known else len(ops) for tp in self.toolpaths]
        self.paths_group.setVisible(order != sorted(order))
        self._fill_loose_rows()
        self._sync_eyes()
        self._sync_retarget()
        self._loading = False
        self._repaint_paths()
        self._report()
        lp = getattr(self.win, 'layers_panel', None)
        if lp is not None and (self.toolpaths or getattr(self, '_traj_row', False)):
            lp.refresh()                                    # ligne « Trajectoires » : ajoutée ou retirée
        self._traj_row = bool(self.toolpaths)
        self._fill_ops3d()                                  # « calculé », « à calculer »
        p3 = getattr(self.win, 'panel3d', None)
        if p3 is not None:                                  # trajectoires en 3D aussi
            p3.stale = True
            if hasattr(self.win, '_refresh_3d_if_visible'):
                self.win._refresh_3d_if_visible()

    def _repaint_paths(self) -> None:
        self.win.canvas.set_toolpaths([(tp, path_colors()[i % len(path_colors())])
                                       for i, tp in enumerate(self.toolpaths) if tp.shown])

    def checked_paths(self) -> list:
        return [tp for tp in self.toolpaths if tp.shown]

    def _path_checked(self, item) -> None:
        if self._loading:
            return
        r = self.paths.row(item)
        if 0 <= r < len(self.toolpaths):
            self.toolpaths[r].shown = item.checkState() == Qt.CheckState.Checked
            self._sync_eyes()
            self._repaint_paths()
            self._report()
            self._schedule_3d()
            lp = getattr(self.win, 'layers_panel', None)
            if lp is not None and hasattr(lp, 'sync_paths'):
                lp.sync_paths()                             # la ligne du parcours sous Trajectoires

    def set_path_shown(self, i: int, on: bool) -> None:
        """Un parcours montré ou caché (sa ligne sous Trajectoires) : comme sa case dans la liste des parcours."""
        if 0 <= i < self.paths.count():
            want = Qt.CheckState.Checked if on else Qt.CheckState.Unchecked
            if self.paths.item(i).checkState() != want:
                self.paths.item(i).setCheckState(want)      # _path_checked : dessin, durée, vue 3D

    def toolpath_form(self, tp, exec_dialog: bool = True):
        """Calque Trajectoires, double-clic sur un parcours : le formulaire complet de son opération ; validé, le parcours
        est recalculé. Un parcours lu d'un programme (SimPL, ISO…) n'a pas d'opération : `program_form`. Rend la fenêtre."""
        s = self.setup()
        k = next((i for i, o in enumerate(s.operations) if tp.op_id and o.id == tp.op_id), -1)
        if k < 0:
            return self.program_form(tp, exec_dialog)
        self._select_row(self.ops, k)
        return self.edit_op(exec_dialog=exec_dialog, take_selection=False)

    def program_form(self, tp, exec_dialog: bool = True):
        """L'opération d'un parcours lu d'un programme, faite d'après lui : un tracé (son trajet repris, au centre de
        l'outil), l'outil du réglage ou reconnu à son libellé (sinon une fraise à régler), la profondeur et le nombre de
        passes du programme. Le formulaire complet s'ouvre ; validé, le trajet entre dans un calque du dessin, l'opération
        dans le réglage, et son parcours calculé remplace celui du programme, à sa place. Rend la fenêtre (None : rien à
        reprendre)."""
        from ..core import geom
        from ..core.document import Layer, Shape
        s = self.setup()
        lines = tp.drawing()
        if not lines:
            self.info.setText(tr('Rien à reprendre : ce parcours n\'a pas d\'avance'))
            return None
        cuts = [m.z for m in tp.moves if m.kind != 'rapid' and m.z < -1e-6]
        depth = round(-min(cuts), 4) if cuts else 0.1
        levels = {round(m.z, 3) for m in tp.moves if m.kind == 'feed' and m.z < -1e-6}
        tool, new_tool = self.program_tool(tp)
        if tool is None:                                    # outil inconnu, création annulée
            return None
        shapes, seen = [], set()
        for c in lines:
            key = tuple((round(x, 3), round(y, 3)) for x, y in c)
            if key in seen or key[::-1] in seen:            # même trajet à une autre passe : repris une fois
                continue
            seen.add(key)
            shut = len(c) > 3 and math.dist(c[0], c[-1]) < 1e-6
            shapes.append(Shape(path=geom.Path([geom.polyline(c[:-1] if shut else c, closed=shut)])))
        op = model.Operation(kind='gravure', name=tp.name or tr('Programme'), tool_id=tool.id,
                             items=[sh.id for sh in shapes], depth=depth,
                             step_down=round(depth / len(levels), 4) if len(levels) > 1 else depth)
        dlg = FieldsDialog(self, None, op, self.doc, list(s.tools) + ([tool] if new_tool else []),
                           library=self.pick_library(), kind_choice=True)  # programme relu : nature devinée, à choisir

        def done(ok) -> None:
            if not ok:
                return
            dlg.apply()
            self.win.push_undo()
            self.doc.layers.append(Layer(name=tr('Programme : {0}').format(tp.name or '—'), items=shapes))
            if new_tool and op.tool_id == tool.id:          # outil gardé au formulaire : dans le réglage
                s.tools.append(tool)
            s.tools.extend(dlg.new_tools)
            s.operations.append(op)
            self.save(s)
            at = next((i for i, t in enumerate(self.toolpaths) if t is tp), len(self.toolpaths))
            self.display([t for t in self.toolpaths if t is not tp])
            new = self.compute_op(op)
            if new is not None and new in self.toolpaths:      # à la place du parcours du programme
                rest = [t for t in self.toolpaths if t is not new]
                rest.insert(min(at, len(rest)), new)
                self.display(rest)
            self.win.canvas.invalidate()
            self.win._on_doc_changed()
        if not exec_dialog:
            dlg.finished.connect(lambda res: done(res == QDialog.DialogCode.Accepted))
            return dlg
        done(dlg.exec())
        return dlg

    def program_tool(self, tp) -> tuple:
        """L'outil du document pour un parcours lu d'un programme : le même que celui du programme, jamais un autre.
        Un outil du document de même référence (ou de même nom) ; sinon l'outil reconnu dans une bibliothèque (Mes
        outils, tools.json de l'atelier…), copié ; sinon l'outil est inconnu : `ask_program_tool` propose de le créer,
        sa référence (ou son numéro, Cielle), sa broche et ses avances préremplies — il rejoint alors Mes outils. Rend
        (outil, à ajouter au document) ; (None, False) : annulé."""
        from ..cam import ncread
        s = self.setup()
        mine = next((t for t in s.tools if t.id == tp.tool_id), None)
        if mine is not None:
            return mine, False
        info = dict(getattr(tp, 'tool_info', None) or {})
        guess = getattr(tp, 'tool_guess', None)
        known = guess is not None and bool(getattr(tp, 'tool_source', ''))      # outil d'une bibliothèque
        given = str(info.get('name') or '').strip()     # le nom du programme : un outil sans référence s'y reconnaît
        if known and getattr(tp, 'tool_alias', False):  # un autre outil choisi à sa place : celui-là seulement
            keys, ref = [{'ref': guess.ref}, {'name': guess.name}], guess.ref
        else:
            keys = [info, {'name': given}]              # (l'outil proposé porte ce nom entier)
            if known:                                   # jamais le nom donné à une proposition (« T3 »)
                keys += [{'ref': guess.ref}, {'name': guess.name}]
            ref = info.get('ref') or (guess.ref if guess is not None else '')
        for key in keys:                                # même nom, autre référence : un autre outil
            same = next((t for t in s.tools if any(key.values()) and ncread.same_identity(t, key)
                         and not ncread.other_ref(t, ref)), None)
            if same is not None:
                return same, False
        used = {t.number for t in s.tools}

        def placed(t):
            c = model.CamTool.from_dict(t.to_dict())
            c.id, c.folder = model.new_id(), ''
            if info.get('number'):
                c.number = int(info['number'])
            if c.number in used or c.number <= 0:
                c.number = max(used | {0}) + 1
            return c
        if guess is not None and getattr(tp, 'tool_source', ''):
            return placed(guess), True                  # reconnu dans une bibliothèque : le même, copié
        prop = guess or model.CamTool(name=info.get('name') or tr('Outil du programme'), kind='fraise', diameter=1.0)
        choice = self.ask_program_tool(tp, prop)
        if choice == 'cancel':
            return None, False
        if choice == 'pick':                            # un outil existant à sa place
            got = self.choose_program_tool(tp)
            if got is None:
                return None, False
            if any(t.id == got.id for t in s.tools):
                return got, False
            return placed(got), True
        tool = placed(prop)
        if choice == 'create':
            dlg = FieldsDialog(self, tr('Nouvel outil, d’après le programme'), tool)
            ok = dlg.exec()
            if ok:
                dlg.apply()
            dlg.deleteLater()
            if not ok:
                return None, False
            if self.save_program_tool(tool):            # les parcours lus du même outil : reconnus (plus de « ? »)
                self.set_program_tool(tp, tool, True, 'Mes outils')
        return tool, True

    def ask_program_tool(self, tp, tool) -> str:
        """Outil d'un programme inconnu des bibliothèques : 'create' (le créer, valeurs du programme préremplies),
        'pick' (choisir un outil existant à sa place), 'keep' (continuer sans l'enregistrer), 'cancel'."""
        from ..cam import ncread
        info = getattr(tp, 'tool_info', None) or {}
        what = info.get('name') or tool.name
        ref = info.get('ref') or (f'T{info["number"]}' if info.get('number') else '')
        names = ', '.join(tr(n) for n, _t in ncread.libraries())
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle(tr('Outil du programme'))
        box.setText(tr('L’outil « {0} »{1} n’est dans aucune bibliothèque ({2}).').format(
            what, f' ({ref})' if ref else '', names or tr('Mes outils')))
        box.setInformativeText(tr('Le créer d’après le programme ? Sa référence (ou son numéro), sa broche et ses '
                                  'avances sont préremplies ; il rejoint Mes outils (dossier « {0} ») et le document.')
                               .format(tr(ncread.PROGRAM_FOLDER)) + '\n' +
                               tr('Ou choisir un outil existant à sa place (document, Mes outils, bibliothèques).'))
        create = box.addButton(tr('Créer l’outil…'), QMessageBox.ButtonRole.AcceptRole)
        pick = box.addButton(tr('Choisir un outil existant…'), QMessageBox.ButtonRole.ActionRole)
        keep = box.addButton(tr('Continuer sans l’enregistrer'), QMessageBox.ButtonRole.ActionRole)
        box.addButton(QMessageBox.StandardButton.Cancel)
        box.exec()
        got = box.clickedButton()
        box.deleteLater()
        return 'create' if got is create else 'pick' if got is pick else 'keep' if got is keep else 'cancel'

    def choose_program_tool(self, tp, exec_dialog: bool = True):
        """Un outil existant (du document, de Mes outils, des bibliothèques des plugins) à la place de celui d'un
        programme lu, pour tous ses parcours du même outil (`set_program_tool`). « Retenir ce choix pour les prochaines
        fois » (cochée) : reconnu aux prochaines lectures ; décochée : pour cette fois, l'association d'avant oubliée.
        Rend l'outil choisi (None : annulé), ou la fenêtre sans l'ouvrir si `exec_dialog` est faux."""
        from ..cam import toollib
        from .tool_picker import ProgramToolDialog
        s = self.setup()
        sources: dict = {}
        lib = {t.id: t for t in toollib.with_plugins(self.library_tools(), sources)}
        guess = getattr(tp, 'tool_guess', None)
        cur = tp.tool_id if tp.tool_id and any(t.id == tp.tool_id for t in s.tools) else None
        if cur is None and guess is not None and getattr(tp, 'tool_source', ''):
            hit = toollib.find_match(guess, list(lib.values()))
            cur = 'lib:' + hit.id if hit is not None else None
        dlg = ProgramToolDialog(self, list(s.tools), lib, cur, self.win.settings,
                                info=getattr(tp, 'tool_info', None) or {},
                                can_create=cur is None and not getattr(tp, 'tool_source', ''))

        def done(ok):
            key = dlg.choice if ok else None
            if not key:
                return None
            if key == ProgramToolDialog.CREATE:         # inconnu : le créer d'après le programme
                return self.create_program_tool(tp)
            if isinstance(key, str) and key.startswith('lib:'):
                tool, src = lib.get(key[4:]), sources.get(key[4:], 'Mes outils')
            else:
                tool, src = next((t for t in s.tools if t.id == key), None), ''
            if tool is None:
                return None
            self.set_program_tool(tp, tool, dlg.remember.isChecked(), src)
            return tool
        if not exec_dialog:
            dlg.finished.connect(lambda r: done(r == QDialog.DialogCode.Accepted))
            dlg.finished.connect(lambda _r: dlg.deleteLater())
            return dlg
        try:
            return done(dlg.exec() == QDialog.DialogCode.Accepted)
        finally:
            dlg.deleteLater()

    def set_program_tool(self, tp, tool, keep: bool = True, source: str = '') -> int:
        """L'outil `tool` (du document, sinon de la bibliothèque `source`) à la place de celui du programme de `tp`, sur
        tous les parcours lus du même outil. `keep` : retenu pour les prochaines lectures (un outil du document absent
        des bibliothèques rejoint aussi Mes outils, pour y être retrouvé) ; sinon l'association d'avant est oubliée.
        Rend le nombre de parcours changés."""
        from ..cam import ncread, toollib
        s = self.setup()
        info = dict(getattr(tp, 'tool_info', None) or {})
        in_doc = any(t.id == tool.id for t in s.tools)
        same = [p for p in self.toolpaths if p is not tp and not p.op_id and ncread.program_key(info)
                and ncread.same_program_tool(info, getattr(p, 'tool_info', None) or {})]
        for p in [tp] + same:
            p.tool_id = tool.id if in_doc else ''
            p.tool_guess = tool
            p.tool_source = (source or 'Outils du document') if in_doc else (source or 'Mes outils')
            p.tool_alias = True
        keep = keep and bool(ncread.program_key(info))   # un programme qui ne nomme pas l'outil : rien à retenir
        saved = True
        try:
            if keep:                                     # un outil d'une bibliothèque (`source`) y est déjà ;
                if not source and not any(toollib.find_match(tool, tools) is not None
                                          for _n, tools in ncread.libraries()):
                    saved = self.save_program_tool(tool)  # outil du document seulement : dans Mes outils
                if saved:
                    ncread.remember(info, tool)
            else:
                ncread.forget(info)
        except OSError as ex:
            self.win.statusBar().showMessage(tr('Associations des outils illisibles : {0}').format(ex), 8000)
        else:
            if saved:                                    # sinon le message d'échec de Mes outils reste affiché
                self.win.statusBar().showMessage(
                    (tr('Outil « {0} » retenu pour « {1} »') if keep else
                     tr('Outil « {0} » pour « {1} », cette fois'))
                    .format(tool.name, info.get('name') or info.get('ref') or tp.name or '—'), 6000)
        lp = getattr(self.win, 'layers_panel', None)
        if lp is not None:
            lp.refresh()
        return 1 + len(same)

    def create_program_tool(self, tp, exec_dialog: bool = True):
        """L'outil inconnu d'un programme créé d'après lui (référence ou numéro, broche, avances préremplies) : dans
        Mes outils (dossier « Outils des programmes »), reconnu sur tous les parcours du même outil. Rend l'outil
        (None : annulé), ou la fenêtre sans l'ouvrir si `exec_dialog` est faux."""
        info = getattr(tp, 'tool_info', None) or {}
        prop = getattr(tp, 'tool_guess', None) or model.CamTool(name=info.get('name') or tr('Outil du programme'),
                                                                 kind='fraise', diameter=1.0)
        tool = model.CamTool.from_dict(prop.to_dict())
        tool.id, tool.folder = model.new_id(), ''
        dlg = FieldsDialog(self, tr('Nouvel outil, d’après le programme'), tool)

        def done(ok):
            if not ok:
                return None
            dlg.apply()
            if not self.save_program_tool(tool):
                return None
            self.set_program_tool(tp, tool, True, 'Mes outils')
            return tool
        if not exec_dialog:
            dlg.finished.connect(lambda r: done(r == QDialog.DialogCode.Accepted))
            dlg.finished.connect(lambda _r: dlg.deleteLater())
            return dlg
        try:
            return done(dlg.exec())
        finally:
            dlg.deleteLater()

    def unknown_program_tools(self, tps) -> list:
        """Les parcours lus dont l'outil n'est dans aucune bibliothèque : un par outil du programme."""
        from ..cam import ncread
        ids = {t.id for t in self.setup().tools}
        out = []
        for p in tps:
            if p.op_id or (p.tool_id and p.tool_id in ids) or getattr(p, 'tool_guess', None) is None \
                    or getattr(p, 'tool_source', ''):
                continue
            info = getattr(p, 'tool_info', None) or {}
            if ncread.program_key(info) and any(ncread.same_program_tool(info, getattr(q, 'tool_info', None) or {})
                                                for q in out):
                continue
            out.append(p)
        return out

    def offer_unknown_tools(self, tps, show: bool = True):
        """À la lecture d'un programme : ses outils inconnus des bibliothèques, à créer ou à remplacer par un outil
        existant, dans une fenêtre non modale (option FAO). Rend la fenêtre (None : rien d'inconnu)."""
        from .options import value
        if not value(self.win.settings, 'fao/outils_inconnus'):
            return None
        seen = {id(p) for p in tps}                     # et ceux des programmes lus avant, encore inconnus
        todo = self.unknown_program_tools(list(tps) + [p for p in self.toolpaths if id(p) not in seen])
        if not todo:
            return None
        from .tool_picker import UnknownToolsDialog
        old = getattr(self, '_unknown_dlg', None)
        if old is not None:
            try:
                old.close()
            except RuntimeError:                            # déjà détruite
                pass
        dlg = self._unknown_dlg = UnknownToolsDialog(self, todo)
        if show:
            dlg.show()
            dlg.raise_()
        return dlg

    def save_program_tool(self, tool) -> bool:
        """Un outil créé d'après un programme : copié dans Mes outils (dossier « Outils des programmes »)."""
        from ..cam import ncread, toollib
        path = toollib.default_path()
        try:
            mine = toollib.load(path) if path.exists() else []
            folders = toollib.load_folders(path) if path.exists() else []
            c = model.CamTool.from_dict(tool.to_dict())
            c.id, c.folder = model.new_id(), ncread.PROGRAM_FOLDER
            toollib.save(mine + [c], path, folders)
        except (OSError, ValueError) as ex:
            self.win.statusBar().showMessage(tr('Mes outils illisible : {0}').format(ex), 8000)
            return False
        self.win.statusBar().showMessage(tr('Outil « {0} » ajouté à Mes outils').format(tool.name), 6000)
        return True

    def _schedule_3d(self) -> None:
        """Vue 3D refaite avec les parcours cochés, après une pause (plusieurs clics : un seul calcul)."""
        p3 = getattr(self.win, 'panel3d', None)
        if p3 is None:
            return
        p3.stale = True
        t = getattr(self, '_3d_timer', None)
        if t is None:
            from PySide6.QtCore import QTimer
            t = self._3d_timer = QTimer(self)
            t.setSingleShot(True)
            t.setInterval(400)
            t.timeout.connect(lambda: hasattr(self.win, '_refresh_3d_if_visible') and self.win._refresh_3d_if_visible())
        t.start()

    def move_path(self, d: int) -> None:
        r = self.paths.currentRow()
        if r < 0 or not 0 <= r + d < len(self.toolpaths):
            return
        t = self.toolpaths
        t[r], t[r + d] = t[r + d], t[r]
        self.display(t)
        self.paths.setCurrentRow(r + d)

    def remove_path(self) -> None:
        r = self.paths.currentRow()
        if r >= 0:
            del self.toolpaths[r]
            self.display(self.toolpaths)

    def reverse_path(self) -> None:
        """Parcours parcouru à l'envers (les arcs changent de sens)."""
        r = self.paths.currentRow()
        if r < 0:
            return
        from ..cam.edit import reversed_toolpath
        tp = reversed_toolpath(self.toolpaths[r])
        tp.reversed = not getattr(self.toolpaths[r], 'reversed', False)     # gardé si tout est recalculé
        self.toolpaths[r] = tp
        self.display(self.toolpaths)
        self.paths.setCurrentRow(r)

    def export_typeedit(self) -> None:
        from ..cam import typeedit
        tps = self.current_paths()
        if not tps:
            return
        base, _ = QFileDialog.getSaveFileName(self, tr('Parcours TypeEdit'), str(self.program_dir() / 'parcours.000'),
                                              tr('Parcours TypeEdit (*.000)'))
        if not base:
            return
        stem = pathlib.Path(base).with_suffix('')
        s = self.setup()
        for i, tp in enumerate(tps):
            t = s.tool(tp.tool_id)
            kw = dict(tool_number=t.number, tool_diameter=t.diameter, tool_angle=t.angle, tool_tip=t.tip) if t else {}
            typeedit.write(tp, f'{stem}.{i:03d}', comment=tp.name, **kw)
        self.info.setText(tr('{0} parcours enregistrés : {1}.000 …').format(len(tps), stem.name))
        self._remember_program(pathlib.Path(f'{stem}.000'))

    def _show_rapids(self, on: bool) -> None:
        self.win.canvas.show_rapids = on
        self.win.canvas.invalidate()

    def clear(self) -> None:
        self.display([])

    def chosen_ops(self) -> list:
        """Les opérations choisies dans la liste (lignes sélectionnées) qui sont actives ; aucune ligne choisie : toutes
        les opérations actives ; des lignes choisies toutes désactivées : aucune."""
        ops = self.setup().operations
        rows = sorted({i.row() for i in self.ops.selectedIndexes() if i.row() < len(ops)})
        if rows:
            return [ops[r] for r in rows if ops[r].enabled]
        return [o for o in ops if o.enabled]

    def hidden_active_ops(self) -> list:
        """Les opérations actives dont tous les parcours calculés sont cachés : hors du programme écrit."""
        shown: dict = {}
        for tp in self.toolpaths:
            if tp.op_id:
                shown[tp.op_id] = shown.get(tp.op_id, False) or bool(getattr(tp, 'shown', True))
        return [o for o in self.setup().operations if o.enabled and o.id in shown and not shown[o.id]]

    def show_all_paths(self) -> int:
        """Tous les parcours des opérations de nouveau montrés (dans le programme) ; rend leur nombre."""
        n = 0
        for tp in self.toolpaths:
            if tp.op_id and not getattr(tp, 'shown', True):
                tp.shown = True
                n += 1
        if n:
            self.display(self.toolpaths)
        return n

    def show_chosen_3d(self, show: bool = True) -> list:
        """« Parcours 3D » : les parcours calculés (ou refaits si le dessin a changé), puis ceux des opérations choisies
        dans la liste (`chosen_ops`) montrés — eux seuls : les autres sont cachés, donc hors du programme écrit, et le
        panneau le dit — en 3D, dans le calque Trajectoires (`show`). Rend ces parcours."""
        self._cancelled = False
        chosen = self.chosen_ops()
        if not chosen:
            self.info.setText(tr('Aucune opération active parmi celles choisies dans la liste')
                              if self.ops.selectedIndexes() else tr('Aucune opération active'))
            return []
        ids = {o.id for o in chosen}
        self.current_paths(dates=False)                  # calculés, ou refaits si le dessin a changé depuis
        if self._cancelled:
            return []
        if self.toolpaths and not ids <= {tp.op_id for tp in self.toolpaths}:
            self._recompute(dates=False)                 # une opération ajoutée ou réactivée depuis : la liste gardée
            if self._cancelled:
                return []
        if any(tp.op_id for tp in self.toolpaths) and self.outdated():
            return []                                    # pas refaits (session reprise…) : le panneau dit pourquoi
        changed = False
        for tp in self.toolpaths:
            if tp.op_id and bool(getattr(tp, 'shown', True)) != (tp.op_id in ids):
                tp.shown = tp.op_id in ids
                changed = True
        if changed:
            self.display(self.toolpaths)                 # une fois : dessin, durée, vue 3D, yeux
        out = [tp for tp in self.toolpaths if tp.op_id in ids]
        every = sum(1 for o in self.setup().operations if o.enabled)
        self.win.statusBar().showMessage(
            tr('Parcours de {0} opération(s) sur {1} : celles choisies dans la liste (aucune choisie : toutes)').format(
                len(chosen), every), 8000)
        if show and out:
            self.win.show_toolpaths('3d')
        return out

    def _selected(self) -> list:
        canvas = getattr(getattr(self, 'win', None), 'canvas', None)
        return list(getattr(canvas, 'selection', []) or [])

    def selection_mode(self) -> bool:
        return self.calc_mode.currentData() == 'selection'

    def set_selection_mode(self, on: bool) -> None:
        self.calc_mode.setCurrentIndex(self.calc_mode.findData('selection' if on else 'couleur'))

    def dates_enabled(self) -> bool:
        return self.win.settings.value('fao/dates', 'true') in (True, 'true')

    def refresh_dates(self, now=None) -> int:
        """Textes datés (|Date|, |Heure|) remis à la date du moment avant le
        calcul (réglage « fao/dates », oui par défaut) : une plaque préparée
        lundi et gravée mercredi porte la date de mercredi. Un pas
        d'annulation ; rend le nombre de textes changés."""
        from ..core import variables as V
        if not self.dates_enabled() or not V.refresh_dates(self.doc, now, dry=True):
            return 0
        self.win.push_undo(tr('Date du jour'))
        n = len(V.refresh_dates(self.doc, now))
        self.win.canvas.invalidate()
        self.win._on_doc_changed()
        guard = getattr(self.win, 'fao_guard', None)
        if guard is not None:                            # la date du jour avant le calcul : pas une alarme
            guard.forget()
        self.win.statusBar().showMessage(tr('Date du jour mise dans {0} texte(s)').format(n), 5000)
        return n

    def compute(self, *, dates: bool = True, only=None, every: bool = False) -> list:
        """Tous les parcours ; `only` : objets à usiner (mode sélection) au
        lieu de la sélection du moment ; `every` : tous les objets, même en
        mode sélection (recalcul d'un calcul fait en mode couleur)."""
        self._cancelled = False
        if dates:
            self.refresh_dates()
        s = self.setup()
        if self._surfaces(s):
            model.store(self.doc, s)
        if not any(o.enabled for o in s.operations):
            self.info.setText(tr('Aucune opération active'))
            return []
        if only is None and not every and self.selection_mode():
            only = [it.id for it in self.win.canvas.selection]
        if only is not None:
            if not only:
                self.info.setText(tr('Mode sélection : sélectionnez les objets à usiner'))
                return []
        from .progress import Cancelled, run
        self._computing = True                           # vue 3D rafraîchie pendant le calcul : pas un 2e
        try:
            extra = {'only': only} if only is not None else {}    # mode couleur : appel inchangé
            tps = run(self.win, tr('Calcul des parcours'), strategies.compute_all, self.doc, s, **extra)
        except Cancelled:
            self._cancelled = True
            self.info.setText(tr('Calcul annulé'))
            return []
        finally:
            self._computing = False
        from ..core import surface2d
        self._remember('_surface_states', surface2d.state(self.doc))     # par document : current_paths
        self._remember('_placement_states', self._placement_state())
        self._remember('_inputs_states', self._inputs_state())
        self._remember('_computed', {tp.op_id for tp in tps if tp.op_id})
        self._remember('_only', ('selection', list(only)) if only is not None else ('couleur', None))
        self._remember('_whole', set())
        self.display(tps)                                # après : la vue 3D les voit à jour
        self.announce_zones()
        done = strategies.LAST_RUN
        if done.get('reused'):
            self.win.statusBar().showMessage(tr('{0} parcours repris tels quels (inchangés), {1} recalculé(s)').format(
                done['reused'], done['computed']), 6000)
        return tps

    def _report(self) -> None:
        from ..cam import timing as TM
        s = self.setup()
        lines = []
        est = TM.estimate(self.toolpaths, s, TM.spec_from_settings(self.win.settings))
        secs = {id(tp): sec for tp, sec in est['paths']}
        for tp in self.toolpaths:
            feed_len, rapid_len = tp.lengths()
            lines.append(tr('{0} : {1} mm en avance, {2} mm en rapide, ~{3}').format(
                tp.name or '—', f'{feed_len:.0f}', f'{rapid_len:.0f}', TM.format_duration(secs.get(id(tp), 0.0))))
            lines += ['  ⚠ ' + w for w in tp.warnings]
        if self.toolpaths:
            lines.append(tr('Temps estimé : ~{0}, dont {1} changement(s) d\'outil (~{2})').format(
                TM.format_duration(est['total']), est['changes'], TM.format_duration(est['change_s'])))
        self.last_estimate = est
        total = lines[-1] if self.toolpaths else None    # replié : la ligne du temps estimé
        hidden = self.hidden_active_ops()
        if hidden:                                       # un programme partiel ne s'écrit pas sans qu'on le sache
            lines.append('⚠ ' + tr('{0} opération(s) active(s) cachée(s) : hors du programme (œil de leur ligne ; '
                                    '« Parcours 3D » sans ligne choisie les montre toutes)').format(len(hidden)))
        self.info.setText('\n'.join(lines), total)
        self.info_area.show_end()                        # déplié et long : la fin en vue (temps estimé, avertissement)
        self._program_changed()

    def simulate(self, exec_dialog: bool = True):
        """Simulation d'enlèvement de matière des parcours cochés (calculés
        au besoin)."""
        tps = self.current_paths(dates=False)
        if not tps:
            return None
        from ..cam import simulate as SIM
        from .sim_dialog import SimDialog
        dlg = SimDialog(self, tps, self.setup(), SIM.stock_of(self.doc, self.setup(), tps), self._theory_lines(tps),
                        on_relief=lambda img: self.win._typeart_put(img, None, tr('Relief de la simulation')))
        if exec_dialog:
            dlg.exec()
        return dlg

    def _theory_lines(self, tps) -> list:
        """Les contours des objets usinés par ces parcours : [points], pour les montrer sur la simulation."""
        s = self.setup()
        ops = {o.id: o for o in s.operations}
        seen, paths = set(), []
        for tp in tps:
            op = ops.get(tp.op_id)
            if op is None:
                continue
            for it in strategies.source_items(self.doc, op):
                g = strategies.item_geometry(it)
                if g is not None and id(it) not in seen:
                    seen.add(id(it))
                    paths.append(g)
        return [pts for pts, _closed in strategies.polylines(paths, s.tolerance)]

    def machine_ops(self) -> int:
        """Les opérations propres à la machine que le dessin porte et que son post-processeur écrit lui-même
        (celles d'un plugin de la machine) : avec elles, le programme s'écrit même sans parcours."""
        from ..cam import post
        s = self.setup()
        available = post.posts(self.machines_dir())
        key = s.post if s.post in available or s.post.startswith('mah:') else next(iter(available), '')
        return post.doc_operations(key, self.doc)

    def _orient_note(self) -> str:
        return tr('Orientation de sortie : les opérations propres à la machine (celles de son plugin) ne sont pas '
                  'écrites, elles ne suivent pas l\'orientation')

    def post_process(self) -> None:
        from ..cam import post
        tps = self.current_paths()                       # parcours d'avant : ancienne date, surface déplacée…
        if not tps:
            old = self.checked_paths()
            if old and not self._writable(old):          # tous d'opérations désactivées ou supprimées depuis
                QMessageBox.information(self, tr('Post-traitement'), tr(
                    'Rien à écrire : les parcours cochés sont ceux d\'opérations désactivées ou supprimées '
                    'depuis le calcul. Recalculer les parcours.'))
                return
            if not self.machine_ops():                   # opérations propres à la machine : un programme quand même
                return
        s = self.setup()
        available = post.posts(self.machines_dir())
        key = s.post if s.post in available or s.post.startswith('mah:') else next(iter(available), '')
        if not key:
            QMessageBox.information(self, tr('Post-traitement'), tr(
                'Aucun post-processeur : VectorDrive n\'en contient pas, ils viennent des plugins de l\'atelier. '
                'Les parcours se calculent, se voient et se simulent sans eux.'))
            return
        if key.startswith('mah:') and not pathlib.Path(key[4:]).exists():
            QMessageBox.warning(self, tr('Post-traitement'), tr('Fiche machine introuvable : {0}').format(key[4:]))
            return
        src = self.win.path or self.doc.source_path
        title = pathlib.Path(src).stem if src else 'VectorDrive'
        box = self._stock_box()
        origin = self.program_origin()
        how = getattr(s, 'output_orient', 'normal')
        mine_doc, mine_note = self.doc, ''
        if box is not None and how != 'normal' and self.machine_ops():
            mine_doc, mine_note = None, self._orient_note()      # elles ne suivent pas l'orientation de sortie
            if not tps:
                QMessageBox.information(self, tr('Post-traitement'), mine_note)
                return
        if box is not None:                              # orientation de sortie : ce qui est écrit, contrôlé et noté
            tps, origin, box = post.oriented(tps, how, (box[0], box[1], box[3], box[4]), origin, box)
        probe = post.run(key, tps, s, title=title, stem='programme', box_mm=box, origin=origin, doc=mine_doc)
        if not probe.files:                              # export refusé (ex. oscillation trop rapide) : rien à écrire
            QMessageBox.warning(self, tr('Post-traitement'), tr('Aucun programme écrit.') + '\n\n' +
                                '\n'.join('• ' + w for w in probe.warnings[:20]))
            return
        if tps and not self.preflight(tps, probe.warnings):      # sans parcours : rien à vérifier
            return
        from ..plugins import REGISTRY
        special = REGISTRY.post_exports.get(key) or REGISTRY.post_exports.get(post.family(key))
        if special is not None:                          # export propre à la machine (travail, dossier, quantité…)
            try:
                if special(self, tps, s):
                    return
            except Exception as ex:                      # un plugin ne casse pas l'export : l'ordinaire suit
                self.win.statusBar().showMessage(tr('Plugin : {0}').format(ex), 10000)
        start = str(self.program_dir() / (title + probe.extension))
        path, _ = QFileDialog.getSaveFileName(self, tr('Programme machine'), start,
                                              tr('Programme ({0})').format('*' + probe.extension))
        if not path:
            return
        out = pathlib.Path(path)
        self.win.settings.setValue('dossier/programmes', str(out.parent))
        groups = post.program_groups(tps, s.program_group, self._plan_of_path)
        results = [(part, post.run(key, part, s, title=title, stem=f'{out.stem}_{suffix}' if suffix else out.stem, box_mm=box,
                                   out_dir=str(out.parent), origin=origin, **post.attach_kw(),
                                   doc=mine_doc if gi == len(groups) - 1 else None))      # une seule fois : à la fin
                   for gi, (suffix, part) in enumerate(groups)]
        others = [out.with_name(name) for _p, r in results for name, _t in r.files if out.with_name(name) != out]
        others = [f.name for f in others if f.exists()]          # le nom choisi a déjà été confirmé par la fenêtre
        joined = [f.name for _p, r in results for f, _d in post.attachment_paths(r, out.parent) if f.exists()]
        others += [n for n in joined if n not in others]          # un fichier joint (l'image…) qui existe : demandé
        if others and (len(results) > 1 or joined) and QMessageBox.question(
                self, tr('Programme machine'), tr('Ces fichiers existent déjà. Les remplacer ?') + '\n\n' + '\n'.join(others[:20])
        ) != QMessageBox.StandardButton.Yes:
            return
        written = []
        from ..cam import postcheck
        from .progress import Cancelled, run
        for part, r in results:
            for name, text in r.files:
                f = out.with_name(name)
                f.write_text(text, encoding=r.encoding, errors='replace', newline='\r\n')
                written.append(f.name)
            written += [f.name for f in post.write_attachments(r, out.parent)]   # l'image de l'aperçu…
            try:                                         # programme relu et comparé aux parcours (sans les
                r.warnings = run(self.win, tr('Contrôle du programme écrit'), postcheck.verify,  # opérations propres
                                 getattr(r, 'check_files', None) or r.files, part, s, origin) + r.warnings  # à la machine)
            except Cancelled:
                pass
        res = results[0][1]
        res.warnings = ([mine_note] if mine_note else []) + [w for _p, r in results for w in r.warnings]
        msg = tr('Programme écrit : {0}').format(', '.join(written))
        msg += '\n' + tr('Dossier : {0}').format(out.parent)
        hidden = self.hidden_active_ops()
        if hidden:
            msg += '\n\n⚠ ' + tr('Programme partiel : {0} opération(s) active(s) cachée(s) n\'y sont pas ({1}).').format(
                len(hidden), ', '.join(self.op_label(o) for o in hidden[:8]))
        jpath = self.write_journal(out, key, tps, written)
        if jpath is not None:
            msg += '\n' + tr('Journal : {0}').format(jpath.name)
        msg += '\n\n' + tr('À simuler avant usinage (origine, outils, hauteurs, bridage).')
        msg += '\n' + tr('Zéro du programme (X0 Y0) : {0} — l\'origine de la machine se règle sur ce point.').format(
            post.zero_text(self.doc.plate, self.program_origin())[0])
        if box is not None and how != 'normal' and how in post.ORIENTATIONS:
            msg += '\n\n• ' + tr('Orientation de sortie : {0}. La simulation montre la plaque sans elle.').format(tr(self.ORIENT_LABELS[how]))
            if how in post.MIRRORS:
                msg += '\n• ' + tr('En miroir, le sens d\'usinage s\'inverse : avalant et opposition sont échangés.')
        if res.warnings:
            msg += '\n\n' + '\n'.join('• ' + w for w in res.warnings[:20])
        first = out.with_name(res.files[0][0]) if res.files else out
        self._remember_program(first)
        from .reveal import done_message
        self.done_box = done_message(self, tr('Post-traitement'), msg, first)

    def post_panels(self) -> None:
        """Parcellisation : les panneaux, puis un programme par panneau et leur rapport."""
        from ..cam import post
        from .panels_dialog import PanelsDialog
        tps = self.current_paths()
        if not tps:
            QMessageBox.information(self, tr('Parcellisation'), tr('Rien à découper : calculez d’abord les parcours.'))
            return
        s = self.setup()
        available = post.posts(self.machines_dir())
        key = s.post if s.post in available or s.post.startswith('mah:') else next(iter(available), '')
        if not key:
            QMessageBox.information(self, tr('Parcellisation'), tr(
                'Aucun post-processeur : VectorDrive n\'en contient pas, ils viennent des plugins de l\'atelier.'))
            return
        box = self._stock_box()
        dlg = PanelsDialog(self, tps, (box[0], box[1], box[3], box[4]) if box else None, s.panels)
        self.panels_box = dlg
        if not dlg.exec():
            return
        s.panels = dlg.values()
        model.store(self.doc, s)
        src = self.win.path or self.doc.source_path
        title = pathlib.Path(src).stem if src else 'VectorDrive'
        probe = post.run(key, tps, s, title=title, stem='programme', box_mm=box, origin=self.program_origin())
        if not probe.files:
            QMessageBox.warning(self, tr('Parcellisation'), tr('Aucun programme écrit.') + '\n\n' +
                                '\n'.join('• ' + w for w in probe.warnings[:20]))
            return
        if not self.preflight(tps, probe.warnings):
            return
        start = str(self.program_dir() / (title + probe.extension))
        path, _ = QFileDialog.getSaveFileName(self, tr('Programmes des panneaux'), start,
                                              tr('Programme ({0})').format('*' + probe.extension))
        if not path:
            return
        written = self.write_panels(key, tps, dlg.panels, dlg.values(), path, dlg.bounds())
        if written:
            self.win.settings.setValue('dossier/programmes', str(pathlib.Path(path).parent))

    def write_panels(self, key: str, tps, panels: list, values: dict, path: str, bounds) -> list:
        """Un programme par panneau où quelque chose tombe, et le rapport : les fichiers écrits."""
        import datetime

        from ..cam import panels as PN
        from ..cam import post, postcheck
        from ..cam import timing as TM
        from .progress import Cancelled, run
        s = self.setup()
        out = pathlib.Path(path)
        overlap, where = float(values.get('overlap', 0.0)), values.get('origin', 'bottom_left')
        try:
            cut = run(self.win, tr('Parcellisation'), PN.split, tps, panels, overlap, s.tolerance)
        except Cancelled:
            return []
        panels, cut = PN.filled(panels, cut)
        if not panels:
            QMessageBox.information(self, tr('Parcellisation'), tr('Aucun parcours ne tombe dans ces panneaux.'))
            return []
        stock = self._stock_box()
        src = self.win.path or self.doc.source_path
        title = pathlib.Path(src).stem if src else 'VectorDrive'
        written, warnings, names = [], [], {}
        for p in panels:
            box = (p.x1, p.y1, stock[2], p.x2, p.y2, stock[5]) if stock else None
            origin = p.origin(where)
            stem = f'{out.stem}_P{p.rank:02d}'
            res = post.run(key, cut[p.rank], s, title=f'{title} - {p.rank}/{len(panels)}', stem=stem, box_mm=box,
                           out_dir=str(out.parent), origin=origin, **post.attach_kw())
            if not res.files:
                warnings.append(tr('Panneau {0} : aucun programme.').format(p.rank))
            for name, text in res.files:
                f = out.with_name(name)
                f.write_text(text, encoding=res.encoding, errors='replace', newline='\r\n')
                written.append(f)
            written += post.write_attachments(res, out.parent)
            names[p.rank] = res.files[0][0] if res.files else stem
            try:
                problems = run(self.win, tr('Contrôle du programme écrit'), postcheck.verify, res.files, cut[p.rank], s,
                               origin) + res.warnings
            except Cancelled:
                problems = res.warnings
            warnings += [tr('Panneau {0} : {1}').format(p.rank, w) for w in problems]
        if self.machine_ops():                           # celles d'un plugin : pas dans les programmes par panneau
            warnings.insert(0, tr('Opérations propres à la machine (celles de son plugin) : non écrites dans les '
                                  'programmes par panneau'))
        when = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
        text = PN.report(panels, cut, s, bounds, out.stem, names=names, overlap=overlap, where=where, when=when,
                         spec=TM.spec_from_settings(self.win.settings))
        rep = out.with_name(out.stem + '_panneaux.txt')
        rep.write_text(text, encoding='utf-8', newline='\r\n')
        written.append(rep)
        msg = tr('{0} panneau(x), {1} fichier(s) écrit(s).').format(len(panels), len(written))
        msg += '\n' + tr('Dossier : {0}').format(out.parent)
        msg += '\n' + tr('Rapport : {0}').format(rep.name)
        msg += '\n\n' + tr('À simuler avant usinage (origine, outils, hauteurs, bridage).')
        if warnings:
            msg += '\n\n' + '\n'.join('• ' + w for w in warnings[:20])
        self._remember_program(written[0])
        from .reveal import done_message
        self.done_box = done_message(self, tr('Parcellisation'), msg, written[0])
        return written

    def program_dir(self) -> pathlib.Path:
        """Dossier proposé pour un programme : celui du dessin, sinon le
        dernier utilisé, sinon Documents — jamais le dossier de VectorDrive
        (installation ou sources : un programme n'a rien à y faire)."""
        from PySide6.QtCore import QStandardPaths
        app = pathlib.Path(__file__).resolve().parents[2]
        src = self.win.path or self.doc.source_path
        cands = [str(pathlib.Path(src).parent) if src else '',
                 str(self.win.settings.value('dossier/programmes', '') or ''),
                 QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)]
        for c in cands:
            if not c:
                continue
            p = pathlib.Path(c)
            try:
                inside = p.resolve().is_relative_to(app)
            except (OSError, ValueError):
                inside = True
            if p.is_dir() and not inside:
                return p
        return pathlib.Path.home()

    def journal_enabled(self) -> bool:
        return self.win.settings.value('fao/journal', 'false') in (True, 'true')

    def write_journal(self, out: pathlib.Path, key: str, tps, written: list):
        """Entrée du journal des exports (cam.journal) à côté du programme,
        si le journal est tenu ; rend son chemin."""
        if not self.journal_enabled():
            return None
        from ..cam import journal as JR
        st = JR.state(self.setup(), tps, key)
        memo = self.doc.extra.setdefault('fao_journal', {})
        entry = JR.render(st, JR.differences(memo.get(out.stem), st), rank=JR.next_rank(out.parent, out.stem),
                          folder=str(out.parent), files=written)
        path = JR.append(out.parent, out.stem, entry)
        if path is not None:
            memo[out.stem] = st
        return path

    def preflight_enabled(self) -> bool:
        return self.win.settings.value('fao/verifier', 'true') in (True, 'true')

    def preflight(self, tps, warnings=(), *, exec_dialog: bool = True) -> bool:
        """Vérification avant l'écriture (cam.preflight), si elle est active :
        rend False si l'opérateur renonce. Coupée, un arrêt qui manque entre
        deux prises est quand même signalé (la machine enchaînerait sans que la
        pièce soit retournée)."""
        from ..cam import post
        from ..cam import preflight as PF
        s = self.setup()
        missing = any(lv == PF.BLOQUANT for lv, _t in PF.setup_changes(self.doc, s, tps)) \
            and bool(PF.add_stops(self.doc, model.CamSetup.from_dict(s.to_dict()), tps))     # il en ajouterait
        if not self.preflight_enabled():
            problems = PF.safety(self.doc, s, tps, warnings)
            return self._safety_guard(tps, problems, missing, exec_dialog) if problems else True
        from ..cam import timing as TM
        from .preflight_dialog import PreflightDialog
        rep = PF.inspect(self.doc, s, tps, post_warnings=warnings,
                         timing_spec=TM.spec_from_settings(self.win.settings), all_paths=self.toolpaths,
                         zero=post.zero_text(self.doc.plate, self.program_origin()))
        self.last_preflight = PreflightDialog(self, rep, add_stops=(lambda: self.add_stops(tps)) if missing else None)
        if not exec_dialog:
            return True
        ok = bool(self.last_preflight.exec())
        if self.last_preflight.stops_added:
            self.info.setText(tr('{0} arrêt(s) ajouté(s) entre les prises : relancer l\'écriture du programme')
                              .format(len(self.last_preflight.stops_added)))
        if ok and self.last_preflight.skip_next_time():
            self.win.settings.setValue('fao/verifier', False)
        return ok

    def _safety_guard(self, tps, problems: list, missing: bool, exec_dialog: bool = True) -> bool:
        """Vérification coupée, mais le programme serait faux (`problems`,
        cam.preflight.safety) : ajouter les arrêts s'il en manque (rien n'est
        écrit), écrire quand même, ou renoncer."""
        shown = problems[:8] + ([tr('… et {0} autre(s)').format(len(problems) - 8)] if len(problems) > 8 else [])
        box = QMessageBox(QMessageBox.Icon.Warning, tr('Avant d\'écrire le programme'),
                          tr('La vérification avant l\'écriture est coupée, mais ceci rendrait le programme faux :')
                          + '\n\n' + '\n\n'.join('• ' + t for t in shown), parent=self)
        add = box.addButton(tr('Ajouter les arrêts'), QMessageBox.ButtonRole.AcceptRole) if missing else None
        force = box.addButton(tr('Écrire quand même'), QMessageBox.ButtonRole.DestructiveRole)
        cancel = box.addButton(QMessageBox.StandardButton.Cancel)
        box.setDefaultButton(add or cancel)
        self.last_guard = box
        if not exec_dialog:
            return True
        box.exec()
        clicked = box.clickedButton()
        box.deleteLater()
        if add is not None and clicked is add:
            if self.add_stops(tps):
                self.info.setText(self.info.text() + tr(' : relancer l\'écriture du programme'))
            return False
        return clicked is force

    def _remember_program(self, path: pathlib.Path) -> None:
        """Dernier programme (ou parcours) écrit : le bouton 📂 y mène."""
        self.last_program = path
        self.folder_btn.setEnabled(True)
        self.folder_btn.setToolTip(tr('Ouvrir le dossier du dernier programme écrit') + f'\n{path}')

    def open_program_folder(self) -> bool:
        """Montre le dernier programme écrit dans l'explorateur."""
        if self.last_program is None:
            return False
        from .reveal import reveal
        if not reveal(self.last_program):
            QMessageBox.information(self, tr('Programme machine'),
                                    tr('Dossier introuvable : {0}').format(self.last_program.parent))
            return False
        return True

    def program_origin(self):
        """Zéro du programme (x, y en mm du dessin), None au zéro du dessin :
        selon le réglage « Zéro du programme » (TE : positionnement de la
        pièce), le coin supérieur gauche, le centre ou le coin inférieur gauche
        de la plaque ; sinon l'origine du dessin — comme TypeEdit, le point
        zéro de la plaque (centre, coin…) devient l'origine des programmes.
        « Selon la machine » (par défaut) : le zéro que dit le post-processeur
        ou la fiche machine, sinon l'origine du dessin."""
        from ..cam import post
        o = self.doc.extra.get('origine') if isinstance(self.doc.extra, dict) else None
        try:
            x, y = float(o[0]), float(o[1])
            origin = (x, y) if abs(x) > 1e-12 or abs(y) > 1e-12 else None
        except (TypeError, ValueError, IndexError):
            origin = None
        s = self.setup()
        zero = post.effective_zero(getattr(s, 'program_zero', 'machine'), self.post_key(s))
        pt = post.zero_point(zero, self.doc.plate, origin)
        if pt is None or (abs(pt[0]) < 1e-12 and abs(pt[1]) < 1e-12):
            return None
        return float(pt[0]), float(pt[1])

    def _stock_box(self):
        """Boîte de la matière (mm) : la plaque du document, son épaisseur
        en Z (la face à Z = 0)."""
        pl = self.doc.plate
        if pl is None:
            return None
        return (pl.x, pl.y, -(pl.thickness or 0.0), pl.x + pl.width, pl.y + pl.height, 0.0)

    def import_typeedit(self, paths=None) -> list:
        from ..cam import typeedit
        if paths is None:
            src = self.win.path or self.doc.source_path
            start = str(pathlib.Path(src).parent) if src else ''
            paths, _ = QFileDialog.getOpenFileNames(
                self, tr('Parcours TypeEdit'), start,
                tr('Parcours TypeEdit (*.0?? *.1?? *.vnd);;Tous (*.*)'))
            if not paths:
                return []
        from ..core import progress as P
        from .progress import Cancelled, run

        def work():
            found, tools, errors = [], {}, []
            for i, p in enumerate(paths):
                P.step(i, len(paths), 'Fichier {0} sur {1}')
                vnd = pathlib.Path(p) if p.lower().endswith('.vnd') else \
                    pathlib.Path(p).with_name(pathlib.Path(p).name.rsplit('.', 1)[0] + '.vnd')
                if vnd.exists():
                    tools.update(typeedit.vnd_tools(vnd))
                if p.lower().endswith('.vnd'):
                    found.extend(typeedit.read_all(p))
                else:
                    try:
                        found.append(typeedit.read(p))
                    except (typeedit.VnvError, ValueError) as ex:
                        errors.append(f'{pathlib.Path(p).name} : {ex}')
            return found, tools, errors
        try:
            tps, self._vnd_tools, errors = run(self.win, tr('Parcours TypeEdit'), work)
        except Cancelled:
            return []
        if errors:
            QMessageBox.warning(self, tr('Parcours TypeEdit'), '\n'.join(errors[:10]))
        if not tps:
            self.info.setText(tr('Aucun parcours TypeEdit trouvé'))
        self._typeedit_tools(tps)
        self.display(tps)
        return tps

    def _typeedit_tools(self, tps) -> None:
        """Outils lus dans les en-têtes des parcours TypeEdit, ajoutés à la
        bibliothèque du document (un par numéro, diamètre, angle)."""
        s = self.setup()
        changed = False
        known = getattr(self, '_vnd_tools', {})
        for tp in tps:
            vt = known.get(getattr(tp, 'file', ''))
            if vt is not None:
                # outil complet du VND : avances et régimes de TypeEdit
                key = (vt.name, round(vt.diameter, 4), round(vt.angle, 3), round(vt.feed, 3))
                t = next((x for x in s.tools
                          if (x.name, round(x.diameter, 4), round(x.angle, 3), round(x.feed, 3)) == key), None)
                if t is None:
                    t = model.CamTool.from_dict(vt.to_dict())
                    t.id = model.new_id()
                    s.tools.append(t)
                    changed = True
                tp.tool_id = t.id
                continue
            info = getattr(tp, 'header', {}).get('tool')
            if not info or not 0 < info['diameter'] <= 100:
                if info:
                    tp.warnings.append(tr("outil de l'en-tête invraisemblable ({0} mm) : non repris").format(
                        f"{info['diameter']:g}"))
                continue
            key = (info['number'], round(info['diameter'], 4), round(info['angle'], 3))
            t = next((x for x in s.tools if (x.number, round(x.diameter, 4), round(x.angle, 3)) == key), None)
            if t is None:
                kind = 'conique' if info['angle'] > 0 else 'fraise'
                t = model.CamTool(name=tr('TypeEdit T{0} Ø{1}').format(info['number'], f"{info['diameter']:g}")
                                  + (f" {info['angle']:g}°" if info['angle'] else ''),
                                  kind=kind, diameter=info['diameter'], angle=info['angle'], tip=info['tip'],
                                  number=info['number'])
                s.tools.append(t)
                changed = True
            tp.tool_id = t.id
            tp.warnings.append(tr('avances et régimes TypeEdit non lus : ceux de l\'outil {0} sont utilisés')
                               .format(t.name))
        if changed:
            self.save(s)
