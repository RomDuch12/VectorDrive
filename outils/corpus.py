"""Ouvre tous les fichiers pris en charge sous des dossiers donnés et
résume : réussites et échecs par format, erreurs groupées, fichiers lents.

    python outils/corpus.py DOSSIER [autre dossier…] [--max-mo 50]
                            [--vdz]  (relecture après enregistrement natif)

Rien n'est modifié : lecture seule (l'option --vdz écrit dans un dossier
temporaire).
"""
from __future__ import annotations

import argparse
import collections
import pathlib
import sys
import tempfile
import time
import traceback

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('dossiers', nargs='+')
    ap.add_argument('--max-mo', type=float, default=50.0)
    ap.add_argument('--vdz', action='store_true')
    ap.add_argument('--exclure', action='append', default=[], help='fragment de chemin à ignorer')
    a = ap.parse_args(argv)
    from vectordrive.io import native, registry
    exts = {e: f.key for f in registry.FORMATS if f.reader for e in f.extensions}
    ok = collections.Counter()
    ko = collections.Counter()
    errors = collections.defaultdict(list)
    slow = []
    empty = collections.Counter()
    for d in a.dossiers:
        for p in pathlib.Path(d).rglob('*'):
            if not p.is_file() or p.suffix.lower() not in exts:
                continue
            if any(x.lower() in str(p).lower() for x in a.exclure):
                continue
            if p.stat().st_size > a.max_mo * 1e6:
                continue
            key = exts[p.suffix.lower()]
            t = time.perf_counter()
            try:
                doc = registry.open_document(p)
                st = doc.stats()
                if a.vdz:
                    with tempfile.TemporaryDirectory() as tmp:
                        f = pathlib.Path(tmp) / 'x.vdz'
                        native.write(doc, f)
                        back = registry.open_document(f)
                        if back.stats()['contours'] != st['contours']:
                            raise AssertionError(f'VDZ : {back.stats()} au lieu de {st}')
                ok[key] += 1
                if st['objets'] == 0:
                    empty[key] += 1
            except Exception as ex:
                ko[key] += 1
                tb = traceback.extract_tb(ex.__traceback__)[-1]
                where = f'{pathlib.Path(tb.filename).name}:{tb.lineno}'
                errors[(key, type(ex).__name__, str(ex)[:90], where)].append(p)
            dt = time.perf_counter() - t
            slow.append((dt, p))
    print('format     lus   échecs  vides')
    for key in sorted(set(ok) | set(ko)):
        print(f'{key:8s} {ok[key]:6d} {ko[key]:7d} {empty[key]:6d}')
    print('\nÉchecs regroupés :')
    for (key, typ, msg, where), files in sorted(errors.items(), key=lambda kv: -len(kv[1])):
        print(f'  {len(files):4d} × {key} {typ} @ {where} : {msg}')
        for f in files[:2]:
            print(f'         {f}')
    print('\nLes plus lents :')
    for dt, p in sorted(slow, reverse=True)[:8]:
        print(f'  {dt:6.2f} s  {p}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
