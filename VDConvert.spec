# -*- mode: python ; coding: utf-8 -*-
# Recette PyInstaller de VD-convert, le convertisseur seul : python -m PyInstaller --clean --noconfirm VDConvert.spec
# Sortie : dist/VD-convert/VD-convert.exe (un dossier, sans console) — recette à part de VectorDrive.spec : le
# dossier se copie seul sur un poste de bureau, sans l'application de dessin.
# Contrôle : dist/VD-convert/VD-convert.exe --autotest (rapport VD-convert_rapport.txt à côté).
# Dehors, délibérément : l'assistant IA (anthropic, openai), les fichiers de Qt jamais ouverts ; les
# plugins ne sont pas chargés et l'application de dessin n'est pas lancée.
import pathlib
import re

racine = pathlib.Path(SPECPATH)
version = re.search(r"__version__ = '([^']+)'", (racine / 'vectordrive' / '__init__.py').read_text(encoding='utf-8')).group(1)
v4 = tuple((list(map(int, version.split('.'))) + [0, 0, 0, 0])[:4])
(racine / 'build').mkdir(exist_ok=True)
vinfo = racine / 'build' / 'vdconvert_version.txt'
vinfo.write_text(f'''VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={v4}, prodvers={v4},
    mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0,
    date=(0, 0)),
  kids=[
    StringFileInfo([
      StringTable('040C04B0', [
        StringStruct('CompanyName', 'VectorDrive'),
        StringStruct('FileDescription', 'VD-convert — conversion de dessins vectoriels'),
        StringStruct('FileVersion', '{version}'),
        StringStruct('InternalName', 'VD-convert'),
        StringStruct('OriginalFilename', 'VD-convert.exe'),
        StringStruct('ProductName', 'VD-convert'),
        StringStruct('ProductVersion', '{version}')])
    ]),
    VarFileInfo([VarStruct('Translation', [1036, 1200])])
  ]
)
''', encoding='utf-8')

a = Analysis(
    ['VDConvert.py'],
    pathex=[str(racine)],
    datas=[(str(racine / 'vectordrive' / 'ressources'), 'vectordrive/ressources'),
           (str(racine / 'licences'), 'licences'), (str(racine / 'THIRD_PARTY_NOTICES.md'), '.'),
           (str(racine / 'LICENSE'), '.'), (str(racine / 'LICENSE-MIT'), '.'),
           (str(racine / 'LICENSE-APACHE'), '.'), (str(racine / 'NOTICE'), '.')],
    hiddenimports=[
        # lecteurs et écrivains chargés à la demande par le registre des formats
        'vectordrive.io.native', 'vectordrive.io.vnd', 'vectordrive.io.dxf', 'vectordrive.io.svg',
        'vectordrive.io.pdf', 'vectordrive.io.vnd_write', 'vectordrive.io.smb', 'vectordrive.io.postscript',
        'vectordrive.vdpathops', 'vectordrive.core.fontformats', 'vectordrive.i18n',
        'vectordrive.ui.vdconvert_window', 'pypdf', 'ezdxf', 'fontTools',
    ],
    excludes=['tkinter', 'matplotlib', 'fitz', 'pymupdf', 'IPython', 'pytest', 'jinja2',
              'PyQt5', 'PyQt6', 'PySide2', 'ezdxf.addons.drawing', 'ezdxf.addons.xqt',
              'PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets', 'PySide6.Qt3DCore',
              'PySide6.QtMultimedia', 'PySide6.QtQuick', 'PySide6.QtQml', 'PySide6.QtPdf', 'PySide6.QtCharts',
              'PySide6.QtNetwork', 'PySide6.QtOpenGL', 'PySide6.QtOpenGLWidgets', 'PySide6.QtSql',
              'PySide6.QtTest', 'PySide6.QtDesigner', 'PySide6.QtHelp', 'PySide6.QtPrintSupport',
              # l'assistant IA : pas dans un convertisseur (les modules de VectorDrive, eux, restent : la lecture et
              # l'écriture des dessins en appellent d'autres, FAO et 3D comprises — les maillages d'un DXF —, à la
              # demande)
              'anthropic', 'openai',
              'scipy', 'pandas', 'pytz', 'tzdata', 'dateutil', 'zstandard', 'websockets', 'click', 'markupsafe'],
    noarchive=False,
)
# fichiers de Qt qu'un convertisseur n'ouvre jamais (rendu OpenGL logiciel, Quick/QML, PDF de Qt, traductions
# autres que le français et l'anglais) : ~40 Mo de moins
_DROP = ('opengl32sw', 'qt6quick', 'qt6qml', 'qt6pdf', 'qt6virtualkeyboard', 'qt6opengl', 'qt6network')


def _keep(entry):
    low = entry[0].replace('\\', '/').lower()
    name = low.rsplit('/', 1)[-1]
    if name.startswith(_DROP):
        return False
    if '/translations/' in low and low.endswith('.qm') and not (name.endswith('_fr.qm') or name.endswith('_en.qm')):
        return False
    return True


a.binaries = [b for b in a.binaries if _keep(b)]
a.datas = [d for d in a.datas if _keep(d)]
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name='VD-convert',
    icon=str(racine / 'vectordrive' / 'ressources' / 'vectordrive.ico'),
    console=False,
    version=str(vinfo),
)
coll = COLLECT(exe, a.binaries, a.datas, name='VD-convert')
