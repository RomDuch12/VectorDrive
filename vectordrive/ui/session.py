"""Session silencieuse : à la fermeture (et toutes les quelques minutes),
tout l'état de travail est gardé — onglets de dessins, avec leurs
modifications non enregistrées, vue, parcours FAO, onglet courant, onglet
du ruban, place des panneaux et de la fenêtre — et rendu tel quel au
démarrage suivant, sans question. Les fichiers de l'utilisateur ne sont
jamais écrits : un dessin modifié est gardé à part (dans la session) et
revient « modifié », à enregistrer quand on le décide.

Dossier : `session/` des données de VectorDrive (`VECTORDRIVE_SESSION` :
autre dossier, pour les essais). Un verrou empêche deux fenêtres d'écrire
la même session.
"""
from __future__ import annotations

import datetime as dt
import array
import gzip
import json
import os
import pathlib
import struct

VERSION = 1
INDEX = 'session.json'


def default_dir() -> pathlib.Path:
    if os.environ.get('VECTORDRIVE_SESSION'):
        return pathlib.Path(os.environ['VECTORDRIVE_SESSION'])
    from ..portable import data_dir
    return data_dir() / 'session'


# --- parcours ------------------------------------------------------------------------------
#: parcours : en-tête JSON puis colonnes binaires (natures en un octet, coordonnées
#: en float64), le tout gzip — 10 × plus petit en mémoire et 4 × plus vite écrit que
#: le JSON des mouvements (2 millions de mouvements : 133 Mo de texte, 5 s)
PATHS_MAGIC = b'VDP1'
KINDS = ('rapid', 'feed', 'plunge', 'arc_cw', 'arc_ccw')


def paths_key(tps) -> tuple:
    """Identité des parcours affichés : change à chaque recalcul (nouveaux
    objets), quand on coche, décoche ou inverse un parcours (gardés avec
    lui), pas quand on déplace un onglet."""
    return tuple((getattr(tp, 'uid', id(tp)), bool(getattr(tp, 'shown', True)), bool(getattr(tp, 'reversed', False)))
                 for tp in tps)


def fin_spans(moves) -> list:
    """[[début, fin)] des suites de mouvements d'une passe de finition (`Move.fin`)."""
    out, start = [], None
    for i, m in enumerate(moves):
        if getattr(m, 'fin', False):
            if start is None:
                start = i
        elif start is not None:
            out.append([start, i])
            start = None
    if start is not None:
        out.append([start, len(moves)])
    return out


def paths_bytes(tps) -> bytes:
    """Parcours → octets (voir PATHS_MAGIC). Peut tourner dans un fil de
    fond : un parcours affiché n'est plus modifié (un recalcul en fait un
    nouveau)."""
    heads, blobs = [], []
    for tp in tps:
        moves = tp.moves
        kinds = [m.kind for m in moves]
        table = list(KINDS) + sorted(set(kinds) - set(KINDS))
        code = {k: i for i, k in enumerate(table)}
        heads.append({'op_id': tp.op_id, 'tool_id': tp.tool_id, 'name': tp.name, 'source': tp.source,
                      'warnings': list(tp.warnings), 'cycles': list(tp.cycles),
                      'shown': bool(getattr(tp, 'shown', True)), 'reversed': bool(getattr(tp, 'reversed', False)),
                      'zones': list(getattr(tp, 'zones', None) or []),
                      'n': len(moves), 'kinds': table[len(KINDS):],
                      'fin': fin_spans(moves)})
        blobs.append(bytes(code[k] for k in kinds))
        for col in ([m.x for m in moves], [m.y for m in moves], [m.z for m in moves],
                    [m.cx for m in moves], [m.cy for m in moves]):
            blobs.append(array.array('d', col).tobytes())
    head = json.dumps(heads, ensure_ascii=False).encode('utf-8')
    return gzip.compress(PATHS_MAGIC + struct.pack('<I', len(head)) + head + b''.join(blobs), 3)


def paths_from_bytes(data: bytes) -> list:
    """Octets (PATHS_MAGIC) ou ancien JSON gzip → parcours."""
    from ..cam.model import Move, Toolpath
    raw = gzip.decompress(data)
    if not raw.startswith(PATHS_MAGIC):
        return _paths_from_json(json.loads(raw))
    (hlen,) = struct.unpack_from('<I', raw, 4)
    heads = json.loads(raw[8:8 + hlen].decode('utf-8'))
    pos = 8 + hlen
    out = []
    for h in heads:
        n = int(h['n'])
        table = list(KINDS) + list(h.get('kinds', []))
        kinds = raw[pos:pos + n]
        pos += n
        cols = []
        for _ in range(5):
            a = array.array('d')
            a.frombytes(raw[pos:pos + 8 * n])
            cols.append(a)
            pos += 8 * n
        tp = Toolpath(op_id=h.get('op_id', ''), tool_id=h.get('tool_id', ''), name=h.get('name', ''),
                      source=h.get('source', 'vectordrive'), warnings=list(h.get('warnings', [])),
                      cycles=list(h.get('cycles', [])), zones=list(h.get('zones', [])),
                      moves=[Move(table[k], x, y, z, cx, cy) for k, x, y, z, cx, cy in zip(kinds, *cols)])
        for a, b in h.get('fin', []):                    # les passes de finition (leur avance)
            for i in range(max(0, int(a)), min(int(b), len(tp.moves))):
                tp.moves[i].fin = True
        tp.shown = bool(h.get('shown', True))
        if h.get('reversed'):
            tp.reversed = True
        out.append(tp)
    return out


def _paths_from_json(data) -> list:
    """Sessions d'avant (parcours_n.json.gz)."""
    from ..cam.model import Move, Toolpath
    out = []
    for d in data or []:
        tp = Toolpath(op_id=d.get('op_id', ''), tool_id=d.get('tool_id', ''), name=d.get('name', ''),
                      source=d.get('source', 'vectordrive'), warnings=list(d.get('warnings', [])),
                      cycles=list(d.get('cycles', [])),
                      moves=[Move(k, x, y, z, cx, cy) for k, x, y, z, cx, cy in d.get('moves', [])])
        tp.shown = bool(d.get('shown', True))
        out.append(tp)
    return out


# --- écriture ------------------------------------------------------------------------------
def snapshot(win) -> dict:
    """État de la fenêtre à garder (rapide, dans le fil principal) :
    {'docs': [(entrée, instantané du dessin ou None, parcours ou None)], 'written': {…}}.
    Les parcours sont donnés tels quels : `write` les sérialise (fil de fond)
    et ne réécrit pas ceux qui n'ont pas changé depuis la dernière fois."""
    from ..io import native
    win._store_current()
    docs = []
    for i, t in enumerate(win.docs):
        if t.pristine() and len(win.docs) > 1:
            continue                                     # onglet vide : rien à garder
        keep_doc = t.modified or not t.path or not pathlib.Path(t.path).exists()
        entry = {'path': t.path, 'modified': bool(t.modified), 'view': list(t.view) if t.view else None,
                 'source': getattr(t.doc, 'source_path', None) or None, 'file': None, 'paths': None,
                 'current': i == win.doc_index, 'uid': t.uid}
        cp = getattr(win, 'cam_panel', None)
        if cp is not None and t.toolpaths:                 # ce qu'on savait de leur calcul : gardé avec eux
            entry['cam'] = cp.memo_of(t.doc)
            if not keep_doc:                               # relu depuis son fichier : celui du calcul ?
                seen = getattr(win, '_file_stamps', {}).get(os.path.normcase(os.path.abspath(t.path)))
                entry['stamp'] = list(seen) if seen else None   # tel qu'il a été lu (pas changé depuis par un
                #                                                 autre poste) ; inconnu : mémo pas repris
        snap = native.snapshot(t.doc) if keep_doc and not t.pristine() else None
        docs.append((entry, snap, list(t.toolpaths) if t.toolpaths else None))
    r = win.ribbon
    return {'docs': docs, 'written': dict(getattr(win, '_session_written', {}) or {}), 'win': win,
            'ribbon': r.tabText(r.currentIndex()) if r.currentIndex() >= 0 else '',
            'geometry': bytes(win.saveGeometry().toBase64()).decode('ascii'),
            'state': bytes(win.saveState().toBase64()).decode('ascii')}


def _stamp(path):
    """Empreinte d'un fichier (date fine, taille), ou None."""
    try:
        st = pathlib.Path(path).stat()
    except (OSError, TypeError, ValueError):
        return None
    return [st.st_mtime_ns, st.st_size]


#: VND d'origine déjà nommés : objet (gardé tant qu'un onglet l'a) → nom du fichier, pour ne pas le relire à chaque écriture
_SOURCE_NAMES: dict = {}


def _source_file(data: bytes, folder: pathlib.Path, names: dict) -> str:
    """Le VND d'origine d'un dessin, à côté des dessins de la session, nommé par son empreinte : écrit une fois, pas à
    chaque sauvegarde de la session."""
    import hashlib
    prev = _SOURCE_NAMES.get(id(data))
    name = prev[1] if prev and prev[0] is data else f'source_{hashlib.sha1(data).hexdigest()[:16]}.vnd'
    names[id(data)] = (data, name)
    p = folder / name
    if not p.exists():
        tmp = folder / (name + '.tmp')
        tmp.write_bytes(data)
        tmp.replace(p)
    return name


def _attach_source(doc, folder: pathlib.Path, entry: dict) -> None:
    """Le dessin rouvert de la session retrouve le VND dont il vient."""
    name = entry.get('vnd_source')
    if not name or not isinstance(getattr(doc, 'extra', None), dict) or doc.extra.get('vnd_source'):
        return
    try:
        data = (folder / pathlib.Path(name).name).read_bytes()
    except OSError:
        return
    from ..io import native
    native.attach_source(doc, data)


def write(snap: dict, folder: pathlib.Path) -> pathlib.Path:
    """Écrit un instantané (peut tourner dans un fil de fond) ; rend l'index.
    Les parcours d'un onglet sont réécrits seulement s'ils ont changé depuis
    la dernière écriture (`snap['written']` : uid de l'onglet → (clé, fichier)).
    Le VND d'origine d'un dessin est écrit à part, une seule fois."""
    global _SOURCE_NAMES
    from ..io import native
    folder = pathlib.Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    entries, keep = [], {INDEX, 'session.lock'}
    written, done = snap.get('written') or {}, {}
    names: dict = {}
    for n, (entry, doc_snap, paths) in enumerate(snap['docs']):
        e = dict(entry)
        uid = e.pop('uid', None) or str(n)
        if doc_snap is not None:
            e['file'] = f'dessin_{n}.vdz'
            src = native.vnd_source(doc_snap)
            if src is not None:
                data = doc_snap.extra['vnd_source']
                e['vnd_source'] = _source_file(data if isinstance(data, bytes) else src, folder, names)
                keep.add(e['vnd_source'])
                doc_snap.extra = {k: v for k, v in doc_snap.extra.items() if k != 'vnd_source'}
            native.write_atomic(doc_snap, folder / e['file'], level=1)
            keep.add(e['file'])
        if paths:
            key = paths_key(paths)
            prev = written.get(uid)
            if prev and prev[0] == key and (folder / prev[1]).exists():
                e['paths'] = prev[1]                     # inchangés : fichier gardé
            else:
                e['paths'] = f'parcours_{uid}.vdp'
                tmp = folder / (e['paths'] + '.tmp')
                tmp.write_bytes(paths_bytes(paths))
                tmp.replace(folder / e['paths'])
            keep.add(e['paths'])
            done[uid] = (key, e['paths'])
        entries.append(e)
    _SOURCE_NAMES = names
    win = snap.get('win')
    if win is not None:
        win._session_written = done
    index = {'version': VERSION, 'saved': dt.datetime.now().isoformat(timespec='seconds'), 'docs': entries,
             'ribbon': snap.get('ribbon', ''), 'geometry': snap.get('geometry', ''), 'state': snap.get('state', '')}
    tmp = folder / (INDEX + '.tmp')
    tmp.write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding='utf-8')
    tmp.replace(folder / INDEX)
    for f in folder.iterdir():                           # dessins d'onglets fermés depuis
        if f.is_file() and f.name not in keep and not f.name.endswith('.tmp'):
            f.unlink(missing_ok=True)
    return folder / INDEX


def save(win, folder) -> pathlib.Path:
    return write(snapshot(win), pathlib.Path(folder))


# --- lecture -------------------------------------------------------------------------------
def load_index(folder) -> dict | None:
    p = pathlib.Path(folder) / INDEX
    try:
        data = json.loads(p.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) and data.get('version') == VERSION else None


def restore(win, folder) -> int:
    """Rouvre la session (sans question) ; rend le nombre d'onglets rendus.
    Un dessin introuvable ou illisible est signalé dans la barre d'état et
    laissé de côté."""
    from ..io import registry
    folder = pathlib.Path(folder)
    index = load_index(folder)
    if not index or not index.get('docs'):
        return 0
    restored, missing, current = 0, [], 0
    for e in index['docs']:
        doc, path = None, e.get('path')
        try:
            if e.get('file') and (folder / e['file']).exists():
                doc = registry.open_document(str(folder / e['file']))
                _attach_source(doc, folder, e)
                doc.source_path = e.get('source') or path or ''
                win._open_in_tab(doc, path, modified=bool(e.get('modified')))
            elif path and pathlib.Path(path).exists():
                if not win.open_path(path):
                    raise OSError(path)
            else:
                missing.append(path or e.get('source') or '?')
                continue
        except Exception:                                  # un dessin abîmé n'empêche pas les autres
            missing.append(path or e.get('file') or '?')
            continue
        t = win.docs[win.doc_index]
        if e.get('view') and len(e['view']) == 3:
            win.canvas.scale, win.canvas.ox, win.canvas.oy = e['view']
            win.canvas.viewChanged.emit()
            win.canvas.update()
        if e.get('paths') and (folder / e['paths']).exists():
            try:
                tps = paths_from_bytes((folder / e['paths']).read_bytes())
                win.cam_panel.display(tps)
                memo = e.get('cam')
                if memo is not None and 'stamp' in e and _stamp(path) != e['stamp']:
                    memo = None                            # fichier changé depuis : calcul d'alors inconnu
                win.cam_panel.restore_memo(memo)           # sinon : « Calculer » avant la première écriture
            except (OSError, ValueError, TypeError, KeyError, struct.error):
                pass
        t.view = (win.canvas.scale, win.canvas.ox, win.canvas.oy)
        if e.get('current'):
            current = win.doc_index
        restored += 1
    if restored:
        win.switch_tab(current)
    if index.get('ribbon'):
        from ..i18n import tr
        r = win.ribbon
        title = index['ribbon']
        if title in (tr('FAO 2D'), tr('FAO 3D')):        # l'onglet FAO suit le mode du dessin rouvert
            title = tr('FAO 3D') if win.view_mode() == '3d' else tr('FAO 2D')
        i = next((k for k in range(r.count()) if r.tabText(k) == title and r.isTabVisible(k)), -1)
        if i >= 0:
            r.setCurrentIndex(i)
    if missing:
        from ..i18n import tr
        win.statusBar().showMessage(tr('Session : {0} dessin(s) introuvable(s) — {1}').format(
            len(missing), ', '.join(pathlib.Path(m).name for m in missing[:3])), 10000)
    return restored


def restore_window(win, folder, geometry: bool = True) -> bool:
    """Place et taille de la fenêtre, panneaux (à faire avant d'afficher) ; `geometry` faux : les panneaux seuls (la
    fenêtre s'ouvre en plein écran). Rend vrai si la place (les panneaux, sans `geometry`) est remise."""
    from PySide6.QtCore import QByteArray
    index = load_index(folder)
    if not index:
        return False
    ok = False
    if geometry and index.get('geometry'):
        ok = win.restoreGeometry(QByteArray.fromBase64(index['geometry'].encode('ascii')))
    if index.get('state'):
        state = win.restoreState(QByteArray.fromBase64(index['state'].encode('ascii')))
        ok = ok if geometry else bool(state)
    return ok
