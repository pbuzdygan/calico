import { ADHERENCE_TOLERANCE, RING_CIRCUMFERENCE } from "./config.js";
import { plural, t } from "./i18n.js";
import { el } from "./state.js";
import { addDaysISO, escapeHtml, fmt, formatDayLabel, formatShortDay, icon, parseISO, todayISO, weekdayShort } from "./util.js";

// --- wykresy (SVG) ---------------------------------------------------------------------------------

export function setRing(total, target) {
  const pct = target > 0 ? Math.min(total / target, 1) : 0;
  el.ringProgress.style.strokeDasharray = `${RING_CIRCUMFERENCE}`;
  el.ringProgress.classList.toggle("is-empty", total <= 0);
  requestAnimationFrame(() => {
    el.ringProgress.style.strokeDashoffset = `${RING_CIRCUMFERENCE * (1 - pct)}`;
  });
}

export function sparklineSvg(values, color) {
  if (values.length < 2) return "";
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const points = values.map((value, index) => `${((index / (values.length - 1)) * 100).toFixed(2)},${(28 - ((value - min) / span) * 24).toFixed(2)}`);
  const last = points[points.length - 1].split(",");
  return `<svg viewBox="0 0 100 32" preserveAspectRatio="none" aria-hidden="true">
    <polyline class="spark-line" points="${points.join(" ")}" stroke="${color}" />
    <circle cx="${last[0]}" cy="${last[1]}" r="2.6" fill="${color}" vector-effect="non-scaling-stroke" />
  </svg>`;
}

let chartSeq = 0;

export function chartWidth(container) {
  return Math.max(280, Math.round(container.clientWidth || 640));
}

export function lineChartSvg({ dates, series, trend = [], color, unit, decimals = 1, label, width = 640 }) {
  if (!series.length) return "";
  const id = `lc${(chartSeq += 1)}`;
  const height = 180;
  const pad = { left: 42, right: 12, top: 12, bottom: 26 };
  const index = new Map(dates.map((date, position) => [date, position]));
  const values = [...series, ...trend].map((point) => point.value);
  let min = Math.min(...values);
  let max = Math.max(...values);
  const margin = Math.max((max - min) * 0.15, 0.5);
  min -= margin;
  max += margin;
  const x = (date) => pad.left + ((index.get(date) ?? 0) / Math.max(1, dates.length - 1)) * (width - pad.left - pad.right);
  const y = (value) => pad.top + (1 - (value - min) / (max - min)) * (height - pad.top - pad.bottom);
  const path = (points) => points.map((point) => `${x(point.date).toFixed(1)},${y(point.value).toFixed(1)}`).join(" ");
  const ticks = [min + margin, (min + max) / 2, max - margin];
  const baseY = height - pad.bottom;
  const first = series[0];
  const last = series[series.length - 1];
  const area = series.length > 1 ? `M${x(first.date).toFixed(1)},${baseY} L${path(series).replaceAll(" ", " L")} L${x(last.date).toFixed(1)},${baseY} Z` : "";
  const summary = t("{label}: od {from} do {to} {unit}, {count} {measurements}.", {
    label,
    from: fmt(first.value, decimals),
    to: fmt(last.value, decimals),
    unit,
    count: series.length,
    measurements: plural(series.length, "pomiar", "pomiary", "pomiarów"),
  });
  return `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="${escapeHtml(summary)}">
    <defs><linearGradient id="${id}" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="${color}" stop-opacity="0.22" /><stop offset="100%" stop-color="${color}" stop-opacity="0" /></linearGradient></defs>
    ${ticks
      .map(
        (tick) => `<line class="chart-grid" x1="${pad.left}" x2="${width - pad.right}" y1="${y(tick).toFixed(1)}" y2="${y(tick).toFixed(1)}" />
      <text class="chart-axis" x="${pad.left - 8}" y="${(y(tick) + 4).toFixed(1)}" text-anchor="end">${escapeHtml(fmt(tick, decimals))}</text>`
      )
      .join("")}
    <text class="chart-axis" x="${pad.left}" y="${height - 6}">${escapeHtml(formatShortDay(dates[0]))}</text>
    <text class="chart-axis" x="${width - pad.right}" y="${height - 6}" text-anchor="end">${escapeHtml(formatShortDay(dates[dates.length - 1]))}</text>
    ${area ? `<path d="${area}" fill="url(#${id})" />` : ""}
    ${series.length > 1 ? `<polyline class="chart-line" points="${path(series)}" stroke="${color}" />` : ""}
    ${trend.length > 1 ? `<polyline class="chart-trend" points="${path(trend)}" stroke="#F4F8FC" />` : ""}
    ${series
      .map(
        (point) =>
          `<circle class="chart-dot" cx="${x(point.date).toFixed(1)}" cy="${y(point.value).toFixed(1)}" r="${series.length > 40 ? 2.5 : 4}" fill="${color}"><title>${escapeHtml(
            `${formatDayLabel(point.date)}: ${fmt(point.value, decimals)} ${unit}`
          )}</title></circle>`
      )
      .join("")}
  </svg>`;
}

export function barChartSvg(dates, byDate, width = 640) {
  const height = 180;
  const pad = { left: 6, right: 6, top: 10, bottom: 24 };
  const food = dates.map((date) => byDate.get(date)).filter((point) => point?.has_food);
  if (!food.length) return "";
  const max = Math.max(1, ...food.map((point) => Math.max(point.total_kcal, point.target_kcal))) * 1.08;
  const slot = (width - pad.left - pad.right) / dates.length;
  const barWidth = Math.max(1, slot * 0.64);
  const plotHeight = height - pad.top - pad.bottom;
  const maxLabels = Math.max(2, Math.floor(width / 64));
  const labelEvery = Math.max(1, Math.ceil(dates.length / maxLabels));
  const parts = dates.map((date, position) => {
    const point = byDate.get(date);
    const x = pad.left + position * slot;
    const label = position % labelEvery === 0 ? `<text class="chart-axis" x="${(x + slot / 2).toFixed(1)}" y="${height - 6}" text-anchor="middle">${escapeHtml(formatShortDay(date))}</text>` : "";
    const hit = `<rect class="chart-hit" data-date="${date}" x="${x.toFixed(1)}" y="${pad.top}" width="${slot.toFixed(1)}" height="${plotHeight}"><title>${escapeHtml(
      point?.has_food ? `${formatDayLabel(date)}: ${fmt(point.total_kcal)} / ${fmt(point.target_kcal)} kcal` : `${formatDayLabel(date)}: ${t("brak wpisów jedzenia")}`
    )}</title></rect>`;
    if (!point?.has_food) return label + hit;
    const barHeight = Math.max(2, (point.total_kcal / max) * plotHeight);
    const targetY = pad.top + plotHeight - (point.target_kcal / max) * plotHeight;
    const over = point.total_kcal > point.target_kcal * (1 + ADHERENCE_TOLERANCE);
    return `<rect class="chart-bar${over ? " over" : ""}" x="${(x + (slot - barWidth) / 2).toFixed(1)}" y="${(pad.top + plotHeight - barHeight).toFixed(1)}" width="${barWidth.toFixed(1)}" height="${barHeight.toFixed(1)}" rx="${Math.min(4, barWidth / 2).toFixed(1)}" />
      <line class="chart-target" x1="${x.toFixed(1)}" x2="${(x + slot).toFixed(1)}" y1="${targetY.toFixed(1)}" y2="${targetY.toFixed(1)}" />${label}${hit}`;
  });
  return `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="${escapeHtml(t("Kalorie dziennie na tle celu ({count} {days} z jedzeniem).", { count: food.length, days: plural(food.length, "dzień", "dni", "dni") }))}">
    <defs><linearGradient id="barGradient" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#20D5FF" /><stop offset="100%" stop-color="#1AA8FF" stop-opacity="0.55" /></linearGradient></defs>
    <line class="chart-grid" x1="${pad.left}" x2="${width - pad.right}" y1="${height - pad.bottom}" y2="${height - pad.bottom}" />
    ${parts.join("")}
  </svg>`;
}

export function emptyChart(title, text) {
  return `<div class="chart-empty"><strong>${escapeHtml(title)}</strong><span>${escapeHtml(text)}</span></div>`;
}

export function dayStatus(point) {
  if (!point?.has_food) return "none";
  const target = point.target_kcal || 0;
  if (target > 0 && Math.abs(point.total_kcal - target) <= target * ADHERENCE_TOLERANCE) return "done";
  return "logged";
}

export function dayDotsHtml(dates, byDate, { labels = false } = {}) {
  const today = todayISO();
  const statusText = { done: t("w celu"), logged: t("wpisy poza zakresem celu"), none: t("brak wpisów jedzenia") };
  return dates
    .map((date) => {
      const status = dayStatus(byDate.get(date));
      const title = `${formatDayLabel(date)}: ${statusText[status]}`;
      return `<span class="dot ${status}${date === today ? " today" : ""}" title="${escapeHtml(title)}">
        <span class="dot-mark">${status === "done" ? icon("check") : ""}<span class="visually-hidden">${escapeHtml(title)}</span></span>
        ${labels ? `<span aria-hidden="true">${escapeHtml(weekdayShort(date))}</span>` : ""}
      </span>`;
    })
    .join("");
}

export function measurementSeries(points, field) {
  return points.filter((point) => point[field] !== null && point[field] !== undefined).map((point) => ({ date: point.log_date, value: point[field] }));
}

// Zmiana względem pomiaru sprzed ≥7 dni (albo najstarszego w zakresie).
export function measurementDelta(series) {
  if (series.length < 2) return null;
  const last = series[series.length - 1];
  const weekAgo = addDaysISO(last.date, -7);
  const reference = [...series].reverse().find((point) => point.date <= weekAgo) || series[0];
  const days = Math.round((parseISO(last.date) - parseISO(reference.date)) / 86400000);
  return { diff: last.value - reference.value, label: days >= 6 && days <= 8 ? t("w tym tygodniu") : t("od {date}", { date: formatShortDay(reference.date) }) };
}

export function renderDelta(target, delta, { unit, goodWhen }) {
  if (!delta) {
    target.textContent = "";
    target.className = "delta";
    return;
  }
  const arrow = delta.diff < -0.05 ? "↓" : delta.diff > 0.05 ? "↑" : "→";
  const direction = delta.diff < -0.05 ? "down" : delta.diff > 0.05 ? "up" : "flat";
  target.textContent = `${arrow} ${fmt(Math.abs(delta.diff), 1)} ${unit} ${delta.label}`;
  target.className = `delta${direction === goodWhen ? " good" : ""}`;
}

