"""Courbe lisse approchant un contour (demande du 18/11 : « approximation courbe Cinfini d'un contour (parametrable
user) »).

Le contour est parcouru à pas régulier ; ses coordonnées, vues comme une fonction de la longueur parcourue, passent par
un filtre passe-bas gaussien : la courbe filtrée est indéfiniment dérivable (C∞). Elle est rendue en B-spline cubique
uniforme, écrite en courbes de Bézier : tangente **et courbure** y sont continues partout (C2), sans aucun coin — une
courbe de Bézier ne peut pas faire mieux d'un morceau à l'autre.

- **longueur de lissage** (mm de tracé) : un détail dont le tracé a cette longueur est réduit de moitié ; plus court,
  il s'efface. La longueur se compte le long du contour : une pointe étroite mais haute a un tracé long et résiste
  plus qu'une ondulation de même largeur. 0 ou moins : le contour est rendu tel quel ;
- **netteté** (1 à 4) : 1, un lissage doux (gaussien) ; au-delà, la coupure est plus franche — la forme d'ensemble est
  mieux gardée, mais de légères ondulations apparaissent près des coins vifs ;
- **écart de tracé** (mm) : l'écart toléré entre la courbe filtrée et son tracé en Bézier ; plus petit, plus de
  morceaux ;
- **contour ouvert** : ses deux bouts ne bougent pas ; **contour fermé** : lissé tout le tour, sans point de départ
  visible, et sans rétrécir — sa forme d'ensemble (sa première harmonique : l'ellipse qui l'approche) est gardée
  entière, même quand la longueur de lissage dépasse le contour.

`smooth_contour(…, report=)` note l'écart maxi entre le contour d'origine et la courbe lisse."""
from __future__ import annotations

import math

import numpy as np

from .geom import Contour, Cubic, Path

#: points par morceau de Bézier pour le filtrage et les contrôles
FINE = 8
#: morceaux : au moins, au plus (par contour)
MIN_SPANS, MAX_SPANS = 8, 32768
#: un morceau au départ pour cette fraction de la longueur de lissage ; resserré tant que l'écart de tracé dépasse
SPAN_RATIO = 3.0
#: suréchantillonnage avant moyenne, quand le contour est trop long pour le pas voulu (pas de repliement)
OVERSAMPLE_MAX = 8


def _polyline(c: Contour, tol: float) -> np.ndarray:
    pts = [c.segments[0].start]
    for s in c.segments:
        pts.extend(s.flatten(tol))                       # sans le départ : c'est l'arrivée du précédent
    P = np.asarray(pts, float)
    if c.closed and np.hypot(*(P[-1] - P[0])) > 1e-9:
        P = np.vstack([P, P[0]])
    keep = np.r_[True, np.hypot(*np.diff(P, axis=0).T) > 1e-12]
    return P[keep]


def _at(P: np.ndarray, s: np.ndarray, at: np.ndarray) -> np.ndarray:
    return np.column_stack([np.interp(at, s, P[:, 0]), np.interp(at, s, P[:, 1])])


def sample(P: np.ndarray, n: int, closed: bool, want_step: float) -> tuple:
    """`n` points à pas régulier le long de la ligne brisée P (fermé : un tour, le premier point non répété ; ouvert :
    bouts compris) ; rend (points, longueur). Si le pas obtenu dépasse `want_step`, chaque point est la moyenne de
    points plus serrés autour de lui : les détails plus fins que le pas ne se replient pas."""
    d = np.hypot(*np.diff(P, axis=0).T)
    s = np.r_[0.0, np.cumsum(d)]
    total = float(s[-1])
    step = total / n if closed else total / max(n - 1, 1)
    at = np.arange(n) * step
    m = int(min(OVERSAMPLE_MAX, max(1, math.ceil(step / max(want_step, 1e-12)))))
    if m <= 1:
        return _at(P, s, at), total
    acc = np.zeros((n, 2))
    for k in range(m):                                   # moyenne sur un pas, centrée sur le point
        off = (k + 0.5) / m - 0.5
        pos = at + off * step
        pos = np.mod(pos, total) if closed else np.clip(pos, 0.0, total)
        acc += _at(P, s, pos)
    Q = acc / m
    if not closed:
        Q[0], Q[-1] = P[0], P[-1]
    return Q, total


def gain(freq: np.ndarray, length: float, sharpness: float = 1.0) -> np.ndarray:
    """Le gain du filtre à la fréquence `freq` (cycles par mm) : 1 pour la forme d'ensemble, 1/2 à la longueur d'onde
    `length`, puis une chute plus rapide que toute puissance (la courbe filtrée est C∞)."""
    if length <= 0:
        return np.ones_like(freq, dtype=float)
    n = max(1.0, min(4.0, float(sharpness)))
    return np.exp(-math.log(2.0) * (np.abs(freq) * length) ** (2.0 * n))


def _filtered(Q: np.ndarray, total: float, closed: bool, length: float, sharpness: float) -> np.ndarray:
    """Les points filtrés (mêmes rangs que Q)."""
    n = len(Q)
    if closed:
        z = Q[:, 0] + 1j * Q[:, 1]
        f = np.fft.fftfreq(n, d=total / n)
        g = gain(f, length, sharpness)
        g1 = float(gain(np.array([1.0 / total]), length, sharpness)[0])
        if g1 > 0:                                       # la première harmonique gardée entière : pas de rétrécissement
            g = np.minimum(1.0, g / g1)
        else:                                            # lissage démesuré : la moyenne et la première harmonique seules
            g = (np.abs(np.round(f * total)) <= 1).astype(float)
        out = np.fft.ifft(np.fft.fft(z) * g)
        return np.column_stack([out.real, out.imag])
    t = np.linspace(0.0, 1.0, n)[:, None]
    trend = Q[0] + (Q[-1] - Q[0]) * t                    # la corde : les bouts restent en place
    q = Q - trend
    ext = np.vstack([q, -q[-2:0:-1]])                    # prolongement impair : période de deux longueurs
    z = ext[:, 0] + 1j * ext[:, 1]
    f = np.fft.fftfreq(len(z), d=total / (n - 1))
    out = np.fft.ifft(np.fft.fft(z) * gain(f, length, sharpness))[:n]
    R = np.column_stack([out.real, out.imag]) + trend
    R[0], R[-1] = Q[0], Q[-1]
    return R


def _bspline_coefs(y: np.ndarray) -> np.ndarray:
    """Les coefficients de la B-spline cubique uniforme périodique qui passe par les points `y` (complexes) : la
    relation y[j] = (c[j−1] + 4 c[j] + c[j+1]) / 6 inversée en fréquence."""
    n = len(y)
    k = np.arange(n)
    return np.fft.ifft(np.fft.fft(y) / ((4.0 + 2.0 * np.cos(2.0 * np.pi * k / n)) / 6.0))


def _spans(c: np.ndarray, count: int, wrap: bool) -> np.ndarray:
    """Les points de contrôle de Bézier (count × 4, complexes) des morceaux 0…count−1 de la B-spline de coefficients
    `c` (périodiques)."""
    n = len(c)
    j = np.arange(count)
    cm, c0, c1, c2 = c[(j - 1) % n], c[j % n], c[(j + 1) % n], c[(j + 2) % n]
    return np.column_stack([(cm + 4 * c0 + c1) / 6, (2 * c0 + c1) / 3, (c0 + 2 * c1) / 3, (c0 + 4 * c1 + c2) / 6])


def _bezier_points(B: np.ndarray, fine: int) -> np.ndarray:
    """Les points des morceaux aux paramètres k / fine (k = 0…fine−1), morceau après morceau (complexes)."""
    t = (np.arange(fine) / fine)[None, :]
    p0, p1, p2, p3 = (B[:, i][:, None] for i in range(4))
    u = 1 - t
    return (u ** 3 * p0 + 3 * u ** 2 * t * p1 + 3 * u * t ** 2 * p2 + t ** 3 * p3).ravel()


def _fit(P: np.ndarray, closed: bool, length: float, sharpness: float, spans: int) -> tuple:
    """(points de contrôle des morceaux, points filtrés fins, points fins du tracé, points d'origine fins)."""
    if closed:
        Q, total = sample(P, spans * FINE, True, length / (SPAN_RATIO * FINE))
        R = _filtered(Q, total, True, length, sharpness)
        z = R[:, 0] + 1j * R[:, 1]
        B = _spans(_bspline_coefs(z[::FINE]), spans, True)
        return B, z, _bezier_points(B, FINE), Q[:, 0] + 1j * Q[:, 1]
    n = spans * FINE + 1
    Q, total = sample(P, n, False, length / (SPAN_RATIO * FINE))
    R = _filtered(Q, total, False, length, sharpness)
    t = np.linspace(0.0, 1.0, n)
    a, b = complex(*Q[0]), complex(*Q[-1])
    q = (R[:, 0] + 1j * R[:, 1]) - (a + (b - a) * t)     # l'écart à la corde, nul aux deux bouts
    knots = q[::FINE]                                    # spans + 1 nœuds
    ext = np.r_[knots, -knots[-2:0:-1]]                  # impair : la B-spline passe par les bouts, sans les bouger
    B = _spans(_bspline_coefs(ext), spans, True)
    j = np.arange(spans)[:, None]
    lin = a + (b - a) * (j + np.array([0.0, 1 / 3, 2 / 3, 1.0])[None, :]) / spans    # la corde, exacte en Bézier
    B = B + lin
    B[0, 0], B[-1, 3] = a, b
    z = R[:, 0] + 1j * R[:, 1]
    return B, z[:-1], _bezier_points(B, FINE), (Q[:, 0] + 1j * Q[:, 1])[:-1]


def _nearest(a: np.ndarray, b: np.ndarray, window: int, closed: bool) -> float:
    """Le plus grand écart des points `a` à la ligne des points `b` (mêmes rangs), cherché à ±`window` rangs."""
    n = len(a)
    best = np.full(n, np.inf)
    for off in range(-window, window + 1):
        if closed:
            d = np.abs(a - np.roll(b, -off))
        else:
            idx = np.clip(np.arange(n) + off, 0, n - 1)
            d = np.abs(a - b[idx])
        best = np.minimum(best, d)
    return float(best.max()) if n else 0.0


def smooth_contour(c: Contour, length: float = 2.0, sharpness: float = 1.0, tol: float = 0.01,
                   report: dict | None = None) -> Contour:
    """La courbe lisse du contour, en courbes de Bézier (B-spline cubique : courbure continue). Rendu tel quel : un
    contour vide, de moins de trois points ou de longueur nulle, ou une longueur de lissage nulle. `report` (un
    dictionnaire) : sa clé 'deviation' reçoit le plus grand écart (mm) du contour d'origine à la courbe lisse."""
    if not c.segments or length <= 0:
        return c
    tol = max(1e-4, float(tol))
    P = _polyline(c, tol / 8)
    if len(P) < (4 if c.closed else 3):
        return c
    total = float(np.sum(np.hypot(*np.diff(P, axis=0).T)))
    if total <= 1e-9:
        return c
    spans = int(min(MAX_SPANS, max(MIN_SPANS, math.ceil(total / (length / SPAN_RATIO)))))
    while True:
        B, z, drawn, orig = _fit(P, c.closed, float(length), sharpness, spans)
        err = float(np.max(np.abs(drawn - z))) if len(z) else 0.0
        if err <= tol or spans * 2 > MAX_SPANS:
            break
        spans *= 2
    segs = [Cubic((b[0].real, b[0].imag), (b[1].real, b[1].imag), (b[2].real, b[2].imag), (b[3].real, b[3].imag))
            for b in B]
    if c.closed:                                         # fermée exactement : le dernier point est le premier
        last = segs[-1]
        segs[-1] = Cubic(last.p0, last.p1, last.p2, segs[0].p0)
    if report is not None:
        dev = _nearest(orig, drawn, 3 * FINE, c.closed)
        report['deviation'] = max(float(report.get('deviation', 0.0)), dev)
    return Contour(segs, c.closed)


def smooth(path: Path, length: float = 2.0, sharpness: float = 1.0, tol: float = 0.01,
           report: dict | None = None) -> Path:
    return Path([smooth_contour(c, length, sharpness, tol, report) for c in path.contours])


def deviation(before: Path, after: Path, tol: float = 0.01) -> float:
    """L'écart maxi (mm) des points du contour d'origine à la courbe lisse (contour par contour, dans l'ordre) ;
    mesure directe, pour les contrôles (la commande prend celui de `smooth_contour`, plus rapide)."""
    worst = 0.0
    for a, b in zip(before.contours, after.contours):
        if not a.segments or not b.segments:
            continue
        A, B = _polyline(a, tol), _polyline(b, tol)
        if len(A) < 1 or len(B) < 2:
            continue
        seg0, seg1 = B[:-1], B[1:]
        d = seg1 - seg0
        L2 = np.maximum(np.einsum('ij,ij->i', d, d), 1e-24)
        for i in range(0, len(A), 32):                  # par paquets : tous les points, mémoire bornée
            p = A[i:i + 32][:, None, :]
            t = np.clip(np.einsum('kij,ij->ki', p - seg0[None], d) / L2, 0.0, 1.0)
            q = seg0[None] + d[None] * t[:, :, None]
            worst = max(worst, float(np.max(np.min(np.hypot(q[:, :, 0] - p[:, :, 0], q[:, :, 1] - p[:, :, 1]),
                                                   axis=1))))
    return worst
