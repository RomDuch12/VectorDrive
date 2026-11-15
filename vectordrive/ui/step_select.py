"""Design STEP, groupe « Sélection 3D » : les faces choisies dans la vue 3D
décrites et mesurées en clair (`core.facesel`)."""
from __future__ import annotations

from ..core import facesel as S
from ..i18n import tr

#: au-delà, les faces choisies sont comptées sans être décrites une à une
LIST_MAX = 10


def num(v: float) -> str:
    """Un nombre à trois décimales au plus, virgule décimale."""
    s = f'{v:.3f}'.rstrip('0').rstrip('.').replace('.', ',')
    return '0' if s in ('-0', '') else s


def vec(v) -> str:
    """Une direction : ±X, ±Y, ±Z si elle l'est, sinon ses composantes."""
    for i, name in enumerate('XYZ'):
        if abs(abs(float(v[i])) - 1.0) < 1e-6:
            return ('+' if v[i] > 0 else '-') + name
    return '(' + ' ; '.join(num(float(x)) for x in v) + ')'


def face_text(p: dict) -> str:
    """La face décrite par `facesel.props` : « trou Ø6,6 sur 5,5 mm, axe +Z », « plan, normale +Z, à 12 mm »…"""
    k = p['kind']
    if k == 'cylindre' and 'radius' in p:
        s = (tr('trou Ø{0}') if p['hollow'] else tr('cylindre Ø{0}')).format(num(2 * p['radius']))
        if 'length' in p:
            s += ' ' + tr('sur {0} mm').format(num(p['length']))
        if 'axis' in p:
            s += ', ' + tr('axe {0}').format(vec(p['axis']))
        return s
    if k == 'plan' and 'normal' in p:
        return tr('plan, normale {0}, à {1} mm').format(vec(p['normal']), num(p['offset']))
    return {'cone': tr('cône'), 'sphere': tr('sphère'), 'tore': tr('tore')}.get(k, tr('face'))


def between_text(b: dict) -> str:
    """Les mesures entre deux faces (`facesel.between`) en clair."""
    w = b['what']
    if w == 'parallel_planes':
        return tr('plans parallèles, distance {0} mm').format(num(b['distance']))
    if w == 'planes':
        return tr('angle entre les plans {0}°').format(num(b['angle']))
    if w == 'parallel_axes':
        return tr('axes parallèles, entraxe {0} mm').format(num(b['distance']))
    if w == 'axes':
        return tr('angle des axes {0}°, plus courte distance {1} mm').format(num(b['angle']), num(b['distance']))
    if w == 'axis_plane':
        return tr('axe parallèle au plan, à {0} mm').format(num(b['distance']))
    if w == 'axis_normal_to_plane':
        return tr('axe perpendiculaire au plan')
    if w == 'plane_axis':
        return tr('axe incliné de {0}° sur le plan').format(num(b['angle']))
    return tr('plus courte distance {0} mm').format(num(b['distance']))


def measure_lines(res: dict) -> list:
    """Les lignes de « Mesurer la sélection » pour le résultat de `facesel.measure`."""
    ps = res['faces']
    lines = [tr('Face {0} : {1}, {2} mm²').format(p['face'], face_text(p), num(p['area'])) for p in ps[:LIST_MAX]]
    if len(ps) > LIST_MAX:
        lines.append(tr('… et {0} autres faces').format(len(ps) - LIST_MAX))
    if 'between' in res:
        lines.append(between_text(res['between']))
    if len(ps) > 1 and 'bounds' in res:
        x0, y0, z0, x1, y1, z1 = res['bounds']
        lines.append(tr('{0} faces : {1} mm² ; encombrement {2} × {3} × {4} mm').format(
            len(ps), num(res['area']), num(x1 - x0), num(y1 - y0), num(z1 - z0)))
    return lines


def short_text(model, faces) -> str:
    """Une face : ce qu'elle est ; deux : leur mesure ; sinon '' (pour la ligne d'état de la vue 3D)."""
    faces = sorted(int(f) for f in faces)
    if len(faces) == 1:
        return face_text(S.props(model, faces[0]))
    if len(faces) == 2:
        res = S.measure(model, faces)
        return between_text(res['between']) if 'between' in res else ''
    return ''
