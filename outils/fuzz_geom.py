"""Fuzz géométrique : formes aléatoires (polygones, Bézier, arcs, contours
qui se recoupent, dégénérés) passées dans les opérations de dessin.

    python outils/fuzz_geom.py [--n 2000] [--graine 1]

Vérifie : aucune exception, coordonnées finies, invariants simples (aire
d'un décalage extérieur ≥ aire de départ, tronquer ne rallonge pas…).
Affiche chaque cas fautif avec sa graine pour le rejouer.
"""
from __future__ import annotations

import argparse
import math
import pathlib
import random
import sys
import time
import traceback

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from vectordrive.core import geom  # noqa: E402
from vectordrive.core.geom import Conic, Contour, Cubic, Line, Path  # noqa: E402


def random_contour(rng: random.Random, closed: bool | None = None) -> Contour:
    kind = rng.choice(['poly', 'star', 'bezier', 'arcs', 'mixed', 'tiny', 'spike', 'circle'])
    closed = rng.random() < 0.7 if closed is None else closed
    cx, cy = rng.uniform(-20, 20), rng.uniform(-20, 20)
    scale = 10 ** rng.uniform(-2, 1.5)
    if kind == 'circle':
        return geom.circle((cx, cy), scale)
    if kind == 'star':
        return geom.star((cx, cy), scale, scale * rng.uniform(0.1, 0.9), rng.randint(3, 9), rng.uniform(0, 360))
    n = rng.randint(2, 9)
    pts = [(cx + rng.uniform(-1, 1) * scale, cy + rng.uniform(-1, 1) * scale) for _ in range(n)]
    if kind == 'tiny':
        pts = [(cx + rng.uniform(-1, 1) * 1e-4, cy + rng.uniform(-1, 1) * 1e-4) for _ in range(n)]
    if kind == 'spike':
        a, b = pts[0], pts[1]
        return Contour([Line(a, b), Line(b, (a[0] + 1e-5, a[1]))], True)
    segs = []
    m = len(pts) if closed else len(pts) - 1
    for i in range(m):
        a, b = pts[i], pts[(i + 1) % len(pts)]
        t = kind if kind != 'mixed' else rng.choice(['poly', 'bezier', 'arcs'])
        if t == 'bezier':
            c1 = (a[0] + rng.uniform(-1, 1) * scale, a[1] + rng.uniform(-1, 1) * scale)
            c2 = (b[0] + rng.uniform(-1, 1) * scale, b[1] + rng.uniform(-1, 1) * scale)
            segs.append(Cubic(a, c1, c2, b))
        elif t == 'arcs':
            mid = ((a[0] + b[0]) / 2 + rng.uniform(-1, 1) * scale * 0.5, (a[1] + b[1]) / 2 + rng.uniform(-1, 1) * scale * 0.5)
            segs.append(Conic(a, mid, b, rng.uniform(0.3, 1.0)))
        else:
            segs.append(Line(a, b))
    return Contour(segs, closed)


def random_path(rng: random.Random, closed: bool | None = None) -> Path:
    return Path([random_contour(rng, closed) for _ in range(rng.randint(1, 3))])


def finite(p: Path) -> bool:
    return all(math.isfinite(v) for c in p.contours for s in c.segments for q in s.controls() for v in q)


def run_case(seed: int) -> list[str]:
    """Une forme, toutes les opérations ; renvoie les problèmes trouvés."""
    from vectordrive.core import envelope, fitcurve, hatch, parallel, pathops, punch, shadow, stamp, trim
    from vectordrive.core.document import Shape
    rng = random.Random(seed)
    path = random_path(rng)
    other = random_path(rng, closed=True)
    d = 10 ** rng.uniform(-2, 0.5)
    pb = path.bbox()
    click = (rng.uniform(pb[0], pb[2]), rng.uniform(pb[1], pb[3])) if pb else (0.0, 0.0)
    problems = []

    def check(name, fn, test=None):
        try:
            out = fn()
        except Exception:
            problems.append(f'{name}: exception\n' + traceback.format_exc(limit=4))
            return None
        paths = out if isinstance(out, list) else [out]
        for x in paths:
            if isinstance(x, Path) and not finite(x):
                problems.append(f'{name}: coordonnée non finie')
        if test is not None and out is not None:
            msg = test(out)
            if msg:
                problems.append(f'{name}: {msg}')
        return out

    others = [s for c in other.contours for s in c.segments]
    check('trim', lambda: trim.trim(path, others, click),
          lambda r: 'rallongé' if r is not None and r.length() > path.length() + 1e-6 else None)
    check('extend', lambda: trim.extend(path, others, click))
    check('punch', lambda: punch.cut(path, other, False, False))
    check('clip', lambda: punch.cut(path, other, False, True))
    check('punch surfaces', lambda: punch.cut(path, other, True, False))
    for c in path.contours:
        check('parallel', lambda c=c: [Path([x]) for x in parallel.parallel(c, d)])
        check('remove_loops', lambda c=c: Path([parallel.remove_loops(c)]),
              lambda r: 'rallongé' if r.length() > c.length() + 1e-6 else None)
    check('double_line', lambda: parallel.double_line(path, d, rng.choice(['open', 'butt', 'round'])))
    closed = Path([c for c in path.contours if c.closed])
    if closed.contours:
        a0 = pathops.area(pathops.normalize(closed))          # région pair-impair

        def grown(r):
            res, _ = r
            a1 = pathops.area(res)
            return f'aire {a1:.6f} < {a0:.6f}' if a1 < a0 - 1e-6 * max(1.0, a0) else None
        check('offset_checked', lambda: parallel.offset_checked(closed, d), grown)
        check('hatch', lambda: hatch.hatch_path(closed, hatch.HatchSpec(spacing=max(d, 0.05), angle=rng.uniform(0, 180))))
        check('shadow', lambda: shadow.shadow_path(closed, shadow.ShadowSpec(rng.choice(shadow.KINDS), rng.uniform(0, 360), d)))
        check('stamp', lambda: stamp.region(closed, stamp.StampSpec(shoulder=rng.choice([0, d / 4]))))
    check('envelope', lambda: envelope.build([Shape(path=path)], envelope.EnvelopeSpec(rng.choice(envelope.KINDS),
                                                                                     rng.uniform(-60, 60))))
    check('approximate', lambda: fitcurve.approximate(path, max(d / 10, 1e-3)))
    check('segment', lambda: fitcurve.segment(path, max(d / 10, 1e-3), rng.choice([0, d])))
    return problems


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--n', type=int, default=2000)
    ap.add_argument('--graine', type=int, default=1)
    a = ap.parse_args(argv)
    bad = 0
    t0 = time.perf_counter()
    worst = (0.0, None)
    for k in range(a.n):
        seed = a.graine * 1_000_003 + k
        t = time.perf_counter()
        probs = run_case(seed)
        dt = time.perf_counter() - t
        if dt > worst[0]:
            worst = (dt, seed)
        if dt > 2:
            print(f'  lent : graine {seed}, {dt:.1f} s', flush=True)
        if probs:
            bad += 1
            print(f'— graine {seed} —')
            for p in probs:
                print('  ' + p.rstrip().replace('\n', '\n  '))
    print(f'{a.n} cas, {bad} fautifs, {time.perf_counter() - t0:.0f} s ; le plus lent : {worst[0]:.2f} s (graine {worst[1]})')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
