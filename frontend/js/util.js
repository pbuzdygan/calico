// --- narzędzia -----------------------------------------------------------------------------------

function localISO(date) {
  const pad = (value) => String(value).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

export function todayISO() {
  return localISO(new Date());
}

export function monthStartISO(isoDate) {
  return `${isoDate.slice(0, 7)}-01`;
}

export function addMonthsISO(monthStart, months) {
  const date = parseISO(monthStart);
  date.setMonth(date.getMonth() + months, 1);
  return localISO(date);
}

export function monthEndISO(monthStart) {
  return addDaysISO(addMonthsISO(monthStart, 1), -1);
}

export function parseISO(isoDate) {
  const [year, month, day] = isoDate.split("-").map(Number);
  return new Date(year, month - 1, day);
}

export function addDaysISO(isoDate, days) {
  const date = parseISO(isoDate);
  date.setDate(date.getDate() + days);
  return localISO(date);
}

export function daysBetween(fromISO, toISO) {
  const result = [];
  for (let current = fromISO; current <= toISO; current = addDaysISO(current, 1)) result.push(current);
  return result;
}

export function formatDayLabel(isoDate) {
  if (!isoDate) return "–";
  const [year, month, day] = isoDate.split("-");
  return `${day}.${month}.${year}`;
}

export function formatShortDay(isoDate) {
  const [, month, day] = isoDate.split("-");
  return `${day}.${month}`;
}

export function formatLongDay(isoDate) {
  return parseISO(isoDate).toLocaleDateString("pl-PL", { weekday: "long", day: "numeric", month: "long" });
}

export function weekdayShort(isoDate) {
  return parseISO(isoDate).toLocaleDateString("pl-PL", { weekday: "short" }).replace(".", "");
}

const numberFormats = new Map();
export function fmt(value, decimals = 0) {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) return "–";
  if (!numberFormats.has(decimals)) {
    numberFormats.set(decimals, new Intl.NumberFormat("pl-PL", { maximumFractionDigits: decimals, useGrouping: "always" }));
  }
  return numberFormats.get(decimals).format(Number(value));
}

export function fmtSigned(value, decimals = 0) {
  if (value === null || value === undefined) return "–";
  if (Math.abs(value) < 0.5 * 10 ** -decimals) return fmt(0, decimals);
  return `${value > 0 ? "+" : "−"}${fmt(Math.abs(value), decimals)}`;
}

export function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

export function parseNumberInput(raw) {
  const text = String(raw ?? "").trim().replace(",", ".");
  if (!text) return null;
  const value = Number(text);
  return Number.isFinite(value) ? value : NaN;
}

export function defaultMealType() {
  const hour = new Date().getHours();
  if (hour < 11) return "breakfast";
  if (hour < 16) return "lunch";
  if (hour < 21) return "dinner";
  return "snack";
}

export function plural(count, one, few, many) {
  const mod10 = count % 10;
  const mod100 = count % 100;
  if (count === 1) return one;
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return few;
  return many;
}

export function icon(name, cls = "icon") {
  return `<svg class="${cls}" aria-hidden="true"><use href="#i-${name}" /></svg>`;
}

