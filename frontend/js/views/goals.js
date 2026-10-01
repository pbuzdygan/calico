import { profileApi } from "../api.js";
import { GOAL_LABELS, MACROS } from "../config.js";
import { el, state } from "../state.js";
import { toast, toastError, withBusy } from "../ui.js";
import { escapeHtml, fmt, fmtSigned, formatDayLabel } from "../util.js";
import { paceText } from "../views/today.js";

// --- Cele -------------------------------------------------------------------------------------------

const PLAN_STATUS_LABELS = {
  no_data: "Za mało danych",
  wait: "Obserwuj",
  on_track: "Plan działa",
  below_range: "Poza zakresem",
  above_range: "Poza zakresem",
};

export async function loadGoals() {
  const [plan, profile] = await Promise.all([profileApi("/plan"), profileApi()]);
  renderPlan(plan);
  renderMacroTargets(profile.macro_targets);
  el.targetWeightInput.value = profile.target_weight_kg !== null ? String(profile.target_weight_kg) : "";
}

// --- Cele: makro (T2.3) - domyślnie z celu kcal, własne wartości opcjonalne ---------------------------

function renderMacroTargets(targets) {
  if (!targets) return;
  state.macroTargets = targets;
  const manualCount = MACROS.filter((macro) => targets[`manual_${macro.key}`] !== null).length;
  el.macroModeChip.textContent = manualCount ? "Własne" : "Automatycznie";
  el.macroTargetList.innerHTML = MACROS.map((macro) => {
    const manual = targets[`manual_${macro.key}`] !== null;
    return `<div class="kv"><span>${macro.label}</span><strong>${fmt(targets[macro.key])} g<small class="kv-note">${manual ? "własny" : "auto"}</small></strong></div>`;
  }).join("");
  el.macroEditBtn.textContent = manualCount ? "Zmień własne cele" : "Ustaw własne cele";
  el.macroAutoBtn.hidden = !manualCount;
  MACROS.forEach((macro) => {
    const input = el[`macro_${macro.key}`];
    const manual = targets[`manual_${macro.key}`];
    input.value = manual !== null ? String(manual) : "";
    input.placeholder = fmt(targets[macro.key]);
  });
}

function readMacroForm() {
  const body = {};
  for (const macro of MACROS) {
    const raw = el[`macro_${macro.key}`].value.trim().replace(",", ".");
    if (!raw) continue;
    const value = Number(raw);
    if (!Number.isFinite(value) || value < 0 || value > macro.max) {
      return { error: `${macro.label}: podaj liczbę od 0 do ${macro.max} g albo zostaw puste pole.` };
    }
    body[macro.key] = value;
  }
  return { body };
}

async function saveMacroTargets(button, body) {
  el.macroFormStatus.textContent = "";
  try {
    await withBusy(button, async () => {
      const profile = await profileApi("/macros", { method: "PUT", body });
      renderMacroTargets(profile.macro_targets);
      el.macroForm.hidden = true;
      el.macroEditBtn.hidden = false;
      toast(Object.keys(body).length ? "Zapisano własne cele makro." : "Przywrócono automatyczne cele makro.", "success");
    });
  } catch (error) {
    el.macroFormStatus.textContent = error.message;
    el.macroFormStatus.className = "form-status error";
  }
}

el.macroEditBtn.addEventListener("click", () => {
  el.macroForm.hidden = false;
  el.macroEditBtn.hidden = true;
  el.macroFormStatus.textContent = "";
  el.macro_protein_g.focus();
});

el.macroCancelBtn.addEventListener("click", () => {
  renderMacroTargets(state.macroTargets);
  el.macroForm.hidden = true;
  el.macroEditBtn.hidden = false;
});

el.macroForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const result = readMacroForm();
  if (result.error) {
    el.macroFormStatus.textContent = result.error;
    el.macroFormStatus.className = "form-status error";
    return;
  }
  saveMacroTargets(el.macroSaveBtn, result.body);
});

el.macroAutoBtn.addEventListener("click", () => saveMacroTargets(el.macroAutoBtn, {}));

function renderPlan(plan) {
  state.goalType = plan.goal_type;
  el.goalTypeChip.textContent = GOAL_LABELS[plan.goal_type] || "";
  el.goalTarget.innerHTML = `${fmt(plan.daily_kcal_target)}<small>kcal/dzień</small>`;
  el.goalPace.textContent = paceText(plan.expected_rate_kg_per_week);
  el.goalPlanTdee.textContent = `${fmt(plan.plan_tdee_kcal)} kcal`;
  el.goalPlanSince.textContent = `${formatDayLabel(plan.plan_started_on)} (${plan.plan_days} dni)`;
  el.goalStartWeight.textContent = `${fmt(plan.plan_weight_kg, 1)} kg`;
  el.goalTrendWeight.textContent = plan.trend_weight_kg !== null ? `${fmt(plan.trend_weight_kg, 1)} kg` : "–";
  el.goalWeightChange.textContent =
    plan.weight_change_since_plan_kg !== null ? `${fmtSigned(plan.weight_change_since_plan_kg, 1)} kg (${fmtSigned(plan.weight_change_since_plan_pct, 1)}%)` : "–";
  el.goalObservedRate.textContent = plan.observed_rate_kg_per_week !== null ? paceText(plan.observed_rate_kg_per_week) : `– (${plan.measurements_count} pomiarów)`;
  el.goalTargetWeight.textContent =
    plan.target_weight_kg !== null
      ? `${fmt(plan.target_weight_kg, 1)} kg${plan.target_weight_remaining_kg !== null ? ` (${fmtSigned(plan.target_weight_remaining_kg, 1)} kg)` : ""}`
      : "–";
  el.goalForecast.textContent = plan.forecast_message || "";

  el.planStatusBadge.textContent = PLAN_STATUS_LABELS[plan.status] || plan.status;
  el.planStatusBadge.className = `chip status-${plan.status}`;
  el.planMessage.textContent =
    plan.reevaluation_due && plan.status !== "on_track" ? `${plan.message} Minął czas na ocenę planu (${plan.plan_days} dni lub zmiana masy ≥ 3%).` : plan.message;
  const kcal = (value) => (value === null || value === undefined ? "–" : `${fmt(value)} kcal`);
  const stats = [
    ["Oczekiwane tempo", plan.expected_rate_low_kg_per_week !== null ? `${fmtSigned(plan.expected_rate_low_kg_per_week, 2)} … ${fmtSigned(plan.expected_rate_high_kg_per_week, 2)} kg/tydz.` : "–"],
    ["TDEE szacowane teraz", kcal(plan.estimated_tdee_kcal)],
    ["TDEE z obserwacji", plan.observed_tdee_kcal !== null ? kcal(plan.observed_tdee_kcal) : plan.intake_coverage_pct !== null ? `– (jedzenie: ${fmt(plan.intake_coverage_pct)}% dni)` : "–"],
  ];
  el.planMetrics.innerHTML = stats.map(([label, value]) => `<div class="stat"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`).join("");
  el.planNotes.innerHTML = plan.notes.map((note) => `<li>${escapeHtml(note)}</li>`).join("");
  state.planSuggestion = plan.suggested_target_kcal;
  el.planApplyBtn.hidden = plan.suggested_target_kcal === null;
  if (plan.suggested_target_kcal !== null) el.planApplyBtn.textContent = `Zastosuj sugestię: ${fmt(plan.suggested_target_kcal)} kcal`;
}

el.targetWeightForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const raw = el.targetWeightInput.value.trim().replace(",", ".");
  const value = raw ? Number(raw) : null;
  el.targetWeightStatus.textContent = "";
  if (value !== null && (!Number.isFinite(value) || value < 30 || value > 300)) {
    el.targetWeightStatus.textContent = "Podaj wagę od 30 do 300 kg albo zostaw puste pole.";
    el.targetWeightStatus.className = "form-status error";
    return;
  }
  try {
    await withBusy(el.targetWeightSaveBtn, async () => {
      await profileApi("/target-weight", { method: "PUT", body: { target_weight_kg: value } });
      renderPlan(await profileApi("/plan"));
      toast(value === null ? "Usunięto wagę docelową." : `Waga docelowa: ${fmt(value, 1)} kg.`, "success");
    });
  } catch (error) {
    el.targetWeightStatus.textContent = error.message;
    el.targetWeightStatus.className = "form-status error";
  }
});

el.planRefreshBtn.addEventListener("click", () => withBusy(el.planRefreshBtn, loadGoals).catch(toastError));

el.planApplyBtn.addEventListener("click", async () => {
  const target = state.planSuggestion;
  if (target === null) return;
  if (!confirm(`Ustawić nowy cel planu: ${fmt(target)} kcal/dzień? Obowiązuje od dziś.`)) return;
  try {
    await withBusy(el.planApplyBtn, async () => {
      renderPlan(await profileApi("/plan/apply", { method: "POST", body: { target_kcal: target } }));
      renderMacroTargets((await profileApi()).macro_targets);
      toast(`Nowy cel planu: ${fmt(target)} kcal/dzień.`, "success");
    });
  } catch (error) {
    toastError(error);
  }
});

