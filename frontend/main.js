const API_BASE = "/api";

// --- stałe domenowe ------------------------------------------------------------------------------

const TYPE_LABELS = {
  breakfast: "Śniadanie",
  lunch: "Obiad",
  dinner: "Kolacja",
  snack: "Przekąska",
  daily_balance: "Bilans dnia",
  weight: "Waga",
  waist: "Obwód pasa",
};

const GOAL_LABELS = { cut: "Redukcja", maintain: "Utrzymanie", bulk: "Masa" };
const MEAL_TYPES = ["breakfast", "lunch", "dinner", "snack"];
const MEAL_GROUP_LABELS = { breakfast: "Śniadanie", lunch: "Obiad", dinner: "Kolacja", snack: "Przekąski" };
const MEASUREMENT_FIELD = { weight: "weight_kg", waist: "waist_cm" };
const MACRO_FIELDS = ["kcal", "carbs_g", "fat_g", "protein_g"];
const FIELD_LABELS = {
  kcal: "Kalorie",
  carbs_g: "Węglowodany",
  fat_g: "Tłuszcze",
  protein_g: "Białko",
  weight_kg: "Waga",
  waist_cm: "Obwód pasa",
};

const MACROS = [
  { field: "total_protein_g", label: "Białko", kcalPerGram: 4, cls: "protein" },
  { field: "total_carbs_g", label: "Węglowodany", kcalPerGram: 4, cls: "carbs" },
  { field: "total_fat_g", label: "Tłuszcze", kcalPerGram: 9, cls: "fat" },
];

// Dzień "w celu": spożycie w granicach ±10% celu kcal dnia (regularność liczona tylko z dni z jedzeniem).
const ADHERENCE_TOLERANCE = 0.1;
const RING_CIRCUMFERENCE = 2 * Math.PI * 84;

const TEXT_TEMPLATES = {
  weight: "Waga: 82,4 kg",
  waist: "Obwód pasa: 91 cm",
  breakfast: "Śniadanie\nIlość kalorii: 540\nWęglowodany: 48\nTłuszcze: 18\nBiałko: 32",
  lunch: "Obiad\nIlość kalorii: 720\nWęglowodany: 62\nTłuszcze: 24\nBiałko: 45",
  dinner: "Kolacja\nIlość kalorii: 610\nWęglowodany: 40\nTłuszcze: 22\nBiałko: 38",
  snack: "Przekąska\nIlość kalorii: 240\nWęglowodany: 20\nTłuszcze: 10\nBiałko: 12",
  daily_balance: "Bilans dnia\nIlość kalorii: 2150\nWęglowodany: 210\nTłuszcze: 70\nBiałko: 145",
};

const ENTRY_HINTS = {
  daily_balance: "Bilans dnia zastępuje sumę wszystkich posiłków z tego dnia. Może być jeden na dzień.",
  weight: "Jeden pomiar na dzień – nowy wpis nadpisuje poprzedni. Cel kcal nie zmienia się automatycznie.",
  waist: "Jeden pomiar na dzień – nowy wpis nadpisuje poprzedni.",
};

const VIEWS = ["today", "log", "progress", "goals", "more"];

// --- elementy ------------------------------------------------------------------------------------

const $ = (id) => document.getElementById(id);
const el = new Proxy({}, { get: (cache, id) => (cache[id] ??= $(id)) });

const state = {
  userId: null,
  userName: "",
  token: "",
  tokenExpiresAt: "",
  view: "today",
  logDate: todayISO(),
  progressQuery: { kind: "days", days: 30 },
  entryType: defaultMealType(),
  entrySheet: { mode: "add", entry: null },
  actionEntry: null,
  dateContext: null,
  planSuggestion: null,
  calMonth: monthStartISO(todayISO()),
  entriesById: new Map(),
  goalType: null,
  lastProgress: null,
  historyExpanded: false,
};

// --- narzędzia -----------------------------------------------------------------------------------

function localISO(date) {
  const pad = (value) => String(value).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

function todayISO() {
  return localISO(new Date());
}

function monthStartISO(isoDate) {
  return `${isoDate.slice(0, 7)}-01`;
}

function addMonthsISO(monthStart, months) {
  const date = parseISO(monthStart);
  date.setMonth(date.getMonth() + months, 1);
  return localISO(date);
}

function monthEndISO(monthStart) {
  return addDaysISO(addMonthsISO(monthStart, 1), -1);
}

function parseISO(isoDate) {
  const [year, month, day] = isoDate.split("-").map(Number);
  return new Date(year, month - 1, day);
}

function addDaysISO(isoDate, days) {
  const date = parseISO(isoDate);
  date.setDate(date.getDate() + days);
  return localISO(date);
}

function daysBetween(fromISO, toISO) {
  const result = [];
  for (let current = fromISO; current <= toISO; current = addDaysISO(current, 1)) result.push(current);
  return result;
}

function formatDayLabel(isoDate) {
  if (!isoDate) return "–";
  const [year, month, day] = isoDate.split("-");
  return `${day}.${month}.${year}`;
}

function formatShortDay(isoDate) {
  const [, month, day] = isoDate.split("-");
  return `${day}.${month}`;
}

function formatLongDay(isoDate) {
  return parseISO(isoDate).toLocaleDateString("pl-PL", { weekday: "long", day: "numeric", month: "long" });
}

function weekdayShort(isoDate) {
  return parseISO(isoDate).toLocaleDateString("pl-PL", { weekday: "short" }).replace(".", "");
}

const numberFormats = new Map();
function fmt(value, decimals = 0) {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) return "–";
  if (!numberFormats.has(decimals)) {
    numberFormats.set(decimals, new Intl.NumberFormat("pl-PL", { maximumFractionDigits: decimals, useGrouping: "always" }));
  }
  return numberFormats.get(decimals).format(Number(value));
}

function fmtSigned(value, decimals = 0) {
  if (value === null || value === undefined) return "–";
  if (Math.abs(value) < 0.5 * 10 ** -decimals) return fmt(0, decimals);
  return `${value > 0 ? "+" : "−"}${fmt(Math.abs(value), decimals)}`;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function parseNumberInput(raw) {
  const text = String(raw ?? "").trim().replace(",", ".");
  if (!text) return null;
  const value = Number(text);
  return Number.isFinite(value) ? value : NaN;
}

function defaultMealType() {
  const hour = new Date().getHours();
  if (hour < 11) return "breakfast";
  if (hour < 16) return "lunch";
  if (hour < 21) return "dinner";
  return "snack";
}

function plural(count, one, few, many) {
  const mod10 = count % 10;
  const mod100 = count % 100;
  if (count === 1) return one;
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return few;
  return many;
}

function icon(name, cls = "icon") {
  return `<svg class="${cls}" aria-hidden="true"><use href="#i-${name}" /></svg>`;
}

// --- powiadomienia i blokada przycisków --------------------------------------------------------

function toast(text, variant = "info", timeoutMs = 5000) {
  const item = document.createElement("div");
  item.className = `toast ${variant}`;
  item.setAttribute("role", variant === "error" ? "alert" : "status");
  item.textContent = text;
  const close = document.createElement("button");
  close.type = "button";
  close.className = "toast-close";
  close.setAttribute("aria-label", "Zamknij");
  close.textContent = "×";
  close.addEventListener("click", () => item.remove());
  item.appendChild(close);
  el.toastRegion.appendChild(item);
  while (el.toastRegion.children.length > 3) el.toastRegion.firstElementChild.remove();
  if (timeoutMs > 0) setTimeout(() => item.remove(), timeoutMs);
}

function toastError(error) {
  toast(error?.message || String(error), "error", 9000);
}

async function withBusy(button, action) {
  if (button?.disabled) return undefined;
  if (button) {
    button.disabled = true;
    button.classList.add("is-busy");
  }
  try {
    return await action();
  } finally {
    if (button) {
      button.classList.remove("is-busy");
      button.disabled = false;
    }
  }
}

// --- API -----------------------------------------------------------------------------------------

function formatApiError(payload, fallback) {
  if (payload && Array.isArray(payload.detail)) {
    return payload.detail
      .map((entry) => {
        const field = Array.isArray(entry.loc) ? entry.loc[entry.loc.length - 1] : "";
        return FIELD_LABELS[field] ? `${FIELD_LABELS[field]}: ${entry.msg}` : entry.msg;
      })
      .join(" ");
  }
  if (payload && typeof payload.detail === "string") return payload.detail;
  return fallback;
}

async function fetchJSON(url, options = {}) {
  let response;
  try {
    response = await fetch(url, options);
  } catch {
    throw new Error("Brak połączenia z serwerem. Sprawdź, czy Calico działa.");
  }
  const raw = await response.text();
  let payload = null;
  try {
    payload = raw ? JSON.parse(raw) : null;
  } catch {
    payload = null;
  }
  if (!response.ok) {
    if (response.status === 428 && state.token) openOnboarding();
    if (response.status === 401 && state.token) {
      lockUser("PIN został zmieniony albo sesja wygasła. Odblokuj ponownie.");
    }
    const fallback = response.status >= 500 ? `Błąd serwera (${response.status}).` : `Błąd żądania (${response.status}).`;
    throw new Error(formatApiError(payload, fallback));
  }
  return payload;
}

function userHeaders(extra = {}) {
  return { Authorization: `Bearer ${state.token}`, ...extra };
}

// --- sesja w sessionStorage: przetrwa przeładowanie karty (np. gdy telefon uśpi przeglądarkę w tle),
// znika po zamknięciu karty. Przechowujemy podpisany token z serwera, nie PIN.

const SESSION_KEY = "calico.session";

function saveSession() {
  try {
    sessionStorage.setItem(
      SESSION_KEY,
      JSON.stringify({ userId: state.userId, userName: state.userName, token: state.token, expiresAt: state.tokenExpiresAt })
    );
  } catch {
    // tryb prywatny / zablokowany storage - sesja tylko w pamięci
  }
}

function readSession() {
  try {
    const session = JSON.parse(sessionStorage.getItem(SESSION_KEY) || "null");
    if (!session?.token || !session.userId) return null;
    if (session.expiresAt && Date.parse(session.expiresAt) <= Date.now()) return null;
    return session;
  } catch {
    return null;
  }
}

function clearSession() {
  try {
    sessionStorage.removeItem(SESSION_KEY);
  } catch {
    // brak dostępu do storage
  }
}

function api(path, { method = "GET", body, params } = {}) {
  if (!state.userId || !state.token) return Promise.reject(new Error("Najpierw odblokuj użytkownika PIN-em."));
  const query = new URLSearchParams({ user_id: String(state.userId), ...params });
  return fetchJSON(`${API_BASE}${path}?${query}`, {
    method,
    headers: userHeaders(body !== undefined ? { "Content-Type": "application/json" } : {}),
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
}

function profileApi(suffix = "", { method = "GET", body } = {}) {
  return fetchJSON(`${API_BASE}/profile/${state.userId}${suffix}`, {
    method,
    headers: userHeaders(body !== undefined ? { "Content-Type": "application/json" } : {}),
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
}

// --- dolne panele (dialog) ------------------------------------------------------------------------

function openSheet(dialog) {
  if (!dialog.open) dialog.showModal();
}

function closeSheet(dialog) {
  if (dialog.open) dialog.close();
}

document.querySelectorAll("dialog.sheet").forEach((dialog) => {
  dialog.querySelectorAll("[data-close]").forEach((button) => button.addEventListener("click", () => closeSheet(dialog)));
  // Klik w tło zamyka panel (poza wymuszonym uzupełnieniem profilu).
  dialog.addEventListener("click", (event) => {
    if (event.target === dialog && dialog.id !== "onboardingDialog") closeSheet(dialog);
  });
});

// --- blokada i sesja -------------------------------------------------------------------------------

function showScreen(name) {
  // name === null: nic nie pokazuj (wznawianie sesji po przeładowaniu, bez mignięcia ekranu blokady)
  el.lockScreen.hidden = name !== "lock";
  el.app.hidden = name !== "app";
}

function lockUser(message = "") {
  state.token = "";
  state.tokenExpiresAt = "";
  clearSession();
  state.entriesById.clear();
  document.querySelectorAll("dialog[open]").forEach((dialog) => dialog.close());
  showScreen("lock");
  el.pinInput.value = "";
  el.authStatus.textContent = message;
  el.authStatus.className = message ? "form-status error" : "form-status";
}

async function loadUsers(selectId = null) {
  const users = await fetchJSON(`${API_BASE}/users`);
  el.userSelect.innerHTML = "";
  if (!users.length) {
    const option = document.createElement("option");
    option.value = "";
    option.textContent = "Brak użytkowników – utwórz nowego";
    el.userSelect.appendChild(option);
    state.userId = null;
    el.authStatus.textContent = "Utwórz pierwszego użytkownika.";
    return;
  }
  users.forEach((user) => {
    const option = document.createElement("option");
    option.value = String(user.id);
    option.textContent = user.display_name;
    el.userSelect.appendChild(option);
  });
  const selected = users.find((user) => user.id === selectId) || users[0];
  state.userId = selected.id;
  state.userName = selected.display_name;
  el.userSelect.value = String(selected.id);
}

async function unlock() {
  if (!state.userId) return;
  const pin = el.pinInput.value.trim();
  if (!/^\d{4,8}$/.test(pin)) {
    el.authStatus.textContent = "PIN musi mieć 4–8 cyfr.";
    el.authStatus.className = "form-status error";
    return;
  }
  let session;
  try {
    session = await verifyPin(state.userId, pin);
  } catch (error) {
    el.authStatus.textContent = error.message;
    el.authStatus.className = "form-status error";
    el.pinInput.select();
    return;
  }
  el.pinInput.value = "";
  el.authStatus.textContent = "";
  await startSession(session);
}

function verifyPin(userId, pin) {
  return fetchJSON(`${API_BASE}/auth/verify`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: userId, pin }),
  });
}

async function startSession(session) {
  state.token = session.token;
  state.tokenExpiresAt = session.expires_at || session.expiresAt || "";
  saveSession();
  const profile = await profileApi();
  if (!profile.is_complete) {
    showScreen("lock");
    openOnboarding();
    return;
  }
  await enterApp();
}

async function enterApp() {
  state.logDate = todayISO();
  el.moreUser.textContent = state.userName;
  const view = viewFromHash();
  state.view = view;
  applyViewVisibility(view);
  await loadView(view);
  showScreen("app");
  // Wykresy rysowane przy ukrytej aplikacji mialy zastepcza szerokosc - przerysuj w docelowej.
  requestAnimationFrame(rerenderProgressCharts);
}

// --- nawigacja ----------------------------------------------------------------------------------------

function viewFromHash() {
  const name = location.hash.replace(/^#\/?/, "");
  return VIEWS.includes(name) ? name : "today";
}

function applyViewVisibility(view) {
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

async function loadView(view) {
  if (view === "today") return loadToday();
  if (view === "log") return loadLog();
  if (view === "progress") return loadProgress();
  if (view === "goals") return loadGoals();
  if (view === "more") return loadMore();
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

function goToLogDay(date) {
  state.logDate = date;
  goTo("log");
}

async function refreshAfterChange() {
  await loadView(state.view);
}

// --- wykresy (SVG) ---------------------------------------------------------------------------------

function setRing(total, target) {
  const pct = target > 0 ? Math.min(total / target, 1) : 0;
  el.ringProgress.style.strokeDasharray = `${RING_CIRCUMFERENCE}`;
  el.ringProgress.classList.toggle("is-empty", total <= 0);
  requestAnimationFrame(() => {
    el.ringProgress.style.strokeDashoffset = `${RING_CIRCUMFERENCE * (1 - pct)}`;
  });
}

function sparklineSvg(values, color) {
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

function chartWidth(container) {
  return Math.max(280, Math.round(container.clientWidth || 640));
}

function lineChartSvg({ dates, series, trend = [], color, unit, decimals = 1, label, width = 640 }) {
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
  const summary = `${label}: od ${fmt(first.value, decimals)} do ${fmt(last.value, decimals)} ${unit}, ${series.length} pomiarów.`;
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

function barChartSvg(dates, byDate, width = 640) {
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
      point?.has_food ? `${formatDayLabel(date)}: ${fmt(point.total_kcal)} / ${fmt(point.target_kcal)} kcal` : `${formatDayLabel(date)}: brak wpisów jedzenia`
    )}</title></rect>`;
    if (!point?.has_food) return label + hit;
    const barHeight = Math.max(2, (point.total_kcal / max) * plotHeight);
    const targetY = pad.top + plotHeight - (point.target_kcal / max) * plotHeight;
    const over = point.total_kcal > point.target_kcal * (1 + ADHERENCE_TOLERANCE);
    return `<rect class="chart-bar${over ? " over" : ""}" x="${(x + (slot - barWidth) / 2).toFixed(1)}" y="${(pad.top + plotHeight - barHeight).toFixed(1)}" width="${barWidth.toFixed(1)}" height="${barHeight.toFixed(1)}" rx="${Math.min(4, barWidth / 2).toFixed(1)}" />
      <line class="chart-target" x1="${x.toFixed(1)}" x2="${(x + slot).toFixed(1)}" y1="${targetY.toFixed(1)}" y2="${targetY.toFixed(1)}" />${label}${hit}`;
  });
  return `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Kalorie dziennie na tle celu (${food.length} dni z jedzeniem).">
    <defs><linearGradient id="barGradient" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#20D5FF" /><stop offset="100%" stop-color="#1AA8FF" stop-opacity="0.55" /></linearGradient></defs>
    <line class="chart-grid" x1="${pad.left}" x2="${width - pad.right}" y1="${height - pad.bottom}" y2="${height - pad.bottom}" />
    ${parts.join("")}
  </svg>`;
}

function emptyChart(title, text) {
  return `<div class="chart-empty"><strong>${escapeHtml(title)}</strong><span>${escapeHtml(text)}</span></div>`;
}

function dayStatus(point) {
  if (!point?.has_food) return "none";
  const target = point.target_kcal || 0;
  if (target > 0 && Math.abs(point.total_kcal - target) <= target * ADHERENCE_TOLERANCE) return "done";
  return "logged";
}

function dayDotsHtml(dates, byDate, { labels = false } = {}) {
  const today = todayISO();
  const statusText = { done: "w celu", logged: "wpisy poza zakresem celu", none: "brak wpisów jedzenia" };
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

function measurementSeries(points, field) {
  return points.filter((point) => point[field] !== null && point[field] !== undefined).map((point) => ({ date: point.log_date, value: point[field] }));
}

// Zmiana względem pomiaru sprzed ≥7 dni (albo najstarszego w zakresie).
function measurementDelta(series) {
  if (series.length < 2) return null;
  const last = series[series.length - 1];
  const weekAgo = addDaysISO(last.date, -7);
  const reference = [...series].reverse().find((point) => point.date <= weekAgo) || series[0];
  const days = Math.round((parseISO(last.date) - parseISO(reference.date)) / 86400000);
  return { diff: last.value - reference.value, label: days >= 6 && days <= 8 ? "w tym tygodniu" : `od ${formatShortDay(reference.date)}` };
}

function renderDelta(target, delta, { unit, goodWhen }) {
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

// --- Dziś -----------------------------------------------------------------------------------------

async function loadToday() {
  const today = todayISO();
  const [detail, month, plan] = await Promise.all([
    api(`/days/${today}`),
    api("/reports/summary", { params: { days: 30 } }),
    profileApi("/plan"),
  ]);
  state.goalType = plan.goal_type;
  el.todayDate.textContent = formatLongDay(today).replace(/^./, (letter) => letter.toUpperCase());
  renderHero(detail);
  renderMeasurementCards(month, plan.goal_type);
  renderAdherenceCard(month);
  renderTargetCard(plan);
  renderRecommendation(plan);
}

function renderHero(detail) {
  const total = Number(detail.total_kcal) || 0;
  const target = Number(detail.target_kcal) || 0;
  setRing(total, target);
  el.calorieRing.setAttribute("aria-label", `Spożyto ${fmt(total)} z ${fmt(target)} kcal`);
  el.ringConsumed.textContent = fmt(total);
  el.ringTarget.textContent = `/ ${fmt(target)} kcal`;
  const remaining = target - total;
  el.ringStatus.classList.toggle("over", remaining < 0);
  el.ringStatus.innerHTML =
    remaining >= 0 ? `Pozostało <strong>${fmt(remaining)} kcal</strong>` : `<strong>${fmt(-remaining)} kcal</strong> ponad cel`;

  const energy = MACROS.reduce((sum, macro) => sum + (Number(detail[macro.field]) || 0) * macro.kcalPerGram, 0);
  el.macroList.innerHTML = MACROS.map((macro) => {
    const grams = Number(detail[macro.field]) || 0;
    const share = energy > 0 ? Math.round(((grams * macro.kcalPerGram) / energy) * 100) : 0;
    return `<div class="macro">
      <span class="macro-name">${macro.label}</span>
      <span class="macro-value">${fmt(grams)} g<small>${share}% kcal</small></span>
      <span class="bar ${macro.cls}" role="img" aria-label="${macro.label}: ${share}% energii z makroskładników"><span style="width:${share}%"></span></span>
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
      config.spark.innerHTML = `<span class="spark-empty">Dodaj pierwszy pomiar</span>`;
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
  el.adherenceValue.innerHTML = `${done} / 7<small>dni w celu</small>`;
  el.adherenceDots.innerHTML = dayDotsHtml(dates, byDate);
  el.adherenceSub.textContent = `Wpisy jedzenia: ${logged} z 7 dni · „w celu” = ±${ADHERENCE_TOLERANCE * 100}% celu kcal`;
}

function paceText(rate) {
  if (rate === null || rate === undefined) return "–";
  if (Math.abs(rate) < 0.05) return "≈ 0 kg/tydz.";
  return `${fmtSigned(rate, 2)} kg/tydz.`;
}

function renderTargetCard(plan) {
  el.targetValue.innerHTML = `${fmt(plan.daily_kcal_target)}<small>kcal/dzień</small>`;
  el.targetGoal.textContent = GOAL_LABELS[plan.goal_type] || "–";
  el.targetPace.textContent = paceText(plan.expected_rate_kg_per_week);
}

function renderRecommendation(plan) {
  const suggestion = plan.suggested_target_kcal;
  el.recommendationCard.hidden = suggestion === null || suggestion === undefined;
  if (!el.recommendationCard.hidden) {
    el.recommendationText.textContent = `Trend masy z ostatnich tygodni sugeruje zmianę celu na ${fmt(suggestion)} kcal (${fmtSigned(
      suggestion - plan.daily_kcal_target
    )} kcal). Decyzja należy do Ciebie.`;
  }
}

// --- Dziennik -------------------------------------------------------------------------------------

async function loadLog(date = state.logDate) {
  state.logDate = date;
  if (monthStartISO(date) !== state.calMonth) state.calMonth = monthStartISO(date);
  const [detail] = await Promise.all([api(`/days/${date}`), loadCalendar()]);
  const today = todayISO();
  el.logDate.value = date;
  el.logDate.max = addDaysISO(today, 1);
  el.logDateLabel.textContent = `${formatLongDay(date)}${date === today ? " · dziś" : ""}`;
  el.logNextBtn.disabled = date >= addDaysISO(today, 1);
  el.logTodayBtn.hidden = date === today;
  el.logSummary.textContent = `${fmt(detail.total_kcal)} / ${fmt(detail.target_kcal)} kcal · ${detail.entries.length} ${plural(detail.entries.length, "pozycja", "pozycje", "pozycji")}`;
  renderLogGroups(detail);
}

function entryValueText(entry) {
  if (entry.entry_type === "weight") return `${fmt(entry.weight_kg, 1)} kg`;
  if (entry.entry_type === "waist") return `${fmt(entry.waist_cm, 1)} cm`;
  return `${fmt(entry.kcal)} kcal`;
}

function entryMacroText(entry) {
  if (MEASUREMENT_FIELD[entry.entry_type]) return "";
  return `Białko ${fmt(entry.protein_g)} g · Węgl. ${fmt(entry.carbs_g)} g · Tł. ${fmt(entry.fat_g)} g`;
}

function entryRowHtml(entry) {
  const macros = entryMacroText(entry);
  return `<button class="entry-row" type="button" data-entry-id="${entry.id}" aria-label="${escapeHtml(`${entry.entry_label}, ${entryValueText(entry)} – opcje`)}">
    <span class="entry-name">${escapeHtml(entry.entry_label)}</span>
    <span class="entry-value">${escapeHtml(entryValueText(entry))}</span>
    ${macros ? `<span class="entry-macros">${escapeHtml(macros)}</span>` : ""}
  </button>`;
}

function renderLogGroups(detail) {
  state.entriesById.clear();
  detail.entries.forEach((entry) => state.entriesById.set(entry.id, { ...entry, log_date: detail.log_date }));
  const groups = MEAL_TYPES.map((type) => ({ type, label: MEAL_GROUP_LABELS[type], entries: detail.entries.filter((entry) => entry.entry_type === type) }));
  const balance = detail.entries.filter((entry) => entry.entry_type === "daily_balance");
  const measurements = detail.entries.filter((entry) => MEASUREMENT_FIELD[entry.entry_type]);

  const html = groups.map((group) => {
    const kcal = group.entries.reduce((sum, entry) => sum + (entry.kcal || 0), 0);
    const excluded = detail.balance_mode && group.entries.length > 0;
    const body = group.entries.length
      ? `<div class="group-rows">${group.entries.map(entryRowHtml).join("")}</div>`
      : `<div class="group-empty"><span>Brak wpisów</span><button class="btn btn-quiet" type="button" data-add-type="${group.type}">${icon("plus")}Dodaj</button></div>`;
    return `<details class="card meal-group${excluded ? " excluded" : ""}" ${group.entries.length ? "open" : ""}>
      <summary><span class="group-name">${group.label}</span><span class="group-kcal">${fmt(kcal)} kcal</span>${icon("chevron-down")}</summary>
      ${body}
    </details>`;
  });
  if (balance.length) {
    html.push(`<details class="card meal-group" open>
      <summary><span class="group-name">Bilans dnia</span><span class="group-kcal">${fmt(balance[0].kcal)} kcal</span>${icon("chevron-down")}</summary>
      <div class="group-rows">${balance.map(entryRowHtml).join("")}</div>
      <div class="group-empty"><span>Zastępuje sumę posiłków z tego dnia.</span></div>
    </details>`);
  }
  if (measurements.length) {
    html.push(`<details class="card meal-group" open>
      <summary><span class="group-name">Pomiary</span><span class="group-kcal"></span>${icon("chevron-down")}</summary>
      <div class="group-rows">${measurements.map(entryRowHtml).join("")}</div>
    </details>`);
  }
  el.logGroups.innerHTML = html.join("");
}

el.logGroups.addEventListener("click", (event) => {
  const addButton = event.target.closest("[data-add-type]");
  if (addButton) {
    openEntrySheet({ mode: "add", type: addButton.dataset.addType, date: state.logDate });
    return;
  }
  const row = event.target.closest(".entry-row");
  if (row) openActionSheet(state.entriesById.get(Number(row.dataset.entryId)));
});

// --- kalendarz dziennika (szybki wybór dnia; kropka = dzień z wpisami) ---------------------------------

async function loadCalendar() {
  const month = state.calMonth;
  const days = await api("/days", { params: { date_from: month, date_to: monthEndISO(month), limit: 62 } });
  if (month === state.calMonth) renderCalendar(new Map(days.map((day) => [day.log_date, day])));
}

function renderCalendar(daysByDate) {
  const month = state.calMonth;
  const today = todayISO();
  const maxDate = addDaysISO(today, 1);
  const label = parseISO(month).toLocaleDateString("pl-PL", { month: "long", year: "numeric" });
  el.calMonthLabel.textContent = label.replace(/^./, (letter) => letter.toUpperCase());
  el.calNextBtn.disabled = addMonthsISO(month, 1) > maxDate;
  const leading = (parseISO(month).getDay() + 6) % 7; // poniedziałek = pierwsza kolumna
  const cells = Array.from({ length: leading }, () => '<span class="cal-cell cal-blank" aria-hidden="true"></span>');
  daysBetween(month, monthEndISO(month)).forEach((date) => {
    const day = daysByDate.get(date);
    const kind = !day ? "" : day.total_kcal > 0 ? "food" : "measure";
    const classes = ["cal-cell", "cal-day", kind && `has-${kind}`, date === state.logDate && "selected", date === today && "today"].filter(Boolean).join(" ");
    const entries = day ? `${day.entries_count} ${plural(day.entries_count, "wpis", "wpisy", "wpisów")}` : "brak wpisów";
    const aria = `${formatLongDay(date)}, ${entries}${day && day.total_kcal > 0 ? `, ${fmt(day.total_kcal)} kcal` : ""}`;
    cells.push(
      `<button class="${classes}" type="button" data-date="${date}" aria-label="${escapeHtml(aria)}" aria-pressed="${date === state.logDate}" ${date > maxDate ? "disabled" : ""}>
        <span>${Number(date.slice(8))}</span>${kind ? '<span class="cal-mark" aria-hidden="true"></span>' : ""}
      </button>`
    );
  });
  el.calGrid.innerHTML = cells.join("");
}

el.calGrid.addEventListener("click", (event) => {
  const day = event.target.closest(".cal-day");
  if (day && !day.disabled) loadLog(day.dataset.date).catch(toastError);
});
el.calPrevBtn.addEventListener("click", () => {
  state.calMonth = addMonthsISO(state.calMonth, -1);
  loadCalendar().catch(toastError);
});
el.calNextBtn.addEventListener("click", () => {
  state.calMonth = addMonthsISO(state.calMonth, 1);
  loadCalendar().catch(toastError);
});

el.logPrevBtn.addEventListener("click", () => loadLog(addDaysISO(state.logDate, -1)).catch(toastError));
el.logNextBtn.addEventListener("click", () => loadLog(addDaysISO(state.logDate, 1)).catch(toastError));
el.logTodayBtn.addEventListener("click", () => loadLog(todayISO()).catch(toastError));
el.logDate.addEventListener("change", () => {
  if (el.logDate.value) loadLog(el.logDate.value).catch(toastError);
});
el.logUndoBtn.addEventListener("click", () =>
  withBusy(el.logUndoBtn, async () => {
    await api(`/days/${state.logDate}/undo`, { method: "POST" });
    toast("Cofnięto ostatnią zmianę w tym dniu.", "success", 3500);
    await refreshAfterChange();
  }).catch(toastError)
);
el.logClearBtn.addEventListener("click", async () => {
  if (!confirm(`Usunąć wszystkie pozycje z dnia ${formatDayLabel(state.logDate)}?`)) return;
  try {
    await withBusy(el.logClearBtn, async () => {
      await api(`/days/${state.logDate}/clear`, { method: "POST" });
      toast(`Wyczyszczono dzień ${formatDayLabel(state.logDate)}.`, "success", 3500);
      await refreshAfterChange();
    });
  } catch (error) {
    toastError(error);
  }
});

// --- Postępy -------------------------------------------------------------------------------------------

function progressRange(query) {
  const today = todayISO();
  if (query.kind === "days") return { from: addDaysISO(today, -(query.days - 1)), to: today };
  if (query.kind === "all") return { from: addDaysISO(today, -3659), to: today };
  return { from: query.from, to: query.to };
}

async function loadProgress(query = state.progressQuery) {
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
  renderProgressMeasurement(weight, { value: el.pWeightValue, delta: el.pWeightDelta, chart: el.pWeightChart, unit: "kg", color: "#1AA8FF", label: "Waga", trend, emptyAction: "wagę" });
  const waist = measurementSeries(report.points, "waist_cm");
  renderProgressMeasurement(waist, { value: el.pWaistValue, delta: el.pWaistDelta, chart: el.pWaistChart, unit: "cm", color: "#32E6C4", label: "Obwód pasa", trend: [], emptyAction: "obwód pasa" });

  const byDate = new Map(report.points.map((point) => [point.log_date, point]));
  const foodDays = report.points.filter((point) => point.has_food);
  const inTarget = foodDays.filter((point) => dayStatus(point) === "done").length;
  el.pAvgKcal.textContent = report.days_with_food ? `${fmt(report.average_kcal)} kcal` : "–";
  el.pAvgTarget.textContent = report.days_with_food ? `${fmt(report.average_target_kcal)} kcal` : "–";
  el.pAdherence.textContent = report.days_with_food ? `${Math.round((inTarget / report.days_with_food) * 100)}%` : "–";
  el.pKcalChart.innerHTML = barChartSvg(dates, byDate, chartWidth(el.pKcalChart)) || emptyChart("Brak wpisów jedzenia", "Dodaj posiłki, aby zobaczyć kalorie na tle celu.");
  el.pKcalNote.textContent = report.days_with_food
    ? `${inTarget} z ${report.days_with_food} dni z jedzeniem w celu (±${ADHERENCE_TOLERANCE * 100}%). Bilans względem celu: ${fmtSigned(report.balance_vs_target_kcal)} kcal. Najwyższy dzień: ${fmt(report.highest_kcal)} kcal (${formatDayLabel(report.highest_kcal_day)}).`
    : "";

  const weekByDate = new Map(week.points.map((point) => [point.log_date, point]));
  const weekDates = daysBetween(addDaysISO(todayISO(), -6), todayISO());
  el.pWeekDots.innerHTML = dayDotsHtml(weekDates, weekByDate, { labels: true });
  const weekDone = weekDates.filter((date) => dayStatus(weekByDate.get(date)) === "done").length;
  const weekLogged = weekDates.filter((date) => dayStatus(weekByDate.get(date)) !== "none").length;
  el.pWeekSub.textContent = `${weekDone} / 7 dni w celu · wpisy jedzenia w ${weekLogged} z 7 dni. Jeden słabszy dzień nie przekreśla tygodnia – liczy się regularność.`;

  const rows = [...report.points].reverse();
  const visible = state.historyExpanded ? rows : rows.slice(0, HISTORY_PREVIEW_ROWS);
  const moreButton =
    rows.length > visible.length
      ? `<button class="btn btn-quiet btn-block" type="button" data-history-more>Pokaż wszystkie (${rows.length} ${plural(rows.length, "dzień", "dni", "dni")})</button>`
      : "";
  el.pHistory.innerHTML = rows.length
    ? visible
        .map((point) => {
          const parts = [];
          if (point.has_food) parts.push(`B ${fmt(point.total_protein_g)} g · W ${fmt(point.total_carbs_g)} g · T ${fmt(point.total_fat_g)} g`);
          if (point.weight_kg !== null) parts.push(`waga ${fmt(point.weight_kg, 1)} kg`);
          if (point.waist_cm !== null) parts.push(`pas ${fmt(point.waist_cm, 1)} cm`);
          const over = point.has_food && point.total_kcal > point.target_kcal * (1 + ADHERENCE_TOLERANCE);
          return `<button class="history-row" type="button" data-date="${point.log_date}">
            <span class="history-day">${escapeHtml(formatDayLabel(point.log_date))}<small>${escapeHtml(weekdayShort(point.log_date))}</small></span>
            <span class="history-kcal${over ? " over" : ""}">${point.has_food ? `${fmt(point.total_kcal)} / ${fmt(point.target_kcal)} kcal` : "–"}</span>
            <span class="history-meta">${escapeHtml(parts.join(" · "))}</span>
          </button>`;
        })
        .join("") + moreButton
    : emptyChart("Brak wpisów w zakresie", "Zmień zakres albo dodaj pierwsze wpisy.");
}

function rerenderProgressCharts() {
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
    config.chart.innerHTML = emptyChart(`Brak pomiarów: ${config.label.toLowerCase()}`, `Dodaj ${config.emptyAction} w zakładce Dziś, aby śledzić postęp.`);
    return;
  }
  const first = series[0];
  const last = series[series.length - 1];
  config.value.innerHTML = `${fmt(last.value, 1)}<small>${config.unit}</small>`;
  const diff = last.value - first.value;
  config.delta.textContent = series.length > 1 ? `${fmtSigned(diff, 1)} ${config.unit} w zakresie` : "jeden pomiar";
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

// --- Cele -------------------------------------------------------------------------------------------

const PLAN_STATUS_LABELS = {
  no_data: "Za mało danych",
  wait: "Obserwuj",
  on_track: "Plan działa",
  below_range: "Poza zakresem",
  above_range: "Poza zakresem",
};

async function loadGoals() {
  renderPlan(await profileApi("/plan"));
}

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

el.planRefreshBtn.addEventListener("click", () => withBusy(el.planRefreshBtn, loadGoals).catch(toastError));

el.planApplyBtn.addEventListener("click", async () => {
  const target = state.planSuggestion;
  if (target === null) return;
  if (!confirm(`Ustawić nowy cel planu: ${fmt(target)} kcal/dzień? Obowiązuje od dziś.`)) return;
  try {
    await withBusy(el.planApplyBtn, async () => {
      renderPlan(await profileApi("/plan/apply", { method: "POST", body: { target_kcal: target } }));
      toast(`Nowy cel planu: ${fmt(target)} kcal/dzień.`, "success");
    });
  } catch (error) {
    toastError(error);
  }
});

// --- Więcej: profil, PIN, eksport, konto ------------------------------------------------------------

async function loadMore() {
  const profile = await profileApi();
  if (!profile.is_complete) {
    openOnboarding();
    return;
  }
  const form = el.profileForm;
  form.sex.value = profile.sex;
  form.age.value = profile.age;
  form.height_cm.value = String(profile.height_cm).replace(".", ",");
  form.weight_kg.value = String(profile.weight_kg).replace(".", ",");
  form.activity_level.value = profile.activity_level;
  form.goal_type.value = profile.goal_type;
  form.goal_delta_pct_percent.value = Math.round((profile.goal_delta_pct || 0) * 100);
  updateGoalDeltaUi(form);
  el.profileStatus.textContent = "";
  el.profileTarget.textContent = `${fmt(profile.daily_kcal_target)} kcal/dzień`;
  const since = profile.plan_started_on ? ` Plan od ${formatDayLabel(profile.plan_started_on)}.` : "";
  el.profileCurrentWeight.textContent =
    profile.current_weight_kg !== null && profile.current_weight_kg !== undefined
      ? `Aktualna waga: ${fmt(profile.current_weight_kg, 1)} kg (${formatDayLabel(profile.current_weight_date)}).${since}`
      : `Brak pomiarów wagi.${since}`;
}

function readProfilePayload(form) {
  const choices = [
    ["sex", "Płeć"],
    ["activity_level", "Aktywność"],
    ["goal_type", "Cel"],
  ];
  for (const [key, label] of choices) {
    if (!form[key].value) return { error: `${label}: wybierz wartość.` };
  }
  const delta = parseNumberInput(form.goal_delta_pct_percent.value);
  const payload = {
    sex: form.sex.value,
    age: parseNumberInput(form.age.value),
    height_cm: parseNumberInput(form.height_cm.value),
    weight_kg: parseNumberInput(form.weight_kg.value),
    activity_level: form.activity_level.value,
    goal_type: form.goal_type.value,
    goal_delta_pct: delta === null || Number.isNaN(delta) ? delta : delta / 100,
  };
  const rules = [
    ["age", 10, 100, "Wiek"],
    ["height_cm", 120, 230, "Wzrost"],
    ["weight_kg", 30, 300, "Waga"],
    ["goal_delta_pct", 0, 0.3, "Korekta celu"],
  ];
  for (const [key, min, max, label] of rules) {
    const value = payload[key];
    if (value === null || Number.isNaN(value) || value < min || value > max) {
      const range = key === "goal_delta_pct" ? "0–30%" : `${min}–${max}`;
      return { error: `${label}: podaj wartość z zakresu ${range}.` };
    }
  }
  if (payload.age !== Math.round(payload.age)) return { error: "Wiek: podaj pełną liczbę lat." };
  return { payload };
}

el.profileForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const result = readProfilePayload(el.profileForm);
  if (result.error) {
    el.profileStatus.textContent = result.error;
    el.profileStatus.className = "form-status span-2 error";
    return;
  }
  const button = event.submitter || el.profileForm.querySelector('button[type="submit"]');
  try {
    await withBusy(button, async () => {
      await profileApi("", { method: "PUT", body: result.payload });
      await loadMore();
      el.profileStatus.textContent = "Zapisano profil – utworzono nowy plan kaloryczny.";
      el.profileStatus.className = "form-status span-2 success";
    });
  } catch (error) {
    el.profileStatus.textContent = error.message;
    el.profileStatus.className = "form-status span-2 error";
  }
});

el.pinChangeForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const newPin = el.newPinInput.value.trim();
  if (!/^\d{4,8}$/.test(newPin)) {
    toast("Nowy PIN musi mieć 4–8 cyfr.", "error");
    return;
  }
  try {
    await withBusy(event.submitter, async () => {
      const changed = await fetchJSON(`${API_BASE}/users/${state.userId}/pin`, {
        method: "POST",
        headers: userHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({ new_pin: newPin }),
      });
      // Zmiana PIN-u unieważnia stare tokeny - serwer zwraca nowy.
      state.token = changed.token;
      state.tokenExpiresAt = changed.expires_at;
      saveSession();
      el.newPinInput.value = "";
      toast("PIN został zmieniony.", "success");
    });
  } catch (error) {
    toastError(error);
  }
});

el.exportBtn.addEventListener("click", () =>
  withBusy(el.exportBtn, async () => {
    const response = await fetch(`${API_BASE}/export?user_id=${state.userId}`, { headers: userHeaders() });
    if (!response.ok) throw new Error(`Eksport nie powiódł się (${response.status}).`);
    const blob = await response.blob();
    const match = /filename="([^"]+)"/.exec(response.headers.get("Content-Disposition") || "");
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = match ? match[1] : "calico.csv";
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(link.href), 1000);
  }).catch(toastError)
);

el.logoutBtn.addEventListener("click", () => {
  location.hash = "";
  lockUser();
});

el.deleteUserBtn.addEventListener("click", async () => {
  if (!confirm(`Usunąć konto „${state.userName}” razem ze wszystkimi wpisami? Tej operacji nie można cofnąć.`)) return;
  try {
    await withBusy(el.deleteUserBtn, async () => {
      await fetchJSON(`${API_BASE}/users/${state.userId}`, { method: "DELETE", headers: userHeaders() });
      location.hash = "";
      lockUser();
      await loadUsers();
      toast("Konto zostało usunięte.", "success");
    });
  } catch (error) {
    toastError(error);
  }
});

// --- panel wpisu (dodawanie / edycja) ------------------------------------------------------------------

function showFieldGroup(type) {
  const group = type === "weight" ? "weight" : type === "waist" ? "waist" : "macro";
  el.entryForm.querySelectorAll("[data-fields]").forEach((field) => {
    field.hidden = field.dataset.fields !== group;
  });
}

function setSheetType(type) {
  state.entryType = type;
  el.entryTypes.querySelectorAll(".type-chip").forEach((chip) => chip.setAttribute("aria-checked", String(chip.dataset.type === type)));
  showFieldGroup(type);
  el.entryHint.textContent = ENTRY_HINTS[type] || "";
  if (state.entrySheet.mode === "add") {
    el.entrySheetTitle.textContent = type === "weight" ? "Dodaj wagę" : type === "waist" ? "Dodaj pomiar pasa" : type === "daily_balance" ? "Dodaj bilans dnia" : "Dodaj posiłek";
  }
}

function setEntryMode(mode) {
  el.entryModeSwitch.querySelectorAll(".seg").forEach((button) => button.classList.toggle("active", button.dataset.mode === mode));
  el.entryForm.hidden = mode !== "form";
  el.textForm.hidden = mode !== "text";
  if (mode === "text") {
    el.entrySheetTitle.textContent = "Szybki wpis tekstowy";
    if (!el.messageInput.value.trim()) el.messageInput.value = TEXT_TEMPLATES[state.entryType];
    el.textStatus.textContent = "";
  } else {
    setSheetType(state.entryType);
  }
}

function openEntrySheet({ mode, type, date, entry }) {
  state.entrySheet = { mode, entry: entry || null };
  el.entryError.textContent = "";
  el.entryForm.querySelectorAll("[data-fields] input").forEach((input) => {
    input.value = "";
  });
  const editing = mode === "edit";
  el.entryModeSwitch.hidden = editing;
  el.entryDateField.hidden = editing;
  el.entryDate.max = addDaysISO(todayISO(), 1);
  el.entryDate.value = date || todayISO();
  el.entrySaveBtn.textContent = editing ? "Zapisz zmiany" : "Zapisz";
  if (editing) {
    el.entrySheetTitle.textContent = `Edytuj: ${entry.entry_label}`;
    [...MACRO_FIELDS, "weight_kg", "waist_cm"].forEach((field) => {
      const input = el.entryForm.querySelector(`[name="${field}"]`);
      if (input && entry[field] !== null && entry[field] !== undefined) input.value = String(entry[field]).replace(".", ",");
    });
  }
  setSheetType(editing ? entry.entry_type : type || state.entryType);
  setEntryMode("form");
  openSheet(el.entrySheet);
  requestAnimationFrame(() => {
    el.entryForm.querySelector("[data-fields]:not([hidden]) input")?.focus({ preventScroll: true });
  });
}

function readEntryValues(type) {
  const fields = MEASUREMENT_FIELD[type] ? [MEASUREMENT_FIELD[type]] : MACRO_FIELDS;
  const payload = { entry_type: type };
  for (const field of fields) {
    const input = el.entryForm.querySelector(`[name="${field}"]`);
    const value = parseNumberInput(input.value);
    if (value === null) {
      input.focus();
      throw new Error(`Uzupełnij pole: ${FIELD_LABELS[field]}.`);
    }
    if (Number.isNaN(value) || value < 0) {
      input.focus();
      throw new Error(`${FIELD_LABELS[field]}: podaj liczbę nieujemną, np. 82,4.`);
    }
    payload[field] = value;
  }
  return payload;
}

el.entryTypes.addEventListener("click", (event) => {
  const chip = event.target.closest(".type-chip");
  if (!chip) return;
  setSheetType(chip.dataset.type);
  el.entryForm.querySelector("[data-fields]:not([hidden]) input")?.focus({ preventScroll: true });
});

el.entryModeSwitch.addEventListener("click", (event) => {
  const button = event.target.closest(".seg");
  if (button) setEntryMode(button.dataset.mode);
});

el.entryForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  el.entryError.textContent = "";
  try {
    await withBusy(el.entrySaveBtn, async () => {
      const values = readEntryValues(state.entryType);
      const { mode, entry } = state.entrySheet;
      if (mode === "edit") {
        await api(`/days/${entry.log_date}/entries/${entry.id}`, { method: "PATCH", body: { entry: values } });
        toast("Zapisano zmiany.", "success", 3000);
      } else {
        const date = el.entryDate.value || todayISO();
        await api(`/days/${date}/entries`, { method: "POST", body: values });
        toast(`Zapisano: ${TYPE_LABELS[state.entryType]} (${formatDayLabel(date)}).`, "success", 3500);
      }
      closeSheet(el.entrySheet);
      await refreshAfterChange();
    });
  } catch (error) {
    el.entryError.textContent = error.message;
  }
});

el.textForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = el.messageInput.value.trim();
  if (!message) return;
  try {
    await withBusy(el.textSendBtn, async () => {
      const data = await fetchJSON(`${API_BASE}/chat/message`, {
        method: "POST",
        headers: userHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({ user_id: state.userId, message }),
      });
      el.textStatus.textContent = data.reply;
      el.textStatus.className = `form-status text-status ${data.kind === "error" ? "error" : data.kind === "saved" ? "success" : ""}`;
      if (data.kind === "saved") {
        el.messageInput.value = "";
        closeSheet(el.entrySheet);
        toast(data.reply, "success", 6000);
        await refreshAfterChange();
      }
    });
  } catch (error) {
    el.textStatus.textContent = error.message;
    el.textStatus.className = "form-status text-status error";
  }
});

el.messageInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
    event.preventDefault();
    el.textForm.requestSubmit();
  }
});

el.insertTemplateBtn.addEventListener("click", () => {
  el.messageInput.value = TEXT_TEMPLATES[state.entryType];
  el.messageInput.focus();
});

el.addFoodBtn.addEventListener("click", () => openEntrySheet({ mode: "add", type: defaultMealType() }));
[el.weightCard, el.waistCard].forEach((card) => card.addEventListener("click", () => openEntrySheet({ mode: "add", type: card.dataset.measure })));

// --- akcje pozycji: edytuj / duplikuj / przenieś / usuń ---------------------------------------------------

function openActionSheet(entry) {
  if (!entry) return;
  state.actionEntry = entry;
  el.actionSheetTitle.textContent = entry.entry_label;
  el.actionSheetSub.textContent = `${entryValueText(entry)} · ${formatDayLabel(entry.log_date)}`;
  openSheet(el.actionSheet);
}

el.actionSheet.addEventListener("click", async (event) => {
  const button = event.target.closest(".action-item");
  if (!button) return;
  const entry = state.actionEntry;
  closeSheet(el.actionSheet);
  const action = button.dataset.action;
  if (action === "edit") {
    openEntrySheet({ mode: "edit", entry });
  } else if (action === "move" || action === "duplicate") {
    openDateSheet(entry, action);
  } else if (action === "delete") {
    if (!confirm(`Usunąć pozycję „${entry.entry_label}” z dnia ${formatDayLabel(entry.log_date)}?`)) return;
    try {
      await api(`/days/${entry.log_date}/entries/${entry.id}`, { method: "DELETE" });
      toast(`Usunięto: ${entry.entry_label}.`, "success", 3500);
      await refreshAfterChange();
    } catch (error) {
      toastError(error);
    }
  }
});

function openDateSheet(entry, mode) {
  state.dateContext = { entry, mode };
  const isMove = mode === "move";
  el.dateSheetTitle.textContent = isMove ? "Przenieś wpis" : "Duplikuj wpis";
  el.dateSheetCopy.textContent = `${entry.entry_label} – ${entryValueText(entry)}, z dnia ${formatDayLabel(entry.log_date)}.`;
  el.dateSheetInput.max = addDaysISO(todayISO(), 1);
  el.dateSheetInput.value = isMove ? addDaysISO(entry.log_date, -1) : entry.log_date;
  el.dateSheetError.textContent = "";
  openSheet(el.dateSheet);
}

el.dateSheetForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const { entry, mode } = state.dateContext;
  const targetDate = el.dateSheetInput.value;
  if (!targetDate) {
    el.dateSheetError.textContent = "Wybierz dzień.";
    return;
  }
  try {
    await withBusy(el.dateSheetSaveBtn, async () => {
      await api(`/days/${entry.log_date}/entries/${entry.id}/${mode}`, { method: "POST", body: { target_date: targetDate } });
      closeSheet(el.dateSheet);
      toast(`${mode === "move" ? "Przeniesiono" : "Zduplikowano"} wpis do dnia ${formatDayLabel(targetDate)}.`, "success", 4000);
      if (state.view === "log" && mode === "move") state.logDate = targetDate;
      await refreshAfterChange();
    });
  } catch (error) {
    el.dateSheetError.textContent = error.message;
  }
});

// --- korekta celu: znak zależny od celu i podgląd wyliczeń ------------------------------------------------

const GOAL_DELTA_UI = {
  cut: { label: "Deficyt kalorii", sign: "−", suggested: 15, hint: "Redukcja: cel = zapotrzebowanie (TDEE) MINUS podany procent. Zwykle 10–20%." },
  bulk: { label: "Nadwyżka kalorii", sign: "+", suggested: 10, hint: "Masa: cel = zapotrzebowanie (TDEE) PLUS podany procent. Zwykle 5–15%." },
  maintain: { label: "Korekta celu", sign: "", suggested: 0, hint: "Utrzymanie: cel = zapotrzebowanie (TDEE), bez korekty." },
};

const goalDeltaState = new Map();

function bindGoalDelta(form) {
  goalDeltaState.set(form, { timer: null, seq: 0 });
  form.goal_type.addEventListener("change", () => updateGoalDeltaUi(form, { goalChanged: true }));
  ["input", "change"].forEach((type) => form.addEventListener(type, () => scheduleGoalPreview(form)));
}

function updateGoalDeltaUi(form, { goalChanged = false } = {}) {
  const box = form.querySelector("[data-goal-delta]");
  const input = form.goal_delta_pct_percent;
  const goal = form.goal_type.value;
  const ui = GOAL_DELTA_UI[goal];
  box.querySelector("[data-delta-label]").textContent = ui ? ui.label : "Korekta celu";
  const sign = box.querySelector("[data-delta-sign]");
  sign.textContent = ui ? ui.sign : "";
  sign.className = `delta-sign ${goal}`;
  box.querySelector("[data-delta-hint]").textContent = ui ? ui.hint : "Najpierw wybierz cel.";
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
  if (payload.goal_type === "cut") {
    return `Zapotrzebowanie (TDEE): ${tdee}. Cel: ${tdee} − ${pct}% = ${fmt(preview.target_kcal)} kcal/dzień (${fmtSigned(preview.delta_kcal)} kcal).`;
  }
  if (payload.goal_type === "bulk") {
    return `Zapotrzebowanie (TDEE): ${tdee}. Cel: ${tdee} + ${pct}% = ${fmt(preview.target_kcal)} kcal/dzień (${fmtSigned(preview.delta_kcal)} kcal).`;
  }
  return `Zapotrzebowanie (TDEE) = cel: ${fmt(preview.target_kcal)} kcal/dzień.`;
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

function openOnboarding() {
  if (el.onboardingDialog.open) return;
  el.onboardingForm.reset();
  el.onboardingError.textContent = "";
  el.onboardingTitle.textContent = state.userName ? `Uzupełnij profil: ${state.userName}` : "Uzupełnij profil";
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
      toast("Profil zapisany. Plan kaloryczny został wyliczony – możesz zaczynać.", "success");
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

// --- ekran blokady: użytkownicy -----------------------------------------------------------------------------

el.unlockForm.addEventListener("submit", (event) => {
  event.preventDefault();
  withBusy(el.unlockBtn, unlock).catch((error) => {
    el.authStatus.textContent = error.message;
    el.authStatus.className = "form-status error";
  });
});

el.userSelect.addEventListener("change", () => {
  if (!el.userSelect.value) return;
  state.userId = Number(el.userSelect.value);
  state.userName = el.userSelect.options[el.userSelect.selectedIndex].textContent;
  el.authStatus.textContent = "";
  el.pinInput.value = "";
  el.pinInput.focus();
});

el.newUserBtn.addEventListener("click", () => {
  el.userDialogForm.reset();
  el.userDialogError.textContent = "";
  openSheet(el.userDialog);
  el.newUserName.focus();
});

el.userDialogForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const displayName = el.newUserName.value.trim();
  const pin = el.newUserPin.value.trim();
  if (displayName.length < 2) {
    el.userDialogError.textContent = "Nazwa musi mieć co najmniej 2 znaki.";
    return;
  }
  if (!/^\d{4,8}$/.test(pin)) {
    el.userDialogError.textContent = "PIN musi mieć 4–8 cyfr.";
    return;
  }
  if (pin !== el.newUserPin2.value.trim()) {
    el.userDialogError.textContent = "PIN-y nie są takie same.";
    return;
  }
  try {
    await withBusy(el.userDialogSaveBtn, async () => {
      const user = await fetchJSON(`${API_BASE}/users`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ display_name: displayName, pin }),
      });
      closeSheet(el.userDialog);
      await loadUsers(user.id);
      await startSession(await verifyPin(user.id, pin));
    });
  } catch (error) {
    el.userDialogError.textContent = error.message;
  }
});

// --- start -------------------------------------------------------------------------------------------------------

async function init() {
  el.ringProgress.style.strokeDasharray = `${RING_CIRCUMFERENCE}`;
  el.ringProgress.style.strokeDashoffset = `${RING_CIRCUMFERENCE}`;
  const saved = readSession();
  showScreen(saved ? null : "lock");
  try {
    await loadUsers(saved?.userId ?? null);
  } catch (error) {
    showScreen("lock");
    el.authStatus.textContent = error.message;
    el.authStatus.className = "form-status error";
    return;
  }
  if (saved && state.userId === saved.userId) {
    // Wznowienie sesji po przeładowaniu karty - bez ponownego pytania o PIN.
    try {
      await startSession(saved);
      return registerServiceWorker();
    } catch (error) {
      // 401 już wylogował (lockUser). Inny błąd (np. chwilowy brak sieci) nie kasuje sesji.
      if (state.token) {
        showScreen("lock");
        el.authStatus.textContent = `${error.message} Odśwież stronę albo podaj PIN.`;
        el.authStatus.className = "form-status error";
        return registerServiceWorker();
      }
    }
  }
  showScreen("lock");
  el.pinInput.focus();
  registerServiceWorker();
}

function registerServiceWorker() {
  // Service worker działa tylko w bezpiecznym kontekście (https albo localhost).
  if ("serviceWorker" in navigator && window.isSecureContext) {
    navigator.serviceWorker.register("/sw.js").catch(() => {});
  }
}

init();
