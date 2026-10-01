// Calico – punkt wejścia (index.html: <script type="module" src="/js/main.js">). Moduły bez bundlera:
//   config.js   stałe domenowe            state.js  el (elementy DOM), state     util.js  formatowanie, daty
//   ui.js       toasty, withBusy, panele  api.js    fetchJSON, sesja             auth.js  blokada, użytkownicy
//   nav.js      routing (location.hash)   charts.js wykresy SVG                  views/*  widoki Dziś…Ustawienia
//   entry-sheet.js  panel wpisu i akcje pozycji   profile-form.js  korekta celu, onboarding (D8)
// Moduły z obsługą zdarzeń importujemy jawnie (rejestrują listenery przy ładowaniu).
import "./nav.js";
import "./entry-sheet.js";
import "./profile-form.js";
import "./views/today.js";
import "./views/log.js";
import "./views/progress.js";
import "./views/goals.js";
import "./views/settings.js";
import { readSession } from "./api.js";
import { loadUsers, showScreen, startSession } from "./auth.js";
import { RING_CIRCUMFERENCE } from "./config.js";
import { el, state } from "./state.js";

// --- start -------------------------------------------------------------------------------------------------------

async function init() {
  el.ringProgress.style.strokeDasharray = `${RING_CIRCUMFERENCE}`;
  el.ringProgress.style.strokeDashoffset = `${RING_CIRCUMFERENCE}`;
  const saved = readSession();
  showScreen(saved ? null : "lock");
  try {
    await loadUsers(saved?.userId ?? null);
  } catch (error) {
    showScreen("lock");
    el.authStatus.textContent = error.message;
    el.authStatus.className = "form-status error";
    return;
  }
  if (saved && state.userId === saved.userId) {
    // Wznowienie sesji po przeładowaniu karty - bez ponownego pytania o PIN.
    try {
      await startSession(saved);
      return registerServiceWorker();
    } catch (error) {
      // 401 już wylogował (lockUser). Inny błąd (np. chwilowy brak sieci) nie kasuje sesji.
      if (state.token) {
        showScreen("lock");
        el.authStatus.textContent = `${error.message} Odśwież stronę albo podaj PIN.`;
        el.authStatus.className = "form-status error";
        return registerServiceWorker();
      }
    }
  }
  showScreen("lock");
  (state.userId ? el.pinInput : el.firstRunBtn).focus();
  registerServiceWorker();
}

function registerServiceWorker() {
  // Service worker działa tylko w bezpiecznym kontekście (https albo localhost).
  if ("serviceWorker" in navigator && window.isSecureContext) {
    navigator.serviceWorker.register("/sw.js").catch(() => {});
  }
}

init();
