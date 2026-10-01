// Przełącznik języka (ekran blokady i Ustawienia). Wybór zapamiętany na urządzeniu (i18n.js)
// i na koncie zalogowanego użytkownika (PUT /api/users/{id}/language).
import { fetchJSON, userHeaders } from "./api.js";
import { API_BASE } from "./config.js";
import { lang, onLanguageChange, setLanguage } from "./i18n.js";
import { loadView } from "./nav.js";
import { updateGoalDeltaUi } from "./profile-form.js";
import { el, state } from "./state.js";
import { toastError } from "./ui.js";

export function renderLanguageButtons() {
  document.querySelectorAll("[data-lang]").forEach((button) => {
    const active = button.dataset.lang === lang();
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", String(active));
  });
}

document.querySelectorAll("[data-lang]").forEach((button) => button.addEventListener("click", () => setLanguage(button.dataset.lang)));

onLanguageChange((language) => {
  renderLanguageButtons();
  // Teksty ustawiane przez JS: formularze profilu i bieżący widok rysujemy ponownie.
  [el.profileForm, el.onboardingForm].forEach((form) => updateGoalDeltaUi(form));
  if (!state.token || !state.userId) return;
  fetchJSON(`${API_BASE}/users/${state.userId}/language`, {
    method: "PUT",
    headers: userHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ language }),
  }).catch(() => {});
  if (!el.app.hidden) loadView(state.view).catch(toastError);
});
