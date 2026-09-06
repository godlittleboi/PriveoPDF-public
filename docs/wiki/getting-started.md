# Bien démarrer

Le menu affiche **PriveoPDF** séparément de **PriveoPDF DEV** et de la bêta interne, avec le logo officiel inclus dans le paquet.

## Installation Linux

L'installateur `.deb` pour Ubuntu 24.04 / Linux Mint 22 en 64 bits est qualifié pour la première bêta mais sa Release reste volontairement privée tant que l'ouverture aux testeurs n'est pas décidée. Les téléchargements officiels apparaîtront dans **Releases**, accompagnés de leur SHA-256.

Après installation d'un paquet validé, **PriveoPDF** apparaît dans le menu.
Dans une installation `.deb`, **Rechercher les mises à jour** consulte uniquement les Releases publiques de `PriveoPDF-public` après votre confirmation. Une nouvelle version détectée affiche ses notes et permet d'ouvrir directement sa Release exacte ; vous installez ensuite le nouveau `.deb` par-dessus l'ancien avec le gestionnaire de paquets. L'updater Git de développement ne s'applique jamais au paquet public.

La désinstallation du paquet conserve vos documents et préférences. Le lancement est refusé si l'isolation réseau obligatoire n'est pas disponible.

## Ouvrir un PDF

Déposez un fichier sur l’accueil ou choisissez **Visualiser un PDF**. Une fois
ouvert, le document apparaît aussi dans **Documents ouverts**.

## Modifier un PDF

1. Choisissez l’outil correspondant à votre besoin.
2. Sélectionnez le ou les PDF locaux.
3. Réglez les pages ou options utiles.
4. Choisissez un nouveau fichier de sortie.
5. Lancez l’opération et ouvrez le résultat.

Consultez [les neuf outils disponibles](features/README.md) pour choisir le bon
parcours. En cas de blocage, ouvrez [Dépannage](troubleshooting.md).
