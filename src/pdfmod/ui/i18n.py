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
        "app.name": "PriveoPDF",
        "language.fr": "Français",
        "language.en": "English",
        "mode.light.action": "MODE CLAIR",
        "mode.dark.action": "MODE SOMBRE",
        "theme.dark": "SOMBRE",
        "theme.system": "Automatique — suivre le système",
        "theme.light": "CLAIR",
        "theme.dark_pro": "Sombre — Sobre",
        "theme.light_pro": "Clair — Sobre",
        "theme.light_coral": "Corail doux",
        "theme.light_ocean": "Océan clair",
        "theme.light_sage": "Sauge douce",
        "theme.light_lavender": "Lavande douce",
        "theme.light_solar": "Solaire",
        "theme.dark_midnight": "Nuit bleue",
        "theme.dark_forest": "Forêt nocturne",
        "theme.dark_plum": "Prune nocturne",
        "theme.dark_graphite": "Graphite orange",
        "theme.dark_contrast": "Contraste élevé",
        "theme.dark_pixel": "Sombre — Pixel",
        "theme.light_pixel": "Clair — Pixel",
        "theme.visual_style.pro": "Sobre",
        "theme.visual_style.pixel": "Pixel",
        "yes": "OUI",
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
        "beta.integration.window_title": "PriveoPDF Bêta — Intégration ({count} PR)",
        "beta.integration.heading": "CHECKLIST BÊTA",
        "beta.integration.identity": "{count} PR intégrées dans cette Bêta.",
        "beta.integration.help": "Cochez uniquement ce que vous avez vérifié.",
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
        "options.beta.item": "PR #{pr} · {sha} · {date}",
        "options.beta.relaunch": "RELANCER CETTE VERSION",
        "options.beta.confirm.title": "Changer de version Bêta",
        "options.beta.confirm.message": (
            "Fermer cette Bêta et relancer la PR #{pr} au SHA {sha} ?"
        ),
        "options.beta.error.title": "Version Bêta indisponible",
        "options.beta.error.message": (
            "Cette version locale n'est plus complète ou sa provenance ne peut plus être "
            "vérifiée. Relancez d'abord le dernier artefact disponible."
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
            "la géométrie de fenêtre et le cache de mise à jour ? Les fichiers PDF source ne "
            "seront pas supprimés."
        ),
        "options.about": "À PROPOS",
        "options.close": "FERMER",
        "options.apply": "APPLIQUER",
        "options.restart_required.title": "Redémarrage requis",
        "options.restart_required.message": (
            "La langue a été enregistrée. Redémarre PriveoPDF pour l'appliquer partout."
        ),
        "options.local_files": "Les fichiers restent sur cet appareil.",
        "options.no_upload": "Aucun upload pour les fonctions locales.",
        "options.product_promise": "Traitement PDF local, sans upload.",
        "about.title": "À PROPOS",
        "about.tooltip": "À propos de PriveoPDF",
        "about.product_promise": "Traitement PDF local, sans upload.",
        "about.no_account": "Aucun compte. Aucun cloud.",
        "about.documents_stay": "Les documents restent sur cet appareil.",
        "about.license": "Exécutable officiel — licence freeware propriétaire.",
        "about.third_party": "Les composants tiers conservent leurs propres licences.",
        "about.copyright": "Copyright © 2026 godlittleboi",
        "first_run.title": "ASSISTANT DE CONFIGURATION INITIALE",
        "first_run.subtitle": (
            "PriveoPDF traite les PDF sur cet appareil, sans dépendance cloud pour les "
            "fonctions locales."
        ),
        "first_run.language": "LANGUE",
        "first_run.theme": "THÈME",
        "first_run.reduce_motion": "RÉDUIRE LES ANIMATIONS",
        "first_run.update_checks": "VÉRIFIER AUTOMATIQUEMENT LES MISES À JOUR",
        "first_run.update_checks.help": (
            "Utilise uniquement un manifest public de version configuré. Aucun fichier PDF, "
            "chemin, nom, métadonnée ou contenu n'est envoyé. La case est désactivée par "
            "défaut et Plus tard ne déclenche aucune connexion."
        ),
        "first_run.default_output_dir": "DOSSIER DE SORTIE PAR DÉFAUT",
        "first_run.after_job": "APRÈS TRAITEMENT",
        "first_run.start": "COMMENCER",
        "first_run.cancel": "PLUS TARD",
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
        "workspace.remove.busy.message": (
            "Ce PDF est utilisé par un traitement local en cours. Attends la fin du traitement "
            "avant de le retirer des documents ouverts."
        ),
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
        "community.nav.home": "Accueil",
        "community.nav.getting_started": "Bien démarrer",
        "community.nav.privacy": "Confidentialité",
        "community.nav.faq": "FAQ",
        "community.nav.addons": "Addons",
        "community.nav.contribute": "Donner un avis",
        "sidebar.local.tooltip": (
            "100 % LOCAL\nAucun compte. Aucun cloud. Les documents restent sur cet appareil."
        ),
        "nav.dashboard.compact": "Accueil",
        "nav.dashboard.tooltip": "Accueil",
        "pending.badge": "EN ATTENTE",
        "pending.title": "Fonction en attente",
        "pending.message": (
            "Cette fonction est en attente. Elle pourra être modifiée, reportée ou abandonnée."
        ),
        "pending.local_message": "Cet outil n'est pas disponible dans cette version.",
        "local.badge": "100 % LOCAL",
        "local.note": "Aucun compte. Aucun cloud. Les documents restent sur cet appareil.",
        "dashboard.subtitle": "Outil PDF local, privé et robuste. Aucun compte, aucun upload.",
        "dashboard.tools": "OUTILS RAPIDES",
        "dashboard.tools.available": "OUTILS DISPONIBLES",
        "dashboard.tools.pending": "À VENIR",
        "dashboard.open_files": "OUVRIR DES PDF",
        "dashboard.open_files.tooltip": "Choisir un ou plusieurs PDF sur cet appareil.",
        "dashboard.search.placeholder": "Rechercher parmi les outils disponibles",
        "dashboard.search.accessible": "Rechercher un outil disponible",
        "dashboard.catalog.show": "TOUS LES OUTILS",
        "dashboard.catalog.show.tooltip": "Afficher les neuf outils disponibles.",
        "dashboard.catalog.hide": "MASQUER LES OUTILS",
        "dashboard.catalog.hide.tooltip": (
            "Masquer le catalogue et revenir aux actions recommandées."
        ),
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
        "dashboard.ready.help": "Choisissez une action.",
        "dashboard.ready.privacy": "Vos fichiers restent sur votre appareil. Rien n'est envoyé.",
        "dashboard.ready.file_selection": "DOCUMENTS OUVERTS",
        "dashboard.ready.recommended_action": "ACTION RECOMMANDÉE",
        "dashboard.ready.other_actions": "AUTRES ACTIONS DISPONIBLES",
        "dashboard.ready.other_actions_single": "AUTRES OUTILS POUR CE PDF",
        "dashboard.ready.other_actions_multi": "VÉRIFIER AVANT DE FUSIONNER",
        "dashboard.ready.view_selected": "VISUALISER PDF SÉLECTIONNÉ",
        "dashboard.ready.view_selected.tooltip": (
            "Visualiser le PDF sélectionné dans les documents ouverts."
        ),
        "dashboard.ready.selected_file": "sélectionné",
        "dashboard.ready.page_count_one": "1 page",
        "dashboard.ready.page_count_many": "{count} pages",
        "dashboard.ready.remove_file": "RETIRER",
        "dashboard.ready.remove_file.tooltip": (
            "Retirer ce PDF des documents ouverts sans supprimer le fichier source."
        ),
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
        "nav.dashboard": "ACCUEIL",
        "tool.dashboard.subtitle": "Traitement PDF local, sans upload.",
        "tool.view.title": "VISUALISER PDF",
        "tool.view.description": "Ouvrir et lire un PDF local sans transformation.",
        "tool.merge.title": "FUSIONNER PDF",
        "tool.merge.description": "Assembler plusieurs PDF en un seul fichier.",
        "tool.merge.subtitle": "Assemblez plusieurs fichiers en un PDF local.",
        "tool.split.title": "DIVISER PDF",
        "tool.split.description": "Créer plusieurs PDF à partir de plages.",
        "tool.split.subtitle": "Créez plusieurs fichiers à partir de plages de pages.",
        "tool.extract.title": "EXTRAIRE DES PAGES",
        "tool.extract.description": (
            "Créer un nouveau PDF avec les pages sélectionnées, dans l'ordre choisi."
        ),
        "tool.extract.subtitle": "Choisissez les pages et leur ordre pour générer un nouveau PDF.",
        "tool.reorder.title": "RÉORGANISER PAGES",
        "tool.reorder.description": "Réordonner toutes les pages d'un PDF.",
        "tool.reorder.subtitle": "Recomposez l'ordre complet d'un document.",
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
        "tool.rotate.title": "FAIRE PIVOTER LES PAGES",
        "tool.rotate.description": "Appliquer une rotation locale à certaines pages.",
        "tool.rotate.subtitle": "Appliquez une rotation relative à des pages.",
        "tool.remove.title": "SUPPRIMER PAGES",
        "tool.remove.description": "Créer un PDF sans les pages choisies.",
        "tool.remove.subtitle": "Créez une version locale sans certaines pages.",
        "tool.compose_pdf.title": "COMPOSER UN PDF",
        "tool.compose_pdf.description": (
            "Combiner plusieurs opérations dans un même parcours avancé."
        ),
        "tool.scan_to_pdf.title": "SCANNER VERS PDF",
        "tool.scan_to_pdf.description": "Créer un PDF depuis un scanner local.",
        "tool.compress.title": "COMPRESSER PDF",
        "tool.compress.description": "Réduire le poids d'un PDF local.",
        "tool.repair_pdf.title": "RÉPARER PDF",
        "tool.repair_pdf.description": "Tenter de récupérer un PDF endommagé.",
        "tool.ocr_pdf.title": "OCR PDF",
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
        "tool.watermark.title": "FILIGRANE",
        "tool.watermark.description": "Ajouter un filigrane visible au PDF.",
        "tool.crop.title": "RECADRER PDF",
        "tool.crop.description": "Recadrer les pages d'un PDF local.",
        "tool.edit_pdf.title": "MODIFIER PDF",
        "tool.edit_pdf.description": "Ajouter des éléments visuels simples au PDF.",
        "tool.pdf_forms.title": "FORMULAIRES PDF",
        "tool.pdf_forms.description": "Préparer ou remplir des champs de formulaire PDF.",
        "tool.unlock_pdf.title": "DÉVERROUILLER PDF",
        "tool.unlock_pdf.description": "Déverrouiller un PDF avec un mot de passe connu.",
        "tool.protect.title": "PROTÉGER PDF",
        "tool.protect.description": "Ajouter une protection par mot de passe.",
        "tool.sign_pdf.title": "SIGNER PDF",
        "tool.sign_pdf.description": (
            "Ajouter une signature visuelle ou préparer une future signature électronique."
        ),
        "tool.redact_pdf.title": "CAVIARDER PDF",
        "tool.redact_pdf.description": (
            "Outil sensible à valider avant toute promesse de suppression réelle."
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
        "tool.status.available": "DISPONIBLE",
        "tool_switcher.label": "Changer d'outil",
        "tool_switcher.button": "OUTILS",
        "tool_switcher.all": "Tous les outils",
        "viewer.choose_pdf": "CHOISIR PDF",
        "viewer.change_pdf": "CHANGER PDF",
        "viewer.previous": "PAGE PRÉCÉDENTE",
        "viewer.previous_short": "PRÉC.",
        "viewer.next": "PAGE SUIVANTE",
        "viewer.next_short": "SUIV.",
        "viewer.zoom_out": "ZOOM -",
        "viewer.zoom_in": "ZOOM +",
        "viewer.zoom_value.accessible": "Niveau de zoom",
        "viewer.zoom_value.tooltip": "Zoom actuel : {percent} %.",
        "viewer.zoom_invalid": "Zoom invalide : utilisez une valeur entre 25 % et 400 %.",
        "viewer.fit_menu": "AJUSTER",
        "viewer.fit_menu.tooltip": "Choisir l'ajustement de la page",
        "viewer.fit_page": "AJUSTER PAGE",
        "viewer.fit_page_short": "PAGE",
        "viewer.fit_width": "AJUSTER LARGEUR",
        "viewer.fit_width_short": "LARG.",
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
        "button.export": "EXPORTER",
        "button.choose_files": "CHOISIR FICHIERS",
        "button.remove": "RETIRER",
        "button.up": "MONTER",
        "button.down": "DESCENDRE",
        "button.duplicate_pages": "DUPLIQUER",
        "button.insert_pages": "INSÉRER LES PAGES",
        "button.blank_page": "AJOUTER LA PAGE BLANCHE",
        "blank.loading": "{name} — lecture des pages en cours...",
        "blank.ready": "{name} — {count} page(s)",
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
        "blank.output.dialog": "Choisir le PDF avec page blanche",
        "blank.error.incomplete": "Choisissez un PDF valide et un fichier de sortie disponible.",
        "blank.progress": "Ajout local de la page blanche...",
        "blank.success.title": "Page blanche ajoutée",
        "blank.success.message": "PDF créé : {name}",
        "button.choose_output": "CHOISIR SORTIE",
        "button.merge": "FUSIONNER PDF",
        "button.choose_pdf": "CHOISIR PDF",
        "button.choose_folder": "CHOISIR DOSSIER",
        "button.clear": "EFFACER",
        "button.view_merged_pdf": "VISUALISER LE PDF FUSIONNÉ",
        "button.cancel": "Annuler",
        "button.open_download_page": "OUVRIR LA PAGE DE TÉLÉCHARGEMENT",
        "update.action.check": "RECHERCHER DES MISES À JOUR",
        "update.action.checking": "RECHERCHE EN COURS...",
        "update.action.up_to_date": "LOGICIEL À JOUR",
        "update.action.available": "MISE À JOUR DISPONIBLE",
        "button.extract": "CRÉER LE NOUVEAU PDF",
        "button.remove_pages": "CRÉER LE PDF SANS CES PAGES",
        "button.rotate": "TOURNER LE PDF",
        "button.rotate_left": "ROTATION GAUCHE",
        "button.rotate_right": "ROTATION DROITE",
        "button.reorder": "RÉORGANISER LE PDF",
        "button.split": "DIVISER EN PLUSIEURS PDF",
        "label.page_ranges": "PLAGES DE PAGES",
        "label.page_order": "ORDRE DES PAGES",
        "label.rotation_angle": "ANGLE DE ROTATION",
        "label.rotation_angle_short": "ANGLE",
        "label.rotation_target": "PAGES",
        "label.rotation_target_short": "CIBLE",
        "rotation.target.all": "Toutes les pages",
        "rotation.target.active": "Page active",
        "rotation.target.selected": "Pages sélectionnées",
        "rotation.preview_unavailable": "Aperçu indisponible",
        "rotation.error.no_pdf": "Choisis un PDF valide avant de lancer l'opération.",
        "rotation.error.no_output": "Choisis un fichier de sortie.",
        "rotation.error.invalid_angle": "Angle non supporté. Utilisez 0, 90, 180 ou 270.",
        "rotation.error.no_pages": "Choisis au moins une page à tourner.",
        "merge.required.files": "Étape requise : ajoutez au moins deux PDF.",
        "merge.required.output": "Étape requise : choisissez le fichier de sortie.",
        "merge.ready": "Sortie choisie. Vous pouvez fusionner.",
        "guidance.next.choose_output": "Étape suivante : choisir la sortie",
        "guidance.next.execute": "Étape suivante : {action}",
        "guidance.next.view_result": "Étape suivante : visualiser le résultat",
        "merge.status.running": "Fusion locale...",
        "merge.dialog.output_title": "Choisir le fichier fusionné",
        "merge.error.no_files": "Choisis au moins deux PDF à fusionner.",
        "merge.error.no_output": "Choisis un fichier de sortie avant de fusionner.",
        "merge.success.title": "Fusion terminée",
        "merge.error.title": "Fusion impossible",
        "visual.source_pdf": "PDF SOURCE",
        "visual.advanced_mode": "MODE AVANCÉ",
        "visual.add_output_pdf": "+ Ajouter un PDF de sortie",
        "visual.output_limit": "{max_count} PDF de sortie maximum.",
        "visual.output_pdf_n": "PDF de sortie {index}",
        "visual.extracted_pdf": "Nouveau PDF",
        "visual.drop_split": "Glisse les pages ici dans l'ordre du PDF à créer.",
        "visual.drop_extract": (
            "Clique ou glisse les pages à ajouter, puis réorganise-les si nécessaire."
        ),
        "visual.remove_from_output": "Retirer de cette sortie",
        "visual.error.no_pdf": "Choisis un PDF valide avant de lancer l'opération.",
        "visual.error.no_output": "Choisis un fichier de sortie.",
        "visual.error.no_output_dir": "Choisis un dossier de sortie.",
        "visual.error.invalid_plan": "Choisis des pages valides avant de lancer l'opération.",
        "visual.error.remove_all": "Impossible de supprimer toutes les pages.",
        "page.merge.help": "Dépose plusieurs PDF ou choisis-les dans l'ordre voulu.",
        "page.reorder.help": (
            "Exemple : 3,1,1,2,4-6. Chaque page source doit être présente au moins une fois ; "
            "répéter un numéro duplique cette page."
        ),
        "insert.primary.title": "1. PDF PRINCIPAL",
        "insert.primary.empty": "Choisissez le PDF qui recevra les nouvelles pages.",
        "insert.source.title": "2. PDF À INSÉRER",
        "insert.source.empty": "Choisissez un autre PDF puis sélectionnez ses pages.",
        "insert.document.loading": "{name} — lecture des pages en cours...",
        "insert.document.ready": "{name} — {count} page(s)",
        "insert.position.title": "3. POSITION D'INSERTION",
        "insert.position.start": "Avant la première page",
        "insert.position.after": "Après la page {page}",
        "insert.position.end": "Après la dernière page ({page})",
        "insert.summary.empty": "Sélectionnez au moins une page du second PDF.",
        "insert.summary.start": "au début",
        "insert.summary.after": "après la page {page}",
        "insert.summary.ready": (
            "Page(s) {pages} du second PDF insérée(s) {position}. "
            "Le résultat contiendra {total} pages."
        ),
        "insert.output.dialog": "Choisir le PDF avec les pages insérées",
        "insert.progress": "Insertion locale...",
        "insert.success.title": "Insertion terminée",
        "insert.success.message": "{name} a été créé sans modifier les PDF sources.",
        "insert.error.primary": "Choisis un PDF principal valide.",
        "insert.error.source": "Choisis un second PDF valide.",
        "insert.error.same_file": "Choisis deux fichiers PDF différents.",
        "insert.error.selection": "Sélectionne au moins une page du second PDF.",
        "insert.error.position": "Choisis une position d'insertion valide.",
        "insert.error.output": "Choisis un fichier de sortie.",
        "error.operation.title": "Opération impossible",
        "output.none_file": "Aucun fichier de sortie choisi",
        "output.none_dir": "Aucun dossier de sortie choisi",
        "output.panel.title": "SORTIE",
        "output.panel.destination": "Destination du fichier",
        "output.panel.status_title": "ÉTAT",
        "input.none_pdf": "Aucun PDF choisi",
        "page_count.empty": "Pages : -",
        "page_count.loading": "Pages : lecture en cours...",
        "page_count.value": "Pages : {count}",
        "document.title": "DOCUMENT",
        "document.empty.title": "Aucun document ouvert",
        "document.empty.meta": "Ouvre un PDF local pour passer en mode document.",
        "document.meta": "{pages} · {size}",
        "document.badge.local": "Local",
        "document.badge.selectable_text": "Texte détecté",
        "document.badge.selectable_text.tooltip": (
            "Texte extractible détecté localement sur un échantillon du PDF."
        ),
        "document.badge.probable_scan": "Document scanné probable",
        "document.badge.probable_scan.compact": "Scan probable",
        "document.badge.probable_scan.tooltip": (
            "L'analyse locale indique que ce PDF ressemble probablement à un scan."
        ),
        "document.badge.protected_pdf": "PDF protégé",
        "document.badge.analysis_unavailable": "Analyse indisponible",
        "document.thumbnails": "PAGES",
        "document.info.title": "INFOS DOCUMENT",
        "document.actions.title": "ACTIONS",
        "document.source_intact": "L'original reste intact. Les outils créent une copie.",
        "document.action.organize": "Organiser",
        "document.action.sign": "Annoter / signer",
        "document.action.searchable": "Rendre recherchable",
        "document.action.compress": "Compresser",
        "document.action.convert": "Convertir",
        "document.action.protect": "Protéger",
        "document.action.more": "Plus",
        "document.layout.hide_pages": "Masquer pages",
        "document.layout.show_pages": "Afficher pages",
        "document.layout.hide_info": "Masquer les informations",
        "document.layout.show_info": "Afficher les informations",
        "document.layout.hide_actions": "Masquer actions",
        "document.layout.show_actions": "Afficher actions",
        "document.layout.reading_mode": "Mode lecture — Ctrl+Maj+R",
        "document.layout.exit_reading": "Quitter le mode lecture — Ctrl+Maj+R",
        "document.layout.pages_compact": "PAGES",
        "document.layout.info_compact": "INFOS",
        "document.layout.actions_compact": "ACTIONS",
        "document.layout.reading_compact": "LECTURE",
        "document.layout.exit_reading_compact": "SORTIR",
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
        "document.size.bytes": "{size} o",
        "document.size.kb": "{size:.1f} Ko",
        "document.size.mb": "{size:.1f} Mo",
        "document.initial.invalid": "Fichier ignoré : ouvre un PDF local valide.",
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
        "update.status.checking": "Vérification...",
        "update.status.up_to_date": "À jour",
        "update.status.update_available": "Mise à jour disponible",
        "update.status.not_verified": "Mises à jour : non vérifiées",
        "update.status.disabled": "Mises à jour désactivées",
        "update.status.not_configured": "Mises à jour non configurées",
        "update.tooltip.checking": "Vérification du manifest de version en cours.",
        "update.tooltip.up_to_date": "La version locale correspond à la dernière version publiée.",
        "update.tooltip.update_available": "Clique pour ouvrir les détails de la mise à jour.",
        "update.tooltip.not_verified": "La vérification des mises à jour n'a pas abouti.",
        "update.tooltip.disabled": "La vérification automatique est désactivée.",
        "update.tooltip.not_configured": "Aucun manifest public de version n'est configuré.",
        "update.manual.tooltip": (
            "Se connecter une fois au service de version pour rechercher une mise à jour. "
            "Aucun document ni chemin local n'est envoyé."
        ),
        "update.manual.tooltip.checking": "Recherche de mise à jour en cours.",
        "update.manual.tooltip.up_to_date": (
            "Le logiciel est à jour. Clique pour vérifier de nouveau."
        ),
        "update.manual.tooltip.update_available": (
            "Clique pour afficher les ajouts et la page officielle de téléchargement."
        ),
        "update.manual.tooltip.not_configured": (
            "Aucun canal public signé n'est encore configuré."
        ),
        "update.manual.result.title": "Recherche de mise à jour",
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
            "Le logiciel se fermera, validera la mise à jour puis redémarrera."
        ),
        "update.dialog.installed": "Version installée : {version}",
        "update.dialog.latest": "Dernière version : {version}",
        "update.dialog.source.installed": "Révision installée : {version}",
        "update.dialog.source.latest": "Révision disponible : {version}",
        "update.dialog.notes": "Notes : {notes}",
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
        "update.install.restart_failed": (
            "La mise à jour est terminée, mais PriveoPDF n'a pas pu redémarrer automatiquement."
        ),
        "update.install.reopen": "ROUVRIR PRIVEOPDF",
        "update.install.close": "FERMER",
    },
    "en": {
        "app.name": "PriveoPDF",
        "language.fr": "Français",
        "language.en": "English",
        "mode.light.action": "LIGHT MODE",
        "mode.dark.action": "DARK MODE",
        "theme.dark": "DARK",
        "theme.system": "Automatic — follow system",
        "theme.light": "LIGHT",
        "theme.dark_pro": "Dark — Clean",
        "theme.light_pro": "Light — Clean",
        "theme.light_coral": "Soft coral",
        "theme.light_ocean": "Light ocean",
        "theme.light_sage": "Soft sage",
        "theme.light_lavender": "Soft lavender",
        "theme.light_solar": "Sunlit",
        "theme.dark_midnight": "Midnight blue",
        "theme.dark_forest": "Forest night",
        "theme.dark_plum": "Plum night",
        "theme.dark_graphite": "Graphite orange",
        "theme.dark_contrast": "High contrast",
        "theme.dark_pixel": "Dark — Pixel",
        "theme.light_pixel": "Light — Pixel",
        "theme.visual_style.pro": "Sober",
        "theme.visual_style.pixel": "Pixel",
        "yes": "YES",
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
        "beta.integration.window_title": "PriveoPDF Beta — Integration ({count} PRs)",
        "beta.integration.heading": "BETA CHECKLIST",
        "beta.integration.identity": "{count} PRs integrated in this Beta.",
        "beta.integration.help": "Check only what you have verified.",
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
        "options.beta.item": "PR #{pr} · {sha} · {date}",
        "options.beta.relaunch": "RELAUNCH THIS VERSION",
        "options.beta.confirm.title": "Change Beta version",
        "options.beta.confirm.message": ("Close this Beta and relaunch PR #{pr} at SHA {sha}?"),
        "options.beta.error.title": "Beta version unavailable",
        "options.beta.error.message": (
            "This local version is incomplete or its provenance can no longer be verified. "
            "Relaunch the latest available artifact first."
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
            "Remove remembered document paths, the default output folder, window geometry, "
            "and the update cache? Source PDF files will not be deleted."
        ),
        "options.about": "ABOUT",
        "options.close": "CLOSE",
        "options.apply": "APPLY",
        "options.restart_required.title": "Restart required",
        "options.restart_required.message": (
            "The language setting was saved. Restart PriveoPDF to apply it everywhere."
        ),
        "options.local_files": "Files stay on this device.",
        "options.no_upload": "No upload for local features.",
        "options.product_promise": "Local PDF processing, no upload.",
        "about.title": "ABOUT",
        "about.tooltip": "About PriveoPDF",
        "about.product_promise": "Local PDF processing, no upload.",
        "about.no_account": "No account. No cloud.",
        "about.documents_stay": "Documents stay on this device.",
        "about.license": "Official executable — proprietary freeware license.",
        "about.third_party": "Third-party components retain their own licenses.",
        "about.copyright": "Copyright © 2026 godlittleboi",
        "first_run.title": "INITIAL SETUP WIZARD",
        "first_run.subtitle": (
            "PriveoPDF processes PDFs on this device, with no cloud dependency for local features."
        ),
        "first_run.language": "LANGUAGE",
        "first_run.theme": "THEME",
        "first_run.reduce_motion": "REDUCE MOTION",
        "first_run.update_checks": "CHECK AUTOMATICALLY FOR UPDATES",
        "first_run.update_checks.help": (
            "Uses only a configured public version manifest. No PDF files, paths, names, "
            "metadata, or document content is sent. The box is off by default and Later "
            "does not make a network connection."
        ),
        "first_run.default_output_dir": "DEFAULT OUTPUT FOLDER",
        "first_run.after_job": "AFTER PROCESSING",
        "first_run.start": "START",
        "first_run.cancel": "LATER",
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
        "community.nav.home": "Home",
        "community.nav.getting_started": "Getting started",
        "community.nav.privacy": "Privacy",
        "community.nav.faq": "FAQ",
        "community.nav.addons": "Addons",
        "community.nav.contribute": "Give feedback",
        "sidebar.local.tooltip": "100% LOCAL\nNo account. No cloud. Documents stay on this device.",
        "nav.dashboard.compact": "Home",
        "nav.dashboard.tooltip": "Home",
        "pending.badge": "COMING SOON",
        "pending.title": "Feature coming soon",
        "pending.message": "This feature is pending. It may be changed, deferred, or cancelled.",
        "pending.local_message": "This tool is not available in this version.",
        "local.badge": "100% LOCAL",
        "local.note": "No account. No cloud. Documents stay on this device.",
        "dashboard.subtitle": "Local, private, robust PDF tool. No account, no upload.",
        "dashboard.tools": "QUICK TOOLS",
        "dashboard.tools.available": "AVAILABLE TOOLS",
        "dashboard.tools.pending": "COMING NEXT",
        "dashboard.open_files": "OPEN PDFS",
        "dashboard.open_files.tooltip": "Choose one or more PDFs on this device.",
        "dashboard.search.placeholder": "Search available tools",
        "dashboard.search.accessible": "Search for an available tool",
        "dashboard.catalog.show": "ALL TOOLS",
        "dashboard.catalog.show.tooltip": "Show the nine available tools.",
        "dashboard.catalog.hide": "HIDE TOOLS",
        "dashboard.catalog.hide.tooltip": "Hide the catalog and return to recommended actions.",
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
        "dashboard.ready.help": "Choose an action.",
        "dashboard.ready.privacy": "Your files stay on your device. Nothing is sent.",
        "dashboard.ready.file_selection": "OPEN DOCUMENTS",
        "dashboard.ready.recommended_action": "RECOMMENDED ACTION",
        "dashboard.ready.other_actions": "OTHER AVAILABLE ACTIONS",
        "dashboard.ready.other_actions_single": "OTHER TOOLS FOR THIS PDF",
        "dashboard.ready.other_actions_multi": "CHECK BEFORE MERGING",
        "dashboard.ready.view_selected": "VIEW SELECTED PDF",
        "dashboard.ready.view_selected.tooltip": "View the selected PDF in open documents.",
        "dashboard.ready.selected_file": "selected",
        "dashboard.ready.page_count_one": "1 page",
        "dashboard.ready.page_count_many": "{count} pages",
        "dashboard.ready.remove_file": "REMOVE",
        "dashboard.ready.remove_file.tooltip": (
            "Remove this PDF from open documents without deleting the source file."
        ),
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
        "nav.dashboard": "HOME",
        "tool.dashboard.subtitle": "Local PDF processing, no upload.",
        "tool.view.title": "VIEW PDF",
        "tool.view.description": "Open and read a local PDF without transforming it.",
        "tool.merge.title": "MERGE PDF",
        "tool.merge.description": "Assemble several PDFs into one file.",
        "tool.merge.subtitle": "Assemble several files into one local PDF.",
        "tool.split.title": "SPLIT PDF",
        "tool.split.description": "Create several PDFs from page ranges.",
        "tool.split.subtitle": "Create several files from page ranges.",
        "tool.extract.title": "EXTRACT PAGES",
        "tool.extract.description": "Create a new PDF with selected pages in the chosen order.",
        "tool.extract.subtitle": "Choose pages and their order to generate a new PDF.",
        "tool.reorder.title": "REORDER PAGES",
        "tool.reorder.description": "Reorder every page in a PDF.",
        "tool.reorder.subtitle": "Recompose the full order of a document.",
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
        "tool.rotate.subtitle": "Apply relative rotation to pages.",
        "tool.remove.title": "REMOVE PAGES",
        "tool.remove.description": "Create a PDF without selected pages.",
        "tool.remove.subtitle": "Create a local version without selected pages.",
        "tool.compose_pdf.title": "COMPOSE A PDF",
        "tool.compose_pdf.description": ("Combine several operations in one advanced workflow."),
        "tool.scan_to_pdf.title": "SCAN TO PDF",
        "tool.scan_to_pdf.description": "Create a PDF from a local scanner.",
        "tool.compress.title": "COMPRESS PDF",
        "tool.compress.description": "Reduce the size of a local PDF.",
        "tool.repair_pdf.title": "REPAIR PDF",
        "tool.repair_pdf.description": "Try to recover a damaged PDF.",
        "tool.ocr_pdf.title": "OCR PDF",
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
        "tool.watermark.title": "WATERMARK",
        "tool.watermark.description": "Add a visible watermark to the PDF.",
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
        "tool.redact_pdf.description": "Sensitive tool to validate before promising true removal.",
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
        "tool.status.available": "AVAILABLE",
        "tool_switcher.label": "Switch tool",
        "tool_switcher.button": "TOOLS",
        "tool_switcher.all": "All tools",
        "viewer.choose_pdf": "CHOOSE PDF",
        "viewer.change_pdf": "CHANGE PDF",
        "viewer.previous": "PREVIOUS PAGE",
        "viewer.previous_short": "PREV",
        "viewer.next": "NEXT PAGE",
        "viewer.next_short": "NEXT",
        "viewer.zoom_out": "ZOOM -",
        "viewer.zoom_in": "ZOOM +",
        "viewer.zoom_value.accessible": "Zoom level",
        "viewer.zoom_value.tooltip": "Current zoom: {percent}%.",
        "viewer.zoom_invalid": "Invalid zoom: use a value between 25% and 400%.",
        "viewer.fit_menu": "FIT",
        "viewer.fit_menu.tooltip": "Choose how the page fits the viewer",
        "viewer.fit_page": "FIT PAGE",
        "viewer.fit_page_short": "PAGE",
        "viewer.fit_width": "FIT WIDTH",
        "viewer.fit_width_short": "WIDTH",
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
        "button.export": "EXPORT",
        "button.choose_files": "CHOOSE FILES",
        "button.remove": "REMOVE",
        "button.up": "UP",
        "button.down": "DOWN",
        "button.duplicate_pages": "DUPLICATE",
        "button.insert_pages": "INSERT PAGES",
        "button.blank_page": "ADD BLANK PAGE",
        "blank.loading": "{name} — reading pages...",
        "blank.ready": "{name} — {count} page(s)",
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
        "blank.output.dialog": "Choose the PDF with a blank page",
        "blank.error.incomplete": "Choose a valid PDF and an available output file.",
        "blank.progress": "Adding the blank page locally...",
        "blank.success.title": "Blank page added",
        "blank.success.message": "PDF created: {name}",
        "button.choose_output": "CHOOSE OUTPUT",
        "button.merge": "MERGE PDF",
        "button.choose_pdf": "CHOOSE PDF",
        "button.choose_folder": "CHOOSE FOLDER",
        "button.clear": "CLEAR",
        "button.view_merged_pdf": "VIEW MERGED PDF",
        "button.cancel": "Cancel",
        "button.open_download_page": "OPEN DOWNLOAD PAGE",
        "update.action.check": "CHECK FOR UPDATES",
        "update.action.checking": "CHECKING...",
        "update.action.up_to_date": "SOFTWARE UP TO DATE",
        "update.action.available": "UPDATE AVAILABLE",
        "button.extract": "CREATE THE NEW PDF",
        "button.remove_pages": "CREATE PDF WITHOUT THESE PAGES",
        "button.rotate": "ROTATE PDF",
        "button.rotate_left": "ROTATE LEFT",
        "button.rotate_right": "ROTATE RIGHT",
        "button.reorder": "REORDER PDF",
        "button.split": "SPLIT INTO SEVERAL PDFS",
        "label.page_ranges": "PAGE RANGES",
        "label.page_order": "PAGE ORDER",
        "label.rotation_angle": "ROTATION ANGLE",
        "label.rotation_angle_short": "ANGLE",
        "label.rotation_target": "PAGES",
        "label.rotation_target_short": "TARGET",
        "rotation.target.all": "All pages",
        "rotation.target.active": "Active page",
        "rotation.target.selected": "Selected pages",
        "rotation.preview_unavailable": "Preview unavailable",
        "rotation.error.no_pdf": "Choose a valid PDF before starting the operation.",
        "rotation.error.no_output": "Choose an output file.",
        "rotation.error.invalid_angle": "Unsupported angle. Use 0, 90, 180, or 270.",
        "rotation.error.no_pages": "Choose at least one page to rotate.",
        "merge.required.files": "Required step: add at least two PDFs.",
        "merge.required.output": "Required step: choose the output file.",
        "merge.ready": "Output selected. You can merge.",
        "guidance.next.choose_output": "Next step: choose output",
        "guidance.next.execute": "Next step: {action}",
        "guidance.next.view_result": "Next step: view the result",
        "merge.status.running": "Local merge...",
        "merge.dialog.output_title": "Choose the merged file",
        "merge.error.no_files": "Choose at least two PDFs to merge.",
        "merge.error.no_output": "Choose an output file before merging.",
        "merge.success.title": "Merge complete",
        "merge.error.title": "Merge unavailable",
        "visual.source_pdf": "SOURCE PDF",
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
        "page.merge.help": "Drop several PDFs or choose them in the expected order.",
        "page.reorder.help": (
            "Example: 3,1,1,2,4-6. Every source page must appear at least once; "
            "repeat a number to duplicate that page."
        ),
        "insert.primary.title": "1. MAIN PDF",
        "insert.primary.empty": "Choose the PDF that will receive the new pages.",
        "insert.source.title": "2. PDF TO INSERT",
        "insert.source.empty": "Choose another PDF, then select its pages.",
        "insert.document.loading": "{name} — reading pages...",
        "insert.document.ready": "{name} — {count} page(s)",
        "insert.position.title": "3. INSERTION POSITION",
        "insert.position.start": "Before the first page",
        "insert.position.after": "After page {page}",
        "insert.position.end": "After the last page ({page})",
        "insert.summary.empty": "Select at least one page from the second PDF.",
        "insert.summary.start": "at the beginning",
        "insert.summary.after": "after page {page}",
        "insert.summary.ready": (
            "Page(s) {pages} from the second PDF inserted {position}. "
            "The result will contain {total} pages."
        ),
        "insert.output.dialog": "Choose the PDF with inserted pages",
        "insert.progress": "Local insertion...",
        "insert.success.title": "Insertion complete",
        "insert.success.message": "{name} was created without modifying the source PDFs.",
        "insert.error.primary": "Choose a valid main PDF.",
        "insert.error.source": "Choose a valid second PDF.",
        "insert.error.same_file": "Choose two different PDF files.",
        "insert.error.selection": "Select at least one page from the second PDF.",
        "insert.error.position": "Choose a valid insertion position.",
        "insert.error.output": "Choose an output file.",
        "error.operation.title": "Operation unavailable",
        "output.none_file": "No output file selected",
        "output.none_dir": "No output folder selected",
        "output.panel.title": "OUTPUT",
        "output.panel.destination": "File destination",
        "output.panel.status_title": "STATUS",
        "input.none_pdf": "No PDF selected",
        "page_count.empty": "Pages: -",
        "page_count.loading": "Pages: reading...",
        "page_count.value": "Pages: {count}",
        "document.title": "DOCUMENT",
        "document.empty.title": "No document open",
        "document.empty.meta": "Open a local PDF to enter document mode.",
        "document.meta": "{pages} · {size}",
        "document.badge.local": "Local",
        "document.badge.selectable_text": "Text detected",
        "document.badge.selectable_text.tooltip": (
            "Extractable text detected locally on a PDF sample."
        ),
        "document.badge.probable_scan": "Probable scanned document",
        "document.badge.probable_scan.compact": "Probable scan",
        "document.badge.probable_scan.tooltip": (
            "Local analysis indicates this PDF probably looks like a scan."
        ),
        "document.badge.protected_pdf": "Protected PDF",
        "document.badge.analysis_unavailable": "Analysis unavailable",
        "document.thumbnails": "PAGES",
        "document.info.title": "DOCUMENT INFO",
        "document.actions.title": "ACTIONS",
        "document.source_intact": "The original stays intact. Tools create a copy.",
        "document.action.organize": "Organize",
        "document.action.sign": "Annotate / sign",
        "document.action.searchable": "Make searchable",
        "document.action.compress": "Compress",
        "document.action.convert": "Convert",
        "document.action.protect": "Protect",
        "document.action.more": "More",
        "document.layout.hide_pages": "Hide pages",
        "document.layout.show_pages": "Show pages",
        "document.layout.hide_info": "Hide document information",
        "document.layout.show_info": "Show document information",
        "document.layout.hide_actions": "Hide actions",
        "document.layout.show_actions": "Show actions",
        "document.layout.reading_mode": "Reading mode — Ctrl+Shift+R",
        "document.layout.exit_reading": "Exit reading mode — Ctrl+Shift+R",
        "document.layout.pages_compact": "PAGES",
        "document.layout.info_compact": "INFO",
        "document.layout.actions_compact": "ACTIONS",
        "document.layout.reading_compact": "READ",
        "document.layout.exit_reading_compact": "EXIT",
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
        "document.size.bytes": "{size} B",
        "document.size.kb": "{size:.1f} KB",
        "document.size.mb": "{size:.1f} MB",
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
        "update.status.checking": "Checking...",
        "update.status.up_to_date": "Up to date",
        "update.status.update_available": "Update available",
        "update.status.not_verified": "Updates: not checked",
        "update.status.disabled": "Updates disabled",
        "update.status.not_configured": "Updates not configured",
        "update.tooltip.checking": "Checking the version manifest.",
        "update.tooltip.up_to_date": "The local version matches the latest published version.",
        "update.tooltip.update_available": "Click to open update details.",
        "update.tooltip.not_verified": "The update check did not complete.",
        "update.tooltip.disabled": "Automatic update checks are disabled.",
        "update.tooltip.not_configured": "No public version manifest is configured.",
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
        "update.manual.result.title": "Update check",
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
            "The software will close, validate the update, and then restart."
        ),
        "update.dialog.installed": "Installed version: {version}",
        "update.dialog.latest": "Latest version: {version}",
        "update.dialog.source.installed": "Installed revision: {version}",
        "update.dialog.source.latest": "Available revision: {version}",
        "update.dialog.notes": "Notes: {notes}",
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
