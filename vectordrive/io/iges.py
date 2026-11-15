"""IGES (*.igs) : lecture d'une pièce ou d'un dessin, en vue de dessus.

Les courbes indépendantes (ligne, arc, conique, polyligne, spline, NURBS,
composite, sous-figures) donnent un calque par niveau IGES, chacune à l'outil de sa
couleur (numéro de couleur ou définition 314 : une couleur = un outil). Les surfaces NURBS,
planes, réglées, de révolution et cylindres tabulés, entières, détourées (144, 143)
ou faces de solide (510), sont maillées puis passent par `mesh3d.top_view`, comme
un STL : un calque par hauteur de face horizontale, et la silhouette. Les autres
surfaces (spline paramétrique, décalée, analytiques de la 5.3) sont signalées dans
le compte rendu.

Écrit d'après la spécification IGES 5.3 : sections S, G, D, P, T en lignes de 80 colonnes.
"""
from __future__ import annotations

import collections
import math
import pathlib

import numpy as np

from ..core import progress
from ..core.chain import chain_tagged
from ..core.document import Document, Layer, Shape
from ..core.geom import Conic, Contour, Cubic, Line, Path, dist
from .colors import ToolColors, black_first, hex_of

CURVES = (100, 102, 104, 106, 110, 112, 126)
SURFACES = (128, 108, 118, 120, 122)                     # plan, réglée, révolution, cylindre tabulé : voir _Surface
#: millimètres par unité du fichier, selon le drapeau d'unité de la section G
UNITS = {1: 25.4, 2: 1.0, 4: 304.8, 5: 1609344.0, 6: 1000.0, 7: 1e6, 8: 0.0254, 9: 0.001, 10: 10.0, 11: 2.54e-5}
UNIT_NAMES = {'IN': 25.4, 'INCH': 25.4, 'MM': 1.0, 'FT': 304.8, 'MI': 1609344.0, 'M': 1000.0, 'KM': 1e6,
              'MIL': 0.0254, 'UM': 0.001, 'CM': 10.0, 'UIN': 2.54e-5}
#: au-delà, l'unité annoncée est tenue pour fausse : le fichier est lu en millimètres
MAX_PIECE = 20000.0
FLAT = 0.01                                              # écart de corde d'une courbe sans équivalent exact (mm)
JOIN = 0.01                                              # raccord des courbes libres (mm)
MAX_CELLS = 128                                          # cases d'une surface, par direction
MESH_TOL = 0.005                                         # écart entre une surface et son maillage (mm)
MAX_DEPTH = 32
FLAT_FACE = 1e-3                                         # une face plate : pas plus de creux que cela (unités du fichier)
CRACK = 0.02                                             # fentes entre faces, refermées dans la silhouette (mm)
#: les couleurs que l'IGES désigne par un numéro (champ 13 de l'entrée)
COLORS = {1: '#000000', 2: '#ff0000', 3: '#00ff00', 4: '#0000ff', 5: '#ffff00', 6: '#ff00ff', 7: '#00ffff',
          8: '#ffffff'}


def _num(text: str, default: float = 0.0) -> float:
    t = text.strip()
    if not t:
        return default
    try:
        v = float(t.replace('D', 'E').replace('d', 'e'))
    except ValueError:
        return default
    return v if math.isfinite(v) else default


def _int(text: str, default: int = 0) -> int:
    return int(_num(text, default))


def _fields(text: str, pd: str, rd: str) -> list[str]:
    """Les champs d'un enregistrement, chaînes « 5Hhello » comprises."""
    if 'H' not in text and 'h' not in text:              # le cas des nombres : bien plus rapide
        return text.split(rd, 1)[0].split(pd)
    out, cur, i, n = [], [], 0, len(text)
    while i < n:
        ch = text[i]
        if ch == rd:
            out.append(''.join(cur))
            return out
        if ch == pd:
            out.append(''.join(cur))
            cur = []
            i += 1
            continue
        if ch in 'Hh' and cur and ''.join(cur).strip().isdigit():
            size = int(''.join(cur).strip())
            cur = [text[i + 1:i + 1 + size]]
            i += 1 + size
            continue
        cur.append(ch)
        i += 1
    out.append(''.join(cur))
    return out


class _Counted(ValueError):
    """Une surface abîmée, déjà comptée sous son propre type."""


class _Entry:
    __slots__ = ('de', 'kind', 'ptr', 'count', 'form', 'matrix', 'level', 'blank', 'sub', 'use', 'color')

    def __init__(self, de: int, a: str, b: str):
        self.de = de
        self.kind = _int(a[0:8])
        self.ptr = _int(a[8:16])
        self.level = _int(a[32:40])
        self.matrix = _int(a[48:56])
        status = a[64:72].replace(' ', '0').rjust(8, '0')
        self.blank = status[0:2] == '01'
        self.sub = status[2:4]                           # 00 : indépendante
        self.use = status[4:6]                           # 00 : géométrie, 05 : paramétrique…
        self.color = _int(b[16:24])                      # 1 à 8 : couleur nommée ; négatif : son entité 314
        self.count = _int(b[24:32], 1)
        self.form = _int(b[32:40])

    @property
    def free(self) -> bool:
        return not self.blank and self.sub == '00' and self.use in ('00', '03', '04')


class _Piece:
    """Un morceau de Bézier rationnelle, en 3D."""
    __slots__ = ('p', 'w')

    def __init__(self, p, w=None):
        self.p = np.asarray(p, dtype=float)
        self.w = np.ones(len(self.p)) if w is None else np.asarray(w, dtype=float)

    def moved(self, m) -> '_Piece':
        return _Piece(self.p @ m[:3, :3].T + m[:3, 3], self.w)

    def reversed(self) -> '_Piece':
        return _Piece(self.p[::-1], self.w[::-1])

    def points(self, n: int) -> np.ndarray:
        t = np.linspace(0.0, 1.0, n + 1)[:, None]
        d = len(self.p) - 1
        h = np.hstack((self.p * self.w[:, None], self.w[:, None]))
        out = np.empty((n + 1, 4))
        for i, u in enumerate(t[:, 0]):
            q = h.copy()
            for r in range(1, d + 1):
                q[:d - r + 1] = (1 - u) * q[:d - r + 1] + u * q[1:d - r + 2]
            out[i] = q[0]
        return out[:, :3] / out[:, 3:4]


def _bezier_pieces(deg: int, knots, ctrl, weights, t0: float, t1: float) -> list[_Piece]:
    """NURBS → morceaux de Bézier sur [t0, t1], par insertion de nœuds (en coordonnées homogènes)."""
    U = [float(x) for x in knots]
    P = list(np.hstack((np.asarray(ctrl, float) * np.asarray(weights, float)[:, None], np.asarray(weights, float)[:, None])))
    if deg < 1 or len(P) < deg + 1 or len(U) != len(P) + deg + 1 or not t1 > t0:
        raise ValueError('courbe NURBS invalide')
    tol = max(abs(t1 - t0), 1.0) * 1e-10

    def insert(u: float, target: int) -> None:
        while True:
            s = sum(1 for x in U if abs(x - u) <= tol)
            if s >= target:
                return
            k = next(i for i in range(len(U) - 1) if U[i] <= u + tol and u + tol < U[i + 1])
            new = []
            for i in range(k - deg + 1, k - s + 1):
                den = U[i + deg] - U[i]
                a = (u - U[i]) / den if den else 0.0
                new.append((1 - a) * P[i - 1] + a * P[i])
            P[k - deg + 1:k - s] = new
            U.insert(k + 1, u)

    inner = sorted({x for x in U if t0 + tol < x < t1 - tol})
    for u in (t0, *inner, t1):
        insert(u, deg)
    pieces = []
    i = deg
    while i < len(P):
        a, b = U[i], U[i + 1]
        if b - a > tol and a >= t0 - tol and b <= t1 + tol:
            local = np.array(P[i - deg:i + 1])
            w = local[:, 3]
            if (np.abs(w) > 1e-12).all():
                pieces.append(_Piece(local[:, :3] / w[:, None], w))
        i += 1
    return pieces


def _arc_pieces(center, r: float, a0: float, sweep: float, z: float) -> list[_Piece]:
    n = max(1, math.ceil(abs(sweep) / (math.pi / 2) - 1e-9))
    step = sweep / n
    w = math.cos(step / 2)
    out = []
    for i in range(n):
        s = a0 + i * step
        e, m = s + step, s + step / 2
        out.append(_Piece([(center[0] + r * math.cos(s), center[1] + r * math.sin(s), z),
                           (center[0] + r / w * math.cos(m), center[1] + r / w * math.sin(m), z),
                           (center[0] + r * math.cos(e), center[1] + r * math.sin(e), z)], [1.0, w, 1.0]))
    return out


class _Surface:
    """Ce qui est commun aux surfaces : les bornes (u0, u1, v0, v1) et le retour de la 3D vers (u, v)."""
    u0 = v0 = 0.0
    u1 = v1 = 1.0
    model_rings = False                                  # un bord se lit d'abord en 3D : voir _Swept
    ring_step = 0.0                                      # un bord lu en 3D : au plus cet écart entre deux points
    edge = None                                          # le bord que la surface donne elle-même, dans (u, v)

    def settled(self, uv: np.ndarray) -> np.ndarray:
        """Les (u, v) d'un bord, tels qu'une face peut les suivre."""
        return uv

    def from_file(self, uv: np.ndarray) -> np.ndarray:
        """Un bord donné dans le paramétrage du fichier, ramené à celui de la surface."""
        return uv

    def closest(self, pts: np.ndarray, m=None) -> np.ndarray:
        """Les (u, v) des points 3D : le plus proche d'une grille serrée, puis quelques pas de Gauss-Newton."""
        ug = np.linspace(self.u0, self.u1, 129)
        vg = np.linspace(self.v0, self.v1, 129)
        uu, vv = np.meshgrid(ug, vg)
        grid = self.at(uu, vv, m)
        best = np.empty(len(pts), dtype=np.int64)
        for i in range(0, len(pts), 256):
            best[i:i + 256] = ((pts[i:i + 256, None, :] - grid[None, :, :]) ** 2).sum(axis=2).argmin(axis=1)
        u, v = uu.ravel()[best], vv.ravel()[best]
        hu, hv = (self.u1 - self.u0) * 1e-5, (self.v1 - self.v0) * 1e-5
        for _ in range(4):
            here = self.at(u, v, m)
            su = (self.at(u + hu, v, m) - self.at(u - hu, v, m)) / (2 * hu)
            sv = (self.at(u, v + hv, m) - self.at(u, v - hv, m)) / (2 * hv)
            r = pts - here
            a, b, c = (su * su).sum(axis=1), (su * sv).sum(axis=1), (sv * sv).sum(axis=1)
            d, e = (su * r).sum(axis=1), (sv * r).sum(axis=1)
            det = a * c - b * b
            ok = np.abs(det) > 1e-18
            du = np.divide(c * d - b * e, det, out=np.zeros_like(det), where=ok)
            dv = np.divide(a * e - b * d, det, out=np.zeros_like(det), where=ok)
            u = np.clip(u + du, self.u0, self.u1)
            v = np.clip(v + dv, self.v0, self.v1)
        return self.settled(np.column_stack((u, v)))

    def at(self, u, v, m=None) -> np.ndarray:
        q = self.eval(u, v)
        return q if m is None else q @ m[:3, :3].T + m[:3, 3]


class _Nurbs(_Surface):
    """Surface NURBS (entité 128) : x(u, v) par la base locale, vectorisée."""

    def __init__(self, v: list[str]):
        self.ku, self.kv, self.du, self.dv = (_int(v[i]) for i in range(4))
        if self.ku < 1 or self.kv < 1 or self.du < 1 or self.dv < 1:
            raise ValueError('surface NURBS invalide')
        i = 9
        nu = self.ku + self.du + 2
        nv = self.kv + self.dv + 2
        count = (self.ku + 1) * (self.kv + 1)
        vals = np.array([_num(x) for x in v[i:i + nu + nv + 4 * count + 4]], dtype=float)
        if len(vals) < nu + nv + 4 * count + 4:
            raise ValueError('surface NURBS incomplète')
        self.U, self.V = vals[:nu], vals[nu:nu + nv]
        at = nu + nv
        w = vals[at:at + count].reshape(self.kv + 1, self.ku + 1)
        at += count
        p = vals[at:at + 3 * count].reshape(self.kv + 1, self.ku + 1, 3)
        at += 3 * count
        self.H = np.concatenate((p * w[:, :, None], w[:, :, None]), axis=2)
        self.u0, self.u1, self.v0, self.v1 = (float(x) for x in vals[at:at + 4])
        if not self.u1 > self.u0 or not self.v1 > self.v0:
            self.u0, self.u1 = float(self.U[self.du]), float(self.U[self.ku + 1])
            self.v0, self.v1 = float(self.V[self.dv]), float(self.V[self.kv + 1])

    @staticmethod
    def _basis(knots, deg: int, last: int, t):
        span = np.clip(np.searchsorted(knots, t, side='right') - 1, deg, last)
        N = np.zeros((t.size, deg + 1))
        N[:, 0] = 1.0
        left = np.zeros_like(N)
        right = np.zeros_like(N)
        for j in range(1, deg + 1):
            left[:, j] = t - knots[span + 1 - j]
            right[:, j] = knots[span + j] - t
            saved = np.zeros(t.size)
            for r in range(j):
                den = right[:, r + 1] + left[:, j - r]
                tmp = np.divide(N[:, r], den, out=np.zeros(t.size), where=den != 0)
                N[:, r] = saved + right[:, r + 1] * tmp
                saved = left[:, j - r] * tmp
            N[:, j] = saved
        return span, N

    def eval(self, u, v) -> np.ndarray:
        u = np.clip(np.asarray(u, float).ravel(), self.u0, self.u1)
        v = np.clip(np.asarray(v, float).ravel(), self.v0, self.v1)
        out = np.empty((u.size, 3))
        for a in range(0, u.size, 50000):                # par paquets : la mémoire reste bornée
            su, Nu = self._basis(self.U, self.du, self.ku, u[a:a + 50000])
            sv, Nv = self._basis(self.V, self.dv, self.kv, v[a:a + 50000])
            iu = su[:, None] - self.du + np.arange(self.du + 1)
            iv = sv[:, None] - self.dv + np.arange(self.dv + 1)
            local = self.H[iv[:, :, None], iu[:, None, :]]
            h = np.einsum('ij,ik,ijkl->il', Nv, Nu, local)
            out[a:a + 50000] = h[:, :3] / h[:, 3:4]
        return out

    def _params(self, knots, deg: int, t0: float, t1: float, bend: float, tol: float) -> np.ndarray:
        """Les valeurs du paramètre : par travée, selon le pli du réseau de contrôle (borne de Wang)."""
        cuts = sorted({float(x) for x in knots if t0 < x < t1} | {t0, t1})
        spans = len(cuts) - 1
        per = 1 if deg == 1 else max(2, math.ceil(math.sqrt(deg * (deg - 1) / 8.0 * bend / max(tol, 1e-12))))
        per = max(1, min(per, MAX_CELLS // max(spans, 1)))
        out = [np.linspace(a, b, per, endpoint=False) for a, b in zip(cuts, cuts[1:])]
        return np.concatenate((*out, [t1]))

    def grid(self, tol: float) -> tuple[np.ndarray, np.ndarray]:
        P = self.H[:, :, :3] / self.H[:, :, 3:4]
        bu = float(np.linalg.norm(P[:, 2:] - 2 * P[:, 1:-1] + P[:, :-2], axis=2).max()) if self.ku >= 2 else 0.0
        bv = float(np.linalg.norm(P[2:, :] - 2 * P[1:-1, :] + P[:-2, :], axis=2).max()) if self.kv >= 2 else 0.0
        return (self._params(self.U, self.du, self.u0, self.u1, bu, tol),
                self._params(self.V, self.dv, self.v0, self.v1, bv, tol))

    def spread(self) -> np.ndarray:
        return (self.H[:, :, :3] / self.H[:, :, 3:4]).reshape(-1, 3)


def _steps(p: _Piece, tol: float) -> int:
    length = float(np.linalg.norm(np.diff(p.p, axis=0), axis=1).sum())
    return int(min(64, max(4, math.ceil(math.sqrt(length / max(tol, 1e-12))))))


def _denser(pts: np.ndarray, step: float) -> np.ndarray:
    """Une ligne brisée, sans côté de plus de `step`."""
    out = [pts[:1]]
    for a, b in zip(pts, pts[1:]):
        n = max(1, int(min(256, math.ceil(float(np.linalg.norm(b - a)) / step))))
        out.append(a + (b - a) * np.linspace(0.0, 1.0, n + 1)[1:, None])
    return np.vstack(out)


class _Profile:
    """Une courbe que suit une surface : ses points à la tolérance, repérés par s dans [0, 1]."""

    def __init__(self, s, pts, t0: float, t1: float, closed: bool):
        self.s, self.pts = s, pts
        self.t0, self.t1 = t0, t1                        # le paramètre de la courbe dans le fichier, à ses deux bouts
        self.closed = closed

    def at(self, s) -> np.ndarray:
        s = np.asarray(s, float)
        if self.closed:
            s = np.mod(s, 1.0)
        return np.stack([np.interp(s, self.s, self.pts[:, i]) for i in range(3)], axis=-1)

    def across(self, lo: float, hi: float) -> np.ndarray:
        """Les valeurs de s d'un maillage entre lo et hi : plus d'un tour si un bord passe la couture."""
        step = max(1, math.ceil((len(self.s) - 1) / MAX_CELLS))
        base = np.append(self.s[:-1][::step], self.s[-1])
        if lo >= -1e-12 and hi <= 1.0 + 1e-12:
            return base
        first, last = math.floor(lo), math.ceil(hi)
        return np.concatenate((*(base[:-1] + k for k in range(first, last)), [float(last)]))


class _Swept(_Surface):
    """Les surfaces balayées. Leur paramétrage varie selon les logiciels et une couture coupe leurs bords : quand
    le fichier donne un bord à la fois en 3D et dans (u, v), celui en 3D fait foi, ramené sur la surface."""
    model_rings = True
    closed_u = False

    def settled(self, uv: np.ndarray) -> np.ndarray:
        if self.closed_u:
            uv = np.column_stack((self._turned(uv[:, 0], 1.0, 0.0), uv[:, 1]))
            self.u0, self.u1 = min(self.u0, float(uv[:, 0].min())), max(self.u1, float(uv[:, 0].max()))
        return uv

    @staticmethod
    def _turned(x: np.ndarray, period: float, low: float) -> np.ndarray:
        """Sans saut d'un tour le long du bord, et commençant dans le premier tour."""
        x = np.unwrap(x, period=period)
        return x - period * math.floor((float(x.min()) - low + 1e-9) / period)

    def spread(self) -> np.ndarray:
        us, vs = self.grid(1.0)
        uu, vv = np.meshgrid(us, vs)
        return self.eval(uu, vv)


class _Tabulated(_Swept):
    """Entité 122 : S(u, v) = C(u) + v·(L - C(0)), u et v dans [0, 1]."""

    def __init__(self, curve: _Profile, end):
        self.curve = curve
        self.closed_u = curve.closed
        self.along = np.asarray(end, float) - curve.pts[0]
        if float(np.linalg.norm(self.along)) <= 0.0:
            raise ValueError('cylindre tabulé sans hauteur')

    def eval(self, u, v) -> np.ndarray:
        u, v = np.asarray(u, float).ravel(), np.asarray(v, float).ravel()
        return self.curve.at(u) + v[:, None] * self.along

    def grid(self, tol: float):
        return self.curve.across(self.u0, self.u1), np.array([self.v0, self.v1])


class _Ruled(_Swept):
    """Entité 118 : S(u, v) = (1 - v)·C1(u) + v·C2(u), C2 parcourue à l'envers si le fichier le demande."""

    def __init__(self, c1: _Profile, c2: _Profile, reverse: bool):
        self.c1, self.c2, self.reverse = c1, c2, reverse
        self.closed_u = c1.closed and c2.closed

    def eval(self, u, v) -> np.ndarray:
        u, v = np.asarray(u, float).ravel(), np.asarray(v, float).ravel()
        other = self.c2.at(1.0 - u if self.reverse else u)
        return (1.0 - v)[:, None] * self.c1.at(u) + v[:, None] * other

    def grid(self, tol: float):
        second = self.c2.across(self.u0, self.u1)
        return np.union1d(self.c1.across(self.u0, self.u1), 1.0 - second if self.reverse else second), \
            np.array([self.v0, self.v1])


class _Revolution(_Swept):
    """Entité 120 : la génératrice C(u) tournée de v radians autour de l'axe, u étant son paramètre ramené à [0, 1]."""

    def __init__(self, a, b, curve: _Profile, start: float, end: float):
        self.o = np.asarray(a, float)
        k = np.asarray(b, float) - self.o
        size = float(np.linalg.norm(k))
        if size <= 0.0:
            raise ValueError('axe de révolution nul')
        self.k = k / size
        self.curve = curve
        self.closed_u = curve.closed
        if end <= start:
            end += 2.0 * math.pi
        self.v0, self.v1 = start, end
        self.rmax = float(self._radius(curve.s).max())
        if self.rmax <= 0.0:
            raise ValueError('génératrice sur son axe')
        self.ring_step = 0.02 * self.rmax                # une corde de disque n'est pas droite dans (u, v)

    def _radius(self, u) -> np.ndarray:
        q = self.curve.at(u) - self.o
        return np.linalg.norm(q - (q @ self.k)[:, None] * self.k, axis=1)

    def eval(self, u, v) -> np.ndarray:
        u, v = np.asarray(u, float).ravel(), np.asarray(v, float).ravel()
        q = self.curve.at(u) - self.o
        along = (q @ self.k)[:, None] * self.k
        return self.o + along + np.cos(v)[:, None] * (q - along) + np.sin(v)[:, None] * np.cross(self.k, q)

    def grid(self, tol: float):
        ratio = min(1.0, tol / self.rmax)
        n = math.ceil((self.v1 - self.v0) / max(2.0 * math.acos(1.0 - ratio), 1e-9))
        return self.curve.across(self.u0, self.u1), np.linspace(self.v0, self.v1, int(min(MAX_CELLS, max(8, n))) + 1)

    def from_file(self, uv: np.ndarray) -> np.ndarray:
        span = self.curve.t1 - self.curve.t0
        return np.column_stack(((uv[:, 0] - self.curve.t0) / span, uv[:, 1]))

    def settled(self, uv: np.ndarray) -> np.ndarray:
        uv = super().settled(uv)
        pole = self._radius(uv[:, 0]) <= 1e-4 * self.rmax
        if pole.all():
            return uv
        at = int(np.argmin(pole))                        # commence hors d'un pôle
        uv, pole = np.roll(uv, -at, axis=0), np.roll(pole, -at)
        kept = ~pole
        angle = uv[:, 1].copy()
        angle[kept] = np.unwrap(angle[kept], period=2.0 * math.pi)
        rows = []
        last = float(angle[0])
        for i, (u, _v) in enumerate(uv):
            if pole[i]:                                  # au pôle, l'angle ne dit rien : on y arrive et on en repart
                rows.append((u, last))
                continue
            if i and pole[i - 1]:
                rows.append((uv[i - 1, 0], float(angle[i])))
            last = float(angle[i])
            rows.append((u, last))
        out = np.array(rows)
        out[:, 1] -= 2.0 * math.pi * math.floor((float(out[:, 1].min()) - self.v0 + 1e-9) / (2.0 * math.pi))
        self.v1 = max(self.v1, float(out[:, 1].max()))
        return out


class _Plane(_Surface):
    """Entité 108 : un plan n'a pas de paramètres à lui. Ses bornes viennent des bords qu'on y pose ; un plan
    horizontal prend x et y pour (u, v), seul cas où un bord donné en (u, v) a un sens."""
    model_rings = True
    u0 = v0 = math.inf
    u1 = v1 = -math.inf

    def __init__(self, a: float, b: float, c: float, d: float):
        n = np.array([a, b, c], float)
        size = float(np.linalg.norm(n))
        if size <= 0.0:
            raise ValueError('plan sans normale')
        n /= size
        self.origin = n * d / size
        self.level = abs(float(n[2])) > 1.0 - 1e-9
        if self.level:
            self.e1, self.e2 = np.array([1.0, 0.0, 0.0]), np.array([0.0, 1.0, 0.0])
        else:
            self.e1 = np.cross((0.0, 0.0, 1.0), n)
            self.e1 /= float(np.linalg.norm(self.e1))
            self.e2 = np.cross(n, self.e1)

    def _grown(self, uv: np.ndarray) -> np.ndarray:
        self.u0, self.u1 = min(self.u0, float(uv[:, 0].min())), max(self.u1, float(uv[:, 0].max()))
        self.v0, self.v1 = min(self.v0, float(uv[:, 1].min())), max(self.v1, float(uv[:, 1].max()))
        return uv

    def eval(self, u, v) -> np.ndarray:
        u, v = np.asarray(u, float).ravel(), np.asarray(v, float).ravel()
        return self.origin + u[:, None] * self.e1 + v[:, None] * self.e2

    def grid(self, tol: float):
        return np.array([self.u0, self.u1]), np.array([self.v0, self.v1])

    def closest(self, pts: np.ndarray, m=None) -> np.ndarray:
        q = pts if m is None else (pts - m[:3, 3]) @ np.linalg.inv(m[:3, :3]).T
        return self._grown(np.column_stack(((q - self.origin) @ self.e1, (q - self.origin) @ self.e2)))

    def from_file(self, uv: np.ndarray) -> np.ndarray:
        if not self.level:
            raise ValueError('bord de plan sans courbe en 3D')
        return self._grown(uv)


def _triangulated(geom) -> list:
    """Triangles (shapely) d'une zone ; `constrained_delaunay_triangles` respecte ses bords."""
    import shapely
    from shapely.ops import triangulate
    out = []
    for poly in getattr(geom, 'geoms', [geom]):
        if poly.is_empty or poly.geom_type != 'Polygon' or poly.area <= 0:
            continue
        if hasattr(shapely, 'constrained_delaunay_triangles'):
            out.extend(shapely.constrained_delaunay_triangles(poly).geoms)
        else:
            out.extend(t for t in triangulate(poly) if poly.contains(t.representative_point()))
    return out


def _mesh_face(surf: _Nurbs, region, tol: float) -> np.ndarray:
    """Triangles (n, 3, 3) d'une surface ; `region` : sa zone utile dans (u, v) (None : toute la surface)."""
    import shapely
    us, vs = surf.grid(tol)
    uu, vv = np.meshgrid(us, vs)
    ax, ay = uu[:-1, :-1].ravel(), vv[:-1, :-1].ravel()
    bx, by = uu[1:, 1:].ravel(), vv[1:, 1:].ravel()
    if region is None:
        uvs = np.stack(((ax, ay), (bx, ay), (bx, by), (ax, ay), (bx, by), (ax, by)), axis=1).transpose(2, 1, 0).reshape(-1, 2)
    else:
        shapely.prepare(region)
        cells = shapely.box(ax, ay, bx, by)
        hit = shapely.intersects(region, cells)
        full = hit & shapely.contains(region, cells)
        rows = []
        if full.any():
            a, c, b, d = ax[full], ay[full], bx[full], by[full]
            rows.append(np.stack(((a, c), (b, c), (b, d), (a, c), (b, d), (a, d)), axis=1).transpose(2, 1, 0).reshape(-1, 2))
        for geom in shapely.intersection(cells[hit & ~full], region):
            tris = [np.asarray(t.exterior.coords)[:3] for t in _triangulated(geom)]
            if tris:
                rows.append(np.asarray(tris).reshape(-1, 2))
        if not rows:
            return np.empty((0, 3, 3))
        uvs = np.vstack(rows)
    pts = surf.eval(uvs[:, 0], uvs[:, 1])
    return pts.reshape(-1, 3, 3)


class _Reader:
    def __init__(self, path):
        self.notes: list[str] = []
        self.skipped: collections.Counter = collections.Counter()
        self.lines = {'S': [], 'G': [], 'D': [], 'P': []}
        try:
            text = pathlib.Path(path).read_bytes().decode('latin-1')
        except OSError as ex:
            raise ValueError(f'IGES illisible : {ex}') from ex
        for line in text.splitlines():
            if len(line) >= 73 and line[72] in self.lines:
                self.lines[line[72]].append(line)
        if not self.lines['D'] or not self.lines['P']:
            raise ValueError('IGES illisible : pas de sections D et P en lignes de 80 colonnes (fichier compressé ou binaire ?)')
        self._global()
        self.entries: dict[int, _Entry] = {}
        d = self.lines['D']
        for i in range(0, len(d) - 1, 2):
            de = _int(d[i][73:80], i + 1)
            self.entries[de] = _Entry(de, d[i].ljust(80), d[i + 1].ljust(80))
        self._params: dict[int, list[str]] = {}
        self._matrices: dict[int, np.ndarray | None] = {}
        self._surfaces: dict[int, _Surface] = {}
        self.tints: dict[int, list] = {}                 # par niveau : la couleur de chaque contour de `free_curves`
        self.tol = MESH_TOL

    def _global(self) -> None:
        g = ''.join(x[:72] for x in self.lines['G'])
        self.pd, self.rd = ',', ';'
        head = g.lstrip()
        if head[:2] == '1H' and len(head) > 2:
            self.pd = head[2]
            rest = head[3:].lstrip()
            if rest.startswith(self.pd):
                rest = rest[1:].lstrip()
            if rest[:2] == '1H' and len(rest) > 2:       # sinon le point-virgule d'origine
                self.rd = rest[2]
        elif head.startswith(','):
            rest = head[1:].lstrip()
            if rest[:2] == '1H' and len(rest) > 2:
                self.rd = rest[2]
        f = _fields(g, self.pd, self.rd)
        flag = _int(f[13], 2) if len(f) > 13 else 2
        name = f[14].strip().upper() if len(f) > 14 else ''
        self.unit = UNITS.get(flag) or UNIT_NAMES.get(name.lstrip('0123456789H'), 1.0)
        self.unit_name = name

    def params(self, de: int) -> list[str]:
        got = self._params.get(de)
        if got is None:
            e = self.entries[de]
            lines = self.lines['P'][e.ptr - 1:e.ptr - 1 + e.count]
            got = _fields(''.join(x[:64] for x in lines), self.pd, self.rd)[1:]
            self._params[de] = got
        return got

    def matrix(self, de: int, depth: int = 0):
        """La matrice 4×4 d'une entité (celle d'une entité 124, avec sa propre matrice) ; None : identité."""
        if de <= 0 or de not in self.entries or depth > MAX_DEPTH:
            return None
        if de in self._matrices:
            return self._matrices[de]
        e = self.entries[de]
        m = None
        if e.kind == 124:
            v = [_num(x) for x in self.params(de)]
            if len(v) >= 12:
                m = np.eye(4)
                m[:3, :4] = np.array(v[:12]).reshape(3, 4)
        parent = self.matrix(e.matrix, depth + 1) if e.matrix > 0 else None
        if parent is not None:
            m = parent if m is None else parent @ m
        self._matrices[de] = m
        return m

    def curve(self, de: int, depth: int = 0) -> list[_Piece]:
        """Les morceaux d'une courbe, dans le repère du modèle."""
        e = self.entries.get(de)
        if e is None or depth > MAX_DEPTH:
            return []
        try:
            out = self._curve(e, depth)
        except (ValueError, IndexError, ZeroDivisionError):
            self.skipped[f'{e.kind} (abîmée)'] += 1
            return []
        m = self.matrix(e.matrix) if e.matrix > 0 else None
        return out if m is None else [p.moved(m) for p in out]

    def _curve(self, e: _Entry, depth: int) -> list[_Piece]:
        v = self.params(e.de)
        k = e.kind
        if k == 110:
            a = [_num(x) for x in v[:6]]
            return [_Piece([a[:3], a[3:6]])] if len(a) == 6 else []
        if k == 100:
            z, cx, cy, sx, sy, ex, ey = (_num(x) for x in v[:7])
            r = math.hypot(sx - cx, sy - cy)
            if r <= 0:
                return []
            a0 = math.atan2(sy - cy, sx - cx)
            sweep = (math.atan2(ey - cy, ex - cx) - a0) % (2 * math.pi)
            if sweep < 1e-9:                             # départ = arrivée : le cercle entier
                sweep = 2 * math.pi
            return _arc_pieces((cx, cy), r, a0, sweep, z)
        if k == 102:
            out: list[_Piece] = []
            for x in v[1:1 + _int(v[0])]:
                out.extend(self.curve(_int(x), depth + 1))
            return out
        if k == 104:
            return self._conic(v, e.form)
        if k == 106:
            return self._copious(v, e.form)
        if k == 112:
            return self._spline(v)
        if k == 126:
            K, M = _int(v[0]), _int(v[1])
            n = K + M + 2
            at = 6
            knots = [_num(x) for x in v[at:at + n]]
            at += n
            w = [_num(x) for x in v[at:at + K + 1]]
            at += K + 1
            p = np.array([_num(x) for x in v[at:at + 3 * (K + 1)]], dtype=float).reshape(-1, 3)
            at += 3 * (K + 1)
            t0, t1 = _num(v[at]), _num(v[at + 1])
            return _bezier_pieces(M, knots, p, w, t0, t1)
        self.skipped[str(k)] += 1
        return []

    def _conic(self, v, form: int) -> list[_Piece]:
        A, B, C, D, E, F, z, sx, sy, ex, ey = (_num(x) for x in v[:11])
        if form == 1 or (form == 0 and 4 * A * C - B * B > 0):
            det = 4 * A * C - B * B
            cx, cy = (B * E - 2 * C * D) / det, (B * D - 2 * A * E) / det
            F0 = F + (D * cx + E * cy) / 2
            th = 0.5 * math.atan2(B, A - C)
            c, s = math.cos(th), math.sin(th)
            a2 = A * c * c + B * c * s + C * s * s
            b2 = A * s * s - B * c * s + C * c * c
            if F0 * a2 >= 0 or F0 * b2 >= 0:
                raise ValueError('ellipse invalide')
            ra, rb = math.sqrt(-F0 / a2), math.sqrt(-F0 / b2)

            def angle(x, y):
                dx, dy = x - cx, y - cy
                return math.atan2((-s * dx + c * dy) / rb, (c * dx + s * dy) / ra)
            a0 = angle(sx, sy)
            sweep = (angle(ex, ey) - a0) % (2 * math.pi)
            if sweep < 1e-9:
                sweep = 2 * math.pi
            m = np.array([[c * ra, -s * rb, 0, cx], [s * ra, c * rb, 0, cy], [0, 0, 1, 0], [0, 0, 0, 1]], dtype=float)
            return [p.moved(m) for p in _arc_pieces((0.0, 0.0), 1.0, a0, sweep, z)]
        # hyperbole, parabole : des points de l'arc, au-dessus de sa corde
        chord = math.hypot(ex - sx, ey - sy)
        if chord <= 0:
            return []
        nx, ny = -(ey - sy) / chord, (ex - sx) / chord
        pts = [(sx, sy, z)]
        for i in range(1, 64):
            t = i / 64
            x0, y0 = sx + t * (ex - sx), sy + t * (ey - sy)
            q2 = A * nx * nx + B * nx * ny + C * ny * ny
            q1 = 2 * A * x0 * nx + B * (x0 * ny + y0 * nx) + 2 * C * y0 * ny + D * nx + E * ny
            q0 = A * x0 * x0 + B * x0 * y0 + C * y0 * y0 + D * x0 + E * y0 + F
            if abs(q2) < 1e-14:
                roots = [-q0 / q1] if abs(q1) > 1e-14 else []
            else:
                disc = q1 * q1 - 4 * q2 * q0
                roots = [(-q1 + w * math.sqrt(disc)) / (2 * q2) for w in (1, -1)] if disc >= 0 else []
            if roots:
                h = min(roots, key=abs)
                pts.append((x0 + h * nx, y0 + h * ny, z))
        pts.append((ex, ey, z))
        return [_Piece([a, b]) for a, b in zip(pts, pts[1:])]

    def _copious(self, v, form: int) -> list[_Piece]:
        if form not in (11, 12, 13, 63):                 # 1 à 3 : un nuage de points ; 20 et plus : des annotations
            self.skipped['106 (points)'] += 1
            return []
        ip, n = _int(v[0]), _int(v[1])
        d = [_num(x) for x in v[2:]]
        if ip == 1:
            z = d[0]
            pts = [(d[1 + 2 * i], d[2 + 2 * i], z) for i in range(n)]
        else:
            size = 3 if ip == 2 else 6
            pts = [(d[size * i], d[size * i + 1], d[size * i + 2]) for i in range(n)]
        if form == 63 and pts:
            pts.append(pts[0])
        return [_Piece([a, b]) for a, b in zip(pts, pts[1:]) if a != b]

    def _spline(self, v) -> list[_Piece]:
        n = _int(v[3])
        d = [_num(x) for x in v[4:]]
        t = d[:n + 1]
        c = d[n + 1:]
        out = []
        for i in range(n):
            s = t[i + 1] - t[i]
            a = c[12 * i:12 * i + 12]
            if len(a) < 12:
                break
            q = []
            for ax in range(3):
                A, B, C, D = a[4 * ax:4 * ax + 4]
                q.append((A, A + B * s / 3, A + 2 * B * s / 3 + C * s * s / 3, A + B * s + C * s * s + D * s ** 3))
            out.append(_Piece(np.array(q).T))
        return out

    # --- surfaces -----------------------------------------------------------------------------

    def _nurbs(self, de: int):
        """La surface (déplacée par sa matrice), ou None : compte les types qu'on ne lit pas et les abîmées."""
        e = self.entries.get(de)
        if e is None:
            return None, None
        if e.kind not in SURFACES:
            self.skipped[str(e.kind)] += 1
            return None, None
        m = self.matrix(e.matrix) if e.matrix > 0 else None
        if de not in self._surfaces:
            self._surfaces[de] = self._surface(e, m)
        return self._surfaces[de], m

    def _surface(self, e: _Entry, m) -> _Surface:
        v = self.params(e.de)
        if e.kind == 128:
            return _Nurbs(v)
        try:
            if e.kind == 108:
                plane = _Plane(*(_num(x) for x in v[:4]))
                ptr = _int(v[4]) if len(v) > 4 else 0
                if ptr > 0 and e.form >= 0 and self.entries.get(ptr) is not None:
                    pieces = self.curve(ptr)
                    if m is not None and self.entries[ptr].matrix <= 0:
                        pieces = [q.moved(m) for q in pieces]    # le bord n'a pas sa matrice : celle du plan
                    plane.edge = self._ring_from_model(pieces, plane, m) if pieces else None
                return plane
            if e.kind == 118:
                by_length = e.form == 0                  # forme 0 : à longueur relative égale ; 1 : à paramètre égal
                return _Ruled(self._profile(_int(v[0]), by_length), self._profile(_int(v[1]), by_length), _int(v[2]) == 1)
            if e.kind == 120:
                axis = self.curve(_int(v[0]))
                if not axis:
                    raise ValueError('axe de révolution illisible')
                return _Revolution(axis[0].p[0], axis[-1].p[-1], self._profile(_int(v[1])), _num(v[2]), _num(v[3]))
            return _Tabulated(self._profile(_int(v[0])), [_num(x) for x in v[1:4]])
        except (ValueError, IndexError, ZeroDivisionError) as ex:
            self.skipped[f'{e.kind} (abîmée)'] += 1
            raise _Counted from ex

    def _profile(self, de: int, by_length: bool = False) -> _Profile:
        """Une courbe en points, s étant son paramètre ramené à [0, 1] (la longueur parcourue, s'il n'est pas connu :
        pour une ligne et un arc, c'est la même chose)."""
        e = self.entries.get(de)
        pieces = self.curve(de) if e is not None else []
        if not pieces:
            raise ValueError('courbe de surface illisible')
        rows = [q.p if len(q.p) == 2 else q.points(_steps(q, self.tol)) for q in pieces]
        v = self.params(de)
        t0, t1, cuts = 0.0, 1.0, None
        if e.kind == 100:
            cx, cy = _num(v[1]), _num(v[2])
            t0 = math.atan2(_num(v[4]) - cy, _num(v[3]) - cx)
            sweep = (math.atan2(_num(v[6]) - cy, _num(v[5]) - cx) - t0) % (2.0 * math.pi)
            t1 = t0 + (sweep if sweep >= 1e-9 else 2.0 * math.pi)
        elif e.kind == 126:
            K, M = _int(v[0]), _int(v[1])
            n = K + M + 2
            t0, t1 = _num(v[6 + n + 4 * (K + 1)]), _num(v[7 + n + 4 * (K + 1)])
            cuts = sorted({_num(x) for x in v[6:6 + n] if t0 < _num(x) < t1} | {t0, t1})
        pts = np.vstack([rows[0], *(r[1:] for r in rows[1:])])
        if cuts is not None and not by_length and len(cuts) == len(rows) + 1:
            parts = [cuts[i] + np.linspace(0.0, 1.0, len(r)) * (cuts[i + 1] - cuts[i]) for i, r in enumerate(rows)]
            s = (np.concatenate([parts[0], *(x[1:] for x in parts[1:])]) - t0) / (t1 - t0)
        else:
            d = np.concatenate(([0.0], np.cumsum(np.linalg.norm(np.diff(pts, axis=0), axis=1))))
            if d[-1] <= 0.0:
                raise ValueError('courbe de surface sans longueur')
            s = d / d[-1]
        keep = np.concatenate(([True], np.diff(s) > 1e-12))
        return _Profile(s[keep], pts[keep], t0, t1, float(np.linalg.norm(pts[-1] - pts[0])) <= max(self.tol, 1e-9))

    def _uv_ring(self, pieces: list[_Piece], surf: _Surface):
        pts = _flat_points(pieces, max(surf.u1 - surf.u0, surf.v1 - surf.v0) / 2000.0)
        return surf.from_file(pts[:, :2]) if len(pts) >= 3 else None

    def _ring_from_model(self, pieces: list[_Piece], surf: _Surface, m):
        """Un bord donné en 3D seulement : ramené dans (u, v) par le point le plus proche sur une grille serrée."""
        pts = _flat_points(pieces, self.tol)
        if len(pts) < 3:
            return None
        if surf.ring_step:
            pts = _denser(pts, surf.ring_step)
        return surf.closest(pts, m)

    def _face(self, surf, m, outer, holes, up=True) -> np.ndarray:
        """Triangles d'une face : `outer`/`holes` dans (u, v) ; bord invalide : la surface entière, comptée."""
        from shapely.geometry import Polygon
        if outer is None:
            outer = surf.edge
        if outer is None and isinstance(surf, _Plane):   # un plan sans bord : il n'a pas de fin
            self.skipped['108'] += 1
            return np.empty((0, 3, 3))
        region = None
        if outer is not None or holes:
            try:
                base = Polygon(outer).buffer(0) if outer is not None else \
                    Polygon([(surf.u0, surf.v0), (surf.u1, surf.v0), (surf.u1, surf.v1), (surf.u0, surf.v1)])
                for h in holes:
                    base = base.difference(Polygon(h).buffer(0))
                if base.is_empty or base.area <= 0:
                    raise ValueError
                region = base
            except (ValueError, TypeError):
                self.untrimmed += 1
        tris = _mesh_face(surf, region, self.tol)
        if m is not None and len(tris):
            tris = tris @ m[:3, :3].T + m[:3, 3]
        if len(tris) and up is not None:
            n = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])[:, 2]
            flip = (n < 0) if up else (n > 0)
            tris[flip] = tris[flip][:, ::-1]
        return tris

    def _trimmed(self, de: int) -> np.ndarray:
        v = self.params(de)
        surf, m = self._nurbs(_int(v[0]))
        if surf is None:
            return np.empty((0, 3, 3))
        n1, n2, pto = _int(v[1]), _int(v[2]), _int(v[3])

        def ring(ptr: int):
            if ptr not in self.entries or self.entries[ptr].kind != 142:
                return None
            f = self.params(ptr)
            b, c = _int(f[2]), _int(f[3])
            for which in ((c, b) if surf.model_rings else (b, c)):
                pieces = self.curve(which) if which > 0 else []
                if pieces:
                    return self._ring_from_model(pieces, surf, m) if which == c else self._uv_ring(pieces, surf)
            return None
        outer = ring(pto) if n1 and pto else None
        holes = [r for r in (ring(_int(x)) for x in v[4:4 + n2]) if r is not None]
        return self._face(surf, m, outer, holes)

    def _bounded(self, de: int) -> np.ndarray:
        """Entité 143 : surface et bords (141), le premier étant l'extérieur."""
        v = self.params(de)
        surf, m = self._nurbs(_int(v[1]))
        if surf is None:
            return np.empty((0, 3, 3))
        rings = []
        for x in v[3:3 + _int(v[2])]:
            ptr = _int(x)
            if ptr not in self.entries or self.entries[ptr].kind != 141:
                continue
            f = self.params(ptr)
            n, at = _int(f[3]), 4
            uv, model = [], []
            for _ in range(n):
                curve, sense, k = _int(f[at]), _int(f[at + 1]), _int(f[at + 2])
                par = [_int(y) for y in f[at + 3:at + 3 + k]]
                at += 3 + k
                got = [p for q in par for p in self.curve(q)]
                uv.extend(_oriented(got, sense != 2))
                model.extend(_oriented(self.curve(curve), sense != 2))
            if uv and not (surf.model_rings and model):
                r = self._uv_ring(uv, surf)
            else:
                r = self._ring_from_model(model, surf, m) if model else None
            if r is not None:
                rings.append(r)
        return self._face(surf, m, rings[0] if rings else None, rings[1:])

    def _solid_face(self, de: int, same: bool | None) -> np.ndarray:
        """Entité 510 : surface et boucles (508), avec leurs courbes dans (u, v) si le fichier les donne."""
        v = self.params(de)
        surf, m = self._nurbs(_int(v[0]))
        if surf is None:
            return np.empty((0, 3, 3))
        n, has_outer = _int(v[1]), _int(v[2])
        rings = [self._loop(_int(x), surf, m) for x in v[3:3 + n]]
        rings = [r for r in rings if r is not None]
        outer = rings[0] if rings and has_outer else None
        holes = rings[1:] if rings and has_outer else rings
        return self._face(surf, m, outer, holes, up=same if same is not None else True)

    def _loop(self, de: int, surf, m):
        e = self.entries.get(de)
        if e is None or e.kind != 508:
            return None
        v = self.params(de)
        n, at = _int(v[0]), 1
        uv: list[_Piece] = []
        model: list[_Piece] = []
        whole = True
        for _ in range(n):
            kind, edge, ndx, same, k = _int(v[at]), _int(v[at + 1]), _int(v[at + 2]), _int(v[at + 3]), _int(v[at + 4])
            par = [_int(v[at + 6 + 2 * j]) for j in range(k)]
            at += 5 + 2 * k
            got = [p for q in par for p in self.curve(q)]
            if got:
                uv.extend(_oriented(got, True))          # chaque courbe paramétrique suit déjà le sens de la boucle
            else:
                whole = False
            if kind == 0 and edge in self.entries and self.entries[edge].kind == 504:
                f = self.params(edge)
                curve = _int(f[1 + 5 * (ndx - 1)]) if ndx >= 1 and 1 + 5 * (ndx - 1) < len(f) else 0
                model.extend(_oriented(self.curve(curve), bool(same)))
        if uv and whole and not (surf.model_rings and model):
            return self._uv_ring(uv, surf)
        return self._ring_from_model(model, surf, m) if model else None

    def net_size(self) -> float:
        """La plus grande étendue des réseaux de contrôle des surfaces (unités du fichier)."""
        lo, hi = None, None
        counted = self.skipped.copy()
        for e in self.entries.values():
            if e.kind not in (128, 118, 120, 122) or e.blank:
                continue
            try:
                surf, m = self._nurbs(e.de)
            except (ValueError, IndexError):
                continue
            q = surf.spread()
            if m is not None:
                q = q @ m[:3, :3].T + m[:3, 3]
            a, b = q.min(axis=0), q.max(axis=0)
            lo = a if lo is None else np.minimum(lo, a)
            hi = b if hi is None else np.maximum(hi, b)
        self.skipped = counted                           # rien n'est compté deux fois
        self._surfaces = {d: x for d, x in self._surfaces.items() if isinstance(x, _Nurbs)}    # la tolérance dépend de l'unité
        return float((hi - lo).max()) if lo is not None else 0.0

    def triangles(self) -> np.ndarray:
        """Toutes les faces, en unités du fichier."""
        self.untrimmed = 0
        self.faces = 0
        self.flat = np.empty(0, dtype=bool)
        used_face = set()
        out = []
        flat = []
        shells = [e for e in self.entries.values() if e.kind == 514 and not e.blank]
        faces = []
        for e in shells:
            v = self.params(e.de)
            for i in range(_int(v[0])):
                face, same = _int(v[1 + 2 * i]), _int(v[2 + 2 * i])
                if face in self.entries and self.entries[face].kind == 510:
                    used_face.add(face)
                    faces.append((face, bool(same)))
        faces += [(e.de, None) for e in self.entries.values() if e.kind == 510 and e.de not in used_face and not e.blank]
        jobs = [('face', d, s) for d, s in faces]
        surfaces_used = set()
        for e in self.entries.values():
            if e.blank:
                continue
            if e.kind in (144, 143):
                jobs.append(('trim' if e.kind == 144 else 'bound', e.de, None))
                try:
                    surfaces_used.add(_int(self.params(e.de)[0 if e.kind == 144 else 1]))
                except IndexError:
                    pass
        for d, _s in faces:
            try:
                surfaces_used.add(_int(self.params(d)[0]))
            except IndexError:
                pass
        for e in self.entries.values():
            if e.kind in SURFACES and not e.blank and e.sub == '00' and e.de not in surfaces_used:
                jobs.append(('whole', e.de, None))
            elif e.kind in (114, 140, 190, 192, 194, 196, 198) and e.free and e.de not in surfaces_used:
                self.skipped[str(e.kind)] += 1
        for i, (kind, de, same) in enumerate(jobs):
            progress.step(i, len(jobs), 'IGES : surface {0} sur {1}')
            try:
                if kind == 'face':
                    t = self._solid_face(de, same)
                elif kind == 'trim':
                    t = self._trimmed(de)
                elif kind == 'bound':
                    t = self._bounded(de)
                else:
                    surf, m = self._nurbs(de)
                    t = self._face(surf, m, None, []) if surf is not None else np.empty((0, 3, 3))
            except _Counted:
                continue
            except (ValueError, IndexError, ZeroDivisionError):
                self.skipped[f'{self.entries[de].kind} (abîmée)'] += 1
                continue
            if len(t):
                out.append(t)
                flat.append(np.full(len(t), float(np.ptp(t[:, :, 2])) <= FLAT_FACE))
                self.faces += 1
        if out:
            self.flat = np.concatenate(flat)
        return np.vstack(out) if out else np.empty((0, 3, 3))

    def free_curves(self) -> dict[int, list[Contour]]:
        """Les courbes indépendantes (sous-figures comprises), par niveau, projetées sur XY, en unités du fichier."""
        by_level: dict[int, list[Contour]] = {}
        self.tints = {}
        for e in self.entries.values():
            if e.free and e.kind in CURVES:
                cs = _contours_of(self.curve(e.de))
                if cs:
                    self._keep(by_level, e.level, cs, self.tint(e))
            elif e.free and e.kind == 408:
                self._instance(e, np.eye(4), by_level, 0, self.tint(e))
            elif e.free and e.kind == 116:
                self.skipped['116 (points)'] += 1
        return by_level

    def _keep(self, by_level, level: int, cs: list, color) -> None:
        by_level.setdefault(level, []).extend(cs)
        self.tints.setdefault(level, []).extend([color] * len(cs))

    def tint(self, e: _Entry, depth: int = 0) -> str | None:
        """La couleur d'une entité (« #rrggbb ») : son numéro (1 à 8), sa définition (314, en pour cent) ou, pour
        une courbe composite qui n'en a pas, celle de son premier morceau coloré. None : sans couleur."""
        if e.color > 0:
            return COLORS.get(e.color)
        if e.color < 0:
            d = self.entries.get(-e.color)
            if d is None or d.kind != 314:
                return None
            v = [_num(x, -1.0) for x in self.params(d.de)[:3]]
            return hex_of(*(c * 2.55 for c in v)) if len(v) == 3 and min(v) >= 0 else None
        if e.kind == 102 and depth <= MAX_DEPTH:
            v = self.params(e.de)
            for x in (v[1:1 + _int(v[0])] if v else ()):
                child = self.entries.get(_int(x))
                c = self.tint(child, depth + 1) if child is not None else None
                if c:
                    return c
        return None

    def _instance(self, e: _Entry, parent, by_level, depth: int, color=None) -> None:
        v = self.params(e.de)
        s = _num(v[4], 1.0) if len(v) > 4 else 1.0
        here = np.diag([s, s, s, 1.0])
        here[:3, 3] = [_num(v[1]), _num(v[2]), _num(v[3])]
        own = self.matrix(e.matrix) if e.matrix > 0 else None
        m = parent @ (here if own is None else own @ here)
        self._figure(_int(v[0]), m, by_level, depth + 1, color)

    def _figure(self, de: int, m, by_level, depth: int, color=None) -> None:
        d = self.entries.get(de)
        if d is None or d.kind != 308 or depth > MAX_DEPTH:
            return
        v = self.params(de)
        for x in v[3:3 + _int(v[2])]:
            ptr = _int(x)
            e = self.entries.get(ptr)
            if e is None or e.blank:
                continue
            if e.kind == 408:
                self._instance(e, m, by_level, depth + 1, self.tint(e) or color)
            elif e.kind in CURVES:
                cs = _contours_of([p.moved(m) for p in self.curve(ptr)])
                if cs:                                   # sans couleur : celle de l'instance
                    self._keep(by_level, e.level, cs, self.tint(e) or color)


def _oriented(pieces: list[_Piece], same: bool) -> list[_Piece]:
    return pieces if same else [p.reversed() for p in reversed(pieces)]


def _flat_points(pieces: list[_Piece], tol: float) -> np.ndarray:
    """Les points d'une suite de morceaux, à `tol` de la courbe."""
    out = []
    for p in pieces:
        if len(p.p) == 2:
            pts = p.p
        else:
            pts = p.points(_steps(p, tol))
        out.append(pts if not out else pts[1:])
    return np.vstack(out) if out else np.empty((0, 3))


def _segment(p: _Piece) -> list:
    """Le morceau projeté sur XY, en segments exacts si possible."""
    q = [(float(x), float(y)) for x, y in p.p[:, :2]]
    d = len(q) - 1
    w = p.w
    if d == 1:
        return [Line(q[0], q[1])] if dist(q[0], q[1]) > 1e-12 else []
    if d == 2 and w[0] * w[2] > 0:
        if max(dist(q[0], q[1]), dist(q[1], q[2])) <= 1e-12:
            return []
        return [Conic(q[0], q[1], q[2], float(w[1] / math.sqrt(w[0] * w[2])))]
    if d == 3 and float(np.ptp(w)) <= 1e-9 * max(abs(float(w[0])), 1e-12):
        return [Cubic(q[0], q[1], q[2], q[3])]
    length = float(np.linalg.norm(np.diff(p.p[:, :2], axis=0), axis=1).sum())
    n = int(min(128, max(4, math.ceil(math.sqrt(length / FLAT)))))
    pts = [(float(x), float(y)) for x, y in p.points(n)[:, :2]]
    return [Line(a, b) for a, b in zip(pts, pts[1:]) if dist(a, b) > 1e-12]


def _contours_of(pieces: list[_Piece]) -> list[Contour]:
    """Des contours sur XY ; un saut entre deux morceaux commence un nouveau contour."""
    out, cur = [], []

    def flush():
        if cur:
            closed = dist(cur[0].p0, _end(cur[-1])) <= 1e-3
            out.append(Contour(list(cur), closed))
            cur.clear()
    for p in pieces:
        for s in _segment(p):
            if cur and dist(_end(cur[-1]), s.p0) > 1e-3:
                flush()
            cur.append(s)
    flush()
    return out


def _end(s):
    return s.p3 if isinstance(s, Cubic) else (s.p2 if isinstance(s, Conic) else s.p1)


def _note_skipped(r: _Reader) -> list[str]:
    if not r.skipped:
        return []
    what = ', '.join(f'type {k} × {n}' for k, n in sorted(r.skipped.items()))
    return [f'IGES : éléments non lus : {what}']


def _scale(r: _Reader, box_size: float) -> float:
    """Millimètres par unité. Une pièce démesurée dans l'unité annoncée : le fichier se trompe, on lit des millimètres."""
    if r.unit != 1.0 and box_size * r.unit > MAX_PIECE:
        r.notes.append(f'IGES : unité annoncée « {r.unit_name} » : la pièce ferait {box_size * r.unit / 1000:g} m ; lue en millimètres')
        return 1.0
    return r.unit


def _size(r: _Reader, by_level) -> float:
    top = r.net_size()
    boxes = [c.bbox() for cs in by_level.values() for c in cs]
    if boxes:
        top = max(top, max(b[2] for b in boxes) - min(b[0] for b in boxes), max(b[3] for b in boxes) - min(b[1] for b in boxes))
    return top


def triangles(path) -> np.ndarray:
    """Le maillage des surfaces du fichier, en millimètres (n, 3, 3)."""
    r = _Reader(path)
    k = _scale(r, _size(r, {}))
    r.tol = MESH_TOL / k
    return r.triangles() * k


def read(path) -> Document:
    """Vue de dessus : courbes par niveau, puis hauteurs des faces et silhouette."""
    from ..core.geom import Affine
    from . import mesh3d
    r = _Reader(path)
    name = pathlib.Path(path).name
    by_level = r.free_curves()
    k = _scale(r, _size(r, by_level))
    r.tol = MESH_TOL / k
    tris = r.triangles()
    doc = Document(layers=[], source_path=str(path), source_format='iges')
    from . import plate_note
    doc.plate = plate_note.find_in(''.join(x[:72] for x in r.lines['S']))    # la plaque notée par VectorDrive
    several = len(by_level) > 1
    joined = 0
    scale = Affine.scaling(k)
    tools = ToolColors(doc)                              # une couleur = un outil (F10 › Fichiers)
    for level in sorted(by_level):
        cs, tints, n, _closed = chain_tagged(by_level[level], r.tints[level], JOIN / k)
        joined += n
        items = [Shape(path=Path([c]).transformed(scale) if k != 1.0 else Path([c]), tool=tools.tool(t))
                 for c, t in zip(cs, tints)]
        doc.layers.append(Layer(name=f'IGES niveau {level}' if several else 'IGES', items=items))
    black_first(doc, tools)
    curves = sum(len(cs) for cs in by_level.values())
    if len(tris):
        view = mesh3d.top_view(tris * k, name, flat=r.flat, close=CRACK)
        # des courbes de couleur ont pris des outils : les hauteurs de la vue prennent les suivants
        base = len(tools.made) if any(v != (0, 0, 0) for v in tools.made.values()) else 0
        for L in view.layers:
            L.name = 'IGES ' + L.name
            if base:
                L.tool = (int(L.tool) + base) % 16
                for it in L.items:
                    it.tool = (int(it.tool) + base) % 16
        doc.layers.extend(view.layers)
    doc.report = [f'{name} : {curves} courbe(s), {r.faces} surface(s), {len(tris)} triangles']
    if joined:
        doc.report.append(f'IGES : {joined} raccord(s) entre courbes')
    if r.untrimmed:
        doc.report.append(f'IGES : {r.untrimmed} face(s) à bord illisible, prises entières')
    doc.report += r.notes + _note_skipped(r)
    if not doc.layers:
        doc.layers.append(Layer(name=pathlib.Path(path).stem))
    return doc
