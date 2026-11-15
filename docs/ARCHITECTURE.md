# Architecture : un cœur libre, des plugins

**VectorDrive** est un logiciel libre, sous double licence **MIT OU
Apache-2.0** (au choix de qui le reprend). Il ne contient **aucune donnée
ni aucun outil propre à un atelier** : pas de bibliothèque d'outils maison,
de coefficients de devis, de fiches machine, de raccourcis personnels, de
chemins de dossiers, de fichiers clients.

Ce qui est propre à un atelier vit dans un **plugin** : un paquet Python,
souvent privé, que l'atelier développe à côté. Il peut apporter :

| Apport | Exemples |
|---|---|
| données de l'utilisateur | jeu de raccourcis, favoris de la palette FAO, dossiers de polices et de symboles, modèle VND |
| polices | formats de polices propriétaires, lus sur le poste et jamais redistribués (`Api.add_font_format`) |
| outils | bibliothèque d'outils maison, choix de l'outil par opération |
| stratégies d'usinage | gammes de gravure, stratégies propres à une machine |
| gabarits | montages enregistrés, modèles de pièces |
| post-processeurs | **tous** : programmes pour une machine, fiches machine (`Api.add_post`, `add_post_provider`), programmes machine du dessin (`Api.add_format`) |
| chiffrage | méthode de devis de l'atelier |

## Frontière

Le cœur garde tout ce qui sert à n'importe quel graveur :

- dessin, formats (DXF, SVG, PDF, AI, STEP ; VND / SMB / GVT lus pour
  l'interopérabilité avec TypeEdit) ;
- FAO générique : stratégies 2D / 2,5D / 3D, vues 2D et 3D des parcours,
  simulation ; le cadre des post-processeurs (contrôles communs, refus) mais
  **aucun post-processeur** : ils viennent des plugins (round 218) ;
- lecture à l'exécution de la configuration **installée** de TypeEdit
  (`TeTurboKey.ini`, palette `T3PALUSER3D.INI`, bases `.Dbt`, paramètres de
  parcours `PathParam_*.TPP`) : rien n'en est copié dans le dépôt ; les
  fiches `.MAH` sont lues par le plugin qui porte les post-processeurs.

Règle : **une valeur qui n'a de sens que pour un atelier va dans son
plugin** ; le cœur a un comportement neutre quand aucun plugin n'est là
(vérifié par `tests/test_round100.py`).

## Mécanisme des plugins (`vectordrive/plugins.py`)

Un plugin est un paquet Python qui expose :

```python
PLUGIN = {'nom': 'Atelier', 'version': '1.0.0', 'api': 1, 'licence': 'propriétaire'}

def register(api):            # api : vectordrive.plugins.Api
    api.add_shortcut_scheme('atelier', 'Raccourcis de l\'atelier', ENTREES, default=True)
    api.add_post('ma_machine', 'Ma machine', ecrire_programme)
    api.add_action('devis', 'Devis…', ouvrir_devis, tab='FAO', group='Devis', icon='quote')
    ...
```

Recherche, dans l'ordre :

1. les dossiers `plugins/` à côté de l'exécutable et dans le dossier des
   données de l'utilisateur (`%LOCALAPPDATA%\VectorDrive\plugins`, sous
   macOS `~/Library/Application Support/VectorDrive/plugins`, ou
   `~/VectorDrive/plugins` s'il existe d'une première version macOS) ;
2. les chemins de la variable `VECTORDRIVE_PLUGINS` (séparés par `;`) ;
3. `VECTORDRIVE_NO_PLUGINS=1` désactive tout.

**Ajouter un plugin** (F10 › Plugins › « Ajouter un plugin… », Windows et
macOS) : on choisit l'archive `.zip` du plugin ; ses paquets (dossiers de la
racine dont le `__init__.py` définit `register`) et son dossier `_lib` sont
décompressés dans le dossier des plugins de l'utilisateur, et remplacent une
version ajoutée avant ; le plugin est chargé au démarrage suivant. `_lib`
contient les bibliothèques Python pures que le plugin apporte (openpyxl…) :
il est ajouté à la fin de `sys.path` avant le chargement des plugins. Toute
autre bibliothèque va dans `_lib` : un paquet de la racine qui ne nomme pas
`register` fait refuser l'archive. Le remplacement est sans perte : ce qui
est remplacé (paquets, entrées de `_lib`) est mis de côté dans un dossier
`.anciens_…`, effacé une fois tout posé ; en cas d'erreur tout est remis, et
si même cela échoue l'ancienne version reste dans ce dossier. Une archive
rangée dans le dossier qui n'apporte que ces paquets devient `.zip.ancien`.
Le dossier `plugins/` de la version portable passe avant celui de
l'utilisateur : un plugin du même nom qui s'y trouve reste prioritaire. Un
plugin destiné aussi à macOS évite ce qui n'existe que sous Windows (winreg,
chemins `C:/`, exécutables `.exe`) ou le teste avant de s'en servir.

Un plugin qui échoue au chargement n'empêche jamais VectorDrive de
démarrer : l'erreur est affichée dans Aide > À propos.

Points d'extension (`Api`) : jeux de raccourcis, favoris FAO, dossiers de
polices et de symboles, formats de polices (`add_font_format`), actions (onglet et groupe du ruban), stratégies
FAO, boutons de la palette « Créer un parcours », post-processeurs
(`add_post`), post-processeurs tirés de fichiers machine
(`add_post_provider`), formats de fichiers (`add_format` : programmes
machine du dessin, avec leur fenêtre de réglages à l'export),
bibliothèques d'outils, gabarits, réglages par défaut, modèle VND,
traductions, vérifications d'autotest, canal de mise à jour, lignes de
« À propos ». La version de l'API (`API_VERSION`) monte à chaque
changement incompatible.

### Fonctions propres à une machine

Une machine (clé de post-processeur, ou la machine qu'une fiche désigne :
`cam.post.family`) peut faire apparaître ses fonctions quand on la choisit :

```python
def register(api):
    api.add_action('ma_fonction', 'Ma fonction…', ouvrir, tab='FAO', group='Machine', posts=('ma_machine',))
    api.add_panel('mon_panneau', 'Ma machine', lambda win: MonPanneau(win), posts=('ma_machine',))
    api.on_post_changed(lambda win, cle: ...)            # machine choisie, autre dessin, modèle d'usinage
    api.add_post_export('ma_machine', exporter)          # exporter(panneau FAO, parcours, réglage) → vrai si fait
```

- `posts` : la commande ou le panneau ancré n'est montré que pour ces
  machines (vide : toujours) ;
- `add_post_export` : « Post-traitement » appelle cette fonction au lieu de la
  boîte « Enregistrer » ordinaire (nom du travail, dossier, quantité…) ;
- `CamSetup.post_options[clé]` : réglages propres à un post-processeur, gardés
  avec le dessin ;
- un post-processeur qui a un paramètre `machine_dir` reçoit le dossier
  d'écriture tel que la machine le voit (F10 › FAO › chemins des programmes).

## Éditions

- **VectorDrive** : le cœur seul (installateur et archive portable).
- **Édition d'atelier** : le même exécutable avec un plugin copié dans
  `plugins/`, son propre canal de mise à jour :
  `python outils/publier.py --build --plugin CHEMIN/DU/PAQUET --edition NOM
  --manifest nom-latest.json --publisher NOM`.

## Dépôt public

Le dépôt de développement contient aussi des documents de travail privés
(journal de développement, notes d'analyse des formats, spécification
d'origine). `python outils/exporter_public.py DOSSIER` en tire le dépôt
public : fichiers publiables seulement, contrôle qu'aucune donnée
d'atelier ne s'y trouve, historique propre (un commit par export).
