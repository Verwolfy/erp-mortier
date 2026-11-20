"""Interface d'inventaire physique : comptage, écarts et approbation distincte."""
from __future__ import annotations

import logging
from decimal import Decimal, InvalidOperation

import pandas as pd
import streamlit as st

from modules.stocks.inventory_service import (
    InventoryError, approve_inventory, count_article, create_inventory,
    inventory_lines, list_inventories, new_inventory_id, submit_inventory,
    summarize_inventory,
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
        remaining = [x for x in lines if x.get("quantite_comptee") is None]
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
        if remaining:
            st.warning(f"{len(remaining)} articles non comptés : soumission impossible.")
        else:
            st.info("Tous les articles possèdent un comptage.")
        if st.button("Soumettre pour double validation", disabled=bool(remaining),
                     key="erp56_submit"):
            try:
                submit_inventory(selected)
            except (ValueError, PermissionError, InventoryError, RuntimeError, TypeError):
                st.error("Soumission non confirmée : vérifier la campagne avant de réessayer.")
            else:
                st.success("Campagne soumise à un valideur différent.")
    elif campaign["statut"] == "SOUMIS":
        st.warning("Campagne figée ; double validation réservée à un administrateur distinct.")
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
