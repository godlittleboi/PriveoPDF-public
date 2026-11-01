# Bien démarrer

Le menu affiche **PriveoPDF** séparément de **PriveoPDF DEV** et de la bêta interne, avec le logo officiel inclus dans le paquet.

Si la colonne gauche est repliée, cliquez sur le logo ou sur la poignée à trois
traits pour retrouver le nom complet et le bloc de confidentialité.
DEV et le paquet public peuvent partager le thème et l'état replié de la colonne
sans exécuter la même version.

## Installation Linux

La première bêta `.deb` installable pour Ubuntu 24.04 / Linux Mint 22 (64 bits)
est encore en préparation. Les téléchargements officiels apparaîtront dans
[Releases](https://github.com/godlittleboi/PriveoPDF-public/releases), avec leurs
instructions de vérification. Les sources publiques et un paquet installable
sont deux distributions distinctes.

Pour un snapshot des sources publiques, suivez le guide d'installation inclus
sous `docs/INSTALL_DEV.md`. Depuis sa racine, lancez
`bash tools/launch_priveopdf.sh` après installation des dépendances. Les
installateurs de raccourcis DEV et outils de bêta internes n'en font pas partie.

Après installation d'un paquet validé, **PriveoPDF** apparaît dans le menu.
Dans une installation `.deb`, **Rechercher les mises à jour** consulte uniquement les Releases publiques de `PriveoPDF-public` après votre confirmation. Une nouvelle version détectée affiche ses notes et permet d'ouvrir directement sa Release exacte ; vous installez ensuite le nouveau `.deb` par-dessus l'ancien avec le gestionnaire de paquets. L'updater Git de développement ne s'applique jamais au paquet public.

La désinstallation du paquet conserve vos documents et préférences. Le lancement est refusé si l'isolation réseau obligatoire n'est pas disponible.

## Ouvrir un PDF

Déposez un fichier sur l’accueil ou choisissez **Visualiser un PDF**. Une fois
ouvert, le document apparaît aussi dans **Documents ouverts**.

Dans un outil, vous pouvez déposer un PDF n’importe où sur la fenêtre : il
devient la source de l’outil affiché. **Changer PDF** et **Ajouter PDF** ouvrent
directement le sélecteur de fichiers, dans le dernier dossier utilisé.

## Modifier un PDF

1. Choisissez l’outil correspondant à votre besoin.
2. Sélectionnez le ou les PDF locaux.
3. Réglez les pages ou options utiles.
4. Vérifiez la sortie proposée : un nouveau fichier, jamais un fichier existant.
5. Lancez l’opération. L’outil reste affiché avec le résultat : fichier créé,
   taille, nombre de pages quand il est connu et dossier.
6. Choisissez la suite : **Ouvrir le PDF**, **Ouvrir le dossier** ou
   **Continuer avec…**, qui ouvre un autre outil sur le fichier créé. Le
   fichier créé n’entre dans **Documents ouverts** que par l’une de ces
   actions ; sinon, l’outil suivant travaille toujours sur votre fichier.

Au clavier, dans un outil, **Ctrl+Entrée** lance l’opération lorsqu’elle est
possible et **Échap** revient en arrière. **Ctrl+K** ouvre la liste des outils.

L’accueil regroupe les outils par famille. Avec un PDF ouvert, il recommande
**Visualiser un PDF** ; avec 2 à 4 PDF lisibles, **Fusionner des PDF**. Un PDF
protégé par mot de passe est marqué **[protégé]** dans **Documents ouverts** dès
qu’un outil ou le lecteur a tenté de l’ouvrir ; l’accueil recommande alors
**Déverrouiller un PDF**.

Consultez [les seize outils disponibles](features/README.md) pour choisir le bon
parcours. En cas de blocage, ouvrez [Dépannage](troubleshooting.md).
