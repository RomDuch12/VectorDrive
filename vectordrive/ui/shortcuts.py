"""Raccourcis clavier : jeu VectorDrive, jeu TypeEdit, réglages personnels.

TypeEdit range ses raccourcis dans `CONFIG\\TeTurboKey.ini` (section
`[TAB_ACCELERATOR]`, triplets `CMD_nnn` = commande, `MOD_nnn` = drapeaux
FCONTROL / FSHIFT / FALT, `KEY_nnn` = touche : lettre, chiffre ou nom
VK_…). `read_turbokey` lit ce fichier ; `TE_ACTIONS` dit à quelle action de
VectorDrive répond chaque commande TypeEdit.

Jeux de raccourcis : « vectordrive » (ceux du programme), « typeedit » (le
TeTurboKey.ini du TypeEdit **installé sur le poste**, lu à l'exécution, ou
un fichier importé) et ceux qu'apportent les plugins (`plugins.Api.
add_shortcut_scheme`). Aucune donnée de TypeEdit n'est copiée.

Jeu de type TypeEdit : chaque action qui a un équivalent TypeEdit prend les
touches de TypeEdit (à la place des siennes) ; les autres gardent les
leurs, sauf une touche déjà prise par TypeEdit. Les réglages personnels
(fenêtre Raccourcis clavier) s'appliquent par-dessus.
"""
from __future__ import annotations

import functools
import glob
import json
import os
import pathlib
import re

from ..i18n import tr

#: commande TypeEdit → action VectorDrive
TE_ACTIONS = {
    'ID_MANIPULER_PLANREPERE': 'guides_dialog',
    'ID_COMPO_FLIPPLAN': 'solid_permute', 'ID_ROTATION_OBJET3D': 'solid_rotate3d', 'ID_SHAPE_SCRIPT': 'shape_script', 'ID_WARPING_GRID': 'relief_warp', 'ID_GALBE_MAPPING': 'relief_photo', 'ID_WRAPPING_TARTTART': 'relief_wrap',
    'ID_CMD_TP_TYPEART': 'cam_new_relief', 'ID_CMD_TP_TYPEARTSEQUENCE': 'cam_new_gamme_relief',
    'ID_TART_METNONDEF': 'relief_keep', 'ID_TART_EXTRACTTART': 'relief_extract', 'ID_TART_DEPOSE': 'relief_place',
    'ID_TROITOIR': 'relief_border', 'ID_TART_RECALAGE_POINT': 'relief_z_align', 'ID_TART_ISO_LETTER': 'relief_prism',
    'ID_TART_FACETSONEDGES': 'relief_facets', 'ID_SETLIGHTPOS': 'view_light', 'ID_INVERT_GROUP': 'group_reverse',
    'ID_MAGICCOPY': 'copy_into_shape',
    # ce que TypeEdit nomme autrement
    'ID_COMPO_CORORTHO': 'spell_check', 'ID_TART_PLANREF': 'relief_level',
    'IDB_RAPIDO_HAUTEUR_CARACTERE': 'text_letters', 'IDB_RAPIDO_LARGEUR_CARACTERE': 'text_letters',
    'IDB_RAPIDO_ROTATION_CARACTERE': 'text_letters', 'ID_RAPIDO_Kernel': 'text_kern_cycle',
    'ID_RAPIDO_CHAR_PBEXPONENT_DLL': 'text_letters', 'ID_RAPIDO_CHAR_PBINDICE_DLL': 'text_letters',
    # fichier, édition
    'ID_FILE_NEW': 'new', 'ID_FILE_OPEN': 'open', 'ID_FILE_VIEWER': 'open', 'ID_FILE_SAVE': 'save',
    'ID_FILE_SAVE_AS': 'saveas', 'ID_FICHIER_IMPORTER': 'import', 'ID_FICHIER_EXPORTER': 'export',
    'ID_FILE_PRINT': 'print', 'ID_EDIT_UNDO': 'undo', 'ID_EDIT_REDO': 'redo', 'ID_EDIT_CUT': 'cut',
    'ID_EDIT_COPY': 'copy', 'ID_EDIT_PASTE': 'paste', 'ID_EDITION_SUPPRIMER': 'delete',
    'ID_EDIT_SELECTALL': 'select_all', 'ID_EDIT_INVERT_SELECTION': 'invert', 'ID_DRAW_FILTER': 'select_filter', 'ID_MANIPULER_PREVUE': 'drag_preview', 'ID_CMD_LED': 'leds',
    'ID_WATERJET_OFFSETCIRCLES': 'cut_cercles', 'ID_WATERJET_OCTOGONES': 'cut_octogones',
    'ID_WATERJET_PORTIONS': 'cut_portions', 'ID_WATERJET_RECTANGLES': 'cut_rectangles',
    'ID_WATERJET_TRIANGLES': 'cut_triangles', 'ID_WATERJET_NESTEDCIRCLES': 'cut_rondelle', 'ID_PALETTE_TEXTURE': 'texture', 'ID_COMPO_MOVETEXT': 'text_move_on_path',
    'ID_SYMMETRICAL_CURVES_REVOLUTION': 'revolution', 'ID_RAPIDO_LISTCAR_DLL': 'char_map', 'ID_RAPIDO_CHAR_PBITALIC': 'text_italic',
    'ID_RAPIDO_CHAR_PBUNDERLINE_DLL': 'text_underline', 'ID_RAPIDO_LINE_BTNESPFIXE_DLL': 'line_fixed',
    'ID_RAPIDO_LINE_BTNESPPROP_DLL': 'line_prop', 'ID_RAPIDO_LINE_BTNESPPROPTYPO_DLL': 'line_typo', 'ID_RAPIDO_MIRROR': 'mirror_h', 'ID_COMPO_TEXTENARCSMULTIPLES': 'text_arcs',
    'ID_COMPO_SELECTIONMODES_OPERATEURS': 'selection_modes',
    'ID_EDIT_OPTIONS': 'options',
    'ID_HELP': 'guide', 'ID_SEARCH_CMD': 'command_search', 'ID_BACKTO': 'tool_select',
    # affichage, accrochage
    'ID_GRID': 'grid', 'ID_SNAP_MOINS': 'snap_prev', 'ID_SNAP_PLUS': 'snap_next', 'ID_MANIPULER_ACCROCHAGE': 'snap',
    'ID_VIEW_WIRESENS': 'direction', 'ID_VIEW_DIRECTIONARROW': 'direction', 'ID_VIEW_WIRECOLOR': 'tool_colors',
    'ID_VIEW_FILLCOLOR': 'fill', 'ID_AFFICHAGE_REDESSIN': 'refresh', 'ID_AFFICHAGE_REDESSINRAPIDE': 'refresh',
    'ID_AFFICHAGE_ZOOMMAXIMUM': 'zoom_fit', 'ID_AFFICHAGE_ZOOMSELECTION': 'zoom_sel',
    # objets
    'ID_ZONE_GROUP': 'group', 'ID_ZONE_UNGROUP': 'ungroup', 'ID_MANIPULER_ZONE_COMBINER': 'combine',
    'ID_MANIPULER_ZONE_ECLATER': 'explode_step', 'ID_TOUT_DEVANT': 'order_front', 'ID_TOUT_DERRIERE': 'order_back',
    'ID_EN_AVANT': 'order_forward', 'ID_EN_ARRIERE': 'order_backward',
    'ID_MANIPULER_ZONE_CONVENCOURBE': 'to_curves', 'ID_MANIPULER_ZONE_ROTATION': 'rot_free',
    # commandes du ruban de TypeEdit que VectorDrive a sous un autre nom
    'ID_FILE_PRINT_PREVIEW': 'proof', 'ID_APP_ABOUT': 'about', 'ID_DEFAULT_HELP': 'guide',
    'ID_FREEZE_UNFREEZE_SELECTION': 'freeze', 'ID_EDIT_CLEARUNDOSTACK': 'clear_history',
    'ID_AFFICHAGE_ZOOMPRECEDENT': 'zoom_prev', 'ID_AFFICHAGE_ZOOMSUPPORT': 'zoom_plate',
    'ID_AFFICHAGE_VUE2DXY': 'view_2d', 'ID_AFFICHAGE_VUE3DGRAVEUR': 'view_engraver',
    'ID_AFFICHAGE_VUE2DYZ': 'view_yz', 'ID_AFFICHAGE_VUE2DZX': 'view_zx', 'ID_AFFICHAGE_DYNAMIC': 'view_3d',
    'ID_TART_VIEWER': 'view_3d', 'ID_SHOWPALVIEWERTART': 'cam_sim_3d', 'ID_CHANGE_TYPEART_INEDITION': 'view_3d',
    'ID_TART_TESTUSI': 'cam_simulate',
    'ID_MANIPULER_ZONE_ALIGNER': 'align_center',
    'ID_MANIPULER_ZONE_CENTRER': 'center_origin', 'ID_CONTOUR_MOVE': 'tool_contour_move',
    'ID_COMPO_ALIGNER_ALIGNEROTVERTI': 'tool_axis_v', 'ID_COMPO_ALIGNER_ALIGNEROTHORIZ': 'tool_axis_h',
    'ID_MODE_POINT_REFINE': 'node_refine', 'ID_CONTOUR_RABOT': 'tool_portion_segment', 'ID_CONTOUR_SETANGLE': 'tool_portion_angle',
    'ID_MACHINING_TOOLSDATABASE': 'tool_library', 'ID_FILE_VECTORIZEPARAMETERS': 'trace', 'ID_COLOR_USI': 'tools_table',
    'ID_AFFICHAGE_VUE3DISOMETRIQUE': 'view_iso', 'ID_MANIPULER_SUPPORT': 'plate', 'ID_MANIPULER_GRILLE': 'grid',
    'ID_COMPO_COLOR': 'tools_table', 'ID_TYPE3_TOOLSDATABASE': 'tool_library',
    'ID_LASERING_TOOLSDATABASE': 'tool_library', 'ID_LISTPATH': 'cam_panel', 'ID_CMD_SIMUL': 'cam_simulate',
    'ID_CMD_SIMUL_VOL_NEW': 'cam_sim_3d', 'ID_CMD_SIMUL_VOL_VULKAN': 'cam_sim_3d',
    'ID_CMD_SIMUL_VOL_OLD': 'cam_simulate', 'ID_CMD_RECOMPUTE_FAST': 'cam_compute',
    'ID_CREATEPATH': 'cam_new_gravure', 'ID_CREATEPATH_LASER': 'cam_new_laser', 'ID_LASER_MACHINING': 'cam_post',
    'ID_PALETTE_MESUREAIRECONTOUR': 'area', 'ID_PALETTE_MESURE': 'tool_measure',
    'ID_COMPO_MULTICOPYINTEL': 'copy_nest', 'ID_TROU_PLAQUE': 'holes', 'ID_ANALYSE_CLEAN_DOC': 'check',
    'ID_SIMPLIFICATION': 'approximate', 'ID_COMPO_POWERAPX': 'approximate', 'ID_EXPLODE': 'explode',
    'ID_REMOVE_CONTOUR': 'tool_contour_erase', 'ID_CONTOUR_SUP': 'tool_contour_erase', 'ID_RETOUCHE_SCISEAU': 'node_break',
    'ID_RETOUCHE_REMOVEPOINT': 'node_delete', 'ID_RETOUCHE_TANGENTPOINT': 'node_smooth',
    'ID_CONTOUR_ARC': 'tool_portion_arc', 'ID_TRANSFO_SEG_ARC': 'to_arcs', 'ID_CONTOUR_Linear_BEZIER': 'tool_portion_curve',
    'ID_PALETTE_ETOILE': 'tool_star', 'ID_PALETTE_ELLIPSE': 'tool_ellipse', 'ID_CMD_CREATE_SPIRAL': 'tool_spiral',
    'ID_PALETTE_ARC3PT': 'tool_arc', 'ID_PALETTE_CERCLE3PT': 'tool_circle3', 'ID_PALETTE_FLECHE': 'arrow',
    'ID_PALETTE_STRAIGHT_LINE': 'tool_line', 'ID_PALETTE_DIGITDROITE': 'tool_dline',
    'ID_PALETTE_POLYCURVE': 'tool_polycurve', 'ID_COMPO_TEXTRECTANGLE': 'text_box', 'ID_COMPO_TEXTSURCOURBE': 'text_path',
    'ID_TEXTSURCOURBEAPRES': 'text_path', 'ID_TEXTONARC': 'text_arc', 'ID_TXTCOLONNE_VN': 'text_table',
    'ID_COMPO_TEXTEEDITFONT': 'font_editor', 'ID_FINDREPLACETEXT': 'find_replace',
    'ID_RAPIDO_CHAR_PBMAJ_DLL': 'case_upper', 'ID_RAPIDO_CHAR_PBMIN_DLL': 'case_lower',
    'ID_RAPIDO_CHAR_PBMAJMIN_DLL': 'case_initial', 'ID_RAPIDO_CHAR_PBDBLSPACE_DLL': 'text_letters', 'ID_RAPIDO_CHAR_PBARABE_DLL': 'text_rtl', 'ID_RAPIDO_CHAR_PBSMAJ_DLL': 'case_small',
    'ID_RAPIDO_LINE_BTNJUSTIF_DLL': 'text_align_justify', 'ID_RAPIDO_LINE_BTNONLB_DLL': 'text_on_baseline',
    'ID_RAPIDO_LINE_BTNUNDERLB_DLL': 'text_under_baseline', 'ID_RAPIDO_LINE_BTNCOMPBYLINE_DLL': 'text_compress_line',
    'ID_RAPIDO_LINE_BTNCOMPBYPARA_DLL': 'text_compress_para', 'ID_RAPIDO_LINE_BTNCOMPBYGLOBAL_DLL': 'text_compress_global', 'ID_CROP': 'clip', 'ID_PALETTE_CLIPPING': 'clip',
    'ID_PUNCH': 'punch', 'ID_COMPO_ENVELOPPE': 'envelope', 'ID_MANIPULER_ZONE_ALIGNERGAUCHE': 'align_left',
    'ID_MANIPULER_ZONE_ALIGNERDROITE': 'align_right', 'ID_MANIPULER_ZONE_ALIGNERHAUT': 'align_top',
    'ID_MANIPULER_ZONE_ALIGNERBAS': 'align_bottom', 'ID_MANIPULER_PLAQUE_ALIGNERGAUCHE': 'align_plate_left',
    'ID_MANIPULER_PLAQUE_ALIGNERDROITE': 'align_plate_right', 'ID_MANIPULER_PLAQUE_ALIGNERHAUT': 'align_plate_top',
    'ID_MANIPULER_PLAQUE_ALIGNERBAS': 'align_plate_bottom', 'ID_COMPO_ALIGNER_MEMETAILLEVERTI': 'same_h',
    'ID_COMPO_ALIGNER_MEMETAILLEHORIZ': 'same_w', 'ID_COMPO_ALIGNER_MEMETAILLE': 'same_both',
    'ID_COMPO_MIROIRAXE': 'mirror_axis', 'ID_REMOVE_CURVE_SELF_INTERSECTION': 'remove_loops',
    'ID_COMPO_EXTEND': 'tool_extend', 'ID_COMPO_REMOVE_ALIGNEDPOINTS': 'remove_aligned',
    'ID_COMPO_CONVENCERCLE': 'convert_curves', 'ID_COMPO_COPIE': 'tool_dup_free', 'ID_COMPO_RESEAUCIRC': 'dup_circular',
    'ID_COMPO_DUPSURCOURBE': 'duplicate', 'ID_COMPO_DUPHOMOTSURCOURBE': 'duplicate_scaled', 'ID_COMPO_SHOWPALDUPLICATION': 'duplicate', 'ID_ZONE_ENCOMPASS': 'bbox_frame',
    'ID_BRAILLE_VN': 'braille', 'ID_TAMPON': 'stamp', 'ID_CODE_BARRE_1D': 'barcode', 'ID_CODE_BARRE_2D': 'barcode',
    'ID_COMPO_PHOTOART': 'halftone', 'ID_COMPO_VECTORIZE': 'trace', 'ID_PALETTE_CENTERLINE': 'trace',
    'ID_COMPO_VERNIERGEN': 'graduation', 'ID_COMPOBOOLCOUTEAU': 'stroke', 'ID_RETOUCHE_ADDPOINT': 'tool_node', 'ID_MANIPULER_POSITIONNEMENTCURSEUR': 'point_xy', 'ID_CMD_BATCHPROCESS': 'batch', 'ID_RAPIDO_LINE_BTNJUSTIFL_DLL': 'text_align_left',
    'ID_RAPIDO_LINE_BTNJUSTIFC_DLL': 'text_align_center', 'ID_RAPIDO_LINE_BTNJUSTIFR_DLL': 'text_align_right', 'ID_FILE_OPENMODEL': 'new_from_template',
    'ID_FILE_SAVEMODEL': 'save_as_template', 'ID_IMPORTEXPORT_CONFIG': 'settings_export', 'ID_APP_EXIT': 'quit',
    'ID_FILE_PRINT_SETUP': 'print', 'ID_COMPO_INVSENS': 'reverse', 'ID_MANIPULER_ZONE_HOMOTETIE': 'dims',
    'ID_MANIPULER_ZONE_ETIRER': 'dims', 'ID_OBJECT_PROPERTIES': 'dims', 'ID_RETOUCHE_PROJECTIONVERT': 'node_project_v',
    'ID_RETOUCHE_PROJECTIONHORIZ': 'node_project_h', 'ID_RETOUCHE_PROJECTIONPERP': 'node_project_perp', 'ID_COMPO_SPLITTER': 'node_break',
    'ID_COMPO_SPLITTER_POINT': 'node_break', 'ID_CUT_AND_DESTROY': 'tool_cut_portion', 'ID_COMPO_EXTEND_ARC': 'tool_extend_arc',
    'ID_NESTING_LIGHT': 'nesting', 'ID_MARQUETTERIE': 'marquetry', 'ID_SYMMETRICAL_CURVES_CYCLIC': 'tool_sym_both',
    'ID_SYMMETRICAL_CURVES_POINT': 'tool_sym_origin', 'ID_POST_IT': 'note', 'ID_PALETTE_ARCCORDE': 'tool_arc', 'ID_COMPO_TEXTVERTICAL': 'text_vertical',
    'ID_COMPO_DTE_TANGENTE': 'tangents', 'ID_BAR_VARIABLE': 'variables', 'ID_BAR_VARALPHA': 'insert_variable', 'ID_COMPO_CERCLE_TANGENT': 'tangent_arc', 'ID_EDIT_UNDO_LIST': 'undo_list', 'ID_EDIT_REDO_LIST': 'redo_list',
    'ID_MANIPULER_ZONE_ALIGNERGAUCHE_EXTERIEUR': 'align_left_out',
    'ID_MANIPULER_ZONE_ALIGNERDROITE_EXTERIEUR': 'align_right_out',
    'ID_MANIPULER_ZONE_ALIGNERHAUT_EXTERIEUR': 'align_top_out',
    'ID_MANIPULER_ZONE_ALIGNERBAS_EXTERIEUR': 'align_bottom_out', 'ID_AFFICHAGE_ZOOM': 'tool_zoom', 'ID_MANIPULER_ZONE_DEPLACER': 'move_by',
    # TypeEdit nomme le miroir d'après son axe : « vertical » = gauche-droite
    'ID_COMPO_MIROIRVERT': 'mirror_h', 'ID_COMPO_MIROIRHORZ': 'mirror_v',
    'ID_SYMMETRICAL_CURVES_AXISX': 'tool_sym_ox', 'ID_SYMMETRICAL_CURVES_AXISY': 'tool_sym_oy',
    'ID_MANIPULER_ZONE_ALIGNERCENTREHORIZ': 'align_hcenter', 'ID_MANIPULER_ZONE_ALIGNERCENTREVERTI': 'align_vcenter',
    'ID_MANIPULER_ZONE_CENTRERHORIZ': 'center_plate_h',
    'ID_MANIPULER_ZONE_CENTRERVERTI': 'center_plate_v', 'ID_COMPO_ALIGNER_ESPACEVERTI': 'distribute_v',
    'ID_COMPO_ALIGNER_ESPACEHORIZ': 'distribute_h', 'ID_COMPO_RESEAU': 'dup_linear', 'ID_COMPO_NESTING': 'nesting',
    # opérations sur les courbes
    'ID_COMPO_BOOLUNION': 'bool_union', 'ID_COMPO_BOOLSUBSTRACT': 'bool_difference',
    'ID_COMPO_BOOLINTER': 'bool_intersect', 'ID_COMPO_BOOLXOR': 'bool_xor', 'ID_COMPO_BOOLOFFSET': 'offset',
    'ID_COMPO_OFFSET_A_SUIVRE': 'offset', 'ID_COMPO_CHISEL_EFFECT': 'shadow',
    'ID_COMPO_MANIPZONE': 'tool_select',
    'ID_COMPO_CURVE_SELF_INTERSECTION': 'normalize', 'ID_REMOVE_DUPLICATE_CONTOUR_POINT': 'remove_dup_points',
    'ID_RETOUCHE_AUTOCONNECT': 'chain', 'ID_COMPO_TRIM': 'tool_trim',
    # mode Point
    'ID_COMPO_SHOWPALPOINT': 'tool_node', 'ID_RETOUCHE_STARTPOINT': 'node_start',
    'ID_RETOUCHE_ALIGNEVERTICAL': 'node_align_v', 'ID_RETOUCHE_ALIGNEHORIZONTAL': 'node_align_h',
    'ID_RETOUCHE_CONGE': 'fillet', 'ID_RETOUCHE_CHANFRAIN': 'chamfer', 'ID_RETOUCHE_JOINPOINT': 'join',
    'ID_RETOUCHE_UNJOINPOINT': 'node_break',
    # création
    'ID_PALETTE_RECTANGLE': 'tool_rect', 'ID_PALETTE_RECTARR': 'tool_rect', 'ID_PALETTE_POLYGONE': 'tool_polygon',
    'ID_PALETTE_DIGIT': 'tool_bezier', 'ID_PALETTE_DIGITDROITESINGLE': 'tool_line',
    'ID_PALETTE_CERCLE': 'tool_ellipse', 'ID_PALETTE_ARC': 'tool_arc', 'ID_PALETTE_MARKER': 'tool_marker',
    'ID_PALETTE_VECTO': 'trace', 'ID_PALETTE_LOGO': 'library_big', 'ID_COMPO_TEXTLIBRE': 'tool_text',
    'ID_OPEN_PAL_TEXT': 'tool_text', 'ID_CODE_BARRE': 'barcode',
    # mesure
    'ID_PALETTE_MESUREDISTANCE2PT': 'tool_measure', 'ID_PALETTE_MESUREDISTANCERECT': 'tool_measure_rect',
    'ID_PALETTE_MESUREANGLE': 'tool_measure_angle', 'ID_PALETTE_MESURE_BOXING': 'bbox_frame',
    'ID_PALETTE_MESURE_COTATION': 'tool_dim', 'ID_PALETTE_MESURELONGCONTOUR': 'perimeter',
    # FAO
    'ID_TYPE3_MACHINING': 'cam_post', 'ID_MACHINING_MACHINING': 'cam_post', 'ID_CMD_MODIFYCOMPUTE': 'cam_compute',
    'ID_SIMUL_OUTIL': 'cam_simulate', 'ID_CMD_TP_PLOTTING': 'cam_new_trace',
    'ID_CMD_TP_CUTTING_3D': 'cam_new_decoupe3d', 'ID_CMD_TP_ENGRAVING_3D': 'cam_new_gravure3d',
    'ID_CMD_TP_SEQUENCE_MULTITOOL': 'cam_new_gamme', 'ID_FAO_FABRICERESTEMATIERE': 'cam_new_reste',
    'ID_CMD_TP_CUTTING_LASER': 'cam_new_laser_decoupe', 'ID_CMD_TP_LASER': 'cam_new_laser',
    'ID_CMD_TP_LASER_ENGRAVE': 'cam_new_laser_gravure',
    'ID_CMDFAO_CYL_MAPPING': 'cam_wrap_cylinder', 'ID_CMDFAO_CON_MAPPING': 'cam_wrap_cone', 'ID_CMDFAO_PARALLEL_MAPPING': 'cam_project',
    'ID_CYLPROJ': 'wrap_drawing_cyl', 'ID_CONPROJ': 'wrap_drawing_cone',
    'ID_FILE_MRU_FILE1': 'recent_1', 'ID_FILE_MRU_FILE2': 'recent_2', 'ID_FILE_MRU_FILE3': 'recent_3',
    'ID_FILE_MRU_FILE4': 'recent_4', 'ID_MACHINING_SETUPMACHINES': 'cam_machines', 'ID_CMD_MERGETP': 'cam_merge', 'ID_GALBE_NEWGALBE': 'galbe', 'ID_GALBE_LISSAGE': 'galbe_smooth',
    'ID_TART_GALBEONMARKER': 'typeart_dome', 'ID_TART_EXTRUSION': 'typeart_extrude',
    'ID_TART_REVOLUTION': 'typeart_revolution', 'ID_TART_MAKEPLAN': 'typeart_plane',
    'ID_TART_RECALAGE': 'relief_z_align', 'ID_DYNAMICTART': 'relief_dynamic', 'ID_TART_ADJUSTTOVOL': 'relief_volume',
    'ID_TART_SLICE': 'relief_slice', 'ID_TART_RAISEDETAIL': 'relief_raise', 'ID_TART_BASRELIEF': 'relief_basrelief',
    'ID_TART_FILLHOLES': 'relief_fill', 'ID_TYPEART_POINCONMATRICE': 'relief_punch', 'ID_GALBE_MALEFEMELLE': 'relief_punch',
    # barre de texte de TypeEdit (rapido) : commandes déjà présentes
    'IDB_ITALIQUE': 'text_italic', 'ID_GII_TXTBARCHAR_PBITALIC': 'text_italic', 'IDB_SOULIGNE': 'text_underline',
    'IDB_MAJUSCULES': 'case_upper', 'IDB_MINUSCULES': 'case_lower', 'IDB_MAJUSCULES_MINUSCULES': 'case_initial',
    'IDB_PETITES_MAJUSCULES': 'case_small', 'IDB_POS_SOUS_LIGNE_BASE': 'text_under_baseline',
    'IDB_POS_SUR_LIGNE_BASE': 'text_on_baseline', 'IDB_INSERER_VARIABLE': 'insert_variable',
    'IDB_REPRODUIRE_STYLE': 'text_copy_format', 'IDB_JUSTIFICATION_CENTRE': 'text_align_center',
    'IDB_JUSTIFICATION_DROITE': 'text_align_right', 'IDB_JUSTIFICATION_GAUCHE': 'text_align_left',
    'IDB_JUSTIFIER': 'text_align_justify', 'IDB_INTERLIGNAGE_CONSTANT': 'line_fixed',
    'IDB_INTERLIGNAGE_PROPORTIONNEL': 'line_prop', 'IDB_INTERLIGNAGE_TYPOGRAPHIQUE': 'line_typo',
    'IDB_COMPRESSION_LIGNE': 'text_compress_line', 'IDB_COMPRESSION_ALL': 'text_compress_para',
    'IDB_LISTE_CARACTERES': 'char_map', 'IDB_MIROIR': 'mirror_h',
    'ID_TART_SETFORUSI': 'relief_tool', 'ID_SCULPT': 'tool_sculpt', 'ID_TART_WEAVE': 'relief_weave', 'ID_TART_OPENCHOICETEXTURE': 'relief_tile', 'ID_CMD_MAKESEAMLESS': 'relief_seamless', 'ID_TART_AUTOTEXTURE': 'relief_fractal', 'ID_TART_LINEARMULTICOPY': 'relief_copy_linear',
    'ID_TART_CIRCULARMULTICOPY': 'relief_copy_circular', 'ID_TART_PERLAGE': 'relief_copy_curve',
    'ID_TART_SWEEPING': 'typeart_sweep', 'ID_TART_NEWSWEEPING': 'typeart_sweep', 'ID_PALETTE_SWEEPING': 'typeart_sweep',
    'ID_TART_BASIC_SWEEPING': 'typeart_sweep_simple', 'ID_TART_TUBE_SWEEPING': 'typeart_sweep_tube',
    'ID_TART_ADVANCED_SWEEPING': 'typeart_sweep_two', 'ID_MAPPING_SURF': 'relief_model3d',
    'ID_PALETTE_MESUREVOLUME': 'measure_volume', 'ID_BarEnroule': 'wrap_drawing_cyl',
    'ID_ADD_SPECIALTOOL': 'special_tool', 'ID_CMDFAO_LOCAL_MAPPING': 'cam_local_projection',
    'ID_MANIPULER_SOURIS': 'mouse_settings', 'ID_OPEN_COMBI': 'relief_merge',
    'ID_CMD_CMDFAO_CAMEDIT': 'cam_to_drawing', 'ID_BITMAPEDITOR': 'image_edit',
    'ID_COMBI1': 'typeart_mode_remplacer', 'ID_COMBI2': 'typeart_mode_ajouter', 'ID_COMBI3': 'typeart_mode_soustraire',
    'ID_COMBI4': 'typeart_mode_maximum', 'ID_COMBI5': 'typeart_mode_minimum', 'ID_COMBI6': 'typeart_mode_moyenne',
    'ID_COMBI7': 'typeart_mode_limit', 'ID_COMPO_TEXTURING': 'texture_create',
    'ID_COMPO_SHOWPALSHAPE': 'palette_shapes', 'ID_COMPO_SHOWPALSHAPE_MANIP': 'palette_shapes',
    'ID_COMPO_SHOWPALSHAPE_MANIP_TA': 'palette_shapes', 'ID_COMPO_SHOWPALSPECIALEFFECTS': 'palette_effects',
    'ID_COMPO_SHOWPALALIGN': 'palette_align', 'ID_COMPO_SHOWPALTRANSFORMATION': 'palette_transform',
    'ID_COMPO_SHOWPALTRANSFORMATION_TA': 'palette_transform', 'ID_COMPO_SHOWPALFXTART': 'palette_typeart',
    'ID_COMPO_SHOWPALUSINAGETART': 'palette_typeart',
    'ID_RAPIDO_TEXT_REPRODMISEENFORME_DLL': 'text_copy_format', 'ID_OPENPAL_METIER': 'palette_trades',
    # Surfaces de TypeArt : leurs équivalents en relief
    'ID_COMPO_SPHERE': 'relief_sphere', 'ID_COMPO_CYLINDRE': 'relief_cylinder', 'ID_CMD_CONE': 'relief_cone',
    'ID_CMD_TORE': 'relief_torus', 'ID_COMPO_CREER_ELLIPSOIDPATCH_SURFACE': 'relief_ellipsoid',
    'ID_COMPO_CREER_BOX_BREP': 'relief_box', 'ID_COMPO_SURFREVOL': 'typeart_revolution',
    'ID_COMPO_CREER_BILINEAR_SURFACE': 'relief_bilinear', 'ID_COMPO_CREER_SWEPT_SURFACE': 'typeart_sweep',
    'ID_COMPO_CREER_SKINNED_SURFACE_ONE_RAIL': 'typeart_sweep',
    'ID_COMPO_CREER_SKINNED_SURFACE_TWO_RAIL': 'typeart_sweep_two',
    'ID_COMPO_PARALLELPROJECTION': 'cam_project', 'ID_COMPO_LOCALPROJECTION': 'cam_local_projection',
    'ID_MANIPULER_ZONE_ALIGNER_POINT': 'tool_align_points', 'ID_GALBE_RENDU': 'view_3d',
}

#: au clavier seulement, une commande TypeEdit qui mène ailleurs que son bouton : Maj+C
#: (Cotation) part sur « Coter » — réglages de la cote choisie, cotes automatiques des objets
#: choisis, sinon l'outil Cote
TE_KEY_ACTIONS = {'ID_PALETTE_MESURE_COTATION': 'smart_dims'}

#: jeux du cœur ; les plugins en ajoutent (voir `schemes`)
SCHEMES = {'typeedit': 'TypeEdit (installé sur ce poste)', 'vectordrive': 'VectorDrive'}


def schemes() -> dict[str, str]:
    """Jeux disponibles : clé → libellé (ceux des plugins compris)."""
    from ..plugins import REGISTRY
    return {**{k: v[0] for k, v in REGISTRY.shortcut_schemes.items()}, **SCHEMES}


def default_scheme() -> str:
    """Jeu par défaut : celui d'un plugin, sinon TypeEdit s'il est
    installé sur le poste, sinon VectorDrive."""
    from ..plugins import REGISTRY
    if REGISTRY.default_scheme in REGISTRY.shortcut_schemes:
        return REGISTRY.default_scheme
    return 'typeedit' if candidate_files() else 'vectordrive'


def installed_entries() -> list[tuple[str, str]]:
    """Accélérateurs du TypeEdit le plus récent installé sur le poste."""
    for f in candidate_files():
        try:
            e = _read_cached(f, os.path.getmtime(f))
        except OSError:
            continue
        if e:
            return list(e)
    return []


@functools.lru_cache(maxsize=8)
def _read_cached(path: str, _mtime: float) -> tuple:
    return tuple(read_turbokey(path))


def scheme_entries(scheme: str, te_entries: list | None = None) -> list | None:
    """Accélérateurs TypeEdit d'un jeu (None : jeu VectorDrive)."""
    from ..plugins import REGISTRY
    if scheme in REGISTRY.shortcut_schemes:
        return REGISTRY.shortcut_schemes[scheme][1]
    if scheme == 'typeedit':
        return te_entries if te_entries is not None else installed_entries()
    return None

_VK = {'DELETE': 'Del', 'INSERT': 'Ins', 'BACK': 'Backspace', 'PRIOR': 'PgUp', 'NEXT': 'PgDown',
       'TAB': 'Tab', 'RETURN': 'Return', 'ESCAPE': 'Esc', 'SPACE': 'Space', 'HOME': 'Home', 'END': 'End',
       'LEFT': 'Left', 'RIGHT': 'Right', 'UP': 'Up', 'DOWN': 'Down', 'ADD': '+', 'SUBTRACT': '-',
       'MULTIPLY': '*', 'DIVIDE': '/'}
_MODS = (('FCONTROL', 'Ctrl'), ('FALT', 'Alt'), ('FSHIFT', 'Shift'))


def key_text(mods: str, key: str) -> str | None:
    """Drapeaux et touche d'un accélérateur TypeEdit → texte Qt (« Ctrl+Shift+O »)."""
    key = key.strip().strip("'\"")
    if not key:
        return None
    if key.upper().startswith('VK_'):
        name = key[3:].upper()
        if re.fullmatch(r'F\d{1,2}', name):
            k = name
        elif re.fullmatch(r'NUMPAD\d', name):
            k = name[-1]
        else:
            k = _VK.get(name)
            if k is None:
                return None
    elif len(key) == 1 and key.isalnum():
        k = key.upper()
    else:
        return None
    flags = set(mods.upper().split())
    return '+'.join([q for f, q in _MODS if f in flags] + [k])


def parse_turbokey(text: str) -> list[tuple[str, str]]:
    """(commande, touches) de la section [TAB_ACCELERATOR] d'un TeTurboKey.ini."""
    rows: dict[str, dict] = {}
    for line in text.splitlines():
        m = re.match(r'\s*(CMD|MOD|KEY)_(\d+)\s*=\s*(.*?)\s*$', line)
        if m:
            rows.setdefault(m.group(2), {})[m.group(1)] = m.group(3)
    out = []
    for n in sorted(rows, key=int):
        r = rows[n]
        seq = key_text(r.get('MOD', ''), r.get('KEY', ''))
        if r.get('CMD') and seq:
            out.append((r['CMD'].strip(), seq))
    return out


def read_text(path) -> str:
    data = pathlib.Path(path).read_bytes()
    if data[:2] in (b'\xff\xfe', b'\xfe\xff'):
        return data.decode('utf-16')
    try:
        return data.decode('utf-8')
    except UnicodeDecodeError:
        return data.decode('cp1252')


def read_turbokey(path) -> list[tuple[str, str]]:
    return parse_turbokey(read_text(path))


def merge(primary: list, secondary: list) -> list:
    """`primary` complété par les commandes de `secondary` qu'il n'a pas,
    quand leur touche est libre."""
    cmds = {c for c, _s in primary}
    keys = {_norm(s) for _c, s in primary}
    out = list(primary)
    for c, s in secondary:
        if c not in cmds and _norm(s) not in keys:
            out.append((c, s))
            keys.add(_norm(s))
    return out


def candidate_files() -> list[str]:
    """TeTurboKey.ini des TypeEdit installés sur ce poste, le plus récent d'abord."""
    pats = [os.path.join(os.environ.get('PROGRAMDATA', 'C:/ProgramData'), 'Gravotech', 'TypeEdit_*', 'CONFIG',
                         'TeTurboKey.ini'),
            'C:/TypeEdit_*/CONFIG/TeTurboKey.ini', 'C:/TypeEdit_*/Config/TeTurboKey.ini']
    found = {os.path.normcase(os.path.abspath(f)): f for p in pats for f in glob.glob(p)}
    return sorted(found.values(), key=lambda f: -os.path.getmtime(f))


def palette_files() -> list[str]:
    """Palettes utilisateur de TypeEdit (T3PALUSER3D.INI), la plus récente d'abord."""
    local = os.environ.get('LOCALAPPDATA', '')
    pats = [os.path.join(local, 'Gravotech', 'TypeEdit_*', 'CONFIG_USER', 'T3PALUSER3D.INI'),
            'C:/TypeEdit_*/CONFIG/T3PALUSER3D.INI', 'C:/TypeEdit_*/Config/T3PALUSER3D.INI']
    found = {os.path.normcase(os.path.abspath(f)): f for p in pats for f in glob.glob(p)}
    return sorted(found.values(), key=lambda f: -os.path.getmtime(f))


def parse_palette(text: str) -> list[str]:
    """Commandes de la palette utilisateur (sections TypeEdit_User / User,
    puis LaserType_User), dans l'ordre."""
    out, section = [], ''
    order = {'typeedit_user': 0, 'user': 0, 'lasertype_user': 1}
    rows: dict[int, list] = {0: [], 1: []}
    for line in text.splitlines():
        m = re.match(r'\s*\[(.+?)\]', line)
        if m:
            section = m.group(1).strip().lower()
            continue
        m = re.match(r'\s*NameCmd_(\d+)\s*=\s*(\S+)', line)
        if m and section in order:
            rows[order[section]].append(m.group(2))
    for k in (0, 1):
        out += [c for c in rows[k] if c not in out]
    return out


def user_palette(path: str | None = None) -> list[str]:
    """Actions VectorDrive de la palette TypeEdit_User (vide si TypeEdit
    n'est pas sur ce poste)."""
    files = [path] if path else palette_files()
    for f in files:
        try:
            cmds = parse_palette(read_text(f))
        except OSError:
            continue
        acts = [TE_ACTIONS[c] for c in cmds if c in TE_ACTIONS]
        if acts:
            return list(dict.fromkeys(acts))
    return []


def _norm(seq: str) -> str:
    from PySide6.QtGui import QKeySequence
    return QKeySequence(seq).toString(QKeySequence.SequenceFormat.PortableText)


def te_mapping(entries: list) -> dict[str, list[str]]:
    """Action VectorDrive → touches, d'après des accélérateurs TypeEdit."""
    out: dict[str, list[str]] = {}
    for cmd, seq in entries:
        act = TE_KEY_ACTIONS.get(cmd) or TE_ACTIONS.get(cmd)
        if act:
            lst = out.setdefault(act, [])
            if _norm(seq) not in [_norm(s) for s in lst]:
                lst.append(seq)
    return out


def unmapped(entries: list) -> list[tuple[str, str]]:
    return [(c, s) for c, s in entries if c not in TE_ACTIONS and c not in TE_KEY_ACTIONS]


def effective(defaults: dict[str, list[str]], scheme: str, te_entries: list | None = None,
              custom: dict | None = None) -> dict[str, list[str]]:
    """Touches de chaque action : jeu choisi, puis réglages personnels.
    Une touche n'appartient jamais qu'à une action."""
    base = {k: list(v) for k, v in defaults.items()}
    entries = scheme_entries(scheme, te_entries)
    if entries:
        te = {k: v for k, v in te_mapping(entries).items() if k in base}
        taken = {_norm(s) for v in te.values() for s in v}
        for k in base:
            base[k] = list(te[k]) if k in te else [s for s in base[k] if _norm(s) not in taken]
    for k, v in (custom or {}).items():
        if k not in base:
            continue
        mine = {_norm(s) for s in v}
        for other in base:
            if other != k:
                base[other] = [s for s in base[other] if _norm(s) not in mine]
        base[k] = list(v)
    return base


def conflicts(mapping: dict[str, list[str]]) -> dict[str, list[str]]:
    """Touche → actions qui la partagent (plus d'une)."""
    by: dict[str, list[str]] = {}
    for k, v in mapping.items():
        for s in v:
            by.setdefault(_norm(s), []).append(k)
    return {s: ks for s, ks in by.items() if len(ks) > 1}


# --- réglages ------------------------------------------------------------------------------

def load(settings) -> tuple[str, list | None, dict]:
    scheme = str(settings.value('raccourcis/jeu', '') or default_scheme())
    te = custom = None
    try:
        te = json.loads(settings.value('raccourcis/typeedit', '') or 'null')
    except (TypeError, ValueError):
        te = None
    try:
        custom = json.loads(settings.value('raccourcis/perso', '') or '{}')
    except (TypeError, ValueError):
        custom = {}
    te = [tuple(x) for x in te] if isinstance(te, list) else None
    return (scheme if scheme in schemes() else default_scheme()), te, (custom if isinstance(custom, dict) else {})


def save(settings, scheme: str, te_entries: list | None, custom: dict) -> None:
    settings.setValue('raccourcis/jeu', scheme)
    settings.setValue('raccourcis/typeedit', json.dumps(te_entries) if te_entries is not None else '')
    settings.setValue('raccourcis/perso', json.dumps(custom))


#: touches du haut d'un clavier français : le caractère de base (sans Maj) de chaque chiffre
AZERTY_DIGITS = {'1': '&', '2': 'É', '3': '"', '4': "'", '5': '(', '6': '-', '7': 'È', '8': '_', '9': 'Ç', '0': 'À'}


def azerty_aliases(mapping: dict[str, list[str]]) -> dict[str, list[str]]:
    """{action : touches en plus} : pour chaque « Ctrl+chiffre » (ou Alt, sans Maj, hors pavé numérique), la touche de
    base du même chiffre sur un clavier français — sans Maj, Qt n'y voit que ce caractère (« Ctrl+_ » pour
    « Ctrl+8 »). Jamais une touche qu'une action a déjà."""
    taken = {_norm(s) for v in mapping.values() for s in v}
    out: dict[str, list[str]] = {}
    for k, seqs in mapping.items():
        for s in seqs:
            parts = str(s).split('+')
            if len(parts) < 2 or parts[-1] not in AZERTY_DIGITS or any(p in ('Shift', 'Num') for p in parts[:-1]) \
                    or ',' in s:
                continue
            alias = '+'.join(parts[:-1] + [AZERTY_DIGITS[parts[-1]]])
            if _norm(alias) not in taken:
                taken.add(_norm(alias))
                out.setdefault(k, []).append(alias)
    return out


def apply(actions: dict, mapping: dict[str, list[str]]) -> None:
    """Pose les touches sur les QAction (et dans leurs bulles d'aide) ; « Ctrl+chiffre » y répond aussi sans Maj sur
    un clavier français (`azerty_aliases`)."""
    from PySide6.QtGui import QKeySequence
    more = azerty_aliases(mapping)
    for k, a in actions.items():
        seqs = list(mapping.get(k, [])) + more.get(k, [])
        a.setShortcuts([QKeySequence(s) for s in seqs])
        tip = a.property('vd_tip') or a.toolTip().split('  (')[0] or a.text()
        a.setProperty('vd_tip', tip)
        a.setToolTip(tip + (f'  ({QKeySequence(seqs[0]).toString(QKeySequence.SequenceFormat.NativeText)})'
                            if seqs else ''))


# --- fenêtre ----------------------------------------------------------------------------------

def dialog_class():
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QBrush, QColor, QKeySequence
    from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QFileDialog, QHBoxLayout, QHeaderView,
                                   QKeySequenceEdit, QLabel, QLineEdit, QMessageBox, QPushButton, QTableWidget,
                                   QTableWidgetItem, QVBoxLayout)

    class ShortcutsDialog(QDialog):
        """Jeu de raccourcis, import d'un TeTurboKey.ini, réglage action par action."""

        def __init__(self, parent, actions: dict, defaults: dict, scheme: str, te_entries, custom: dict):
            super().__init__(parent)
            from .fit import no_hscroll
            no_hscroll(self)                                 # pas de défilement horizontal à l'ouverture
            self.setWindowTitle(tr('Raccourcis clavier'))
            self.resize(720, 640)
            self.actions, self.defaults = actions, defaults
            self.scheme, self.te_entries, self.custom = scheme, te_entries, dict(custom)
            lay = QVBoxLayout(self)
            row = QHBoxLayout()
            row.addWidget(QLabel(tr('Jeu de raccourcis')))
            self.combo = QComboBox()
            for k, lab in schemes().items():
                self.combo.addItem(tr(lab), k)
            self.combo.setCurrentIndex(max(0, self.combo.findData(scheme)))
            self.combo.currentIndexChanged.connect(self._scheme_changed)
            row.addWidget(self.combo, 1)
            b = QPushButton(tr('Importer de TypeEdit…'))
            b.setToolTip(tr('Lire les raccourcis d\'un TeTurboKey.ini (dossier CONFIG de TypeEdit)'))
            b.clicked.connect(lambda: self.import_file())
            row.addWidget(b)
            lay.addLayout(row)
            self.source = QLabel()
            self.source.setWordWrap(True)
            lay.addWidget(self.source)
            self.filter = QLineEdit()
            self.filter.setPlaceholderText(tr('Filtrer (nom ou touche)'))
            self.filter.textChanged.connect(self._filter)
            lay.addWidget(self.filter)
            self.table = QTableWidget(0, 3)
            self.table.setHorizontalHeaderLabels([tr('Commande'), tr('Raccourci'), tr('Autres touches')])
            self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
            self.table.verticalHeader().hide()
            self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
            self.table.cellDoubleClicked.connect(lambda r, _c: self.edit_row(r))
            lay.addWidget(self.table, 1)
            row = QHBoxLayout()
            self.edit = QKeySequenceEdit()
            self.edit.setMaximumSequenceLength(1)
            row.addWidget(QLabel(tr('Touche')))
            row.addWidget(self.edit, 1)
            for text, slot in ((tr('Affecter'), self.assign), (tr('Effacer'), self.clear_row),
                               (tr('Rétablir le jeu'), self.reset)):
                b = QPushButton(text)
                b.clicked.connect(lambda _=False, s=slot: s())
                row.addWidget(b)
            lay.addLayout(row)
            self.info = QLabel()
            self.info.setWordWrap(True)
            lay.addWidget(self.info)
            bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
            bb.accepted.connect(self.accept)
            bb.rejected.connect(self.reject)
            lay.addWidget(bb)
            names = {k: a.text().replace('&', '') for k, a in actions.items()}
            seen: dict[str, int] = {}
            for v in names.values():
                seen[v] = seen.get(v, 0) + 1
            for k, a in actions.items():                 # même nom pour deux commandes : on précise
                tip = (a.statusTip() or '').strip()
                if seen[names[k]] > 1 and tip and tip != names[k]:
                    names[k] = f'{names[k]} — {tip}'
            self.names = names
            self._keys = sorted(actions, key=lambda k: names[k].lower())
            self.refresh()

        def mapping(self) -> dict:
            return effective(self.defaults, self.scheme, self.te_entries, self.custom)

        def refresh(self) -> None:
            m = self.mapping()
            clash = {k for ks in conflicts(m).values() for k in ks}
            self.table.setRowCount(len(self._keys))
            for r, k in enumerate(self._keys):
                seqs = [QKeySequence(s).toString(QKeySequence.SequenceFormat.NativeText) for s in m.get(k, [])]
                cells = (self.names[k], seqs[0] if seqs else '', ', '.join(seqs[1:]))
                for c, v in enumerate(cells):
                    it = QTableWidgetItem(v)
                    it.setData(Qt.ItemDataRole.UserRole, k)
                    if k in self.custom:
                        f = it.font()
                        f.setBold(True)
                        it.setFont(f)
                    if k in clash:
                        it.setForeground(QBrush(QColor('#c92a2a')))
                    self.table.setItem(r, c, it)
            from ..plugins import REGISTRY
            if self.scheme in REGISTRY.shortcut_schemes:
                src = tr('Jeu apporté par un plugin : {0} ({1} touches)').format(
                    tr(REGISTRY.shortcut_schemes[self.scheme][0]), len(REGISTRY.shortcut_schemes[self.scheme][1]))
            elif self.scheme == 'typeedit':
                if self.te_entries is not None:
                    src = tr('Raccourcis lus dans un TeTurboKey.ini ({0} touches)').format(len(self.te_entries))
                elif candidate_files():
                    src = tr('Raccourcis du TypeEdit installé : {0}').format(candidate_files()[0])
                else:
                    src = tr('TypeEdit n\'est pas installé sur ce poste : importer un TeTurboKey.ini')
            else:
                src = tr('Raccourcis d\'origine de VectorDrive')
            self.source.setText(src + (tr(' ; en gras : vos réglages') if self.custom else ''))
            self._filter(self.filter.text())

        def _filter(self, text: str) -> None:
            t = text.strip().lower()
            for r in range(self.table.rowCount()):
                vis = not t or any(t in (self.table.item(r, c).text().lower()) for c in range(3))
                self.table.setRowHidden(r, not vis)

        def _scheme_changed(self) -> None:
            self.scheme = self.combo.currentData()
            self.refresh()

        def _row_key(self):
            r = self.table.currentRow()
            return self.table.item(r, 0).data(Qt.ItemDataRole.UserRole) if r >= 0 else None

        def edit_row(self, r: int) -> None:
            self.table.selectRow(r)
            self.edit.setFocus()

        def assign(self) -> None:
            k = self._row_key()
            seq = self.edit.keySequence().toString(QKeySequence.SequenceFormat.PortableText)
            if not k or not seq:
                return
            m = self.mapping()
            owners = [o for o, v in m.items() if o != k and _norm(seq) in {_norm(s) for s in v}]
            self.custom[k] = [seq] + [s for s in m.get(k, []) if _norm(s) != _norm(seq)]
            self.info.setText(tr('{0} retiré de : {1}').format(seq, ', '.join(self.names[o] for o in owners))
                              if owners else '')
            self.refresh()

        def clear_row(self) -> None:
            k = self._row_key()
            if k:
                self.custom[k] = []
                self.refresh()

        def reset(self) -> None:
            self.custom = {}
            self.info.setText('')
            self.refresh()

        def import_file(self, path: str | None = None) -> int:
            if path is None:
                start = (candidate_files() or [''])[0]
                path, _ = QFileDialog.getOpenFileName(self, tr('Raccourcis TypeEdit'), start,
                                                      'TeTurboKey.ini (*TurboKey*.ini);;INI (*.ini)')
                if not path:
                    return 0
            try:
                entries = read_turbokey(path)
            except OSError as ex:
                QMessageBox.warning(self, tr('Raccourcis clavier'), str(ex))
                return 0
            if not entries:
                QMessageBox.warning(self, tr('Raccourcis clavier'), tr('Aucun raccourci dans ce fichier'))
                return 0
            self.te_entries = entries
            self.combo.setCurrentIndex(self.combo.findData('typeedit'))
            self.scheme = 'typeedit'
            miss = unmapped(entries)
            self.info.setText(tr('{0} raccourcis lus, {1} sans équivalent dans VectorDrive : {2}').format(
                len(entries), len(miss), ', '.join(f'{c} ({s})' for c, s in miss[:12]) + ('…' if len(miss) > 12 else '')))
            self.refresh()
            return len(entries)

    return ShortcutsDialog
