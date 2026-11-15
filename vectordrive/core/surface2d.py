"""Surface 3D posée en 2D : une face (ou des faces de même orientation)
choisie dans la vue 3D devient un sous-onglet du dessin — un calque dont
les coordonnées sont celles de la prise qui tourne cette face vers l'outil
(une des six faces, ou la pièce posée pour une face inclinée :
`core.placement3d`). Le contour de la face y est tracé (guide verrouillé,
jamais usiné) ; ce qu'on y dessine s'usine dans cette prise, à partir de la
hauteur de la face.

Le calque garde dans `extra['surface2d']` : la face de la prise (telle que
`mill3d.side_placement` la lit), le corps (-1 : toute la pièce), les faces
choisies, le fichier ('' : les volumes du dessin), la cote Z de la face sous
le haut de la pièce posée, et son écart de planéité.

Il garde aussi le placement de la prise au moment de la pose (`pl`) : la
pièce placée autrement ensuite (rotation, position, plaque, corps posé à
part), le contenu du calque la suit (`follow`) ; tant qu'il ne l'a pas
suivie, il n'est pas usiné.

Les opérations : une opération dont les objets sont sur un calque de
surface — ou, usinée par couleur, créée sur lui — lui est rattachée
(`attach`) : elle prend sa prise et part de sa cote, et
`Operation.surface2d` garde ce que le rattachement a changé, pour le
défaire quand ses objets quittent le calque ou qu'il disparaît (`detach`,
`sync`). Elle n'usine que les objets de son calque ; les autres opérations
n'usinent jamais ceux d'une surface (`layer_filter`)."""
from __future__ import annotations

import numpy as np

#: clé du calque d'une surface posée
KEY = 'surface2d'
#: clé du contour (guide) d'une surface : jamais usiné
OUTLINE = 'surface2d_contour'
#: écart (mm) sous lequel la surface est plane
FLAT_TOL = 0.05
#: stratégies laissées de côté : leur zone vient de la pièce 3D, ou elles n'usinent rien
NOT_2D = ('instruction', 'surface3d', 'ebauche3d', 'reprise3d', 'niveaux3d', 'relief', 'decoupe3d')


def _raw(doc, path: str):
    from ..cam import mill3d
    return mill3d.raw_model(path) if path else mill3d.volumes_model(doc)


def _posed(doc, path: str, face: str, body: int):
    from ..cam import mill3d
    return mill3d.load_model(doc, path, face, body) if path else mill3d.volumes_model(doc, face, body)


def pose(doc, path: str, faces, body: int = -1) -> dict | None:
    """La prise qui tourne les `faces` (pièce `path`, '' : volumes du dessin)
    vers l'outil, leur contour et leur cote dans cette prise : {'face',
    'body', 'faces', 'path', 'z', 'flat', 'loops' [[(x, y)…]], 'pl'
    (placement de la prise), 'down' (vraie : tournées vers le bas même
    posée à l'inverse — maillage incohérent)} ; None : pièce absente, faces
    inconnues ou d'orientations trop différentes."""
    from . import faces3d
    from . import placement3d as P3
    from ..cam import mill3d
    raw = _raw(doc, path)
    if raw is None or not len(getattr(raw, 'triangles', ())):
        return None
    if body >= 0:
        raw = mill3d.submodel(raw, body)
    faces = sorted(int(f) for f in faces)
    idx = faces3d.face_triangles(raw.face_ids(), faces)
    if not len(idx):
        return None
    n = outward_normal(raw, idx)
    if n is None:                                      # faces tournées de tous côtés
        return None
    for normal in (n, -n):                             # maillage retourné par endroits : la pose inverse
        face = P3.face_for_rest(-normal)               # posée sur l'opposé : la face vers l'outil
        m = _posed(doc, path, face, body)
        if m is None:
            return None
        pidx = faces3d.face_triangles(m.face_ids(), faces)
        down = facing_down(m, pidx)
        if not down:
            break
    allt = np.asarray(m.triangles, dtype=np.float64)
    z = allt[pidx][:, :, 2]
    top = float(m.bounds()[5])
    loops = [[(round(float(p[0]), 4), round(float(p[1]), 4)) for p in L[:-1]]
             for L in faces3d.boundary_loops(allt, pidx)]
    pl = mill3d.side_placement(doc, path, face, body) if path else None
    return {'face': face, 'body': int(body), 'faces': faces, 'path': path or '',
            'z': round(float(z.max()) - top, 4), 'flat': round(float(z.max() - z.min()), 4), 'loops': loops,
            'pl': P3.to_dict(pl) if pl is not None else None, 'down': down}


def facing_down(model, idx) -> bool:
    """Les faces `idx` du modèle posé sont-elles tournées vers le bas ? Un
    rayon vers le haut depuis le centre de leur plus grand triangle traverse
    alors son propre corps un nombre impair de fois (il part du dedans) —
    sans se fier au sens des triangles, faux dans certains fichiers."""
    tris = np.asarray(model.triangles, dtype=np.float64)
    idx = np.asarray(idx, dtype=np.int64)
    if not len(idx) or not len(tris):
        return False
    a = tris[idx]
    k = int(np.argmax(np.linalg.norm(np.cross(a[:, 1] - a[:, 0], a[:, 2] - a[:, 0]), axis=1)))
    c = a[k].mean(axis=0)
    rest = np.ones(len(tris), dtype=bool)
    rest[idx] = False
    bid = getattr(model, 'body_ids', None)
    if callable(bid):
        b = np.asarray(bid())
        if len(b) == len(tris):
            rest &= b == b[idx[k]]                     # son corps seulement : un autre peut le surplomber
    t = tris[rest]
    if not len(t):
        return False
    p = c[:2] + (1.7e-6, 2.9e-6)                       # à côté des arêtes et des sommets
    e1, e2, w = t[:, 1, :2] - t[:, 0, :2], t[:, 2, :2] - t[:, 0, :2], p - t[:, 0, :2]
    den = e1[:, 0] * e2[:, 1] - e1[:, 1] * e2[:, 0]
    ok = np.abs(den) > 1e-12                           # parois verticales : pas traversées
    den = np.where(ok, den, 1.0)
    u = (w[:, 0] * e2[:, 1] - w[:, 1] * e2[:, 0]) / den
    v = (e1[:, 0] * w[:, 1] - e1[:, 1] * w[:, 0]) / den
    inside = ok & (u >= 0) & (v >= 0) & (u + v <= 1)
    zt = t[:, 0, 2] + u * (t[:, 1, 2] - t[:, 0, 2]) + v * (t[:, 2, 2] - t[:, 0, 2])
    return bool(int(np.count_nonzero(inside & (zt > c[2] + 1e-4))) % 2)


def outward_normal(model, idx):
    """Normale moyenne (unitaire, vers le dehors) des triangles `idx`, None
    s'ils sont tournés de tous côtés. Maillage retourné (volume signé de ses
    corps négatif, normales vers le dedans) : la normale est retournée."""
    tris = np.asarray(model.triangles, dtype=np.float64)
    t = tris[np.asarray(idx, dtype=np.int64)]
    cr = np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0])
    total, s = float(np.linalg.norm(cr, axis=1).sum()), cr.sum(axis=0)
    if total <= 0 or float(np.linalg.norm(s)) < 0.5 * total:
        return None
    n = s / np.linalg.norm(s)
    tb = tris
    bid = getattr(model, 'body_ids', None)
    if callable(bid):
        b = np.asarray(bid())
        if len(b) == len(tris):
            tb = tris[np.isin(b, np.unique(b[np.asarray(idx, dtype=np.int64)]))]
    vol = float(np.einsum('ij,ij->i', tb[:, 0], np.cross(tb[:, 1], tb[:, 2])).sum())
    return -n if vol < 0 else n


def label(doc, info: dict) -> str:
    """Nom de la prise d'une surface (« Côté +X », « Posée sur une face plane »…)."""
    from . import placement3d as P3
    from ..i18n import tr
    return tr(P3.face_label(info.get('face') or '+Z'))


def add_layer(doc, info: dict, name: str = ''):
    """Nouveau calque (sous-onglet) de la surface `info` (`pose`) : son
    contour en guide verrouillé ; rend le calque, devenu le calque actif."""
    from . import geom
    from .document import Layer, Shape
    from ..i18n import tr
    keep = {k: info[k] for k in ('face', 'body', 'faces', 'path', 'z', 'flat', 'pl') if k in info}
    names = {L.name for L in doc.layers}
    base = name or tr('Surface — {0}').format(label(doc, info))
    nm = base if base not in names else next(f'{base} ({i})' for i in range(2, 1000) if f'{base} ({i})' not in names)
    L = Layer(name=nm, tool=doc.active_layer.tool, extra={KEY: keep})
    for pts in info.get('loops') or []:
        if len(pts) < 3:
            continue
        sh = Shape(path=geom.Path([geom.polyline(pts, closed=True)]), tool=L.tool, locked=True)
        sh.name = tr('Contour de la surface')
        sh.extra[OUTLINE] = True
        L.items.append(sh)
    doc.layers.append(L)
    doc.active = L.id
    return L


def of_layer(L) -> dict | None:
    d = (getattr(L, 'extra', None) or {}).get(KEY)
    return d if isinstance(d, dict) else None


def part_of(doc, d: dict) -> str:
    """Pièce d'une surface posée : celle du dessin (`model3d.source_of`)
    si elle porte le nom gardé — une surface se pose toujours sur la pièce du
    dessin, et le chemin gardé peut être l'ancien (dossier copié ou déplacé,
    pièce d'à côté prise puis enregistrée, lecteur vu autrement) —, sinon le
    chemin gardé ('' : volumes du dessin)."""
    p = d.get('path') or ''
    if not p:
        return ''
    from ..io import model3d
    src = model3d.source_of(doc)
    return src if src and model3d.same_name(src, p) else p


def other_part(doc, d: dict) -> bool:
    """La pièce sur laquelle la surface a été posée existe encore, n'est
    pas celle à laquelle elle est rapportée (`part_of`) et n'a pas la même
    taille : peut-être une autre pièce du même nom (une copie, même
    téléchargée ou désarchivée avec une autre date, a la même taille)."""
    import os
    p, part = d.get('path') or '', part_of(doc, d)
    if not p or not part or not os.path.isfile(p):
        return False
    from ..io import model3d
    if model3d._same(p, part):
        return False
    try:
        a, b = os.stat(p), os.stat(part)
    except OSError:
        return False
    return a.st_size != b.st_size


def layer_key(doc, L) -> tuple | None:
    """Prise (face, corps) d'un calque de surface, face du dessin ramenée à '' ; None : calque ordinaire."""
    d = of_layer(L)
    if d is None:
        return None
    from . import workspace as WS
    body = int(d.get('body', -1))
    return WS.norm_face(doc, str(d.get('face') or ''), part_of(doc, d) or None, body), body


def _record(op) -> dict | None:
    """Rattachement de l'opération à un calque de surface {layer, face, body,
    z, safe_z, dz} (ce qu'il a changé), ou None."""
    d = getattr(op, 'surface2d', None)
    return d if isinstance(d, dict) and d.get('layer') else None


def op_layer(doc, op):
    """Calque de surface auquel l'opération est rattachée (None : aucun, ou disparu)."""
    rec = _record(op)
    if rec is None:
        return None
    return next((L for L in getattr(doc, 'layers', ()) if L.id == rec['layer'] and of_layer(L) is not None), None)


def layer_filter(doc, op):
    """Calques que l'opération peut usiner (fonction calque → bool), None :
    tous (aucune surface posée). Opération rattachée à une surface : son
    calque seulement — aucun s'il a disparu (en attendant `sync`) ou si la
    pièce a été placée autrement depuis la pose (contenu pas encore suivi :
    `follow`) ; les autres : aucun calque de surface."""
    if _record(op) is not None:
        mine = op_layer(doc, op)
        if mine is None or stale(doc, mine):
            return lambda L: False
        return lambda L: L is mine
    ids = {id(L) for L in getattr(doc, 'layers', ()) if of_layer(L) is not None}
    if not ids:
        return None
    return lambda L: id(L) not in ids


def orphaned(doc, op) -> bool:
    """Opération rattachée à un calque de surface qui n'existe plus (elle
    n'usine rien ; annuler la suppression du calque la lui rend)."""
    return _record(op) is not None and op_layer(doc, op) is None


def placement_of(doc, d: dict):
    """Placement actuel de la prise d'un calque de surface
    (`mill3d.side_placement`) ; None : volumes du dessin, pièce illisible,
    ou qui n'est plus celle du dessin (placement inconnu : le contenu ne
    bouge pas, plutôt que suivre un placement par défaut)."""
    path = part_of(doc, d)
    if not path:
        return None
    from ..cam import mill3d
    if not mill3d._is_source(doc, path):
        return None
    try:
        return mill3d.side_placement(doc, path, str(d.get('face') or ''), int(d.get('body', -1)))
    except Exception:                                  # noqa: BLE001 — fichier absent ou illisible
        return None


def _moved(doc, d: dict):
    """(affine du plan, placement actuel) : contenu posé avec le placement
    gardé → posé avec l'actuel (même face en haut : rotation autour de Z et
    décalage ; affine None si la face a changé) ; None : inchangé, ou inconnu."""
    from . import placement3d as P3
    old = d.get('pl')
    if not isinstance(old, dict):
        return None
    cur = placement_of(doc, d)
    if cur is None:
        return None
    try:
        o = P3.Placement(**{k: old[k] for k in ('face', 'rot', 'mode', 'dx', 'dy') if k in old})
    except TypeError:
        return None
    if cur.face != o.face:
        return None, cur
    if abs(cur.rot - o.rot) < 1e-9 and abs(cur.dx - o.dx) < 1e-6 and abs(cur.dy - o.dy) < 1e-6:
        return None
    from .geom import Affine
    return Affine.translation(cur.dx, cur.dy) @ Affine.rotation(cur.rot - o.rot) @ \
        Affine.translation(-o.dx, -o.dy), cur


def stale(doc, L) -> bool:
    """Le calque de surface `L` a-t-il été posé avec un autre placement de
    la pièce que l'actuel (contenu pas encore suivi) ?"""
    d = of_layer(L)
    return d is not None and _moved(doc, d) is not None


def follow(doc) -> int:
    """Calques de surface posés avec un autre placement de la pièce (tournée,
    déplacée, autre plaque, corps posé à part…) : leur contenu (contour et
    dessin) suit la pièce ; rend le nombre de calques déplacés."""
    from . import placement3d as P3
    from .document import struct_copy
    n = 0
    for L in getattr(doc, 'layers', ()):
        d = of_layer(L)
        mv = _moved(doc, d) if d is not None else None
        if mv is None or mv[0] is None:
            continue
        T, cur = mv
        L.items = [struct_copy(it).transformed(T) for it in L.items]
        L.extra = {**L.extra, KEY: {**d, 'pl': P3.to_dict(cur)}}   # refaite : l'annulation garde l'ancienne
        n += 1
    return n


def _item_layers(doc) -> dict:
    """{id d'objet : calque}, objets des groupes compris."""
    out = {}

    def walk(it, L) -> None:
        out[it.id] = L
        for ch in getattr(it, 'children', None) or ():
            walk(ch, L)
    for L in doc.layers:
        for it in L.items:
            walk(it, L)
    return out


def attach(doc, op, layer) -> bool:
    """L'opération rattachée au calque de surface `layer` : sa prise (si
    elle n'en a pas déjà une autre), son Z de départ à la hauteur de la face
    et le dégagement relevé d'autant (au-dessus du haut de la pièce), si elle
    n'a pas déjà sa propre cote ; ce qui a changé est gardé
    (`Operation.surface2d`) pour être défait (`detach`). Déjà rattachée à ce
    calque : rien (les retouches restent) ; à un autre : défaite d'abord.
    Rend vrai si elle a changé."""
    d = of_layer(layer)
    if d is None or op.kind in NOT_2D or not hasattr(op, 'surface2d'):
        return False
    rec = _record(op)
    if rec is not None:
        if rec['layer'] == layer.id:
            return False
        detach(op)
    from . import workspace as WS
    key = layer_key(doc, layer)
    rec = {'layer': layer.id, 'face': None, 'body': -1, 'z': None, 'safe_z': None, 'dz': 0.0}
    mine = ((getattr(op, 'setup_face', '') or ''), int(getattr(op, 'body3d', -1)))
    if mine == ('', -1):
        if key != ('', -1):
            op.setup_face, op.body3d = str(d.get('face') or ''), key[1]
            rec['face'], rec['body'] = op.setup_face, op.body3d
    elif WS.op_setup(op, doc) == key:                  # déjà dans cette prise (dessin d'une version d'avant)
        rec['face'], rec['body'] = mine
    else:
        return False                                   # une prise à elle, pas celle de la surface
    z = round(float(d.get('z') or 0.0), 4)
    if z < -1e-9:
        if not float(getattr(op, 'z_start', 0.0) or 0.0):
            op.z_start = z
            op.safe_z = round(float(op.safe_z) - z, 4)    # le dégagement reste au-dessus du haut de la pièce
        if abs(float(op.z_start) - z) < 1e-9:
            rec['z'], rec['safe_z'], rec['dz'] = z, float(op.safe_z), -z
    op.surface2d = rec
    return True


def detach(op) -> bool:
    """Rattachement défait : prise, Z de départ et dégagement remis comme
    avant, s'ils n'ont pas été retouchés depuis ; rend vrai s'il y en avait un."""
    rec = _record(op)
    if rec is None:
        return False
    if rec.get('face') is not None and \
            ((op.setup_face or ''), int(op.body3d)) == (rec['face'], int(rec.get('body', -1))):
        op.setup_face, op.body3d = '', -1
    z = rec.get('z')
    if z is not None and abs(float(op.z_start) - float(z)) < 1e-9:
        op.z_start = 0.0
        sz = rec.get('safe_z')
        if sz is not None and abs(float(op.safe_z) - float(sz)) < 1e-9:
            op.safe_z = round(float(op.safe_z) - float(rec.get('dz') or 0.0), 4)
    op.surface2d = {}
    return True


def strip(d: dict) -> dict:
    """Opération écrite (`to_dict`) sans son rattachement à une surface
    (défait) : pour un modèle de parcours, réappliqué sur d'autres dessins."""
    rec = d.get('surface2d') if isinstance(d, dict) else None
    if not (isinstance(rec, dict) and rec.get('layer')):
        return d
    from ..cam.model import Operation
    op = Operation.from_dict(d)
    detach(op)
    return op.to_dict()


def adopt(doc, op, active=None) -> bool:
    """Nouvelle opération : la prise et la cote de la surface où sont ses
    objets choisis (tous sur un même calque de surface), sinon — usinage par
    couleur — celles du calque actif `active` s'il est une surface."""
    ids = list(op.items or [])
    if not ids:
        return attach(doc, op, active) if active is not None else False
    where = _item_layers(doc)
    found = [where[i] for i in ids if i in where]
    if len(found) != len(ids) or len({id(L) for L in found}) != 1:
        return False
    return attach(doc, op, found[0])


def sync(doc, setup) -> int:
    """Rattachements tenus à jour : une opération dont tous les objets
    choisis sont sur un même calque de surface y est rattachée (`attach`) ;
    une opération rattachée dont les objets ont quitté son calque est défaite
    (`detach`). Usinée par couleur, elle reste à sa surface — sans rien
    usiner si celle-ci a disparu (`orphaned`), plutôt que d'usiner le dessin
    entier dans sa prise. Rend le nombre d'opérations changées."""
    has = any(of_layer(L) is not None for L in getattr(doc, 'layers', ()))
    where = _item_layers(doc) if has else {}
    n = 0
    for op in setup.operations:
        if not has and _record(op) is None:
            continue
        ids = list(op.items or [])
        if ids:
            found = [where.get(i) for i in ids]
            one = found[0] if all(f is not None for f in found) and len({id(f) for f in found}) == 1 else None
            target = one if one is not None and of_layer(one) is not None else None
        else:
            target = op_layer(doc, op)
            if target is None and _record(op) is not None:
                continue                               # surface disparue : rien usiné, rattachement gardé
        if target is None:
            n += int(detach(op))
        elif attach(doc, op, target):
            n += 1
    return n


def is_outline(item) -> bool:
    return bool((getattr(item, 'extra', None) or {}).get(OUTLINE))


def state(doc) -> tuple:
    """Empreinte des surfaces posées (calque, pose, placement gardé) : elle
    change quand une surface suit la pièce (`follow`) — les parcours calculés
    avant sont alors à refaire."""
    import json
    out = []
    for L in getattr(doc, 'layers', ()):
        d = of_layer(L)
        if d is not None:
            out.append((L.id, json.dumps({k: v for k, v in d.items() if k != 'faces'}, sort_keys=True, default=str)))
    return tuple(out)


def lost(doc) -> list:
    """Calques qui ont le contour d'une surface posée mais plus sa pose
    (document enregistré par une version qui ne gardait pas les données des
    calques, 0.523.0 à 0.527.0) : leur contenu serait usiné sur la prise du
    dessin, à Z 0."""
    return [L for L in getattr(doc, 'layers', ()) if of_layer(L) is None and any(is_outline(it) for it in L.items)]
