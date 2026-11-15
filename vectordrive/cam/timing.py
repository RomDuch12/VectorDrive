"""Temps d'usinage estimé d'après les mouvements réels des parcours :
avance de coupe ou de plongée de l'opération (sinon de l'outil), rapides à
la vitesse de la machine, accélération en trapèze (pas d'arrêt entre deux
segments presque alignés : arcs aplatis, courbes), changements d'outil.

Une estimation — la machine a ses propres réglages d'anticipation — mais
fondée sur les distances et les avances effectives : utile au devis.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from .model import arc_length, arc_points, move_feed


@dataclass
class TimingSpec:
    rapid: float = 15000.0          # vitesse des rapides (mm/min)
    accel: float = 1000.0           # accélération (mm/s²)
    tool_change: float = 10.0       # changement d'outil (s)
    corner: float = 15.0            # écart de direction sans arrêt (°)


def run_time(length: float, speed: float, accel: float) -> float:
    """Temps (s) d'un trajet de `length` mm à `speed` mm/s, parti et arrivé
    à l'arrêt, accélération `accel` mm/s² (trapèze, ou triangle si court)."""
    if length <= 0 or speed <= 0:
        return 0.0
    if accel <= 0:
        return length / speed
    if length >= speed * speed / accel:
        return length / speed + speed / accel
    return 2.0 * math.sqrt(length / accel)


def _speeds(m, prev, op, tool, spec: TimingSpec) -> float:
    """Vitesse (mm/min) du mouvement m."""
    if m.kind == 'rapid':
        return spec.rapid
    plunge = m.kind == 'plunge' or (m.z < prev[2] - 1e-9 and math.hypot(m.x - prev[0], m.y - prev[1]) < 1e-6)
    feed = move_feed(m, op, tool) or 600.0           # cadre actif ; passe de finition : l'avance de finition
    if plunge:
        return (op.plunge if op is not None and op.plunge else 0.0) or \
            (tool.plunge if tool is not None and tool.plunge else 0.0) or feed
    return feed


def path_seconds(tp, setup, spec: TimingSpec | None = None) -> float:
    """Temps d'un parcours (s)."""
    spec = spec or TimingSpec()
    op = next((o for o in setup.operations if o.id == tp.op_id), None)
    tool = setup.tool(tp.tool_id)
    total = 0.0
    run_len, run_speed, run_dir = 0.0, 0.0, None
    cos_lim = math.cos(math.radians(spec.corner))
    prev = None
    feeds = getattr(tp, 'feeds', None)                 # programme lu : avances programmées (F)
    feeds = feeds if feeds and len(feeds) == len(tp.moves) else None
    for k, m in enumerate(tp.moves):
        here = (m.x, m.y, m.z)
        if prev is None:
            prev = here
            continue
        if feeds is not None and m.kind != 'rapid' and feeds[k] > 0:
            speed = feeds[k] / 60.0
        else:
            speed = _speeds(m, prev, op, tool, spec) / 60.0
        pts = [prev] + (arc_points(prev, m, 0.05) if getattr(m, 'is_arc', False) else [here])
        for a, b in zip(pts, pts[1:]):
            d = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
            L = math.sqrt(d[0] ** 2 + d[1] ** 2 + d[2] ** 2)
            if L < 1e-9:
                continue
            u = (d[0] / L, d[1] / L, d[2] / L)
            smooth = run_dir is not None and abs(speed - run_speed) < 1e-9 and \
                u[0] * run_dir[0] + u[1] * run_dir[1] + u[2] * run_dir[2] >= cos_lim
            if smooth:
                run_len += L
            else:
                total += run_time(run_len, run_speed, spec.accel)
                run_len, run_speed = L, speed
            run_dir = u
        prev = here
    return total + run_time(run_len, run_speed, spec.accel)


def cumulative(toolpaths, setup, spec: TimingSpec | None = None) -> list[float]:
    """Temps écoulé (s) à la fin de chaque mouvement, parcours à la suite
    (longueur ÷ vitesse, sans les accélérations : pour la lecture pas à pas)."""
    spec = spec or TimingSpec()
    out, t = [], 0.0
    for tp in toolpaths:
        op = next((o for o in setup.operations if o.id == tp.op_id), None)
        tool = setup.tool(tp.tool_id)
        feeds = getattr(tp, 'feeds', None)
        feeds = feeds if feeds and len(feeds) == len(tp.moves) else None
        prev = None
        for k, m in enumerate(tp.moves):
            here = (m.x, m.y, m.z)
            if prev is not None:
                L = arc_length(prev, m) if getattr(m, 'is_arc', False) else math.dist(prev, here)
                if feeds is not None and m.kind != 'rapid' and feeds[k] > 0:
                    v = feeds[k]
                else:
                    v = _speeds(m, prev, op, tool, spec)
                t += L / max(v / 60.0, 1e-6)
            out.append(t)
            prev = here
    return out


def estimate(toolpaths, setup, spec: TimingSpec | None = None) -> dict:
    """{'paths': [(parcours, s)], 'changes': n, 'change_s': s, 'total': s}."""
    spec = spec or TimingSpec()
    paths = [(tp, path_seconds(tp, setup, spec)) for tp in toolpaths if tp.moves]
    changes, last = 0, None
    for tp, _s in paths:
        if tp.tool_id != last:
            changes += 1
            last = tp.tool_id
    change_s = changes * spec.tool_change
    return {'paths': paths, 'changes': changes, 'change_s': change_s,
            'total': sum(s for _tp, s in paths) + change_s}


def format_duration(seconds: float) -> str:
    s = int(round(seconds))
    h, rest = divmod(s, 3600)
    m, s = divmod(rest, 60)
    if h:
        return f'{h} h {m:02d} min'
    if m:
        return f'{m} min {s:02d} s'
    return f'{s} s'


def spec_from_settings(settings) -> TimingSpec:
    """Réglages F10 (FAO) ; à défaut, ceux d'un plugin (`defaults['timing']`)."""
    from ..plugins import REGISTRY
    plug = REGISTRY.defaults.get('timing', {})
    d = TimingSpec()

    def val(key, field, default):
        if settings is not None and settings.contains(key):
            try:
                return float(settings.value(key))
            except (TypeError, ValueError):
                return default
        return float(plug.get(field, default))
    return TimingSpec(rapid=val('fao/vitesse_rapide', 'rapid', d.rapid), accel=val('fao/acceleration', 'accel', d.accel),
                      tool_change=val('fao/changement_outil', 'tool_change', d.tool_change), corner=d.corner)
