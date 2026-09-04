# Installation utilisateur Linux

Cette page explique comment installer et lancer PriveoPDF comme un utilisateur Linux normal, sans connaitre Python, Git ou `uv`.

PriveoPDF reste une application locale : les PDF ne sont pas envoyes sur Internet par l'application. L'installateur prepare seulement le dossier du projet, les dependances Python locales, les preferences initiales et le lanceur Linux.

## Systeme cible

Parcours prevu pour :

- Linux Mint recent.
- Ubuntu recent.
- Distribution Debian-like proche, si les prerequis sont presents.

Prerequis normalement disponibles ou installables :

- `bash`.
- `python3`.
- `python3-venv`.
- `curl`, uniquement si `uv` doit etre installe automatiquement.

Sur Linux Mint / Ubuntu, en cas de prerequis manquant :

```bash
sudo apt update
sudo apt install python3 python3-venv python3-pip curl
```

## Installation depuis un zip

1. Decompresser l'archive PriveoPDF.
2. Ouvrir le dossier decompresse.
3. Clic droit dans le dossier, puis ouvrir un terminal ici.
4. Lancer :

```bash
bash install_priveopdf.sh
```

L'installateur va :

- verifier que le terminal est dans le bon dossier ;
- verifier Linux et Python ;
- proposer d'installer `uv` si absent ;
- synchroniser les dependances dans `.venv/` ;
- demander la langue ;
- demander le theme ;
- configurer les preferences initiales si possible ;
- verifier les assets de marque ;
- installer ou reparer le lanceur Linux ;
- faire un test minimal de demarrage Python.

## Installation depuis un clone Git

Depuis la racine du depot :

```bash
bash install_priveopdf.sh
```

Le parcours est le meme que pour le zip. Git sert seulement a recuperer ou contribuer au projet ; il n'est pas necessaire pour utiliser PriveoPDF une fois le dossier present.

## Options utiles

```bash
bash install_priveopdf.sh --help
bash install_priveopdf.sh --yes
bash install_priveopdf.sh --no-color
bash install_priveopdf.sh --dry-run
bash install_priveopdf.sh --dry-run --yes --no-color
```

`--yes` choisit les options recommandees sans question interactive.

`--dry-run` simule les etapes sans installer ni modifier les preferences. C'est utile pour verifier le parcours avant une vraie installation.

## Lancer PriveoPDF

Depuis le dossier du projet :

```bash
uv run pdfmod
```

Ouvrir un PDF directement :

```bash
uv run pdfmod chemin/vers/document.pdf
```

Apres installation du lanceur, PriveoPDF peut aussi apparaitre dans le menu des applications. Selon l'environnement de bureau, l'entree peut mettre quelques secondes a apparaitre.

## Test utilisateur minimal apres installation

Pour valider que l'etape P0 fonctionne vraiment :

1. Lancer l'application depuis le terminal avec `uv run pdfmod`.
2. Verifier que la fenetre s'ouvre.
3. Ouvrir un PDF local.
4. Verifier que le PDF s'affiche.
5. Fermer l'application.
6. Chercher PriveoPDF dans le menu Linux.
7. Lancer PriveoPDF depuis le menu si l'entree est disponible.

Le cycle complet installation / desinstallation / reinstallation est documente dans `docs/INSTALL_CYCLE_TEST.md`.

Un diagnostic non destructeur est disponible :

```bash
bash scripts/check_linux_install_state.sh
```

## Reinstaller ou reparer l'installation

Relancer simplement :

```bash
bash install_priveopdf.sh
```

Le script est prevu pour etre relancable : il resynchronise les dependances, reapplique les preferences choisies et reinstalle le lanceur local.

## Desinstaller

Depuis la racine du projet :

```bash
bash uninstall_priveopdf.sh
```

La desinstallation supprime uniquement les fichiers installes par PriveoPDF pour
le lanceur Linux :

- `priveopdf.desktop` sous `$XDG_DATA_HOME/applications/` ou `~/.local/share/applications/` ;
- les icones PriveoPDF sous `$XDG_DATA_HOME/icons/hicolor/.../apps/` ou `~/.local/share/icons/hicolor/.../apps/`.

Elle conserve :

- les PDF utilisateur ;
- le dossier du projet ;
- `.venv/` ;
- les preferences locales par defaut.

Options utiles :

```bash
bash uninstall_priveopdf.sh --help
bash uninstall_priveopdf.sh --dry-run
bash uninstall_priveopdf.sh --no-color
bash uninstall_priveopdf.sh --remove-preferences
```

`--remove-preferences` supprime uniquement le fichier de preferences exact
retourne par Qt via `QSettings("PriveoPDF", "PriveoPDF").fileName()`, si PySide6
est disponible. Si Qt ou PySide6 est indisponible pendant la desinstallation, les
preferences sont conservees avec un avertissement. Le dossier parent n'est jamais
supprime.

## Archive beta Linux

Une archive beta peut etre produite depuis la racine du projet :

```bash
bash scripts/build_beta_zip.sh
```

Le zip est genere sous `dist/PriveoPDF-linux-beta.zip`. Le script refuse
d'ecraser une archive existante sans option explicite :

```bash
bash scripts/build_beta_zip.sh --force
```

Les notes de beta sont dans `BETA_NOTES.md`.

## Ce que l'installateur modifie

L'installateur peut modifier :

- `.venv/` dans le dossier du projet ;
- les preferences locales PriveoPDF, si le script de configuration existe ;
- le lanceur utilisateur sous `~/.local/share/applications/` ou `$XDG_DATA_HOME/applications/` ;
- les icones utilisateur sous `~/.local/share/icons/hicolor/` ou `$XDG_DATA_HOME/icons/hicolor/`.

L'installateur ne doit pas :

- modifier les PDF utilisateur ;
- uploader les PDF ;
- demander de compte ;
- activer de telemetrie ;
- supprimer le dossier du projet.

## Depannage rapide

### `uv: command not found`

Fermer puis rouvrir le terminal, ou lancer :

```bash
source "$HOME/.local/bin/env"
uv --version
```

Puis relancer :

```bash
bash install_priveopdf.sh
```

### `python3-venv semble absent`

Installer le paquet :

```bash
sudo apt update
sudo apt install python3-venv
```

Puis relancer :

```bash
bash install_priveopdf.sh
```

### `Ce dossier ne ressemble pas a la racine de PriveoPDF`

Le terminal n'est probablement pas ouvert dans le bon dossier. Il faut etre dans le dossier contenant `install_priveopdf.sh`, `pyproject.toml` et `src/`.

Commande de verification :

```bash
pwd
ls
```

### Le menu Linux n'affiche pas PriveoPDF

Relancer l'installation du lanceur :

```bash
bash tools/install_linux_launcher.sh
```

Puis attendre quelques secondes ou relancer la session graphique si le menu ne se met pas a jour.

### L'application ne demarre pas

Depuis la racine du projet :

```bash
uv run pdfmod
```

Si cela echoue, lancer le test minimal :

```bash
PYTHONPATH=src .venv/bin/python -c "import pdfmod; print('ok')"
```

Si le test minimal echoue, le probleme vient probablement des dependances Python ou du dossier de lancement.

### Desinstaller seulement le lanceur

```bash
bash tools/uninstall_linux_launcher.sh
```

Ce script retire seulement le fichier desktop et les icones PriveoPDF de
l'utilisateur courant.
