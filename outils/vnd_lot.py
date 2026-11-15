"""Contrôle d'un lot de VND/GVT : lecture, textes par police (polices
absentes du poste), objets non lus, réécriture identique sans modification.

    python outils/vnd_lot.py DOSSIER [DOSSIER…]

Lecture seule : rien n'est écrit sur le disque.
"""
from __future__ import annotations

import collections
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from vectordrive.core import fonts  # noqa: E402
from vectordrive.core.document import Text  # noqa: E402
from vectordrive.io import registry, vnd_write  # noqa: E402


def main(argv=None) -> int:
    folders = [pathlib.Path(a) for a in (argv if argv is not None else sys.argv[1:])]
    files = sorted(p for d in folders for p in d.rglob('*') if p.suffix.lower() in ('.vnd', '.gvt'))
    stats = collections.Counter()
    per_font = collections.Counter()
    missing = collections.Counter()
    for f in files:
        t = time.perf_counter()
        try:
            doc = registry.open_document(str(f))
        except Exception as ex:
            stats['illisibles'] += 1
            print(f'ILLISIBLE {f}: {ex}')
            continue
        texts = [x for x in doc.iter_leaves() if isinstance(x, Text)]
        for x in texts:
            per_font[x.font] += 1
            if not fonts.is_available(x.font):
                missing[x.font] += 1
        partial = doc.extra.get('vnd_partial')
        state = 'partiel' if partial else '?'
        if f.suffix.lower() == '.vnd' and not partial:
            try:
                out, _ = vnd_write.write_document(doc)
                state = 'identique' if out == f.read_bytes() else 'reconstruit'
            except Exception as ex:
                state = f'écriture impossible ({type(ex).__name__})'
        stats[state] += 1
        print(f'{f.name[:50]:50} {time.perf_counter() - t:5.1f} s  {len(texts):4} textes  {state}'
              + (f'  ({partial[:60]})' if partial else ''))
    print('\nBilan :', dict(stats))
    print('Textes par police :', per_font.most_common())
    if missing:
        print('Polices absentes du poste (remplacées) :', missing.most_common())
    return 0


if __name__ == '__main__':
    sys.exit(main())
