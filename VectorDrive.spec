# -*- mode: python ; coding: utf-8 -*-
# Recette PyInstaller : python -m PyInstaller --clean --noconfirm VectorDrive.spec
# Sortie : dist/VectorDrive/VectorDrive.exe (un dossier, sans console).
# Contrôle : dist/VectorDrive/VectorDrive.exe --autotest > rapport.txt
import os
import pathlib
import re

from PyInstaller.utils.hooks import collect_submodules

racine = pathlib.Path(SPECPATH)

# ressource de version Windows tirée de vectordrive/__init__.py
version = re.search(r"__version__ = '([^']+)'", (racine / 'vectordrive' / '__init__.py').read_text(encoding='utf-8')).group(1)
v4 = tuple((list(map(int, version.split('.'))) + [0, 0, 0, 0])[:4])
(racine / 'version_info.txt').write_text(f'''VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={v4}, prodvers={v4},
    mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0,
    date=(0, 0)),
  kids=[
    StringFileInfo([
      StringTable('040C04B0', [
        StringStruct('CompanyName', 'BFM'),
        StringStruct('FileDescription', 'VectorDrive — dessin pour la gravure'),
        StringStruct('FileVersion', '{version}'),
        StringStruct('InternalName', 'VectorDrive'),
        StringStruct('OriginalFilename', 'VectorDrive.exe'),
        StringStruct('ProductName', 'VectorDrive'),
        StringStruct('ProductVersion', '{version}')])
    ]),
    VarFileInfo([VarStruct('Translation', [1036, 1200])])
  ]
)
''', encoding='utf-8')

a = Analysis(
    ['VectorDrive.py'],
    pathex=[str(racine)],
    datas=[(str(racine / 'vectordrive' / 'ressources'), 'vectordrive/ressources'),
           (str(racine / 'licences'), 'licences'), (str(racine / 'THIRD_PARTY_NOTICES.md'), '.'),
           (str(racine / 'LICENSE'), '.'), (str(racine / 'LICENSE-MIT'), '.'),
           (str(racine / 'LICENSE-APACHE'), '.'), (str(racine / 'NOTICE'), '.'),
           (str(racine / 'CHANGELOG.md'), 'vectordrive/ressources')],
    hiddenimports=[
        # lecteurs chargés à la demande par le registre des formats
        'vectordrive.io.native', 'vectordrive.io.vnd', 'vectordrive.io.dxf',
        'vectordrive.io.svg', 'vectordrive.io.pdf', 'vectordrive.io.vnd_write', 'vectordrive.io.smb', 'vectordrive.vdpathops', 'vectordrive.io.postscript',
        'vectordrive.io.step',
        'vectordrive.io.neostep.stepread', 'vectordrive.io.neostep.step3d',
        'vectordrive.core.snap', 'vectordrive.core.duplicate', 'vectordrive.ui.layers',
        'vectordrive.update', 'vectordrive.i18n', 'vectordrive.core.codes', 'vectordrive.core.barcode',
        'vectordrive.core.cleanup', 'vectordrive.core.combine', 'vectordrive.core.braille',
        'vectordrive.core.halftone', 'vectordrive.ui.guide', 'vectordrive.core.dial', 'vectordrive.core.holes', 'vectordrive.core.check', 'vectordrive.core.nesting', 'vectordrive.core.trace', 'vectordrive.core.chain', 'vectordrive.ui.rulers', 'vectordrive.io.raster', 'vectordrive.core.fontformats', 'vectordrive.io.paragraph', 'vectordrive.core.hatch', 'vectordrive.core.shadow', 'vectordrive.core.fitcurve', 'vectordrive.core.envelope', 'vectordrive.core.stamp', 'vectordrive.core.trim', 'vectordrive.core.punch', 'vectordrive.core.parallel', 'vectordrive.core.blend', 'vectordrive.core.symmetric', 'vectordrive.ui.news', 'vectordrive.ui.command_search', 'vectordrive.portable', 'vectordrive.ui.batdialog', 'vectordrive.ui.checkdlg', 'vectordrive.core.biarc', 'vectordrive.core.clip',
        'vectordrive.ui.printing', 'PySide6.QtPrintSupport',
        'pypdf', 'ezdxf', 'fontTools', 'vectordrive.plugins', 'manifold3d',
        'anthropic', 'openai',                           # assistant IA (importés à la demande)
        # bibliothèque standard souvent utile aux plugins (chargés depuis plugins/, hors de l'analyse) et aux
        # bibliothèques qu'ils apportent dans _lib (openpyxl : xml.etree, zipfile…)
        'decimal', 'csv', 'xml.etree.ElementTree', 'xml.dom.minidom', 'xml.sax.saxutils', 'zipfile', 'hashlib',
        'uuid', 'pkgutil', 'struct', 'unicodedata', 'numbers', 'fractions', 'statistics', 'difflib', 'textwrap',
        'configparser', 'shlex', 'glob', 'base64', 'gzip', 'calendar', 'heapq', 'bisect', 'array', 'pprint',
        'html.parser', 'logging.handlers', 'concurrent.futures', 'queue',
    ] + [m for m in os.environ.get('VECTORDRIVE_HIDDEN_IMPORTS', '').split(',') if m]
    # tout le cœur : les plugins (chargés hors de l'analyse) importent des modules que le cœur
    # n'utilise plus lui-même (ex. cam.tiling pour le post Cielle du plugin BFM)
    + collect_submodules('vectordrive', filter=lambda m: '.tests' not in m),
    excludes=['tkinter', 'matplotlib', 'fitz', 'pymupdf', 'IPython', 'pytest', 'jinja2',
              'PyQt5', 'PyQt6', 'PySide2', 'ezdxf.addons.drawing', 'ezdxf.addons.xqt',
              'PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets', 'PySide6.Qt3DCore',
              'PySide6.QtMultimedia', 'PySide6.QtQuick', 'PySide6.QtQml',
              # entrés avec les SDK de l'assistant IA (aides facultatives de openai, anthropic), jamais servis :
              # 34 Mo de la portable 0.926.0 (round 1070)
              'scipy', 'pandas', 'pytz', 'tzdata', 'dateutil', 'zstandard', 'websockets', 'click', 'markupsafe'],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name='VectorDrive',
    icon=str(racine / 'vectordrive' / 'ressources' / 'vectordrive.ico'),
    console=False,
    version=str(racine / 'version_info.txt'),
)
coll = COLLECT(exe, a.binaries, a.datas, name='VectorDrive')
