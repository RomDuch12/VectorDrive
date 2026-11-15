"""Paramètres de parcours enregistrés dans TypeEdit (`CONFIG/PathParam_*.TPP`,
les modèles de la fenêtre « Créer un parcours ») — interopérabilité
seulement, rien de Gravotech n'est copié dans VectorDrive.

Format (lu, binaire, petit-boutiste) : des dossiers nommés, et dans chacun
des modèles. Les chaînes sont des CString MFC : longueur sur un octet puis
les caractères ANSI (TypeEdit 13), ou `FF FE FF`, longueur, caractères
UTF-16 (TypeEdit 15). Un dossier : deux entiers négatifs (huit octets `FF`
en 13, −3, −2 en 15, d'autres pour les groupes de la palette), le nombre
d'éléments qu'il contient (modèles, sous-dossiers, et séparateurs « ---- »,
dossiers vides), son nom ; l'arbre est écrit dans l'ordre, chaque dossier
suivi de ses éléments. Un modèle : quatre octets `FF`, son nom, trois entiers, le
type de parcours (`CP_Cutting_3D`, `CP_Sweeping`…), `01 01 00 00 00`, le
nom d'un groupe, `01`, le nombre de sections (entier 32 bits), puis chaque
section : nom, nombre d'entrées, et autant de couples clé / valeur
(chaînes). Les longueurs sont en mètres, les angles en radians.

Après les sections, la fiche de chaque outil du modèle (une, ou plusieurs
pour une gamme) : un entier, la version, le nom de l'outil, puis le même
bloc que dans les bases d'outils (`cam.tooldb`) — numéro, nature,
diamètre, angle, référence, fournisseur, avances. Le modèle importé garde
ces outils : le formulaire s'ouvre avec le bon, et la palette montre pour
chaque modèle son outil (numéro, nom, référence).

Clés reprises : PROFONDEUR (ZBOTTOM profondeur, ZUP Z de départ, NBSLICES
nombre de passes, PROFPASSE passe), SPECIALDECOUPE (AllowanceEdit
surépaisseur, DecInternal côté : 1 intérieur, 2 extérieur, 0 sur le trait,
climbMilling avalant, AddLinks pontets, HeightOfBridge, LengthOfBridge,
DistanceUnderBridge), Properties (iEnable / oEnable entrée et sortie).
"""
from __future__ import annotations

import glob
import math
import os
import pathlib
import re
import struct
from dataclasses import dataclass, field

#: type de parcours TypeEdit → (bouton de la palette VectorDrive, stratégie)
TYPES = {
    'CP_Plotting': ('trace', 'gravure'), 'CP_Plotting_WaterJet': ('trace', 'gravure'), 'CP_Vinyl': ('trace', 'vinyle'),
    'CP_Cutter': ('trace', 'vinyle'), 'CP_Gamme_Chamfer': ('decoupe', 'chanfrein_bord'),
    'CP_Boring': ('percage', 'percage'), 'CP_Boring_WaterJet': ('percage', 'percage'),
    'CP_Sweeping': ('gravure', 'poche'),
    'CP_Cutting_3D': ('decoupe', 'contour'), 'CP_Cutting_WaterJet': ('decoupe', 'contour'),
    'CP_Engraving_3D': ('gravure3d', 'vcarve'), 'CP_Intaglio': ('gravure3d', 'vcarve'),
    'CP_Engraving_Prismatic': ('prismatique', 'prismatique'),
    'CP_Finishing': ('gravure3d', 'vcarve'),            # finition de gravure : bords et tirés d'angle
    'CP_Embossing': ('relief', 'fer_dorer'),                 # fer à dorer gaufrant
    'CP_TypeArt': ('relief', 'relief'), 'CP_TypeArtSequence': ('relief', 'relief'),
    'CP_Sequence_MultiTool': ('gamme', 'vcarve'),       # gamme : ébauche (poche) + finition (2,5D)
}
#: dossiers où TypeEdit range ses paramètres de parcours
CONFIG_GLOBS = ['C:/TypeEdit_*/CONFIG/PathParam_*.TPP', 'C:/TypeEdit_*/CONFIG/PathParam_*.tpp',
                os.path.join(os.environ.get('PROGRAMDATA', 'C:/ProgramData'), 'Gravotech', 'TypeEdit_*', 'CONFIG',
                             'PathParam_*.TPP')]
_UNI = b'\xff\xfe\xff'


@dataclass
class Preset:
    name: str
    kind: str                                          # type TypeEdit (CP_…)
    folder: str = ''
    sections: dict = field(default_factory=dict)       # section → {clé: valeur}
    offset: int = 0
    end: int = 0                                       # fin des sections
    tools: list = field(default_factory=list)          # CamTool des fiches du modèle

    def value(self, section: str, key: str, default: float = 0.0) -> float:
        try:
            return float(self.sections.get(section, {}).get(key, default))
        except (TypeError, ValueError):
            return default


def _cstr(b: bytes, pos: int) -> tuple[str, int]:
    """CString MFC à `pos` (ANSI ou Unicode) → (texte, position suivante)."""
    if b[pos:pos + 3] == _UNI:
        pos += 3
        n = b[pos]
        pos += 1
        if n == 0xFF:
            n = struct.unpack_from('<H', b, pos)[0]
            pos += 2
        raw = b[pos:pos + 2 * n]
        if len(raw) < 2 * n:
            raise IndexError('chaîne coupée')
        return raw.decode('utf-16-le', 'replace'), pos + 2 * n
    n = b[pos]
    pos += 1
    if n == 0xFF:
        n = struct.unpack_from('<H', b, pos)[0]
        pos += 2
    raw = b[pos:pos + n]
    if len(raw) < n:
        raise IndexError('chaîne coupée')
    return raw.decode('cp1252', 'replace'), pos + n


def _lenstr(b: bytes, pos: int) -> tuple[str, int]:
    return _cstr(b, pos)


def _ending_at(b: bytes, end: int, longest: int = 120) -> tuple[int | None, str | None]:
    """Chaîne (ANSI ou Unicode) qui finit juste avant `end`."""
    for n in range(1, min(longest, end)):
        k = end - 2 * n - 4                            # Unicode : FF FE FF n, 2n octets
        if k >= 0 and b[k:k + 3] == _UNI and b[k + 3] == n:
            return k, b[k + 4:end].decode('utf-16-le', 'replace')
        k = end - n - 1
        if b[k] == n:
            return k, b[k + 1:end].decode('cp1252', 'replace')
    return None, None


def _name_before(b: bytes, end: int, longest: int = 120) -> tuple[int | None, str | None]:
    """Nom d'un modèle, qui finit juste avant `end` : précédé de quatre
    octets FF ; à défaut, la plus courte chaîne qui y finit."""
    first = None
    for n in range(1, min(longest, end)):
        for k, raw, enc in ((end - 2 * n - 4, 4, 'utf-16-le'), (end - n - 1, 1, 'cp1252')):
            if k < 0:
                continue
            if enc == 'cp1252' and b[k] != n or enc != 'cp1252' and (b[k:k + 3] != _UNI or b[k + 3] != n):
                continue
            found = (k, b[k + raw:end].decode(enc, 'replace'))
            if b[max(0, k - 4):k] == b'\xff' * 4:
                return found                           # en-tête d'un modèle : le nom entier
            first = first or found
    return first or (None, None)


def _printable(s: str) -> bool:
    return bool(s) and all(c >= ' ' for c in s) and not set(s) <= {'-', ' '}


def _entries(b: bytes) -> list[tuple[int, str, int]]:
    """(position, nom, nombre d'éléments) des dossiers et des séparateurs
    (« ------ », dossiers vides de TypeEdit, nom vide ici) : le nombre
    compte les modèles et les dossiers placés dessous (arborescence)."""
    out = []
    for m in re.finditer(rb'(?=[\xf0-\xff]\xff\xff\xff[\xf0-\xff]\xff\xff\xff[^\xff])', b):
        p = m.start()                                  # deux entiers de −16 à −1 (dossier, groupe), puis le nombre
        if p + 13 > len(b) or (p >= 4 and b[p - 4:p] == b'\xff' * 4 and b[p] == 0xFF):
            continue                                   # suite de FF : pas un en-tête
        try:
            name, _end = _cstr(b, p + 12)
        except IndexError:
            continue
        count = struct.unpack_from('<i', b, p + 8)[0]
        if not 0 <= count < 100000 or not 0 < len(name) < 100 or any(c < ' ' for c in name):
            continue
        out.append((p, name.strip() if _printable(name) else '', count))
    return sorted(out)


def _folders(b: bytes) -> list[tuple[int, str]]:
    """(position, nom) des dossiers : huit octets 0xFF (TypeEdit 13) ou les
    entiers −3, −2 (TypeEdit 15), un entier, le nom."""
    out = []
    for marker in (b'\xff' * 8, b'\xfd\xff\xff\xff\xfe\xff\xff\xff'):
        i = 0
        while True:
            p = b.find(marker, i)
            if p < 0 or p + 13 > len(b):
                break
            i = p + 8
            if marker[0] == 0xFF and b[p + 8] == 0xFF:
                continue                               # suite de FF : pas un en-tête
            try:
                name, _end = _cstr(b, p + 12)
            except IndexError:
                continue
            if 0 < len(name) < 100 and _printable(name):
                out.append((p, name.strip()))
    return sorted(out)


def _tools(seg: bytes) -> list:
    """Fiches d'outils d'un modèle (après ses sections) : entier, version,
    nom, bloc d'outil de TypeEdit (`cam.tooldb`)."""
    from . import tooldb
    out = []
    k = 0
    while k < len(seg) - 16:
        v = struct.unpack_from('<i', seg, k + 4)[0]
        if v in (1, 2, 3, 4) and seg[k + 8] not in (0,):
            try:
                name, pos = _cstr(seg, k + 8)
            except IndexError:
                name, pos = '', 0
            size = 0x378 if v < 3 else 0x3f8
            if name and len(name) < 120 and all(c >= ' ' for c in name) and pos + size <= len(seg):
                blk = seg[pos:pos + size]
                ty = struct.unpack_from('<i', blk, 4)[0]
                dia = struct.unpack_from('<d', blk, 8)[0]
                if 0 <= ty <= 8 and 1e-6 < dia < 0.2:
                    _ty, t, _notes = tooldb._tool_of(name.strip(), v, blk)
                    out.append(t)
                    k = pos + size
                    continue
        k += 1
    return out


def _cp_strings(b: bytes):
    """(début de la chaîne, type CP_…, position après) des types de parcours."""
    for m in re.finditer(rb'CP_[A-Za-z0-9_]+', b):
        k = m.start() - 1
        if k >= 0 and b[k] == len(m.group(0)):
            yield k, m.group(0).decode('ascii'), m.end()
    for m in re.finditer(rb'C\x00P\x00_\x00(?:[A-Za-z0-9_]\x00)+', b):
        k = m.start() - 4
        if k >= 0 and b[k:k + 3] == _UNI and b[k + 3] == len(m.group(0)) // 2:
            yield k, m.group(0).decode('utf-16-le'), m.end()


def parse(data: bytes) -> list[Preset]:
    """Modèles d'un fichier TPP (ceux qu'on sait lire ; le reste est sauté)."""
    out = []
    folders = _folders(data)
    entries = _entries(data)
    for k, kind, end in sorted(_cp_strings(data)):
        if data[end:end + 5] != b'\x01\x01\x00\x00\x00':
            continue
        try:
            _group, pos = _cstr(data, end + 5)
            if data[pos] != 1:
                continue
            nsec = struct.unpack_from('<I', data, pos + 1)[0]
            pos += 5
            if not 0 < nsec < 64:
                continue
            sections = {}
            for _ in range(nsec):
                sec, pos = _cstr(data, pos)
                n = struct.unpack_from('<I', data, pos)[0]
                pos += 4
                if n > 1000:
                    raise ValueError('section trop longue')
                d = {}
                for _ in range(n):
                    key, pos = _cstr(data, pos)
                    val, pos = _cstr(data, pos)
                    d[key] = val
                sections[sec] = d
        except (IndexError, ValueError, struct.error):
            continue
        if 'PARAMPCR' not in sections:
            continue
        _j, name = _name_before(data, k - 12)
        if not name:
            continue
        out.append(Preset(name.strip(), kind, '', sections, k, pos))
    _place(out, entries)
    # fiches d'outils : entre la fin des sections et le modèle (ou le dossier) suivant
    starts = sorted([p.offset for p in out] + [p for p, _f in folders])
    for p in out:
        nxt = next((s for s in starts if s > p.end), len(data))
        p.tools = _tools(data[p.end:nxt])
    return out


def _place(presets: list[Preset], entries: list) -> None:
    """Dossier de chaque modèle (« Datron/2501 Process ») : les éléments se
    suivent dans l'ordre de l'arbre, chaque dossier annonçant combien il en
    contient (modèles, dossiers, séparateurs)."""
    events = sorted([(p, 'D', name, n) for p, name, n in entries] + [(m.offset, 'M', m, 0) for m in presets],
                    key=lambda e: e[0])
    stack: list = []                                   # [nom, éléments restants]
    for _p, what, obj, n in events:
        while stack and stack[-1][1] <= 0:
            stack.pop()
        if stack:
            stack[-1][1] -= 1
        if what == 'M':
            obj.folder = '/'.join(f for f, _r in stack if f)
        elif obj:                                      # dossier (un séparateur n'en ouvre pas)
            stack.append([obj, n])


def read(path) -> list[Preset]:
    return parse(pathlib.Path(path).read_bytes())


def installed() -> list[str]:
    """Fichiers TPP des TypeEdit installés sur le poste."""
    if os.environ.get('VECTORDRIVE_NO_TYPEEDIT') == '1':
        return []
    found = {os.path.normcase(os.path.abspath(f)): f for g in CONFIG_GLOBS for f in glob.glob(g)}
    return sorted(found.values())


def source_name(path) -> str:
    """Nom du dossier d'import d'un fichier TPP : « TypeEdit 13 — Meca3 »."""
    p = pathlib.Path(path)
    m = re.search(r'TypeEdit_V?(\d+)', str(p), re.IGNORECASE)
    stem = re.sub(r'^PathParam_', '', p.stem, flags=re.IGNORECASE)
    return f'TypeEdit {m.group(1)} — {stem}' if m else f'TypeEdit — {stem}'


def _mm(v: float) -> float:
    return round(v * 1000.0, 4)


def tool_memo(t) -> str:
    """Mémo d'un outil : « T248 Ø3 Z1 L13 — réf. 0068803E (DATRON) »."""
    s = f'T{t.number} {t.name}'
    if t.ref:
        s += f' — réf. {t.ref}'
        if t.vendor:
            s += f' ({t.vendor})'
    elif t.vendor:
        s += f' ({t.vendor})'
    return s


def _gamme_ops(p: Preset, fin, tools: list) -> list:
    """Gamme TypeEdit (SPECIALGAMME_NEW), construite comme une gamme de VectorDrive (`gamme.build`). Relevé dans TE13 sur 25 fichiers de
    9 gammes enregistrées : une ligne ne va à `ZBottom_i` que si `independant_depth_i`, sinon à `ZBottom` ; `NbSlices_i` : ses passes ;
    `Mode3DOnly_i` : Finition 3D ; `SkipExternal` : Ignorer le cadre ; `Allowance` : surépaisseur ; `2dfinishing_i` : aucun effet.
    `AngleDecal_i` : l'angle du balayage, sur toutes les zones, avec `AngleMode_i` à 1 comme dans ces 30 réglages. `ModeOnBottom` 1 : En surface.
    Aucun réglage n'a une autre valeur : 2, En fond de gravure, est supposé d'après l'ordre des boutons."""
    from . import gamme, model
    g = p.sections.get('SPECIALGAMME_NEW', {})

    def val(key, i):
        return p.value('SPECIALGAMME_NEW', f'{key}_{i}') if f'{key}_{i}' in g else 0.0
    base = _mm(p.value('SPECIALGAMME_NEW', 'ZBottom')) or fin.depth
    steps = []
    climb = {}
    for i, t in enumerate(tools):
        own = _mm(val('ZBottom', i)) if str(g.get(f'independant_depth_{i}', '1')) == '1' else 0.0
        depth = own or base
        n = int(val('NbSlices', i) or 0)
        steps.append(gamme.Step(t['id'], 'balayage' if str(g.get(f'Sweeping_{i}', '0')) == '1' else 'contournage', stepover=_mm(val('Stepover', i)),
                                depth=depth, finish3d=str(g.get(f'Mode3DOnly_{i}', '1')) == '1',
                                sweep_angle=round(math.degrees(val('AngleDecal', i)), 3), step_down=round(depth / n, 6) if n > 0 else 0.0))
        if f'climbMilling_{i}' in g:                   # 1 : en opposition, 2 : en avalant
            climb[t['id']] = str(g.get(f'climbMilling_{i}')) == '2'
    glob = p.sections.get('FAO_NEWPARAMGLOB', {})
    common = dict(pass_order=fin.pass_order, start_policy=fin.start_policy, ramp=str(glob.get('PLONGEEANGULAIRE_ATIVE', '0')) == '1')
    if common['ramp']:
        common['ramp_angle'] = round(math.degrees(p.value('FAO_NEWPARAMGLOB', 'PLONGEEANGULAIRE_ANGLE')), 2) or fin.ramp_angle
    setup = model.CamSetup(tools=[model.CamTool.from_dict(d) for d in tools])
    ops = gamme.build(setup, steps, max(s.depth for s in steps), stock=_mm(p.value('SPECIALGAMME_NEW', 'Allowance')),
                      contour_ref='fond' if str(g.get('ModeOnBottom', '1')) == '2' else 'surface',
                      skip_frame=str(g.get('SkipExternal', '0')) == '1', z_start=_mm(p.value('SPECIALGAMME_NEW', 'Zup')) or fin.z_start,
                      label=p.name, **common)
    for o in ops:
        o.climb = climb.get(o.tool_id, o.climb)
    return ops


def _chamfer_gamme_ops(p: Preset, fin, tools: list) -> list:
    """Gamme TypeEdit « chanfrein » (SPECIALGAMME_NEW, une étape par outil) :
    étape à chanfrein (Chamfer2D_i) → chanfrein des bords, largeur
    √(longueur² − hauteur²) du chanfrein (ChamferLength_i, ChamferHeight_i) ;
    les autres → détourage à la profondeur ZBottom_i en NbSlices_i passes,
    côté ModeExternal (1 : extérieur), sens climbMilling_i ; pontets si
    AddLinks_i. Une surépaisseur négative (AllowanceCutting_i) n'est pas
    reprise : elle mordrait dans la pièce."""
    from . import model
    g = p.sections.get('SPECIALGAMME_NEW', {})

    def val(key, i, default=0.0):
        return p.value('SPECIALGAMME_NEW', f'{key}_{i}') if f'{key}_{i}' in g else default
    side = 'exterieur' if str(g.get('ModeExternal', '1')) == '1' else 'interieur'
    ops = []
    for i, t in enumerate(tools):
        depth = _mm(val('ZBottom', i))
        climb = str(g.get(f'climbMilling_{i}', '2')) == '2'
        if str(g.get(f'Chamfer2D_{i}', '0')) == '1':
            h, L = _mm(val('ChamferHeight', i)), _mm(val('ChamferLength', i))
            width = math.sqrt(max(0.0, L * L - h * h)) if L > h else h
            o = model.Operation(name=f'{p.name} — chanfrein', kind='chanfrein_bord', tool_id=t['id'], side=side,
                                climb=climb, chamfer_width=round(width or 0.3, 3), depth=depth or fin.depth)
        else:
            o = model.Operation(name=f'{p.name} — découpe {i}', kind='contour', tool_id=t['id'], side=side,
                                climb=climb, depth=depth or fin.depth)
            n = int(val('NbSlices', i) or 0)
            o.step_down = round(o.depth / n, 6) if n > 0 and o.depth > 0 else _mm(val('ProfPasse', i))
            stock = _mm(val('AllowanceCutting', i))
            o.stock = stock if stock > 0 else 0.0
            if str(g.get(f'AddLinks_{i}', '0')) == '1':
                o.tab_height = _mm(val('HeightOfBridge', i)) or o.tab_height
                o.tab_width = _mm(val('LengthOfBridge', i)) or o.tab_width
                o.tab_gap = _mm(val('DistanceUnderBridge', i))
                o.tabs = 0 if o.tab_gap > 0 else 4
        o.z_start = fin.z_start
        ops.append(o)
    return ops


def to_template(p: Preset, root: str = '') -> dict | None:
    """Modèle d'usinage VectorDrive d'un modèle TypeEdit (une opération et
    les outils de sa fiche) ; None pour un type sans équivalent (TypeArt…).
    `root` : dossier de l'import, où le modèle est rangé (« TypeEdit 13 —
    Meca3 / Atelier »), pour ne pas le mêler aux autres."""
    if p.kind not in TYPES:
        return None
    from . import model
    preset, kind = TYPES[p.kind]
    op = model.Operation(name=p.name, kind=kind)
    depth = _mm(p.value('PROFONDEUR', 'ZBOTTOM'))
    if depth > 0:
        op.depth = depth
    n = int(p.value('PROFONDEUR', 'NBSLICES', 0) or 0)
    step = _mm(p.value('PROFONDEUR', 'PROFPASSE'))
    if n > 1 and depth > 0:
        op.step_down = round(depth / n, 6)
    elif step > 0 and depth > 0:
        op.step_down = min(step, depth)
    op.z_start = _mm(p.value('PROFONDEUR', 'ZUP'))
    # relevé dans TE13 : 0 chaque passe sur tout le dessin, 1 chaque forme jusqu'au fond
    if str(p.sections.get('FAO_NEWPARAMGLOB', {}).get('MODE_MULTIPASSE', '1')) == '0':
        op.pass_order = 'global'
    op.start_policy = 'dessin'                                     # relevé dans TE13 : les contours fermés partent de leur premier point
    # passes de profondeurs différentes (NBSLICES1…n, en mètres)
    if n > 1:
        slices = [_mm(p.value('PROFONDEUR', f'NBSLICES{i}')) for i in range(1, n + 1)]
        if all(v > 0 for v in slices) and max(slices) - min(slices) > 1e-6:
            op.pass_depths = ' '.join(f'{v:g}' for v in slices)
    sd = p.sections.get('SPECIALDECOUPE', {})
    if sd:
        op.stock = _mm(p.value('SPECIALDECOUPE', 'AllowanceEdit'))
        op.side = {'1': 'interieur', '2': 'exterieur', '0': 'sur'}.get(str(sd.get('DecInternal', '2')), 'exterieur')
        op.climb = str(sd.get('climbMilling', '2')) == '2'     # 1 : en opposition, 2 : en avalant (ordre des boutons de TE)
        if str(sd.get('AddLinks', '0')) == '1':
            op.tab_height = _mm(p.value('SPECIALDECOUPE', 'HeightOfBridge')) or op.tab_height
            op.tab_width = _mm(p.value('SPECIALDECOUPE', 'LengthOfBridge')) or op.tab_width
            op.tab_gap = _mm(p.value('SPECIALDECOUPE', 'DistanceUnderBridge'))
            op.tabs = 0 if op.tab_gap > 0 else 4
        op.offset_add = _mm(p.value('SPECIALDECOUPE', 'OffsetAdd'))
        op.chain_cut = str(sd.get('chainMode', '0')) == '1'
        if str(sd.get('AllowanceCheck', '0')) == '1' and op.stock > 0:   # supprimer sur la dernière passe
            op.finish = True
        if str(sd.get('Mode3DOnly', '0')) == '1' and kind == 'contour':   # option Découpe 3D
            op.kind = 'decoupe3d'
        op.corner_round = _mm(p.value('SPECIALDECOUPE', 'Anglearrondi'))
        if str(sd.get('m_AddLoop', '0')) == '1':       # onglet Boucles
            op.corner_loops = True
            op.loop_radius = _mm(p.value('SPECIALDECOUPE', 'm_LoopRadius')) or op.loop_radius
            op.loop_length = _mm(p.value('SPECIALDECOUPE', 'm_LoopLength')) or op.loop_length
            op.loop_min_side = _mm(p.value('SPECIALDECOUPE', 'm_LengthMini')) or op.loop_min_side
            op.loop_angle_min = round(math.degrees(p.value('SPECIALDECOUPE', 'm_AngleMin')), 3) or op.loop_angle_min
            op.loop_angle_max = round(math.degrees(p.value('SPECIALDECOUPE', 'm_AngleMax')), 3) or op.loop_angle_max
            op.loop_check = str(sd.get('m_CheckCollision', '0')) == '1'
    props = p.sections.get('Properties', {})
    glob = p.sections.get('FAO_NEWPARAMGLOB', {})
    if 'PLONGEEANGULAIRE_ATIVE' in glob:
        # plongée angulaire de TypeEdit : entrée en rampe, angle en radians
        op.ramp = str(glob.get('PLONGEEANGULAIRE_ATIVE')) == '1' and kind in ('contour', 'poche', 'gravure')
        if op.ramp:
            op.ramp_angle = round(math.degrees(p.value('FAO_NEWPARAMGLOB', 'PLONGEEANGULAIRE_ANGLE')), 2)
            # ConnectToolpath : TE13 l'ignore en plongée angulaire (il remonte à chaque passe) ; VectorDrive le respecte
            op.link_passes = str(props.get('ConnectToolpath', '0')) == '1' and kind in ('contour', 'poche', 'gravure')
    elif str(props.get('iEnable', '0')) == '1':
        op.ramp = True
    io = p.sections.get('ENTRETANGENTIELLE', {})
    # 1 : « Aucune » (vu dans la boîte de TE13, ses parcours n'ont pas d'entrée) ; 2 : « Automatique » (supposé : aucun réglage ne l'a)
    if str(io.get('ModeIOtgt', '0')) == '2' and op.kind in ('contour', 'laser_decoupe'):
        # rayon de transition, distance et rayon de perçage des réglages globaux (m)
        def glob_mm(key: str) -> float:
            return _mm(p.value('FAO_NEWPARAMGLOB', key)) if key in glob else 0.0
        op.lead_transition = glob_mm('ES_TANGEANCIELLE_RACORD') or 1.0
        op.lead_mode = 'percage'
        op.lead_in = op.lead_out = glob_mm('ES_TANGEANCIELLE_DIST') or 2 * op.lead_transition
        op.lead_pierce = glob_mm('ES_TANGEANCIELLE_RAYON')
    if op.kind == 'decoupe3d':                         # découpe 3D TypeEdit : avec tirés d'angle
        op.corner_pull = True
        if str(props.get('TAP', '0')) == '1':          # tiré d'angle au pied
            op.foot_pull = True
            op.foot_pull_min = float(props.get('TAPMinAngle', 22.5) or 22.5)
            op.foot_pull_max = float(props.get('TAPMaxAngle', 135.0) or 135.0)
        if 'P25D_AngleMax' in glob:
            op.corner_pull_angle = round(math.degrees(p.value('FAO_NEWPARAMGLOB', 'P25D_AngleMax')), 3) or 135.0
    if str(glob.get('OPTIMISATION_ANGLES_G2D', '0')) == '1' and kind == 'poche':   # optimisation des angles
        op.corner_opt = True
        op.corner_opt_angle = round(math.degrees(p.value('FAO_NEWPARAMGLOB', 'OPTIANGLEG2D_AngleMax')), 3) or 135.0
    if 'CUT2D_ON_BOTTOM' in props:                     # gravure 2D : contour respecté en surface ou au fond
        op.contour_ref = 'fond' if str(props.get('CUT2D_ON_BOTTOM')) == '1' else 'surface'
    trace = p.sections.get('SPECIALTRACE', {})
    if trace:                                          # tracé : 1 aller simple, 2 aller-retour, 3 A-R dernière tranche
        op.trace_mode = {'1': 'simple', '2': 'ar', '3': 'dernier'}.get(str(trace.get('ModeTrace', '1')), 'simple')
    sw = p.sections.get('SPECIALSWEEPING', {})
    if sw and kind == 'poche':
        # Balayage TypeEdit : passes parallèles (numéros = ordre des boutons de la
        # fenêtre de TypeEdit 13, FAODLGFR.dll : Aller-retour, En opposition, En avalant ;
        # Sans, Avant, Après)
        op.pocket_mode = 'balayage'
        if _mm(p.value('Properties', 'AllowanceSweep')) > 0:     # surépaisseur propre au cassé d'angle
            op.sweep_contour_stock = _mm(p.value('Properties', 'AllowanceSweep'))
        op.sweep_angle = round(math.degrees(p.value('SPECIALSWEEPING', 'AngleDecal')), 3)
        op.sweep_angle_mode = {'1': 'optimise', '2': 'fixe', '3': 'croise'}.get(str(sw.get('AngleMode', '2')), 'fixe')
        op.sweep_direction = {'1': 'aller_retour', '2': 'opposition', '3': 'avalant'}.get(
            str(sw.get('SweepingMode', '1')), 'aller_retour')
        op.sweep_contour = {'1': 'sans', '2': 'avant', '3': 'apres'}.get(str(sw.get('BreakAngleMode', '1')), 'sans')
        op.sweep_by_zone = str(sw.get('SweepingType', '1')) != '2'       # ordre des boutons de TE13 : Par zone, Avec saut d'îlots
        op.sweep_angle_incr = round(math.degrees(p.value('SPECIALSWEEPING', 'AngleIncr')), 3)
        if op.sweep_contour != 'sans':                                   # le sens ne sert qu'au cassé d'angle : 1 en opposition, 2 en avalant
            op.climb = str(sw.get('BreakAngleClimb', '2')) == '2'
        op.stepover_mm = _mm(p.value('SPECIALSWEEPING', 'Stepover'))
        op.stock = _mm(p.value('SPECIALSWEEPING', 'Allowance')) or op.stock
        if str(sw.get('Texturing', '0')) == '1':      # fond texturé : bornes de l'onglet Texturing
            tx = p.sections.get('TEXTURING', {})
            op.sweep_texture = True
            op.tex_depth_min = _mm(p.value('TEXTURING', 'DepthMin')) or op.tex_depth_min
            op.tex_depth_max = _mm(p.value('TEXTURING', 'DepthMax')) or op.tex_depth_max
            op.tex_len_min = p.value('TEXTURING', 'LengthMin') or op.tex_len_min
            op.tex_len_max = p.value('TEXTURING', 'LengthMax') or op.tex_len_max
            if 'OverlapMin' in tx or 'OverlapMax' in tx:
                op.tex_overlap = (p.value('TEXTURING', 'OverlapMin') + p.value('TEXTURING', 'OverlapMax')) / 2
    fin = p.sections.get('SPECIALFINITION', {})
    if fin and 'climbMilling' in fin:
        op.climb = str(fin.get('climbMilling')) == '2'
    if p.kind == 'CP_Finishing':
        op.vcarve_edges_only = True
        op.vcarve_step = op.step_down                              # relevé dans TE13 : le tout à chaque passe en Z
        op.finish_3d_only = str(fin.get('Mode3DOnly', '0')) == '1'
    grav = p.sections.get('SPECIALGRAVURE', {})
    if grav and kind == 'vcarve':
        # gravure 3D TypeEdit : pas entre les passes décalées (m), sens, cadre ignoré
        op.vcarve_walls = False                                    # relevé dans TE13 : le fond et le bord, rien sur les flancs
        op.vcarve_step = op.step_down                              # et le tout à chaque passe en Z
        st = _mm(p.value('SPECIALGRAVURE', 'Stepover'))
        if st > 0:
            op.resolution = st
            op.stepover_mm = st                                    # TE : la même distance au fond
        if 'climbMilling' in grav:
            op.climb = str(grav.get('climbMilling')) == '2'          # 1 : en opposition, 2 : en avalant
        op.finish_skip_frame = str(grav.get('SkipExternal', '0')) == '1'
        op.stock = _mm(p.value('SPECIALGRAVURE', 'Allowance')) or op.stock
        op.pocket_spiral = str(grav.get('Spiraling', '0')) == '1'          # En spirale
        if str(grav.get('IsLimitednbStep', '0')) == '1':                   # nombre de pas limité
            op.vcarve_max_steps = max(0, int(float(grav.get('NbLimitedStep', 0) or 0)))
        op.pocket_outside_in = str(grav.get('OuterToInner', '0')) == '1'   # En partant de l'extérieur
    if p.kind == 'CP_Intaglio':                        # intaille : ligne médiane
        # TE13, SPECIALINTAILLE/Prismatic : 1 « Optimisé » (les deux flancs en une passe), 0 « Standard » (aller-retour)
        prism = str(p.sections.get('SPECIALINTAILLE', {}).get('Prismatic', '1')).strip()
        op.vcarve_mode = 'axe_ar' if prism in ('0', '0.') else 'axe'
        op.stock = _mm(p.value('SPECIALINTAILLE', 'Allowance')) or op.stock
    if fin:
        op.stock = _mm(p.value('SPECIALFINITION', 'Allowance')) or op.stock
        if not (grav and kind == 'vcarve' and 'SkipExternal' in grav):    # gravure 3D : celui de SPECIALGRAVURE
            op.finish_skip_frame = str(fin.get('SkipExternal', '0')) == '1'
    tools = []
    for t in p.tools:
        d = t.to_dict()
        d['folder'] = ''
        d['catalog'] = {**(d.get('catalog') or {}), 'typeedit': p.name}
        tools.append(d)
    ops = [op]
    if tools:
        op.tool_id = tools[-1]['id']                   # gamme : la finition ; l'ébauche passe avant
        if p.kind == 'CP_Sequence_MultiTool' and len(tools) > 1:
            op.ref_tool_id = tools[0]['id']
            ops = _gamme_ops(p, op, tools)
        elif p.kind == 'CP_Gamme_Chamfer' and p.sections.get('SPECIALGAMME_NEW'):
            ops = _chamfer_gamme_ops(p, op, tools)
    dicts = []
    for o in ops:
        d = o.to_dict()
        d['items'] = []
        dicts.append(d)
    d = dicts[0]
    folder = '/'.join(x for x in (root.strip(), p.folder.strip()) if x)
    name = f'{folder} / {p.name}' if folder else p.name
    memo = [tool_memo(t) for t in p.tools]
    desc = f'TypeEdit : {p.name} ({p.kind}{", " + p.folder if p.folder else ""})'
    if memo:
        desc += '\n' + '\n'.join(f'Outil : {m}' for m in memo)
    return {'format': 'vectordrive-modele-fao', 'version': 2, 'name': name, 'description': desc,
            'tools': tools, 'operations': dicts, 'post': '', 'machine': '', 'preset': preset,
            'origine': 'typeedit', 'dossier': folder, 'outils_memo': memo}
