"""Dessin d'un outil à partir de ses cotes : un DXF (la silhouette cotée,
et le demi-profil de révolution) et un STEP (le solide de révolution
exact : plans, cylindres, cônes). Repris de NeoDrive (même auteur).

Cotes (`CamTool.geometry`, comme les catalogues des fabricants) : D1 le Ø
de coupe (la POINTE d'une pointe à graver), D2 la queue, D3 / L3 le
dégagement (col et longueur), L1 la longueur totale, L2 la longueur de
coupe, `angle` l'angle de pointe, R le rayon (boule, torique, fraise à
rayonner), `dents`. Ce qui manque se déduit de l'outil (diamètre, angle,
pointe, longueur utile) puis prend des valeurs courantes.

Le profil se décrit de la pointe (z = 0) à la queue (z = L1) : des points
(r, z), z jamais décroissant (un épaulement est un pas horizontal).
"""
from __future__ import annotations

import math
from datetime import datetime
from typing import Dict, List, Tuple

#: le rayon mini d'une pointe (un cône pointu devient un tout petit plat)
EPS_POINTE = 0.01
#: segments d'un quart d'arc (boule, torique, rayon)
N_ARC = 8

FAMILLES = ('fraise', 'surfacage', 'torique', 'boule', 'foret', 'conique',
            'chanfrein', 'rayon', 'filetage', 'tslot')
#: nature d'outil VectorDrive → famille de dessin
FAMILLE_DE = {'fraise': 'fraise', 'boule': 'boule', 'conique': 'conique', 'foret': 'foret', 'laser': 'fraise'}


def _n(v, defaut: float = 0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return float(defaut)


def cotes_outil(tool) -> Dict:
    """Les cotes d'un outil (`CamTool`) : {'famille', 'D1', 'D2', 'D3',
    'L1', 'L2', 'L3', 'angle', 'R', 'pointe', 'hauteur', 'dents',
    'gravure', 'source', 'libelle'}."""
    g = {k: v for k, v in dict(getattr(tool, 'geometry', None) or {}).items() if v not in (None, '')}
    famille = str(g.get('famille') or FAMILLE_DE.get(getattr(tool, 'kind', 'fraise'), 'fraise'))
    if famille == 'fraise' and _n(g.get('R')) > 0:
        famille = 'torique'
    c = {'famille': famille, 'libelle': str(g.get('libelle') or famille),
         'source': 'cotes de l\'outil' if g else 'outil (diamètre, angle, pointe)'}
    D = _n(g.get('D1')) or _n(getattr(tool, 'diameter', 0))
    tip = _n(getattr(tool, 'tip', 0))
    angle = _n(g.get('angle')) or _n(getattr(tool, 'angle', 0))
    gravure = famille == 'conique' and (tip > 0 or not g.get('D1'))
    c['gravure'] = gravure
    if gravure:
        c['D1'] = tip or EPS_POINTE * 2          # une pointe à graver : D1 est la pointe
        c['D2'] = _n(g.get('D2')) or _n(getattr(tool, 'diameter', 0)) or 3.175
    else:
        c['D1'] = D
        c['D2'] = _n(g.get('D2'))
    c['D3'] = _n(g.get('D3'))
    c['L1'] = _n(g.get('L1'))
    c['L2'] = _n(g.get('L2')) or _n(getattr(tool, 'cut_length', 0))
    c['L3'] = _n(g.get('L3'))
    c['angle'] = angle
    c['R'] = _n(g.get('R')) or (_n(getattr(tool, 'diameter', 0)) / 2 if famille == 'boule' else 0.0)
    c['pointe'] = tip if (not gravure and 0 < tip < c['D1']) else 0.0
    c['dents'] = int(_n(g.get('dents')) or _n(getattr(tool, 'flutes', 0)))
    c['pas'] = _n(g.get('pas'))
    c['hauteur'] = _n(g.get('hauteur'))
    if not c['D1']:
        c['D1'] = 3.0
    if not c['D2']:
        c['D2'] = 6.0 if c['D1'] <= 6.0 else (8.0 if c['D1'] <= 8.0 else 10.0)
    if famille == 'tslot':
        c['D2'] = c['D2'] if c['D2'] < c['D1'] else min(6.0, 0.75 * c['D1'])
    if not c['L2']:
        c['L2'] = min(c['L3'], 3 * c['D1']) if c['L3'] else max(1.0, 2.0 * c['D1'])
    if not c['L1']:
        c['L1'] = max(40.0, c['L3'] + 15.0, c['L2'] + 20.0)
    return c


# ───────────────────────── le profil ─────────────────────────

class _Profil:
    def __init__(self):
        self.pts: List[Tuple[float, float]] = []

    def vers(self, r: float, z: float) -> None:
        r = max(EPS_POINTE, float(r))
        z = float(z)
        if self.pts:
            r0, z0 = self.pts[-1]
            z = max(z, z0)
            if abs(r - r0) < 1e-6 and abs(z - z0) < 1e-6:
                return
        self.pts.append((r, z))

    @property
    def r(self) -> float:
        return self.pts[-1][0]

    @property
    def z(self) -> float:
        return self.pts[-1][1]

    def arc(self, cr: float, cz: float, R: float, a0: float, a1: float,
            n: int = N_ARC) -> None:
        """Un arc (centre (cr, cz), rayon R) de a0 à a1 degrés."""
        for k in range(1, n + 1):
            a = math.radians(a0 + (a1 - a0) * k / n)
            self.vers(cr + R * math.cos(a), cz + R * math.sin(a))

    def passer_a(self, r_cible: float, z_mini: float = None) -> None:
        """Un raccord à 45° vers un autre rayon (queue, col)."""
        if z_mini is not None and z_mini > self.z:
            self.vers(self.r, z_mini)
        if abs(r_cible - self.r) > 1e-6:
            self.vers(r_cible, self.z + abs(r_cible - self.r))


def profil(c: Dict) -> Dict:
    """Le profil de révolution: {'points': [(r, z)], 'z_coupe'} de la
    pointe (z = 0) à la queue (z = L1)."""
    fam = c['famille']
    r1, r2 = c['D1'] / 2.0, c['D2'] / 2.0
    r3 = c['D3'] / 2.0
    L1, L2, L3 = c['L1'], c['L2'], c['L3']
    R = c['R']
    angle = c['angle']
    p = _Profil()
    z_coupe = L2

    def col_et_queue():
        """Après la coupe: le col (D3 jusqu'à L3), puis la queue."""
        if r3 > 0 and L3 > p.z + 1e-6:
            if r3 < p.r:
                p.vers(r3, p.z)            # épaulement
            else:
                p.passer_a(r3)
            p.vers(r3, L3)
        elif L3 > p.z + 1e-6 and fam not in ('surfacage',):
            p.vers(p.r, L3)
        p.passer_a(r2)
        p.vers(r2, max(L1, p.z + 1.0))

    if fam in ('fraise', 'surfacage', 'torique'):
        if R > 0 and R < r1:
            p.vers(r1 - R, 0.0)
            p.arc(r1 - R, R, R, -90.0, 0.0)
        else:
            p.vers(r1, 0.0)
        p.vers(r1, max(L2, p.z))
        col_et_queue()
    elif fam == 'boule':
        Rb = min(R or r1, r1)
        p.vers(EPS_POINTE, 0.0)
        p.arc(0.0, Rb, Rb, -90.0, 0.0)
        if r1 > Rb:
            p.vers(r1, Rb)
        p.vers(r1, max(L2, p.z))
        col_et_queue()
    elif fam == 'foret':
        a = math.radians(max(60.0, min(179.0, angle or 118.0)) / 2)
        p.vers(EPS_POINTE, 0.0)
        p.vers(r1, r1 / math.tan(a))
        p.vers(r1, max(L2, p.z))
        p.passer_a(r2)
        p.vers(r2, max(L1, p.z + 1.0))
    elif fam == 'conique':
        a = math.radians(max(5.0, min(170.0, angle or 30.0)) / 2)
        if c.get('gravure') or r1 < 0.3 * r2 or not L2 or \
                'grav' in c.get('libelle', '').lower():
            # une pointe à graver: D1 est la pointe, le cône monte à la
            # queue
            rp = max(EPS_POINTE, r1)
            p.vers(rp, 0.0)
            p.vers(r2, (r2 - rp) / math.tan(a))
            z_coupe = p.z
            p.vers(r2, max(L1, p.z + 1.0))
        else:
            # une fraise pour rainure en V: D1 en haut du cône
            rp = max(EPS_POINTE, c['pointe'] / 2.0)
            p.vers(rp, 0.0)
            p.vers(r1, (r1 - rp) / math.tan(a))
            p.vers(r1, max(L2, p.z))
            p.passer_a(r2)
            p.vers(r2, max(L1, p.z + 1.0))
    elif fam == 'chanfrein':
        a = math.radians(max(5.0, min(170.0, angle or 90.0)) / 2)
        if 0 < c.get('pointe', 0) < c['D1']:
            rp = c['pointe'] / 2.0         # la troncature de la fiche
        else:
            rp = r1 - L2 * math.tan(a) if L2 else 0.0
        rp = max(EPS_POINTE, rp)
        p.vers(rp, 0.0)
        p.vers(r1, (r1 - rp) / math.tan(a))
        z_coupe = p.z
        p.passer_a(r2)
        p.vers(r2, max(L1, p.z + 1.0))
    elif fam == 'rayon':
        # fraise à rayonner: un quart de cercle CREUX, de la pointe au Ø
        Rr = R or 1.0
        p.vers(r1, 0.0)
        p.arc(r1 + Rr, 0.0, Rr, 180.0, 90.0)
        z_coupe = p.z
        if L2 > p.z:
            p.vers(p.r, L2)
        col_et_queue()
    elif fam == 'filetage':
        rc = r3 if 0 < r3 < r1 else 0.7 * r1
        a = math.radians(max(20.0, min(120.0, angle or 60.0)) / 2)
        t = (r1 - rc) * math.tan(a)
        h = max(L2, 2 * t)
        p.vers(rc, 0.0)
        p.vers(r1, t)
        if h > 2 * t + 1e-6:
            p.vers(r1, h - t)
        p.vers(rc, h)
        z_coupe = h
        if L3 > p.z:
            p.vers(rc, L3)
        p.passer_a(r2)
        p.vers(r2, max(L1, p.z + 1.0))
    elif fam == 'tslot':
        h = c['hauteur'] or max(0.5, 0.2 * c['D1'])
        rc = 0.45 * r1
        portee = L3 or L2 or 3 * c['D1']
        p.vers(r1, 0.0)
        p.vers(r1, h)
        p.vers(rc, h)
        z_coupe = h
        p.vers(rc, max(portee, h + 1.0))
        p.passer_a(r2)
        p.vers(r2, max(L1, p.z + 1.0))
    else:
        p.vers(r1, 0.0)
        p.vers(r1, max(L2, 1.0))
        col_et_queue()
    pts = _nettoyer(p.pts)
    return {'points': pts, 'z_coupe': min(z_coupe, pts[-1][1])}


def _nettoyer(pts):
    """Ni deux points confondus, ni deux pas horizontaux de suite, ni un
    point au milieu d'un segment droit."""
    sortie = []
    for r, z in pts:
        if sortie and abs(sortie[-1][0] - r) < 1e-6 \
                and abs(sortie[-1][1] - z) < 1e-6:
            continue
        sortie.append((r, z))
    k = 1
    while k < len(sortie) - 1:
        (ra, za), (rb, zb), (rc, zc) = sortie[k - 1], sortie[k], sortie[k + 1]
        alignes = abs((rb - ra) * (zc - za) - (zb - za) * (rc - ra)) < 1e-9
        deux_plats = abs(za - zb) < 1e-9 and abs(zb - zc) < 1e-9
        if alignes or deux_plats:
            sortie.pop(k)
            continue
        k += 1
    return sortie


# ───────────────────────── le STEP ─────────────────────────

def _ascii(texte: str) -> str:
    import unicodedata
    t = unicodedata.normalize('NFKD', str(texte))
    return "".join(ch for ch in t if 32 <= ord(ch) < 127 and ch not in "'\\")


def _f(v: float) -> str:
    v = float(v)
    if abs(v) < 1e-12:
        return "0."
    s = f"{v:.9f}".rstrip('0')
    return s if not s.endswith('.') else s


class _Step:
    def __init__(self):
        self.lignes: List[str] = []

    def e(self, texte: str) -> str:
        self.lignes.append(texte)
        return f"#{len(self.lignes)}"

    def pt(self, x, y, z) -> str:
        return self.e(f"CARTESIAN_POINT('',({_f(x)},{_f(y)},{_f(z)}))")

    def dr(self, x, y, z) -> str:
        return self.e(f"DIRECTION('',({_f(x)},{_f(y)},{_f(z)}))")

    def axe(self, z: float, sens: float = 1.0) -> str:
        return self.e(f"AXIS2_PLACEMENT_3D('',{self.pt(0, 0, z)},"
                      f"{self.dr(0, 0, sens)},{self.dr(1, 0, 0)})")


def texte_step(points, nom: str = "outil", z_coupe: float = None,
               reference: str = "") -> str:
    """Le STEP (AP214) du solide de révolution du profil: une face par
    segment (plan, cylindre, cône), un disque en bas et en haut; la
    partie coupante (z ≤ z_coupe) en or, le corps en gris."""
    pts = _nettoyer([(max(EPS_POINTE, r), z) for r, z in points])
    st = _Step()
    nom_a = _ascii(nom) or "outil"
    ctx = st.e("APPLICATION_CONTEXT('core data for automotive mechanical "
               "design processes')")
    st.e(f"APPLICATION_PROTOCOL_DEFINITION('international standard',"
         f"'automotive_design',2000,{ctx})")
    pctx = st.e(f"PRODUCT_CONTEXT('',{ctx},'mechanical')")
    produit = st.e(f"PRODUCT('{_ascii(reference) or nom_a}','{nom_a}',"
                   f"'',({pctx}))")
    st.e(f"PRODUCT_RELATED_PRODUCT_CATEGORY('part',$,({produit}))")
    pdf = st.e(f"PRODUCT_DEFINITION_FORMATION('','',{produit})")
    pdc = st.e(f"PRODUCT_DEFINITION_CONTEXT('part definition',{ctx},"
               f"'design')")
    pd = st.e(f"PRODUCT_DEFINITION('design','',{pdf},{pdc})")
    pds = st.e(f"PRODUCT_DEFINITION_SHAPE('','',{pd})")
    lg = st.e("(LENGTH_UNIT()NAMED_UNIT(*)SI_UNIT(.MILLI.,.METRE.))")
    an = st.e("(NAMED_UNIT(*)PLANE_ANGLE_UNIT()SI_UNIT($,.RADIAN.))")
    so = st.e("(NAMED_UNIT(*)SI_UNIT($,.STERADIAN.)SOLID_ANGLE_UNIT())")
    unc = st.e(f"UNCERTAINTY_MEASURE_WITH_UNIT(LENGTH_MEASURE(1.E-07),"
               f"{lg},'distance_accuracy_value','confusion accuracy')")
    rctx = st.e(f"(GEOMETRIC_REPRESENTATION_CONTEXT(3)"
                f"GLOBAL_UNCERTAINTY_ASSIGNED_CONTEXT(({unc}))"
                f"GLOBAL_UNIT_ASSIGNED_CONTEXT(({lg},{an},{so}))"
                f"REPRESENTATION_CONTEXT('Context #1',"
                f"'3D Context with UNIT and UNCERTAINTY'))")
    # les cercles (un par point du profil) et leurs sommets
    sommets, cercles = [], []
    for r, z in pts:
        v = st.e(f"VERTEX_POINT('',{st.pt(r, 0, z)})")
        c = st.e(f"CIRCLE('',{st.axe(z)},{_f(r)})")
        cercles.append(st.e(f"EDGE_CURVE('',{v},{v},{c},.T.)"))
        sommets.append(v)

    def oe(arete, sens: bool) -> str:
        return st.e(f"ORIENTED_EDGE('',*,*,{arete},{'.T.' if sens else '.F.'})")

    def boucle(aretes) -> str:
        return st.e(f"EDGE_LOOP('',({','.join(aretes)}))")

    faces = []          # (face, en coupe)
    # le disque du bas (vers −Z)
    surf = st.e(f"PLANE('',{st.axe(pts[0][1], -1.0)})")
    b = st.e(f"FACE_OUTER_BOUND('',{boucle([oe(cercles[0], False)])},.T.)")
    faces.append((st.e(f"ADVANCED_FACE('',({b}),{surf},.T.)"), True))
    for i in range(len(pts) - 1):
        (ra, za), (rb, zb) = pts[i], pts[i + 1]
        coupe = (za + zb) / 2 <= (z_coupe if z_coupe is not None
                                  else -1) + 1e-9
        if abs(zb - za) < 1e-9:
            # un épaulement: une couronne plane
            if rb < ra:          # le dessus de la partie large (+Z)
                surf = st.e(f"PLANE('',{st.axe(za, 1.0)})")
                ext = st.e(f"FACE_OUTER_BOUND('',"
                           f"{boucle([oe(cercles[i], True)])},.T.)")
                inte = st.e(f"FACE_BOUND('',"
                            f"{boucle([oe(cercles[i + 1], False)])},.T.)")
            else:                # le dessous de la partie large (−Z)
                surf = st.e(f"PLANE('',{st.axe(za, -1.0)})")
                ext = st.e(f"FACE_OUTER_BOUND('',"
                           f"{boucle([oe(cercles[i + 1], False)])},.T.)")
                inte = st.e(f"FACE_BOUND('',"
                            f"{boucle([oe(cercles[i], True)])},.T.)")
            faces.append((st.e(f"ADVANCED_FACE('',({ext},{inte}),{surf},"
                               f".T.)"), coupe))
            continue
        if abs(rb - ra) < 1e-9:
            surf = st.e(f"CYLINDRICAL_SURFACE('',{st.axe(za)},{_f(ra)})")
        else:
            demi = math.atan(abs(rb - ra) / (zb - za))
            surf = st.e(f"CONICAL_SURFACE('',"
                        f"{st.axe(za, 1.0 if rb > ra else -1.0)},"
                        f"{_f(ra)},{_f(demi)})")
        dv = (rb - ra, 0.0, zb - za)
        lg_s = math.hypot(dv[0], dv[2])
        vec = st.e(f"VECTOR('',{st.dr(dv[0] / lg_s, 0, dv[2] / lg_s)},{_f(lg_s)})")   # entité à part
        ligne = st.e(f"LINE('',{st.pt(ra, 0, za)},{vec})")
        couture = st.e(f"EDGE_CURVE('',{sommets[i]},{sommets[i + 1]},"
                       f"{ligne},.T.)")
        b = st.e(f"FACE_OUTER_BOUND('',{boucle([oe(cercles[i], True), oe(couture, True), oe(cercles[i + 1], False), oe(couture, False)])},.T.)")
        faces.append((st.e(f"ADVANCED_FACE('',({b}),{surf},.T.)"), coupe))
    # le disque du haut (vers +Z)
    surf = st.e(f"PLANE('',{st.axe(pts[-1][1], 1.0)})")
    b = st.e(f"FACE_OUTER_BOUND('',{boucle([oe(cercles[-1], True)])},.T.)")
    faces.append((st.e(f"ADVANCED_FACE('',({b}),{surf},.T.)"), False))
    coque = st.e(f"CLOSED_SHELL('',({','.join(f for f, _c in faces)}))")
    brep = st.e(f"MANIFOLD_SOLID_BREP('{nom_a}',{coque})")
    origine = st.axe(0.0)
    absr = st.e(f"ADVANCED_BREP_SHAPE_REPRESENTATION('',({brep},{origine}),"
                f"{rctx})")
    st.e(f"SHAPE_DEFINITION_REPRESENTATION({pds},{absr})")
    # les couleurs: la coupe en or, le corps en gris
    styles = []
    for teinte, rgb in (('coupe', (0.85, 0.68, 0.25)),
                        ('corps', (0.62, 0.64, 0.68))):
        col = st.e(f"COLOUR_RGB('{teinte}',{_f(rgb[0])},{_f(rgb[1])},"
                   f"{_f(rgb[2])})")
        fsc = st.e(f"FILL_AREA_STYLE_COLOUR('',{col})")
        fas = st.e(f"FILL_AREA_STYLE('',({fsc}))")
        ssfa = st.e(f"SURFACE_STYLE_FILL_AREA({fas})")
        sss = st.e(f"SURFACE_SIDE_STYLE('',({ssfa}))")
        ssu = st.e(f"SURFACE_STYLE_USAGE(.BOTH.,{sss})")
        styles.append(st.e(f"PRESENTATION_STYLE_ASSIGNMENT(({ssu}))"))
    items = [st.e(f"STYLED_ITEM('',({styles[0] if c else styles[1]}),{f})")
             for f, c in faces]
    st.e(f"MECHANICAL_DESIGN_GEOMETRIC_PRESENTATION_REPRESENTATION('',"
         f"({','.join(items)}),{rctx})")
    date = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
    entete = ["ISO-10303-21;", "HEADER;",
              "FILE_DESCRIPTION(('VectorDrive - outil dessine depuis ses "
              "cotes'),'2;1');",
              f"FILE_NAME('{nom_a}.step','{date}',('VectorDrive'),(''),"
              f"'VectorDrive','VectorDrive','');",
              "FILE_SCHEMA(('AUTOMOTIVE_DESIGN { 1 0 10303 214 1 1 1 1 }'));",
              "ENDSEC;", "DATA;"]
    corps = [f"#{k + 1}={ligne};" for k, ligne in enumerate(st.lignes)]
    return "\n".join(entete + corps + ["ENDSEC;", "END-ISO-10303-21;", ""])


def ecrire_step(chemin: str, points, nom: str = "outil",
                z_coupe: float = None, reference: str = "") -> str:
    with open(chemin, 'w', encoding='ascii', newline='\n') as f:
        f.write(texte_step(points, nom, z_coupe, reference))
    return chemin


# ───────────────────────── le DXF ─────────────────────────

def ecrire_dxf(chemin: str, points, cotes: Dict, nom: str = "outil",
               z_coupe: float = None, reference: str = "") -> str:
    """L'outil debout, pointe en bas à l'origine: la silhouette (la
    partie coupante sur son calque), l'axe, les cotes (Ø D1, Ø D2, L1,
    L2, L3), l'angle et le rayon, un cartouche; et le demi-profil de
    révolution (calque PROFIL) pour une FAO."""
    import ezdxf
    pts = [(max(0.0, r), z) for r, z in points]
    doc = ezdxf.new('R2010', setup=True)
    doc.units = 4                  # mm (ezdxf: mètres par défaut)
    doc.header['$MEASUREMENT'] = 1
    msp = doc.modelspace()
    for calque, couleur, ltype in (('CONTOUR', 7, 'CONTINUOUS'),
                                   ('COUPE', 2, 'CONTINUOUS'),
                                   ('AXE', 1, 'CENTER'),
                                   ('COTES', 3, 'CONTINUOUS'),
                                   ('TEXTE', 7, 'CONTINUOUS'),
                                   ('PROFIL', 4, 'CONTINUOUS')):
        if calque not in doc.layers:
            doc.layers.add(calque, color=couleur, linetype=ltype)
    L1 = pts[-1][1]
    zc = z_coupe if z_coupe is not None else 0.0
    # la silhouette: le côté droit, le dessus, le côté gauche, le dessous
    droite = list(pts)
    gauche = [(-r, z) for r, z in reversed(pts)]
    contour = droite + gauche
    msp.add_lwpolyline(contour, close=True, dxfattribs={'layer': 'CONTOUR'})
    # la partie coupante, en couleur, par-dessus
    for sgn in (1.0, -1.0):
        seg = [(sgn * r, z) for r, z in pts if z <= zc + 1e-9]
        if len(seg) >= 2:
            msp.add_lwpolyline(seg, dxfattribs={'layer': 'COUPE'})
    if zc > 0:
        r_c = max((r for r, z in pts if z <= zc + 1e-9), default=0.0)
        msp.add_line((-r_c, zc), (r_c, zc), dxfattribs={'layer': 'COUPE'})
    # l'axe
    msp.add_line((0, -2.0), (0, L1 + 2.0), dxfattribs={'layer': 'AXE'})
    # le demi-profil de révolution (fermé sur l'axe)
    demi = [(0.0, pts[0][1])] + pts + [(0.0, L1)]
    msp.add_lwpolyline(demi, close=True, dxfattribs={'layer': 'PROFIL'})
    # éteint: il double la silhouette; une FAO l'allume
    doc.layers.get('PROFIL').off()
    # les cotes
    hauteur = max(0.8, min(3.0, L1 / 30.0))
    style = doc.dimstyles.get('EZDXF')
    style.dxf.dimtxt = hauteur
    style.dxf.dimasz = hauteur * 0.8
    style.dxf.dimexe = hauteur * 0.4
    style.dxf.dimexo = hauteur * 0.3
    style.dxf.dimdec = 2
    style.dxf.dimzin = 8
    rmax = max(r for r, _z in pts)

    def cote_h(r, z, texte, ecart):
        if r <= 0:
            return
        d = msp.add_linear_dim(base=(0, z + ecart), p1=(-r, z), p2=(r, z),
                               angle=0, dimstyle='EZDXF', text=texte,
                               dxfattribs={'layer': 'COTES'})
        d.render()

    def cote_v(z0, z1, x, texte):
        if z1 - z0 <= 1e-6:
            return
        d = msp.add_linear_dim(base=(x, (z0 + z1) / 2), p1=(rmax, z0),
                               p2=(rmax, z1), angle=90, dimstyle='EZDXF',
                               text=texte, dxfattribs={'layer': 'COTES'})
        d.render()

    D1, D2 = cotes.get('D1', 0), cotes.get('D2', 0)
    r_coupe = max((r for r, z in pts if z <= max(zc, 1e-6) + 1e-9),
                  default=D1 / 2)
    cote_h(r_coupe, max(zc, 0.0) * 0.5, f"%%c{D1:g}", -0.0)
    z_queue = (pts[-1][1] + max(z for _r, z in pts[:-1])) / 2
    cote_h(pts[-1][0], z_queue, f"%%c{D2:g}", 0.0)
    pas = 3 * hauteur
    cote_v(0.0, L1, rmax + 4 * pas, f"{round(L1, 2):g}")
    if zc > 0:
        cote_v(0.0, zc, rmax + 2 * pas, f"{round(zc, 2):g}")
    L3 = cotes.get('L3', 0)
    if L3 and L3 > zc + 1e-6 and L3 < L1 - 1e-6:
        cote_v(0.0, L3, rmax + 3 * pas, f"{round(L3, 2):g}")
    notes = []
    if cotes.get('angle'):
        notes.append(f"{cotes['angle']:g}%%d")
    if cotes.get('R'):
        notes.append(f"R{cotes['R']:g}")
    if notes:
        msp.add_text(" ".join(notes), height=hauteur,
                     dxfattribs={'layer': 'COTES'}).set_placement(
            (rmax + hauteur, -hauteur * 1.5))
    # le cartouche
    lignes = [nom, f"Ref. {reference}" if reference else "",
              cotes.get('libelle', ''),
              f"D1 {D1:g}  D2 {D2:g}"
              + (f"  D3 {cotes['D3']:g}" if cotes.get('D3') else ""),
              f"L1 {L1:g}  L2 {cotes.get('L2', 0):g}"
              + (f"  L3 {L3:g}" if L3 else ""),
              (f"{cotes['dents']} dent(s)" if cotes.get('dents') else ""),
              f"Source: {cotes.get('source', '')}"]
    y = L1
    for ligne in [l for l in lignes if l]:
        msp.add_text(ligne, height=hauteur,
                     dxfattribs={'layer': 'TEXTE'}).set_placement(
            (rmax + 7 * pas, y))
        y -= hauteur * 1.6
    doc.saveas(chemin)
    return chemin


# ───────────────────────── pour l'interface et l'appel ─────────────────────────

def profile_of(tool) -> Dict:
    """Profil de révolution d'un outil : {'points', 'z_coupe', 'cotes'}."""
    c = cotes_outil(tool)
    p = profil(c)
    p['cotes'] = c
    return p


def outline(tool) -> Tuple[List[Tuple[float, float]], float]:
    """Silhouette de l'outil debout, pointe en bas (x = r, y = z) :
    contour fermé et hauteur de la partie coupante."""
    p = profile_of(tool)
    pts = p['points']
    return [(r, z) for r, z in pts] + [(-r, z) for r, z in reversed(pts)], p['z_coupe']


def write_drawings(tool, folder, stem: str | None = None) -> Dict[str, str]:
    """DXF et STEP de l'outil dans `folder` ; rend leurs chemins."""
    import pathlib
    folder = pathlib.Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    stem = stem or (getattr(tool, 'ref', '') or getattr(tool, 'name', '') or 'outil')
    stem = ''.join(ch if ch.isalnum() or ch in '-_.' else '_' for ch in stem).strip('_') or 'outil'
    p = profile_of(tool)
    name, ref = getattr(tool, 'name', '') or stem, getattr(tool, 'ref', '')
    step = ecrire_step(str(folder / f'{stem}.step'), p['points'], name, p['z_coupe'], ref)
    dxf = ecrire_dxf(str(folder / f'{stem}.dxf'), p['points'], p['cotes'], name, p['z_coupe'], ref)
    return {'dxf': dxf, 'step': step, 'genere_le': datetime.now().isoformat(timespec='seconds')}
