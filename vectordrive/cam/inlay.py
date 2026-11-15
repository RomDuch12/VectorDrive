"""Usinage d'une marqueterie (core.marquetry) : opérations du prédéfini."""
from __future__ import annotations

from ..core.marquetry import PRESETS, MarquetrySpec
from .model import Operation


def operations(spec: MarquetrySpec, female: list, male: list, setup, thickness: float = 0.0) -> list:
    """Opérations du prédéfini (aucune sans prédéfini) : femelle en poche
    (borgne) ou détourée par l'intérieur (débouchante), mâle détourée par
    l'extérieur ; outil : le premier du réglage de la nature voulue."""
    label, female_kind, tool_kind = PRESETS.get(spec.preset, PRESETS['aucun'])
    if not female_kind:
        return []
    tool = next((t for t in setup.tools if t.kind == tool_kind), None)
    tid = tool.id if tool else ''
    through = thickness if thickness > 0 else 1.0
    ops = []
    if female:
        if female_kind == 'poche':
            ops.append(Operation(name=f'Marqueterie femelle — {label}', kind='poche', tool_id=tid,
                                 items=[s.id for s in female], depth=0.5))
        else:
            ops.append(Operation(name=f'Marqueterie femelle — {label}', kind='contour', side='interieur',
                                 tool_id=tid, items=[s.id for s in female], depth=through))
    if male:
        ops.append(Operation(name=f'Marqueterie mâle — {label}', kind='contour', side='exterieur', tool_id=tid,
                             items=[s.id for s in male], depth=through))
    return ops
