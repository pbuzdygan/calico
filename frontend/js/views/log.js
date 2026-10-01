import { api } from "../api.js";
import { MEAL_GROUP_LABELS, MEAL_TYPES, MEASUREMENT_FIELD } from "../config.js";
import { openActionSheet, openEntrySheet } from "../entry-sheet.js";
import { refreshAfterChange } from "../nav.js";
import { el, state } from "../state.js";
import { toast, toastError, withBusy } from "../ui.js";
import { addDaysISO, addMonthsISO, daysBetween, escapeHtml, fmt, formatDayLabel, formatLongDay, icon, monthEndISO, monthStartISO, parseISO, plural, todayISO } from "../util.js";

// --- Dziennik -------------------------------------------------------------------------------------

export async function loadLog(date = state.logDate) {
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

export function entryValueText(entry) {
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

