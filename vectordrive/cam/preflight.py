"""Vérification avant l'écriture du programme machine, reprise de TauDrive
(même auteur).

Le dernier moment où une erreur ne coûte rien : après, elle coûte une
plaque ou une pièce. Le récapitulatif rassemble ce qu'on vérifierait à la
main quand on n'est pas pressé — et c'est pressé qu'on se trompe. Il ne
bloque rien : il montre, et signale ce qui mérite un regard ; la décision
reste à l'opérateur, qui voit la matière et la pièce.
"""
from __future__ import annotations

import html
from dataclasses import dataclass, field

BLOQUANT, ATTENTION, INFO = 'bloquant', 'attention', 'info'
_RANK = {BLOQUANT: 0, ATTENTION: 1, INFO: 2}
#: au-delà, un travail est « long » (s)
LONG_JOB_S = 3600.0


@dataclass
class Report:
    paths: int = 0
    operations: int = 0
    disabled: int = 0
    feed_mm: float = 0.0
    rapid_mm: float = 0.0
    duration_s: float = 0.0
    tool_changes: int = 0
    #: (numéro, nom, nature) des outils employés, dans l'ordre
    tools: list = field(default_factory=list)
    extent: tuple | None = None                     # (x0, y0, x1, y1) des parcours
    zero: str = ''                                  # où tombe le zéro du programme sur la plaque (vide : non dit)
    #: (niveau, texte), le plus grave d'abord
    notes: list = field(default_factory=list)

    def blocking(self) -> list[str]:
        return [t for lv, t in self.notes if lv == BLOQUANT]


def _extent(tp):
    xs = [m.x for m in tp.moves if m.kind != 'rapid']
    ys = [m.y for m in tp.moves if m.kind != 'rapid']
    return (min(xs), min(ys), max(xs), max(ys)) if xs else None


#: instructions qui arrêtent la machine et attendent l'opérateur
STOPS = ('retournement', 'question')


class _Loose:
    """Parcours sans opération (TypeEdit, programme relu), vu comme une
    opération de la prise du dessin."""
    id, kind, instruction, enabled, setup_face, body3d, model_path = '', 'parcours', '', True, '', -1, ''

    def __init__(self, tp):
        self.name = tp.name or 'parcours'


def setup_changes(doc, setup, toolpaths) -> list:
    """Passages d'une prise à une autre sans arrêt entre les deux
    (`STOPS`) : [(niveau, texte)] — autre face vers l'outil : la pièce doit
    être retournée (bloquant) ; autre corps seul : il est peut-être tenu à
    côté, à regarder."""
    out = []
    for o, k, prev, before, weak, turned in _changes(doc, setup, toolpaths):
        name = before.name or before.kind
        if turned and weak:
            out.append((ATTENTION, f'« {o.name or o.kind} » usine la pièce tournée autrement que « {name} », avec '
                                   'seulement une question entre les deux : si elle ne demande pas de retourner la '
                                   'pièce, la machine enchaînerait sans — mettre plutôt une instruction '
                                   '« Retournement de la pièce ».'))
        elif turned and isinstance(o, _Loose):
            out.append((BLOQUANT, f'Le parcours « {o.name} » (sans opération : prise du dessin) vient après « {name} », '
                                  'sur la pièce tournée autrement, sans arrêt entre les deux : la machine '
                                  'l\'usinerait sur la pièce retournée — le remettre dans la liste avant le '
                                  'retournement, ou ajouter à la main un arrêt « Retournement de la pièce » juste '
                                  'avant lui.'))
        elif turned and isinstance(before, _Loose):
            out.append((BLOQUANT, f'« {o.name or o.kind} » usine la pièce tournée autrement que le parcours « {name} » '
                                  '(sans opération : prise du dessin), sans arrêt entre les deux : la machine '
                                  f'enchaînerait sans la retourner — si « {name} » vient après un retournement, le '
                                  'remettre dans la liste avant lui ; sinon, ajouter un arrêt « Retournement de la '
                                  f'pièce » avant « {o.name or o.kind} » (bouton « Ajouter les arrêts » s\'il est '
                                  'proposé, sinon à la main).'))
        elif turned:
            out.append((BLOQUANT, f'« {o.name or o.kind} » usine la pièce tournée autrement que « {name} », sans '
                                  'arrêt entre les deux : la machine enchaînerait sans la retourner — ajouter une '
                                  'instruction « Retournement de la pièce » avant (bouton « Ajouter les arrêts » ; '
                                  'parcours déplacés à la main : les remettre dans l\'ordre des opérations).'))
        elif weak:
            continue                                     # autre corps seul, après une question : laissé
        else:
            out.append((ATTENTION, f'« {o.name or o.kind} » usine un autre corps seul que « {name} », sans arrêt '
                                   'entre les deux : s\'il doit être posé ou repris, ajouter une instruction '
                                   '« Retournement de la pièce » avant.'))
    return out


def _changes(doc, setup, toolpaths, loose: bool = True):
    """(opération, sa prise, prise d'avant, opération d'avant, faible,
    tournée) à chaque passage d'une prise à une autre sans « Retournement »
    entre les deux — faible : seulement une question (elle arrête la
    machine, mais ne dit pas de retourner la pièce) ; tournée : autre face
    vers l'outil, aussi pour un corps positionné à part (sa face propre
    quand la prise n'en dit pas d'autre) — dans l'ordre des parcours écrits
    (`toolpaths` : cochés, déplacés, instructions comprises), pas celui des
    opérations ; `loose` : les parcours sans opération comptent (prise du
    dessin, `_Loose`)."""
    from ..core import workspace
    ops = {o.id: o for o in setup.operations}
    prev, stop, asked = None, False, False
    for tp in toolpaths:
        o = ops.get(tp.op_id)
        if o is None and loose and not tp.op_id:
            o = _Loose(tp)
        if o is None or not o.enabled:
            continue
        if o.kind == 'instruction':
            stop = stop or o.instruction == 'retournement'
            asked = asked or o.instruction in STOPS
            continue
        if not (tp.moves or tp.cycles):                   # perçages : cycles seulement
            continue
        k = workspace.op_setup(o, doc)
        if prev is not None and k != prev[0] and not stop:
            yield o, k, prev[0], prev[1], asked, _turned(doc, o, prev[1])
        prev, stop, asked = (k, o), False, False


def _turned(doc, o, before) -> bool:
    """`o` usine-t-il la pièce avec une autre face vers l'outil que
    `before` — face réelle (corps positionné à part : sa face propre) ; entre
    deux fichiers différents, la face de leur prise ?"""
    from . import mill3d
    from ..core import workspace
    if mill3d.model_path(doc, o) != mill3d.model_path(doc, before):
        return workspace.op_setup(o, doc)[0] != workspace.op_setup(before, doc)[0]
    return workspace.pose_face(o, doc) != workspace.pose_face(before, doc)


def add_stops(doc, setup, toolpaths) -> list:
    """Instruction « Retournement de la pièce » (broche coupée, parking,
    attente de l'opérateur) ajoutée quand une opération usine la pièce
    tournée autrement que celle d'avant sans arrêt entre les deux — après la
    dernière opération de la prise d'avant, même décochée, désactivée ou
    vide (cochée plus tard, elle ne se retrouve pas derrière l'arrêt), mais
    avant un palpage ou un message de la prise suivante ; un autre corps
    seul, sur la même face, est laissé (il peut être tenu à côté). Dans
    l'ordre des opérations (celui où les parcours sont remis une fois les
    arrêts calculés). L'arrêt garde la prise qu'il annonce (`stop_notes`).
    Rend les instructions ajoutées."""
    from .auto3d import pose_text
    from .model import Operation
    from ..core import placement3d as P3
    from ..core import workspace
    from ..i18n import tr
    order = {o.id: i for i, o in enumerate(setup.operations)}
    ranked = sorted(toolpaths, key=lambda t: order.get(t.op_id, len(order)))
    added, done = [], set()
    for o, k, prev, before, weak, turned in list(_changes(doc, setup, ranked, loose=False)):
        if not turned or weak or o.id in done:          # une question à sa place : l'opérateur l'a voulue
            continue
        done.add(o.id)
        who = tr('le corps {0}').format(k[1] + 1) if k[1] >= 0 else tr('la pièce')
        side = k[0] or (workspace.pose_face(o, doc) if P3.body_of(doc, k[1]) is not None else '')
        text = pose_text(who, side)                      # corps positionné à part : sa pose, pas « comme le dessin »
        stop = Operation(name=text, kind='instruction', instruction='retournement',     # pose annoncée gardée :
                         params={'message': text, 'park': True, 'setup': [side, k[1]]}, tool_id='')   # stop_notes
        ops = setup.operations
        at = ops.index(before)
        for i in range(at + 1, ops.index(o)):            # après la dernière de la pose d'avant (autre corps non
            q = ops[i]                                   # positionné à part, même face : même pose)
            if q.kind == 'instruction':
                continue
            g = workspace.op_setup(q, doc)
            if g == prev or (P3.body_of(doc, g[1]) is None and not _turned(doc, q, before)):
                at = i
        ops.insert(at + 1, stop)
        added.append(stop)
    return added


def _announced(o):
    """Prise (face telle que posée, corps) qu'annonce un arrêt posé par
    `add_stops`, ou None (arrêt fait à la main, autre instruction)."""
    v = (o.params if isinstance(o.params, dict) else {}).get('setup')
    try:
        return str(v[0] or ''), int(v[1])
    except (TypeError, ValueError, IndexError, KeyError, OverflowError):
        return None


def stop_notes(doc, setup, toolpaths) -> list:
    """[(niveau, texte)] des arrêts qui annoncent une prise (`add_stops`)
    suivis, dans l'ordre des parcours écrits, d'une opération d'une autre
    prise : l'opérateur poserait la pièce comme annoncé et la machine
    usinerait autre chose (opération de la prise d'avant cochée ou réactivée
    derrière l'arrêt, opération déplacée, parcours sans opération — prise du
    dessin) ; un autre corps seul : à regarder. Un « Retournement » fait à la
    main après lui pose la pièce autrement (plus rien n'est dit) ; une
    question (« Continuer ? ») ne change pas la pose annoncée."""
    from . import mill3d
    from ..core import workspace
    ops = {o.id: o for o in setup.operations}
    out, pending = [], None
    for tp in toolpaths:
        o = ops.get(tp.op_id)
        if o is None and not tp.op_id:
            o = _Loose(tp)
        if o is None or not o.enabled:
            continue
        if o.kind == 'instruction':
            want = _announced(o) if o.instruction in STOPS else None
            if want is not None:
                pending = (o, want)
            elif o.instruction == 'retournement':
                pending = None
            continue
        if not (tp.moves or tp.cycles):
            continue
        if pending is not None:
            stop, (face, body) = pending
            if face:                                       # face du dessin d'aujourd'hui : ''
                face = workspace.norm_face(doc, face, mill3d.model_path(doc, o), body)
            k = workspace.op_setup(o, doc)
            name, said = o.name or o.kind, stop.name or stop.instruction
            want = face or workspace.drawing_face(doc, mill3d.model_path(doc, o) or None, body)
            if workspace.pose_face(o, doc) != want:      # face réelle (corps positionné à part : la sienne)
                out.append((BLOQUANT, f'L\'arrêt « {said} » annonce une autre prise que celle de « {name} », qui '
                                      f'le suit : l\'opérateur poserait la pièce comme annoncé et la machine '
                                      f'usinerait « {name} » sur la pièce mal posée — mettre l\'arrêt juste avant '
                                      'la première opération de sa prise (ou le supprimer, puis « Ajouter les '
                                      'arrêts »), puis recalculer les parcours.'))
            elif k[1] != body:
                out.append((ATTENTION, f'L\'arrêt « {said} » annonce un autre corps que celui de « {name} », qui '
                                       'le suit : à regarder (corps tenu à côté ?).'))
        pending = None
    return out


def surface_notes(doc, setup) -> list:
    """[(niveau, texte)] des surfaces posées : calque qui a perdu sa pose
    (bloquant s'il a du contenu), opération rattachée à une surface disparue."""
    from ..core import surface2d
    out = []
    for L in surface2d.lost(doc):
        if any(not surface2d.is_outline(it) for it in L.items):
            out.append((BLOQUANT, f'Le calque « {L.name} » a le contour d\'une surface posée mais n\'est pas (ou '
                                  'plus) une surface posée — document enregistré par la version 0.523.0 à 0.527.0, '
                                  'ou contour copié hors de sa surface : son contenu serait usiné sur la prise du '
                                  'dessin, à Z 0 (modèle de dessin : sans sa pièce 3D). Refaire la pose (vue 3D, '
                                  'Utiliser ▸ Poser sur une surface 2D) et '
                                  'y remettre le contenu, ou supprimer ce contour.'))
    from ..io import model3d
    alone = []
    for L in doc.layers:
        d = surface2d.of_layer(L)
        if d is None or not d.get('path') or not any(not surface2d.is_outline(it) for it in L.items):
            continue
        if surface2d.placement_of(doc, d) is None:
            src = model3d.source_of(doc)
            if src is None:
                alone.append(L.name)
            elif model3d.same_name(src, d['path']):
                out.append((ATTENTION, f'La surface « {L.name} » n\'a pas pu être rapportée à la pièce du dessin ({src}) '
                                       ': pièce illisible ? Son contenu reste où il était, même si la pièce a été '
                                       'placée autrement depuis — vérifier sa place (vue 3D).'))
            else:
                out.append((ATTENTION, f'La surface « {L.name} » a été posée sur une autre pièce que celle du dessin '
                                       f'({d["path"]}) : son contenu reste où il était, même si la pièce a été placée '
                                       'autrement depuis — vérifier sa place (vue 3D).'))
        elif surface2d.other_part(doc, d):
            out.append((ATTENTION, f'La surface « {L.name} » a été posée sur {d["path"]} ; elle est rapportée à la '
                                   f'pièce du dessin {surface2d.part_of(doc, d)}, qui n\'a pas le même contenu : '
                                   'vérifier que c\'est la même pièce (révision, placement).'))
    if alone:
        out.append((ATTENTION, 'Pièce 3D du dessin introuvable : les surfaces posées '
                               + ', '.join(f'« {n} »' for n in alone) + ' restent où elles étaient, même si la pièce a '
                               'été placée autrement depuis.'))
    for o in setup.operations:
        if o.enabled and surface2d.orphaned(doc, o):
            out.append((ATTENTION, f'« {o.name or o.kind} » est rattachée à une surface posée qui n\'existe plus : '
                                   'elle n\'usine rien (la supprimer, ou annuler la suppression de la surface).'))
    return out


def safety(doc, setup, toolpaths, post_warnings=()) -> list:
    """Ce qui rendrait le programme faux, signalé avant l'écriture même
    quand la vérification est coupée : arrêt qui manque entre deux prises,
    arrêt qui annonce une autre prise que celle qui le suit, surface qui a
    perdu sa pose, avertissement « BLOQUANT » du post (arrêt qu'il ne sait
    pas écrire…). Rend les textes."""
    out = [t for lv, t in setup_changes(doc, setup, toolpaths) if lv == BLOQUANT]
    out += [t for lv, t in stop_notes(doc, setup, toolpaths) if lv == BLOQUANT]
    out += [t for lv, t in surface_notes(doc, setup) if lv == BLOQUANT]
    out += [w for w in post_warnings if w.startswith('BLOQUANT')]
    return out


def inspect(doc, setup, toolpaths, *, post_warnings=(), timing_spec=None, all_paths=None, zero=None) -> Report:
    """Récapitulatif et points à regarder (cam.timing pour la durée) ;
    `all_paths` : tous les parcours de la liste, cochés ou non (opération
    active absente du programme) ; `zero` : (texte, repérable) de
    `cam.post.zero_text`, le zéro du programme sur la plaque."""
    from . import timing
    from ..core.document import Text
    r = Report()
    add = r.notes.append
    ops = {o.id: o for o in setup.operations}
    r.operations = sum(1 for o in setup.operations if o.enabled)
    r.disabled = len(setup.operations) - r.operations
    live = [tp for tp in toolpaths if tp.moves or tp.cycles]
    r.paths = len(live)
    seen_tools = []
    for tp in live:
        f, ra = tp.lengths()
        r.feed_mm += f
        r.rapid_mm += ra
        t = setup.tool(tp.tool_id)
        if t is not None and t.id not in [x[3] for x in seen_tools]:
            seen_tools.append((t.number, t.name, t.kind, t.id))
        e = _extent(tp)
        if e:
            r.extent = e if r.extent is None else (min(r.extent[0], e[0]), min(r.extent[1], e[1]),
                                                   max(r.extent[2], e[2]), max(r.extent[3], e[3]))
    r.tools = [x[:3] for x in seen_tools]
    est = timing.estimate(live, setup, timing_spec)
    r.duration_s, r.tool_changes = est['total'], est['changes']

    if not live:
        add((BLOQUANT, 'Aucun parcours à usiner : le programme serait vide.'))
    if zero is not None:                                       # l'opérateur règle l'origine de la machine sur ce point
        r.zero = zero[0]
        if not zero[1]:
            add((ATTENTION, f'Zéro du programme (X0 Y0) : {zero[0]}. L\'opérateur devra régler l\'origine de la '
                            'machine sur ce point précis, sans repère sur la plaque.'))
    for tp in toolpaths:
        if not (tp.moves or tp.cycles):
            add((ATTENTION, f'« {tp.name or "opération"} » ne produit aucun parcours.'))
    # sortie de plaque, au-delà du rayon de l'outil (un détourage extérieur la déborde d'autant)
    pl = getattr(doc, 'plate', None)
    if pl is not None:
        for tp in live:
            e = _extent(tp)
            t = setup.tool(tp.tool_id)
            tol = (t.diameter / 2 if t else 0.0) + 0.5
            if e and (e[0] < pl.x - tol or e[1] < pl.y - tol or e[2] > pl.x + pl.width + tol
                      or e[3] > pl.y + pl.height + tol):
                add((ATTENTION, f'« {tp.name or "parcours"} » sort de la plaque ({pl.width:g} × {pl.height:g} mm).'))
    # objets masqués : jamais usinés
    hidden = sum(1 for L in doc.layers for it in L.items if not (L.visible and it.visible))
    if hidden:
        add((INFO, f'{hidden} objet(s) masqué(s) (ou sur un plan masqué) : ils ne seront pas usinés.'))
    # textes dont la police manque : contour de repli (Arial), pas celui voulu
    from ..core import fonts
    nofont = sum(1 for it in doc.iter_leaves() if isinstance(it, Text)
                 and (not it.outline or not fonts.is_available(it.font)))
    if nofont:
        add((ATTENTION, f'{nofont} texte(s) sans contour de leur police (police absente) : '
                        f'usinés avec la police de remplacement, ou pas du tout.'))
    # porte-outil : une descente plus profonde que le dépassement de l'outil le met dans la matière
    for tp in live:
        t = setup.tool(tp.tool_id)
        from .model import holder_of
        so = holder_of(t, setup)[0]
        low = min((m.z for m in tp.moves if m.kind != 'rapid'), default=0.0)
        if so > 0 and -low > so:
            add((ATTENTION, f'« {tp.name or "parcours"} » descend à {-low:.2f} mm, plus que le dépassement de '
                            f'« {t.name} » ({so:g} mm) : le porte-outil touchera la pièce là où la matière reste '
                            '— simuler pour voir où.'))
    # espace de travail : l'outil ou le porte-outil dans l'étau, le mandrin, une bride…
    from ..core import workspace
    for h in workspace.collisions_all(live, setup, doc):          # chaque prise contre son espace
        add((BLOQUANT, 'Espace de travail : ' + workspace.hit_text(h)))
    for text in workspace.unchecked(live, setup, doc):               # ce qui n'a pas pu l'être
        add((ATTENTION, 'Espace de travail : ' + text))
    for lv, text in setup_changes(doc, setup, toolpaths):            # pièce à tourner sans arrêt
        add((lv, text))
    for note in surface_notes(doc, setup):                         # surface sans sa pose, disparue
        add(note)
    for note in stop_notes(doc, setup, toolpaths):                 # arrêt qui annonce une autre prise
        add(note)
    if all_paths is not None:                                      # active, mais pas dans le programme
        listed: dict = {}
        for tp in all_paths:
            listed[tp.op_id] = listed.get(tp.op_id, False) or getattr(tp, 'shown', True)
        for o in setup.operations:
            if not o.enabled:
                continue
            if o.id not in listed:
                add((ATTENTION, f'« {o.name or o.kind} » est active mais n\'a pas de parcours calculé : elle ne '
                                'sera pas dans le programme — recalculer les parcours.'))
            elif not listed[o.id]:
                add((INFO, f'« {o.name or o.kind} » : parcours décoché, pas dans le programme.'))
    from ..io import model3d
    twin = model3d.twin_note(doc)
    if twin:                                                       # deux pièces 3D du même nom
        add((ATTENTION, twin))
    # un même numéro d'outil pour des réglages différents : la machine prend ceux de son magasin
    by_number: dict = {}
    for tp in live:
        t = setup.tool(tp.tool_id)
        if t is not None and t.number:
            by_number.setdefault(t.number, set()).add((t.kind, round(t.diameter, 4), t.power, t.frequency))
    for n, sets in sorted(by_number.items()):
        if len(sets) > 1:
            add((ATTENTION, f'T{n} est appelé pour {len(sets)} outils ou réglages différents : la machine '
                            'appliquera ce que porte son magasin.'))
    for tp in live:
        t = setup.tool(tp.tool_id)
        if t is not None and t.kind == 'laser' and t.power <= 0:
            add((ATTENTION, f'« {t.name} » à 0 % de puissance : il ne marquera rien.'))
            break
    for tp in toolpaths:
        for w in tp.warnings:
            lv = BLOQUANT if w.startswith('BLOQUANT') else ATTENTION
            add((lv, f'{tp.name or "parcours"} : {w}'))
    for w in post_warnings:
        add((BLOQUANT if w.startswith(('export refusé', 'BLOQUANT')) else INFO, w))
    if r.disabled:
        add((INFO, f'{r.disabled} opération(s) désactivée(s) : pas dans le programme.'))
    if r.duration_s > LONG_JOB_S:
        add((INFO, f'Travail long : {timing.format_duration(r.duration_s)} estimées.'))
    seen = set()
    r.notes = [n for n in sorted(r.notes, key=lambda n: _RANK[n[0]]) if not (n in seen or seen.add(n))]
    return r


def summary_html(r: Report, tr=lambda s: s) -> str:
    """Récapitulatif lisible (fenêtre de vérification) : les points à voir
    d'abord (bloquants, puis à surveiller, puis pour information), puis les
    chiffres du programme."""
    from . import timing
    rows = [(tr('Parcours'), f'{r.paths}'), (tr('Opérations actives'), f'{r.operations}'),
            (tr('Longueur en avance'), f'{r.feed_mm:.0f} mm'), (tr('Longueur en rapide'), f'{r.rapid_mm:.0f} mm'),
            (tr('Durée estimée'), timing.format_duration(r.duration_s)),
            (tr('Changements d\'outil'), f'{r.tool_changes}')]
    if r.zero:
        rows.insert(0, (tr('Zéro du programme (X0 Y0)'), r.zero))
    if r.extent:
        e = r.extent
        rows.append((tr('Encombrement des parcours'), f'{e[2] - e[0]:.1f} × {e[3] - e[1]:.1f} mm'))
    colors = {BLOQUANT: '#c92a2a', ATTENTION: '#e67700', INFO: '#868e96'}
    marks = {BLOQUANT: '⛔', ATTENTION: '⚠', INFO: 'ℹ'}
    rank = {BLOQUANT: 0, ATTENTION: 1, INFO: 2}
    if r.notes:
        notes = sorted(r.notes, key=lambda n: rank.get(n[0], 3))
        out = ['<p>' + '<br>'.join(f'<span style="color:{colors[lv]}">{marks[lv]} {html.escape(t)}</span>'
                                   for lv, t in notes) + '</p>']
    else:
        out = [f'<p>{html.escape(tr("Rien de particulier à signaler."))}</p>']
    out += ['<table>'] + [f'<tr><td>{html.escape(a)}</td><td><b>{html.escape(b)}</b></td></tr>' for a, b in rows]
    out.append('</table>')
    if r.tools:
        out.append(f'<p><b>{html.escape(tr("Outils"))}</b><br>' + '<br>'.join(
            html.escape(f'T{n} — {name} ({kind})') for n, name, kind in r.tools) + '</p>')
    return '\n'.join(out)
