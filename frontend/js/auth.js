import { clearSession, fetchJSON, profileApi, saveSession } from "./api.js";
import { API_BASE } from "./config.js";
import { plural, setLanguage, t } from "./i18n.js";
import { applyViewVisibility, loadView, viewFromHash } from "./nav.js";
import { openOnboarding } from "./profile-form.js";
import { el, state } from "./state.js";
import { closeSheet, openSheet, toast, withBusy } from "./ui.js";
import { todayISO } from "./util.js";
import { rerenderProgressCharts } from "./views/progress.js";

// Ustawienia logowania z /api/meta (T-PUB): lista użytkowników albo nazwa, minimalna długość PIN-u, pierwszy start.
export const loginMeta = { showUserList: true, pinMinLength: 6, setupRequired: false, allowSignup: true };
const PIN_MAX_LENGTH = 8;

// --- blokada i sesja -------------------------------------------------------------------------------

export function showScreen(name) {
  // name === null: zostaje ekran startowy (wznawianie sesji po przeładowaniu, bez mignięcia ekranu blokady)
  el.bootScreen.hidden = name !== null;
  el.lockScreen.hidden = name !== "lock";
  el.app.hidden = name !== "app";
}

export function lockUser(message = "") {
  state.token = "";
  state.tokenExpiresAt = "";
  pendingPin = "";
  clearSession();
  state.entriesById.clear();
  document.querySelectorAll("dialog[open]").forEach((dialog) => dialog.close());
  showScreen("lock");
  el.pinInput.value = "";
  el.authStatus.textContent = message;
  el.authStatus.className = message ? "form-status error" : "form-status";
}

export function pinRuleText() {
  return t("PIN: {min}–{max} cyfr, bez prostych ciągów (np. 123456, 111111).", { min: loginMeta.pinMinLength, max: PIN_MAX_LENGTH });
}

function isValidNewPin(pin) {
  return new RegExp(`^\\d{${loginMeta.pinMinLength},${PIN_MAX_LENGTH}}$`).test(pin);
}

export async function loadUsers(selectId = null) {
  const meta = await fetchJSON(`${API_BASE}/meta`);
  loginMeta.showUserList = meta.show_user_list !== false;
  loginMeta.pinMinLength = meta.pin_min_length || 6;
  loginMeta.setupRequired = Boolean(meta.setup_required);
  loginMeta.allowSignup = Boolean(meta.allow_signup);
  el.pinRuleHint.textContent = pinRuleText();
  const firstRun = loginMeta.setupRequired;
  el.firstRun.hidden = !firstRun;
  el.unlockForm.hidden = firstRun;
  // ALLOW_SIGNUP=false: bez przycisku "Nowy użytkownik" (pierwszy start działa zawsze).
  el.lockLinks.hidden = firstRun || !loginMeta.allowSignup;
  el.userSelectField.hidden = !loginMeta.showUserList;
  el.loginNameField.hidden = loginMeta.showUserList;
  el.userSelect.innerHTML = "";
  if (firstRun) {
    state.userId = null;
    return;
  }
  if (!loginMeta.showUserList) {
    // Lista ukryta (SHOW_USER_LIST=false): użytkownik wpisuje nazwę; urządzenie pamięta ostatnią (nie PIN).
    if (!el.loginNameInput.value) el.loginNameInput.value = readLocal(LAST_USER_KEY) || "";
    if (selectId) state.userId = selectId;
    return;
  }
  const users = await fetchJSON(`${API_BASE}/users`);
  users.forEach((user) => {
    const option = document.createElement("option");
    option.value = String(user.id);
    option.textContent = user.display_name;
    el.userSelect.appendChild(option);
  });
  const selected = users.find((user) => user.id === selectId) || users[0];
  if (!selected) return;
  state.userId = selected.id;
  state.userName = selected.display_name;
  el.userSelect.value = String(selected.id);
}

export function focusLogin() {
  if (loginMeta.setupRequired) el.firstRunBtn.focus();
  else if (!loginMeta.showUserList && !el.loginNameInput.value) el.loginNameInput.focus();
  else el.pinInput.focus();
}

// --- localStorage: zaufane urządzenia i ostatnia nazwa (nigdy PIN) ---------------------------------------

const DEVICE_KEY = "calico.devices";
const LAST_USER_KEY = "calico.lastUser";
const MAX_DEVICE_TOKENS = 10;

function readLocal(key) {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function writeLocal(key, value) {
  try {
    localStorage.setItem(key, value);
  } catch {
    // tryb prywatny / zablokowany storage - bez zapamiętywania
  }
}

function deviceTokens() {
  try {
    const tokens = JSON.parse(readLocal(DEVICE_KEY) || "[]");
    return Array.isArray(tokens) ? tokens.filter((token) => typeof token === "string").slice(0, MAX_DEVICE_TOKENS) : [];
  } catch {
    return [];
  }
}

function tokenUserId(token) {
  try {
    const payload = token.split(".")[0].replace(/-/g, "+").replace(/_/g, "/");
    return JSON.parse(atob(payload)).uid;
  } catch {
    return null;
  }
}

function rememberDevice(token) {
  if (!token) return;
  const uid = tokenUserId(token);
  const others = deviceTokens().filter((stored) => tokenUserId(stored) !== uid);
  writeLocal(DEVICE_KEY, JSON.stringify([token, ...others].slice(0, MAX_DEVICE_TOKENS)));
}

// --- logowanie -----------------------------------------------------------------------------------------

// PIN zaraz po zalogowaniu - tylko w pamięci, do wymuszonej zmiany zbyt krótkiego PIN-u (serwer wymaga obecnego).
let pendingPin = "";

async function unlock() {
  const pin = el.pinInput.value.trim();
  const name = el.loginNameInput.value.trim();
  if (loginMeta.showUserList ? !state.userId : !name) {
    el.authStatus.textContent = t("Podaj nazwę użytkownika.");
    el.authStatus.className = "form-status error";
    el.loginNameInput.focus();
    return;
  }
  if (!/^\d{4,8}$/.test(pin)) {
    el.authStatus.textContent = t("PIN musi mieć 4–8 cyfr.");
    el.authStatus.className = "form-status error";
    return;
  }
  let session;
  try {
    session = await verifyPin(pin, loginMeta.showUserList ? { user_id: state.userId } : { name });
  } catch (error) {
    el.authStatus.textContent = error.message;
    el.authStatus.className = "form-status error";
    el.pinInput.select();
    return;
  }
  if (!loginMeta.showUserList) writeLocal(LAST_USER_KEY, name);
  el.pinInput.value = "";
  el.authStatus.textContent = "";
  await startSession(session, pin);
}

function verifyPin(pin, who) {
  return fetchJSON(`${API_BASE}/auth/verify`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...who, pin, device_tokens: deviceTokens() }),
  });
}

export async function startSession(session, pin = "") {
  state.token = session.token;
  state.tokenExpiresAt = session.expires_at || session.expiresAt || "";
  if (session.user_id) state.userId = session.user_id;
  if (session.display_name) state.userName = session.display_name;
  if (session.language) setLanguage(session.language); // język zapamiętany na koncie (z /auth/verify)
  rememberDevice(session.device_token);
  saveSession();
  if (session.failed_attempts > 0) {
    const count = session.failed_attempts;
    state.loginNotice = t("Od ostatniego logowania: {count} {attempts} logowania na to konto.", {
      count,
      attempts: plural(count, "nieudana próba", "nieudane próby", "nieudanych prób"),
    });
  }
  if (session.pin_change_required) {
    pendingPin = pin;
    showScreen("lock");
    openForcedPinChange();
    return;
  }
  const profile = await profileApi();
  if (!profile.is_complete) {
    showScreen("lock");
    openOnboarding();
    return;
  }
  await enterApp();
}

export async function enterApp() {
  state.logDate = todayISO();
  el.settingsUser.textContent = state.userName;
  el.navUser.textContent = state.userName;
  const view = viewFromHash();
  state.view = view;
  applyViewVisibility(view);
  await loadView(view);
  showScreen("app");
  // Wykresy rysowane przy ukrytej aplikacji mialy zastepcza szerokosc - przerysuj w docelowej.
  requestAnimationFrame(rerenderProgressCharts);
  if (state.loginNotice) {
    toast(state.loginNotice, "warning", 12000);
    state.loginNotice = "";
  }
}

// --- wymuszona zmiana zbyt krótkiego PIN-u (T-PUB) --------------------------------------------------------

export function openForcedPinChange() {
  if (el.forcedPinDialog.open) return;
  document.querySelectorAll("dialog[open]").forEach((dialog) => dialog.close());
  el.forcedPinForm.reset();
  el.forcedPinError.textContent = "";
  el.forcedPinHint.textContent = `${t("Twój PIN jest za krótki. Ustaw nowy, aby kontynuować.")} ${pinRuleText()}`;
  el.forcedPinDialog.showModal();
  el.forcedPinNew.focus();
}

el.forcedPinDialog.addEventListener("cancel", (event) => event.preventDefault());

el.forcedPinForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const newPin = el.forcedPinNew.value.trim();
  if (!isValidNewPin(newPin)) {
    el.forcedPinError.textContent = pinRuleText();
    return;
  }
  if (newPin !== el.forcedPinRepeat.value.trim()) {
    el.forcedPinError.textContent = t("PIN-y nie są takie same.");
    return;
  }
  if (!pendingPin) {
    // np. po przeładowaniu strony - obecny PIN nie jest już znany
    lockUser(t("Zaloguj się ponownie, aby ustawić nowy PIN."));
    return;
  }
  try {
    await withBusy(el.forcedPinSaveBtn, async () => {
      const changed = await fetchJSON(`${API_BASE}/users/${state.userId}/pin`, {
        method: "POST",
        headers: { Authorization: `Bearer ${state.token}`, "Content-Type": "application/json" },
        body: JSON.stringify({ current_pin: pendingPin, new_pin: newPin }),
      });
      pendingPin = "";
      closeSheet(el.forcedPinDialog);
      await startSession({ ...changed, failed_attempts: 0 });
      toast(t("PIN został zmieniony."), "success");
    });
  } catch (error) {
    el.forcedPinError.textContent = error.message;
  }
});

el.forcedPinLogoutBtn.addEventListener("click", () => {
  lockUser();
  loadUsers(state.userId).then(focusLogin);
});

// --- ekran blokady: użytkownicy -----------------------------------------------------------------------------

el.unlockForm.addEventListener("submit", (event) => {
  event.preventDefault();
  withBusy(el.unlockBtn, unlock).catch((error) => {
    el.authStatus.textContent = error.message;
    el.authStatus.className = "form-status error";
  });
});

el.userSelect.addEventListener("change", () => {
  if (!el.userSelect.value) return;
  state.userId = Number(el.userSelect.value);
  state.userName = el.userSelect.options[el.userSelect.selectedIndex].textContent;
  el.authStatus.textContent = "";
  el.pinInput.value = "";
  el.pinInput.focus();
});

function openNewUserDialog() {
  el.userDialogForm.reset();
  el.userDialogError.textContent = "";
  el.setupCodeField.hidden = !loginMeta.setupRequired;
  el.newUserPinLabel.textContent = t("PIN ({min}–{max} cyfr)", { min: loginMeta.pinMinLength, max: PIN_MAX_LENGTH });
  openSheet(el.userDialog);
  (loginMeta.setupRequired ? el.setupCodeInput : el.newUserName).focus();
}

el.newUserBtn.addEventListener("click", openNewUserDialog);
el.firstRunBtn.addEventListener("click", openNewUserDialog);

el.userDialogForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const displayName = el.newUserName.value.trim();
  const pin = el.newUserPin.value.trim();
  const setupCode = el.setupCodeInput.value.trim();
  if (loginMeta.setupRequired && !setupCode) {
    el.userDialogError.textContent = t("Podaj kod pierwszego uruchomienia z logów kontenera.");
    return;
  }
  if (displayName.length < 2) {
    el.userDialogError.textContent = t("Nazwa musi mieć co najmniej 2 znaki.");
    return;
  }
  if (!isValidNewPin(pin)) {
    el.userDialogError.textContent = pinRuleText();
    return;
  }
  if (pin !== el.newUserPin2.value.trim()) {
    el.userDialogError.textContent = t("PIN-y nie są takie same.");
    return;
  }
  try {
    await withBusy(el.userDialogSaveBtn, async () => {
      const user = await fetchJSON(`${API_BASE}/users`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ display_name: displayName, pin, ...(loginMeta.setupRequired ? { setup_code: setupCode } : {}) }),
      });
      closeSheet(el.userDialog);
      await loadUsers(user.id);
      if (!loginMeta.showUserList) {
        el.loginNameInput.value = user.display_name;
        writeLocal(LAST_USER_KEY, user.display_name);
      }
      await startSession(await verifyPin(pin, { user_id: user.id }), pin);
    });
  } catch (error) {
    el.userDialogError.textContent = error.message;
  }
});
