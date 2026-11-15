"""Ramasse-miettes et gros dessins.

Un dessin d'atelier compte des centaines de milliers d'objets Python
(segments, points) qui vivent tant qu'il est ouvert : chaque collecte
complète du ramasse-miettes les parcourt tous (50 à 100 ms sur un gros
VND) et fige l'interface — ou la sauvegarde de fond, qui tient alors le
verrou de l'interpréteur. Après le chargement d'un gros dessin, on les
« gèle » (`gc.freeze`) : les collectes les ignorent, le comptage de
références les libère toujours. Au chargement suivant, on dégèle et on
collecte d'abord, pour libérer les éventuels cycles de l'ancien dessin.
"""
from __future__ import annotations

import gc

#: segments à partir desquels un dessin est gelé après son chargement
LARGE = 20_000


def settle(segments: int) -> bool:
    """À appeler après le chargement d'un dessin de `segments` segments.
    Rend True si les objets vivants ont été gelés."""
    large = segments >= LARGE
    if not large and not gc.get_freeze_count():
        return False                       # petit dessin, rien de gelé : rien à faire
    gc.unfreeze()
    gc.collect()
    if large:
        gc.freeze()
    return large
