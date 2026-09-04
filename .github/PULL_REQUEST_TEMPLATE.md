# Résultat

> **Phase commentaires seulement.** Les Pull Requests de code externes ne sont
> pas acceptées et ne seront ni fusionnées, ni cherry-pickées, ni recopiées.
> Ce template est réservé aux mainteneurs et collaborateurs expressément
> autorisés du dépôt privé. Pour un retour public, utiliser les canaux décrits
> dans `CONTRIBUTING.md` sans envoyer de code.

Décrire le résultat unique obtenu et le problème résolu.

## Issue liée

Closes #

## Périmètre

- Inclus :
- Hors périmètre :

## Critères d’acceptation

- [ ]

## Fichiers modifiés

Lister les fichiers ou groupes de fichiers importants.

## Tests automatisés

Lister uniquement les commandes réellement exécutées et leur résultat exact.

## Validation manuelle

Décrire le scénario, l’environnement, le résultat et les preuves jointes.
Une PR limitée à la documentation, aux commentaires ou à un refactor interne
peut indiquer `Exemption sans effet observable` seulement si elle ne modifie ni
UI ou texte visible, ressource embarquée, comportement public, sortie fichier,
performance significative, configuration ou valeur par défaut, persistance,
permission, dépendance, build ou packaging. Énumérer les fichiers et fournir les
contrôles d'équivalence ; au moindre doute, tester l'artefact du SHA exact.

## Captures UI

Ajouter des captures si l’interface change, sinon indiquer `Sans objet`.

## Localisation et thèmes — obligatoire

Le validateur de contrat détecte dans le diff toute modification de l’interface,
des ressources visibles ou de la localisation. Dans ce cas, cocher les deux
premières cases et fournir des preuves ciblées. Sinon, cocher `Sans objet` et
en expliquer la raison sur la même ligne. La validation est refusée si la déclaration
contredit les fichiers modifiés ou si cette section est incomplète.

- [ ] <!-- localization-all-languages --> Tous les textes visibles ajoutés ou modifiés sont présents dans chaque langue disponible, sans clé manquante ni texte codé en dur.
- [ ] <!-- ui-all-presets --> Les vues affectées ont été validées dans chaque combinaison langue × preset sélectionnable déclaré dans `src/pdfmod/ui/theme/tokens.py`.
- [ ] <!-- localization-ui-not-applicable --> Sans objet, raison : <!-- expliquer pourquoi aucun texte visible ni aucune interface ne change -->

Preuves ciblées (tests, captures ou validation manuelle) :

- A_REMPLACER

## Wiki multilingue — obligatoire

Le contrat exige une décision explicite pour chaque PR. Si le wiki change, les pages
concernées doivent être mises à jour en français et en anglais au même chemin
logique. Sinon, cocher `Sans objet` et fournir une raison précise.

- [ ] <!-- wiki-all-languages --> Les pages pertinentes du wiki sont à jour en français et en anglais, avec les mêmes chemins relatifs.
- [ ] <!-- wiki-not-applicable --> Sans objet, raison : <!-- expliquer pourquoi le wiki utilisateur n'est pas concerné -->

Pages et preuves :

- A_REMPLACER

## Sécurité et vie privée — obligatoire

Chaque case doit être cochée. Si un point est sans objet, le cocher puis
l’expliquer dans la justification. La validation refuse une Pull Request incomplète.

- [ ] <!-- security-impact-reviewed --> J’ai analysé les nouveaux risques de sécurité, y compris PDF hostile, chemins, processus, mises à jour et supply chain.
- [ ] <!-- privacy-impact-reviewed --> J’ai analysé les données personnelles, chemins, métadonnées, journaux, caches, préférences et durées de conservation.
- [ ] <!-- network-impact-reviewed --> J’ai identifié toute nouvelle connexion réseau, télémétrie ou transmission ; aucune donnée documentaire ne part sans action explicite.
- [ ] <!-- tests-impact-reviewed --> J’ai ajouté ou adapté les tests de sécurité/confidentialité, ou justifié précisément leur absence.
- [ ] <!-- dependencies-impact-reviewed --> J’ai examiné toute dépendance, action CI, permission, lockfile et licence modifiés, ou confirmé qu’il n’y en a pas.
- [ ] <!-- docs-impact-reviewed --> J’ai mis à jour le modèle de menaces, l’inventaire des données et les documents concernés, ou justifié leur non-modification.

<!-- security-privacy-justification -->
A_REMPLACER : expliquer concrètement les impacts, les mesures prises, les tests
ajoutés et les risques résiduels. Minimum 40 caractères.

## Documentation

- [ ] `README.md` mis à jour car l’installation, les commandes, les fonctionnalités, la confidentialité, les dépendances, le packaging, la licence ou la roadmap visible changent.
- [ ] `README.md` inchangé, raison : <!-- expliquer pourquoi le README n’est pas concerné -->
- [ ] Pas de pricing ajouté au README.
- [ ] `CHANGELOG.md` mis à jour pour les changements notables.
- [ ] `THIRD_PARTY_NOTICES.md` mis à jour si une dépendance change.

## Checklist finale

- [ ] Le diff complet a été relu.
- [ ] Les controles locaux pertinents passent et, lorsque requise, la CI Linux manuelle correspond au SHA exact.
- [ ] Le scénario manuel pertinent a été exécuté, ou l'exemption sans effet observable est démontrée dans la section Validation manuelle.
- [ ] La logique PDF n’a pas été déplacée dans l’UI.
- [ ] Le design system `docs/UI_STYLE_GUIDE.md` est respecté.
- [ ] Aucun badge `100 % local` n’est dupliqué.
- [ ] Aucun secret, document utilisateur ou chemin personnel n’a été ajouté.
- [ ] Aucun suivi nécessaire n’est caché dans cette PR : il possède une Issue.
- [ ] Les risques résiduels sont indiqués et ne sont pas présentés comme corrigés.

