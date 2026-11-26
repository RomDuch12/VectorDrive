"""Post-processeur Fanuc Robocut : électroérosion à fil, code ISO, axes X Y (table) et U V (guide haut).

Il écrit les parcours d'électroérosion à fil (`cam.wire_edm`, leur cycle `fil_edm`) : point de départ (G92), absolu
ou relatif (G90 / G91), compensation du fil (G41 / G42 et un registre D par passe, G40), dépouille constante
(G51 à gauche, G52 à droite, G50 annulée, angle sous l'adresse A), contours haut et bas (U V à chaque point),
enfilage et coupe du fil entre les contours, arrêt programmé avant la coupe d'une attache, compensation et
dépouille annulées et guide haut ramené droit après chaque contour et avant la fin (G40 G50, U0 V0), fin M02. Les
registres D sont numérotés sur tout le programme (un par valeur de décalage).

Ce qui peut casser le fil ou la pièce bloque l'écriture : rien n'est écrit et l'avertissement commence par
« BLOQUANT » (reconnu par `cam.preflight`) — avertissement bloquant du calcul (`cam.wire_edm`), orientation de
sortie autre que normale, mouvements du parcours qui ne sont plus ceux du cycle, inclinaison au-delà de la limite,
coupe ou attache dans un morceau déjà détaché quand plusieurs opérations se suivent (`_whole` : un seul calcul des
chutes sur tout le programme), électroérosion répartie en plusieurs programmes (dit au parcours par
`post.program_groups`). Les attaches « en fin » d'une
opération sont coupées après ses contours, avant l'opération suivante.

Ces codes viennent de la documentation publique des commandes Fanuc pour électroérosion à fil et des usages
courants ; tout ce qui peut changer d'une machine à l'autre est un réglage (`OPTIONS`, gardé dans
`CamSetup.post_options['robocut']`). **Rien n'a été essayé sur une machine** : le programme dit dans son en-tête
qu'il est à vérifier, et la liste de ce qu'il faut vérifier est dans les notes du round.

Le cœur ne déclare aucun post-processeur (ils viennent des plugins) : celui-ci est déclaré par un plugin qui
appelle `register(api)` (le post et la machine « Fanuc Robocut »), ou par un essai le temps de l'essai.
"""
from __future__ import annotations

from . import PostResult, ascii_only

KEY = 'robocut'
LABEL = 'Fanuc Robocut (électroérosion à fil)'

#: réglages du post (à vérifier sur la machine) et leurs valeurs d'office
OPTIONS = {
    'numero': 1,                    # numéro du programme (O)
    'absolu': True,                 # G90 (absolu) ; sinon G91 (relatif)
    'decimales': 3,
    'numeroter': False,             # numéros de blocs N
    'pas_numero': 10,
    'fin': 'M02',                   # fin de programme (M02 ou M30)
    'arret': 'M00',                 # arrêt avant la coupe d'une attache (M00, ou M01 : arrêt optionnel)
    'enfilage': 'M60',              # enfilage automatique du fil
    'coupe_fil': 'M50',             # coupe du fil
    'enfiler_debut': False,         # enfiler au premier trou (sinon le fil y est enfilé avant le départ)
    'gauche': 'G41',                # compensation du fil à gauche du sens de coupe
    'droite': 'G42',
    'sans': 'G40',
    'mot_decalage': 'D',            # adresse du registre de décalage
    'cone_gauche': 'G51',           # dépouille : fil penché à gauche du sens de coupe
    'cone_droite': 'G52',
    'cone_sans': 'G50',
    'mot_angle': 'A',               # adresse de l'angle de dépouille (°)
    'cone_seul': False,             # dépouille sur un bloc à elle, avant le mouvement (sinon sur le mouvement)
    'inverser_uv': False,           # U V de signe opposé (guide haut compté dans l'autre sens)
    #                                 (l'inclinaison la plus forte est un réglage de l'opération : une seule limite)
    'reglage_plans': '',            # ligne écrite après l'en-tête : {plan}, {guides}, {epaisseur} (vide : commentaire)
    'extension': '.nc',
}


def options_of(setup) -> dict:
    """Les réglages du post : `OPTIONS` complétés par ceux du dessin."""
    o = dict(OPTIONS)
    got = (getattr(setup, 'post_options', None) or {}).get(KEY) if setup is not None else None
    if isinstance(got, dict):
        for k, v in got.items():
            if k in o and isinstance(v, type(o[k])) or (k in o and isinstance(o[k], float) and isinstance(v, int)):
                o[k] = v
    o['decimales'] = max(0, min(6, int(o['decimales'])))
    return o


def _comment(text: str) -> str:
    t = ascii_only(str(text)).upper().replace('(', '[').replace(')', ']')
    return f'({t})'


class _Writer:
    """Les lignes d'un programme : états modaux (compensation, dépouille, position) et formats."""

    def __init__(self, o: dict, four: bool):
        self.o = o
        self.four = four                                 # U V écrits (contours haut et bas)
        self.lines: list = []
        self.n = 0
        self.pos = None                                  # (x, y, u, v) programmés
        self.comp = ('', 0)                              # (côté, registre) en vigueur
        self.cone = ('', 0.0)
        self.want_comp = ('', 0)
        self.want_cone = ('', 0.0)
        self.threaded = False
        self.last = ''                                   # la dernière ligne écrite (sans numéro de bloc)

    def emit(self, text: str) -> None:
        self.last = text
        if self.o['numeroter'] and not text.startswith('(') and text != '%':
            self.n += self.o['pas_numero']
            text = f'N{self.n} {text}'
        self.lines.append(text)

    def num(self, v: float) -> str:
        s = f'{v:.{self.o["decimales"]}f}'
        if float(s) == 0.0:
            s = f'{0.0:.{self.o["decimales"]}f}'
        return s if '.' in s else s + '.'

    def words(self, pt) -> str:
        x, y = float(pt[0]), float(pt[1])
        u, v = (float(pt[2]), float(pt[3])) if len(pt) >= 4 else (0.0, 0.0)
        if self.o['inverser_uv']:
            u, v = -u, -v
        if self.o['absolu'] or self.pos is None:
            vals = (x, y, u, v)
        else:
            vals = (x - self.pos[0], y - self.pos[1], u - self.pos[2], v - self.pos[3])
        self.pos = (x, y, u, v)
        out = f'X{self.num(vals[0])} Y{self.num(vals[1])}'
        if self.four:
            out += f' U{self.num(vals[2])} V{self.num(vals[3])}'
        return out

    def modal(self) -> str:
        """Les mots de compensation et de dépouille à écrire avec le mouvement qui suit (changés seulement)."""
        o, out = self.o, []
        if self.want_comp != self.comp:
            side, d = self.want_comp
            out.append(o['sans'] if not side else f'{o[side]} {o["mot_decalage"]}{d}')
            self.comp = self.want_comp
        if self.want_cone != self.cone:
            side, a = self.want_cone
            words = o['cone_sans'] if not side else f'{o["cone_" + side]} {o["mot_angle"]}{self.num(a)}'
            self.cone = self.want_cone
            if o['cone_seul']:
                self.emit(words)
            else:
                out.append(words)
        return ' '.join(out)

    def move(self, code: str, pt) -> None:
        m = self.modal()
        self.emit(' '.join(w for w in (code, m, self.words(pt)) if w))

    def reset(self, force: bool = False) -> None:
        """Compensation et dépouille annulées (G40 G50, toujours avec `force`), guide haut ramené droit (U0 V0, en
        4 axes) : fil coupé, à la fin d'un contour et avant la fin du programme (pas deux fois de suite)."""
        o = self.o
        cancel = f'{o["sans"]} {o["cone_sans"]}'
        if self.comp != ('', 0) or self.cone != ('', 0.0) or (force and self.last != cancel):
            self.emit(cancel)
        self.comp = self.want_comp = ('', 0)
        self.cone = self.want_cone = ('', 0.0)
        if self.four and self.pos is not None and (abs(self.pos[2]) > 1e-12 or abs(self.pos[3]) > 1e-12):
            u, v = (0.0, 0.0) if o['absolu'] else (-self.pos[2], -self.pos[3])
            self.emit(f'G00 U{self.num(u)} V{self.num(v)}')
            self.pos = (self.pos[0], self.pos[1], 0.0, 0.0)


def _points(cy) -> list:
    """Les points (x, y) des blocs du cycle, dans l'ordre des mouvements montrés (contours, puis attaches)."""
    out = []
    for b in list(cy.get('blocs') or []) + list(cy.get('attaches') or []):
        if b.get('op') == 'rapide':
            out.append((float(b['pt'][0]), float(b['pt'][1])))
        elif b.get('op') == 'coupe':
            out += [(float(q[0]), float(q[1])) for q in b.get('pts') or []]
    return out


def _shift(tp, cy) -> tuple:
    """(dx, dy, problème) : le décalage des coordonnées du cycle que le zéro du programme a donné aux mouvements
    (`anchor` : le premier mouvement au calcul). Chaque mouvement doit rester le point du cycle décalé de (dx, dy) :
    sinon (orientation de sortie, mouvements retouchés, parcours recalculé à moitié) le problème est dit."""
    pts = _points(cy)
    if len(pts) != len(tp.moves):
        return 0.0, 0.0, f'{len(tp.moves)} mouvements pour {len(pts)} points du cycle'
    if not pts:
        return 0.0, 0.0, ''
    a = cy.get('anchor') or [pts[0][0], pts[0][1]]
    dx, dy = float(a[0]) - tp.moves[0].x, float(a[1]) - tp.moves[0].y
    for (x, y), m in zip(pts, tp.moves):
        if abs(x - dx - m.x) > 1e-6 or abs(y - dy - m.y) > 1e-6:
            return 0.0, 0.0, f'mouvement en X {m.x:.3f} Y {m.y:.3f} au lieu de X {x - dx:.3f} Y {y - dy:.3f}'
    return dx, dy, ''


def _blockers(tp, cy, setup) -> list:
    """Ce qui empêche d'écrire le parcours (avertissements « BLOQUANT … »)."""
    from ..wire_edm import BLOCKING
    name = tp.name or 'électroérosion'
    out = [f'{BLOCKING} : « {name} » : {w[len(BLOCKING):].lstrip(" :")}' for w in tp.warnings
           if str(w).startswith(BLOCKING)]
    how = getattr(setup, 'output_orient', 'normal') or 'normal'
    if how != 'normal':
        out.append(f'{BLOCKING} : « {name} » : orientation de sortie « {how} » (miroir ou quart de tour) non prise en '
                   'charge en électroérosion à fil : la remettre à « normal »')
    _dx, _dy, gap = _shift(tp, cy)
    if gap:
        out.append(f'{BLOCKING} : « {name} » : les mouvements ne sont plus ceux du calcul ({gap}) : parcours '
                   'transformé (miroir, quart de tour, parcellisation, retouche…), non pris en charge en '
                   'électroérosion à fil')
    r = cy.get('reglages') or {}
    lim = float(r.get('angle_max', 30.0) or 30.0)
    worst = max(abs(float(r.get('angle') or 0.0)), float(r.get('angle_haut_bas') or 0.0))
    if worst > lim + 1e-9 and not any('inclinaison la plus forte' in w for w in out):
        out.append(f'{BLOCKING} : « {name} » : fil incliné de {worst:.2f}°, plus que l\'inclinaison la plus forte de '
                   f'la machine ({lim:g}°)')
    return out


def _whole(items: list, keys=None) -> list:
    """Tout le programme d'un coup, quand il a plusieurs opérations d'électroérosion (`items` : [(nom, cycle, son
    calcul a déjà signalé une coupe dans un morceau détaché)] dans l'ordre d'écriture) : UN seul `find_pieces` sur
    la matière, les étapes de toutes les opérations à la suite (chacune : ses contours, ses attaches avancées, puis
    ses attaches « en fin »), les attaches « à part » de toutes en dernier (le second programme). Toute coupe ou
    attache dans un morceau déjà détaché (pièce extérieure tombée puis recoupée, zone qu'un tour général ou une coupe
    de bord à bord fait tomber avec ses pièces encore tenues, trous d'une opération suivante dans une pièce déjà
    découpée…) : avertissement bloquant. Ce qu'une opération fait seule est déjà signalé par son calcul.
    La matière : l'union des bruts des opérations (le brut du dessin quand il y en a un, le même pour toutes).

    Gardé en mémoire avec la liste des parcours (`keys` : leurs identités de calcul) et leurs cycles eux-mêmes
    (comparés par `is`) : l'aperçu de la fenêtre Programme, le programme d'essai et l'écriture d'un même calcul ne le
    refont pas."""
    if len(items) < 2:
        return []
    key = tuple(keys) if keys is not None else None
    cys = [cy for _n, cy, _s in items]
    for k, kept, out in _WHOLE:
        if key is not None and k == key and len(kept) == len(cys) and all(a is b for a, b in zip(kept, cys)):
            return list(out)
    out = _whole_check(items)
    if key is not None:
        del _WHOLE[:-7]                                  # les 8 derniers calculs seulement
        _WHOLE.append((key, cys, list(out)))
    return out


#: résultats de `_whole` : [(identités des parcours, leurs cycles, avertissements)], les plus récents à la fin
_WHOLE: list = []


def _whole_check(items: list) -> list:
    from shapely.ops import unary_union
    from ..wire_edm import BLOCKING, find_pieces, poly_of
    bruts = [poly_of(cy.get('brut')) for _n, cy, _s in items if cy.get('brut')]
    stock = unary_union([b for b in bruts if not b.is_empty]) if bruts else None
    if stock is None or stock.is_empty:
        return []
    bride = next((cy['bride'] for _n, cy, _s in items if len(cy.get('bride') or []) >= 2), None)
    steps, who, late = [], [], []

    def add(i, st):
        steps.append({'lines': st.get('lignes') or [], 'main': st.get('principal') or None,
                      'kerf': st.get('saignee'), 'tab': bool(st.get('attache'))})
        who.append((i, st))
    for i, (_n, cy, _s) in enumerate(items):
        for st in cy.get('etapes') or []:
            add(i, st)
        tabs = cy.get('etapes_attaches') or []
        if (cy.get('reglages') or {}).get('attache_coupe') == 'apart':
            late += [(i, st) for st in tabs]
        else:
            for st in tabs:
                add(i, st)
    for i, st in late:
        add(i, st)
    kerf = max([float(s['kerf'] or 0.0) for s in steps] + [0.01])
    _pieces, problems, _held = find_pieces(stock, steps, kerf, bride)
    out = []
    for a, b in problems:
        (ia, sa), (ib, sb) = who[a], who[b]
        if ia == ib and items[ia][2]:                    # dans une même opération : son calcul l'a déjà dit
            continue
        what = 'l\'attache du contour' if sa.get('attache') else 'le contour'
        at = 'de l\'attache du contour' if sb.get('attache') else 'du contour'
        msg = (f'{BLOCKING} : « {items[ia][0]} » : {what} {sa.get("contour")} est coupé dans un morceau déjà '
               f'détaché (tombé à la fin {at} {sb.get("contour")} de « {items[ib][0]} ») : le fil couperait une '
               'matière qui n\'est plus tenue — mettre ces contours dans la même opération, changer l\'ordre des '
               'opérations ou poser une attache')
        if msg not in out:
            out.append(msg)
    return out


def _registers(blocks: list) -> dict:
    """Les registres D du programme : un par valeur de décalage (au 1/10 000 de mm), numérotés dans l'ordre
    d'apparition sur tout le programme (deux opérations n'emploient pas le même D pour deux valeurs)."""
    regs: dict = {}
    for b in blocks:
        if b.get('op') == 'comp' and b.get('cote') and b.get('d'):
            key = round(float(b.get('valeur') or 0.0), 4)
            regs.setdefault(key, len(regs) + 1)
    return regs


def _moved(pt, dx: float, dy: float) -> list:
    q = [float(v) for v in pt]
    q[0] -= dx
    q[1] -= dy
    return q


def _header(w: _Writer, title: str, number: int, cys: list, regs: dict, tail: str = '') -> None:
    w.emit('%')
    w.emit(f'O{number:04d} ' + _comment(title or 'PROGRAMME'))
    w.emit(_comment('VectorDrive - electroerosion a fil - a simuler avant usinage'))
    w.emit(_comment('programme non essaye sur la machine : codes a verifier'))
    if tail:
        w.emit(_comment(tail))
    for cy in cys:
        r = cy.get('reglages') or {}
        w.emit(_comment(f'fil {r.get("fil", 0):.3f} etincelage {r.get("gap", 0):.3f} '
                        f'saignee {r.get("saignee", 0):.3f}'))
        w.emit(_comment(f'epaisseur {r.get("epaisseur", 0):.3f} plan de programmation {r.get("plan", 0):.3f} '
                        f'distance entre guides {r.get("guides", 0):.3f}'))
        if r.get('inclinaison') == 'constante' and r.get('angle'):
            a = float(r['angle'])
            w.emit(_comment(f'depouille {abs(a):.3f} deg a {"gauche" if a > 0 else "droite"} du sens de coupe, '
                            f'u/v {float(r.get("uv", 0)):.3f}'))
        elif r.get('inclinaison') == 'haut_bas':
            w.emit(_comment('contours haut et bas : u v a chaque point'))
        line = w.o['reglage_plans']
        if line:
            try:
                w.emit(line.format(plan=w.num(r.get('plan', 0.0)), guides=w.num(r.get('guides', 0.0)),
                                   epaisseur=w.num(r.get('epaisseur', 0.0))))
            except (KeyError, IndexError, ValueError):
                w.emit(_comment('reglage des plans illisible : ' + line))
    if regs:                                             # registres de tout le programme
        w.emit(_comment('decalages ' + ' '.join(f'{w.o["mot_decalage"]}{i} {d:.4f}' for d, i in regs.items())))
    w.emit('G90' if w.o['absolu'] else 'G91')


def _blocks(w: _Writer, blocks: list, first: list, regs: dict) -> None:
    """Les blocs d'un cycle (`cam.wire_edm`) en lignes ; `first` : [vrai] tant que le point de départ n'est pas
    posé (le premier déplacement devient G92) ; `regs` : les registres D du programme (`_registers`)."""
    o = w.o
    for b in blocks:
        op = b.get('op')
        if op == 'rapide':
            if first[0]:
                pt = b['pt']
                w.emit(f'G92 X{w.num(pt[0])} Y{w.num(pt[1])}' + (f' U{w.num(0)} V{w.num(0)}' if w.four else ''))
                w.pos = (float(pt[0]), float(pt[1]), 0.0, 0.0)
                first[0] = False
                if not o['enfiler_debut']:
                    w.threaded = True
                    w.emit(_comment('fil enfile au trou de depart'))
            else:
                w.move('G00', b['pt'])
        elif op == 'enfiler':
            if not w.threaded:
                w.emit(o['enfilage'])
            w.threaded = True
        elif op == 'couper_fil':
            w.emit(o['coupe_fil'])
            w.threaded = False
        elif op == 'comp':
            side = b.get('cote') or ''
            d = regs.get(round(float(b.get('valeur') or 0.0), 4), int(b.get('d') or 0)) if side else 0
            w.want_comp = (side, d)
        elif op == 'remise':
            w.reset()
        elif op == 'cone':
            side = b.get('cote') or ''
            w.want_cone = (side, float(b.get('angle') or 0.0)) if side and float(b.get('angle') or 0) > 0 \
                else ('', 0.0)
        elif op == 'arret':
            w.emit(f'{o["arret"]} ' + _comment(b.get('texte', '')))
        elif op == 'coupe':
            for pt in b.get('pts') or []:
                w.move('G01', pt)


def write(toolpaths, setup, *, title: str = '', machine=None, stem: str = 'programme', box_mm=None) -> PostResult:
    """Le programme Fanuc Robocut des parcours d'électroérosion à fil ; les autres parcours sont laissés de côté
    (avertissement). Attaches coupées « à part » : un second fichier, `<nom>_attaches`. Un avertissement bloquant
    (`_blockers`) : rien n'est écrit."""
    from ..wire_edm import BLOCKING, KIND, split_wire
    o = options_of(setup)
    warnings = ['Fanuc Robocut : codes G et M à vérifier sur la machine avant le premier usinage (réglages du post)']
    others, wire = split_wire(toolpaths)
    if others:
        warnings.append(f'{len(others)} parcours qui ne sont pas de l\'électroérosion à fil : pas écrits')
    main, apart, cys, blockers = [], [], [], []
    for tp in wire:
        cy = next(c for c in tp.cycles if isinstance(c, dict) and c.get('kind') == KIND)
        blockers += _blockers(tp, cy, setup)
        dx, dy, _gap = _shift(tp, cy)

        def moved(blocks):
            out = []
            for b in blocks:
                b = dict(b)
                if 'pt' in b:
                    b['pt'] = _moved(b['pt'], dx, dy)
                if 'pts' in b:
                    b['pts'] = [_moved(q, dx, dy) for q in b['pts']]
                out.append(b)
            return out
        r = cy.get('reglages') or {}
        cys.append(cy)
        main += moved(cy.get('blocs') or [])
        # attaches : après les contours de leur opération (avant l'opération suivante), chacune après un arrêt
        (apart if r.get('attache_coupe') == 'apart' else main).extend(moved(cy.get('attaches') or []))
    items = [(tp.name or 'électroérosion', cy, any(str(w).startswith(BLOCKING) and 'déjà détaché' in w
                                                   for w in tp.warnings)) for tp, cy in zip(wire, cys)]
    blockers += _whole(items, [(getattr(tp, 'uid', ''), n, f) for tp, (n, _cy, f) in zip(wire, items)])
    four = any(abs(float(q[2])) > 1e-12 or abs(float(q[3])) > 1e-12
               for b in main + apart for q in ([b['pt']] if 'pt' in b else []) + list(b.get('pts') or [])
               if len(q) >= 4)
    if not wire:
        return PostResult('', warnings + ['aucun parcours d\'électroérosion à fil à écrire'], o['extension'])
    if blockers:                                         # le fil ou la pièce en danger : rien n'est écrit
        return PostResult('', blockers + warnings, o['extension'])
    regs = _registers(main + apart)
    w = _Writer(o, four)
    _header(w, title, int(o['numero']), cys, regs)
    _blocks(w, main, [True], regs)
    w.reset(force=True)
    w.emit(o['fin'])
    w.emit('%')
    text = '\n'.join(w.lines) + '\n'
    files = [(stem + o['extension'], text)]
    if apart:
        w2 = _Writer(o, four)
        _header(w2, (title or 'programme') + ' attaches', int(o['numero']) + 1, cys, regs,
                'placer le fil au trou de depart de la premiere attache')
        _blocks(w2, apart, [True], regs)
        w2.reset(force=True)
        w2.emit(o['fin'])
        w2.emit('%')
        files.append((stem + '_attaches' + o['extension'], '\n'.join(w2.lines) + '\n'))
        warnings.append('attaches coupées dans un programme à part : ' + files[-1][0])
    return PostResult(text, warnings, o['extension'], files=files)


write.wire_edm = True                                    # électroérosion à fil : ce post écrit les cycles fil_edm


def register(api) -> None:
    """Déclaration par un plugin : le post-processeur et la machine « Fanuc Robocut » (ruban FAO 2D)."""
    api.add_post(KEY, LABEL, write)
    api.add_machine(KEY, 'Fanuc Robocut', kind='fraiseuse', posts=(KEY,),
                    tip='Électroérosion à fil : contours, fil incliné (U/V), chutes')
