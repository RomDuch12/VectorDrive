"""Oscillation du faisceau laser (wobble), reprise de TauDrive (même auteur).

Superposer une oscillation à l'avance élargit le trait en un seul passage
(un spot de 0,03 mm trace une bande de 0,2 mm) : marquage noir large et
régulier, saignée de découpe un peu plus large que le faisceau. Elle se
fait dans la géométrie, avant l'export : une transformation du parcours.

La phase suit la longueur parcourue (pas le paramètre de chaque segment)
et continue d'un segment au suivant ; elle repart de zéro à chaque trait,
dont le premier et le dernier point restent sur le tracé (un contour
fermé reste fermé).

L'oscillation demande au scanner une cadence de `vitesse / pas` : à
80 m/min et 0,1 mm de pas, 13 kHz — bien au-delà de ce qu'un galvo suit.
`check` le dit avant l'export.
"""
from __future__ import annotations

import math

from .model import Move, arc_points

#: formes d'oscillation : clé → (libellé, effet)
SHAPES = {
    'none': ('Aucune', 'trajectoire directe'),
    'circle': ('Cercle', 'ressort : largeur couverte régulièrement'),
    'eight': ('Huit', 'deux boucles par tour : énergie sur les bords'),
    'transverse': ('Transverse', 'va-et-vient perpendiculaire : le plus court'),
}
#: points par tour : seize, soit un point tous les 6 µm à 0,1 mm de pas
STEPS_PER_TURN = 16
#: cadence qu'un galvo de marquage suit sans faiblir, et au-delà de laquelle il ne suit plus (Hz)
SCANNER_SAFE_HZ = 500.0
SCANNER_MAX_HZ = 1000.0
#: longueur d'un tour, en multiples de l'amplitude (mesurée sur le tracé produit, à 9 % près)
TURN_LENGTH = {'circle': 5.5, 'eight': 8.9, 'transverse': 4.3}


def active(shape: str, amplitude: float, pitch: float) -> bool:
    return shape in SHAPES and shape != 'none' and amplitude > 0 and pitch > 0


def scanner_hz(speed_mm_min: float, pitch_mm: float) -> float:
    """Cadence demandée au scanner : une oscillation par pas parcouru."""
    if pitch_mm <= 0 or speed_mm_min <= 0:
        return 0.0
    return speed_mm_min / 60.0 / pitch_mm


def max_speed(pitch_mm: float, limit_hz: float = SCANNER_SAFE_HZ) -> float:
    """Vitesse (mm/min) au-delà de laquelle le scanner ne suit plus."""
    return max(0.0, pitch_mm * limit_hz * 60.0)


def length_factor(amplitude: float, pitch: float, shape: str = 'circle') -> float:
    """De combien l'oscillation multiplie la longueur d'un trait (≥ 1)."""
    if not active(shape, amplitude, pitch):
        return 1.0
    return max(1.0, math.hypot(TURN_LENGTH.get(shape, 0.0) * amplitude, pitch) / pitch)


def check(speed_mm_min: float, pitch: float, amplitude: float, shape: str = 'circle') -> list[tuple[str, str]]:
    """(niveau, texte) à voir avant l'export ; niveau 'bloquant', 'attention' ou 'info'."""
    notes = []
    if not active(shape, amplitude, pitch):
        return notes
    hz = scanner_hz(speed_mm_min, pitch)
    if hz > SCANNER_MAX_HZ:
        notes.append(('bloquant', f'oscillation à {hz:.0f} Hz : le scanner n\'en suit pas plus de '
                                  f'{SCANNER_MAX_HZ:.0f} ; descendre à {max_speed(pitch) / 1000:.2f} m/min '
                                  'ou élargir le pas'))
    elif hz > SCANNER_SAFE_HZ:
        notes.append(('attention', f'oscillation à {hz:.0f} Hz : au-delà de {SCANNER_SAFE_HZ:.0f} Hz, '
                                   'l\'amplitude réelle faiblit ; à vérifier sur une chute'))
    if pitch > amplitude * 4:
        notes.append(('attention', f'pas de {pitch:g} mm pour une amplitude de {amplitude:g} mm : '
                                   'tours trop espacés, bande festonnée'))
    k = length_factor(amplitude, pitch, shape)
    if k > 8:
        notes.append(('info', f'oscillation : longueur gravée multipliée par {k:.0f} (durée, taille du fichier)'))
    return notes


def _offset(shape: str, phase: float, a: float) -> tuple[float, float]:
    """Écart au tracé, en repère local (tangente, normale)."""
    if shape == 'circle':
        return a * math.sin(phase), a * math.cos(phase)
    if shape == 'eight':                                 # Lissajous 1:2
        return a * math.sin(2 * phase), a * math.cos(phase)
    if shape == 'transverse':
        return 0.0, a * math.cos(phase)
    return 0.0, 0.0


def apply_polyline(poly: list, amplitude: float, pitch: float, shape: str = 'circle') -> list:
    """Une polyligne (x, y), oscillation superposée ; bouts sur le tracé."""
    if not active(shape, amplitude, pitch) or len(poly) < 2:
        return [tuple(p[:2]) for p in poly]
    step = pitch / STEPS_PER_TURN
    out, run = [], 0.0
    for (x1, y1), (x2, y2) in zip([p[:2] for p in poly], [p[:2] for p in poly[1:]]):
        dx, dy = x2 - x1, y2 - y1
        seg = math.hypot(dx, dy)
        if seg <= 1e-12:
            continue
        tx, ty = dx / seg, dy / seg
        nx, ny = -ty, tx                                 # normale à gauche
        n = max(1, int(math.ceil(seg / step)))
        for k in range(n):
            lo, no = _offset(shape, 2 * math.pi * (run + seg * k / n) / pitch, amplitude)
            out.append((x1 + dx * k / n + tx * lo + nx * no, y1 + dy * k / n + ty * lo + ny * no))
        run += seg
    if not out:
        return [tuple(p[:2]) for p in poly]
    out[0] = tuple(poly[0][:2])
    out.append(tuple(poly[-1][:2]))
    return out


def apply_moves(moves: list, amplitude: float, pitch: float, shape: str = 'circle') -> list:
    """Parcours, oscillation superposée à chaque suite d'avances (arcs
    aplatis) ; rapides et plongées inchangés."""
    if not active(shape, amplitude, pitch):
        return list(moves)
    out, chain, z = [], [], 0.0

    def flush():
        nonlocal chain
        if len(chain) > 1:
            out.extend(Move('feed', x, y, z) for x, y in apply_polyline(chain, amplitude, pitch, shape)[1:])
        chain = []

    pos = (0.0, 0.0, 0.0)
    for m in moves:
        if m.kind == 'feed' or m.is_arc:
            if not chain or abs(m.z - z) > 1e-9:
                flush()
                chain, z = [pos[:2]], m.z
                if abs(pos[2] - m.z) > 1e-9:             # avance en pente : laissée telle quelle
                    out.append(m)
                    chain = []
                    pos = (m.x, m.y, m.z)
                    continue
            pts = arc_points(pos, m) if m.is_arc else [(m.x, m.y, m.z)]
            chain.extend(p[:2] for p in pts)
        else:
            flush()
            out.append(m)
        pos = (m.x, m.y, m.z)
    flush()
    return out
