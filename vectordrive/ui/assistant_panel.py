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

#: les couleurs de la discussion (lisibles sur fond clair ou sombre) : vous, l'assistant, les valeurs de ses réponses
C_USER, C_BOT, C_VALUE = '#1f6fd1', '#2e8b3e', '#c0661a'
#: les raccourcis d'édition laissés au texte (le dessin a les mêmes)
EDIT_KEYS = (QKeySequence.StandardKey.Copy, QKeySequence.StandardKey.Paste, QKeySequence.StandardKey.Cut,
             QKeySequence.StandardKey.SelectAll, QKeySequence.StandardKey.Undo, QKeySequence.StandardKey.Redo)
#: la discussion (lecture seule) : copier, tout sélectionner ; Ctrl+Z et les autres restent au dessin
VIEW_KEYS = (QKeySequence.StandardKey.Copy, QKeySequence.StandardKey.SelectAll)
#: les valeurs d'une réponse : un texte entre guillemets, un nombre et son unité
VALUE = re.compile(r'«[^»\n]{1,200}»|“[^”\n]{1,200}”|"[^"\n]{1,200}"'
                   r'|(?<![\w.,])[-+−]?\d+(?:[.,]\d+)*(?:\s?(?:mm|cm|m|px|pt|min|s)\b|\s?[°%])?')


def highlight(text: str) -> str:
    """Le texte d'une réponse en HTML, ses valeurs en couleur."""
    out, at = [], 0
    for m in VALUE.finditer(text):
        out.append(html.escape(text[at:m.start()]))
        out.append('<span style="color:{0}">{1}</span>'.format(C_VALUE, html.escape(m.group(0))))
        at = m.end()
    out.append(html.escape(text[at:]))
    return '<span style="white-space:pre-wrap">{0}</span>'.format(''.join(out).replace('\n', '<br>'))


class _Relay(QObject):
    """Les nouvelles du fil de travail, rendues dans le fil de l'interface."""
    text = Signal(str)
    tool = Signal(str)
    done = Signal(str)


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
        st = win.settings

        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        self.provider = QComboBox()
        for slug, (label, *_r) in PROVIDERS.items():
            self.provider.addItem(label, slug)
        k = self.provider.findData(str(st.value(KEY_PROVIDER, 'anthropic') or 'anthropic'))
        self.provider.setCurrentIndex(max(0, k))
        self.model = QComboBox()
        self.model.setEditable(True)
        self.model.setToolTip(tr('Le modèle du fournisseur ; un autre nom peut être écrit'))
        self.url = QLineEdit(str(st.value(KEY_URL, '') or ''))
        self.url.setPlaceholderText('https://api.mistral.ai/v1/chat/completions')
        self.url.setToolTip(tr('Adresse du serveur : celle de Mistral d’office ; un serveur local du même format convient'))
        self.lbl_url = QLabel(tr('Adresse'))
        grid.addWidget(QLabel(tr('Fournisseur')), 0, 0)
        grid.addWidget(self.provider, 0, 1)
        grid.addWidget(QLabel(tr('Modèle')), 1, 0)
        grid.addWidget(self.model, 1, 1)
        grid.addWidget(self.lbl_url, 2, 0)
        grid.addWidget(self.url, 2, 1)
        grid.setColumnStretch(1, 1)
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
        self.input = QPlainTextEdit()
        self.input.setPlaceholderText(tr('Votre demande (Ctrl+Entrée : envoyer)'))
        self.input.setMaximumHeight(self.input.fontMetrics().lineSpacing() * 5 + 12)
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
        for b in (self.btn_send, self.btn_stop, self.btn_new, self.btn_memory):
            row.addWidget(b)
        lay.addLayout(row)
        self.status = QLabel('')
        self.status.setWordWrap(True)
        lay.addWidget(self.status)

        self.provider.currentIndexChanged.connect(lambda _i: self._provider_changed())
        self.model.currentTextChanged.connect(lambda t: st.setValue(KEY_MODEL.format(self.slug()), t.strip()))
        self.url.editingFinished.connect(lambda: st.setValue(KEY_URL, self.url.text().strip()))
        self._provider_changed()
        self._busy(False)
        tab = self._current_tab()
        self._tab = [weakref.ref(tab) if tab is not None else None]

    def _new_view(self) -> QTextBrowser:
        v = QTextBrowser()
        v.setOpenExternalLinks(False)
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
                return fn()
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
        return str(self.provider.currentData() or 'anthropic')

    def _provider_changed(self) -> None:
        p = self.slug()
        self.win.settings.setValue(KEY_PROVIDER, p)
        _label, default, models, _env = self.providers[p]
        self.model.blockSignals(True)
        self.model.clear()
        self.model.addItems(list(models))
        self.model.setEditText(str(self.win.settings.value(KEY_MODEL.format(p), '') or default))
        self.model.blockSignals(False)
        self.lbl_url.setVisible(p == 'mistral')
        self.url.setVisible(p == 'mistral')
        from ..agent.chat import KEY_PAGES
        self.get_key.setText('<a href="{0}">{1}</a>'.format(html.escape(KEY_PAGES[p]),
                                                           html.escape(tr('Obtenir une clé d’API'))))
        self._key_state()

    def _key_state(self) -> None:
        p = self.slug()
        env = self.providers[p][3]
        if self.keys.stored(p):
            text = tr('Clé : retenue')
        elif self.keys.load(p):
            text = tr('Clé : celle de la variable {0}').format(env)
        else:
            text = tr('Aucune clé : collez celle du fournisseur ci-dessous')
        self.key_state.setText(text)
        self.btn_forget.setEnabled(self.keys.stored(p))

    def save_key(self) -> None:
        k = self.key.text().strip()
        if not k:
            return
        kept = self.keys.save(self.slug(), k)
        self.key.clear()
        self.status.setText(tr('Clé retenue dans le gestionnaire d’identifiants de Windows') if kept
                            else tr('Clé retenue pour cette session seulement'))
        self._key_state()

    def forget_key(self) -> None:
        self.keys.forget(self.slug())
        self.conv = None
        self.status.setText(tr('Clé oubliée'))
        self._key_state()

    # --- la discussion ------------------------------------------------------------------------------------
    def _settings_key(self) -> tuple:
        p = self.slug()
        return (p, self.model.currentText().strip(), self.url.text().strip() if p == 'mistral' else '',
                self.keys.load(p))

    def conversation(self):
        """La discussion en cours ; refaite (vide) si le fournisseur, le modèle, l'adresse ou la clé a changé."""
        key = self._settings_key()
        if self.conv is None or key != self._conv_key:
            from ..agent.chat import Conversation
            from ..agent.tools import ToolSet
            p, model, url, api_key = key
            from ..agent.tools import memory_prompt
            self.conv = Conversation(p, model, api_key, ToolSet(self.win, self._runner(self._tab), extended=True),
                                     url=url, client=self.client_for(p), system=memory_prompt(),
                                     on_text=self.relay.text.emit, on_tool=self._tool_seen)
            if self._conv_key is not None and self.view.toPlainText().strip():
                self._line(tr('— Nouvelle discussion ({0}, {1}) —').format(self.providers[p][0], model or '…'))
            self._conv_key = key
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
        try:
            conv = self.conversation()
        except ImportError as ex:
            self.status.setText(tr('Le module « {0} » manque dans cette installation').format(ex.name or ex))
            return False
        except ValueError as ex:
            from ..agent.chat import BadAddress
            self.status.setText(tr('Adresse refusée : https://, ou http:// vers cette machine seulement')
                                if isinstance(ex, BadAddress) else str(ex))
            return False
        self._out = self.view                            # la discussion de cet onglet, même s'il change
        self._line('<b style="color:{2}">{0}</b> <span style="color:{2}">{1}</span>'.format(
            html.escape(tr('Vous :')), html.escape(text).replace('\n', '<br>'), C_USER), raw=True)
        self._replying = False
        self._running = conv                             # « Arrêter » la trouve même si la discussion est refaite
        self._busy(True)
        self.status.setText(tr('L’assistant réfléchit…'))
        self._thread = threading.Thread(target=self._work, args=(conv, text), daemon=True,
                                        name='vectordrive-assistant')
        self._thread.start()
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

    def new_chat(self) -> None:
        if self.running:
            return
        self.conv = None
        self._conv_key = None
        self.view.clear()
        self.status.setText('')

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
        self.btn_forget.setEnabled(not on and self.keys.stored(self.slug()))

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
            self._line('<b style="color:{1}">{0}</b>'.format(html.escape(tr('Assistant :')), C_BOT), raw=True)
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
        if not text.strip():
            return
        c.removeSelectedText()
        c.insertHtml(highlight(text))                    # les espaces gardés (pre-wrap)

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

    def _on_tool(self, text: str) -> None:
        self._line('<span style="color:gray">{0}</span>'.format(html.escape(text)), raw=True)

    def _on_done(self, message: str) -> None:
        self._thread = None                              # dit en dernier par le fil : la demande est finie
        self._busy(False)
        self.status.setText(message)
        self._finish_reply()
        self._replying = False
        if message:
            self._line('<i style="color:#a05a00">{0}</i>'.format(html.escape(message)), raw=True)
        self._out = None
