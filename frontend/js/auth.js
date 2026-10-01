import { clearSession, fetchJSON, profileApi, saveSession } from "./api.js";
import { API_BASE } from "./config.js";
import { applyViewVisibility, loadView, viewFromHash } from "./nav.js";
import { openOnboarding } from "./profile-form.js";
import { $, el, state } from "./state.js";
import { closeSheet, openSheet, withBusy } from "./ui.js";
import { todayISO } from "./util.js";
import { rerenderProgressCharts } from "./views/progress.js";

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
  clearSession();
  state.entriesById.clear();
  document.querySelectorAll("dialog[open]").forEach((dialog) => dialog.close());
  showScreen("lock");
  el.pinInput.value = "";
  el.authStatus.textContent = message;
  el.authStatus.className = message ? "form-status error" : "form-status";
}

export async function loadUsers(selectId = null) {
  const [users, meta] = await Promise.all([fetchJSON(`${API_BASE}/users`), fetchJSON(`${API_BASE}/meta`)]);
  el.userSelect.innerHTML = "";
  const firstRun = !users.length;
  el.firstRun.hidden = !firstRun;
  el.unlockForm.hidden = firstRun;
  // ALLOW_SIGNUP=false: bez przycisku "Nowy użytkownik" (pierwszy start działa zawsze).
  el.lockLinks.hidden = firstRun || !meta.allow_signup;
  if (firstRun) {
    state.userId = null;
    return;
  }
  users.forEach((user) => {
    const option = document.createElement("option");
    option.value = String(user.id);
    option.textContent = user.display_name;
    el.userSelect.appendChild(option);
  });
  const selected = users.find((user) => user.id === selectId) || users[0];
  state.userId = selected.id;
  state.userName = selected.display_name;
  el.userSelect.value = String(selected.id);
}

async function unlock() {
  if (!state.userId) return;
  const pin = el.pinInput.value.trim();
  if (!/^\d{4,8}$/.test(pin)) {
    el.authStatus.textContent = "PIN musi mieć 4–8 cyfr.";
    el.authStatus.className = "form-status error";
    return;
  }
  let session;
  try {
    session = await verifyPin(state.userId, pin);
  } catch (error) {
    el.authStatus.textContent = error.message;
    el.authStatus.className = "form-status error";
    el.pinInput.select();
    return;
  }
  el.pinInput.value = "";
  el.authStatus.textContent = "";
  await startSession(session);
}

function verifyPin(userId, pin) {
  return fetchJSON(`${API_BASE}/auth/verify`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: userId, pin }),
  });
}

export async function startSession(session) {
  state.token = session.token;
  state.tokenExpiresAt = session.expires_at || session.expiresAt || "";
  saveSession();
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
}

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
  openSheet(el.userDialog);
  el.newUserName.focus();
}

el.newUserBtn.addEventListener("click", openNewUserDialog);
el.firstRunBtn.addEventListener("click", openNewUserDialog);

el.userDialogForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const displayName = el.newUserName.value.trim();
  const pin = el.newUserPin.value.trim();
  if (displayName.length < 2) {
    el.userDialogError.textContent = "Nazwa musi mieć co najmniej 2 znaki.";
    return;
  }
  if (!/^\d{4,8}$/.test(pin)) {
    el.userDialogError.textContent = "PIN musi mieć 4–8 cyfr.";
    return;
  }
  if (pin !== el.newUserPin2.value.trim()) {
    el.userDialogError.textContent = "PIN-y nie są takie same.";
    return;
  }
  try {
    await withBusy(el.userDialogSaveBtn, async () => {
      const user = await fetchJSON(`${API_BASE}/users`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ display_name: displayName, pin }),
      });
      closeSheet(el.userDialog);
      await loadUsers(user.id);
      await startSession(await verifyPin(user.id, pin));
    });
  } catch (error) {
    el.userDialogError.textContent = error.message;
  }
});

