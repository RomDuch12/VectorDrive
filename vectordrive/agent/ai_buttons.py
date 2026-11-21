"""Les boutons IA personnalisés (demande du 20/11, 15 h 32 : « fonction créer un bouton personnalisé qui s'ajoutera dans
la barre favori et colonne Assistant IA : On définit un plan de travail (la selection, le calque, ou tous les calques)
et la tache à effectuer, les règles à respecter, le niveau de controle final, la mémoire et autres données que tu juges
pertinent »).

Un bouton : un libellé, son plan de travail, la tâche, les règles, le contrôle final, une mémoire thématique
(`agent.memories`), les outils permis, les tours au plus, une discussion neuve ou non. Retenus dans les réglages
(`assistant/boutons`, JSON) ; leurs commandes `ia_bouton_<id>` vont dans les favoris comme les autres."""
from __future__ import annotations

import dataclasses
import hashlib
import json
import uuid

KEY = 'assistant/boutons'
PREFIX = 'ia_bouton_'
SCOPES = ('selection', 'calque', 'tous')
#: contrôle final : rien de plus ; un compte rendu ; il vérifie son travail ; une fenêtre Garder / Défaire à la fin
CONTROLS = ('aucun', 'compte_rendu', 'verification', 'validation')
#: les groupes d'outils du panneau (`agent.tools.TOOL_GROUPS`) qu'un bouton peut permettre ou non
GROUPS = ('memory', 'scripts', 'commands', 'cam', 'copies', 'step')
MAX_BUTTONS = 40
LABEL_MAX = 40
TEXT_MAX = 4000


@dataclasses.dataclass
class AIButton:
    id: str = dataclasses.field(default_factory=lambda: uuid.uuid4().hex[:8])
    label: str = ''
    scope: str = 'selection'
    task: str = ''
    rules: str = ''
    control: str = 'compte_rendu'
    memory: str = ''                     # titre d'une mémoire thématique ('' : aucune)
    turns: int = 0                       # tours au plus (0 : celui des options)
    tools: list = dataclasses.field(default_factory=lambda: list(GROUPS))
    new_chat: bool = True                # une discussion neuve à chaque lancement

    @property
    def key(self) -> str:
        return PREFIX + self.id

    def clean(self) -> 'AIButton':
        """Les valeurs ramenées à ce qui est permis (réglages modifiés à la main, version plus ancienne)."""
        b = dataclasses.replace(self)
        b.id = ''.join(c for c in str(b.id) if c.isalnum())[:16] or hashlib.sha1(   # illisible : stable d'un
            f'{b.label}\n{b.task}'.encode('utf-8', 'replace')).hexdigest()[:8]     # chargement à l'autre
        b.label = ' '.join(str(b.label or '').split())[:LABEL_MAX]
        b.scope = b.scope if b.scope in SCOPES else 'selection'
        b.task = str(b.task or '').strip()[:TEXT_MAX]
        b.rules = str(b.rules or '').strip()[:TEXT_MAX]
        b.control = b.control if b.control in CONTROLS else 'compte_rendu'
        b.memory = ' '.join(str(b.memory or '').split())[:80]
        try:
            b.turns = max(0, min(200, int(b.turns)))
        except (TypeError, ValueError):
            b.turns = 0
        b.tools = [g for g in GROUPS if g in (b.tools if isinstance(b.tools, (list, tuple)) else ())]
        b.new_chat = bool(b.new_chat)
        return b


def load(settings) -> list:
    """Les boutons retenus, dans l'ordre (illisibles : ignorés)."""
    raw = settings.value(KEY, '') if settings is not None else ''
    try:
        data = json.loads(raw) if isinstance(raw, str) and raw.strip() else []
    except ValueError:
        return []
    out, seen = [], set()
    names = {f.name for f in dataclasses.fields(AIButton)}
    for d in data if isinstance(data, list) else []:
        if not isinstance(d, dict):
            continue
        b = AIButton(**{k: v for k, v in d.items() if k in names}).clean()
        if b.label and b.task and b.id not in seen:
            seen.add(b.id)
            out.append(b)
    return out[:MAX_BUTTONS]


def save(settings, buttons) -> None:
    data = [dataclasses.asdict(b.clean()) for b in buttons][:MAX_BUTTONS]
    if data:
        settings.setValue(KEY, json.dumps(data, ensure_ascii=False))
    else:
        settings.remove(KEY)


def find(settings, bid: str):
    return next((b for b in load(settings) if b.id == bid), None)


#: les modèles de boutons (demande du 20/11, 21 h 48 : clé en main) : (libellé, plan de travail, tâche, règles,
#: contrôle, outils) ; libellé, tâche et règles passés à tr() à la création
TEMPLATES = (
    ('Cadre autour', 'selection',
     'Ajoute un rectangle à 5 mm autour de la sélection, coins arrondis de 2 mm, sur le calque actif.',
     'Ne modifie pas les objets sélectionnés.', 'compte_rendu', ('memory',)),
    ('Centrer sur la plaque', 'selection',
     'Centre la sélection sur la plaque (la zone de travail), sans changer sa taille.',
     '', 'compte_rendu', ('memory',)),
    ('Vérifier avant la FAO', 'tous',
     'Vérifie le dessin avant la FAO : contours ouverts, doublons superposés, objets minuscules, textes non '
     'vectorisés, objets hors de la plaque. Liste ce que tu trouves, objet par objet.',
     'Ne modifie rien : rends compte seulement.', 'verification', ('memory',)),
    ('Nettoyer le dessin', 'tous',
     'Supprime les doublons superposés et les objets de moins de 0,1 mm ; dis combien tu en as retiré.',
     'Ne touche pas aux textes.', 'validation', ('memory',)),
    ('Préparer la FAO', 'tous',
     'Prépare la FAO du dessin : la machine si elle n’est pas choisie, des opérations adaptées (contour, poche, '
     'gravure) avec des outils de la bibliothèque, puis le calcul des parcours ; dis ce qu’il faut vérifier.',
     'Jamais le programme écrit sur le disque.', 'verification', ('memory', 'cam')),
    # le STEP (demande du 20/11, 22 h) : débutant, avancé, expert
    ('Pièce STEP du dessin', 'selection',
     'Fais une pièce STEP extrudée des contours fermés sélectionnés : le plus extérieur est le bord, les contours '
     'ronds des trous débouchants, les autres des poches de 2 mm ; épaisseur 10 mm. Relis le fichier et donne '
     'l’encombrement et le volume.', 'Ne modifie pas le dessin.', 'verification', ('memory', 'step')),
    ('Pièce tournée STEP', 'selection',
     'Fais une pièce STEP tournée du demi-profil fermé sélectionné (l’axe : le trait droit sélectionné avec lui, '
     'sinon la verticale par son point le plus à gauche). Relis le fichier et donne les diamètres et la longueur.',
     'Ne modifie pas le dessin.', 'verification', ('memory', 'step')),
    ('Plaque et visserie STEP', 'selection',
     'Fais un assemblage STEP avec step_build : la plaque extrudée de 10 mm des contours sélectionnés (un corps '
     '« drawing », trous ronds débouchants), et dans chaque trou rond la vis CHC ISO 4762 qui y passe (le plus grand '
     'diamètre nominal qui laisse du jeu), son axe au centre du trou, tête posée sur le dessus, longueur la plus '
     'proche de 1,5 fois l’épaisseur. Vérifie d’abord sans écrire.',
     'Ne modifie pas le dessin. Un trou sans vis qui convienne : dis-le.', 'verification', ('memory', 'step')),
)


def template(i: int, tr=lambda t: t) -> AIButton:
    """Le modèle `i`, prêt à être relu et gardé (un nouvel identifiant)."""
    label, scope, task, rules, control, tools = TEMPLATES[i]
    return AIButton(label=tr(label), scope=scope, task=tr(task), rules=tr(rules) if rules else '',
                    control=control, tools=list(tools)).clean()
