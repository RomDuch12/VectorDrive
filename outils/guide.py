"""Écrit docs/guide_commandes.md (ou _en.md) à partir du ruban réel.

    python outils/guide.py [--lang en]
"""
from __future__ import annotations

import argparse
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--lang', default='fr', choices=['fr', 'en'])
    a = ap.parse_args(argv)
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    from vectordrive import i18n
    i18n.set_language(a.lang)
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from vectordrive.ui.guide import commands_markdown
    from vectordrive.ui.main_window import MainWindow
    w = MainWindow()
    name = 'guide_commandes.md' if a.lang == 'fr' else 'guide_commandes_en.md'
    (ROOT / 'docs' / name).write_text(commands_markdown(w), encoding='utf-8')
    w.modified = False
    w.close()
    print(ROOT / 'docs' / name)
    return 0


if __name__ == '__main__':
    sys.exit(main())
