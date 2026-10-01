import { profileApi } from "./api.js";
import { enterApp, lockUser } from "./auth.js";
import { N_, t } from "./i18n.js";
import { el, state } from "./state.js";
import { toast, withBusy } from "./ui.js";
import { fmt, fmtSigned } from "./util.js";
import { readProfilePayload } from "./views/settings.js";

// --- korekta celu: znak zależny od celu i podgląd wyliczeń ------------------------------------------------

const GOAL_DELTA_UI = {
  cut: { label: N_("Deficyt kalorii"), sign: "−", suggested: 15, hint: N_("Redukcja: cel = zapotrzebowanie (TDEE) MINUS podany procent. Zwykle 10–20%.") },
  bulk: { label: N_("Nadwyżka kalorii"), sign: "+", suggested: 10, hint: N_("Masa: cel = zapotrzebowanie (TDEE) PLUS podany procent. Zwykle 5–15%.") },
  maintain: { label: N_("Korekta celu"), sign: "", suggested: 0, hint: N_("Utrzymanie: cel = zapotrzebowanie (TDEE), bez korekty.") },
};

const goalDeltaState = new Map();

function bindGoalDelta(form) {
  goalDeltaState.set(form, { timer: null, seq: 0 });
  form.goal_type.addEventListener("change", () => updateGoalDeltaUi(form, { goalChanged: true }));
  ["input", "change"].forEach((type) => form.addEventListener(type, () => scheduleGoalPreview(form)));
}

export function updateGoalDeltaUi(form, { goalChanged = false } = {}) {
  const box = form.querySelector("[data-goal-delta]");
  const input = form.goal_delta_pct_percent;
  const goal = form.goal_type.value;
  const ui = GOAL_DELTA_UI[goal];
  box.querySelector("[data-delta-label]").textContent = t(ui ? ui.label : "Korekta celu");
  const sign = box.querySelector("[data-delta-sign]");
  sign.textContent = ui ? ui.sign : "";
  sign.className = `delta-sign ${goal}`;
  box.querySelector("[data-delta-hint]").textContent = t(ui ? ui.hint : "Najpierw wybierz cel.");
  if (!ui) {
    input.disabled = true;
    input.value = "";
  } else if (goal === "maintain") {
    input.disabled = true;
    input.value = "0";
  } else {
    input.disabled = false;
    // Zmiana celu (np. redukcja -> masa) podpowiada typową wartość dla nowego kierunku.
    if (goalChanged || !input.value || input.value === "0") input.value = String(ui.suggested);
  }
  scheduleGoalPreview(form);
}

function formatGoalPreview(payload, preview) {
  const tdee = `${fmt(preview.tdee_kcal)} kcal`;
  const pct = fmt(payload.goal_delta_pct * 100);
  const params = { tdee, pct, target: fmt(preview.target_kcal), delta: fmtSigned(preview.delta_kcal) };
  if (payload.goal_type === "cut") return t("Zapotrzebowanie (TDEE): {tdee}. Cel: {tdee} − {pct}% = {target} kcal/dzień ({delta} kcal).", params);
  if (payload.goal_type === "bulk") return t("Zapotrzebowanie (TDEE): {tdee}. Cel: {tdee} + {pct}% = {target} kcal/dzień ({delta} kcal).", params);
  return t("Zapotrzebowanie (TDEE) = cel: {target} kcal/dzień.", params);
}

function scheduleGoalPreview(form) {
  const meta = goalDeltaState.get(form);
  const output = form.querySelector("[data-goal-preview]");
  clearTimeout(meta.timer);
  meta.timer = setTimeout(async () => {
    const result = readProfilePayload(form);
    const seq = ++meta.seq;
    if (result.error || !state.token || !state.userId) {
      output.textContent = "";
      return;
    }
    try {
      const preview = await profileApi("/preview", { method: "POST", body: result.payload });
      if (seq === meta.seq) output.textContent = formatGoalPreview(result.payload, preview);
    } catch {
      if (seq === meta.seq) output.textContent = "";
    }
  }, 250);
}

bindGoalDelta(el.profileForm);
bindGoalDelta(el.onboardingForm);

// --- wymuszone uzupełnienie profilu (D8) ------------------------------------------------------------------

export function openOnboarding() {
  if (el.onboardingDialog.open) return;
  el.onboardingForm.reset();
  el.onboardingError.textContent = "";
  el.onboardingTitle.textContent = state.userName ? t("Uzupełnij profil: {name}", { name: state.userName }) : t("Uzupełnij profil");
  updateGoalDeltaUi(el.onboardingForm);
  el.onboardingDialog.showModal();
  el.onboardingForm.querySelector("select, input")?.focus();
}

// Okna nie da się zamknąć klawiszem Esc – profil jest wymagany.
el.onboardingDialog.addEventListener("cancel", (event) => event.preventDefault());
["input", "change"].forEach((type) => el.onboardingForm.addEventListener(type, () => (el.onboardingError.textContent = "")));

el.onboardingForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const result = readProfilePayload(el.onboardingForm);
  if (result.error) {
    el.onboardingError.textContent = result.error;
    return;
  }
  try {
    await withBusy(el.onboardingSaveBtn, async () => {
      await profileApi("", { method: "PUT", body: result.payload });
      el.onboardingDialog.close();
      await enterApp();
      toast(t("Profil zapisany. Plan kaloryczny został wyliczony – możesz zaczynać."), "success");
    });
  } catch (error) {
    el.onboardingError.textContent = error.message;
  }
});

el.onboardingLogoutBtn.addEventListener("click", () => {
  el.onboardingDialog.close();
  lockUser();
  el.pinInput.focus();
});

