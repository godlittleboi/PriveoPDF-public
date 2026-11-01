# GitHub Discussions — canal unique de retours

Statut : GitHub Discussions est activé sur le dépôt public. Ce canal doit rester
accessible avant toute annonce de bêta ; le dépôt canonique privé n'utilise pas
Discussions comme canal utilisateur.

## Organisation initiale

GitHub fournit des catégories par défaut lors de l'activation de Discussions.
Pour la première bêta, il n'est pas nécessaire de créer une seconde plateforme
ni une taxonomie complexe :

| Catégorie GitHub | Usage PriveoPDF |
| --- | --- |
| Announcements | versions et informations confirmées du mainteneur |
| General | retours généraux, problèmes rencontrés et commentaires d'interface |
| Ideas | fonctions et améliorations souhaitées |
| Q&A | questions d'installation ou d'utilisation |
| Polls | sondages éventuels du mainteneur |
| Show and tell | démonstrations avec données artificielles ou librement partageables |

Un utilisateur normal est donc dirigé uniquement vers Discussions. Lorsqu'un
retour devient un bug reproductible ou une tâche suffisamment cadrée, le
mainteneur crée ou convertit l'élément de suivi correspondant en Issue. L'utilisateur
n'a pas à choisir lui-même entre plusieurs canaux.

La sécurité ne doit pas être une catégorie publique. Toute vulnérabilité
potentielle suit `SECURITY.md` et le canal confidentiel doit avoir été testé
avant toute annonce publique.

## Contrôles avant une annonce

- Vérifier que Discussions reste accessible sur le dépôt public.
- Vérifier : Les catégories par défaut sont présentes et permettent Questions, Idées et Retours.
- Vérifier : `Announcements` reste réservé aux mainteneurs selon le format GitHub.
- Vérifier : `CONTRIBUTING.md`, `FEEDBACK.md`, `SUPPORT.md` et `SECURITY.md` sont accessibles.
- Vérifier : Le signalement privé de vulnérabilité est activé et testé séparément.
- Vérifier : Aucun PDF utilisateur, secret ou vulnérabilité non corrigée n'est demandé dans Discussions.

Le publisher DEV peut activer Discussions automatiquement. Les éventuels renommages,
sections ou formulaires supplémentaires restent des améliorations de communauté et
ne bloquent pas la première bêta tant que le canal unique fonctionne réellement.
