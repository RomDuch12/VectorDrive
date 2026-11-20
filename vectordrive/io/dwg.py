"""DWG (AutoCAD) : ouverts et enregistrés par ODA File Converter (Open Design Alliance, gratuit, installé sur le poste ;
ni fourni ni repris). VectorDrive lui confie un DXF, ou reçoit de lui un DXF qu'ezdxf lit comme les autres : toutes
les versions de DWG, de R12 à 2018 (AutoCAD 2025 compris). Les vignettes de la bibliothèque et du navigateur viennent
de l'aperçu que tout DWG porte dans son en-tête, lu sans lui."""
from __future__ import annotations

import glob
import os
import pathlib
import re
import shutil
import struct
import subprocess
import tempfile

from ..core import progress
from ..core.document import Document

EXTENSIONS = ('.dwg',)
#: Réglage F10 : chemin d'ODAFileConverter.exe, s'il n'est pas à sa place habituelle
SETTING = 'import/oda'
#: Réglage F10 : version des DWG enregistrés
VERSION_SETTING = 'export/dwg_version'
VERSIONS = (('ACAD2018', 'AutoCAD 2018 et après'), ('ACAD2013', 'AutoCAD 2013 à 2017'),
            ('ACAD2010', 'AutoCAD 2010 à 2012'), ('ACAD2007', 'AutoCAD 2007 à 2009'),
            ('ACAD2004', 'AutoCAD 2004 à 2006'), ('ACAD2000', 'AutoCAD 2000 à 2002'),
            ('ACAD14', 'AutoCAD R14'), ('ACAD12', 'AutoCAD R12'))
DEFAULT_VERSION = 'ACAD2018'
#: page de téléchargement d'ODA File Converter (proposée quand il manque)
URL = 'https://www.opendesign.com/guestfiles/oda_file_converter'
#: début du bloc d'aperçu d'un DWG (R13 et après)
_SENTINEL = bytes.fromhex('1f256d07d43628289d57ca3f9d44102b')
_PREVIEW_MAX = 16 * 1024 * 1024


class ConverterMissing(ValueError):
    """ODA File Converter introuvable sur le poste : le message dit quoi faire (la fenêtre propose la page de
    téléchargement et le choix du programme)."""


def _settings(settings):
    if settings is not None:
        return settings
    try:
        from ..portable import settings as _s
        return _s()
    except Exception:                                    # pragma: no cover - réglages illisibles
        return None


def _version_key(path: str) -> tuple:
    """« …/ODAFileConverter 25.12.0/… » → (25, 12, 0) : la plus récente d'abord."""
    m = re.search(r'ODAFileConverter[^\\/]*', path)
    return tuple(int(n) for n in re.findall(r'\d+', m.group(0))) if m else ()


def _usual_places() -> list[str]:
    out = []
    for var in ('ProgramFiles', 'ProgramW6432', 'ProgramFiles(x86)'):
        root = os.environ.get(var)
        if root:
            out += sorted(glob.glob(os.path.join(root, 'ODA', 'ODAFileConverter*', 'ODAFileConverter.exe')),
                          key=_version_key, reverse=True)
    out.append('/Applications/ODAFileConverter.app/Contents/MacOS/ODAFileConverter')   # macOS
    return out


def find(settings=None) -> str:
    """Chemin d'ODA File Converter : le réglage, puis le chemin du système, puis Program Files\\ODA (la version la
    plus récente). '' s'il n'y est pas."""
    s = _settings(settings)
    chosen = str(s.value(SETTING, '') or '').strip().strip('"') if s is not None else ''
    if chosen and os.path.isfile(chosen):
        return chosen
    found = shutil.which('ODAFileConverter')
    if found and not (os.name == 'nt' and os.path.dirname(os.path.abspath(found)) == os.getcwd()):
        return found                                     # (sous Windows, jamais celui du dossier courant)
    return next((p for p in _usual_places() if os.path.isfile(p)), '')


def version_of(settings=None) -> str:
    s = _settings(settings)
    v = str(s.value(VERSION_SETTING, DEFAULT_VERSION) or '') if s is not None else ''
    return v if v in dict(VERSIONS) else DEFAULT_VERSION


def command(exe: str, in_dir: str, out_dir: str, version: str, kind: str, name: str) -> list[str]:
    """Ligne de commande d'ODA File Converter : dossier d'entrée, de sortie, version, DWG ou DXF, sans sous-dossiers,
    avec réparation (audit), le seul fichier `name`."""
    return [exe, in_dir, out_dir, version, kind, '0', '1', name]


def _hidden():
    """Pas de fenêtre du convertisseur (une application Qt, qui en ouvre une même en ligne de commande)."""
    if not hasattr(subprocess, 'STARTUPINFO'):
        return None
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = 0                                   # SW_HIDE
    return si


def _text(data: bytes) -> str:
    """Ce qu'écrit le convertisseur : UTF-8, sinon la page de codes du poste (ses messages accentués)."""
    try:
        return data.decode('utf-8')
    except UnicodeDecodeError:
        import locale
        return data.decode(locale.getpreferredencoding(False) or 'cp1252', 'replace')


def _run(exe: str, in_dir: str, out_dir: str, version: str, kind: str, name: str, label: str,
         timeout: float) -> str:
    """Convertit `in_dir/name` dans `out_dir` ; rend le chemin écrit, sinon ValueError avec la raison donnée par le
    convertisseur (ses fichiers .err)."""
    import time
    progress.check()
    try:
        proc = subprocess.Popen(command(exe, in_dir, out_dir, version, kind, name), stdout=subprocess.DEVNULL,
                                stderr=subprocess.PIPE, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
                                startupinfo=_hidden())
    except OSError as ex:
        raise ValueError(f'{label} : ODA File Converter n\'a pas pu démarrer ({ex})') from ex
    t0 = time.monotonic()
    try:
        while True:
            try:
                _o, stderr = proc.communicate(timeout=0.25)
                break
            except subprocess.TimeoutExpired:
                progress.check()                         # Annuler : le convertisseur est arrêté
                if time.monotonic() - t0 > timeout:
                    raise ValueError(f'{label} : ODA File Converter ne répond pas après {int(timeout)} s') from None
    except BaseException:
        proc.kill()
        try:
            proc.communicate(timeout=10)
        except Exception:                                # noqa: BLE001 — arrêté quoi qu'il arrive
            pass
        raise
    out = os.path.join(out_dir, pathlib.Path(name).stem + '.' + kind.lower())
    if os.path.isfile(out) and os.path.getsize(out) > 0:
        return out
    why = []
    for err in sorted(glob.glob(os.path.join(out_dir, '*.err'))):
        try:
            why += [t.strip() for t in _text(pathlib.Path(err).read_bytes()).splitlines() if t.strip()]
        except OSError:
            pass
    if not why:
        why = [t.strip() for t in _text(stderr or b'').splitlines() if t.strip()]
    raise ValueError(f'{label} : ODA File Converter n\'a pas su le convertir' + (f' ({why[-1][:200]})' if why else ''))


def read(path, settings=None, *, timeout: float = 300) -> Document:
    """Le DWG, converti en DXF par ODA File Converter puis lu comme un DXF. Sans lui : `ConverterMissing`."""
    from . import dxf
    src = pathlib.Path(path)
    exe = find(settings)
    if not exe:
        raise ConverterMissing(f'{src.name} : les DWG s\'ouvrent par ODA File Converter (gratuit, Open Design '
                               'Alliance), qui n\'est pas trouvé sur ce poste. L\'installer, ou donner son chemin '
                               'dans F10 > Fichiers ; ou demander le dessin en DXF.')
    with tempfile.TemporaryDirectory(prefix='vd_dwg_', ignore_cleanup_errors=True) as tmp:
        in_dir, out_dir = os.path.join(tmp, 'entree'), os.path.join(tmp, 'sortie')
        os.mkdir(in_dir)
        os.mkdir(out_dir)
        shutil.copyfile(src, os.path.join(in_dir, 'dessin.dwg'))     # (un nom simple : le convertisseur filtre)
        out = _run(exe, in_dir, out_dir, DEFAULT_VERSION, 'DXF', 'dessin.dwg', src.name, timeout)
        doc = dxf.read(out)
    doc.source_path = str(src)
    doc.source_format = 'dwg'
    doc.report.append(f'{src.name} ouvert par ODA File Converter')
    return doc


def write(doc: Document, path, settings=None, *, timeout: float = 300) -> None:
    """Le dessin en DXF, converti en DWG par ODA File Converter, de la version réglée dans F10 (AutoCAD 2018 et
    après par défaut). Sans lui : `ConverterMissing`."""
    from . import dxf
    dst = pathlib.Path(path)
    exe = find(settings)
    if not exe:
        raise ConverterMissing(f'{dst.name} : les DWG s\'écrivent par ODA File Converter (gratuit, Open Design '
                               'Alliance), qui n\'est pas trouvé sur ce poste. L\'installer, ou donner son chemin '
                               'dans F10 > Fichiers ; ou enregistrer le dessin en DXF.')
    version = version_of(settings)
    part = str(dst) + '.tmp'
    try:
        with tempfile.TemporaryDirectory(prefix='vd_dwg_', ignore_cleanup_errors=True) as tmp:
            in_dir, out_dir = os.path.join(tmp, 'entree'), os.path.join(tmp, 'sortie')
            os.mkdir(in_dir)
            os.mkdir(out_dir)
            dxf.write(doc, os.path.join(in_dir, 'dessin.dxf'))
            out = _run(exe, in_dir, out_dir, version, 'DWG', 'dessin.dxf', dst.name, timeout)
            shutil.copyfile(out, part)
        os.replace(part, dst)                            # (le DWG ouvert dans AutoCAD : refusé, rien ne reste)
    except BaseException:
        try:
            os.remove(part)
        except OSError:
            pass
        raise
    doc.report.append(f'{dst.name} écrit par ODA File Converter ({dict(VERSIONS)[version]})')


def preview(path) -> tuple[str, bytes] | None:
    """L'aperçu enregistré dans l'en-tête du DWG (R13 et après) : ('png', PNG) ou ('bmp', DIB sans en-tête de
    fichier) ; None s'il n'y en a pas ou que le fichier n'est pas un DWG. Sans ODA File Converter."""
    try:
        with open(path, 'rb') as f:
            head = f.read(0x11)
            if len(head) < 0x11 or not head.startswith(b'AC10') or head[:6] < b'AC1012':
                return None
            f.seek(struct.unpack_from('<I', head, 0x0D)[0])
            block = f.read(21)
            if len(block) < 21 or block[:16] != _SENTINEL:
                return None
            count = block[20]
            table = f.read(9 * count)
            found = {}
            for i in range(len(table) // 9):
                code, start, size = struct.unpack_from('<BII', table, 9 * i)
                if code in (2, 6) and 0 < size <= _PREVIEW_MAX:
                    found.setdefault(code, (start, size))
            for code, kind in ((6, 'png'), (2, 'bmp')):
                if code in found:
                    start, size = found[code]
                    f.seek(start)
                    data = f.read(size)
                    if len(data) == size and (kind != 'png' or data.startswith(b'\x89PNG')):
                        return kind, data
    except (OSError, struct.error, ValueError):
        return None
    return None
