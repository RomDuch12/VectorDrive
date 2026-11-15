"""Suite des essais répartie sur plusieurs processus (2 à 3 fois plus vite
qu'un seul ``unittest discover``) : les fichiers ``tests/test_*.py`` sont
partagés en morceaux, un processus par morceau ; résumé et premières
erreurs à la fin ; code de sortie 1 au moindre échec. Les fichiers
temporaires des essais vont dans un dossier à part, supprimé à la fin
(sinon des milliers de dossiers s'accumulaient dans le Temp de Windows).

    python outils/tests_paralleles.py [--processus N]
    python outils/tests_paralleles.py --morceau K N     (un morceau : usage interne)
"""
from __future__ import annotations

import os
import pathlib
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def modules() -> list[str]:
    return sorted(f'tests.{p.stem}' for p in (ROOT / 'tests').glob('test_*.py'))


def run_piece(k: int, n: int) -> int:
    """Les modules k, k + n, k + 2n… dans ce processus."""
    sys.path.insert(0, str(ROOT))
    os.chdir(ROOT)
    names = modules()[k::n]
    suite = unittest.defaultTestLoader.loadTestsFromNames(names)
    res = unittest.TextTestRunner(stream=sys.stderr, verbosity=1).run(suite)
    return 0 if res.wasSuccessful() else 1


def main(argv=None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args[:1] == ['--morceau']:
        return run_piece(int(args[1]), int(args[2]))
    if hasattr(sys.stdout, 'reconfigure'):            # console cp1252 : un échec cité ne plante plus
        sys.stdout.reconfigure(errors='replace')
    n = 4
    if args[:1] == ['--processus']:
        n = max(1, int(args[1]))
    import shutil
    scratch = tempfile.mkdtemp(prefix='vd_essais_')     # Temp des essais, supprimé à la fin
    env = dict(os.environ, QT_QPA_PLATFORM='offscreen', PYTHONDONTWRITEBYTECODE='1',
               TMP=scratch, TEMP=scratch, TMPDIR=scratch)
    out_dir = pathlib.Path(tempfile.mkdtemp(prefix='vd_tests_'))
    t0 = time.time()
    procs = []
    for k in range(n):
        log = open(out_dir / f'morceau{k}.txt', 'w', encoding='utf-8', errors='replace')
        procs.append((subprocess.Popen([sys.executable, str(pathlib.Path(__file__).resolve()), '--morceau', str(k),
                                        str(n)], cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT), log))
    failed = 0
    for k, (p, log) in enumerate(procs):
        code = p.wait()
        log.close()
        text = (out_dir / f'morceau{k}.txt').read_text(encoding='utf-8', errors='replace')
        summary = [ln for ln in text.splitlines() if ln.startswith(('Ran ', 'OK', 'FAILED'))]
        print(f'morceau {k + 1}/{n} : ' + ' ; '.join(summary[-2:]))
        if code:
            failed += 1
            for block in text.split('=' * 70)[1:4]:      # les premières erreurs
                print('=' * 70 + block.rstrip()[:3000])
    print(f'{n} morceaux en {time.time() - t0:.0f} s : ' + ('ÉCHEC' if failed else 'OK'))
    shutil.rmtree(scratch, ignore_errors=True)
    if not failed:
        shutil.rmtree(out_dir, ignore_errors=True)        # en cas d'échec, les journaux restent
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
