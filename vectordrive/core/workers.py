"""Fils de calcul partagés : les opérations de géométrie de shapely (GEOS)
libèrent le verrou de Python, plusieurs retraits d'une même région se
calculent donc vraiment en même temps sur les cœurs du poste.

Nombre de fils : réglage F10 › Performances (`perf/fils`, 0 = automatique :
cœurs − 1), appliqué par `set_count`. Chaque tâche voit l'avancement et
l'annulation du calcul qui l'a lancée (core.progress).
"""
from __future__ import annotations

import contextvars
import os
import threading
from concurrent.futures import ThreadPoolExecutor

_COUNT = 0                      # 0 : automatique
_POOL: ThreadPoolExecutor | None = None
_POOL_SIZE = 0
_LOCK = threading.Lock()


def auto_count() -> int:
    return max(1, (os.cpu_count() or 2) - 1)


def count() -> int:
    """Fils de calcul en service."""
    return _COUNT if _COUNT > 0 else auto_count()


def set_count(n: int) -> None:
    """Nombre de fils (0 : automatique) ; le réservoir est refait au prochain usage."""
    global _COUNT
    _COUNT = max(0, int(n or 0))


def _pool() -> ThreadPoolExecutor:
    global _POOL, _POOL_SIZE
    n = count()
    with _LOCK:
        if _POOL is None or _POOL_SIZE != n:
            if _POOL is not None:
                _POOL.shutdown(wait=False)
            _POOL = ThreadPoolExecutor(max_workers=n, thread_name_prefix='vd-geometrie')
            _POOL_SIZE = n
        return _POOL


def pmap(fn, items) -> list:
    """[fn(x) for x in items], en parallèle sur les fils de calcul (dans
    l'ordre). Un seul fil, un seul élément, ou appel depuis un fil de calcul
    (pas d'imbrication) : à la suite, sans réservoir."""
    items = list(items)
    if len(items) < 2 or count() < 2 or threading.current_thread().name.startswith('vd-geometrie'):
        return [fn(x) for x in items]
    pool = _pool()
    futures = [pool.submit(contextvars.copy_context().run, fn, x) for x in items]
    try:
        return [f.result() for f in futures]
    except BaseException:
        for f in futures:
            f.cancel()
        raise


# --- processus : calculs en Python (le verrou de Python n'en laisse passer qu'un par processus) ---------

#: éléments restants au moins pour passer sur plusieurs processus
PARALLEL_MIN = 4
#: durée estimée du reste (s) au-delà de laquelle il passe sur plusieurs processus (chaque processus
#: charge VectorDrive : 1 à 2 s ; un petit travail reste à la suite, sans surcoût)
SWITCH_S = 5.0
#: processus au plus (environ 150 Mo chacun) ; réglage F10 › Performances (perf/processus, 0 : automatique)
PROCESS_MAX = 8
_PROCESSES = 0


def set_processes(n: int) -> None:
    """Processus au plus pour les longs travaux (0 : automatique, jusqu'à PROCESS_MAX)."""
    global _PROCESSES
    _PROCESSES = max(0, int(n or 0))


def process_limit() -> int:
    return _PROCESSES if _PROCESSES > 0 else min(count(), PROCESS_MAX)


def processes(n_items: int, min_items: int | None = None) -> int:
    """Processus pour `n_items` éléments restants : 1 (à la suite) en dessous
    de `min_items`, sinon la limite réglée (ou automatique), bornée."""
    if n_items < (PARALLEL_MIN if min_items is None else min_items):
        return 1
    return max(1, min(process_limit(), n_items // 2))


def exit_with_parent() -> None:
    """Dans un processus de calcul : s'arrêter dès que le processus parent
    disparaît (application fermée brutalement, serveur de vignettes arrêté) —
    sinon il resterait en mémoire, orphelin."""
    import multiprocessing
    from multiprocessing.connection import wait
    parent = multiprocessing.parent_process()
    if parent is None:
        return

    def watch():
        wait([parent.sentinel])
        os._exit(0)
    threading.Thread(target=watch, daemon=True, name='vd-parent').start()


def terminate_pool(pool) -> None:
    """Processus d'un réservoir arrêtés tout de suite (sortie du programme)."""
    if pool is None:
        return
    for p in list(getattr(pool, '_processes', {}).values()):
        try:
            p.terminate()
        except Exception:                                # noqa: BLE001 — déjà parti
            pass
    pool.shutdown(wait=False, cancel_futures=True)


def _start_process(plugins: bool) -> None:
    """Processus de calcul : formats et lecteurs des plugins comme dans l'application."""
    from .. import winpaths  # noqa: F401 — lecteur verrouillé : « absent » comme dans l'application
    exit_with_parent()
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    if plugins:
        from .. import plugins as PL
        PL.load()


def _apply_chunk(fn, jobs: list) -> list:
    return [fn(*job) for job in jobs]


def adaptive_map(fn, jobs: list, *, text: str = 'Objet {0} sur {1}', switch_s: float | None = None,
                 min_items: int | None = None) -> list:
    """[fn(*job) for job in jobs], dans l'ordre : à la suite tant que le reste
    s'annonce court ; au-delà de `switch_s` estimées, le reste sur des
    processus (avancement suivi, Annuler entre deux paquets). `fn` et les
    `jobs` doivent pouvoir passer d'un processus à l'autre (fonction du
    module, données simples ou objets du dessin)."""
    import time
    from . import progress
    switch_s = SWITCH_S if switch_s is None else switch_s
    out = []
    t0 = time.perf_counter()
    for i, job in enumerate(jobs):
        left = len(jobs) - i
        if i and (time.perf_counter() - t0) / i * left > switch_s and processes(left, min_items) > 1:
            return out + run_pool(fn, jobs[i:], offset=i, total=len(jobs), text=text, min_items=min_items)
        progress.step(i, len(jobs), text)
        out.append(fn(*job))
    return out


def run_pool(fn, jobs: list, *, offset: int = 0, total: int | None = None, text: str = 'Objet {0} sur {1}',
             min_items: int | None = None) -> list:
    """[fn(*job) for job in jobs] sur des processus, dans l'ordre (paquets de
    plusieurs éléments : peu d'échanges pour de petits calculs)."""
    import multiprocessing
    from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
    from . import progress
    from .. import plugins as PL
    total = total or len(jobs)
    n = max(1, processes(len(jobs), min_items))
    size = max(1, len(jobs) // (n * 8))
    chunks = [jobs[k:k + size] for k in range(0, len(jobs), size)]
    out: list = [None] * len(chunks)
    ctx = multiprocessing.get_context('spawn')
    with ProcessPoolExecutor(n, mp_context=ctx, initializer=_start_process,
                             initargs=(bool(PL.REGISTRY.plugins),)) as ex:
        futures = {ex.submit(_apply_chunk, fn, c): k for k, c in enumerate(chunks)}
        pending = set(futures)
        try:
            while pending:
                finished = sum(len(chunks[futures[f]]) for f in futures if f not in pending)
                progress.step(offset + finished, total, text)
                ready, pending = wait(pending, timeout=0.2, return_when=FIRST_COMPLETED)
                for f in ready:
                    out[futures[f]] = f.result()
        except BaseException:
            ex.shutdown(wait=False, cancel_futures=True)
            raise
    return [r for part in out for r in part]
