"""F10 : toutes les options, par onglets.

Chaque option est décrite une fois (`SPEC`) : clé des réglages, libellé,
nature, valeur par défaut. La fenêtre se construit d'après la liste ;
`MainWindow.apply_options` met les valeurs en œuvre. `value(settings, key)`
rend la valeur d'une option, avec sa valeur par défaut.
"""
from __future__ import annotations

import pathlib
from dataclasses import dataclass, field

from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFileDialog,
                               QFontComboBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QScrollArea, QSpinBox,
                               QTabWidget, QToolButton, QVBoxLayout, QWidget)

from ..i18n import tr


@dataclass(frozen=True)
class Opt:
    key: str
    label: str
    kind: str                     # float, int, bool, choice, text, folder, folders, file, font, theme, color
    default: object = None
    lo: float = 0.0
    hi: float = 1e6
    suffix: str = ''
    decimals: int = 3
    choices: tuple = ()           # (valeur, libellé)
    tip: str = ''
    restart: bool = False         # prend effet au prochain démarrage
    extra: dict = field(default_factory=dict)


def F(key, label, default, lo=0.0, hi=1e6, suffix='', decimals=3, **kw):
    return Opt(key, label, 'float', default, lo, hi, suffix, decimals, **kw)


def I(key, label, default, lo=0, hi=100000, suffix='', **kw):
    return Opt(key, label, 'int', default, lo, hi, suffix, 0, **kw)


def B(key, label, default, **kw):
    return Opt(key, label, 'bool', default, **kw)


def C(key, label, default, choices, **kw):
    return Opt(key, label, 'choice', default, choices=tuple(choices), **kw)


SPEC: list[tuple[str, list[Opt]]] = [
    ('Général', [
        C('options/langue', 'Langue', '', [('', 'Langue du système'), ('fr', 'Français'), ('en', 'English')],
          restart=True),
        I('options/annulations', 'Nombre d\'annulations', 200, 10, 2000),
        B('options/annulations_liste', 'Défaire et Refaire montrent la liste des modifications', True,
          tip='Quelques secondes, par-dessus le plan de travail : un clic sur une ligne revient à cette étape'),
        I('options/autosave_min', 'Sauvegarde de récupération toutes les', 3, 1, 60, ' min'),
        I('fichiers/max_recents', 'Fichiers récents retenus', 12, 1, 50),
        B('options/session', 'Fermer sans question et tout rouvrir au démarrage (onglets, dessins modifiés, fenêtre)',
          True, restart=True,
          tip='Les dessins modifiés reviennent tels quels, à enregistrer quand vous le décidez ; '
              'vos fichiers ne sont jamais écrits sans vous'),
        B('options/ouvrir_dernier', 'Rouvrir le dernier dessin au démarrage (sans la session)', False),
        I('options/decimales', 'Décimales des cotes affichées', 3, 0, 6),
    ]),
    ('Apparence', [
        Opt('vue/theme', 'Thème', 'theme', 'crepuscule', extra={'systeme': True},     # themes.DEFAULT_KEY
            tip='Thème de l\'interface ; « Suivre le système » prend le thème clair ou sombre préféré'),
        Opt('vue/theme_clair', 'Thème clair préféré', 'theme', 'clair', extra={'only': 'clair'},
            tip='Mode sombre désactivé, ou système en clair'),
        Opt('vue/theme_sombre', 'Thème sombre préféré', 'theme', 'sombre', extra={'only': 'sombre'},
            tip='Mode sombre (Vue > Affichage), ou système en sombre'),
        Opt('vue/accent', 'Couleur d\'accent', 'color', '', tip='Boutons cochés, onglet actif, sélection des listes'),
        B('vue/police_ui_perso', 'Police de l\'interface personnalisée', False),
        Opt('vue/police_ui', 'Police de l\'interface', 'font', 'Segoe UI'),
        I('vue/taille_police_ui', 'Taille du texte de l\'interface (0 : celle du système)', 0, 0, 24, ' pt'),
        C('vue/densite', 'Densité', 'normale', [('compacte', 'Compacte'), ('normale', 'Normale'), ('aeree', 'Aérée')]),
        I('vue/arrondi', 'Arrondi des boutons', 3, 0, 12, ' px'),
        C('vue/ruban_icones', 'Icônes du ruban', 'normales',
          [('petites', 'Petites'), ('normales', 'Normales'), ('grandes', 'Grandes')]),
        B('vue/ruban_libelles', 'Libellés sous les icônes du ruban', True),
        C('vue/legendes', 'Légendes des groupes du ruban', 'theme',
          [('theme', 'Selon le thème'), ('bandeau', 'Bandeau coloré (TypeEdit)'), ('texte', 'Texte seul'),
           ('aucune', 'Aucune')]),
        C('vue/ruban_familles', 'Groupes du ruban', 'place',
          [('place', 'Repliés en familles quand la place manque'),
           ('toujours', 'Toujours repliés en familles (un clic déroule la barre)')],
          tip='Le ruban ne défile jamais : une famille repliée est un bouton, un clic dessus déroule sa barre'),
        B('vue/ruban_reduit', 'Ruban réduit aux onglets (Ctrl+F1, double-clic sur un onglet)', False),
        C('vue/disposition', 'Disposition du ruban', 'theme',
          [('theme', 'Selon le thème (TypeEdit 13 : celle de TypeEdit 13)'), ('vectordrive', 'VectorDrive'),
           ('typeedit13', 'TypeEdit 13 (lue dans le TypeEdit 13 du poste)')]),
        Opt('vue/c_fond', 'Plan de travail : fond', 'color', ''),
        Opt('vue/c_page', 'Plan de travail : page', 'color', ''),
        Opt('vue/c_plaque', 'Plan de travail : plaque', 'color', ''),
        Opt('vue/c_grille', 'Plan de travail : grille', 'color', ''),
        Opt('vue/c_selection', 'Plan de travail : objets sélectionnés', 'color', ''),
        Opt('vue/c_apercu', 'Plan de travail : aperçu du tracé', 'color', ''),
        Opt('vue/c_accrochage', 'Plan de travail : accrochage', 'color', ''),
    ]),
    ('Dessin', [
        B('options/proportions', 'Respecter les proportions (case cochée par défaut)', True,
          tip='État de la case « Conserver les proportions » du panneau Dimensions'),
        B('meme_taille/proportions', 'Même taille : garder les proportions', False),
        F('options/deplacement', 'Déplacement au clavier (flèches)', 1.0, 0.001, 1000, ' mm'),
        F('options/ecart_pas', 'Écart ajouté au pas proposé par Ctrl+flèche', 0.0, -1000, 1000, ' mm'),
        I('options/delai_deplacement', 'Maintien avant déplacement à la souris', 250, 0, 3000, ' ms',
          tip='Temps pendant lequel le bouton reste appuyé sur une forme avant qu’un glisser la déplace (0,25 s par '
              'défaut) : un clic qui bouge un peu ne déplace rien par mégarde'),
        F('options/grille', 'Pas de la grille d\'accrochage', 5.0, 0.01, 1000, ' mm'),
        I('options/tolerance', 'Tolérance d\'accrochage', 8, 2, 40, ' px'),
        I('options/surbrillance', 'Épaisseur de la surbrillance de la sélection', 2, 1, 12, ' px',
          tip='Épaisseur du trait des objets sélectionnés (2 px par défaut)'),
        B('options/accrochage', 'Accrochage actif au démarrage', True),
        Opt('texte/police', 'Police par défaut', 'font', 'Arial'),
        F('texte/hauteur', 'Hauteur de texte par défaut', 5.0, 0.05, 2000, ' mm'),
        I('polices/propositions', 'Reconnaissance de police : nombre de propositions', 5, 1, 50,
          tip='Liste des polices › « Reconnaître la sélection » : les polices les plus proches des lettres en courbes '
              'sélectionnées'),
        F('options/cote_texte', 'Hauteur du texte des cotes', 3.5, 0.1, 100, ' mm', 2),
        F('marqueur/taille', 'Taille des marqueurs', 3.0, 0.1, 200, ' mm'),
        F('plaque/largeur', 'Plaque des nouveaux dessins : largeur', 500.0, 1, 10000, ' mm'),
        F('plaque/hauteur', 'Plaque des nouveaux dessins : hauteur', 400.0, 1, 10000, ' mm'),
        F('plaque/epaisseur', 'Plaque des nouveaux dessins : épaisseur', 50.0, 0, 1000, ' mm'),
        F('plaque/rayon', 'Plaque des nouveaux dessins : rayon des coins', 10.0, 0, 5000, ' mm'),
        C('plaque/origine', 'Plaque des nouveaux dessins : origine (0, 0)', 'centre',
          [('centre', 'Au centre de la plaque'), ('coin', 'Au coin bas-gauche')]),
        B('proprietes/outil', 'Reproduire les propriétés : outil', True),
        B('proprietes/plein', 'Reproduire les propriétés : remplissage', True),
        B('proprietes/calque', 'Reproduire les propriétés : calque', True,
          tip='Les objets qui reçoivent les propriétés passent dans le calque de l\'objet de départ'),
        B('proprietes/texte', 'Reproduire les propriétés : mise en forme des textes', True,
          tip='Police, hauteur, largeur, espacements, alignement et styles, d\'un texte à des textes'),
        F('axe/debord', 'Ligne d\'axe : débord au-delà des traits', 2.0, 0, 1000, ' mm'),
        B('axe/tirets', 'Ligne d\'axe en trait mixte (type CENTER)', False,
          tip='Tirets longs et courts, un tiret long à chaque bout'),
        F('axe/echelle', 'Ligne d\'axe : échelle du trait mixte', 0.25, 0.01, 100, ' ×', 2,
          tip='1 : motif CENTER des DAO (tiret long de 31,75 mm) ; 0,25 : tiret long de 7,9 mm'),
    ]),
    ('Affichage', [
        B('vue/regles', 'Règles', True),
        B('vue/grille_visible', 'Grille visible au démarrage', False),
        B('vue/sens', 'Sens de parcours visible au démarrage', False),
        B('vue/remplissage', 'Contours fermés remplis au démarrage', False),
        B('vue/onglets_calques', 'Calques en onglets', False),
        B('vue/panneau_fao', 'Panneau FAO ouvert au démarrage', False),
        F('vue/zoom_pas', 'Pas du zoom (Rapprocher / Éloigner)', 1.4, 1.05, 4, '×', 2),
        I('vue/poignees', 'Taille des poignées de sélection', 7, 4, 20, ' px'),
    ]),
    ('Fichiers', [
        B('import/raccord_dxf', 'Raccorder les contours des DXF à l\'ouverture', True),
        F('raccord/tolerance', 'Tolérance de raccord', 0.01, 0.0001, 10, ' mm', 4),
        B('import/couleurs', 'Couleurs des fichiers lus gardées (DXF, SVG, PDF, EPS, AI : une couleur = un outil)', True,
          tip='Chaque couleur du fichier devient un outil du dessin, dans l\'ordre où elle apparaît (le blanc '
              'des DAO compte pour le noir) ; décoché : tout à l\'outil 1'),
        B('export/dxf_noir', 'DXF écrits : le noir aussi en couleur vraie (TypeEdit le garde noir)', True,
          tip='Le noir porte dans un DXF le numéro 7, « blanc ou noir selon le fond » : TypeEdit le dessine en blanc, '
              'invisible sur sa page, sauf si la couleur vraie est écrite aussi. Décoché : le numéro 7 seul, pour un '
              'logiciel à fond noir (AutoCAD…) où un noir vrai ne se verrait pas.'),
        C('export/dxf_courbes', 'DXF écrits : courbes', 'splines',
          [('splines', 'En courbes exactes (SPLINE) : AutoCAD, TypeEdit'),
           ('arcs', 'En arcs raccordés à 0,005 mm : tous les logiciels, LibreCAD compris')],
          tip='Une courbe de Bézier part dans un DXF en SPLINE, exacte. LibreCAD ignore les nœuds des SPLINE et la '
              'déforme dès qu’elle a plusieurs morceaux ; en arcs de cercle raccordés, le tracé est lu à '
              'l’identique partout, à 0,005 mm de la courbe.'),
        Opt('polices/dossiers', 'Dossiers de polices supplémentaires', 'folders', '',
            tip='Dossiers séparés par ; (polices TypeEdit, Type3, réseau…)'),
        Opt('symboles/dossiers_extra', 'Dossiers de symboles supplémentaires', 'folders', '', restart=True),
        B('symboles/poser_au_clic', 'Bibliothèque : double-clic, puis un clic pour poser le dessin '
          '(sinon : au centre de la vue)', True),
        C('vnd/compagnon', 'Enregistrement dans un autre format que VDZ : fichier .vdz compagnon', 'besoin',
          [('besoin', 'si des données ne tiennent pas dans ce format'), ('toujours', 'toujours'),
           ('jamais', 'jamais')],
          tip='Enregistrer en VND, DXF, SVG, PDF… écrit le fichier demandé avec tout ce que son format garde ; le '
              'compagnon (piece.vdz pour un VND, piece.dxf.vdz pour un DXF) garde le reste et est relu à '
              'l\'ouverture. Exporter n\'en écrit jamais.'),
        B('ouvrir/navigateur', 'Ouvrir (Ctrl+O) : navigateur de VectorDrive (sinon la boîte du système)', True),
        C('ouvrir/police_absente', 'Dessin ouvert dont une police manque sur le poste', 'copie',
          [('copie', 'Ses textes en VD Géo dans une copie du calque (l’original caché, intact)'),
           ('remplacement', 'Police de remplacement, dans le calque')],
          tip='La police installée ensuite, VectorDrive ouvert, les textes du calque d’origine se redessinent dans '
              'leur police : montrez-le, retirez la copie'),
        B('navigateur/caches', 'Ouvrir et Bibliothèque : montrer les éléments masqués (cachés ou système)', False),
        C('navigateur/vue', 'Ouvrir : affichage', 'details', [('details', 'Détails (comme Windows)'),
                                                              ('vignettes', 'Vignettes')]),
        C('navigateur/tri', 'Ouvrir : tri', 'nom', [('nom', 'Nom'), ('date', 'Date (récents d\'abord)'),
                                                    ('taille', 'Taille (gros d\'abord)'), ('type', 'Type')]),
        I('navigateur/taille', 'Ouvrir : taille des vignettes', 160, 48, 512, ' px'),
        B('vnd/copie_bak', 'Copie .vnd.bak avant d\'écrire par-dessus un VND', True),
        B('vnd/textes_vivants', 'Enregistrement en VND : textes TypeEdit modifiables', True,
          tip='Textes en police installée dans Windows ou de TypeEdit, sans mise en forme que TypeEdit ne garde pas ; '
              "les autres en courbes (le compte rendu de l'enregistrement dit pourquoi)"),
        B('symboles/textes_vivants', 'Symboles créés : textes TypeEdit modifiables', True,
          tip='Comme pour un VND : les textes en police installée dans Windows ou de TypeEdit ; les autres en courbes'),
        B('symboles/couleurs', 'Symboles créés : couleurs gardées (bloc VectorDrive en fin de fichier, que '
          'TypeEdit ne lit pas)', True),
        C('symboles/format', 'Symboles créés : format', 'smb',
          [('smb', 'SMB (TypeEdit)'), ('dxf', 'DXF'), ('smb+dxf', 'SMB et DXF'),
           ('vdz', 'VDZ (VectorDrive : tout est gardé)')],
          tip='Pour « Créer un symbole » et « Ajouter la sélection » de la Bibliothèque, qui lit ces formats'),
        F('image/dpi', 'Export d\'image : résolution', 300.0, 10, 4800, ' ppp', 0),
        Opt('import/convertisseur_cao', 'Convertisseur CATIA → STEP (ligne de commande)', 'text', '',
            tip='Pour ouvrir les .CATPart / .CATProduct / .cgr : par exemple "C:\\…\\convertisseur.exe" '
                '{entree} {sortie} ; VectorDrive lit ensuite le STEP écrit'),
        Opt('texte/langue_orthographe', 'Langue du correcteur d\'orthographe (vide : celle du poste ; ex. fr-FR)', 'text', ''),
        Opt('import/inkscape', 'Inkscape (pour ouvrir CorelDRAW, EMF, WMF, Visio)', 'text', '',
            tip='Chemin d\'inkscape.exe, s\'il n\'est pas à sa place habituelle. Vide : VectorDrive le cherche'),
    ]),
    ('FAO', [
        Opt('fao/post', 'Post-processeur (machine) du dessin et des nouveaux dessins', 'post', '',
            tip='Programme écrit par « Post-traiter » : le choix vaut pour le dessin ouvert et pour les nouveaux '
                'dessins (les post-processeurs viennent des plugins et des fiches machine)'),
        I('fao/opacite', 'Opacité des panneaux FAO détachés et des formulaires', 94, 40, 100, ' %',
          tip='100 % : opaques ; en dessous, le dessin se devine au travers'),
        Opt('fao/bibliotheque', 'Bibliothèque d\'outils (Mes outils) : fichier', 'file', '',
            tip='Fichier tools.json de Mes outils ; vide : outils/tools.json du dossier des données de VectorDrive'),
        Opt('fao/machines', 'Dossier des fiches machine TypeEdit (.MAH)', 'folder', ''),
        F('fao/z_degagement', 'Hauteur de dégagement des nouvelles opérations', 2.0, 0, 200, ' mm'),
        F('fao/z_surface', 'Dégagement des nouvelles opérations sur une zone déjà surfacée (0 = sans)', 0.2, 0, 50, ' mm'),
        F('fao/z_approche', 'Hauteur d\'approche des nouvelles opérations', 0.5, 0, 100, ' mm'),
        C('fao/depart', 'Départ des contours fermés des nouvelles opérations', 'proche',
          [('proche', 'Au plus près (moins de déplacements)'), ('dessin', 'Point de départ du dessin (comme TypeEdit)')],
          tip='Les points de départ choisis à la main (Mode Point) sont toujours respectés'),
        B('fao/rampe', 'Entrée en rampe des nouveaux détourages, poches et tracés (TypeEdit : plongée angulaire)', True,
          tip='Les passes connectées (TypeEdit : ConnectToolpath) vont avec la rampe dans VectorDrive ; TypeEdit, lui, '
              'demande de couper la plongée angulaire pour connecter les passes'),
        B('fao/gravure3d_flancs', 'Gravure 3D des nouvelles opérations : passes sur les flancs avant le fond', False,
          tip='Sans : comme TypeEdit, le fond et le bord à chaque passe'),
        C('fao/gravure3d_fond', 'Gravure 3D des nouvelles opérations : distance entre les passes du fond', 'pointe',
          [('pointe', '50 % de la pointe de l\'outil (comme TypeEdit)'),
           ('crete', 'Sans crête de plus de 0,02 mm (deux fois moins de passes)')]),
        B('fao/outil_propose', 'Mode expert : un nouveau parcours propose et vérifie l’outil conseillé', True,
          tip='Le plus gros outil adapté qui atteint tous les détails (outils du document et Mes outils de la '
              'machine) est choisi d’office ; la vérification s’écrit sous l’outil'),
        B('fao/rapides', 'Afficher les rapides', True),
        B('fao/panneaux_onglet', 'Onglet CAD : ranger les panneaux FAO ; un onglet FAO les rétablit', True),
        F('fao/simulation_pas', 'Pas de la simulation (0 = automatique)', 0.0, 0, 2, ' mm'),
        F('fao/vitesse_rapide', 'Temps estimé : vitesse des rapides', 15000.0, 100, 200000, ' mm/min', 0),
        F('fao/acceleration', 'Temps estimé : accélération', 1000.0, 10, 100000, ' mm/s²', 0),
        F('fao/changement_outil', 'Temps estimé : changement d\'outil', 10.0, 0, 600, ' s', 1),
        B('fao/outils_inconnus', 'Programme lu : proposer ses outils inconnus (les créer ou choisir des outils '
          'existants)', True,
          tip='À la lecture d’un programme (SimPL, ISO…), une fenêtre propose ses outils absents des bibliothèques'),
        Opt('fao/chemins_programmes', 'Programmes appelés : chemin machine = chemin du poste', 'text', '',
            tip='Appels externes d\'un programme (SimPL usermodule…) : le chemin vu de la machine remplacé par '
                'celui du poste pour suivre le programme appelé, par exemple « network:T:\\=\\\\serveur\\partage » ; '
                'plusieurs correspondances séparées par ; (sinon : chemin tel quel, puis dossier du programme)'),
    ]),
    ('BAT', [
        C('bat/page', 'Format', 'A4', [('A4', 'A4'), ('A3', 'A3'), ('A5', 'A5'), ('Letter', 'Letter')]),
        C('bat/orientation', 'Orientation', 'portrait', [('portrait', 'Portrait'), ('paysage', 'Paysage'),
                                                         ('auto', 'Selon le dessin')]),
        C('bat/scale_mode', 'Échelle', 'vues', [('vues', '1:1 cotée + agrandissement ou réduction'),
                                                 ('reelle', 'Taille réelle (réduite si besoin)'),
                                                 ('normalisee', 'Échelle normalisée'), ('ajuster', 'Ajustée à la page'),
                                                 ('imposee', 'Imposée (ci-dessous)')]),
        F('bat/scale', 'Échelle imposée (2 = 2:1, 0,5 = 1:2)', 1.0, 0.01, 100, '', 3),
        B('bat/title_block', 'Cartouche', True),
        B('bat/dims', 'Cotes d\'encombrement', True),
        B('bat/legend', 'Légende des outils', True),
        F('bat/enlarge_below', 'Agrandissement proposé sous', 30.0, 0, 1000, ' mm', 1,
          tip='Une pièce plus petite que cette taille reçoit aussi une vue agrandie'),
        B('bat/enlarge', 'Toujours ajouter une vue agrandie', False),
        F('bat/margin', 'Marge', 10.0, 0, 60, ' mm', 1),
        Opt('bat/author', 'Établi par', 'text', ''),
        Opt('bat/company', 'En-tête : entreprise', 'text', ''),
        Opt('bat/logo', 'En-tête : logo (image ou dessin)', 'file', '',
            tip='Imprimé en haut à gauche de chaque BAT (10 mm de haut) ; un dessin (SVG, PDF, DXF…) reste en tracés exacts',
            extra={'open': True, 'filter': 'Images et dessins (*.png *.jpg *.jpeg *.bmp *.gif *.tif *.tiff *.svg *.pdf '
                                            '*.ai *.eps *.dxf *.vnd *.gvt *.smb)'}),
        Opt('bat/logo2', 'En-tête : second logo, à droite (image ou dessin)', 'file', '',
            tip='Le logo du client, par exemple',
            extra={'open': True, 'filter': 'Images et dessins (*.png *.jpg *.jpeg *.bmp *.gif *.tif *.tiff *.svg *.pdf '
                                            '*.ai *.eps *.dxf *.vnd *.gvt *.smb)'}),
        Opt('bat/clients', 'Carnet de clients : dossier', 'folder', '',
            tip='Noms et logos des clients du BAT (les logos y sont copiés). Vide : dans les données de VectorDrive ; '
                'un dossier partagé sert à tous les postes'),
        B('bat/mono', 'Noir et blanc', False),
        C('bat/fill_mode', 'Coloriage', 'contour', [('contour', 'Couleur des contours (pleins et vides alternés)'),
                                                    ('noir', 'Logo en noir (contours fermés : pleins et vides alternés)'),
                                                    ('teinte', 'Teinte claire de la couleur de l\'outil')]),
        C('bat/title_color', 'Couleur du cartouche', '', [('', 'Noir'), ('logo', 'Prise sur le logo'), ('#1f4e9c', 'Bleu'),
                                                          ('#b22222', 'Rouge'), ('#2e7d32', 'Vert'),
                                                          ('#d46a00', 'Orange'), ('#6b6b6b', 'Gris')]),
        B('bat/theme_all', 'Thème : cette couleur aussi pour le cadre, l\'en-tête et les cotes', False),
        C('bat/decimals', 'Précision des cotes', '2', [('0', '0 décimale'), ('1', '1 décimale'), ('2', '2 décimales'),
                                                       ('3', '3 décimales'), ('4', '4 décimales')]),
        B('bat/keep_zeros', 'Garder les zéros de la fin (12,50)', False),
        B('bat/show_bruts', 'Bruts des ensembles, cotés à part', True),
    ]),
    ('Impression', [
        C('impression/quoi', 'Imprimer (Ctrl+P), la première fois', 'demander',
          [('demander', 'La sélection, sinon la plaque'), ('bat', 'La page BAT'), ('dessin', 'Tout le dessin')],
          tip='Ensuite, la fenêtre Imprimer reprend vos derniers choix'),
        C('impression/format', 'Format de la feuille', 'A4', [('A4', 'A4'), ('A3', 'A3'), ('A5', 'A5'),
                                                              ('Letter', 'Letter'), ('A6', 'A6'), ('A2', 'A2'),
                                                              ('A1', 'A1')]),
        C('impression/orientation', 'Orientation', 'portrait', [('portrait', 'Portrait'), ('paysage', 'Paysage'),
                                                                ('auto', 'Selon le dessin')]),
        C('impression/echelle', 'Échelle du dessin', '1', [('1', '1:1 (taille réelle)'), ('2', '2:1'), ('5', '5:1'),
                                                           ('0.5', '1:2'), ('0.2', '1:5'),
                                                           ('ajuster', 'Ajustée à la feuille')]),
        B('impression/reduire', 'Réduire le dessin s\'il dépasse la feuille', True),
        B('impression/mosaique', 'Plus grand que la feuille : à l\'échelle sur plusieurs feuilles (mosaïque)', False,
          tip='Au lieu de le réduire : feuilles repérées A1, B1… avec 6 mm de recouvrement pour les assembler'),
        C('impression/position', 'Position sur la feuille', 'centre',
          [('centre', 'Centré'), ('coin', 'En bas à gauche, à la marge')]),
        F('impression/marge', 'Marge', 10.0, 0, 60, ' mm', 1),
        B('impression/plaque', 'Imprimer la plaque (pointillés)', True),
        B('impression/selection', 'Seulement la sélection, s\'il y en a une', False),
        B('impression/apercu', 'Aperçu avant d\'imprimer', True,
          tip='La feuille telle qu\'elle sortira (format, orientation, échelle) ; le bouton de l\'aperçu imprime'),
    ]),
    ('Mises à jour', [
        Opt('maj/source', 'Source des mises à jour', 'folder', '', tip='Dossier partagé ou adresse https'),
        B('maj/auto', 'Rechercher les mises à jour au démarrage', False),
    ]),
    ('Plugins', [
        Opt('plugins/dossiers', 'Dossiers de plugins supplémentaires', 'folders', '', restart=True),
    ]),
    ('Performances', [
        I('perf/fils', 'Fils de calcul (0 = automatique : cœurs du poste moins un)', 0, 0, 128,
          tip='Retraits de régions (poches, gravure 2,5D…) calculés en même temps sur plusieurs cœurs ; '
              'moins de fils laisse plus de place aux autres logiciels'),
        I('perf/processus', 'Processus des longs travaux (0 = automatique, 8 au plus)', 0, 0, 64,
          tip='Traitement par lots, Décaler, vignettes lentes : chaque processus prend environ 150 Mo de mémoire'),
        B('perf/priorite_basse', 'Calculs longs en priorité basse (les autres logiciels restent fluides)', False,
          tip='Pendant un calcul avec barre de progression, VectorDrive cède la main aux autres programmes'),
        C('affichage/gpu', 'Carte graphique de la vue 3D', 'auto',
          [('auto', 'Choix de Windows'), ('economie', 'Économie d\'énergie (carte intégrée)'),
           ('performance', 'Hautes performances (carte dédiée)'),
           ('logiciel', 'Rendu logiciel (sans carte graphique)')], restart=True,
          tip='Postes à deux cartes (intégrée + dédiée) : la carte utilisée par la vue 3D, posée dans le réglage '
              'Graphismes de Windows pour VectorDrive'),
        I('perf/cache_vignettes', 'Mémoire des vignettes (bibliothèque, Ouvrir, récents)', 256, 16, 8192, ' Mo',
          tip='Vignettes gardées pour la séance ; au-delà, les moins récemment vues sont retracées au besoin'),
        I('perf/cache_simulations', 'Mémoire des simulations 3D', 512, 0, 16384, ' Mo',
          tip='Simulations gardées pour la séance (vue 3D rouverte : aussitôt) ; 0 : jamais gardées'),
        C('vue3d/anticrenelage', 'Vue 3D : anticrénelage', '4',
          [('0', 'Aucun (le plus rapide)'), ('2', '2 ×'), ('4', '4 ×'), ('8', '8 × (le plus lisse)')], restart=True,
          tip='Lissage des traits et des arêtes de la vue 3D ; moins sollicite moins la carte graphique '
              '(aucun en rendu logiciel)'),
    ]),
]
BY_KEY = {o.key: o for _t, opts in SPEC for o in opts}
#: onglets de la fenêtre, repris en boutons dans l'onglet Options du ruban : titre → (clé, icône)
PAGES = {'Général': ('general', 'options'), 'Apparence': ('apparence', 'themes'), 'Dessin': ('dessin', 'bezier'),
         'Affichage': ('affichage', 'view_2d'), 'Fichiers': ('fichiers', 'open'), 'FAO': ('fao', 'cam'),
         'BAT': ('bat', 'pdf'), 'Impression': ('impression', 'print'), 'Mises à jour': ('maj', 'update'), 'Plugins': ('plugins', 'ribbon'),
         'Performances': ('performances', 'view_3d')}
assert list(PAGES) == [t for t, _o in SPEC], 'un bouton par onglet des options'
#: réglages d'apparence : un changement réapplique le thème
APPEARANCE = [o.key for o in dict(SPEC)['Apparence']]


def _fold(text: str) -> str:
    """Texte sans accents ni casse, pour chercher un réglage."""
    import unicodedata
    return ''.join(c for c in unicodedata.normalize('NFD', str(text).lower()) if unicodedata.category(c) != 'Mn')


def default_of(o: Opt):
    """Valeur par défaut d'une option : celle de sa définition, ou celle qu'un plugin fournit
    (`api.set_defaults('options', {clé: valeur})`)."""
    from ..plugins import default
    return default('options', o.key, o.default)


def value(settings, key: str):
    """Valeur d'une option (type de sa définition)."""
    o = BY_KEY[key]
    v = settings.value(key, default_of(o))
    if o.kind == 'bool':
        return v in (True, 'true', 1, '1')
    if o.kind == 'float':
        try:
            return float(v)
        except (TypeError, ValueError):
            return float(o.default)
    if o.kind == 'int':
        try:
            return int(float(v))
        except (TypeError, ValueError):
            return int(o.default)
    return '' if v is None else str(v)


class OptionsDialog(QDialog):
    """F10 : options générales, par onglets (enregistrées dans le profil)."""

    def measure_machine(self):
        """Mesure rapide du poste (fils, processus) et conseil de réglage."""
        from . import resources
        from .progress import Cancelled, run
        try:
            r = run(self, tr('Mesure du poste'), resources.benchmark)
        except Cancelled:
            return None
        self.measure.setText(resources.benchmark_text(r))
        return r

    def clear_memories(self) -> None:
        from . import resources
        resources.clear_all()
        if getattr(self, 'usage', None) is not None:
            self.usage.setText(resources.usage_text())

    @staticmethod
    def _gpu_text() -> str:
        """Cartes du poste et celle qui rend la vue 3D pendant la séance."""
        import os
        from .. import gpu
        from ..core import workers
        cards = gpu.adapters()
        lines = [tr('Ce poste : {0} cœurs logiques — {1} fil(s) de calcul en service').format(
            os.cpu_count() or 1, workers.count())]
        if cards:
            lines.append(tr('Cartes graphiques du poste : {0}').format(', '.join(cards)))
        lines.append(tr('Vue 3D rendue par : {0}').format(gpu.RENDERER) if gpu.RENDERER else
                     tr('Vue 3D pas encore ouverte pendant cette séance'))
        return '\n'.join(lines)

    def __init__(self, settings, parent=None, page: str | None = None):
        super().__init__(parent)
        from .fit import no_hscroll
        no_hscroll(self)                                 # pas de défilement horizontal à l'ouverture
        page_title = page                               # onglet à montrer (titre de SPEC)
        self.setWindowTitle(tr('Options'))
        self.setSizeGripEnabled(True)
        avail = self.screen().availableGeometry() if self.screen() is not None else None
        self.resize(min(980, avail.width() - 80) if avail else 980, min(740, avail.height() - 80) if avail else 740)
        self.settings = settings
        self.widgets: dict[str, QWidget] = {}
        self._rows: list = []                            # (onglet, formulaire, champ, texte cherché)
        lay = QVBoxLayout(self)
        from PySide6.QtWidgets import QLineEdit
        self.search = QLineEdit()
        self.search.setPlaceholderText(tr('Chercher un réglage (ex. : fils, vignettes, VND, outil)…'))
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.filter_options)
        lay.addWidget(self.search)
        self.tabs = QTabWidget()
        for title, opts in SPEC:
            page = QWidget()
            form = QFormLayout(page)
            for o in opts:
                w = self._widget(o)
                self.widgets[o.key] = w
                label = tr(o.label) + (' *' if o.restart else '')
                if o.kind == 'bool':
                    w.setText(label)
                    form.addRow(w)
                else:
                    form.addRow(label, w)
                if o.tip:
                    w.setToolTip(tr(o.tip))
                self._rows.append((self.tabs.count(), form, w, _fold(' '.join(
                    (label, tr(o.tip) if o.tip else '', o.label, o.tip or '', o.key)))))
            if title == 'Plugins':
                form.addRow(QLabel(self._plugins_text()))
                from PySide6.QtWidgets import QPushButton
                add = QPushButton(tr('Ajouter un plugin…'))
                add.setObjectName('addPluginButton')
                add.setToolTip(tr('Choisir l’archive .zip d’un plugin : elle est décompressée dans le dossier des '
                                  'plugins de VectorDrive ; le plugin est chargé au prochain démarrage'))
                add.clicked.connect(lambda: self.add_plugin())
                folder = QPushButton(tr('Ouvrir le dossier des plugins'))
                folder.setObjectName('pluginFolderButton')
                folder.clicked.connect(self.open_plugins_folder)
                row = QHBoxLayout()
                row.addWidget(add)
                row.addWidget(folder)
                row.addStretch(1)
                form.addRow(row)
                self.plugin_status = QLabel()
                self.plugin_status.setObjectName('pluginStatus')
                self.plugin_status.setWordWrap(True)
                form.addRow(self.plugin_status)
            if title == 'Performances':
                form.addRow(QLabel(self._gpu_text()))
                from PySide6.QtWidgets import QPushButton
                from . import resources
                self.usage = QLabel(resources.usage_text())
                form.addRow(self.usage)
                b = QPushButton(tr('Vider les mémoires'))
                b.setToolTip(tr('Vignettes, simulations 3D, parcours et caractères gardés pour la séance : '
                                'oubliés, recalculés au besoin'))
                b.clicked.connect(self.clear_memories)
                form.addRow(b)
                m = QPushButton(tr('Mesurer le poste'))
                m.setToolTip(tr('Quelques secondes de calcul pour voir ce que les fils et les processus apportent '
                                'sur ce poste'))
                m.clicked.connect(self.measure_machine)
                form.addRow(m)
                self.measure = QLabel()
                self.measure.setWordWrap(True)
                form.addRow(self.measure)
            if title == 'Général' and hasattr(parent, 'simple_mode_dialog'):
                from PySide6.QtWidgets import QPushButton
                b = self.simple_mode_button = QPushButton(tr('Commandes du mode simple…'))
                b.setToolTip(tr('Choisir, onglet par onglet, les commandes du ruban que le mode simple montre'))
                b.clicked.connect(lambda _=False: parent.simple_mode_dialog())
                form.addRow(b)
            if title == 'Général' and hasattr(parent, 'agent_dialog'):
                from PySide6.QtWidgets import QPushButton
                b = self.agent_button = QPushButton(tr('Assistant (serveur MCP)…'))
                b.setToolTip(tr('Brancher un assistant (Claude Code…) sur le dessin ouvert : il le lit et peut y dessiner'))
                b.clicked.connect(lambda _=False: parent.agent_dialog())
                form.addRow(b)
            if title == 'Apparence' and hasattr(parent, 'theme_editor'):
                from PySide6.QtWidgets import QPushButton
                b = QPushButton(tr('Éditeur de thèmes…'))
                b.clicked.connect(self._theme_editor)
                form.addRow(b)
            sc = QScrollArea()
            sc.setWidgetResizable(True)
            sc.setWidget(page)
            self.tabs.addTab(sc, tr(title))
        lay.addWidget(self.tabs, 1)
        self.show_page(page_title)
        lay.addWidget(QLabel(tr('* au prochain démarrage')))
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
                              | QDialogButtonBox.StandardButton.RestoreDefaults)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        bb.button(QDialogButtonBox.StandardButton.RestoreDefaults).clicked.connect(self.restore_defaults)
        lay.addWidget(bb)

    def filter_options(self, text: str = '') -> int:
        """Seuls les réglages dont le libellé, l'info-bulle ou la clé contient
        le texte (sans accents ni casse) ; onglets sans réglage trouvé grisés,
        le premier qui en a au premier plan. Rend le nombre trouvé."""
        q = _fold(text.strip())
        found = 0
        per_tab: dict = {}
        for tab, form, w, hay in self._rows:
            on = not q or q in hay
            form.setRowVisible(w, on)
            per_tab[tab] = per_tab.get(tab, 0) + on
            found += on
        for i in range(self.tabs.count()):
            self.tabs.setTabEnabled(i, not q or per_tab.get(i, 0) > 0)
        if q and found and not per_tab.get(self.tabs.currentIndex(), 0):
            self.tabs.setCurrentIndex(next(i for i in range(self.tabs.count()) if per_tab.get(i, 0)))
        return found

    def show_page(self, title: str | None) -> bool:
        """Onglet `title` (titre de SPEC, en français) au premier plan."""
        titles = [t for t, _o in SPEC]
        if title not in titles:
            return False
        self.tabs.setCurrentIndex(titles.index(title))
        return True

    def _theme_editor(self) -> None:
        self.parent().theme_editor()
        for key, o in BY_KEY.items():                   # thèmes ajoutés ou supprimés
            if o.kind == 'theme':
                w = self.widgets[key]
                cur = w.currentData()
                w.clear()
                self._fill_themes(w, o, cur)

    def _fill_themes(self, w, o: Opt, v) -> None:
        from . import themes as T
        from .theme_editor import swatch_icon
        if o.extra.get('systeme'):
            w.addItem(tr('Suivre le système (clair ou sombre)'), 'systeme')
        only = o.extra.get('only')
        for t in T.all_themes().values():
            if only == 'clair' and t.dark or only == 'sombre' and not t.dark:
                continue
            w.addItem(swatch_icon(t), tr(t.name) + ('' if only else f' ({tr("sombre") if t.dark else tr("clair")})'),
                      t.key)
        i = w.findData(v)
        if i < 0:
            i = w.findData(o.default)
        w.setCurrentIndex(max(0, i))

    def add_plugin(self, path=None) -> list[str]:
        """« Ajouter un plugin… » : l'archive choisie (ou `path`) rangée dans le dossier des plugins ; le compte rendu
        sous les boutons. Rend les paquets ajoutés (vide : rien d'ajouté)."""
        from .. import plugins as PL
        if path is None:
            path, _ = QFileDialog.getOpenFileName(self, tr('Ajouter un plugin'), '', tr('Plugin VectorDrive (*.zip)'))
            if not path:
                return []
        try:
            names = PL.install(path)
        except PL.ArchiveError as ex:
            why = {'illisible': tr('archive illisible'),
                   'vide': tr('aucun plugin dans cette archive (il faut à sa racine un dossier dont le __init__.py '
                              'définit register)'),
                   'reserve': tr('nom réservé à VectorDrive'),
                   'chemin': tr('chemin qui sortirait du dossier des plugins'),
                   'paquet': tr('paquet qui n’est pas un plugin : sa place est dans le dossier _lib de '
                                'l’archive')}.get(ex.kind, ex.kind)
            self.plugin_status.setText(tr('Plugin non ajouté : {0} ({1}).').format(why, ex.detail))
            return []
        except OSError as ex:                           # un fichier du plugin en service, un dossier protégé…
            self.plugin_status.setText(tr('Plugin non ajouté : {0} ({1}).').format(tr('écriture impossible'), ex))
            return []
        except Exception as ex:                         # jamais d'exception jusqu'à la fenêtre
            self.plugin_status.setText(tr('Plugin non ajouté : {0} ({1}).').format(tr('erreur inattendue'), ex))
            return []
        text = tr('Plugin ajouté : {0}. Il sera chargé au prochain démarrage de VectorDrive.').format(', '.join(names))
        # seul le dossier plugins/ de la version portable passe avant celui de l'utilisateur (plugins.search_dirs)
        from ..portable import app_dir

        def loaded_from(folder):
            folder = folder.resolve()
            return [p for p in PL.REGISTRY.plugins if p.module in names and p.path
                    and folder in (pathlib.Path(p.path).resolve(), pathlib.Path(p.path).resolve().parent)]

        first = app_dir()
        ahead = loaded_from(first / 'plugins') if first is not None else []
        if ahead:
            text += ' ' + tr('Un plugin du même nom est déjà chargé depuis un autre dossier ({0}) : il reste '
                             'prioritaire.').format(ahead[0].path)
        if loaded_from(PL.user_dir()):                  # ses fichiers viennent d'être remplacés sous lui
            text += ' ' + tr('Redémarrez VectorDrive dès que possible : la version en cours lit des fichiers qui '
                             'viennent d’être remplacés.')
        kept = PL.archives_with(PL.user_dir(), names)
        if kept:
            text += ' ' + tr('L’archive {0} du dossier des plugins apporte aussi {1} avec un autre plugin : elle est '
                             'gardée, retirez-la si besoin.').format(kept[0].name, ', '.join(names))
        self.plugin_status.setText(text)
        return names

    def open_plugins_folder(self) -> None:
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        from .. import plugins as PL
        d = PL.user_dir()
        try:
            d.mkdir(parents=True, exist_ok=True)
        except OSError as ex:                           # support en lecture seule…
            self.plugin_status.setText(tr('Dossier des plugins impossible à créer : {0}').format(ex))
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(d)))

    def _plugins_text(self) -> str:
        from ..plugins import REGISTRY
        if not REGISTRY.plugins:
            return tr('Aucun plugin chargé.')
        return '\n'.join(f'{p.name} {p.version}' + (f' — {tr("erreur")} : {p.error}' if p.error else '')
                         for p in REGISTRY.plugins)

    def _widget(self, o: Opt) -> QWidget:
        v = value(self.settings, o.key)
        if o.kind == 'bool':
            w = QCheckBox()
            w.setChecked(bool(v))
        elif o.kind in ('float', 'int'):
            w = QDoubleSpinBox() if o.kind == 'float' else QSpinBox()
            w.setRange(o.lo, o.hi) if o.kind == 'float' else w.setRange(int(o.lo), int(o.hi))
            if o.kind == 'float':
                w.setDecimals(o.decimals)
            w.setSuffix(o.suffix)
            w.setValue(v)
        elif o.kind == 'choice':
            w = QComboBox()
            for val, lab in o.choices:
                w.addItem(tr(lab), val)
            w.setCurrentIndex(max(0, w.findData(v)))
        elif o.kind == 'post':
            w = QComboBox()
            self._fill_posts(w, v)
        elif o.kind == 'font':
            w = QFontComboBox()
            w.setCurrentFont(QFont(v or 'Arial'))
        elif o.kind == 'theme':
            w = QComboBox()
            w.setMaxVisibleItems(20)
            self._fill_themes(w, o, v)
        elif o.kind == 'color':
            from .theme_editor import ColorButton
            w = ColorButton(v)
        elif o.kind in ('folder', 'folders', 'file'):
            w = QWidget()
            row = QHBoxLayout(w)
            row.setContentsMargins(0, 0, 0, 0)
            edit = QLineEdit(v)
            b = QToolButton()
            b.setText('…')
            if o.kind == 'file':
                b.clicked.connect(lambda _=False, e=edit, opt=o: self._browse_file(e, opt))
            else:
                b.clicked.connect(lambda _=False, e=edit, many=o.kind == 'folders': self._browse(e, many))
            row.addWidget(edit, 1)
            row.addWidget(b)
            w.edit = edit
        else:
            w = QLineEdit(v)
        return w

    def _fill_posts(self, w, v) -> None:
        """Post-processeurs connus (plugins, fiches machine) ; choisi : celui
        du dessin ouvert, sinon le dernier choisi."""
        from ..cam import post
        cp = getattr(self.parent(), 'cam_panel', None)
        d = str(self.settings.value('fao/machines', '') or '') or post.default_machines_dir()
        try:
            found = post.posts(d)
        except Exception:                                # dossier illisible : posts des plugins seuls
            found = post.posts('')
        from ..cam import machines as MC
        for k, label, m in MC.choices(found):            # chaque machine une fois, sous son nom ; puis les autres
            if m is None and k.startswith('mah:'):
                label = f'{label} — {pathlib.Path(k[4:]).parent.name}'
            w.addItem(tr(label), k)
        if not w.count():
            w.addItem(tr('(aucun : un plugin en apporte)'), '')
        cur = cp.setup().post if cp is not None and hasattr(cp, 'setup') else v
        if cur and w.findData(cur) < 0:                  # double emploi d'une machine : c'est elle qui est choisie
            known = MC.of_post(cur)
            cur = (MC.resolve(known, found) if known is not None else '') or cur
        if cur and w.findData(cur) < 0 and str(cur).startswith('mah:'):
            w.addItem(tr('Fiche {0}').format(pathlib.Path(cur[4:]).name), cur)
        w.setCurrentIndex(max(0, w.findData(cur if w.findData(cur) >= 0 else v)))

    def _browse(self, edit, many: bool) -> None:
        cur = edit.text().split(';')[-1].strip() if many else edit.text()
        d = QFileDialog.getExistingDirectory(self, tr('Choisir un dossier'), cur)
        if d:
            edit.setText((edit.text().rstrip(';') + ';' + d).lstrip(';') if many and edit.text().strip() else d)

    def _browse_file(self, edit, o: Opt | None = None) -> None:
        """Fichier existant ou à créer (bibliothèque d'outils…) ; `o.extra` : 'filter' (filtre de la boîte)
        et 'open' (fichier existant à choisir : logo…)."""
        extra = (o.extra if o is not None else None) or {}
        if extra.get('open'):
            path, _ = QFileDialog.getOpenFileName(self, tr('Choisir un fichier'), edit.text(),
                                                  tr(extra.get('filter', 'Tous les fichiers (*)')))
        else:
            path, _ = QFileDialog.getSaveFileName(self, tr('Choisir un fichier'), edit.text() or 'tools.json',
                                                  extra.get('filter', 'JSON (*.json)'),
                                                  options=QFileDialog.Option.DontConfirmOverwrite)
        if path:
            edit.setText(path)

    def read(self, key: str):
        o, w = BY_KEY[key], self.widgets[key]
        if o.kind == 'bool':
            return w.isChecked()
        if o.kind in ('float', 'int'):
            return w.value()
        if o.kind in ('choice', 'theme', 'post'):
            return w.currentData()
        if o.kind == 'color':
            return w.value()
        if o.kind == 'font':
            return w.currentFont().family()
        if o.kind in ('folder', 'folders', 'file'):
            return w.edit.text().strip()
        return w.text().strip()

    def restore_defaults(self) -> None:
        for o in BY_KEY.values():
            w = self.widgets[o.key]
            o = Opt(**{**o.__dict__, 'default': default_of(o)})
            if o.kind == 'bool':
                w.setChecked(bool(o.default))
            elif o.kind in ('float', 'int'):
                w.setValue(o.default)
            elif o.kind in ('choice', 'theme'):
                w.setCurrentIndex(max(0, w.findData(o.default)))
            elif o.kind == 'post':                       # le post-processeur n'a pas de « défaut » : gardé
                pass
            elif o.kind == 'color':
                w.setValue(o.default)
            elif o.kind == 'font':
                w.setCurrentFont(QFont(o.default))
            elif o.kind in ('folder', 'folders', 'file'):
                w.edit.setText(o.default)
            else:
                w.setText(o.default)

    def accept(self) -> None:
        for key in self.widgets:
            self.settings.setValue(key, self.read(key))
        super().accept()
