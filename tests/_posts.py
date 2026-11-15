"""Post-processeur d'essai : le cœur n'en contient aucun (ils viennent des
plugins, round 218) ; les essais qui ont besoin d'un programme en déclarent
un le temps de l'essai."""
from __future__ import annotations

import contextlib


def write(toolpaths, setup, *, title: str = '', machine=None, stem: str = 'programme', box_mm=None):
    from vectordrive.cam.post import PostResult
    lines = ['%', f'(ESSAI {title})']
    for tp in toolpaths:
        for m in tp.moves:
            lines.append(f'{"G0" if m.kind == "rapid" else "G1"} X{m.x:.3f} Y{m.y:.3f} Z{m.z:.3f}')
    lines.append('M30')
    return PostResult('\n'.join(lines) + '\n', [], '.nc')


@contextlib.contextmanager
def registered(key: str = 'gcode', fn=write):
    """Le post-processeur d'essai sous la clé `key`, le temps du bloc."""
    from vectordrive.plugins import REGISTRY
    old = REGISTRY.posts.get(key)
    REGISTRY.posts[key] = ('Essai', fn)
    try:
        yield
    finally:
        if old is None:
            REGISTRY.posts.pop(key, None)
        else:
            REGISTRY.posts[key] = old
