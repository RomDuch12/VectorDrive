"""Électroérosion à fil (demande du 26/11 : « fonction de calcul angle fil (avec u et v) qui détecte les chutes
matière qui se détachent du brut et coupent le fil »).

Une opération de nature `KIND` découpe des contours au fil : ses réglages vivent dans `Operation.params` (voir
`DEFAULTS`), les champs communs de l'opération gardent leur sens (objets ou couleurs usinés, côté : `side`
'exterieur' = la pièce est dedans, 'interieur' = un trou, 'sur' = sur le trait ; ordre `order_mode`).

- **Décalage** : saignée = Ø du fil + 2 × étincelage ; le centre du fil passe à Ø/2 + étincelage du contour (plus la
  surépaisseur des passes de reprise). Soit la commande décale (G41/G42 et un registre D par passe, le contour
  programmé est celui du dessin), soit le parcours est décalé ici (G40).
- **Inclinaison** : aucune, dépouille constante (un angle signé : + = fil penché à gauche du sens de coupe, G51 ;
  − = à droite, G52 ; la commande calcule U/V), ou contours haut et bas différents (deux contours du dessin reliés
  point à point, U/V écrits à chaque point). U/V = écart du guide haut par rapport au guide bas :
  (dessus − dessous) × distance entre guides ÷ épaisseur ; X/Y = le point au plan de programmation.
- **Chutes** (`find_pieces`) : la matière (brut du dessin, sinon la plaque) moins les saignées, coupe après coupe ;
  un morceau qui se sépare du morceau tenu (celui du point bridé, sinon le plus grand de ceux qui touchent le bord du
  brut) tombe à la fin de la coupe qui le libère. Son risque pour le fil (`assess`) et deux propositions : incliner
  le fil (angle minimal `min_taper`) ou laisser une attache (micro-pont coupé après un arrêt programmé).

Le parcours (`compute`) porte, en plus des mouvements montrés (au plan de programmation, Z 0), un cycle
`{'kind': 'fil_edm', …}` : la suite des blocs que le post-processeur d'électroérosion écrit (`cam.post.robocut`).
Ce qui peut casser le fil ou la pièce est un avertissement qui commence par `BLOCKING` (« BLOQUANT ») : la
vérification avant l'écriture le reconnaît et le post-processeur n'écrit rien. Règles et hypothèses : NOTES du
round. Rien n'a été essayé sur une machine.
"""
from __future__ import annotations

import math

KIND = 'fil_edm'
LABEL = 'Électroérosion à fil (contours, fil incliné, chutes)'
#: distance entre guides prise quand elle n'est pas donnée : l'épaisseur plus ceci (mm)
GUIDE_GAP = 20.0
#: épaisseur prise sans brut ni plaque épaisse (mm)
DEFAULT_THICKNESS = 10.0
#: début des avertissements qui bloquent l'écriture du programme (reconnu par `cam.preflight`)
BLOCKING = 'BLOQUANT'

#: réglages de l'opération (`Operation.params`) et leurs valeurs d'office
DEFAULTS = {
    'epaisseur': 0.0,           # mm ; 0 : celle du brut du dessin, sinon de la plaque
    'plan_prog': 0.0,           # hauteur du plan de programmation au-dessus de la table (dessous de la pièce, mm)
    'guides': 0.0,              # distance entre le guide bas et le guide haut (mm) ; 0 : épaisseur + GUIDE_GAP,
    #                             sauf contours haut et bas (les U/V en dépendent : à donner, sinon bloquant)
    'fil': 0.25,                # Ø du fil (mm)
    'gap': 0.02,                # étincelage, de chaque côté (mm)
    'compensation': 'g41',      # 'g41' : la commande décale (G41/G42 D) ; 'calcul' : parcours décalé ici (G40)
    'passes': 1,                # passes : la première, puis des reprises
    'surep_passe': 0.03,        # matière laissée à chaque reprise (mm)
    'inclinaison': 'aucune',    # 'aucune', 'constante', 'haut_bas'
    'angle': 0.0,               # dépouille constante (°) : + à gauche du sens de coupe (G51), − à droite (G52)
    'bas': '',                  # haut/bas : l'objet du contour du dessous
    'haut': '',                 # … et celui du dessus
    'sens': 'trigo',            # contours fermés : 'trigo', 'horaire', 'dessin'
    'approche': 3.0,            # du trou de départ au contour (mm)
    'attache': 1.0,             # longueur de matière d'une attache (mm)
    'attaches': [],             # attaches posées : [{'x', 'y', 'longueur'}]
    'attache_coupe': 'fin',     # 'fin' : coupées après un arrêt, à la fin de l'opération ; 'apart' : programme à part
    'retenue': 'coincee',       # proposition d'inclinaison : 'coincee' (la chute reste) ou 'libre' (elle tombe)
    'descente': 0.5,            # chute coincée : descente admise avant le coincement (fraction de l'épaisseur)
    'densite': 7.85,            # g/cm³ (acier)
    'lourde': 100.0,            # g : au-delà, la chute s'affaisse en fin de coupe
    'angle_max': 30.0,          # ° : l'inclinaison la plus forte de la machine (la seule limite : au-delà, bloquant)
    'bride': [],                # [x, y] : un point de la partie bridée ; vide : le plus grand morceau au bord
}
CHOICES = {'compensation': ('g41', 'calcul'), 'inclinaison': ('aucune', 'constante', 'haut_bas'),
           'sens': ('trigo', 'horaire', 'dessin'), 'attache_coupe': ('fin', 'apart'),
           'retenue': ('coincee', 'libre')}
#: libellés des choix dans le formulaire de l'opération (la valeur gardée y est le libellé : `params_of` le relit)
CHOICE_LABELS = {
    'compensation': {'g41': 'Par la commande (G41 / G42, registres D)', 'calcul': 'Calculé ici (parcours décalé, G40)'},
    'inclinaison': {'aucune': 'Aucune (fil droit)', 'constante': 'Dépouille constante (un angle)',
                    'haut_bas': 'Contours haut et bas (U/V à chaque point)'},
    'sens': {'trigo': 'Sens trigonométrique', 'horaire': 'Sens horaire', 'dessin': 'Sens du dessin'},
    'attache_coupe': {'fin': 'À la fin de l’opération, après un arrêt', 'apart': 'Dans un programme à part'},
    'retenue': {'coincee': 'Coincée dans la pièce', 'libre': 'Tombe librement'},
}


def _choice(key: str, label: str = 'Choix') -> tuple:
    labels = CHOICE_LABELS[key]
    return key, label, 'choice', labels[DEFAULTS[key]], list(labels.values())


#: le formulaire de l'opération (`cam.instructions.KIND_PARAMS`) : (clé, libellé, type, défaut[, choix])
FORM_FIELDS = [
    ('epaisseur', 'Épaisseur de la pièce (mm, 0 : celle du brut ou de la plaque)', 'float', 0.0),
    ('fil', 'Ø du fil (mm)', 'float', 0.25),
    ('gap', 'Étincelage, de chaque côté (mm)', 'float', 0.02),
    _choice('compensation', 'Décalage du fil'),
    _choice('inclinaison', 'Inclinaison du fil'),
    ('angle', 'Dépouille constante (°, + : fil penché à gauche du sens de coupe, G51 ; − : à droite, G52)', 'float',
     0.0),
    ('plan_prog', 'Plan de programmation : hauteur au-dessus de la table (mm)', 'float', 0.0),
    ('guides', 'Distance entre les guides (mm, 0 : épaisseur + 20 ; à donner pour les contours haut et bas)', 'float',
     0.0),
    _choice('sens', 'Sens de coupe des contours fermés'),
    ('approche', 'Trou de départ : distance au contour (mm)', 'float', 3.0),
    ('passes', 'Passes (la première, puis les reprises)', 'int', 1),
    ('attache', 'Longueur d’une attache proposée (mm)', 'float', 1.0),
    _choice('attache_coupe', 'Coupe des attaches'),
    _choice('retenue', 'Inclinaison proposée pour une chute'),
    ('surep_passe', 'Matière laissée à chaque reprise (mm)', 'float', 0.03),
    ('descente', 'Chute coincée : descente admise (fraction de l’épaisseur)', 'float', 0.5),
    ('densite', 'Densité de la matière (g/cm³)', 'float', 7.85),
    ('lourde', 'Chute lourde à partir de (g)', 'float', 100.0),
    ('angle_max', 'Inclinaison la plus forte de la machine (°)', 'float', 30.0),
    ('bas', 'Contour du dessous (contours haut et bas)', 'str', ''),
    ('haut', 'Contour du dessus (contours haut et bas)', 'str', ''),
]
FORM_ADVANCED = ('surep_passe', 'descente', 'densite', 'lourde', 'angle_max', 'bas', 'haut')
FORM_NOTE = ('Contours haut et bas : sélectionner le contour du dessous puis celui du dessus (une sélection au cadre '
             'suit l\'ordre du dessin : nommer alors les objets « dessous » et « dessus »), puis « Prendre sur la '
             'sélection », et donner la distance entre les guides. Les chutes qui se détachent sont signalées après '
             'le calcul, avec les propositions (incliner le fil, laisser une attache).')
#: niveaux de risque, du plus faible au plus fort
RISKS = ('faible', 'moyen', 'fort')
#: aire (mm²) en deçà de laquelle une petite chute tombe sans gêner le fil, même plus haute que large
SMALL_AREA = 4.0


def _num(v, default: float, lo: float | None = 0.0, hi: float | None = None) -> float:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(x):
        return default
    if lo is not None:
        x = max(lo, x)
    if hi is not None:
        x = min(hi, x)
    return x


def params_of(op) -> dict:
    """Les réglages d'électroérosion de l'opération : `DEFAULTS` complétés par `op.params`, nombres bornés, choix
    inconnus remis à leur valeur d'office."""
    raw = getattr(op, 'params', None)
    raw = raw if isinstance(raw, dict) else {}
    p = dict(DEFAULTS)
    for k, v in DEFAULTS.items():
        if k not in raw:
            continue
        if isinstance(v, float):
            p[k] = _num(raw[k], v, None if k == 'angle' else 0.0)
        elif isinstance(v, int):
            p[k] = int(_num(raw[k], v, 1, 9))
        elif isinstance(v, str):
            p[k] = str(raw[k] or '')
        else:
            p[k] = list(raw[k]) if isinstance(raw[k], (list, tuple)) else list(v)
    for k, allowed in CHOICES.items():
        back = {lab: key for key, lab in CHOICE_LABELS.get(k, {}).items()}
        p[k] = back.get(p[k], p[k])                     # le libellé du formulaire : sa clé
        if p[k] not in allowed:
            p[k] = DEFAULTS[k]
    p['angle'] = _num(p['angle'], 0.0, -89.0, 89.0)
    p['descente'] = _num(p['descente'], 0.5, 0.05, 1.0)
    p['attaches'] = [dict(x=float(a['x']), y=float(a['y']), longueur=_num(a.get('longueur'), p['attache']))
                     for a in p['attaches'] if isinstance(a, dict) and _is_xy(a.get('x'), a.get('y'))]
    b = p['bride']
    p['bride'] = [float(b[0]), float(b[1])] if len(b) >= 2 and _is_xy(b[0], b[1]) else []
    return p


def _is_xy(x, y) -> bool:
    try:
        return math.isfinite(float(x)) and math.isfinite(float(y))
    except (TypeError, ValueError):
        return False


def kerf(p: dict) -> float:
    """Largeur de la saignée (mm) : Ø du fil + 2 × étincelage."""
    return max(1e-3, p['fil'] + 2 * p['gap'])


def offsets(p: dict) -> list:
    """Décalage du centre du fil à chaque passe (mm), de la première à la dernière : Ø/2 + étincelage, plus la
    surépaisseur laissée aux reprises qui suivent."""
    n = max(1, int(p['passes']))
    base = p['fil'] / 2 + p['gap']
    return [base + p['surep_passe'] * (n - 1 - i) for i in range(n)]


# --- géométrie des tracés ------------------------------------------------------------------------------------------
# Un tracé est une liste de points ; un point est (x, y), ou (xb, yb, xh, yh) pour un contour haut/bas (le dessous,
# puis le point du dessus qui lui est relié). Les longueurs se prennent sur (x, y) ; les autres coordonnées suivent.
# Un tracé fermé répète son premier point à la fin.

def _xy(p) -> tuple:
    return float(p[0]), float(p[1])


def _same(a, b, eps: float = 1e-9) -> bool:
    return all(abs(u - v) <= eps for u, v in zip(a, b))


def _clean(pts: list) -> list:
    """Points consécutifs confondus retirés (toutes les coordonnées)."""
    out = []
    for p in pts:
        q = tuple(float(v) for v in p)
        if not out or not _same(out[-1], q):
            out.append(q)
    return out


def _interp(a, b, t: float) -> tuple:
    return tuple(u + (v - u) * t for u, v in zip(a, b))


def signed_area(pts: list) -> float:
    """Aire signée (> 0 : sens trigonométrique) d'un tracé fermé, premier point répété ou non."""
    P = [_xy(p) for p in pts]
    if len(P) > 1 and _same(P[0], P[-1]):
        P = P[:-1]
    return 0.5 * sum(P[i][0] * P[(i + 1) % len(P)][1] - P[(i + 1) % len(P)][0] * P[i][1] for i in range(len(P)))


def cumulative(pts: list) -> list:
    out = [0.0]
    for a, b in zip(pts, pts[1:]):
        out.append(out[-1] + math.dist(_xy(a), _xy(b)))
    return out


def length(pts: list) -> float:
    return cumulative(pts)[-1] if len(pts) >= 2 else 0.0


def point_at(pts: list, s: float, cum: list | None = None) -> tuple:
    """(point, rang du segment) à l'abscisse curviligne `s` du tracé."""
    cum = cum or cumulative(pts)
    s = min(max(0.0, s), cum[-1])
    for i in range(len(pts) - 1):
        if s <= cum[i + 1] + 1e-12:
            L = cum[i + 1] - cum[i]
            return _interp(pts[i], pts[i + 1], (s - cum[i]) / L if L > 1e-15 else 0.0), i
    return tuple(pts[-1]), max(0, len(pts) - 2)


def sub_path(pts: list, s0: float, s1: float) -> list:
    """Le morceau du tracé de l'abscisse `s0` à `s1` (s0 < s1), bouts interpolés."""
    cum = cumulative(pts)
    a, i = point_at(pts, s0, cum)
    b, j = point_at(pts, s1, cum)
    return _clean([a] + [tuple(pts[k]) for k in range(i + 1, j + 1)] + [b])


def rotate_ring(pts: list, s: float) -> list:
    """Le tracé fermé repris à partir de l'abscisse `s` (un point ajouté là au besoin)."""
    cum = cumulative(pts)
    S = cum[-1]
    if S <= 1e-12:
        return list(pts)
    q, i = point_at(pts, s % S, cum)
    ring = [tuple(p) for p in pts[:-1]]
    return _clean([q] + ring[i + 1:] + ring[:i + 1] + [q])


def project(pts: list, q) -> tuple:
    """(abscisse, distance) du point du tracé le plus proche de `q`."""
    cum = cumulative(pts)
    best = (0.0, math.inf)
    qx, qy = _xy(q)
    for i in range(len(pts) - 1):
        (ax, ay), (bx, by) = _xy(pts[i]), _xy(pts[i + 1])
        dx, dy = bx - ax, by - ay
        L2 = dx * dx + dy * dy
        t = 0.0 if L2 <= 1e-24 else min(1.0, max(0.0, ((qx - ax) * dx + (qy - ay) * dy) / L2))
        d = math.hypot(ax + dx * t - qx, ay + dy * t - qy)
        if d < best[1]:
            best = (cum[i] + t * (cum[i + 1] - cum[i]), d)
    return best


def _dirs(P: list, closed: bool) -> list:
    """Direction unitaire de chaque segment ; un segment nul prend celle d'un voisin."""
    n = len(P)
    m = n if closed else n - 1
    out = []
    for i in range(m):
        a, b = P[i], P[(i + 1) % n]
        L = math.dist(a, b)
        out.append(((b[0] - a[0]) / L, (b[1] - a[1]) / L) if L > 1e-12 else None)
    good = [d for d in out if d is not None]
    if not good:
        return []
    last = next(d for d in reversed(out) if d is not None) if closed else good[0]
    for i in range(m):
        if out[i] is None:
            out[i] = last
        last = out[i]
    return out


def miter_offset(pts: list, d: float, closed: bool = True, limit: float = 4.0, insert: bool = True) -> list:
    """Tracé décalé de `d` (> 0 : à gauche du sens de parcours). Angles rentrants : le point où le fil touche les deux
    côtés (onglet entier) ; angles saillants : l'onglet, ou au-delà de `limit` × d deux points d'équerre (`insert`),
    sinon l'onglet borné (contours haut/bas : le nombre de points doit rester celui de l'autre contour)."""
    P = [_xy(p) for p in pts]
    if closed and len(P) > 1 and _same(P[0], P[-1]):
        P = P[:-1]
    n = len(P)
    D = _dirs(P, closed) if n >= 2 else []
    if not D or abs(d) < 1e-15:
        return [tuple(p) for p in P] + ([tuple(P[0])] if closed and P else [])
    out = []
    for i in range(n):
        prev = D[i - 1] if (closed or i > 0) else D[0]
        nxt = D[i] if (closed or i < len(D)) else D[-1]
        n1, n2 = (-prev[1], prev[0]), (-nxt[1], nxt[0])
        bx, by = n1[0] + n2[0], n1[1] + n2[1]
        L = math.hypot(bx, by)
        x, y = P[i]
        if L < 1e-9:                                     # demi-tour : d'équerre au bout
            if insert:
                out += [(x + d * n1[0] + abs(d) * prev[0], y + d * n1[1] + abs(d) * prev[1]),
                        (x + d * n2[0] + abs(d) * prev[0], y + d * n2[1] + abs(d) * prev[1])]
            else:
                out.append((x + d * n1[0], y + d * n1[1]))
            continue
        bx, by = bx / L, by / L
        c = bx * n1[0] + by * n1[1]                      # cosinus du demi-angle
        turn = prev[0] * nxt[1] - prev[1] * nxt[0]       # > 0 : virage à gauche
        outward = (turn < 0) == (d > 0)                  # l'onglet s'éloigne de l'angle
        if outward and c < 1.0 / limit:
            if insert:
                a = abs(d)
                out += [(x + d * n1[0] + a * prev[0], y + d * n1[1] + a * prev[1]),
                        (x + d * n2[0] - a * nxt[0], y + d * n2[1] - a * nxt[1])]
                continue
            c = 1.0 / limit
        k = d / max(c, 1e-6)
        out.append((x + k * bx, y + k * by))
    if closed:
        out.append(out[0])
    return out


def offset_path(pts: list, d: float, closed: bool) -> list:
    """`miter_offset` d'un tracé (x, y) ou haut/bas (le dessous et le dessus décalés chacun, points gardés en
    regard)."""
    if pts and len(pts[0]) == 4:
        lo = miter_offset([p[:2] for p in pts], d, closed, insert=False)
        hi = miter_offset([p[2:4] for p in pts], d, closed, insert=False)
        return [(a[0], a[1], b[0], b[1]) for a, b in zip(lo, hi)]
    return miter_offset(pts, d, closed)


def _sample(pts: list, ts: list) -> list:
    cum = cumulative(pts)
    return [point_at(pts, t * cum[-1], cum)[0] for t in ts]


def pair_contours(bas: list, haut: list, closed: bool) -> list:
    """Le contour du dessous et celui du dessus reliés point à point : [(xb, yb, xh, yh)]. Même nombre de points :
    reliés tels quels (le dessus tourné pour que les paires soient les plus courtes) ; sinon chaque sommet de l'un a
    son point sur l'autre à la même fraction de longueur. Fermés : même sens que le dessous."""
    B = [_xy(p) for p in _clean(bas)]
    H = [_xy(p) for p in _clean(haut)]
    if closed:
        B = B[:-1] if len(B) > 1 and _same(B[0], B[-1]) else B
        H = H[:-1] if len(H) > 1 and _same(H[0], H[-1]) else H
        if (signed_area(B) > 0) != (signed_area(H) > 0):
            H = H[::-1]
        if len(B) == len(H) and len(B) <= 2000:
            n = len(B)
            r = min(range(n), key=lambda k: sum(math.dist(B[i], H[(i + k) % n]) for i in range(n)))
        else:
            r = min(range(len(H)), key=lambda k: math.dist(B[0], H[k]))
        H = H[r:] + H[:r]
        if len(B) == len(H):
            out = [(b[0], b[1], h[0], h[1]) for b, h in zip(B, H)]
            return out + [out[0]]
        B, H = B + [B[0]], H + [H[0]]
    elif len(B) == len(H):
        return [(b[0], b[1], h[0], h[1]) for b, h in zip(B, H)]
    tb = [c / cumulative(B)[-1] for c in cumulative(B)] if length(B) > 0 else [0.0]
    th = [c / cumulative(H)[-1] for c in cumulative(H)] if length(H) > 0 else [0.0]
    ts = sorted({round(t, 12) for t in tb + th})
    return [(b[0], b[1], h[0], h[1]) for b, h in zip(_sample(B, ts), _sample(H, ts))]


def prog_points(path: list, T: float, H: float, zp: float) -> list:
    """Les points programmés (x, y, u, v) : (x, y) au plan de programmation `zp` (hauteur au-dessus du dessous de la
    pièce), (u, v) = écart du guide haut par rapport au guide bas, pour une distance entre guides `H` et une
    épaisseur `T`. Un tracé (x, y) seul : fil droit, U/V nuls."""
    out = []
    for p in path:
        if len(p) == 4 and T > 0:
            dx, dy = p[2] - p[0], p[3] - p[1]
            out.append((p[0] + dx * zp / T, p[1] + dy * zp / T, dx * H / T, dy * H / T))
        else:
            out.append((float(p[0]), float(p[1]), 0.0, 0.0))
    return out


def uv_constant(angle: float, H: float) -> float:
    """Écart des guides (mm) d'une dépouille constante de `angle` degrés : H × tan(angle)."""
    return H * math.tan(math.radians(abs(angle)))


def taper_uv(pts: list, angle: float, H: float, closed: bool = True) -> list:
    """U/V à chaque point d'une dépouille constante (+ : fil penché à gauche du sens de parcours) : perpendiculaires
    au tracé (bissectrice aux sommets), de longueur H × tan(angle)."""
    m = uv_constant(angle, H) * (1 if angle >= 0 else -1)
    unit = miter_offset([_xy(p) for p in pts], 1.0, closed, limit=1e9, insert=False)
    out = []
    for p, q in zip(pts, unit):
        nx, ny = q[0] - p[0], q[1] - p[1]
        L = math.hypot(nx, ny)
        out.append((m * nx / L, m * ny / L) if L > 1e-12 else (0.0, 0.0))
    return out


def min_taper(k: float, T: float, mode: str = 'coincee', descente: float = 0.5) -> float:
    """Angle de dépouille minimal (°) pour une saignée `k` et une épaisseur `T`.

    Chute coincée (plus large en haut qu'en bas) : la saignée `k` se mesure d'équerre au fil ; en descendant de `h`,
    les flancs se rapprochent de h × sin(a) et se touchent quand h × sin(a) = k ; elle doit se coincer avant d'être
    descendue de `descente` × T : sin(a) = k ÷ (descente × T) (tan(a) en serait une approximation, un peu faible).
    Chute libre (plus large en bas) : le jeu double sur l'épaisseur, sin(a) = k ÷ T. Au-delà de 90° : 90."""
    if T <= 0:
        return 0.0
    r = max(0.05, descente) if mode == 'coincee' else 1.0
    return math.degrees(math.asin(min(1.0, k / (r * T))))


# --- chutes --------------------------------------------------------------------------------------------------

def find_pieces(stock, steps: list, kerf_w: float, held_point=None, min_area: float | None = None,
                history: list | None = None) -> tuple:
    """Les morceaux qui se détachent de la matière `stock` (shapely), coupe après coupe.

    `steps` : [{'lines': [tracés (x, y) du centre du fil], 'main': le trait coupé (le contour du dessin : le bord de
    la pièce, de quel côté que soit le fil), 'kerf': saignée de l'étape (d'office `kerf_w`), …}] dans l'ordre de
    coupe ; une saignée = le tracé élargi de la moitié de la saignée de chaque côté. Une étape dont le trait passe
    (pour plus de moitié) dans un morceau déjà détaché, ou sur son bord, est un problème : la recoupe d'un trou
    (le trait borde la matière tenue, la chute est de l'autre côté de la saignée) n'en est pas un, celle d'une pièce
    extérieure tombée en est un. Après chaque étape, la matière restante se range en morceaux ; le morceau tenu
    est celui qui contient `held_point` (le point bridé), sinon le plus grand de ceux qui touchent le bord de la
    matière (le brut est tenu par son bord, même s'il dépasse à peine de la pièce), sinon celui qui garde le plus du
    morceau tenu d'avant ; les autres morceaux sortis de lui se détachent à cette étape. Rend (morceaux, problèmes,
    morceau tenu) :
    morceaux = [{'step': rang de l'étape, 'poly': shapely}], problèmes = [(étape, étape qui a libéré le morceau)]
    pour une coupe faite dans un morceau déjà détaché. `history` (liste) : reçoit le morceau tenu avant chaque
    étape (la matière encore là quand elle commence), un `_Held` : `near(g)` sa matière autour de `g`, `geom()` en
    entier.

    En temps à peu près linéaire (une plaque de centaines de trous) : le morceau tenu n'est pas refait à chaque
    étape ; c'est une base moins ce qui en a été ôté (saignées, morceaux tombés : indexés, `_Index`). Une coupe se
    regarde dans une fenêtre autour d'elle : un morceau qui n'atteint pas le bord de la fenêtre est séparé de tout le
    reste ; s'il y a plus d'un morceau au bord de la fenêtre (une coupe qui traverse), si la fenêtre couvre la base
    ou si le morceau tenu devient un morceau de la fenêtre, l'étape se fait sur le morceau entier, qui devient la
    nouvelle base. La recoupe d'un morceau tombé se cherche aussi par un index.

    Matière en plusieurs morceaux séparés (bruts de plusieurs opérations, éloignés) : chacun est tenu à part
    (`_by_part`)."""
    import shapely
    from shapely.geometry import LineString, Point, box
    from shapely.ops import unary_union
    parts = [g for g in getattr(stock, 'geoms', [stock]) if not g.is_empty]
    if len(parts) > 1:
        return _by_part(parts, steps, kerf_w, held_point, min_area, history)
    r = max(kerf_w, 1e-3) / 2
    min_area = max(1e-3, kerf_w * kerf_w) if min_area is None else min_area
    edge = stock.boundary
    shapely.prepare(edge)
    fallen, near = _Index(), {}
    pieces, problems = [], []
    hp = Point(held_point[0], held_point[1]) if held_point else None

    def fall(k, c):
        fallen.add(c)
        pieces.append({'step': k, 'poly': c})

    def recut(line, tol):                                # le premier morceau tombé que `line` recoupe
        for i in fallen.query(line.buffer(tol, quad_segs=2)):
            g = near.get((i, tol))
            if g is None:
                g = near[(i, tol)] = fallen.polys[i].buffer(tol)
                shapely.prepare(g)
            if g.intersects(line) and line.intersection(g).length > 0.5 * line.length:
                return i
        return None

    def pick(cands):                                     # (clé, aire, au bord, point bridé dedans)
        got = next((c for c in cands if c[3]), None)
        if got is None:
            got = max([c for c in cands if c[2]] or cands, key=lambda c: c[1])
        return got[0]

    def based(g):                                        # nouvelle base : (base, ôtés, aire, bord touché, bridé)
        return (g, _Index(), g.area, _lines(edge.intersection(g.buffer(1e-6))),
                hp is not None and g.distance(hp) <= r)

    base, removed, area, contact, has_hp = based(stock)
    for k, st in enumerate(steps):
        if history is not None:
            history.append(_Held(base, removed, len(removed.polys)))
        rk = max(float(st.get('kerf') or kerf_w), 1e-3) / 2   # une étape peut avoir sa saignée (autre opération)
        lines = [[_xy(p) for p in ln] for ln in st.get('lines', ()) if len(ln) >= 2]
        geoms = [LineString(ln).buffer(rk, quad_segs=4) for ln in lines if length(ln) > 1e-9]
        if not geoms:
            continue
        cut = unary_union(geoms)
        main = st.get('main') or (lines[-1] if lines else None)
        if main is not None and length(main) > 1e-9:     # `main` : le trait du dessin (le bord de la pièce)
            hit = recut(LineString([_xy(q) for q in main]), min(rk / 2, 0.05))
            if hit is not None:
                problems.append((k, pieces[hit]['step']))
        if base is None:                                 # plus rien de tenu
            continue
        m = max(4 * rk, 1.0)
        x0, y0, x1, y1 = cut.bounds
        w = (x0 - m, y0 - m, x1 + m, y1 + m)
        bx = base.bounds
        whole = base.geom_type != 'Polygon' or (w[0] <= bx[0] and w[1] <= bx[1] and w[2] >= bx[2] and w[3] >= bx[3])
        if not whole:
            local = _Held(base, removed, len(removed.polys)).window(w)
            if local.is_empty or not local.intersects(cut):     # rien de la matière tenue n'est coupé
                continue
            rest = local.difference(cut)
            comps = [c for c in getattr(rest, 'geoms', [rest]) if not c.is_empty]
            frame = box(*w).exterior
            touching = [c for c in comps if shapely.dwithin(frame, c, 1e-7)]
            out = touching[0] if touching else None
            if len(touching) <= 1:
                wbox = box(*w)
                out_area = area - local.area + out.area if out is not None else 0.0
                cands = [(i, c.area, shapely.dwithin(edge, c, 1e-6), hp is not None and c.distance(hp) <= r)
                         for i, c in enumerate(comps) if c is not out and c.area >= min_area]
                if out is not None and out_area >= min_area:
                    cands.append((-1, out_area,
                                  not contact.difference(wbox).is_empty or shapely.dwithin(edge, out, 1e-6),
                                  has_hp and (not wbox.contains(hp) or out.distance(hp) <= r)))
                if not cands:
                    base = None
                    continue
                new = pick(cands)
                if new == -1:                            # le reste de la matière tenue : la base gardée
                    removed.add(cut)
                    for c in comps:
                        if c is not out:
                            removed.add(c)
                            if c.area >= min_area:
                                fall(k, c)
                    has_hp = cands[-1][3]
                    area = out_area
                    touched = _lines(edge.intersection(out.buffer(1e-6)))     # le bord touché, hors de la
                    contact = _lines(_lines(contact.difference(wbox)).union(touched))   # fenêtre et dedans
                    continue
            whole = True                                 # une coupe qui traverse, ou un morceau de la fenêtre tenu
        held = _Held(base, removed, len(removed.polys)).geom()
        if held.is_empty or not held.intersects(cut):
            continue
        rest = held.difference(cut)
        comps = [c for c in getattr(rest, 'geoms', [rest]) if not c.is_empty and c.area >= min_area]
        if not comps:
            base = None
            continue
        new = comps[pick([(i, c.area, shapely.dwithin(edge, c, 1e-6), hp is not None and c.distance(hp) <= r)
                          for i, c in enumerate(comps)])]
        for c in comps:
            if c is not new:
                fall(k, c)
        base, removed, area, contact, has_hp = based(new)
    held = _Held(base, removed, len(removed.polys)).geom()
    return pieces, problems, held


def _by_part(parts: list, steps: list, kerf_w: float, held_point, min_area, history) -> tuple:
    """`find_pieces` sur une matière en morceaux séparés : chaque morceau tenu à part (un brut n'en fait pas tomber un
    autre), avec les étapes dont les tracés le touchent ; les rangs rendus sont ceux de `steps`. Une étape qui ne
    touche aucun morceau ne coupe rien (son morceau tenu : vide)."""
    import shapely
    from shapely.geometry import LineString, Polygon
    from shapely.ops import unary_union
    pieces, problems, helds = [], [], []
    seen = [None] * len(steps)
    for part in parts:
        shapely.prepare(part)
        mine = [k for k, st in enumerate(steps)
                if any(len(ln) >= 2 and shapely.dwithin(part, LineString([_xy(q) for q in ln]),
                                                        max(float(st.get('kerf') or kerf_w), 1e-3) / 2)
                       for ln in st.get('lines', ()))]
        if not mine:
            helds.append(part)
            continue
        hist = []
        got, bad, held = find_pieces(part, [steps[k] for k in mine], kerf_w, held_point, min_area, hist)
        pieces += [dict(pc, step=mine[pc['step']]) for pc in got]
        problems += [(mine[a], mine[b]) for a, b in bad]
        for k, h in zip(mine, hist):
            seen[k] = h if seen[k] is None else seen[k]
        helds.append(held)
    if history is not None:
        history += [h if h is not None else _Held(None, _Index(), 0) for h in seen]
    pieces.sort(key=lambda pc: pc['step'])
    helds = [h for h in helds if not h.is_empty]
    return pieces, sorted(set(problems)), unary_union(helds) if helds else Polygon()


class _Index:
    """Des géométries indexées (`find_pieces`) : un arbre (STRtree) refait par paquets, plus les dernières venues
    regardées une à une."""

    BATCH = 64

    def __init__(self):
        self.polys, self.boxes, self.tree, self.indexed = [], [], None, 0

    def add(self, g) -> None:
        self.polys.append(g)
        self.boxes.append(g.bounds)
        if len(self.polys) - self.indexed >= self.BATCH:
            from shapely import STRtree
            self.tree, self.indexed = STRtree(self.polys), len(self.polys)

    def query(self, zone, n: int | None = None) -> list:
        """Les rangs (croissants) des `n` premières géométries dont la boîte touche celle de `zone`."""
        n = len(self.polys) if n is None else n
        out = [int(i) for i in self.tree.query(zone) if i < n] if self.tree is not None else []
        x0, y0, x1, y1 = zone.bounds
        out += [i for i in range(min(self.indexed, n), n)
                if self.boxes[i][0] <= x1 and self.boxes[i][2] >= x0 and self.boxes[i][1] <= y1 and
                self.boxes[i][3] >= y0]
        return sorted(out)


class _Held:
    """Le morceau tenu à une étape de `find_pieces` : `base` moins les `n` premières géométries de `removed`."""

    def __init__(self, base, removed: _Index, n: int):
        self.base, self.removed, self.n = base, removed, n

    @property
    def is_empty(self) -> bool:
        return self.base is None or self.base.is_empty

    def window(self, w: tuple):
        """Sa matière dans la boîte `w` (x0, y0, x1, y1)."""
        from shapely.geometry import Polygon, box
        from shapely.ops import unary_union
        if self.is_empty:
            return Polygon()
        b = box(*w)
        local = self.base.intersection(b)
        cut = [self.removed.polys[i].intersection(b) for i in self.removed.query(b, self.n)] \
            if not local.is_empty else []
        cut = [c for c in cut if not c.is_empty]
        return local.difference(unary_union(cut)) if cut else local

    def near(self, g, margin: float = 1.0):
        """Sa matière autour de la géométrie `g` (sa boîte agrandie de `margin`)."""
        x0, y0, x1, y1 = g.bounds
        return self.window((x0 - margin, y0 - margin, x1 + margin, y1 + margin))

    def geom(self):
        """Toute sa matière."""
        from shapely.geometry import Polygon
        from shapely.ops import unary_union
        if self.is_empty:
            return Polygon()
        if not self.n:
            return self.base
        return self.base.difference(unary_union(self.removed.polys[:self.n]))


def _lines(g):
    """Les traits d'une géométrie (sans ses points isolés), en un MultiLineString."""
    from shapely.geometry import MultiLineString
    out, todo = [], [g]
    while todo:
        p = todo.pop()
        if p is None or p.is_empty:
            continue
        if p.geom_type in ('LineString', 'LinearRing'):
            out.append(p)
        elif hasattr(p, 'geoms'):
            todo += list(p.geoms)
    return MultiLineString([list(p.coords) for p in out])


def piece_side(poly, path: list, kerf_w: float):
    """Le morceau `poly` est-il à gauche ('gauche') ou à droite ('droite') du tracé `path` (centre du fil) ? Essayé
    au milieu des plus longs segments, juste au-delà de la saignée ; None si l'on ne sait pas."""
    from shapely.geometry import Point
    segs = sorted(((math.dist(_xy(a), _xy(b)), _xy(a), _xy(b)) for a, b in zip(path, path[1:])), reverse=True)
    for L, a, b in segs[:8]:
        if L <= 1e-9:
            break
        mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        nx, ny = -(b[1] - a[1]) / L, (b[0] - a[0]) / L
        e = kerf_w / 2 + min(0.5, max(kerf_w / 4, 0.01))
        if poly.contains(Point(mx + nx * e, my + ny * e)):
            return 'gauche'
        if poly.contains(Point(mx - nx * e, my - ny * e)):
            return 'droite'
    return None


def assess(poly, T: float, kerf_w: float, p: dict, *, by_tab: bool = False, taper=None, side=None) -> dict:
    """Le risque d'un morceau détaché pour le fil : {'risque', 'raisons', 'masse' (g), 'largeur', 'longueur' (mm),
    'aire' (mm²)}. Règles (NOTES) : retenu par une attache → faible ; une dépouille constante `taper` (°, signée)
    assez forte pour le coincer ou le laisser tomber librement → faible ; lourd (≥ `lourde` g) → fort ; petit (plus
    grande cote ≤ max(2 mm, 4 saignées) et aire ≤ `SMALL_AREA`) → faible ; plus haut que large → fort ; sinon moyen
    (il tombe ou bascule quand la coupe se referme, le fil encore dans la saignée)."""
    rect = poly.minimum_rotated_rectangle
    cs = list(rect.exterior.coords) if hasattr(rect, 'exterior') else []
    sides = sorted(math.dist(cs[i], cs[i + 1]) for i in range(min(2, len(cs) - 1))) if len(cs) >= 3 else [0.0, 0.0]
    w, l = (sides + [0.0, 0.0])[:2] if len(sides) >= 2 else (0.0, 0.0)
    area = poly.area
    mass = p['densite'] * area * T / 1000.0
    out = {'aire': area, 'masse': mass, 'largeur': w, 'longueur': l, 'risque': 'moyen', 'raisons': []}
    if by_tab:
        out.update(risque='faible', raisons=['retenue par son attache jusqu\'à l\'arrêt programmé'])
        return out
    if taper and side in ('gauche', 'droite') and T > 0:
        away = (taper < 0) == (side == 'gauche')         # le haut du fil s'écarte du morceau : plus large en haut
        if away and abs(taper) >= min_taper(kerf_w, T, 'coincee', p['descente']) - 1e-9:
            out.update(risque='faible', raisons=[f'coincée par la dépouille de {abs(taper):g}°'])
            return out
        if not away and abs(taper) >= min_taper(kerf_w, T, 'libre') - 1e-9:
            out.update(risque='faible', raisons=[f'tombe librement grâce à la dépouille de {abs(taper):g}°'])
            return out
    if mass >= p['lourde']:
        out['raisons'].append(f'lourde ({mass:.0f} g) : elle s\'affaisse en fin de coupe et pince le fil')
    elif l <= max(2.0, 4 * kerf_w) and area <= SMALL_AREA:
        out.update(risque='faible', raisons=['petite : elle tombe sans gêner le fil'])
        return out
    if w < T:
        out['raisons'].append('plus haute que large : elle peut basculer dans la saignée et coincer le fil')
    if out['raisons']:
        out['risque'] = 'fort'
    else:
        out['raisons'].append('elle tombe ou bascule quand la coupe se referme, le fil encore dans la saignée')
    return out


def taper_proposal(side, T: float, H: float, kerf_w: float, p: dict) -> dict | None:
    """Incliner le fil pour un morceau à gauche ou à droite du sens de coupe : {'angle' (° signé, arrondi au
    centième au-dessus), 'minimal', 'cote', 'code', 'uv' (mm), 'retenue', 'possible'} ; None sans côté connu.
    Coincée : le haut du fil s'écarte du morceau ; libre : il penche vers lui."""
    if side not in ('gauche', 'droite') or T <= 0:
        return None
    mode = p['retenue']
    a = min_taper(kerf_w, T, mode, p['descente'])
    a_up = math.ceil(a * 100 - 1e-9) / 100
    toward_left = (side == 'gauche') != (mode == 'coincee')
    angle = a_up if toward_left else -a_up
    return {'angle': angle, 'minimal': a, 'cote': 'gauche' if angle > 0 else 'droite',
            'code': 'G51' if angle > 0 else 'G52', 'uv': uv_constant(angle, H), 'retenue': mode,
            'possible': a_up <= p['angle_max'] + 1e-9}


def tab_spot(ring: list, length_mm: float, entry=None, margin: float = 0.5) -> dict | None:
    """Où poser une attache sur le contour fermé `ring` (x, y) : le milieu d'un segment droit assez long (attache +
    2 × `margin`), le plus loin de l'entrée `entry` (d'office le début du contour) ; à défaut, le plus long segment.
    {'x', 'y', 'longueur', 'droit'} ; None pour un contour trop court."""
    P = [_xy(q) for q in ring]
    if len(P) < 3 or length(P) < length_mm + 2 * margin:
        return None
    e = _xy(entry) if entry is not None else P[0]
    segs = [(math.dist(a, b), ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)) for a, b in zip(P, P[1:])]
    ok = [s for s in segs if s[0] >= length_mm + 2 * margin]
    if ok:
        L, m = max(ok, key=lambda s: (round(math.dist(s[1], e), 6), s[0]))
    else:
        L, m = max(segs, key=lambda s: s[0])
    return {'x': m[0], 'y': m[1], 'longueur': length_mm, 'droit': bool(ok)}


def apply_taper(op, proposal: dict) -> None:
    """La proposition d'inclinaison retenue : dépouille constante de l'opération (le choix gardé sous son libellé,
    comme le formulaire)."""
    p = dict(op.params) if isinstance(op.params, dict) else {}
    p.update(inclinaison=CHOICE_LABELS['inclinaison']['constante'], angle=float(proposal['angle']))
    op.params = p


def apply_tab(op, proposal: dict) -> None:
    """La proposition d'attache retenue : ajoutée aux attaches de l'opération (une seule par contour : celle qui
    est déjà sur le même contour est remplacée au calcul suivant, la plus proche gardée)."""
    p = dict(op.params) if isinstance(op.params, dict) else {}
    tabs = [dict(a) for a in p.get('attaches') or [] if isinstance(a, dict)]
    tabs.append({'x': float(proposal['x']), 'y': float(proposal['y']),
                 'longueur': float(proposal.get('longueur') or DEFAULTS['attache'])})
    p['attaches'] = tabs
    op.params = p


#: mots du nom d'un objet qui disent le contour du dessous, ou du dessus (contours haut et bas)
LOWER_WORDS = frozenset({'dessous', 'bas', 'inferieur', 'inférieur', 'bottom', 'lower'})
UPPER_WORDS = frozenset({'dessus', 'haut', 'superieur', 'supérieur', 'top', 'upper'})


def lower_upper(items: list) -> list:
    """Les deux premiers objets d'une sélection rangés pour les contours haut et bas, le dessous d'abord : selon
    leur nom quand il le dit (« dessous », « bas », « haut »…), sinon dans l'ordre de la sélection (le premier
    sélectionné est le dessous ; une sélection au cadre suit l'ordre du dessin)."""
    import re

    def word(it) -> int:
        toks = set(re.split(r'[^\w]+', (getattr(it, 'name', '') or '').lower()))
        lo, up = bool(toks & LOWER_WORDS), bool(toks & UPPER_WORDS)
        return 1 if up and not lo else -1 if lo and not up else 0
    a, b = list(items)[:2]
    return [b, a] if word(a) > word(b) else [a, b]


# --- calcul de l'opération -------------------------------------------------------------------------------------

def is_wire(tp) -> bool:
    """Parcours d'électroérosion à fil (son cycle `fil_edm`) ?"""
    return any(isinstance(c, dict) and c.get('kind') == KIND for c in (getattr(tp, 'cycles', None) or ()))


def split_wire(toolpaths) -> tuple:
    """(parcours ordinaires, parcours d'électroérosion à fil)."""
    keep, wire = [], []
    for tp in toolpaths:
        (wire if is_wire(tp) else keep).append(tp)
    return keep, wire


def _flip(side: str) -> str:
    return {'gauche': 'droite', 'droite': 'gauche'}.get(side, '')


def thickness_of(doc, setup, p: dict) -> tuple:
    """(épaisseur, note) : la réglée, sinon celle du brut du dessin, sinon de la plaque, sinon DEFAULT_THICKNESS."""
    if p['epaisseur'] > 0:
        return p['epaisseur'], ''
    try:
        from ..core import stock2d
        st = stock2d.of_setup(setup)
        box = stock2d.box_for(doc, setup)
        if box is not None and st.active() and box.top - box.bottom > 0:
            return float(box.top - box.bottom), ''
    except Exception:                                    # brut illisible : la plaque
        pass
    t = float(getattr(getattr(doc, 'plate', None), 'thickness', 0.0) or 0.0)
    if t > 0:
        return t, ''
    return DEFAULT_THICKNESS, f'épaisseur non donnée (ni brut ni plaque épaisse) : prise à {DEFAULT_THICKNESS:g} mm'


def _stock(doc, setup, closed_rings: list, all_lines: list) -> tuple:
    """(matière shapely, note) : le brut du dessin, sinon la plaque si elle contient les contours fermés (sans
    contour fermé : si un trait la traverse ; une coupe de bord à bord en sort), sinon la boîte des contours agrandie
    de 5 mm."""
    from shapely.geometry import LineString, box
    try:
        from ..core import stock2d
        b = stock2d.box_for(doc, setup)
        if b is not None:
            return b.footprint(), ''
    except Exception:                                    # brut illisible : la plaque
        pass
    pts = [_xy(q) for r in (closed_rings or all_lines) for q in r]
    pl = getattr(doc, 'plate', None)
    if pl is not None and pl.width > 0 and pl.height > 0:
        g = box(pl.x, pl.y, pl.x + pl.width, pl.y + pl.height)
        if not pts or (g.buffer(0.5).contains(box(*_bounds(pts))) if closed_rings else
                       any(len(ln) >= 2 and g.intersects(LineString([_xy(q) for q in ln])) for ln in all_lines)):
            return g, ''
    if not pts:
        return None, ''
    x0, y0, x1, y1 = _bounds(pts)
    return box(x0 - 5, y0 - 5, x1 + 5, y1 + 5), 'brut supposé : la boîte des contours agrandie de 5 mm'


def _bounds(pts: list) -> tuple:
    xs, ys = [q[0] for q in pts], [q[1] for q in pts]
    return min(xs), min(ys), max(xs), max(ys)


def _contours(doc, setup, op, p: dict, tol: float) -> tuple:
    """([(points, fermé, nom)], note) : les contours à couper. Haut/bas : la paire (points haut/bas)."""
    from .strategies import item_geometry, polylines, source_items
    if p['inclinaison'] == 'haut_bas':
        b = doc.find(p['bas']) if p['bas'] else None
        h = doc.find(p['haut']) if p['haut'] else None
        gb = item_geometry(b) if b is not None else None
        gh = item_geometry(h) if h is not None else None
        if gb is None or gh is None:
            return [], 'contours haut et bas : choisir le contour du dessous et celui du dessus'
        cb, ch = polylines([gb], tol), polylines([gh], tol)
        if not cb or not ch:
            return [], 'contours haut et bas : choisir le contour du dessous et celui du dessus'
        (pb, fb), (ph, fh) = cb[0], ch[0]
        if fb != fh:
            return [], 'contours haut et bas : l\'un est fermé, l\'autre ouvert'
        note = 'contours haut et bas : seul le premier contour de chaque objet est pris' \
            if len(cb) > 1 or len(ch) > 1 else ''
        return [(pair_contours(pb, ph, fb), fb, getattr(b, 'name', '') or 'haut/bas')], note
    try:
        from ..core import stock2d
        skip = stock2d.of_setup(setup).item if stock2d.of_setup(setup).kind == 'contour' else ''
    except Exception:                                    # brut illisible : rien d'ôté
        skip = ''
    out = []
    for it in source_items(doc, op):
        if skip and it.id == skip:                       # le contour du brut n'est pas une coupe
            continue
        g = item_geometry(it)
        if g is None:
            continue
        for pts, closed in polylines([g], tol):
            out.append(([_xy(q) for q in pts], closed, getattr(it, 'name', '') or ''))
    return out, ''


def _order(cuts: list, here, drawing: bool) -> list:
    """Ordre de coupe : les contours intérieurs (les plus enfoncés) d'abord, puis au plus proche ; `drawing` :
    l'ordre du dessin."""
    if drawing:
        return list(cuts)
    out, pos = [], (float(here[0]), float(here[1])) if here is not None else (0.0, 0.0)

    def far(b):                                          # au moins cette distance : la boîte du contour
        return math.hypot(max(b[0] - pos[0], 0.0, pos[0] - b[2]), max(b[1] - pos[1], 0.0, pos[1] - b[3]))
    for depth in sorted({c['depth'] for c in cuts}, reverse=True):
        group = [(c, _bounds(c['geo'])) for c in cuts if c['depth'] == depth]
        while group:                                     # le plus proche : les boîtes d'abord (une plaque de
            best = None                                  # centaines de trous), le contour seulement s'il peut l'être
            for lb, i in sorted((far(b), i) for i, (_c, b) in enumerate(group)):
                if best is not None and lb > best[0]:
                    break
                d = project(group[i][0]['geo'], pos)[1]
                if best is None or (d, i) < best:
                    best = (d, i)
            c = group.pop(best[1])[0]
            out.append(c)
            pos = _xy(c['geo'][-1])
    return out


def _hole(geo: list, wire_side: str, appr: float, poly) -> tuple:
    """Le trou de départ : à `appr` du début du contour, du côté du fil (la chute) ; rapproché tant qu'il tombe du
    mauvais côté du contour (petit trou)."""
    from shapely.geometry import Point
    a, b = _xy(geo[0]), _xy(geo[1])
    z = _xy(geo[-2]) if len(geo) >= 3 else a
    n = miter_offset([z, a, b], 1.0, closed=False, limit=1e9, insert=False)[1]
    nx, ny = n[0] - a[0], n[1] - a[1]
    L = math.hypot(nx, ny) or 1.0
    sgn = -1.0 if wire_side == 'droite' else 1.0
    nx, ny = sgn * nx / L, sgn * ny / L
    inside = (signed_area(geo) > 0) == (sgn > 0)        # le côté du fil est l'intérieur du contour
    d = max(appr, 0.05)
    for _k in range(8):
        h = (a[0] + nx * d, a[1] + ny * d)
        if poly is None or poly.contains(Point(h)) == inside:
            return h
        d /= 2
    return a[0] + nx * d, a[1] + ny * d


def _pts4(path: list) -> list:
    return [tuple(q) for q in path]


def _reverse(path: list) -> list:
    return list(reversed(path))


def compute(doc, setup, op, tp, here=(0.0, 0.0)):
    """Le parcours d'une opération d'électroérosion à fil (`tp` : le parcours vide, rempli et rendu)."""
    from shapely.geometry import LineString, Point, Polygon
    from .model import Move
    p = params_of(op)
    tol = float(getattr(setup, 'tolerance', 0.01) or 0.01)
    notes = []
    T, note = thickness_of(doc, setup, p)
    notes.append(note)
    mode = p['inclinaison']
    hb = mode == 'haut_bas'
    H = p['guides']
    if H <= 0:
        H = T + GUIDE_GAP
        notes.append(f'{BLOCKING} : contours haut et bas : donner la distance entre les guides (les U/V en '
                     'dépendent)' if hb else
                     f'distance entre guides non donnée : prise à l\'épaisseur + {GUIDE_GAP:g} mm ({H:g} mm)')
    elif H < T:
        notes.append((f'{BLOCKING} : ' if hb else '') +
                     f'distance entre guides ({H:g} mm) plus petite que l\'épaisseur ({T:g} mm)')
    zp = min(max(p['plan_prog'], 0.0), T)
    k = kerf(p)
    ds = offsets(p)
    calc = p['compensation'] == 'calcul' or hb
    if hb and p['compensation'] == 'g41':
        notes.append('contours haut et bas : parcours décalé ici (G40), la compensation G41/G42 n\'est pas employée')
    angle = p['angle'] if mode == 'constante' else 0.0
    if mode == 'constante' and abs(angle) < 1e-9:
        notes.append('dépouille constante de 0° : fil droit')
    if abs(angle) > p['angle_max'] + 1e-9:
        notes.append(f'{BLOCKING} : dépouille de {abs(angle):g}° : plus que l\'inclinaison la plus forte de la '
                     f'machine ({p["angle_max"]:g}°)')
    raw, note = _contours(doc, setup, op, p, tol)
    notes.append(note)
    if not raw:
        tp.warnings += [n for n in notes if n] + ([] if note else ['aucun contour à couper'])
        return tp
    # sens et côté de chaque contour (pair-impair : un contour dans un autre change de côté)
    cuts = []
    for pts, closed, name in raw:
        pts = _clean(pts)
        if closed and not _same(pts[0], pts[-1]):
            pts.append(pts[0])
        if len(pts) < (4 if closed else 2):
            continue
        if closed and p['sens'] != 'dessin' and (signed_area(pts) > 0) != (p['sens'] == 'trigo'):
            pts = pts[::-1]
        cuts.append({'geo': pts, 'closed': closed, 'name': name})
    if not cuts:
        tp.warnings += [n for n in notes if n] + ['aucun contour à couper']
        return tp
    polys = [Polygon([_xy(q) for q in c['geo']]).buffer(0) if c['closed'] else None for c in cuts]
    from shapely import STRtree
    have = [j for j, g in enumerate(polys) if g is not None and not g.is_empty]
    tree = STRtree([polys[j] for j in have]) if have else None
    for i, c in enumerate(cuts):
        if polys[i] is not None and not polys[i].is_empty:
            on = Point(_xy(c['geo'][0]))                 # un point du contour même : dedans ceux qui l'entourent
        else:                                            # contour ouvert : son milieu
            on = Point(_xy(point_at(c['geo'], length(c['geo']) / 2)[0]))
        near = [have[int(j)] for j in tree.query(on)] if tree is not None else []
        c['depth'] = sum(1 for j in near if j != i and polys[j].contains(on))
        c['poly'] = polys[i]
    base = op.side if op.side in ('exterieur', 'interieur', 'sur') else 'exterieur'
    for c in cuts:
        side = base if c['closed'] else 'sur'
        if side != 'sur' and c['depth'] % 2:
            side = 'interieur' if side == 'exterieur' else 'exterieur'
        c['side'] = side
        ccw = c['closed'] and signed_area(c['geo']) > 0
        c['wire'] = '' if side == 'sur' else ('gauche' if (side == 'interieur') == ccw else 'droite')
    if any(not c['closed'] for c in cuts) and base != 'sur':
        notes.append('contours ouverts : coupés sur le trait (sans décalage), en une passe')
    cuts = _order(cuts, here, getattr(op, 'order_mode', 'auto') == 'dessin')
    # départ, attache et trou de chaque contour fermé
    from .strategies import start_marks
    try:
        marks = [(float(m[0]), float(m[1])) for m in start_marks(doc, op, tol)] if mode != 'haut_bas' else []
    except Exception:                                    # dessin sans repères : départ au plus près
        marks = []
    tabs_left = list(p['attaches'])
    r_eff = p['fil'] / 2 + p['gap']
    pos = (float(here[0]), float(here[1])) if here is not None else (0.0, 0.0)
    for n, c in enumerate(cuts, 1):
        c['n'] = n
        c['tab'] = None
        geo = c['geo']
        if not c['closed']:
            c['hole'] = _xy(geo[0])
            continue
        reach = max(2.0, 3 * ds[0] + 1.0)
        m = min(marks, key=lambda q: project(geo, q)[1], default=None)
        m = m if m is not None and project(geo, m)[1] <= reach else None
        near = sorted(((project(geo, (a['x'], a['y']))[1], i) for i, a in enumerate(tabs_left)))
        near = [i for d, i in near if d <= reach]
        S = length(geo)
        if near:
            a = tabs_left[near[0]]
            if len(near) > 1:
                notes.append(f'contour {n} : une seule attache par contour, {len(near) - 1} autre(s) ignorée(s)')
            for i in sorted(near, reverse=True):
                tabs_left.pop(i)
            skip = a['longueur'] + 2 * r_eff
            if skip >= 0.5 * S:
                notes.append(f'contour {n} : attache trop longue pour le contour, ignorée')
            else:
                sc = project(geo, (a['x'], a['y']))[0]
                c['tab'] = {'x': a['x'], 'y': a['y'], 'longueur': a['longueur'], 'skip': skip}
                geo = rotate_ring(geo, sc + skip / 2)    # le contour finit au bout de l'attache
                if m is not None:                        # le départ du Mode Point ne tient plus : le dire
                    notes.append(f'contour {n}{_name(c)} : départ imposé (X {m[0]:.2f} Y {m[1]:.2f}) déplacé au '
                                 f'bout de l\'attache, en X {geo[0][0]:.2f} Y {geo[0][1]:.2f}')
        if c['tab'] is None:
            if m is not None:
                geo = rotate_ring(geo, project(geo, m)[0])
            elif getattr(op, 'start_policy', 'proche') != 'dessin':
                geo = rotate_ring(geo, project(geo, pos)[0])
        c['geo'] = geo
        c['hole'] = _hole(geo, c['wire'], p['approche'], c['poly'] if c['poly'] is not None else None)
        pos = c['hole']
    if tabs_left:
        notes.append(f'{len(tabs_left)} attache(s) loin de tout contour fermé : ignorée(s)')
    # tracés de chaque passe et blocs de chaque contour ; chaque contour (et chaque attache) finit fil coupé, puis
    # « remise » : compensation et dépouille annulées, guide haut ramené droit (U0 V0)
    moves = []
    taper_side = 'gauche' if angle > 0 else 'droite' if angle < 0 else ''
    amax, amax_at = 0.0, None
    for c in cuts:
        geo, closed, wire = c['geo'], c['closed'], c['wire']
        sgn = -1.0 if wire == 'droite' else 1.0
        npass = len(ds) if closed else 1
        paths = [offset_path(geo, sgn * ds[i], closed) if wire else _pts4(geo) for i in range(npass)]
        progs = [prog_points(pa if calc or not wire else geo, T, H, zp) for pa in paths]
        for q in (q for pr in progs for q in pr):        # inclinaison du fil : tan = écart des guides ÷ distance
            a_q = math.degrees(math.atan(math.hypot(q[2], q[3]) / H)) if H > 0 else 0.0
            if a_q > amax:
                amax, amax_at = a_q, (q[0], q[1])
        c['paths'] = paths
        if not closed:
            _open_blocks(c, progs[0], paths[0], taper_side, abs(angle), p['approche'])
            continue
        hole = c['hole']
        start = (hole[0], hole[1], 0.0, 0.0)
        comp = '' if calc or not wire else wire
        tab = c['tab']
        skip = tab['skip'] if tab else 0.0
        mains = []
        for pr in progs:
            S = length(pr)
            mains.append(sub_path(pr, 0.0, S - skip) if tab else pr)
        blocks = [{'op': 'rapide', 'pt': list(start)}, {'op': 'enfiler'}]
        prev = None
        for i, mp in enumerate(mains):
            fwd = (i % 2 == 0) if tab else True
            seq = mp if fwd else _reverse(mp)
            blocks += [{'op': 'comp', 'cote': comp if fwd else _flip(comp), 'd': i + 1 if comp else 0,
                        'valeur': ds[i] if comp else 0.0},
                       {'op': 'cone', 'cote': taper_side if fwd else _flip(taper_side), 'angle': abs(angle)}]
            if prev is None:
                blocks.append({'op': 'coupe', 'role': 'approche', 'pts': [list(seq[0])]})
            elif not _same(prev, seq[0], 1e-6):
                blocks.append({'op': 'coupe', 'role': 'passe', 'pts': [list(seq[0])]})
            blocks.append({'op': 'coupe', 'role': 'contour' if i == 0 else 'passe',
                           'pts': [list(q) for q in seq[1:]]})
            prev = seq[-1]
        if not tab or len(mains) % 2 == 0:               # revenu au départ : sortie par l'approche
            blocks += [{'op': 'comp', 'cote': '', 'd': 0, 'valeur': 0.0}, {'op': 'cone', 'cote': '', 'angle': 0.0},
                       {'op': 'coupe', 'role': 'sortie', 'pts': [list(start)]}, {'op': 'couper_fil'},
                       {'op': 'remise'}]
        else:                                            # arrêté devant l'attache : fil coupé sur place
            blocks += [{'op': 'couper_fil'}, {'op': 'remise'}]
        c['blocks'] = blocks
        p1 = [_xy(q) for q in paths[0]]
        S1 = length(p1)
        main1 = sub_path(p1, 0.0, S1 - skip) if tab else p1
        g1 = [_xy(q) for q in geo]                       # le trait du dessin : le bord de la pièce
        edge1 = sub_path(g1, 0.0, max(length(g1) - skip, length(g1) / 2)) if tab else g1
        c['step'] = {'lines': [[_xy(hole), p1[0]], main1], 'main': edge1, 'cut': c}
        if tab:
            last = progs[-1]
            Sl = length(last)
            piece = _reverse(sub_path(last, Sl - skip, Sl))
            nl = len(ds)
            c['tab_blocks'] = [
                {'op': 'rapide', 'pt': list(start)}, {'op': 'enfiler'},
                {'op': 'arret', 'texte': f'attache du contour {c["n"]} : retenir la chute avant de la couper'},
                {'op': 'comp', 'cote': _flip(comp), 'd': nl if comp else 0, 'valeur': ds[-1] if comp else 0.0},
                {'op': 'cone', 'cote': _flip(taper_side), 'angle': abs(angle)},
                {'op': 'coupe', 'role': 'approche', 'pts': [list(piece[0])]},
                {'op': 'coupe', 'role': 'attache', 'pts': [list(q) for q in piece[1:]]},
                {'op': 'couper_fil'}, {'op': 'remise'}]
            # le trait de l'attache : le bord de la pièce sous elle (pas le tracé du fil, à demi dans les saignées
            # déjà coupées quand l'attache est plus courte qu'une saignée)
            Sg = length(g1)
            c['tab_step'] = {'lines': [sub_path(p1, S1 - skip, S1)], 'main': sub_path(g1, Sg - skip, Sg), 'cut': c,
                             'tab': True}
    if hb and amax > p['angle_max'] + 1e-9:
        notes.append(f'{BLOCKING} : contours haut et bas : le fil penche jusqu\'à {amax:.2f}° (vers X '
                     f'{amax_at[0]:.2f} Y {amax_at[1]:.2f}), plus que l\'inclinaison la plus forte de la machine '
                     f'({p["angle_max"]:g}°)')
    # ordre du programme : les attaches à la fin (ou dans un programme à part), sauf celle d'un contour qu'entoure un
    # contour coupé ensuite sans attache : coupée juste avant lui, sinon la pièce tomberait avec la chute retenue
    seq, pending = [], []
    for c in cuts:
        if c['closed'] and not c['tab'] and c['poly'] is not None and not c['poly'].is_empty:
            for t in [t for t in pending if c['poly'].contains(Point(_xy(t['geo'][0])))]:
                pending.remove(t)
                t['avant'] = c['n']
                for b in t['tab_blocks']:
                    if b['op'] == 'arret':
                        b['texte'] += f' (avant le contour {c["n"]})'
                seq.append(('attache', t))
        seq.append(('contour', c))
        if c['tab']:
            pending.append(c)
    blocks, tab_blocks, steps = [], [], []
    for what, c in seq:
        blocks += c['blocks'] if what == 'contour' else c['tab_blocks']
        steps.append(c['step'] if what == 'contour' else c['tab_step'])
    for t in pending:
        tab_blocks += t['tab_blocks']
        steps.append(t['tab_step'])
    early = [c['n'] for c in cuts if c.get('avant')]
    if early and p['attache_coupe'] == 'apart':
        notes.append('attache(s) du (des) contour(s) ' + ', '.join(map(str, early)) + ' coupée(s) dans le programme '
                     'principal, avant le contour qui les entoure')
    # chutes : la matière moins les saignées, dans l'ordre du programme
    stock, note = _stock(doc, setup, [c['geo'] for c in cuts if c['closed']], [c['geo'] for c in cuts])
    notes.append(note)
    chutes = []
    k1 = 2 * ds[0]
    if stock is not None and not stock.is_empty:
        held_at = []
        pieces, problems, _held = find_pieces(stock, steps, k1, p['bride'] or None, history=held_at)
        for st, held in zip(steps, held_at):            # contour ouvert incliné : enfilé en amont, dans le vide ?
            c = st['cut']
            appr = None if st.get('tab') else c.get('approach')
            if appr and not held.is_empty and \
                    LineString(appr).intersection(held.near(LineString(appr))).length > 1e-3:
                notes.append(f'{BLOCKING} : contour {c["n"]}{_name(c)} (ouvert, fil incliné) : l\'approche depuis le '
                             f'trou d\'enfilage (X {appr[0][0]:.2f} Y {appr[0][1]:.2f}) traverse de la matière non '
                             'coupée — faire commencer le trait hors de la matière (le prolonger jusqu\'au bord) ou le '
                             'couper fil droit')
            elif not st.get('tab') and not c['closed'] and not held.is_empty and \
                    held.near(Point(c['hole'])).buffer(-1e-3).contains(Point(c['hole'])):   # fil droit : enfilé dedans
                notes.append(f'contour {c["n"]}{_name(c)} (ouvert) : enfilage en X {c["hole"][0]:.2f} Y '
                             f'{c["hole"][1]:.2f}, dans la matière — y percer un trou de départ, ou faire commencer '
                             'le trait hors de la matière')
        for st_k, freed in problems:
            who, at = _step_name(steps[st_k]), _step_name(steps[freed])
            notes.append(f'{BLOCKING} : {who[0]} : coupe faite dans un morceau déjà détaché (tombé à la fin {at[1]}) : '
                         'le fil couperait une matière qui n\'est plus tenue — couper d\'abord ce qui est à '
                         'l\'intérieur (ordre « auto ») ou poser une attache sur le contour '
                         f'{steps[freed]["cut"]["n"]}')
        for m, pc in enumerate(pieces, 1):
            chutes.append(_chute(m, pc, steps[pc['step']], T, H, k1, p, angle, mode))
    for ch in chutes:
        if ch['risque'] in ('moyen', 'fort'):
            notes.append(_chute_text(ch))
            tp.zones.append({'kind': 'chute', 'risque': ch['risque'], 'pts': ch['pts']})
    # mouvements montrés : au plan de programmation, Z 0
    for b in blocks + tab_blocks:
        if b['op'] == 'rapide':
            moves.append(Move('rapid', b['pt'][0], b['pt'][1], 0.0))
        elif b['op'] == 'coupe':
            moves += [Move('feed', q[0], q[1], 0.0) for q in b['pts']]
    tp.moves = moves
    tp.warnings += [n for n in notes if n]
    tp.cycles = [{
        'kind': KIND,
        'anchor': [moves[0].x, moves[0].y] if moves else [0.0, 0.0],
        'anchor2': [moves[-1].x, moves[-1].y] if moves else [0.0, 0.0],
        'blocs': blocks, 'attaches': tab_blocks,
        'reglages': {'fil': p['fil'], 'gap': p['gap'], 'saignee': k, 'epaisseur': T, 'plan': zp, 'guides': H,
                     'decalages': ds if not calc else [], 'compensation': 'calcul' if calc else 'g41',
                     'inclinaison': mode, 'angle': angle, 'uv': uv_constant(angle, H),
                     'angle_max': p['angle_max'], 'angle_haut_bas': amax if hb else 0.0,
                     'attache_coupe': p['attache_coupe'], 'passes': len(ds)},
        'contours': [{'n': c['n'], 'nom': c['name'], 'trou': list(c['hole']), 'ferme': c['closed'],
                      'cote': c['side'], 'fil': c['wire'], 'attache': bool(c['tab']),
                      'attache_avant': c.get('avant') or 0,
                      'attache_xy': [c['tab']['x'], c['tab']['y']] if c['tab'] else [],
                      'pts': [list(_xy(q)) for q in c['geo']]} for c in cuts],
        'chutes': chutes,
        # pour le contrôle de tout le programme (`cam.post.robocut`, plusieurs opérations à la suite) : les étapes
        # de coupe dans l'ordre (contours et attaches avancées ; les attaches de la fin à part), la matière, le
        # point bridé
        'etapes': [_step_data(st, k1) for st in steps[:len(seq)]],
        'etapes_attaches': [_step_data(st, k1) for st in steps[len(seq):]],
        'brut': _poly_data(stock) if stock is not None else [],
        'bride': list(p['bride']),
    }]
    return tp


def _step_data(st: dict, k1: float) -> dict:
    """Une étape de coupe gardée dans le cycle (listes : enregistrable avec le dessin ; au 1/10 000 de mm, comme les
    chutes : le cycle est gardé avec les parcours)."""
    return {'lignes': [_rounded(ln) for ln in st['lines']],
            'principal': _rounded(st['main']) if st.get('main') else [],
            'contour': st['cut']['n'], 'attache': bool(st.get('tab')), 'saignee': k1}


def _rounded(pts) -> list:
    return [[round(q[0], 4), round(q[1], 4)] for q in pts]


def _poly_data(g) -> list:
    """La matière (shapely) en listes : [[extérieur, [trous]]] par polygone."""
    return [[_rounded(pg.exterior.coords), [_rounded(r.coords) for r in pg.interiors]]
            for pg in getattr(g, 'geoms', [g]) if hasattr(pg, 'exterior') and not pg.is_empty]


def poly_of(data: list):
    """La matière relue (`_poly_data`), ou None."""
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    polys = [Polygon(ext, holes) for ext, holes in data or [] if len(ext) >= 4]
    return unary_union(polys) if polys else None


def _open_blocks(c: dict, pr: list, path: list, taper_side: str, angle: float, appr: float) -> None:
    """Les blocs d'un contour ouvert (`c['blocks']`, `c['step']`, `c['hole']`). Fil incliné (dépouille, ou U/V au
    premier point) : enfilé droit à `appr` en amont du premier point, sur le prolongement du premier segment, il
    s'incline sur l'approche ; sinon enfilé au premier point."""
    first = pr[0]
    P = [_xy(q) for q in path]
    tilted = angle > 1e-9 or any(abs(q[2]) > 1e-9 or abs(q[3]) > 1e-9 for q in pr)
    blocks = []
    if tilted:
        x0, y0 = first[0], first[1]
        x1, y1 = next(((q[0], q[1]) for q in pr[1:] if math.dist(q[:2], first[:2]) > 1e-9), (x0 + 1.0, y0))
        L = math.dist((x0, y0), (x1, y1))
        d = max(appr, 0.05)
        hole = (x0 - (x1 - x0) / L * d, y0 - (y1 - y0) / L * d)
        blocks += [{'op': 'rapide', 'pt': [hole[0], hole[1], 0.0, 0.0]}, {'op': 'enfiler'},
                   {'op': 'comp', 'cote': '', 'd': 0, 'valeur': 0.0},
                   {'op': 'cone', 'cote': taper_side, 'angle': angle},
                   {'op': 'coupe', 'role': 'approche', 'pts': [list(first)]}]
        lines = [[hole, P[0]], P]
        c['approach'] = [hole, P[0]]                     # contrôlée contre la matière (`compute`)
    else:
        hole = (first[0], first[1])
        blocks += [{'op': 'rapide', 'pt': [first[0], first[1], 0.0, 0.0]}, {'op': 'enfiler'},
                   {'op': 'comp', 'cote': '', 'd': 0, 'valeur': 0.0}, {'op': 'cone', 'cote': '', 'angle': 0.0}]
        lines = [P]
    blocks += [{'op': 'coupe', 'role': 'contour', 'pts': [list(q) for q in pr[1:]]}, {'op': 'couper_fil'},
               {'op': 'remise'}]
    c['hole'] = hole
    c['blocks'] = blocks
    c['step'] = {'lines': lines, 'main': P, 'cut': c}


def _step_name(st: dict) -> tuple:
    """(sujet, complément « à la fin de … ») d'une étape de coupe : un contour ou son attache."""
    c = st['cut']
    if st.get('tab'):
        return f'attache du contour {c["n"]}{_name(c)}', f'de l\'attache du contour {c["n"]}{_name(c)}'
    return f'contour {c["n"]}{_name(c)}', f'du contour {c["n"]}{_name(c)}'


def _name(c) -> str:
    return f' « {c["name"]} »' if c.get('name') else ''


def _chute(m: int, pc: dict, st: dict, T: float, H: float, k1: float, p: dict, angle: float, mode: str) -> dict:
    """Le résumé d'un morceau détaché : où, quand, sa taille, son risque, les propositions."""
    c = st['cut']
    poly = pc['poly']
    by_tab = bool(st.get('tab'))
    ref = [_xy(q) for q in c['paths'][0]]
    side = piece_side(poly, ref, k1)
    a = assess(poly, T, k1, p, by_tab=by_tab, taper=angle if mode == 'constante' else None, side=side)
    end = st['lines'][-1][-1]
    genre = 'pièce' if c['closed'] and c['side'] == 'exterieur' and c['poly'] is not None \
        and c['poly'].buffer(k1).contains(poly) else 'chute'
    out = {'n': m, 'genre': genre, 'contour': c['n'], 'nom': c['name'], 'x': end[0], 'y': end[1],
           'attache': by_tab, 'cote': side, 'pts': [[round(x, 4), round(y, 4)] for x, y in poly.exterior.coords],
           **a, 'inclinaison': None, 'attache_proposee': None}
    if a['risque'] in ('moyen', 'fort'):
        if mode != 'haut_bas':
            out['inclinaison'] = taper_proposal(side, T, H, k1, p)
        if c['closed']:
            spot = tab_spot([_xy(q) for q in c['geo']], p['attache'], entry=c['geo'][0])
            out['attache_proposee'] = spot
    return out


def _chute_text(ch: dict) -> str:
    """Le signalement d'un morceau détaché à risque (avertissements de la FAO)."""
    what = 'pièce' if ch['genre'] == 'pièce' else 'chute'
    head = (f'{what} {ch["n"]} ({ch["longueur"]:.1f} × {ch["largeur"]:.1f} mm, {ch["masse"]:.0f} g) libérée à la fin '
            f'du contour {ch["contour"]}' + (f' « {ch["nom"]} »' if ch['nom'] else '') +
            f' (X {ch["x"]:.2f} Y {ch["y"]:.2f}) : risque {ch["risque"]} pour le fil — ' + ' ; '.join(ch['raisons']))
    props = []
    t = ch.get('inclinaison')
    if t:
        goal = 'qu\'elle reste coincée' if t['retenue'] == 'coincee' else 'qu\'elle tombe librement'
        props.append(f'incliner le fil de {abs(t["angle"]):.2f}° à {t["cote"]} ({t["code"]}, U/V {t["uv"]:.3f} mm) '
                     f'pour {goal}' + ('' if t['possible'] else ' (plus que l\'inclinaison la plus forte réglée)'))
    s = ch.get('attache_proposee')
    if s:
        props.append(f'une attache de {s["longueur"]:g} mm en X {s["x"]:.2f} Y {s["y"]:.2f}' +
                     ('' if s['droit'] else ' (pas de segment droit assez long)'))
    return head + ('. Proposé : ' + ', ou '.join(props) if props else '')
