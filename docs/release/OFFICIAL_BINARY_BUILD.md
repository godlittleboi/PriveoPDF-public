# Préparer une distribution binaire officielle

Cette procédure prépare un futur exécutable gratuit sous licence freeware. Elle
ne transforme pas l'archive bêta interne, ne publie rien et ne remplace aucune
validation humaine.

## Entrées obligatoires

Le payload compilé doit être placé hors du dépôt. Il contient l'exécutable, les
bibliothèques réellement livrées et deux fichiers générés par la chaîne de
qualification :

- `SBOM.cdx.json`, inventaire CycloneDX du payload réel ;
- `QT_RUNTIME_INVENTORY.json`, inventaire et preuve de remplacement décrits dans
  `docs/legal/QT_LGPL_COMPLIANCE.md`.

Le bundle de sources Qt réel doit avoir été construit et vérifié depuis
`compliance/third_party_sources.lock.json`.

## Commande

```bash
uv run python tools/build_official_binary_bundle.py \
  --payload-dir /staging/priveopdf-linux-x86_64 \
  --third-party-sources /sortie/PriveoPDF-third-party-sources-qt-6.11.2.zip \
  --output-dir /sortie-officielle \
  --version <version-qualifiee> \
  --platform linux-x86_64 \
  --entrypoint bin/priveopdf \
  --source-commit <sha-complet> \
  --source-date-epoch <epoch-du-commit>
```

Le constructeur refuse l'écrasement. Il produit le ZIP, son checksum SHA-256,
le SBOM et la provenance externes. L'archive contient aussi ces éléments, la
licence freeware canonique, les textes LGPL/GPL, les notices, les instructions
de remplacement, le bundle complet de sources tierces, la politique de
sécurité, le support, l'inventaire réseau, la confidentialité et un manifeste
de checksums.

## Gate de distribution

Exécuter le contrôle indépendant sur les quatre artefacts avant toute action de
publication :

```bash
uv run python tools/check_public_distribution_contract.py \
  --archive /sortie-officielle/PriveoPDF-official-freeware-<version>-<plateforme>.zip \
  --checksum /sortie-officielle/PriveoPDF-official-freeware-<version>-<plateforme>.zip.sha256 \
  --provenance /sortie-officielle/PriveoPDF-official-freeware-<version>-<plateforme>.provenance.json \
  --sbom /sortie-officielle/PriveoPDF-official-freeware-<version>-<plateforme>.sbom.cdx.json
```

Le gate refuse notamment un chemin ZIP dangereux, un payload source, une fuite
évidente, un manifeste incohérent, une confusion freeware/source-available, un Qt non
remplaçable dynamiquement, un module GPL-only, une modification amont non
couverte ou un bundle de sources correspondant mal au verrou.

L'absence actuelle d'un payload compilé et du gigaoctet de sources Qt vérifiées
est un blocage normal : aucun hash d'exécutable réel n'est affirmé dans cette
préparation.
