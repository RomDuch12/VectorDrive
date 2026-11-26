"""Compagnon .vdz d'un VND : ce que le VND ne sait pas garder.

Enregistrer en VND (le format de TypeEdit) perd ce qui est propre à
VectorDrive : textes modifiables (écrits en courbes), objets paramétriques
(hachures, tampon, cadran, codes-barres… réglables), réglage FAO, guides,
calques masqués ou verrouillés. Quand il y en a, un `piece.vdz` est écrit à
côté de `piece.vnd` : un document VectorDrive complet (il s'ouvre seul),
plus `compagnon.json` qui le lie au VND :

    {"version": 1, "fichier": "piece.vnd", "format": "vnd",
     "sha256": "<empreinte du VND écrit>", "compteurs": [n objets par calque],
     "raisons": [...], "date": "2026-10-17T…"}

À l'ouverture du VND, le compagnon est relu :

* les données du document (FAO, guides…), l'état des calques : toujours ;
* les objets VectorDrive (textes modifiables, objets paramétriques) : à la
  place de leur version en courbes, **seulement si le VND n'a pas changé**
  (même empreinte : il n'a pas été retouché dans TypeEdit entre-temps) —
  sinon le VND fait foi et un message le dit.

Un compagnon devenu inutile (plus rien à garder) est supprimé ; un .vdz du
même nom sans `compagnon.json` est un document indépendant : jamais touché.

Les autres formats (DXF, SVG, PDF, EPS, AI, HPGL, SMB, images…) ont le même
compagnon, nommé d'après le fichier entier : `piece.dxf` → `piece.dxf.vdz`
(un dessin enregistré sous le même nom en deux formats garde un compagnon
pour chacun). Il est écrit quand `reasons` le demande, ou quand la relecture
du fichier qui vient d'être écrit ne rend pas le dessin tel quel (plaque,
table d'outils, calques, objets : `differences`). À l'ouverture : fichier
inchangé (même empreinte) — le dessin VectorDrive entier du compagnon est
repris ; fichier retouché ailleurs — il fait foi, et seuls le réglage FAO,
les guides et l'état des calques sont repris.

Une origine posée (`doc.extra['origine']`) devient le zéro du VND
(`vnd_write.at_origin`), pas celui du compagnon : à la relecture, le dessin
du VND est remis dans le repère de VectorDrive (+origine) avant d'y reprendre
le compagnon — même dessin, même origine, et le VND réécrit au même endroit.
"""
from __future__ import annotations

import datetime as dt
import functools
import hashlib
import json
import pathlib
import zipfile

from ..core.document import Document, Group, Image, Text
from . import native

LINK = 'compagnon.json'
#: clés de `doc.extra` que le VND redonne lui-même (ou propres à un autre format lu)
_FROM_VND = ('page_mm', 'compagnon', 'smb_fonts')
#: réglages d'objet que le VND garde lui-même (trous, cotes TypeEdit)
NATIVE = ('trou', 'cotation')
#: outils d'un document TypeEdit (table de la fin du VND) : au-delà, leurs couleurs vont dans le compagnon
TE_TOOLS = 10


#: la famille TypeEdit que VectorDrive écrit (VND, dessin LaserType, modèle) : la même archive, qui garde les mêmes
#: données — même compagnon, mêmes égards à l'écriture
TE_EXT = ('.vnd', '.vnl', '.vnm')
#: ceux que Ctrl+S réenregistre à leur place dès l'ouverture (un modèle : « Enregistrer sous »)
TE_DRAWINGS = ('.vnd', '.vnl')


def te_native(path) -> bool:
    return pathlib.Path(path).suffix.lower() in TE_EXT


def companion_path(path) -> pathlib.Path:
    """Compagnon de `path` : `piece.vdz` pour un VND (depuis toujours), `piece.dxf.vdz` pour un autre format."""
    p = pathlib.Path(path)
    if p.suffix.lower() == '.vnd':
        return p.with_suffix('.vdz')
    return p.with_name(p.name + '.vdz')


def _link(path) -> dict | None:
    try:
        with zipfile.ZipFile(path) as z:
            link = json.loads(z.read(LINK).decode('utf-8'))
        return link if isinstance(link, dict) else None
    except (OSError, ValueError, KeyError, zipfile.BadZipFile):
        return None


def twin_of(path) -> pathlib.Path | None:
    """Le fichier qu'accompagne le compagnon `path`, à côté de lui : celui que nomme son lien, sinon celui que donne
    son nom (`piece.vdz` → `piece.vnd`, `piece.dxf.vdz` → `piece.dxf`). None : pas un compagnon, ou fichier absent."""
    link = _link(path)
    if link is None:
        return None
    p = pathlib.Path(path)
    names = [str(link.get('fichier') or ''), p.with_suffix('.vnd').name, p.stem if pathlib.Path(p.stem).suffix else '']
    for name in names:
        if name and name.lower() != p.name.lower() and p.with_name(name).is_file():
            return p.with_name(name)
    return None


def format_key(path) -> str:
    """Clé du format de `path` dans le registre ('vnd', 'dxf'…) ; son extension s'il n'y est pas."""
    from . import registry
    f = registry.by_extension(path)
    return f.key if f is not None else pathlib.Path(path).suffix.lower().lstrip('.')


def _own_extra(extra: dict) -> dict:
    return {k: v for k, v in (extra or {}).items()
            if not k.startswith('vnd') and k not in _FROM_VND and v not in (None, '', [], {})}


def rich(it, native: tuple = NATIVE) -> bool:
    """Objet que le VND ne garde qu'en courbes : texte modifiable, objet
    paramétrique (réglages dans `extra`), ou groupe qui en contient. `native` : les réglages qui ne comptent pas."""
    if (it.extra or {}).get('vnd_obj') is not None:
        return False                                  # objet TypeEdit d'origine : le VND le garde
    if isinstance(it, Text) or (isinstance(it, Image) and image_rich(it)):
        return True
    if any(not k.startswith('vnd') and k not in native and v not in (None, '', [], {})
           for k, v in (it.extra or {}).items()):
        return True
    return isinstance(it, Group) and any(rich(c, native) for c in it.children)


def image_rich(it) -> bool:
    """Image que le VND ne rend pas telle quelle (round 1160) : tournée ou inclinée (TypeEdit la pose droite), ou
    transparente (le VND l'écrit en DIB sur fond blanc). Seulement retournée : le VND garde le signe de sa largeur et
    de sa hauteur (`vnd_write._vnimage`, relu tel quel), elle n'en a pas besoin."""
    m = it.matrix
    if abs(m.b) > 1e-9 or abs(m.c) > 1e-9:
        return True
    data = it.data or b''
    if it.fmt != 'png' or data[:8] != b'\x89PNG\r\n\x1a\n' or len(data) < 26:
        return False
    idat = data.find(b'IDAT')
    if data[25] not in (4, 6) and b'tRNS' not in data[:idat if idat > 0 else 64]:
        return False                                     # ni canal alpha ni couleur transparente
    return _see_through(bytes(data))


@functools.lru_cache(maxsize=32)
def _see_through(data: bytes) -> bool:
    """Un PNG à canal alpha (ou à couleur transparente) a-t-il un pixel qui n'est pas tout à fait opaque ? (Un PNG
    RGBA entièrement opaque passe dans le VND sans perte.) Illisible ici : oui, dans le doute."""
    import numpy as np
    from PySide6.QtGui import QImage
    from .raster import _app
    _app()
    q = QImage.fromData(data, 'PNG')
    if q.isNull():
        return True
    if not q.hasAlphaChannel():
        return False
    q = q.convertToFormat(QImage.Format.Format_Alpha8)
    px = np.frombuffer(q.constBits(), np.uint8, count=q.sizeInBytes()).reshape(q.height(), q.bytesPerLine())
    return bool((px[:, :q.width()] != 255).any())


def only_coloured(it) -> bool:
    """Objet que le compagnon ne garde que pour sa couleur propre (celle qui suit l'objet, quel que soit son outil)."""
    from ..core.document import OWN_COLOR
    return not isinstance(it, Text) and rich(it) and not rich(it, NATIVE + (OWN_COLOR,))


def reasons(doc: Document) -> list[str]:
    """Pourquoi un compagnon est nécessaire (vide : le VND suffit)."""
    out = []
    extra = _own_extra(doc.extra)
    fao = extra.pop('fao', None)
    if isinstance(fao, dict) and (fao.get('tools') or fao.get('operations')):
        out.append('réglage FAO')
    guides = [extra.pop('guides', None), extra.pop('guides_obliques', None)]
    if any(guides):
        out.append('guides')
    if extra:
        out.append('données VectorDrive (' + ', '.join(sorted(extra)) + ')')
    texts = sum(1 for L in doc.layers for it in L.items if isinstance(it, Text))
    coloured = sum(1 for L in doc.layers for it in L.items if only_coloured(it))
    pictures = sum(1 for L in doc.layers for it in L.items if isinstance(it, Image) and image_rich(it))
    others = sum(1 for L in doc.layers for it in L.items
                 if rich(it) and not isinstance(it, Text)) - coloured - pictures
    if pictures:
        out.append(f'{pictures} image(s) tournée(s) ou transparente(s)')
    grouped = any(isinstance(x, Image) and image_rich(x) for L in doc.layers for it in L.items
                  if isinstance(it, Group) for x in _walk(it.children))
    if texts:
        out.append(f'{texts} texte(s) modifiable(s)')
    if coloured:
        out.append(f'{coloured} contour(s) de couleur propre')
    if others:
        out.append(f'{others} objet(s) paramétrique(s) ou groupe(s) avec textes'
                   + (' ou images' if grouped else ''))
    if any(not L.visible or L.locked for L in doc.layers):
        out.append('calques masqués ou verrouillés')
    from ..core import surface2d
    if any(surface2d.of_layer(L) is not None for L in doc.layers):
        out.append('surfaces posées en 2D')
    beyond = sorted({int(getattr(lf, 'tool', 0) or 0) for lf in doc.iter_leaves()} - set(range(TE_TOOLS)))
    if beyond:                                           # la table de TypeEdit n'a que 10 outils : couleurs ici
        out.append(f'{len(beyond)} outil(s) au-delà du {TE_TOOLS}e (couleurs)')
    if _plates(doc):                                     # jamais écrite ailleurs que dans un VDZ (`save_document`)
        out.append('plaque de reprise posée')
    return out


def _plates(doc: Document) -> list[int]:
    """Rangs des calques de plaques de reprise posées : les calques que seul le VDZ reçoit."""
    from ..cam.fixture import is_plate_layer
    return [i for i, L in enumerate(doc.layers) if is_plate_layer(L)]


def _held_plates(comp: Document, link: dict) -> list:
    """[(rang, calque)] des plaques de reprise que le compagnon garde et que le fichier n'a pas reçues (lien
    `plaques` ; absent d'un compagnon d'avant 0.908.0 : le fichier les avait, rien à remettre)."""
    from ..cam.fixture import is_plate_layer
    ranks = [i for i in (link.get('plaques') or []) if isinstance(i, int)]
    return [(i, comp.layers[i]) for i in ranks if 0 <= i < len(comp.layers) and is_plate_layer(comp.layers[i])]


def _put_plates(doc: Document, held: list) -> None:
    """Les plaques de reprise `held` remises dans le dessin relu, à leur rang."""
    for i, plate in sorted(held, key=lambda h: h[0]):
        if not any(L is plate for L in doc.layers):
            doc.layers.insert(min(i, len(doc.layers)), plate)


def _sha(path) -> str:
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()


def is_companion(path) -> bool:
    try:
        with zipfile.ZipFile(path) as z:
            return LINK in z.namelist()
    except (OSError, zipfile.BadZipFile):
        return False


def _walk(items):
    for it in items:
        yield it
        yield from _walk(getattr(it, 'children', ()) or ())


def _signature(doc: Document) -> dict:
    """Ce qu'un format doit rendre pour se passer de compagnon : plaque, table d'outils, calques et objets — sans les
    identifiants ni les données `extra` (comptées par `reasons`)."""
    d = native.to_dict(doc)

    def item(i: dict) -> dict:
        out = {k: v for k, v in i.items() if k not in ('id', 'extra', 'children', 'data')}
        if 'children' in i:
            out['children'] = [item(c) for c in i['children']]
        if 'data' in i:
            out['data'] = hashlib.sha256(str(i['data']).encode('ascii', 'replace')).hexdigest()
        return out
    return {'plate': d.get('plate'), 'tools': d.get('tools'),
            'layers': [{'name': L.get('name'), 'tool': L.get('tool'), 'items': [item(i) for i in L.get('items', [])]}
                       for L in d.get('layers', [])]}


def _same(a, b, tol: float) -> bool:
    if isinstance(a, bool) or isinstance(b, bool):
        return a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(a - b) <= tol
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(_same(a[k], b[k], tol) for k in a)
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return len(a) == len(b) and all(_same(x, y, tol) for x, y in zip(a, b))
    return a == b


def _shifted(v, dx: float, dy: float):
    """La signature d'objets `v`, déplacée de (dx, dy) : segments des tracés, matrices des images."""
    if isinstance(v, list):
        if v and v[0] in ('L', 'C', 'Q') and all(isinstance(x, (int, float)) for x in v[1:]):
            n = {'L': 4, 'C': 8, 'Q': 6}[v[0]]
            return [v[0]] + [x + (dx if i % 2 == 0 else dy) for i, x in enumerate(v[1:1 + n])] + v[1 + n:]
        return [_shifted(x, dx, dy) for x in v]
    if isinstance(v, dict):
        out = {k: _shifted(x, dx, dy) for k, x in v.items() if k != 'matrix'}
        if 'matrix' in v:
            m = list(v['matrix'])
            out['matrix'] = m[:4] + [m[4] + dx, m[5] + dy] if len(m) == 6 else m
        return out
    return v


def differences(doc: Document, back: Document, tol: float = 2e-3) -> list[str]:
    """Ce que `back` (le fichier relu) ne rend pas de `doc`, à `tol` mm près : la liste des raisons d'un compagnon.
    Le nom d'un calque unique ne compte pas (« Plan 1 » relu « Page 1 ») ; un dessin rendu tel quel mais ailleurs
    (formats « page » : SVG, PDF, EPS, HPGL, symbole) a perdu sa position."""
    a, b = _signature(doc), _signature(back)
    out = []
    if not _same(a['plate'], b['plate'], tol):
        out.append('plaque')
    if not _same(a['tools'], b['tools'], tol):
        out.append('table d\'outils')
    la, lb = a['layers'], b['layers']
    if len(la) != len(lb) or [L['tool'] for L in la] != [L['tool'] for L in lb] or \
            (len(la) > 1 and [L['name'] for L in la] != [L['name'] for L in lb]):
        out.append('calques')
        return out
    ia, ib = [L['items'] for L in la], [L['items'] for L in lb]
    if not _same(ia, ib, tol):
        ba, bb = doc.bbox(include_plate=False), back.bbox(include_plate=False)
        moved = ba is not None and bb is not None and _same(ia, _shifted(ib, ba[0] - bb[0], ba[1] - bb[1]), tol)
        out.append('position du dessin' if moved else 'objets que ce format ne rend pas tels quels')
    return out


def foreign_reasons(doc: Document, path) -> list[str]:
    """Pourquoi `path` — un autre format que VDZ et VND, qui vient d'être écrit — ne suffit pas : ce que `reasons`
    compte, les objets TypeEdit d'origine (seul le VND les garde), puis ce que sa relecture ne rend pas."""
    out = reasons(doc)
    if any((it.extra or {}).get('vnd_obj') is not None for L in doc.layers for it in _walk(L.items)):
        out.append('objets TypeEdit d\'origine')
    if out:
        return out
    from . import registry
    f = registry.by_extension(path)
    if f is not None and f.key == 'image':
        return ['dessin vectoriel (une image n\'en garde que l\'aspect)']
    if f is not None and f.key == 'inkscape':            # relire demanderait de relancer Inkscape : le compagnon garde tout
        return ['dessin converti par Inkscape']
    if f is not None and f.key in ('step', 'mesh'):      # relu, ce fichier n'est qu'une vue de dessus
        return ['dessin d\'origine (ce format ne garde que la pièce en volume)']
    if f is None or f.reader is None:
        return ['format qu\'on ne sait pas relire']
    try:
        back = registry.open_document(path)
    except Exception as ex:                              # noqa: BLE001 — relecture en défaut : le compagnon garde tout
        return [f'relecture impossible ({type(ex).__name__})']
    return differences(doc, back)


def sync(doc: Document, vnd_path, mode: str = 'besoin') -> tuple[pathlib.Path | None, list[str]]:
    """Après l'écriture de `vnd_path` (un VND, ou tout autre format que le VDZ) : écrit (ou met à jour, ou supprime)
    son compagnon. `mode` : 'besoin' (s'il y a des données à garder),
    'toujours', 'jamais'. Rend (chemin du compagnon ou None, raisons)."""
    cp = companion_path(vnd_path)
    key = format_key(vnd_path)
    why = (reasons(doc) if te_native(vnd_path) else foreign_reasons(doc, vnd_path)) if mode != 'jamais' else []
    if mode == 'toujours' and not why:
        why = ['document VectorDrive complet']
    if not why:
        if cp.exists() and is_companion(cp):
            cp.unlink()
        return None, []
    if cp.exists() and not is_companion(cp):
        raise FileExistsError(f'{cp.name} existe déjà et n\'est pas un compagnon de VND : '
                              'données VectorDrive non enregistrées (renommer l\'un des deux)')
    plates = _plates(doc)                                # pas écrites dans le fichier : comptées à part
    written = [L for i, L in enumerate(doc.layers) if i not in plates]
    if te_native(vnd_path):                              # une copie en VD Géo écrite à la place de son calque
        from ..core import missing_fonts as MF
        written = MF.for_vnd(written)[0]
    link = {'version': 1, 'fichier': pathlib.Path(vnd_path).name, 'format': key, 'sha256': _sha(vnd_path),
            'compteurs': [len(L.items) for L in written], 'raisons': why,
            'objets': [[i for i, it in enumerate(L.items) if rich(it)] for L in written],
            'plaques': plates, 'date': dt.datetime.now().isoformat(timespec='seconds')}
    if te_native(vnd_path):                              # l'ordre des calques écrits (0.956.0) : `_in_vnd_order`
        from .vnd_write import first_shown_of
        link['ordre'] = 'premier' if first_shown_of(doc) else 'dessin'
    data = json.dumps(native.to_dict(doc), ensure_ascii=False, separators=(',', ':'))
    tmp = cp.with_suffix('.vdz.tmp')
    with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('document.json', data)
        z.writestr('mimetype', 'application/x-vectordrive')
        z.writestr(LINK, json.dumps(link, ensure_ascii=False, indent=1))
    tmp.replace(cp)
    return cp, why


def apply(doc: Document, vnd_path) -> list[str]:
    """À l'ouverture de `vnd_path` : reprend ce que garde son compagnon.
    Rend les messages pour l'utilisateur."""
    cp = companion_path(vnd_path)
    if not cp.exists() or not is_companion(cp):
        return []
    try:
        with zipfile.ZipFile(cp) as z:
            link = json.loads(z.read(LINK).decode('utf-8'))
            comp = native.from_dict(json.loads(z.read('document.json').decode('utf-8')))
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as ex:
        return [f'compagnon {cp.name} illisible ({ex}) : ignoré']
    if link.get('fichier', '').lower() != pathlib.Path(vnd_path).name.lower():
        return [f'{cp.name} accompagne {link.get("fichier")}, pas ce VND : ignoré']
    if not te_native(vnd_path):
        return _apply_foreign(doc, vnd_path, cp, link, comp)
    shift = _origin_shift(comp.extra)                    # le zéro du VND est l'origine du dessin : on y revient
    if shift and not (isinstance(doc.extra, dict) and 'origine' in doc.extra):     # (pas deux fois)
        _to_drawing(doc, shift)                          # dès lors, VND relu et compagnon dans le même repère
    held = _held_plates(comp, link)                      # plaques de reprise : le VND ne les a pas reçues
    comp.layers = [C for C in comp.layers if not any(C is P for _i, P in held)]
    msgs = []
    doc.extra.update(_own_extra(comp.extra))
    ordre = link.get('ordre')
    written, info = comp.layers, {}
    if ordre in ('dessin', 'premier'):                   # 0.956.0 : la copie en VD Géo pas écrite en plus de son calque
        from ..core import missing_fonts as MF
        written, info = MF.for_vnd(comp.layers)
    real = {k: (p['original'] if p['sorte'] == 'devant' else p['copie']) for k, p in info.items()
            if p['sorte'] in ('devant', 'derriere')}     # écrits montré / caché : leur état à eux est dans le compagnon
    order = _in_vnd_order(doc.layers, written, ordre)
    same = _sha(vnd_path) == link.get('sha256')          # le VND tel qu'il a été écrit (pas retouché dans TypeEdit)
    twins = _twins(doc.layers, written, ordre if same else None, order)     # noms en double, ordre pas sûr
    if twins:                                            # dit dans les remarques de l'ouverture, sans fenêtre
        msgs.append(f'calque(s) de même nom ({", ".join(sorted(twins))}) : rien n\'en est repris du compagnon '
                    '(ordre des calques non vérifiable) — renommer les calques')
    if len(written) == len(doc.layers):
        for L, C in zip(doc.layers, (written[i] for i in order)):
            if L.name != C.name or L.name in twins:      # pas sûrement le même calque : rien n'en est repris (ni son
                continue                                 # état, ni son id : les opérations FAO le désignent)
            R = real.get(id(C), C)
            L.visible, L.locked = R.visible, R.locked
            if doc.active == L.id:                       # même calque : son id (rattachements FAO) et ses données
                doc.active = C.id                        # (surface posée…), le VND ne les a pas
            L.id = C.id
            L.extra = {**R.extra, **L.extra}
            _outlines(L, C)
    n = 0
    back, hid = {}, {}
    if same and len(written) == len(doc.layers):
        counts = link.get('compteurs') or []
        wanted = link.get('objets') or []
        for L, k in zip(doc.layers, order):
            C = written[k]
            p = info.get(id(C))
            if p is not None and p['sorte'] == 'fusion':  # le calque écrit à la place d'une copie : les deux reviennent
                if L.name == C.name:
                    back[id(L)] = (p, C)
                continue
            if p is not None and p['sorte'] == 'cachee' and L.name == C.name:
                hid[id(L)] = (p['copie'], C)             # sa copie cachée, pas écrite : elle revient aussi
            if L.name != C.name or len(L.items) != len(C.items) or (k < len(counts) and counts[k] != len(C.items)):
                continue                                 # jamais les objets d'un calque dans un autre
            if L.name in twins or not all(_written(it) for it in C.items):
                continue                                 # nom en double, objet masqué (pas écrit) : rangs douteux
            for it, cit in zip(L.items, C.items):
                _copy_ids(it, cit)                       # les opérations FAO désignent les objets par leur id
            for i in (wanted[k] if k < len(wanted) else []):
                if 0 <= i < len(C.items):                # même VND, même rang : sa version en courbes
                    L.items[i] = C.items[i]
                    n += 1
        if back or hid:                                  # la copie et son original, dans l'ordre du compagnon
            rank = {id(C): i for i, C in enumerate(comp.layers)}
            out = []
            for L in doc.layers:
                if id(L) in back:
                    p, W = back[id(L)]
                    _originals(L, W, p['original'])
                    out.extend(sorted((p['copie'], p['original']), key=lambda C: rank[id(C)]))
                elif id(L) in hid:
                    c, W = hid[id(L)]
                    out.extend([c, L] if rank[id(c)] < rank[id(W)] else [L, c])
                else:
                    out.append(L)
            doc.layers[:] = out
    if same:                                             # images : le VND écrit un calque par outil (round 1160)
        n += _images_back(doc, written, ordre, twins)
    kept = ', '.join(link.get('raisons') or [])
    if same:
        more = []
        if n:
            more.append(f'{n} objet(s) VectorDrive repris')
        if back or hid:
            more.append(f'{len(back) + len(hid)} calque(s) en VD Géo repris avec leur original')
        msgs.append(f'compagnon {cp.name} relu : {kept}' + (f' ({" ; ".join(more)})' if more else ''))
    else:
        what = 'VND' if pathlib.Path(vnd_path).suffix.lower() == '.vnd' else 'fichier'
        msgs.append(f'le {what} a changé depuis son compagnon {cp.name} (retouché dans TypeEdit ?) : '
                    f'le dessin du {what} fait foi ; seuls le réglage FAO, les guides et l\'état des calques '
                    'sont repris')
    _put_plates(doc, held)                               # remises à leur rang, VND retouché ou non
    msgs += _lost_operations(doc)
    doc.extra['compagnon'] = cp.name
    return msgs


def _images_back(doc: Document, comp_layers: list, ordre: str | None, cited=frozenset()) -> int:
    """Les images que le VND a dégradées (tournées, inclinées, transparentes : `image_rich`) reprises du compagnon
    (round 1160), calque par calque : les calques du compagnon partagés comme à l'écriture (un calque TypeEdit par
    outil, `vnd_write._tool_layers` : « nom (n° d'outil) ») et remis dans l'ordre du VND (`_in_vnd_order`) ; un calque
    du VND prend les images du sien s'ils ont le même nom et autant d'images, une à une dans l'ordre (matrice et
    pixels ; côté compagnon, seulement les images écrites : visibles, dans des groupes visibles). Une image déjà
    reprise du compagnon (rang des objets) n'est pas retouchée ; dans le doute (nombre de calques, noms différents ou
    en double, nombre d'images différent), rien n'est remplacé ; ni d'un calque cité dans la remarque des noms en
    double d'`apply` (`cited`), même partagé par outil. Rend leur nombre."""
    from .vnd_write import _tool_layers
    subs = [L for L, _tool in _tool_layers(comp_layers)]
    if len(subs) != len(doc.layers):
        return 0
    order = _in_vnd_order(doc.layers, subs, ordre)
    twins = _twins(doc.layers, subs, ordre, order)       # l'ordre direct seulement, comme dans `apply`
    skip = {C.id for C in comp_layers if C.name in cited}   # un calque partagé garde l'id du sien
    from_comp = {id(it) for C in subs for it in _walk(C.items) if isinstance(it, Image)}
    n = 0
    for L, k in zip(doc.layers, order):
        C = subs[k]
        mine = [it for it in _walk(L.items) if isinstance(it, Image)]
        theirs = [it for it in _walk_written(C.items) if isinstance(it, Image)]
        if L.name != C.name or L.name in twins or C.id in skip or len(mine) != len(theirs):
            continue                                     # jamais les images d'un calque dans un autre
        for a, b in zip(mine, theirs):
            if id(a) in from_comp or not image_rich(b):
                continue
            if a.data != b.data or a.matrix != b.matrix:
                a.data, a.fmt, a.matrix = b.data, b.fmt, b.matrix
                n += 1
    return n


def _written(it) -> bool:
    """L'objet est-il écrit dans le VND (`vnd_write._zone`) : visible, et pour un groupe au moins un enfant écrit
    (ou zone vide de la source) ; un objet TypeEdit d'origine (`vnd_obj` : texte, trou, solide, point ou axe de
    construction, sans enfants) est réécrit tel quel — dans le compagnon la clé reste, à None ; déplacé ou retouché
    (`vnd_moved`), il est redessiné, ou réécrit translaté (`vnd_shift`) : compté écrit de même ; une image sans données
    ne l'est pas (round 1160)."""
    if not getattr(it, 'visible', True):
        return False
    if isinstance(getattr(it, 'extra', None), dict) and 'vnd_obj' in it.extra:
        return True
    if isinstance(it, Group):
        return any(_written(c) for c in it.children) or bool((it.extra.get('vnd') or {}).get('empty_zone'))
    return not isinstance(it, Image) or bool(it.data)


def _walk_written(items):
    """Comme `_walk`, sans les objets que le VND n'écrit pas (masqués, ou dans un groupe masqué)."""
    for it in items:
        if _written(it):
            yield it
            yield from _walk_written(getattr(it, 'children', ()) or ())


def _origin_shift(extra) -> tuple[float, float] | None:
    """L'origine posée (`doc.extra['origine']`) dont l'écriture a fait le zéro du VND (`vnd_write.at_origin`) ; le
    compagnon, lui, reste dans le repère du dessin. None : pas d'origine, posée au zéro, ou invalide (NaN, infinie,
    hors bornes : écartée par `vnd_write.clean_document`, le VND n'a pas été décalé)."""
    from .vnd_write import _point_ok
    o = extra.get('origine') if isinstance(extra, dict) else None
    try:
        if not o or not _point_ok(o):
            return None
        x, y = float(o[0]), float(o[1])
    except (TypeError, ValueError, IndexError, KeyError):
        return None
    return (x, y) if abs(x) >= 1e-9 or abs(y) >= 1e-9 else None   # les seuils de `at_origin`


def _to_drawing(doc: Document, o: tuple[float, float]) -> None:
    """Le dessin relu d'un VND écrit avec l'origine `o` pour zéro, remis dans le repère de VectorDrive (+o) :
    objets (un objet TypeEdit d'origine cumule la translation, `vnd_write.source_object`), plaque, page. À
    l'enregistrement suivant, `at_origin` le redécale de −o : le VND est réécrit au même endroit."""
    import dataclasses
    from ..core.geom import Affine
    m = Affine.translation(o[0], o[1])
    for L in doc.layers:
        L.items = [it.transformed(m) for it in L.items]
    if doc.plate is not None:
        doc.plate = dataclasses.replace(doc.plate, x=doc.plate.x + o[0], y=doc.plate.y + o[1])
    page = doc.extra.get('page_mm') if isinstance(doc.extra, dict) else None
    if page and len(page) == 6:                          # VND sans réglages : la page de travail (x0, y0, z0, x1…)
        doc.extra['page_mm'] = (page[0] + o[0], page[1] + o[1], page[2], page[3] + o[0], page[4] + o[1], page[5])


BOX_TOL = 0.05                                           # mm : boîtes d'un objet relu du VND et de son modèle


def _same_kinds(L, C) -> bool:
    """Le calque relu du VND a-t-il, rang pour rang, des objets de même nature (image ou non) que ceux que le VND a
    reçus du calque du compagnon (ses objets écrits, `_written`) ? Le même nombre, donc."""
    return [isinstance(it, Image) for it in L.items] == [isinstance(it, Image) for it in C.items if _written(it)]


def _box(it):
    try:
        b = it.bbox()
    except Exception:                                    # noqa: BLE001 — chemin vide… : pas de boîte
        return None
    return tuple(float(v) for v in b) if b else None


def _same_boxes(L, C) -> bool:
    """Rang pour rang, les objets du calque relu (sauf les images, que le VND dégrade) ont-ils la boîte englobante,
    à `BOX_TOL` près, des objets écrits du calque du compagnon ? Origine posée ou non : `apply` a remis le dessin
    relu dans le repère du compagnon (`_to_drawing`)."""
    for a, b in zip(L.items, [it for it in C.items if _written(it)]):
        if isinstance(a, Image) or isinstance(b, Image):
            continue
        p, q = _box(a), _box(b)
        if (p is None) != (q is None) or (p and any(abs(u - v) > BOX_TOL for u, v in zip(p, q))):
            return False
    return True


def _verified(layers: list, comp_layers: list, order: list | None, names: set) -> bool:
    """L'ordre refait des calques en ordre 'premier' se vérifie-t-il pour les calques jumeaux (`names`) ? Seulement
    s'il est l'ordre que l'écriture donne directement aux calques du compagnon (`vnd_write.write_order`), jamais
    retrouvé par le repli de `_in_vnd_order` (rotations, rang pour rang) : `_written` peut compter écrit un objet que
    le VND n'écrit pas (texte vide, chemin vide, image que `to_dib` refuse), et les noms y collent par hasard. Puis
    chaque calque jumeau du VND a les objets du sien : même nombre et même nature (`_same_kinds`), mêmes boîtes
    (`_same_boxes`, toujours : avec une origine posée aussi, le dessin relu étant remis dans le repère du dessin)."""
    from . import vnd_write
    if order is None or not len(order) == len(layers) == len(comp_layers):
        return False
    try:
        direct = vnd_write.write_order(comp_layers, lambda C: any(_written(it) for it in C.items), True)
    except Exception:                                    # noqa: BLE001 — compagnon abîmé : pas vérifié
        return False
    if list(order) != list(direct):
        return False
    return all(L.name == comp_layers[k].name and _same_kinds(L, comp_layers[k])
               and _same_boxes(L, comp_layers[k]) for L, k in zip(layers, order) if L.name in names)


def _twins(layers: list, comp_layers: list, ordre: str | None, order: list | None = None) -> set:
    """Noms de calque en double, dans le VND relu ou dans le compagnon (round 1160) : l'ordre retrouvé ne se vérifie
    pas par le nom, rien n'est repris de ces calques (ni objets, ni images, ni leur état). En ordre 'dessin' (réglage
    d'office), l'écriture garde l'ordre du dessin (`vnd_write.write_order` : l'identité) : le calque k du VND est à
    coup sûr le calque k du compagnon, aucun n'est écarté. Cette certitude ne vaut que pour le VND tel qu'il a été
    écrit (même empreinte) : retouché dans TypeEdit, `apply` passe `ordre` à None et la règle s'applique. En ordre
    'premier' (VND tel qu'écrit), aucun n'est écarté si l'ordre refait (`order`) se vérifie (`_verified` : l'ordre
    direct de l'écriture, et les contenus des calques jumeaux ; round 989 : deux « Plan », le premier masqué). Compagnon
    sans ordre (d'avant 0.956) : la règle, toujours."""
    if ordre == 'dessin':
        return set()
    out = set()
    for group in (layers, comp_layers):
        names = [L.name for L in group]
        out |= {n for n in names if names.count(n) > 1}
    if out and ordre == 'premier' and _verified(layers, comp_layers, order, out):
        return set()                                     # ordre refait vérifié par les contenus
    return out


def _in_vnd_order(layers: list, comp_layers: list, ordre: str | None = None) -> list[int]:
    """Rang dans le compagnon (ses calques tels que le VND les a écrits) de chaque calque relu du VND. On refait sur
    le compagnon l'ordre que l'écriture a donné (`ordre` du lien : 'dessin' — l'ordre du dessin, 'premier' — le premier
    calque qui a quelque chose à montrer en tête, absent — un compagnon d'avant 0.956.0, `vnd_write.layer_order`),
    vérifié par les noms (deux calques du même nom restent à leur place) ; sinon, retrouvé par les noms ; sinon, rang
    pour rang."""
    names = [L.name for L in layers]
    k = list(range(len(comp_layers)))
    if len(names) != len(k):
        return k
    from . import vnd_write
    try:                                                 # l'ordre que l'écriture a donné à ces calques
        order = (vnd_write.write_order(comp_layers, lambda C: any(_written(it) for it in C.items),
                                       ordre == 'premier') if ordre in ('dessin', 'premier')
                 else list(vnd_write.layer_order(comp_layers)[0]))
    except Exception:                                    # noqa: BLE001 — compagnon abîmé : les essais d'après
        order = []
    if sorted(order) == k and [comp_layers[i].name for i in order] == names:
        return order
    if len(set(names)) == len(names) and sorted(C.name for C in comp_layers) == sorted(names):
        by_name = {C.name: i for i, C in enumerate(comp_layers)}     # noms tous différents : par le nom
        return [by_name[n] for n in names]
    shown = ([i for i, C in enumerate(comp_layers) if C.items and C.visible]
             or [i for i, C in enumerate(comp_layers) if C.items])
    if shown:
        j = shown[0]
        order = [j] + k[:j] + k[j + 1:]
        if [comp_layers[i].name for i in order] == names:
            return order
    if [C.name for C in comp_layers] == names:
        return k
    for j in range(1, len(k)):
        order = [j] + k[:j] + k[j + 1:]
        if [comp_layers[i].name for i in order] == names:
            return order
    return k


def _lost_operations(doc: Document) -> list[str]:
    """Opérations FAO limitées à des objets que le dessin relu n'a plus."""
    fao = doc.extra.get('fao')
    if not isinstance(fao, dict):
        return []
    ids = {it.id for L in doc.layers for it in _walk(L.items)}
    lost = [o.get('name') or o.get('kind') for o in fao.get('operations', [])
            if o.get('items') and not ids.intersection(o['items'])]
    if not lost:
        return []
    return [f'{len(lost)} opération(s) FAO limitée(s) à des objets disparus ({", ".join(lost)}) : '
            'les refaire sur la sélection']


def _apply_foreign(doc: Document, path, cp, link: dict, comp: Document) -> list[str]:
    """Compagnon d'un autre format que le VND. Fichier inchangé depuis (même empreinte) : le dessin VectorDrive
    entier du compagnon est repris. Fichier retouché ailleurs : il fait foi ; seuls le réglage FAO, les guides et
    l'état des calques sont repris."""
    kept = ', '.join(link.get('raisons') or [])
    name = pathlib.Path(path).name
    if _sha(path) == link.get('sha256'):
        doc.layers, doc.plate, doc.tools, doc.active = comp.layers, comp.plate, comp.tools, comp.active
        doc.extra = dict(comp.extra or {})
        msgs = [f'compagnon {cp.name} relu : {kept}']
    else:
        doc.extra.update(_own_extra(comp.extra))
        held = _held_plates(comp, link)                  # plaques de reprise : le fichier ne les a pas reçues
        rest = [C for C in comp.layers if not any(C is P for _i, P in held)]
        if len(rest) == len(doc.layers):
            for L, C in zip(doc.layers, rest):
                L.visible, L.locked = C.visible, C.locked
        _put_plates(doc, held)
        msgs = [f'{name} a changé depuis son compagnon {cp.name} (retouché dans un autre logiciel ?) : son dessin '
                'fait foi ; seuls le réglage FAO, les guides et l\'état des calques sont repris']
        msgs += _lost_operations(doc)
    doc.extra['compagnon'] = cp.name
    return msgs


def _outlines(L, C) -> None:
    """Contour d'une surface posée marqué de nouveau (le VND ne garde pas
    la marque : sans elle il serait usiné), reconnu à sa place et sa taille."""
    from ..core import surface2d

    def box(it):
        try:
            return it.bbox()
        except Exception:                              # noqa: BLE001 — objet sans étendue
            return None
    def near(it, t, m):
        b = box(it)
        return type(it) is t and b is not None and max(abs(p - q) for p, q in zip(b, m)) < 0.05
    used = set()
    for k, c in enumerate(C.items):                    # un pour un : un détourage tracé sur le bord reste usiné
        m = box(c) if surface2d.is_outline(c) else None
        if not m:
            continue
        found = [i for i, it in enumerate(L.items) if i not in used and near(it, type(c), m)]
        if found:                                      # même outil d'abord, puis même rang (VND réordonné)
            same = lambda j: getattr(L.items[j], 'tool', None) == getattr(c, 'tool', None)     # noqa: E731
            i = min(found, key=lambda j: (not same(j), j != k, j))
            used.add(i)
            L.items[i].extra = {**(L.items[i].extra or {}), surface2d.OUTLINE: True}
            L.items[i].locked = True


def _originals(L, W, orig) -> None:
    """Le calque relu du VND à la place d'une copie en VD Géo (`missing_fonts.for_vnd`, `W` : ce qui a été écrit) :
    les objets d'origine, écrits tels quels avec leur objet TypeEdit, reprennent la place de leur version du compagnon
    dans l'original `orig` (le compagnon ne garde pas l'objet TypeEdit : sans lui, le texte passerait en courbes au
    prochain enregistrement)."""
    if len(L.items) != len(W.items):
        return
    mine = {id(it): k for k, it in enumerate(orig.items)}
    for it, w in zip(L.items, W.items):
        k = mine.get(id(w))
        if k is not None and type(it) is type(w):
            _copy_ids(it, w)
            orig.items[k] = it


def _copy_ids(it, cit) -> None:
    """Identifiants du compagnon reportés sur l'objet relu du VND (même
    structure)."""
    if type(it) is not type(cit):
        return
    it.id = cit.id
    a, b = getattr(it, 'children', None), getattr(cit, 'children', None)
    if a is not None and b is not None and len(a) == len(b):
        for x, y in zip(a, b):
            _copy_ids(x, y)
