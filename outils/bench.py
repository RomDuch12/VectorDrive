"""Banc de mesure de l'interface sur un gros dessin.

    python outils/bench.py fichier.smb [--copies 10]

Mesure : ouverture, premier affichage, repeint complet, survol avec
accrochage (surimpression), tout sélectionner, déplacer, annuler, refaire.
`--copies N` juxtapose N exemplaires du dessin pour simuler un fichier N
fois plus gros. Fenêtre hors écran ; rien n'est enregistré.
"""
from __future__ import annotations

import argparse
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('fichier')
    ap.add_argument('--copies', type=int, default=1)
    a = ap.parse_args(argv)
    from PySide6.QtCore import QEvent, QPointF, Qt
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from vectordrive.core.geom import Affine
    from vectordrive.io import registry
    from vectordrive.ui.main_window import MainWindow

    res = []

    def mesure(nom, fn, n=1):
        t = time.perf_counter()
        for _ in range(n):
            fn()
        dt = (time.perf_counter() - t) / n
        res.append((nom, dt))
        print(f'  {nom:38s} {dt * 1000:9.1f} ms', flush=True)

    t = time.perf_counter()
    doc = registry.open_document(a.fichier)
    res.append(('ouverture', time.perf_counter() - t))
    if a.copies > 1:
        L = doc.layers[0]
        base = list(L.items)
        bb = doc.bbox()
        w = bb[2] - bb[0]
        for k in range(1, a.copies):
            L.items.extend(it.transformed(Affine.translation(k * w * 1.05, 0)) for it in base)
    st = doc.stats()
    print(f'{pathlib.Path(a.fichier).name} × {a.copies} : {st["objets"]} objets, {st["contours"]} contours, '
          f'{st["segments"]} segments')
    print(f'  {"ouverture":38s} {res[0][1] * 1000:9.1f} ms')
    win = MainWindow()
    win.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
    win.resize(1400, 900)
    win.show()
    app.processEvents()
    c = win.canvas

    def show():
        c.set_document(doc)
        c.repaint()
    mesure('premier affichage', show)

    def full():
        c.update()
        c.repaint()
    mesure('repeint complet (cache de tracés plein)', full, 3)
    win.A['snap'].setChecked(True)
    win.set_tool('measure')
    pts = iter(range(10_000))

    def hover():
        i = next(pts)
        p = QPointF(300 + i % 50 * 9, 300 + i % 37 * 7)
        c.mouseMoveEvent(QMouseEvent(QEvent.Type.MouseMove, p, p, Qt.MouseButton.NoButton,
                                     Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier))
        c.repaint()
    mesure('survol + accrochage (1er)', hover)
    mesure('survol + accrochage (suivants)', hover, 30)
    win.set_tool('select')
    mesure('tout sélectionner', lambda: (c.select_all(), c.repaint()))
    mesure('déplacer tout', lambda: (c.transform_selection(Affine.translation(1, 0)), c.repaint()))
    mesure('annuler', lambda: (win.undo(), c.repaint()))
    mesure('refaire', lambda: (win.redo(), c.repaint()))
    win.modified = False
    win.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
