"""Programmes en série (demande du 14/11 : « système d'automatisation de programmes (liste opés appliquée à un pattern
dessin gravure + brut) ») : chaque dessin d'un lot reçoit un modèle d'usinage (ses opérations, couleur par couleur),
ses parcours sont calculés et son programme machine est écrit — comme le post-traitement du panneau FAO (zéro du
programme, orientation de sortie, programmes par groupe), sans fenêtre. Les dessins ne sont jamais réécrits. Sans Qt."""
from __future__ import annotations

import pathlib
from dataclasses import dataclass, field

from ..core import progress


@dataclass
class SeriesResult:
    done: list = field(default_factory=list)        # (source, [fichiers écrits])
    skipped: list = field(default_factory=list)     # (source, raison)
    errors: list = field(default_factory=list)      # (source, message)
    warnings: list = field(default_factory=list)    # (source, avertissement du post-processeur)

    def summary(self) -> str:
        return (f'{len(self.done)} programme(s) écrit(s), {len(self.skipped)} ignoré(s), '
                f'{len(self.errors)} erreur(s)')


def stock_box(doc):
    """Boîte de la matière (mm) : la plaque du dessin, son épaisseur en Z (comme `CamPanel._stock_box`)."""
    pl = doc.plate
    if pl is None:
        return None
    return (pl.x, pl.y, -(pl.thickness or 0.0), pl.x + pl.width, pl.y + pl.height, 0.0)


def origin_of(doc, setup, key: str):
    """Zéro du programme (comme `CamPanel.program_origin`) : None au zéro du dessin."""
    from . import post
    o = doc.extra.get('origine') if isinstance(doc.extra, dict) else None
    try:
        x, y = float(o[0]), float(o[1])
        origin = (x, y) if abs(x) > 1e-12 or abs(y) > 1e-12 else None
    except (TypeError, ValueError, IndexError):
        origin = None
    zero = post.effective_zero(getattr(setup, 'program_zero', 'machine'), key)
    pt = post.zero_point(zero, doc.plate, origin)
    if pt is None or (abs(pt[0]) < 1e-12 and abs(pt[1]) < 1e-12):
        return None
    return float(pt[0]), float(pt[1])


def plan_of(doc, setup):
    """Pour les programmes par plan (TE : Grouper) : parcours → le plan (calque) du premier objet qu'il usine (comme
    `CamPanel._plan_of_path`)."""
    from . import strategies
    ops = {o.id: o for o in setup.operations}

    def name(tp) -> str:
        op = ops.get(tp.op_id)
        if op is None:
            return ''
        used = {id(it) for it in strategies.source_items(doc, op)}

        def has(it) -> bool:
            return id(it) in used or any(has(c) for c in getattr(it, 'children', ()))
        return next((L.name for L in doc.layers if any(has(it) for it in L.items)), '')
    return name


def setup_for(doc, tpl: dict | None, replace: bool = True, default_post: str = ''):
    """Le réglage FAO du dessin, avec le modèle appliqué (`replace` : à la place de ses opérations). Dessin sans
    réglage : le post-processeur des Options (`default_post`), comme `CamPanel.setup`."""
    from . import model, templates
    s = model.setup_of(doc)
    if default_post and 'fao' not in (doc.extra if isinstance(doc.extra, dict) else {}):
        s.post = default_post
    if tpl:
        s, _report = templates.apply(s, tpl, replace=replace)
    return s


def post_for(setup, key: str = '', machines_dir: str = '') -> str:
    """Le post-processeur : `key` s'il est donné, sinon celui du réglage, sinon le premier disponible."""
    from . import post
    if key:
        return key
    if setup.post.startswith('mah:') or setup.post in post.posts(''):
        return setup.post
    available = post.posts(machines_dir)
    return setup.post if setup.post in available else next(iter(available), '')


def _is_drawing(f: pathlib.Path) -> bool:
    """Un dessin lisible (pas un programme machine) : jamais remplacé par un programme (un post qui écrit du DXF…)."""
    from ..io import registry
    fmt = registry.by_extension(f)
    return fmt is not None and fmt.reader is not None and not fmt.machine


def _live(tp) -> bool:
    return bool(tp.moves or getattr(tp, 'cycles', None))


def program_one(src: str, out: str, tpl: dict | None = None, key: str = '', **kw) -> tuple:
    """Un dessin du lot (`_program_one`), les remarques de son compagnon (opérations perdues, fichier changé depuis
    lui…) en tête de ses avertissements : sans elles, elles n'iraient qu'au compte rendu du dessin, jamais montré."""
    notes: list = []
    kind, src, info, warnings = _program_one(src, out, tpl, key, notes=notes, **kw)
    return kind, src, info, notes + list(warnings)


def _program_one(src: str, out: str, tpl: dict | None = None, key: str = '', *, replace: bool = True,
                 overwrite: bool = False, machines_dir: str = '', default_post: str = '', dates: bool = True,
                 taken: dict | None = None, sources=(), notes: list | None = None) -> tuple:
    """Un dessin du lot : ('fait', source, [fichiers], avertissements) | ('ignoré' | 'erreur', source, raison, []).
    `out` : chemin du programme sans son extension (celle du post-processeur) ; `default_post` : le post-processeur
    des Options (dessin sans réglage) ; `dates` : |Date| et |Heure| à la date du moment (réglage « fao/dates ») ;
    `taken` : {fichier (casse ignorée) : dessin} des programmes déjà écrits par le lot (aucun n'en écrase un autre) ;
    `sources` : les dessins du lot (jamais remplacés)."""
    from ..core import surface2d, variables
    from ..io import companion
    from ..plugins import REGISTRY
    from . import mill3d, model, post, postcheck, preflight, strategies
    src_p, out_p = pathlib.Path(src), pathlib.Path(out)
    taken = {} if taken is None else taken
    try:
        doc = companion.open_document(src_p, notes=notes)  # comme à l'ouverture : son compagnon (round 1174)
        s = setup_for(doc, tpl, replace, default_post)
        if not any(o.enabled for o in s.operations):
            return 'ignoré', src, 'aucune opération (ni dans le dessin, ni dans le modèle)', []
        k = post_for(s, key, machines_dir)
        if not k:
            return 'erreur', src, 'aucun post-processeur (ils viennent des plugins)', []
        if k.startswith('mah:') and not pathlib.Path(k[4:]).exists():
            return 'erreur', src, f'fiche machine introuvable : {k[4:]}', []
        if REGISTRY.post_exports.get(k) or REGISTRY.post_exports.get(post.family(k)):
            return 'erreur', src, 'export propre à la machine (travail, dossier…) : passer par le panneau FAO', []
        s.post = k
        if dates:                                    # comme le calcul du panneau : la date du jour (en mémoire)
            variables.refresh_dates(doc)
        surface2d.follow(doc)                        # surfaces posées : elles suivent la pièce, comme au calcul
        surface2d.sync(doc, s)
        mill3d.bind_volumes(doc, s)
        model.store(doc, s)                          # le réglage appliqué, comme s'il était celui du dessin
        tps = strategies.compute_all(doc, s)
        if not any(_live(tp) for tp in tps):
            return 'ignoré', src, 'aucun parcours : les couleurs des opérations ne sont pas dans le dessin', []
        box = stock_box(doc)
        origin = origin_of(doc, s, k)
        how = getattr(s, 'output_orient', 'normal')
        if box is not None:                          # orientation de sortie, comme le post-traitement
            tps, origin, box = post.oriented(tps, how, (box[0], box[1], box[3], box[4]), origin, box)
        results = [(part, post.run(k, part, s, title=src_p.stem,
                                   stem=f'{out_p.name}_{suffix}' if suffix else out_p.name,
                                   box_mm=box, out_dir=str(out_p.parent), origin=origin, **post.attach_kw()))
                   for suffix, part in post.program_groups(tps, s.program_group, plan_of(doc, s))]
        files = [(out_p.parent / name, text, r.encoding) for _p, r in results for name, text in r.files]
        warnings = [w for _p, r in results for w in r.warnings]
        if not files:                                # export refusé (oscillation trop rapide…)
            return 'erreur', src, ' ; '.join(warnings[:3]) or 'aucun programme écrit', []
        blocking = preflight.safety(doc, s, tps, warnings)   # comme le post-traitement, même vérification coupée
        if blocking:
            return 'erreur', src, ' ; '.join(blocking[:3]), []
        mine = {str(p.resolve()).lower() for p in [src_p, *map(pathlib.Path, sources)]}
        for f, _t, _e in files:
            if str(f.resolve()).lower() in mine or (f.exists() and _is_drawing(f)):
                return 'erreur', src, f'le programme {f.name} remplacerait un dessin', []
            other = taken.get(str(f.resolve()).lower())
            if other is not None:
                return 'erreur', src, f'{f.name} : même fichier que le programme de {pathlib.Path(other).name}', []
        there = [f for f, _t, _e in files if f.exists()]
        if there and not overwrite:
            return 'ignoré', src, f'{there[0].name} existe déjà', []
        progress.check()                             # Annuler avant d'écrire : rien d'écrit pour ce dessin
        out_p.parent.mkdir(parents=True, exist_ok=True)
        for f, text, enc in files:
            f.write_text(text, encoding=enc, errors='replace', newline='\r\n')
            taken[str(f.resolve()).lower()] = src
        joined = []                                  # les fichiers joints (l'image de l'aperçu…), à côté
        for _p, r in results:
            skip = [f for f, _d in post.attachment_paths(r, out_p.parent)
                    if str(f.resolve()).lower() in mine or (f.exists() and (not overwrite or _is_drawing(f)))
                    or str(f.resolve()).lower() in taken]
            for f in post.write_attachments(r, out_p.parent, skip):
                taken[str(f.resolve()).lower()] = src
                joined.append(f)
            warnings += [w for w in r.warnings if w.startswith('fichier joint non écrit')]
        for part, r in results:                      # programme relu et comparé aux parcours, comme au post-traitement
            warnings = postcheck.verify(r.files, part, s, origin) + warnings
        return 'fait', src, [str(f) for f, _t, _e in files] + [str(f) for f in joined], warnings
    except progress.Cancelled:
        raise
    except Exception as ex:                          # un dessin abîmé n'arrête pas le lot
        return 'erreur', src, f'{type(ex).__name__} : {ex}', []


def programs(paths, out_dir='', tpl: dict | None = None, key: str = '', *, replace: bool = True,
             overwrite: bool = False, keep_tree_from=None, machines_dir: str = '', default_post: str = '',
             dates: bool = True) -> SeriesResult:
    """Le programme de chaque dessin de `paths`, l'un après l'autre (Annuler entre deux dessins) : dans `out_dir`
    (arborescence gardée sous `keep_tree_from` s'il est donné), sinon à côté de chaque dessin. Aucun programme du lot
    n'en remplace un autre, ni un dessin."""
    res = SeriesResult()
    taken: dict = {}
    sources = [str(p) for p in paths]
    jobs, seen = [], {}
    for src in (pathlib.Path(p) for p in paths):
        if out_dir:
            rel = pathlib.Path(src.name)
            if keep_tree_from is not None:
                try:
                    rel = src.resolve().relative_to(pathlib.Path(keep_tree_from).resolve())
                except ValueError:
                    rel = pathlib.Path(src.name)
            out = pathlib.Path(out_dir) / rel.parent / rel.stem
        else:
            out = src.parent / src.stem
        k = str(out).lower()
        if k in seen:                                # x.vnd et x.dxf : un seul programme x
            res.skipped.append((str(src), f'même programme que {pathlib.Path(seen[k]).name}'))
            continue
        seen[k] = str(src)
        jobs.append((str(src), str(out)))
    for i, (src, out) in enumerate(jobs):
        progress.step(i, len(jobs), 'Dessin {0} sur {1}')
        with progress.span(i / len(jobs), (i + 1) / len(jobs)):   # les parcours de ce dessin : sa part de la barre
            kind, src, info, warnings = program_one(src, out, tpl, key, replace=replace, overwrite=overwrite,
                                                    machines_dir=machines_dir, default_post=default_post,
                                                    dates=dates, taken=taken, sources=sources)
        {'fait': res.done, 'ignoré': res.skipped, 'erreur': res.errors}[kind].append((src, info))
        res.warnings += [(src, w) for w in warnings]
    return res
