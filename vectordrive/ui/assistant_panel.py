"""Panneau « Assistant IA » (demande du 17/11 : « prio assistant ia Claude inapp (chercher aussi une compatibilité
Mistral et chatGPT) ») : une discussion, dans une colonne de la fenêtre, avec Claude, ChatGPT ou Mistral, qui lisent
et modifient le dessin ouvert avec les outils de l'assistant (`agent.tools`, les mêmes que le serveur MCP).

- Le fournisseur, son modèle (liste modifiable) et, pour Mistral, l'adresse du serveur (un serveur local du même
  format convient aussi).
- La clé d'API de l'utilisateur, retenue dans le gestionnaire d'identifiants de Windows (`agent.keys`) ; un
  abonnement Claude.ai, ChatGPT ou Le Chat n'en donne pas : le lien mène à la console du fournisseur.
- Ce que l'assistant lit du dessin part chez le fournisseur : le panneau le dit.
- La demande tourne dans un fil de travail ; chaque outil s'exécute dans le fil de l'interface, un pas d'annulation
  chacun (Ctrl+Z) ; une fenêtre modale ou une commande en cours le fait refuser. « Arrêter » coupe au prochain pas.
- Ctrl+Entrée envoie ; « Nouvelle discussion » repart de zéro.
- (demande du 18/11 soir) Copier-coller : les raccourcis d'édition vont au texte de la discussion et de la demande ; le
  menu de la discussion copie toute la discussion. Couleurs : vos demandes, les réponses, les outils, les messages ;
  dans les réponses, les valeurs (nombres, unités, textes entre guillemets). Un assistant par onglet de dessin : chaque
  onglet garde sa discussion ; les outils d'une demande n'agissent que sur l'onglet où elle a été faite.
"""
from __future__ import annotations

import html
import re
import threading
import weakref

from PySide6.QtCore import QEvent, QObject, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QKeySequence, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (QApplication, QComboBox, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit,
                               QPushButton, QStackedWidget, QTextBrowser, QVBoxLayout, QWidget)

from ..i18n import tr

KEY_PROVIDER = 'assistant/fournisseur'
KEY_MODEL = 'assistant/modele_{0}'
KEY_URL = 'assistant/adresse_mistral'
#: les fournisseurs dont on règle l'adresse du serveur → leur clé de réglage (Mistral, Mistral en local)
URL_KEYS = {'mistral': KEY_URL, 'local': 'assistant/adresse_local'}
KEY_MODE = 'assistant/mode'
#: les modes (demande du 20/11, 21 h 48) : Débutant, clé en main ; Avancé, tous les réglages
MODES = (('debutant', 'Débutant'), ('avance', 'Avancé'))
#: des exemples de demandes (mode Débutant, discussion vide)
SUGGESTIONS = ('Décris ce dessin : calques, objets, dimensions',
               'Ajoute un cadre à 5 mm autour de la sélection',
               'Aligne les objets sélectionnés sur leur centre',
               'Prépare la FAO de ce dessin et dis-moi ce qu’il faut vérifier',
               'Fais-moi une vis CHC M5 × 20 en STEP',
               'Que sais-tu faire dans VectorDrive ?')


def mode_of(settings, keys) -> str:
    """Le mode retenu ; jamais choisi : Avancé si une clé est déjà retenue (l'assistant servait déjà), sinon Débutant."""
    from ..agent.chat import PROVIDERS
    v = str(settings.value(KEY_MODE, '') or '') if settings is not None else ''
    if v in dict(MODES):
        return v
    return 'avance' if any(keys.stored(p) for p in PROVIDERS) else 'debutant'

#: les couleurs de la discussion (lisibles sur fond clair ou sombre) : vous, l'assistant, les valeurs de ses réponses
C_USER, C_BOT, C_VALUE = '#1f6fd1', '#2e8b3e', '#c0661a'
C_TOOL = '#808080'
#: les couleurs des options (F10 › Assistant) : vide, celle d'office
COLOR_KEYS = {'user': ('assistant/couleur_vous', C_USER), 'bot': ('assistant/couleur_assistant', C_BOT),
              'value': ('assistant/couleur_valeurs', C_VALUE), 'tool': ('assistant/couleur_outils', C_TOOL)}


def colors(settings) -> dict:
    """Les couleurs de la discussion : celles des options, sinon celles d'office."""
    from PySide6.QtGui import QColor
    out = {}
    for name, (key, default) in COLOR_KEYS.items():
        v = str(settings.value(key, '') or '').strip() if settings is not None else ''
        out[name] = QColor(v).name() if v and QColor(v).isValid() else default
    return out
#: les raccourcis d'édition laissés au texte (le dessin a les mêmes)
EDIT_KEYS = (QKeySequence.StandardKey.Copy, QKeySequence.StandardKey.Paste, QKeySequence.StandardKey.Cut,
             QKeySequence.StandardKey.SelectAll, QKeySequence.StandardKey.Undo, QKeySequence.StandardKey.Redo)
#: la discussion (lecture seule) : copier, tout sélectionner ; Ctrl+Z et les autres restent au dessin
VIEW_KEYS = (QKeySequence.StandardKey.Copy, QKeySequence.StandardKey.SelectAll)
#: les valeurs d'une réponse : un texte entre guillemets, un nombre et son unité
VALUE = re.compile(r'«[^»\n]{1,200}»|“[^”\n]{1,200}”|"[^"\n]{1,200}"'
                   r'|(?<![\w.,])[-+−]?\d+(?:[.,]\d+)*(?:\s?(?:mm|cm|m|px|pt|min|s)\b|\s?[°%])?')


def highlight(text: str, value_color: str = '') -> str:
    """Le texte d'une réponse en HTML, ses valeurs en couleur (`value_color`, sinon celle d'office)."""
    out, at = [], 0
    for m in VALUE.finditer(text):
        out.append(html.escape(text[at:m.start()]))
        out.append('<span style="color:{0}">{1}</span>'.format(value_color or C_VALUE, html.escape(m.group(0))))
        at = m.end()
    out.append(html.escape(text[at:]))
    return '<span style="white-space:pre-wrap">{0}</span>'.format(''.join(out).replace('\n', '<br>'))


class _Relay(QObject):
    """Les nouvelles du fil de travail, rendues dans le fil de l'interface."""
    text = Signal(str)
    tool = Signal(str)
    done = Signal(str)
    usage = Signal(object)                               # (porteur de l'onglet, fournisseur, modèle, jetons)
    status = Signal(str)                                 # une étape à dire : 'ollama-start', 'ollama-ready'


def plain_text(text: str) -> str:
    """Le texte d'une sélection de Qt, tel qu'on le lit : fins de paragraphe et de ligne en retours à la ligne,
    espaces insécables en espaces."""
    return text.replace('\u2029', '\n').replace('\u2028', '\n').replace('\xa0', ' ')


def _plain_mime(edit):
    from PySide6.QtCore import QMimeData
    md = QMimeData()
    md.setText(plain_text(edit.textCursor().selection().toPlainText()))
    return md


class ChatView(QTextBrowser):
    """La discussion : copiée (Ctrl+C, menu, glisser) en texte seul — Qt y joint sinon du HTML, du Markdown et de
    l'OpenDocument, que bien des applications collent à la place du texte (demande du 19/11)."""

    def createMimeDataFromSelection(self):
        return _plain_mime(self)


class PlainInput(QPlainTextEdit):
    """La demande : copiée en texte seul, elle aussi."""

    def createMimeDataFromSelection(self):
        return _plain_mime(self)


class _CheckTools:
    # les « outils » de « Vérifier » : un seul, sans effet (certains fournisseurs refusent une liste vide)

    def specs(self):
        return [{'name': 'ping', 'description': 'Not needed: answer with text only.',
                 'inputSchema': {'type': 'object', 'properties': {}, 'required': []}, 'annotations': {}}]

    def call(self, name, arguments):
        return [{'type': 'text', 'text': 'pong'}]


class AssistantPanel(QWidget):
    """`win` : la fenêtre principale. `client_for(fournisseur)` : un client déjà fait (essais), sinon None."""

    def __init__(self, win):
        super().__init__(win)
        from ..agent import keys
        from ..agent.chat import PROVIDERS
        from ..agent.server import UiBridge
        self.win = win
        self.keys = keys
        self.providers = PROVIDERS
        self.client_for = lambda _p: None
        self.bridge = UiBridge(self)
        self.conv = None
        self._conv_key = None
        self._thread = None
        self._replying = False
        self.relay = _Relay(self)
        self.relay.text.connect(self._on_text)
        self.relay.tool.connect(self._on_tool)
        self.relay.done.connect(self._on_done)
        self.relay.status.connect(self._on_status)
        st = win.settings

        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        # le mode (demande du 20/11, 21 h 48) : Débutant, clé en main ; Avancé, tous les réglages
        self._setup_open = False                         # Débutant : « Changer » a rouvert le fournisseur et la clé
        self.suggest_box = None
        top = QHBoxLayout()
        top.addWidget(QLabel(tr('Mode')))
        self.mode = QComboBox()
        for k, label in MODES:
            self.mode.addItem(tr(label), k)
        self.mode.setToolTip(tr('Débutant : clé en main (premiers pas, exemples de demandes) ; Avancé : tous les '
                                'réglages'))
        m = mode_of(st, keys)
        st.setValue(KEY_MODE, m)                         # retenu : les options (F10) le montrent aussi
        self.mode.setCurrentIndex(max(0, self.mode.findData(m)))
        top.addWidget(self.mode, 1)
        self.btn_options = QPushButton(tr('Options…'))
        self.btn_options.setToolTip(tr('Les options de l’assistant (F10 › Assistant) : outils permis, consignes, '
                                       'crédits, discussion'))
        self.btn_options.clicked.connect(lambda _=False: self.open_options())
        top.addWidget(self.btn_options)
        lay.addLayout(top)
        # les profils (mode Avancé) : des réglages nommés retrouvés d'un clic (jamais la clé)
        self.profile_box = QWidget()
        prow = QHBoxLayout(self.profile_box)
        prow.setContentsMargins(0, 0, 0, 0)
        prow.addWidget(QLabel(tr('Profil')))
        self.profile = QComboBox()
        self.profile.setToolTip(tr('Des réglages nommés : fournisseur, modèle, adresse, outils permis, consignes, '
                                   'tours (jamais la clé d’API ni le plafond des dépenses)'))
        prow.addWidget(self.profile, 1)
        self.btn_profile_save = QPushButton(tr('Garder…'))
        self.btn_profile_save.setToolTip(tr('Les réglages actuels gardés sous un nom (le même nom : remplacé)'))
        self.btn_profile_save.clicked.connect(lambda _=False: self.keep_profile())
        prow.addWidget(self.btn_profile_save)
        self.btn_profile_del = QPushButton(tr('Retirer'))
        self.btn_profile_del.setToolTip(tr('Un profil choisi dans le menu, retiré (les réglages actuels restent)'))
        from PySide6.QtWidgets import QMenu
        self.btn_profile_del.setMenu(QMenu(self.btn_profile_del))
        prow.addWidget(self.btn_profile_del)
        lay.addWidget(self.profile_box)
        self.fill_profiles()
        self.profile.activated.connect(lambda i: self.use_profile(self.profile.itemData(i)))
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        self.provider = QComboBox()
        for slug, (label, *_r) in PROVIDERS.items():
            self.provider.addItem(label, slug)
        k = self.provider.findData(str(st.value(KEY_PROVIDER, 'mistral') or 'mistral'))
        self.provider.setCurrentIndex(max(0, k))
        self.model = QComboBox()
        self.model.setEditable(True)
        self.model.setToolTip(tr('Le modèle du fournisseur ; un autre nom peut être écrit'))
        self.url = QLineEdit(str(st.value(KEY_URL, '') or ''))
        self._url_for = 'mistral'                        # le fournisseur dont `url` montre l'adresse
        self.url.setPlaceholderText('https://api.mistral.ai/v1/chat/completions')
        self.url.setToolTip(tr('Adresse du serveur : celle de Mistral d’office ; un serveur local du même format convient'))
        self.lbl_url = QLabel(tr('Adresse'))
        self.lbl_provider = QLabel(tr('Fournisseur'))
        self.lbl_model = QLabel(tr('Modèle'))
        grid.addWidget(self.lbl_provider, 0, 0)
        grid.addWidget(self.provider, 0, 1)
        grid.addWidget(self.lbl_model, 1, 0)
        grid.addWidget(self.model, 1, 1)
        grid.addWidget(self.lbl_url, 2, 0)
        grid.addWidget(self.url, 2, 1)
        grid.setColumnStretch(1, 1)
        self.steps = QLabel(tr('<b>Premiers pas</b> : 1. choisissez le fournisseur (Mistral d’office) ; 2. « Obtenir '
                               'une clé d’API » : un compte chez lui, un abonnement Le Chat, ChatGPT ou Claude.ai n’en '
                               'donne pas ; 3. collez la clé ci-dessous, puis « Retenir ».'))
        self.steps.setWordWrap(True)
        lay.addWidget(self.steps)
        self.summary = QLabel('')                        # Débutant, une clé : fournisseur, clé, « Changer »
        self.summary.setWordWrap(True)
        self.summary.linkActivated.connect(self._open_setup)
        lay.addWidget(self.summary)
        lay.addLayout(grid)

        row = QHBoxLayout()
        self.key_state = QLabel('')
        self.key_state.setWordWrap(True)
        row.addWidget(self.key_state, 1)
        self.btn_forget = QPushButton(tr('Oublier la clé'))
        self.btn_forget.clicked.connect(self.forget_key)
        row.addWidget(self.btn_forget)
        lay.addLayout(row)
        row = QHBoxLayout()
        self.key = QLineEdit()
        self.key.setEchoMode(QLineEdit.EchoMode.Password)
        self.key.setPlaceholderText(tr('Clé d’API du fournisseur'))
        self.key.returnPressed.connect(self.save_key)
        row.addWidget(self.key, 1)
        self.btn_save = QPushButton(tr('Retenir'))
        self.btn_save.setToolTip(tr('Gardée dans le gestionnaire d’identifiants de Windows, jamais dans les réglages'))
        self.btn_save.clicked.connect(self.save_key)
        row.addWidget(self.btn_save)
        self.btn_check = QPushButton(tr('Vérifier'))
        self.btn_check.setToolTip(tr('Une courte demande au fournisseur (quelques jetons) : la clé, le modèle et le '
                                     'réseau vérifiés ; la réponse ou l’erreur en clair'))
        self.btn_check.clicked.connect(lambda _=False: self.check_key())
        row.addWidget(self.btn_check)
        self._checking = False
        lay.addLayout(row)
        self.get_key = QLabel('')
        self.get_key.setOpenExternalLinks(False)
        self.get_key.linkActivated.connect(lambda url: QDesktopServices.openUrl(QUrl(url)))
        lay.addWidget(self.get_key)
        note = QLabel(tr('Ce que l’assistant lit du dessin (objets, cotes, captures) est envoyé au fournisseur choisi.'))
        note.setWordWrap(True)
        f = note.font()
        f.setPointSizeF(f.pointSizeF() * 0.9)
        note.setFont(f)
        lay.addWidget(note)

        self.stack = QStackedWidget()                    # une discussion par onglet de dessin
        self._tabs: dict = {}                            # id(onglet) : [son porteur, vue, discussion, clé]
        self._tab = [None]                               # le porteur de l'onglet de la discussion affichée : [weakref]
        self._out = None                                 # la vue où écrit la demande en cours
        self._reply_at = None
        self.view = self._new_view()
        lay.addWidget(self.stack, 1)
        from .flow import FlowLayout
        box = QWidget()                                  # Débutant, discussion vide : des exemples de demandes
        flow = FlowLayout(box)
        flow.setContentsMargins(0, 0, 0, 0)
        flow.addWidget(QLabel(tr('Exemples :')))
        self.suggestions = []
        for text in SUGGESTIONS:
            from PySide6.QtWidgets import QToolButton
            b = QToolButton()
            b.setText(tr(text))
            b.setAutoRaise(True)
            b.setToolTip(tr('Mis dans la demande, à relire ou compléter avant d’envoyer'))
            b.clicked.connect(lambda _=False, t=tr(text): self.use_suggestion(t))
            flow.addWidget(b)
            self.suggestions.append(b)
        self.input = PlainInput()
        self.input.setPlaceholderText(tr('Votre demande (Ctrl+Entrée : envoyer)'))
        self.input.setMaximumHeight(self.input.fontMetrics().lineSpacing() * 5 + 12)
        lay.addWidget(box)
        lay.addWidget(self.input)
        self.input.installEventFilter(self)              # Ctrl+Entrée : envoyer (l'éditeur la prendrait pour lui)
        row = QHBoxLayout()
        self.btn_send = QPushButton(tr('Envoyer'))
        self.btn_send.setDefault(True)
        self.btn_send.clicked.connect(self.send_input)
        self.btn_stop = QPushButton(tr('Arrêter'))
        self.btn_stop.clicked.connect(self.stop)
        self.btn_new = QPushButton(tr('Nouvelle discussion'))
        self.btn_new.clicked.connect(self.new_chat)
        self.btn_memory = QPushButton(tr('Mémoire…'))
        self.btn_memory.setToolTip(tr('Ce que l’assistant retient d’une discussion à l’autre : le voir, le corriger'))
        self.btn_memory.clicked.connect(lambda _=False: self.edit_memory())
        self.btn_add_memory = QPushButton(tr('Ajouter à une mémoire…'))
        self.btn_add_memory.setToolTip(tr('Les opérations faites sur ce dessin, dans une mémoire nouvelle ou existante '
                                          '(titre, description) que l’assistant lit quand elle sert'))
        self.btn_add_memory.clicked.connect(lambda _=False: self.add_to_memory())
        from PySide6.QtWidgets import QMenu, QToolButton
        self.btn_more = QToolButton()                    # Débutant : Mémoire et Ajouter à une mémoire, rangés ici
        self.btn_more.setText(tr('Plus'))
        self.btn_more.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        more = QMenu(self.btn_more)
        more.addAction(tr('Mémoire…'), lambda: self.edit_memory())
        more.addAction(tr('Ajouter à une mémoire…'), lambda: self.add_to_memory())
        self.btn_more.setMenu(more)
        for b in (self.btn_send, self.btn_stop, self.btn_new, self.btn_memory, self.btn_add_memory, self.btn_more):
            row.addWidget(b)
        lay.addLayout(row)
        # les boutons IA personnalisés (demande du 20/11, 15 h 32) : leur rangée, « + » pour en créer
        self._override = None                            # (outils retirés, tours) du bouton lancé ; None : les options
        self._button_run = None
        self.validation_box = None
        from .flow import FlowLayout
        self.ai_box = QWidget()                          # à la ligne quand la colonne est étroite
        self.ai_row = FlowLayout(self.ai_box)
        self.ai_row.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.ai_box)
        self.fill_ai_buttons()
        self.status = QLabel('')
        self.status.setWordWrap(True)
        lay.addWidget(self.status)
        # les crédits : ce qu'ont coûté les demandes de la session et celles du dessin affiché (agent.credits)
        self.credits = QLabel('')
        self.credits.setObjectName('assistantCredits')
        self.credits.setWordWrap(True)
        self.credits.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        lay.addWidget(self.credits)
        #: les dépenses de la session (ce lancement, tous les dessins) ; celles d'un dessin : doc.extra['ia_credits']
        self.session_credits = None
        self.relay.usage.connect(self._on_usage)

        self.provider.currentIndexChanged.connect(lambda _i: self._provider_changed())
        self.mode.currentIndexChanged.connect(lambda _i: self._mode_changed())
        self.suggest_box = box
        self.model.currentTextChanged.connect(lambda t: st.setValue(KEY_MODEL.format(self.slug()), t.strip()))
        self.url.editingFinished.connect(
            lambda: st.setValue(URL_KEYS.get(self._url_for, KEY_URL), self.url.text().strip()))
        self._provider_changed()
        self._busy(False)
        tab = self._current_tab()
        self._tab = [weakref.ref(tab) if tab is not None else None]
        self._show_credits()

    def _new_view(self) -> QTextBrowser:
        v = ChatView()
        v.setOpenExternalLinks(False)
        self._style_view(v)
        v.setPlaceholderText(tr('Par exemple : « Dessine une plaque de 120 × 40 mm aux coins arrondis de 5 mm, '
                                'avec le texte BUREAU centré, hauteur 15 mm »'))
        v.installEventFilter(self)                       # Ctrl+C, Ctrl+A : au texte
        v.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        v.customContextMenuRequested.connect(lambda pos, v=v: self._view_menu(v, pos))
        self.stack.addWidget(v)
        self.stack.setCurrentWidget(v)
        return v

    def _view_menu(self, v, pos) -> None:
        m = v.createStandardContextMenu(pos)
        m.addSeparator()
        m.addAction(tr('Copier toute la discussion'), lambda: QApplication.clipboard().setText(v.toPlainText()))
        m.addAction(tr('Enregistrer la discussion…'), lambda: self.save_discussion())
        m.exec(v.viewport().mapToGlobal(pos))
        m.deleteLater()

    # --- un assistant par onglet ----------------------------------------------------------------------------
    def _current_tab(self):
        docs, i = getattr(self.win, 'docs', None), getattr(self.win, 'doc_index', -1)
        return docs[i] if isinstance(docs, list) and 0 <= i < len(docs) else None

    def tab_changed(self, tab) -> None:
        """Un autre onglet de dessin affiché : sa discussion (vide la première fois) ; la demande en cours continue
        dans la sienne. L'onglet vierge remplacé sur place (un fichier ouvert, un nouveau dessin) garde la sienne."""
        ref = self._tab[0]
        cur = ref() if ref is not None else None
        if tab is None or cur is tab:
            return
        e = self._tabs.pop(id(tab), None)
        if e is not None and (e[0][0] is None or e[0][0]() is not tab):     # un identifiant repris : une autre
            if e[1] is not self._out:
                self.stack.removeWidget(e[1])
                e[1].deleteLater()
            e = None
        if cur is None and ref is not None and e is None:
            self._tab[0] = weakref.ref(tab)              # l'onglet remplacé sur place : la discussion continue
            self._show_credits()
            return
        if cur is not None:
            self._tabs[id(cur)] = [self._tab, self.view, self.conv, self._conv_key]
        elif self.view is not self._out:                 # l'onglet affiché est fermé : sa discussion s'en va
            self.stack.removeWidget(self.view)
            self.view.deleteLater()
        for k in [k for k, x in self._tabs.items() if x[0][0]() is None and x[1] is not self._out]:
            x = self._tabs.pop(k)                        # onglets fermés : leur discussion s'en va
            self.stack.removeWidget(x[1])
            x[1].deleteLater()
        if e is not None:
            self._tab, self.view, self.conv, self._conv_key = e
        else:
            self._tab = [weakref.ref(tab)]
            self.view, self.conv, self._conv_key = self._new_view(), None, None
        self.stack.setCurrentWidget(self.view)
        self._show_credits()
        self._apply_mode()                               # les exemples : selon la discussion de cet onglet

    def _runner(self, holder):
        """L'exécution des outils d'une discussion : dans le fil de l'interface, sur l'onglet de la discussion
        seulement (`holder` : [weakref de l'onglet], suivi si l'onglet est remplacé sur place)."""
        def run(fn):
            def guarded():
                ref = holder[0]
                if ref is not None and ref() is not self._current_tab():
                    from ..agent.protocol import ToolError
                    raise ToolError('the user is now looking at another drawing tab: this conversation belongs to '
                                    'its own tab; ask the user to come back to it, then try again')
                run_ = getattr(self, '_button_run', None)   # un bouton IA : les pas posés par ses outils, comptés
                before = getattr(self.win, '_undo_pushes', 0)
                try:
                    return fn()
                finally:
                    if run_ is not None and run_ is getattr(self, '_button_run', None):
                        run_['tool_steps'] += getattr(self.win, '_undo_pushes', 0) - before
            return self.bridge.run(guarded)
        return run

    def eventFilter(self, obj, ev):                      # noqa: N802 — nom imposé par Qt
        if ev.type() == QEvent.Type.ShortcutOverride and isinstance(obj, (QTextBrowser, QPlainTextEdit)) \
                and any(ev.matches(k) for k in (VIEW_KEYS if isinstance(obj, QTextBrowser) else EDIT_KEYS)):
            ev.accept()                                  # au texte, pas aux raccourcis du dessin
            return True
        if getattr(self, 'input', None) is None:         # en construction : la demande pas encore faite
            return super().eventFilter(obj, ev)
        if obj is self.input and ev.type() == QEvent.Type.KeyPress \
                and ev.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) \
                and ev.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.send_input()
            return True
        return super().eventFilter(obj, ev)

    # --- le fournisseur, le modèle, la clé ------------------------------------------------------------
    def slug(self) -> str:
        return str(self.provider.currentData() or 'mistral')

    def _provider_changed(self) -> None:
        p = self.slug()
        self.win.settings.setValue(KEY_PROVIDER, p)
        _label, default, models, _env = self.providers[p]
        self.model.blockSignals(True)
        self.model.clear()
        self.model.addItems(list(models))
        if p == 'local':                                 # les modèles vus chez Ollama à la dernière vérification
            from ..agent import local_models as LM
            seen = self.win.settings.value(LM.KEY_SEEN, '') or ''
            seen = seen.split('|') if isinstance(seen, str) else [str(x) for x in seen]
            self.model.addItems([m for m in seen if m and m not in models])
        self.model.setEditText(str(self.win.settings.value(KEY_MODEL.format(p), '') or default))
        self.model.blockSignals(False)
        from ..agent.chat import KEY_PAGES, NO_KEY
        self.get_key.setText('<a href="{0}">{1}</a>'.format(
            html.escape(KEY_PAGES[p]),
            html.escape(tr('Installer Ollama') if p in NO_KEY else tr('Obtenir une clé d’API'))))
        self._show_url(p)
        self._key_state()

    def _show_url(self, p: str) -> None:
        """L'adresse du serveur du fournisseur `p` (Mistral : celle de Mistral d'office ; en local : Ollama sur ce
        poste d'office)."""
        if p not in URL_KEYS:
            return
        self._url_for = p
        self.url.setText(str(self.win.settings.value(URL_KEYS[p], '') or ''))
        if p == 'local':
            from ..agent import local_models as LM
            self.url.setPlaceholderText(LM.DEFAULT_URL)
            self.url.setToolTip(tr('Adresse d’Ollama : ce poste d’office ; un poste de l’atelier : http://nom:11434'))
        else:
            self.url.setPlaceholderText('https://api.mistral.ai/v1/chat/completions')
            self.url.setToolTip(tr('Adresse du serveur : celle de Mistral d’office ; un serveur local du même format '
                                   'convient'))

    def _key_state(self) -> None:
        p = self.slug()
        env = self.providers[p][3]
        from ..agent.chat import NO_KEY
        if p in NO_KEY:
            text = tr('Sans clé : le modèle tourne sur ce poste, par Ollama ; « Vérifier » l’essaie')
        elif self.keys.stored(p):
            text = tr('Clé : retenue')
        elif self.keys.load(p):
            text = tr('Clé : celle de la variable {0}').format(env)
        else:
            text = tr('Aucune clé : collez celle du fournisseur ci-dessous')
        self.key_state.setText(text)
        self.btn_forget.setEnabled(self.keys.stored(p))
        self._apply_mode()

    # --- le mode : Débutant (clé en main) ou Avancé (demande du 20/11, 21 h 48) ------------------------------------
    def advanced(self) -> bool:
        return self.mode.currentData() == 'avance'

    def _mode_changed(self) -> None:
        self.win.settings.setValue(KEY_MODE, self.mode.currentData())
        self._setup_open = False
        self._apply_mode()

    def _apply_mode(self) -> None:
        """Ce que montre le panneau selon le mode. Débutant : sans clé, les premiers pas (fournisseur, lien, clé) ;
        avec une clé, une ligne (fournisseur, clé, « Changer ») ; des exemples de demandes tant que la discussion est
        vide ; Mémoire et Ajouter à une mémoire sous « Plus ». Avancé : tout."""
        if getattr(self, 'suggest_box', None) is None:   # en construction
            return
        adv = self.advanced()
        p = self.slug()
        has_key = bool(self.keys.load(p))
        setup = adv or not has_key or self._setup_open
        for w in (self.lbl_provider, self.provider, self.key_state, self.btn_forget, self.key, self.btn_save,
                  self.get_key, self.btn_check):
            w.setVisible(setup)
        from ..agent.chat import NO_KEY
        if p in NO_KEY:                                  # sans clé : ni champ, ni Retenir, ni Oublier
            for w in (self.key, self.btn_save, self.btn_forget):
                w.setVisible(False)
        self.btn_check.setEnabled(has_key and not self.running)
        tuned = adv or self._setup_open                  # « Changer » : le modèle et l'adresse aussi (ils servent)
        for w in (self.lbl_model, self.model):
            w.setVisible(tuned)
        for w in (self.lbl_url, self.url):
            w.setVisible(tuned and p in URL_KEYS)
        self.steps.setVisible(not adv and not has_key)
        brief = not adv and has_key                      # la ligne courte : ce qui sert, et Changer / Masquer
        self.summary.setVisible(brief)
        if brief:
            source = (tr('sans clé') if p in NO_KEY else tr('clé retenue') if self.keys.stored(p)
                      else tr('clé de la variable {0}').format(self.providers[p][3]))
            parts = [self.providers[p][0], self.model.currentText().strip(), source]
            if p in URL_KEYS and self.url.text().strip():
                parts.insert(2, self.url.text().strip())  # un serveur choisi : dit, puisqu'il sert
            self.summary.setText('{0} · <a href="setup">{1}</a>'.format(
                ' · '.join(html.escape(x) for x in parts if x),
                html.escape(tr('Masquer') if self._setup_open else tr('Changer'))))
        for w in (self.btn_memory, self.btn_add_memory):
            w.setVisible(adv)
        self.btn_more.setVisible(not adv)
        self.profile_box.setVisible(adv)
        self.suggest_box.setVisible(not adv and not getattr(self, 'running', False) and not self.view.toPlainText().strip())

    def _open_setup(self, _link=None) -> None:
        """« Changer » : le fournisseur, le modèle et la clé, montrés (mode Débutant) ; « Masquer » : la ligne courte
        seule."""
        self._setup_open = not self._setup_open
        self._apply_mode()
        if self._setup_open:
            self.key.setFocus()

    # --- les profils (mode Avancé) -------------------------------------------------------------------------------
    def fill_profiles(self, current: str = '') -> None:
        from . import assistant_profiles as PR
        self.profile.blockSignals(True)
        self.profile.clear()
        self.profile.addItem(tr('— réglages actuels —'), '')
        for p in PR.load(self.win.settings):
            self.profile.addItem(p['name'], p['name'])
        self.profile.setCurrentIndex(max(0, self.profile.findData(current)) if current else 0)
        self.profile.blockSignals(False)
        menu = self.btn_profile_del.menu()               # Retirer : un profil choisi dans son menu, sans le prendre
        menu.clear()
        for p in PR.load(self.win.settings):
            menu.addAction(p['name'], lambda n=p['name']: self.remove_profile(n))
        self.btn_profile_del.setEnabled(not menu.isEmpty())

    def use_profile(self, name) -> bool:
        """Les réglages du profil `name` pris (la prochaine demande : une nouvelle discussion s'ils changent)."""
        from . import assistant_profiles as PR
        if not name:
            return False
        if self.running:
            self.status.setText(tr('Une demande est en cours : attendez sa fin, ou Arrêter'))
            self.fill_profiles()
            return False
        p = PR.find(self.win.settings, name)
        if p is None:
            self.fill_profiles()
            return False
        PR.apply(self.win.settings, p['values'])
        self.apply_settings()                            # fournisseur, modèle, adresse ; le reste : à la demande
        self.fill_profiles(p['name'])
        self.status.setText(tr('Profil « {0} » : ses réglages pris').format(p['name']))
        return True

    def keep_profile(self, name=None):
        """Les réglages actuels gardés sous un nom (demandé si `name` est None ; le même nom : remplacé)."""
        from . import assistant_profiles as PR
        if name is None:
            from PySide6.QtWidgets import QInputDialog
            name, ok = QInputDialog.getText(self, tr('Garder un profil'), tr('Nom du profil'),
                                            text=self.profile.currentData() or '')
            if not ok:
                return None
        got = PR.keep(self.win.settings, name)
        if got is None:
            self.status.setText(tr('Profil refusé : un nom, et au plus {0} profils').format(PR.MAX_PROFILES))
            return None
        self.fill_profiles(got)
        self.status.setText(tr('Profil « {0} » gardé (jamais la clé d’API)').format(got))
        return got

    def remove_profile(self, name=None) -> bool:
        """Le profil `name` retiré (sinon celui de la liste) ; les réglages actuels restent."""
        from . import assistant_profiles as PR
        if not isinstance(name, str):
            name = self.profile.currentData()
        if not name or not PR.remove(self.win.settings, name):
            return False
        current = self.profile.currentData()
        self.fill_profiles(current if current and PR.find(self.win.settings, current) else '')
        self.status.setText(tr('Profil « {0} » retiré').format(name))
        return True

    def use_suggestion(self, text: str) -> None:
        """Un exemple de demande : mis dans la demande, à relire ou compléter avant d'envoyer."""
        self.input.setPlainText(text)
        self.input.setFocus()

    def validate_requests(self) -> bool:
        """Garder ou Défaire à la fin de chaque demande : réglage « assistant/valider » (selon le mode : Débutant
        oui, Avancé non)."""
        v = self._option('assistant/valider')
        return v == 'oui' or (v == 'mode' and not self.advanced())

    def _request_run(self) -> dict:
        """Le suivi d'une demande tapée, comme celui d'un bouton IA au contrôle « validation » (tout le dessin)."""
        from ..agent import ai_buttons as AB
        stack = self.win._undo
        b = AB.AIButton(id='', label=tr('Votre demande'), scope='tous', control='validation')
        return {'button': b, 'pushes': getattr(self.win, '_undo_pushes', 0), 'tool_steps': 0, 'stack': stack,
                'mark': stack[-1] if stack else None, 'outside': {}, 'doc': self.win.canvas.doc}

    def open_options(self, exec_dialog: bool = True):
        """Les options de l'assistant (F10 › Assistant)."""
        return self.win.options_dialog(exec_dialog=exec_dialog, page='Assistant')

    def check_key(self) -> bool:
        """« Vérifier » : une courte demande à part (quelques jetons : ni la discussion, ni ses outils, ni le dessin —
        ses crédits comptent pour la session seulement) ; « Connexion vérifiée », ou l'erreur en clair (clé refusée,
        modèle inconnu, pas de réseau…)."""
        if self.running:
            return False
        p = self.slug()
        if not self.keys.load(p) and self.client_for(p) is None:
            self.status.setText(tr('Il faut une clé d’API du fournisseur (lien ci-dessus)'))
            return False
        from ..agent import credits as CR
        limit = CR.cap(self.win.settings)
        from ..agent.chat import NO_KEY
        if limit > 0 and p not in NO_KEY and float((self.session_credits or {}).get('cout') or 0.0) >= limit:
            self.status.setText(tr('Plafond des dépenses de la session atteint'))
            return False
        from ..agent.chat import Conversation
        p, model, url, api_key = self._settings_key()[:4]
        try:
            conv = Conversation(p, model, api_key, _CheckTools(), url=url, client=self.client_for(p),
                                system='Connection check: answer with the single word OK.', max_steps=1,
                                context=self._settings_key()[7])
        except (ImportError, ValueError) as ex:
            self.status.setText(tr('Vérification impossible : {0}').format(ex))
            return False
        conv.on_usage = lambda used, c=conv: self.relay.usage.emit((None, c.provider, c.model, used))
        self._checking = True
        try:
            self._running = conv
            self._busy(True)
            self.status.setText(tr('Vérification de la connexion…'))
            self._thread = threading.Thread(target=self._work, daemon=True, name='vectordrive-assistant-check',
                                            args=(conv, tr('Vérification de la connexion : réponds seulement « OK ».')))
            self._thread.start()
        except Exception:
            self._checking = False
            self._thread = None
            self._busy(False)
            raise
        return True

    def save_discussion(self, path=None):
        """La discussion de l'onglet affiché dans un fichier : texte (.txt, .md) ou HTML (.html) ; rend le chemin, None
        si rien n'est écrit."""
        if not self.view.toPlainText().strip():
            self.status.setText(tr('La discussion est vide'))
            return None
        if path is None:
            from PySide6.QtWidgets import QFileDialog
            import pathlib as _pl
            path, chosen = QFileDialog.getSaveFileName(self, tr('Enregistrer la discussion'),
                                                       str(_pl.Path.home() / 'discussion.txt'),
                                                       tr('Texte (*.txt);;Markdown (*.md);;HTML (*.html)'))
            if not path:
                return None
            if not _pl.Path(path).suffix:                # le filtre choisi donne l'extension
                path += '.html' if '*.html' in chosen else '.md' if '*.md' in chosen else '.txt'
        import pathlib
        p = pathlib.Path(path)
        ext = p.suffix.lower()
        text = (self.view.toHtml() if ext in ('.html', '.htm') else self.view.document().toMarkdown()
                if ext == '.md' else self.view.toPlainText())
        tmp = p.with_name(p.name + '.~vd')
        try:
            tmp.write_text(text, encoding='utf-8')
            tmp.replace(p)
        except OSError as ex:
            try:
                tmp.unlink()
            except OSError:
                pass
            self.status.setText(tr('Discussion non enregistrée : {0}').format(ex))
            return None
        self.status.setText(tr('Discussion enregistrée : {0}').format(p.name))
        return str(p)

    def save_key(self) -> None:
        k = self.key.text().strip()
        if not k:
            return
        kept = self.keys.save(self.slug(), k)
        self.key.clear()
        self.status.setText(tr('Clé retenue dans le gestionnaire d’identifiants de Windows') if kept
                            else tr('Clé retenue pour cette session seulement'))
        self._setup_open = False                         # Débutant : la ligne courte revient
        self._key_state()

    def forget_key(self) -> None:
        self.keys.forget(self.slug())
        self.conv = None
        self.status.setText(tr('Clé oubliée'))
        self._key_state()

    # --- la discussion ------------------------------------------------------------------------------------
    def _settings_key(self) -> tuple:
        from . import assistant_options as AO
        p, st = self.slug(), self.win.settings
        return (p, self.model.currentText().strip(), self.url.text().strip() if p in URL_KEYS else '',
                self.keys.load(p), AO.without(st), AO.instructions(st), self._option('assistant/tours_max'),
                self._option('assistant/contexte_local') if p == 'local' else 0)

    def _option(self, key: str):
        from .options import value
        return value(self.win.settings, key)

    def _colors(self) -> dict:
        return colors(self.win.settings)

    def _style_view(self, v) -> None:
        """La taille du texte de la discussion (options ; 0 : celle de l'interface)."""
        f = self.font()
        size = self._option('assistant/taille_texte')
        if size > 0:
            f.setPointSize(size)
        v.setFont(f)

    def apply_settings(self) -> None:
        """Les options (F10 › Assistant) reprises : fournisseur, modèle, adresse, taille du texte ; la prochaine
        demande prend les autres (outils, consignes, tours : une nouvelle discussion)."""
        st = self.win.settings
        m = self.mode.findData(mode_of(st, self.keys))
        if m >= 0 and m != self.mode.currentIndex():
            self.mode.setCurrentIndex(m)                 # → _mode_changed
        k = self.provider.findData(str(st.value(KEY_PROVIDER, 'mistral') or 'mistral'))
        if k >= 0 and k != self.provider.currentIndex():
            self.provider.setCurrentIndex(k)             # → _provider_changed
        else:
            self._provider_changed()                     # le modèle des réglages
        self._show_url(self.slug())
        for i in range(self.stack.count()):
            self._style_view(self.stack.widget(i))
        self._show_credits()                             # la devise, le plafond

    def conversation(self):
        """La discussion en cours ; refaite (vide) si le fournisseur, le modèle, l'adresse ou la clé a changé."""
        ov = getattr(self, '_override', None)            # un bouton IA : ses outils et ses tours
        key = self._settings_key() + (ov,)
        old, old_key = self.conv, self._conv_key
        if self.conv is None or key != self._conv_key:
            from ..agent.chat import Conversation
            from ..agent.tools import ToolSet
            p, model, url, api_key = key[:4]
            context = key[7]
            from . import assistant_options as AO
            st = self.win.settings
            tools = ToolSet(self.win, self._runner(self._tab), extended=True,
                            without=ov[0] if ov else AO.without(st))
            self.conv = Conversation(p, model, api_key, tools, url=url, client=self.client_for(p),
                                     system=AO.system_text(st, removed=ov[0] if ov else None),
                                     max_steps=ov[1] if ov else self._option('assistant/tours_max'),
                                     on_text=self.relay.text.emit, on_tool=self._tool_seen, context=context,
                                     on_status=self.relay.status.emit)
            # les jetons de chaque tour : comptés pour la session et pour le dessin de cette discussion (son onglet,
            # suivi s'il est remplacé sur place), même si un autre onglet est affiché entre-temps
            self.conv.on_usage = (lambda used, holder=self._tab, c=self.conv:
                                  self.relay.usage.emit((holder, c.provider, c.model, used)))
            # seuls les outils ou les tours changent (un bouton IA, la demande d'après) : la même discussion
            carry = old is not None and old_key is not None and old_key[:-1] == key[:-1]
            if carry:                                    # même fournisseur : même backend ; OpenAI la tient chez lui
                for attr in ('messages', 'last_id', '_pending'):
                    if hasattr(old._backend, attr) and hasattr(self.conv._backend, attr):
                        setattr(self.conv._backend, attr, getattr(old._backend, attr))
            if not carry and self._conv_key is not None and self.view.toPlainText().strip():
                self._line(tr('— Nouvelle discussion ({0}, {1}) —').format(self.providers[p][0], model or '…'))
            self._conv_key = key
        # Ollama démarré tout seul (réglage repris à chaque demande, sans refaire la discussion)
        self.conv.autostart = key[0] == 'local' and bool(self._option('assistant/demarrage_local'))
        return self.conv

    def send_input(self) -> None:
        text = self.input.toPlainText().strip()
        if text and self.send(text):
            self.input.clear()

    def send(self, text: str) -> bool:
        """Envoie une demande ; rend False si elle ne part pas (déjà une en cours, pas de clé…)."""
        if self.running:
            return False
        p = self.slug()
        if not self.keys.load(p) and self.client_for(p) is None:
            self.status.setText(tr('Il faut une clé d’API du fournisseur (lien ci-dessus)'))
            self.key.setFocus()
            return False
        from ..agent import credits as CR
        from ..i18n import decimal_sep
        limit = CR.cap(self.win.settings)
        from ..agent.chat import NO_KEY
        free = self.slug() in NO_KEY                     # le modèle local ne dépense rien : pas de plafond
        if limit > 0 and not free and float((self.session_credits or {}).get('cout') or 0.0) >= limit:
            self.status.setText(tr('Plafond des dépenses de la session atteint ({0}) : plus de demande avant le '
                                   'prochain lancement (Options › Assistant)')
                                .format(CR.money_text(limit, CR.currency(self.win.settings), decimal_sep())))
            return False
        try:
            conv = self.conversation()
        except ImportError as ex:
            self.status.setText(tr('Le module « {0} » manque dans cette installation').format(ex.name or ex))
            return False
        except ValueError as ex:
            from ..agent.chat import BadAddress
            if not isinstance(ex, BadAddress):
                self.status.setText(str(ex))
            elif self.slug() == 'local':
                self.status.setText(tr('Adresse refusée : https://, ou http:// vers ce poste ou le réseau de '
                                       'l’atelier'))
            else:
                self.status.setText(tr('Adresse refusée : https://, ou http:// vers cette machine seulement'))
            return False
        self._out = self.view                            # la discussion de cet onglet, même s'il change
        self._line('<b style="color:{2}">{0}</b> <span style="color:{2}">{1}</span>'.format(
            html.escape(tr('Vous :')), html.escape(text).replace('\n', '<br>'), self._colors()['user']), raw=True)
        self._replying = False
        self._running = conv                             # « Arrêter » la trouve même si la discussion est refaite
        self._busy(True)
        if getattr(self, '_button_run', None) is None and self.validate_requests():
            self._button_run = self._request_run()       # Garder ou Défaire à la fin (un bouton IA : le sien)
        self.status.setText(tr('L’assistant réfléchit…'))
        self._thread = threading.Thread(target=self._work, args=(conv, text), daemon=True,
                                        name='vectordrive-assistant')
        self._thread.start()
        self.suggest_box.setVisible(False)
        return True

    def _work(self, conv, text: str) -> None:
        from ..agent.chat import Stopped
        try:
            conv.send(text)
            said = {'cut': tr('Réponse coupée : trop longue'),
                    'steps': tr('Arrêt : trop de tours pour une seule demande')}
            message = ' ; '.join(said.get(k, k) for k in conv.notes)
        except Stopped:
            message = tr('Arrêté')
        except Exception as ex:                          # noqa: BLE001 — dite dans le panneau
            message = self.explain(ex)
        try:
            self.relay.done.emit(message)
        except RuntimeError:                             # la fenêtre a été fermée entre-temps
            pass

    def explain(self, ex: Exception) -> str:
        """Une erreur du fournisseur, en clair."""
        from ..agent.chat import LocalDown, LocalError, LocalTimeout, MissingModel
        if isinstance(ex, LocalTimeout):
            return tr('Le modèle local n’a pas répondu à temps : un palier plus petit ou un contexte plus court '
                      '(Options › Assistant › Mistral en local)')
        if isinstance(ex, LocalError):
            if ex.memory:
                return tr('Mémoire insuffisante pour ce modèle : un palier plus petit ou un contexte plus court '
                          '(Options › Assistant › Mistral en local)')
            return tr('Ollama : {0}').format(ex.detail[:200])
        if isinstance(ex, LocalDown):
            from ..agent import local_models as LM
            if not LM.on_this_machine(ex.base):
                return tr('Ollama ne répond pas ({0}) : allumez le poste qui le sert, ou videz l’adresse (Options › '
                          'Assistant › Mistral en local)').format(ex.base)
            return tr('Ollama ne répond pas ({0}) : « Tout préparer » l’installe et le démarre (Options › '
                      'Assistant › Mistral en local)').format(ex.base)
        if isinstance(ex, MissingModel):
            return tr('Le modèle « {0} » n’est pas chez Ollama : « Télécharger le modèle » ou « Tout préparer » '
                      'dans Options › Assistant › Mistral en local').format(ex.model)
        status = getattr(ex, 'status_code', None)
        name = type(ex).__name__
        if status == 401:
            return tr('Clé refusée par le fournisseur (401) : vérifiez-la')
        if status == 403:
            return tr('Accès refusé par le fournisseur (403)')
        if status == 404:
            return tr('Modèle ou adresse inconnus du fournisseur (404)')
        low = str(ex).lower()
        if status in (400, 413) and any(w in low for w in ('context', 'too long', 'too many tokens', 'maximum')):
            return tr('Discussion trop longue pour le modèle : commencez une nouvelle discussion')
        if status == 429:
            return tr('Trop de demandes, ou crédit épuisé chez le fournisseur (429) : réessayez plus tard')
        if isinstance(status, int) and status >= 500:
            return tr('Le fournisseur ne répond pas (HTTP {0}) : réessayez plus tard').format(status)
        if 'Connection' in name or 'Timeout' in name or isinstance(ex, OSError):
            return tr('Pas de connexion au fournisseur : vérifiez le réseau')
        return f'{name}: {ex}'[:300]

    def stop(self) -> None:
        conv = getattr(self, '_running', None)
        if conv is not None and self.running:
            conv.stop()
            self.status.setText(tr('Arrêt au prochain pas…'))

    def edit_memory(self, exec_dialog: bool = True):
        """La mémoire de l'assistant, à voir et corriger (elle vaut pour les discussions suivantes). Rend la
        fenêtre."""
        from PySide6.QtWidgets import QDialog, QDialogButtonBox
        from ..agent import tools as AT
        d = QDialog(self)
        from .fit import release
        release(d)                                     # fermée : détruite, pas gardée
        d.setWindowTitle(tr('Mémoire de l’assistant'))
        lay = QVBoxLayout(d)
        lbl = QLabel(tr('Ce que l’assistant retient d’une discussion à l’autre (il l’écrit quand vous le lui '
                        'demandez) ; donnée au début de chaque nouvelle discussion.'))
        lbl.setWordWrap(True)
        lay.addWidget(lbl)
        d.edit = QPlainTextEdit(AT.memory_text())
        lay.addWidget(d.edit, 1)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(d.accept)
        bb.rejected.connect(d.reject)
        lay.addWidget(bb)
        d.resize(560, 420)

        def keep():
            full = d.edit.toPlainText()
            text = full[:AT.MAX_MEMORY]
            try:
                AT.write_memory(text)
                if len(full) > AT.MAX_MEMORY:
                    self.status.setText(tr('Mémoire gardée, coupée à {0} caractères : elle vaut pour les discussions '
                                           'suivantes').format(AT.MAX_MEMORY))
                else:
                    self.status.setText(tr('Mémoire gardée : elle vaut pour les discussions suivantes'))
            except OSError as ex:
                self.status.setText(str(ex))
        d.accepted.connect(keep)
        if exec_dialog:
            d.exec()
        return d

    # --- les boutons IA personnalisés (demande du 20/11, 15 h 32) ------------------------------------------------------
    def fill_ai_buttons(self) -> None:
        """La rangée des boutons IA : un bouton par bouton défini (clic : lancé ; clic droit : modifier, dupliquer,
        favoris, supprimer), puis « + » pour en créer un."""
        from PySide6.QtWidgets import QToolButton
        from ..agent import ai_buttons as AB
        while self.ai_row.count():
            w = self.ai_row.takeAt(0).widget()
            if w is not None:
                w.deleteLater()
        self.ai_buttons = {}
        lbl = QLabel(tr('Boutons IA :'))
        self.ai_row.addWidget(lbl)
        for b in AB.load(self.win.settings):
            t = QToolButton()
            t.setText(b.label)
            t.setToolTip(b.task[:300])
            t.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            t.clicked.connect(lambda _=False, bid=b.id: self.run_button(bid))
            t.customContextMenuRequested.connect(lambda pos, bid=b.id, w=t: self._ai_menu(bid, w.mapToGlobal(pos)))
            self.ai_row.addWidget(t)
            self.ai_buttons[b.id] = t
        add = QToolButton()
        add.setText('+')
        add.setToolTip(tr('Nouveau bouton IA : un plan de travail, une tâche, des règles, le contrôle final, une '
                          'mémoire ; la flèche : depuis un modèle tout prêt'))
        add.clicked.connect(lambda _=False: self.new_ai_button())
        from PySide6.QtWidgets import QMenu
        menu = QMenu(add)                                # les modèles (demande du 20/11, 21 h 48 : clé en main)
        menu.addAction(tr('Nouveau bouton IA…'), lambda: self.new_ai_button())
        menu.addSection(tr('Depuis un modèle'))
        for i, t in enumerate(AB.TEMPLATES):
            menu.addAction(tr(t[0]), lambda _=False, i=i: self.new_ai_button(template=i))
        add.setMenu(menu)
        add.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        self.ai_row.addWidget(add)
        self.ai_add = add

    def _ai_buttons_changed(self, buttons) -> None:
        from ..agent import ai_buttons as AB
        from . import assistant_buttons as UB
        AB.save(self.win.settings, buttons)
        UB.install(self.win)
        self.win._apply_shortcuts()                      # les raccourcis des boutons (créés, retirés)
        if hasattr(self.win, '_custom_relays'):          # onglets à soi : un bouton supprimé en part, renommé suit
            r = self.win.ribbon
            shown = r.tabText(r.currentIndex())
            self.win._build_custom_tab()
            at = next((i for i in range(r.count()) if r.tabText(i) == shown), -1)
            if at >= 0 and at != r.currentIndex():       # l'onglet affiché, refait : on y reste
                r.setCurrentIndex(at)
        self.win.refresh_favorites()
        self.fill_ai_buttons()

    def new_ai_button(self, exec_dialog: bool = True, source=None, template=None):
        """Un nouveau bouton IA (`source` : un bouton à dupliquer ; `template` : le numéro d'un modèle tout prêt).
        Rend la fenêtre."""
        import dataclasses
        from ..agent import ai_buttons as AB
        from .assistant_buttons import ButtonDialog
        if len(AB.load(self.win.settings)) >= AB.MAX_BUTTONS:   # dit avant la saisie, pas après
            self.status.setText(tr('Au plus {0} boutons IA').format(AB.MAX_BUTTONS))
            return None
        start = None
        if source is not None:
            start = dataclasses.replace(source, id=AB.AIButton().id, label=(source.label + ' 2')[:AB.LABEL_MAX])
        elif isinstance(template, int) and not isinstance(template, bool) and 0 <= template < len(AB.TEMPLATES):
            start = AB.template(template, tr)
        d = ButtonDialog(self.win, start, favorite=True, parent=self)
        if source is None:
            d.setWindowTitle(tr('Nouveau bouton IA'))

        def kept():
            buttons = AB.load(self.win.settings)
            if len(buttons) >= AB.MAX_BUTTONS:
                self.status.setText(tr('Au plus {0} boutons IA').format(AB.MAX_BUTTONS))
                return
            b = d.button()
            self._ai_buttons_changed(buttons + [b])
            if d.favorite.isChecked():
                self.win.add_favorite(b.key)
            self.status.setText(tr('Bouton IA « {0} » créé').format(b.label))
        d.accepted.connect(kept)
        if exec_dialog:
            d.exec()
        return d

    def edit_ai_button(self, bid: str, exec_dialog: bool = True):
        from ..agent import ai_buttons as AB
        from .assistant_buttons import ButtonDialog
        b = AB.find(self.win.settings, bid)
        if b is None:
            return None
        d = ButtonDialog(self.win, b, favorite=b.key in self.win.favorite_keys(), parent=self)

        def kept():
            nb = d.button()
            self._ai_buttons_changed([nb if x.id == bid else x for x in AB.load(self.win.settings)])
            if d.favorite.isChecked():
                self.win.add_favorite(nb.key)
            else:
                self.win.remove_favorite(nb.key)
        d.accepted.connect(kept)
        if exec_dialog:
            d.exec()
        return d

    def delete_ai_button(self, bid: str) -> bool:
        from ..agent import ai_buttons as AB
        buttons = AB.load(self.win.settings)
        b = next((x for x in buttons if x.id == bid), None)
        if b is None:
            return False
        self.win.remove_favorite(b.key)
        self._ai_buttons_changed([x for x in buttons if x.id != bid])
        self.status.setText(tr('Bouton IA « {0} » supprimé').format(b.label))
        return True

    def _ai_menu(self, bid: str, at, exec_menu: bool = True):
        from PySide6.QtWidgets import QMenu, QMessageBox
        from ..agent import ai_buttons as AB
        b = AB.find(self.win.settings, bid)
        if b is None:
            return None
        m = QMenu(self)
        m.addAction(tr('Lancer'), lambda: self.run_button(bid))
        m.addAction(tr('Modifier…'), lambda: self.edit_ai_button(bid))
        m.addAction(tr('Dupliquer…'), lambda: self.new_ai_button(source=b))
        fav = b.key in self.win.favorite_keys()
        m.addAction(tr('Retirer des favoris') if fav else tr('Ajouter aux favoris'),
                    lambda: self.win.remove_favorite(b.key) if fav else self.win.add_favorite(b.key))
        m.addSeparator()

        def delete():
            if QMessageBox.question(self, tr('Bouton IA'), tr('Supprimer le bouton « {0} » ?').format(b.label)) \
                    == QMessageBox.StandardButton.Yes:
                self.delete_ai_button(bid)
        m.addAction(tr('Supprimer…'), delete)
        if exec_menu:
            m.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
            m.exec(at)
        return m

    def run_button(self, bid: str) -> bool:
        """Lance le bouton IA `bid` : sa demande (plan de travail, tâche, règles, mémoire, contrôle) avec ses outils et
        ses tours ; rend False si elle ne part pas (dit dans la barre du panneau)."""
        from ..agent import ai_buttons as AB
        from . import assistant_buttons as UB
        from . import assistant_options as AO
        b = AB.find(self.win.settings, bid)
        if b is None:
            self.status.setText(tr('Ce bouton IA n’existe plus'))
            return False
        if self.running:
            self.status.setText(tr('Une demande est en cours : attendez sa fin, ou Arrêter'))
            return False
        items, description = UB.scope_items(self.win, b.scope)
        if not items:
            self.status.setText(UB.empty_text(b.scope))
            return False
        st = self.win.settings
        without = tuple(sorted(set(AO.without(st)) | (set(AB.GROUPS) - set(b.tools))))
        turns = b.turns or self._option('assistant/tours_max')
        before = (self._override, self.conv)
        self._override = None if (without == AO.without(st) and not b.turns) else (without, turns)
        if b.new_chat:
            self.conv = None
        ids = [it.id for it in items]
        stack = self.win._undo
        # « tool_steps » : les pas posés par ses outils (compté dans _runner) ; Défaire n'annule qu'eux
        self._button_run = {'button': b, 'pushes': getattr(self.win, '_undo_pushes', 0), 'tool_steps': 0,
                            'stack': stack, 'mark': stack[-1] if stack else None,
                            'outside': UB.outside(self.win, ids), 'doc': self.win.canvas.doc}
        ok = False
        try:
            ok = bool(self.send(UB.compose(b, items, description, memory_allowed='memory' not in AO.without(st))))
        finally:
            if not ok:                                   # partie ou pas, jamais un état collé
                self._button_run = None
                self._override, self.conv = before
        return ok

    def _after_button(self) -> None:
        """La demande d'un bouton IA finie : les objets hors du plan de travail changés dits ; contrôle
        « validation » : Garder ou Défaire."""
        from . import assistant_buttons as UB
        run, self._button_run = getattr(self, '_button_run', None), None
        if run is None:
            return
        b = run['button']
        steps = run['tool_steps']
        if self.win.canvas.doc is not run['doc']:        # un autre onglet entre-temps : rien à comparer ici
            if b.control == 'validation' and steps > 0:
                self.status.setText(tr('Le dessin du bouton « {0} » n’est plus affiché : Garder ou Défaire impossible '
                                       'ici (Ctrl+Z sur son onglet)').format(b.label) if b.id else
                                    tr('Le dessin de la demande n’est plus affiché : Garder ou Défaire impossible ici '
                                       '(Ctrl+Z sur son onglet)'))
            return
        moved = UB.changed(run['outside'], self.win)
        if moved:
            self.status.setText(tr('Attention : {0} objet(s) hors du plan de travail ont changé (Ctrl+Z pour '
                                   'revenir)').format(len(moved)))
        stack, mark = run['stack'], run['mark']
        only_its = getattr(self.win, '_undo_pushes', 0) - run['pushes'] == steps   # rien d'autre posé pendant
        if b.control == 'validation' and steps > 0 and only_its and self.win._undo is stack:
            at = -1 if mark is None else next((i for i in range(len(stack) - 1, -1, -1) if stack[i] is mark), None)
            if at is not None:                           # ce qui reste de ses pas (l'outil « undo » en retire)
                steps = len(stack) - 1 - at
        if b.control == 'validation' and steps > 0 and not only_its:
            self.status.setText(tr('D’autres modifications ont été faites pendant le bouton « {0} » : Ctrl+Z à la '
                                   'main pour défaire').format(b.label) if b.id else
                                tr('D’autres modifications ont été faites pendant la demande : Ctrl+Z à la main pour '
                                   'défaire'))
            return
        if b.control == 'validation' and steps > 0:
            prev = getattr(self, 'validation_box', None)
            if prev is not None:                         # celle d'un lancement d'avant : remplacée
                try:
                    prev.hide()
                    prev.deleteLater()
                except RuntimeError:                     # déjà détruite
                    pass
            box = UB.ValidationBox(self, b, steps, moved)
            top = stack[-1] if stack else None

            def its_own() -> bool:
                """Le haut de la pile : exactement ses pas, posés sur le pas d'avant le lancement."""
                if not only_its or self.win._undo is not stack or not stack or stack[-1] is not top:
                    return False
                at = -1 if mark is None else next((i for i in range(len(stack) - 1, -1, -1) if stack[i] is mark),
                                                  None)
                return at is not None and len(stack) - 1 - at == steps

            def undo():
                if self.running:                         # une autre demande travaille sur le dessin
                    self.status.setText(tr('Une demande est en cours : attendez sa fin, ou Arrêter'))
                    return
                if self.win.canvas.doc is not run['doc'] or not its_own():
                    self.status.setText(tr('D’autres modifications que celles du bouton : Ctrl+Z à la main') if b.id
                                        else tr('D’autres modifications que celles de la demande : Ctrl+Z à la main'))
                    return
                for _ in range(steps):
                    self.win.undo()
                self.status.setText(tr('Modifications du bouton « {0} » défaites').format(b.label) if b.id
                                    else tr('Modifications de la demande défaites'))
            box.undo_button.clicked.connect(lambda _=False: undo())   # « clicked » passe un booléen
            self.validation_box = box
            box.show()                                   # pas open() : modale à la fenêtre, elle bloquerait l'assistant

    def add_to_memory(self, exec_dialog: bool = True):
        """« Ajouter à une mémoire… » (demande du 20/11, 15 h 36) : les opérations du dessin affiché dans une mémoire
        thématique, nouvelle ou existante. Rend la fenêtre."""
        from .assistant_memories import AddToMemory
        d = AddToMemory(self.win, self)

        def kept():
            from . import assistant_options as AO
            if 'memory' in AO.without(self.win.settings):
                self.status.setText(tr('Gardé dans la mémoire « {0} » ; l’assistant ne la lit pas : sa mémoire est '
                                       'retirée dans les options (Options › Assistant)').format(d.saved_title))
                return
            self.status.setText(tr('Gardé dans la mémoire « {0} » : l’assistant la lit quand elle sert (les '
                                   'prochaines discussions la voient d’office)').format(d.saved_title))
        d.accepted.connect(kept)
        if exec_dialog:
            d.exec()
        return d

    def new_chat(self) -> None:
        if self.running:
            return
        self.conv = None
        self._conv_key = None
        self.view.clear()
        self.status.setText('')
        self._apply_mode()

    def shutdown(self) -> None:
        """La fenêtre se ferme : la demande en cours s'arrête, aucun outil ne s'exécute plus."""
        self.bridge.closed = True
        for conv in (self.conv, getattr(self, '_running', None)):
            if conv is not None:
                conv.stop()

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def wait(self, seconds: float = 30.0) -> bool:
        """Attend la fin de la demande en cours en laissant tourner l'interface (essais) ; rend True si finie."""
        import time
        end = time.monotonic() + seconds
        while self.running and time.monotonic() < end:
            QApplication.processEvents()
            time.sleep(0.01)
        QApplication.processEvents()
        return not self.running

    # --- l'affichage ----------------------------------------------------------------------------------------
    def _busy(self, on: bool) -> None:
        self.btn_send.setEnabled(not on)
        self.btn_stop.setEnabled(on)
        self.btn_new.setEnabled(not on)
        for w in (self.provider, self.model, self.url, self.key, self.btn_save):
            w.setEnabled(not on)
        if hasattr(self, 'btn_check'):
            self.btn_check.setEnabled(not on and bool(self.keys.load(self.slug())))
        self.btn_forget.setEnabled(not on and self.keys.stored(self.slug()))
        box = getattr(self, 'validation_box', None)
        if box is not None:                              # pendant une demande : pas de Défaire (sa boîte se fermerait)
            from shiboken6 import isValid
            if isValid(box):
                box.undo_button.setEnabled(not on)

    def _target(self) -> QTextBrowser:
        out = self._out
        try:
            if out is not None:
                out.document()
                return out
        except RuntimeError:                             # sa vue est partie
            self._out = None
        return self.view

    def _line(self, text: str, raw: bool = False) -> None:
        self._finish_reply()
        v = self._target()
        c = v.textCursor()
        c.movePosition(QTextCursor.MoveOperation.End)
        if not v.document().isEmpty():
            c.insertBlock()
        c.insertHtml(text if raw else html.escape(text))
        v.setTextCursor(c)
        v.ensureCursorVisible()
        self._replying = False

    def _on_text(self, chunk: str) -> None:
        v = self._target()
        if not self._replying:
            self._line('<b style="color:{1}">{0}</b>'.format(html.escape(tr('Assistant :')), self._colors()['bot']),
                       raw=True)
            self._replying = True
            end = QTextCursor(v.document())
            end.movePosition(QTextCursor.MoveOperation.End)
            self._reply_at = end.position()
            chunk = ' ' + chunk
        c = v.textCursor()
        c.movePosition(QTextCursor.MoveOperation.End)
        c.insertText(chunk, QTextCharFormat())           # pas le gras du libellé
        v.setTextCursor(c)
        v.ensureCursorVisible()

    def _finish_reply(self) -> None:
        """La réponse finie : ses valeurs mises en couleur."""
        at, self._reply_at = self._reply_at, None
        if not self._replying or at is None:
            return
        v = self._target()
        c = QTextCursor(v.document())
        c.setPosition(min(at, v.document().characterCount() - 1))
        c.movePosition(QTextCursor.MoveOperation.End, QTextCursor.MoveMode.KeepAnchor)
        text = c.selectedText().replace('\u2029', '\n')
        if not text.strip() or not self._option('assistant/valeurs_couleur'):
            return
        c.removeSelectedText()
        c.insertHtml(highlight(text, self._colors()['value']))   # les espaces gardés (pre-wrap)

    def _tool_seen(self, name: str, _args, out: list, err: bool) -> None:
        """Dans le fil de travail : un outil appelé, dit dans le panneau."""
        if err:
            why = ' '.join(c.get('text', '') for c in out if c.get('type') == 'text')[:160]
            self.relay.tool.emit(f'⚙ {name} — {why}')
        elif name == 'memory_write' and isinstance(_args, dict):    # ce qu'il retient : dit, pour le voir
            what = str(_args.get('text', ''))[:300]
            self.relay.tool.emit(f'⚙ {name} — {what}' if what else f'⚙ {name}')
        else:
            self.relay.tool.emit(f'⚙ {name}')

    def _on_status(self, key: str) -> None:
        """Une étape du fil de travail (le démarrage d'Ollama), dans la ligne d'état du panneau."""
        said = {'ollama-start': tr('Ollama ne répondait pas : démarrage d’Ollama…'),
                'ollama-ready': tr('Ollama est en marche : l’assistant réfléchit…')}
        if self.running:
            self.status.setText(said.get(key, key))

    def _on_tool(self, text: str) -> None:
        if not self._option('assistant/montrer_outils'):
            return
        self._line('<span style="color:{1}">{0}</span>'.format(html.escape(text), self._colors()['tool']), raw=True)

    def _on_usage(self, payload) -> None:
        """Dans le fil de l'interface : les jetons d'un tour, comptés pour la session et pour le dessin de la
        discussion — dans `doc.extra['ia_credits']`, donc dans son .vdz ; le dessin est marqué modifié, pour qu'ils
        ne se perdent pas à la fermeture."""
        from ..agent import credits as CR
        holder, provider, model, used = payload
        if not any(CR.normal(used).values()):
            return
        if getattr(self.win, '_writing_doc', False):     # un enregistrement lit doc.extra dans son fil : après lui
            from PySide6.QtCore import QTimer
            QTimer.singleShot(200, lambda p=payload: self._on_usage(p))
            return
        st = self.win.settings
        table, money = CR.prices(st), CR.currency(st)
        self.session_credits = CR.add(self.session_credits, provider, model, used, table, money)
        ref = holder[0] if holder else None
        tab = ref() if ref is not None else None
        if tab is not None:
            current = tab is self._current_tab()
            canvas = getattr(self.win, 'canvas', None)
            doc = getattr(canvas, 'doc', None) if current else getattr(tab, 'doc', None)
            if isinstance(getattr(doc, 'extra', None), dict):
                doc.extra[CR.KEY] = CR.add(doc.extra.get(CR.KEY), provider, model, used, table, money)
                path = getattr(self.win, 'path', None) if current else getattr(tab, 'path', None)
                # marqué modifié pour que la dépense aille dans son .vdz — pas un dessin vide jamais enregistré
                # (l'onglet vierge resterait sinon à enregistrer, et ne serait plus repris par Ouvrir / Nouveau)
                if path or getattr(doc, 'source_path', None) or any(L.items for L in getattr(doc, 'layers', [])):
                    if current:
                        self.win.modified = True
                        title = getattr(self.win, '_title', None)
                        if callable(title):
                            title()
                    else:
                        tab.modified = True
                    sync = getattr(self.win, '_sync_tabs', None)
                    if callable(sync):
                        sync()
        self._show_credits()

    def _show_credits(self) -> None:
        """Sous la discussion : les dépenses de la session et du dessin affiché ; le détail par modèle en infobulle."""
        from ..agent import credits as CR
        from ..i18n import decimal_sep
        lab = getattr(self, 'credits', None)
        if lab is None:
            return
        st = self.win.settings
        sep = decimal_sep()
        doc = getattr(getattr(self.win, 'canvas', None), 'doc', None)
        mine = doc.extra.get(CR.KEY) if isinstance(getattr(doc, 'extra', None), dict) else None

        def part(t) -> str:
            if not CR.spent(t):
                return tr('rien')
            return tr('{0} ({1} jetons)').format(
                CR.money_text(float(t.get('cout') or 0.0), str(t.get('devise') or CR.currency(st)), sep),
                CR.tokens_text(CR.tokens(t)))
        lab.setText(tr('Crédits — cette session : {0} · ce dessin : {1}').format(part(self.session_credits),
                                                                               part(mine)))
        tip = []
        for title, t in ((tr('Cette session'), self.session_credits), (tr('Ce dessin (gardé dans son .vdz)'), mine)):
            if not CR.spent(t):
                continue
            tip.append(title + ' :')
            for key, one in sorted((t.get('par_modele') or {}).items()):
                tip.append('  ' + tr('{0} — {1} ; {2} tours ; {3} en entrée, {4} en sortie, {5} en cache').format(
                    key, CR.money_text(float(one.get('cout') or 0.0), str(t.get('devise') or CR.currency(st)), sep),
                    one.get('tours', 0), CR.tokens_text(one.get('entree', 0)), CR.tokens_text(one.get('sortie', 0)),
                    CR.tokens_text(one.get('cache', 0) + one.get('ecrit', 0))))
            if t.get('sans_prix'):
                tip.append('  ' + tr('Sans prix (jetons comptés seulement) : {0}').format(', '.join(t['sans_prix'])))
        limit = CR.cap(st)
        if limit > 0:
            tip.append(tr('Plafond par session : {0}').format(CR.money_text(limit, CR.currency(st), sep)))
        tip.append(tr('Prix et plafond : Options › Assistant'))
        lab.setToolTip('\n'.join(tip))

    def _on_done(self, message: str) -> None:
        self._thread = None                              # dit en dernier par le fil : la demande est finie
        try:
            self._busy(False)
            if getattr(self, '_checking', False):        # « Vérifier » : pas d'erreur, la connexion est bonne
                self._checking = False
                message = message or tr('Connexion vérifiée : le fournisseur répond')
            self.status.setText(message)
            self._finish_reply()
            self._replying = False
            if message:
                self._line('<i style="color:#a05a00">{0}</i>'.format(html.escape(message)), raw=True)
            self._out = None
        finally:
            try:
                self._after_button()                     # toujours : `_button_run` vidé
            finally:
                self._override = None                    # la demande suivante : les réglages des options
