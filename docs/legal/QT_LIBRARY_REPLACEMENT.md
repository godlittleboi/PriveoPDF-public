# Remplacer les bibliothèques Qt couvertes par la LGPL

Statut : instructions préparatoires. Elles devront être validées sur chaque
exécutable effectivement qualifié. Aucun exécutable public n'est annoncé par ce
document.

## Inventaire propre à chaque distribution

L'archive officielle doit contenir `QT_RUNTIME_INVENTORY.json`. Ce fichier donne
la version, les modules, les bibliothèques et plugins Qt réellement livrés, leur
chemin relatif, le type de liaison et la preuve du test de remplacement. Il est
prioritaire sur tout exemple générique de cette page.

## Principe

PriveoPDF doit charger les composants Qt concernés comme bibliothèques partagées.
Le destinataire peut les remplacer par une version compatible qu'il a modifiée
ou reconstruite conformément à leur licence. La licence freeware PriveoPDF
n'interdit ni ce remplacement, ni la reliaison, ni l'ingénierie inverse
nécessaire au débogage de ces modifications.

1. Vérifier le checksum de l'archive reçue et conserver une copie intacte.
2. Lire `QT_RUNTIME_INVENTORY.json` et repérer l'ensemble des bibliothèques et
   plugins Qt, PySide6 et Shiboken concernés ; ne pas remplacer un seul fichier
   sans ses dépendances compatibles.
3. Récupérer ou reconstruire les composants depuis le bundle de sources
   correspondant fourni dans `third-party-sources/`.
4. Installer les bibliothèques reconstruites dans une copie de l'application ou
   les présenter au chargeur dynamique par un chemin de recherche temporaire
   propre à la plateforme.
5. Conserver les noms/ABI attendus par la version inventoriée, puis lancer la
   copie depuis un terminal pour observer les éventuelles erreurs du chargeur.

Sous Linux, une distribution portable peut charger ses fichiers `.so` depuis
son répertoire `app/`; une copie de ce répertoire peut recevoir les versions
reconstruites. Un chemin `LD_LIBRARY_PATH` temporaire peut aussi être utilisé si
la qualification de la release confirme ce mécanisme. Sous Windows, les DLL
compatibles peuvent être remplacées dans une copie du répertoire applicatif.
Sous macOS, les frameworks ou dylibs d'une copie du bundle peuvent être
remplacés sous réserve de respecter les chemins d'installation et les règles de
signature de la plateforme.

## Limites

Une bibliothèque incompatible peut empêcher le démarrage ou altérer le rendu.
La garantie et le support d'une version modifiée restent régis par les textes
applicables, sans réduire les droits LGPL. Les clés privées de signature ne sont
ni nécessaires au remplacement local, ni fournies.

Si l'inventaire, le test de remplacement, le bundle de sources ou les
informations propres à la plateforme manquent, la distribution n'est pas prête
et son gate doit échouer.
