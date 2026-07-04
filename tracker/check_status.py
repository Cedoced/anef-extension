#!/usr/bin/env python3
"""
ANEF Status Tracker — GitHub Actions Edition
=============================================

Vérifie le statut de naturalisation ANEF, le déchiffre,
et notifie via Telegram + Brevo si changement détecté.

Conçu pour tourner dans GitHub Actions (cron 2x/jour).
L'état est persisté dans data/status.json (commité dans le repo).

Variables d'environnement requises :
    ANEF_USERNAME          Identifiant ANEF
    ANEF_PASSWORD          Mot de passe ANEF
    TELEGRAM_BOT_TOKEN     Token du bot Telegram
    TELEGRAM_CHAT_ID       Chat ID Telegram
    BREVO_API_KEY          Clé API Brevo (optionnel)
    BREVO_SENDER_EMAIL     Email expéditeur (optionnel)
    BREVO_RECIPIENT_EMAIL  Email destinataire (optionnel)
"""

import os
import sys
import json
import base64
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes, serialization

# ─────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).parent
REPO_DIR = SCRIPT_DIR.parent
STATUS_FILE = REPO_DIR / "data" / "status.json"

TZ_PARIS = timezone(timedelta(hours=2))  # CEST

ANEF_BASE = "https://administration-etrangers-en-france.interieur.gouv.fr"
ANEF_API_STEPPER = f"{ANEF_BASE}/api/anf/dossier-stepper"
ANEF_API_DOSSIER = f"{ANEF_BASE}/api/anf/usager/dossiers/"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
log = logging.getLogger('anef')

# ─────────────────────────────────────────────────────────────
# Clé RSA (depuis l'extension ANEF)
# ─────────────────────────────────────────────────────────────

PRIVATE_KEY_PEM = b"""-----BEGIN PRIVATE KEY-----
MIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQC/WvhR9YrO6DHY
0UpAoIlIuDoF3PtLEJ3J0T5FOLAPSY2sa33AnECl6jWfM7uLuojuTDbfIz6J3vAo
sNUzwYFNHKx3EG1o6cYzjWm2LzZDa4e25wYlXcL2r3T0mFGS9DT7adKlomNURj4L
f2WUt11oNH8RYyH/uNk+kIL0HRJLtfTjyyjlWSyjUUDD1ATYZwjnQS2HvdcqJ+Go
3TTvqTG7yOPzC/lwSKG3zE3eL+pi9E9Lgw9NlSanewOu7toB9NiKwzP3kfSBNpkz
Sv4UBNClfp1UG+psSPnTx3Csil9TbPjSe99ZZ0/ffPf0h2xoga/7rWgScQwHzN9E
crvEfDgxAgMBAAECggEAa08Ikm2wOffcfEph6XwdgLpPT5ptEdtvoQ3GbessUGZf
HKHrE2iMmH6PM4g/VEx3Hat/2gJZv9dVtnv0E+IgMK4zyVFdCciPbbmP3qr7MzPK
F7fWqn26J7ydSc1hcZehXpwplNlL+qaphKkcvhlWOGm4GHgPSOjQa1V/GoZzDCE1
e1z9KpVuMMiV4d89FFiE3MHtnrmMnmUdbnesffVftnPmzkkGKKWTCL1BLrdEXgCz
GSFdqCo+PjcJjEojjmqHhgzTyjPOR6JGh0FqG9ht3aduIQMZfKR1p2+Ds18NlOZu
T60Lyc7Ud/d0H0f2h9GfftHYCSLkIxfTaAmoYXzXAQKBgQDoWc91xlh8Kb3vmIN1
IoVY2yhviDTpUqkGxvjt6WYmu38CFpEwSO0cpTVCAkWRKvjKLUOoCAaqfaTrN04t
LG85Z18gvSQKmncfv0zrKaTN/FrnKOA//hPCAcveDT6Ir9SCxgVmNBox70k89eQ+
5cDOZACqFhKcoAQa/LjF621HBQKBgQDS1Pi+GhSwbn6nBiqQdzU1+RpXdburzubd
3dgNlrAOmLoFEGqYNzaMcKbNljNTnAdv/FX6/NYaQGx/pYTs26o/SZZ+SE7Cl2RS
RJIuWeskuNEoH4W06JgO1djyHVOiHmKbyaATWCjoZSQnnHo8OUBUKOJpw8mrNlQl
IYUE0OLcPQKBgQDD3LlKUZnTiKhoqYrfGeuIfK34Xrwjlx+O6/l5LA+FRPaKfxWC
u2bNh+J+M0YLWksAuulWYvWjkGiOMz++Sr+zhxUkluwj2BPk+jDP53nafgju5YEr
0HU9TKBbHZUCSh384wo4HmGaiFiXf7wY3ToLgTciKZsk1qq/SRxFEvE6NQKBgHcS
Cs2qgybFsMf55o4ilS2/Ww4sEurMdny1bvD1usbzoJN9mwYOoMMeWEZh3ukIhPbN
J24R34WB/wT0YSc4RGVr1Q/LHJgv0lvYGEsPQ4tAyfeEHgp3FnHCerz6rSIxUPW1
IK/sKWZewNWSPULH/rnJQV4EUmBc1ZcG4E5A/u7tAoGBAMneO96PMhJFQDhsakTL
vGTbhuwBnFjbSuxmyebhszASOuKm8XTVDe004AZTSy7lAm+iYTkfeRbfVrIGWElT
5DWhmlN/zNTdX56dQWG3P5M48+bxZFXz0YCBAZJw8jZ5LcFuKrr5tQbcNZN9Pqgk
QJNdXtE3G7SjkDOn36yZSaXp
-----END PRIVATE KEY-----"""

# ─────────────────────────────────────────────────────────────
# Dictionnaire complet des statuts
# ─────────────────────────────────────────────────────────────

STATUTS = {
    "draft": {"phase": "Brouillon", "explication": "Dossier en brouillon", "etape": 1, "rang": 100, "icon": "📝", "desc": "Votre dossier est en cours de préparation."},
    "dossier_depose": {"phase": "Dépôt", "explication": "Dossier déposé", "etape": 2, "rang": 200, "icon": "📨", "desc": "Dossier soumis avec succès."},
    "verification_formelle_a_traiter": {"phase": "Vérification formelle", "explication": "Dossier reçu, en tri", "etape": 3, "rang": 301, "icon": "🔍", "desc": "En file d'attente pour le premier tri."},
    "verification_formelle_en_cours": {"phase": "Vérification formelle", "explication": "Tri en cours", "etape": 3, "rang": 302, "icon": "🔍", "desc": "Un agent vérifie l'admissibilité."},
    "verification_formelle_mise_en_demeure": {"phase": "Vérification formelle", "explication": "Mise en demeure", "etape": 3, "rang": 303, "icon": "⚠️", "desc": "Documents manquants à fournir."},
    "instruction_a_affecter": {"phase": "Affectation", "explication": "Attente d'affectation", "etape": 4, "rang": 400, "icon": "👤", "desc": "Dossier recevable, en attente d'un instructeur."},
    "instruction_recepisse_completude_a_envoyer": {"phase": "Instruction", "explication": "Examen approfondi", "etape": 5, "rang": 501, "icon": "📖", "desc": "Un agent examine en détail votre dossier."},
    "instruction_recepisse_completude_a_envoyer_retour_complement_a_traiter": {"phase": "Instruction", "explication": "Compléments à vérifier", "etape": 5, "rang": 502, "icon": "📋", "desc": "Compléments reçus, en cours de vérification."},
    "instruction_date_ea_a_fixer": {"phase": "Complétude & enquêtes", "explication": "Enquêtes lancées", "etape": 6, "rang": 601, "icon": "🔎", "desc": "Dossier complet, enquêtes lancées."},
    "ea_demande_report_ea": {"phase": "Complétude & enquêtes", "explication": "Report d'entretien", "etape": 6, "rang": 602, "icon": "🔄", "desc": "Demande de report d'entretien."},
    "ea_en_attente_ea": {"phase": "Entretien", "explication": "Convocation envoyée", "etape": 7, "rang": 701, "icon": "📬", "desc": "Convocation à l'entretien envoyée."},
    "ea_crea_a_valider": {"phase": "Entretien", "explication": "CR en rédaction", "etape": 7, "rang": 702, "icon": "✅", "desc": "Entretien passé, compte-rendu en rédaction."},
    "prop_decision_pref_a_effectuer": {"phase": "Décision préfecture", "explication": "Avis en cours", "etape": 8, "rang": 801, "icon": "⚖️", "desc": "L'instructeur analyse votre dossier."},
    "prop_decision_pref_en_attente_retour_hierarchique": {"phase": "Décision préfecture", "explication": "Validation hiérarchique", "etape": 8, "rang": 802, "icon": "👔", "desc": "Proposition soumise à la hiérarchie."},
    "prop_decision_pref_prop_a_editer": {"phase": "Décision préfecture", "explication": "Rédaction proposition", "etape": 8, "rang": 803, "icon": "📝", "desc": "Document de proposition en rédaction."},
    "prop_decision_pref_en_attente_retour_signataire": {"phase": "Décision préfecture", "explication": "Attente signature préfet", "etape": 8, "rang": 804, "icon": "✍️", "desc": "En attente de la signature du préfet."},
    "controle_a_affecter": {"phase": "Contrôle SDANF", "explication": "SDANF — attente affectation", "etape": 9, "rang": 901, "icon": "🏛️", "desc": "Dossier arrivé à la SDANF (Rezé), en attente d'un agent."},
    "controle_a_effectuer": {"phase": "Contrôle SDANF", "explication": "Contrôle en cours", "etape": 9, "rang": 902, "icon": "📑", "desc": "Un agent SDANF contrôle votre dossier."},
    "controle_en_attente_pec": {"phase": "Contrôle SCEC", "explication": "Transmis SCEC Nantes", "etape": 9, "rang": 903, "icon": "🏛️", "desc": "Le SCEC de Nantes vérifie vos actes d'état civil."},
    "controle_pec_a_faire": {"phase": "Contrôle SCEC", "explication": "Vérification état civil", "etape": 9, "rang": 904, "icon": "✔️", "desc": "Vérification des pièces d'état civil en cours."},
    "controle_transmise_pour_decret": {"phase": "Préparation décret", "explication": "🎉 FAVORABLE — transmis pour décret", "etape": 10, "rang": 1001, "icon": "🎉", "desc": "Excellente nouvelle ! Avis FAVORABLE !"},
    "controle_en_attente_retour_hierarchique": {"phase": "Préparation décret", "explication": "Validation hiérarchique ministérielle", "etape": 10, "rang": 1002, "icon": "👔", "desc": "Validation hiérarchique au ministère."},
    "controle_decision_a_editer": {"phase": "Préparation décret", "explication": "Édition décision favorable", "etape": 10, "rang": 1003, "icon": "📄", "desc": "Décision favorable en cours d'édition."},
    "controle_en_attente_signature": {"phase": "Préparation décret", "explication": "Attente signature ministérielle", "etape": 10, "rang": 1004, "icon": "✍️", "desc": "Décret en attente de signature."},
    "transmis_a_ac": {"phase": "Préparation décret", "explication": "Transmis administration centrale", "etape": 10, "rang": 1005, "icon": "📬", "desc": "Transmis à l'administration centrale."},
    "a_verifier_avant_insertion_decret": {"phase": "Préparation décret", "explication": "Vérifications finales", "etape": 10, "rang": 1006, "icon": "🔎", "desc": "Dernières vérifications avant insertion au décret."},
    "prete_pour_insertion_decret": {"phase": "Préparation décret", "explication": "Prêt pour insertion décret", "etape": 10, "rang": 1007, "icon": "✅", "desc": "Validé, prêt pour le décret !"},
    "decret_en_preparation": {"phase": "Préparation décret", "explication": "Décret en préparation", "etape": 10, "rang": 1008, "icon": "📋", "desc": "Décret en cours de préparation."},
    "decret_a_qualifier": {"phase": "Préparation décret", "explication": "Décret en qualification", "etape": 10, "rang": 1009, "icon": "📋", "desc": "Décret en phase de qualification."},
    "decret_en_validation": {"phase": "Préparation décret", "explication": "Décret en validation", "etape": 10, "rang": 1010, "icon": "📋", "desc": "Décret en validation finale."},
    "inseree_dans_decret": {"phase": "Publication JO", "explication": "Inséré dans décret signé", "etape": 11, "rang": 1101, "icon": "🎉", "desc": "Votre nom est inscrit dans un décret !"},
    "decret_envoye_prefecture": {"phase": "Publication JO", "explication": "Décret envoyé à la préfecture", "etape": 11, "rang": 1102, "icon": "📨", "desc": "Décret transmis à votre préfecture."},
    "notification_envoyee": {"phase": "Publication JO", "explication": "Notification officielle envoyée", "etape": 11, "rang": 1103, "icon": "📬", "desc": "Notification officielle envoyée."},
    "decret_naturalisation_publie": {"phase": "NATURALISÉ(E) 🇫🇷", "explication": "Décret publié au JO", "etape": 12, "rang": 1201, "icon": "🇫🇷", "desc": "FÉLICITATIONS ! Vous êtes français(e) !"},
    "decret_naturalisation_publie_jo": {"phase": "NATURALISÉ(E) 🇫🇷", "explication": "Décret publié au JO", "etape": 12, "rang": 1202, "icon": "🇫🇷", "desc": "FÉLICITATIONS !"},
    "decret_publie": {"phase": "NATURALISÉ(E) 🇫🇷", "explication": "Décret publié", "etape": 12, "rang": 1203, "icon": "🇫🇷", "desc": "FÉLICITATIONS !"},
    "demande_traitee": {"phase": "Finalisé", "explication": "Demande traitée", "etape": 12, "rang": 1204, "icon": "✅", "desc": "Demande entièrement traitée."},
    "decision_negative_en_delais_recours": {"phase": "Décision négative", "explication": "Défavorable — recours ouvert", "etape": 12, "rang": 1205, "icon": "❌", "desc": "Décision défavorable. Recours possible sous 2 mois."},
    "decision_notifiee": {"phase": "Décision négative", "explication": "Décision notifiée", "etape": 12, "rang": 1206, "icon": "❌", "desc": "Décision notifiée."},
    "demande_en_cours_rapo": {"phase": "Recours RAPO", "explication": "Recours en cours", "etape": 12, "rang": 1207, "icon": "⚖️", "desc": "Recours administratif en cours d'examen."},
    "irrecevabilite_manifeste": {"phase": "Irrecevabilité", "explication": "Conditions non remplies", "etape": 12, "rang": 1209, "icon": "❌", "desc": "Conditions légales non remplies."},
    "css_en_delais_recours": {"phase": "Classement sans suite", "explication": "Classé sans suite", "etape": 12, "rang": 1211, "icon": "⚠️", "desc": "Dossier classé sans suite."},
    "css_notifie": {"phase": "Classement sans suite", "explication": "CSS notifié", "etape": 12, "rang": 1212, "icon": "⚠️", "desc": "Classement sans suite notifié."},
}


# ─────────────────────────────────────────────────────────────
# Connexion ANEF SSO
# ─────────────────────────────────────────────────────────────

def anef_login(username: str, password: str) -> requests.Session:
    """Se connecte au portail ANEF via SSO Keycloak. Retourne la session."""
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                      'AppleWebKit/537.36 Chrome/137.0 Safari/537.36',
        'Accept-Language': 'fr-FR,fr;q=0.9',
    })

    log.info("🔐 Connexion au portail ANEF...")

    # Étape 1 — Accéder au endpoint de login → redirige vers Keycloak
    resp = session.get(f"{ANEF_BASE}/api/anf/auth/login", allow_redirects=True, timeout=30)
    if resp.status_code != 200:
        raise ConnectionError(f"Login endpoint HTTP {resp.status_code}")

    # Déjà connecté ?
    if 'mon-compte' in resp.url:
        log.info("✅ Déjà connecté")
        return session

    # Étape 2 — Extraire et soumettre le formulaire Keycloak
    soup = BeautifulSoup(resp.text, 'html.parser')
    form = soup.find('form', id='kc-form-login') or soup.find('form')
    if not form:
        raise ConnectionError("Formulaire SSO non trouvé")

    action = form.get('action', '')
    if not action.startswith('http'):
        action = urljoin(resp.url, action)

    # Champs cachés + identifiants
    data = {inp.get('name'): inp.get('value', '')
            for inp in form.find_all('input', type='hidden') if inp.get('name')}
    data['username'] = username
    data['password'] = password

    log.info("📤 Soumission des identifiants...")
    resp2 = session.post(action, data=data, allow_redirects=True, timeout=30)

    # Vérifier échec
    if 'error' in resp2.url.lower() or resp2.status_code >= 400:
        soup2 = BeautifulSoup(resp2.text, 'html.parser')
        err = soup2.find(class_='alert-error') or soup2.find(class_='kc-feedback-text')
        msg = err.get_text(strip=True) if err else "Login échoué"
        raise ConnectionError(f"❌ {msg}")

    if 'UPDATE_PASSWORD' in resp2.url:
        raise ConnectionError("⚠️ Mot de passe ANEF expiré — renouvelez-le sur le portail")

    # Étape 3 — Vérifier que l'API est accessible
    test = session.get(ANEF_API_STEPPER, timeout=15)
    if test.status_code == 200:
        try:
            if test.json().get('dossier', {}).get('statut'):
                log.info("✅ Connexion réussie !")
                return session
        except Exception:
            pass

    # Fallback: vérifier les cookies
    if any('anef' in c.domain.lower() for c in session.cookies):
        log.info("✅ Connexion réussie (cookies détectés)")
        return session

    raise ConnectionError("Session non établie après login")


# ─────────────────────────────────────────────────────────────
# Déchiffrement RSA
# ─────────────────────────────────────────────────────────────

def decrypt_status(encrypted_b64: str) -> tuple[str, str | None]:
    """Déchiffre le statut RSA-OAEP SHA-256. Retourne (code, date)."""
    key = serialization.load_pem_private_key(PRIVATE_KEY_PEM, password=None)
    raw = key.decrypt(
        base64.b64decode(encrypted_b64),
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    ).decode('utf-8')

    parts = raw.split('#K#')
    return parts[0], parts[1] if len(parts) > 1 else None


def status_info(code: str) -> dict:
    """Retourne les infos enrichies d'un code statut."""
    info = STATUTS.get(code.lower().strip(), {
        "phase": "Inconnu", "explication": code, "etape": 0, "rang": 0,
        "icon": "❓", "desc": "Statut non répertorié."
    })
    rang = info['rang']
    sub = f"{rang // 100}.{rang % 100}" if rang % 100 else str(rang // 100)
    return {**info, 'code': code.lower().strip(), 'sub': sub}


# ─────────────────────────────────────────────────────────────
# Persistance (data/status.json)
# ─────────────────────────────────────────────────────────────

def load_state() -> dict:
    if STATUS_FILE.exists():
        return json.loads(STATUS_FILE.read_text('utf-8'))
    return {"last_status": None, "last_date": None, "history": []}


def save_state(state: dict):
    STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATUS_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), 'utf-8')


# ─────────────────────────────────────────────────────────────
# Notifications
# ─────────────────────────────────────────────────────────────

def build_message(info: dict, prev_code: str | None, is_change: bool, date_statut: str) -> dict:
    """Construit les messages de notification."""
    now = datetime.now(TZ_PARIS).strftime('%d/%m/%Y %H:%M')

    bar = ""
    for i in range(1, 13):
        if i < info['etape']:
            bar += "█"
        elif i == info['etape']:
            bar += "▓"
        else:
            bar += "░"

    if is_change:
        prev = status_info(prev_code) if prev_code else None
        title = "🔔 Changement de statut ANEF !"
        if info['etape'] >= 10:
            title = "🎉 BONNE NOUVELLE ANEF !"

        telegram = (
            f"<b>{title}</b>\n\n"
            f"{info['icon']} <b>{info['phase']}</b>\n"
            f"{info['explication']}\n\n"
            f"📊 Étape <b>{info['sub']}</b> / 12\n"
            f"<code>{bar}</code>\n\n"
            f"📝 {info.get('desc', '')}\n\n"
        )
        if prev:
            telegram += f"🔄 Avant : {prev['sub']} — {prev['explication']}\n\n"
        telegram += f"🕐 {now}"
    else:
        title = "ℹ️ Statut ANEF inchangé"
        telegram = (
            f"<b>{title}</b>\n\n"
            f"{info['icon']} <b>{info['phase']}</b>\n"
            f"{info['explication']}\n"
            f"📊 Étape <b>{info['sub']}</b> / 12\n"
            f"<code>{bar}</code>\n\n"
            f"🕐 Vérifié le {now}"
        )

    email_subject = f"{info['icon']} ANEF — {info['phase']} ({info['sub']}/12)"
    email_body = (
        f"<h2>{title}</h2>"
        f"<p><b>{info['icon']} {info['phase']}</b> — {info['explication']}</p>"
        f"<p>📊 Étape <b>{info['sub']}</b> / 12</p>"
        f"<p>{info.get('desc', '')}</p>"
    )
    if is_change and prev_code:
        prev = status_info(prev_code)
        email_body += f"<p>🔄 <em>Avant : {prev['sub']} — {prev['explication']}</em></p>"
    email_body += f"<hr><p style='color:#888'>Vérifié le {now} — ANEF Status Tracker</p>"

    return {
        "title": title,
        "telegram": telegram,
        "email_subject": email_subject,
        "email_html": email_body,
    }


def send_telegram(msg: str):
    """Envoie un message via Telegram Bot API."""
    token = os.environ.get('TELEGRAM_BOT_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')
    if not token or not chat_id:
        log.warning("⚠️ Telegram non configuré (TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID manquants)")
        return False
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": msg, "parse_mode": "HTML"},
            timeout=10
        )
        resp.raise_for_status()
        log.info("📱 Telegram envoyé !")
        return True
    except Exception as e:
        log.error(f"❌ Telegram échoué : {e}")
        return False


def send_brevo(subject: str, html: str):
    """Envoie un email via l'API Brevo (ex-Sendinblue)."""
    api_key = os.environ.get('BREVO_API_KEY')
    sender = os.environ.get('BREVO_SENDER_EMAIL')
    recipient = os.environ.get('BREVO_RECIPIENT_EMAIL')
    if not api_key or not sender or not recipient:
        log.warning("⚠️ Brevo non configuré")
        return False
    try:
        resp = requests.post(
            "https://api.brevo.com/v3/smtp/email",
            headers={"api-key": api_key, "Content-Type": "application/json"},
            json={
                "sender": {"email": sender, "name": "ANEF Tracker"},
                "to": [{"email": recipient}],
                "subject": subject,
                "htmlContent": f"""
                <html><body style="font-family:-apple-system,sans-serif;padding:20px;background:#f5f5f5">
                <div style="max-width:600px;margin:0 auto;background:#fff;border-radius:12px;
                            padding:30px;box-shadow:0 2px 10px rgba(0,0,0,.1)">
                {html}
                </div></body></html>"""
            },
            timeout=10
        )
        resp.raise_for_status()
        log.info("📧 Email Brevo envoyé !")
        return True
    except Exception as e:
        log.error(f"❌ Brevo échoué : {e}")
        return False


# ─────────────────────────────────────────────────────────────
# Point d'entrée
# ─────────────────────────────────────────────────────────────

def main():
    force = '--force-notify' in sys.argv or '-f' in sys.argv

    username = os.environ.get('ANEF_USERNAME')
    password = os.environ.get('ANEF_PASSWORD')
    if not username or not password:
        log.error("❌ ANEF_USERNAME / ANEF_PASSWORD non définis")
        sys.exit(1)

    state = load_state()

    try:
        # 1. Login
        session = anef_login(username, password)

        # 2. Fetch status
        log.info("📡 Appel API dossier-stepper...")
        resp = session.get(ANEF_API_STEPPER, timeout=15)
        if resp.status_code in (502, 503):
            raise ConnectionError("Site ANEF en maintenance")
        resp.raise_for_status()
        data = resp.json()

        encrypted = data.get('dossier', {}).get('statut')
        dossier_id = data.get('dossier', {}).get('id')
        if not encrypted:
            raise ValueError("Pas de statut dans la réponse API")

        # 3. Decrypt
        code, date_statut = decrypt_status(encrypted)
        log.info(f"🔓 Statut déchiffré : {code} (date: {date_statut})")

        info = status_info(code)
        prev = state.get('last_status')
        is_change = prev != code.lower()

        # 4. Update state
        now = datetime.now(TZ_PARIS).isoformat()
        state['last_status'] = code.lower()
        state['last_date'] = date_statut
        state['last_check'] = now
        state['dossier_id'] = dossier_id
        state['history'].append({
            "ts": now, "status": code.lower(), "date": date_statut,
            "sub": info['sub'], "phase": info['phase'], "changed": is_change
        })
        state['history'] = state['history'][-200:]
        save_state(state)

        # 5. Log
        log.info(f"{'='*50}")
        log.info(f"{info['icon']} {info['phase']} — {info['explication']}")
        log.info(f"📊 Étape {info['sub']}/12")
        if is_change:
            log.info(f"🔔 CHANGEMENT ! (avant: {prev})")
        else:
            log.info(f"ℹ️ Inchangé")
        log.info(f"{'='*50}")

        # 6. Notify
        if is_change or force:
            msgs = build_message(info, prev, is_change, date_statut)
            send_telegram(msgs['telegram'])
            send_brevo(msgs['email_subject'], msgs['email_html'])

        # GitHub Actions output
        if os.environ.get('GITHUB_OUTPUT'):
            with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
                f.write(f"status={code.lower()}\n")
                f.write(f"step={info['sub']}\n")
                f.write(f"changed={'true' if is_change else 'false'}\n")
                f.write(f"phase={info['phase']}\n")

    except Exception as e:
        log.error(f"❌ Erreur : {e}")
        # Notifier l'erreur aussi
        send_telegram(f"⚠️ <b>ANEF Tracker — Erreur</b>\n\n{e}\n\n🕐 {datetime.now(TZ_PARIS).strftime('%d/%m %H:%M')}")
        sys.exit(1)


if __name__ == '__main__':
    main()
