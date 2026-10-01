import { api, profileApi } from "../api.js";
import { dayDotsHtml, dayStatus, measurementDelta, measurementSeries, renderDelta, setRing, sparklineSvg } from "../charts.js";
import { ADHERENCE_TOLERANCE, GOAL_LABELS, MACROS } from "../config.js";
import { t } from "../i18n.js";
import { el, state } from "../state.js";
import { addDaysISO, daysBetween, escapeHtml, fmt, fmtSigned, formatDayLabel, formatLongDay, todayISO } from "../util.js";

// --- Dziś -----------------------------------------------------------------------------------------

export async function loadToday() {
  const today = todayISO();
  // Pomiary z całego roku: karta wagi/obwodu ma pokazywać zmianę także przy rzadkich lub zaimportowanych pomiarach.
  const [detail, month, year, plan] = await Promise.all([
    api(`/days/${today}`),
    api("/reports/summary", { params: { days: 30 } }),
    api("/reports/summary", { params: { days: 365 } }),
    profileApi("/plan"),
  ]);
  state.goalType = plan.goal_type;
  el.todayDate.textContent = formatLongDay(today).replace(/^./, (letter) => letter.toUpperCase());
  renderHero(detail);
  renderMeasurementCards(year, plan.goal_type);
  renderAdherenceCard(month);
  renderTargetCard(plan);
  renderRecommendation(plan);
}

function renderHero(detail) {
  const total = Number(detail.total_kcal) || 0;
  const target = Number(detail.target_kcal) || 0;
  setRing(total, target);
  el.calorieRing.setAttribute("aria-label", t("Spożyto {total} z {target} kcal", { total: fmt(total), target: fmt(target) }));
  el.ringConsumed.textContent = fmt(total);
  el.ringTarget.textContent = `/ ${fmt(target)} kcal`;
  const remaining = target - total;
  el.ringStatus.classList.toggle("over", remaining < 0);
  el.ringStatus.innerHTML =
    remaining >= 0
      ? t("Pozostało <strong>{kcal} kcal</strong>", { kcal: fmt(remaining) })
      : t("<strong>{kcal} kcal</strong> ponad cel", { kcal: fmt(-remaining) });

  // Postęp względem celu makro (g) dnia; przekroczenie celu na bursztynowo.
  el.macroList.innerHTML = MACROS.map((macro) => {
    const grams = Number(detail[macro.field]) || 0;
    const goal = Number(detail[macro.targetField]) || 0;
    const pct = goal > 0 ? Math.round((grams / goal) * 100) : 0;
    const over = goal > 0 && grams > goal;
    const note = goal > 0 ? (over ? `+${fmt(grams - goal)} g` : `${pct}%`) : "";
    return `<div class="macro${over ? " over" : ""}">
      <span class="macro-name">${t(macro.label)}</span>
      <span class="macro-value">${fmt(grams)}<small> / ${goal > 0 ? fmt(goal) : "–"} g</small>${note ? `<small class="macro-note">${note}</small>` : ""}</span>
      <span class="bar ${macro.cls}" role="img" aria-label="${escapeHtml(t(over ? "{label}: {grams} z {goal} g, ponad cel" : "{label}: {grams} z {goal} g", { label: t(macro.label), grams: fmt(grams), goal: fmt(goal) }))}"><span style="width:${Math.min(pct, 100)}%"></span></span>
    </div>`;
  }).join("");
  el.balanceNote.hidden = !detail.balance_mode;
}

function renderMeasurementCards(report, goalType) {
  const configs = [
    { field: "weight_kg", value: el.weightValue, delta: el.weightDelta, spark: el.weightSpark, unit: "kg", color: "#1AA8FF", good: goalType === "bulk" ? "up" : goalType === "cut" ? "down" : "flat" },
    { field: "waist_cm", value: el.waistValue, delta: el.waistDelta, spark: el.waistSpark, unit: "cm", color: "#32E6C4", good: goalType === "bulk" ? "flat" : "down" },
  ];
  configs.forEach((config) => {
    const series = measurementSeries(report.points, config.field);
    if (!series.length) {
      config.value.textContent = "–";
      renderDelta(config.delta, null, config);
      config.spark.innerHTML = `<span class="spark-empty">${t("Dodaj pierwszy pomiar")}</span>`;
      return;
    }
    const last = series[series.length - 1];
    config.value.innerHTML = `${fmt(last.value, 1)}<small>${config.unit}</small>`;
    renderDelta(config.delta, measurementDelta(series), { unit: config.unit, goodWhen: config.good });
    config.spark.innerHTML = sparklineSvg(series.slice(-14).map((point) => point.value), config.color) || `<span class="spark-empty">${formatDayLabel(last.date)}</span>`;
  });
}

function renderAdherenceCard(report) {
  const byDate = new Map(report.points.map((point) => [point.log_date, point]));
  const dates = daysBetween(addDaysISO(todayISO(), -6), todayISO());
  const statuses = dates.map((date) => dayStatus(byDate.get(date)));
  const done = statuses.filter((status) => status === "done").length;
  const logged = statuses.filter((status) => status !== "none").length;
  el.adherenceValue.innerHTML = `${done} / 7<small>${t("dni w celu")}</small>`;
  el.adherenceDots.innerHTML = dayDotsHtml(dates, byDate);
  el.adherenceSub.textContent = t("Wpisy jedzenia: {logged} z 7 dni · „w celu” = ±{tolerance}% celu kcal", { logged, tolerance: ADHERENCE_TOLERANCE * 100 });
}

export function paceText(rate) {
  if (rate === null || rate === undefined) return "–";
  if (Math.abs(rate) < 0.05) return t("≈ 0 kg/tydz.");
  return t("{rate} kg/tydz.", { rate: fmtSigned(rate, 2) });
}

function renderTargetCard(plan) {
  el.targetValue.innerHTML = `${fmt(plan.daily_kcal_target)}<small>${t("kcal/dzień")}</small>`;
  el.targetGoal.textContent = GOAL_LABELS[plan.goal_type] ? t(GOAL_LABELS[plan.goal_type]) : "–";
  el.targetPace.textContent = paceText(plan.expected_rate_kg_per_week);
}

function renderRecommendation(plan) {
  const suggestion = plan.suggested_target_kcal;
  el.recommendationCard.hidden = suggestion === null || suggestion === undefined;
  if (!el.recommendationCard.hidden) {
    el.recommendationText.textContent = t("Trend masy z ostatnich tygodni sugeruje zmianę celu na {kcal} kcal ({delta} kcal). Decyzja należy do Ciebie.", {
      kcal: fmt(suggestion),
      delta: fmtSigned(suggestion - plan.daily_kcal_target),
    });
  }
}

