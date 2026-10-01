import { VIEWS } from "./config.js";
import { $, el, state } from "./state.js";
import { toastError } from "./ui.js";
import { loadGoals } from "./views/goals.js";
import { loadLog } from "./views/log.js";
import { loadSettings } from "./views/settings.js";
import { loadProgress } from "./views/progress.js";
import { loadToday } from "./views/today.js";

// --- nawigacja ----------------------------------------------------------------------------------------

export function viewFromHash() {
  const name = location.hash.replace(/^#\/?/, "");
  if (name === "more") return "settings"; // stary adres (zakładki, PWA)
  return VIEWS.includes(name) ? name : "today";
}

export function applyViewVisibility(view) {
  VIEWS.forEach((name) => {
    $(`view-${name}`).hidden = name !== view;
  });
  document.querySelectorAll(".nav-item").forEach((item) => {
    const active = item.dataset.view === view;
    item.classList.toggle("active", active);
    if (active) item.setAttribute("aria-current", "page");
    else item.removeAttribute("aria-current");
  });
}

export async function loadView(view) {
  if (view === "today") return loadToday();
  if (view === "log") return loadLog();
  if (view === "progress") return loadProgress();
  if (view === "goals") return loadGoals();
  if (view === "settings") return loadSettings();
  return undefined;
}

window.addEventListener("hashchange", () => {
  if (!state.token || el.app.hidden) return;
  state.view = viewFromHash();
  applyViewVisibility(state.view);
  window.scrollTo({ top: 0 });
  loadView(state.view).catch(toastError);
});

function goTo(view) {
  if (location.hash === `#/${view}`) loadView(view).catch(toastError);
  else location.hash = `#/${view}`;
}

export function goToLogDay(date) {
  state.logDate = date;
  goTo("log");
}

export async function refreshAfterChange() {
  await loadView(state.view);
}

