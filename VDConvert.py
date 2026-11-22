"""VD-convert — le convertisseur seul de VectorDrive (voir vectordrive/vdconvert.py).

    VD-convert.exe                                  la fenêtre (installer, désinstaller, convertir, mode d'emploi)
    VD-convert.exe --convert a.dxf --to pdf [--out DOSSIER] [--keep]
    VD-convert.exe --installer [--silencieux]       installer (autres versions retirées et remplacées)
    VD-convert.exe --desinstaller [--silencieux]    désinstaller (les Applications de Windows l'appellent)
    VD-convert.exe --autotest                       contrôles de la version empaquetée
"""
from __future__ import annotations

import argparse
import os
import pathlib
import sys
import traceback


def make_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog='VD-convert')
    ap.add_argument('--convert', metavar='ENTREE')
    ap.add_argument('--to', default='dxf')
    ap.add_argument('--out')
    ap.add_argument('--keep', action='store_true', help='jamais d\'écrasement (nom « nom (2).ext »)')
    ap.add_argument('--installer', action='store_true')
    ap.add_argument('--desinstaller', action='store_true')
    ap.add_argument('--silencieux', action='store_true', help='sans question ni message')
    ap.add_argument('--autotest', action='store_true')
    return ap


def _log(autotest: bool = False):
    """Sans console (exécutable fenêtré) : la sortie va dans %LOCALAPPDATA%\\VD-convert\\VD-convert.log, ou à côté
    de l'exécutable pour l'autotest (VD-convert_rapport.txt, lu par la recette de publication)."""
    if sys.stdout is not None:
        return
    if autotest:
        try:
            sys.stdout = sys.stderr = open(pathlib.Path(sys.executable).parent / 'VD-convert_rapport.txt', 'w',
                                           encoding='utf-8')
            return
        except OSError:
            pass
    base = pathlib.Path(os.environ.get('LOCALAPPDATA') or pathlib.Path.home()) / 'VD-convert'
    try:
        base.mkdir(parents=True, exist_ok=True)
        sys.stdout = sys.stderr = open(base / 'VD-convert.log', 'a', encoding='utf-8')
    except OSError:
        sys.stdout = sys.stderr = open(os.devnull, 'w', encoding='utf-8')


def _app():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName('VD-convert')
    return app


def _say(title: str, text: str, error: bool = False) -> None:
    from PySide6.QtWidgets import QMessageBox
    _app()
    (QMessageBox.warning if error else QMessageBox.information)(None, title, text)


def main(argv=None) -> int:
    args = make_parser().parse_args(argv)
    _log(args.autotest)
    if args.autotest:
        return autotest()
    from vectordrive import vdconvert as VC
    if args.convert:
        try:
            dest, notes = VC.convert(args.convert, args.to, args.out, keep=args.keep)
        except Exception as ex:                          # noqa: BLE001 — dit à l'utilisateur, pas une trace muette
            traceback.print_exc()
            if not args.silencieux:
                _say('VD-convert', f'{pathlib.Path(args.convert).name} : {ex}', error=True)
            return 1
        print(f'{args.convert} -> {dest}')
        for n in notes:
            print(f'  remarque : {n}')
        return 0
    if args.installer or args.desinstaller:
        try:
            if args.installer:
                src = VC.running_dir()
                got = VC.install(None, src, VC.install_dir() if src is not None else None)
                lines = [f'Installé : {got["exe"]}'] + [f'retiré : {r}' for r in got['removed']]
            else:
                if not args.silencieux:
                    from PySide6.QtWidgets import QMessageBox
                    _app()
                    if QMessageBox.question(None, 'VD-convert', 'Désinstaller VD-convert ?') != \
                            QMessageBox.StandardButton.Yes:
                        return 1
                run = VC.running_dir()                   # les Applications de Windows lancent l'exe installé
                lines = VC.uninstall(None, run if VC.safe_folder(run) else VC.install_dir()) or ['Rien à retirer.']
        except OSError as ex:
            print(ex)
            if not args.silencieux:
                _say('VD-convert', str(ex), error=True)
            return 1
        print('\n'.join(lines))
        if not args.silencieux:
            _say('VD-convert', '\n'.join(lines))
        return 0
    app = _app()
    from vectordrive.ui.vdconvert_window import ConvertWindow
    w = ConvertWindow()
    w.show()
    return app.exec()


def autotest() -> int:
    """La version empaquetée : conversions dans chaque format, fenêtre, menu prévu (registre en mémoire), et sans
    l'application de dessin ni l'assistant IA."""
    import shutil
    import tempfile
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    try:
        sys.stdout.reconfigure(errors='replace')
    except (AttributeError, ValueError):
        pass
    tmp = pathlib.Path(tempfile.mkdtemp(prefix='vdconvert_autotest_'))
    os.environ['VECTORDRIVE_SETTINGS'] = str(tmp / 'reglages.ini')
    os.environ['VECTORDRIVE_VDCONVERT_DIR'] = str(tmp / 'installe')
    ok = ko = 0

    def check(name, fn):
        nonlocal ok, ko
        try:
            detail = fn() or ''
            ok += 1
            print(f'  OK   {name} {detail}', flush=True)
        except Exception as ex:                          # noqa: BLE001
            ko += 1
            print(f'  ÉCHEC {name} : {ex}', flush=True)
            traceback.print_exc(limit=3)

    from vectordrive import vdconvert as VC
    from vectordrive import shellmenu as SM
    print(f'VD-convert {VC.version()} — autotest', flush=True)
    src = tmp / 'cote.svg'
    src.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="60mm" viewBox="0 0 100 60">'
                   '<rect x="10" y="10" width="80" height="40" fill="none"/></svg>', encoding='utf-8')

    def t_convert():
        from vectordrive.io import registry
        sizes = []
        for k, _lab in SM.TARGETS:
            dest, _n = VC.convert(src, k, tmp / 'sortie', keep=True)
            sizes.append(f'{k} {dest.stat().st_size} o')
            back, _n = VC.convert(dest, 'svg', tmp / 'relu', keep=True)
            bb = registry.open_document(str(back)).bbox()
            if abs((bb[2] - bb[0]) - 80) > 0.05 or abs((bb[3] - bb[1]) - 40) > 0.05:
                raise AssertionError(f'{k} : {bb}')
        return ' · '.join(sizes)

    def t_sources():
        # chaque format d'entrée du menu qu'on sait écrire : écrit, puis converti dans chaque format de sortie
        from vectordrive.io import registry
        doc = registry.open_document(str(src))
        done = []
        for ext in SM.SOURCES:
            f = registry.writer_for(f'x{ext}')
            if f is None or f.writer is None:
                continue
            p = tmp / 'entrees' / f'e{ext}'
            p.parent.mkdir(exist_ok=True)
            registry.save_document(doc, p)
            for k, _lab in SM.targets_for(ext):
                VC.convert(p, k, tmp / 'depuis', keep=True)
            done.append(ext.lstrip('.'))
        return ', '.join(done)

    def t_window():
        _app()
        from vectordrive.ui.vdconvert_window import ConvertWindow
        w = ConvertWindow(reg=VC.MemoryReg())
        assert w.install_btn is not None and w.uninstall_btn is not None and len(w.guide_text()) > 200
        w.close()
        return w.windowTitle()

    def t_menu():
        reg = VC.MemoryReg()
        prog = (str(tmp / 'installe' / VC.EXE), [])
        SM.install(write=reg.write, program=prog, lots=False)
        cmd = reg.read(rf'{SM.CLASSES}\{SM.VERB}.dxf\shell\01svg\command', '')
        assert VC.EXE in cmd and '--convert' in cmd, cmd
        assert not reg.read(rf'{SM.CLASSES}\{SM.DIR_KEY}', 'MUIVerb')     # pas de traitement par lots ici
        return f'{len(SM.SOURCES)} extensions'

    def t_reduced():
        bad = [m for m in ('vectordrive.ui.main_window', 'vectordrive.agent.chat', 'anthropic', 'openai')
               if m in sys.modules]
        assert not bad, bad
        return 'ni application de dessin, ni assistant IA'

    check('conversions DXF, SVG, PDF, EPS (et relues)', t_convert)
    check('formats d’entrée', t_sources)
    check('fenêtre', t_window)
    check('menu de l\'explorateur prévu', t_menu)
    check('version réduite', t_reduced)
    shutil.rmtree(tmp, ignore_errors=True)
    print(f'{ok} OK, {ko} échec(s)', flush=True)
    return 1 if ko else 0


if __name__ == '__main__':
    sys.exit(main())
