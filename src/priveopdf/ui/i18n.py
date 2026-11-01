from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Locale = Literal["fr", "en"]

DEFAULT_LOCALE: Locale = "en"


@dataclass(frozen=True)
class LanguageOption:
    locale: Locale
    label_key: str


SUPPORTED_LANGUAGE_OPTIONS: tuple[LanguageOption, ...] = (
    LanguageOption("en", "language.en"),
    LanguageOption("fr", "language.fr"),
)
SUPPORTED_LOCALES: tuple[Locale, ...] = tuple(
    option.locale for option in SUPPORTED_LANGUAGE_OPTIONS
)

TRANSLATIONS: dict[Locale, dict[str, str]] = {
    "fr": {
        "tool.share_check.title": "VÉRIFIER AVANT PARTAGE",
        "tool.share_check.description": "Consulter les métadonnées, les retirer ou reconstruire le PDF en images.",
        "share.refresh": "Recalculer le bilan",
        "share.details": "Détails techniques du bilan",
        "share.details_toggle": "Détails techniques",
        "share.synthesis.none": "Rien à signaler dans les éléments contrôlés.",
        "share.synthesis.one": "1 élément à vérifier avant de partager ce PDF.",
        "share.synthesis.many": "{count} éléments à vérifier avant de partager ce PDF.",
        "share.column.item": "Élément",
        "share.column.value": "Dans ce PDF",
        "share.column.todo": "À faire",
        "share.element.metadata": "Métadonnées",
        "share.value.present": "Présentes",
        "share.value.none": "Aucune",
        "share.todo.metadata": "À effacer avec SUPPRIMER LES MÉTADONNÉES.",
        "share.todo.form": "À relire : SUPPRIMER LES MÉTADONNÉES n'y touche pas ; la photocopie peut être refusée si le formulaire ne peut pas être rendu fidèlement.",
        "share.synthesis.incomplete": "Bilan incomplet : consultez les détails techniques avant de partager.",
        "share.todo.kept": "À relire : SUPPRIMER LES MÉTADONNÉES n'y touche pas ; la photocopie ne garde que l'aspect visible des pages.",
        "share.todo.signed": "Aucune transformation possible : un PDF signé peut seulement être vérifié.",
        "share.todo.details": "Voir les détails techniques.",
        "share.todo.nothing": "Rien à faire.",
        "share.property.Title": "Titre",
        "share.property.Author": "Auteur",
        "share.property.Subject": "Sujet",
        "share.property.Keywords": "Mots-clés",
        "share.property.Creator": "Application d'origine",
        "share.property.Producer": "Producteur PDF",
        "share.property.CreationDate": "Date de création",
        "share.property.ModDate": "Date de modification",
        "share.preview": "Préparer l'aperçu de la photocopie",
        "share.metadata_action": "Supprimer les métadonnées",
        "share.photo_action": "Créer la photocopie",
        "share.photo_mode": "Photocopier le PDF — images uniquement",
        "share.fit": "Page entière",
        "share.mode": "Mode de nettoyage",
        "share.page": "Page de l'aperçu",
        "share.zoom": "Zoom de l'aperçu",
        "share.report": "Bilan avant partage",
        "share.inspecting": "Analyse du document…",
        "share.processing": "Préparation du traitement…",
        "share.progress": "Rendu et vérification : {done}/{total} étapes",
        "share.no_report": "Aucun bilan disponible. Recalculez l'analyse.",
        "share.complete": "Analyse complète dans le périmètre contrôlé. Info et XMP sont affichés séparément ; comparez leurs valeurs.",
        "share.partial": "Analyse incomplète : les comptes sont des minimums, pas une preuve d'absence.",
        "share.error.analysis_failed": "Le fichier n'a pas pu être lu comme un PDF : aucune analyse n'a été possible.",
        "share.error.analysis_incomplete": "L'analyse s'est arrêtée avant la fin : limite d'objets ou de durée atteinte, ou structure illisible.",
        "share.empty": "(valeur vide)",
        "share.truncated": "[affichage tronqué]",
        "share.no_extra": "Aucune propriété supplémentaire affichable.",
        "share.encrypted": "Ce PDF est protégé par mot de passe : utilisez Déverrouiller un PDF avant toute transformation.",
        "share.changed": "Le document a changé. Recalculez le bilan et préparez un nouvel aperçu.",
        "share.preview_ready": "Aperçu de la photocopie vérifiée. Parcourez les pages et zoomez pour vérifier la lisibilité avant de créer le résultat.",
        "share.metadata_done": "Métadonnées globales retirées et vérifiées. Les autres contenus sont conservés. Le bilan ci-dessus est recalculé sur le résultat.",
        "share.photo_done": "Pages reconstruites et vérifiées : images seules, sans texte sélectionnable ni anciennes structures cachées. Les informations visibles restent. Le bilan est recalculé sur le résultat.",
        "share.sizes": "Taille avant : {before} · après : {after}",
        "share.line": "{name} : {value}",
        "share.at_least": "≥ {count}",
        "share.zoom_value": "{value} %",
        "share.required.preview": "Préparez et vérifiez l'aperçu avant de créer la photocopie.",
        "share.standard_help": "Retire uniquement les métadonnées globales du document (titre, auteur, dates…). Le texte, les commentaires, formulaires, liens et pièces jointes sont conservés, avec leurs propres données. Le nom du fichier et les informations visibles ne sont pas anonymisés. Une conformité PDF/A ou PDF/UA n'est pas garantie après nettoyage.",
        "share.warning": "Cette opération transforme chaque page en image. Le texte ne sera plus sélectionnable ou recherchable ; les liens, formulaires et la structure d'accessibilité seront perdus. Les pièces jointes et commentaires non visibles ne seront pas conservés. Les noms, signatures dessinées, annotations et filigranes visibles peuvent rester : cette opération ne les anonymise pas. La netteté au fort zoom peut diminuer et le fichier grossir. Aucun OCR ni certification PDF/A ou PDF/UA. Vérifiez l'aperçu avant de continuer.",
        "share.replace": "Remplacer l'original par la version sans métadonnées globales ? La version précédente ne sera pas conservée. Une erreur ou une annulation avant publication conserve l'original.",
        "share.replace_photo": "Remplacer l'original par des images ? Le texte sélectionnable, les liens, formulaires et autres fonctions de l'original seront perdus. La version précédente ne sera pas conservée. Une erreur ou une annulation avant publication conserve l'original.",
        "share.state.absent": "Absent dans le périmètre contrôlé",
        "share.state.present": "Détecté",
        "share.state.unreadable": "Présent mais illisible",
        "share.state.limited": "Analyse limitée",
        "share.state.not_analyzed": "Non analysé",
        "share.category.comments": "Commentaires",
        "share.category.links": "Liens",
        "share.category.widgets": "Zones interactives de formulaire",
        "share.category.attachments": "Pièces jointes",
        "share.category.forms": "Champs de formulaire",
        "share.category.internal_navigation": "Navigation interne",
        "share.category.external_references": "Références externes",
        "share.category.active_actions": "Actions automatiques reconnues",
        "share.category.unknown_actions": "Actions automatiques non reconnues",
        "share.category.signatures": "Signatures apposées",
        "share.category.empty_signatures": "Champs de signature vides",
        "share.error.metadata_absent": "Aucune métadonnée globale à retirer : aucun fichier créé. La photocopie reste possible.",
        "share.error.share_signed": "Ce PDF porte une signature : inspection autorisée, transformation refusée.",
        "share.error.encrypted_pdf": "Ce PDF est protégé par mot de passe : utilisez Déverrouiller un PDF avant toute transformation.",
        "share.error.photocopy_limit": "Le PDF dépasse le budget de pages, pixels ou volume. Aucune réduction de qualité automatique.",
        "share.error.photocopy_unsupported": "Un formulaire ou contenu interactif ne peut pas être rendu fidèlement. Aucun résultat créé.",
        "share.error.user_cancelled": "Opération annulée.",
        "share.error.worker_timeout": "Le traitement a dépassé la durée autorisée. Aucun résultat publié.",
        "share.error.generic": "Le traitement ou sa vérification a échoué. Aucun résultat publié ; vérifiez aussi la destination.",
        "share.error.network_isolation_unavailable": "L'isolation requise est indisponible. Aucun traitement lancé.",
        "share.error.render_memory_unavailable": "La photocopie n'a pas pu fonctionner sous sa protection mémoire sur cet ordinateur. Aucun résultat publié. Le document a peut-être aussi dépassé sa limite de traitement : voir l'aide, Dépannage.",
        "share.error.render_memory_or_worker_failed": "La photocopie n'a pas pu fonctionner sous sa protection mémoire sur cet ordinateur. Aucun résultat publié. Le document a peut-être aussi dépassé sa limite de traitement : voir l'aide, Dépannage.",
        "share.error.photocopy_renderer_unavailable": "La photocopie n'a pas pu fonctionner sous sa protection mémoire sur cet ordinateur. Aucun résultat publié. Le document a peut-être aussi dépassé sa limite de traitement : voir l'aide, Dépannage.",
        "viewer.isolation_unavailable": "Isolation locale indisponible : aucun PDF ouvert.",
        "viewer.render_error": "Page indisponible. Rouvrez le PDF pour réessayer.",
        "viewer.accessible": "Lecteur PDF : navigation, zoom, sélection et recherche de texte",
        "viewer.search.open": "Rechercher dans le PDF (Ctrl+F)",
        "viewer.search.placeholder": "Rechercher dans le PDF",
        "viewer.search.previous": "Résultat précédent (Maj+Entrée)",
        "viewer.search.next": "Résultat suivant (Entrée)",
        "viewer.search.close": "Fermer la recherche (Échap)",
        "viewer.search.running": "Recherche…",
        "viewer.search.none": "Aucun résultat",
        "viewer.search.failed": "Recherche impossible dans ce document",
        "viewer.search.count": "{current} / {total}",
        "viewer.search.count_more": "{current} / {total}+",
        "viewer.loading": "Ouverture du PDF…",
        "password.error.replacement_refused": (
            "Ce fichier a changé ou ne peut pas être remplacé en sécurité. Réessayez sur une copie."
        ),
        "viewer.password_required": (
            "Ce PDF est protégé par un mot de passe. Déverrouillez-le pour afficher ses pages."
        ),
        "password.show": "Afficher",
        "password.hide": "Masquer",
        "password.show_accessible": "Afficher le mot de passe",
        "password.hide_accessible": "Masquer le mot de passe",
        "password.replace_title": "Remplacer le PDF actuel ?",
        "password.replace_confirmation": (
            "Remplacer « {name} » par le résultat ? La version précédente ne sera pas "
            "conservée. En cas de mauvais mot de passe, d'erreur ou d'annulation avant "
            "l'enregistrement, le fichier reste inchangé."
        ),
        "password.new": "Nouveau mot de passe",
        "password.known": "Mot de passe connu",
        "password.help_known": "Saisissez le mot de passe du PDF. Il ne sera pas mémorisé.",
        "password.confirm": "Confirmer le mot de passe",
        "password.help": (
            "Utilisez une phrase longue et gardez-la : PriveoPDF ne mémorise pas le mot de passe."
        ),
        "password.invalid": (
            "Mot de passe trop long ou contenant un caractère non accepté (127 octets UTF-8 "
            "maximum)."
        ),
        "password.mismatch": "Les deux mots de passe ne correspondent pas.",
        "password.required": "Saisissez le mot de passe.",
        "password.protect.action": "Protéger le PDF",
        "password.unlock_pdf.action": "Déverrouiller le PDF",
        "password.progress": "Traitement du PDF en cours…",
        "password.protected": (
            "Copie protégée créée. Ouvrez-la dans votre lecteur PDF et saisissez le mot de "
            "passe pour la vérifier."
        ),
        "password.unlocked": "Copie déverrouillée créée. Elle s'ouvre sans mot de passe.",
        "password.error.wrong_password": (
            "Mot de passe incorrect. Réessayez avec le mot de passe du PDF."
        ),
        "password.error.password_signed_pdf": (
            "Ce PDF porte une signature numérique. L'opération est refusée pour ne pas l'invalider."
        ),
        "password.error.password_integrity": (
            "L'intégrité du PDF n'a pas pu être vérifiée. Aucun fichier créé."
        ),
        "password.error.pdf_not_encrypted": (
            "Ce PDF n'est pas chiffré. Aucun déverrouillage nécessaire."
        ),
        "password.error.pdf_already_encrypted": (
            "Ce PDF est déjà chiffré. Déverrouillez une copie avant de la protéger avec un "
            "nouveau mot de passe."
        ),
        "password.error.invalid_pdf": "Ce PDF est invalide ou endommagé. Aucun fichier créé.",
        "password.error.dangerous_output": (
            "Cette destination existe déjà ou correspond à la source. Choisissez un nouveau nom."
        ),
        "password.error.user_cancelled": "Opération annulée. Aucun fichier créé.",
        "password.error.worker_timeout": "Le délai de traitement est dépassé. Aucun fichier créé.",
        "password.error.network_isolation_unavailable": (
            "L'isolation locale nécessaire au traitement est indisponible. Aucun fichier créé."
        ),
        "password.error.generic": (
            "L'opération a échoué. Vérifiez le document et choisissez une destination accessible."
        ),
        "compress.lossless": "Sans perte de qualité",
        "compress.strong": "Réduction renforcée",
        "compress.warning": "La qualité de certaines images peut être réduite.",
        "compress.action": "Compresser",
        "compress.progress": "Compression en cours…",
        "compress.no_gain": (
            "Aucune réduction obtenue avec ce réglage.\nAucun fichier créé. Votre "
            "original est inchangé."
        ),
        "compress.result": (
            "Avant : {before}\nAprès : {after}\nRéduction : {gain} % · Durée : {duration} s"
        ),
        "compress.error.encrypted_pdf": (
            "Ce PDF est chiffré. La compression des PDF chiffrés n'est pas prise en charge."
        ),
        "compress.error.compression_signed_pdf": (
            "Ce PDF porte une signature numérique. La compression est refusée pour "
            "ne pas l'invalider."
        ),
        "compress.error.compression_integrity": (
            "L'intégrité du PDF n'a pas pu être vérifiée. Aucun fichier créé."
        ),
        "compress.error.invalid_pdf": "Ce PDF est invalide ou endommagé. Aucun fichier créé.",
        "compress.error.dangerous_output": (
            "Cette destination existe déjà ou correspond à la source. Choisissez un nouveau nom."
        ),
        "compress.error.user_cancelled": "Compression annulée. Aucun fichier créé.",
        "compress.error.worker_timeout": "Le délai de traitement est dépassé. Aucun fichier créé.",
        "compress.error.network_isolation_unavailable": (
            "L'isolation locale nécessaire au traitement est indisponible. Aucun fichier créé."
        ),
        "compress.error.generic": (
            "La compression a échoué. Vérifiez le document et choisissez une "
            "destination accessible."
        ),
        "app.name": "PriveoPDF",
        "language.fr": "Français",
        "language.en": "English",
        "mode.light.action": "MODE CLAIR",
        "mode.dark.action": "MODE SOMBRE",
        "theme.system": "Automatique — suivre le système",
        "theme.dark_pro": "Sombre — Sobre",
        "theme.light_pro": "Clair — Sobre",
        "theme.dark_contrast": "Contraste élevé",
        "theme.dark_pixel": "Sombre — Pixel",
        "theme.light_pixel": "Clair — Pixel",
        "theme.visual_style.pro": "Sobre",
        "theme.visual_style.pixel": "Pixel",
        "no": "NON",
        "options": "Paramètres",
        "options.title": "PARAMÈTRES",
        "options.general": "GÉNÉRAL",
        "options.language": "LANGUE",
        "options.theme": "THÈME",
        "options.reduce_motion": "RÉDUIRE LES ANIMATIONS",
        "options.update_checks": "VÉRIFICATIONS AUTOMATIQUES DES MISES À JOUR",
        "options.check_updates_now": "VÉRIFIER MAINTENANT",
        "options.default_output_dir": "DOSSIER DE SORTIE PAR DÉFAUT",
        "options.default_output_dir.empty": "Aucun dossier par défaut",
        "options.output_behavior": "APRÈS TRAITEMENT",
        "options.after_job.none": "Ne rien ouvrir",
        "options.after_job.open_output_folder": "Ouvrir le dossier de sortie",
        "options.pdf_reading": "LECTURE PDF",
        "options.pdf_opening_mode": "MODE D'OUVERTURE PDF",
        "options.pdf_opening_mode.fit_page": "Ajuster page",
        "options.pdf_opening_mode.fit_width": "Ajuster largeur",
        "options.open_last_pdf_on_startup": "Ouvrir automatiquement le dernier PDF au démarrage",
        "beta.integration.window_title": "PriveoPDF Bêta — Essai local ({count} PR)",
        "beta.integration.heading": "CHECKLIST BÊTA",
        "beta.integration.identity": "{count} PR intégrées dans cette Bêta.",
        "beta.integration.help": "Observations dans cet assemblage local, pas une qualification individuelle ni GitHub. Cochez uniquement ce que vous avez vérifié.",
        "beta.individual.identity": "Essai local d'une PR à son SHA exact.",
        "beta.individual.help": "Checklist individuelle, distincte de l'assemblage et de la qualification GitHub.",
        "options.beta.current_local": "Essai local actuel : PR #{pr} · {sha}",
        "options.beta.current_integration": "Assemblage local actuel : {sha}",
        "options.beta.integration_item": "Historique · Assemblage {sha} · {date}",
        "options.beta.confirm.integration": "Fermer cette Beta et relancer cet assemblage local ({sha}) ?",
        "beta.integration.sha": "Version : {sha}",
        "beta.integration.progress": "{completed}/{total} cases cochées",
        "beta.integration.complete": "Checklist terminée : {completed}/{total}",
        "options.beta_versions": "VERSIONS BÊTA",
        "options.beta.current": "Version actuelle : PR #{pr} · {sha}",
        "options.beta.current_unavailable": "Version actuelle : provenance indisponible",
        "options.beta.help": (
            "Relancez une des dix versions Bêta précédentes conservées sur cet appareil. "
            "PriveoPDF stable et ses préférences ne sont jamais modifiés."
        ),
        "options.beta.previous": "VERSION PRÉCÉDENTE",
        "options.beta.none": "Aucune version précédente disponible",
        "options.beta.item": "Historique · PR #{pr} · {sha} · {date}",
        "options.beta.relaunch": "RELANCER CETTE VERSION",
        "options.beta.confirm.title": "Changer de version Bêta",
        "options.beta.confirm.message": (
            "Fermer cette Bêta et relancer la PR #{pr} au SHA {sha} ?"
        ),
        "options.beta.error.title": "Version Bêta indisponible",
        "options.beta.error.message": (
            "Cette version locale n'est plus complète ou sa provenance ne peut plus être "
            "vérifiée. Préparez à nouveau un essai local de cette PR."
        ),
        "options.beta.diagnostic": "DIAGNOSTIC BÊTA",
        "options.beta.diagnostic.help": (
            "Redémarrez explicitement une session privée pour reproduire un défaut, puis "
            "exportez un ZIP local à relire avant de le partager. Aucun PDF n'est inclus."
        ),
        "options.beta.diagnostic.status.none": "Aucune session de diagnostic disponible.",
        "options.beta.diagnostic.status.active": (
            "Session de diagnostic active : reproduisez le défaut puis exportez le rapport."
        ),
        "options.beta.diagnostic.status.available": (
            "Le rapport de la dernière session peut être exporté."
        ),
        "options.beta.diagnostic.status.abnormal": (
            "La dernière session s'est arrêtée anormalement. Son rapport est disponible."
        ),
        "options.beta.diagnostic.start": "REDÉMARRER EN SESSION DE DIAGNOSTIC",
        "options.beta.diagnostic.export": "EXPORTER LE DERNIER RAPPORT",
        "options.beta.diagnostic.zip_filter": "Archive ZIP (*.zip)",
        "options.beta.diagnostic.confirm.title": "Démarrer le diagnostic Bêta",
        "options.beta.diagnostic.confirm.message": (
            "Fermer cette fenêtre et redémarrer la même PR et le même SHA avec une "
            "journalisation locale privée et bornée ?"
        ),
        "options.beta.diagnostic.exported.title": "Rapport de diagnostic exporté",
        "options.beta.diagnostic.exported.message": (
            "Le rapport {name} a été créé. Relisez son contenu avant de le joindre."
        ),
        "options.beta.diagnostic.error.title": "Diagnostic indisponible",
        "options.beta.diagnostic.error.message": (
            "Le diagnostic n'a pas pu être démarré ou exporté. Vérifiez que cette Bêta "
            "provient toujours d'un artefact complet et choisissez un nouveau nom de fichier."
        ),
        "diagnostic.previous_crash.title": "Diagnostic Bêta disponible",
        "diagnostic.previous_crash.message": (
            "La dernière session de diagnostic s'est arrêtée anormalement. Son rapport "
            "reste disponible dans Options > Diagnostic Bêta."
        ),
        "options.privacy": "CONFIDENTIALITÉ LOCALE",
        "options.remember_open_documents": "MÉMORISER LES DOCUMENTS OUVERTS",
        "options.remember_open_documents.help": (
            "Désactivé par défaut. Si activé, PriveoPDF stocke localement les chemins, noms "
            "de sessions et la sélection, jamais le contenu des PDF. La réouverture au "
            "démarrage reste un réglage séparé."
        ),
        "options.clear_local_data": "EFFACER LES DONNÉES LOCALES",
        "options.clear_local_data.confirm.title": "Effacer les données locales",
        "options.clear_local_data.confirm.message": (
            "Supprimer les chemins de documents mémorisés, le dossier de sortie par défaut, "
            "le dernier dossier d'ouverture, l'historique du sélecteur de fichiers, la géométrie de fenêtre et le cache de mise à jour ? Les fichiers PDF source ne "
            "seront pas supprimés."
        ),
        "options.close": "FERMER",
        "options.apply": "APPLIQUER",
        "options.restart_required.title": "Redémarrage requis",
        "options.restart_required.message": (
            "La langue a été enregistrée. Redémarre PriveoPDF pour l'appliquer partout."
        ),
        "about.title": "À PROPOS",
        "about.tooltip": "À propos de PriveoPDF",
        "about.product_promise": "Traitement PDF local, sans upload.",
        "about.no_account": "Aucun compte. Aucun cloud.",
        "about.documents_stay": "Les documents restent sur cet appareil.",
        "about.license": "Code et exécutable officiel sous Apache 2.0. Vous pouvez les utiliser, les modifier et les redistribuer selon cette licence.",
        "about.third_party": "Les composants tiers conservent leurs propres licences.",
        "about.copyright": "Copyright © 2026 godlittleboi",
        "first_run.title": "ASSISTANT DE CONFIGURATION INITIALE",
        "first_run.subtitle": (
            "PriveoPDF traite les PDF sur cet appareil, sans dépendance cloud pour les "
            "fonctions locales."
        ),
        "first_run.language": "LANGUE",
        "first_run.start": "COMMENCER",
        "sidebar.collapse": "Réduire le panneau latéral",
        "sidebar.expand": "Afficher le panneau latéral",
        "sidebar.workspace": "DOCUMENTS OUVERTS",
        "sidebar.workspace.empty": "Aucun PDF ouvert",
        "sidebar.workspace.tooltip": "Documents ouverts",
        "workspace.use_with": "Utiliser avec...",
        "workspace.use_with.placeholder": "Choisir un outil",
        "workspace.new": "Nouvelle session locale",
        "workspace.new.compact": "+",
        "workspace.limit_reached": "Limite atteinte : {max_count} sessions locales maximum.",
        "workspace.rename": "Renommer",
        "workspace.card.tooltip": "Groupe de documents ouverts. Double-cliquez pour le renommer.",
        "workspace.delete": "Supprimer la session",
        "workspace.deleted": "Session supprimée. Les fichiers PDF n'ont pas été supprimés.",
        "workspace.delete.last.title": "Session locale",
        "workspace.delete.last.message": "La dernière session locale ne peut pas être supprimée.",
        "workspace.delete.confirm.title": "Supprimer la session",
        "workspace.delete.confirm.message": (
            "Supprimer « {name} » retire seulement ce conteneur de session. "
            "Les PDF restent sur le disque."
        ),
        "workspace.remove": "Retirer des documents ouverts",
        "workspace.removed": (
            "Retiré des documents ouverts. Le fichier source n'a pas été supprimé."
        ),
        "workspace.remove.busy.title": "Documents ouverts",
        "workspace.remove.busy.message": "Ce PDF est utilisé par un traitement local en cours. Attendez la fin du traitement avant de le retirer des documents ouverts.",
        "workspace.restore.missing": (
            "{count} fichier(s) récent(s) sont introuvables et ont été ignorés."
        ),
        "sidebar.workspace.compact": "Docs",
        "sidebar.workspace.compact_single": "Doc",
        "sidebar.workspace.show_tooltip": "Afficher les documents ouverts",
        "sidebar.options.compact": "Paramètres",
        "sidebar.community": "AIDE",
        "sidebar.community.compact": "Aide",
        "sidebar.community.tooltip": "Ouvrir le wiki installé, sans connexion.",
        "community.title": "Aide",
        "community.description": (
            "Consultez l'aide incluse avec cette version. Ces pages restent disponibles "
            "hors ligne et n'envoient aucune donnée."
        ),
        "community.page_label": "PAGE",
        "community.offline_copy": "COPIE INSTALLÉE — HORS LIGNE",
        "community.portal_note": (
            "Un futur site communautaire pourra proposer une copie à jour, des espaces "
            "de commentaires et un catalogue d'addons. Son ouverture restera une action "
            "réseau explicite."
        ),
        "community.unavailable": "# Page indisponible\n\nCette page manque dans l'installation.",
        "community.link.external_blocked": (
            "Lien externe bloqué : l'aide hors ligne n'ouvre aucune adresse réseau."
        ),
        "community.link.invalid": (
            "Lien refusé : ce chemin sort de l'aide installée ou n'est pas un fichier "
            "Markdown valide."
        ),
        "community.link.unavailable": "Page introuvable dans l'aide installée.",
        "sidebar.local.tooltip": (
            "PRIVACY BY DESIGN\nAucun compte. Aucun cloud. Les documents restent sur cet appareil."
        ),
        "nav.dashboard.compact": "Accueil",
        "nav.dashboard.tooltip": "Accueil",
        "pending.badge": "EN ATTENTE",
        "pending.local_message": "Cet outil n'est pas disponible dans cette version.",
        "local.badge": "PRIVACY BY DESIGN",
        "local.note": "Aucun compte. Aucun cloud. Les documents restent sur cet appareil.",
        "local.badge_unisolated": "NON ISOLÉ",
        "local.note_unisolated": "Mode développement : les traitements ne sont pas isolés du système. Ne l'utilisez pas pour de vrais documents.",
        "dashboard.tools.available": "OUTILS DISPONIBLES",
        "dashboard.open_files": "OUVRIR DES PDF",
        "dashboard.open_files.tooltip": "Choisir un ou plusieurs PDF sur cet appareil.",
        "dashboard.search.placeholder": "Rechercher parmi les outils disponibles",
        "dashboard.search.accessible": "Rechercher un outil disponible",
        "dashboard.planned.show": "VOIR LES FONCTIONS PRÉVUES",
        "dashboard.planned.show.tooltip": (
            "Afficher les fonctions prévues, qui ne sont pas encore utilisables."
        ),
        "dashboard.planned.hide": "MASQUER LES FONCTIONS PRÉVUES",
        "dashboard.planned.hide.tooltip": "Masquer la liste des fonctions prévues.",
        "dashboard.planned.intro": (
            "Ces fonctions ne sont pas encore utilisables. Les outils spécialisés ci-dessus "
            "restent la méthode normale et simple."
        ),
        "dashboard.planned.stage.planned": "prévu",
        "dashboard.planned.stage.later": "plus tard",
        "dashboard.planned.item": "{title} — {stage}. {description}",
        "dashboard.ready.single_title": "PDF PRÊT",
        "dashboard.ready.multi_title": "{count} PDF PRÊTS",
        "dashboard.ready.recommended_action": "ACTION RECOMMANDÉE",
        "dashboard.ready.selected_file": "sélectionné",
        "dashboard.ready.page_count_one": "1 page",
        "dashboard.ready.page_count_many": "{count} pages",
        "dashboard.ready.add_files": "AJOUTER PDF",
        "dashboard.ready.add_files.tooltip": "Ajouter un PDF local aux documents ouverts.",
        "dashboard.group.organize_pdf": "ORGANISER PDF",
        "dashboard.group.optimize_pdf": "OPTIMISER PDF",
        "dashboard.group.convert_to_pdf": "CONVERTIR VERS PDF",
        "dashboard.group.convert_from_pdf": "CONVERTIR DEPUIS PDF",
        "dashboard.group.edit_pdf": "MODIFIER PDF",
        "dashboard.group.security_pdf": "SÉCURITÉ PDF",
        "dashboard.group.intelligence_pdf": "INTELLIGENCE PDF",
        "dropzone.title": "DÉPOSEZ VOS FICHIERS PDF ICI",
        "dropzone.single_title": "DÉPOSEZ UN PDF ICI",
        "dropzone.subtitle": "ou",
        "dropzone.single_subtitle": "ou choisissez un fichier local",
        "dropzone.browse": "PARCOURIR L'APPAREIL",
        "dropzone.accepted": "{count} PDF ajouté(s) localement.",
        "dropzone.rejected": "Seuls les fichiers PDF sont acceptés.",
        "pdf_input.empty_single": "Déposez un PDF ici ou parcourez l'appareil",
        "pdf_input.empty_multi": "Déposez vos PDF ici ou parcourez l'appareil",
        "pdf_input.dialog_single": "Choisir un PDF",
        "pdf_input.dialog_multi": "Choisir des PDF",
        "pdf_input.change_pdf": "CHANGER PDF",
        "pdf_input.add_pdf": "AJOUTER PDF",
        "source.protected": "Ce PDF est protégé par mot de passe.",
        "source.protected_named": "« {name} » est protégé par mot de passe.",
        "source.invalid": "Ce PDF est illisible ou endommagé.",
        "source.invalid_named": "« {name} » est illisible ou endommagé.",
        "source.not_protected": "Ce PDF n'est pas protégé : rien à déverrouiller.",
        "source.unlock": "DÉVERROUILLER PDF",
        "source.checking": "Vérification du PDF…",
        "source.signed": "Ce PDF porte une signature numérique. L'opération la rendrait invalide : seule une copie sans signature peut être produite. L'original n'est pas modifié.",
        "source.signed_choice": "Produire une copie sans signature",
        "source.signed_help": "La copie ne contiendra plus la signature numérique de l'original. Une signature visible reste une simple image.",
        "source.signed_blocker": "Cochez « Produire une copie sans signature » pour continuer.",
        "workspace.document_not_added": "Ce PDF n'a pas pu être ajouté aux documents ouverts.",
        "nav.dashboard": "ACCUEIL",
        "tool.view.title": "VISUALISER UN PDF",
        "tool.view.description": "Ouvrir et lire un PDF local sans transformation.",
        "tool.merge.title": "FUSIONNER DES PDF",
        "tool.merge.description": "Assembler plusieurs PDF en un seul fichier.",
        "tool.split.title": "DIVISER UN PDF",
        "tool.split.description": "Créer plusieurs PDF : toutes les N pages, une page par fichier, par groupes ou par plages.",
        "tool.extract.title": "EXTRAIRE DES PAGES",
        "tool.extract.description": (
            "Créer un nouveau PDF avec les pages sélectionnées, dans l'ordre choisi."
        ),
        "tool.reorder.title": "RÉORGANISER DES PAGES",
        "tool.reorder.description": "Réordonner toutes les pages d'un PDF.",
        "tool.insert_pages.title": "INSÉRER DES PAGES",
        "tool.insert_pages.description": "Insérer les pages choisies d'un second PDF.",
        "tool.blank_page.title": "AJOUTER UNE PAGE BLANCHE",
        "tool.blank_page.description": (
            "Ajouter une page blanche configurable dans une copie du PDF."
        ),
        "tool.blank_page.subtitle": (
            "Choisissez le format, l'orientation et la position de la nouvelle page."
        ),
        "tool.insert_pages.subtitle": (
            "Choisissez deux PDF, les pages à importer et leur position dans le document."
        ),
        "tool.rotate.title": "FAIRE PIVOTER DES PAGES",
        "tool.rotate.description": "Appliquer une rotation locale à certaines pages.",
        "tool.remove.title": "SUPPRIMER DES PAGES",
        "tool.remove.description": "Créer un PDF sans les pages choisies.",
        "tool.compose_pdf.title": "COMPOSER UN PDF",
        "tool.compose_pdf.description": (
            "Combiner plusieurs opérations dans un même parcours avancé."
        ),
        "tool.scan_to_pdf.title": "SCANNER VERS PDF",
        "tool.scan_to_pdf.description": "Créer un PDF depuis un scanner local.",
        "tool.compress.title": "COMPRESSER UN PDF",
        "tool.compress.description": "Réduire le poids d'un PDF local.",
        "tool.repair_pdf.title": "RÉPARER PDF",
        "tool.repair_pdf.description": "Tenter de récupérer un PDF endommagé.",
        "tool.ocr_pdf.title": "RECONNAÎTRE LE TEXTE (OCR)",
        "tool.ocr_pdf.description": "Rendre un PDF scanné recherchable et sélectionnable.",
        "tool.jpg_to_pdf.title": "JPG VERS PDF",
        "tool.jpg_to_pdf.description": "Créer un PDF depuis des images JPG locales.",
        "tool.word_to_pdf.title": "DOC/DOCX/ODT VERS PDF",
        "tool.word_to_pdf.description": "Convertir un document texte local en PDF.",
        "tool.powerpoint_to_pdf.title": "PPT/PPTX/ODP VERS PDF",
        "tool.powerpoint_to_pdf.description": "Convertir une présentation locale en PDF.",
        "tool.excel_to_pdf.title": "XLS/XLSX/ODS VERS PDF",
        "tool.excel_to_pdf.description": "Convertir un tableur local en PDF.",
        "tool.html_to_pdf.title": "HTML VERS PDF",
        "tool.html_to_pdf.description": "Convertir une page HTML locale en PDF.",
        "tool.pdf_to_jpg.title": "PDF VERS JPG",
        "tool.pdf_to_jpg.description": "Exporter des pages PDF en images JPG locales.",
        "tool.pdf_to_word.title": "PDF VERS DOCX/ODT",
        "tool.pdf_to_word.description": ("Convertir un PDF local en document texte si possible."),
        "tool.pdf_to_powerpoint.title": "PDF VERS PPTX/ODP",
        "tool.pdf_to_powerpoint.description": "Convertir un PDF local en présentation si possible.",
        "tool.pdf_to_excel.title": "PDF VERS XLSX/ODS",
        "tool.pdf_to_excel.description": (
            "Extraire des tableaux vers un format tableur si possible."
        ),
        "tool.pdf_to_pdfa.title": "PDF VERS PDF/A",
        "tool.pdf_to_pdfa.description": "Préparer un PDF local pour l'archivage PDF/A.",
        "tool.page_numbers.title": "NUMÉROS DE PAGE",
        "tool.page_numbers.description": "Ajouter des numéros de page au PDF.",
        "tool.watermark.title": "FILIGRANER UN PDF",
        "tool.watermark.description": (
            "Écrire un texte visible sur chaque page (mention, destinataire, référence),"
            " intégré au contenu de la page et vérifié après écriture."
        ),
        "tool.crop.title": "RECADRER PDF",
        "tool.crop.description": "Recadrer les pages d'un PDF local.",
        "tool.edit_pdf.title": "MODIFIER PDF",
        "tool.edit_pdf.description": "Ajouter des éléments visuels simples au PDF.",
        "tool.pdf_forms.title": "FORMULAIRES PDF",
        "tool.pdf_forms.description": "Préparer ou remplir des champs de formulaire PDF.",
        "tool.unlock_pdf.title": "DÉVERROUILLER UN PDF",
        "tool.unlock_pdf.description": "Déverrouiller un PDF avec un mot de passe connu.",
        "tool.protect.title": "PROTÉGER UN PDF",
        "tool.protect.description": "Ajouter une protection par mot de passe.",
        "tool.sign_pdf.title": "SIGNER PDF",
        "tool.sign_pdf.description": (
            "Ajouter une signature visuelle ou préparer une future signature électronique."
        ),
        "tool.redact_pdf.title": "CAVIARDER UN PDF",
        "tool.redact_pdf.description": (
            "Noircir des zones et supprimer réellement ce qui se trouvait dessous : le PDF"
            " produit est une photocopie vérifiée, sans texte ni objet caché."
        ),
        "tool.compare_pdf.title": "COMPARER PDF",
        "tool.compare_pdf.description": "Comparer deux PDF locaux pour repérer les différences.",
        "tool.summarize_pdf_ai.title": "RÉSUMER PDF AVEC IA",
        "tool.summarize_pdf_ai.description": (
            "Piste IA hors dashboard tant que le local n'est pas qualifié."
        ),
        "tool.translate_pdf_ai.title": "TRADUIRE PDF",
        "tool.translate_pdf_ai.description": (
            "Piste IA hors dashboard tant que le local n'est pas qualifié."
        ),
        "tool.hidden.title": "OUTIL RETIRÉ DU CATALOGUE",
        "tool.hidden.description": (
            "Cet ancien outil n'est plus visible dans le catalogue principal."
        ),
        "tool_switcher.label": "Changer d'outil",
        "tool_switcher.button": "OUTILS",
        "tool_switcher.all": "Tous les outils",
        "viewer.previous": "PAGE PRÉCÉDENTE",
        "viewer.previous_short": "PRÉC.",
        "viewer.next": "PAGE SUIVANTE",
        "viewer.next_short": "SUIV.",
        "viewer.zoom_out": "ZOOM -",
        "viewer.zoom_in": "ZOOM +",
        "viewer.zoom_value.accessible": "Niveau de zoom",
        "viewer.zoom_value.tooltip": "Zoom actuel : {percent} %.",
        "viewer.fit_menu": "AJUSTER",
        "viewer.fit_menu.tooltip": "Choisir l'ajustement de la page",
        "viewer.fit_page": "AJUSTER PAGE",
        "viewer.fit_width": "AJUSTER LARGEUR",
        "viewer.no_pdf": "Aucun PDF ouvert dans les documents ouverts.",
        "viewer.loaded": "PDF chargé localement : {name}",
        "viewer.load_error": "Impossible d'ouvrir ce PDF en visualisation.",
        "viewer.page_status": "Page {page} / {total}",
        "viewer.page_number.accessible": "Aller à la page",
        "viewer.page_number.prefix": "Page ",
        "viewer.page_number.tooltip": "Saisissez un numéro de page de 1 à {total}.",
        "viewer.page_number.unavailable": "Ouvrez un PDF pour choisir une page.",
        "viewer.page_number.empty": "—",
        "button.back": "RETOUR",
        "button.home": "ACCUEIL",
        "button.remove": "RETIRER",
        "button.up": "MONTER",
        "button.down": "DESCENDRE",
        "button.duplicate_pages": "DUPLIQUER",
        "button.insert_pages": "INSÉRER LES PAGES",
        "button.blank_page": "AJOUTER LA PAGE BLANCHE",
        "blank.loading": "{name} — lecture des pages en cours...",
        "blank.ready": "{name} — {pages}",
        "blank.format.custom": "Personnalisé",
        "blank.label.format": "Format",
        "blank.label.width": "Largeur",
        "blank.label.height": "Hauteur",
        "blank.label.orientation": "Orientation",
        "blank.label.position": "Position",
        "blank.label.after_page": "Numéro de page",
        "blank.orientation.portrait": "Portrait",
        "blank.orientation.landscape": "Paysage",
        "blank.position.start": "Au début",
        "blank.position.after": "Après la page",
        "blank.position.end": "À la fin",
        "blank.effective": "Dimensions effectives : {width} x {height} mm",
        "blank.error.incomplete": "Choisissez un PDF valide et un fichier de sortie disponible.",
        "blank.progress": "Ajout local de la page blanche...",
        "blank.unit_mm": " mm",
        "button.choose_output": "CHOISIR SORTIE",
        "button.merge": "FUSIONNER LES PDF",
        "button.choose_folder": "CHOISIR DOSSIER",
        "button.clear": "EFFACER",
        "button.cancel": "Annuler",
        "update.action.check": "RECHERCHER DES MISES À JOUR",
        "update.action.checking": "RECHERCHE EN COURS...",
        "update.action.up_to_date": "LOGICIEL À JOUR",
        "update.action.available": "MISE À JOUR DISPONIBLE",
        "button.extract": "CRÉER LE NOUVEAU PDF",
        "button.remove_pages": "CRÉER LE PDF SANS CES PAGES",
        "button.rotate": "FAIRE PIVOTER LES PAGES",
        "button.rotate_left": "À GAUCHE",
        "button.rotate_right": "À DROITE",
        "rotation.accessible.left": "Faire pivoter d'un quart de tour à gauche",
        "rotation.accessible.right": "Faire pivoter d'un quart de tour à droite",
        "button.reorder": "RÉORGANISER LE PDF",
        "button.split": "DIVISER EN PLUSIEURS PDF",
        "label.page_ranges": "PLAGES DE PAGES",
        "label.page_order": "ORDRE DES PAGES",
        "label.rotation_angle": "ANGLE DE ROTATION",
        "label.rotation_angle_short": "ANGLE",
        "label.rotation_target_short": "CIBLE",
        "rotation.target.all": "Toutes les pages",
        "rotation.target.active": "Page active",
        "rotation.target.selected": "Pages sélectionnées",
        "rotation.preview_unavailable": "Aperçu indisponible",
        "rotation.preview_loading": "Chargement de l'aperçu…",
        "rotation.error.no_pdf": "Choisissez un PDF valide avant de lancer l'opération.",
        "rotation.error.no_output": "Choisissez un fichier de sortie.",
        "rotation.error.invalid_angle": "Angle non supporté. Utilisez 0, 90, 180 ou 270.",
        "rotation.error.no_pages": "Choisissez au moins une page à tourner.",
        "rotation.required.angle": "Tournez avec À GAUCHE ou À DROITE : 0° laisserait les pages inchangées.",
        "tool.action.shortcut": "Raccourci : Ctrl+Entrée. Échap revient en arrière.",
        "split.mode.label": "DÉCOUPER",
        "split.mode.groups": "Par groupes (glisser-déposer)",
        "split.mode.ranges": "Par plages",
        "split.required.ranges": "Saisissez les plages, une par fichier, par exemple 1-3,4-6.",
        "split.mode.every_n": "Toutes les N pages",
        "split.mode.single_pages": "Une page par fichier",
        "split.size.label": "Pages par fichier",
        "split.announce.one": "1 fichier sera créé : {names}",
        "split.announce.many": "{count} fichiers seront créés : {names}",
        "split.required.pages": "Un document d'une page ne peut pas être divisé.",
        "split.required.parts": "Ce découpage recopierait tout le document dans un seul fichier.",
        "split.required.free_names": "« {name} » existe déjà dans ce dossier : choisissez un autre dossier.",
        "merge.required.files": "Étape requise : ajoutez au moins deux PDF.",
        "merge.required.output": "Étape requise : choisissez le fichier de sortie.",
        "guidance.next.choose_output": "Étape suivante : choisir la sortie",
        "guidance.next.view_result": "Étape suivante : visualiser le résultat",
        "merge.status.running": "Fusion locale...",
        "merge.error.no_files": "Choisissez au moins deux PDF à fusionner.",
        "merge.error.no_output": "Choisissez un fichier de sortie avant de fusionner.",
        "merge.error.title": "Fusion impossible",
        "visual.source_pdf": "PDF SOURCE",
        "merge.row.pages_unknown": "Pages : …",
        "merge.row.remove": "Retirer {name} de la fusion (le fichier n'est pas supprimé)",
        "visual.advanced_mode": "MODE AVANCÉ",
        "visual.add_output_pdf": "+ Ajouter un PDF de sortie",
        "visual.output_limit": "{max_count} PDF de sortie maximum.",
        "visual.output_pdf_n": "PDF de sortie {index}",
        "visual.extracted_pdf": "Nouveau PDF",
        "visual.drop_split": "Glissez les pages ici dans l'ordre du PDF à créer.",
        "visual.drop_extract": "Cliquez ou glissez les pages à ajouter, puis réorganisez-les si nécessaire.",
        "visual.remove_from_output": "Retirer de cette sortie",
        "visual.error.no_pdf": "Choisissez un PDF valide avant de lancer l'opération.",
        "visual.error.no_output": "Choisissez un fichier de sortie.",
        "visual.error.no_output_dir": "Choisissez un dossier de sortie.",
        "visual.error.invalid_plan": "Choisissez des pages valides avant de lancer l'opération.",
        "visual.error.remove_all": "Impossible de supprimer toutes les pages.",
        "visual.required.split": "Glissez au moins une page dans un PDF de sortie.",
        "visual.required.extract": "Ajoutez au moins une page au nouveau PDF.",
        "visual.required.remove": "Cliquez sur les pages à supprimer.",
        "visual.required.ranges": "Corrigez les plages de pages.",
        "reorder.required.pages": "Ce document n'a qu'une page : rien à réorganiser.",
        "reorder.required.change": (
            "Changez l'ordre d'au moins une page : l'ordre actuel produirait une copie identique."
        ),
        "page.reorder.help": (
            "Exemple : 3,1,1,2,4-6. Chaque page source doit être présente au moins une fois ; "
            "répéter un numéro duplique cette page."
        ),
        "insert.primary.title": "1. PDF PRINCIPAL",
        "insert.primary.empty": "Choisissez le PDF qui recevra les nouvelles pages.",
        "insert.source.title": "2. PDF À INSÉRER",
        "insert.source.empty": "Choisissez un autre PDF puis sélectionnez ses pages.",
        "insert.document.loading": "{name} — lecture des pages en cours...",
        "insert.document.ready": "{name} — {pages}",
        "insert.position.title": "3. POSITION D'INSERTION",
        "insert.position.start": "Avant la première page",
        "insert.summary.empty": "Sélectionnez au moins une page du second PDF.",
        "insert.summary.start": "au début",
        "insert.summary.after": "après la page {page}",
        "insert.summary.ready": (
            "Page(s) {pages} du second PDF insérée(s) {position}. "
            "Le résultat contiendra {total} pages."
        ),
        "insert.progress": "Insertion locale...",
        "insert.success.message": "Les PDF sources sont inchangés.",
        "insert.error.primary": "Choisissez un PDF principal valide.",
        "insert.error.source": "Choisissez un second PDF valide.",
        "insert.error.same_file": "Choisissez deux fichiers PDF différents.",
        "insert.error.selection": "Sélectionnez au moins une page du second PDF.",
        "insert.error.position": "Choisissez une position d'insertion valide.",
        "insert.error.output": "Choisissez un fichier de sortie.",
        "job.success.file_created": "Fichier créé : {name}",
        "tool.required.source": "Ajoutez un PDF pour commencer.",
        "tool.required.output": "Choisissez un fichier de sortie.",
        "tool.required.valid_source": "Choisissez un autre PDF.",
        "job.success.files_created": "{count} fichiers créés",
        "job.success.details_folder": "dans {folder}",
        "job.error.generic": "Le traitement a échoué. Aucun fichier créé.",
        "job.error.detail": "Détail technique : {code}",
        "job.error.invalid_pdf": "Ce PDF est invalide ou endommagé. Choisissez un autre PDF.",
        "job.error.encrypted_pdf": "Ce PDF est protégé par mot de passe. Déverrouillez-le d'abord avec Déverrouiller un PDF.",
        "job.error.wrong_password": "Mot de passe incorrect. Vérifiez-le puis réessayez.",  # pragma: allowlist secret
        "job.error.input_path_error": "Fichier introuvable ou illisible. Choisissez un autre PDF.",
        "job.error.invalid_page_selection": "La sélection de pages est invalide. Corrigez-la.",
        "job.error.invalid_page_order": "L'ordre des pages est invalide. Corrigez-le.",
        "job.error.invalid_split_plan": "Le découpage demandé est invalide. Corrigez-le.",
        "job.error.unsupported_pdf_feature": (
            "Ce PDF utilise une fonction non prise en charge. Aucun fichier créé."
        ),
        "job.error.pdf_structure_too_complex": (
            "La structure de ce PDF est trop volumineuse pour cet outil. Aucun fichier créé."
        ),
        "job.error.output_write_error": "Impossible d'écrire le fichier de sortie. Choisissez un autre emplacement.",
        "job.error.dangerous_output": "Ce fichier de sortie existe déjà ou est une source. Choisissez un autre nom.",
        "job.error.user_cancelled": "Traitement annulé. Aucun fichier créé.",
        "job.error.worker_timeout": "Le délai de traitement est dépassé. Aucun fichier créé.",
        "job.error.network_isolation_unavailable": (
            "L'isolation de sécurité est indisponible sur ce système. Aucun document traité."
        ),
        "output.none_file": "Aucun fichier de sortie choisi",
        "output.none_dir": "Aucun dossier de sortie choisi",
        "output.panel.destination": "Destination du fichier",
        "output.panel.destination_dir": "Dossier de destination",
        "output.change": "CHANGER…",
        "output.replace_input": "Remplacer ce PDF",
        "output.copy_help": "Par défaut, une copie est créée : le PDF actuel reste inchangé.",
        "output.replace_help": (
            "Conserver le même fichier et le même nom. La version précédente sera remplacée "
            "après confirmation et réussite du traitement."
        ),
        "size.bytes": "{value}\u00a0octets",
        "size.kib": "{value}\u00a0Ko",
        "size.mib": "{value}\u00a0Mo",
        "size.gib": "{value}\u00a0Go",
        "output.dialog.file": "Choisir le fichier de sortie",
        "output.dialog.directory": "Choisir le dossier de sortie",
        "output.suffix.merge": "_fusionné",
        "output.suffix.remove": "_sans-pages",
        "output.suffix.extract": "_extrait",
        "output.suffix.reorder": "_réorganisé",
        "output.suffix.insert": "_avec-pages",
        "output.suffix.blank_page": "_avec-page-blanche",
        "output.suffix.rotate": "_tourné",
        "output.suffix.compress": "_compressé",
        "output.suffix.unlock_pdf": "_déverrouillé",
        "output.suffix.protect": "_protégé",
        "output.suffix.share_check": "_sans-métadonnées",
        "output.suffix.share_photo": "_photocopie",
        "output.suffix.ocr_pdf": "_recherchable",
        "output.suffix.redact_pdf": "_caviardé",
        "output.suffix.watermark": "_filigrané",
        "ocr.languages": "Langue du texte scanné",
        "ocr.languages_help": "Cochez la ou les langues du document (trois au plus). Seuls les modèles installés sur cet ordinateur sont proposés.",
        "ocr.languages_add": "Une langue ajoutée apparaît ici dès que son modèle est installé.",
        "ocr.add.button": "Ajouter une langue…",
        "ocr.add.title": "Ajouter une langue",
        "ocr.add.intro": "Choisissez une langue : le programme d'installation du système demande votre mot de passe, puis installe son modèle. PriveoPDF ne télécharge rien lui-même.",
        "ocr.add.search": "Rechercher une langue",
        "ocr.add.item": "{name} ({code})",
        "ocr.add.item_installed": "{name} ({code}) — installée",
        "ocr.add.install": "Installer",
        "ocr.add.copy": "Copier la commande",
        "ocr.add.choose": "Sélectionnez une langue dans la liste.",
        "ocr.add.already": "{name} est déjà installée.",
        "ocr.add.ready": "Ou, dans un terminal : {command}",
        "ocr.add.manual": "Aucun programme d'installation graphique trouvé. Dans un terminal : {command}",
        "ocr.add.waiting": "Installation en cours dans la fenêtre du système… Cette fenêtre se met à jour dès que le modèle est présent. Si rien ne s'ouvre, dans un terminal : {command}",
        "ocr.add.copied": "Commande copiée : {command}",
        "ocr.add.done": "{name} est installée et cochée. Vous pouvez fermer cette fenêtre.",
        "ocr.language_missing": "Modèle non installé. Dans un terminal : sudo apt install tesseract-ocr-{code}",
        "ocr.language_limit": "Trois langues au plus par traitement.",
        "ocr.help": "Seules les pages scannées sont traitées ; les pages qui contiennent déjà du texte restent telles quelles. Le texte reconnu est ajouté de façon invisible : l'aspect des pages ne change pas.",
        "ocr.required.models": "Aucun modèle OCR n'est installé. Dans un terminal : sudo apt install tesseract-ocr tesseract-ocr-fra",
        "ocr.required.language": "Cochez au moins une langue.",
        "ocr.action": "Reconnaître le texte",
        "redact.action": "Caviarder le PDF",
        "redact.areas.title": "Zones à noircir",
        "redact.areas.count": "Zones : {count}",
        "redact.areas.help": "Tracez un rectangle sur la page avec la souris. Tout ce qui se trouve dessous sera supprimé.",
        "redact.areas.remove_last": "Retirer la dernière zone",
        "redact.areas.clear": "Tout effacer",
        "redact.required.areas": "Tracez au moins une zone à noircir.",
        "redact.required.too_many": "Au plus {maximum} zones par document.",
        "redact.required.fresh": "Ce PDF a changé sur le disque depuis l'affichage des pages : rechargez-le avec Changer PDF.",
        "redact.status.ready": "Chaque page du PDF produit deviendra une image : le texte ne sera plus sélectionnable. Pour le rendre recherchable ensuite, utilisez Reconnaître le texte (OCR).",
        "redact.result": "Zones noircies : {areas}, sur {pages}. Vérifié après écriture : chaque page est une image et aucun texte ne subsiste.",
        "redact.error.redaction_integrity": "Le caviardage n'a pas pu être vérifié. Aucun fichier créé.",
        "redact.error.redaction_area_invalid": "Une zone à noircir est hors de sa page. Retirez-la et tracez-la de nouveau.",
        "redact.error.photocopy_limit": "Ce PDF est trop grand ou trop long pour le caviardage (500 pages au plus, format A2 au plus). Aucun fichier créé.",
        "redact.error.photocopy_unsupported": "Un formulaire ou contenu interactif ne peut pas être rendu fidèlement. Aucun fichier créé.",
        "redact.error.photocopy_integrity": "Le caviardage n'a pas pu être vérifié. Aucun fichier créé.",
        "redact.error.photocopy_renderer_unavailable": "Le caviardage n'a pas pu fonctionner sous sa protection mémoire sur cet ordinateur. Aucun fichier créé.",
        "redact.error.render_memory_unavailable": "Le caviardage n'a pas pu fonctionner sous sa protection mémoire sur cet ordinateur. Aucun fichier créé. Le document a peut-être aussi dépassé sa limite de traitement : voir l'aide, Dépannage.",
        "redact.error.render_memory_or_worker_failed": "Le caviardage n'a pas pu fonctionner sous sa protection mémoire sur cet ordinateur. Aucun fichier créé. Le document a peut-être aussi dépassé sa limite de traitement : voir l'aide, Dépannage.",
        "redact.error.share_signed": "Ce PDF porte une signature numérique : l'opération est refusée sans votre accord pour une copie sans signature. Aucun fichier créé.",
        "redact.error.share_integrity": "Le fichier a changé pendant le traitement. Aucun fichier créé.",
        "redact.error.generic": "Le caviardage ou sa vérification a échoué. Aucun fichier créé ; vérifiez aussi la destination.",
        "watermark.action": "Filigraner le PDF",
        "watermark.settings.title": "Filigrane",
        "watermark.text.label": "Texte",
        "watermark.text.placeholder": "Ex. : Copie remise à … — confidentiel",
        "watermark.text.help": "Jusqu'à 120 caractères, écrit sur chaque page. L'aperçu à gauche montre le résultat.",
        "watermark.layout.label": "Disposition",
        "watermark.layout.diagonal": "En diagonale, au centre",
        "watermark.layout.tiled": "Répété sur toute la page",
        "watermark.strength.label": "Intensité",
        "watermark.strength.light": "Légère",
        "watermark.strength.medium": "Moyenne",
        "watermark.strength.strong": "Forte",
        "watermark.required.text": "Saisissez le texte du filigrane.",
        "watermark.required.text_invalid": "Le texte contient un caractère non pris en charge : utilisez des lettres latines, des chiffres et la ponctuation courante.",
        "watermark.required.fresh": "Ce PDF a changé sur le disque depuis l'affichage des pages : rechargez-le avec Changer PDF.",
        "watermark.status.ready": "Le texte est écrit dans chaque page, pas en simple annotation : il ne s'enlève pas d'un clic. Il reste visible et sélectionnable ; une réédition volontaire du PDF peut toujours le retirer.",
        "watermark.result": "Filigrane vérifié sur {pages} : texte présent et visible sur chacune.",
        "watermark.error.watermark_integrity": "Le filigrane n'a pas pu être vérifié. Aucun fichier créé.",
        "watermark.error.watermark_text_invalid": "Le texte du filigrane est vide, trop long ou contient un caractère non pris en charge.",
        "watermark.error.watermark_limit": "Ce PDF dépasse les limites du filigrane (500 pages au plus). Aucun fichier créé.",
        "watermark.error.watermark_unsupported": "Une page de ce PDF a une taille ou une rotation non prise en charge par le filigrane. Aucun fichier créé.",
        "watermark.error.photocopy_limit": "Une page de ce PDF est trop grande pour la vérification du filigrane. Aucun fichier créé.",
        "watermark.error.photocopy_integrity": "Le filigrane n'a pas pu être vérifié. Aucun fichier créé.",
        "watermark.error.photocopy_renderer_unavailable": "La vérification du filigrane n'a pas pu fonctionner sous sa protection mémoire sur cet ordinateur. Aucun fichier créé.",
        "watermark.error.render_memory_unavailable": "La vérification du filigrane n'a pas pu fonctionner sous sa protection mémoire sur cet ordinateur. Aucun fichier créé. Le document a peut-être aussi dépassé sa limite de traitement : voir l'aide, Dépannage.",
        "watermark.error.render_memory_or_worker_failed": "La vérification du filigrane n'a pas pu fonctionner sous sa protection mémoire sur cet ordinateur. Aucun fichier créé. Le document a peut-être aussi dépassé sa limite de traitement : voir l'aide, Dépannage.",
        "watermark.error.share_signed": "Ce PDF porte une signature numérique : l'opération est refusée sans votre accord pour une copie sans signature. Aucun fichier créé.",
        "watermark.error.share_integrity": "Le fichier a changé pendant le traitement. Aucun fichier créé.",
        "watermark.error.generic": "Le filigrane ou sa vérification a échoué. Aucun fichier créé ; vérifiez aussi la destination.",
        "ocr.progress": "Reconnaissance du texte en cours…",
        "ocr.result": "Pages rendues recherchables : {recognized} · pages déjà textuelles, laissées intactes : {present} · pages sans texte détecté : {empty}",
        "ocr.result.selected": "Pages rendues recherchables : {recognized} · pages laissées intactes (déjà textuelles ou non choisies) : {present} · pages sans texte détecté : {empty}",
        "ocr.advanced": "OPTIONS AVANCÉES",
        "ocr.pages": "Pages à reconnaître",
        "ocr.pages_placeholder": "Toutes les pages scannées",
        "ocr.pages_help": "Laissez vide pour traiter toutes les pages scannées. Sinon, saisissez des numéros ou des plages, par exemple 1-50, 52 : les autres pages restent telles quelles. Un document de plus de 50 pages scannées se traite en plusieurs passes, sur la copie produite.",
        "ocr.required.pages": "Corrigez les pages à reconnaître, par exemple 1-50, 52.",
        "ocr.required.pages_bounds": "Les pages à reconnaître doivent être comprises entre 1 et {count}.",
        "ocr.required.pages_many": "Au plus {count} pages peuvent être choisies.",
        "ocr.error.ocr_already_searchable_selected": "Les pages choisies contiennent déjà du texte : rien à reconnaître. Aucun fichier créé.",
        "ocr.error.ocr_already_searchable": "Toutes les pages contiennent déjà du texte : ce PDF est déjà recherchable. Aucun fichier créé.",
        "ocr.error.ocr_no_eligible_pages": "Aucun texte n'a été reconnu sur les pages scannées. Vérifiez la langue cochée et la netteté du scan. Aucun fichier créé.",
        "ocr.error.ocr_limit": "Ce PDF dépasse les limites de l'OCR local : 500 pages au total, et au plus 50 pages scannées au format A4 (25 en A3 ; format maximal A2). Choisissez moins de pages dans Options avancées, ou divisez-le d'abord avec Diviser un PDF. Aucun fichier créé.",
        "ocr.error.ocr_unsupported": "Une page scannée porte une annotation, un formulaire ou un cadrage que l'OCR ne prend pas encore en charge. Aucun fichier créé.",
        "ocr.error.ocr_signed": "Ce PDF porte une signature numérique : l'opération est refusée sans votre accord pour une copie sans signature. Aucun fichier créé.",
        "ocr.error.ocr_model_missing": "Un modèle de langue coché n'est pas installé. Dans un terminal : sudo apt install tesseract-ocr-<code>. Aucun fichier créé.",
        "ocr.error.ocr_library_missing": "Le moteur OCR Tesseract n'est pas installé. Dans un terminal : sudo apt install tesseract-ocr. Aucun fichier créé.",
        "ocr.error.ocr_native_error": "La reconnaissance du texte a échoué. Aucun fichier créé.",
        "ocr.error.ocr_integrity": "La copie OCR n'a pas pu être vérifiée. Aucun fichier créé.",
        "ocr.error.worker_timeout": "L'OCR a dépassé trente minutes. Choisissez moins de pages dans Options avancées, ou divisez le document avec Diviser un PDF, puis relancez. Aucun fichier créé.",
        "ocr.error.ocr_renderer_unavailable": "L'OCR n'a pas pu fonctionner sous sa protection mémoire sur cet ordinateur. Aucun fichier créé. Le document a peut-être aussi dépassé sa limite de traitement : voir l'aide, Dépannage.",
        "ocr.error.render_memory_unavailable": "L'OCR n'a pas pu fonctionner sous sa protection mémoire sur cet ordinateur. Aucun fichier créé. Le document a peut-être aussi dépassé sa limite de traitement : voir l'aide, Dépannage.",
        "ocr.error.render_memory_or_worker_failed": "L'OCR n'a pas pu fonctionner sous sa protection mémoire sur cet ordinateur. Aucun fichier créé. Le document a peut-être aussi dépassé sa limite de traitement : voir l'aide, Dépannage.",
        "ocr.error.generic": "La reconnaissance ou sa vérification a échoué. Aucun fichier créé ; vérifiez aussi la destination.",
        "result.open_pdf": "OUVRIR LE PDF",
        "result.open_folder": "OUVRIR LE DOSSIER",
        "result.continue_with": "CONTINUER AVEC…",
        "job.running": "Traitement local en cours…",
        "input.none_pdf": "Aucun PDF choisi",
        "page_count.empty": "Pages : -",
        "page_count.loading": "Pages : lecture en cours...",
        "page_count.value": "Pages : {count}",
        "document.title": "DOCUMENT",
        "document.empty.title": "Aucun document ouvert",
        "document.empty.meta": "Ouvrez un PDF local pour passer en mode document.",
        "document.meta": "{pages} · {size}",
        "document.badge.selectable_text": "Texte détecté",
        "document.badge.selectable_text.tooltip": (
            "Texte extractible détecté localement sur un échantillon du PDF."
        ),
        "document.badge.probable_scan.compact": "Scan probable",
        "document.badge.probable_scan.tooltip": (
            "L'analyse locale indique que ce PDF ressemble probablement à un scan."
        ),
        "document.badge.protected_pdf": "PDF protégé",
        "document.badge.restricted_pdf": "Restrictions d'usage",
        "document.status.locked": "protégé",
        "document.badge.analysis_unavailable": "Analyse indisponible",
        "document.thumbnails": "PAGES",
        "document.info.title": "INFOS DOCUMENT",
        "document.source_intact": "L'original reste intact. Les outils créent une copie.",
        "document.layout.hide_pages": "Masquer pages",
        "document.layout.show_pages": "Afficher pages",
        "document.layout.hide_info": "Masquer les informations",
        "document.layout.show_info": "Afficher les informations",
        "document.layout.reading_mode": "Mode lecture — Ctrl+Maj+R",
        "document.layout.exit_reading": "Quitter le mode lecture — Ctrl+Maj+R",
        "document.layout.pages_compact": "PAGES",
        "document.layout.info_compact": "INFOS",
        "document.use_with.button": "UTILISER AVEC…",
        "document.use_with.tooltip": "Continuer avec un outil disponible pour ce PDF",
        "document.more.button": "PLUS",
        "document.more.tooltip": "Options de lecture et emplacement du fichier",
        "document.open_folder": "OUVRIR LE DOSSIER",
        "document.open_folder.tooltip": "Ouvrir le dossier qui contient le PDF source",
        "document.analysis.empty": "Analyse locale en attente.",
        "document.analysis.running": "Analyse locale légère en cours...",
        "document.analysis.unavailable": "Analyse indisponible pour ce fichier.",
        "document.scan_likelihood.unknown": "Type de document indéterminé.",
        "document.scan_likelihood.unknown.tooltip": (
            "L'analyse locale ne permet pas de déterminer si le PDF contient du texte extractible."
        ),
        "document.scan_likelihood.low": "Texte détecté sur l'échantillon analysé.",
        "document.scan_likelihood.medium": "Scan possible sur l'échantillon analysé.",
        "document.scan_likelihood.high": "Document scanné probable.",
        "document.size.unknown": "Taille inconnue",
        "document.initial.invalid": "Fichier ignoré : ouvrez un PDF local valide.",
        "document.initial.opened_first": (
            "Plusieurs PDF reçus : le premier est ouvert, les autres restent dans les "
            "documents ouverts."
        ),
        "thumbnails.load_more": "AFFICHER PLUS DE MINIATURES",
        "thumbnails.page_label": "Page {page}",
        "thumbnails.page_tooltip": "Page {page}",
        "thumbnails.loading": "chargement",
        "thumbnails.unavailable": "aperçu indisponible",
        "thumbnails.deleted": "SUPPRIMÉE",
        "thumbnails.assigned": "ASSIGNÉE",
        "update.manual.tooltip": (
            "Se connecter une fois au service de version pour rechercher une mise à jour. "
            "Aucun document ni chemin local n'est envoyé."
        ),
        "update.manual.tooltip.checking": "Recherche de mise à jour en cours.",
        "update.manual.tooltip.up_to_date": "Le logiciel est à jour. Cliquez pour vérifier de nouveau.",
        "update.manual.tooltip.update_available": "Cliquez pour afficher les ajouts et la page officielle de téléchargement.",
        "update.manual.tooltip.not_configured": (
            "Aucun canal public signé n'est encore configuré."
        ),
        "update.consent.title": "Connexion internet requise",
        "update.consent.message": (
            "Rechercher des mises à jour nécessite de se connecter à internet. "
            "Êtes-vous certain de vouloir continuer ?"
        ),
        "update.consent.privacy": (
            "Seule la version de PriveoPDF est vérifiée. Aucun document ni chemin local "
            "n'est envoyé."
        ),
        "update.consent.accept": "OUI, CONTINUER",
        "update.consent.decline": "NON",
        "update.progress.title": "Recherche de mise à jour",
        "update.progress.message": "Vérification sécurisée de la dernière version…",
        "update.result.up_to_date.title": "PriveoPDF est à jour",
        "update.result.failed.title": "Recherche impossible",
        "update.state.checking": "Vérification des mises à jour en cours.",
        "update.state.up_to_date": "Aucune mise à jour disponible.",
        "update.state.update_available": "Mise à jour disponible.",
        "update.state.not_verified": "Mises à jour non vérifiées.",
        "update.state.disabled": "Vérification des mises à jour désactivée.",
        "update.state.not_configured": "Vérification des mises à jour non configurée.",
        "update.state.offline": "Vérification des mises à jour indisponible hors ligne.",
        "update.state.private_or_not_found": "Source de mise à jour introuvable ou privée.",
        "update.state.no_release": "Aucune version compatible trouvée.",
        "update.state.rate_limited": "Vérification temporairement limitée.",
        "update.state.invalid_payload": "Réponse de mise à jour invalide.",
        "update.state.https_required": "Source refusée : HTTPS est obligatoire.",
        "update.state.host_not_allowed": "Hôte de mise à jour non autorisé.",
        "update.state.private_address": "Adresse réseau privée refusée.",
        "update.state.credentials_not_allowed": "Identifiants interdits dans l'URL.",
        "update.state.port_not_allowed": "Port réseau non autorisé.",
        "update.state.redirect_not_allowed": "Redirection de mise à jour refusée.",
        "update.state.response_too_large": "Réponse de mise à jour trop volumineuse.",
        "update.state.invalid_content_type": "Type de réponse de mise à jour invalide.",
        "update.state.invalid_signature": "Signature du manifeste invalide.",
        "update.state.unknown_signing_key": "Clé de signature du manifeste inconnue.",
        "update.state.signature_verifier_unavailable": "Vérification de signature indisponible.",
        "update.state.invalid_signing_key": "Clé de signature invalide.",
        "update.state.invalid_checksum": "Somme de contrôle de l'artefact invalide.",
        "update.state.checksum_mismatch": "Somme de contrôle de l'artefact incorrecte.",
        "update.state.downgrade_refused": "Version antérieure refusée.",
        "update.state.unsupported_manifest_schema": "Version du manifeste non prise en charge.",
        "update.state.source_updater_unavailable": (
            "Mise à jour intégrée indisponible : Git est introuvable."
        ),
        "update.state.source_checkout_invalid": (
            "La copie locale de PriveoPDF n'est pas reconnue."
        ),
        "update.state.source_checkout_dirty": (
            "La copie locale contient des modifications ou des fichiers non suivis."
        ),
        "update.state.source_checkout_wrong_branch": (
            "La mise à jour intégrée exige la branche main."
        ),
        "update.state.source_checkout_wrong_remote": (
            "Le dépôt distant n'est pas le dépôt PriveoPDF autorisé."
        ),
        "update.state.source_checkout_diverged": (
            "La copie locale et origin/main ont divergé. Mise à jour refusée."
        ),
        "update.state.source_fetch_failed": (
            "Impossible de joindre origin/main avec les identifiants Git configurés."
        ),
        "update.state.source_check_timeout": "La vérification Git a dépassé le délai autorisé.",
        "update.dialog.title": "Mise à jour disponible",
        "update.dialog.available": (
            "PriveoPDF {version} est disponible. Voulez-vous ouvrir la page officielle "
            "pour l'installer ?"
        ),
        "update.dialog.source.available": (
            "Une nouvelle révision de PriveoPDF est prête. Voulez-vous l'installer ? "
            "Le logiciel se fermera, lancera les tests automatiques de cette révision, "
            "puis redémarrera."
        ),
        "update.dialog.installed": "Version installée : {version}",
        "update.dialog.latest": "Dernière version : {version}",
        "update.dialog.source.installed": "Révision installée : {version}",
        "update.dialog.source.latest": "Révision disponible : {version}",
        "update.dialog.changes": "AJOUTS",
        "update.dialog.no_notes": "Aucune note courte disponible.",
        "update.dialog.install": "OUI, OUVRIR L'INSTALLATION",
        "update.dialog.source.install": "OUI, INSTALLER ET REDÉMARRER",
        "update.dialog.later": "PLUS TARD",
        "update.install.title": "Mise à jour de PriveoPDF",
        "update.install.waiting": "Fermeture sécurisée de PriveoPDF…",
        "update.install.waiting_other_instances": (
            "Fermez toutes les autres fenêtres PriveoPDF pour poursuivre la mise à jour…"
        ),
        "update.install.progress": (
            "Validation et installation de la mise à jour. Cette étape peut prendre "
            "plusieurs minutes."
        ),
        "update.install.phase.preflight": "Étape 1/8 — Vérification de l'installation locale",
        "update.install.phase.fetch": "Étape 2/8 — Téléchargement de la révision approuvée",
        "update.install.phase.prepare": "Étape 3/8 — Préparation de la copie de validation",
        "update.install.phase.dependencies": "Étape 4/8 — Vérification des dépendances",
        "update.install.phase.bootstrap": "Étape 5/8 — Vérification du démarrage",
        "update.install.phase.tests": "Étape 6/8 — Tests applicatifs en cours",
        "update.install.phase.install": "Étape 7/8 — Installation de la révision validée",
        "update.install.phase.finalize": "Étape 8/8 — Synchronisation finale",
        "update.install.phase.complete": "Mise à jour validée",
        "update.install.elapsed": "Temps écoulé : {duration}",
        "update.install.log.show": "AFFICHER LE JOURNAL",
        "update.install.log.hide": "MASQUER LE JOURNAL",
        "update.install.log.accessible": "Journal technique de la mise à jour",
        "update.install.success": "Mise à jour installée. Redémarrage de PriveoPDF…",
        "update.install.failed": (
            "La mise à jour a échoué. PriveoPDF n'a pas redémarré automatiquement ; "
            "consultez les détails avant de le rouvrir."
        ),
        "update.install.unsafe_failure": (
            "L'installation a échoué et l'état du logiciel ne peut pas être confirmé. "
            "Ne rouvrez pas PriveoPDF ; relancez la mise à jour depuis le terminal."
        ),
        "update.install.recovery": (
            "Récupération : fermez cette fenêtre, ouvrez un terminal dans le dossier "
            "PriveoPDF, puis exécutez : bash tools/update_from_github.sh {revision}"
        ),
        "update.install.launch_failed": "Le processus sécurisé de mise à jour n'a pas démarré.",
        "update.open_release.failed.title": "Page non ouverte",
        "update.open_release.failed": (
            "Votre navigateur n'a pas pu ouvrir la page de la nouvelle version. "
            "Copiez cette adresse dans votre navigateur :"
        ),
        "update.open_release.copy": "Copier l'adresse",
        "update.install.restart_failed": (
            "La mise à jour est terminée, mais PriveoPDF n'a pas pu redémarrer automatiquement."
        ),
        "update.install.reopen": "ROUVRIR PRIVEOPDF",
        "update.install.close": "FERMER",
    },
    "en": {
        "tool.share_check.title": "CHECK BEFORE SHARING",
        "tool.share_check.description": "Inspect metadata, remove it or rebuild the PDF as images.",
        "share.refresh": "Refresh inspection",
        "share.details": "Technical details of the inspection",
        "share.details_toggle": "Technical details",
        "share.synthesis.none": "Nothing to report in the checked items.",
        "share.synthesis.one": "1 item to check before sharing this PDF.",
        "share.synthesis.many": "{count} items to check before sharing this PDF.",
        "share.column.item": "Item",
        "share.column.value": "In this PDF",
        "share.column.todo": "To do",
        "share.element.metadata": "Metadata",
        "share.value.present": "Present",
        "share.value.none": "None",
        "share.todo.metadata": "Clear it with REMOVE METADATA.",
        "share.todo.form": "Review it: REMOVE METADATA leaves it as is; the photocopy may be refused if the form cannot be rendered faithfully.",
        "share.synthesis.incomplete": "Incomplete inspection: check the technical details before sharing.",
        "share.todo.kept": "Review it: REMOVE METADATA leaves it as is; the photocopy keeps only the visible look of the pages.",
        "share.todo.signed": "No transformation possible: a signed PDF can only be checked.",
        "share.todo.details": "See the technical details.",
        "share.todo.nothing": "Nothing to do.",
        "share.property.Title": "Title",
        "share.property.Author": "Author",
        "share.property.Subject": "Subject",
        "share.property.Keywords": "Keywords",
        "share.property.Creator": "Creating application",
        "share.property.Producer": "PDF producer",
        "share.property.CreationDate": "Creation date",
        "share.property.ModDate": "Modification date",
        "share.preview": "Prepare photocopy preview",
        "share.metadata_action": "Remove metadata",
        "share.photo_action": "Create photocopy",
        "share.photo_mode": "Photocopy PDF — images only",
        "share.fit": "Fit page",
        "share.mode": "Cleaning mode",
        "share.page": "Preview page",
        "share.zoom": "Preview zoom",
        "share.report": "Check before sharing",
        "share.inspecting": "Inspecting document…",
        "share.processing": "Preparing processing…",
        "share.progress": "Rendering and verification: {done}/{total} steps",
        "share.no_report": "No inspection available. Refresh the inspection.",
        "share.complete": "Inspection complete within the checked scope. Info and XMP are shown separately; compare their values.",
        "share.partial": "Incomplete inspection: counts are lower bounds, not evidence of absence.",
        "share.error.analysis_failed": "The file could not be read as a PDF: no inspection was possible.",
        "share.error.analysis_incomplete": "The inspection stopped before the end: object or time limit reached, or unreadable structure.",
        "share.empty": "(empty value)",
        "share.truncated": "[display truncated]",
        "share.no_extra": "No additional displayable properties.",
        "share.encrypted": "This PDF is password-protected: use Unlock PDF before transforming it.",
        "share.changed": "The document changed. Refresh inspection and prepare a new preview.",
        "share.preview_ready": "Verified photocopy preview. Browse pages and zoom to check readability before creating the result.",
        "share.metadata_done": "Global metadata removed and verified. Other contents are preserved. The inspection above is recalculated from the result.",
        "share.photo_done": "Pages rebuilt and verified: images only, without selectable text or original hidden structures. Visible information remains. Inspection is recalculated from the result.",
        "share.sizes": "Size before: {before} · after: {after}",
        "share.line": "{name}: {value}",
        "share.at_least": "≥ {count}",
        "share.zoom_value": "{value}%",
        "share.required.preview": "Prepare and check the preview before creating the photocopy.",
        "share.standard_help": "Removes only the document's global metadata (title, author, dates…). Text, comments, forms, links and attachments are preserved, including their own data. The filename and visible information are not anonymized. PDF/A or PDF/UA compliance is not guaranteed after cleaning.",
        "share.warning": "This operation turns each page into an image. Text will no longer be selectable or searchable; links, forms and accessibility structure will be lost. Attachments and non-visible comments will not be retained. Visible names, drawn signatures, annotations and watermarks may remain: this does not anonymize them. Sharpness at high zoom may decrease and the file may grow. No OCR or PDF/A or PDF/UA certification. Check the preview before continuing.",
        "share.replace": "Replace the original with the version without global metadata? The previous version will not be retained. An error or cancellation before publication preserves the original.",
        "share.replace_photo": "Replace the original with images? Selectable text, links, forms and other original features will be lost. The previous version will not be retained. An error or cancellation before publication preserves the original.",
        "share.state.absent": "Absent within checked scope",
        "share.state.present": "Detected",
        "share.state.unreadable": "Present but unreadable",
        "share.state.limited": "Limited inspection",
        "share.state.not_analyzed": "Not analyzed",
        "share.category.comments": "Comments",
        "share.category.links": "Links",
        "share.category.widgets": "Interactive form areas",
        "share.category.attachments": "Attachments",
        "share.category.forms": "Form fields",
        "share.category.internal_navigation": "Internal navigation",
        "share.category.external_references": "External references",
        "share.category.active_actions": "Recognized automatic actions",
        "share.category.unknown_actions": "Unrecognized automatic actions",
        "share.category.signatures": "Applied signatures",
        "share.category.empty_signatures": "Empty signature fields",
        "share.error.metadata_absent": "No global metadata to remove: no file created. Photocopy remains available.",
        "share.error.share_signed": "This PDF has a signature: inspection is allowed, transformation refused.",
        "share.error.encrypted_pdf": "This PDF is password-protected: use Unlock PDF before transforming it.",
        "share.error.photocopy_limit": "The PDF exceeds the page, pixel or volume budget. Quality is not automatically reduced.",
        "share.error.photocopy_unsupported": "A form or interactive content cannot be rendered faithfully. No result created.",
        "share.error.user_cancelled": "Operation cancelled.",
        "share.error.worker_timeout": "Processing exceeded the time limit. No result published.",
        "share.error.generic": "Processing or verification failed. No result published; also check the destination.",
        "share.error.network_isolation_unavailable": "Required isolation is unavailable. No processing started.",
        "share.error.render_memory_unavailable": "Photocopy could not run under its memory protection on this computer. No result published. The document may also have exceeded its processing limit: see Help, Troubleshooting.",
        "share.error.render_memory_or_worker_failed": "Photocopy could not run under its memory protection on this computer. No result published. The document may also have exceeded its processing limit: see Help, Troubleshooting.",
        "share.error.photocopy_renderer_unavailable": "Photocopy could not run under its memory protection on this computer. No result published. The document may also have exceeded its processing limit: see Help, Troubleshooting.",
        "viewer.isolation_unavailable": "Local isolation unavailable: no PDF opened.",
        "viewer.render_error": "Page unavailable. Reopen the PDF to retry.",
        "viewer.accessible": "PDF reader: navigation, zoom, text selection and search",
        "viewer.search.open": "Search in the PDF (Ctrl+F)",
        "viewer.search.placeholder": "Search in the PDF",
        "viewer.search.previous": "Previous result (Shift+Enter)",
        "viewer.search.next": "Next result (Enter)",
        "viewer.search.close": "Close search (Esc)",
        "viewer.search.running": "Searching…",
        "viewer.search.none": "No results",
        "viewer.search.failed": "Search failed in this document",
        "viewer.search.count": "{current} / {total}",
        "viewer.search.count_more": "{current} / {total}+",
        "viewer.loading": "Opening PDF…",
        "password.error.replacement_refused": (
            "This file changed or cannot be safely replaced. Try again with a copy."
        ),
        "viewer.password_required": "This PDF is password-protected. Unlock it to view its pages.",  # pragma: allowlist secret
        "password.show": "Show",
        "password.hide": "Hide",
        "password.show_accessible": "Show password",
        "password.hide_accessible": "Hide password",
        "password.replace_title": "Replace the current PDF?",
        "password.replace_confirmation": (
            "Replace “{name}” with the result? The previous version will not be kept. A wrong "
            "password, error or cancellation before saving leaves the file unchanged."
        ),
        "password.new": "New password",
        "password.known": "Known password",
        "password.help_known": "Enter the PDF password. It will not be remembered.",
        "password.confirm": "Confirm password",
        "password.help": (
            "Use a long passphrase and keep it: PriveoPDF does not remember the password."
        ),
        "password.invalid": (
            "Password too long or containing an unsupported character (maximum 127 UTF-8 bytes)."
        ),
        "password.mismatch": "The passwords do not match.",
        "password.required": "Enter the password.",
        "password.protect.action": "Protect PDF",
        "password.unlock_pdf.action": "Unlock PDF",
        "password.progress": "Processing PDF…",
        "password.protected": (
            "Protected copy created. Open it in your PDF reader and enter the password to check it."
        ),
        "password.unlocked": "Unlocked copy created. It opens without a password.",
        "password.error.wrong_password": "Incorrect password. Try again with the PDF password.",  # pragma: allowlist secret
        "password.error.password_signed_pdf": (
            "This PDF has a digital signature. The operation is refused to avoid invalidating it."
        ),
        "password.error.password_integrity": (
            "PDF integrity could not be verified. No file created."
        ),
        "password.error.pdf_not_encrypted": "This PDF is not encrypted. No unlocking is needed.",
        "password.error.pdf_already_encrypted": (
            "This PDF is already encrypted. Unlock a copy before protecting it with a new password."
        ),
        "password.error.invalid_pdf": "This PDF is invalid or damaged. No file created.",
        "password.error.dangerous_output": (
            "This destination already exists or matches the source. Choose a new name."
        ),
        "password.error.user_cancelled": "Operation cancelled. No file created.",
        "password.error.worker_timeout": "Processing timed out. No file created.",
        "password.error.network_isolation_unavailable": (
            "The local isolation required for processing is unavailable. No file created."
        ),
        "password.error.generic": (
            "The operation failed. Check the document and choose an accessible destination."
        ),
        "compress.lossless": "No loss of quality",
        "compress.strong": "Stronger reduction",
        "compress.warning": "The quality of some images may be reduced.",
        "compress.action": "Compress",
        "compress.progress": "Compressing…",
        "compress.no_gain": (
            "No reduction obtained with this setting.\nNo file created. Your original is unchanged."
        ),
        "compress.result": (
            "Before: {before}\nAfter: {after}\nReduction: {gain}% · Duration: {duration} s"
        ),
        "compress.error.encrypted_pdf": (
            "This PDF is encrypted. Compressing encrypted PDFs is not supported."
        ),
        "compress.error.compression_signed_pdf": (
            "This PDF contains a digital signature. Compression is refused to avoid"
            " invalidating it."
        ),
        "compress.error.compression_integrity": (
            "PDF integrity could not be verified. No file created."
        ),
        "compress.error.invalid_pdf": "This PDF is invalid or damaged. No file created.",
        "compress.error.dangerous_output": (
            "This destination already exists or is the source. Choose a new name."
        ),
        "compress.error.user_cancelled": "Compression cancelled. No file created.",
        "compress.error.worker_timeout": "The processing time limit was exceeded. No file created.",
        "compress.error.network_isolation_unavailable": (
            "The local isolation required for processing is unavailable. No file created."
        ),
        "compress.error.generic": (
            "Compression failed. Check the document and choose a writable destination."
        ),
        "app.name": "PriveoPDF",
        "language.fr": "Français",
        "language.en": "English",
        "mode.light.action": "LIGHT MODE",
        "mode.dark.action": "DARK MODE",
        "theme.system": "Automatic — follow system",
        "theme.dark_pro": "Dark — Clean",
        "theme.light_pro": "Light — Clean",
        "theme.dark_contrast": "High contrast",
        "theme.dark_pixel": "Dark — Pixel",
        "theme.light_pixel": "Light — Pixel",
        "theme.visual_style.pro": "Sober",
        "theme.visual_style.pixel": "Pixel",
        "no": "NO",
        "options": "Settings",
        "options.title": "SETTINGS",
        "options.general": "GENERAL",
        "options.language": "LANGUAGE",
        "options.theme": "THEME",
        "options.reduce_motion": "REDUCE MOTION",
        "options.update_checks": "AUTOMATIC UPDATE CHECKS",
        "options.check_updates_now": "CHECK NOW",
        "options.default_output_dir": "DEFAULT OUTPUT FOLDER",
        "options.default_output_dir.empty": "No default folder",
        "options.output_behavior": "AFTER PROCESSING",
        "options.after_job.none": "Open nothing",
        "options.after_job.open_output_folder": "Open output folder",
        "options.pdf_reading": "PDF READING",
        "options.pdf_opening_mode": "PDF OPENING MODE",
        "options.pdf_opening_mode.fit_page": "Fit page",
        "options.pdf_opening_mode.fit_width": "Fit width",
        "options.open_last_pdf_on_startup": "Open last PDF on startup",
        "beta.integration.window_title": "PriveoPDF Beta — Local trial ({count} PRs)",
        "beta.integration.heading": "BETA CHECKLIST",
        "beta.integration.identity": "{count} PRs integrated in this Beta.",
        "beta.integration.help": "Observations in this local assembly, not individual or GitHub qualification. Check only what you have verified.",
        "beta.individual.identity": "Local trial of one PR at its exact SHA.",
        "beta.individual.help": "Individual checklist, separate from assembly and GitHub qualification.",
        "options.beta.current_local": "Current local trial: PR #{pr} · {sha}",
        "options.beta.current_integration": "Current local assembly: {sha}",
        "options.beta.integration_item": "Historical · Assembly {sha} · {date}",
        "options.beta.confirm.integration": "Close this Beta and relaunch this local assembly ({sha})?",
        "beta.integration.sha": "Version: {sha}",
        "beta.integration.progress": "{completed}/{total} items checked",
        "beta.integration.complete": "Checklist complete: {completed}/{total}",
        "options.beta_versions": "BETA VERSIONS",
        "options.beta.current": "Current version: PR #{pr} · {sha}",
        "options.beta.current_unavailable": "Current version: provenance unavailable",
        "options.beta.help": (
            "Relaunch one of the ten previous Beta versions retained on this device. "
            "Stable PriveoPDF and its preferences are never changed."
        ),
        "options.beta.previous": "PREVIOUS VERSION",
        "options.beta.none": "No previous version available",
        "options.beta.item": "Historical · PR #{pr} · {sha} · {date}",
        "options.beta.relaunch": "RELAUNCH THIS VERSION",
        "options.beta.confirm.title": "Change Beta version",
        "options.beta.confirm.message": ("Close this Beta and relaunch PR #{pr} at SHA {sha}?"),
        "options.beta.error.title": "Beta version unavailable",
        "options.beta.error.message": (
            "This local version is incomplete or its provenance can no longer be verified. "
            "Prepare a local trial of this PR again."
        ),
        "options.beta.diagnostic": "BETA DIAGNOSTICS",
        "options.beta.diagnostic.help": (
            "Explicitly restart a private session to reproduce a defect, then export a local "
            "ZIP to review before sharing. No PDF file is included."
        ),
        "options.beta.diagnostic.status.none": "No diagnostic session is available.",
        "options.beta.diagnostic.status.active": (
            "Diagnostic session active: reproduce the defect, then export the report."
        ),
        "options.beta.diagnostic.status.available": ("The latest session report can be exported."),
        "options.beta.diagnostic.status.abnormal": (
            "The latest session ended abnormally. Its report is available."
        ),
        "options.beta.diagnostic.start": "RESTART IN DIAGNOSTIC SESSION",
        "options.beta.diagnostic.export": "EXPORT LATEST REPORT",
        "options.beta.diagnostic.zip_filter": "ZIP archive (*.zip)",
        "options.beta.diagnostic.confirm.title": "Start Beta diagnostics",
        "options.beta.diagnostic.confirm.message": (
            "Close this window and restart the same PR and SHA with private, bounded local logging?"
        ),
        "options.beta.diagnostic.exported.title": "Diagnostic report exported",
        "options.beta.diagnostic.exported.message": (
            "The report {name} was created. Review its contents before attaching it."
        ),
        "options.beta.diagnostic.error.title": "Diagnostics unavailable",
        "options.beta.diagnostic.error.message": (
            "The diagnostic session could not be started or exported. Check that this Beta "
            "still comes from a complete artifact and choose a new file name."
        ),
        "diagnostic.previous_crash.title": "Beta diagnostic available",
        "diagnostic.previous_crash.message": (
            "The latest diagnostic session ended abnormally. Its report remains available "
            "in Options > Beta diagnostics."
        ),
        "options.privacy": "LOCAL PRIVACY",
        "options.remember_open_documents": "REMEMBER OPEN DOCUMENTS",
        "options.remember_open_documents.help": (
            "Off by default. When enabled, PriveoPDF stores local paths, session names, and "
            "the selection, never PDF contents. Reopening at startup remains a separate setting."
        ),
        "options.clear_local_data": "CLEAR LOCAL DATA",
        "options.clear_local_data.confirm.title": "Clear local data",
        "options.clear_local_data.confirm.message": (
            "Remove remembered document paths, the default output folder, the last open "
            "folder, the file chooser history, window geometry, and the update cache? Source PDF "
            "files will not be deleted."
        ),
        "options.close": "CLOSE",
        "options.apply": "APPLY",
        "options.restart_required.title": "Restart required",
        "options.restart_required.message": (
            "The language setting was saved. Restart PriveoPDF to apply it everywhere."
        ),
        "about.title": "ABOUT",
        "about.tooltip": "About PriveoPDF",
        "about.product_promise": "Local PDF processing, no upload.",
        "about.no_account": "No account. No cloud.",
        "about.documents_stay": "Documents stay on this device.",
        "about.license": "Code and official executable under Apache 2.0. You may use, modify and redistribute them under this license.",
        "about.third_party": "Third-party components retain their own licenses.",
        "about.copyright": "Copyright © 2026 godlittleboi",
        "first_run.title": "INITIAL SETUP WIZARD",
        "first_run.subtitle": (
            "PriveoPDF processes PDFs on this device, with no cloud dependency for local features."
        ),
        "first_run.language": "LANGUAGE",
        "first_run.start": "START",
        "sidebar.collapse": "Collapse side panel",
        "sidebar.expand": "Expand side panel",
        "sidebar.workspace": "OPEN DOCUMENTS",
        "sidebar.workspace.empty": "No PDF open",
        "sidebar.workspace.tooltip": "Open documents",
        "workspace.use_with": "Use with...",
        "workspace.use_with.placeholder": "Choose a tool",
        "workspace.new": "New local session",
        "workspace.new.compact": "+",
        "workspace.limit_reached": "Limit reached: {max_count} local sessions maximum.",
        "workspace.rename": "Rename",
        "workspace.card.tooltip": "Group of open documents. Double-click to rename it.",
        "workspace.delete": "Delete session",
        "workspace.deleted": "Session deleted. PDF files were not deleted.",
        "workspace.delete.last.title": "Local session",
        "workspace.delete.last.message": "The last local session cannot be deleted.",
        "workspace.delete.confirm.title": "Delete session",
        "workspace.delete.confirm.message": (
            'Deleting "{name}" only removes this session container. The PDFs stay on disk.'
        ),
        "workspace.remove": "Remove from open documents",
        "workspace.removed": "Removed from open documents. The source file was not deleted.",
        "workspace.remove.busy.title": "Open documents",
        "workspace.remove.busy.message": (
            "This PDF is used by a local job in progress. Wait for the job to finish before "
            "removing it from open documents."
        ),
        "workspace.restore.missing": (
            "{count} recent file(s) could not be found and were ignored."
        ),
        "sidebar.workspace.compact": "Docs",
        "sidebar.workspace.compact_single": "Doc",
        "sidebar.workspace.show_tooltip": "Show open documents",
        "sidebar.options.compact": "Settings",
        "sidebar.community": "HELP",
        "sidebar.community.compact": "Help",
        "sidebar.community.tooltip": "Open the installed wiki without connecting.",
        "community.title": "Help",
        "community.description": (
            "Read the help bundled with this release. These pages remain available offline "
            "and send no data."
        ),
        "community.page_label": "PAGE",
        "community.offline_copy": "INSTALLED COPY — OFFLINE",
        "community.portal_note": (
            "A future community website may offer an updated copy, comment spaces, and an "
            "addon catalog. Opening it will remain an explicit network action."
        ),
        "community.unavailable": (
            "# Page unavailable\n\nThis page is missing from the installation."
        ),
        "community.link.external_blocked": (
            "External link blocked: offline Help does not open network addresses."
        ),
        "community.link.invalid": (
            "Link refused: this path leaves installed Help or is not a valid Markdown file."
        ),
        "community.link.unavailable": "Page not found in installed Help.",
        "sidebar.local.tooltip": (
            "PRIVACY BY DESIGN\nNo account. No cloud. Documents stay on this device."
        ),
        "nav.dashboard.compact": "Home",
        "nav.dashboard.tooltip": "Home",
        "pending.badge": "COMING SOON",
        "pending.local_message": "This tool is not available in this version.",
        "local.badge": "PRIVACY BY DESIGN",
        "local.note": "No account. No cloud. Documents stay on this device.",
        "local.badge_unisolated": "NOT ISOLATED",
        "local.note_unisolated": "Development mode: processing is not isolated from the system. Do not use it for real documents.",
        "dashboard.tools.available": "AVAILABLE TOOLS",
        "dashboard.open_files": "OPEN PDFS",
        "dashboard.open_files.tooltip": "Choose one or more PDFs on this device.",
        "dashboard.search.placeholder": "Search available tools",
        "dashboard.search.accessible": "Search for an available tool",
        "dashboard.planned.show": "VIEW PLANNED FEATURES",
        "dashboard.planned.show.tooltip": "Show planned features that are not available yet.",
        "dashboard.planned.hide": "HIDE PLANNED FEATURES",
        "dashboard.planned.hide.tooltip": "Hide the planned feature list.",
        "dashboard.planned.intro": (
            "These features are not available yet. The specialized tools above remain the "
            "normal, simple path."
        ),
        "dashboard.planned.stage.planned": "planned",
        "dashboard.planned.stage.later": "later",
        "dashboard.planned.item": "{title} — {stage}. {description}",
        "dashboard.ready.single_title": "PDF READY",
        "dashboard.ready.multi_title": "{count} PDFS READY",
        "dashboard.ready.recommended_action": "RECOMMENDED ACTION",
        "dashboard.ready.selected_file": "selected",
        "dashboard.ready.page_count_one": "1 page",
        "dashboard.ready.page_count_many": "{count} pages",
        "dashboard.ready.add_files": "ADD PDF",
        "dashboard.ready.add_files.tooltip": "Add a local PDF to open documents.",
        "dashboard.group.organize_pdf": "ORGANIZE PDF",
        "dashboard.group.optimize_pdf": "OPTIMIZE PDF",
        "dashboard.group.convert_to_pdf": "CONVERT TO PDF",
        "dashboard.group.convert_from_pdf": "CONVERT FROM PDF",
        "dashboard.group.edit_pdf": "EDIT PDF",
        "dashboard.group.security_pdf": "PDF SECURITY",
        "dashboard.group.intelligence_pdf": "PDF INTELLIGENCE",
        "dropzone.title": "DROP YOUR PDF FILES HERE",
        "dropzone.single_title": "DROP A PDF HERE",
        "dropzone.subtitle": "or",
        "dropzone.single_subtitle": "or choose a local file",
        "dropzone.browse": "BROWSE DEVICE",
        "dropzone.accepted": "{count} PDF added locally.",
        "dropzone.rejected": "Only PDF files are accepted.",
        "pdf_input.empty_single": "Drop a PDF here or browse this device",
        "pdf_input.empty_multi": "Drop your PDFs here or browse this device",
        "pdf_input.dialog_single": "Choose a PDF",
        "pdf_input.dialog_multi": "Choose PDFs",
        "pdf_input.change_pdf": "CHANGE PDF",
        "pdf_input.add_pdf": "ADD PDF",
        "source.protected": "This PDF is password-protected.",
        "source.protected_named": "“{name}” is password-protected.",
        "source.invalid": "This PDF is unreadable or damaged.",
        "source.invalid_named": "“{name}” is unreadable or damaged.",
        "source.not_protected": "This PDF is not protected: nothing to unlock.",
        "source.unlock": "UNLOCK PDF",
        "source.checking": "Checking the PDF…",
        "source.signed": "This PDF carries a digital signature. The operation would invalidate it: only a copy without the signature can be produced. The original is not modified.",
        "source.signed_choice": "Produce a copy without the signature",
        "source.signed_help": "The copy will no longer carry the original's digital signature. A visible signature remains a plain image.",
        "source.signed_blocker": "Tick “Produce a copy without the signature” to continue.",
        "workspace.document_not_added": "This PDF could not be added to the open documents.",
        "nav.dashboard": "HOME",
        "tool.view.title": "VIEW PDF",
        "tool.view.description": "Open and read a local PDF without transforming it.",
        "tool.merge.title": "MERGE PDF",
        "tool.merge.description": "Assemble several PDFs into one file.",
        "tool.split.title": "SPLIT PDF",
        "tool.split.description": "Create several PDFs: every N pages, one page per file, by groups, or by ranges.",
        "tool.extract.title": "EXTRACT PAGES",
        "tool.extract.description": "Create a new PDF with selected pages in the chosen order.",
        "tool.reorder.title": "REORDER PAGES",
        "tool.reorder.description": "Reorder every page in a PDF.",
        "tool.insert_pages.title": "INSERT PAGES",
        "tool.insert_pages.description": "Insert selected pages from a second PDF.",
        "tool.blank_page.title": "ADD A BLANK PAGE",
        "tool.blank_page.description": "Add a configurable blank page to a copy of the PDF.",
        "tool.blank_page.subtitle": "Choose the new page size, orientation, and position.",
        "tool.insert_pages.subtitle": (
            "Choose two PDFs, the pages to import, and their position in the document."
        ),
        "tool.rotate.title": "ROTATE PAGES",
        "tool.rotate.description": "Apply local rotation to selected pages.",
        "tool.remove.title": "REMOVE PAGES",
        "tool.remove.description": "Create a PDF without selected pages.",
        "tool.compose_pdf.title": "COMPOSE A PDF",
        "tool.compose_pdf.description": ("Combine several operations in one advanced workflow."),
        "tool.scan_to_pdf.title": "SCAN TO PDF",
        "tool.scan_to_pdf.description": "Create a PDF from a local scanner.",
        "tool.compress.title": "COMPRESS PDF",
        "tool.compress.description": "Reduce the size of a local PDF.",
        "tool.repair_pdf.title": "REPAIR PDF",
        "tool.repair_pdf.description": "Try to recover a damaged PDF.",
        "tool.ocr_pdf.title": "RECOGNIZE TEXT (OCR)",
        "tool.ocr_pdf.description": "Make a scanned PDF searchable and selectable.",
        "tool.jpg_to_pdf.title": "JPG TO PDF",
        "tool.jpg_to_pdf.description": "Create a PDF from local JPG images.",
        "tool.word_to_pdf.title": "DOC/DOCX/ODT TO PDF",
        "tool.word_to_pdf.description": "Convert a local text document to PDF.",
        "tool.powerpoint_to_pdf.title": "PPT/PPTX/ODP TO PDF",
        "tool.powerpoint_to_pdf.description": "Convert a local presentation to PDF.",
        "tool.excel_to_pdf.title": "XLS/XLSX/ODS TO PDF",
        "tool.excel_to_pdf.description": "Convert a local spreadsheet to PDF.",
        "tool.html_to_pdf.title": "HTML TO PDF",
        "tool.html_to_pdf.description": "Convert a local HTML page to PDF.",
        "tool.pdf_to_jpg.title": "PDF TO JPG",
        "tool.pdf_to_jpg.description": "Export PDF pages as local JPG images.",
        "tool.pdf_to_word.title": "PDF TO DOCX/ODT",
        "tool.pdf_to_word.description": "Convert a local PDF to a text document when possible.",
        "tool.pdf_to_powerpoint.title": "PDF TO PPTX/ODP",
        "tool.pdf_to_powerpoint.description": (
            "Convert a local PDF to a presentation when possible."
        ),
        "tool.pdf_to_excel.title": "PDF TO XLSX/ODS",
        "tool.pdf_to_excel.description": "Extract tables to a spreadsheet format when possible.",
        "tool.pdf_to_pdfa.title": "PDF TO PDF/A",
        "tool.pdf_to_pdfa.description": "Prepare a local PDF for PDF/A archiving.",
        "tool.page_numbers.title": "PAGE NUMBERS",
        "tool.page_numbers.description": "Add page numbers to the PDF.",
        "tool.watermark.title": "WATERMARK PDF",
        "tool.watermark.description": (
            "Write a visible text on every page (notice, recipient, reference), built into"
            " the page content and verified after writing."
        ),
        "tool.crop.title": "CROP PDF",
        "tool.crop.description": "Crop pages in a local PDF.",
        "tool.edit_pdf.title": "EDIT PDF",
        "tool.edit_pdf.description": "Add simple visible elements to the PDF.",
        "tool.pdf_forms.title": "PDF FORMS",
        "tool.pdf_forms.description": "Prepare or fill PDF form fields.",
        "tool.unlock_pdf.title": "UNLOCK PDF",
        "tool.unlock_pdf.description": "Unlock a PDF with a known password.",
        "tool.protect.title": "PROTECT PDF",
        "tool.protect.description": "Add password protection.",
        "tool.sign_pdf.title": "SIGN PDF",
        "tool.sign_pdf.description": (
            "Add a visual signature or prepare future e-signature support."
        ),
        "tool.redact_pdf.title": "REDACT PDF",
        "tool.redact_pdf.description": (
            "Black out areas and really remove what was underneath: the output is a"
            " verified photocopy, with no text and no hidden object."
        ),
        "tool.compare_pdf.title": "COMPARE PDF",
        "tool.compare_pdf.description": "Compare two local PDFs to spot differences.",
        "tool.summarize_pdf_ai.title": "SUMMARIZE PDF WITH AI",
        "tool.summarize_pdf_ai.description": (
            "AI track kept off dashboard until local use is qualified."
        ),
        "tool.translate_pdf_ai.title": "TRANSLATE PDF",
        "tool.translate_pdf_ai.description": (
            "AI track kept off dashboard until local use is qualified."
        ),
        "tool.hidden.title": "TOOL REMOVED FROM CATALOG",
        "tool.hidden.description": "This older tool is no longer visible in the main catalog.",
        "tool_switcher.label": "Switch tool",
        "tool_switcher.button": "TOOLS",
        "tool_switcher.all": "All tools",
        "viewer.previous": "PREVIOUS PAGE",
        "viewer.previous_short": "PREV",
        "viewer.next": "NEXT PAGE",
        "viewer.next_short": "NEXT",
        "viewer.zoom_out": "ZOOM -",
        "viewer.zoom_in": "ZOOM +",
        "viewer.zoom_value.accessible": "Zoom level",
        "viewer.zoom_value.tooltip": "Current zoom: {percent}%.",
        "viewer.fit_menu": "FIT",
        "viewer.fit_menu.tooltip": "Choose how the page fits the viewer",
        "viewer.fit_page": "FIT PAGE",
        "viewer.fit_width": "FIT WIDTH",
        "viewer.no_pdf": "No PDF open in open documents.",
        "viewer.loaded": "PDF loaded locally: {name}",
        "viewer.load_error": "This PDF cannot be opened in the viewer.",
        "viewer.page_status": "Page {page} / {total}",
        "viewer.page_number.accessible": "Go to page",
        "viewer.page_number.prefix": "Page ",
        "viewer.page_number.tooltip": "Enter a page number from 1 to {total}.",
        "viewer.page_number.unavailable": "Open a PDF to choose a page.",
        "viewer.page_number.empty": "—",
        "button.back": "BACK",
        "button.home": "HOME",
        "button.remove": "REMOVE",
        "button.up": "UP",
        "button.down": "DOWN",
        "button.duplicate_pages": "DUPLICATE",
        "button.insert_pages": "INSERT PAGES",
        "button.blank_page": "ADD BLANK PAGE",
        "blank.loading": "{name} — reading pages...",
        "blank.ready": "{name} — {pages}",
        "blank.format.custom": "Custom",
        "blank.label.format": "Format",
        "blank.label.width": "Width",
        "blank.label.height": "Height",
        "blank.label.orientation": "Orientation",
        "blank.label.position": "Position",
        "blank.label.after_page": "Page number",
        "blank.orientation.portrait": "Portrait",
        "blank.orientation.landscape": "Landscape",
        "blank.position.start": "At the beginning",
        "blank.position.after": "After page",
        "blank.position.end": "At the end",
        "blank.effective": "Effective size: {width} x {height} mm",
        "blank.error.incomplete": "Choose a valid PDF and an available output file.",
        "blank.progress": "Adding the blank page locally...",
        "blank.unit_mm": " mm",
        "button.choose_output": "CHOOSE OUTPUT",
        "button.merge": "MERGE PDFS",
        "button.choose_folder": "CHOOSE FOLDER",
        "button.clear": "CLEAR",
        "button.cancel": "Cancel",
        "update.action.check": "CHECK FOR UPDATES",
        "update.action.checking": "CHECKING...",
        "update.action.up_to_date": "SOFTWARE UP TO DATE",
        "update.action.available": "UPDATE AVAILABLE",
        "button.extract": "CREATE THE NEW PDF",
        "button.remove_pages": "CREATE PDF WITHOUT THESE PAGES",
        "button.rotate": "ROTATE PAGES",
        "button.rotate_left": "ROTATE LEFT",
        "button.rotate_right": "ROTATE RIGHT",
        "rotation.accessible.left": "Rotate a quarter turn to the left",
        "rotation.accessible.right": "Rotate a quarter turn to the right",
        "button.reorder": "REORDER PDF",
        "button.split": "SPLIT INTO SEVERAL PDFS",
        "label.page_ranges": "PAGE RANGES",
        "label.page_order": "PAGE ORDER",
        "label.rotation_angle": "ROTATION ANGLE",
        "label.rotation_angle_short": "ANGLE",
        "label.rotation_target_short": "TARGET",
        "rotation.target.all": "All pages",
        "rotation.target.active": "Active page",
        "rotation.target.selected": "Selected pages",
        "rotation.preview_unavailable": "Preview unavailable",
        "rotation.preview_loading": "Loading preview…",
        "rotation.error.no_pdf": "Choose a valid PDF before starting the operation.",
        "rotation.error.no_output": "Choose an output file.",
        "rotation.error.invalid_angle": "Unsupported angle. Use 0, 90, 180, or 270.",
        "rotation.error.no_pages": "Choose at least one page to rotate.",
        "rotation.required.angle": "Turn with ROTATE LEFT or ROTATE RIGHT: 0° would leave the pages unchanged.",
        "tool.action.shortcut": "Shortcut: Ctrl+Enter. Escape goes back.",
        "split.mode.label": "SPLIT",
        "split.mode.groups": "By groups (drag and drop)",
        "split.mode.ranges": "By ranges",
        "split.required.ranges": "Type the ranges, one per file, for example 1-3,4-6.",
        "split.mode.every_n": "Every N pages",
        "split.mode.single_pages": "One page per file",
        "split.size.label": "Pages per file",
        "split.announce.one": "1 file will be created: {names}",
        "split.announce.many": "{count} files will be created: {names}",
        "split.required.pages": "A one-page document cannot be split.",
        "split.required.parts": "This split would copy the whole document into a single file.",
        "split.required.free_names": "“{name}” already exists in this folder: choose another folder.",
        "merge.required.files": "Required step: add at least two PDFs.",
        "merge.required.output": "Required step: choose the output file.",
        "guidance.next.choose_output": "Next step: choose output",
        "guidance.next.view_result": "Next step: view the result",
        "merge.status.running": "Local merge...",
        "merge.error.no_files": "Choose at least two PDFs to merge.",
        "merge.error.no_output": "Choose an output file before merging.",
        "merge.error.title": "Merge unavailable",
        "visual.source_pdf": "SOURCE PDF",
        "merge.row.pages_unknown": "Pages: …",
        "merge.row.remove": "Remove {name} from the merge (the file is not deleted)",
        "visual.advanced_mode": "ADVANCED MODE",
        "visual.add_output_pdf": "+ Add output PDF",
        "visual.output_limit": "{max_count} output PDFs maximum.",
        "visual.output_pdf_n": "Output PDF {index}",
        "visual.extracted_pdf": "New PDF",
        "visual.drop_split": "Drag pages here in the order for the PDF to create.",
        "visual.drop_extract": "Click or drag pages to add, then reorder them if needed.",
        "visual.remove_from_output": "Remove from this output",
        "visual.error.no_pdf": "Choose a valid PDF before starting the operation.",
        "visual.error.no_output": "Choose an output file.",
        "visual.error.no_output_dir": "Choose an output folder.",
        "visual.error.invalid_plan": "Choose valid pages before starting the operation.",
        "visual.error.remove_all": "You cannot remove every page.",
        "visual.required.split": "Drag at least one page into an output PDF.",
        "visual.required.extract": "Add at least one page to the new PDF.",
        "visual.required.remove": "Click the pages to remove.",
        "visual.required.ranges": "Correct the page ranges.",
        "reorder.required.pages": "This document has only one page: nothing to reorder.",
        "reorder.required.change": (
            "Change the order of at least one page: the current order would make an identical copy."
        ),
        "page.reorder.help": (
            "Example: 3,1,1,2,4-6. Every source page must appear at least once; "
            "repeat a number to duplicate that page."
        ),
        "insert.primary.title": "1. MAIN PDF",
        "insert.primary.empty": "Choose the PDF that will receive the new pages.",
        "insert.source.title": "2. PDF TO INSERT",
        "insert.source.empty": "Choose another PDF, then select its pages.",
        "insert.document.loading": "{name} — reading pages...",
        "insert.document.ready": "{name} — {pages}",
        "insert.position.title": "3. INSERTION POSITION",
        "insert.position.start": "Before the first page",
        "insert.summary.empty": "Select at least one page from the second PDF.",
        "insert.summary.start": "at the beginning",
        "insert.summary.after": "after page {page}",
        "insert.summary.ready": (
            "Page(s) {pages} from the second PDF inserted {position}. "
            "The result will contain {total} pages."
        ),
        "insert.progress": "Local insertion...",
        "insert.success.message": "The source PDFs are unchanged.",
        "insert.error.primary": "Choose a valid main PDF.",
        "insert.error.source": "Choose a valid second PDF.",
        "insert.error.same_file": "Choose two different PDF files.",
        "insert.error.selection": "Select at least one page from the second PDF.",
        "insert.error.position": "Choose a valid insertion position.",
        "insert.error.output": "Choose an output file.",
        "job.success.file_created": "File created: {name}",
        "tool.required.source": "Add a PDF to start.",
        "tool.required.output": "Choose an output file.",
        "tool.required.valid_source": "Choose another PDF.",
        "job.success.files_created": "{count} files created",
        "job.success.details_folder": "in {folder}",
        "job.error.generic": "Processing failed. No file was created.",
        "job.error.detail": "Technical detail: {code}",
        "job.error.invalid_pdf": "This PDF is invalid or damaged. Choose another PDF.",
        "job.error.encrypted_pdf": (
            "This PDF is password-protected. Unlock it first with Unlock PDF."
        ),
        "job.error.wrong_password": "Wrong password. Check it and try again.",  # pragma: allowlist secret
        "job.error.input_path_error": "File not found or unreadable. Choose another PDF.",
        "job.error.invalid_page_selection": "The page selection is invalid. Correct it.",
        "job.error.invalid_page_order": "The page order is invalid. Correct it.",
        "job.error.invalid_split_plan": "The requested split is invalid. Correct it.",
        "job.error.unsupported_pdf_feature": (
            "This PDF uses an unsupported feature. No file was created."
        ),
        "job.error.pdf_structure_too_complex": (
            "The structure of this PDF is too large for this tool. No file was created."
        ),
        "job.error.output_write_error": (
            "The output file cannot be written. Choose another location."
        ),
        "job.error.dangerous_output": (
            "This output file already exists or is a source. Choose another name."
        ),
        "job.error.user_cancelled": "Processing cancelled. No file was created.",
        "job.error.worker_timeout": "Processing took too long. No file was created.",
        "job.error.network_isolation_unavailable": (
            "Security isolation is unavailable on this system. No document was processed."
        ),
        "output.none_file": "No output file selected",
        "output.none_dir": "No output folder selected",
        "output.panel.destination": "File destination",
        "output.panel.destination_dir": "Destination folder",
        "output.change": "CHANGE…",
        "output.replace_input": "Replace this PDF",
        "output.copy_help": "By default, a copy is created: the current PDF stays unchanged.",
        "output.replace_help": (
            "Keep the same file and name. The previous version is replaced after "
            "confirmation and successful processing."
        ),
        "size.bytes": "{value}\u00a0bytes",
        "size.kib": "{value}\u00a0KB",
        "size.mib": "{value}\u00a0MB",
        "size.gib": "{value}\u00a0GB",
        "output.dialog.file": "Choose the output file",
        "output.dialog.directory": "Choose the output folder",
        "output.suffix.merge": "_merged",
        "output.suffix.remove": "_pages-removed",
        "output.suffix.extract": "_extracted",
        "output.suffix.reorder": "_reordered",
        "output.suffix.insert": "_pages-inserted",
        "output.suffix.blank_page": "_blank-page-added",
        "output.suffix.rotate": "_rotated",
        "output.suffix.compress": "_compressed",
        "output.suffix.unlock_pdf": "_unlocked",
        "output.suffix.protect": "_protected",
        "output.suffix.share_check": "_no-metadata",
        "output.suffix.share_photo": "_photocopy",
        "output.suffix.ocr_pdf": "_searchable",
        "output.suffix.redact_pdf": "_redacted",
        "output.suffix.watermark": "_watermarked",
        "ocr.languages": "Language of the scanned text",
        "ocr.languages_help": "Tick the document's language or languages (three at most). Only models installed on this computer are offered.",
        "ocr.languages_add": "An added language appears here as soon as its model is installed.",
        "ocr.add.button": "Add a language…",
        "ocr.add.title": "Add a language",
        "ocr.add.intro": "Pick a language: the system installer asks your password, then installs its model. PriveoPDF downloads nothing itself.",
        "ocr.add.search": "Search a language",
        "ocr.add.item": "{name} ({code})",
        "ocr.add.item_installed": "{name} ({code}) — installed",
        "ocr.add.install": "Install",
        "ocr.add.copy": "Copy the command",
        "ocr.add.choose": "Select a language in the list.",
        "ocr.add.already": "{name} is already installed.",
        "ocr.add.ready": "Or, in a terminal: {command}",
        "ocr.add.manual": "No graphical installer found. In a terminal: {command}",
        "ocr.add.waiting": "Installing in the system window… This window updates as soon as the model is present. If nothing opens, in a terminal: {command}",
        "ocr.add.copied": "Command copied: {command}",
        "ocr.add.done": "{name} is installed and ticked. You can close this window.",
        "ocr.language_missing": "Model not installed. In a terminal: sudo apt install tesseract-ocr-{code}",
        "ocr.language_limit": "Three languages at most per run.",
        "ocr.help": "Only scanned pages are processed; pages that already contain text stay as they are. The recognized text is added invisibly: pages look exactly the same.",
        "ocr.required.models": "No OCR model is installed. In a terminal: sudo apt install tesseract-ocr tesseract-ocr-eng",
        "ocr.required.language": "Tick at least one language.",
        "ocr.action": "Recognize text",
        "redact.action": "Redact the PDF",
        "redact.areas.title": "Areas to black out",
        "redact.areas.count": "Areas: {count}",
        "redact.areas.help": "Draw a rectangle on the page with the mouse. Everything underneath will be removed.",
        "redact.areas.remove_last": "Remove the last area",
        "redact.areas.clear": "Clear all",
        "redact.required.areas": "Draw at least one area to black out.",
        "redact.required.too_many": "At most {maximum} areas per document.",
        "redact.required.fresh": "This PDF changed on disk since its pages were shown: load it again with Change PDF.",
        "redact.status.ready": "Every page of the output becomes an image: text is no longer selectable. To make it searchable again, use Recognize text (OCR).",
        "redact.result": "Areas blacked out: {areas}, on {pages}. Verified after writing: every page is an image and no text remains.",
        "redact.error.redaction_integrity": "The redaction could not be verified. No file created.",
        "redact.error.redaction_area_invalid": "An area to black out is outside its page. Remove it and draw it again.",
        "redact.error.photocopy_limit": "This PDF is too large or too long for redaction (at most 500 pages, A2 at most). No file created.",
        "redact.error.photocopy_unsupported": "A form or interactive content cannot be rendered faithfully. No file created.",
        "redact.error.photocopy_integrity": "The redaction could not be verified. No file created.",
        "redact.error.photocopy_renderer_unavailable": "Redaction could not run under its memory protection on this computer. No file created.",
        "redact.error.render_memory_unavailable": "Redaction could not run under its memory protection on this computer. No file created. The document may also have exceeded its processing limit: see Help, Troubleshooting.",
        "redact.error.render_memory_or_worker_failed": "Redaction could not run under its memory protection on this computer. No file created. The document may also have exceeded its processing limit: see Help, Troubleshooting.",
        "redact.error.share_signed": "This PDF carries a digital signature: the operation is refused without your choice of a copy without the signature. No file created.",
        "redact.error.share_integrity": "The file changed during processing. No file created.",
        "redact.error.generic": "Redaction or its verification failed. No file created; also check the destination.",
        "watermark.action": "Watermark the PDF",
        "watermark.settings.title": "Watermark",
        "watermark.text.label": "Text",
        "watermark.text.placeholder": "E.g.: Copy issued to … — confidential",
        "watermark.text.help": "Up to 120 characters, written on every page. The preview on the left shows the result.",
        "watermark.layout.label": "Layout",
        "watermark.layout.diagonal": "Diagonal, centered",
        "watermark.layout.tiled": "Repeated over the page",
        "watermark.strength.label": "Strength",
        "watermark.strength.light": "Light",
        "watermark.strength.medium": "Medium",
        "watermark.strength.strong": "Strong",
        "watermark.required.text": "Enter the watermark text.",
        "watermark.required.text_invalid": "The text contains an unsupported character: use Latin letters, digits and common punctuation.",
        "watermark.required.fresh": "This PDF changed on disk since its pages were shown: load it again with Change PDF.",
        "watermark.status.ready": "The text is written into every page, not as a mere annotation: it cannot be removed with one click. It stays visible and selectable; a deliberate re-edit of the PDF can still remove it.",
        "watermark.result": "Watermark verified on {pages}: text present and visible on each of them.",
        "watermark.error.watermark_integrity": "The watermark could not be verified. No file created.",
        "watermark.error.watermark_text_invalid": "The watermark text is empty, too long or contains an unsupported character.",
        "watermark.error.watermark_limit": "This PDF exceeds the watermark limits (500 pages at most). No file created.",
        "watermark.error.watermark_unsupported": "A page of this PDF has a size or a rotation the watermark does not support. No file created.",
        "watermark.error.photocopy_limit": "A page of this PDF is too large for the watermark verification. No file created.",
        "watermark.error.photocopy_integrity": "The watermark could not be verified. No file created.",
        "watermark.error.photocopy_renderer_unavailable": "The watermark verification could not run under its memory protection on this computer. No file created.",
        "watermark.error.render_memory_unavailable": "The watermark verification could not run under its memory protection on this computer. No file created. The document may also have exceeded its processing limit: see Help, Troubleshooting.",
        "watermark.error.render_memory_or_worker_failed": "The watermark verification could not run under its memory protection on this computer. No file created. The document may also have exceeded its processing limit: see Help, Troubleshooting.",
        "watermark.error.share_signed": "This PDF carries a digital signature: the operation is refused without your choice of a copy without the signature. No file created.",
        "watermark.error.share_integrity": "The file changed during processing. No file created.",
        "watermark.error.generic": "The watermark or its verification failed. No file created; also check the destination.",
        "ocr.progress": "Recognizing text…",
        "ocr.result": "Pages made searchable: {recognized} · pages already with text, left intact: {present} · pages with no text found: {empty}",
        "ocr.result.selected": "Pages made searchable: {recognized} · pages left intact (already with text, or not chosen): {present} · pages with no text found: {empty}",
        "ocr.advanced": "ADVANCED OPTIONS",
        "ocr.pages": "Pages to recognize",
        "ocr.pages_placeholder": "Every scanned page",
        "ocr.pages_help": "Leave empty to process every scanned page. Otherwise type page numbers or ranges, for example 1-50, 52: the other pages stay as they are. A document with more than 50 scanned pages is processed in several passes, on the copy produced.",
        "ocr.required.pages": "Correct the pages to recognize, for example 1-50, 52.",
        "ocr.required.pages_bounds": "The pages to recognize must be between 1 and {count}.",
        "ocr.required.pages_many": "At most {count} pages can be chosen.",
        "ocr.error.ocr_already_searchable_selected": "The chosen pages already contain text: nothing to recognize. No file created.",
        "ocr.error.ocr_already_searchable": "Every page already contains text: this PDF is already searchable. No file created.",
        "ocr.error.ocr_no_eligible_pages": "No text was recognized on the scanned pages. Check the ticked language and the sharpness of the scan. No file created.",
        "ocr.error.ocr_limit": "This PDF exceeds the local OCR limits: 500 pages in total, and at most 50 scanned A4 pages (25 in A3; largest size A2). Choose fewer pages under Advanced options, or split it first with Split PDF. No file created.",
        "ocr.error.ocr_unsupported": "A scanned page has an annotation, a form or a crop that OCR does not support yet. No file created.",
        "ocr.error.ocr_signed": "This PDF carries a digital signature: the operation is refused without your choice of a copy without the signature. No file created.",
        "ocr.error.ocr_model_missing": "A ticked language model is not installed. In a terminal: sudo apt install tesseract-ocr-<code>. No file created.",
        "ocr.error.ocr_library_missing": "The Tesseract OCR engine is not installed. In a terminal: sudo apt install tesseract-ocr. No file created.",
        "ocr.error.ocr_native_error": "Text recognition failed. No file created.",
        "ocr.error.ocr_integrity": "The OCR copy could not be verified. No file created.",
        "ocr.error.worker_timeout": "OCR took more than thirty minutes. Choose fewer pages under Advanced options, or split the document with Split PDF, then try again. No file created.",
        "ocr.error.ocr_renderer_unavailable": "OCR could not run under its memory protection on this computer. No file created. The document may also have exceeded its processing limit: see Help, Troubleshooting.",
        "ocr.error.render_memory_unavailable": "OCR could not run under its memory protection on this computer. No file created. The document may also have exceeded its processing limit: see Help, Troubleshooting.",
        "ocr.error.render_memory_or_worker_failed": "OCR could not run under its memory protection on this computer. No file created. The document may also have exceeded its processing limit: see Help, Troubleshooting.",
        "ocr.error.generic": "Recognition or its verification failed. No file created; also check the destination.",
        "result.open_pdf": "OPEN PDF",
        "result.open_folder": "OPEN FOLDER",
        "result.continue_with": "CONTINUE WITH…",
        "job.running": "Local processing…",
        "input.none_pdf": "No PDF selected",
        "page_count.empty": "Pages: -",
        "page_count.loading": "Pages: reading...",
        "page_count.value": "Pages: {count}",
        "document.title": "DOCUMENT",
        "document.empty.title": "No document open",
        "document.empty.meta": "Open a local PDF to enter document mode.",
        "document.meta": "{pages} · {size}",
        "document.badge.selectable_text": "Text detected",
        "document.badge.selectable_text.tooltip": (
            "Extractable text detected locally on a PDF sample."
        ),
        "document.badge.probable_scan.compact": "Probable scan",
        "document.badge.probable_scan.tooltip": (
            "Local analysis indicates this PDF probably looks like a scan."
        ),
        "document.badge.protected_pdf": "Protected PDF",
        "document.badge.restricted_pdf": "Usage restrictions",
        "document.status.locked": "protected",
        "document.badge.analysis_unavailable": "Analysis unavailable",
        "document.thumbnails": "PAGES",
        "document.info.title": "DOCUMENT INFO",
        "document.source_intact": "The original stays intact. Tools create a copy.",
        "document.layout.hide_pages": "Hide pages",
        "document.layout.show_pages": "Show pages",
        "document.layout.hide_info": "Hide document information",
        "document.layout.show_info": "Show document information",
        "document.layout.reading_mode": "Reading mode — Ctrl+Shift+R",
        "document.layout.exit_reading": "Exit reading mode — Ctrl+Shift+R",
        "document.layout.pages_compact": "PAGES",
        "document.layout.info_compact": "INFO",
        "document.use_with.button": "USE WITH…",
        "document.use_with.tooltip": "Continue with an available tool for this PDF",
        "document.more.button": "MORE",
        "document.more.tooltip": "Reading options and file location",
        "document.open_folder": "OPEN FOLDER",
        "document.open_folder.tooltip": "Open the folder containing the source PDF",
        "document.analysis.empty": "Local analysis pending.",
        "document.analysis.running": "Light local analysis running...",
        "document.analysis.unavailable": "Analysis unavailable for this file.",
        "document.scan_likelihood.unknown": "Document type undetermined.",
        "document.scan_likelihood.unknown.tooltip": (
            "Local analysis could not determine whether the PDF contains extractable text."
        ),
        "document.scan_likelihood.low": "Text detected in the analyzed sample.",
        "document.scan_likelihood.medium": "Scan possible in the analyzed sample.",
        "document.scan_likelihood.high": "Probable scanned document.",
        "document.size.unknown": "Unknown size",
        "document.initial.invalid": "File ignored: open a valid local PDF.",
        "document.initial.opened_first": (
            "Several PDFs received: the first is open, the others stay in open documents."
        ),
        "thumbnails.load_more": "SHOW MORE THUMBNAILS",
        "thumbnails.page_label": "Page {page}",
        "thumbnails.page_tooltip": "Page {page}",
        "thumbnails.loading": "loading",
        "thumbnails.unavailable": "preview unavailable",
        "thumbnails.deleted": "REMOVED",
        "thumbnails.assigned": "ASSIGNED",
        "update.manual.tooltip": (
            "Connect once to the version service to check for an update. "
            "No document or local path is sent."
        ),
        "update.manual.tooltip.checking": "Checking for an update.",
        "update.manual.tooltip.up_to_date": ("The software is up to date. Click to check again."),
        "update.manual.tooltip.update_available": (
            "Click to view changes and the official download page."
        ),
        "update.manual.tooltip.not_configured": (
            "No signed public update channel is configured yet."
        ),
        "update.consent.title": "Internet connection required",
        "update.consent.message": (
            "Checking for updates requires an internet connection. Are you sure you "
            "want to continue?"
        ),
        "update.consent.privacy": (
            "Only the PriveoPDF version is checked. No document or local path is sent."
        ),
        "update.consent.accept": "YES, CONTINUE",
        "update.consent.decline": "NO",
        "update.progress.title": "Checking for updates",
        "update.progress.message": "Securely checking the latest version…",
        "update.result.up_to_date.title": "PriveoPDF is up to date",
        "update.result.failed.title": "Unable to check",
        "update.state.checking": "Checking for updates.",
        "update.state.up_to_date": "No update available.",
        "update.state.update_available": "Update available.",
        "update.state.not_verified": "Updates not checked.",
        "update.state.disabled": "Update checks disabled.",
        "update.state.not_configured": "Update checks not configured.",
        "update.state.offline": "Update checks unavailable offline.",
        "update.state.private_or_not_found": "Update source not found or private.",
        "update.state.no_release": "No compatible release found.",
        "update.state.rate_limited": "Update check temporarily rate limited.",
        "update.state.invalid_payload": "Invalid update response.",
        "update.state.https_required": "Update source refused: HTTPS is required.",
        "update.state.host_not_allowed": "Update host is not allowed.",
        "update.state.private_address": "Private network address refused.",
        "update.state.credentials_not_allowed": "Credentials are forbidden in the URL.",
        "update.state.port_not_allowed": "Network port is not allowed.",
        "update.state.redirect_not_allowed": "Update redirect refused.",
        "update.state.response_too_large": "Update response is too large.",
        "update.state.invalid_content_type": "Invalid update response type.",
        "update.state.invalid_signature": "Invalid manifest signature.",
        "update.state.unknown_signing_key": "Unknown manifest signing key.",
        "update.state.signature_verifier_unavailable": "Signature verification unavailable.",
        "update.state.invalid_signing_key": "Invalid signing key.",
        "update.state.invalid_checksum": "Invalid artifact checksum.",
        "update.state.checksum_mismatch": "Artifact checksum mismatch.",
        "update.state.downgrade_refused": "Older version refused.",
        "update.state.unsupported_manifest_schema": "Unsupported manifest version.",
        "update.state.source_updater_unavailable": (
            "Integrated update unavailable: Git was not found."
        ),
        "update.state.source_checkout_invalid": ("The local PriveoPDF checkout is not recognized."),
        "update.state.source_checkout_dirty": (
            "The local checkout contains changes or untracked files."
        ),
        "update.state.source_checkout_wrong_branch": (
            "Integrated updates require the main branch."
        ),
        "update.state.source_checkout_wrong_remote": (
            "The remote repository is not the authorized PriveoPDF repository."
        ),
        "update.state.source_checkout_diverged": (
            "The local checkout and origin/main have diverged. Update refused."
        ),
        "update.state.source_fetch_failed": (
            "Unable to reach origin/main with the configured Git credentials."
        ),
        "update.state.source_check_timeout": "The Git check exceeded the allowed time.",
        "update.dialog.title": "Update available",
        "update.dialog.available": (
            "PriveoPDF {version} is available. Would you like to open the official "
            "installation page?"
        ),
        "update.dialog.source.available": (
            "A new PriveoPDF revision is ready. Would you like to install it? "
            "The software will close, run the automatic tests of this revision, "
            "and then restart."
        ),
        "update.dialog.installed": "Installed version: {version}",
        "update.dialog.latest": "Latest version: {version}",
        "update.dialog.source.installed": "Installed revision: {version}",
        "update.dialog.source.latest": "Available revision: {version}",
        "update.dialog.changes": "WHAT'S NEW",
        "update.dialog.no_notes": "No short notes available.",
        "update.dialog.install": "YES, OPEN INSTALLATION",
        "update.dialog.source.install": "YES, INSTALL AND RESTART",
        "update.dialog.later": "LATER",
        "update.install.title": "Updating PriveoPDF",
        "update.install.waiting": "Securely closing PriveoPDF…",
        "update.install.waiting_other_instances": (
            "Close every other PriveoPDF window to continue the update…"
        ),
        "update.install.progress": (
            "Validating and installing the update. This may take several minutes."
        ),
        "update.install.phase.preflight": "Step 1/8 — Checking the local installation",
        "update.install.phase.fetch": "Step 2/8 — Downloading the approved revision",
        "update.install.phase.prepare": "Step 3/8 — Preparing the validation copy",
        "update.install.phase.dependencies": "Step 4/8 — Checking dependencies",
        "update.install.phase.bootstrap": "Step 5/8 — Checking application startup",
        "update.install.phase.tests": "Step 6/8 — Running application tests",
        "update.install.phase.install": "Step 7/8 — Installing the validated revision",
        "update.install.phase.finalize": "Step 8/8 — Final synchronization",
        "update.install.phase.complete": "Update validated",
        "update.install.elapsed": "Elapsed time: {duration}",
        "update.install.log.show": "SHOW LOG",
        "update.install.log.hide": "HIDE LOG",
        "update.install.log.accessible": "Update technical log",
        "update.install.success": "Update installed. Restarting PriveoPDF…",
        "update.install.failed": (
            "The update failed. PriveoPDF did not restart automatically; review the "
            "details before reopening it."
        ),
        "update.install.unsafe_failure": (
            "The installation failed and the application state could not be verified. "
            "Do not reopen PriveoPDF; rerun the update from a terminal."
        ),
        "update.install.recovery": (
            "Recovery: close this window, open a terminal in the PriveoPDF folder, "
            "then run: bash tools/update_from_github.sh {revision}"
        ),
        "update.install.launch_failed": "The secure update process did not start.",
        "update.open_release.failed.title": "Page not opened",
        "update.open_release.failed": (
            "Your browser could not open the new version's page. "
            "Paste this address into your browser:"
        ),
        "update.open_release.copy": "Copy address",
        "update.install.restart_failed": (
            "The update completed, but PriveoPDF could not restart automatically."
        ),
        "update.install.reopen": "REOPEN PRIVEOPDF",
        "update.install.close": "CLOSE",
    },
}


def normalize_locale(locale: str) -> Locale:
    value = locale.lower()
    if value.startswith("fr"):
        return "fr"
    if value.startswith("en"):
        return "en"
    return DEFAULT_LOCALE


def tr(key: str, locale: Locale = DEFAULT_LOCALE, **kwargs: object) -> str:
    text = TRANSLATIONS.get(locale, TRANSLATIONS[DEFAULT_LOCALE]).get(
        key,
        TRANSLATIONS[DEFAULT_LOCALE].get(key, key),
    )
    if kwargs:
        return text.format(**kwargs)
    return text
