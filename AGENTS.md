# Consignes des agents — snapshot public PriveoPDF

Ce dépôt contient un snapshot public de PriveoPDF. Lire [README.md](README.md),
[CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md) et le
[socle de développement avec un agent IA](docs/ai-development.md) avant une tâche.
Les règles ci-dessous adaptent ce socle à cette copie publiée.

## Source et portée des changements

- Maintenir les évolutions officielles à la source de publication, puis produire
  un nouvel export contrôlé. Ne pas corriger manuellement le miroir ni recalculer
  son manifeste pour présenter un arbre modifié comme le snapshot d'origine.
- Ce fichier provient d'un modèle public dédié dont le contenu est verrouillé
  dans le contrôleur d'export. Une évolution de ses consignes se prépare dans ce
  modèle et actualise explicitement son empreinte après revue.
- Respecter la politique de contribution de `CONTRIBUTING.md`. La préparation
  d'une modification locale ne vaut ni acceptation d'une contribution externe,
  ni autorisation de fusionner ou de publier une version officielle.
- Ne pas demander ni recopier l'historique, les consignes ou les données du
  développement privé dans le dépôt public. Utiliser les sources présentes
  dans ce snapshot et signaler les éléments nécessaires qui manquent.

## Vérifications disponibles

Sur un snapshot intact, vérifier d'abord son intégrité et son contrat technique :

```bash
sha256sum --check SHA256SUMS
python3 tools/check_public_source_contract.py --snapshot . --technical-only --repository-checkout
```

Ces contrôles décrivent la copie publiée. Ils ne qualifient pas une modification
locale et ne donnent pas une autorisation de publication.

Les commandes de développement correspondent au workflow livré dans le snapshot.
Lire sa version avant de les utiliser. L'installation des dépendances nécessite
le réseau ; elle reste distincte du traitement local des PDF.

```bash
uv sync --frozen --dev
uv run ruff check .
uv run pyright
QT_QPA_PLATFORM=offscreen uv run pytest
```

Commencer par les tests concernés lorsqu'une copie de travail est modifiée.
Préciser les commandes exécutées, les résultats et les contrôles non réalisés.
Ne pas affaiblir les assertions ou les contrôles d'intégrité pour obtenir du vert.

## Invariants du produit

- Garder les PDF, leurs contenus, leurs chemins et les secrets hors du réseau,
  des journaux et des fixtures publiées. Utiliser des données artificielles.
- Préserver le document source et contrôler la validité de la sortie. Le
  traitement reste hors du thread d'interface ; réutiliser les moteurs et les
  validations existants plutôt qu'écrire un parseur PDF supplémentaire.
- Pour une interface, suivre [la charte UI](docs/UI_STYLE_GUIDE.md), les composants
  présents et les traductions disponibles. Aligner l'aide sous `docs/wiki/` si un
  comportement utilisateur change.
- Relire le diff pour la confidentialité, les régressions et la complexité.
  Une revue, des tests et une validation humaine constituent des preuves distinctes.
