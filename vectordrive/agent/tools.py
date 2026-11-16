"""Les outils qu'un assistant (Claude, par le protocole MCP) peut appeler sur le dessin ouvert dans VectorDrive
(demande du 15/11 : « Possibilité de connecter un agent claude ou chatgpt pour créer des dessins 2d et 3d ? », puis
« queue serveur MCP ») : lire le dessin, ajouter des formes et du texte, déplacer, tourner, mettre à l'échelle,
supprimer, réunir ou soustraire, sélectionner, prendre une capture, annuler.

- Millimètres ; X vers la droite, Y vers le haut — comme le dessin.
- Chaque outil qui change le dessin fait UN pas d'annulation : Ctrl+Z le défait, comme une commande de la fenêtre.
- Rien n'est écrit sur le disque, rien n'est lu en dehors du dessin ouvert.
- Les noms et les descriptions des outils sont en anglais : ils sont lus par le modèle.

    outils = ToolSet(fenetre)
    outils.specs()                                  # pour `tools/list`
    outils.call('add_rectangle', {'x': 0, 'y': 0, 'width': 40, 'height': 20})
"""
from __future__ import annotations

from ..i18n import tr
from .protocol import ToolError, text_content

#: au plus tant d'objets listés ; de points et de contours rendus pour un objet ; de points donnés à une polyligne
MAX_LISTED = 500
MAX_POINTS = 2000
MAX_CONTOURS = 200
MAX_GIVEN = 20000
#: une cote ou une position au-delà (mm) est refusée : rien de tel ne se grave, et un nombre infini casse le dessin
LIMIT = 1.0e6

NUM = {'type': 'number'}
IDS = {'type': 'array', 'items': {'type': 'string'}, 'minItems': 1,
       'description': 'Object ids, as returned by list_objects or by the add_* tools.'}


def _schema(props: dict, required=()) -> dict:
    return {'type': 'object', 'properties': props, 'required': list(required), 'additionalProperties': False}


def _number(v, what: str) -> float:
    """`v` en nombre fini et raisonnable ; ni booléen, ni chaîne."""
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise ToolError(f'{what} must be a number')
    try:
        v = float(v)
    except OverflowError:
        v = float('inf')
    if v != v or abs(v) > LIMIT:
        raise ToolError(f'{what} must be a finite number between -{LIMIT:g} and {LIMIT:g}')
    return v


def _num(args: dict, key: str, default=None, *, positive: bool = False) -> float:
    v = _number(args.get(key, default), f'"{key}"')
    if positive and v <= 0:
        raise ToolError(f'"{key}" must be greater than 0')
    return v


def _int(args: dict, key: str, default: int, lo: int, hi: int) -> int:
    v = args.get(key, default)
    if isinstance(v, bool) or not isinstance(v, int) or not lo <= v <= hi:
        raise ToolError(f'"{key}" must be an integer from {lo} to {hi}')
    return v


def _thin(points: list, keep: int) -> list:
    """Au plus `keep` points (2 au moins), pris régulièrement, le premier et le dernier gardés."""
    keep = max(2, keep)
    if len(points) <= keep:
        return list(points)
    last = len(points) - 1
    return [points[round(i * last / (keep - 1))] for i in range(keep)]


def _box(bb) -> list | None:
    return [round(float(v), 3) for v in bb] if bb else None


class ToolSet:
    """Les outils, sur la fenêtre `win`. `run(fonction)` exécute une fonction dans le fil de l'interface et rend son
    résultat (d'office : sur place — le serveur local en donne un qui passe par le fil de l'interface)."""

    def __init__(self, win, run=None):
        self.win = win
        self.run = run or (lambda fn: fn())
        self._tools: dict = {}
        self._declare()

    # --- le registre --------------------------------------------------------------------------------
    def _add(self, name: str, description: str, schema: dict, fn, changes: bool = False) -> None:
        self._tools[name] = (description, schema, fn, changes)

    def specs(self) -> list:
        """Pour `tools/list` ; `readOnlyHint` : l'outil ne change rien (le client peut le laisser passer sans
        demander)."""
        return [{'name': name, 'description': d, 'inputSchema': s, 'annotations': {'readOnlyHint': not c}}
                for name, (d, s, _f, c) in self._tools.items()]

    def names(self) -> list:
        return list(self._tools)

    def call(self, name: str, arguments: dict) -> list:
        """Exécute l'outil `name` ; rend ses contenus. KeyError : outil inconnu ; ToolError : refus dit au modèle."""
        _d, schema, fn, _changes = self._tools[name]
        unknown = set(arguments) - set(schema['properties'])
        if unknown:
            raise ToolError('unknown argument(s): ' + ', '.join(sorted(unknown)))
        missing = [k for k in schema['required'] if k not in arguments]
        if missing:
            raise ToolError('missing argument(s): ' + ', '.join(missing))

        def work():
            self._name, self._stepped = name, False
            try:
                out = fn(arguments)
            except KeyError as ex:                       # pas « outil inconnu » : une erreur de l'outil lui-même
                raise RuntimeError(f'KeyError: {ex}') from ex
            if self._stepped:
                self.win.canvas.invalidate()
                self.win._on_doc_changed()
            return out
        out = self.run(work)
        return out if isinstance(out, list) else [text_content(out)]

    def _step(self) -> None:
        """Le pas d'annulation de l'outil en cours, pris juste avant de changer le dessin : tout est vérifié et
        calculé avant, un refus n'en laisse donc pas."""
        if not self._stepped:
            self.win.push_undo(tr('Assistant : {0}').format(self._name))
            self._stepped = True

    # --- le dessin ------------------------------------------------------------------------------------
    @property
    def doc(self):
        return self.win.canvas.doc

    def _top(self) -> dict:
        """id → (calque, objet) des objets de premier niveau."""
        return {it.id: (L, it) for L in self.doc.layers for it in L.items}

    def _find(self, item_id: str):
        """L'objet de cet identifiant, à tout niveau (un groupe dans un groupe aussi) ; None s'il n'y en a pas."""
        stack = [it for L in self.doc.layers for it in L.items]
        while stack:
            it = stack.pop()
            if it.id == item_id:
                return it
            stack.extend(getattr(it, 'children', ()) or ())
        return None

    def _items(self, ids) -> list:
        if not isinstance(ids, list) or not ids or not all(isinstance(i, str) for i in ids):
            raise ToolError('"ids" must be a non-empty list of object ids')
        top = self._top()
        out = []
        for i in dict.fromkeys(ids):
            if i not in top:
                inside = self._find(i) is not None
                raise ToolError(f'object {i} is inside a group: use the id of its group' if inside
                                else f'no object with id {i}')
            layer, it = top[i]
            out.append((layer, it))
        return out

    def _describe(self, it, layer=None) -> dict:
        from ..core.document import Group, Image, Shape, Text
        kind = ('text' if isinstance(it, Text) else 'group' if isinstance(it, Group) else 'image'
                if isinstance(it, Image) else 'shape' if isinstance(it, Shape) else type(it).__name__.lower())
        layer = layer or self.doc.layer_of(it)
        d = {'id': it.id, 'type': kind, 'layer': layer.name if layer is not None else '', 'tool': int(it.tool),
             'bbox': _box(it.bbox())}
        if it.name:
            d['name'] = it.name
        if isinstance(it, Text):
            d['text'] = it.text
        if isinstance(it, Group):
            d['children'] = len(it.children)
        if it.locked or (layer is not None and layer.locked):
            d['locked'] = True
        if not it.visible or (layer is not None and not layer.visible):
            d['visible'] = False
        return d

    def _put(self, items: list) -> dict:
        """Ajoute `items` au calque actif (à sa couleur), les sélectionne ; rend leurs identifiants."""
        tool = int(getattr(self.win.canvas, 'current_tool_index', 0) or 0)
        layer = self.doc.active_layer
        if layer.locked:
            raise ToolError(f'the active layer "{layer.name}" is locked')
        if any(not it.bbox() for it in items):           # rien à dessiner (points confondus, texte sans contour)
            raise ToolError('this would draw nothing (empty shape)')
        self._step()
        for it in items:
            it.tool = tool
            self.doc.add(it)
        self.win.canvas.select(list(items))
        return {'ids': [it.id for it in items], 'bbox': _box(items[0].bbox()) if len(items) == 1 else None}

    def _replace(self, pairs: list) -> None:
        """[(calque, ancien objet, nouvel objet ou None)] : remplacés à leur place, ou retirés."""
        for layer, old, new in pairs:
            k = next(i for i, it in enumerate(layer.items) if it is old)
            if new is None:
                del layer.items[k]
            else:
                layer.items[k] = new

    def _free(self, pairs: list) -> None:
        locked = [it.id for layer, it in pairs if layer.locked or it.locked]
        if locked:
            raise ToolError('locked object(s) or layer: ' + ', '.join(locked))

    # --- les outils -----------------------------------------------------------------------------------
    def _declare(self) -> None:
        a = self._add
        a('get_document', 'Summary of the open drawing: plate (x, y of its lower-left corner, width, height), '
          'layers, number of objects, bounding box, selected object ids. Units: millimetres, Y up. Call this first.',
          _schema({}), self.get_document)
        a('list_objects', 'List the top-level objects of the drawing (id, type, layer, tool/colour index, bounding '
          'box [x0, y0, x1, y1], text for a text). Optional: only one layer.',
          _schema({'layer': {'type': 'string', 'description': 'Layer name.'},
                   'limit': {'type': 'integer', 'minimum': 1, 'maximum': MAX_LISTED}}), self.list_objects)
        a('get_object', 'Geometry of one object: for a shape, its contours as point lists (curves flattened); for a '
          'text, its string, font, size and position; for a group, its children.',
          _schema({'id': {'type': 'string'}, 'tolerance': NUM,
                   'max_points': {'type': 'integer', 'minimum': 10, 'maximum': MAX_POINTS}}, ['id']), self.get_object)
        a('add_rectangle', 'Add a rectangle; (x, y) is its lower-left corner. Optional corner radius.',
          _schema({'x': NUM, 'y': NUM, 'width': NUM, 'height': NUM, 'radius': NUM}, ['x', 'y', 'width', 'height']),
          self.add_rectangle, True)
        a('add_ellipse', 'Add an ellipse (a circle when rx = ry) centred at (cx, cy); rotation in degrees.',
          _schema({'cx': NUM, 'cy': NUM, 'rx': NUM, 'ry': NUM, 'rotation': NUM}, ['cx', 'cy', 'rx']),
          self.add_ellipse, True)
        a('add_polygon', 'Add a regular polygon centred at (cx, cy), inscribed in a circle of the given radius.',
          _schema({'cx': NUM, 'cy': NUM, 'radius': NUM, 'sides': {'type': 'integer', 'minimum': 3, 'maximum': 360}},
                  ['cx', 'cy', 'radius', 'sides']), self.add_polygon, True)
        a('add_polyline', 'Add a polyline through the points [[x, y], ...]; closed: join the last point to the first.',
          _schema({'points': {'type': 'array', 'minItems': 2, 'items': {'type': 'array', 'items': NUM, 'minItems': 2,
                                                                         'maxItems': 2}},
                   'closed': {'type': 'boolean'}}, ['points']), self.add_polyline, True)
        a('add_text', 'Add an editable text; (x, y) is the start of its baseline, size is the capital height in mm.',
          _schema({'text': {'type': 'string'}, 'x': NUM, 'y': NUM, 'size': NUM, 'font': {'type': 'string'},
                   'align': {'type': 'string', 'enum': ['left', 'center', 'right']}}, ['text', 'x', 'y']),
          self.add_text, True)
        a('move_objects', 'Move objects by (dx, dy).', _schema({'ids': IDS, 'dx': NUM, 'dy': NUM}, ['ids', 'dx', 'dy']),
          self.move_objects, True)
        a('rotate_objects', 'Rotate objects by an angle in degrees (counter-clockwise) about (cx, cy); default: the '
          'centre of their bounding box.', _schema({'ids': IDS, 'angle': NUM, 'cx': NUM, 'cy': NUM}, ['ids', 'angle']),
          self.rotate_objects, True)
        a('scale_objects', 'Scale objects by sx (and sy, default sx) about (cx, cy); default: the centre of their '
          'bounding box.', _schema({'ids': IDS, 'sx': NUM, 'sy': NUM, 'cx': NUM, 'cy': NUM}, ['ids', 'sx']),
          self.scale_objects, True)
        a('delete_objects', 'Delete objects.', _schema({'ids': IDS}, ['ids']), self.delete_objects, True)
        a('boolean', 'Combine shapes: union, intersect, or difference (the first shape minus the others). The '
          'shapes are replaced by the result.',
          _schema({'operation': {'type': 'string', 'enum': ['union', 'intersect', 'difference']}, 'ids': IDS},
                  ['operation', 'ids']), self.boolean, True)
        a('select_objects', 'Select objects in the window (an empty list clears the selection).',
          _schema({'ids': {'type': 'array', 'items': {'type': 'string'}}}, ['ids']), self.select_objects, True)
        a('capture', 'A PNG picture of the drawing as shown in the window.',
          _schema({'width': {'type': 'integer', 'minimum': 64, 'maximum': 2048}}), self.capture)
        a('undo', 'Undo the last change (one step of the undo history of the window).', _schema({}), self.undo, True)

    def get_document(self, _args: dict) -> dict:
        doc = self.doc
        plate = doc.plate
        return {'units': 'mm', 'y_axis': 'up',
                'plate': {'x': round(float(plate.x), 3), 'y': round(float(plate.y), 3),
                          'width': round(float(plate.width), 3), 'height': round(float(plate.height), 3)}
                if plate is not None else None,
                'layers': [{'name': L.name, 'visible': bool(L.visible), 'locked': bool(L.locked),
                            'objects': len(L.items)} for L in doc.layers],
                'active_layer': doc.active_layer.name,
                'objects': sum(len(L.items) for L in doc.layers),
                'bbox': _box(doc.bbox()),
                'selection': [it.id for it in self.win.canvas.selection]}

    def list_objects(self, args: dict) -> dict:
        want = args.get('layer')
        limit = _int(args, 'limit', MAX_LISTED, 1, MAX_LISTED)
        if want is not None and want not in [L.name for L in self.doc.layers]:
            raise ToolError(f'no layer named "{want}"')
        rows = [self._describe(it, L) for L in self.doc.layers if want is None or L.name == want for it in L.items]
        return {'objects': rows[:limit], 'total': len(rows)}

    def get_object(self, args: dict) -> dict:
        from ..core.document import Group, Shape, Text
        it = self._find(str(args['id']))                 # à tout niveau : l'enfant d'un groupe se lit aussi
        if it is None:
            raise ToolError(f'no object with id {args["id"]}')
        tol = _num(args, 'tolerance', 0.05)
        if not 0.001 <= tol <= 10:
            raise ToolError('"tolerance" must be between 0.001 and 10 (mm)')
        budget = _int(args, 'max_points', 500, 10, MAX_POINTS)
        d = self._describe(it)
        if isinstance(it, Shape):
            flat = [(bool(c.closed), c.flatten(tol)) for c in it.path.contours[:MAX_CONTOURS]]
            total = sum(len(pts) for _c, pts in flat)
            d['contours_total'] = len(it.path.contours)
            d['points_total'] = total
            if total > budget or len(it.path.contours) > MAX_CONTOURS:
                # trop de points : chaque contour garde sa part, régulièrement répartie (2 points au moins) — dit
                d['truncated'] = True
                flat = [(c, _thin(pts, len(pts) * budget // max(1, total))) for c, pts in flat]
            d['contours'] = [{'closed': c, 'points': [[round(x, 3), round(y, 3)] for x, y in pts]}
                             for c, pts in flat]
        elif isinstance(it, Text):
            x, y = it.matrix.apply((0.0, 0.0))
            d.update(font=it.font, size=round(float(it.size), 3), align=it.align, x=round(x, 3), y=round(y, 3))
        elif isinstance(it, Group):
            d['children'] = [self._describe(c) for c in it.children[:MAX_LISTED]]
        return d

    def add_rectangle(self, args: dict) -> dict:
        from ..core import geom
        from ..core.document import Shape
        w, h = _num(args, 'width', positive=True), _num(args, 'height', positive=True)
        r = _num(args, 'radius', 0.0)
        if r < 0 or r > min(w, h) / 2 + 1e-9:
            raise ToolError('"radius" must be between 0 and half the smaller side')
        return self._put([Shape(path=geom.Path([geom.rect(_num(args, 'x'), _num(args, 'y'), w, h, r)]))])

    def add_ellipse(self, args: dict) -> dict:
        from ..core import geom
        from ..core.document import Shape
        rx = _num(args, 'rx', positive=True)
        ry = _num(args, 'ry', rx, positive=True)
        c = geom.ellipse((_num(args, 'cx'), _num(args, 'cy')), rx, ry, _num(args, 'rotation', 0.0))
        return self._put([Shape(path=geom.Path([c]))])

    def add_polygon(self, args: dict) -> dict:
        from ..core import geom
        from ..core.document import Shape
        sides = args.get('sides')
        if isinstance(sides, bool) or not isinstance(sides, int) or not 3 <= sides <= 360:
            raise ToolError('"sides" must be an integer from 3 to 360')
        c = geom.polygon((_num(args, 'cx'), _num(args, 'cy')), _num(args, 'radius', positive=True), sides)
        return self._put([Shape(path=geom.Path([c]))])

    def add_polyline(self, args: dict) -> dict:
        from ..core import geom
        from ..core.document import Shape
        pts = args.get('points')
        if not isinstance(pts, list) or not all(isinstance(p, (list, tuple)) and len(p) == 2 for p in pts):
            raise ToolError('"points" must be a list of [x, y] pairs')
        if len(pts) > MAX_GIVEN:
            raise ToolError(f'too many points ({MAX_GIVEN} at most)')
        points = [(_number(p[0], 'each coordinate'), _number(p[1], 'each coordinate')) for p in pts]
        if len(set(points)) < 2:
            raise ToolError('"points" must hold at least two different points')
        return self._put([Shape(path=geom.Path([geom.polyline(points, closed=bool(args.get('closed', False)))]))])

    def add_text(self, args: dict) -> dict:
        from ..core import fonts
        from ..core import text as TX
        from ..core.document import Text
        from ..core.geom import Affine
        text = args.get('text')
        if not isinstance(text, str) or not text.strip() or len(text) > 10000:
            raise ToolError('"text" must be a non-empty string (10000 characters at most)')
        try:
            text.encode('utf-8')
        except UnicodeEncodeError:
            raise ToolError('"text" holds an invalid character (lone surrogate)') from None
        align = args.get('align', 'left')
        if align not in ('left', 'center', 'right'):
            raise ToolError('"align" must be left, center or right')
        font = args.get('font')
        if font is None:                                 # la police d'office des textes (Options › Dessin)
            font = str(self.win.settings.value('texte/police', 'Arial') or 'Arial')
        if not isinstance(font, str) or not font.strip():
            raise ToolError('"font" must be a font family name')
        if not fonts.is_available(font.strip()):
            raise ToolError(f'the font "{font.strip()}" is not installed on this computer')
        it = Text(text=text, font=font.strip(), size=_num(args, 'size', 10.0, positive=True), align=align,
                  matrix=Affine.translation(_num(args, 'x'), _num(args, 'y')))
        it.outline = TX.outline_for(it)                  # comme l'outil Texte : le vrai cadre, tout de suite
        return self._put([it])

    def _transform(self, args: dict, matrix_of) -> dict:
        pairs = self._items(args.get('ids'))
        self._free(pairs)
        boxes = [it.bbox() for _l, it in pairs if it.bbox()]
        if not boxes:
            raise ToolError('these objects have no extent')
        x0, y0 = min(b[0] for b in boxes), min(b[1] for b in boxes)
        x1, y1 = max(b[2] for b in boxes), max(b[3] for b in boxes)
        m = matrix_of(((x0 + x1) / 2, (y0 + y1) / 2))
        new = [it.transformed(m) for _l, it in pairs]
        box = _union(n.bbox() for n in new)
        if box is None or any(v != v or abs(v) > 10 * LIMIT for v in box):
            raise ToolError('the result would be out of bounds')
        self._step()
        self._replace([(layer, it, n) for (layer, it), n in zip(pairs, new)])
        self.win.canvas.select(new)
        return {'ids': [it.id for it in new], 'bbox': _box(box)}

    def move_objects(self, args: dict) -> dict:
        from ..core.geom import Affine
        dx, dy = _num(args, 'dx'), _num(args, 'dy')
        return self._transform(args, lambda _c: Affine.translation(dx, dy))

    def rotate_objects(self, args: dict) -> dict:
        from ..core.geom import Affine
        angle = _num(args, 'angle')
        return self._transform(args, lambda c: Affine.rotation(angle, (_num(args, 'cx', c[0]), _num(args, 'cy', c[1]))))

    def scale_objects(self, args: dict) -> dict:
        from ..core.geom import Affine
        sx = _num(args, 'sx')
        sy = _num(args, 'sy', sx)
        if abs(sx) < 1e-9 or abs(sy) < 1e-9:
            raise ToolError('scale factors must not be 0')

        def matrix(c):
            cx, cy = _num(args, 'cx', c[0]), _num(args, 'cy', c[1])
            return Affine.translation(cx, cy) @ Affine.scaling(sx, sy) @ Affine.translation(-cx, -cy)
        return self._transform(args, matrix)

    def delete_objects(self, args: dict) -> dict:
        pairs = self._items(args.get('ids'))
        self._free(pairs)
        self._step()
        self._replace([(layer, it, None) for layer, it in pairs])
        self.win.canvas.select([])
        return {'deleted': len(pairs)}

    def boolean(self, args: dict) -> dict:
        from ..core import pathops
        from ..core.document import Shape
        op = args.get('operation')
        if op not in ('union', 'intersect', 'difference'):
            raise ToolError('"operation" must be union, intersect or difference')
        pairs = self._items(args.get('ids'))
        self._free(pairs)
        if len(pairs) < 2 or not all(isinstance(it, Shape) for _l, it in pairs):
            raise ToolError('boolean needs at least two shapes (not texts, groups or images)')
        shapes = [it for _l, it in pairs]
        if op == 'union':
            res = pathops.union_all([s.path for s in shapes])
        else:
            res = shapes[0].path
            for s in shapes[1:]:
                res = pathops.boolean(res, s.path, op)
        layer = pairs[0][0]
        new = Shape(path=res, tool=shapes[0].tool) if res else None
        gone = {id(it) for _l, it in pairs}              # la place de la première forme, les autres retirées
        k = 0
        for it in layer.items:
            if it is shapes[0]:
                break
            k += id(it) not in gone
        self._step()
        self._replace([(lay, it, None) for lay, it in pairs])
        if new is not None:
            layer.items.insert(min(k, len(layer.items)), new)
        self.win.canvas.select([new] if new is not None else [])
        return {'ids': [new.id] if new is not None else [], 'bbox': _box(new.bbox()) if new is not None else None,
                'empty': new is None}

    def select_objects(self, args: dict) -> dict:
        ids = args.get('ids')
        if not isinstance(ids, list):
            raise ToolError('"ids" must be a list')
        items = [it for _l, it in self._items(ids)] if ids else []
        self.win.canvas.select(items)
        return {'selected': len(self.win.canvas.selection)}      # un objet gelé n'entre pas dans la sélection

    def capture(self, args: dict) -> list:
        import base64
        from PySide6.QtCore import QBuffer, QIODevice, Qt
        width = _int(args, 'width', 1024, 64, 2048)
        pm = self.win.canvas.grab()
        if pm.isNull():
            raise ToolError('nothing to capture')
        if pm.width() > width:
            pm = pm.scaledToWidth(width, Qt.TransformationMode.SmoothTransformation)
        buf = QBuffer()
        buf.open(QIODevice.OpenModeFlag.WriteOnly)
        pm.save(buf, 'PNG')
        data = base64.b64encode(bytes(buf.data())).decode('ascii')
        return [{'type': 'image', 'data': data, 'mimeType': 'image/png'}]

    def undo(self, _args: dict) -> dict:
        self.win.undo()
        return {'objects': sum(len(L.items) for L in self.doc.layers)}


def _union(boxes):
    boxes = [b for b in boxes if b]
    if not boxes:
        return None
    return (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))
