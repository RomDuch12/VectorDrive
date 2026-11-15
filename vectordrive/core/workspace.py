"""Espace de travail : la table de la machine et le matériel de serrage —
étaux, mandrins, brides, cales, blocs, montages importés en STEP / STL —
dessinés par l'utilisateur autour de la pièce, pour les voir dans la vue
3D, régler la prise dans les mors et vérifier que les parcours (outil et
porte-outil) ne les touchent pas.

Repère : celui de la FAO — X, Y du dessin, Z = 0 au haut de la pièce
(au-dessous : négatif). Chaque élément est posé en (x, y, z) — z : sa base
— et tourné de `rot` degrés autour de Z ; ses dimensions sont ses
paramètres (`KINDS`).

- **Étau** : mors serrant suivant son Y (tourné de 90° : suivant X),
  `opening` entre les mors, haut des mors à z + `height` ; cales
  parallèles éventuelles contre les mors.
- **Mandrin** : corps cylindrique, `jaws` mors radiaux serrant le
  diamètre `clamp`, haut des mors à z + `height` ; à quatre mors, la paire
  en X peut serrer une autre largeur (`clamp2` : brut rectangulaire).
- **Bride**, **cale**, **bloc**, **cylindre** : volumes simples ; **table** :
  rainures en T possibles (`slots`).
- **Machine** : table rainurée et portique (deux montants, une traverse à
  `clearance` au-dessus de la table) ; le portique est montré, pas vérifié
  (il passe au-dessus du travail).
- **Broche** : écrou de pince, nez et corps, à sa place pour la voir ; elle
  suit l'outil : vérifiée au-dessus du porte-outil (nez et corps contre le
  matériel), jamais comme une butée fixe.
- **Modèle importé** : un STEP ou un STL (étau du fabricant, montage…),
  centré en X, Y sur sa position, posé sur sa base.

Collisions (`collisions`) : le matériel vu de dessus en carte de hauteurs
(le plus haut point en chaque nœud) ; l'outil (son corps : un cône jusqu'à
sa queue) et le porte-outil (dépassement et diamètre connus) suivis le long
de chaque mouvement, avances et rapides : un point plus bas que le matériel
sous lui est une collision. Outil vertical (3 axes) : ce qui est sous un
surplomb du matériel compte comme plein.

Gardé avec le dessin (`Document.extra['workspace']`) ; chaque autre prise
(pièce retournée, corps posé seul) peut avoir le sien
(`Document.extra['workspaces']` {« face|corps » : espace}), dans le repère
de cette prise : la pièce tenue autrement pour usiner ses autres faces. Un
espace se garde aussi sous un nom (dossier `espaces_de_travail` des données) pour le
reprendre sur d'autres pièces. Les plugins ajoutent les leurs :
`api.add_templates('workspace', {nom: espace})`.
"""
from __future__ import annotations

import json
import math
import pathlib
import re
from dataclasses import dataclass, field

import numpy as np

KEY = 'workspace'
KEY_SETUPS = 'workspaces'           # les autres prises : {« face|corps » : espace}
SETUPS_KEY = 'prises3d'             # prises ajoutées à la main (vue 3D, « + Prise ») : [« face|corps »]
KIND = 'workspace'
#: natures : (libellé, paramètres [(clé, libellé, défaut)])
KINDS = {
    'etau': ('Étau', [('opening', 'Ouverture des mors (mm)', 60.0), ('jaw_w', 'Largeur des mors (mm)', 125.0),
                      ('jaw_h', 'Hauteur des mors (mm)', 40.0), ('jaw_t', 'Épaisseur des mors (mm)', 20.0),
                      ('height', 'Hauteur totale (mm)', 120.0), ('body_l', 'Longueur du corps (mm)', 400.0),
                      ('parallel', 'Hauteur des cales parallèles (mm, 0 = sans)', 0.0)]),
    'mandrin': ('Mandrin', [('diameter', 'Diamètre du corps (mm)', 160.0), ('height', 'Hauteur totale (mm)', 90.0),
                            ('jaws', 'Nombre de mors', 3.0), ('clamp', 'Diamètre serré (mm)', 40.0),
                            ('jaw_w', 'Largeur des mors (mm)', 20.0), ('jaw_l', 'Longueur des mors (mm)', 45.0),
                            ('jaw_h', 'Hauteur des mors (mm)', 30.0),
                            ('clamp2', '4 mors : largeur serrée en X (mm, 0 = la même)', 0.0)]),
    'bride': ('Bride', [('length', 'Longueur (mm)', 80.0), ('width', 'Largeur (mm)', 25.0),
                        ('height', 'Épaisseur (mm)', 15.0)]),
    'cale': ('Cale', [('sx', 'Longueur X (mm)', 100.0), ('sy', 'Largeur Y (mm)', 10.0), ('sz', 'Hauteur (mm)', 20.0)]),
    'bloc': ('Bloc', [('sx', 'Longueur X (mm)', 50.0), ('sy', 'Largeur Y (mm)', 50.0), ('sz', 'Hauteur (mm)', 50.0)]),
    'cylindre': ('Cylindre', [('diameter', 'Diamètre (mm)', 50.0), ('height', 'Hauteur (mm)', 50.0)]),
    'table': ('Table de la machine', [('sx', 'Longueur X (mm)', 800.0), ('sy', 'Largeur Y (mm)', 400.0),
                                      ('sz', 'Épaisseur (mm)', 40.0),
                                      ('slots', 'Rainures en T (nombre, 0 = table lisse)', 0.0),
                                      ('slot_w', 'Largeur des rainures (mm)', 14.0),
                                      ('slot_d', 'Profondeur des rainures (mm)', 12.0)]),
    'machine': ('Machine (table rainurée et portique)', [
        ('sx', 'Table : longueur X (mm)', 800.0), ('sy', 'Table : largeur Y (mm)', 600.0),
        ('sz', 'Table : épaisseur (mm)', 60.0), ('slots', 'Rainures en T (nombre)', 5.0),
        ('slot_w', 'Largeur des rainures (mm)', 14.0), ('slot_d', 'Profondeur des rainures (mm)', 12.0),
        ('clearance', 'Passage sous le portique (mm)', 250.0), ('frame', 'Portique montré (1 = oui, 0 = non)', 1.0)]),
    'broche': ('Broche', [('nut_d', 'Écrou de pince : Ø (mm)', 50.0), ('nut_l', 'Écrou de pince : hauteur (mm)', 25.0),
                          ('nose_d', 'Nez de broche : Ø (mm)', 80.0), ('nose_l', 'Nez de broche : hauteur (mm)', 40.0),
                          ('body_d', 'Corps : Ø (mm)', 120.0), ('body_l', 'Corps : hauteur (mm)', 260.0)]),
    'modele': ('Modèle 3D importé (STEP, STL)', [('scale', 'Échelle', 1.0)]),
}
#: prise minimale conseillée dans les mors (mm) et garde sous la passe la plus basse (mm)
MIN_GRIP, CLEARANCE = 3.0, 1.0
#: carte du matériel : nœuds au plus
MAX_CELLS = 4_000_000
#: segments d'un cylindre
SEGMENTS = 48
#: éléments qui suivent l'outil : montrés, jamais dans la carte du matériel fixe
MOBILE = ('broche',)
#: alignés sur les axes de la machine : ne tournent pas avec l'étau (fit_to_stock)
FIXED = ('table', 'machine', 'broche')
#: paramètres entiers (nombre de mors, de rainures, oui / non)
INTEGER = ('jaws', 'slots', 'frame')
#: portique d'une machine : largeur des montants, profondeur, hauteur de la traverse (mm)
FRAME_W, FRAME_D, BEAM_H = 90.0, 220.0, 140.0


@dataclass
class Element:
    kind: str = 'bloc'
    name: str = ''
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0                  # base de l'élément (repère FAO : haut de la pièce à 0)
    rot: float = 0.0                # degrés autour de Z
    params: dict = field(default_factory=dict)
    path: str = ''                  # modèle importé (STEP, STL)
    visible: bool = True

    def p(self, key: str) -> float:
        """Paramètre (sinon son défaut)."""
        spec = {k: d for k, _l, d in KINDS.get(self.kind, ('', []))[1]}
        try:
            return float(self.params.get(key, spec.get(key, 0.0)))
        except (TypeError, ValueError):
            return float(spec.get(key, 0.0))

    def label(self) -> str:
        return self.name or KINDS.get(self.kind, (self.kind,))[0]

    def to_dict(self) -> dict:
        d = {'kind': self.kind, 'name': self.name, 'x': self.x, 'y': self.y, 'z': self.z, 'rot': self.rot,
             'params': {k: float(v) for k, v in (self.params or {}).items()}}
        if self.path:
            d['path'] = self.path
        if not self.visible:
            d['visible'] = False
        return d

    @classmethod
    def from_dict(cls, d) -> 'Element':
        d = d if isinstance(d, dict) else {}
        e = cls(kind=str(d.get('kind', 'bloc')), name=str(d.get('name', '')), path=str(d.get('path', '')),
                visible=bool(d.get('visible', True)))
        if e.kind not in KINDS:
            e.kind = 'bloc'
        for k in ('x', 'y', 'z', 'rot'):
            try:
                setattr(e, k, float(d.get(k, 0.0) or 0.0))
            except (TypeError, ValueError):
                pass
        params = d.get('params') if isinstance(d.get('params'), dict) else {}
        for k, v in params.items():
            try:
                e.params[str(k)] = float(v)
            except (TypeError, ValueError):
                pass
        return e


@dataclass
class Workspace:
    name: str = ''
    description: str = ''
    elements: list = field(default_factory=list)
    #: '' : positions dans le repère FAO ; 'brut' : par rapport au brut (sans étau ni mandrin) —
    #: X, Y depuis son centre, Z depuis son dessous ; une bride : X, Y depuis le bord du brut du
    #: côté de leur signe (0 : au milieu), Z depuis son dessus
    origin: str = ''

    def to_dict(self) -> dict:
        d = {'name': self.name, 'description': self.description, 'elements': [e.to_dict() for e in self.elements]}
        if self.origin:
            d['origin'] = self.origin
        return d

    @classmethod
    def from_dict(cls, d) -> 'Workspace':
        d = d if isinstance(d, dict) else {}
        els = d.get('elements') if isinstance(d.get('elements'), list) else []
        return cls(str(d.get('name', '')), str(d.get('description', '')), [Element.from_dict(e) for e in els],
                   'brut' if d.get('origin') == 'brut' else '')


def setup_key(face: str = '', body: int = -1) -> str:
    return f'{face or ""}|{int(body)}'


def _parse_key(k) -> tuple[str, int] | None:
    face, sep, body = str(k).partition('|')
    try:
        return (face, int(body)) if sep else None
    except ValueError:
        return None


def extra_setups(doc) -> list[tuple[str, int]]:
    """Prises sans usinage qui existent quand même : ajoutées à la main
    (« + Prise » de la vue 3D), puis celles qui ont un espace de travail à
    elles ; [(face vers l'outil, corps)], faces ramenées à '' pour celle du
    dessin (`norm_face`), sans doublon ni la prise du dessin."""
    extra = getattr(doc, 'extra', {}) or {}
    keys = list(extra.get(SETUPS_KEY) or []) if isinstance(extra.get(SETUPS_KEY), list) else []
    keys += sorted(extra.get(KEY_SETUPS) or {}) if isinstance(extra.get(KEY_SETUPS), dict) else []
    out = []
    for k in keys:
        g = _parse_key(k)
        if g is not None:
            g = (norm_face(doc, g[0], None, g[1]), g[1])
            if g != ('', -1) and g not in out:
                out.append(g)
    return out


def declare(doc, face: str = '', body: int = -1) -> bool:
    """Prise (`face` vers l'outil, `body` seul) gardée avec le dessin, même
    sans usinage ; False : elle y était déjà."""
    g = (norm_face(doc, face, None, body), int(body))
    if g == ('', -1) or g in extra_setups(doc):
        return False
    have = doc.extra.get(SETUPS_KEY)
    doc.extra[SETUPS_KEY] = (list(have) if isinstance(have, list) else []) + [setup_key(*g)]
    return True


def undeclare(doc, face: str = '', body: int = -1) -> None:
    """Prise retirée de celles gardées avec le dessin, son espace de travail
    à elle aussi."""
    want = (norm_face(doc, face, None, body), int(body))

    def same(k) -> bool:
        g = _parse_key(k)
        return g is not None and (norm_face(doc, g[0], None, g[1]), g[1]) == want
    have = [k for k in (doc.extra.get(SETUPS_KEY) or []) if not same(k)] \
        if isinstance(doc.extra.get(SETUPS_KEY), list) else []
    if have:
        doc.extra[SETUPS_KEY] = have
    else:
        doc.extra.pop(SETUPS_KEY, None)
    m = {k: v for k, v in (doc.extra.get(KEY_SETUPS) or {}).items() if not same(k)} \
        if isinstance(doc.extra.get(KEY_SETUPS), dict) else {}
    if m:
        doc.extra[KEY_SETUPS] = m
    else:
        doc.extra.pop(KEY_SETUPS, None)


def drawing_face(doc, path: str | None = None, body: int = -1) -> str:
    """Face de la pièce `path` (None : celle du dessin) tournée vers l'outil
    dans le dessin : celle de son placement si c'est la pièce du dessin
    (celle du corps `body` s'il est positionné à part), sinon '+Z' (volumes
    du dessin, autre fichier) — comme `cam.mill3d.side_placement`."""
    from ..cam import mill3d
    from . import placement3d as P3
    if doc is None:
        return '+Z'
    if path is None:
        from ..io import model3d
        path = model3d.source_of(doc) or ''
    if not (path and mill3d._is_source(doc, path)):
        return '+Z'
    if int(body) >= 0:
        try:
            if int(body) >= mill3d.raw_model(path).body_count():
                body = -1                              # corps disparu du fichier : comme `side_placement`
        except Exception:                              # noqa: BLE001 — pièce illisible
            body = -1
    own = P3.body_of(doc, body)
    return ((own or P3.of(doc)).face or '+Z')


def norm_face(doc, face: str, path: str | None = None, body: int = -1) -> str:
    """'' pour la face du dessin (« dessus » d'une pièce posée comme le
    dessin : même prise, mêmes trajectoires — pour un corps positionné à
    part, la face de sa pose), la face sinon."""
    face = face or ''
    return '' if face and doc is not None and face == drawing_face(doc, path, body) else face


def op_setup(op, doc=None) -> tuple[str, int]:
    """(face vers l'outil, corps) de la prise d'une opération ; ('', -1) :
    celle du dessin (avec `doc` : la face du dessin aussi, `norm_face`)."""
    if op is None:
        return '', -1
    face = getattr(op, 'setup_face', '') or ''
    body = int(getattr(op, 'body3d', -1))
    if body >= 0 and doc is not None and getattr(op, 'body3d_ref', None):
        from ..cam import mill3d
        now = mill3d.op_body(doc, op)                  # volume du dessin gardé : son rang d'aujourd'hui
        body = body if now is None else now
    if face and doc is not None:
        from ..cam import mill3d
        face = norm_face(doc, face, mill3d.model_path(doc, op), body)
    return face, body


def pose_face(op, doc) -> str:
    """Face vers l'outil telle que la pièce — ou le corps positionné à part
    — est vraiment posée pour l'opération : celle de sa prise, sinon celle
    du dessin (de la pose propre du corps)."""
    face, body = op_setup(op, doc)
    if face or doc is None:
        return face or '+Z'
    from ..cam import mill3d
    return drawing_face(doc, mill3d.model_path(doc, op) or None, body)


def own(doc, face: str = '', body: int = -1) -> bool:
    """La prise a-t-elle un espace à elle (autre que celui du dessin) ?"""
    face = norm_face(doc, face, None, body)
    return (face, int(body)) != ('', -1) and isinstance(
        ((getattr(doc, 'extra', {}) or {}).get(KEY_SETUPS) or {}).get(setup_key(face, body)), dict)


def of(doc, face: str = '', body: int = -1) -> Workspace:
    """Espace de la prise (`face` vers l'outil, `body` seul) : le sien s'il
    en a un ; sinon, face du dessin, celui du dessin — vu du repère d'un
    corps usiné seul (haut du corps à Z 0) ; pièce retournée sans espace :
    aucun (elle n'est plus dans le même étau) ; corps positionné à part sans
    espace : aucun (il est tenu ailleurs)."""
    from . import placement3d as P3
    extra = getattr(doc, 'extra', {}) or {}
    face = norm_face(doc, face, None, body)
    if own(doc, face, body):
        return Workspace.from_dict(extra[KEY_SETUPS][setup_key(face, body)])
    if face or P3.body_of(doc, body) is not None:
        return Workspace()
    main = Workspace.from_dict(extra.get(KEY))
    return _in_body_frame(main, doc, int(body)) if int(body) >= 0 else main


def _in_body_frame(ws: Workspace, doc, body: int) -> Workspace:
    """L'espace du dessin dans le repère d'un corps usiné seul (son haut à
    Z 0, sa position selon le placement : `cam.reassemble.transform`) ;
    aucun si ce repère ne se calcule pas (pièce illisible, corps tourné)."""
    if not ws.elements:
        return ws
    import copy
    from ..cam import reassemble
    from ..cam.model import Operation
    tr = reassemble.transform(doc, Operation(kind='surface3d', body3d=body))
    if tr is None or not np.allclose(tr[0], np.eye(3), atol=1e-9):
        return Workspace()
    b = tr[1]
    out = copy.deepcopy(ws)
    for e in out.elements:
        e.x, e.y, e.z = e.x - float(b[0]), e.y - float(b[1]), e.z - float(b[2])
    return out


def store(doc, ws: Workspace, face: str = '', body: int = -1) -> None:
    """Espace gardé pour la prise (`face`, `body`) ; vide : retiré."""
    face = norm_face(doc, face, None, body)
    if (face, int(body)) == ('', -1):
        if ws.elements:
            doc.extra[KEY] = ws.to_dict()
        else:
            doc.extra.pop(KEY, None)
        return
    m = dict(doc.extra.get(KEY_SETUPS) or {})
    if ws.elements:
        m[setup_key(face, body)] = ws.to_dict()
    else:
        m.pop(setup_key(face, body), None)
    if m:
        doc.extra[KEY_SETUPS] = m
    else:
        doc.extra.pop(KEY_SETUPS, None)


# --- géométrie --------------------------------------------------------------------------------
def _table_parts(sx: float, sy: float, sz: float, slots: int, slot_w: float, slot_d: float) -> list[tuple]:
    """Table (centre en 0, 0, base à z 0) : un pavé, ou une semelle et des
    nervures entre `slots` rainures parallèles à X, régulièrement espacées en Y."""
    slots = max(0, int(round(slots)))
    slot_w = min(max(0.0, slot_w), sy / max(1, 2 * slots))
    slot_d = min(max(0.0, slot_d), sz * 0.8)
    if slots <= 0 or slot_w <= 0 or slot_d <= 0:
        return [('box', 0.0, 0.0, sx / 2, sy / 2, 0.0, 0.0, sz)]
    out = [('box', 0.0, 0.0, sx / 2, sy / 2, 0.0, 0.0, sz - slot_d)]
    pitch = sy / slots
    edges = [-sy / 2] + [-sy / 2 + pitch * (k + 0.5) + s * slot_w / 2 for k in range(slots) for s in (-1, 1)] + [sy / 2]
    for a, b in zip(edges[0::2], edges[1::2]):                # nervures entre les rainures
        if b - a > 1e-6:
            out.append(('box', 0.0, (a + b) / 2, sx / 2, (b - a) / 2, 0.0, sz - slot_d, sz))
    return out


def parts(el: Element, frame: bool = True) -> list[tuple]:
    """Volumes de l'élément dans son repère (centre en 0, 0, base à z 0) :
    ('box', cx, cy, demi-longueur, demi-largeur, angle °, z0, z1) ou
    ('cyl', cx, cy, rayon, z0, z1). `frame` faux : sans le portique d'une
    machine (vérifications)."""
    k = el.kind
    if k == 'machine':
        sx, sy, sz = el.p('sx'), el.p('sy'), el.p('sz')
        out = _table_parts(sx, sy, sz, el.p('slots'), el.p('slot_w'), el.p('slot_d'))
        if frame and el.p('frame') > 0:
            top = sz + el.p('clearance')
            xc = sx / 2 + FRAME_W / 2 + 20.0
            out += [('box', s * xc, 0.0, FRAME_W / 2, FRAME_D / 2, 0.0, 0.0, top + BEAM_H) for s in (-1, 1)]
            out.append(('box', 0.0, 0.0, xc + FRAME_W / 2, FRAME_D * 0.35, 0.0, top, top + BEAM_H))   # traverse
        return out
    if k == 'broche':
        nl, ol, bl = el.p('nut_l'), el.p('nose_l'), el.p('body_l')
        return [('cyl', 0.0, 0.0, el.p('nut_d') / 2, 0.0, nl), ('cyl', 0.0, 0.0, el.p('nose_d') / 2, nl, nl + ol),
                ('cyl', 0.0, 0.0, el.p('body_d') / 2, nl + ol, nl + ol + bl)]
    if k == 'etau':
        o, jw, jh, jt = el.p('opening'), el.p('jaw_w'), el.p('jaw_h'), el.p('jaw_t')
        H, bl, par = el.p('height'), el.p('body_l'), el.p('parallel')
        seat = max(0.0, H - jh)
        out = [('box', 0.0, 0.0, jw / 2, max(bl, o + 2 * jt) / 2, 0.0, 0.0, seat),       # corps
               ('box', 0.0, (o + jt) / 2, jw / 2, jt / 2, 0.0, seat, H),                # mors fixe
               ('box', 0.0, -(o + jt) / 2, jw / 2, jt / 2, 0.0, seat, H)]               # mors mobile
        if par > 0:                                                                    # cales contre les mors
            t = min(6.0, o / 4)
            out += [('box', 0.0, o / 2 - t / 2, jw / 2, t / 2, 0.0, seat, seat + par),
                    ('box', 0.0, -o / 2 + t / 2, jw / 2, t / 2, 0.0, seat, seat + par)]
        return out
    if k == 'mandrin':
        D, H, n = el.p('diameter'), el.p('height'), max(2, int(round(el.p('jaws'))))
        d, jw, jl, jh = el.p('clamp'), el.p('jaw_w'), el.p('jaw_l'), el.p('jaw_h')
        seat = max(0.0, H - jh)
        out = [('cyl', 0.0, 0.0, D / 2, 0.0, seat)]
        d2 = el.p('clamp2') if n == 4 and el.p('clamp2') > 0 else d
        for i in range(n):
            a = 90.0 + 360.0 * i / n
            rc = (d2 if i % 2 else d) / 2 + jl / 2           # 4 mors : les mors 1 et 3 serrent en X
            out.append(('box', rc * math.cos(math.radians(a)), rc * math.sin(math.radians(a)), jl / 2, jw / 2, a,
                        seat, H))
        return out
    if k == 'bride':
        return [('box', 0.0, 0.0, el.p('length') / 2, el.p('width') / 2, 0.0, 0.0, el.p('height'))]
    if k == 'table':
        return _table_parts(el.p('sx'), el.p('sy'), el.p('sz'), el.p('slots'), el.p('slot_w'), el.p('slot_d'))
    if k in ('cale', 'bloc'):
        return [('box', 0.0, 0.0, el.p('sx') / 2, el.p('sy') / 2, 0.0, 0.0, el.p('sz'))]
    if k == 'cylindre':
        return [('cyl', 0.0, 0.0, el.p('diameter') / 2, 0.0, el.p('height'))]
    return []


def _box_tris(cx, cy, hx, hy, ang, z0, z1) -> np.ndarray:
    a = math.radians(ang)
    c, s = math.cos(a), math.sin(a)
    corners = [(cx + px * c - py * s, cy + px * s + py * c) for px, py in ((-hx, -hy), (hx, -hy), (hx, hy), (-hx, hy))]
    lo = [(x, y, z0) for x, y in corners]
    up = [(x, y, z1) for x, y in corners]
    quads = [(lo[0], lo[3], lo[2], lo[1]), (up[0], up[1], up[2], up[3])]
    quads += [(lo[i], lo[(i + 1) % 4], up[(i + 1) % 4], up[i]) for i in range(4)]
    tris = []
    for q in quads:
        tris += [(q[0], q[1], q[2]), (q[0], q[2], q[3])]
    return np.asarray(tris, dtype=np.float64)


def _cyl_tris(cx, cy, r, z0, z1, n: int = SEGMENTS) -> np.ndarray:
    ring = [(cx + r * math.cos(2 * math.pi * k / n), cy + r * math.sin(2 * math.pi * k / n)) for k in range(n)]
    tris = []
    for k in range(n):
        (ax, ay), (bx, by) = ring[k], ring[(k + 1) % n]
        tris += [((cx, cy, z0), (bx, by, z0), (ax, ay, z0)), ((cx, cy, z1), (ax, ay, z1), (bx, by, z1)),
                 ((ax, ay, z0), (bx, by, z0), (bx, by, z1)), ((ax, ay, z0), (bx, by, z1), (ax, ay, z1))]
    return np.asarray(tris, dtype=np.float64)


_MODELS: dict = {}


def _model_tris(path: str) -> np.ndarray:
    """Triangles d'un modèle importé, gardés en mémoire (même fichier, même date)."""
    import os
    from ..io import model3d
    key = (os.path.normcase(os.path.abspath(path)), os.path.getmtime(path))
    t = _MODELS.get(key)
    if t is None:
        t = np.asarray(model3d.load(path).triangles, dtype=np.float64).reshape(-1, 3, 3)
        _MODELS[key] = t
        while len(_MODELS) > 8:
            _MODELS.pop(next(iter(_MODELS)))
    return t


def triangles(el: Element, frame: bool = True) -> np.ndarray:
    """Triangles (n, 3, 3) de l'élément posé (repère FAO) ; modèle illisible :
    aucun. `frame` faux : sans le portique d'une machine."""
    if el.kind == 'modele':
        if not el.path or not pathlib.Path(el.path).is_file():
            return np.zeros((0, 3, 3))
        try:
            t = _model_tris(el.path) * (el.p('scale') or 1.0)
        except Exception:                                  # noqa: BLE001 — fichier tiers
            return np.zeros((0, 3, 3))
        if not len(t):
            return t
        lo, hi = t.reshape(-1, 3).min(axis=0), t.reshape(-1, 3).max(axis=0)
        t = t - np.array([(lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, lo[2]])   # centré, posé sur sa base
    else:
        chunks = [(_box_tris(*q[1:]) if q[0] == 'box' else _cyl_tris(*q[1:])) for q in parts(el, frame)]
        t = np.concatenate(chunks) if chunks else np.zeros((0, 3, 3))
    return place(el, t)


def edges(el: Element) -> np.ndarray:
    """Arêtes (m, 2, 3) de l'élément posé : celles des pavés et cylindres
    (cercles et quatre génératrices) ; modèle importé : aucune."""
    segs = []
    for q in parts(el):
        if q[0] == 'box':
            _k, cx, cy, hx, hy, ang, z0, z1 = q
            a = math.radians(ang)
            c, s = math.cos(a), math.sin(a)
            pts = [(cx + px * c - py * s, cy + px * s + py * c) for px, py in ((-hx, -hy), (hx, -hy), (hx, hy), (-hx, hy))]
            ring = list(zip(pts, pts[1:] + pts[:1]))
            segs += [((p[0], p[1], z), (r[0], r[1], z)) for z in (z0, z1) for p, r in ring]
            segs += [((p[0], p[1], z0), (p[0], p[1], z1)) for p in pts]
        else:
            _k, cx, cy, r, z0, z1 = q
            ring = [(cx + r * math.cos(2 * math.pi * k / SEGMENTS), cy + r * math.sin(2 * math.pi * k / SEGMENTS))
                    for k in range(SEGMENTS + 1)]
            segs += [((p[0], p[1], z), (t[0], t[1], z)) for z in (z0, z1) for p, t in zip(ring, ring[1:])]
            segs += [((ring[k][0], ring[k][1], z0), (ring[k][0], ring[k][1], z1)) for k in range(0, SEGMENTS, SEGMENTS // 4)]
    return place(el, np.asarray(segs, dtype=np.float64).reshape(-1, 2, 3))


def place(el: Element, pts) -> np.ndarray:
    """Points (…, 3) du repère de l'élément → repère FAO."""
    a = np.asarray(pts, dtype=np.float64)
    r = math.radians(el.rot)
    c, s = math.cos(r), math.sin(r)
    out = np.empty_like(a)
    out[..., 0] = a[..., 0] * c - a[..., 1] * s + el.x
    out[..., 1] = a[..., 0] * s + a[..., 1] * c + el.y
    out[..., 2] = a[..., 2] + el.z
    return out


def local(el: Element, pts) -> np.ndarray:
    """Points (…, 3) du repère FAO → repère de l'élément."""
    a = np.asarray(pts, dtype=np.float64)
    r = math.radians(el.rot)
    c, s = math.cos(r), math.sin(r)
    dx, dy = a[..., 0] - el.x, a[..., 1] - el.y
    out = np.empty_like(a)
    out[..., 0] = dx * c + dy * s
    out[..., 1] = -dx * s + dy * c
    out[..., 2] = a[..., 2] - el.z
    return out


def jaw_top(el: Element) -> float | None:
    """Haut des mors (Z, repère FAO) d'un étau ou d'un mandrin."""
    return el.z + el.p('height') if el.kind in ('etau', 'mandrin') else None


# --- serrage ----------------------------------------------------------------------------------
def clamp_stock(el: Element, box, grip: float) -> Element:
    """Étau ou mandrin placé pour serrer le brut `box` (core.stock3d.StockBox)
    sur `grip` mm de haut : centré sur le brut, mors d'un étau sur ses deux
    grands côtés (ouverture = la largeur), mandrin serrant son diamètre ;
    haut des mors au bas du brut + `grip` ; cales d'un étau à la hauteur qui
    porte le brut."""
    import copy
    e = copy.deepcopy(el)
    cx, cy = box.center
    sx, sy = box.x1 - box.x0, box.y1 - box.y0
    e.x, e.y = cx, cy
    e.z = box.bottom + grip - e.p('height')
    if e.kind == 'etau':
        e.rot = 0.0 if sx >= sy else 90.0                  # mors serrant le côté étroit
        e.params['opening'] = round(min(sx, sy), 3)
        if e.p('parallel') > 0 or grip < e.p('jaw_h'):
            e.params['parallel'] = round(max(0.0, e.p('jaw_h') - grip), 3)
    elif e.kind == 'mandrin':
        if int(round(e.p('jaws'))) == 4:                   # mors indépendants : chaque paire sur son côté
            turned = 45.0 <= e.rot % 180.0 < 135.0         # mandrin tourné : ses mors « Y » serrent en X
            e.params['clamp'], e.params['clamp2'] = (round(sx, 3), round(sy, 3)) if turned else (round(sy, 3),
                                                                                                  round(sx, 3))
        else:
            e.params['clamp'] = round(min(sx, sy), 3)
    return e


def clamping(ws: Workspace) -> int:
    """Rang du premier étau ou mandrin montré (celui qui serre le brut), -1 : aucun."""
    return next((i for i, e in enumerate(ws.elements) if e.visible and e.kind in ('etau', 'mandrin')), -1)


def fit_to_stock(ws: Workspace, box, grip: float) -> Workspace:
    """Espace recalé sur le brut : son premier étau (ou mandrin) le serre
    (`clamp_stock`) et le reste le suit — cales, brides… : même
    déplacement, même rotation autour de lui ; table, machine et broche,
    alignées sur les axes de la machine : même déplacement sans tourner
    (l'étau tourne sur la table). Un espace gardé se replace ainsi sous
    chaque nouvelle pièce. Sans étau ni mandrin, un espace « par rapport au
    brut » (`origin` 'brut') est posé sur lui."""
    import copy
    out = copy.deepcopy(ws)
    k = clamping(out)
    if box is not None and k < 0 and out.origin == 'brut':
        cx, cy = box.center
        hx, hy = (box.x1 - box.x0) / 2, (box.y1 - box.y0) / 2
        for e in out.elements:
            if e.kind == 'bride':                          # depuis le bord : la bride appuie sur le brut
                e.x += math.copysign(hx, e.x) if abs(e.x) > 1e-9 else 0.0
                e.y += math.copysign(hy, e.y) if abs(e.y) > 1e-9 else 0.0
            e.x, e.y = e.x + cx, e.y + cy
            e.z += box.top if e.kind == 'bride' else box.bottom
        out.origin = ''
        return out
    if k < 0 or box is None:
        return out
    el = out.elements[k]
    new = clamp_stock(el, box, grip)
    dr = new.rot - el.rot
    c, s = math.cos(math.radians(dr)), math.sin(math.radians(dr))
    for i, e in enumerate(out.elements):
        if i == k:
            continue
        if e.kind in FIXED:
            e.x, e.y = e.x + new.x - el.x, e.y + new.y - el.y
        else:
            dx, dy = e.x - el.x, e.y - el.y
            e.x, e.y = new.x + dx * c - dy * s, new.y + dx * s + dy * c
            e.rot = (e.rot + dr) % 360.0
        e.z += new.z - el.z
    out.elements[k] = new
    return out


def auto_grip(el: Element, box, toolpaths, setup) -> tuple[float, list[str]]:
    """Prise proposée pour l'étau ou le mandrin `el` serrant le brut `box` :
    `grip_for` avec la coupe la plus basse près de ses mors une fois placé."""
    probe = clamp_stock(el, box, 0.0)
    return grip_for(box, deepest_near_jaws(probe, toolpaths, setup), probe.p('jaw_h'))


def jaw_floor(ws: Workspace) -> tuple[float, 'Element | None']:
    """Profondeur la plus basse (mm sous le haut de la pièce, > 0) où l'on
    peut usiner sans approcher les mors du premier étau (ou mandrin) à moins
    de CLEARANCE, et cet élément ; (0, None) : pas de limite (aucun, ou mors
    au-dessus du haut de la pièce : rien d'usinable)."""
    k = clamping(ws)
    if k < 0:
        return 0.0, None
    el = ws.elements[k]
    d = -(jaw_top(el) + CLEARANCE)
    return (round(d, 3), el) if d > 0 else (0.0, None)


def deepest_near_jaws(el: Element, toolpaths, setup, margin: float = 0.5) -> float | None:
    """Cote la plus basse (Z) des coupes qui passent près des mors de
    l'étau ou du mandrin `el` (à un rayon d'outil + `margin` de leur face) ;
    None : aucune."""
    low = None
    for tp in toolpaths:
        tool = setup.tool(tp.tool_id)
        if tool is None or not tp.moves:
            continue
        r = tool.body_diameter() / 2 + margin
        pts = np.array([(m.x, m.y, m.z) for m in tp.moves if m.kind != 'rapid'], dtype=np.float64)
        if not len(pts):
            continue
        q = local(el, pts)
        if el.kind == 'etau':
            near = (np.abs(q[:, 1]) >= el.p('opening') / 2 - r) & (np.abs(q[:, 0]) <= el.p('jaw_w') / 2 + r)
        elif el.kind == 'mandrin':
            d = el.p('clamp')
            if int(round(el.p('jaws'))) == 4 and el.p('clamp2') > 0:
                d = min(d, el.p('clamp2'))                 # 4 mors : la paire la plus serrée (côté sûr)
            near = np.hypot(q[:, 0], q[:, 1]) >= d / 2 - r
        else:
            return None
        if near.any():
            z = float(pts[near, 2].min())
            low = z if low is None else min(low, z)
    return low


def grip_for(box, deepest: float | None, jaw_h: float, min_grip: float = MIN_GRIP,
             clearance: float = CLEARANCE) -> tuple[float, list[str]]:
    """Prise dans les mors (mm) : le plus de serrage possible — au plus la
    hauteur des mors — sans que les mors montent à moins de `clearance` sous
    la coupe la plus basse près d'eux (`deepest`, Z ; None : aucune) ;
    avertissements si la prise reste sous `min_grip`."""
    from ..i18n import tr
    room = (deepest - clearance - box.bottom) if deepest is not None else box.height
    grip = max(0.0, min(jaw_h, room, box.height))
    out = []
    if grip < min_grip - 1e-9:
        out.append(tr('prise : {0} mm de brut seulement sous les coupes près des mors (garde de {1} mm comprise) — '
                      'moins que la prise minimale de {2} mm : usiner en deux prises, prendre un brut plus haut ou '
                      'des mors doux').format(_mm(max(0.0, room)), _mm(clearance), _mm(min_grip)))
    return round(grip, 3), out


def _mm(v: float) -> str:
    from ..i18n import decimal_sep
    return f'{v:.2f}'.rstrip('0').rstrip('.').replace('.', decimal_sep())


# --- collisions -------------------------------------------------------------------------------
@dataclass
class Hit:
    path: str                       # parcours
    what: str                       # 'outil' | 'porte-outil'
    element: str                    # élément touché
    x: float
    y: float
    z: float
    count: int                      # points en collision le long du parcours


def _grow_max(H, k: int):
    """Carte des hauteurs élargie de k nœuds (octogone proche du disque,
    un peu plus large : côté sûr) — le plus haut point à portée."""
    m = H.copy()
    for step in range(max(0, int(k))):
        g = m.copy()
        np.maximum(g[1:], m[:-1], out=g[1:])
        np.maximum(g[:-1], m[1:], out=g[:-1])
        np.maximum(g[:, 1:], m[:, :-1], out=g[:, 1:])
        np.maximum(g[:, :-1], m[:, 1:], out=g[:, :-1])
        if step % 2 == 0:
            np.maximum(g[1:, 1:], m[:-1, :-1], out=g[1:, 1:])
            np.maximum(g[:-1, :-1], m[1:, 1:], out=g[:-1, :-1])
            np.maximum(g[1:, :-1], m[:-1, 1:], out=g[1:, :-1])
            np.maximum(g[:-1, 1:], m[1:, :-1], out=g[:-1, 1:])
        m = g
    return m


def _rings(tool, holder: tuple[float, float], spindle: 'Element | None' = None) -> list[tuple[str, float, float]]:
    """Anneaux de contrôle d'un outil : (cause, rayon, hauteur au-dessus de
    la pointe) — le matériel à moins de `rayon` du centre ne doit pas monter
    plus haut que la pointe + `hauteur`. Un cône s'élargit avec la hauteur :
    quelques anneaux (côté sûr : chacun avec la hauteur de l'anneau
    précédent) ; puis le porte-outil au-dessus du dépassement, puis le nez et
    le corps de la broche `spindle` au-dessus de l'écrou (dépassement connu
    seulement)."""
    body = max(tool.body_diameter(), tool.diameter, 0.01) / 2
    out = []
    if tool.kind == 'conique' and 0 < tool.angle < 180:
        t = math.tan(math.radians(tool.angle) / 2)
        top = max(0.0, (body - tool.tip / 2) / t) if t > 1e-9 else 0.0
        hs = [top * k / 4 for k in range(5)]
        for ha, hb in zip(hs, hs[1:]):
            out.append(('outil', max(tool.radius_at(hb), tool.tip / 2, 0.01), ha))
        if not out:
            out.append(('outil', body, 0.0))
    else:
        out.append(('outil', body, 0.0))
    so, hd = holder
    if so > 0 and hd / 2 > 0:
        out.append(('porte-outil', hd / 2, so))
    if spindle is not None and so > 0:
        nose = so + spindle.p('nut_l')
        out += [('broche', max(hd, spindle.p('nut_d')) / 2, so),          # écrou de pince
                ('broche', spindle.p('nose_d') / 2, nose),
                ('broche', spindle.p('body_d') / 2, nose + spindle.p('nose_l'))]
    return out


def _samples(tp, step: float) -> np.ndarray:
    """Points du parcours (avances et rapides, arcs aplatis) tous les `step` mm au plus."""
    from ..cam.model import arc_points
    pts, prev = [], None
    for m in tp.moves:
        here = (m.x, m.y, m.z)
        if prev is not None and m.is_arc:
            pts.extend(arc_points(prev, m, min(0.02, step)))
        else:
            pts.append(here)
        prev = here
    P = np.asarray(pts, dtype=np.float64).reshape(-1, 3)
    if len(P) < 2:
        return P
    A, B = P[:-1], P[1:]
    k = np.maximum(1, np.ceil(np.hypot(B[:, 0] - A[:, 0], B[:, 1] - A[:, 1]) / step)).astype(np.int64)
    idx = np.repeat(np.arange(len(A)), k)
    f = (np.arange(int(k.sum())) - np.repeat(np.cumsum(k) - k, k)) / np.repeat(k, k)
    return np.vstack([A[idx] + (B[idx] - A[idx]) * f[:, None], P[-1:]])


def collisions(toolpaths, setup, ws: Workspace, res: float = 0.5, tol: float = 0.05,
               only: tuple | None = None, doc=None) -> list[Hit]:
    """Parcours qui touchent le matériel de l'espace de travail : un point
    du parcours (avances et rapides, tous les res / 2) plus bas que le
    matériel à portée de l'outil (son corps) ou du porte-outil (au-dessus
    du dépassement). Un résultat par parcours et par cause, au premier point.
    `only` (face, corps) : les parcours de cette prise seulement ; None :
    ceux de la face du dessin (`ws` est l'espace de la première prise) ;
    `doc` : la face du dessin reconnue (`norm_face`)."""
    from ..cam.advanced import heightmap_from_triangles
    from ..cam.model import holder_of
    from ..core import progress
    shown = [(e, triangles(e, frame=False)) for e in ws.elements if e.visible and e.kind not in MOBILE]
    shown = [(e, t) for e, t in shown if len(t)]
    spindle = next((e for e in ws.elements if e.visible and e.kind == 'broche'), None)
    ops = {o.id: o for o in getattr(setup, 'operations', [])}
    live = []
    for tp in toolpaths:
        tool = setup.tool(tp.tool_id)
        op = ops.get(tp.op_id)
        k = op_setup(op, doc)
        mine = k == tuple(only) if only is not None else not k[0]
        if tp.moves and tool is not None and tool.kind != 'laser' and mine:
            live.append((tp, _rings(tool, holder_of(tool, setup), spindle)))
    if not shown or not live:
        return []
    allt = np.concatenate([t for _e, t in shown])
    lo, hi = allt.reshape(-1, 3).min(axis=0), allt.reshape(-1, 3).max(axis=0)
    margin = max(r for _tp, rings in live for _w, r, _h in rings) + 2 * res
    w, h = hi[0] - lo[0] + 2 * margin, hi[1] - lo[1] + 2 * margin
    res = max(res, math.sqrt(w * h / MAX_CELLS))
    x0, y0 = lo[0] - margin, lo[1] - margin
    nx, ny = int(math.ceil(w / res)) + 1, int(math.ceil(h / res)) + 1
    H = np.full((ny, nx), -np.inf)
    owner = np.full((ny, nx), -1, dtype=np.int64)
    for i, (_e, t) in enumerate(shown):
        He = heightmap_from_triangles(t, x0, y0, nx, ny, res)
        up = He > H
        H[up], owner[up] = He[up], i
    top = float(hi[2])
    grown: dict = {}

    def grow(k):
        if k not in grown:
            grown[k] = _grow_max(H, k)
        return grown[k]
    hits = []
    for n, (tp, rings) in enumerate(live):
        progress.step(n, len(live), 'Espace de travail : parcours {0} sur {1}')
        P = _samples(tp, res / 2)
        P = P[P[:, 2] <= top + tol]                    # au-dessus du matériel : rien à toucher
        if not len(P):
            continue
        i = np.clip(np.round((P[:, 0] - x0) / res).astype(np.int64), 0, nx - 1)
        j = np.clip(np.round((P[:, 1] - y0) / res).astype(np.int64), 0, ny - 1)
        bads: dict = {}
        for what, r, dz in rings:
            k = int(math.ceil(max(r, res / 2) / res))
            bad = grow(k)[j, i] > P[:, 2] + dz + tol
            reach = max(bads.get(what, (None, 0))[1], k)
            bads[what] = ((bads[what][0] | bad) if what in bads else bad, reach)
        for what, (bad, k) in bads.items():
            if not bad.any():
                continue
            q = int(np.flatnonzero(bad)[0])
            oi = _owner_near(owner, H, int(j[q]), int(i[q]), k)
            name = shown[oi][0].label() if oi >= 0 else ''
            hits.append(Hit(tp.name or 'parcours', what, name, float(P[q, 0]), float(P[q, 1]), float(P[q, 2]),
                            int(bad.sum())))
    return hits


def collisions_all(toolpaths, setup, doc) -> list[Hit]:
    """Collisions de toutes les prises : les parcours de chacune contre son
    espace de travail (`of`), dans son repère."""
    hits = []
    for face, body in _keys(toolpaths, setup, doc):
        ws = of(doc, face, body)
        if ws.elements:
            hits += collisions(toolpaths, setup, ws, only=(face, body), doc=doc)
    return hits


def _keys(toolpaths, setup, doc) -> list:
    """Prises des parcours qui coupent (outil connu, pas laser), dans l'ordre."""
    ops = {o.id: o for o in getattr(setup, 'operations', [])}
    keys = []
    for tp in toolpaths:
        tool = setup.tool(tp.tool_id)
        if not tp.moves or tool is None or tool.kind == 'laser':
            continue
        k = op_setup(ops.get(tp.op_id), doc)
        if k not in keys:
            keys.append(k)
    return keys


def setup_label(face: str, body: int) -> str:
    """« corps 2, dessous »… ; « comme le dessin » pour la première prise."""
    from ..cam.auto3d import SIDE_LABELS
    bits = [b for b in (f'corps {body + 1}' if body >= 0 else '', SIDE_LABELS.get(face, face) if face else '')
            if b]
    return ', '.join(bits) or SIDE_LABELS['']


def unchecked(toolpaths, setup, doc) -> list[str]:
    """Ce que `collisions_all` ne peut pas vérifier, quand le dessin a un
    espace de travail : prises sans matériel (pièce retournée sans le sien,
    repère d'un corps inconnu), broche sans dépassement d'outil connu."""
    from ..cam.model import holder_of
    extra = getattr(doc, 'extra', {}) or {}
    if not (extra.get(KEY) or extra.get(KEY_SETUPS)):
        return []
    ops = {o.id: o for o in getattr(setup, 'operations', [])}
    out = []
    for face, body in _keys(toolpaths, setup, doc):
        ws = of(doc, face, body)
        if not ws.elements:
            out.append(f'prise « {setup_label(face, body)} » sans matériel : ses parcours ne sont pas vérifiés')
            continue
        if any(e.visible and e.kind == 'broche' for e in ws.elements):
            names = []
            for tp in toolpaths:
                tool = setup.tool(tp.tool_id)
                if tool is None or not tp.moves or op_setup(ops.get(tp.op_id), doc) != (face, body):
                    continue
                if holder_of(tool, setup)[0] <= 0 and tool.name not in names:
                    names.append(tool.name or '?')
            if names:
                out.append(f'broche non vérifiée pour {", ".join(names)} (dépassement hors pince inconnu)')
    return out


def _owner_near(owner, H, j: int, i: int, k: int) -> int:
    """Élément le plus haut à portée (k nœuds) du nœud (j, i)."""
    j0, j1, i0, i1 = max(0, j - k), j + k + 1, max(0, i - k), i + k + 1
    sub = H[j0:j1, i0:i1]
    if not sub.size or not np.isfinite(sub).any():
        return -1
    q = np.unravel_index(int(np.argmax(sub)), sub.shape)
    return int(owner[j0 + q[0], i0 + q[1]])


def hit_text(h: Hit) -> str:
    from ..i18n import tr
    who = {'porte-outil': tr('le porte-outil'), 'broche': tr('la broche')}.get(h.what, tr('l\'outil'))
    return tr('« {0} » : {1} touche « {2} » en X {3} Y {4} Z {5} ({6} point(s))').format(
        h.path, who, h.element, _mm(h.x), _mm(h.y), _mm(h.z), h.count)


# --- espaces gardés ---------------------------------------------------------------------------
def builtin() -> dict[str, Workspace]:
    """Espaces livrés, exemples à reprendre : chargés, modifiés puis
    enregistrés sous un autre nom (dimensions à ajuster à son matériel). Le
    premier étau ou mandrin serre le brut, le reste le suit."""
    vise = Element('etau', 'Étau', z=-120.0)
    machine = [vise, Element('machine', 'Machine à portique', z=-180.0),
               Element('broche', 'Broche', z=60.0)]
    small = Element('etau', 'Étau de 80 mm', z=-90.0, params={'jaw_w': 80.0, 'jaw_h': 30.0, 'jaw_t': 16.0,
                                                               'height': 90.0, 'body_l': 260.0})
    four = Element('mandrin', 'Mandrin 4 mors', z=-80.0, params={'diameter': 125.0, 'height': 80.0, 'jaws': 4.0,
                                                                  'jaw_w': 16.0, 'jaw_l': 36.0, 'jaw_h': 25.0})
    table = Element('table', 'Table rainurée', z=-50.0, params={'sx': 600.0, 'sy': 400.0, 'sz': 50.0,
                                                                  'slots': 4.0})
    ws = [Workspace('Étau de 125 mm', 'Étau à mors de 125 mm, ouverture réglée sur le brut',
                    [Element('etau', 'Étau')]),
          Workspace('Mandrin 3 mors Ø 160', 'Mandrin trois mors, serrage réglé sur le brut',
                    [Element('mandrin', 'Mandrin')]),
          Workspace('Machine à portique et étau', 'Table rainurée de 800 × 600, portique, étau de 125 mm, broche',
                    machine),
          Workspace('Étau de 80 mm sur table', 'Petit étau sur une table rainurée',
                    [small, Element('table', 'Table', z=-130.0, params={'sx': 500.0, 'sy': 300.0, 'sz': 40.0,
                                                                        'slots': 3.0})]),
          Workspace('Mandrin 4 mors Ø 125', 'Mandrin quatre mors indépendants (pièces carrées)', [four]),
          Workspace('Table rainurée et brides', 'Brut posé sur la table, tenu par deux brides à ses extrémités',
                    [table] + [Element('bride', 'Bride', x=s * 30.0) for s in (-1, 1)],   # 10 mm sur le brut
                    origin='brut')]
    return {w.name: w for w in ws}


# --- STEP ---------------------------------------------------------------------------------------
#: couleurs des volumes dans un STEP (comme la vue 3D)
STEP_COLORS = {'table': (0.36, 0.38, 0.42), 'machine': (0.36, 0.38, 0.42), 'etau': (0.52, 0.60, 0.70),
               'mandrin': (0.52, 0.60, 0.70), 'broche': (0.80, 0.80, 0.82)}


def step_solids(el: Element) -> list[dict]:
    """Volumes de l'élément posé pour `io.step_solids` (pavés tournés,
    cylindres) ; modèle importé : aucun (il a déjà son fichier)."""
    out = []
    color = STEP_COLORS.get(el.kind, (0.62, 0.62, 0.56))
    for q in parts(el):
        if q[0] == 'box':
            _k, cx, cy, hx, hy, ang, z0, z1 = q
            a = math.radians(ang)
            c, s = math.cos(a), math.sin(a)
            pts = [(cx + px * c - py * s, cy + px * s + py * c, 0.0) for px, py in ((-hx, -hy), (hx, -hy), (hx, hy),
                                                                                  (-hx, hy))]
            P = place(el, pts)
            out.append({'kind': 'box', 'corners': [(float(p[0]), float(p[1])) for p in P], 'z0': z0 + el.z,
                        'z1': z1 + el.z, 'name': el.label(), 'color': color})
        else:
            _k, cx, cy, r, z0, z1 = q
            p = place(el, [(cx, cy, 0.0)])[0]
            out.append({'kind': 'cyl', 'cx': float(p[0]), 'cy': float(p[1]), 'r': r, 'z0': z0 + el.z,
                        'z1': z1 + el.z, 'name': el.label(), 'color': color})
    return out


def to_step(ws: Workspace, path: str, centered: bool = False) -> int:
    """Les éléments montrés de `ws` en STEP (`path`), à leur place (repère
    FAO) ; `centered` : un élément seul ramené au centre, base à Z 0 (à
    réimporter comme modèle). Rend le nombre de volumes écrits."""
    import copy
    from ..io import step_solids as SS
    sols = []
    for e in ws.elements:
        if not e.visible:
            continue
        if centered:
            e = copy.deepcopy(e)
            e.x = e.y = e.z = 0.0
        sols += step_solids(e)
    SS.write(path, sols, ws.name or 'espace')
    return len(sols)


def _example_stock():
    """Brut des exemples écrits en STEP : 60 × 40 × 20, haut à Z 0."""
    from .stock3d import StockBox
    return StockBox(-30.0, -20.0, 30.0, 20.0, 0.0, -20.0)


def write_examples(folder) -> list[pathlib.Path]:
    """Exemples en STEP dans `folder` : chaque espace livré (à sa place) et
    chaque matériel seul (centré, base à Z 0) — étau, mandrins, broche,
    machine, table — à ouvrir et modifier dans un logiciel de CAO, puis à
    réimporter comme « Modèle 3D importé ». Rend les fichiers écrits."""
    folder = pathlib.Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    out = []
    seen = set()
    for name, w in builtin().items():
        f = folder / f'{ascii_stem(name)}.step'
        to_step(fit_to_stock(w, _example_stock(), 5.0), str(f))
        out.append(f)
        for e in w.elements:
            key = (e.kind, json.dumps(e.params, sort_keys=True))
            if key in seen:
                continue
            seen.add(key)
            g = folder / f'materiel_{ascii_stem(e.label())}.step'
            to_step(Workspace(e.label(), '', [e]), str(g), centered=True)
            out.append(g)
    return out


def ascii_stem(name: str) -> str:
    """Nom de fichier sans accents ni signes (« Mandrin 3 mors Ø 160 » →
    « Mandrin_3_mors_D160 »)."""
    import unicodedata
    t = unicodedata.normalize('NFKD', str(name).replace('Ø ', 'D').replace('Ø', 'D'))
    t = ''.join(ch for ch in t if ord(ch) < 128)
    return re.sub(r'[^A-Za-z0-9.-]+', '_', t).strip('_') or 'espace'


def user_dir() -> pathlib.Path:
    """Dossier des espaces de l'utilisateur : `espaces_de_travail`, à côté
    des modèles d'usinage (dossier des essais pendant les essais)."""
    import os
    env = os.environ.get('VECTORDRIVE_WORKSPACES')
    if env:
        return pathlib.Path(env)
    from ..cam import templates
    return templates.user_dir().parent / 'espaces_de_travail'


def _file(name: str) -> pathlib.Path:
    stem = re.sub(r'[^\w.-]+', '_', name, flags=re.UNICODE).strip('_') or 'espace'
    return user_dir() / f'{stem}.json'


def user_workspaces() -> dict[str, Workspace]:
    out = {}
    d = user_dir()
    if d.is_dir():
        for f in sorted(d.glob('*.json')):
            try:
                data = json.loads(f.read_text(encoding='utf-8'))
            except (OSError, ValueError):
                continue
            if isinstance(data, dict) and data.get('name') and isinstance(data.get('elements'), list):
                out[str(data['name'])] = Workspace.from_dict(data)
    return out


def plugin_workspaces() -> dict[str, Workspace]:
    from ..plugins import REGISTRY
    out = {}
    for name, d in (REGISTRY.templates.get(KIND) or {}).items():
        if isinstance(d, dict):
            d = {**d, 'name': d.get('name') or name}
            out[str(d['name'])] = Workspace.from_dict(d)
    return out


def all_workspaces() -> dict[str, tuple[str, Workspace]]:
    """{nom: (origine 'cœur' | 'plugin' | 'utilisateur', espace)} ; celui de
    l'utilisateur remplace celui du même nom."""
    out = {n: ('cœur', w) for n, w in builtin().items()}
    out.update({n: ('plugin', w) for n, w in plugin_workspaces().items()})
    out.update({n: ('utilisateur', w) for n, w in user_workspaces().items()})
    return out


def save_user(ws: Workspace) -> pathlib.Path:
    if not ws.name:
        raise ValueError('espace de travail sans nom')
    f = _file(ws.name)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(ws.to_dict(), ensure_ascii=False, indent=1), encoding='utf-8')
    return f


def delete_user(name: str) -> bool:
    f = _file(name)
    if f.is_file():
        f.unlink()
        return True
    return False
