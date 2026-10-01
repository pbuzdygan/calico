import { api, fetchJSON, profileApi, saveSession, userHeaders } from "../api.js";
import { loadUsers, lockUser } from "../auth.js";
import { API_BASE } from "../config.js";
import { openOnboarding, updateGoalDeltaUi } from "../profile-form.js";
import { $, el, state } from "../state.js";
import { toast, toastError, withBusy } from "../ui.js";
import { escapeHtml, fmt, formatDayLabel, parseNumberInput, plural } from "../util.js";

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

export function readProfilePayload(form) {
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
      await loadSettings();
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

// --- eksport / import "wiersz = dzień" (D11) ---------------------------------------------------------

const IMPORT_MAX_BYTES = 1_000_000;

async function downloadCsv(path, fallbackName) {
  const response = await fetch(`${API_BASE}${path}?user_id=${state.userId}`, { headers: userHeaders() });
  if (!response.ok) throw new Error(`Pobieranie nie powiodło się (${response.status}).`);
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
    const more = result.error_count > result.errors.length ? `<li>… i ${result.error_count - result.errors.length} więcej</li>` : "";
    el.importResult.innerHTML = `<p class="form-status error">Nic nie zaimportowano – popraw ${result.error_count} ${plural(result.error_count, "wiersz", "wiersze", "wierszy")} i spróbuj ponownie.</p>
      <ul class="notes">${result.errors.map((error) => `<li>Wiersz ${error.row}: ${escapeHtml(error.message)}</li>`).join("")}${more}</ul>`;
    return;
  }
  const parts = [`Zaimportowano ${result.imported_days} ${plural(result.imported_days, "dzień", "dni", "dni")} (${result.imported_entries} ${plural(result.imported_entries, "wpis", "wpisy", "wpisów")}).`];
  if (result.skipped_dates.length) {
    parts.push(`Pominięto ${result.skipped_dates.length} ${plural(result.skipped_dates.length, "dzień", "dni", "dni")} z istniejącymi wpisami: ${result.skipped_dates.map(formatDayLabel).join(", ")}.`);
  }
  el.importResult.innerHTML = `<p class="form-status success">${escapeHtml(parts.join(" "))}</p>`;
  if (result.earliest_imported_date) {
    // Dane sprzed startu planu: ocena planu i "zmiana od startu" ich nie obejmują, dopóki start nie zostanie przesunięty.
    el.importResult.innerHTML += `<p class="hint">Zaimportowane dane sięgają ${escapeHtml(formatDayLabel(result.earliest_imported_date))} – wcześniej niż start planu (${escapeHtml(formatDayLabel(result.plan_started_on))}). Jeśli realizujesz plan od tamtej pory, zmień datę startu w <a href="#/goals">Celach</a>.</p>`;
  }
  toast(parts[0], "success");
}

el.exportBtn.addEventListener("click", () => withBusy(el.exportBtn, () => downloadCsv("/export", "calico.csv")).catch(toastError));

el.templateBtn.addEventListener("click", () =>
  withBusy(el.templateBtn, () => downloadCsv("/import/template", "calico-szablon-importu.csv")).catch(toastError)
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
    el.importResult.innerHTML = `<p class="form-status error">Plik jest za duży (maks. 1 MB).</p>`;
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

