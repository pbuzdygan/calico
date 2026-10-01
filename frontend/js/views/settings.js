import { api, fetchJSON, profileApi, saveSession, userHeaders } from "../api.js";
import { loadUsers, lockUser, loginMeta, pinRuleText } from "../auth.js";
import { API_BASE } from "../config.js";
import { N_, t } from "../i18n.js";
import { openOnboarding, updateGoalDeltaUi } from "../profile-form.js";
import { $, el, state } from "../state.js";
import { toast, toastError, withBusy } from "../ui.js";
import { escapeHtml, fmt, formatDayLabel, inputNumber, parseNumberInput, plural } from "../util.js";

// --- Ustawienia: profil, PIN, eksport/import, konto ------------------------------------------------------------

export async function loadSettings() {
  const profile = await profileApi();
  if (!profile.is_complete) {
    openOnboarding();
    return;
  }
  const form = el.profileForm;
  form.sex.value = profile.sex;
  form.age.value = profile.age;
  form.height_cm.value = inputNumber(profile.height_cm);
  form.weight_kg.value = inputNumber(profile.weight_kg);
  form.activity_level.value = profile.activity_level;
  form.goal_type.value = profile.goal_type;
  form.goal_delta_pct_percent.value = Math.round((profile.goal_delta_pct || 0) * 100);
  updateGoalDeltaUi(form);
  el.profileStatus.textContent = "";
  el.profileTarget.textContent = `${fmt(profile.daily_kcal_target)} ${t("kcal/dzień")}`;
  const since = profile.plan_started_on ? ` ${t("Plan od {date}.", { date: formatDayLabel(profile.plan_started_on) })}` : "";
  el.profileCurrentWeight.textContent =
    profile.current_weight_kg !== null && profile.current_weight_kg !== undefined
      ? t("Aktualna waga: {value} kg ({date}).", { value: fmt(profile.current_weight_kg, 1), date: formatDayLabel(profile.current_weight_date) }) + since
      : t("Brak pomiarów wagi.") + since;
}

export function readProfilePayload(form) {
  const choices = [
    ["sex", N_("Płeć")],
    ["activity_level", N_("Aktywność")],
    ["goal_type", N_("Cel")],
  ];
  for (const [key, label] of choices) {
    if (!form[key].value) return { error: t("{label}: wybierz wartość.", { label: t(label) }) };
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
    ["age", 10, 100, N_("Wiek")],
    ["height_cm", 120, 230, N_("Wzrost")],
    ["weight_kg", 30, 300, N_("Waga")],
    ["goal_delta_pct", 0, 0.3, N_("Korekta celu")],
  ];
  for (const [key, min, max, label] of rules) {
    const value = payload[key];
    if (value === null || Number.isNaN(value) || value < min || value > max) {
      const range = key === "goal_delta_pct" ? "0–30%" : `${min}–${max}`;
      return { error: t("{label}: podaj wartość z zakresu {range}.", { label: t(label), range }) };
    }
  }
  if (payload.age !== Math.round(payload.age)) return { error: t("Wiek: podaj pełną liczbę lat.") };
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
      await loadSettings();
      el.profileStatus.textContent = t("Zapisano profil – utworzono nowy plan kaloryczny.");
      el.profileStatus.className = "form-status span-2 success";
    });
  } catch (error) {
    el.profileStatus.textContent = error.message;
    el.profileStatus.className = "form-status span-2 error";
  }
});

el.pinChangeForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const currentPin = el.currentPinInput.value.trim();
  const newPin = el.newPinInput.value.trim();
  if (!/^\d{4,8}$/.test(currentPin)) {
    toast(t("Podaj obecny PIN."), "error");
    el.currentPinInput.focus();
    return;
  }
  if (!new RegExp(`^\\d{${loginMeta.pinMinLength},8}$`).test(newPin)) {
    toast(pinRuleText(), "error");
    return;
  }
  try {
    await withBusy(event.submitter, async () => {
      // Zmiana PIN-u wymaga obecnego PIN-u (przejęta sesja nie wystarczy) i unieważnia stare tokeny - serwer zwraca nowy.
      const changed = await fetchJSON(`${API_BASE}/users/${state.userId}/pin`, {
        method: "POST",
        headers: userHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({ current_pin: currentPin, new_pin: newPin }),
      });
      state.token = changed.token;
      state.tokenExpiresAt = changed.expires_at;
      saveSession();
      el.pinChangeForm.reset();
      toast(t("PIN został zmieniony."), "success");
    });
  } catch (error) {
    toastError(error);
  }
});

// --- eksport / import "wiersz = dzień" (D11) ---------------------------------------------------------

const IMPORT_MAX_BYTES = 1_000_000;

async function downloadCsv(path, fallbackName) {
  const response = await fetch(`${API_BASE}${path}?user_id=${state.userId}`, { headers: userHeaders() });
  if (!response.ok) throw new Error(t("Pobieranie nie powiodło się ({status}).", { status: response.status }));
  const blob = await response.blob();
  const match = /filename="([^"]+)"/.exec(response.headers.get("Content-Disposition") || "");
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = match ? match[1] : fallbackName;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(link.href), 1000);
}

function renderImportResult(result) {
  if (result.error_count) {
    const hidden = result.error_count - result.errors.length;
    const more = hidden > 0 ? `<li>${escapeHtml(t("… i {count} więcej", { count: hidden }))}</li>` : "";
    const summary = t("Nic nie zaimportowano – popraw {count} {rows} i spróbuj ponownie.", {
      count: result.error_count,
      rows: plural(result.error_count, "wiersz", "wiersze", "wierszy"),
    });
    const rows = result.errors.map((error) => `<li>${escapeHtml(t("Wiersz {row}: {message}", { row: error.row, message: error.message }))}</li>`).join("");
    el.importResult.innerHTML = `<p class="form-status error">${escapeHtml(summary)}</p><ul class="notes">${rows}${more}</ul>`;
    return;
  }
  const parts = [
    t("Zaimportowano {days} {daysWord} ({entries} {entriesWord}).", {
      days: result.imported_days,
      daysWord: plural(result.imported_days, "dzień", "dni", "dni"),
      entries: result.imported_entries,
      entriesWord: plural(result.imported_entries, "wpis", "wpisy", "wpisów"),
    }),
  ];
  if (result.skipped_dates.length) {
    parts.push(
      t("Pominięto {count} {days} z istniejącymi wpisami: {dates}.", {
        count: result.skipped_dates.length,
        days: plural(result.skipped_dates.length, "dzień", "dni", "dni"),
        dates: result.skipped_dates.map(formatDayLabel).join(", "),
      })
    );
  }
  el.importResult.innerHTML = `<p class="form-status success">${escapeHtml(parts.join(" "))}</p>`;
  if (result.earliest_imported_date) {
    // Dane sprzed startu planu: ocena planu i "zmiana od startu" ich nie obejmują, dopóki start nie zostanie przesunięty.
    const hint = t("Zaimportowane dane sięgają {date} – wcześniej niż start planu ({start}). Jeśli realizujesz plan od tamtej pory, zmień datę startu w Celach.", {
      date: formatDayLabel(result.earliest_imported_date),
      start: formatDayLabel(result.plan_started_on),
    });
    el.importResult.innerHTML += `<p class="hint">${escapeHtml(hint)} <a href="#/goals">${escapeHtml(t("Przejdź do Celów"))}</a></p>`;
  }
  toast(parts[0], "success");
}

el.exportBtn.addEventListener("click", () => withBusy(el.exportBtn, () => downloadCsv("/export", "calico.csv")).catch(toastError));

el.templateBtn.addEventListener("click", () =>
  withBusy(el.templateBtn, () => downloadCsv("/import/template", t("calico-szablon-importu.csv"))).catch(toastError)
);

el.importBtn.addEventListener("click", () => {
  el.importFile.value = "";
  el.importFile.click();
});

el.importFile.addEventListener("change", () => {
  const file = el.importFile.files[0];
  if (!file) return;
  el.importResult.innerHTML = "";
  if (file.size > IMPORT_MAX_BYTES) {
    el.importResult.innerHTML = `<p class="form-status error">${escapeHtml(t("Plik jest za duży (maks. 1 MB)."))}</p>`;
    return;
  }
  withBusy(el.importBtn, async () => {
    const content = await file.text();
    renderImportResult(await api("/import", { method: "POST", body: { content } }));
  }).catch((error) => {
    el.importResult.innerHTML = `<p class="form-status error">${escapeHtml(error.message)}</p>`;
  });
});

el.navLogoutBtn.addEventListener("click", () => {
  location.hash = "";
  lockUser();
});

el.deleteUserBtn.addEventListener("click", async () => {
  if (!confirm(t("Usunąć konto „{name}” razem ze wszystkimi wpisami? Tej operacji nie można cofnąć.", { name: state.userName }))) return;
  try {
    await withBusy(el.deleteUserBtn, async () => {
      await fetchJSON(`${API_BASE}/users/${state.userId}`, { method: "DELETE", headers: userHeaders() });
      location.hash = "";
      lockUser();
      await loadUsers();
      toast(t("Konto zostało usunięte."), "success");
    });
  } catch (error) {
    toastError(error);
  }
});

