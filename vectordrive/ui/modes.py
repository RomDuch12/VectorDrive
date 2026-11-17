"""Modes simple et expert : quels boutons du ruban le mode simple montre.

Le mode expert montre tout. Le mode simple ne garde que l'essentiel — ouvrir un dessin, le retoucher, l'écrire,
l'aligner, le graver : les commandes de `SIMPLE`, le choix de la machine, et celles qu'apportent les plugins.
Chacun ajuste : un clic droit sur un bouton du ruban le passe d'un mode à l'autre, et ce choix est gardé dans les
réglages (`modes/simple_plus` : montrés en plus ; `modes/simple_moins` : réservés au mode expert).

Le mode ne touche que les boutons du ruban : les raccourcis, les menus du dessin et la recherche de commande
donnent toujours tout.
"""
from __future__ import annotations

MODES = ('simple', 'expert')
KEY = 'vue/mode'
PLUS, MINUS = 'modes/simple_plus', 'modes/simple_moins'

#: les commandes du mode simple, par onglet du ruban
SIMPLE = frozenset('''
    new open save saveas import export proof print print_selection quit
    undo redo paste cut copy delete tool_select select_all order_front order_back group ungroup dims snap
    contour_color
    zoom_fit zoom_sel zoom_in zoom_out refresh fill grid rulers layer_tabs themes full_screen ribbon_collapse
    tool_rect tool_ellipse tool_line tool_polyline tool_arc tool_text char_map font_recognize assistant_ia tool_dim tool_measure tool_node join
    tool_trim tool_extend symbols library_big save_symbol barcode trace hatch
    bool_union bool_intersect bool_difference offset mirror_h mirror_v rot90 rot-90 rot_free move_by
    align_left align_hcenter align_right align_top align_vcenter align_bottom center_plate
    close_contour reverse duplicate dup_linear dup_circular check
    text_back text_align_left text_align_center text_align_right case_upper case_lower find_replace text_styles
    cam_panel tool_library cam_compute cam_post cam_paths_2d cam_simulate cam_clear cam_view_nc
    place_model3d cam3d_auto cam3d_ops_list cam_paths_3d cam_sim_3d
    options options_general options_apparence options_fao plate tools_table shortcuts
    guide about update news command_search
    ui_mode view_toggle
'''.split())


def current(settings) -> str:
    """Le mode retenu : 'simple' ou 'expert' (d'office : expert — rien ne disparaît sans l'avoir demandé)."""
    v = str(settings.value(KEY, 'expert') or 'expert') if settings is not None else 'expert'
    return v if v in MODES else 'expert'


def _keys(settings, name: str) -> set:
    v = settings.value(name, []) if settings is not None else []
    if isinstance(v, str):
        v = [x for x in v.split(';') if x]
    return {str(x) for x in (v or [])}


def default_simple(key: str, plugin_keys=()) -> bool:
    """La commande est-elle du mode simple d'office ? Celles de `SIMPLE`, le choix de la machine, celles des plugins."""
    return key in SIMPLE or key.startswith('machine_') or key in plugin_keys


def in_simple(key: str, settings=None, plugin_keys=()) -> bool:
    """Le mode simple montre-t-il le bouton de cette commande ? D'office, puis les choix de l'utilisateur."""
    if key in _keys(settings, MINUS):
        return False
    return default_simple(key, plugin_keys) or key in _keys(settings, PLUS)


def move(settings, key: str, to_simple: bool, plugin_keys=()) -> None:
    """Passe le bouton d'une commande d'un mode à l'autre : montré en mode simple, ou réservé au mode expert. Seul
    l'écart à la répartition d'office est gardé."""
    plus, minus = _keys(settings, PLUS), _keys(settings, MINUS)
    plus.discard(key)
    minus.discard(key)
    if to_simple and not default_simple(key, plugin_keys):
        plus.add(key)
    elif not to_simple and default_simple(key, plugin_keys):
        minus.add(key)
    settings.setValue(PLUS, sorted(plus))
    settings.setValue(MINUS, sorted(minus))
