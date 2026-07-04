/**
 * Constantes et utilitaires centralisés - Extension ANEF Status Tracker
 */

// ─────────────────────────────────────────────────────────────
// URLs et domaines
// ─────────────────────────────────────────────────────────────

export const ANEF_BASE_URL = 'https://administration-etrangers-en-france.interieur.gouv.fr';

// Depuis mi-2026, l'app ANEF est servie sous le segment /usagers/
// (auparavant /particuliers/). L'URL "nue" (sans segment) redirige
// encore correctement, mais cibler /usagers/ évite une double redirection.
export const ANEF_ROUTES = {
  LOGIN: '/usagers/#/espace-personnel/connexion-inscription',
  MON_COMPTE: '/usagers/#/espace-personnel/mon-compte',
  HOME: '/usagers/#/'
};

// ─────────────────────────────────────────────────────────────
// Patterns de détection d'URL
// ─────────────────────────────────────────────────────────────

export const URLPatterns = {
  isANEFLogin: (url) => url?.includes('connexion-inscription') || false,
  isMonCompte: (url) => url?.includes('mon-compte') || false,
  isSSOPage: (url) => {
    if (!url) return false;
    return (
      url.includes('authentification') ||
      url.includes('agentconnect') ||
      url.includes('/auth') ||
      url.includes('/login') ||
      url.includes('sso.')
    );
  },
  isHomepage: (url) => {
    if (!url) return false;
    return url.endsWith('/#/') || url.endsWith('/#') || /\/(particuliers|usagers)\/#\/?$/.test(url);
  },
  isLoginPage: (url) => URLPatterns.isANEFLogin(url) || URLPatterns.isSSOPage(url),
  isPasswordExpired: (url) => !!(url?.includes('required-action') && url?.includes('UPDATE_PASSWORD'))
};

// ─────────────────────────────────────────────────────────────
// Messages autorisés (whitelist sécurité)
// ─────────────────────────────────────────────────────────────

export const ALLOWED_MESSAGE_TYPES = [
  'DOSSIER_DATA',
  'DOSSIER_STEPPER',
  'API_DATA',
  'NOTIFICATIONS',
  'USER_INFO',
  'HISTORIQUE',
  'MAINTENANCE',
  'EXPIRED_SESSION',
  'LOG'
];

// ─────────────────────────────────────────────────────────────
// Configuration des logs
// ─────────────────────────────────────────────────────────────

export const LogConfig = {
  MAX_LOGS: 500,
  STORAGE_KEY: 'debug_logs'
};

// ─────────────────────────────────────────────────────────────
// Supabase (statistiques anonymes communautaires)
// ─────────────────────────────────────────────────────────────

export const SUPABASE_URL = '__SUPABASE_URL__';
export const SUPABASE_ANON_KEY = '__SUPABASE_ANON_KEY__';
export const SUPABASE_EDGE_KEY = '__SUPABASE_EDGE_KEY__';

// ─────────────────────────────────────────────────────────────
// Telegram (Configuration Personnelle)
// ─────────────────────────────────────────────────────────────

export const TELEGRAM_BOT_TOKEN = '8977273354:AAEZUhWMAcAdMMnEhjM3Dci1EHBZB5945xU';
export const TELEGRAM_CHAT_ID = '5636131212';

