"""Index des dossiers favoris de la fenêtre Ouvrir (demande du 20/11) : chercher un dossier, ou un fichier, dont le nom
contient un texte, parmi les favoris et tous leurs sous-dossiers.

La première fois, chaque dossier favori est parcouru en entier et retenu (ses sous-dossiers, leurs fichiers, la date
de chaque dossier). Les fois suivantes : d'abord ce que l'index connaît (instantané), puis ces résultats vérifiés
(toujours là ?), puis les nouveaux cherchés — seuls les dossiers dont la date a changé sont relus (un nom ajouté,
retiré ou renommé change la date de son dossier) —, enfin l'index réécrit s'il a changé.

Sans Qt : le fil de calcul de l'interface l'appelle (avancement et Annuler par `core.progress`)."""
from __future__ import annotations

import json
import os
import pathlib
import sys
import threading

from . import progress

VERSION = 1
#: au-delà, la recherche s'arrête (la liste montrée resterait illisible)
LIMIT = 4000


def key_of(path) -> str:
    """La clé d'un dossier favori : son chemin entier, sans casse sous Windows."""
    return os.path.normcase(os.path.abspath(str(path)))


def _join(root: str, rel: str) -> str:
    return os.path.join(root, rel) if rel else root


def _parent(rel: str) -> str:
    return os.path.dirname(rel)


class FavIndex:
    """L'index, gardé dans `path` (JSON). `hidden(entrée os.DirEntry)` : vrai pour un fichier ou un dossier caché ou
    système (omis, comme l'explorateur) ; None : seuls les noms en « . » et « $ » sont omis."""

    def __init__(self, path, hidden=None):
        self.path = pathlib.Path(path)
        self.hidden = hidden
        #: dossier favori (clé) → {'root': chemin tel quel, 'dirs': {chemin relatif: [date, [fichiers], [sous-dossiers]]}}
        self.roots: dict = {}
        self.dirty = False
        #: tenu par `search` (fil de calcul) : après Annuler, ce fil finit son dossier en cours avant de rendre la main
        self.lock = threading.Lock()
        self._trust: dict = {}
        self.load()

    # --- le fichier ------------------------------------------------------------------------------------------------
    def load(self) -> None:
        try:
            data = json.loads(self.path.read_text(encoding='utf-8', errors='surrogatepass'))
        except (OSError, ValueError):
            return
        if isinstance(data, dict) and data.get('version') == VERSION and isinstance(data.get('roots'), dict):
            self.roots = {k: v for k, v in data['roots'].items() if _well_formed(v)}

    def save(self) -> bool:
        """Réécrit l'index s'il a changé (remplacement atomique). Rend vrai s'il a été écrit."""
        if not self.dirty:
            return False
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(f'{self.path.suffix}.{os.getpid()}.{threading.get_ident()}.tmp')
            tmp.write_text(json.dumps({'version': VERSION, 'roots': self.roots}, ensure_ascii=False),
                           encoding='utf-8', errors='surrogatepass')        # (un nom de fichier mal formé)
            os.replace(tmp, self.path)
        except (OSError, ValueError):
            try:
                tmp.unlink()
            except (OSError, NameError):
                pass
            return False
        self.dirty = False
        return True

    # --- lecture du disque ---------------------------------------------------------------------------------------
    def _skip(self, entry) -> bool:
        if entry.name.startswith(('.', '$')):
            return True
        if _reparse(entry):                              # jonction, lien : jamais suivis (boucles, arbres en double)
            return True
        try:
            return bool(self.hidden is not None and self.hidden(entry))
        except OSError:
            return False

    def _read(self, folder: str):
        """(date, fichiers, sous-dossiers) du dossier ; None s'il est illisible ou disparu."""
        try:
            mtime = os.stat(folder).st_mtime
            with os.scandir(folder) as sc:
                entries = list(sc)
        except OSError:
            return None
        files, subs = [], []
        for e in entries:
            try:
                if self._skip(e):
                    continue
                if e.is_dir(follow_symlinks=False):
                    subs.append(e.name)
                elif e.is_file(follow_symlinks=False):
                    files.append(e.name)
            except OSError:
                continue
        return mtime, sorted(files, key=str.lower), sorted(subs, key=str.lower)

    @staticmethod
    def _drop(dirs: dict, rel: str) -> None:
        """Le dossier `rel` et tous ses sous-dossiers retirés de l'index."""
        stack = [rel]
        while stack:
            r = stack.pop()
            entry = dirs.pop(r, None)
            if entry:
                stack.extend(os.path.join(r, s) for s in entry[2])

    def indexed(self, root) -> bool:
        return key_of(root) in self.roots

    def update(self, root) -> bool | None:
        """Le favori `root` parcouru (en entier la première fois ; ensuite seuls les dossiers dont la date a changé
        sont relus, les autres seulement datés). Rend vrai si l'index a changé ; None s'il est injoignable. Annuler (core.progress) garde ce qui
        est déjà relu."""
        progress.check()                                 # (Annuler avant un accès disque qui peut durer)
        k = key_of(root)
        if not os.path.isdir(str(root)):                 # injoignable (réseau, clé débranchée) ou un fichier :
            return None                                  # son index reste tel quel pour son retour
        trust = self._trust.get(k)
        if trust is None:
            trust = self._trust[k] = _dates_reliable(str(root))
        rec = self.roots.get(k)
        if rec is None:
            rec = self.roots[k] = {'root': str(root), 'dirs': {}}
            self.dirty = True
        dirs = rec['dirs']
        changed = False
        stack, seen = [''], 0
        while stack:
            rel = stack.pop()
            progress.check()
            seen += 1
            task = progress.current() if seen % 50 == 0 else None
            if task is not None:
                task.fraction = -1.0
                task.text = f'{seen} dossiers vus'
            folder = _join(str(root), rel)
            old = dirs.get(rel)
            try:
                mtime = os.stat(folder).st_mtime
            except OSError:
                if rel == '':                            # la racine disparue en cours : rien d'oublié
                    break
                if old is not None:
                    self._drop(dirs, rel)
                    changed = self.dirty = True
                continue
            if old is None or old[0] != mtime or not trust:
                got = self._read(folder)
                if got is None:
                    continue
                new = [got[0], got[1], got[2]]
                if old is not None:
                    for gone in set(old[2]) - set(new[2]):
                        self._drop(dirs, os.path.join(rel, gone))
                if old != new:
                    dirs[rel] = new
                    changed = self.dirty = True          # tout de suite : Annuler garde ce qui est relu
            entry = dirs.get(rel)
            if entry is not None:
                stack.extend(os.path.join(rel, s) for s in reversed(entry[2]))
        if changed:
            self.dirty = True
        return changed

    def forget(self, keep) -> bool:
        """Les favoris retirés depuis : oubliés. `keep` : les dossiers favoris du moment."""
        want = {key_of(r) for r in keep}
        gone = [k for k in self.roots if k not in want]
        for k in gone:
            del self.roots[k]
        if gone:
            self.dirty = True
        return bool(gone)

    # --- recherche ----------------------------------------------------------------------------------------------
    def lookup(self, roots, kind: str, match, exts=None, limit: int = LIMIT) -> list[pathlib.Path]:
        """Ce que l'index connaît, sans toucher au disque : les dossiers (`kind` 'dossier') ou les fichiers ('fichier',
        d'extension dans `exts` si donnée) des favoris `roots` dont le nom répond à `match(nom)`."""
        exts = tuple(e.lower() for e in exts) if exts else None
        out, seen = [], set()
        for root in roots:
            rec = self.roots.get(key_of(root))
            if rec is None:
                continue
            for rel, (_m, files, subs) in sorted(rec['dirs'].items(), key=lambda kv: kv[0].lower()):
                folder = _join(str(root), rel)
                names = subs if kind == 'dossier' else files
                for n in names:
                    if kind != 'dossier' and exts is not None and os.path.splitext(n)[1].lower() not in exts:
                        continue
                    if match(n):
                        p = os.path.join(folder, n)
                        c = os.path.normcase(p)
                        if c not in seen:
                            seen.add(c)
                            out.append(pathlib.Path(p))
                            if len(out) >= limit:
                                return out
        return out

    @staticmethod
    def still_there(paths, kind: str) -> list[pathlib.Path]:
        """Les résultats toujours présents sur le disque."""
        out = []
        for p in paths:
            progress.check()                             # (un partage lent : Annuler sans attendre)
            if (os.path.isdir(p) if kind == 'dossier' else os.path.isfile(p)):
                out.append(p)
        return out

    def search(self, roots, kind: str, match, exts=None, limit: int = LIMIT, first=None,
               box: dict | None = None, extra=()) -> list[pathlib.Path]:
        """Toute la recherche, dans l'ordre demandé : `first` (ce que l'index a déjà donné, sinon relu) vérifié, puis
        chaque favori relu (en entier s'il n'est pas encore indexé), puis la réponse de l'index à jour. Rend les
        résultats ; `box['verifies']` : les premiers résultats vérifiés (ce qui reste si l'on annule ensuite). L'index
        est enregistré à la fin, même après Annuler (par ce fil, une fois son dossier en cours fini). `extra` : d'autres
        chemins à vérifier avec `first` (les favoris eux-mêmes)."""
        box = {} if box is None else box
        roots = top_roots(roots)
        with self.lock:
            try:
                progress.check()                         # annulée pendant l'attente du verrou : rien de plus
                if first is None:
                    first = self.lookup(roots, kind, match, exts, limit)
                box['verifies'] = self.still_there(list(extra) + list(first), kind)
                live = [r for r in roots if self.update(r) is not None]     # injoignable : ses résultats écartés
                return self.lookup(live, kind, match, exts, limit)
            finally:
                self.save()                              # ici, même après Annuler : ce fil a fini d'y toucher


def _well_formed(rec) -> bool:
    """Une entrée d'index lue du disque de la bonne forme (sinon : oubliée, le dossier sera réindexé)."""
    if not isinstance(rec, dict) or not isinstance(rec.get('root'), str) or not isinstance(rec.get('dirs'), dict):
        return False
    for rel, v in rec['dirs'].items():
        if not (isinstance(rel, str) and isinstance(v, list) and len(v) == 3 and isinstance(v[0], (int, float))
                and isinstance(v[1], list) and isinstance(v[2], list)
                and all(isinstance(n, str) for n in v[1]) and all(isinstance(n, str) for n in v[2])):
            return False
    return True


_SHARED: dict = {}
_SHARED_LOCK = threading.Lock()


def shared(path, hidden=None) -> FavIndex:
    """L'index de `path`, un seul par fichier pour tout le programme (chaque fenêtre Ouvrir le reprend : un seul
    verrou, pas deux écritures croisées)."""
    k = key_of(path)
    with _SHARED_LOCK:
        idx = _SHARED.get(k)
        if idx is None:
            idx = _SHARED[k] = FavIndex(path, hidden=hidden)
        return idx


#: points d'analyse jamais suivis : jonction (IO_REPARSE_TAG_MOUNT_POINT), lien (IO_REPARSE_TAG_SYMLINK) ; les
#: autres (OneDrive « fichiers à la demande », déduplication…) sont des fichiers et dossiers ordinaires
LINK_TAGS = (0xA0000003, 0xA000000C)


def _reparse(entry) -> bool:
    """Vrai pour une jonction ou un lien symbolique (jamais suivis : boucles, arbres en double)."""
    try:
        if entry.is_symlink():
            return True
        junction = getattr(entry, 'is_junction', None)   # Python 3.12
        if junction is not None:
            return bool(junction())
        st = entry.stat(follow_symlinks=False)
        if not getattr(st, 'st_file_attributes', 0) & 0x400:     # FILE_ATTRIBUTE_REPARSE_POINT
            return False
        tag = getattr(st, 'st_reparse_tag', 0) or getattr(os.lstat(entry.path), 'st_reparse_tag', 0)
        return tag in LINK_TAGS
    except OSError:
        return False


def _dates_reliable(root: str) -> bool:
    """Faux pour un volume FAT ou exFAT (clé USB, carte) : la date d'un dossier n'y suit pas toujours ses
    changements ; chaque dossier y est alors relu."""
    if sys.platform != 'win32':
        return True
    try:
        import ctypes
        drive = os.path.splitdrive(os.path.abspath(root))[0]
        if not drive:
            return True
        buf = ctypes.create_unicode_buffer(64)
        ok = ctypes.windll.kernel32.GetVolumeInformationW(ctypes.c_wchar_p(drive.rstrip('\\') + '\\'), None, 0,
                                                          None, None, None, buf, len(buf))
        return not (ok and buf.value.upper().startswith(('FAT', 'EXFAT')))
    except (OSError, AttributeError, ValueError):
        return True


def top_roots(roots) -> list[pathlib.Path]:
    """Les dossiers favoris, sans ceux déjà compris dans un autre (indexés une fois) ni les doublons."""
    paths = []
    for r in roots:
        k = key_of(r)
        if not any(k == key_of(o) for o in paths):
            paths.append(pathlib.Path(r))
    keys = [key_of(p) for p in paths]
    out = []
    for p, k in zip(paths, keys):
        inside = any(o != k and (k.startswith(o.rstrip(os.sep) + os.sep)) for o in keys)
        if not inside:
            out.append(p)
    return out
