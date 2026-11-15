"""STEP en volume: toute la pièce — ou tout l'assemblage — pour la voir.

`stepread` tire d'un STEP ce qu'une fraiseuse usine depuis le dessus.
Ici on lit TOUT, sans noyau de CAO:

- la structure du produit: pièces, sous-assemblages et leurs
  positions (NEXT_ASSEMBLY_USAGE_OCCURRENCE + transformations,
  MAPPED_ITEM), chaque pièce placée où l'assemblage la met;
- tous les solides et coques: MANIFOLD_SOLID_BREP, BREP_WITH_VOIDS,
  FACETED_BREP (POLY_LOOP), SHELL_BASED_SURFACE_MODEL, faces
  triangulées AP242 (TRIANGULATED_FACE, COMPLEX_TRIANGULATED_FACE);
- toutes les surfaces, maillées pour l'ombrage: plan, cylindre, cône,
  sphère, tore, B-spline (rationnelle ou non), surface de révolution,
  d'extrusion. Chaque face est triangulée dans son espace (u, v), ses
  trous respectés (Delaunay contraint), puis replacée sur la surface;
- toutes les arêtes (droites, cercles, ellipses, B-splines, courbes
  coupées, polylignes) — sans les coutures des cylindres, qui ne sont
  pas des arêtes de la pièce;
- les couleurs du fichier (pièce ou face).

`instances()` sert aussi à `stepread.lire`: le 2D d'un assemblage
pose chaque pièce à sa place, et une pièce exportée couchée est
redressée.
"""

import math
from collections import Counter
from typing import Dict, List, Tuple

import numpy as np

from .stepread import StepError, Ref, lire_entites, _Modele, EPS
from .dxfimport import Cancelled

#: types de représentation de forme qui portent de la géométrie
_SOLIDES = ('MANIFOLD_SOLID_BREP', 'BREP_WITH_VOIDS', 'FACETED_BREP',
            'SHELL_BASED_SURFACE_MODEL', 'CLOSED_SHELL', 'OPEN_SHELL',
            'TESSELLATED_SOLID', 'TESSELLATED_SHELL', 'MAPPED_ITEM',
            'ADVANCED_FACE', 'FACE_SURFACE', 'TRIANGULATED_FACE',
            'COMPLEX_TRIANGULATED_FACE', 'GEOMETRIC_CURVE_SET',
            'GEOMETRIC_SET')

#: une surface au-delà de ce nombre de triangles est allégée
_MAX_TRI_FACE = 20000


# ──── Transformations rigides (R 3×3, t 3) ────

IDENTITE = (np.eye(3), np.zeros(3))


def composer(a, b):
    """a ∘ b: appliquer b, puis a."""
    return (a[0] @ b[0], a[0] @ b[1] + a[1])


def inverse(a):
    rt = a[0].T
    return (rt, -rt @ a[1])


def appliquer(T, pts):
    """Points (N, 3) transformés."""
    if T is None:
        return pts
    return pts @ T[0].T + T[1]


def _cadre_brut(mod: _Modele, ref):
    """Le repère AXIS2_PLACEMENT_3D d'une entité, en coordonnées du
    fichier (transformation courante NON appliquée), comme transformation
    local → fichier."""
    a = mod.args(ref)
    if not a:
        return IDENTITE
    loc = _point_brut(mod, a[1])
    w = _dir_brute(mod, a[2] if len(a) > 2 else None, (0.0, 0.0, 1.0))
    u = _dir_brute(mod, a[3] if len(a) > 3 else None, (1.0, 0.0, 0.0))
    u = u - np.dot(u, w) * w
    if np.linalg.norm(u) < 1e-9:
        u = np.array([1.0, 0.0, 0.0]) if abs(w[0]) < 0.9 \
            else np.array([0.0, 1.0, 0.0])
        u = u - np.dot(u, w) * w
    u = u / np.linalg.norm(u)
    v = np.cross(w, u)
    return (np.column_stack([u, v, w]), loc)


def _point_brut(mod, ref):
    ent = mod.e.get(int(ref)) if ref is not None else None
    if ent and ent[0] == 'VERTEX_POINT':
        return _point_brut(mod, ent[1][1])
    if ent and ent[0] == 'CARTESIAN_POINT':
        c = list(ent[1][1]) + [0.0, 0.0, 0.0]
        return np.array(c[:3], dtype=float) * mod.f
    return np.zeros(3)


def _dir_brute(mod, ref, defaut):
    if ref is None or mod.type_de(ref) != 'DIRECTION':
        return np.array(defaut, dtype=float)
    c = (list(mod.args(ref)[1]) + [0.0, 0.0, 0.0])[:3]
    v = np.array(c, dtype=float)
    n = np.linalg.norm(v)
    return v / n if n > 0 else np.array(defaut, dtype=float)


# ──── Structure du produit ────

def _types(ent) -> Tuple[str, ...]:
    """Les noms de type d'une entité (plusieurs pour une complexe)."""
    if not ent:
        return ()
    return tuple(ent[1].keys()) if ent[0] == '*' else (ent[0],)


def _partie(ent, nom):
    """Les arguments d'un type dans une entité (simple ou complexe)."""
    if not ent:
        return None
    if ent[0] == '*':
        return ent[1].get(nom)
    return ent[1] if ent[0] == nom else None


class Instance:
    """Une pièce placée: sa transformation, ses éléments de forme."""

    def __init__(self, T, items, nom=""):
        self.T = T
        self.items = list(items)
        self.nom = nom


def instances(mod: _Modele) -> List[Instance]:
    """Toutes les pièces du fichier, chacune à sa place.

    La structure produit (PRODUCT_DEFINITION, assemblages) quand elle
    existe; à défaut, tous les solides du fichier, tels quels."""
    e = mod.e
    reps = {}               # n -> items
    for n, ent in e.items():
        for t in _types(ent):
            if t.endswith('REPRESENTATION') and 'SHAPE' in t:
                a = _partie(ent, t)
                if a and len(a) >= 2 and isinstance(a[1], list):
                    reps[n] = [r for r in a[1] if isinstance(r, Ref)]
                elif ent[0] == '*' and 'REPRESENTATION' in ent[1]:
                    ra = ent[1]['REPRESENTATION']
                    if len(ra) >= 2 and isinstance(ra[1], list):
                        reps[n] = [r for r in ra[1] if isinstance(r, Ref)]
                break
    # liens SANS transformation: même pièce, deux représentations
    meme = {n: {n} for n in reps}

    def _unir(a, b):
        if a not in meme or b not in meme:
            return
        groupe = meme[a] | meme[b]
        for k in groupe:
            meme[k] = groupe

    liens_t = []            # (rep_1, rep_2, transformation, n)
    for n, ent in e.items():
        ts = _types(ent)
        if 'CONSTRUCTIVE_GEOMETRY_REPRESENTATION_RELATIONSHIP' in ts:
            continue
        rr = (_partie(ent, 'REPRESENTATION_RELATIONSHIP')
              or _partie(ent, 'SHAPE_REPRESENTATION_RELATIONSHIP'))
        if not rr or len(rr) < 4:
            continue
        r1, r2 = rr[2], rr[3]
        trans = _partie(ent, 'REPRESENTATION_RELATIONSHIP_WITH_TRANSFORMATION')
        if trans:
            liens_t.append((int(r1), int(r2), trans[0], n))
        else:
            _unir(int(r1), int(r2))

    # produit -> représentations; occurrences d'assemblage
    pds_def = {}            # PRODUCT_DEFINITION_SHAPE -> définition
    for n, (t, a) in e.items():
        if t == 'PRODUCT_DEFINITION_SHAPE' and len(a) >= 3:
            pds_def[n] = int(a[2]) if a[2] is not None else None
    rep_de = {}             # PD -> {reps}
    for n, (t, a) in e.items():
        if t == 'SHAPE_DEFINITION_REPRESENTATION' and len(a) >= 2:
            d = pds_def.get(int(a[0]))
            if d is not None and int(a[1]) in reps:
                rep_de.setdefault(d, set()).update(meme[int(a[1])])
    nauo = []               # (n, parent, enfant)
    for n, (t, a) in e.items():
        if t == 'NEXT_ASSEMBLY_USAGE_OCCURRENCE' and len(a) >= 5:
            nauo.append((n, int(a[3]), int(a[4])))
    cdsr = {}               # NAUO -> lien transformé
    lien_par_n = {l[3]: l for l in liens_t}
    for n, (t, a) in e.items():
        if t == 'CONTEXT_DEPENDENT_SHAPE_REPRESENTATION' and len(a) >= 2:
            nd = pds_def.get(int(a[1]))
            if nd is not None and int(a[0]) in lien_par_n:
                cdsr[nd] = lien_par_n[int(a[0])]

    def _nom_pd(pd):
        try:
            pdf = mod.args(mod.args(pd)[2])
            prod = mod.args(pdf[2])
            return str(prod[1] or prod[0] or "")
        except (IndexError, TypeError, ValueError):
            return ""

    sortie: List[Instance] = []
    if rep_de:
        enfants = {}
        for n, p, c in nauo:
            enfants.setdefault(p, []).append((n, c))
        racines = [pd for pd in rep_de if pd not in {c for _n, _p, c in nauo}]
        racines += [pd for pd in {p for _n, p, _c in nauo}
                    if pd not in rep_de
                    and pd not in {c for _n, _p, c in nauo}]

        def _descendre(pd, T, profondeur):
            if profondeur > 30:
                return
            groupe = rep_de.get(pd, set())
            items = []
            for r in groupe:
                items += reps.get(r, [])
            if items:
                sortie.append(Instance(T, items, _nom_pd(pd)))
            for n, c in enfants.get(pd, []):
                Tc = IDENTITE
                lien = cdsr.get(n)
                if lien is not None:
                    Tc = _transformation_lien(
                        mod, lien, rep_de.get(c, set()), groupe)
                _descendre(c, composer(T, Tc), profondeur + 1)

        for pd in racines:
            _descendre(pd, IDENTITE, 0)
    if not any(_a_de_la_forme(mod, inst.items) for inst in sortie):
        # pas de structure lisible: tous les solides, tels quels
        tous = [n for n, ent in e.items()
                if ent[0] in ('MANIFOLD_SOLID_BREP', 'BREP_WITH_VOIDS',
                              'FACETED_BREP', 'SHELL_BASED_SURFACE_MODEL',
                              'TESSELLATED_SOLID', 'TESSELLATED_SHELL')]
        if not tous:
            tous = [n for n, ent in e.items()
                    if ent[0] in ('ADVANCED_FACE', 'FACE_SURFACE',
                                  'TRIANGULATED_FACE',
                                  'COMPLEX_TRIANGULATED_FACE')]
        sortie = [Instance(IDENTITE, [Ref(n) for n in tous])]
    return sortie


def _a_de_la_forme(mod, items) -> bool:
    for r in items:
        t = mod.type_de(r)
        if t in _SOLIDES:
            return True
    return False


def _transformation_lien(mod, lien, reps_enfant, reps_parent):
    """La transformation enfant → parent d'un lien d'assemblage.

    ITEM_DEFINED_TRANSFORMATION relie deux repères: celui qui
    appartient à la représentation de l'ENFANT est le départ, l'autre
    l'arrivée (on vérifie l'appartenance; à défaut, item 1 = enfant,
    l'usage courant)."""
    r1, r2, trans, _n = lien
    ent = mod.e.get(int(trans)) if trans is not None else None
    if not ent:
        return IDENTITE
    if ent[0] == 'ITEM_DEFINED_TRANSFORMATION' and len(ent[1]) >= 4:
        i1, i2 = int(ent[1][2]), int(ent[1][3])

        def _items(reps):
            s = set()
            for r in reps:
                s.update(int(x) for x in (mod.args(r)[1]
                                          if len(mod.args(r)) > 1
                                          and isinstance(mod.args(r)[1], list)
                                          else []))
            return s
        enfant = _items(reps_enfant) | _items({r1} if r1 in reps_enfant
                                              else set())
        parent = _items(reps_parent)
        depart, arrivee = i1, i2
        if i2 in enfant and i1 not in enfant:
            depart, arrivee = i2, i1
        elif i1 in parent and i2 not in parent:
            depart, arrivee = i2, i1
        A = _cadre_brut(mod, depart)
        B = _cadre_brut(mod, arrivee)
        return composer(B, inverse(A))
    if ent[0] in ('CARTESIAN_TRANSFORMATION_OPERATOR_3D',
                  'CARTESIAN_TRANSFORMATION_OPERATOR'):
        a = ent[1]
        try:
            ax1 = _dir_brute(mod, a[2], (1.0, 0.0, 0.0))
            ax2 = _dir_brute(mod, a[3], (0.0, 1.0, 0.0))
            o = _point_brut(mod, a[4])
            ax3 = _dir_brute(mod, a[6] if len(a) > 6 else None,
                             tuple(np.cross(ax1, ax2)))
            return (np.column_stack([ax1, ax2, ax3]), o)
        except (IndexError, TypeError):
            return IDENTITE
    return IDENTITE


def faces_et_courbes(mod: _Modele, items, T=IDENTITE, profondeur=0):
    """[(face, T)], [(courbe libre, T)] des éléments d'une
    représentation — MAPPED_ITEM développés."""
    faces, courbes = [], []
    vus = set()

    def _face(r, T):
        cle = (int(r), id(T))
        if cle in vus:
            return
        vus.add(cle)
        faces.append((int(r), T))

    def _coque(r, T):
        ent = mod.e.get(int(r))
        if not ent:
            return
        t, a = ent
        if t in ('CLOSED_SHELL', 'OPEN_SHELL', 'CONNECTED_FACE_SET'):
            for f in a[1]:
                _faces_de(f, T)
        elif t in ('ORIENTED_CLOSED_SHELL', 'ORIENTED_OPEN_SHELL'):
            _coque(a[2], T)

    def _faces_de(r, T):
        ent = mod.e.get(int(r))
        if not ent:
            return
        if ent[0] == 'ORIENTED_FACE':
            _faces_de(ent[1][2], T)
        else:
            _face(r, T)

    def _item(r, T, prof):
        ent = mod.e.get(int(r))
        if not ent or prof > 20:
            return
        t, a = ent
        if t in ('MANIFOLD_SOLID_BREP', 'FACETED_BREP'):
            _coque(a[1], T)
        elif t == 'BREP_WITH_VOIDS':
            _coque(a[1], T)
            for v in a[2]:
                _coque(v, T)
        elif t == 'SHELL_BASED_SURFACE_MODEL':
            for c in a[1]:
                _coque(c, T)
        elif t in ('CLOSED_SHELL', 'OPEN_SHELL', 'ORIENTED_CLOSED_SHELL'):
            _coque(r, T)
        elif t in ('TESSELLATED_SOLID', 'TESSELLATED_SHELL'):
            for f in a[1]:
                _face(f, T)
        elif t in ('ADVANCED_FACE', 'FACE_SURFACE', 'TRIANGULATED_FACE',
                   'COMPLEX_TRIANGULATED_FACE'):
            _face(r, T)
        elif t == 'MAPPED_ITEM':
            source = mod.args(a[1])
            if len(source) >= 2:
                origine = _cadre_brut(mod, source[0]) \
                    if mod.type_de(source[0]) == 'AXIS2_PLACEMENT_3D' \
                    else IDENTITE
                cible = _cadre_brut(mod, a[2]) \
                    if mod.type_de(a[2]) == 'AXIS2_PLACEMENT_3D' \
                    else IDENTITE
                Tm = composer(T, composer(cible, inverse(origine)))
                rep = mod.args(source[1])
                for x in (rep[1] if len(rep) > 1
                          and isinstance(rep[1], list) else []):
                    _item(x, Tm, prof + 1)
        elif t in ('GEOMETRIC_CURVE_SET', 'GEOMETRIC_SET'):
            for x in a[1]:
                courbes.append((int(x), T))

    for r in items:
        _item(r, T, profondeur)
    return faces, courbes


def corps_des_faces(mod: _Modele, insts, noms: list) -> dict:
    """{(face, id(T)) et face : numéro du corps} : un corps par solide (élément de
    forme) de chaque pièce placée ; `noms` reçoit leurs noms (« Corps1 »,
    ou « pièce — Corps1 » dans un assemblage)."""
    out = {}
    plusieurs = sum(1 for i in insts if _a_de_la_forme(mod, i.items)) > 1
    for inst in insts:
        for r in inst.items:
            faces, _c = faces_et_courbes(mod, [r], inst.T)
            if not faces:
                continue
            ent = mod.e.get(int(r))
            nom = ''
            if ent and ent[1] and isinstance(ent[1][0], str):
                nom = ent[1][0].strip()
            nom = nom or f'Corps {len(noms) + 1}'
            if plusieurs and inst.nom:
                nom = f'{inst.nom} — {nom}'
            k = len(noms)
            noms.append(nom)
            for f, T in faces:
                out.setdefault((f, id(T)), k)
                out.setdefault(f, k)                       # repli : pièce placée par MAPPED_ITEM (autre T)
    return out


def toutes_les_faces(mod: _Modele, insts) -> list:
    """[(face, T)] de toutes les pièces placées — et, par sécurité,
    les faces qu'aucune pièce ne cite (fichier à la structure
    incomplète), telles quelles."""
    sortie = []
    for inst in insts:
        f, _c = faces_et_courbes(mod, inst.items, inst.T)
        sortie += f
    vues = {f for f, _T in sortie}
    for n, (typ, _a) in mod.e.items():
        if typ in ('ADVANCED_FACE', 'FACE_SURFACE') and n not in vues:
            sortie.append((n, IDENTITE))
    return sortie


# ──── Orientation: quel axe est le haut ? ────

ORIENTATIONS = {
    'Z': np.eye(3),
    # Y vers le haut (export « Y up »): y → z, z → -y
    'Y': np.array([[1.0, 0, 0], [0, 0, -1.0], [0, 1.0, 0]]),
    'X': np.array([[0, 0, -1.0], [0, 1.0, 0], [1.0, 0, 0]]),
}


def surfaces_planes_par_axe(mod: _Modele, faces) -> Dict[str, float]:
    """Aire des faces planes selon l'axe de leur normale (X, Y, Z):
    une pièce de fraisage pose ses grandes faces à plat."""
    aires = {'X': 0.0, 'Y': 0.0, 'Z': 0.0}
    for f, T in faces:
        ent = mod.e.get(f)
        if not ent or ent[0] not in ('ADVANCED_FACE', 'FACE_SURFACE'):
            continue
        a = ent[1]
        surf = mod.e.get(int(a[2])) if a[2] is not None else None
        if not surf or surf[0] != 'PLANE':
            continue
        R, c = composer(T, _cadre_brut(mod, surf[1][1]))
        w = R[:, 2]
        axe = 'XYZ'[int(np.argmax(np.abs(w)))]
        if abs(w['XYZ'.index(axe)]) < 0.999:
            continue
        aire = 0.0
        for b in a[1]:
            pts = _sommets_boucle(mod, b)
            if len(pts) >= 3:
                P = appliquer(T, np.array(pts))
                uv = (P - c) @ R[:, :2]
                x, y = uv[:, 0], uv[:, 1]
                s = 0.5 * (np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))
                aire += s
        aires[axe] += abs(aire)
    return aires


def _sommets_boucle(mod, ref_bord):
    a = mod.args(ref_bord)
    if len(a) < 2:
        return []
    boucle = mod.e.get(int(a[1]))
    if not boucle:
        return []
    if boucle[0] == 'POLY_LOOP':
        return [tuple(_point_brut(mod, p)) for p in boucle[1][1]]
    if boucle[0] != 'EDGE_LOOP':
        return []
    pts = []
    for oe in boucle[1][1]:
        o = mod.args(oe)
        if len(o) < 5:
            continue
        ec = mod.args(o[3])
        if len(ec) < 3:
            continue
        va = ec[1] if o[4] == 'T' else ec[2]
        pts.append(tuple(_point_brut(mod, va)))
    return pts


def axe_haut_probable(mod: _Modele, faces) -> str:
    """Le haut de la pièce: une pièce de fraisage pose ses grandes
    faces planes À PLAT. 'Z' sauf si les faces normales à Y (ou X)
    sont nettement plus grandes — plus du double: la pièce a été
    exportée couchée."""
    aires = surfaces_planes_par_axe(mod, faces)
    meilleur = 'Y' if aires['Y'] >= aires['X'] else 'X'
    if aires[meilleur] > 2.0 * aires['Z'] and aires[meilleur] > 0:
        return meilleur
    return 'Z'


# ──── Le modèle 3D ────

class Modele3D:
    """Une pièce (ou un assemblage) maillée, prête à afficher."""

    def __init__(self):
        self.triangles = np.zeros((0, 3, 3))
        self.couleurs = np.zeros((0, 3))
        self.aretes: List[np.ndarray] = []
        self.notes: List[str] = []
        self.n_instances = 0
        self.n_faces = 0
        self.n_faces_maillees = 0
        self.non_maillees: Counter = Counter()
        self.surfaces: Counter = Counter()
        self.unite_mm = 1.0
        self.axe_haut = 'Z'
        self.noms: List[str] = []
        #: les faces maillées (voir `info_face`), et pour chaque
        #: triangle l'index de sa face
        self.faces: List[Dict] = []
        self.face_de = np.zeros(0, dtype=int)
        #: les corps (solides) : leur nom ; chaque face sait le sien ('corps')
        self.corps: List[str] = []

    def bornes(self):
        pts = [self.triangles.reshape(-1, 3)] + list(self.aretes)
        pts = [p for p in pts if len(p)]
        if not pts:
            return None
        tous = np.vstack(pts)
        return (*tous.min(axis=0), *tous.max(axis=0))

    def aire(self) -> float:
        t = self.triangles
        if not len(t):
            return 0.0
        return float(0.5 * np.linalg.norm(
            np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0]), axis=1).sum())

    def resume(self) -> str:
        txt = (f"{self.n_faces} faces ({self.n_faces_maillees} maillées), "
               f"{len(self.triangles)} triangles, {len(self.aretes)} "
               f"arêtes")
        if self.n_instances > 1:
            txt += f", {self.n_instances} pièces"
        return txt


#: couleur par défaut des pièces sans couleur: aluminium
_ALU = (0.70, 0.74, 0.80)


class _Mailleur:
    """Maille les faces d'un modèle; une arête n'est échantillonnée
    qu'une fois par pièce placée."""

    def __init__(self, mod: _Modele, tolerance: float):
        self.mod = mod
        self.tol = max(1e-4, float(tolerance))
        self.cache_aretes = {}
        self.unite_angle = _unite_angle(mod)
        self.couleur_de = _couleurs(mod)
        #: boucles et paramétrage de la dernière face maillée
        self.derniere = None

    # -- courbes --

    def points_arete(self, ec_ref, T):
        """Les points d'une EDGE_CURVE, de son départ à son arrivée
        (sens de l'arête), en coordonnées placées."""
        cle = (int(ec_ref), id(T))
        p = self.cache_aretes.get(cle)
        if p is None:
            p = appliquer(T, self._points_arete_brut(ec_ref))
            self.cache_aretes[cle] = p
        return p

    def _points_arete_brut(self, ec_ref):
        mod = self.mod
        ec = mod.args(ec_ref)
        if len(ec) < 5:
            return np.zeros((0, 3))
        pa, pb = _point_brut(mod, ec[1]), _point_brut(mod, ec[2])
        sens = ec[4] == 'T'
        ferme = int(ec[1]) == int(ec[2]) or np.linalg.norm(pa - pb) < EPS
        pts = self.points_courbe(ec[3], pa, pb, sens, ferme)
        return pts

    def points_courbe(self, ref, pa, pb, sens, ferme):
        mod = self.mod
        ref = mod.courbe_3d(ref)
        ent = mod.e.get(int(ref)) if ref is not None else None
        if not ent:
            return np.array([pa, pb])
        t, a = ent
        if t == 'TRIMMED_CURVE':
            return self.points_courbe(a[1], pa, pb,
                                      sens == (a[4] == 'T'), ferme)
        if t == 'LINE':
            return np.array([pa, pb])
        if t in ('CIRCLE', 'ELLIPSE'):
            R, c = _cadre_brut(mod, a[1])
            ra = float(a[2]) * mod.f
            rb = float(a[3]) * mod.f if t == 'ELLIPSE' else ra

            def ang(p):
                d = (p - c) @ R
                return math.atan2(d[1] / rb, d[0] / ra)
            t0, t1 = ang(pa), ang(pb)
            if sens:
                b = (t1 - t0) % (2 * math.pi)
                if ferme and b < 1e-9:
                    b = 2 * math.pi
            else:
                b = -((t0 - t1) % (2 * math.pi))
                if ferme and b > -1e-9:
                    b = -2 * math.pi
            r = max(ra, rb)
            pas = 2 * math.acos(max(-1.0, min(1.0, 1 - self.tol / r))) \
                if r > self.tol else math.radians(20)
            pas = max(math.radians(1.0), min(pas, math.radians(10.0)))
            n = max(2, int(math.ceil(abs(b) / pas)) + 1)
            ts = t0 + b * np.linspace(0.0, 1.0, n)
            pts = (c + np.outer(ra * np.cos(ts), R[:, 0])
                   + np.outer(rb * np.sin(ts), R[:, 1]))
            pts[0], pts[-1] = pa, pb
            return pts
        if t == 'POLYLINE':
            pts = np.array([_point_brut(mod, p) for p in a[1]])
            if len(pts) >= 2:
                if not sens:
                    pts = pts[::-1]
                return pts
            return np.array([pa, pb])
        ech = self._echantillons_bspline(ref)
        if ech is not None and len(ech) >= 2:
            return _portion(ech, pa, pb, sens, ferme)
        return np.array([pa, pb])

    def _echantillons_bspline(self, ref):
        pts = self.mod.echantillons(ref)
        if not pts:
            return None
        # echantillons() applique la transformation courante du modèle:
        # ici, le modèle reste en coordonnées du fichier
        return np.array(pts, dtype=float)

    # -- faces --

    def boucles(self, face_args, T):
        """Les contours d'une face: [(points (N,3), extérieur ?)] en
        coordonnées placées, et les arêtes rencontrées."""
        mod = self.mod
        sortie = []
        aretes = []
        for b in face_args[1]:
            fb = mod.e.get(int(b))
            if not fb:
                continue
            fa = fb[1]
            boucle = mod.e.get(int(fa[1])) if len(fa) > 1 else None
            if not boucle:
                continue
            exterieur = fb[0] == 'FACE_OUTER_BOUND'
            orient = len(fa) < 3 or fa[2] != 'F'
            if boucle[0] == 'POLY_LOOP':
                pts = appliquer(T, np.array(
                    [_point_brut(mod, p) for p in boucle[1][1]]))
                if len(pts) >= 3:
                    sortie.append((pts if orient else pts[::-1], exterieur))
                    for i in range(len(pts)):
                        aretes.append(('poly', np.array(
                            [pts[i], pts[(i + 1) % len(pts)]])))
                continue
            if boucle[0] == 'VERTEX_LOOP':
                p = appliquer(T, np.array([_point_brut(mod, boucle[1][1])]))
                sortie.append((p, exterieur))
                continue
            if boucle[0] != 'EDGE_LOOP':
                continue
            morceaux = []
            utilisees = Counter(int(mod.args(oe)[3]) for oe in boucle[1][1]
                                if len(mod.args(oe)) >= 5)
            for oe in boucle[1][1]:
                o = mod.args(oe)
                if len(o) < 5:
                    continue
                pts = self.points_arete(o[3], T)
                if o[4] != 'T':
                    pts = pts[::-1]
                morceaux.append(pts)
                couture = (utilisees[int(o[3])] > 1
                           or mod.type_de(mod.args(o[3])[3])
                           == 'SEAM_CURVE')
                aretes.append((int(o[3]), None if couture else pts))
            if not morceaux:
                continue
            pts = morceaux[0]
            for m in morceaux[1:]:
                pts = np.vstack([pts, m[1:]]) if len(m) > 1 else pts
            if len(pts) > 1 and np.linalg.norm(pts[0] - pts[-1]) < 1e-7:
                pts = pts[:-1]
            if not orient:
                pts = pts[::-1]
            sortie.append((pts, exterieur))
        return sortie, aretes

    def mailler(self, face_ref, T):
        """Triangles (N,3,3) d'une face, ou None (surface non lue)."""
        mod = self.mod
        ent = mod.e.get(int(face_ref))
        if not ent:
            return None, [], ""
        t, a = ent
        if t == 'TRIANGULATED_FACE':
            return _triangulee(mod, a, T), [], 'TRIANGULATED_FACE'
        if t == 'COMPLEX_TRIANGULATED_FACE':
            return _triangulee_complexe(mod, a, T), [], \
                'COMPLEX_TRIANGULATED_FACE'
        if t == 'FACE' and len(a) >= 2:
            # face sans surface (FACETED_BREP issu d'un maillage): son
            # plan est celui de son polygone (normale de Newell)
            boucles, aretes = self.boucles(a, T)
            self.derniere = {'boucles': boucles, 'param': None,
                             'meme_sens': True}
            if not boucles or len(boucles[0][0]) < 3:
                return None, aretes, t
            P = boucles[0][0]
            n = np.zeros(3)
            for i in range(len(P)):
                p, q = P[i], P[(i + 1) % len(P)]
                n += [(p[1] - q[1]) * (p[2] + q[2]),
                      (p[2] - q[2]) * (p[0] + q[0]),
                      (p[0] - q[0]) * (p[1] + q[1])]
            if np.linalg.norm(n) < 1e-12:
                return None, aretes, t
            w = n / np.linalg.norm(n)
            u = P[1] - P[0]
            u = u - np.dot(u, w) * w
            if np.linalg.norm(u) < 1e-12:
                return None, aretes, t
            u = u / np.linalg.norm(u)
            plan = _Plan(np.column_stack([u, np.cross(w, u), w]), P[0])
            self.derniere['param'] = plan
            try:
                return _trianguler(plan, boucles, self.tol), aretes, 'FACE'
            except Exception:
                return None, aretes, 'FACE'
        if t not in ('ADVANCED_FACE', 'FACE_SURFACE') or len(a) < 3:
            return None, [], t
        boucles, aretes = self.boucles(a, T)
        surf = mod.e.get(int(a[2])) if a[2] is not None else None
        nom = surf[0] if surf else ""
        if nom == '*' and surf:
            nom = 'B_SPLINE_SURFACE' if 'B_SPLINE_SURFACE' in surf[1] \
                else '*'
        try:
            param = _parametrage(self, a[2], T, boucles)
        except Exception:
            param = None
        self.derniere = {'boucles': boucles, 'param': param,
                         'meme_sens': len(a) < 4 or a[3] != 'F'}
        if param is None or not boucles:
            return None, aretes, nom
        try:
            tri = _trianguler(param, boucles, self.tol,
                              sens_face=len(a) < 4 or a[3] != 'F')
        except Exception:
            tri = None
        return tri, aretes, nom


def _portion(ech, pa, pb, sens, ferme):
    """La portion d'une courbe échantillonnée entre deux sommets, dans
    le sens de l'arête."""
    if not sens:
        ech = ech[::-1]
    ia = int(np.argmin(np.linalg.norm(ech - pa, axis=1)))
    ib = int(np.argmin(np.linalg.norm(ech - pb, axis=1)))
    if ferme:
        pts = np.vstack([ech[ia:], ech[1:ia + 1]]) if ia else ech
    elif ib >= ia:
        pts = ech[ia:ib + 1]
    else:
        pts = np.vstack([ech[ia:], ech[1:ib + 1]])
    if len(pts) < 2:
        pts = np.array([pa, pb])
    pts = np.array(pts, dtype=float)
    pts[0], pts[-1] = pa, pb
    return pts


def _unite_angle(mod) -> float:
    """Radians par unité d'angle du fichier (1, ou π/180 en degrés)."""
    for nom, args in mod.e.values():
        if nom == '*' and 'PLANE_ANGLE_UNIT' in args:
            if 'CONVERSION_BASED_UNIT' in args:
                return math.pi / 180.0
            return 1.0
    return 1.0


def _couleurs(mod) -> Dict[int, tuple]:
    """{élément stylé: (r, g, b)} — STYLED_ITEM jusqu'à COLOUR_RGB."""
    nommees = {'red': (1, 0, 0), 'green': (0, 1, 0), 'blue': (0, 0, 1),
               'yellow': (1, 1, 0), 'magenta': (1, 0, 1),
               'cyan': (0, 1, 1), 'black': (0.1, 0.1, 0.1),
               'white': (1, 1, 1)}
    sortie = {}

    def _chercher(r, prof):
        if prof > 12:
            return None
        ent = mod.e.get(int(r))
        if not ent:
            return None
        t, a = ent
        if t == 'COLOUR_RGB' and len(a) >= 4:
            return (float(a[1]), float(a[2]), float(a[3]))
        if t == 'DRAUGHTING_PRE_DEFINED_COLOUR' and a:
            return nommees.get(str(a[0]).lower())
        if t == '*':
            return None
        for x in _refs(a):
            c = _chercher(x, prof + 1)
            if c is not None:
                return c
        return None

    for n, (t, a) in mod.e.items():
        if t in ('STYLED_ITEM', 'OVER_RIDING_STYLED_ITEM') and len(a) >= 3:
            c = None
            for s in (a[1] if isinstance(a[1], list) else []):
                c = _chercher(s, 0)
                if c is not None:
                    break
            if c is not None and a[2] is not None:
                sortie[int(a[2])] = c
    return sortie


def _refs(valeur):
    if isinstance(valeur, Ref):
        yield valeur
    elif isinstance(valeur, list):
        for v in valeur:
            yield from _refs(v)
    elif isinstance(valeur, tuple) and len(valeur) == 2:
        yield from _refs(valeur[1])


# ──── Paramétrage des surfaces: (u, v) <-> point ────

class _Param:
    """Une surface vue dans son plan (u, v): `uv(points)` et
    `point(uv)`, et la période en u (0 si aucune) — en v aussi pour le
    tore (angle autour du tube)."""
    periode_u = 0.0
    periode_v = 0.0
    courbe = False         # à subdiviser pour suivre la courbure
    pas_u = pas_v = None

    def v_pole(self, cote, v_boucle):
        """Le v du pôle (sphère) ou de la pointe (cône) du côté
        `cote` (+1: v croissant), ou None s'il n'y en a pas."""
        return None


class _Plan(_Param):
    def __init__(self, R, c):
        self.R, self.c = R, c

    def uv(self, P):
        return (P - self.c) @ self.R[:, :2]

    def point(self, UV):
        return self.c + UV[:, :1] * self.R[:, 0] + UV[:, 1:2] * self.R[:, 1]


class _Revolution(_Param):
    """Base des surfaces d'axe: angle θ autour de l'axe (u = θ·r_ref)."""
    courbe = True

    def _theta_h(self, P):
        d = (P - self.c) @ self.R
        return np.arctan2(d[:, 1], d[:, 0]), d[:, 2], np.hypot(d[:, 0],
                                                              d[:, 1])


class _Cylindre(_Revolution):
    def __init__(self, R, c, r, tol):
        self.R, self.c, self.r = R, c, max(r, 1e-9)
        self.periode_u = 2 * math.pi * self.r
        self.pas_u = _pas_angle(self.r, tol) * self.r

    def uv(self, P):
        th, h, _ = self._theta_h(P)
        return np.column_stack([th * self.r, h])

    def point(self, UV):
        th = UV[:, 0] / self.r
        return (self.c + np.outer(self.r * np.cos(th), self.R[:, 0])
                + np.outer(self.r * np.sin(th), self.R[:, 1])
                + np.outer(UV[:, 1], self.R[:, 2]))


class _Cone(_Revolution):
    def __init__(self, R, c, r, tan_a, tol, r_ref):
        self.R, self.c, self.r, self.k = R, c, r, tan_a
        self.s = max(r_ref, 1e-6)
        self.periode_u = 2 * math.pi * self.s
        self.pas_u = _pas_angle(self.s, tol) * self.s

    def uv(self, P):
        th, h, _ = self._theta_h(P)
        return np.column_stack([th * self.s, h])

    def v_pole(self, cote, v_boucle):
        if abs(self.k) < 1e-12:
            return None
        pointe = -self.r / self.k
        return pointe if (pointe - v_boucle) * cote > 0 else None

    def point(self, UV):
        th = UV[:, 0] / self.s
        rho = self.r + UV[:, 1] * self.k
        return (self.c + np.outer(rho * np.cos(th), self.R[:, 0])
                + np.outer(rho * np.sin(th), self.R[:, 1])
                + np.outer(UV[:, 1], self.R[:, 2]))


class _Sphere(_Revolution):
    def __init__(self, R, c, r, tol):
        self.R, self.c, self.r = R, c, max(r, 1e-9)
        self.periode_u = 2 * math.pi * self.r
        self.pas_u = self.pas_v = _pas_angle(self.r, tol) * self.r

    def uv(self, P):
        d = (P - self.c) @ self.R
        th = np.arctan2(d[:, 1], d[:, 0])
        ph = np.arcsin(np.clip(d[:, 2] / self.r, -1.0, 1.0))
        return np.column_stack([th * self.r, ph * self.r])

    def v_pole(self, cote, v_boucle):
        return cote * math.pi / 2 * self.r

    def point(self, UV):
        th, ph = UV[:, 0] / self.r, UV[:, 1] / self.r
        return (self.c + np.outer(self.r * np.cos(ph) * np.cos(th),
                                  self.R[:, 0])
                + np.outer(self.r * np.cos(ph) * np.sin(th), self.R[:, 1])
                + np.outer(self.r * np.sin(ph), self.R[:, 2]))


class _Tore(_Revolution):
    def __init__(self, R, c, grand, petit, tol):
        self.R, self.c = R, c
        self.a, self.b = max(grand, 1e-9), max(petit, 1e-9)
        self.periode_u = 2 * math.pi * self.a
        self.periode_v = 2 * math.pi * self.b             # autour du tube : ±π au côté intérieur
        self.pas_u = _pas_angle(self.a + self.b, tol) * self.a
        self.pas_v = _pas_angle(self.b, tol) * self.b

    def uv(self, P):
        d = (P - self.c) @ self.R
        th = np.arctan2(d[:, 1], d[:, 0])
        rho = np.hypot(d[:, 0], d[:, 1])
        ph = np.arctan2(d[:, 2], rho - self.a)
        return np.column_stack([th * self.a, ph * self.b])

    def point(self, UV):
        th, ph = UV[:, 0] / self.a, UV[:, 1] / self.b
        rho = self.a + self.b * np.cos(ph)
        return (self.c + np.outer(rho * np.cos(th), self.R[:, 0])
                + np.outer(rho * np.sin(th), self.R[:, 1])
                + np.outer(self.b * np.sin(ph), self.R[:, 2]))


class _Grille(_Param):
    """Toute surface qu'on sait ÉVALUER (B-spline, révolution d'une
    courbe, extrusion): les points du contour sont projetés sur une
    grille fine puis affinés (Newton), et l'on triangule en (u, v)."""
    courbe = True

    def __init__(self, evaluer, u0, u1, v0, v1, tol, nu=40, nv=40,
                 periode_u=0.0):
        self.f = evaluer
        self.u0, self.u1, self.v0, self.v1 = u0, u1, v0, v1
        self.periode_u = periode_u
        us = np.linspace(u0, u1, nu)
        vs = np.linspace(v0, v1, nv)
        UU, VV = np.meshgrid(us, vs, indexing='ij')
        self._g_uv = np.column_stack([UU.ravel(), VV.ravel()])
        self._g_p = self.f(self._g_uv)
        etendue = float(np.ptp(self._g_p, axis=0).max()) or 1.0
        # échelle (u, v) -> mm, pour des triangles bien formés
        du = np.linalg.norm(np.diff(self._g_p.reshape(nu, nv, 3), axis=0),
                            axis=2).sum(axis=0).mean() if nu > 1 else 1.0
        dv = np.linalg.norm(np.diff(self._g_p.reshape(nu, nv, 3), axis=1),
                            axis=2).sum(axis=1).mean() if nv > 1 else 1.0
        self.su = max(du / max(u1 - u0, 1e-12), 1e-9)
        self.sv = max(dv / max(v1 - v0, 1e-12), 1e-9)
        self.periode_u = periode_u * self.su
        n = max(4, min(60, int(math.ceil(etendue / max(tol * 40, 1e-6)))))
        self.pas_u = (u1 - u0) * self.su / n
        self.pas_v = (v1 - v0) * self.sv / n

    def _brut(self, P):
        d2 = ((self._g_p[None, :, :] - P[:, None, :]) ** 2).sum(axis=2) \
            if len(P) * len(self._g_p) < 4e6 else None
        if d2 is None:
            idx = np.array([int(np.argmin(((self._g_p - p) ** 2).sum(axis=1)))
                            for p in P])
        else:
            idx = np.argmin(d2, axis=1)
        uv = self._g_uv[idx].copy()
        h = 1e-6 * max(self.u1 - self.u0, self.v1 - self.v0, 1e-9)
        for _ in range(8):
            S = self.f(uv)
            Su = (self.f(uv + [h, 0.0]) - S) / h
            Sv = (self.f(uv + [0.0, h]) - S) / h
            r = P - S
            a11 = (Su * Su).sum(1)
            a12 = (Su * Sv).sum(1)
            a22 = (Sv * Sv).sum(1)
            b1 = (Su * r).sum(1)
            b2 = (Sv * r).sum(1)
            det = a11 * a22 - a12 * a12
            ok = np.abs(det) > 1e-18
            du = np.where(ok, (a22 * b1 - a12 * b2) / np.where(ok, det, 1), 0)
            dv = np.where(ok, (a11 * b2 - a12 * b1) / np.where(ok, det, 1), 0)
            uv[:, 0] = np.clip(uv[:, 0] + du, self.u0, self.u1)
            uv[:, 1] = np.clip(uv[:, 1] + dv, self.v0, self.v1)
        return uv

    def uv(self, P):
        uv = self._brut(P)
        return np.column_stack([uv[:, 0] * self.su, uv[:, 1] * self.sv])

    def point(self, UV):
        return self.f(np.column_stack([UV[:, 0] / self.su,
                                       UV[:, 1] / self.sv]))


def _pas_angle(r, tol):
    if r <= tol:
        return math.radians(30)
    a = 2 * math.acos(max(-1.0, min(1.0, 1 - tol / r)))
    return max(math.radians(2.0), min(a, math.radians(12.0)))


def _plage_extrusion(C, D, boucles, defaut=(-2.0, 3.0)):
    """Plage du paramètre v d'une extrusion (point = courbe + v·D) qui
    couvre le contour de la face, avec une marge ; `defaut` sans contour."""
    pts = [np.asarray(b, dtype=float) for b, _e in (boucles or ()) if len(b)]
    dd = float(D @ D)
    if not pts or dd <= 0:
        return defaut
    pv = np.vstack(pts) @ D / dd
    cv = C @ D / dd
    v0, v1 = float(pv.min() - cv.max()), float(pv.max() - cv.min())
    marge = 0.05 * (v1 - v0) + 1e-3 / math.sqrt(dd)
    return v0 - marge, v1 + marge


def _parametrage(m: _Mailleur, surf_ref, T, boucles=None):
    mod = m.mod
    ent = mod.e.get(int(surf_ref)) if surf_ref is not None else None
    if not ent:
        return None
    t, a = ent
    tol = m.tol
    if t in ('PLANE', 'CYLINDRICAL_SURFACE', 'CONICAL_SURFACE',
             'SPHERICAL_SURFACE', 'TOROIDAL_SURFACE',
             'DEGENERATE_TOROIDAL_SURFACE'):
        R, c = composer(T, _cadre_brut(mod, a[1]))
        if t == 'PLANE':
            return _Plan(R, c)
        if t == 'CYLINDRICAL_SURFACE':
            return _Cylindre(R, c, float(a[2]) * mod.f, tol)
        if t == 'CONICAL_SURFACE':
            r = float(a[2]) * mod.f
            ang = float(a[3]) * m.unite_angle
            if abs(ang) >= math.pi / 2:          # degrés lus en radians
                ang = float(a[3]) * math.pi / 180.0
            return _Cone(R, c, r, math.tan(ang), tol, max(r, 1.0))
        if t == 'SPHERICAL_SURFACE':
            return _Sphere(R, c, float(a[2]) * mod.f, tol)
        return _Tore(R, c, float(a[2]) * mod.f, float(a[3]) * mod.f, tol)
    if t == 'SURFACE_OF_LINEAR_EXTRUSION':
        courbe = mod.echantillons(a[1])
        cref = mod.courbe_3d(a[1])
        if courbe is None and mod.type_de(cref) in ('LINE', 'CIRCLE'):
            return None
        vec = mod.args(a[2])
        d = _dir_brute(mod, vec[1], (0, 0, 1)) * float(vec[2]) * mod.f
        C = appliquer(T, np.array(courbe, dtype=float))
        D = T[0] @ d
        s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(
            np.diff(C, axis=0), axis=1))])
        if s[-1] <= 0:
            return None

        def ev(UV, C=C, s=s, D=D):
            u = np.clip(UV[:, 0], 0, s[-1])
            pts = np.column_stack([np.interp(u, s, C[:, k])
                                   for k in range(3)])
            return pts + np.outer(UV[:, 1], D)
        v0, v1 = _plage_extrusion(C, D, boucles)          # le vecteur d'extrusion n'est qu'une unité de v
        return _Grille(ev, 0.0, s[-1], v0, v1, tol, nu=60, nv=12)
    if t == 'SURFACE_OF_REVOLUTION':
        courbe = mod.echantillons(a[1])
        cref = mod.courbe_3d(a[1])
        if courbe is None:
            ce = mod.e.get(int(cref))
            if ce and ce[0] == 'LINE':
                p0 = _point_brut(mod, ce[1][1])
                vec = mod.args(ce[1][2])
                dd = _dir_brute(mod, vec[1], (0, 0, 1))
                courbe = [p0 - 1e3 * dd, p0 + 1e3 * dd]
            else:
                return None
        ax = mod.args(a[2])
        o = _point_brut(mod, ax[1])
        w = _dir_brute(mod, ax[2] if len(ax) > 2 else None, (0, 0, 1))
        C = np.array(courbe, dtype=float)
        s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(
            np.diff(C, axis=0), axis=1))])
        if s[-1] <= 0:
            return None

        def ev(UV, C=C, s=s, o=o, w=w):
            v = np.clip(UV[:, 1], 0, s[-1])
            pts = np.column_stack([np.interp(v, s, C[:, k])
                                   for k in range(3)]) - o
            th = UV[:, 0]
            cos, sin = np.cos(th)[:, None], np.sin(th)[:, None]
            kxv = np.cross(np.broadcast_to(w, pts.shape), pts)
            kdv = (pts @ w)[:, None] * w
            rot = pts * cos + kxv * sin + kdv * (1 - cos)
            return appliquer(T, rot + o)
        return _Grille(ev, -math.pi, math.pi, 0.0, s[-1], tol, nu=48,
                       nv=48, periode_u=2 * math.pi)
    # B-spline (simple ou complexe/rationnelle)
    bs = _bspline_surface(mod, ent)
    if bs is not None:
        pu, pv, P, W, U, V = bs
        u0, u1 = U[pu], U[len(U) - pu - 1]
        v0, v1 = V[pv], V[len(V) - pv - 1]
        Pt = appliquer(T, P.reshape(-1, 3)).reshape(P.shape)

        def ev(UV, pu=pu, pv=pv, Pt=Pt, W=W, U=U, V=V):
            return _eval_bspline_surface(pu, pv, Pt, W, U, V, UV)
        nu = max(16, min(80, 6 * (P.shape[0] - pu + 1)))
        nv = max(16, min(80, 6 * (P.shape[1] - pv + 1)))
        return _Grille(ev, u0, u1, v0, v1, tol, nu=nu, nv=nv)
    return None


def _bspline_surface(mod, ent):
    t, a = ent
    if t == 'B_SPLINE_SURFACE_WITH_KNOTS':
        pu, pv = int(a[1]), int(a[2])
        grille = a[3]
        mu, mv, ku, kv = a[8], a[9], a[10], a[11]
        poids = None
    elif t == '*' and 'B_SPLINE_SURFACE' in a:
        b = a['B_SPLINE_SURFACE']
        k = a.get('B_SPLINE_SURFACE_WITH_KNOTS')
        if not k:
            return None
        pu, pv = int(b[0]), int(b[1])
        grille = b[2]
        mu, mv, ku, kv = k[0], k[1], k[2], k[3]
        poids = (a.get('RATIONAL_B_SPLINE_SURFACE') or [None])[0]
    else:
        return None
    P = np.array([[_point_brut(mod, r) for r in rang] for rang in grille],
                 dtype=float)
    W = (np.array(poids, dtype=float) if poids is not None
         else np.ones(P.shape[:2]))
    U = np.repeat(np.array(ku, dtype=float), np.array(mu, dtype=int))
    V = np.repeat(np.array(kv, dtype=float), np.array(mv, dtype=int))
    if len(U) != P.shape[0] + pu + 1 or len(V) != P.shape[1] + pv + 1:
        return None
    return pu, pv, P, W, U, V


def _bases(p, U, u):
    """Fonctions de base B-spline non nulles en u (vectorisé): rend
    (indice de l'intervalle (N,), valeurs (N, p+1))."""
    n = len(U) - p - 2
    k = np.searchsorted(U, u, side='right') - 1
    k = np.clip(k, p, n)
    N = np.zeros((len(u), p + 1))
    N[:, 0] = 1.0
    gauche = np.zeros((len(u), p + 1))
    droite = np.zeros((len(u), p + 1))
    for j in range(1, p + 1):
        gauche[:, j] = u - U[k + 1 - j]
        droite[:, j] = U[k + j] - u
        sauve = np.zeros(len(u))
        for r in range(j):
            den = droite[:, r + 1] + gauche[:, j - r]
            tmp = np.where(np.abs(den) > 1e-14,
                           N[:, r] / np.where(np.abs(den) > 1e-14, den, 1),
                           0.0)
            N[:, r] = sauve + droite[:, r + 1] * tmp
            sauve = gauche[:, j - r] * tmp
        N[:, j] = sauve
    return k, N


def _eval_bspline_surface(pu, pv, P, W, U, V, UV):
    ku, Nu = _bases(pu, U, UV[:, 0])
    kv, Nv = _bases(pv, V, UV[:, 1])
    num = np.zeros((len(UV), 3))
    den = np.zeros(len(UV))
    for i in range(pu + 1):
        ii = ku - pu + i
        for j in range(pv + 1):
            jj = kv - pv + j
            w = W[ii, jj] * Nu[:, i] * Nv[:, j]
            num += P[ii, jj] * w[:, None]
            den += w
    return num / np.where(den == 0, 1.0, den)[:, None]


# ──── Triangulation d'une face dans son plan (u, v) ────

def _trianguler(param: _Param, boucles, tol, sens_face=True):
    import shapely
    from shapely.geometry import Polygon, box
    from shapely.validation import make_valid

    loops = []
    for pts, ext in boucles:
        if len(pts) == 1:
            loops.append(('point', param.uv(pts), ext))
            continue
        uv = param.uv(pts)
        if param.periode_u:
            uv[:, 0] = _derouler(uv[:, 0], param.periode_u)
        if param.periode_v:                              # bord sur ±π du tube : pas de saut d'une période
            uv[:, 1] = _derouler(uv[:, 1], param.periode_v)
        loops.append(('boucle', uv, ext))
    P = param.periode_u
    Pv = param.periode_v
    # une boucle qui fait le tour du cylindre (sans couture): son u
    # avance d'une période entière
    tour = [i for i, l in enumerate(loops) if l[0] == 'boucle' and P
            and abs(l[1][-1, 0] - l[1][0, 0] + _saut(l[1], P)) > 0.5 * P]
    enroulees = [loops[i] for i in tour]
    autres = [l for i, l in enumerate(loops)
              if i not in tour and l[0] == 'boucle']
    points = [l for l in loops if l[0] == 'point']
    if Pv and autres and not enroulees:                  # tore : trous ramenés près du bord extérieur, en v
        ref = max(autres, key=lambda l: abs(_aire(l[1])))
        mv = float(np.mean(ref[1][:, 1]))
        autres = [(g, uv - [0.0, round((float(np.mean(uv[:, 1])) - mv) / Pv) * Pv], e) for g, uv, e in autres]

    if enroulees:
        bandes = []
        for _g, uv, _e in enroulees:
            bandes.append(_ouvrir(uv, P))
        bandes.sort(key=lambda b: float(np.mean(b[:, 1])))
        if Pv and len(bandes) >= 2:                      # tore : le côté du tube par l'orientation
            bas, haut = _bandes_du_tore(enroulees, P, Pv, sens_face)
        elif len(bandes) >= 2:
            bas, haut = bandes[0], bandes[-1]
        else:
            bas = bandes[0]
            if points:
                v_pt = float(points[0][1][0, 1])
            else:
                # une seule boucle qui fait le tour (hémisphère, cône
                # jusqu'à sa pointe): la face est à GAUCHE de sa boucle
                # dans le plan (u, v) — à droite si elle est retournée
                # (le repère (u, v) suit la normale de la surface)
                uv0 = enroulees[0][1]
                s_u = 1.0 if (uv0[-1, 0] - uv0[0, 0]
                              + _saut(uv0, P)) > 0 else -1.0
                cote = s_u if sens_face else -s_u
                v_pt = param.v_pole(cote, float(np.mean(bas[:, 1])))
                if v_pt is None:
                    return None
            u0 = bas[0, 0]
            haut = np.array([[u0, v_pt], [u0 + P, v_pt]])
            if v_pt < float(np.mean(bas[:, 1])):
                bas, haut = haut, bas
        u0 = min(bas[0, 0], haut[0, 0])
        bas = _caler(bas, u0, P)
        haut = _caler(haut, u0, P)
        coque = np.vstack([bas, haut[::-1]])
        trous = []
        for _g, uv, _e in autres:
            m = float(np.mean(uv[:, 0]))
            k = math.floor((m - u0) / P)
            uv = uv - [k * P, 0.0]
            if Pv:                                       # tore : le trou ramené entre les deux bandes
                mb = float(np.mean(bas[:, 1]))
                uv = uv - [0.0, math.floor((float(np.mean(uv[:, 1])) - mb) / Pv) * Pv]
            trous.append(uv)
        poly = Polygon(coque, trous)
    else:
        if not autres:
            return None
        aires = [abs(_aire(l[1])) for l in autres]
        i_ext = next((i for i, l in enumerate(autres) if l[2]),
                     int(np.argmax(aires)))
        ext = autres[i_ext][1]
        trous = []
        for i, l in enumerate(autres):
            if i == i_ext:
                continue
            uv = l[1]
            if P:
                m = float(np.mean(uv[:, 0]))
                me = float(np.mean(ext[:, 0]))
                uv = uv - [round((m - me) / P) * P, 0.0]
            trous.append(uv)
        poly = Polygon(ext, trous)

    if not poly.is_valid:
        poly = make_valid(poly)
    if poly.is_empty or poly.area <= 0:
        return None
    morceaux = [poly]
    if param.courbe and (param.pas_u or param.pas_v):
        x0, y0, x1, y1 = poly.bounds
        pu = param.pas_u or (x1 - x0 + 1)
        pv = param.pas_v or (y1 - y0 + 1)
        nu = max(1, min(200, int(math.ceil((x1 - x0) / pu))))
        nv = max(1, min(200, int(math.ceil((y1 - y0) / pv))))
        if nu * nv > 1:
            morceaux = []
            for i in range(nu):
                for j in range(nv):
                    cel = box(x0 + (x1 - x0) * i / nu,
                              y0 + (y1 - y0) * j / nv,
                              x0 + (x1 - x0) * (i + 1) / nu,
                              y0 + (y1 - y0) * (j + 1) / nv)
                    inter = poly.intersection(cel)
                    if not inter.is_empty and inter.area > 0:
                        morceaux.append(inter)
    tris = []
    for m in morceaux:
        geoms = getattr(m, 'geoms', [m])
        for g in geoms:
            if g.geom_type != 'Polygon' or g.area <= 0:
                continue
            cdt = shapely.constrained_delaunay_triangles(g)
            for tri in getattr(cdt, 'geoms', []):
                c = np.array(tri.exterior.coords)[:3]
                if len(c) == 3:
                    tris.append(c)
    if not tris:
        return None
    UV = np.array(tris).reshape(-1, 2)
    if len(UV) > 3 * _MAX_TRI_FACE:
        UV = UV[:3 * _MAX_TRI_FACE]
    return _sur_le_bord(param, boucles, UV).reshape(-1, 3, 3)


def _bandes_du_tore(enroulees, P, Pv, sens_face):
    """(bas, haut) des deux bandes d'une face de tore qui fait le tour de
    l'axe : la face est à gauche de chaque bande dans le plan (u, v) (à
    droite si elle est retournée) — la bande qui a la face au-dessus est le
    bas, l'autre ramenée au-dessus d'elle à moins d'une période (le tube pris
    du bon côté, même au-delà de 180°) ; orientation incohérente : par v."""
    infos = []
    for _g, uv, _e in enroulees:
        s_u = 1.0 if (uv[-1, 0] - uv[0, 0] + _saut(uv, P)) > 0 else -1.0
        b = _ouvrir(uv, P)
        b = b - [0.0, round(float(np.mean(b[:, 1])) / Pv) * Pv]
        infos.append((b, (s_u if sens_face else -s_u) > 0))
    dessous = [b for b, up in infos if up]
    dessus = [b for b, up in infos if not up]
    if len(dessous) == 1 and len(dessus) == 1:
        bas, haut = dessous[0], dessus[0]
        mb, mh = float(np.mean(bas[:, 1])), float(np.mean(haut[:, 1]))
        return bas, haut + [0.0, (math.floor((mb - mh) / Pv) + 1) * Pv]
    bandes = sorted((b for b, _up in infos), key=lambda b: float(np.mean(b[:, 1])))
    return bandes[0], bandes[-1]


def _sans_plats(tris, couls, ids):
    """Triangles plats (aire nulle : deux sommets confondus, trois alignés)
    retirés, avec leur couleur et leur face — ils n'ajoutent rien à
    l'affichage et gênent la fermeture du maillage."""
    t = np.asarray(tris, dtype=float)
    if not len(t):
        return t, couls, ids
    aire = np.linalg.norm(np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0]), axis=1)
    garde = aire > 1e-12 * max(1.0, float(np.ptp(t.reshape(-1, 3), axis=0).max()) ** 2)
    if garde.all():
        return t, couls, ids
    return t[garde], np.asarray(couls)[garde], np.asarray(ids)[garde]


def _sur_le_bord(param, boucles, UV):
    """Points 3D des sommets (u, v) ; ceux du bord de la face reprennent
    EXACTEMENT les points de ses arêtes (partagés avec la face voisine) —
    l'aller-retour (u, v) les décalerait un peu, et le maillage ne serait
    plus fermé. Un sommet ajouté SUR un segment du bord (découpe en
    cellules) est posé sur la corde 3D de ce segment, celle de la voisine."""
    XYZ = param.point(UV)
    P = param.periode_u
    Pv = getattr(param, 'periode_v', 0.0)

    def mod(x, p):                                       # x modulo p, la couture comptée une fois (0)
        k = round(x % p, 7)
        return 0.0 if abs(k - round(p, 7)) < 1e-7 else k

    def cle(u, v):
        return (mod(u, P) if P else round(u, 7), mod(v, Pv) if Pv else round(v, 7))
    exacts = {}
    for pts, _e in boucles:
        if len(pts) < 2:
            continue
        for (u, v), q in zip(param.uv(pts).tolist(), np.asarray(pts, dtype=float).tolist()):
            exacts.setdefault(cle(u, v), q)
    if exacts:
        loose = []
        for i, (u, v) in enumerate(UV.tolist()):
            q = exacts.get(cle(u, v))
            if q is not None:
                XYZ[i] = q
            else:
                loose.append(i)
        if loose:
            _sur_les_cordes(param, boucles, UV, XYZ, np.asarray(loose))
    return XYZ


def _sur_les_cordes(param, boucles, UV, XYZ, idx) -> None:
    """Sommets `idx` situés sur un segment de bord en (u, v) : posés sur
    la corde 3D du segment (interpolation entre ses deux points d'arête)."""
    import shapely
    P = param.periode_u
    Pv = getattr(param, 'periode_v', 0.0)
    pts_uv = UV[idx]
    span = float(np.ptp(UV, axis=0).max()) if len(UV) else 1.0
    eps = 1e-9 * max(1.0, span)
    for pts, _e in boucles:
        if len(pts) < 2:
            continue
        p3 = np.asarray(pts, dtype=float)
        uv = param.uv(p3)
        if P:
            uv[:, 0] = _derouler(uv[:, 0], P)
        if Pv:
            uv[:, 1] = _derouler(uv[:, 1], Pv)
        a = uv
        b = np.vstack([uv[1:], uv[:1]])
        b3 = np.vstack([p3[1:], p3[:1]])
        if P:                                            # segment de fermeture déroulé lui aussi
            b[-1, 0] = a[-1, 0] + ((b[-1, 0] - a[-1, 0] + P / 2) % P - P / 2)
        if Pv:
            b[-1, 1] = a[-1, 1] + ((b[-1, 1] - a[-1, 1] + Pv / 2) % Pv - Pv / 2)
        q = pts_uv.copy()                                 # les sommets ramenés dans la période de la boucle
        if P:
            q[:, 0] -= np.round((q[:, 0] - float(a[:, 0].mean())) / P) * P
        if Pv:
            q[:, 1] -= np.round((q[:, 1] - float(a[:, 1].mean())) / Pv) * Pv
        segs = shapely.linestrings(np.stack([a, b], axis=1))
        tree = shapely.STRtree(segs)
        pi, si = tree.query(shapely.points(q), predicate='dwithin', distance=eps)
        if not len(pi):
            continue
        d = b[si] - a[si]
        L2 = (d * d).sum(axis=1)
        ok = L2 > 0
        t = np.clip(((q[pi] - a[si]) * d).sum(axis=1) / np.where(ok, L2, 1.0), 0.0, 1.0)
        pos = p3[si] + t[:, None] * (b3[si] - p3[si])
        XYZ[idx[pi[ok]]] = pos[ok]


def _derouler(u, P):
    """u continu le long d'une boucle (la couture ne fait pas sauter
    d'une période)."""
    d = np.diff(u)
    d = d - P * np.round(d / P)
    return np.concatenate([[u[0]], u[0] + np.cumsum(d)])


def _saut(uv, P):
    """Le dernier pas (du dernier point au premier), déroulé."""
    d = uv[0, 0] - uv[-1, 0]
    return d - P * round(d / P)


def _ouvrir(uv, P):
    """Une boucle qui fait le tour, en fonction de u croissant sur une
    période (fermée: le premier point répété à +P)."""
    if uv[-1, 0] + _saut(uv, P) < uv[0, 0]:
        uv = uv[::-1].copy()
    i = int(np.argmin(np.mod(uv[:, 0], P)))
    uv = np.vstack([uv[i:], uv[:i]])
    uv[:, 0] = _derouler(uv[:, 0], P)
    fin = uv[0] + [P, 0.0]
    return np.vstack([uv, fin])


def _caler(b, u0, P):
    k = math.floor((b[0, 0] - u0) / P + 1e-9)
    return b - [k * P, 0.0]


def _aire(uv):
    x, y = uv[:, 0], uv[:, 1]
    return 0.5 * (np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))


def _triangulee(mod, a, T):
    """TRIANGULATED_FACE (AP242)."""
    try:
        coords = mod.args(a[1])
        pts = np.array(coords[2], dtype=float) * mod.f
        pnindex = a[5] or []
        tris = np.array(a[6], dtype=int) - 1
        if pnindex:
            idx = np.array(pnindex, dtype=int) - 1
            tris = idx[tris]
        return appliquer(T, pts[tris].reshape(-1, 3)).reshape(-1, 3, 3)
    except (IndexError, TypeError, ValueError):
        return None


def _triangulee_complexe(mod, a, T):
    """COMPLEX_TRIANGULATED_FACE: bandes et éventails."""
    try:
        coords = mod.args(a[1])
        pts = np.array(coords[2], dtype=float) * mod.f
        pnindex = [int(i) - 1 for i in (a[5] or [])]

        def idx(i):
            return pnindex[int(i) - 1] if pnindex else int(i) - 1
        tris = []
        for bande in (a[6] or []):
            for k in range(len(bande) - 2):
                i, j, l = bande[k], bande[k + 1], bande[k + 2]
                if len({i, j, l}) < 3:
                    continue
                tris.append((idx(i), idx(j), idx(l)) if k % 2 == 0
                            else (idx(j), idx(i), idx(l)))
        for fan in (a[7] or []):
            for k in range(1, len(fan) - 1):
                tris.append((idx(fan[0]), idx(fan[k]), idx(fan[k + 1])))
        if not tris:
            return None
        t = np.array(tris, dtype=int)
        return appliquer(T, pts[t].reshape(-1, 3)).reshape(-1, 3, 3)
    except (IndexError, TypeError, ValueError):
        return None


# ──── Lecture ────

def info_face(derniere, surface: str, tri) -> Dict:
    """Ce qu'il faut savoir d'une face pour l'usiner: {'genre':
    'plan'|'cylindre'|'cone'|'sphere'|'tore'|'autre', 'surface',
    'boucles': [(points (N,3), extérieure?)], 'aire', 'z_min',
    'z_max'} et, selon le genre, 'normale' (plan, vers l'extérieur de
    la matière), 'axe', 'centre', 'rayon', 'creux' (cylindre: un trou
    plutôt qu'un bossage); cône, sphère, tore: 'axe' et 'centre' (un
    point de l'axe, le centre de la sphère)."""
    t = np.asarray(tri, dtype=float)
    info = {'genre': 'autre', 'surface': surface, 'boucles': [],
            'aire': float(0.5 * np.linalg.norm(np.cross(
                t[:, 1] - t[:, 0], t[:, 2] - t[:, 0]), axis=1).sum()),
            'z_min': float(t[:, :, 2].min()),
            'z_max': float(t[:, :, 2].max())}
    if not derniere:
        return info
    info['boucles'] = [(np.asarray(p, dtype=float), bool(ext))
                       for p, ext in derniere.get('boucles') or []
                       if len(p) >= 2]
    param = derniere.get('param')
    sens = 1.0 if derniere.get('meme_sens', True) else -1.0
    if isinstance(param, _Plan):
        # la normale déclarée: celle de la surface, retournée si la face
        # n'a pas le même sens (une face sans surface: celle de Newell
        # de sa boucle extérieure, orientée par la convention STEP).
        # PAS celle des triangles: leur sens varie d'une face à l'autre
        n = np.asarray(param.R[:, 2], dtype=float) * sens
        info.update(genre='plan', normale=n / max(np.linalg.norm(n),
                                                  1e-12))
    elif isinstance(param, _Cylindre):
        axe = np.asarray(param.R[:, 2], dtype=float)
        c = np.asarray(param.c, dtype=float)
        # creux: les normales des triangles regardent l'axe
        centres = t.mean(axis=1)
        nt = np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0])
        rad = centres - c
        rad = rad - np.outer(rad @ axe, axe)
        vers = float((nt * rad).sum())
        creux = vers < 0 if abs(vers) > 1e-12 else sens < 0
        info.update(genre='cylindre', axe=axe, centre=c,
                    rayon=float(param.r), creux=bool(creux))
    elif isinstance(param, (_Cone, _Sphere, _Tore)):
        # l'axe et un point de l'axe: les faces coaxiales (un trou, un
        # arbre entiers)
        info.update(genre='cone' if isinstance(param, _Cone) else
                    'sphere' if isinstance(param, _Sphere) else 'tore',
                    axe=np.asarray(param.R[:, 2], dtype=float),
                    centre=np.asarray(param.c, dtype=float))
    return info


#: direction des rayons du test « dans la matière »: un peu de biais,
#: pour ne pas filer le long d'une arête ou d'une paroi verticale
_RAYON = np.array([0.0127, 0.0071, 1.0]) / np.linalg.norm(
    [0.0127, 0.0071, 1.0])


def dans_la_matiere(triangles, points) -> np.ndarray:
    """Pour chaque point, est-il dans le solide? (parité des traversées
    d'un rayon, Möller–Trumbore). Le maillage doit être fermé."""
    T = np.asarray(triangles, dtype=float)
    P = np.atleast_2d(np.asarray(points, dtype=float))
    if not len(T) or not len(P):
        return np.zeros(len(P), dtype=bool)
    d = _RAYON
    v0 = T[:, 0]
    e1, e2 = T[:, 1] - v0, T[:, 2] - v0
    h = np.cross(d, e2)
    a = (e1 * h).sum(axis=1)
    ok = np.abs(a) > 1e-14
    f = np.where(ok, 1.0 / np.where(ok, a, 1.0), 0.0)
    sortie = np.zeros(len(P), dtype=bool)
    for i, p in enumerate(P):
        s_ = p - v0
        u = f * (s_ * h).sum(axis=1)
        q = np.cross(s_, e1)
        v = f * (q @ d)
        t = f * (e2 * q).sum(axis=1)
        traverse = ok & (u >= 0) & (v >= 0) & (u + v <= 1) & (t > 1e-9)
        sortie[i] = int(traverse.sum()) % 2 == 1
    return sortie


def orienter_faces(modele: "Modele3D") -> None:
    """Le côté matière de chaque plan et de chaque cylindre, mesuré:
    un point posé à un pas de la face, côté normale (plan) ou loin de
    l'axe (cylindre), est-il dans la pièce? La normale d'un plan
    regarde alors HORS de la matière; un cylindre est `creux` (un trou)
    quand la matière l'entoure."""
    T = modele.triangles
    if not len(T):
        return
    diag = float(np.linalg.norm(np.ptp(T.reshape(-1, 3), axis=0))) or 1.0
    eps = max(1e-4, diag * 2e-4)
    aires = 0.5 * np.linalg.norm(np.cross(T[:, 1] - T[:, 0],
                                          T[:, 2] - T[:, 0]), axis=1)
    sondes, quoi = [], []
    for info in modele.faces:
        if info.get('genre') not in ('plan', 'cylindre'):
            continue
        idx = np.nonzero(modele.face_de == info['index'])[0]
        if not len(idx):
            continue
        # les deux plus grands triangles de la face: deux avis
        for k in idx[np.argsort(-aires[idx])][:2]:
            c = T[k].mean(axis=0)
            if info['genre'] == 'plan':
                dirn = np.asarray(info['normale'], dtype=float)
            else:
                axe = np.asarray(info['axe'], dtype=float)
                r = c - np.asarray(info['centre'], dtype=float)
                r = r - np.dot(r, axe) * axe
                n = np.linalg.norm(r)
                if n < 1e-12:
                    continue
                dirn = r / n
            sondes.append(c + eps * dirn)
            quoi.append(info['index'])
    if not sondes:
        return
    dedans = dans_la_matiere(T, np.array(sondes))
    votes = {}
    for i, d in zip(quoi, dedans):
        votes.setdefault(i, []).append(bool(d))
    for info in modele.faces:
        v = votes.get(info['index'])
        if not v:
            continue
        matiere_dehors = sum(v) * 2 > len(v) or (sum(v) * 2 == len(v)
                                                and v[0])
        if info['genre'] == 'plan':
            if matiere_dehors:
                info['normale'] = -np.asarray(info['normale'])
        else:
            info['creux'] = bool(matiere_dehors)
        info['oriente'] = True


def lire_modele(chemin_ou_texte, *, tolerance_mm: float = None,
                units_mm: float = None, axe_haut: str = 'auto',
                progress=None) -> Modele3D:
    """Lit un STEP et le maille. `axe_haut`: 'auto', 'Z', 'Y' ou 'X'.

    `progress(fraction, texte)` rend False pour annuler."""
    if isinstance(chemin_ou_texte, str) and '\n' not in chemin_ou_texte \
            and 'ISO-10303' not in chemin_ou_texte[:64]:
        try:
            with open(chemin_ou_texte, 'r', encoding='latin-1') as f:
                texte = f.read()
        except OSError as err:
            raise StepError(f"lecture impossible: {err}") from None
    else:
        texte = chemin_ou_texte

    def _lecture(fraction, msg):
        if progress is None:
            return True
        return progress(0.3 * fraction, msg)
    entites = lire_entites(texte, _lecture if progress else None)
    if not entites:
        raise StepError("aucune entité lue dans ce fichier STEP")
    mod = _Modele(entites)
    declaree = mod.unite()
    mod.f = float(units_mm) if units_mm else declaree

    sortie = Modele3D()
    sortie.unite_mm = mod.f
    insts = instances(mod)
    sortie.n_instances = sum(1 for i in insts
                             if _a_de_la_forme(mod, i.items))
    sortie.noms = [i.nom for i in insts if i.nom]
    toutes = toutes_les_faces(mod, insts)
    corps_de = corps_des_faces(mod, insts, sortie.corps)
    corps_par_face = [corps_de.get((f, id(T)), corps_de.get(f, -1)) for f, T in toutes]
    libres = []
    for inst in insts:
        libres += faces_et_courbes(mod, inst.items, inst.T)[1]
    axe = axe_haut if axe_haut in ORIENTATIONS else (
        axe_haut_probable(mod, toutes))
    sortie.axe_haut = axe
    if axe != 'Z':
        Rh = (ORIENTATIONS[axe], np.zeros(3))
        toutes = [(f, composer(Rh, T)) for f, T in toutes]
        libres = [(c, composer(Rh, T)) for c, T in libres]
        sortie.notes.append(
            f"Pièce exportée « {axe} vers le haut »: redressée (Z vers "
            "le haut, l'axe de l'outil).")
    # tolérance de corde: un millième de la taille de la pièce
    if tolerance_mm is None:
        pts = np.array([_point_brut(mod, n) for n, (t, _a)
                        in list(entites.items())
                        if t == 'CARTESIAN_POINT'][:20000] or [[0, 0, 0]])
        diag = float(np.linalg.norm(np.ptp(pts, axis=0))) or 10.0
        tolerance_mm = min(0.05, max(0.002, diag / 1500.0))
    m = _Mailleur(mod, tolerance_mm)

    tris, couls, ids = [], [], []
    aretes_vues = set()
    sortie.n_faces = len(toutes)
    couleur_solide = {}
    for inst in insts:
        for r in inst.items:
            c = m.couleur_de.get(int(r))
            if c is not None:
                couleur_solide[id(inst.T)] = c
    for i, (f, T) in enumerate(toutes):
        if progress is not None and i % 25 == 0:
            if progress(0.3 + 0.7 * i / max(1, len(toutes)),
                        "maillage des faces…") is False:
                raise Cancelled("lecture du STEP")
        m.derniere = None
        try:
            tri, aretes, nom = m.mailler(f, T)
        except Exception:
            tri, aretes, nom = None, [], "?"
        sortie.surfaces[nom] += 1
        for cle, pts in aretes:
            if pts is None or len(pts) < 2:
                continue
            k = (cle, id(T)) if cle != 'poly' else None
            if k is not None:
                if k in aretes_vues:
                    continue
                aretes_vues.add(k)
            sortie.aretes.append(np.asarray(pts, dtype=float))
        if tri is None or not len(tri):
            sortie.non_maillees[nom] += 1
            continue
        sortie.n_faces_maillees += 1
        tris.append(tri)
        c = m.couleur_de.get(f) or couleur_solide.get(id(T)) or _ALU
        couls.append(np.tile(np.array(c, dtype=float), (len(tri), 1)))
        try:
            info = info_face(m.derniere, nom, tri)
        except Exception:
            info = {'genre': 'autre', 'surface': nom, 'boucles': []}
        info['index'] = len(sortie.faces)
        info['corps'] = corps_par_face[i]
        sortie.faces.append(info)
        ids.append(np.full(len(tri), info['index'], dtype=int))
    for c, T in libres:
        ent = mod.e.get(c)
        if not ent:
            continue
        try:
            pts = m.points_courbe(c, np.zeros(3), np.zeros(3), True, True)
            if len(pts) >= 2:
                sortie.aretes.append(appliquer(T, pts))
        except Exception:
            continue
    if tris:
        sortie.triangles, sortie.couleurs, sortie.face_de = _sans_plats(
            np.vstack(tris), np.vstack(couls), np.concatenate(ids))
        try:
            orienter_faces(sortie)
        except Exception:
            pass
    sortie.notes += mod.notes
    if sortie.non_maillees:
        sortie.notes.append(
            "Faces vues en arêtes seulement: " + ", ".join(
                f"{n} {nom.lower().replace('_', ' ')}"
                for nom, n in sortie.non_maillees.most_common()))
    if progress is not None:
        progress(1.0, "pièce maillée")
    return sortie
