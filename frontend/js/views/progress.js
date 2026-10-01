import { api } from "../api.js";
import { barChartSvg, chartWidth, dayDotsHtml, dayStatus, emptyChart, lineChartSvg, measurementSeries } from "../charts.js";
import { ADHERENCE_TOLERANCE } from "../config.js";
import { t } from "../i18n.js";
import { goToLogDay } from "../nav.js";
import { el, state } from "../state.js";
import { closeSheet, openSheet, toastError, withBusy } from "../ui.js";
import { addDaysISO, daysBetween, escapeHtml, fmt, fmtSigned, formatDayLabel, plural, todayISO, weekdayShort } from "../util.js";

// --- Postępy -------------------------------------------------------------------------------------------

function progressRange(query) {
  const today = todayISO();
  if (query.kind === "days") return { from: addDaysISO(today, -(query.days - 1)), to: today };
  if (query.kind === "all") return { from: addDaysISO(today, -3659), to: today };
  return { from: query.from, to: query.to };
}

export async function loadProgress(query = state.progressQuery) {
  state.progressQuery = query;
  state.historyExpanded = false;
  document.querySelectorAll(".range-chips .seg").forEach((button) => {
    const range = button.dataset.range;
    const active = (query.kind === "days" && range === String(query.days)) || (query.kind === "all" && range === "all") || (query.kind === "custom" && range === "custom");
    button.classList.toggle("active", active);
  });
  const { from, to } = progressRange(query);
  const [report, week] = await Promise.all([
    query.kind === "days" ? api("/reports/summary", { params: { days: query.days } }) : api("/reports/range", { params: { date_from: from, date_to: to } }),
    api("/reports/summary", { params: { days: 7 } }),
  ]);
  renderProgress(report, week);
}

const HISTORY_PREVIEW_ROWS = 14;

function renderProgress(report, week) {
  state.lastProgress = { report, week };
  let dates = daysBetween(report.date_from, report.date_to);
  if (state.progressQuery.kind === "all" && report.points.length) {
    dates = daysBetween(report.points[0].log_date, report.date_to);
  }
  el.progressRangeLabel.textContent = `${formatDayLabel(dates[0])} – ${formatDayLabel(report.date_to)}`;

  const weight = measurementSeries(report.points, "weight_kg");
  const trend = report.points.filter((point) => point.weight_trend_kg !== null).map((point) => ({ date: point.log_date, value: point.weight_trend_kg }));
  renderProgressMeasurement(weight, { value: el.pWeightValue, delta: el.pWeightDelta, chart: el.pWeightChart, unit: "kg", color: "#1AA8FF", label: t("Waga"), trend, empty: t("Brak pomiarów wagi"), emptyHint: t("Dodaj wagę w zakładce Dziś, aby śledzić postęp.") });
  const waist = measurementSeries(report.points, "waist_cm");
  renderProgressMeasurement(waist, { value: el.pWaistValue, delta: el.pWaistDelta, chart: el.pWaistChart, unit: "cm", color: "#32E6C4", label: t("Obwód pasa"),
    trend: [],
    empty: t("Brak pomiarów obwodu pasa"),
    emptyHint: t("Dodaj obwód pasa w zakładce Dziś, aby śledzić postęp."),
  });

  const byDate = new Map(report.points.map((point) => [point.log_date, point]));
  const foodDays = report.points.filter((point) => point.has_food);
  const inTarget = foodDays.filter((point) => dayStatus(point) === "done").length;
  el.pAvgKcal.textContent = report.days_with_food ? `${fmt(report.average_kcal)} kcal` : "–";
  el.pAvgTarget.textContent = report.days_with_food ? `${fmt(report.average_target_kcal)} kcal` : "–";
  el.pAdherence.textContent = report.days_with_food ? `${Math.round((inTarget / report.days_with_food) * 100)}%` : "–";
  el.pKcalChart.innerHTML = barChartSvg(dates, byDate, chartWidth(el.pKcalChart)) || emptyChart(t("Brak wpisów jedzenia"), t("Dodaj posiłki, aby zobaczyć kalorie na tle celu."));
  el.pKcalNote.textContent = report.days_with_food
    ? t("{inTarget} z {days} dni z jedzeniem w celu (±{tolerance}%). Bilans względem celu: {balance} kcal. Najwyższy dzień: {highest} kcal ({date}).", {
        inTarget,
        days: report.days_with_food,
        tolerance: ADHERENCE_TOLERANCE * 100,
        balance: fmtSigned(report.balance_vs_target_kcal),
        highest: fmt(report.highest_kcal),
        date: formatDayLabel(report.highest_kcal_day),
      })
    : "";

  const weekByDate = new Map(week.points.map((point) => [point.log_date, point]));
  const weekDates = daysBetween(addDaysISO(todayISO(), -6), todayISO());
  el.pWeekDots.innerHTML = dayDotsHtml(weekDates, weekByDate, { labels: true });
  const weekDone = weekDates.filter((date) => dayStatus(weekByDate.get(date)) === "done").length;
  const weekLogged = weekDates.filter((date) => dayStatus(weekByDate.get(date)) !== "none").length;
  el.pWeekSub.textContent = t("{done} / 7 dni w celu · wpisy jedzenia w {logged} z 7 dni. Jeden słabszy dzień nie przekreśla tygodnia – liczy się regularność.", {
    done: weekDone,
    logged: weekLogged,
  });

  const rows = [...report.points].reverse();
  const visible = state.historyExpanded ? rows : rows.slice(0, HISTORY_PREVIEW_ROWS);
  const moreButton =
    rows.length > visible.length
      ? `<button class="btn btn-quiet btn-block" type="button" data-history-more>${t("Pokaż wszystkie ({count} {days})", { count: rows.length, days: plural(rows.length, "dzień", "dni", "dni") })}</button>`
      : "";
  el.pHistory.innerHTML = rows.length
    ? visible
        .map((point) => {
          const parts = [];
          if (point.has_food) {
            parts.push(t("B {protein} g · W {carbs} g · T {fat} g", { protein: fmt(point.total_protein_g), carbs: fmt(point.total_carbs_g), fat: fmt(point.total_fat_g) }));
          }
          if (point.weight_kg !== null) parts.push(t("waga {value} kg", { value: fmt(point.weight_kg, 1) }));
          if (point.waist_cm !== null) parts.push(t("pas {value} cm", { value: fmt(point.waist_cm, 1) }));
          const over = point.has_food && point.total_kcal > point.target_kcal * (1 + ADHERENCE_TOLERANCE);
          return `<button class="history-row" type="button" data-date="${point.log_date}">
            <span class="history-day">${escapeHtml(formatDayLabel(point.log_date))}<small>${escapeHtml(weekdayShort(point.log_date))}</small></span>
            <span class="history-kcal${over ? " over" : ""}">${point.has_food ? `${fmt(point.total_kcal)} / ${fmt(point.target_kcal)} kcal` : "–"}</span>
            <span class="history-meta">${escapeHtml(parts.join(" · "))}</span>
          </button>`;
        })
        .join("") + moreButton
    : emptyChart(t("Brak wpisów w zakresie"), t("Zmień zakres albo dodaj pierwsze wpisy."));
}

export function rerenderProgressCharts() {
  if (state.view === "progress" && state.lastProgress && !el.app.hidden) renderProgress(state.lastProgress.report, state.lastProgress.week);
}

let resizeTimer = null;
window.addEventListener("resize", () => {
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(rerenderProgressCharts, 200);
});

function renderProgressMeasurement(series, config) {
  if (!series.length) {
    config.value.textContent = "–";
    config.delta.textContent = "";
    config.chart.innerHTML = emptyChart(config.empty, config.emptyHint);
    return;
  }
  const first = series[0];
  const last = series[series.length - 1];
  config.value.innerHTML = `${fmt(last.value, 1)}<small>${config.unit}</small>`;
  const diff = last.value - first.value;
  config.delta.textContent = series.length > 1 ? t("{diff} {unit} w zakresie", { diff: fmtSigned(diff, 1), unit: config.unit }) : t("jeden pomiar");
  config.delta.className = "delta";
  const dates = daysBetween(state.progressQuery.kind === "all" ? first.date : progressRange(state.progressQuery).from, progressRange(state.progressQuery).to);
  config.chart.innerHTML = lineChartSvg({ dates, series, trend: config.trend, color: config.color, unit: config.unit, label: config.label, width: chartWidth(config.chart) });
}

document.querySelectorAll(".range-chips .seg").forEach((button) => {
  button.addEventListener("click", () => {
    const range = button.dataset.range;
    if (range === "custom") {
      const { from, to } = progressRange(state.progressQuery);
      el.rangeFrom.value = from;
      el.rangeTo.value = to;
      el.rangeTo.max = todayISO();
      openSheet(el.rangeSheet);
      return;
    }
    const query = range === "all" ? { kind: "all" } : { kind: "days", days: Number(range) };
    withBusy(button, () => loadProgress(query)).catch(toastError);
  });
});

el.rangeSheetForm.addEventListener("submit", (event) => {
  event.preventDefault();
  if (!el.rangeFrom.value || !el.rangeTo.value) return;
  const [from, to] = [el.rangeFrom.value, el.rangeTo.value].sort();
  closeSheet(el.rangeSheet);
  loadProgress({ kind: "custom", from, to }).catch(toastError);
});

[el.pKcalChart, el.pHistory].forEach((container) =>
  container.addEventListener("click", (event) => {
    if (event.target.closest("[data-history-more]")) {
      state.historyExpanded = true;
      rerenderProgressCharts();
      return;
    }
    const target = event.target.closest("[data-date]");
    if (target) goToLogDay(target.dataset.date);
  })
);

