const API_BASE = "/api";

const TEMPLATES = {
  weight: "Waga:\nWaga: 82.4 kg",
  waist: "Obwod pasa:\nObwod pasa: 91 cm",
  breakfast: "Sniadanie\nIlosc kalorii: 540\nWeglowodany: 48\nTluszcze: 18\nBialko: 32",
  lunch: "Obiad\nIlosc kalorii: 720\nWeglowodany: 62\nTluszcze: 24\nBialko: 45",
  dinner: "Kolacja\nIlosc kalorii: 610\nWeglowodany: 40\nTluszcze: 22\nBialko: 38",
  snack: "Przekaska\nIlosc kalorii: 240\nWeglowodany: 20\nTluszcze: 10\nBialko: 12",
  daily_balance: "Bilans dnia\nIlosc kalorii: 2150\nWeglowodany: 210\nTluszcze: 70\nBialko: 145",
};

const userSelect = document.getElementById("userSelect");
const newUserBtn = document.getElementById("newUserBtn");
const pinInput = document.getElementById("pinInput");
const unlockBtn = document.getElementById("unlockBtn");
const unlockToggleBtn = document.getElementById("unlockToggleBtn");
const pinPopover = document.getElementById("pinPopover");
const authStatus = document.getElementById("authStatus");
const deleteUserBtn = document.getElementById("deleteUserBtn");

const tabButtons = Array.from(document.querySelectorAll(".tab-btn"));
const tabPanels = Array.from(document.querySelectorAll(".tab-panel"));
const protectedPanels = Array.from(document.querySelectorAll(".user-protected-panel"));

const dayCaloriesCompactEl = document.getElementById("dayCaloriesCompact");
const carbsTotalEl = document.getElementById("carbsTotal");
const fatTotalEl = document.getElementById("fatTotal");
const proteinTotalEl = document.getElementById("proteinTotal");

const showBtn = document.getElementById("showBtn");
const undoBtn = document.getElementById("undoBtn");
const closeBtn = document.getElementById("closeBtn");
const clearDraftBtn = document.getElementById("clearDraftBtn");
const entryFeedback = document.getElementById("entryFeedback");

const templateButtons = Array.from(document.querySelectorAll(".template-btn"));
const chatForm = document.getElementById("chatForm");
const messageInput = document.getElementById("messageInput");
const miniReportChart = document.getElementById("miniReportChart");

const daySelect = document.getElementById("daySelect");
const refreshDayBtn = document.getElementById("refreshDayBtn");
const clearDayBtn = document.getElementById("clearDayBtn");
const journalMeta = document.getElementById("journalMeta");
const journalMeals = document.getElementById("journalMeals");

const reportPresetButtons = Array.from(document.querySelectorAll(".report-preset"));
const reportFromInput = document.getElementById("reportFrom");
const reportToInput = document.getElementById("reportTo");
const reportMonthInput = document.getElementById("reportMonth");
const reportRangeBtn = document.getElementById("reportRangeBtn");
const reportMonthBtn = document.getElementById("reportMonthBtn");
const metricAverage = document.getElementById("metricAverage");
const metricTotal = document.getElementById("metricTotal");
const metricAbove = document.getElementById("metricAbove");
const metricEntries = document.getElementById("metricEntries");
const reportChart = document.getElementById("reportChart");
const reportTable = document.getElementById("reportTable");

const profileForm = document.getElementById("profileForm");
const profileStatus = document.getElementById("profileStatus");
const goalTypeSelect = profileForm.goal_type;
const goalDeltaPercentInput = profileForm.goal_delta_pct_percent;
const profileSubmitBtn = profileForm.querySelector('button[type="submit"]');

const adminPinInput = document.getElementById("adminPinInput");
const adminUnlockBtn = document.getElementById("adminUnlockBtn");
const adminStatus = document.getElementById("adminStatus");
const adminUserSelect = document.getElementById("adminUserSelect");
const adminRefreshBtn = document.getElementById("adminRefreshBtn");
const adminLoadLogsBtn = document.getElementById("adminLoadLogsBtn");
const adminSummary = document.getElementById("adminSummary");
const adminLogs = document.getElementById("adminLogs");

let currentUserId = null;
let currentPin = "";
let selectedDay = todayISO();
let selectedTab = "chatPanel";
let currentReportDays = 7;
let isGoalDeltaTouched = false;
let latestReport = null;
let latestJournalDay = null;
let isSavingProfile = false;
let adminPin = "";
let adminEnabled = false;
let adminSummaries = [];
let activeTemplateKey = "breakfast";
let entryFeedbackTimer = null;

function todayISO() {
  return new Date().toISOString().slice(0, 10);
}

function toNumber(value, fallback = 0) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function suggestedGoalDeltaPercent(goalType) {
  if (goalType === "cut") return 15;
  if (goalType === "bulk") return 10;
  return 0;
}

function authHeaders(extra = {}) {
  if (!currentPin) return { ...extra };
  return { "X-User-PIN": currentPin, ...extra };
}

function adminHeaders(extra = {}) {
  if (!adminPin) return { ...extra };
  return { "X-Admin-PIN": adminPin, ...extra };
}

async function fetchJSON(url, options = {}) {
  const response = await fetch(url, options);
  if (!response.ok) {
    let payload = null;
    let detail = "";
    try {
      payload = await response.json();
    } catch {
      detail = await response.text();
    }
    throw new Error(formatApiError(payload, detail || "Request failed"));
  }
  return response.json();
}

function formatApiError(payload, fallback) {
  if (payload && Array.isArray(payload.detail)) {
    return payload.detail
      .map((entry) => {
        const field = Array.isArray(entry.loc) ? entry.loc[entry.loc.length - 1] : "";
        const label = fieldLabel(field);
        return label ? `${label}: ${entry.msg}` : entry.msg;
      })
      .join(" ");
  }
  if (payload && typeof payload.detail === "string") {
    return payload.detail;
  }
  return fallback;
}

function fieldLabel(fieldName) {
  const map = {
    age: "Wiek",
    height_cm: "Wzrost",
    weight_kg: "Waga",
    goal_delta_pct: "Korekta celu",
  };
  return map[fieldName] || "";
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function setAuthText(text) {
  authStatus.textContent = text;
}

function openPinPopover() {
  pinPopover.classList.remove("is-hidden");
  pinInput.focus({ preventScroll: true });
}

function closePinPopover() {
  pinPopover.classList.add("is-hidden");
}

function setProfileStatus(text, variant = "") {
  profileStatus.textContent = text;
  profileStatus.className = "form-status";
  if (variant) profileStatus.classList.add(variant);
}

function setAdminStatus(text, variant = "") {
  adminStatus.textContent = text;
  adminStatus.className = "form-status";
  if (variant) adminStatus.classList.add(variant);
}

function setEmptyState(target, text) {
  target.innerHTML = `<div class="empty-state">${escapeHtml(text)}</div>`;
}

function hideEntryFeedback() {
  if (entryFeedbackTimer) {
    clearTimeout(entryFeedbackTimer);
    entryFeedbackTimer = null;
  }
  entryFeedback.textContent = "";
  entryFeedback.className = "entry-feedback is-hidden";
}

function showEntryFeedback(text, variant = "info", autoHideMs = 4200) {
  if (entryFeedbackTimer) {
    clearTimeout(entryFeedbackTimer);
    entryFeedbackTimer = null;
  }
  entryFeedback.textContent = text;
  entryFeedback.className = `entry-feedback ${variant}`;
  if (autoHideMs > 0) {
    entryFeedbackTimer = setTimeout(() => {
      hideEntryFeedback();
    }, autoHideMs);
  }
}

function setActiveTemplate(key) {
  activeTemplateKey = key;
  templateButtons.forEach((button) => {
    button.classList.toggle("active", button.dataset.template === key);
  });
}

function insertTemplate(key) {
  setActiveTemplate(key);
  messageInput.value = TEMPLATES[key];
}

function focusTemplateInput() {
  messageInput.focus({ preventScroll: true });
}

function setPanelLocked(panel, locked, message) {
  panel.classList.toggle("is-locked", locked);
  const lockCopy = panel.querySelector(".lock-copy");
  if (lockCopy && message) {
    lockCopy.textContent = message;
  }
  panel.querySelectorAll(".lockable-body button, .lockable-body input, .lockable-body textarea, .lockable-body select").forEach((control) => {
    control.disabled = locked;
  });
}

function applyUserLockState(locked, message = "Podaj PIN, aby odblokowac dane uzytkownika.") {
  protectedPanels.forEach((panel) => setPanelLocked(panel, locked, message));
}

function clearOperatorSummary() {
  dayCaloriesCompactEl.textContent = "-";
  carbsTotalEl.textContent = "-";
  fatTotalEl.textContent = "-";
  proteinTotalEl.textContent = "-";
}

function resetProfileFormToDefaults() {
  profileForm.reset();
  goalDeltaPercentInput.value = suggestedGoalDeltaPercent(goalTypeSelect.value);
  isGoalDeltaTouched = false;
}

function clearUserDataViews(message = "Wybierz uzytkownika i podaj PIN, aby odblokowac dane.") {
  latestReport = null;
  latestJournalDay = null;
  clearOperatorSummary();
  journalMeta.textContent = "Brak danych dnia.";
  setEmptyState(journalMeals, message);
  reportChart.innerHTML = `<div class="empty-state">${escapeHtml(message)}</div>`;
  reportTable.innerHTML = "";
  metricAverage.textContent = "-";
  metricTotal.textContent = "-";
  metricAbove.textContent = "-";
  metricEntries.textContent = "-";
  miniReportChart.innerHTML = `<div class="empty-state">${escapeHtml(message)}</div>`;
  daySelect.innerHTML = "";
  hideEntryFeedback();
  setProfileStatus("");
  resetProfileFormToDefaults();
  messageInput.value = TEMPLATES[activeTemplateKey];
  closePinPopover();
}

function resetUiForNoUsers() {
  currentUserId = null;
  currentPin = "";
  selectedDay = todayISO();
  pinInput.value = "";
  userSelect.innerHTML = "";
  const placeholder = document.createElement("option");
  placeholder.value = "";
  placeholder.textContent = "Brak userow - utworz nowego usera";
  placeholder.selected = true;
  userSelect.appendChild(placeholder);
  clearUserDataViews("Brak userow. Utworz nowe konto, aby rozpoczac prace.");
  applyUserLockState(true, "Brak aktywnego uzytkownika. Utworz konto i odblokuj je PIN-em.");
}

function formatDayLabel(isoDate) {
  if (!isoDate) return "-";
  const [year, month, day] = isoDate.split("-");
  return `${day}.${month}.${year}`;
}

function setActiveTab(tabId) {
  selectedTab = tabId;
  tabButtons.forEach((button) => {
    button.classList.toggle("active", button.dataset.tab === tabId);
  });
  tabPanels.forEach((panel) => {
    panel.classList.toggle("active", panel.id === tabId);
  });
}

function renderAdminSummaryList(summaries) {
  adminSummaries = summaries;
  adminUserSelect.innerHTML = "";
  if (!summaries.length) {
    adminUserSelect.innerHTML = '<option value="">Brak logow userow</option>';
    adminSummary.textContent = "Brak danych diagnostycznych dla aktywnych userow.";
    adminLogs.innerHTML = "";
    return;
  }
  summaries.forEach((summary) => {
    const option = document.createElement("option");
    option.value = String(summary.user_id);
    option.textContent = `${summary.display_name} (${summary.entries_count})`;
    adminUserSelect.appendChild(option);
  });
  const first = summaries[0];
  adminUserSelect.value = String(first.user_id);
  adminSummary.textContent = `${first.display_name} | wpisy diagnostyczne: ${first.entries_count} | ostatni zapis: ${first.last_event_at || "-"}`;
}

function renderAdminLogs(entries) {
  if (!entries.length) {
    adminLogs.innerHTML = `<div class="admin-log-entry">Brak wpisow diagnostycznych dla wybranego usera.</div>`;
    return;
  }
  adminLogs.innerHTML = entries
    .map((entry) => {
      const responsePreview = entry.response ? JSON.stringify(entry.response, null, 2) : "";
      const errorPreview = entry.error ? `\nBlad:\n${entry.error}` : "";
      return `
        <article class="admin-log-entry">
          <div class="report-top">
            <h3>${escapeHtml(entry.display_name)}</h3>
            <strong>${escapeHtml(entry.timestamp)}</strong>
          </div>
          <p><strong>Wiadomosc:</strong> ${escapeHtml(entry.user_message)}</p>
          <div class="meta-line">Wynik: ${escapeHtml(entry.outcome)}</div>
          <pre>${escapeHtml(responsePreview + errorPreview)}</pre>
        </article>
      `;
    })
    .join("");
}

async function refreshAdminStatus() {
  const status = await fetchJSON(`${API_BASE}/admin/status`);
  adminEnabled = Boolean(status.enabled);
  if (!adminEnabled) {
    setAdminStatus("Tryb administracyjny jest wylaczony. Ustaw ADMIN_PIN w .env.", "error");
    adminUserSelect.innerHTML = "";
    adminLogs.innerHTML = "";
    adminSummary.textContent = "Admin mode disabled.";
    return;
  }
  if (!adminPin) {
    setAdminStatus("Podaj ADMIN_PIN, aby odblokowac panel administracyjny.");
  }
}

async function loadAdminSummaries() {
  if (!adminEnabled) return;
  const summaries = await fetchJSON(`${API_BASE}/admin/diagnostics/users`, { headers: adminHeaders() });
  renderAdminSummaryList(summaries);
}

async function loadAdminLogs() {
  if (!adminEnabled || !adminPin || !adminUserSelect.value) return;
  const userId = adminUserSelect.value;
  const entries = await fetchJSON(`${API_BASE}/admin/diagnostics/logs?user_id=${userId}&limit=200`, { headers: adminHeaders() });
  const summary = adminSummaries.find((item) => String(item.user_id) === String(userId));
  if (summary) {
    adminSummary.textContent = `${summary.display_name} | wpisy diagnostyczne: ${summary.entries_count} | ostatni zapis: ${summary.last_event_at || "-"}`;
  }
  renderAdminLogs(entries);
}

function ensureUnlocked() {
  if (!currentUserId || !currentPin) {
    throw new Error("Najpierw odblokuj uzytkownika PIN-em.");
  }
}

function updateSummaryCards(summary, entriesCount) {
  const total = Math.round(toNumber(summary.total_kcal));
  const target = Math.round(toNumber(summary.target_kcal));
  const carbs = Math.round(toNumber(summary.total_carbs_g));
  const fat = Math.round(toNumber(summary.total_fat_g));
  const protein = Math.round(toNumber(summary.total_protein_g));

  dayCaloriesCompactEl.textContent = `${total} / ${target}`;
  carbsTotalEl.textContent = `${carbs} g`;
  fatTotalEl.textContent = `${fat} g`;
  proteinTotalEl.textContent = `${protein} g`;
}

function parseDecimalField(value) {
  const normalized = String(value).trim().replace(",", ".");
  const parsed = Number(normalized);
  return Number.isFinite(parsed) ? parsed : NaN;
}

function buildProfilePayload() {
  return {
    sex: profileForm.sex.value,
    age: parseDecimalField(profileForm.age.value),
    height_cm: parseDecimalField(profileForm.height_cm.value),
    weight_kg: parseDecimalField(profileForm.weight_kg.value),
    activity_level: profileForm.activity_level.value,
    goal_type: profileForm.goal_type.value,
    goal_delta_pct: parseDecimalField(goalDeltaPercentInput.value) / 100,
  };
}

function validateProfilePayload(payload) {
  const rules = [
    { key: "age", min: 10, max: 100, label: "Wiek" },
    { key: "height_cm", min: 120, max: 230, label: "Wzrost" },
    { key: "weight_kg", min: 30, max: 300, label: "Waga" },
    { key: "goal_delta_pct", min: 0, max: 0.3, label: "Korekta celu" },
  ];
  for (const rule of rules) {
    const value = payload[rule.key];
    if (!Number.isFinite(value)) {
      return `${rule.label}: podaj poprawna liczbe.`;
    }
    if (value < rule.min || value > rule.max) {
      if (rule.key === "goal_delta_pct") {
        return `${rule.label}: wartosc musi byc w zakresie 0-30%.`;
      }
      return `${rule.label}: wartosc musi byc w zakresie ${rule.min}-${rule.max}.`;
    }
  }
  return "";
}

function renderDaySelect(days) {
  const existing = new Map(days.map((day) => [day.log_date, day]));
  if (!existing.has(todayISO())) {
    days = [
      {
        log_date: todayISO(),
        status: "open",
        total_kcal: 0,
        target_kcal: 0,
        total_carbs_g: 0,
        total_fat_g: 0,
        total_protein_g: 0,
        balance_mode: false,
        user_id: currentUserId,
      },
      ...days,
    ];
  }
  daySelect.innerHTML = "";
  days.forEach((day) => {
    const option = document.createElement("option");
    option.value = day.log_date;
    const balanceSuffix = day.balance_mode ? " | bilans" : "";
    option.textContent = `${formatDayLabel(day.log_date)} (${Math.round(toNumber(day.total_kcal))} kcal${balanceSuffix})`;
    daySelect.appendChild(option);
  });
  if (!days.some((day) => day.log_date === selectedDay)) {
    selectedDay = todayISO();
  }
  daySelect.value = selectedDay;
}

function formatJournalEntryValue(entry) {
  if (entry.entry_type === "weight") {
    return `${entry.weight_kg?.toFixed(1) || "-"} kg`;
  }
  if (entry.entry_type === "waist") {
    return `${entry.waist_cm?.toFixed(1) || "-"} cm`;
  }
  return `${Math.round(toNumber(entry.kcal))} kcal | W ${Math.round(toNumber(entry.carbs_g))} g | T ${Math.round(toNumber(entry.fat_g))} g | B ${Math.round(toNumber(entry.protein_g))} g`;
}

function renderJournal(dayDetail) {
  latestJournalDay = dayDetail;
  const balanceNote = dayDetail.balance_mode ? " | aktywny bilans dnia" : "";
  journalMeta.textContent = `${formatDayLabel(dayDetail.log_date)} | ${dayDetail.entries.length} pozycji | ${Math.round(dayDetail.total_kcal)} kcal / cel ${Math.round(dayDetail.target_kcal)} kcal | W ${Math.round(dayDetail.total_carbs_g)} g | T ${Math.round(dayDetail.total_fat_g)} g | B ${Math.round(dayDetail.total_protein_g)} g${balanceNote}`;

  if (dayDetail.entries.length === 0) {
    setEmptyState(journalMeals, "Brak pozycji w tym dniu.");
    return;
  }
  journalMeals.innerHTML = dayDetail.entries
    .map(
      (entry) => `
        <article class="meal-item" data-entry-id="${entry.id}">
          <div class="meal-top">
            <h3>#${entry.position} ${escapeHtml(entry.entry_label)}</h3>
            <strong>${escapeHtml(formatJournalEntryValue(entry))}</strong>
          </div>
          <pre>${escapeHtml(entry.source_text)}</pre>
          <div class="meal-actions">
            <button class="ghost meal-action" data-action="edit" type="button">Edytuj</button>
            <button class="ghost meal-action" data-action="delete" type="button">Usun</button>
          </div>
        </article>
      `
    )
    .join("");
}

function renderMiniReport(points) {
  if (!Array.isArray(points) || !points.length) {
    miniReportChart.innerHTML = `<div class="empty-state">Brak danych w raporcie.</div>`;
    return;
  }

  const recentPoints = points.slice(-7);
  let maxValue = 1;
  recentPoints.forEach((point) => {
    maxValue = Math.max(maxValue, toNumber(point.total_kcal), toNumber(point.target_kcal));
  });

  miniReportChart.innerHTML = recentPoints
    .map((point) => {
      const totalHeight = Math.max(8, Math.round((toNumber(point.total_kcal) / maxValue) * 120));
      const targetHeight = Math.max(8, Math.round((toNumber(point.target_kcal) / maxValue) * 120));
      return `
        <div class="mini-bar">
          <div class="mini-bar-track">
            <span class="mini-bar-fill" style="height:${totalHeight}px"></span>
            <span class="mini-bar-target" style="bottom:${targetHeight}px"></span>
          </div>
          <small>${escapeHtml(point.log_date.slice(5))}</small>
        </div>
      `;
    })
    .join("");
}

function renderReport(report) {
  latestReport = report;
  metricAverage.textContent = `${Math.round(report.average_kcal)} kcal`;
  metricTotal.textContent = `${Math.round(report.total_kcal)} kcal`;
  metricAbove.textContent = String(report.above_target_days);
  metricEntries.textContent = String(report.entries_count);
  renderMiniReport(report.points);

  reportChart.innerHTML = "";
  if (!Array.isArray(report.points) || report.points.length === 0) {
    reportChart.innerHTML = `<div class="empty-state">Brak danych w wybranym zakresie.</div>`;
    reportTable.innerHTML = "";
    return;
  }

  let maxValue = 1;
  report.points.forEach((point) => {
    maxValue = Math.max(maxValue, toNumber(point.total_kcal), toNumber(point.target_kcal));
  });

  report.points.forEach((point) => {
    const totalHeight = Math.max(6, Math.round((toNumber(point.total_kcal) / maxValue) * 130));
    const barCol = document.createElement("div");
    barCol.className = "bar-col";
    barCol.innerHTML = `<div class="bar" style="height:${totalHeight}px"></div><small>${escapeHtml(point.log_date.slice(5))}</small>`;
    reportChart.appendChild(barCol);
  });

  reportTable.innerHTML = report.points
    .map(
      (point) => `
        <article class="report-row">
          <div class="report-top">
            <h3>${escapeHtml(formatDayLabel(point.log_date))}</h3>
            <strong>${Math.round(point.total_kcal)} / ${Math.round(point.target_kcal)} kcal</strong>
          </div>
          <p>W ${Math.round(point.total_carbs_g)} g | T ${Math.round(point.total_fat_g)} g | B ${Math.round(point.total_protein_g)} g | wpisy: ${point.entries}</p>
        </article>
      `
    )
    .join("");
}

async function loadUsers() {
  const users = await fetchJSON(`${API_BASE}/users`);
  if (!users.length) {
    resetUiForNoUsers();
    setAuthText("Brak userow. Utworz nowego usera.");
    return;
  }
  userSelect.innerHTML = "";
  users.forEach((user) => {
    const option = document.createElement("option");
    option.value = user.id;
    option.textContent = user.display_name;
    userSelect.appendChild(option);
  });
  currentUserId = users[0].id;
  userSelect.value = String(currentUserId);
  currentPin = "";
  selectedDay = todayISO();
  pinInput.value = "";
  clearUserDataViews("Podaj PIN, aby odblokowac dane wybranego uzytkownika.");
  applyUserLockState(true, "Dane sa ukryte do czasu poprawnej weryfikacji PIN-u.");
  setAuthText("Wpisz PIN i kliknij Odblokuj.");
}

async function refreshProfile() {
  ensureUnlocked();
  const profile = await fetchJSON(`${API_BASE}/profile/${currentUserId}`, { headers: authHeaders() });
  profileForm.sex.value = profile.sex;
  profileForm.age.value = profile.age;
  profileForm.height_cm.value = profile.height_cm;
  profileForm.weight_kg.value = profile.weight_kg;
  profileForm.activity_level.value = profile.activity_level;
  profileForm.goal_type.value = profile.goal_type;
  goalDeltaPercentInput.value = Math.round((profile.goal_delta_pct || 0) * 100);
  isGoalDeltaTouched = false;
  setProfileStatus("");
}

async function fetchDayDetail(logDate) {
  ensureUnlocked();
  return fetchJSON(`${API_BASE}/days/${logDate}?user_id=${currentUserId}`, { headers: authHeaders() });
}

async function loadDeckDay() {
  const dayDetail = await fetchDayDetail(todayISO());
  updateSummaryCards(dayDetail, dayDetail.entries.length);
}

async function refreshDayOptions() {
  ensureUnlocked();
  const days = await fetchJSON(`${API_BASE}/days?user_id=${currentUserId}&limit=90`, { headers: authHeaders() });
  renderDaySelect(days);
}

async function loadJournalDay(logDate = selectedDay) {
  ensureUnlocked();
  selectedDay = logDate;
  const dayDetail = await fetchDayDetail(logDate);
  renderJournal(dayDetail);
}

async function loadReportSummary(days = 7) {
  ensureUnlocked();
  currentReportDays = days;
  const report = await fetchJSON(`${API_BASE}/reports/summary?user_id=${currentUserId}&days=${days}`, { headers: authHeaders() });
  renderReport(report);
}

async function loadReportRange() {
  ensureUnlocked();
  if (!reportFromInput.value || !reportToInput.value) {
    throw new Error("Podaj date od i do.");
  }
  const report = await fetchJSON(`${API_BASE}/reports/range?user_id=${currentUserId}&date_from=${reportFromInput.value}&date_to=${reportToInput.value}`, {
    headers: authHeaders(),
  });
  renderReport(report);
}

async function loadReportMonth() {
  ensureUnlocked();
  if (!reportMonthInput.value) {
    throw new Error("Podaj miesiac.");
  }
  const report = await fetchJSON(`${API_BASE}/reports/month?user_id=${currentUserId}&month=${reportMonthInput.value}`, {
    headers: authHeaders(),
  });
  renderReport(report);
}

async function refreshAllUnlockedContext() {
  ensureUnlocked();
  applyUserLockState(false);
  await refreshDayOptions();
  await loadDeckDay();
  await loadJournalDay(selectedDay);
  await refreshProfile();
  await loadReportSummary(currentReportDays);
}

async function postJournalAction(path, method = "POST", body = null) {
  ensureUnlocked();
  await fetchJSON(path, {
    method,
    headers: authHeaders(body ? { "Content-Type": "application/json" } : {}),
    body: body ? JSON.stringify(body) : undefined,
  });
  await refreshDayOptions();
  await loadDeckDay();
  await loadJournalDay(selectedDay);
  if (selectedTab === "reportsPanel") {
    await loadReportSummary(currentReportDays);
  }
}

async function sendChat(message) {
  ensureUnlocked();
  const normalizedMessage = message.trim().toLowerCase();
  const data = await fetchJSON(`${API_BASE}/chat/message`, {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ user_id: currentUserId, message }),
  });
  showEntryFeedback(data.reply, "success", 5200);
  if (Array.isArray(data.warnings) && data.warnings.length) {
    showEntryFeedback(`${data.reply}\n\nUwaga: ${data.warnings.join(" ")}`, "warning", 7200);
  }
  if (!["pokaz dzis", "podsumuj dzien", "cofnij ostatni"].includes(normalizedMessage)) {
    selectedDay = data.log_date;
  }
  await refreshDayOptions();
  await loadDeckDay();
  if (selectedDay === data.log_date || selectedTab === "journalPanel" || data.log_date === todayISO()) {
    await loadJournalDay(selectedDay);
  }
  if (selectedTab === "reportsPanel") {
    await loadReportSummary(currentReportDays);
  }
}

tabButtons.forEach((button) => {
  button.addEventListener("click", async () => {
    setActiveTab(button.dataset.tab);
    try {
      if (selectedTab === "adminPanel") {
        await refreshAdminStatus();
        if (adminEnabled && adminPin) {
          await loadAdminSummaries();
          await loadAdminLogs();
        }
      } else if (!currentPin) {
        return;
      } else if (selectedTab === "journalPanel") {
        await refreshDayOptions();
        await loadJournalDay(selectedDay);
      } else if (selectedTab === "reportsPanel") {
        await loadReportSummary(currentReportDays);
      } else if (selectedTab === "userPanel") {
        await refreshProfile();
      } else if (selectedTab === "chatPanel") {
        await loadDeckDay();
      }
    } catch (error) {
      showEntryFeedback(error.message, "error", 7200);
    }
  });
});

chatForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = messageInput.value.trim();
  if (!message) return;
  messageInput.value = "";
  try {
    await sendChat(message);
  } catch (error) {
    showEntryFeedback(error.message, "error", 7200);
  }
});

templateButtons.forEach((button) => {
  button.addEventListener("click", () => insertTemplate(button.dataset.template));
});

clearDraftBtn.addEventListener("click", () => {
  messageInput.value = TEMPLATES[activeTemplateKey];
  focusTemplateInput();
});

showBtn.addEventListener("click", async () => {
  try {
    await sendChat("pokaz dzis");
  } catch (error) {
    showEntryFeedback(error.message, "error", 7200);
  }
});

undoBtn.addEventListener("click", async () => {
  try {
    await sendChat("cofnij ostatni");
  } catch (error) {
    showEntryFeedback(error.message, "error", 7200);
  }
});

closeBtn.addEventListener("click", async () => {
  try {
    await sendChat("podsumuj dzien");
  } catch (error) {
    showEntryFeedback(error.message, "error", 7200);
  }
});

function handleUserSelectionChanged() {
  if (!userSelect.value) return;
  currentUserId = Number(userSelect.value);
  currentPin = "";
  pinInput.value = "";
  selectedDay = todayISO();
  clearUserDataViews("Podaj PIN, aby odblokowac dane wybranego uzytkownika.");
  applyUserLockState(true, "Dane sa ukryte do czasu poprawnej weryfikacji PIN-u.");
  setAuthText("Wpisz PIN i kliknij Odblokuj.");
}

userSelect.addEventListener("change", handleUserSelectionChanged);

newUserBtn.addEventListener("click", async () => {
  const displayName = prompt("Nazwa uzytkownika:");
  const pin = prompt("PIN 4-8 cyfr:");
  if (!displayName || !pin) return;
  try {
    await fetchJSON(`${API_BASE}/users`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ display_name: displayName, pin }),
    });
    await loadUsers();
    setAuthText("Nowy user dodany. Podaj PIN i kliknij Odblokuj.");
  } catch (error) {
    showEntryFeedback(error.message, "error", 7200);
  }
});

unlockToggleBtn.addEventListener("click", () => {
  if (!currentUserId) return;
  if (pinPopover.classList.contains("is-hidden")) {
    openPinPopover();
    return;
  }
  unlockBtn.click();
});

unlockBtn.addEventListener("click", async () => {
  if (!currentUserId) return;
  const pin = pinInput.value.trim();
  if (!/^\d{4,8}$/.test(pin)) {
    setAuthText("PIN musi miec 4-8 cyfr.");
    return;
  }
  try {
    await fetchJSON(`${API_BASE}/auth/verify`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: currentUserId, pin }),
    });
    currentPin = pin;
    closePinPopover();
    setAuthText("PIN poprawny. Uzytkownik odblokowany.");
    hideEntryFeedback();
    await refreshAllUnlockedContext();
    showEntryFeedback("Uzytkownik odblokowany. Dane zostaly zaladowane.", "success", 3200);
  } catch {
    currentPin = "";
    applyUserLockState(true, "Dane pozostaja ukryte do czasu poprawnej weryfikacji PIN-u.");
    clearUserDataViews("Niepoprawny PIN. Sprobuj ponownie.");
    setAuthText("Niepoprawny PIN.");
  }
});

pinInput.addEventListener("keydown", (event) => {
  if (event.key !== "Enter") return;
  event.preventDefault();
  unlockBtn.click();
});

document.addEventListener("click", (event) => {
  if (pinPopover.classList.contains("is-hidden")) return;
  if (pinPopover.contains(event.target) || unlockToggleBtn.contains(event.target)) return;
  closePinPopover();
});

daySelect.addEventListener("change", async () => {
  if (!currentPin) return;
  selectedDay = daySelect.value;
  try {
    await loadJournalDay(selectedDay);
  } catch (error) {
    showEntryFeedback(error.message, "error", 7200);
  }
});

refreshDayBtn.addEventListener("click", async () => {
  if (!currentPin) return;
  try {
    await refreshDayOptions();
    await loadJournalDay(selectedDay);
  } catch (error) {
    showEntryFeedback(error.message, "error", 7200);
  }
});

clearDayBtn.addEventListener("click", async () => {
  if (!currentPin) return;
  if (!confirm(`Wyczysc caly dzien ${formatDayLabel(selectedDay)}?`)) return;
  try {
    await postJournalAction(`${API_BASE}/days/${selectedDay}/clear?user_id=${currentUserId}`);
    showEntryFeedback(`Wyczyszczono dzien ${formatDayLabel(selectedDay)}.`, "success", 4200);
  } catch (error) {
    showEntryFeedback(error.message, "error", 7200);
  }
});

journalMeals.addEventListener("click", async (event) => {
  const trigger = event.target.closest(".meal-action");
  if (!trigger || !currentPin) return;
  const card = event.target.closest(".meal-item");
  if (!card) return;
  const entryId = Number(card.dataset.entryId);
  const action = trigger.dataset.action;
  if (!entryId || !action) return;
  try {
    if (action === "delete") {
      if (!confirm("Usunac pozycje?")) return;
      await postJournalAction(`${API_BASE}/days/${selectedDay}/entries/${entryId}?user_id=${currentUserId}`, "DELETE");
      showEntryFeedback(`Usunieto pozycje z dnia ${formatDayLabel(selectedDay)}.`, "success", 4200);
      return;
    }
    if (action === "edit") {
      const currentText = card.querySelector("pre")?.textContent || "";
      const sourceText = prompt("Nowa tresc pozycji:", currentText);
      if (!sourceText) return;
      await postJournalAction(`${API_BASE}/days/${selectedDay}/entries/${entryId}?user_id=${currentUserId}`, "PATCH", { source_text: sourceText });
      showEntryFeedback(`Zaktualizowano pozycje z dnia ${formatDayLabel(selectedDay)}.`, "success", 4200);
    }
  } catch (error) {
    showEntryFeedback(error.message, "error", 7200);
  }
});

reportPresetButtons.forEach((button) => {
  button.addEventListener("click", async () => {
    if (!currentPin) return;
    reportPresetButtons.forEach((preset) => preset.classList.toggle("active", preset === button));
    try {
      await loadReportSummary(Number(button.dataset.days));
    } catch (error) {
      showEntryFeedback(error.message, "error", 7200);
    }
  });
});

reportRangeBtn.addEventListener("click", async () => {
  if (!currentPin) return;
  try {
    await loadReportRange();
  } catch (error) {
    showEntryFeedback(error.message, "error", 7200);
  }
});

reportMonthBtn.addEventListener("click", async () => {
  if (!currentPin) return;
  try {
    await loadReportMonth();
  } catch (error) {
    showEntryFeedback(error.message, "error", 7200);
  }
});

goalTypeSelect.addEventListener("change", () => {
  if (isGoalDeltaTouched) return;
  goalDeltaPercentInput.value = suggestedGoalDeltaPercent(goalTypeSelect.value);
});

goalDeltaPercentInput.addEventListener("input", () => {
  isGoalDeltaTouched = true;
});

profileForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!currentPin || isSavingProfile) return;
  try {
    const payload = buildProfilePayload();
    const validationError = validateProfilePayload(payload);
    if (validationError) {
      setProfileStatus(validationError, "error");
      return;
    }
    isSavingProfile = true;
    profileSubmitBtn.disabled = true;
    setProfileStatus("Zapisywanie profilu...");
    await fetchJSON(`${API_BASE}/profile/${currentUserId}`, {
      method: "PUT",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify(payload),
    });
    await refreshAllUnlockedContext();
    setProfileStatus("Zapisalem profil i przeliczylem cel kcal.", "success");
    showEntryFeedback("Profil zapisany. Cel kcal zostal przeliczony ponownie.", "success", 4200);
  } catch (error) {
    setProfileStatus(`Blad: ${error.message}`, "error");
    showEntryFeedback(error.message, "error", 7200);
  } finally {
    isSavingProfile = false;
    profileSubmitBtn.disabled = false;
  }
});

deleteUserBtn.addEventListener("click", async () => {
  if (!currentPin || !currentUserId) return;
  const selectedName = userSelect.options[userSelect.selectedIndex]?.textContent || "tego usera";
  if (!confirm(`Usunac konto ${selectedName} razem z jego wpisami i historia?`)) return;
  try {
    await fetchJSON(`${API_BASE}/users/${currentUserId}`, {
      method: "DELETE",
      headers: authHeaders(),
    });
    await loadUsers();
    setAuthText(currentUserId ? "User usuniety. Wybierz konto i odblokuj PIN-em." : "Usunieto ostatnie konto. Utworz nowego usera.");
  } catch (error) {
    showEntryFeedback(error.message, "error", 7200);
  }
});

adminUnlockBtn.addEventListener("click", async () => {
  try {
    const candidate = adminPinInput.value.trim();
    if (!candidate) {
      setAdminStatus("Podaj ADMIN_PIN.", "error");
      return;
    }
    await fetchJSON(`${API_BASE}/admin/verify`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pin: candidate }),
    });
    adminPin = candidate;
    setAdminStatus("Panel administracyjny odblokowany.", "success");
    await loadAdminSummaries();
    await loadAdminLogs();
  } catch (error) {
    adminPin = "";
    setAdminStatus(`Blad: ${error.message}`, "error");
  }
});

adminPinInput.addEventListener("keydown", (event) => {
  if (event.key !== "Enter") return;
  event.preventDefault();
  adminUnlockBtn.click();
});

adminRefreshBtn.addEventListener("click", async () => {
  if (!adminPin) return;
  try {
    await loadAdminSummaries();
    await loadAdminLogs();
  } catch (error) {
    setAdminStatus(`Blad: ${error.message}`, "error");
  }
});

adminLoadLogsBtn.addEventListener("click", async () => {
  if (!adminPin) return;
  try {
    await loadAdminLogs();
  } catch (error) {
    setAdminStatus(`Blad: ${error.message}`, "error");
  }
});

document.addEventListener("DOMContentLoaded", async () => {
  setActiveTemplate(activeTemplateKey);
  insertTemplate(activeTemplateKey);
  window.scrollTo({ top: 0, left: 0, behavior: "auto" });
  clearUserDataViews("Wybierz uzytkownika i podaj PIN, aby odblokowac dane.");
  applyUserLockState(true, "Wybierz uzytkownika i podaj jego PIN, aby odblokowac dane.");
  try {
    await loadUsers();
    await refreshAdminStatus();
  } catch (error) {
    showEntryFeedback(error.message, "error", 7200);
  }
});
