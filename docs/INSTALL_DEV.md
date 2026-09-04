# Installation developpeur

Cette page documente le lancement manuel de PriveoPDF depuis un checkout Git ou
un dossier extrait. Pour un usage simple sur Linux Mint / Ubuntu, utiliser plutot
la commande principale :

```bash
bash install_priveopdf.sh
```

## Prerequis

- Python 3.12 ou plus recent.
- `python3-venv`.
- `curl` si `uv` doit etre installe.
- `bubblewrap` pour tout lancement utilisateur qualifie sous Linux.
- `uv` pour synchroniser l'environnement Python.
- Git uniquement pour cloner ou contribuer au projet.

Sur Linux Mint / Ubuntu :

```bash
sudo apt update
sudo apt install python3 python3-venv python3-pip git curl bubblewrap
```

Installer `uv` manuellement :

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source "$HOME/.local/bin/env"
uv --version
```

## Installation manuelle

Depuis la racine du projet :

```bash
uv sync
```

Cette commande cree ou met a jour `.venv/` et installe les dependances Python du
projet. Elle ne traite aucun PDF.

## Lancement manuel

```bash
bash tools/launch_priveopdf.sh
bash tools/launch_priveopdf.sh chemin/vers/document.pdf
./scripts/dev_run.sh
```

`scripts/dev_run.sh` est un raccourci developpeur non qualifiant autour de
`uv run pdfmod`. Il active volontairement `PRIVEOPDF_ALLOW_UNSANDBOXED_DEV=1` ;
ne pas l'utiliser pour traiter un document non fiable ni pour valider la promesse
de confidentialite.

## Relancer l'installateur

L'installateur peut etre relance depuis la racine du projet :

```bash
bash install_priveopdf.sh
```

Il est prevu pour etre idempotent : il resynchronise les dependances, reapplique
les preferences choisies et reinstalle le lanceur local si necessaire.

Options utiles :

```bash
bash install_priveopdf.sh --help
bash install_priveopdf.sh --yes
bash install_priveopdf.sh --no-color
bash install_priveopdf.sh --dry-run --yes --no-color
```

## Lanceur Linux

Le lanceur est installe via le script existant :

```bash
bash tools/install_linux_launcher.sh
```

Il cree ou met a jour l'entree desktop utilisateur et les icones locales sous
`$XDG_DATA_HOME` ou `~/.local/share`. Selon l'environnement de bureau,
PriveoPDF peut apparaitre dans le menu des applications apres quelques secondes.

## Depannage

### `uv: command not found`

```bash
source "$HOME/.local/bin/env"
uv --version
```

Si `uv` reste absent, relancer l'installation de `uv` :

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### `No module named pdfmod`

Verifier que la commande est lancee depuis la racine du projet :

```bash
pwd
uv sync
bash tools/launch_priveopdf.sh
```

### L'application ne demarre pas

Lancer les checks de base :

```bash
uv run pytest
uv run ruff check .
```

Fallback si `uv` ne fonctionne pas mais que `.venv` existe :

```bash
PYTHONPATH=src .venv/bin/python -m pytest
PYTHONPATH=src .venv/bin/python -c "import pdfmod; print('ok')"
```
