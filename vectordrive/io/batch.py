"""Traitement par lots (comme celui de TypeEdit) : des dessins convertis d'un
coup dans un autre format — VND en DXF, PDF, SVG… — avec, au choix, un BAT
PDF de chacun ; ou seulement vérifiés (lus, comptés, rapport CSV). Sans
Qt : appelé dans un fil de calcul (barre de progression, Annuler entre
deux fichiers). Un lot assez grand est réparti sur plusieurs processus
(les fils de calcul de F10 › Performances) : la lecture des dessins est du
Python, un seul processus n'emploie qu'un cœur.
"""
from __future__ import annotations

import pathlib
from dataclasses import dataclass, field

from ..core import progress
from . import registry


@dataclass
class BatchResult:
    done: list = field(default_factory=list)        # (source, destination)
    skipped: list = field(default_factory=list)     # (source, raison)
    errors: list = field(default_factory=list)      # (source, message)
    notes: list = field(default_factory=list)       # (source, remarque) : converti, avec une réserve (round 1174)

    def summary(self) -> str:
        return f'{len(self.done)} converti(s), {len(self.skipped)} ignoré(s), {len(self.errors)} erreur(s)'


def writable_formats() -> list:
    return [f for f in registry.all_formats() if f.writer is not None]


def readable(path) -> bool:
    f = registry.by_extension(path)
    return f is not None and f.reader is not None


def is_program(path) -> bool:
    """Programme machine (G-code, Heidenhain, langages des plugins : SimPL…) ?"""
    from ..ui.nc_preview import is_program as _is
    return _is(path)


def collect(paths, *, recursive: bool = True, programs: bool = False) -> list[pathlib.Path]:
    """Fichiers lisibles : ceux donnés, et ceux des dossiers donnés ;
    `programs` : les programmes machine aussi (vérification)."""
    def wanted(f):
        return readable(f) or (programs and is_program(f))
    out = []
    for p in paths:
        p = pathlib.Path(p)
        if p.is_dir():
            it = p.rglob('*') if recursive else p.glob('*')
            out += sorted(f for f in it if f.is_file() and wanted(f))
        elif p.is_file() and wanted(p):
            out.append(p)
    seen, uniq = set(), []
    for f in out:
        k = str(f.resolve()).lower()
        if k not in seen:
            seen.add(k)
            uniq.append(f)
    return uniq


def processes(n_files: int) -> int:
    """Processus pour `n_files` fichiers restants (core.workers)."""
    from ..core import workers
    return workers.processes(n_files)


def _run_jobs(fn, jobs: list) -> list:
    """[fn(*job) for job in jobs], dans l'ordre : à la suite tant que le reste
    du lot s'annonce court, sinon sur plusieurs processus (core.workers)."""
    from ..core import workers
    return workers.adaptive_map(fn, jobs, text='Fichier {0} sur {1}')


def _convert_one(src: str, dst: str, overwrite: bool, proof: bool, live_texts: bool = False,
                 companion_mode: str = 'besoin') -> tuple:
    """Un fichier du lot : ('fait' | 'ignoré' | 'erreur', source, destination ou raison). `live_texts` : en VND,
    textes TypeEdit modifiables (le réglage du poste, pas celui resté dans le dessin). `companion_mode` : réglage
    « vnd/compagnon » pour une sortie TypeEdit ; compagnon refusé (round 1174) : ('fait', source, (destination,
    remarque))."""
    src_p, dst_p = pathlib.Path(src), pathlib.Path(dst)
    if dst_p.resolve() == src_p.resolve():
        return 'ignoré', src, 'même fichier'
    if dst_p.exists() and not overwrite:
        return 'ignoré', src, f'{dst_p.name} existe déjà'
    try:
        from . import companion
        doc = companion.open_document(src_p)              # comme à l'ouverture : son compagnon (round 1174)
        if isinstance(doc.extra, dict) and dst_p.suffix.lower() in ('.vnd', '.vnl', '.vnm'):
            doc.extra['vnd_textes_vivants'] = bool(live_texts)
            doc.extra.pop('vnd_premier_plan', None)     # l'ordre des calques du dessin (round 1099), pas un reste
        if isinstance(doc.extra, dict) and dst_p.suffix.lower() == '.vdz':
            doc.extra.pop('compagnon', None)           # lu du compagnon de la source : un VDZ n'en a pas
        dst_p.parent.mkdir(parents=True, exist_ok=True)
        registry.save_document(doc, dst_p)
        note = None
        if companion.te_native(dst_p):                 # comme Enregistrer (réglage « vnd/compagnon ») : à côté, ce
            try:                                       # que le fichier ne garde pas (outils des objets d'un calque
                companion.sync(doc, dst_p, mode=companion_mode)    # de plusieurs couleurs…) ; « jamais » : retiré
            except FileExistsError as ex:              # un x.vdz qui n'est pas un compagnon : fichier écrit, dit
                note = str(ex)
        if proof:
            from . import proof as P
            P.write(doc, dst_p.with_name(dst_p.stem + '_BAT.pdf'), P.ProofInfo(reference=src_p.stem))
        return 'fait', src, ((dst, note) if note else dst)
    except progress.Cancelled:
        raise
    except Exception as ex:                          # un fichier abîmé n'arrête pas le lot
        return 'erreur', src, f'{type(ex).__name__} : {ex}'


def convert(paths, out_dir, fmt_key: str, *, overwrite: bool = False, proof: bool = False,
            keep_tree_from=None, live_texts: bool = False, companion_mode: str = 'besoin') -> BatchResult:
    """Convertit chaque dessin dans le format `fmt_key`, dans `out_dir`
    (arborescence gardée sous `keep_tree_from` s'il est donné) ; un grand
    lot sur plusieurs processus. `live_texts` : en VND, textes TypeEdit
    modifiables (réglage `vnd/textes_vivants`). `companion_mode` : réglage `vnd/compagnon` (sortie TypeEdit)."""
    fmt = next((f for f in registry.all_formats() if f.key == fmt_key and f.writer), None)
    if fmt is None:
        raise ValueError(f'format sans écriture : {fmt_key}')
    out_dir = pathlib.Path(out_dir)
    res = BatchResult()
    jobs = []
    seen: dict = {}
    for src in (pathlib.Path(p) for p in paths):
        rel = src.name
        if keep_tree_from is not None:
            try:
                rel = str(src.resolve().relative_to(pathlib.Path(keep_tree_from).resolve()))
            except ValueError:
                rel = src.name
        dst = (out_dir / rel).with_suffix(fmt.extensions[0])
        key = str(dst).lower()
        if key in seen:                              # deux sources (x.vnd, x.gvt) pour une même sortie
            res.skipped.append((str(src), f'même fichier de sortie que {pathlib.Path(seen[key]).name}'))
            continue
        seen[key] = str(src)
        jobs.append((str(src), str(dst), overwrite, proof, live_texts, companion_mode))
    for kind, src, info in _run_jobs(_convert_one, jobs):
        if kind == 'fait' and isinstance(info, tuple):   # converti, compagnon refusé : la remarque à part
            info, note = info
            res.notes.append((src, note))
        {'fait': res.done, 'ignoré': res.skipped, 'erreur': res.errors}[kind].append((src, info))
    return res


# --- vérification ----------------------------------------------------------------------------------
CHECK_FIELDS = ('fichier', 'format', 'lu', 'objets', 'contours', 'segments', 'calques', 'typeedit13', 'remarques',
                'remarque', 'erreur', 'ms')


def typeedit13(src, fmt: str) -> str:
    """Le fichier est-il lisible tel quel par TypeEdit 13 (celui de
    l'atelier) ? 'oui', 'non : raison', ou '' hors formats TypeEdit."""
    if fmt == 'gvt':
        return 'non : GVT de TypeEdit 14 ou plus (enregistrer en VND avec VectorDrive)'
    if fmt not in ('vnd', 'vnl', 'vnm'):
        return ''
    from . import vnd
    from .vnd_write import v13_issues
    bad = v13_issues(vnd.parse(pathlib.Path(src).read_bytes())[0])
    return 'non : ' + bad[0] if bad else 'oui'


def check(paths) -> list[dict]:
    """Lit chaque dessin sans rien écrire : format, objets, contours,
    remarques du lecteur, erreur éventuelle, durée (pour des fichiers
    nouveaux venus de l'atelier) ; un grand lot sur plusieurs processus."""
    return _run_jobs(_check_one, [(str(p),) for p in paths])


def _check_program(src: pathlib.Path, row: dict) -> dict:
    """Ligne d'un programme machine : mouvements (objets), outils (contours), remarques du lecteur."""
    import time
    from ..cam import ncread
    from ..ui.nc_preview import read_program
    t0 = time.perf_counter()
    try:
        tp = read_program(src)
        head = src.read_text(encoding='utf-8', errors='replace')[:4000]
        parts = [q for q in (getattr(tp, 'parts', None) or []) if q.moves] or [tp]
        notes = [str(w) for w in tp.warnings]
        row.update(format='programme ' + ncread.dialect(head, src.name), lu=bool(tp.moves), objets=len(tp.moves),
                   contours=len(parts), segments=len(tp.moves), remarques=len(notes),
                   remarque=notes[0] if notes else '')
        if not tp.moves:
            row['erreur'] = notes[0] if notes else 'aucun mouvement lu'
    except Exception as ex:                              # noqa: BLE001 — programme illisible : la raison
        row['erreur'] = f'{type(ex).__name__} : {ex}'
    row['ms'] = int((time.perf_counter() - t0) * 1000)
    return row


def _check_one(path: str) -> dict:
    """Une ligne du rapport de vérification."""
    import time
    src = pathlib.Path(path)
    f = registry.by_extension(src)
    if f is None and is_program(src):
        row = dict.fromkeys(CHECK_FIELDS, '')
        row.update(fichier=str(src), lu=False)
        return _check_program(src, row)
    row = dict.fromkeys(CHECK_FIELDS, '')
    row.update(fichier=str(src), format=f.key if f else '?', lu=False)
    t0 = time.perf_counter()
    try:
        doc = registry.open_document(src)
        st = doc.stats()
        row.update(lu=True, objets=st['objets'], contours=st['contours'], segments=st['segments'],
                   calques=len(doc.layers), remarques=len(doc.report),
                   remarque=doc.report[0] if doc.report else '')
        try:
            row['typeedit13'] = typeedit13(src, row['format'])
        except Exception as ex:                     # lecture partielle : arbre incomplet
            row['typeedit13'] = f'? ({type(ex).__name__})'
    except progress.Cancelled:
        raise
    except Exception as ex:
        row['erreur'] = f'{type(ex).__name__} : {ex}'
    row['ms'] = int((time.perf_counter() - t0) * 1000)
    return row


def check_summary(rows) -> str:
    ok = sum(1 for r in rows if r['lu'])
    notes = sum(1 for r in rows if r['lu'] and r['remarques'])
    return f'{len(rows)} fichier(s) : {ok} lu(s), dont {notes} avec remarques ; {len(rows) - ok} en erreur'


def write_csv(rows, path) -> pathlib.Path:
    """Rapport CSV (séparateur ; pour Excel en français)."""
    import csv
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', newline='', encoding='utf-8-sig') as fh:
        w = csv.DictWriter(fh, fieldnames=list(CHECK_FIELDS), delimiter=';')
        w.writeheader()
        for r in rows:
            w.writerow({k: ('oui' if v is True else 'non' if v is False else v) for k, v in r.items()})
    return path
