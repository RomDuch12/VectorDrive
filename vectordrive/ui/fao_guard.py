"""Les formes à la base d'un parcours calculé (demande du 17/11, 0 h 15) : « Un dessin déplacé ou modifié alors qu'il est
à la base d'un calcul fao doit emettre un warning visuel (par exemple clignotement 2s de son contour user pourra alors
faire ctrlZ ou parametrer bloquer formes, ou pas d'alarme (mode fao de TE) ».

`Guard` suit les formes dont chaque parcours de la liste a été calculé (retenues au premier pas d'annulation qui suit
le calcul : celles que le calcul a lues, pas celles ajoutées depuis dans la même couleur). À chaque pas d'annulation
(`push_undo`, juste avant la modification), il prend leur empreinte, puis la compare une fois la modification faite
(bouton de la souris relâché, aucun calcul en cours) — une seule fois par pas :
- « clignoter » (d'office) : le contour des formes déplacées ou modifiées clignote 2 s sur le dessin, la barre d'état
  rappelle Ctrl+Z ;
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
MODES = ('clignoter', 'bloquer', 'rien')
FLASH_MS = 2000


def mode(settings) -> str:
    """Le réglage (F10 › FAO), défaut d'un plugin compris."""
    if settings is None:
        return 'clignoter'
    try:
        from . import options
        v = options.value(settings, KEY)
    except Exception:
        v = settings.value(KEY, 'clignoter')
    v = str(v or 'clignoter')
    return v if v in MODES else 'clignoter'


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
        #: les dernières formes signalées (essais)
        self.flagged: list = []

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
        return moved

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
