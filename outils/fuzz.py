"""Fichiers abîmés : chaque lecteur doit échouer proprement (exception),
vite, sans boucler ni réclamer des gigaoctets.

    python outils/fuzz.py [--n 200] [--timeout 10] fichier1 fichier2 …

Pour chaque fichier, `n` variantes reproductibles (graine = rang) :
octets inversés ou écrasés, fichier tronqué, morceau dupliqué, compteurs
32 bits gonflés. Les variantes sont lues dans un processus fils ; une
variante qui dépasse `--timeout` secondes ou fait tomber le processus est
signalée (et gardée dans `tests/_sorties/fuzz/` pour reproduire).
"""
from __future__ import annotations

import argparse
import os
import pathlib
import random
import subprocess
import sys
import tempfile
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]


def mutate(data: bytes, seed: int) -> bytes:
    rnd = random.Random(seed)
    b = bytearray(data)
    kind = seed % 5
    if not b:
        return bytes(b)
    if kind == 0:                                        # bits inversés
        for _ in range(rnd.randint(1, 8)):
            i = rnd.randrange(len(b))
            b[i] ^= 1 << rnd.randrange(8)
    elif kind == 1:                                      # octets écrasés
        for _ in range(rnd.randint(1, 4)):
            i = rnd.randrange(len(b))
            n = rnd.randint(1, 16)
            b[i:i + n] = bytes(rnd.randrange(256) for _ in range(n))
    elif kind == 2:                                      # tronqué
        b = b[:rnd.randrange(len(b))]
    elif kind == 3:                                      # morceau dupliqué
        i = rnd.randrange(len(b))
        j = min(len(b), i + rnd.randint(1, 4096))
        b[j:j] = b[i:j]
    else:                                                # compteur gonflé
        for _ in range(rnd.randint(1, 3)):
            i = rnd.randrange(max(1, len(b) - 4)) & ~3
            b[i:i + 4] = rnd.choice((b'\xff\xff\xff\x7f', b'\x00\x00\x00\x40', b'\xff\xff\xff\xff',
                                     b'\x00\x00\x10\x00'))
    return bytes(b)


def child(cases_file: str) -> int:
    """Lit les variantes une à une et écrit « START i » / « END i état »."""
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    sys.path.insert(0, str(ROOT))
    from vectordrive.io import registry
    lines = pathlib.Path(cases_file).read_text(encoding='utf-8').splitlines()
    tmp = pathlib.Path(tempfile.mkdtemp(prefix='vd_fuzz_'))
    for line in lines:
        i, seed, path = line.split('\t')
        src = pathlib.Path(path)
        f = tmp / ('v' + src.suffix)
        f.write_bytes(mutate(src.read_bytes(), int(seed)))
        print(f'START {i}', flush=True)
        t = time.perf_counter()
        try:
            registry.open_document(f)
            state = 'ok'
        except MemoryError:
            state = 'MEMOIRE'
        except RecursionError:
            state = 'RECURSION'
        except Exception as ex:                          # échec propre attendu
            state = 'erreur ' + type(ex).__name__
        print(f'END {i} {time.perf_counter() - t:.2f} {state}', flush=True)
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('files', nargs='*')
    ap.add_argument('--n', type=int, default=200)
    ap.add_argument('--timeout', type=float, default=10.0)
    ap.add_argument('--child')
    a = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if a.child:
        return child(a.child)
    cases = [(len_i, seed, f) for len_i, (f, seed) in
             enumerate((f, s) for f in a.files for s in range(a.n))]
    out_dir = ROOT / 'tests' / '_sorties' / 'fuzz'
    pending = list(cases)
    problems = []
    stats: dict[str, int] = {}
    slow = 0.0
    while pending:
        with tempfile.NamedTemporaryFile('w', suffix='.txt', delete=False, encoding='utf-8') as cf:
            cf.write('\n'.join(f'{i}\t{s}\t{f}' for i, s, f in pending))
        proc = subprocess.Popen([sys.executable, __file__, '--child', cf.name], stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL, text=True, encoding='utf-8')
        current, started = None, time.time()
        done = set()
        import threading
        lines: list[str] = []
        th = threading.Thread(target=lambda: [lines.append(x) for x in proc.stdout], daemon=True)
        th.start()
        k = 0
        while True:
            while k < len(lines):
                ln = lines[k].split()
                k += 1
                if ln[0] == 'START':
                    current, started = int(ln[1]), time.time()
                elif ln[0] == 'END':
                    i, dt, state = int(ln[1]), float(ln[2]), ' '.join(ln[3:])
                    done.add(i)
                    stats[state.split()[0]] = stats.get(state.split()[0], 0) + 1
                    slow = max(slow, dt)
                    if state in ('MEMOIRE', 'RECURSION') or dt > a.timeout / 2:
                        problems.append((cases[i], f'{state} en {dt:.1f} s'))
                    current = None
            if proc.poll() is not None and k >= len(lines) and not th.is_alive():
                break
            if current is not None and time.time() - started > a.timeout:
                proc.kill()
                problems.append((cases[current], f'bloqué plus de {a.timeout:g} s'))
                done.add(current)
                break
            time.sleep(0.05)
        proc.wait()
        os.unlink(cf.name)
        if current is not None and current not in done:            # processus tombé
            problems.append((cases[current], f'processus arrêté (code {proc.returncode})'))
            done.add(current)
        pending = [c for c in pending if c[0] not in done]
    for (i, seed, f), why in problems:
        out_dir.mkdir(parents=True, exist_ok=True)
        keep = out_dir / f'{pathlib.Path(f).stem}_{seed}{pathlib.Path(f).suffix}'
        keep.write_bytes(mutate(pathlib.Path(f).read_bytes(), seed))
        print(f'PROBLÈME {pathlib.Path(f).name} graine {seed} : {why} -> {keep.name}')
    print(f'{len(cases)} variantes : ' + ', '.join(f'{k} {v}' for k, v in sorted(stats.items()))
          + f' ; la plus lente {slow:.2f} s ; {len(problems)} problème(s)')
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main())
