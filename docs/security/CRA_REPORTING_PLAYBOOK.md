# Playbook de préparation aux signalements CRA

Statut : procédure interne préparatoire, à faire qualifier sur chaque cas. Elle
ne constitue ni une déclaration UE de conformité, ni un marquage CE, ni une
preuve de conformité d'ensemble au règlement (UE) 2024/2847.

## Entrée en application visée

L'article 14 du règlement (UE) 2024/2847 s'applique à partir du
**11 septembre 2026**. Le règlement s'applique principalement à partir du
11 décembre 2027. Avant toute notification, confirmer que PriveoPDF, l'opérateur,
la version, la mise à disposition et les faits entrent dans le champ applicable.

Sources officielles consultées le 7 août 2026 :

- règlement (UE) 2024/2847, articles 14, 16 et 71 :
  <https://eur-lex.europa.eu/eli/reg/2024/2847/oj> ;
- synthèse officielle de la Commission :
  <https://digital-strategy.ec.europa.eu/en/policies/cra-reporting> ;
- plateforme unique de signalement ENISA :
  <https://www.enisa.europa.eu/topics/product-security-and-certification/single-reporting-platform-srp>.

## Chronologie à déclencher si l'article 14 est applicable

| Échéance maximale | Vulnérabilité activement exploitée | Incident grave affectant la sécurité |
| --- | --- | --- |
| sans retard injustifié, au plus 24 h après prise de connaissance | alerte initiale | alerte initiale, avec indication d'une cause illicite/malveillante soupçonnée si connue |
| sans retard injustifié, au plus 72 h après prise de connaissance | notification principale : produit, nature générale, exploitation, corrections/mitigations et mesures utilisateur disponibles | notification principale : nature, évaluation initiale, corrections/mitigations et mesures utilisateur disponibles |
| rapport final | au plus 14 jours après disponibilité d'une mesure corrective ou de mitigation | dans le mois suivant la notification des 72 h |

Les notifications passent par la plateforme unique prévue à l'article 16 vers
le point électronique du CSIRT coordonnateur déterminé par l'établissement
principal dans l'Union, avec accès simultané d'ENISA. La plateforme et le point
exact doivent être vérifiés au moment du cas ; aucune URL de soumission n'est
codée en dur ici.

## Procédure

1. Ouvrir un dossier privé depuis `SECURITY_INCIDENT_TEMPLATE.md` et fixer
   l'heure UTC de prise de connaissance ; ne jamais réécrire cette heure.
2. Appliquer `VULNERABILITY_TRIAGE.md`, identifier les versions publiées, les
   États membres connus et les utilisateurs affectés.
3. Désigner le responsable opérationnel et obtenir sans délai une qualification
   juridique du champ, sans suspendre la préparation de l'alerte des 24 h.
4. Préparer l'alerte minimale avec faits vérifiés, inconnues et sensibilité ; ne
   pas joindre de document utilisateur ni de secret inutile.
5. Soumettre sur la plateforme applicable, conserver accusé, heure UTC, contenu
   exact, destinataires et classification dans le dossier privé.
6. Préparer la notification des 72 h et tout rapport intermédiaire demandé.
7. Corriger ou mitiger, tester, signer et distribuer par le processus de release
   sécurisé ; conserver la traçabilité version/SHA/SBOM.
8. Informer en temps utile les utilisateurs affectés et, lorsque approprié,
   tous les utilisateurs des mesures qu'ils peuvent appliquer.
9. Produire le rapport final dans le délai applicable et archiver les preuves
   selon une durée validée.

## Contrôles de communication

- aucune Issue, Discussion, PR, CI publique ou page du dépôt ne reçoit le détail d'une
  vulnérabilité non corrigée ;
- les messages utilisateurs sont exacts, actionnables et ne promettent pas un
  délai non maîtrisé ;
- la publication technique est coordonnée après disponibilité de la mesure,
  sauf instruction ou obligation contraire ;
- toute incertitude, retard, correction de notification ou demande d'autorité
  est horodatée et conservée.
