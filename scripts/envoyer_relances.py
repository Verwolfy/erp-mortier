"""
Script d'automatisation : Envoi de relances par email pour les factures échues.
À exécuter quotidiennement via un Cron job ou GitHub Actions.
"""
import os
import smtplib
from email.message import EmailMessage
import pandas as pd
from datetime import datetime
from supabase import create_client

# Configuration Supabase (via variables d'environnement injectées par GitHub Actions)
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Configuration Email (via variables d'environnement)
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USER = os.getenv("SMTP_USER")  # Votre adresse email
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")  # Mot de passe d'application


def get_factures_echues(supabase):
    """
    Récupère les factures en retard non soldées.
    Optimisation OOM : Le filtrage de la date se fait directement côté SQL (Supabase).
    """
    aujourdhui_str = datetime.now().strftime("%Y-%m-%d")

    response = supabase.table("factures") \
        .select("*") \
        .in_("statut", ["EN_ATTENTE", "PARTIELLE", "BROUILLON", "VALIDE"]) \
        .lt("date_echeance", aujourdhui_str) \
        .execute()

    return pd.DataFrame(response.data)


def get_clients(supabase):
    """Récupère le dictionnaire des clients pour avoir leurs emails."""
    response = supabase.table("clients").select("client_id, nom, email_contact, nom_contact").execute()
    return pd.DataFrame(response.data)


def envoyer_email_relance(client_nom, client_email, facture_id, montant_restant, date_echeance):
    """Envoie un email via SMTP."""
    if not client_email or "@" not in str(client_email):
        print(f"⚠️ Email invalide pour {client_nom} (Facture {facture_id})")
        return False

    msg = EmailMessage()
    msg['Subject'] = f"Relance : Facture impayée n° {facture_id}"
    msg['From'] = SMTP_USER
    msg['To'] = client_email

    contenu = f"""Bonjour {client_nom},

Sauf erreur ou omission de notre part, le paiement de la facture {facture_id} arrivée à échéance le {date_echeance} ne nous est pas parvenu.
Le montant restant à régler s'élève à {montant_restant:,.2f} DZD.

Nous vous prions de bien vouloir procéder au règlement dans les meilleurs délais. 
Si votre paiement a déjà été effectué entre-temps, veuillez ignorer ce message.

Cordialement,
Le Service Comptabilité
    """
    msg.set_content(contenu)

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
        print(f"✅ Relance envoyée avec succès à {client_email} pour la facture {facture_id}.")
        return True
    except Exception as e:
        print(f"❌ Erreur lors de l'envoi de l'email à {client_email} : {e}")
        return False


def main():
    print("--- DÉMARRAGE DU SCRIPT DE RELANCE ---")
    if not all([SUPABASE_URL, SUPABASE_KEY, SMTP_USER, SMTP_PASSWORD]):
        print("❌ Erreur : Variables d'environnement manquantes.")
        return

    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

    df_echues = get_factures_echues(supabase)
    if df_echues.empty:
        print("✅ Aucune facture en retard à relancer aujourd'hui.")
        return

    df_clients = get_clients(supabase)

    for _, facture in df_echues.iterrows():
        client_info = df_clients[df_clients["client_id"] == facture["client_id"]]
        if client_info.empty:
            continue

        client = client_info.iloc[0]
        montant_restant = float(facture.get("montant_ttc", 0)) - float(facture.get("montant_paye", 0))

        # Règle métier : On ne relance que s'il reste au moins 10 DZD à payer
        if montant_restant > 10.0:
            envoyer_email_relance(
                client_nom=client["nom"],
                client_email=client["email_contact"],
                facture_id=facture["facture_id"],
                montant_restant=montant_restant,
                date_echeance=facture["date_echeance"]
            )

    print("--- FIN DU SCRIPT ---")


if __name__ == "__main__":
    main()