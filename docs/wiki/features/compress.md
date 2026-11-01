# Compresser un PDF

## À quoi ça sert

Réduire la taille d'un PDF avec un réglage simple. Le gain dépend du document :
certains fichiers ne deviennent pas plus petits.

## Comment faire

Ouvrez **Compresser un PDF** depuis l'accueil ou depuis un PDF ouvert avec
**Outils**. Déposez un seul PDF, puis choisissez :

- **Sans perte de qualité**, sélectionné par défaut : optimise le fichier sans
  dégrader les images ni changer leur résolution.
- **Réduction renforcée** : optimise aussi certaines images avec un réglage fixe.
  **La qualité de certaines images peut être réduite.**

Un fichier de destination est proposé d'office dans le dossier du PDF, par
exemple `rapport_compressé.pdf` ; **CHANGER…** permet d'en choisir un autre.
Cliquez sur **COMPRESSER**. Vous pouvez annuler pendant le traitement.

## Résultat

Après un export, le résultat s'affiche sous le bouton : fichier créé, tailles
avant/après, gain et durée, avec **OUVRIR LE PDF**, **OUVRIR LE DOSSIER** et **CONTINUER AVEC…**. Vérifiez les pages, le texte et les images.
L'original reste inchangé et un fichier existant n'est jamais remplacé : la
destination suivante devient `-2`, `-3`, etc.

Si le résultat n'est pas strictement plus petit, aucun fichier n'est créé.
Vous pouvez changer de réglage ou de document.

Un message de contrôle d'intégrité indique que l'export a été bloqué, même si
le PDF peut s'ouvrir dans un lecteur. Un défaut mineur connu de l'index interne
est accepté après vérification du résultat ; les autres avertissements bloquent
l'export. L'original reste inchangé dans tous les cas.

## Limites

Les PDF chiffrés et les documents portant une signature numérique détectée sont
refusés. Un champ de signature vide reste accepté. Aucun gain minimal n'est
promis. La compression ne retire pas les métadonnées, ne répare pas les PDF et
ne crée pas de couche OCR. Elle ne propose ni lots ni réglages de résolution.
La conformité PDF/A ou PDF/UA n'est pas certifiée par cette opération.
