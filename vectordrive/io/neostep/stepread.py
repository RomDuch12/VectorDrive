"""Lecture des fichiers STEP (ISO 10303-21) pour l'usinage 2,5D.

Sans noyau de CAO: on lit le graphe d'entités du fichier et on en
tire ce qu'une fraiseuse 3 axes usine depuis le dessus —

- les FACES HORIZONTALES tournées vers le haut (dessus de la pièce,
  fonds de poche, épaulements) et leurs contours. Chaque contour
  distinct n'est posé QU'UNE fois, sur le calque de sa profondeur la
  plus basse sous le dessus (« STEP Pz 5 »): une poche apparaît une
  fois, à la cote de son fond, et « Générer » n'en fait pas deux;
- les TROUS verticaux (surfaces cylindriques d'axe Z dont la matière
  est dehors): centre, Ø, profondeur, traversant ou borgne — dans le
  compte rendu (`rapport.trous`);
- l'unité de longueur déclarée (mm, m, pouce);
- les ASSEMBLAGES: chaque pièce posée où l'assemblage la met
  (`step3d.instances`), et une pièce exportée couchée (Y vers le
  haut) redressée.

Les arcs restent des courbes (Béziers cubiques), les B-splines (même
rationnelles) et les ellipses sont évaluées. Ce qui ne se lit pas
depuis le dessus (chanfreins coniques, congés toriques, surfaces
libres) est compté dans le compte rendu, pas inventé.

Convention: Z vers le haut est l'axe de l'outil. Une pièce exportée
couchée (Y vers le haut) le dit dans le compte rendu.
"""

import math
import re
from typing import Dict, List, Optional, Tuple

from .dxfimport import Cancelled, ImportReport
from .geometry import Chemin

SUFFIXES = ('.stp', '.step')
EPS = 1e-6


class StepError(RuntimeError):
    pass


class Ref(int):
    """Une référence #n."""


class Enum(str):
    """Une énumération .NOM."""


# ──── Lecture du texte (ISO 10303-21) ────

_JETON = re.compile(r"""
    (?P<s>'(?:[^']|'')*')
  | (?P<r>\#\d+)
  | (?P<e>\.[A-Za-z_][A-Za-z0-9_]*\.)
  | (?P<n>[-+]?(?:\d+\.?\d*(?:[eE][-+]?\d+)?|\.\d+(?:[eE][-+]?\d+)?))
  | (?P<k>[A-Za-z_][A-Za-z0-9_]*)
  | (?P<p>[(),;=$*])
  | (?P<w>\s+)
""", re.VERBOSE)


_CHAINE = r"'(?:[^']|'')*'"
#: une chaîne (passée) ou un commentaire (retiré)
_CHAINE_OU_COMMENTAIRE = re.compile(rf"{_CHAINE}|/\*.*?\*/", re.DOTALL)
#: une chaîne (passée) ou l'instruction « DATA; » / « DATA('nom',(…)); »
_CHAINE_OU_DATA = re.compile(
    rf"{_CHAINE}|\bDATA\s*(?:\((?:{_CHAINE}|[^;'])*\))?\s*;")


def _section_donnees(texte: str) -> str:
    """Le texte après l'instruction DATA (la fin, ENDSEC, est trouvée par
    `lire_entites`) ; chaînes de l'en-tête et commentaires respectés."""
    if "/*" in texte:
        texte = _CHAINE_OU_COMMENTAIRE.sub(
            lambda m: m.group() if m.group().startswith("'") else " ", texte)
    for m in _CHAINE_OU_DATA.finditer(texte):
        if not m.group().startswith("'"):
            return texte[m.end():]
    raise StepError("pas de section DATA: ce n'est pas un fichier "
                    "STEP (ISO 10303-21)")


def _valeur(jetons, i):
    genre, v = jetons[i]
    if genre == 'p':
        if v == '(':
            return _liste(jetons, i)
        if v in '$*':
            return None, i + 1
        raise StepError(f"jeton inattendu « {v} »")
    if genre == 'n':
        return float(v), i + 1
    if genre == 'r':
        return Ref(int(v[1:])), i + 1
    if genre == 'e':
        return Enum(v[1:-1]), i + 1
    if genre == 's':
        return v[1:-1].replace("''", "'"), i + 1
    # mot-clé: valeur typée NOM(...) ou nom seul
    if i + 1 < len(jetons) and jetons[i + 1] == ('p', '('):
        args, j = _liste(jetons, i + 1)
        return (v, args), j
    return v, i + 1


def _liste(jetons, i):
    i += 1                     # après « ( »
    out = []
    while jetons[i] != ('p', ')'):
        if jetons[i] == ('p', ','):
            i += 1
            continue
        val, i = _valeur(jetons, i)
        out.append(val)
    return out, i + 1


def lire_entites(texte: str, progress=None) -> Dict[int, tuple]:
    """{n: (TYPE, args)} — ou (\"*\", {TYPE: args}) pour une entité
    complexe (plusieurs types réunis, comme les unités)."""
    donnees = _section_donnees(texte)
    total = max(1, len(donnees))
    entites: Dict[int, tuple] = {}
    instruction: List[tuple] = []
    profondeur = 0
    prochain = 0
    for m in _JETON.finditer(donnees):
        genre = m.lastgroup
        if genre == 'w':
            continue
        v = m.group(genre)
        if genre == 'p':
            if v == '(':
                profondeur += 1
            elif v == ')':
                profondeur -= 1
            elif v == ';' and profondeur == 0:
                if instruction == [('k', 'ENDSEC')]:
                    break                       # fin de la section DATA
                _ranger(instruction, entites)
                instruction = []
                if progress is not None and m.end() >= prochain:
                    prochain = m.end() + 200_000
                    if progress(0.7 * m.end() / total,
                                "lecture du STEP…") is False:
                        raise Cancelled("lecture du STEP")
                continue
        instruction.append((genre, v))
    return entites


def _ranger(instruction, entites) -> None:
    if len(instruction) < 3 or instruction[0][0] != 'r' \
            or instruction[1] != ('p', '='):
        return
    n = int(instruction[0][1][1:])
    try:
        corps, _ = _valeur(instruction, 2)
    except (StepError, IndexError, ValueError):
        return
    if isinstance(corps, tuple):
        entites[n] = corps
    elif isinstance(corps, list) and corps \
            and all(isinstance(c, tuple) for c in corps):
        entites[n] = ("*", {nom: args for nom, args in corps})


# ──── Géométrie ────

class _Modele:
    def __init__(self, entites: Dict[int, tuple]):
        self.e = entites
        self.f = 1.0
        self.notes: List[str] = []
        self._cache_pt: Dict[int, tuple] = {}
        # placement de la pièce lue (assemblage, redressement): None,
        # ou (R 3×3, t) — appliqué aux points et directions
        self.T = None

    def transformer(self, T) -> None:
        """Lit désormais la pièce placée par T (None: telle quelle)."""
        if T is not self.T:
            self.T = T
            self._cache_pt = {}

    def _placer(self, p, translation=True):
        if self.T is None:
            return p
        R, t = self.T
        q = [R[i][0] * p[0] + R[i][1] * p[1] + R[i][2] * p[2]
             for i in range(3)]
        if translation:
            q = [q[i] + t[i] for i in range(3)]
        return (float(q[0]), float(q[1]), float(q[2]))

    def type_de(self, ref) -> str:
        ent = self.e.get(int(ref)) if ref is not None else None
        return ent[0] if ent else ""

    def args(self, ref) -> list:
        ent = self.e.get(int(ref))
        return ent[1] if ent else []

    # -- unités --
    def unite(self) -> float:
        for nom, args in self.e.values():
            if nom != "*" or 'LENGTH_UNIT' not in args:
                continue
            si = args.get('SI_UNIT')
            if si is not None and len(si) >= 2 and si[1] == 'METRE':
                return {None: 1000.0, 'MILLI': 1.0, 'CENTI': 10.0,
                        'DECI': 100.0, 'MICRO': 0.001,
                        'KILO': 1e6}.get(si[0], 1.0)
            conv = args.get('CONVERSION_BASED_UNIT')
            if conv is not None and len(conv) >= 2:
                try:
                    mesure = self.args(conv[1])
                    valeur = mesure[0][1][0] if isinstance(mesure[0], tuple) \
                        else float(mesure[0])
                    base = self.e.get(int(mesure[1]))
                    f_base = 1.0
                    if base and base[0] == "*" and 'SI_UNIT' in base[1]:
                        pref = base[1]['SI_UNIT'][0]
                        f_base = {None: 1000.0, 'MILLI': 1.0,
                                  'CENTI': 10.0}.get(pref, 1.0)
                    return float(valeur) * f_base
                except (IndexError, TypeError, ValueError, KeyError):
                    pass
        self.notes.append("Unité de longueur non trouvée: millimètres "
                          "supposés.")
        return 1.0

    # -- points, directions, repères --
    def point(self, ref) -> tuple:
        n = int(ref)
        p = self._cache_pt.get(n)
        if p is None:
            ent = self.e.get(n)
            if ent and ent[0] == 'VERTEX_POINT':
                p = self.point(ent[1][1])
            elif ent and ent[0] == 'CARTESIAN_POINT':
                c = list(ent[1][1]) + [0.0, 0.0, 0.0]
                p = self._placer((c[0] * self.f, c[1] * self.f,
                                  c[2] * self.f))
            else:
                p = self._placer((0.0, 0.0, 0.0))
            self._cache_pt[n] = p
        return p

    def direction(self, ref, defaut=(0.0, 0.0, 1.0)) -> tuple:
        if ref is None or self.type_de(ref) != 'DIRECTION':
            return defaut
        c = list(self.args(ref)[1]) + [0.0, 0.0, 0.0]
        norme = math.sqrt(c[0] ** 2 + c[1] ** 2 + c[2] ** 2) or 1.0
        return self._placer((c[0] / norme, c[1] / norme, c[2] / norme),
                            translation=False)

    def repere(self, ref):
        a = self.args(ref)
        loc = self.point(a[1])
        axe = self.direction(a[2] if len(a) > 2 else None)
        ref_dir = self.direction(a[3] if len(a) > 3 else None,
                                 (1.0, 0.0, 0.0))
        return loc, axe, ref_dir

    # -- courbes --
    def courbe_3d(self, ref):
        """SURFACE_CURVE / SEAM_CURVE enveloppent la vraie courbe."""
        nom = self.type_de(ref)
        if nom in ('SURFACE_CURVE', 'SEAM_CURVE', 'INTERSECTION_CURVE'):
            return self.courbe_3d(self.args(ref)[1])
        return ref

    def echantillons(self, ref) -> Optional[List[tuple]]:
        """Points le long d'une courbe libre (B-spline, ellipse)."""
        ent = self.e.get(int(ref))
        if not ent:
            return None
        nom, args = ent
        if nom == 'ELLIPSE':
            loc, axe, rd = self.repere(args[1])
            a, b = args[2] * self.f, args[3] * self.f
            v = _vectoriel(axe, rd)
            return [tuple(loc[k] + a * math.cos(t) * rd[k]
                          + b * math.sin(t) * v[k] for k in range(3))
                    for t in (2 * math.pi * i / 96 for i in range(97))]
        if nom == 'POLYLINE':
            return [self.point(r) for r in args[1]]
        if nom == 'TRIMMED_CURVE':
            return self.echantillons(args[1])
        if nom == 'B_SPLINE_CURVE_WITH_KNOTS':
            return self._bspline(args[1], args[2], args[6], args[7], None)
        if nom == '*' and 'B_SPLINE_CURVE' in args:
            bs = args['B_SPLINE_CURVE']
            kn = args.get('B_SPLINE_CURVE_WITH_KNOTS')
            poids = (args.get('RATIONAL_B_SPLINE_CURVE') or [None])[0]
            if kn:
                return self._bspline(bs[0], bs[1], kn[0], kn[1], poids)
        return None

    def _bspline(self, degre, refs_pts, mults, noeuds, poids):
        p = int(degre)
        P = [self.point(r) for r in refs_pts]
        U = []
        for m, k in zip(mults, noeuds):
            U += [float(k)] * int(m)
        if len(U) != len(P) + p + 1 or len(P) < 2:
            return None
        W = [float(w) for w in poids] if poids else [1.0] * len(P)
        u0, u1 = U[p], U[len(P)]
        n_ech = max(32, min(400, 24 * (len(P) - p)))
        sortie = []
        for i in range(n_ech + 1):
            u = u0 + (u1 - u0) * i / n_ech
            sortie.append(_de_boor(p, U, P, W, u))
        return sortie


def _net(v: float, n: int = 3) -> float:
    """Une cote propre: arrondie, et sans « -0 » ni « 6.6e-15 »."""
    v = round(float(v), n)
    return 0.0 if v == 0 else v


def _vectoriel(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def _de_boor(p, U, P, W, u):
    n = len(P) - 1
    k = p
    while k < n and U[k + 1] <= u:
        k += 1
    d = [(P[j][0] * W[j], P[j][1] * W[j], P[j][2] * W[j], W[j])
         for j in range(k - p, k + 1)]
    for r in range(1, p + 1):
        for j in range(p, r - 1, -1):
            i = j + k - p
            den = U[i + p - r + 1] - U[i]
            a = 0.0 if abs(den) < 1e-12 else (u - U[i]) / den
            d[j] = tuple((1 - a) * d[j - 1][c] + a * d[j][c]
                         for c in range(4))
    w = d[p][3] or 1.0
    return (d[p][0] / w, d[p][1] / w, d[p][2] / w)


def _arc_beziers(chemin: Chemin, cx, cy, r, a0, balayage) -> None:
    """Un arc de cercle en Béziers cubiques (≤ 90° chacune), depuis le
    point courant du chemin (supposé au départ de l'arc)."""
    n = max(1, int(math.ceil(abs(balayage) / (math.pi / 2) - 1e-9)))
    theta = balayage / n
    k = 4.0 / 3.0 * math.tan(theta / 4.0)
    for i in range(n):
        t0 = a0 + theta * i
        t1 = t0 + theta
        p0 = (cx + r * math.cos(t0), cy + r * math.sin(t0))
        p3 = (cx + r * math.cos(t1), cy + r * math.sin(t1))
        p1 = (p0[0] - k * r * math.sin(t0), p0[1] + k * r * math.cos(t0))
        p2 = (p3[0] + k * r * math.sin(t1), p3[1] - k * r * math.cos(t1))
        chemin.cubicto(p1, p2, p3)


# ──── Lecture des faces ────

def _boucle(mod: _Modele, ref_bord, tolerance, compte) -> Tuple[
        Optional[Chemin], frozenset, List[tuple], float]:
    """Le contour d'une face (FACE_BOUND), en XY. Rend (chemin,
    signature, sommets 3D, balayage total des arcs en radians). La
    signature ignore le point de départ et le sens: deux faces qui
    partagent un contour le reconnaissent."""
    a = mod.args(ref_bord)
    if len(a) < 2:
        return None, frozenset(), [], 0.0
    boucle = mod.e.get(int(a[1]))
    if boucle and boucle[0] == 'POLY_LOOP':
        # faces à facettes (FACETED_BREP): des points, des droites
        pts = [mod.point(r) for r in boucle[1][1]]
        if len(pts) < 3:
            return None, frozenset(), pts, 0.0
        chemin = Chemin(tolerance=tolerance)
        chemin.moveto(pts[0][0], pts[0][1])
        for p in pts[1:]:
            chemin.lineto(p[0], p[1])
        chemin.fermer()
        signature = frozenset((round(p[0], 3), round(p[1], 3))
                              for p in pts)
        return chemin, signature, pts, 0.0
    if not boucle or boucle[0] != 'EDGE_LOOP':
        return None, frozenset(), [], 0.0
    chemin = Chemin(tolerance=tolerance)
    signature = set()
    sommets = []
    balaye = 0.0
    for ref_oe in boucle[1][1]:
        oe = mod.args(ref_oe)
        if len(oe) < 5:
            continue
        ec = mod.args(oe[3])
        if len(ec) < 5:
            continue
        sens_oe = oe[4] == 'T'
        va, vb = (ec[1], ec[2]) if sens_oe else (ec[2], ec[1])
        pa, pb = mod.point(va), mod.point(vb)
        sommets += [pa, pb]
        signature.add((round(pa[0], 3), round(pa[1], 3)))
        if not chemin.points:
            chemin.moveto(pa[0], pa[1])
        courbe = mod.courbe_3d(ec[3])
        inverse = False
        while mod.type_de(courbe) == 'TRIMMED_CURVE':
            # la courbe coupée suit sa base, dans un sens ou l'autre
            inverse ^= mod.args(courbe)[4] != 'T'
            courbe = mod.courbe_3d(mod.args(courbe)[1])
        nom = mod.type_de(courbe)
        naturel = ((ec[4] == 'T') == sens_oe) != inverse
        if nom == 'CIRCLE':
            ca = mod.args(courbe)
            loc, axe, _ = mod.repere(ca[1])
            r = ca[2] * mod.f
            signature.add(('c', round(loc[0], 3), round(loc[1], 3),
                           round(r, 3)))
            trigo = (axe[2] >= 0) == naturel
            t0 = math.atan2(pa[1] - loc[1], pa[0] - loc[0])
            t1 = math.atan2(pb[1] - loc[1], pb[0] - loc[0])
            complet = int(va) == int(vb) or (
                abs(pa[0] - pb[0]) < EPS and abs(pa[1] - pb[1]) < EPS)
            if trigo:
                b = (t1 - t0) % (2 * math.pi)
                b = 2 * math.pi if complet and b < EPS else b
            else:
                b = -((t0 - t1) % (2 * math.pi))
                b = -2 * math.pi if complet and b > -EPS else b
            _arc_beziers(chemin, loc[0], loc[1], r, t0, b)
            balaye += abs(b)
        elif nom == 'LINE' or not nom:
            chemin.lineto(pb[0], pb[1])
        else:
            pts = mod.echantillons(courbe)
            if pts:
                sous = _sous_arc(pts, pa, pb, naturel)
                for x, y, _z in sous[1:]:
                    chemin.lineto(x, y)
                chemin.lineto(pb[0], pb[1])
            else:
                compte['courbes_approchees'] += 1
                chemin.lineto(pb[0], pb[1])
    if len(chemin.points) >= 2:
        chemin.fermer()
        return chemin, frozenset(signature), sommets, balaye
    return None, frozenset(), sommets, balaye


def _normale_z(pts) -> float:
    """La composante Z de la normale (Newell) d'un polygone 3D."""
    n = [0.0, 0.0, 0.0]
    for i in range(len(pts)):
        p, q = pts[i], pts[(i + 1) % len(pts)]
        n[0] += (p[1] - q[1]) * (p[2] + q[2])
        n[1] += (p[2] - q[2]) * (p[0] + q[0])
        n[2] += (p[0] - q[0]) * (p[1] + q[1])
    norme = math.sqrt(n[0] ** 2 + n[1] ** 2 + n[2] ** 2)
    return n[2] / norme if norme > 0 else 0.0


def _sous_arc(pts, pa, pb, naturel):
    """La portion d'une courbe échantillonnée entre deux sommets."""
    def proche(p):
        return min(range(len(pts)), key=lambda i: (pts[i][0] - p[0]) ** 2
                   + (pts[i][1] - p[1]) ** 2 + (pts[i][2] - p[2]) ** 2)
    ia, ib = proche(pa), proche(pb)
    if not naturel:
        pts = pts[::-1]
        ia, ib = len(pts) - 1 - ia, len(pts) - 1 - ib
    if ib >= ia:
        return pts[ia:ib + 1]
    return pts[ia:] + pts[1:ib + 1]         # courbe fermée: on boucle


def lire(chemin, *, tolerance_mm: float = 0.02, units_mm: float = None,
         progress=None, ask=None, orientation=None):
    """Lit un STEP. Rend ({calque: [Chemin]}, rapport) comme les autres
    lecteurs; `rapport.trous` liste les trous verticaux. `orientation`
    (3×3) : rotation appliquée à la pièce redressée (une autre face vers le
    haut : vue de dessus de cette face)."""
    try:
        with open(chemin, 'r', encoding='latin-1') as f:
            texte = f.read()
    except OSError as err:
        raise StepError(f"lecture impossible: {err}") from None
    entites = lire_entites(texte, progress)
    if not entites:
        raise StepError("aucune entité lue dans ce fichier STEP")
    mod = _Modele(entites)
    declaree = mod.unite()
    mod.f = float(units_mm) if units_mm else declaree

    # Chaque pièce à sa place (assemblage), le haut vers +Z
    from . import step3d
    insts = step3d.instances(mod)
    faces_placees = step3d.toutes_les_faces(mod, insts)
    axe = step3d.axe_haut_probable(mod, faces_placees)
    if axe != 'Z':
        import numpy as _np
        Rh = (step3d.ORIENTATIONS[axe], _np.zeros(3))
        faces_placees = [(f, step3d.composer(Rh, T))
                         for f, T in faces_placees]
        mod.notes.append(
            f"Pièce exportée « {axe} vers le haut »: redressée (Z vers "
            "le haut, l'axe de l'outil).")
    if orientation is not None:
        import numpy as _np
        Ro = (_np.asarray(orientation, dtype=float), _np.zeros(3))
        faces_placees = [(f, step3d.composer(Ro, T)) for f, T in faces_placees]
    n_pieces = sum(1 for i in insts if step3d._a_de_la_forme(mod, i.items))

    compte = {'courbes_approchees': 0}
    autres: Dict[str, int] = {}
    contours = {}                 # signature -> (chemin, z le plus bas)
    trous: Dict[tuple, dict] = {}
    cones: List[dict] = []
    n_faces = n_horiz = 0
    z_tous: List[float] = []
    faces = [(n, entites[n][1], T) for n, T in faces_placees
             if entites.get(n, ("",))[0] in ('ADVANCED_FACE', 'FACE_SURFACE',
                                             'FACE')]
    for numero, (_n, args, T) in enumerate(faces):
        if progress is not None and numero % 200 == 0:
            if progress(0.7 + 0.3 * numero / max(1, len(faces)),
                        "faces du STEP…") is False:
                raise Cancelled("lecture du STEP")
        mod.transformer(None if T is step3d.IDENTITE else T)
        n_faces += 1
        if len(args) == 2:
            # face à facettes (FACETED_BREP, sans surface): son plan
            # est celui de son polygone
            c, sig, sommets, _b = _boucle(mod, args[1][0], tolerance_mm,
                                          compte) if args[1] else (
                None, None, [], 0)
            z_tous += [p[2] for p in sommets]
            nz = _normale_z(sommets)
            if c is not None and nz > 0.999:
                n_horiz += 1
                z = sum(p[2] for p in sommets) / len(sommets)
                if sig not in contours or z < contours[sig][1]:
                    contours[sig] = (c, z)
            continue
        if len(args) < 4:
            continue
        bords, ref_surf, meme_sens = args[1], args[2], args[3] == 'T'
        surf = entites.get(int(ref_surf)) if ref_surf is not None else None
        nom_surf = surf[0] if surf else ""
        if nom_surf == 'PLANE':
            loc, axe, _ = mod.repere(surf[1][1])
            nz = axe[2] if meme_sens else -axe[2]
            for b in bords:
                _c, _s, sommets, _b = _boucle(mod, b, tolerance_mm, compte)
                z_tous += [p[2] for p in sommets]
            if abs(abs(axe[2]) - 1.0) > 1e-6 or nz <= 0:
                continue          # verticale, ou tournée vers le bas
            n_horiz += 1
            z = loc[2]
            for b in bords:
                c, sig, _s, _b = _boucle(mod, b, tolerance_mm, compte)
                if c is None:
                    continue
                if sig not in contours or z < contours[sig][1]:
                    contours[sig] = (c, z)
        elif nom_surf == 'CYLINDRICAL_SURFACE':
            loc, axe, _ = mod.repere(surf[1][1])
            r = surf[1][2] * mod.f
            zs = []
            tour = 0.0
            for b in bords:
                _c, _s, sommets, balaye = _boucle(mod, b, tolerance_mm,
                                                  compte)
                zs += [p[2] for p in sommets]
                tour += balaye
            z_tous += zs
            if abs(abs(axe[2]) - 1.0) > 1e-6 or not zs:
                autres['cylindres non verticaux'] = autres.get(
                    'cylindres non verticaux', 0) + 1
                continue
            cle = (round(loc[0], 3), round(loc[1], 3), round(r, 3))
            t = trous.setdefault(cle, {'x': loc[0], 'y': loc[1],
                                       'diametre': 2 * r,
                                       'z_bas': min(zs), 'z_haut': max(zs),
                                       'trou': not meme_sens,
                                       'couverture': 0.0})
            t['z_bas'] = min(t['z_bas'], min(zs))
            t['z_haut'] = max(t['z_haut'], max(zs))
            # chaque morceau d'angle compte deux fois (arc du haut, arc
            # du bas): la moitié du balayage est la part du tour faite
            t['couverture'] += tour / 2.0
        elif nom_surf == 'CONICAL_SURFACE' and abs(abs(
                mod.repere(surf[1][1])[1][2]) - 1.0) <= 1e-6:
            loc = mod.repere(surf[1][1])[0]
            som = []
            for b in bords:
                _c, _s, sommets, _b = _boucle(mod, b, tolerance_mm, compte)
                som += sommets
            z_tous += [p[2] for p in som]
            if not som:
                continue
            zb, zh = min(p[2] for p in som), max(p[2] for p in som)

            def _r_a(z):
                rs = [math.hypot(p[0] - loc[0], p[1] - loc[1])
                      for p in som if abs(p[2] - z) < 1e-4]
                return sum(rs) / len(rs) if rs else 0.0
            cones.append({'x': loc[0], 'y': loc[1], 'z_bas': zb,
                          'z_haut': zh, 'r_bas': _r_a(zb),
                          'r_haut': _r_a(zh), 'creux': not meme_sens,
                          'rattache': False})
        else:
            libelle = {'CONICAL_SURFACE': 'faces coniques (chanfreins)',
                       'TOROIDAL_SURFACE': 'faces toriques (congés)',
                       'SPHERICAL_SURFACE': 'faces sphériques'}.get(
                nom_surf, 'surfaces libres')
            autres[libelle] = autres.get(libelle, 0) + 1

    mod.transformer(None)
    rapport = ImportReport()
    rapport.units_mm = mod.f
    rapport.declared_units_mm = declaree
    rapport.units_overridden = bool(units_mm)
    z_dessus = max((z for _c, z in contours.values()), default=0.0)
    z_dessus = max([z_dessus] + z_tous) if z_tous else z_dessus
    z_fond = min(z_tous) if z_tous else z_dessus

    # Un TROU fait le tour (360°, souvent en deux demi-faces): un
    # congé de coin de poche n'en fait qu'un quart — ce n'est pas un
    # trou, même si sa matière est dehors.
    vrais = {cle: t for cle, t in trous.items()
             if t['trou'] and t['couverture'] >= 2 * math.pi - 0.05}
    for t in vrais.values():
        t['z_entree'] = t['z_haut']
        t['fraisure'] = t['fraisure_dessous'] = None
        t['pointe'] = t['debouchant'] = False
        for c in cones:
            if not c['creux'] or abs(c['x'] - t['x']) > 1e-3 \
                    or abs(c['y'] - t['y']) > 1e-3:
                continue
            if abs(c['z_bas'] - t['z_haut']) < 1e-3 \
                    and c['r_haut'] > c['r_bas']:
                # fraisure côté dessus: l'entrée est en haut du cône
                t['z_entree'] = max(t['z_entree'], c['z_haut'])
                t['fraisure'] = 2 * c['r_haut']
                c['rattache'] = True
            elif abs(c['z_haut'] - t['z_bas']) < 1e-3:
                if c['r_bas'] > c['r_haut']:
                    # fraisure côté dessous: le trou débouche
                    t['fraisure_dessous'] = 2 * c['r_bas']
                    t['debouchant'] = True
                else:
                    t['pointe'] = True     # pointe de foret
                c['rattache'] = True
    seuls = sum(1 for c in cones if not c['rattache'])
    if seuls:
        autres['faces coniques (chanfreins)'] = autres.get(
            'faces coniques (chanfreins)', 0) + seuls

    calques: Dict[str, List[Chemin]] = {}
    for sig, (c, z) in contours.items():
        arcs = {s[1:] for s in sig if isinstance(s, tuple)
                and len(s) == 4 and s[0] == 'c'}
        # le cercle d'un trou: posé à la cote où le trou COMMENCE (son
        # fond ne se fraise pas, le perçage s'en charge)
        if len(arcs) == 1 and next(iter(arcs)) in vrais:
            z = vrais[next(iter(arcs))]['z_haut']
        pz = round(z_dessus - z, 3)
        calques.setdefault(f"STEP Pz {pz:g}", []).append(c)

    liste_trous = []
    for t in sorted(vrais.values(), key=lambda t: (t['x'], -t['y'])):
        liste_trous.append({
            'x': _net(t['x']), 'y': _net(t['y']),
            'diametre': _net(t['diametre']),
            # depuis l'entrée (haut de la fraisure s'il y en a une)
            'profondeur': _net(t['z_entree'] - t['z_bas']),
            'traversant': (abs(t['z_bas'] - z_fond) < 1e-3
                           or t['debouchant']),
            'pz_depart': _net(z_dessus - t['z_entree']),
            'fraisure': _net(t['fraisure']) if t['fraisure'] else None,
            'fraisure_dessous': (_net(t['fraisure_dessous'])
                                 if t['fraisure_dessous'] else None),
            'pointe': t['pointe']})
    rapport.trous = liste_trous

    rapport.layers = {nom: len(v) for nom, v in calques.items()}
    rapport.polylines = sum(rapport.layers.values())
    tous = [p for v in calques.values() for c in v for p in c.points]
    if tous:
        xs = [p[0] for p in tous]
        ys = [p[1] for p in tous]
        rapport.extent = (min(xs), min(ys), max(xs), max(ys))
    rapport.notes += mod.notes
    rapport.notes.append(
        f"STEP: {n_faces} faces, {n_horiz} horizontale(s) vers le haut, "
        f"{len(liste_trous)} trou(s) vertical(aux); hauteur "
        f"{z_dessus - z_fond:g} mm.")
    for t in liste_trous[:40]:
        detail = ""
        if t['fraisure']:
            detail += f", fraisure Ø{t['fraisure']:g}"
        if t['fraisure_dessous']:
            detail += f", fraisure Ø{t['fraisure_dessous']:g} côté dessous"
        if t['pointe']:
            detail += ", fond en pointe"
        rapport.notes.append(
            f"  trou Ø{t['diametre']:g} en X{t['x']:g} Y{t['y']:g} — "
            + ("traversant" if t['traversant'] else "borgne")
            + f", {t['profondeur']:g} mm depuis Pz {t['pz_depart']:g}"
            + detail)
    if len(liste_trous) > 40:
        rapport.notes.append(f"  … et {len(liste_trous) - 40} autres")
    for libelle, n in sorted(autres.items()):
        rapport.notes.append(f"{n} {libelle} non lue(s) depuis le dessus.")
    if compte['courbes_approchees']:
        rapport.notes.append(
            f"{compte['courbes_approchees']} courbe(s) d'un type non lu "
            "approchée(s) par une droite.")
    if n_faces and not n_horiz:
        rapport.notes.append(
            "Aucune face horizontale tournée vers +Z: la pièce est "
            "peut-être couchée (exportée Y vers le haut ?).")
    if n_pieces > 1:
        rapport.notes.append(
            f"Assemblage: {n_pieces} pièces, chacune posée à sa place.")
    if progress is not None:
        progress(1.0, 'terminé')
    return calques, rapport
