"""Interface d'inventaire physique : comptage, écarts et approbation distincte."""
from __future__ import annotations

import logging
from decimal import Decimal, InvalidOperation

import pandas as pd
import streamlit as st

from modules.stocks.inventory_service import (
    InventoryError, approve_inventory, count_article, create_inventory,
    inventory_lines, inventory_lots, count_inventory_lot,
    import_inventory_counts, lot_reconciliation, list_inventories,
    new_inventory_id, submit_inventory, summarize_inventory,
)

_LOG = logging.getLogger(__name__)


def show_inventory_panel(user_id: str, can_write: bool) -> None:
    st.subheader("📋 Inventaires physiques MP / PF")
    st.caption(
        "Campagne datée, comptage réel, comparaison au stock théorique et "
        "double validation. **Aucune régularisation automatique des stocks ni "
        "écriture comptable n'est réalisée.**"
    )
    if can_write:
        with st.expander("Nouvelle campagne d'inventaire", expanded=False):
            with st.form("erp56_new_inventory"):
                label = st.text_input("Libellé de campagne", max_chars=160,
                                      placeholder="Inventaire fin de mois")
                category = st.selectbox("Périmètre", ["TOUS", "MP", "PF"],
                                        format_func=lambda x: {
                                            "TOUS": "Matières, emballages et produits finis",
                                            "MP": "Matières premières et emballages",
                                            "PF": "Produits finis (SKU)",
                                        }[x])
                create = st.form_submit_button("Créer une photographie des stocks")
            if create:
                key = f"erp56_pending_create_{user_id}"
                pending = st.session_state.get(key)
                if not isinstance(pending, dict):
                    pending = {"id": new_inventory_id(), "category": category, "label": label}
                    st.session_state[key] = pending
                if pending["category"] != category or pending["label"] != label:
                    st.error("Une création précédente reste à vérifier. Reprendre ses paramètres avant de changer.")
                else:
                    try:
                        result = create_inventory(category, label, campaign_id=pending["id"])
                    except (PermissionError, ValueError, InventoryError, RuntimeError, TypeError) as exc:
                        _LOG.warning("Création inventaire non confirmée (%s)", type(exc).__name__)
                        st.error("Création non confirmée. Vérifier la campagne avant tout nouvel essai.")
                    else:
                        st.session_state.pop(key, None)
                        st.success(f"Campagne {result['inventaire_id']} créée : {result['lignes']} lignes.")
    try:
        campaigns = list_inventories()
    except (PermissionError, InventoryError, RuntimeError, ValueError, TypeError) as exc:
        _LOG.warning("Inventaires non consultables (%s)", type(exc).__name__)
        st.error("Inventaires indisponibles ou droits non vérifiables.")
        return
    if not campaigns:
        st.info("Aucune campagne d'inventaire créée.")
        return
    # Écran de synthèse sans identités nominatives superflues.
    brief = pd.DataFrame([
        {"Référence": item.get("inventaire_id"), "Libellé": item.get("libelle"),
         "Périmètre": item.get("categorie"), "Statut": item.get("statut"),
         "Photographie": item.get("date_snapshot")}
        for item in campaigns
    ])
    st.dataframe(brief, use_container_width=True, hide_index=True)
    ids = [c["inventaire_id"] for c in campaigns]
    selected = st.selectbox("Campagne à consulter", ids,
                            key="erp56_campaign_selected")
    try:
        campaign, lines = inventory_lines(selected)
        lots = inventory_lots(selected)
        reconciliation = lot_reconciliation(lines, lots)
        summary = summarize_inventory(lines)
    except (PermissionError, InventoryError, RuntimeError, ValueError,
            TypeError, KeyError, InvalidOperation) as exc:
        _LOG.warning("Dossier inventaire illisible (%s)", type(exc).__name__)
        st.error("Campagne non vérifiable : aucun résultat partiel affiché.")
        return
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Articles", summary["lignes"])
    c2.metric("Comptés", summary["comptees"])
    c3.metric("Lignes avec écart", summary["ecarts"])
    c4.metric("Écart net valorisé", (
        f"{Decimal(summary['valeur_ecart_dzd']):,.2f} DZD"
        if summary["valeur_ecart_dzd"] is not None else "Non valorisable"
    ))
    st.caption(
        "L'écart valorisé peut comporter des coûts manquants ; "
        "ce rapport est un **état de gestion**, pas un justificatif SCF."
    )
    export_rows = []
    for row in lines:
        qty = row.get("quantite_comptee")
        delta = (Decimal(str(qty)) - Decimal(str(row["quantite_theorique"]))
                 if qty is not None else None)
        cost = row.get("pmp_snapshot")
        value = delta * Decimal(str(cost)) if delta is not None and cost is not None else None
        export_rows.append({
            "type_article": row["type_article"], "article_id": row["article_id"],
            "stock_theorique": str(row["quantite_theorique"]),
            "quantite_comptee": str(qty) if qty is not None else None,
            "ecart_quantite": str(delta) if delta is not None else None,
            "pmp_snapshot_dzd": str(cost) if cost is not None else None,
            "ecart_valorise_dzd": str(value) if value is not None else None,
            "motif_ecart": row.get("motif_ecart"),
            "date_comptage": row.get("compte_le"),
        })
    df = pd.DataFrame(export_rows)
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.subheader("Traçabilité et comptage par lot")
    st.caption("Lots figés à la création de la campagne. La nomenclature des dépôts "
               "n'existe pas encore ; aucune ventilation géographique théorique n'est inventée.")
    if reconciliation["articles_non_reconcilies"]:
        st.warning(
            f"{reconciliation['articles_non_reconcilies']} article(s) sans rapprochement "
            "complet stock / lots. La validation finale est bloquée jusqu'à résolution "
            "des écarts de traçabilité."
        )
    lot_cols = ["lot_id", "type_article", "article_id", "quantite_theorique",
                "quantite_comptee", "statut_snapshot", "date_peremption_snapshot",
                "motif_ecart"]
    if lots:
        st.dataframe(pd.DataFrame(lots)[lot_cols],
                     use_container_width=True, hide_index=True)
    else:
        st.info("Aucun lot physique photographié pour ce périmètre.")
    if st.checkbox("Afficher le rapprochement stock / lots", value=False,
                   key="erp57_lot_reconciliation_show"):
        st.dataframe(pd.DataFrame(reconciliation["lignes"]),
                     use_container_width=True, hide_index=True)
    if lots:
        lot_fmt = st.selectbox(
            "Exporter les lots",
            ("Excel (.xlsx)", "CSV (.csv)", "PDF (.pdf)"),
            key="erp57_lot_export_format",
        )
        if st.button("Préparer l'état des lots", key="erp57_lot_export_prepare"):
            from core.export_formats import build_export, export_filename, ExportError
            try:
                ext = lot_fmt.split("(")[1].split(")")[0].lstrip(".")
                data, mime, ext = build_export(
                    [{key: lot.get(key) for key in lot_cols} for lot in lots],
                    lot_cols, fmt=ext, title=f"Lots de l'inventaire {selected}",
                    warning="PHOTOGRAPHIE ET COMPTAGES - NON CERTIFIÉS SCF",
                )
            except (ExportError, ValueError, TypeError):
                st.error("État de lots trop volumineux ou non vérifiable.")
            else:
                st.download_button(
                    f"Télécharger les lots {lot_fmt}", data=data, mime=mime,
                    file_name=export_filename(f"Lots_{selected}", ext),
                    key="erp57_lot_export_download",
                )
    fmt = st.selectbox("Exporter cet inventaire",
                       ("Excel (.xlsx)", "CSV (.csv)", "PDF (.pdf)"),
                       key="erp56_export_format")
    if st.button("Préparer le fichier d'inventaire", key="erp56_export_prepare"):
        from core.export_formats import build_export, export_filename, ExportError
        try:
            ext = fmt.split("(")[1].split(")")[0].lstrip(".")
            payload, mime, ext = build_export(
                export_rows, list(df.columns), fmt=ext,
                title=f"Inventaire {selected} — {campaign['statut']}",
                warning="COMPTAGE NON CERTIFIÉ SCF — aucun mouvement de régularisation",
            )
        except (ExportError, ValueError, TypeError) as exc:
            st.error("Export inventaire impossible : volume ou données incompatibles.")
        else:
            st.download_button(
                f"Télécharger {fmt}", data=payload, mime=mime,
                file_name=export_filename(f"Inventaire_{selected}", ext),
                key="erp56_export_download",
            )
    if not can_write:
        st.info("Profil Stocks en lecture seule : comptages et validations interdits.")
        return
    if campaign["statut"] == "OUVERT":
        with st.expander("Importer les comptages depuis Excel — prévisualisation", expanded=False):
            from modules.stocks.inventory_excel import (
                InventoryImportError, export_count_template, parse_count_workbook,
            )
            st.caption("Classeur XLSX vierge, 500 quantités par import maximum, "
                       "aucune formule autorisée. Les lignes non renseignées sont ignorées.")
            try:
                model = export_count_template(lines, campaign_id=selected)
            except InventoryImportError:
                st.error("Modèle indisponible : photographie invalide.")
            else:
                st.download_button(
                    "Télécharger le modèle Excel de comptage", data=model,
                    file_name=f"NEXTGEN_Comptage_{selected}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="erp57_import_template",
                )
            uploaded = st.file_uploader(
                "Choisir le fichier de comptages complété (.xlsx)",
                type=["xlsx"], key=f"erp57_import_upload_{selected}",
            )
            if uploaded is not None:
                try:
                    proposed = parse_count_workbook(uploaded.getvalue(), lines, campaign_id=selected)
                except InventoryImportError as exc:
                    st.error(f"Fichier refusé : {exc}")
                else:
                    st.info(f"{len(proposed)} ligne(s) validée(s) en prévisualisation. "
                            "Aucune donnée n'est encore enregistrée.")
                    st.dataframe(pd.DataFrame(proposed), use_container_width=True,
                                 hide_index=True)
                    if st.button("Importer atomiquement ces comptages", type="primary",
                                 key="erp57_import_confirm"):
                        try:
                            result = import_inventory_counts(selected, proposed)
                        except (ValueError, PermissionError, InventoryError, RuntimeError,
                                TypeError):
                            st.error("Import non confirmé : consulter le dossier et "
                                     "réutiliser exactement le même fichier pour reprendre.")
                        else:
                            st.success(
                                f"{result['lignes_mises_a_jour']} comptages enregistrés. "
                                "Aucun stock modifié."
                            )
        if lots:
            with st.form("erp57_lot_count_form"):
                choices = {r["lot_id"]: r for r in lots}
                lot_id = st.selectbox(
                    "Lot physique à compter", list(choices),
                    format_func=lambda x: (
                        f"{x} — {choices[x]['type_article']}/"
                        f"{choices[x]['article_id']} : {choices[x]['quantite_theorique']}"
                    ),
                )
                counted_lot = st.text_input(
                    "Quantité constatée pour ce lot",
                    value=(str(choices[lot_id]["quantite_comptee"])
                           if choices[lot_id].get("quantite_comptee") is not None else ""),
                    max_chars=45,
                )
                lot_motif = st.text_area(
                    "Justification de l'écart de lot", max_chars=600,
                )
                submit_lot = st.form_submit_button("Enregistrer le comptage du lot")
            if submit_lot:
                try:
                    count_inventory_lot(selected, lot_id, counted_lot, lot_motif)
                except (ValueError, PermissionError, InventoryError, RuntimeError,
                        TypeError):
                    st.error("Comptage de lot refusé : quantité, justification ou droits invalides.")
                else:
                    st.success("Lot compté ; recharger l'inventaire pour actualiser les écarts.")
        remaining = [x for x in lines if x.get("quantite_comptee") is None]
        lots_remaining = reconciliation["lots_non_comptes"]
        with st.form("erp56_count_form"):
            label_map = {
                f"{row['type_article']}|{row['article_id']}": row
                for row in lines
            }
            choice = st.selectbox(
                "Article à compter (MP ou SKU)",
                list(label_map),
                format_func=lambda x: (
                    f"{x} — théorique {label_map[x]['quantite_theorique']}"
                ),
            )
            number = st.text_input(
                "Quantité physiquement comptée (zéro autorisé)",
                value=(str(label_map[choice]["quantite_comptee"])
                       if label_map[choice].get("quantite_comptee") is not None else ""),
                max_chars=40,
            )
            reason = st.text_area(
                "Observation / justification (obligatoire en cas d'écart)",
                max_chars=600,
            )
            count = st.form_submit_button("Enregistrer le comptage")
        if count:
            try:
                number_dec = Decimal(number.strip())
                expected = Decimal(str(label_map[choice]["quantite_theorique"]))
                if not number_dec.is_finite() or number_dec < 0:
                    raise ValueError("Quantité non valide")
                if number_dec != expected and len(reason.strip()) < 5:
                    raise ValueError("Justification obligatoire en cas d'écart")
                row = label_map[choice]
                count_article(
                    selected, row["type_article"], row["article_id"],
                    str(number_dec), reason,
                )
            except (ValueError, InvalidOperation, PermissionError, InventoryError,
                    RuntimeError, TypeError) as exc:
                _LOG.warning("Comptage refusé (%s)", type(exc).__name__)
                st.error("Comptage non enregistré : quantité, justification ou droits invalides.")
            else:
                st.success("Comptage enregistré. Recharger l'écran pour voir les écarts actualisés.")
        if remaining or lots_remaining:
            st.warning(
                f"Soumission impossible : {len(remaining)} article(s) et "
                f"{lots_remaining} lot(s) non comptés."
            )
        else:
            st.info("Tous les articles et lots photographiés possèdent un comptage.")
        if st.button("Soumettre pour double validation",
                     disabled=bool(remaining or lots_remaining),
                     key="erp56_submit"):
            try:
                submit_inventory(selected)
            except (ValueError, PermissionError, InventoryError, RuntimeError, TypeError):
                st.error("Soumission non confirmée : vérifier la campagne avant de réessayer.")
            else:
                st.success("Campagne soumise à un valideur différent.")
    elif campaign["statut"] == "SOUMIS":
        st.warning("Campagne figée ; double validation réservée à un administrateur distinct. "
                   "Tout manque de traçabilité des lots bloque aussi l'approbation.")
        if user_id in {campaign.get("createur_id"), campaign.get("soumis_par")}:
            st.info("Séparation des tâches : vous ne pouvez pas approuver votre propre campagne.")
            return
        with st.form("erp56_approve"):
            note = st.text_area("Justification de validation (minimum 10 caractères)",
                                max_chars=600)
            accept = st.form_submit_button("Valider le constat sans régulariser les stocks")
        if accept:
            try:
                result = approve_inventory(selected, note)
            except (ValueError, PermissionError, InventoryError, RuntimeError, TypeError):
                st.error("Approbation refusée : droits, dérive du stock ou dossier incomplet.")
            else:
                st.success(
                    f"Constat validé : {result['statut']}. "
                    "Aucun ajustement du stock n'a été appliqué."
                )
    else:
        st.info("Inventaire validé en lecture seule. Les écarts attendent une procédure "
                "distincte de régularisation par lot et coût justifié.")
