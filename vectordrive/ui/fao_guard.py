"""Les formes à la base d'un parcours calculé (demande du 17/11, 0 h 15) : « Un dessin déplacé ou modifié alors qu'il est
à la base d'un calcul fao doit emettre un warning visuel (par exemple clignotement 2s de son contour user pourra alors
faire ctrlZ ou parametrer bloquer formes, ou pas d'alarme (mode fao de TE) ».

`Guard` suit les formes dont chaque parcours de la liste a été calculé (retenues au premier pas d'annulation qui suit
le calcul : celles que le calcul a lues, pas celles ajoutées depuis dans la même couleur). À chaque pas d'annulation
(`push_undo`, juste avant la modification), il prend leur empreinte, puis la compare une fois la modification faite
(bouton de la souris relâché, aucun calcul en cours) — une seule fois par pas :
- « demander » (d'office ; demande du 18/11 soir : « modifier un dessin qui sert à un parcours -> popup dupliquer dessin
  (pour garder l'utile) ou mettre à jour les parcours concernés ») : les formes clignotent et une fenêtre, qui ne
  bloque rien, propose de dupliquer le dessin (la forme d'origine revient pour le parcours, la forme modifiée devient une
  copie à part), de mettre à jour les parcours concernés (recalculés) ou de laisser ; « Ne plus demander » passe au
  clignotement ;
- « clignoter » : le contour des formes déplacées ou modifiées clignote 2 s sur le dessin, la barre d'état rappelle
  Ctrl+Z ;
- « bloquer » : la modification est défaite aussitôt (et ne se refait pas par Ctrl+Y), les formes clignotent ;
- « rien » : aucune alarme, comme le mode FAO de TypeEdit.
Un objet supprimé ne clignote pas (les parcours le disent déjà) ; défaire, refaire, la date du jour posée par le calcul,
un autre dessin ne déclenchent rien.
"""
from __future__ import annotations

from PySide6.QtCore import QObject, Qt, QTimer
from PySide6.QtWidgets import QApplication

from ..i18n import tr

KEY = 'fao/formes_parcours'
MODES = ('demander', 'clignoter', 'bloquer', 'rien')
DEFAULT = 'demander'
FLASH_MS = 2000


def mode(settings) -> str:
    """Le réglage (F10 › FAO), défaut d'un plugin compris."""
    if settings is None:
        return DEFAULT
    try:
        from . import options
        v = options.value(settings, KEY)
    except Exception:
        v = settings.value(KEY, DEFAULT)
    v = str(v or DEFAULT)
    return v if v in MODES else DEFAULT


class Guard(QObject):
    """L'alarme des formes à la base d'un parcours calculé, pour la fenêtre `win`."""

    def __init__(self, win):
        super().__init__(win)
        self.win = win
        #: empreintes {identifiant : empreinte} des formes suivies avant la modification du pas en cours ; None : rien
        #: à comparer (pas encore de pas, ou déjà comparé) ; `top` / `mark` : ce pas et le compteur des pas
        self.before: dict | None = None
        self.top = None
        self.mark = -1
        #: par dessin (`id(doc)` : (référence faible, formes suivies, empreintes)) : les formes suivies par parcours
        #: {op_id : (identités des parcours calculés, identifiants lus par le calcul)} et les empreintes gardées tant
        #: que la géométrie est le même objet {identifiant : (clé, empreinte, tracé)}
        self._docs: dict = {}
        self.watched: dict = {}
        self._cache: dict = {}
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(0)
        self.timer.timeout.connect(self.check)
        #: les dernières formes signalées (essais) ; la fenêtre « demander » ouverte, s'il y en a une
        self.flagged: list = []
        self.box = None

    # --- formes suivies ---------------------------------------------------------------------------------------------
    def _watch(self) -> set:
        """Identifiants des formes à la base des parcours de la liste : pour chaque opération, celles que son calcul a
        lues (retenues à la première occasion après le calcul, d'après le mode du calcul : couleur ou sélection)."""
        import weakref
        cam = getattr(self.win, 'cam_panel', None)
        doc = self.win.canvas.doc
        self._docs = {k: e for k, e in self._docs.items() if e[0]() is not None}
        e = self._docs.get(id(doc))
        if e is None or e[0]() is not doc:               # chaque dessin (onglet) a les siens
            e = self._docs[id(doc)] = (weakref.ref(doc), {}, {})
        self.watched, self._cache = e[1], e[2]
        tps = getattr(cam, 'toolpaths', None) or []
        uids: dict = {}
        for tp in tps:
            if getattr(tp, 'op_id', ''):
                uids.setdefault(tp.op_id, set()).add(getattr(tp, 'uid', ''))
        for k in [k for k in self.watched if k not in uids]:
            del self.watched[k]
        stale = [k for k, u in uids.items() if k not in self.watched or self.watched[k][0] != frozenset(u)]
        if stale:
            from ..cam import strategies as S
            ops = {o.id: o for o in cam.setup().operations}
            how = cam._memo('_only') if hasattr(cam, '_memo') else None
            only = how[1] if isinstance(how, tuple) and len(how) == 2 and how[0] == 'selection' else None
            whole = set(cam._memo('_whole') or ()) if hasattr(cam, '_memo') else set()
            for k in stale:
                op = ops.get(k)
                if op is None or not (op.items or op.sources):
                    ids = set()                          # ni objets ni couleurs (surfaçage du brut…) : rien de lu
                else:                                    # calculée seule (formulaire) : sur tous ses objets
                    ids = {it.id for it in S.source_items(doc, op, only=None if k in whole else only)}
                self.watched[k] = (frozenset(uids[k]), frozenset(ids))
        return set().union(*(ids for _u, ids in self.watched.values())) if self.watched else set()

    def _items(self, ids: set) -> dict:
        from ..core.document import Group
        out = {}

        def walk(items):
            for it in items:
                if it.id in ids:
                    out[it.id] = it
                if isinstance(it, Group):
                    walk(it.children)
        for L in self.win.canvas.doc.layers:
            walk(L.items)
        return out

    def _print(self, it):
        """Empreinte d'une forme : son tracé (ou son contour de texte), sa matrice et son texte (une image, un texte
        sans contour se déplacent aussi). Gardée tant que le tracé est le même objet (jamais modifié en place)."""
        from ..cam import strategies as S
        g = S.item_geometry(it)
        key = (id(g), repr(getattr(it, 'matrix', None)), getattr(it, 'text', None), getattr(it, 'tool', None),
               getattr(it, 'visible', True))           # une autre couleur, masquée : sortie du parcours
        hit = self._cache.get(it.id)
        if hit is not None and hit[0] == key and hit[2] is g:
            return hit[1]
        d = S._digest((g, key[1:], type(it).__name__))
        self._cache[it.id] = (key, d, g)
        return d

    def prints(self, items: dict) -> dict:
        return {k: self._print(it) for k, it in items.items()}

    # --- appelés par la fenêtre ------------------------------------------------------------------------------------
    def before_change(self) -> None:
        """Un pas d'annulation vient d'être posé : l'état des formes suivies avant la modification."""
        try:
            if self.before is not None and self.timer.isActive() and \
                    QApplication.mouseButtons() == Qt.MouseButton.NoButton:
                self.check()                             # le pas d'avant d'abord (commandes enchaînées)
            if mode(self.win.settings) == 'rien':
                self.forget()
                return
            ids = self._watch()
            for k in [k for k in self._cache if k not in ids]:
                del self._cache[k]                       # formes plus suivies : leurs tracés libérés
            new = self.prints(self._items(ids)) if ids else None
            if new is not None and self.before is not None:      # le pas d'avant pas encore comparé : l'état
                new = {**new, **{k: v for k, v in self.before.items() if k in new}}   # le plus ancien
            self.before = new
            win = self.win
            self.top = win._undo[-1] if getattr(win, '_undo', None) else None
            self.mark = getattr(win, '_undo_pushes', 0)
        except Exception:                                # jamais une commande empêchée par l'alarme
            self.forget()

    def changed(self) -> None:
        """Le dessin a changé : comparé une fois la modification finie (souris relâchée, calcul fini)."""
        if self.before:
            self.timer.start()

    def forget(self) -> None:
        """Défaire, refaire, la date du jour, un autre dessin : rien à comparer."""
        self.before = None
        self.top = None
        self.timer.stop()

    def check(self) -> list:
        """Les formes suivies déplacées ou modifiées depuis `before_change` : signalées (clignotent) ou, en mode
        « bloquer », le pas défait. Une seule comparaison par pas. Rend les identifiants signalés."""
        if not self.before:
            return []
        cam = getattr(self.win, 'cam_panel', None)
        if QApplication.mouseButtons() != Qt.MouseButton.NoButton or getattr(cam, '_computing', False) or \
                QApplication.activeModalWidget() is not None or QApplication.overrideCursor() is not None:
            self.timer.start(120)                        # un glissé, un calcul, une boîte ouverte : à la fin seulement
            return []
        was, top, mark = self.before, self.top, self.mark
        self.forget()
        try:
            items = self._items(set(was))
            now = self.prints(items)
        except Exception:
            return []
        moved = [k for k, d in now.items() if k in was and was[k] != d]
        self.flagged = moved
        how = mode(self.win.settings)
        if not moved or how == 'rien':
            return []
        win = self.win
        undo = getattr(win, '_undo', None)
        if how == 'bloquer' and undo and top is not None and undo[-1] is top and \
                getattr(win, '_undo_pushes', 0) == mark:
            redo = list(win._redo)
            win.undo()                                   # la modification défaite…
            win._redo[:] = redo                          # … et pas à refaire par Ctrl+Y
            win._history_changed()
            self.forget()
            back = self._items(set(moved))
            self._flash([back[k] for k in moved if k in back])
            win.statusBar().showMessage(tr('Modification annulée : ces formes servent à un parcours calculé '
                                           '(réglage : F10 › FAO)'), 8000)
            return moved
        self._flash([items[k] for k in moved])
        win.statusBar().showMessage(tr('Forme à la base d’un parcours calculé déplacée ou modifiée : Ctrl+Z pour '
                                       'revenir'), 8000)
        if how == 'demander':
            self.ask(moved, top, mark, was)
        return moved

    # --- « demander » : dupliquer le dessin ou mettre à jour les parcours -------------------------------------------
    def ask(self, moved: list, top, mark, was=None) -> None:
        """La fenêtre du réglage « demander », qui ne bloque rien et ne prend pas le clavier : Dupliquer le dessin,
        Mettre à jour les parcours, Laisser ; « Ne plus demander » passe au clignotement. `was` : les empreintes
        d'avant la modification."""
        import weakref

        from PySide6.QtWidgets import QCheckBox, QMessageBox
        self.close_box()
        win = self.win
        doc = weakref.ref(win.canvas.doc)
        box = QMessageBox(win)
        box.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)            # fermée : détruite (rien ne s'accumule)
        box.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)    # Ctrl+Z, les flèches, la frappe : au dessin
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle(tr('Forme d’un parcours modifiée'))
        box.setText(tr('{0} forme(s) à la base d’un parcours calculé déplacée(s) ou modifiée(s).').format(len(moved)))
        box.setInformativeText(tr('Dupliquer le dessin : la forme d’origine revient pour le parcours, la forme '
                                  'modifiée devient une copie à part. Mettre à jour : les parcours concernés sont '
                                  'recalculés avec la forme modifiée.'))
        dup = box.addButton(tr('Dupliquer le dessin'), QMessageBox.ButtonRole.ActionRole)
        upd = box.addButton(tr('Mettre à jour les parcours'), QMessageBox.ButtonRole.AcceptRole)
        box.addButton(tr('Laisser'), QMessageBox.ButtonRole.RejectRole)
        never = QCheckBox(tr('Ne plus demander (le contour clignote seulement ; F10 › FAO)'))
        box.setCheckBox(never)
        box.setWindowModality(Qt.WindowModality.NonModal)
        state = {'done': False}

        def done(_result=None):
            if state['done']:
                return
            state['done'] = True
            if self.box is box:
                self.box = None
            button = box.clickedButton()                 # la croix de la fenêtre : aucun
            if never.isChecked():
                win.settings.setValue(KEY, 'clignoter')
            if button not in (dup, upd):
                return
            if doc() is not win.canvas.doc:              # un autre onglet entre-temps
                win.statusBar().showMessage(tr('Ce dessin n’est plus celui affiché : rien n’est fait'), 6000)
            elif button is dup:
                self.duplicate(moved, top, mark, was)
            else:
                self.update_paths(moved)
        box.finished.connect(done)                      # un bouton ou la croix
        self.box = box
        box.show()
        canvas = getattr(win, 'canvas', None)
        if canvas is not None:
            canvas.setFocus()

    def close_box(self) -> None:
        if self.box is not None:
            box, self.box = self.box, None
            try:
                box.close()
            except RuntimeError:                         # déjà détruite
                pass

    def _where(self, iid):
        """(liste qui le contient, rang, liste du calque, rang au calque de l'objet de premier niveau qui le contient)
        de l'objet d'identifiant `iid` dans le dessin ; None : absent."""
        from ..core.document import Group

        def walk(items):
            for i, it in enumerate(items):
                if it.id == iid:
                    return items, i
                if isinstance(it, Group):
                    got = walk(it.children)
                    if got is not None:
                        return got
            return None
        for L in self.win.canvas.doc.layers:
            for j, it in enumerate(L.items):
                got = walk([it])
                if got is not None:
                    if got[0][0] is it:                  # au premier niveau du calque
                        return L.items, j, L.items, j
                    return got[0], got[1], L.items, j
        return None

    def duplicate(self, moved: list, top, mark, was=None) -> bool:
        """Dupliquer le dessin : les formes d'origine reviennent à leur place (le parcours les garde, groupes
        compris) ; chaque forme modifiée devient une copie à part (un autre identifiant), juste au-dessus — hors du
        groupe s'il y en a un. Les opérations par couleur qui lisaient ces formes passent à leurs objets (la copie,
        de la même couleur, n'y entre pas). Un pas d'annulation (FAO comprise). Seulement si rien n'a changé depuis la
        modification et que le pas défait est bien celui de l'alarme (sinon un message)."""
        from ..core.document import new_id, struct_copy
        win = self.win
        undo = getattr(win, '_undo', None)
        refused = tr('Le dessin a changé depuis : Ctrl+Z pour revenir à la forme du parcours')
        if not undo or top is None or undo[-1] is not top or getattr(win, '_undo_pushes', 0) != mark:
            win.statusBar().showMessage(refused, 8000)
            return False
        redo = list(win._redo)
        win.undo()                                       # l'état d'avant : les formes d'origine
        items = self._items(set(moved))
        same = was is None or all(was.get(k) == d for k, d in self.prints(items).items() if k in was)
        orig = {k: struct_copy(it) for k, it in items.items()}
        win.redo()                                       # la modification, de nouveau
        win._redo[:] = redo
        if not same:                                     # plusieurs pas comparés d'un coup : pas celui-ci seul
            self.forget()
            win._history_changed()
            win.statusBar().showMessage(refused, 8000)
            return False
        cam = getattr(win, 'cam_panel', None)
        self._watch()
        hit = set(moved)
        by_colour = [o for o in (cam.setup().operations if cam is not None else [])
                     if not o.items and o.sources and o.id in self.watched and hit & set(self.watched[o.id][1])]
        win.push_undo(tr('Dupliquer le dessin'), with_cam=bool(by_colour))
        n = 0
        for k in moved:
            got = self._where(k)
            if got is None or k not in orig:
                continue
            box, i, layer, j = got
            copy = box[i]
            copy.id = new_id()                           # la forme modifiée : une copie à part
            box[i] = orig[k]                             # la forme d'origine, à sa place
            if box is layer:
                layer.insert(i + 1, copy)                # la copie juste au-dessus
            else:
                layer.insert(j + 1, copy)                # hors du groupe : au-dessus de lui
            n += 1
        if by_colour:
            s = cam.setup()
            pin = {o.id: sorted(self.watched[o.id][1]) for o in by_colour}
            for o in s.operations:
                if o.id in pin:
                    o.items = list(pin[o.id])
            cam.save(s)
        self.forget()                                    # rien à comparer : les formes suivies sont celles d'avant
        win.canvas.invalidate()
        win._on_doc_changed()
        self.forget()
        win._history_changed()
        msg = tr('{0} forme(s) dupliquée(s) : l’original garde le parcours').format(n)
        if by_colour:
            msg += ' — ' + tr('{0} opération(s) par couleur passée(s) à leurs objets').format(len(by_colour))
        win.statusBar().showMessage(msg, 8000)
        return True

    def update_paths(self, moved: list) -> int:
        """Mettre à jour les parcours : ceux dont le calcul a lu une forme de `moved`, recalculés (sur tous leurs
        objets ; ceux calculés sur une sélection sont laissés, avec un mot). Rend leur nombre."""
        win = self.win
        cam = getattr(win, 'cam_panel', None)
        if cam is None:
            return 0
        self._watch()
        hit = set(moved)
        ops = [o for o in cam.setup().operations if o.id in self.watched and hit & set(self.watched[o.id][1])]
        how = cam._memo('_only') if hasattr(cam, '_memo') else None
        only = isinstance(how, tuple) and len(how) == 2 and how[0] == 'selection'
        whole = set(cam._memo('_whole') or ()) if hasattr(cam, '_memo') else set()
        part = [o for o in ops if only and o.id not in whole]
        n = 0
        for op in ops:
            if op in part:
                continue
            if cam.compute_op(op) is None:               # annulé : les autres non plus
                break
            n += 1
        msg = tr('{0} parcours recalculé(s)').format(n)
        if part:
            msg += ' — ' + tr('{0} calculé(s) sur une sélection : à recalculer dans la FAO').format(len(part))
        win.statusBar().showMessage(msg, 8000)
        return n

    def _flash(self, items) -> None:
        from ..cam import strategies as S
        from ..core import geom
        flash = getattr(self.win.canvas, 'flash', None)
        if not callable(flash):
            return
        paths = []
        many = len(items) > 300                          # beaucoup de formes : leurs cadres (peinture légère)
        for it in items:
            g = None if many else S.item_geometry(it)
            if g is None:                                # une image, un texte sans contour : leur cadre
                try:
                    b = it.bbox()
                    g = geom.Path([geom.rect(b[0], b[1], b[2] - b[0], b[3] - b[1])]) if b else None
                except Exception:
                    g = None
            paths.append(g)
        try:
            flash(paths, FLASH_MS)
        except Exception:                                # l'alarme ne casse jamais une commande
            pass
