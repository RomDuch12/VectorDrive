"""L'environnement STEP de l'assistant (demande du 20/11, 22 h : « fournir a assistant ai le meilleur environnement
de génération step pour débutants et avances et expert »).

Trois niveaux, tous en géométrie exacte (`core.brep` : plans, cylindres, cônes, sphères ; arcs gardés) :
- débutant : une pièce du catalogue (`core.stepgen` : visserie, transmission, bruts, moule, bridage), ses
  paramètres vérifiés ;
- avancé : la pièce des formes du dessin (`core.stepdraw` : plaque percée, poches ; `core.steprevolve` : tournée) ;
- expert : des corps décrits un à un (tranches, boucles, révolutions, trous, placements, pièces du catalogue
  pour les assemblages : `from_spec`).

Chaque fichier va dans le dossier STEP de l'assistant (« step » dans celui de ses copies), jamais par-dessus un
fichier qui n'est pas l'un des siens (le registre de ses copies, `agent.tools`) ; il est relu après écriture
(`read_back`) pour en rendre le résumé."""
from __future__ import annotations

import math

from .protocol import ToolError

#: le sous-dossier des copies où vont les STEP de l'assistant
SUBFOLDER = 'step'
#: au plus tant de corps, de tranches par corps, de boucles par tranche, de points par boucle (description experte)
MAX_BODIES = 50
MAX_SLABS = 200
MAX_LOOPS = 500
MAX_POINTS = 5000
#: une cote au-delà (mm) est refusée
LIMIT = 1.0e5


class StepToolError(ToolError):
    """Un refus dit au modèle (comme `ToolError`)."""


def step_dir(settings=None):
    from .tools import copies_dir
    return copies_dir(settings) / SUBFOLDER


def check_name(name) -> str:
    import re
    if not isinstance(name, str) or not re.fullmatch(r'[\w -]{1,60}', name.strip()) \
            or re.fullmatch(r'(CON|PRN|AUX|NUL|(COM|LPT)[0-9¹²³])', name.strip(), re.IGNORECASE):
        raise StepToolError('"name": 1 to 60 letters, digits, spaces, - or _ (not a reserved name of the system)')
    return name.strip()


def place(path, data: bytes, overwrite: bool = False) -> bool:
    """Écrit `data` dans `path` comme un fichier de l'assistant : jamais par-dessus un fichier qui n'est pas l'un des
    siens (inchangé depuis) ; l'un des siens seulement avec `overwrite`. Écrit d'abord dans un dossier provisoire du
    même disque, puis posé (lien dur, sinon création exclusive) ; retenu au registre. Rend True s'il a remplacé."""
    import os
    import secrets
    import shutil
    from .tools import file_hash, own_copy, record_copy
    path = __import__('pathlib').Path(path)
    existed = os.path.lexists(path)
    if existed:
        if not path.is_file() or path.is_symlink() or not own_copy(path):
            raise StepToolError(f'"{path.name}" exists and is not one of your files (or it was changed since): it is '
                                f'never overwritten; choose another name')
        if not overwrite:
            raise StepToolError(f'"{path.name}" is one of your files: "overwrite": true to replace it, or choose '
                                f'another name')
    work = path.parent / f'.~{secrets.token_hex(4)}'
    tmp = work / path.name
    placed = False
    try:
        work.mkdir(parents=True)
        tmp.write_bytes(data)
        digest = file_hash(tmp)
        if existed:
            if not own_copy(path):
                raise StepToolError(f'"{path.name}" was changed meanwhile: it is not overwritten')
            os.replace(tmp, path)
        else:
            try:
                os.link(tmp, path)
            except FileExistsError as ex:
                raise StepToolError(f'"{path.name}" appeared meanwhile: choose another name') from ex
            except OSError:
                try:
                    dst = open(path, 'xb')
                except FileExistsError as ex:
                    raise StepToolError(f'"{path.name}" appeared meanwhile: choose another name') from ex
                try:
                    with dst:
                        dst.write(data)
                except OSError:
                    os.remove(path)
                    raise
        placed = True
        record_copy(path, digest)
    except StepToolError:
        raise
    except OSError as ex:
        if placed:
            raise StepToolError(f'"{path.name}" was written but could not be recorded as one of your files ({ex}): '
                                f'it will not be overwritten') from ex
        raise StepToolError(f'the file could not be written: {ex}') from ex
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return existed


# --- le catalogue (débutant) --------------------------------------------------------------------------------------
def families(category: str | None = None) -> list:
    from ..core import stepgen as G
    out = []
    for f in G.FAMILIES.values():
        if category and f.category.casefold() != str(category).casefold():
            continue
        out.append({'key': f.key, 'label': f.label, 'category': f.category, 'standard': f.standard,
                    'parameters': [p.key for p in f.params]})
    return out


def family(key: str) -> dict:
    from ..core import stepgen as G
    f = G.FAMILIES.get(key)
    if f is None:
        raise StepToolError(f'unknown family "{key}" (step_families)')
    params = []
    for p in f.params:
        d = {'key': p.key, 'label': p.label, 'kind': p.kind, 'default': p.default}
        if p.kind == 'choice':
            d['choices'] = [{'value': c, 'label': G.CHOICE_LABELS.get(c, c)} for c in p.choices]
        else:
            d.update({'min': p.lo, 'max': p.hi, 'unit': p.unit})
        params.append(d)
    return {'key': f.key, 'label': f.label, 'category': f.category, 'standard': f.standard, 'note': f.note,
            'parameters': params}


def generate(key: str, values: dict | None = None):
    """(corps, valeurs retenues, nom de fichier proposé, description) d'une pièce du catalogue."""
    from ..core import stepgen as G
    if key not in G.FAMILIES:
        raise StepToolError(f'unknown family "{key}" (step_families)')
    if values is not None and not isinstance(values, dict):
        raise StepToolError('"values" must be an object {parameter: value}')
    known = {p.key for p in G.FAMILIES[key].params}
    for k, x in (values or {}).items():                  # vérifié avant `stepgen.values` (un vrai pour 1, « nan »…)
        if k not in known:
            raise StepToolError(f'unknown parameter "{k}" (step_family "{key}")')
        if isinstance(x, bool) or not isinstance(x, (int, float, str)):
            raise StepToolError(f'"{k}": a number, or one of its choices (step_family "{key}")')
        if isinstance(x, float) and not math.isfinite(x):
            raise StepToolError(f'"{k}": {x!r} is not a finite number')
    try:
        v = G.values(key, **(values or {}))
        bodies = G.build(key, v)
    except G.GenError as ex:
        raise StepToolError(str(ex)) from ex
    except (TypeError, ValueError, ArithmeticError) as ex:
        raise StepToolError(f'these values do not make a part: {ex}') from ex
    f = G.FAMILIES[key]
    return bodies, v, G.file_name(key, v), f'{f.label} {f.standard}'.strip()


# --- le texte et sa relecture ----------------------------------------------------------------------------------------
def step_bytes(bodies, name: str, description: str = 'VectorDrive') -> bytes:
    from ..core import brep as B
    for b in bodies:
        try:
            B.check(b)
        except B.BrepError as ex:
            raise StepToolError(f'{b.name}: {ex}') from ex
    return B.step_text(bodies, name=name, description=description).encode('utf-8')


def summary(bodies) -> dict:
    """Nombre de corps, leurs noms, l'encombrement (mm) et le volume (mm³) d'après les corps eux-mêmes."""
    import numpy as np
    from ..core import brep as B
    vol = 0.0
    pts = []
    for b in bodies:
        try:
            vol += float(B.volume(b))
        except Exception:                                # noqa: BLE001 — un volume non calculé : sans
            pass
        pts.append(np.asarray(B.mesh(b, n_arc=32, bands=4)).reshape(-1, 3))
    P = np.concatenate(pts) if pts else np.zeros((0, 3))
    box = [round(float(x), 3) for x in (list(P.min(axis=0)) + list(P.max(axis=0)))] if len(P) else []
    return {'bodies': len(bodies), 'names': [b.name for b in bodies][:MAX_BODIES], 'bounds_mm': box,
            'size_mm': [round(box[i + 3] - box[i], 3) for i in range(3)] if box else [],
            'volume_mm3': round(vol, 1)}


#: au-delà, un fichier n'est pas relu (le maillage se fait dans le fil de l'interface)
READ_MAX = 30 * 1024 * 1024


def read_back(path, expect: dict | None = None) -> dict:
    """Le fichier relu par le lecteur STEP de VectorDrive (l'axe Z tel quel) : faces, triangles, solides,
    encombrement — la preuve qu'il se lit ; `expect` (le résumé des corps écrits) : « ok » exige aussi le même
    nombre de solides et le même encombrement (à 1 % près)."""
    import os
    from ..io.neostep import step3d
    size = os.path.getsize(path)
    if size > READ_MAX:
        return {'ok': False, 'error': f'{size // 1048576} MB: too large to be read back here'}
    with open(path, 'r', encoding='latin-1') as f:       # le texte, pas le chemin (un nom « ISO-10303… »)
        text = f.read()
    m = step3d.lire_modele(text, axe_haut='Z')
    out = {'faces': int(getattr(m, 'n_faces', 0)), 'faces_meshed': int(getattr(m, 'n_faces_maillees', 0)),
           'triangles': int(len(m.triangles)), 'solids': len(getattr(m, 'corps', None) or [])}
    try:
        b = m.bornes()                                   # (xmin, ymin, zmin, xmax, ymax, zmax) ou None
        if b is not None and len(b) == 6:
            out['bounds_mm'] = [round(float(x), 3) for x in b]
    except Exception:                                    # noqa: BLE001 — sans encombrement
        pass
    ok = out['faces'] > 0 and out['faces'] == out['faces_meshed'] and out['triangles'] > 0
    if ok and expect:
        if expect.get('bodies') and out['solids'] and out['solids'] != expect['bodies']:
            ok = False
            out['mismatch'] = f"{out['solids']} solids read, {expect['bodies']} written"
        a, b = expect.get('bounds_mm') or [], out.get('bounds_mm') or []
        if len(a) == 6 and len(b) == 6:
            span = max(1.0, max(a[i + 3] - a[i] for i in range(3)))
            if max(abs(x - y) for x, y in zip(a, b)) > 0.01 * span:
                ok = False
                out['mismatch'] = 'the bounds read back differ from the bodies written'
    out['ok'] = ok
    return out


def drawing_solids(win, bodies, centre: bool = True):
    """Les volumes du dessin (maillés) des corps, prêts à poser — calculés avant d'écrire le fichier : le milieu de
    leur encombrement au centre de la plaque (`centre`, sinon où ils sont : une pièce des contours du dessin reste
    sur eux, Z compris : sa plaque sur Z = 0, sa visserie au-dessus et dessous), sinon posés sur Z = 0. Rend (volumes, translation)."""
    import numpy as np
    from ..core import brep as B
    from ..core import solids as SO
    if not SO.available():                               # (pas `_solids_ready` : sa fenêtre bloquerait l'outil)
        raise StepToolError('3D volumes are not available in this installation (manifold3d)')
    layer = win.canvas.doc.active_layer
    if getattr(layer, 'locked', False):
        raise StepToolError(f'the active layer "{layer.name}" is locked: no "add_to_drawing"')
    plate = win.canvas.doc.plate
    cx, cy = (plate.x + plate.width / 2, plate.y + plate.height / 2) if plate is not None else (0.0, 0.0)
    meshes = [np.asarray(B.mesh(b)) for b in bodies]
    P = np.concatenate([m.reshape(-1, 3) for m in meshes])
    lo, hi = P.min(axis=0), P.max(axis=0)
    at = [cx - (lo[0] + hi[0]) / 2, cy - (lo[1] + hi[1]) / 2, -lo[2]] if centre else [0.0, 0.0, 0.0]
    sols = []
    try:
        for b, m in zip(bodies, meshes):
            s = SO.from_triangles(m + np.asarray(at), b.name)
            s.color = tuple(b.color)
            sols.append(s)
    except (ValueError, RuntimeError) as ex:
        raise StepToolError(f'no 3D volume from these bodies: {ex}') from ex
    return sols, at


def put_solids(win, sols, at, stepgen: dict | None = None) -> list:
    """Les volumes posés dans le dessin (un pas d'annulation, `_put_solids`) ; rend leurs identifiants."""
    new = win._put_solids(sols)
    for it in new:
        if stepgen is not None:
            it.extra['stepgen'] = dict(stepgen, at=[float(x) for x in at])
    return [it.id for it in new]


def _finite(x, what: str) -> float:
    if isinstance(x, bool) or not isinstance(x, (int, float)):
        raise StepToolError(f'{what}: {x!r} is not a number')
    try:
        v = float(x)
    except (TypeError, ValueError, OverflowError):
        raise StepToolError(f'{what}: {x!r} is not a number') from None
    if not math.isfinite(v) or abs(v) > LIMIT:
        raise StepToolError(f'{what}: {x!r} out of range (±{LIMIT:g} mm)')
    return v


# --- la pièce du dessin (avancé) -------------------------------------------------------------------------------------
#: les modes des contours intérieurs (nom donné au modèle → `core.stepdraw`)
INNER = {'holes': 'trous', 'pockets': 'poches', 'round_holes': 'ronds'}
SHAPES = ('extruded', 'turned')


def contours(items) -> list:
    """Les contours (mm) des objets `items` et de leurs enfants (formes, textes par leur contour)."""
    from ..ui.canvas import _leaves, item_path
    return [c for leaf in _leaves(list(items)) for c in (getattr(item_path(leaf), 'contours', None) or []) if c]


def from_drawing(items, shape: str = 'extruded', thickness: float = 0.0, inner: str = 'holes',
                 pocket: float = 0.0, name: str = 'piece', tol: float | None = None) -> list:
    """Les corps tirés des contours fermés de `items` : extrudés (`core.stepdraw` : le contour le plus extérieur est
    le bord, les autres selon `inner`), ou tournés (`core.steprevolve` : un demi-profil par contour fermé, l'axe un
    trait droit choisi avec lui, sinon la verticale par son point le plus à gauche)."""
    from ..core import stepdraw as SD
    from ..core import steprevolve as RV
    from ..core.geom import Path
    if not isinstance(shape, str) or shape not in SHAPES:
        raise StepToolError('"shape" must be "extruded" or "turned"')
    cs = contours(items)
    if not any(c.closed for c in cs):
        raise StepToolError('no closed contour in these objects (the edge of the part, its holes)')
    tol = SD.TOL if tol is None else _finite(tol, 'tolerance')
    if not 0.0005 <= tol <= 1.0:
        raise StepToolError('"tolerance": from 0.0005 to 1 mm')
    try:
        if shape == 'turned':
            return RV.bodies(Path(cs), name, tol)
        if not isinstance(inner, str) or inner not in INNER:
            raise StepToolError('"inner" must be "holes", "pockets" or "round_holes"')
        t = _finite(thickness, 'thickness')
        if not t > 0:
            raise StepToolError('"thickness" (mm) must be greater than 0 for an extruded part')
        p = _finite(pocket or 0.0, 'pocket')
        if INNER[inner] != 'trous' and not 0 < p < t:
            raise StepToolError('"pocket" (mm): the depth of the pockets, greater than 0 and less than the thickness')
        return SD.bodies(Path(cs), t, INNER[inner], p, name, tol)
    except SD.DrawError as ex:
        raise StepToolError(f'no part from these contours: {ex}') from ex


def file_stem(text: str) -> str:
    """Un nom de fichier permis tiré d'un nom proposé (« Vis_CHC_ISO4762_M2.5x10 » → « …M2_5x10 »)."""
    import re
    s = re.sub(r'[^\w -]+', '_', str(text)).strip(' -_')[:60].strip(' -_')
    return s or 'piece'


def listing(settings=None) -> dict:
    """Les fichiers STEP du dossier STEP de l'assistant : nom, taille, « yours » (l'un des siens, inchangé)."""
    import os
    from .tools import own_copy
    folder = step_dir(settings)
    out = []
    try:
        names = sorted(os.listdir(folder))
    except OSError:
        names = []
    for n in names:
        p = folder / n
        if p.suffix.lower() in ('.step', '.stp') and p.is_file():
            out.append({'name': n, 'size': p.stat().st_size, 'yours': own_copy(p)})
    return {'folder': str(folder), 'files': out[-200:]}


def step_file(settings, name):
    """Le fichier `name` du dossier STEP de l'assistant (seulement là, .step ou .stp)."""
    import pathlib
    if not isinstance(name, str) or not name.strip() or pathlib.Path(name).name != name.strip():
        raise StepToolError('"name": the name of a file of your STEP folder (step_check without "name" lists them)')
    p = step_dir(settings) / name.strip()
    if p.suffix.lower() not in ('.step', '.stp'):
        p = p.with_name(p.name + '.step')
    if not p.is_file():
        raise StepToolError(f'no file "{p.name}" in your STEP folder')
    return p


DOC = '''STEP parts (exact geometry: planes, cylinders, cones, spheres; arcs stay arcs). Every file goes to your STEP
folder ("step" in your copies folder); a file that is not one of yours is never overwritten; one of yours only with
"overwrite": true. Each file is read back after it is written (faces, triangles, bounds): say so to the user.

Levels:
- Beginner: a catalogue part. step_families (optionally "category": Visserie, Transmission, Brut, Moule, Bridage)
  gives the keys; step_family "key" gives its parameters (choices, min, max, unit, default); step_generate "key"
  with "values" {parameter: value} (the defaults for the others). Screws stand on the Z axis, under the head at Z = 0
  (countersunk: top of the head at Z = 0), shank downwards; nuts, washers, bars, plates stand on Z = 0.
- Advanced: a part from closed contours of the drawing, step_from_drawing with "ids" (default: the selection).
  "shape": "extruded" (the outermost contour is the edge, Z from 0 to "thickness"; the inner contours are "holes"
  through, "pockets" of "pocket" depth from the top, or "round_holes": round ones through, the others pockets; a
  contour inside a pocket is an island) or "turned" (each closed contour is a half profile turned around the axis:
  a straight line selected with it, otherwise the vertical through its leftmost point; the bottom of the profile at
  Z = 0). Draw the contours first (shapes, texts by their outline) when the user describes a flat or turned part.
"add_to_drawing": true also adds the part as 3D volumes in the drawing (one undo step), on Z = 0: a catalogue or
turned part centred on the plate, an extruded part where its contours are. step_check reads back a file of your STEP folder (without "name": lists them).
Prefer the catalogue for standard parts (exact standard dimensions); give the main dimensions in your answer.'''


def doc_text() -> str:
    return DOC + '\n\n' + EXPERT


# --- la description experte (round 1135) : des corps décrits un à un -------------------------------------------------
EXPERT = '''Expert: step_build with "spec" {"bodies": [body, ...]} (at most 50 bodies); "dry_run": true checks and
measures without writing. A body is one of:
- {"slabs": [{"z0": 0, "z1": 10, "loops": [loop, ...]}, ...]}: a stack of slabs along Z, from bottom to top, each
  slab touching the next one (no gap, no overlap); the loops of a slab are nested: the outer contour, holes inside it,
  islands inside the holes. Two neighbouring slabs: loops identical, one inside the other, or sharing straight walls;
  never crossing.
- {"revolve": {"profile": [[z, r], ...], "holes": [{"z0", "z1", "loop"}], "cx": 0, "cy": 0}}: turned around a vertical
  axis, profile read from bottom to top (r > 0: cylinders and cones).
- {"part": "<catalogue key>", "values": {...}}: a catalogue part (step_family), for assemblies.
- {"drawing": ["<id>", ...], "thickness": 10, "inner": "holes", "pocket": 2}: extruded from closed contours of the
  drawing (ids from list_objects; as step_from_drawing), where they are, from Z = 0 to the thickness: a plate and its
  screws in one assembly ("add_to_drawing": the assembly stays where it is, the plate on Z = 0).
Any body: "name", "color" [r, g, b] (0 to 1), "holes" [{"z0", "z1", "loop"}] (added to the slabs between z0 and z1:
counterbores, pockets, through holes; not for "part"), "placement" {"origin": [x, y, z], "z_axis": [x, y, z],
"x_axis": [x, y, z], "rotate_z": degrees} (rotation and translation only: no mirror).
A loop is one of:
- {"circle": [cx, cy, r]} (+ "r_top": radius at the top of the slab: a cone; or "sphere": [zc, R]: on that sphere,
  r is then not used: the radius follows the sphere; in a hole, cone and sphere follow z0..z1 of the
  hole)
- {"rect": [x0, y0, x1, y1]} (+ "r": corner radius)
- {"slot": [cx, cy, length, width]} (+ "angle" in degrees)
- {"regular": [n, across_flats]} (+ "cx", "cy", "start" degrees: a hexagon is n = 6)
- {"polygon": [[x, y], ...]} (+ "bulges": one per vertex towards the next, tan(angle/4) as in DXF, positive
  counter-clockwise; or "scale_top" with "center": a straight-sided taper, no arcs)
Example, a flange 80 x 80 x 12 with a counterbored bore and four holes:
{"bodies": [{"name": "flange", "slabs": [{"z0": 0, "z1": 12, "loops": [{"rect": [-40, -40, 40, 40], "r": 6},
{"circle": [0, 0, 10]}, {"circle": [30, 30, 3.2]}, {"circle": [-30, 30, 3.2]}, {"circle": [-30, -30, 3.2]},
{"circle": [30, -30, 3.2]}]}], "holes": [{"z0": 8, "z1": 12, "loop": {"circle": [0, 0, 16]}}]}]}
A hole cuts where there is material: in its slabs, the loops it contains are removed first (here the bore under
the counterbore), in any order of the holes; where it is already empty, nothing changes; a hole outside the material
is refused (it would add matter). The same for "revolve.holes". A loop that crosses itself is refused.
A refusal names the body and what is wrong: fix that and try again (dry_run first for a complex part).'''

_KINDS = ('circle', 'rect', 'slot', 'regular', 'polygon')
_BODY_KEYS = {'name', 'color', 'placement', 'slabs', 'revolve', 'part', 'values', 'holes', 'drawing', 'thickness',
              'inner', 'pocket'}
_DRAWING_KEYS = {'thickness', 'inner', 'pocket'}


def _num(x, what: str) -> float:
    if isinstance(x, bool):
        raise StepToolError(f'{what}: {x!r} is not a number')
    return _finite(x, what)


def _nums(x, n: int, what: str) -> list:
    if not isinstance(x, (list, tuple)) or len(x) != n:
        raise StepToolError(f'{what}: a list of {n} numbers')
    return [_num(v, f'{what}[{i}]') for i, v in enumerate(x)]


def _loop(d, where: str):
    from ..core import brep as B
    if not isinstance(d, dict):
        raise StepToolError(f'{where}: a loop is an object ({", ".join(_KINDS)})')
    kinds = [k for k in _KINDS if k in d]
    if len(kinds) != 1:
        raise StepToolError(f'{where}: exactly one of {", ".join(_KINDS)}')
    k = kinds[0]
    allowed = {'circle': {'r_top', 'sphere'}, 'rect': {'r'}, 'slot': {'angle'}, 'regular': {'cx', 'cy', 'start'},
               'polygon': {'bulges', 'scale_top', 'center'}}[k] | {k}
    extra = set(d) - allowed
    if extra:
        raise StepToolError(f'{where}: unknown key(s) {", ".join(sorted(extra))} for a {k}')
    if k == 'circle':
        cx, cy, r = _nums(d['circle'], 3, f'{where}.circle')
        if r <= 0:
            raise StepToolError(f'{where}.circle: the radius must be greater than 0')
        r_top = _num(d['r_top'], f'{where}.r_top') if d.get('r_top') is not None else None
        sphere = tuple(_nums(d['sphere'], 2, f'{where}.sphere')) if d.get('sphere') is not None else None
        if r_top is not None and sphere is not None:
            raise StepToolError(f'{where}: "r_top" or "sphere", not both')
        return B.Circle(cx, cy, r, r_top, sphere)
    if k == 'rect':
        x0, y0, x1, y1 = _nums(d['rect'], 4, f'{where}.rect')
        if not (x1 > x0 and y1 > y0):
            raise StepToolError(f'{where}.rect: [x0, y0, x1, y1] with x1 > x0 and y1 > y0')
        return B.rounded_rect(x0, y0, x1, y1, _num(d.get('r', 0.0), f'{where}.r'))
    if k == 'slot':
        cx, cy, length, width = _nums(d['slot'], 4, f'{where}.slot')
        if not (width > 0 and length > width):
            raise StepToolError(f'{where}.slot: [cx, cy, length, width] with length > width > 0')
        return B.slot(cx, cy, length, width, _num(d.get('angle', 0.0), f'{where}.angle'))
    if k == 'regular':
        n, af = _nums(d['regular'], 2, f'{where}.regular')
        if n != int(n) or not 3 <= n <= 64 or af <= 0:
            raise StepToolError(f'{where}.regular: [n, across_flats], n a whole number from 3 to 64, across_flats > 0')
        return B.polygon(int(n), af, _num(d.get('cx', 0.0), f'{where}.cx'), _num(d.get('cy', 0.0), f'{where}.cy'),
                         _num(d.get('start', 0.0), f'{where}.start'))
    pts = d['polygon']
    if not isinstance(pts, list) or not 2 <= len(pts) <= MAX_POINTS:
        raise StepToolError(f'{where}.polygon: from 2 to {MAX_POINTS} points [x, y]')
    pts = [tuple(_nums(p, 2, f'{where}.polygon[{i}]')) for i, p in enumerate(pts)]
    for i in range(len(pts)):
        a, b = pts[i], pts[(i + 1) % len(pts)]
        if math.hypot(a[0] - b[0], a[1] - b[1]) < 1e-6:
            raise StepToolError(f'{where}.polygon: points {i} and {(i + 1) % len(pts)} are the same (the last point '
                                f'is not repeated: the loop closes by itself)')
    bulges = None
    if d.get('bulges') is not None:
        if not isinstance(d['bulges'], list) or len(d['bulges']) != len(pts):
            raise StepToolError(f'{where}.bulges: one number per point')
        bulges = [_num(b, f'{where}.bulges[{i}]') for i, b in enumerate(d['bulges'])]
        if any(abs(b) > 100 for b in bulges):
            raise StepToolError(f'{where}.bulges: from -100 to 100 (tan(angle/4))')
    scale = _num(d.get('scale_top', 1.0), f'{where}.scale_top')
    if not 0.01 <= scale <= 100:
        raise StepToolError(f'{where}.scale_top: from 0.01 to 100')
    center = tuple(_nums(d['center'], 2, f'{where}.center')) if d.get('center') is not None else (
        sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))
    return B.Poly(pts, bulges, scale, center)


def _holes(lst, where: str) -> list:
    if not isinstance(lst, list) or len(lst) > MAX_LOOPS:
        raise StepToolError(f'{where}: a list of at most {MAX_LOOPS} {{"z0", "z1", "loop"}}')
    out = []
    for i, h in enumerate(lst):
        w = f'{where}[{i}]'
        if not isinstance(h, dict) or set(h) != {'z0', 'z1', 'loop'}:
            raise StepToolError(f'{w}: {{"z0", "z1", "loop"}}')
        z0, z1 = _num(h['z0'], f'{w}.z0'), _num(h['z1'], f'{w}.z1')
        if not z1 > z0:
            raise StepToolError(f'{w}: z1 must be greater than z0')
        out.append((z0, z1, _loop(h['loop'], f'{w}.loop')))
    return out


def _placement(d, where: str):
    from ..core import brep as B
    if d is None:
        return None
    if not isinstance(d, dict) or set(d) - {'origin', 'z_axis', 'x_axis', 'rotate_z'}:
        raise StepToolError(f'{where}: {{"origin", "z_axis", "x_axis", "rotate_z"}}')
    origin = _nums(d.get('origin', [0, 0, 0]), 3, f'{where}.origin')
    z_axis = _nums(d.get('z_axis', [0, 0, 1]), 3, f'{where}.z_axis')
    if math.hypot(*z_axis) < 1e-9:
        raise StepToolError(f'{where}.z_axis: not a null vector')
    x_axis = _nums(d['x_axis'], 3, f'{where}.x_axis') if d.get('x_axis') is not None else None
    if x_axis is not None:
        nz = math.hypot(*z_axis)
        dot = sum(a * b for a, b in zip(x_axis, z_axis)) / nz
        if math.hypot(*[x_axis[i] - dot * z_axis[i] / nz for i in range(3)]) < 1e-9:
            raise StepToolError(f'{where}.x_axis: not along z_axis')
    m = B.placement(origin, z_axis, x_axis)
    if d.get('rotate_z') is not None:
        m = B.compose(m, B.rotation_z(_num(d['rotate_z'], f'{where}.rotate_z')))
    return m


def _loop_at(lp, z0: float, z1: float, za: float, zb: float):
    """La boucle d'un trou décrite de z0 à z1, ramenée à la tranche za..zb (un cône, une sphère, un tronc de
    pyramide suivent la hauteur du trou, pas celle de chaque tranche)."""
    from ..core import brep as B
    if isinstance(lp, B.Circle):
        if lp.sphere is not None:
            return B.Circle(lp.cx, lp.cy, lp.radius(za, z0, z1), sphere=lp.sphere)
        if lp.varies():
            return B.Circle(lp.cx, lp.cy, lp.radius(za, z0, z1), lp.radius(zb, z0, z1))
        return B.Circle(lp.cx, lp.cy, lp.r)
    if lp.varies():
        h = z1 - z0
        sa = 1.0 + (lp.scale_top - 1.0) * (za - z0) / h
        sb = 1.0 + (lp.scale_top - 1.0) * (zb - z0) / h
        return B.Poly(lp.at(za, z0, z1), list(lp.bulges) if lp.bulges else None, sb / sa if sa > B.EPS else 1.0,
                      lp.center)
    return B.Poly(list(lp.pts), list(lp.bulges) if lp.bulges else None, 1.0, lp.center)


def _heights(loops, za: float, zb: float) -> list:
    """Les cotes où juger une tranche za..zb : près de ses faces, au milieu, au centre d'une sphère qui la traverse
    (deux cônes ne se croisent qu'une fois : les deux bouts le disent)."""
    from ..core import brep as B
    dz = zb - za
    hs = [za + 1e-3 * dz, (za + zb) / 2.0, zb - 1e-3 * dz]
    lo, hi = za + 1e-3 * dz, zb - 1e-3 * dz
    balls = [q for q in loops if isinstance(q, B.Circle) and q.sphere is not None]
    cones = [q for q in loops if isinstance(q, B.Circle) and q.sphere is None and q.varies()]
    for q in balls:
        zc, R = q.sphere
        hs.append(zc)
        for c in cones:                                  # sphère contre cône : là où leurs pentes s'égalent
            k = (c.r_top - c.r) / dz
            hs.append(zc - k * R / (1.0 + k * k) ** 0.5)
    return sorted(h for h in hs if lo <= h <= hi)


def _cut_hole(body, z0: float, z1: float, lp, where: str):
    """Le trou `lp` entre z0 et z1 (lamage, poche, perçage, fraisure) : les tranches recoupées ; dans chacune, les
    boucles qu'il contient retirées (un perçage sous un lamage, un îlot dans la poche : enlevés avec la matière), puis
    le trou ajouté s'il tombe dans la matière (déjà vide là : rien à ajouter — l'ordre des trous ne compte pas) ; hors
    de la matière : refusé (il en ajouterait). Jugé à plusieurs cotes de la tranche (un cône, une sphère changent le
    long d'elle) : un bord qui touche celui d'une boucle, une réponse qui change d'une cote à l'autre : refusé."""
    from shapely.geometry import Polygon
    from ..core import brep as B
    b = B.cut(body, z0, z1)
    hit = 0
    for s in b.slabs:
        if not (s.z0 >= z0 - B.EPS and s.z1 <= z1 + B.EPS):
            continue
        mine = _loop_at(lp, z0, z1, s.z0, s.z1)
        first = None
        for h in _heights(s.loops + [mine], s.z0, s.z1):
            try:
                outer = Polygon(B._level_points(mine, h, s.z0, s.z1))
                if not outer.is_valid:
                    raise StepToolError(f'{where}: the hole crosses itself')
                inside, polys = [], []
                for q in s.loops:
                    qp = Polygon(B._level_points(q, h, s.z0, s.z1))
                    if outer.exterior.intersects(qp.exterior):   # bords communs : une poche étagée, un même trou
                        inn = outer.covers(qp)
                        if not inn and not qp.covers(outer):
                            raise StepToolError(f'{where}: the hole partly overlaps a contour of the slab z '
                                                f'{s.z0:g}..{s.z1:g} (at z {h:g}): a hole is either inside the '
                                                f'material, or contains whole contours')
                    else:
                        inn = outer.contains(qp)
                    inside.append(inn)
                    polys.append(qp)
                pt = outer.representative_point()            # un point du trou, pas sur un bord commun
                depth = sum(1 for qp, c in zip(polys, inside) if not c and qp.contains(pt))
            except StepToolError:
                raise
            except Exception as ex:                      # noqa: BLE001 — shapely : boucle impossible
                raise StepToolError(f'{where}: {type(ex).__name__}: {ex}') from ex
            now = (tuple(inside), depth == 0, depth % 2)
            if first is None:
                first = now
            elif now != first:
                raise StepToolError(f'{where}: between z {s.z0:g} and {s.z1:g}, the hole crosses the wall of a cone '
                                    f'or a sphere: split it at that height (two holes)')
        inside, empty, odd = first
        if empty:
            raise StepToolError(f'{where}: the hole is not inside the material between z {s.z0:g} and {s.z1:g} (it '
                                f'would add matter): check its position and size')
        s.loops = [q for q, c in zip(s.loops, inside) if not c] + ([mine] if odd else [])
        hit += 1
    if not hit:
        raise StepToolError(f'{where}: z0..z1 outside the body')
    return b


def _simple(body, where: str) -> None:
    """Une boucle qui se recoupe (en huit, arcs qui se chevauchent) : refusée (le solide serait faux)."""
    from shapely.geometry import LinearRing
    from ..core import brep as B
    for k, s in enumerate(body.slabs):
        zm = (s.z0 + s.z1) / 2.0
        for j, lp in enumerate(s.loops):
            if isinstance(lp, B.Circle):
                continue
            pts = B._level_points(lp, zm, s.z0, s.z1)
            if len(pts) < 3 or not LinearRing(pts).is_simple or abs(B._area(pts)) <= B.EPS:
                raise StepToolError(f'{where}: a loop of the slab z {s.z0:g}..{s.z1:g} crosses itself or has no '
                                    f'area')


def from_spec(spec, resolve=None) -> list:
    """Les corps d'une description experte (voir `EXPERT`) ; StepToolError dit lequel ne va pas, et pourquoi.
    `resolve(ids)` : les objets du dessin d'un corps « drawing » (sans lui, ce corps est refusé)."""
    from ..core import brep as B
    if not isinstance(spec, dict) or set(spec) != {'bodies'} or not isinstance(spec['bodies'], list) \
            or not spec['bodies']:
        raise StepToolError('"spec": {"bodies": [body, ...]} (read_documentation topic "step")')
    if len(spec['bodies']) > MAX_BODIES:
        raise StepToolError(f'at most {MAX_BODIES} bodies')
    out = []
    for i, b in enumerate(spec['bodies']):
        where = f'bodies[{i}]'
        if not isinstance(b, dict):
            raise StepToolError(f'{where}: a body is an object')
        extra = set(b) - _BODY_KEYS
        if extra:
            raise StepToolError(f'{where}: unknown key(s) {", ".join(sorted(extra))}')
        kinds = [k for k in ('slabs', 'revolve', 'part', 'drawing') if k in b]
        if len(kinds) != 1:
            raise StepToolError(f'{where}: exactly one of "slabs", "revolve", "part", "drawing"')
        if kinds[0] != 'drawing' and set(b) & _DRAWING_KEYS:
            raise StepToolError(f'{where}: "thickness", "inner", "pocket" go with "drawing"')
        name = b.get('name', f'body_{i + 1}')
        if not isinstance(name, str) or not 0 < len(name.strip()) <= 60:
            raise StepToolError(f'{where}.name: 1 to 60 characters')
        name = name.strip()
        color = tuple(_nums(b['color'], 3, f'{where}.color')) if b.get('color') is not None else B.GREY
        if not all(0 <= c <= 1 for c in color):
            raise StepToolError(f'{where}.color: three numbers from 0 to 1')
        m = _placement(b.get('placement'), f'{where}.placement')
        if 'values' in b and kinds[0] != 'part':
            raise StepToolError(f'{where}: "values" goes with "part"')
        if kinds[0] == 'part':
            if 'holes' in b:
                raise StepToolError(f'{where}: no "holes" on a catalogue part')
            try:
                parts, _v, _f, _d = generate(str(b['part']), b.get('values'))
            except StepToolError as ex:
                raise StepToolError(f'{where}: {ex}') from ex
            for k, p in enumerate(parts):
                pm = p.matrix
                p.matrix = B.compose(m, pm) if m is not None and pm is not None else (m if m is not None else pm)
                p.name = name if len(parts) == 1 else f'{name}_{k + 1}'
                if b.get('color') is not None:
                    p.color = color
                out.append(p)
            continue
        if kinds[0] == 'drawing':
            if resolve is None:
                raise StepToolError(f'{where}: "drawing" is not available here')
            try:
                got = from_drawing(resolve(b['drawing']), 'extruded', b.get('thickness', 0.0), b.get('inner', 'holes'),
                                   b.get('pocket', 0.0), name)
            except ToolError as ex:
                raise StepToolError(f'{where}.drawing: {ex}') from ex
            except Exception as ex:                      # noqa: BLE001 — un objet inattendu : dit au modèle
                raise StepToolError(f'{where}.drawing: {type(ex).__name__}: {ex}') from ex
            if len(got) != 1 and 'holes' in b:
                raise StepToolError(f'{where}: these contours make {len(got)} separate parts: "holes" go with one')
            if len(got) != 1:
                for k, p in enumerate(got):
                    p.name, p.color, p.matrix = f'{name}_{k + 1}', color, m
                    out.append(p)
                continue
            body = got[0]
            body.name, body.color = name, color
        elif kinds[0] == 'revolve':
            rv = b['revolve']
            if not isinstance(rv, dict) or 'profile' not in rv or set(rv) - {'profile', 'holes', 'cx', 'cy'}:
                raise StepToolError(f'{where}.revolve: {{"profile": [[z, r], ...], "holes", "cx", "cy"}}')
            prof = rv['profile']
            if not isinstance(prof, list) or not 2 <= len(prof) <= MAX_SLABS + 1:
                raise StepToolError(f'{where}.revolve.profile: from 2 to {MAX_SLABS + 1} points [z, r]')
            prof = [tuple(_nums(p, 2, f'{where}.revolve.profile[{k}]')) for k, p in enumerate(prof)]
            if any(z1 < z0 for (z0, _a), (z1, _b) in zip(prof, prof[1:])):
                raise StepToolError(f'{where}.revolve.profile: read from bottom to top (z never decreasing)')
            if any(r <= 0 for _z, r in prof):
                raise StepToolError(f'{where}.revolve.profile: every radius greater than 0 (a point on the axis: a '
                                    f'small radius such as 0.05)')
            body = B.revolve(prof, name, color, _num(rv.get('cx', 0.0), f'{where}.revolve.cx'),
                             _num(rv.get('cy', 0.0), f'{where}.revolve.cy'))
            for k, (z0, z1, lp) in enumerate(_holes(rv.get('holes', []), f'{where}.revolve.holes')):
                body = _cut_hole(body, z0, z1, lp, f'{where}.revolve.holes[{k}]')   # même règle que « holes »
        else:
            slabs = b['slabs']
            if not isinstance(slabs, list) or not 1 <= len(slabs) <= MAX_SLABS:
                raise StepToolError(f'{where}.slabs: from 1 to {MAX_SLABS} slabs')
            ss = []
            for k, s in enumerate(slabs):
                w = f'{where}.slabs[{k}]'
                if not isinstance(s, dict) or set(s) != {'z0', 'z1', 'loops'}:
                    raise StepToolError(f'{w}: {{"z0", "z1", "loops"}}')
                z0, z1 = _num(s['z0'], f'{w}.z0'), _num(s['z1'], f'{w}.z1')
                if not z1 > z0:
                    raise StepToolError(f'{w}: z1 must be greater than z0')
                if not isinstance(s['loops'], list) or not 1 <= len(s['loops']) <= MAX_LOOPS:
                    raise StepToolError(f'{w}.loops: from 1 to {MAX_LOOPS} loops')
                ss.append(B.Slab(z0, z1, [_loop_at(_loop(lp, f'{w}.loops[{j}]'), z0, z1, z0, z1)
                                          for j, lp in enumerate(s['loops'])]))
            body = B.Body(name, sorted(ss, key=lambda s: s.z0), color)
        for k, (z0, z1, lp) in enumerate(_holes(b.get('holes', []), f'{where}.holes')):
            body = _cut_hole(body, z0, z1, lp, f'{where}.holes[{k}]')
        body.matrix = m
        _simple(body, f'{where} ({name})')
        try:
            B.check(body)
        except B.BrepError as ex:
            raise StepToolError(f'{where} ({name}): {ex}') from ex
        except Exception as ex:                          # noqa: BLE001 — shapely, calcul : dit au modèle
            raise StepToolError(f'{where} ({name}): {type(ex).__name__}: {ex}') from ex
        out.append(body)
    return out
