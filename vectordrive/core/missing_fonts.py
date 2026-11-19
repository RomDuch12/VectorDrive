"""Textes d'un dessin ouvert dont une police manque sur le poste (retour de l'atelier du 12/11 : TypeEdit fait fermer,
installer la police, relancer). Leur calque est copié juste devant lui, ces textes y passent en VD Géo (police
monotrait intégrée, toujours là) ; le calque d'origine, caché, reste tel quel : ses textes gardent leur police et se
redessinent dans celle-ci dès qu'elle est installée (`fonts.rescan`), VectorDrive ouvert. Les objets de la copie sont
des objets neufs (identifiants neufs, sans l'objet TypeEdit d'origine : un VND réécrit n'a pas deux fois le même
objet) ; les opérations FAO qui usinent les objets du calque usinent aussi leur copie (un calque caché ne s'usine pas).
Un VND écrit n'a pas la copie en plus de son calque (`for_vnd`, demande du 19/11) : elle y est écrite à sa place.
"""
from __future__ import annotations

from . import fonts as F
from . import text as TX
from .document import Layer, Text, drop_source_object, new_id, struct_copy

#: police des textes de la copie
FONT = 'VD Géo'
#: marque d'un calque copie : {'de': id du calque d'origine, 'polices': polices absentes}
MARK = 'police_absente'
#: fin du nom d'un calque copie : un VND relu sans son compagnon n'a plus la marque, le nom la remplace
SUFFIX = f' — {FONT}'
#: dans la marque d'une copie : {id d'un objet de la copie : [id de l'objet d'origine, sa signature à la copie]}
OBJECTS = 'objets'


def _walk(items):
    for it in items:
        yield it
        yield from _walk(getattr(it, 'children', None) or ())


def absent(it) -> list[str]:
    """Polices d'un texte à écrire qui manquent sur le poste : la sienne, celles de ses lettres (réglages par lettre)."""
    if not isinstance(it, Text) or not it.text.strip():
        return []
    used = {it.font, *(f.get('font') for f in TX.char_fx(it).values())} - {None, ''}
    return sorted(f for f in used if not F.is_available(f))


def missing_font(it) -> bool:
    """Texte dessiné dans une police de remplacement : une de ses polices manque sur le poste, et c'est un texte
    TypeEdit d'origine (dessiné à la lecture) ou un texte sans tracé. Un texte relu avec son tracé (VDZ, compagnon
    d'un VND) se montre tel qu'il a été écrit : il reste dans son calque."""
    return bool(absent(it)) and ((it.extra or {}).get('vnd_obj') is not None or not it.outline)


def copies(doc) -> dict:
    """{id d'un calque : sa copie en VD Géo}, par la marque, sinon par le nom (VND relu sans son compagnon)."""
    out = {}
    for L in doc.layers:
        de = ((L.extra or {}).get(MARK) or {}).get('de')
        if de:
            out[de] = L
    by_name = {L.name: L for L in doc.layers}
    for L in doc.layers:
        c = by_name.get(L.name + SUFFIX) if isinstance(L.name, str) else None
        if c is not None and c is not L and L.id not in out:
            out[L.id] = c
    return out


def signature(it) -> str:
    """Empreinte d'un objet, sans ses identifiants, ni le tracé d'un texte (recalculé), ni les données TypeEdit :
    changée, l'objet a été modifié."""
    import hashlib
    import json
    from ..io import native

    def bare(d: dict) -> dict:
        out = {k: v for k, v in d.items() if k not in ('id', 'children', 'data', 'outline', 'extra')}
        out['extra'] = {k: v for k, v in (d.get('extra') or {}).items() if not str(k).startswith('vnd')}
        if 'children' in d:
            out['children'] = [bare(c) for c in d['children']]
        if 'data' in d:
            out['data'] = hashlib.sha256(str(d['data']).encode('ascii', 'replace')).hexdigest()
        return out
    raw = json.dumps(bare(native._item_out(it)), sort_keys=True, ensure_ascii=True, default=str)
    return hashlib.sha256(raw.encode('ascii')).hexdigest()[:24]


def for_vnd(layers: list) -> tuple[list, dict]:
    """Les calques tels qu'un VND les écrit (demande du 19/11 : « ouverture TE produit un calque dupliqué VD géo…
    peut-on éviter cela ? ») : la copie en VD Géo d'un calque n'y est pas en plus de lui. Montrée, elle est écrite à sa
    place, sous son nom et son id : ses objets dans son ordre, chacun resté tel que copié remplacé par l'objet d'origine
    (le texte TypeEdit dans sa police, que TypeEdit redessine sur un poste qui l'a), les autres (modifiés, ajoutés)
    tels quels — seulement si l'original est caché (les deux montrés : les deux écrits, comme deux calques). Cachée (la
    police est là), l'original seul ; le compagnon la garde. Une copie sans correspondance de ses objets (marquée avant
    0.956.0, ou retrouvée par son nom) : comme avant, l'original écrit devant elle, montré, elle cachée — ses textes
    TypeEdit ne passent jamais en courbes. Les calques ne sont pas touchés (calques à part pour ce qui change). Rend
    (calques, {id() d'un calque écrit : {'sorte': 'fusion' | 'devant' | 'derriere' | 'cachee', 'copie', 'original',
    'repris', 'retires'}}) : 'cachee' est rangée sous l'original, écrit tel quel, dont la copie n'est pas écrite."""
    import types
    by_id = {L.id: L for L in layers}
    skip, put, info = set(), {}, {}
    for de, c in copies(types.SimpleNamespace(layers=layers)).items():
        L = by_id.get(de)
        if L is None or L is c:
            continue
        if not c.visible:
            skip.add(c.id)
            info[id(L)] = {'sorte': 'cachee', 'copie': c, 'original': L, 'repris': 0, 'retires': 0}
            continue
        if L.visible:                                    # les deux montrés : deux calques, rien de fusionné
            continue
        objs = ((c.extra or {}).get(MARK) or {}).get(OBJECTS)
        if not isinstance(objs, dict) or not objs:       # pas de correspondance : l'original devant, la copie cachée
            o = Layer(name=L.name, items=L.items, visible=True, locked=L.locked, id=L.id, extra=L.extra, tool=L.tool)
            h = Layer(name=c.name, items=c.items, visible=False, locked=c.locked, id=c.id, extra=c.extra, tool=c.tool)
            put[c.id] = [o, h]
            skip.add(L.id)
            info[id(o)] = {'sorte': 'devant', 'copie': c, 'original': L, 'repris': 0, 'retires': 0}
            info[id(h)] = {'sorte': 'derriere', 'copie': c, 'original': L, 'repris': 0, 'retires': 0}
            continue
        kept = {it.id: it for it in L.items}
        items, used = [], set()
        for it in c.items:
            e = objs.get(it.id)
            o = kept.get(e[0]) if isinstance(e, (list, tuple)) and len(e) == 2 else None
            if o is not None and id(o) not in used and signature(it) == e[1]:
                items.append(o)
                used.add(id(o))
            else:
                items.append(it)
        here = {it.id for it in c.items}
        mapped = {e[0] for cid, e in objs.items() if cid in here and isinstance(e, (list, tuple)) and e}
        gone = sum(1 for it in L.items if it.id not in mapped)            # objets d'origine supprimés de la copie
        m = Layer(name=L.name, items=items, visible=True, locked=c.locked, id=L.id, extra=dict(L.extra or {}),
                  tool=L.tool)
        put[c.id] = [m]
        skip.add(L.id)
        info[id(m)] = {'sorte': 'fusion', 'copie': c, 'original': L, 'repris': len(used), 'retires': gone}
    out = []
    for L in layers:
        if L.id in skip:
            continue
        out.extend(put.get(L.id, [L]))
    return out, info


def missing(doc) -> dict:
    """{id du calque : textes à passer en VD Géo} (groupes compris) ; ni les calques copies ni ceux qui en ont une, ni
    les calques de surface (leurs opérations FAO n'usinent qu'eux : leurs textes gardent la police de remplacement)."""
    from . import surface2d
    made = copies(doc)
    skip = set(made) | {c.id for c in made.values()}
    out = {}
    for L in doc.layers:
        if L.id in skip or surface2d.of_layer(L) is not None:
            continue
        texts = [it for it in _walk(L.items) if missing_font(it)]
        if texts:
            out[L.id] = texts
    return out


def _renew(items) -> dict:
    """Identifiants neufs pour des objets copiés (groupes compris) ; les copies liées suivent leur modèle copié.
    Rend {ancien : neuf}."""
    ids = {}
    for it in _walk(items):
        old = it.id
        it.id = new_id()
        ids[old] = it.id
    for it in _walk(items):
        link = (it.extra or {}).get('link')
        if isinstance(link, dict) and link.get('master') in ids:
            it.extra = {**it.extra, 'link': {**link, 'master': ids[link['master']]}}
    return ids


def _operations_follow(doc, ids: dict) -> None:
    """Les opérations FAO qui usinent des objets copiés usinent aussi leur copie."""
    fao = (doc.extra or {}).get('fao')
    if not isinstance(fao, dict):
        return
    for op in fao.get('operations') or []:
        items = op.get('items') if isinstance(op, dict) else None
        if isinstance(items, list):
            add = [ids[i] for i in items if i in ids and ids[i] not in items]
            if add:
                op['items'] = items + add


def _to_vd_geo(it, font_table: list) -> None:
    """Un texte de la copie : ses polices absentes (la sienne, celles de ses lettres) en VD Géo, redessiné ; un texte
    TypeEdit (avant d'oublier son objet) : ses lettres en VD Géo dans les boîtes de TypeEdit, l'interlettrage recalé
    sur VD Géo (`vnd.relayout` ; à la lecture, il l'était sur la police de remplacement)."""
    from ..io import vnd
    gone = set(absent(it))
    if it.font in gone:
        it.font = FONT
    fx = TX.char_fx(it)
    if any(f.get('font') in gone for f in fx.values()):
        TX.set_char_fx(it, {i: ({**f, 'font': FONT} if f.get('font') in gone else f) for i, f in fx.items()})
    if not vnd.relayout(it, font_table, {f: FONT for f in gone}):
        it.outline = TX.outline_for(it)


def copy_layers(doc) -> tuple[int, list[str], list, list[str]]:
    """Chaque calque qui a des textes en police absente : une copie juste devant lui (le VND écrit et TypeEdit
    montrent le premier calque, et l'ordre des calques du VND reste celui du dessin), ces textes en VD Géo ; le calque
    d'origine caché et intact ; le calque actif passe à sa copie. Une copie retrouvée par son nom seul (VND relu sans
    son compagnon : tous ses calques visibles) : marquée de nouveau, pas de deuxième copie, et un seul des deux montré
    — la copie si la police manque encore, sinon l'original (rien n'est usiné deux fois). Rend (textes en VD Géo,
    polices absentes, copies faites, copies cachées parce que leur police est maintenant là)."""
    by_id = {L.id: L for L in doc.layers}
    back = []
    for de, c in copies(doc).items():
        L = by_id.get(de)
        if L is None:
            continue
        if MARK in (c.extra or {}):                        # déjà marquée (compagnon) : l'état des deux calques revu
            if not any(absent(it) for it in _walk(L.items)):
                if c.visible or not L.visible:             # la police est arrivée : l'original, sa copie cachée
                    L.visible, c.visible = True, False
                    back.append(c.name)
                if doc.active_layer is c:
                    doc.active = L.id
            elif doc.active_layer is L and c.visible and not L.visible:
                doc.active = c.id                          # VND réécrit : l'original, écrit devant, est son plan courant
            continue
        texts = [it for it in _walk(L.items) if missing_font(it)]
        c.extra = {**(c.extra or {}), MARK: {'de': L.id, 'polices': sorted({f for t in texts for f in absent(t)},
                                                                          key=str.lower)}}
        if texts:
            if doc.active_layer is L:
                doc.active = c.id
            L.visible, c.visible = False, True
        else:                                              # la police est là : l'original, sa copie cachée
            L.visible, c.visible = True, False
            back.append(c.name)
            if doc.active == c.id:
                doc.active = L.id
    found = missing(doc)
    if not found:
        return 0, [], [], back
    table = list((doc.extra or {}).get('vnd_fonts') or [])
    n, names, made, out, ids = 0, set(), [], [], {}
    act = doc.active_layer
    for L in doc.layers:
        if L.id in found:
            here = sorted({f for t in found[L.id] for f in absent(t)}, key=str.lower)
            c = Layer(name=L.name + SUFFIX, items=[struct_copy(it) for it in L.items], visible=True, locked=L.locked,
                      extra={k: v for k, v in (L.extra or {}).items() if k != 'vnd'}, tool=L.tool)
            change = [missing_font(it) for it in _walk(c.items)]      # avant d'oublier les objets TypeEdit
            ids.update(_renew(c.items))
            for it, todo in zip(list(_walk(c.items)), change):
                if todo:
                    _to_vd_geo(it, table)                  # avant d'oublier l'objet TypeEdit : ses boîtes servent
                    n += 1
                drop_source_object(it)
            c.extra[MARK] = {'de': L.id, 'polices': here,      # objet copié → objet d'origine (VND écrit : `for_vnd`)
                             OBJECTS: {cit.id: [it.id, signature(cit)] for cit, it in zip(c.items, L.items)}}
            names.update(here)
            L.visible = False
            if act is L:                                   # calque actif (ou premier calque, sans calque actif)
                doc.active = c.id
            out.append(c)
            made.append(c)
        out.append(L)
    doc.layers[:] = out
    _operations_follow(doc, ids)
    return n, sorted(names, key=str.lower), made, back
