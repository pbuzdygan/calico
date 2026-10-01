import { api, fetchJSON, userHeaders } from "./api.js";
import { API_BASE, ENTRY_HINTS, FIELD_LABELS, MACRO_FIELDS, MEASUREMENT_FIELD, TEXT_TEMPLATES, TYPE_LABELS } from "./config.js";
import { t } from "./i18n.js";
import { refreshAfterChange } from "./nav.js";
import { el, state } from "./state.js";
import { closeSheet, openSheet, toast, toastError, withBusy } from "./ui.js";
import { addDaysISO, defaultMealType, formatDayLabel, inputNumber, parseNumberInput, todayISO } from "./util.js";
import { entryValueText } from "./views/log.js";

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
  el.entryHint.textContent = ENTRY_HINTS[type] ? t(ENTRY_HINTS[type]) : "";
  if (state.entrySheet.mode === "add") {
    el.entrySheetTitle.textContent =
      type === "weight" ? t("Dodaj wagę") : type === "waist" ? t("Dodaj pomiar pasa") : type === "daily_balance" ? t("Dodaj bilans dnia") : t("Dodaj posiłek");
  }
}

function setEntryMode(mode) {
  el.entryModeSwitch.querySelectorAll(".seg").forEach((button) => button.classList.toggle("active", button.dataset.mode === mode));
  el.entryForm.hidden = mode !== "form";
  el.textForm.hidden = mode !== "text";
  if (mode === "text") {
    el.entrySheetTitle.textContent = t("Szybki wpis tekstowy");
    if (!el.messageInput.value.trim()) el.messageInput.value = t(TEXT_TEMPLATES[state.entryType]);
    el.textStatus.textContent = "";
  } else {
    setSheetType(state.entryType);
  }
}

export function openEntrySheet({ mode, type, date, entry }) {
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
  el.entrySaveBtn.textContent = editing ? t("Zapisz zmiany") : t("Zapisz");
  if (editing) {
    el.entrySheetTitle.textContent = t("Edytuj: {label}", { label: entry.entry_label });
    [...MACRO_FIELDS, "weight_kg", "waist_cm"].forEach((field) => {
      const input = el.entryForm.querySelector(`[name="${field}"]`);
      if (input && entry[field] !== null && entry[field] !== undefined) input.value = inputNumber(entry[field]);
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
      throw new Error(t("Uzupełnij pole: {field}.", { field: t(FIELD_LABELS[field]) }));
    }
    if (Number.isNaN(value) || value < 0) {
      input.focus();
      throw new Error(t("{field}: podaj liczbę nieujemną, np. 82,4.", { field: t(FIELD_LABELS[field]) }));
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
        toast(t("Zapisano zmiany."), "success", 3000);
      } else {
        const date = el.entryDate.value || todayISO();
        await api(`/days/${date}/entries`, { method: "POST", body: values });
        toast(t("Zapisano: {label} ({date}).", { label: t(TYPE_LABELS[state.entryType]), date: formatDayLabel(date) }), "success", 3500);
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
  el.messageInput.value = t(TEXT_TEMPLATES[state.entryType]);
  el.messageInput.focus();
});

el.addFoodBtn.addEventListener("click", () => openEntrySheet({ mode: "add", type: defaultMealType() }));
[el.weightCard, el.waistCard].forEach((card) => card.addEventListener("click", () => openEntrySheet({ mode: "add", type: card.dataset.measure })));

// --- akcje pozycji: edytuj / duplikuj / przenieś / usuń ---------------------------------------------------

export function openActionSheet(entry) {
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
    if (!confirm(t("Usunąć pozycję „{label}” z dnia {date}?", { label: entry.entry_label, date: formatDayLabel(entry.log_date) }))) return;
    try {
      await api(`/days/${entry.log_date}/entries/${entry.id}`, { method: "DELETE" });
      toast(t("Usunięto: {label}.", { label: entry.entry_label }), "success", 3500);
      await refreshAfterChange();
    } catch (error) {
      toastError(error);
    }
  }
});

function openDateSheet(entry, mode) {
  state.dateContext = { entry, mode };
  const isMove = mode === "move";
  el.dateSheetTitle.textContent = isMove ? t("Przenieś wpis") : t("Duplikuj wpis");
  el.dateSheetCopy.textContent = t("{label} – {value}, z dnia {date}.", { label: entry.entry_label, value: entryValueText(entry), date: formatDayLabel(entry.log_date) });
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
    el.dateSheetError.textContent = t("Wybierz dzień.");
    return;
  }
  try {
    await withBusy(el.dateSheetSaveBtn, async () => {
      await api(`/days/${entry.log_date}/entries/${entry.id}/${mode}`, { method: "POST", body: { target_date: targetDate } });
      closeSheet(el.dateSheet);
      const params = { date: formatDayLabel(targetDate) };
      toast(mode === "move" ? t("Przeniesiono wpis do dnia {date}.", params) : t("Zduplikowano wpis do dnia {date}.", params), "success", 4000);
      if (state.view === "log" && mode === "move") state.logDate = targetDate;
      await refreshAfterChange();
    });
  } catch (error) {
    el.dateSheetError.textContent = error.message;
  }
});

