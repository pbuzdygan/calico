import { lockUser, openForcedPinChange } from "./auth.js";
import { API_BASE, FIELD_LABELS } from "./config.js";
import { lang, t } from "./i18n.js";
import { openOnboarding } from "./profile-form.js";
import { state } from "./state.js";

// --- API -----------------------------------------------------------------------------------------

function formatApiError(payload, fallback) {
  if (payload && Array.isArray(payload.detail)) {
    return payload.detail
      .map((entry) => {
        const field = Array.isArray(entry.loc) ? entry.loc[entry.loc.length - 1] : "";
        return FIELD_LABELS[field] ? `${t(FIELD_LABELS[field])}: ${entry.msg}` : entry.msg;
      })
      .join(" ");
  }
  if (payload && typeof payload.detail === "string") return payload.detail;
  return fallback;
}

export async function fetchJSON(url, options = {}) {
  let response;
  try {
    // Accept-Language: komunikaty API w języku interfejsu.
    response = await fetch(url, { ...options, headers: { "Accept-Language": lang(), ...options.headers } });
  } catch {
    throw new Error(t("Brak połączenia z serwerem. Sprawdź, czy Calico działa."));
  }
  const raw = await response.text();
  let payload = null;
  try {
    payload = raw ? JSON.parse(raw) : null;
  } catch {
    payload = null;
  }
  if (!response.ok) {
    if (response.status === 428 && state.token) {
      // T-PUB: najpierw zmiana zbyt krótkiego PIN-u, potem profil (D8)
      if (payload?.code === "pin_change_required") openForcedPinChange();
      else openOnboarding();
    }
    if (response.status === 401 && state.token) {
      lockUser(t("PIN został zmieniony albo sesja wygasła. Odblokuj ponownie."));
    }
    const fallback = response.status >= 500 ? t("Błąd serwera ({status}).", { status: response.status }) : t("Błąd żądania ({status}).", { status: response.status });
    throw new Error(formatApiError(payload, fallback));
  }
  return payload;
}

export function userHeaders(extra = {}) {
  return { Authorization: `Bearer ${state.token}`, "Accept-Language": lang(), ...extra };
}

// --- sesja w sessionStorage: przetrwa przeładowanie karty (np. gdy telefon uśpi przeglądarkę w tle),
// znika po zamknięciu karty. Przechowujemy podpisany token z serwera, nie PIN.

const SESSION_KEY = "calico.session";

export function saveSession() {
  try {
    sessionStorage.setItem(
      SESSION_KEY,
      JSON.stringify({ userId: state.userId, userName: state.userName, token: state.token, expiresAt: state.tokenExpiresAt })
    );
  } catch {
    // tryb prywatny / zablokowany storage - sesja tylko w pamięci
  }
}

export function readSession() {
  try {
    const session = JSON.parse(sessionStorage.getItem(SESSION_KEY) || "null");
    if (!session?.token || !session.userId) return null;
    if (session.expiresAt && Date.parse(session.expiresAt) <= Date.now()) return null;
    return session;
  } catch {
    return null;
  }
}

export function clearSession() {
  try {
    sessionStorage.removeItem(SESSION_KEY);
  } catch {
    // brak dostępu do storage
  }
}

export function api(path, { method = "GET", body, params } = {}) {
  if (!state.userId || !state.token) return Promise.reject(new Error(t("Najpierw odblokuj użytkownika PIN-em.")));
  const query = new URLSearchParams({ user_id: String(state.userId), ...params });
  return fetchJSON(`${API_BASE}${path}?${query}`, {
    method,
    headers: userHeaders(body !== undefined ? { "Content-Type": "application/json" } : {}),
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
}

export function profileApi(suffix = "", { method = "GET", body } = {}) {
  return fetchJSON(`${API_BASE}/profile/${state.userId}${suffix}`, {
    method,
    headers: userHeaders(body !== undefined ? { "Content-Type": "application/json" } : {}),
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
}

