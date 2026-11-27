"""Les dossiers de l'utilisateur pour l'assistant (demande du 27/11 : « Assistant IA possibilité d'accéder aux dossiers
sélectionnés et les fichiers pour des recherches de dessin. […] Assistant IA peut accèder à cet index. »).

En lecture seule, et seulement dans les dossiers choisis par l'utilisateur pour l'index des formes (Fichier ›
Dossiers indexés, `ui.shape_search.folders`) : lister un dossier, chercher des fichiers (nom, extension, date), lire
les informations d'un dessin, interroger l'index des formes (`core.shape_index`). Tout chemin est vérifié une fois
résolu (`..`, liens et jonctions suivis jusqu'au bout, autre lecteur) : hors de ces dossiers, refusé. Rien n'est
jamais écrit, déplacé ni supprimé ; ouvrir un dessin reste à l'utilisateur (fenêtre « Dessins semblables »).

Chaque réponse est bornée : entrées parcourues (MAX_SCAN), durée (DEADLINE, résultat partiel signalé), textes,
taille totale (MAX_REPLY caractères).

Les fonctions prennent la fenêtre et les arguments de l'outil (`agent.tools.ToolSet` les déclare) ; un refus lève
`ToolError` (dit au modèle)."""
from __future__ import annotations

import datetime
import fnmatch
import json
import os
import threading
import time

from .protocol import ToolError

#: au plus tant d'entrées rendues ; d'entrées parcourues par appel ; de secondes par appel ; de résultats de formes
MAX_LISTED = 500
MAX_SCAN = 50000
DEADLINE = 10.0
MAX_RESULTS = 100
#: textes d'un dessin rendus : au plus tant de caractères chacun, tous ensemble ; ceux d'un résultat de recherche
TEXT_CHARS = 200
TEXTS_CHARS = 4000
ROW_TEXTS, ROW_TEXT_CHARS = 3, 80
#: une réponse au plus de tant de caractères (JSON) : au-delà, ses dernières entrées sont retirées
MAX_REPLY = 30000
#: un dessin hors de l'index (ou pas à jour) n'est lu que s'il fait au plus tant d'octets : au-delà, refus clair
MAX_FILE_BYTES = 20 * 1024 * 1024
#: chemins réels des dossiers permis gardés tant de secondes ; un dossier qui ne répond pas en REAL_WAIT secondes
#: (lecteur réseau déconnecté) est dit injoignable, sans bloquer
REAL_TTL = 30.0
REAL_WAIT = 2.0
_REAL: dict = {}                                         # chemin absolu → (instant, chemin résolu ou None)
_PENDING: dict = {}                                      # chemin absolu → fil encore en attente du disque
_REAL_LOCK = threading.Lock()
NO_FOLDER = ('the user has not chosen any folder for you: they add folders in File > Indexed folders (the "Index" tab '
             'of the "Similar drawings" window); nothing else on the disk can be read')


def _settings(win):
    return getattr(win, 'settings', None)


def roots(win) -> list:
    """Les dossiers permis : ceux de l'index des formes, tels que l'utilisateur les a choisis."""
    st = _settings(win)
    if st is None:
        return []
    from ..ui.shape_search import folders
    return folders(st)


def _real(a: str):
    """Le chemin réel du dossier permis `a`, ou None s'il est injoignable : gardé REAL_TTL secondes, cherché dans un
    fil attendu au plus REAL_WAIT secondes (un lecteur réseau déconnecté ne fige pas la fenêtre)."""
    now = time.monotonic()
    with _REAL_LOCK:
        hit = _REAL.get(a)
        if hit is not None and now - hit[0] < REAL_TTL:
            return hit[1]
        t = _PENDING.get(a)
        if t is not None and t.is_alive():               # le disque ne répond toujours pas
            return None
        box: dict = {}

        def work():
            try:
                box['r'] = os.path.realpath(a) if os.path.isdir(a) else None
            except (OSError, ValueError):
                box['r'] = None
        t = _PENDING[a] = threading.Thread(target=work, name='vd-dossier-permis', daemon=True)
    t.start()
    t.join(REAL_WAIT)
    r = None if t.is_alive() else box.get('r')
    with _REAL_LOCK:
        _REAL[a] = (now, r)
        if not t.is_alive():
            _PENDING.pop(a, None)
    return r


def allowed(win) -> list:
    """[(chemin absolu, chemin résolu ou None : injoignable)] des dossiers permis : résolus une fois par appel
    d'outil, au plus REAL_WAIT secondes chacun (cache court)."""
    return [(a, _real(a)) for a in (os.path.abspath(r) for r in roots(win))]


def _key(p: str) -> str:
    return os.path.normcase(os.path.normpath(p))


def _within(path: str, root: str) -> bool:
    try:
        return os.path.commonpath([_key(path), _key(root)]) == _key(root)
    except ValueError:                                   # autre lecteur, chemin absolu et relatif mêlés
        return False


def resolve(win, path, kind: str = 'any', allow=None) -> str:
    """Le chemin `path` résolu (`..`, liens, jonctions), s'il est dans un dossier permis ; `kind` 'dir' ou 'file' :
    il doit l'être. Sinon : ToolError. `allow` : `allowed(win)` déjà calculé."""
    allow = allowed(win) if allow is None else allow
    if not allow:
        raise ToolError(NO_FOLDER)
    if not isinstance(path, str) or not path.strip() or '\x00' in path:
        raise ToolError('"path" must be an absolute path inside one of the allowed folders (folders_allowed)')
    raw = os.path.expanduser(path.strip()) if path.strip().startswith('~') else path.strip()
    if not os.path.isabs(raw):
        raise ToolError(f'"{path}" is not an absolute path: give the full path, inside one of the allowed folders '
                        f'(folders_allowed)')
    full = os.path.abspath(raw)
    drive = os.path.splitdrive(full)[0].lower()
    if not any(os.path.splitdrive(a)[0].lower() == drive for a, _r in allow):     # avant tout accès au disque
        raise ToolError(f'"{path}" is outside the allowed folders (another drive): see folders_allowed')
    if not any(_within(full, a) for a, _r in allow):
        raise ToolError(f'"{path}" is outside the allowed folders: see folders_allowed')
    if not any(r is not None and _within(full, a) for a, r in allow):
        raise ToolError(f'the allowed folder of "{path}" is not reachable now (disconnected drive or network)')
    real = os.path.realpath(raw)                         # liens et jonctions suivis : là où l'on lirait vraiment
    if not any(r is not None and _within(real, r) for _a, r in allow):
        raise ToolError(f'"{path}" leads outside the allowed folders (link or junction): refused')
    if kind == 'dir' and not os.path.isdir(real):
        raise ToolError(f'"{path}" is not a folder')
    if kind == 'file' and not os.path.isfile(real):
        raise ToolError(f'"{path}" is not a file')
    return real


def _when(ts: float) -> str:
    return datetime.datetime.fromtimestamp(ts).isoformat(timespec='seconds')


def _date(v, what: str):
    if v is None:
        return None
    try:
        return datetime.datetime.fromisoformat(str(v)).timestamp()
    except ValueError as ex:
        raise ToolError(f'"{what}" must be a date such as 2026-11-27 or 2026-11-27T14:30') from ex


def _limit(args: dict, default: int, hi: int) -> int:
    v = args.get('limit', default)
    if isinstance(v, bool) or not isinstance(v, int) or not 1 <= v <= hi:
        raise ToolError(f'"limit" must be an integer from 1 to {hi}')
    return v


def _skip(entry) -> bool:
    """Noms cachés en « . » ou « $ », liens et jonctions : jamais montrés ni suivis."""
    from ..core.fav_index import _reparse
    return entry.name.startswith(('.', '$')) or _reparse(entry)


def _capped(out: dict, key: str) -> dict:
    """La réponse ramenée à MAX_REPLY caractères : les dernières entrées de `out[key]` retirées au besoin."""
    note = out.get('note', '')
    for k in (key, 'layers'):                            # les entrées, puis les calques
        rows = out.get(k)
        if not isinstance(rows, list):
            continue
        n = len(rows)
        while rows and len(json.dumps(out, ensure_ascii=False)) > MAX_REPLY:
            rows.pop()                                   # (la note de l'abrègement comptée dans la taille)
            out['truncated'] = True
            out['note'] = (note + ' ' if note else '') + \
                f'reply shortened to {len(rows)} of {n} {k}: narrow the request'
        if len(rows) < n:
            note = out['note']
    return out


def _texts(texts, n=None, each=TEXT_CHARS, total=TEXTS_CHARS) -> list:
    from ..core.shape_index import clip_texts
    return clip_texts(list(texts or ())[:n] if n else texts, each, total)


# --- les outils -----------------------------------------------------------------------------------------------
def folders_allowed(win, _args: dict) -> dict:
    from ..core import shape_index as SI
    from ..ui import shape_search as SS
    allow = roots(win)
    st = _settings(win)
    idx = SS.index()
    s = idx.summary(allow)
    return {'folders': [{'path': r, 'reachable': _real(os.path.abspath(r)) is not None} for r in allow],
            'index': {'files': s['files'], 'drawings': s['drawings'], 'unreadable': s['unreadable'],
                      'to_refresh': idx.stale(SS.params(st), allow) if st is not None else 0},
            'formats': list(SS.exts(st)) if st is not None else list(SI.DEFAULT_EXTS),
            'note': 'read only; the user updates the index by hand (Index tab, "Update the index")'}


def _entries(folder: str, t_end: float):
    """(entrées du dossier, complet) : au plus MAX_SCAN entrées, avant `t_end`."""
    got, done = [], True
    try:
        with os.scandir(folder) as sc:
            for e in sc:
                if len(got) >= MAX_SCAN or time.monotonic() > t_end:
                    done = False
                    break
                got.append(e)
    except OSError as ex:
        raise ToolError(f'the folder could not be read: {ex}') from ex
    return got, done


def folder_list(win, args: dict) -> dict:
    folder = resolve(win, args.get('path'), 'dir')
    limit = _limit(args, 200, MAX_LISTED)
    entries, done = _entries(folder, time.monotonic() + DEADLINE)
    rows = []
    for e in entries:
        try:
            if _skip(e):
                continue
            st = e.stat(follow_symlinks=False)
            if e.is_dir(follow_symlinks=False):
                rows.append({'name': e.name, 'type': 'folder', 'modified': _when(st.st_mtime)})
            elif e.is_file(follow_symlinks=False):
                rows.append({'name': e.name, 'type': 'file', 'size': st.st_size, 'modified': _when(st.st_mtime)})
        except OSError:
            continue
    rows.sort(key=lambda r: (r['type'] != 'folder', r['name'].lower()))
    out = {'path': folder, 'entries': rows[:limit], 'total': len(rows), 'complete': done}
    if not done:
        out['note'] = 'very large folder: only part of it was read; use files_find with a name or extensions'
    return _capped(out, 'entries')


def files_find(win, args: dict) -> dict:
    from ..core.shape_index import fold
    allow = allowed(win)
    if not allow:
        raise ToolError(NO_FOLDER)
    name = args.get('name') or ''
    if not isinstance(name, str):
        raise ToolError('"name" must be a text')
    exts = args.get('extensions') or []
    if not isinstance(exts, list) or not all(isinstance(e, str) for e in exts):
        raise ToolError('"extensions" must be a list such as [".dxf", ".vnd"]')
    exts = {('.' + e.lower().lstrip('.')) for e in exts if e.strip()}
    after, before = _date(args.get('modified_after'), 'modified_after'), _date(args.get('modified_before'),
                                                                              'modified_before')
    limit = _limit(args, 100, MAX_LISTED)
    recursive = args.get('recursive', True)
    if not isinstance(recursive, bool):
        raise ToolError('"recursive" must be true or false')
    starts = [resolve(win, args['folder'], 'dir', allow)] if args.get('folder') is not None else \
        [r for _a, r in allow if r is not None]
    pattern = fold(name.strip())
    glob = any(c in pattern for c in '*?[')
    words = pattern.split()
    found, scanned, seen = [], 0, set()
    stack = list(reversed(starts))
    t_end = time.monotonic() + DEADLINE
    stopped = ''
    while stack and not stopped:
        folder = stack.pop()
        subs = []
        try:
            with os.scandir(folder) as sc:
                for e in sc:                             # plafonds vérifiés à chaque entrée
                    scanned += 1
                    if scanned > MAX_SCAN or time.monotonic() > t_end:
                        stopped = 'entries' if scanned > MAX_SCAN else 'time'
                        break
                    try:
                        if _skip(e):
                            continue
                        if e.is_dir(follow_symlinks=False):
                            subs.append(e.path)
                            continue
                        if not e.is_file(follow_symlinks=False):
                            continue
                        n = fold(e.name)
                        if exts and os.path.splitext(n)[1] not in exts:
                            continue
                        if pattern and not (fnmatch.fnmatchcase(n, pattern) if glob else all(w in n for w in words)):
                            continue
                        st = e.stat(follow_symlinks=False)
                        if (after is not None and st.st_mtime < after) or (before is not None and st.st_mtime > before):
                            continue
                        k = _key(e.path)
                        if k not in seen:
                            seen.add(k)
                            found.append({'path': e.path, 'size': st.st_size, 'modified': _when(st.st_mtime)})
                            if len(found) >= limit:
                                stopped = 'limit'
                                break
                    except OSError:
                        continue
        except OSError:
            continue
        if recursive:
            stack.extend(sorted(subs, key=str.lower, reverse=True))
    found.sort(key=lambda f: f['path'].lower())
    done = not stopped and (not stack or not recursive)
    out = {'files': found, 'complete': done}
    if stopped in ('entries', 'time'):
        out['note'] = 'stopped early (too many entries or too long): partial result; narrow the search (folder, ' \
                      'name, extensions)'
    elif stopped == 'limit':
        out['note'] = f'the first {limit} files found: raise "limit" or narrow the search for more'
    return _capped(out, 'files')


def drawing_info(win, args: dict) -> dict:
    """Les informations d'un dessin : de l'index s'il y est à jour, sinon lu (en lecture seule)."""
    from ..core import shape_index as SI
    from ..ui import shape_search as SS
    path = resolve(win, args.get('path'), 'file')
    ext = os.path.splitext(path)[1].lower()
    if not SI.norm_exts([ext]):
        raise ToolError(f'"{ext}" is not a drawing format read by the application itself')
    st = os.stat(path)
    out = {'path': path, 'size_bytes': st.st_size, 'modified': _when(st.st_mtime)}
    rec = SS.index().files.get(SI.key_of(path))
    if rec and rec.get('size') == st.st_size and rec.get('mtime') == st.st_mtime and 'error' not in rec:
        out.update({'width': rec.get('w'), 'height': rec.get('h'), 'contours': rec.get('contours'),
                    'layers': [dict(L) for L in (rec.get('layers') or [])[:SI.MAX_LAYERS]],
                    'texts': _texts(rec.get('texts')),
                    'from_index': True})
        return _capped(out, 'texts')
    doc = _read(path, st)
    d = SI.describe(doc, SS.params(_settings(win)))
    layers = d['layers']
    for L, src in zip(layers, doc.layers):
        L['visible'] = bool(getattr(src, 'visible', True))
    out.update({'width': d['w'], 'height': d['h'], 'contours': d['contours'],
                'objects': sum(len(L.items) for L in doc.layers), 'layers': layers,
                'texts': _texts(d['texts']), 'from_index': False})
    if len(doc.layers) > len(layers):
        out['note'] = f'the first {len(layers)} of {len(doc.layers)} layers'
    return _capped(out, 'texts')


def _read(path: str, st):
    """Le dessin lu (hors de l'index) : refus clair au-delà de MAX_FILE_BYTES, ou s'il ne se lit pas."""
    from ..core import shape_index as SI
    if st.st_size > MAX_FILE_BYTES:
        raise ToolError(f'the drawing is too large to be read here ({st.st_size / 1048576:.1f} MB, at most '
                        f'{MAX_FILE_BYTES / 1048576:.0f} MB): the user can index its folder (Index tab) or open it')
    try:
        return SI.read_drawing(path)
    except Exception as ex:                              # noqa: BLE001 — illisible : dit au modèle
        raise ToolError(f'the drawing could not be read: {type(ex).__name__}: {str(ex)[:200]}') from ex


def _bool(args: dict, key: str):
    v = args.get(key)
    if v is not None and not isinstance(v, bool):
        raise ToolError(f'"{key}" must be true or false')
    return v


def _num(args: dict, key: str):
    v = args.get(key)
    if v is None:
        return None
    if isinstance(v, bool) or not isinstance(v, (int, float)) or v != v or not 0 <= v <= 1e6:
        raise ToolError(f'"{key}" must be a number from 0 to 1000000')
    return float(v)


def shape_search(win, args: dict) -> dict:
    """Les dessins de l'index (dans les dossiers permis) semblables à la sélection, au dessin, à un fichier, ou
    selon des critères."""
    import dataclasses
    from ..core import shape_index as SI
    from ..ui import shape_search as SS
    allow = allowed(win)
    if not allow:
        raise ToolError(NO_FOLDER)
    folders = [a for a, _r in allow]
    st = _settings(win)
    idx = SS.index()
    P, M = SS.params(st), SS.match(st)
    over = {k: _bool(args, k) for k in ('scale', 'rotation', 'mirror')}
    M = dataclasses.replace(M, **{k: v for k, v in over.items() if v is not None})
    if args.get('threshold') is not None:
        t = _num(args, 'threshold')
        if t > 100:
            raise ToolError('"threshold" must be from 0 to 100 (%)')
        M.threshold = t
    M.limit = _limit(args, min(M.limit, 20), MAX_RESULTS)
    M = M.clean()
    source = args.get('source', 'selection')
    if source not in ('selection', 'drawing', 'file', 'criteria'):
        raise ToolError('"source" must be "selection", "drawing", "file" or "criteria"')
    path = resolve(win, args.get('path'), 'file', allow) if source == 'file' else None     # refusé avant tout
    summary = idx.summary(folders)
    base = {'index_files': summary['files'], 'settings': {'scale_ignored': M.scale, 'rotation_ignored': M.rotation,
                                                          'mirror_ignored': M.mirror, 'threshold': M.threshold}}
    if not summary['files']:
        return dict(base, results=[], note='the index is empty: the user indexes the folders by hand (Index tab)')
    if source == 'criteria':
        def rng(lo, hi):
            a, b = _num(args, lo), _num(args, hi)
            return (a, b) if a is not None or b is not None else None
        text, name = args.get('text') or '', args.get('name') or ''
        if not isinstance(text, str) or not isinstance(name, str):
            raise ToolError('"text" and "name" must be texts')
        recs = idx.find(width=rng('min_width', 'max_width'), height=rng('min_height', 'max_height'),
                        contours=rng('min_contours', 'max_contours'), text=text, name=name, folders=folders,
                        limit=M.limit)
        return _capped(dict(base, results=[_row(None, r) for r in recs]), 'results')
    if not idx.records(P, folders):
        return dict(base, results=[], note='the index must be updated (the indexing settings changed since): the '
                                           'user does it in the Index tab')
    skip = None
    if source == 'file':
        rec = idx.files.get(SI.key_of(path))
        fs = os.stat(path)
        if rec and rec.get('sig') and rec.get('p') == P.digest() and rec.get('size') == fs.st_size \
                and rec.get('mtime') == fs.st_mtime:
            sig = rec['sig']
        else:
            sig = SI.describe(_read(path, fs), P)['sig']
        skip = path
    else:
        canvas = win.canvas
        sel = list(canvas.selection) if source == 'selection' else []
        sig = SI.signature(sel or SI.doc_items(canvas.doc, P.hidden), P)
        if not sel:
            skip = getattr(win, 'path', None)
    if sig is None:
        raise ToolError('nothing to compare: no contour large enough (the minimum size is set by the user)')
    found = idx.search(sig, M, P, folders=folders, exclude=[skip] if skip else ())
    return _capped(dict(base, results=[_row(s, r, sims) for s, r, sims in found],
                        note='the user opens a result by double-clicking it in File > Similar drawings'), 'results')


def _row(score, rec, sims=None) -> dict:
    d = {'path': rec['path'], 'width': rec.get('w'), 'height': rec.get('h'), 'contours': rec.get('contours'),
         'texts': _texts(rec.get('texts'), ROW_TEXTS, ROW_TEXT_CHARS, ROW_TEXTS * ROW_TEXT_CHARS)}
    if score is not None:
        d['score'] = score
        d['criteria'] = {k: round(v, 3) for k, v in (sims or {}).items()}
    return d
