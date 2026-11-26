"""Lanceur de VectorDrive.

    python VectorDrive.py [fichier]
    python VectorDrive.py --autotest          contrôle l'installation, rapport sur stdout
    python VectorDrive.py --convert entree.vnd --to dxf [--out dossier]

`--autotest` vérifie qu'un exécutable empaqueté est complet : démarrer sans
planter ne prouve pas que les lecteurs de formats et leurs dépendances
sont embarqués.
"""
from __future__ import annotations

import argparse
import pathlib
import sys
import time
import traceback

_T0 = time.perf_counter()        # mesure du démarrage (VECTORDRIVE_TEMPS=1)

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))


def free_name(dest: pathlib.Path) -> pathlib.Path:
    """`dest`, ou « nom (2).ext », « nom (3).ext »… s'il existe déjà."""
    n = 2
    out = dest
    while out.exists():
        out = dest.with_name(f'{dest.stem} ({n}){dest.suffix}')
        n += 1
    return out


def convert(src: str, fmt: str, out_dir: str | None, keep: bool = False) -> int:
    from vectordrive import plugins
    from vectordrive.io import registry
    plugins.load()                                      # formats des plugins (programmes machine…)
    doc = registry.open_document(src)
    p = pathlib.Path(src)
    dest = pathlib.Path(out_dir or p.parent) / f'{p.stem}.{fmt.lstrip(".")}'
    if keep:
        dest = free_name(dest)                          # menu de l'explorateur : jamais d'écrasement
    registry.save_document(doc, dest)
    st = doc.stats()
    print(f'{p.name} -> {dest} ({st["objets"]} objets, {st["contours"]} contours)')   # console cp1252
    for r in doc.report:
        print(f'  remarque : {r}')
    return 0


def autotest() -> int:
    import os
    import tempfile
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    # réglages dans un fichier temporaire : l'autotest ne touche pas au profil
    _tmp = tempfile.mkdtemp(prefix='vd_autotest_')
    import atexit
    import shutil
    atexit.register(shutil.rmtree, _tmp, True)          # supprimé à la fin : rien ne reste dans le Temp
    os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(_tmp, 'reglages.ini'))
    os.environ.setdefault('VECTORDRIVE_CACHE', _tmp)
    os.environ.setdefault('VECTORDRIVE_TOOLS', os.path.join(_tmp, 'outils', 'tools.json'))
    os.environ.setdefault('VECTORDRIVE_SESSION_TEMP', os.path.join(_tmp, 'sessions'))
    os.environ.setdefault('VECTORDRIVE_CAM_TEMPLATES', os.path.join(_tmp, 'modeles_fao'))
    os.environ.setdefault('VECTORDRIVE_SESSION', os.path.join(_tmp, 'session'))
    os.environ.setdefault('VECTORDRIVE_BIBLIOTHEQUE', os.path.join(_tmp, 'bibliotheque'))
    try:
        # console en cp1252 : un caractère non affichable ne doit pas faire échouer un contrôle
        sys.stdout.reconfigure(errors='replace')
    except (AttributeError, ValueError):
        pass
    ok = ko = 0

    def check(name, fn):
        nonlocal ok, ko
        t = time.perf_counter()
        try:
            detail = fn() or ''
            ok += 1
            print(f'  OK   {name} {detail} ({(time.perf_counter() - t) * 1000:.0f} ms)', flush=True)
        except Exception as ex:
            ko += 1
            print(f'  ÉCHEC {name} : {ex}', flush=True)
            traceback.print_exc(limit=3)

    from vectordrive import __version__
    print(f'VectorDrive {__version__} — autotest', flush=True)
    from vectordrive.core import geom
    from vectordrive.core.document import Document, Shape
    from vectordrive.io import registry

    def t_geom():
        c = geom.circle((0, 0), 10)
        L = c.length()
        assert abs(L - 2 * 3.141592653589793 * 10) < 1e-3, L
        return f'cercle Ø20 : {L:.4f} mm'
    check('géométrie exacte', t_geom)

    def t_formats():
        import tempfile
        doc = Document()
        doc.add(Shape(path=geom.Path([geom.rect(0, 0, 80, 40, 5)])))
        doc.add(Shape(path=geom.Path([geom.circle((40, 20), 8)])))
        with tempfile.TemporaryDirectory() as d:
            res = []
            for ext in ('vdz', 'svg', 'dxf', 'pdf', 'eps'):           # programmes machine : formats des plugins
                f = pathlib.Path(d) / f'essai.{ext}'
                registry.save_document(doc, f)
                back = registry.open_document(f)
                n = back.stats()['contours']
                assert n == 2, f'{ext} : {n} contours relus'
                res.append(ext)
        return 'aller-retour ' + ', '.join(res)
    check('formats', t_formats)

    def t_vnd_new():
        import tempfile
        from vectordrive.io import vnd
        doc = Document()
        doc.add(Shape(path=geom.Path([geom.circle((40, 20), 8)])))
        with tempfile.TemporaryDirectory() as d:
            f = pathlib.Path(d) / 'neuf.vnd'
            registry.save_document(doc, f)
            back = vnd.read(f)
        L = sum(it.path.length() for it in back.iter_leaves())
        assert abs(L - 2 * 3.141592653589793 * 8) < 1e-6, L
        return f'cercle relu {L:.6f} mm, {len(back.tools)} outils'
    check('VND neuf (modèle embarqué)', t_vnd_new)

    def t_fonts():
        from vectordrive.core import fonts
        f = fonts.find_font('Arial')
        assert f, 'aucune police'
        g, adv = fonts.glyph(f[0], f[1], 'A')
        assert g and adv > 0
        return f'{len(fonts.families())} polices, « A » = {len(g.contours)} contours'
    check('polices', t_fonts)

    def t_pathops():
        import math
        from vectordrive.core import pathops
        sq = geom.Path([geom.rect(0, 0, 10, 10)])
        a = pathops.area(pathops.offset(sq, 1.0, 'round'))
        assert abs(a - (140 + math.pi)) < 1e-3, a
        u = pathops.area(pathops.boolean(sq, geom.Path([geom.rect(5, 5, 10, 10)]), 'union'))
        assert abs(u - 175) < 1e-6, u
        return f'moteur {pathops.available()}, offset et union exacts'
    check('booléens et décalage', t_pathops)

    def t_snap_dup():
        from vectordrive.core import duplicate
        from vectordrive.core.snap import Snap
        sq = Shape(path=geom.Path([geom.rect(0, 0, 10, 10)]))
        circ = Shape(path=geom.Path([geom.circle((50, 50), 10)]))
        s = Snap(enabled=True, grid_step=5)
        hits = [s.query(10.2, 9.9, 1, [sq, circ]), s.query(5.1, 0.2, 1, [sq, circ]),
                s.query(50.3, 50.2, 1, [sq, circ]), s.query(24.7, 30.2, 1, [sq, circ])]
        kinds = [h.kind for h in hits]
        assert kinds == ['node', 'middle', 'center', 'grid'], kinds
        n = len(duplicate.circular([sq], 8, (0, 0))) + len(duplicate.grid([sq], 3, 3, 12, 12))
        assert n == 15, n
        return 'nœud, milieu, centre, grille ; 15 copies'
    check('accrochage et duplication', t_snap_dup)

    def t_i18n_update():
        import json
        import tempfile
        from vectordrive import i18n, update
        try:
            i18n.set_language('en')
            assert i18n.tr('Fichier') == 'File', 'table anglaise absente'
        finally:
            i18n.set_language('fr')
        with tempfile.TemporaryDirectory() as t:
            src = pathlib.Path(t)
            (src / 'setup.exe').write_bytes(b'essai')
            (src / update.MANIFEST).write_text(json.dumps({
                'version': '999.0.0', 'installer': 'setup.exe',
                'sha256': update.sha256_file(src / 'setup.exe')}), encoding='utf-8')
            up = update.check(str(src))
            assert up and up.version == '999.0.0'
            dl = src / 'dl'
            dl.mkdir()
            update.fetch(up, dl)
        return 'FR/EN, manifeste et empreinte vérifiés'
    check('langues et mises à jour', t_i18n_update)

    def t_codes():
        from vectordrive.core import codes, pathops
        out = []
        for kind, text in (('datamatrix', 'VectorDrive 2026'), ('qr', 'VectorDrive'), ('code128', 'VD0042-42')):
            spec = codes.BarcodeSpec(kind, text, 0.5, height=10)
            dark = sum(v for row in codes.matrix(spec) for v in row)
            areas = []
            for style in ('runs', 'outline') if kind != 'code128' else ('runs',):
                spec.style = style
                areas.append(pathops.area(codes.paths(spec)[0]))
            want = dark * 0.25 if kind != 'code128' else dark * 0.5 * 10
            assert all(abs(a - want) < 1e-6 for a in areas), (kind, areas, want)
            out.append(f'{kind} {dark} modules')
        return ', '.join(out)
    check('codes-barres', t_codes)

    def t_smb_write():
        from vectordrive.io import smb
        data = smb.build([Shape(path=geom.Path([geom.rect(10, 10, 30, 20, 4)]))])
        root, fonts, ar = smb.parse(data)
        assert ar.pos == len(data) and smb.rewrite(data) == data
        bb = root.fields['bbox']
        assert abs(bb[0] + bb[3]) < 1e-12 and abs(bb[1] + bb[4]) < 1e-12, bb      # centré
        return f"symbole de {len(data)} octets, centré, relu et réécrit à l'identique"
    check('création de symbole', t_smb_write)

    def t_nest():
        from vectordrive.core import combine
        cs = [geom.circle((0, 0), 10), geom.circle((0, 0), 6), geom.circle((0, 0), 2), geom.rect(30, 0, 5, 5)]
        groups = combine.nest(cs)
        assert [len(h) for _o, h in groups] == [1, 0, 0], groups
        assert all(o.signed_area() > 0 for o, _h in groups) and groups[0][1][0].signed_area() < 0
        return '« O » avec son trou, îlot et forme isolée ; sens normalisés'
    check('englobants / englobés', t_nest)

    def t_braille_photo():
        import numpy as np
        from vectordrive.core import braille, halftone
        assert braille.unicode_braille('Salle 12') == '\u2828\u280e\u2801\u2807\u2807\u2811 \u2820\u2821\u2823'
        img = np.tile(np.linspace(1, 0, 100), (50, 1))
        spec = halftone.HalftoneSpec(width=20, pitch=1, min_size=0)
        p = halftone.paths(img, spec)
        k = halftone.density(img, spec)
        ratio = sum(c.signed_area() for c in p.contours) / k.sum()
        assert abs(ratio - 1) < 5e-3, ratio
        return f'braille « Salle 12 », trame de {len(p.contours)} points (aire à {abs(ratio - 1):.1e} près)'
    check('braille et photo', t_braille_photo)

    def t_dial_fill():
        from vectordrive.core import dial, duplicate
        g = dial.build(dial.DialSpec(start=0, sweep=360, divisions=12, major_every=3, medium_every=0,
                                     text_height=0, radius=30))
        assert len(g.children[0].path.contours) == 12
        sq = Shape(path=geom.Path([geom.rect(0, 0, 30, 10)]))
        out, lay = duplicate.fill([sq], (0, 0, 100, 50), 2, 2, 3)
        assert len(out) == 9 and lay['origin'] == (3.0, 8.0), lay
        return 'cadran de 12 graduations, multicopie 3 × 3 centrée'
    check('cadran et multicopie', t_dial_fill)

    def t_biarc():
        from vectordrive.core import biarc
        s = geom.Cubic((0, 0), (10, 30), (40, -20), (50, 10))
        segs = biarc.segment_to_arcs(s, 0.01)
        dev = biarc._deviation(s, segs, 1.0)
        assert dev <= 0.0106, dev
        assert all(isinstance(x, geom.Line) or x.circle_params() for x in segs)
        return f'Bézier en {len(segs)} arcs/droites, écart {dev:.4f} mm'
    check('arcs et segments', t_biarc)

    def t_clip():
        import math
        from vectordrive.core import clip
        p = clip.clip_strokes(geom.Path([geom.circle((10, 5), 4)]), (0, 0, 10, 10))
        assert abs(p.length() - 4 * math.pi) < 1e-9
        return 'demi-cercle coupé au bord : longueur exacte'
    check('rogner', t_clip)

    def t_handles():
        from PySide6.QtWidgets import QApplication
        QApplication.instance() or QApplication([])
        from vectordrive.ui.canvas import Canvas
        m = Canvas.scale_matrix((0, 0, 20, 10), 4, (40, -10))
        assert m.apply((0, 10)) == (0.0, 10.0)
        _m, a = Canvas.rotation_matrix((0, 0, 20, 10), (20, 5), (10, 15))
        assert abs(a - 90) < 1e-9
        return 'poignées : échelle proportionnelle, rotation de 90°'
    check('poignées', t_handles)

    def t_print():
        import tempfile
        from PySide6.QtWidgets import QApplication
        QApplication.instance() or QApplication([])
        from PySide6.QtPrintSupport import QPrinter
        from vectordrive.core.document import Document
        from vectordrive.io import registry
        from vectordrive.ui import printing
        d = Document()
        d.add(Shape(path=geom.Path([geom.rect(0, 0, 100, 20)])))
        with tempfile.TemporaryDirectory() as t:
            f = pathlib.Path(t) / 'p.pdf'
            pr = QPrinter(QPrinter.PrinterMode.HighResolution)
            pr.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
            pr.setOutputFileName(str(f))
            printing.print_drawing(d, pr)
            bb = registry.open_document(f).bbox()
        w, h = bb[2] - bb[0], bb[3] - bb[1]
        assert abs(w - 100) < 0.05 and abs(h - 20) < 0.05, (w, h)
        return f'impression 1:1 vérifiée : {w:.2f} × {h:.2f} mm'
    check('impression', t_print)

    draws = pathlib.Path('C:/ProgramData/Gravotech/TypeEdit_V15-LaserType_V15/DRAWS/watch.gvt')
    if draws.exists():
        def t_gvt():
            from vectordrive.io import registry
            d = registry.open_document(draws)
            assert d.stats()['contours'] == 207 and d.plate and abs(d.plate.width - 30) < 1e-9, d.stats()
            return f"watch.gvt : {d.stats()['contours']} contours, plaque {d.plate.width:g} × {d.plate.height:g} mm"
        check('GVT (TypeEdit 9+)', t_gvt)

    def t_holes():
        from vectordrive.core import holes
        from vectordrive.io import vnd, vnd_write
        d = Document()
        d.add(holes.make((12, 8), holes.HoleSpec(diameter=3, depth=4)))
        data, _ = vnd_write.write_document(d)
        root, _ = vnd.parse(data)
        t = root.children[0].children[0].children[0]
        assert t.cls.name == 'CTrou', t.cls.name
        assert [round(v * 1000, 9) for v in t.fields['pos']] == [12, 8, 0], t.fields['pos']
        assert round(t.fields['profondeur'] * 1000, 9) == 4, t.fields['profondeur']
        return 'trou Ø3 prof. 4 écrit en CTrou'
    check('trous de perçage', t_holes)

    def t_check():
        from vectordrive.core import check as CK
        from vectordrive.core.document import Plate
        from vectordrive.core.geom import Contour, Line
        d = Document()
        d.plate = Plate(100, 50)
        d.add(Shape(path=geom.Path([Contour([Line((0, 0), (10, 0)), Line((10, 0), (10, 10)),
                                             Line((10, 10), (0, 0.05))], False)])))
        d.add(Shape(path=geom.Path([geom.circle((99, 25), 5)])))
        codes = sorted(i.code for i in CK.check(d))
        assert codes == ['hors_plaque', 'presque_ferme'], codes
        fixed = CK.fix_item(d.layers[0].items[0], 'presque_ferme')
        assert fixed.path.contours[0].closed
        return 'hors plaque et contour presque fermé détectés, contour fermé'
    check('vérification avant gravure', t_check)

    def t_nesting():
        from vectordrive.core import nesting as N
        from vectordrive.core.document import Plate
        parts = [Shape(path=geom.Path([geom.rect(0, 0, 45, 20)]))]
        r = N.nest(parts, Plate(100, 50), N.NestSpec(margin=0, gap=0, allow_rotate=False, copies=10))
        assert (len(r.placed), r.plates) == (10, 3), (len(r.placed), r.plates)
        return '10 pièces 45 × 20 sur 3 plaques 100 × 50'
    check('imbrication', t_nesting)

    def t_trace():
        import math
        import numpy as np
        from vectordrive.core import trace as TR
        yy, xx = np.mgrid[0:100, 0:100] + 0.5
        g = np.where(np.hypot(xx - 50, yy - 50) < 30, 0.0, 1.0)
        cs = TR.trace(g, TR.TraceSpec())
        assert len(cs) == 1, len(cs)
        err = abs(cs[0].length() - 2 * math.pi * 30) / (2 * math.pi * 30)
        assert err < 0.02, err
        return f'disque de 30 px tracé, périmètre à {err * 100:.1f} %'
    check('vectorisation', t_trace)

    def t_centerline():
        import numpy as np
        from vectordrive.core import trace as TR
        g = np.ones((60, 200))
        g[95 - 70:101 - 70, 20:180] = 0
        g[5:55, 97:103] = 0
        cs = TR.trace_centerline(g, TR.TraceSpec())
        assert len(cs) == 2 and not any(c.closed for c in cs), [(c.closed, c.bbox()) for c in cs]
        return 'croix de traits de 6 px : 2 traits centraux'
    check('trait central', t_centerline)

    def t_snap_cross():
        import math
        from vectordrive.core.snap import Snap
        b = Shape(path=geom.Path([geom.circle((50, 25), 20)]))
        c = Shape(path=geom.Path([geom.circle((75, 25), 20)]))
        ey = 25 + math.sqrt(400 - 12.5 ** 2)
        h = Snap(enabled=True).query(62.7, ey - 0.3, 1.0, [b, c])
        err = math.dist((h.x, h.y), (62.5, ey))
        assert h.kind == 'intersection' and err < 1e-9, (h, err)
        return f'intersection de deux cercles exacte ({err:.1e} mm)'
    check('accrochage aux intersections', t_snap_cross)

    def t_chain():
        from vectordrive.core import chain as CH
        from vectordrive.core.geom import Contour
        parts = [Contour([s], False) for s in geom.rect(0, 0, 10, 5).segments]
        parts[1] = parts[1].reversed()
        out, j, k = CH.chain(parts[::-1], 0.01)
        assert (j, k, len(out)) == (3, 1, 1) and out[0].closed, (j, k, len(out))
        return 'rectangle éclaté en 4 droites mélangées : 1 contour fermé'
    check('raccord des contours', t_chain)

    def t_guides():
        from vectordrive.core.snap import Snap
        from vectordrive.ui.rulers import tick_steps
        sn = Snap(enabled=True, modes={'guide'})
        sn.guides = [['v', 10.0], ['h', 20.0]]
        h = sn.query(10.4, 19.7, 1.0, [])
        assert (h.x, h.y, h.kind) == (10.0, 20.0, 'guide'), h
        assert tick_steps(3.0) == (2, 20), tick_steps(3.0)
        return 'croisement de guides accroché ; graduations 2 / 20 mm à 3 px/mm'
    check('règles et guides', t_guides)

    def t_raster():
        import tempfile
        from PySide6.QtGui import QImage
        from vectordrive.io import raster
        d = Document()
        d.add(Shape(path=geom.Path([geom.rect(0, 0, 10, 5)]), filled=True))
        with tempfile.TemporaryDirectory() as tmp:
            f = pathlib.Path(tmp) / 'a.png'
            raster.write(d, f, raster.RasterSpec(dpi=254, margin=1, include_plate=False))
            img = QImage(str(f))
        assert (img.width(), img.height()) == (120, 70), (img.width(), img.height())
        return 'PNG 120 × 70 px pour 12 × 7 mm à 254 dpi'
    check('export image', t_raster)

    def t_tool_width():
        from vectordrive.core import check as CK
        d = Document()
        d.tools[0].width = 1.0
        d.add(Shape(path=geom.Path([geom.rect(0, 0, 0.6, 3)])))
        assert 'trop_petit' in {i.code for i in CK.check(d)}
        return 'contour de 0,6 mm signalé pour un outil de 1 mm'
    check('largeur des outils', t_tool_width)

    def t_kerning():
        from vectordrive.core import fonts as F
        from vectordrive.core import text as T
        ff = F.find_font('Calibri') or F.find_font('Arial')
        k = T._kern(ff, 'A', 'V')
        assert k < 0, k
        return f'paire AV : {k:g} unités ({pathlib.Path(ff[0]).name})'
    check('crénage OpenType', t_kerning)


    def t_text_arc():
        import math
        from vectordrive.core import duplicate
        from vectordrive.core import text as TX
        from vectordrive.core.document import Text
        total, at = geom.walker(geom.circle((0, 0), 10))
        assert abs(total - 20 * math.pi) < 1e-9, total
        t = Text(text='VDR', font='Arial', size=4, align='center')
        t.extra['arc'] = {'center': [0, 0], 'radius': 20, 'position': 'top', 'side': 'outside'}
        p = TX.outline_for(t)
        rs = [math.hypot(*q) for c in p.contours for q in c.flatten(0.05)]
        assert rs and 19.7 < min(rs) and max(rs) < 24.3, (min(rs), max(rs))
        n = len(duplicate.along([Shape(path=geom.Path([geom.rect(-1, -1, 2, 2)]))], geom.circle((0, 0), 30), 12))
        assert n == 12
        return f'arc r 20 : {min(rs):.2f} à {max(rs):.2f} mm, 12 copies sur cercle'
    check('texte en arc, duplication sur courbe', t_text_arc)

    def t_hatch():
        import math
        from vectordrive.core import hatch
        r = Shape(path=geom.Path([geom.circle((0, 0), 20), geom.circle((0, 0), 10)]))
        g = hatch.build([r], hatch.HatchSpec(spacing=0.5, angle=30))
        L = sum(c.length() for c in g.children[1].path.contours)
        ref = math.pi * 300 / 0.5
        assert abs(L - ref) < ref * 0.005, (L, ref)
        return f'couronne : {len(g.children[1].path.contours)} traits, {L:.0f} mm (aire/pas {ref:.0f})'
    check('hachures', t_hatch)

    def t_shadow():
        from vectordrive.core import pathops, shadow
        sq = geom.Path([geom.rect(0, 0, 10, 10)])
        a = pathops.area(shadow.shadow_path(sq, shadow.ShadowSpec('pleine', -45, 2 * 2 ** 0.5)))
        assert abs(a - 40) < 1e-6, a
        return f"ombre pleine d'un carré : {a:.6f} mm² (40 attendus)"
    check('ombrage', t_shadow)

    def t_spiral():
        c = geom.spiral((0, 0), 30, 5)
        assert geom.dist(c.end, (30, 0)) < 1e-9 and geom.dist(c.start, (0, 0)) < 1e-9
        return f'5 tours, r 30 : {len(c.segments)} Bézier, {c.length():.3f} mm'
    check('spirale', t_spiral)

    def t_fit():
        import math
        from vectordrive.core import fitcurve
        dense = geom.Path([geom.polyline(geom.circle((0, 0), 20).flatten(0.001), closed=True)])
        a = fitcurve.approximate(dense, 0.01)
        dev = max(abs(math.hypot(*q) - 20) for q in a.contours[0].flatten(1e-4))
        assert dev < 0.01 and a.segment_count() < 20, (dev, a.segment_count())
        return f'cercle de {dense.segment_count()} segments : {a.segment_count()} courbes à {dev:.4f} mm'
    check('approximation', t_fit)

    def t_envelope():
        from vectordrive.core import envelope
        r = Shape(path=geom.Path([geom.rect(0, 0, 40, 10)]))
        g = envelope.build([r], envelope.EnvelopeSpec('arc', 50))
        top = max(y for _, y in g.children[1].path.contours[0].flatten(1e-4))
        assert abs(top - 15) < 1e-3, top
        return f'rectangle 40 × 10 en arc 50 % : sommet à {top:.4f} mm'
    check('enveloppe', t_envelope)

    def t_stamp():
        from vectordrive.core import pathops, stamp
        a = pathops.area(stamp.region(geom.Path([geom.rect(0, 0, 10, 10)]), stamp.StampSpec(margin=2, radius=0, border=1)))
        assert abs(a - 44) < 1e-6, a
        return f"fond d'un tampon carré : {a:.6f} mm² (44 attendus)"
    check('tampon', t_stamp)

    def t_trim():
        import math
        from vectordrive.core import trim
        res = trim.trim(geom.Path([geom.circle((0, 0), 10)]), [geom.Line((-20, 0), (20, 0))], (0, 10))
        L = res.contours[0].length()
        assert abs(L - math.pi * 10) < 1e-6, L
        return f'demi-cercle restant : {L:.9f} mm (π × 10)'
    check('tronquer', t_trim)

    def t_punch():
        from vectordrive.core import punch
        out = punch.cut(geom.Path([geom.rect(0, 0, 10, 10)]), geom.Path([geom.circle((10, 10), 4)]), False, False)
        assert len(out.contours) == 1 and abs(out.length() - 32) < 1e-9, out.length()
        return f'carré poinçonné par un disque : {out.length():.9f} mm de trait (32)'
    check('poinçonner', t_punch)

    def t_parallel():
        import math
        from vectordrive.core import parallel
        [c] = parallel.parallel(geom.circle((0, 0), 10), 1)
        dev = max(abs(math.hypot(*q) - 9) for q in c.flatten(1e-5))
        [sq] = parallel.parallel(geom.rect(0, 0, 10, 10), -1)
        assert dev < 1e-9 and abs(sq.length() - (40 + 2 * math.pi)) < 1e-9, (dev, sq.length())
        return f'cercle décalé à {dev:.1e} mm près, carré : {sq.length():.9f} mm (40 + 2π)'
    check('courbes parallèles', t_parallel)

    def t_offset():
        import math
        from vectordrive.core import parallel, pathops
        ring = geom.Path([geom.circle((0, 0), 10), geom.circle((0, 0), 5)])
        res, exact = parallel.offset_checked(ring, 1)
        a = pathops.area(res)
        assert exact and abs(a - math.pi * (121 - 16)) < 1e-6, (exact, a)
        return f'couronne décalée de 1 mm : {a:.6f} mm² (105π), exact'
    check('décalage exact', t_offset)

    def t_nodes():
        import math
        from vectordrive.core import nodes
        c = nodes.smooth_node(nodes.to_curves(geom.rect(0, 0, 10, 10), [1]), 1)
        a, b = c.segments[1], c.segments[2]
        u, v = (a.p3[0] - a.p2[0], a.p3[1] - a.p2[1]), (b.p1[0] - b.p0[0], b.p1[1] - b.p0[1])
        cr = abs(u[0] * v[1] - u[1] * v[0]) / (math.hypot(*u) * math.hypot(*v))
        assert cr < 1e-9, cr
        return 'coin de carré lissé : poignées alignées'
    check('Mode Point', t_nodes)

    def t_columns():
        from vectordrive.core import text as TX
        from vectordrive.core.document import Text
        t = Text(text='a\nb\nc\nd', font='Arial', size=5)
        cols = TX.columns(t, 2, 3.0)
        assert [c.text for c in cols] == ['a\nb', 'c\nd'], [c.text for c in cols]
        gap = cols[1].outline.bbox()[0] - cols[0].outline.bbox()[2]
        assert abs(gap - 3) < 1e-6, gap
        return 'deux colonnes à 3 mm'
    check('texte en colonnes', t_columns)

    def t_mirror_axis():
        from vectordrive.core.geom import Affine
        m = Affine.reflection((0, 0), (1, 1))
        x, y = m.apply((3, -2))
        assert abs(x + 2) < 1e-12 and abs(y - 3) < 1e-12, (x, y)
        return 'symétrie par rapport à y = x'
    check('miroir sur axe', t_mirror_axis)

    def t_blend():
        import math
        from vectordrive.core import blend
        c = blend.blend(geom.Contour([geom.Line((0, 0), (6, 0))], False),
                        geom.Contour([geom.Line((10, 4), (10, 10))], False), 2)
        assert c is not None and abs(c.length() - (16 + math.pi)) < 1e-9, c
        return f'deux traits écartés raccordés (r 2) : {c.length():.9f} mm (16 + π)'
    check('raccordement', t_blend)

    def t_marker():
        cs = geom.marker((0, 0), 4)
        assert len(cs) == 3 and cs[0].length() == 4, cs
        return 'croix de 4 mm et cercle'
    check('marqueur', t_marker)

    def t_symmetric():
        from vectordrive.core import symmetric
        half = geom.Contour([geom.Line((50, 10), (70, 10)), geom.Line((70, 10), (50, 30))], False)
        r = symmetric.mirror_join(geom.Path([half]), 50)
        assert len(r.contours) == 1 and r.contours[0].closed, r
        return 'demi-losange refermé par son reflet'
    check('dessin symétrique', t_symmetric)

    def t_news():
        from vectordrive.ui import news
        jp = news.journal_path()
        assert jp is not None, 'CHANGELOG.md absent'
        es = news.entries(jp.read_text(encoding='utf-8'))
        assert max(e[1] for e in es) == news.version_tuple(__version__), 'journal en retard sur la version'
        return f'{len(es)} entrées, dernière {es[-1][0][:40]}…'
    check('nouveautés (CHANGELOG embarqué)', t_news)

    def t_qt_fr():
        import PySide6
        from PySide6.QtCore import QLibraryInfo, QTranslator
        t = QTranslator()
        dirs = (QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath),
                str(pathlib.Path(PySide6.__file__).resolve().parent / 'translations'))
        assert any(t.load('qtbase_fr', d) for d in dirs), dirs
        return 'qtbase_fr trouvé (boutons « Annuler »…)'
    check('traductions de Qt', t_qt_fr)

    def t_portable():
        from vectordrive import portable
        mode = 'portable' if portable.is_portable() else 'installé'
        return f'{mode} ; données : {portable.data_dir()}'
    check('mode', t_portable)

    def t_ui():
        from PySide6.QtWidgets import QApplication
        from vectordrive.ui.main_window import MainWindow
        app = QApplication.instance() or QApplication([])
        w = MainWindow()
        w.show()
        app.processEvents()
        w.canvas.doc.add(Shape(path=geom.Path([geom.rect(0, 0, 10, 10)])))
        w.canvas.select_all()
        w.mirror(True)
        w.undo()
        w.modified = False          # pas de boîte « enregistrer ? » en autotest
        w.close()
        return f'{len(w.A)} commandes'
    check('interface', t_ui)

    def t_theme_tabs():
        from PySide6.QtWidgets import QApplication
        from vectordrive.core.document import Layer
        from vectordrive.ui import theme
        from vectordrive.ui.main_window import MainWindow
        QApplication.instance() or QApplication([])
        w = MainWindow()
        settings = (w.settings.value('vue/theme'), w.settings.value('vue/onglets_calques'))
        try:
            d = w.canvas.doc
            d.add(Shape(path=geom.Path([geom.rect(0, 0, 10, 10)])))
            d.layers.append(Layer(name='B', tool=2))
            d.layers[1].items.append(Shape(path=geom.Path([geom.circle((5, 5), 2)]), tool=2))
            w.layers_panel.refresh()
            w.A['layer_tabs'].setChecked(True)
            w.layer_all.setChecked(False)                 # un seul calque visible : l'onglet
            w.layer_tabs.setCurrentIndex(1)               # « B » (plus d'onglet « Tous » depuis 0.229)
            w.canvas.select_all()
            assert w.canvas.selection == d.layers[1].items, 'onglet : autres calques sélectionnés'
            w.A['theme_dark'].setChecked(True)
            assert theme.current().dark and theme.canvas_colors() is theme.current().canvas
            w.A['theme_dark'].setChecked(False)
            assert not theme.current().dark
            w.A['layer_tabs'].setChecked(False)
        finally:
            for k, v in zip(('vue/theme', 'vue/onglets_calques'), settings):
                if v is None:
                    w.settings.remove(k)
                else:
                    w.settings.setValue(k, v)
            w.modified = False
            w.close()
        return 'calque seul en onglet, thème sombre et retour au clair'
    check('mode sombre, calques en onglets', t_theme_tabs)

    def t_cam():
        from vectordrive.cam import model, post, strategies, typeedit
        from vectordrive.core.document import Document
        d = Document()
        d.add(Shape(path=geom.Path([geom.rect(0, 0, 30, 15), geom.circle((8, 7.5), 3)])))
        s = model.CamSetup(tools=[model.CamTool(name='F2', diameter=2, step_down=0.5)])
        s.operations = [model.Operation(kind=k, tool_id=s.tools[0].id, depth=1) for k in ('poche', 'contour')]
        tps = strategies.compute_all(d, s)
        assert all(tp.moves and not tp.warnings for tp in tps), [tp.warnings for tp in tps]
        back = typeedit.read_bytes(typeedit.write_bytes(tps[1]))
        assert len(back.moves) == len(tps[1].moves)
        return f'{sum(len(tp.moves) for tp in tps)} mouvements'
    check('FAO : poche, détourage, parcours TypeEdit', t_cam)

    def t_posts():
        from vectordrive.cam import model, post, strategies
        from vectordrive.core.document import Document
        assert post.BUILTIN == {}, post.BUILTIN                  # le cœur n'en contient aucun
        found = post.posts()
        if not found:
            try:
                post.run('gcode', [], model.CamSetup())
            except post.PostError:
                return 'aucun dans le cœur (ils viennent des plugins)'
            raise AssertionError('post-processeur sans plugin')
        d = Document()
        d.add(Shape(path=geom.Path([geom.rect(0, 0, 20, 10)])))
        s = model.CamSetup(tools=[model.CamTool(name='F2', diameter=2, number=3, kind='fraise')])
        s.operations = [model.Operation(kind='gravure', tool_id=s.tools[0].id)]
        tps = strategies.compute_all(d, s)
        names = []
        for key in found:
            res = post.run(key, tps, s, stem='essai')
            names.append(f'{key} ({len(res.files)})')
        return 'des plugins : ' + ', '.join(names)
    check('post-processeurs', t_posts)

    def t_simulation():
        from vectordrive.cam import model, simulate
        s = model.CamSetup(tools=[model.CamTool(kind='conique', diameter=6, angle=90)])
        tp = model.Toolpath(op_id='', tool_id=s.tools[0].id)
        tp.moves = [model.Move('rapid', 0, 0, 2), model.Move('plunge', 0, 0, -1), model.Move('feed', 20, 0, -1)]
        r = simulate.simulate([tp], s, res=0.05)
        j = int(round((0.5 - r.y0) / r.res))
        i = int(round((10 - r.x0) / r.res))
        assert abs(r.H[j, i] + 0.5) < 0.03, r.H[j, i]          # flanc du V à 45°
        return f'sillon en V : {r.removed:.1f} mm³ enlevés'
    check("simulation d'enlèvement de matière", t_simulation)

    def t_shortcuts():
        from PySide6.QtWidgets import QApplication
        from vectordrive.ui import shortcuts as SC
        from vectordrive.ui.main_window import MainWindow
        QApplication.instance() or QApplication([])
        w = MainWindow()
        try:
            for scheme in SC.schemes():
                m = SC.effective(w._default_shortcuts, scheme)
                assert not SC.conflicts(m), (scheme, SC.conflicts(m))
            m = SC.effective(w._default_shortcuts, *SC.load(w.settings))
            e = SC.parse_turbokey('CMD_000=ID_EDIT_REDO\nMOD_000=FCONTROL FNOINVERT FVIRTKEY\nKEY_000=E\n')
            assert e == [('ID_EDIT_REDO', 'Ctrl+E')], e
            n = sum(1 for v in m.values() if v)
        finally:
            w.modified = False
            w.close()
        return f'{n} commandes avec raccourci (jeu « {SC.load(w.settings)[0]} »), aucun conflit dans les jeux'
    check('raccourcis TypeEdit (TeTurboKey.ini)', t_shortcuts)

    def t_cam_palette():
        from vectordrive.cam import model, strategies
        from vectordrive.core.document import Document
        d = Document()
        d.add(Shape(path=geom.Path([geom.rect(0, 0, 30, 15)])))
        v = model.CamTool(kind='conique', diameter=6, angle=60, tip=0.2, step_down=1, cut_length=10)
        big, small = model.CamTool(diameter=4), model.CamTool(diameter=1)
        las = model.CamTool(kind='laser', diameter=0.1)
        s = model.CamSetup(tools=[v, big, small, las])
        ops = [model.Operation(kind='decoupe3d', tool_id=v.id, depth=0.5),
               model.Operation(kind='poche', tool_id=big.id, depth=0.5, stock=v.radius_at(0.5)),
               model.Operation(kind='vcarve', tool_id=v.id, depth=0.5, ref_tool_id=big.id),
               model.Operation(kind='reste', tool_id=small.id, ref_tool_id=big.id, depth=0.5),
               model.Operation(kind='laser_gravure', tool_id=las.id, resolution=0.2)]
        out = []
        for op in ops:
            tp = strategies.compute(d, s, op)
            assert tp.moves, (op.kind, tp.warnings)
            out.append(f'{op.kind} {len(tp.moves)}')
        return ', '.join(out)
    check('FAO : découpe 3D, gamme, reste matière, gravure laser', t_cam_palette)

    def t_bat_companion():
        import tempfile
        from vectordrive.core.document import Document, Plate
        from vectordrive.io import companion, proof, vnd
        from vectordrive.io.vnd_write import write
        d = Document()
        d.plate = Plate(x=0, y=0, width=600, height=400)
        a = Shape(path=geom.Path([geom.rect(10, 10, 20, 8)]))
        d.add(a)
        d.add(Shape(path=geom.Path([geom.circle((500, 300), 40)])))
        k_all = proof.page_scale(d, proof.ProofInfo())
        views = proof._geometry(d, proof.ProofInfo(), [a])['views']
        k_sel = views[-1]['k']
        assert k_all < 1 and views[0]['k'] == 1 and k_sel > 1, (k_all, views)        # 1:1 coté + agrandissement
        d.extra['guides'] = [('v', 12.0)]
        with tempfile.TemporaryDirectory() as tmp:
            f = os.path.join(tmp, 'essai.vnd')
            write(d, f)
            cp, why = companion.sync(d, f)
            assert cp is not None and why == ['guides'], why
            back = vnd.read(f)
            msgs = companion.apply(back, f)
            assert back.extra.get('guides') and 'relu' in msgs[0], msgs
        return f'BAT de la sélection à {proof.scale_label(k_sel)} (tout : {proof.scale_label(k_all)}), ' \
               f'VND + compagnon relu'
    check('BAT de la sélection, VND avec compagnon .vdz', t_bat_companion)

    def t_progress():
        import time
        from PySide6.QtWidgets import QApplication
        from vectordrive.core import progress as P
        from vectordrive.ui import progress as UP
        QApplication.instance() or QApplication([])
        assert UP.run(None, 'essai', lambda: 6 * 7) == 42

        def endless():
            for i in range(2000):
                P.step(i, 2000)
                time.sleep(0.005)
        UP.AUTO_CANCEL_AFTER_MS = 80
        t0 = time.monotonic()
        try:
            UP.run(None, 'essai', endless)
            raise AssertionError('calcul non annulé')
        except P.Cancelled:
            pass
        finally:
            UP.AUTO_CANCEL_AFTER_MS = None
        return f'calcul dans un fil, annulé en {int((time.monotonic() - t0) * 1000)} ms'
    check('Barre de progression et Annuler', t_progress)

    def t_themes():
        from PySide6.QtWidgets import QApplication
        from vectordrive.ui import theme, themes
        from vectordrive.ui.main_window import MainWindow
        QApplication.instance() or QApplication([])
        assert (len(themes.LIGHT_KEYS), len(themes.DARK_KEYS)) == (5, 25)
        w = MainWindow()
        before = w.settings.value('vue/theme')
        try:
            for key in ('typeedit', 'minuit', 'clair'):
                w.set_theme(key)
                assert theme.current().key == key, key
            te = themes.installed_typeedit()
        finally:
            if before is None:
                w.settings.remove('vue/theme')
            else:
                w.set_theme(str(before))
            w.modified = False
            w.close()
        return f'{len(themes.all_themes())} thèmes ; TypeEdit du poste : ' + \
            (f'{len(te)} couleurs lues' if te else 'absent (couleurs de la V15)')
    check('Thèmes (5 clairs, 25 sombres, TypeEdit)', t_themes)

    def t_view3d():
        from PySide6.QtGui import QGuiApplication
        from PySide6.QtWidgets import QApplication
        from vectordrive.cam import relief
        from vectordrive.core.document import Plate
        from vectordrive.ui import view3d
        QApplication.instance() or QApplication([])
        d = Document()
        d.plate = Plate(width=40, height=20)
        d.add(Shape(path=geom.Path([geom.circle((20, 10), 6)])))
        r = relief.build(d, 'auto', res=0.1)
        assert r.source == 'dessin' and abs(r.sim.deepest + relief.DEFAULT_DEPTH) < 1e-9, r.sim.deepest
        strips, per = view3d.mesh(r.sim, exag=3)
        detail = f'relief {r.sim.H.shape[1]} × {r.sim.H.shape[0]}, maillage {strips.shape[0] * per} sommets'
        if QGuiApplication.platformName() != 'offscreen':
            v = view3d.View3D()
            v.resize(200, 120)
            v.set_relief(r)
            v.grabFramebuffer()
            detail += ', OpenGL ' + ('oui' if v.ok else 'non (vue de dessus ombrée)')
        return detail
    check('Plan de travail en 3D (relief, maillage)', t_view3d)

    def t_mesh3d():
        import struct
        import tempfile
        from vectordrive.io import mesh3d, registry
        tris = []
        for z, x0 in ((5.0, 0.0), (3.0, 10.0)):              # deux marches vues de dessus
            a, b, c, d = (x0, 0, z), (x0 + 10, 0, z), (x0 + 10, 10, z), (x0, 10, z)
            tris += [(a, b, c), (a, c, d)]
        with tempfile.TemporaryDirectory() as tmp:
            f = os.path.join(tmp, 'marches.stl')
            with open(f, 'wb') as fh:
                fh.write(b'\0' * 80 + struct.pack('<I', len(tris)))
                for t in tris:
                    fh.write(struct.pack('<3f', 0, 0, 0) + b''.join(struct.pack('<3f', *v) for v in t) + b'\0\0')
            doc = registry.open_document(f)
            names = [L.name for L in doc.layers]
            assert names[:2] == ['Pz 5', 'Pz 3'], names
            try:
                mesh3d.read_catia(os.path.join(tmp, 'x.CATPart'), _NoConverter())
                raise AssertionError('CATIA sans convertisseur accepté')
            except ValueError as ex:
                assert 'STEP' in str(ex)
        return 'STL : ' + ', '.join(names) + ' ; CATIA : message d\'export sans convertisseur'

    class _NoConverter:
        @staticmethod
        def value(key, default=None):
            return ''
    check('Pièces 3D : STL, 3D XML, CATIA', t_mesh3d)

    def t_parity():
        import math
        from vectordrive.core import graduation, shapes, textops
        from vectordrive.ui import shortcuts
        g = graduation.build(graduation.GraduationSpec(divisions=20, vernier=10))
        assert len(graduation.vernier_ticks(graduation.GraduationSpec(vernier=10))) == 11
        poly = geom.polyline([(5 * math.cos(k * math.pi / 30), 5 * math.sin(k * math.pi / 30)) for k in range(60)],
                             closed=True)
        _p, n = shapes.to_circles(geom.Path([poly, geom.rect(0, 0, 4, 4)]))
        assert n == 1, n
        assert textops.change_case('saint-étienne', 'mots') == 'Saint-Étienne'
        assert textops.find_replace('Lot 1, lot 2', 'lot', 'N°') == ('N° 1, N° 2', 2)
        return f'{len(shortcuts.TE_ACTIONS)} commandes TypeEdit reliées ; règle et vernier ' \
               f'({len(g.children)} parties), cercles reconnus, casse, remplacer'
    check('Parité TypeEdit (commandes, graduations, textes)', t_parity)

    def t_cam_templates():
        from vectordrive.cam import model, templates
        s = model.CamSetup()
        f = model.CamTool(name='F2', diameter=2.0, number=1)
        s.tools = [f]
        s.operations = [model.Operation(kind='contour', depth=1.0, tool_id=f.id, sources=[1])]
        tpl = templates.from_setup(s, 'essai')
        out, rep = templates.apply(s, tpl, sources=[2])
        assert len(out.operations) == 2 and len(out.tools) == 1 and out.operations[1].sources == [2], rep
        return f'modèle appliqué ({rep[0]}), outil retrouvé ; {len(templates.all_templates())} modèle(s) disponibles'
    check('Modèles d\'usinage', t_cam_templates)

    def t_custom_ribbon():
        from PySide6.QtWidgets import QApplication
        from vectordrive.ui import ribbon_editor as RE
        from vectordrive.ui.main_window import MainWindow
        QApplication.instance() or QApplication([])
        w = MainWindow()
        before = (w.settings.value(RE.KEY), w.settings.value(RE.HIDDEN))
        try:
            n = w.ribbon.count()
            RE.save(w.settings, {'titre': 'Essai', 'groupes': [{'titre': 'G', 'commandes': [{'key': 'open', 'big': True}]}]})
            w._build_custom_tab()
            assert w.ribbon.count() == n + 1 and w.ribbon.tabText(0) == 'Essai'
        finally:
            for k, v in zip((RE.KEY, RE.HIDDEN), before):
                if v is None:
                    w.settings.remove(k)
                else:
                    w.settings.setValue(k, v)
            w.modified = False
            w.close()
        return 'onglet personnel construit et retiré'
    check('Ruban personnalisé (Mon onglet)', t_custom_ribbon)

    def t_tangents():
        import math
        from vectordrive.core import shapes
        b = shapes.belt((0, 0), 2, (10, 0), 2)
        assert abs(b.signed_area() - (40 + 4 * math.pi)) < 0.05, b.signed_area()
        n = len(shapes.circle_tangents((0, 0), 2, (10, 0), 1, 'toutes'))
        assert n == 4, n
        return f'enveloppe de deux cercles, {n} tangentes'
    check('Tangentes et enveloppe de deux cercles', t_tangents)

    def t_doc_templates():
        import tempfile
        from vectordrive.io import doc_templates, native
        d = Document()
        d.add(Shape(path=geom.Path([geom.rect(0, 0, 10, 10)])))
        with tempfile.TemporaryDirectory() as tmp:
            old = os.environ.get('VECTORDRIVE_DOC_TEMPLATES')
            os.environ['VECTORDRIVE_DOC_TEMPLATES'] = tmp
            try:
                f = doc_templates.save(d, 'Plaque × essai')
                assert 'Plaque × essai' in doc_templates.templates()
                back = native.read(f)
                assert len(list(back.iter_items())) == 1
            finally:
                if old is None:
                    os.environ.pop('VECTORDRIVE_DOC_TEMPLATES')
                else:
                    os.environ['VECTORDRIVE_DOC_TEMPLATES'] = old
        return 'modèle de dessin enregistré et relu'
    check('Modèles de dessin', t_doc_templates)

    def t_text_format():
        from PySide6.QtWidgets import QApplication
        from vectordrive.core.document import Text
        from vectordrive.ui.main_window import MainWindow
        QApplication.instance() or QApplication([])
        w = MainWindow()
        try:
            t = Text(text='Essai', font='Arial', size=4)
            w.canvas.doc.layers[0].items.append(t)
            w.canvas.select([t])
            w._on_selection()
            w.textbar.size.setValue(8)
            assert t.size == 8 and t.outline is not None
            assert w.set_text_align('right') == 1 and t.align == 'right'
        finally:
            w.modified = False
            w.close()
        return 'onglet Mise en forme : hauteur, alignement appliqués'
    check('Mise en forme des textes', t_text_format)

    def t_batch():
        import tempfile
        from vectordrive.io import batch, registry
        with tempfile.TemporaryDirectory() as tmp:
            d = Document()
            d.add(Shape(path=geom.Path([geom.rect(0, 0, 10, 5)])))
            src = os.path.join(tmp, 'essai.vdz')
            registry.save_document(d, src)
            out = os.path.join(tmp, 'sortie')
            res = batch.convert([src], out, 'dxf')
            assert len(res.done) == 1 and os.path.isfile(os.path.join(out, 'essai.dxf')), res.summary()
        return res.summary()
    check('Traitement par lots', t_batch)

    def t_cyclic_notes():
        from PySide6.QtWidgets import QApplication
        from vectordrive.core.document import Plate
        from vectordrive.ui.main_window import MainWindow
        QApplication.instance() or QApplication([])
        w = MainWindow()
        try:
            w.canvas.doc.plate = Plate(width=100, height=100)
            w._set_cyclic(4)
            sh = w.canvas.commit_shape(geom.Path([geom.rect(70, 48, 10, 4)]))
            assert len(sh.path.contours) == 4
            w.A['sym_cyclic'].setChecked(False)
            assert w.add_note('essai', at=(0, 0)) == 0 and w.canvas.notes()[0]['text'] == 'essai'
        finally:
            w.modified = False
            w.close()
        return 'rosace de 4, note posée'
    check('Symétrie cyclique et notes', t_cyclic_notes)

    def t_timing():
        from vectordrive.cam import model, timing
        s = model.CamSetup()
        t = model.CamTool(name='F2', diameter=2.0, feed=600, plunge=100, number=1)
        s.tools = [t]
        op = model.Operation(kind='gravure', tool_id=t.id)
        s.operations = [op]
        tp = model.Toolpath(op.id, t.id, moves=[model.Move('feed', 0, 0, -0.1), model.Move('feed', 100, 0, -0.1)])
        est = timing.estimate([tp], s, timing.TimingSpec(accel=1e9, tool_change=10))
        assert abs(est['total'] - 20.0) < 0.01, est['total']
        return f'100 mm à 600 mm/min + un changement d\'outil : {timing.format_duration(est["total"])}'
    check('Temps d\'usinage estimé', t_timing)

    def t_check_files():
        import tempfile
        from vectordrive.io import batch, registry
        with tempfile.TemporaryDirectory() as tmp:
            d = Document()
            d.add(Shape(path=geom.Path([geom.rect(0, 0, 10, 5)])))
            registry.save_document(d, os.path.join(tmp, 'bon.vdz'))
            with open(os.path.join(tmp, 'abime.dxf'), 'w', encoding='utf-8') as fh:
                fh.write('pas un dxf')
            rows = batch.check(batch.collect([tmp]))
            assert sorted(r['lu'] for r in rows) == [False, True], rows
        return batch.check_summary(rows)
    check('Vérification de dessins (lecture seule)', t_check_files)

    def t_point_xy():
        from PySide6.QtWidgets import QApplication
        from vectordrive.core.document import Plate
        from vectordrive.ui.main_window import MainWindow
        QApplication.instance() or QApplication([])
        w = MainWindow()
        try:
            w.canvas.doc.plate = Plate(width=100, height=60)
            w.set_tool('rect')
            w.point_by_coordinates({'x1': 10, 'y1': 5, 'x2': 40, 'y2': 25})
            bb = w.canvas.doc.layers[0].items[0].bbox()
            assert tuple(round(v, 6) for v in bb) == (10, 5, 40, 25), bb
        finally:
            w.modified = False
            w.close()
        return 'rectangle posé par ses coordonnées'
    check('Points par coordonnées', t_point_xy)

    def t_knife():
        from vectordrive.core import knife
        parts = knife.cut(geom.Path([geom.rect(0, 0, 10, 4)]), geom.Path([geom.polyline([(4, -1), (6, 5)])]))
        assert len(parts) == 2, len(parts)
        total = sum(abs(p.contours[0].signed_area()) for p in parts)
        assert abs(total - 40) < 1e-3, total
        return 'rectangle coupé en deux morceaux, surface conservée'
    check('Couteau', t_knife)

    def t_typeedit_barcode():
        from vectordrive.io import vnd
        from vectordrive.io.mfc import Archive, MfcClass, MfcObject
        from vectordrive.io.vnd_write import MfcWriter, _obdao_fields, w_bcode
        o = MfcObject(MfcClass('CObBCode', 3))
        o.fields = _obdao_fields((0.0, 0.0, 0.0, 0.01, 0.005, 0.0))
        o.fields.update(has_zone=0, zone=None, norme_len=20, norme=b'\x06\x00\x00\x00*DLSOFT*1D*1',
                        data=b'1234567890', var_flag=0, i124=0, var=None, d138=0.0)
        w = MfcWriter()
        w_bcode(w, o)
        back = MfcObject(MfcClass('CObBCode', 3))
        ar = Archive(bytes(w.buf), 0, vnd.READERS)
        vnd.read_bcode(ar, back)
        assert ar.pos == len(w.buf) and back.fields['data'] == b'1234567890'
        return f"code-barres TypeEdit relu ({vnd.bcode_norm(back)}), modèles .vnm lisibles"
    check('Codes-barres et modèles TypeEdit', t_typeedit_barcode)

    def t_typeedit_dial():
        import struct
        from vectordrive.io import vnd
        from vectordrive.io import vnd_write as W
        from vectordrive.io.mfc import Archive, MfcClass, MfcObject
        raw = (struct.pack('<I', 1) + bytes(0x70 + 36) + struct.pack('<i', 5) + b'Arial' + bytes(40)
               + struct.pack('<i', 0) + bytes(8) + struct.pack('<i', 0) + struct.pack('<i', 3) + b'022'
               + bytes(3 * 48) + struct.pack('<I', 0) + struct.pack('<I', 5) + bytes(200)
               + struct.pack('<I', 1) + bytes(44) + struct.pack('<I', 1) + bytes(20))
        o = MfcObject(MfcClass('CObCadran', 5))
        o.fields = W._obdao_fields((0.0, 0.0, 0.0, 0.02, 0.01, 0.0))
        o.fields.update(has_courbe=0, courbe=None, has_zone=0, zone=None, c250=0, c254=0, name_n=0,
                        has_var=0, var=None, has_vernier=1,
                        vernier=vnd._cadran_vernier(Archive(raw, 0, vnd.READERS), 5),
                        prop_a=W._property_extend(), prop_b=W._property_extend(), d_f8=0.0)
        t = W.translated_object(o, 0.01, 0.0)
        w = W.MfcWriter()
        W.w_cadran(w, t)
        back = MfcObject(MfcClass('CObCadran', 5))
        ar = Archive(bytes(w.buf), 0, vnd.READERS)
        vnd.read_cadran(ar, back)
        assert ar.pos == len(w.buf)
        assert struct.unpack_from('<d', back.fields['vernier']['raw'], 4 + 0x10)[0] == 0.01
        return f"cadran TypeEdit relu, déplacé (graduations {vnd.cadran_text(back.fields['vernier']['graduations'], 5)})"
    check('Cadrans TypeEdit', t_typeedit_dial)

    def t_typeedit_v15_barcode():
        import struct
        from vectordrive.io import vnd
        from vectordrive.io import vnd_write as W
        from vectordrive.io.mfc import Archive, MfcClass, MfcObject
        norme = struct.pack('<I', 6) + b'*DLSOFT*2D*3'
        out = []
        for cls in ('CObNewBCode1D', 'CObNewBCode2D'):
            o = MfcObject(MfcClass(cls, 2))
            o.fields = W._obdao_fields((0.0, 0.0, 0.0, 0.01, 0.01, 0.0))
            o.fields.update(has_zone=0, zone=None, norme_len=4 + len(norme), norme=norme, data='SN-1',
                            var_flag=0, adv_var=0, i128=0, var=None, d140=0.0, b198=bytes(0x58), b148=bytes(0x50))
            w = W.MfcWriter()
            W.w_new_bcode(w, o)
            back = MfcObject(MfcClass(cls, 2))
            ar = Archive(bytes(w.buf), 0, vnd.READERS)
            vnd.read_new_bcode(ar, back)
            assert ar.pos == len(w.buf) and back.fields['data'] == 'SN-1'
            out.append(vnd.BARCODES[cls])
        return 'codes-barres TypeEdit V15 relus (' + ', '.join(out) + ')'
    check('Codes-barres TypeEdit V15', t_typeedit_v15_barcode)

    def t_typeedit_braille():
        import struct
        from vectordrive.io import vnd
        from vectordrive.io import vnd_write as W
        from vectordrive.io.mfc import Archive, MfcClass, MfcObject
        hdr = MfcObject(MfcClass('CObBraille', 10))
        hdr.fields = W._obdao_fields((0.0, 0.0, 0.0, 0.02, 0.01, 0.0))
        w = W.MfcWriter()
        W.w_obdao_fin(w, hdr)
        w.u32(0), w.u32(0), w.u32(0), w.cstring('Salle 1'), w.cstring('')
        for _ in range(4):
            w.u32(0)
        w.raw(struct.pack('<I', 5) + bytes(200) + struct.pack('<I', 1) + bytes(44) + struct.pack('<I', 1) + bytes(20))
        for x in (0.01, 0.02, 0.0):
            w.f64(x)
        w.u32(0), w.u32(0), w.u32(0), w.f64(0.0), w.f64(0.0), w.cstring('Salle 1'), w.f64(0.0)
        w.u32(0), w.u32(0), w.u32(0), w.f64(0.0), w.u32(0)
        raw = bytes(w.buf)
        obj = MfcObject(MfcClass('CObBraille', 10))
        ar = Archive(raw, 0, vnd.READERS)
        vnd.read_braille(ar, obj)
        assert ar.pos == len(raw)
        w2 = W.MfcWriter()
        W.w_braille(w2, W.translated_object(obj, 0.005, 0.0))
        back = MfcObject(MfcClass('CObBraille', 10))
        vnd.read_braille(Archive(bytes(w2.buf), 0, vnd.READERS), back)
        assert abs(vnd.braille_field(back, 'pos_x') - 0.015) < 1e-12
        return f"braille TypeEdit « {vnd.braille_text(back)} » relu et déplacé"
    check('Braille TypeEdit', t_typeedit_braille)

    def t_theme_typeedit13():
        from vectordrive.ui import themes as T
        t = T.BUILTIN['typeedit13']
        assert (t.colors['ribbon'], t.colors['caption'], t.canvas['plate_edge']) == ('#bcc7d8', '#5a83b7', '#000000')
        assert T.get('typeedit_classique').key == 'typeedit13'
        assert (len(T.BUILTIN), len(T.LIGHT_KEYS)) == (30, 5)
        return 'thème « TypeEdit 13 » (ruban #bcc7d8, bandeaux #5a83b7)'
    check('Thème TypeEdit 13', t_theme_typeedit13)

    def t_vnd_v13():
        from vectordrive.core import geom
        from vectordrive.core.document import Document, Shape
        from vectordrive.io import vnd
        from vectordrive.io import vnd_write as W
        from vectordrive.io.mfc import MfcClass, MfcObject
        d = Document()
        d.add(Shape(path=geom.Path([geom.rect(0, 0, 40, 20)])))
        data, rep = W.write_document(d)
        bad = W.v13_issues(vnd.parse(data)[0])
        assert not bad, bad
        assert W.v13_issues(MfcObject(MfcClass('CTravail', 11)))       # VND de la V15 : refusé
        return f"VND écrit lisible par TypeEdit 13 (CTravail {vnd.parse(data)[0].cls.schema}, CObDao 9)"
    check('VND compatible TypeEdit 13', t_vnd_v13)

    def t_typeedit_variables():
        import struct
        from vectordrive.io import vnd
        from vectordrive.io.mfc import Archive, MfcClass, MfcObject
        raw = (struct.pack('<III', 1, 2, 4) + 'VAR1'.encode('utf-16-le') + b'\0\0'
               + struct.pack('<I', 0) + struct.pack('<I', 0))
        o = MfcObject(MfcClass('CVariable', 2))
        ar = Archive(raw, 0, vnd.READERS)
        vnd._read_variable(ar, o)
        assert ar.pos == len(raw) and o.fields['variables'] == [['VAR1', '']]
        return 'variables du document lues (VAR1)'
    check('Variables TypeEdit', t_typeedit_variables)

    def t_open_folder():
        import tempfile
        from unittest import mock
        from vectordrive.ui import reveal as RV
        tmp = pathlib.Path(tempfile.mkdtemp())
        f = tmp / 'programme.nc'
        f.write_text('M30')
        with mock.patch.object(RV.subprocess, 'Popen') as po, \
                mock.patch.object(RV.QDesktopServices, 'openUrl', return_value=True) as ou:
            assert RV.reveal(f) and RV.reveal(tmp)
        assert po.called or ou.called
        from PySide6.QtWidgets import QApplication
        from vectordrive.ui.main_window import MainWindow
        QApplication.instance() or QApplication([])
        w = MainWindow()
        try:
            assert not w.cam_panel.folder_btn.isEnabled() and not w.cam_panel.open_program_folder()
        finally:
            w.modified = False
            w.close()
        return 'bouton dossier du panneau FAO, « Ouvrir le dossier » après post-traitement'
    check('Ouvrir le dossier du programme', t_open_folder)

    def t_live_texts_vnd():
        import struct
        from vectordrive.io import paragraph as PG
        r = PG.char_record(65, 0, 0.005, 1.0)
        assert len(r) == 204 and struct.unpack_from('<d', r, 56)[0] == -0.4
        return 'attributs de caractère TypeEdit conformes à la V13 (textes modifiables)'
    check('Textes TypeEdit modifiables', t_live_texts_vnd)

    def t_model3d():
        import numpy as np
        from vectordrive.io import model3d as M
        from vectordrive.ui import view3d as V3
        V = np.array([[x, y, z] for x in (0, 10) for y in (0, 10) for z in (0, 10)], float)
        F = [(0, 1, 3), (0, 3, 2), (4, 6, 7), (4, 7, 5), (0, 4, 5), (0, 5, 1),
             (2, 3, 7), (2, 7, 6), (0, 2, 6), (0, 6, 4), (1, 5, 7), (1, 7, 3)]
        tris = V[np.array(F)]
        m = M.Model3D(tris.astype(np.float32), np.tile(np.array(M.ALU, np.float32), (12, 1)), M.sharp_edges(tris))
        tri, edge = V3.model_arrays(m)
        assert tri.shape == (36, 9) and edge.shape == (24, 9)
        return 'modèle 3D : ' + m.summary()
    check('Mode 3D : modèle du fichier', t_model3d)

    def t_fast_conics():
        import math
        from vectordrive.core.geom import Conic
        from vectordrive.ui.canvas import conic_cubics_fast
        r, th = 50.0, math.radians(120)
        t = r / math.cos(th / 2)
        c = Conic((r, 0.0), (t * math.cos(th / 2), t * math.sin(th / 2)), (r * math.cos(th), r * math.sin(th)),
                  math.cos(th / 2))
        worst = 0.0
        for p0, p1, p2, p3 in conic_cubics_fast(c, 1e-3):
            for k in range(1, 20):
                u = k / 20
                x = (1 - u) ** 3 * p0[0] + 3 * (1 - u) ** 2 * u * p1[0] + 3 * (1 - u) * u * u * p2[0] + u ** 3 * p3[0]
                y = (1 - u) ** 3 * p0[1] + 3 * (1 - u) ** 2 * u * p1[1] + 3 * (1 - u) * u * u * p2[1] + u ** 3 * p3[1]
                worst = max(worst, abs(math.hypot(x, y) - r))
        assert worst < 1e-3, worst
        return f'arcs en cubiques pour l\'affichage : écart {worst * 1000:.2f} µm'
    check('Affichage rapide des arcs', t_fast_conics)

    def t_typeedit_layout():
        from vectordrive.ui import typeedit_layout as TL
        script = ('set c = configProduct.AddCategoryFromID(307)\nset p = c.AddPanelFromID(506)\n'
                  'cmd = "ID_COMPO_SHOWPALSHAPE"\nset b = p.AddButton(cmd,true,false)\nb.SetContextID(1001)\n'
                  'set k = configProduct.AddContextCategoryFromID(316,-1,1001)\nset q = k.AddPanelFromID(316)\n'
                  'cmd = "ID_COMPO_RECTANGLE"\nq.AddButton cmd,true,false\n')
        lay = TL.parse(script, {307: 'TypeEdit', 316: 'Formes', 506: 'Mode'})
        assert [t.title for t in lay.tabs] == ['TypeEdit'] and lay.modes == {'ID_COMPO_SHOWPALSHAPE': '1001'}
        inst = TL.installed(13)
        return 'disposition TypeEdit 13 : ' + (f'{len(inst.tabs)} onglets lus sur le poste' if inst else
                                              'TypeEdit 13 absent du poste (lecture du script vérifiée)')
    check('Disposition du ruban TypeEdit 13', t_typeedit_layout)

    def t_quick_access():
        from vectordrive.ui import typeedit_layout as TL
        cmds, top = TL.quick_access('[QAT]\nStateOnTop=1\nNbCommand=2\nQAT_CMD_0=ID_FILE_NEW\nQAT_CMD_1=ID_EDIT_UNDO\n'
                                    'QAT_CMD_2=ID_FILE_SAVE\n')
        assert cmds == ['ID_FILE_NEW', 'ID_EDIT_UNDO'] and top
        inst = TL.installed(13)
        n = len(inst.quick) if inst else 0
        return f'barre d\'accès rapide de TypeEdit 13 : {n} commande(s) lues sur le poste'
    check('Accès rapide TypeEdit 13', t_quick_access)

    def t_live_multiline():
        from vectordrive.core import fonts as F
        from vectordrive.core import text as TX
        from vectordrive.core.document import Text
        from vectordrive.io import paragraph as PG
        if not F.find_font('Arial'):
            return 'Arial absente : vérification sautée'
        t = Text(text='Deux\nlignes', font='Arial', size=5)
        t.outline = TX.outline_for(t)
        p = PG.build(t, 0)
        n = len(p.fields['courbe1'].children)
        assert n == 2, n
        return 'texte TypeEdit vivant de 2 lignes : 2 lignes de base'
    check('Textes TypeEdit de plusieurs lignes', t_live_multiline)

    def t_fast_area():
        import math
        from vectordrive.core import geom
        from vectordrive.io import vnd_write as W
        a = W.fast_signed_area(geom.circle((0, 0), 5))
        assert abs(a - math.pi * 25) < 1e-6 and W._contour_type(geom.rect(0, 0, 2, 1).reversed()) == 2
        return f'sens des contours sans aplatir : aire du cercle {a:.6f} mm²'
    check('Enregistrement VND rapide', t_fast_area)

    def t_background_save():
        import json
        from vectordrive.core import geom
        from vectordrive.core.document import Document, Shape
        from vectordrive.io import native
        d = Document()
        d.add(Shape(path=geom.Path([geom.circle((0, 0), 5), geom.rect(0, 0, 2, 1)])))
        D = native.to_dict(d)
        assert native.dumps(D) == json.dumps(D, ensure_ascii=False, separators=(',', ':'))
        s = native.snapshot(d)
        d.layers[0].items.clear()
        assert len(s.layers[0].items) == 1
        c = s.layers[0].items[0].path.contours[0]
        assert c.bbox() is c.bbox()
        return 'copie du dessin, JSON par objets identique, encombrements en cache'
    check('Sauvegarde de récupération en tâche de fond', t_background_save)

    def t_point_mode_te13():
        from vectordrive.core import geom, nodes as N
        from vectordrive.core.geom import Contour, Line
        r = N.refine(geom.rect(0, 0, 10, 4))
        assert len(r.segments) == 8
        arc = Contour(geom.arc_conics((0, 0), 5, 5, 0, 90), False)
        c = Contour([Line((5, -3), (5, 0))] + arc.segments + [Line((0, 5), (-3, 5))], False)
        apex = N.to_angle(c, 1, 2).segments[1].end
        assert abs(apex[0] - 5) < 1e-9 and abs(apex[1] - 5) < 1e-9
        assert len(N.to_segment(c, 0, 3).segments) == 1
        return 'affiner, en segment, en angle (sommet à l\'intersection des tangentes)'
    check('Mode Point de TypeEdit 13', t_point_mode_te13)

    def t_axis_align():
        from vectordrive.core.geom import Affine
        from vectordrive.ui.tools import AxisAlignTool as T
        a = T.angle((2, 1), (3, 9), 'v')
        x, _y = Affine.rotation(a, (2, 1)).apply((3, 9))
        assert abs(x - 2) < 1e-9 and abs(a) <= 90
        return f'redresser : rotation de {a:.3f}° autour du pivot'
    check('Aligner suivant un axe (redresser)', t_axis_align)

    def t_contour_move():
        from vectordrive.ui.shortcuts import TE_ACTIONS
        from vectordrive.ui.tools import ContourMoveTool
        assert TE_ACTIONS['ID_CONTOUR_MOVE'] == 'tool_contour_move'
        assert TE_ACTIONS['ID_MANIPULER_ZONE_ALIGNER'] == 'align_center'
        assert callable(ContourMoveTool.find)
        return 'déplacer un contour sans décombiner, aligner et centrer'
    check('Déplacer un contour, aligner et centrer', t_contour_move)

    def t_projections():
        from vectordrive.core import geom, nodes as N
        sq = geom.rect(0, 0, 10, 10)
        assert N.project_point(sq, (4, 2), 'v') == (4, 0)
        q = N.project_point(geom.circle((0, 0), 5), (3, 9), 'v')
        assert q[0] == 3 and abs(q[1] - 4) < 1e-9
        assert N.project_on_guide('h', 20, (3, 5), 'h') is None
        return 'verticale, horizontale, orthogonale sur guide ou contour'
    check('Projections de points (Mode Point)', t_projections)

    def t_crossing_and_circles():
        from vectordrive.core import geom
        from vectordrive.core.document import Shape
        from vectordrive.io import dxf
        from vectordrive.ui.canvas import touches_rect
        ring = Shape(path=geom.Path([geom.circle((0, 0), 10)]))
        assert touches_rect(ring, (9, -1, 12, 1)) and not touches_rect(ring, (-2, -2, 2, 2))
        (cx, cy), r = dxf.full_circle(geom.circle((3, 4), 1.65))
        assert abs(r - 1.65) < 1e-9
        return 'sélection des objets touchés ; cercles en CIRCLE dans les DXF'
    check('Sélection par contact, cercles DXF', t_crossing_and_circles)

    def t_ribbon_after():
        from PySide6.QtGui import QAction
        from PySide6.QtWidgets import QToolButton
        from vectordrive.ui.ribbon import RibbonGroup
        g = RibbonGroup('essai')
        a, b, c = QAction('BAT'), QAction('Imprimer'), QAction('Devis')
        g.add(a)
        g.add(b)
        g.insert_after(a, c)
        acts = [g._row.itemAt(i).widget().defaultAction() for i in range(g._row.count())
                if isinstance(g._row.itemAt(i).widget(), QToolButton)]
        assert acts == [a, c, b]
        return 'bouton de plugin juste après un bouton du ruban (Devis après BAT)'
    check('Bouton de plugin à côté d\'un bouton du ruban', t_ribbon_after)

    def t_commands_open():
        from PySide6.QtWidgets import QApplication, QDialog
        from vectordrive.ui.main_window import MainWindow
        QApplication.instance() or QApplication([])
        shown = []
        orig = QDialog.exec
        QDialog.exec = lambda d: (shown.append(type(d).__name__), 0)[1]
        try:
            w = MainWindow()
            w.A['options'].trigger()                       # recevait False comme exec_dialog
            w.modified = False
            w.close()
        finally:
            QDialog.exec = orig
        assert shown, "Options ne s'ouvre pas"
        return f'commande Options : {shown[0]} ouvert'
    check('Commandes qui ouvrent leur fenêtre', t_commands_open)

    def t_selection_mode():
        from vectordrive.cam import model, strategies as S
        d = Document()
        a = Shape(path=geom.Path([geom.rect(0, 0, 10, 10)]), tool=0)
        b = Shape(path=geom.Path([geom.rect(20, 0, 10, 10)]), tool=0)
        d.add(a)
        d.add(b)
        s = model.CamSetup()
        t = model.CamTool(name='F1', diameter=1, feed=600, number=1)
        s.tools = [t]
        s.operations = [model.Operation(kind='gravure', tool_id=t.id, sources=[0], depth=0.1)]
        full, part = S.compute_all(d, s)[0].lengths()[0], S.compute_all(d, s, only=[a.id])[0].lengths()[0]
        assert part < full * 0.75 and S._ONLY.get() is None
        return f'parcours sur la sélection : {part:.0f} mm contre {full:.0f} mm pour la couleur'
    check('Calcul des parcours sur la sélection', t_selection_mode)

    def t_my_tools_folders():
        from vectordrive.cam import model, toollib as L
        tools = [model.CamTool(name='a'), model.CamTool(name='b', folder='Datron')]
        assert L.folders(tools) == ['Mes outils', 'Datron']
        assert L.unique_folder('Datron', tools) == 'Datron (2)'
        L.merge_folders(tools, 'Datron', 'Mes outils')
        assert L.folders(tools) == ['Mes outils']
        return 'Mes outils en dossiers : un import = un dossier, fusion, renommage'
    check('Mes outils en dossiers', t_my_tools_folders)

    def t_ttpl():
        from vectordrive.cam import ttpl
        xml = ('<gangdrill.BdOTool type="0" num="7" diameter="3.175" angle="0.2617993877991494" truncation="0.2" '
               'maxDepth="0.15" passDepth="0.05" snominal="24000" fnominal="0.8" fplg="0.3" toolName="Conique">'
               '<mapparam.CMapParam MODE_GRAVURE="1"></mapparam.CMapParam></gangdrill.BdOTool>')
        tpl = ttpl.parse(xml, 'essai')
        back = ttpl.parse(ttpl.to_xml(tpl).split('?>', 1)[1].strip(), 'retour')
        t = back['tools'][0]
        assert t['kind'] == 'conique' and abs(t['angle'] - 30) < 1e-6 and back['operations'][0]['depth'] == 0.15
        return f'modèle de parcours TypeEdit : outil {t["name"]}, {len(ttpl.installed())} sur le poste'
    check('Modèles de parcours TypeEdit (.ttpl)', t_ttpl)

    def t_ramps():
        import math
        from vectordrive.cam import model, strategies as S
        em = S.Emitter(model.Operation(), model.CamTool())
        S.cut_chain(em, [(0, 0), (2, 0)], False, [-0.5], ramp=True, ramp_angle=5)
        prev, worst = None, 0.0
        for m in em.moves:
            if prev is not None and m.kind == 'feed' and m.z < prev[2] - 1e-12:
                worst = max(worst, (prev[2] - m.z) / max(1e-12, math.dist(prev[:2], (m.x, m.y))))
            prev = (m.x, m.y, m.z)
        assert worst <= math.tan(math.radians(5)) + 1e-9
        return f'rampe en zigzag sur un trait de 2 mm : pente {math.degrees(math.atan(worst)):.1f}°'
    check('Liaisons en rampe', t_ramps)

    def t_holes():
        import math
        from vectordrive.cam import model, strategies as S
        d = Document()
        d.plate = None
        d.add(Shape(path=geom.Path([geom.circle((0, 0), 1.65)]), tool=0))
        s = model.CamSetup()
        t = model.CamTool(diameter=2.5, cut_length=8)
        s.tools = [t]
        op = model.Operation(kind='taraudage', tool_id=t.id, depth=6, thread='M4')
        s.operations = [op]
        tp = S.compute(d, s, op)
        r = max(math.hypot(m.x, m.y) for m in tp.moves if m.kind == 'feed')
        assert abs(r - 0.75) < 1e-6 and tp.cycles and tp.cycles[0]['pitch'] == 0.7
        return f'taraudage M4 : hélice de rayon {r:.2f} mm, pas 0,7 ; cycle noté pour la machine'
    check('Taraudage et trous (opérations NeoDrive)', t_holes)

    def t_probes():
        from vectordrive.cam import instructions as I
        p = I.from_selection('palpage_coin', {'corner': 'Arrière droit'}, (0, 0, 120, 40))
        assert (p['x'], p['y']) == (120, 40), p
        p = I.from_selection('palpage_rectangle', {}, (0, 0, 120, 40))
        assert (p['x'], p['y'], p['width_x'], p['width_y']) == (60, 20, 120, 40), p
        return 'palpages coin, arête, rectangle, symétrie, U : position reprise de la sélection'
    check('Palpages (instructions NeoDrive)', t_probes)

    def t_wobble():
        from vectordrive.cam import wobble as W
        from vectordrive.cam.model import Move
        moves = [Move('rapid', 0, 0, 1), Move('plunge', 0, 0, 0), Move('feed', 10, 0, 0), Move('rapid', 10, 0, 1)]
        out = W.apply_moves(moves, 0.1, 0.1, 'circle')
        ys = [m.y for m in out if m.kind == 'feed']
        assert len(ys) > 1000 and abs(max(ys) - 0.1) < 1e-3 and (out[-2].x, out[-2].y) == (10, 0)
        assert W.check(80000, 0.1, 0.1)[0][0] == 'bloquant'
        return f'oscillation en cercle : {len(ys)} points sur 10 mm ; 80 m/min au pas de 0,1 : refusé'
    check('Oscillation du faisceau laser', t_wobble)

    def t_coupon():
        from vectordrive.cam import coupon as CP, model, strategies as S
        t = model.CamTool(name='Laser', kind='laser', diameter=0.05, power=60, frequency=30, feed=2000)
        c = CP.build(CP.Spec(x_count=3, y_count=2, title=False), t)
        d = Document()
        d.plate = None
        d.add(c.group)
        s = model.CamSetup()
        s.tools, s.operations = c.tools, c.operations
        tps = S.compute_all(d, s)
        assert c.cells == 6 and len(tps) == 7 and all(tp.moves for tp in tps[:6]), (c.cells, len(tps))
        return f'coupon 3 × 2 : {len(c.tools)} outils, {len(c.operations)} opérations, cases calculées'
    check('Coupon d\'essai laser', t_coupon)

    def t_marquetry():
        from vectordrive.core import marquetry as MQ
        sq = Shape(path=geom.Path([geom.rect(0, 0, 10, 10)]))
        f, m = MQ.forms([sq], MQ.MarquetrySpec(corner_radius=1.0, female_offset=0.1, male_offset=-0.1))
        fb, mb = f[0].bbox(), m[0].bbox()
        assert abs((fb[2] - fb[0]) - 10.2) < 1e-3 and abs((mb[2] - mb[0]) - 9.8) < 1e-3, (fb, mb)
        return 'carré de 10 mm : femelle 10,2, mâle 9,8, angles arrondis'
    check('Marqueterie', t_marquetry)

    def t_states():
        from vectordrive.core import variables as V
        from vectordrive.core.document import Text
        t = Text(text='N° |N|', font='Police absente')
        groups, lay = V.produce([t], V.VarTable(['N'], [['1'], ['2'], ['3']]), (0, 0, 100, 50))
        texts = [g.children[0].text for g in groups]
        assert texts == ['N° 1', 'N° 2', 'N° 3'] and t.text == 'N° |N|', texts
        return f'3 états produits, {lay["cols"]} par rangée'
    check('Textes variables : production des états', t_states)
    # vérifications apportées par les plugins (édition d'atelier)
    from vectordrive import plugins
    for pl in plugins.load():
        if pl.error:
            check(f'plugin {pl.name or pl.module}', lambda pl=pl: (_ for _ in ()).throw(RuntimeError(pl.error)))
    for name, fn in plugins.REGISTRY.autotests:
        check(name, fn)
    print(f'{ok} réussi(s), {ko} échec(s)')
    return 1 if ko else 0


def verify(paths, out=None) -> int:
    """--verifier : lit les dessins donnés (dossiers récursifs), rapport à
    l'écran et, avec --out, en CSV ; code de sortie 1 s'il y a des erreurs."""
    from PySide6.QtGui import QGuiApplication
    from vectordrive import plugins
    from vectordrive.io import batch
    QGuiApplication.instance() or QGuiApplication(sys.argv[:1])
    plugins.load()                                      # formats des plugins (programmes machine…)
    rows = batch.check(batch.collect(paths, programs=True))   # dessins et programmes machine
    for r in rows:
        state = 'OK    ' if r['lu'] else 'ERREUR'
        prog = str(r['format']).startswith('programme')
        detail = ((f"{r['objets']} mouvements, {r['contours']} outil(s)" if prog else
                   f"{r['objets']} objets, {r['contours']} contours")
                  + (f" — TypeEdit 13 : {r['typeedit13']}" if r['typeedit13'] else '')
                  + (f" — {r['remarque']}" if r['remarque'] else '')
                  if r['lu'] else r['erreur'])
        print(f"{state} {r['fichier']} ({r['format']}, {r['ms']} ms) : {detail}")
    print(batch.check_summary(rows))
    if out:
        print('rapport :', batch.write_csv(rows, out))
    return 0 if all(r['lu'] for r in rows) else 1


def _report_file(beside_exe: bool):
    import os
    candidates = []
    if beside_exe:
        base = pathlib.Path(sys.executable).parent if getattr(sys, 'frozen', False) else pathlib.Path.cwd()
        candidates.append(base / 'VectorDrive_rapport.txt')
    if sys.platform == 'darwin':                    # comme portable.data_dir()
        local = pathlib.Path.home() / 'Library' / 'Application Support' / 'VectorDrive'
    else:
        local = pathlib.Path(os.environ.get('LOCALAPPDATA') or pathlib.Path.home()) / 'VectorDrive'
    candidates.append(local / ('VectorDrive_rapport.txt' if beside_exe else 'VectorDrive.log'))
    for f in candidates:
        try:
            f.parent.mkdir(parents=True, exist_ok=True)
            return open(f, 'w', encoding='utf-8')
        except OSError:
            continue
    return open(os.devnull, 'w', encoding='utf-8')


def make_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog='VectorDrive')
    ap.add_argument('fichier', nargs='?')
    ap.add_argument('--autotest', action='store_true')
    ap.add_argument('--convert', metavar='ENTREE')
    ap.add_argument('--to', default='dxf')
    ap.add_argument('--out')
    ap.add_argument('--keep', action='store_true',
                    help='conversion : garder un fichier existant (nouveau nom « nom (2).ext »)')
    ap.add_argument('--lang', choices=['fr', 'en'], help="langue de l'interface (sinon réglage F10 ou système)")
    ap.add_argument('--verifier', metavar='DOSSIER', nargs='+',
                    help='lire des dessins ou des dossiers sans rien écrire, rapport (CSV avec --out)')
    ap.add_argument('--lots', nargs='+', metavar='FICHIER',
                    help='ouvrir le traitement par lots avec ces fichiers ou dossiers (clic droit de l\'explorateur)')
    ap.add_argument('--vignettes-serveur', action='store_true', dest='thumb_server',
                    help="serveur des vignettes de l'explorateur Windows (lancé par l'explorateur, sans fenêtre)")
    ap.add_argument('--mcp', action='store_true',
                    help='pont MCP (entrée et sortie standard) vers le serveur local du VectorDrive ouvert, sans '
                         'fenêtre : la commande que lance un client MCP comme Claude Desktop')
    ap.add_argument('--nouvelle-fenetre', action='store_true', dest='new_window',
                    help="une fenêtre à part (sans session), au lieu d'un onglet dans la fenêtre ouverte")
    ap.add_argument('-SCRIPT', '--script', metavar='FICHIER', dest='script',
                    help='lancer ce script de forme dans une nouvelle fenêtre')
    ap.add_argument('-SCPARAM', '--script-param', nargs='*', default=[], dest='script_params', metavar='VALEUR',
                    help='les paramètres du script (GetAppParameter)')
    return ap


def main(argv=None) -> int:
    from vectordrive import winpaths  # noqa: F401 — lecteur verrouillé, réseau perdu : « absent » plutôt qu'une erreur
    args = make_parser().parse_args(argv)
    if args.script:
        args.new_window = True                          # comme TypeEdit : le script dessine dans une fenêtre à lui
    if args.mcp:                                        # sans fenêtre ni journal : la sortie standard est au client
        from vectordrive.agent import stdio
        return stdio.main()
    if args.thumb_server:                               # sans fenêtre ni journal (le journal de l'application reste)
        import os
        if sys.stdout is None:
            sys.stdout = sys.stderr = open(os.devnull, 'w', encoding='utf-8')
        from vectordrive import thumbshell
        return thumbshell.serve()
    if sys.stdout is None:
        # exécutable sans console : autotest / conversion → rapport à côté de
        # l'exe ; sinon (ou dossier protégé, ex. Program Files) → journal
        # dans %LOCALAPPDATA%\VectorDrive
        sys.stdout = sys.stderr = _report_file(args.autotest or bool(args.convert) or bool(args.verifier))
    if args.autotest:
        return autotest()
    if args.verifier:
        return verify(args.verifier, args.out)
    if args.convert:
        return convert(args.convert, args.to, args.out, args.keep)
    from PySide6.QtWidgets import QApplication
    from vectordrive import i18n
    # la langue doit être fixée avant d'importer l'interface
    from vectordrive import portable
    lang = i18n.set_language(args.lang or portable.settings().value('options/langue', '') or None)
    if lang == 'en':
        # nombres avec point décimal dans les champs de saisie
        from PySide6.QtCore import QLocale
        QLocale.setDefault(QLocale(QLocale.Language.English, QLocale.Country.UnitedKingdom))
    from vectordrive.ui.main_window import MainWindow
    from vectordrive import gpu
    gpu.before_qt(str(portable.settings().value(gpu.SETTING, 'auto') or 'auto'))    # rendu logiciel : avant Qt
    app = QApplication(sys.argv[:1])
    app.setApplicationName('VectorDrive')
    app.setOrganizationName('VectorDrive')
    from vectordrive.ui import instance
    starting = None
    if not args.new_window and args.lots:
        # clic droit « Traitement par lots… » : une commande par fichier choisi ;
        # la première lance la fenêtre, les suivantes lui passent leur fichier
        if instance.forward_lots(args.lots):
            return 0
        starting = instance.starting_lock()
        if starting is None and instance.forward_lots(args.lots, wait_s=30):
            return 0
    elif not args.new_window and instance.forward(args.fichier or ''):
        return 0                                         # ouvert dans un onglet de la fenêtre déjà lancée
    i18n.install_qt_translations(app)
    from vectordrive import portable
    from vectordrive.ui.theme import apply_theme
    from vectordrive.ui.themes import DEFAULT_KEY
    try:
        portable.offer_previous()                        # portable neuf à côté du précédent : reprendre ses réglages ?
    except Exception:                                    # noqa: BLE001 — jamais un lancement empêché pour cela
        pass
    st = portable.settings()
    apply_theme(app, str(st.value('vue/theme', DEFAULT_KEY) or DEFAULT_KEY), st)
    from PySide6.QtGui import QIcon
    import vectordrive
    ico = pathlib.Path(vectordrive.__file__).resolve().parent / 'ressources' / 'vectordrive.ico'
    if ico.exists():
        app.setWindowIcon(QIcon(str(ico)))
    if sys.platform == 'win32':
        # icône propre dans la barre des tâches (sinon celle de python.exe)
        import ctypes
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('VectorDrive.VectorDrive')
        except Exception:
            pass
    w = MainWindow()
    from vectordrive.ui.options import value as option
    session_on = not args.new_window and option(st, 'options/session') and w.start_session()
    w.show_at_start(bool(session_on))                    # plein écran d'office, sinon la fenêtre de la dernière fois
    if not args.new_window:
        w._instance_server = instance.serve(w)            # lancements suivants : un onglet ici
    if starting is not None:
        starting.unlock()
    if sys.platform == 'win32':                           # cartes graphiques lues en fond : F10 s'ouvre aussitôt
        import threading
        threading.Thread(target=gpu.adapters, name='cartes', daemon=True).start()
    if sys.platform == 'win32' and getattr(sys, 'frozen', False) and \
            st.value('explorateur/menu', False) in (True, 'true'):
        # menu de l'explorateur posé par l'utilisateur : remis à jour en silence
        # (nouvelle version, nouvelles entrées, programme déplacé)
        from vectordrive import shellmenu
        try:
            if not shellmenu.check()[0]:
                shellmenu.install()
        except OSError:
            pass
    import os
    if os.environ.get('VECTORDRIVE_TEMPS'):
        # mesure : temps jusqu'à la fenêtre prête, puis sortie
        from PySide6.QtCore import QTimer

        def done():
            print(f'fenêtre prête en {time.perf_counter() - _T0:.2f} s', flush=True)
            w.modified = False
            app.quit()
        QTimer.singleShot(0, done)
        return app.exec()
    w.start_autosave()
    if session_on:
        app.processEvents()
        w.restore_session()                              # sans question
    if not args.new_window and not args.script:          # premier lancement après une mise à jour de l'application :
        w.reopen_after_update()                          # les onglets de l'ancienne version, même sans session
    if not args.new_window and not args.script:          # lancement normal : les onglets gardés à la fermeture d'une
        w.reopen_kept()                                  # fenêtre sans session reviennent (sinon : au prochain)
    if args.fichier:
        w.open_path(args.fichier)
    if args.lots:
        w.batch_add(args.lots)
    from PySide6.QtCore import QTimer
    if args.script:
        QTimer.singleShot(0, lambda: w.run_script_file(args.script, args.script_params))
    QTimer.singleShot(500, w.check_recovery)             # dessins d'une version d'avant arrêtée brutalement
    return app.exec()


if __name__ == '__main__':
    import multiprocessing
    multiprocessing.freeze_support()                     # exécutable : processus du traitement par lots
    sys.exit(main())
