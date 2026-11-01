# Third Party Notices

Le code, la documentation propres et les executables officiels PriveoPDF sont sous Apache-2.0. Ce document suit
les licences et risques des dependances. La licence PriveoPDF ne remplace pas les
droits propres aux composants tiers.

## Dependances runtime

| Dependance | Usage | Licence connue | Note |
| --- | --- | --- | --- |
| Tesseract 5 (paquet système libtesseract5) | Reconnaissance de texte d'OCR PDF | Apache-2.0 | Bibliothèque fournie par la distribution (Ubuntu 24.04 / Linux Mint 22 : 5.3.4), chargée dynamiquement par `ctypes` depuis `libtesseract.so.5` ; aucune copie embarquée, aucun CLI lancé. Dépend de Leptonica (`liblept5`, licence BSD à deux clauses de Leptonica), également fournie par la distribution. Sources : https://github.com/tesseract-ocr/tesseract |
| Modèles Tesseract (paquets système tesseract-ocr-osd, -eng, -fra, -spa) | Orientation et langues d'OCR PDF | Apache-2.0 | Fichiers de données lus en lecture seule dans `/usr/share/tesseract-ocr/5/tessdata` ; jamais téléchargés ni empaquetés par PriveoPDF. Le `.deb` les recommande (osd, eng, fra) ou les suggère (spa). |
| libseccomp (paquet système libseccomp2) | Filtre des appels système des workers Linux | LGPL-2.1-only | Bibliothèque fournie et maintenue par la distribution, chargée dynamiquement depuis son chemin système ; aucune copie embarquée. Sources et licence : https://github.com/seccomp/libseccomp |
| cryptography 50.0.2 | Verification Ed25519 des manifestes de mise a jour | Apache-2.0 ou BSD-3-Clause | Version verrouillee apres CVE-2026-69247. Utilise uniquement des primitives auditees ; aucune cle privee n'est incluse. Embarque des composants natifs Rust/OpenSSL selon la wheel. |
| packaging 26.3 | Comparaison robuste des versions pour la verification de mises a jour | Apache-2.0 ou BSD-2-Clause | Version verrouillee dans `uv.lock`. Utilisee pour comparer la version locale aux tags GitHub Releases, sans traiter de document. |
| Pillow 13.0.0 | Images de pikepdf et de PriveoPDF | MIT-CMU | Version verrouillee ; correctifs PYSEC-2026-2253 à 2257 inclus depuis 12.3.0. |
| PySide6 6.11.3 | Meta-paquet des bindings Qt | Qt for Python Community Edition : LGPLv3/GPLv3 ; licence commerciale possible selon les droits obtenus | Le modele prepare s'appuie sur l'option LGPL pour les composants eligibles. |
| PySide6-Addons 6.11.3 | Modules additionnels, dont QtPdf et QtPdfWidgets | Licences propres aux modules Qt, dont LGPLv3 pour les modules utilises | Inventaire binaire et notices par module obligatoires avant distribution. |
| PySide6-Essentials 6.11.3 | QtCore, QtGui, QtWidgets et bindings essentiels | LGPLv3/GPLv3 ou licence commerciale selon le composant | Liaison dynamique et remplacement doivent etre prouves sur le payload reel. |
| Shiboken6 6.11.3 | Runtime des bindings Qt for Python | LGPLv3/GPLv3 ou licence commerciale | Sources couvertes par l'archive Qt for Python verrouillee. |
| pikepdf 10.17.0 | Manipulation structurelle PDF | MPL-2.0 | Utilisee via qpdf, sans parseur maison. La version de qpdf effectivement embarquee doit figurer dans le SBOM du payload. |

## Dossier Qt / LGPL 6.11.3

Le code applicatif importe QtCore, QtGui, QtWidgets et QtPdf.
QtTest reste une dependance de test uniquement. Aucun module GPL-only n'a ete
identifie dans cet inventaire source ; la distribution finale doit encore
inventorier toutes les bibliotheques et tous les plugins effectivement livres.

Les textes `licenses/LGPL-3.0.txt`, `licenses/GPL-3.0.txt` et
`licenses/QT-NOTICE.txt` accompagnent la preparation. Les sources officielles
Qt 6.11.3 et Qt for Python 6.11.3 sont verrouillees par nom, taille, URL et
SHA-256 dans `compliance/third_party_sources.lock.json`. Elles doivent etre
assemblees dans le bundle correspondant, verifiees octet par octet et rendues
disponibles avec tout executable qui embarque ces composants.

La licence Apache 2.0 de PriveoPDF, pour le code et les executables, ne remplace
ni ne limite ces droits tiers. Le dossier et les
gates sont decrits dans
`docs/legal/QT_LGPL_COMPLIANCE.md`.

## Dependances developpement

| Dependance | Usage | Licence connue | Note |
| --- | --- | --- | --- |
| bandit | Analyse statique de securite Python | Apache-2.0 | Controle CI ; absent du runtime utilisateur. |
| cyclonedx-bom | Generation du SBOM CycloneDX | Apache-2.0 | Controle CI et release ; absent du runtime utilisateur. |
| detect-secrets | Detection de secrets committes | Apache-2.0 | Controle CI base sur des empreintes, sans publier les valeurs detectees. |
| pip-audit | Audit des avis de vulnerabilite Python | Apache-2.0 | Controle CI ; interroge la base de vulnerabilites uniquement pendant la CI. |
| MkDocs | Construction statique du wiki communautaire | BSD-2-Clause | Dependence de developpement et de CI ; absente du runtime utilisateur. Les sources Markdown sont lues directement par l'aide hors ligne. |
| pyright | Verification statique des types | MIT | Controle de typage en developpement et CI. |
| pytest | Tests | MIT | Tests unitaires et integration. |
| ruff | Lint et formatage | MIT | Qualite locale. |

## Fixtures PDF de test

Ces fichiers sont uniquement utilises en developpement et en CI. Ils ne sont
pas inclus dans l'artefact applicatif. Les fichiers sont redistribues sans
modification binaire dans `tests/pdf_corpus/archives/` ; le detail de la
selection figure dans `tests/pdf_corpus/ATTRIBUTIONS.md` et `manifest.json`.

| Corpus | Usage | Licence | Revision amont |
| --- | --- | --- | --- |
| OpenPreserve Format Corpus | Malformations structurelles et cas produits par de vrais logiciels | CC0-1.0 | `366f068cec399d0cdfd61fa473de3ab6dc858098` |
| veraPDF Corpus | Cas PDF/A, PDF/UA, ISO 32000-1 et ISO 32000-2 | CC-BY-4.0 | `49de56cd987929932c9e4fbbbe67d052bf44ef83` |
| PDF Association PDF 2.0 examples | UTF-8, sauvegarde incrementale, offset de depart, annotations et intentions de sortie PDF 2.0 | CC-BY-SA-4.0 | `c20f2c17bfcc4baab7cfe62e70fae64caf14d5fa` |

## Composants natifs et outils systeme

Le constructeur `.deb` utilise PyInstaller 6.22.2 et ses dépendances de build
épinglées avec hashes dans `packaging/linux/build-requirements.txt`. Cet outil
reste réservé à la construction. Son exception à la GPL autorise les exécutables
distribués sous une licence propriétaire ; elle ne remplace aucune licence des
composants embarqués. Le bootloader amont n'est pas modifié. Référence officielle :
https://pyinstaller.org/en/v6.22.2/license.html.

Le candidat `.deb` conserve Qt sous forme de bibliothèques partagées remplaçables.
Le plugin optionnel Qt Virtual Keyboard et ses bibliothèques sont exclus de la
collecte PyInstaller : l'application ne les utilise pas et leur licence est
commerciale ou GPLv3, sans option LGPL. Le validateur de payload les refuse aussi.
Référence : https://doc.qt.io/qt-6/qtvirtualkeyboard-index.html.
La redistribution officielle reste soumise à l'inventaire effectif, aux notices
natives, aux sources Qt et au test de remplacement décrits dans la documentation
de conformité. Un candidat construit n'est pas une preuve de conformité finale.

L'archive source beta ne redistribue ni `bubblewrap`, ni `qpdf`, ni les bibliotheques Qt du
systeme. Les wheels verrouillees de PySide6, pikepdf et cryptography peuvent en revanche
embarquer leurs composants natifs conformement a leurs licences respectives. `bubblewrap`
est utilise, lorsqu'il est deja installe, comme defense supplementaire avec espace reseau
isole ; l'application conserve un repli documente vers un processus borne. ShellCheck est
un outil CI uniquement (GPL-3.0) et n'est pas inclus dans l'artefact utilisateur.

## Dependances a analyser avant apercu, rendu ou OCR

Ces dependances ne sont pas ajoutees au projet dans le MVP actuel. Toute adoption doit documenter la licence, la taille, le packaging et l'impact sur la promesse locale.

| Dependance | Usage envisage | Licence | Taille/packaging | Plateformes | Risques | Decision | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| PyMuPDF | Rendu, apercu, extraction visuelle | AGPL-3.0 ou licence commerciale Artifex, a analyser avant usage | A analyser | Linux, Windows, macOS a verifier | Obligations AGPL a analyser avant integration ; Apache-2.0 ne les remplace pas | A analyser | Ne pas ajouter pour apercu, miniatures, extraction visuelle ou OCR sans decision licence explicite. |
| pypdfium2 / PDFium | Rendu et miniatures | Apache-2.0 ou BSD-3-Clause pour pypdfium2/PDFium ; dependances tierces PDFium a documenter avant redistribution | A analyser | Linux, Windows, macOS a verifier | Packaging natif, taille et dependances tierces | A analyser | Option possible pour preview locale si packaging maitrise. |
| Poppler | Rendu PDF local | A confirmer avant usage | A analyser | Linux fort, autres plateformes a verifier | Dependances systeme et packaging | A analyser | Prudent pour Linux, plus lourd en multiplateforme. |
| Ghostscript | Conversion, optimisation, rendu | AGPL ou licence commerciale selon l'edition, a confirmer avant usage | Potentiellement lourd | Multiplateforme a verifier | Obligations AGPL ou licence commerciale a analyser avant integration | A analyser | Ne pas ajouter sans decision documentee. |
| OCRmyPDF | Pipeline OCR local | MPL-2.0 | Lourd | Linux fort, autres plateformes a verifier | Empile plusieurs dependances dont Tesseract/Ghostscript ; impose des processus enfants refuses par le worker | Ecarte (#292) | L'API C de Tesseract est utilisee directement ; voir les dependances runtime. |
| LibreOffice headless | Conversion documents bureautiques | MPL/LGPL selon composants | Tres lourd | Multiplateforme a verifier | Lancement lent, packaging, surface de securite | A analyser | Plus tard, hors MVP PDF organizer. |

Toute nouvelle dependance doit etre ajoutee ici avant d'elargir le perimetre.
