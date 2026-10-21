"""Interface Production : droits vérifiés, recettes par unité, clôture d'OF idempotente.

Aucune donnée métier n'est lue avant l'autorisation Supabase. La convention SQL
est : lignes_recette.quantite_par_unite = quantité de MP PAR unité de PF.
Le formulaire peut saisir une recette par batch, mais convertit explicitement
la quantité de chaque matière en quantité par unité de produit.
"""
from __future__ import annotations

from copy import deepcopy
from decimal import Decimal, InvalidOperation
import logging

import pandas as pd
import streamlit as st

from config.roles import has_permission
from core.db_service import fetch_data, get_supabase_client
from core.utils import get_local_now
from modules.production.service import (
    create_recette, create_ordre_fabrication, get_recettes,
    get_ordres_fabrication, changer_statut_of, enregistrer_controle_qualite,
    get_lignes_recette, get_consommations_of, get_controles_qualite,
)

_LOG = logging.getLogger(__name__)
_ACTIVE = frozenset({"oui", "true", "1", "actif", "active", "yes"})
_VALID_STATES = frozenset({"PLANIFIE", "EN_COURS", "TERMINE", "REJETE", "CONTROLE_QUALITE"})


def _production_access() -> tuple[str, bool, bool] | None:
    """Vérifie l'utilisateur et son rôle ACTUEL dans Supabase avant toute lecture."""
    try:
        if st.session_state.get("authenticated") is not True:
            return None
        session_user = st.session_state.get("user")
        if not isinstance(session_user, dict):
            return None
        user_id = session_user.get("user_id")
        if not isinstance(user_id, str) or not user_id.strip():
            return None
        response = (get_supabase_client().table("users")
                    .select("user_id,role,actif")
                    .eq("user_id", user_id).limit(1).execute())
        records = response.data or []
        if len(records) != 1 or not isinstance(records[0], dict):
            return None
        user = records[0]
        if user.get("user_id") != user_id:
            return None
        active = user.get("actif")
        if active is not True and str(active).strip().casefold() not in _ACTIVE:
            return None
        role = user.get("role")
        if not isinstance(role, str) or not role.strip():
            return None
        if has_permission(role, "Production", "lecture") is not True:
            return None
        can_write = has_permission(role, "Production", "ecriture") is True
        can_stock = has_permission(role, "Stocks", "ecriture") is True if can_write else False
        return user_id, can_write, can_stock
    except Exception as exc:
        _LOG.warning("Autorisation Production non vérifiable (%s)", type(exc).__name__)
        return None


def get_produits_actifs() -> pd.DataFrame:
    df = pd.DataFrame(fetch_data("produits"))
    return df[df["actif"] == "OUI"] if not df.empty and "actif" in df.columns else pd.DataFrame()


def get_mp_actives() -> pd.DataFrame:
    df = pd.DataFrame(fetch_data("matieres_premieres"))
    return df[df["actif"] == "OUI"] if not df.empty and "actif" in df.columns else pd.DataFrame()


def get_skus_actifs() -> pd.DataFrame:
    df = pd.DataFrame(fetch_data("sku_conditionnement"))
    return df[df["actif"] == "OUI"] if not df.empty and "actif" in df.columns else pd.DataFrame()


def _decimal(value: object, field: str, *, allow_zero: bool = False) -> Decimal:
    if isinstance(value, bool) or len(str(value)) > 64:
        raise ValueError(f"{field} invalide")
    try:
        n = Decimal(str(value))
    except (TypeError, InvalidOperation, ValueError) as exc:
        raise ValueError(f"{field} invalide") from exc
    if not n.is_finite() or n >= Decimal("1e15") or (n < 0 if allow_zero else n <= 0):
        raise ValueError(f"{field} doit être positif et fini")
    return n


def _line_per_unit(quantity_per_batch: object, batch_yield: object) -> float:
    """Conversion dimensionnelle : quantité MP / quantité PF (sans supposer kg=L)."""
    qty = _decimal(quantity_per_batch, "Quantité par batch")
    yield_qty = _decimal(batch_yield, "Rendement du batch")
    per_unit = qty / yield_qty
    if per_unit <= 0 or per_unit.as_tuple().exponent < -12:
        raise ValueError("Précision insuffisante pour la quantité par unité")
    return float(per_unit)


def _cart_key(user_id: str) -> str:
    return f"production_recette_cart_{user_id}"


def _document_key(kind: str, user_id: str) -> str:
    if kind not in {"recette", "of"}:
        raise ValueError("Document inconnu")
    return f"production_document_{kind}_{user_id}"


def _document_panel(kind: str, user_id: str) -> bool:
    """La création de recettes/OF n'est PAS idempotente côté SQL : jamais de retry auto."""
    key = _document_key(kind, user_id)
    record = st.session_state.get(key)
    if record is None:
        return False
    if not isinstance(record, dict) or record.get("status") not in {"uncertain", "confirmed"}:
        st.error("Dossier de création illisible. Faire intervenir l'administrateur.")
        return True
    if record["status"] == "uncertain":
        st.error("Création non confirmée : vérifier le document et ses lignes dans Supabase. Ne PAS réessayer ici.")
        if st.checkbox("J'ai vérifié le résultat dans Supabase", key=f"verify_{kind}_{user_id}"):
            if st.button("Terminer la vérification", key=f"reset_{kind}_{user_id}"):
                del st.session_state[key]
                st.rerun()
    else:
        st.success(f"Document {record['document_id']} créé.")
        if st.button("Préparer un nouveau document", key=f"new_{kind}_{user_id}"):
            del st.session_state[key]
            st.rerun()
    return True


def _create_document(kind: str, user_id: str, payload: dict) -> None:
    key = _document_key(kind, user_id)
    if key in st.session_state:
        st.error("Un document est déjà en attente de vérification.")
        return
    # Stocker la demande avant son exécution. Aucun operation_id côté service.
    record = {"status": "uncertain", "payload": deepcopy(payload)}
    st.session_state[key] = record
    try:
        if kind == "recette":
            doc_id = create_recette(**deepcopy(payload))
        else:
            doc_id = create_ordre_fabrication(**deepcopy(payload))
        if not isinstance(doc_id, str) or not doc_id.strip():
            raise RuntimeError("Identifiant du document non confirmé")
    except Exception as exc:
        _LOG.warning("Création Production non confirmée (%s)", type(exc).__name__)
        st.error("Création non confirmée : vérifier le document en base avant toute nouvelle tentative.")
        return
    record["status"] = "confirmed"
    record["document_id"] = doc_id
    if kind == "recette":
        st.session_state.pop(_cart_key(user_id), None)
    st.cache_data.clear()
    st.rerun()


def _closure_key(user_id: str) -> str:
    return f"production_cloture_{user_id}"


def _execute_closure(user_id: str, can_stock: bool) -> None:
    """En cas de timeout, même OF et MÊMES paramètres (SQL idempotent par of_id)."""
    key = _closure_key(user_id)
    record = st.session_state[key]
    if record["status"] == "confirmed":
        return
    payload = record["payload"]
    if payload["conforme"] == "OUI" and not can_stock:
        st.error("Droits Stocks requis pour finaliser un OF conforme.")
        return
    try:
        result = enregistrer_controle_qualite(**deepcopy(payload))
        if not isinstance(result, dict) or result.get("of_id") != payload["of_id"] \
                or result.get("statut") != ("TERMINE" if payload["conforme"] == "OUI" else "REJETE"):
            raise RuntimeError("Réponse de clôture non vérifiable")
    except (ValueError, PermissionError) as exc:
        # Émises avant l'appel RPC par le service : l'utilisateur peut corriger.
        _LOG.warning("Clôture rejetée avant exécution (%s)", type(exc).__name__)
        del st.session_state[key]
        st.error("Clôture refusée : vérifiez les données et les autorisations.")
        return
    except Exception as exc:
        _LOG.warning("Clôture OF non confirmée (%s)", type(exc).__name__)
        record["status"] = "uncertain"
        st.error("Résultat incertain : consulter l'OF en base puis reprendre uniquement avec les mêmes paramètres.")
        return
    record["status"] = "confirmed"
    record["result"] = deepcopy(result)
    st.cache_data.clear()
    st.rerun()


def _closure_panel(user_id: str, can_stock: bool) -> bool:
    key = _closure_key(user_id)
    record = st.session_state.get(key)
    if record is None:
        return False
    valid = (isinstance(record, dict)
             and record.get("status") in {"uncertain", "confirmed"}
             and isinstance(record.get("payload"), dict)
             and {"of_id", "conforme", "remarques", "controleur", "quantite_produite",
                  "emballage_mp_id", "emballage_consomme"}.issubset(record["payload"]))
    if not valid:
        st.error("Dossier de clôture illisible. Demander une vérification à l'administrateur.")
        return True
    p = record["payload"]
    st.info(f"OF {p['of_id']} — contrôle qualité {p['conforme']}")
    if record["status"] == "uncertain":
        st.warning("Clôture non confirmée : ne pas modifier la quantité ni le contrôle qualité.")
        st.write("Vérifiez d'abord l'état de l'OF dans Supabase. La reprise rejoue la même demande.")
        if st.button("Réessayer la même clôture", key=f"retry_close_{user_id}"):
            _execute_closure(user_id, can_stock)
    else:
        st.success(f"OF {p['of_id']} clôturé et confirmé.")
        if st.button("Traiter un autre OF", key=f"next_close_{user_id}"):
            del st.session_state[key]
            st.rerun()
    return True


def _start_closure(user_id: str, payload: dict, can_stock: bool) -> None:
    key = _closure_key(user_id)
    if key in st.session_state:
        st.error("Une clôture reste à traiter.")
        return
    st.session_state[key] = {"status": "uncertain", "payload": deepcopy(payload)}
    _execute_closure(user_id, can_stock)


def _recipe_tab(user_id: str, can_write: bool, products: pd.DataFrame, materials: pd.DataFrame) -> None:
    st.subheader("Nouvelle recette")
    st.info("Les quantités sont saisies PAR BATCH, puis sauvegardées PAR UNITÉ produite, comme l'exige le service.")
    if not can_write:
        st.info("Mode lecture seule")
        return
    if _document_panel("recette", user_id):
        return
    if products.empty or materials.empty:
        st.warning("Configurer d'abord les produits et matières premières actifs.")
        return
    pf_labels = {r["pf_id"]: f"{r['pf_id']} - {r['nom']}" for _, r in products.iterrows()}
    pf_id = st.selectbox("Produit fabriqué", list(pf_labels), format_func=lambda x: pf_labels[x])
    pf_row = products[products["pf_id"] == pf_id].iloc[0]
    production_unit = str(pf_row.get("unite_production") or "").strip()
    version = st.text_input("Version", value="v1.0")
    yield_qty = st.number_input(f"Rendement par batch ({production_unit or 'unité PF'})", min_value=0.001,
                                value=1000.0, step=10.0)
    instructions = st.text_area("Instructions de fabrication")
    cart_key = _cart_key(user_id)
    batch = str(yield_qty)
    cart = st.session_state.get(cart_key)
    if not isinstance(cart, dict) or cart.get("pf_id") != pf_id or cart.get("yield") != batch:
        if isinstance(cart, dict) and cart.get("lines"):
            st.warning("Produit ou rendement modifié : l'ancien panier a été réinitialisé pour éviter un calcul erroné.")
        cart = {"pf_id": pf_id, "yield": batch, "lines": []}
        st.session_state[cart_key] = cart

    components = materials[materials["categorie_mp"] != "EMBALLAGE_CONSOMMABLE"] \
        if "categorie_mp" in materials.columns else materials
    if components.empty:
        st.warning("Aucune matière première hors emballage disponible.")
        return
    labels = {r["mp_id"]: f"{r['mp_id']} - {r['nom']} ({r.get('unite_stock', '?')})"
              for _, r in components.iterrows()}
    mp_id = st.selectbox("Composant", list(labels), format_func=lambda x: labels[x])
    qte = st.number_input("Quantité MP nécessaire pour le batch (dans l'unité de stock de la MP)",
                          min_value=0.000001, step=1.0)
    if st.button("Ajouter le composant", key=f"add_recipe_{user_id}"):
        if mp_id in {line["mp_id"] for line in cart["lines"]}:
            st.error("Matière déjà présente : évitez les lignes en double.")
        else:
            line = components[components["mp_id"] == mp_id].iloc[0]
            cart["lines"].append({"mp_id": mp_id, "nom_mp": line.get("nom", mp_id),
                                  "unite_stock": str(line.get("unite_stock") or ""),
                                  "quantite_batch": float(_decimal(qte, "Quantité"))})
            st.rerun()
    if not cart["lines"]:
        st.info("Ajoutez les composants de la recette.")
        return

    st.dataframe(pd.DataFrame(cart["lines"]), hide_index=True, use_container_width=True)
    if st.button("Vider la recette", key=f"clear_recipe_{user_id}"):
        cart["lines"] = []
        st.rerun()

    # Un bilan de masse n'est fiable que lorsque TOUTES les quantités sont en kg.
    # Sans densité ou conversion explicite, ne pas additionner litres et kilogrammes.
    unit_keys = {line["unite_stock"].strip().casefold() for line in cart["lines"]}
    balance_available = production_unit.strip().casefold() in {"kg", "kilogramme", "kilogrammes"} \
        and all(x in {"kg", "kilogramme", "kilogrammes"} for x in unit_keys)
    if balance_available:
        sum_mp = sum((_decimal(line["quantite_batch"], "MP") for line in cart["lines"]), Decimal(0))
        delta = sum_mp - _decimal(yield_qty, "Rendement")
        st.metric("Écart massique du batch (kg)", f"{delta:+.3f}")
        if delta != 0:
            st.warning("Écart de masse à justifier : matières non incluses, pertes ou rendement incorrect.")
    else:
        st.warning("Bilan de masse désactivé : unités hétérogènes ou différentes de kg. Vérifier les unités et densités avant validation métier.")

    confirmed = st.checkbox("Je confirme les quantités, les unités et le rendement de ce batch",
                            key=f"recipe_unit_ack_{user_id}_{pf_id}_{batch}")
    if st.button("Sauvegarder la recette", key=f"save_recipe_{user_id}", disabled=not confirmed):
        try:
            lines = [{"mp_id": line["mp_id"],
                      "quantite_par_unite": _line_per_unit(line["quantite_batch"], yield_qty)}
                     for line in cart["lines"]]
            payload = {"pf_id": pf_id, "version": version,
                       "rendement_unite": float(_decimal(yield_qty, "Rendement")),
                       "instructions": instructions, "panier_lignes": lines}
            _create_document("recette", user_id, payload)
        except ValueError as exc:
            st.error(str(exc))


def _of_tab(user_id: str, can_write: bool, products: pd.DataFrame, skus: pd.DataFrame) -> None:
    st.subheader("Créer un ordre de fabrication")
    if not can_write:
        st.info("Mode lecture seule")
        return
    if _document_panel("of", user_id):
        return
    recipes = get_recettes()
    if products.empty or skus.empty or recipes.empty:
        st.warning("Produits, SKU ou recettes actifs manquants.")
        return
    product_names = {r["pf_id"]: r["nom"] for _, r in products.iterrows()}
    labels = {r["sku_id"]: f"{product_names.get(r['pf_id'], 'Produit inconnu')} - {r.get('format', '')} ({r['sku_id']})"
              for _, r in skus.iterrows()}
    sku = st.selectbox("SKU", list(labels), format_func=lambda x: labels[x])
    sku_row = skus[skus["sku_id"] == sku].iloc[0]
    pf_id = sku_row["pf_id"]
    if not _sku_unit_safe(sku_row, products):
        st.error("Conversion SKU ↔ unité de production non prise en charge : création d’OF bloquée jusqu’à validation métier et SQL.")
        return
    matches = recipes[(recipes["pf_id"] == pf_id) & (recipes["actif"] == "OUI")]
    if matches.empty:
        st.warning("Aucune recette active pour ce produit.")
        return
    recipes_dict = {r["recette_id"]: f"{r['version']} (batch : {r['rendement_unite']})"
                    for _, r in matches.iterrows()}
    with st.form(f"new_of_{user_id}"):
        recipe = st.selectbox("Recette", list(recipes_dict), format_func=lambda x: recipes_dict[x])
        quantity = st.number_input("Quantité prévue (unités SKU)", min_value=1.0, step=1.0)
        date_planif = st.date_input("Date planifiée")
        notes = st.text_input("Notes de fabrication")
        st.warning("Vérifier les conversions unité PF / unité SKU avant d'utiliser un conditionnement différent du vrac.")
        if st.form_submit_button("Créer l'OF"):
            payload = {"pf_id": pf_id, "recette_id": recipe, "sku_id": sku,
                       "quantite_prevue": float(_decimal(quantity, "Quantité OF")),
                       "date_planification": str(date_planif), "notes": notes}
            _create_document("of", user_id, payload)


def _sku_unit_safe(sku_row: pd.Series, products: pd.DataFrame) -> bool:
    """Ne pas lancer la consommation PF quand une conversion SKU est nécessaire."""
    if products.empty or "pf_id" not in products.columns or "unite_production" not in products.columns:
        return False
    found = products[products["pf_id"] == sku_row.get("pf_id")]
    if found.empty:
        return False
    try:
        factor = _decimal(sku_row.get("facteur_conversion"), "Facteur SKU")
    except ValueError:
        return False
    pf_unit = str(found.iloc[0].get("unite_production") or "").strip().casefold()
    sale_unit = str(sku_row.get("unite_vente") or "").strip().casefold()
    return factor == 1 and bool(pf_unit) and pf_unit == sale_unit


def _theoretical_consumptions(of: pd.Series, produced: object,
                              materials: pd.DataFrame) -> pd.DataFrame:
    """Aperçu lisible avant toute mutation : besoin = quantite_par_unite × production."""
    recipe_id = of.get("recette_id")
    if not isinstance(recipe_id, str) or not recipe_id.strip():
        raise ValueError("OF sans recette valide")
    lines = get_lignes_recette(recipe_id)
    if not isinstance(lines, pd.DataFrame) or lines.empty or not {"mp_id", "quantite_par_unite"}.issubset(lines.columns):
        raise ValueError("Impossible de vérifier les matières de la recette")
    quantity = _decimal(produced, "Production prévue")
    rows = []
    for _, line in lines.iterrows():
        mp_id = line["mp_id"]
        if not isinstance(mp_id, str) or not mp_id.strip():
            raise ValueError("Matière de recette invalide")
        unit = "non renseignée"
        if not materials.empty and {"mp_id", "unite_stock"}.issubset(materials.columns):
            match = materials[materials["mp_id"] == mp_id]
            if not match.empty:
                unit = str(match.iloc[0].get("unite_stock") or unit)
        rate = _decimal(line["quantite_par_unite"], "Quantité de la recette")
        required = quantity * rate
        if required >= Decimal("1e15"):
            raise ValueError("Besoin matière hors limites")
        rows.append({"mp_id": mp_id, "unite_stock": unit,
                     "par_unite_produite": float(rate), "besoin_pour_OF": float(required)})
    return pd.DataFrame(rows)


def _control_form(user_id: str, of: pd.Series, skus: pd.DataFrame, materials: pd.DataFrame,
                  products: pd.DataFrame, can_stock: bool) -> None:
    of_id = of["of_id"]
    sku_id = of["sku_id"]
    sku_row = skus[skus["sku_id"] == sku_id] if "sku_id" in skus.columns else pd.DataFrame()
    packaging_id = ""
    if not sku_row.empty:
        value = sku_row.iloc[0].get("emballage_mp_id")
        if isinstance(value, str) and value.strip() and value.lower() not in ("nan", "none"):
            packaging_id = value.strip()
    if sku_row.empty or not _sku_unit_safe(sku_row.iloc[0], products):
        st.error("Conversion SKU ↔ unité de production incompatible : clôture bloquée pour éviter une consommation MP incorrecte.")
        return
    if packaging_id and not materials.empty and "mp_id" in materials.columns:
        matched = materials[materials["mp_id"] == packaging_id]
        if matched.empty:
            st.warning("Emballage du SKU introuvable/inactif : vérifier le référentiel.")
    with st.form(f"quality_{user_id}_{of_id}"):
        st.subheader(f"Contrôle qualité / clôture de l'OF {of_id}")
        conforme = st.radio("Produit conforme ?", ["OUI", "NON"], key=f"qc_{of_id}")
        remarks = st.text_area("Remarques / motif de rejet")
        controller = st.text_input("Contrôleur")
        if conforme == "OUI":
            qty = st.number_input("Quantité réellement produite (unités SKU)", min_value=0.001,
                                  value=float(of["quantite_prevue"]))
            pack_qty = st.number_input("Emballages réellement consommés", min_value=0.0,
                                       value=0.0, disabled=not packaging_id)
            if packaging_id:
                st.caption(f"Emballage configuré : {packaging_id}. Indiquer la consommation réelle.")
            else:
                st.caption("Aucun emballage configuré pour ce SKU.")
            try:
                forecast = _theoretical_consumptions(of, qty, materials)
                st.caption("Prévision des consommations MP : quantité par unité × quantité produite")
                st.dataframe(forecast, use_container_width=True, hide_index=True)
                needs_valid = True
            except ValueError as exc:
                st.error(str(exc))
                needs_valid = False
            if not can_stock:
                st.warning("Droits Stocks nécessaires pour valider une clôture conforme.")
        else:
            needs_valid = True
            qty = 0.0
            pack_qty = 0.0
            st.info("OF rejeté : aucune matière consommée et aucune entrée de produit fini.")
        recipe_ack = st.checkbox("Je confirme que la recette indique les consommations de MP PAR unité produite et que les unités sont cohérentes",
                                 key=f"qc_recipe_ack_{user_id}_{of_id}") if conforme == "OUI" else True
        if st.form_submit_button("Valider et clôturer cet OF", disabled=(not recipe_ack or not needs_valid or (conforme == "OUI" and not can_stock))):
            if not isinstance(controller, str) or not controller.strip():
                st.error("Le contrôleur est obligatoire.")
                return
            if conforme == "OUI" and packaging_id and pack_qty <= 0:
                st.error("SKU avec emballage : indiquer une quantité d’emballage strictement positive.")
                return
            try:
                payload = {"of_id": of_id, "conforme": conforme,
                           "remarques": remarks, "controleur": controller.strip(),
                           "quantite_produite": float(_decimal(qty, "Quantité produite", allow_zero=conforme == "NON")),
                           "emballage_mp_id": packaging_id or None if conforme == "OUI" and pack_qty > 0 else None,
                           "emballage_consomme": float(_decimal(pack_qty, "Quantité emballage", allow_zero=True))}
                _start_closure(user_id, payload, can_stock)
            except ValueError as exc:
                st.error(str(exc))


def _followup_tab(user_id: str, can_write: bool, can_stock: bool,
                  skus: pd.DataFrame, materials: pd.DataFrame, products: pd.DataFrame) -> None:
    st.subheader("Suivi et contrôle qualité des OF")
    orders = get_ordres_fabrication()
    if orders.empty:
        st.info("Aucun OF enregistré.")
        return
    st.dataframe(orders.sort_values(by="date_planification", ascending=False),
                 use_container_width=True, hide_index=True)
    if not can_write:
        st.info("Mode lecture seule")
        return
    if _closure_panel(user_id, can_stock):
        return
    active = orders[orders["statut"].isin(["PLANIFIE", "EN_COURS", "CONTROLE_QUALITE"])]
    if active.empty:
        st.info("Aucun OF actif.")
        return
    labels = {r["of_id"]: f"{r['of_id']} — {r['statut']}" for _, r in active.iterrows()}
    of_id = st.selectbox("OF à traiter", list(labels), format_func=lambda x: labels[x])
    of = active[active["of_id"] == of_id].iloc[0]
    state = of["statut"]
    if state == "PLANIFIE":
        if st.button("Démarrer la production", key=f"start_{user_id}_{of_id}"):
            try:
                result = changer_statut_of(of_id, "EN_COURS")
                if not isinstance(result, dict) or result.get("statut") != "EN_COURS":
                    raise RuntimeError("Démarrage non confirmé")
                st.cache_data.clear()
                st.rerun()
            except Exception as exc:
                _LOG.warning("Démarrage OF non confirmé (%s)", type(exc).__name__)
                st.error("Démarrage non confirmé. Vérifiez l'état de l'OF avant de réessayer (transition idempotente).")
    elif state == "EN_COURS":
        _control_form(user_id, of, skus, materials, products, can_stock)
    elif state == "CONTROLE_QUALITE":
        st.error("Ancien statut CONTROLE_QUALITE non pris en charge par la RPC : intervention administrateur requise. Ne pas forcer la clôture.")


def show_production_page() -> None:
    st.title("🏭 Production & Nomenclatures")
    access = _production_access()
    if access is None:
        st.error("Accès au module Production refusé ou compte inactif.")
        return
    user_id, can_write, can_stock = access
    products = get_produits_actifs()
    materials = get_mp_actives()
    skus = get_skus_actifs()
    tab_recipe, tab_of, tab_follow, tab_history = st.tabs([
        "📝 Recettes", "⚙️ OF", "📊 Production et CQ", "🔍 Consommations et contrôles",
    ])
    with tab_recipe:
        _recipe_tab(user_id, can_write, products, materials)
    with tab_of:
        _of_tab(user_id, can_write, products, skus)
    with tab_follow:
        _followup_tab(user_id, can_write, can_stock, skus, materials, products)
    with tab_history:
        st.subheader("Historique des consommations et contrôles qualité")
        consumed = get_consommations_of()
        controls = get_controles_qualite()
        if not consumed.empty:
            st.dataframe(consumed.sort_values(by="consommation_id", ascending=False),
                         use_container_width=True, hide_index=True)
        else:
            st.info("Aucune consommation")
        if not controls.empty:
            st.dataframe(controls.sort_values(by="date", ascending=False),
                         use_container_width=True, hide_index=True)
        else:
            st.info("Aucun contrôle qualité")
