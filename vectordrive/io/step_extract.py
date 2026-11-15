"""Corps d'un STEP recopiés dans d'autres STEP, géométrie exacte : les
entités de chaque corps (solide, coques, faces, arêtes, courbes, surfaces)
reprises telles quelles et renumérotées, la place de la pièce dans
l'assemblage appliquée aux points et aux directions ; noms, couleurs et
unités du fichier gardés.

- `bodies(path)` : les corps du fichier, dans l'ordre du lecteur 3D
  (`Model3D.body_names`) ;
- `extract(path, picks, out)` : des corps dans un fichier ; `split(path,
  folder)` : un fichier par corps (un moule en trois parties : trois STEP) ;
- `combine(parts, out)` : des corps de plusieurs fichiers, chacun déplacé
  (rotation, translation), en une seule pièce.

Un déplacement est un placement rigide (rotation, sans miroir) : les axes
omis des repères (« $ », valeurs par défaut de la norme) sont écrits avant
d'être tournés ; les coordonnées et normales en ligne des corps maillés
(AP242 : COORDINATES_LIST, TRIANGULATED_FACE…) sont déplacées aussi.
"""
from __future__ import annotations

import math
import pathlib
import re
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime

import numpy as np

REF = re.compile(r'#(\d+)')
NUM = re.compile(r'[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?')
#: noms de fichiers réservés de Windows
RESERVED = {'CON', 'PRN', 'AUX', 'NUL'} | {f'COM{i}' for i in range(1, 10)} | {f'LPT{i}' for i in range(1, 10)}
#: entités maillées dont les normales en ligne (4e argument) tournent avec la pièce
TESSELLATED_NORMALS = ('TRIANGULATED_FACE', 'COMPLEX_TRIANGULATED_FACE', 'TRIANGULATED_SURFACE_SET',
                       'COMPLEX_TRIANGULATED_SURFACE_SET')


class ExtractError(ValueError):
    pass


def split_entities(text: str) -> dict:
    """{numéro : texte de l'entité sans « #n= » ni « ; »} de la section DATA (instructions lues une à une
    depuis le début, chaînes et commentaires respectés : « DATA ; » reconnu, un « DATA; » dans une chaîne de
    l'en-tête non)."""
    out = {}
    n = len(text)
    i = 0
    buf = []
    in_str = in_data = found = False
    while i < n:
        c = text[i]
        if in_str:
            buf.append(c)
            if c == "'":
                if i + 1 < n and text[i + 1] == "'":
                    buf.append("'")
                    i += 1
                else:
                    in_str = False
        elif c == "'":
            in_str = True
            buf.append(c)
        elif c == '/' and text.startswith('/*', i):
            j = text.find('*/', i + 2)
            i = n if j < 0 else j + 1
        elif c == ';':
            stmt = ''.join(buf).strip()
            buf = []
            if not in_data:
                if re.fullmatch(r'DATA\s*(\(.*\))?', stmt, re.S):
                    in_data = found = True
            elif stmt == 'ENDSEC':
                in_data = False
            else:
                m = re.match(r'#(\d+)\s*=\s*', stmt)
                if m:
                    out[int(m.group(1))] = stmt[m.end():]
        elif c in '\r\n':
            buf.append(' ')
        else:
            buf.append(c)
        i += 1
    if not found:
        raise ExtractError('pas de section DATA')
    return out


def _outside_strings(raw: str):
    """Morceaux (texte, dans une chaîne ?) de l'entité."""
    parts = re.split(r"('(?:[^']|'')*')", raw)
    return [(p, k % 2 == 1) for k, p in enumerate(parts)]


def refs_of(raw: str) -> list:
    return [int(m) for p, s in _outside_strings(raw) if not s for m in REF.findall(p)]


def renumber(raw: str, mapping: dict) -> str:
    """Références renumérotées ; une référence vers une entité absente du fichier devient « $ »."""
    def sub(m):
        k = mapping.get(int(m.group(1)))
        return f'#{k}' if k is not None else '$'
    return ''.join(p if s else REF.sub(sub, p) for p, s in _outside_strings(raw))


def closure(ents: dict, roots) -> list:
    """Les entités atteintes depuis `roots` (références suivies), dans l'ordre de la recherche."""
    seen, order = set(), []
    q = deque(int(r) for r in roots)
    while q:
        k = q.popleft()
        if k in seen or k not in ents:
            continue
        seen.add(k)
        order.append(k)
        q.extend(refs_of(ents[k]))
    return order


def _type(raw: str) -> str:
    m = re.match(r'\s*([A-Z_0-9]+)\s*\(', raw)
    return m.group(1) if m else ''


def _args(raw: str) -> tuple:
    """(début « TYPE( », [arguments de premier niveau], fin « ) ») d'une entité simple (chaînes et
    parenthèses respectées)."""
    i, j = raw.find('('), raw.rfind(')')
    body = raw[i + 1:j]
    out, cur, depth, in_str = [], [], 0, False
    k = 0
    while k < len(body):
        c = body[k]
        if in_str:
            cur.append(c)
            if c == "'":
                if k + 1 < len(body) and body[k + 1] == "'":
                    cur.append("'")
                    k += 1
                else:
                    in_str = False
        elif c == "'":
            in_str = True
            cur.append(c)
        elif c == ',' and depth == 0:
            out.append(''.join(cur).strip())
            cur = []
        else:
            depth += (c == '(') - (c == ')')
            cur.append(c)
        k += 1
    out.append(''.join(cur).strip())
    return raw[:i + 1], out, raw[j:]


@dataclass
class BodyRef:
    """Un corps du fichier : son élément de forme, sa place (R 3×3, t en mm) et son contexte."""
    name: str
    item: int
    R: np.ndarray
    t: np.ndarray
    context: int | None
    faces: int = 0
    extra: dict = field(default_factory=dict)


def bodies(path) -> list:
    """Les corps du fichier (un par solide de chaque pièce placée), dans l'ordre du lecteur 3D."""
    from .neostep import step3d as S
    text = pathlib.Path(path).read_text(encoding='latin-1')
    mod = S._Modele(S.lire_entites(text))
    mod.f = mod.unite()
    angle = S._unite_angle(mod)
    insts = S.instances(mod)
    ctx_of = {}
    for n, ent in mod.e.items():
        for t in S._types(ent):
            if t.endswith('REPRESENTATION') and 'SHAPE' in t:
                a = S._partie(ent, t)
                if not (a and len(a) >= 3 and isinstance(a[1], list)) and ent[0] == '*' \
                        and 'REPRESENTATION' in ent[1]:
                    a = ent[1]['REPRESENTATION']          # complexe : les arguments sont dans REPRESENTATION
                if a and len(a) >= 3 and isinstance(a[1], list) and isinstance(a[2], S.Ref):
                    for r in a[1]:
                        if isinstance(r, S.Ref):
                            ctx_of.setdefault(int(r), int(a[2]))
                break
    noms: list = []
    S.corps_des_faces(mod, insts, noms)             # mêmes noms, même ordre que le lecteur
    out = []
    for inst in insts:
        for r in inst.items:
            if not isinstance(r, S.Ref):
                continue
            faces, _c = S.faces_et_courbes(mod, [r], inst.T)
            if not faces:
                continue
            R, t = inst.T if inst.T is not None else S.IDENTITE
            name = noms[len(out)] if len(out) < len(noms) else f'Corps {len(out) + 1}'
            out.append(BodyRef(name, int(r), np.asarray(R, float), np.asarray(t, float), ctx_of.get(int(r)),
                               len(faces), {'unit_mm': mod.f, 'angle': angle}))
    return out


def _f(x: float) -> str:
    x = float(x)
    if abs(x) < 1e-12:
        return '0.'
    s = f'{x:.10f}'.rstrip('0')
    return s if not s.endswith('.') else s


def _move_points(raw: str, R, t, scale: float, kind: str) -> str:
    """CARTESIAN_POINT déplacé (t en mm, coordonnées du fichier à `scale` mm l'unité), DIRECTION tournée."""
    m = re.match(r"(\s*[A-Z_]+\s*\(\s*'(?:[^']|'')*'\s*,\s*\()([^)]*)(\).*)$", raw, re.S)
    if not m:
        return raw
    vals = [float(x) for x in NUM.findall(m.group(2))]
    if len(vals) != 3:                                  # point 2D (courbe de paramètres) : laissé tel quel
        return raw
    v = R @ np.array(vals) + (t / scale if kind == 'CARTESIAN_POINT' else 0.0)
    return m.group(1) + ','.join(_f(x) for x in v) + m.group(3)


def _move_tuples(text: str, R, shift) -> str:
    """Chaque triplet « (x,y,z) » de `text` déplacé (R·v + shift) ; les autres laissés."""
    def sub(m):
        vals = [float(x) for x in NUM.findall(m.group(1))]
        if len(vals) != 3:
            return m.group(0)
        return '(' + ','.join(_f(x) for x in R @ np.array(vals) + shift) + ')'
    return re.sub(r'\(([^()]*)\)', sub, text)


def _move_tessellated(raw: str, R, t, scale: float) -> str:
    """Coordonnées en ligne (COORDINATES_LIST) déplacées, normales en ligne des faces maillées tournées."""
    kind = _type(raw)
    head, a, tail = _args(raw)
    if kind == 'COORDINATES_LIST' and len(a) >= 3:
        a[2] = _move_tuples(a[2], R, t / scale)
    elif kind in TESSELLATED_NORMALS and len(a) >= 4:
        a[3] = _move_tuples(a[3], R, np.zeros(3))
    return head + ','.join(a) + tail


def _vector(ents: dict, ref: str, default) -> np.ndarray:
    m = REF.fullmatch(ref.strip())
    if m and int(m.group(1)) in ents:
        vals = [float(x) for x in NUM.findall(_args(ents[int(m.group(1))])[1][-1])]
        if len(vals) == 3:
            return np.array(vals) / (np.linalg.norm(vals) or 1.0)
    return np.array(default, float)


def _explicit_axes(ents: dict, order: list) -> tuple:
    """Axes omis (« $ ») des repères rendus explicites avant une rotation : ({numéro : texte modifié},
    {nouveau numéro : DIRECTION}). Axe d'un repère : (0, 0, 1) ; direction de référence : first_proj_axis de la
    norme (X projeté sur le plan de l'axe ; Z si l'axe est X)."""
    over, new = {}, {}
    nxt = max(ents) + 1

    def add(v) -> str:
        nonlocal nxt
        new[nxt] = f"DIRECTION('',({','.join(_f(x) for x in v)}))"
        nxt += 1
        return f'#{nxt - 1}'
    for k in order:
        raw = ents[k]
        kind = _type(raw)
        if kind not in ('AXIS2_PLACEMENT_3D', 'AXIS1_PLACEMENT') or '$' not in raw:
            continue
        head, a, tail = _args(raw)
        if len(a) < 3:
            continue
        z = _vector(ents, a[2], (0.0, 0.0, 1.0))
        if a[2] == '$':
            a[2] = add(z)
        if kind == 'AXIS2_PLACEMENT_3D' and len(a) >= 4 and a[3] == '$':
            v = np.array((1.0, 0.0, 0.0)) if abs(abs(float(z[0])) - 1.0) > 1e-9 else np.array((0.0, 0.0, 1.0))
            x = v - (v @ z) * z
            a[3] = add(x / (np.linalg.norm(x) or 1.0))
        over[k] = head + ','.join(a) + tail
    return over, new


def _styles_index(ents: dict) -> dict:
    """{élément coloré : [numéros des STYLED_ITEM]} ; OVER_RIDING_STYLED_ITEM : l'élément est son 3e argument."""
    out: dict = {}
    for k, raw in ents.items():
        kind = _type(raw)
        if kind in ('STYLED_ITEM', 'OVER_RIDING_STYLED_ITEM'):
            a = _args(raw)[1]
            m = REF.fullmatch(a[2].strip()) if len(a) >= 3 else None
            if m:
                out.setdefault(int(m.group(1)), []).append(k)
    return out


class _Out:
    def __init__(self):
        self.lines: list = []

    def add(self, raw: str) -> int:
        self.lines.append(raw)
        return len(self.lines)


def _ascii(text: str) -> str:
    import unicodedata
    t = unicodedata.normalize('NFKD', str(text))
    return ''.join(ch for ch in t if 32 <= ord(ch) < 127 and ch not in "'\\")


def _rigid(R) -> bool:
    R = np.asarray(R, float)
    return R.shape == (3, 3) and np.allclose(R.T @ R, np.eye(3), atol=1e-6) and np.linalg.det(R) > 0


def write_bodies(sources: list, out_path, name: str = '', description: str = 'VectorDrive',
                 cache: dict | None = None) -> str:
    """Écrit `sources` [(entités du fichier, BodyRef, (R, t) en plus ou None)…] dans un STEP ; rend le chemin.
    `cache` : un dictionnaire gardé d'un appel à l'autre sur les mêmes entités (index des styles)."""
    if not sources:
        raise ExtractError('aucun corps')
    units = {round(float(b.extra.get('unit_mm', 1.0)), 9) for _e, b, _m in sources}
    if len(units) > 1:
        raise ExtractError('fichiers en unités de longueur différentes (mm et pouces) : à réunir un par un')
    angles = {round(float(b.extra.get('angle', 1.0)), 12) for _e, b, _m in sources}
    if len(angles) > 1:
        raise ExtractError('fichiers en unités d\'angle différentes (degrés et radians) : à réunir un par un')
    o = _Out()
    p = pathlib.Path(out_path)
    nom = _ascii(name or p.stem) or 'piece'
    items, styled = [], []
    ctx_new = None
    ctx_cache: dict = {}
    style_idx: dict = cache.setdefault('styles', {}) if cache is not None else {}   # id(entités) → index
    style_memo: dict = {}                                # id(entités) → {entité de style : numéro écrit}
    for ents, b, move in sources:
        R, t = b.R, b.t
        if move is not None:
            R2, t2 = np.asarray(move[0], float), np.asarray(move[1], float)
            R, t = R2 @ R, R2 @ t + t2
        moved = not (np.allclose(R, np.eye(3)) and np.allclose(t, 0.0))
        if moved and not _rigid(R):
            raise ExtractError(f'{b.name} : placement en miroir ou déformé, non pris en charge')
        if b.context is not None and (id(ents), b.context) not in ctx_cache:
            mp = {}
            order = closure(ents, [b.context])
            for k in order:
                mp[k] = len(o.lines) + 1 + len(mp)
            for k in order:
                o.add(renumber(ents[k], mp))
            ctx_cache[(id(ents), b.context)] = mp[b.context]
        if ctx_new is None and b.context is not None:
            ctx_new = ctx_cache[(id(ents), b.context)]
        order = closure(ents, [b.item])                 # tout ce que le corps cite (représentations citées comprises)
        over, new = _explicit_axes(ents, order) if moved else ({}, {})
        if moved and any(_type(ents[k]) == 'CARTESIAN_TRANSFORMATION_OPERATOR_3D' and '$' in ents[k]
                         for k in order):
            raise ExtractError(f'{b.name} : opérateur de transformation aux axes omis, déplacement non pris en '
                               'charge')
        scale = float(b.extra.get('unit_mm', 1.0)) or 1.0
        base = len(o.lines) + 1
        final = {k: base + i for i, k in enumerate(order + list(new))}
        for k in order + list(new):
            raw = new[k] if k in new else over.get(k, ents[k])
            kind = _type(raw)
            if moved:
                if kind in ('CARTESIAN_POINT', 'DIRECTION'):
                    raw = _move_points(raw, R, t, scale, kind)
                elif kind == 'COORDINATES_LIST' or kind in TESSELLATED_NORMALS:
                    raw = _move_tessellated(raw, R, t, scale)
            o.add(renumber(raw, final))
        items.append(final[b.item])
        if id(ents) not in style_idx:
            style_idx[id(ents)] = _styles_index(ents)
        if id(ents) not in style_memo:
            style_memo[id(ents)] = {}
        idx, memo = style_idx[id(ents)], style_memo[id(ents)]
        for item in order:
            for sk in idx.get(item, ()):
                head, a, _tail = _args(ents[sk])
                srefs = refs_of(a[1]) if len(a) >= 2 else []
                for k in closure(ents, srefs):          # chaîne du style (couleur…) écrite une fois par fichier
                    if k not in memo:
                        memo[k] = None
                fresh = [k for k, v in memo.items() if v is None]
                for i, k in enumerate(fresh):
                    memo[k] = len(o.lines) + 1 + i
                for k in fresh:
                    o.add(renumber(ents[k], memo))
                smp = dict(memo)
                smp[item] = final[item]
                plain = f"STYLED_ITEM({a[0]},{a[1]},{a[2]})"        # surcharge gardée comme style simple
                styled.append(o.add(renumber(plain, smp)))
    unit = next(iter(units))
    if ctx_new is None:                                 # aucun contexte lu : millimètres
        if abs(unit - 1.0) > 1e-9:
            raise ExtractError('contexte des unités introuvable dans un fichier qui n\'est pas en millimètres')
        lg = o.add("(LENGTH_UNIT()NAMED_UNIT(*)SI_UNIT(.MILLI.,.METRE.))")
        an = o.add("(NAMED_UNIT(*)PLANE_ANGLE_UNIT()SI_UNIT($,.RADIAN.))")
        so = o.add("(NAMED_UNIT(*)SI_UNIT($,.STERADIAN.)SOLID_ANGLE_UNIT())")
        unc = o.add(f"UNCERTAINTY_MEASURE_WITH_UNIT(LENGTH_MEASURE(1.E-07),#{lg},'distance_accuracy_value',"
                    f"'confusion accuracy')")
        ctx_new = o.add(f"(GEOMETRIC_REPRESENTATION_CONTEXT(3)GLOBAL_UNCERTAINTY_ASSIGNED_CONTEXT((#{unc}))"
                        f"GLOBAL_UNIT_ASSIGNED_CONTEXT((#{lg},#{an},#{so}))REPRESENTATION_CONTEXT('','3D'))")
    ac = o.add("APPLICATION_CONTEXT('core data for automotive mechanical design processes')")
    o.add(f"APPLICATION_PROTOCOL_DEFINITION('international standard','automotive_design',2000,#{ac})")
    pc = o.add(f"PRODUCT_CONTEXT('',#{ac},'mechanical')")
    prod = o.add(f"PRODUCT('{nom}','{nom}','',(#{pc}))")
    o.add(f"PRODUCT_RELATED_PRODUCT_CATEGORY('part',$,(#{prod}))")
    pdf = o.add(f"PRODUCT_DEFINITION_FORMATION('','',#{prod})")
    pdc = o.add(f"PRODUCT_DEFINITION_CONTEXT('part definition',#{ac},'design')")
    pd = o.add(f"PRODUCT_DEFINITION('design','',#{pdf},#{pdc})")
    pds = o.add(f"PRODUCT_DEFINITION_SHAPE('','',#{pd})")
    solid = all(_type(o.lines[i - 1]) in ('MANIFOLD_SOLID_BREP', 'BREP_WITH_VOIDS') for i in items)
    origin_p = o.add("CARTESIAN_POINT('',(0.,0.,0.))")
    origin_z = o.add("DIRECTION('',(0.,0.,1.))")
    origin_x = o.add("DIRECTION('',(1.,0.,0.))")
    origin = o.add(f"AXIS2_PLACEMENT_3D('',#{origin_p},#{origin_z},#{origin_x})")
    kind = 'ADVANCED_BREP_SHAPE_REPRESENTATION' if solid else 'SHAPE_REPRESENTATION'
    rep = o.add(f"{kind}('{nom}',({','.join(f'#{i}' for i in items + [origin])}),#{ctx_new})")
    o.add(f"SHAPE_DEFINITION_REPRESENTATION(#{pds},#{rep})")
    if styled:
        o.add(f"MECHANICAL_DESIGN_GEOMETRIC_PRESENTATION_REPRESENTATION('',({','.join(f'#{s}' for s in styled)}),"
              f"#{ctx_new})")
    date = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
    head = ['ISO-10303-21;', 'HEADER;', f"FILE_DESCRIPTION(('{_ascii(description)}'),'2;1');",
            f"FILE_NAME('{nom}.step','{date}',('VectorDrive'),(''),'VectorDrive','VectorDrive','');",
            "FILE_SCHEMA(('AUTOMOTIVE_DESIGN { 1 0 10303 214 1 1 1 1 }'));", 'ENDSEC;', 'DATA;']
    body = [f'#{k + 1}={line};' for k, line in enumerate(o.lines)]
    text = '\n'.join(head + body + ['ENDSEC;', 'END-ISO-10303-21;', ''])
    tmp = p.with_name(p.name + '.tmp')                  # écrit à côté puis mis en place : jamais un fichier vidé
    try:
        tmp.write_text(text, encoding='latin-1', newline='\n')
        tmp.replace(p)
    finally:
        if tmp.exists():
            tmp.unlink()
    return str(p)


def _load(path) -> tuple:
    text = pathlib.Path(path).read_text(encoding='latin-1')
    return split_entities(text), bodies(path)


def _picks(picks, n: int) -> list:
    sel = list(range(n)) if picks is None else sorted(set(int(k) for k in picks))
    if not sel or any(not 0 <= k < n for k in sel):
        raise ExtractError('corps inconnu')
    return sel


def extract(path, picks, out_path, name: str = '', moves: dict | None = None) -> str:
    """Les corps `picks` (numéros de `bodies`) dans un STEP ; `moves` {numéro : (R, t mm)} : déplacés en plus."""
    ents, bs = _load(path)
    sel = _picks(picks, len(bs))
    return write_bodies([(ents, bs[k], (moves or {}).get(k)) for k in sel], out_path, name)


def pattern_moves(count: int, step=None, angle: float | None = None, centre=(0.0, 0.0)) -> list:
    """Déplacements [(R, t mm)…] des `count` copies, la première à sa place : en ligne au pas `step` (x, y, z),
    ou en rond de l'angle total `angle` (°) autour de la verticale par `centre` (x, y) — 360 : réparties sur le
    tour, sinon de la première à la dernière."""
    count = int(count)
    if count < 1:
        raise ExtractError('au moins une copie')
    out = []
    if angle is not None:
        if abs(angle) < 1e-9:
            raise ExtractError('angle nul : les copies seraient confondues')
        full = abs(abs(angle) - 360.0) < 1e-9
        cx, cy = (float(x) for x in centre)
        for k in range(count):
            a = math.radians(angle) * k / (count if full else max(count - 1, 1))
            c, s = math.cos(a), math.sin(a)
            out.append((np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]]),
                        np.array([cx - (c * cx - s * cy), cy - (s * cx + c * cy), 0.0])))
        return out
    d = np.asarray(step if step is not None else (0.0, 0.0, 0.0), dtype=float)
    if count > 1 and float(np.linalg.norm(d)) < 1e-9:
        raise ExtractError('pas nul : les copies seraient confondues')
    return [(np.eye(3), d * k) for k in range(count)]


def file_moves(moves: list, up: str = 'Z') -> list:
    """Des déplacements donnés dans les axes de la pièce redressée (vue 3D ; `up` : l'axe du fichier tourné vers
    le haut à la lecture) ramenés aux axes du fichier."""
    from .neostep.step3d import ORIENTATIONS
    Rh = np.asarray(ORIENTATIONS.get(up, np.eye(3)), dtype=float)
    return [(Rh.T @ np.asarray(R, float) @ Rh, Rh.T @ np.asarray(t, float)) for R, t in moves]


def pattern(path, picks, out_path, moves: list, name: str = '') -> str:
    """Les corps `picks` (numéros de `bodies`, None : tous) de `path` répétés, une fois par déplacement de
    `moves` [(R, t mm)…], dans un STEP ; rend le chemin."""
    if not moves:
        raise ExtractError('aucune copie')
    ents, bs = _load(path)
    sel = _picks(picks, len(bs))
    return write_bodies([(ents, bs[k], m) for m in moves for k in sel], out_path, name)


def safe_name(text: str) -> str:
    """Un nom de fichier sûr (ASCII, lettres, chiffres, « _ . - », pas un nom réservé de Windows), '' s'il ne
    reste rien."""
    s = re.sub(r'[^A-Za-z0-9_.-]+', '_', _ascii(text)).strip('_.')
    return f'_{s}' if s.split('.')[0].upper() in RESERVED else s


def file_stems(bs: list, picks=None) -> list:
    """Noms de fichiers (sans extension) des corps `picks` de `bs` : le nom du corps en ASCII, numéroté
    s'il revient (sans égard à la casse : Windows)."""
    out, used = [], set()
    for k in (range(len(bs)) if picks is None else picks):
        base = safe_name(bs[k].name) or f'corps_{k + 1}'
        stem, i = base, 2
        while stem.lower() in used:
            stem, i = f'{base}_{i}', i + 1
        used.add(stem.lower())
        out.append(stem)
    return out


def split(path, folder, picks=None, moves: dict | None = None) -> list:
    """Un STEP par corps dans `folder` (nommé d'après le corps, `file_stems`) ; `moves` comme pour
    `extract` ; rend les fichiers. Un échec en cours de route dit les fichiers déjà écrits."""
    from ..core import progress as P
    ents, bs = _load(path)
    sel = _picks(picks, len(bs))
    folder = pathlib.Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    done, cache = [], {}
    for i, (k, stem) in enumerate(zip(sel, file_stems(bs, sel))):
        P.step(i, len(sel), 'Corps {0} sur {1}')
        try:
            done.append(write_bodies([(ents, bs[k], (moves or {}).get(k))], folder / f'{stem}.step', bs[k].name,
                                     cache=cache))
        except (OSError, ExtractError) as ex:
            if not done:
                raise
            raise ExtractError(f'{len(done)} fichier(s) écrit(s), puis {bs[k].name} : {ex}') from ex
    return done


def combine(parts: list, out_path, name: str = '') -> str:
    """Une pièce faite des corps de plusieurs fichiers : `parts` [(chemin, numéros ou None : tous, (R, t mm)
    ou None)…]."""
    sources = []
    for path, picks, move in parts:
        ents, bs = _load(path)
        for k in _picks(picks, len(bs)):
            sources.append((ents, bs[k], move))
    return write_bodies(sources, out_path, name)
