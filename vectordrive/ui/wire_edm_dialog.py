"""Électroérosion à fil : la fenêtre des chutes à risque, après le calcul (demande du 26/11 : « la signaler et
proposer d'incliner le fil et une attache »).

Après chaque calcul, les parcours d'électroérosion (`cam.wire_edm`) qui signalent des morceaux à risque pour le fil
(moyen ou fort) l'ouvrent une fois, sans bloquer la fenêtre : un paragraphe par morceau (où et quand il se détache,
sa taille, pourquoi il gêne le fil) et, au choix, « Incliner le fil » (la dépouille constante de l'opération réglée à
l'angle proposé) ou « Laisser une attache » (ajoutée aux attaches de l'opération) ; l'opération est alors recalculée.
Les morceaux restent en surbrillance orange sur le dessin, avec le parcours.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea,
                               QVBoxLayout, QWidget)

from ..i18n import tr

#: risques signalés par la fenêtre
RISKY = ('moyen', 'fort')


def risky(tp) -> list:
    """Les morceaux à risque d'un parcours d'électroérosion (aucun pour un autre parcours)."""
    for c in getattr(tp, 'cycles', None) or ():
        if isinstance(c, dict) and c.get('kind') == 'fil_edm':
            return [ch for ch in c.get('chutes') or () if ch.get('risque') in RISKY]
    return []


def announce(panel):
    """La fenêtre pour les parcours du panneau FAO `panel` qui ont des morceaux à risque, une fois par calcul ; rend
    la fenêtre ouverte, ou None."""
    from shiboken6 import isValid
    seen = panel.__dict__.setdefault('_chutes_seen', set())
    new = [tp for tp in panel.toolpaths if tp.uid not in seen and risky(tp)]
    if not new:
        return None
    seen.update(tp.uid for tp in new)
    old = getattr(panel, 'chutes_box', None)
    if old is not None and isValid(old):
        old.close()
    dlg = ChutesDialog(panel, new)
    dlg.show()
    panel.chutes_box = dlg
    return dlg


class ChutesDialog(QDialog):
    """Les morceaux à risque et leurs propositions ; `buttons` : [(proposition, op_id, données, bouton)]."""

    def __init__(self, panel, toolpaths):
        super().__init__(panel.win)
        from ..cam import wire_edm
        self.panel = panel
        self.setWindowTitle(tr('Chutes à risque pour le fil'))
        self.setModal(False)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        lay = QVBoxLayout(self)
        intro = QLabel(tr('Ces morceaux se détachent de la matière pendant la coupe et peuvent coincer ou casser le '
                          'fil. Ils sont en surbrillance orange sur le dessin, avec le parcours.'))
        intro.setWordWrap(True)
        lay.addWidget(intro)
        body = QWidget()
        rows = QVBoxLayout(body)
        self.buttons = []
        for tp in toolpaths:
            for ch in risky(tp):
                frame = QFrame()
                frame.setFrameShape(QFrame.Shape.StyledPanel)
                fl = QVBoxLayout(frame)
                text = QLabel((tp.name + ' — ' if tp.name else '') + wire_edm._chute_text(ch))
                text.setWordWrap(True)
                text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                fl.addWidget(text)
                line = QHBoxLayout()
                t = ch.get('inclinaison')
                if t:
                    msg = tr('Incliner le fil de {0}° à gauche ({1})') if t['angle'] > 0 else \
                        tr('Incliner le fil de {0}° à droite ({1})')
                    b = QPushButton(msg.format(f'{abs(t["angle"]):.2f}', t['code']))
                    b.setToolTip(tr('Dépouille constante de l’opération : les flancs de la pièce seront inclinés') if
                                 t['possible'] else tr('Plus que l’inclinaison la plus forte réglée pour la machine'))
                    b.setEnabled(bool(t['possible']))
                    b.clicked.connect(lambda _c=False, o=tp.op_id, d=t: self.apply('taper', o, d))
                    line.addWidget(b)
                    self.buttons.append(('taper', tp.op_id, t, b))
                s = ch.get('attache_proposee')
                if s:
                    b = QPushButton(tr('Laisser une attache de {0} mm').format(f'{s["longueur"]:g}'))
                    b.setToolTip(tr('Coupée après un arrêt programmé : retenir la chute avant de la couper'))
                    b.clicked.connect(lambda _c=False, o=tp.op_id, d=s: self.apply('tab', o, d))
                    line.addWidget(b)
                    self.buttons.append(('tab', tp.op_id, s, b))
                line.addStretch(1)
                fl.addLayout(line)
                rows.addWidget(frame)
        rows.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(body)
        lay.addWidget(scroll, 1)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        bb.rejected.connect(self.close)
        lay.addWidget(bb)
        self.resize(640, 420)

    def apply(self, what: str, op_id: str, proposal: dict) -> bool:
        """La proposition retenue (`what` : 'taper' ou 'tab') réglée dans l'opération, qui est recalculée."""
        from ..cam import wire_edm
        panel = self.panel
        s = panel.setup()
        op = next((o for o in s.operations if o.id == op_id), None)
        if op is None:
            return False
        (wire_edm.apply_taper if what == 'taper' else wire_edm.apply_tab)(op, proposal)
        panel.save(s)
        self.close()
        panel.compute_op(op)
        return True
