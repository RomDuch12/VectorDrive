"""Historique des volumes : de quoi refaire un volume, commande par commande
(d'après la frise des opérations de SolidCraft).

Chaque commande de volumes note sur la forme qu'elle rend ce qu'elle était et ce
qu'elle a pris dans la sélection. Rejouer, c'est remettre ces entrées dans un
dessin provisoire, les choisir et relancer la commande avec ses réglages
(`MainWindow._hist_eval`) : le calcul reste celui de la commande, il n'y en a
pas un second à tenir à jour.

extra['histoire'] = {'steps': [étape…], 'result': empreinte}, à plat et dans
l'ordre où tout s'est fait, la dernière étape donnant le volume. À plat : la
longueur d'un historique ne pèse ni sur l'enregistrement ni sur la pile d'appels.

Étape : {'cmd', 'kw', 'params', 'inputs', 'index', 'title', 'shown', 'off', 'centers'}
Entrée : {'kind': 'solid', 'step': rang, 't', 'name', 'tool', 'color', 'id', 'extra'}
pour un volume qui a son historique, sans son maillage ; {'kind': 'item', 'item'}
pour un tracé, un marqueur ou un volume sans historique, tels quels.

Une référence (`ref`) est le rang d'une étape (-1 : la dernière) ou le couple
(rang de l'étape, rang de l'entrée).

`result` est l'empreinte du maillage de la forme : un volume changé hors de
l'historique ne lui correspond plus, et il compte alors pour un volume figé.
"""
from __future__ import annotations

import hashlib

from . import solids as SO

KEY = 'histoire'

#: Au-delà, ce qui est choisi entre dans la commande comme volume figé : un
#: recalcul doit rester praticable.
MAX_STEPS = 2000
#: Plus d'objets choisis que ça : la commande se fait sans historique.
MAX_INPUTS = 100

#: Les commandes qui se rejouent. Ni les inspections, qui ne changent rien, ni
#: l'import, dont le fichier peut avoir disparu : ce qui en sort est un volume figé.
RECORDED = ('solid_primitive', 'solid_move_z', 'solid_align3d', 'solid_rotate3d', 'solid_permute',
            'solid_scale3d', 'solid_mirror_z', 'solid_slice', 'solid_array_z', 'solid_separate',
            'solid_cells', 'solid_sweep', 'solid_loft', 'solid_polysolid', 'solid_shell', 'solid_round',
            'solid_offset', 'solid_smooth', 'solid_presspull', 'solid_coil', 'solid_thread', 'solid_hole',
            'solid_pipe', 'solid_rib', 'solid_boss', 'solid_lip', 'solid_snap_fit', 'solid_rest',
            'solid_wrap_emboss', 'solid_sheet', 'solid_fold', 'solid_tray', 'solid_frame', 'solid_extrude',
            'solid_revolve', 'solid_boolean', 'solid_edges', 'solid_draft', 'solid_move_faces', 'solid_delete_faces')


class HistoryError(ValueError):
    """Le recalcul n'aboutit pas ; le message est pour l'utilisateur."""


class HistoryCancelled(Exception):
    """La fenêtre des réglages a été fermée sans valider."""


def mesh_hash(item) -> str:
    return hashlib.sha1(item.extra[SO.KEY]['mesh'].encode('ascii')).hexdigest()


def history_of(item) -> dict | None:
    """L'historique d'un volume, s'il correspond encore à son maillage."""
    if not SO.is_solid(item):
        return None
    h = item.extra.get(KEY)
    if not isinstance(h, dict) or not h.get('steps') or h.get('result') != mesh_hash(item):
        return None
    return h


def has_history(item) -> bool:
    return history_of(item) is not None


def root_of(item) -> dict | None:
    """La dernière étape, celle qui donne le volume."""
    h = history_of(item)
    return h['steps'][-1] if h is not None else None


def placement(item) -> list:
    """Où la forme a été déplacée depuis son calcul (matrice 4x4 à plat)."""
    return list(item.extra[SO.KEY]['m'])


def _baked(item) -> dict:
    from ..io import native
    out = native._item_out(item)
    if isinstance(out.get('extra'), dict):
        out['extra'].pop(KEY, None)
    return {'kind': 'item', 'item': out}


def _shifted(steps: list, by: int) -> list:
    """Des étapes déjà faites, placées `by` rangs plus loin. Elles ne sont jamais
    modifiées sur place (une reprise travaille sur une copie) : elles restent partagées."""
    if not by:
        return steps
    return [dict(s, inputs=[dict(e, step=e['step'] + by) if e['kind'] == 'solid' else e for e in s['inputs']])
            for s in steps]


def gather(selection) -> tuple | None:
    """(étapes déjà faites, entrées) d'une commande sur cette sélection ;
    None : trop d'objets pour en garder l'histoire."""
    if len(selection) > MAX_INPUTS:
        return None
    steps, inputs = [], []
    for it in selection:
        h = history_of(it)
        if h is None or len(steps) + len(h['steps']) >= MAX_STEPS:
            inputs.append(_baked(it))
            continue
        steps = steps + _shifted(h['steps'], len(steps))
        sd = it.extra[SO.KEY]
        kept = {k: v for k, v in it.extra.items() if k not in (SO.KEY, KEY)}
        inputs.append({'kind': 'solid', 'step': len(steps) - 1, 't': placement(it), 'name': it.name,
                       'tool': it.tool, 'color': list(sd.get('color', SO.ALU)), 'id': it.id, 'extra': kept})
    return steps, inputs


def attach(outputs, cmd, kw, note, gathered, centers=None) -> int:
    """Note l'historique sur les volumes rendus par une commande ; en rend le nombre."""
    steps, inputs = gathered
    solids = [it for it in outputs if SO.is_solid(it)]
    for i, it in enumerate(solids):
        step = {'cmd': cmd, 'kw': dict(kw), 'params': note['values'] if note else None,
                'title': note['title'] if note else '', 'shown': note['shown'] if note else '',
                'inputs': inputs, 'index': i, 'off': False}
        if centers is not None:
            step['centers'] = [list(c) for c in centers]
        it.extra = dict(it.extra, **{KEY: {'steps': steps + [step], 'result': mesh_hash(it)}})
    return len(solids)


def at(hist: dict, ref) -> dict:
    """L'étape ou l'entrée désignée par `ref`."""
    if isinstance(ref, (tuple, list)):
        return hist['steps'][ref[0]]['inputs'][ref[1]]
    return hist['steps'][ref]


def is_step(entry: dict) -> bool:
    return 'cmd' in entry


def can_suspend(step: dict) -> bool:
    """Une étape se suspend si elle part d'un volume : sans elle, il reste celui-là."""
    return is_step(step) and any(e['kind'] == 'solid' or SO.KEY in (e['item'].get('extra') or {})
                                 for e in step['inputs'])


def sketch_of(entry: dict) -> dict | None:
    """L'esquisse d'une entrée (un tracé parti d'une esquisse contrainte)."""
    if entry.get('kind') != 'item':
        return None
    return (entry['item'].get('extra') or {}).get('sketch')


def last_uses(steps: list) -> list:
    """Pour chaque étape : les rangs des volumes dont on n'a plus besoin après elle."""
    last = {}
    for i, s in enumerate(steps):
        for e in s['inputs']:
            if e['kind'] == 'solid':
                last[e['step']] = i
    out = [[] for _ in steps]
    for rank, i in last.items():
        out[i].append(rank)
    return out


def _choice_label(options, value):
    for o in options or ():
        if isinstance(o, (tuple, list)) and len(o) == 2 and o[0] == value:
            return o[1]
    return value


def describe(values: dict, spec: list, choices: dict | None = None) -> str:
    """Le réglage principal et ceux qui ne sont pas à leur valeur par défaut, en clair."""
    choices = choices or {}
    parts = []
    for rank, (name, _kind, default, label) in enumerate(spec):
        v = values.get(name, default)
        if rank and v == default:
            continue
        if isinstance(v, bool):
            if not v:
                continue
            text = label.split(' (')[0]
        else:
            shown = _choice_label(choices.get(name), v)
            shown = f'{shown:g}' if isinstance(shown, float) else str(shown)
            text = f"{label.split(' (')[0]} : {shown}"
        parts.append(text)
    return ' ; '.join(parts[:6])
