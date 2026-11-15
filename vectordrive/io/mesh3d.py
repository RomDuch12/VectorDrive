"""Pièces 3D maillées — STL et 3D XML (format d'échange ouvert de CATIA et
des logiciels Dassault) — et fichiers CATIA natifs par un convertisseur.

Comme le lecteur STEP, on en tire la **vue de dessus** utile à la gravure :
les faces horizontales tournées vers le haut, un calque par hauteur
(« Pz 0 », « Pz -2 »…, la plus haute d'abord), et la **silhouette** de la
pièce. Unités : millimètres.

CATIA V5 (.CATPart, .CATProduct, .cgr) est un format fermé : aucun lecteur
libre ne l'ouvre. Deux chemins :
- depuis CATIA, exporter en STEP (AP214 / AP242), 3D XML, STL ou, pour un
  plan (.CATDrawing), en DXF — VectorDrive les lit ;
- ou désigner dans F10 > Fichiers un convertisseur en ligne de commande
  (celui de CATIA en mode batch, un convertisseur du commerce…) qui écrit un
  STEP : VectorDrive l'appelle à l'ouverture (`{entree}`, `{sortie}`).
"""
from __future__ import annotations

import math
import os
import pathlib
import re
import shlex
import struct
import subprocess
import tempfile
import zipfile
import xml.etree.ElementTree as ET

from ..core import progress
from ..core.document import Document, Layer, Shape
from ..core.geom import Contour, Line, Path

CATIA_EXTENSIONS = ('.catpart', '.catproduct', '.cgr', '.catdrawing')
#: réglage : commande du convertisseur CATIA → STEP
CONVERTER_KEY = 'import/convertisseur_cao'
UP = 0.995                   # face « horizontale tournée vers le haut » : composante z de la normale
LEVEL = 0.01                 # mm : faces de même hauteur à ce près


# --- lecture des maillages ------------------------------------------------------------------
def read_stl(path):
    """Triangles (n, 3, 3) d'un STL binaire ou texte."""
    import numpy as np
    data = pathlib.Path(path).read_bytes()
    if len(data) >= 84:
        n = struct.unpack_from('<I', data, 80)[0]
        if 84 + 50 * n == len(data):
            rec = np.dtype([('n', '<f4', 3), ('v', '<f4', (3, 3)), ('a', '<u2')])
            arr = np.frombuffer(data, rec, count=n, offset=84)
            return arr['v'].astype(float)
    text = data.decode('latin-1', errors='replace')
    if 'facet' not in text:
        raise ValueError('STL illisible (ni binaire ni texte)')
    nums = re.findall(r'vertex\s+(\S+)\s+(\S+)\s+(\S+)', text)
    v = np.array(nums, dtype=float)
    if len(v) % 3:
        raise ValueError('STL texte incomplet')
    return v.reshape(-1, 3, 3)


def _local(tag: str) -> str:
    return tag.rsplit('}', 1)[-1]


def _xsi_type(el) -> str:
    for k, v in el.attrib.items():
        if _local(k) == 'type':
            return v.split(':')[-1]
    return ''


def _indices(text: str) -> list[list[int]]:
    """'0 1 2,3 4 5' → [[0, 1, 2], [3, 4, 5]]."""
    return [[int(x) for x in grp.split()] for grp in (text or '').split(',') if grp.strip()]


def _rep_triangles(rep) -> list:
    """Triangles d'une représentation polygonale 3D XML."""
    pos = None
    for el in rep.iter():
        if _local(el.tag) == 'Positions' and el.text:
            pts = []
            for trip in el.text.replace('\n', ' ').split(','):
                c = trip.split()
                if len(c) >= 3:
                    pts.append((float(c[0]), float(c[1]), float(c[2])))
            pos = pts
            break
    if not pos:
        return []
    tris = []
    for el in rep.iter():
        if _local(el.tag) != 'Face':
            continue
        for grp in _indices(el.get('triangles', '')):
            for k in range(0, len(grp) - 2, 3):
                tris.append((grp[k], grp[k + 1], grp[k + 2]))
        for grp in _indices(el.get('strips', '')):
            for k in range(len(grp) - 2):
                a, b, c = grp[k], grp[k + 1], grp[k + 2]
                tris.append((a, b, c) if k % 2 == 0 else (b, a, c))
        for grp in _indices(el.get('fans', '')):
            for k in range(1, len(grp) - 1):
                tris.append((grp[0], grp[k], grp[k + 1]))
    n = len(pos)
    return [(pos[a], pos[b], pos[c]) for a, b, c in tris if a < n and b < n and c < n]


def _matrix(text: str):
    """RelativeMatrix 3D XML (12 nombres : rotation par colonnes, translation) → 4×4."""
    import numpy as np
    v = [float(x) for x in (text or '').split()]
    if len(v) != 12:
        return np.eye(4)
    m = np.eye(4)
    m[:3, 0], m[:3, 1], m[:3, 2], m[:3, 3] = v[0:3], v[3:6], v[6:9], v[9:12]
    return m


def read_3dxml(path):
    """Triangles (n, 3, 3) d'un fichier 3D XML : représentations polygonales
    placées selon la structure produit (instances, matrices)."""
    import numpy as np
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        files = {}
        for name in names:
            if name.lower().endswith(('.3drep', '.3dxml', '.xml')):
                try:
                    files[name] = ET.fromstring(z.read(name))
                except ET.ParseError:
                    continue
    reps: dict[str, list] = {}                       # fichier → triangles (repère local)
    for name, root in files.items():
        tris = []
        for el in root.iter():
            if _local(el.tag) == 'Rep' and _xsi_type(el) == 'PolygonalRepType':
                tris.extend(_rep_triangles(el))
        if tris:
            reps[name] = tris
    if not reps:
        raise ValueError('3D XML sans représentation polygonale (exporter en mode « tessellé »)')
    # structure produit
    refs, inst3d, refreps, instreps, root_id = {}, [], {}, [], None
    for root in files.values():
        for el in root.iter():
            t = _local(el.tag)
            if t == 'ProductStructure' and el.get('root'):
                root_id = el.get('root')
            elif t == 'Reference3D':
                refs[el.get('id')] = el
            elif t == 'Instance3D':
                kids = {_local(c.tag): (c.text or '').strip() for c in el}
                inst3d.append((kids.get('IsAggregatedBy'), kids.get('IsInstanceOf'), _matrix(kids.get('RelativeMatrix'))))
            elif t == 'ReferenceRep':
                refreps[el.get('id')] = (el.get('associatedFile') or '').split(':')[-1]
            elif t == 'InstanceRep':
                kids = {_local(c.tag): (c.text or '').strip() for c in el}
                instreps.append((kids.get('IsAggregatedBy'), kids.get('IsInstanceOf')))
    world: dict[str, list] = {}

    def placements(ref_id, depth=0):
        if ref_id in world:
            return world[ref_id]
        if depth > 50:
            return [np.eye(4)]
        parents = [(agg, m) for agg, inst, m in inst3d if inst == ref_id]
        if not parents or ref_id == root_id:
            out = [np.eye(4)]
        else:
            out = [pm @ m for agg, m in parents for pm in placements(agg, depth + 1)]
        world[ref_id] = out
        return out

    def rep_tris(file_ref: str):
        for name, tris in reps.items():
            if name == file_ref or name.endswith('/' + file_ref) or pathlib.PurePosixPath(name).name == file_ref:
                return tris
        return None

    out = []
    for agg, rr in instreps:
        fname = refreps.get(rr, '')
        tris = rep_tris(fname) if fname else None
        if not tris:
            continue
        T = np.array(tris, dtype=float)
        for m in placements(agg):
            P = T @ m[:3, :3].T + m[:3, 3]
            out.append(P)
    if not out:                                         # pas de structure lisible : tout tel quel
        out = [np.array(t, dtype=float) for t in reps.values()]
    return np.concatenate(out, axis=0)


# --- vue de dessus ------------------------------------------------------------------------------
def _contours(geom_) -> list[Contour]:
    out = []
    polys = getattr(geom_, 'geoms', [geom_])
    for poly in polys:
        if poly.is_empty or not hasattr(poly, 'exterior'):
            continue
        for ring in [poly.exterior] + list(poly.interiors):
            pts = list(ring.coords)
            segs = [Line(a, b) for a, b in zip(pts, pts[1:]) if math.dist(a, b) > 1e-9]
            if len(segs) >= 2:
                out.append(Contour(segs, True))
    return out


def top_view(tris, name: str = 'pièce', *, silhouette: bool = True, flat=None, close: float = 0.0) -> Document:
    """Document de la vue de dessus : un calque par hauteur de faces
    horizontales tournées vers le haut, et la silhouette. `flat` : les seuls
    triangles qui peuvent donner une hauteur (masque) ; `close` : referme les
    fentes de cette largeur entre des faces maillées à part (mm)."""
    import numpy as np
    import shapely
    T = np.asarray(tris, dtype=float)
    if T.ndim != 3 or len(T) == 0:
        raise ValueError('aucun triangle')
    N = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0])
    L = np.linalg.norm(N, axis=1)
    ok = L > 1e-12
    T, N, L = T[ok], N[ok], L[ok]
    nz = N[:, 2] / L
    up = nz > UP
    if flat is not None:
        up = up & np.asarray(flat, dtype=bool)[ok]
    z = np.round(T[:, :, 2].mean(axis=1) / LEVEL) * LEVEL
    doc = Document(layers=[], source_format='mesh')
    levels = sorted(set(z[up].tolist()), reverse=True)
    groups = [(f'Pz {lv:g}', np.nonzero(up & (z == lv))[0]) for lv in levels]
    if silhouette:
        groups.append(('Silhouette', np.nonzero(np.abs(nz) > 1e-6)[0]))
    for gi, (lname, idx) in enumerate(groups):
        progress.step(gi, len(groups), 'Vue de dessus : niveau {0} sur {1}')
        tri = T[idx][:, :, :2]                           # les triangles du niveau, vus de dessus
        area2 = (tri[:, 1, 0] - tri[:, 0, 0]) * (tri[:, 2, 1] - tri[:, 0, 1]) \
            - (tri[:, 2, 0] - tri[:, 0, 0]) * (tri[:, 1, 1] - tri[:, 0, 1])
        tri = tri[np.abs(area2) > 1e-12]                 # sans ceux vus par la tranche
        if not len(tri):
            continue
        merged = shapely.union_all(shapely.polygons(tri)).buffer(0)      # tous d'un coup : pas un objet par triangle
        if close > 0:
            merged = merged.buffer(close).buffer(-close)
        merged = merged.simplify(0.001)
        cs = _contours(merged)
        if not cs:
            continue
        tool = gi % 16
        doc.layers.append(Layer(name=lname, items=[Shape(path=Path(cs), tool=tool)], tool=tool))
    bb = T.reshape(-1, 3)
    doc.report = [f'{name} : {len(T)} triangles, {len(levels)} hauteur(s) de faces vers le haut, '
                  f'pièce {np.ptp(bb[:, 0]):.2f} × {np.ptp(bb[:, 1]):.2f} × {np.ptp(bb[:, 2]):.2f} mm']
    if not doc.layers:
        doc.layers.append(Layer(name=name))
    return doc


def read(path) -> Document:
    """STL ou 3D XML → vue de dessus."""
    ext = pathlib.Path(path).suffix.lower()
    tris = read_3dxml(path) if ext == '.3dxml' else read_stl(path)
    doc = top_view(tris, pathlib.Path(path).name)
    doc.source_path, doc.source_format = str(path), ext.lstrip('.')
    return doc


# --- CATIA -------------------------------------------------------------------------------------
def converter_command(settings=None) -> str:
    if settings is None:
        try:
            from ..portable import settings as _s
            settings = _s()
        except Exception:
            return ''
    return str(settings.value(CONVERTER_KEY, '') or '').strip()


def convert_command(template: str, src: str, dst: str) -> list[str]:
    """Arguments du convertisseur : `{entree}` et `{sortie}` remplacés (sans
    passer par l'interpréteur de commandes)."""
    args = shlex.split(template, posix=False)
    out = []
    for a in args:
        a = a.strip('"')
        out.append(a.replace('{entree}', src).replace('{sortie}', dst)
                    .replace('{input}', src).replace('{output}', dst))
    if not any('{entree}' in a or '{input}' in a for a in args):
        out.append(src)
    if not any('{sortie}' in a or '{output}' in a for a in args):
        out.append(dst)
    return out


def read_catia(path, settings=None, *, timeout: float = 600) -> Document:
    """Fichier CATIA : converti en STEP par le convertisseur désigné, puis lu
    comme un STEP (vue de dessus). Sans convertisseur : message explicatif."""
    ext = pathlib.Path(path).suffix.lower()
    tpl = converter_command(settings)
    if not tpl:
        what = 'un plan' if ext == '.catdrawing' else 'une pièce'
        raise ValueError(
            f'{pathlib.Path(path).name} : format CATIA fermé, aucun lecteur libre ne l\'ouvre.\n'
            f'Depuis CATIA, enregistrer {what} en '
            + ('DXF (Fichier > Enregistrer sous > dxf)' if ext == '.catdrawing'
               else 'STEP (AP214 ou AP242), 3D XML ou STL')
            + ', puis l\'ouvrir dans VectorDrive ; ou désigner un convertisseur CATIA → STEP '
              'dans F10 > Fichiers (commande avec {entree} et {sortie}).')
    with tempfile.TemporaryDirectory(prefix='vd_cao_') as tmp:
        dst = os.path.join(tmp, pathlib.Path(path).stem + '.stp')
        cmd = convert_command(tpl, str(path), dst)
        progress.check()
        try:
            r = subprocess.run(cmd, capture_output=True, timeout=timeout,
                               creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        except (OSError, subprocess.TimeoutExpired) as ex:
            raise ValueError(f'convertisseur CATIA : {ex}') from ex
        if not os.path.isfile(dst):
            err = (r.stderr or r.stdout or b'').decode('utf-8', errors='replace').strip()[-400:]
            raise ValueError(f'le convertisseur n\'a pas écrit de STEP (code {r.returncode}) {err}')
        from . import step
        doc = step.read(dst)
    doc.source_path, doc.source_format = str(path), 'catia'
    doc.report.insert(0, f'CATIA converti en STEP par : {cmd[0]}')
    return doc
