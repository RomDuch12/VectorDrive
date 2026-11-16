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
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import pathlib
import zipfile

from ..core.document import Document, Group, Text
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
    if isinstance(it, Text):
        return True
    if any(not k.startswith('vnd') and k not in native and v not in (None, '', [], {})
           for k, v in (it.extra or {}).items()):
        return True
    return isinstance(it, Group) and any(rich(c, native) for c in it.children)


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
    others = sum(1 for L in doc.layers for it in L.items if rich(it) and not isinstance(it, Text)) - coloured
    if texts:
        out.append(f'{texts} texte(s) modifiable(s)')
    if coloured:
        out.append(f'{coloured} contour(s) de couleur propre')
    if others:
        out.append(f'{others} objet(s) paramétrique(s) ou groupe(s) avec textes')
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
    link = {'version': 1, 'fichier': pathlib.Path(vnd_path).name, 'format': key, 'sha256': _sha(vnd_path),
            'compteurs': [len(L.items) for L in written], 'raisons': why,
            'objets': [[i for i, it in enumerate(L.items) if rich(it)] for L in written],
            'plaques': plates, 'date': dt.datetime.now().isoformat(timespec='seconds')}
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
    held = _held_plates(comp, link)                      # plaques de reprise : le VND ne les a pas reçues
    comp.layers = [C for C in comp.layers if not any(C is P for _i, P in held)]
    msgs = []
    doc.extra.update(_own_extra(comp.extra))
    order = _in_vnd_order(doc.layers, comp.layers)
    if len(comp.layers) == len(doc.layers):
        for L, C in zip(doc.layers, (comp.layers[i] for i in order)):
            if L.name != C.name:                         # pas le même calque (ordre pas retrouvé) : rien n'en est repris
                continue
            L.visible, L.locked = C.visible, C.locked
            if L.name == C.name:                         # même calque : son id (rattachements FAO) et ses données
                if doc.active == L.id:                   # (surface posée…), le VND ne les a pas
                    doc.active = C.id
                L.id = C.id
                L.extra = {**C.extra, **L.extra}
                _outlines(L, C)
    same = _sha(vnd_path) == link.get('sha256')
    n = 0
    if same and len(comp.layers) == len(doc.layers):
        counts = link.get('compteurs') or []
        wanted = link.get('objets') or []
        for L, k in zip(doc.layers, order):
            C = comp.layers[k]
            if L.name != C.name or len(L.items) != len(C.items) or (k < len(counts) and counts[k] != len(C.items)):
                continue                                 # jamais les objets d'un calque dans un autre
            for it, cit in zip(L.items, C.items):
                _copy_ids(it, cit)                       # les opérations FAO désignent les objets par leur id
            for i in (wanted[k] if k < len(wanted) else []):
                if 0 <= i < len(C.items):                # même VND, même rang : sa version en courbes
                    L.items[i] = C.items[i]
                    n += 1
    kept = ', '.join(link.get('raisons') or [])
    if same:
        msgs.append(f'compagnon {cp.name} relu : {kept}' + (f' ({n} objet(s) VectorDrive repris)' if n else ''))
    else:
        what = 'VND' if pathlib.Path(vnd_path).suffix.lower() == '.vnd' else 'fichier'
        msgs.append(f'le {what} a changé depuis son compagnon {cp.name} (retouché dans TypeEdit ?) : '
                    f'le dessin du {what} fait foi ; seuls le réglage FAO, les guides et l\'état des calques '
                    'sont repris')
    _put_plates(doc, held)                               # remises à leur rang, VND retouché ou non
    msgs += _lost_operations(doc)
    doc.extra['compagnon'] = cp.name
    return msgs


def _in_vnd_order(layers: list, comp_layers: list) -> list[int]:
    """Rang dans le compagnon de chaque calque relu du VND. L'écriture du VND passe devant le premier calque qui a
    quelque chose à montrer (`vnd_write._calques`), le compagnon garde l'ordre du dessin : on refait ce choix sur le
    compagnon (deux calques du même nom restent à leur place), vérifié par les noms ; sinon, retrouvé par les noms ;
    sinon, rang pour rang."""
    names = [L.name for L in layers]
    k = list(range(len(comp_layers)))
    if len(names) != len(k):
        return k
    from . import vnd_write
    try:                                                 # l'ordre que l'écriture a donné à ces calques
        order = list(vnd_write.layer_order(comp_layers)[0])
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
