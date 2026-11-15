"""Reprise d'usinage (TypeEdit) : n'usiner qu'une partie d'un parcours, après une casse d'outil ou un arrêt par exemple.

L'opération garde le premier et le dernier mouvement choisis, avec l'empreinte du parcours au moment du choix : des numéros de
mouvement ne valent que pour ce parcours-là. S'il a changé depuis, la reprise est ignorée et un message le dit : mieux vaut
repasser à vide que de reprendre à une mauvaise place.

Le parcours complet reste sur `tp.uncut` : le reste du calcul (liaisons basses, gamme) travaille sur lui.
"""
from __future__ import annotations

import zlib

from .model import Move

NOTE = "reprise d'usinage"
EPS = 1e-9


def entries(moves: list) -> list[int]:
    """Les mouvements qui entrent dans la matière : venus du dessus, ils arrivent à la surface ou plus bas."""
    return [i for i in range(1, len(moves))
            if moves[i].kind != 'rapid' and moves[i - 1].z > EPS and moves[i].z <= EPS]


def rows(moves: list) -> list[int]:
    """Les points que l'on peut choisir : la fin de chaque mouvement qui usine."""
    return [i for i, m in enumerate(moves) if m.kind != 'rapid']


def signature(moves: list) -> str:
    """L'empreinte du parcours : son nombre de mouvements et leurs points, au dix-millième de millimètre."""
    crc = 0
    for m in moves:
        crc = zlib.crc32(f'{m.kind} {m.x:.4f} {m.y:.4f} {m.z:.4f} {m.cx:.4f} {m.cy:.4f};'.encode('ascii'), crc)
    return f'{len(moves)}:{crc:08x}'


def cut(moves: list, start: int, end: int, safe: float, clear: float) -> list:
    """Les mouvements qui suivent le point `start`, jusqu'au point `end` compris. L'outil arrive au-dessus du point de départ,
    y descend en plongée (il y est déjà passé : le chemin est libre) et finit au dégagement."""
    first = moves[start]
    head = [Move('rapid', first.x, first.y, safe), Move('rapid', first.x, first.y, clear)]
    if first.z < clear - EPS:
        head.append(Move('plunge', first.x, first.y, first.z))
    kept = list(moves[start + 1:end + 1])
    while kept and kept[-1].kind == 'rapid':            # pas de trajet vers ce qui ne sera pas usiné
        kept.pop()
    last = kept[-1] if kept else first
    return head + kept + [Move('rapid', last.x, last.y, safe)]


def choose(op, moves: list, start: int, end: int) -> None:
    """Note la reprise sur l'opération ; tout le parcours : plus de reprise."""
    keep = rows(moves)
    if not keep or (start <= keep[0] and end >= keep[-1]):
        forget(op)
        return
    op.restart_from, op.restart_to, op.restart_sig = int(start), int(end), signature(moves)


def forget(op) -> None:
    op.restart_from, op.restart_to, op.restart_sig = 0, 0, ''


def current(op, moves: list) -> tuple | None:
    """(début, fin) notés sur l'opération s'ils valent pour ces mouvements."""
    if getattr(op, 'restart_sig', '') and op.restart_sig == signature(moves):
        return op.restart_from, op.restart_to
    return None


def full_moves(tp) -> list:
    return tp.uncut[0] if tp.uncut is not None else tp.moves


def restore(tp) -> None:
    """Le parcours redevient complet."""
    if tp.uncut is not None:
        tp.moves, tp.cycles, tp.unfaced = tp.uncut
        tp.uncut = None
    tp.warnings[:] = [w for w in tp.warnings if not w.startswith(NOTE)]


def apply(op, tp) -> bool:
    """Coupe le parcours (complet) selon l'opération ; rend vrai s'il l'est. Les cycles machine sont retirés : le post-processeur
    qui les préfère écrirait sinon tous les trous."""
    if not getattr(op, 'restart_sig', '') or not tp.moves:
        return False
    span = current(op, tp.moves)
    if span is None:
        tp.warnings.append(f"{NOTE} ignorée : le parcours a changé depuis son choix, il est usiné en entier")
        return False
    start, end = span
    all_in = entries(tp.moves)
    tp.uncut = (tp.moves, tp.cycles, tp.unfaced)
    tp.moves = cut(tp.moves, start, end, op.safe_z, op.clear_z)
    tp.cycles, tp.unfaced = [], None
    kept = sum(1 for i in all_in if start <= i <= end)
    tp.warnings.append(f"{NOTE} : du mouvement {start + 1} au mouvement {end + 1} sur {len(tp.uncut[0])}, "
                       f"{kept} entrée(s) dans la matière sur {len(all_in)}")
    return True


def whole(tp):
    """Le parcours tel qu'il est usiné en entier, pour ce qui compte la matière déjà enlevée (gamme)."""
    if tp.uncut is None:
        return tp
    import copy
    c = copy.copy(tp)
    c.moves, c.cycles, c.unfaced = tp.uncut
    c.uncut = None
    return c
