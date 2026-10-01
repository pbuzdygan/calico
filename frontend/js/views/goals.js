import { profileApi } from "../api.js";
import { GOAL_LABELS, MACROS } from "../config.js";
import { locale, N_, t } from "../i18n.js";
import { el, state } from "../state.js";
import { toast, toastError, withBusy } from "../ui.js";
import { escapeHtml, fmt, fmtSigned, formatDayLabel, plural, todayISO } from "../util.js";
import { paceText } from "../views/today.js";

// --- Cele -------------------------------------------------------------------------------------------

const PLAN_STATUS_LABELS = {
  no_data: N_("Za mało danych"),
  wait: N_("Obserwuj"),
  on_track: N_("Plan działa"),
  below_range: N_("Poza zakresem"),
  above_range: N_("Poza zakresem"),
};

function planStatusLabel(status) {
  return PLAN_STATUS_LABELS[status] ? t(PLAN_STATUS_LABELS[status]) : status;
}

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
  el.macroModeChip.textContent = manualCount ? t("Własne") : t("Automatycznie");
  el.macroTargetList.innerHTML = MACROS.map((macro) => {
    const manual = targets[`manual_${macro.key}`] !== null;
    return `<div class="kv"><span>${t(macro.label)}</span><strong>${fmt(targets[macro.key])} g<small class="kv-note">${manual ? t("własny") : t("auto")}</small></strong></div>`;
  }).join("");
  el.macroEditBtn.textContent = manualCount ? t("Zmień własne cele") : t("Ustaw własne cele");
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
      return { error: t("{label}: podaj liczbę od 0 do {max} g albo zostaw puste pole.", { label: t(macro.label), max: macro.max }) };
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
      toast(Object.keys(body).length ? t("Zapisano własne cele makro.") : t("Przywrócono automatyczne cele makro."), "success");
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
  el.goalTypeChip.textContent = GOAL_LABELS[plan.goal_type] ? t(GOAL_LABELS[plan.goal_type]) : "";
  el.goalTarget.innerHTML = `${fmt(plan.daily_kcal_target)}<small>${t("kcal/dzień")}</small>`;
  el.goalPace.textContent = paceText(plan.expected_rate_kg_per_week);
  el.goalPlanTdee.textContent = `${fmt(plan.plan_tdee_kcal)} kcal`;
  state.planStartedOn = plan.plan_started_on;
  el.goalPlanSince.textContent = `${formatDayLabel(plan.plan_started_on)} (${plan.plan_days} ${plural(plan.plan_days, "dzień", "dni", "dni")})`;
  el.goalStartWeight.textContent = `${fmt(plan.plan_weight_kg, 1)} kg`;
  el.goalTrendWeight.textContent = plan.trend_weight_kg !== null ? `${fmt(plan.trend_weight_kg, 1)} kg` : "–";
  el.goalWeightChange.textContent =
    plan.weight_change_since_plan_kg !== null ? `${fmtSigned(plan.weight_change_since_plan_kg, 1)} kg (${fmtSigned(plan.weight_change_since_plan_pct, 1)}%)` : "–";
  el.goalObservedRate.textContent = plan.observed_rate_kg_per_week !== null ? paceText(plan.observed_rate_kg_per_week)
      : `– (${plan.measurements_count} ${plural(plan.measurements_count, "pomiar", "pomiary", "pomiarów")})`;
  el.goalTargetWeight.textContent =
    plan.target_weight_kg !== null
      ? `${fmt(plan.target_weight_kg, 1)} kg${plan.target_weight_remaining_kg !== null ? ` (${fmtSigned(plan.target_weight_remaining_kg, 1)} kg)` : ""}`
      : "–";
  el.goalForecast.textContent = plan.forecast_message || "";

  el.planStatusBadge.textContent = planStatusLabel(plan.status);
  el.planStatusBadge.className = `chip status-${plan.status}`;
  el.planMessage.textContent =
    plan.reevaluation_due && plan.status !== "on_track"
      ? `${plan.message} ${t("Minął czas na ocenę planu ({days} dni lub zmiana masy ≥ 3%).", { days: plan.plan_days })}`
      : plan.message;
  const kcal = (value) => (value === null || value === undefined ? "–" : `${fmt(value)} kcal`);
  const stats = [
    [
      t("Oczekiwane tempo"),
      plan.expected_rate_low_kg_per_week !== null
        ? t("{low} … {high} kg/tydz.", { low: fmtSigned(plan.expected_rate_low_kg_per_week, 2), high: fmtSigned(plan.expected_rate_high_kg_per_week, 2) })
        : "–",
    ],
    [t("TDEE szacowane teraz"), kcal(plan.estimated_tdee_kcal)],
    [
      t("TDEE z obserwacji"),
      plan.observed_tdee_kcal !== null
        ? kcal(plan.observed_tdee_kcal)
        : plan.intake_coverage_pct !== null
          ? t("– (jedzenie: {coverage}% dni)", { coverage: fmt(plan.intake_coverage_pct) })
          : "–",
    ],
  ];
  el.planMetrics.innerHTML = stats.map(([label, value]) => `<div class="stat"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`).join("");
  el.planNotes.innerHTML = plan.notes.map((note) => `<li>${escapeHtml(note)}</li>`).join("");
  state.planSuggestion = plan.suggested_target_kcal;
  el.planApplyBtn.hidden = plan.suggested_target_kcal === null;
  if (plan.suggested_target_kcal !== null) el.planApplyBtn.textContent = t("Zastosuj sugestię: {kcal} kcal", { kcal: fmt(plan.suggested_target_kcal) });
}

// --- Cele: data startu planu (dane historyczne, np. po imporcie) ------------------------------------------

el.planStartEditBtn.addEventListener("click", () => {
  el.planStartInput.value = state.planStartedOn || "";
  el.planStartInput.max = todayISO();
  el.planStartStatus.textContent = "";
  el.planStartForm.hidden = false;
  el.planStartEditBtn.hidden = true;
  el.planStartInput.focus();
});

el.planStartCancelBtn.addEventListener("click", () => {
  el.planStartForm.hidden = true;
  el.planStartEditBtn.hidden = false;
});

el.planStartForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const value = el.planStartInput.value;
  if (!value) {
    el.planStartStatus.textContent = t("Wybierz datę.");
    el.planStartStatus.className = "form-status error";
    return;
  }
  try {
    await withBusy(el.planStartSaveBtn, async () => {
      await profileApi("/plan-start", { method: "PUT", body: { plan_started_on: value } });
      renderPlan(await profileApi("/plan"));
      el.planStartForm.hidden = true;
      el.planStartEditBtn.hidden = false;
      toast(t("Start planu: {date}. Ocena planu przeliczona.", { date: formatDayLabel(value) }), "success");
    });
  } catch (error) {
    el.planStartStatus.textContent = error.message;
    el.planStartStatus.className = "form-status error";
  }
});

el.targetWeightForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const raw = el.targetWeightInput.value.trim().replace(",", ".");
  const value = raw ? Number(raw) : null;
  el.targetWeightStatus.textContent = "";
  if (value !== null && (!Number.isFinite(value) || value < 30 || value > 300)) {
    el.targetWeightStatus.textContent = t("Podaj wagę od 30 do 300 kg albo zostaw puste pole.");
    el.targetWeightStatus.className = "form-status error";
    return;
  }
  try {
    await withBusy(el.targetWeightSaveBtn, async () => {
      await profileApi("/target-weight", { method: "PUT", body: { target_weight_kg: value } });
      renderPlan(await profileApi("/plan"));
      toast(value === null ? t("Usunięto wagę docelową.") : t("Waga docelowa: {value} kg.", { value: fmt(value, 1) }), "success");
    });
  } catch (error) {
    el.targetWeightStatus.textContent = error.message;
    el.targetWeightStatus.className = "form-status error";
  }
});

// Ręczne przeliczenie: wynik musi być widoczny (godzina, podstawa, wniosek), inaczej wygląda, jakby nic się nie stało.
el.planRefreshBtn.addEventListener("click", () =>
  withBusy(el.planRefreshBtn, async () => {
    const plan = await profileApi("/plan");
    renderPlan(plan);
    const time = new Date().toLocaleTimeString(locale(), { hour: "2-digit", minute: "2-digit" });
    const label = planStatusLabel(plan.status);
    const conclusion = plan.suggested_target_kcal !== null ? t("sugestia: {kcal} kcal/dzień", { kcal: fmt(plan.suggested_target_kcal) }) : t("cel bez zmian");
    el.planCheckedAt.textContent = t("Przeliczono o {time}: {count} {measurements} wagi od {date} – {status}, {conclusion}.", {
      time,
      count: plan.measurements_count,
      measurements: plural(plan.measurements_count, "pomiar", "pomiary", "pomiarów"),
      date: formatDayLabel(plan.plan_started_on),
      status: label.toLowerCase(),
      conclusion,
    });
    el.planCard.classList.remove("refreshed");
    void el.planCard.offsetWidth; // restart animacji
    el.planCard.classList.add("refreshed");
    toast(t("Ocena planu przeliczona: {status} – {conclusion}.", { status: label, conclusion }), "success");
  }).catch(toastError)
);

el.planApplyBtn.addEventListener("click", async () => {
  const target = state.planSuggestion;
  if (target === null) return;
  if (!confirm(t("Ustawić nowy cel planu: {kcal} kcal/dzień? Obowiązuje od dziś.", { kcal: fmt(target) }))) return;
  try {
    await withBusy(el.planApplyBtn, async () => {
      renderPlan(await profileApi("/plan/apply", { method: "POST", body: { target_kcal: target } }));
      renderMacroTargets((await profileApi()).macro_targets);
      toast(t("Nowy cel planu: {kcal} kcal/dzień.", { kcal: fmt(target) }), "success");
    });
  } catch (error) {
    toastError(error);
  }
});

