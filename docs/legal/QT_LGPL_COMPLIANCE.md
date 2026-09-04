# Dossier Qt / PySide6 / Shiboken — préparation LGPL

Statut au 6 août 2026 : préparation interne, sans distribution publique. Ce
document décrit un mécanisme de conformité et des gates ; il ne constitue ni
un avis juridique, ni une déclaration de conformité d'un exécutable qui
n'existe pas encore sous forme qualifiée.

## Baseline effectivement verrouillée

`uv.lock` fixe les paquets suivants à la version 6.11.2 :

| Paquet | Version | Rôle |
| --- | --- | --- |
| PySide6 | 6.11.2 | méta-paquet des bindings Qt for Python |
| PySide6-Addons | 6.11.2 | modules Qt additionnels, dont QtPdf |
| PySide6-Essentials | 6.11.2 | QtCore, QtGui, QtWidgets et dépendances essentielles |
| Shiboken6 | 6.11.2 | runtime des bindings |

L'analyse AST du code applicatif trouve exactement : `PySide6.QtCore`,
`PySide6.QtGui`, `PySide6.QtPdf`, `PySide6.QtPdfWidgets` et
`PySide6.QtWidgets`. `PySide6.QtTest` n'est utilisé que par les tests de
développement. Aucun import d'un module Qt identifié comme GPL-only n'a été
trouvé. Le gate compare à nouveau cette liste au lock à chaque changement.

Qt PDF 6.11.2 est proposé par Qt sous licence commerciale ou, notamment, sous
GNU LGPL v3 ; PriveoPDF prévoit de s'appuyer sur l'option LGPL pour les
composants éligibles. Les licences des archives amont et des composants tiers
qu'elles contiennent restent seules contractuelles.

## Ce qui n'est pas encore affirmé

Le dépôt ne contient pas de payload exécutable public qualifié. Il est donc
impossible d'inventer dès maintenant la liste des `.so`, DLL, dylibs,
frameworks et plugins réellement embarqués. Pour chaque plateforme, le staging
doit fournir `QT_RUNTIME_INVENTORY.json` avec :

- versions et modules réellement livrés ;
- chemins relatifs de chaque bibliothèque et plugin Qt/PySide6/Shiboken ;
- licence applicable à chaque élément ;
- preuve de liaison dynamique ;
- absence de module GPL-only ;
- absence de patch amont non fourni ;
- résultat d'un test réel de remplacement d'une bibliothèque partagée.

Le constructeur officiel refuse l'archive si cet inventaire, son SBOM ou la
preuve de remplacement sont absents ou incompatibles avec le lock.

## Mesures de conformité préparées

| Exigence | Mesure préparée | Gate restant avant diffusion |
| --- | --- | --- |
| Avis et textes | `QT-NOTICE.txt`, LGPL v3 et GPL v3 embarqués | vérifier les notices de tous les composants réellement livrés |
| Séparation des licences | freeware pour le binaire officiel, licence PriveoPDF source-available pour le code propre, licences amont pour les tiers | inspecter l'archive finale et son SBOM |
| Liaison/remplacement | inventaire exige `dynamic` et `replacement_supported=true` ; instructions de remplacement fournies | tester sur chaque OS et architecture |
| Ingénierie inverse utile | la licence freeware réserve explicitement les droits LGPL | revue juridique de la version finale |
| Sources correspondantes | bundle complet Qt + Qt for Python 6.11.2, verrouillé par taille et SHA-256 | construire les archives réelles de 1 037 714 800 octets au total et les publier avec le binaire |
| Modifications amont | le gate n'accepte actuellement que `upstream_modifications=[]` | si un patch existe, l'ajouter aux sources et étendre le gate |
| Installation information | instructions génériques suivies d'un inventaire propre à la release | prouver qu'une version Qt reconstruite peut être chargée |
| Code tiers dans Qt | archives amont intégrales conservées | inventorier les plugins/bibliothèques réellement distribués et leurs notices |

Les termes PriveoPDF ne doivent jamais interdire un acte permis par la LGPL.
Ils ne peuvent pas requalifier les composants tiers en code propriétaire
PriveoPDF.

## Sources correspondantes verrouillées

`compliance/third_party_sources.lock.json` fixe deux téléchargements officiels :

1. `qt-everywhere-src-6.11.2.tar.xz`, 1 019 661 552 octets,
   SHA-256 `6dcfbca271d76a6502741a2c0dc6fc98ef7dd0b7b4cfd0abcebb285a86a26f33` ;
2. `pyside-setup-everywhere-src-6.11.2.tar.xz`, 18 053 248 octets,
   SHA-256 `cba47efbaad1bedd529725cbc14e21f156c7a19366f07b3edfbb076ffd7afdf8`.

Le constructeur est volontairement hors ligne : il ne télécharge rien, exige
les fichiers dans un cache fourni, vérifie type, taille et hash, puis produit un
ZIP déterministe avec manifeste et checksums. Le vérificateur relit et rehache
chaque membre, y compris les archives amont. Les URLs officielles restent dans
le lock et dans l'avis de disponibilité.

```bash
uv run python tools/build_third_party_sources_bundle.py \
  --cache-dir /cache/qt-verifie \
  --output-dir /sortie/hors-depot

uv run python tools/build_third_party_sources_bundle.py \
  --verify-bundle /sortie/hors-depot/PriveoPDF-third-party-sources-qt-6.11.2.zip
```

La taille des sources officielles interdit de prétendre que le bundle réel a
été construit dans cette préparation. Son absence reste bloquante pour une
diffusion d'exécutable.

## Qualification de la liaison dynamique

Pour chaque payload final :

1. inventorier les fichiers issus des wheels et les plugins effectivement
   copiés ;
2. utiliser les outils de la plateforme (`readelf`/`ldd`, inspection PE ou
   Mach-O) sur un environnement éphémère ;
3. vérifier qu'aucun objet Qt n'est incorporé statiquement dans l'exécutable ;
4. reconstruire ou obtenir une bibliothèque compatible depuis le bundle de
   sources, la substituer dans une copie et exécuter le smoke test ;
5. enregistrer uniquement des chemins relatifs et le résultat dans
   `QT_RUNTIME_INVENTORY.json` ;
6. vérifier que les conditions techniques ou de signature de plateforme ne
   rendent pas le remplacement impossible.

Les instructions destinataire sont dans `QT_LIBRARY_REPLACEMENT.md`. Une clé
privée de signature ne doit jamais être incluse et ne doit pas être nécessaire
au remplacement local.

## Construction de l'archive officielle

`tools/build_official_binary_bundle.py` exige un payload binaire hors dépôt,
un SBOM CycloneDX, l'inventaire Qt qualifié et le bundle réel de sources. Il
refuse les sources Python, secrets, chemins personnels, symlinks, modules
GPL-only, liaison statique, versions divergentes et absence de test de
remplacement. Il embarque la licence freeware française comme `LICENSE.txt`,
les notices tierces, les sources Qt, la confidentialité, la sécurité, le SBOM,
la provenance et les checksums.

## Checklist bloquante par plateforme

- [ ] Payload exact construit depuis un SHA revu et environnement fixé.
- [ ] Bibliothèques et plugins embarqués inventoriés ; aucun élément inattendu.
- [ ] Liaison dynamique démontrée ; aucun objet Qt statiquement lié.
- [ ] Remplacement d'une bibliothèque LGPL testé avec succès.
- [ ] SBOM du payload réel sans chemin local ni composant manquant.
- [ ] Notices propres aux composants et plugins réellement livrés vérifiées.
- [ ] Bundle Qt/PySide6/Shiboken complet construit deux fois avec hash identique.
- [ ] Bundle de sources et binaire rendus disponibles ensemble.
- [ ] Licence freeware, LGPL/GPL, sécurité, confidentialité et provenance présentes.
- [ ] Revue juridique finale effectuée ; aucune revendication générale de conformité.

## Sources officielles consultées le 2 septembre 2026

- <https://www.qt.io/development/open-source-lgpl-obligations>
- <https://doc.qt.io/qt-6/licensing.html>
- <https://doc.qt.io/qt-6/qtpdf-index.html>
- <https://doc.qt.io/qtforpython-6/index.html>
- <https://download.qt.io/official_releases/qt/6.11/6.11.2/single/>
- <https://download.qt.io/official_releases/QtForPython/pyside6/PySide6-6.11.2-src/>
- <https://www.gnu.org/licenses/lgpl-3.0.html>
- <https://www.gnu.org/licenses/gpl-3.0.html>
