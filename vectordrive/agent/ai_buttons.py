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
GROUPS = ('memory', 'scripts', 'commands', 'cam', 'copies')
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
