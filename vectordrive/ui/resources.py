"""Ressources de la séance (F10 › Performances) : mémoire du processus et
des mémoires de VectorDrive (vignettes, simulations 3D, parcours FAO,
caractères des polices), et leur vidage d'un clic."""
from __future__ import annotations

import sys

from ..i18n import tr


def process_memory_mb() -> float | None:
    """Mémoire de travail du processus (Mo) ; None hors Windows ou en cas d'échec."""
    if sys.platform != 'win32':
        return None
    try:
        import ctypes
        from ctypes import wintypes

        class Counters(ctypes.Structure):
            _fields_ = [('cb', wintypes.DWORD), ('PageFaultCount', wintypes.DWORD),
                        ('PeakWorkingSetSize', ctypes.c_size_t), ('WorkingSetSize', ctypes.c_size_t),
                        ('QuotaPeakPagedPoolUsage', ctypes.c_size_t), ('QuotaPagedPoolUsage', ctypes.c_size_t),
                        ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t), ('QuotaNonPagedPoolUsage', ctypes.c_size_t),
                        ('PagefileUsage', ctypes.c_size_t), ('PeakPagefileUsage', ctypes.c_size_t)]
        k32 = ctypes.WinDLL('kernel32')
        k32.GetCurrentProcess.restype = wintypes.HANDLE
        psapi = ctypes.WinDLL('psapi')
        psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
        psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
        c = Counters()
        c.cb = ctypes.sizeof(c)
        if not psapi.GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(c), c.cb):
            return None
        return c.WorkingSetSize / (1024 * 1024)
    except (AttributeError, OSError):
        return None


def usage() -> dict:
    """{'process', 'thumbs', 'thumbs_budget', 'sims', 'sims_budget', 'paths', 'glyphs'} (Mo, nombres)."""
    from ..cam import simulate, strategies
    from ..core import fonts
    from .symbols import _PREVIEWS
    mb = 1024 * 1024
    return {'process': process_memory_mb(),
            'thumbs': _PREVIEWS.used / mb, 'thumbs_budget': _PREVIEWS.budget / mb,
            'sims': sum(s.H.nbytes for s in simulate._SIM_CACHE.values()) / mb,
            'sims_budget': simulate.SIM_CACHE_BYTES / mb,
            'paths': len(strategies._TP_CACHE),
            'glyphs': fonts.glyph.cache_info().currsize}


def usage_text() -> str:
    u = usage()
    lines = []
    if u['process'] is not None:
        lines.append(tr('VectorDrive utilise {0} Mo de mémoire').format(f'{u["process"]:.0f}'))
    lines.append(tr('Vignettes : {0} Mo sur {1} — simulations 3D : {2} Mo sur {3} — parcours gardés : {4}').format(
        f'{u["thumbs"]:.0f}', f'{u["thumbs_budget"]:.0f}', f'{u["sims"]:.0f}', f'{u["sims_budget"]:.0f}',
        u['paths']))
    return '\n'.join(lines)


def clear_all() -> None:
    """Vide les mémoires de la séance (tout se recalcule au besoin)."""
    from ..cam import simulate, strategies
    from ..core import fonts
    from .symbols import _PREVIEWS, release_preview_processes
    _PREVIEWS.clear()
    release_preview_processes(force=True)             # processus des vignettes : rendus aussi
    simulate._SIM_CACHE.clear()
    strategies.clear_toolpath_cache()
    fonts.glyph.cache_clear()
    import gc
    gc.collect()


def _spawn_probe() -> int:
    return 1


def benchmark() -> dict:
    """Mesure rapide du poste (2 à 5 s) : retraits d'une région de 400 formes
    sur un fil puis sur les fils de calcul, et lancement d'un processus.
    Rend {'cores', 'one', 'many', 'threads', 'speedup', 'spawn', 'advice'}."""
    import multiprocessing
    import os
    import time
    from concurrent.futures import ProcessPoolExecutor
    from shapely.geometry import Point
    import shapely
    from ..cam import strategies as S
    from ..core import progress, workers
    parts = [Point(7 * (i % 20), 7 * (i // 20)).buffer(3.0, 16) for i in range(400)]
    reg = shapely.union_all(parts)
    dists = [0.2 * k for k in range(1, 13)]
    progress.step(0, 3, 'Mesure : {0} sur {1}')
    t = time.perf_counter()
    for d in dists:
        S.erode(reg, d, 8)
    one = time.perf_counter() - t
    progress.step(1, 3, 'Mesure : {0} sur {1}')
    t = time.perf_counter()
    workers.pmap(lambda d: S.erode(reg, d, 8), dists)
    many = time.perf_counter() - t
    progress.step(2, 3, 'Mesure : {0} sur {1}')
    t = time.perf_counter()
    with ProcessPoolExecutor(1, mp_context=multiprocessing.get_context('spawn'),
                             initializer=workers._start_process, initargs=(False,)) as ex:
        ex.submit(_spawn_probe).result(timeout=120)
    spawn = time.perf_counter() - t
    speed = one / many if many > 0 else 1.0
    cores = os.cpu_count() or 1
    advice = []
    if speed < 1.3 and workers.count() > 1:
        advice.append(tr('les fils de calcul aident peu sur ce poste : 2 fils suffisent'))
    if spawn > 4:
        advice.append(tr('lancer un processus est lent ({0} s) : 2 ou 3 processus au plus').format(_fr(spawn, 1)))
    return {'cores': cores, 'one': one, 'many': many, 'threads': workers.count(), 'speedup': speed,
            'spawn': spawn, 'advice': advice}


def _fr(v: float, n: int) -> str:
    return f'{v:.{n}f}'.replace('.', ',')


def benchmark_text(r: dict) -> str:
    lines = [tr('Mesure : {0} cœurs ; géométrie {1} s sur 1 fil, {2} s sur {3} fils (× {4}) ; '
                'lancement d\'un processus {5} s').format(
        r['cores'], _fr(r['one'], 2), _fr(r['many'], 2), r['threads'], _fr(r['speedup'], 1), _fr(r['spawn'], 1))]
    lines += [tr('Conseil : {0}').format(a) for a in r['advice']] or [tr('Réglages automatiques adaptés à ce poste')]
    return '\n'.join(lines)
