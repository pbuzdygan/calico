import { lang, locale } from "./i18n.js";

export { plural } from "./i18n.js";

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

// Daty liczbowe: PL 01.10.2026, EN 01/10/2026 (dzień przed miesiącem, jak en-GB).
export function formatDayLabel(isoDate) {
  if (!isoDate) return "–";
  const [year, month, day] = isoDate.split("-");
  const separator = lang() === "pl" ? "." : "/";
  return `${day}${separator}${month}${separator}${year}`;
}

export function formatShortDay(isoDate) {
  const [, month, day] = isoDate.split("-");
  return lang() === "pl" ? `${day}.${month}` : `${day}/${month}`;
}

export function formatLongDay(isoDate) {
  return parseISO(isoDate).toLocaleDateString(locale(), { weekday: "long", day: "numeric", month: "long" });
}

export function weekdayShort(isoDate) {
  return parseISO(isoDate).toLocaleDateString(locale(), { weekday: "short" }).replace(".", "");
}

const numberFormats = new Map();
export function fmt(value, decimals = 0) {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) return "–";
  const key = `${locale()}:${decimals}`;
  if (!numberFormats.has(key)) {
    numberFormats.set(key, new Intl.NumberFormat(locale(), { maximumFractionDigits: decimals, useGrouping: "always" }));
  }
  return numberFormats.get(key).format(Number(value));
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

// Liczba do pola formularza: separator dziesiętny języka interfejsu (parseNumberInput przyjmuje oba).
export function inputNumber(value) {
  const text = String(value);
  return lang() === "pl" ? text.replace(".", ",") : text;
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

export function icon(name, cls = "icon") {
  return `<svg class="${cls}" aria-hidden="true"><use href="#i-${name}" /></svg>`;
}

