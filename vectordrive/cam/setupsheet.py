"""Fiche de réglage (feuille d'atelier) : ce qu'il faut pour monter et
lancer le travail — plaque, encombrement du dessin, outils (numéro, type,
diamètre, angle), opérations dans l'ordre (stratégie, outil, profondeur,
passe, surépaisseur, avances, temps estimé), totaux, avertissements des
parcours et une vue de dessus des trajectoires. Un fichier HTML autonome,
à imprimer depuis le navigateur.
"""
from __future__ import annotations

import datetime
import html

from .model import OP_KINDS, TOOL_KINDS


def _fmt(v, unit: str = '') -> str:
    try:
        return f'{float(v):g}'.replace('.', ',') + (f' {unit}' if unit else '')
    except (TypeError, ValueError):
        return html.escape(str(v))


def _svg(toolpaths, width: float = 640.0) -> str:
    """Vue de dessus des trajectoires (avances en trait plein, rapides en
    pointillés), mise à l'échelle dans `width` pixels."""
    lines = [(kind, pts) for tp in toolpaths for kind, pts in tp.polylines(0.05)]
    xs = [p[0] for _k, pts in lines for p in pts]
    ys = [p[1] for _k, pts in lines for p in pts]
    if not xs:
        return ''
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    w, h = max(x1 - x0, 1e-6), max(y1 - y0, 1e-6)
    k = width / w
    hh = h * k
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" height="{hh + 2:.0f}" '
           f'viewBox="-1 -1 {width + 2:.1f} {hh + 2:.1f}">']
    for kind, pts in lines:
        d = ' '.join(f'{(x - x0) * k:.2f},{(y1 - y) * k:.2f}' for x, y, *_z in pts)
        style = 'stroke:#999;stroke-dasharray:3,3' if kind == 'rapid' else 'stroke:#c33'
        out.append(f'<polyline points="{d}" style="fill:none;{style};stroke-width:0.8"/>')
    out.append('</svg>')
    return ''.join(out)


def build(doc, setup, toolpaths, timing: dict | None = None, title: str = '') -> str:
    """Le HTML de la fiche."""
    from .timing import format_duration
    esc = html.escape
    tools = {t.id: t for t in setup.tools}
    rows_t = []
    used = []
    for op in setup.operations:
        if op.enabled and op.tool_id in tools and op.tool_id not in used:
            used.append(op.tool_id)
    for tid in used:
        t = tools[tid]
        rows_t.append(f'<tr><td>T{t.number}</td><td>{esc(t.name)}</td><td>{esc(TOOL_KINDS.get(t.kind, t.kind))}</td>'
                      f'<td>{_fmt(t.diameter, "mm")}</td><td>{_fmt(t.angle, "°") if t.angle else ""}</td>'
                      f'<td>{_fmt(t.tip, "mm") if t.tip else ""}</td><td>{_fmt(t.spindle, "tr/min")}</td></tr>')
    secs = {id(tp): s for tp, s in (timing or {}).get('paths', [])}
    by_op = {}
    for tp in toolpaths:
        by_op.setdefault(tp.op_id, []).append(tp)
    rows_o = []
    n = 0
    for op in setup.operations:
        if not op.enabled:
            continue
        n += 1
        t = tools.get(op.tool_id)
        from .model import op_feed                   # l'avance du cadre actif (ébauche ou finition)
        s = sum(secs.get(id(tp), 0.0) for tp in by_op.get(op.id, []))
        rows_o.append(f'<tr><td>{n}</td><td>{esc(op.name or "")}</td><td>{esc(OP_KINDS.get(op.kind, op.kind))}</td>'
                      f'<td>{"T" + str(t.number) if t else "?"}</td><td>{_fmt(op.depth, "mm")}</td>'
                      f'<td>{_fmt(op.step_down or (t.step_down if t else 0), "mm")}</td><td>{_fmt(op.stock, "mm")}</td>'
                      f'<td>{_fmt(op_feed(op, t), "mm/min")}</td>'
                      f'<td>{format_duration(s) if s else ""}</td></tr>')
    warns = sorted({w for tp in toolpaths for w in tp.warnings})
    pl = doc.plate
    plate = (f'{_fmt(pl.width)} × {_fmt(pl.height)} mm' + (f' × ép. {_fmt(pl.thickness)} mm' if pl.thickness else '') +
             (f' — {esc(pl.material)}' if pl.material else '')) if pl else '—'
    bb = doc.bbox()
    draw = f'{_fmt(bb[2] - bb[0])} × {_fmt(bb[3] - bb[1])} mm' if bb else '—'
    total = format_duration((timing or {}).get('total', 0.0)) if timing else '—'
    changes = (timing or {}).get('changes', 0)
    feed_len = sum(tp.lengths()[0] for tp in toolpaths)
    now = datetime.datetime.now().strftime('%d/%m/%Y %H:%M')
    css = ('body{font-family:Segoe UI,Arial,sans-serif;font-size:11pt;margin:18px}h1{font-size:16pt;margin:0}'
           'table{border-collapse:collapse;margin:8px 0 14px}td,th{border:1px solid #888;padding:3px 7px;'
           'text-align:left}th{background:#eee}.k{color:#555}@media print{body{margin:0}}')
    return ''.join([
        '<!doctype html><html lang="fr"><head><meta charset="utf-8">',
        f'<title>Fiche de réglage — {esc(title)}</title><style>{css}</style></head><body>',
        f'<h1>Fiche de réglage — {esc(title)}</h1><p class="k">{now}</p>',
        f'<p><b>Plaque :</b> {plate}<br><b>Dessin :</b> {draw}<br><b>Temps estimé :</b> {total} '
        f'({changes} changement(s) d\'outil) — <b>avance :</b> {_fmt(round(feed_len, 1), "mm")}</p>',
        '<h2>Outils</h2><table><tr><th>N°</th><th>Nom</th><th>Type</th><th>Ø</th><th>Angle</th><th>Pointe</th>'
        '<th>Broche</th></tr>', ''.join(rows_t), '</table>',
        '<h2>Opérations</h2><table><tr><th>#</th><th>Nom</th><th>Stratégie</th><th>Outil</th><th>Profondeur</th>'
        '<th>Passe</th><th>Surépaisseur</th><th>Avance</th><th>Temps</th></tr>', ''.join(rows_o), '</table>',
        ('<h2>À vérifier</h2><ul>' + ''.join(f'<li>{esc(w)}</li>' for w in warns) + '</ul>') if warns else '',
        '<h2>Trajectoires (vue de dessus)</h2>', _svg(toolpaths), '</body></html>'])
