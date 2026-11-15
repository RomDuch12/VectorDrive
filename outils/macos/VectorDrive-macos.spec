# -*- mode: python ; coding: utf-8 -*-
# Recette PyInstaller pour macOS (version d'essai) :
#   python -m PyInstaller --clean --noconfirm outils/macos/VectorDrive-macos.spec
# Sortie : dist/VectorDrive.app ; contrôle : dist/VectorDrive.app/Contents/MacOS/VectorDrive --autotest
# Construite sur les machines macOS de GitHub (.github/workflows/macos.yml), une par processeur (arm64, x86_64).
import pathlib
import re

from PyInstaller.utils.hooks import collect_submodules

racine = pathlib.Path(SPECPATH).resolve().parents[1]
version = re.search(r"__version__ = '([^']+)'",
                    (racine / 'vectordrive' / '__init__.py').read_text(encoding='utf-8')).group(1)
# moteur natif compilé sur place (natif/vdpathops, voir le workflow) ; sans lui, son remplaçant en Python
natif = sorted((racine / 'vectordrive').glob('vdpathops*.so'))

a = Analysis(
    [str(racine / 'VectorDrive.py')],
    pathex=[str(racine)],
    datas=[(str(racine / 'vectordrive' / 'ressources'), 'vectordrive/ressources'),
           (str(racine / 'licences'), 'licences'), (str(racine / 'THIRD_PARTY_NOTICES.md'), '.'),
           (str(racine / 'LICENSE'), '.'), (str(racine / 'LICENSE-MIT'), '.'),
           (str(racine / 'LICENSE-APACHE'), '.'), (str(racine / 'NOTICE'), '.'),
           (str(racine / 'CHANGELOG.md'), 'vectordrive/ressources')],
    # tout le cœur (les plugins, chargés hors de l'analyse, en importent des modules), et la bibliothèque standard
    # souvent utile aux plugins et aux bibliothèques qu'ils apportent dans _lib (openpyxl : xml.etree, zipfile…)
    hiddenimports=['PySide6.QtPrintSupport', 'pypdf', 'ezdxf', 'fontTools', 'manifold3d', 'decimal', 'csv',
                   'xml.etree.ElementTree', 'xml.dom.minidom', 'xml.sax.saxutils', 'zipfile', 'hashlib', 'uuid',
                   'pkgutil', 'struct', 'unicodedata', 'numbers', 'fractions', 'statistics', 'difflib', 'textwrap',
                   'configparser', 'shlex', 'glob', 'base64', 'gzip', 'calendar', 'heapq', 'bisect', 'array',
                   'pprint', 'html.parser', 'logging.handlers', 'concurrent.futures', 'queue']
    + (['vectordrive.vdpathops'] if natif else [])
    + collect_submodules('vectordrive', filter=lambda m: '.tests' not in m and m != 'vectordrive.vdpathops'),
    excludes=['tkinter', 'matplotlib', 'fitz', 'pymupdf', 'IPython', 'pytest', 'jinja2',
              'PyQt5', 'PyQt6', 'PySide2', 'ezdxf.addons.drawing', 'ezdxf.addons.xqt',
              'PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets', 'PySide6.Qt3DCore',
              'PySide6.QtMultimedia', 'PySide6.QtQuick', 'PySide6.QtQml'],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='VectorDrive', console=False, argv_emulation=False)
coll = COLLECT(exe, a.binaries, a.datas, name='VectorDrive')
app = BUNDLE(
    coll,
    name='VectorDrive.app',
    icon=str(racine / 'vectordrive' / 'ressources' / 'vectordrive.png'),
    bundle_identifier='io.github.romduch12.vectordrive',
    version=version,
    info_plist={
        'CFBundleName': 'VectorDrive',
        'CFBundleDisplayName': 'VectorDrive',
        'CFBundleShortVersionString': version,
        'CFBundleVersion': version,
        'NSHighResolutionCapable': True,
        # numpy 2.5 et shiboken6 6.12 (roues macosx_14_0) : macOS 14 au moins ; plus ancien, macOS le dit au lancement
        'LSMinimumSystemVersion': '14.0',
        'NSHumanReadableCopyright': 'RomDuch with Claude — MIT OR Apache-2.0',
    },
)
