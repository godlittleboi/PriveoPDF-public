# PriveoPDF — PDF sur votre ordinateur

PriveoPDF permet d’ouvrir et d’organiser vos PDF localement, sans compte ni envoi de documents.

## Télécharger et installer — Linux Mint / Ubuntu

**La première bêta Linux `.deb` est qualifiée, mais sa release d’installation reste volontairement privée pour le moment.**

Quand elle sera rendue visible aux utilisateurs, le téléchargement officiel sera disponible uniquement dans [Releases](/godlittleboi/PriveoPDF-public/releases). Ne téléchargez pas un paquet PriveoPDF provenant d’un autre emplacement.

Pour installer la bêta publique :

1. Ouvrez la dernière release et descendez jusqu’à **Assets** (fichiers à télécharger).
2. Téléchargez **`priveopdf_<version>_amd64.deb`**. Ce paquet est destiné aux PC Intel/AMD 64 bits sous **Linux Mint 22** ou **Ubuntu 24.04**. Les archives **Source code** servent uniquement à consulter le code source publié.
3. Facultatif mais recommandé : téléchargez aussi le fichier **`.deb.sha256`** associé pour vérifier l’intégrité du paquet.
4. Double-cliquez sur le fichier `.deb`, puis choisissez **Installer le paquet**. Linux peut demander votre mot de passe et installer des dépendances système nécessaires.
5. Une fois l’installation terminée, ouvrez **PriveoPDF** depuis le menu des applications. La version distribuée aux utilisateurs utilise le logo PriveoPDF normal, sans marqueur DEV ou BETA interne.

### Mettre à jour

Dans une installation `.deb`, **Rechercher les mises à jour** consulte uniquement les Releases de ce dépôt public après votre confirmation. Les releases Draft restent invisibles et sont ignorées. Si une version plus récente est disponible, PriveoPDF affiche les notes de version et le bouton de mise à jour ouvre directement la Release exacte dans votre navigateur.

Fermez ensuite PriveoPDF et installez le nouveau `.deb` par-dessus la version déjà présente. Il n’est normalement pas nécessaire de désinstaller l’ancienne version. PriveoPDF ne lance pas d’installation système privilégiée automatiquement et n’utilise jamais l’updater Git privé dans une installation `.deb`. Les documents personnels et les préférences utilisateur ne sont pas supprimés par une mise à niveau normale.

### Désinstaller

Utilisez le gestionnaire de logiciels de Linux Mint / Ubuntu ou le gestionnaire de paquets du système. La désinstallation de l’application ne supprime pas vos PDF personnels.

### Vérifier le téléchargement

Chaque release officielle doit fournir au minimum le paquet `.deb`, son checksum SHA-256, les notes de version et les éléments de provenance prévus pour cette version. Le fichier `.sha256` permet de vérifier que le paquet téléchargé correspond exactement à celui publié.

Le lancement et les traitements PDF imposent l’isolation réseau Linux. Si elle est indisponible, consultez les limites indiquées dans la release avant installation.

---

PriveoPDF is a local desktop PDF application. PDF files and their contents are
processed locally and are not uploaded. Telemetry is disabled by default.
Optional update checks may contact GitHub after an explicit action or consent;
they send no document, document contents, or document path.

## Status of this copy

This repository is a cleaned, non-canonical publication of one selected
version. It starts from a single root commit and contains no private Git
history, old branch, private pull request, issue, or Actions log. Development
remains in a separate private canonical repository.

The PriveoPDF-owned source in this snapshot is **source available, not open
source**. Its root `LICENSE` is the PriveoPDF Proprietary License — Free Use
and Source Review, version 1.0. It permits personal and internal business use
of an unmodified version, plus source review and security audit. It does not
permit modification, redistribution, resale, sublicensing, or offering the
software as a service without separate written permission. The informative
French and English summaries under `docs/legal/` are not contractual.

Official executables use a separate proprietary freeware license. The French
text under `licenses/PriveoPDF-Freeware-License-FR.txt` is canonical and the
English version is informative. Third-party components retain their own
licenses and are described in `THIRD_PARTY_NOTICES.md`.

For the Qt 6.11.2 baseline, this snapshot also carries the LGPL/GPL texts, the
Qt notice, the exact corresponding-source lock and offline bundle verifier.
These files prepare compliance; they do not assert that an executable or the
one-gigabyte verified source bundle has already been published.

## Downloads and updates

The first Linux `.deb` beta has passed its packaging qualification, but its
installation release is intentionally still private. Once opened to users, the
only official download location will be this repository's **GitHub Releases**
area. Each downloadable package will be tied to a published source snapshot and
accompanied by its version, SHA-256 checksum, release notes, and provenance.
Internal Actions artifacts or packages copied elsewhere are not official
releases.

An installed `.deb` checks only this repository's public GitHub Releases after
user consent. Draft releases are ignored. When a newer version is found, the
application shows its notes and opens that exact Release page; the user then
installs the new `.deb` through the system package manager. The installed build
does not use the private Git updater and does not perform privileged package
installation automatically.

## Feedback

GitHub Discussions is the single entry point for normal user feedback. Questions,
ideas, general feedback, and reproducible problems can start there; the maintainer
moves sufficiently scoped work into Issues when needed. Security reports never
belong in a public Discussion.

## Privacy, network, and security

`docs/compliance/NETWORK_ACTIVITY.md` is the exact inventory of prepared network
paths. Core PDF processing remains local; PDFs are not uploaded and telemetry is
disabled by default. Dependency installation is not an offline operation.

The public repository is only considered ready for announcement when its branch
protection, read-only default Actions permissions, secret scanning with push
protection, Discussions, and GitHub Private Vulnerability Reporting have been
configured successfully. The DEV publisher reverts an incomplete first setup to
private instead of leaving a partially configured public mirror.

Potential vulnerabilities must follow `SECURITY.md`. No security email or postal
address is invented by this project. The CRA playbook is conditional preparation,
not a declaration of conformity.

## Build for local review

Requirements: Python 3.12 and the pinned `uv` version used by the release
process.

```bash
uv sync --frozen --dev
uv run pdfmod
```

The source-checkout update path and internal PR beta history are deliberately
disabled in this review snapshot. This does not affect ordinary local PDF
processing.

## Contribution policy

The initial public phase accepts comments only. Do not send patches, diffs,
substantial source files, third-party code, sensitive PDFs, secrets, personal
paths, confidential information, or details of an unpatched vulnerability.
See `CONTRIBUTING.md`, `FEEDBACK.md`, and `SECURITY.md`.

## Provenance

`PUBLIC_SOURCE_MANIFEST.json` records the exact private source commit, export
schema, deterministic build date, generated files, license mapping, exclusions
by category, and SHA-256 of each payload file. `SHA256SUMS` covers the payload
and the manifest. The ZIP checksum is supplied as a sidecar file.
