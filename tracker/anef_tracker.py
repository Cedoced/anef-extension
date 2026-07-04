#!/usr/bin/env python3
"""
ANEF Status Tracker — Suivi automatique du statut de naturalisation
===================================================================

Script autonome qui :
1. Se connecte au portail ANEF via le SSO Keycloak
2. Récupère le statut chiffré via l'API interne
3. Le déchiffre avec la clé RSA
4. Compare avec le dernier statut connu
5. Envoie des notifications si changement détecté

Usage:
    python3 anef_tracker.py                 # Vérification unique
    python3 anef_tracker.py --verbose       # Mode verbeux
    python3 anef_tracker.py --force-notify  # Forcer la notification (test)
    python3 anef_tracker.py --history       # Afficher l'historique
"""

import os
import sys
import json
import time
import base64
import hashlib
import logging
import argparse
import smtplib
import subprocess
from datetime import datetime, timezone, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from urllib.parse import urlparse, parse_qs, urljoin

import yaml
import requests
from bs4 import BeautifulSoup
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes, serialization

# ─────────────────────────────────────────────────────────────
# Configuration par défaut
# ─────────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).parent
CONFIG_FILE = SCRIPT_DIR / "config.yaml"
DEFAULT_HISTORY_FILE = SCRIPT_DIR / "status_history.json"
DEFAULT_LOG_FILE = SCRIPT_DIR / "anef_tracker.log"

# Fuseau horaire Paris
TZ_PARIS = timezone(timedelta(hours=2))  # CEST (été)

# ─────────────────────────────────────────────────────────────
# URLs ANEF
# ─────────────────────────────────────────────────────────────

ANEF_BASE = "https://administration-etrangers-en-france.interieur.gouv.fr"
ANEF_LOGIN_PAGE = f"{ANEF_BASE}/usagers/#/espace-personnel/connexion-inscription"
ANEF_API_STEPPER = f"{ANEF_BASE}/api/anf/dossier-stepper"
ANEF_API_DOSSIER = f"{ANEF_BASE}/api/anf/usager/dossiers/"
SSO_BASE = "https://sso.anef.dgef.interieur.gouv.fr"

# ─────────────────────────────────────────────────────────────
# Clé RSA pour déchiffrement (depuis l'extension)
# ─────────────────────────────────────────────────────────────

PRIVATE_KEY_PEM = """-----BEGIN PRIVATE KEY-----
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
# Dictionnaire des statuts (complet, depuis status-parser.js)
# ─────────────────────────────────────────────────────────────

STATUTS = {
    "draft": {"phase": "Brouillon", "explication": "Dossier en brouillon", "etape": 1, "rang": 100, "icon": "📝",
              "description": "Votre dossier est en cours de préparation sur la plateforme ANEF."},
    "dossier_depose": {"phase": "Dépôt", "explication": "Dossier déposé", "etape": 2, "rang": 200, "icon": "📨",
                       "description": "Votre dossier a été soumis avec succès."},
    "verification_formelle_a_traiter": {"phase": "Vérification formelle", "explication": "Dossier reçu, en tri", "etape": 3, "rang": 301, "icon": "🔍",
                                       "description": "La préfecture a bien reçu votre demande. Elle est en file d'attente pour le premier tri."},
    "verification_formelle_en_cours": {"phase": "Vérification formelle", "explication": "Tri en cours", "etape": 3, "rang": 302, "icon": "🔍",
                                      "description": "Un agent vérifie l'admissibilité formelle de votre dossier."},
    "verification_formelle_mise_en_demeure": {"phase": "Vérification formelle", "explication": "Mise en demeure, pièces à fournir", "etape": 3, "rang": 303, "icon": "⚠️",
                                             "description": "Documents manquants. Répondez dans le délai imparti."},
    "css_mise_en_demeure_a_affecter": {"phase": "Vérification formelle", "explication": "Classement sans suite en cours", "etape": 3, "rang": 304, "icon": "⚠️"},
    "css_mise_en_demeure_a_rediger": {"phase": "Vérification formelle", "explication": "Classement sans suite en rédaction", "etape": 3, "rang": 305, "icon": "⚠️"},
    "instruction_a_affecter": {"phase": "Affectation", "explication": "Dossier recevable, attente d'affectation", "etape": 4, "rang": 400, "icon": "👤",
                               "description": "Votre dossier a passé la vérification ! Il attend d'être attribué à un instructeur."},
    "instruction_recepisse_completude_a_envoyer": {"phase": "Instruction", "explication": "Dossier complet, examen approfondi", "etape": 5, "rang": 501, "icon": "📖",
                                                  "description": "Un agent examine en détail votre dossier."},
    "instruction_recepisse_completude_a_envoyer_retour_complement_a_traiter": {"phase": "Instruction", "explication": "Compléments reçus, à vérifier", "etape": 5, "rang": 502, "icon": "📋"},
    "css_manuels_a_affecter": {"phase": "Classement sans suite", "explication": "Proposition de CSS manuel", "etape": 5, "rang": 503, "icon": "⚠️"},
    "css_manuels_a_rediger": {"phase": "Classement sans suite", "explication": "CSS manuel en rédaction", "etape": 5, "rang": 504, "icon": "⚠️"},
    "css_automatiques_a_affecter": {"phase": "Classement sans suite", "explication": "CSS automatique à affecter", "etape": 5, "rang": 505, "icon": "⚠️"},
    "css_automatiques_a_rediger": {"phase": "Classement sans suite", "explication": "CSS automatique en rédaction", "etape": 5, "rang": 506, "icon": "⚠️"},
    "instruction_date_ea_a_fixer": {"phase": "Complétude & enquêtes", "explication": "Enquêtes administratives lancées", "etape": 6, "rang": 601, "icon": "🔎",
                                   "description": "Dossier complet ! Enquêtes lancées, entretien à fixer."},
    "ea_demande_report_ea": {"phase": "Complétude & enquêtes", "explication": "Demande de report d'entretien", "etape": 6, "rang": 602, "icon": "🔄"},
    "ea_en_attente_ea": {"phase": "Entretien d'assimilation", "explication": "Convocation envoyée, en attente", "etape": 7, "rang": 701, "icon": "📬",
                         "description": "Convocation à l'entretien envoyée. Préparez-vous !"},
    "ea_crea_a_valider": {"phase": "Entretien d'assimilation", "explication": "Entretien passé, CR en rédaction", "etape": 7, "rang": 702, "icon": "✅",
                          "description": "Entretien passé ! Le compte-rendu est en cours de rédaction."},
    "prop_decision_pref_a_effectuer": {"phase": "Décision préfecture", "explication": "Avis préfectoral en cours", "etape": 8, "rang": 801, "icon": "⚖️",
                                      "description": "L'instructeur analyse l'ensemble de votre dossier pour formuler son avis."},
    "prop_decision_pref_en_attente_retour_hierarchique": {"phase": "Décision préfecture", "explication": "Validation hiérarchique en cours", "etape": 8, "rang": 802, "icon": "👔"},
    "prop_decision_pref_prop_a_editer": {"phase": "Décision préfecture", "explication": "Rédaction de la proposition", "etape": 8, "rang": 803, "icon": "📝"},
    "prop_decision_pref_en_attente_retour_signataire": {"phase": "Décision préfecture", "explication": "Attente signature du préfet", "etape": 8, "rang": 804, "icon": "✍️"},
    "controle_a_affecter": {"phase": "Contrôle SDANF", "explication": "Arrivé à la SDANF, attente affectation", "etape": 9, "rang": 901, "icon": "🏛️",
                            "description": "Dossier arrivé à la SDANF (Rezé). En attente d'attribution à un agent."},
    "controle_a_effectuer": {"phase": "Contrôle SDANF", "explication": "Contrôle ministériel en cours", "etape": 9, "rang": 902, "icon": "📑",
                             "description": "Un agent de la SDANF contrôle votre dossier."},
    "controle_en_attente_pec": {"phase": "Contrôle SCEC", "explication": "Transmis au SCEC de Nantes", "etape": 9, "rang": 903, "icon": "🏛️",
                                "description": "Le SCEC de Nantes vérifie l'authenticité de vos actes d'état civil."},
    "controle_pec_a_faire": {"phase": "Contrôle SCEC", "explication": "Vérification d'état civil en cours", "etape": 9, "rang": 904, "icon": "✔️"},
    "controle_transmise_pour_decret": {"phase": "Préparation décret", "explication": "Avis FAVORABLE, transmis pour décret", "etape": 10, "rang": 1001, "icon": "🎉",
                                      "description": "Excellente nouvelle ! Avis FAVORABLE. Transmis pour décret !"},
    "controle_en_attente_retour_hierarchique": {"phase": "Préparation décret", "explication": "Validation hiérarchique ministérielle", "etape": 10, "rang": 1002, "icon": "👔"},
    "controle_decision_a_editer": {"phase": "Préparation décret", "explication": "Décision favorable, édition en cours", "etape": 10, "rang": 1003, "icon": "📄"},
    "controle_en_attente_signature": {"phase": "Préparation décret", "explication": "Attente signature ministérielle", "etape": 10, "rang": 1004, "icon": "✍️"},
    "transmis_a_ac": {"phase": "Préparation décret", "explication": "Transmis à l'administration centrale", "etape": 10, "rang": 1005, "icon": "📬"},
    "a_verifier_avant_insertion_decret": {"phase": "Préparation décret", "explication": "Vérifications finales avant insertion", "etape": 10, "rang": 1006, "icon": "🔎"},
    "prete_pour_insertion_decret": {"phase": "Préparation décret", "explication": "Validé, prêt pour insertion décret", "etape": 10, "rang": 1007, "icon": "✅"},
    "decret_en_preparation": {"phase": "Préparation décret", "explication": "Décret en cours de préparation", "etape": 10, "rang": 1008, "icon": "📋"},
    "decret_a_qualifier": {"phase": "Préparation décret", "explication": "Décret en cours de qualification", "etape": 10, "rang": 1009, "icon": "📋"},
    "decret_en_validation": {"phase": "Préparation décret", "explication": "Décret en validation finale", "etape": 10, "rang": 1010, "icon": "📋"},
    "inseree_dans_decret": {"phase": "Publication JO", "explication": "Inséré dans un décret signé", "etape": 11, "rang": 1101, "icon": "🎉",
                            "description": "Votre nom est inscrit dans un décret de naturalisation !"},
    "decret_envoye_prefecture": {"phase": "Publication JO", "explication": "Décret envoyé à votre préfecture", "etape": 11, "rang": 1102, "icon": "📨"},
    "notification_envoyee": {"phase": "Publication JO", "explication": "Notification officielle envoyée", "etape": 11, "rang": 1103, "icon": "📬"},
    "decret_naturalisation_publie": {"phase": "NATURALISÉ(E)", "explication": "Décret publié au Journal Officiel", "etape": 12, "rang": 1201, "icon": "🇫🇷",
                                    "description": "FÉLICITATIONS ! Vous êtes officiellement citoyen(ne) français(e) !"},
    "decret_naturalisation_publie_jo": {"phase": "NATURALISÉ(E)", "explication": "Décret publié au JO", "etape": 12, "rang": 1202, "icon": "🇫🇷"},
    "decret_publie": {"phase": "NATURALISÉ(E)", "explication": "Décret publié", "etape": 12, "rang": 1203, "icon": "🇫🇷"},
    "demande_traitee": {"phase": "Finalisé", "explication": "Demande entièrement traitée", "etape": 12, "rang": 1204, "icon": "✅"},
    "decision_negative_en_delais_recours": {"phase": "Décision négative", "explication": "Défavorable, délai de recours ouvert", "etape": 12, "rang": 1205, "icon": "❌"},
    "decision_notifiee": {"phase": "Décision négative", "explication": "Décision notifiée au demandeur", "etape": 12, "rang": 1206, "icon": "❌"},
    "demande_en_cours_rapo": {"phase": "Recours RAPO", "explication": "Recours administratif en cours", "etape": 12, "rang": 1207, "icon": "⚖️"},
    "controle_demande_notifiee": {"phase": "Décision notifiée", "explication": "Décision de contrôle notifiée", "etape": 12, "rang": 1208, "icon": "📬"},
    "irrecevabilite_manifeste": {"phase": "Irrecevabilité", "explication": "Conditions légales non remplies", "etape": 12, "rang": 1209, "icon": "❌"},
    "irrecevabilite_manifeste_en_delais_recours": {"phase": "Irrecevabilité", "explication": "Irrecevable, délai de recours ouvert", "etape": 12, "rang": 1210, "icon": "❌"},
    "css_en_delais_recours": {"phase": "Classement sans suite", "explication": "Classé sans suite, recours possible", "etape": 12, "rang": 1211, "icon": "⚠️"},
    "css_notifie": {"phase": "Classement sans suite", "explication": "Classement sans suite notifié", "etape": 12, "rang": 1212, "icon": "⚠️"},
}


# ─────────────────────────────────────────────────────────────
# Logger
# ─────────────────────────────────────────────────────────────

def setup_logging(log_file, verbose=False):
    """Configure le logging vers fichier + console."""
    log_path = Path(log_file).expanduser()
    log_path.parent.mkdir(parents=True, exist_ok=True)

    handlers = [
        logging.FileHandler(log_path, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]

    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=handlers
    )
    return logging.getLogger('anef_tracker')


# ─────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────

def load_config():
    """Charge la configuration depuis config.yaml."""
    if not CONFIG_FILE.exists():
        print(f"❌ Fichier de configuration introuvable : {CONFIG_FILE}")
        print(f"   Créez-le à partir de config.yaml.example")
        sys.exit(1)

    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    # Valeurs par défaut
    config.setdefault('schedule', {})
    config['schedule'].setdefault('hours', [8, 19])

    config.setdefault('notifications', {})
    config['notifications'].setdefault('macos', True)
    config['notifications'].setdefault('email', {'enabled': False})
    config['notifications'].setdefault('telegram', {'enabled': False})

    config.setdefault('options', {})
    config['options'].setdefault('log_file', str(DEFAULT_LOG_FILE))
    config['options'].setdefault('history_file', str(DEFAULT_HISTORY_FILE))
    config['options'].setdefault('notify_on_same_status', False)
    config['options'].setdefault('verbose', False)

    return config


# ─────────────────────────────────────────────────────────────
# Connexion ANEF (SSO Keycloak)
# ─────────────────────────────────────────────────────────────

class ANEFSession:
    """Gère la session authentifiée avec le portail ANEF via SSO Keycloak."""

    def __init__(self, username, password, logger):
        self.username = username
        self.password = password
        self.log = logger
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7',
        })

    def login(self):
        """Se connecte au portail ANEF via le SSO Keycloak.

        Le flux OpenID Connect ANEF fonctionne ainsi :
        1. GET /api/anf/auth/login → redirige vers Keycloak avec des paramètres OIDC
        2. Keycloak affiche le formulaire → POST username/password
        3. Keycloak redirige vers le callback ANEF avec un code d'autorisation
        4. Le backend ANEF échange le code contre un token et pose des cookies de session
        """
        self.log.info("🔐 Connexion au portail ANEF...")

        try:
            # Étape 1 : Accéder au endpoint de login qui redirige vers Keycloak
            self.log.debug("Étape 1 : Accès au endpoint de login ANEF...")
            login_resp = self.session.get(
                f"{ANEF_BASE}/api/anf/auth/login",
                allow_redirects=True,
                timeout=30
            )

            if login_resp.status_code != 200:
                # Essayer l'URL alternative
                self.log.debug("Tentative URL alternative...")
                login_resp = self.session.get(
                    f"{ANEF_BASE}/api/auth/login",
                    allow_redirects=True,
                    timeout=30
                )

            if login_resp.status_code != 200:
                raise ConnectionError(f"Impossible d'accéder à la page de login (HTTP {login_resp.status_code})")

            current_url = login_resp.url
            self.log.debug(f"URL après redirection : {current_url[:100]}...")

            # Vérifier si on est déjà connecté
            if 'mon-compte' in current_url or 'espace-personnel' in current_url:
                self.log.info("✅ Déjà connecté !")
                return True

            # Étape 2 : Extraire le formulaire de login Keycloak
            soup = BeautifulSoup(login_resp.text, 'html.parser')
            login_form = soup.find('form', id='kc-form-login') or soup.find('form')

            if not login_form:
                # Peut-être que l'URL de login SSO est dans la page ANEF
                # Essayer de trouver le lien de connexion
                self.log.debug("Formulaire non trouvé, recherche d'un lien SSO...")
                sso_link = None
                for link in soup.find_all('a', href=True):
                    if 'sso' in link['href'] or 'auth' in link['href']:
                        sso_link = link['href']
                        break

                if sso_link:
                    self.log.debug(f"Lien SSO trouvé : {sso_link[:80]}...")
                    login_resp = self.session.get(sso_link, allow_redirects=True, timeout=30)
                    soup = BeautifulSoup(login_resp.text, 'html.parser')
                    login_form = soup.find('form', id='kc-form-login') or soup.find('form')

            if not login_form:
                self.log.error("❌ Formulaire de login non trouvé dans la page")
                self.log.debug(f"Contenu de la page (500 chars) : {login_resp.text[:500]}")
                raise ConnectionError("Formulaire de login non trouvé")

            # Extraire l'URL d'action du formulaire
            form_action = login_form.get('action', '')
            if not form_action.startswith('http'):
                form_action = urljoin(login_resp.url, form_action)

            self.log.debug(f"URL du formulaire : {form_action[:100]}...")

            # Extraire les champs cachés du formulaire
            form_data = {}
            for hidden in login_form.find_all('input', type='hidden'):
                name = hidden.get('name')
                value = hidden.get('value', '')
                if name:
                    form_data[name] = value

            # Ajouter les identifiants
            form_data['username'] = self.username
            form_data['password'] = self.password

            # Étape 3 : Soumettre le formulaire
            self.log.info("📤 Soumission des identifiants...")
            submit_resp = self.session.post(
                form_action,
                data=form_data,
                allow_redirects=True,
                timeout=30
            )

            # Vérifier le résultat
            final_url = submit_resp.url
            self.log.debug(f"URL finale : {final_url[:100]}...")

            # Vérifier si le login a échoué
            if 'error' in final_url or submit_resp.status_code >= 400:
                # Chercher un message d'erreur dans la page
                error_soup = BeautifulSoup(submit_resp.text, 'html.parser')
                error_msg = error_soup.find(class_='alert-error') or error_soup.find(class_='kc-feedback-text')
                if error_msg:
                    raise ConnectionError(f"Identifiants incorrects : {error_msg.get_text(strip=True)}")
                raise ConnectionError("Login échoué (erreur dans l'URL)")

            # Vérifier si on est redirigé vers la page de changement de mot de passe
            if 'UPDATE_PASSWORD' in final_url or 'required-action' in final_url:
                raise ConnectionError("Votre mot de passe ANEF a expiré. Renouvelez-le sur le portail.")

            # Vérifier qu'on est bien connecté en testant l'API
            self.log.debug("Vérification de la session...")
            test_resp = self.session.get(ANEF_API_STEPPER, timeout=15)
            if test_resp.status_code == 200:
                try:
                    data = test_resp.json()
                    if data.get('dossier', {}).get('statut'):
                        self.log.info("✅ Connexion réussie et API accessible !")
                        return True
                except (json.JSONDecodeError, KeyError):
                    pass

            # Si l'API ne répond pas directement, la session est peut-être quand même valide
            if 'JSESSIONID' in str(self.session.cookies) or any('anef' in c.domain for c in self.session.cookies):
                self.log.info("✅ Connexion réussie (cookies de session détectés)")
                return True

            self.log.warning("⚠️ Login terminé mais session incertaine")
            return True

        except requests.exceptions.Timeout:
            raise ConnectionError("Timeout lors de la connexion (le site ANEF est peut-être en maintenance)")
        except requests.exceptions.ConnectionError as e:
            raise ConnectionError(f"Impossible de se connecter au site ANEF : {e}")

    def fetch_stepper(self):
        """Appelle l'API dossier-stepper et retourne les données brutes."""
        self.log.debug("📡 Appel API dossier-stepper...")
        resp = self.session.get(ANEF_API_STEPPER, timeout=15)

        if resp.status_code == 502 or resp.status_code == 503:
            raise ConnectionError("Site ANEF en maintenance")

        if resp.status_code == 401 or resp.status_code == 403:
            raise ConnectionError("Session expirée, reconnexion nécessaire")

        resp.raise_for_status()
        return resp.json()

    def fetch_details(self, dossier_id):
        """Appelle l'API détails du dossier."""
        self.log.debug(f"📡 Appel API détails dossier {dossier_id}...")
        resp = self.session.get(f"{ANEF_API_DOSSIER}{dossier_id}", timeout=15)
        if resp.status_code != 200:
            self.log.warning(f"API détails : HTTP {resp.status_code}")
            return None
        raw = resp.json()
        return raw.get('data', raw)


# ─────────────────────────────────────────────────────────────
# Déchiffrement RSA
# ─────────────────────────────────────────────────────────────

def decrypt_status(encrypted_base64, logger):
    """Déchiffre le statut avec la clé RSA (RSA-OAEP SHA-256)."""
    try:
        private_key = serialization.load_pem_private_key(
            PRIVATE_KEY_PEM.encode(),
            password=None
        )
        decoded = base64.b64decode(encrypted_base64)
        decrypted = private_key.decrypt(
            decoded,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        result = decrypted.decode('utf-8')
        # Format: "CODE_STATUT#K#2026-07-04"
        parts = result.split('#K#')
        statut_code = parts[0]
        date_statut = parts[1] if len(parts) > 1 else None
        logger.info(f"🔓 Statut déchiffré : {statut_code} (date: {date_statut})")
        return statut_code, date_statut
    except Exception as e:
        logger.error(f"❌ Erreur déchiffrement RSA : {e}")
        return None, None


def get_status_info(statut_code):
    """Retourne les informations détaillées d'un statut."""
    code = (statut_code or '').lower().strip()
    info = STATUTS.get(code)
    if info:
        rang = info['rang']
        sub = f"{rang // 100}.{rang % 100}" if rang % 100 != 0 else str(rang // 100)
        return {**info, 'code': code, 'sous_etape': sub, 'found': True}
    return {
        'phase': 'Statut inconnu', 'explication': statut_code or 'N/A',
        'etape': 0, 'rang': 0, 'icon': '❓', 'code': code,
        'sous_etape': '?', 'found': False,
        'description': 'Statut non répertorié. Contactez votre préfecture.'
    }


# ─────────────────────────────────────────────────────────────
# Historique
# ─────────────────────────────────────────────────────────────

def load_history(history_file):
    """Charge l'historique des statuts."""
    path = Path(history_file).expanduser()
    if path.exists():
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {'entries': [], 'last_status': None, 'last_check': None}


def save_history(history, history_file):
    """Sauvegarde l'historique des statuts."""
    path = Path(history_file).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


# ─────────────────────────────────────────────────────────────
# Notifications
# ─────────────────────────────────────────────────────────────

def notify_macos(title, message, subtitle="", sound="default"):
    """Envoie une notification native macOS."""
    try:
        script = f'''
        display notification "{message}" with title "{title}" subtitle "{subtitle}" sound name "{sound}"
        '''
        subprocess.run(['osascript', '-e', script], check=True, capture_output=True)
        return True
    except Exception as e:
        logging.warning(f"Notification macOS échouée : {e}")
        return False


def notify_email(config, subject, body):
    """Envoie un email de notification."""
    email_cfg = config.get('notifications', {}).get('email', {})
    if not email_cfg.get('enabled'):
        return False

    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = email_cfg['sender']
        msg['To'] = email_cfg['recipient']

        # Version texte
        msg.attach(MIMEText(body, 'plain', 'utf-8'))

        # Version HTML
        html_body = body.replace('\n', '<br>')
        html = f"""
        <html>
        <body style="font-family: -apple-system, sans-serif; padding: 20px; background: #f5f5f5;">
            <div style="max-width: 600px; margin: 0 auto; background: white; border-radius: 12px; padding: 30px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
                <h2 style="color: #1a1a2e; margin-top: 0;">🏛️ {subject}</h2>
                <div style="color: #333; line-height: 1.6;">{html_body}</div>
                <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
                <p style="color: #888; font-size: 12px;">ANEF Status Tracker — Suivi automatique</p>
            </div>
        </body>
        </html>
        """
        msg.attach(MIMEText(html, 'html', 'utf-8'))

        with smtplib.SMTP(email_cfg['smtp_server'], email_cfg.get('smtp_port', 587)) as server:
            server.starttls()
            server.login(email_cfg['sender'], email_cfg['password'])
            server.sendmail(email_cfg['sender'], email_cfg['recipient'], msg.as_string())

        logging.info("📧 Email envoyé !")
        return True
    except Exception as e:
        logging.error(f"❌ Email échoué : {e}")
        return False


def notify_telegram(config, message):
    """Envoie un message Telegram."""
    tg_cfg = config.get('notifications', {}).get('telegram', {})
    if not tg_cfg.get('enabled'):
        return False

    try:
        url = f"https://api.telegram.org/bot{tg_cfg['bot_token']}/sendMessage"
        resp = requests.post(url, json={
            'chat_id': tg_cfg['chat_id'],
            'text': message,
            'parse_mode': 'HTML'
        }, timeout=10)
        resp.raise_for_status()
        logging.info("📱 Telegram envoyé !")
        return True
    except Exception as e:
        logging.error(f"❌ Telegram échoué : {e}")
        return False


def send_notifications(config, status_info, previous_status, is_change, logger):
    """Envoie les notifications sur tous les canaux configurés."""
    now = datetime.now(TZ_PARIS).strftime('%d/%m/%Y à %H:%M')

    if is_change:
        title = "🔔 Changement de statut ANEF !"
        if status_info.get('etape', 0) >= 10:
            title = "🎉 Bonne nouvelle ANEF !"
    else:
        title = "ℹ️ Statut ANEF inchangé"

    sub = status_info.get('sous_etape', '?')
    phase = status_info.get('phase', '?')
    explication = status_info.get('explication', '?')
    icon = status_info.get('icon', '📋')
    description = status_info.get('description', '')

    # Message court (macOS / Telegram)
    short_msg = f"{icon} {phase} — {explication}\nÉtape {sub}/12"
    if is_change and previous_status:
        prev_info = get_status_info(previous_status)
        short_msg += f"\n(avant : {prev_info.get('sous_etape', '?')} — {prev_info.get('explication', '?')})"

    # Message long (email)
    long_msg = f"""Vérification du {now}

{icon} Statut actuel : {phase}
📋 Détail : {explication}
📊 Étape : {sub} / 12

{description}
"""
    if is_change and previous_status:
        prev_info = get_status_info(previous_status)
        long_msg += f"""
🔄 CHANGEMENT DÉTECTÉ !
   Avant : {prev_info.get('sous_etape', '?')} — {prev_info.get('explication', '?')}
   Après : {sub} — {explication}
"""

    # Envoyer sur chaque canal
    notif_cfg = config.get('notifications', {})

    if notif_cfg.get('macos', True):
        notify_macos(title, f"{icon} {explication} (étape {sub}/12)", phase)

    if notif_cfg.get('email', {}).get('enabled'):
        notify_email(config, f"{title} — Étape {sub}/12", long_msg)

    if notif_cfg.get('telegram', {}).get('enabled'):
        tg_msg = f"<b>{title}</b>\n\n{icon} <b>{phase}</b>\n{explication}\n📊 Étape <b>{sub}</b>/12"
        if description:
            tg_msg += f"\n\n{description}"
        if is_change and previous_status:
            prev_info = get_status_info(previous_status)
            tg_msg += f"\n\n🔄 <i>Avant : {prev_info.get('sous_etape', '?')} — {prev_info.get('explication', '?')}</i>"
        tg_msg += f"\n\n🕐 {now}"
        notify_telegram(config, tg_msg)


# ─────────────────────────────────────────────────────────────
# Point d'entrée principal
# ─────────────────────────────────────────────────────────────

def check_status(config, logger, force_notify=False):
    """Vérifie le statut ANEF et notifie si changement."""
    anef_cfg = config.get('anef', {})
    username = anef_cfg.get('username')
    password = anef_cfg.get('password')

    if not username or not password:
        logger.error("❌ Identifiants ANEF manquants dans config.yaml")
        return False

    options = config.get('options', {})
    history_file = options.get('history_file', str(DEFAULT_HISTORY_FILE))
    history = load_history(history_file)

    try:
        # 1. Connexion
        session = ANEFSession(username, password, logger)
        session.login()

        # 2. Récupérer le statut
        stepper_data = session.fetch_stepper()
        dossier = stepper_data.get('dossier', {})
        encrypted_status = dossier.get('statut')
        dossier_id = dossier.get('id')

        if not encrypted_status:
            logger.error("❌ Pas de statut dans la réponse API")
            return False

        # 3. Déchiffrer
        statut_code, date_statut = decrypt_status(encrypted_status, logger)
        if not statut_code:
            logger.error("❌ Déchiffrement échoué")
            return False

        # 4. Récupérer les détails (optionnel)
        details = None
        if dossier_id:
            try:
                details = session.fetch_details(dossier_id)
            except Exception as e:
                logger.warning(f"Détails non récupérés : {e}")

        # 5. Comparer avec le dernier statut
        previous_status = history.get('last_status')
        is_change = previous_status != statut_code.lower()
        status_info = get_status_info(statut_code)

        now_str = datetime.now(TZ_PARIS).isoformat()

        # 6. Mettre à jour l'historique
        entry = {
            'timestamp': now_str,
            'statut': statut_code.lower(),
            'date_statut': date_statut,
            'phase': status_info['phase'],
            'explication': status_info['explication'],
            'etape': status_info['etape'],
            'sous_etape': status_info['sous_etape'],
            'changed': is_change,
            'dossier_id': dossier_id
        }
        history['entries'].append(entry)
        history['last_status'] = statut_code.lower()
        history['last_check'] = now_str
        history['last_date_statut'] = date_statut

        # Garder les 500 dernières entrées
        history['entries'] = history['entries'][-500:]
        save_history(history, history_file)

        # 7. Afficher le résultat
        logger.info(f"{'='*50}")
        logger.info(f"{status_info['icon']} Statut : {status_info['phase']} — {status_info['explication']}")
        logger.info(f"📊 Étape : {status_info['sous_etape']}/12")
        logger.info(f"📅 Date statut : {date_statut or 'N/A'}")
        if is_change:
            logger.info(f"🔔 CHANGEMENT détecté ! (avant : {previous_status or 'premier check'})")
        else:
            logger.info(f"ℹ️ Statut inchangé depuis le dernier check")
        logger.info(f"{'='*50}")

        # 8. Notifier
        should_notify = is_change or force_notify or options.get('notify_on_same_status', False)
        if should_notify:
            send_notifications(config, status_info, previous_status, is_change, logger)

        return True

    except ConnectionError as e:
        logger.error(f"❌ Erreur de connexion : {e}")
        # Notifier de l'erreur aussi
        if config.get('notifications', {}).get('macos', True):
            notify_macos("⚠️ ANEF Tracker — Erreur", str(e))
        return False
    except Exception as e:
        logger.error(f"❌ Erreur inattendue : {e}", exc_info=True)
        return False


def show_history(config):
    """Affiche l'historique des vérifications."""
    options = config.get('options', {})
    history_file = options.get('history_file', str(DEFAULT_HISTORY_FILE))
    history = load_history(history_file)

    if not history['entries']:
        print("📭 Aucun historique. Lancez une première vérification.")
        return

    print(f"\n📋 Historique des vérifications ({len(history['entries'])} entrées)\n")
    print(f"{'Date':<22} {'Étape':<8} {'Phase':<25} {'Changé'}")
    print(f"{'─'*22} {'─'*8} {'─'*25} {'─'*8}")

    for entry in history['entries'][-20:]:
        ts = entry.get('timestamp', '')[:19].replace('T', ' ')
        sub = entry.get('sous_etape', '?')
        phase = entry.get('phase', '?')[:25]
        changed = '🔔 OUI' if entry.get('changed') else '—'
        print(f"{ts:<22} {sub:<8} {phase:<25} {changed}")

    print(f"\n📊 Dernier statut : {history.get('last_status', 'N/A')}")
    print(f"🕐 Dernière vérification : {history.get('last_check', 'N/A')[:19].replace('T', ' ')}")


def main():
    parser = argparse.ArgumentParser(description='ANEF Status Tracker — Suivi automatique')
    parser.add_argument('--verbose', '-v', action='store_true', help='Mode verbeux')
    parser.add_argument('--force-notify', '-f', action='store_true', help='Forcer l\'envoi des notifications')
    parser.add_argument('--history', action='store_true', help='Afficher l\'historique')
    parser.add_argument('--config', type=str, default=str(CONFIG_FILE), help='Chemin du fichier de configuration')
    args = parser.parse_args()

    global CONFIG_FILE
    CONFIG_FILE = Path(args.config)

    config = load_config()
    if args.verbose:
        config['options']['verbose'] = True

    if args.history:
        show_history(config)
        return

    logger = setup_logging(
        config['options']['log_file'],
        verbose=config['options']['verbose']
    )

    logger.info("🚀 ANEF Status Tracker démarré")
    success = check_status(config, logger, force_notify=args.force_notify)
    logger.info(f"{'✅' if success else '❌'} Terminé")
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
