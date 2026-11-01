# Politique de sécurité

PriveoPDF est une application desktop locale en phase bêta. La sécurité repose sur des
bibliothèques PDF maintenues, une séparation UI/domaine/moteur et des sorties créées sans
modifier les sources. Le projet ne prétend pas être invulnérable.

## Versions prises en charge

Seule la dernière version publiée est destinée à recevoir des correctifs de sécurité. Une
branche de développement ou une archive non publiée ne constitue pas une version prise en
charge.

Clé OpenPGP de signature des versions : son empreinte complète sera inscrite ici avec la
première Release signée. Aucune n'est publiée à ce jour ; un fichier signé par une autre clé
n'est pas officiel.

## Signaler une vulnérabilité

Utiliser exclusivement le bouton **Report a vulnerability /
Signaler une vulnérabilité** de l'onglet **Security** du dépôt public propre. Il
ouvre un avis de sécurité privé visible seulement par le mainteneur et les
personnes autorisées. Ce canal est utilisé uniquement si son fonctionnement a
été vérifié ; la publication publique doit rester bloquée jusque-là.

Si ce bouton n'est pas affiché, ne pas ouvrir d'Issue, de Discussion ou de Pull
Request avec les détails. Le mainteneur doit rétablir le canal privé avant de
publier une nouvelle version. Utiliser
[le modèle de rapport](docs/security/VULNERABILITY_REPORT_TEMPLATE.md) dans
le rapport privé ; aucune adresse électronique n'est présumée.

Le rapport doit contenir :

- la version, le système et les étapes minimales de reproduction ;
- l'impact observé et les préconditions ;
- un PDF synthétique minimal si nécessaire, sans donnée réelle ou confidentielle ;
- aucun mot de passe, jeton, chemin personnel complet ou contenu documentaire sensible.

Le mainteneur cherchera à accuser réception, qualifier et coordonner une
correction selon la gravité, sans promettre un délai fixe. La publication
coordonnée est préférée après disponibilité du correctif ou d'une mitigation.

## Périmètre prioritaire

- corruption mémoire ou crash exploitable dans le traitement d'un PDF ;
- traversée de chemin, suivi de symlink, écrasement ou modification d'une source ;
- fuite de document, miniature, texte, métadonnée, mot de passe ou chemin local ;
- contournement de la vérification d'une mise à jour ou altération d'une release ;
- exécution de commande ou désérialisation non sûre ;
- déni de service durable par consommation CPU, mémoire, disque ou processus.

Les simples erreurs d'affichage sans impact de confidentialité, d'intégrité ou de
disponibilité peuvent être signalées comme bugs ordinaires.

## Principes de traitement

- Aucun document de démonstration confidentiel n'est conservé.
- Les détails publics sont différés si leur diffusion augmente le risque utilisateur.
- Un correctif de sécurité inclut des tests de non-régression et une analyse du risque
  résiduel.
- Les clés privées de signature ne résident jamais dans le dépôt ni dans l'application.
- L'heure UTC de prise de connaissance d'un incident potentiellement déclarable
  est conservée sans réécriture.
- À partir du 11 septembre 2026, les cas entrant dans l'article 14 du règlement
  (UE) 2024/2847 suivent les étapes conditionnelles des 24 h, 72 h et rapport
  final décrites dans le playbook ; ce dispositif ne prouve aucune conformité
  d'ensemble.

Voir [le triage des vulnérabilités](docs/security/VULNERABILITY_TRIAGE.md) et
[le playbook de signalement](docs/security/CRA_REPORTING_PLAYBOOK.md).

---

Potential vulnerabilities must use **Report a vulnerability** in the
[public repository's Security tab](https://github.com/godlittleboi/PriveoPDF-public/security).
If that private reporting channel is unavailable, do not publish details in an
Issue, Discussion or pull request. The maintainer must restore it before a new
publication. Never send a real user PDF, credential, private path, unnecessary
personal data or unreviewed log. No security email or postal address is implied
by this policy.
