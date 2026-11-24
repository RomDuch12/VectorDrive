"""FAO : outils d'usinage, opérations, parcours.

Comme dans TypeEdit, un **outil du dessin** (une couleur, souvent un
calque) désigne ce qu'il faut usiner ; une **opération** dit comment : la
fraise ou le laser, la stratégie (gravure sur le trait, détourage, poche,
perçage…), les profondeurs, les vitesses. Le réglage FAO d'un document
vit dans `doc.extra['fao']` (dictionnaire JSON, enregistré avec le .vdz).

Unités : mm, mm/min, tr/min ; Z = 0 à la surface de la pièce, négatif
dans la matière.
"""
from __future__ import annotations

import math
import uuid
from dataclasses import asdict, dataclass, field, fields

#: natures d'outil
TOOL_KINDS = {
    'fraise': 'Fraise droite',
    'boule': 'Fraise boule',
    'conique': 'Outil conique (gravure, chanfrein)',
    'foret': 'Foret',
    'laser': 'Laser',
    'couteau': 'Couteau (vinyle, carton : déport de la lame = pointe)',
    'profil': 'Outil spécial (profil dessiné)',
}

#: stratégies
OP_KINDS = {
    'gravure': 'Gravure sur le trait',
    'contour': 'Détourage (contour décalé)',
    'poche': 'Poche (vidage)',
    'percage': 'Perçage (centres des cercles)',
    'vcarve': 'Gravure 2,5D à l\'outil conique',
    'prismatique': 'Lettres prismatiques (relief en V, outil conique)',
    'vinyle': 'Découpe au couteau (vinyle : tracé, asservi, flottant)',
    'chanfrein_bord': 'Chanfrein des bords (outil conique)',
    'fer_dorer': 'Fer à dorer gaufrant (galbe en passes 2D)',
    'decoupe3d': 'Découpe 3D (outil conique, bord chanfreiné)',
    'reste': 'Reste matière (après un outil plus gros)',
    'relief': 'Relief 3D (carte de hauteurs)',
    'surface3d': 'Surface 3D (pièce STEP, STL, 3D XML)',
    'ebauche3d': 'Ébauche 3D (paliers en Z, pièce STEP, STL, 3D XML)',
    'reprise3d': 'Reprise 3D (reste de l\'outil d\'avant, pièce 3D)',
    'niveaux3d': 'Niveaux constants 3D (parois, pièce 3D)',
    'finition25d': 'Finition 2,5D (surface de la gravure 2,5D, balayée)',
    'laser': 'Marquage laser',
    'laser_decoupe': 'Découpe laser (faisceau compensé)',
    'laser_gravure': 'Gravure laser (remplissage)',
    'taraudage': 'Taraudage (fraise à fileter, centres des cercles)',
    'percage_fraise': 'Perçage à la fraise (hélice, centres des cercles)',
    'chanfrein': 'Ébavurage des trous (outil conique)',
    'surfacage': 'Surfaçage (dessus de la zone ou de la plaque)',
    'instruction': 'Instruction machine (palpage, origine, message…)',
    'texte_machine': 'Texte machine (police de la commande, n° de série, date)',
}
#: filetages métriques ISO à pas gros : nom → (Ø nominal, pas, Ø d'avant-trou), mm
THREADS = {'M2': (2.0, 0.4, 1.6), 'M2.5': (2.5, 0.45, 2.05), 'M3': (3.0, 0.5, 2.5), 'M4': (4.0, 0.7, 3.3),
           'M5': (5.0, 0.8, 4.2), 'M6': (6.0, 1.0, 5.0), 'M8': (8.0, 1.25, 6.8), 'M10': (10.0, 1.5, 8.5),
           'M12': (12.0, 1.75, 10.2)}


def op_kinds() -> dict[str, str]:
    """Stratégies : celles du cœur et celles des plugins."""
    from ..plugins import REGISTRY
    return {**OP_KINDS, **{k: v[0] for k, v in REGISTRY.strategies.items()}}


def new_id() -> str:
    return uuid.uuid4().hex[:12]


def _from_dict(cls, d: dict):
    names = {f.name for f in fields(cls)}
    return cls(**{k: v for k, v in (d or {}).items() if k in names})


@dataclass
class CamTool:
    """Outil d'usinage (bibliothèque)."""
    name: str = 'Fraise 1 mm'
    kind: str = 'fraise'
    diameter: float = 1.0           # mm ; outil conique : grand diamètre
    tip: float = 0.0                # outil conique : largeur de la pointe (mm)
    angle: float = 0.0              # outil conique : angle au sommet (°)
    flutes: int = 1
    cut_length: float = 3.0         # longueur utile (mm)
    stickout: float = 0.0           # dépassement hors pince (mm) ; 0 : collisions du porte-outil non vérifiées
    holder_diameter: float = 0.0    # Ø de l'écrou de pince ou du porte-outil (mm)
    number: int = 1                 # place dans le magasin (T)
    ref: str = ''                   # référence fabricant
    vendor: str = ''                # fournisseur (Datron : « Vendor »)
    spindle: float = 20000.0        # tr/min
    feed: float = 600.0             # avance de coupe (mm/min)
    plunge: float = 200.0           # avance de plongée (mm/min)
    ramp_feed: float = 0.0          # avance en rampe (mm/min, 0 = celle de plongée)
    finish_feed: float = 0.0        # avance de finition (mm/min, 0 = celle de coupe)
    step_down: float = 0.2          # passe en Z (mm)
    stepover: float = 0.4           # recouvrement des poches (fraction du diamètre)
    power: float = 0.0              # laser : puissance (%)
    frequency: float = 0.0          # laser : fréquence (kHz)
    notes: str = ''
    folder: str = ''                # dossier dans « Mes outils » (un import = un dossier ; vide : Mes outils)
    #: cotes du fabricant (D1 Ø de coupe, D2 queue, D3/L3 dégagement, L1 totale,
    #: L2 de coupe, angle, R, dents, famille) — voir `cam.tooldraw`
    geometry: dict = field(default_factory=dict)
    #: catalogue : fournisseur, référence, adresse de la fiche, prix, devise, date
    catalog: dict = field(default_factory=dict)
    #: dessins générés : chemins du DXF et du STEP
    drawings: dict = field(default_factory=dict)
    #: changements des vitesses : [{'date', 'champ', 'avant', 'apres', 'source'}, …] (les 50 derniers)
    history: list = field(default_factory=list)
    #: outil spécial : profil de révolution [[rayon, hauteur au-dessus de la pointe], …] (mm)
    profile: list = field(default_factory=list)
    #: machines (clés de post-processeur) où l'outil est monté ; vide : toutes
    machines: list = field(default_factory=list)
    id: str = field(default_factory=new_id)

    def profile_radius(self, h: float) -> float:
        """Outil spécial : rayon du profil à la hauteur h (interpolé)."""
        P = sorted((float(b), float(a)) for a, b in self.profile)
        if not P:
            return self.diameter / 2
        if h <= P[0][0]:
            return P[0][1]
        for (h0, r0), (h1, r1) in zip(P, P[1:]):
            if h <= h1:
                return r0 + (r1 - r0) * (h - h0) / (h1 - h0) if h1 > h0 else max(r0, r1)
        return P[-1][1]

    def body_diameter(self) -> float:
        """Plus grand diamètre de la partie qui coupe : celui de l'outil ; un
        outil conique s'élargit jusqu'à sa queue (cote D2 du fabricant) — les
        fiches de NeoDrive n'ont pas de diamètre pour les cônes (1 mm par
        défaut à l'import), ce qui bornait la gravure à quelques dixièmes."""
        d = self.diameter
        if self.kind == 'conique':
            try:
                d = max(d, float((self.geometry or {}).get('D2') or 0.0))
            except (TypeError, ValueError):
                pass
        return d

    def radius_at(self, depth: float) -> float:
        """Rayon de coupe à la profondeur `depth` (> 0) sous la pointe."""
        if self.kind == 'conique' and 0 < self.angle < 180:
            r = self.tip / 2 + depth * math.tan(math.radians(self.angle) / 2)
            body = self.body_diameter()
            return min(r, body / 2) if body > 0 else r
        if self.kind == 'boule':
            r = self.diameter / 2
            d = min(depth, r)
            return math.sqrt(max(0.0, r * r - (r - d) ** 2))
        if self.kind == 'profil' and self.profile:
            return max(self.profile_radius(h) for h in (depth * k / 16 for k in range(17)))
        return self.diameter / 2

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> 'CamTool':
        return _from_dict(cls, d)


#: valeurs de `Operation.trace_mode` d'avant le relevé dans TE13
OLD_TRACE_MODES = {'aller_retour': 'simple', 'aller_simple': 'meme_sens', 'dernier_ar': 'dernier'}


@dataclass
class Operation:
    """Une opération : ce qu'on usine (outils du dessin), avec quoi, comment."""

    def __post_init__(self):
        # anciens noms, gardés dans les dessins et les modèles : le parcours calculé reste le même
        self.trace_mode = OLD_TRACE_MODES.get(self.trace_mode, self.trace_mode)

    name: str = ''
    kind: str = 'gravure'
    tool_id: str = ''
    #: reste matière, gamme : outil passé avant (plus gros), dont on reprend les restes
    ref_tool_id: str = ''
    #: outils du dessin (index des couleurs) concernés ; vide = tous
    sources: list = field(default_factory=list)
    #: objets du dessin (identifiants) ; s'il y en a, seuls eux sont usinés
    items: list = field(default_factory=list)
    depth: float = 0.2              # profondeur finale (mm, > 0)
    z_start: float = 0.0            # Z de départ : cote du dessus de la matière (mm) ; le parcours entier en suit
    step_down: float = 0.0          # passe ; 0 = celle de l'outil
    side: str = 'exterieur'         # détourage : exterieur, interieur, sur
    climb: bool = True              # avalant (sinon en opposition)
    stock: float = 0.0              # surépaisseur laissée (mm)
    stock_z: float = 0.0            # contour, poche, reste : surépaisseur Z laissée au fond pour une finition (mm)
    finish: bool = False            # passe de finition à pleine profondeur
    peck: float = 0.0               # perçage : débourrage (mm, 0 = d'un coup)
    drill_points: str = 'cercles'   # perçage : 'cercles' (et marqueurs), 'marqueurs', 'depart', 'arrivee',
                                    # 'depart_arrivee', 'centres' (centre des contours fermés : braille)
    drill_mode: str = 'debourrage'  # perçage en passes : 'debourrage' (remonte au dégagement), 'brise_copeau'
                                    # (petit recul), 'simple' (une passe)
    drill_feed_retract: bool = False  # perçage : remontée en vitesse de travail (sinon en rapide)
    tabs: int = 0                   # détourage : nombre de pontets
    tab_width: float = 2.0
    tab_height: float = 0.5
    tab_spacing: float = 0.0        # détourage : un pontet tous les … mm (0 = d'après le nombre)
    tab_gap: float = 0.0            # détourage : distance entre ponts de TE13 (0 = d'après le nombre)
    tab_max: int = 0                # pontets : pas plus que ce nombre par contour, quelle que soit la distance (0 : sans limite)
    tab_mode: str = 'pont'          # pontets : 'pont' (hauteur laissée), 'pointille' (non usinés), 'nettoyer' (seuls eux sont usinés)
    tab_shape: str = 'droit'        # pontets 'droit' (flancs verticaux) ou 'incurve' (montée et descente
                                    # en douceur, TypeEdit : ponts incurvés)
    ramp: bool = False              # entrée en rampe (sinon plongée) ; traits ouverts : en zigzag
    ramp_angle: float = 0.0         # angle de la rampe (°) ; 0 = 5°
    ramp_helix: float = 0.0         # poche : rampe en hélice de ce rayon (mm) ; 0 : le long de l'anneau
    ramp_max: float = 0.0           # distance maxi de la rampe (mm, 0 = sans limite) : allers-retours sur le début du contour
    finish_skip_frame: bool = False  # finition : pas de passe sur le cadre (contour extérieur) — relief
    #: poche entière : la passe de finition à toutes les cotes le long de la matière que l'ébauche n'a pas ouverte
    #: (zone étroite, coin aigu), au fond ailleurs — la règle de « seulement le reste », en option (réponse 7 du 14/11)
    finish_shut_levels: bool = False
    common_line: bool = False       # détourage extérieur : bord partagé de pièces voisines coupé une fois
    small_first: bool = False       # détourage : les plus petites pièces d'abord (sinon au plus proche)
    order_mode: str = 'auto'        # tri des contours : 'auto' (au plus court) ou 'dessin' (ordre du dessin)
    holes_order: str = 'element'    # détourage : trous 'element' (ceux de chaque pièce, puis son tour) ou 'tous' (tous les trous, puis tous les tours)
    raster_dir: str = 'x'           # relief, surface 3D : passes selon X, Y, ou 'xy' (puis une finition selon Y)
    scan_mode: str = 'passes'       # relief, surface 3D : 'passes' (raster_dir), 'angle' ou 'spirale'
    raster_angle: float = 0.0       # scan_mode 'angle' : angle des passes (°)
    raster_turn: float = 0.0        # scan_mode 'angle' : une dernière passe croisée, tournée de … (°, 0 : aucune)
    spiral_outward: bool = False    # scan_mode 'spirale' : de l'intérieur vers l'extérieur
    parallel_slices: int = 0        # relief, surface 3D : tranches parallèles au profil (0 : par cotes de Z)
    follow_profile: bool = True     # relief, surface 3D : l'outil suit la surface déjà usinée, sinon il remonte
    rough_mode: bool = False        # finition 2,5D : ébauche (paliers en Z jusqu'à la surface), sinon la surface seule
    stock_xy: float = 0.0           # finition 2,5D en ébauche : décalage en XY laissé le long des flancs (mm)
    small_first_by: str = 'aire'    # petites pièces : selon 'aire', 'perimetre' ou 'cercle' (cercle inscrit)
    contour_ref: str = 'surface'    # outil conique / boule : contour respecté 'surface' ou 'fond' (TypeEdit)
    # tracé, relevé dans TE13 : 'simple' (fermé : un tour par passe ; ouvert : un sens par passe, sans relever), 'ar' (à chaque passe,
    # le trait puis son retour à la même cote), 'dernier' (ouvert : même sens, relevé entre les passes ; le retour à la dernière),
    # 'meme_sens' (ouvert : toujours dans le même sens, relevé entre les passes)
    trace_mode: str = 'simple'
    knife_mode: str = 'flottant'    # couteau : 'trace', 'asservi' (remonte aux angles), 'flottant' (pivote), 'boucles'
    knife_angle: float = 30.0       # couteau : changement de direction (°) au-delà duquel il remonte ou pivote
    knife_angle_max: float = 165.0  # couteau : au-delà (presque demi-tour), ni remontée ni boucle
    pocket_spiral: bool = False     # poche concentrique : une spirale continue plutôt que des anneaux
    corner_pull: bool = False       # découpe 3D : tirés d'angle (l'outil remonte dans les angles rentrants)
    corner_pull_angle: float = 135.0  # … plus fermés que celui-ci (°)
    corner_pull_z: float = 0.0      # … et l'outil monte jusqu'à cette hauteur au-dessus de la matière (mm, 0 = à la surface)
    foot_pull: bool = False         # découpe 3D : tiré d'angle au pied (angles saillants vifs en bas : poinçons)
    foot_pull_min: float = 22.5     # … angles d'au moins (°)
    foot_pull_max: float = 135.0    # … et de moins de (°)
    corner_opt: bool = False        # poche concentrique : l'outil va chercher la matière des angles aigus
    corner_opt_angle: float = 135.0  # … des angles plus fermés que celui-ci (°)
    pocket_outside_in: bool = False  # poche concentrique : du bord vers le centre (sinon du centre vers le bord)
    sweep_contour_stock: float = -1.0  # balayage : surépaisseur du cassé d'angle (mm, de 0 à celle des hachures ; -1 : la même)
    wrap_guide: list = field(default_factory=list)  # projection locale : courbe guide [[x, y], …]
    corner_loops: bool = False      # découpe : boucles aux angles extérieurs (angles vifs, vitesse tenue)
    chain_cut: bool = False         # découpe en chaîne : d'une pièce à la suivante sans relever l'outil
    trochoidal: bool = False        # détourage trochoïdal : l'outil avance en boucles (engagement réduit)
    troch_width: float = 0.0        # … largeur de la rainure (mm, 0 : 1,5 × diamètre de l'outil)
    troch_step: float = 0.0         # … avance par boucle (mm, 0 : 10 % du diamètre)
    loop_angle_min: float = 5.0     # découpe à boucles : pas de boucle pour un virage plus faible (°)
    loop_angle_max: float = 165.0   # découpe à boucles : ni pour un virage plus fort (°)
    corner_round: float = 0.0       # découpe : arrondi supplémentaire des angles de la pièce (mm)
    offset_add: float = 0.0         # découpe : décalage supplémentaire du parcours (mm, négatif : vers la pièce)
    loop_min_side: float = 0.1      # boucles aux angles : côtés plus courts (courbes aplaties) ignorés
    loop_length: float = 5.5        # boucles aux angles : distance d'entrée / sortie de la boucle (mm)
    loop_radius: float = 2.5        # boucles aux angles : rayon de la boucle (mm)
    loop_check: bool = True         # boucles aux angles : réduites ou omises si elles touchent le dessin ou la matière
    chamfer_width: float = 0.3      # chanfrein des bords : largeur du chanfrein sur le dessus (mm)
    gravure_rule: int = 881          # gravure 3D : relevé dans TE13. 878 : cadre ignoré, le fond va jusqu'à lui ; profondeur sans limite par le corps de l'outil. 879 : ordre du fond par branches. 881 : intaille sans branches parasites
    finish_rule: int = 877           # finition : 877, le trajet relevé dans TE13 ; avant, un anneau puis les tirés d'angle à part
    finish_3d_only: bool = False     # finition : les tirés d'angle et les parties étroites, sans le contour
    prism_hollow: bool = False       # lettres prismatiques : en creux (le fond sous le contour décalé) ; sinon en relief
    prism_lateral: bool = False      # lettres prismatiques : passes latérales (à chaque niveau, les contours décalés jusqu'au bord)
    #: lettres prismatiques en relief : la matière laissée par les opérations d'avant entre les lettres et le passage de
    #: leur outil (XY), enlevée à chaque niveau (demande du 19/11)
    prism_rest: bool = False
    gamme_rule: int = 0              # gamme : 885, le trajet relevé dans TE13 (voir `gamme.cone_step`) ; 0, celui d'avant
    prism_rule: int = 1113           # lettres prismatiques : 1113, le relief garde l'outil hors des formes ; 882, le trajet relevé dans TE13
    #                                  (le toit taillé dans la lettre) ; avant, le contour décalé de la pointe à chaque niveau
    vcarve_edges_only: bool = False  # gravure 2,5D : bords et tirés d'angle seulement (finition TypeEdit)
    vcarve_max_steps: int = 0       # gravure 2,5D, poche : seules les n passes les plus proches du bord (0 : toutes)
    vcarve_mode: str = 'passes'     # gravure 2,5D : 'passes' (décalages), 'axe' (ligne médiane, intaille optimisée), 'axe_ar' (intaille standard : un flanc à l'aller, l'autre au retour)
                                    # ou 'contour' (contour 2D au fond, sans remontées d'angle, puis vidage)
    vcarve_offset: float = 0.0      # contour 2D : décalage XY du contour (mm, + vers l'intérieur de la forme)
    vcarve_step: float = 0.0        # gravure 2,5D : passe en Z (mm) — paliers jusqu'au fond ; 0 : en une fois
    vcarve_walls: bool = True       # gravure 2,5D : passes sur les flancs avant le fond ; sans : comme TE13, le fond et le bord à chaque passe
    vcarve_finish: bool = False     # gravure 2,5D : passe de finition — avec une surépaisseur XY, les bords et les tirés d'angle
                                    # repris sur la forme exacte, à l'avance de finition (demande du 15/11)
    sweep_texture: bool = False     # balayage : fond texturé (coups de gouge aléatoires, TypeEdit : Texturing)
    tex_depth_min: float = 0.3      # texturing : profondeur des coups (mm)
    tex_depth_max: float = 0.6
    tex_len_min: float = 2.5        # texturing : longueur des coups (mm)
    tex_len_max: float = 5.0
    tex_overlap: float = 40.0       # texturing : chevauchement d'un coup sur le suivant (%)
    tex_seed: int = 1               # texturing : tirage (autre nombre : autre texture)
    copies_x: int = 1               # multicopie du parcours : colonnes
    copies_y: int = 1               # multicopie du parcours : rangées
    copies_dx: float = 0.0          # pas entre colonnes (mm, 0 : largeur des objets + écart)
    copies_dy: float = 0.0          # pas entre rangées (mm, 0 : hauteur des objets + écart)
    copies_gap: float = 5.0         # écart entre copies quand le pas est calculé (mm)
    emboss_edge: float = 0.0        # fer à dorer : largeur laissée au bord des lettres (mm)
    emboss_width: float = 2.0       # fer à dorer : largeur maxi du demi-profil (mm)
    emboss_start_angle: float = 0.0  # fer à dorer : angle de départ du profil (°, au bord, depuis la verticale ; 0 : le plus raide que l'outil permet)
    emboss_end_angle: float = 0.0   # fer à dorer : angle d'arrivée (°, au fond, depuis l'horizontale)
    emboss_side: str = 'dedans'     # fer à dorer : galbe 'dedans' les formes (TE), ou 'autour' (elles restent en relief)
    emboss_passes: str = 'standard'  # fer à dorer : 'standard' (concentriques), 'intaille' (ligne centrale), 'les_deux'
    pass_depths: str = ''           # profondeurs des passes successives (mm, « 0,6 0,5 0,4 ») ; vide : passes égales
    pass_order: str = 'poche'       # passes multiples : 'poche' (chaque poche / contour jusqu'au fond) ou 'global'
    link_passes: bool = False       # d'une passe à la suivante : rester dans la matière, descente en rampe (TE : ConnectToolpath)
    link_rule: int = 872            # 872 : en rampe sans connexion, l'outil remonte à chaque passe (avant : jamais)
    #: lier au parcours précédent (gamme TypeEdit) : seulement la matière laissée par les opérations d'avant
    link_previous: bool = False
    #: poche, seulement le reste (ébauche puis finition) : ce que les poches d'avant n'ont pas vidé, rien d'autre
    rest_previous: bool = False
    #: reprise d'usinage (voir restart.py) : premier et dernier point, empreinte du parcours au moment du choix ; vide : aucune
    restart_from: int = 0
    restart_to: int = 0
    restart_sig: str = ''
    pocket_mode: str = 'concentrique'  # poche : 'concentrique' ou 'balayage' (passes parallèles, TypeEdit)
    stepover_mm: float = 0.0        # poche : distance entre passes (mm, 0 = recouvrement de l'outil)
    sweep_angle: float = 0.0        # balayage : angle des passes (°)
    sweep_angle_mode: str = 'fixe'  # balayage : 'fixe', 'optimise' (le long de la forme), 'croise' (X et Y)
    sweep_direction: str = 'aller_retour'  # balayage : 'aller_retour', 'opposition', 'avalant'
    sweep_by_zone: bool = True      # balayage : une zone finie avant la suivante ; sinon de haut en bas, en sautant les îlots
    sweep_angle_incr: float = 90.0  # balayage « X et Y » : rotation d'une passe à la suivante (°)
    sweep_rule: int = 876           # 876 : rangées, liaisons et entrées relevées dans TE13 (avant : un remplissage centré, sans suivre les bords)
    sweep_contour: str = 'apres'    # balayage : tour du contour (cassé d'angle) 'sans', 'avant', 'apres'
    safe_z: float = 2.0             # hauteur de dégagement (mm)
    safe_z_faced: float = 0.2       # dégagement au-dessus d'une zone déjà surfacée par une opération d'avant (0 : sans)
    clear_z: float = 0.5            # hauteur d'approche au-dessus de la pièce
    feed: float = 0.0               # 0 = celle de l'outil
    plunge: float = 0.0
    spindle: float = 0.0
    #: cadre de vitesses actif : 'ebauche' (avance, plongée, broche) ou 'finition' (avance de finition)
    feed_frame: str = 'ebauche'
    finish_feed: float = 0.0        # avance de finition (mm/min) ; 0 = celle de l'outil, sinon celle d'ébauche
    resolution: float = 0.1         # relief : pas de la carte ; gravure 2,5D : pas des retraits (mm)
    invert: bool = False            # relief : blanc en creux (sinon noir en creux)
    hatch_angle: float = 0.0        # gravure laser : angle des lignes (°) ; pas = `resolution`
    hatch_step: float = 0.0         # gravure laser : rotation des lignes à chaque passage (°)
    hatch_cross: bool = False       # gravure laser : seconde nappe à +90° dans le même passage
    hatch_inset: float = 0.0        # gravure laser : retrait du remplissage dans le contour (mm)
    fill_order: str = 'global'      # gravure laser : 'global' (ligne à ligne sur tout), 'forme' (forme par
                                    # forme), 'zones' (par carreaux fill_dx × fill_dy) — TypeEdit : Optimisation
    fill_dx: float = 10.0           # … largeur des carreaux (mm)
    fill_dy: float = 10.0           # … hauteur des carreaux (mm)
    hatch_auto: bool = False        # gravure laser : lignes dans le sens de la longueur de chaque morceau
                                    # (hatch_angle s'y ajoute) — TypeEdit : Automatic orientation
    laser_passes: int = 1           # laser : nombre de passages
    line_width: float = 0.0         # marquage laser : épaisseur du trait par passages parallèles (mm, 0 = simple)
    line_step: float = 0.0          # écart entre ces passages (mm, 0 = 80 % du Ø du faisceau)
    lead_in: float = 0.0            # détourage, découpe laser : entrée tangente en quart de cercle (rayon, mm, 0 = sans)
    lead_out: float = 0.0           # détourage, découpe laser : sortie tangente (rayon, mm, 0 = sans)
    lead_mode: str = 'arc'          # 'arc' : quart de cercle de rayon lead_in / lead_out ; 'ligne' : droite de cette longueur ;
                                    # 'percage' : perçage à cette distance, en goutte (TE, page 661)
    lead_angle: float = 45.0        # 'ligne' : angle de l'entrée avec le contour (°, 90 = perpendiculaire)
    lead_out_angle: float = 45.0    # 'ligne' : angle de la sortie avec le contour (°)
    lead_pierce: float = 0.0        # rayon de perçage : celui de la goutte, et le contrôle des contours voisins (mm, 0 = sans)
    lead_transition: float = 0.0    # rayon de transition de TE13 (R) : celui de la goutte, à la place du rayon de perçage (mm, 0 = sans)
    start_policy: str = 'proche'    # contours fermés : 'proche' (au plus près) ou 'dessin' (leur point de départ) ; les points
                                    # choisis à la main (Mode Point) sont toujours respectés
    leave_uncut: float = 0.0        # détourage : matière laissée avant la fin du contour (mm, 0 = coupé en entier)
                                    # — la pièce reste tenue (TypeEdit : With remaining material)
    wobble: str = 'none'            # laser : oscillation du faisceau (cam.wobble.SHAPES)
    wobble_amplitude: float = 0.0   # laser : amplitude de l'oscillation (mm)
    wobble_pitch: float = 0.0       # laser : avance par tour d'oscillation (mm)
    wrap: str = 'none'              # enroulement sur une pièce cylindrique ou conique (cam.wrap.MODES)
    wrap_radius: float = 0.0        # enroulement : rayon de la pièce (mm ; cône : à la cote 0 de l'axe)
    wrap_origin: float = 0.0        # enroulement : génératrice du dessus, en travers de l'axe (mm)
    wrap_radius2: float = 0.0       # cône : rayon à la cote `wrap_length` de l'axe (mm)
    wrap_length: float = 0.0        # cône : écart entre les deux rayons, le long de l'axe (mm)
    wrap_model: str = ''            # projection parallèle : fichier STEP de la pièce
    model_path: str = ''            # usinage 3D : fichier de la pièce (STEP, STL, 3D XML) ; vide : celui du dessin
    faces3d: list = field(default_factory=list)      # usinage 3D : faces choisies dans la vue 3D ; vide : toute la pièce
    contours3d: list = field(default_factory=list)   # usinage 3D : contours fermés choisis [[x, y, z], …]
    contours3d_pl: dict = field(default_factory=dict)  # placement de la pièce (comme le dessin) au choix des
    #                                                    contours : ils la suivent ensuite ; vide : celui du moment
    slope_min: float = 0.0          # usinage 3D : seulement les pentes d'au moins … (°) — niveaux constants : parois
    setup_face: str = ''            # usinage 3D : face de la pièce vers l'outil (prise) ; vide : celle du dessin
    body3d: int = -1                # usinage 3D : corps usiné seul (pièce à plusieurs corps) ; -1 : toute la pièce
    body3d_ref: dict = field(default_factory=dict)   # volumes du dessin : {'item': objet volume, 'n': body3d d'alors}
    slope_max: float = 90.0         # usinage 3D : seulement les pentes d'au plus … (°) — balayage : pentes douces
    thread: str = 'M4'              # taraudage : filetage (THREADS)
    thread_left: bool = False       # taraudage : filet à gauche
    thread_external: bool = False   # filetage (vis) : la fraise tourne autour, dehors
    thread_start_angle: float = 0.0  # taraudage / filetage : angle de départ (°, depuis OX, sens trigonométrique)
    thread_lead: str = 'droit'      # entrée et sortie : 'droit' (radiales) ou 'arc' (tangentes)
    thread_lead_dist: float = 1.0   # filetage : distance d'entrée / sortie (mm)
    pitch: float = 0.0              # taraudage : pas (mm, 0 = pas ISO du filetage)
    hole_diameter: float = 0.0      # perçage à la fraise : Ø du trou (0 = celui du cercle dessiné)
    extension: float = 0.0          # surfaçage : débordement autour de la zone (mm)
    face_angle: float = 0.0         # surfaçage : angle des passes (°)
    face_direction: str = 'aller_retour'  # surfaçage : 'aller_retour', 'avalant' (toutes), 'opposition' (toutes)
    instruction: str = 'message'    # instruction machine (cam.instructions)
    params: dict = field(default_factory=dict)   # réglages de l'instruction
    #: rattachement à une surface posée en 2D (core.surface2d) : calque, et ce qui a changé pour lui
    surface2d: dict = field(default_factory=dict)
    enabled: bool = True
    id: str = field(default_factory=new_id)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> 'Operation':
        if d.get('kind') == 'fer_dorer' and 'emboss_side' not in d:     # d'avant le choix du côté : le galbe était autour des formes
            d = dict(d, emboss_side='autour')
        if 'prism_rule' not in d:                                       # d'avant : le parcours enregistré ne change pas
            d = dict(d, prism_rule=0)
        if 'gravure_rule' not in d:                                     # d'avant : le parcours enregistré ne change pas
            d = dict(d, gravure_rule=0)
        if 'finish_rule' not in d:                                      # d'avant : le parcours enregistré ne change pas
            d = dict(d, finish_rule=0)
        if 'sweep_rule' not in d:                                       # d'avant : le parcours enregistré ne change pas
            d = dict(d, sweep_rule=0, sweep_by_zone=bool(d.get('sweep_by_zone', False)))
        if 'link_rule' not in d and d.get('ramp') and d.get('kind') in ('contour', 'gravure'):
            d = dict(d, link_passes=True)                               # d'avant : en rampe, l'outil restait dans la matière
        return _from_dict(cls, d)


@dataclass
class Move:
    """Mouvement d'un parcours : rapide, avance, plongée en ligne droite,
    ou arc (horaire / anti-horaire, centre cx, cy) — les parcours calculés
    par VectorDrive sont aplatis ; ceux de TypeEdit gardent leurs arcs."""
    kind: str                       # 'rapid', 'feed', 'plunge', 'arc_cw', 'arc_ccw'
    x: float
    y: float
    z: float
    cx: float = 0.0
    cy: float = 0.0
    #: avance d'une passe de finition (le tour à la surépaisseur enlevée) : faite à l'avance de finition s'il y en a une
    #: (voir `move_feed`) ; hors des comparaisons
    fin: bool = field(default=False, compare=False, repr=False)

    @property
    def is_arc(self) -> bool:
        return self.kind in ('arc_cw', 'arc_ccw')


def arc_sweep(start, m: Move) -> tuple[float, float, float]:
    """(rayon, angle de départ, balayage signé) d'un arc partant de `start`."""
    x0, y0 = start[0], start[1]
    r = math.hypot(x0 - m.cx, y0 - m.cy)
    a0 = math.atan2(y0 - m.cy, x0 - m.cx)
    sweep = math.atan2(m.y - m.cy, m.x - m.cx) - a0
    if m.kind == 'arc_ccw':
        if sweep <= 1e-12:
            sweep += 2 * math.pi
    elif sweep >= -1e-12:
        sweep -= 2 * math.pi
    return r, a0, sweep


def arc_length(start, m: Move) -> float:
    """Longueur exacte d'un arc (hélice comprise)."""
    r, _a0, sweep = arc_sweep(start, m)
    return math.hypot(r * abs(sweep), m.z - start[2])


def _drop_aligned(pts: list, tol: float) -> list:
    """Points intermédiaires alignés (à `tol` près) retirés."""
    if len(pts) < 3:
        return pts
    out = [pts[0]]
    for i in range(1, len(pts) - 1):
        a, b, c = out[-1], pts[i], pts[i + 1]
        dx, dy = c[0] - a[0], c[1] - a[1]
        L = (dx * dx + dy * dy) ** 0.5
        if L < 1e-12 or abs((b[0] - a[0]) * dy - (b[1] - a[1]) * dx) / L > tol:
            out.append(b)
    out.append(pts[-1])
    return out


def arc_points(start, m: Move, tol: float = 0.01) -> list[tuple[float, float, float]]:
    """Points d'un arc (z interpolé : hélice), sans le départ."""
    z0 = start[2]
    r, a0, sweep = arc_sweep(start, m)
    if r <= 1e-9:
        return [(m.x, m.y, m.z)]
    step = 2 * math.acos(max(-1.0, 1 - tol / r)) if tol < r else math.pi / 4
    n = max(1, math.ceil(abs(sweep) / max(step, 1e-6)))
    n = min(n, 10000)
    out = [(m.cx + r * math.cos(a0 + sweep * k / n), m.cy + r * math.sin(a0 + sweep * k / n),
            z0 + (m.z - z0) * k / n) for k in range(1, n)]
    out.append((m.x, m.y, m.z))
    return out


@dataclass
class Toolpath:
    """Parcours d'une opération."""
    op_id: str
    tool_id: str
    moves: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    name: str = ''
    source: str = 'vectordrive'     # ou 'typeedit' (parcours importé)
    #: cycles machine équivalents (trous) : [{kind, x, y, depth, …}] en mm — les
    #: post-processeurs qui en ont (Datron) les écrivent au lieu des mouvements
    cycles: list = field(default_factory=list)
    #: identité du calcul (un recalcul donne un nouveau parcours) : la session ne réécrit que ce qui a changé
    uid: str = field(default_factory=lambda: uuid.uuid4().hex[:12], compare=False, repr=False)
    #: zones du dessin que le parcours signale, montrées avec lui : [{'kind': 'ile', 'pts': [[x, y], …]}] — îles
    #: gardées malgré l'arrondi des angles d'un détourage intérieur
    zones: list = field(default_factory=list, compare=False)
    #: mouvements d'avant les liaisons basses sur zone surfacée (voir strategies.apply_faced), pour les refaire
    unfaced: list | None = field(default=None, compare=False, repr=False)
    #: reprise d'usinage : (mouvements, cycles, unfaced) du parcours complet (voir restart.py)
    uncut: tuple | None = field(default=None, compare=False, repr=False)

    def lengths(self) -> tuple[float, float]:
        """(longueur en avance, longueur en rapide), mm."""
        feed = rapid = 0.0
        prev = None
        for m in self.moves:
            if prev is not None:
                if m.is_arc:
                    d = arc_length((prev.x, prev.y, prev.z), m)
                else:
                    d = math.dist((prev.x, prev.y, prev.z), (m.x, m.y, m.z))
                if m.kind == 'rapid':
                    rapid += d
                else:
                    feed += d
            prev = m
        return feed, rapid

    def polylines(self, tol: float = 0.02) -> list[tuple[str, list]]:
        """Tracés pour l'affichage : (nature, points 3D) — 'rapid' ou
        'feed' (avance, plongée et arcs aplatis)."""
        out: list[tuple[str, list]] = []
        prev = None
        for m in self.moves:
            kind = 'rapid' if m.kind == 'rapid' else 'feed'
            if prev is None:
                prev = (m.x, m.y, m.z)
                continue
            pts = arc_points(prev, m, tol) if m.is_arc else [(m.x, m.y, m.z)]
            if out and out[-1][0] == kind:
                out[-1][1].extend(pts)
            else:
                out.append((kind, [prev] + pts))
            prev = (m.x, m.y, m.z)
        return out

    def drawing(self, tol: float = 0.01, simplify: float = 0.001) -> list[list[tuple[float, float]]]:
        """Trajectoire du centre de l'outil en traits 2D (avances seules, une
        polyligne par passage continu au même Z) — pour la reprendre dans le
        dessin ; points alignés retirés à `simplify` près."""
        out, cur, prev = [], [], None
        for m in self.moves:
            if prev is None or m.kind in ('rapid', 'plunge') or (m.kind == 'feed' and abs(m.z - prev[2]) > 1e-9
                                                                 and abs(m.x - prev[0]) + abs(m.y - prev[1]) < 1e-9):
                if len(cur) >= 2:
                    out.append(cur)
                cur = [(m.x, m.y)]
                prev = (m.x, m.y, m.z)
                continue
            pts = arc_points(prev, m, tol) if m.is_arc else [(m.x, m.y, m.z)]
            for p in pts:
                q = (p[0], p[1])
                if not cur or (q[0] - cur[-1][0]) ** 2 + (q[1] - cur[-1][1]) ** 2 > 1e-18:
                    cur.append(q)
            prev = (m.x, m.y, m.z)
        if len(cur) >= 2:
            out.append(cur)
        if simplify > 0:
            out = [_drop_aligned(c, simplify) for c in out]
        return out

    def bbox(self):
        if not self.moves:
            return None
        xs = [m.x for m in self.moves]
        ys = [m.y for m in self.moves]
        zs = [m.z for m in self.moves]
        return (min(xs), min(ys), min(zs), max(xs), max(ys), max(zs))


@dataclass
class CamSetup:
    """Réglage FAO d'un document : bibliothèque d'outils du document,
    opérations dans l'ordre d'usinage, machine et post-processeur."""
    tools: list = field(default_factory=list)
    operations: list = field(default_factory=list)
    machine: str = ''               # nom de la machine (fiche .MAH ou intégrée)
    post: str = 'gcode'             # post-processeur
    tolerance: float = 0.01         # aplatissement des courbes (mm)
    collet_length: float = 0.0      # broche : longueur d'outil serrée dans la pince (mm, 0 = inconnue)
    nut_diameter: float = 0.0       # broche : Ø de l'écrou de pince (mm, 0 = inconnu)
    laser_field: float = 110.0      # laser à scanner : côté du champ de marquage (mm)
    laser_tiles: bool = False       # laser : graver en morceaux ce qui dépasse le champ (cam.tiling)
    laser_margin: float = 2.0       # morceaux : marge au bord du champ (mm)
    laser_marks: bool = False       # morceaux : traits de raccord aux frontières
    #: programmes : segments ajustés en arcs G2 / G3 à cette tolérance (mm ; 0 = segments seuls)
    arc_fit: float = 0.01
    output_orient: str = 'normal'   # orientation de la plaque dans le programme (`cam.post.ORIENTATIONS`)
    #: zéro des programmes (`cam.post.ZEROS`) : 'machine' (celui qu'attend la machine, sinon l'origine du dessin),
    #: 'dessin' (origine du dessin), 'plaque_hg', 'plaque_centre', 'plaque_bg'
    program_zero: str = 'machine'
    program_group: str = 'tout'     # programmes : 'tout' (un fichier), 'plan' (un par plan), 'parcours' (un par parcours)
    #: réglages propres à un post-processeur, par clé de post (ex. {'datron': {'touche': 3}}) — gardés avec le dessin
    post_options: dict = field(default_factory=dict)
    #: brut de la pièce 3D (`core.stock3d` : bloc, barre ronde, plaque, marges) ; vide : aucun
    stock3d: dict = field(default_factory=dict)
    #: brut du dessin 2D (`core.stock2d` : plaque ou contour dessiné, marges, surépaisseur) ; vide : plaque plate à Z 0
    stock2d: dict = field(default_factory=dict)
    #: parcellisation : réglages gardés avec le dessin (`ui.panels_dialog`)
    panels: dict = field(default_factory=dict)

    def tool(self, tool_id: str) -> CamTool | None:
        return next((t for t in self.tools if t.id == tool_id), None)

    def to_dict(self) -> dict:
        return {'tools': [t.to_dict() for t in self.tools],
                'operations': [o.to_dict() for o in self.operations],
                'machine': self.machine, 'post': self.post, 'tolerance': self.tolerance,
                'laser_field': self.laser_field, 'laser_tiles': self.laser_tiles,
                'laser_margin': self.laser_margin, 'laser_marks': self.laser_marks,
                'collet_length': self.collet_length, 'nut_diameter': self.nut_diameter, 'arc_fit': self.arc_fit,
                 'output_orient': self.output_orient, 'program_group': self.program_group,
                'program_zero': self.program_zero,
                'post_options': {k: dict(v) for k, v in (self.post_options or {}).items() if isinstance(v, dict)},
                'stock3d': dict(self.stock3d or {}), 'stock2d': dict(self.stock2d or {}),
                'panels': dict(self.panels or {})}

    @classmethod
    def from_dict(cls, d: dict) -> 'CamSetup':
        d = d or {}
        return cls(tools=[CamTool.from_dict(t) for t in d.get('tools', [])],
                   operations=[Operation.from_dict(o) for o in d.get('operations', [])],
                   machine=d.get('machine', ''), post=d.get('post', 'gcode'),
                   tolerance=float(d.get('tolerance', 0.01)),
                   laser_field=float(d.get('laser_field', 110.0) or 110.0),
                   laser_tiles=bool(d.get('laser_tiles', False)),
                   laser_margin=float(d.get('laser_margin', 2.0)),
                   laser_marks=bool(d.get('laser_marks', False)),
                   collet_length=float(d.get('collet_length', 0.0) or 0.0),
                   nut_diameter=float(d.get('nut_diameter', 0.0) or 0.0),
                   arc_fit=max(0.0, float(d.get('arc_fit', 0.01) or 0.0)),
                   output_orient=str(d.get('output_orient', 'normal') or 'normal'),
                   program_zero=str(d.get('program_zero', 'machine') or 'machine'),
                   program_group=str(d.get('program_group', 'tout') or 'tout'),
                   post_options={str(k): dict(v) for k, v in (d.get('post_options') or {}).items()
                                 if isinstance(v, dict)},
                   stock3d=dict(d.get('stock3d') or {}) if isinstance(d.get('stock3d'), dict) else {},
                   stock2d=dict(d.get('stock2d') or {}) if isinstance(d.get('stock2d'), dict) else {},
                   panels=dict(d.get('panels') or {}) if isinstance(d.get('panels'), dict) else {})


def holder_of(tool, setup) -> tuple[float, float]:
    """(dépassement hors pince, Ø du porte-outil) d'un outil : ses valeurs,
    sinon celles de la machine — dépassement estimé comme NeoDrive : longueur
    totale du catalogue (L1) moins la longueur serrée, jamais moins que la
    longueur utile + 1 mm. (0, 0) : inconnus, rien n'est vérifié."""
    if tool is None:
        return 0.0, 0.0
    so = float(getattr(tool, 'stickout', 0.0) or 0.0)
    if so <= 0 and getattr(setup, 'collet_length', 0.0) > 0:
        g = getattr(tool, 'geometry', None) or {}
        try:
            L1 = float(g.get('L1') or 0.0)
            useful = max(float(g.get('L2') or 0.0), float(g.get('L3') or 0.0), float(tool.cut_length or 0.0))
        except (TypeError, ValueError):
            L1 = useful = 0.0
        if L1 > 0:
            so = max(L1 - setup.collet_length, useful + 1.0, 1.0)
    hd = float(getattr(tool, 'holder_diameter', 0.0) or 0.0) or float(getattr(setup, 'nut_diameter', 0.0) or 0.0)
    return so, hd


def group_by_tool(ops: list, anchor: int | None = None) -> list:
    """Opérations regroupées par outil (TypeEdit : fusionner les parcours) :
    celles de l'outil de l'opération `anchor` mises à sa suite, dans leur
    ordre ; sans `anchor`, toutes, chaque outil à la place de sa première
    opération. Les instructions machine (sans outil) restent où elles sont
    par rapport à l'opération qui les suit. Ordre relatif d'un même outil
    gardé."""
    if anchor is not None:
        tool = ops[anchor].tool_id
        if not tool:
            return list(ops)
        moved = {i for i, o in enumerate(ops) if i > anchor and o.tool_id == tool and o.kind != 'instruction'}
        rest = [o for i, o in enumerate(ops) if i not in moved]
        return rest[:anchor + 1] + [ops[i] for i in sorted(moved)] + rest[anchor + 1:]
    blocks: list = []                                   # [outil, opérations] dans l'ordre des premières
    pending = []                                        # instructions en attente de l'opération suivante
    for o in ops:
        if o.kind == 'instruction' or not o.tool_id:
            pending.append(o)
            continue
        blk = next((b for b in blocks if b[0] == o.tool_id), None)
        if blk is None:
            blocks.append([o.tool_id, pending + [o]])
        else:
            blk[1].extend(pending + [o])
        pending = []
    return [o for _t, group in blocks for o in group] + pending


def tool_changes(ops: list) -> int:
    """Changements d'outil d'une suite d'opérations actives."""
    n, cur = 0, None
    for o in ops:
        if o.enabled and o.kind != 'instruction' and o.tool_id and o.tool_id != cur:
            n += 1
            cur = o.tool_id
    return n


def setup_of(doc) -> CamSetup:
    """Réglage FAO du document (vide s'il n'y en a pas)."""
    return CamSetup.from_dict(doc.extra.get('fao') if isinstance(doc.extra, dict) else None)


#: vitesses d'un outil dont les changements entrent dans son historique
FEED_KEYS = ('spindle', 'feed', 'finish_feed', 'plunge', 'ramp_feed')


def op_feed(op, tool) -> float:
    """Avance de coupe d'une opération, d'après son cadre actif (demande du 14/11, 19 h 45). Ébauche : celle de
    l'opération, sinon de l'outil. Finition : l'avance de finition de l'opération, sinon de l'outil, sinon celle
    d'ébauche."""
    rough = float(getattr(op, 'feed', 0.0) or 0.0) or float(getattr(tool, 'feed', 0.0) or 0.0)
    if getattr(op, 'feed_frame', 'ebauche') == 'finition':
        return float(getattr(op, 'finish_feed', 0.0) or 0.0) or float(getattr(tool, 'finish_feed', 0.0) or 0.0) \
            or rough
    return rough


def finish_feed_of(op, tool) -> float:
    """Avance des passes de finition (mm/min) : celle de l'opération (cadre Finition), sinon celle de l'outil — sauf si
    l'opération impose sa propre avance d'ébauche (une avance d'outil plus vive ne la dépasse pas) ; 0 : aucune."""
    own = float(getattr(op, 'finish_feed', 0.0) or 0.0)
    if own > 0:
        return own
    if float(getattr(op, 'feed', 0.0) or 0.0) > 0:
        return 0.0
    return float(getattr(tool, 'finish_feed', 0.0) or 0.0)


def move_feed(m, op, tool) -> float:
    """Avance (mm/min) d'un mouvement de coupe : une passe de finition (`Move.fin`) à l'avance de finition de
    l'opération ou de l'outil s'il y en a une (demande du 14/11, 19 h 45) ; le reste à l'avance du cadre actif."""
    if getattr(m, 'fin', False):
        f = finish_feed_of(op, tool)
        if f > 0:
            return f
    return op_feed(op, tool)


def note_change(tool, key: str, before, after, source: str = '') -> None:
    """Un changement de vitesse dans l'historique de l'outil (les 50 derniers gardés)."""
    from datetime import datetime
    hist = list(getattr(tool, 'history', None) or [])
    hist.append({'date': datetime.now().isoformat(timespec='seconds'), 'champ': key,
                 'avant': float(before or 0.0), 'apres': float(after or 0.0), 'source': source})
    tool.history = hist[-50:]


def history_lines(tool, labels: dict | None = None) -> list:
    """L'historique des vitesses de l'outil, du plus récent au plus ancien, une ligne par changement."""
    out = []
    for h in reversed(list(getattr(tool, 'history', None) or [])):
        if not isinstance(h, dict):
            continue
        key = str(h.get('champ', ''))
        lab = (labels or {}).get(key, key)
        src = str(h.get('source') or '')
        out.append(f"{str(h.get('date', '')).replace('T', ' ')} — {lab} : {float(h.get('avant') or 0):g} → "
                   f"{float(h.get('apres') or 0):g}" + (f' ({src})' if src else ''))
    return out


def store(doc, setup: CamSetup) -> None:
    doc.extra['fao'] = setup.to_dict()
